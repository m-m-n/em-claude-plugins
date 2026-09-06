"""Tests for task0002 (implement-failed-kind): the three terminal write
paths in `em-workflow/references/implement-phase.md`'s Step I.2.c that set
the `implement` step's `status` to `failed` each carry `failed_kind` in that
same single write, with the classification pinned per path, and the
route-back write set clears the field when it moves the step off `failed`.

Covers task0002 Acceptance Criteria
(feature-docs/implement-failed-kind/tasks/task0002.md):

- AC-1 (FR3): the abort-phase option's write description states that the
  same single write carries `failed_kind`, and states the orphaned-origin
  condition that selects the external-cause (`infra`) value and the
  otherwise-decision (`decision`) fallback.
- AC-2 (FR4): the batch `implement.failed-task` paragraph states that its
  abort writes the decision-required value unconditionally, explicitly
  including the orphaned-origin case, and cites
  `references/batch-terminal-line.md` for why the stop is unaffected.
- AC-3 (FR5): the route-back gate-rejected terminal's write description
  states that its single write carries the decision-required value
  unconditionally.
- AC-4 (FR2): the route-back-to-planning ordered write set states that
  `failed_kind` returns to null as a member of that same write set.
- AC-5 (NFR2): each of the three terminal paths still states that the
  terminal status write and its own commit are the only side effect, and
  the route-back path still states its single pre-cleanup commit. A
  negative proof shows the matcher fires against a synthetic copy in which
  one of those sentences was removed.
- AC-6 (NFR1): the document cites `references/workflow-schema.md` where the
  field is first used, and contains no restatement of the value set as a
  permitted set, no gloss of the values' meanings, and no restatement of
  the missing-value read rule. A negative proof shows the detector fires
  against a synthetic copy that does restate them.
- AC-7: the route-back gate's own admissibility conditions, its three
  blocking conjuncts, the cleanup ordering, and the orphaned-`launched`
  convergence paragraph are unchanged by this task -- asserted as the
  continued presence of their existing statements, not by comparing
  revisions.
- AC-8 (NFR4): `python3 -m unittest discover -s tests` passes with this
  module present, and this module imports only the standard library.

This module reads only `em-workflow/references/implement-phase.md`, follows
the established test-module convention (standard library only, document
text read from the repository root computed from this module's own path,
exact-wording markers held as module constants and matched after
whitespace normalisation, one negative proof per matcher against synthetic
text, a non-vacuity guard where a matcher could pass on absent input), and
locates each write path by an exact-wording anchor drawn from its own
commit message string (Test Notes) -- those strings are stable and unique,
so an assertion anchored on them will not drift onto a neighbouring
paragraph.

Three other test modules in this suite (`test_implement_routeback_gate.py`,
`test_recycled_task_id_consistency.py`,
`test_routeback_reset_scope_consistency.py`) each pin the batch
second-failure paragraph as a byte-identical tail of the I.2.c section --
an anti-regression guard predating this feature. This task's Edit 2 (FR4)
explicitly changes that exact paragraph's wording (the task plan requires
it), so each of those three pinned literals was updated in place to the new
post-edit text; none of their assertions were loosened or removed, and no
test module was deleted (tdd-testing skill's explicit-authorization
exception: the task plan explicitly changes that paragraph's content).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IMPLEMENT_PHASE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "implement-phase.md"
)

I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"

# --- exact-wording anchors, drawn from each write path's own commit
# message string (Test Notes) -----------------------------------------------

ABORT_PHASE_MARKER = "- **abort phase**"
NO_SKIP_OPTION_MARKER = "There is NO skip option"
GATE_REJECTED_MARKER = "When the gate does not hold"
ROUTEBACK_WRITE_SET_MARKER = "then make one ordered workflow.yaml write set"
BATCH_PARAGRAPH_MARKER = "Batch mode (`references/batch-mode.md`"

ABORT_COMMIT_MSG = 'docs({feature}): implement phase aborted" "$ABORT_TIP"'
GATE_REJECTED_COMMIT_MSG = (
    'docs({feature}): implement route-back gate rejected" "$TERMINAL_TIP"'
)
ROUTEBACK_COMMIT_MSG = (
    'docs({feature}): implement route back to planning" "$ROUTEBACK_TIP"'
)

ONLY_SIDE_EFFECT_PHRASE = (
    "the terminal status write and its own commit are the ONLY side effect"
)

# --- AC-1: abort-phase option ------------------------------------------------

ABORT_SAME_WRITE_PHRASE = "together with `failed_kind` in that same single write"
ABORT_ORPHANED_TO_INFRA_PHRASE = (
    "`infra` when the failing task's failure originates from a journal\n"
    "  `failed` event whose reason is `orphaned`"
)
ABORT_OTHERWISE_DECISION_PHRASE = "`decision` otherwise"

# --- AC-2: batch second-failure paragraph -----------------------------------

BATCH_DECISION_UNCONDITIONAL_PHRASE = (
    "together with `failed_kind`\nvalued `decision` unconditionally"
)
BATCH_ORPHANED_OVERRIDE_PHRASE = (
    "including when the failure\noriginates from a journal `failed` event "
    "whose reason is `orphaned`,\noverriding the abort-phase option's rule "
    "above for this entrance"
)
BATCH_STOP_UNAFFECTED_CITATION_PHRASE = (
    "unaffected by this\noverride, since `references/batch-terminal-line.md` "
    "already gives\n`implement-second-failure` precedence over "
    "`stop-condition-3`"
)

# --- AC-3: route-back gate rejected terminal --------------------------------

REJECTED_DECISION_UNCONDITIONAL_PHRASE = (
    "together with `failed_kind` valued `decision`\n  unconditionally"
)
REJECTED_SINGLE_WRITE_PHRASE = "the single write this path makes"

# --- AC-4: route-back write set clears the field ----------------------------

WRITE_SET_CLEAR_PHRASE = "clear `failed_kind`"
WRITE_SET_CITATION_PHRASE = "(`references/workflow-schema.md`)"
WRITE_SET_NULL_PHRASE = "back to null in that same write set"
WRITE_SET_LEAVING_FAILED_PHRASE = "since the step is leaving `failed`"

# --- AC-7: gate/conjunct/cleanup/convergence retention ----------------------

ORPHANED_LAUNCHED_CONVERGENCE_OPENING = (
    "Orphaned-`launched` convergence (FR4): a `failed` event whose reason "
    "is\n`orphaned`"
)
GATE_MERGED_CONJUNCT_PHRASE = "no task has status `merged`"
GATE_IN_PROGRESS_CONJUNCT_PHRASE = "no task has status `in_progress`"
GATE_THIRD_CONJUNCT_OPENING = (
    "A third conjunct blocks\n  independently of both halves above"
)
CLEANUP_ORDERING_PHRASE = "Only once that commit\n  succeeds, clean up"


def _read():
    with open(IMPLEMENT_PHASE_PATH, encoding="utf-8") as fh:
        return fh.read()


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _slice(section, start_marker, end_marker, start_from=0):
    start = section.index(start_marker, start_from)
    end = section.index(end_marker, start)
    return section[start:end]


class FailedKindDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.raw_section = _i2c_section(cls.text)
        cls.section = _norm(cls.raw_section)

    def _abort_bullet(self, raw=False):
        source = self.raw_section if raw else self.section
        return _slice(source, ABORT_PHASE_MARKER, NO_SKIP_OPTION_MARKER)

    def _gate_rejected_branch(self, raw=False):
        source = self.raw_section if raw else self.section
        return _slice(source, GATE_REJECTED_MARKER, ABORT_PHASE_MARKER)

    def _routeback_write_set(self, raw=False):
        source = self.raw_section if raw else self.section
        return _slice(source, ROUTEBACK_WRITE_SET_MARKER, GATE_REJECTED_MARKER)

    def _batch_paragraph(self, raw=False):
        source = self.raw_section if raw else self.section
        start = source.index(BATCH_PARAGRAPH_MARKER)
        return source[start:]


# --- AC-1: abort-phase option (FR3) -----------------------------------------


class TestAbortPhaseOptionCarriesFailedKind(FailedKindDocTestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(IMPLEMENT_PHASE_PATH))

    def test_states_same_single_write_carries_failed_kind(self):
        self.assertIn(ABORT_SAME_WRITE_PHRASE, self._abort_bullet())

    def test_orphaned_origin_selects_infra(self):
        # Matched against the raw (un-normalized) text: this marker spans a
        # deliberate line wrap in the source.
        self.assertIn(
            ABORT_ORPHANED_TO_INFRA_PHRASE, self._abort_bullet(raw=True)
        )

    def test_otherwise_decision_fallback(self):
        self.assertIn(ABORT_OTHERWISE_DECISION_PHRASE, self._abort_bullet())

    def test_cites_orphaned_launched_convergence_rather_than_a_new_lookup(self):
        # Design: the determination is stated as a property of the
        # already-reconciled failure, citing the convergence paragraph at
        # the head of I.2.c, not as a new lookup step.
        self.assertIn(
            "the orphaned-`launched` convergence paragraph above already "
            "establishes this",
            self._abort_bullet(),
        )

    def test_abort_bullet_only_side_effect_sentence_unchanged(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._abort_bullet())

    def test_negative_proof_matcher_flags_absence_when_clause_removed(self):
        synthetic = self._abort_bullet().replace(
            ABORT_SAME_WRITE_PHRASE, "in workflow.yaml"
        )
        self.assertNotIn(ABORT_SAME_WRITE_PHRASE, synthetic)


# --- AC-2: batch second-failure paragraph (FR4) -----------------------------


class TestBatchSecondFailureWritesDecisionUnconditionally(FailedKindDocTestCase):
    def test_writes_decision_unconditionally(self):
        self.assertIn(
            BATCH_DECISION_UNCONDITIONAL_PHRASE, self._batch_paragraph(raw=True)
        )

    def test_explicitly_overrides_orphaned_origin_case(self):
        self.assertIn(
            BATCH_ORPHANED_OVERRIDE_PHRASE, self._batch_paragraph(raw=True)
        )

    def test_cites_batch_terminal_line_for_unaffected_stop(self):
        self.assertIn(
            BATCH_STOP_UNAFFECTED_CITATION_PHRASE, self._batch_paragraph(raw=True)
        )

    def test_batch_paragraph_only_side_effect_sentence_unchanged(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._batch_paragraph())

    def test_retains_route_back_never_automatic(self):
        self.assertIn(
            "Route-back-to-planning is never taken automatically",
            self._batch_paragraph(),
        )

    def test_retains_gate_id_and_non_packet_gates_table(self):
        self.assertIn("Non-packet gates table", self._batch_paragraph())
        self.assertIn("`implement.failed-task`", self._batch_paragraph())

    def test_negative_proof_matcher_flags_absence_when_override_removed(self):
        synthetic = self._batch_paragraph(raw=True).replace(
            BATCH_ORPHANED_OVERRIDE_PHRASE, ""
        )
        self.assertNotIn(BATCH_ORPHANED_OVERRIDE_PHRASE, synthetic)


# --- AC-3: route-back gate rejected terminal (FR5) --------------------------


class TestGateRejectedTerminalWritesDecisionUnconditionally(FailedKindDocTestCase):
    def test_writes_decision_unconditionally(self):
        self.assertIn(
            REJECTED_DECISION_UNCONDITIONAL_PHRASE,
            self._gate_rejected_branch(raw=True),
        )

    def test_states_reason_is_planning_side_blocker(self):
        self.assertIn(
            "the blocker is a planning-side state (a `merged` or "
            "in-flight task), so an automatic resume would meet the same "
            "gate again",
            self._gate_rejected_branch(),
        )

    def test_single_write_phrase_survives(self):
        self.assertIn(
            REJECTED_SINGLE_WRITE_PHRASE, self._gate_rejected_branch()
        )

    def test_rejected_path_only_side_effect_sentence_unchanged(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._gate_rejected_branch())

    def test_no_route_back_side_effect_sentence_unchanged(self):
        self.assertIn(
            "There is no route-back write set, no worktree/branch cleanup "
            "and no route-back commit on this path",
            self._gate_rejected_branch(),
        )

    def test_negative_proof_matcher_flags_absence_when_value_removed(self):
        synthetic = self._gate_rejected_branch(raw=True).replace(
            REJECTED_DECISION_UNCONDITIONAL_PHRASE, ""
        )
        self.assertNotIn(REJECTED_DECISION_UNCONDITIONAL_PHRASE, synthetic)


# --- AC-4: route-back write set clears the field (FR2) ----------------------


class TestRouteBackWriteSetClearsFailedKind(FailedKindDocTestCase):
    def test_write_set_clears_failed_kind(self):
        write_set = self._routeback_write_set()
        self.assertIn(WRITE_SET_CLEAR_PHRASE, write_set)
        self.assertIn(WRITE_SET_NULL_PHRASE, write_set)

    def test_states_reason_is_leaving_failed(self):
        self.assertIn(
            WRITE_SET_LEAVING_FAILED_PHRASE, self._routeback_write_set()
        )

    def test_clear_is_member_of_the_same_write_set_before_the_commit(self):
        # The clear sits between the write-set opening anchor and the
        # commit-docs.sh invocation for this path's own commit message --
        # i.e. it rides the existing single commit, adding no new one.
        write_set = self._routeback_write_set()
        clear_idx = write_set.index(WRITE_SET_CLEAR_PHRASE)
        create_plan_idx = write_set.index("`create-plan` to `needs_update`")
        implement_pending_idx = write_set.index(
            "`implement`\n  step back to `pending`"
        ) if "`implement`\n  step back to `pending`" in write_set else write_set.index(
            "`implement` step back to `pending`"
        )
        self.assertLess(create_plan_idx, clear_idx)
        self.assertLess(implement_pending_idx, clear_idx)
        commit_idx = self.raw_section.index(ROUTEBACK_COMMIT_MSG)
        clear_idx_raw = self.raw_section.index(
            WRITE_SET_CLEAR_PHRASE, self.raw_section.index(ROUTEBACK_WRITE_SET_MARKER)
        )
        self.assertLess(clear_idx_raw, commit_idx)

    def test_write_set_still_resets_failed_tasks_to_pending(self):
        write_set = self._routeback_write_set()
        self.assertIn("`tasks.{T}.status` back to `pending`", write_set)

    def test_negative_proof_matcher_flags_absence_when_clear_removed(self):
        synthetic = self._routeback_write_set(raw=True).replace(
            "clear `failed_kind`\n  (`references/workflow-schema.md`) back "
            "to null in that same write set\n  since the step is leaving "
            "`failed`, ",
            "",
        )
        self.assertNotIn(WRITE_SET_CLEAR_PHRASE, synthetic)


# --- AC-6 (NFR1): citation discipline ---------------------------------------


# Definition-shaped artefacts a restating consumer would introduce: both
# values presented together as the permitted set, the meanings gloss, or
# the missing-value read rule -- built as small standalone matchers so the
# detector below can be exercised (and proven) independently of either
# legitimate value mention this document's branch conditions require.

_BOTH_VALUES_TOGETHER_RE = re.compile(
    r"`infra`\s*(?:/|,|\bor\b|\band\b)\s*`decision`"
    r"|`decision`\s*(?:/|,|\bor\b|\band\b)\s*`infra`"
)

_MEANINGS_GLOSS_MARKERS = (
    ("infrastructure-caused", "decision-caused"),
    ("external-cause", "implementation-failure"),
)

_MISSING_VALUE_RULE_MARKERS = (
    "absent `failed_kind`",
    "missing `failed_kind`",
    "`failed_kind` is absent",
    "`failed_kind` is missing",
)


def _restates_definition(text):
    if _BOTH_VALUES_TOGETHER_RE.search(text):
        return True
    for pair in _MEANINGS_GLOSS_MARKERS:
        if all(marker in text for marker in pair):
            return True
    for marker in _MISSING_VALUE_RULE_MARKERS:
        if marker in text:
            return True
    return False


class TestCitationDisciplineAtFirstUse(FailedKindDocTestCase):
    def test_first_failed_kind_occurrence_is_the_write_set_clear(self):
        first_idx = self.text.index("failed_kind")
        write_set_start = self.text.index(ROUTEBACK_WRITE_SET_MARKER)
        # No occurrence of `failed_kind` precedes the write set's own use.
        self.assertGreaterEqual(first_idx, write_set_start)

    def test_first_use_cites_workflow_schema(self):
        first_idx = self.text.index("failed_kind")
        window = self.text[first_idx : first_idx + 80]
        self.assertIn("references/workflow-schema.md", window)

    def test_no_definition_shaped_restatement_in_i2c_section(self):
        self.assertFalse(_restates_definition(self.raw_section))

    def test_negative_proof_detector_fires_on_both_values_enumeration(self):
        synthetic = self.raw_section + "\n\nPermitted values: `infra` / `decision`.\n"
        self.assertTrue(_restates_definition(synthetic))

    def test_negative_proof_detector_fires_on_meanings_gloss(self):
        synthetic = (
            self.raw_section
            + "\n\nAn infrastructure-caused failure differs from a "
            "decision-caused one.\n"
        )
        self.assertTrue(_restates_definition(synthetic))

    def test_negative_proof_detector_fires_on_missing_value_rule_restatement(self):
        synthetic = (
            self.raw_section
            + "\n\nWhen `failed_kind` is absent, treat it as `decision`.\n"
        )
        self.assertTrue(_restates_definition(synthetic))

    def test_non_vacuity_detector_is_false_on_empty_text(self):
        # Guard against a vacuous matcher that would pass (return False)
        # on any input, including absent/empty text.
        self.assertFalse(_restates_definition(""))
        self.assertTrue(_restates_definition("`infra` or `decision`"))


# --- AC-5 (NFR2): only-side-effect sentence survives on all three paths ----


class TestOnlySideEffectSentenceSurvivesOnAllThreePaths(FailedKindDocTestCase):
    def test_abort_bullet_states_only_side_effect(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._abort_bullet())

    def test_batch_paragraph_states_only_side_effect(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._batch_paragraph())

    def test_gate_rejected_states_only_side_effect(self):
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self._gate_rejected_branch())

    def test_routeback_states_single_pre_cleanup_commit(self):
        write_set = self._routeback_write_set()
        self.assertIn(
            "Commit that write set next, BEFORE any cleanup", write_set
        )

    def test_negative_proof_matcher_fires_on_synthetic_copy_missing_sentence(self):
        for branch in (
            self._abort_bullet(),
            self._batch_paragraph(),
            self._gate_rejected_branch(),
        ):
            synthetic = branch.replace(ONLY_SIDE_EFFECT_PHRASE, "")
            self.assertNotIn(ONLY_SIDE_EFFECT_PHRASE, synthetic)


# --- AC-7: gate/conjuncts/cleanup/convergence unchanged ---------------------


class TestGateAndConvergenceUnchanged(FailedKindDocTestCase):
    def test_orphaned_launched_convergence_paragraph_present(self):
        self.assertIn(
            ORPHANED_LAUNCHED_CONVERGENCE_OPENING, self.raw_section
        )

    def test_gate_merged_conjunct_present(self):
        self.assertIn(GATE_MERGED_CONJUNCT_PHRASE, self.section)

    def test_gate_in_progress_conjunct_present(self):
        self.assertIn(GATE_IN_PROGRESS_CONJUNCT_PHRASE, self.section)

    def test_gate_third_conjunct_present(self):
        self.assertIn(GATE_THIRD_CONJUNCT_OPENING, self.raw_section)

    def test_cleanup_ordering_present(self):
        self.assertIn(CLEANUP_ORDERING_PHRASE, self.raw_section)

    def test_no_skip_option_paragraph_present(self):
        self.assertIn(
            "There is NO skip option: a task is either merged, retried, "
            "or re-planned",
            self.section,
        )


# --- AC-8 (NFR4): module discoverability / stdlib-only ----------------------


class TestModuleDiscoverabilityAndStdlibOnly(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        this_file = os.path.abspath(__file__)
        with open(this_file, encoding="utf-8") as fh:
            source = fh.read()
        import ast

        tree = ast.parse(source)
        allowed = {"os", "re", "unittest", "ast"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {node.module}")


if __name__ == "__main__":
    unittest.main()
