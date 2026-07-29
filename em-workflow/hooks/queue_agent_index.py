#!/usr/bin/env python3
"""em-workflow queue agent index writer: PostToolUse hook on subagent-launch
calls.

Fires after a `Task()` / `Agent()` launch call completes. The subagent-launch
tool is named `Agent` in current Claude Code versions and `Task` in older
ones -- both names are matched (hooks.json registers `Task|Agent`), exactly
as `queue_launch_guard.py` documents: matching only one silently disables
this writer on the other.

Its only job is to record, in the feature's agent index (`agents.jsonl`,
sibling of `journal.jsonl`), the mapping from the harness's own agent
identifier to the em-workflow task it just launched, so that a later
`TaskStop` can be resolved back to a task and its journal (Agent index
contract, IMPLEMENTATION.md). It never writes `journal.jsonl`, never decides
anything about task state, and never blocks the tool call -- it is
diagnostic plumbing only (IMPLEMENTATION.md, Layer Structure).

Behavior on each PostToolUse event (stdin = PostToolUse JSON) for the `Task`
or `Agent` tool:
  1. Identify the launch: `tool_input.subagent_type`, when present and
     non-empty, is authoritative (`em-workflow:implementer` or nothing
     happens); otherwise fall back to the presence of a valid
     `# Task assignment` block in `tool_input.prompt` (Task-identity
     discovery contract -- identical acceptance rule to
     `queue_launch_guard.py`'s existing implementation).
  2. Extract and validate `task_id` / `worktree_path` from that block.
     Invalid values -> no action.
  3. Extract the harness agent identifier from `tool_response`: a structured
     identifier field when the result is an object, otherwise an identifier
     embedded in the result's text. Failing to find one -> no action
     (IMPLEMENTATION.md D3 -- the live payload shape is unverified in this
     environment).
  4. Derive the journal directory: dirname(normpath(worktree_path)) (Journal-
     directory derivation, IMPLEMENTATION.md -- identical to the derivation
     already used by both existing queue hooks). If it does not exist -> no
     action; this hook NEVER creates it.
  5. Append one entry to `agents.jsonl` in that directory under an exclusive
     whole-file lock (Agent index contract): symlink-refusing open, `0o644`,
     created if absent.

Fail-open convention: this hook is a net, not an authority. ALWAYS exits 0,
enforced by a top-level catch-all in main(), mirroring
`queue_failure_net.py`'s stated rationale -- no unexpected condition here
(malformed stdin, an invalid identity, an unrecoverable identifier, an
unreadable/absent journal location) may ever turn into a hung or blocked
tool call.
"""

import fcntl
import json
import os
import re
import sys
from datetime import datetime

TASK_ID_RE = re.compile(r"^task[0-9]+$")
ASSIGNMENT_HEADER_RE = re.compile(r"^#\s*Task assignment\s*$", re.MULTILINE)
TASK_ID_LINE_RE = re.compile(r"^task_id:\s*(\S+)\s*$", re.MULTILINE)
# Same parser as queue_launch_guard.py / queue_failure_net.py (Task-identity
# discovery contract): the path may contain internal spaces -- capture the
# whole line remainder.
WORKTREE_PATH_LINE_RE = re.compile(r"^worktree_path:\s*(\S.*?)\s*$", re.MULTILINE)

IMPLEMENTER_SUBAGENT_TYPE = "em-workflow:implementer"

# The subagent-launch tool's name: `Agent` in current Claude Code versions,
# `Task` in older ones. Both are indexed (queue_launch_guard.py convention).
LAUNCH_TOOL_NAMES = ("Task", "Agent")

# Structured tool_response fields that might carry the harness's own agent
# identifier, checked in this order (IMPLEMENTATION.md D3 -- unverified
# payload shape; `agentId` is the field Claude Code's documented PostToolUse
# schema uses for a completed Agent-tool call, and is the spelling confirmed
# empirically). `taskId`/`task_id` are accepted too, symmetric with the
# TaskStop recorder's HARNESS_ID_FIELD = "task_id" (queue_taskstop_net.py),
# so that a payload using the harness's own "task_id" naming still joins.
# This widening is confined to structured fields; EMBEDDED_ID_RE below is
# deliberately NOT widened to task[_-]?id, since implementer prompts always
# contain a literal `task_id: task0001` line that would otherwise be
# misread as an agent identifier.
STRUCTURED_ID_FIELDS = ("agentId", "agent_id", "taskId", "task_id")

# Fallback: an identifier embedded in freeform result text, e.g.
# `agentId: a4d2c8f1e0b3a297` or `agent_id="a4d2c8f1e0b3a297"`.
EMBEDDED_ID_RE = re.compile(r"(?i)agent[_-]?id[\"':=\s]+([A-Za-z0-9_-]{4,})")


def extract_task_assignment(prompt):
    """Pull (task_id, worktree_path) out of a `# Task assignment` block.

    Same parser as queue_launch_guard.py (Task-identity discovery contract).
    Returns (None, None) when the prompt carries no such block at all (the
    block header must be present); individual missing lines yield None for
    that field only.
    """
    if not isinstance(prompt, str):
        return None, None
    header = ASSIGNMENT_HEADER_RE.search(prompt)
    if not header:
        return None, None
    tail = prompt[header.end():]
    task_id_match = TASK_ID_LINE_RE.search(tail)
    worktree_match = WORKTREE_PATH_LINE_RE.search(tail)
    task_id = task_id_match.group(1) if task_id_match else None
    worktree_path = worktree_match.group(1) if worktree_match else None
    return task_id, worktree_path


def is_implementer_launch(tool_input, task_id):
    """Task-identity discovery: subagent_type when provided, else the block.
    Identical acceptance rule to queue_launch_guard.py."""
    subagent_type = tool_input.get("subagent_type")
    if isinstance(subagent_type, str) and subagent_type:
        return subagent_type == IMPLEMENTER_SUBAGENT_TYPE
    return task_id is not None


def valid_task_id(task_id):
    return isinstance(task_id, str) and bool(TASK_ID_RE.match(task_id))


def valid_worktree_path(worktree_path):
    return (
        isinstance(worktree_path, str)
        and worktree_path.strip() != ""
        and os.path.isabs(worktree_path)
        and ".." not in worktree_path.split("/")
    )


def journal_dir_for(worktree_path):
    """Journal-directory derivation (IMPLEMENTATION.md Shared Components):
    the parent of the normalized worktree path -- identical to the
    derivation already used by both existing queue hooks."""
    return os.path.dirname(os.path.normpath(worktree_path))


def _text_from_content_blocks(content):
    if not isinstance(content, list):
        return None
    parts = [
        block.get("text")
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ]
    return "\n".join(parts) if parts else None


def extract_agent_identifier(tool_response):
    """Recover the harness's own agent identifier from a PostToolUse
    `tool_response` of unverified shape (IMPLEMENTATION.md D3):
      - a structured identifier field, when the result is an object;
      - otherwise, an identifier embedded in the result's text (either a
        top-level string result, or the joined text of a `content` block
        list).
    Returns None when nothing recoverable is found (fail-open, no action).
    Non-string structured values are never coerced -- only a genuine string
    field counts.
    """
    if isinstance(tool_response, dict):
        for field in STRUCTURED_ID_FIELDS:
            value = tool_response.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        text = _text_from_content_blocks(tool_response.get("content"))
        if text:
            match = EMBEDDED_ID_RE.search(text)
            if match:
                return match.group(1)
        return None

    if isinstance(tool_response, str) and tool_response.strip():
        match = EMBEDDED_ID_RE.search(tool_response)
        if match:
            return match.group(1)
        return None

    return None


def now_rfc3339():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_index_entry(journal_dir, agent_id, task_id, worktree_path):
    """Append one entry to `agents.jsonl` under an exclusive whole-file lock
    (Agent index contract, IMPLEMENTATION.md): symlink-refusing open,
    `0o644`, created if absent. The containing directory is NEVER created
    here -- the caller has already confirmed it exists."""
    path = os.path.join(journal_dir, "agents.jsonl")
    entry = {
        "agent_id": agent_id,
        "task": task_id,
        "worktree_path": worktree_path,
        "at": now_rfc3339(),
    }
    line = json.dumps(entry, ensure_ascii=False)
    # O_NOFOLLOW: a symlink planted at the index path must never redirect
    # the append elsewhere (defense in depth, same as the existing hooks).
    flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def hook_main(data):
    if not isinstance(data, dict) or data.get("tool_name") not in LAUNCH_TOOL_NAMES:
        return

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    task_id, worktree_path = extract_task_assignment(tool_input.get("prompt"))

    if not is_implementer_launch(tool_input, task_id):
        return  # not an em-workflow implementer launch: none of our concern

    if not valid_task_id(task_id) or not valid_worktree_path(worktree_path):
        return  # fail-open: invalid identity, discarded rather than repaired

    agent_id = extract_agent_identifier(data.get("tool_response"))
    if agent_id is None:
        return  # no recoverable agent identifier: fail-open, no action

    journal_dir = journal_dir_for(worktree_path)
    if not os.path.isdir(journal_dir):
        return  # absent journal directory: fail-open, never create it

    append_index_entry(journal_dir, agent_id, task_id, worktree_path)


def main():
    # Broad catch-all by design: this hook is a fail-open net
    # (IMPLEMENTATION.md "Conventions" / "Failure policy"), never a blocking
    # authority -- any unhandled state must still exit 0 rather than leave
    # the tool call blocked.
    try:
        data = json.load(sys.stdin)
        hook_main(data)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
