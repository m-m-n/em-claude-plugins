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

task0019 acceptance criteria (round2 findings 87ae09bcfe6410c0,
61c73dc71f323f45, cbb5659c4025c46e -- confidence 95: the worker under
scrutiny controlled which file the origin check opened):

- AC-5: step 3 states that the review round record is located by the
  orchestrator from `references/review-phase.md`'s R5 position, that the
  named `stable_id`s are searched only there, and that `evidence[].path`
  is a human-readable hint that is never opened for this check.
- AC-6: step 3 still aborts when the origin is absent, unresolvable, or
  not found in the located record, and when any originating finding's
  category read from that record is `security` or `license`; every abort
  still records its reason and the evidence considered. (Pre-existing
  pins above already cover most of this half unchanged; task0019 adds no
  new assertions here beyond the below since the wording survives
  verbatim.)
- AC-7: `questions[].evidence[]` carries `finding_stable_id`, and step 3
  requires at least one entry carrying it for a `rework.spec-change`
  question, aborting when none does. (The schema half -- the field table
  row itself -- is pinned in tests/test_worker_contract_docs.py.)
- AC-9 (NFR3, partial): the new `finding_stable_id` abort states its
  reason is recorded.

task0025 acceptance criteria (feature-docs/goal-vs-spec-divergence review
round3 rework AC-1, AC-3, AC-5 -- the gate's outcome closes its question):

- AC-1 (FR7, NFR1): the new step 11 ("Outcome") is the one place stating
  what the proceed and stop verdicts each write to the packet and to the
  answer model, citing the field shapes from
  `references/question-packet-schema.md` (answer object) and
  `references/phase-state.md` (`packets[]` / `packets[].questions[]`)
  rather than restating them. (The Batch resolution sequence's citation of
  this step, and the cross-section non-duplication guard, are pinned in
  tests/test_question_resolution_doc.py, alongside the section that cites
  it -- C4.)
- AC-2 (FR7): the proceed bullet names `source: batch-classification-gate`.
  (The schema/validator vocabulary-agreement half of AC-2 is pinned in
  tests/test_gate_outcome_packet_lifecycle.py, which is this task's own
  new cross-document module -- C4.)
- AC-3 (NFR3): no packet resolved by this gate -- proceed, stop, or
  inapplicable -- is left `issued`; the status each outcome leaves is
  named (`answered` on proceed, `obsolete` on stop/inapplicable).
- AC-5 (NFR3): the stop bullet cites the classification audit record
  (step 9) for the stop's reason and evidence rather than defining a
  second record.
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

    # --- task0019 AC-5/AC-7/AC-9: origin verification locates the record ----
    # --- itself; evidence[].path is demoted; finding_stable_id required -----

    def test_record_never_supplied_by_the_packet(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "the review round record that carries them is never supplied "
            "by the packet",
            section,
        )

    def test_orchestrator_locates_record_from_r5_position(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "the orchestrator itself locates it, as the review round "
            "record for this feature at the position "
            "`references/review-phase.md`".lower(),
            section,
        )
        self.assertIn(
            'phase r5: persist the round record" defines', section
        )
        self.assertIn("cited, not restated", section)

    def test_searches_only_the_located_record(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "searches only there for each named `stable_id`".lower(), section
        )

    def test_evidence_path_demoted_to_never_opened_hint(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "`evidence[].path` is a human-readable hint presented to a "
            "reader".lower(),
            section,
        )
        self.assertIn("it is never opened as part of this check", section)

    def test_negative_twin_packet_supplied_path_wording_fails(self):
        # Test Notes: a synthetic sample where the origin check is
        # described as opening a packet-chosen path must fail this matcher.
        fake_section = (
            "**Origin verification.** The orchestrator opens the file at "
            "`evidence[].path` and reads the finding's category from it."
        )
        self.assertNotIn(
            "the review round record that carries them is never supplied "
            "by the packet",
            fake_section.lower(),
        )

    def test_requires_finding_stable_id_on_at_least_one_evidence_entry(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "at least one of its `evidence[]` entries "
            "(`references/question-packet-schema.md`) must carry "
            "`finding_stable_id`".lower(),
            section,
        )

    def test_missing_finding_stable_id_aborts_a_spec_change_question(self):
        section = self._norm(self._origin_verification_section())
        self.assertIn(
            "a `rework.spec-change` question with no `evidence[]` entry "
            "carrying it aborts here, recording that reason".lower(),
            section,
        )

    def test_negative_twin_no_finding_stable_id_requirement_fails(self):
        fake_section = (
            "**Origin verification.** The question must name the "
            "originating review finding(s) by `stable_id` somewhere in its "
            "prose."
        )
        self.assertNotIn(
            "at least one of its `evidence[]` entries "
            "(`references/question-packet-schema.md`) must carry "
            "`finding_stable_id`".lower(),
            fake_section.lower(),
        )

    # --- task0025 AC-1/AC-2/AC-3/AC-5: the "Outcome" step (step 11) --------

    def _outcome_step_section(self):
        section = self._gate_section()
        start = section.index("**Outcome.**")
        return section[start:]

    def test_outcome_step_present_and_non_empty(self):
        # Non-vacuity guard (Test Notes): the section exists and carries
        # content before any content matcher below is trusted.
        section = self._outcome_step_section()
        self.assertTrue(section.strip())
        self.assertGreater(len(section), len("**Outcome.**"))

    def test_outcome_step_is_the_one_place_stating_packet_effects(self):
        section = self._norm(self._outcome_step_section())
        self.assertIn(
            "what each verdict writes to the packet and to the answer "
            "model is stated here, in this one place",
            section,
        )

    def test_outcome_step_cites_owning_documents_rather_than_restating(self):
        section = self._outcome_step_section()
        self.assertIn("`references/question-packet-schema.md`'s answer object", section)
        self.assertIn(
            "`references/phase-state.md`'s `packets[].questions[]`", section
        )
        self.assertIn("`references/phase-state.md`'s `packets[]`", section)

    # --- AC-2: proceed writes one answer record with the gate's source ----

    def test_proceed_writes_one_answer_record_with_gate_source(self):
        section = self._outcome_step_section()
        self.assertIn("**Proceed.**", section)
        norm_section = self._norm(section)
        self.assertIn(
            "one answer record", norm_section
        )
        self.assertIn("`source: batch-classification-gate`", section)
        self.assertIn("`resolution_note`", section)

    def test_proceed_names_the_answered_status(self):
        section = self._norm(self._outcome_step_section())
        self.assertIn(
            "the question's per-question `status`".lower(), section
        )
        self.assertIn("becomes `answered`", section)
        self.assertIn(
            "the packet's own `status` follows the same rule any other "
            "fully-answered packet follows",
            section,
        )

    # --- AC-3/AC-5: stop writes no answer record, closes the packet -------

    def test_stop_writes_no_answer_record(self):
        section = self._outcome_step_section()
        self.assertIn("**Stop.**", section)
        norm_section = self._norm(section)
        self.assertIn("no answer record is written", norm_section)

    def test_stop_names_the_obsolete_status(self):
        section = self._norm(self._outcome_step_section())
        self.assertIn("becomes `obsolete`", section)
        self.assertIn("never re-presents it", section)

    def test_stop_cites_the_audit_record_not_a_second_record(self):
        # AC-5 (NFR1): the stop's reason/evidence are the audit record
        # (step 9) above, not a newly defined second record.
        section = self._norm(self._outcome_step_section())
        self.assertIn(
            "the stop's reason and the evidence considered are the audit "
            "record above",
            section,
        )
        self.assertIn("nothing is duplicated into a second record", section)

    def test_inapplicable_closes_by_the_stop_rule(self):
        section = self._norm(self._outcome_step_section())
        self.assertIn("**inapplicable**".lower(), section)
        self.assertIn(
            "the packet is closed by the stop rule immediately above",
            section,
        )

    def test_no_packet_resolved_by_gate_left_issued(self):
        section = self._norm(self._outcome_step_section())
        self.assertIn(
            "no packet resolved by this gate", section
        )
        self.assertIn(
            "on proceed, on stop, or in the inapplicable case", section
        )
        self.assertIn("is left `issued`", section)

    # --- AC-6 (this task's own new matchers): negative proofs -------------

    def test_negative_twin_missing_answer_record_language_fails(self):
        # A synthetic Outcome step that changes packet status but never
        # mentions writing an answer record must not satisfy the proceed
        # matcher above.
        fake_section = (
            "**Outcome.**\n"
            "- **Proceed.** The question's per-question `status` becomes "
            "`answered`."
        )
        self.assertNotIn("one answer record", fake_section.lower())

    def test_negative_twin_packet_still_issued_fails(self):
        # A synthetic Outcome step that leaves the packet `issued` after a
        # stop must not satisfy either the `obsolete`-status matcher or the
        # "no packet resolved by this gate ... left issued" matcher above.
        fake_section = (
            "**Outcome.**\n"
            "- **Stop.** The packet's own `status` stays `issued` until a "
            "human resumes the run."
        )
        self.assertNotIn("becomes `obsolete`", fake_section)
        self.assertNotIn(
            "no packet resolved by this gate", fake_section.lower()
        )

    # --- section position (extends the existing position pins above) -----

    def test_outcome_step_precedes_batch_resolution_sequence(self):
        outcome_idx = self.text.index("**Outcome.**")
        sequence_idx = self.text.index("## Batch resolution sequence")
        self.assertLess(outcome_idx, sequence_idx)

    def test_outcome_step_follows_unattended_run_continuity(self):
        continuity_idx = self.text.index("**Unattended-run continuity.**")
        outcome_idx = self.text.index("**Outcome.**")
        self.assertLess(continuity_idx, outcome_idx)

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


class TestRoutedArmSingleExceptionToRestoredAbort(unittest.TestCase):
    """task0024 AC-1 (FR11, NFR2, round 3): `category: spec-change` returns
    to the Fail-closed classification's immediate-abort list, and the
    routed arm is written as that abort's single exception, admitted only
    for the exact `gate_id: rework.spec-change` pairing. This class owns
    the routed-arm-adjacent pins for that restoration; the abort-list
    bullet's own retention (security/license/reversible:false) and the
    bidirectional malformed-pairing rule (AC-2) are pinned in
    tests/test_question_resolution_doc.py, alongside the rest of the
    Fail-closed classification section's pre-existing pins (the routed
    arm's own gate_id-keyed entry condition and interactive-mode statement
    are unaffected by this task and stay pinned there too)."""

    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def _abort_list_section(self):
        start = self.text.index("Abort the phase immediately")
        end = self.text.index("**The irreversibility abort's basis")
        return self.text[start:end]

    def _norm(self, section):
        return re.sub(r"\s+", " ", section).lower()

    def test_category_spec_change_is_back_on_the_immediate_abort_list(self):
        section = self._norm(self._abort_list_section())
        self.assertIn(
            "the question's `category` "
            "(`references/question-packet-schema.md`) is `spec-change`",
            section,
        )

    def test_routed_arm_written_as_the_abort_lists_single_exception(self):
        section = self._norm(self._abort_list_section())
        self.assertIn(
            "unless its `gate_id` is exactly `rework.spec-change`", section
        )
        self.assertIn(
            "the routed arm below is written as this abort's single "
            "exception",
            section,
        )
        self.assertIn("admitted for that exact `gate_id` alone", section)

    def test_any_other_gate_id_is_stated_to_abort_recording_its_reason(self):
        section = self._norm(self._abort_list_section())
        self.assertIn(
            "every other `category: spec-change` question aborts here, "
            "recording its reason",
            section,
        )

    def test_negative_twin_plain_spec_change_bullet_without_exception_fails(
        self,
    ):
        # Non-vacuity guard: a bullet that restores `category: spec-change`
        # to the abort list WITHOUT the routed-arm exception clause (which
        # would make the routed arm unreachable for any spec-change
        # question) must not satisfy the exception matcher above.
        fake_section = (
            "- the question's `category` "
            "(`references/question-packet-schema.md`) is `spec-change`;"
        )
        self.assertNotIn(
            "unless its `gate_id` is exactly `rework.spec-change`",
            fake_section.lower(),
        )

    def test_routed_arm_still_reachable_after_restored_abort(self):
        # The abort-list bullet's own exception is what keeps "The routed
        # arm" paragraph (still keyed on gate_id alone, unchanged by this
        # task) reachable for the one pairing it exists to route: its
        # gate_id-keyed entry condition and "does not abort here" statement
        # must survive verbatim after the abort list is restored.
        routed_idx = self.text.index("**The routed arm.**")
        abort_list_idx = self.text.index("Abort the phase immediately")
        self.assertLess(abort_list_idx, routed_idx)
        start = self.text.index("**The routed arm.**")
        end = self.text.index("**Malformed pairing.**")
        section = self._norm(self.text[start:end])
        self.assertIn(
            "the routed arm's entry condition is the question's `gate_id` "
            "being `rework.spec-change`",
            section,
        )
        self.assertIn("does not abort here", section)


if __name__ == "__main__":
    unittest.main()
