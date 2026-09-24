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

task0013 (goal-vs-spec-divergence, review round 1 rework) rebuilds AC-6's
recursion-invariant reasoning: the "widened gate admits no `merged` task"
premise this task's own text relied on is no longer the only door into
re-planning (the SPEC-change transition reaches it without going through
I.2.c's gate at all), so `RECURSION_INVARIANT_PHRASE` is restated to derive
the same conclusion from `references/workflow-patch.md`'s re-planning
task-id allocation rule instead (no retired id is ever re-issued to a
different task). `TestI2aRecursionInvariantPresent` is updated in place
(name kept); the removed premise's absence is a new regression guard in
`TestRegressionGuards`, proven against a captured pre-change sample in
`TestValidationDetectsRegressions`.

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

task0001 (routeback-residual-connections) closes three connections left
unproven in Step I.2.a / Step I.2.c after PR #7: the carve-out / gate /
reconciled-state chain now has a stated end point (Site B), the route-back
reset target set covers both `failed` sources (Site C), and the cleanup's
not-merged claim is limited to what is actually read, with the undetected
residual recorded (Site D, Site E). FR1 is a pin, not an edit -- the I.2.a
premise already read `below` and named I.2.c's third conjunct; the negative
proof reuses this module's own SAMPLE_7_I2A_WIDENED_GATE_PREMISE, captured
at `b3d8824da4182071c2a5d7490925fee1aba951e1` (D3). All other new-wording
negative proofs below run against verbatim excerpts of
`em-workflow/references/implement-phase.md` captured at
`9f9502487a8da29220aece87f253058becda432e` (D4), read from the git object
store, never paraphrased. All new material (constants, samples, classes)
is additive, per this module's own C7: no pre-existing constant, test
method or class is modified.

Covers task0001 Acceptance Criteria
(feature-docs/routeback-residual-connections/tasks/task0001.md):

- AC-1 (FR1; TS-1): I.2.a names I.2.c's route-back gate as `below` in the
  journal-`merged` premise (unchanged); I.2.c states the third-conjunct
  phrase that premise refers to; no I.2.c gate/conjunct reference in I.2.a
  is followed by `above`, proven tight against the "(the widened I.2.c
  gate above)" sample without catching "the recycled-task-id carve-out
  above".
- AC-2 (FR2; TS-2): I.2.a's new chain-termination sentence, placed after
  the first "correctly scoped to `failed` only." and before "is applied by
  two parties", states the `failed`+`pending`-only reclassification, that
  the carve-out's outcome cannot change a `merged`/`launched`
  classification, that Step I.2.b step 1's classifications therefore never
  consult it, and that the carve-out/gate/reconciled-state chain
  terminates there; the premise-to-first-scoped-anchor span keeps exactly
  one "Because " and one " so ".
- AC-3 (FR3; TS-3): I.2.c's reset target set is the union of the existing
  reconciled-state-`failed` literal (leading, verbatim) and a new
  workflow.yaml-`status: failed` member; a sentence before "Commit that
  write set next, BEFORE any cleanup" cites Step I.2.b step 3 and
  `replace_all` in the same slice, without restating either rule; the
  first `tasks.{T}.status` still has `pending` within 60 characters.
- AC-4 (FR4, FR5; TS-4): the cleanup sentence's not-merged claim names only
  workflow.yaml `status` and Step I.2.b step 1's reconciled state (the
  bare "confirmed not merged" is gone); the gate above is given as the
  reason no reconciled-`merged` task is ever a cleanup target; a residual
  sentence between the leftover-state sentence and "End the phase with a"
  names merge-task.sh's `git update-ref`, the journal-write-failure window
  and the stop-without-report window, and states the residual is known and
  unclosed; `git branch -D` still occurs exactly once in I.2.c.
- AC-5 (FR6, NFR9): every new-wording literal above is one module-level
  constant read by both its positive assertion and its negative proof;
  every new excerpt is copied verbatim from its named revision with a
  non-vacuity guard on a retained anchor.

Matcher -> negative-proof inventory (D8; every new matcher this task
adds):

- test_direction_below_phrase_present -> RETENTION/pin matcher (D3), no
  proof needed
- test_third_conjunct_referent_present_in_i2c -> RETENTION/pin matcher
  (D3), no proof needed
- test_no_gate_or_conjunct_reference_followed_by_above_in_i2a -> regression
  guard -> test_absence_matcher_flags_the_pre_change_widened_gate_sample
  (reuses SAMPLE_7_I2A_WIDENED_GATE_PREMISE and its existing non-vacuity
  guard, D3)
- test_reclassify_phrase_present, test_outcome_phrase_present,
  test_never_consult_phrase_present, test_chain_terminates_phrase_present
  -> new wording ->
  test_termination_matchers_flag_absence_in_pre_change_wording
- test_causal_span_still_has_single_because_and_so -> ordering/regression
  guard, no proof needed
- test_second_reset_member_present_and_follows_first ->
  test_reset_union_matchers_flag_absence_in_pre_change_wording
- test_diverge_sentence_present, test_step_i2b_step3_owner_citation_present,
  test_citation_and_replace_all_share_one_sentence -> new wording -> same
  proof above
- test_first_tasks_status_has_pending_within_60_chars -> ordering guard, no
  proof needed
- test_source_qualified_not_merged_phrase_present,
  test_bare_confirmed_not_merged_absent -> new wording / regression guard
  -> test_cleanup_matchers_flag_the_pre_change_wording
- test_gate_reason_phrase_present -> new wording -> same proof above
- test_retained_cleanup_literals_survive -> RETENTION matcher, no proof
  needed
- test_residual_sentence_present_between_leftover_and_end_of_phase,
  test_residual_names_merge_task_sh_update_ref,
  test_residual_states_warning_and_stop_without_report_windows,
  test_residual_states_known_and_unclosed -> new wording -> same proof
  above (SAMPLE_9F95024_CLEANUP)
- test_git_branch_d_still_occurs_exactly_once -> regression guard, no
  proof needed

Each new pre-change excerpt's non-vacuity is guarded in
`TestTask0001PreChangeSampleGuards`, on a retained anchor present in both
the excerpt and the live document.
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

# Site 5 / AC-6 (FR6): I.2.a's recursion-invariant statement. Restated by
# task0013 (goal-vs-spec-divergence): derived from workflow-patch.md's
# re-planning task-id allocation rule (no retired id is ever re-issued to a
# different task) instead of from the widened I.2.c gate, which is no
# longer the only door into re-planning.
UNREACHABILITY_OPENING_ANCHOR = "Given I.2.c's route-back precondition"
RECURSION_INVARIANT_PHRASE = (
    "No retired task id is ever re-issued, so a task whose workflow.yaml "
    "`status` is `pending` can never carry an inherited `merged` journal "
    "last event"
)

# task0013's own removed premise (the widened-gate-based reasoning this
# task's edit replaces) -- must not resurface.
OLD_RENUMBERING_PREMISE_PHRASE = (
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

# task0013 (goal-vs-spec-divergence): the widened-gate-based premise this
# task's edit replaces, captured verbatim from this task's own base commit
# (immediately before this task's edit landed) -- not paraphrased, not
# reconstructed.
SAMPLE_7_I2A_WIDENED_GATE_PREMISE = (
    "Because route-back proceeds only when no task is `merged` under\n"
    "either source (the widened I.2.c gate above), no retired task id can\n"
    "leave a `merged` last event behind for a renumbered task to inherit, "
    "so\n"
    "the recycled-task-id carve-out above stays correctly scoped to "
    "`failed`\n"
    "only."
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
    restated by task0013 (goal-vs-spec-divergence) as: no retired task id
    is ever re-issued, so a `pending` task can never carry an inherited
    `merged` journal last event -- placed after the unreachability
    terminal; the carve-out and the retained in-flight sentence stay
    intact; the superseded widened-gate premise does not resurface."""

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

    def test_old_renumbering_premise_absent(self):
        # task0013: the widened-gate-based premise this task's edit
        # replaces must not resurface anywhere in I.2.a.
        self.assertNotIn(OLD_RENUMBERING_PREMISE_PHRASE, self.i2a)


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
        # Brought to the post-change text by implement-failed-kind/task0002:
        # the batch second-failure abort now writes `failed_kind` valued
        # `decision` unconditionally, including the orphaned-origin case,
        # and cites `references/batch-terminal-line.md` for why the run's
        # stop is unaffected.
        pre_change_batch_mode_paragraph = (
            "Batch mode (`references/batch-mode.md`'s Non-packet gates "
            "table,\n"
            "`implement.failed-task`): no AskUserQuestion —\n"
            "after the drain, auto-select **retry** ONCE per task (kept "
            "worktree, I.2.a\n"
            "resume guard). A task that fails a second time → **abort "
            "phase**: refresh\n"
            "the integration worktree, capture the tip, then set and "
            "commit the\n"
            "`implement` step's `status` to `failed`, together with "
            "`failed_kind`\n"
            "valued `decision` unconditionally — including when the "
            "failure\n"
            "originates from a journal `failed` event whose reason is "
            "`orphaned`,\n"
            "overriding the abort-phase option's rule above for this "
            "entrance — via\n"
            "`commit-docs.sh` (no `create-plan` `needs_update`, no task "
            "status or\n"
            "notes write set, no worktree or branch cleanup — the "
            "terminal status\n"
            "write and its own commit are the ONLY side effect), then "
            "report and\n"
            "stop; control returns via develop's stop condition 3, firing "
            "on the next\n"
            "Step B iteration reading `implement: failed` — unaffected by "
            "this\n"
            "override, since `references/batch-terminal-line.md` already "
            "gives\n"
            "`implement-second-failure` precedence over "
            "`stop-condition-3`. The\n"
            "external service cuts a follow-up task. "
            "Route-back-to-planning is never\n"
            "taken automatically. Track the retry-consumed state per "
            "task in\n"
            "`tasks.{T}.notes`.\n"
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

    def test_old_renumbering_premise_matcher_flags_pre_change_wording(self):
        # task0013: proves the new absence guard is not vacuous -- the
        # phrase it looks for genuinely appeared in this task's own base
        # commit.
        sample = _normalize_ws(SAMPLE_7_I2A_WIDENED_GATE_PREMISE)
        self.assertIn(OLD_RENUMBERING_PREMISE_PHRASE, sample)

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

    def test_sample7_retains_carve_out_scoped_anchor(self):
        sample = _normalize_ws(SAMPLE_7_I2A_WIDENED_GATE_PREMISE)
        self.assertIn(
            "the recycled-task-id carve-out above stays correctly scoped "
            "to `failed` only",
            sample,
        )


# =====================================================================
# task0001 (routeback-residual-connections): additive material only, per
# this module's own C7 -- no constant, test method or class above this
# line is modified. TS-1..TS-4 below map to task0001's own AC-1..AC-5
# (feature-docs/routeback-residual-connections/tasks/task0001.md).
# =====================================================================

# --- TS-1 (FR1; AC-1): I.2.a's direction wording naming I.2.c's gate as
# "below" (Site A -- a pin, not an edit: D3), and I.2.c's own third-conjunct
# phrase that premise refers to. The negative proof reuses this module's
# own SAMPLE_7_I2A_WIDENED_GATE_PREMISE and its existing non-vacuity guard
# above (D3) -- no new pre-change sample is captured for this pin.
DIRECTION_BELOW_PHRASE = "Step I.2.c's route-back gate below"
THIRD_CONJUNCT_MERGED_BLOCK_PHRASE = (
    "the last-event-per-task replay alone reports any task's journal "
    "last event as `merged`, route-back is inadmissible"
)
# Tight absence matcher (Design note): must catch a direct "gate"/"conjunct"
# ... "above" reference (e.g. "(the widened I.2.c gate above)") without
# catching "the recycled-task-id carve-out above", which I.2.a legitimately
# says (including in task0001's own new Site B sentence below). Bounded to
# 60 characters and never crosses a sentence boundary ("." acts as a hard
# stop), so a "gate"/"conjunct" occurrence followed, later in the SAME
# sentence, by an unrelated "... carve-out above" in the NEXT sentence can
# never be caught.
GATE_OR_CONJUNCT_FOLLOWED_BY_ABOVE_RE = re.compile(
    r"\b(?:gate|conjunct)\b(?:(?!\.)[\s\S]){0,60}\babove\b"
)

# --- TS-2 (FR2; AC-2): I.2.a's new chain-termination sentence (Site B),
# inserted after the first "correctly scoped to `failed` only." and before
# "is applied by two parties". Negative proof: a verbatim excerpt of
# `implement-phase.md` at 9f9502487a8da29220aece87f253058becda432e, from
# the journal-`merged` premise through the start of the two-parties
# sentence (D4).
CARVE_OUT_SCOPED_ANCHOR = "correctly scoped to `failed` only."
TWO_PARTIES_OPENING_ANCHOR = "is applied by two parties"
TERMINATION_RECLASSIFY_PHRASE = (
    "The carve-out reclassifies only a task whose journal last event is "
    "`failed` and whose workflow.yaml `status` is `pending`"
)
TERMINATION_OUTCOME_PHRASE = (
    "its outcome cannot change a `merged` or a `launched` classification"
)
TERMINATION_NEVER_CONSULT_PHRASE = (
    "Step I.2.b step 1's `merged` and in-flight classifications below — "
    "the inputs Step I.2.c's gate below reads — never consult it"
)
TERMINATION_CHAIN_TERMINATES_PHRASE = (
    "the carve-out / gate / reconciled-state chain terminates there"
)

SAMPLE_9F95024_I2A_TERMINATION = (
    "Because Step I.2.c's route-back gate below blocks route-back\n"
    "whenever any task's journal last event is `merged` — read from the\n"
    "journal directly, independent of the ancestor check — that gate never\n"
    "admits route-back while such an event stands. No retired task id is "
    "ever\n"
    "re-issued, so a task whose workflow.yaml `status` is `pending` can "
    "never\n"
    "carry an inherited `merged` journal last event; the recycled-task-id\n"
    "carve-out above stays correctly scoped to `failed` only. The\n"
    "recycled-task-id carve-out above is applied by two parties:"
)

# --- TS-3 (FR3; AC-3): I.2.c's reset-target-set union and its connecting
# sentence (Site C). Negative proof: a verbatim excerpt of
# `implement-phase.md` at 9f9502487a8da29220aece87f253058becda432e, from
# "then make one ordered workflow.yaml write set" through the `replace_all`
# citation (D4).
SECOND_RESET_MEMBER_PHRASE = (
    "every task that workflow.yaml reports as `status: failed`"
)
DIVERGE_SENTENCE_OPENING_PHRASE = "The two members can diverge"
STEP_I2B_STEP3_OWNER_CITATION_PHRASE = (
    "Step I.2.b step 3 owns workflow.yaml's own `failed` write, cited "
    "here not restated"
)

SAMPLE_9F95024_WRITE_SET = (
    "  then make one ordered workflow.yaml write set over the reset "
    "target\n"
    "  set — every task whose Step I.2.b step 1 reconciled state is\n"
    "  `failed`: set `create-plan` to `needs_update`, set the `implement`\n"
    "  step back to `pending`, clear `failed_kind`\n"
    "  (`references/workflow-schema.md`) back to null in that same write "
    "set —\n"
    "  re-asserting the null value Step I.1's phase-start write already "
    "set on\n"
    "  this entry, so this adds no extra write and no extra commit — "
    "record\n"
    "  each such task's failure reason (the implementer's report "
    "`notes`) in\n"
    "  `tasks.{T}.notes`, and set `tasks.{T}.status` back to `pending` "
    "for\n"
    "  every task in that set — the\n"
    "  gate above already established that no task is `merged` or\n"
    "  `in_progress` at this point, so the result is that no task is "
    "left\n"
    "  `merged` or `in_progress` or `failed`, which is exactly what "
    "makes the\n"
    "  planner's `replace_planning` operation admissible on re-entry\n"
    "  (`references/workflow-patch.md`'s `replace_all` permission\n"
    "  conditions own the full condition set and the protocol-error "
    "rule —\n"
    "  not restated here)."
)

# --- TS-4 (FR4, FR5; AC-4): I.2.c's source-qualified cleanup claim, gate-
# reason sentence (Site D) and the residual sentence (Site E). Negative
# proof: a verbatim excerpt of `implement-phase.md` at
# 9f9502487a8da29220aece87f253058becda432e, from "Only once that commit"
# through "already cover." (D4).
SOURCE_QUALIFIED_NOT_MERGED_PHRASE = (
    "neither workflow.yaml `status` nor Step I.2.b step 1's reconciled "
    "state reports any of these tasks `merged`"
)
GATE_REASON_PHRASE = (
    "the gate above already refused route-back whenever such a task "
    "exists, so the set just reset contains none"
)
RESIDUAL_MERGE_TASK_SH_UPDATE_REF_PHRASE = "merge-task.sh's `git update-ref`"
RESIDUAL_OPENING_PHRASE = "is invisible to both sources above"
RESIDUAL_WARNING_EXIT0_PHRASE = (
    "reported only as a warning, with the script still exiting 0"
)
RESIDUAL_STOP_WITHOUT_REPORT_PHRASE = (
    "stops between the ref update and the journal write and leaves no "
    "report"
)
RESIDUAL_KNOWN_RESIDUAL_PHRASE = "a known residual this gate does not close"
OLD_CONFIRMED_NOT_MERGED_PHRASE = "confirmed not merged"

SAMPLE_9F95024_CLEANUP = (
    "  no worktree or branch has been deleted). Only once that commit\n"
    "  succeeds, clean up worktrees and branches for exactly the tasks "
    "the\n"
    "  write set just reset — confirmed not merged; a task whose "
    "reconciled\n"
    "  state is `merged` is never a cleanup target, whatever "
    "workflow.yaml\n"
    "  says (`git worktree remove --force\n"
    '  "$WT_ROOT/{T}"`; `git branch -D "em-workflow/{feature}/{T}"`, for\n'
    "  every {T} just reset) — this order's one residual leftover state "
    "is the\n"
    "  commit succeeding and the cleanup not yet running, i.e. stale\n"
    "  worktrees for tasks now `pending`, which Step I.2.a's resume "
    "guard and\n"
    "  its recycled-task-id rule already cover."
)


class TestTask0001I2aGateDirectionIsPinnedBelow(unittest.TestCase):
    """AC-1 / FR1 (TS-1): I.2.a's premise names I.2.c's route-back gate as
    `below` (a pin, not an edit: D3); I.2.c's own third conjunct states the
    journal-`merged` block that premise refers to; no I.2.c gate/conjunct
    reference in normalized I.2.a is followed by `above`."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.i2a = _normalize_ws(_i2a_section(text))
        cls.i2c = _normalize_ws(_i2c_section(text))

    def test_direction_below_phrase_present(self):
        self.assertIn(DIRECTION_BELOW_PHRASE, self.i2a)

    def test_third_conjunct_referent_present_in_i2c(self):
        self.assertIn(THIRD_CONJUNCT_MERGED_BLOCK_PHRASE, self.i2c)

    def test_no_gate_or_conjunct_reference_followed_by_above_in_i2a(self):
        self.assertIsNone(GATE_OR_CONJUNCT_FOLLOWED_BY_ABOVE_RE.search(self.i2a))

    def test_absence_matcher_flags_the_pre_change_widened_gate_sample(self):
        # Reuses this module's own SAMPLE_7_I2A_WIDENED_GATE_PREMISE (D3)
        # and its existing non-vacuity guard
        # (test_sample7_retains_carve_out_scoped_anchor above) -- no new
        # sample is captured for this pin.
        sample = _normalize_ws(SAMPLE_7_I2A_WIDENED_GATE_PREMISE)
        self.assertIsNotNone(GATE_OR_CONJUNCT_FOLLOWED_BY_ABOVE_RE.search(sample))
        self.assertNotIn(DIRECTION_BELOW_PHRASE, sample)


class TestTask0001I2aChainTerminationSentence(unittest.TestCase):
    """AC-2 / FR2 (TS-2, Site B): the new sentence -- placed after the
    first "correctly scoped to `failed` only." and before "is applied by
    two parties" -- states the `failed`+`pending`-only reclassification,
    that the carve-out's outcome cannot change a `merged`/`launched`
    classification, that Step I.2.b step 1's classifications therefore
    never consult it, and that the chain terminates there; the
    premise-to-scoped-anchor span keeps a single causal construction."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))
        start = cls.i2a.index(CARVE_OUT_SCOPED_ANCHOR) + len(
            CARVE_OUT_SCOPED_ANCHOR
        )
        end = cls.i2a.index(TWO_PARTIES_OPENING_ANCHOR, start)
        cls.slice_ = cls.i2a[start:end]

    def test_reclassify_phrase_present(self):
        self.assertIn(TERMINATION_RECLASSIFY_PHRASE, self.slice_)

    def test_outcome_phrase_present(self):
        self.assertIn(TERMINATION_OUTCOME_PHRASE, self.slice_)

    def test_never_consult_phrase_present(self):
        self.assertIn(TERMINATION_NEVER_CONSULT_PHRASE, self.slice_)

    def test_chain_terminates_phrase_present(self):
        self.assertIn(TERMINATION_CHAIN_TERMINATES_PHRASE, self.slice_)

    def test_causal_span_still_has_single_because_and_so(self):
        start = self.i2a.index("Because " + DIRECTION_BELOW_PHRASE)
        end = self.i2a.index(CARVE_OUT_SCOPED_ANCHOR, start) + len(
            CARVE_OUT_SCOPED_ANCHOR
        )
        span = self.i2a[start:end]
        self.assertEqual(span.count("Because "), 1)
        self.assertEqual(span.count(" so "), 1)


class TestTask0001I2cResetTargetIsUnionOfBothMembers(unittest.TestCase):
    """AC-3 / FR3 (TS-3, Site C): the reset target set names the existing
    reconciled-state-`failed` literal (leading, verbatim, RESET_TARGET_PHRASE
    above) and a new workflow.yaml-`status: failed` member; the connecting
    sentence cites Step I.2.b step 3 and `replace_all` in the same
    sentence; the first `tasks.{T}.status` still has `pending` within 60
    characters."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_second_reset_member_present_and_follows_first(self):
        first_idx = self.section.index(RESET_TARGET_PHRASE)
        second_idx = self.section.index(SECOND_RESET_MEMBER_PHRASE)
        self.assertLess(first_idx, second_idx)

    def test_diverge_sentence_present(self):
        self.assertIn(DIVERGE_SENTENCE_OPENING_PHRASE, self.section)

    def test_step_i2b_step3_owner_citation_present(self):
        self.assertIn(STEP_I2B_STEP3_OWNER_CITATION_PHRASE, self.section)

    def test_citation_and_replace_all_share_one_sentence(self):
        # "replace_all" already occurs elsewhere in I.2.c (the write-set's
        # own permission-conditions citation), so a whole-section presence
        # check proves nothing -- slice to the connecting sentence itself.
        start = self.section.index(DIVERGE_SENTENCE_OPENING_PHRASE)
        end = self.section.index(
            "Commit that write set next, BEFORE any cleanup", start
        )
        sentence = self.section[start:end]
        self.assertIn(STEP_I2B_STEP3_OWNER_CITATION_PHRASE, sentence)
        self.assertIn("replace_all", sentence)

    def test_diverge_sentence_precedes_commit(self):
        diverge_idx = self.section.index(DIVERGE_SENTENCE_OPENING_PHRASE)
        commit_idx = self.section.index(
            "Commit that write set next, BEFORE any cleanup"
        )
        self.assertLess(diverge_idx, commit_idx)

    def test_first_tasks_status_has_pending_within_60_chars(self):
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx : idx + 60]
        self.assertIn("pending", window)


class TestTask0001I2cCleanupIsSourceQualified(unittest.TestCase):
    """AC-4 / FR4, first part of FR5 (TS-4, Site D): the not-merged claim
    names only workflow.yaml `status` and Step I.2.b step 1's reconciled
    state; the bare "confirmed not merged" is gone; the gate above is
    given as the reason no reconciled-`merged` task is ever a cleanup
    target; the retained cleanup literals survive verbatim; `git branch -D`
    still occurs exactly once in I.2.c."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_source_qualified_not_merged_phrase_present(self):
        self.assertIn(SOURCE_QUALIFIED_NOT_MERGED_PHRASE, self.section)

    def test_bare_confirmed_not_merged_absent(self):
        self.assertNotIn(OLD_CONFIRMED_NOT_MERGED_PHRASE, self.section)

    def test_gate_reason_phrase_present(self):
        self.assertIn(GATE_REASON_PHRASE, self.section)

    def test_gate_reason_sits_inside_cleanup_sentence_slice(self):
        start = self.section.index("Only once that commit")
        end = self.section.index(
            "this order's one residual leftover state"
        )
        slice_ = self.section[start:end]
        self.assertIn(GATE_REASON_PHRASE, slice_)
        self.assertIn(SOURCE_QUALIFIED_NOT_MERGED_PHRASE, slice_)

    def test_retained_cleanup_literals_survive(self):
        self.assertIn(CLEANUP_TARGET_SCOPE_PHRASE, self.section)
        self.assertIn(CLEANUP_CONFIRMED_NOT_MERGED_PHRASE, self.section)

    def test_git_branch_d_still_occurs_exactly_once(self):
        occurrences = [
            m.start()
            for m in re.finditer(re.escape("git branch -D"), self.section)
        ]
        self.assertEqual(len(occurrences), 1)


class TestTask0001I2cResidualSentence(unittest.TestCase):
    """AC-4 / second part of FR5 (TS-4, Site E): the residual sentence sits
    between the leftover-state sentence and "End the phase with a", names
    merge-task.sh's `git update-ref`, the journal-write-failure window
    (warning, exit 0) and the stop-without-report window, and states the
    residual is known and unclosed, verifying nothing and changing no
    behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))
        start = cls.section.index(
            "this order's one residual leftover state"
        )
        end = cls.section.index("End the phase with a", start)
        cls.slice_ = cls.section[start:end]

    def test_residual_sentence_present_between_leftover_and_end_of_phase(self):
        self.assertIn(RESIDUAL_OPENING_PHRASE, self.slice_)

    def test_residual_names_merge_task_sh_update_ref(self):
        self.assertIn(RESIDUAL_MERGE_TASK_SH_UPDATE_REF_PHRASE, self.slice_)

    def test_residual_states_warning_and_stop_without_report_windows(self):
        self.assertIn(RESIDUAL_WARNING_EXIT0_PHRASE, self.slice_)
        self.assertIn(RESIDUAL_STOP_WITHOUT_REPORT_PHRASE, self.slice_)

    def test_residual_states_known_and_unclosed(self):
        self.assertIn(RESIDUAL_KNOWN_RESIDUAL_PHRASE, self.slice_)

    def test_residual_contains_neither_append_nor_rework(self):
        self.assertNotIn("append", self.slice_)
        self.assertNotIn("rework", self.slice_)

    def test_residual_contains_no_literal_git_branch_dash_d(self):
        self.assertNotIn("git branch -D", self.slice_)


class TestTask0001ValidationDetectsRegressions(unittest.TestCase):
    """D8 / AC-5: proof that every new-wording matcher above fails
    meaningfully -- demonstrated against captured pre-change wording
    samples, each normalized by this module's own helper."""

    def test_termination_matchers_flag_absence_in_pre_change_wording(self):
        sample = _normalize_ws(SAMPLE_9F95024_I2A_TERMINATION)
        self.assertNotIn(TERMINATION_RECLASSIFY_PHRASE, sample)
        self.assertNotIn(TERMINATION_OUTCOME_PHRASE, sample)
        self.assertNotIn(TERMINATION_NEVER_CONSULT_PHRASE, sample)
        self.assertNotIn(TERMINATION_CHAIN_TERMINATES_PHRASE, sample)

    def test_reset_union_matchers_flag_absence_in_pre_change_wording(self):
        sample = _normalize_ws(SAMPLE_9F95024_WRITE_SET)
        self.assertNotIn(SECOND_RESET_MEMBER_PHRASE, sample)
        self.assertNotIn(DIVERGE_SENTENCE_OPENING_PHRASE, sample)
        self.assertNotIn(STEP_I2B_STEP3_OWNER_CITATION_PHRASE, sample)

    def test_cleanup_matchers_flag_the_pre_change_wording(self):
        sample = _normalize_ws(SAMPLE_9F95024_CLEANUP)
        self.assertIn(OLD_CONFIRMED_NOT_MERGED_PHRASE, sample)
        self.assertNotIn(SOURCE_QUALIFIED_NOT_MERGED_PHRASE, sample)
        self.assertNotIn(GATE_REASON_PHRASE, sample)
        self.assertNotIn(RESIDUAL_OPENING_PHRASE, sample)
        self.assertNotIn(RESIDUAL_MERGE_TASK_SH_UPDATE_REF_PHRASE, sample)
        self.assertNotIn(RESIDUAL_KNOWN_RESIDUAL_PHRASE, sample)


class TestTask0001PreChangeSampleGuards(unittest.TestCase):
    """D8 point 3: each new pre-change sample carries a RETAINED anchor --
    present in both the sample and the live document -- so the negative
    proofs above cannot silently degrade into a tautology."""

    def test_termination_sample_retains_carve_out_scoped_anchor(self):
        sample = _normalize_ws(SAMPLE_9F95024_I2A_TERMINATION)
        self.assertIn(CARVE_OUT_SCOPED_ANCHOR, sample)

    def test_write_set_sample_retains_create_plan_anchor(self):
        sample = _normalize_ws(SAMPLE_9F95024_WRITE_SET)
        self.assertIn("`create-plan` to `needs_update`", sample)

    def test_cleanup_sample_retains_just_reset_anchor(self):
        sample = _normalize_ws(SAMPLE_9F95024_CLEANUP)
        self.assertIn("every {T} just reset", sample)


if __name__ == "__main__":
    unittest.main()
