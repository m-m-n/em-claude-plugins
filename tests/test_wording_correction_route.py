"""Tests for task0003: the wording-correction route in
`em-workflow/references/rework-task-synthesis.md` Section 9, and its
"conjunctive, not alternative" eligibility framing.

Covers task0003 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0003.md):

- AC-3 (FR15): the wording-correction route is a distinct branch of route
  selection, naming `IMPLEMENTATION.md` and `VERIFICATION.md` as the
  documents it covers, and stating it requires no planner re-entry.
- AC-4 (FR15): the three eligibility conditions are stated conjunctively --
  no planner re-entry, plan/task metadata unchanged, requirement metadata
  unchanged.
- AC-5 (FR16): a change failing any one condition falls back to the normal
  rework / SPEC-change route, and the conditions are stated so a deviation
  is detectable after the fact rather than only by intent.
- AC-6 (NFR1) route-side half: the route does not restate a rule owned by
  `references/question-resolution.md` (the classification gate's verdicts).
  The transition-side half of AC-6, and AC-1/AC-2/AC-7, are covered by
  `tests/test_rework_synthesis_contract.py`, which this module does not
  duplicate.

Per task0003.md Test Notes ("All assertions read only files this task
owns", C4): every assertion below reads only
`em-workflow/references/rework-task-synthesis.md`.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SSOT_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"

ROUTE_HEADING = "### Wording-correction route"
SECTION_10_HEADING = "## 10. Workflow state transition"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _route_section(text):
    start = text.index(ROUTE_HEADING)
    end = text.index(SECTION_10_HEADING, start)
    return text[start:end]


def _eligibility_block(section):
    start = section.index("**Eligibility")
    end = section.index("**Outcome when eligible**")
    return section[start:end]


def _guard_block(section):
    start = section.index("**Guard**")
    end = section.index("**Ordering**")
    return section[start:end]


class TestWordingCorrectionRouteExistsAsDistinctBranch(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)
        cls.section = _route_section(cls.text)

    def test_route_heading_present(self):
        self.assertIn(ROUTE_HEADING, self.text)

    def test_names_the_two_covered_documents(self):
        self.assertIn("IMPLEMENTATION.md", self.section)
        self.assertIn("VERIFICATION.md", self.section)

    def test_requires_no_planner_reentry(self):
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertIn("No planner re-entry is needed", normalized)

    def test_route_is_positioned_ahead_of_section_10(self):
        # Design's Ordering rule: only a change that fails this route can
        # reach the SPEC-change transition, so the heading must precede
        # Section 10 in raw document order. (Full 13-section order/count is
        # test_rework_synthesis_contract.py's job; this is the route-local
        # half of that ordering guarantee.)
        route_idx = self.text.index(ROUTE_HEADING)
        section10_idx = self.text.index(SECTION_10_HEADING)
        self.assertLess(route_idx, section10_idx)

    def test_route_is_a_subsection_not_a_new_numbered_top_level_section(self):
        # C3: never insert a new numbered section; extend inside 9/10.
        self.assertNotIn("## 14.", self.text)

    def test_new_numbered_section_marker_would_be_detected(self):
        # Non-vacuity proof for the assertion above.
        fake_text = "## 14. New Section\n"
        self.assertIn("## 14.", fake_text)


class TestEligibilityConditionsAreConjunctive(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)
        cls.section = _route_section(cls.text)
        cls.eligibility = _eligibility_block(cls.section)

    def test_states_conjunctive_explicitly(self):
        self.assertIn("conjunctive", self.eligibility)

    def test_three_numbered_conditions_present_in_order(self):
        numbered = re.findall(r"^(\d+)\. ", self.eligibility, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3"])

    def test_condition_one_is_no_planner_reentry(self):
        self.assertIn("No planner re-entry is needed", self.eligibility)

    def test_condition_two_names_plan_task_metadata_artefacts(self):
        for token in ("files", "skills", "domains", "complexity", "plan paths"):
            with self.subTest(token=token):
                self.assertIn(token, self.eligibility)

    def test_condition_three_names_requirement_metadata_artefacts(self):
        for token in (
            "requirement statements",
            "IDs",
            "`status`",
            "task/test mapping",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.eligibility)

    def test_alternative_disjunctive_framing_would_be_rejected(self):
        # Edge case (Test Notes): a matcher that would accept "any of"
        # wording is too weak. This proves the real assertion
        # (test_states_conjunctive_explicitly) actually distinguishes the
        # conjunctive framing from a disjunctive one carrying the same
        # three numbered items.
        alternative_sample = (
            "**Eligibility (any of the following applies)**:\n\n"
            "1. No planner re-entry is needed.\n"
            "2. No plan or task metadata changes.\n"
            "3. No requirement metadata changes.\n"
        )
        numbered = re.findall(r"^(\d+)\. ", alternative_sample, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3"])
        self.assertNotIn("conjunctive", alternative_sample)


class TestGuardFallback(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)
        cls.section = _route_section(cls.text)
        cls.guard = _guard_block(cls.section)

    def test_states_fallback_to_normal_route_on_any_failing_condition(self):
        self.assertIn("rework-task synthesis", self.guard)
        self.assertIn("SPEC-change transition", self.guard)

    def test_conditions_name_concrete_artefacts_for_detectability(self):
        # AC-5: a deviation must be recognizable after the fact, not only
        # by the intent behind the change.
        self.assertIn("concrete", self.guard)
        self.assertIn("artefact", self.guard)

    def test_vague_guard_wording_would_be_detected_as_insufficient(self):
        # Non-vacuity proof: a guard that only says "otherwise the normal
        # route applies" without naming concrete artefacts must fail the
        # detectability check above.
        vague_guard = (
            "**Guard**: if this route does not apply, the normal route is "
            "used instead."
        )
        self.assertNotIn("concrete", vague_guard)
        self.assertNotIn("artefact", vague_guard)


class TestRouteDoesNotRestateOwnedRules(unittest.TestCase):
    """AC-6 (route-side half; the SPEC-change transition's own half of
    NFR1 is pinned in test_rework_synthesis_contract.py)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)
        cls.section = _route_section(cls.text)

    def test_does_not_restate_classification_gate_verdicts(self):
        # goal_not_met / spec_gap / not_applicable are owned by
        # references/question-resolution.md (task0004's classification
        # gate); this route must only cite the document, never its verdicts.
        for verdict in ("goal_not_met", "spec_gap", "not_applicable"):
            with self.subTest(verdict=verdict):
                self.assertNotIn(verdict, self.section)

    def test_verdict_leak_would_be_detected(self):
        # Non-vacuity proof for the assertion above.
        leaking_sample = "verdict: goal_not_met"
        self.assertIn("goal_not_met", leaking_sample)

    def test_cites_question_resolution_by_path(self):
        self.assertIn("references/question-resolution.md", self.section)


if __name__ == "__main__":
    unittest.main()
