"""Tests for task0002 (batch-verify-rework-lineage-cap): the develop-skill's
batch-only stop-condition exception for a verify cap-reached run, the
Step C entry-condition heading rewrite, and the cap-reached run's terminal
line.

Covers task0002 Acceptance Criteria
(feature-docs/batch-verify-rework-lineage-cap/tasks/task0002.md):

- AC-1 (FR7): SKILL.md carries a batch-only independent clause in Step B
  stating that, when batch mode AND a lineage/hard-cap-reached `failed`
  verify coincide, both stop condition 3 and stop condition 1 are excepted;
  non-applicable cases (other `failed` reasons, interactive) are named too.
- AC-2 (FR7 / regression): the pre-existing automatic-re-entry carve-out
  block's body and exhaustiveness claim are untouched -- verified by running
  tests/test_develop_skill_rewiring.py unmodified (not duplicated here; this
  module additionally pins the new clause's placement OUTSIDE that block).
- AC-3 (FR7): 「ターンを終わらせていい唯一の条件」's conditions 1 and 3 can
  reach the new clause via a pointer sentence (items 1-7's own text is
  pinned byte-for-byte by tests/test_develop_once_option.py's
  ITEMS_1_TO_6_VERBATIM + ITEM_7_VERBATIM adjacency check, so this task adds
  no text to condition 1 or condition 3 themselves -- the pointer sentence
  sits right after item 7, before the closing anchor).
- AC-4 (FR6): the Step C heading is rewritten to admit entry when verify
  remains `failed` solely because of cap-reached (in addition to the
  pre-existing all-`completed`/`design`-`skipped` path).
- AC-5 (FR6): the new heading string is reflected byte-for-byte in SKILL.md
  and in both sibling test modules' STEP_C_HEADING constants.
- AC-6 (FR11): 「## バッチ終端行」 states the cap-reached run's terminal
  outcome (stopped, not completed; step verify; detail names Step C
  completion) and keeps the section's pre-existing content.
- AC-7 (NFR5): `em-workflow/references/batch-terminal-line.md` is not part
  of this task's file scope and is never read or asserted against here
  (Test Notes: avoid unnecessary coupling to a file this task does not
  change) -- verified by construction (not present in expected_files / not
  written by this task), not by an in-repo unit test.
- AC-8 (NFR3, NFR4): this module imports the standard library only, and its
  new matchers each carry a negative proof against synthetic text reviving
  the old wording, plus a non-vacuity guard.

Deviation from AC-6's literal wording (recorded in the implementer report):
the task plan's own AC-6 text uses `reason=verify_rework_cap_reached` as
shorthand, but that literal string cannot be written into SKILL.md -- doing
so trips the pre-existing whole-file reason-code absence guard in BOTH
tests/test_batch_quiet_output_skill_wiring.py
(`TestWholeFileForbiddenLiteralAbsence`) and
tests/test_batch_stop_contract_skill_wiring.py
(`TestStateValueGuardWholeFileScope`), neither of which this task may edit
beyond the STEP_C_HEADING constant (D8 ownership table). SKILL.md instead
names the stop point `verify-rework-cap`, which
`references/batch-terminal-line.md`'s Stop point coverage table already
binds to that reason code (IMPLEMENTATION.md D5) -- the same NFR1-SSOT-
preserving pattern this document already uses everywhere else for terminal-
line values (e.g. the `state` domain, the removed "2 つの終端状態" count).
This module asserts the stop point identifier and the descriptive prose
(stopped, not completed; step verify), never the raw reason-code literal,
and positively asserts the literal's absence.

This is a documentation-contract task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following
the pattern of tests/test_batch_stop_contract_skill_wiring.py and
tests/test_develop_skill_rewiring.py: standard library only, no import from
another test module (sibling test modules' STEP_C_HEADING constants are
read as raw source text and regex-extracted, never imported -- importing
would run those modules' tests a second time under this module's own
discovery), constants re-declared locally.

Matcher -> negative-proof inventory (Test Notes: every new matcher carries a
negative proof over a forged/synthetic sample plus a non-vacuity guard):

- `_states_step_c_cap_continuation_heading` (TS6): negative proof is
  TestMatchersRejectOldWording.test_heading_matcher_rejects_the_old_heading,
  non-vacuity guard is
  TestMatchersRejectOldWording.test_heading_matcher_accepts_the_new_heading.
- `_states_cap_reached_continues_to_step_c` (TS15): negative proof is
  TestMatchersRejectOldWording.test_continuation_matcher_rejects_old_stop_on_cap_wording,
  non-vacuity guard is
  TestMatchersRejectOldWording.test_continuation_matcher_accepts_the_real_clause.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
QUIET_OUTPUT_TEST_PATH = Path(__file__).resolve().parent / "test_batch_quiet_output_skill_wiring.py"
STOP_CONTRACT_TEST_PATH = Path(__file__).resolve().parent / "test_batch_stop_contract_skill_wiring.py"

STEP_B_HEADING = "## Step B: 自走ループ"
DESIGN_BRANCH_HEADING = "### design ステップ分岐"
TURN_END_HEADING = "### ターンを終わらせていい唯一の条件"
TURN_END_ANCHOR = "これらに該当しない限り"
TERMINAL_LINE_HEADING = "## バッチ終端行"
FILE_END_MARKER = "$ARGUMENTS"

# Verbatim, taken from tests/test_develop_skill_rewiring.py -- redeclared
# locally rather than imported (Cross-module isolation convention).
STOP_CONDITION_3_LABEL = "**停止条件 3 との優先関係**"
CREATE_PLAN_EXEMPTION_RATIONALE_LABEL = "**create-plan が `in_progress` を経ない理由**"

# This task's own new clause label (Step B, D4's independent-clause design;
# distinct from the "Step C 見出し文字列" shared component below).
BATCH_CAP_EXCEPTION_LABEL = "**batch: verify の cap 到達に対する停止条件の例外**"

# The Step C heading this task owns (IMPLEMENTATION.md Shared Components
# "Step C 見出し文字列"): must be byte-for-byte identical in SKILL.md and
# both sibling test modules' STEP_C_HEADING constants.
NEW_STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — "
    "か、cap 到達により verify が `failed` のまま残る場合のみ）"
)
OLD_STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — 時のみ）"
)

# The stop point identifier `references/batch-terminal-line.md`'s Stop
# point coverage table already binds to the `verify_rework_cap_reached`
# reason code (IMPLEMENTATION.md D5) -- SKILL.md names the identifier
# rather than the reason-code literal itself (module docstring deviation
# note).
CAP_REACHED_STOP_POINT = "verify-rework-cap"

# The literal this task must never write into SKILL.md (see deviation
# note). Declared locally for an ABSENCE check only -- this module never
# asserts that references/batch-terminal-line.md defines it.
FORBIDDEN_REASON_CODE_LITERAL = "verify_rework_cap_reached"

STEP_C_HEADING_CONST_PATTERN = re.compile(r'STEP_C_HEADING\s*=\s*\(\s*"([^"]*)"\s*\)')


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


def _extract_step_c_heading_constant(test_module_text):
    """Extracts a sibling test module's STEP_C_HEADING constant string
    value from its SOURCE TEXT, without importing the module (Test Notes:
    importing would run that module's tests a second time under this
    module's own `unittest discover`)."""
    match = STEP_C_HEADING_CONST_PATTERN.search(test_module_text)
    if match is None:
        raise AssertionError(
            "could not find a STEP_C_HEADING = (\"...\") constant in the "
            "given module text"
        )
    return match.group(1)


def _states_step_c_cap_continuation_heading(heading):
    """TS6 matcher: true iff `heading` expresses BOTH Step C entry paths --
    the pre-existing all-`completed`/`design`-`skipped` path AND the new
    cap-reached-`failed` path."""
    return (
        "全 step completed" in heading
        and "design のみ" in heading
        and "skipped" in heading
        and "cap" in heading
        and "`failed`" in heading
    )


def _states_cap_reached_continues_to_step_c(section):
    """TS15 matcher: true iff `section` states that a cap-reached verify
    failure does NOT stop the run short -- retrospect completes and Step C
    is entered -- rather than the pre-task0002 behaviour (cap reached ->
    report `failed` and stop)."""
    stripped = _strip_ws(section)
    return (
        _strip_ws("Step C へ進み") in stripped
        and _strip_ws("走行を完了させてよい") in stripped
    )


class TestBatchCapExceptionClausePlacement(unittest.TestCase):
    """AC-1, AC-2, AC-3 (TS15): the new batch-only clause exists, states its
    scope precisely, and sits outside the pre-existing automatic-re-entry
    carve-out block (IMPLEMENTATION.md D4's placement constraint)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b_section = _section(cls.text, STEP_B_HEADING, DESIGN_BRANCH_HEADING)
        cls.carve_out_section = _section(
            cls.step_b_section,
            STOP_CONDITION_3_LABEL,
            CREATE_PLAN_EXEMPTION_RATIONALE_LABEL,
        )
        # Sliced to the END of step_b_section (not re-bounded by
        # DESIGN_BRANCH_HEADING): step_b_section is already exclusive of
        # that marker, so it cannot serve as an end marker within it.
        cls.clause_section = cls.step_b_section[
            cls.step_b_section.index(BATCH_CAP_EXCEPTION_LABEL) :
        ]

    def test_clause_label_present_in_step_b(self):
        self.assertIn(BATCH_CAP_EXCEPTION_LABEL, self.step_b_section)

    def test_clause_sits_outside_the_existing_carve_out_block(self):
        # D4's placement constraint, enforced mechanically: the new
        # clause's own label must not appear inside the pre-existing
        # carve-out block's text range.
        self.assertNotIn(BATCH_CAP_EXCEPTION_LABEL, self.carve_out_section)

    def test_applicability_is_conjunctive_batch_and_cap_failed(self):
        stripped = _strip_ws(self.clause_section)
        self.assertIn("batch", self.clause_section)
        self.assertTrue(
            _strip_ws("系譜 cap") in stripped or _strip_ws("hard cap") in stripped
        )
        self.assertIn("`failed`", self.clause_section)

    def test_stop_condition_3_exception_wording(self):
        self.assertIn("停止条件 3", self.clause_section)
        self.assertIn(
            _strip_ws("この `failed` を停止理由にしない"),
            _strip_ws(self.clause_section),
        )

    def test_stop_condition_1_exception_wording(self):
        self.assertIn("停止条件 1", self.clause_section)
        self.assertIn("retrospect", self.clause_section)
        self.assertTrue(
            _states_cap_reached_continues_to_step_c(self.clause_section),
            "expected the clause to state that a cap-reached verify "
            "failure lets the run continue to Step C rather than stopping",
        )

    def test_non_applicability_names_other_failed_reasons(self):
        self.assertIn(_strip_ws("implement の失敗"), _strip_ws(self.clause_section))
        self.assertIn(_strip_ws("review の失敗"), _strip_ws(self.clause_section))
        self.assertIn(
            _strip_ws("cap 未到達の verify 失敗"), _strip_ws(self.clause_section)
        )

    def test_non_applicability_excludes_interactive(self):
        self.assertIn(
            _strip_ws("interactive にも"), _strip_ws(self.clause_section)
        )
        self.assertIn("適用されない", self.clause_section)

    def test_verify_status_stays_failed_no_deferred_status(self):
        self.assertIn(
            _strip_ws("`verify.status` は `failed` のまま"),
            _strip_ws(self.clause_section),
        )
        self.assertIn("`deferred`", self.clause_section)

    def test_clause_declares_independence_from_existing_carve_out(self):
        self.assertIn(
            _strip_ws("網羅性宣言を変更しない"), _strip_ws(self.clause_section)
        )


class TestTurnEndConditionsReferenceTheNewClause(unittest.TestCase):
    """AC-3: 条件 1・条件 3 から新条項へ到達できる, via a pointer sentence
    placed after item 7 (items 1-7's own text is pinned byte-for-byte
    elsewhere -- tests/test_develop_once_option.py's ITEMS_1_TO_6_VERBATIM
    + ITEM_7_VERBATIM adjacency check -- so this task must not edit their
    own wording)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.turn_end_section = _section(cls.text, TURN_END_HEADING, TURN_END_ANCHOR)

    def test_pointer_sentence_names_conditions_1_and_3(self):
        self.assertIn("条件 1", self.turn_end_section)
        self.assertIn("条件 3", self.turn_end_section)
        self.assertIn(BATCH_CAP_EXCEPTION_LABEL, self.turn_end_section)

    def test_pointer_sentence_follows_item_7_without_disturbing_it(self):
        item_7_idx = self.turn_end_section.index("7. `--once`")
        pointer_idx = self.turn_end_section.index(BATCH_CAP_EXCEPTION_LABEL)
        self.assertGreater(pointer_idx, item_7_idx)

    def test_item_7_text_is_still_present_verbatim(self):
        # Non-vacuity guard for the ordering check above: item 7's own
        # wording must still be intact for "follows item 7" to mean
        # anything.
        self.assertIn(
            "7. `--once` 指定時、1 フェーズが完了したとき（フェーズ境界の定義は下記",
            self.turn_end_section,
        )


class TestStepCHeadingExpressesCapContinuation(unittest.TestCase):
    """AC-4, AC-5 (TS6): the Step C heading is rewritten to admit the
    cap-reached-`failed` entry path, and the exact same string is reflected
    in both sibling test modules' STEP_C_HEADING constants."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.quiet_output_test_text = _read(QUIET_OUTPUT_TEST_PATH)
        cls.stop_contract_test_text = _read(STOP_CONTRACT_TEST_PATH)

    def test_new_heading_present_in_skill_md(self):
        self.assertIn(NEW_STEP_C_HEADING, self.text)

    def test_old_heading_is_gone_from_skill_md(self):
        self.assertNotIn(OLD_STEP_C_HEADING, self.text)

    def test_quiet_output_module_constant_matches_byte_for_byte(self):
        constant = _extract_step_c_heading_constant(self.quiet_output_test_text)
        self.assertEqual(constant, NEW_STEP_C_HEADING)

    def test_stop_contract_module_constant_matches_byte_for_byte(self):
        constant = _extract_step_c_heading_constant(self.stop_contract_test_text)
        self.assertEqual(constant, NEW_STEP_C_HEADING)

    def test_all_three_sites_are_identical(self):
        skill_heading = next(
            line for line in self.text.splitlines() if line.startswith("## Step C: ")
        )
        quiet_constant = _extract_step_c_heading_constant(self.quiet_output_test_text)
        stop_constant = _extract_step_c_heading_constant(self.stop_contract_test_text)
        self.assertEqual(skill_heading, quiet_constant)
        self.assertEqual(skill_heading, stop_constant)

    def test_sibling_modules_setup_class_do_not_raise(self):
        # AC-5: any class in either sibling module that slices on
        # STEP_C_HEADING must find it in the (now-rewritten) real file --
        # exercised for real by running those modules' own suites, proven
        # here structurally by confirming the constant is a literal
        # substring of the real SKILL.md text (which is exactly what
        # `_section`'s `.index()` call requires to not raise).
        constant = _extract_step_c_heading_constant(self.quiet_output_test_text)
        self.assertIn(constant, self.text)


class TestTerminalLineCapReachedState(unittest.TestCase):
    """AC-6 (TS15): the バッチ終端行 section states the cap-reached run's
    terminal outcome (stopped, not completed; step verify; detail names
    Step C completion), citing the stop point rather than restating the
    reason-code literal (module docstring deviation note), and retains the
    section's pre-existing content."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, TERMINAL_LINE_HEADING, FILE_END_MARKER)

    def test_existing_section_content_is_retained(self):
        self.assertIn("対象は Step C の完了処理（通常完了）と", self.section)
        self.assertIn("終端行を出力しない", self.section)
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md` を Read し、",
            self.section,
        )

    def test_stop_point_identifier_is_named(self):
        self.assertIn(f"`{CAP_REACHED_STOP_POINT}`", self.section)

    def test_terminal_state_is_stopped_not_completed(self):
        self.assertIn(
            _strip_ws("通常完了ではなく停止として終端行を出す"),
            _strip_ws(self.section),
        )

    def test_executed_step_is_verify(self):
        self.assertIn(
            _strip_ws("cap 到達走行の実行した step は verify である"),
            _strip_ws(self.section),
        )

    def test_detail_names_step_c_completion(self):
        self.assertIn(
            _strip_ws("Step C まで到達し、worktree 掃除と終了報告は完了した"),
            _strip_ws(self.section),
        )

    def test_one_line_per_run_emitted_right_after_step_c_report(self):
        self.assertIn(
            _strip_ws("1 走行につき 1 行"), _strip_ws(self.section)
        )
        self.assertIn(
            _strip_ws("Step C の完了報告の直後"), _strip_ws(self.section)
        )

    def test_reason_code_literal_is_never_restated_anywhere_in_skill_md(self):
        # NFR1 / D5 (module docstring deviation note): the reason code
        # remains defined in exactly one place -- never here.
        self.assertNotIn(FORBIDDEN_REASON_CODE_LITERAL, self.text)


class TestMatchersRejectOldWording(unittest.TestCase):
    """AC-8: negative proofs plus non-vacuity guards for both new matchers,
    exercised against synthetic text reviving the pre-task0002 wording
    (Test Notes: "旧文言...を含む合成テキストに対して同じ matcher が
    失敗することを示す負の証明")."""

    def test_heading_matcher_rejects_the_old_heading(self):
        self.assertFalse(_states_step_c_cap_continuation_heading(OLD_STEP_C_HEADING))

    def test_heading_matcher_accepts_the_new_heading(self):
        self.assertTrue(_states_step_c_cap_continuation_heading(NEW_STEP_C_HEADING))

    def test_continuation_matcher_rejects_old_stop_on_cap_wording(self):
        forged_old_text = (
            "batch: 確認せず自動 rework。`batch.verify_rework_count == 0` "
            "なら interactive と同じ手順で rework-planner を dispatch し、"
            "カウンタを +1、既に 1 以上なら `failed` のまま報告して停止する。"
        )
        self.assertFalse(_states_cap_reached_continues_to_step_c(forged_old_text))

    def test_forged_old_text_is_well_formed_and_found(self):
        # Non-vacuity guard: the forged sample genuinely describes the old
        # stop-on-cap behaviour (not some unrelated text the matcher would
        # trivially reject for the wrong reason).
        forged_old_text = (
            "batch: 確認せず自動 rework。`batch.verify_rework_count == 0` "
            "なら interactive と同じ手順で rework-planner を dispatch し、"
            "カウンタを +1、既に 1 以上なら `failed` のまま報告して停止する。"
        )
        self.assertIn("既に 1 以上なら", forged_old_text)
        self.assertIn("停止する", forged_old_text)

    def test_continuation_matcher_accepts_the_real_clause(self):
        text = _read(SKILL_PATH)
        step_b_section = _section(text, STEP_B_HEADING, DESIGN_BRANCH_HEADING)
        clause_section = step_b_section[
            step_b_section.index(BATCH_CAP_EXCEPTION_LABEL) :
        ]
        self.assertTrue(_states_cap_reached_continues_to_step_c(clause_section))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """NFR3/NFR4: this module imports the Python standard library only."""

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
