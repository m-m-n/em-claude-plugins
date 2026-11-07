"""Document contract tests for task0008 (plan-feature-docs-route): develop's
`## Step A.6: failed からの入口` gains the feature-docs judgment, and
create-plan-phase.md section 13 gains `### Feature-docs correction dispatch`.

Covers task0008 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0008.md):

- AC-1: `TestAC1ScriptAndOrder` -- Step A.6 runs
  `scripts/feature-docs-entry.py` with the four arguments before
  `scripts/report-name-entry.py`, names its output keys, and evaluates both
  judgments in one evaluation.
- AC-2 (NFR1): `TestAC2DispatchCoversBothJudgments` -- a feature-docs
  `dispatch` runs section 13's subsection, before stop condition 3, whatever
  `failed_kind` is, in interactive and batch runs, with no gate and no
  question.
- AC-3 (FR9): `TestAC3RestorationSplit` -- the D9 split of the restoration.
  task0010 (plan-feature-docs-route, review round 1) revises that split: a
  correction that is not the last writes its patch only, and every
  restoration item goes into the last correction's one Write.
- AC-4: `TestAC4UnresolvedJudgment` -- an unresolved judgment leaves
  `workflow.yaml` unchanged for that judgment, stop condition 3 fires, and
  the report names each unresolved judgment's failed conditions.
- AC-5: `TestAC5Section13Subsection` -- the one H3 inside section 13 and the
  points it states.
- AC-6: `TestAC6ForbiddenWords` -- none of the forbidden words appears from
  the section 12 heading to the end of create-plan-phase.md.

Conventions: standard library `unittest` only. Step A.6 assertions are scoped
to the text between its heading and Step B's heading and match Japanese
phrases after removing all whitespace (the convention of
tests/test_failed_entry_develop_docs.py). The subsection is located by its H3
heading, up to the end of the document. Every check is a function that
returns its defects, so each negative proof runs the same function on a
mutated copy of the live text. No test writes under `em-workflow/`.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_PATH = os.path.join(REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md")
CREATE_PLAN_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "phases", "create-plan-phase.md"
)

STEP_A6_HEADING = "## Step A.6: failed からの入口"
STEP_B_HEADING = "## Step B: 自走ループ"
SECTION_12_HEADING = "## 12. Declared change set derivation"
SECTION_13_HEADING = "## 13. Final-path correction dispatch"
SUBSECTION_HEADING = "### Feature-docs correction dispatch"

FD_SCRIPT = "${CLAUDE_PLUGIN_ROOT}/scripts/feature-docs-entry.py"
RN_SCRIPT = "${CLAUDE_PLUGIN_ROOT}/scripts/report-name-entry.py"
FOUR_ARGUMENTS = ("--workflow", "--journal", "--target-repo", "--base-commit")

# The bold labels that section 13's existing paragraphs already use.
SECTION_13_LABELS = (
    "**Pre-dispatch.**",
    "**Dispatch.**",
    "**Record.**",
    "**Validation.**",
    "**Failure outcome.**",
    "**Apply.**",
)

FORBIDDEN_WORD_RE = re.compile(
    r"exclud\w*|subtract\w*|ignor\w*|除外", re.IGNORECASE
)
FORBIDDEN_LITERALS = (
    "SUPERSET",
    "CONTAINED IN",
    "Initial-planning path",
    "protocol error on BOTH paths",
)

FENCE = "`" * 3


def _read(path):
    if not os.path.isfile(path):
        raise AssertionError(f"expected file to exist: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_ws(text):
    # The skill hard-wraps Japanese prose without a space at the break
    # point, so phrases are matched after stripping all whitespace.
    return re.sub(r"\s+", "", text)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


def _missing_ws(text, phrases):
    """The phrases the whitespace-stripped text does not hold."""
    return [p for p in phrases if not _contains(text, p)]


def _missing_norm(text, phrases):
    """The phrases the whitespace-collapsed text does not hold."""
    flat = _norm(text)
    return [p for p in phrases if _norm(p) not in flat]


def _replace_flexible(text, phrase, replacement):
    """Replace the one occurrence of `phrase`, wherever the document wraps
    its lines. Raises when the phrase is not found, so a negative proof never
    mutates nothing."""
    pattern = r"\s*".join(re.escape(ch) for ch in _strip_ws(phrase))
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1)
    if count != 1:
        raise AssertionError(f"phrase to mutate not found: {phrase!r}")
    return new


def _lines_outside_fences(text):
    """[(offset, line)] for every line that is not inside a fenced block."""
    out = []
    in_fence = False
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(FENCE):
            in_fence = not in_fence
        elif not in_fence:
            out.append((offset, line))
        offset += len(line)
    return out


def _heading_offsets(text, heading):
    return [
        offset
        for offset, line in _lines_outside_fences(text)
        if line.rstrip("\n") == heading
    ]


def _step_a6_section(text):
    starts = [
        o
        for o, line in _lines_outside_fences(text)
        if line.startswith(STEP_A6_HEADING)
    ]
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one {STEP_A6_HEADING!r} heading, found {len(starts)}"
        )
    ends = [
        o
        for o, line in _lines_outside_fences(text)
        if line.startswith(STEP_B_HEADING) and o > starts[0]
    ]
    if not ends:
        raise AssertionError(f"{STEP_B_HEADING!r} must follow Step A.6")
    return text[starts[0] : ends[0]]


def _subsection(text):
    """From the H3 heading to the end of the document. Raises unless the
    heading is present exactly once."""
    starts = _heading_offsets(text, SUBSECTION_HEADING)
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one {SUBSECTION_HEADING!r} heading, found {len(starts)}"
        )
    return text[starts[0] :]


def _from_section_12(text):
    starts = _heading_offsets(text, SECTION_12_HEADING)
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one {SECTION_12_HEADING!r} heading, found {len(starts)}"
        )
    return text[starts[0] :]


def _blocks(section):
    """The section split into blocks: a block ends at a blank line, and a
    numbered list item (`N. `) starts a block of its own. A numbered item
    keeps its indented continuation lines and sub-bullets."""
    blocks = []
    current = []

    def flush():
        if current:
            blocks.append("\n".join(current))
            current.clear()

    for line in section.splitlines():
        if not line.strip():
            flush()
            continue
        if re.match(r"\d+\. ", line):
            flush()
        current.append(line)
    flush()
    return blocks


def _block_with(section, *phrases):
    """The first block (see `_blocks`) that holds every phrase."""
    for block in _blocks(section):
        if not _missing_ws(block, phrases):
            return block
    raise AssertionError(f"no block holds {phrases!r}")


def _split_region(section):
    """The restoration-split paragraph, its list and the paragraph on an
    interruption between corrections: from the `**復元の分割**` label up to the
    paragraph on untouched worktrees."""
    start = section.find("**復元の分割**")
    end = section.find("対象タスクの worktree とブランチには触れない")
    if start < 0 or end < 0 or end < start:
        raise AssertionError("the restoration-split region is not found")
    return section[start:end]


# ---------------------------------------------------------------------------
# Defect finders: each returns the list of defects of a text, so a negative
# proof can run the very same function on a mutated copy.
# ---------------------------------------------------------------------------


def order_defects(section):
    """The feature-docs script is named before the report-name script, and
    the four arguments sit before the report-name script."""
    defects = []
    fd = section.find(FD_SCRIPT)
    rn = section.find(RN_SCRIPT)
    if fd < 0:
        defects.append(f"{FD_SCRIPT} is not named")
    if rn < 0:
        defects.append(f"{RN_SCRIPT} is not named")
    if fd >= 0 and rn >= 0:
        if fd > rn:
            defects.append("the feature-docs script comes after the report-name script")
        before_rn = section[:rn]
        for arg in FOUR_ARGUMENTS:
            if arg not in before_rn:
                defects.append(f"{arg} is not stated before the report-name script")
    return defects


def dispatch_item_defects(item):
    """The `dispatch` item covers both judgments with the existing sentences."""
    return _missing_ws(
        item,
        (
            "`references/phases/create-plan-phase.md` の 13 節",
            "`### Feature-docs correction dispatch`",
            "`failed_kind` が `decision` でも",
            "停止条件 3 より前に評価",
            "対話実行と batch 実行のどちらでも同じこの入口を使う",
            "新しい `gate_id` もユーザーへの質問も導入しない",
            "どちらの `dispatch` にも当てはまる",
        ),
    )


# The split text task0010 replaces: it wrote each correction's task-level items
# in that correction's own Write. Kept as a fixture so the negative proofs show
# that split_defects rejects it.
PRE_CHANGE_SPLIT_REGION = """**復元の分割**は、1 回の評価の中で書き込みをどう配分するかを決める。

- タスクの項目（`tasks.{T}.status` と `tasks.{T}.routeback_failed_journal_line`）は、
  訂正ごとに、その訂正の対象について書く。最終パスの訂正の対象は `violations`、
  feature-docs の訂正の対象は `targets` である。その訂正のパッチと一緒に、
  その訂正の成果物のコミットの後の 1 回の Write と 1 回のコミットで書く。
- step の項目（`implement` と `failed_kind`）は、評価の最後の訂正の Write に入れる。
  ただし、未解決の判定が 1 つもないときに限る。未解決の判定は、`blocked` になった
  判定、終了コードが 0 以外だった判定、検証済みのパッチを得ないまま終わった判定。
- feature-docs の訂正は、`final_path_remaining` が false のとき最後の訂正になる。
  true のときは、8. のとおり捕捉し直した先端で最終パスの判定が続き、`implement` が
  `failed` のままその判定が `dispatch` を返せば、その訂正が最後の訂正になる。
- 捕捉し直した先端での最終パスの判定が `none` を返したときは、step の項目だけを
  1 回の Write と 1 回のコミットで書く。

訂正と訂正の間で中断した場合、次の起動は feature-docs の判定が `none` を返し、
最終パスの判定に進む。13 節の Apply 段落は、各 Write がパッチと復元を一緒に書くので
そのまま成り立つ。

"""

# The per-correction task-level wording the pre-change split used. The section
# between the Step A.6 heading and the Step B heading no longer holds it.
STALE_PER_CORRECTION_PHRASES = (
    "訂正ごとに、その訂正の対象について書く",
    "その訂正のパッチと一緒に",
    "その訂正の成果物のコミットの後の 1 回の Write と 1 回のコミットで書く",
)

PRE_CHANGE_ITEM_9 = (
    "9. 検証済みのパッチを得たときは、成果物のコミットを作った後、パッチと復元を\n"
    "   1 回の Write と 1 回のコミットで書く。コミットは\n"
    "   `${CLAUDE_PLUGIN_ROOT}/scripts/commit-docs.sh` で行う。評価が終わったら\n"
    "   Step B へ進む。"
)


def split_defects(block):
    """The D9 restoration split, as revised by task0010."""
    return _missing_ws(
        block,
        (
            # a correction that is not the last writes its patch only
            "評価の最後でない訂正の Write は、その訂正のパッチだけを書く",
            "対象の `tasks.{T}.status` は `failed` のままにし",
            "`tasks.{T}.routeback_failed_journal_line` は書かない",
            "journal に `failed` のイベントがあるかどうかにかかわらず",
            # every restoration item: the last correction's one Write, only
            # when nothing is unresolved
            "復元の項目はすべて、評価の最後の訂正の Write に、まとめて入れる",
            "ただし、未解決の判定が 1 つもないときに限る",
            # task-level items: the targets of every correction
            "タスクの項目",
            "評価のすべての訂正の対象について書く",
            "最終パスの訂正の対象は `violations`",
            "feature-docs の訂正の対象は `targets`",
            # step-level items: the same Write
            "step の項目（`implement` と `failed_kind`）も同じ Write に入れる",
            # unresolved judgment: nothing is written
            "`blocked` になった判定",
            "終了コードが 0 以外だった判定",
            "検証済みのパッチを得ないまま終わった判定",
            "未解決の判定があるときは、タスクの項目も step の項目も、復元の項目を 1 つも書かない",
            # the final_path_remaining rule
            "`final_path_remaining` が false のとき最後の訂正になる",
            "true のときは",
            "捕捉し直した先端で最終パスの判定が続き",
            # the none case: feature-docs targets and step-level items together
            "`none` を返したときは、feature-docs の訂正の対象のタスクの項目と step の項目を、"
            "まとめて 1 回の Write と 1 回のコミットで書く",
        ),
    )


def interruption_defects(block):
    """The paragraph on an interruption between corrections, or on an
    unresolved final-path correction."""
    return _missing_ws(
        block,
        (
            "訂正と訂正の間で中断した場合",
            "最終パスの訂正が未解決で終わった場合",
            "対象のタスクはどれも `status` が `failed` のまま",
            "`implement` も `failed` のまま",
            "feature-docs の判定が `none` を返し",
            "評価は最終パスの判定に進む",
            "最終パスの判定は、それらのタスクを失敗したタスクとして選ぶ",
            "その評価の復元は、その評価自身の訂正の対象について書く",
            "13 節の Apply 段落",
            "最終パスの訂正が常にその評価の最後の訂正",
        ),
    )


def stale_split_defects(text):
    """The per-correction task-level wording of the pre-change split that
    `text` still holds."""
    return [p for p in STALE_PER_CORRECTION_PHRASES if _contains(text, p)]


def item_9_defects(item):
    """List item 9: the pinned sentence plus the patch-only statement."""
    return _missing_ws(
        item,
        (
            "成果物のコミットを作った後",
            "パッチと復元を 1 回の Write と 1 回のコミットで書く",
            "Write が運ぶ復元は、下記の復元の分割がその Write に割り当てるものである",
            "評価の最後でない訂正の Write は、パッチだけを運ぶ",
            "`${CLAUDE_PLUGIN_ROOT}/scripts/commit-docs.sh`",
        ),
    )


def unresolved_item_defects(item):
    """Item on none / blocked / non-zero results: AC-4."""
    return _missing_ws(
        item,
        (
            "その判定の分の workflow.yaml を変えない",
            "未解決",
            "停止条件 3 が発火する",
            "`blocked` では停止の報告に失敗した条件を名指しする",
            "未解決の判定が複数あるときは",
            "各判定の失敗した条件をすべて",
            "その判定の `errors` から読んで名指しする",
        ),
    )


def forbidden_word_defects(text):
    """The forbidden words of IMPLEMENTATION.md Conventions, in `text`."""
    defects = [m.group(0) for m in FORBIDDEN_WORD_RE.finditer(text)]
    defects += [lit for lit in FORBIDDEN_LITERALS if lit in text]
    return defects


def subsection_defects(sub):
    """Each point of the Design list for the subsection (AC-5)."""
    return _missing_norm(
        sub,
        (
            # where it runs from
            "Run from `skills/develop/SKILL.md`'s `## Step A.6: failed からの入口`",
            "when `scripts/feature-docs-entry.py` returns `dispatch`",
            # the patch contract, cited
            "`references/workflow-patch.md`'s `## Feature-docs correction`",
            "cited here and not restated",
            # the pre-dispatch checks
            "The checks before the dispatch are those of section 2",
            # the dispatch
            '`Task(subagent_type="em-workflow:implementation-planner")`',
            "`planning_inputs.feature_docs_correction` copied from the entry script's `targets`",
            "the `write_policy` of `references/contracts/planner-contract.md`'s "
            "`### feature_docs_correction (dispatch-resolved value)`",
            # the stage-1 request result
            "A stage-1 request result is handled by the grant rule of section 4",
            "followed by one re-dispatch",
            # the record
            "`phase-state/create-plan.yaml`",
            "a new `request_id`",
            "the next unused `patch_id`",
            "The `create-plan` step stays `completed`",
            "an interrupted correction restarts from Step A.6",
            # the validation
            "the canonical invocation of section 9, plus `--journal`",
            # the failure outcome
            "Any result other than `completed`",
            "any validator exit other than 0",
            "any stale result ends the dispatch",
            "the worker's writes are discarded",
            "`workflow.yaml` is not changed",
            # the apply step
            "the artifact commit comes first",
            "the restoration of `skills/develop/SKILL.md`'s `## Step A.6: failed からの入口`",
            "its split",
        ),
    )


_GATE_ID_PREFIXES = (
    "create-spec",
    "create-plan",
    "design",
    "implement",
    "verify",
    "rework",
    "review",
    "develop",
)
_GATE_ID_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _GATE_ID_PREFIXES) + r")\.([a-z][a-z-]*)\b"
)
_FILE_SUFFIXES = {"md", "yaml", "yml", "py", "sh", "json"}


def gate_id_shaped_tokens(text):
    return sorted(
        {
            m.group(0)
            for m in _GATE_ID_RE.finditer(text)
            if m.group(2) not in _FILE_SUFFIXES
        }
    )


# ---------------------------------------------------------------------------
# Step A.6
# ---------------------------------------------------------------------------


class _SkillTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _step_a6_section(cls.text)

    def assertStates(self, haystack, phrase, why):
        self.assertTrue(
            _contains(haystack, phrase),
            f"Step A.6 must state {why}: expected {phrase!r}",
        )


class TestAC1ScriptAndOrder(_SkillTestCase):
    """AC-1."""

    def test_opening_paragraph_names_the_feature_docs_correction(self):
        opening = _blocks(self.section)[1]
        self.assertEqual(
            _missing_ws(
                opening,
                (
                    "feature 名を指定した再実行の開始時",
                    "feature-docs の訂正",
                    "`files` から `feature-docs` 配下のパスを取り除く訂正",
                ),
            ),
            [],
        )

    def test_feature_docs_script_is_run_with_python3(self):
        self.assertIn("python3 " + FD_SCRIPT, self.section)

    def test_four_arguments_and_script_order(self):
        self.assertEqual(order_defects(self.section), [])

    def test_feature_docs_script_item_names_its_output_keys(self):
        item = _block_with(self.section, FD_SCRIPT, "python3")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "`entry`（`none` / `dispatch` / `blocked`）",
                    "`targets`（各要素が `task_id` / `path` / `failed_journal_line`）",
                    "`errors`",
                    "`final_path_remaining`",
                    "判定の定義はこのスクリプトが持ち、ここでは繰り返さない",
                ),
            ),
            [],
        )

    def test_report_name_script_item_keeps_its_output_keys(self):
        item = _block_with(self.section, RN_SCRIPT, "python3")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "`entry`（`none` / `dispatch` / `blocked`）",
                    "`violations`（各要素が `task_id` / `path` / `failed_journal_line`）",
                    "`errors`",
                    "判定の定義はこのスクリプトが持ち、ここでは繰り返さない",
                ),
            ),
            [],
        )

    def test_both_judgments_are_evaluated_in_one_evaluation(self):
        item = _block_with(self.section, "1 回の評価")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "Step A.6 の 1 回の評価",
                    "どちらの結果も、もう片方の判定の評価を飛ばさない",
                ),
            ),
            [],
        )

    # negative proofs
    def test_negative_swapped_scripts_fail_the_order_check(self):
        swapped = (
            self.section.replace(FD_SCRIPT, "@@SWAP@@")
            .replace(RN_SCRIPT, FD_SCRIPT)
            .replace("@@SWAP@@", RN_SCRIPT)
        )
        self.assertNotEqual(order_defects(swapped), [])
        self.assertTrue(
            any("comes after" in d for d in order_defects(swapped)),
            order_defects(swapped),
        )

    def test_negative_a_section_without_the_feature_docs_script_fails(self):
        without = self.section.replace(FD_SCRIPT, "")
        self.assertNotEqual(order_defects(without), [])

    def test_negative_arguments_after_the_report_name_script_fail(self):
        moved = self.section
        for arg in FOUR_ARGUMENTS:
            moved = moved.replace(arg, "@@")
        moved = moved + "\n" + " ".join(FOUR_ARGUMENTS)
        self.assertNotEqual(order_defects(moved), [])


class TestAC2DispatchCoversBothJudgments(_SkillTestCase):
    """AC-2 (NFR1)."""

    def test_the_dispatch_item_covers_both_judgments(self):
        item = _block_with(self.section, "停止条件 3 より前に評価")
        self.assertEqual(dispatch_item_defects(item), [])

    def test_the_dispatch_item_names_each_judgments_correction(self):
        item = _block_with(self.section, "停止条件 3 より前に評価")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "最終パスの判定の `dispatch` は 13 節の最終パスの訂正",
                    "feature-docs の判定の `dispatch` は 13 節の `### Feature-docs correction dispatch` を実行する",
                ),
            ),
            [],
        )

    def test_the_gate_and_question_sentence_appears_once(self):
        self.assertEqual(
            _strip_ws(self.section).count(
                _strip_ws("新しい `gate_id` もユーザーへの質問も導入しない")
            ),
            1,
        )

    # negative proofs
    def test_negative_the_pre_change_item_does_not_cover_the_feature_docs_dispatch(self):
        pre_change = (
            "4. 結果が `dispatch` のときは、`references/phases/create-plan-phase.md` の 13 節を実行する。"
            "`failed_kind` が `decision` でも、外部要因を示す値でも、この入口は停止条件 3 より前に"
            "評価される。対話実行と batch 実行のどちらでも同じこの入口を使う。新しい `gate_id` も"
            "ユーザーへの質問も導入しない。"
        )
        defects = dispatch_item_defects(pre_change)
        self.assertIn("`### Feature-docs correction dispatch`", defects)
        self.assertIn("どちらの `dispatch` にも当てはまる", defects)

    def test_negative_an_item_that_adds_a_question_loses_the_no_question_sentence(self):
        item = _block_with(self.section, "停止条件 3 より前に評価")
        forged = _replace_flexible(
            item,
            "新しい `gate_id` もユーザーへの質問も導入しない",
            "ユーザーに質問する",
        )
        self.assertIn(
            "新しい `gate_id` もユーザーへの質問も導入しない",
            dispatch_item_defects(forged),
        )


class TestAC3RestorationSplit(_SkillTestCase):
    """AC-3 (TS-8, FR9)."""

    def setUp(self):
        self.block = _split_region(self.section)

    def test_the_split_states_every_d9_point(self):
        self.assertEqual(split_defects(self.block), [])

    def test_the_split_follows_the_restoration_list(self):
        flat = _strip_ws(self.section)
        self.assertLess(
            flat.index(_strip_ws("`implement` を `pending` にする")),
            flat.index(_strip_ws("**復元の分割**")),
        )

    def test_the_split_names_the_interruption_between_corrections(self):
        # AC-4 (FR8, TS-12): the targets keep status failed, the feature-docs
        # judgment returns none, the final-path judgment still selects them.
        self.assertEqual(interruption_defects(self.block), [])

    def test_the_non_last_write_carries_the_patch_only(self):
        # AC-1 (FR9).
        bullet = _block_with(
            self.block,
            "評価の最後でない訂正の Write は、その訂正のパッチだけを書く",
        )
        self.assertEqual(
            _missing_ws(
                bullet,
                (
                    "対象の `tasks.{T}.status` は `failed` のままにし",
                    "`tasks.{T}.routeback_failed_journal_line` は書かない",
                ),
            ),
            [],
        )

    def test_every_restoration_item_goes_into_the_last_correction_write(self):
        # AC-2 (FR9, TS-8): both targets lists, the step-level items, the
        # unresolved condition and the nothing-written rule.
        bullet = _block_with(
            self.block,
            "復元の項目はすべて、評価の最後の訂正の Write に、まとめて入れる",
        )
        self.assertEqual(
            _missing_ws(
                bullet,
                (
                    "ただし、未解決の判定が 1 つもないときに限る",
                    "評価のすべての訂正の対象について書く",
                    "最終パスの訂正の対象は `violations`",
                    "feature-docs の訂正の対象は `targets`",
                    "step の項目（`implement` と `failed_kind`）も同じ Write に入れる",
                ),
            ),
            [],
        )
        self.assertTrue(
            _contains(
                self.block,
                "未解決の判定があるときは、タスクの項目も step の項目も、復元の項目を 1 つも書かない",
            )
        )

    def test_the_none_case_writes_the_feature_docs_targets_with_the_step_items(self):
        # AC-3 (FR9).
        bullet = _block_with(self.block, "`none` を返したときは")
        self.assertEqual(
            _missing_ws(
                bullet,
                (
                    "捕捉し直した先端での最終パスの判定が `none` を返したときは",
                    "feature-docs の訂正の対象のタスクの項目と step の項目を、"
                    "まとめて 1 回の Write と 1 回のコミットで書く",
                ),
            ),
            [],
        )

    def test_item_9_keeps_its_pinned_sentence_and_states_the_patch_only_write(self):
        # AC-5.
        item = _block_with(self.section, "成果物のコミットを作った後")
        self.assertEqual(item_9_defects(item), [])

    def test_the_section_no_longer_writes_each_corrections_task_items_with_its_patch(self):
        # AC-5: a negative assertion on the section text.
        self.assertEqual(stale_split_defects(self.section), [])

    def test_the_restoration_list_names_both_targets_lists(self):
        item = _block_with(self.section, "**復元**は")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "最終パスの訂正の対象は `violations` に挙がったタスク",
                    "feature-docs の訂正の対象は `targets` に挙がったタスク",
                ),
            ),
            [],
        )

    # negative proofs
    def test_negative_a_split_without_the_unresolved_condition_is_rejected(self):
        forged = _replace_flexible(
            self.block, "ただし、未解決の判定が 1 つもないときに限る。", ""
        )
        self.assertIn(
            "ただし、未解決の判定が 1 つもないときに限る", split_defects(forged)
        )

    def test_negative_a_split_without_the_final_path_remaining_rule_is_rejected(self):
        forged = self.block.replace("`final_path_remaining`", "`@@`")
        self.assertNotEqual(forged, self.block)
        self.assertIn(
            "`final_path_remaining` が false のとき最後の訂正になる",
            split_defects(forged),
        )

    def test_negative_a_split_without_the_none_case_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "feature-docs の訂正の対象のタスクの項目と step の項目を、まとめて",
            "",
        )
        self.assertIn(
            "`none` を返したときは、feature-docs の訂正の対象のタスクの項目と step の項目を、"
            "まとめて 1 回の Write と 1 回のコミットで書く",
            split_defects(forged),
        )

    def test_negative_a_copy_whose_non_last_write_still_writes_task_items_is_rejected(self):
        # The patch-only statement removed: the non-last Write is left free to
        # write the task-level items.
        forged = _replace_flexible(
            self.block,
            "評価の最後でない訂正の Write は、その訂正のパッチだけを書く。",
            "",
        )
        self.assertNotEqual(forged, self.block)
        self.assertIn(
            "評価の最後でない訂正の Write は、その訂正のパッチだけを書く",
            split_defects(forged),
        )

    def test_negative_a_copy_that_writes_the_journal_line_in_the_non_last_write_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "`tasks.{T}.routeback_failed_journal_line` は書かない",
            "`tasks.{T}.routeback_failed_journal_line` も書く",
        )
        self.assertIn(
            "`tasks.{T}.routeback_failed_journal_line` は書かない",
            split_defects(forged),
        )

    def test_negative_a_copy_that_sets_the_targets_pending_in_the_non_last_write_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "対象の `tasks.{T}.status` は `failed` のままにし",
            "対象の `tasks.{T}.status` を `pending` にし",
        )
        self.assertIn(
            "対象の `tasks.{T}.status` は `failed` のままにし",
            split_defects(forged),
        )

    def test_negative_a_copy_without_the_nothing_written_rule_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "未解決の判定があるときは、タスクの項目も step の項目も、復元の項目を 1 つも書かない。",
            "",
        )
        self.assertIn(
            "未解決の判定があるときは、タスクの項目も step の項目も、復元の項目を 1 つも書かない",
            split_defects(forged),
        )

    def test_negative_a_copy_without_the_last_write_rule_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "復元の項目はすべて、評価の最後の訂正の Write に、まとめて入れる",
            "復元の項目は、訂正ごとに書く",
        )
        self.assertIn(
            "復元の項目はすべて、評価の最後の訂正の Write に、まとめて入れる",
            split_defects(forged),
        )

    def test_negative_the_pre_change_split_text_is_rejected(self):
        defects = split_defects(PRE_CHANGE_SPLIT_REGION)
        self.assertNotEqual(defects, [])
        for phrase in (
            "評価の最後でない訂正の Write は、その訂正のパッチだけを書く",
            "復元の項目はすべて、評価の最後の訂正の Write に、まとめて入れる",
            "評価のすべての訂正の対象について書く",
            "未解決の判定があるときは、タスクの項目も step の項目も、復元の項目を 1 つも書かない",
            "`none` を返したときは、feature-docs の訂正の対象のタスクの項目と step の項目を、"
            "まとめて 1 回の Write と 1 回のコミットで書く",
        ):
            self.assertIn(phrase, defects)

    def test_negative_the_pre_change_text_holds_the_stale_per_correction_wording(self):
        self.assertEqual(
            stale_split_defects(PRE_CHANGE_SPLIT_REGION),
            list(STALE_PER_CORRECTION_PHRASES),
        )

    def test_negative_the_pre_change_interruption_paragraph_is_rejected(self):
        defects = interruption_defects(PRE_CHANGE_SPLIT_REGION)
        self.assertIn("対象のタスクはどれも `status` が `failed` のまま", defects)
        self.assertIn(
            "最終パスの判定は、それらのタスクを失敗したタスクとして選ぶ", defects
        )
        self.assertIn("最終パスの訂正が未解決で終わった場合", defects)

    def test_negative_an_interruption_paragraph_without_the_failed_selection_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "最終パスの判定は、それらのタスクを失敗したタスクとして選ぶ。",
            "",
        )
        self.assertIn(
            "最終パスの判定は、それらのタスクを失敗したタスクとして選ぶ",
            interruption_defects(forged),
        )

    def test_negative_an_interruption_paragraph_without_the_kept_status_is_rejected(self):
        forged = _replace_flexible(
            self.block,
            "対象のタスクはどれも `status` が `failed` のままで、",
            "",
        )
        self.assertIn(
            "対象のタスクはどれも `status` が `failed` のまま",
            interruption_defects(forged),
        )

    def test_negative_item_9_without_the_patch_only_statement_is_rejected(self):
        item = _block_with(self.section, "成果物のコミットを作った後")
        forged = _replace_flexible(
            item,
            "評価の最後でない訂正の Write は、パッチだけを運ぶ。",
            "",
        )
        self.assertIn(
            "評価の最後でない訂正の Write は、パッチだけを運ぶ", item_9_defects(forged)
        )

    def test_negative_the_pre_change_item_9_is_rejected(self):
        defects = item_9_defects(PRE_CHANGE_ITEM_9)
        self.assertIn(
            "評価の最後でない訂正の Write は、パッチだけを運ぶ", defects
        )
        self.assertIn(
            "Write が運ぶ復元は、下記の復元の分割がその Write に割り当てるものである",
            defects,
        )
        # The pinned sentence itself was already there before the change.
        self.assertNotIn("パッチと復元を 1 回の Write と 1 回のコミットで書く", defects)

    def test_negative_a_section_that_gains_the_stale_wording_is_rejected(self):
        forged = self.section + "\n" + "その訂正のパッチと一緒に書く。\n"
        self.assertEqual(
            stale_split_defects(forged), ["その訂正のパッチと一緒に"]
        )


class TestAC4UnresolvedJudgment(_SkillTestCase):
    """AC-4."""

    def test_the_unresolved_item_states_every_point(self):
        item = _block_with(self.section, "`none`、`blocked`、または終了コードが 0 以外")
        self.assertEqual(unresolved_item_defects(item), [])

    def test_the_unresolved_item_keeps_the_pinned_rejected_correction_wording(self):
        item = _block_with(self.section, "`none`、`blocked`、または終了コードが 0 以外")
        self.assertEqual(
            _missing_ws(
                item,
                (
                    "検証済みのパッチを得ないまま 13 節が終わったとき",
                    "却下された訂正",
                ),
            ),
            [],
        )

    def test_nothing_written_goes_to_step_b_unchanged(self):
        self.assertStates(
            self.section,
            "どちらの判定も workflow.yaml を変えなかったときは、workflow.yaml を変えずに Step B へ進む",
            "that nothing is written when no judgment changes workflow.yaml",
        )

    # negative proofs
    def test_negative_an_item_without_the_per_judgment_scope_is_rejected(self):
        item = _block_with(self.section, "`none`、`blocked`、または終了コードが 0 以外")
        forged = _replace_flexible(item, "その判定の分の", "")
        self.assertIn(
            "その判定の分の workflow.yaml を変えない", unresolved_item_defects(forged)
        )

    def test_negative_an_item_that_reads_no_errors_is_rejected(self):
        item = _block_with(self.section, "`none`、`blocked`、または終了コードが 0 以外")
        forged = _replace_flexible(item, "その判定の `errors` から", "その判定の標準出力から")
        self.assertIn(
            "その判定の `errors` から読んで名指しする", unresolved_item_defects(forged)
        )


class TestAC1To4UntouchedItemsCoverBothCorrections(_SkillTestCase):
    """The untouched-items paragraph covers both corrections."""

    def test_the_untouched_paragraph_covers_both_corrections(self):
        block = _block_with(self.section, "対象タスクの worktree とブランチには触れない")
        self.assertEqual(
            _missing_ws(
                block,
                (
                    "マージ済みのタスクには触れない",
                    "未コミットの変更がある worktree は破棄しない",
                    "この 3 文は、2 つの訂正のどちらにも当てはまる",
                ),
            ),
            [],
        )

    def test_negative_the_pre_change_paragraph_does_not_cover_both(self):
        pre_change = (
            "対象タスクの worktree とブランチには触れない。マージ済みのタスクには触れない。\n"
            "未コミットの変更がある worktree は破棄しない。"
        )
        self.assertFalse(_contains(pre_change, "2 つの訂正のどちらにも当てはまる"))


class TestStepA6ScopeNonVacuity(unittest.TestCase):
    """The section extraction fails loudly instead of matching nothing."""

    def test_extraction_rejects_a_document_without_the_heading(self):
        with self.assertRaises(AssertionError):
            _step_a6_section("## Step A.5\n\n" + STEP_B_HEADING + "\n")

    def test_extraction_stops_at_the_step_b_heading(self):
        extracted = _step_a6_section(
            STEP_A6_HEADING + "\nin scope\n\n" + STEP_B_HEADING + "\nout of scope\n"
        )
        self.assertIn("in scope", extracted)
        self.assertNotIn("out of scope", extracted)

    def test_a_phrase_outside_the_section_does_not_satisfy_a_check(self):
        # The feature-docs script named only after Step B does not count.
        doc = (
            STEP_A6_HEADING
            + "\ntext\n\n"
            + STEP_B_HEADING
            + "\n"
            + FD_SCRIPT
            + "\n"
        )
        self.assertNotIn(FD_SCRIPT, _step_a6_section(doc))


# ---------------------------------------------------------------------------
# create-plan-phase.md section 13
# ---------------------------------------------------------------------------


class _CreatePlanTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)
        cls.sub = _subsection(cls.text)


class TestAC5Section13Subsection(_CreatePlanTestCase):
    """AC-5."""

    def test_exactly_one_subsection_heading(self):
        self.assertEqual(len(_heading_offsets(self.text, SUBSECTION_HEADING)), 1)

    def test_section_13_is_still_the_last_h2_and_holds_the_subsection(self):
        h2 = [
            (o, line.rstrip("\n"))
            for o, line in _lines_outside_fences(self.text)
            if line.startswith("## ")
        ]
        self.assertEqual(h2[-1][1], SECTION_13_HEADING)
        self.assertTrue(h2[-2][1].startswith("## 12. "), h2[-2][1])
        self.assertEqual([t for _, t in h2].count(SECTION_13_HEADING), 1)
        sub_at = _heading_offsets(self.text, SUBSECTION_HEADING)[0]
        self.assertGreater(sub_at, h2[-1][0])

    def test_section_13_has_no_other_h3(self):
        h3 = [
            line.rstrip("\n")
            for o, line in _lines_outside_fences(self.text)
            if line.startswith("### ")
            and o > _heading_offsets(self.text, SECTION_13_HEADING)[0]
        ]
        self.assertEqual(h3, [SUBSECTION_HEADING])

    def test_the_subsection_follows_the_existing_paragraphs(self):
        sub_at = _heading_offsets(self.text, SUBSECTION_HEADING)[0]
        before = self.text[: sub_at]
        section_13 = before[_heading_offsets(self.text, SECTION_13_HEADING)[0] :]
        positions = [section_13.find(label) for label in SECTION_13_LABELS]
        self.assertTrue(all(p >= 0 for p in positions), positions)
        self.assertEqual(positions, sorted(positions))

    def test_the_subsection_uses_no_bold_label_section_13_already_uses(self):
        for label in SECTION_13_LABELS:
            self.assertNotIn(label, self.sub)

    def test_the_subsection_states_each_design_point(self):
        self.assertEqual(subsection_defects(self.sub), [])

    def test_the_subsection_does_not_restate_the_naming_regex(self):
        self.assertNotIn("REPORT|SUMMARY", self.sub)

    def test_the_subsection_has_no_gate_id_shaped_token(self):
        self.assertEqual(gate_id_shaped_tokens(self.sub), [])

    def test_the_subsection_has_no_home_directory_path_or_notion_url(self):
        self.assertIsNone(re.search(r"/home/[A-Za-z0-9_.-]+/", self.sub))
        self.assertNotIn("notion.so", self.sub)

    def test_the_existing_section_13_paragraphs_are_unchanged_in_wording(self):
        # The pinned paragraphs of tests/test_final_path_correction_docs.py
        # stay in section 13 ahead of the subsection.
        sub_at = _heading_offsets(self.text, SUBSECTION_HEADING)[0]
        head = self.text[_heading_offsets(self.text, SECTION_13_HEADING)[0] : sub_at]
        self.assertEqual(
            _missing_norm(
                head,
                (
                    "`scripts/report-name-entry.py` returns `dispatch`",
                    "`planning_inputs.path_correction`",
                    "`tasks/` in `allowed_write_roots`",
                    "an interrupted correction restarts from Step A.6",
                    "the worker's writes are discarded",
                    "cannot leave corrected `files` with `implement: failed`",
                ),
            ),
            [],
        )

    # negative proofs
    def test_negative_extraction_rejects_a_document_without_the_subsection(self):
        with self.assertRaises(AssertionError):
            _subsection("## 13. Final-path correction dispatch\n\ntext\n")

    def test_negative_extraction_rejects_a_document_with_two_subsections(self):
        doc = SUBSECTION_HEADING + "\na\n\n" + SUBSECTION_HEADING + "\nb\n"
        with self.assertRaises(AssertionError):
            _subsection(doc)

    def test_negative_a_subsection_without_the_grant_rule_is_rejected(self):
        forged = self.sub.replace("the grant rule of section 4", "an unspecified rule")
        self.assertIn(
            "A stage-1 request result is handled by the grant rule of section 4",
            subsection_defects(forged),
        )

    def test_negative_a_subsection_that_keeps_the_writes_is_rejected(self):
        forged = self.sub.replace(
            "the worker's writes are discarded", "the worker's writes are kept"
        )
        self.assertIn("the worker's writes are discarded", subsection_defects(forged))

    def test_negative_a_gate_id_shaped_token_is_detected(self):
        self.assertEqual(
            gate_id_shaped_tokens("see `create-plan.example-gate` here"),
            ["create-plan.example-gate"],
        )
        self.assertEqual(
            gate_id_shaped_tokens("see `phase-state/create-plan.yaml` here"), []
        )


class TestAC6ForbiddenWords(_CreatePlanTestCase):
    """AC-6: none of the forbidden words from the section 12 heading to the
    end of create-plan-phase.md."""

    def test_no_forbidden_word_from_section_12_to_the_end(self):
        self.assertEqual(forbidden_word_defects(_from_section_12(self.text)), [])

    # negative proofs
    def test_negative_a_forbidden_word_in_the_subsection_is_detected(self):
        for word in ("excluded", "subtract", "ignore", "除外", "SUPERSET"):
            forged = _from_section_12(self.text) + "\n" + word + "\n"
            self.assertNotEqual(forbidden_word_defects(forged), [], word)

    def test_negative_a_forbidden_word_inside_the_subsection_text_is_detected(self):
        sub = _replace_flexible(
            self.sub, "cited here and not restated", "nothing is ignored here"
        )
        self.assertNotEqual(sub, self.sub)
        self.assertEqual(forbidden_word_defects(self.sub), [])
        self.assertNotEqual(forbidden_word_defects(sub), [])

    def test_negative_the_scope_starts_at_the_section_12_heading(self):
        with self.assertRaises(AssertionError):
            _from_section_12("## 13. Final-path correction dispatch\n")


if __name__ == "__main__":
    unittest.main()
