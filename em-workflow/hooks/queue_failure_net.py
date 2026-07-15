#!/usr/bin/env python3
"""em-workflow SubagentStop failure net: journal `failed` recorder.

Fires on EVERY subagent stop. Its only job is to make swallowed implementer
failures visible in the journal — it never blocks the stop and never decides
what to do about a failure (that is the orchestrator's protocol, prompted via
the Stop hook's failed-task pass-through). See IMPLEMENTATION.md's Journal
contract and Task-identity discovery contract
(feature-docs/implement-phase-queue/IMPLEMENTATION.md).

Behavior on each SubagentStop event (stdin = SubagentStop JSON):
  1. Identify the stopped agent: the `agent_type` field, when present, is
     authoritative (`em-workflow:implementer` or nothing happens). When
     absent, fall back to scanning the agent's first user message (an inline
     prompt field if one is ever provided, otherwise the transcript file at
     `agent_transcript_path`) for a `# Task assignment` block.
  2. Extract and validate `task_id` / `worktree_path` from that block; derive
     the sibling journal path (dirname(worktree_path)/journal.jsonl).
  3. Replay the journal for that task id (last event by file order):
       - `merged` or `failed` -> nothing to do.
       - anything else (`launched` or no event at all) -> append one `failed`
         event under flock.
  4. Any unexpected shape or unreadable state -> exit 0 silently (fail-open;
     see IMPLEMENTATION.md "Conventions" — these queue hooks are nets, not
     authorities, unlike bash_guard.py's fail-closed security boundary).

The hook ALWAYS exits 0 (never blocks the stop) — this is enforced by a
top-level catch-all in main(), not just by careful coding, because a stray
exception here must never turn into a hung/blocked subagent stop.
"""

import fcntl
import json
import os
import re
import sys
from datetime import datetime

IMPLEMENTER_AGENT_TYPE = "em-workflow:implementer"
FAILED_REASON = "implementer stopped without a merged event"

TASK_ASSIGNMENT_HEADER_RE = re.compile(r"^#\s*Task assignment\s*$", re.MULTILINE)
TASK_ID_LINE_RE = re.compile(r"^task_id:\s*(\S+)\s*$", re.MULTILINE)
WORKTREE_PATH_LINE_RE = re.compile(r"^worktree_path:\s*(\S+)\s*$", re.MULTILINE)
TASK_ID_RE = re.compile(r"^task[0-9]+$")

# Fields that might carry the initial prompt text directly (checked before
# falling back to reading agent_transcript_path from disk).
INLINE_PROMPT_FIELDS = ("prompt", "initial_prompt", "agent_prompt")


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


def first_user_message_text(transcript_path):
    """Read the FIRST user-role message text from a JSONL transcript file.
    Returns None on any unreadable/malformed condition (fail-open)."""
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
                if text is not None:
                    return text
    except OSError:
        return None
    return None


def find_prompt_text(data):
    for key in INLINE_PROMPT_FIELDS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    transcript_path = data.get("agent_transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return None
    return first_user_message_text(transcript_path)


def find_task_assignment(text):
    """Return (task_id, worktree_path) if text contains a well-formed and
    valid `# Task assignment` block; None otherwise."""
    if not isinstance(text, str) or not TASK_ASSIGNMENT_HEADER_RE.search(text):
        return None
    task_match = TASK_ID_LINE_RE.search(text)
    worktree_match = WORKTREE_PATH_LINE_RE.search(text)
    if not task_match or not worktree_match:
        return None
    task_id = task_match.group(1).strip()
    worktree_path = worktree_match.group(1).strip()
    if not valid_task_id(task_id) or not valid_worktree_path(worktree_path):
        return None
    return task_id, worktree_path


def replay_last_event(journal_path, task_id):
    """Last event (by file order) for task_id; None if the file is absent or
    carries no event for this task. Malformed lines are skipped."""
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


def now_rfc3339():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_failed_event(journal_path, task_id, reason):
    """Append one `failed` line under an exclusive flock on the journal file
    itself (Journal contract append discipline). Creates the file if absent
    (the containing directory is already confirmed to exist by the caller)."""
    entry = {
        "event": "failed",
        "task": task_id,
        "at": now_rfc3339(),
        "reason": reason,
    }
    line = json.dumps(entry, ensure_ascii=False)
    fd = os.open(journal_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def hook_main(data):
    if not isinstance(data, dict):
        return

    agent_type = data.get("agent_type")
    if isinstance(agent_type, str) and agent_type.strip():
        if agent_type.strip() != IMPLEMENTER_AGENT_TYPE:
            return  # explicit, different type: authoritative "not an implementer"

    text = find_prompt_text(data)
    if text is None:
        return

    identity = find_task_assignment(text)
    if identity is None:
        return
    task_id, worktree_path = identity

    journal_dir = os.path.dirname(worktree_path)
    if not os.path.isdir(journal_dir):
        return  # absent journal directory: fail-open, never fabricate state
    journal_path = os.path.join(journal_dir, "journal.jsonl")

    last_event = replay_last_event(journal_path, task_id)
    if last_event in ("merged", "failed"):
        return

    append_failed_event(journal_path, task_id, FAILED_REASON)


def main():
    # Broad catch-all by design: this hook is a fail-open net (IMPLEMENTATION.md
    # "Conventions"), never a blocking authority — any unhandled state must
    # still exit 0 rather than leave the subagent stop hung.
    try:
        data = json.load(sys.stdin)
        hook_main(data)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
