"""Subprocess-driven contract tests for em-workflow/hooks/queue_stop_guard.py.

Per test/README.md: hooks are invoked as subprocesses with Claude Code
Stop-hook JSON on stdin; assertions are on exit code and stderr content.
Fixtures are throwaway temp directories shaped like a project root
(feature-docs/{feature}/workflow.yaml +
.claude/worktrees/em-workflow/{feature}/journal.jsonl).
"""

import ast
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_stop_guard.py")


def build_workflow_yaml(feature, implement_status, task_ids):
    lines = [
        "schema_version: 1",
        f"feature: {feature}",
        "created: 2026-07-15",
        "base_branch: main",
        f"parent_branch: em-workflow/{feature}/integration",
        "",
        "project:",
        "  components:",
        "    main:",
        "      language: python",
        '      build_command: ""',
        '      test_command: "python3 -m unittest discover -s tests"',
        '      format_command: ""',
        "",
        "workflow:",
        "  - id: create-spec",
        "    status: completed",
        "  - id: design",
        "    status: skipped",
        "  - id: create-plan",
        "    status: completed",
        "  - id: implement",
        f"    status: {implement_status}",
        "    base_commit: null",
        "  - id: review",
        "    status: pending",
        "  - id: verify",
        "    status: pending",
        "  - id: retrospect",
        "    status: pending",
        "",
        "tasks:",
    ]
    for task_id in task_ids:
        lines.extend(
            [
                f"  {task_id}:",
                f'    title: "task {task_id}"',
                f"    plan: tasks/{task_id}.md",
                "    files: []",
                "    skills: [infra-impl]",
                "    domains: []",
                "    complexity: medium",
                "    requirements: []",
                "    status: pending",
                "    notes: null",
            ]
        )
    return "\n".join(lines) + "\n"


class StopGuardFixture:
    """Builds a throwaway project-root directory for one feature."""

    def __init__(self, tmp_dir, feature="sample-feature"):
        self.root = tmp_dir
        self.feature = feature
        self.docs_dir = os.path.join(self.root, "feature-docs", feature)
        self.journal_dir = os.path.join(
            self.root, ".claude", "worktrees", "em-workflow", feature
        )
        os.makedirs(self.docs_dir, exist_ok=True)

    def write_workflow(self, implement_status, task_ids):
        content = build_workflow_yaml(self.feature, implement_status, task_ids)
        with open(os.path.join(self.docs_dir, "workflow.yaml"), "w") as fh:
            fh.write(content)

    def write_journal(self, records, raw_extra_lines=None):
        os.makedirs(self.journal_dir, exist_ok=True)
        path = os.path.join(self.journal_dir, "journal.jsonl")
        with open(path, "w") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
            for raw_line in raw_extra_lines or []:
                fh.write(raw_line + "\n")
        return path

    def sidecar_path(self):
        return os.path.join(self.journal_dir, "stop-guard-state.json")


def launched(task_id, at="2026-07-15T09:00:00+09:00"):
    return {"event": "launched", "task": task_id, "at": at}


def merged(task_id, commit="deadbeef", at="2026-07-15T09:05:00+09:00"):
    return {"event": "merged", "task": task_id, "commit": commit, "at": at}


def failed(task_id, reason="boom", at="2026-07-15T09:05:00+09:00"):
    return {"event": "failed", "task": task_id, "reason": reason, "at": at}


def invoke_hook(cwd, raw_stdin):
    import subprocess

    return subprocess.run(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input=raw_stdin,
        capture_output=True,
        text=True,
        timeout=15,
    )


DEFAULT_STDIN = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})


class TestQueueStopGuardBlocking(unittest.TestCase):
    """AC-1: block with the exact bounded, ascending task-id list."""

    def test_free_slots_and_unlaunched_tasks_blocks_with_bounded_ascending_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = [f"task{i:04d}" for i in range(1, 9)]  # 8 tasks
            fx.write_workflow("in_progress", task_ids)
            # 3 in-flight -> free_slots = 6 - 3 = 3; 5 unlaunched remain.
            fx.write_journal(
                [launched("task0006"), launched("task0007"), launched("task0008")]
            )

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("sample-feature", result.stderr)
            self.assertIn("free_slots=3", result.stderr)
            for expected in ("task0001", "task0002", "task0003"):
                self.assertIn(expected, result.stderr)
            for not_expected in ("task0004", "task0005", "task0006", "task0007", "task0008"):
                self.assertNotIn(not_expected, result.stderr)


class TestQueueStopGuardFailedTask(unittest.TestCase):
    """AC-2: a failed task suppresses blocking even with capacity."""

    def test_failed_task_present_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([failed("task0001")])  # task0002/3 unlaunched, free slots plenty

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)


class TestQueueStopGuardNonBlockingStates(unittest.TestCase):
    """AC-3: full slots / zero pending / no active feature."""

    def test_exactly_six_in_flight_no_free_slot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = [f"task{i:04d}" for i in range(1, 8)]  # 7 tasks
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([launched(t) for t in task_ids[:6]])  # 6 in flight

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_zero_unlaunched_tasks_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([merged("task0001"), launched("task0002")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_no_feature_with_implement_in_progress_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("pending", ["task0001", "task0002"])
            # No journal at all: implement hasn't started.

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)


class TestQueueStopGuardConsecutiveBlockCap(unittest.TestCase):
    """AC-4: cap at 3 consecutive blocks in the same state; state change resets."""

    def test_three_blocks_then_fourth_passes_with_warning_then_state_change_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([])  # all three unlaunched, 6 free slots

            for i in range(1, 4):
                result = invoke_hook(tmp, DEFAULT_STDIN)
                self.assertEqual(result.returncode, 2, f"block #{i} should block")

            fourth = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(fourth.returncode, 0)
            self.assertIn("WARNING", fourth.stderr)

            # A state change (task0001 now launched) must reset the cap.
            fx.write_journal([launched("task0001")])
            after_change = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(after_change.returncode, 2)

            # And it should again tolerate up to 3 consecutive blocks in
            # this new state before bypassing.
            second = invoke_hook(tmp, DEFAULT_STDIN)
            third = invoke_hook(tmp, DEFAULT_STDIN)
            fourth_in_new_state = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(third.returncode, 2)
            self.assertEqual(fourth_in_new_state.returncode, 0)
            self.assertIn("WARNING", fourth_in_new_state.stderr)


class TestQueueStopGuardFailOpen(unittest.TestCase):
    """AC-5: missing journal / malformed journal lines / malformed stdin /
    missing feature-docs never crash and never block."""

    def test_missing_journal_directory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            # journal_dir intentionally never created.

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)

    def test_malformed_journal_line_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal(
                [launched("task0003")],
                raw_extra_lines=["{not valid json", "", "   "],
            )

            result = invoke_hook(tmp, DEFAULT_STDIN)

            # task0003 in-flight (from the valid line); task0001/2 unlaunched
            # with free slots -> still blocks; the malformed lines must not
            # crash the hook.
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("task0001", result.stderr)
            self.assertIn("task0002", result.stderr)
            self.assertNotIn("task0003", result.stderr)

    def test_malformed_stdin_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001"])
            fx.write_journal([])

            result = invoke_hook(tmp, "not valid json at all")

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_feature_docs_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            # An entirely empty project root: no feature-docs/ at all.
            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)


class TestQueueStopGuardRetryAfterFailure(unittest.TestCase):
    """AC-6: failed -> launched (retry) counts as in-flight, not failed/unlaunched."""

    def test_retried_task_counts_as_in_flight(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = [f"task{i:04d}" for i in range(1, 8)]  # 7 tasks
            fx.write_workflow("in_progress", task_ids)
            # task0001 failed then relaunched (retry); task0002 unlaunched
            # remains pending; the rest untouched/unlaunched.
            fx.write_journal(
                [failed("task0001"), launched("task0001")]
            )

            result = invoke_hook(tmp, DEFAULT_STDIN)

            # No task's LAST event is `failed` -> must not suppress blocking.
            self.assertEqual(result.returncode, 2)
            # task0001 is in-flight (not unlaunched): must not appear in the
            # launch list, and free_slots must reflect 1 in-flight task.
            self.assertIn("free_slots=5", result.stderr)
            self.assertNotIn("task0001", result.stderr)
            self.assertIn("task0002", result.stderr)


class TestQueueStopGuardStdlibOnly(unittest.TestCase):
    """AC-7: the script imports only Python stdlib modules."""

    def test_only_stdlib_imports(self):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=HOOK_PATH)

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported_names.add(node.module.split(".")[0])

        self.assertTrue(imported_names, "expected at least one import")
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        for name in imported_names:
            if stdlib_names is not None:
                self.assertIn(name, stdlib_names, f"{name} is not a stdlib module")


if __name__ == "__main__":
    unittest.main()
