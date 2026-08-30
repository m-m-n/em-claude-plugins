"""Tests for task0018 (goal-vs-spec-divergence, review round 2 finding
68d1f5558ed5ae1d): create-spec-phase.md's workflow.yaml construction section
(section 11) states that a `create-spec` re-entry with `status:
needs_update` is a partial update, not a reconstruction, and enumerates what
survives it.

Also covers task0026 (goal-vs-spec-divergence, review round 3 finding
b5f85c29102b8c97): the same section's `requirements` member of the
partial-update list is replaced with an upsert rule, sourced from
spec-writer's `spec_index`, so that a SPEC change adding or altering a
requirement produces a `workflow.yaml` requirement map the following
re-planning pass can register tasks against, while every surviving
requirement's already-earned `tasks` and `tests` history survives the
re-entry.

Covers task0018 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0018.md):

- AC-1 (FR6): section 11 states that a `create-spec` re-entry with
  `status: needs_update` is a partial update rather than a reconstruction of
  `workflow.yaml`.
- AC-2 (FR5): the preserved set is enumerated and names, individually,
  `tasks`, each step's `status`, `workflow.implement.base_commit` and
  `completed_at_commit`. A pin fails if any one of the four is dropped from
  the enumeration later.
- AC-3: the section also names what the re-entry does write, so the
  statement bounds the partial update in both directions rather than only
  listing exclusions.
- AC-4 (FR2, retention): the existing `goal` re-entry carve-out is still
  present and unchanged in meaning -- the new statement does not absorb,
  reword or replace it.
- AC-5 (NFR1): the statement cites `references/workflow-patch.md` and
  `references/rework-task-synthesis.md` rather than restating either
  document's rules; no rule text is duplicated into this section.
- AC-6 (NFR5, NFR8): standard-library only, a negative proof against a
  synthetic sample missing the preservation statement, and a non-vacuity
  guard for every absence assertion.

Covers task0026 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0026.md):

- AC-1 (FR6): `requirements` is no longer listed among the things a
  `needs_update` re-entry leaves untouched, and the section states an
  upsert rule in its place, sourced from spec-writer's `spec_index`.
- AC-2 (FR5): the upsert rule states that a surviving requirement's `tasks`
  and `tests` arrays are preserved and that only the fields the
  `spec_index` owns are refreshed -- a requirement that merged tasks
  already reference does not lose that reference.
- AC-3 (FR6): the rule states exactly one outcome for a requirement that
  disappears from the new `spec_index`, and that outcome keeps the id
  resolvable for any merged task whose `requirements` names it. No wording
  permits dropping such an entry.
- AC-4 (FR6): the section states that the upsert happens during create-spec
  and therefore precedes the re-planning patch's validation, so a task
  entry naming a newly added requirement id is acceptable when that patch
  is applied.
- AC-5 (NFR8): every other member of the partial-update list is still
  present with the same force -- covered by the pre-existing task0018
  classes above, left untouched by this task's edit.
- AC-6 (NFR1, NFR5): the rule is stated once, in create-spec-phase.md, and
  cites `references/workflow-schema.md` for the requirement entry's shape
  rather than restating it.

Per task0026's Test Notes: the "untouched" list matcher is kept (not
weakened), a positive matcher is added for the upsert rule, and a negative
proof shows a document still listing `requirements` as untouched fails.
AC-3's matcher asserts the presence of a named outcome, not merely the
absence of the word "delete". This module never asserts over
`references/workflow-patch.md`, `references/phase-state.md` or
`skills/develop/SKILL.md` -- task0022 and task0023 own those this round
(C4).

Per the task's Test Notes: assertions here scan only section 11 of
`em-workflow/references/phases/create-spec-phase.md` (C4) -- not the whole
document, and never `references/workflow-patch.md` or
`references/rework-task-synthesis.md` themselves (those are sibling tasks'
/ other sections' files; cross-document agreement is a verify-phase item,
C4/C8 in IMPLEMENTATION.md).

AC-2/AC-3/AC-5 assertions are scoped to a dedicated slice bounded by the new
statement's own lead marker and the pre-existing `**The `goal` field**:`
heading that immediately follows it in section 11 -- NOT to the whole
section -- because section 11 already mentions `completed_at_commit` (in
the unrelated `create-spec` step's own field) and
`references/workflow-patch.md` (in the unrelated "workers never write
workflow.yaml themselves" sentence) before this task's edit exists. Scoping
to the whole section would let those pre-existing, unrelated mentions make
an assertion pass before the statement this task adds is written at all.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

CONSTRUCTION_START = "## 11. workflow.yaml construction"
CONSTRUCTION_END = "## 11a. Design-system determination"

# The new statement's own lead marker, immediately followed in section 11 by
# the pre-existing `goal`-field heading -- bounds a slice covering only the
# text this task adds.
REENTRY_STATEMENT_START = "**Partial update on re-entry**"
REENTRY_STATEMENT_END = "**The `goal` field**"

# Ties the "partial update, not a reconstruction" statement to `needs_update`
# specifically, not to any generic mention of re-entry (mirrors the Test
# Notes discipline used for the sibling `goal` carve-out pin).
NEEDS_UPDATE_PARTIAL_UPDATE_RE = re.compile(
    r"needs_update.{0,400}partial\s+update.{0,200}(not\s+a\s+reconstruction|"
    r"never\s+a?\s*reconstruction)",
    re.IGNORECASE | re.DOTALL,
)

# The existing `goal` carve-out's own literal sentences (unchanged since
# task0001/task0007/task0014). Retention check (AC-4): a careless rewrite of
# section 11 that folded this into the new general statement would drop
# these exact sentences.
GOAL_CARVEOUT_UNCHANGED_SENTENCE_1 = (
    "an existing `goal` block is left exactly as it is."
)
GOAL_CARVEOUT_UNCHANGED_SENTENCE_2 = (
    "Only a first construction of `workflow.yaml` writes it."
)

# task0026: the `requirements` upsert rule's own heading. It bounds the
# untouched-list slice (everything before it, within REENTRY_STATEMENT) from
# the upsert rule's own text (everything from it onward, up to the
# pre-existing `goal`-field heading).
REQUIREMENTS_UPSERT_HEADING = "**The `requirements` upsert**"

# task0026 AC-2: ties the surviving-id preservation rule to `tasks` and
# `tests` specifically, and to "refreshed" for the index-owned fields --
# not to any generic mention of "requirements" or "preserved".
SURVIVING_ID_PRESERVED_RE = re.compile(
    r"present in both.{0,300}`tasks`.{0,50}`tests`.{0,200}exactly\s+as\s+"
    r"they\s+are.{0,400}refreshed",
    re.IGNORECASE | re.DOTALL,
)

# task0026 AC-3: ties the disappearing-id rule to `spec_index` absence and
# to resolvability for a merged task, requiring a POSITIVE outcome word
# (kept/retained/remains) rather than merely the absence of "delete" (Test
# Notes: an absence-only assertion passes against a document that says
# nothing at all).
DISAPPEARING_ID_OUTCOME_RE = re.compile(
    r"absent from the new `spec_index`.{0,300}(kept|retained|remains?)"
    r".{0,200}resolvable",
    re.IGNORECASE | re.DOTALL,
)

# task0026 AC-4: ties the ordering claim to create-spec preceding the
# re-planning patch's validation, and to that ordering being what makes a
# newly named requirement id acceptable.
UPSERT_ORDERING_RE = re.compile(
    r"during create-spec.{0,200}before.{0,200}re-planning\s+patch.{0,200}"
    r"validated.{0,300}acceptable",
    re.IGNORECASE | re.DOTALL,
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _reentry_statement(text):
    section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
    return _slice(section, REENTRY_STATEMENT_START, REENTRY_STATEMENT_END)


def _untouched_list_slice(statement):
    """task0026: the portion of the re-entry statement that lists what is
    left untouched -- bounded before the `requirements` upsert rule's own
    heading, so a mention of `requirements` inside the upsert rule itself
    can never satisfy an assertion scoped to this slice."""
    return _slice(statement, REENTRY_STATEMENT_START, REQUIREMENTS_UPSERT_HEADING)


def _upsert_rule_slice(statement):
    """task0026: the portion of the re-entry statement from the
    `requirements` upsert rule's own heading onward (to the end of the
    REENTRY_STATEMENT slice)."""
    idx = statement.index(REQUIREMENTS_UPSERT_HEADING)
    return statement[idx:]


class TestFileExists(unittest.TestCase):
    def test_create_spec_phase_doc_exists(self):
        self.assertTrue(
            CREATE_SPEC_PATH.is_file(), f"expected {CREATE_SPEC_PATH} to exist"
        )


class TestConstructionSectionSliceIsLocatedAndNonEmpty(unittest.TestCase):
    """Non-vacuity guard: confirm the section slice used below was actually
    located and is non-empty, so a marker typo cannot make every other test
    in this module vacuously pass."""

    def test_construction_section_slice_non_empty(self):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        self.assertGreater(len(section), 0)
        self.assertIn("workflow.yaml construction", section)


class TestReentryStatementSliceIsLocatedAndNonEmpty(unittest.TestCase):
    """Non-vacuity guard for the narrower slice: the new statement's own
    lead marker must be found before the pre-existing `goal`-field heading,
    and the slice between them must be non-empty. Without this guard, a
    marker typo in the matchers below could make every AC-2/AC-3/AC-5 test
    silently pass against an empty slice."""

    def test_reentry_statement_slice_non_empty(self):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        statement = _slice(
            section, REENTRY_STATEMENT_START, REENTRY_STATEMENT_END
        )
        self.assertGreater(len(statement.strip()), 0)


class TestReentryIsPartialUpdateNotReconstruction(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_regex_matches_a_positive_synthetic_sample(self):
        sample = (
            "when create-spec is re-entered with `status: needs_update`, "
            "building workflow.yaml here is a partial update, not a "
            "reconstruction."
        )
        self.assertRegex(sample, NEEDS_UPDATE_PARTIAL_UPDATE_RE)

    def test_regex_rejects_generic_partial_update_wording_without_needs_update(
        self,
    ):
        # Edge case: a document that only ever says "this is a partial
        # update, not a reconstruction" without tying it to `needs_update`
        # must NOT satisfy the matcher.
        sample = "this write is a partial update, not a reconstruction."
        self.assertNotRegex(sample, NEEDS_UPDATE_PARTIAL_UPDATE_RE)

    def test_document_states_reentry_is_a_partial_update_tied_to_needs_update(
        self,
    ):
        self.assertRegex(self.section, NEEDS_UPDATE_PARTIAL_UPDATE_RE)

    def test_needs_update_status_literal_present(self):
        self.assertIn("needs_update", self.section)


class TestPreservedSetEnumeratesAllFourNamesIndividually(unittest.TestCase):
    """AC-2: `tasks`, each step's `status`, `workflow.implement.base_commit`
    and `completed_at_commit` are each named individually in the new
    statement's own enumeration, so a partial regression names the field
    that went missing."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        cls.statement = _slice(
            section, REENTRY_STATEMENT_START, REENTRY_STATEMENT_END
        )

    def test_tasks_named_as_preserved(self):
        self.assertIn(
            "`tasks`",
            self.statement,
            "expected the preserved-set enumeration to name `tasks`",
        )

    def test_each_steps_status_named_as_preserved(self):
        self.assertIn(
            "step's `status`",
            self.statement,
            "expected the preserved-set enumeration to name each step's "
            "`status`",
        )

    def test_base_commit_named_as_preserved(self):
        self.assertIn(
            "`workflow.implement.base_commit`",
            self.statement,
            "expected the preserved-set enumeration to name "
            "`workflow.implement.base_commit`",
        )

    def test_completed_at_commit_named_as_preserved(self):
        self.assertIn(
            "`completed_at_commit`",
            self.statement,
            "expected the preserved-set enumeration to name "
            "`completed_at_commit`",
        )

    def test_synthetic_sample_missing_any_one_name_fails_the_check(self):
        # Non-vacuity / negative proof: a synthetic enumeration missing one
        # of the four names must not satisfy that name's assertion, proving
        # each check above is independently discriminating.
        sample_missing_base_commit = (
            "the re-entry preserves `tasks`, each step's `status` and "
            "`completed_at_commit`."
        )
        self.assertNotIn(
            "`workflow.implement.base_commit`", sample_missing_base_commit
        )

        sample_missing_completed_at_commit = (
            "the re-entry preserves `tasks`, each step's `status` and "
            "`workflow.implement.base_commit`."
        )
        self.assertNotIn(
            "`completed_at_commit`", sample_missing_completed_at_commit
        )

        sample_missing_tasks = (
            "the re-entry preserves each step's `status`, "
            "`workflow.implement.base_commit` and `completed_at_commit`."
        )
        self.assertNotIn("`tasks`", sample_missing_tasks)

        sample_missing_step_status = (
            "the re-entry preserves `tasks`, `workflow.implement.base_commit` "
            "and `completed_at_commit`."
        )
        self.assertNotIn("step's `status`", sample_missing_step_status)


class TestReentryWriteScopeIsBoundedInBothDirections(unittest.TestCase):
    """AC-3: the new statement names what the re-entry DOES write, not only
    what it leaves untouched."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        cls.statement = _slice(
            section, REENTRY_STATEMENT_START, REENTRY_STATEMENT_END
        )

    def test_states_what_the_reentry_does_write(self):
        lowered = self.statement.lower()
        self.assertIn("does write", lowered)
        self.assertIn("create-spec artifacts", lowered)

    def test_states_the_step_statuses_the_transition_assigns(self):
        self.assertIn(
            "the step statuses the transition assigns", self.statement.lower()
        )

    def test_synthetic_sample_missing_the_statement_fails_the_check(self):
        sample = "the re-entry leaves tasks and base_commit untouched."
        lowered = sample.lower()
        self.assertNotIn("does write", lowered)
        self.assertNotIn("create-spec artifacts", lowered)
        self.assertNotIn("the step statuses the transition assigns", lowered)


class TestGoalCarveoutRetainedUnabsorbed(unittest.TestCase):
    """AC-4 (retention, C5): the pre-existing `goal` re-entry carve-out
    still stands on its own -- its own literal sentences are unchanged and
    were not folded into the new general statement."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_goal_carveout_sentence_one_still_present_verbatim(self):
        self.assertIn(
            GOAL_CARVEOUT_UNCHANGED_SENTENCE_1,
            self.section,
            "expected the pre-existing `goal` re-entry sentence to survive "
            "verbatim",
        )

    def test_goal_carveout_sentence_two_still_present_verbatim(self):
        self.assertIn(
            GOAL_CARVEOUT_UNCHANGED_SENTENCE_2,
            self.section,
            "expected the pre-existing `goal` re-entry sentence to survive "
            "verbatim",
        )

    def test_goal_field_heading_still_present(self):
        # The goal carve-out lives under its own labelled subsection; if a
        # rewrite absorbed it into the new general statement, this heading
        # would be the first casualty.
        self.assertIn("**The `goal` field**", self.section)

    def test_new_statement_precedes_and_is_distinct_from_the_goal_heading(self):
        # The new statement's marker must appear strictly BEFORE the
        # pre-existing goal-field heading, i.e. it is prepended alongside
        # the carve-out rather than replacing or wrapping it.
        self.assertLess(
            self.section.index(REENTRY_STATEMENT_START),
            self.section.index(REENTRY_STATEMENT_END),
        )

    def test_synthetic_sample_without_the_carveout_sentences_fails_the_check(
        self,
    ):
        sample = (
            "on re-entry, tasks and base_commit survive; goal handling is "
            "covered by the general rule above."
        )
        self.assertNotIn(GOAL_CARVEOUT_UNCHANGED_SENTENCE_1, sample)
        self.assertNotIn(GOAL_CARVEOUT_UNCHANGED_SENTENCE_2, sample)


class TestCitesWithoutRestatingSiblingDocuments(unittest.TestCase):
    """AC-5 (NFR1): the new statement cites `references/workflow-patch.md`
    and `references/rework-task-synthesis.md` rather than restating either
    document's rules. This module never reads those documents (Test Notes /
    C4/C8) -- only known phrases unique to their own rule text are checked
    for absence here, as a duplication guard."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        cls.statement = _slice(
            section, REENTRY_STATEMENT_START, REENTRY_STATEMENT_END
        )
        cls.section = section

    def test_cites_workflow_patch_path(self):
        self.assertIn("references/workflow-patch.md", self.statement)

    def test_cites_rework_task_synthesis_path(self):
        self.assertIn("references/rework-task-synthesis.md", self.statement)

    def test_does_not_restate_the_replanning_paths_own_rule_text(self):
        # Phrases that belong to workflow-patch.md's own description of the
        # Re-planning path's permission conditions -- restating them here
        # would duplicate a rule that already has exactly one home.
        self.assertNotIn(
            "recognizable as having come through", self.section
        )
        self.assertNotIn("mandatory `preserve` set", self.section)
        self.assertNotIn("in the patch's `preserve` list", self.section)

    def test_does_not_restate_the_spec_change_transitions_own_step_list(self):
        # Phrases that belong to rework-task-synthesis.md Section 10's own
        # five-step transition list -- restating them here would duplicate
        # a rule that already has exactly one home.
        self.assertNotIn(
            "the develop state machine re-enters at create-spec",
            self.section,
        )
        self.assertNotIn(
            "records the interruption reason and the finding's",
            self.section,
        )

    def test_synthetic_sample_with_restated_text_fails_the_absence_checks(self):
        # Non-vacuity guard for the four assertNotIn checks above: a sample
        # that DOES restate the sibling documents' rule text must trip
        # them, proving the checks are not vacuous.
        sample = (
            "a `create-plan` reads `pending` on a re-entry recognizable as "
            "having come through a `create-spec: needs_update` cycle, per "
            "the mandatory `preserve` set and the value appearing in the "
            "patch's `preserve` list; the develop state machine re-enters "
            "at create-spec, and phase-state records the interruption "
            "reason and the finding's stable_id."
        )
        self.assertIn("recognizable as having come through", sample)
        self.assertIn("mandatory `preserve` set", sample)
        self.assertIn("in the patch's `preserve` list", sample)
        self.assertIn(
            "the develop state machine re-enters at create-spec", sample
        )
        self.assertIn(
            "records the interruption reason and the finding's", sample
        )


class TestRequirementsUpsertHeadingPresentAndBounded(unittest.TestCase):
    """task0026 non-vacuity guard: the upsert rule's own heading must be
    found inside the re-entry statement, and both the slice before it (the
    untouched list) and the slice from it onward (the upsert rule) must be
    non-empty -- otherwise a marker typo could make every task0026 test
    below silently pass against an empty slice."""

    def test_requirements_upsert_heading_present_with_non_empty_slices_around_it(
        self,
    ):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        self.assertIn(REQUIREMENTS_UPSERT_HEADING, statement)
        untouched_list = _untouched_list_slice(statement)
        upsert_rule = _upsert_rule_slice(statement)
        self.assertGreater(len(untouched_list.strip()), 0)
        self.assertGreater(len(upsert_rule.strip()), 0)


class TestRequirementsLeavesUntouchedListAndGainsUpsertRule(unittest.TestCase):
    """task0026 AC-1 (FR6): `requirements` is no longer listed among the
    things a `needs_update` re-entry leaves untouched, and the section
    states an upsert rule in its place, sourced from spec-writer's
    `spec_index`."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        cls.untouched_list = _untouched_list_slice(statement)
        cls.upsert_rule = _upsert_rule_slice(statement)

    def test_requirements_not_named_in_the_untouched_list(self):
        self.assertNotIn("`requirements`", self.untouched_list)

    def test_project_still_named_on_its_own_in_the_untouched_list(self):
        # AC-5: `project` keeps standing on its own, with the same force,
        # once `requirements` is removed from the same bullet.
        self.assertIn("`project`", self.untouched_list)

    def test_upsert_rule_sourced_from_spec_writers_spec_index(self):
        self.assertIn("`requirements`", self.upsert_rule)
        self.assertIn("spec_index", self.upsert_rule)
        self.assertIn("spec-writer", self.upsert_rule.lower())

    def test_synthetic_sample_still_listing_requirements_as_untouched_is_a_non_vacuous_check(
        self,
    ):
        # Non-vacuity: proves the assertNotIn above is discriminating
        # against exactly the old wording, not vacuously true against any
        # text.
        sample = (
            "- `workflow.implement.base_commit`;\n"
            "- `project` and `requirements`;\n"
            "- `goal` (carved out separately below).\n"
        )
        self.assertIn("`requirements`", sample)


class TestSurvivingRequirementPreservesTasksAndTests(unittest.TestCase):
    """task0026 AC-2 (FR5): a surviving requirement's `tasks` and `tests`
    arrays are preserved, and only the fields `spec_index` owns are
    refreshed -- a requirement that merged tasks already reference does not
    lose that reference."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        cls.upsert_rule = _upsert_rule_slice(statement)

    def test_surviving_id_tasks_and_tests_preserved_and_only_index_owned_fields_refreshed(
        self,
    ):
        self.assertRegex(self.upsert_rule, SURVIVING_ID_PRESERVED_RE)

    def test_merged_task_reference_is_stated_to_survive(self):
        self.assertIn(
            "does not lose that reference", self.upsert_rule.lower()
        )

    def test_synthetic_sample_without_the_preservation_wording_fails_the_check(
        self,
    ):
        sample = (
            "an id present in both is refreshed from `spec_index`, "
            "including its status."
        )
        self.assertNotRegex(sample, SURVIVING_ID_PRESERVED_RE)
        self.assertNotIn("does not lose that reference", sample.lower())


class TestDisappearingRequirementKeepsExactlyOneResolvableOutcome(
    unittest.TestCase
):
    """task0026 AC-3 (FR6): exactly one outcome is stated for a
    requirement that disappears from the new `spec_index`, and that
    outcome keeps the id resolvable for any merged task whose
    `requirements` names it. No wording permits dropping such an entry."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        cls.upsert_rule = _upsert_rule_slice(statement)

    def test_states_a_named_outcome_that_stays_resolvable(self):
        self.assertRegex(self.upsert_rule, DISAPPEARING_ID_OUTCOME_RE)

    def test_states_exactly_one_outcome_literally(self):
        self.assertIn("exactly one outcome", self.upsert_rule)

    def test_no_wording_permits_dropping_the_entry(self):
        self.assertIn(
            "No wording here permits dropping such an entry",
            self.upsert_rule,
        )

    def test_synthetic_sample_missing_the_named_outcome_fails_the_check(self):
        # Test Notes: an absence-only assertion (e.g. only checking that
        # "delete" is not mentioned) would pass against a document that
        # says nothing at all about the disappearing case -- so the
        # positive-outcome regex above must reject a sample that is silent
        # on the outcome, proven here.
        sample = (
            "an id present in `workflow.yaml` and absent from the new "
            "`spec_index` is handled per the usual process."
        )
        self.assertNotRegex(sample, DISAPPEARING_ID_OUTCOME_RE)
        self.assertNotIn("exactly one outcome", sample)


class TestUpsertOrderingPrecedesReplanningPatchValidation(unittest.TestCase):
    """task0026 AC-4 (FR6): the upsert happens during create-spec and
    therefore precedes the re-planning patch's validation, so a task entry
    naming a newly added requirement id is acceptable when that patch is
    applied."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        cls.upsert_rule = _upsert_rule_slice(statement)

    def test_states_the_upsert_precedes_replanning_patch_validation(self):
        self.assertRegex(self.upsert_rule, UPSERT_ORDERING_RE)

    def test_synthetic_sample_missing_the_ordering_statement_fails_the_check(
        self,
    ):
        sample = (
            "the upsert rebuilds `requirements` from `spec_index` "
            "whenever create-spec runs."
        )
        self.assertNotRegex(sample, UPSERT_ORDERING_RE)


class TestUpsertCitesWorkflowSchemaForEntryShapeWithoutRestating(
    unittest.TestCase
):
    """task0026 AC-6 (NFR1, NFR5): the requirement entry's shape is cited
    from `references/workflow-schema.md`, not restated here."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        statement = _reentry_statement(text)
        cls.upsert_rule = _upsert_rule_slice(statement)

    def test_cites_workflow_schema_path(self):
        self.assertIn("references/workflow-schema.md", self.upsert_rule)

    def test_synthetic_sample_without_the_citation_fails_the_check(self):
        sample = (
            "an id present in the new `spec_index` and absent from "
            "`workflow.yaml` is created with its title and status."
        )
        self.assertNotIn("references/workflow-schema.md", sample)


class TestSectionHeadingsUnchangedAndInOrder(unittest.TestCase):
    """AC-6 / C3 / C5: this task extends section 11 in place -- no
    numbered section of create-spec-phase.md is renumbered or added."""

    EXPECTED_HEADINGS = [
        "## 1. Purpose and ownership",
        "## 2. Inputs and preconditions",
        "## 3. Bootstrap and durable-state boundary",
        "## 4. Reconcile on entry",
        "## 5. Analyst dispatch loop",
        "## 6. Question normalization",
        "## 7. Interactive answer handling",
        "## 8. Batch answer handling",
        "## 9. Spec writer dispatch",
        "## 10. Artifact validation",
        "## 11. workflow.yaml construction",
        "## 11a. Design-system determination",
        "## 12. Command approval gate",
        "## 13. Completion",
        "## Termination conditions",
        "## Loop-stop conditions (progress fingerprint)",
        "## Scope verification",
        "## Gate option vocabulary",
    ]

    HEADING_RE = re.compile(r"^## .+$", re.MULTILINE)

    def test_expected_headings_all_present_in_order(self):
        text = _read(CREATE_SPEC_PATH)
        found = self.HEADING_RE.findall(text)
        self.assertEqual(found, self.EXPECTED_HEADINGS)


if __name__ == "__main__":
    unittest.main()
