"""Structural assertions for em-workflow/references/question-resolution.md.

Pre-existing coverage (kept passing per this task's Test Notes, not tied to
this task's own acceptance criteria):
- deduplication rules in order, the priority sort, `depends_on` deferral,
  and the presentation limits.
- the batch resolution sequence, including that a missing option ID is a
  protocol error and label matching may not substitute for it.
- the Codex consultation procedure's substance (availability probe, wrapper
  invocation, one turn per call, trajectory judgement, turn ceiling, who
  decides, untrusted-output rule) and the fail-closed classification's
  content (category values, explicit gate list, irreversible-assumption
  signal, cross-check reference, intentional behaviour-change note).

Batch classification gate (this task's own acceptance criteria — see
task0004's AC-1): the fail-closed classification's four abort arms become
three abort arms (`security`, `license`, `reversible: false`) plus one
routed arm (`spec-change` / `rework.spec-change`, routed to the
Classification gate in batch; asked directly in interactive). The retention
pins below assert the three unchanged abort arms individually, plus the
"regardless of ..." clauses that make them non-overridable, and the
four-category sentence pin is replaced with a three-category-plus-routed
pin of the same specificity (C5). The Classification gate section itself is
pinned in `tests/test_classification_gate.py`.

task0022 acceptance criteria (round2.yaml findings bs2, bs3, bs6, bs8 —
correcting round1's "presenter" criterion to gate-identifier presence):

- AC-1: the document states the jurisdiction as gate-identifier presence
  (a `gate_id` resolves the same way whether packet-borne or
  orchestrator-opened), not as "packet vs non-packet by presenter".
- AC-3: the Batch resolution sequence's entry condition covers an
  orchestrator-opened gate (no worker packet) and states how an answer is
  formed in that case (`packet_id` null, direct action instead of
  re-dispatch).
- AC-4 (bs2): the fail-closed classification is hoisted into its own
  section, appearing before ANY policy lookup — so it applies to a listed
  `gate_id` exactly as it applies to an unlisted one — and the
  Unlisted-gate fallback references it rather than restating it.
- AC-6 (bs6): the Codex consultation carries a bound independent of
  question count (packet-level batching, not one consultation per
  question), and the re-sent history is capped/summarized rather than
  growing every turn.
- AC-7 (bs8): no feature-docs task identifier (`task00NN`) is cited as the
  attribution for the category/on_unanswered cross-check; the citation
  instead points at `references/question-packet-schema.md`, which states
  the constraint AND names the enforcing script itself (a second,
  independent assertion below covers question-packet-schema.md's own
  text, since AC-7 spans both documents).

task0019 acceptance criteria (round2 findings 87ae09bcfe6410c0,
61c73dc71f323f45 -- confidence 95: the gate's routing and its origin check
both consumed values the worker under scrutiny supplied):

- AC-1: the routed arm's entry condition is stated as the question's
  `gate_id` being `rework.spec-change`, and the section states that the
  worker-set `category` never selects a route.
- AC-2: a packet whose `gate_id` is `rework.spec-change` but whose
  `category` is not `spec-change` is stated to abort as malformed -- it
  reaches neither the routed arm nor the unlisted-gate fallback.
- AC-3: irreversibility is decided from orchestrator-held metadata about
  the operation, and a packet's `reversible: false` still aborts in
  addition; omitting the assumption cannot remove the abort.
- AC-4 (retention): the three immediate-abort conditions and the
  precedence reservation survive unchanged (asserted individually by the
  pre-existing retention tests above; this task adds one consolidated
  confirmation).
- AC-9 (NFR3, partial): the new malformed-pairing and orchestrator-held
  irreversibility stops each state that their reason is recorded. (The
  origin-verification half of AC-9 is pinned in
  tests/test_classification_gate.py, alongside the section it belongs to.)

The Classification gate's own step 3 (origin verification) rewrite --
AC-5 through AC-7 -- is pinned in tests/test_classification_gate.py, per
C4's one-module-per-section convention; question-packet-schema.md's new
`finding_stable_id` field (AC-7's schema half) is pinned in
tests/test_worker_contract_docs.py, alongside that document's other field
pins.

task0025 acceptance criteria (feature-docs/goal-vs-spec-divergence review
round3 rework, AC-1 half): the routed arm's exit sentence at Batch
resolution sequence step 2 no longer ends the question's story in place
("the gate's own proceed/stop outcome and its audit record are the
resolution for that question") -- it now points at the Classification
gate's own Outcome step (pinned in tests/test_classification_gate.py,
alongside the section it belongs to, per C4). The pins below cover only
the citation change at step 2 and the NFR1 non-duplication guard (the
packet/answer-model rule the Outcome step states must not be restated a
second time anywhere else in this document, including the Batch resolution
sequence itself).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)
SCHEMA_DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-packet-schema.md"
)


class TestQuestionResolutionDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        # Whitespace-collapsed rendering for phrase assertions that must not
        # be sensitive to Markdown line-wrapping.
        cls.norm = re.sub(r"\s+", " ", cls.text)

    # --- pre-existing: deduplication rules, in order ----------------------

    def test_dedup_rule_same_question_id(self):
        self.assertIn("question_id", self.text)
        self.assertIn("worker protocol violation", self.text)

    def test_dedup_rule_supersedes(self):
        self.assertIn("supersedes", self.text)
        self.assertIn("obsoletes", self.text.lower())

    def test_dedup_rule_gate_evidence_field_match(self):
        self.assertIn("gate_id", self.text)
        self.assertIn("evidence", self.text)
        self.assertIn("duplicate candidate", self.text)

    def test_dedup_rule_no_prose_judgment(self):
        self.assertIn("prose differences", self.text)
        self.assertIn("stable question ID", self.text)

    def test_dedup_rule_answered_never_represented(self):
        self.assertIn("never re-presented", self.text)

    def test_dedup_rules_appear_in_order(self):
        markers = [
            "question_id",
            "supersedes",
            "duplicate candidate",
            "prose differences",
            "never re-presented",
        ]
        positions = [self.text.index(m) for m in markers]
        self.assertEqual(positions, sorted(positions))

    # --- pre-existing: priority sort + depends_on deferral ----------------

    def test_priority_sort_blocking_first(self):
        self.assertIn("blocking", self.text)

    def test_priority_sort_priority_levels_in_order(self):
        match = re.search(
            r"critical\s*→\s*high\s*→\s*normal\s*→\s*low", self.text
        )
        self.assertIsNotNone(match, "priority levels not stated in order")

    def test_priority_sort_category_order(self):
        for category in [
            "feature-identity",
            "business-objective",
            "functional-requirement",
            "acceptance-criteria",
            "security",
            "technical-requirement",
            "testing",
            "edge-case",
        ]:
            self.assertIn(category, self.text)

    def test_depends_on_deferral(self):
        self.assertIn("depends_on", self.text)
        self.assertIn("withheld from presentation", self.text)

    # --- pre-existing: presentation limits, as numbers --------------------

    def test_presentation_limits_are_numeric(self):
        self.assertIn("3 questions", self.text)
        self.assertIn("4 options", self.text)
        self.assertIn("32 questions", self.text)

    # --- pre-existing: batch resolution sequence --------------------------

    def test_batch_resolution_sequence_present(self):
        self.assertIn("needs_user_input", self.text)
        self.assertIn("batch-policies.yaml", self.text)
        self.assertIn("source: batch-decision-table", self.text)

    def test_missing_option_id_is_protocol_error(self):
        self.assertIn("protocol error", self.text)

    def test_label_matching_forbidden_as_substitute(self):
        self.assertIn("label matching is never substituted", self.text)

    # --- AC-1: jurisdiction stated as gate-identifier presence -------------
    # --- (round2 bs3: the criterion is identifier presence, never who     --
    # --- presents the gate)                                               --

    def test_jurisdiction_stated_as_identifier_presence_not_presenter(self):
        self.assertIn(
            "whether a worker returned it inside a question", self.norm
        )
        self.assertIn(
            "packet or the orchestrator raised the question directly "
            "outside of any",
            self.norm,
        )

    def test_artifact_overwrite_family_named_as_orchestrator_opened_example(self):
        self.assertIn("{phase}.artifact-overwrite", self.text)
        self.assertIn(
            "references/contracts/spec-writer-contract.md", self.text
        )

    def test_jurisdiction_does_not_turn_on_presenter(self):
        self.assertIn(
            "the jurisdiction below never turns on which one happened",
            self.norm,
        )

    # --- AC-3: batch resolution sequence covers orchestrator-opened gates -

    def _batch_sequence_section(self):
        marker = "## Batch resolution sequence"
        self.assertIn(marker, self.text)
        end_marker = "## Unlisted-gate fallback"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def test_entry_condition_covers_both_packet_and_orchestrator_opened(self):
        section = self._batch_sequence_section()
        self.assertIn("status: needs_user_input", section)
        self.assertIn(
            "the orchestrator raises the question directly outside any",
            section,
        )

    def test_answer_formed_without_a_packet_is_described(self):
        section = self._batch_sequence_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("`packet_id` is null", norm_section)
        self.assertIn(
            "`question_id` is the gate's own `gate_id`", norm_section
        )

    def test_no_packet_means_direct_action_not_redispatch(self):
        section = self._batch_sequence_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "the orchestrator instead acts on the decision directly at the",
            norm_section,
        )
        self.assertIn("rather than re-dispatching a worker turn", norm_section)

    # --- AC-4 (bs2): classification hoisted above BOTH branches -----------

    def test_classification_section_precedes_batch_resolution_sequence(self):
        classify_idx = self.text.index("## Fail-closed classification")
        sequence_idx = self.text.index("## Batch resolution sequence")
        self.assertLess(
            classify_idx,
            sequence_idx,
            "the classification section must precede the batch resolution "
            "sequence in document order",
        )

    def test_classification_precedes_any_policy_lookup(self):
        classify_idx = self.text.index("## Fail-closed classification")
        lookup_idx = self.text.index(
            "Look up the `gate_id` in `references/batch-policies.yaml`."
        )
        self.assertLess(
            classify_idx,
            lookup_idx,
            "the classification must precede the policy-table lookup, so "
            "a LISTED gate is classified too",
        )

    def test_classification_precedes_unlisted_gate_fallback(self):
        classify_idx = self.text.index("## Fail-closed classification")
        fallback_idx = self.text.index("## Unlisted-gate fallback")
        self.assertLess(classify_idx, fallback_idx)

    def test_classification_applies_regardless_of_listing(self):
        self.assertIn(
            "regardless of whether that `gate_id` turns out to have an "
            "entry in",
            self.norm,
        )
        self.assertIn(
            "this is what makes a listed gate classified too", self.norm.lower()
        )

    def test_fallback_references_classification_rather_than_restating(self):
        marker = "## Unlisted-gate fallback"
        section = self.text.split(marker, 1)[1]
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "the fail-closed classification above has already run",
            norm_section.lower(),
        )
        self.assertIn(
            "this fallback does not re-classify and does not restate the "
            "rule",
            norm_section,
        )

    def test_fail_closed_categories_named(self):
        # AC-1: the three abort arms (security, license, irreversible) are
        # named together with unchanged force. Replaces the old
        # four-category pin (spec-change no longer aborts here) at the same
        # specificity (C5) — see test_old_four_category_sentence_is_gone for
        # the corresponding negative proof.
        self.assertTrue(
            re.search(
                r"Security,\s+licensing,\s+and\s+irreversible\s+operations\s+"
                r"abort\s+the\s+phase\s+immediately",
                self.text,
            ),
            "fail-closed rule must name security, licensing and "
            "irreversible operations together, unchanged",
        )

    def test_fail_closed_categories_outside_revision_scope(self):
        # AC-1/NFR2: the three-arm sentence states they are outside this
        # revision's scope, so the classification gate can never be read as
        # a bypass around them.
        self.assertIn("outside this revision's scope", self.norm)
        self.assertIn(
            "none of the classification gate's steps", self.norm.lower()
        )

    def test_old_four_category_sentence_is_gone(self):
        # Negative proof (Test Notes): no surviving sentence names
        # spec-change among the immediate, unconditional aborts.
        self.assertNotIn(
            "Specification change, security, licensing, and irreversible "
            "operations abort",
            self.text,
        )

    # --- retention pins (TS-4): the three unchanged abort arms, individually

    def test_security_and_license_abort_arm_retained(self):
        self.assertIn(
            "the question's `category` "
            "(`references/question-packet-schema.md`) is `security` or "
            "`license`",
            self.norm,
        )

    def test_irreversible_assumption_abort_arm_retained(self):
        self.assertIn(
            "an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation.",
            self.norm,
        )

    def test_explicit_gate_list_mechanism_retained_as_a_slot(self):
        # The list mechanism survives for a future entry; `rework.spec-change`
        # is explicitly removed from it (see the routed-arm tests below).
        self.assertIn(
            "the `gate_id` appears on the explicit fail-closed gate list",
            self.norm,
        )

    def test_spec_change_no_longer_cited_as_todays_gate_list_entry(self):
        # Negative proof: the old wording that made `rework.spec-change` an
        # abort-arm example ("today, per the comment in
        # references/batch-policies.yaml") is gone.
        self.assertNotIn(
            "`rework.spec-change` today, per the comment in", self.text
        )

    # --- AC-1/FR7/FR8/D8: the routed arm ------------------------------------

    def test_routed_arm_present_and_not_aborting(self):
        self.assertIn("**The routed arm.**", self.text)
        self.assertIn(
            "does not abort here", self.norm
        )

    def test_routed_arm_states_batch_routes_to_classification_gate(self):
        # AC-1/AC-2: batch routes spec-change to the classification gate
        # instead of aborting.
        self.assertIn(
            "in batch, it is routed to the classification gate below "
            "instead of aborting",
            self.norm.lower(),
        )

    def test_routed_arm_states_interactive_asks_directly(self):
        # AC-2/FR8/D8: interactive keeps asking the user directly; no new
        # interactive question is introduced.
        self.assertIn(
            "in interactive, the question is asked directly, exactly as "
            "today",
            self.norm.lower(),
        )
        self.assertIn(
            "this revision introduces no new interactive question",
            self.norm.lower(),
        )

    def test_no_sentence_aborts_spec_change_unconditionally_in_batch(self):
        # Negative proof (Test Notes): the fail-closed section's abort
        # sentence no longer includes spec-change.
        classify_idx = self.text.index("## Fail-closed classification")
        gate_idx = self.text.index("## Classification gate")
        section = self.text[classify_idx:gate_idx]
        self.assertNotIn("`spec-change`, `security`, or `license`", section)

    def test_abort_ignores_on_unanswered_value(self):
        self.assertIn(
            "regardless of the question's",
            self.norm,
        )
        self.assertIn("`on_unanswered` value", self.norm)

    def test_abort_ignores_gate_listing_elsewhere(self):
        self.assertIn(
            "regardless of whether the `gate_id` is later found to be "
            "listed elsewhere",
            self.norm,
        )

    def test_abort_ignores_codex_mapping(self):
        self.assertIn(
            "regardless of whether a Codex suggestion would have mapped "
            "onto one of the question's existing `option_id`s",
            self.norm,
        )

    def test_none_of_three_can_override(self):
        self.assertIn(
            "none of those three can override this step", self.norm
        )

    def test_intentional_behaviour_change_stated(self):
        self.assertIn("intentional", self.text.lower())
        self.assertIn("not a regression", self.text)
        self.assertIn("continue-on-success-path", self.text)

    # --- task0012 AC-1 (FR11): routed-arm exit from the Batch resolution
    # --- sequence, at step 2 -----------------------------------------------

    def test_step_2_states_routed_arm_also_exits_the_sequence(self):
        section = re.sub(r"\s+", " ", self._batch_sequence_section())
        self.assertIn(
            "a question the routed arm instead sends to the classification "
            "gate below also leaves the sequence here",
            section.lower(),
        )

    def test_step_2_names_all_three_things_the_routed_question_never_reaches(
        self,
    ):
        section = re.sub(r"\s+", " ", self._batch_sequence_section()).lower()
        self.assertIn("neither step 3's policy lookup", section)
        self.assertIn("nor the unlisted-gate fallback", section)
        self.assertIn("nor `on_unanswered`", section)

    def test_step_2_negative_proof_abort_only_wording_would_not_satisfy_matcher(
        self,
    ):
        # Non-vacuity guard (Test Notes): a step 2 that states only the
        # abort-exit half (the pre-task0012 wording) must not satisfy the
        # routed-arm-exit matcher above.
        fake_step_2 = (
            "Apply the Fail-closed classification above. A question it "
            "aborts never reaches step 3."
        )
        self.assertNotIn(
            "a question the routed arm instead sends to the classification "
            "gate below also leaves the sequence here",
            fake_step_2.lower(),
        )

    # --- task0025 AC-1: step 2's exit cites the Outcome step instead of ----
    # --- ending the question's story in place -------------------------------

    def test_step_2_cites_the_outcome_step_instead_of_restating(self):
        section = re.sub(r"\s+", " ", self._batch_sequence_section())
        self.assertIn(
            "the Classification gate's Outcome step above", section
        )
        self.assertIn(
            "is the resolution for that question; it is not restated here",
            section,
        )

    def test_step_2_old_ending_wording_is_gone(self):
        # Negative proof (Test Notes): the pre-task0025 wording, which ended
        # the question's story in place instead of pointing at a named
        # section, must not survive anywhere in the document.
        self.assertNotIn(
            "the gate's own proceed/stop outcome and its audit record are "
            "the resolution for that question",
            self.text,
        )

    def test_step_2_negative_proof_old_ending_would_have_satisfied_neither_matcher(
        self,
    ):
        # Non-vacuity guard: proves the two matchers above actually
        # distinguish the old wording from the new one -- the old ending
        # does not contain the new citation, and (trivially) the new
        # citation string is not the old sentence.
        fake_old_ending = (
            "it reaches neither step 3's policy lookup, nor the "
            "Unlisted-gate fallback, nor `on_unanswered` -- the gate's own "
            "proceed/stop outcome and its audit record are the resolution "
            "for that question."
        )
        self.assertNotIn(
            "the Classification gate's Outcome step above", fake_old_ending
        )

    # --- task0025 NFR1: the packet/answer-model rule is stated exactly once

    def test_batch_resolution_sequence_does_not_restate_packet_effects(self):
        # NFR1 (Test Notes: "check the whole file for a second statement of
        # the packet effects"): the Outcome step's own vocabulary -- the
        # answer-source value it introduces and the packet status it names
        # for a stopped gate -- must appear nowhere inside the Batch
        # resolution sequence section, which now only cites the Outcome
        # step instead of restating what it says.
        section = self._batch_sequence_section()
        self.assertNotIn("batch-classification-gate", section)
        self.assertNotIn("obsolete", section)

    def test_outcome_step_vocabulary_appears_in_the_classification_gate_section(
        self,
    ):
        # Non-vacuity companion to the guard above: proves the vocabulary
        # searched for there is genuinely present somewhere in the
        # document (inside the Classification gate section), so an absent
        # feature could not trivially pass the restatement guard too.
        classify_idx = self.text.index("## Classification gate")
        sequence_idx = self.text.index("## Batch resolution sequence")
        gate_section = self.text[classify_idx:sequence_idx]
        self.assertIn("batch-classification-gate", gate_section)
        self.assertIn("obsolete", gate_section)

    # --- task0012 AC-3 (NFR2): precedence reservation on the routed arm ----

    def _precedence_reservation_section(self):
        start = self.text.index("**Precedence reservation.**")
        end = self.text.index("## Classification gate")
        return self.text[start:end]

    def test_routed_arm_states_precedence_reservation(self):
        self.assertIn("**Precedence reservation.**", self.text)
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "the routed arm applies only when none of the three "
            "immediate-abort conditions above holds",
            section,
        )

    def test_precedence_reservation_names_all_three_conditions(self):
        section = re.sub(r"\s+", " ", self._precedence_reservation_section())
        self.assertIn("`category: security`", section)
        self.assertIn("`category: license`", section)
        self.assertIn("`reversible: false`", section)

    def test_precedence_reservation_states_abort_final_and_non_overridable(
        self,
    ):
        section = re.sub(
            r"\s+", " ", self._precedence_reservation_section()
        ).lower()
        self.assertIn(
            "the abort arm is evaluated first and its abort is final and "
            "non-overridable",
            section,
        )
        self.assertIn(
            "the routed arm never converts an abort into a classification",
            section,
        )

    def test_precedence_reservation_negative_proof_omitted_reservation_fails(
        self,
    ):
        # Non-vacuity guard: a routed-arm paragraph that OMITS the
        # precedence reservation (the pre-task0012 wording) must not carry
        # the marker the section-locator above depends on.
        fake_routed_arm = (
            "**The routed arm.** A question whose `category` is "
            "`spec-change` -- `gate_id: rework.spec-change` -- does not "
            "abort here. In batch, it is routed to the Classification gate "
            "below instead of aborting."
        )
        self.assertNotIn("**Precedence reservation.**", fake_routed_arm)

    # --- task0012 AC-2 (FR11, NFR2): Unlisted-gate fallback distinguishes
    # --- the aborted set from the routed set --------------------------------

    def _fallback_block_branch(self):
        marker = "## Unlisted-gate fallback"
        end_marker = "### Codex consultation procedure"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        section = self.text[start:end]
        block_idx = section.index("8. `block`")
        next_idx = section.index("9. `use_batch_policy`")
        return section[block_idx:next_idx]

    def test_block_branch_distinguishes_aborted_set_from_routed_set(self):
        section = re.sub(r"\s+", " ", self._fallback_block_branch()).lower()
        self.assertIn(
            "security, licensing and irreversible-operation questions "
            "never reach here because the fail-closed classification "
            "above has already aborted them",
            section,
        )
        self.assertIn(
            "specification-change questions never reach here either, but "
            "for a different reason",
            section,
        )
        self.assertIn(
            "the routed arm removed them from the sequence entirely at "
            "step 2",
            section,
        )

    def test_superseded_single_mechanism_sentence_is_gone(self):
        # C5: the absence half. Non-vacuity: the block-branch locator above
        # already proves the region was found and is non-empty (it would
        # have raised ValueError otherwise).
        section = self._fallback_block_branch()
        self.assertTrue(section.strip())
        self.assertNotIn(
            "The Fail-closed classification above has already aborted "
            "every specification-change, security, licensing and "
            "irreversible-operation question before this branch is "
            "reached",
            section,
        )

    def test_block_branch_negative_proof_old_sentence_would_be_caught(self):
        # Non-vacuity guard (Test Notes): the matcher above must actually
        # flag the pre-task0012 wording it supersedes.
        fake_section = (
            "8. `block` → The Fail-closed classification above has "
            "already aborted every specification-change, security, "
            "licensing and irreversible-operation question before this "
            "branch is reached, so this branch only ever sees the "
            "remainder."
        )
        self.assertIn(
            "The Fail-closed classification above has already aborted "
            "every specification-change, security, licensing and "
            "irreversible-operation question before this branch is "
            "reached",
            fake_section,
        )

    # --- classification is stated mechanically -----------------------------

    def test_classification_names_category_values(self):
        for value in ["`spec-change`", "`security`", "`license`"]:
            self.assertIn(value, self.text)

    def test_classification_names_explicit_gate_list(self):
        self.assertIn("explicit fail-closed gate list", self.norm)
        self.assertIn("rework.spec-change", self.text)

    def test_classification_names_irreversible_assumption_signal(self):
        self.assertIn("assumptions[]", self.text)
        self.assertIn("related_question_ids", self.text)
        self.assertIn("reversible: false", self.text)
        self.assertIn("irreversible operation", self.norm)

    # --- worker-set fields are cross-checked by the validator ---------------

    def test_worker_set_fields_not_trusted_alone(self):
        self.assertIn("trusted alone", self.norm)

    def test_validator_cross_check_referenced(self):
        self.assertIn("scripts/validate-worker-output.py", self.text)
        self.assertIn("cross-checks", self.norm)

    def test_validator_rule_not_restated(self):
        self.assertIn("does not restate the check itself", self.norm)

    # --- AC-7 (bs8): no feature-docs task identifier; schema cited instead -

    def test_no_feature_docs_task_identifier_cited(self):
        self.assertIsNone(
            re.search(r"task\d{4}", self.text),
            "question-resolution.md must not attribute a rule to a "
            "feature-docs task identifier that does not exist in the "
            "distributed plugin (round2.yaml bs8)",
        )

    def test_cross_check_attributed_to_the_packet_schema(self):
        self.assertIn("references/question-packet-schema.md", self.text)
        self.assertIn(
            "states the constraint this check enforces", self.norm
        )

    # --- AC-6 (bs6): consultation budget independent of question count ----

    def test_codex_procedure_section_present(self):
        self.assertIn("### Codex consultation procedure", self.text)

    def _codex_procedure_section(self):
        marker = "### Codex consultation procedure"
        self.assertIn(marker, self.text)
        return self.text.split(marker, 1)[1]

    def test_codex_procedure_availability_probe(self):
        section = self._codex_procedure_section()
        self.assertIn("Availability probe", section)
        self.assertIn("run_codex_exec.sh", section)
        self.assertIn("command -v codex", section)

    def test_codex_procedure_wrapper_invocation(self):
        section = self._codex_procedure_section()
        self.assertIn("Wrapper invocation", section)
        self.assertIn("readonly", section)
        self.assertIn('-C "{project_root}"', section)

    def test_codex_procedure_one_turn_per_call(self):
        section = self._codex_procedure_section()
        self.assertIn("One turn per call", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("prior exchange", norm_section)

    def test_history_is_capped_or_summarized_not_resent_in_full(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("compressed to its concluding", norm_section)
        self.assertIn(
            "caps the prompt size instead of letting it grow with every "
            "turn",
            norm_section,
        )
        # The old unbounded wording must be gone.
        self.assertNotIn("includes the FULL", self.text)

    def test_codex_procedure_trajectory_judgement(self):
        section = self._codex_procedure_section()
        self.assertIn("Trajectory judgement", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("turn 3", norm_section)
        self.assertIn("third turn", norm_section)

    def test_codex_procedure_five_turn_ceiling(self):
        section = self._codex_procedure_section()
        self.assertIn("Five-turn ceiling", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("five turns total", norm_section)

    def test_ceiling_bounds_per_packet_not_per_question(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("bounds the total launches per packet", norm_section)
        self.assertIn("not per question", norm_section)

    def test_packet_batching_stated_in_fallback_sequence(self):
        marker = "## Unlisted-gate fallback"
        section = self.text.split(marker, 1)[1]
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "batch every unresolved question from the same packet",
            norm_section.lower(),
        )
        self.assertIn(
            "bounds the total number of consultations to one per packet "
            "rather than one per question",
            norm_section,
        )

    def test_per_command_fallback_cache_referenced(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("per-command approval fallback", norm_section)

    def test_codex_procedure_decision_stays_with_claude(self):
        section = self._codex_procedure_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("stays with Claude", norm_section)

    def test_codex_procedure_output_untrusted(self):
        # Untrusted-output rule is stated both at the fallback mapping step
        # and again, in the procedure itself.
        self.assertGreaterEqual(self.text.count("untrusted"), 2)
        section = self._codex_procedure_section()
        self.assertIn("untrusted", section)

    def test_codex_procedure_availability_precedes_wrapper_invocation(self):
        section = self._codex_procedure_section()
        probe_idx = section.index("Availability probe")
        wrapper_idx = section.index("Wrapper invocation")
        self.assertLess(probe_idx, wrapper_idx)

    # --- Design note: decision basis recorded -----------------------------

    def test_resolution_basis_recorded(self):
        self.assertIn("resolution_note", self.text)
        self.assertIn("run report", self.text)


class TestClassificationTrustBoundaryFix(unittest.TestCase):
    """task0019 AC-1 through AC-4, AC-9 (round2 findings 87ae09bcfe6410c0,
    61c73dc71f323f45): the routed arm and the irreversibility abort must not
    depend on values the worker under scrutiny supplies.

    - AC-1: the routed arm's entry condition is the question's `gate_id`
      being `rework.spec-change`; a worker-set `category` never selects a
      route on its own.
    - AC-2: a packet whose `gate_id` is `rework.spec-change` but whose
      `category` disagrees is malformed and aborts, reaching neither the
      routed arm nor the Unlisted-gate fallback.
    - AC-3: irreversibility is decided from orchestrator-held metadata
      about the operation, independent of the packet; a packet's
      `reversible: false` assumption still aborts in addition, and
      omitting it can never remove the orchestrator-held abort.
      **Superseded by task0024 (D11, round 3): no orchestrator-held
      metadata source exists anywhere in the repository, so this claim is
      withdrawn and replaced by an accurate statement of the abort's only
      actual basis — see the AC-3 methods below, now pinning the
      replacement text instead of the withdrawn claim.**
    - AC-4: the three pre-existing abort arms and the precedence
      reservation are not weakened, merged or removed by the above.
    - AC-9 (partial): the two new stop paths each state their reason is
      recorded.
    """

    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def _fail_closed_section(self):
        start = self.text.index("## Fail-closed classification")
        end = self.text.index("## Classification gate")
        return self.text[start:end]

    def _fail_closed_norm(self):
        return re.sub(r"\s+", " ", self._fail_closed_section()).lower()

    # --- AC-1: routed arm keyed on gate_id, never on category --------------

    def test_routed_arm_condition_is_gate_id_not_category(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the routed arm's entry condition is the question's `gate_id` "
            "being `rework.spec-change`",
            section,
        )
        self.assertIn(
            "a worker-set `category` value never selects a route on its "
            "own",
            section,
        )

    def test_routed_arm_condition_negative_twin_category_keyed_wording_fails(
        self,
    ):
        # Test Notes: a synthetic sample describing the route as keyed on
        # `category` must fail the matcher above, otherwise the pin would
        # pass on any prose merely containing the word `gate_id`.
        fake_section = (
            "**The routed arm.** A question whose `category` is "
            "`spec-change` is routed to the Classification gate below, "
            "keyed on `gate_id: rework.spec-change` for bookkeeping only."
        )
        self.assertNotIn(
            "the routed arm's entry condition is the question's `gate_id` "
            "being `rework.spec-change`",
            fake_section.lower(),
        )

    # --- AC-2: malformed gate_id/category pairing aborts --------------------

    def test_malformed_pairing_aborts_reaching_neither_arm(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "a question whose `gate_id` is `rework.spec-change` and whose "
            "`category` is anything other than `spec-change` is malformed "
            "and aborts here, recording that reason",
            section,
        )
        self.assertIn(
            "it reaches neither the routed arm above nor the unlisted-gate "
            "fallback below",
            section,
        )

    def test_malformed_pairing_negative_twin_no_mismatch_rule_fails(self):
        fake_section = (
            "**The routed arm.** A question whose `gate_id` is "
            "`rework.spec-change` is routed to the Classification gate, "
            "regardless of its `category`."
        )
        self.assertNotIn("is malformed and aborts", fake_section.lower())

    # --- task0024 AC-2: malformed pairing becomes bidirectional -------------

    def test_malformed_pairing_reverse_direction_also_aborts(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the reverse mismatch is equally malformed", section
        )
        self.assertIn(
            "a question whose `category` is `spec-change` and whose "
            "`gate_id` is anything other than `rework.spec-change` also "
            "aborts, recording that reason",
            section,
        )

    def test_malformed_pairing_neither_direction_reaches_policy_lookup_or_on_unanswered(
        self,
    ):
        section = self._fail_closed_norm()
        self.assertIn(
            "neither mismatched pairing reaches the policy lookup in the "
            "batch resolution sequence below, the unlisted-gate fallback, "
            "or `on_unanswered`",
            section,
        )

    def test_malformed_pairing_reverse_direction_negative_twin_fails(self):
        # Non-vacuity guard: the pre-task0024 single-direction wording alone
        # must not satisfy the reverse-direction matcher above.
        fake_section = (
            "**Malformed pairing.** A question whose `gate_id` is "
            "`rework.spec-change` and whose `category` is anything other "
            "than `spec-change` is malformed and aborts here, recording "
            "that reason: it reaches neither the routed arm above nor the "
            "Unlisted-gate fallback below."
        )
        self.assertNotIn(
            "the reverse mismatch is equally malformed",
            fake_section.lower(),
        )

    # --- AC-3 (superseded by task0024's own AC-3, D11): the task0019-era
    # --- orchestrator-held-metadata claim named a defence with no
    # --- definition anywhere in the repository; task0024 withdraws it and
    # --- replaces it with an accurate statement of the abort's only actual
    # --- basis (the packet's own `assumptions[].reversible: false`,
    # --- worker-declared). The four methods below pin the replacement text
    # --- in place of the withdrawn claim; the abort's own force (it still
    # --- fires, still records its reason) is retained, per AC-3/AC-6.

    def test_irreversibility_basis_is_the_packets_own_declaration(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "the irreversibility abort's basis is the packet's own "
            "declaration",
            section,
        )
        self.assertIn(
            "is this abort's only current trigger", section
        )

    def test_irreversibility_basis_named_worker_declared_limitation(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "this basis is worker-declared", section
        )
        self.assertIn(
            "a stated limitation of the current design, not a second, "
            "independent defence",
            section,
        )

    def test_no_orchestrator_held_source_claimed(self):
        section = self._fail_closed_norm()
        self.assertIn(
            "no orchestrator-held source constrains it today", section
        )

    def test_irreversibility_abort_still_records_its_reason(self):
        # Retention (AC-3: "the abort's own force is unchanged"): the abort
        # still fires and still records its reason, exactly as before the
        # claim was withdrawn.
        section = self._fail_closed_norm()
        self.assertIn(
            "this abort records its reason exactly as every abort in this "
            "section does",
            section,
        )

    def test_orchestrator_held_irreversible_operations_list_claim_is_gone(
        self,
    ):
        # AC-3 negative proof: no sentence claims an orchestrator-held
        # metadata source or irreversible-operations list -- the withdrawn
        # task0019-era claim must not survive anywhere in the document.
        self.assertNotIn(
            "decided from metadata the orchestrator holds about that "
            "operation",
            self.norm.lower(),
        )
        self.assertNotIn("irreversible-operations list", self.text.lower())
        self.assertNotIn(
            "independently of whatever the packet's `assumptions[]` does "
            "or does not declare",
            self.norm,
        )

    def test_irreversibility_negative_twin_bare_bullet_wording_fails(self):
        # Non-vacuity guard (Test Notes): the bare bullet alone (no
        # replacement paragraph) must not satisfy the replacement-statement
        # matchers above -- proves the matcher is not vacuous against an
        # empty/renamed section.
        fake_section = (
            "- an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation."
        )
        self.assertNotIn(
            "the irreversibility abort's basis is the packet's own "
            "declaration",
            fake_section.lower(),
        )

    # --- AC-4: retention, consolidated (individual pins already exist above)

    def test_ac4_all_three_abort_arms_and_precedence_reservation_survive(
        self,
    ):
        section = re.sub(r"\s+", " ", self._fail_closed_section())
        self.assertIn(
            "the question's `category` "
            "(`references/question-packet-schema.md`) is `security` or "
            "`license`",
            section,
        )
        self.assertIn(
            "an `assumptions[]` entry whose `related_question_ids` names "
            "this question carries `reversible: false` — an irreversible "
            "operation.",
            section,
        )
        self.assertIn("**Precedence reservation.**", self._fail_closed_section())


class TestQuestionPacketSchemaCategoryBlockingConstraint(unittest.TestCase):
    """AC-7 (round2.yaml bs8): the packet-shape SSOT (question-packet-
    schema.md) states the category-to-blocking constraint itself and names
    the enforcing script, instead of leaving the rule undocumented at its
    own source of truth and attributed elsewhere to a feature-docs task
    identifier that does not exist in the distributed plugin."""

    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def test_constraint_states_the_three_categories_require_block(self):
        self.assertIn(
            "A question whose `category` is `spec-change`, `security`, or "
            "`license` must carry `on_unanswered: block`",
            self.norm,
        )

    def test_enforcing_script_named(self):
        self.assertIn("scripts/validate-worker-output.py", self.text)
        self.assertIn("enforces this constraint", self.norm)

    def test_no_feature_docs_task_identifier_cited(self):
        self.assertIsNone(
            re.search(r"task\d{4}", self.text),
            "question-packet-schema.md must not attribute ownership to a "
            "feature-docs task identifier that does not exist in the "
            "distributed plugin (round2.yaml bs8)",
        )


if __name__ == "__main__":
    unittest.main()
