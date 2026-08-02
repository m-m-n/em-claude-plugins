"""Structural assertions for em-workflow/references/question-resolution.md.

Pre-existing coverage (kept passing per this task's Test Notes, not tied to
task0018's own acceptance criteria):
- deduplication rules in order, the priority sort, `depends_on` deferral,
  and the presentation limits.
- the batch resolution sequence, including that a missing option ID is a
  protocol error and label matching may not substitute for it.

task0018 acceptance criteria (fail-closed ordering + Codex procedure,
review round1 findings as8 / as4):
- AC-1: the fail-closed classification appears before the Codex
  consultation and before the record-as-TBD branch, in document order.
- AC-2: the abort applies to all four categories regardless of the
  unanswered behaviour value, the gate's listing, or whether a Codex
  suggestion maps to an existing option.
- AC-3: the classification is stated mechanically — category values, the
  explicit gate identifier list, and the irreversible-assumption signal.
- AC-4: the document states that the worker-set category and unanswered
  behaviour are cross-checked by the validator, referencing it rather than
  restating the rule.
- AC-5: the Codex consultation procedure is present as substance —
  availability probe, wrapper invocation, one turn per call, trajectory
  judgement, turn ceiling, who decides, untrusted-output rule.
- AC-6: the ordering is asserted via document position comparisons, not
  merely presence.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
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

    # --- AC-1 / AC-6: fail-closed classification precedes Codex          --
    # --- consultation and the record-as-TBD branch, by document position --

    def _fallback_section(self):
        marker = "## Unlisted-gate fallback"
        self.assertIn(marker, self.text)
        return self.text.split(marker, 1)[1]

    def test_classification_precedes_codex_consultation_by_position(self):
        section = self._fallback_section()
        classify_idx = section.index("Classify before doing anything else")
        codex_idx = section.index("Pass the question's `prompt`")
        self.assertLess(
            classify_idx,
            codex_idx,
            "fail-closed classification must appear before the Codex "
            "consultation step in document order",
        )

    def test_classification_precedes_record_tbd_by_position(self):
        section = self._fallback_section()
        classify_idx = section.index("Classify before doing anything else")
        record_tbd_idx = section.index("record_tbd` → generate a TBD answer")
        self.assertLess(
            classify_idx,
            record_tbd_idx,
            "fail-closed classification must appear before the "
            "record-as-TBD branch in document order",
        )

    def test_codex_consultation_precedes_record_tbd_by_position(self):
        # Sanity check on the surrounding structure: the fallback sequence
        # itself is unchanged in relative order (Codex before record_tbd).
        section = self._fallback_section()
        codex_idx = section.index("Pass the question's `prompt`")
        record_tbd_idx = section.index("record_tbd` → generate a TBD answer")
        self.assertLess(codex_idx, record_tbd_idx)

    # --- AC-2: abort applies regardless of the three overriding signals ---

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
            "regardless of whether a Codex suggestion in step 3 would "
            "have mapped onto one of the question's existing "
            "`option_id`s",
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

    # --- AC-3: the classification is stated mechanically ------------------

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

    # --- AC-4: worker-set fields are cross-checked by the validator, ------
    # --- referenced rather than restated -----------------------------------

    def test_worker_set_fields_not_trusted_alone(self):
        self.assertIn("trusted alone", self.norm)

    def test_validator_cross_check_referenced(self):
        self.assertIn("scripts/validate-worker-output.py", self.text)
        self.assertIn("cross-checks", self.norm)
        self.assertIn("task0016", self.text)

    def test_validator_rule_not_restated(self):
        self.assertIn("does not restate the check itself", self.norm)

    # --- AC-5: the Codex consultation procedure is present as substance ---

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


if __name__ == "__main__":
    unittest.main()
