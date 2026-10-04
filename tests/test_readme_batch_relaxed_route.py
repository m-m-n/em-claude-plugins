"""Tests for task0002 (codex-fallback-review-residuals): the README's
`--batch` bullet states how security, license and irreversible-operation
questions are handled in each mode and defers the conditions to
`em-workflow/references/question-resolution.md`, and the README agent table
lists `opus-escalation`.

Covers task0002 Acceptance Criteria
(feature-docs/codex-fallback-review-residuals/tasks/task0002.md):

- AC-1: README no longer contains the old fail-closed clause ("仕様変更・
  セキュリティ・ライセンス・不可逆判断のゲートは未収載なら安全側で中断する
  （fail-closed）"), and the absence matcher is proven to catch a forged
  bullet that carries it.
- AC-2: the `--batch` bullet states that, for security, license and
  irreversible-operation questions, interactive mode aborts while batch mode
  takes the relaxed route without aborting, naming Codex 相談, Opus
  escalation and 最小副作用 in that order.
- AC-3: the bullet cites `references/question-resolution.md` together with
  "The batch relaxation" and "The surviving aborts"; one sentence (delimited
  by 。) names the surviving aborts and fail-closed and states that they are
  the only fail-closed classification stops left in batch; the bullet
  restates none of the trigger-condition literals.
- AC-4: exactly one agent-table row has `opus-escalation` as its first cell;
  it lies in the same contiguous block of table lines as the table header
  and the `review-evaluator` row, directly after the latter; its last cell
  is "—"; every pre-existing row is still present exactly once.
- AC-5: this module asserts AC-1..AC-4 with the standard library only, and
  every negative assertion (absence of the old clause, non-restatement of
  trigger literals, contiguity of the row, forbidden role wording) has a
  non-vacuity proof over a forged sample. The full-suite run
  (`python3 -m unittest discover -s tests`) exiting 0 is a CLI-level
  property this module cannot assert about itself without recursion; it is
  verified by actually running it.

Per Test Notes: the bullet already cites `references/question-resolution.md`
today (for the unlisted-gate fallback), so the path alone would pass before
the change -- AC-3 pins the two section names alongside it. The bullet is
located by its unchanged opening text; the table block is located from its
header row down to the first line that is not a table line. Every matcher
is a plain function over text, so the negative proofs feed it forged
samples built in memory -- nothing here reads or writes README.md as a
fixture. This module reads README.md alone: the agent definition, its
contract and question-resolution.md are out of its reach.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "em-workflow" / "README.md"

BATCH_BULLET_PREFIX = "- `--batch` で無人実行モードになる"

# The clause this task retired, as it read before the change (tail of the
# unlisted-gate sentence).
OLD_FAIL_CLOSED_CLAUSE = (
    "仕様変更・セキュリティ・ライセンス・不可逆判断のゲートは未収載なら"
    "安全側で中断する（fail-closed）"
)

QUESTION_RESOLUTION_PATH = "references/question-resolution.md"
SECTION_BATCH_RELAXATION = "The batch relaxation"
SECTION_SURVIVING_ABORTS = "The surviving aborts"

# Trigger-condition literals owned by question-resolution.md; the README
# defers to it and must not restate any of them.
TRIGGER_LITERALS = (
    "category: security",
    "category: license",
    "reversible: false",
    "rework.spec-change",
)

AGENT_TABLE_HEADER = ["エージェント", "役割", "静的プリロード"]
NEW_AGENT = "opus-escalation"
PREDECESSOR_AGENT = "review-evaluator"
EMPTY_PRELOAD_CELL = "—"

# Every agent row the README carried before this task. The gitignore-guard
# and git-setup-guard rows sit after the paragraph that interrupts the table
# (pre-existing, out of scope), so presence is asserted for them, not
# membership of the contiguous block.
PRE_EXISTING_AGENT_ROWS = (
    "requirements-analyst",
    "spec-writer",
    "designer",
    "implementation-planner",
    "rework-planner",
    "implementer",
    "reviewer",
    "codex-reviewer",
    "review-editor",
    "review-evaluator",
    "gitignore-guard",
    "git-setup-guard",
)

# Wording that described the pre-llm-led review composition; the new row's
# role text must not use any of it (re-declared here from
# tests/test_llm_led_review_user_docs.py -- no module imports another).
FORBIDDEN_ROLE_PHRASES = (
    "クロスモデル二重化",
    "クロスモデル検証は強度の軸として分離",
    "で二重実行される",
    "クロスバリデーション用",
    "クロスバリデーションは全滅してクリーンにスキップされる",
    "全観点がチェーン末尾の Codex エントリに落ちる",
    "cross-model agreement",
    "agreement scoring",
)

ROLE_MENTIONS = ("Opus", "オーケストレーター")


# ---------------------------------------------------------------------------
# Matchers: plain functions over text, so forged samples can be fed to them.
# ---------------------------------------------------------------------------


def _flat(text):
    """Collapse every whitespace run to one space, so Markdown re-wrapping
    does not break a prose pin."""
    return re.sub(r"\s+", " ", text)


def _squash(text):
    """Drop all whitespace -- for Japanese runs that a re-wrap could split at
    an arbitrary point."""
    return re.sub(r"\s+", "", text)


def find_batch_bullet(text):
    """The single line beginning with the bullet's unchanged opening text.
    Raises when it is absent or appears more than once (the bullet stays one
    line)."""
    hits = [
        line for line in text.splitlines() if line.strip().startswith(BATCH_BULLET_PREFIX)
    ]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one line starting with {BATCH_BULLET_PREFIX!r}, "
            f"found {len(hits)}"
        )
    return hits[0]


def sentences(bullet):
    """Split on the Japanese full stop. A fragment is a sentence body without
    its trailing 。"""
    return [part for part in _flat(bullet).split("。") if part.strip()]


def carries_old_clause(text):
    """AC-1 absence matcher: True when the retired clause is present, in any
    whitespace wrapping."""
    return _squash(OLD_FAIL_CLOSED_CLAUSE) in _squash(text)


def relaxed_route_problems(bullet):
    """AC-2: reasons the bullet does not state the interactive-aborts /
    batch-relaxed split. Empty list means it does."""
    problems = []
    candidates = [
        s
        for s in sentences(bullet)
        if all(term in s for term in ("セキュリティ", "ライセンス", "不可逆"))
    ]
    if not candidates:
        return ["no sentence names security, license and irreversible-operation questions"]
    sentence = candidates[0]
    split = re.search(r"対話[^。]*?中断[^。]*?batch[^。]*?中断(?:せず|しない)", sentence)
    if not split:
        problems.append(
            "no interactive-aborts / batch-does-not-abort split in the sentence"
        )
    batch_at = sentence.find("batch")
    if batch_at < 0:
        problems.append("the sentence never names batch")
        return problems
    order = []
    for term in ("Codex 相談", "Opus escalation", "最小副作用"):
        at = sentence.find(term, batch_at)
        if at < 0:
            problems.append(f"{term!r} missing from the batch half of the sentence")
        order.append(at)
    if all(at >= 0 for at in order) and order != sorted(order):
        problems.append("Codex 相談 / Opus escalation / 最小副作用 are not in that order")
    return problems


def citation_problems(bullet):
    """AC-3 (citation half): the path plus both section names."""
    flat = _flat(bullet)
    problems = []
    for needle in (QUESTION_RESOLUTION_PATH, SECTION_BATCH_RELAXATION, SECTION_SURVIVING_ABORTS):
        if needle not in flat:
            problems.append(f"bullet does not cite {needle!r}")
    return problems


def only_surviving_stops_sentence_present(bullet):
    """AC-3 (sentence half): one 。-delimited sentence names the surviving
    aborts and fail-closed and states they are the only fail-closed
    classification stops left in batch."""
    for s in sentences(bullet):
        if (
            SECTION_SURVIVING_ABORTS in s
            and "fail-closed" in s
            and "batch" in s
            and "分類" in s
            and re.search(r"だけ|のみ", s)
        ):
            return True
    return False


def restated_trigger_literals(bullet):
    """AC-3 (non-restatement): the trigger literals found in the bullet."""
    flat = _flat(bullet)
    return [literal for literal in TRIGGER_LITERALS if literal in flat]


def _is_table_line(line):
    return line.strip().startswith("|")


def _cells(line):
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") else inner
    return [cell.strip() for cell in inner.split("|")]


def agent_table_block(text):
    """The lines of the agent table: from its header row down to the first
    line that is not a table line. Raises when the header is absent."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if _is_table_line(line) and _cells(line) == AGENT_TABLE_HEADER:
            block = []
            for member in lines[index:]:
                if not _is_table_line(member):
                    break
                block.append(member)
            return block
    raise AssertionError(f"no table header row {AGENT_TABLE_HEADER!r}")


def _rows_by_first_cell(text, name):
    return [
        line for line in text.splitlines() if _is_table_line(line) and _cells(line)[0] == name
    ]


def agent_row_problems(text):
    """AC-4: reasons the README agent table does not carry the single
    `opus-escalation` row where the design places it. Empty means it does."""
    problems = []
    rows = _rows_by_first_cell(text, NEW_AGENT)
    if len(rows) != 1:
        problems.append(f"expected exactly one {NEW_AGENT!r} row, found {len(rows)}")
        return problems
    row = rows[0]
    block = agent_table_block(text)
    if row not in block:
        problems.append(
            f"the {NEW_AGENT!r} row is outside the contiguous block of the agent table"
        )
    else:
        predecessors = [
            i for i, line in enumerate(block) if _cells(line)[0] == PREDECESSOR_AGENT
        ]
        if len(predecessors) != 1:
            problems.append(
                f"the agent table block does not carry exactly one {PREDECESSOR_AGENT!r} row"
            )
        elif block.index(row) != predecessors[0] + 1:
            problems.append(
                f"the {NEW_AGENT!r} row does not directly follow the {PREDECESSOR_AGENT!r} row"
            )
    cells = _cells(row)
    if len(cells) != len(AGENT_TABLE_HEADER):
        problems.append(
            f"the {NEW_AGENT!r} row has {len(cells)} cells, header has {len(AGENT_TABLE_HEADER)}"
        )
    elif cells[-1] != EMPTY_PRELOAD_CELL:
        problems.append(f"the last cell is {cells[-1]!r}, not {EMPTY_PRELOAD_CELL!r}")
    return problems


def pre_existing_row_problems(text):
    problems = []
    for name in PRE_EXISTING_AGENT_ROWS:
        count = len(_rows_by_first_cell(text, name))
        if count != 1:
            problems.append(f"pre-existing row {name!r} appears {count} times, expected 1")
    return problems


def role_cell_problems(text):
    """The new row's role text: states the Opus subagent / orchestrator-
    decides role and uses none of the forbidden review-composition phrases."""
    rows = _rows_by_first_cell(text, NEW_AGENT)
    if len(rows) != 1:
        return [f"expected exactly one {NEW_AGENT!r} row, found {len(rows)}"]
    cells = _cells(rows[0])
    if len(cells) < 2:
        return [f"the {NEW_AGENT!r} row has no role cell"]
    role = cells[1]
    problems = []
    for needle in ROLE_MENTIONS:
        if needle not in role:
            problems.append(f"role text does not mention {needle!r}")
    for phrase in FORBIDDEN_ROLE_PHRASES:
        if phrase in role:
            problems.append(f"role text uses forbidden phrase {phrase!r}")
    return problems


# ---------------------------------------------------------------------------
# Forged samples. GOOD_* are self-contained synthetic samples that satisfy
# every matcher, so each negative proof is known to fail for the reason it
# claims rather than because its base sample was already invalid.
# ---------------------------------------------------------------------------

GOOD_BULLET = (
    "- `--batch` で無人実行モードになる: 全ての AskUserQuestion ゲートを既定値へ置き換える。"
    "policy に無い `gate_id` は `references/question-resolution.md` の未収載ゲート fallback に従う。"
    "セキュリティ・ライセンス・不可逆操作の質問は、対話では中断し、`--batch` では中断せず"
    "緩和ルート（Codex 相談 → Opus escalation → 最小副作用の選択肢）で解決する。"
    "その条件は `references/question-resolution.md` の The batch relaxation と "
    "The surviving aborts が定める。"
    "batch で残る fail-closed の分類停止は The surviving aborts が列挙するものだけである。"
    "失敗時は停止して報告する。"
)

GOOD_TABLE_README = """\
# README

### エージェント

| エージェント | 役割 | 静的プリロード |
|-------------|------|---------------|
| requirements-analyst | 調査 | — |
| spec-writer | 執筆 | — |
| designer | デザイン | — |
| implementation-planner | 計画 | plan-writing |
| rework-planner | 追加計画 | — |
| implementer | 実装 | worktree-task-workflow, tdd-testing |
| reviewer | 汎用 Claude レビュアー | — |
| codex-reviewer | primary reviewer | codex-prompting |
| review-editor | auto-fix | — |
| review-evaluator | Opus 評価 | — |
| opus-escalation | 緩和ルートの Opus サブエージェント（決定はオーケストレーター） | — |

別段落。
| gitignore-guard | ignore 確認 | — |
| git-setup-guard | gitleaks 確認 | — |
"""


class _Forge:
    @staticmethod
    def bullet_with_old_clause():
        return GOOD_BULLET.replace(
            "失敗時は停止して報告する。",
            OLD_FAIL_CLOSED_CLAUSE + "。失敗時は停止して報告する。",
        )

    @staticmethod
    def readme_with_old_clause_rewrapped():
        # The same clause, but wrapped across lines the way an editor might.
        wrapped = OLD_FAIL_CLOSED_CLAUSE.replace("ゲートは", "ゲートは\n")
        return GOOD_TABLE_README + "\n" + wrapped + "\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOldClauseAbsent(unittest.TestCase):
    """AC-1: the old fail-closed clause is gone from the README, and the
    absence matcher is proven able to see it."""

    @classmethod
    def setUpClass(cls):
        cls.text = README_PATH.read_text(encoding="utf-8")

    def test_readme_no_longer_carries_the_old_clause(self):
        self.assertFalse(
            carries_old_clause(self.text),
            "the README still carries the retired fail-closed clause",
        )

    def test_matcher_accepts_the_clean_synthetic_bullet(self):
        # Non-vacuity base: the synthetic sample used for the forgeries below
        # is itself free of the old clause.
        self.assertFalse(carries_old_clause(GOOD_BULLET))

    def test_matcher_catches_a_forged_bullet_carrying_the_old_clause(self):
        self.assertTrue(carries_old_clause(_Forge.bullet_with_old_clause()))

    def test_matcher_catches_the_old_clause_rewrapped_across_lines(self):
        self.assertTrue(carries_old_clause(_Forge.readme_with_old_clause_rewrapped()))

    def test_bullet_locator_fails_loudly_when_the_bullet_is_absent(self):
        with self.assertRaises(AssertionError):
            find_batch_bullet("# README\n\n- some other bullet\n")


class TestBatchBulletRelaxedRoute(unittest.TestCase):
    """AC-2: the `--batch` bullet states the interactive-aborts /
    batch-relaxed split, naming the relaxed route's three steps in order."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = find_batch_bullet(README_PATH.read_text(encoding="utf-8"))

    def test_bullet_states_interactive_aborts_and_batch_takes_relaxed_route(self):
        self.assertEqual(relaxed_route_problems(self.bullet), [])

    def test_matcher_accepts_the_synthetic_good_bullet(self):
        self.assertEqual(relaxed_route_problems(GOOD_BULLET), [])

    def test_matcher_rejects_a_bullet_where_batch_still_aborts(self):
        forged = GOOD_BULLET.replace("`--batch` では中断せず", "`--batch` でも中断し")
        self.assertNotEqual(relaxed_route_problems(forged), [])

    def test_matcher_rejects_a_bullet_with_the_route_steps_out_of_order(self):
        forged = GOOD_BULLET.replace(
            "Codex 相談 → Opus escalation → 最小副作用の選択肢",
            "Opus escalation → Codex 相談 → 最小副作用の選択肢",
        )
        self.assertNotEqual(relaxed_route_problems(forged), [])

    def test_matcher_rejects_a_bullet_missing_a_route_step(self):
        forged = GOOD_BULLET.replace(" → Opus escalation", "")
        self.assertNotEqual(relaxed_route_problems(forged), [])

    def test_matcher_rejects_a_bullet_that_no_longer_names_the_questions(self):
        forged = GOOD_BULLET.replace("セキュリティ・ライセンス・不可逆操作の質問", "一部の質問")
        self.assertNotEqual(relaxed_route_problems(forged), [])

    def test_matcher_ignores_route_steps_named_only_before_the_batch_half(self):
        # The steps must appear in the batch half of the sentence, not merely
        # somewhere earlier in it.
        forged = GOOD_BULLET.replace(
            "セキュリティ・ライセンス・不可逆操作の質問は、対話では中断し、"
            "`--batch` では中断せず"
            "緩和ルート（Codex 相談 → Opus escalation → 最小副作用の選択肢）で解決する。",
            "Codex 相談 → Opus escalation → 最小副作用の選択肢の順に、"
            "セキュリティ・ライセンス・不可逆操作の質問は、対話では中断し、"
            "`--batch` では中断せずに解決する。",
        )
        self.assertNotEqual(relaxed_route_problems(forged), [])


class TestBatchBulletCitations(unittest.TestCase):
    """AC-3: the bullet cites the reference with both section names, one
    sentence states the only-surviving-stops claim, and no trigger
    condition is restated."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = find_batch_bullet(README_PATH.read_text(encoding="utf-8"))

    def test_bullet_cites_path_and_both_section_names(self):
        self.assertEqual(citation_problems(self.bullet), [])

    def test_one_sentence_states_the_surviving_aborts_are_the_only_stops(self):
        self.assertTrue(only_surviving_stops_sentence_present(self.bullet))

    def test_bullet_restates_no_trigger_literal(self):
        self.assertEqual(restated_trigger_literals(self.bullet), [])

    # --- non-vacuity proofs -------------------------------------------------

    def test_citation_matcher_accepts_the_synthetic_good_bullet(self):
        self.assertEqual(citation_problems(GOOD_BULLET), [])

    def test_citation_matcher_rejects_the_path_alone(self):
        # The bullet already cited the path before this task; the path alone
        # must not satisfy the pin.
        forged = GOOD_BULLET.replace("The batch relaxation", "x").replace(
            "The surviving aborts", "y"
        )
        problems = citation_problems(forged)
        self.assertTrue(any(SECTION_BATCH_RELAXATION in p for p in problems))
        self.assertTrue(any(SECTION_SURVIVING_ABORTS in p for p in problems))

    def test_citation_matcher_rejects_a_bullet_without_the_path(self):
        forged = GOOD_BULLET.replace(QUESTION_RESOLUTION_PATH, "references/other.md")
        self.assertNotEqual(citation_problems(forged), [])

    def test_sentence_matcher_accepts_the_synthetic_good_bullet(self):
        self.assertTrue(only_surviving_stops_sentence_present(GOOD_BULLET))

    def test_sentence_matcher_rejects_a_sentence_without_the_only_claim(self):
        forged = GOOD_BULLET.replace("列挙するものだけである", "列挙する")
        self.assertFalse(only_surviving_stops_sentence_present(forged))

    def test_sentence_matcher_rejects_the_claim_split_across_sentences(self):
        forged = GOOD_BULLET.replace(
            "batch で残る fail-closed の分類停止は The surviving aborts が列挙するものだけである。",
            "batch で残る fail-closed の分類停止がある。The surviving aborts が列挙するものだけである。",
        )
        self.assertFalse(only_surviving_stops_sentence_present(forged))

    def test_sentence_matcher_rejects_a_sentence_without_fail_closed(self):
        forged = GOOD_BULLET.replace("fail-closed の", "")
        self.assertFalse(only_surviving_stops_sentence_present(forged))

    def test_non_restatement_matcher_accepts_the_synthetic_good_bullet(self):
        self.assertEqual(restated_trigger_literals(GOOD_BULLET), [])

    def test_non_restatement_matcher_catches_each_forged_trigger_literal(self):
        for literal in TRIGGER_LITERALS:
            with self.subTest(literal=literal):
                forged = GOOD_BULLET.replace(
                    "失敗時は停止して報告する。", f"{literal} の質問を扱う。失敗時は停止して報告する。"
                )
                self.assertEqual(restated_trigger_literals(forged), [literal])

    def test_non_restatement_matcher_catches_a_literal_split_by_rewrap(self):
        forged = GOOD_BULLET.replace(
            "失敗時は停止して報告する。", "reversible:\nfalse の質問を扱う。失敗時は停止して報告する。"
        )
        self.assertEqual(restated_trigger_literals(forged), ["reversible: false"])


class TestAgentTableRow(unittest.TestCase):
    """AC-4: the agent table lists `opus-escalation` once, inside the
    table's contiguous block directly after `review-evaluator`, with a last
    cell of —, and every pre-existing row survives."""

    @classmethod
    def setUpClass(cls):
        cls.text = README_PATH.read_text(encoding="utf-8")

    def test_exactly_one_row_in_the_contiguous_block_directly_after_review_evaluator(self):
        self.assertEqual(agent_row_problems(self.text), [])

    def test_every_pre_existing_row_is_still_present_exactly_once(self):
        self.assertEqual(pre_existing_row_problems(self.text), [])

    def test_role_text_names_the_opus_subagent_and_uses_no_forbidden_phrase(self):
        self.assertEqual(role_cell_problems(self.text), [])

    # --- non-vacuity proofs -------------------------------------------------

    def test_matchers_accept_the_synthetic_good_readme(self):
        self.assertEqual(agent_row_problems(GOOD_TABLE_README), [])
        self.assertEqual(role_cell_problems(GOOD_TABLE_README), [])

    def test_contiguity_check_rejects_the_row_placed_after_a_non_table_line(self):
        row = [
            line
            for line in GOOD_TABLE_README.splitlines()
            if line.startswith("| opus-escalation |")
        ][0]
        forged = GOOD_TABLE_README.replace(row + "\n", "").replace(
            "別段落。\n", "別段落。\n" + row + "\n"
        )
        problems = agent_row_problems(forged)
        self.assertEqual(len(problems), 1)
        self.assertIn("outside the contiguous block", problems[0])

    def test_check_rejects_the_row_not_directly_after_review_evaluator(self):
        row = [
            line
            for line in GOOD_TABLE_README.splitlines()
            if line.startswith("| opus-escalation |")
        ][0]
        forged = GOOD_TABLE_README.replace(row + "\n", "").replace(
            "| spec-writer |", row + "\n| spec-writer |"
        )
        problems = agent_row_problems(forged)
        self.assertEqual(len(problems), 1)
        self.assertIn("does not directly follow", problems[0])

    def test_check_rejects_a_missing_row(self):
        forged = "\n".join(
            line
            for line in GOOD_TABLE_README.splitlines()
            if not line.startswith("| opus-escalation |")
        )
        self.assertNotEqual(agent_row_problems(forged), [])

    def test_check_rejects_a_duplicated_row(self):
        row = [
            line
            for line in GOOD_TABLE_README.splitlines()
            if line.startswith("| opus-escalation |")
        ][0]
        forged = GOOD_TABLE_README.replace(row + "\n", row + "\n" + row + "\n")
        self.assertNotEqual(agent_row_problems(forged), [])

    def test_check_rejects_a_last_cell_other_than_the_dash(self):
        forged = GOOD_TABLE_README.replace(
            "（決定はオーケストレーター） | — |", "（決定はオーケストレーター） | plan-writing |"
        )
        problems = agent_row_problems(forged)
        self.assertEqual(len(problems), 1)
        self.assertIn("last cell", problems[0])

    def test_check_rejects_a_row_with_the_wrong_cell_count(self):
        forged = GOOD_TABLE_README.replace(
            "（決定はオーケストレーター） | — |", "（決定はオーケストレーター） |"
        )
        self.assertNotEqual(agent_row_problems(forged), [])

    def test_table_locator_fails_loudly_without_the_header(self):
        with self.assertRaises(AssertionError):
            agent_table_block("# README\n\n| a | b |\n|---|---|\n")

    def test_pre_existing_row_check_catches_a_dropped_row(self):
        forged = "\n".join(
            line
            for line in GOOD_TABLE_README.splitlines()
            if not line.startswith("| review-editor |")
        )
        problems = pre_existing_row_problems(forged)
        self.assertEqual(len(problems), 1)
        self.assertIn("review-editor", problems[0])

    def test_role_check_catches_each_forbidden_phrase(self):
        for phrase in FORBIDDEN_ROLE_PHRASES:
            with self.subTest(phrase=phrase):
                forged = GOOD_TABLE_README.replace(
                    "緩和ルートの Opus サブエージェント", f"緩和ルートの Opus サブエージェント {phrase}"
                )
                self.assertTrue(
                    any(phrase in p for p in role_cell_problems(forged)),
                    f"forbidden phrase {phrase!r} was not caught",
                )

    def test_role_check_catches_a_role_that_drops_the_orchestrator_decision(self):
        forged = GOOD_TABLE_README.replace("（決定はオーケストレーター）", "")
        self.assertNotEqual(role_cell_problems(forged), [])


if __name__ == "__main__":
    unittest.main()
