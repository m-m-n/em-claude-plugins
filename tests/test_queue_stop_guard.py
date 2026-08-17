"""Subprocess-driven contract tests for em-workflow/hooks/queue_stop_guard.py.

Per test/README.md: hooks are invoked as subprocesses with Claude Code
Stop-hook JSON on stdin; assertions are on exit code and stderr content.
Fixtures are throwaway temp directories shaped like the integration-worktree
layout: `{tmp}/.claude/worktrees/em-workflow/{feature}/integration/
feature-docs/{feature}/workflow.yaml`, with the journal and sidecar at the
worktree-side directory (`{tmp}/.claude/worktrees/em-workflow/{feature}/`).
"""

import ast
import json
import os
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_stop_guard.py")


def build_workflow_yaml(feature, implement_status, task_ids, task_statuses=None):
    """`task_statuses` optionally maps a task id to the value written after
    its own `status:` line. A task id absent from the mapping keeps writing
    `status: pending` (today's fixed text) so every existing call site's
    output is byte-identical. A mapped value of None omits the `status:`
    key entirely (the "absent status key" scenario); a mapped value of ""
    writes `status:` with no value after the colon (the "undeterminable"
    scenario, since a bare colon leaves nothing for a status reader to
    capture)."""
    task_statuses = task_statuses or {}
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
            ]
        )
        if task_id in task_statuses:
            status = task_statuses[task_id]
            if status is not None:
                lines.append(f"    status: {status}")
        else:
            lines.append("    status: pending")
        lines.append("    notes: null")
    return "\n".join(lines) + "\n"


class StopGuardFixture:
    """Builds a throwaway integration-worktree layout for one feature under
    a temp directory standing in for the ancestor whose `.claude/worktrees/
    em-workflow` directory the hook's ancestor walk resolves.

    `docs_segment` lets a test diverge the `feature-docs/<segment>` wildcard
    name from the worktree-side segment (`feature`) — used only by the
    AC-8 single-derivation probe; every other caller leaves it at its
    default (equal to `feature`).
    """

    def __init__(self, tmp_dir, feature="sample-feature", docs_segment=None):
        self.root = tmp_dir
        self.feature = feature
        self.docs_segment = feature if docs_segment is None else docs_segment
        self.worktrees_root = os.path.join(
            self.root, ".claude", "worktrees", "em-workflow"
        )
        # The worktree-side feature directory IS the journal directory
        # (Path Contract) and an ancestor of the enumerated workflow.yaml.
        self.journal_dir = os.path.join(self.worktrees_root, feature)
        self.integration_dir = os.path.join(self.journal_dir, "integration")
        self.docs_dir = os.path.join(
            self.integration_dir, "feature-docs", self.docs_segment
        )
        os.makedirs(self.docs_dir, exist_ok=True)

    def write_workflow(self, implement_status, task_ids, task_statuses=None):
        content = build_workflow_yaml(
            self.docs_segment, implement_status, task_ids, task_statuses=task_statuses
        )
        with open(self.workflow_path(), "w") as fh:
            fh.write(content)

    def write_journal(self, records, raw_extra_lines=None):
        os.makedirs(self.journal_dir, exist_ok=True)
        path = self.journal_path()
        with open(path, "w") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
            for raw_line in raw_extra_lines or []:
                fh.write(raw_line + "\n")
        return path

    def workflow_path(self):
        return os.path.join(self.docs_dir, "workflow.yaml")

    def journal_path(self):
        return os.path.join(self.journal_dir, "journal.jsonl")

    def sidecar_path(self):
        return os.path.join(self.journal_dir, "stop-guard-state.json")


def set_mtime(path, seconds_ago):
    """Pin a file's modification time explicitly to `seconds_ago` before
    the real wall-clock now, so freshness assertions never sit near the
    24-hour boundary (Test Notes)."""
    stamp = time.time() - seconds_ago
    os.utime(path, (stamp, stamp))


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


class TestQueueStopGuardRealLayoutAncestorWalk(unittest.TestCase):
    """AC-1: byte-identical stderr and exit code whether the working
    directory is the fixture root or the integration-worktree directory
    inside it — a statement about the ancestor walk, not the message
    format (Test Notes)."""

    def test_blocks_identically_from_fixture_root_and_integration_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([])

            from_root = invoke_hook(tmp, DEFAULT_STDIN)
            from_integration = invoke_hook(fx.integration_dir, DEFAULT_STDIN)

            self.assertEqual(from_root.returncode, 2)
            self.assertEqual(from_integration.returncode, from_root.returncode)
            self.assertEqual(from_integration.stderr, from_root.stderr)
            self.assertIn("sample-feature", from_root.stderr)
            self.assertIn("task0001", from_root.stderr)
            self.assertIn("task0002", from_root.stderr)

    def test_blocks_from_a_deep_subdirectory_of_the_integration_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001"])
            fx.write_journal([])
            deep_cwd = os.path.join(fx.integration_dir, "some", "nested", "cwd")
            os.makedirs(deep_cwd, exist_ok=True)

            result = invoke_hook(deep_cwd, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("task0001", result.stderr)


class TestQueueStopGuardFreshness(unittest.TestCase):
    """AC-2: an abandoned integration worktree is excluded regardless of an
    in_progress implement step and unlaunched tasks; a fresh one still
    blocks. Times are set explicitly to "now" / "now minus 25 hours" so no
    assertion sits near the 24-hour threshold."""

    def test_stale_journal_mtime_excludes_despite_unlaunched_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            fx.write_journal([])
            set_mtime(fx.journal_path(), seconds_ago=25 * 60 * 60)

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_fresh_journal_mtime_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            fx.write_journal([])
            set_mtime(fx.journal_path(), seconds_ago=0)

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)

    def test_no_journal_file_falls_back_to_stale_workflow_yaml_mtime_and_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            # journal.jsonl intentionally never written; journal_dir exists
            # (it is an ancestor of workflow.yaml's own path).
            set_mtime(fx.workflow_path(), seconds_ago=25 * 60 * 60)

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_no_journal_file_falls_back_to_fresh_workflow_yaml_mtime_and_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            set_mtime(fx.workflow_path(), seconds_ago=0)

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)


class TestQueueStopGuardLayoutIsolation(unittest.TestCase):
    """AC-3: nothing outside the integration-worktree layout is ever
    enumerated."""

    def test_flat_main_tree_workflow_yaml_is_never_enumerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A valid enumeration root exists (so the ancestor walk
            # succeeds), but the only workflow.yaml lives at the OLD flat
            # main-tree path -- it must never be picked up. A readable,
            # empty journal is present at the worktree-side directory so
            # that, if the flat file WERE (wrongly) enumerated, the hook
            # would reach an actual BLOCK decision rather than bailing out
            # for an unrelated missing-journal reason -- this is what makes
            # the assertion a genuine statement about layout isolation.
            os.makedirs(os.path.join(tmp, ".claude", "worktrees", "em-workflow"))
            flat_docs_dir = os.path.join(tmp, "feature-docs", "sample-feature")
            os.makedirs(flat_docs_dir)
            content = build_workflow_yaml(
                "sample-feature", "in_progress", ["task0001", "task0002"]
            )
            with open(os.path.join(flat_docs_dir, "workflow.yaml"), "w") as fh:
                fh.write(content)
            journal_dir = os.path.join(
                tmp, ".claude", "worktrees", "em-workflow", "sample-feature"
            )
            os.makedirs(journal_dir)
            open(os.path.join(journal_dir, "journal.jsonl"), "w").close()

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_no_worktrees_directory_anywhere_above_cwd_passes_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A bare, freshly created temp directory with nothing in it: no
            # .claude/worktrees/em-workflow anywhere above it. A fresh
            # tempfile.TemporaryDirectory() per test avoids a shared
            # temporary parent accidentally supplying one (Test Notes).
            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertNotIn("Traceback", result.stderr)


class TestQueueStopGuardFailedTask(unittest.TestCase):
    """AC-2 (fail-open surface): a genuinely failed task suppresses
    blocking even with capacity.

    task0001's own workflow status is explicitly non-pending here so this
    exercises a genuine failure, not the recycled-task-id carve-out (see
    TestQueueStopGuardRecycledTaskId for that discriminator)."""

    def test_failed_task_present_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow(
                "in_progress", task_ids, task_statuses={"task0001": "failed"}
            )
            fx.write_journal([failed("task0001")])  # task0002/3 unlaunched, free slots plenty

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)


class TestQueueStopGuardNonBlockingStates(unittest.TestCase):
    """Full slots / zero pending / no active feature."""

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
    """Cap at 3 consecutive blocks in the same state; state change resets."""

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
    """Missing journal / malformed journal lines / malformed stdin /
    missing worktree layout never crash and never block."""

    def test_missing_journal_directory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Under the real layout, the worktree-side feature directory IS
            # the journal directory and an ancestor of the enumerated
            # workflow.yaml path -- so "journal directory absent" now
            # coincides with "the whole feature subdirectory was never
            # created". Only worktrees_root itself exists (the ancestor
            # walk still succeeds); no feature subdirectory beneath it, so
            # nothing is enumerated.
            os.makedirs(os.path.join(tmp, ".claude", "worktrees", "em-workflow"))

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
            # An entirely empty project root: no .claude/worktrees at all.
            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)


class TestQueueStopGuardRetryAfterFailure(unittest.TestCase):
    """failed -> launched (retry) counts as in-flight, not failed/unlaunched."""

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


class TestQueueStopGuardRecycledTaskId(unittest.TestCase):
    """Recycled-task-id carve-out: a `failed` journal last event whose
    task's own workflow status still reads `pending` is a retired id from a
    route-back re-plan, not a genuine failure."""

    def test_retired_task_id_with_pending_status_is_unlaunched_and_blocks(self):
        # The residual `failed` event for task0001 must not suppress the
        # feature once its own status is still `pending`.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow("in_progress", task_ids)  # all default to pending
            fx.write_journal([failed("task0001")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("free_slots=6", result.stderr)
            for expected in ("task0001", "task0002", "task0003"):
                self.assertIn(expected, result.stderr)

    def test_failed_task_with_non_pending_status_still_suppresses(self):
        # Every genuine-failure status value keeps suppressing.
        for status in ("failed", "in_progress", "merged", "cancelled"):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = StopGuardFixture(tmp)
                    task_ids = ["task0001", "task0002", "task0003"]
                    fx.write_workflow(
                        "in_progress", task_ids, task_statuses={"task0001": status}
                    )
                    fx.write_journal([failed("task0001")])

                    result = invoke_hook(tmp, DEFAULT_STDIN)

                    self.assertEqual(result.returncode, 0)

    def test_failed_task_with_absent_status_key_still_suppresses(self):
        # No `status:` key at all in the task's own block.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow(
                "in_progress", task_ids, task_statuses={"task0001": None}
            )
            fx.write_journal([failed("task0001")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_failed_task_with_undeterminable_status_still_suppresses(self):
        # A `status:` line whose value cannot be captured (bare colon,
        # nothing after it).
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow(
                "in_progress", task_ids, task_statuses={"task0001": ""}
            )
            fx.write_journal([failed("task0001")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_mixed_retired_and_genuinely_failed_tasks_suppresses(self):
        # A retired id (pending) alongside a genuine failure -- the whole
        # feature still suppresses because of the genuine failure.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow(
                "in_progress", task_ids, task_statuses={"task0002": "failed"}
            )
            fx.write_journal([failed("task0001"), failed("task0002")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_status_scoped_to_own_task_block_not_confused_with_step_status(self):
        # The per-task status read must not pick up a workflow-step status
        # line. "skipped" is a real step-status value elsewhere in the
        # fixture (the `design` step); used here as a TASK status it is
        # simply an unrecognized value, not `pending`, so it must still
        # suppress rather than be silently reclassified.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow(
                "in_progress", task_ids, task_statuses={"task0001": "skipped"}
            )
            fx.write_journal([failed("task0001")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 0)

    def test_task_id_absent_from_tasks_mapping_is_ignored_even_if_failed_in_journal(self):
        # Any journal state for a task id not declared under `tasks:` is
        # not evaluated at all -- it must not suppress the feature nor
        # appear in the launch list.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002"]
            fx.write_workflow("in_progress", task_ids)
            fx.write_journal([failed("task9999")])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("task0001", result.stderr)
            self.assertIn("task0002", result.stderr)
            self.assertNotIn("task9999", result.stderr)

    def test_retired_task_participates_in_free_slot_arithmetic_and_bounded_list(self):
        # A reclassified (retired) task counts as unlaunched for free-slot
        # arithmetic and the ascending bounded launch list, same as any
        # other unlaunched task.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = [f"task{i:04d}" for i in range(1, 9)]  # 8 tasks
            fx.write_workflow("in_progress", task_ids)  # all pending
            # task0001 is a retired id (pending); task0006-8 in-flight ->
            # free_slots = 6 - 3 = 3; unlaunched = task0001..task0005 (5),
            # bounded ascending list = task0001, task0002, task0003.
            fx.write_journal(
                [
                    failed("task0001"),
                    launched("task0006"),
                    launched("task0007"),
                    launched("task0008"),
                ]
            )

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("free_slots=3", result.stderr)
            for expected in ("task0001", "task0002", "task0003"):
                self.assertIn(expected, result.stderr)
            for not_expected in ("task0004", "task0005", "task0006", "task0007", "task0008"):
                self.assertNotIn(not_expected, result.stderr)

    def test_consecutive_block_cap_still_works_with_reclassified_task(self):
        # The cap/fingerprint machinery downstream of classification is
        # unaffected by a reclassified task being present.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            task_ids = ["task0001", "task0002", "task0003"]
            fx.write_workflow("in_progress", task_ids)  # all pending
            fx.write_journal([failed("task0001")])  # retired id, reclassified unlaunched

            for i in range(1, 4):
                result = invoke_hook(tmp, DEFAULT_STDIN)
                self.assertEqual(result.returncode, 2, f"block #{i} should block")

            fourth = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(fourth.returncode, 0)
            self.assertIn("WARNING", fourth.stderr)

            # A real state change (task0001 now launched) re-arms blocking.
            fx.write_journal([launched("task0001")])
            after_change = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(after_change.returncode, 2)


class TestQueueStopGuardStdlibOnly(unittest.TestCase):
    """AC-7: the script imports only Python stdlib modules and spawns no
    process; no reference to the removed repository-top-level probe."""

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

    def test_no_process_spawning_facility_or_repo_toplevel_probe_referenced(self):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            source = fh.read()

        self.assertNotIn("subprocess", source)
        self.assertNotIn("rev-parse", source)
        self.assertNotIn("show-toplevel", source)
        self.assertNotIn("find_project_root", source)


class TestQueueStopGuardSingleDerivation(unittest.TestCase):
    """AC-8: feature identity is derived exactly once. A probe fixture
    whose worktree-side segment name differs from its feature-docs segment
    name must block, name the worktree-side segment as the feature, and
    prove it read the enumerated file -- which fails if any read path is
    rebuilt from an enumeration root plus a feature name."""

    def test_divergent_worktree_and_docs_segment_names_reads_the_enumerated_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(
                tmp, feature="worktree-segment", docs_segment="unrelated-docs-name"
            )
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            fx.write_journal([])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("worktree-segment", result.stderr)
            self.assertNotIn("unrelated-docs-name", result.stderr)
            self.assertIn("task0001", result.stderr)
            self.assertIn("task0002", result.stderr)


class TestQueueStopGuardMultiFeatureOrdering(unittest.TestCase):
    """AC-5: with two features enumerated at once, both in_progress and
    both refillable, the hook reports the first by stable ascending
    feature-name ordering."""

    def test_two_features_reports_first_by_ascending_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx_a = StopGuardFixture(tmp, feature="feature-a")
            fx_b = StopGuardFixture(tmp, feature="feature-b")
            fx_a.write_workflow("in_progress", ["task0001"])
            fx_a.write_journal([])
            fx_b.write_workflow("in_progress", ["task0001"])
            fx_b.write_journal([])

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("feature-a", result.stderr)
            self.assertNotIn("feature-b", result.stderr)


class TestQueueStopGuardReviewRound1Regressions(unittest.TestCase):
    """Review round 1 regressions (FR4)."""

    def test_journal_file_absent_but_directory_present_blocks(self):
        # The worktree layout exists (implement started) but no launch was
        # ever recorded: every declared task is unlaunched -- a forgotten
        # INITIAL launch must be caught, not silently passed.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            # journal_dir already exists (ancestor of workflow.yaml); no
            # journal.jsonl written.

            result = invoke_hook(tmp, DEFAULT_STDIN)

            self.assertEqual(result.returncode, 2)
            self.assertIn("task0001", result.stderr)
            self.assertIn("task0002", result.stderr)

    def test_stops_after_cap_keep_passing_in_same_state(self):
        # FR4: once the cap is hit, the guard must NOT resume blocking the
        # same unchanged state (the user has taken over) -- only a real
        # state change re-arms it.
        with tempfile.TemporaryDirectory() as tmp:
            fx = StopGuardFixture(tmp)
            fx.write_workflow("in_progress", ["task0001", "task0002"])
            fx.write_journal([])

            for i in range(1, 4):
                result = invoke_hook(tmp, DEFAULT_STDIN)
                self.assertEqual(result.returncode, 2, f"block #{i} should block")

            for i in range(4, 7):
                result = invoke_hook(tmp, DEFAULT_STDIN)
                self.assertEqual(
                    result.returncode, 0,
                    f"stop #{i} in the same state must keep passing after the cap",
                )
                self.assertIn("WARNING", result.stderr)

            # A real state change re-arms blocking.
            fx.write_journal([launched("task0001")])
            after_change = invoke_hook(tmp, DEFAULT_STDIN)
            self.assertEqual(after_change.returncode, 2)


if __name__ == "__main__":
    unittest.main()
