"""Tests for task0002/task0005 (batch-stop-contract): the develop-skill and
batch-mode pointer wiring for the batch terminal-line contract.

Covers task0005 Acceptance Criteria
(feature-docs/batch-stop-contract/tasks/task0005.md; task0005 is a round-1
rework of task0002's original module, extending it in place rather than
replacing it):

- AC-1 (FR5): the 「バッチ終端行」 subsection's stop enumeration additionally
  names Step A's feature-resolution failure and the phase abort taken on a
  second `commit-docs.sh` exit 4, each asserted marker by marker, alongside
  every marker the subsection already carried.
- AC-2 (FR6): the subsection states the no-line rule as a general rule over
  turns that end without the run reaching a terminal state, naming develop's
  停止条件 5 and implement's launch turn and wake turn as instances of that
  rule -- not, as task0002's original wording had it, as an exclusion of
  停止条件 5 alone. The strings 「停止条件 5」 and 「終端行を出力しない」 stay
  present.
- AC-3 (FR3): the subsection instructs the orchestrator to Read
  `${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` immediately
  before emitting the line and to use the prefix, field grammar and value
  sets defined there; `references/batch-mode.md`'s `## Terminal line`
  section carries an equivalent instruction naming the same document.
- AC-4 (FR3 partition, NFR2): neither `skills/develop/SKILL.md` nor
  `references/batch-mode.md` restates any contract literal -- the prefix
  literal, the four field names as a group, any of the ELEVEN reason codes
  fixed in IMPLEMENTATION.md, or the sentinel value -- and this module's own
  reason-code tuple lists all eleven (used for absence checks only).
- AC-5 (NFR2, FR4 non-regression): every Step C completion-report element
  this module already guards is still present with its current wording;
  every pinned heading and anchor sentence is unchanged; `batch-mode.md`'s
  Non-packet gates table still has ten data rows with its catch-all,
  diff-size and per-command wording intact (guarded indirectly: this module
  never touches that table, and a dedicated check below pins its row count);
  and `check-plugin-invariants.py` exits 0 against the repository root.
- AC-6 (FR8, NFR1, NFR4): this module is discovered by
  `python3 -m unittest discover -s tests`, imports the Python standard
  library only, and every matcher added by this task (task0005) carries a
  negative proof plus a non-vacuity guard; the five pre-existing AC-4 (now
  Step-C-regression) assertions remain exempt per Test Notes since they are
  pure regression guards over retained pre-change wording.

This is a documentation-contract task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following the
pattern established by tests/test_develop_skill_rewiring.py -- same target
files, independent helper functions (no cross-module import, matching that
module's own convention of self-contained helpers).

Extended again by develop-once-option/task0002 (a DIFFERENT feature from the
batch-stop-contract one above; task IDs collide across features by
coincidence, not by relationship). Covers develop-once-option task0002
Acceptance Criteria
(feature-docs/develop-once-option/tasks/task0002.md):

- AC-1 (FR9): the 「バッチ終端行」 subsection additionally states that a turn
  ending at a `--once` phase boundary is also a terminal-line output
  target, while every pre-existing guarantee (subsection placement, the
  Read-before-emit instruction, the last-line rule, the generalized
  no-line rule, the pre-existing stop-point enumeration) is unchanged.
- AC-2 (FR11): the old cardinality-pinning wording (「2 つの終端状態」) is
  gone from `skills/develop/SKILL.md`, and the replacement wording names no
  `state` value.
- AC-3 (FR9, NFR1): `batch-mode.md`'s `## Terminal line` section states the
  same `--once` phase-boundary occasion, with no value literal, keeping its
  Read-before-emit instruction naming the contract document.
- AC-4 (FR10): the literal guard is extended with a `state`-value shape
  check (D2) and applied whole-file (not just section-scoped) to both real
  files, with 0 violations.
- AC-5 (FR10, NFR3): forged SKILL.md and batch-mode.md excerpts that
  restate the new `--once` boundary state value are both rejected, each
  with a non-vacuity guard.
- AC-6 (FR10): `completed` / `skipped` / `stopped` used as ordinary step
  status in the real files never trip the extended guard -- proven with a
  non-vacuity check that the words actually occur.
- AC-7 (NFR2, NFR3): this module keeps importing the standard library only.

Extended again by develop-once-option/task0006 (review round 1 rework;
source findings 133dad87f620ed69, d19b6a0240c04f8d, 5a7d022d8ac79472).
Covers task0006 Acceptance Criteria
(feature-docs/develop-once-option/tasks/task0006.md):

- AC-1 (FR9, FR11, NFR3): the 「バッチ終端行」 subsection's opening definition
  sentence now states the output condition as "the run reached one of the
  SSOT's terminal states this turn" rather than additionally limiting it to
  "a turn that ends the run" -- the old double-limiting wording put the
  `--once` phase-boundary turn (which does not end the run) outside the
  definition's own words even though the enumeration further down already
  listed it.
- AC-2/AC-3/AC-6/AC-7: every other pre-existing guarantee this module pins
  for the subsection, `batch-mode.md`, and the whole-file literal guard is
  unchanged (regression only; no new assertions needed).
- AC-4/AC-5: `TestStateValueGuardWholeFileScope` no longer asserts that
  `stopped` is absent from the real files' text -- that assertion was never
  a contractual requirement and made the class's own whitelist claim
  (a whitelisted word appearing there would be harmless) permanently
  unfalsifiable for `stopped`. The whitelist behavior is instead proven
  directly against a synthetic sample containing `completed` / `skipped` /
  `stopped` as ordinary prose.

Extended again by develop-once-option/task0008 (verify rework, SC4's
emission-occasion half; IMPLEMENTATION.md D11). Covers task0008 Acceptance
Criteria (feature-docs/develop-once-option/tasks/task0008.md):

- AC-1/AC-2: `batch-mode.md`'s `## Terminal line` opening definition states
  the output condition as "a batch turn reaches one of the terminal states
  the contract SSOT defines", with normal completion, every terminating
  stop and a turn ending at a `--once` phase boundary named as occasions on
  which that condition holds -- not, as the pre-task0008 wording had it,
  "At the end of every batch run" with the `--once` boundary listed as a
  third item under a run-ending subject that boundary does not satisfy. The
  substring "a `--once` phase boundary" stays present (unchanged pre-
  existing test `test_section_covers_once_boundary_occasion`).
- AC-3: a new matcher, independent of SKILL.md's Japanese
  `_states_definition_condition_correctly` (D11 -- each pointer document
  states the rule in its own language with its own matcher, neither
  reusable across the two), carries its own negative proof (a forged
  section reproducing the old "At the end of every batch run" wording
  verbatim) and non-vacuity guard (the forged section is sliceable and
  genuinely names the contract document and the `--once` occasion).
- AC-4/AC-5/AC-6/AC-7: unaffected -- the contract-literal guard, the
  Read-before-emit instruction, the Non-packet gates table and SKILL.md are
  regression-guarded only (no new assertions needed beyond the pre-existing
  ones already in this module).

Matcher -> negative-proof inventory (task0008 addition):

- `_batch_mode_states_definition_condition_correctly` (AC-1/AC-2's
  batch-mode.md opening-definition matcher): negative proof is
  TestBatchModeDefinitionConditionMatcherCanFail.test_matcher_rejects_old_run_ending_definition
  (a forged `## Terminal line` section reproducing the pre-task0008
  "At the end of every batch run" wording verbatim), non-vacuity guard is
  TestBatchModeDefinitionConditionMatcherCanFail.test_forged_old_definition_is_well_formed_and_found.

Matcher -> negative-proof inventory (task0006 additions):

- `_states_definition_condition_correctly` (AC-1's opening-definition
  matcher): negative proof is
  TestDefinitionConditionMatcherCanFail.test_matcher_rejects_old_double_limiting_definition
  (a forged subsection reproducing the pre-task0006 「ランを終わらせるターン」
  double-limiting wording verbatim), non-vacuity guard is
  TestDefinitionConditionMatcherCanFail.test_forged_old_definition_is_well_formed_and_found.
- `TestStateValueGuardWholeFileScope.test_guard_does_not_flag_step_status_vocabulary_in_a_synthetic_sample`
  (AC-5) replaces the removed real-file `stopped`-absence assertion: a
  direct whitelist-behavior proof over a synthetic sample rather than a
  negative/non-vacuity pair, matching this class's pre-existing convention
  for the same reason (`stopped` does not occur in either real file, so a
  real-file non-vacuity proof for it would be vacuous).

Matcher -> negative-proof inventory (task0002 additions):

- The state-value shape extension to `_find_contract_literal_violations`
  (D2 rules 1 and 2): negative proof is
  TestStateValueMatcherCanFail (SKILL.md and batch-mode.md forged
  restatements of `state=phase_done`) and
  TestOnceBoundaryBareLiteralMatcherCanFail (a bare `phase_done` literal
  dodging the `state=` shape); each has a matching non-vacuity guard in the
  same class.
- `TestSkillMdNamesNoTerminalStateCount` (AC-2) is a pure regression guard
  over retained/removed wording (Test Notes) and is exempt from a negative
  proof, matching this module's own convention for that category.
- `TestStateValueGuardWholeFileScope` (AC-4/AC-6) is the whole-file
  false-positive proof plus non-vacuity check; it reuses the matcher
  negative-proofed above rather than introducing a new one.

Matcher -> negative-proof inventory (Test Notes):

- `_find_contract_literal_violations` (the contract-literal absence
  matcher, shared by both SKILL.md and batch-mode.md): negative proof is
  TestContractLiteralMatcherCanFail.test_matcher_rejects_the_forged_field_name_restatement
  (SKILL.md) and
  TestBatchModeLiteralMatcherCanFail.test_matcher_rejects_forged_reason_code_restatement
  (batch-mode.md); each has a matching non-vacuity guard in the same class.
- `_states_generalized_no_line_rule` (AC-2's generalization matcher):
  negative proof is
  TestNoLineGeneralizationMatcherCanFail.test_matcher_rejects_subsection_naming_stop_condition_5_only,
  non-vacuity guard is
  TestNoLineGeneralizationMatcherCanFail.test_forged_no_line_only_subsection_is_well_formed_and_found.
- `_has_read_instruction_for_contract_doc` (AC-3's SKILL.md Read-instruction
  matcher): negative proof is
  TestReadInstructionMatcherCanFail.test_matcher_rejects_doc_name_without_read_instruction,
  non-vacuity guard is
  TestReadInstructionMatcherCanFail.test_forged_doc_name_without_read_instruction_is_well_formed_and_found.
- AC-5's five Step C assertions (TestStepCCompletionReportNonRegression) are
  pure regression guards over retained pre-change wording (Test Notes) and
  are exempt from a negative proof, as are the pinned-heading/forbidden-
  literal assertions in TestExistingHeadingsAndForbiddenLiteralsUnchanged
  and the Non-packet gates row-count guard in
  TestBatchModeNonPacketGatesTableUnchanged.

Extended again by batch-structured-result-output/task0003 (SKILL.md's own
half of this contract is rewritten to describe the structured result
instead of a terminal line; `references/batch-mode.md` is OUT of this
task's scope and is asserted only for regression -- its own half of this
contract is task0002's, in a different worktree, and stays on the retired
"## Terminal line" / terminal-line wording throughout this task).
Covers task0003 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0003.md):

- AC-1/AC-2/AC-3/AC-4: `NEW_SUBSECTION_HEADING` is renamed to
  「## バッチ構造化結果」; the subsection states the result is the WHOLE
  final assistant message of a terminal turn (not a line appended to one),
  restates the no-result rule with 「構造化結果を出力しない」 replacing the
  retired 「終端行を出力しない」, and Step C's completion-report instruction
  states the batch audit items are carried in full inside the structured
  result's values (IMPLEMENTATION.md SC7) rather than appended as a line.
- AC-5: a new class, `TestImplementPhaseCitationUnchanged`, covers
  `implement-phase.md`'s single SSOT citation -- a pure regression guard,
  since that sentence never named a "line" and so needed no wording change.
- AC-6/AC-7: the forbidden-literal set (`REASON_CODES`, `FIELD_NAME_TOKENS`,
  `ORDINARY_REASON_VALUE`) is widened to IMPLEMENTATION.md SC5 (SC1's eight
  keys, the twelfth reason code `context_budget_reached`, and the ordinary
  word "none" checked by `reason={value}` shape rather than as a bare word
  -- the same false-positive rationale D2 already established for `state`).
  This widened matcher is reused unchanged for `batch-mode.md`'s (task0002,
  out of scope) sections, which continue to pass because that file's real
  text contains none of the new literals either (verified by inspection:
  no `state=`/`step=`/`reason=` shape, no `context_budget_reached`, no
  eight-field-name group).

Matcher -> negative-proof inventory (task0003 additions):

- The `reason={value}` shape check for the ordinary word "none": negative
  proof is
  TestReasonNoneShapeMatcherCanFail.test_matcher_rejects_forged_reason_none_shape,
  non-vacuity guard is
  TestReasonNoneShapeMatcherCanFail.test_forged_excerpt_is_well_formed_and_found.
  The whitelist behavior (bare "none" as ordinary prose never flagged) is
  proven directly in
  TestStateValueGuardWholeFileScope.test_guard_does_not_flag_the_ordinary_word_none,
  with non-vacuity in
  TestStateValueGuardWholeFileScope.test_ordinary_none_word_actually_occurs_in_the_real_files
  (matching this module's pre-existing convention for `state`'s whitelist
  proof).
- `TestOwnReasonCodeTupleIsTwelve` and the eight-field forgery in
  `TestContractLiteralMatcherCanFail` are pure updates to already
  negative-proofed matchers (Test Notes: a matcher whose SHAPE is unchanged
  and whose domain is merely widened does not need a second negative proof
  beyond the existing one, now exercised against the widened domain).
- `TestImplementPhaseCitationUnchanged` is a pure regression guard (Test
  Notes) and is exempt from a negative proof, per the module's own
  established convention (e.g. TestStepCCompletionReportNonRegression).

Extended again by batch-structured-result-output/task0007 (review round 1
rework; finding d48f305d463a7feb; IMPLEMENTATION.md SC10). Covers task0007
Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0007.md):

- AC-1/AC-5: 「## バッチ構造化結果」 gains a general statement of the
  terminal-turn message-boundary rule -- the last assistant message of
  EVERY terminal turn carries the structured result and nothing else, and
  every prose report the turn owes is emitted in the message(s) before it
  -- rather than the rule being carried only by the cap-reached run's own
  paragraph. This module carries the binding assertion (D5: SKILL.md is
  this task's own file) via
  `TestBatchTerminalLineSubsectionWiring.test_subsection_states_general_message_boundary_rule`.
- AC-3: `tests/test_verify_cap_run_continuation.py` (a different module,
  not edited here) gains its own lighter assertion for the same general
  rule, keeping its existing cap-specific assertions; this module's binding
  assertion above is the one D5 requires for SKILL.md.

Matcher -> negative-proof inventory (task0007 addition):

- `_states_terminal_turn_message_boundary_general_rule` (SC10 general-rule
  matcher): negative proof is
  TestGeneralRuleMatcherCanFail.test_matcher_rejects_cap_reached_paragraph_alone
  (a forged section carrying the heading, the Read-before-emit instruction
  and the cap-reached run's own pinned sentences, but not the general
  rule's every-terminal-turn subject statement), non-vacuity guard is
  TestGeneralRuleMatcherCanFail.test_forged_cap_only_section_is_well_formed_and_found.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

NEW_SUBSECTION_HEADING = "## バッチ構造化結果"
FILE_END_MARKER = "$ARGUMENTS"

IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — か、cap 到達により verify が `failed` のまま残る場合のみ）"
)
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"

# batch-structured-result-output task0002 (out-of-scope minimal fix; see
# feature-docs/batch-structured-result-output/tasks/task0002.md deviations):
# `batch-mode.md`'s "## Terminal line" heading is renamed "## Structured
# result" by that task (A2: the retired term "terminal line" no longer
# names any section). This is a slice-boundary constant only -- every
# content assertion below (contract-doc reference, Read instruction,
# literal absence, once-boundary occasion, opening-definition wording) is
# unaffected and continues to hold against the renamed section's real text.
TERMINAL_LINE_HEADING = "## Structured result"
REPORTING_HEADING = "## Reporting"
NON_PACKET_GATES_HEADING = "## Non-packet gates"
BATCH_BLOCK_HEADING = "## workflow.yaml `batch` block"

CONTRACT_DOC_REFERENCE = "references/batch-terminal-line.md"
CONTRACT_DOC_PLUGIN_ROOT_REFERENCE = (
    "${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md"
)

# The contract's literals (IMPLEMENTATION.md Shared Components SC5 --
# batch-structured-result-output), which a pointer document may name the
# *document* for but must never restate itself (SSOT partition,
# IMPLEMENTATION.md Conventions). SC5 is the union of: SC1's eight field-
# name tokens (checked as a GROUP below, same false-positive rationale as
# the pre-existing four-field group check), every `reason` code (the
# original eleven plus the twelfth, `context_budget_reached`, D8), the
# `no-step` step-value sentinel, every `state` value (by shape), and the
# removed SC6 prefix literal. This tuple is used for absence checks only --
# it does not assert that the contract document (task0001's file) defines
# all twelve, since that file may or may not have merged yet in this
# worktree (D9/D5 cross-task safety).
REASON_CODES = (
    "step_stuck",
    "step_needs_intervention",
    "workflow_yaml_unparseable",
    "git_setup_aborted",
    "gate_fail_closed",
    "gate_option_unavailable",
    "implement_task_failed",
    "verify_rework_cap_reached",
    "completion_aborted",
    "feature_resolution_aborted",
    "docs_commit_conflict_aborted",
    "context_budget_reached",
)
FIELD_NAME_TOKENS = (
    "`state`",
    "`step`",
    "`reason`",
    "`detail`",
    "`feature`",
    "`branch`",
    "`pr_url`",
    "`resume_conditions`",
)
PREFIX_LITERAL = "EM_WORKFLOW_TERMINAL:"
SENTINEL_VALUE = "no-step"
# SC5's `reason` domain also includes the ordinary English word "none" --
# unlike the other eleven/twelve codes (unique snake_case tokens, safe as a
# bare substring), "none" is common prose (it already occurs in both real
# pointer documents outside any contract citation), so it is checked by the
# same `key={value}` shape convention D2 established for `state` values
# below, never as a bare word.
ORDINARY_REASON_VALUE = "none"

# IMPLEMENTATION.md (develop-once-option) D1/D2: the `state` domain once the
# `--once` phase boundary adds a third value. Declared locally for absence
# checks ONLY (D2, and this module's own cross-task-safety convention above
# for REASON_CODES) -- this module never asserts that any contract document
# DEFINES `phase_done`; that is task0003's document, which may not have
# merged into this worktree yet.
STATE_DOMAIN = ("completed", "stopped", "phase_done")
# The `--once` boundary's value: contract-only vocabulary occurring nowhere
# else in either pointer document (D2 rule 2), so a bare-literal check adds
# no false-positive surface.
ONCE_BOUNDARY_STATE_VALUE = "phase_done"

# feature-docs/develop-once-option/tasks/task0006.md AC-1: the opening
# definition sentence of 「## バッチ終端行」 must state the output condition
# as "the run reached one of the SSOT's terminal states this turn" and must
# NOT additionally limit it to "a turn that ends the run" -- the old
# double-limiting wording put the `--once` phase-boundary turn (which does
# not end the run) outside the definition's own words, even though the
# enumeration further down already lists it as a target.
DEFINITION_CONDITION_PHRASE = "ランが同 SSOT の定める終端状態に達した"
OLD_RUN_ENDING_TURN_PHRASE = "ランを終わらせるターン"

# feature-docs/develop-once-option/tasks/task0008.md AC-1/AC-2:
# `batch-mode.md`'s `## Terminal line` opening definition must state the
# output condition as "a batch turn reaches one of the terminal states the
# contract SSOT defines" and must NOT state "At the end of every batch
# run" -- the old wording's subject was the run's end, with the `--once`
# phase-boundary turn (which does not end the run) listed as a third
# occasion under that same run-ending subject (IMPLEMENTATION.md D11).
# Independent of `_states_definition_condition_correctly` /
# DEFINITION_CONDITION_PHRASE / OLD_RUN_ENDING_TURN_PHRASE above: D11 has
# each pointer document state the rule in its own language, with its own
# matcher -- neither is reusable across the two documents.
BATCH_MODE_DEFINITION_CONDITION_PHRASE = "reaches one of the terminal states"
BATCH_MODE_OLD_RUN_ENDING_PHRASE = "At the end of every batch run"

# IMPLEMENTATION.md D7's forbidden-literal list, restricted to the items
# applicable to skills/develop/SKILL.md (items 2 and 5 name batch-mode.md
# only and are out of this file's scope).
FORBIDDEN_DECISION_TABLE_PATTERNS = ("decision table", "決定表")
FORBIDDEN_STALE_AGENT_NAME = "requirements-spec-creator"
FORBIDDEN_STALE_INLINE_PHRASE = "Read してインラインで従う"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): this document
    # hard-wraps Japanese prose without a space at the break point, so
    # collapsing to a single space would inject whitespace the source never
    # had and break substring matches that span a wrap (same rationale as
    # tests/test_develop_skill_rewiring.py's helper of the same name).
    return re.sub(r"\s+", "", text)


def _find_contract_literal_violations(text):
    """The contract-literal absence matcher (AC-4): returns a list of
    human-readable violation descriptions if `text` restates any of the
    contract's literals, empty when none is restated. Shared by both
    SKILL.md and batch-mode.md checks below. The four field names are
    checked as a GROUP (all four backticked together) rather than as
    individual words, since `step` alone is ordinary vocabulary both
    documents already use for workflow steps -- checking it in isolation
    would false-positive on unrelated prose.

    develop-once-option/task0002 (D2) extension: checks the `state` domain
    by SHAPE rather than bare word, for the same false-positive reason --
    `completed` / `stopped` / `skipped` are ordinary `workflow.yaml`
    step-status vocabulary in both pointer documents and must never be
    flagged (AC-6). Rule 1: the contract-specific `state={value}` form (this
    substring check already covers bare, backticked and quoted spellings,
    since backticks/quotes only wrap the substring rather than interleave
    it). Rule 2: the `--once` boundary value's bare literal, which is
    contract-only vocabulary appearing nowhere else, so without this a
    pointer document could restate the value while dodging rule 1 (e.g.
    'the state becomes phase_done' with no `state=` prefix).

    batch-structured-result-output/task0003 (SC5) extension: the
    field-name-token group is widened from four to SC1's full eight keys
    (still an ALL-of-group check, so an isolated ordinary word like
    `` `feature` `` never trips it), the reason-code set gains the twelfth
    code (`context_budget_reached`, a unique snake_case token safe as a
    bare substring), and the ordinary word "none" -- also part of SC5's
    `reason` domain -- is checked by the `reason={value}` shape only, for
    the same false-positive reason as `state`."""
    violations = []
    if PREFIX_LITERAL in text:
        violations.append(f"prefix literal {PREFIX_LITERAL!r} restated")
    if all(token in text for token in FIELD_NAME_TOKENS):
        violations.append("all eight field-name tokens restated together")
    for code in REASON_CODES:
        if code in text:
            violations.append(f"reason code {code!r} restated")
    if SENTINEL_VALUE in text:
        violations.append(f"sentinel value {SENTINEL_VALUE!r} restated")
    for value in STATE_DOMAIN:
        shape = f"state={value}"
        if shape in text:
            violations.append(f"state-value shape {shape!r} restated")
    if ONCE_BOUNDARY_STATE_VALUE in text:
        violations.append(
            f"once-boundary state value {ONCE_BOUNDARY_STATE_VALUE!r} restated"
        )
    reason_none_shape = f"reason={ORDINARY_REASON_VALUE}"
    if reason_none_shape in text:
        violations.append(f"reason-value shape {reason_none_shape!r} restated")
    return violations


def _states_generalized_no_line_rule(text):
    """AC-2's generalization matcher: true iff `text` states the no-result
    rule generally -- keeping the 停止条件 5 / 構造化結果を出力しない anchors
    that already proved the original (task0002) wait-turn guarantee, restated
    by task0003 for the structured result (`構造化結果を出力しない` replaces
    the retired `終端行を出力しない`) -- AND additionally names implement's
    launch turn and wake turn as further instances of the same rule, rather
    than stopping at 停止条件 5 alone (task0002's narrower wording, which is
    exactly what the negative proof below forges). All four are required
    together."""
    stripped = _strip_ws(text)
    return (
        "停止条件 5" in text
        and "構造化結果を出力しない" in text
        and _strip_ws("launch ターン") in stripped
        and _strip_ws("wake ターン") in stripped
    )


def _has_read_instruction_for_contract_doc(text, doc_reference):
    """AC-3's Read-instruction matcher: true iff `text` names
    `doc_reference` AND pairs it with an explicit Read instruction --
    naming the document alone (task0002's original wording for SKILL.md,
    and the pre-task0005 wording for batch-mode.md) is not enough, since
    that is exactly what a consumer with no instruction to open the file
    would still see. `doc_reference` is parameterized so the same matcher
    serves both SKILL.md's `${CLAUDE_PLUGIN_ROOT}`-prefixed convention and
    batch-mode.md's bare-relative-path convention."""
    return doc_reference in text and "Read" in text


def _states_definition_condition_correctly(text):
    """AC-1's opening-definition matcher (task0006): true iff `text` states
    the terminal-line output condition as "the run reached one of the
    SSOT's terminal states this turn" AND does not additionally limit that
    condition to "a turn that ends the run" (task0006's fix -- the old
    double-limiting wording, since a `--once` phase-boundary turn does not
    end the run)."""
    stripped = _strip_ws(text)
    return (
        _strip_ws(DEFINITION_CONDITION_PHRASE) in stripped
        and OLD_RUN_ENDING_TURN_PHRASE not in text
    )


def _batch_mode_states_definition_condition_correctly(text):
    """AC-1/AC-2's opening-definition matcher for batch-mode.md's
    `## Terminal line` (task0008): true iff `text` states the terminal-line
    output condition as "a batch turn reaches one of the terminal states
    [the contract SSOT] defines" AND does not state the old run-ending
    wording ("At the end of every batch run"). The English counterpart of
    `_states_definition_condition_correctly` above, kept as an independent
    matcher per D11 (each pointer document states the rule in its own
    language, with its own matcher)."""
    return (
        BATCH_MODE_DEFINITION_CONDITION_PHRASE in text
        and BATCH_MODE_OLD_RUN_ENDING_PHRASE not in text
    )


def _states_terminal_turn_message_boundary_general_rule(section):
    """SC10 general-rule matcher (batch-structured-result-output/task0007;
    IMPLEMENTATION.md Shared Components SC10, review round 1 finding
    d48f305d463a7feb): true iff `section` states the message-boundary rule
    as a rule whose SUBJECT is the set of every terminal turn -- not the
    cap-reached run's own paragraph alone -- covering (a) that the last
    assistant message carries the structured result and nothing else, and
    (b) that every prose report the turn owes is emitted in the message(s)
    before it. Anchored on the general-subject phrase so a section stating
    the rule only inside the cap-reached run's own paragraph does not
    satisfy it (Test Notes edge case: "it must not be satisfied by the
    cap-reached paragraph alone"). Checked via `_strip_ws` (not a bare
    substring check): this document hard-wraps Japanese prose without a
    space at the break point, and the third phrase below straddles one in
    the real file."""
    stripped = _strip_ws(section)
    return (
        _strip_ws("終端状態に達したすべてのターン") in stripped
        and _strip_ws("それ以外の内容を一切含まない") in stripped
        and _strip_ws("この最後のメッセージより前のメッセージで出力する") in stripped
    )


class TestBatchTerminalLineSubsectionWiring(unittest.TestCase):
    """AC-1, AC-2, and Design item 4 (Step C pointer line)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, NEW_SUBSECTION_HEADING, FILE_END_MARKER)
        cls.step_c_section = _section(cls.text, STEP_C_HEADING, STOP_REPORT_HEADING)

    def test_subsection_heading_is_present(self):
        self.assertIn(NEW_SUBSECTION_HEADING, self.text)

    def test_subsection_is_placed_immediately_after_stop_report_section(self):
        stop_report_idx = self.text.index(STOP_REPORT_HEADING)
        subsection_idx = self.text.index(NEW_SUBSECTION_HEADING)
        self.assertLess(
            stop_report_idx,
            subsection_idx,
            "the batch terminal-line subsection must follow the existing "
            "stop-report section",
        )
        between = self.text[stop_report_idx + len(STOP_REPORT_HEADING) : subsection_idx]
        self.assertNotIn(
            "\n## ",
            between,
            "no other level-2 heading may sit between the stop-report "
            "section and the new subsection",
        )

    def test_subsection_names_the_contract_document(self):
        self.assertIn(CONTRACT_DOC_REFERENCE, self.section)

    def test_subsection_states_result_is_whole_final_message(self):
        # FR2 (task0003): the structured result is the WHOLE final assistant
        # message of the turn that reaches a terminal state -- not a line
        # appended to it.
        self.assertIn(
            _strip_ws("最後の assistant メッセージの全体を構造化結果とする"),
            _strip_ws(self.section),
        )

    def test_subsection_covers_normal_completion(self):
        self.assertIn("Step C の完了処理", self.section)
        self.assertIn("通常完了", self.section)

    def test_subsection_covers_the_terminating_stops(self):
        for marker in (
            "停止条件 2",
            "停止条件 3",
            "停止条件 4",
            "停止条件 6",
            "フェーズ内のゲート中断",
            "Step C 内の中断",
        ):
            self.assertIn(marker, self.section)
        self.assertIn(
            _strip_ws("implement / verify フェーズが定める終端停止"),
            _strip_ws(self.section),
        )

    def test_subsection_covers_step_a_and_docs_commit_conflict_stops(self):
        # AC-1 (task0005): the two stops finding 0637708c55c7f230 /
        # 0637708c55c7f231 identified as missing from the enumeration.
        self.assertIn("Step A の feature 解決失敗", self.section)
        self.assertIn(
            _strip_ws("commit-docs.sh の 2 回目の exit 4 によるフェーズ中断"),
            _strip_ws(self.section),
        )

    def test_subsection_states_wait_turn_emits_no_result(self):
        self.assertIn("停止条件 5", self.section)
        self.assertIn("構造化結果を出力しない", self.section)

    def test_no_line_rule_is_generalized_over_non_terminal_turn_ends(self):
        # AC-2 (task0005, finding 55903a56e01e5125): not just 停止条件 5 --
        # implement's launch turn and wake turn are named as further
        # instances of the same general rule.
        self.assertTrue(
            _states_generalized_no_line_rule(self.section),
            "expected the no-line rule to be stated generally over turns "
            "ending without the run reaching a terminal state, naming "
            "implement's launch turn and wake turn alongside 停止条件 5",
        )

    def test_subsection_states_general_message_boundary_rule(self):
        # AC-1/AC-5 (batch-structured-result-output/task0007, SC10, D5's
        # binding assertion -- SKILL.md is this task's own file): the
        # message-boundary rule is stated as a rule over EVERY terminal
        # turn, not only the cap-reached run's own paragraph.
        self.assertTrue(
            _states_terminal_turn_message_boundary_general_rule(self.section),
            "expected the general SC10 rule -- subject: every terminal "
            "turn -- stated in addition to the cap-reached run's own "
            "paragraph",
        )

    def test_subsection_instructs_reading_the_contract_doc_before_emitting(self):
        # AC-3 (task0005, finding 6a1c9f2d84be3057).
        self.assertTrue(
            _has_read_instruction_for_contract_doc(
                self.section, CONTRACT_DOC_PLUGIN_ROOT_REFERENCE
            ),
            "expected an instruction to Read the plugin-root-prefixed "
            "contract document immediately before emitting the line",
        )

    def test_step_c_report_item_points_at_structured_result(self):
        # AC-4 (task0003): the audit items are carried IN FULL inside the
        # structured result's values (IMPLEMENTATION.md SC7), not appended
        # as a line after the report -- the report is emitted first, and
        # the structured result is the message that follows it (FR2).
        self.assertIn(CONTRACT_DOC_REFERENCE, self.step_c_section)
        self.assertIn(
            _strip_ws(
                "これらの監査項目は、この報告に続けて出す構造化結果の値の"
                "中に全文で運ぶ"
            ),
            _strip_ws(self.step_c_section),
        )

    def test_subsection_covers_once_boundary_occasion(self):
        # AC-1 (develop-once-option/task0002): the subsection additionally
        # states that a turn ending at a `--once` phase boundary is also a
        # terminal-line output target ("when", not the boundary's own
        # definition -- that stays owned by the section task0001 writes).
        self.assertIn(
            _strip_ws("`--once` のフェーズ境界で終わるターン"),
            _strip_ws(self.section),
        )


# Forged sample for AC-5 (SC10, batch-structured-result-output/task0007):
# carries the subsection heading, the Read-before-emit instruction and the
# cap-reached run's own pinned sentences (Test Notes non-vacuity: "the
# forged section is otherwise well formed -- it carries the heading, the
# Read-before-emit instruction and the cap-specific sentences"), WITHOUT the
# general rule's every-terminal-turn subject statement (Test Notes edge
# case: "it must not be satisfied by the cap-reached paragraph alone").
FORGED_CAP_REACHED_ONLY_SECTION = (
    f"{NEW_SUBSECTION_HEADING}\n\n"
    "出力の直前に `${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` "
    "を Read し、そこに定義されたキーの集合・順序・値の集合をそのまま使う。\n\n"
    "cap 到達走行（stop point `verify-rework-cap`）は、Step C の完了処理まで"
    "到達し worktree 掃除と終了報告を完了させたうえで、通常完了ではなく"
    "停止として構造化結果を出す。cap 到達走行の実行した step は verify で"
    "ある。構造化結果は 1 走行につき 1 件出力し、cap 到達走行では Step C の"
    "完了報告を先に出力してから、その直後の最後の assistant メッセージとして"
    "構造化結果を出す。"
)


class TestGeneralRuleMatcherCanFail(unittest.TestCase):
    """AC-5 (SC10, batch-structured-result-output/task0007): negative proof
    + non-vacuity guard for
    `_states_terminal_turn_message_boundary_general_rule`."""

    def test_matcher_rejects_cap_reached_paragraph_alone(self):
        self.assertFalse(
            _states_terminal_turn_message_boundary_general_rule(
                FORGED_CAP_REACHED_ONLY_SECTION
            )
        )

    def test_forged_cap_only_section_is_well_formed_and_found(self):
        self.assertIn(NEW_SUBSECTION_HEADING, FORGED_CAP_REACHED_ONLY_SECTION)
        self.assertTrue(
            _has_read_instruction_for_contract_doc(
                FORGED_CAP_REACHED_ONLY_SECTION, CONTRACT_DOC_PLUGIN_ROOT_REFERENCE
            ),
            "forged sample must carry the Read-before-emit instruction",
        )
        self.assertIn(
            _strip_ws("構造化結果は 1 走行につき 1 件出力し"),
            _strip_ws(FORGED_CAP_REACHED_ONLY_SECTION),
        )


class TestBatchTerminalLineDefinitionCondition(unittest.TestCase):
    """AC-1 (task0006, review round 1 finding 133dad87f620ed69): the opening
    definition sentence of 「## バッチ終端行」 states the output condition as
    "the run reached one of the SSOT's terminal states this turn" and no
    longer additionally limits it to "a turn that ends the run" -- the old
    double-limiting wording that put the `--once` phase-boundary turn
    (which does not end the run) outside the definition's own words even
    though the enumeration further down already lists it as a target."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, NEW_SUBSECTION_HEADING, FILE_END_MARKER)

    def test_definition_states_terminal_state_condition_without_old_limit(self):
        self.assertTrue(
            _states_definition_condition_correctly(self.section),
            "expected the opening definition to state the terminal-state "
            "condition without the old run-ending-turn limiting phrase",
        )


class TestDefinitionConditionMatcherCanFail(unittest.TestCase):
    """AC-1 / Test Notes (task0006): negative proof plus non-vacuity guard
    for `_states_definition_condition_correctly` -- a forged subsection
    reproducing the pre-task0006 double-limiting wording verbatim (`ランを
    終わらせるターン（Step C の完了処理、または下記に列挙する終端の停止条件で
    終わるターン）`)."""

    FORGED_OLD_DEFINITION_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "`--batch` 実行では、ランを終わらせるターン（Step C の完了処理、"
        "または下記に列挙する終端の停止条件で終わるターン）が、最後の "
        "assistant メッセージの末尾に終端行を 1 行出力する。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_old_definition_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds it, and it genuinely carries
        # the old limiting phrase -- so the rejection below exercises the
        # limiting-phrase check, not a slicing or fixture defect.
        section = _section(
            self.FORGED_OLD_DEFINITION_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn(OLD_RUN_ENDING_TURN_PHRASE, section)

    def test_matcher_rejects_old_double_limiting_definition(self):
        section = _section(
            self.FORGED_OLD_DEFINITION_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertFalse(
            _states_definition_condition_correctly(section),
            "matcher failed to detect the old run-ending-turn limiting phrase",
        )


class TestSkillMdNamesNoTerminalStateCount(unittest.TestCase):
    """AC-2 (FR11, develop-once-option/task0002): SKILL.md no longer pins
    the terminal-state count at two -- a third state (`phase_done`) now
    exists once `--once` is wired, so a document naming a fixed count of
    two would become false. The Contract SSOT owns the count; every other
    document refers to the set without naming it (IMPLEMENTATION.md D4).
    Pure regression guard over retained/removed wording (Test Notes),
    exempt from a negative proof."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_old_fixed_terminal_state_count_wording_is_gone(self):
        self.assertNotIn(_strip_ws("2 つの終端状態"), _strip_ws(self.text))

    def test_replacement_wording_present(self):
        self.assertIn(
            _strip_ws("同 SSOT が定める終端状態のいずれか"),
            _strip_ws(self.text),
        )

    def test_replacement_names_no_state_value(self):
        # Subsumed by TestStateValueGuardWholeFileScope but re-asserted
        # directly here as the AC-2-specific regression guard, since AC-2's
        # wording explicitly requires the replacement to name no `state`
        # value (not merely to drop the count).
        self.assertEqual(_find_contract_literal_violations(self.text), [])


class TestNoLineGeneralizationMatcherCanFail(unittest.TestCase):
    """AC-2 / Test Notes (a): negative proof plus non-vacuity guard for
    `_states_generalized_no_line_rule` -- a forged subsection that names
    only 停止条件 5, matching task0002's pre-rework wording (restated here in
    task0003's post-rename terminology, 構造化結果, since the rule under test
    is the GENERALIZATION scope, not the retired term itself)."""

    FORGED_NO_LINE_ONLY_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "停止条件 5（implementer の完了通知待ち）でターンを終える場合は、"
        "ラン自体は継続しているため構造化結果を出力しない。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_no_line_only_subsection_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds it, and it genuinely carries
        # both pre-existing anchors -- so the rejection below exercises the
        # generalization requirement, not a slicing or fixture defect.
        section = _section(
            self.FORGED_NO_LINE_ONLY_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn("停止条件 5", section)
        self.assertIn("構造化結果を出力しない", section)

    def test_matcher_rejects_subsection_naming_stop_condition_5_only(self):
        section = _section(
            self.FORGED_NO_LINE_ONLY_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertFalse(
            _states_generalized_no_line_rule(section),
            "matcher failed to detect the un-generalized (停止条件 5 only) wording",
        )


class TestReadInstructionMatcherCanFail(unittest.TestCase):
    """AC-3 / Test Notes (b): negative proof plus non-vacuity guard for
    `_has_read_instruction_for_contract_doc` -- a forged subsection that
    names the plugin-root-prefixed contract document but issues no Read
    instruction for it."""

    FORGED_DOC_NAME_WITHOUT_READ_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "値の集合は `${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` "
        "を唯一の SSOT とする。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_doc_name_without_read_instruction_is_well_formed_and_found(self):
        section = _section(
            self.FORGED_DOC_NAME_WITHOUT_READ_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn(CONTRACT_DOC_PLUGIN_ROOT_REFERENCE, section)

    def test_matcher_rejects_doc_name_without_read_instruction(self):
        section = _section(
            self.FORGED_DOC_NAME_WITHOUT_READ_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertFalse(
            _has_read_instruction_for_contract_doc(
                section, CONTRACT_DOC_PLUGIN_ROOT_REFERENCE
            ),
            "matcher failed to detect the missing Read instruction",
        )


class TestOwnReasonCodeTupleIsTwelve(unittest.TestCase):
    """AC-4/AC-6 (task0005/D9, extended by task0003/D8/SC5): this module's
    own `REASON_CODES` tuple -- used for absence checks only, never asserted
    against the contract document itself (D9/D5 cross-task safety) -- lists
    all twelve codes: the original eleven plus the twelfth,
    `context_budget_reached` (D8: reserved by the consumer, documented but
    never emitted by em-workflow)."""

    def test_reason_codes_tuple_has_twelve_members(self):
        self.assertEqual(len(REASON_CODES), 12)

    def test_reason_codes_tuple_includes_the_two_rework_codes(self):
        self.assertIn("feature_resolution_aborted", REASON_CODES)
        self.assertIn("docs_commit_conflict_aborted", REASON_CODES)

    def test_reason_codes_tuple_includes_context_budget_reached(self):
        self.assertIn("context_budget_reached", REASON_CODES)

    def test_reason_codes_tuple_has_no_duplicates(self):
        self.assertEqual(len(REASON_CODES), len(set(REASON_CODES)))


class TestSubsectionRestatesNoContractLiteral(unittest.TestCase):
    """AC-4: the new subsection restates none of the contract's literals.
    `_find_contract_literal_violations` is the matcher; the negative proof
    and non-vacuity guard live in TestContractLiteralMatcherCanFail below."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, NEW_SUBSECTION_HEADING, FILE_END_MARKER)

    def test_subsection_restates_no_contract_literal(self):
        self.assertEqual(_find_contract_literal_violations(self.section), [])

    def test_prefix_literal_absent_from_whole_skill_md(self):
        # D6 (IMPLEMENTATION.md): the prefix's single-file property -- it
        # may appear under em-workflow/ in exactly one file, the contract
        # document itself, never a pointer document.
        self.assertNotIn(PREFIX_LITERAL, self.text)


class TestContractLiteralMatcherCanFail(unittest.TestCase):
    """AC-4 / Test Notes: negative proof plus non-vacuity guard for the
    contract-literal absence matcher -- a forged subsection that restates
    all eight field names (SC1), run through the same slicer used above."""

    FORGED_FULL_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "構造化結果は `state` / `step` / `reason` / `detail` / `feature` / "
        "`branch` / `pr_url` / `resume_conditions` の 8 キーを持つ。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_restatement_is_a_well_formed_subsection_the_slicer_finds(self):
        # Non-vacuity guard: the slicer finds it, and the forged sentence
        # genuinely carries all eight field-name tokens -- so the rejection
        # below exercises the comparison, not a slicing or fixture defect.
        section = _section(
            self.FORGED_FULL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn("8 キーを持つ", section)
        self.assertTrue(all(token in section for token in FIELD_NAME_TOKENS))

    def test_matcher_rejects_the_forged_field_name_restatement(self):
        section = _section(
            self.FORGED_FULL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        violations = _find_contract_literal_violations(section)
        self.assertTrue(violations, "matcher failed to detect the forged restatement")


class TestBatchModeTerminalLineWiring(unittest.TestCase):
    """AC-3 and AC-4, batch-mode.md half: `## Terminal line` names the
    contract document, instructs reading it before emitting, and restates
    none of its literals."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.section = _section(cls.text, TERMINAL_LINE_HEADING, REPORTING_HEADING)

    def test_section_names_the_contract_document(self):
        self.assertIn(CONTRACT_DOC_REFERENCE, self.section)

    def test_section_instructs_reading_the_contract_doc_before_emitting(self):
        # AC-3 (task0005, finding 6a1c9f2d84be3057): the batch-mode.md half
        # of the same instruction, naming the document via this file's own
        # bare-relative-path convention (matching its pre-existing mention
        # in this same section) rather than SKILL.md's ${CLAUDE_PLUGIN_ROOT}
        # convention.
        self.assertTrue(
            _has_read_instruction_for_contract_doc(self.section, CONTRACT_DOC_REFERENCE),
            "expected an instruction to Read the contract document "
            "immediately before emitting the line",
        )

    def test_section_restates_no_contract_literal(self):
        self.assertEqual(_find_contract_literal_violations(self.section), [])

    def test_prefix_literal_absent_from_whole_batch_mode_md(self):
        # D6 (IMPLEMENTATION.md): the prefix's single-file property.
        self.assertNotIn(PREFIX_LITERAL, self.text)

    def test_section_covers_once_boundary_occasion(self):
        # AC-3 (develop-once-option/task0002, D8): the occasion list is
        # extended to include a turn ending at a `--once` phase boundary,
        # stated as an occasion only -- no value literal, no field grammar.
        self.assertIn("a `--once` phase boundary", self.section)


class TestBatchModeTerminalLineDefinitionCondition(unittest.TestCase):
    """AC-1/AC-2 (task0008, verify rework SC4 / IMPLEMENTATION.md D11):
    `## Terminal line`'s opening definition states the output condition as
    "a batch turn reaches one of the terminal states the contract SSOT
    defines" and no longer states "At the end of every batch run" -- the
    old wording's subject was the run's end, with the `--once`
    phase-boundary turn (which does not end the run) listed as a third
    occasion under that same run-ending subject."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.section = _section(cls.text, TERMINAL_LINE_HEADING, REPORTING_HEADING)

    def test_definition_states_terminal_state_condition_without_old_wording(self):
        self.assertTrue(
            _batch_mode_states_definition_condition_correctly(self.section),
            "expected the opening definition to state the terminal-state "
            "condition without the old 'At the end of every batch run' "
            "wording",
        )


class TestBatchModeDefinitionConditionMatcherCanFail(unittest.TestCase):
    """AC-3 (task0008): negative proof plus non-vacuity guard for
    `_batch_mode_states_definition_condition_correctly` -- a forged
    `## Terminal line` section reproducing the pre-task0008 run-ending
    definition verbatim ("At the end of every batch run — on normal
    completion, on every terminating stop, and on a turn that ends at a
    `--once` phase boundary —")."""

    FORGED_OLD_TERMINAL_LINE_TEXT = (
        "...\n\n"
        f"{TERMINAL_LINE_HEADING}\n\n"
        "At the end of every batch run — on normal completion, on every "
        "terminating stop, and on a turn that ends at a `--once` phase "
        "boundary — the final assistant message carries a machine-readable "
        "terminal line as its last line. "
        f"`{CONTRACT_DOC_REFERENCE}` is the sole owner of that line's "
        "format and is referenced here rather than restated.\n\n"
        f"{REPORTING_HEADING}\n"
    )

    def test_forged_old_definition_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds it, and it genuinely names the
        # contract document and the `--once` occasion -- so the rejection
        # below exercises the definition-condition check, not a slicing or
        # fixture defect.
        section = _section(
            self.FORGED_OLD_TERMINAL_LINE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        self.assertIn(CONTRACT_DOC_REFERENCE, section)
        self.assertIn("a `--once` phase boundary", section)

    def test_matcher_rejects_old_run_ending_definition(self):
        section = _section(
            self.FORGED_OLD_TERMINAL_LINE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        self.assertFalse(
            _batch_mode_states_definition_condition_correctly(section),
            "matcher failed to detect the old 'At the end of every batch "
            "run' definition",
        )


class TestBatchModeLiteralMatcherCanFail(unittest.TestCase):
    """AC-4 / Test Notes (c): the batch-mode.md literal-absence matcher
    (the same `_find_contract_literal_violations` function used for
    SKILL.md above) reused against a forged `## Terminal line` body that
    restates a reason code."""

    FORGED_TERMINAL_LINE_TEXT = (
        "...\n\n"
        f"{TERMINAL_LINE_HEADING}\n\n"
        "On a terminating stop the line's `reason` field is one of "
        "step_stuck, gate_fail_closed, or another closed-set code.\n\n"
        f"{REPORTING_HEADING}\n"
    )

    def test_forged_body_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds it, and it genuinely carries
        # a reason code -- so the rejection below exercises the comparison,
        # not a slicing or fixture defect.
        section = _section(
            self.FORGED_TERMINAL_LINE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        self.assertIn("step_stuck", section)
        self.assertIn("gate_fail_closed", section)

    def test_matcher_rejects_forged_reason_code_restatement(self):
        section = _section(
            self.FORGED_TERMINAL_LINE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        violations = _find_contract_literal_violations(section)
        self.assertTrue(violations, "matcher failed to detect the forged restatement")


class TestStateValueMatcherCanFail(unittest.TestCase):
    """AC-5 (develop-once-option/task0002): negative proof plus non-vacuity
    guard for the D2 state-value shape extension -- forged SKILL.md and
    batch-mode.md excerpts that restate the new `--once` boundary state
    value in the contract-specific `state={value}` shape, built the same
    way as the pre-existing field-name / reason-code negative proofs above
    (Test Notes): the slicer finds a minimal forged section, and the forged
    text genuinely carries the new state value."""

    FORGED_SKILL_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "`--once` のフェーズ境界で終わるターンでは `state=phase_done` を出す。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    FORGED_BATCH_MODE_TEXT = (
        "...\n\n"
        f"{TERMINAL_LINE_HEADING}\n\n"
        "On a `--once` phase boundary the line carries `state=phase_done`.\n\n"
        f"{REPORTING_HEADING}\n"
    )

    def test_forged_skill_excerpt_is_well_formed_and_found(self):
        section = _section(
            self.FORGED_SKILL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn("state=phase_done", section)

    def test_matcher_rejects_forged_skill_state_value_restatement(self):
        section = _section(
            self.FORGED_SKILL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        violations = _find_contract_literal_violations(section)
        self.assertTrue(
            violations, "matcher failed to detect the forged state-value restatement"
        )

    def test_forged_batch_mode_excerpt_is_well_formed_and_found(self):
        section = _section(
            self.FORGED_BATCH_MODE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        self.assertIn("state=phase_done", section)

    def test_matcher_rejects_forged_batch_mode_state_value_restatement(self):
        section = _section(
            self.FORGED_BATCH_MODE_TEXT, TERMINAL_LINE_HEADING, REPORTING_HEADING
        )
        violations = _find_contract_literal_violations(section)
        self.assertTrue(
            violations, "matcher failed to detect the forged state-value restatement"
        )


class TestOnceBoundaryBareLiteralMatcherCanFail(unittest.TestCase):
    """D2 rule 2 (develop-once-option/task0002): a bare `phase_done`
    literal, dodging rule 1's `state={value}` shape check by omitting the
    `state=` prefix, must still be rejected -- it is contract-only
    vocabulary occurring nowhere else in either pointer document."""

    FORGED_BARE_LITERAL_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "`--once` のフェーズ境界で終わるターンの状態は phase_done。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_bare_literal_excerpt_is_well_formed_and_found(self):
        # Non-vacuity guard, and confirms this specifically exercises rule
        # 2: the forged text carries the bare literal but NOT the
        # `state=phase_done` shape rule 1 already covers.
        section = _section(
            self.FORGED_BARE_LITERAL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn("phase_done", section)
        self.assertNotIn("state=phase_done", section)

    def test_matcher_rejects_bare_once_boundary_literal(self):
        section = _section(
            self.FORGED_BARE_LITERAL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        violations = _find_contract_literal_violations(section)
        self.assertTrue(
            violations, "matcher failed to detect the bare once-boundary literal"
        )


class TestReasonNoneShapeMatcherCanFail(unittest.TestCase):
    """SC5 (task0003): negative proof plus non-vacuity guard for the
    `reason={value}` shape check over the ordinary word "none" -- a forged
    excerpt that restates the value in the contract-specific shape, built
    the same way as the pre-existing state-value shape negative proof
    above."""

    FORGED_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "通常完了では `reason=none` を書く。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_excerpt_is_well_formed_and_found(self):
        section = _section(self.FORGED_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER)
        self.assertIn("reason=none", section)

    def test_matcher_rejects_forged_reason_none_shape(self):
        section = _section(self.FORGED_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER)
        violations = _find_contract_literal_violations(section)
        self.assertTrue(
            violations, "matcher failed to detect the forged reason=none shape"
        )


class TestStateValueGuardWholeFileScope(unittest.TestCase):
    """AC-4 and AC-6 (whole-file guard scope, real-file guarantees) plus
    AC-5 (whitelist proof via synthetic sample) -- task0006 rework of
    task0002's class (review round 1 finding 5a7d022d8ac79472 /
    d19b6a0240c04f8d): the extended guard applied to the WHOLE FILE (not
    just the edited section) of both real pointer documents finds 0
    violations -- including where `completed` / `skipped` are used as
    ordinary `workflow.yaml` step-status vocabulary elsewhere in each file.
    AC-6's false-positive proof would be vacuous if those words never
    actually occurred, so their presence is checked directly first
    (non-vacuity).

    This class makes no claim about whether `stopped` (also part of the
    guard's whitelist, D2) occurs in either real pointer document -- that
    was never a contractual requirement, and asserting it made the
    whitelist's own claim (that a whitelisted word appearing there would be
    harmless) permanently unfalsifiable for `stopped` specifically. The
    real-file guarantee is carried entirely by the two whole-file
    0-violation checks below. The whitelist BEHAVIOR itself -- `completed` /
    `skipped` / `stopped` used as ordinary prose never trip the guard -- is
    proven directly against a synthetic sample in
    `test_guard_does_not_flag_step_status_vocabulary_in_a_synthetic_sample`,
    which includes `stopped` alongside the other two."""

    @classmethod
    def setUpClass(cls):
        cls.skill_text = _read(SKILL_PATH)
        cls.batch_mode_text = _read(BATCH_MODE_PATH)

    def test_step_status_words_actually_occur_in_the_real_files(self):
        combined = self.skill_text + self.batch_mode_text
        for word in ("completed", "skipped"):
            self.assertIn(
                word,
                combined,
                f"non-vacuity: {word!r} must occur somewhere in the real "
                "files for the false-positive proof below to mean anything",
            )

    def test_ordinary_none_word_actually_occurs_in_the_real_files(self):
        # Non-vacuity for SC5's "none" whitelist proof below (task0003):
        # "none" occurs as ordinary English prose in these documents
        # (e.g. batch-mode.md's Non-packet gates section), never as a
        # `reason=none` citation.
        combined = self.skill_text + self.batch_mode_text
        self.assertIn("none", combined)

    def test_guard_does_not_flag_step_status_vocabulary_in_a_synthetic_sample(self):
        # AC-5 (task0006): whitelist behavior proven against a synthetic
        # sample containing `completed` / `skipped` / `stopped` as ordinary
        # prose. This module asserts nothing about whether these words
        # occur in the real files (see class docstring); the real-file
        # guarantee is the two whole-file 0-violation checks below.
        sample = (
            "The step completed, another step was skipped, and the run "
            "stopped cleanly afterward."
        )
        self.assertEqual(_find_contract_literal_violations(sample), [])

    def test_guard_does_not_flag_the_ordinary_word_none(self):
        # SC5 (task0003): "none" used as ordinary prose (never in the
        # `reason=none` shape) must not be flagged.
        sample = "None of the gates below carries a marker; the answer is none."
        self.assertEqual(_find_contract_literal_violations(sample), [])

    def test_guard_raises_no_violation_over_whole_skill_md(self):
        self.assertEqual(_find_contract_literal_violations(self.skill_text), [])

    def test_guard_raises_no_violation_over_whole_batch_mode_md(self):
        self.assertEqual(
            _find_contract_literal_violations(self.batch_mode_text), []
        )


class TestBatchModeNonPacketGatesTableUnchanged(unittest.TestCase):
    """AC-5 / IMPLEMENTATION.md D7 item 5: this task's edit is confined to
    `## Terminal line` and must not touch the Non-packet gates table --
    still exactly ten data rows, catch-all/diff-size/per-command wording
    intact. A pure regression guard (Test Notes), exempt from a negative
    proof."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.section = _section(cls.text, NON_PACKET_GATES_HEADING, BATCH_BLOCK_HEADING)

    def test_table_has_exactly_ten_data_rows(self):
        # Data rows start with "| " immediately followed by non-`-`/`Gate`
        # content; the header row and the `|---|---|` separator are
        # excluded by requiring the row to start with a backtick-quoted or
        # prose cell rather than `-` or the literal header text.
        row_lines = [
            line
            for line in self.section.splitlines()
            if line.startswith("| ") and not line.startswith("|---") and "| Gate (" not in line
        ]
        self.assertEqual(len(row_lines), 10, f"expected 10 data rows, found {len(row_lines)}")

    def test_catch_all_diff_size_and_per_command_wording_intact(self):
        self.assertIn("the ten rows above", self.section)
        self.assertIn("Review phase diff-size gate", self.section)
        self.assertIn(
            "Per-command approval fallback used when the PreToolUse hook is inactive",
            self.section,
        )


class TestStepCCompletionReportNonRegression(unittest.TestCase):
    """AC-5: every element of the Step C completion report survives
    unchanged, each asserted individually (Test Notes)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_C_HEADING, STOP_REPORT_HEADING)

    def test_completion_headline_present(self):
        self.assertIn("`em-workflow 完了: {feature}`", self.section)
        self.assertIn(
            _strip_ws("タスク数 / レビュー ラウンド数 / 残存 findings"),
            _strip_ws(self.section),
        )

    def test_retained_branch_guidance_present(self):
        self.assertIn(_strip_ws("ブランチを残した分岐"), _strip_ws(self.section))
        self.assertIn(
            "`git switch em-workflow/{feature}/integration`", self.section
        )
        self.assertIn(
            _strip_ws("ローカルマージまたは `git push` + PR 作成」の案内"),
            _strip_ws(self.section),
        )

    def test_pr_url_guidance_present(self):
        self.assertIn(
            _strip_ws("PR を作成した場合は PR URL を添える"),
            _strip_ws(self.section),
        )

    def test_license_single_line_present(self):
        self.assertIn(
            "`LICENSE が無いから /em-workflow:gen-license の実行をおすすめするよ`",
            self.section,
        )

    def test_batch_audit_items_present(self):
        for item in (
            "自動承認コマンド",
            "記録した仮定",
            "rework 消費",
            "deferred findings",
        ):
            self.assertIn(item, self.section)


class TestExistingHeadingsAndForbiddenLiteralsUnchanged(unittest.TestCase):
    """AC-5: headings/anchor sentences pre-existing test modules assert
    against are unchanged, and none of D7's forbidden literals appears."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_pinned_headings_unchanged(self):
        for heading in (
            "## Step 0: git-setup ゲート（workflow 開始時に毎回）",
            "## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）",
            "## Step B: 自走ループ",
            STEP_C_HEADING,
            STOP_REPORT_HEADING,
        ):
            self.assertIn(heading, self.text)

    def test_no_decision_table_literal(self):
        lowered = self.text.lower()
        for pattern in FORBIDDEN_DECISION_TABLE_PATTERNS:
            self.assertNotIn(pattern.lower(), lowered)

    def test_no_stale_agent_name(self):
        self.assertNotIn(FORBIDDEN_STALE_AGENT_NAME, self.text)

    def test_no_stale_inline_phrase(self):
        self.assertNotIn(FORBIDDEN_STALE_INLINE_PHRASE, self.text)

    def test_new_subsection_mentions_no_gate_id(self):
        # D7 item 6 guard: the new content introduces no `gate_id` / `gate
        # ID` mention at all, so it cannot newly trigger the 120-character
        # proximity constraint against any existing mention elsewhere in
        # the file (the nearest pre-existing mention sits far earlier, near
        # the `--batch` argument-processing section).
        section = _section(self.text, NEW_SUBSECTION_HEADING, FILE_END_MARKER)
        self.assertNotIn("gate_id", section)
        self.assertNotIn("gate ID", section)


class TestImplementPhaseCitationUnchanged(unittest.TestCase):
    """AC-5 (task0003): `implement-phase.md`'s single citation of the SSOT
    (the implement second-failure stop's precedence over the generic stop
    condition) still gives that precedence, still names the SSOT by path,
    restates no SC5 literal anywhere in the whole file, and still uses
    `completed` / `skipped` / `stopped` as ordinary status words elsewhere
    in the file.

    Pure regression guard (Test Notes): the sentence itself never named a
    "line" (it cites the SSOT only for the precedence RULE, not for the
    result's format), so this task made no wording change to it -- verified
    by asserting the sentence is present byte-for-byte, unchanged. Exempt
    from a negative proof for that reason, matching this module's own
    convention for pure regression guards elsewhere (e.g.
    TestStepCCompletionReportNonRegression)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)

    def test_precedence_sentence_present_unchanged(self):
        self.assertIn(CONTRACT_DOC_REFERENCE, self.text)
        self.assertIn(
            _strip_ws(
                "since `references/batch-terminal-line.md` already gives "
                "`implement-second-failure` precedence over `stop-condition-3`"
            ),
            _strip_ws(self.text),
        )

    def test_restates_no_sc5_literal_over_the_whole_file(self):
        self.assertEqual(_find_contract_literal_violations(self.text), [])

    def test_ordinary_status_words_still_present(self):
        # Non-vacuity for the whitelist claim scoped to THIS file (AC-5):
        # `completed` / `skipped` / `stopped` occur here as ordinary status
        # vocabulary, unrelated to the contract's `state` domain, and must
        # never be flagged by the guard above.
        for word in ("completed", "skipped", "stopped"):
            self.assertIn(word, self.text)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6 / NFR1: this module imports the Python standard library only."""

    def test_own_imports_are_all_stdlib(self):
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
