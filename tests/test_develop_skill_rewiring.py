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

task0022 rework (round2.yaml finding bs3 — correcting round1's "presenter"
criterion to gate-identifier presence) adds:

- AC-5 (task0022.md): the `--batch` argument-processing entry states the
  jurisdiction split as gate-identifier presence, not as "packet gates vs
  everything else routed by which step presents them" — and so no longer
  contradicts Step A.5's own `create-spec.command-approval` routing to
  `batch-policies.yaml`.

task0001 (create-plan-status-conflict) adds:

- AC-1: Step B states that create-plan is the sole step exempt from the
  pre-dispatch `in_progress` update, and that it advances to `completed`
  only after the phase completes (patch applied and commit succeeded).
- AC-2: Step B states that the exemption preserves the entry status, and
  names both entry statuses (`pending`, `needs_update`) as what the planner
  is dispatched with.
- AC-3: the exemption carries both reasons (the `replace_all`
  permission-condition reason and the `phase-state/create-plan.yaml`
  recovery reason) and cites `references/workflow-patch.md` for the
  permission conditions without reproducing that document's condition text.

task0004 (create-plan-status-conflict rework round 1, finding
`cmp-stopcond3-universal-claim`) adds:

- AC-1: the universal claim sentence ("stop condition 3's `needs_update`
  carve-out means any step other than create-plan") no longer occurs
  anywhere in the file.
- AC-2: Step B states the generalized carve-out — a `needs_update` set by a
  transition whose owning phase protocol prescribes automatic re-entry is
  not a stop-condition-3 stop reason, and the phase runs with that status
  unchanged.
- AC-3: the block enumerates both qualifying transitions, citing
  `references/implement-phase.md` for the create-plan route back to
  planning and both `references/rework-task-synthesis.md` and
  `references/contracts/rework-planner-contract.md` for the create-spec
  spec-change transition.
- AC-4: the block states the negative case (the `needs_update` set by
  `create-spec.stalled`'s abort option still stops the loop) and the
  discriminator that separates it from the spec-change case (an unconsumed
  record in `phase-state/rework.yaml`).
- AC-5: bullet 3 of the "ターンを終わらせていい唯一の条件" list is
  restated in generalized terms and points at the Step B block.
- AC-6: the create-plan `in_progress` exemption remains create-plan-only.
- AC-7: the spec-change transition is cited, never restated with per-step
  status assignments.
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

# task0001 (create-plan-status-conflict): the bold-label marker that opens
# the create-plan `in_progress` exemption block, placed after the generic
# pre-dispatch `in_progress` sentence so it narrows rather than replaces it
# (IMPLEMENTATION.md D2).
CREATE_PLAN_EXEMPTION_MARKER = "**例外: create-plan は先に `in_progress` を経ない**"

# The exemption's own rationale label, distinct from the design-system
# backfill's "`in_progress` へ先に更新しない理由" label so the two "why we
# skip `in_progress`" explanations in this section are never confused for
# one another.
CREATE_PLAN_EXEMPTION_RATIONALE_LABEL = "**create-plan が `in_progress` を経ない理由**"

# The paragraph that immediately follows the exemption block in Step B,
# used as the section's end marker.
STEP_B_COMMIT_DISCIPLINE_MARKER = (
    "workflow.yaml か feature-docs/ 配下のドキュメントを Write/Edit するたび"
)

# workflow-patch.md's `replace_all` permission-condition sentences (5.5.1 /
# application rule 5). Step B must cite this document, never reproduce
# these sentences (S3 rule-5 citation discipline, IMPLEMENTATION.md).
WORKFLOW_PATCH_CONDITION_SENTENCES = (
    "`tasks` is empty, OR every existing task's `status` is `pending`",
    "the `create-plan` step is `pending` (first planning pass)",
    "the `create-plan` step is `needs_update` (an explicit re-plan)",
)

# task0004 (rework round 1, finding cmp-stopcond3-universal-claim): the
# label opening the stop-condition-3 carve-out block, already distinct from
# both CREATE_PLAN_EXEMPTION_RATIONALE_LABEL and the backfill-ordering
# label ("`in_progress` へ先に更新しない理由"), so it is reused rather than
# replaced by a new label.
STOP_CONDITION_3_LABEL = "**停止条件 3 との優先関係**"

# The universal claim round 1 added and this rework removes: it makes the
# create-spec spec-change re-entry (which also sets a `needs_update`)
# unreachable because it reads as scoping the carve-out to "any step other
# than create-plan" being covered, when create-plan is in fact the ONE step
# explicitly named as covered by the old sentence.
UNIVERSAL_CLAIM_SENTENCE = (
    "停止条件 3 が意味する「ユーザー介入が必要な `needs_update`」は "
    "create-plan 以外の step を指す"
)


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): Japanese prose in
    # this document hard-wraps without a space at the break point, so
    # collapsing to a single space would inject whitespace the source
    # never had and break substring matches that span a wrap.
    return re.sub(r"\s+", "", text)


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


class TestBatchArgumentJurisdictionByGateIdentifier(unittest.TestCase):
    """task0022 AC-5 (round2.yaml bs3): the `--batch` argument-processing
    entry states the gate-resolution jurisdiction as gate-identifier
    presence, never as "who presents the gate", and no longer contradicts
    Step A.5's own routing of `create-spec.command-approval` to
    `batch-policies.yaml`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, "## 引数処理", "## Step 0")

    def test_jurisdiction_stated_as_gate_id_presence(self):
        self.assertIn("`gate_id` を持つか", self.section)
        self.assertIn("gate_id` を持つゲートは", self.section)
        self.assertIn("gate_id` を\n  一切持たないゲート", self.section)

    def test_jurisdiction_not_stated_as_presenter(self):
        # The old wording routed "Step A / A.5 / 各フェーズ / Step C" as a
        # block to batch-mode.md regardless of gate_id presence. That
        # phrase must be gone.
        self.assertNotIn(
            "それ以外のゲート\n  （Step A / A.5 / 各フェーズ / Step C）は "
            "batch-mode.md の Non-packet",
            self.section,
        )

    def test_criterion_phrase_present(self):
        self.assertIn("「誰が提示するか」ではなく「`gate_id` を持つか」", self.section)

    def test_artifact_overwrite_and_command_approval_cited_as_gate_id_examples(self):
        self.assertIn("create-spec.command-approval", self.section)
        self.assertIn("{phase}.artifact-overwrite", self.section)

    def test_does_not_contradict_step_a5_command_approval_routing(self):
        step_a5_section = _section(
            self.text,
            "## Step A.5",
            "## Step B",
        )
        self.assertIn("batch-policies.yaml", step_a5_section)
        self.assertIn("create-spec.command-approval", step_a5_section)
        # The argument-processing section must route the SAME gate to the
        # SAME document, not to batch-mode.md's Non-packet table.
        self.assertIn(
            "gate_id` を持つゲートは `references/question-resolution.md` の",
            self.section,
        )


class TestCreatePlanInProgressExemption(unittest.TestCase):
    """task0001 AC-1, AC-2, AC-3: Step B states that create-plan is the sole
    step exempt from the pre-dispatch `in_progress` update, preserves its
    entry status into planner dispatch, and carries both reasons for the
    exemption via a citation (never a restatement) of workflow-patch.md's
    `replace_all` permission conditions."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b_section = _section(
            cls.text, "## Step B: 自走ループ", "### design ステップ分岐"
        )
        cls.exemption_section = _section(
            cls.step_b_section,
            CREATE_PLAN_EXEMPTION_MARKER,
            STEP_B_COMMIT_DISCIPLINE_MARKER,
        )

    def test_exemption_block_follows_the_generic_in_progress_sentence(self):
        # AC-1 placement (IMPLEMENTATION.md D2): the exemption narrows the
        # generic sentence, so it must be described after it.
        generic_idx = self.step_b_section.index(
            "以上を経て、step 実行前にその step を `in_progress` に更新し"
        )
        exemption_idx = self.step_b_section.index(CREATE_PLAN_EXEMPTION_MARKER)
        self.assertLess(generic_idx, exemption_idx)

    def test_exemption_names_create_plan_as_the_sole_exempt_step(self):
        # AC-1: create-plan is stated as THE exception, not merely an
        # exception among several.
        self.assertIn("create-plan", self.exemption_section)
        self.assertIn("だけ", self.exemption_section)

    def test_exemption_advances_to_completed_only_after_patch_and_commit(self):
        # AC-1: advances to `completed` only once the phase has finished —
        # the proposed patch applied AND the commit succeeded — and does
        # not advance if either fails.
        self.assertIn("completed", self.exemption_section)
        self.assertIn("規則 R2", self.exemption_section)
        self.assertIn("コミット", self.exemption_section)
        self.assertIn("失敗", self.exemption_section)

    def test_entry_status_preservation_names_both_statuses(self):
        # AC-2: the exemption never overwrites the entry status, and both
        # statuses the planner may be dispatched with are named.
        self.assertIn("`pending`", self.exemption_section)
        self.assertIn("`needs_update`", self.exemption_section)
        self.assertIn("上書きしない", self.exemption_section)

    def test_rationale_label_is_distinct_from_backfill_label(self):
        # Test Notes edge case: the two "why we skip `in_progress`"
        # explanations (backfill, create-plan) must not share a label, or
        # an assertion on the shared label alone could not tell them apart.
        self.assertIn(
            CREATE_PLAN_EXEMPTION_RATIONALE_LABEL, self.exemption_section
        )
        self.assertNotIn(
            "**`in_progress` へ先に更新しない理由**", self.exemption_section
        )

    def test_rationale_cites_workflow_patch_rule_5_without_reproducing_it(self):
        # AC-3: the reference is present; the copied condition text is not.
        self.assertIn("workflow-patch.md", self.exemption_section)
        self.assertIn("適用規則 5", self.exemption_section)
        for sentence in WORKFLOW_PATCH_CONDITION_SENTENCES:
            self.assertNotIn(sentence, self.exemption_section)

    def test_rationale_cites_phase_state_create_plan_recovery(self):
        # AC-3: the second reason — interrupt recovery ownership.
        self.assertIn("phase-state/create-plan.yaml", self.exemption_section)


class TestStopCondition3AutomaticReentryCarveOut(unittest.TestCase):
    """task0004 (rework round 1, finding cmp-stopcond3-universal-claim)
    AC-1 through AC-7: the universal claim that stop condition 3's
    `needs_update` carve-out means "any step other than create-plan" is
    replaced by a generalized carve-out — a `needs_update` set by a
    transition whose owning phase protocol prescribes automatic re-entry is
    not a stop reason — enumerating both qualifying transitions (create-plan
    route back to planning, create-spec spec-change), naming the
    create-spec.stalled abort as the still-stopping negative case, and
    stating the unconsumed phase-state/rework.yaml record as the
    discriminator between the two create-spec `needs_update` meanings."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b_section = _section(
            cls.text, "## Step B: 自走ループ", "### design ステップ分岐"
        )
        cls.carve_out_section = _section(
            cls.step_b_section,
            STOP_CONDITION_3_LABEL,
            CREATE_PLAN_EXEMPTION_RATIONALE_LABEL,
        )

    def test_universal_claim_sentence_is_absent_from_whole_file(self):
        # AC-1: a pure absence assertion over the whole file. Strip all
        # whitespace (not just collapse it) before comparing: the source
        # markdown hard-wraps Japanese prose without inserting spaces at
        # the wrap point, so collapsing whitespace to a single space would
        # itself inject a stray space the original text never had.
        self.assertNotIn(_strip_ws(UNIVERSAL_CLAIM_SENTENCE), _strip_ws(self.text))

    def test_generalized_carve_out_is_stated(self):
        # AC-2
        self.assertIn("自動的に再エントリさせるために", self.carve_out_section)
        self.assertIn("この停止条件の停止理由にしない", self.carve_out_section)
        self.assertIn("保持したまま実行され", self.carve_out_section)

    def test_both_qualifying_transitions_enumerated_with_owning_documents(self):
        # AC-3
        self.assertIn("references/implement-phase.md", self.carve_out_section)
        self.assertIn("route back to planning", self.carve_out_section)
        self.assertIn(
            "references/rework-task-synthesis.md", self.carve_out_section
        )
        self.assertIn(
            "references/contracts/rework-planner-contract.md",
            self.carve_out_section,
        )
        self.assertIn("spec-change", self.carve_out_section)

    def test_enumeration_is_stated_as_exhaustive(self):
        # AC-3 / Design "exhaustive enumeration": guard against a rewrite
        # that lists the two transitions without stating exhaustiveness.
        self.assertIn("網羅的", self.carve_out_section)

    def test_negative_case_still_stops_the_loop(self):
        # AC-4 (negative case)
        self.assertIn("create-spec.stalled", self.carve_out_section)
        self.assertIn("選択肢 3", self.carve_out_section)
        self.assertIn("正真正銘のユーザー介入待ち", self.carve_out_section)

    def test_discriminator_names_unconsumed_rework_yaml_record(self):
        # AC-4 (discriminator)
        self.assertIn("phase-state/rework.yaml", self.carve_out_section)
        self.assertIn("未消費", self.carve_out_section)
        self.assertIn("stable_id", self.carve_out_section)

    def test_bullet_3_is_generalized_and_points_at_the_step_b_block(self):
        # AC-5
        turn_end_section = _section(
            self.text,
            "### ターンを終わらせていい唯一の条件",
            "これらに該当しない限り",
        )
        bullet_3_start = turn_end_section.index("3. ")
        bullet_4_start = turn_end_section.index("4. ")
        bullet_3 = turn_end_section[bullet_3_start:bullet_4_start]
        self.assertNotIn("create-plan", bullet_3)
        self.assertIn(STOP_CONDITION_3_LABEL, bullet_3)

    def test_in_progress_exemption_still_create_plan_only(self):
        # AC-6 regression guard: the neighbouring exemption block (which now
        # sits next to a carve-out block that also discusses create-spec)
        # still names create-plan as the sole step exempt from the
        # pre-dispatch `in_progress` update, and the carve-out block itself
        # says nothing about a second step skipping that update.
        exemption_section = _section(
            self.step_b_section,
            CREATE_PLAN_EXEMPTION_MARKER,
            STEP_B_COMMIT_DISCIPLINE_MARKER,
        )
        self.assertIn("create-plan", exemption_section)
        self.assertIn("だけ", exemption_section)
        self.assertNotIn("in_progress を経ない", self.carve_out_section)
        self.assertNotIn("in_progress に更新", self.carve_out_section)

    def test_spec_change_transition_cited_not_restated_with_per_step_statuses(self):
        # AC-7: the citation is present (checked above); no sentence
        # assigns statuses to implement / review as part of describing the
        # spec-change transition inside this block (create-plan's own
        # status assignment is legitimate — it belongs to the OTHER
        # transition, the create-plan route back to planning, per AC-3).
        self.assertNotIn("implement を", self.carve_out_section)
        self.assertNotIn("review を", self.carve_out_section)


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

    def test_missing_create_plan_exemption_marker_is_detected(self):
        # task0001 AC-1/AC-5: a Step B section without the exemption block
        # must not contain its opening marker.
        fake_section = (
            "以上を経て、step 実行前にその step を `in_progress` に更新し"
            "、フェーズ完了時に `completed` へ更新する。"
        )
        self.assertNotIn(CREATE_PLAN_EXEMPTION_MARKER, fake_section)

    def test_missing_entry_status_preservation_is_detected(self):
        # task0001 AC-2/AC-5: a rewrite that always dispatches create-plan
        # as `in_progress` (dropping entry-status preservation) must fail
        # the `needs_update` presence check.
        fake_section = "create-plan は常に `in_progress` で dispatch される。"
        self.assertNotIn("`needs_update`", fake_section)

    def test_copied_permission_condition_sentence_is_detected(self):
        # task0001 AC-3/AC-5: reproducing workflow-patch.md's condition
        # enumeration instead of citing it must be caught by the
        # assertNotIn checks in TestCreatePlanInProgressExemption.
        fake_section = (
            "the `create-plan` step is `pending` (first planning pass), OR "
            "the `create-plan` step is `needs_update` (an explicit re-plan)"
        )
        self.assertIn(
            "the `create-plan` step is `pending` (first planning pass)",
            fake_section,
        )

    def test_universal_claim_matcher_detects_the_old_wording(self):
        # task0004 AC-1/AC-8: the exact sentence round 1 added must be
        # caught by the assertNotIn check, including when a hard line-wrap
        # splits it mid-sentence the way the real document does.
        fake_text = (
            "停止条件 3 が意味する「ユーザー\n"
            "介入が必要な `needs_update`」は create-plan 以外の step を指す。"
        )
        self.assertIn(_strip_ws(UNIVERSAL_CLAIM_SENTENCE), _strip_ws(fake_text))

    def test_missing_second_transition_citation_is_detected(self):
        # task0004 AC-3/AC-8: a carve-out block naming only the create-plan
        # transition (omitting the rework spec-change transition) must fail
        # the rework-task-synthesis.md presence check.
        fake_section = (
            "route back to planning — `references/implement-phase.md`"
            "（I.2.c）が create-plan を `needs_update` に設定する遷移のみ"
        )
        self.assertNotIn("references/rework-task-synthesis.md", fake_section)

    def test_missing_discriminator_is_detected(self):
        # task0004 AC-4/AC-8: stating the negative case without the
        # unconsumed-record discriminator must fail the phase-state/rework
        # .yaml presence check.
        fake_section = "create-spec.stalled の選択肢 3 は停止条件 3 を発火する。"
        self.assertNotIn("phase-state/rework.yaml", fake_section)

    def test_bullet_3_still_naming_create_plan_is_detected(self):
        # task0004 AC-5/AC-8: a bullet 3 that still names create-plan
        # specifically (instead of the generalized carve-out) must fail
        # the create-plan-absence check.
        fake_bullet_3 = (
            "3. ある step の status が `failed` / `needs_update`（ただし "
            "create-plan step が `needs_update` のまま dispatch される "
            "Step B の例外中は、この条件では停止しない）\n"
        )
        self.assertIn("create-plan", fake_bullet_3)


if __name__ == "__main__":
    unittest.main()
