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

Round-1 rework (task0015, source_ids `45cc2053b58d2a24`) extends this module
with the third input (implement-derived additions), the single retention
location, and the third re-derivation trigger (an implement wake that
admitted a deviation) -- covering task0015 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0015.md):

- AC-1 (FR19): Inputs name the implement-derived additions, citing
  `implement-phase.md`'s auto-addition rule by path without restating its
  evidence condition.
- AC-2 (FR19): exactly one retention location is named, and re-derivation
  is stated to read it.
- AC-3 (FR19, NFR3): Timing lists the implement-wake trigger alongside the
  existing two.
- AC-4 (FR18): the guard status, default-entry citation and containment
  semantics stay exactly as task0009 pinned them (retention pin, no new
  test needed beyond the unmodified existing classes below).
- AC-5 (NFR1, C6c/C6d): the auto-addition condition and the default-entry
  enumeration are not restated, the two root globs never co-occur, and no
  exclusion wording is introduced.

Round-2 rework (task0020, review round 2, source_ids `c6b1737a7d7e82f1`,
`c64996c1c4a836d2`, `ad9b77c0c67b93f7`) covers task0020 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0020.md), create-plan-side
only (C4; the implement-phase.md-side assertions live in
test_deviation_auto_addition.py):

- AC-5 (FR18): `TestTask0020AC5RetentionSurvivesReplanning` -- the
  Retention bullet states that the location survives re-derivation because
  a re-planning `replace_all` may not drop a registered task entry, citing
  `references/workflow-patch.md` by path without restating the rule.
- AC-7 (NFR1): `TestTask0020AC7NoRestatementInSection12` -- the evidence
  form and the write procedure (implement-phase.md's own content) are not
  restated in this section.
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

# task0015 AC-1 literals: the third input (implement-derived additions),
# cited by path, its evidence condition not restated here.
IMPLEMENT_PHASE_CITATION = "references/implement-phase.md"
IMPLEMENT_DERIVED_PHRASE = "implement-derived additions"
EVIDENCE_CONDITION_PHRASE = "acceptance criterion would otherwise be dropped"

# task0015 AC-2 literals: the single retention location, and re-derivation
# reading it.
RETENTION_LOCATION_PHRASE = "the `files` list of the task whose deviation was admitted"
RETENTION_READS_LOCATION_PHRASE = "Re-derivation reads that location"
RETENTION_SURVIVES_PHRASE = "survive every later re-derivation"

# task0015 AC-3 literals: the third re-derivation trigger, alongside the
# existing two.
TRIGGER_REPLANNING_PHRASE = "re-planning"
TRIGGER_REWORK_APPEND_PHRASE = "rework append"
TRIGGER_IMPLEMENT_WAKE_PHRASE = "an implement wake that admitted a deviation"

# task0020 AC-5 literals: the Retention bullet's no-drop reason, cited by
# path to workflow-patch.md (task0017 owns that document this round; never
# restated here).
RETENTION_NO_DROP_PHRASE = (
    "a re-planning `replace_all` may not drop an already-registered task "
    "entry"
)
WORKFLOW_PATCH_CITATION = "references/workflow-patch.md"

# task0020 AC-7 literals: the evidence form / write procedure that live
# only in implement-phase.md and must not be restated here.
TASK0020_APPEND_PHRASE = "an append to that same task's `files`"
TASK0020_SAME_COMMIT_PHRASE = "in the same commit as the status update"
TASK0020_PATH_BEING_ADDED_PHRASE = "the path being added"
TASK0020_RESOLVE_EXISTS_PHRASE = "must resolve to something that exists"


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


class TestThirdInputStated(unittest.TestCase):
    """task0015 AC-1 (FR19): the implement-derived additions are named as a
    third input, citing implement-phase.md's auto-addition rule by path
    without restating its evidence condition."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_implement_derived_additions_named(self):
        self.assertIn(IMPLEMENT_DERIVED_PHRASE, self.section)

    def test_implement_phase_cited_by_path(self):
        self.assertIn(IMPLEMENT_PHASE_CITATION, self.section)

    def test_evidence_condition_not_restated(self):
        self.assertNotIn(EVIDENCE_CONDITION_PHRASE, self.section)

    def test_all_three_inputs_present_together(self):
        self.assertTrue(
            TASKS_FILES_LITERAL in self.section
            and DEFAULT_ENTRIES_PHRASE in self.section
            and IMPLEMENT_DERIVED_PHRASE in self.section
            and IMPLEMENT_PHASE_CITATION in self.section
        )


class TestRetentionLocationStated(unittest.TestCase):
    """task0015 AC-2 (FR19): exactly one retention location is named, and
    re-derivation is stated to read it, so an admitted addition survives
    every later re-derivation."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_retention_location_named(self):
        self.assertIn(RETENTION_LOCATION_PHRASE, self.section)

    def test_rederivation_reads_that_location(self):
        self.assertIn(RETENTION_READS_LOCATION_PHRASE, self.section)

    def test_survives_every_later_rederivation(self):
        self.assertIn(RETENTION_SURVIVES_PHRASE, self.section)


class TestThirdTriggerStated(unittest.TestCase):
    """task0015 AC-3 (FR19, NFR3): Timing lists an implement wake that
    admitted a deviation as a re-derivation trigger, alongside the existing
    two (re-planning, rework append)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_all_three_triggers_present_together(self):
        self.assertTrue(
            TRIGGER_REPLANNING_PHRASE in self.section
            and TRIGGER_REWORK_APPEND_PHRASE in self.section
            and TRIGGER_IMPLEMENT_WAKE_PHRASE in self.section
        )


class TestTask0020AC5RetentionSurvivesReplanning(unittest.TestCase):
    """task0020 AC-5 (FR18): the Retention bullet states that the location
    survives re-derivation because a re-planning `replace_all` may not
    drop a registered task entry, citing `references/workflow-patch.md` by
    path without restating the rule."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_derivation_section(_read()))

    def test_retention_states_the_no_drop_reason(self):
        self.assertIn(RETENTION_NO_DROP_PHRASE, self.section)

    def test_retention_cites_workflow_patch_by_path(self):
        self.assertIn(WORKFLOW_PATCH_CITATION, self.section)

    def test_existing_retention_pins_still_hold(self):
        # C5 retention half: the location/read/survive pins task0015 wrote
        # stay true after this rework -- not weakened, only extended.
        self.assertIn(RETENTION_LOCATION_PHRASE, self.section)
        self.assertIn(RETENTION_READS_LOCATION_PHRASE, self.section)
        self.assertIn(RETENTION_SURVIVES_PHRASE, self.section)

    def test_does_not_restate_workflow_patchs_own_rule_text(self):
        # NFR1/C2: workflow-patch.md's own permission-condition / protocol
        # error prose is never copied here -- only cited by path.
        self.assertNotIn("Initial-planning path", self.section)
        self.assertNotIn("protocol error on BOTH paths", self.section)


class TestTask0020AC7NoRestatementInSection12(unittest.TestCase):
    """task0020 AC-7 (NFR1): the evidence form and the write procedure are
    each stated in exactly one document -- implement-phase.md, the rule's
    own home -- and this section cites rather than repeats them."""

    @classmethod
    def setUpClass(cls):
        cls.section = _derivation_section(_read())

    def test_section_does_not_restate_the_write_procedure(self):
        self.assertNotIn(TASK0020_APPEND_PHRASE, self.section)
        self.assertNotIn(TASK0020_SAME_COMMIT_PHRASE, self.section)

    def test_section_does_not_restate_the_evidence_form(self):
        self.assertNotIn(TASK0020_PATH_BEING_ADDED_PHRASE, self.section)
        self.assertNotIn(TASK0020_RESOLVE_EXISTS_PHRASE, self.section)


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

    def test_third_input_matchers_flag_a_sample_naming_only_the_two_existing_sources(
        self,
    ):
        sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "- **Inputs**: the union of `tasks.*.files` entries and the "
            "default entries."
        )
        self.assertFalse(
            TASKS_FILES_LITERAL in sample
            and DEFAULT_ENTRIES_PHRASE in sample
            and IMPLEMENT_DERIVED_PHRASE in sample
            and IMPLEMENT_PHASE_CITATION in sample
        )

    def test_retention_matchers_flag_a_sentence_naming_two_different_locations(
        self,
    ):
        sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "- **Retention**: an admitted addition is retained both in "
            "`phase-state/rework.yaml` and in the task's completion "
            "report."
        )
        self.assertNotIn(RETENTION_LOCATION_PHRASE, sample)
        self.assertNotIn(RETENTION_READS_LOCATION_PHRASE, sample)

    def test_third_trigger_matcher_flags_a_timing_list_carrying_only_the_two_existing_triggers(
        self,
    ):
        sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "- **Timing**: re-derived whenever the task set changes — "
            "re-planning, or a rework append."
        )
        self.assertTrue(
            TRIGGER_REPLANNING_PHRASE in sample
            and TRIGGER_REWORK_APPEND_PHRASE in sample
        )
        self.assertFalse(TRIGGER_IMPLEMENT_WAKE_PHRASE in sample)

    def test_evidence_condition_matcher_flags_a_synthetic_violation(self):
        bad_sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "the implement-derived additions are admitted only when "
            "accompanied by evidence that an existing acceptance criterion "
            "would otherwise be dropped."
        )
        self.assertIn(EVIDENCE_CONDITION_PHRASE, bad_sample)

    def test_no_drop_matcher_flags_absence_in_synthetic_sample(self):
        sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "- **Retention**: an admitted addition is retained and "
            "survives every later re-derivation."
        )
        self.assertNotIn(RETENTION_NO_DROP_PHRASE, sample)
        self.assertNotIn(WORKFLOW_PATCH_CITATION, sample)

    def test_no_drop_matcher_flags_presence_in_a_synthetic_violation(self):
        # "Violation" here means the opposite: a sample that DOES carry the
        # required phrasing, proving the matcher can also detect presence.
        good_sample = _normalize_ws(
            "## 12. Declared change set derivation\n\n"
            "- **Retention**: survives every later re-derivation because a "
            "re-planning `replace_all` may not drop an already-registered "
            "task entry (references/workflow-patch.md)."
        )
        self.assertIn(RETENTION_NO_DROP_PHRASE, good_sample)
        self.assertIn(WORKFLOW_PATCH_CITATION, good_sample)


if __name__ == "__main__":
    unittest.main()
