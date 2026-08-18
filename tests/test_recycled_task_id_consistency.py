"""Tests for task0001 (recycled-task-id-consistency): harmonizing the
recycled-task-id rule across its four sites and gating the I.2.c route-back
on a terminal-journal-event precondition, in
`em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/recycled-task-id-consistency/tasks/task0001.md):

- AC-1 (FR1): Step I.2.b step 3's `failed` write-back is keyed off step 1's
  reconciled state, not off the journal last event directly; the
  journal-only phrasing is gone; the `merged` half and the
  report-is-`failed`/malformed clause are unchanged.
- AC-2 (FR2): I.2.a keeps the sole normative recycled-task-id statement;
  I.2.b step 1 keeps its citation of it unchanged.
- AC-3 (FR3): the I.2.c route-back bullet gains a terminal-journal-last-
  event precondition, positioned before the ordered workflow.yaml write
  set; the existing "no task has status `merged`" gate survives.
- AC-4 (FR4): a non-terminal journal last event makes route-back
  INAPPLICABLE -- no partial write, `implement` stays `failed`, report
  names the offending tasks, control returns via develop's stop condition
  3 / "abort phase"; no "rework" or "append" anywhere in I.2.c.
- AC-5 (FR5): I.2.a states id recycling arises only through I.2.c's
  route-back plus the planner's `replace_all` renumbering, and that,
  given AC-3's precondition, `status: pending` + journal last event
  `launched` can never arise; the retained in-flight sentence survives.
- AC-6 (FR6): a sentence scopes the recycled-task-id rule to the
  orchestrator's interpretation of the journal, naming all four hooks and
  stating they never consult `tasks.{T}.status` (never the stronger,
  false "never reads workflow.yaml"). SUPERSEDED by task0001
  (recycled-task-id-carveout) below: the "governs only the orchestrator's
  interpretation" framing was itself the self-contradiction that feature
  removes (SPEC.md's Overview) -- `TestRecycledTaskIdRuleScopedToOrchestrator`
  now asserts a different contract; see that paragraph for the current one.
- AC-7 (NFR1, NFR3, NFR4): the full suite (including the six protected
  pre-existing modules) stays green; no bare `git ... commit`/`add -A`
  line is introduced -- verified by the untouched
  tests/test_implement_routeback_gate.py and by running the whole suite.
- AC-8 (NFR5): this module exists, is discovered, implements TS-1 .. TS-10,
  and gives each new matcher a negative-proof test.

Content assertions compare against a whitespace-normalized copy of each
section (line-wrap choices never make an assertion brittle); byte-identity
assertions (TS-7, TS-8, TS-9) compare the raw, un-normalized text.

task0003 (verify-sourced rework, TS-14 / SC-6) extends this module with
negative proofs for the eight matchers below that assert NEW post-change
wording and previously had none: each keeps its literal in one module-level
constant shared by its positive test and its negative-proof test (Contract
1), and the negative proofs run against captured pre-change wording samples
(Contract 2) in `TestValidationDetectsRegressions`, guarded for non-vacuity
in `TestPreChangeSampleGuards` (Contract 4).

task0001 (recycled-task-id-carveout) rewrites the I.2.a closing scope
sentence and its Supporting-cast citing bullet
(feature-docs/recycled-task-id-carveout/tasks/task0001.md):

- AC-1/AC-2 (FR1): the self-contradictory literal "governs only the
  orchestrator's interpretation of the journal" -- immediately followed by
  a declared exception for `queue_stop_guard.py` -- is removed and replaced
  by a single non-contradictory rule: the recycled-task-id rule applies to
  the orchestrator's interpretation of the journal AND, identically, to
  `queue_stop_guard.py`, which applies the same carve-out itself; the other
  three hooks derive state from the journal's last event alone and never
  consult `tasks.{T}.status`. Neither "never read(s) workflow.yaml" occurs
  anywhere (unchanged regression guard).
- AC-3 (FR6): a new sentence, appended to the same paragraph, documents the
  deliberate unlaunched-definition divergence -- the hook classifies a task
  with no journal event as unlaunched without consulting its
  workflow.yaml status, so a missing/truncated journal can surface a
  `merged`-status task in the hook's launch list -- marked as intended
  fail-open behavior, not a defect. No hook file is touched.
- AC-4 (FR2, NFR6): the Supporting-cast Stop-hook bullet's equivalence
  claim is rescoped to state explicitly that it is limited to the
  carve-out itself and that I.2.a is the owning rule; the I.2.b step 1
  citation literal is unchanged (retention test, unmodified).
- AC-5/AC-6 (FR3, FR5): `TestRecycledTaskIdRuleScopedToOrchestrator` is
  split into two anchored-slice claims (the three journal-only hooks;
  `queue_stop_guard.py` as the single exception) replacing the four-hook
  filename-presence conjunction that stayed green with its meaning
  inverted (SPEC.md's Overview) -- neither claim is satisfiable by a
  filename occurring merely somewhere in the section.
  `ORCHESTRATOR_ONLY_SCOPE_PHRASE` is repurposed from a presence matcher's
  literal to a whole-document absence matcher's literal (Contract 1: kept
  as one constant, still shared by its positive test and its negative
  proof). `PRE_CHANGE_I2A_HOOK_PARENTHETICAL_SAMPLE` and its sole
  remaining reader are retired together, since every matcher that used it
  is retired by this task.
- AC-7 (FR8, NFR1, NFR2): the whole suite runs green; only standard-library
  imports are added; no file outside this task's two-file scope changes.

task0004 (verify-sourced rework, TS-2 / TS-12 / TS-13 / TS-14, SPEC AC-6)
closes two findings left open by task0001's own rework of this class:

- AC-1/AC-2/AC-3: `TestValidationDetectsRegressions` gains the paired
  negative proof
  `test_three_hooks_never_consult_slice_matcher_flags_four_hook_fold_in`
  for the three-hook anchored-slice matcher, applied to a newly captured
  pre-stopguard-retired-failed excerpt of `implement-phase.md` (commit
  061786a3c34f0f8a1d05ffd7915e5d5d51e04d56 -- the commit immediately
  preceding the already-merged `stopguard-retired-failed` feature's
  merge) in which `queue_stop_guard.py` was folded into the SAME "never
  consult `tasks.{T}.status`" claim as the three journal-only hooks --
  proving a naive filename-presence check would wrongly accept that
  wording (every hook name it names IS present in the sample) while the
  anchored-slice matcher correctly cannot even form its slice against it,
  since `THREE_HOOKS_SLICE_START_ANCHOR` was introduced only later, by
  the edit that separated `queue_stop_guard.py` out. No sample already in
  this module reaches back to that wording -- it predates both this
  feature and `recycled-task-id-consistency` -- so it is captured fresh
  rather than reused. `TestPreChangeSampleGuards` gains the paired
  retained-anchor guard for that new sample.
- AC-4: the inventory entry below for
  `test_three_journal_only_hooks_named_in_anchored_never_consult_slice`
  is corrected from a RETENTION classification (Contract 3, no proof
  needed) to a new-wording classification (Contracts 1, 2, 4) -- the
  WORDING inside the slice is retained, but the anchored-slice CLAIM the
  matcher makes is new.
- AC-5/AC-6: `HOOK_FILENAMES` is retired together with the derivation
  that was its sole remaining reader; `JOURNAL_ONLY_HOOK_FILENAMES`
  becomes a direct tuple literal and gains a second reader (the new
  negative proof above), leaving no module-level constant in this module
  with fewer than two reader sites.
- The AC-6 entry of
  `test-docs/recycled-task-id-carveout/task0001.tests.yaml` is corrected
  to record this exact single-reader state as it stood at task0001's
  merge, rather than the unmet ">=2 readers or fully retired" claim it
  previously recorded (IMPLEMENTATION.md D7).

Matcher -> negative-proof inventory (AC-5; every matcher in this module):

- test_reconciled_state_phrasing_present -> new wording ->
  test_reconciled_state_phrase_matcher_flags_absence_in_pre_change_wording
- test_journal_only_phrasing_absent -> new wording (pre-existing proof) ->
  test_journal_only_phrase_matcher_flags_the_pre_change_wording
- test_merged_half_unchanged -> RETENTION matcher, no proof needed
- test_report_failed_or_malformed_clause_survives -> RETENTION matcher, no
  proof needed
- test_i2a_normative_statement_present -> RETENTION matcher (statement
  unchanged by task0001's edit), no proof needed
- test_i2b_step1_citation_present -> RETENTION matcher, no proof needed
- test_precondition_names_terminal_event_with_merged_and_failed -> new
  wording (pre-existing proof) ->
  test_precondition_matcher_flags_absence_in_pre_change_wording
- test_precondition_precedes_ordered_write_set -> derivative ordering check
  on the same literal proven by
  test_precondition_matcher_flags_absence_in_pre_change_wording; no separate
  proof needed
- test_existing_merged_gate_survives -> RETENTION matcher, no proof needed
- test_inapplicable_branch_states_implement_stays_failed -> new wording ->
  test_inapplicable_marker_and_implement_stays_failed_flag_pre_change_wording
- test_inapplicable_branch_cites_stop_condition_3_and_abort_phase -> new
  wording (slice-anchor shape) ->
  test_inapplicable_anchored_slice_cannot_be_taken_on_pre_change_wording
- test_inapplicable_branch_names_no_partial_write -> new wording ->
  test_no_partial_write_phrases_matcher_flags_pre_change_wording
- test_no_rework_or_append_anywhere_in_i2c -> regression guard (pre-existing
  proof) -> test_rework_append_matcher_flags_the_bad_wording
- test_unreachability_sentence_present -> new wording (slice-anchor shape)
  -> test_unreachability_opening_anchor_matcher_flags_absence_in_pre_change_wording
- test_retained_in_flight_sentence_survives -> RETENTION matcher, no proof
  needed
- test_three_journal_only_hooks_named_in_anchored_never_consult_slice ->
  new-wording matcher (Contracts 1, 2, 4, task0004 correction): the
  SLICED WORDING is unchanged by this task's own edit, but the
  anchored-slice CLAIM itself is new -- it replaces the retired
  four-hook filename-presence conjunction
  (`test_scope_sentence_names_all_four_hooks`) and, by construction,
  excludes `queue_stop_guard.py` from the slice rather than merely
  happening to omit it -- so it is governed by Contracts 1, 2 and 4, not
  the Contract 3 retention exemption ->
  test_three_hooks_never_consult_slice_matcher_flags_four_hook_fold_in
  (task0004)
- test_stop_guard_named_as_explicit_exception_in_anchored_slice -> new
  wording (slice-anchor shape) ->
  test_stop_guard_exception_anchor_matcher_flags_absence_in_pre_change_wording
- test_orchestrator_only_scope_phrase_absent_everywhere -> regression guard
  (the literal is removed by this task) ->
  test_orchestrator_only_scope_phrase_matcher_flags_the_pre_change_wording
- test_no_never_reads_workflow_yaml_claim_anywhere -> regression guard
  (pre-existing proof) ->
  test_never_reads_workflow_yaml_matcher_flags_the_bad_wording
- test_divergence_names_missing_journal_event_case /
  test_divergence_names_merged_status_consequence /
  test_divergence_marked_deliberate -> new wording ->
  test_divergence_phrases_matcher_flags_absence_in_pre_change_wording
- test_bullet_limits_equivalence_to_carveout_and_cites_i2a -> new wording ->
  test_supporting_cast_scope_limit_phrase_matcher_flags_pre_change_wording
- test_bullet_still_states_the_carveout_reclassification -> RETENTION
  matcher, no proof needed
- TestProtectedRawLiteralsSurvive.* (TS-7), TestWakePhaseCommitLiteralSurvives
  (TS-8), TestI2cHeadingAndBatchModeParagraphByteIdentical.* (TS-9),
  TestI2cOrderings.* (TS-10) -> regression guards over pre-existing literals
  and orderings, no proof needed
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

# The removed, journal-only write-back phrasing (TS-1 / AC-1).
OLD_JOURNAL_ONLY_PHRASE = "for every task whose last journal event is `failed`"

# TS-9's byte-identical literal, copied here per the task plan rather than
# imported from tests/test_implement_routeback_gate.py (that module is not
# imported and not modified). Brought to the post-change text by task0001
# (abort-phase-terminal).
PRE_CHANGE_BATCH_MODE_PARAGRAPH = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase**: refresh\n"
    "the integration worktree, capture the tip, then set and commit the\n"
    "`implement` step's `status` to `failed` via `commit-docs.sh` (no\n"
    "`create-plan` `needs_update`, no task status or notes write set, no\n"
    "worktree or branch cleanup — the terminal status write and its own commit\n"
    "are the ONLY side effect), then report and stop; control returns via\n"
    "develop's stop condition 3, firing on the next Step B iteration reading\n"
    "`implement: failed`. The external service cuts a follow-up task.\n"
    "Route-back-to-planning is never taken automatically. Track the\n"
    "retry-consumed state per task in `tasks.{T}.notes`.\n"
    "\n"
)

# --- task0003 (D8): module-level constants for the eight new-wording
# matchers this task adds negative proofs for. Each constant is read by
# both its positive test above and its negative-proof test in
# TestValidationDetectsRegressions below -- the literal is never spelled
# twice (Contract 1 / AC-1).

# AC-1 (FR1) group: I.2.b step 3's reconciled-state write-back phrasing.
RECONCILED_STATE_PHRASE = "step 1 reconciled state is `failed`"

# AC-4 (FR4) group: the I.2.c rejected branch -- the path taken when the
# route-back gate does not hold. The gate's second source (Step I.2.b's
# last-event-per-task rule) is what a non-terminal journal last event
# trips, so that case reaches this branch and never reaches the write set.
REJECTED_PATH_MARKER = "When the gate does not hold"
IMPLEMENT_TERMINAL_FAILED_PHRASE = "sets the `implement` step's `status` to `failed`"
STOP_CONDITION_3_PHRASE = "stop condition 3"
ABORT_PHASE_TERMINAL_PHRASE = 'the same terminal as the "abort phase" option below'
NO_ROUTE_BACK_SIDE_EFFECT_PHRASE = (
    "There is no route-back write set, no worktree/branch cleanup and no "
    "route-back commit on this path"
)
ONLY_SIDE_EFFECT_PHRASE = (
    "the terminal status write and its own commit are the ONLY side effect"
)

# AC-5 (FR5) group: the I.2.a unreachability sentence's opening anchor.
UNREACHABILITY_OPENING_ANCHOR = "Given I.2.c's route-back precondition"

# AC-6 (FR6) group: the I.2.a scope sentence. task0004 (rework, TS-13 /
# SC-1): JOURNAL_ONLY_HOOK_FILENAMES is a direct literal rather than a
# derivation from a HOOK_FILENAMES constant -- HOOK_FILENAMES is retired
# together with the derivation, since the derivation was HOOK_FILENAMES's
# only remaining reader (module Convention "Non-vacuity discipline": a
# constant whose only remaining reader is a derivation feeding one other
# constant is retired together with that derivation).
JOURNAL_ONLY_HOOK_FILENAMES = (
    "queue_launch_guard.py",
    "queue_failure_net.py",
    "queue_taskstop_net.py",
)
STATUS_NEVER_CONSULTED_PHRASE = "never consult `tasks.{T}.status`"
# task0001 (recycled-task-id-carveout): the literal that must now be ABSENT
# from the whole document -- it is the contradiction the feature removes
# (it was immediately followed by a declared exception for
# `queue_stop_guard.py`, so "governs only the orchestrator's" was never
# true). Repurposed from a presence matcher's literal to an absence
# matcher's literal; kept as one constant per the module's Contract 1.
ORCHESTRATOR_ONLY_SCOPE_PHRASE = (
    "governs only the orchestrator's interpretation of the journal"
)

# task0001 (recycled-task-id-carveout): anchors for the two separated
# claims that replace the four-hook filename-presence conjunction (FR3).
# Claim (a): the three journal-only hooks, inside a slice opening here and
# closing at STATUS_NEVER_CONSULTED_PHRASE. task0004 (rework, TS-2 /
# TS-12): although the SLICED WORDING is unchanged by this task's own
# edit, the anchored-slice CLAIM itself is new -- it replaces the retired
# four-hook filename-presence conjunction and, by construction, excludes
# `queue_stop_guard.py` from the slice -- so it carries its own paired
# negative proof below (Contracts 1, 2, 4), not a Contract 3 retention
# exemption.
THREE_HOOKS_SLICE_START_ANCHOR = "The other three hooks"
# Claim (b): `queue_stop_guard.py` named as the single explicit exception,
# inside a slice opening here (NEW wording -- this exact conjunction did
# not exist before this task) and closing at the retained phrase "applies
# this same recycled-task-id carve-out itself".
STOP_GUARD_EXCEPTION_START_ANCHOR = (
    "This recycled-task-id rule applies to the orchestrator's "
    "interpretation of the journal"
)
STOP_GUARD_EXCEPTION_END_ANCHOR = (
    "applies this same recycled-task-id carve-out itself"
)

# AC-3 (FR6) group: the deliberate unlaunched-definition divergence
# statement appended to the same I.2.a paragraph.
DIVERGENCE_NO_JOURNAL_EVENT_PHRASE = (
    "the hook classifies a task with no journal event as unlaunched "
    "without consulting that task's workflow.yaml status at all"
)
DIVERGENCE_MERGED_STATUS_PHRASE = (
    "a task whose workflow.yaml status reads `merged` can still be named "
    "in the hook's launch list"
)
DIVERGENCE_DELIBERATE_PHRASE = (
    "This divergence is deliberate, intended fail-open behavior, not a "
    "defect"
)

# AC-4 (FR2) group: the Supporting-cast Stop-hook bullet's rescoped
# equivalence clause.
SUPPORTING_CAST_SCOPE_LIMIT_PHRASE = (
    "I.2.a is the owning rule and this equivalence claim is limited to "
    "the carve-out itself"
)

# --- task0003 (D8): pre-change wording samples, one per group, each a
# verbatim excerpt of em-workflow/references/implement-phase.md at the
# implement phase's base commit b73c6e69e4ee81519d0e6f7f8f6a03ec06b5db24
# (Contract 2). Not paraphrased, not reconstructed -- copied the same way
# TS-9's byte-identity literal was copied.

# AC-1 group sample: I.2.b step 3's write-back sentence, including its
# `merged` half (RETAINED anchor) and its report clause.
PRE_CHANGE_I2B_STEP3_WRITE_BACK_SAMPLE = (
    "set `tasks.{T}.status = merged` for every task verified\n"
    "   merged, `= failed` for every task whose last journal event is "
    "`failed`\n"
    "   or whose report is `failed`/malformed"
)

# AC-4 group sample: the I.2.c route-back bullet, from its opening gate
# sentence ("no task has status `merged`" -- RETAINED anchor) through the
# ordered workflow.yaml write set.
PRE_CHANGE_I2C_ROUTEBACK_SAMPLE = (
    "This automatic re-entry applies only when no task has status\n"
    "  `merged` — the absence of any `merged` task; the drain above has\n"
    "  already retired every `in_progress` sibling by this point. Refresh\n"
    "  the integration worktree first (`git -C \"$WT_ROOT/integration\"\n"
    "  reset --hard em-workflow/{feature}/integration`), then capture\n"
    "  `ROUTEBACK_TIP=$(git -C \"$WT_ROOT/integration\" rev-parse HEAD)`,\n"
    "  then make one ordered workflow.yaml write set: set `create-plan` to\n"
    "  `needs_update`, set the `implement` step back to `pending`, record\n"
    "  each failed task's failure reason (the implementer's report\n"
    "  `notes`) in `tasks.{T}.notes`, and set\n"
    "  **every** failed task's `tasks.{T}.status` back to `pending`"
)

# AC-5 group sample: the I.2.a recycled-task-id paragraph, from the
# normative statement through the retained in-flight sentence (RETAINED
# anchor).
PRE_CHANGE_I2A_RECYCLED_PARAGRAPH = (
    "Recycled task id: workflow.yaml's status wins over a stale journal "
    "event\n"
    "here — a task whose workflow.yaml `status` is `pending` while the\n"
    "journal's last event for that id is `failed` counts as "
    "**unlaunched**, not\n"
    "failed. This carve-out is deliberately scoped to `failed` only, to "
    "stay\n"
    "consistent with `queue_launch_guard.py`, which reads only the "
    "journal's\n"
    "last event (never workflow.yaml) and allows a post-`failed` launch "
    "as the\n"
    "legitimate retry path. A task whose journal last event is "
    "`launched` is\n"
    "always in-flight, regardless of workflow.yaml `status` — never "
    "reinterpret\n"
    "it as unlaunched, since the launch guard would deny that launch."
)

# --- task0001 (recycled-task-id-carveout): pre-change wording samples,
# captured verbatim from em-workflow/references/implement-phase.md at this
# task's own base commit 300b565d4985d24b77c71077368ea79cc1c68a98 (Contract
# 2), i.e. the text this task itself is about to replace -- not paraphrased,
# not reconstructed.

# AC-1/AC-2/AC-3 group sample: the I.2.a closing scope sentence this task
# rewrites, from the self-contradictory "governs only..." opening through
# the retained "...scoped by this rule." closing clause.
PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE = (
    "This recycled-task-id rule governs only the orchestrator's\n"
    "interpretation of the journal, with one explicit exception:\n"
    "`queue_stop_guard.py` applies this same recycled-task-id carve-out "
    "itself\n"
    "(see the Stop-hook bullet under 'Supporting cast: journal, hooks, "
    "resume'\n"
    "below, which states the same classification). The other three "
    "hooks —\n"
    "`queue_launch_guard.py`,\n"
    "`queue_failure_net.py` and `queue_taskstop_net.py` — derive a "
    "task's state\n"
    "from the journal's last event alone and never consult "
    "`tasks.{T}.status`\n"
    "(see 'Supporting cast: journal, hooks, resume' below). The journal "
    "itself\n"
    "stays append-only (see Supporting cast below) — only the "
    "interpretation of\n"
    "its events is scoped by this rule."
)

# AC-4 group sample: the Supporting-cast Stop-hook bullet this task
# rescopes.
PRE_CARVEOUT_STOP_HOOK_BULLET_SAMPLE = (
    "- **Stop hook** (`queue_stop_guard.py`) — fires when the "
    "orchestrator's turn\n"
    "  ends. Replays the journal and workflow.yaml, applying the same\n"
    "  recycled-task-id carve-out as I.2.a above — a task whose journal "
    "last\n"
    "  event is `failed` and whose workflow.yaml `status` reads "
    "`pending`\n"
    "  reclassifies as unlaunched, not failed; if refillable slots and\n"
    "  unlaunched tasks exist and no task's reconciled state is "
    "`failed`, it\n"
    "  BLOCKS (exit 2) naming the tasks to launch — catching a "
    "forgotten refill\n"
    "  after a wake phase. A consecutive-block cap (3, tracked in a "
    "sidecar\n"
    "  next to the journal)\n"
    "  prevents it from wedging the session on unexpected state; "
    "exceeding the\n"
    "  cap yields a warning and lets the turn end. Does not write the "
    "journal."
)

# --- task0004 (verify-sourced rework, TS-2 / SC-1): the wording that
# predates BOTH this feature and `recycled-task-id-consistency` -- the
# state before the already-merged `stopguard-retired-failed` feature
# split `queue_stop_guard.py` out as a separate exception. Captured
# verbatim from em-workflow/references/implement-phase.md at commit
# 061786a3c34f0f8a1d05ffd7915e5d5d51e04d56 (the commit immediately
# preceding stopguard-retired-failed's merge) -- the last point at which
# `queue_stop_guard.py` was folded into the SAME "never consult
# `tasks.{T}.status`" claim as the other three hooks, which is exactly
# the violation VERIFICATION.md TS-2's negative half requires (Contract
# 2). No sample already captured in this module reaches back this far:
# `THREE_HOOKS_SLICE_START_ANCHOR` ("The other three hooks") was
# introduced BY stopguard-retired-failed's own edit as the mechanism that
# separated `queue_stop_guard.py` out, so no wording captured after that
# point ever folds it back in, and no wording captured before that point
# ever carries that anchor -- the two properties are mutually exclusive
# across real history, which is exactly what the negative proof below
# demonstrates: the anchor genuinely cannot be found in this sample.
PRE_STOPGUARD_RETIRED_FAILED_FOUR_HOOK_NEVER_CONSULT_SAMPLE = (
    "This recycled-task-id rule governs only the orchestrator's\n"
    "interpretation of the journal: `queue_launch_guard.py`,\n"
    "`queue_stop_guard.py`, `queue_failure_net.py` and "
    "`queue_taskstop_net.py`\n"
    "derive a task's state from the journal's last event alone and "
    "never\n"
    "consult `tasks.{T}.status` (see 'Supporting cast: journal, hooks, "
    "resume'\n"
    "below). The journal itself stays append-only (see Supporting cast "
    "below) —\n"
    "only the interpretation of its events is scoped by this rule."
)

# --- task0001 (abort-phase-terminal): the closing batch-mode paragraph's
# old status-without-a-write phrasing, captured before this task's edit
# landed -- needed for this task's own absence assertion's paired
# regression proof (AC-2). Distinct from PRE_CHANGE_BATCH_MODE_PARAGRAPH
# above, which this task updates to the POST-change bytes for TS-9's
# byte-pin check.
OLD_BATCH_MODE_STAYS_FAILED_REPORT_STOP_PHRASE = (
    "implement stays `failed`, report and stop"
)
OLD_BATCH_MODE_PARAGRAPH_BEFORE_ABORT_TERMINAL = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase** (implement\n"
    "stays `failed`, report and stop; the external service cuts a follow-up\n"
    "task). Route-back-to-planning is never taken automatically. Track the\n"
    "retry-consumed state per task in `tasks.{T}.notes`.\n"
    "\n"
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


def _i2b_section(text):
    start = text.index(I2B_HEADING, text.index(I2A_HEADING))
    end = text.index(I2C_HEADING, start)
    return text[start:end]


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


STOP_HOOK_BULLET_START = "- **Stop hook**"
NEXT_SUPPORTING_CAST_BULLET_START = (
    "- **PreToolUse(Task|Agent) launch guard**"
)


def _stop_hook_bullet(text):
    start = text.index(STOP_HOOK_BULLET_START)
    end = text.index(NEXT_SUPPORTING_CAST_BULLET_START, start)
    return text[start:end]


class TestWakePhaseWriteBackKeyedOffReconciledState(unittest.TestCase):
    """TS-1 / AC-1 (FR1): step 3's `failed` write-back names step 1's
    reconciled state; the journal-only phrasing is gone; the `merged` half
    and the report-is-`failed`/malformed clause survive."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2b_section(_read()))

    def test_reconciled_state_phrasing_present(self):
        self.assertIn(RECONCILED_STATE_PHRASE, self.section)

    def test_journal_only_phrasing_absent(self):
        self.assertNotIn(OLD_JOURNAL_ONLY_PHRASE, self.section)

    def test_merged_half_unchanged(self):
        self.assertIn(
            "set `tasks.{T}.status = merged` for every task verified merged",
            self.section,
        )

    def test_report_failed_or_malformed_clause_survives(self):
        self.assertIn("or whose report is `failed`/malformed", self.section)


class TestRecycledTaskIdRuleStaysSingleSource(unittest.TestCase):
    """TS-2 / AC-2 (FR2): I.2.a keeps the sole normative statement; I.2.b
    step 1 keeps its citation of it unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.i2a = _normalize_ws(_i2a_section(cls.text))
        cls.i2b = _normalize_ws(_i2b_section(cls.text))

    def test_i2a_normative_statement_present(self):
        self.assertIn(
            "Recycled task id: workflow.yaml's status wins over a stale "
            "journal event here",
            self.i2a,
        )

    def test_i2b_step1_citation_present(self):
        self.assertIn("the recycled-task-id rule in I.2.a above", self.i2b)


class TestRouteBackPreconditionRequiresTerminalEvent(unittest.TestCase):
    """TS-3 / AC-3 (FR3): the precondition names a terminal journal last
    event with both `merged` and `failed`, positioned before the ordered
    write set; the existing "no task has status `merged`" gate survives."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_precondition_names_terminal_event_with_merged_and_failed(self):
        self.assertIn(
            "terminal journal last event (`merged` or `failed`)", self.section
        )

    def test_precondition_precedes_ordered_write_set(self):
        precondition_idx = self.section.index(
            "terminal journal last event (`merged` or `failed`)"
        )
        write_set_idx = self.section.index("`create-plan` to `needs_update`")
        self.assertLess(precondition_idx, write_set_idx)

    def test_existing_merged_gate_survives(self):
        self.assertIn("no task has status `merged`", self.section)


class TestNonTerminalEventMakesRouteBackInapplicable(unittest.TestCase):
    """TS-4 / AC-4 (FR4): a non-terminal journal last event makes
    route-back inapplicable -- it trips the gate's second source (Step
    I.2.b's last-event-per-task rule), so control lands on the rejected
    path: `implement` is written to `failed` as that path's single write
    and control returns via develop's stop condition 3 / "abort phase";
    no "rework" or "append" anywhere in I.2.c."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_rejected_path_writes_implement_failed(self):
        self.assertIn(REJECTED_PATH_MARKER, self.section)
        self.assertIn(IMPLEMENT_TERMINAL_FAILED_PHRASE, self.section)

    def test_rejected_path_cites_stop_condition_3_and_abort_phase(self):
        # Anchor on the rejected-path opening (new text) so this proves
        # the NEW branch cites stop condition 3 / abort phase, not merely
        # that the pre-existing merged-task branch already did.
        idx = self.section.index(REJECTED_PATH_MARKER)
        branch = self.section[idx:]
        self.assertIn(STOP_CONDITION_3_PHRASE, branch)
        self.assertIn(ABORT_PHASE_TERMINAL_PHRASE, branch)

    def test_rejected_path_names_no_partial_write(self):
        self.assertIn(NO_ROUTE_BACK_SIDE_EFFECT_PHRASE, self.section)
        self.assertIn(ONLY_SIDE_EFFECT_PHRASE, self.section)

    def test_no_rework_or_append_anywhere_in_i2c(self):
        self.assertNotIn("rework", self.section)
        self.assertNotIn("append", self.section)


class TestUnreachablePendingLaunchedCombination(unittest.TestCase):
    """TS-5 / AC-5 (FR5): the unreachability sentence mentions the
    planner's `replace_all` renumbering together with `launched` and
    `pending`; the retained in-flight sentence survives."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2a_section(_read()))

    def test_unreachability_sentence_present(self):
        idx = self.section.index(UNREACHABILITY_OPENING_ANCHOR)
        end = self.section.index("can never arise.", idx) + len("can never arise.")
        sentence = self.section[idx:end]
        self.assertIn("replace_all", sentence)
        self.assertIn("launched", sentence)
        self.assertIn("pending", sentence)

    def test_retained_in_flight_sentence_survives(self):
        self.assertIn(
            "A task whose journal last event is `launched` is always "
            "in-flight, regardless of workflow.yaml `status`",
            self.section,
        )


class TestRecycledTaskIdRuleScopedToOrchestrator(unittest.TestCase):
    """TS-6 / AC-2 (FR1, task0001/recycled-task-id-carveout): the I.2.a
    scope sentence states ONE non-contradictory rule as two SEPARATE
    claims -- (a) the three journal-only hooks are named inside an
    anchored slice that also states they never consult
    `tasks.{T}.status`, and that slice excludes `queue_stop_guard.py`;
    (b) `queue_stop_guard.py` is named as the explicit, single exception
    applying the carve-out, inside its own anchored slice. Neither
    assertion is satisfiable merely by a filename occurring somewhere in
    the section -- each is confined to its anchored slice. The document
    nowhere contains "governs only the orchestrator's interpretation of
    the journal" (the self-contradiction this task removes) or "never
    read(s) workflow.yaml"."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        # Whole-document, whitespace-normalized: the removed literal spans
        # a line-wrap in the raw text at this exact location, so a raw
        # (un-normalized) check would pass vacuously without the edit
        # (NFR3 -- prose assertions compare against normalized text).
        cls.normalized_text = _normalize_ws(cls.text)
        cls.i2a = _normalize_ws(_i2a_section(cls.text))

    def test_three_journal_only_hooks_named_in_anchored_never_consult_slice(
        self,
    ):
        start = self.i2a.index(THREE_HOOKS_SLICE_START_ANCHOR)
        end = self.i2a.index(STATUS_NEVER_CONSULTED_PHRASE, start) + len(
            STATUS_NEVER_CONSULTED_PHRASE
        )
        slice_ = self.i2a[start:end]
        for hook in JOURNAL_ONLY_HOOK_FILENAMES:
            self.assertIn(f"`{hook}`", slice_)
        # The exception hook must NOT be conflated into this claim.
        self.assertNotIn("`queue_stop_guard.py`", slice_)

    def test_stop_guard_named_as_explicit_exception_in_anchored_slice(self):
        start = self.i2a.index(STOP_GUARD_EXCEPTION_START_ANCHOR)
        end = self.i2a.index(STOP_GUARD_EXCEPTION_END_ANCHOR, start) + len(
            STOP_GUARD_EXCEPTION_END_ANCHOR
        )
        slice_ = self.i2a[start:end]
        self.assertIn("`queue_stop_guard.py`", slice_)

    def test_orchestrator_only_scope_phrase_absent_everywhere(self):
        self.assertNotIn(ORCHESTRATOR_ONLY_SCOPE_PHRASE, self.normalized_text)

    def test_no_never_reads_workflow_yaml_claim_anywhere(self):
        self.assertNotIn("never read workflow.yaml", self.text)
        self.assertNotIn("never reads workflow.yaml", self.text)


class TestUnlaunchedDefinitionDivergenceDocumented(unittest.TestCase):
    """AC-3 (FR6, task0001/recycled-task-id-carveout): I.2.a records the
    unlaunched-definition divergence between its own definition and
    `queue_stop_guard.py`'s status-blind treatment of a missing journal
    event, and marks it deliberate, intended fail-open behavior -- not a
    defect. No hook file is touched by this task (verified by the
    unmodified-module scope, not by a test here)."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))

    def test_divergence_names_missing_journal_event_case(self):
        self.assertIn(DIVERGENCE_NO_JOURNAL_EVENT_PHRASE, self.i2a)

    def test_divergence_names_merged_status_consequence(self):
        self.assertIn(DIVERGENCE_MERGED_STATUS_PHRASE, self.i2a)

    def test_divergence_marked_deliberate(self):
        self.assertIn(DIVERGENCE_DELIBERATE_PHRASE, self.i2a)


class TestSupportingCastStopHookBulletScopedToCarveout(unittest.TestCase):
    """AC-4 (FR2, NFR6, task0001/recycled-task-id-carveout): the
    Supporting-cast Stop-hook bullet's equivalence claim is limited to
    the carve-out itself and cites I.2.a as the owning rule; the bullet
    remains a citing consumer, never an independent restatement."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = _normalize_ws(_stop_hook_bullet(_read()))

    def test_bullet_limits_equivalence_to_carveout_and_cites_i2a(self):
        self.assertIn(SUPPORTING_CAST_SCOPE_LIMIT_PHRASE, self.bullet)

    def test_bullet_still_states_the_carveout_reclassification(self):
        self.assertIn(
            "a task whose journal last event is `failed` and whose "
            "workflow.yaml `status` reads `pending` reclassifies as "
            "unlaunched, not failed",
            self.bullet,
        )


class TestProtectedRawLiteralsSurvive(unittest.TestCase):
    """TS-7: both line-wrap-sensitive literals of IMPLEMENTATION.md D3 are
    present in the raw (un-normalized) text, with the Step I.0 one
    occurring earlier in the file than the Step I.2.a one."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_step_i2a_select_literal_survives(self):
        literal = (
            "`tasks.*.status`. Select\n"
            "unlaunched tasks (no journal event yet and `status != merged`, "
            "ascending"
        )
        self.assertIn(
            literal,
            self.text,
            "Step I.2.a's `Select` / `unlaunched tasks (...) ascending` "
            "line-wrap literal was reflowed",
        )

    def test_step_i0_pending_literal_survives(self):
        literal = 'in `tasks` whose\n   `status == pending`'
        self.assertIn(
            literal,
            self.text,
            "Step I.0's `require at least one task in `tasks` whose` / "
            "`status == pending` line-wrap literal was reflowed",
        )

    def test_step_i0_literal_precedes_step_i2a_literal(self):
        i0_idx = self.text.index('in `tasks` whose\n   `status == pending`')
        i2a_idx = self.text.index(
            "`tasks.*.status`. Select\nunlaunched tasks (no journal event "
            "yet and `status != merged`, ascending"
        )
        self.assertLess(i0_idx, i2a_idx)


class TestWakePhaseCommitLiteralSurvives(unittest.TestCase):
    """TS-8: the I.2.b step 3 commit literal survives with its exact
    newline and three-space continuation indent."""

    def test_commit_literal_survives(self):
        literal = (
            '`commit-docs.sh {integration_worktree} "docs({feature}): '
            "implement wake\n"
            '   phase reconcile" "$RECONCILE_TIP"`'
        )
        self.assertIn(
            literal,
            _read(),
            "I.2.b step 3's commit-docs.sh line-wrap literal was reflowed",
        )


class TestI2cHeadingAndBatchModeParagraphByteIdentical(unittest.TestCase):
    """TS-9: the I.2.c heading is byte-identical, and the batch-mode
    paragraph is still the byte-identical tail of the I.2.c section."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_is_byte_identical(self):
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx: idx + len(I2C_HEADING)], I2C_HEADING)

    def test_batch_mode_paragraph_is_byte_identical_tail(self):
        section = _i2c_section(self.text)
        start = section.index("Batch mode (`references/batch-mode.md`")
        actual = section[start:]
        self.assertEqual(actual, PRE_CHANGE_BATCH_MODE_PARAGRAPH)


class TestBatchModeParagraphRestatesSC1Terminal(unittest.TestCase):
    """AC-2 (task0001, abort-phase-terminal) / FR2: the closing batch-mode
    paragraph describes the same refresh / `implement: failed` write /
    `commit-docs.sh` / report sequence as the rejected path and the
    abort-phase option, still names the Non-packet gates table and
    `implement.failed-task`, no longer contains the old
    status-without-a-write phrasing, and -- on the raw text -- is still
    the section's final content before `### Supporting cast`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.raw_section = _i2c_section(cls.text)
        cls.section = _normalize_ws(cls.raw_section)
        cls.paragraph = cls.section[
            cls.section.index("Batch mode (`references/batch-mode.md`") :
        ]

    def test_names_non_packet_gates_table_and_gate_id(self):
        self.assertIn("Non-packet gates table", self.paragraph)
        self.assertIn("`implement.failed-task`", self.paragraph)

    def test_states_refresh(self):
        self.assertIn("refresh the integration worktree", self.paragraph)

    def test_states_implement_failed_write_via_commit_docs_sh(self):
        self.assertIn(
            "set and commit the `implement` step's `status` to `failed` "
            "via `commit-docs.sh`",
            self.paragraph,
        )

    def test_states_report_and_stop(self):
        self.assertIn("report and stop", self.paragraph)

    def test_old_stays_failed_report_and_stop_phrase_absent(self):
        self.assertNotIn(
            OLD_BATCH_MODE_STAYS_FAILED_REPORT_STOP_PHRASE, self.section
        )

    def test_paragraph_still_final_content_before_supporting_cast(self):
        idx = self.text.index(NEXT_SECTION_HEADING)
        tail_before_heading = self.text[:idx]
        # exactly one blank line separates the paragraph's end from the
        # next heading -- i.e. the raw text ends "...notes`.\n\n" right
        # before "### Supporting cast".
        self.assertTrue(
            tail_before_heading.endswith("`tasks.{T}.notes`.\n\n")
        )

    def test_retains_auto_retry_once_per_task_rule(self):
        self.assertIn("auto-select **retry** ONCE per task", self.paragraph)

    def test_retains_route_back_never_automatic(self):
        self.assertIn(
            "Route-back-to-planning is never taken automatically",
            self.paragraph,
        )

    def test_retains_retry_consumed_state_note(self):
        self.assertIn(
            "Track the retry-consumed state per task in `tasks.{T}.notes`",
            self.paragraph,
        )


class TestI2cOrderings(unittest.TestCase):
    """TS-10: normalized I.2.c orderings survive -- first `tasks.{T}.status`
    has `pending` within 60 characters; the four write tokens precede
    `git worktree remove --force`; the first `commit-docs.sh` precedes
    cleanup, which precedes `End the phase with a`. The commit-before-
    cleanup order is owned by I.2.c itself: an unexpected non-zero exit at
    the route-back commit must not leave the write set uncommitted with
    worktrees already deleted."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_first_tasks_status_has_pending_within_60_chars(self):
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx: idx + 60]
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

    def test_commit_precedes_cleanup_precedes_end_of_phase_report(self):
        cleanup_idx = self.section.index("git worktree remove --force")
        commit_idx = self.section.index("commit-docs.sh")
        report_idx = self.section.index("End the phase with a")
        self.assertLess(commit_idx, cleanup_idx)
        self.assertLess(cleanup_idx, report_idx)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- one
    negative-proof per new matcher, demonstrated against pre-change (or
    hypothetically-bad) wording samples."""

    def test_journal_only_phrase_matcher_flags_the_pre_change_wording(self):
        sample = (
            "set `tasks.{T}.status = merged` for every task verified "
            "merged, `= failed` for every task whose last journal event "
            "is `failed` or whose report is `failed`/malformed"
        )
        self.assertIn(OLD_JOURNAL_ONLY_PHRASE, sample)

    def test_never_reads_workflow_yaml_matcher_flags_the_bad_wording(self):
        sample = (
            "these hooks derive a task's state from the journal alone "
            "and never read workflow.yaml"
        )
        self.assertIn("never read workflow.yaml", sample)

    def test_precondition_matcher_flags_absence_in_pre_change_wording(self):
        # The I.2.c route-back bullet's opening, as it read before this
        # task's edit -- no terminal-journal-event precondition anywhere.
        sample = _normalize_ws(
            "This automatic re-entry applies only when no task has status "
            "`merged` — the absence of any `merged` task; the drain above "
            "has already retired every `in_progress` sibling by this "
            "point. Refresh the integration worktree first (`git -C "
            '"$WT_ROOT/integration" reset --hard '
            "em-workflow/{feature}/integration`), then capture..."
        )
        self.assertNotIn("terminal journal last event", sample)

    def test_rework_append_matcher_flags_the_bad_wording(self):
        sample = "the failed task is queued for rework before the next retry"
        self.assertIn("rework", sample)
        other_sample = "the failure reason is appended to the report"
        self.assertIn("append", other_sample)

    # --- task0003 (D8 / TS-14 / SC-6): negative proofs for the eight
    # matchers that assert NEW post-change wording and previously had no
    # proof they would flag the pre-change document.

    def test_reconciled_state_phrase_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_I2B_STEP3_WRITE_BACK_SAMPLE)
        self.assertNotIn(RECONCILED_STATE_PHRASE, sample)

    def test_rejected_path_marker_and_implement_failed_flag_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_I2C_ROUTEBACK_SAMPLE)
        self.assertNotIn(REJECTED_PATH_MARKER, sample)
        self.assertNotIn(IMPLEMENT_TERMINAL_FAILED_PHRASE, sample)

    def test_rejected_path_anchored_slice_cannot_be_taken_on_pre_change_wording(
        self,
    ):
        # The matcher slices the section from the rejected-path marker
        # onward before checking "stop condition 3" / the abort-phase
        # terminal phrase. On the pre-change sample the marker is absent,
        # so that slice cannot be taken at all -- proving the surviving
        # "abort phase" mention elsewhere in the pre-change document could
        # not satisfy this matcher (it never reaches that check).
        sample = _normalize_ws(PRE_CHANGE_I2C_ROUTEBACK_SAMPLE)
        with self.assertRaises(ValueError):
            sample.index(REJECTED_PATH_MARKER)

    def test_no_partial_write_phrases_matcher_flags_pre_change_wording(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_ROUTEBACK_SAMPLE)
        self.assertNotIn(NO_ROUTE_BACK_SIDE_EFFECT_PHRASE, sample)
        self.assertNotIn(ONLY_SIDE_EFFECT_PHRASE, sample)

    def test_unreachability_opening_anchor_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        # The matcher slices from this opening anchor to a closing anchor
        # before checking the three tokens. Those tokens (`launched`,
        # `pending`) DO occur elsewhere in the pre-change paragraph, so
        # proving the matcher flags the pre-change wording must be about
        # the slice anchor, not the tokens: the opening anchor is absent,
        # so the slice -- and therefore the matcher -- cannot be formed.
        sample = _normalize_ws(PRE_CHANGE_I2A_RECYCLED_PARAGRAPH)
        with self.assertRaises(ValueError):
            sample.index(UNREACHABILITY_OPENING_ANCHOR)

    # --- task0001 (recycled-task-id-carveout): negative proofs for the
    # matchers added/revised by this task (AC-6).

    def test_orchestrator_only_scope_phrase_matcher_flags_the_pre_change_wording(
        self,
    ):
        # The absence-check above is only meaningful if the literal really
        # was present before this task's own edit -- prove it against this
        # task's own captured pre-change sample.
        sample = _normalize_ws(PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE)
        self.assertIn(ORCHESTRATOR_ONLY_SCOPE_PHRASE, sample)

    def test_stop_guard_exception_anchor_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        # The matcher slices from this NEW opening anchor onward. On the
        # pre-change sample the anchor is absent (the old text opened with
        # "governs only ... with one explicit exception:" instead), so the
        # slice -- and therefore the matcher -- cannot even be formed.
        sample = _normalize_ws(PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE)
        with self.assertRaises(ValueError):
            sample.index(STOP_GUARD_EXCEPTION_START_ANCHOR)

    def test_divergence_phrases_matcher_flags_absence_in_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE)
        self.assertNotIn(DIVERGENCE_NO_JOURNAL_EVENT_PHRASE, sample)
        self.assertNotIn(DIVERGENCE_MERGED_STATUS_PHRASE, sample)
        self.assertNotIn(DIVERGENCE_DELIBERATE_PHRASE, sample)

    def test_supporting_cast_scope_limit_phrase_matcher_flags_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(PRE_CARVEOUT_STOP_HOOK_BULLET_SAMPLE)
        self.assertNotIn(SUPPORTING_CAST_SCOPE_LIMIT_PHRASE, sample)

    def test_old_batch_mode_stays_failed_phrase_matcher_flags_pre_change_wording(
        self,
    ):
        sample = _normalize_ws(OLD_BATCH_MODE_PARAGRAPH_BEFORE_ABORT_TERMINAL)
        self.assertIn(OLD_BATCH_MODE_STAYS_FAILED_REPORT_STOP_PHRASE, sample)

    # --- task0004 (verify-sourced rework, TS-2 / SC-1): the paired
    # negative proof for the three-hook anchored-slice matcher (AC-1/AC-2).

    def test_three_hooks_never_consult_slice_matcher_flags_four_hook_fold_in(
        self,
    ):
        sample = _normalize_ws(
            PRE_STOPGUARD_RETIRED_FAILED_FOUR_HOOK_NEVER_CONSULT_SAMPLE
        )
        # The sample genuinely folds `queue_stop_guard.py` into the same
        # claim as the three journal-only hooks -- every hook name the
        # positive matcher checks for IS present in this sample, and so is
        # the never-consult phrase, so a naive filename-presence check
        # would wrongly accept it.
        for hook in JOURNAL_ONLY_HOOK_FILENAMES:
            self.assertIn(f"`{hook}`", sample)
        self.assertIn("`queue_stop_guard.py`", sample)
        self.assertIn(STATUS_NEVER_CONSULTED_PHRASE, sample)
        # Yet the anchored-slice matcher -- reading the SAME
        # THREE_HOOKS_SLICE_START_ANCHOR constant the positive test reads
        # -- cannot even form its slice against this sample: that opening
        # anchor was introduced by a later edit that separated
        # `queue_stop_guard.py` out, so it is absent here. The matcher
        # does not match this sample.
        with self.assertRaises(ValueError):
            sample.index(THREE_HOOKS_SLICE_START_ANCHOR)


class TestPreChangeSampleGuards(unittest.TestCase):
    """AC-2 / Contract 4: each pre-change wording sample carries a RETAINED
    anchor -- a phrase present both in the sample and in the post-change
    document -- asserted positively here. A sample that was emptied,
    truncated past the relevant sentence, or replaced with unrelated text
    fails one of these guards, so a negative proof above cannot silently
    degrade into a tautology (`assertNotIn(X, "")` passes for every X)."""

    def test_i2b_step3_sample_retains_merged_half(self):
        sample = _normalize_ws(PRE_CHANGE_I2B_STEP3_WRITE_BACK_SAMPLE)
        self.assertIn(
            "set `tasks.{T}.status = merged` for every task verified merged",
            sample,
        )

    def test_i2c_routeback_sample_retains_merged_gate(self):
        sample = _normalize_ws(PRE_CHANGE_I2C_ROUTEBACK_SAMPLE)
        self.assertIn("no task has status `merged`", sample)

    def test_i2a_recycled_paragraph_sample_retains_in_flight_sentence(self):
        sample = _normalize_ws(PRE_CHANGE_I2A_RECYCLED_PARAGRAPH)
        self.assertIn(
            "A task whose journal last event is `launched` is always "
            "in-flight",
            sample,
        )

    def test_pre_carveout_scope_sentence_sample_retains_three_hooks_anchor(
        self,
    ):
        sample = _normalize_ws(PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE)
        self.assertIn(THREE_HOOKS_SLICE_START_ANCHOR, sample)

    def test_pre_carveout_scope_sentence_sample_retains_never_consulted_phrase(
        self,
    ):
        sample = _normalize_ws(PRE_CARVEOUT_I2A_SCOPE_SENTENCE_SAMPLE)
        self.assertIn(STATUS_NEVER_CONSULTED_PHRASE, sample)

    def test_pre_carveout_stop_hook_bullet_sample_retains_carveout_citation(
        self,
    ):
        sample = _normalize_ws(PRE_CARVEOUT_STOP_HOOK_BULLET_SAMPLE)
        self.assertIn(
            "applying the same recycled-task-id carve-out as I.2.a above",
            sample,
        )

    def test_old_batch_mode_paragraph_sample_retains_gate_id_anchor(self):
        sample = _normalize_ws(OLD_BATCH_MODE_PARAGRAPH_BEFORE_ABORT_TERMINAL)
        self.assertIn("`implement.failed-task`", sample)

    def test_pre_stopguard_retired_failed_sample_retains_never_consulted_phrase(
        self,
    ):
        # AC-3 (task0004): the RETAINED anchor for the new negative-proof
        # sample above -- STATUS_NEVER_CONSULTED_PHRASE is present both
        # here and in the current post-change document, so the negative
        # proof's ValueError cannot be a symptom of an emptied sample.
        sample = _normalize_ws(
            PRE_STOPGUARD_RETIRED_FAILED_FOUR_HOOK_NEVER_CONSULT_SAMPLE
        )
        self.assertIn(STATUS_NEVER_CONSULTED_PHRASE, sample)


if __name__ == "__main__":
    unittest.main()
