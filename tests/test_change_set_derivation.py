"""Tests for task0009 (goal-vs-spec-divergence): pins the declared change
set derivation section this task adds to
`em-workflow/references/phases/create-plan-phase.md`.

Covers task0009 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0009.md):

- AC-1 (FR18): the create-plan phase document defines the declared change
  set as the union of every task's `files` entries plus the default
  entries, citing the two templates for the default entries instead of
  enumerating them.
- AC-2 (FR18): the same document states explicitly that the declaration is
  a guard, not a statement of the goal.
- AC-3 (FR18): the same document states the superset/containment semantics
  by citation (never restatement) and states when the derivation is
  re-derived.
- AC-6 (NFR1, C6c/C6d): the new section never enumerates the two
  workflow-artifact root globs together, and introduces no verify-side
  exclusion rule.

Scoped only to the derivation section this task adds (C4) -- this module
never asserts over the SPEC or REQUIREMENTS templates (pinned in their own
sibling modules) or over any file another task owns. AC-7's "repository-wide
carrier and exclusion-rule guards still pass" is exercised by
`test_declared_change_set_invariants.py` (unedited by this task) plus the
full-suite run recorded in this task's test record, not re-tested here.

Content assertions read a whitespace-normalized slice of the new section
(`_normalize_ws`), so line-wrap choices never make an assertion brittle;
position/uniqueness assertions read raw offsets.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CREATE_PLAN_PHASE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "phases" / "create-plan-phase.md"
)

# Contract AN: the new section's anchor, and the section immediately before
# it. Slicing runs from the anchor to end-of-file -- well-defined without a
# following anchor since this is the last section of the document.
DERIVATION_SECTION_HEADING = "## 12. Declared change set derivation"
PRECEDING_HEADING = "## 11. Completion or failure"

# AC-1 literals.
DERIVED_NOT_AUTHORED_PHRASE = "derived — not authored"
TASKS_FILES_LITERAL = "`tasks.*.files`"
DEFAULT_ENTRIES_PHRASE = "default entries"
SPEC_TEMPLATE_CITATION = "references/templates/spec-document.md"
REQUIREMENTS_TEMPLATE_CITATION = "references/templates/requirements-document.md"

# AC-2 literal.
GUARD_NOT_GOAL_PHRASE = "a guard, not a statement of the goal"

# AC-3 literals.
CONTAINMENT_CITATION_PHRASE = (
    "the templates cited above state the superset/containment semantics"
)
RE_DERIVED_PHRASE = "re-derived whenever the task set changes"

# Contract MK's two root literals -- must never co-occur in this document
# (C6c); the two templates are the sole permitted carriers (D6), not this
# document.
FEATURE_DOCS_ROOT_LITERAL = "feature-docs/{feature}/**"
TEST_DOCS_ROOT_LITERAL = "test-docs/{feature}/**"

# C6d: no verify-side exclusion rule -- checked by absence of exclusion
# vocabulary in the new section at all, which trivially satisfies "no rule
# says artifacts are excluded/ignored/subtracted at verification time".
EXCLUSION_WORDS = ("exclud", "subtract", "ignor", "除外")


def _read():
    return CREATE_PLAN_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _derivation_section(text):
    start = text.index(DERIVATION_SECTION_HEADING)
    return text[start:]


class TestSectionExists(unittest.TestCase):
    """AC-1: the section exists, is unique, and follows the document's
    existing last section (C3: no existing section is renumbered)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_present(self):
        self.assertIn(DERIVATION_SECTION_HEADING, self.text)

    def test_heading_occurs_exactly_once(self):
        self.assertEqual(self.text.count(DERIVATION_SECTION_HEADING), 1)

    def test_heading_follows_completion_section(self):
        preceding_idx = self.text.index(PRECEDING_HEADING)
        derivation_idx = self.text.index(DERIVATION_SECTION_HEADING)
        self.assertLess(preceding_idx, derivation_idx)


class TestInputsStated(unittest.TestCase):
    """AC-1: the union of tasks' `files` plus the default entries, citing
    the templates instead of enumerating them."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_derived_not_authored_stated(self):
        self.assertIn(DERIVED_NOT_AUTHORED_PHRASE, self.section)

    def test_tasks_files_literal_cited(self):
        self.assertIn(TASKS_FILES_LITERAL, self.section)

    def test_default_entries_phrase_present(self):
        self.assertIn(DEFAULT_ENTRIES_PHRASE, self.section)

    def test_cites_both_templates_for_default_entries(self):
        self.assertIn(SPEC_TEMPLATE_CITATION, self.section)
        self.assertIn(REQUIREMENTS_TEMPLATE_CITATION, self.section)

    def test_does_not_enumerate_the_default_entries_itself(self):
        # C6c: this document cites the templates for the default entries;
        # it must never enumerate the two workflow-artifact root globs
        # together itself.
        self.assertFalse(
            FEATURE_DOCS_ROOT_LITERAL in self.section
            and TEST_DOCS_ROOT_LITERAL in self.section
        )


class TestGuardStatusStated(unittest.TestCase):
    """AC-2: the document states explicitly that the declaration is a
    guard, not a statement of the goal."""

    def test_guard_not_goal_phrase_present(self):
        section = _normalize_ws(_derivation_section(_read()))
        self.assertIn(GUARD_NOT_GOAL_PHRASE, section)


class TestSemanticsAndTimingStated(unittest.TestCase):
    """AC-3: the superset/containment semantics are stated by citation
    (not restatement), and the re-derivation timing is stated."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_semantics_cited_not_restated(self):
        self.assertIn(CONTAINMENT_CITATION_PHRASE, self.section)
        # Restraint: the literal words "SUPERSET" / "CONTAINED IN" belong
        # to the templates (D6) and must not be copied into this document.
        self.assertNotIn("SUPERSET", self.section)
        self.assertNotIn("CONTAINED IN", self.section)

    def test_re_derivation_timing_stated(self):
        self.assertIn(RE_DERIVED_PHRASE, self.section)


class TestNoForbiddenLiteralsInSection(unittest.TestCase):
    """AC-6 (NFR1, C6c/C6d): the new section never enumerates the two
    workflow-artifact root globs together, and introduces no verify-side
    exclusion rule."""

    @classmethod
    def setUpClass(cls):
        cls.section = _derivation_section(_read())

    def test_root_globs_never_co_occur(self):
        self.assertFalse(
            FEATURE_DOCS_ROOT_LITERAL in self.section
            and TEST_DOCS_ROOT_LITERAL in self.section
        )

    def test_no_exclusion_wording_at_all(self):
        lowered = self.section.lower()
        for word in EXCLUSION_WORDS:
            self.assertNotIn(word, lowered)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Negative proof: every matcher above fails meaningfully against a
    synthetic sample that omits the property it checks, or flags a
    synthetic sample that violates it."""

    def test_inputs_matchers_flag_absence_in_synthetic_sample(self):
        sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "This section is a placeholder with none of the required "
            "content yet."
        )
        self.assertNotIn(DERIVED_NOT_AUTHORED_PHRASE, sample)
        self.assertNotIn(TASKS_FILES_LITERAL, sample)
        self.assertNotIn(SPEC_TEMPLATE_CITATION, sample)
        self.assertNotIn(REQUIREMENTS_TEMPLATE_CITATION, sample)

    def test_guard_matcher_flags_absence_in_synthetic_sample(self):
        sample = "## 12. Declared change set derivation\n\nJust a description."
        self.assertNotIn(GUARD_NOT_GOAL_PHRASE, sample)

    def test_semantics_and_timing_matchers_flag_absence_in_synthetic_sample(
        self,
    ):
        sample = "## 12. Declared change set derivation\n\nNo semantics here."
        self.assertNotIn(CONTAINMENT_CITATION_PHRASE, sample)
        self.assertNotIn(RE_DERIVED_PHRASE, sample)

    def test_forbidden_literal_matchers_flag_a_synthetic_violation(self):
        bad_sample = (
            "## 12. Declared change set derivation\n\n"
            "The default entries are `feature-docs/{feature}/**` and "
            "`test-docs/{feature}/**`, both excluded from the observed "
            "change set at verification time."
        )
        self.assertTrue(
            FEATURE_DOCS_ROOT_LITERAL in bad_sample
            and TEST_DOCS_ROOT_LITERAL in bad_sample
        )
        lowered = bad_sample.lower()
        self.assertTrue(any(word in lowered for word in EXCLUSION_WORDS))


if __name__ == "__main__":
    unittest.main()
