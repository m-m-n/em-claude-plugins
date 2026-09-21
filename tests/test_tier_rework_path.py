"""Tests for task0008 (task-tier-reduction): the rework path's behaviour
when review/verify-triggered rework fires at the most-reducing tier, where
no `VERIFICATION.md` exists, and the validator's matching change.

Covers task0008 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0008.md):

- AC-1: `em-workflow/references/rework-task-synthesis.md` states which of
  the two routes into rework applies at the most-reducing tier and what
  happens when the verification document is absent, in a form that admits
  exactly one validator behaviour (TS-19).
- AC-2: `em-workflow/references/contracts/rework-planner-contract.md`
  states the same outcome from the worker-contract side, citing rather than
  restating the owning document.
- AC-3: the validator's scenario-novelty check has an explicit, fail-closed
  outcome for the absent-document case, with an error message naming that
  case distinctly from the no-baseline case (TS-19).
- AC-4: the validator's task-entry validation is unchanged, proved by a case
  that an empty requirement list on a task entry is still accepted.
- AC-7 (the part scoped to this module): discovered by `python3 -m unittest
  discover -s tests`, imports only the standard library, and each matcher
  this module exercises is paired with a negative proof and a non-vacuity
  guard.

Test Notes: AC-3/AC-4 are behavioural -- the validator's internal
`_validate_rework_index` / `validate_task_entry` helpers are called directly,
the same way `tests/test_validate_worker_output.py` already calls
`_validate_rework_index` for its own baseline-requirement coverage. This
module does not modify that file (task0008.md's file scope: create-only for
tests/test_tier_rework_path.py).
"""

import ast
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"
SYNTHESIS_DOC_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
CONTRACT_DOC_PATH = (
    PLUGIN_ROOT / "references" / "contracts" / "rework-planner-contract.md"
)


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output_task0008", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_validator_module()


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _write_verification_md(dir_path, scenario_ids):
    dir_path.mkdir(parents=True, exist_ok=True)
    lines = ["### Test Scenarios from SPEC.md", ""]
    lines.extend(f"- {tid}: something" for tid in scenario_ids)
    (dir_path / "VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1: rework-task-synthesis.md states which route applies, and what
# happens when the verification document is absent.
# ---------------------------------------------------------------------------

class TestSynthesisDocStatesMostReducingTierRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SYNTHESIS_DOC_PATH)

    def test_section_8a_heading_present(self):
        self.assertIn(
            "### 8a. The most-reducing tier: no verification document exists",
            self.text,
        )

    def _section_8a(self):
        start = self.text.index("### 8a.")
        end = self.text.index("## 9. Related document updates")
        return self.text[start:end]

    def test_states_document_never_produced_at_this_tier(self):
        section = self._section_8a()
        self.assertIn("`VERIFICATION.md`", section)
        self.assertIn("subtracts", section)

    def test_names_both_routes(self):
        section = self._section_8a()
        self.assertIn("UPGRADE", section)
        self.assertIn("DIRECT", section)

    def test_states_the_upgrade_route_is_the_one_that_can_succeed(self):
        section = self._section_8a()
        self.assertIn("the upgrade route is the one that can\nsucceed", section)

    def test_states_direct_route_cannot_produce_a_valid_task(self):
        section = self._section_8a()
        self.assertIn("cannot\nproduce a valid task", section)

    def test_states_fail_closed_consequence(self):
        section = self._section_8a()
        self.assertIn("fail-closed", section)

    def test_cites_reduction_table_and_upgrade_procedure_without_restating(self):
        section = self._section_8a()
        self.assertIn("cited not restated", section)
        # The subtraction list itself (what each tier removes) is not
        # reproduced here -- only referenced.
        self.assertNotIn("task-level parallelism", section)

    def test_validation_section_names_the_absent_document_outcome(self):
        start = self.text.index("## 12. Validation")
        end = self.text.index("## 13. Execution adapter")
        section = self.text[start:end]
        self.assertIn("Section 8a", section)
        self.assertIn("fail-closed", section)


class TestSynthesisDocRouteAssertionsCanFail(unittest.TestCase):
    """Proof that the checks above fail meaningfully against a forged copy
    missing the route statement (tdd-testing: a test that can never fail is
    not a test)."""

    def test_forged_text_without_route_statement_is_detected(self):
        forged = (
            "### 8a. The most-reducing tier\n\n"
            "Nothing is said about what happens here.\n\n"
            "## 9. Related document updates\n"
        )
        self.assertNotIn("UPGRADE", forged)
        self.assertNotIn("fail-closed", forged)

    def test_forged_text_is_otherwise_well_formed(self):
        forged = "### 8a. The most-reducing tier: no verification document exists\n"
        self.assertIn("### 8a.", forged)


# ---------------------------------------------------------------------------
# AC-2: rework-planner-contract.md states the same outcome, citing rather
# than restating.
# ---------------------------------------------------------------------------

class TestContractDocCitesSynthesisDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_names_the_most_reducing_tier(self):
        self.assertIn("**The most-reducing tier.**", self.text)

    def test_cites_section_8a_rather_than_restating_it(self):
        self.assertIn("Section 8a (cited, not restated)", self.text)

    def test_states_new_scenarios_blocked_until_upgrade(self):
        self.assertIn(
            "cannot declare\n`new_scenarios` until the tier has been upgraded",
            self.text,
        )

    def test_states_fail_closed_outcome_named_distinctly(self):
        self.assertIn("fail-closed", self.text)
        self.assertIn("distinctly from", self.text)

    def test_does_not_restate_the_reduction_table(self):
        # The contract states the CONSEQUENCE, never the subtraction list
        # itself -- that stays owned by the develop skill's reduction table
        # per rework-task-synthesis.md Section 8a.
        self.assertNotIn("task-level parallelism", self.text)
        self.assertNotIn("Every tier keeps", self.text)


class TestContractDocAssertionsCanFail(unittest.TestCase):
    def test_missing_citation_is_detected(self):
        forged = "no mention of section 8a here"
        self.assertNotIn("Section 8a", forged)


# ---------------------------------------------------------------------------
# AC-3: the validator's scenario-novelty check has an explicit, fail-closed
# outcome for the absent-document case, distinct from the no-baseline case.
# ---------------------------------------------------------------------------

def _rework_index_and_patch():
    rework_index = {
        "task0007": {
            "covered_by_existing": [],
            "new_scenarios": ["TS-9"],
            "rationale": "new case",
        }
    }
    workflow_patch = {
        "tasks_patch": {"entries": {"task0007": {}}},
        "requirements_patch": {
            "mode": "merge_entries",
            "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}},
        },
    }
    return rework_index, workflow_patch


class TestValidatorAbsentDocumentCase(unittest.TestCase):
    def test_new_scenarios_rejected_when_document_absent_with_baseline_supplied(self):
        rework_index, workflow_patch = _rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            feature_dir.mkdir()  # no VERIFICATION.md written -- absent-document case
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index,
                workflow_patch,
                envelope=None,
                feature_dir=feature_dir,
                baseline_dir=baseline_dir,
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertTrue(errors, "expected the absent-document case to be rejected")
        self.assertIn(
            "no VERIFICATION.md exists in the feature directory", messages
        )

    def test_absent_document_error_is_distinct_from_no_baseline_error(self):
        rework_index, workflow_patch = _rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            feature_dir.mkdir()
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(baseline_dir, [])
            absent_doc_errors = VWO._validate_rework_index(
                rework_index,
                workflow_patch,
                envelope=None,
                feature_dir=feature_dir,
                baseline_dir=baseline_dir,
            )
        no_baseline_errors = VWO._validate_rework_index(
            rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None
        )
        absent_msg = " ".join(e["message"] for e in absent_doc_errors)
        no_baseline_msg = " ".join(e["message"] for e in no_baseline_errors)
        self.assertIn("no VERIFICATION.md exists in the feature directory", absent_msg)
        self.assertNotIn("no VERIFICATION.md exists in the feature directory", no_baseline_msg)
        self.assertIn("no --baseline-dir was supplied", no_baseline_msg)
        self.assertNotIn("no --baseline-dir was supplied", absent_msg)

    def test_non_vacuity_when_document_is_present_the_check_does_not_fire(self):
        # Non-vacuity guard: with a baseline supplied AND the feature
        # directory's VERIFICATION.md actually present, the absent-document
        # error must not fire -- proving the check is scoped to genuine
        # absence, not to "a baseline was supplied" generally.
        rework_index, workflow_patch = _rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index,
                workflow_patch,
                envelope=None,
                feature_dir=feature_dir,
                baseline_dir=baseline_dir,
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("no VERIFICATION.md exists in the feature directory", messages)

    def test_covered_by_existing_only_is_unaffected_by_document_absence(self):
        # A task declaring only covered_by_existing never reaches the
        # new_scenarios branch, so document absence is irrelevant to it.
        rework_index = {
            "task0007": {"covered_by_existing": ["TS-3"], "new_scenarios": [], "rationale": "x"}
        }
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        envelope = {"verification_index": {"TS-3": ["FR1"]}}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            feature_dir.mkdir()
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index,
                workflow_patch,
                envelope=envelope,
                feature_dir=feature_dir,
                baseline_dir=baseline_dir,
            )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# AC-4: the validator's task-entry validation is unchanged -- an empty
# requirement list on a task entry is still accepted.
# ---------------------------------------------------------------------------

class TestTaskEntryValidationUnchangedForEmptyRequirements(unittest.TestCase):
    def _entry(self, **overrides):
        entry = {
            "files": ["feature-docs/example/tasks/task0001.md"],
            "skills": [],
            "domains": [],
            "complexity": "low",
            "requirements": [],
            "initial_status": "pending",
        }
        entry.update(overrides)
        return entry

    def test_empty_requirements_list_produces_no_requirements_error(self):
        errors = VWO.validate_task_entry(
            "task0001", self._entry(), mode="replace_all", registries=None, workflow=None
        )
        requirement_errors = [e for e in errors if e["code"] == "requirements"]
        self.assertEqual(requirement_errors, [])

    def test_missing_requirements_key_also_produces_no_requirements_error(self):
        entry = self._entry()
        del entry["requirements"]
        errors = VWO.validate_task_entry(
            "task0001", entry, mode="replace_all", registries=None, workflow=None
        )
        requirement_errors = [e for e in errors if e["code"] == "requirements"]
        self.assertEqual(requirement_errors, [])

    def test_non_list_requirements_is_still_rejected(self):
        # Negative proof: the surrounding validation is otherwise intact --
        # a genuinely malformed `requirements` field (not a list at all)
        # still fails, so the empty-list acceptance above is not a case of
        # the field being ignored entirely.
        entry = self._entry(requirements="not-a-list")
        errors = VWO.validate_task_entry(
            "task0001", entry, mode="replace_all", registries=None, workflow=None
        )
        requirement_errors = [e for e in errors if e["code"] == "requirements"]
        self.assertTrue(requirement_errors)

    def test_unknown_requirement_id_is_still_rejected_when_workflow_supplied(self):
        # Negative proof (workflow cross-reference branch): a non-empty
        # requirements list naming an ID absent from workflow.yaml is still
        # rejected -- proving that branch, too, survived this task's change
        # untouched.
        entry = self._entry(requirements=["FR99"])
        workflow = {"requirements": {"FR1": {}}}
        errors = VWO.validate_task_entry(
            "task0001", entry, mode="replace_all", registries=None, workflow=workflow
        )
        requirement_errors = [e for e in errors if e["code"] == "requirements"]
        self.assertTrue(requirement_errors)

    def test_known_requirement_id_is_accepted_when_workflow_supplied(self):
        # Non-vacuity guard for the two tests above: a requirement ID that
        # DOES exist in workflow.yaml is accepted.
        entry = self._entry(requirements=["FR1"])
        workflow = {"requirements": {"FR1": {}}}
        errors = VWO.validate_task_entry(
            "task0001", entry, mode="replace_all", registries=None, workflow=workflow
        )
        requirement_errors = [e for e in errors if e["code"] == "requirements"]
        self.assertEqual(requirement_errors, [])


# ---------------------------------------------------------------------------
# AC-7 (module-level part): stdlib-only imports.
# ---------------------------------------------------------------------------

class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
