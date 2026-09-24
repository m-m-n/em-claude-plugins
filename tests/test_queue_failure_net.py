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


def write_multi_transcript(tmp_dir, name, messages):
    """messages: list of (role, content) tuples. content may be a string or
    a text-block-list (list of {"text": ...} dicts) -- both transcript
    content shapes."""
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        for role, content in messages:
            fh.write(
                json.dumps({"type": role, "message": {"role": role, "content": content}}) + "\n"
            )
    return path


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


def diagnostics_path(root):
    return os.path.join(root, "subagent-stop-diagnostics.jsonl")


def read_diagnostics_lines(root):
    path = diagnostics_path(root)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


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


class TestAgentTypeShortFormAccepted(QueueFailureNetTestCase):
    """AC-1: agent_type == "implementer" (short form, without the
    `em-workflow:` prefix) is also accepted."""

    def test_agent_type_implementer_short_form_appends_failed(self):
        feature, task_id = "demo", "task0201"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type="implementer", transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")


class TestTranscriptScanSkipsNonHeaderMessages(QueueFailureNetTestCase):
    """AC-2: no inline field; the transcript's first user-role message has
    no header but the second one carries a valid block -> failed for the
    second message's task. An inline field without a header does not
    prevent the transcript scan; an inline field WITH a header takes
    precedence over a transcript block naming a different task."""

    def test_second_user_message_with_header_is_used(self):
        feature, task_id = "demo", "task0210"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_multi_transcript(
            self.tmp_dir,
            "agent.jsonl",
            [
                ("user", "hello, just checking in"),
                ("assistant", "ok"),
                ("user", assignment_block(task_id, worktree_path)),
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("task"), task_id)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")

    def test_inline_field_without_header_does_not_block_transcript_scan(self):
        feature, task_id = "demo", "task0211"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)
        payload["prompt"] = "no header here, just a note"

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("task"), task_id)

    def test_inline_field_with_header_takes_precedence_over_transcript(self):
        feature = "demo"
        inline_task = "task0212"
        transcript_task = "task0213"
        inline_worktree, journal_path = make_worktree(self.tmp_dir, feature, inline_task)
        transcript_worktree, _ = make_worktree(self.tmp_dir, feature, transcript_task)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": inline_task, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "launched", "task": transcript_task, "at": "2026-01-01T00:00:01+00:00"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(transcript_task, transcript_worktree)
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)
        payload["prompt"] = assignment_block(inline_task, inline_worktree)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = [json.loads(l) for l in read_journal_lines(journal_path)]
        by_task = {entry["task"]: entry["event"] for entry in lines}
        self.assertEqual(by_task[inline_task], "failed")
        self.assertEqual(by_task[transcript_task], "launched")  # untouched


class TestAgentIndexFallback(QueueFailureNetTestCase):
    """AC-3 (single-hook side): resolving via the agent-index fallback when
    no inline prompt and no usable transcript block are found."""

    def test_resolves_via_agent_index_when_no_block_found(self):
        feature = "demo"
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        worktree_path = os.path.join(feature_dir, "task0220")
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(
            journal_path,
            [{"event": "launched", "task": "task0220", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir,
            [
                {
                    "agent_id": "agent-1",
                    "task": "task0220",
                    "worktree_path": worktree_path,
                    "at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir  # base_payload's default agent_id "agent-1" matches

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("task"), "task0220")
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")


class TestAgentIndexRefusals(QueueFailureNetTestCase):
    """AC-3: refusal fixtures for the agent-index fallback -- nothing is
    appended for any of them (identifier matching two tasks, a superseded
    entry of a relaunched task, a worktree path outside the feature
    directory, an oversized candidate list, no matching entry)."""

    def _feature_dir(self, feature="demo"):
        feature_dir = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow", feature)
        os.makedirs(feature_dir, exist_ok=True)
        return feature_dir

    def _root(self):
        return os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")

    def _assert_index_unresolved(self):
        """Distinguishes "the fallback ran and specifically refused" from
        "the fallback never ran at all" -- both leave the journal
        unchanged, but only the former records outcome `index-unresolved`
        in the diagnostics log."""
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "index-unresolved")

    def test_identifier_matching_two_tasks_appends_nothing(self):
        feature_dir = self._feature_dir()
        w1 = os.path.join(feature_dir, "task0230")
        w2 = os.path.join(feature_dir, "task0231")
        os.makedirs(w1, exist_ok=True)
        os.makedirs(w2, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": "task0230", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "launched", "task": "task0231", "at": "2026-01-01T00:00:01+00:00"},
            ],
        )
        write_agent_index(
            feature_dir,
            [
                {"agent_id": "agent-1", "task": "task0230", "worktree_path": w1, "at": "2026-01-01T00:00:00+00:00"},
                {"agent_id": "agent-1", "task": "task0231", "worktree_path": w2, "at": "2026-01-01T00:00:02+00:00"},
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = [json.loads(l) for l in read_journal_lines(journal_path)]
        self.assertTrue(all(entry["event"] == "launched" for entry in lines))
        self._assert_index_unresolved()

    def test_superseded_entry_of_relaunched_task_appends_nothing(self):
        feature_dir = self._feature_dir()
        worktree_path = os.path.join(feature_dir, "task0232")
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(
            journal_path,
            [{"event": "launched", "task": "task0232", "at": "2026-01-01T00:10:00+00:00"}],
        )
        write_agent_index(
            feature_dir,
            [
                {"agent_id": "agent-1", "task": "task0232", "worktree_path": worktree_path, "at": "2026-01-01T00:00:00+00:00"},
                {"agent_id": "agent-2", "task": "task0232", "worktree_path": worktree_path, "at": "2026-01-01T00:10:00+00:00"},
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir  # default agent_id "agent-1" is the superseded (earlier) identifier

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 1)
        self._assert_index_unresolved()

    def test_worktree_path_outside_feature_directory_appends_nothing(self):
        feature_dir = self._feature_dir()
        outside_worktree = os.path.join(self.tmp_dir, "task0233")
        write_agent_index(
            feature_dir,
            [
                {
                    "agent_id": "agent-1",
                    "task": "task0233",
                    "worktree_path": outside_worktree,
                    "at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isfile(os.path.join(feature_dir, "journal.jsonl")))
        self._assert_index_unresolved()

    def test_oversized_candidate_list_appends_nothing(self):
        feature_dir = self._feature_dir()
        worktree_path = os.path.join(feature_dir, "task0234")
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(
            journal_path,
            [{"event": "launched", "task": "task0234", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir,
            [
                {
                    "agent_id": "agent-primary",
                    "agent_ids": ["agent-primary", "id-2", "id-3", "id-4", "id-5", "agent-1"],
                    "task": "task0234",
                    "worktree_path": worktree_path,
                    "at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir  # default agent_id "agent-1" is in the oversized list -> ignored wholesale

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 1)
        self._assert_index_unresolved()

    def test_no_matching_entry_appends_nothing(self):
        feature_dir = self._feature_dir()
        worktree_path = os.path.join(feature_dir, "task0235")
        os.makedirs(worktree_path, exist_ok=True)
        journal_path = os.path.join(feature_dir, "journal.jsonl")
        write_journal(
            journal_path,
            [{"event": "launched", "task": "task0235", "at": "2026-01-01T00:00:00+00:00"}],
        )
        write_agent_index(
            feature_dir,
            [
                {
                    "agent_id": "agent-does-not-match",
                    "task": "task0235",
                    "worktree_path": worktree_path,
                    "at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(read_journal_lines(journal_path)), 1)
        self._assert_index_unresolved()


class TestDiagnosticsOutcomes(QueueFailureNetTestCase):
    """AC-6: one diagnostics line per invocation, with the SC2 keys, for
    each of the nine outcome codes."""

    def _root(self):
        root = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")
        os.makedirs(root, exist_ok=True)
        return root

    def test_outcome_appended(self):
        self._root()
        feature, task_id = "demo", "task0300"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["outcome"], "appended")
        self.assertEqual(entry["source"], "transcript")
        self.assertEqual(entry["task_id"], task_id)
        self.assertTrue(RFC3339_RE.match(entry["at"]))

    def test_outcome_already_terminal(self):
        self._root()
        feature, task_id = "demo", "task0301"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-01T01:00:00+00:00", "commit": "abc"},
            ],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "already-terminal")
        self.assertEqual(entries[0]["task_id"], task_id)

    def test_outcome_not_implementer_type(self):
        self._root()
        transcript_path = write_transcript(self.tmp_dir, "agent.jsonl", "not a block")
        payload = base_payload(agent_type="Explore", transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "not-implementer-type")
        self.assertEqual(entries[0]["source"], "none")
        self.assertNotIn("task_id", entries[0])

    def test_outcome_no_prompt_text(self):
        self._root()
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir
        payload["agent_id"] = ""  # no usable agent_id either

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "no-prompt-text")
        self.assertNotIn("task_id", entries[0])

    def test_outcome_no_assignment_block(self):
        self._root()
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", "just chatting, no header here"
        )
        payload = base_payload(agent_type=None, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir
        payload["agent_id"] = ""

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "no-assignment-block")
        self.assertNotIn("task_id", entries[0])

    def test_outcome_invalid_identity(self):
        self._root()
        feature, task_id = "demo", "task0305"
        worktree_path, _journal_path = make_worktree(self.tmp_dir, feature, task_id)
        bad_block = assignment_block(task_id, worktree_path).replace(
            f"task_id: {task_id}", "task_id: not-a-valid-id"
        )
        transcript_path = write_transcript(self.tmp_dir, "agent.jsonl", bad_block)
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "invalid-identity")
        self.assertNotIn("task_id", entries[0])

    def test_outcome_index_unresolved(self):
        self._root()  # exists, but empty of features
        payload = base_payload(agent_type=None, transcript_path=None)
        payload["cwd"] = self.tmp_dir
        payload["agent_id"] = "agent-nothing-matches"

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "index-unresolved")
        self.assertNotIn("task_id", entries[0])

    def test_outcome_journal_dir_missing(self):
        self._root()
        feature, task_id = "demo", "task0307"
        never_created_worktree = os.path.join(
            self.tmp_dir, ".claude", "worktrees", "em-workflow", feature, task_id
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, never_created_worktree)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "journal-dir-missing")
        self.assertEqual(entries[0]["task_id"], task_id)

    def test_outcome_error_via_journal_symlink(self):
        feature, task_id = "demo", "task0308"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        outside_target = os.path.join(self.tmp_dir, "outside-target.jsonl")
        self.assertFalse(os.path.isfile(outside_target))
        os.symlink(outside_target, journal_path)
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isfile(outside_target))
        entries = read_diagnostics_lines(self._root())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "error")
        self.assertTrue(
            isinstance(entries[0].get("error_class"), str) and entries[0]["error_class"]
        )


class TestDiagnosticsRootFallback(QueueFailureNetTestCase):
    """AC-6: when cwd yields no root but the validated worktree path does,
    the diagnostics line lands in the worktree path's root; when neither
    yields a root, no diagnostics file is created anywhere in the temporary
    tree."""

    def test_cwd_outside_any_root_falls_back_to_worktree_path_root(self):
        feature, task_id = "demo", "task0310"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        transcript_path = write_transcript(
            self.tmp_dir, "agent.jsonl", assignment_block(task_id, worktree_path)
        )
        outside_cwd = os.path.join(self.tmp_dir, "outside-any-root")
        os.makedirs(outside_cwd, exist_ok=True)
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = outside_cwd

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        root = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")
        entries = read_diagnostics_lines(root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["outcome"], "appended")

    def test_no_root_anywhere_creates_no_diagnostics_file(self):
        outside_cwd = os.path.join(self.tmp_dir, "nowhere-near-a-root")
        os.makedirs(outside_cwd, exist_ok=True)
        transcript_path = write_transcript(self.tmp_dir, "agent.jsonl", "no header at all")
        payload = base_payload(agent_type="Explore", transcript_path=transcript_path)
        payload["cwd"] = outside_cwd

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        for _root_dir, _dirs, files in os.walk(self.tmp_dir):
            self.assertNotIn("subagent-stop-diagnostics.jsonl", files)


class TestDiagnosticsObstruction(QueueFailureNetTestCase):
    """AC-7: a symlink or a directory at the diagnostics log path never
    stops the hook (exit 0, the `failed` line still lands in the journal,
    symlink target never written); a sentinel placed in the prompt never
    leaks into the diagnostics file or the journal."""

    def _make_payload(self, task_id, sentinel):
        feature = "demo"
        worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
        write_journal(
            journal_path,
            [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}],
        )
        block = assignment_block(task_id, worktree_path) + f"# sentinel: {sentinel}\n"
        transcript_path = write_transcript(self.tmp_dir, f"{task_id}.jsonl", block)
        payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
        payload["cwd"] = self.tmp_dir
        return payload, journal_path

    def test_symlinked_diagnostics_log_path_is_refused(self):
        sentinel = "SENTINEL-XYZ-001"
        payload, journal_path = self._make_payload("task0320", sentinel)
        root = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")
        os.makedirs(root, exist_ok=True)
        outside_target = os.path.join(self.tmp_dir, "outside-diag-target.jsonl")
        self.assertFalse(os.path.isfile(outside_target))
        log_path = os.path.join(root, "subagent-stop-diagnostics.jsonl")
        os.symlink(outside_target, log_path)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.isfile(outside_target))
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")
        for raw_line in lines:
            self.assertNotIn(sentinel, raw_line)

    def test_directory_at_diagnostics_log_path_is_refused(self):
        sentinel = "SENTINEL-XYZ-002"
        payload, journal_path = self._make_payload("task0321", sentinel)
        root = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")
        log_path = os.path.join(root, "subagent-stop-diagnostics.jsonl")
        os.makedirs(log_path, exist_ok=True)

        result = run_hook_json(payload)

        self.assertEqual(result.returncode, 0)
        lines = read_journal_lines(journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[-1]).get("event"), "failed")
        for raw_line in lines:
            self.assertNotIn(sentinel, raw_line)


class TestConcurrentDiagnosticsWrites(QueueFailureNetTestCase):
    """AC-7: concurrent invocations each append a diagnostics line, and
    every line parses as JSON (no torn writes)."""

    def test_concurrent_invocations_produce_parseable_diagnostics_lines(self):
        feature = "demo"
        task_ids = [f"task033{n}" for n in range(0, 6)]
        root = os.path.join(self.tmp_dir, ".claude", "worktrees", "em-workflow")
        payloads = []
        for task_id in task_ids:
            worktree_path, journal_path = make_worktree(self.tmp_dir, feature, task_id)
            transcript_path = write_transcript(
                self.tmp_dir, f"agent-{task_id}.jsonl", assignment_block(task_id, worktree_path)
            )
            payload = base_payload(agent_type=IMPLEMENTER_TYPE, transcript_path=transcript_path)
            payload["cwd"] = self.tmp_dir
            payloads.append(payload)

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

        log_path = os.path.join(root, "subagent-stop-diagnostics.jsonl")
        with open(log_path, encoding="utf-8") as fh:
            raw_lines = [line for line in fh if line.strip()]
        self.assertEqual(len(raw_lines), len(task_ids))
        for line in raw_lines:
            json.loads(line)  # every line must parse -- no torn writes


class TestHooksJsonSubagentStopRegistration(unittest.TestCase):
    """AC-9: hooks.json registers exactly one SubagentStop group with no
    matcher and one command hook, whose command is
    `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/queue_failure_net.py` with
    timeout 15."""

    def test_registration_shape(self):
        hooks_json_path = REPO_ROOT / "em-workflow" / "hooks" / "hooks.json"
        config = json.loads(hooks_json_path.read_text(encoding="utf-8"))
        groups = config["hooks"]["SubagentStop"]
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertNotIn("matcher", group)
        self.assertEqual(len(group["hooks"]), 1)
        hook = group["hooks"][0]
        self.assertEqual(hook.get("timeout"), 15)
        self.assertEqual(
            hook.get("command"),
            'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/queue_failure_net.py',
        )


class TestModuleDocstring(unittest.TestCase):
    """AC-10: the module docstring names all nine outcome codes, the
    diagnostics file name, and the three identification sources."""

    OUTCOME_CODES = (
        "not-implementer-type",
        "no-prompt-text",
        "no-assignment-block",
        "invalid-identity",
        "index-unresolved",
        "journal-dir-missing",
        "already-terminal",
        "appended",
        "error",
    )
    SOURCES = ("inline", "transcript", "agent-index")

    @classmethod
    def setUpClass(cls):
        source = HOOK_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(HOOK_PATH))
        cls.docstring = ast.get_docstring(tree) or ""

    def test_all_outcome_codes_named(self):
        for code in self.OUTCOME_CODES:
            with self.subTest(code=code):
                self.assertIn(code, self.docstring)

    def test_diagnostics_file_name_named(self):
        self.assertIn("subagent-stop-diagnostics.jsonl", self.docstring)

    def test_all_sources_named(self):
        for source in self.SOURCES:
            with self.subTest(source=source):
                self.assertIn(source, self.docstring)


if __name__ == "__main__":
    unittest.main()
