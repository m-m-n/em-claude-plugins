"""Cross-hook tests for em-workflow/hooks/queue_failure_net.py: fixtures
that drive it together with queue_launch_guard.py and queue_taskstop_net.py.

Covers task0001's (subagentstop-failed-event) Acceptance Criteria that run
another hook alongside queue_failure_net.py: AC-3's recorder comparison
(agent-index fallback parity with queue_taskstop_net.py's find_task_identity),
AC-4's parser parity with queue_launch_guard.py, AC-5's concurrency across
both nets, and AC-8's retry-path interop. Test names reference the AC they
exercise. See feature-docs/subagentstop-failed-event/tasks/task0001.md.

This module duplicates the fixture helpers it needs (Test Notes) rather than
importing tests/test_queue_failure_net.py or tests/test_queue_taskstop_net.py
-- no test module in this suite imports another.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FAILURE_NET_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_failure_net.py"
TASKSTOP_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_taskstop_net.py"
LAUNCH_GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_launch_guard.py"

FAILURE_NET_IMPLEMENTER_TYPE = "em-workflow:implementer"


def run_hook(stdin_text, hook_path, timeout=10):
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_hook_json(payload, hook_path, timeout=10):
    return run_hook(json.dumps(payload), hook_path, timeout=timeout)


def failure_net_assignment_block(task_id, worktree_path):
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


def failure_net_write_transcript(tmp_dir, name, first_user_text):
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


def failure_net_payload(agent_type, transcript_path):
    return {
        "session_id": "sess-1",
        "transcript_path": "/nonexistent/main-session.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "agent_id": "agent-1",
        "last_assistant_message": "done",
        "agent_type": agent_type,
        "agent_transcript_path": transcript_path,
    }


def read_journal_entries(journal_path):
    if not os.path.isfile(journal_path):
        return []
    with open(journal_path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QueueFailureNetCrossHookTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)


class TestOnlyPostHeaderTaskIsMarkedFailed(QueueFailureNetCrossHookTestCase):
    """AC-4: a prompt with `task_id: task0099` and a worktree-path line
    BEFORE the header, and a real task after it, leads to a `failed` line
    for the post-header task only."""

    def test_only_post_header_task_is_marked_failed(self):
        feature = "demo"
        fake_task = "task0099"
        real_task = "task0410"
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        real_worktree = os.path.join(feature_dir, real_task)
        os.makedirs(real_worktree, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"event": "launched", "task": real_task, "at": "2026-01-01T00:00:00+00:00"})
                + "\n"
            )

        prompt = (
            f"task_id: {fake_task}\n"
            f"worktree_path: /somewhere/{fake_task}\n"
            "# Task assignment\n"
            f"task_id: {real_task}\n"
            f"worktree_path: {real_worktree}\n"
        )
        transcript_path = failure_net_write_transcript(self.tmp_dir, "agent.jsonl", prompt)
        payload = failure_net_payload(FAILURE_NET_IMPLEMENTER_TYPE, transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload, FAILURE_NET_PATH)

        self.assertEqual(result.returncode, 0)
        entries = read_journal_entries(journal_path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["task"], real_task)
        self.assertEqual(entries[-1]["event"], "failed")
        self.assertNotIn(fake_task, [e["task"] for e in entries])


class TestParserParity(unittest.TestCase):
    """AC-4: this hook's extract_task_assignment returns exactly what
    queue_launch_guard.py's does, for at least 8 prompt fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.failure_net = _load_module_from_path(
            "failure_net_parity_target", str(FAILURE_NET_PATH)
        )
        cls.launch_guard = _load_module_from_path(
            "launch_guard_parity_target", str(LAUNCH_GUARD_PATH)
        )

    FIXTURES = {
        "no_header": "task_id: task0001\nworktree_path: /a/b\n",
        "header_with_both_lines": "# Task assignment\ntask_id: task0002\nworktree_path: /a/b\n",
        "both_lines_only_before_header": "task_id: task0003\nworktree_path: /a/b\n# Task assignment\n",
        "lines_before_and_after_header": (
            "task_id: task0004\nworktree_path: /before\n"
            "# Task assignment\ntask_id: task0005\nworktree_path: /after\n"
        ),
        "header_with_trailing_whitespace": "# Task assignment   \ntask_id: task0006\nworktree_path: /a/b\n",
        "header_without_space_after_hash": "#Task assignment\ntask_id: task0007\nworktree_path: /a/b\n",
        "worktree_path_with_spaces": (
            "# Task assignment\ntask_id: task0008\nworktree_path: /a dir/with spaces/task0008\n"
        ),
        "missing_worktree_path_line": "# Task assignment\ntask_id: task0009\n",
        "two_headers": (
            "# Task assignment\ntask_id: task0010\nworktree_path: /first\n"
            "# Task assignment\ntask_id: task0011\nworktree_path: /second\n"
        ),
        "carriage_return_line_endings": "# Task assignment\r\ntask_id: task0012\r\nworktree_path: /a/b\r\n",
        "non_string_input": 12345,
    }

    def test_parser_returns_the_same_values_as_launch_guard(self):
        for name, prompt in self.FIXTURES.items():
            with self.subTest(fixture=name):
                failure_net_result = self.failure_net.extract_task_assignment(prompt)
                launch_guard_result = self.launch_guard.extract_task_assignment(prompt)
                self.assertEqual(failure_net_result, launch_guard_result)


class TestFailureNetAndLaunchGuardAgreeOnTaskId(QueueFailureNetCrossHookTestCase):
    """AC-4: queue_launch_guard.py, given the same prompt, appends
    `launched` for the same task id this hook marked `failed`."""

    def test_launch_guard_launches_the_same_task_this_hook_failed(self):
        feature = "demo"
        task_id = "task0420"
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        worktree_path = os.path.join(feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"})
                + "\n"
            )

        prompt = f"# Task assignment\ntask_id: {task_id}\nworktree_path: {worktree_path}\n"
        transcript_path = failure_net_write_transcript(self.tmp_dir, "agent.jsonl", prompt)
        payload = failure_net_payload(FAILURE_NET_IMPLEMENTER_TYPE, transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload, FAILURE_NET_PATH)
        self.assertEqual(result.returncode, 0)
        entries = read_journal_entries(journal_path)
        self.assertEqual(entries[-1]["event"], "failed")

        launch_payload = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "em-workflow:implementer", "prompt": prompt},
        }
        guard_result = run_hook_json(launch_payload, LAUNCH_GUARD_PATH)
        self.assertEqual(guard_result.returncode, 0)
        self.assertEqual(guard_result.stdout, "")  # no deny decision

        entries = read_journal_entries(journal_path)
        self.assertEqual(entries[-1]["event"], "launched")
        self.assertEqual(entries[-1]["task"], task_id)


class TestAgentIndexFallbackMatchesTaskStopRecorder(unittest.TestCase):
    """AC-3: for identical fixtures, this hook's agent-index fallback and
    queue_taskstop_net.py produce the same journal change (same events for
    the same tasks) -- `at` and `reason` values differ by design."""

    def setUp(self):
        self._tmp_a = tempfile.TemporaryDirectory()
        self._tmp_b = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_a.cleanup)
        self.addCleanup(self._tmp_b.cleanup)

    def _events_by_task(self, journal_path):
        by_task = {}
        for entry in read_journal_entries(journal_path):
            by_task.setdefault(entry["task"], []).append(entry["event"])
        return by_task

    def _run_both(self, build_fn, identifier):
        journal_a = build_fn(self._tmp_a.name)
        journal_b = build_fn(self._tmp_b.name)

        failure_net_stop_payload = {
            "session_id": "sess-1",
            "cwd": self._tmp_a.name,
            "hook_event_name": "SubagentStop",
            "agent_id": identifier,
            "last_assistant_message": "done",
        }
        result_a = run_hook_json(failure_net_stop_payload, FAILURE_NET_PATH)
        self.assertEqual(result_a.returncode, 0)

        taskstop_payload = {
            "session_id": "sess-1",
            "cwd": self._tmp_b.name,
            "hook_event_name": "PostToolUse",
            "tool_name": "TaskStop",
            "tool_input": {"task_id": identifier},
            "tool_response": {},
        }
        result_b = run_hook_json(taskstop_payload, TASKSTOP_PATH)
        self.assertEqual(result_b.returncode, 0)

        return self._events_by_task(journal_a), self._events_by_task(journal_b)

    def test_successful_match_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            worktree_path = os.path.join(feature_dir, "task0430")
            os.makedirs(worktree_path, exist_ok=True)
            journal_path = os.path.join(feature_dir, "journal.jsonl")
            with open(journal_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"event": "launched", "task": "task0430", "at": "2026-01-01T00:00:00+00:00"})
                    + "\n"
                )
            index_path = os.path.join(feature_dir, "agents.jsonl")
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "agent_id": "agent-x",
                            "task": "task0430",
                            "worktree_path": worktree_path,
                            "at": "2026-01-01T00:00:00+00:00",
                        }
                    )
                    + "\n"
                )
            return journal_path

        by_task_a, by_task_b = self._run_both(build, "agent-x")
        self.assertEqual(by_task_a, by_task_b)
        self.assertEqual(by_task_a["task0430"][-1], "failed")

    def test_ambiguous_identifier_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            w1 = os.path.join(feature_dir, "task0431")
            w2 = os.path.join(feature_dir, "task0432")
            os.makedirs(w1, exist_ok=True)
            os.makedirs(w2, exist_ok=True)
            journal_path = os.path.join(feature_dir, "journal.jsonl")
            with open(journal_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": "launched", "task": "task0431", "at": "2026-01-01T00:00:00+00:00"}) + "\n")
                fh.write(json.dumps({"event": "launched", "task": "task0432", "at": "2026-01-01T00:00:01+00:00"}) + "\n")
            index_path = os.path.join(feature_dir, "agents.jsonl")
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"agent_id": "agent-ambiguous", "task": "task0431", "worktree_path": w1, "at": "2026-01-01T00:00:00+00:00"})
                    + "\n"
                )
                fh.write(
                    json.dumps({"agent_id": "agent-ambiguous", "task": "task0432", "worktree_path": w2, "at": "2026-01-01T00:00:02+00:00"})
                    + "\n"
                )
            return journal_path

        by_task_a, by_task_b = self._run_both(build, "agent-ambiguous")
        self.assertEqual(by_task_a, by_task_b)
        self.assertEqual(by_task_a["task0431"], ["launched"])
        self.assertEqual(by_task_a["task0432"], ["launched"])

    def test_stale_identifier_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            worktree_path = os.path.join(feature_dir, "task0433")
            os.makedirs(worktree_path, exist_ok=True)
            journal_path = os.path.join(feature_dir, "journal.jsonl")
            with open(journal_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": "launched", "task": "task0433", "at": "2026-01-01T00:10:00+00:00"}) + "\n")
            index_path = os.path.join(feature_dir, "agents.jsonl")
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"agent_id": "agent-early", "task": "task0433", "worktree_path": worktree_path, "at": "2026-01-01T00:00:00+00:00"})
                    + "\n"
                )
                fh.write(
                    json.dumps({"agent_id": "agent-late", "task": "task0433", "worktree_path": worktree_path, "at": "2026-01-01T00:10:00+00:00"})
                    + "\n"
                )
            return journal_path

        by_task_a, by_task_b = self._run_both(build, "agent-early")
        self.assertEqual(by_task_a, by_task_b)
        self.assertEqual(by_task_a["task0433"], ["launched"])  # stale match, unaffected

    def test_worktree_outside_feature_directory_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            os.makedirs(feature_dir, exist_ok=True)
            outside_worktree = os.path.join(root, "task0434")
            index_path = os.path.join(feature_dir, "agents.jsonl")
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"agent_id": "agent-outside", "task": "task0434", "worktree_path": outside_worktree, "at": "2026-01-01T00:00:00+00:00"})
                    + "\n"
                )
            return os.path.join(feature_dir, "journal.jsonl")

        by_task_a, by_task_b = self._run_both(build, "agent-outside")
        self.assertEqual(by_task_a, {})
        self.assertEqual(by_task_b, {})

    def test_oversized_candidate_list_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            worktree_path = os.path.join(feature_dir, "task0435")
            os.makedirs(worktree_path, exist_ok=True)
            journal_path = os.path.join(feature_dir, "journal.jsonl")
            with open(journal_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": "launched", "task": "task0435", "at": "2026-01-01T00:00:00+00:00"}) + "\n")
            index_path = os.path.join(feature_dir, "agents.jsonl")
            entry = {
                "agent_id": "agent-primary",
                "agent_ids": ["agent-primary", "id-2", "id-3", "id-4", "id-5", "agent-target"],
                "task": "task0435",
                "worktree_path": worktree_path,
                "at": "2026-01-01T00:00:00+00:00",
            }
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
            return journal_path

        by_task_a, by_task_b = self._run_both(build, "agent-target")
        self.assertEqual(by_task_a, by_task_b)
        self.assertEqual(by_task_a["task0435"], ["launched"])

    def test_no_matching_entry_produces_same_journal_change(self):
        def build(root):
            feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", "demo")
            worktree_path = os.path.join(feature_dir, "task0436")
            os.makedirs(worktree_path, exist_ok=True)
            journal_path = os.path.join(feature_dir, "journal.jsonl")
            with open(journal_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": "launched", "task": "task0436", "at": "2026-01-01T00:00:00+00:00"}) + "\n")
            index_path = os.path.join(feature_dir, "agents.jsonl")
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"agent_id": "agent-somebody-else", "task": "task0436", "worktree_path": worktree_path, "at": "2026-01-01T00:00:00+00:00"})
                    + "\n"
                )
            return journal_path

        by_task_a, by_task_b = self._run_both(build, "agent-nomatch")
        self.assertEqual(by_task_a, by_task_b)
        self.assertEqual(by_task_a["task0436"], ["launched"])


class TestConcurrentBothHooksLeaveExactlyOneFailedLine(unittest.TestCase):
    """AC-5: concurrently started queue_failure_net.py and
    queue_taskstop_net.py subprocesses (at least five of each) for the same
    `launched` task leave exactly one `failed` line for that task, and
    every journal line parses as JSON."""

    def test_concurrent_rounds_leave_exactly_one_failed_line(self):
        for round_no in range(3):
            with self.subTest(round=round_no):
                self._run_round(round_no)

    def _run_round(self, round_no):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        feature = "demo"
        task_id = f"task05{round_no:02d}"
        feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", feature)
        worktree_path = os.path.join(feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}) + "\n")
        index_path = os.path.join(feature_dir, "agents.jsonl")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"agent_id": "agent-shared", "task": task_id, "worktree_path": worktree_path, "at": "2026-01-01T00:00:00+00:00"})
                + "\n"
            )

        failure_net_stop_payload = {
            "session_id": "sess-1",
            "cwd": root,
            "hook_event_name": "SubagentStop",
            "agent_id": "agent-shared",
        }
        taskstop_payload = {
            "session_id": "sess-1",
            "cwd": root,
            "hook_event_name": "PostToolUse",
            "tool_name": "TaskStop",
            "tool_input": {"task_id": "agent-shared"},
        }

        results = []

        def invoke(hook_path, payload):
            results.append(run_hook_json(payload, hook_path))

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=invoke, args=(FAILURE_NET_PATH, failure_net_stop_payload)))
            threads.append(threading.Thread(target=invoke, args=(TASKSTOP_PATH, taskstop_payload)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual(result.returncode, 0)

        entries = []
        with open(journal_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    entries.append(json.loads(line))  # every line must parse -- no torn writes

        failed_lines = [e for e in entries if e.get("task") == task_id and e.get("event") == "failed"]
        self.assertEqual(len(failed_lines), 1)


class TestSymlinkedJournalDuringFailureNetInvocation(QueueFailureNetCrossHookTestCase):
    """AC-5: a symlinked journal path is refused by queue_failure_net.py --
    link target never written, exit code 0."""

    def test_failure_net_refuses_symlinked_journal(self):
        feature = "demo"
        task_id = "task0510"
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        worktree_path = os.path.join(feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        outside_target = os.path.join(self.tmp_dir, "outside.jsonl")
        self.assertFalse(os.path.isfile(outside_target))
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        os.symlink(outside_target, journal_path)

        prompt = f"# Task assignment\ntask_id: {task_id}\nworktree_path: {worktree_path}\n"
        transcript_path = failure_net_write_transcript(self.tmp_dir, "agent.jsonl", prompt)
        payload = failure_net_payload(FAILURE_NET_IMPLEMENTER_TYPE, transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload, FAILURE_NET_PATH)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isfile(outside_target))


class TestBothWritersLeaveExactlyOneFailedLineBothOrders(QueueFailureNetCrossHookTestCase):
    """AC-8: after this hook appends `failed` for a task whose last event
    was `launched` (agent_type `implementer`), queue_launch_guard.py given
    an `em-workflow:implementer` launch with the same assignment exits 0
    with no deny output, and the journal's last line is a new `launched`
    event for that task -- the retry path this feature exists to unblock."""

    def test_retry_after_failure_net_records_failure_is_allowed(self):
        feature = "demo"
        task_id = "task0520"
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        worktree_path = os.path.join(feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        with open(journal_path, "w", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"})
                + "\n"
            )

        prompt = f"# Task assignment\ntask_id: {task_id}\nworktree_path: {worktree_path}\n"
        transcript_path = failure_net_write_transcript(self.tmp_dir, "agent.jsonl", prompt)
        payload = failure_net_payload("implementer", transcript_path)
        payload["cwd"] = self.tmp_dir

        stop_result = run_hook_json(payload, FAILURE_NET_PATH)
        self.assertEqual(stop_result.returncode, 0)
        entries = read_journal_entries(journal_path)
        self.assertEqual(entries[-1]["event"], "failed")
        self.assertEqual(entries[-1]["task"], task_id)

        launch_payload = {
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "em-workflow:implementer", "prompt": prompt},
        }
        guard_result = run_hook_json(launch_payload, LAUNCH_GUARD_PATH)

        self.assertEqual(guard_result.returncode, 0)
        self.assertEqual(guard_result.stdout, "")  # no deny decision
        entries = read_journal_entries(journal_path)
        self.assertEqual(entries[-1]["event"], "launched")
        self.assertEqual(entries[-1]["task"], task_id)


if __name__ == "__main__":
    unittest.main()
