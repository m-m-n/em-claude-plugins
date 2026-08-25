"""Tests for task0001 (develop-once-option): SKILL.md's `--once` argument
handling, phase-boundary definition, stop condition 7, non-boundaries, and
the interactive closing line.

Covers task0001 Acceptance Criteria
(feature-docs/develop-once-option/tasks/task0001.md):

- AC-1 (FR1): 「引数処理」 gains a `--once` item stating (a) it ends the turn
  after exactly one phase, (b) it combines with `--batch`, (c) it is a
  per-invocation setting persisted neither to `workflow.yaml` nor to
  `phase-state/`; the frontmatter `argument-hint` includes `--once` and
  retains every pre-existing token.
- AC-2 (FR2, FR3, FR4, FR5): SKILL.md states all four phase-boundary kinds
  -- ordinary step, `retrospect`, verify-fail rework, automatic re-entry --
  each ending the turn once the corresponding state change is committed.
- AC-3 (FR6, NFR4): 「ターンを終わらせていい唯一の条件」 gains item 7 with
  items 1-6 unchanged (verbatim, byte-for-byte) and the closing anchor
  sentence still following the list.
- AC-4 (FR14): `--once` never ends the turn inside the implement phase; stop
  condition 5's wait turns and implement's launch/wake turns are stated as
  non-terminal.
- AC-5 (FR12): the interactive `--once` closing line matches SPEC.md FR12's
  wording exactly (whitespace-stripped, per this document's hard-wrap
  convention).
- AC-6 (NFR4, IMPLEMENTATION.md D3): the new content satisfies the D3
  placement invariants relevant to this task -- it sits before 「## 停止時の
  報告」, SKILL.md names no terminal-line `state` value literal anywhere,
  and the content this task added introduces no `gate_id` / "gate ID"
  mention.
- AC-7 (NFR2, NFR3): this module is discovered by
  `python3 -m unittest discover -s tests`, imports the Python standard
  library only, and every matcher added here carries a negative proof plus
  a non-vacuity guard.

This is a documentation-only task (Test Notes: unit-level structural
assertions over SKILL.md's raw text; no runtime behaviour changes, NFR2),
following the pattern established by tests/test_develop_skill_rewiring.py --
same target file, self-contained helpers, no cross-module import
(Cross-module isolation convention, IMPLEMENTATION.md Conventions).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

ARGUMENT_PROCESSING_HEADING = "## 引数処理"
STEP_0_HEADING = "## Step 0"
TURN_END_HEADING = "### ターンを終わらせていい唯一の条件"
TURN_END_ANCHOR = "これらに該当しない限り"
ONCE_SECTION_HEADING = "## `--once` のフェーズ境界"
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"
ONCE_BULLET_START_MARKER = "- `--once`:"
ONCE_BULLET_END_MARKER = "- パス引数"

BOUNDARY_TABLE_HEADER = '| 境界 | ターンが終わる条件 | 次の起動が再開する位置 |'
BOUNDARY_KIND_LABELS = ("通常の step", "`retrospect`", "verify 失敗時の rework", "自動再エントリ")

# IMPLEMENTATION.md D1's third terminal-line `state` value literal. Declared
# locally -- never imported from another module (Cross-module isolation,
# IMPLEMENTATION.md Conventions) -- and used for absence checks only. This
# module never asserts that any document DEFINES it; task0003 owns that.
PHASE_DONE_VALUE = "phase_done"
STATE_VALUE_DOMAIN = ("completed", "stopped", PHASE_DONE_VALUE)

# The interactive `--once` closing line, SPEC.md FR12's exact wording
# (feature-docs/develop-once-option/SPEC.md).
CLOSING_LINE = '{step} が完了したよ。続きは /clear してから /em-workflow:develop {feature} を実行してね'

# The pre-existing wording of stop conditions 1-6, captured verbatim before
# this task's change (AC-3: item 7 is appended without altering a single
# character of the existing six).
ITEMS_1_TO_6_VERBATIM = '1. `workflow` 配列の全 step が `completed`、ただし design のみ `skipped` も\n   可（完了処理まで済ませた後）\n2. ある step を 2 回連続で実行しても status が進まない（= スタック）\n3. ある step の status が `failed` / `needs_update`（= ユーザー介入が必要。\n   ただし、フェーズプロトコルがそのフェーズの自動再エントリのために設定した\n   `needs_update` の間はこの条件では停止しない — 詳細は Step B の\n   「**停止条件 3 との優先関係**」参照）\n4. workflow.yaml の YAML parse エラー（= リカバリ不能）\n5. implement フェーズでバックグラウンド implementer の完了通知を待つとき\n   （= キューループが定める正常な待機。次の 2 形がある:\n   (a) 起動/補充した直後、(b) failed 発生後のドレイン中 — 新規投入は\n   止めて in-flight の完了通知だけを待ち、全て回収してからユーザー三択を\n   出す（batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の\n   failed で中断 — `batch-mode.md` の Non-packet gates 表、\n   `implement.failed-task`）。通知で起こされたら reconcile\n   → 補充（ドレイン中は補充しない）→\n   また待つ。queue_stop_guard hook が「空きスロットがあるのに補充せず\n   終える」ターンだけを exit 2 で弾き、failed 存在時はブロックしない）\n6. Step 0 の git-setup ゲートが中断を報告したとき\n   （gitleaks 不在 / git リポジトリでない / guard 失敗）\n'

ITEM_7_VERBATIM = '7. `--once` 指定時、1 フェーズが完了したとき（フェーズ境界の定義は下記\n   「`--once` のフェーズ境界」参照）'

ARGUMENT_HINT_LINE = 'argument-hint: "[feature-path] [--report-only] [--batch] [--once] [task-description]"'


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


def _extract_boundary_rows(text):
    """Returns the data rows of the phase-boundary table (each a raw
    ``| ... | ... | ... |`` line), skipping the header and separator rows.
    Empty list if the table header is absent."""
    if BOUNDARY_TABLE_HEADER not in text:
        return []
    rest = text[text.index(BOUNDARY_TABLE_HEADER):]
    lines = rest.splitlines()
    rows = []
    for line in lines[2:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return rows


def _covers_all_four_phase_boundary_kinds(text):
    """AC-2's matcher: true iff `text` contains the phase-boundary table
    with exactly the four expected kinds, in order, and each row states
    that the boundary is reached once the corresponding change is
    committed (「コミット済み」)."""
    rows = _extract_boundary_rows(text)
    if len(rows) != 4:
        return False
    for label, row in zip(BOUNDARY_KIND_LABELS, rows):
        if label not in row:
            return False
        if "コミット済み" not in row:
            return False
    return True


def _restates_state_value_literal(text):
    """AC-6 / IMPLEMENTATION.md D3-5 matcher: true iff `text` names a
    terminal-line `state` value -- either the contract shape
    ``state={value}`` (bare, backticked or double-quoted) for any member of
    the domain, or the bare `--once`-boundary value on its own (D2 rule 2:
    it is contract-only vocabulary that occurs nowhere else, so a bare
    check adds no false-positive surface)."""
    for value in STATE_VALUE_DOMAIN:
        for shape in (f"state={value}", f"`state={value}`", f'"state={value}"'):
            if shape in text:
                return True
    if PHASE_DONE_VALUE in text:
        return True
    return False


class TestArgumentProcessingOnceOption(unittest.TestCase):
    """AC-1: 「引数処理」 documents `--once` as per-invocation, combinable
    with `--batch`, and persisted nowhere; the frontmatter `argument-hint`
    includes it alongside every pre-existing token."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(
            cls.text, ARGUMENT_PROCESSING_HEADING, STEP_0_HEADING
        )

    def test_once_bullet_present(self):
        self.assertIn("`--once`:", self.section)

    def test_ends_turn_after_one_phase(self):
        self.assertIn(
            _strip_ws("指定時は 1 フェーズを実行してターンを終える"),
            _strip_ws(self.section),
        )

    def test_combinable_with_batch(self):
        self.assertIn("`--batch` と併用できる", self.section)

    def test_not_persisted_to_workflow_yaml_or_phase_state(self):
        self.assertIn(
            _strip_ws("`workflow.yaml` にも `phase-state/` にも一切記録しない"),
            _strip_ws(self.section),
        )

    def test_argument_hint_line_includes_once_and_retains_existing_tokens(self):
        self.assertIn(ARGUMENT_HINT_LINE, self.text)
        for token in (
            "feature-path",
            "--report-only",
            "--batch",
            "--once",
            "task-description",
        ):
            self.assertIn(token, ARGUMENT_HINT_LINE)


class TestStopCondition7AppendedWithoutAlteringExisting(unittest.TestCase):
    """AC-3: item 7 is appended, items 1-6 keep their current wording
    verbatim, and the closing anchor sentence still follows the list."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.turn_end_section = _section(
            cls.text, TURN_END_HEADING, TURN_END_ANCHOR
        )

    def test_items_1_to_6_immediately_followed_by_item_7_unchanged(self):
        # A single substring check proves three things at once: items 1-6
        # are present byte-for-byte as captured before this task's change,
        # item 7 immediately follows with nothing inserted between them,
        # and nothing was appended after item 6 elsewhere in the list.
        self.assertIn(
            ITEMS_1_TO_6_VERBATIM + ITEM_7_VERBATIM, self.turn_end_section
        )

    def test_item_7_mentions_once(self):
        self.assertIn("`--once`", ITEM_7_VERBATIM)

    def test_anchor_sentence_follows_item_7(self):
        item_7_idx = self.text.index("7. `--once`")
        anchor_idx = self.text.index(TURN_END_ANCHOR, item_7_idx)
        self.assertGreater(anchor_idx, item_7_idx)


class TestOnceSectionCoversAllFourPhaseBoundaryKinds(unittest.TestCase):
    """AC-2: SKILL.md states all four phase-boundary kinds, each reached
    once the corresponding change is committed."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(
            cls.text, ONCE_SECTION_HEADING, STOP_REPORT_HEADING
        )

    def test_blanket_committed_sentence_present(self):
        self.assertIn(
            _strip_ws("コミット済みになった時点で"), _strip_ws(self.section)
        )

    def test_covers_all_four_phase_boundary_kinds(self):
        self.assertTrue(
            _covers_all_four_phase_boundary_kinds(self.section),
            "expected the phase-boundary table to state exactly the four "
            "kinds, each committed",
        )

    def test_ordinary_step_boundary_names_design_skipped_exception(self):
        self.assertIn(
            "`design` のみ `skipped`", self.section
        )

    def test_retrospect_boundary_defers_step_c_to_next_launch(self):
        self.assertIn(
            _strip_ws("StepC（完了処理）はここでは実行せず"),
            _strip_ws(self.section),
        )

    def test_verify_fail_rework_boundary_names_implement_and_verify_pending(self):
        self.assertIn(
            "`implement` と `verify` を `pending` に戻し", self.section
        )

    def test_automatic_reentry_boundary_names_both_transitions(self):
        self.assertIn("`create-plan` → `needs_update`", self.section)
        self.assertIn("`create-spec` → `needs_update`", self.section)


class TestPhaseBoundaryMatcherCanFail(unittest.TestCase):
    """AC-2 / NFR3: negative proof plus non-vacuity guard for
    `_covers_all_four_phase_boundary_kinds` -- a forged section stating
    only three of the four boundary kinds (omitting automatic re-entry)."""

    FORGED_THREE_KIND_TEXT = (
        "...\n\n"
        f"{ONCE_SECTION_HEADING}\n\n"
        "`--once` 指定時にターンを終える境界は次の 3 種。\n\n"
        f"{BOUNDARY_TABLE_HEADER}\n"
        "|---|---|---|\n"
        "| 通常の step | ...コミット済み | 次の step |\n"
        "| `retrospect` | ...コミット済み | Step C（完了処理） |\n"
        "| verify 失敗時の rework | ...コミット済み | `implement` |\n"
        "\n"
        f"{STOP_REPORT_HEADING}\n"
    )

    def test_forged_three_kind_table_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds the section, it genuinely has
        # exactly three data rows, and each of the three names its expected
        # boundary kind -- so the rejection below exercises the count/kind
        # comparison, not a slicing or fixture defect.
        section = _section(
            self.FORGED_THREE_KIND_TEXT, ONCE_SECTION_HEADING, STOP_REPORT_HEADING
        )
        rows = _extract_boundary_rows(section)
        self.assertEqual(len(rows), 3)
        self.assertIn("通常の step", section)
        self.assertIn("`retrospect`", section)
        self.assertIn("verify 失敗時の rework", section)
        self.assertNotIn("自動再エントリ", section)

    def test_matcher_rejects_the_three_kind_forgery(self):
        section = _section(
            self.FORGED_THREE_KIND_TEXT, ONCE_SECTION_HEADING, STOP_REPORT_HEADING
        )
        self.assertFalse(
            _covers_all_four_phase_boundary_kinds(section),
            "matcher failed to detect the missing automatic-re-entry "
            "boundary kind",
        )


class TestNonBoundariesStated(unittest.TestCase):
    """AC-4 (FR14): `--once` never ends the turn inside the implement
    phase; stop condition 5's wait turns and implement's launch/wake turns
    are stated as non-terminal."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(
            cls.text, ONCE_SECTION_HEADING, STOP_REPORT_HEADING
        )

    def test_no_mid_implement_termination(self):
        self.assertIn(
            _strip_ws("implementフェーズの途中ではターンを終えない"),
            _strip_ws(self.section),
        )
        self.assertIn(
            _strip_ws("in-flightの実装者がプロセス終了で失われるため"),
            _strip_ws(self.section),
        )

    def test_stop_condition_5_wait_turn_is_non_terminal(self):
        self.assertIn("停止条件 5", self.section)

    def test_implement_launch_and_wake_turns_are_non_terminal(self):
        self.assertIn(
            _strip_ws("launch / wakeターンは非終端"), _strip_ws(self.section)
        )


class TestInteractiveClosingLineMatchesSpecFR12(unittest.TestCase):
    """AC-5: the interactive `--once` closing line matches SPEC.md FR12's
    wording exactly, whitespace-stripped."""

    def test_closing_line_present_verbatim(self):
        text = _read(SKILL_PATH)
        self.assertIn(_strip_ws(CLOSING_LINE), _strip_ws(text))

    def test_closing_line_carries_both_placeholders(self):
        self.assertIn("{step}", CLOSING_LINE)
        self.assertIn("{feature}", CLOSING_LINE)


class TestPlacementInvariantsD3(unittest.TestCase):
    """AC-6 (IMPLEMENTATION.md D3): the new content sits before 「## 停止時の
    報告」, SKILL.md names no terminal-line `state` value literal anywhere,
    and the content this task added introduces no `gate_id` mention."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.once_section = _section(
            cls.text, ONCE_SECTION_HEADING, STOP_REPORT_HEADING
        )
        arg_section = _section(
            cls.text, ARGUMENT_PROCESSING_HEADING, STEP_0_HEADING
        )
        cls.once_bullet = _section(
            arg_section, ONCE_BULLET_START_MARKER, ONCE_BULLET_END_MARKER
        )

    def test_once_section_precedes_stop_report_heading(self):
        once_idx = self.text.index(ONCE_SECTION_HEADING)
        stop_report_idx = self.text.index(STOP_REPORT_HEADING)
        self.assertLess(once_idx, stop_report_idx)

    def test_no_state_value_literal_anywhere_in_skill_md(self):
        self.assertFalse(
            _restates_state_value_literal(self.text),
            "SKILL.md must name no terminal-line `state` value literal "
            "anywhere (D3-5); the state is described by role, the value "
            "is left to the SSOT",
        )

    def test_new_content_introduces_no_gate_id_mention(self):
        new_content = self.once_section + self.once_bullet + ITEM_7_VERBATIM
        self.assertNotIn("gate_id", new_content)
        self.assertNotIn("gate ID", new_content)


class TestStateValueLiteralMatcherCanFail(unittest.TestCase):
    """AC-6 / NFR3: negative proof plus non-vacuity guard for
    `_restates_state_value_literal` -- a forged excerpt that restates the
    `--once` boundary's `state` value in the contract shape."""

    FORGED_STATE_LITERAL_TEXT = (
        "`--once` が終わるとターンは `state=phase_done` になる。"
    )

    def test_forged_text_is_well_formed_and_contains_the_literal(self):
        # Non-vacuity guard: the forged excerpt genuinely carries the
        # contract-shaped literal, so the rejection below exercises the
        # comparison, not a fixture defect.
        self.assertIn(PHASE_DONE_VALUE, self.FORGED_STATE_LITERAL_TEXT)
        self.assertIn("state=", self.FORGED_STATE_LITERAL_TEXT)

    def test_matcher_rejects_the_forged_state_literal(self):
        self.assertTrue(
            _restates_state_value_literal(self.FORGED_STATE_LITERAL_TEXT),
            "matcher failed to detect the forged state-value restatement",
        )

    def test_matcher_passes_ordinary_step_status_prose(self):
        # False-positive guard: bare `completed` / `stopped` as ordinary
        # workflow.yaml step-status vocabulary must not be flagged -- the
        # real SKILL.md uses `completed` extensively for step statuses.
        ordinary_prose = "step の `status` が `completed` になり、コミット済み"
        self.assertFalse(_restates_state_value_literal(ordinary_prose))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-7 / NFR3: this module imports the Python standard library only."""

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
