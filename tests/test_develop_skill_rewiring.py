"""Tests for task0012: rewiring `em-workflow/skills/develop/SKILL.md` so
create-spec / design / create-plan run through phase protocols and Task
dispatch, the verify rework branches reference the rework synthesis SSOT,
and legacy features get their `project.design_system` backfilled before a
design-system-dependent step begins.

Covers task0012 Acceptance Criteria
(feature-docs/agent-separation/tasks/task0012.md):

- AC-1: the step table contains no instruction to read an agent definition
  and follow it inline, for any step.
- AC-2: the design step is dispatched as a Task with the designer subagent
  type, preceded by the design-system cross-product check.
- AC-3: the cross-product check aborts on both inconsistent combinations and
  runs the reclassification gate for the recorded-none-with-tokens case,
  resuming from the same step without changing its status.
- AC-4: both verify rework branches reference the rework synthesis SSOT and
  the rework-planner instead of describing synthesis inline, and retain
  their existing interactive and batch decision behaviour.
- AC-5: the backfill branch sits between step selection and the in-progress
  update, restarts step selection after completing, and states the
  rationale for that ordering.
- AC-6: the `completed_at_commit` wording expresses the normative rule
  without changing its meaning, and the exit-4 recovery discipline is
  retained.

This is a documentation task (Test Notes: verification is by structural /
textual assertion over the markdown), following the pattern established by
tests/test_rework_synthesis_contract.py (task0004) and
tests/test_review_implement_develop_lock_contracts.py.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

# The exact wording the pre-task0012 step table used for create-spec /
# design / create-plan: "Read an agent definition and follow it inline".
INLINE_AGENT_PHRASE = "インラインで従う"

# The deleted create-spec agent's file name (agents/requirements-spec-creator.md,
# removed by task0013 after task0009 / task0011 create its replacements).
# task0012's own edge case: no residual reference may remain in this file,
# even though the repository-wide sweep belongs to task0013.
DELETED_AGENT_NAME = "requirements-spec-creator"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class TestNoInlineAgentDefinitionWording(unittest.TestCase):
    """AC-1 + Test Notes: the inline-execution phrase does not occur
    anywhere in the file, and no residual reference to the deleted
    create-spec agent name survives either."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_inline_agent_definition_phrase_is_absent(self):
        self.assertNotIn(INLINE_AGENT_PHRASE, self.text)

    def test_deleted_create_spec_agent_name_is_absent(self):
        self.assertNotIn(DELETED_AGENT_NAME, self.text)

    def test_create_spec_and_create_plan_point_at_phase_protocols(self):
        self.assertIn("references/phases/create-spec-phase.md", self.text)
        self.assertIn("references/phases/create-plan-phase.md", self.text)

    def test_design_row_points_at_task_dispatch_branch(self):
        step_table_start = self.text.index("| step | 実行方法 |")
        step_table_end = self.text.index("### design ステップ分岐")
        table = self.text[step_table_start:step_table_end]
        design_row = next(
            line for line in table.splitlines() if line.startswith("| design |")
        )
        self.assertIn("design ステップ分岐", design_row)
        self.assertNotIn("agents/designer.md", design_row)


class TestDesignStepDispatchAndCrossProductCheck(unittest.TestCase):
    """AC-2 + AC-3: the design step branch performs the design-system
    cross-product check immediately before dispatching the designer Task,
    aborts on both inconsistent combinations, and runs the reclassification
    gate (resuming without changing status) for the none-with-tokens case."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(
            cls.text, "### design ステップ分岐", "### verify フェーズ"
        )

    def test_designer_subagent_type_dispatched_as_task(self):
        self.assertIn(
            'Task(subagent_type="em-workflow:designer")', self.section
        )

    def test_cross_product_check_precedes_task_dispatch(self):
        check_idx = self.section.index("designer-contract.md")
        dispatch_idx = self.section.index(
            'Task(subagent_type="em-workflow:designer")'
        )
        self.assertLess(
            check_idx,
            dispatch_idx,
            "the cross-product check must be described before the Task "
            "dispatch line",
        )

    def test_none_with_tokens_case_runs_reclassification_gate(self):
        self.assertIn("`kind: none`", self.section)
        self.assertIn("再分類ゲート", self.section)

    def test_reclassification_gate_resumes_without_changing_status(self):
        self.assertIn("事前条件から再開する", self.section)
        self.assertIn("status は\n     変更しない", self.section)

    def test_em_workflow_yaml_missing_html_present_case_aborts(self):
        self.assertIn(
            "`kind: em_workflow` かつ yaml が無く html だけ実在する場合",
            self.section,
        )
        self.assertIn("不整合", self.section)

    def test_both_inconsistent_combinations_are_distinct_from_normal_path(self):
        # Guard against collapsing the two abort rows into one branch: both
        # `kind: none` and `kind: em_workflow` combinations must appear
        # ahead of the normal-path write_policy construction.
        none_idx = self.section.index("`kind: none`")
        em_workflow_idx = self.section.index(
            "`kind: em_workflow` かつ yaml が無く html だけ実在する場合"
        )
        normal_path_idx = self.section.index("`designer-contract.md` の対応表どおりに")
        self.assertLess(none_idx, normal_path_idx)
        self.assertLess(em_workflow_idx, normal_path_idx)


class TestVerifyReworkBranchesReferenceSSOT(unittest.TestCase):
    """AC-4: both the interactive and the batch verify failure branches
    reference the rework synthesis SSOT and the rework-planner instead of
    describing synthesis inline, and retain the existing interactive
    three-way choice and the batch counter-capped auto-rework."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(
            cls.text, "### verify フェーズ", "### retrospect フェーズ"
        )

    def _branches(self):
        batch_idx = self.section.index("（batch: 確認せず自動 rework。")
        return self.section[:batch_idx], self.section[batch_idx:]

    def test_ssot_referenced_from_both_branches(self):
        interactive, batch = self._branches()
        self.assertIn(
            "rework-task-synthesis.md",
            interactive,
            "interactive verify rework branch must reference the SSOT",
        )
        self.assertIn(
            "rework-task-synthesis.md",
            batch,
            "batch verify rework branch must reference the SSOT",
        )

    def test_rework_planner_is_the_named_worker(self):
        self.assertIn("rework-planner", self.section)
        self.assertIn(
            'Task(subagent_type="em-workflow:rework-planner")', self.section
        )

    def test_synthesis_mechanics_are_not_restated_inline(self):
        # Guard against the old wording resurfacing: pre-task0012 the batch
        # branch described synthesis inline ("failed_items から rework
        # タスクを合成"). That phrasing must be gone now that both branches
        # point at the SSOT.
        self.assertNotIn("failed_items から rework タスクを合成", self.section)

    def test_old_thin_batch_mode_reference_is_replaced(self):
        normalized = re.sub(r"\s+", " ", self.section)
        self.assertNotIn(
            'batch-mode.md「Rework task synthesis」', normalized
        )

    def test_interactive_three_way_choice_is_retained(self):
        interactive, _batch = self._branches()
        self.assertIn("AskUserQuestion", interactive)
        self.assertIn("implement へ rework", interactive)
        self.assertIn("review へ", interactive)
        self.assertIn("中断", interactive)

    def test_batch_counter_cap_is_retained(self):
        _interactive, batch = self._branches()
        self.assertIn("batch.verify_rework_count == 0", batch)
        self.assertIn("カウンタを +1", batch)
        self.assertIn("既に 1 以上なら", batch)
        self.assertIn("`failed` のまま報告して停止", batch)

    def test_pending_rework_task_invariant_is_stated(self):
        self.assertIn(
            "新しい\n   rework task が 1 件以上 workflow.yaml へ登録されるまで戻さない",
            self.section,
        )


class TestBackfillBranchOrderingAndRationale(unittest.TestCase):
    """AC-5: the backfill branch sits between step selection and the
    in-progress update, restarts step selection after completing, and
    states the rationale for that ordering."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b_section = _section(
            cls.text, "## Step B: 自走ループ", "### design ステップ分岐"
        )

    def test_backfill_section_precedes_in_progress_update_instruction(self):
        backfill_idx = self.step_b_section.index("**design-system backfill**")
        in_progress_update_idx = self.step_b_section.index(
            "以上を経て、step 実行前にその step を `in_progress` に更新し"
        )
        self.assertLess(
            backfill_idx,
            in_progress_update_idx,
            "the backfill branch must be described before the in-progress "
            "update instruction",
        )

    def test_backfill_targets_design_and_create_plan_only(self):
        self.assertIn(
            "選択した step が `design` または `create-plan` で、かつ workflow.yaml に\n"
            "   `project.design_system` が未設定なら",
            self.step_b_section,
        )

    def test_backfill_restarts_step_selection_after_completing(self):
        self.assertIn(
            "workflow.yaml を**読み直して step 特定からやり直す**",
            self.step_b_section,
        )

    def test_backfill_does_not_change_status_before_restart(self):
        self.assertIn(
            "（その step の status はまだ変更しない）", self.step_b_section
        )

    def test_rationale_for_ordering_is_stated(self):
        self.assertIn(
            "**`in_progress` へ先に更新しない理由**", self.step_b_section
        )
        self.assertIn("再開判定では扱えなくなるため", self.step_b_section)


class TestCommitSemanticsWordingAndExit4Recovery(unittest.TestCase):
    """AC-6: the `completed_at_commit` wording expresses the normative rule
    (rule R2) without changing its meaning, and the exit-4 recovery
    discipline is retained."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_completed_at_commit_states_normative_rule(self):
        self.assertIn(
            "その step の `status` を `completed` へ更新するコミットを作る**直前の HEAD**",
            self.text,
        )
        self.assertIn("規則 R2", self.text)

    def test_completed_at_commit_meaning_is_unchanged(self):
        self.assertIn(
            "（規則 R2。全 7 step に適用し、意味は変更しない）。", self.text
        )

    def test_exit4_recovery_discipline_is_retained(self):
        self.assertIn("exit-4 リカバリ", self.text)
        self.assertIn(
            "`commit-docs.sh` を 1 回だけ再試行する。2 回目も", self.text
        )
        self.assertIn("無限リトライ\nしない", self.text)


class TestRetainedElementsSurviveTheRewrite(unittest.TestCase):
    """Test Notes: the retained elements (Step 0 gate, approval gate, exit-4
    recovery, completion choices) are still present."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def test_step_0_git_setup_gate_present(self):
        self.assertIn(
            "## Step 0: git-setup ゲート（workflow 開始時に毎回）", self.text
        )

    def test_step_a5_approval_gate_present(self):
        self.assertIn(
            "## Step A.5: コマンド承認ゲート（workflow.yaml が存在するとき必ず）",
            self.text,
        )

    def test_step_c_completion_choices_present(self):
        self.assertIn("にマージ", self.text)
        self.assertIn("ブランチを残す", self.text)
        self.assertIn("PR を作成", self.text)


class TestDevelopSkillRewiringAssertionsCanFail(unittest.TestCase):
    """Proof that the structural checks above fail meaningfully, per the
    tdd-testing discipline (a test that can never fail is not a test)."""

    def test_inline_agent_phrase_matcher_detects_the_old_wording(self):
        fake_text = (
            "| create-spec | `agents/requirements-spec-creator.md` を Read "
            "してその指示にインラインで従う |"
        )
        self.assertIn(INLINE_AGENT_PHRASE, fake_text)

    def test_missing_ssot_reference_is_detected(self):
        fake_branch = "no reference here, just synthesize inline"
        self.assertNotIn("rework-task-synthesis.md", fake_branch)

    def test_wrong_ordering_is_detected(self):
        fake_section = "in_progress 更新の指示\n...\nbackfill 判定"
        backfill_idx = fake_section.index("backfill")
        in_progress_idx = fake_section.index("in_progress")
        self.assertGreater(backfill_idx, in_progress_idx)


if __name__ == "__main__":
    unittest.main()
