"""Tests for task0004 (prelaunch-inprogress-routeback): the recycled-task-id
carve-out in `em-workflow/references/implement-phase.md` applies only to the
one `failed` journal event that Step I.2.c's route-back reset, as identified
by the orchestrator-only record `tasks.{T}.routeback_failed_journal_line`.

Covers task0004 Acceptance Criteria
(feature-docs/prelaunch-inprogress-routeback/tasks/task0004.md):

- AC-1 (FR8, TM-2): Region P's carve-out definition states the three
  conditions, states that a `pending` + `failed` task with no record, a null
  record, a non-canonical record or a non-matching line is `failed` and goes
  to I.2.c's failure handling, and cites `references/workflow-schema.md` for
  the record's definition. "This carve-out is deliberately scoped to `failed`
  only" occurs exactly once and the "The carve-out reclassifies only a task
  whose ..." phrase remains.
- AC-2 (FR8, FR9, TM-2): I.2.b step 1's exception clause and the Stop-hook
  bullet state the same three conditions and the same `failed` outcome; the
  bullet says the hook does not block on a non-matching task; I.2.b keeps "the
  recycled-task-id rule in I.2.a above" and the bullet keeps its pinned
  phrases.
- AC-3 (FR8, NFR1): I.2.c's route-back write set carries the record item;
  with that single item removed, the whitespace-normalized I.2.c section
  equals its base text; the exit-4 recovery bullet is byte-identical to its
  base text; the item contains neither "rework" nor "append".
- AC-4 (FR10): I.2.a no longer contains "arises only from I.2.c's own reset";
  the Reason sentence names the not-reached-launch-state-commit failure path
  and states that the record match tells it apart from a route-back reset;
  the allocation-rule citation remains; I.2.a does not contain "task0001".
- AC-5 (FR5): Region P states that a task whose launch-state commit was not
  reached and which later fails does not match the record and is `failed`;
  the in-flight sentence, the replacement sentence and the premise span stay
  byte-identical to the base revision.
- AC-6 (FR6, NFR4): every new-wording matcher below has a negative proof
  against a verbatim base-revision sample of the same site, and each negative
  proof has a non-vacuity guard.
- AC-7 (NFR1, NFR2, NFR3): the Branch & Worktree Model and the hook
  classification table are byte-identical to the base revision. (Region L is
  owned by another task, so this module does not pin it.)

This module reads only `em-workflow/references/implement-phase.md`. It does
not import another test module. The schema heading that defines the record
is another task's deliverable: this module asserts only that
`implement-phase.md` cites `references/workflow-schema.md` next to the record
name, never that the heading exists.

Content assertions compare against a whitespace-normalized copy of the
relevant section, so line-wrap choices never make a prose assertion
brittle; byte-identity assertions compare the raw, un-normalized text (or a
digest of it). The two are never mixed in one assertion.

Matcher -> negative-proof inventory (every new-wording matcher):

- test_definition_states_three_conditions,
  test_definition_flags_each_missing_element -> three-condition predicate ->
  test_three_condition_predicate_flags_the_pre_change_definition
- test_definition_lists_each_non_match_case,
  test_definition_routes_non_match_to_failure_handling,
  test_definition_names_pre_record_route_back_task,
  test_definition_states_nothing_clears_the_record,
  test_definition_cites_workflow_schema_next_to_record_name -> new wording ->
  test_definition_phrases_are_absent_from_pre_change_definition
- test_i2b_clause_states_three_conditions,
  test_i2b_clause_routes_non_match_to_failure_handling -> three-condition
  predicate -> test_three_condition_predicate_flags_the_pre_change_i2b_clause
- test_stop_hook_bullet_states_three_conditions,
  test_stop_hook_bullet_says_hook_does_not_block -> three-condition
  predicate -> test_three_condition_predicate_flags_the_pre_change_stop_bullet
- test_record_item_* (I.2.c) -> new wording ->
  test_record_item_is_absent_from_pre_change_write_set,
  test_removal_digest_matcher_is_sensitive
- test_reason_* (I.2.a) -> new wording ->
  test_reason_matchers_flag_the_pre_change_sentence
- test_fr5_* (Region P) -> new wording ->
  test_fr5_sentence_is_absent_from_pre_change_definition
- test_divergence_paragraph_* -> new wording ->
  test_divergence_matcher_flags_the_pre_change_paragraph
- retention / byte-identity / digest tests -> RETENTION matchers, guarded by
  TestDigestPinsAreSensitive, no proof needed

Every negative proof runs against a PRE_CHANGE_*_SAMPLE constant, a verbatim
excerpt of `em-workflow/references/implement-phase.md` as it reads at this
task's base revision (`3c7d753ee4bf91930f2897107f8e22fce9c60a5d`), generated
from the file by script and not reconstructed. Their non-vacuity is guarded
in `TestPreChangeSampleGuards`: each anchor the matchers rely on is asserted
present in both the sample and the live document.
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

BRANCH_WORKTREE_MODEL_HEADING = "## Branch & Worktree Model"
STEP_I0_HEADING = "## Step I.0"
I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
SUPPORTING_CAST_HEADING = "### Supporting cast"
# Region P ends where Region L begins (IMPLEMENTATION.md, Shared Components).
REGION_L_OPENING_ANCHOR = "For each selected task T"

# --- Module-level constants: every literal asserted as new wording is read
# by both its positive test and its negative-proof test.

RECORD_LITERAL = "routeback_failed_journal_line"

# The three-condition predicate. Each element is one regex (or literal) that
# every site must satisfy.
PENDING_CONDITION_RE = re.compile(
    r"workflow\.yaml `status` (?:is|reads) `pending`"
)
FAILED_LAST_EVENT_RE = re.compile(
    r"journal(?:'s)? last event (?:is|for that id is) `failed`"
)
LINE_EQUALITY_RE = re.compile(
    r"event's physical line equals [^;]{0,80}" + RECORD_LITERAL
)
# The outcome: a `pending` + `failed` task that fails the match is `failed`.
FAILED_OUTCOME_RE = re.compile(
    r"`pending` \+ `failed` task [^;]{0,200}?"
    r"\b(?:is|stays|remains) (?:\*\*|`)?failed(?:\*\*|`)?(?![\w-])"
)
# Elements the pre-change sites already satisfy (non-vacuity), and the ones
# only the new wording satisfies.
OLD_SITE_ELEMENTS = ("pending_condition", "failed_last_event")
NEW_WORDING_ELEMENTS = ("record_literal", "line_equality", "failed_outcome")

# AC-1: Region P's carve-out definition.
NON_MATCH_CASES_PHRASE = (
    "the match fails when the record is absent, `null`, not in canonical "
    "form, or names a different line"
)
ROUTE_TO_FAILURE_HANDLING_PHRASE = "I.2.c's failure handling"
BATCH_POLICY_PHRASE = (
    "(batch: `implement.failed-task` in `references/batch-policies.yaml`)"
)
PRE_RECORD_ROUTE_BACK_PHRASE = (
    "a task route-backed before this record existed, which carries none"
)
NOTHING_CLEARS_PHRASE = (
    "Nothing clears the record: a re-launched task that fails again has its "
    "last `failed` event on a new line, so it no longer matches."
)
WORKFLOW_SCHEMA_CITATION = "references/workflow-schema.md"
SCHEMA_CITATION_WINDOW = 250
DEFINITION_OPENING_ANCHOR = "Recycled task id:"
IN_FLIGHT_OPENING_ANCHOR = (
    "A task whose journal last event is `launched` is"
)
CARVE_OUT_SCOPED_SENTENCE = (
    "This carve-out is deliberately scoped to `failed` only"
)
TERMINATION_RECLASSIFY_PHRASE = (
    "The carve-out reclassifies only a task whose journal last event is "
    "`failed` and whose workflow.yaml `status` is `pending`"
)
TWO_PARTIES_PHRASE = "is applied by two parties"
STOP_GUARD_NAME = "`queue_stop_guard.py`"

# AC-2: I.2.b step 1 and the Stop-hook bullet.
I2B_STEP1_OPENING_ANCHOR = "1. **Reconcile**"
I2B_FIRST_NESTED_BULLET = "\n   - "
I2B_KEPT_RULE_CITATION = "the recycled-task-id rule in I.2.a above"
I2B_KEPT_NO_EVENT_NOTE = (
    "this no-event classification does not consult the `workflow.yaml` status"
)
STOP_HOOK_BULLET_OPENING_ANCHOR = "- **Stop hook**"
NEXT_TOP_LEVEL_BULLET_ANCHOR = "\n- **"
STOP_NO_BLOCK_PHRASE = "the hook does not block that feature (exit 0)"
STOP_KEPT_PHRASES = (
    "catching a forgotten refill after a wake phase",
    "Classification (hook classification table above): **reads** "
    "`tasks.{T}.status`",
    "matching I.2.a's classification exactly",
)

# AC-3: the single I.2.c write-set item, and its anchors.
STATUS_BACK_TO_PENDING_PHRASE = (
    "set `tasks.{T}.status` back to `pending` for every task in that set"
)
GATE_TAIL_PHRASE = " — the gate above already established"
ROUTEBACK_RECORD_ITEM = (
    ", and for each task in that set that has a journal event, set "
    "`tasks.{T}.routeback_failed_journal_line` to the physical line of that "
    "task's last `failed` event (the record is defined in "
    "`references/workflow-schema.md`; the line comes from the same journal "
    "replay used for the gate and the reset-set decision, a task with no "
    "journal event gets no record, and the route-back commit below commits "
    "this item with the rest of the write set, adding no new write and no "
    "new commit)"
)
RECORD_SET_PHRASE = (
    "set `tasks.{T}.routeback_failed_journal_line` to the physical line of "
    "that task's last `failed` event"
)
SAME_REPLAY_PHRASE = (
    "the line comes from the same journal replay used for the gate and the "
    "reset-set decision"
)
NO_EVENT_NO_RECORD_PHRASE = (
    "a task with no journal event gets no record"
)
EXISTING_COMMIT_PHRASE = (
    "the route-back commit below commits this item with the rest of the "
    "write set, adding no new write and no new commit"
)
ITEM_FORBIDDEN_WORDS = ("rework", "append")
FIRST_STATUS_LITERAL = "tasks.{T}.status"
PENDING_WINDOW = 60
FAILED_KIND_SPAN_RAW = (
    "clear `failed_kind`\n"
    "  (`references/workflow-schema.md`) back to null in that same write "
    "set —\n"
    "  re-asserting the null value Step I.1's phase-start write already set "
    "on\n"
    "  this entry, so this adds no extra write and no extra commit — "
    "record\n"
    "  "
)
RESIDUAL_ALREADY_COVER_PHRASE = (
    "which Step I.2.a's resume guard and its recycled-task-id rule already "
    "cover"
)
EXIT4_BULLET_OPENING_ANCHOR = "- **exit-4 recovery**"
EXIT4_BULLET_END_ANCHOR = "- **abort terminal-commit exception**"

# AC-4: the Reason sentence.
REASON_OPENING_ANCHOR = "Reason:"
REPLACEMENT_OPENING_ANCHOR = "Given I.2.c's route-back precondition below"
OLD_REASON_CLAIM = "arises only from I.2.c's own reset"
REASON_ORIGIN_RESET_PHRASE = (
    "I.2.c's own reset of the task's own prior `failed` status"
)
REASON_ORIGIN_NOT_REACHED_PHRASE = (
    "a launched task that failed without reaching Step I.2.a's "
    "launch-state commit below, whether through an interruption or after a "
    "second exit 4"
)
REASON_TELLS_APART_PHRASE = "The record match tells the two origins apart"
ALLOCATION_RULE_PHRASE = "allocation rule"
FORBIDDEN_REASON_WORDS = ("task0001", "renumber")

# AC-5: the FR5 addition and the byte-identical neighbours.
FR5_PHRASE = (
    "A task whose launch-state commit was not reached and which later fails "
    "becomes `pending` + `failed` as well; its `failed` event does not match "
    "the record, so the carve-out does not apply and the task is **failed**."
)
NEVER_ARISE_RE = re.compile(r"\bnever\s+arises?\b")
IN_FLIGHT_SENTENCE_RAW = (
    "A task whose journal last event is `launched` is\n"
    "always in-flight, regardless of workflow.yaml `status`"
)
# From the replacement sentence's opening through the end of the premise
# span, whitespace between them included, captured from the base revision.
REPLACEMENT_THROUGH_PREMISE_RAW = (
    "Given I.2.c's route-back precondition below, which admits only\n"
    "tasks with a terminal journal last event, and the allocation rule's\n"
    "guarantee that a `replace_all` never re-issues a retired id, a task can\n"
    "only ever carry its OWN journal's terminal event — route-back alone\n"
    "therefore never produces workflow.yaml `status: pending` combined with\n"
    "journal last event `launched`; that combination arises between a task's\n"
    "launch and Step I.2.a's launch-state commit below, and also when that\n"
    "commit is not reached (an interruption, or a second exit 4). The\n"
    "in-flight rule stated just above governs that combination, cited here "
    "and\n"
    "not restated; the recycled-task-id carve-out above does not apply to "
    "it.\n"
    "Because Step I.2.c's route-back gate below blocks route-back\n"
    "whenever any task's journal last event is `merged` — read from the\n"
    "journal directly, independent of the ancestor check — that gate never\n"
    "admits route-back while such an event stands. No retired task id is "
    "ever\n"
    "re-issued, so a task whose workflow.yaml `status` is `pending` can "
    "never\n"
    "carry an inherited `merged` journal last event; the recycled-task-id\n"
    "carve-out above stays correctly scoped to `failed` only."
)
PREMISE_OPENING_ANCHOR = "Because Step I.2.c's route-back gate below"
PREMISE_TERMINAL_PHRASE = "correctly scoped to `failed` only."

# Divergence paragraph.
DIVERGENCE_OPENING_ANCHOR = "`queue_stop_guard.py` is the exception"
DIVERGENCE_END_ANCHOR = "narrower than the orchestrator's own selection rule"
DIVERGENCE_RECORD_PHRASE = "and that carve-out also requires the record match"
FAIL_OPEN_LITERAL = "fail-open"

# AC-3 / AC-7: digests captured from the base revision.
BASE_I2C_NORMALIZED_SHA256 = (
    "c62ecacc17f294c18e0b2862c77e822883cb27c29989b09a7fb69efa6040edad"
)
BASE_EXIT4_BULLET_SHA256 = (
    "75bd5d29fce4c48e3b99fd9624de31aaf43c2d6e738bcf9c724383e8d0b7b381"
)
BASE_BRANCH_WORKTREE_MODEL_SHA256 = (
    "8363469d8dc8d914e304fbb4f2fbb3bea4502ec014bc2803b93df4158fdda632"
)
BASE_HOOK_TABLE_SHA256 = (
    "56e8837024b213fe69d800e0745e2d797a72ec36a16359baadca4e98919b6c7a"
)
HOOK_TABLE_OPENING_ANCHOR = "| Hook | Classification |"
HOOK_TABLE_END_ANCHOR = "\n\n- **Stop hook**"

# --- Pre-change samples: verbatim excerpts of
# em-workflow/references/implement-phase.md at this task's base revision
# 3c7d753ee4bf91930f2897107f8e22fce9c60a5d. Generated from the file by
# script, never reconstructed.

# Region P: the carve-out definition (the "pending + failed -> unlaunched"
# only wording), through the sentence that precedes the in-flight sentence.
PRE_CHANGE_DEFINITION_SAMPLE = (
    "Recycled task id: workflow.yaml's status wins over a stale journal event\n"
    "here — a task whose workflow.yaml `status` is `pending` while the\n"
    "journal's last event for that id is `failed` counts as **unlaunched**, "
    "not\n"
    "failed. This carve-out is deliberately scoped to `failed` only, to "
    "stay\n"
    "consistent with `queue_launch_guard.py`, which reads only the "
    "journal's\n"
    "last event (never workflow.yaml) and allows a post-`failed` launch as "
    "the\n"
    "legitimate retry path. "
)

# Region P: the old Reason sentence.
PRE_CHANGE_REASON_SAMPLE = (
    "Reason:\n"
    "I.2.c's route back to planning is the only writer that resets a "
    "task's\n"
    "status to `pending`, and no re-planning pass ever re-issues a retired "
    "task\n"
    "id to a different task — `references/workflow-patch.md`'s "
    "re-planning\n"
    "task-id allocation rule (cited here, never restated) allocates every "
    "new\n"
    "id above the highest the feature has ever registered, so the "
    "`pending` +\n"
    "`failed` combination arises only from I.2.c's own reset of a task's "
    "own\n"
    "prior `failed` status, never from a task inheriting a different "
    "task's\n"
    "retired id. "
)

# Region P: the old divergence-paragraph mention of the Stop hook.
PRE_CHANGE_DIVERGENCE_SAMPLE = (
    "`queue_stop_guard.py` is the exception: as described above, it also "
    "reads\n"
    "`tasks.{T}.status` to apply the recycled-task-id carve-out that "
    "reclassifies\n"
    "a `failed` + `pending` task as unlaunched. This is\n"
    "narrower than the orchestrator's own selection rule"
)

# I.2.b step 1: the old exception clause.
PRE_CHANGE_I2B_STEP1_SAMPLE = (
    "1. **Reconcile** — replay the journal (last-event-per-task rule: no "
    "event →\n"
    "   unlaunched — this no-event classification does not consult the\n"
    "   `workflow.yaml` status; the `status != merged` exclusion is applied "
    "by\n"
    "   I.2.a's selection condition, per the divergence discussion in "
    "I.2.a\n"
    "   above; `launched` → in-flight; `merged` → merged; `failed` →\n"
    "   failed — except that a task whose journal last event is `failed` "
    "AND\n"
    "   whose workflow.yaml `status` is `pending` is unlaunched instead, "
    "the\n"
    "   recycled-task-id rule in I.2.a above; a `launched` last event is "
    "always\n"
    "   in-flight regardless of workflow.yaml `status`) and cross-check "
    "against\n"
    "   git actual state, trust-but-verify:"
)

# Supporting cast: the old Stop-hook bullet.
PRE_CHANGE_STOP_BULLET_SAMPLE = (
    "- **Stop hook** (`queue_stop_guard.py`) — fires when the "
    "orchestrator's turn\n"
    "  ends. Replays the journal and workflow.yaml, applying the same\n"
    "  recycled-task-id carve-out as I.2.a above — a task whose journal "
    "last\n"
    "  event is `failed` and whose workflow.yaml `status` reads `pending`\n"
    "  reclassifies as unlaunched, not failed; if refillable slots and\n"
    "  unlaunched tasks exist and no task's reconciled state is `failed`, "
    "it\n"
    "  BLOCKS (exit 2) naming the tasks to launch — catching a forgotten "
    "refill\n"
    "  after a wake phase. Classification (hook classification table "
    "above):\n"
    "  **reads** `tasks.{T}.status`, the sole exception among the four "
    "queue\n"
    "  hooks named in I.2.a — matching I.2.a's classification exactly. A\n"
    "  consecutive-block cap (3, tracked in a sidecar next to the "
    "journal)\n"
    "  prevents it from wedging the session on unexpected state; "
    "exceeding the\n"
    "  cap yields a warning and lets the turn end. Does not write the "
    "journal.\n"
)

# I.2.c: the old route-back write set, from "then make one ordered ..."
# through the start of the `replace_planning` citation.
PRE_CHANGE_WRITE_SET_SAMPLE = (
    "then make one ordered workflow.yaml write set over the reset target\n"
    "  set — the union of every task whose Step I.2.b step 1 reconciled\n"
    "  state is `failed` and every task that workflow.yaml reports as\n"
    "  `status: failed`: set `create-plan` to `needs_update`, set the "
    "`implement`\n"
    "  step back to `pending`, clear `failed_kind`\n"
    "  (`references/workflow-schema.md`) back to null in that same write "
    "set —\n"
    "  re-asserting the null value Step I.1's phase-start write already "
    "set on\n"
    "  this entry, so this adds no extra write and no extra commit — "
    "record\n"
    "  each such task's failure reason (the implementer's report `notes`) "
    "in\n"
    "  `tasks.{T}.notes`, and set `tasks.{T}.status` back to `pending` "
    "for\n"
    "  every task in that set — the\n"
    "  gate above already established that no task is `merged` or\n"
    "  `in_progress` at this point, so the result is that no task is "
    "left\n"
    "  `merged` or `in_progress` or `failed`, which is exactly what "
    "makes the\n"
    "  planner's `replace_planning` operation "
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space."""
    return re.sub(r"\s+", " ", text)


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _region_p(text):
    """Step I.2.a's selection rules: from the I.2.a heading up to, not
    including, the paragraph that opens "For each selected task T"."""
    start = text.index(I2A_HEADING)
    end = text.index(REGION_L_OPENING_ANCHOR, start)
    return text[start:end]


def _definition_slice(text):
    """Region P's carve-out definition: from "Recycled task id:" up to the
    in-flight sentence."""
    text = _normalize_ws(text)
    start = text.index(DEFINITION_OPENING_ANCHOR)
    end = text.index(IN_FLIGHT_OPENING_ANCHOR, start)
    return text[start:end]


def _reason_slice(text):
    """Region P's Reason sentence: from "Reason:" up to the replacement
    sentence."""
    text = _normalize_ws(text)
    start = text.index(REASON_OPENING_ANCHOR)
    end = text.index(REPLACEMENT_OPENING_ANCHOR, start)
    return text[start:end]


def _divergence_slice(text):
    """Region P's divergence paragraph mention of the Stop hook."""
    text = _normalize_ws(text)
    start = text.index(DIVERGENCE_OPENING_ANCHOR)
    end = text.index(DIVERGENCE_END_ANCHOR, start)
    return text[start:end]


def _i2b_step1_slice(text):
    """I.2.b step 1: from "1. **Reconcile**" up to the first nested
    bullet."""
    start = text.index(I2B_STEP1_OPENING_ANCHOR, text.index(I2B_HEADING))
    end = text.index(I2B_FIRST_NESTED_BULLET, start)
    return text[start:end]


def _stop_hook_bullet_slice(text):
    """The Supporting cast Stop-hook bullet: from "- **Stop hook**" up to
    the next top-level bullet."""
    start = text.index(STOP_HOOK_BULLET_OPENING_ANCHOR)
    end = text.index(NEXT_TOP_LEVEL_BULLET_ANCHOR, start + 1)
    return text[start:end]


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(SUPPORTING_CAST_HEADING, start)
    return text[start:end]


def _exit4_bullet(text):
    start = text.index(EXIT4_BULLET_OPENING_ANCHOR)
    end = text.index(EXIT4_BULLET_END_ANCHOR, start)
    return text[start:end]


def _branch_worktree_model(text):
    start = text.index(BRANCH_WORKTREE_MODEL_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _hook_table(text):
    start = text.index(HOOK_TABLE_OPENING_ANCHOR)
    end = text.index(HOOK_TABLE_END_ANCHOR, start)
    return text[start:end]


def three_condition_gaps(text):
    """The one three-condition predicate, applied to every site. Returns
    the names of the elements the (whitespace-normalized) text lacks; an
    empty list means the site states the `pending` condition, the `failed`
    last-event condition, the line-equality condition against the record, and
    the `failed` outcome for a `pending` + `failed` task without the match."""
    normalized = _normalize_ws(text)
    gaps = []
    if RECORD_LITERAL not in normalized:
        gaps.append("record_literal")
    if not PENDING_CONDITION_RE.search(normalized):
        gaps.append("pending_condition")
    if not FAILED_LAST_EVENT_RE.search(normalized):
        gaps.append("failed_last_event")
    if not LINE_EQUALITY_RE.search(normalized):
        gaps.append("line_equality")
    if not FAILED_OUTCOME_RE.search(normalized):
        gaps.append("failed_outcome")
    return gaps


def _schema_citation_next_to_record(text):
    """True when `references/workflow-schema.md` sits within the window of an
    occurrence of the record name."""
    normalized = _normalize_ws(text)
    for record_match in re.finditer(re.escape(RECORD_LITERAL), normalized):
        low = max(0, record_match.start() - SCHEMA_CITATION_WINDOW)
        high = record_match.end() + SCHEMA_CITATION_WINDOW
        if WORKFLOW_SCHEMA_CITATION in normalized[low:high]:
            return True
    return False


def _pending_within_window_of_first_status(i2c_text):
    """True when "pending" appears within PENDING_WINDOW characters after the
    first `tasks.{T}.status` in the I.2.c text."""
    idx = i2c_text.index(FIRST_STATUS_LITERAL)
    after = i2c_text[idx + len(FIRST_STATUS_LITERAL) :]
    return "pending" in after[:PENDING_WINDOW]


def _remove_record_item(normalized_i2c):
    """The whitespace-normalized I.2.c text with the one record item
    removed. Raises AssertionError unless the item occurs exactly once."""
    count = normalized_i2c.count(ROUTEBACK_RECORD_ITEM)
    if count != 1:
        raise AssertionError(
            f"the record item occurs {count} times in I.2.c, expected 1"
        )
    return normalized_i2c.replace(ROUTEBACK_RECORD_ITEM, "", 1)


def _ordered_spans(text, needles):
    """Locate each needle in order, searching each later needle only after
    the earlier needle's match ends. Raises AssertionError naming the first
    needle that is missing from its allowed range."""
    spans = []
    pos = 0
    for needle in needles:
        idx = text.find(needle, pos)
        if idx == -1:
            raise AssertionError(
                f"{needle!r} not found at or after offset {pos}"
            )
        pos = idx + len(needle)
        spans.append((idx, pos))
    return spans


# =====================================================================
# AC-1: Region P's carve-out definition.
# =====================================================================


class TestCarveOutDefinition(unittest.TestCase):
    """AC-1 (FR8, TM-2): Region P's carve-out definition."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.region_p_raw = _region_p(text)
        cls.region_p = _normalize_ws(cls.region_p_raw)
        cls.definition = _normalize_ws(_definition_slice(text))

    def test_definition_states_three_conditions(self):
        self.assertEqual(three_condition_gaps(self.definition), [])

    def test_definition_flags_each_missing_element(self):
        # Each element of the predicate is individually load-bearing: the
        # predicate reports a gap when that one element is removed.
        mutations = {
            "record_literal": (RECORD_LITERAL, "x"),
            "pending_condition": ("`status` is `pending`", "`status` is `x`"),
            "failed_last_event": (
                "journal last event is `failed`",
                "journal last event is `x`",
            ),
            "line_equality": ("physical line equals", "physical line is"),
            "failed_outcome": ("is **failed**", "is **x**"),
        }
        for element, (needle, replacement) in mutations.items():
            with self.subTest(element=element):
                self.assertIn(needle, self.definition)
                mutated = self.definition.replace(needle, replacement)
                self.assertIn(element, three_condition_gaps(mutated))

    def test_definition_lists_each_non_match_case(self):
        self.assertIn(NON_MATCH_CASES_PHRASE, self.definition)

    def test_definition_routes_non_match_to_failure_handling(self):
        self.assertIn(ROUTE_TO_FAILURE_HANDLING_PHRASE, self.definition)
        self.assertIn(BATCH_POLICY_PHRASE, self.definition)

    def test_definition_names_pre_record_route_back_task(self):
        self.assertIn(PRE_RECORD_ROUTE_BACK_PHRASE, self.definition)

    def test_definition_states_nothing_clears_the_record(self):
        self.assertIn(NOTHING_CLEARS_PHRASE, self.definition)

    def test_definition_cites_workflow_schema_next_to_record_name(self):
        self.assertTrue(_schema_citation_next_to_record(self.definition))

    def test_scoped_phrase_occurs_exactly_once_in_raw_text(self):
        self.assertEqual(
            self.region_p_raw.count(CARVE_OUT_SCOPED_SENTENCE), 1
        )

    def test_reclassifies_only_phrase_remains(self):
        self.assertIn(TERMINATION_RECLASSIFY_PHRASE, self.region_p)

    def test_two_parties_phrase_naming_stop_guard_remains(self):
        idx = self.region_p.index(TWO_PARTIES_PHRASE)
        self.assertIn(STOP_GUARD_NAME, self.region_p[idx : idx + 200])


# =====================================================================
# AC-2: I.2.b step 1 and the Stop-hook bullet.
# =====================================================================


class TestI2bStep1Clause(unittest.TestCase):
    """AC-2 (FR8, FR9, TM-2): I.2.b step 1's exception clause."""

    @classmethod
    def setUpClass(cls):
        cls.step1 = _normalize_ws(_i2b_step1_slice(_read()))

    def test_i2b_clause_states_three_conditions(self):
        self.assertEqual(three_condition_gaps(self.step1), [])

    def test_i2b_clause_routes_non_match_to_failure_handling(self):
        self.assertIn(ROUTE_TO_FAILURE_HANDLING_PHRASE, self.step1)

    def test_i2b_clause_keeps_recycled_task_id_rule_citation(self):
        self.assertIn(I2B_KEPT_RULE_CITATION, self.step1)

    def test_i2b_clause_keeps_no_event_note(self):
        self.assertIn(I2B_KEPT_NO_EVENT_NOTE, self.step1)


class TestStopHookBullet(unittest.TestCase):
    """AC-2 (FR8, FR9, TM-2): the Supporting cast Stop-hook bullet."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = _normalize_ws(_stop_hook_bullet_slice(_read()))

    def test_stop_hook_bullet_states_three_conditions(self):
        self.assertEqual(three_condition_gaps(self.bullet), [])

    def test_stop_hook_bullet_says_hook_does_not_block(self):
        self.assertIn(STOP_NO_BLOCK_PHRASE, self.bullet)

    def test_stop_hook_bullet_keeps_pinned_phrases(self):
        for phrase in STOP_KEPT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.bullet)


class TestSitesAgreeOnTheMatchRule(unittest.TestCase):
    """AC-2: Region P, I.2.b step 1 and the Stop-hook bullet are judged by
    the same predicate and agree on every element."""

    def test_all_three_sites_pass_the_same_predicate(self):
        text = _read()
        sites = {
            "region P definition": _definition_slice(text),
            "I.2.b step 1": _i2b_step1_slice(text),
            "Stop-hook bullet": _stop_hook_bullet_slice(text),
        }
        for name, site in sites.items():
            with self.subTest(site=name):
                self.assertEqual(three_condition_gaps(site), [])


# =====================================================================
# AC-3: I.2.c's route-back write set.
# =====================================================================


class TestI2cRecordItem(unittest.TestCase):
    """AC-3 (FR8, NFR1): I.2.c's route-back write set contains the record
    item and nothing else in I.2.c changed."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.i2c_raw = _i2c_section(text)
        cls.i2c = _normalize_ws(cls.i2c_raw)
        cls.exit4_raw = _exit4_bullet(text)

    def test_record_item_occurs_exactly_once(self):
        self.assertEqual(self.i2c.count(ROUTEBACK_RECORD_ITEM), 1)

    def test_record_item_sits_between_status_reset_and_gate_tail(self):
        self.assertIn(
            STATUS_BACK_TO_PENDING_PHRASE
            + ROUTEBACK_RECORD_ITEM
            + GATE_TAIL_PHRASE,
            self.i2c,
        )

    def test_record_item_sets_record_to_last_failed_event_line(self):
        self.assertIn(RECORD_SET_PHRASE, ROUTEBACK_RECORD_ITEM)
        self.assertIn(RECORD_SET_PHRASE, self.i2c)

    def test_record_item_takes_the_line_from_the_same_replay(self):
        self.assertIn(SAME_REPLAY_PHRASE, ROUTEBACK_RECORD_ITEM)
        self.assertIn(SAME_REPLAY_PHRASE, self.i2c)

    def test_record_item_writes_no_record_for_task_without_event(self):
        self.assertIn(NO_EVENT_NO_RECORD_PHRASE, ROUTEBACK_RECORD_ITEM)
        self.assertIn(NO_EVENT_NO_RECORD_PHRASE, self.i2c)

    def test_record_item_rides_the_existing_route_back_commit(self):
        self.assertIn(EXISTING_COMMIT_PHRASE, ROUTEBACK_RECORD_ITEM)
        self.assertIn(EXISTING_COMMIT_PHRASE, self.i2c)
        # No second commit call site is introduced.
        self.assertNotIn("commit-docs.sh", ROUTEBACK_RECORD_ITEM)

    def test_record_item_cites_schema_next_to_record_name(self):
        self.assertTrue(_schema_citation_next_to_record(ROUTEBACK_RECORD_ITEM))

    def test_record_item_contains_neither_rework_nor_append(self):
        lowered = ROUTEBACK_RECORD_ITEM.lower()
        for word in ITEM_FORBIDDEN_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, lowered)

    def test_removing_the_record_item_restores_the_base_i2c_text(self):
        remainder = _remove_record_item(self.i2c)
        self.assertEqual(_sha256(remainder), BASE_I2C_NORMALIZED_SHA256)

    def test_first_status_write_still_has_pending_within_window(self):
        self.assertTrue(_pending_within_window_of_first_status(self.i2c))

    def test_failed_kind_through_record_span_is_byte_identical(self):
        self.assertEqual(self.i2c_raw.count(FAILED_KIND_SPAN_RAW), 1)

    def test_residual_already_cover_sentence_is_kept(self):
        self.assertIn(RESIDUAL_ALREADY_COVER_PHRASE, self.i2c)

    def test_exit4_recovery_bullet_is_byte_identical_to_base(self):
        self.assertEqual(_sha256(self.exit4_raw), BASE_EXIT4_BULLET_SHA256)


# =====================================================================
# AC-4: I.2.a's Reason sentence.
# =====================================================================


class TestReasonSentence(unittest.TestCase):
    """AC-4 (FR10): the Reason sentence names two origins of the
    `pending` + `failed` combination and the record match that tells them
    apart."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.i2a = _normalize_ws(_i2a_section(text))
        cls.reason = _normalize_ws(_reason_slice(text))

    def test_i2a_no_longer_claims_the_combination_arises_only_from_reset(
        self,
    ):
        self.assertNotIn(OLD_REASON_CLAIM, self.i2a)

    def test_reason_names_the_route_back_reset_origin(self):
        self.assertIn(REASON_ORIGIN_RESET_PHRASE, self.reason)

    def test_reason_names_the_not_reached_launch_state_commit_origin(self):
        self.assertIn(REASON_ORIGIN_NOT_REACHED_PHRASE, self.reason)

    def test_reason_states_the_record_match_tells_the_origins_apart(self):
        self.assertIn(REASON_TELLS_APART_PHRASE, self.reason)

    def test_reason_keeps_the_allocation_rule_citation(self):
        self.assertIn(ALLOCATION_RULE_PHRASE, self.reason)

    def test_reason_has_no_forbidden_words(self):
        for word in FORBIDDEN_REASON_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, self.reason)

    def test_i2a_does_not_contain_task0001(self):
        self.assertNotIn("task0001", self.i2a)


# =====================================================================
# AC-5: the FR5 addition and the byte-identical neighbours.
# =====================================================================


class TestFr5AdditionAndNeighbours(unittest.TestCase):
    """AC-5 (FR5): Region P states that a task whose launch-state commit was
    not reached and which later fails does not match the record and is
    `failed`; the in-flight sentence, the replacement sentence and the
    premise span stay byte-identical."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.region_p_raw = _region_p(text)
        cls.region_p = _normalize_ws(cls.region_p_raw)

    def test_fr5_sentence_is_in_region_p(self):
        self.assertIn(FR5_PHRASE, self.region_p)

    def test_fr5_sentence_does_not_sit_between_replacement_and_premise(self):
        fr5 = self.region_p.index(FR5_PHRASE)
        replacement = self.region_p.index(REPLACEMENT_OPENING_ANCHOR)
        self.assertLess(fr5, replacement)

    def test_in_flight_sentence_is_byte_identical(self):
        self.assertEqual(self.region_p_raw.count(IN_FLIGHT_SENTENCE_RAW), 1)

    def test_replacement_sentence_and_premise_span_are_byte_identical(self):
        # One raw span covers the replacement sentence, the whitespace
        # between it and "Because", and the premise span.
        self.assertEqual(
            self.region_p_raw.count(REPLACEMENT_THROUGH_PREMISE_RAW), 1
        )

    def test_premise_span_has_exactly_one_because_and_one_so(self):
        start = self.region_p.index(PREMISE_OPENING_ANCHOR)
        end = self.region_p.index(PREMISE_TERMINAL_PHRASE, start) + len(
            PREMISE_TERMINAL_PHRASE
        )
        span = self.region_p[start:end]
        self.assertEqual(span.count("Because "), 1)
        self.assertEqual(span.count(" so "), 1)

    def test_region_p_introduces_no_never_arise_claim(self):
        self.assertIsNone(NEVER_ARISE_RE.search(self.region_p))

    def test_region_p_items_keep_their_relative_order(self):
        spans = _ordered_spans(
            self.region_p,
            (
                DEFINITION_OPENING_ANCHOR,
                FR5_PHRASE,
                CARVE_OUT_SCOPED_SENTENCE,
                _normalize_ws(IN_FLIGHT_SENTENCE_RAW),
                REPLACEMENT_OPENING_ANCHOR,
                PREMISE_OPENING_ANCHOR,
            ),
        )
        self.assertEqual(len(spans), 6)


# =====================================================================
# Divergence paragraph.
# =====================================================================


class TestDivergenceParagraph(unittest.TestCase):
    """Region P's divergence paragraph says the Stop hook's carve-out also
    requires the record match, without a fail-open claim."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(_divergence_slice(_read()))

    def test_divergence_paragraph_states_record_match_requirement(self):
        self.assertIn(DIVERGENCE_RECORD_PHRASE, self.paragraph)

    def test_divergence_paragraph_has_no_fail_open_claim(self):
        self.assertNotIn(FAIL_OPEN_LITERAL, self._full_paragraph())

    @staticmethod
    def _full_paragraph():
        """The whole divergence paragraph, from the "other three queue
        hooks" opening to the sentence that follows it."""
        text = _normalize_ws(_read())
        start = text.index("The other three queue hooks detect a task as")
        end = text.index("Tasks whose reconciled state is `failed` are NEVER")
        return text[start:end]


# =====================================================================
# AC-7: sites this task does not touch.
# =====================================================================


class TestProtectedTextIsUnchanged(unittest.TestCase):
    """AC-7 (NFR1, NFR2, NFR3): the Branch & Worktree Model and the hook
    classification table are byte-identical to the base revision. Region L is
    owned by another task, so it is not pinned here."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.model = _branch_worktree_model(text)
        cls.table = _hook_table(text)

    def test_branch_worktree_model_is_byte_identical_to_base(self):
        self.assertEqual(
            _sha256(self.model), BASE_BRANCH_WORKTREE_MODEL_SHA256
        )

    def test_hook_classification_table_is_byte_identical_to_base(self):
        self.assertEqual(_sha256(self.table), BASE_HOOK_TABLE_SHA256)


class TestDigestPinsAreSensitive(unittest.TestCase):
    """Non-vacuity guards for the digest-based retention matchers: the
    slices are non-empty and a one-character change moves the digest."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.slices = {
            "I.2.c": _normalize_ws(_i2c_section(text)),
            "exit-4 bullet": _exit4_bullet(text),
            "Branch & Worktree Model": _branch_worktree_model(text),
            "hook table": _hook_table(text),
        }

    def test_slices_are_not_empty(self):
        for name, piece in self.slices.items():
            with self.subTest(slice=name):
                self.assertGreater(len(piece), 100)

    def test_one_character_change_moves_every_digest(self):
        for name, piece in self.slices.items():
            with self.subTest(slice=name):
                self.assertNotEqual(_sha256(piece), _sha256(piece + " "))

    def test_removal_digest_matcher_is_sensitive(self):
        # The matcher behind "removing the item restores the base text"
        # fails when the item is left in place, and fails on an extra word.
        i2c = self.slices["I.2.c"]
        remainder = _remove_record_item(i2c)
        self.assertNotEqual(_sha256(i2c), BASE_I2C_NORMALIZED_SHA256)
        self.assertNotEqual(
            _sha256(remainder + " extra"), BASE_I2C_NORMALIZED_SHA256
        )
        with self.assertRaises(AssertionError):
            _remove_record_item(i2c.replace(ROUTEBACK_RECORD_ITEM, ""))

    def test_pending_window_matcher_flags_an_item_inserted_after_status(self):
        i2c = self.slices["I.2.c"]
        self.assertTrue(_pending_within_window_of_first_status(i2c))
        broken = i2c.replace(
            FIRST_STATUS_LITERAL,
            FIRST_STATUS_LITERAL + ROUTEBACK_RECORD_ITEM,
            1,
        )
        self.assertFalse(_pending_within_window_of_first_status(broken))


# =====================================================================
# AC-6: negative proofs against verbatim pre-change samples.
# =====================================================================


class TestPreChangeSampleDetection(unittest.TestCase):
    """AC-6 (FR6, NFR4): every new-wording matcher above fails meaningfully
    against the verbatim pre-change sample of the same site."""

    @classmethod
    def setUpClass(cls):
        cls.definition = _normalize_ws(PRE_CHANGE_DEFINITION_SAMPLE)
        cls.reason = _normalize_ws(PRE_CHANGE_REASON_SAMPLE)
        cls.divergence = _normalize_ws(PRE_CHANGE_DIVERGENCE_SAMPLE)
        cls.i2b = _normalize_ws(PRE_CHANGE_I2B_STEP1_SAMPLE)
        cls.stop = _normalize_ws(PRE_CHANGE_STOP_BULLET_SAMPLE)
        cls.write_set = _normalize_ws(PRE_CHANGE_WRITE_SET_SAMPLE)

    def _assert_flags_new_wording_only(self, sample):
        gaps = three_condition_gaps(sample)
        for element in NEW_WORDING_ELEMENTS:
            self.assertIn(element, gaps, f"{element} not flagged")
        # The old site already carries the conditions the new wording keeps,
        # so the flagged gaps are about the record, not about a truncated
        # sample.
        for element in OLD_SITE_ELEMENTS:
            self.assertNotIn(element, gaps, f"{element} missing in sample")

    def test_three_condition_predicate_flags_the_pre_change_definition(self):
        self._assert_flags_new_wording_only(self.definition)

    def test_three_condition_predicate_flags_the_pre_change_i2b_clause(self):
        self._assert_flags_new_wording_only(self.i2b)

    def test_three_condition_predicate_flags_the_pre_change_stop_bullet(self):
        self._assert_flags_new_wording_only(self.stop)

    def test_definition_phrases_are_absent_from_pre_change_definition(self):
        for phrase in (
            NON_MATCH_CASES_PHRASE,
            ROUTE_TO_FAILURE_HANDLING_PHRASE,
            BATCH_POLICY_PHRASE,
            PRE_RECORD_ROUTE_BACK_PHRASE,
            NOTHING_CLEARS_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.definition)
        self.assertFalse(_schema_citation_next_to_record(self.definition))

    def test_i2b_matchers_flag_absence_in_pre_change_clause(self):
        self.assertNotIn(ROUTE_TO_FAILURE_HANDLING_PHRASE, self.i2b)

    def test_stop_hook_matcher_flags_absence_in_pre_change_bullet(self):
        self.assertNotIn(STOP_NO_BLOCK_PHRASE, self.stop)

    def test_record_item_is_absent_from_pre_change_write_set(self):
        self.assertNotIn(RECORD_LITERAL, self.write_set)
        for phrase in (
            ROUTEBACK_RECORD_ITEM,
            RECORD_SET_PHRASE,
            SAME_REPLAY_PHRASE,
            NO_EVENT_NO_RECORD_PHRASE,
            EXISTING_COMMIT_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.write_set)

    def test_reason_matchers_flag_the_pre_change_sentence(self):
        self.assertIn(OLD_REASON_CLAIM, self.reason)
        for phrase in (
            REASON_ORIGIN_RESET_PHRASE,
            REASON_ORIGIN_NOT_REACHED_PHRASE,
            REASON_TELLS_APART_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.reason)

    def test_fr5_sentence_is_absent_from_pre_change_definition(self):
        self.assertNotIn(FR5_PHRASE, self.definition)
        self.assertNotIn("launch-state commit", self.definition)

    def test_divergence_matcher_flags_the_pre_change_paragraph(self):
        self.assertNotIn(DIVERGENCE_RECORD_PHRASE, self.divergence)


class TestPreChangeSampleGuards(unittest.TestCase):
    """Non-vacuity guards: each anchor the matchers rely on is present in
    both the pre-change sample and the live document, so a negative proof
    above cannot degrade into a tautology (an absence check passes against an
    empty or truncated sample)."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.pairs = {
            "definition": (
                _normalize_ws(PRE_CHANGE_DEFINITION_SAMPLE),
                _normalize_ws(_definition_slice(text)),
                (
                    "Recycled task id: workflow.yaml's status wins over a "
                    "stale journal event",
                    CARVE_OUT_SCOPED_SENTENCE,
                    "`queue_launch_guard.py`",
                ),
            ),
            "reason": (
                _normalize_ws(PRE_CHANGE_REASON_SAMPLE),
                _normalize_ws(_reason_slice(text)),
                (
                    REASON_OPENING_ANCHOR,
                    ALLOCATION_RULE_PHRASE,
                    "references/workflow-patch.md",
                ),
            ),
            "divergence": (
                _normalize_ws(PRE_CHANGE_DIVERGENCE_SAMPLE),
                _normalize_ws(_divergence_slice(text)),
                (
                    DIVERGENCE_OPENING_ANCHOR,
                    "reclassifies a `failed` + `pending` task as unlaunched",
                ),
            ),
            "I.2.b step 1": (
                _normalize_ws(PRE_CHANGE_I2B_STEP1_SAMPLE),
                _normalize_ws(_i2b_step1_slice(text)),
                (I2B_STEP1_OPENING_ANCHOR, I2B_KEPT_RULE_CITATION),
            ),
            "Stop-hook bullet": (
                _normalize_ws(PRE_CHANGE_STOP_BULLET_SAMPLE),
                _normalize_ws(_stop_hook_bullet_slice(text)),
                (STOP_HOOK_BULLET_OPENING_ANCHOR, *STOP_KEPT_PHRASES),
            ),
            "I.2.c write set": (
                _normalize_ws(PRE_CHANGE_WRITE_SET_SAMPLE),
                _normalize_ws(_i2c_section(text)),
                (
                    "then make one ordered workflow.yaml write set",
                    STATUS_BACK_TO_PENDING_PHRASE,
                    GATE_TAIL_PHRASE.strip(),
                ),
            ),
        }
        cls.live_i2c = _normalize_ws(_i2c_section(text))

    def test_anchors_are_in_sample_and_live_document(self):
        for name, (sample, live, anchors) in self.pairs.items():
            for anchor in anchors:
                with self.subTest(site=name, anchor=anchor):
                    self.assertIn(anchor, sample)
                    self.assertIn(anchor, live)

    def test_old_conditions_are_in_sample_and_live_document(self):
        # The `pending` and `failed` last-event conditions are present in the
        # pre-change wording and survive in the live wording, so the new
        # elements the predicate flags are what changed.
        for name in ("definition", "I.2.b step 1", "Stop-hook bullet"):
            sample, live, _ = self.pairs[name]
            for label, text in (("sample", sample), ("live", live)):
                with self.subTest(site=name, side=label):
                    self.assertTrue(PENDING_CONDITION_RE.search(text))
                    self.assertTrue(FAILED_LAST_EVENT_RE.search(text))

    def test_sample_carries_old_claims_the_live_document_dropped(self):
        self.assertIn(OLD_REASON_CLAIM, self.pairs["reason"][0])
        self.assertNotIn(OLD_REASON_CLAIM, self.pairs["reason"][1])
        self.assertNotIn(RECORD_LITERAL, self.pairs["definition"][0])
        self.assertIn(RECORD_LITERAL, self.pairs["definition"][1])

    def test_write_set_sample_is_the_live_text_without_the_item(self):
        # The live I.2.c text, with the one record item removed, contains the
        # whole pre-change write-set sample: the sample is a faithful base
        # excerpt of the same site, not an unrelated string.
        sample = self.pairs["I.2.c write set"][0].strip()
        remainder = _remove_record_item(self.live_i2c)
        self.assertIn(sample, remainder)


class TestModuleUsesOnlyStandardLibrary(unittest.TestCase):
    """AC-6 (NFR4): this module imports only the standard library and no
    other test module."""

    def test_imports_are_standard_library_only(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                imported.add("<relative import>")
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
