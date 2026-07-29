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
     root for entries that match. Before matching, each entry is checked
     for plausibility and discarded wholesale (never matched, never
     tracked) if either check fails:
       - candidate-list cap: `agent_ids`, when present, must not exceed
         MAX_AGENT_IDS_LEN elements -- longer than the legitimate writer
         (queue_agent_index.py) could ever produce for one launch (round 1
         finding F-1's candidate-list cap).
       - containment: the entry's `worktree_path` must normalize to a
         direct child of the feature directory this SAME `agents.jsonl`
         lives in (the agents.jsonl/journal.jsonl same-directory contract).
         An entry failing this could otherwise redirect the journal append
         to any existing directory on disk (round 1 finding F-1, the
         residual high).
     A surviving entry matches if the recovered identifier equals any
     element of its `agent_ids` candidate list (queue_agent_index.py
     records every distinct identifier candidate seen in the launch's
     tool_response, not just one), falling back to the single
     representative-key match (`agent_id`/`agentId`) for older entries
     written before `agent_ids` existed.
     If the surviving matches span two or more distinct (agents.jsonl,
     task) pairs, the identifier is ambiguous -- resolution fails (no-op),
     never last-wins (round 1 finding F-2: a reused/shared identifier, e.g.
     a parent task or session ID, must never let one launch's stop mark a
     DIFFERENT task `failed`). Otherwise the LAST matching entry for that
     one pair (stable scan order) wins.
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

# Fallback keys for an agents.jsonl entry's representative harness agent
# identifier, used only when the entry lacks the `agent_ids` candidate-list
# field (older entries, written before that contract existed). `agent_id`
# is what queue_agent_index.py (task0001, the index's writer) actually
# stores; `agentId` is accepted defensively too, since IMPLEMENTATION.md's
# "Agent index contract" fixes the field's presence, not its exact name.
AGENT_ID_KEYS = ("agent_id", "agentId")

# queue_agent_index.py stores the em-workflow task identifier under the key
# `task` (not `task_id`) in each agents.jsonl entry.
ENTRY_TASK_ID_KEY = "task"

# queue_agent_index.py's STRUCTURED_ID_FIELDS lists 4 structured
# tool_response fields it can pull a candidate from, plus one more slot for
# its embedded-text fallback (EMBEDDED_ID_RE) -- a genuine `agent_ids` list
# therefore never exceeds 4 + 1 = 5 elements. An entry claiming more is not
# something the legitimate writer could have produced (round 1 finding F-1's
# candidate-list cap).
MAX_AGENT_IDS_LEN = 5

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


def candidate_list_within_cap(entry):
    """False iff `entry['agent_ids']` is a list longer than the legitimate
    writer (queue_agent_index.py) could ever produce for one launch
    (MAX_AGENT_IDS_LEN). An entry failing this is ignored wholesale by the
    caller -- never matched, never tracked for staleness (round 1 finding
    F-1's candidate-list cap; entries without a list-shaped `agent_ids`
    pass through unaffected, since AGENT_ID_KEYS fallback matching does not
    consult this field's length at all)."""
    agent_ids = entry.get("agent_ids")
    if isinstance(agent_ids, list) and len(agent_ids) > MAX_AGENT_IDS_LEN:
        return False
    return True


def entry_contained_in_feature(index_path, worktree_path):
    """True iff `worktree_path` normalizes to a direct child of the feature
    directory that owns `index_path` (its agents.jsonl) -- the
    agents.jsonl/journal.jsonl same-directory contract (Agent index
    contract, IMPLEMENTATION.md). An entry failing this check could
    otherwise redirect a journal append to any existing directory on disk
    and must never be trusted, matching or not (round 1 finding F-1, the
    residual high)."""
    if not valid_worktree_path(worktree_path):
        return False
    feature_dir = os.path.normpath(os.path.dirname(index_path))
    journal_dir = os.path.normpath(os.path.dirname(os.path.normpath(worktree_path)))
    return journal_dir == feature_dir


def entry_matches_identifier(entry, identifier):
    """True iff `identifier` matches this agents.jsonl entry.

    queue_agent_index.py (the index's writer) stores, alongside the
    representative `agent_id`, a new `agent_ids` field: a list of every
    distinct identifier candidate recovered from the launch's
    tool_response, in discovery order (`agent_id` always equals
    `agent_ids[0]`). When `agent_ids` is present as a list, `identifier`
    matches if it equals ANY string element of that list (non-string
    elements and empty strings are ignored). Older entries written before
    this contract change lack `agent_ids` entirely, so this falls back to
    the single representative-key match (AGENT_ID_KEYS) in that case."""
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


def find_task_identity(worktrees_root, identifier):
    """Scan every feature's agents.jsonl under worktrees_root for entries
    that match `identifier` (see entry_matches_identifier: any element of
    the entry's `agent_ids` candidate list, or its representative key as a
    fallback for older entries); return the (task_id, worktree_path) of
    the resolved entry, or None. Malformed lines/files are skipped, never
    raised.

    Two plausibility checks run BEFORE matching, per entry, and an entry
    failing either is ignored wholesale -- it is never matched and never
    counted toward staleness tracking, exactly as if the line were absent:
      - candidate_list_within_cap: an implausibly long `agent_ids` (round 1
        finding F-1's cap).
      - entry_contained_in_feature: a `worktree_path` that does not
        normalize to a child of the feature directory this agents.jsonl
        lives in (round 1 finding F-1, the residual high).

    Ambiguity refusal (round 1 finding F-2): if the surviving matches span
    two or more distinct (agents.jsonl path, task_id) pairs, `identifier`
    is ambiguous across genuinely different tasks -- resolution fails
    (None), never last-wins. A reused/shared identifier (e.g. a parent
    task/session ID) must never let one launch's stop mark a DIFFERENT
    task `failed`.

    Staleness (unchanged from before F-1/F-2): agents.jsonl is
    append-only, so a re-launched task gets a brand-new entry (new agent
    identifier) while the old identifier's entry stays put. Once a single
    (agents.jsonl, task_id) pair is resolved, the LAST matching entry for
    that pair (stable scan order) is used only if no later entry for that
    SAME pair (task_id is only unique per feature, not globally) exists
    under a different identifier; otherwise the match is stale -- return
    None rather than attribute a stop to a launch already superseded."""
    matches = []  # [(index_path, task_id, worktree_path, pos), ...]
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
            if not candidate_list_within_cap(entry):
                continue  # implausible candidate list: ignore wholesale
            worktree_path = entry.get("worktree_path")
            if not entry_contained_in_feature(index_path, worktree_path):
                continue  # not contained in the feature dir it came from
            pos += 1
            task_id = entry.get(ENTRY_TASK_ID_KEY)
            if isinstance(task_id, str) and task_id:
                last_task_pos[(index_path, task_id)] = pos
            if not entry_matches_identifier(entry, identifier):
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
