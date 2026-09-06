"""Tests for em-workflow/scripts/journal-append-failed.py (SC2).

Covers task0002's Acceptance Criteria (see
feature-docs/orphaned-implementer-recovery/tasks/task0002.md); test names
reference the AC they exercise. The script's hyphenated filename means it is
loaded two ways here: via importlib for function-level assertions on the
decision/append logic, and via subprocess (exactly as a real caller would
invoke it) for the command-line entry point.

AC-7 additionally drives em-workflow/hooks/queue_launch_guard.py through its
documented hook interface (subprocess, stdin JSON) to prove the
downstream-convergence outcome: a `failed`/`orphaned` line this helper wrote
does not block a subsequent launch. It does not re-test the guard's own
rules (Test Notes).
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
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "journal-append-failed.py"
LAUNCH_GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_launch_guard.py"

RFC3339_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def load_module():
    """Loads journal-append-failed.py as a module for function-level tests
    (the hyphenated filename is not import-able as a normal module path)."""
    spec = importlib.util.spec_from_file_location("journal_append_failed", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(args, timeout=10):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def write_journal(path, lines):
    """lines: list of dicts (JSON entries) OR raw strings (used verbatim, for
    malformed-line coverage). Creates the parent directory (fixture setup
    only -- the script under test must never do this itself)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line) + "\n")


def read_journal_lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [line for line in fh if line.strip()]


class JournalAppendFailedTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        # A throwaway worktree-root layout inside the temp dir (Test Notes):
        # nothing outside self.tmp_dir is ever touched, and no real
        # ~/.claude state is read (NFR5).
        self.feature_dir = os.path.join(
            self.tmp_dir, ".claude", "worktrees", "em-workflow", "demo-feature"
        )
        self.journal_path = os.path.join(self.feature_dir, "journal.jsonl")


class TestAC1LaunchedAppendsFailed(JournalAppendFailedTestCase):
    """AC-1: final event `launched` -> exactly one well-formed `failed` line
    carrying reason `orphaned`; no pre-existing line changes."""

    def test_appends_exactly_one_failed_line_with_reason_orphaned(self):
        task_id = "task0007"
        write_journal(
            self.journal_path,
            [
                {"event": "merged", "task": "task0001", "at": "2026-01-01T00:00:00+00:00", "commit": "abc"},
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:05:00+00:00"},
            ],
        )
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = read_journal_lines(self.journal_path)
        self.assertEqual(len(lines), 3)
        # Pre-existing lines are byte-identical to what they were before.
        self.assertEqual(lines[:2], before_lines)
        appended = json.loads(lines[-1])
        self.assertEqual(appended.get("event"), "failed")
        self.assertEqual(appended.get("task"), task_id)
        self.assertEqual(appended.get("reason"), "orphaned")
        self.assertTrue(
            RFC3339_RE.match(appended.get("at", "")),
            f"'at' not RFC3339-with-offset: {appended.get('at')!r}",
        )

    def test_stdout_outcome_is_appended(self):
        task_id = "task0008"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload, {"outcome": "appended", "task": task_id, "reason": "orphaned"})

    def test_field_shape_matches_existing_failed_writers(self):
        """SC4: field names and ORDER are taken from the existing `failed`
        writers, not invented -- verified at the raw-text level so a
        reordering (which json.loads would hide) is caught."""
        task_id = "task0009"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = read_journal_lines(self.journal_path)
        appended_raw = lines[-1]
        self.assertEqual(
            list(json.loads(appended_raw).keys()),
            ["event", "task", "at", "reason"],
        )


class TestAC2TerminalIsNoop(JournalAppendFailedTestCase):
    """AC-2: a second invocation (or any invocation against an already
    terminal final event) appends nothing and reports noop_terminal; exactly
    one `failed` line survives for the task (TS-2). Holds for both `merged`
    and `failed` as the final event."""

    def test_second_invocation_after_failed_is_noop(self):
        task_id = "task0010"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        first = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])
        self.assertEqual(first.returncode, 0, first.stderr)

        second = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(second.returncode, 0, second.stderr)
        payload = json.loads(second.stdout.strip())
        self.assertEqual(payload["outcome"], "noop_terminal")
        lines = read_journal_lines(self.journal_path)
        failed_lines = [l for l in lines if json.loads(l).get("task") == task_id and json.loads(l).get("event") == "failed"]
        self.assertEqual(len(failed_lines), 1)

    def test_final_event_merged_is_noop(self):
        task_id = "task0011"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-01T00:10:00+00:00", "commit": "def456"},
            ],
        )
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["outcome"], "noop_terminal")
        self.assertEqual(read_journal_lines(self.journal_path), before_lines)

    def test_final_event_failed_is_noop(self):
        task_id = "task0012"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"},
                {"event": "failed", "task": task_id, "at": "2026-01-01T00:10:00+00:00", "reason": "implementer stopped without a merged event"},
            ],
        )
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["outcome"], "noop_terminal")
        self.assertEqual(read_journal_lines(self.journal_path), before_lines)


class TestAC3ReasonValidation(JournalAppendFailedTestCase):
    """AC-3: a --reason value outside the closed set is rejected, non-zero
    exit, no write -- even when the journal's final event would otherwise
    qualify for an append."""

    def test_unknown_reason_rejected_without_write(self):
        task_id = "task0013"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "manual"])

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_journal_lines(self.journal_path), before_lines)
        self.assertEqual(result.stdout, "")

    def test_empty_reason_rejected_without_write(self):
        task_id = "task0014"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", ""])

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_journal_lines(self.journal_path), before_lines)


class TestAC4JournalAccessPreconditions(JournalAppendFailedTestCase):
    """AC-4: a symlinked journal path is refused without writing; an absent
    journal file and an absent parent directory are each reported as an
    error, and neither is created (TS-7)."""

    def test_symlinked_journal_path_refused_without_writing(self):
        task_id = "task0015"
        real_path = os.path.join(self.tmp_dir, "real-journal.jsonl")
        write_journal(real_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])
        before_lines = read_journal_lines(real_path)
        link_path = os.path.join(self.tmp_dir, "linked-journal.jsonl")
        os.symlink(real_path, link_path)

        result = run_cli(["--journal", link_path, "--task", task_id, "--reason", "orphaned"])

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_journal_lines(real_path), before_lines)

    def test_absent_journal_file_is_error_and_not_created(self):
        os.makedirs(self.feature_dir, exist_ok=True)
        self.assertFalse(os.path.exists(self.journal_path))

        result = run_cli(["--journal", self.journal_path, "--task", "task0016", "--reason", "orphaned"])

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.journal_path))
        self.assertEqual(result.stdout, "")

    def test_absent_parent_directory_is_error_and_not_created(self):
        self.assertFalse(os.path.isdir(self.feature_dir))

        result = run_cli(["--journal", self.journal_path, "--task", "task0017", "--reason", "orphaned"])

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.isdir(self.feature_dir))
        self.assertFalse(os.path.exists(self.journal_path))
        self.assertEqual(result.stdout, "")


class TestAC5Contention(JournalAppendFailedTestCase):
    """AC-5: two invocations contending for the same journal produce at most
    one appended `failed` line for the task, and never a partially written
    line (TS-7). Genuine contention: both processes are started before
    either can have finished, and the assertion is on the observable
    post-state, not on lock internals."""

    def test_concurrent_invocations_append_at_most_one_failed_line(self):
        task_id = "task0018"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        results = [None, None]

        def invoke(index):
            results[index] = run_cli(
                ["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"]
            )

        threads = [threading.Thread(target=invoke, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        for result in results:
            self.assertIsNotNone(result)
            self.assertEqual(result.returncode, 0, result.stderr)

        lines = read_journal_lines(self.journal_path)
        for line in lines:
            json.loads(line)  # every line must parse -- no torn/partial writes
        failed_lines = [l for l in lines if json.loads(l).get("event") == "failed" and json.loads(l).get("task") == task_id]
        self.assertEqual(len(failed_lines), 1)

        outcomes = sorted(json.loads(r.stdout.strip())["outcome"] for r in results)
        self.assertEqual(outcomes, ["appended", "noop_terminal"])


class TestAC6OutcomeReporting(JournalAppendFailedTestCase):
    """AC-6: outcome reporting matches SC2 -- one line of JSON on stdout,
    exit 0 for both decided outcomes, non-zero and no write for usage/
    internal errors, diagnostics on stderr only."""

    def test_appended_outcome_is_single_json_line_on_stdout(self):
        task_id = "task0019"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])

        self.assertEqual(result.returncode, 0, result.stderr)
        stdout_lines = [l for l in result.stdout.splitlines() if l.strip()]
        self.assertEqual(len(stdout_lines), 1)
        payload = json.loads(stdout_lines[0])
        self.assertEqual(set(payload.keys()), {"outcome", "task", "reason"})
        self.assertEqual(payload["outcome"], "appended")

    def test_usage_error_missing_required_arg_is_nonzero_no_stdout(self):
        result = run_cli(["--task", "task0020", "--reason", "orphaned"])  # missing --journal

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip())

    def test_internal_error_reports_diagnostics_on_stderr_only(self):
        # Absent journal directory is an internal/usage-shaped error path;
        # confirms diagnostics land on stderr, never stdout, alongside AC-4.
        result = run_cli(
            ["--journal", self.journal_path, "--task", "task0021", "--reason", "orphaned"]
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip())


class TestAC7LaunchGuardConvergence(JournalAppendFailedTestCase):
    """AC-7 (TS-4, downstream convergence for FR4): after this helper records
    `failed` with reason `orphaned`, a subsequent launch of the same task is
    PERMITTED by the launch guard (queue_launch_guard.py) and `launched` is
    appended -- it is not denied. Drives the guard through its documented
    hook interface (subprocess, stdin JSON); does not re-test the guard's
    own rules."""

    def test_launch_after_orphaned_failed_is_permitted_and_appends_launched(self):
        task_id = "task0022"
        worktree_path = os.path.join(self.feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])

        recovery = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "orphaned"])
        self.assertEqual(recovery.returncode, 0, recovery.stderr)
        self.assertEqual(json.loads(recovery.stdout.strip())["outcome"], "appended")

        prompt = (
            "# Task assignment\n"
            f"task_id: {task_id}\n"
            f"worktree_path: {worktree_path}\n"
        )
        guard_payload = {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "em-workflow:implementer",
                "prompt": prompt,
            },
        }
        guard_result = subprocess.run(
            [sys.executable, str(LAUNCH_GUARD_PATH)],
            input=json.dumps(guard_payload),
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(guard_result.returncode, 0, guard_result.stderr)
        # No deny decision: the hook emits a `permissionDecision: deny`
        # payload on stdout only when it blocks the call; the allow path
        # prints nothing.
        self.assertNotIn("deny", guard_result.stdout)
        lines = read_journal_lines(self.journal_path)
        last_event_for_task = None
        for line in lines:
            entry = json.loads(line)
            if entry.get("task") == task_id:
                last_event_for_task = entry.get("event")
        self.assertEqual(last_event_for_task, "launched")


class TestFunctionLevelDecisionLogic(JournalAppendFailedTestCase):
    """Function-level coverage (Design "Structure for testability"): the
    replay decision and the append are reachable as functions independent of
    the command-line entry point."""

    def setUp(self):
        super().setUp()
        self.module = load_module()

    def test_valid_reason_accepts_only_the_closed_set(self):
        self.assertTrue(self.module.valid_reason("orphaned"))
        self.assertFalse(self.module.valid_reason("manual"))
        self.assertFalse(self.module.valid_reason(""))
        self.assertFalse(self.module.valid_reason(None))

    def test_last_event_for_task_replays_last_by_file_order(self):
        content = "\n".join(
            json.dumps(e)
            for e in [
                {"event": "launched", "task": "task0001", "at": "t1"},
                {"event": "failed", "task": "task0001", "at": "t2", "reason": "x"},
                {"event": "launched", "task": "task0001", "at": "t3"},
                {"event": "launched", "task": "task0002", "at": "t4"},
            ]
        )
        self.assertEqual(self.module.last_event_for_task(content, "task0001"), "launched")
        self.assertEqual(self.module.last_event_for_task(content, "task0002"), "launched")
        self.assertIsNone(self.module.last_event_for_task(content, "task0099"))

    def test_last_event_for_task_skips_malformed_lines(self):
        content = "not json\n" + json.dumps({"event": "merged", "task": "task0003", "at": "t1", "commit": "x"})
        self.assertEqual(self.module.last_event_for_task(content, "task0003"), "merged")

    def test_decide_and_append_raises_on_missing_journal(self):
        with self.assertRaises(self.module.JournalAccessError):
            self.module.decide_and_append(self.journal_path, "task0024", "orphaned")

    def test_decide_and_append_appends_only_when_launched(self):
        write_journal(self.journal_path, [{"event": "launched", "task": "task0025", "at": "t1"}])
        outcome = self.module.decide_and_append(self.journal_path, "task0025", "orphaned")
        self.assertEqual(outcome, "appended")


if __name__ == "__main__":
    unittest.main()
