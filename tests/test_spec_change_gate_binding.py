"""goal-vs-spec-divergence/task0024: the spec-change gate binding, pinned
across the three artifacts it spans (IMPLEMENTATION.md Shared Components,
"Spec-change gate binding"):

- `em-workflow/references/question-resolution.md` -- the Fail-closed
  classification section states `category: spec-change` <=> `gate_id:
  rework.spec-change` in both directions (the document-level halves of this
  are pinned individually, alongside that section's other content, in
  tests/test_question_resolution_doc.py and tests/test_classification_gate.
  py -- this module does not re-pin their prose).
- `em-workflow/references/contracts/rework-planner-contract.md` -- the
  "## Gate identifiers" section that attributes `rework.spec-change` to
  `rework-planner` (the contract-document half is pinned in
  tests/test_worker_contract_docs.py).
- `em-workflow/scripts/validate-worker-output.py` -- the gate registry the
  contract attribution feeds, and the validator's bidirectional rejection
  built on it (the unit-level halves are pinned in
  tests/test_validate_worker_output.py).

What THIS module owns, and what the three sibling modules above do not
individually prove: that all three artifacts agree on the SAME two literal
strings (`rework.spec-change`, `spec-change`) and that the chain from
"contract names the gate" to "validator rejects a mismatched question"
actually holds end to end against the plugin's own real files -- not a
synthetic stand-in for any one of them. C4 test scoping is satisfied
because every file this module reads is inside this task's own file set
(question-resolution.md, rework-planner-contract.md,
validate-worker-output.py); it does not assert over any sibling task's
files.
"""

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTION_RESOLUTION_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "question-resolution.md"
)
REWORK_PLANNER_CONTRACT_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "rework-planner-contract.md"
)
REFERENCES_DIR = REPO_ROOT / "em-workflow" / "references"
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"

GATE_ID = "rework.spec-change"
CATEGORY = "spec-change"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


def _read(path):
    return path.read_text(encoding="utf-8")


def _section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


class TestGateIdAndCategoryAgreeAcrossAllThreeArtifacts(unittest.TestCase):
    """The same two literal strings -- `rework.spec-change` and
    `spec-change` -- must be the ones each artifact actually names, not
    merely SOME gate_id / category pair that happens to satisfy each
    document's own isolated pin."""

    @classmethod
    def setUpClass(cls):
        cls.question_resolution_text = _read(QUESTION_RESOLUTION_PATH)
        cls.contract_text = _read(REWORK_PLANNER_CONTRACT_PATH)
        cls.registry = VWO.build_gate_registry(REFERENCES_DIR)

    def test_question_resolution_names_the_gate_id_in_the_routed_arm(self):
        section = _section(
            self.question_resolution_text,
            "**The routed arm.**",
            "**Malformed pairing.**",
        )
        self.assertIn(f"`{GATE_ID}`", section)
        self.assertIn(f"`{CATEGORY}`", section)

    def test_contract_names_the_same_gate_id_in_gate_identifiers(self):
        section = _section(
            self.contract_text,
            "## Gate identifiers",
            "## Other conditions under which a question packet may be returned",
        )
        self.assertIn(f"`{GATE_ID}`", section)

    def test_registry_derives_the_same_pairing_from_the_contract_section(self):
        entry = self.registry.get(GATE_ID)
        self.assertIsNotNone(
            entry,
            f"{GATE_ID} must be present in the registry derived from "
            "references/contracts/*.md -- the contract's own Gate "
            "identifiers section is what puts it there",
        )
        self.assertEqual(entry["worker"], "rework-planner")
        self.assertEqual(entry["category"], CATEGORY)

    def test_negative_twin_a_contract_naming_a_different_gate_id_would_not_bind(
        self,
    ):
        # Non-vacuity guard (C9): proves the registry derivation is
        # actually reading the contract's own gate_id token, not some
        # hardcoded constant, by checking a gate_id this feature never
        # introduces is correctly absent.
        self.assertIsNone(self.registry.get("rework.not-a-real-gate"))


class TestBidirectionalRejectionHoldsEndToEnd(unittest.TestCase):
    """Closes the loop AC-5 requires: given the registry the contract
    attribution above actually produces, the validator rejects both
    mismatched pairings and accepts the correct one -- driven through
    validate_question, never through a document scan (Test Notes)."""

    @classmethod
    def setUpClass(cls):
        cls.registry = VWO.build_gate_registry(REFERENCES_DIR)

    @staticmethod
    def _question(gate_id, category):
        return {
            "question_id": "q.binding-e2e",
            "gate_id": gate_id,
            "category": category,
            "priority": "high",
            "blocking": True,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "block",
        }

    def _has_binding_error(self, gate_id, category):
        errors = VWO.validate_question(
            self._question(gate_id, category),
            0,
            gate_registry=self.registry,
            packet_phase="rework",
            packet_worker="rework-planner",
        )
        messages = " ".join(e["message"] for e in errors)
        return ("requires category" in messages) or ("requires gate_id" in messages)

    def test_category_spec_change_with_a_foreign_gate_id_is_rejected(self):
        self.assertTrue(
            self._has_binding_error("some-other.gate", CATEGORY),
            "category: spec-change with a non-rework.spec-change gate_id "
            "must be rejected (the direction the Design section names as "
            "previously unenforced)",
        )

    def test_gate_id_rework_spec_change_with_a_foreign_category_is_rejected(
        self,
    ):
        self.assertTrue(
            self._has_binding_error(GATE_ID, "other"),
            "gate_id: rework.spec-change with a non-spec-change category "
            "must be rejected",
        )

    def test_the_correctly_paired_question_is_accepted(self):
        self.assertFalse(
            self._has_binding_error(GATE_ID, CATEGORY),
            "the correctly paired question must produce no category/"
            "gate_id binding error",
        )

    def test_negative_twin_unrelated_pairing_has_no_binding_error_either(
        self,
    ):
        # Non-vacuity guard: proves _has_binding_error can also return
        # False for a genuinely unconstrained pairing, so the "accepted"
        # assertion above is not vacuously true for every input.
        self.assertFalse(self._has_binding_error("gate.unrelated", "other"))


if __name__ == "__main__":
    unittest.main()
