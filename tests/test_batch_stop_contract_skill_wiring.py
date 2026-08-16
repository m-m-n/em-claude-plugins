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
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

NEW_SUBSECTION_HEADING = "## バッチ終端行"
FILE_END_MARKER = "$ARGUMENTS"

STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — 時のみ）"
)
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"

TERMINAL_LINE_HEADING = "## Terminal line"
REPORTING_HEADING = "## Reporting"
NON_PACKET_GATES_HEADING = "## Non-packet gates"
BATCH_BLOCK_HEADING = "## workflow.yaml `batch` block"

CONTRACT_DOC_REFERENCE = "references/batch-terminal-line.md"
CONTRACT_DOC_PLUGIN_ROOT_REFERENCE = (
    "${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md"
)

# The contract's literals (IMPLEMENTATION.md Shared Components), which a
# pointer document may name the *document* for but must never restate
# itself (SSOT partition, IMPLEMENTATION.md Conventions). Extended to the
# full ELEVEN-member set by task0005/D9 (rework round 1): the original nine
# from task0001/task0002 plus the two closing the Step A / docs-commit-
# conflict gap. This tuple is used for absence checks only -- it does not
# assert that the contract document (task0004's file) defines all eleven,
# since that file may or may not have merged yet in this worktree (D9 cross-
# task safety).
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
)
FIELD_NAME_TOKENS = ("`state`", "`step`", "`reason`", "`detail`")
PREFIX_LITERAL = "EM_WORKFLOW_TERMINAL:"
SENTINEL_VALUE = "no-step"

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
    would false-positive on unrelated prose."""
    violations = []
    if PREFIX_LITERAL in text:
        violations.append(f"prefix literal {PREFIX_LITERAL!r} restated")
    if all(token in text for token in FIELD_NAME_TOKENS):
        violations.append("all four field-name tokens restated together")
    for code in REASON_CODES:
        if code in text:
            violations.append(f"reason code {code!r} restated")
    if SENTINEL_VALUE in text:
        violations.append(f"sentinel value {SENTINEL_VALUE!r} restated")
    return violations


def _states_generalized_no_line_rule(text):
    """AC-2's generalization matcher: true iff `text` states the no-line
    rule generally -- keeping the 停止条件 5 / 終端行を出力しない anchors
    that already proved the original (task0002) wait-turn guarantee -- AND
    additionally names implement's launch turn and wake turn as further
    instances of the same rule, rather than stopping at 停止条件 5 alone
    (task0002's narrower wording, which is exactly what the negative proof
    below forges). All four are required together."""
    stripped = _strip_ws(text)
    return (
        "停止条件 5" in text
        and "終端行を出力しない" in text
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

    def test_subsection_states_terminal_line_is_last_line_of_final_message(self):
        self.assertIn(
            _strip_ws("最後の assistant メッセージの末尾に終端行を 1 行出力する"),
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

    def test_subsection_states_wait_turn_emits_no_terminal_line(self):
        self.assertIn("停止条件 5", self.section)
        self.assertIn("終端行を出力しない", self.section)

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

    def test_subsection_instructs_reading_the_contract_doc_before_emitting(self):
        # AC-3 (task0005, finding 6a1c9f2d84be3057).
        self.assertTrue(
            _has_read_instruction_for_contract_doc(
                self.section, CONTRACT_DOC_PLUGIN_ROOT_REFERENCE
            ),
            "expected an instruction to Read the plugin-root-prefixed "
            "contract document immediately before emitting the line",
        )

    def test_step_c_report_item_points_at_terminal_line(self):
        self.assertIn(CONTRACT_DOC_REFERENCE, self.step_c_section)
        self.assertIn(
            _strip_ws("この報告のあとに終端行を追記する"),
            _strip_ws(self.step_c_section),
        )


class TestNoLineGeneralizationMatcherCanFail(unittest.TestCase):
    """AC-2 / Test Notes (a): negative proof plus non-vacuity guard for
    `_states_generalized_no_line_rule` -- a forged subsection that names
    only 停止条件 5, matching task0002's pre-rework wording verbatim."""

    FORGED_NO_LINE_ONLY_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "停止条件 5（implementer の完了通知待ち）でターンを終える場合は、"
        "ラン自体は継続しているため終端行を出力しない。\n\n"
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
        self.assertIn("終端行を出力しない", section)

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


class TestOwnReasonCodeTupleIsEleven(unittest.TestCase):
    """AC-4 (task0005/D9): this module's own `REASON_CODES` tuple -- used
    for absence checks only, never asserted against the contract document
    itself (D9 cross-task safety) -- lists all eleven codes, the original
    nine plus the two closing the Step A / docs-commit-conflict gap."""

    def test_reason_codes_tuple_has_eleven_members(self):
        self.assertEqual(len(REASON_CODES), 11)

    def test_reason_codes_tuple_includes_the_two_rework_codes(self):
        self.assertIn("feature_resolution_aborted", REASON_CODES)
        self.assertIn("docs_commit_conflict_aborted", REASON_CODES)

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
    contract-literal absence matcher -- a forged subsection that restates a
    field name, run through the same slicer used above."""

    FORGED_FULL_TEXT = (
        "...\n\n"
        f"{NEW_SUBSECTION_HEADING}\n\n"
        "終端行は `state` / `step` / `reason` / `detail` の 4 フィールドを持つ。\n\n"
        f"{FILE_END_MARKER}\n"
    )

    def test_forged_restatement_is_a_well_formed_subsection_the_slicer_finds(self):
        # Non-vacuity guard: the slicer finds it, and the forged sentence
        # genuinely carries all four field-name tokens -- so the rejection
        # below exercises the comparison, not a slicing or fixture defect.
        section = _section(
            self.FORGED_FULL_TEXT, NEW_SUBSECTION_HEADING, FILE_END_MARKER
        )
        self.assertIn("4 フィールドを持つ", section)
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
