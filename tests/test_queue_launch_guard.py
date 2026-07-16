"""Subprocess-driven contract tests for queue_launch_guard.py.

Mirrors the PreToolUse JSON contract Claude Code actually sends for a
`Task(subagent_type="em-workflow:implementer")` launch (implement-phase.md
Step I.2.b payload embedded in tool_input.prompt).
"""

import ast
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_launch_guard.py")

AT_RE_FMT = "%Y-%m-%dT%H:%M:%S%z"


def build_prompt(task_id, worktree_path, include_header=True):
    header = "# Task assignment\n" if include_header else ""
    return (
        f"{header}"
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


def run_hook(stdin_text):
    proc = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc


def run_hook_payload(payload):
    return run_hook(json.dumps(payload))


def task_payload(task_id, worktree_path, subagent_type="em-workflow:implementer", include_header=True):
    return {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": subagent_type,
            "description": f"Implement {task_id}",
            "prompt": build_prompt(task_id, worktree_path, include_header=include_header),
        },
    }


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


def assert_rfc3339_with_offset(value):
    # Must parse as an RFC 3339 timestamp carrying an explicit UTC offset
    # (never a bare, timezone-less timestamp).
    parsed = datetime.strptime(value, AT_RE_FMT)
    assert parsed.utcoffset() is not None


class TestFirstLaunch(unittest.TestCase):
    """AC-1: no journal events -> allow, append exactly one launched line."""

    def test_first_launch_allowed_and_appends_launched_event(self):
        with _tmp_worktree() as worktree_path:
            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")

            lines = read_journal_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["event"], "launched")
            self.assertEqual(lines[0]["task"], "task0001")
            assert_rfc3339_with_offset(lines[0]["at"])


class TestInFlightDenial(unittest.TestCase):
    """AC-2: last event launched -> deny, task id in reason, nothing appended."""

    def test_launch_denied_when_last_event_is_launched(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [{"event": "launched", "task": "task0001", "at": "2026-07-15T00:00:00+00:00"}],
            )

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            decision = json.loads(proc.stdout)
            self.assertEqual(
                decision["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn("task0001", decision["hookSpecificOutput"]["permissionDecisionReason"])

            lines = read_journal_lines(worktree_path)
            self.assertEqual(len(lines), 1)  # nothing appended


class TestRetryAfterFailure(unittest.TestCase):
    """AC-3: last event failed -> allow (retry path), appends a new launched line."""

    def test_launch_allowed_after_failed_retry(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [{"event": "failed", "task": "task0001", "at": "2026-07-15T00:00:00+00:00",
                  "reason": "build failed"}],
            )

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")

            lines = read_journal_lines(worktree_path)
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[-1]["event"], "launched")
            self.assertEqual(lines[-1]["task"], "task0001")


class TestMergedDenial(unittest.TestCase):
    """AC-4: last event merged -> deny (distinct reason), nothing appended."""

    def test_launch_denied_when_last_event_is_merged(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [{"event": "merged", "task": "task0001", "at": "2026-07-15T00:00:00+00:00",
                  "commit": "abc123"}],
            )

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            self.assertEqual(proc.returncode, 0)
            decision = json.loads(proc.stdout)
            self.assertEqual(
                decision["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            merged_reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("task0001", merged_reason)

            lines = read_journal_lines(worktree_path)
            self.assertEqual(len(lines), 1)  # nothing appended

    def test_merged_and_in_flight_denials_have_distinct_reasons(self):
        with _tmp_worktree() as worktree_path_a, _tmp_worktree() as worktree_path_b:
            write_journal(
                worktree_path_a,
                [{"event": "merged", "task": "task0001", "at": "2026-07-15T00:00:00+00:00",
                  "commit": "abc123"}],
            )
            write_journal(
                worktree_path_b,
                [{"event": "launched", "task": "task0001", "at": "2026-07-15T00:00:00+00:00"}],
            )

            merged_decision = json.loads(
                run_hook_payload(task_payload("task0001", worktree_path_a)).stdout
            )
            in_flight_decision = json.loads(
                run_hook_payload(task_payload("task0001", worktree_path_b)).stdout
            )

            self.assertNotEqual(
                merged_decision["hookSpecificOutput"]["permissionDecisionReason"],
                in_flight_decision["hookSpecificOutput"]["permissionDecisionReason"],
            )


class TestNonImplementerCallsIgnored(unittest.TestCase):
    """AC-5: not an em-workflow implementer launch -> exit 0, no decision, no write."""

    def test_different_subagent_type_with_no_assignment_block_is_ignored(self):
        with _tmp_worktree() as worktree_path:
            payload = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "Explore",
                    "description": "look around",
                    "prompt": "Explore the codebase and summarize it.",
                },
            }
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(read_journal_lines(worktree_path), [])

    def test_different_subagent_type_takes_priority_over_assignment_block(self):
        # subagent_type is provided and is NOT em-workflow:implementer: identity
        # is decided by the type field, even though the prompt happens to carry
        # a well-formed assignment block.
        with _tmp_worktree() as worktree_path:
            payload = task_payload("task0001", worktree_path, subagent_type="Explore")
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(read_journal_lines(worktree_path), [])

    def test_missing_subagent_type_and_no_assignment_block_is_ignored(self):
        with _tmp_worktree() as worktree_path:
            payload = {
                "tool_name": "Task",
                "tool_input": {
                    "description": "some other task",
                    "prompt": "Please do something unrelated.\ntask_id: task0001\n",
                },
            }
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(read_journal_lines(worktree_path), [])

    def test_non_task_tool_is_ignored(self):
        proc = run_hook_payload(
            {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")


class TestFailOpen(unittest.TestCase):
    """AC-6: malformed stdin / invalid identifiers / uncreatable journal -> exit 0, no crash."""

    def test_malformed_stdin_exits_zero(self):
        proc = run_hook("not json at all {{{")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_empty_stdin_exits_zero(self):
        proc = run_hook("")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_invalid_task_id_exits_zero_no_write(self):
        with _tmp_worktree() as worktree_path:
            proc = run_hook_payload(task_payload("not-a-task-id", worktree_path))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(read_journal_lines(worktree_path), [])

    def test_relative_worktree_path_exits_zero_no_write(self):
        proc = run_hook_payload(task_payload("task0001", "relative/path/task0001"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_uncreatable_journal_location_exits_zero(self):
        bogus_worktree = "/nonexistent-em-workflow-dir-xyz/task0001"
        self.assertFalse(os.path.isdir(os.path.dirname(bogus_worktree)))

        proc = run_hook_payload(task_payload("task0001", bogus_worktree))

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(os.path.isdir(os.path.dirname(bogus_worktree)))


class TestMalformedJournalLineSkipped(unittest.TestCase):
    """A bad line between valid ones must not flip the state derivation."""

    def test_malformed_line_between_valid_ones_is_skipped(self):
        with _tmp_worktree() as worktree_path:
            path = journal_path_for(worktree_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(
                    {"event": "launched", "task": "task0001", "at": "2026-07-15T00:00:00+00:00"}
                ) + "\n")
                fh.write("{not valid json,,,\n")
                fh.write(json.dumps(
                    {"event": "merged", "task": "task0001", "at": "2026-07-15T00:10:00+00:00",
                     "commit": "abc123"}
                ) + "\n")

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            decision = json.loads(proc.stdout)
            self.assertEqual(
                decision["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn("task0001", decision["hookSpecificOutput"]["permissionDecisionReason"])
            # last real event was merged, not launched -> deny reason must be
            # the merged one, proving the garbage line did not become "last".
            lines = read_journal_lines_tolerant(worktree_path)
            self.assertEqual(len(lines), 3)

    def test_other_tasks_lines_do_not_affect_this_tasks_derivation(self):
        with _tmp_worktree() as worktree_path:
            write_journal(
                worktree_path,
                [
                    {"event": "merged", "task": "task0002", "at": "2026-07-15T00:00:00+00:00",
                     "commit": "zzz"},
                    {"event": "launched", "task": "task0001", "at": "2026-07-15T00:01:00+00:00"},
                    {"event": "failed", "task": "task0001", "at": "2026-07-15T00:02:00+00:00",
                     "reason": "oops"},
                    {"event": "launched", "task": "task0002", "at": "2026-07-15T00:03:00+00:00"},
                ],
            )

            proc = run_hook_payload(task_payload("task0001", worktree_path))

            # task0001's own last event is "failed" -> retry path -> allowed.
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            lines = read_journal_lines(worktree_path)
            self.assertEqual(len(lines), 5)
            self.assertEqual(lines[-1], {"event": "launched", "task": "task0001",
                                          "at": lines[-1]["at"]})


def read_journal_lines_tolerant(worktree_path):
    """Like read_journal_lines but tolerates (and counts) malformed lines."""
    path = journal_path_for(worktree_path)
    with open(path, encoding="utf-8") as fh:
        return [line for line in fh if line.strip()]


class TestStdlibOnly(unittest.TestCase):
    """AC-7: the script imports only Python stdlib modules."""

    def test_imports_are_all_stdlib(self):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=HOOK_PATH)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in the hook script")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


@contextlib.contextmanager
def _tmp_worktree():
    """A fresh temp dir standing in for the feature's worktree root, with a
    'worktree_path' inside it (dirname(worktree_path) is where journal.jsonl
    lives, per the journal contract)."""
    with tempfile.TemporaryDirectory() as tmp_root:
        yield os.path.join(tmp_root, "task0001")


class TestConcurrentLaunchAtomicity(unittest.TestCase):
    """Review round 1 regression: the replay -> decide -> append sequence is
    one flock critical section, so N concurrent launches for the SAME task
    yield exactly one `launched` event and N-1 denials."""

    def test_concurrent_same_task_launches_yield_one_launched_and_denials(self):
        import threading

        with _tmp_worktree() as worktree_path:
            os.makedirs(os.path.dirname(worktree_path), exist_ok=True)
            stdin_text = json.dumps(task_payload("task0001", worktree_path))

            n = 6
            results = [None] * n
            barrier = threading.Barrier(n)

            def launch(i):
                barrier.wait()
                results[i] = run_hook(stdin_text)

            threads = [threading.Thread(target=launch, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            lines = read_journal_lines(worktree_path)
            launched_lines = [l for l in lines if l.get("event") == "launched"]
            self.assertEqual(
                len(launched_lines), 1,
                f"exactly one launched event expected, journal: {lines}",
            )

            denials = 0
            for proc in results:
                self.assertEqual(proc.returncode, 0)
                if proc.stdout.strip():
                    decision = json.loads(proc.stdout)
                    self.assertEqual(
                        decision["hookSpecificOutput"]["permissionDecision"], "deny"
                    )
                    denials += 1
            self.assertEqual(denials, n - 1)


class TestWorktreePathValidationConsistency(unittest.TestCase):
    """Review round 1 regression: `..` segments are rejected (parser/validator
    parity with queue_failure_net.py)."""

    def test_dotdot_worktree_path_exits_zero_no_write(self):
        with _tmp_worktree() as worktree_path:
            evil = os.path.join(os.path.dirname(worktree_path), "..", "task0001")
            proc = run_hook_payload(task_payload("task0001", evil))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout.strip(), "")
            self.assertEqual(read_journal_lines(worktree_path), [])


if __name__ == "__main__":
    unittest.main()
