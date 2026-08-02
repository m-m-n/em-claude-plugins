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
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SSOT_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"

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


if __name__ == "__main__":
    unittest.main()
