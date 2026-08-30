"""Tests for task0029 (goal-vs-spec-divergence): the classification audit
record's accumulation and two-pass retention (feature-docs/
goal-vs-spec-divergence/tasks/task0029.md).

Covers task0029 Acceptance Criteria:

- AC-3 (FR14, NFR3): `references/phase-state.md` defines `classification`
  as an append-type list -- pinned here at the validator level: a document
  whose `classification` value is a single mapping (what a wholesale
  replace would leave behind) is rejected.
- AC-4 (FR14, NFR3): a phase-state document carrying two `classification`
  entries validates, and both entries' `classifier`, `verdict`,
  `evidence_ids`, `decision` and `reason` are readable afterwards; a
  document in which a second pass replaced the first is detected as a
  violation.
- AC-7 (NFR5): a negative proof per matcher -- a document that replaces
  the record, one that drops an earlier entry's `reason` -- and a
  non-vacuity guard on every absence assertion.

Driven directly against `validate_phase_state` (`--kind phase-state`,
design-input.md 5.6), per the task's Test Notes: "AC-4 and AC-6 are
executable end to end: drive them through the validator with real
documents and fixtures rather than by scanning prose." No fixture
directory is added for this task (Files to Create names only this module;
`references/fixtures/phase-state/*` groups are status-keyed and owned by
task0003, C4) -- coverage is direct unit tests against the validator
function instead, following the precedent
`TestCarriedTaskIdsNamingAnUnregisteredIdRejected`
(tests/test_replanning_carry_over.py, task0023) set for a narrow check
staying within its own task's file scope.

AC-3's document-level half (the wholesale-replacement statement is gone
from `references/phase-state.md`'s field table and the record leaves the
id-uniqueness exemption) is a string/structure scan and lives in
`tests/test_phase_state_doc.py` (`TestClassificationAuditRecord`,
`TestClassificationAuditRecordNegativeProof`) per Test Notes: "The
document assertions (AC-1 ... AC-3, AC-5) are string / structure scans."
This module does not duplicate those checks (C4/DRY within the task).
"""

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output_classification_retention", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


def _base_phase_state(**overrides):
    base = {
        "schema_version": 1,
        "feature": "example",
        "phase": "rework",
        "status": "completed",
        "generation": 1,
    }
    base.update(overrides)
    return base


def _entry(*, classifier="codex", verdict="goal_not_met", evidence_ids=None,
           decision="proceed", reason=None):
    entry = {
        "classifier": classifier,
        "verdict": verdict,
        "evidence_ids": evidence_ids if evidence_ids is not None else [],
        "decision": decision,
    }
    if reason is not None:
        entry["reason"] = reason
    return entry


# ---------------------------------------------------------------------------
# AC-4: accumulation -- two (and n) entries validate, and both remain
# readable afterwards.
# ---------------------------------------------------------------------------


class TestClassificationListAccumulates(unittest.TestCase):
    def test_two_entries_validate(self):
        data = _base_phase_state(
            classification=[
                _entry(decision="stop", reason="first pass: no evidence yet"),
                _entry(verdict="spec_gap", evidence_ids=["FR14"], decision="proceed"),
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)

    def test_both_entries_fields_are_readable_after_validation(self):
        data = _base_phase_state(
            classification=[
                _entry(decision="stop", reason="first pass: no evidence yet"),
                _entry(verdict="spec_gap", evidence_ids=["FR14"], decision="proceed"),
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [])
        first, second = data["classification"]
        self.assertEqual(first["classifier"], "codex")
        self.assertEqual(first["verdict"], "goal_not_met")
        self.assertEqual(first["evidence_ids"], [])
        self.assertEqual(first["decision"], "stop")
        self.assertEqual(first["reason"], "first pass: no evidence yet")
        self.assertEqual(second["classifier"], "codex")
        self.assertEqual(second["verdict"], "spec_gap")
        self.assertEqual(second["evidence_ids"], ["FR14"])
        self.assertEqual(second["decision"], "proceed")

    def test_a_third_pass_still_accumulates_n_entries(self):
        data = _base_phase_state(
            classification=[_entry(), _entry(), _entry(verdict="not_applicable")]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)
        self.assertEqual(len(data["classification"]), 3)

    def test_single_entry_still_validates(self):
        # The n=1 case of the same rule, not a special case.
        data = _base_phase_state(classification=[_entry()])
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)

    def test_absent_classification_is_not_an_error(self):
        # classification is present only when phase: rework AND at least
        # one gate pass has occurred -- its absence is not itself a
        # violation.
        data = _base_phase_state()
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)


# ---------------------------------------------------------------------------
# AC-3 / AC-4: a document in which a second pass replaced the first --
# classification persisted as a single mapping instead of an accumulating
# list -- is detected as a violation.
# ---------------------------------------------------------------------------


class TestClassificationWholesaleReplaceIsAViolation(unittest.TestCase):
    def test_classification_as_a_mapping_is_rejected(self):
        data = _base_phase_state(
            classification={
                "classifier": "codex",
                "verdict": "goal_not_met",
                "evidence_ids": [],
                "decision": "proceed",
            }
        )
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(errors, [], "a mapping classification must be rejected")
        codes = {e["code"] for e in errors}
        self.assertIn("classification", codes)

    def test_non_vacuity_the_same_content_wrapped_in_a_list_is_accepted(self):
        # Proves the check above is about the TYPE (list vs. mapping), not
        # the content -- the same fields, wrapped in a one-element list,
        # pass.
        data = _base_phase_state(
            classification=[
                {
                    "classifier": "codex",
                    "verdict": "goal_not_met",
                    "evidence_ids": [],
                    "decision": "proceed",
                }
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)

    def test_non_mapping_entry_inside_the_list_is_rejected(self):
        data = _base_phase_state(classification=[_entry(), "not-a-mapping"])
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(errors, [])
        codes = {e["code"] for e in errors}
        self.assertIn("classification", codes)

    def test_non_vacuity_two_well_formed_mappings_in_a_list_pass(self):
        data = _base_phase_state(classification=[_entry(), _entry()])
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)


# ---------------------------------------------------------------------------
# AC-7: negative proof -- a document that drops an earlier entry's
# `reason` (the exact loss the wholesale-replace defect used to cause,
# NFR3: "a stop's reason and evidence remain").
# ---------------------------------------------------------------------------


class TestEarlierEntryReasonMustSurviveAccumulation(unittest.TestCase):
    def test_earlier_stop_entrys_missing_reason_is_rejected(self):
        data = _base_phase_state(
            classification=[
                _entry(decision="stop"),  # reason dropped -- the defect
                _entry(decision="proceed"),
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(
            errors, [], "a stop entry missing its reason must be rejected"
        )
        codes = {e["code"] for e in errors}
        self.assertIn("classification", codes)

    def test_non_vacuity_the_same_entry_with_reason_present_passes(self):
        data = _base_phase_state(
            classification=[
                _entry(decision="stop", reason="first pass stopped here"),
                _entry(decision="proceed"),
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)

    def test_earlier_entrys_reason_is_still_readable_after_a_later_pass_accumulates(self):
        data = _base_phase_state(
            classification=[
                _entry(decision="stop", reason="first pass stopped here"),
                _entry(decision="proceed"),
            ]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [])
        self.assertEqual(
            data["classification"][0]["reason"], "first pass stopped here"
        )
        # The later entry never inherits or overwrites the earlier one's
        # reason -- each entry's own fields are independent.
        self.assertNotIn("reason", data["classification"][1])

    def test_spec_gap_entry_missing_evidence_ids_is_rejected(self):
        # Same defect shape, the other mandatory-when field (Out of Scope:
        # the field-set rule itself -- non-empty evidence_ids for
        # spec_gap -- is unchanged; this proves it survives being
        # ENFORCED once classification became a list).
        data = _base_phase_state(
            classification=[_entry(verdict="spec_gap", evidence_ids=[])]
        )
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(errors, [])
        codes = {e["code"] for e in errors}
        self.assertIn("classification", codes)

    def test_non_vacuity_spec_gap_entry_with_evidence_ids_passes(self):
        data = _base_phase_state(
            classification=[_entry(verdict="spec_gap", evidence_ids=["FR14"])]
        )
        errors = VWO.validate_phase_state(data)
        self.assertEqual(errors, [], errors)


# ---------------------------------------------------------------------------
# Field-vocabulary checks (unchanged field set, Out of Scope -- proven so
# the list-shape addition above did not accidentally narrow or widen it).
# ---------------------------------------------------------------------------


class TestClassificationFieldVocabularyUnchanged(unittest.TestCase):
    def test_classifier_must_be_codex_or_claude(self):
        for bad in ("gpt", "", None):
            with self.subTest(bad=bad):
                data = _base_phase_state(classification=[_entry(classifier=bad)])
                errors = VWO.validate_phase_state(data)
                self.assertNotEqual(errors, [])

    def test_verdict_must_be_one_of_the_three_values(self):
        data = _base_phase_state(classification=[_entry(verdict="something_else")])
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(errors, [])

    def test_decision_must_be_proceed_or_stop(self):
        data = _base_phase_state(classification=[_entry(decision="pause")])
        errors = VWO.validate_phase_state(data)
        self.assertNotEqual(errors, [])

    def test_non_vacuity_every_legal_value_combination_passes(self):
        for classifier in ("codex", "claude"):
            for verdict in ("goal_not_met", "not_applicable"):
                with self.subTest(classifier=classifier, verdict=verdict):
                    data = _base_phase_state(
                        classification=[_entry(classifier=classifier, verdict=verdict)]
                    )
                    errors = VWO.validate_phase_state(data)
                    self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
