"""Tests for task0001 (task-id-allocation-ssot): rewriting
`em-workflow/references/implement-phase.md` Step I.2.c so it no longer
assumes that re-planning recycles or renumbers task ids, cites
`references/workflow-patch.md`'s 'Re-planning task-id allocation' section
for the allocation rule, states that a task's own id owns its own journal
terminal events, re-grounds the three existing recycled-task-id
countermeasures on that owning rule, and replaces the old re-scope sentence
with wording the owning section already permits.

Covers task0001 Acceptance Criteria
(feature-docs/task-id-allocation-ssot/tasks/task0001.md):

- AC-1 (FR2, FR5): none of the five removed/replaced premise phrases
  survive in the whitespace-normalized I.2.c section; the same absence
  matcher detects each of them in the pre-change I.2.c sample this module
  captured verbatim before the edit landed.
- AC-2 (FR1, FR3): I.2.c names `references/workflow-patch.md` together
  with the section heading 'Re-planning task-id allocation', and states
  that a task's journal terminal events are its own because task ids are
  never re-issued; neither matcher fires on the pre-change sample.
- AC-4 (FR4): I.2.c records, in one explicit re-judgment passage, that each
  of `deny_already_merged`, the third conjunct and the failed+pending
  carve-out remains necessary under the owning rule; the pre-change sample
  contains no such passage.
- AC-5 (FR5): the re-scope replacement states that the failed task's id is
  carried verbatim, that new tasks are added above the high-water mark,
  cites 'Re-planning task-id allocation', and keeps the SPEC.md update path
  for dropping a requirement; none of its presence matchers fire on the
  pre-change sample.
- AC-6 (FR6, NFR4): the 'recycled-task-id carve-out' label still appears in
  `implement-phase.md` and in `skills/develop/SKILL.md`; I.2.c contains
  neither the high-water-mark expression nor an enumeration of the carried
  record's full field list, while the same matchers detect both in the
  live owning section of `workflow-patch.md`.

AC-3 (FR4; the third conjunct's own anchors and its rewritten narrowing/
never-narrowed rationale) and AC-7 (the full-suite run) are covered
elsewhere: AC-3 by `tests/test_implement_routeback_gate.py` (literals
updated in place), AC-7 by running the whole suite.

"workflow-patch.md is not modified by this task" and "the label-retention
literals in the three retention-test modules are unmodified" are diff
facts confirmed at review and verify, per the task plan's Test Notes --
not persisted as tests here.

Matcher -> negative-proof inventory (every matcher this module adds):

- test_recycles_every_id_absent, test_renumbered_task_id_absent,
  test_leaves_a_recycled_id_launchable_absent,
  test_no_recycled_id_can_ever_inherit_absent,
  test_old_rescope_sentence_absent -> regression guards -> each has its
  positive counterpart in TestPreChangeSampleContainsRemovedPhrases below,
  proving the matcher is not vacuous.
- test_names_workflow_patch_with_heading,
  test_states_task_ids_never_reissued_and_terminal_events_are_own -> new
  wording -> test_ownership_matchers_absent_from_pre_change_sample.
- test_re_judgment_passage_names_all_three -> new wording ->
  test_re_judgment_opening_absent_from_pre_change_sample.
- test_rescope_states_id_carried_verbatim,
  test_rescope_states_new_tasks_above_high_water_mark,
  test_rescope_cites_replanning_allocation_section,
  test_rescope_keeps_spec_md_update_path -> new wording ->
  test_rescope_matchers_absent_from_pre_change_sample.
- test_carve_out_label_still_present_in_implement_phase_and_skill ->
  RETENTION matcher, no proof needed (label already existed pre-change).
- test_i2c_omits_high_water_mark_expression_and_full_field_list ->
  regression guard -> test_same_matchers_detect_both_in_owning_section
  (non-vacuity: the owning section is live text, not a frozen sample, so
  its own continued presence there each run is the proof).
"""

import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
WORKFLOW_PATCH_PATH = PLUGIN_ROOT / "references" / "workflow-patch.md"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"
REPLANNING_HEADING = "### Re-planning task-id allocation"
APPEND_REQUIREMENTS_HEADING = "### `append` requirements"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, matching this task's own Design/Test design section and
    the convention already used in tests/test_implement_routeback_gate.py."""
    return re.sub(r"\s+", " ", text)


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def _replanning_section(text):
    start = text.index(REPLANNING_HEADING)
    end = text.index(APPEND_REQUIREMENTS_HEADING, start)
    return text[start:end]


# --- Pre-change wording samples: verbatim excerpts of
# em-workflow/references/implement-phase.md's I.2.c section, captured
# BEFORE this task's edit landed (this feature's implement base commit) --
# not paraphrased, not reconstructed. Two samples because the removed/
# replaced passages are not contiguous in the source document.

PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE = (
    "  the owning rule, not restated. The second source is what makes the gate\n"
    "  admit route-back only when every task in the current plan whose journal\n"
    "  carries any event has a terminal journal last event (`merged` or\n"
    "  `failed`) — the planner's `replace_all` recycles every id, not only the\n"
    "  failed ones, so a task with no journal event at all has nothing to\n"
    "  inherit and never blocks route-back. A third conjunct blocks\n"
    "  independently of both halves above, closing a gap neither sees: whenever\n"
    "  the last-event-per-task replay alone reports any task's journal last\n"
    "  event as `merged`, route-back is inadmissible — this holds regardless of\n"
    "  the `git merge-base --is-ancestor` verification the `merged` half's\n"
    "  second source requires, so it blocks a task whose journal reports\n"
    "  `merged` even when that verification fails. The reason is one fact,\n"
    "  cited here from its owning bullet under 'Supporting cast: journal,\n"
    "  hooks, resume' below rather than restated: the launch guard denies a\n"
    "  launch whose journal last event is `merged`, so a renumbered task id\n"
    "  inheriting such an event could never be launched. This narrows the\n"
    "  terminal journal last event named just above: of `merged` and `failed`,\n"
    "  only the failed one leaves a recycled id launchable. This conjunct is\n"
    "  never narrowed to admit route-back for that state: no recycled id can\n"
    "  ever inherit a journal `merged` the launch guard denies through this\n"
    "  phase's own write set. The state it protects still has a way out that\n"
)

PRE_CHANGE_I2C_RESCOPE_SAMPLE = (
    '  ("停止条件 3 との優先関係") owns that precedence and dispatches the\n'
    "  planner with the step still `needs_update` (not restated here). The\n"
    "  planner re-scopes the failed task (split it, change the approach) — or,\n"
    "  when a requirement itself must be dropped, routes that change through\n"
    "  the normal SPEC.md update path first. When the gate does not hold —\n"
)


class TestPreChangeSampleContainsRemovedPhrases(unittest.TestCase):
    """Non-vacuity guard (Contract 4 pattern, same as
    tests/test_implement_routeback_gate.py's TestPreChangeSampleGuards):
    each removed/replaced phrase this task's AC-1 absence matchers check for
    is proven to have genuinely existed in the pre-change I.2.c text, so
    those absence matchers cannot be silently tautological."""

    def test_recycles_every_id_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertIn("recycles every id", sample)

    def test_renumbered_task_id_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertIn("renumbered task id", sample)

    def test_leaves_a_recycled_id_launchable_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertIn("leaves a recycled id launchable", sample)

    def test_no_recycled_id_can_ever_inherit_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertIn("no recycled id can ever inherit", sample)

    def test_old_rescope_sentence_present_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_RESCOPE_SAMPLE)
        self.assertIn(
            "The planner re-scopes the failed task (split it, change the "
            "approach)",
            sample,
        )


class TestAC1RemovedPremisePhrasesAbsent(unittest.TestCase):
    """AC-1: none of the five removed/replaced phrases survive in the
    whitespace-normalized I.2.c section. Paired positive proofs (that each
    phrase really was present pre-change) live in
    TestPreChangeSampleContainsRemovedPhrases above -- the same phrase
    string is never spelled twice."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read(IMPLEMENT_PHASE_PATH)))

    def test_recycles_every_id_absent(self):
        self.assertNotIn("recycles every id", self.section)

    def test_renumbered_task_id_absent(self):
        self.assertNotIn("renumbered task id", self.section)

    def test_leaves_a_recycled_id_launchable_absent(self):
        self.assertNotIn("leaves a recycled id launchable", self.section)

    def test_no_recycled_id_can_ever_inherit_absent(self):
        self.assertNotIn("no recycled id can ever inherit", self.section)

    def test_old_rescope_sentence_absent(self):
        self.assertNotIn(
            "The planner re-scopes the failed task (split it, change the "
            "approach)",
            self.section,
        )


class TestAC2OwnershipStatementCitesOwningSection(unittest.TestCase):
    """AC-2: I.2.c names workflow-patch.md together with the section
    heading 'Re-planning task-id allocation', and states that a task's
    journal terminal events are its own because task ids are never
    re-issued. Neither matcher fires on the pre-change sample."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read(IMPLEMENT_PHASE_PATH)))

    def test_names_workflow_patch_with_heading(self):
        self.assertIn("references/workflow-patch.md", self.section)
        idx = self.section.index("Re-planning task-id allocation")
        # the citation names the document immediately before the heading --
        # a tight window rules out an accidental, unrelated co-occurrence
        # of the two substrings elsewhere in the section.
        window = self.section[max(0, idx - 80) : idx]
        self.assertIn("workflow-patch.md", window)

    def test_states_task_ids_never_reissued_and_terminal_events_are_own(self):
        self.assertIn("task ids are never re-issued", self.section)
        self.assertIn(
            "every terminal event a task has is its own", self.section
        )
        # causal ordering: the never-re-issued premise precedes the
        # own-terminal-event consequence it is stated to produce.
        self.assertLess(
            self.section.index("task ids are never re-issued"),
            self.section.index("every terminal event a task has is its own"),
        )

    def test_ownership_matchers_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertNotIn("Re-planning task-id allocation", sample)
        self.assertNotIn("task ids are never re-issued", sample)
        self.assertNotIn(
            "every terminal event a task has is its own", sample
        )


class TestAC4ReJudgmentPassageNamesAllThreeCountermeasures(unittest.TestCase):
    """AC-4: I.2.c records, in one explicit re-judgment passage, that each
    of `deny_already_merged`, the third conjunct and the failed+pending
    carve-out remains necessary under the owning rule, each with a reason
    stated in terms of the task's own id. The pre-change sample contains no
    such passage."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read(IMPLEMENT_PHASE_PATH)))

    def test_re_judgment_passage_names_all_three(self):
        start = self.section.index("Re-judgment under the owning rule")
        end = self.section.index(
            "The state it protects still has a way out", start
        )
        passage = self.section[start:end]
        self.assertIn("`deny_already_merged`", passage)
        self.assertIn(
            "The third conjunct above blocks route-back", passage
        )
        self.assertIn("The recycled-task-id carve-out", passage)

    def test_re_judgment_reasons_are_stated_in_terms_of_the_own_id(self):
        start = self.section.index("Re-judgment under the owning rule")
        end = self.section.index(
            "The state it protects still has a way out", start
        )
        passage = self.section[start:end]
        self.assertIn("the task's own merged id", passage)
        self.assertIn("own last journal event is `merged`", passage)
        self.assertIn("a task's own `failed` status", passage)

    def test_re_judgment_opening_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_GATE_AND_THIRD_CONJUNCT_SAMPLE)
        self.assertNotIn("Re-judgment under the owning rule", sample)


class TestAC5RescopeReplacementGrantsOnlyPermittedActions(unittest.TestCase):
    """AC-5: the re-scope replacement states that the failed task's id is
    carried verbatim, that new tasks are added above the high-water mark,
    cites 'Re-planning task-id allocation', and keeps the SPEC.md update
    path for dropping a requirement. None of its presence matchers fire on
    the pre-change sample."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read(IMPLEMENT_PHASE_PATH)))

    def test_rescope_states_id_carried_verbatim(self):
        self.assertIn("The reset failed task keeps its id", self.section)
        self.assertIn("verbatim through the re-planning pass", self.section)

    def test_rescope_states_new_tasks_above_high_water_mark(self):
        self.assertIn(
            "added as new tasks with fresh ids above the high-water mark",
            self.section,
        )

    def test_rescope_cites_replanning_allocation_section(self):
        idx = self.section.index("The reset failed task keeps its id")
        window = self.section[idx : idx + 400]
        self.assertIn("Re-planning task-id allocation", window)

    def test_rescope_keeps_spec_md_update_path(self):
        self.assertIn(
            "that change still routes through the normal SPEC.md update "
            "path first",
            self.section,
        )

    def test_rescope_matchers_absent_from_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_RESCOPE_SAMPLE)
        self.assertNotIn("The reset failed task keeps its id", sample)
        self.assertNotIn(
            "added as new tasks with fresh ids above the high-water mark",
            sample,
        )
        self.assertNotIn(
            "that change still routes through the normal SPEC.md update "
            "path first",
            sample,
        )


class TestAC6LabelRetentionAndNoRestatement(unittest.TestCase):
    """AC-6: the 'recycled-task-id carve-out' label still appears in
    implement-phase.md and in skills/develop/SKILL.md; I.2.c contains
    neither the high-water-mark expression nor an enumeration of the
    carried record's full field list, while the same matchers detect both
    in the live owning section of workflow-patch.md."""

    HIGH_WATER_MARK_EXPRESSION = "max(carried_task_ids"
    CARRIED_RECORD_FIELD_LIST_FRAGMENT = (
        "`skills`, `domains`, `complexity`, `requirements`"
    )

    @classmethod
    def setUpClass(cls):
        cls.implement_phase_text = _read(IMPLEMENT_PHASE_PATH)
        cls.i2c_section = _normalize_ws(
            _i2c_section(cls.implement_phase_text)
        )
        cls.owning_section = _normalize_ws(
            _replanning_section(_read(WORKFLOW_PATCH_PATH))
        )

    def test_carve_out_label_still_present_in_implement_phase_and_skill(self):
        self.assertIn(
            "recycled-task-id carve-out", self.implement_phase_text
        )
        self.assertIn(
            "recycled-task-id carve-out", _read(DEVELOP_SKILL_PATH)
        )

    def test_i2c_omits_high_water_mark_expression_and_full_field_list(self):
        self.assertNotIn(
            self.HIGH_WATER_MARK_EXPRESSION, self.i2c_section
        )
        self.assertNotIn(
            self.CARRIED_RECORD_FIELD_LIST_FRAGMENT, self.i2c_section
        )

    def test_same_matchers_detect_both_in_owning_section(self):
        self.assertIn(
            self.HIGH_WATER_MARK_EXPRESSION, self.owning_section
        )
        self.assertIn(
            self.CARRIED_RECORD_FIELD_LIST_FRAGMENT, self.owning_section
        )


class TestI2cStillContainsNeitherBannedToken(unittest.TestCase):
    """Regression guard shared with tests/test_implement_routeback_gate.py,
    tests/test_recycled_task_id_consistency.py and
    tests/test_routeback_reset_scope_consistency.py: this task's own
    additions must not introduce either of the two tokens I.2.c already
    excludes."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read(IMPLEMENT_PHASE_PATH)))

    def test_no_rework_or_append_in_i2c(self):
        self.assertNotIn("rework", self.section)
        self.assertNotIn("append", self.section)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """C6: this module uses the Python standard library only."""

    def test_own_imports_are_all_stdlib(self):
        import ast

        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
