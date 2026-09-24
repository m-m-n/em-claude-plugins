#!/usr/bin/env python3
"""em-workflow SubagentStop failure net: journal `failed` recorder and
diagnostics log writer.

Fires on EVERY subagent stop. Its only job is to make a swallowed
implementer failure visible in the journal -- it never blocks the stop and
never decides what to do about a failure (that is the orchestrator's
protocol, prompted via the Stop hook's failed-task pass-through). See
feature-docs/subagentstop-failed-event/IMPLEMENTATION.md's SC1
(identification and outcome flow), SC2 (diagnostics log record) and SC3
(the unchanged `failed` journal line).

Identification order (SC1), stopping at the first step that finds a task:
  1. `agent_type`: `em-workflow:implementer` or `implementer` continues to
     the next step; any other non-empty string ends the flow with outcome
     `not-implementer-type`. A missing, empty or non-string value also
     continues.
  2. An inline prompt field (`prompt`, `initial_prompt`, `agent_prompt`,
     checked in that order) that contains a `# Task assignment` header line
     -- source `inline`. A field without a header does not stop the search.
  3. Failing that, the first transcript (`agent_transcript_path`) user-role
     message that contains the header -- source `transcript`. A missing
     path, an unreadable file and malformed lines yield no text; none of
     them is an error.
  4. Failing that, the agent-index fallback: the payload's `agent_id`,
     trimmed, resolved against the nearest `agents.jsonl` files under the
     worktrees root found by walking up from `cwd`, using the same
     resolution rules as `queue_taskstop_net.py`'s `find_task_identity`
     (candidate-list cap, feature-directory containment, ambiguity and
     staleness refusal) -- source `agent-index`. Nothing resolved: outcome
     `index-unresolved`. No usable `agent_id` either: outcome
     `no-assignment-block` when some prompt text was seen at all (an inline
     field or a transcript user message, header or not), otherwise outcome
     `no-prompt-text`.

Only the text AFTER the first header line is parsed for `task_id:` and
`worktree_path:` -- `extract_task_assignment` below is a copy of
`queue_launch_guard.py`'s function of the same name, with byte-identical
header/task-id-line/worktree-path-line patterns and the same return
contract. The resulting `task_id` / `worktree_path` (or the agent-index
fallback's) are then validated the same way regardless of source; either
invalid ends the flow with outcome `invalid-identity` (the source already
determined is kept).

The journal directory is the parent of the normalized `worktree_path`; when
it does not exist the flow ends with outcome `journal-dir-missing` and
nothing is created. Otherwise the replay -> decide -> append sequence runs
as ONE critical section under an exclusive flock on the journal file
(atomic compare-and-append): the whole file is replayed through the locked
descriptor from the start, skipping malformed lines; a task whose last
event is already `merged` or `failed` gets nothing appended (outcome
`already-terminal`); otherwise exactly one `failed` line is appended and
flushed to disk (outcome `appended`). Any unexpected exception anywhere in
this flow becomes outcome `error` (the exception's class name is recorded),
keeping whatever source/task id had already been determined -- never a
crash or a hang.

Every invocation, in addition, appends exactly one line to the diagnostics
log `subagent-stop-diagnostics.jsonl`, directly inside the worktrees root
(the `.claude/worktrees/em-workflow` directory itself) resolved by walking
up from `cwd`, falling back to walking up from the validated
`worktree_path` when `cwd` yields no root. This log is NOT a journal and
not a journal writer: nothing in the workflow reads it, it carries no
task-status meaning, it is never committed and it is never rotated. A
missing diagnostics line alone does not distinguish a hook that did not run
at all from one that ran but could not write the log -- the write is
skipped silently on any failure (no root found, a symlink or a directory at
the log path, or anything else).

The outcome code set is closed and every invocation selects exactly one:
  `not-implementer-type`, `no-prompt-text`, `no-assignment-block`,
  `invalid-identity`, `index-unresolved`, `journal-dir-missing`,
  `already-terminal`, `appended`, `error`.

The identification `source` recorded in the diagnostics line is one of
`inline`, `transcript`, `agent-index` or `none`.

Fail-open convention: this hook ALWAYS exits 0 (never blocks the stop) --
enforced by a top-level catch-all around the identification/journal flow
and a separate catch-all around the diagnostics write, both in `main()`.
"""

import fcntl
import glob
import json
import os
import re
import sys
from datetime import datetime

IMPLEMENTER_AGENT_TYPE = "em-workflow:implementer"
IMPLEMENTER_AGENT_TYPE_SHORT = "implementer"
FAILED_REASON = "implementer stopped without a merged event"

DIAGNOSTICS_FILE_NAME = "subagent-stop-diagnostics.jsonl"

# Byte-identical to queue_launch_guard.py's ASSIGNMENT_HEADER_RE (and
# queue_agent_index.py's ASSIGNMENT_HEADER_RE) -- task0006 F-4: these had
# drifted (this file previously tolerated 0+ spaces after `#`), so a header
# spelling the launch guard would reject as "not an implementer launch"
# could still be accepted here as a valid task assignment.
TASK_ASSIGNMENT_HEADER_RE = re.compile(r"(?m)^# Task assignment\s*$")
# Byte-identical to queue_launch_guard.py's TASK_ID_LINE_RE /
# WORKTREE_PATH_LINE_RE -- extract_task_assignment below is a copy of that
# hook's function of the same name (subagentstop-failed-event task0001,
# FR4).
TASK_ID_LINE_RE = re.compile(r"(?m)^task_id:\s*(\S+)\s*$")
WORKTREE_PATH_LINE_RE = re.compile(r"(?m)^worktree_path:\s*(\S.*?)\s*$")
TASK_ID_RE = re.compile(r"^task[0-9]+$")

# Fields that might carry the initial prompt text directly (checked before
# falling back to reading agent_transcript_path from disk).
INLINE_PROMPT_FIELDS = ("prompt", "initial_prompt", "agent_prompt")

# Agent-index resolution rules (FR3), same as queue_taskstop_net.py's
# find_task_identity: an agents.jsonl entry whose agent_ids candidate list
# is longer than the legitimate writer (queue_agent_index.py) could ever
# produce is ignored wholesale.
MAX_AGENT_IDS_LEN = 5
AGENT_ID_KEYS = ("agent_id", "agentId")
ENTRY_TASK_ID_KEY = "task"


def valid_task_id(task_id):
    return isinstance(task_id, str) and bool(TASK_ID_RE.match(task_id))


def valid_worktree_path(path):
    if not isinstance(path, str) or not path:
        return False
    if not os.path.isabs(path):
        return False
    if ".." in path.split("/"):
        return False
    return True


def now_rfc3339():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def extract_user_text(entry):
    """Pull the text content out of a transcript-line entry if it represents
    a user-role message; None otherwise. Tolerates both the string-content
    and content-block-list transcript shapes."""
    if not isinstance(entry, dict):
        return None
    message = entry.get("message")
    if not isinstance(message, dict):
        message = entry
    if message.get("role") != "user":
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if parts:
            return "\n".join(parts)
    return None


def _first_transcript_user_text_with_header(transcript_path):
    """Scan a JSONL transcript file line by line for the first user-role
    message whose text contains the assignment header line; stops at the
    first match. Returns (text_or_None, any_user_message_seen) -- a missing
    path, an unreadable file and malformed lines all yield (None, False)
    without error (fail-open)."""
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return None, False
    any_seen = False
    try:
        path = os.path.expanduser(transcript_path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                text = extract_user_text(entry)
                if text is None:
                    continue
                any_seen = True
                if TASK_ASSIGNMENT_HEADER_RE.search(text):
                    return text, any_seen
    except OSError:
        return None, any_seen
    return None, any_seen


def find_prompt_text_with_header(data):
    """Prompt-text finder (SC1 steps 3-4, FR2): returns (text, source,
    any_seen). `text` is the first inline field, else the first transcript
    user-role message, whose content contains the assignment header line;
    `source` is `inline`, `transcript` or `none` accordingly. `any_seen`
    reports whether ANY prompt text was found at all -- a non-empty inline
    field, or at least one transcript user-role message -- regardless of
    whether it carried a header; this is what separates outcome
    `no-assignment-block` from `no-prompt-text` when no header is ever
    found. An inline field without a header does not stop the search, and
    an inline field with a header takes precedence over the transcript."""
    any_seen = False
    for key in INLINE_PROMPT_FIELDS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            any_seen = True
            if TASK_ASSIGNMENT_HEADER_RE.search(value):
                return value, "inline", True

    text, transcript_any_seen = _first_transcript_user_text_with_header(
        data.get("agent_transcript_path")
    )
    if transcript_any_seen:
        any_seen = True
    if text is not None:
        return text, "transcript", any_seen

    return None, "none", any_seen


def extract_task_assignment(prompt):
    """Pull (task_id, worktree_path) out of a `# Task assignment` block.

    A copy of queue_launch_guard.py's function of the same name (FR4): the
    same header/task-id-line/worktree-path-line patterns, the same return
    contract. Returns (None, None) when the prompt carries no such block at
    all (the header must be present); an individual missing line yields
    None for that field only. Only text after the first header line is
    searched.
    """
    if not isinstance(prompt, str):
        return None, None
    header = TASK_ASSIGNMENT_HEADER_RE.search(prompt)
    if not header:
        return None, None
    tail = prompt[header.end():]
    task_id_match = TASK_ID_LINE_RE.search(tail)
    worktree_match = WORKTREE_PATH_LINE_RE.search(tail)
    task_id = task_id_match.group(1) if task_id_match else None
    worktree_path = worktree_match.group(1) if worktree_match else None
    return task_id, worktree_path


def find_worktrees_root(path):
    """Walk up from `path` (itself first, then each ancestor) to the
    nearest directory containing `.claude/worktrees/em-workflow`; return
    that directory's path, or None when none is found or `path` is not a
    usable absolute string. Used for both the agent-index search root
    (FR3) and the diagnostics root (SC2) -- the hook process's own working
    directory is never consulted."""
    if not isinstance(path, str) or not path or not os.path.isabs(path):
        return None
    current = os.path.normpath(path)
    while True:
        candidate = os.path.join(current, ".claude", "worktrees", "em-workflow")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _candidate_list_within_cap(entry):
    agent_ids = entry.get("agent_ids")
    if isinstance(agent_ids, list) and len(agent_ids) > MAX_AGENT_IDS_LEN:
        return False
    return True


def _entry_contained_in_feature(index_path, worktree_path):
    if not valid_worktree_path(worktree_path):
        return False
    feature_dir = os.path.normpath(os.path.dirname(index_path))
    journal_dir = os.path.normpath(os.path.dirname(os.path.normpath(worktree_path)))
    return journal_dir == feature_dir


def _entry_matches_identifier(entry, identifier):
    agent_ids = entry.get("agent_ids")
    if isinstance(agent_ids, list):
        return any(
            isinstance(value, str) and value and value == identifier
            for value in agent_ids
        )
    for key in AGENT_ID_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value and value == identifier:
            return True
    return False


def resolve_via_agent_index(identifier, cwd):
    """Agent-index fallback (FR3, SC1 step 5): the same resolution rules as
    queue_taskstop_net.py's find_task_identity, scoped to `identifier` =
    the payload's trimmed `agent_id`. Returns (task_id, worktree_path), or
    None when nothing resolved, the match was ambiguous across distinct
    (index file, task) pairs, or the match is stale (a later entry for the
    same pair exists)."""
    worktrees_root = find_worktrees_root(cwd)
    if worktrees_root is None:
        return None

    matches = []
    last_task_pos = {}
    pos = 0
    for feature_dir in sorted(glob.glob(os.path.join(worktrees_root, "*"))):
        if not os.path.isdir(feature_dir):
            continue
        index_path = os.path.join(feature_dir, "agents.jsonl")
        try:
            with open(index_path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if not _candidate_list_within_cap(entry):
                continue  # implausible candidate list: ignore wholesale
            worktree_path = entry.get("worktree_path")
            if not _entry_contained_in_feature(index_path, worktree_path):
                continue  # not contained in the feature dir it came from
            pos += 1
            task_id = entry.get(ENTRY_TASK_ID_KEY)
            if isinstance(task_id, str) and task_id:
                last_task_pos[(index_path, task_id)] = pos
            if not _entry_matches_identifier(entry, identifier):
                continue
            matches.append((index_path, task_id, worktree_path, pos))

    if not matches:
        return None

    distinct_pairs = {(index_path, task_id) for index_path, task_id, _, _ in matches}
    if len(distinct_pairs) > 1:
        return None  # ambiguous across distinct tasks: resolution failure

    index_path, task_id, worktree_path, match_pos = matches[-1]
    if isinstance(task_id, str) and task_id and last_task_pos.get((index_path, task_id)) != match_pos:
        return None  # a later launch of the same task exists: stale match
    return task_id, worktree_path


def open_journal_locked(path):
    """Open (creating if absent) the journal with an exclusive flock held
    (SC1 step 9 / FR5): read-write, create, append, no-follow, mode 0644.
    Caller unlocks and closes the returned fd on every path."""
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        os.close(fd)
        raise
    return fd


def last_event_for_task_fd(fd, task_id):
    """Replay the journal through an already-open fd, returning the LAST
    event value for task_id. None means no events for this task
    (unlaunched). Malformed lines are skipped, never raised."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    content = b"".join(chunks).decode("utf-8", errors="replace")

    last_event = None
    for line in content.splitlines():
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
    return last_event


def append_failed_fd(fd, task_id, reason):
    """Append the failed line through the locked fd (O_APPEND) and flush it
    to disk (SC1 step 9)."""
    entry = {"event": "failed", "task": task_id, "at": now_rfc3339(), "reason": reason}
    line = json.dumps(entry, ensure_ascii=False)
    os.write(fd, (line + "\n").encode("utf-8"))
    os.fsync(fd)


def replay_and_append(journal_path, task_id, reason):
    """The SC1 step 9 critical section: ONE exclusive-lock section that
    replays the whole journal through the same descriptor and appends at
    most one `failed` line. Returns `already-terminal` or `appended`."""
    fd = open_journal_locked(journal_path)
    try:
        last_event = last_event_for_task_fd(fd, task_id)
        if last_event in ("merged", "failed"):
            return "already-terminal"
        append_failed_fd(fd, task_id, reason)
        return "appended"
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class OutcomeRecord:
    """Accumulates SC1's identification state step by step, so that an
    `error` outcome (SC1 step 10) keeps whatever source/task id had already
    been determined before the failure. `worktree_path` is carried only for
    the SC2 diagnostics-root fallback and is never logged."""

    __slots__ = ("source", "task_id", "worktree_path", "outcome", "error_class")

    def __init__(self):
        self.source = "none"
        self.task_id = None
        self.worktree_path = None
        self.outcome = None
        self.error_class = None


def _run_flow(data, record):
    """SC1 steps 2-9: mutates `record` in place."""
    agent_type = data.get("agent_type")
    if isinstance(agent_type, str) and agent_type.strip():
        trimmed = agent_type.strip()
        if trimmed not in (IMPLEMENTER_AGENT_TYPE, IMPLEMENTER_AGENT_TYPE_SHORT):
            record.outcome = "not-implementer-type"
            return

    text, source, any_prompt_seen = find_prompt_text_with_header(data)
    record.source = source

    if text is not None:
        task_id, worktree_path = extract_task_assignment(text)
    else:
        agent_id = data.get("agent_id")
        if isinstance(agent_id, str) and agent_id.strip():
            resolved = resolve_via_agent_index(agent_id.strip(), data.get("cwd"))
            if resolved is None:
                record.outcome = "index-unresolved"
                return
            task_id, worktree_path = resolved
            record.source = "agent-index"
        else:
            record.outcome = "no-assignment-block" if any_prompt_seen else "no-prompt-text"
            return

    if not valid_task_id(task_id) or not valid_worktree_path(worktree_path):
        record.outcome = "invalid-identity"
        return
    record.task_id = task_id
    record.worktree_path = worktree_path

    journal_dir = os.path.dirname(os.path.normpath(worktree_path))
    if not os.path.isdir(journal_dir):
        record.outcome = "journal-dir-missing"
        return
    journal_path = os.path.join(journal_dir, "journal.jsonl")

    record.outcome = replay_and_append(journal_path, task_id, FAILED_REASON)


def hook_main(data):
    """Runs SC1 steps 2-9 and returns a fully populated OutcomeRecord. Any
    unexpected exception during those steps yields outcome `error` (SC1
    step 10), recording the exception's class name and keeping whatever
    source/task id had already been determined."""
    record = OutcomeRecord()
    try:
        _run_flow(data, record)
    except Exception as exc:
        record.outcome = "error"
        record.error_class = type(exc).__name__
    return record


def _string_field(data, key):
    value = data.get(key)
    return value if isinstance(value, str) else ""


def build_diagnostics_line(data, record):
    """One JSON line per invocation (SC2): the keys and presence rules of
    the diagnostics record."""
    entry = {
        "at": now_rfc3339(),
        "hook_event_name": _string_field(data, "hook_event_name"),
        "agent_id": _string_field(data, "agent_id"),
        "agent_type": _string_field(data, "agent_type"),
        "source": record.source,
    }
    if record.task_id is not None:
        entry["task_id"] = record.task_id
    entry["outcome"] = record.outcome
    if record.outcome == "error" and record.error_class:
        entry["error_class"] = record.error_class
    return json.dumps(entry, ensure_ascii=False)


def find_diagnostics_root(data, record):
    """SC2 root resolution: `cwd`, falling back to the validated
    `worktree_path` (only set when SC1 step 7 passed) when `cwd` yields no
    root. The hook process's own working directory is never consulted."""
    root = find_worktrees_root(data.get("cwd"))
    if root is not None:
        return root
    if record.worktree_path is not None:
        return find_worktrees_root(record.worktree_path)
    return None


def write_diagnostics(data, record):
    """Append exactly one diagnostics line (SC2), or nothing when no root
    is found or the write fails for any reason -- directories are never
    created, and a symlink or a directory at the log path is refused
    (O_NOFOLLOW / IsADirectoryError) by the caller's catch-all."""
    root = find_diagnostics_root(data, record)
    if root is None:
        return
    log_path = os.path.join(root, DIAGNOSTICS_FILE_NAME)
    line = build_diagnostics_line(data, record)
    flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(log_path, flags, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def main():
    # SC1 step 1: stdin not parsable JSON, or not a mapping -- end silently,
    # no journal write, no diagnostics line at all (there is no payload to
    # build one from).
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0

    # Broad catch-all by design (NFR1): this hook is a fail-open net, never
    # a blocking authority -- any unhandled state must still exit 0 rather
    # than leave the subagent stop hung. hook_main() already turns an
    # unexpected exception into outcome `error`; this outer guard is a last
    # resort in case OutcomeRecord construction itself somehow failed.
    try:
        record = hook_main(data)
    except Exception:
        return 0

    try:
        write_diagnostics(data, record)
    except Exception:
        pass  # SC2: any failure skips the line silently

    return 0


if __name__ == "__main__":
    sys.exit(main())
