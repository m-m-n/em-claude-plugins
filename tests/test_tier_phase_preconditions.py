"""Tests for task0006: tier transcription, the task document, and
tier-aware create-plan preconditions.

Covers feature-docs/task-tier-reduction/tasks/task0006.md Acceptance
Criteria:

- AC-1: TestTierTranscriptionStated -- em-workflow/references/phases/
  create-spec-phase.md states that the orchestrator reads the persisted
  tier record and writes `tier` / `tier_decision` in the same write that
  builds workflow.yaml, and that a later re-transcription may raise but
  never lower the tier (TS-8).
- AC-2: TestArtifactsPerTierStated -- create-spec-phase.md states which
  artifacts are not produced at the `reduced` and `minimal` tiers by citing
  the develop skill's reduction table, and restates no subtraction list of
  its own.
- AC-3: TestTaskDocumentTemplate -- em-workflow/references/templates/
  task-document.md has exactly two sections (the change, the expected
  result), in both directions (missing / extra).
- AC-4: TestCreatePlanPreconditionsTierAware -- em-workflow/references/
  phases/create-plan-phase.md admits an absent REQUIREMENTS.md at the
  `reduced` tier, and an absent SPEC.md plus an empty requirement map at
  the `minimal` tier, naming the task document as the planner's input in
  that case (TS-6).
- AC-5: TestSingleTaskShapeStated -- create-plan-phase.md states that the
  `minimal` tier still registers exactly one task entry pointing at the
  task document, with every mandatory field including `complexity`, and a
  `requirements` list that may be empty.
- AC-6: TestValidatorAcceptsMinimalShapePatch -- a workflow patch built
  from that shape (an empty `requirements` map in workflow.yaml and an
  empty `requirements` list on the single task) passes
  em-workflow/scripts/validate-worker-output.py unmodified (TS-6); a
  negative proof forges the same patch with `complexity` missing and
  confirms the validator rejects it.
- AC-7: this module itself -- discovered by
  `python3 -m unittest discover -s tests`, imports only standard-library
  modules, and pairs every matcher with a negative proof and a
  non-vacuity guard.

Test Notes followed:
- The two-section assertion for the template is exact in both directions:
  a missing section and an extra one both fail (single assertEqual on the
  full ordered heading list, not two independent assertIn/assertNotIn).
- AC-2's "restates no subtraction list" is an absence check (VERIFICATION.md
  / "parallel worktree" -- reduction-table-only vocabulary that
  create-spec-phase.md has no reason to ever mention); its negative proof
  forges a copy that reintroduces that vocabulary.
- The empty-map (`requirements: {}`) and empty-list (`requirements: []`)
  YAML shapes are both exercised in the same AC-6 patch, per the Design
  section's "single-task shape".
- The transcription assertion pins the single-writer wording so a future
  edit cannot quietly let a worker write these fields.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CREATE_SPEC_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "phases" / "create-spec-phase.md"
CREATE_PLAN_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "phases" / "create-plan-phase.md"
TASK_DOCUMENT_TEMPLATE_PATH = REPO_ROOT / "em-workflow" / "references" / "templates" / "task-document.md"
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    return re.sub(r"\s+", " ", text)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# AC-1: tier transcription (TS-8)
# ---------------------------------------------------------------------------

def _assert_transcription_stated(test, text):
    norm = _normalize(text)
    test.assertIn(
        "the orchestrator reads that persisted tier record and writes "
        "`tier` and `tier_decision` into `workflow.yaml` in the same "
        "write that builds it",
        norm,
    )
    test.assertIn(
        "no worker proposes these fields, only the orchestrator writes them",
        norm,
    )
    test.assertIn(
        "MAY raise the tier already recorded but MUST NEVER lower it",
        norm,
    )
    test.assertIn("TS-8", norm)


class TestTierTranscriptionStated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PHASE_PATH)

    def test_transcription_is_stated(self):
        _assert_transcription_stated(self, self.text)

    def test_persisted_record_is_cited_not_restated(self):
        # The persisted tier.yaml record's own field shapes belong to
        # references/phase-state.md (task0003's territory); this document
        # cites it by path rather than restating its schema.
        norm = _normalize(self.text)
        self.assertIn("references/phase-state.md", norm)
        self.assertIn("references/workflow-schema.md", norm)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_NO_TRANSCRIPTION = (
        "# Create-spec Phase Protocol (em-workflow)\n\n"
        "This document has no tier content of any kind.\n"
    )

    def test_forged_text_without_transcription_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_transcription_stated(self, self.FORGED_NO_TRANSCRIPTION)

    def test_forged_text_otherwise_well_formed(self):
        # Proves the negative proof fails for the SPECIFIC missing wording,
        # not because the forged sample is garbage in general.
        self.assertIn("Create-spec Phase Protocol", self.FORGED_NO_TRANSCRIPTION)


# ---------------------------------------------------------------------------
# AC-2: which artifacts are not produced at reduced/minimal, citing the
# develop skill's reduction table, restating no subtraction list of its own.
# ---------------------------------------------------------------------------

# Vocabulary that belongs only to the develop skill's full reduction table
# (IMPLEMENTATION.md Shared Components: "Tier reduction table") -- items
# create-spec never itself produces or subtracts, so their presence here
# would mean the table was restated rather than cited.
RESTATED_SUBTRACTION_MARKERS = ("VERIFICATION.md", "parallel worktree")


def _assert_artifacts_per_tier_stated(test, text):
    norm = _normalize(text)
    test.assertIn("develop skill's reduction table", norm)
    test.assertIn("`skills/develop/SKILL.md`", norm)
    test.assertIn("cited here, never restated", norm)
    test.assertIn("REQUIREMENTS.md is not produced", norm)
    test.assertIn("spec-writer is not dispatched at all", norm)
    for marker in RESTATED_SUBTRACTION_MARKERS:
        test.assertNotIn(marker, text)


class TestArtifactsPerTierStated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PHASE_PATH)

    def test_artifacts_per_tier_is_stated(self):
        _assert_artifacts_per_tier_stated(self, self.text)

    def test_task_document_named_as_the_minimal_tier_replacement(self):
        norm = _normalize(self.text)
        self.assertIn("references/templates/task-document.md", norm)

    # -- negative proof + non-vacuity guard -----------------------------

    def test_forged_text_restating_the_subtraction_list_is_rejected(self):
        forged = self.text + (
            "\n\nFor completeness: `reduced` subtracts REQUIREMENTS.md, "
            "IMPLEMENTATION.md and the design step; `minimal` additionally "
            "subtracts SPEC.md, the task split, VERIFICATION.md and "
            "parallel worktree.\n"
        )
        with self.assertRaises(AssertionError):
            _assert_artifacts_per_tier_stated(self, forged)

    def test_forged_text_otherwise_well_formed(self):
        forged = self.text + (
            "\n\nFor completeness: `reduced` subtracts REQUIREMENTS.md, "
            "IMPLEMENTATION.md and the design step; `minimal` additionally "
            "subtracts SPEC.md, the task split, VERIFICATION.md and "
            "parallel worktree.\n"
        )
        # The forgery only ADDS text; every real assertion the matcher
        # makes about the true content still holds, isolating the failure
        # to the restated-list check specifically.
        norm = _normalize(forged)
        self.assertIn("develop skill's reduction table", norm)
        self.assertIn("REQUIREMENTS.md is not produced", norm)


# ---------------------------------------------------------------------------
# AC-3: the task document template has exactly two sections.
# ---------------------------------------------------------------------------

def _section_headings(text):
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def _assert_exactly_two_sections(test, text):
    test.assertEqual(_section_headings(text), ["Change", "Expected Result"])


class TestTaskDocumentTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(TASK_DOCUMENT_TEMPLATE_PATH)

    def test_template_file_exists(self):
        self.assertTrue(TASK_DOCUMENT_TEMPLATE_PATH.is_file())

    def test_exactly_two_sections_change_and_expected_result(self):
        _assert_exactly_two_sections(self, self.text)

    def test_no_requirement_identifiers_scenarios_or_assumptions_block(self):
        norm = _normalize(self.text)
        for forbidden in ("FR1", "NFR1", "## Scenarios", "## Assumptions"):
            self.assertNotIn(forbidden, norm)

    # -- negative proofs (both directions) + non-vacuity guards ---------

    def test_forged_missing_expected_result_section_is_rejected(self):
        forged = "# Task Document: task0001 -- Something\n\n## Change\n\nDo the thing.\n"
        with self.assertRaises(AssertionError):
            _assert_exactly_two_sections(self, forged)

    def test_forged_missing_section_otherwise_well_formed(self):
        forged = "# Task Document: task0001 -- Something\n\n## Change\n\nDo the thing.\n"
        self.assertIn("## Change", forged)

    def test_forged_extra_third_section_is_rejected(self):
        forged = (
            "# Task Document: task0001 -- Something\n\n"
            "## Change\n\nDo the thing.\n\n"
            "## Expected Result\n\nIt works.\n\n"
            "## Notes\n\nSomething extra.\n"
        )
        with self.assertRaises(AssertionError):
            _assert_exactly_two_sections(self, forged)

    def test_forged_extra_section_otherwise_well_formed(self):
        forged = (
            "# Task Document: task0001 -- Something\n\n"
            "## Change\n\nDo the thing.\n\n"
            "## Expected Result\n\nIt works.\n\n"
            "## Notes\n\nSomething extra.\n"
        )
        self.assertIn("## Change", forged)
        self.assertIn("## Expected Result", forged)


# ---------------------------------------------------------------------------
# AC-4: create-plan preconditions are tier-aware (TS-6).
# ---------------------------------------------------------------------------

def _assert_preconditions_tier_aware(test, text):
    norm = _normalize(text)
    test.assertIn(
        "at the `reduced` tier REQUIREMENTS.md may be absent",
        norm,
    )
    test.assertIn(
        "At the `minimal` tier SPEC.md may be absent too",
        norm,
    )
    test.assertIn(
        "task document (`feature-docs/{feature}/TASK.md`, "
        "`references/templates/task-document.md`) named as the "
        "planner's input in its place",
        norm,
    )
    test.assertIn(
        "an empty `requirements` map (`requirements: {}`) is a legitimate "
        "state, not a mismatch",
        norm,
    )


class TestCreatePlanPreconditionsTierAware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PHASE_PATH)

    def test_preconditions_are_tier_aware(self):
        _assert_preconditions_tier_aware(self, self.text)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_FULL_ONLY = (
        "## 2. Preconditions\n\n"
        "- REQUIREMENTS.md and SPEC.md exist; DESIGN.md is additionally "
        "required when `design` is `completed`.\n"
        "- `workflow.yaml`'s `requirements` agree with SPEC.md's FR/NFR set.\n"
    )

    def test_forged_full_tier_only_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_preconditions_tier_aware(self, self.FORGED_FULL_ONLY)

    def test_forged_text_otherwise_well_formed(self):
        self.assertIn("REQUIREMENTS.md and SPEC.md exist", self.FORGED_FULL_ONLY)


# ---------------------------------------------------------------------------
# AC-5: the most-reducing tier's single-task shape is stated.
# ---------------------------------------------------------------------------

def _assert_single_task_shape_stated(test, text):
    norm = _normalize(text)
    test.assertIn("exactly one task entry", norm)
    test.assertIn("task document", norm)
    test.assertIn("every mandatory field", norm)
    test.assertIn("including its `complexity` value", norm)
    test.assertIn("`requirements` list may be empty", norm)


class TestSingleTaskShapeStated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PHASE_PATH)

    def test_single_task_shape_is_stated(self):
        _assert_single_task_shape_stated(self, self.text)

    def test_task_completion_defined_by_merge(self):
        norm = _normalize(self.text)
        self.assertIn("merge into the integration branch", norm)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_NO_SHAPE = (
        "## 3. Reconcile on entry\n\nNo single-task shape content here.\n"
    )

    def test_forged_text_without_shape_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_single_task_shape_stated(self, self.FORGED_NO_SHAPE)

    def test_forged_text_otherwise_well_formed(self):
        self.assertIn("Reconcile on entry", self.FORGED_NO_SHAPE)


# ---------------------------------------------------------------------------
# AC-6: the minimal-tier shape passes validate-worker-output.py unmodified.
# ---------------------------------------------------------------------------

DIGEST_SOURCE = {
    "answers_digest": "sha256:" + "2" * 70,
    "digest_inputs": {
        "feature-docs/example/TASK.md": "sha256:" + "1" * 70,
    },
    "mode": "interactive",
    "value_inputs": {"task_description": None},
    "worker": "implementation-planner",
    "workflow_blob": "8f17c04",
    "write_policy_digest": "sha256:" + "3" * 70,
}


def _build_patch(vwo, *, with_complexity=True):
    entry = {
        "title": "Something",
        "plan": "TASK.md",
        "files": ["src/api/register.go"],
        "skills": ["backend-impl"],
        "domains": ["api-contract"],
        # Edge case (Test Notes): requirements: [] -- the empty-LIST shape.
        "requirements": [],
        "initial_status": "pending",
    }
    if with_complexity:
        entry["complexity"] = "medium"
    return {
        "schema_version": 1,
        "patch_id": "create-plan-p0001",
        "base_input_digest": vwo.normalize_json_sha256(DIGEST_SOURCE),
        "base_workflow_blob": DIGEST_SOURCE["workflow_blob"],
        "operation": "replace_planning",
        "tasks_patch": {
            "mode": "replace_all",
            "entries": {"task0001": entry},
        },
        "requirements_patch": None,
        "step_patches": [],
        "preserve": [],
    }


def _build_workflow():
    return {
        "schema_version": 1,
        "feature": "example",
        "project": {"license": "MIT"},
        # Edge case (Test Notes): requirements: {} -- the empty-MAP shape,
        # in the SAME document as the empty-list task requirements above.
        "requirements": {},
        "tasks": {},
        "workflow": [
            {"id": "create-spec", "status": "completed", "completed_at_commit": "aaa"},
            {"id": "design", "status": "skipped", "skipped_reason": "no UI"},
            {"id": "create-plan", "status": "pending"},
            {"id": "implement", "status": "pending", "base_commit": "deadbeef"},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
    }


class TestValidatorAcceptsMinimalShapePatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vwo = _load_module()

    def _run(self, patch):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            input_path.write_text(json.dumps(patch), encoding="utf-8")
            workflow_path.write_text(json.dumps(_build_workflow()), encoding="utf-8")
            digest_source_path.write_text(json.dumps(DIGEST_SOURCE), encoding="utf-8")
            return run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--dry-run-apply",
                ]
            )

    def test_empty_requirement_map_and_empty_requirement_list_pass(self):
        patch = _build_patch(self.vwo, with_complexity=True)
        result = self._run(patch)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_requirements_field_is_the_empty_list_shape(self):
        patch = _build_patch(self.vwo, with_complexity=True)
        self.assertEqual(patch["tasks_patch"]["entries"]["task0001"]["requirements"], [])

    def test_workflow_requirements_field_is_the_empty_map_shape(self):
        self.assertEqual(_build_workflow()["requirements"], {})

    # -- negative proof + non-vacuity guard -----------------------------

    def test_patch_missing_complexity_is_rejected(self):
        patch = _build_patch(self.vwo, with_complexity=False)
        result = self._run(patch)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("complexity", messages)

    def test_patch_missing_complexity_otherwise_well_formed(self):
        # Non-vacuity guard: the only thing wrong with this patch is the
        # missing `complexity` key -- everything else that made the
        # positive case pass is still present.
        patch = _build_patch(self.vwo, with_complexity=False)
        entry = patch["tasks_patch"]["entries"]["task0001"]
        self.assertNotIn("complexity", entry)
        self.assertEqual(entry["requirements"], [])
        self.assertEqual(patch["operation"], "replace_planning")


if __name__ == "__main__":
    unittest.main()
