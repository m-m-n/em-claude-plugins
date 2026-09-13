"""Retry-reachability proof for `queue_launch_guard.py` against this
feature's new `stale-launched` failed-reason value (task0004,
stale-launched-retry-recovery).

Covers task0004 Acceptance Criteria
(feature-docs/stale-launched-retry-recovery/tasks/task0004.md):

- AC-1 (FR8): against a journal whose last event for the task is a `failed`
  line with reason `stale-launched`, the guard exits 0, produces no deny
  decision, and the journal gains exactly one `launched` line for that
  task.
- AC-2 (FR8): against a journal whose last event for the task is `launched`,
  the guard denies the relaunch and appends nothing; against one whose last
  event is `merged`, it denies and appends nothing -- double-launch
  prevention undiminished.
- AC-3 (FR8): the launch guard's source file is not in this feature's
  change set; this module reads it only as a subprocess target and never
  imports or rewrites it.
- AC-8 (NFR6): this module imports only the standard library.

`em-workflow/hooks/queue_launch_guard.py` is NOT modified by this feature
(IMPLEMENTATION.md: "queue_launch_guard.py is not modified by any task
(FR8)"). The guard's decision reads only the journal's last event name for
the task -- it never inspects a `failed` line's `reason` field -- so the
retry path this task proves was already open before this feature existed;
what is new is the `stale-launched` reason value itself (written by a
sibling task), and this module is the proof that its presence changes
nothing about reachability or about the two deny paths.
"""

import ast
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_launch_guard.py")


def build_prompt(task_id, worktree_path):
    return (
        "# Task assignment\n"
        f"task_id: {task_id}\n"
        f"worktree_path: {worktree_path}\n"
        f"task_plan_path: /main/feature-docs/f/tasks/{task_id}.md\n"
        f"implementation_md_path: /main/feature-docs/f/IMPLEMENTATION.md\n"
        f"parent_branch: em-workflow/f/integration\n"
        f"merge_script: /main/em-workflow/scripts/merge-task.sh\n"
        f"skills_to_load: []\n"
        f"project_commands:\n"
        f"  build: \"\"\n"
        f"  test: \"echo ok\"\n"
        f"  format: \"\"\n"
        f"expected_files: []\n"
    )


def task_payload(task_id, worktree_path):
    return {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "em-workflow:implementer",
            "description": f"Implement {task_id}",
            "prompt": build_prompt(task_id, worktree_path),
        },
    }


def run_hook(stdin_text):
    return subprocess.run(
        [sys.executable, HOOK_PATH],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


def run_hook_payload(payload):
    return run_hook(json.dumps(payload))


def journal_path_for(worktree_path):
    return os.path.join(os.path.dirname(worktree_path), "journal.jsonl")


def write_journal(worktree_path, lines):
    path = journal_path_for(worktree_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    return path


def read_journal_lines(worktree_path):
    path = journal_path_for(worktree_path)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def last_event_for_task(lines, task_id):
    """Replay `lines` (already-parsed journal entries) and return the LAST
    event name recorded for `task_id`, or None if it never appears. An
    independent, from-scratch reimplementation in test code -- this module
    never imports the guard's own replay logic (AC-3)."""
    last = None
    for entry in lines:
        if entry.get("task") == task_id:
            last = entry.get("event")
    return last


@contextlib.contextmanager
def _tmp_worktree(task_id="task0001"):
    with tempfile.TemporaryDirectory() as tmp_root:
        yield os.path.join(tmp_root, task_id)


class TestRetryAfterStaleLaunchedFailure(unittest.TestCase):
    """AC-1: last event `failed` with reason `stale-launched` -> allow,
    exactly one new `launched` line appended for that task."""

    def test_allows_relaunch_and_appends_one_launched_line(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [
                    {
                        "event": "failed",
                        "task": "task0001",
                        "at": "2026-09-01T00:00:00+00:00",
                        "reason": "stale-launched",
                    }
                ],
            )
            before = read_journal_lines(worktree_path)
            self.assertEqual(last_event_for_task(before, "task0001"), "failed")

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")  # no deny decision emitted

            after = read_journal_lines(worktree_path)
            self.assertEqual(last_event_for_task(after, "task0001"), "launched")
            # Exactly one line was appended -- proven by replaying the
            # fixture journal for the task before and after, not by
            # counting raw file lines (Test Notes).
            self.assertEqual(len(after), len(before) + 1)
            appended = after[len(before):]
            self.assertEqual(len(appended), 1)
            self.assertEqual(appended[0]["event"], "launched")
            self.assertEqual(appended[0]["task"], "task0001")

    def test_per_task_replay_is_not_confused_by_a_second_tasks_events(self):
        # A fixture whose journal carries events for two task ids, proving
        # the last-event replay this task relies on is per-task.
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [
                    {"event": "launched", "task": "task0002",
                     "at": "2026-09-01T00:00:00+00:00"},
                    {"event": "failed", "task": "task0001",
                     "at": "2026-09-01T00:01:00+00:00", "reason": "stale-launched"},
                    {"event": "merged", "task": "task0002",
                     "at": "2026-09-01T00:02:00+00:00", "commit": "deadbeef"},
                ],
            )
            before = read_journal_lines(worktree_path)
            self.assertEqual(last_event_for_task(before, "task0001"), "failed")
            self.assertEqual(last_event_for_task(before, "task0002"), "merged")

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")

            after = read_journal_lines(worktree_path)
            self.assertEqual(last_event_for_task(after, "task0001"), "launched")
            # task0002's own last event must be untouched by task0001's relaunch.
            self.assertEqual(last_event_for_task(after, "task0002"), "merged")
            self.assertEqual(len(after), len(before) + 1)


class TestDoubleLaunchPreventionUndiminished(unittest.TestCase):
    """AC-2: an in-flight (`launched`) or merged task is still denied and
    nothing is appended, even when a `stale-launched` failure sits earlier
    in that same task's journal history."""

    def test_last_event_launched_denies_and_appends_nothing(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [
                    {"event": "failed", "task": "task0001",
                     "at": "2026-09-01T00:00:00+00:00", "reason": "stale-launched"},
                    {"event": "launched", "task": "task0001",
                     "at": "2026-09-01T00:01:00+00:00"},
                ],
            )
            before = read_journal_lines(worktree_path)

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            decision = json.loads(proc.stdout)
            self.assertEqual(
                decision["hookSpecificOutput"]["permissionDecision"], "deny"
            )

            after = read_journal_lines(worktree_path)
            self.assertEqual(after, before)  # nothing appended

    def test_last_event_merged_denies_and_appends_nothing(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [
                    {"event": "failed", "task": "task0001",
                     "at": "2026-09-01T00:00:00+00:00", "reason": "stale-launched"},
                    {"event": "launched", "task": "task0001",
                     "at": "2026-09-01T00:01:00+00:00"},
                    {"event": "merged", "task": "task0001",
                     "at": "2026-09-01T00:02:00+00:00", "commit": "cafef00d"},
                ],
            )
            before = read_journal_lines(worktree_path)

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            decision = json.loads(proc.stdout)
            self.assertEqual(
                decision["hookSpecificOutput"]["permissionDecision"], "deny"
            )

            after = read_journal_lines(worktree_path)
            self.assertEqual(after, before)  # nothing appended


class TestGuardSourceUntouched(unittest.TestCase):
    """AC-3: the guard's source file is out of scope for this feature; this
    module reads it only as a subprocess target, never importing or
    rewriting it."""

    def test_module_never_imports_the_guard(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertNotIn("queue_launch_guard", imported)

    def test_guard_source_bytes_unchanged_after_invocation(self):
        with open(HOOK_PATH, "rb") as fh:
            before = fh.read()

        with _tmp_worktree() as worktree_path:
            run_hook_payload(task_payload("task0001", worktree_path))

        with open(HOOK_PATH, "rb") as fh:
            after = fh.read()

        self.assertEqual(before, after)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-8 (NFR6): this new module imports only the standard library."""

    def test_only_standard_library_imports(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
