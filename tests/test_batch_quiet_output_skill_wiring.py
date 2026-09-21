"""Tests for task0002 (batch-quiet-output): the develop-skill's wiring of
the batch output-suppression discipline defined by
`references/batch-mode.md` (task0001).

Covers task0002 Acceptance Criteria
(feature-docs/batch-quiet-output/tasks/task0002.md):

- AC-1 (FR1, FR12, NFR4): every site in Design items 1-8 that needs the
  discipline names `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md`, and
  SKILL.md restates neither the marker format nor the suppressed-scope list
  nor the exception list anywhere.
- AC-2 (FR2, FR8, NFR2): the 停止条件 5 site and the `--once` 非境界 note
  state that such a turn's final message is the marker line the discipline
  defines and nothing else; the `--once` phase-boundary case states
  terminal line only, no other narration; and the marker prefix literal,
  the terminal prefix literal and every other literal listed in
  IMPLEMENTATION.md D6(b) are absent from the whole file.
- AC-3 (FR4, FR9, FR10): the Step A.5, design-branch, verify and retrospect
  sites each carry a batch clause withholding their narration or
  result-summary body, each stating that writes, commits, gate resolution
  and status transitions are unchanged; no gate resolution rule, cap,
  counter or status-transition rule in SKILL.md is altered, and no
  `gate_id` mention is added.
- AC-4 (FR5, FR11, NFR5): Step C's report keeps every element it has today
  (completion headline, kept-branch guidance, PR URL line, gen-license
  line, the four batch audit items) -- the pre-existing assertions in
  `tests/test_batch_stop_contract_skill_wiring.py` still pass unmodified --
  and additionally states that the batch audit items are assembled from the
  discipline's persisted source map, in the file's existing Japanese voice.
- AC-5 (FR11): Step A.5's batch branch states that the auto-approved
  command strings are recorded as the `create-spec.command-approval` gate
  resolution in the feature's phase-state, and no longer relies on the
  running output to carry them to the final report; the interactive
  approval path's wording is unchanged.
- AC-6 (FR6, NFR3): each stop/abort site named in Design item 5 is covered
  by the stop/abort exception, stated once by reference, with every
  existing stop-report wording retained; the 停止時の報告 section's current
  three bullets are unchanged.
- AC-7 (FR7, NFR1): the バッチ終端行 section's existing guarantees are
  intact (heading, placement after the stop-report section, the
  Read-before-emit instruction, the last-line rule, the generalized no-line
  rule, the stop-point enumeration, the `--once` occasion), and the whole
  pre-existing test suite passes with no pre-existing module modified.

This is a documentation-contract task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following
`tests/test_batch_stop_contract_skill_wiring.py`'s form: standard library
only, no import from another test module, constants re-declared locally
(including a locally declared copy of the forbidden literals from
IMPLEMENTATION.md D6(b) plus the marker prefix literal, used for ABSENCE
checks only -- this module must not assert what `batch-mode.md` defines,
since task0001's file may not have merged into this worktree yet).

Matcher -> negative-proof inventory (Test Notes: every NEW matcher carries a
negative proof over a forged section plus a non-vacuity guard; AC-4's and
AC-7's non-regression assertions are pure regression guards over retained
wording and are exempt):

- `_names_batch_mode_discipline` (pointer-site matcher, AC-1): negative
  proof is TestPointerSiteMatcherCanFail.test_matcher_rejects_section_missing_the_reference,
  non-vacuity guard is
  TestPointerSiteMatcherCanFail.test_forged_section_missing_reference_is_well_formed_and_found.
- `_states_turn_ends_with_marker_line_only` (marker-only-turn matcher,
  AC-2): negative proof is
  TestMarkerOnlyMatcherCanFail.test_matcher_rejects_section_without_exclusivity_wording,
  non-vacuity guard is
  TestMarkerOnlyMatcherCanFail.test_forged_section_is_well_formed_and_found.
- `_states_batch_once_boundary_terminal_line_only` (AC-2's `--once`
  phase-boundary half): negative proof is
  TestBatchOnceTerminalOnlyMatcherCanFail.test_matcher_rejects_section_without_exclusivity_clause,
  non-vacuity guard is
  TestBatchOnceTerminalOnlyMatcherCanFail.test_forged_section_is_well_formed_and_found.
- `_states_step_a5_records_gate_resolution_in_phase_state` (Step A.5
  recording matcher, AC-5): negative proof is
  TestStepA5RecordingMatcherCanFail.test_matcher_rejects_section_missing_the_answers_shape,
  non-vacuity guard is
  TestStepA5RecordingMatcherCanFail.test_forged_section_is_well_formed_and_found.
- `_states_step_c_sources_audit_items_from_persisted_map` (Step C sourcing
  matcher, AC-4): negative proof is
  TestStepCSourcingMatcherCanFail.test_matcher_rejects_section_missing_the_wake_commit_source
  (forged section names the source map but omits the DECLINE-deviation
  source traced to `implement-phase.md`), non-vacuity guard is
  TestStepCSourcingMatcherCanFail.test_forged_section_is_well_formed_and_found.
- `_find_forbidden_literal_violations` (whole-file literal-absence guard,
  AC-2): negative proof is
  TestForbiddenLiteralMatcherCanFail.test_matcher_rejects_forged_marker_and_terminal_prefixes,
  non-vacuity guard is
  TestForbiddenLiteralMatcherCanFail.test_forged_text_genuinely_carries_both_prefixes.

AC-3's "no gate resolution rule, cap, counter or status-transition rule is
altered" and "no `gate_id` mention is added" and AC-6's "the 停止時の報告
section's current three bullets are unchanged" are pure regression guards
over retained pre-change wording (Test Notes) and are exempt from a
negative proof.

Extended again by batch-structured-result-output/task0003: the terminal-
prefix / field-name / reason-code / sentinel forbidden-literal set is
widened to IMPLEMENTATION.md SC5 (SC1's eight keys, the twelfth reason code
`context_budget_reached`, and the ordinary word "none" checked by the
`reason={value}` shape rather than as a bare word -- the retired terminal
prefix, `EM_WORKFLOW_TERMINAL:`, is unaffected: it was already forbidden
here and stays forbidden under SC6). The バッチ終端行 heading and its
「終端行」/「終端行を出力しない」 wording pins are restated to バッチ構造化結果
/「構造化結果」/「構造化結果を出力しない」 (the underlying guarantees -- whole-
message result, no-result-on-non-terminal-turn, exclusivity at the `--once`
boundary -- are unchanged; only the noun naming the removed shape changed).

Extended again by batch-structured-result-output/task0007 (review round 1
rework; finding d48f305d463a7feb; IMPLEMENTATION.md SC10). Covers task0007
Acceptance Criterion AC-2
(feature-docs/batch-structured-result-output/tasks/task0007.md):
`TestStopAbortExceptionStatedOnce` gains
`test_section_states_message_boundary_and_value_carriage`, asserting that
「## 停止時の報告」's batch exception now states (a) WHICH message carries
the report -- a message before the turn's final one -- and (b) that the
report's cause/affected paths/recovery guidance are ALSO carried in full
inside the structured result's own values (`detail` /
`resume_conditions`), as an addition rather than a substitute. The three
existing bullets stay unchanged (already guarded, unaffected).

Matcher -> negative-proof inventory (task0007 addition):

- `_states_stop_report_message_boundary_and_value_carriage` (AC-2
  message-boundary/value-carriage matcher): negative proof is
  TestStopReportMessageBoundaryMatcherCanFail.test_matcher_rejects_pre_task0007_wording
  (the pre-task0007 section text, verbatim), non-vacuity guard is
  TestStopReportMessageBoundaryMatcherCanFail.test_forged_old_section_is_well_formed_and_found.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

# The pointer literal every wired site must name (IMPLEMENTATION.md D3
# pointer convention -- SKILL.md's own ${CLAUDE_PLUGIN_ROOT}-prefixed
# convention).
BATCH_MODE_REFERENCE = "${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md"

FILE_END_MARKER = "$ARGUMENTS"

# Section boundary markers, taken verbatim from skills/develop/SKILL.md.
ONCE_ARG_BULLET = "- `--once`:"
STEP_A5_HEADING = "## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）"
STEP_B_HEADING = "## Step B: 自走ループ"
DESIGN_BRANCH_HEADING = "### design ステップ分岐"
VERIFY_HEADING = "### verify フェーズ"
RETROSPECT_HEADING = "### retrospect フェーズ（収集は自動・承認不要）"
# task-tier-reduction/task0005 (FR3) generalized this heading so `skipped`
# is admitted whether design's own skip or a tier's skip caused it, instead
# of restricting the exception to design alone. Updated in place here (not
# duplicated) to pin the new wording -- same established convention as the
# sibling STEP_C_HEADING constants in this test suite.
STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — `skipped` の step（design 自身の skip、または tier による skip）があっても可 — か、cap 到達により verify が `failed` のまま残る場合のみ）"
)
ONCE_BOUNDARY_HEADING = "## `--once` のフェーズ境界"
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"
TERMINAL_LINE_HEADING = "## バッチ構造化結果"

STOP_CONDITION_5_MARKER = (
    "5. implement フェーズでバックグラウンド implementer の完了通知を待つとき"
)
STOP_CONDITION_6_MARKER = "6. Step 0 の git-setup ゲートが中断を報告したとき"
TURN_END_ANCHOR = "これらに該当しない限り"

# IMPLEMENTATION.md (batch-structured-result-output) SC5's forbidden
# literals, re-declared locally for ABSENCE checks only (this module never
# asserts that batch-mode.md or batch-terminal-line.md defines any of
# these, since those files' sections may not have merged into this
# worktree yet -- Test Notes cross-task safety). SC5 is the union of SC1's
# eight field-name tokens (checked as a GROUP, same false-positive
# rationale as the pre-existing four-field group check), every `reason`
# code (the eleven from batch-stop-contract plus the twelfth,
# `context_budget_reached`, D8), the `no-step` step-value sentinel, every
# `state` value (by shape), and this feature's own retired terminal-line
# prefix (SC6) plus batch-mode's own marker prefix literal (unaffected by
# this feature, kept for regression).
TERMINAL_PREFIX_LITERAL = "EM_WORKFLOW_TERMINAL:"
MARKER_PREFIX_LITERAL = "EM_WORKFLOW_PROGRESS:"
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
SENTINEL_VALUE = "no-step"
STATE_DOMAIN = ("completed", "stopped", "phase_done")
# SC5's `reason` domain also includes the ordinary English word "none" --
# checked by the `reason={value}` shape only (same false-positive rationale
# as `state`), never as a bare word (see test_batch_stop_contract_skill_
# wiring.py's identical convention).
ORDINARY_REASON_VALUE = "none"


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
    # hard-wraps Japanese prose without a space at the break point, so a
    # phrase can straddle a line break with no literal space there
    # (matching tests/test_batch_stop_contract_skill_wiring.py's helper of
    # the same name / same rationale).
    return re.sub(r"\s+", "", text)


def _extract_batch_clause(section, end_marker):
    """Isolates just the newly-added batch clause within `section`, from
    its `batch:` opener to `end_marker` (inclusive) -- so a check like
    "no `gate_id` mention added" is scoped to what this task actually
    added, not to pre-existing unrelated prose elsewhere in the same
    section (e.g. verify フェーズ's step 4 already discusses `gate_id` for an
    unrelated reason).

    `end_marker` may be a single literal, or a tuple/list of candidate
    literals when the clause's closing wording can legitimately vary
    (e.g. verify's clause gained a rework-cap exception sentence that
    moved its closing `）` to a different literal) -- the first candidate
    found after `batch:\n` wins."""
    start = section.index("batch:\n")
    candidates = (end_marker,) if isinstance(end_marker, str) else tuple(end_marker)
    best_end = None
    for candidate in candidates:
        try:
            idx = section.index(candidate, start) + len(candidate)
        except ValueError:
            continue
        if best_end is None or idx < best_end:
            best_end = idx
    if best_end is None:
        raise ValueError(f"none of {candidates!r} found in section after 'batch:\\n'")
    return section[start:best_end]


def _find_forbidden_literal_violations(text):
    """Whole-file literal-absence guard (AC-2, IMPLEMENTATION.md SC5 +
    this feature's own marker prefix): returns a list of human-readable
    violation descriptions if `text` restates any contract/marker literal,
    empty when none is restated."""
    violations = []
    if TERMINAL_PREFIX_LITERAL in text:
        violations.append(f"terminal prefix literal {TERMINAL_PREFIX_LITERAL!r} restated")
    if MARKER_PREFIX_LITERAL in text:
        violations.append(f"marker prefix literal {MARKER_PREFIX_LITERAL!r} restated")
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
    reason_none_shape = f"reason={ORDINARY_REASON_VALUE}"
    if reason_none_shape in text:
        violations.append(f"reason-value shape {reason_none_shape!r} restated")
    return violations


def _names_batch_mode_discipline(section):
    """Pointer-site matcher (AC-1, Design items 1-8): true iff `section`
    names the discipline document via SKILL.md's own
    `${CLAUDE_PLUGIN_ROOT}`-prefixed convention."""
    return BATCH_MODE_REFERENCE in section


def _states_turn_ends_with_marker_line_only(section):
    """Marker-only-turn matcher (AC-2, Design items 4/7): true iff
    `section` names the discipline document, mentions the marker line, and
    states exclusivity (nothing else on that turn's final message) via
    「のみ」 or 「だけ」."""
    return (
        BATCH_MODE_REFERENCE in section
        and "マーカー行" in section
        and ("のみ" in section or "だけ" in section)
    )


def _states_batch_once_boundary_terminal_line_only(section):
    """`--once` phase-boundary matcher for batch mode (AC-2, Design item
    7): true iff `section` names batch mode, names the structured result
    (restated by batch-structured-result-output/task0003 from the retired
    "終端行" term), and states that no narration other than the structured
    result is emitted."""
    return (
        "batch" in section
        and "構造化結果" in section
        and "以外" in section
        and "ナラティブ" in section
    )


def _states_step_a5_records_gate_resolution_in_phase_state(section):
    """Step A.5 recording matcher (AC-5): true iff `section` states that
    the auto-approved command strings are recorded as the
    `create-spec.command-approval` gate resolution in the feature's
    phase-state, using the existing `answers` entry shape, and names the
    discipline document."""
    return (
        BATCH_MODE_REFERENCE in section
        and "create-spec.command-approval" in section
        and "phase-state" in section
        and "`answers`" in section
    )


def _states_step_c_sources_audit_items_from_persisted_map(section):
    """Step C sourcing matcher (AC-4): true iff `section` names the
    discipline document's source map that the batch audit items are
    assembled from, and traces the DECLINE-deviation source to
    `implement-phase.md`."""
    return (
        BATCH_MODE_REFERENCE in section
        and "ソースマップ" in section
        and "implement-phase.md" in section
        and "DECLINE" in section
    )


def _states_stop_report_message_boundary_and_value_carriage(section):
    """AC-2 matcher (batch-structured-result-output/task0007; review round
    1 finding d48f305d463a7feb; IMPLEMENTATION.md SC10): true iff `section`
    states (a) WHICH message carries the batch stop/abort report -- a
    message before the turn's final one, per the general SC10 rule -- and
    (b) that the report's content is ALSO carried in full inside the
    structured result's own values (cause/affected paths in `detail`,
    recovery guidance in `resume_conditions`), as an ADDITION rather than a
    substitute."""
    stripped = _strip_ws(section)
    return (
        _strip_ws("より前のメッセージで出力する") in stripped
        and "`detail`" in section
        and "`resume_conditions`" in section
        and _strip_ws("追加であり、置き換えではない") in stripped
    )


class TestBatchArgBulletNamesDiscipline(unittest.TestCase):
    """AC-1, Design item 1: the `--batch` argument-processing bullet names
    the discipline document. The bullet already named
    `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` before this task (for
    unrelated gate-jurisdiction reasons), so the bare presence check alone
    would not be red-confirmed against this task's change -- the new
    assertion below targets the specific clause this task adds instead."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, "- `--batch`:", ONCE_ARG_BULLET)

    def test_bullet_names_the_discipline_document(self):
        self.assertTrue(_names_batch_mode_discipline(self.section))

    def test_bullet_states_document_also_covers_output_suppression(self):
        self.assertIn("出力抑制の規律も定める", self.section)

    def test_bullet_does_not_restate_any_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestStepA5RecordingWiring(unittest.TestCase):
    """AC-3, AC-5, Design item 2: the batch branch of Step A.5 records the
    auto-approved command strings as the gate resolution in phase-state,
    naming the discipline document, and withholds them from the running
    output."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_A5_HEADING, STEP_B_HEADING)

    def test_section_names_the_discipline_document(self):
        self.assertTrue(_names_batch_mode_discipline(self.section))

    def test_section_states_the_gate_resolution_recording(self):
        self.assertTrue(
            _states_step_a5_records_gate_resolution_in_phase_state(self.section),
            "expected Step A.5's batch branch to state that auto-approved "
            "command strings are recorded as the create-spec.command-"
            "approval gate resolution in phase-state, using the existing "
            "`answers` entry shape",
        )

    def test_section_states_running_output_is_withheld(self):
        self.assertIn("ランニング出力に出さず", self.section)

    def test_interactive_approval_wording_unchanged(self):
        # The interactive path's own instruction (present/AskUserQuestion/
        # --record) must survive verbatim.
        self.assertIn(
            "AskUserQuestion（multiSelect）で一括承認 → `--record` で記録",
            self.section,
        )

    def test_no_gate_id_mention_added(self):
        self.assertNotIn("gate_id", self.section.replace("`gate_id`", ""))

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestStopCondition5MarkerOnly(unittest.TestCase):
    """AC-2, Design item 4: the 停止条件 5 wait turn (both forms) ends with
    the marker line and nothing else. The statement sits in a new
    paragraph right after item 7 (not inside item 5's own numbered text --
    tests/test_develop_once_option.py's `ITEMS_1_TO_6_VERBATIM` pins item
    5's wording byte-for-byte, so this task's addition must not touch it),
    hence the section spans from item 5's marker through the list's
    closing anchor sentence."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STOP_CONDITION_5_MARKER, TURN_END_ANCHOR)

    def test_section_states_marker_line_only(self):
        self.assertTrue(
            _states_turn_ends_with_marker_line_only(self.section),
            "expected 停止条件 5's site to state that the wait turn's final "
            "assistant message is the marker line and nothing else",
        )

    def test_section_covers_both_wait_forms(self):
        self.assertIn("(a)(b)", self.section)

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


DESIGN_CLAUSE_END = "design step の status 遷移は対話時と変わらない）"
# verify's batch clause may end either at the plain "...対話時と変わらない）"
# closer, or (after the rework-cap exception sentence was appended) at
# "...対話時と同じ内容を全文出力する）" -- both close the same batch: 括弧,
# so accept either wording rather than hardcoding one.
VERIFY_CLAUSE_END = (
    "verify step の status 遷移は対話時と変わらない）",
    "対話時と同じ内容を全文出力する）",
)
RETROSPECT_CLAUSE_END = "status 遷移は対話時と変わらない）"


class TestDesignVerifyRetrospectBatchClauses(unittest.TestCase):
    """AC-3, Design item 3: design-branch / verify / retrospect each carry
    a batch clause withholding narration and result-summary body, stating
    writes/commits/gate-resolution/status-transitions are unchanged. Each
    check is scoped to the newly-added clause itself (`_extract_batch_
    clause`), not the whole pre-existing section -- verify フェーズ's step 4
    already discusses `gate_id` for an unrelated reason (sentinel-value
    assignment), so a whole-section absence check would false-positive
    there."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.design_section = _section(cls.text, DESIGN_BRANCH_HEADING, VERIFY_HEADING)
        cls.verify_section = _section(cls.text, VERIFY_HEADING, RETROSPECT_HEADING)
        cls.retrospect_section = _section(cls.text, RETROSPECT_HEADING, STEP_C_HEADING)
        cls.design_clause = _extract_batch_clause(cls.design_section, DESIGN_CLAUSE_END)
        cls.verify_clause = _extract_batch_clause(cls.verify_section, VERIFY_CLAUSE_END)
        cls.retrospect_clause = _extract_batch_clause(
            cls.retrospect_section, RETROSPECT_CLAUSE_END
        )

    def _assert_clause(self, clause, label):
        self.assertTrue(
            _names_batch_mode_discipline(clause), f"{label}: missing discipline reference"
        )
        stripped = _strip_ws(clause)
        self.assertIn(
            _strip_ws("ランニング出力に出さない"), stripped, f"{label}: missing narration withholding"
        )
        self.assertIn(
            _strip_ws("commit-docs.sh でのコミット"),
            stripped,
            f"{label}: missing commit-unchanged clause",
        )
        self.assertIn("ゲート解決", clause, f"{label}: missing gate-resolution-unchanged clause")
        self.assertIn(
            _strip_ws("対話時と変わらない"),
            stripped,
            f"{label}: missing status-transition-unchanged clause",
        )
        self.assertEqual(_find_forbidden_literal_violations(clause), [])
        self.assertNotIn("gate_id", clause, f"{label}: unexpected new gate_id mention")

    def test_design_branch_clause(self):
        self._assert_clause(self.design_clause, "design ステップ分岐")

    def test_verify_clause(self):
        self._assert_clause(self.verify_clause, "verify フェーズ")

    def test_retrospect_clause(self):
        self._assert_clause(self.retrospect_clause, "retrospect フェーズ")

    def test_verify_rework_cap_wording_unaltered(self):
        # task0001 (batch-verify-rework-lineage-cap) replaced the fixed
        # counter cap with an independently-evaluated lineage cap / hard
        # cap pair. Pin the new wording here so a regression back to the
        # old fixed counter is caught by this non-regression guard.
        self.assertIn("系譜 cap", self.verify_section)
        self.assertIn("hard cap", self.verify_section)
        self.assertIn("batch.verify_rework", self.verify_section)


class TestStepCSourcingWiring(unittest.TestCase):
    """AC-4, Design item 6: Step C's batch audit items are stated as
    assembled from the discipline's persisted source map, with the
    DECLINE-deviation source traced to `implement-phase.md`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_C_HEADING, ONCE_BOUNDARY_HEADING)

    def test_section_names_the_discipline_document(self):
        self.assertTrue(_names_batch_mode_discipline(self.section))

    def test_section_states_the_source_map_sentence(self):
        self.assertTrue(
            _states_step_c_sources_audit_items_from_persisted_map(self.section),
            "expected Step C to state that the batch audit items are "
            "assembled from the persisted source map, tracing the "
            "DECLINE-deviation source to implement-phase.md",
        )

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestStepCCompletionReportNonRegression(unittest.TestCase):
    """AC-4: every element of the Step C completion report is retained
    (pure regression guard, Test Notes -- exempt from a negative proof)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_C_HEADING, ONCE_BOUNDARY_HEADING)

    def test_completion_headline_present(self):
        self.assertIn("`em-workflow 完了: {feature}`", self.section)

    def test_kept_branch_guidance_present(self):
        self.assertIn(
            "`git switch em-workflow/{feature}/integration`", self.section
        )

    def test_pr_url_line_present(self):
        self.assertIn("PR を作成した場合は PR URL を添える", self.section)

    def test_gen_license_line_present(self):
        self.assertIn(
            "`LICENSE が無いから /em-workflow:gen-license の実行をおすすめするよ`",
            self.section,
        )

    def test_four_batch_audit_items_present(self):
        for item in ("自動承認コマンド", "記録した仮定", "rework 消費", "deferred findings"):
            self.assertIn(item, self.section)


class TestOnceBoundaryBatchWiring(unittest.TestCase):
    """AC-2, Design item 7: the batch `--once` phase-boundary emits the
    terminal line only, and the 非境界 note states that the stop-condition-5
    wait / implement launch / wake turns carry the marker line instead."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, ONCE_BOUNDARY_HEADING, STOP_REPORT_HEADING)

    def test_non_boundary_note_states_marker_line_only(self):
        self.assertTrue(
            _states_turn_ends_with_marker_line_only(self.section),
            "expected the 非境界 note to state that those turns' final "
            "assistant message is the marker line and nothing else",
        )

    def test_non_boundary_note_names_all_three_turns(self):
        self.assertIn("停止条件 5", self.section)
        self.assertIn("launch", self.section)
        self.assertIn("wake", self.section)

    def test_batch_once_boundary_states_terminal_line_only(self):
        self.assertTrue(
            _states_batch_once_boundary_terminal_line_only(self.section),
            "expected the batch `--once` phase-boundary case to state "
            "terminal line only, no other narration",
        )

    def test_interactive_once_ending_line_unchanged(self):
        self.assertIn(
            "`{step} が完了したよ。続きは /clear してから "
            "/em-workflow:develop {feature} を実行してね`",
            self.section,
        )

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestStopAbortExceptionStatedOnce(unittest.TestCase):
    """AC-6, Design item 5: every stop/abort site is covered by a single
    stated exception referencing the discipline document; the three
    existing stop-report bullets are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STOP_REPORT_HEADING, TERMINAL_LINE_HEADING)

    def test_section_names_the_discipline_document(self):
        self.assertTrue(_names_batch_mode_discipline(self.section))

    def test_exception_names_every_design_item_5_site(self):
        for marker in (
            "停止条件 6",
            "フェーズ内のゲート中断",
            "Step A の feature 解決失敗",
            "commit-docs.sh の 2 回目の exit 4 によるフェーズ中断",
            "Step C 内の中断",
        ):
            self.assertIn(
                _strip_ws(marker), _strip_ws(self.section), f"missing stop/abort site: {marker!r}"
            )

    def test_exception_stated_exactly_once(self):
        self.assertEqual(self.section.count(BATCH_MODE_REFERENCE), 1)

    def test_section_states_message_boundary_and_value_carriage(self):
        # AC-2 (batch-structured-result-output/task0007, SC10): which
        # message carries the report, and that the report's content is
        # ALSO carried in full inside the result's own values.
        self.assertTrue(
            _states_stop_report_message_boundary_and_value_carriage(
                self.section
            ),
            "expected the section to state which message carries the "
            "stop/abort report and that its content is also carried in "
            "full inside detail / resume_conditions",
        )

    def test_three_existing_bullets_unchanged(self):
        self.assertIn(
            "- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`",
            self.section,
        )
        self.assertIn(
            "- 中断: `{step} が {status} のため中断。"
            "再開するには /em-workflow:develop を実行してね`",
            self.section,
        )
        self.assertIn("- YAML エラー: 内容と `git restore` 等のリカバリ案を報告", self.section)

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestTerminalLineSectionNonRegression(unittest.TestCase):
    """AC-7, Design item 8: the バッチ構造化結果 section (renamed by
    batch-structured-result-output/task0003 from バッチ終端行) keeps every
    guarantee it already had (pure regression guard, Test Notes -- exempt
    from a negative proof), and gains exactly one sentence distinguishing
    the structured result from the non-terminal marker line. The two
    wording pins retired by task0003 (the last-line rule and the
    終端行を出力しない no-line phrasing) are restated here in the new
    terminology (構造化結果 replaces 終端行) rather than dropped, since the
    underlying guarantee (whole-message result; no-result-on-non-terminal-
    turn) is unchanged -- only the noun naming the removed shape changed."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, TERMINAL_LINE_HEADING, FILE_END_MARKER)

    def test_heading_present(self):
        self.assertIn(TERMINAL_LINE_HEADING, self.text)

    def test_placed_immediately_after_stop_report_section(self):
        stop_report_idx = self.text.index(STOP_REPORT_HEADING)
        terminal_idx = self.text.index(TERMINAL_LINE_HEADING)
        self.assertLess(stop_report_idx, terminal_idx)
        between = self.text[
            stop_report_idx + len(STOP_REPORT_HEADING) : terminal_idx
        ]
        self.assertNotIn("\n## ", between)

    def test_read_before_emit_instruction_present(self):
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` を Read し、",
            self.section,
        )

    def test_result_is_whole_final_message_rule_present(self):
        self.assertIn(
            _strip_ws("最後の assistant メッセージの全体を構造化結果とする"),
            _strip_ws(self.section),
        )

    def test_generalized_no_line_rule_present(self):
        self.assertIn("構造化結果を出力しない", self.section)
        self.assertIn("停止条件 5", self.section)
        self.assertIn("launch ターン", self.section)
        self.assertIn("wake ターン", self.section)

    def test_stop_point_enumeration_present(self):
        for marker in ("停止条件 2", "停止条件 3", "停止条件 4", "停止条件 6"):
            self.assertIn(marker, self.section)

    def test_once_occasion_present(self):
        self.assertIn("`--once` のフェーズ境界で終わる", self.section)

    def test_gains_distinguishing_sentence_naming_the_discipline(self):
        self.assertTrue(_names_batch_mode_discipline(self.section))
        self.assertIn("マーカー行とは別物である", self.section)

    def test_section_restates_no_forbidden_literal(self):
        self.assertEqual(_find_forbidden_literal_violations(self.section), [])


class TestWholeFileForbiddenLiteralAbsence(unittest.TestCase):
    """AC-1, AC-2: no forbidden literal (contract or marker) appears
    anywhere in SKILL.md."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_no_violation_over_whole_file(self):
        self.assertEqual(_find_forbidden_literal_violations(self.text), [])

    def test_marker_prefix_literal_absent(self):
        self.assertNotIn(MARKER_PREFIX_LITERAL, self.text)

    def test_terminal_prefix_literal_absent(self):
        self.assertNotIn(TERMINAL_PREFIX_LITERAL, self.text)


# Forged sample for AC-2 (batch-structured-result-output/task0007): the
# pre-task0007 「## 停止時の報告」 section text, verbatim -- well formed (the
# discipline reference, all three bullets, the exception wording) but
# WITHOUT the new message-boundary / value-carriage statements.
FORGED_PRE_TASK0007_STOP_REPORT_SECTION = (
    "\n\nbatch: 下記 3 件に加えて、停止条件 6、フェーズ内のゲート中断、"
    "Step A の feature 解決失敗、commit-docs.sh の 2 回目の exit 4 による"
    "フェーズ中断、Step C 内の中断、そして implement / verify フェーズが"
    "定める終端停止（下記「バッチ構造化結果」が列挙する停止点のすべてを"
    "含む）は、いずれも\n"
    f"{BATCH_MODE_REFERENCE} の出力抑制規律が定める\n"
    "停止/中断の例外であり、対話時と同じ内容を全文報告する。\n\n"
    "- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`\n"
    "- 中断: `{step} が {status} のため中断。"
    "再開するには /em-workflow:develop を実行してね`\n"
    "- YAML エラー: 内容と `git restore` 等のリカバリ案を報告\n"
)


class TestStopReportMessageBoundaryMatcherCanFail(unittest.TestCase):
    """AC-2 (batch-structured-result-output/task0007, SC10): negative
    proof + non-vacuity guard for
    `_states_stop_report_message_boundary_and_value_carriage`."""

    def test_matcher_rejects_pre_task0007_wording(self):
        self.assertFalse(
            _states_stop_report_message_boundary_and_value_carriage(
                FORGED_PRE_TASK0007_STOP_REPORT_SECTION
            )
        )

    def test_forged_old_section_is_well_formed_and_found(self):
        self.assertTrue(
            _names_batch_mode_discipline(
                FORGED_PRE_TASK0007_STOP_REPORT_SECTION
            )
        )
        self.assertIn(
            "対話時と同じ内容を全文報告する",
            FORGED_PRE_TASK0007_STOP_REPORT_SECTION,
        )
        self.assertIn(
            "- スタック:", FORGED_PRE_TASK0007_STOP_REPORT_SECTION
        )
        self.assertIn(
            "- YAML エラー:", FORGED_PRE_TASK0007_STOP_REPORT_SECTION
        )


class TestPointerSiteMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_names_batch_mode_discipline` -- a forged section that never names the
    discipline document."""

    FORGED_SECTION = (
        "batch モードでは進捗のナラティブを出力しない。"
        "詳細は別紙を参照すること。"
    )

    def test_forged_section_missing_reference_is_well_formed_and_found(self):
        self.assertIn("batch モード", self.FORGED_SECTION)
        self.assertNotIn(BATCH_MODE_REFERENCE, self.FORGED_SECTION)

    def test_matcher_rejects_section_missing_the_reference(self):
        self.assertFalse(_names_batch_mode_discipline(self.FORGED_SECTION))

    def test_matcher_accepts_a_section_with_the_reference(self):
        self.assertTrue(
            _names_batch_mode_discipline(
                self.FORGED_SECTION + f" {BATCH_MODE_REFERENCE} 参照。"
            )
        )


class TestMarkerOnlyMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_states_turn_ends_with_marker_line_only` -- a forged section that
    names the discipline and the marker line but omits the exclusivity
    wording (「のみ」/「だけ」)."""

    FORGED_SECTION = (
        f"batch: このターンは {BATCH_MODE_REFERENCE} が定めるマーカー行を"
        "最後の assistant メッセージとして出す。"
    )

    def test_forged_section_is_well_formed_and_found(self):
        self.assertIn(BATCH_MODE_REFERENCE, self.FORGED_SECTION)
        self.assertIn("マーカー行", self.FORGED_SECTION)
        self.assertNotIn("のみ", self.FORGED_SECTION)
        self.assertNotIn("だけ", self.FORGED_SECTION)

    def test_matcher_rejects_section_without_exclusivity_wording(self):
        self.assertFalse(_states_turn_ends_with_marker_line_only(self.FORGED_SECTION))

    def test_matcher_accepts_section_with_exclusivity_wording(self):
        self.assertTrue(
            _states_turn_ends_with_marker_line_only(self.FORGED_SECTION + "マーカー行のみとする。")
        )


class TestBatchOnceTerminalOnlyMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_states_batch_once_boundary_terminal_line_only` -- a forged section
    that names batch and the terminal line but omits the exclusivity
    clause naming narration."""

    FORGED_SECTION = "batch モードでターンが終わるとき、構造化結果を出力する。"

    def test_forged_section_is_well_formed_and_found(self):
        self.assertIn("batch", self.FORGED_SECTION)
        self.assertIn("構造化結果", self.FORGED_SECTION)
        self.assertNotIn("以外", self.FORGED_SECTION)
        self.assertNotIn("ナラティブ", self.FORGED_SECTION)

    def test_matcher_rejects_section_without_exclusivity_clause(self):
        self.assertFalse(
            _states_batch_once_boundary_terminal_line_only(self.FORGED_SECTION)
        )

    def test_matcher_accepts_section_with_exclusivity_clause(self):
        extended = self.FORGED_SECTION + "構造化結果以外のナラティブは一切出さない。"
        self.assertTrue(_states_batch_once_boundary_terminal_line_only(extended))


class TestStepA5RecordingMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_states_step_a5_records_gate_resolution_in_phase_state` -- a forged
    section naming the gate and phase-state but missing the `answers`
    entry-shape mention."""

    FORGED_SECTION = (
        f"batch: 自動承認した文字列を {BATCH_MODE_REFERENCE} の規律により "
        "`create-spec.command-approval` ゲートの解決として feature の "
        "phase-state に記録する。"
    )

    def test_forged_section_is_well_formed_and_found(self):
        self.assertIn(BATCH_MODE_REFERENCE, self.FORGED_SECTION)
        self.assertIn("create-spec.command-approval", self.FORGED_SECTION)
        self.assertIn("phase-state", self.FORGED_SECTION)
        self.assertNotIn("`answers`", self.FORGED_SECTION)

    def test_matcher_rejects_section_missing_the_answers_shape(self):
        self.assertFalse(
            _states_step_a5_records_gate_resolution_in_phase_state(self.FORGED_SECTION)
        )

    def test_matcher_accepts_section_with_the_answers_shape(self):
        extended = self.FORGED_SECTION + "既存の `answers` エントリ形式を使う。"
        self.assertTrue(
            _states_step_a5_records_gate_resolution_in_phase_state(extended)
        )


class TestStepCSourcingMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_states_step_c_sources_audit_items_from_persisted_map` -- a forged
    section naming the discipline and its source map but missing the
    DECLINE-deviation source traced to `implement-phase.md`."""

    FORGED_SECTION = (
        f"batch の監査項目は {BATCH_MODE_REFERENCE} が定めるソースマップから "
        "組み立てる。"
    )

    def test_forged_section_is_well_formed_and_found(self):
        self.assertIn(BATCH_MODE_REFERENCE, self.FORGED_SECTION)
        self.assertIn("ソースマップ", self.FORGED_SECTION)
        self.assertNotIn("implement-phase.md", self.FORGED_SECTION)
        self.assertNotIn("DECLINE", self.FORGED_SECTION)

    def test_matcher_rejects_section_missing_the_wake_commit_source(self):
        self.assertFalse(
            _states_step_c_sources_audit_items_from_persisted_map(self.FORGED_SECTION)
        )

    def test_matcher_accepts_section_with_the_wake_commit_source(self):
        extended = (
            self.FORGED_SECTION
            + "deviation の DECLINE のソースは "
            + "${CLAUDE_PLUGIN_ROOT}/references/implement-phase.md が定める。"
        )
        self.assertTrue(
            _states_step_c_sources_audit_items_from_persisted_map(extended)
        )


class TestForbiddenLiteralMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof plus non-vacuity guard for
    `_find_forbidden_literal_violations` -- a forged text restating both
    this feature's marker prefix and the pre-existing terminal prefix."""

    FORGED_TEXT = (
        "batch は非終端ターンで `EM_WORKFLOW_PROGRESS: phase=implement point=wait` "
        "を出し、終端ターンで `EM_WORKFLOW_TERMINAL: state=completed step=review "
        "reason=no-step detail=ok` を出す。"
    )

    def test_forged_text_genuinely_carries_both_prefixes(self):
        self.assertIn(MARKER_PREFIX_LITERAL, self.FORGED_TEXT)
        self.assertIn(TERMINAL_PREFIX_LITERAL, self.FORGED_TEXT)

    def test_matcher_rejects_forged_marker_and_terminal_prefixes(self):
        violations = _find_forbidden_literal_violations(self.FORGED_TEXT)
        self.assertTrue(violations, "matcher failed to detect the forged restatement")
        self.assertTrue(any("marker prefix" in v for v in violations))
        self.assertTrue(any("terminal prefix" in v for v in violations))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """NFR1: this module imports the Python standard library only."""

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
