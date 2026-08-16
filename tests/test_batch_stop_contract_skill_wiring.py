"""Tests for task0002 (batch-stop-contract): the develop-skill wiring for
the batch terminal-line contract.

Covers task0002 Acceptance Criteria
(feature-docs/batch-stop-contract/tasks/task0002.md):

- AC-1 (FR1, FR5): `em-workflow/skills/develop/SKILL.md` contains a new
  subsection that names `references/batch-terminal-line.md` and states that
  a batch run's run-ending turn emits the terminal line as the last line of
  the final assistant message, covering both normal completion and the
  terminating stops.
- AC-2 (FR6): that subsection states that the turn ending while waiting for
  an implementer completion notification emits no terminal line.
- AC-3 (FR3 partition, NFR2): the subsection restates none of the contract's
  literals -- the prefix literal, the four field names, any reason code and
  the sentinel value are all absent from SKILL.md.
- AC-4 (FR4): every element of the Step C completion report listed in the
  task plan's non-regression table is still present in SKILL.md with its
  current wording, each asserted individually.
- AC-5 (NFR2): every heading and anchor sentence pre-existing test modules
  assert against is unchanged, and none of the forbidden literals of
  IMPLEMENTATION.md D7 (the subset applicable to this file) appears in
  SKILL.md.
- AC-6 (FR8, NFR1, NFR4): this module is discovered by
  `python3 -m unittest discover -s tests`, imports the Python standard
  library only, and provides a negative proof plus a non-vacuity guard for
  each matcher it defines.

Design (task0002.md) item 4 -- a one-line pointer added to the Step C
completion-report item, stating that the batch branch appends the terminal
line after the existing report lines -- is exercised by
TestBatchTerminalLineSubsectionWiring.test_step_c_report_item_points_at_terminal_line,
alongside AC-1's own "covering ... normal completion" requirement.

This is a documentation-contract task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following the
pattern established by tests/test_develop_skill_rewiring.py -- same target
file, independent helper functions (no cross-module import, matching that
module's own convention of self-contained helpers).

Matcher -> negative-proof inventory (Test Notes):

- `_find_contract_literal_violations` (the contract-literal absence
  matcher): negative proof is
  TestContractLiteralMatcherCanFail.test_matcher_rejects_the_forged_field_name_restatement,
  non-vacuity guard is
  TestContractLiteralMatcherCanFail.test_forged_restatement_is_a_well_formed_subsection_the_slicer_finds.
- AC-4's five Step C assertions are pure regression guards over retained
  pre-change wording (Test Notes) and are exempt from a negative proof.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

NEW_SUBSECTION_HEADING = "## バッチ終端行"
FILE_END_MARKER = "$ARGUMENTS"

STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — 時のみ）"
)
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"

CONTRACT_DOC_REFERENCE = "references/batch-terminal-line.md"

# The contract's literals (IMPLEMENTATION.md Shared Components), which a
# pointer document may name the *document* for but must never restate
# itself (SSOT partition, IMPLEMENTATION.md Conventions).
PREFIX_LITERAL = "EM_WORKFLOW_TERMINAL:"
FIELD_NAME_TOKENS = ("`state`", "`step`", "`reason`", "`detail`")
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
)
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
    """The contract-literal absence matcher (AC-3): returns a list of
    human-readable violation descriptions if `text` restates any of the
    contract's literals, empty when none is restated. The four field names
    are checked as a GROUP (all four backticked together) rather than as
    individual words, since `step` alone is ordinary vocabulary this very
    document already uses for its workflow steps -- checking it in
    isolation would false-positive on unrelated prose."""
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

    def test_subsection_states_wait_turn_emits_no_terminal_line(self):
        self.assertIn("停止条件 5", self.section)
        self.assertIn("終端行を出力しない", self.section)

    def test_step_c_report_item_points_at_terminal_line(self):
        self.assertIn(CONTRACT_DOC_REFERENCE, self.step_c_section)
        self.assertIn(
            _strip_ws("この報告のあとに終端行を追記する"),
            _strip_ws(self.step_c_section),
        )


class TestSubsectionRestatesNoContractLiteral(unittest.TestCase):
    """AC-3: the new subsection restates none of the contract's literals.
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
    """AC-3 / Test Notes: negative proof plus non-vacuity guard for the
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


class TestStepCCompletionReportNonRegression(unittest.TestCase):
    """AC-4 / TS5: every element of the Step C completion report survives
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
