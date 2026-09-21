"""Tests for task0010: the most-reducing tier's single-task plan actually
validates -- the task-document exemption `create-plan-phase.md` section 2a
declares for a task entry whose `plan` names the task document
(`feature-docs/{feature}/TASK.md`) is implemented in
`validate-worker-output.py`, worded identically on both sides, and proven
end to end against a real task document.

Covers task0010 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0010.md):

- AC-1: TestTaskDocumentExemption.test_task_document_plan_suppresses_
  files_mismatch_and_acceptance_criteria_errors -- an entry whose `plan`
  names the task document produces neither the files-mismatch nor the
  acceptance-criteria error, even when its declared files and the task
  document disagree and the task document has no Acceptance Criteria
  section at all.
- AC-2: TestTaskDocumentExemption's other cases -- for the same
  task-document-named entry, an absolute plan path, a plan path with a
  parent-directory segment, a plan path escaping the feature directory via
  a symlink whose final segment is still the task document's file name, a
  plan path naming a file that does not exist, and an oversized plan file
  each still produce exactly the pre-existing error kind.
- AC-3: TestOrdinaryTaskPlanRegression -- an entry whose `plan` names an
  ordinary task plan (not the task document) still produces the
  files-mismatch error on a files disagreement and the acceptance-criteria
  error on a missing/empty Acceptance Criteria section: the negative proof
  that the exemption does not leak to ordinary plans.
- AC-4: TestExemptionTriggerWordingMatches -- `create-plan-phase.md`
  section 2a and `validate-worker-output.py` state the exemption's trigger
  in the identical words, with a forged pre-change-wording sample as the
  negative proof that the check is not vacuously true.
- AC-5: TestEndToEndCanonicalInvocation -- the validator, invoked the way
  create-plan-phase.md's canonical invocation reaches the task-plan checks
  (`--kind worker-result --worker implementation-planner --input ...
  --input-envelope ... --feature-dir ...`), reports no error for a real
  feature directory holding a two-section task document and a single-task
  patch whose entry points at it.

AC-1/AC-2/AC-3/AC-5 load the validator module the way
`tests/test_check_plugin_invariants.py` already loads a plugin script and
drive it over temporary feature directories built by this module. Imports
standard-library modules only (AC-6).
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
PHASE_DOC_PATH = REPO_ROOT / "em-workflow" / "references" / "phases" / "create-plan-phase.md"

# task-tier-reduction/task0010 (AC-4): the exact words both sides use for
# the exemption's trigger -- asserted identically against both documents'
# raw text below. Prose in both source documents wraps at a column width,
# so the comparison normalizes whitespace (collapsing newlines/indentation)
# rather than requiring the phrase to sit on one physical line.
TRIGGER_PHRASE = "the plan value's final path segment equals the task document's file name"


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output_task0010", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

# references/templates/task-document.md: exactly two sections, no Files
# bullets and no Acceptance Criteria section at all.
TASK_DOCUMENT_TEXT = (
    "# Task Document: task0001 -- Something\n\n"
    "## Change\n\nDo the change.\n\n"
    "## Expected Result\n\nThe result.\n"
)

# An ordinary, valid per-task plan (references/templates/task-plan.md
# shape) whose Files section agrees with files=[\"src/a.go\"].
ORDINARY_PLAN_TEXT = (
    "# Task Plan: task0001 -- Something\n\n"
    "## Goal\n\nDeliver something.\n\n"
    "## Requirements\n\nFR1\n\n"
    "## Scope\n\n"
    "### Files to Create\n"
    "- `src/a.go` -- main file\n\n"
    "### Files to Modify\n\n"
    "## Design\n\nNotes.\n\n"
    "## Acceptance Criteria (MANDATORY)\n\n"
    "- [ ] AC-1: something is delivered\n\n"
    "## Test Notes\n\nNotes.\n\n"
    "## Out of Scope\n\nNone.\n"
)

# Same shape, but with no Acceptance Criteria bullets under the mandatory
# heading -- the negative proof for the acceptance-criteria check.
ORDINARY_PLAN_TEXT_NO_ACCEPTANCE_CRITERIA = (
    "# Task Plan: task0001 -- Something\n\n"
    "## Goal\n\nDeliver something.\n\n"
    "## Requirements\n\nFR1\n\n"
    "## Scope\n\n"
    "### Files to Create\n"
    "- `src/a.go` -- main file\n\n"
    "### Files to Modify\n\n"
    "## Design\n\nNotes.\n\n"
    "## Acceptance Criteria (MANDATORY)\n\n"
    "## Test Notes\n\nNotes.\n\n"
    "## Out of Scope\n\nNone.\n"
)


def _make_patch(entries):
    return {
        "schema_version": 1,
        "patch_id": "create-plan-p0001",
        "base_input_digest": "sha256:" + "a" * 64,
        "base_workflow_blob": "8f17c04",
        "operation": "replace_planning",
        "tasks_patch": {
            "mode": "replace_all",
            "entries": entries,
        },
        "requirements_patch": None,
        "step_patches": [],
        "preserve": [],
    }


def _entry(plan, files=None):
    return {
        "title": "Something",
        "plan": plan,
        "files": files or [],
        "skills": [],
        "domains": [],
        "complexity": "medium",
        "requirements": [],
        "initial_status": "pending",
    }


class TestTaskDocumentExemption(unittest.TestCase):
    """AC-1, AC-2: the exemption applies for an entry whose `plan` names
    the task document, and every other check (path safety, symlink
    rejection, containment, existence, size) still applies unchanged."""

    def _feature_dir(self, tmp_path):
        feature_dir = tmp_path / "feature-dir"
        feature_dir.mkdir()
        return feature_dir

    def test_task_document_plan_suppresses_files_mismatch_and_acceptance_criteria_errors(self):
        # AC-1: files disagree AND the task document has no Acceptance
        # Criteria section at all -- neither error is produced.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            (feature_dir / "TASK.md").write_text(TASK_DOCUMENT_TEXT, encoding="utf-8")
            patch = _make_patch({
                "task0001": _entry("TASK.md", files=["src/a.go", "src/b.go"]),
            })

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual(errors, [])

    def test_absolute_task_document_plan_path_is_still_rejected(self):
        # AC-2: absolute path -- pre-existing "task-plan-path" rejection.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            patch = _make_patch({"task0001": _entry("/etc/TASK.md", files=[])})

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual([e["code"] for e in errors], ["task-plan-path"])

    def test_parent_segment_task_document_plan_path_is_still_rejected(self):
        # AC-2: `..` segment -- pre-existing "task-plan-path" rejection.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            (tmp_path / "TASK.md").write_text(TASK_DOCUMENT_TEXT, encoding="utf-8")
            patch = _make_patch({"task0001": _entry("../TASK.md", files=[])})

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual([e["code"] for e in errors], ["task-plan-path"])

    def test_symlink_escape_task_document_plan_path_is_still_rejected(self):
        # AC-2 / Test Notes: a plan value whose final segment is the task
        # document's file name, but whose path escapes the feature
        # directory via a symlink -- the exemption must not be reached
        # before containment is decided; the path error wins, not a pass.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            outside_dir = tmp_path / "outside"
            outside_dir.mkdir()
            secret = outside_dir / "secret.md"
            secret.write_text("secret content", encoding="utf-8")
            subdir = feature_dir / "escape"
            subdir.mkdir()
            symlink_path = subdir / "TASK.md"
            os.symlink(secret, symlink_path)
            self.assertTrue(symlink_path.is_symlink())
            patch = _make_patch({"task0001": _entry("escape/TASK.md", files=[])})

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual([e["code"] for e in errors], ["task-plan-path"])
            self.assertIn("symlink", errors[0]["message"].lower())

    def test_missing_task_document_plan_file_is_still_rejected(self):
        # AC-2: does not exist -- pre-existing "task-plan-missing" rejection.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            patch = _make_patch({"task0001": _entry("TASK.md", files=[])})

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual([e["code"] for e in errors], ["task-plan-missing"])

    def test_oversized_task_document_plan_file_is_still_rejected(self):
        # AC-2: exceeds the size limit -- pre-existing "task-plan-too-large"
        # rejection.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = self._feature_dir(tmp_path)
            (feature_dir / "TASK.md").write_text(
                "x" * (VWO.MAX_PLAN_READ_BYTES + 1), encoding="utf-8"
            )
            patch = _make_patch({"task0001": _entry("TASK.md", files=[])})

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            self.assertEqual([e["code"] for e in errors], ["task-plan-too-large"])


class TestOrdinaryTaskPlanRegression(unittest.TestCase):
    """AC-3: the negative proof paired with AC-1 -- an entry whose `plan`
    does NOT name the task document is unaffected by the exemption."""

    def _feature_dir(self, tmp_path):
        feature_dir = tmp_path / "feature-dir"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        return feature_dir, tasks_dir

    def test_ordinary_plan_files_mismatch_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(ORDINARY_PLAN_TEXT, encoding="utf-8")
            patch = _make_patch({
                "task0001": _entry("tasks/task0001.md", files=["src/other.go"]),
            })

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            codes = [e["code"] for e in errors]
            self.assertIn("task-plan-files-mismatch", codes)
            self.assertNotIn("task-plan-acceptance-criteria", codes)

    def test_ordinary_plan_missing_acceptance_criteria_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(
                ORDINARY_PLAN_TEXT_NO_ACCEPTANCE_CRITERIA, encoding="utf-8"
            )
            patch = _make_patch({
                "task0001": _entry("tasks/task0001.md", files=["src/a.go"]),
            })

            errors = VWO._validate_task_plans_against_patch(patch, feature_dir)

            codes = [e["code"] for e in errors]
            self.assertNotIn("task-plan-files-mismatch", codes)
            self.assertIn("task-plan-acceptance-criteria", codes)


class TestExemptionTriggerWordingMatches(unittest.TestCase):
    """AC-4: `create-plan-phase.md` section 2a and the validator state the
    exemption's trigger in the identical words."""

    def test_phase_doc_states_trigger_phrase(self):
        text = PHASE_DOC_PATH.read_text(encoding="utf-8")
        self.assertIn(TRIGGER_PHRASE, _normalize_ws(text))

    def test_validator_states_same_trigger_phrase(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(TRIGGER_PHRASE, _normalize_ws(text))

    def test_pre_change_wording_does_not_satisfy_the_check(self):
        # Negative proof: the pre-change sentence ("do not apply when
        # `plan` names `TASK.md`") does not contain the new trigger
        # phrase, so the two assertions above are not vacuously true
        # against any mention of TASK.md.
        forged_pre_change_sample = (
            "the task-plan checks that `validate-worker-output.py` applies "
            "to a task entry's `plan` document (`### Files to Modify` "
            "reconciliation, `## Acceptance Criteria (MANDATORY)` "
            "presence) do not apply when `plan` names `TASK.md`; those "
            "checks are scoped to per-task plan documents produced at "
            "tiers where the task split is not subtracted."
        )
        self.assertNotIn(TRIGGER_PHRASE, _normalize_ws(forged_pre_change_sample))


class TestEndToEndCanonicalInvocation(unittest.TestCase):
    """AC-5: the validator invoked the way create-plan-phase.md's canonical
    invocation reaches the task-plan checks (`--kind worker-result --worker
    implementation-planner --input ... --input-envelope ... --feature-dir
    ...`; `--workflow`/`--registries`/`--phase-state`/`--digest-source`/
    `--dry-run-apply` are each independently optional and orthogonal to the
    task-plan checks under test here, per section 9's own description of
    what each omitted flag narrows), against a feature directory holding a
    real two-section task document and a single-task patch whose entry
    points at it."""

    def test_single_task_patch_pointing_at_task_document_reports_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            feature_dir.mkdir()
            (feature_dir / "TASK.md").write_text(TASK_DOCUMENT_TEXT, encoding="utf-8")

            result_obj = {
                "schema_version": 1,
                "request_id": "run-0001",
                "worker": "implementation-planner",
                "status": "completed",
                "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
                "question_packet": None,
                "blocking_reason": None,
                "written_artifacts": [
                    {"path": "feature-docs/example/TASK.md", "sha256": "sha256:" + "e" * 64},
                ],
                "workflow_patch": {
                    "schema_version": 1,
                    "patch_id": "create-plan-p0001",
                    "base_input_digest": "sha256:" + "a" * 64,
                    "base_workflow_blob": "8f17c04",
                    "operation": "replace_planning",
                    "tasks_patch": {
                        "mode": "replace_all",
                        "entries": {
                            "task0001": {
                                "title": "Something",
                                "plan": "TASK.md",
                                "files": ["src/a.go"],
                                "skills": [],
                                "domains": [],
                                "complexity": "medium",
                                "requirements": [],
                                "initial_status": "pending",
                            }
                        },
                    },
                    "requirements_patch": None,
                    "step_patches": [],
                    "preserve": [],
                },
                "mode_echo": None,
                "payload": {"task_index": {"task0001": {"title": "Something"}}},
                "warnings": [],
                "report": "done",
            }
            envelope_obj = {
                "schema_version": 1,
                "request_id": "env-run-0001",
                "phase": "create-plan",
                "mode": "interactive",
                "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
                "write_policy": {"targets": []},
                "allowed_write_roots": ["feature-docs/example/"],
                "resolved_input_paths": {},
            }
            input_path = tmp_path / "input.json"
            envelope_path = tmp_path / "envelope.json"
            input_path.write_text(json.dumps(result_obj), encoding="utf-8")
            envelope_path.write_text(json.dumps(envelope_obj), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT_PATH),
                    "--kind", "worker-result",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--input-envelope", str(envelope_path),
                    "--feature-dir", str(feature_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
