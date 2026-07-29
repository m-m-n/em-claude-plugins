#!/usr/bin/env python3
"""em-workflow TaskStop journal `failed` recorder.

Fires on the POST-invocation event of the harness's `TaskStop` tool call --
the tool that stops a running background task, agent-team teammate, or
background subagent. Its only job is to make a deliberate stop of an
em-workflow implementer visible in the journal, exactly once. It never
blocks the tool call, never decides what happens next, and never touches
`workflow.yaml` (feature-docs/taskstop-journal-failed-event/IMPLEMENTATION.md
and tasks/task0002.md).

Complements (does NOT replace) `queue_failure_net.py`'s `SubagentStop` net:
a `TaskStop`-initiated stop of a subagent does not reliably deliver a usable
`SubagentStop` event (IMPLEMENTATION.md D1's empirical investigation), so
this hook is the recorder for a deliberate `TaskStop` stop. Both writers
replay the journal before appending (D4), so if a future harness version
ever delivers both events for the same stop, exactly one `failed` line
still results.

Behavior on each PostToolUse event for the `TaskStop` tool (stdin = the
event JSON):
  1. Recover the harness agent identifier: the tool input's `task_id` field
     (TaskStop's own parameter, naming the background task/agent it
     stopped) when present, else the corresponding field of `tool_response`
     (IMPLEMENTATION.md D3 payload-shape tolerance).
  2. Locate the search root by walking up from the hook input's `cwd` to
     the nearest ancestor containing `.claude/worktrees/em-workflow`
     (Agent index contract's read discipline, IMPLEMENTATION.md).
  3. Scan every feature directory's `agents.jsonl` one level below that
     root for entries whose agent identifier matches; the LAST such entry
     (across the whole scan, in a stable directory/line order) wins.
  4. Validate the entry's task identifier / worktree path (same rules as
     `queue_launch_guard.py`'s Task-identity discovery contract).
  5. Derive the journal directory from the worktree path (Journal contract:
     dirname(normpath(worktree_path))). A missing directory -> no action,
     never created.
  6. Replay the journal for that task id and, unless its last event is
     already `merged` or `failed`, append exactly one `failed` event with a
     reason string distinct from `queue_failure_net.py`'s. Replay and
     append happen inside ONE exclusive-flock critical section over the
     journal file (atomic compare-and-append, mirroring
     `queue_launch_guard.py`), so a concurrent writer cannot slip a
     terminal event in between.

Every abnormal condition (malformed stdin, a different tool, an
unresolvable identifier, no matching index entry, invalid index values, a
missing journal directory, an unreadable/unwritable journal) results in a
silent exit 0 with no journal write -- this hook is a fail-open net, not an
authority, exactly like the other three queue hooks. `main()` carries a
top-level catch-all so no exception can ever escape and block the stop.
"""

import fcntl
import glob
import json
import os
import re
import sys
from datetime import datetime

STOP_TOOL_NAME = "TaskStop"

# TaskStop's own input parameter naming the background task/agent to stop
# (harness convention: `TaskStop(task_id="<id>")`); the same key is checked
# on tool_response as the fallback location (IMPLEMENTATION.md D3).
HARNESS_ID_FIELD = "task_id"

# The agent index entry's key for the harness agent identifier. `agent_id`
# is what queue_agent_index.py (task0001, the index's writer) actually
# stores; `agentId` is accepted defensively too, since IMPLEMENTATION.md's
# "Agent index contract" fixes the field's presence, not its exact name.
AGENT_ID_KEYS = ("agent_id", "agentId")

# queue_agent_index.py stores the em-workflow task identifier under the key
# `task` (not `task_id`) in each agents.jsonl entry.
ENTRY_TASK_ID_KEY = "task"

TASK_ID_RE = re.compile(r"^task[0-9]+$")

FAILED_REASON = (
    "implementer stopped via a TaskStop tool call (deliberate stop, not a "
    "natural completion)"
)


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


def extract_agent_identifier(data):
    """The stop tool input's task-identifier field, falling back to the
    corresponding field of the tool result (IMPLEMENTATION.md D3)."""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        value = tool_input.get(HARNESS_ID_FIELD)
        if isinstance(value, str) and value.strip():
            return value.strip()
    tool_response = data.get("tool_response")
    if isinstance(tool_response, dict):
        value = tool_response.get(HARNESS_ID_FIELD)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def find_worktrees_root(cwd):
    """Walk up from cwd to the nearest ancestor (self included) containing
    `.claude/worktrees/em-workflow`; return that directory's path, or None
    if the walk reaches the filesystem root without finding one."""
    if not isinstance(cwd, str) or not cwd:
        return None
    current = os.path.abspath(cwd)
    while True:
        candidate = os.path.join(current, ".claude", "worktrees", "em-workflow")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def entry_agent_identifier(entry):
    for key in AGENT_ID_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def find_task_identity(worktrees_root, identifier):
    """Scan every feature's agents.jsonl under worktrees_root for entries
    whose agent identifier matches `identifier`; return the (task_id,
    worktree_path) of the LAST such entry (stable directory then line
    order), or None. Malformed lines/files are skipped, never raised."""
    match = None
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
            if entry_agent_identifier(entry) != identifier:
                continue
            match = (entry.get(ENTRY_TASK_ID_KEY), entry.get("worktree_path"))
    return match


def open_journal_locked(path):
    """Open (creating if absent) the journal with an exclusive flock held.

    O_NOFOLLOW: a symlink planted at the journal path must never redirect
    the append elsewhere (defense in depth, same as the other queue hooks).
    Caller unlocks and closes the returned fd.
    """
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, "O_NOFOLLOW", 0)
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
    """Append the failed line through the locked fd (O_APPEND)."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = {"event": "failed", "task": task_id, "at": now, "reason": reason}
    line = json.dumps(entry, ensure_ascii=False)
    os.write(fd, (line + "\n").encode("utf-8"))
    os.fsync(fd)


def hook_main(data):
    if not isinstance(data, dict) or data.get("tool_name") != STOP_TOOL_NAME:
        return

    identifier = extract_agent_identifier(data)
    if identifier is None:
        return

    worktrees_root = find_worktrees_root(data.get("cwd"))
    if worktrees_root is None:
        return

    identity = find_task_identity(worktrees_root, identifier)
    if identity is None:
        return
    task_id, worktree_path = identity
    if not valid_task_id(task_id) or not valid_worktree_path(worktree_path):
        return

    # Same derivation as queue_launch_guard.journal_path_for /
    # queue_failure_net.hook_main (Journal contract):
    # dirname(normpath(worktree_path)).
    journal_dir = os.path.dirname(os.path.normpath(worktree_path))
    if not os.path.isdir(journal_dir):
        return  # absent journal directory: fail-open, never fabricate state
    journal_path = os.path.join(journal_dir, "journal.jsonl")

    try:
        fd = open_journal_locked(journal_path)
    except OSError:
        return  # uncreatable/unopenable journal location: fail-open
    try:
        # Atomic critical section: replay and append happen under the SAME
        # flock, so a concurrent writer cannot slip a terminal event in
        # between the check and the write.
        last_event = last_event_for_task_fd(fd, task_id)
        if last_event in ("merged", "failed"):
            return
        append_failed_fd(fd, task_id, FAILED_REASON)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main():
    # Broad catch-all by design: this hook is a fail-open net, never a
    # blocking authority -- any unhandled state must still exit 0 rather
    # than leave the TaskStop call (or the session) hung.
    try:
        data = json.load(sys.stdin)
        hook_main(data)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
