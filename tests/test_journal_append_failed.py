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

`TestTask0001*` classes cover task0001's own Acceptance Criteria (see
feature-docs/stale-launched-retry-recovery/tasks/task0001.md): the widened
reason set, the in-lock launch-identity comparison, the `launch_changed`
outcome and its concurrency property. Their AC numbers are task0001's own
and are unrelated to the `TestAC*` numbering above, which stays task0002's.

`TestMergeUnverified*` classes cover a LATER, DIFFERENT task0001 (see
feature-docs/routeback-deferred-findings/tasks/task0001.md): the third
reason, `merge-unverified`, which appends only over a task's own final
event `merged` (never `launched`) and never accepts `--launch-at`. Their AC
numbers are this task's own and are unrelated to the `TestAC*` /
`TestTask0001*` numbering above, which belongs to earlier features.
"""

import ast
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


def read_journal_bytes(path):
    """Raw byte content of `path`, or None if it does not exist. Used for
    the AC-5-style byte-identity assertions (task0001): a line-count or
    parsed-line comparison does not prove byte-for-byte equality, only a
    raw read does."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


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


class TestTask0001AC1WidenedReasonSet(JournalAppendFailedTestCase):
    """task0001 AC-1: the closed reason set accepts exactly `orphaned` and
    `stale-launched`; `manual`, the empty string (TestAC3ReasonValidation,
    unchanged) and a wholly MISSING `--reason` are each rejected with a
    non-zero exit, no stdout outcome line, and a byte-identical journal."""

    def test_missing_reason_value_rejected_without_write(self):
        task_id = "task0030"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id])  # --reason omitted entirely

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)


class TestTask0001AC2StaleLaunchedAppends(JournalAppendFailedTestCase):
    """task0001 AC-2: invoking with reason `stale-launched` against a
    journal whose last event for the task is `launched` appends exactly one
    line whose fields are `event`, `task`, `at`, `reason` in that order,
    with `event` = `failed` and `reason` = `stale-launched`, and reports
    outcome `appended`."""

    def test_stale_launched_appends_failed_line_with_correct_fields(self):
        task_id = "task0031"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-01T00:00:00+00:00"}])
        before_lines = read_journal_lines(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched"])

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = read_journal_lines(self.journal_path)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[:1], before_lines)
        appended_raw = lines[-1]
        self.assertEqual(list(json.loads(appended_raw).keys()), ["event", "task", "at", "reason"])
        appended = json.loads(appended_raw)
        self.assertEqual(appended["event"], "failed")
        self.assertEqual(appended["reason"], "stale-launched")
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload, {"outcome": "appended", "task": task_id, "reason": "stale-launched"})


class TestTask0001AC3LaunchIdentityComparison(JournalAppendFailedTestCase):
    """task0001 AC-3 (and TS5's edge cases): with `--launch-at` supplied and
    matching the last `launched` event's `at`, the append happens and
    outcome is `appended`; with it supplied and NOT matching (different
    value, absent `at`, or non-string `at`), nothing is appended, the
    journal is byte-identical to its pre-call content, outcome is
    `launch_changed`, and the exit code is 0."""

    def test_matching_launch_at_appends(self):
        task_id = "task0032"
        launch_at = "2026-02-02T10:00:00+00:00"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": launch_at}])

        result = run_cli(
            ["--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched", "--launch-at", launch_at]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "appended")
        self.assertEqual(len(read_journal_lines(self.journal_path)), 2)

    def test_mismatched_launch_at_does_not_append(self):
        task_id = "task0033"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-02-02T10:00:00+00:00"}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                "--launch-at", "2026-02-02T11:00:00+00:00",
            ]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout.strip()),
            {"outcome": "launch_changed", "task": task_id, "reason": "stale-launched"},
        )
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_absent_at_on_last_launched_event_does_not_append(self):
        task_id = "task0034"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id}])  # no `at` field at all
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                "--launch-at", "2026-02-02T10:00:00+00:00",
            ]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "launch_changed")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_non_string_at_on_last_launched_event_does_not_append(self):
        task_id = "task0035"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": 20260202100000}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                "--launch-at", "20260202100000",
            ]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "launch_changed")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_interleaved_other_task_events_do_not_affect_comparison(self):
        """Test Notes edge case: interleaved events for OTHER task ids
        around the launch under recovery must not affect the replay."""
        task_id = "task0036"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": "task0999", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "launched", "task": task_id, "at": "2026-03-03T09:00:00+00:00"},
                {"event": "failed", "task": "task0999", "at": "2026-01-01T00:05:00+00:00", "reason": "orphaned"},
            ],
        )

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                "--launch-at", "2026-03-03T09:00:00+00:00",
            ]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "appended")

    def test_relaunch_overtakes_before_invocation_yields_launch_changed(self):
        """TS5: build a journal whose last event for the task is `launched`
        with one `at` value, then rewrite the file so the last event is a
        `launched` with a DIFFERENT `at`, then invoke with the first value:
        no append, mismatch outcome."""
        task_id = "task0037"
        first_at = "2026-04-04T08:00:00+00:00"
        second_at = "2026-04-04T09:00:00+00:00"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": first_at}])
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": second_at}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            ["--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched", "--launch-at", first_at]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "launch_changed")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)


class TestTask0001AC4LaunchAtOmittedPreservesLegacyBehavior(JournalAppendFailedTestCase):
    """task0001 AC-4 (NFR5): with `--launch-at` omitted entirely, every
    pre-existing case keeps its current outcome. This class adds no new
    coverage beyond what TestAC1LaunchedAppendsFailed / TestAC2TerminalIsNoop
    already assert (those tests never pass `--launch-at`) -- it exists so
    the mapping from this task's AC-4 to that pre-existing coverage is
    explicit, per the task plan's own note that AC-4 is proven by those
    tests continuing to pass rather than by new tests."""


class TestTask0001AC5ByteIdentityAcrossNonAppendingOutcomes(JournalAppendFailedTestCase):
    """task0001 AC-5 (FR9): every non-appending outcome (`noop_terminal`,
    `launch_changed`, reason rejection, precondition failure) leaves the
    journal byte-for-byte identical and creates neither the file nor its
    parent directory."""

    def test_launch_changed_leaves_journal_byte_identical(self):
        task_id = "task0038"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-05-05T05:00:00+00:00"}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                "--launch-at", "2026-05-05T06:00:00+00:00",
            ]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "launch_changed")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_reason_rejection_leaves_journal_byte_identical(self):
        task_id = "task0039"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-05-05T05:00:00+00:00"}])
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "manual"])

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_precondition_failure_creates_neither_file_nor_parent(self):
        task_id = "task0040"
        self.assertFalse(os.path.isdir(self.feature_dir))

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched"])

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.isdir(self.feature_dir))
        self.assertFalse(os.path.exists(self.journal_path))


class TestTask0001AC6ConcurrentSameLaunchIdentity(JournalAppendFailedTestCase):
    """task0001 AC-6 (NFR2): N concurrent invocations carrying the SAME
    launch identity against the same journal append at most one `failed`
    line in total."""

    def test_concurrent_invocations_with_same_launch_identity_append_at_most_one(self):
        task_id = "task0041"
        launch_at = "2026-06-06T06:00:00+00:00"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": launch_at}])

        n = 5
        results = [None] * n

        def invoke(index):
            results[index] = run_cli(
                [
                    "--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched",
                    "--launch-at", launch_at,
                ]
            )

        threads = [threading.Thread(target=invoke, args=(i,)) for i in range(n)]
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
        failed_lines = [
            l for l in lines if json.loads(l).get("event") == "failed" and json.loads(l).get("task") == task_id
        ]
        self.assertEqual(len(failed_lines), 1)

        outcomes = sorted(json.loads(r.stdout.strip())["outcome"] for r in results)
        self.assertEqual(outcomes, ["appended"] + ["noop_terminal"] * (n - 1))


class TestTask0001AC7StdlibOnly(unittest.TestCase):
    """task0001 AC-7 (NFR6): the module imports only the standard library,
    and the test module imports no third-party package."""

    @staticmethod
    def _top_level_imports(source):
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and node.level == 0:
                    names.add(node.module.split(".")[0])
        return names

    def test_helper_module_imports_only_stdlib(self):
        stdlib = set(sys.stdlib_module_names)
        imported = self._top_level_imports(SCRIPT_PATH.read_text(encoding="utf-8"))
        non_stdlib = imported - stdlib
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")

    def test_test_module_imports_only_stdlib(self):
        stdlib = set(sys.stdlib_module_names)
        imported = self._top_level_imports(Path(__file__).read_text(encoding="utf-8"))
        non_stdlib = imported - stdlib
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


class TestFunctionLevelDecisionLogic(JournalAppendFailedTestCase):
    """Function-level coverage (Design "Structure for testability"): the
    replay decision and the append are reachable as functions independent of
    the command-line entry point."""

    def setUp(self):
        super().setUp()
        self.module = load_module()

    def test_valid_reason_accepts_only_the_closed_set(self):
        self.assertTrue(self.module.valid_reason("orphaned"))
        self.assertTrue(self.module.valid_reason("stale-launched"))
        self.assertTrue(self.module.valid_reason("merge-unverified"))
        self.assertFalse(self.module.valid_reason("manual"))
        self.assertFalse(self.module.valid_reason(""))
        self.assertFalse(self.module.valid_reason(None))

    def test_last_entry_for_task_returns_full_dict_of_last_event(self):
        content = "\n".join(
            json.dumps(e)
            for e in [
                {"event": "launched", "task": "task0001", "at": "t1"},
                {"event": "launched", "task": "task0001", "at": "t2"},
            ]
        )
        self.assertEqual(
            self.module.last_entry_for_task(content, "task0001"),
            {"event": "launched", "task": "task0001", "at": "t2"},
        )

    def test_last_entry_for_task_returns_none_when_no_event(self):
        self.assertIsNone(self.module.last_entry_for_task("", "task0099"))

    def test_decide_and_append_with_matching_launch_at_appends(self):
        write_journal(self.journal_path, [{"event": "launched", "task": "task0042", "at": "t1"}])
        outcome = self.module.decide_and_append(self.journal_path, "task0042", "stale-launched", launch_at="t1")
        self.assertEqual(outcome, "appended")

    def test_decide_and_append_with_mismatched_launch_at_returns_launch_changed(self):
        write_journal(self.journal_path, [{"event": "launched", "task": "task0043", "at": "t1"}])
        outcome = self.module.decide_and_append(self.journal_path, "task0043", "stale-launched", launch_at="t2")
        self.assertEqual(outcome, "launch_changed")

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


class TestMergeUnverifiedAC1AppendsOverMerged(JournalAppendFailedTestCase):
    """AC-1: with a journal whose final event for the task is `merged`
    (preceded by other tasks' lines), `--reason merge-unverified` exits 0
    and appends exactly one well-formed `failed` line with reason
    `merge-unverified`, fields in order event/task/at/reason, an
    RFC3339-with-offset `at`, and the prior bytes are otherwise untouched."""

    def test_appends_exactly_one_failed_line_with_reason_merge_unverified(self):
        task_id = "task0109"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": "task0900", "at": "2026-01-01T00:00:00+00:00"},
                {"event": "launched", "task": task_id, "at": "2026-01-01T00:05:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-01T00:10:00+00:00", "commit": "abc123"},
            ],
        )
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified"])

        self.assertEqual(result.returncode, 0, result.stderr)
        stdout_lines = [l for l in result.stdout.splitlines() if l.strip()]
        self.assertEqual(len(stdout_lines), 1)
        payload = json.loads(stdout_lines[0])
        self.assertEqual(payload, {"outcome": "appended", "task": task_id, "reason": "merge-unverified"})

        after_bytes = read_journal_bytes(self.journal_path)
        self.assertTrue(after_bytes.startswith(before_bytes))
        new_text = after_bytes[len(before_bytes):].decode("utf-8")
        new_lines = [l for l in new_text.splitlines() if l.strip()]
        self.assertEqual(len(new_lines), 1)
        appended = json.loads(new_lines[0])
        self.assertEqual(list(appended.keys()), ["event", "task", "at", "reason"])
        self.assertEqual(appended["event"], "failed")
        self.assertEqual(appended["task"], task_id)
        self.assertEqual(appended["reason"], "merge-unverified")
        self.assertTrue(
            RFC3339_RE.match(appended.get("at", "")),
            f"'at' not RFC3339-with-offset: {appended.get('at')!r}",
        )


class TestMergeUnverifiedAC2NoopOverNonMergedFinalEvents(JournalAppendFailedTestCase):
    """AC-2: for each of the final-event states `launched`, `failed`, no
    event for the task, and an unrecognized event name, `--reason
    merge-unverified` exits 0 with outcome `noop_terminal` and the journal
    is byte-identical to its prior content."""

    def _assert_noop(self, task_id):
        before_bytes = read_journal_bytes(self.journal_path)
        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "noop_terminal")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_noop_over_launched(self):
        task_id = "task0110"
        write_journal(self.journal_path, [{"event": "launched", "task": task_id, "at": "2026-01-02T00:00:00+00:00"}])
        self._assert_noop(task_id)

    def test_noop_over_failed(self):
        task_id = "task0111"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-02T00:00:00+00:00"},
                {"event": "failed", "task": task_id, "at": "2026-01-02T00:05:00+00:00", "reason": "orphaned"},
            ],
        )
        self._assert_noop(task_id)

    def test_noop_over_no_event_for_task(self):
        task_id = "task0112"
        write_journal(
            self.journal_path,
            [{"event": "launched", "task": "task0998", "at": "2026-01-02T00:00:00+00:00"}],
        )
        self._assert_noop(task_id)

    def test_noop_over_unrecognized_event_name(self):
        task_id = "task0113"
        write_journal(self.journal_path, [{"event": "reconciled", "task": task_id, "at": "2026-01-02T00:00:00+00:00"}])
        self._assert_noop(task_id)


class TestMergeUnverifiedAC3ExistingReasonsStillNoopOverMerged(JournalAppendFailedTestCase):
    """AC-3: `orphaned` and `stale-launched` over a final `merged` event
    each report `noop_terminal` with a byte-identical journal (unchanged
    behaviour). `test_final_event_merged_is_noop` (TestAC2TerminalIsNoop)
    already covers `orphaned`; this adds `stale-launched`."""

    def test_stale_launched_over_merged_is_noop(self):
        task_id = "task0114"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-03T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-03T00:10:00+00:00", "commit": "def456"},
            ],
        )
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "stale-launched"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip())["outcome"], "noop_terminal")
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)


class TestMergeUnverifiedAC4ReasonSetAndDocs(JournalAppendFailedTestCase):
    """AC-4: the function-level reason check accepts exactly `orphaned`,
    `stale-launched` and `merge-unverified` (see the updated
    test_valid_reason_accepts_only_the_closed_set) and rejects `manual`,
    the empty string and a non-string; the command-line help output names
    all three values; the module docstring names `merge-unverified`
    together with its merged-only precondition."""

    def test_help_output_names_all_three_reason_values(self):
        result = run_cli(["--help"])

        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("orphaned", "stale-launched", "merge-unverified"):
            self.assertIn(value, result.stdout)

    def test_module_docstring_names_merge_unverified_precondition(self):
        module = load_module()
        doc = module.__doc__ or ""
        self.assertIn("merge-unverified", doc)
        self.assertIn("never over `launched`", doc)


class TestMergeUnverifiedAC5LaunchAtUsageError(JournalAppendFailedTestCase):
    """AC-5: `--reason merge-unverified` supplied together with
    `--launch-at` exits non-zero, prints nothing on stdout, writes a
    diagnostic to stderr, and leaves the journal byte-identical --
    including when the final event is `merged`. The diagnostic identifies
    the merge-unverified/--launch-at combination, distinct from the
    unknown-reason diagnostic (`must be one of`), so this rejection is
    distinguishable from today's unknown-reason rejection."""

    def test_rejected_over_merged_final_event_with_distinct_diagnostic(self):
        task_id = "task0115"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-04T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-04T00:10:00+00:00", "commit": "abc789"},
            ],
        )
        before_bytes = read_journal_bytes(self.journal_path)

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified",
                "--launch-at", "2026-01-04T00:10:00+00:00",
            ]
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip())
        self.assertNotIn("must be one of", result.stderr)
        self.assertIn("launch-at", result.stderr)
        self.assertIn("merge-unverified", result.stderr)
        self.assertEqual(read_journal_bytes(self.journal_path), before_bytes)

    def test_rejected_before_journal_is_opened(self):
        task_id = "task0116"
        # The journal file and its parent directory are never created; if
        # the usage error is decided BEFORE the journal is opened, this
        # exits non-zero via the D4 diagnostic rather than the "journal
        # directory does not exist" diagnostic.
        self.assertFalse(os.path.isdir(self.feature_dir))

        result = run_cli(
            [
                "--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified",
                "--launch-at", "2026-01-04T00:10:00+00:00",
            ]
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("launch-at", result.stderr)
        self.assertFalse(os.path.isdir(self.feature_dir))
        self.assertFalse(os.path.exists(self.journal_path))


class TestMergeUnverifiedAC6Concurrency(JournalAppendFailedTestCase):
    """AC-6: several concurrent `--reason merge-unverified` invocations for
    one task whose final event is `merged` add exactly one `failed` line in
    total; exactly one invocation reports `appended` and every other
    reports `noop_terminal`."""

    def test_concurrent_invocations_over_merged_append_exactly_one(self):
        task_id = "task0117"
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-05T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-05T00:10:00+00:00", "commit": "ghi012"},
            ],
        )

        n = 5
        results = [None] * n

        def invoke(index):
            results[index] = run_cli(
                ["--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified"]
            )

        threads = [threading.Thread(target=invoke, args=(i,)) for i in range(n)]
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
        failed_lines = [
            l for l in lines if json.loads(l).get("event") == "failed" and json.loads(l).get("task") == task_id
        ]
        self.assertEqual(len(failed_lines), 1)

        outcomes = sorted(json.loads(r.stdout.strip())["outcome"] for r in results)
        self.assertEqual(outcomes, ["appended"] + ["noop_terminal"] * (n - 1))


class TestMergeUnverifiedAC7LaunchGuardConvergence(JournalAppendFailedTestCase):
    """AC-7: after a `merge-unverified` `failed` line has been written for a
    task, invoking the unmodified queue_launch_guard.py through its hook
    interface for that task exits 0 with no deny decision, and the task's
    journal last event becomes `launched`. Drives the guard through its
    documented hook interface (subprocess, stdin JSON); does not re-test
    the guard's own rules."""

    def test_launch_after_merge_unverified_failed_is_permitted_and_appends_launched(self):
        task_id = "task0118"
        worktree_path = os.path.join(self.feature_dir, task_id)
        os.makedirs(worktree_path, exist_ok=True)
        write_journal(
            self.journal_path,
            [
                {"event": "launched", "task": task_id, "at": "2026-01-06T00:00:00+00:00"},
                {"event": "merged", "task": task_id, "at": "2026-01-06T00:10:00+00:00", "commit": "jkl345"},
            ],
        )

        recovery = run_cli(["--journal", self.journal_path, "--task", task_id, "--reason", "merge-unverified"])
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
        self.assertNotIn("deny", guard_result.stdout)
        lines = read_journal_lines(self.journal_path)
        last_event_for_task = None
        for line in lines:
            entry = json.loads(line)
            if entry.get("task") == task_id:
                last_event_for_task = entry.get("event")
        self.assertEqual(last_event_for_task, "launched")


if __name__ == "__main__":
    unittest.main()
