#!/usr/bin/env python3
"""recover-orphaned-task.py -- SC3' decision entry point for the
orphaned-implementer-recovery feature, extended by
stale-launched-retry-recovery.

Normative source: feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md
(Shared Components SC3, SC5, SC6; Cross-task Design Decisions D1, D2, D3, D7)
and feature-docs/orphaned-implementer-recovery/tasks/task0003.md,
task0006.md; extended by
feature-docs/stale-launched-retry-recovery/IMPLEMENTATION.md (Shared
Components SC3', SC6, the Evidence inputs table, the Agent-identity binding
rule; Cross-task Design Decisions D-A through D-F) and
feature-docs/stale-launched-retry-recovery/tasks/task0002.md.

Decides, for ONE candidate task, whether the session that launched its
implementer is provably gone. Called by the orchestrator's I.2.b reconcile
step after it has already established the candidate conditions it owns: the
task's journal last event is `launched`, the task's `Task()` call is not
among this reconcile step's own currently-outstanding calls, and the Agent
index lookup resolves no live agent. Artifact state (task worktree / task
branch presence) is evidence, never a precondition -- the new chain below
accepts the caller's own observations of them as evidence inputs (D-B).

Two chains, selected by whether the caller supplies at least one of seven
new, optional evidence inputs (D-A):

LEGACY CHAIN (no evidence input supplied) -- unchanged, fixed order, each
step's failure ending the run as `residual` with its SC6 reason code (no
write, no helper invocation):

  1. an `agents.jsonl` entry for the task exists            -> no-agent-entry
  2. that entry is bound to the launch under recovery (D7): its own `at`
     is not earlier than the last `launched` journal event's `at` for the
     task by more than the binding tolerance -- skipped when the journal
     records no `launched` event for the task at all          -> stale-agent-entry
  3. that entry carries a `session_id`                      -> no-session-id
  4. the value passes SC5's format rule                     -> invalid-session-id
  5. the current session's identity + start resolve (D2)    -> current-session-unknown
  6. the recorded identity differs from the current one     -> same-session
  7. the transcripts directory (D1) resolves and exists,
     and the assembled transcript path resolves inside it   -> transcripts-dir-missing
  8. the transcript yields at least one usable timestamp     -> transcript-unreadable
  9. its newest usable timestamp is strictly older than the
     current session's start (D3)                            -> transcript-active

Only once all eight steps pass does the journal pre-check run (the task's
final journal event must be `launched`; an already-terminal event is
`noop_terminal`, anything else is the SC6 `journal-not-launched` residual).
This pre-check exists solely to avoid a pointless invocation of the journal
helper -- SC2's own in-lock replay remains the authoritative check. On
proof, the journal helper is invoked exactly once with reason `orphaned`
and no launch identity.

NEW CHAIN (at least one of the seven evidence inputs supplied) -- entered
ONLY from step 6's same-session branch above (the recorded identity equals
the current one), so it structurally never runs for a different session's
launch (D-A). Its own fixed order (`evaluate_stale_launched_chain`,
self-contained and independently callable):

  1. each of `--worktree-present` and `--branch-present` is an observation,
     exactly `yes` or exactly `no` (case-sensitive), accepted as evidence;
     decided before any agent index read, any path assembly and any file
     open. An absent or unrecognized observation on either flag ->
     task-artifacts-missing (its narrowed meaning: absent or unrecognized,
     never a recognized `no`); a recognized pair (any of the four yes/no
     combinations) is kept as evidence and the chain proceeds -- `no` never
     ends the chain by itself. Then the task's last journal event: a
     terminal event is `noop_terminal`, any event other than `launched` is
     -> journal-not-launched
  2. an `agents.jsonl` entry for the task exists and is D7-bound (reusing
     the legacy functions, not restating them)
     -> no-agent-entry / stale-agent-entry
  3. the entry carries a `session_id` passing SC5's format rule, and the
     current session's identity + start resolve (D2)
     -> no-session-id / invalid-session-id / current-session-unknown
  4. the agent-identity binding rule holds: the entry names exactly one
     distinct candidate, its recorded worktree matches `--task-worktree`,
     and `--stop-target` equals that candidate; `session_id` is never a
     candidate and never becomes the stop target on any path
     -> agent-identity-unproven
  5. `--launch-termination` is `terminated` (`running` is distinguished;
     every other value, including an absent input, is unproven)
     -> agent-still-live / agent-termination-unproven
  6. `--stop-result` is `not-running` for the SAME bound target
     -> stop-result-unproven
  7. the journal helper is invoked exactly once with reason `stale-launched`
     and the last `launched` event's raw `at` as the launch identity (D-C);
     its outcomes map: `appended` -> `recovered`, `noop_terminal` ->
     `noop_terminal`, `launch_changed` -> `residual`/`launch-changed` (D-D)

No elapsed-time threshold and no idle-interval input exists anywhere in the
new chain; doubt at any step is a residual, never a pass (NFR1).

On proof (either chain), the journal helper (SC2', `journal-append-failed.py`
by default, `--journal-helper` for testing) is invoked exactly once; its
outcome is propagated. This script NEVER writes the journal itself (Layer
Structure, IMPLEMENTATION.md).

Outcome: one line of JSON on stdout with keys `outcome`
(`recovered` | `noop_terminal` | `residual`), `task`, `reason` (an SC6 code
for `residual`; empty otherwise -- SC6 defines reason codes for the
`residual` outcome only, so `noop_terminal` reports an empty reason exactly
like `recovered` does). Exit 0 for every decided outcome. A non-zero exit
means usage or internal error (including a journal-helper failure), is
never accompanied by a journal write, and the caller treats it as Residual.
Diagnostics go to stderr, never stdout.

Full closed set of `residual` reason codes (SC6, sixteen values): the ten
pre-existing values above, plus six added by the new chain:
`task-artifacts-missing`, `agent-identity-unproven`,
`agent-termination-unproven`, `agent-still-live`, `stop-result-unproven`,
`launch-changed`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# SC6 -- closed set of residual reason codes.
# ---------------------------------------------------------------------------

REASON_NO_AGENT_ENTRY = "no-agent-entry"
REASON_STALE_AGENT_ENTRY = "stale-agent-entry"
REASON_NO_SESSION_ID = "no-session-id"
REASON_INVALID_SESSION_ID = "invalid-session-id"
REASON_CURRENT_SESSION_UNKNOWN = "current-session-unknown"
REASON_SAME_SESSION = "same-session"
REASON_TRANSCRIPTS_DIR_MISSING = "transcripts-dir-missing"
REASON_TRANSCRIPT_UNREADABLE = "transcript-unreadable"
REASON_TRANSCRIPT_ACTIVE = "transcript-active"
REASON_JOURNAL_NOT_LAUNCHED = "journal-not-launched"

# New (stale-launched-retry-recovery task0002): the opt-in evidence chain's
# six additional reason codes (SC6).
REASON_TASK_ARTIFACTS_MISSING = "task-artifacts-missing"
REASON_AGENT_IDENTITY_UNPROVEN = "agent-identity-unproven"
REASON_AGENT_TERMINATION_UNPROVEN = "agent-termination-unproven"
REASON_AGENT_STILL_LIVE = "agent-still-live"
REASON_STOP_RESULT_UNPROVEN = "stop-result-unproven"
REASON_LAUNCH_CHANGED = "launch-changed"

TERMINAL_JOURNAL_EVENTS = ("merged", "failed")

DEFAULT_JOURNAL_HELPER_NAME = "journal-append-failed.py"
ORPHANED_REASON = "orphaned"
STALE_LAUNCHED_REASON = "stale-launched"

# D7 -- the agent index entry's own `at` must not be earlier than the last
# `launched` journal event's `at` for the task by more than this tolerance.
# 2 seconds: the two writes come from two separate PreToolUse hook
# invocations, each stamping whole seconds from the local clock in an order
# the harness does not fix, so the genuine pair can straddle a second
# boundary in either direction. A genuinely stale entry is separated from
# the newest launch by a whole implementer run, not by seconds.
AGENT_ENTRY_BINDING_TOLERANCE = timedelta(seconds=2)

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


def _earliest_entry_timestamp(lines):
    """The EARLIEST parseable timestamp among ALL of the transcript's
    entries -- not the positionally-first line's. The same line-level
    tolerance the newest-activity reader (D3) applies is used here: blank
    lines, lines that are not valid JSON, lines that are not JSON objects,
    and entries whose `timestamp` is absent or unparsable are SKIPPED
    rather than aborting resolution. None only when NO entry in the file
    yields a parseable timestamp at all (D2, revised: real transcripts open
    with a record carrying no `timestamp`, so reading only the first line
    resolved nothing in practice -- MANUAL-D2)."""
    earliest = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        dt = parse_timestamp(obj.get("timestamp"))
        if dt is None:
            continue
        if earliest is None or dt < earliest:
            earliest = dt
    return earliest


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
        # First transcript containing the token: commit to it -- a later
        # failure never falls through to an older transcript. Its stem is
        # the current session identity; its start is the EARLIEST parseable
        # timestamp among its entries (D2, revised), never the positionally
        # first line's.
        earliest_ts = _earliest_entry_timestamp(lines)
        if earliest_ts is None:
            return None
        stem = os.path.splitext(os.path.basename(path))[0]
        return stem, earliest_ts
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
# D7 -- binding the agent index entry to the launch under recovery.
# ---------------------------------------------------------------------------


def find_last_launched_at(journal_path, task_id):
    """Scan the journal for the task's `launched` events (by file order) and
    return `(found, at_value)`: `found` is True iff at least one `launched`
    event was recorded for the task at all -- D7's binding step applies only
    then. `at_value` is the LAST such event's raw `at` field, unparsed and
    possibly absent (None) -- callers parse it themselves so a missing or
    unparsable value is uniformly a binding failure, not a pass. Malformed
    lines are skipped; an absent/unreadable file reports `found=False`,
    which correctly leaves the binding step inapplicable (the pre-existing
    journal pre-check handles that case)."""
    found = False
    at_value = None
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
                if entry.get("event") == "launched":
                    found = True
                    at_value = entry.get("at")
    except OSError:
        return False, None
    return found, at_value


def agent_entry_is_bound(entry_at, last_launched_at):
    """D7: True when the agent index entry's own `at` (`entry_at`) binds to
    the last `launched` journal event's `at` for the task
    (`last_launched_at`) -- both parse as timestamps, are comparable, and
    `entry_at` is not earlier than `last_launched_at` by more than
    `AGENT_ENTRY_BINDING_TOLERANCE`. Data that cannot be compared at all --
    either side missing, non-string or unparsable, or an aware/naive
    combination that cannot be compared -- is a binding FAILURE (False),
    never a pass (Conventions' error-handling policy: doubt never produces
    a write)."""
    entry_dt = parse_timestamp(entry_at)
    last_dt = parse_timestamp(last_launched_at)
    if entry_dt is None or last_dt is None:
        return False
    try:
        return (last_dt - entry_dt) <= AGENT_ENTRY_BINDING_TOLERANCE
    except TypeError:
        # Incomparable aware/naive datetimes: cannot prove the entry binds
        # from this evidence -- fail safe rather than raise.
        return False


# ---------------------------------------------------------------------------
# Agent-identity binding rule (IMPLEMENTATION.md, new chain step 4).
# ---------------------------------------------------------------------------


def resolve_bound_stop_target(entry, task_worktree, stop_target):
    """The stop target's identity is uniquely bound when ALL hold against
    the given (already D7-bound) agent index entry: its candidate list
    (`agent_ids`) names exactly one distinct value; its recorded
    `worktree_path` equals `task_worktree`; and `stop_target` equals that
    one candidate. Returns the bound identity string on success, else None
    (-> agent-identity-unproven) -- no candidate, two or more distinct
    candidates, a worktree mismatch, a stop-target mismatch, and an absent
    or non-string `stop_target` are all a binding failure.

    Only `agent_ids` is ever read as a candidate source: no OTHER entry
    field is consulted as a fallback identity, even when it happens to be
    byte-equal to a genuine candidate."""
    candidates = entry.get("agent_ids")
    if not isinstance(candidates, list) or not candidates:
        return None
    distinct = set(candidates)
    if len(distinct) != 1:
        return None
    (only_candidate,) = distinct
    if entry.get("worktree_path") != task_worktree:
        return None
    if not isinstance(stop_target, str) or stop_target != only_candidate:
        return None
    return only_candidate


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


def invoke_journal_helper(helper_path, journal_path, task_id, reason=ORPHANED_REASON, launch_at=None):
    """Invoke the journal helper exactly once (SC2' contract:
    `--journal PATH --task TASKID --reason REASON`, plus `--launch-at VALUE`
    when `launch_at` is supplied -- D-E: the reason and the launch-identity
    argument are parameters of the invocation, chosen by the caller of this
    function, never inferred here) and propagate its outcome. Returns
    (outcome_dict, exit_code); outcome_dict is None when the helper failed
    (non-zero exit, unparsable stdout, or an unrecognized outcome value) --
    a helper failure is NEVER reported as `recovered`. The helper's
    `launch_changed` outcome (D-D) maps to `residual`/`launch-changed`."""
    cmd = [
        sys.executable,
        helper_path,
        "--journal",
        journal_path,
        "--task",
        task_id,
        "--reason",
        reason,
    ]
    if launch_at is not None:
        cmd += ["--launch-at", launch_at]
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
    if helper_outcome == "launch_changed":
        return _residual(task_id, REASON_LAUNCH_CHANGED)

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
# Opt-in evidence chain (FR3, D-A through D-F): self-contained and
# independently callable, so its own step order can be proven directly
# (AC-6) as well as via decide()'s same-session dispatch below.
# ---------------------------------------------------------------------------


def evaluate_stale_launched_chain(
    task_id,
    journal_path,
    agents_index_path,
    current_session_id=None,
    current_session_start=None,
    marker=None,
    transcripts_dir=None,
    worktree_present=None,
    branch_present=None,
    task_worktree=None,
    stop_target=None,
    launch_termination=None,
    stop_result=None,
    stop_result_target=None,
    journal_helper=None,
):
    """FR3's seven-step evidence chain. Every step's failure ends the run as
    `residual` with its SC6 reason code and reads/opens nothing further.
    Reuses the legacy pipeline's own functions for the agent-index,
    binding, session-identity and current-session sub-checks rather than
    restating them; adds the artifact/journal precheck (step 1), the
    agent-identity binding rule (step 4), the termination and stop-result
    checks (steps 5-6), and the reason/launch-identity-parameterised helper
    invocation (step 7)."""
    resolved_transcripts_dir = (
        transcripts_dir if transcripts_dir is not None else default_transcripts_dir()
    )

    # 1. Artifacts, then journal state -- decided before any agent index
    # read, any path assembly and any file open (AC-6). Each observation
    # must be exactly "yes" or exactly "no" (case-sensitive); an absent or
    # unrecognized observation on either flag ends the chain here with the
    # narrowed `task-artifacts-missing` meaning. A recognized pair (any of
    # the four yes/no combinations) is kept as evidence and the chain
    # proceeds regardless of value -- "no" never ends the chain by itself.
    if worktree_present not in ("yes", "no") or branch_present not in ("yes", "no"):
        return _residual(task_id, REASON_TASK_ARTIFACTS_MISSING)
    final_event = replay_final_event(journal_path, task_id)
    if final_event in TERMINAL_JOURNAL_EVENTS:
        return _noop_terminal(task_id)
    if final_event != "launched":
        return _residual(task_id, REASON_JOURNAL_NOT_LAUNCHED)

    # 2. Agent index entry, D7-bound (reused, not restated).
    entry = find_agent_entry(agents_index_path, task_id)
    if entry is None:
        return _residual(task_id, REASON_NO_AGENT_ENTRY)
    has_launched_event, last_launched_at = find_last_launched_at(journal_path, task_id)
    if not (has_launched_event and agent_entry_is_bound(entry.get("at"), last_launched_at)):
        return _residual(task_id, REASON_STALE_AGENT_ENTRY)

    # 3. Session identity present, valid, and the current session resolves.
    recorded_session_id = entry.get("session_id")
    if not isinstance(recorded_session_id, str) or recorded_session_id == "":
        return _residual(task_id, REASON_NO_SESSION_ID)
    if not is_valid_session_id(recorded_session_id):
        return _residual(task_id, REASON_INVALID_SESSION_ID)
    current = resolve_current_session(
        current_session_id, current_session_start, marker, resolved_transcripts_dir
    )
    if current is None:
        return _residual(task_id, REASON_CURRENT_SESSION_UNKNOWN)

    # 4. Bound stop target (agent-identity binding rule).
    bound_identity = resolve_bound_stop_target(entry, task_worktree, stop_target)
    if bound_identity is None:
        return _residual(task_id, REASON_AGENT_IDENTITY_UNPROVEN)

    # 5. Harness termination of THIS launch -- no elapsed-time proxy.
    if launch_termination == "running":
        return _residual(task_id, REASON_AGENT_STILL_LIVE)
    if launch_termination != "terminated":
        return _residual(task_id, REASON_AGENT_TERMINATION_UNPROVEN)

    # 6. Stop result for the SAME bound target.
    if stop_result != "not-running" or stop_result_target != bound_identity:
        return _residual(task_id, REASON_STOP_RESULT_UNPROVEN)

    # 7. In-lock launch identity: invoke the helper exactly once.
    helper_path = journal_helper if journal_helper else default_journal_helper_path()
    return invoke_journal_helper(
        helper_path,
        journal_path,
        task_id,
        reason=STALE_LAUNCHED_REASON,
        launch_at=last_launched_at,
    )


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
    worktree_present=None,
    branch_present=None,
    task_worktree=None,
    stop_target=None,
    launch_termination=None,
    stop_result=None,
    stop_result_target=None,
):
    """Run the evidence pipeline in fixed order for one task, then (on proof)
    the journal pre-check and helper invocation. Returns
    (outcome_dict_or_None, exit_code); outcome_dict is None only when
    exit_code is non-zero (usage/internal error -- never accompanied by a
    journal write).

    The seven trailing parameters are the new chain's evidence inputs
    (D-A): supplying at least one of them opts into
    `evaluate_stale_launched_chain` from the same-session branch below;
    supplying none reproduces today's behaviour exactly (FR5/NFR5)."""
    evidence_supplied = any(
        value is not None
        for value in (
            worktree_present,
            branch_present,
            task_worktree,
            stop_target,
            launch_termination,
            stop_result,
            stop_result_target,
        )
    )
    using_default_dir = transcripts_dir is None
    resolved_transcripts_dir = transcripts_dir if transcripts_dir is not None else default_transcripts_dir()

    # 1. Agent index entry.
    entry = find_agent_entry(agents_index_path, task_id)
    if entry is None:
        return _residual(task_id, REASON_NO_AGENT_ENTRY)

    # 2. Bind the entry to the launch under recovery (D7). Runs before the
    # entry's session identity is read, so an entry that is not evidence
    # about THIS launch never has its contents trusted. Skipped entirely
    # when the journal records no `launched` event for the task at all --
    # the journal pre-check below already ends that run as
    # `journal-not-launched` or `noop_terminal`.
    has_launched_event, last_launched_at = find_last_launched_at(journal_path, task_id)
    if has_launched_event and not agent_entry_is_bound(entry.get("at"), last_launched_at):
        return _residual(task_id, REASON_STALE_AGENT_ENTRY)

    # 3. Session identity present.
    recorded_session_id = entry.get("session_id")
    if not isinstance(recorded_session_id, str) or recorded_session_id == "":
        return _residual(task_id, REASON_NO_SESSION_ID)

    # 4. SC5 format validation -- before any path is assembled.
    if not is_valid_session_id(recorded_session_id):
        return _residual(task_id, REASON_INVALID_SESSION_ID)

    # 5. Current session resolution (D2).
    current = resolve_current_session(
        current_session_id, current_session_start, marker, resolved_transcripts_dir
    )
    if current is None:
        return _residual(task_id, REASON_CURRENT_SESSION_UNKNOWN)
    current_id, current_start = current

    # 6. Recorded identity differs from current -- OR, when the caller has
    # supplied at least one of the new evidence inputs, the opt-in chain
    # (D-A). This dispatch is placed HERE, on the same-session branch
    # itself, so the new chain structurally never runs for a task launched
    # by a different session (Out of Scope: do not lift it to an earlier
    # point in the pipeline).
    if recorded_session_id == current_id:
        if evidence_supplied:
            return evaluate_stale_launched_chain(
                task_id=task_id,
                journal_path=journal_path,
                agents_index_path=agents_index_path,
                current_session_id=current_session_id,
                current_session_start=current_session_start,
                marker=marker,
                transcripts_dir=resolved_transcripts_dir,
                worktree_present=worktree_present,
                branch_present=branch_present,
                task_worktree=task_worktree,
                stop_target=stop_target,
                launch_termination=launch_termination,
                stop_result=stop_result,
                stop_result_target=stop_result_target,
                journal_helper=journal_helper,
            )
        return _residual(task_id, REASON_SAME_SESSION)

    # 7. Transcripts directory resolves and exists; path containment.
    if not os.path.isdir(resolved_transcripts_dir):
        return _residual(task_id, REASON_TRANSCRIPTS_DIR_MISSING)

    transcript_path = resolve_transcript_path(
        resolved_transcripts_dir, recorded_session_id, using_default_dir
    )
    if transcript_path is None:
        return _residual(task_id, REASON_TRANSCRIPT_UNREADABLE)

    # 8. At least one usable timestamp.
    newest_ts = newest_transcript_timestamp(transcript_path)
    if newest_ts is None:
        return _residual(task_id, REASON_TRANSCRIPT_UNREADABLE)

    # 9. Strictly older than the current session's start (D3).
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

    # On proof: invoke the journal helper exactly once (D-E: the legacy
    # chain always uses reason `orphaned` and no launch identity).
    helper_path = journal_helper if journal_helper else default_journal_helper_path()
    return invoke_journal_helper(helper_path, journal_path, task_id, reason=ORPHANED_REASON)


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
    parser.add_argument(
        "--worktree-present",
        default=None,
        help="Opt-in evidence chain (step 1): an observation, exactly yes "
        "or no, of the task worktree",
    )
    parser.add_argument(
        "--branch-present",
        default=None,
        help="Opt-in evidence chain (step 1): an observation, exactly yes "
        "or no, of the task branch",
    )
    parser.add_argument(
        "--task-worktree",
        default=None,
        help="Opt-in evidence chain (step 4): the task's expected worktree "
        "path, supplied whether or not it exists",
    )
    parser.add_argument(
        "--stop-target",
        default=None,
        help="Opt-in evidence chain (step 4): the agent identity the I.2.b "
        "Recovery stop call was made against",
    )
    parser.add_argument(
        "--launch-termination",
        default=None,
        help="Opt-in evidence chain (step 5): terminated|running|"
        "launch-accepted|error|output-idle",
    )
    parser.add_argument(
        "--stop-result",
        default=None,
        help="Opt-in evidence chain (step 6): not-running|error",
    )
    parser.add_argument(
        "--stop-result-target",
        default=None,
        help="Opt-in evidence chain (step 6): which target the stop result "
        "is about",
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
        worktree_present=args.worktree_present,
        branch_present=args.branch_present,
        task_worktree=args.task_worktree,
        stop_target=args.stop_target,
        launch_termination=args.launch_termination,
        stop_result=args.stop_result,
        stop_result_target=args.stop_result_target,
    )
    if outcome is not None:
        print(json.dumps(outcome, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
