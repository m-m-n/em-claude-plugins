"""Tests for review-gate-abort-recovery/task0002: the develop skill cites
review-phase.md Phase R5's gate-abort rule and legacy recovery procedure.

Covers task0002 Acceptance Criteria
(feature-docs/review-gate-abort-recovery/tasks/task0002.md):

- AC-1 (FR2): Step B's spec-change gate-call paragraph carries a citation
  that names `references/review-phase.md`, `Phase R5` and the gate-abort
  block's label text on a single line, and states that the review status
  written at that stop and the resume path are defined there and not
  restated here. The pre-change paragraph, verbatim, is rejected.
- AC-2 (FR2, NFR3, NFR4): the paragraph contains none of the values the
  cited block owns; a synthetic paragraph restating a value is flagged.
  (The pins of `TestDevelopSkillStepBSpecChangeGateCall` in
  tests/test_gate_outcome_packet_lifecycle.py are exercised by the full
  suite, unedited.)
- AC-3 (FR4): the 停止時の報告 section carries a paragraph stating that a
  stop-condition-3 stop on the `review` step's `failed` carries the legacy
  recovery procedure -- its location together with its content -- in the
  report and, in batch, in `resume_conditions`, citing
  `references/review-phase.md`, `Phase R5` and the recovery block's label
  text. The pre-change section, verbatim, is rejected.
- AC-4 (FR4, NFR3, NFR4): the section restates none of the cited block's
  decision / status / classification literals; a synthetic section that
  restates the applicability condition is flagged. (The pins that
  tests/test_batch_quiet_output_skill_wiring.py and
  tests/test_batch_stop_contract_skill_wiring.py hold on this section are
  exercised by the full suite, unedited.)
- AC-5 (NFR1): the verbatim anchors of every stop-condition-3 text this
  feature must not change are present (whitespace-stripped comparison), and
  exactly three top-level bullets lie inside the priority block's
  enumeration. A synthetic four-bullet enumeration is rejected.
- AC-6 (FR6, NFR2): every matcher below has a negative twin its matcher
  rejects, every sliced region has a non-vacuity check, the
  "interactive はこの改訂で変更しない" statement stays in the gate-call
  paragraph, and the interactive-question tool name keeps its baseline
  count in the develop skill.
- AC-7 (NFR4, NFR7): standard library only; discovered by
  `python3 -m unittest discover -s tests`; no other test module is edited.

This module reads the develop skill document only. It asserts nothing about
review-phase.md: that the labels cited here resolve there is checked on the
integrated tree, not here.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVELOP_SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "develop" / "SKILL.md"

# --- Cited-block coordinates (IMPLEMENTATION.md SC1 / SC2 / SC3) ----------
REVIEW_PHASE_CITED_PATH = "references/review-phase.md"
PHASE_R5_TOKEN = "Phase R5"
GATE_ABORT_LABEL = "Spec-change gate abort (review-sourced rework)"
LEGACY_RECOVERY_LABEL = "Legacy review-failure recovery"

# --- Region boundaries ----------------------------------------------------
STEP_B_START = "## Step B: 自走ループ"
STEP_B_END = "### design ステップ分岐"
GATE_CALL_MARKER = "**spec-change 遷移のゲート呼び出し（バッチのみ）**"
STOP_REPORT_START = "## 停止時の報告（停止条件 2-4 のみ）"
STOP_REPORT_END = "## バッチ構造化結果"
STOP_REPORT_LAST_BULLET = "- YAML エラー: 内容と `git restore` 等のリカバリ案を報告"

# --- Non-restatement tokens (Design sections 1 and 2) ---------------------
GATE_CALL_FORBIDDEN_TOKENS = (
    "needs_rework",
    "review_rework_count",
    "pending",
    "failed",
    "decision: stop",
)
STOP_REPORT_FORBIDDEN_TOKENS = (
    "decision: stop",
    "needs_rework",
    "classification",
)

# --- Interactive-question budget (AC-6) -----------------------------------
INTERACTIVE_UNCHANGED_PHRASE = "interactive はこの改訂で変更しない"
QUESTION_TOOL_NAME = "AskUserQuestion"
QUESTION_TOOL_BASELINE_COUNT = 7

# --- Pre-change texts, verbatim (the AC-1 / AC-3 negative twins) ----------
PRE_CHANGE_GATE_CALL_PARAGRAPH = (
    "**spec-change 遷移のゲート呼び出し（バッチのみ）**: バッチ実行でこの\n"
    "spec-change 遷移の question の `gate_id` が特定され、\n"
    "`references/question-resolution.md` の routed arm がそれを Classification\n"
    "gate へ送った直後、上記の Specification-change transition が定める 5 つの\n"
    "step のいずれも実行する前に、その Classification gate を呼ぶ — これが\n"
    "バッチにおける唯一の呼び出し位置。ゲートの verdict が stop\n"
    "（inapplicable の場合を含む）なら、5 つの step は 1 つも実行せずその時点\n"
    "で run を停止し、理由を記録する。verdict が proceed のときだけ、5 つの\n"
    "step が続けて実行される。interactive はこの改訂で変更しない — ユーザーへ\n"
    "直接質問する既存の挙動のままであり、新しい interactive の質問は追加され\n"
    "ない。"
)

PRE_CHANGE_STOP_REPORT_SECTION = (
    "## 停止時の報告（停止条件 2-4 のみ）\n"
    "\n"
    "batch: 下記 3 件に加えて、停止条件 6、フェーズ内のゲート中断、Step A の\n"
    "feature 解決失敗、commit-docs.sh の 2 回目の exit 4 によるフェーズ中断、\n"
    "Step C 内の中断、そして implement / verify フェーズが定める終端停止\n"
    "（下記「バッチ構造化結果」が列挙する停止点のすべてを含む）は、いずれも\n"
    "`${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` の出力抑制規律が定める\n"
    "停止/中断の例外であり、対話時と同じ内容を全文報告する。この報告は、下記\n"
    "「バッチ構造化結果」が定める規則に従い、そのターンの最後の assistant\n"
    "メッセージより前のメッセージで出力する。停止の原因・影響範囲・リカバリ\n"
    "手順は、この報告に加えて、構造化結果の値の中にも全文で運ぶ —\n"
    "原因と影響範囲は `detail` に、リカバリ手順は `resume_conditions` に。\n"
    "この報告は追加であり、置き換えではない。\n"
    "\n"
    "- スタック: `{step} が {status} のままだよ。フェーズ出力を確認してね`\n"
    "- 中断: `{step} が {status} のため中断。再開するには /em-workflow:develop を実行してね`\n"
    "- YAML エラー: 内容と `git restore` 等のリカバリ案を報告\n"
    "\n"
)

# --- Protected stop-condition-3 texts (Design section 3, NFR1) ------------
# (name, start marker, end marker, anchors). Each region is sliced from the
# raw document by single-line markers; each anchor is compared with all
# whitespace removed on both sides, because Japanese lines hard-wrap
# without a space at the break.
PROTECTED_BLOCKS = (
    (
        "stop condition 3 (item 3 of the only-condition list)",
        "3. ある step の status が `failed` / `needs_update`",
        "4. workflow.yaml の YAML parse エラー",
        (
            "ある step の status が `failed` / `needs_update`（= ユーザー介入が必要。",
            "ただし、フェーズプロトコルがそのフェーズの自動再エントリのために設定した"
            " `needs_update` の間はこの条件では停止しない",
            "「**停止条件 3 との優先関係**」参照。`implement` step の `failed` は"
            " `failed_kind` により発火条件が絞られる",
            "「**batch: implement の failed_kind による自動再開**」参照）",
        ),
    ),
    (
        "停止条件 3 との優先関係 block",
        "**停止条件 3 との優先関係**:",
        GATE_CALL_MARKER,
        (
            "停止条件 3 は Step B がこれから実行する step を特定した時点で、"
            "その step の `failed` / `needs_update` status に対して 1 度評価される。",
            "該当する遷移は現時点で厳密に次の 3 つで、それぞれ所有ドキュメントを明記する:",
            "この列挙は、所有 SSOT 自身がフェーズの自動再エントリを明記している遷移"
            "だけが対象という構成上の理由でこの 3 つで網羅的であり、"
            "他の遷移はこの除外の対象外。",
        ),
    ),
    (
        "batch verify cap exception block",
        "**batch: verify の cap 到達に対する停止条件の例外**（FR7）:",
        "**batch: implement の failed_kind による自動再開**（FR6, FR7, FR8）:",
        (
            "次の条件が揃ったときにのみ適用される — batch モードであり、"
            "かつ verify が系譜 cap または hard cap の到達により `failed` であること。",
            "- 非適用: 上記以外の理由による `failed`（implement の失敗、review の失敗、"
            "cap 未到達の verify 失敗）には適用されない。interactive にも適用されない。",
            "同ブロックの本文・網羅性宣言を変更しない。",
        ),
    ),
    (
        "batch implement failed_kind block",
        "**batch: implement の failed_kind による自動再開**（FR6, FR7, FR8）:",
        "**Tier 削減表**",
        (
            "`implement` step の `status` が `failed` のとき、停止条件 3 が発火するのは"
            " `failed_kind` が要ユーザー判断の値を示す場合に限る。",
            "停止条件 3 のもう一方の発火条件（`needs_update`）、および `review` / `verify`"
            " step に対する挙動はこの block の対象外であり、一切変更しない",
        ),
    ),
)

# The enumeration inside the priority block: three top-level bullets lie
# between its opening sentence and its exhaustiveness sentence.
ENUMERATION_OPENING = "該当する遷移は現時点で厳密に次の 3 つで"
ENUMERATION_CLOSING = "この列挙は、所有 SSOT 自身がフェーズの自動再エントリを明記している遷移"
ENUMERATION_BULLET_COUNT = 3


# --- Helpers (names specific to this module) ------------------------------


def _wiring_read_skill_text():
    if not DEVELOP_SKILL_PATH.is_file():
        raise AssertionError(f"expected file to exist: {DEVELOP_SKILL_PATH}")
    return DEVELOP_SKILL_PATH.read_text(encoding="utf-8")


def _wiring_strip_ws(text):
    # All whitespace is removed (not collapsed): the document hard-wraps
    # Japanese prose without a space at the break point.
    return re.sub(r"\s+", "", text)


def _wiring_slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start + len(start_marker))
    return text[start:end]


def _wiring_step_b_region(text):
    return _wiring_slice(text, STEP_B_START, STEP_B_END)


def _wiring_gate_call_paragraph(text):
    """The paragraph from the gate-call marker to the next blank line inside
    Step B, as raw text (the bounds tests/test_gate_outcome_packet_lifecycle.py
    uses)."""
    region = _wiring_step_b_region(text)
    rest = region[region.index(GATE_CALL_MARKER) :]
    stop = rest.find("\n\n")
    return rest if stop == -1 else rest[:stop]


def _wiring_stop_report_section(text):
    return _wiring_slice(text, STOP_REPORT_START, STOP_REPORT_END)


def _wiring_block_containing(section, needle):
    """The blank-line-delimited block of `section` containing `needle`, or
    None when no block does."""
    for block in section.split("\n\n"):
        if needle in block:
            return block
    return None


def _wiring_cites_label(text, label):
    """Citation matcher (SC3 form): some single line of `text` names the
    cited document path, the `Phase R5` token and the label text."""
    return any(
        REVIEW_PHASE_CITED_PATH in line and PHASE_R5_TOKEN in line and label in line
        for line in text.splitlines()
    )


def _wiring_gate_paragraph_cites_gate_abort(paragraph):
    return _wiring_cites_label(paragraph, GATE_ABORT_LABEL)


def _wiring_gate_paragraph_defers_status_and_resume(paragraph):
    """Scope matcher: the paragraph says the review status written at this
    stop and the resume path are defined by the cited block and not restated
    here."""
    stripped = _wiring_strip_ws(paragraph)
    return (
        _wiring_gate_paragraph_cites_gate_abort(paragraph)
        and _wiring_strip_ws("review の status") in stripped
        and "再開" in stripped
        and _wiring_strip_ws("繰り返さない") in stripped
    )


def _wiring_restated_tokens(text, tokens):
    """Non-restatement matcher: the tokens of `tokens` that occur in `text`
    (case-insensitive), empty when none does."""
    lowered = text.lower()
    return [token for token in tokens if token.lower() in lowered]


def _wiring_stop_report_recovery_block(section):
    """The new recovery paragraph of the stop-report section: the plain
    (non-bullet) block that follows the three bullets and names the legacy
    recovery label. None when there is none."""
    block = _wiring_block_containing(section, LEGACY_RECOVERY_LABEL)
    if block is None or block.lstrip().startswith("- "):
        return None
    if STOP_REPORT_LAST_BULLET not in section:
        return None
    if section.index(block) < section.index(STOP_REPORT_LAST_BULLET):
        return None
    return block


def _wiring_stop_report_cites_legacy_recovery(section):
    block = _wiring_stop_report_recovery_block(section)
    return block is not None and _wiring_cites_label(block, LEGACY_RECOVERY_LABEL)


def _wiring_stop_report_carries_recovery_in_full(section):
    """Carriage matcher: the recovery paragraph ties a stop-condition-3 stop
    on the review step's `failed` to the report and to `resume_conditions`,
    and states the location AND the content are carried (a bare pointer does
    not satisfy it)."""
    block = _wiring_stop_report_recovery_block(section)
    if block is None:
        return False
    stripped = _wiring_strip_ws(block)
    return (
        _wiring_strip_ws("停止条件 3") in stripped
        and _wiring_strip_ws("`review` step の `failed`") in stripped
        and "報告" in stripped
        and "`resume_conditions`" in block
        and "所在" in stripped
        and "内容" in stripped
    )


def _wiring_missing_anchors(region, anchors):
    stripped = _wiring_strip_ws(region)
    return [anchor for anchor in anchors if _wiring_strip_ws(anchor) not in stripped]


def _wiring_enumeration_region(text):
    return _wiring_slice(text, ENUMERATION_OPENING, ENUMERATION_CLOSING)


def _wiring_top_level_bullet_count(region):
    return sum(1 for line in region.splitlines() if line.startswith("- "))


def _wiring_enumeration_has_three_bullets(region):
    return _wiring_top_level_bullet_count(region) == ENUMERATION_BULLET_COUNT


def _wiring_question_tool_count(text):
    return text.count(QUESTION_TOOL_NAME)


# --- Synthetic negative-twin texts ----------------------------------------

SYNTH_CITATION_SPLIT_ACROSS_LINES = (
    PRE_CHANGE_GATE_CALL_PARAGRAPH
    + "\nこの停止で review の status に書く値と再開経路は、"
    + "`references/review-phase.md` の Phase R5 の\n"
    + "Spec-change gate abort (review-sourced rework) が定義し、ここでは繰り返さない。"
)

SYNTH_PARAGRAPH_WITH_BARE_CITATION = (
    PRE_CHANGE_GATE_CALL_PARAGRAPH
    + "\n`references/review-phase.md` の Phase R5 の"
    + " Spec-change gate abort (review-sourced rework) を参照。"
)

SYNTH_PARAGRAPH_RESTATING_A_VALUE = (
    PRE_CHANGE_GATE_CALL_PARAGRAPH
    + "\nこの停止で review の status に書く値と再開経路は、"
    + "`references/review-phase.md` の Phase R5 の"
    + " Spec-change gate abort (review-sourced rework) が定義し、"
    + "ここでは繰り返さない。なお review の status は `pending` に書く。"
)

SYNTH_SECTION_WITH_BARE_POINTER = (
    PRE_CHANGE_STOP_REPORT_SECTION
    + "停止条件 3 が `review` step の `failed` で発火したときは、"
    + "`references/review-phase.md` の Phase R5 の"
    + " Legacy review-failure recovery を見よ。\n\n"
)

SYNTH_SECTION_CITING_THE_OTHER_LABEL = (
    PRE_CHANGE_STOP_REPORT_SECTION
    + "停止条件 3 が `review` step の `failed` で発火したときは、報告と"
    + " `resume_conditions` が `references/review-phase.md` の Phase R5 の"
    + " Spec-change gate abort (review-sourced rework) の所在と内容を運ぶ。\n\n"
)

SYNTH_SECTION_CITATION_SPLIT_ACROSS_LINES = (
    PRE_CHANGE_STOP_REPORT_SECTION
    + "停止条件 3 が `review` step の `failed` で発火したときは、報告と"
    + " `resume_conditions` が所在と内容を運ぶ。\n"
    + "`references/review-phase.md` の Phase R5 の\n"
    + "Legacy review-failure recovery ブロックが定める。\n\n"
)

SYNTH_SECTION_RESTATING_APPLICABILITY = (
    PRE_CHANGE_STOP_REPORT_SECTION
    + "停止条件 3 が `review` step の `failed` で発火したときは、報告と"
    + " `resume_conditions` が所在と内容を運ぶ。"
    + "`references/review-phase.md` の Phase R5 の"
    + " Legacy review-failure recovery は、review の status が `needs_rework`"
    + " のまま残った場合にだけ適用される。\n\n"
)

SYNTH_ENUMERATION_THREE_BULLETS = (
    "該当する遷移は現時点で厳密に次の 3 つで、\n"
    "それぞれ所有ドキュメントを明記する:\n"
    "- first transition —\n"
    "  continuation\n"
    "- second transition —\n"
    "  continuation\n"
    "- third transition —\n"
    "  continuation\n"
    "\n"
)

SYNTH_ENUMERATION_FOUR_BULLETS = (
    SYNTH_ENUMERATION_THREE_BULLETS + "- fourth transition —\n  continuation\n\n"
)

SYNTH_ENUMERATION_TWO_BULLETS = (
    "該当する遷移は現時点で厳密に次の 3 つで、\n"
    "- first transition\n"
    "- second transition\n"
    "\n"
)


class TestGateCallParagraphCitesGateAbortBlock(unittest.TestCase):
    """AC-1, AC-2: Step B's spec-change gate-call paragraph cites the
    gate-abort block and restates none of its values."""

    @classmethod
    def setUpClass(cls):
        cls.text = _wiring_read_skill_text()
        cls.step_b = _wiring_step_b_region(cls.text)
        cls.paragraph = _wiring_gate_call_paragraph(cls.text)

    # -- non-vacuity of the sliced regions --

    def test_step_b_region_is_non_vacuous(self):
        self.assertTrue(self.step_b.startswith(STEP_B_START))
        self.assertIn(GATE_CALL_MARKER, self.step_b)
        self.assertNotIn(STEP_B_END, self.step_b)
        self.assertGreater(len(self.step_b), 2000)

    def test_gate_call_paragraph_is_non_vacuous(self):
        self.assertTrue(self.paragraph.startswith(GATE_CALL_MARKER))
        self.assertNotIn("\n\n", self.paragraph)
        self.assertIn("5 つの step", self.paragraph)
        self.assertGreater(len(self.paragraph), len(GATE_CALL_MARKER))

    def test_pre_change_constant_is_the_gate_call_paragraph_shape(self):
        # The twin constant must stay a faithful copy of the pre-change
        # paragraph: same marker, bounded by no blank line, and still
        # carrying the phrase the interactive matcher looks for.
        self.assertTrue(PRE_CHANGE_GATE_CALL_PARAGRAPH.startswith(GATE_CALL_MARKER))
        self.assertNotIn("\n\n", PRE_CHANGE_GATE_CALL_PARAGRAPH)
        self.assertIn(
            _wiring_strip_ws(INTERACTIVE_UNCHANGED_PHRASE),
            _wiring_strip_ws(PRE_CHANGE_GATE_CALL_PARAGRAPH),
        )
        self.assertTrue(_wiring_strip_ws(self.paragraph).startswith(
            _wiring_strip_ws(PRE_CHANGE_GATE_CALL_PARAGRAPH)
        ))

    # -- AC-1 --

    def test_ac1_paragraph_cites_gate_abort_block(self):
        self.assertTrue(
            _wiring_gate_paragraph_cites_gate_abort(self.paragraph),
            "expected one line of the gate-call paragraph to name "
            f"{REVIEW_PHASE_CITED_PATH}, {PHASE_R5_TOKEN} and {GATE_ABORT_LABEL!r}",
        )

    def test_ac1_paragraph_defers_status_and_resume_path(self):
        self.assertTrue(
            _wiring_gate_paragraph_defers_status_and_resume(self.paragraph),
            "expected the paragraph to say the review status written at this "
            "stop and the resume path are defined by the cited block and not "
            "restated here",
        )

    def test_ac1_negative_twin_pre_change_paragraph_is_rejected(self):
        self.assertFalse(
            _wiring_gate_paragraph_cites_gate_abort(PRE_CHANGE_GATE_CALL_PARAGRAPH)
        )
        self.assertFalse(
            _wiring_gate_paragraph_defers_status_and_resume(
                PRE_CHANGE_GATE_CALL_PARAGRAPH
            )
        )

    def test_ac1_negative_twin_citation_split_across_lines_is_rejected(self):
        self.assertFalse(
            _wiring_gate_paragraph_cites_gate_abort(SYNTH_CITATION_SPLIT_ACROSS_LINES)
        )

    def test_ac1_negative_twin_bare_citation_lacks_the_scope_statement(self):
        # The citation matcher passes, the scope matcher rejects: a pointer
        # that does not say what it defines is not the SC1 sentence.
        self.assertTrue(
            _wiring_gate_paragraph_cites_gate_abort(SYNTH_PARAGRAPH_WITH_BARE_CITATION)
        )
        self.assertFalse(
            _wiring_gate_paragraph_defers_status_and_resume(
                SYNTH_PARAGRAPH_WITH_BARE_CITATION
            )
        )

    def test_ac1_negative_twin_wrong_label_is_rejected(self):
        wrong = self.paragraph.replace(GATE_ABORT_LABEL, LEGACY_RECOVERY_LABEL)
        self.assertNotEqual(wrong, self.paragraph)
        self.assertFalse(_wiring_gate_paragraph_cites_gate_abort(wrong))

    # -- AC-2 --

    def test_ac2_paragraph_restates_no_cited_value(self):
        self.assertEqual(
            _wiring_restated_tokens(self.paragraph, GATE_CALL_FORBIDDEN_TOKENS), []
        )

    def test_ac2_pre_change_paragraph_restates_no_cited_value_either(self):
        # Establishes the matcher's baseline: the unedited paragraph passes.
        self.assertEqual(
            _wiring_restated_tokens(
                PRE_CHANGE_GATE_CALL_PARAGRAPH, GATE_CALL_FORBIDDEN_TOKENS
            ),
            [],
        )

    def test_ac2_negative_twin_restated_value_is_flagged(self):
        self.assertEqual(
            _wiring_restated_tokens(
                SYNTH_PARAGRAPH_RESTATING_A_VALUE, GATE_CALL_FORBIDDEN_TOKENS
            ),
            ["pending"],
        )

    def test_ac2_negative_twin_each_forbidden_token_is_flagged(self):
        for token in GATE_CALL_FORBIDDEN_TOKENS:
            with self.subTest(token=token):
                synthetic = PRE_CHANGE_GATE_CALL_PARAGRAPH + f"\n（{token}）"
                self.assertEqual(
                    _wiring_restated_tokens(synthetic, GATE_CALL_FORBIDDEN_TOKENS),
                    [token],
                )


class TestStopReportSectionCitesLegacyRecovery(unittest.TestCase):
    """AC-3, AC-4: the 停止時の報告 section carries the legacy recovery
    procedure for a stop-condition-3 stop on the review step's `failed`,
    cited and not restated."""

    @classmethod
    def setUpClass(cls):
        cls.text = _wiring_read_skill_text()
        cls.section = _wiring_stop_report_section(cls.text)

    # -- non-vacuity of the sliced region --

    def test_stop_report_section_is_non_vacuous(self):
        self.assertTrue(self.section.startswith(STOP_REPORT_START))
        self.assertNotIn(STOP_REPORT_END, self.section)
        self.assertIn(STOP_REPORT_LAST_BULLET, self.section)
        self.assertIn("- スタック:", self.section)
        self.assertIn("- 中断:", self.section)

    def test_pre_change_constant_is_the_stop_report_section_shape(self):
        self.assertTrue(PRE_CHANGE_STOP_REPORT_SECTION.startswith(STOP_REPORT_START))
        self.assertIn(STOP_REPORT_LAST_BULLET, PRE_CHANGE_STOP_REPORT_SECTION)
        self.assertTrue(_wiring_strip_ws(self.section).startswith(
            _wiring_strip_ws(PRE_CHANGE_STOP_REPORT_SECTION)
        ))

    # -- AC-3 --

    def test_ac3_section_cites_legacy_recovery_block(self):
        self.assertTrue(
            _wiring_stop_report_cites_legacy_recovery(self.section),
            "expected one line of a paragraph after the three bullets to name "
            f"{REVIEW_PHASE_CITED_PATH}, {PHASE_R5_TOKEN} and {LEGACY_RECOVERY_LABEL!r}",
        )

    def test_ac3_section_carries_recovery_location_and_content(self):
        self.assertTrue(
            _wiring_stop_report_carries_recovery_in_full(self.section),
            "expected the paragraph to tie a stop-condition-3 stop on the "
            "review step's `failed` to the report and to `resume_conditions`, "
            "carrying the location together with the content",
        )

    def test_ac3_recovery_paragraph_follows_the_three_bullets(self):
        block = _wiring_stop_report_recovery_block(self.section)
        self.assertIsNotNone(block)
        self.assertGreater(
            self.section.index(block), self.section.index(STOP_REPORT_LAST_BULLET)
        )
        self.assertFalse(block.lstrip().startswith("- "))

    def test_ac3_no_level_two_heading_inside_the_section(self):
        self.assertEqual(
            [line for line in self.section.splitlines() if line.startswith("## ")],
            [STOP_REPORT_START],
        )

    def test_ac3_negative_twin_pre_change_section_is_rejected(self):
        self.assertFalse(
            _wiring_stop_report_cites_legacy_recovery(PRE_CHANGE_STOP_REPORT_SECTION)
        )
        self.assertFalse(
            _wiring_stop_report_carries_recovery_in_full(PRE_CHANGE_STOP_REPORT_SECTION)
        )

    def test_ac3_negative_twin_bare_pointer_lacks_content_carriage(self):
        # The citation matcher passes, the carriage matcher rejects: naming
        # the location without carrying the content does not satisfy the
        # in-full rule.
        self.assertTrue(
            _wiring_stop_report_cites_legacy_recovery(SYNTH_SECTION_WITH_BARE_POINTER)
        )
        self.assertFalse(
            _wiring_stop_report_carries_recovery_in_full(SYNTH_SECTION_WITH_BARE_POINTER)
        )

    def test_ac3_negative_twin_other_label_is_rejected(self):
        self.assertFalse(
            _wiring_stop_report_cites_legacy_recovery(SYNTH_SECTION_CITING_THE_OTHER_LABEL)
        )
        self.assertFalse(
            _wiring_stop_report_carries_recovery_in_full(SYNTH_SECTION_CITING_THE_OTHER_LABEL)
        )

    def test_ac3_negative_twin_citation_split_across_lines_is_rejected(self):
        self.assertFalse(
            _wiring_stop_report_cites_legacy_recovery(
                SYNTH_SECTION_CITATION_SPLIT_ACROSS_LINES
            )
        )

    def test_ac3_negative_twin_label_in_a_bullet_is_not_the_paragraph(self):
        # A bullet naming the label does not count as the new paragraph.
        bullet_only = (
            PRE_CHANGE_STOP_REPORT_SECTION.rstrip("\n")
            + "\n- `references/review-phase.md` の Phase R5 の"
            + f" {LEGACY_RECOVERY_LABEL}\n\n"
        )
        self.assertFalse(_wiring_stop_report_cites_legacy_recovery(bullet_only))

    # -- AC-4 --

    def test_ac4_section_restates_no_cited_value(self):
        self.assertEqual(
            _wiring_restated_tokens(self.section, STOP_REPORT_FORBIDDEN_TOKENS), []
        )

    def test_ac4_pre_change_section_restates_no_cited_value_either(self):
        self.assertEqual(
            _wiring_restated_tokens(
                PRE_CHANGE_STOP_REPORT_SECTION, STOP_REPORT_FORBIDDEN_TOKENS
            ),
            [],
        )

    def test_ac4_negative_twin_restated_applicability_is_flagged(self):
        self.assertEqual(
            _wiring_restated_tokens(
                SYNTH_SECTION_RESTATING_APPLICABILITY, STOP_REPORT_FORBIDDEN_TOKENS
            ),
            ["needs_rework"],
        )

    def test_ac4_negative_twin_each_forbidden_token_is_flagged(self):
        for token in STOP_REPORT_FORBIDDEN_TOKENS:
            with self.subTest(token=token):
                synthetic = PRE_CHANGE_STOP_REPORT_SECTION + f"（{token}）\n\n"
                self.assertEqual(
                    _wiring_restated_tokens(synthetic, STOP_REPORT_FORBIDDEN_TOKENS),
                    [token],
                )


class TestStopConditionThreeTextsUnchanged(unittest.TestCase):
    """AC-5: the stop-condition-3 texts NFR1 protects are untouched, and the
    priority block's enumeration still holds exactly three bullets."""

    @classmethod
    def setUpClass(cls):
        cls.text = _wiring_read_skill_text()
        cls.regions = [
            (name, _wiring_slice(cls.text, start, end), anchors)
            for name, start, end, anchors in PROTECTED_BLOCKS
        ]
        cls.enumeration = _wiring_enumeration_region(cls.text)

    # -- non-vacuity of the sliced regions --

    def test_every_protected_region_is_non_vacuous(self):
        self.assertEqual(len(self.regions), len(PROTECTED_BLOCKS))
        for (name, region, anchors), block in zip(self.regions, PROTECTED_BLOCKS):
            with self.subTest(region=name):
                self.assertTrue(region.startswith(block[1]))
                self.assertGreater(len(region.strip()), len(block[1]))
                self.assertGreaterEqual(len(anchors), 2)

    def test_enumeration_region_is_non_vacuous(self):
        self.assertTrue(self.enumeration.startswith(ENUMERATION_OPENING))
        self.assertNotIn(ENUMERATION_CLOSING, self.enumeration)
        self.assertGreater(_wiring_top_level_bullet_count(self.enumeration), 0)

    # -- anchors --

    def test_every_protected_anchor_is_present(self):
        for name, region, anchors in self.regions:
            with self.subTest(region=name):
                self.assertEqual(_wiring_missing_anchors(region, anchors), [])

    def test_negative_twin_a_dropped_anchor_is_reported_missing(self):
        for name, region, anchors in self.regions:
            for anchor in anchors:
                with self.subTest(region=name, anchor=anchor[:24]):
                    stripped_anchor = _wiring_strip_ws(anchor)
                    mutilated = _wiring_strip_ws(region).replace(stripped_anchor, "")
                    self.assertNotEqual(mutilated, _wiring_strip_ws(region))
                    self.assertEqual(
                        _wiring_missing_anchors(mutilated, [anchor]), [anchor]
                    )

    def test_negative_twin_a_reworded_anchor_is_reported_missing(self):
        name, region, anchors = self.regions[2]
        reworded = region.replace("適用されない。interactive にも", "適用される。interactive にも")
        self.assertNotEqual(reworded, region)
        self.assertEqual(
            _wiring_missing_anchors(reworded, anchors), [anchors[1]], name
        )

    # -- enumeration bullet count --

    def test_enumeration_holds_exactly_three_top_level_bullets(self):
        self.assertTrue(
            _wiring_enumeration_has_three_bullets(self.enumeration),
            "expected exactly three top-level bullets between the "
            "enumeration's opening sentence and its exhaustiveness sentence, "
            f"found {_wiring_top_level_bullet_count(self.enumeration)}",
        )

    def test_negative_twin_four_bullet_enumeration_is_rejected(self):
        self.assertTrue(
            _wiring_enumeration_has_three_bullets(SYNTH_ENUMERATION_THREE_BULLETS)
        )
        self.assertFalse(
            _wiring_enumeration_has_three_bullets(SYNTH_ENUMERATION_FOUR_BULLETS)
        )

    def test_negative_twin_two_bullet_enumeration_is_rejected(self):
        self.assertFalse(
            _wiring_enumeration_has_three_bullets(SYNTH_ENUMERATION_TWO_BULLETS)
        )

    def test_continuation_lines_are_not_counted_as_bullets(self):
        self.assertEqual(
            _wiring_top_level_bullet_count(SYNTH_ENUMERATION_THREE_BULLETS), 3
        )


class TestInteractiveBehaviourUnchanged(unittest.TestCase):
    """AC-6: the additions add no interactive behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.text = _wiring_read_skill_text()
        cls.paragraph = _wiring_gate_call_paragraph(cls.text)

    def test_interactive_unchanged_statement_stays_in_gate_call_paragraph(self):
        self.assertIn(
            _wiring_strip_ws(INTERACTIVE_UNCHANGED_PHRASE),
            _wiring_strip_ws(self.paragraph),
        )

    def test_negative_twin_paragraph_without_the_statement_is_rejected(self):
        without = self.paragraph.replace(INTERACTIVE_UNCHANGED_PHRASE, "")
        self.assertNotEqual(without, self.paragraph)
        self.assertNotIn(
            _wiring_strip_ws(INTERACTIVE_UNCHANGED_PHRASE),
            _wiring_strip_ws(without),
        )

    def test_question_tool_name_keeps_its_baseline_count(self):
        self.assertEqual(
            _wiring_question_tool_count(self.text), QUESTION_TOOL_BASELINE_COUNT
        )

    def test_negative_twin_an_added_occurrence_changes_the_count(self):
        grown = self.text + f"\n{QUESTION_TOOL_NAME}\n"
        self.assertEqual(
            _wiring_question_tool_count(grown), QUESTION_TOOL_BASELINE_COUNT + 1
        )
        self.assertNotEqual(
            _wiring_question_tool_count(grown), QUESTION_TOOL_BASELINE_COUNT
        )

    def test_question_tool_count_matcher_is_non_vacuous(self):
        self.assertGreater(QUESTION_TOOL_BASELINE_COUNT, 0)
        self.assertGreater(_wiring_question_tool_count(self.text), 0)


if __name__ == "__main__":
    unittest.main()
