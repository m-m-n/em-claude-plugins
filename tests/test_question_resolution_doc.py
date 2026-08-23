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
