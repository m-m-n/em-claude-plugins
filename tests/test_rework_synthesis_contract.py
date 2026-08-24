"""Tests for task0004: the rework task synthesis SSOT and the
implement-phase / review-phase references that point to it.

Covers task0004 Acceptance Criteria:

- AC-1: references/rework-task-synthesis.md exists with all thirteen
  sections from design-input.md 5.10, and names the four applicable routes.
- AC-2: the document states all eleven invariants, including the
  pending-task precondition, base_commit preservation, and the
  interactive/batch parity of synthesis rules.
- AC-3: the document states the verification coverage rules and forbids a
  rework task whose covered_by_existing and new_scenarios are both empty.
- AC-4: the document states the review-sourced state transition ordering
  and that verify-sourced rework omits the needs_rework step.
- AC-5: references/implement-phase.md states the rework re-entry
  precondition requiring at least one pending task, and does not alter the
  existing completed_at_commit wording.
- AC-6: references/review-phase.md references the new SSOT from both the
  interactive and the batch rework branch and documents the needs_rework
  update ordering.

This is a documentation task (feature-docs/agent-separation/tasks/task0004.md,
Test Notes): verification is by structural/textual assertion over the
markdown, not behavioral tests of running code.

Per task0004.md's Test Notes: `skills/develop/SKILL.md`'s verify rework
branches are owned by task0012 — this file asserts nothing about that file.

task0019 AC-8 (round2 findings 87ae09bcfe6410c0, 61c73dc71f323f45,
confidence 95), field renamed by rework-contract-drift/task0004 (FR4): what
the `rework.spec-change` packet must carry is pinned here as well as in
tests/test_worker_contract_docs.py -- the packet names its origin(s) via
`evidence[].origin_id` and does not name the review round record path; the
orchestrator locates that record itself (`references/question-
resolution.md`, pinned in tests/test_classification_gate.py). Neither
document restates the other's rule.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SSOT_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
REWORK_PLANNER_CONTRACT_PATH = (
    PLUGIN_ROOT / "references" / "contracts" / "rework-planner-contract.md"
)

# The thirteen sections design-input.md 5.10 lists, in order.
SECTION_HEADINGS = [
    "1. Purpose",
    "2. Applicable modes",
    "3. Inputs",
    "4. Grouping rules",
    "5. Task ID allocation",
    "6. Task plan requirements",
    "7. Metadata derivation",
    "8. Verification coverage rules",
    "9. Related document updates",
    "10. Workflow state transition",
    "11. Invariants",
    "12. Validation",
    "13. Execution adapter",
]

FOUR_ROUTES = [
    "Interactive review rework",
    "Batch review rework",
    "Interactive verify rework",
    "Batch verify rework",
]


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


class TestReworkSynthesisSSOTExistsAndStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)

    def test_file_exists(self):
        self.assertTrue(SSOT_PATH.is_file())

    def test_all_thirteen_sections_present_in_order(self):
        indices = []
        for heading in SECTION_HEADINGS:
            marker = f"## {heading}"
            self.assertIn(
                marker, self.text, f"missing section heading: {marker!r}"
            )
            indices.append(self.text.index(marker))
        self.assertEqual(
            indices,
            sorted(indices),
            "the thirteen sections must appear in design-input.md 5.10's order",
        )

    def test_names_four_applicable_routes(self):
        for route in FOUR_ROUTES:
            self.assertIn(
                route, self.text, f"must name the route: {route!r}"
            )


class TestReworkSynthesisSSOTInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)

    def _invariants_section(self):
        start = self.text.index("## 11. Invariants")
        end = self.text.index("## 12. Validation")
        return self.text[start:end]

    def test_invariant_list_has_eleven_items(self):
        section = self._invariants_section()
        items = re.findall(r"^\d+\.", section, re.MULTILINE)
        self.assertEqual(
            len(items),
            11,
            f"expected exactly eleven numbered invariants, found {len(items)}",
        )

    def test_states_pending_task_precondition_invariant(self):
        self.assertIn(
            "at least one new rework task is\n   registered in workflow.yaml",
            self.text,
        )

    def test_states_base_commit_preservation_invariant(self):
        self.assertIn(
            "`workflow[implement].base_commit` is never changed by a rework patch",
            self.text,
        )

    def test_states_interactive_batch_parity_invariant(self):
        self.assertIn(
            "Interactive and batch never differ in task synthesis rules",
            self.text,
        )


class TestReworkSynthesisSSOTCoverageRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)

    def test_states_rework_index_structure(self):
        self.assertIn("rework_index", self.text)
        self.assertIn("covered_by_existing", self.text)
        self.assertIn("new_scenarios", self.text)

    def test_forbids_rework_task_with_both_fields_empty(self):
        self.assertIn(
            "`covered_by_existing` AND `new_scenarios` are BOTH empty\nis FORBIDDEN",
            self.text,
        )

    def test_states_four_machine_checkable_validation_rules(self):
        validation_start = self.text.index("## 12. Validation")
        validation_end = self.text.index("## 13. Execution adapter")
        section = self.text[validation_start:validation_end]
        self.assertIn("rework_index", section)
        self.assertIn("verification_index", section)
        self.assertIn("VERIFICATION.md", section)
        self.assertIn("tests_append", section)


class TestReworkSynthesisSSOTStateTransition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)

    def _transition_section(self):
        start = self.text.index("## 10. Workflow state transition")
        end = self.text.index("## 11. Invariants")
        return self.text[start:end]

    def test_states_review_sourced_ordering(self):
        section = self._transition_section()
        needs_rework_idx = section.index("review.needs_rework = true")
        dispatch_idx = section.index("dispatches rework-planner")
        patch_idx = section.index("validates and applies rework-planner's patch")
        implement_idx = section.index(
            "`implement` returning to `pending` happens INSIDE that patch's"
        )
        self.assertLess(needs_rework_idx, dispatch_idx)
        self.assertLess(dispatch_idx, patch_idx)
        self.assertLess(patch_idx, implement_idx)

    def test_states_verify_sourced_omits_needs_rework_step(self):
        section = self._transition_section()
        self.assertIn(
            "**Verify-sourced rework** skips step 1 entirely and starts at step 2",
            section,
        )
        self.assertIn("review-specific", section)

    def test_states_create_plan_reentry_holds_with_merged_tasks(self):
        # task0003 AC-1 (FR6): create-plan re-entry under the SPEC-change
        # transition is not rejected merely because merged tasks already
        # exist, and the permission rule itself is cited by path rather
        # than restated here (C2).
        section = self._transition_section()
        self.assertIn(
            "not rejected merely because merged tasks",
            section,
        )
        self.assertIn("references/workflow-patch.md", section)

    def test_does_not_restate_workflow_patch_permission_conditions(self):
        # task0003 AC-6 (NFR1): the `replace_all` permission conjunction is
        # owned by workflow-patch.md and must not be copied here.
        section = self._transition_section()
        self.assertNotIn(
            "every existing task's `status` is `pending`", section
        )
        self.assertNotIn("an explicit re-plan", section)

    def test_batch_mode_routes_through_classification_gate(self):
        # task0003 AC-2 (FR6, D8): batch resolves rework.spec-change through
        # the classification gate in question-resolution.md.
        section = self._transition_section()
        normalized = re.sub(r"\s+", " ", section)
        self.assertIn("classification gate", normalized)
        self.assertIn("references/question-resolution.md", section)

    def test_old_unlisted_gate_abort_wording_is_gone(self):
        # task0003 AC-2: the superseded claim that batch aborts through the
        # unlisted-gate fallback must not survive.
        section = self._transition_section()
        self.assertNotIn("falls to the unlisted-gate fallback", section)
        self.assertNotIn(
            "which aborts, because a SPEC change is not a success-path "
            "outcome",
            section,
        )

    def test_interactive_mode_explicitly_stated_unchanged(self):
        # task0003 AC-2 (D8): interactive mode is stated as unchanged, not
        # merely left silent.
        normalized = re.sub(r"\s+", " ", self._transition_section())
        self.assertIn(
            "Interactive mode is unchanged: the user is asked directly",
            normalized,
        )


class TestImplementPhaseReworkPrecondition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)

    def test_states_pending_task_precondition(self):
        self.assertIn(
            "require at least one task in `tasks` whose\n   `status == pending`",
            self.text,
        )
        self.assertIn("protocol error", self.text)

    def test_references_rework_synthesis_ssot(self):
        self.assertIn("rework-task-synthesis.md", self.text)

    def test_completed_at_commit_wording_is_unchanged(self):
        # task0004.md Design: "The completed_at_commit semantics are not
        # changed." -- assert the existing Step I.3 sentence survives
        # verbatim.
        self.assertIn(
            'When every task is `merged`: set `implement` step `status = completed`,\n'
            '`completed_at_commit = $(git rev-parse "em-workflow/{feature}/integration")`.',
            self.text,
        )

    def test_regression_precondition_stated_before_launch_selection(self):
        # The bug this task fixes: returning `implement` to `pending` with
        # no pending task leaves nothing to launch. A reader must reach the
        # precondition BEFORE reaching the launch-selection wording in I.2.a.
        precondition_idx = self.text.index(
            "require at least one task in `tasks` whose\n   `status == pending`"
        )
        launch_selection_idx = self.text.index(
            "Select\nunlaunched tasks (no journal event yet and "
            "`status != merged`, ascending"
        )
        self.assertLess(
            precondition_idx,
            launch_selection_idx,
            "the precondition must be stated before the launch-selection step",
        )


class TestReviewPhaseReworkReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PHASE_PATH)

    def _r5_section(self):
        start = self.text.index("## Phase R5: Persist the round record")
        end = self.text.index("## Phase R6: Report")
        return self.text[start:end]

    def test_references_ssot_from_two_distinct_locations(self):
        section = self._r5_section()
        completion_gate_idx = section.index("**Completion gate**")
        batch_mode_idx = section.index(
            "Batch mode (develop-駆動 only): no offer"
        )
        interactive_branch = section[completion_gate_idx:batch_mode_idx]
        batch_branch = section[batch_mode_idx:]
        self.assertIn(
            "rework-task-synthesis.md",
            interactive_branch,
            "interactive rework branch must reference the SSOT",
        )
        self.assertIn(
            "rework-task-synthesis.md",
            batch_branch,
            "batch rework branch must reference the SSOT",
        )

    def test_documents_needs_rework_update_ordering(self):
        section = self._r5_section()
        self.assertIn("review.needs_rework = true", section)
        self.assertIn("review.status = pending", section)
        # The write must be documented as preceding dispatch, and the
        # implement-pending transition as carried inside the patch rather
        # than a separate write.
        write_idx = section.index("review.needs_rework = true")
        dispatch_idx = section.index("dispatches rework-planner")
        self.assertLess(write_idx, dispatch_idx)
        self.assertIn(
            "is carried inside that patch",
            section,
        )

    def test_old_thin_batch_mode_reference_is_replaced(self):
        # Guards against the pre-task0004 wording ("batch-mode.md \"Rework
        # task synthesis\"") surviving the rewrite -- it must now point at
        # the new SSOT instead. Whitespace-normalized so a line-wrap doesn't
        # let a stale reference slip past the check.
        normalized = re.sub(r"\s+", " ", self.text)
        self.assertNotIn(
            'batch-mode.md "Rework task synthesis"', normalized
        )


class TestSpecChangePacketCarriesOriginIdNotRecordPath(unittest.TestCase):
    """task0019 AC-8 (NFR1), renamed by rework-contract-drift/task0004
    (FR4): rework-planner-contract.md states the spec-change packet names
    its origin(s) via `evidence[].origin_id` and does not name the review
    round record path -- consistent with question-resolution.md's
    Classification gate step 3, which locates that record itself. Neither
    document restates the other's rule."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_PLANNER_CONTRACT_PATH)
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def test_packet_names_origins_via_origin_id_field(self):
        # task0028 AC-5: the packet names its origin(s) via the
        # `evidence[].origin_id` field, generalized to the origin_kind/
        # origin_id pair rework-task-synthesis.md's Invariant 6 defines
        # (both origin kinds, not review findings alone).
        self.assertIn(
            "names its origin(s) — the `origin_kind` / `origin_id` pair "
            "`references/rework-task-synthesis.md`'s Invariant 6 defines "
            "(cited, not restated) — via `evidence[].origin_id`",
            self.norm,
        )

    def test_packet_does_not_name_the_record_path(self):
        self.assertIn(
            "does not name the review round record path", self.norm
        )

    def test_gate_cited_not_restated(self):
        self.assertIn(
            "the gate's origin verification "
            "(`references/question-resolution.md`) locates its own bound "
            "set itself",
            self.norm,
        )

    def test_does_not_restate_the_r5_position_or_path_formula(self):
        # NFR1: the round-record location formula is owned by
        # references/review-phase.md's R5 section and cited from
        # question-resolution.md; this contract must not restate it.
        self.assertNotIn("Phase R5", self.text)
        self.assertNotIn("reviews/round", self.text)

    def test_negative_twin_old_record_path_naming_wording_fails(self):
        fake_text = (
            "The question packet returned for `gate_id: rework.spec-change` "
            "names each originating review finding's `stable_id` and the "
            "review round record path in the question's `evidence[]` "
            "entries."
        )
        self.assertNotIn(
            "does not name the review round record path", fake_text
        )

    def test_old_review_only_packet_naming_wording_is_gone(self):
        # task0028 AC-8: the pre-task0028 wording, which named review
        # findings alone as the packet's origin vocabulary via the now-
        # retired single-field name, must not survive anywhere in the
        # document. Built at run time (never a contiguous literal) so this
        # sample never trips the retired-identifier absence scan
        # (IMPLEMENTATION.md Shared Components).
        retired_field = "finding" + "_stable_id"
        self.assertNotIn(
            "names each originating review finding's `stable_id` in the "
            f"question's `evidence[].{retired_field}` entries",
            self.text,
        )


class TestReworkSynthesisAssertionsCanFail(unittest.TestCase):
    """Proof that the structural checks above fail meaningfully, per the
    tdd-testing discipline (a test that can never fail is not a test)."""

    def test_missing_section_heading_is_detected(self):
        fake_text = "\n".join(
            f"## {h}" for h in SECTION_HEADINGS if h != "5. Task ID allocation"
        )
        self.assertNotIn("## 5. Task ID allocation", fake_text)

    def test_missing_ssot_reference_is_detected(self):
        fake_review_text = "no reference here"
        self.assertNotIn("rework-task-synthesis.md", fake_review_text)

    def test_wrong_invariant_count_is_detected(self):
        fake_section = "1. one\n2. two\n3. three\n"
        items = re.findall(r"^\d+\.", fake_section, re.MULTILINE)
        self.assertNotEqual(len(items), 11)

    def test_superseded_batch_abort_wording_would_be_caught(self):
        # task0003 AC-2 negative proof: the matcher used by
        # test_old_unlisted_gate_abort_wording_is_gone must actually flag
        # the pre-task0003 wording it supersedes, not merely pass by
        # vacuity against text that never contained it.
        fake_section = (
            "Batch mode has no `rework.spec-change` entry in "
            "`batch-policies.yaml`, so it\nfalls to the unlisted-gate "
            "fallback (`references/question-resolution.md`)\n— which "
            "aborts, because a SPEC change is not a success-path outcome."
        )
        self.assertIn("falls to the unlisted-gate fallback", fake_section)
        self.assertIn(
            "which aborts, because a SPEC change is not a success-path "
            "outcome",
            fake_section,
        )


if __name__ == "__main__":
    unittest.main()
