#!/usr/bin/env python3
"""merge-ci-wait.py -- bounded wait for the PR checks of a pushed head.

Decision script of the unattended-merge feature (IMPLEMENTATION.md C1, C2, C8
and decision D7). It makes ONE bounded invocation per call: the merge skill
repeats the call until the outcome is final, carrying the absolute `deadline`
this script echoes. No loop over this script exists in any command string.

Arguments (long options only):

  --project-root PATH   main working tree root (gh is run from there)
  --repo OWNER/NAME     GitHub repository, named explicitly on every gh read
  --pr N                pull request number
  --head SHA            the pushed / verified head (40 lowercase hex)
  --deadline-in SECS    first call: deadline = now + SECS (absolute epoch)
  --deadline EPOCH      later calls: the deadline an earlier call echoed
                        (exactly one of --deadline-in / --deadline)
  --budget SECS         per-invocation budget, default 540, at most 570
  --interval SECS       sleep between polls, default 30
  --settle SECS         how long zero checks are tolerated, default 60

Output: exactly one JSON object on one stdout line with the keys `outcome`,
`reason`, `detail`, `deadline` (absolute epoch seconds, always echoed).

  outcome   reason          meaning
  --------  --------------  ---------------------------------------------
  passed    null            at least one check, every one passing/skipped
  no_checks null            zero checks once the settle window has passed
  pending   null            budget exhausted before the deadline: call
                            again with the echoed --deadline
  stop      ci_failed       a check failed or was cancelled (names in detail)
  stop      ci_timeout      deadline reached while checks were pending
  stop      pr_head_moved   the PR head is no longer --head

Each poll reads the PR head (`gh pr view --json headRefOid`) and, when it
equals --head, the PR checks (`gh pr checks --json name,bucket`). Only these
two read operations are ever run. gh's result category (`bucket`) is grouped:
pass / skipping count as passing, fail / cancel as failing, anything else as
pending.

One invocation returns by min(deadline, start + budget). Every gh call has a
time limit (GH_CALL_LIMIT) that also fits inside what is left of that window,
and a call that overruns is killed together with its process group. The worst
case duration is the budget plus WORST_CASE_OVERRUN; with the default budget
that stays below the 600 s Bash limit.

Exit codes: 0 when a decision was produced (stop outcomes included), 2 for
missing or malformed arguments, 1 for an internal failure (for example gh
failing on every one of MAX_CONSECUTIVE_GH_FAILURES polls in a row). Nothing is
ever reported as passed from an unreadable answer: diagnostics go to stderr.
"""

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import time

# Defaults documented in --help and in the module docstring (C8).
DEFAULT_BUDGET = 540
DEFAULT_INTERVAL = 30
DEFAULT_SETTLE = 60
# The Bash tool stops a call at 600 s; no accepted budget may reach it.
MAX_BUDGET = 570
# Upper limit for a single gh child process (further capped by the window).
GH_CALL_LIMIT = 60
# Time allowed for reaping a killed gh child, and the documented margin by
# which an invocation may exceed its budget (kill, reap, final write).
KILL_GRACE = 5
WORST_CASE_OVERRUN = 10
# gh answering with an error this many polls in a row ends the run.
MAX_CONSECUTIVE_GH_FAILURES = 3

PASS_BUCKETS = frozenset({"pass", "skipping"})
FAIL_BUCKETS = frozenset({"fail", "cancel"})

MAX_LISTED_NAMES = 10
MAX_NAME_LENGTH = 80

SHA_RE = re.compile(r"[0-9a-f]{40}")
PR_RE = re.compile(r"[1-9][0-9]{0,11}")
REPO_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+")

_current_child = None


class InternalFailure(Exception):
    """A condition that is not a decision (exit 1, diagnostics on stderr)."""


def positive_number(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not a number: %r" % text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return value


def non_negative_number(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not a number: %r" % text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be a non-negative finite number")
    return value


def budget_number(text):
    value = positive_number(text)
    if value > MAX_BUDGET:
        raise argparse.ArgumentTypeError(
            "must not exceed %d seconds (the Bash tool limit is 600)" % MAX_BUDGET
        )
    return value


def sha_value(text):
    if not SHA_RE.fullmatch(text):
        raise argparse.ArgumentTypeError("must be 40 lowercase hexadecimal characters")
    return text


def pr_value(text):
    if not PR_RE.fullmatch(text):
        raise argparse.ArgumentTypeError("must be a positive decimal integer")
    return text


def repo_value(text):
    if not REPO_RE.fullmatch(text) or text.rsplit("/", 1)[1] in (".", ".."):
        raise argparse.ArgumentTypeError("must be OWNER/NAME")
    return text


def build_parser():
    parser = argparse.ArgumentParser(
        prog="merge-ci-wait.py",
        description=(
            "Bounded wait for the PR checks of a pushed head. One invocation "
            "returns within --budget; repeat it with the echoed --deadline."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--project-root", required=True,
                        help="main working tree root")
    parser.add_argument("--repo", required=True, type=repo_value,
                        help="GitHub repository as OWNER/NAME")
    parser.add_argument("--pr", required=True, type=pr_value,
                        help="pull request number")
    parser.add_argument("--head", required=True, type=sha_value,
                        help="expected PR head commit (40 lowercase hex)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deadline-in", type=positive_number, metavar="SECONDS",
                       help="first call: absolute deadline = now + SECONDS")
    group.add_argument("--deadline", type=positive_number, metavar="EPOCH_SECONDS",
                       help="later calls: the deadline an earlier call echoed")
    parser.add_argument("--budget", type=budget_number, default=DEFAULT_BUDGET,
                        metavar="SECONDS",
                        help="per-invocation budget (default %(default)s, "
                             "at most " + str(MAX_BUDGET) + ")")
    parser.add_argument("--interval", type=positive_number, default=DEFAULT_INTERVAL,
                        metavar="SECONDS",
                        help="sleep between polls (default %(default)s)")
    parser.add_argument("--settle", type=non_negative_number, default=DEFAULT_SETTLE,
                        metavar="SECONDS",
                        help="how long zero checks are waited on before "
                             "no_checks (default %(default)s)")
    return parser


def as_number(value):
    """Integral values print as integers so the deadline round-trips cleanly."""
    if value == int(value) and abs(value) < 2 ** 53:
        return int(value)
    return value


def emit(outcome, reason, detail, deadline):
    record = {
        "outcome": outcome,
        "reason": reason,
        "detail": detail,
        "deadline": as_number(deadline),
    }
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def clean_text(text, limit):
    """Untrusted free text reduced to one printable line of bounded length."""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in str(text))
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 3] + "..."
    return cleaned


def diagnostic(message):
    sys.stderr.write("merge-ci-wait: %s\n" % message)
    sys.stderr.flush()


# --- gh child processes ----------------------------------------------------


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except OSError:
            pass


def reap(proc):
    try:
        proc.communicate(timeout=KILL_GRACE)
    except subprocess.TimeoutExpired:
        pass
    finally:
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass


def run_gh(args, cwd, limit):
    """Run gh with a time limit; returns (status, returncode, stdout, stderr).

    status is "ok" (the process ended), "timeout" (killed at the limit) or
    "error" (gh could not be started).
    """
    global _current_child
    env = dict(os.environ)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["NO_COLOR"] = "1"
    try:
        proc = subprocess.Popen(
            ["gh"] + args,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return "error", None, "", "cannot start gh: %s" % exc.__class__.__name__
    _current_child = proc
    try:
        out, err = proc.communicate(timeout=max(limit, 0.01))
    except subprocess.TimeoutExpired:
        kill_group(proc)
        reap(proc)
        return "timeout", None, "", ""
    finally:
        _current_child = None
    return (
        "ok",
        proc.returncode,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"),
    )


def on_terminate(signum, _frame):
    if _current_child is not None:
        kill_group(_current_child)
    sys.exit(128 + signum)


# --- one poll --------------------------------------------------------------


class Poll:
    """The result of one poll: kind is moved / checks / timeout / error."""

    def __init__(self, kind, **fields):
        self.kind = kind
        self.__dict__.update(fields)


def read_head(opts, limit):
    status, code, out, err = run_gh(
        ["pr", "view", opts.pr, "--repo", opts.repo, "--json", "headRefOid"],
        opts.project_root, limit,
    )
    if status == "timeout":
        return "timeout", None
    if status == "error":
        return "error", clean_text(err, 200)
    if code != 0:
        return "error", "gh pr view exited %s" % code
    try:
        head = json.loads(out)["headRefOid"]
    except (ValueError, KeyError, TypeError):
        return "error", "gh pr view answered with unreadable JSON"
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        return "error", "gh pr view reported an unexpected head value"
    return "ok", head


def read_checks(opts, limit):
    status, code, out, err = run_gh(
        ["pr", "checks", opts.pr, "--repo", opts.repo, "--json", "name,bucket"],
        opts.project_root, limit,
    )
    if status == "timeout":
        return "timeout", None
    if status == "error":
        return "error", clean_text(err, 200)
    text = out.strip()
    if not text:
        # gh prints nothing on stdout and a notice on stderr when a PR has no
        # checks at all.
        if "no checks reported" in err.lower():
            return "ok", []
        return "error", "gh pr checks exited %s without output" % code
    try:
        checks = json.loads(text)
    except ValueError:
        return "error", "gh pr checks answered with unreadable JSON"
    if not isinstance(checks, list):
        return "error", "gh pr checks answered with an unexpected JSON shape"
    return "ok", checks


def classify(checks):
    """Group checks by gh's result category: (failed names, pending count, pass count)."""
    failed = []
    pending = 0
    passing = 0
    for check in checks:
        bucket = None
        name = "(unnamed)"
        if isinstance(check, dict):
            if isinstance(check.get("bucket"), str):
                bucket = check["bucket"]
            if isinstance(check.get("name"), str):
                name = check["name"]
        if bucket in FAIL_BUCKETS:
            failed.append(name)
        elif bucket in PASS_BUCKETS:
            passing += 1
        else:
            pending += 1
    return failed, pending, passing


def poll_once(opts, remaining):
    """One poll: the head first, the checks only while the head is unchanged."""
    status, value = read_head(opts, min(GH_CALL_LIMIT, remaining()))
    if status != "ok":
        return Poll(status, message=value)
    if value != opts.head:
        return Poll("moved", head=value)
    left = remaining()
    if left <= 0:
        return Poll("timeout", message=None)
    status, value = read_checks(opts, min(GH_CALL_LIMIT, left))
    if status != "ok":
        return Poll(status, message=value)
    return Poll("checks", checks=value)


def describe_failed(names):
    unique = []
    for name in names:
        shown = clean_text(name, MAX_NAME_LENGTH) or "(unnamed)"
        if shown not in unique:
            unique.append(shown)
    listed = unique[:MAX_LISTED_NAMES]
    detail = "failed checks: " + ", ".join(listed)
    if len(unique) > len(listed):
        detail += " (+%d more)" % (len(unique) - len(listed))
    return detail


# --- the bounded wait ------------------------------------------------------


def wait(opts, deadline):
    """Run one bounded invocation; returns (outcome, reason, detail)."""
    budget_end = time.monotonic() + opts.budget

    def remaining():
        return min(budget_end - time.monotonic(), deadline - time.time())

    first_poll = None
    consecutive_errors = 0
    last_state = "no poll completed"

    while remaining() > 0:
        if first_poll is None:
            first_poll = time.monotonic()
        result = poll_once(opts, remaining)

        if result.kind == "moved":
            return ("stop", "pr_head_moved",
                    "PR head is now %s, expected %s" % (result.head, opts.head))

        if result.kind == "error":
            consecutive_errors += 1
            last_state = "last gh read failed"
            if consecutive_errors >= MAX_CONSECUTIVE_GH_FAILURES:
                raise InternalFailure(
                    "gh failed on %d polls in a row: %s"
                    % (consecutive_errors, clean_text(result.message, 200))
                )
        elif result.kind == "timeout":
            last_state = "last gh read timed out"
        else:
            consecutive_errors = 0
            failed, pending, passing = classify(result.checks)
            total = len(result.checks)
            if failed:
                return "stop", "ci_failed", describe_failed(failed)
            if total == 0:
                if time.monotonic() - first_poll >= opts.settle:
                    return ("no_checks", None,
                            "no checks reported after the %g s settle window"
                            % opts.settle)
                last_state = "no checks yet, inside the settle window"
            elif pending == 0:
                return ("passed", None,
                        "%d check(s) passed or were skipped" % passing)
            else:
                last_state = "%d of %d check(s) pending" % (pending, total)

        left = remaining()
        if left <= 0:
            break
        time.sleep(min(opts.interval, left))

    if deadline - time.time() <= 0:
        return ("stop", "ci_timeout",
                "deadline reached with checks not complete (%s)" % last_state)
    return ("pending", None,
            "budget exhausted before the deadline (%s)" % last_state)


def main(argv=None):
    parser = build_parser()
    opts = parser.parse_args(argv)
    if not os.path.isdir(opts.project_root):
        parser.error("--project-root is not a directory")

    if opts.deadline_in is not None:
        deadline = round(time.time() + opts.deadline_in, 3)
    else:
        deadline = opts.deadline

    signal.signal(signal.SIGTERM, on_terminate)
    signal.signal(signal.SIGINT, on_terminate)

    try:
        outcome, reason, detail = wait(opts, deadline)
    except InternalFailure as exc:
        diagnostic(str(exc))
        return 1
    if outcome == "stop":
        emit("stop", reason, detail, deadline)
    else:
        emit(outcome, None, detail, deadline)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # internal failure: never a silent decision
        diagnostic("internal failure: %s" % exc.__class__.__name__)
        sys.exit(1)
