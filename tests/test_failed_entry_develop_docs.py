"""Document contract tests for task0007 (subagent-report-write-block): the
develop skill's `## Step A.6: failed からの入口` section.

Covers task0007 Acceptance Criteria
(feature-docs/subagent-report-write-block/tasks/task0007.md, TS-14):

- AC-1: the section sits between Step A.5 and Step B and states the
  judgment at the start of a re-run naming the feature, once per
  invocation, on Step A's existing-feature branch.
- AC-2: the section states the entry is not taken inside the failed run.
- AC-3: the section states the entry precedes stop condition 3 even when
  `failed_kind` is `decision`, that a batch re-run uses the same entry,
  and that no gate is added.
- AC-4: the section states that when the FR5 conditions are not met,
  including a rejected correction, workflow.yaml is not changed and the
  run stops at stop condition 3.
- AC-5: the section states each restoration item and that the patch and
  the restoration are one Write and one commit.
- AC-6: the section states the target's worktree and branch and merged
  tasks are not touched and uncommitted changes are not discarded.

Every assertion is scoped to the text between the two headings, so wording
elsewhere in the document cannot satisfy a criterion. The existing tests
locate `## Step A.5` and `## Step B`; this module also pins that both
headings are unchanged. The document cites the report-name rule by its
heading and never contains the FR2 regex (IMPLEMENTATION.md, Conventions).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_PATH = os.path.join(REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md")

STEP_A5_HEADING = "## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）"
STEP_A6_HEADING = "## Step A.6: failed からの入口"
STEP_B_HEADING = "## Step B: 自走ループ"

FAILED_KIND_BLOCK_ANCHOR = (
    "**batch: implement の failed_kind による自動再開**（FR6, FR7, FR8）:"
)
FAILED_KIND_BLOCK_END = "**Tier 削減表**"

# The FR2 pattern source and its table-escaped form must never appear in the
# develop skill: documents other than plan-writing cite the rule heading.
FR2_REGEX_SOURCE = r"^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$"


def _read(path):
    if not os.path.isfile(path):
        raise AssertionError(f"expected file to exist: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_ws(text):
    # The document hard-wraps Japanese prose without a space at the break
    # point, so phrases are matched after stripping all whitespace (the
    # convention of tests/test_failed_kind_stop_condition.py).
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


def _heading_positions(text, heading):
    return [m.start() for m in re.finditer(r"^" + re.escape(heading), text, re.M)]


def _section(text):
    starts = _heading_positions(text, STEP_A6_HEADING)
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one {STEP_A6_HEADING!r} heading, found {len(starts)}"
        )
    start = starts[0]
    ends = [p for p in _heading_positions(text, STEP_B_HEADING) if p > start]
    if not ends:
        raise AssertionError(f"{STEP_B_HEADING!r} must follow Step A.6")
    return text[start : ends[0]]


class _SectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text)

    def assertSectionStates(self, phrase, why):
        self.assertTrue(
            _contains(self.section, phrase),
            f"Step A.6 must state {why}: expected {phrase!r}",
        )


class TestAC1Placement(_SectionTestCase):
    """AC-1: placement and the once-per-invocation judgment."""

    def test_headings_present_once_and_in_order(self):
        a5 = _heading_positions(self.text, STEP_A5_HEADING)
        a6 = _heading_positions(self.text, STEP_A6_HEADING)
        b = _heading_positions(self.text, STEP_B_HEADING)
        self.assertEqual(len(a5), 1, "Step A.5 heading must stay unchanged")
        self.assertEqual(len(a6), 1)
        self.assertEqual(len(b), 1, "Step B heading must stay unchanged")
        self.assertLess(a5[0], a6[0])
        self.assertLess(a6[0], b[0])

    def test_states_judgment_at_start_of_rerun_naming_the_feature(self):
        self.assertSectionStates(
            "feature 名を指定した再実行の開始時", "the judgment point"
        )

    def test_states_once_per_invocation(self):
        self.assertSectionStates("1 回の起動につき 1 度だけ", "once per invocation")

    def test_states_existing_feature_branch_after_step_a5(self):
        self.assertSectionStates(
            "Step A の既存 feature の分岐", "the existing-feature branch of Step A"
        )
        self.assertSectionStates("Step A.5 を終えた後", "the position after Step A.5")

    def test_states_script_invocation_with_four_arguments(self):
        for token in (
            "${CLAUDE_PLUGIN_ROOT}/scripts/report-name-entry.py",
            "--workflow",
            "--journal",
            "--target-repo",
            "--base-commit",
        ):
            self.assertIn(token, self.section)

    def test_states_full_commit_id_capture_of_integration_tip(self):
        self.assertSectionStates(
            "integration の先端を完全なコミット ID として捕捉",
            "the full commit ID capture of the integration tip",
        )

    def test_states_not_failed_goes_to_step_b(self):
        self.assertSectionStates(
            "`implement` の `status` が `failed` でなければ",
            "the not-failed branch",
        )


class TestAC2NotTakenInsideFailedRun(_SectionTestCase):
    """AC-2: the entry is not taken inside the failed run."""

    def test_states_step_b_never_enters_the_section(self):
        self.assertSectionStates("Step B はこの節に入らない", "that Step B never enters it")

    def test_states_not_taken_inside_the_failed_run(self):
        self.assertSectionStates(
            "失敗した走行の中ではこの入口を取らない",
            "that the entry is not taken inside the failed run",
        )


class TestAC3PrecedenceBatchNoGate(_SectionTestCase):
    """AC-3: precedence over stop condition 3, batch parity, no new gate."""

    def test_states_precedes_stop_condition_3_regardless_of_failed_kind(self):
        self.assertSectionStates("停止条件 3 より前に評価", "the precedence over stop condition 3")
        self.assertSectionStates(
            "`failed_kind` が `decision` でも", "that failed_kind decision does not exclude the entry"
        )

    def test_states_batch_uses_the_same_entry(self):
        self.assertSectionStates(
            "対話実行と batch 実行のどちらでも同じこの入口を使う",
            "that interactive and batch share the entry",
        )

    def test_states_no_new_gate(self):
        self.assertSectionStates(
            "新しい `gate_id` もユーザーへの質問も導入しない", "that no gate is added"
        )

    def test_states_dispatch_runs_section_13_of_create_plan_phase(self):
        self.assertSectionStates(
            "`references/phases/create-plan-phase.md` の 13 節", "the section 13 dispatch"
        )


class TestAC4NotMetFallsThroughToStopCondition3(_SectionTestCase):
    """AC-4: unmet conditions leave workflow.yaml unchanged."""

    def test_states_none_blocked_and_nonzero_exit_leave_workflow_unchanged(self):
        self.assertSectionStates(
            "`none`、`blocked`、または終了コードが 0 以外", "the three non-dispatch results"
        )
        self.assertSectionStates(
            "workflow.yaml を変えずに Step B へ進む", "that workflow.yaml is unchanged"
        )
        self.assertSectionStates("停止条件 3 が発火する", "that stop condition 3 fires")

    def test_states_blocked_report_names_the_failed_condition(self):
        self.assertSectionStates(
            "`blocked` では停止の報告に失敗した条件を名指しする",
            "that the stop report names the failed condition",
        )

    def test_states_rejected_correction_leaves_workflow_unchanged(self):
        self.assertSectionStates(
            "検証済みのパッチを得ないまま 13 節が終わったとき",
            "the no-validated-patch case",
        )
        self.assertSectionStates("却下された訂正", "the rejected correction")


class TestAC5RestorationOneWrite(_SectionTestCase):
    """AC-5: each restoration item, and one Write plus one commit."""

    def test_states_each_restoration_item(self):
        for phrase in (
            "`implement` を `pending` にする",
            "`failed_kind` を null にする",
            "`tasks.{T}.status` を `pending` にする",
            "`tasks.{T}.routeback_failed_journal_line`",
            "`failed_journal_line`",
            "null でないとき",
        ):
            self.assertSectionStates(phrase, "a restoration item")

    def test_states_notes_cleared_by_patch_application(self):
        self.assertSectionStates(
            "`notes` はパッチの適用が消す", "that notes is cleared by the patch"
        )
        self.assertSectionStates(
            "再試行の消費の記録", "the retry-consumption record that notes carries"
        )

    def test_states_restoration_covers_each_violation_task(self):
        self.assertSectionStates("`violations` に挙がった", "the violation-listed tasks")

    def test_states_artifact_commit_then_one_write_and_one_commit(self):
        self.assertSectionStates("成果物のコミットを作った後", "the artifact commit first")
        self.assertSectionStates(
            "パッチと復元を 1 回の Write と 1 回のコミットで書く",
            "that patch and restoration are one Write and one commit",
        )

    def test_artifact_commit_precedes_the_single_write(self):
        artifact = _strip_ws(self.section).index(_strip_ws("成果物のコミットを作った後"))
        write = _strip_ws(self.section).index(
            _strip_ws("パッチと復元を 1 回の Write と 1 回のコミットで書く")
        )
        self.assertLess(artifact, write)


class TestAC6NothingElseTouched(_SectionTestCase):
    """AC-6: worktree, branch, merged tasks and uncommitted changes."""

    def test_states_target_worktree_and_branch_are_not_touched(self):
        self.assertSectionStates(
            "対象タスクの worktree とブランチには触れない", "that the target worktree and branch are untouched"
        )

    def test_states_merged_tasks_are_not_touched(self):
        self.assertSectionStates("マージ済みのタスクには触れない", "that merged tasks are untouched")

    def test_states_uncommitted_changes_are_not_discarded(self):
        self.assertSectionStates(
            "未コミットの変更がある worktree は破棄しない",
            "that uncommitted changes are not discarded",
        )


class TestStepBPointer(unittest.TestCase):
    """The Step B failed_kind block gains a pointer to Step A.6 and keeps its text."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        start = cls.text.index(FAILED_KIND_BLOCK_ANCHOR)
        cls.block = cls.text[start : cls.text.index(FAILED_KIND_BLOCK_END, start)]

    def test_block_points_at_step_a6(self):
        self.assertTrue(_contains(self.block, "Step A.6"))

    def test_block_numbered_steps_are_kept(self):
        for marker in (
            "1. `failed_kind` を読む。",
            "2. 値が要ユーザー判断を示す場合",
            "3. 値が外部要因を示し、かつ対話実行の場合",
            "4. 値が外部要因を示し、かつ batch 実行の場合",
            "5. 実行済み回数が cap に達している場合",
            "6. それ以外の場合",
        ):
            self.assertTrue(_contains(self.block, marker), marker)


class TestNoRestatedRule(unittest.TestCase):
    """The document cites the rule by heading and never contains the FR2 regex."""

    def test_skill_does_not_contain_the_fr2_regex(self):
        text = _read(SKILL_PATH)
        self.assertNotIn(FR2_REGEX_SOURCE, text)
        self.assertNotIn(FR2_REGEX_SOURCE.replace("|", "\\|"), text)


class TestSectionScopeNonVacuity(unittest.TestCase):
    """The section extraction fails loudly instead of matching nothing."""

    def test_section_extraction_rejects_a_document_without_the_heading(self):
        with self.assertRaises(AssertionError):
            _section("## Step A.5\n\n## Step B: 自走ループ\n")

    def test_section_extraction_stops_at_the_step_b_heading(self):
        synthetic = (
            STEP_A6_HEADING + "\nin scope\n\n" + STEP_B_HEADING + "\nout of scope\n"
        )
        extracted = _section(synthetic)
        self.assertIn("in scope", extracted)
        self.assertNotIn("out of scope", extracted)


if __name__ == "__main__":
    unittest.main()
