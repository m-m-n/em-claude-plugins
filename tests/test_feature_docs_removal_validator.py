"""Tests for task0006 of plan-feature-docs-route: the validator side of the
feature-docs correction, the patch field `tasks_patch.feature_docs_removals`
(IMPLEMENTATION.md D7).

Acceptance Criteria covered (feature-docs/plan-feature-docs-route/tasks/
task0006.md):

- AC-5 (TM-4): each `feature-docs-removal-*` code is produced by its failing
  case and absent from the passing case; a `failed` target is accepted and an
  `in_progress` task is rejected.
- AC-6 (TS-8, TM-4): the in-memory application, the plan agreement and the
  inputs that --dry-run-apply needs.
- TS-9 (NFR2): a malformed field is an error, never an exception.

The workflows and the plans are built in a temporary directory; the tests use
the standard library and unittest only (NFR3).
"""

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

THREAT_MODEL = "feature-docs/call-end-history/THREAT-MODEL.md"
NOTES = "feature-docs/other/NOTES.md"
THIRD = "feature-docs/third/DESIGN.md"

DIGEST_SOURCE = {
    "answers_digest": "sha256:" + "2" * 64,
    "digest_inputs": {"feature-docs/demo/SPEC.md": "sha256:" + "1" * 64},
    "mode": "interactive",
    "value_inputs": {"task_description": None},
    "worker": "implementation-planner",
    "workflow_blob": "8f17c04",
    "write_policy_digest": "sha256:" + "3" * 64,
}

PRESERVE = ("workflow.implement.base_commit",)


def plan_text(task_id, files):
    bullets = "".join(f"- `{f}` - file\n" for f in files)
    return (
        f"# Task Plan: {task_id} - title\n\n## Scope\n\n### Files to Modify\n{bullets}\n"
        "## Acceptance Criteria (MANDATORY)\n\n- [ ] AC-1: it works.\n"
    )


def make_workflow(*, create_plan="completed", implement="failed", statuses=None, files=None):
    statuses = statuses or {"task0001": "failed", "task0002": "pending", "task0003": "merged"}
    files = files or {
        "task0001": [THREAT_MODEL, "src/a.py"],
        "task0002": [NOTES, "src/b.py"],
        "task0003": [THIRD, "src/c.py"],
    }

    def record(task_id):
        return {
            "title": f"title of {task_id}",
            "plan": f"tasks/{task_id}.md",
            "files": list(files[task_id]),
            "skills": ["backend-impl"],
            "domains": ["input-handling"],
            "complexity": "low",
            "requirements": ["FR1"],
            "status": statuses[task_id],
            "notes": "failed: kept for the test" if statuses[task_id] == "failed" else None,
            "branch": f"em-workflow/demo/{task_id}",
            "routeback_failed_journal_line": 7,
        }

    return {
        "schema_version": 1,
        "feature": "demo",
        "project": {"license": "MIT"},
        "requirements": {"FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}},
        "workflow": [
            {"id": "create-spec", "status": "completed", "completed_at_commit": "aaa"},
            {"id": "design", "status": "skipped", "skipped_reason": "no UI"},
            {"id": "create-plan", "status": create_plan},
            {"id": "implement", "status": implement, "base_commit": "b" * 40},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
        "tasks": {task_id: record(task_id) for task_id in statuses},
    }


def removal(task_id, path):
    return {"task_id": task_id, "path": path}


GOOD_REMOVALS = [removal("task0001", THREAT_MODEL), removal("task0002", NOTES)]


def make_patch(removals, *, carried=("task0001", "task0002", "task0003"), entries=None, step_patches=None,
               requirements_patch=None, operation="replace_planning", path_corrections=None,
               preserve=PRESERVE):
    tasks_patch = {
        "mode": "replace_all" if operation == "replace_planning" else "append",
        "carried_task_ids": list(carried),
        "entries": entries or {},
    }
    if operation == "append_rework":
        tasks_patch["expected_next_task_id"] = "task0004"
    if removals is not None:
        tasks_patch["feature_docs_removals"] = removals
    if path_corrections is not None:
        tasks_patch["path_corrections"] = path_corrections
    return {
        "schema_version": 1,
        "patch_id": "create-plan-p0001",
        "base_input_digest": VWO.normalize_json_sha256(DIGEST_SOURCE),
        "base_workflow_blob": DIGEST_SOURCE["workflow_blob"],
        "operation": operation,
        "tasks_patch": tasks_patch,
        "requirements_patch": requirements_patch,
        "step_patches": step_patches or [],
        "preserve": list(preserve),
    }


def codes(errors):
    return [e["code"] for e in errors]


def removal_codes(errors):
    return [c for c in codes(errors) if c.startswith("feature-docs-removal")]


class Fixture(unittest.TestCase):
    """A feature directory whose plans already agree with the corrected files,
    a journal, and the helpers that run the validator on them."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.feature_dir = self.tmp / "feature-docs" / "demo"
        (self.feature_dir / "tasks").mkdir(parents=True)
        self.write_plan("task0001", ["src/a.py"])
        self.write_plan("task0002", ["src/b.py"])
        self.write_plan("task0003", [THIRD, "src/c.py"])
        self.journal = self.tmp / "journal.jsonl"
        self.write_journal([
            ("task0001", "launched"), ("task0001", "failed"),
            ("task0003", "launched"), ("task0003", "merged"),
        ])
        self.workflow = make_workflow()

    def write_plan(self, task_id, files):
        (self.feature_dir / "tasks" / f"{task_id}.md").write_text(plan_text(task_id, files), encoding="utf-8")

    def write_journal(self, events):
        self.journal.write_text(
            "".join(json.dumps({"task": t, "event": e}) + "\n" for t, e in events), encoding="utf-8"
        )

    def validate(self, patch, workflow=None, *, dry_run=True, journal="default", feature_dir="default",
                 phase_state=None):
        workflow = self.workflow if workflow is None else workflow
        kwargs = {}
        if dry_run:
            kwargs = dict(
                digest_source=DIGEST_SOURCE,
                phase_state=phase_state,
                dry_run=True,
                feature_dir=self.feature_dir if feature_dir == "default" else feature_dir,
                journal=self.journal if journal == "default" else journal,
            )
        return VWO.validate_workflow_patch(patch, workflow=workflow, **kwargs)

    def good_patch(self):
        return make_patch(copy.deepcopy(GOOD_REMOVALS))


# ---------------------------------------------------------------------------
# The passing case (AC-5: a failed target is accepted)
# ---------------------------------------------------------------------------

class TestPassingCase(Fixture):
    def test_a_valid_patch_on_the_correction_entry_passes(self):
        self.assertEqual(self.validate(self.good_patch()), [])

    def test_a_failed_target_is_accepted(self):
        self.assertEqual(self.workflow["tasks"]["task0001"]["status"], "failed")
        self.assertNotIn("replace-all-not-permitted", codes(self.validate(self.good_patch())))
        self.assertEqual(removal_codes(self.validate(self.good_patch())), [])

    def test_the_structural_check_passes_without_dry_run(self):
        self.assertEqual(self.validate(self.good_patch(), dry_run=False), [])

    def test_a_patch_without_the_field_is_unchanged_in_every_state(self):
        # A replace_all without the field behaves as before (D7).
        states = {
            "correction entry": make_workflow(),
            "initial planning": make_workflow(
                create_plan="pending", implement="pending",
                statuses={"task0001": "pending", "task0002": "pending", "task0003": "pending"}),
            "re-planning": make_workflow(create_plan="needs_update", implement="pending",
                                         statuses={"task0001": "pending", "task0002": "pending", "task0003": "merged"}),
        }
        for label, workflow in states.items():
            with self.subTest(label):
                errors = self.validate(make_patch(None), workflow)
                self.assertEqual(removal_codes(errors), [])
        # The correction entry without a correction field is still not a
        # permitted replace_all.
        self.assertIn("replace-all-not-permitted", codes(self.validate(make_patch(None), states["correction entry"])))

    def test_null_and_absent_are_the_same(self):
        patch = make_patch(None)
        patch["tasks_patch"]["feature_docs_removals"] = None
        self.assertEqual(removal_codes(self.validate(patch, dry_run=False)), [])
        self.assertEqual(removal_codes(self.validate(make_patch(None), dry_run=False)), [])


# ---------------------------------------------------------------------------
# AC-5: feature-docs-removal-shape (with and without --dry-run-apply)
# ---------------------------------------------------------------------------

class TestShape(Fixture):
    def test_malformed_fields_are_feature_docs_removal_shape(self):
        cases = {
            "not a list": "oops",
            "a mapping": {"task_id": "task0001", "path": THREAT_MODEL},
            "empty list": [],
            "item not a mapping": ["x"],
            "extra key": [dict(removal("task0001", THREAT_MODEL), note="x")],
            "missing path": [{"task_id": "task0001"}],
            "missing task_id": [{"path": THREAT_MODEL}],
            "non-string path": [removal("task0001", 3)],
            "non-string task_id": [removal(7, THREAT_MODEL)],
            "unhashable task_id": [removal(["task0001"], THREAT_MODEL)],
            "task not carried": [removal("task0009", THREAT_MODEL)],
            "repeated pair": [removal("task0001", THREAT_MODEL), removal("task0001", THREAT_MODEL)],
        }
        for label, field in cases.items():
            for dry_run in (False, True):
                with self.subTest(label, dry_run=dry_run):
                    errors = self.validate(make_patch(field), dry_run=dry_run)
                    self.assertIn("feature-docs-removal-shape", codes(errors), errors)

    def test_a_task_that_is_not_carried_is_rejected_even_when_registered(self):
        patch = make_patch(copy.deepcopy(GOOD_REMOVALS), carried=("task0001", "task0003"))
        self.assertIn("feature-docs-removal-shape", codes(self.validate(patch, dry_run=False)))

    def test_use_with_path_corrections_is_rejected(self):
        patch = make_patch(
            copy.deepcopy(GOOD_REMOVALS),
            path_corrections=[{"task_id": "task0001", "old_path": "a/B.md", "new_path": "a/c.md"}],
        )
        self.assertIn("feature-docs-removal-shape", codes(self.validate(patch, dry_run=False)))

    def test_use_on_append_rework_is_rejected(self):
        patch = make_patch(copy.deepcopy(GOOD_REMOVALS), operation="append_rework")
        self.assertIn("feature-docs-removal-shape", codes(self.validate(patch, dry_run=False)))

    def test_the_same_path_on_two_tasks_is_not_a_duplicate(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "src/a.py"], "task0002": [THREAT_MODEL, "src/b.py"], "task0003": ["src/c.py"],
        })
        self.write_plan("task0003", ["src/c.py"])
        patch = make_patch([removal("task0001", THREAT_MODEL), removal("task0002", THREAT_MODEL)])
        self.assertEqual(self.validate(patch, workflow), [])

    def test_a_malformed_field_never_raises_and_applies_nothing(self):
        for field in ("oops", [], ["x"], [removal(7, 8)], [removal(["a"], ["b"])], {"a": 1}):
            with self.subTest(field=field):
                patch = make_patch(field)
                VWO.validate_workflow_patch(patch, workflow=self.workflow)
                new = VWO.apply_patch(self.workflow, patch)
                self.assertEqual(new["tasks"]["task0001"], self.workflow["tasks"]["task0001"])
                self.assertEqual(new["tasks"]["task0002"], self.workflow["tasks"]["task0002"])


# ---------------------------------------------------------------------------
# AC-5: feature-docs-removal-not-permitted
# ---------------------------------------------------------------------------

class TestPermission(Fixture):
    def assert_not_permitted(self, workflow, phase_state=None):
        errors = self.validate(self.good_patch(), workflow, phase_state=phase_state)
        self.assertIn("feature-docs-removal-not-permitted", codes(errors), errors)

    def test_the_initial_planning_state_is_not_permitted(self):
        workflow = make_workflow(
            create_plan="pending", implement="pending",
            statuses={"task0001": "pending", "task0002": "pending", "task0003": "pending"})
        self.assert_not_permitted(workflow)

    def test_the_replanning_state_is_not_permitted(self):
        workflow = make_workflow(
            create_plan="needs_update", implement="pending",
            statuses={"task0001": "pending", "task0002": "pending", "task0003": "merged"})
        self.assert_not_permitted(workflow)

    def test_a_spec_change_reentry_is_not_permitted(self):
        workflow = make_workflow(
            create_plan="pending", implement="pending",
            statuses={"task0001": "pending", "task0002": "pending", "task0003": "merged"})
        phase_state = {
            "phase": "rework", "feature": "demo",
            "spec_change": {"reason": "r", "origin_kind": "review", "origin_id": "x",
                            "recorded_at_commit": "abc", "replan_authorized": True},
        }
        self.assert_not_permitted(workflow, phase_state)

    def test_other_states_are_not_permitted(self):
        for create_plan, implement in (("completed", "completed"), ("completed", "pending"),
                                       ("completed", "in_progress"), ("skipped", "failed")):
            with self.subTest(create_plan=create_plan, implement=implement):
                self.assert_not_permitted(make_workflow(create_plan=create_plan, implement=implement))

    def test_the_correction_entry_is_permitted(self):
        self.assertNotIn("feature-docs-removal-not-permitted", codes(self.validate(self.good_patch())))

    def test_an_in_progress_task_is_rejected_on_the_correction_entry(self):
        workflow = make_workflow(statuses={"task0001": "failed", "task0002": "in_progress", "task0003": "merged"})
        errors = self.validate(self.good_patch(), workflow)
        self.assertIn("feature-docs-removal-in-flight", codes(errors))
        self.assertIn("replace-all-not-permitted", codes(errors))
        self.assertNotIn("feature-docs-removal-not-permitted", codes(errors))

    def test_the_replanning_obligations_still_apply_on_the_correction_entry(self):
        patch = self.good_patch()
        patch["preserve"] = []
        self.assertIn("preserve", codes(self.validate(patch)))
        patch = make_patch(copy.deepcopy(GOOD_REMOVALS), carried=("task0001", "task0002"))
        self.assertIn("replace-all-drops-task", codes(self.validate(patch)))
        patch = make_patch(copy.deepcopy(GOOD_REMOVALS), carried=("task0001", "task0002", "task0003", "task0009"))
        self.assertIn("replace-all-carried-id-unregistered", codes(self.validate(patch)))
        patch = make_patch(copy.deepcopy(GOOD_REMOVALS), entries={"task0002": {"title": "x"}})
        self.assertIn("replace-all-entry-for-registered-id", codes(self.validate(patch)))


# ---------------------------------------------------------------------------
# AC-5: the precondition conditions
# ---------------------------------------------------------------------------

class TestPreconditions(Fixture):
    def test_in_flight_a_task_in_progress(self):
        workflow = make_workflow(statuses={"task0001": "failed", "task0002": "in_progress", "task0003": "merged"})
        errors = [e for e in self.validate(self.good_patch(), workflow) if e["code"] == "feature-docs-removal-in-flight"]
        self.assertEqual([e["task_id"] for e in errors], ["task0002"])

    def test_in_flight_a_launched_last_event(self):
        self.write_journal([("task0001", "failed"), ("task0002", "launched")])
        errors = [e for e in self.validate(self.good_patch()) if e["code"] == "feature-docs-removal-in-flight"]
        self.assertEqual([e["task_id"] for e in errors], ["task0002"])

    def test_in_flight_applies_to_a_task_that_is_not_a_target(self):
        self.write_journal([("task0003", "launched")])
        self.assertIn("feature-docs-removal-in-flight", codes(self.validate(self.good_patch())))

    def test_merged_by_the_last_journal_event(self):
        self.write_journal([("task0001", "failed"), ("task0002", "launched"), ("task0002", "merged")])
        errors = [e for e in self.validate(self.good_patch()) if e["code"] == "feature-docs-removal-merged"]
        self.assertEqual([e["task_id"] for e in errors], ["task0002"])

    def test_merged_by_the_status(self):
        workflow = make_workflow(statuses={"task0001": "failed", "task0002": "merged", "task0003": "merged"})
        errors = [e for e in self.validate(self.good_patch(), workflow) if e["code"] == "feature-docs-removal-merged"]
        self.assertEqual([e["task_id"] for e in errors], ["task0002"])

    def test_a_merged_task_that_is_not_a_target_does_not_matter(self):
        self.assertNotIn("feature-docs-removal-merged", codes(self.validate(self.good_patch())))

    def test_path_that_is_not_a_feature_docs_path(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "src/a.py"], "task0002": [NOTES, "src/b.py"], "task0003": [THIRD, "src/c.py"],
        })
        for path in ("src/a.py", "feature-docs-archive/x.md", "src/feature-docs/x.md", "Feature-Docs/x.md"):
            with self.subTest(path):
                workflow["tasks"]["task0001"]["files"] = [THREAT_MODEL, path]
                patch = make_patch([removal("task0001", path), removal("task0002", NOTES)])
                errors = [e for e in self.validate(patch, workflow) if e["code"] == "feature-docs-removal-path"]
                self.assertEqual([(e["task_id"], e["path"]) for e in errors], [("task0001", path)])

    def test_path_that_is_not_in_the_target_files(self):
        patch = make_patch([removal("task0001", "feature-docs/other/ABSENT.md"), removal("task0002", NOTES)])
        errors = [e for e in self.validate(patch) if e["code"] == "feature-docs-removal-path"]
        self.assertEqual([(e["task_id"], e["path"]) for e in errors], [("task0001", "feature-docs/other/ABSENT.md")])

    def test_path_is_compared_as_given(self):
        patch = make_patch([removal("task0001", "./" + THREAT_MODEL), removal("task0002", NOTES)])
        self.assertIn("feature-docs-removal-path", codes(self.validate(patch)))

    def test_empty_files_when_every_path_of_the_target_is_removed(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "feature-docs/x/Y.md"], "task0002": [NOTES, "src/b.py"], "task0003": ["src/c.py"],
        })
        patch = make_patch([removal("task0001", THREAT_MODEL), removal("task0001", "feature-docs/x/Y.md"),
                            removal("task0002", NOTES)])
        errors = [e for e in self.validate(patch, workflow) if e["code"] == "feature-docs-removal-empty-files"]
        self.assertEqual([e["task_id"] for e in errors], ["task0001"])

    def test_empty_files_is_judged_after_every_path_named_for_the_target(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "feature-docs/x/Y.md", "src/a.py"], "task0002": [NOTES, "src/b.py"],
            "task0003": ["src/c.py"],
        })
        self.write_plan("task0001", ["src/a.py"])
        patch = make_patch([removal("task0001", THREAT_MODEL), removal("task0001", "feature-docs/x/Y.md"),
                            removal("task0002", NOTES)])
        self.assertEqual(removal_codes(self.validate(patch, workflow)), [])

    def test_empty_files_when_a_repeated_path_is_the_only_entry(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, THREAT_MODEL], "task0002": [NOTES, "src/b.py"], "task0003": ["src/c.py"],
        })
        patch = make_patch([removal("task0001", THREAT_MODEL), removal("task0002", NOTES)])
        self.assertIn("feature-docs-removal-empty-files", codes(self.validate(patch, workflow)))

    def test_incomplete_when_an_unmerged_task_keeps_a_feature_docs_path(self):
        patch = make_patch([removal("task0001", THREAT_MODEL)])
        errors = [e for e in self.validate(patch) if e["code"] == "feature-docs-removal-incomplete"]
        self.assertEqual([e["task_id"] for e in errors], ["task0002"])

    def test_incomplete_leaves_a_merged_task_alone(self):
        self.assertEqual(self.workflow["tasks"]["task0003"]["files"][0], THIRD)
        self.assertNotIn("feature-docs-removal-incomplete", codes(self.validate(self.good_patch())))

    def test_incomplete_when_one_of_two_paths_of_a_task_is_left(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "feature-docs/x/Y.md", "src/a.py"], "task0002": [NOTES, "src/b.py"],
            "task0003": [THIRD, "src/c.py"],
        })
        self.write_plan("task0001", ["feature-docs/x/Y.md", "src/a.py"])
        patch = make_patch([removal("task0001", THREAT_MODEL), removal("task0002", NOTES)])
        errors = [e for e in self.validate(patch, workflow) if e["code"] == "feature-docs-removal-incomplete"]
        self.assertEqual([e["task_id"] for e in errors], ["task0001"])

    def test_limits_for_each_breach(self):
        cases = {
            "entries": make_patch(copy.deepcopy(GOOD_REMOVALS), entries={
                "task0004": {"title": "x", "plan": "tasks/task0004.md", "files": ["src/d.py"], "skills": [],
                             "domains": [], "complexity": "low", "requirements": ["FR1"],
                             "initial_status": "pending"}}),
            "step_patches": make_patch(copy.deepcopy(GOOD_REMOVALS), step_patches=[
                {"step_id": "implement", "expected": {"status": "failed"}, "set": {"status": "pending"}}]),
            "requirements_patch": make_patch(copy.deepcopy(GOOD_REMOVALS), requirements_patch={
                "mode": "merge_entries", "entries": {"FR1": {"set": {"tasks_append": ["task0001"]}}}}),
        }
        for label, patch in cases.items():
            with self.subTest(label):
                errors = self.validate(patch)
                self.assertIn("feature-docs-removal-limits", codes(errors), errors)

    def test_limits_admit_a_null_or_entryless_requirements_patch(self):
        for requirements_patch in (None, {}, {"mode": "merge_entries", "entries": {}}):
            with self.subTest(requirements_patch=requirements_patch):
                patch = make_patch(copy.deepcopy(GOOD_REMOVALS), requirements_patch=requirements_patch)
                self.assertEqual(removal_codes(self.validate(patch)), [])

    def test_each_code_is_absent_from_the_passing_case(self):
        self.assertEqual(removal_codes(self.validate(self.good_patch())), [])

    def test_the_precondition_function_takes_the_workflow_removals_and_last_events(self):
        last_events = VWO.journal_last_events(self.journal)
        self.assertEqual(
            VWO.feature_docs_removal_precondition_errors(self.workflow, copy.deepcopy(GOOD_REMOVALS), last_events), [])
        errors = VWO.feature_docs_removal_precondition_errors(
            self.workflow,
            [removal("task0001", "src/a.py"), removal("task0003", THIRD), removal("task0009", THREAT_MODEL)],
            dict(last_events, task0002=("launched", 9)),
        )
        self.assertEqual(
            sorted(set(codes(errors))),
            ["feature-docs-removal-in-flight", "feature-docs-removal-merged", "feature-docs-removal-path"],
        )

    def test_the_precondition_function_never_raises_on_malformed_input(self):
        for workflow in (None, {}, {"tasks": []}, {"tasks": {"task0001": "oops"}}, {"tasks": {"task0001": {"files": 3}}}):
            for removals in ([], [removal("task0001", THREAT_MODEL)], [{"task_id": 1}], ["x"], [None]):
                with self.subTest(workflow=workflow, removals=removals):
                    errors = VWO.feature_docs_removal_precondition_errors(workflow, removals, None)
                    self.assertIsInstance(errors, list)


# ---------------------------------------------------------------------------
# AC-6: the application
# ---------------------------------------------------------------------------

class TestApplication(Fixture):
    def test_every_occurrence_of_the_path_leaves_files_and_notes_becomes_null(self):
        workflow = make_workflow(files={
            "task0001": [THREAT_MODEL, "src/a.py", THREAT_MODEL, "src/z.py"], "task0002": [NOTES, "src/b.py"],
            "task0003": [THIRD, "src/c.py"],
        })
        new = VWO.apply_patch(workflow, self.good_patch())
        self.assertEqual(new["tasks"]["task0001"]["files"], ["src/a.py", "src/z.py"])
        self.assertEqual(new["tasks"]["task0002"]["files"], ["src/b.py"])
        for task_id in ("task0001", "task0002"):
            self.assertIsNone(new["tasks"][task_id]["notes"])

    def test_the_other_fields_of_a_target_are_unchanged(self):
        new = VWO.apply_patch(self.workflow, self.good_patch())
        for task_id in ("task0001", "task0002"):
            before = copy.deepcopy(self.workflow["tasks"][task_id])
            after = copy.deepcopy(new["tasks"][task_id])
            for key in ("files", "notes"):
                before.pop(key)
                after.pop(key)
            self.assertEqual(after, before)
        self.assertEqual(new["tasks"]["task0001"]["status"], "failed")
        self.assertEqual(new["tasks"]["task0001"]["routeback_failed_journal_line"], 7)

    def test_merged_records_are_the_same_as_before(self):
        new = VWO.apply_patch(self.workflow, self.good_patch())
        self.assertEqual(new["tasks"]["task0003"], self.workflow["tasks"]["task0003"])
        self.assertEqual(
            json.dumps(new["tasks"]["task0003"], sort_keys=True),
            json.dumps(self.workflow["tasks"]["task0003"], sort_keys=True),
        )

    def test_the_task_order_and_the_other_sections_are_kept(self):
        new = VWO.apply_patch(self.workflow, self.good_patch())
        self.assertEqual(list(new["tasks"]), list(self.workflow["tasks"]))
        self.assertEqual(new["workflow"], self.workflow["workflow"])
        self.assertEqual(new["requirements"], self.workflow["requirements"])

    def test_the_input_workflow_is_not_changed(self):
        before = copy.deepcopy(self.workflow)
        VWO.apply_patch(self.workflow, self.good_patch())
        self.assertEqual(self.workflow, before)

    def test_a_path_the_task_does_not_hold_leaves_files_unchanged(self):
        # The condition check rejects it (-path); the application is still
        # total: files stay, nothing raises.
        patch = make_patch([removal("task0001", "feature-docs/other/ABSENT.md")])
        new = VWO.apply_patch(self.workflow, patch)
        self.assertEqual(new["tasks"]["task0001"]["files"], self.workflow["tasks"]["task0001"]["files"])

    def test_a_target_that_is_not_in_the_workflow_is_skipped(self):
        patch = make_patch([removal("task0001", THREAT_MODEL)], carried=("task0001", "task0003"))
        new = VWO.apply_patch(self.workflow, patch)
        self.assertNotIn("task0002", new["tasks"])


# ---------------------------------------------------------------------------
# AC-6: the plan agreement
# ---------------------------------------------------------------------------

class TestPlanAgreement(Fixture):
    def agreement_errors(self, patch=None, workflow=None):
        return VWO._validate_task_plans_against_patch(
            patch or self.good_patch(), self.feature_dir, workflow=workflow or self.workflow)

    def test_plans_that_agree_with_the_corrected_files_pass(self):
        self.assertEqual(self.agreement_errors(), [])

    def test_a_plan_that_still_lists_the_path_is_task_plan_files_mismatch(self):
        self.write_plan("task0001", [THREAT_MODEL, "src/a.py"])
        errors = self.agreement_errors()
        self.assertEqual(codes(errors), ["task-plan-files-mismatch"])
        self.assertIn("task0001", errors[0]["message"])

    def test_the_mismatch_is_reported_for_each_target_plan(self):
        self.write_plan("task0001", [THREAT_MODEL, "src/a.py"])
        self.write_plan("task0002", [NOTES, "src/b.py"])
        errors = self.agreement_errors()
        self.assertEqual(codes(errors), ["task-plan-files-mismatch"] * 2)

    def test_a_plan_that_lost_other_files_is_a_mismatch_too(self):
        self.write_plan("task0001", [])
        self.assertEqual(codes(self.agreement_errors()), ["task-plan-files-mismatch"])

    def test_the_plan_of_a_task_that_is_not_a_target_is_not_read(self):
        (self.feature_dir / "tasks" / "task0003.md").unlink()
        self.assertEqual(self.agreement_errors(), [])

    def test_the_agreement_needs_the_workflow_and_the_field(self):
        self.write_plan("task0001", [THREAT_MODEL, "src/a.py"])
        self.assertEqual(VWO._validate_task_plans_against_patch(self.good_patch(), self.feature_dir), [])
        self.assertEqual(self.agreement_errors(make_patch(None)), [])

    def test_the_worker_result_path_reports_the_mismatch(self):
        def result_errors():
            result = {
                "schema_version": 1, "worker": "implementation-planner", "request_id": "req-1",
                "status": "completed", "input_revision": {"input_digest": "sha256:x"}, "mode_echo": None,
                "payload": {"task_index": {}}, "workflow_patch": self.good_patch(),
                "written_artifacts": [], "question_packet": None, "blocking_reason": None,
            }
            return VWO.validate_worker_result(
                result, "implementation-planner", workflow=self.workflow, digest_source=DIGEST_SOURCE,
                dry_run=True, feature_dir=self.feature_dir, journal=self.journal,
            )

        self.assertEqual(result_errors(), [])
        self.write_plan("task0001", [THREAT_MODEL, "src/a.py"])
        self.assertIn("task-plan-files-mismatch", codes(result_errors()))


# ---------------------------------------------------------------------------
# A name a failed task still holds is the final-path judgment's (SPEC A4)
# ---------------------------------------------------------------------------

class TestReportNameStaysOutOfTheCorrection(Fixture):
    MATCHING = "test-docs/demo/REPORT.md"

    def report_workflow(self, **kwargs):
        return make_workflow(files={
            "task0001": [THREAT_MODEL, self.MATCHING, "src/a.py"],
            "task0002": [NOTES, "src/b.py"],
            "task0003": [THIRD, "src/c.py"],
        }, **kwargs)

    def test_a_report_name_a_failed_task_still_holds_does_not_stop_the_correction(self):
        # The patch only removes paths, so it introduces no report artifact
        # name; the final-path judgment corrects the name on the next
        # evaluation. No --target-repo and --base-commit are needed for it.
        self.write_plan("task0001", [self.MATCHING, "src/a.py"])
        self.assertEqual(self.validate(self.good_patch(), self.report_workflow()), [])

    def test_the_carried_report_name_check_still_runs_when_the_field_is_not_permitted(self):
        workflow = self.report_workflow(
            create_plan="pending", implement="pending",
            statuses={"task0001": "pending", "task0002": "pending", "task0003": "pending"})
        with self.assertRaises(VWO.ExecutionError):
            self.validate(self.good_patch(), workflow)


# ---------------------------------------------------------------------------
# AC-6: the inputs --dry-run-apply needs (exit 2)
# ---------------------------------------------------------------------------

class TestRequiredInputs(Fixture):
    def test_a_missing_input_is_an_execution_error(self):
        base = dict(workflow=self.workflow, digest_source=DIGEST_SOURCE, dry_run=True,
                    feature_dir=self.feature_dir, journal=self.journal)
        self.assertEqual(VWO.validate_workflow_patch(self.good_patch(), **base), [])
        for name in ("workflow", "feature_dir", "journal"):
            with self.subTest(name):
                with self.assertRaises(VWO.ExecutionError):
                    VWO.validate_workflow_patch(self.good_patch(), **dict(base, **{name: None}))

    def test_a_patch_without_the_field_does_not_need_the_inputs(self):
        base = dict(workflow=self.workflow, digest_source=DIGEST_SOURCE, dry_run=True,
                    feature_dir=None, journal=None)
        VWO.validate_workflow_patch(make_patch(None), **base)

    def test_a_missing_journal_file_reads_as_no_events(self):
        self.journal.unlink()
        self.assertEqual(self.validate(self.good_patch()), [])

    def test_the_command_line_exits_2_for_a_missing_input_and_0_for_a_complete_call(self):
        patch_path = self.tmp / "patch.json"
        workflow_path = self.tmp / "workflow.json"
        digest_path = self.tmp / "digest-source.json"
        patch_path.write_text(json.dumps(self.good_patch()), encoding="utf-8")
        workflow_path.write_text(json.dumps(self.workflow), encoding="utf-8")
        digest_path.write_text(json.dumps(DIGEST_SOURCE), encoding="utf-8")
        flags = {
            "--workflow": str(workflow_path),
            "--feature-dir": str(self.feature_dir),
            "--journal": str(self.journal),
        }
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

        def run(omit=None):
            args = [sys.executable, str(SCRIPT_PATH), "--kind", "workflow-patch",
                    "--worker", "implementation-planner", "--input", str(patch_path),
                    "--digest-source", str(digest_path), "--dry-run-apply"]
            for flag, value in flags.items():
                if flag != omit:
                    args += [flag, value]
            return subprocess.run(args, capture_output=True, text=True, env=env)

        complete = run()
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        for flag in flags:
            with self.subTest(flag):
                result = run(omit=flag)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
