#!/usr/bin/env python3
"""recover-orphaned-task.py -- SC3 decision entry point for the
orphaned-implementer-recovery feature.

Normative source: feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md
(Shared Components SC3, SC5, SC6; Cross-task Design Decisions D1, D2, D3) and
feature-docs/orphaned-implementer-recovery/tasks/task0003.md.

Decides, for ONE candidate task, whether the session that launched its
implementer is provably gone. Called by the orchestrator's I.2.b reconcile
step after it has already established the candidate conditions it owns: the
task worktree and task branch exist, and the Agent index resolves no live
agent. This script never re-checks those two conditions.

Evidence pipeline (fixed order -- each step's failure ends the run as
`residual` with its SC6 reason code; no write, no helper invocation):

  1. an `agents.jsonl` entry for the task exists            -> no-agent-entry
  2. that entry carries a `session_id`                      -> no-session-id
  3. the value passes SC5's format rule                     -> invalid-session-id
  4. the current session's identity + start resolve (D2)    -> current-session-unknown
  5. the recorded identity differs from the current one     -> same-session
  6. the transcripts directory (D1) resolves and exists,
     and the assembled transcript path resolves inside it   -> transcripts-dir-missing
  7. the transcript yields at least one usable timestamp     -> transcript-unreadable
  8. its newest usable timestamp is strictly older than the
     current session's start (D3)                            -> transcript-active

Only once all eight steps pass does the journal pre-check run (the task's
final journal event must be `launched`; an already-terminal event is
`noop_terminal`, anything else is the SC6 `journal-not-launched` residual).
This pre-check exists solely to avoid a pointless invocation of the journal
helper -- SC2's own in-lock replay remains the authoritative check.

On proof, the journal helper (SC2, `journal-append-failed.py` by default,
`--journal-helper` for testing) is invoked exactly once with the task
identifier and reason `orphaned`; its outcome is propagated. This script
NEVER writes the journal itself (Layer Structure, IMPLEMENTATION.md).

Outcome: one line of JSON on stdout with keys `outcome`
(`recovered` | `noop_terminal` | `residual`), `task`, `reason` (an SC6 code
for `residual`; empty otherwise -- SC6 defines reason codes for the
`residual` outcome only, so `noop_terminal` reports an empty reason exactly
like `recovered` does). Exit 0 for every decided outcome. A non-zero exit
means usage or internal error (including a journal-helper failure), is
never accompanied by a journal write, and the caller treats it as Residual.
Diagnostics go to stderr, never stdout.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# SC6 -- closed set of residual reason codes.
# ---------------------------------------------------------------------------

REASON_NO_AGENT_ENTRY = "no-agent-entry"
REASON_NO_SESSION_ID = "no-session-id"
REASON_INVALID_SESSION_ID = "invalid-session-id"
REASON_CURRENT_SESSION_UNKNOWN = "current-session-unknown"
REASON_SAME_SESSION = "same-session"
REASON_TRANSCRIPTS_DIR_MISSING = "transcripts-dir-missing"
REASON_TRANSCRIPT_UNREADABLE = "transcript-unreadable"
REASON_TRANSCRIPT_ACTIVE = "transcript-active"
REASON_JOURNAL_NOT_LAUNCHED = "journal-not-launched"

TERMINAL_JOURNAL_EVENTS = ("merged", "failed")

DEFAULT_JOURNAL_HELPER_NAME = "journal-append-failed.py"
ORPHANED_REASON = "orphaned"

# Module-level so tests can monkeypatch it to exercise the default-helper
# wiring (AC-7) without touching the real sibling file or the real script
# location.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# SC5 -- session_id validation rule (pure function, unit-tested directly).
# ---------------------------------------------------------------------------

# Non-empty, <=64 chars, first char ASCII letter/digit, remainder ASCII
# letters/digits/hyphen/underscore. Dots, path separators, whitespace and NUL
# are all excluded from both character classes, which makes a `..` segment
# and a path-separator escape unrepresentable.
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def is_valid_session_id(value):
    return isinstance(value, str) and bool(SESSION_ID_RE.match(value))


# ---------------------------------------------------------------------------
# D1 -- transcripts directory derivation (pure function, unit-tested
# directly) and path containment.
# ---------------------------------------------------------------------------


def encode_cwd(cwd):
    """Every character outside {ASCII letter, digit, hyphen} becomes exactly
    one hyphen -- no collapsing of consecutive replacements. The leading
    path separator becomes a leading hyphen as a consequence of the same
    rule (it is not ASCII letter/digit/hyphen)."""
    return re.sub(r"[^A-Za-z0-9-]", "-", cwd)


def default_transcripts_dir(cwd=None):
    """`~/.claude/projects/{encoded}` where `{encoded}` is `encode_cwd` applied
    to the invoking process's absolute working directory. `--transcripts-dir`
    replaces this derivation entirely; production code path only, never
    exercised by a test with the real `~/.claude` (AC-4)."""
    if cwd is None:
        cwd = os.getcwd()
    return os.path.join(os.path.expanduser("~/.claude/projects"), encode_cwd(cwd))


def resolve_transcript_path(transcripts_dir, session_id, check_under_claude_projects):
    """Assemble `{transcripts_dir}/{session_id}.jsonl` and confirm it resolves
    INSIDE `transcripts_dir` (symlink- and `..`-aware, via realpath), and,
    when `check_under_claude_projects` is true, additionally inside
    `~/.claude/projects/`. Returns the resolved path, or None on any
    containment violation -- no file is opened before this check runs.

    Defense-in-depth: by the time this runs, `session_id` has already passed
    `is_valid_session_id`, which forbids path separators and dots outright,
    so a real escape here should be unreachable. This function is still
    unit-tested directly with a bypassing input (Test Notes: containment
    regressions must be localised quickly)."""
    transcripts_dir_real = os.path.realpath(transcripts_dir)
    candidate = os.path.join(transcripts_dir, session_id + ".jsonl")
    candidate_real = os.path.realpath(candidate)
    try:
        if os.path.commonpath([transcripts_dir_real, candidate_real]) != transcripts_dir_real:
            return None
    except ValueError:
        return None  # different drives etc. -- never reachable on POSIX, fail safe anyway
    if check_under_claude_projects:
        claude_projects_real = os.path.realpath(os.path.expanduser("~/.claude/projects"))
        try:
            if os.path.commonpath([claude_projects_real, candidate_real]) != claude_projects_real:
                return None
        except ValueError:
            return None
    return candidate_real


# ---------------------------------------------------------------------------
# Timestamp parsing (D3) and transcript reading.
# ---------------------------------------------------------------------------


def parse_timestamp(value):
    """Parse an RFC3339-ish timestamp string; None on anything unparsable.
    A trailing `Z` is normalized to `+00:00` for portability across Python
    versions whose `datetime.fromisoformat` does not accept `Z` directly."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def newest_transcript_timestamp(transcript_path):
    """Newest usable timestamp across the transcript's JSONL lines (each
    line an object with a string `timestamp` field). Malformed lines,
    non-object lines and lines with an unusable timestamp are skipped
    (D3). None when the file is unreadable/absent or yields no usable
    timestamp at all -- both map to `transcript-unreadable`, never to "no
    activity"."""
    newest = None
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                dt = parse_timestamp(obj.get("timestamp"))
                if dt is None:
                    continue
                if newest is None or dt > newest:
                    newest = dt
    except OSError:
        return None
    return newest


# ---------------------------------------------------------------------------
# D2 -- current-session identity and start-time resolution.
# ---------------------------------------------------------------------------


def _first_entry_timestamp(lines):
    """The timestamp of the transcript's FIRST entry (first non-blank JSONL
    line) -- not the first parseable one. A malformed or timestamp-less
    first entry fails resolution outright rather than falling through to a
    later line (D2: "that file's ... first entry's timestamp")."""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            return None
        if not isinstance(obj, dict):
            return None
        return parse_timestamp(obj.get("timestamp"))
    return None


def _resolve_current_session_via_marker(marker, transcripts_dir):
    try:
        names = os.listdir(transcripts_dir)
    except OSError:
        return None
    candidates = []
    for name in names:
        path = os.path.join(transcripts_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        candidates.append((mtime, path))
    # Newest modification time first.
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    for _, path in candidates:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        if not any(marker in line for line in lines):
            continue
        # First transcript containing the token: commit to it. Its stem is
        # the current session identity regardless of what its first entry's
        # timestamp turns out to be.
        first_ts = _first_entry_timestamp(lines)
        if first_ts is None:
            return None
        stem = os.path.splitext(os.path.basename(path))[0]
        return stem, first_ts
    return None


def resolve_current_session(current_session_id, current_session_start, marker, transcripts_dir):
    """D2: form 1 (explicit id + start, together) takes precedence over
    form 2 (marker scan). Returns (session_id, start_datetime) or None when
    neither form resolves (-> current-session-unknown)."""
    if current_session_id and current_session_start:
        start_dt = parse_timestamp(current_session_start)
        if start_dt is None:
            return None
        return current_session_id, start_dt
    if marker:
        return _resolve_current_session_via_marker(marker, transcripts_dir)
    return None


# ---------------------------------------------------------------------------
# Agent index (agents.jsonl) reading.
# ---------------------------------------------------------------------------


def find_agent_entry(agents_index_path, task_id):
    """The LAST `agents.jsonl` line whose `task` field matches `task_id`
    (most recent launch wins, mirroring the journal's own last-event-wins
    replay convention). None when the file is absent/unreadable or carries
    no matching entry (-> no-agent-entry)."""
    last_match = None
    try:
        with open(agents_index_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("task") == task_id:
                    last_match = entry
    except OSError:
        return None
    return last_match


# ---------------------------------------------------------------------------
# Journal pre-check (non-authoritative; SC2's in-lock replay is the SSOT).
# ---------------------------------------------------------------------------


def replay_final_event(journal_path, task_id):
    """Last `event` (by file order) recorded for `task_id`; None when the
    file is absent/unreadable or carries no event for this task. Malformed
    lines are skipped."""
    last_event = None
    try:
        with open(journal_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("task") != task_id:
                    continue
                event = entry.get("event")
                if isinstance(event, str):
                    last_event = event
    except OSError:
        return None
    return last_event


# ---------------------------------------------------------------------------
# Journal-write layer invocation (D6, SC2 contract).
# ---------------------------------------------------------------------------


def default_journal_helper_path():
    """The sibling `journal-append-failed.py`, resolved relative to this
    script's own directory. Reads the module-level `_SCRIPT_DIR` so tests can
    monkeypatch it to exercise this wiring end to end against a stub, without
    touching the real script directory (AC-7)."""
    return os.path.join(_SCRIPT_DIR, DEFAULT_JOURNAL_HELPER_NAME)


def invoke_journal_helper(helper_path, journal_path, task_id):
    """Invoke the journal helper exactly once (SC2 contract:
    `--journal PATH --task TASKID --reason orphaned`) and propagate its
    outcome. Returns (outcome_dict, exit_code); outcome_dict is None when the
    helper failed (non-zero exit, unparsable stdout, or an unrecognized
    outcome value) -- a helper failure is NEVER reported as `recovered`."""
    cmd = [
        sys.executable,
        helper_path,
        "--journal",
        journal_path,
        "--task",
        task_id,
        "--reason",
        ORPHANED_REASON,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        print(
            "recover-orphaned-task: failed to invoke journal helper "
            f"{helper_path!r}: {exc}",
            file=sys.stderr,
        )
        return None, 1

    if proc.returncode != 0:
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        print(
            "recover-orphaned-task: journal helper exited "
            f"{proc.returncode}",
            file=sys.stderr,
        )
        return None, 1

    stdout = proc.stdout.strip()
    first_line = stdout.splitlines()[0] if stdout else ""
    try:
        parsed = json.loads(first_line)
    except ValueError:
        print(
            "recover-orphaned-task: journal helper produced unparsable "
            f"stdout: {stdout!r}",
            file=sys.stderr,
        )
        return None, 1

    helper_outcome = parsed.get("outcome") if isinstance(parsed, dict) else None
    if helper_outcome == "appended":
        return {"outcome": "recovered", "task": task_id, "reason": ""}, 0
    if helper_outcome == "noop_terminal":
        return {"outcome": "noop_terminal", "task": task_id, "reason": ""}, 0

    print(
        "recover-orphaned-task: unexpected journal helper outcome: "
        f"{helper_outcome!r}",
        file=sys.stderr,
    )
    return None, 1


# ---------------------------------------------------------------------------
# Outcome builders.
# ---------------------------------------------------------------------------


def _residual(task_id, reason):
    return {"outcome": "residual", "task": task_id, "reason": reason}, 0


def _noop_terminal(task_id):
    return {"outcome": "noop_terminal", "task": task_id, "reason": ""}, 0


# ---------------------------------------------------------------------------
# Decision entry point.
# ---------------------------------------------------------------------------


def decide(
    task_id,
    journal_path,
    agents_index_path,
    transcripts_dir=None,
    current_session_id=None,
    current_session_start=None,
    marker=None,
    journal_helper=None,
):
    """Run the evidence pipeline in fixed order for one task, then (on proof)
    the journal pre-check and helper invocation. Returns
    (outcome_dict_or_None, exit_code); outcome_dict is None only when
    exit_code is non-zero (usage/internal error -- never accompanied by a
    journal write)."""
    using_default_dir = transcripts_dir is None
    resolved_transcripts_dir = transcripts_dir if transcripts_dir is not None else default_transcripts_dir()

    # 1. Agent index entry.
    entry = find_agent_entry(agents_index_path, task_id)
    if entry is None:
        return _residual(task_id, REASON_NO_AGENT_ENTRY)

    # 2. Session identity present.
    recorded_session_id = entry.get("session_id")
    if not isinstance(recorded_session_id, str) or recorded_session_id == "":
        return _residual(task_id, REASON_NO_SESSION_ID)

    # 3. SC5 format validation -- before any path is assembled.
    if not is_valid_session_id(recorded_session_id):
        return _residual(task_id, REASON_INVALID_SESSION_ID)

    # 4. Current session resolution (D2).
    current = resolve_current_session(
        current_session_id, current_session_start, marker, resolved_transcripts_dir
    )
    if current is None:
        return _residual(task_id, REASON_CURRENT_SESSION_UNKNOWN)
    current_id, current_start = current

    # 5. Recorded identity differs from current.
    if recorded_session_id == current_id:
        return _residual(task_id, REASON_SAME_SESSION)

    # 6. Transcripts directory resolves and exists; path containment.
    if not os.path.isdir(resolved_transcripts_dir):
        return _residual(task_id, REASON_TRANSCRIPTS_DIR_MISSING)

    transcript_path = resolve_transcript_path(
        resolved_transcripts_dir, recorded_session_id, using_default_dir
    )
    if transcript_path is None:
        return _residual(task_id, REASON_TRANSCRIPT_UNREADABLE)

    # 7. At least one usable timestamp.
    newest_ts = newest_transcript_timestamp(transcript_path)
    if newest_ts is None:
        return _residual(task_id, REASON_TRANSCRIPT_UNREADABLE)

    # 8. Strictly older than the current session's start (D3).
    try:
        proven_gone = newest_ts < current_start
    except TypeError:
        # Incomparable aware/naive datetimes: cannot prove anything from
        # this evidence -- fail safe rather than raise.
        return _residual(task_id, REASON_TRANSCRIPT_UNREADABLE)
    if not proven_gone:
        return _residual(task_id, REASON_TRANSCRIPT_ACTIVE)

    # Journal pre-check (non-authoritative; avoids a pointless helper call).
    final_event = replay_final_event(journal_path, task_id)
    if final_event in TERMINAL_JOURNAL_EVENTS:
        return _noop_terminal(task_id)
    if final_event != "launched":
        return _residual(task_id, REASON_JOURNAL_NOT_LAUNCHED)

    # On proof: invoke the journal helper exactly once.
    helper_path = journal_helper if journal_helper else default_journal_helper_path()
    return invoke_journal_helper(helper_path, journal_path, task_id)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Decide whether the session that launched a task's implementer "
            "is provably gone, and on proof append a `failed` journal event "
            "(reason `orphaned`) via the journal-write helper."
        )
    )
    parser.add_argument("--journal", required=True, help="Path to journal.jsonl")
    parser.add_argument("--agents-index", required=True, help="Path to agents.jsonl")
    parser.add_argument("--task", required=True, help="Task id, e.g. task0003")
    parser.add_argument(
        "--transcripts-dir",
        default=None,
        help="Overrides the D1 default derivation entirely",
    )
    parser.add_argument("--current-session-id", default=None)
    parser.add_argument("--current-session-start", default=None)
    parser.add_argument(
        "--marker",
        default=None,
        help="D2 form 2: token to find in the current session's own transcript",
    )
    parser.add_argument(
        "--journal-helper",
        default=None,
        help="Overrides the default sibling journal-append-failed.py",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    outcome, exit_code = decide(
        task_id=args.task,
        journal_path=args.journal,
        agents_index_path=args.agents_index,
        transcripts_dir=args.transcripts_dir,
        current_session_id=args.current_session_id,
        current_session_start=args.current_session_start,
        marker=args.marker,
        journal_helper=args.journal_helper,
    )
    if outcome is not None:
        print(json.dumps(outcome, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
