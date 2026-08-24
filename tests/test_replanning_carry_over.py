"""Tests for task0023 (goal-vs-spec-divergence, review round 3, D10):
carried task ids, so a re-planning pass cannot rewrite what is already
merged.

Covers task0023 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0023.md):

- AC-1 (FR4) / AC-2 (FR5): `TestWorkflowPatchDocDeclaresCarryOver` pins
  `references/workflow-patch.md`'s `tasks_patch.carried_task_ids`
  definition -- every registered id, `entries` names only unregistered
  ids, the two sets disjoint, the verbatim field list, and application
  rule 12 narrowed to `entries`. (The specific pin edits inside
  `workflow-patch.md`'s own document-pin module,
  `tests/test_workflow_patch_doc.py`, are task0023's too -- this module
  adds the CROSS-file proof that the document's declared field list and
  the validator's actual copied fields agree, rather than duplicating
  every doc-text assertion here.)
- AC-4 (FR5): `TestApplyPatchCopiesCarriedRecordVerbatim` -- the in-memory
  apply (`validate-worker-output.py`'s `apply_patch`) copies a carried
  task's WHOLE record from the pre-apply workflow, field by field
  (Test Notes: "assert the whole record, not just `status`"), including
  `files` with a path that exists only because an implement wake admitted
  it (Test Notes' explicit ask, proving create-plan-phase.md §12's
  retention claim by execution).
- AC-3 (FR4), unregistered-id half: `TestCarriedTaskIdsNamingAnUnregisteredIdRejected`
  -- the `carried_task_ids`-names-an-unregistered-id rejection
  (`replace-all-carried-id-unregistered`), reported alone, exercised
  directly against `validate_workflow_patch` rather than via a second new
  fixture directory (the missing-a-registered-id half is
  `replace-all-drops-task`, already re-grounded and pinned by
  `tests/test_validate_worker_output.py`'s
  `TestReplanningMandatoryPreserveAndTaskIdAllocation`; the entries-side
  rejection is that module's `TestReplanningCarryOverEnforcement`).
- AC-6 (FR4, NFR8): `TestFixtureCarryOverShape` -- the `replace_planning`
  fixture group's carry-over-relevant fixtures actually carry the shape
  the rule requires (structural sanity on top of
  `tests/test_validate_worker_output.py`'s exit-code-level pins).

Scoped to files this task owns (C4): `references/workflow-patch.md`,
`scripts/validate-worker-output.py` and the `replace_planning` fixture
group are all in task0023's own file set, so the cross-file proofs below
are within-task, not the cross-TASK consistency C4 reserves for the
verify phase. No assertion here reads `references/phase-state.md`,
`skills/develop/SKILL.md` or `references/question-resolution.md` (C4;
those belong to task0022/task0024/task0025 this round).
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
DOC_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"
FIXTURES_ROOT = (
    REPO_ROOT / "em-workflow" / "references" / "fixtures" / "workflow-patch" / "replace_planning"
)

# The verbatim field list task0023 fixes (Shared Components, "Re-planning
# carry-over declaration", IMPLEMENTATION.md): the SAME ten fields must be
# named in workflow-patch.md's prose AND actually copied by apply_patch.
CARRIED_RECORD_FIELDS = {
    "title", "plan", "files", "skills", "domains", "complexity",
    "requirements", "status", "branch", "notes",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


def _read_doc():
    return DOC_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a multi-word assertion never depends on where a line happens
    to wrap."""
    return re.sub(r"\s+", " ", text)


def _base_workflow(task0009_files=None, extra_tasks=None):
    """A minimal workflow.yaml-shaped dict with one MERGED task0009,
    mirroring the shape the replace_planning fixture group uses."""
    tasks = {
        "task0009": {
            "branch": "em-workflow/example/task0009",
            "complexity": "low",
            "domains": [],
            "files": list(task0009_files) if task0009_files is not None else ["x.go"],
            "notes": None,
            "plan": "tasks/task0009.md",
            "requirements": ["FR1"],
            "skills": [],
            "status": "merged",
            "title": "existing",
        }
    }
    if extra_tasks:
        tasks.update(extra_tasks)
    return {
        "feature": "example",
        "project": {"license": "MIT"},
        "requirements": {"FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}},
        "schema_version": 1,
        "tasks": tasks,
        "workflow": [
            {"completed_at_commit": "aaa", "id": "create-spec", "status": "completed"},
            {"id": "design", "skipped_reason": "no UI", "status": "skipped"},
            {"id": "create-plan", "status": "pending"},
            {"base_commit": "deadbeef", "id": "implement", "status": "pending"},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
    }


def _base_patch(carried_task_ids, entries):
    return {
        "base_input_digest": "sha256:" + "b" * 64,
        "base_workflow_blob": "8f17c04",
        "operation": "replace_planning",
        "patch_id": "create-plan-p0001",
        "preserve": ["workflow.implement.base_commit"],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": [],
        "tasks_patch": {
            "mode": "replace_all",
            "carried_task_ids": carried_task_ids,
            "entries": entries,
        },
    }


def _digest_source():
    return {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "implementation-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }


def _phase_state():
    # A rework-shaped phase-state carrying the unconsumed spec_change
    # record the re-planning path's second re-entry case reads
    # (workflow-patch.md's `replace_all` permission conditions) -- needed
    # so `is_replanning` is True and the carry-over checks below actually
    # run (they are scoped to the Re-planning path, never the
    # Initial-planning one).
    return {
        "phase": "rework",
        "feature": "example",
        "spec_change": {
            "consumed": False,
            "finding_stable_id": "abc123",
            "reason": "SPEC changed after implementation to add a missed requirement",
            "recorded_at_commit": "deadbeef",
        },
    }


class TestCarriedTaskIdsNamingAnUnregisteredIdRejected(unittest.TestCase):
    """AC-3's second rejection, unregistered-id half: `carried_task_ids`
    naming an id NOT registered in `workflow.yaml`. Exercised directly
    against `validate_workflow_patch` (no dedicated fixture directory --
    the task plan's Files to Create names only one new fixture,
    `invalid-replace-all-replanning-entry-for-registered-id`, for the
    entries-side rejection; this branch is proven as a direct unit test
    instead of a second fixture directory, staying within this task's file
    scope)."""

    def test_unregistered_carried_id_rejected_alone(self):
        workflow = _base_workflow()
        digest_source = _digest_source()
        patch = _base_patch(carried_task_ids=["task0009", "task9999"], entries={})
        patch["base_input_digest"] = VWO.normalize_json_sha256(digest_source)
        errors = VWO.validate_workflow_patch(
            patch,
            workflow=workflow,
            digest_source=digest_source,
            phase_state=_phase_state(),
            dry_run=True,
        )
        codes = {e["code"] for e in errors}
        self.assertEqual(codes, {"replace-all-carried-id-unregistered"})
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("task9999", messages)

    def test_fully_correct_carried_task_ids_reports_no_carry_over_error(self):
        # Non-vacuity companion: the same helper machinery, with a CORRECT
        # carried_task_ids, reports none of the three carry-over rejection
        # identifiers -- proving the previous test fails for the reason
        # claimed, not because the harness always rejects.
        workflow = _base_workflow()
        digest_source = _digest_source()
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        patch["base_input_digest"] = VWO.normalize_json_sha256(digest_source)
        errors = VWO.validate_workflow_patch(
            patch,
            workflow=workflow,
            digest_source=digest_source,
            phase_state=_phase_state(),
            dry_run=True,
        )
        codes = {e["code"] for e in errors}
        self.assertFalse(
            codes
            & {
                "replace-all-entry-for-registered-id",
                "replace-all-drops-task",
                "replace-all-carried-id-unregistered",
            }
        )


class TestApplyPatchCopiesCarriedRecordVerbatim(unittest.TestCase):
    """AC-4: apply_patch's replace_planning arm copies a carried task's
    WHOLE record from the pre-apply workflow, not just `status`."""

    def test_carried_record_equals_pre_apply_record_field_by_field(self):
        workflow = _base_workflow()
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        self.assertEqual(
            new_workflow["tasks"]["task0009"], workflow["tasks"]["task0009"]
        )

    def test_files_survive_including_a_path_only_an_implement_deviation_admitted(self):
        # Test Notes: give `files` its own case with a path that only
        # exists because an implement wake admitted it, so
        # create-plan-phase.md #12's retention claim is proved by
        # execution, not by reading the sentence.
        admitted_files = ["x.go", "x-deviation-admitted.go"]
        workflow = _base_workflow(task0009_files=admitted_files)
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        self.assertEqual(new_workflow["tasks"]["task0009"]["files"], admitted_files)

    def test_status_and_branch_of_a_merged_carried_task_are_unchanged(self):
        # The specific finding this task fixes: a merged task must still be
        # merged, on the same branch, after the patch -- not forced back to
        # pending / null the way the pre-task0023 entries re-declaration did.
        workflow = _base_workflow()
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        carried = new_workflow["tasks"]["task0009"]
        self.assertEqual(carried["status"], "merged")
        self.assertEqual(carried["branch"], "em-workflow/example/task0009")

    def test_carried_record_is_a_deep_copy_not_a_shared_reference(self):
        # Non-vacuity / aliasing guard: mutating the applied workflow must
        # never mutate the workflow the patch was generated against.
        workflow = _base_workflow()
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        new_workflow["tasks"]["task0009"]["files"].append("mutated-after-apply.go")
        self.assertEqual(workflow["tasks"]["task0009"]["files"], ["x.go"])

    def test_entries_task_still_gets_pending_status_and_null_defaults(self):
        # Retention half (C5): a genuinely NEW id under entries is
        # unaffected by this task's change -- application rule 12 and the
        # existing initial_status/notes/branch defaulting still apply.
        workflow = _base_workflow()
        patch = _base_patch(
            carried_task_ids=["task0009"],
            entries={
                "task0010": {
                    "complexity": "medium",
                    "domains": ["api-contract"],
                    "files": ["src/api/register.go"],
                    "initial_status": "pending",
                    "plan": "tasks/task0010.md",
                    "requirements": ["FR1"],
                    "skills": ["backend-impl"],
                    "title": "User registration API",
                }
            },
        )
        new_workflow = VWO.apply_patch(workflow, patch)
        fresh = new_workflow["tasks"]["task0010"]
        self.assertEqual(fresh["status"], "pending")
        self.assertIsNone(fresh["notes"])
        self.assertIsNone(fresh["branch"])

    def test_an_id_named_in_neither_carried_task_ids_nor_entries_is_absent_after_apply(self):
        # Documents the mechanism (not a validity claim -- the validator
        # rejects this patch upstream via replace-all-drops-task): apply_patch
        # itself replaces `tasks` wholesale from carried_task_ids + entries,
        # it does not fall back to the pre-apply task set for an id neither
        # names.
        workflow = _base_workflow()
        patch = _base_patch(carried_task_ids=[], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        self.assertEqual(new_workflow["tasks"], {})

    def test_entries_wins_over_carried_task_ids_when_a_malformed_patch_names_both(self):
        # apply_patch is documented as "a minimal, in-memory simulation...
        # NOT the orchestrator's real apply step" -- it does not itself
        # enforce the carried_task_ids/entries disjointness a real patch
        # must satisfy (that is _validate_dry_run_apply's
        # replace-all-entry-for-registered-id check, upstream of this
        # function). This pins the actual (permissive) simulation behaviour
        # so a future refactor cannot silently change it without a test
        # noticing, without asserting it is a VALID patch shape.
        workflow = _base_workflow()
        patch = _base_patch(
            carried_task_ids=["task0009"],
            entries={
                "task0009": {
                    "complexity": "low",
                    "domains": [],
                    "files": ["x.go"],
                    "initial_status": "pending",
                    "plan": "tasks/task0009.md",
                    "requirements": ["FR1"],
                    "skills": [],
                    "title": "existing",
                }
            },
        )
        new_workflow = VWO.apply_patch(workflow, patch)
        # entries processed after carried_task_ids => entries wins, and the
        # merged status is lost -- exactly why the validator must reject
        # this shape before apply_patch ever runs for real.
        self.assertEqual(new_workflow["tasks"]["task0009"]["status"], "pending")


class TestWorkflowPatchDocDeclaresCarryOver(unittest.TestCase):
    """AC-1 / AC-2: cross-file proof that workflow-patch.md's verbatim
    field list and apply_patch's actually-copied fields are the SAME set --
    the document and the code cannot silently drift apart on which fields
    "carried verbatim" covers."""

    def test_doc_names_exactly_the_fields_apply_patch_copies(self):
        text = _normalize_ws(_read_doc())
        match = re.search(
            r"copied from that `workflow\.yaml` \*\*verbatim\*\* — ((?:`[a-z_]+`(?:, )?)+)",
            text,
        )
        self.assertIsNotNone(match, "expected the verbatim field-list sentence")
        doc_fields = set(re.findall(r"`([a-z_]+)`", match.group(1)))
        self.assertEqual(doc_fields, CARRIED_RECORD_FIELDS)

    def test_apply_patch_copies_exactly_the_declared_fields_for_a_full_record(self):
        workflow = _base_workflow()
        patch = _base_patch(carried_task_ids=["task0009"], entries={})
        new_workflow = VWO.apply_patch(workflow, patch)
        self.assertEqual(set(new_workflow["tasks"]["task0009"].keys()), CARRIED_RECORD_FIELDS)

    def test_field_list_matcher_fails_on_a_synthetic_partial_list(self):
        # Negative proof: a partial field list (missing `files`, the
        # finding's real subject) must not satisfy the matcher.
        synthetic = (
            "copied from that `workflow.yaml` **verbatim** — `title`, "
            "`plan`, `status`, `branch`"
        )
        match = re.search(
            r"copied from that `workflow\.yaml` \*\*verbatim\*\* — ((?:`[a-z_]+`(?:, )?)+)",
            synthetic,
        )
        self.assertIsNotNone(match)
        doc_fields = set(re.findall(r"`([a-z_]+)`", match.group(1)))
        self.assertNotEqual(doc_fields, CARRIED_RECORD_FIELDS)
        self.assertNotIn("files", doc_fields)

    def test_disjointness_stated(self):
        text = _normalize_ws(_read_doc())
        self.assertIn(
            "a carried id must not also be a key of `tasks_patch.entries`",
            text,
        )

    def test_rule_twelve_narrowed_to_entries(self):
        raw = _read_doc()
        self.assertTrue(raw, "expected a non-empty document")
        section = re.search(r"12\. .*?(?=\n13\. )", raw, re.DOTALL)
        self.assertIsNotNone(section, "expected application rule 12's text")
        self.assertIn("applies to `entries` only", _normalize_ws(section.group(0)))


class TestFixtureCarryOverShape(unittest.TestCase):
    """AC-6: the replace_planning fixture group's carry-over-relevant
    fixtures actually carry the shape D10 requires -- structural sanity on
    top of test_validate_worker_output.py's exit-code-level pins (which
    this module deliberately does not duplicate, C4/DRY within the task)."""

    @staticmethod
    def _load(case_name, stem):
        path = FIXTURES_ROOT / case_name / f"{stem}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_valid_merged_tasks_fixture_carries_every_registered_id(self):
        case = "valid-replace-all-replanning-merged-tasks"
        workflow = self._load(case, "workflow")
        input_data = self._load(case, "input")
        tasks_patch = input_data["tasks_patch"]
        registered_ids = set(workflow["tasks"])
        self.assertEqual(set(tasks_patch["carried_task_ids"]), registered_ids)
        # AC-6: entries re-declares none of the carried (merged) tasks.
        self.assertFalse(set(tasks_patch["entries"]) & registered_ids)

    def test_valid_merged_tasks_fixture_task0009_files_include_a_deviation_admitted_path(self):
        # Ties this fixture directly to the Test Notes' files-survival ask
        # -- the same fixture file the CLI-level tests already exercise.
        case = "valid-replace-all-replanning-merged-tasks"
        workflow = self._load(case, "workflow")
        self.assertEqual(len(workflow["tasks"]["task0009"]["files"]), 2)

    def test_drops_existing_task_fixture_carried_task_ids_omits_a_registered_id(self):
        case = "invalid-replace-all-replanning-drops-existing-task"
        workflow = self._load(case, "workflow")
        input_data = self._load(case, "input")
        carried = set(input_data["tasks_patch"]["carried_task_ids"])
        registered_ids = set(workflow["tasks"])
        self.assertTrue(
            registered_ids - carried,
            "this fixture must omit at least one registered id from "
            "carried_task_ids -- otherwise it does not exercise the drop",
        )

    def test_entry_for_registered_id_fixture_entries_names_a_registered_id(self):
        case = "invalid-replace-all-replanning-entry-for-registered-id"
        workflow = self._load(case, "workflow")
        input_data = self._load(case, "input")
        entries = set(input_data["tasks_patch"]["entries"])
        registered_ids = set(workflow["tasks"])
        self.assertTrue(
            entries & registered_ids,
            "this fixture must name a registered id under entries -- "
            "otherwise it does not exercise the AC-3 rejection",
        )
        # Sanity: carried_task_ids is otherwise CORRECT (covers every
        # registered id), so the drop check does not also fire -- the
        # fixture isolates the entries-side rejection (Test Notes: exactly
        # one error identifier per case).
        carried = set(input_data["tasks_patch"]["carried_task_ids"])
        self.assertEqual(carried, registered_ids)


if __name__ == "__main__":
    unittest.main()
