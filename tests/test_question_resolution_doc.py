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
        # The four fail-closed categories must all be named together.
        self.assertTrue(
            re.search(
                r"Specification\s+change,\s+security,\s+licensing,\s+and\s+irreversible\s+operations\s+abort",
                self.text,
            ),
            "fail-closed rule must name specification change, security, "
            "licensing and irreversible operations together",
        )

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
