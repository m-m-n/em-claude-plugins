"""Doc tests for task0005 (rework-docs-only-task-routing): the orchestrator
side documents state what happens after a docs-only round.

Covers task0005 Acceptance Criteria
(feature-docs/rework-docs-only-task-routing/tasks/task0005.md; TS-10, TS-11
of VERIFICATION.md):

- AC-1 (FR8): the interactive segment of `skills/develop/SKILL.md`'s verify
  phase item 6 (the text before 「（batch: 確認せず自動 rework。」) states that
  for a docs-only round (文書のみの回) the applied patch returns only
  `verify` to `pending`, `implement` stays `completed`, and the change is
  committed with commit-docs.sh, citing the docs-only correction route of
  `references/rework-task-synthesis.md`.
- AC-2 (FR8, NFR1): the batch segment states the same for the automatic
  rework path, and the lineage cap / hard cap paragraph with its counting
  rule is byte-identical to the base revision (a docs-only round is counted
  like any other round, with no new counting text).
- AC-3 (NFR1): the existing line-broken text 「新しい\\n   rework task が 1
  件以上 workflow.yaml へ登録されるまで戻さない」 and the strings
  `tests/test_develop_skill_rewiring.py` pins for this section remain.
- AC-4 (FR8): the `--once` phase-boundary table keeps exactly its four rows
  and labels; a note directly below it (not a row) states that a docs-only
  verify rework round ends the turn once its patch is applied and committed
  and that the next invocation resumes at `verify`.
- AC-5 (FR9): in `references/review-phase.md`'s Phase R5 section, both the
  interactive rework path and the batch rework paragraph cite the docs-only
  correction route and state that a review-sourced docs-only round returns
  only `review` to `pending` and leaves `implement` completed.
- AC-6 (NFR4, NFR5): every pin carries a non-vacuity negative sample, and
  this module imports the Python standard library only.

Documentation task: structural assertions over the markdown's raw text,
following tests/test_develop_skill_rewiring.py and
tests/test_develop_once_option.py (same target files, self-contained
helpers, no cross-module import).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"

VERIFY_SECTION_START = "### verify フェーズ"
VERIFY_SECTION_END = "### retrospect フェーズ"
BATCH_MARKER = "（batch: 確認せず自動 rework。"

ONCE_SECTION_HEADING = "## `--once` のフェーズ境界"
ONCE_SECTION_END = "## 停止時の報告（停止条件 2-4 のみ）"
BOUNDARY_TABLE_HEADER = "| 境界 | ターンが終わる条件 | 次の起動が再開する位置 |"
BOUNDARY_KIND_LABELS = (
    "通常の step",
    "`retrospect`",
    "verify 失敗時の rework",
    "自動再エントリ",
)
NON_BOUNDARY_MARKER = "**非境界**"
ONCE_INTRO_SENTENCE = (
    "`--once` 指定時にターンを終える 1 フェーズの境界は次の 4 種。いずれも、"
)

R5_START = "## Phase R5: Persist the round record"
R5_END = "## Phase R6: Report"
R5_COMPLETION_GATE = "**Completion gate**"
R5_INTERACTIVE_PATH = "Rework path (interactive)"
R5_BATCH_MARKER = "Batch mode (develop-駆動 only): no offer"

# The docs-only clause of the verify phase: it starts at the term 文書のみの回
# and ends at the commit statement. Both segments carry one clause of this
# shape, so the fragments below are checked inside the clause and not
# against the whole segment (the segment already mentions the SSOT path and
# commit-docs.sh elsewhere, which would make a segment-wide check vacuous).
VERIFY_CLAUSE_START = "文書のみの回"
VERIFY_CLAUSE_END = "コミットする。"
VERIFY_CLAUSE_FRAGMENTS = (
    "references/rework-task-synthesis.md",
    "### Docs-only correction route",
    "`verify` だけを `pending` に戻し",
    "`implement` は `completed` のまま",
    "commit-docs.sh でコミットする",
)
VERIFY_BATCH_CLAUSE_EXTRA_FRAGMENTS = ("自動 rework",)

ONCE_NOTE_START = "文書のみの回"
ONCE_NOTE_FRAGMENTS = (
    "references/rework-task-synthesis.md",
    "### Docs-only correction route",
    "`verify` を `pending` に戻し",
    "`implement` は `completed` のまま",
    "コミット済みになった時点で終え",
    "`verify` から再開する",
)

# A docs-only clause of the review phase starts at the term below and ends
# at the first "completed." after it.
R5_CLAUSE_START = "review-sourced docs-only round"
R5_CLAUSE_END = "completed."
R5_CLAUSE_FRAGMENTS = (
    "docs-only correction route of `references/rework-task-synthesis.md`",
    "returns only `review` to `pending`",
    "leaves `implement` completed",
)

# The review-phase sentences the existing tests pin; they must stay.
R5_PINNED_STRINGS = (
    "review.needs_rework = true",
    "review.status = pending",
    "dispatches rework-planner",
    "is carried inside that patch",
)

# The strings tests/test_develop_skill_rewiring.py pins for the verify
# section, as (segment, string); segment is "interactive", "batch" or "all".
REWIRING_PINS = (
    ("interactive", "rework-task-synthesis.md"),
    ("batch", "rework-task-synthesis.md"),
    ("all", "rework-planner"),
    ("all", 'Task(subagent_type="em-workflow:rework-planner")'),
    ("interactive", "AskUserQuestion"),
    ("interactive", "implement へ rework"),
    ("interactive", "review へ"),
    ("interactive", "中断"),
    ("batch", "系譜 cap"),
    ("batch", "hard cap"),
    ("batch", "batch.verify_rework"),
    ("batch", "retrospect フェーズ"),
    ("batch", "停止せず"),
)

# The pending-rework-task invariant text with its exact line break and
# three-space indent (pinned by tests/test_develop_skill_rewiring.py).
INVARIANT_LINE_BREAK = (
    "新しい\n   rework task が 1 件以上 workflow.yaml へ登録されるまで戻さない"
)

# The lineage cap / hard cap paragraph and counting rule of the base
# revision, byte for byte. A docs-only round is counted like any other
# round, so this block gains no text.
CAP_BLOCK_START = "**batch 自動 rework の系譜 cap**"
CAP_BLOCK_END = "「検証の偽装」になるため）。"
BASE_CAP_BLOCK = """**batch 自動 rework の系譜 cap**: batch モードの verify 失敗時、自動
rework を回すかどうかは次の 2 つの独立した判定で決める。どちらか一方でも
到達していれば cap 到達とする。

- 系譜 cap（値 1）: `batch.verify_rework.failed_id_counts` が保持する
  failed item ID ごとの累積出現回数が 2 に達した時点（同一 ID が 2 回目の
  `failed_items` に現れた時点）で到達する。同じ問題が直らないことを検出
  する。過去ラウンドの `failed_items` に現れなかった新規 ID は累積出現
  回数が 1 のため系譜 cap に触れず、新規予算を得る
- hard cap（値 3）: `batch.verify_rework.rounds`（rework を実行した
  ラウンド数）が 3 に達した時点で到達する。新しい問題が湧き続けることを
  検出する

カウントの更新規則: verify ラウンドが `failed_items` を確定させたら、
そのラウンドに現れた**全 ID** について `failed_id_counts` の累積出現
回数を 1 増やす（1 回目のラウンドも含む）。続けて `rounds` を 1 増やす。
この更新は rework を回すかどうかの判定より先に行う。

cap 到達時は走行を停止しない。`verify.status` は `failed` のまま次の
フェーズ（retrospect）へ進む。残った `failed_items` に `deferred` を
与えない（review の defer は「リスク受容の記録」だが、verify の defer は
「検証の偽装」になるため）。"""


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # Strip ALL whitespace: the Japanese prose hard-wraps without a space at
    # the break point, so collapsing to one space would inject whitespace the
    # source never had (same rationale as the helper of the same name in
    # tests/test_develop_skill_rewiring.py).
    return re.sub(r"\s+", "", text)


def _split_verify_segments(section):
    idx = section.index(BATCH_MARKER)
    return section[:idx], section[idx:]


def _clause(text, start_term, end_term):
    """The whitespace-stripped span from the first `start_term` to the first
    `end_term` after it, inclusive; None when either is absent."""
    stripped = _strip_ws(text)
    start = stripped.find(_strip_ws(start_term))
    if start < 0:
        return None
    end_needle = _strip_ws(end_term)
    end = stripped.find(end_needle, start)
    if end < 0:
        return None
    return stripped[start : end + len(end_needle)]


def _missing_fragments(clause, fragments):
    """Fragments (whitespace-insensitive) absent from `clause`; every
    fragment when the clause itself is absent."""
    if clause is None:
        return list(fragments)
    return [f for f in fragments if _strip_ws(f) not in clause]


def _verify_clause_problems(segment, extra_fragments=()):
    clause = _clause(segment, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END)
    return _missing_fragments(
        clause, VERIFY_CLAUSE_FRAGMENTS + tuple(extra_fragments)
    )


def _boundary_rows(text):
    """The data rows of the `--once` phase-boundary table; [] when the
    table header is absent."""
    if BOUNDARY_TABLE_HEADER not in text:
        return []
    rest = text[text.index(BOUNDARY_TABLE_HEADER) :]
    rows = []
    for line in rest.splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return rows


def _text_below_boundary_table(text):
    """The text between the table's last row and the 非境界 paragraph;
    None when the table or the paragraph is absent."""
    rows = _boundary_rows(text)
    if not rows or NON_BOUNDARY_MARKER not in text:
        return None
    table_end = text.index(rows[-1]) + len(rows[-1])
    marker = text.index(NON_BOUNDARY_MARKER, table_end)
    return text[table_end:marker]


def _once_note_problems(text):
    """Why `text` lacks the docs-only note directly below the table; []
    when the note is there and is not a table row."""
    below = _text_below_boundary_table(text)
    if below is None:
        return ["table or 非境界 paragraph absent"]
    note = below.strip()
    if not note:
        return ["no note between the table and the 非境界 paragraph"]
    if any(line.startswith("|") for line in note.splitlines()):
        return ["the note is a table row"]
    if not _strip_ws(note).startswith(_strip_ws(ONCE_NOTE_START)):
        return ["the note does not start with the docs-only term"]
    return _missing_fragments(_strip_ws(note), ONCE_NOTE_FRAGMENTS)


def _r5_problems(branch):
    clause = _clause(branch, R5_CLAUSE_START, R5_CLAUSE_END)
    return _missing_fragments(clause, R5_CLAUSE_FRAGMENTS)


def _r5_branches(text):
    section = _section(text, R5_START, R5_END)
    gate = section.index(R5_COMPLETION_GATE)
    interactive_path = section.index(R5_INTERACTIVE_PATH)
    batch = section.index(R5_BATCH_MARKER)
    interactive_branch = section[interactive_path:batch]
    batch_paragraph = section[batch:].split("\n\n")[0]
    return section, gate, interactive_branch, batch_paragraph


class TestVerifyInteractiveSegmentDocsOnly(unittest.TestCase):
    """AC-1: the interactive segment states the docs-only transition."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_SECTION_START, VERIFY_SECTION_END)
        cls.interactive, _batch = _split_verify_segments(cls.section)

    def test_interactive_segment_has_docs_only_clause(self):
        clause = _clause(self.interactive, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END)
        self.assertIsNotNone(
            clause,
            "interactive segment must carry a 文書のみの回 clause ending at "
            "the commit statement",
        )

    def test_clause_cites_the_route_by_path_and_heading(self):
        clause = _clause(self.interactive, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END)
        missing = _missing_fragments(clause, VERIFY_CLAUSE_FRAGMENTS[:2])
        self.assertEqual(missing, [])

    def test_clause_returns_only_verify_and_keeps_implement_completed(self):
        clause = _clause(self.interactive, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END)
        missing = _missing_fragments(clause, VERIFY_CLAUSE_FRAGMENTS[2:4])
        self.assertEqual(missing, [])

    def test_clause_states_the_commit(self):
        clause = _clause(self.interactive, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END)
        missing = _missing_fragments(clause, VERIFY_CLAUSE_FRAGMENTS[4:])
        self.assertEqual(missing, [])

    def test_clause_sits_before_the_batch_marker(self):
        self.assertLess(
            _strip_ws(self.section).index(_strip_ws(VERIFY_CLAUSE_START)),
            _strip_ws(self.section).index(_strip_ws(BATCH_MARKER)),
        )

    def test_clause_follows_the_invariant_1_sentence(self):
        stripped = _strip_ws(self.interactive)
        invariant_end = stripped.index(_strip_ws("同\n   SSOT Invariant 1）。"))
        self.assertLess(invariant_end, stripped.index(_strip_ws(VERIFY_CLAUSE_START)))


class TestVerifyBatchSegmentDocsOnly(unittest.TestCase):
    """AC-2 (first half): the batch segment states the same for the
    automatic rework path."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_SECTION_START, VERIFY_SECTION_END)
        _interactive, cls.batch = _split_verify_segments(cls.section)

    def test_batch_segment_states_the_same_for_the_automatic_path(self):
        self.assertEqual(
            _verify_clause_problems(self.batch, VERIFY_BATCH_CLAUSE_EXTRA_FRAGMENTS),
            [],
        )

    def test_clause_is_inside_the_automatic_rework_text(self):
        # The clause precedes the cap-reached branch's "どちらか一方でも到達
        # していれば" sentence, i.e. it belongs to the path that runs rework.
        stripped = _strip_ws(self.batch)
        self.assertLess(
            stripped.index(_strip_ws(VERIFY_CLAUSE_START)),
            stripped.index(_strip_ws("どちらか一方でも到達していれば rework を回さず")),
        )


class TestVerifyCapParagraphUnchanged(unittest.TestCase):
    """AC-2 (second half): the lineage cap / hard cap paragraph and its
    counting rule are byte-identical to the base revision."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_SECTION_START, VERIFY_SECTION_END)

    def _block(self, section):
        start = section.index(CAP_BLOCK_START)
        end = section.index(CAP_BLOCK_END, start) + len(CAP_BLOCK_END)
        return section[start:end]

    def test_cap_block_is_byte_identical_to_the_base_revision(self):
        self.assertEqual(self._block(self.section), BASE_CAP_BLOCK)

    def test_cap_block_has_no_docs_only_counting_text(self):
        self.assertNotIn("文書のみ", self._block(self.section))
        self.assertNotIn("Docs-only", self._block(self.section))


class TestVerifyExistingTextRetained(unittest.TestCase):
    """AC-3: the pending-rework-task invariant text keeps its line break and
    indentation, and the strings the rewiring tests pin remain."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_SECTION_START, VERIFY_SECTION_END)
        cls.interactive, cls.batch = _split_verify_segments(cls.section)

    def test_invariant_text_keeps_its_exact_line_break_and_indent(self):
        self.assertIn(INVARIANT_LINE_BREAK, self.section)

    def test_rewiring_pinned_strings_remain_per_segment(self):
        segments = {
            "interactive": self.interactive,
            "batch": self.batch,
            "all": self.section,
        }
        for segment, needle in REWIRING_PINS:
            with self.subTest(segment=segment, needle=needle):
                self.assertIn(needle, segments[segment])


class TestOnceNoteBelowBoundaryTable(unittest.TestCase):
    """AC-4: the table keeps its four rows and labels; a note directly below
    it states the docs-only round's turn end and the resume position."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, ONCE_SECTION_HEADING, ONCE_SECTION_END)

    def test_table_has_exactly_four_rows(self):
        self.assertEqual(len(_boundary_rows(self.section)), 4)

    def test_table_rows_keep_their_labels_in_order(self):
        for label, row in zip(BOUNDARY_KIND_LABELS, _boundary_rows(self.section)):
            with self.subTest(label=label):
                self.assertIn(label, row)

    def test_intro_sentence_naming_four_kinds_stays(self):
        self.assertIn(_strip_ws(ONCE_INTRO_SENTENCE), _strip_ws(self.section))

    def test_note_below_table_states_the_docs_only_boundary(self):
        self.assertEqual(_once_note_problems(self.section), [])

    def test_note_names_the_resume_position_verify(self):
        below = _strip_ws(_text_below_boundary_table(self.section))
        self.assertIn(_strip_ws("次の起動は `verify` から再開する"), below)


class TestReviewPhaseR5DocsOnlyPointer(unittest.TestCase):
    """AC-5: both Phase R5 rework paths cite the docs-only correction route
    and state that a review-sourced docs-only round returns only `review`
    to `pending` and leaves `implement` completed."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PHASE_PATH)
        (
            cls.section,
            cls.gate,
            cls.interactive_branch,
            cls.batch_paragraph,
        ) = _r5_branches(cls.text)

    def test_interactive_rework_path_has_the_docs_only_sentence(self):
        self.assertEqual(_r5_problems(self.interactive_branch), [])

    def test_batch_rework_paragraph_has_the_docs_only_sentence(self):
        self.assertEqual(_r5_problems(self.batch_paragraph), [])

    def test_interactive_sentence_follows_the_completion_gate(self):
        clause_at = self.section.index(R5_CLAUSE_START)
        self.assertLess(self.gate, clause_at)

    def test_existing_pinned_sentences_remain(self):
        for needle in R5_PINNED_STRINGS:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.section)

    def test_needs_rework_write_still_precedes_the_dispatch(self):
        self.assertLess(
            self.section.index("review.needs_rework = true"),
            self.section.index("dispatches rework-planner"),
        )


# A docs-only clause is shaped like the real one (hard-wrapped the way the
# document wraps), so the negative samples below exercise the same matchers
# as the pins above.
_GOOD_VERIFY_SEGMENT = (
    "   SSOT Invariant 1）。ただし rework-planner の検証済みの結果が文書のみの回\n"
    "   （`${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` の\n"
    "   `### Docs-only correction route`）の場合は、自動 rework でも適用した\n"
    "   patch は `verify` だけを `pending` に戻し、`implement` は `completed` の\n"
    "   まま残して、この変更を commit-docs.sh でコミットする。\n"
    "   タスク合成の中身は同 SSOT が定義する。\n"
)
_GOOD_ONCE_SECTION = (
    "`--once` 指定時にターンを終える 1 フェーズの境界は次の 4 種。いずれも、\n"
    "\n"
    "| 境界 | ターンが終わる条件 | 次の起動が再開する位置 |\n"
    "|---|---|---|\n"
    "| 通常の step | 条件 コミット済み | 次の step |\n"
    "| `retrospect` | 条件 コミット済み | Step C |\n"
    "| verify 失敗時の rework | 条件 コミット済み | `implement` |\n"
    "| 自動再エントリ | 条件 コミット済み | 再エントリした step |\n"
    "\n"
    "文書のみの回（`${CLAUDE_PLUGIN_ROOT}/references/rework-task-synthesis.md` の\n"
    "`### Docs-only correction route`）の verify rework は、同じ境界でターンを終える。\n"
    "patch を適用して `verify` を `pending` に戻し（`implement` は `completed` の\n"
    "まま）、コミット済みになった時点で終え、次の起動は `verify` から再開する。\n"
    "\n"
    "**非境界**: 本文。\n"
)
_GOOD_R5_BRANCH = (
    "When rework-planner's validated result is a review-sourced docs-only round\n"
    "(the docs-only correction route of `references/rework-task-synthesis.md`,\n"
    "cited here and not restated), the applied patch returns only `review` to\n"
    "`pending` and leaves `implement` completed.\n"
)


class TestDocsOnlyReworkAssertionsCanFail(unittest.TestCase):
    """AC-6: every matcher above fails on a sample without the pinned text,
    and passes on a sample with it (non-vacuity)."""

    def test_verify_matcher_accepts_the_well_formed_sample(self):
        self.assertEqual(
            _verify_clause_problems(_GOOD_VERIFY_SEGMENT, ("自動 rework",)), []
        )

    def test_verify_matcher_rejects_a_segment_without_the_clause(self):
        sample = "   SSOT Invariant 1）。タスク合成の中身は同 SSOT が定義する。\n"
        self.assertEqual(
            _verify_clause_problems(sample), list(VERIFY_CLAUSE_FRAGMENTS)
        )

    def test_verify_matcher_rejects_returning_both_steps(self):
        sample = _GOOD_VERIFY_SEGMENT.replace(
            "`verify` だけを `pending` に戻し、`implement` は `completed` の\n"
            "   まま残して、",
            "`implement` と `verify` を `pending` に戻し、",
        )
        self.assertNotEqual(sample, _GOOD_VERIFY_SEGMENT)
        problems = _verify_clause_problems(sample)
        self.assertIn("`verify` だけを `pending` に戻し", problems)
        self.assertIn("`implement` は `completed` のまま", problems)

    def test_verify_matcher_rejects_a_missing_route_citation(self):
        sample = _GOOD_VERIFY_SEGMENT.replace("### Docs-only correction route", "")
        self.assertIn("### Docs-only correction route", _verify_clause_problems(sample))

    def test_verify_matcher_rejects_a_missing_commit_statement(self):
        sample = _GOOD_VERIFY_SEGMENT.replace("commit-docs.sh でコミットする", "記録する")
        self.assertEqual(
            _clause(sample, VERIFY_CLAUSE_START, VERIFY_CLAUSE_END), None
        )
        self.assertTrue(_verify_clause_problems(sample))

    def test_verify_batch_matcher_rejects_a_clause_without_the_automatic_path(self):
        sample = _GOOD_VERIFY_SEGMENT.replace("自動 rework でも", "")
        self.assertEqual(_verify_clause_problems(sample), [])
        self.assertEqual(
            _verify_clause_problems(sample, ("自動 rework",)), ["自動 rework"]
        )

    def test_verify_matcher_ignores_commit_docs_text_outside_the_clause(self):
        # The segment-wide mention of commit-docs.sh must not satisfy the
        # clause check on its own.
        sample = (
            "   いずれの分岐も workflow.yaml 更新後に commit-docs.sh でコミットする。\n"
            + _GOOD_VERIFY_SEGMENT.replace(
                "この変更を commit-docs.sh でコミットする。", "この変更を記録する。"
            )
        )
        self.assertTrue(_verify_clause_problems(sample))

    def test_cap_block_comparison_detects_an_added_counting_sentence(self):
        mutated = BASE_CAP_BLOCK.replace(
            "この更新は rework を回すかどうかの判定より先に行う。",
            "この更新は rework を回すかどうかの判定より先に行う。"
            "文書のみの回は数えない。",
        )
        self.assertNotEqual(mutated, BASE_CAP_BLOCK)
        section = "前文\n" + mutated + "\n\n### retrospect フェーズ"
        start = section.index(CAP_BLOCK_START)
        end = section.index(CAP_BLOCK_END, start) + len(CAP_BLOCK_END)
        self.assertNotEqual(section[start:end], BASE_CAP_BLOCK)

    def test_invariant_pin_requires_the_exact_line_break(self):
        collapsed = INVARIANT_LINE_BREAK.replace("\n   ", " ")
        reindented = INVARIANT_LINE_BREAK.replace("\n   ", "\n  ")
        self.assertNotIn(INVARIANT_LINE_BREAK, collapsed)
        self.assertNotIn(INVARIANT_LINE_BREAK, reindented)

    def test_once_matcher_accepts_the_well_formed_sample(self):
        self.assertEqual(len(_boundary_rows(_GOOD_ONCE_SECTION)), 4)
        self.assertEqual(_once_note_problems(_GOOD_ONCE_SECTION), [])

    def test_once_matcher_rejects_a_missing_note(self):
        note_start = _GOOD_ONCE_SECTION.index("文書のみの回")
        marker = _GOOD_ONCE_SECTION.index(NON_BOUNDARY_MARKER)
        sample = _GOOD_ONCE_SECTION[:note_start] + _GOOD_ONCE_SECTION[marker:]
        self.assertEqual(
            _once_note_problems(sample),
            ["no note between the table and the 非境界 paragraph"],
        )

    def test_once_matcher_rejects_a_note_without_the_resume_position(self):
        sample = _GOOD_ONCE_SECTION.replace("次の起動は `verify` から再開する", "次の起動で続ける")
        self.assertIn("`verify` から再開する", _once_note_problems(sample))

    def test_once_matcher_rejects_a_note_that_is_a_fifth_table_row(self):
        sample = _GOOD_ONCE_SECTION.replace(
            "| 自動再エントリ | 条件 コミット済み | 再エントリした step |\n\n文書のみの回",
            "| 自動再エントリ | 条件 コミット済み | 再エントリした step |\n"
            "| 文書のみの回 | 条件 コミット済み | `verify` |\n\n文書のみの回",
        )
        self.assertNotEqual(sample, _GOOD_ONCE_SECTION)
        self.assertEqual(len(_boundary_rows(sample)), 5)

    def test_once_matcher_rejects_a_note_that_is_not_directly_below_the_table(self):
        sample = _GOOD_ONCE_SECTION.replace(
            "\n文書のみの回", "\n別の段落。\n\n文書のみの回", 1
        )
        self.assertNotEqual(sample, _GOOD_ONCE_SECTION)
        self.assertIn(
            "the note does not start with the docs-only term",
            _once_note_problems(sample),
        )

    def test_r5_matcher_accepts_the_well_formed_sample(self):
        self.assertEqual(_r5_problems(_GOOD_R5_BRANCH), [])

    def test_r5_matcher_rejects_a_branch_without_the_sentence(self):
        self.assertEqual(
            _r5_problems("Rework path (interactive): ordinary text only.\n"),
            list(R5_CLAUSE_FRAGMENTS),
        )

    def test_r5_matcher_rejects_returning_implement_to_pending(self):
        sample = _GOOD_R5_BRANCH.replace(
            "returns only `review` to\n`pending` and leaves `implement` completed.",
            "returns `review` and `implement` to\n`pending`.",
        )
        self.assertNotEqual(sample, _GOOD_R5_BRANCH)
        self.assertTrue(_r5_problems(sample))

    def test_r5_matcher_rejects_a_missing_route_citation(self):
        sample = _GOOD_R5_BRANCH.replace(
            "the docs-only correction route of `references/rework-task-synthesis.md`",
            "a correction route",
        )
        self.assertIn(
            "docs-only correction route of `references/rework-task-synthesis.md`",
            _r5_problems(sample),
        )

    def test_r5_batch_paragraph_split_excludes_later_paragraphs(self):
        text = (
            R5_START
            + "\n"
            + R5_COMPLETION_GATE
            + "\n"
            + R5_INTERACTIVE_PATH
            + " text\n\n"
            + R5_BATCH_MARKER
            + " paragraph without the sentence.\n\n"
            + _GOOD_R5_BRANCH
            + "\n"
            + R5_END
        )
        _section_text, _gate, _interactive, batch_paragraph = _r5_branches(text)
        self.assertNotIn(R5_CLAUSE_START, batch_paragraph)
        self.assertTrue(_r5_problems(batch_paragraph))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6 / NFR5: this module imports the Python standard library only."""

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
        self.assertEqual(imported - stdlib_names, set())

    def test_stdlib_check_flags_a_third_party_import(self):
        tree = ast.parse("import yaml\nfrom pathlib import Path\n")
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertEqual(imported - set(sys.stdlib_module_names), {"yaml"})


if __name__ == "__main__":
    unittest.main()
