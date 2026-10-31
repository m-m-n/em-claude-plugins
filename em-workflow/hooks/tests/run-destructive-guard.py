#!/usr/bin/env python3
"""Expectation suite for destructive-guard.py.

    python3 em-workflow/hooks/tests/run-destructive-guard.py

Exits non-zero on the first mismatch, so it drops straight into CI or a
pre-push check. Pass a path to test a copy elsewhere, e.g. the installed
one under ~/.claude/hooks/.

Two halves carry equal weight. The `deny` and `ask` cases guard the point of
the hook: a genuinely destructive command must not slip through. The `allow`
cases guard the cost of getting there: every false positive stalls an
unattended run, and each one here is a shape that actually did — a `rm -rf`
written inside a quoted string, a here-doc body holding shell examples, a
redirect to /dev/null read as another path to delete.

Each case is `[decision, label, command]`. A case may carry a fourth element,
an object that sets the situation the hook is judged in:

    {"cwd": "<absolute path>", "batch": true}

`cwd` is sent as the payload's working directory. `batch` sets CLAUDE_BATCH for
that case. Both keys are optional; a three-element case sends no working
directory and runs with CLAUDE_BATCH cleared.

A `cwd` may contain the placeholder {merge_fixture}. Once per run the runner
builds a temporary directory holding a git repository with one commit, and
replaces the placeholder with that repository's root before it sends the
payload (the directory is removed when the run ends). The repository holds:

    .claude/worktrees/em-workflow/demo/integration            a registered worktree
                                                              on em-workflow/demo/integration
    .claude/worktrees/em-workflow/2fa-login-v2/integration    a registered worktree
                                                              on em-workflow/2fa-login-v2/integration
    .claude/worktrees/em-workflow/unregistered/integration    a plain directory of the
                                                              same shape, not a worktree

The hook's allow for the canonical PR merge reads the disk for the
registration, so the cases that judge it name these paths. Any other `cwd` is
sent unchanged and need not exist. No repository is built when no case uses
the placeholder.

CLAUDE_BATCH is cleared for every run unless a case asks for it. The hook
demotes `ask` to `deny` when it sees that variable (nobody is there to
answer), which would fail every `ask` case if the suite happened to run inside
a batch session. The demotion itself is covered by the last check, which sets
the variable back.

Every evaluation is bounded at GUARD_TIMEOUT_SECONDS. A case that runs past
the limit is stopped, counted as a FAIL marked as a timeout, and the run goes
on with the remaining cases, so a performance regression in the hook shows up
as a FAIL instead of hanging the suite.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "destructive-guard-cases.json")
GUARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "destructive-guard.py")

# Limit for one evaluation, in seconds. Mirrors the "timeout" hooks.json sets
# for destructive-guard.py: past it the real hook's verdict is lost, so the
# suite treats the same overrun as a failure.
GUARD_TIMEOUT_SECONDS = 10

# The decision verdict() reports for an evaluation that ran past the limit.
TIMED_OUT = "(timeout)"

# A case's `cwd` may contain this; judge() replaces it with the root of the
# repository build_merge_fixture() makes.
MERGE_FIXTURE_PLACEHOLDER = "{merge_fixture}"

# Features whose integration worktree the fixture registers with
# `git worktree add`, and features that get a plain directory of the same shape.
MERGE_FIXTURE_REGISTERED = ("demo", "2fa-login-v2")
MERGE_FIXTURE_UNREGISTERED = ("unregistered",)

# Limit for one git command while the fixture is built, in seconds.
GIT_TIMEOUT_SECONDS = 60


def case_options(case):
    """The (cwd, batch) a case asks for: its optional fourth element, or the
    defaults (no working directory, CLAUDE_BATCH cleared). A fourth element
    that is not an object holding only `cwd` (a string) and `batch` (a
    boolean) ends the run: a case the runner cannot honour must not pass by
    being judged in some other situation."""
    if len(case) == 3:
        return None, False
    options = case[3] if len(case) == 4 else None
    ok = (
        isinstance(options, dict)
        and set(options) <= {"cwd", "batch"}
        and isinstance(options.get("cwd", ""), str)
        and isinstance(options.get("batch", False), bool)
    )
    if not ok:
        sys.exit("malformed case (want [decision, label, command] or a fourth "
                 "element {\"cwd\": str, \"batch\": bool}): %r" % (case,))
    return options.get("cwd"), options.get("batch", False)


def uses_placeholder(case):
    """Whether a case's `cwd` contains the {merge_fixture} placeholder. A case
    that is not well formed has none (case_options() ends the run on it)."""
    options = case[3] if len(case) == 4 else None
    cwd = options.get("cwd") if isinstance(options, dict) else None
    return isinstance(cwd, str) and MERGE_FIXTURE_PLACEHOLDER in cwd


def build_merge_fixture():
    """A temporary git repository with one commit whose integration worktrees
    are registered (MERGE_FIXTURE_REGISTERED), plus plain directories of the
    same shape (MERGE_FIXTURE_UNREGISTERED). Returns (temporary directory,
    repository root); the caller removes the directory.

    git runs with a scrubbed environment, so the developer's global git
    configuration and hooks cannot change the result. A repository that cannot
    be built ends the run: the cases that name it would otherwise be judged
    against paths that do not exist."""
    tmp = tempfile.TemporaryDirectory(prefix="destructive-guard-merge-")
    base = os.path.realpath(tmp.name)
    home = os.path.join(base, "home")
    root = os.path.join(base, "repo")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": home,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }

    def git(*args):
        subprocess.run(
            [
                "git",
                "-c", "user.name=fixture",
                "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false",
                "-c", "core.hooksPath=" + os.devnull,
                *args,
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )

    try:
        os.makedirs(home)
        os.makedirs(root)
        git("init", "-q")
        git("commit", "-q", "--allow-empty", "-m", "fixture")
        for feature in MERGE_FIXTURE_REGISTERED:
            git(
                "worktree", "add", "-q",
                "-b", "em-workflow/%s/integration" % feature,
                ".claude/worktrees/em-workflow/%s/integration" % feature,
            )
        for feature in MERGE_FIXTURE_UNREGISTERED:
            os.makedirs(
                os.path.join(root, ".claude", "worktrees", "em-workflow", feature, "integration")
            )
    except (OSError, subprocess.SubprocessError) as exc:
        tmp.cleanup()
        detail = (getattr(exc, "stderr", None) or "").strip() or str(exc)
        sys.exit("cannot build the %s repository: %s" % (MERGE_FIXTURE_PLACEHOLDER, detail))
    return tmp, root


def verdict(command, batch=False, cwd=None):
    """Run the guard over one command and return (decision, reason). CWD, when
    given, is the payload's working directory."""
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)
    # The guard loads a sibling module; no run of it leaves bytecode behind.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if batch:
        env["CLAUDE_BATCH"] = "1"
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    try:
        proc = subprocess.run(
            [sys.executable, GUARD],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=GUARD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run() has already killed and reaped the child.
        return TIMED_OUT, "%d 秒の制限時間を超えたため中断した。" % GUARD_TIMEOUT_SECONDS
    if proc.returncode != 0:
        return "(exit %d)" % proc.returncode, (proc.stderr or "").strip()
    if not proc.stdout.strip():
        return "(silent)", "フックが判定を出さずに終了した。"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


def timeout_marker(got):
    """The suffix a FAIL line carries when the evaluation timed out."""
    if got == TIMED_OUT:
        return " [TIMEOUT %ds]" % GUARD_TIMEOUT_SECONDS
    return ""


def main():
    with open(CASES, encoding="utf-8") as f:
        cases = json.load(f)

    fixture, root = None, None
    if any(uses_placeholder(case) for case in cases):
        fixture, root = build_merge_fixture()
    try:
        return judge(cases, root)
    finally:
        if fixture is not None:
            fixture.cleanup()


def judge(cases, root):
    """Run every case and the unattended-demotion check; return the exit
    status. ROOT is the fixture repository's root, or None when no case uses
    the placeholder."""
    failed = []

    for case in cases:
        want, label, command = case[:3]
        cwd, batch = case_options(case)
        if cwd is not None and root is not None:
            cwd = cwd.replace(MERGE_FIXTURE_PLACEHOLDER, root)
        got, reason = verdict(command, batch=batch, cwd=cwd)
        if got != want:
            failed.append((label, want, got, reason))
        print(f"{'ok  ' if got == want else 'FAIL'} {want:5} {label}{timeout_marker(got)}")
        if got != want:
            print(f"       got={got} {reason[:150]}")

    # The unattended demotion: with nobody to answer, `ask` has to become
    # `deny` rather than hang a batch run on a prompt.
    got, reason = verdict("echo x > ~/.claude/settings.json", batch=True)
    label = "無人実行では ask が deny に降格"
    if got != "deny":
        failed.append((label, "deny", got, reason))
    print(f"{'ok  ' if got == 'deny' else 'FAIL'} deny  {label}{timeout_marker(got)}")

    total = len(cases) + 1
    print(f"\n{total - len(failed)}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
