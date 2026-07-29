"""Subprocess-driven tests for em-workflow/hooks/queue_taskstop_net.py.

Covers task0002's Acceptance Criteria (see
feature-docs/taskstop-journal-failed-event/tasks/task0002.md); test names
reference the AC they exercise. The hook is invoked exactly as Claude Code
would invoke it: JSON on stdin, decisions read from exit code / journal
side-effects.
"""

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
HOOK_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_taskstop_net.py"
LAUNCH_GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_launch_guard.py"
FAILURE_NET_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_failure_net.py"

STOP_TOOL_NAME = "TaskStop"
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def run_hook(stdin_text, hook_path=HOOK_PATH, timeout=10):
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_hook_json(payload, hook_path=HOOK_PATH, timeout=10):
    return run_hook(json.dumps(payload), hook_path=hook_path, timeout=timeout)


def failure_net_reason_constant():
    """The reason string queue_failure_net.py writes -- read from its own
    source rather than hardcoded, so this test cannot silently pass if that
    constant changes (Test Notes)."""
    source = FAILURE_NET_PATH.read_text(encoding="utf-8")
    match = re.search(r'^FAILED_REASON\s*=\s*"([^"]*)"', source, re.MULTILINE)
    assert match, "queue_failure_net.py FAILED_REASON constant not found"
    return match.group(1)


def read_journal_lines(journal_path):
    if not os.path.isfile(journal_path):
        return []
    with open(journal_path, encoding="utf-8") as fh:
        return [line for line in fh if line.strip()]


def make_feature(root, feature):
    """Create <root>/.claude/worktrees/em-workflow/<feature>/ and return its
    path (the directory that holds journal.jsonl and agents.jsonl)."""
    feature_dir = os.path.join(root, ".claude", "worktrees", "em-workflow", feature)
    os.makedirs(feature_dir, exist_ok=True)
    return feature_dir


def make_worktree(feature_dir, task_id, create=True):
    worktree_path = os.path.join(feature_dir, task_id)
    if create:
        os.makedirs(worktree_path, exist_ok=True)
    return worktree_path


def write_journal(feature_dir, lines):
    """lines: list of dicts (JSON entries) OR raw strings (verbatim, for
    malformed-line tests)."""
    journal_path = os.path.join(feature_dir, "journal.jsonl")
    with open(journal_path, "w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line) + "\n")
    return journal_path


def write_agent_index(feature_dir, entries):
    """entries: list of dicts OR raw strings (verbatim, for malformed-line
    tests). Written to <feature_dir>/agents.jsonl."""
    index_path = os.path.join(feature_dir, "agents.jsonl")
    with open(index_path, "w", encoding="utf-8") as fh:
        for entry in entries:
            if isinstance(entry, str):
                fh.write(entry + "\n")
            else:
                fh.write(json.dumps(entry) + "\n")
    return index_path


def index_entry(agent_id, task_id, worktree_path, at="2026-01-01T00:00:00+00:00", key="agent_id"):
    return {key: agent_id, "task_id": task_id, "worktree_path": worktree_path, "at": at}


def stop_payload(cwd, input_id=None, result_id=None, tool_name=STOP_TOOL_NAME):
    payload = {
        "session_id": "sess-1",
        "transcript_path": "/nonexistent/main-session.jsonl",
        "cwd": cwd,
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {},
        "tool_response": {},
    }
    if input_id is not None:
        payload["tool_input"]["task_id"] = input_id
    if result_id is not None:
        payload["tool_response"]["task_id"] = result_id
    return payload


class QueueTaskStopNetTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)


class TestLaunchedAppendsFailed(QueueTaskStopNetTestCase):
    """AC-1: last event `launched` -> exactly one well-formed `failed` line."""

    def test_launched_last_event_appends_failed(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0001")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0001", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-abc", "task0001", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-abc")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), "task0001")
        self.assertTrue(isinstance(appended.get("reason"), str) and appended["reason"])
        self.assertTrue(
            RFC3339_RE.match(appended.get("at", "")),
            f"'at' not RFC3339-with-offset: {appended.get('at')!r}",
        )

    def test_no_prior_event_for_task_appends_failed(self):
        """"no event" branch of AC-1: journal has no line at all for this
        task -> treated the same as `launched`."""
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0002")
        write_journal(
            feature_dir,
            [{"event": "merged", "task": "task0001", "at": "2026-01-01T00:00:00+00:00", "commit": "abc"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-def", "task0002", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-def")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), "task0002")

    def test_journal_file_absent_but_directory_present_appends_failed(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0003")
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        self.assertFalse(os.path.isfile(journal_path))
        write_agent_index(feature_dir, [index_entry("agent-ghi", "task0003", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-ghi")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]).get("event"), "failed")

    def test_walk_up_from_nested_cwd_finds_worktrees_root(self):
        """The search root is found by walking UP from cwd -- exercise a cwd
        several levels below the em-workflow worktrees directory itself."""
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0004")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0004", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-jkl", "task0004", worktree_path)])
        nested_cwd = os.path.join(worktree_path, "em-workflow", "hooks")
        os.makedirs(nested_cwd, exist_ok=True)
        payload = stop_payload(nested_cwd, input_id="agent-jkl")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")

    def test_agent_id_camel_case_key_is_also_accepted(self):
        """Defensive tolerance for the agent index's harness-identifier key
        spelling (IMPLEMENTATION.md leaves the exact key name unspecified)."""
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0005")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0005", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir, [index_entry("agent-mno", "task0005", worktree_path, key="agentId")]
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-mno")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")


class TestReasonStringDistinctFromFailureNet(QueueTaskStopNetTestCase):
    """AC-2: the appended reason must differ from queue_failure_net.py's."""

    def test_reason_differs_from_subagent_stop_net_reason(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0006")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0006", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-pqr", "task0006", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-pqr")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        appended = json.loads(lines[-1])
        self.assertNotEqual(appended.get("reason"), failure_net_reason_constant())


class TestTerminalEventsAppendNothing(QueueTaskStopNetTestCase):
    """AC-3: last event `merged` or `failed` -> nothing appended (idempotency)."""

    def test_merged_last_event_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0007")
        write_journal(
            feature_dir,
            [
                {"event": "launched", "task": "task0007", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "merged", "task": "task0007", "at": "2026-01-01T01:00:00+00:00", "commit": "abc"},
            ],
        )
        write_agent_index(feature_dir, [index_entry("agent-stu", "task0007", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-stu")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)

    def test_failed_last_event_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0008")
        write_journal(
            feature_dir,
            [
                {"event": "launched", "task": "task0008", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "failed", "task": "task0008", "at": "2026-01-01T00:05:00+00:00", "reason": "x"},
            ],
        )
        write_agent_index(feature_dir, [index_entry("agent-vwx", "task0008", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-vwx")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)


class TestNoAgentIndexMatch(QueueTaskStopNetTestCase):
    """AC-4: unresolvable agent identifier -> nothing appended, exit 0."""

    def test_identifier_absent_from_agent_index_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0009")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0009", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-yzz", "task0009", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-does-not-exist")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)

    def test_no_agent_index_file_at_all_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0010", "at": "2026-01-01T00:00:00+00:00"}],
        )
        index_path = os.path.join(feature_dir, "agents.jsonl")
        self.assertFalse(os.path.isfile(index_path))
        payload = stop_payload(self.tmp_dir, input_id="agent-anything")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)

    def test_no_em_workflow_worktrees_ancestor_appends_nothing(self):
        # tmp_dir has no .claude/worktrees/em-workflow anywhere above it.
        payload = stop_payload(self.tmp_dir, input_id="agent-anything")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class TestInvalidIndexEntry(QueueTaskStopNetTestCase):
    """AC-5: invalid task id / relative or `..`-containing worktree path in
    the matched index entry -> nothing appended, exit 0."""

    def test_invalid_task_id_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0011")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0011", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir, [index_entry("agent-bad1", "not-a-valid-id", worktree_path)]
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-bad1")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)

    def test_relative_worktree_path_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0012", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir, [index_entry("agent-bad2", "task0012", "relative/path/task0012")]
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-bad2")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)

    def test_dotdot_worktree_path_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0013", "at": "2026-01-01T00:00:00+00:00"}],
        )
        evil_path = os.path.join(feature_dir, "..", "task0013")
        write_agent_index(feature_dir, [index_entry("agent-bad3", "task0013", evil_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-bad3")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)


class TestAbsentJournalDirectory(QueueTaskStopNetTestCase):
    """AC-6: derived journal directory absent -> nothing appended, no file
    or directory created, exit 0."""

    def test_absent_journal_directory_exits_zero_no_crash(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        # A stale index entry whose worktree_path lives under a DIFFERENT,
        # never-created feature directory -- agents.jsonl itself lives in
        # feature_dir (which does exist), but the journal directory the
        # hook independently derives from the entry's worktree_path must
        # not be fabricated just because the index happened to be found.
        stale_journal_dir = os.path.join(
            self.tmp_dir, ".claude", "worktrees", "em-workflow", "never-created-feature"
        )
        never_created_worktree = os.path.join(stale_journal_dir, "task0014")
        self.assertFalse(os.path.isdir(stale_journal_dir))
        write_agent_index(
            feature_dir, [index_entry("agent-bad4", "task0014", never_created_worktree)]
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-bad4")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isdir(stale_journal_dir))
        stale_journal_path = os.path.join(stale_journal_dir, "journal.jsonl")
        self.assertFalse(os.path.isfile(stale_journal_path))


class TestFailOpenOnBadInput(QueueTaskStopNetTestCase):
    """AC-7: malformed stdin JSON and a different tool name -> exit 0, no
    output, no journal write."""

    def test_malformed_stdin_exits_zero_no_crash(self):
        result = run_hook("not json at all {{{")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_empty_stdin_exits_zero(self):
        result = run_hook("")
        self.assertEqual(result.returncode, 0)

    def test_json_array_stdin_exits_zero(self):
        result = run_hook("[1, 2, 3]")
        self.assertEqual(result.returncode, 0)

    def test_json_null_stdin_exits_zero(self):
        result = run_hook("null")
        self.assertEqual(result.returncode, 0)

    def test_different_tool_name_appends_nothing(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0015")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0015", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-oth", "task0015", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-oth", tool_name="Bash")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 1)

    def test_no_identifier_anywhere_appends_nothing(self):
        payload = stop_payload(self.tmp_dir)
        result = run_hook_json(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_malformed_agent_index_line_between_valid_lines_is_skipped(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0016")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0016", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir,
            [
                "{ this is not valid json ]]",
                index_entry("agent-skip", "task0016", worktree_path),
            ],
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-skip")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")


class TestOnlyMatchingTaskAffected(QueueTaskStopNetTestCase):
    """AC-8: three tasks recorded as `launched` -- a stop for one of them
    appends `failed` for that task only; the others stay `launched`."""

    def test_stop_for_one_task_leaves_the_others_launched(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        task_ids = ["task0020", "task0021", "task0022"]
        worktree_paths = {tid: make_worktree(feature_dir, tid) for tid in task_ids}
        write_journal(
            feature_dir,
            [
                {"event": "launched", "task": tid, "at": "2026-01-01T00:00:00+00:00"}
                for tid in task_ids
            ],
        )
        write_agent_index(
            feature_dir,
            [
                index_entry(f"agent-{tid}", tid, worktree_paths[tid])
                for tid in task_ids
            ],
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-task0021")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = [json.loads(l) for l in read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))]
        by_task = {}
        for entry in lines:
            by_task[entry["task"]] = entry["event"]
        self.assertEqual(by_task["task0020"], "launched")
        self.assertEqual(by_task["task0021"], "failed")
        self.assertEqual(by_task["task0022"], "launched")


class TestRetryPathReopensAfterStop(QueueTaskStopNetTestCase):
    """AC-9: after this hook appends `failed`, queue_launch_guard.py allows
    a relaunch of the same task (no deny decision, appends `launched`) --
    the retry path this feature exists to unblock. Only the guard's
    observable output/side-effects are asserted, never its internals."""

    def test_launch_guard_allows_retry_after_taskstop_recorded_failure(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0030")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0030", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-retry", "task0030", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-retry")

        recorder_result = run_hook_json(payload)
        self.assertEqual(recorder_result.returncode, 0)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")

        launch_payload = {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "em-workflow:implementer",
                "description": "Implement task0030",
                "prompt": (
                    "# Task assignment\n"
                    "task_id: task0030\n"
                    f"worktree_path: {worktree_path}\n"
                    "task_plan_path: /repo/feature-docs/demo/tasks/task0030.md\n"
                    "implementation_md_path: /repo/feature-docs/demo/IMPLEMENTATION.md\n"
                    "parent_branch: em-workflow/demo/integration\n"
                    "merge_script: /repo/em-workflow/scripts/merge-task.sh\n"
                    "skills_to_load: []\n"
                    "project_commands:\n"
                    '  build: ""\n'
                    '  test: ""\n'
                    '  format: ""\n'
                    "expected_files: []\n"
                ),
            },
        }
        guard_result = run_hook_json(launch_payload, hook_path=LAUNCH_GUARD_PATH)

        self.assertEqual(guard_result.returncode, 0)
        self.assertEqual(guard_result.stdout, "")  # no deny decision
        launch_guard_lines = [json.loads(l) for l in read_journal_lines(journal_path)]
        self.assertEqual(launch_guard_lines[-1]["event"], "launched")
        self.assertEqual(launch_guard_lines[-1]["task"], "task0030")


class TestLastMatchingEntryWins(QueueTaskStopNetTestCase):
    """AC-10: two agent-index entries for the same identifier -> the LAST
    one determines the task."""

    def test_last_index_entry_for_identifier_wins(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        first_worktree = make_worktree(feature_dir, "task0040")
        second_worktree = make_worktree(feature_dir, "task0041")
        write_journal(
            feature_dir,
            [
                {"event": "launched", "task": "task0040", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "launched", "task": "task0041", "at": "2026-01-01T00:01:00+00:00"},
            ],
        )
        write_agent_index(
            feature_dir,
            [
                index_entry("agent-reused", "task0040", first_worktree, at="2026-01-01T00:00:00+00:00"),
                index_entry("agent-reused", "task0041", second_worktree, at="2026-01-01T00:02:00+00:00"),
            ],
        )
        payload = stop_payload(self.tmp_dir, input_id="agent-reused")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = [json.loads(l) for l in read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))]
        by_task = {entry["task"]: entry["event"] for entry in lines}
        self.assertEqual(by_task["task0040"], "launched")  # unaffected
        self.assertEqual(by_task["task0041"], "failed")  # last entry's task


class TestIdentifierRecoveryPaths(QueueTaskStopNetTestCase):
    """AC-11: the agent identifier is recovered both from the stop tool
    input's task-identifier field, and (when that is absent) from the tool
    result -- two separate cases."""

    def test_identifier_recovered_from_tool_input(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0050")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0050", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-input-src", "task0050", worktree_path)])
        payload = stop_payload(self.tmp_dir, input_id="agent-input-src")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)

    def test_identifier_recovered_from_tool_result_when_input_absent(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0051")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0051", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-result-src", "task0051", worktree_path)])
        payload = stop_payload(self.tmp_dir, result_id="agent-result-src")

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)

    def test_tool_input_identifier_takes_priority_over_tool_result(self):
        """When both are present, the tool input's field is preferred."""
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        worktree_path = make_worktree(feature_dir, "task0052")
        write_journal(
            feature_dir,
            [{"event": "launched", "task": "task0052", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(feature_dir, [index_entry("agent-priority", "task0052", worktree_path)])
        payload = stop_payload(
            self.tmp_dir, input_id="agent-priority", result_id="agent-decoy-not-indexed"
        )

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(os.path.join(feature_dir, "journal.jsonl"))
        self.assertEqual(len(lines), 2)  # the input-sourced id matched


class TestHooksJsonRegistration(QueueTaskStopNetTestCase):
    """AC-12: hooks.json remains valid JSON, keeps its pre-existing
    registrations, and registers this hook under the post-invocation tool
    event with timeout 15 and the plugin-root-relative command form."""

    @classmethod
    def setUpClass(cls):
        hooks_json_path = REPO_ROOT / "em-workflow" / "hooks" / "hooks.json"
        cls.config = json.loads(hooks_json_path.read_text(encoding="utf-8"))

    def test_pre_existing_registrations_unchanged(self):
        pre_tool_use = self.config["hooks"]["PreToolUse"]
        matchers = {group.get("matcher") for group in pre_tool_use}
        self.assertIn("Bash", matchers)
        self.assertIn("Task|Agent", matchers)
        self.assertIn("queue_stop_guard.py", self.config["hooks"]["Stop"][0]["hooks"][0]["command"])
        self.assertIn(
            "queue_failure_net.py",
            self.config["hooks"]["SubagentStop"][0]["hooks"][0]["command"],
        )

    def test_taskstop_hook_registered_under_post_tool_use(self):
        post_tool_use = self.config["hooks"].get("PostToolUse", [])
        matches = []
        for group in post_tool_use:
            if group.get("matcher") != STOP_TOOL_NAME:
                continue
            for hook in group.get("hooks", []):
                if "queue_taskstop_net.py" in hook.get("command", ""):
                    matches.append(hook)
        self.assertTrue(
            matches,
            "expected a PostToolUse(TaskStop) entry referencing queue_taskstop_net.py",
        )
        hook = matches[0]
        self.assertEqual(hook.get("timeout"), 15)
        self.assertEqual(
            hook.get("command"),
            'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/queue_taskstop_net.py',
        )


class TestConcurrentAppends(QueueTaskStopNetTestCase):
    """NFR4: concurrent journal appends for different tasks in the same
    feature must not corrupt the file (flock)."""

    def test_concurrent_invocations_do_not_corrupt_journal(self):
        feature = "demo"
        feature_dir = make_feature(self.tmp_dir, feature)
        task_ids = [f"task{n:04d}" for n in range(60, 66)]
        journal_lines = []
        index_lines = []
        payloads = []
        for tid in task_ids:
            worktree_path = make_worktree(feature_dir, tid)
            journal_lines.append({"event": "launched", "task": tid, "at": "2026-01-01T00:00:00+00:00"})
            index_lines.append(index_entry(f"agent-{tid}", tid, worktree_path))
            payloads.append(stop_payload(self.tmp_dir, input_id=f"agent-{tid}"))
        write_journal(feature_dir, journal_lines)
        write_agent_index(feature_dir, index_lines)

        results = [None] * len(payloads)

        def invoke(index, payload):
            results[index] = run_hook_json(payload)

        threads = [threading.Thread(target=invoke, args=(i, p)) for i, p in enumerate(payloads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        for result in results:
            self.assertIsNotNone(result)
            self.assertEqual(result.returncode, 0)

        journal_path = os.path.join(feature_dir, "journal.jsonl")
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2 * len(task_ids))
        failed_tasks = set()
        for line in lines:
            entry = json.loads(line)  # every line must parse -- no torn writes
            if entry.get("event") == "failed":
                failed_tasks.add(entry.get("task"))
        self.assertEqual(failed_tasks, set(task_ids))


if __name__ == "__main__":
    unittest.main()
