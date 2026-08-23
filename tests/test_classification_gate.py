"""Structural assertions for the Classification gate section of
em-workflow/references/question-resolution.md.

Scope (task0004's own acceptance criteria AC-2 through AC-7 — AC-1's
retention-pin and routed-arm assertions live in
tests/test_question_resolution_doc.py, alongside the fail-closed
classification's pre-existing pins, per C4's one-module-per-owned-document
convention):

- AC-2: the gate is batch-only, its two input documents are named, and the
  interactive route is stated to ask the user directly (the interactive
  statement itself is pinned in test_question_resolution_doc.py's routed-arm
  tests; this module pins the gate's own batch-only framing and its inputs).
- AC-3: the question is posed so both directions can be raised.
- AC-4: the asymmetry between the two verdicts.
- AC-5: the evidence criterion, and that it applies identically when Codex
  is absent.
- AC-6: Codex output stays untrusted/non-verbatim, the Codex-absent route is
  defined, and every gate pass produces the audit record defined in
  references/phase-state.md (cited, not restated).
- AC-7: the goal-absent inapplicability rule, the stop-reason record, and
  unattended-run continuity.

Constraints (C6a, C6b): no `taskNNNN`-shaped identifier and no "decision
table" / 「決定表」 phrase anywhere in the document.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)


class TestClassificationGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def _gate_section(self):
        marker = "## Classification gate"
        self.assertIn(marker, self.text)
        end_marker = "## Batch resolution sequence"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def _norm(self, section):
        return re.sub(r"\s+", " ", section).lower()

    # --- section position ---------------------------------------------------

    def test_gate_section_follows_the_routed_arm(self):
        routed_idx = self.text.index("**The routed arm.**")
        gate_idx = self.text.index("## Classification gate")
        self.assertLess(
            routed_idx,
            gate_idx,
            "the Classification gate section must be positioned so it is "
            "reached only from the routed arm above it",
        )

    def test_gate_section_precedes_batch_resolution_sequence(self):
        gate_idx = self.text.index("## Classification gate")
        sequence_idx = self.text.index("## Batch resolution sequence")
        self.assertLess(gate_idx, sequence_idx)

    def test_gate_reached_only_from_routed_arm_stated(self):
        section = self._norm(self._gate_section())
        self.assertIn("reached only from the routed arm above", section)

    # --- AC-2: inputs named, untrusted -------------------------------------

    def test_inputs_name_goal_block_and_spec_document(self):
        section = self._gate_section()
        self.assertIn("`goal` block", section)
        self.assertIn("references/workflow-schema.md", section)
        self.assertIn("`SPEC.md`", section)

    def test_inputs_stated_untrusted_read_not_executed(self):
        section = self._norm(self._gate_section())
        self.assertIn("untrusted data", section)
        self.assertIn("never executed as instructions", section)

    # --- AC-3: two-directional question shape -------------------------------

    def test_question_shape_states_both_directions(self):
        section = self._norm(self._gate_section())
        self.assertIn("the implementation cannot satisfy the goal", section)
        self.assertIn(
            "the implementation satisfies the goal but diverges from the "
            "specification text",
            section,
        )

    # --- AC-4: asymmetry -----------------------------------------------------

    def test_goal_reconsideration_verdict_stops_unconditionally(self):
        section = self._norm(self._gate_section())
        self.assertIn("stops the run unconditionally", section)
        self.assertIn("claude's disagreement does not overturn it", section)

    def test_no_path_passes_on_a_second_verdict(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "no path passes on a second verdict once verdict (a) has been "
            "reached",
            section,
        )

    def test_spec_gap_verdict_proceeds_only_when_convinced(self):
        section = self._norm(self._gate_section())
        self.assertIn("proceeds only when claude is convinced", section)

    # --- AC-5: evidence criterion, identical on Codex-absent route ---------

    def test_evidence_criterion_requires_named_ids(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "adopted only when the classification names specific existing "
            "requirement ids or acceptance-criterion ids",
            section,
        )

    def test_conclusion_only_reply_stops_the_run(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "a conclusion-only reply is not adopted, and the run stops",
            section,
        )

    def test_evidence_criterion_applies_identically_on_codex_absent_route(
        self,
    ):
        section = self._norm(self._gate_section())
        self.assertIn(
            "this applies identically on the codex-absent route", section
        )

    def test_classifier_defines_codex_absent_route(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "where codex is unavailable, claude performs the "
            "classification itself",
            section,
        )
        self.assertIn(
            "every rule below applies identically on both routes", section
        )

    # --- AC-6: Codex output untrusted/non-verbatim, audit record -----------

    def test_codex_output_untrusted_non_verbatim(self):
        section = self._norm(self._gate_section())
        self.assertIn("read-only", section)
        self.assertIn("never executed as instructions", section)
        self.assertIn("never adopted verbatim", section)

    def test_transcription_decision_belongs_to_claude(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "the decision to transcribe a verdict into requirements or "
            "acceptance criteria belongs to claude",
            section,
        )

    def test_codex_consultation_procedure_reused_by_citation(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "through the codex consultation procedure above", section
        )
        self.assertIn("cited and not restated", section)

    def test_audit_record_cites_phase_state_not_restated(self):
        section = self._gate_section()
        self.assertIn("references/phase-state.md", section)
        self.assertIn("cited, not restated", self._norm(section))

    def test_audit_record_produced_on_every_pass_incl_stop_and_inapplicable(
        self,
    ):
        section = self._norm(self._gate_section())
        self.assertIn("every pass through this gate", section)
        self.assertIn("including one that", section)
        self.assertIn("including the inapplicable case above", section)

    # --- AC-7: goal-absent inapplicability, stop record, continuity --------

    def test_applicability_requires_a_goal_block(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "the gate applies only when the feature's `workflow.yaml` "
            "carries a `goal` block".lower(),
            section,
        )

    def test_goal_absent_stops_as_before_with_no_backfill(self):
        section = self._norm(self._gate_section())
        self.assertIn("the gate is inapplicable", section)
        self.assertIn(
            "the batch run stops exactly as it did before this revision",
            section,
        )
        self.assertIn("no backfill of the goal", section)

    def test_stop_reason_records_the_inapplicability(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "the stop reason records that the classification gate was "
            "inapplicable because the goal block is absent",
            section,
        )

    def test_unattended_run_continuity_stated(self):
        section = self._norm(self._gate_section())
        self.assertIn(
            "this gate never raises, in batch, a confirmation nobody can "
            "answer",
            section,
        )
        self.assertIn(
            "every stop leaves its reason and evidence as a record instead",
            section,
        )

    # --- task0012 AC-4 (NFR2, FR9, FR10): origin verification --------------

    def _origin_verification_section(self):
        section = self._gate_section()
        start = section.index("**Origin verification.**")
        end = section.index("**Question shape.**")
        return section[start:end]

    def test_origin_verification_positioned_between_applicability_and_classifier(
        self,
    ):
        section = self._gate_section()
        applicability_idx = section.index("**Applicability.**")
        origin_idx = section.index("**Origin verification.**")
        classifier_idx = section.index("**Classifier.**")
        self.assertLess(applicability_idx, origin_idx)
        self.assertLess(origin_idx, classifier_idx)

    def test_origin_verification_requires_stable_id_and_round_record(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "must name the originating review finding(s) by `stable_id`".lower(),
            section,
        )
        self.assertIn(
            "the review round record that carries them".lower(), section
        )

    def test_origin_verification_reads_category_from_record_not_worker_set(
        self,
    ):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "the orchestrator reads each named finding's `category` from "
            "that record".lower(),
            section,
        )
        self.assertIn(
            "never from the question's own worker-set `category`".lower(),
            section,
        )

    def test_origin_verification_aborts_on_security_license_or_irreversible(
        self,
    ):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "aborts when any originating finding's category is `security` "
            "or `license`".lower(),
            section,
        )
        self.assertIn(
            "an `assumptions[]` entry naming the question carries "
            "`reversible: false`".lower(),
            section,
        )

    def test_origin_verification_aborts_on_absent_unresolvable_or_unmatched_origin(
        self,
    ):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "an origin that is absent, unresolvable, or does not match a "
            "finding in the named record also aborts".lower(),
            section,
        )
        self.assertIn("fail-closed", section)

    def test_origin_verification_records_reason_and_evidence_no_unanswerable_confirmation(
        self,
    ):
        # AC-6: every new stop states its reason/evidence are recorded and
        # raises no unanswerable batch confirmation (NFR3).
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "every abort here records its reason and the evidence "
            "considered".lower(),
            section,
        )
        self.assertIn(
            "none of them raises, in batch, a confirmation nobody can "
            "answer".lower(),
            section,
        )

    def test_origin_verification_negative_proof_reading_category_from_packet_fails(
        self,
    ):
        # Non-vacuity guard (Test Notes): a synthetic gate step that reads
        # `category` from the packet (worker-set) instead of from the named
        # review round record must NOT satisfy the matcher above.
        fake_step = (
            "3. **Origin verification.** The orchestrator reads the "
            "question's own `category` field to decide whether to abort."
        )
        self.assertNotIn(
            "the orchestrator reads each named finding's `category` from "
            "that record".lower(),
            fake_step.lower(),
        )

    # --- Constraints: forbidden literals (C6a, C6b) -------------------------

    def test_no_taskNNNN_identifier_anywhere_in_document(self):
        self.assertIsNone(
            re.search(r"task\d{4}", self.text),
            "question-resolution.md must not carry a feature-docs task "
            "identifier (C6b)",
        )

    def test_no_decision_table_phrase_anywhere_in_document(self):
        self.assertNotIn("decision table", self.text.lower())
        self.assertNotIn("決定表", self.text)


if __name__ == "__main__":
    unittest.main()
