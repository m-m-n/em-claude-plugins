"""Subprocess-driven tests for em-workflow/hooks/queue_failure_net.py.

Covers task0004's Acceptance Criteria (see
feature-docs/implement-phase-queue/tasks/task0004.md); test names reference
the AC they exercise. The hook is invoked exactly as Claude Code would invoke
it: JSON on stdin, decisions read from exit code / journal side-effects.
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_failure_net.py"

IMPLEMENTER_TYPE = "em-workflow:implementer"
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def run_hook(stdin_text, timeout=10):
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_hook_json(payload, timeout=10):
    return run_hook(json.dumps(payload), timeout=timeout)


def read_journal_lines(journal_path):
    if not os.path.isfile(journal_path):
        return []
    with open(journal_path, encoding="utf-8") as fh:
        return [line for line in fh if line.strip()]


def make_worktree(tmp_dir, feature, task_id):
    """Create .claude/worktrees/em-workflow/{feature}/{task_id}.

    Returns (worktree_path, journal_path) — journal_path is the sibling
    journal.jsonl per the Journal contract (dirname(worktree_path)/journal.jsonl).
    """
    feature_dir = os.path.join(tmp_dir, ".claude", "worktrees", "em-workflow", feature)
    worktree_path = os.path.join(feature_dir, task_id)
    os.makedirs(worktree_path, exist_ok=True)
    journal_path = os.path.join(feature_dir, "journal.jsonl")
    return worktree_path, journal_path


def write_journal(journal_path, lines):
    """lines: list of dicts (JSON entries) OR raw strings (used verbatim, for malformed-line tests)."""
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line) + "\n")


def assignment_block(task_id, worktree_path):
    return (
        "# Task assignment\n"
        f"task_id: {task_id}\n"
        f"worktree_path: {worktree_path}\n"
        "task_plan_path: /repo/feature-docs/demo/tasks/{task_id}.md\n"
        "implementation_md_path: /repo/feature-docs/demo/IMPLEMENTATION.md\n"
        "parent_branch: em-workflow/demo/integration\n"
        "merge_script: /repo/em-workflow/scripts/merge-task.sh\n"
        "skills_to_load: []\n"
        "project_commands:\n"
        '  build: ""\n'
        '  test: ""\n'
        '  format: ""\n'
        "expected_files: []\n"
    )


def write_transcript(tmp_dir, name, first_user_text):
    """Minimal JSONL transcript fixture whose first user-role entry carries
    first_user_text as its message content (matches the real Claude Code
    transcript shape: {"type": "user", "message": {"role": "user", "content": ...}})."""
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"type": "user", "message": {"role": "user", "content": first_user_text}})
            + "\n"
        )
        fh.write(
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "ok"}})
            + "\n"
        )
    return path


def base_payload(agent_type=None, transcript_path=None):
    payload = {
        "session_id": "sess-1",
        "transcript_path": "/nonexistent/main-session.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "agent_id": "agent-1",
        "last_assistant_message": "done",
    }
    if agent_type is not None:
        payload["agent_type"] = agent_type
    if transcript_path is not None:
        payload["agent_transcript_path"] = transcript_path
    return payload


class QueueFailureNetTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)


class TestLaunchedAppendsFailed(QueueFailureNetTestCase):
    """AC-1: last event `launched` -> exactly one well-formed `failed` line."""

    def test_launched_last_event_via_agent_type_appends_failed(self):
        feature, task_id = "demo", "task0007"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), task_id)
        self.assertTrue(isinstance(appended.get("reason"), str) and appended["reason"])
        self.assertTrue(
            RFC3339_RE.match(appended.get("at", "")),
            f"'at' not RFC3339-with-offset: {appended.get('at')!r}",
        )

    def test_launched_last_event_via_transcript_prompt_appends_failed(self):
        """Identity discovered purely by scanning the transcript's first user
        message (no agent_type field at all) — the other identity source."""
        feature, task_id = "demo", "task0009"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), task_id)

    def test_no_prior_event_for_task_appends_failed(self):
        """"no event" branch of AC-1: journal exists (other tasks) but has no
        line at all for this task -> treated the same as `launched`."""
        feature, task_id = "demo", "task0011"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "merged", "task": "task0001", "at": "2026-01-01T00:00:00+00:00", "commit": "abc123"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), task_id)

    def test_journal_file_absent_but_directory_present_appends_failed(self):
        """No journal.jsonl file yet (directory exists) -> "no event" -> append,
        creating the file."""
        feature, task_id = "demo", "task0013"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        self.assertFalse(os.path.isfile(journal_path))
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 1)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")

    def test_retry_then_relaunch_last_event_launched_appends_failed(self):
        """failed -> launched sequence: LAST event (launched) governs, not the
        earlier failed — a retried task stopping again still gets recorded."""
        feature, task_id = "demo", "task0015"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "failed", "task": task_id, "at": "2026-01-01T00:05:00+00:00", "reason": "x"},
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:10:00+00:00"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 4)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")

    def test_malformed_journal_line_between_valid_lines_is_skipped(self):
        """Test Notes: cover the malformed-journal-line skip during replay —
        a garbage line must not flip the derived last event."""
        feature, task_id = "demo", "task0017"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                "{ this is not valid json ]]",
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 3)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), task_id)


class TestMergedAppendsNothing(QueueFailureNetTestCase):
    """AC-2: last event `merged` -> appends nothing."""

    def test_merged_last_event_appends_nothing(self):
        feature, task_id = "demo", "task0020"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-01T01:00:00+00:00", "commit": "deadbeef"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)

    def test_malformed_journal_line_before_merged_still_appends_nothing(self):
        """A malformed line sitting BEFORE the true last (`merged`) event must
        not be mistaken for the last event either."""
        feature, task_id = "demo", "task0021"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                "not json at all {{{",
                {"event": "merged", "task": task_id, "at": "2026-01-01T01:00:00+00:00", "commit": "cafef00d"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 3)


class TestFailedAppendsNothing(QueueFailureNetTestCase):
    """AC-3: last event already `failed` -> appends nothing (no duplicates)."""

    def test_failed_last_event_appends_nothing(self):
        feature, task_id = "demo", "task0025"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "failed", "task": task_id, "at": "2026-01-01T00:05:00+00:00", "reason": "prior failure"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)


class TestNonImplementerStopsIgnored(QueueFailureNetTestCase):
    """AC-4: non-implementer subagent stops -> append nothing, exit 0."""

    def test_different_agent_type_appends_nothing_even_with_assignment_block(self):
        """agent_type field, when present, is authoritative: a different type
        must be ignored even if the transcript happens to contain a
        Task-assignment-shaped block."""
        feature, task_id = "demo", "task0030"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type="Explore", transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 1)

    def test_no_task_assignment_block_appends_nothing(self):
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", "Please review this PR and summarize findings."
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class TestFailOpen(QueueFailureNetTestCase):
    """AC-5 / AC-6: unexpected input/state never crashes and never blocks."""

    def test_malformed_stdin_exits_zero_no_crash(self):
        result = run_hook("not json at all {{{")
        self.assertEqual(result.returncode, 0)

    def test_empty_stdin_exits_zero(self):
        result = run_hook("")
        self.assertEqual(result.returncode, 0)

    def test_json_array_stdin_exits_zero(self):
        result = run_hook("[1, 2, 3]")
        self.assertEqual(result.returncode, 0)

    def test_json_null_stdin_exits_zero(self):
        result = run_hook("null")
        self.assertEqual(result.returncode, 0)

    def test_missing_transcript_file_exits_zero_no_append(self):
        feature, task_id = "demo", "task0040"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        missing_transcript = os.path.join(self.tmp_dir, "does-not-exist.jsonl")
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=missing_transcript)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 1)

    def test_no_transcript_field_at_all_exits_zero(self):
        payload = base_payload(agent_type=None, transcript_path=None)
        result = run_hook_json(payload)
        self.assertEqual(result.returncode, 0)

    def test_invalid_task_id_exits_zero_no_append(self):
        feature, task_id = "demo", "task0050"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        bad_block = assignment_block(task_id, worktree_path).replace(
            f"task_id: {task_id}", "task_id: not-a-valid-id"
        )
        transcript_path = write_transcript(self.tmp_dir, "agent.jsonl", bad_block)
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 0)

    def test_relative_worktree_path_exits_zero_no_append(self):
        feature, task_id = "demo", "task0055"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        bad_block = assignment_block(task_id, worktree_path).replace(
            f"worktree_path: {worktree_path}", "worktree_path: relative/path/task0055"
        )
        transcript_path = write_transcript(self.tmp_dir, "agent.jsonl", bad_block)
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 0)

    def test_absent_journal_directory_exits_zero_no_crash(self):
        """worktree_path is well-formed but its parent directory never
        existed on disk at all -> exit 0, nothing created."""
        feature, task_id = "demo", "task0060"
        never_created_worktree = os.path.join(
            self.tmp_dir, ".claude", "worktrees", "em-workflow", feature, task_id
        )
        journal_path = os.path.join(
            self.tmp_dir, ".claude", "worktrees", "em-workflow", feature, "journal.jsonl"
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, never_created_worktree)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isfile(journal_path))
        self.assertFalse(os.path.isdir(os.path.dirname(journal_path)))

    def test_malformed_transcript_jsonl_exits_zero(self):
        path = os.path.join(self.tmp_dir, "broken.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json\n")
            fh.write("{also not json\n")
        payload = base_payload(agent_type=None, transcript_path=path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)

    def test_exit_code_always_zero_across_edge_payloads(self):
        """AC-6 sweep: whatever the input shape, the hook never blocks."""
        edge_inputs = [
            "",
            "   \n\t",
            "{}",
            "true",
            '"just a string"',
            "42",
            json.dumps({"agent_type": IMPLEMENTER_TYPE}),
            json.dumps({"agent_type": IMPLEMENTER_TYPE, "agent_transcript_path": 12345}),
            json.dumps({"agent_transcript_path": None}),
        ]
        for stdin_text in edge_inputs:
            with self.subTest(stdin=stdin_text):
                result = run_hook(stdin_text)
                self.assertEqual(result.returncode, 0)


class TestStdlibOnly(unittest.TestCase):
    """AC-7: the script imports only Python stdlib modules."""

    def test_only_stdlib_imports(self):
        source = HOOK_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(HOOK_PATH))
        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported.add(node.module.split(".")[0])
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


class TestConcurrentAppends(QueueFailureNetTestCase):
    """NFR2: concurrent journal appends must not corrupt the file (flock)."""

    def test_concurrent_invocations_do_not_corrupt_journal(self):
        feature = "demo"
        task_ids = [f"task{n:04d}" for n in range(60, 66)]
        journal_path = None
        payloads = []
        for task_id in task_ids:
            worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
            transcript_path = write_transcript(
                self.tmp_dir, f"agent-{task_id}.jsonl", assignment_block(task_id, worktree_path)
            )
            payloads.append(base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path))

        results = [None] * len(payloads)

        def invoke(index, payload):
            results[index] = run_hook_json(payload)

        threads = [
            threading.Thread(target=invoke, args=(i, payload)) for i, payload in enumerate(payloads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        for result in results:
            self.assertIsNotNone(result)
            self.assertEqual(result.returncode, 0)

        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), len(task_ids))
        seen_tasks = set()
        for line in lines:
            entry = json.loads(line)  # every line must parse — no torn writes
            self.assertEqual(entry.get("event"), "failed")
            seen_tasks.add(entry.get("task"))
        self.assertEqual(seen_tasks, set(task_ids))


class TestWorktreePathWithSpaces(QueueFailureNetTestCase):
    """Review round 1 regression: a valid absolute worktree path containing
    spaces must not evade failure recording (parser parity with
    queue_launch_guard.py)."""

    def test_spaced_worktree_path_appends_failed(self):
        feature_dir = os.path.join(
            self.tmp_dir, "dir with spaces", ".claude", "worktrees",
            "em-workflow", "demo-feature",
        )
        worktree_path = os.path.join(feature_dir, "task0001")
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(journal_path, [
            {"event": "launched", "task": "task0001", "at": "2026-07-15T09:00:00+09:00"},
        ])

        transcript = write_transcript(
            self.tmp_dir, "sub.jsonl", assignment_block("task0001", worktree_path)
        )
        payload = base_payload(
            agent_type="em-workflow:implementer", transcript_path=transcript
        )

        proc = run_hook_json(payload)

        self.assertEqual(proc.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended["event"], "failed")
        self.assertEqual(appended["task"], "task0001")


if __name__ == "__main__":
    unittest.main()
