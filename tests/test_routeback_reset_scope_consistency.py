"""Tests for task0001 (routeback-reset-scope-consistency): making Step
I.2.c's route-back derive its admissibility gate, its workflow.yaml write
set and its worktree/branch cleanup from one source -- Step I.2.b step 1's
reconciled state -- in `em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/routeback-reset-scope-consistency/tasks/task0001.md):

- AC-1 (FR1): the gate's `merged` conjunct is stated as a union of
  workflow.yaml status and Step I.2.b step 1's reconciled state (ancestor-
  verified), citing I.2.b as owner without restating it; the retained
  literal "no task has status `merged`" survives and stays sentence-joined
  with "no task has status `in_progress`".
- AC-2 (FR2): the write set's reset target is expressed in reconciled-state
  terms; the pre-change workflow.yaml-status-only phrasing is absent; the
  four write instructions survive and precede cleanup; the first
  `tasks.{T}.status` still has `pending` within 60 normalized characters.
- AC-3 (FR3): the cleanup sentence names its targets as exactly the tasks
  the write set just reset and states they are confirmed not merged;
  `git branch -D` occurs exactly once in the I.2.c section and only inside
  that sentence; ordering and the leftover-state sentence survive.
- AC-4 (FR4, NFR4): the rejected branch enumerates the reconciled-state-
  `merged` blocker alongside the existing ones; its single terminal and
  containment survive.
- AC-5 (FR5): the Branch & Worktree Model's exit-4 union-rule sentence
  names the `in_progress` union specifically; the I.2.a unreachability
  sentence stays present and true.
- AC-6 (FR6): I.2.a states the recursion invariant (no retired id can carry
  a `merged` last event under the widened gate), placed after the
  unreachability terminal, with the carve-out and in-flight sentence intact.
- AC-7 (NFR1..NFR6, NFR8): regression guards -- byte-identical heading and
  batch-mode tail, the three protected raw line-wrap literals, the four
  normalized I.2.c orderings, retained gate literals, and the whole-file
  bare-git-line invariant.
- AC-8 (FR7, NFR7): this module exists, is discovered by
  `python3 -m unittest discover -s tests`, uses only the standard library,
  and gives every new-wording matcher a negative proof plus a non-vacuity
  guard, per IMPLEMENTATION.md D8.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import from, and does not modify, any other test module; literals it
needs from a protected module (the batch-mode paragraph) are copied into it
as their own constants, per the task plan.

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
byte-identity and line-wrap-survival assertions compare the raw,
un-normalized text -- mixing the two is the known source of both false
passes and false failures in this suite (Test Notes).

Matcher -> negative-proof inventory (D8; every matcher in this module):

- test_merged_union_opening_present -> new wording ->
  test_merged_union_opening_anchor_matcher_flags_absence_in_pre_change_wording
- test_merged_union_names_workflow_yaml_source -> new wording -> same proof
  above (slice cannot be formed without the opening anchor)
- test_merged_union_names_reconciled_state_source -> new wording -> same
  proof above
- test_merged_union_states_ancestor_verification -> new wording -> same
  proof above
- test_merged_union_cites_step_i2b_without_restating -> new wording (the
  literal itself pre-exists for the `in_progress` half, so the proof is the
  anchored-slice-cannot-be-formed pattern, not a bare absence check) -> same
  proof above
- test_retained_merged_literal_survives -> RETENTION matcher, no proof
  needed
- test_retained_in_progress_literal_survives -> RETENTION matcher, no proof
  needed
- test_merged_and_in_progress_literals_joined_without_sentence_break ->
  regression/ordering guard over retained literals, no proof needed
- test_reset_target_phrase_present -> new wording ->
  test_reset_target_phrase_matcher_flags_absence_in_pre_change_wording
- test_old_workflow_status_only_reset_phrase_absent -> regression guard
  (absence of pre-change wording) ->
  test_old_reset_phrase_matcher_flags_the_pre_change_wording
- test_four_write_instructions_survive_and_precede_cleanup -> RETENTION +
  ordering guard, no proof needed
- test_first_tasks_status_has_pending_within_60_chars -> ordering guard, no
  proof needed
- test_cleanup_scope_phrase_present -> new wording ->
  test_cleanup_phrases_matcher_flags_absence_in_pre_change_wording
- test_cleanup_confirmed_not_merged_phrase_present -> new wording -> same
  proof above
- test_git_branch_d_occurs_exactly_once_and_within_cleanup_sentence ->
  regression/ordering guard over a retained literal, no proof needed
- test_commit_docs_precedes_cleanup_precedes_end_of_phase -> ordering guard,
  no proof needed
- test_leftover_state_sentence_survives -> RETENTION matcher, no proof
  needed
- test_rejected_merged_reconciled_phrase_present -> new wording ->
  test_rejected_merged_reconciled_phrase_matcher_flags_absence_in_pre_change_wording
- test_existing_blockers_still_enumerated -> RETENTION matcher, no proof
  needed
- test_rejected_terminal_unchanged -> RETENTION matcher, no proof needed
- test_containment_after_gate_rejects -> regression guard (pre-existing
  containment property), no proof needed
- test_no_rework_or_append_in_i2c -> regression guard, no proof needed
- test_in_progress_union_rule_named_phrase_present -> new wording ->
  test_in_progress_union_rule_named_phrase_matcher_flags_absence_in_pre_change_wording
- test_rest_of_exit4_bullet_unchanged -> RETENTION matcher, no proof needed
- test_i2a_unreachability_sentence_present_and_terminates_correctly ->
  RETENTION matcher (sentence unchanged by this task's edit), no proof
  needed
- test_recursion_invariant_phrase_present -> new wording ->
  test_recursion_invariant_phrase_matcher_flags_absence_in_pre_change_wording
- test_recursion_invariant_placed_after_unreachability_terminal ->
  derivative ordering check on the same literal proven above, no separate
  proof needed
- test_carve_out_still_scoped_to_failed_only -> RETENTION matcher, no proof
  needed
- test_retained_in_flight_sentence_survives -> RETENTION matcher, no proof
  needed
- TestRegressionGuards.* (TS-7) -> regression guards over pre-existing
  literals, orderings and the whole-file invariant, no proof needed

Every negative proof above runs against a captured pre-change sample -- a
verbatim excerpt of `em-workflow/references/implement-phase.md` at this
feature's implement base commit
(`b3d8824da4182071c2a5d7490925fee1aba951e1`), copied (not paraphrased) the
same way the protected modules' pre-change samples were captured -- and
each sample's non-vacuity is guarded in `TestPreChangeSampleGuards` (D8
point 3).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"
BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model"
STEP_I0_HEADING = "## Step I.0"

# --- D8: module-level constants for every matcher asserting NEW post-change
# wording. Each constant is read by both its positive test and its
# negative-proof test below -- the literal is never spelled twice.

# Site 1 / AC-1 (FR1): the `merged` conjunct's two-source union.
MERGED_UNION_OPENING_ANCHOR = (
    "The `merged` half is likewise a union of two independent sources"
)
INPROGRESS_HALF_OPENING_ANCHOR = (
    "The `in_progress` half is a union of two independent sources"
)
MERGED_UNION_WORKFLOW_SOURCE = "workflow.yaml reporting a task `merged`"
MERGED_UNION_RECONCILED_SOURCE = (
    "Step I.2.b step 1's reconciled state reporting a task `merged`"
)
MERGED_UNION_ANCESTOR_VERIFICATION_PHRASE = (
    "verified by `git merge-base --is-ancestor` as that step already requires"
)
MERGED_UNION_CITATION_PHRASE = "cited here as the owning rule, not restated"
RETAINED_MERGED_LITERAL = "no task has status `merged`"
RETAINED_IN_PROGRESS_LITERAL = "no task has status `in_progress`"

# Site 2 / AC-2 (FR2): the write set's reset target set.
RESET_TARGET_PHRASE = (
    "every task whose Step I.2.b step 1 reconciled state is `failed`"
)
OLD_WRITE_SET_RESET_PHRASE = (
    "**every** failed task's `tasks.{T}.status` back to `pending`"
)

# Site 3 / AC-3 (FR3): the cleanup sentence's confirmed-not-merged scoping.
CLEANUP_TARGET_SCOPE_PHRASE = (
    "clean up worktrees and branches for exactly the tasks the write set "
    "just reset"
)
CLEANUP_CONFIRMED_NOT_MERGED_PHRASE = (
    "a task whose reconciled state is `merged` is never a cleanup target, "
    "whatever workflow.yaml says"
)

# Site 4 / AC-4 (FR4): the rejected branch's new enumerated blocker.
REJECTED_PATH_MARKER = "When the gate does not hold"
REJECTED_MERGED_RECONCILED_PHRASE = (
    "Step I.2.b step 1's reconciled state reports a task `merged` though "
    "workflow.yaml does not"
)

# Site 5 / AC-6 (FR6): I.2.a's recursion-invariant statement.
UNREACHABILITY_OPENING_ANCHOR = "Given I.2.c's route-back precondition"
RECURSION_INVARIANT_PHRASE = (
    "no retired task id can leave a `merged` last event behind for a "
    "renumbered task to inherit"
)

# Site 6 / AC-5 (FR5): the exit-4 bullet naming which union it invokes.
IN_PROGRESS_UNION_RULE_NAMED_PHRASE = (
    "The widened I.2.c gate's `in_progress` union rule"
)

# Retained gate literals (NFR5) -- TS-7 regression guard.
RETAINED_GATE_LITERALS = (
    "re-read from workflow.yaml task statuses",
    "not inferred from the drain above",
    "a union of two independent sources",
    "terminal journal last event (`merged` or `failed`)",
)

# --- D8 point 2: pre-change wording samples, one per group, each a verbatim
# excerpt of em-workflow/references/implement-phase.md at this feature's
# implement base commit b3d8824da4182071c2a5d7490925fee1aba951e1. Captured
# BEFORE this task's edit landed -- not paraphrased, not reconstructed.

SAMPLE_1_GATE_MERGED_CONJUNCT = (
    "This automatic re-entry applies only when the gate holds: no task\n"
    "  has status `merged`, and no task has status `in_progress` — both\n"
    "  re-read from workflow.yaml task statuses at this point, as an\n"
    "  independent check, not inferred from the drain above (which only\n"
    "  describes the normal case, not the admissibility test); a stale or\n"
    "  unretired `in_progress` entry left by a crashed implementer blocks "
    "this\n"
    "  path exactly as a `merged` task does. The `in_progress` half is a "
    "union\n"
    "  of two independent sources, either of which blocks: workflow.yaml\n"
    "  reporting a task `in_progress`, OR Step I.2.b's last-event-per-task\n"
    "  rule reporting a task in-flight (a `launched` last event, with the\n"
    "  recycled-task-id carve-out that step already defines) — cited here "
    "as\n"
    "  the owning rule, not restated."
)

SAMPLE_2_WRITE_SET_RESET_TARGET = (
    "  then make one ordered workflow.yaml write set: set `create-plan` "
    "to\n"
    "  `needs_update`, set the `implement` step back to `pending`, "
    "record\n"
    "  each failed task's failure reason (the implementer's report\n"
    "  `notes`) in `tasks.{T}.notes`, and set\n"
    "  **every** failed task's `tasks.{T}.status` back to `pending` — "
    "the\n"
    "  gate above already established that no task is `merged` or\n"
    "  `in_progress` at this point, so the result is that no task is "
    "left\n"
    "  `merged` or `in_progress` or `failed`,\n"
    "  which is exactly what makes the planner's `replace_planning`\n"
    "  operation admissible on re-entry\n"
    "  (`references/workflow-patch.md`'s `replace_all` permission\n"
    "  conditions own the full condition set and the protocol-error "
    "rule —\n"
    "  not restated here)."
)

SAMPLE_3_CLEANUP_SCOPE = (
    "Only once that commit\n"
    "  succeeds, clean up each of those failed\n"
    "  tasks' worktrees and branches (`git worktree remove --force\n"
    '  "$WT_ROOT/{T}"`; `git branch -D "em-workflow/{feature}/{T}"`, for\n'
    "  every {T} just reset) — this order's one residual leftover state "
    "is the\n"
    "  commit succeeding and the cleanup not yet running, i.e. stale\n"
    "  worktrees for tasks now `pending`, which Step I.2.a's resume "
    "guard and\n"
    "  its recycled-task-id rule already cover."
)

SAMPLE_4_REJECTED_ENUMERATION = (
    "When the gate does not hold —\n"
    "  because a task has status `merged`, because a task has status\n"
    "  `in_progress`, or because Step I.2.b's last-event-per-task rule "
    "reports\n"
    "  a task in-flight — this automatic re-entry does not apply:"
)

SAMPLE_5_I2A_RECURSION = (
    "`status: pending` combined with journal last event `launched` can "
    "never\n"
    "arise. This recycled-task-id rule governs only the orchestrator's\n"
    "interpretation of the journal:"
)

SAMPLE_6_EXIT4_UNION_RULE = (
    "The widened I.2.c gate's union rule — blocked when workflow.yaml "
    "reports\n"
    "  a task `in_progress` OR Step I.2.b's last-event-per-task rule "
    "reports a\n"
    "  task in-flight — excludes the first path: route back proceeds "
    "only when"
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _bare_git_commit_or_add_lines(text):
    """Lines that are actual shell invocations (start with `git`, ignoring
    markdown backticks/indentation) touching `commit` or `add -A` -- as
    opposed to prose that merely mentions "git commit" inside a sentence."""
    out = []
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if re.match(r"^git\s", stripped) and re.search(
            r"\b(commit\b|add -A\b)", stripped
        ):
            out.append(line.strip())
    return out


class TestI2cGateMergedConjunctIsUnion(unittest.TestCase):
    """AC-1 / FR1: the gate's `merged` conjunct is a union of workflow.yaml
    status and Step I.2.b step 1's reconciled state, either of which
    blocks, citing I.2.b as owner without restating it; the retained
    literals and their one-sentence join survive."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))
        start = cls.section.index(MERGED_UNION_OPENING_ANCHOR)
        end = cls.section.index(INPROGRESS_HALF_OPENING_ANCHOR, start)
        cls.merged_union_slice = cls.section[start:end]

    def test_merged_union_opening_present(self):
        self.assertIn(MERGED_UNION_OPENING_ANCHOR, self.section)

    def test_merged_union_names_workflow_yaml_source(self):
        self.assertIn(MERGED_UNION_WORKFLOW_SOURCE, self.merged_union_slice)

    def test_merged_union_names_reconciled_state_source(self):
        self.assertIn(
            MERGED_UNION_RECONCILED_SOURCE, self.merged_union_slice
        )

    def test_merged_union_states_ancestor_verification(self):
        self.assertIn(
            MERGED_UNION_ANCESTOR_VERIFICATION_PHRASE,
            self.merged_union_slice,
        )

    def test_merged_union_cites_step_i2b_without_restating(self):
        self.assertIn(MERGED_UNION_CITATION_PHRASE, self.merged_union_slice)

    def test_retained_merged_literal_survives(self):
        self.assertIn(RETAINED_MERGED_LITERAL, self.section)

    def test_retained_in_progress_literal_survives(self):
        self.assertIn(RETAINED_IN_PROGRESS_LITERAL, self.section)

    def test_merged_and_in_progress_literals_joined_without_sentence_break(
        self,
    ):
        idx1 = self.section.index(RETAINED_MERGED_LITERAL)
        idx2 = self.section.index(RETAINED_IN_PROGRESS_LITERAL)
        self.assertLess(idx1, idx2)
        between = self.section[idx1:idx2]
        self.assertNotIn(". ", between)


class TestI2cWriteSetResetTargetIsReconciledState(unittest.TestCase):
    """AC-2 / FR2: the write set's reset target set is expressed in
    reconciled-state terms; the pre-change workflow.yaml-status-only
    phrasing is gone; the four write instructions survive and precede
    cleanup; the first `tasks.{T}.status` still has `pending` within 60
    normalized characters."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_reset_target_phrase_present(self):
        self.assertIn(RESET_TARGET_PHRASE, self.section)

    def test_old_workflow_status_only_reset_phrase_absent(self):
        self.assertNotIn(OLD_WRITE_SET_RESET_PHRASE, self.section)

    def test_four_write_instructions_survive_and_precede_cleanup(self):
        section = self.section
        cleanup_idx = section.index("git worktree remove --force")
        for token in (
            "`create-plan` to `needs_update`",
            "`implement` step back to `pending`",
            "`tasks.{T}.status` back to `pending`",
            "`tasks.{T}.notes`",
        ):
            self.assertLess(section.index(token), cleanup_idx)

    def test_first_tasks_status_has_pending_within_60_chars(self):
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx : idx + 60]
        self.assertIn("pending", window)


class TestI2cCleanupTargetsConfirmedNotMerged(unittest.TestCase):
    """AC-3 / FR3: the cleanup sentence names its targets as exactly the
    tasks the write set just reset and states they are confirmed not
    merged; `git branch -D` occurs exactly once in the I.2.c section and
    only within that sentence; ordering and the leftover-state sentence
    survive."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_cleanup_scope_phrase_present(self):
        self.assertIn(CLEANUP_TARGET_SCOPE_PHRASE, self.section)

    def test_cleanup_confirmed_not_merged_phrase_present(self):
        self.assertIn(CLEANUP_CONFIRMED_NOT_MERGED_PHRASE, self.section)

    def test_git_branch_d_occurs_exactly_once_and_within_cleanup_sentence(
        self,
    ):
        section = self.section
        occurrences = [
            m.start() for m in re.finditer(re.escape("git branch -D"), section)
        ]
        self.assertEqual(len(occurrences), 1)
        scope_idx = section.index(CLEANUP_TARGET_SCOPE_PHRASE)
        leftover_idx = section.index(
            "this order's one residual leftover state"
        )
        self.assertLess(scope_idx, occurrences[0])
        self.assertLess(occurrences[0], leftover_idx)

    def test_commit_docs_precedes_cleanup_precedes_end_of_phase(self):
        section = self.section
        commit_idx = section.index("commit-docs.sh")
        cleanup_idx = section.index("git worktree remove --force")
        report_idx = section.index("End the phase with a")
        self.assertLess(commit_idx, cleanup_idx)
        self.assertLess(cleanup_idx, report_idx)

    def test_leftover_state_sentence_survives(self):
        self.assertIn(
            "this order's one residual leftover state is the commit "
            "succeeding and the cleanup not yet running",
            self.section,
        )


class TestI2cRejectedBranchEnumeratesReconciledMergedBlocker(
    unittest.TestCase
):
    """AC-4 / FR4, NFR4: the rejected branch additionally enumerates a task
    the reconciled state reports `merged` though workflow.yaml does not;
    the existing blockers and single terminal survive; containment holds."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))
        start = cls.section.index(REJECTED_PATH_MARKER)
        end = cls.section.index("- **abort phase**", start)
        cls.branch = cls.section[start:end]
        cls.tail = cls.section[start:]

    def test_rejected_merged_reconciled_phrase_present(self):
        self.assertIn(REJECTED_MERGED_RECONCILED_PHRASE, self.branch)

    def test_existing_blockers_still_enumerated(self):
        self.assertIn("because a task has status `merged`", self.branch)
        self.assertIn("because a task has status `in_progress`", self.branch)
        self.assertIn(
            "Step I.2.b's last-event-per-task rule reports a task "
            "in-flight",
            self.branch,
        )

    def test_rejected_terminal_unchanged(self):
        branch = self.branch
        self.assertIn("create-plan` is NOT set to `needs_update`", branch)
        self.assertIn(
            "sets the `implement` step's `status` to `failed`", branch
        )
        self.assertIn("the single write this path makes", branch)
        self.assertIn("commits exactly that write", branch)
        self.assertIn("stop condition 3", branch)

    def test_containment_after_gate_rejects(self):
        tail = self.tail
        self.assertNotIn("make one ordered workflow.yaml write set", tail)
        self.assertNotIn("git worktree remove --force", tail)
        self.assertNotIn("ROUTEBACK_TIP", tail)

    def test_no_rework_or_append_in_i2c(self):
        self.assertNotIn("rework", self.section)
        self.assertNotIn("append", self.section)


class TestCrossReferencesDescribeGateCorrectly(unittest.TestCase):
    """AC-5 / FR5: the Branch & Worktree Model's exit-4 union-rule sentence
    names the `in_progress` union specifically now that the gate has two
    unions; the rest of that bullet is unchanged; Step I.2.a's
    unreachability sentence stays present and true."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.branch_section = _normalize_ws(
            _branch_worktree_model_section(text)
        )
        cls.i2a = _normalize_ws(_i2a_section(text))

    def test_in_progress_union_rule_named_phrase_present(self):
        self.assertIn(
            IN_PROGRESS_UNION_RULE_NAMED_PHRASE, self.branch_section
        )

    def test_rest_of_exit4_bullet_unchanged(self):
        section = self.branch_section
        self.assertIn("excludes the first path", section)
        self.assertIn("no implementer of this feature can be running", section)
        self.assertIn("no concurrent ref advance can occur", section)

    def test_i2a_unreachability_sentence_present_and_terminates_correctly(
        self,
    ):
        idx = self.i2a.index(UNREACHABILITY_OPENING_ANCHOR)
        end = self.i2a.index("can never arise.", idx) + len(
            "can never arise."
        )
        sentence = self.i2a[idx:end]
        self.assertIn("replace_all", sentence)
        self.assertIn("launched", sentence)
        self.assertIn("pending", sentence)


class TestI2aRecursionInvariantPresent(unittest.TestCase):
    """AC-6 / FR6: I.2.a states that route-back's own recursion invariant --
    no retired id can carry a `merged` last event forward under the widened
    gate -- placed after the unreachability terminal; the carve-out and
    the retained in-flight sentence stay intact."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))

    def test_recursion_invariant_phrase_present(self):
        self.assertIn(RECURSION_INVARIANT_PHRASE, self.i2a)

    def test_recursion_invariant_placed_after_unreachability_terminal(self):
        idx_arise = self.i2a.index("can never arise.")
        idx_invariant = self.i2a.index(RECURSION_INVARIANT_PHRASE)
        self.assertLess(idx_arise, idx_invariant)

    def test_carve_out_still_scoped_to_failed_only(self):
        self.assertIn(
            "This carve-out is deliberately scoped to `failed` only",
            self.i2a,
        )

    def test_retained_in_flight_sentence_survives(self):
        self.assertIn(
            "A task whose journal last event is `launched` is always "
            "in-flight, regardless of workflow.yaml `status`",
            self.i2a,
        )


class TestRegressionGuards(unittest.TestCase):
    """TS-7 / NFR1-NFR6: heading and batch-mode-paragraph byte identity;
    the three protected raw line-wrap literals; retained gate literals; the
    whole-file bare-git-commit/add-A invariant."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.section = _normalize_ws(_i2c_section(cls.text))

    def test_heading_is_byte_identical(self):
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx : idx + len(I2C_HEADING)], I2C_HEADING)

    def test_batch_mode_paragraph_is_byte_identical_tail(self):
        pre_change_batch_mode_paragraph = (
            "Batch mode (`references/batch-mode.md`'s Non-packet gates "
            "table,\n"
            "`implement.failed-task`): no AskUserQuestion —\n"
            "after the drain, auto-select **retry** ONCE per task (kept "
            "worktree, I.2.a\n"
            "resume guard). A task that fails a second time → **abort "
            "phase** (implement\n"
            "stays `failed`, report and stop; the external service cuts a "
            "follow-up\n"
            "task). Route-back-to-planning is never taken automatically. "
            "Track the\n"
            "retry-consumed state per task in `tasks.{T}.notes`.\n"
            "\n"
        )
        section = _i2c_section(self.text)
        start = section.index("Batch mode (`references/batch-mode.md`")
        actual = section[start:]
        self.assertEqual(actual, pre_change_batch_mode_paragraph)

    def test_step_i0_pending_literal_survives(self):
        literal = "in `tasks` whose\n   `status == pending`"
        self.assertIn(
            literal,
            self.text,
            "Step I.0's line-wrap literal was reflowed",
        )

    def test_step_i2a_select_literal_survives(self):
        literal = (
            "`tasks.*.status`. Select\n"
            "unlaunched tasks (no journal event yet and `status != "
            "merged`, ascending"
        )
        self.assertIn(
            literal,
            self.text,
            "Step I.2.a's `Select` line-wrap literal was reflowed",
        )

    def test_step_i2b_commit_literal_survives(self):
        literal = (
            '`commit-docs.sh {integration_worktree} "docs({feature}): '
            "implement wake\n"
            '   phase reconcile" "$RECONCILE_TIP"`'
        )
        self.assertIn(
            literal,
            self.text,
            "Step I.2.b step 3's commit-docs.sh line-wrap literal was "
            "reflowed",
        )

    def test_first_tasks_status_has_pending_within_60_chars(self):
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx : idx + 60]
        self.assertIn("pending", window)

    def test_write_tokens_precede_cleanup(self):
        cleanup_idx = self.section.index("git worktree remove --force")
        for token in (
            "`create-plan` to `needs_update`",
            "`implement` step back to `pending`",
            "`tasks.{T}.status` back to `pending`",
            "`tasks.{T}.notes`",
        ):
            self.assertLess(self.section.index(token), cleanup_idx)

    def test_commit_precedes_cleanup_precedes_end_of_phase(self):
        commit_idx = self.section.index("commit-docs.sh")
        cleanup_idx = self.section.index("git worktree remove --force")
        report_idx = self.section.index("End the phase with a")
        self.assertLess(commit_idx, cleanup_idx)
        self.assertLess(cleanup_idx, report_idx)

    def test_retained_gate_literals_survive(self):
        for literal in RETAINED_GATE_LITERALS:
            self.assertIn(literal, self.section)
        terminal_idx = self.section.index(
            "terminal journal last event (`merged` or `failed`)"
        )
        create_plan_idx = self.section.index("`create-plan` to `needs_update`")
        self.assertLess(terminal_idx, create_plan_idx)

    def test_no_rework_or_append_in_i2c(self):
        self.assertNotIn("rework", self.section)
        self.assertNotIn("append", self.section)

    def test_no_bare_git_commit_or_add_lines(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")


class TestValidationDetectsRegressions(unittest.TestCase):
    """D8 / TS-8: proof that every new-wording matcher above fails
    meaningfully -- demonstrated against captured pre-change wording
    samples, each normalized by this module's own helper."""

    def test_merged_union_opening_anchor_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_1_GATE_MERGED_CONJUNCT)
        with self.assertRaises(ValueError):
            sample.index(MERGED_UNION_OPENING_ANCHOR)
        self.assertNotIn(MERGED_UNION_RECONCILED_SOURCE, sample)
        self.assertNotIn(MERGED_UNION_ANCESTOR_VERIFICATION_PHRASE, sample)

    def test_reset_target_phrase_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_2_WRITE_SET_RESET_TARGET)
        self.assertNotIn(RESET_TARGET_PHRASE, sample)

    def test_old_reset_phrase_matcher_flags_the_pre_change_wording(self):
        sample = _normalize_ws(SAMPLE_2_WRITE_SET_RESET_TARGET)
        self.assertIn(OLD_WRITE_SET_RESET_PHRASE, sample)

    def test_cleanup_phrases_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_3_CLEANUP_SCOPE)
        self.assertNotIn(CLEANUP_TARGET_SCOPE_PHRASE, sample)
        self.assertNotIn(CLEANUP_CONFIRMED_NOT_MERGED_PHRASE, sample)

    def test_rejected_merged_reconciled_phrase_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_4_REJECTED_ENUMERATION)
        self.assertNotIn(REJECTED_MERGED_RECONCILED_PHRASE, sample)

    def test_recursion_invariant_phrase_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_5_I2A_RECURSION)
        self.assertNotIn(RECURSION_INVARIANT_PHRASE, sample)

    def test_in_progress_union_rule_named_phrase_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(SAMPLE_6_EXIT4_UNION_RULE)
        self.assertNotIn(IN_PROGRESS_UNION_RULE_NAMED_PHRASE, sample)

    def test_bare_commit_line_matcher_flags_an_unlocked_commit(self):
        sample = (
            'git -C {project_root} add -A -- foo && git -C {project_root} '
            'commit -m "x"'
        )
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertTrue(lines)

    def test_bare_commit_line_matcher_ignores_prose_mentioning_commit(self):
        sample = (
            "No bare `git add`/`git commit` against the integration "
            "worktree runs outside"
        )
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertEqual(lines, [])


class TestPreChangeSampleGuards(unittest.TestCase):
    """D8 point 3 / Contract 4: each pre-change wording sample carries a
    RETAINED anchor -- a phrase present in both the sample and the
    post-change document -- asserted positively here, so a negative proof
    above cannot silently degrade into a tautology (`assertNotIn(X, "")`
    passes for every X)."""

    def test_sample1_retains_merged_gate_anchor(self):
        sample = _normalize_ws(SAMPLE_1_GATE_MERGED_CONJUNCT)
        self.assertIn(RETAINED_MERGED_LITERAL, sample)

    def test_sample2_retains_create_plan_anchor(self):
        sample = _normalize_ws(SAMPLE_2_WRITE_SET_RESET_TARGET)
        self.assertIn("`create-plan` to `needs_update`", sample)

    def test_sample3_retains_just_reset_anchor(self):
        sample = _normalize_ws(SAMPLE_3_CLEANUP_SCOPE)
        self.assertIn("every {T} just reset", sample)

    def test_sample4_retains_merged_blocker_anchor(self):
        sample = _normalize_ws(SAMPLE_4_REJECTED_ENUMERATION)
        self.assertIn("because a task has status `merged`", sample)

    def test_sample5_retains_can_never_arise_anchor(self):
        sample = _normalize_ws(SAMPLE_5_I2A_RECURSION)
        self.assertIn("can never arise.", sample)

    def test_sample6_retains_blocked_when_workflow_yaml_anchor(self):
        sample = _normalize_ws(SAMPLE_6_EXIT4_UNION_RULE)
        self.assertIn(
            "blocked when workflow.yaml reports a task `in_progress` OR "
            "Step I.2.b's last-event-per-task rule reports a task "
            "in-flight",
            sample,
        )


if __name__ == "__main__":
    unittest.main()
