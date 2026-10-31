#!/usr/bin/env python3
"""em-workflow queue launch guard: PreToolUse hook on subagent-launch calls.

The subagent-launch tool is named `Agent` in current Claude Code versions
and `Task` in older ones — the hook accepts BOTH tool names (and hooks.json
registers the matcher `Task|Agent`). Matching only one name silently
disables the guard on the other: the fail-open convention means no launched
events get recorded and no double-launch is ever denied (observed in the
wild on 2.1.211, where launches arrive as `Agent`).

Deterministic net for the implement-phase work-queue loop
(feature-docs/implement-phase-queue/IMPLEMENTATION.md). Keeps the
per-feature journal (`journal.jsonl`) machine-written by:

  - denying a `Task()` launch that would double-launch a task whose last
    journal event is `launched` (already in flight);
  - denying a `Task()` launch that would relaunch a task whose last journal
    event is `merged` (terminal — always a mistake);
  - denying a `Task()` launch while the orchestrator's cwd is not the
    project root: a subagent inherits that cwd, and the cross-repo write
    guard judges every write against the git toplevel of it, so an
    implementer started inside another worktree has its writes to its own
    worktree denied. Checked before the journal is touched, so a denied
    launch leaves no `launched` event behind;
  - allowing every other em-workflow implementer launch (no events yet, or
    last event `failed` — the retry path) and appending exactly one
    `launched` event before the call proceeds.

The replay -> decide -> append sequence runs as ONE critical section under
an exclusive flock on the journal file (atomic compare-and-append):
concurrent PreToolUse invocations for the same task serialize on the lock,
so exactly one of them observes "not in flight" and appends `launched`;
the rest see that event and deny.

Identity discovery (Task-identity discovery contract, IMPLEMENTATION.md):
an invocation counts as an em-workflow implementer launch if and only if its
`subagent_type` is `em-workflow:implementer` (when the hook input provides
that field) or, failing that, its prompt contains a `# Task assignment`
block with a valid `task_id:` line. Anything else is none of this hook's
concern: exit 0, no output, no journal write.

Project root: the directory the cwd check compares the cwd's git toplevel
with. When the worktree path contains the `.claude/worktrees/em-workflow/`
segment, the project root is the prefix before its last occurrence. When the
segment is absent, the project root is the parent directory of the git common
dir resolved from the worktree path (`git rev-parse --path-format=absolute
--git-common-dir`, run once with the worktree path as its working directory);
this is the case in a linked layout, where `.claude`, `.claude/worktrees` or
`.claude/worktrees/em-workflow` is a link and the canonical worktree path has
no such segment. When neither resolves, the project root is undetermined and
the cwd check is skipped (fail-open).

Fail-open convention: this hook is a net, not an authority. Any unexpected
state — malformed stdin, an invalid task id or worktree path, an unreadable
journal, an uncreatable journal location, a missing cwd, a cwd whose git
toplevel cannot be resolved — exits 0 silently rather than
risk blocking (or crashing) the user's session. The orchestrator protocol
and the resume guard remain authoritative.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime

TASK_ID_RE = re.compile(r"^task[0-9]+$")
ASSIGNMENT_HEADER_RE = re.compile(r"(?m)^# Task assignment\s*$")
TASK_ID_LINE_RE = re.compile(r"(?m)^task_id:\s*(\S+)\s*$")
WORKTREE_PATH_LINE_RE = re.compile(r"(?m)^worktree_path:\s*(\S.*?)\s*$")

IMPLEMENTER_SUBAGENT_TYPE = "em-workflow:implementer"

# Task worktrees live at `{project_root}/.claude/worktrees/em-workflow/{feature}/{T}`.
WORKTREES_SEGMENT = "/.claude/worktrees/em-workflow/"

GIT_TIMEOUT_SECONDS = 5

# The subagent-launch tool's name: `Agent` in current Claude Code versions,
# `Task` in older ones. Both are guarded.
LAUNCH_TOOL_NAMES = ("Task", "Agent")


def extract_task_assignment(prompt):
    """Pull (task_id, worktree_path) out of a `# Task assignment` block.

    Returns (None, None) when the prompt carries no such block at all (the
    block header must be present); individual missing lines yield None for
    that field only.
    """
    if not isinstance(prompt, str):
        return None, None
    header = ASSIGNMENT_HEADER_RE.search(prompt)
    if not header:
        return None, None
    tail = prompt[header.end() :]
    task_id_match = TASK_ID_LINE_RE.search(tail)
    worktree_match = WORKTREE_PATH_LINE_RE.search(tail)
    task_id = task_id_match.group(1) if task_id_match else None
    worktree_path = worktree_match.group(1) if worktree_match else None
    return task_id, worktree_path


def is_implementer_launch(tool_input, task_id):
    """Task-identity discovery: subagent_type when provided, else the block."""
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


def git_common_dir_root(worktree_path):
    """The parent directory of the git common dir resolved from
    `worktree_path`, or None when git cannot resolve one.

    One `git rev-parse` run with `worktree_path` as its working directory,
    bounded by GIT_TIMEOUT_SECONDS. A process that cannot start (a missing
    working directory included), a timeout, a non-zero exit, and output that
    is empty or not an absolute path all leave the root undetermined.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    common_dir = proc.stdout.strip()
    if not common_dir or not os.path.isabs(common_dir):
        return None
    return os.path.dirname(os.path.normpath(common_dir))


def project_root_for(worktree_path):
    """The project root a task worktree belongs to, or None when it cannot
    be determined.

    The `.claude/worktrees/em-workflow/` segment decides when the normalized
    path contains it: the root is the prefix before its last occurrence (a
    segment at the very start of the path leaves the root undetermined, with
    no fallback). When the segment does not occur at all, as in a linked
    layout where the canonical path lacks it, the root is the parent of the
    git common dir resolved from the worktree path.
    """
    norm = os.path.normpath(worktree_path)
    index = norm.rfind(WORKTREES_SEGMENT)
    if index > 0:
        return norm[:index]
    if index == 0:
        return None
    return git_common_dir_root(worktree_path)


def git_toplevel(cwd):
    """The output of `git rev-parse --show-toplevel` in `cwd`, or None."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    top = proc.stdout.strip()
    return top or None


def cwd_outside_project_root(cwd, worktree_path):
    """The project root when it is determined, `cwd`'s git toplevel is
    resolvable and is not it (the launch must be denied); None otherwise
    (including every undecidable state)."""
    if not isinstance(cwd, str) or not cwd:
        return None
    project_root = project_root_for(worktree_path)
    if project_root is None:
        return None
    top = git_toplevel(cwd)
    if top is None:
        return None
    if os.path.realpath(top) == os.path.realpath(project_root):
        return None
    return project_root


def journal_path_for(worktree_path):
    return os.path.join(os.path.dirname(os.path.normpath(worktree_path)), "journal.jsonl")


def open_journal_locked(path):
    """Open (creating if absent) the journal with an exclusive flock held.

    O_NOFOLLOW: a symlink planted at the journal path must never redirect
    the append elsewhere (defense in depth; the path is validated upstream).
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


def append_launched_fd(fd, task_id):
    """Append the launched line through the locked fd (O_APPEND)."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    line = json.dumps({"event": "launched", "task": task_id, "at": now}, ensure_ascii=False)
    os.write(fd, (line + "\n").encode("utf-8"))
    os.fsync(fd)


def emit_deny(reason, additional_context=None):
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    if additional_context:
        output["hookSpecificOutput"]["additionalContext"] = additional_context
    json.dump(output, sys.stdout, ensure_ascii=False)


def deny_in_flight(task_id):
    emit_deny(
        f"em-workflow queue guard: タスク {task_id} はすでに実行中だよ"
        "（journal の最終イベントが launched）。二重起動になるから今は再起動しないで。",
        "merged か failed になってから、必要であれば再度 Task() を起動して。"
        "in-flight 状態は journal.jsonl の最終イベントで判定しているよ。",
    )


def deny_already_merged(task_id):
    emit_deny(
        f"em-workflow queue guard: タスク {task_id} はすでに merge 済みだよ"
        "（journal の最終イベントが merged）。merge 済みタスクの再起動は常に誤りとして扱うよ。",
        "追加の変更が必要なら、新しいタスクとして起票して。",
    )


def deny_cwd_outside_project_root(task_id, cwd, project_root):
    emit_deny(
        f"em-workflow queue guard: 作業ディレクトリ（{cwd}）がプロジェクトのルート"
        f"（{project_root}）じゃないから、タスク {task_id} を起動しないよ。"
        "implementer は今の作業ディレクトリを引き継ぐから、このまま起動すると"
        "自分の worktree への書き込みが cross-repo-write-guard に拒否されちゃう。",
        f"Bash で単独の cd \"{project_root}\" を実行してプロジェクトのルートに戻ってから、"
        "同じ Task() を起動し直して。",
    )


def hook_main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0  # malformed stdin: no decision, normal permission flow

    if not isinstance(data, dict) or data.get("tool_name") not in LAUNCH_TOOL_NAMES:
        return 0

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    try:
        task_id, worktree_path = extract_task_assignment(tool_input.get("prompt"))

        if not is_implementer_launch(tool_input, task_id):
            return 0  # not an em-workflow implementer launch: none of our concern

        if not valid_task_id(task_id) or not valid_worktree_path(worktree_path):
            return 0  # fail-open: the orchestrator's own fail-closed gate governs real launches

        # Before the journal: a denied launch must not leave `launched` behind.
        cwd = data.get("cwd")
        project_root = cwd_outside_project_root(cwd, worktree_path)
        if project_root is not None:
            deny_cwd_outside_project_root(task_id, cwd, project_root)
            return 0

        path = journal_path_for(worktree_path)

        # Atomic compare-and-append: replay -> decide -> append happen inside
        # ONE flock critical section, so concurrent invocations for the same
        # task cannot both observe "not in flight" and both append.
        fd = open_journal_locked(path)
        try:
            last_event = last_event_for_task_fd(fd, task_id)

            if last_event == "launched":
                deny_in_flight(task_id)
                return 0
            if last_event == "merged":
                deny_already_merged(task_id)
                return 0

            # No events, or last event "failed" (retry path): allow. Append
            # the launched line BEFORE the subagent actually starts (D2 in
            # IMPLEMENTATION.md); exit with no decision output so the normal
            # permission flow proceeds.
            append_launched_fd(fd, task_id)
            return 0
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except OSError:
        return 0  # unreadable/absent journal location: fail open, never crash


def main():
    return hook_main()


if __name__ == "__main__":
    sys.exit(main())
