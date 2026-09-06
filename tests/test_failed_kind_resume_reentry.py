"""Tests for task0006 (implement-failed-kind, round-1 rework): the batch
infra auto-resume's re-entry admissibility is one contract stated across
three documents (IMPLEMENTATION.md D10) --
`em-workflow/references/implement-phase.md` (Step I.0's re-entry
precondition, and the route-back write set's `failed_kind` clear's own
role), `em-workflow/references/rework-task-synthesis.md` (Invariant 1's
scope), and `em-workflow/skills/develop/SKILL.md` (the auto-resume block's
write-set rationale). This module is the document-invariant pin for all
four statements.

Covers task0006 Acceptance Criteria
(feature-docs/implement-failed-kind/tasks/task0006.md):

- AC-1: `implement-phase.md` Step I.0 names three entry routes into
  `implement: pending`, states the auto-resume route's own satisfying
  condition (at least one task whose reconciled state is `failed`) and that
  no `pending` task is required on it; the fresh-first-pass route, the
  rework route and the immediate ABORT for a state satisfying neither
  condition are otherwise unchanged; the auto-resume branch is cited to the
  develop skill, not restated.
- AC-2: `rework-task-synthesis.md` Invariant 1 is scoped to rework-derived
  transitions and names the infra auto-resume as a transition outside its
  scope, citing the implement phase's Step I.0 for that route's
  precondition.
- AC-3: the develop skill's auto-resume block states that its write set
  touches no `tasks.*` key by design, why a task-status reset is not
  performed, and that the resumed phase handles the failed task through the
  implement phase's own reconcile and failure branch (cited, not
  restated).
- AC-4: `implement-phase.md` no longer gives "since the step is leaving
  `failed`" as the route-back clear's reason; Step I.1's phase-start write
  is the one place that names the write set carrying the lifecycle clear on
  entry from `failed`, the route-back clause states its own accurate role,
  and both cite the lifecycle rule's owner instead of restating it.

Every matcher below is backed by a negative proof against synthetic text
that omits or contradicts the statement (AC-6). Follows this suite's
established convention: standard library only, document text read from the
repository root computed from this module's own path, exact-wording markers
held as module constants, matched after whitespace normalisation (these
documents hard-wrap mid-phrase, including in Japanese without a
break-point space).
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPLEMENT_PHASE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "implement-phase.md"
)
REWORK_SYNTHESIS_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "rework-task-synthesis.md"
)
SKILL_PATH = os.path.join(REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md")


def _read(path):
    if not os.path.isfile(path):
        raise AssertionError(f"expected file to exist: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_ws(text):
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


# ---------------------------------------------------------------------
# AC-1: implement-phase.md Step I.0 -- three entry routes
# ---------------------------------------------------------------------

STEP_I0_HEADING = "## Step I.0: Preconditions"
STEP_I1_HEADING = "## Step I.1: Confirm the integration worktree"

THREE_ROUTES_OPENING = (
    "Step I.0 recognises three entry routes into\n   `implement: pending` "
    "— a fresh first pass, a rework re-entry, and the\n   develop skill's "
    "batch infra auto-resume"
)
AUTO_RESUME_CITED_NOT_RESTATED = (
    "(`skills/develop/SKILL.md`, the\n   auto-resume block; its own "
    "precondition and write set are stated there,\n   not restated here)"
)
FRESH_FIRST_PASS_NO_CONDITION = "A fresh first pass carries no further condition"
REWORK_ROUTE_UNCHANGED = (
    "require at least one task in `tasks` whose\n   `status == pending`"
)
AUTO_RESUME_SATISFYING_CONDITION = (
    "require at least one task whose Step\n   I.2.b step 1's reconciled "
    "state is `failed`"
)
AUTO_RESUME_NO_PENDING_REQUIRED = (
    "no `pending` task is required on this\n   route, since the "
    "auto-resume's write set registers no task"
)
ABORT_NEITHER_CONDITION = (
    "A non-fresh entry satisfying neither condition — every task "
    "`merged`\n   (or otherwise none `pending`), and no task whose "
    "reconciled state is\n   `failed` — is therefore a protocol error"
)


class ImplementPhaseDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.step_i0 = _section(cls.text, STEP_I0_HEADING, STEP_I1_HEADING)


class TestAC1ThreeEntryRoutes(ImplementPhaseDocTestCase):
    def test_names_three_entry_routes(self):
        self.assertTrue(_contains(self.step_i0, THREE_ROUTES_OPENING))

    def test_auto_resume_route_cited_to_develop_skill_not_restated(self):
        self.assertTrue(_contains(self.step_i0, AUTO_RESUME_CITED_NOT_RESTATED))

    def test_fresh_first_pass_route_unchanged(self):
        self.assertTrue(_contains(self.step_i0, FRESH_FIRST_PASS_NO_CONDITION))

    def test_rework_route_condition_unchanged(self):
        self.assertTrue(_contains(self.step_i0, REWORK_ROUTE_UNCHANGED))
        self.assertTrue(_contains(self.step_i0, "Invariant 1 of"))

    def test_auto_resume_satisfying_condition_stated(self):
        self.assertTrue(_contains(self.step_i0, AUTO_RESUME_SATISFYING_CONDITION))

    def test_no_pending_task_required_on_auto_resume_route(self):
        self.assertTrue(_contains(self.step_i0, AUTO_RESUME_NO_PENDING_REQUIRED))

    def test_abort_covers_neither_condition(self):
        self.assertTrue(_contains(self.step_i0, ABORT_NEITHER_CONDITION))

    def test_negative_proof_synthetic_two_route_text_fails_every_matcher(self):
        # A synthetic precondition naming only the OLD two routes (fresh +
        # rework), with no auto-resume route and no relaxed pending
        # condition -- every AC-1 matcher above must fail against it.
        synthetic = (
            "5. **Rework re-entry precondition**: when this phase is "
            "entered because review or verify sent `implement` back to "
            "`pending` (rework, not a fresh first pass), require at least "
            "one task in `tasks` whose `status == pending` — this is "
            "Invariant 1 of `references/rework-task-synthesis.md`. "
            "Entering this phase with every task `merged` (or otherwise "
            "none `pending`) is therefore a protocol error."
        )
        self.assertFalse(_contains(synthetic, THREE_ROUTES_OPENING))
        self.assertFalse(_contains(synthetic, AUTO_RESUME_CITED_NOT_RESTATED))
        self.assertFalse(_contains(synthetic, AUTO_RESUME_SATISFYING_CONDITION))
        self.assertFalse(_contains(synthetic, AUTO_RESUME_NO_PENDING_REQUIRED))
        self.assertFalse(_contains(synthetic, ABORT_NEITHER_CONDITION))
        # The rework route's own condition, unaffected by this task, is
        # still present in the synthetic text -- proving the matcher can
        # also correctly PASS, not just fail.
        self.assertTrue(_contains(synthetic, REWORK_ROUTE_UNCHANGED))


# ---------------------------------------------------------------------
# AC-2: rework-task-synthesis.md Invariant 1 -- scoped to rework-derived
# transitions, auto-resume named out of scope
# ---------------------------------------------------------------------

INVARIANTS_HEADING = "## 11. Invariants"
VALIDATION_HEADING = "## 12. Validation"

INVARIANT_1_SCOPED_OPENING = (
    "For a rework-derived transition (Section 10), before `implement`"
)
INVARIANT_1_STILL_REQUIRES_REGISTRATION = (
    "at least one new rework task is registered in\n   workflow.yaml"
)
INVARIANT_1_NAMES_AUTO_RESUME_OUT_OF_SCOPE = (
    "also returns\n   `implement` to `pending`, but is not a "
    "rework-derived transition and\n   registers no task; this invariant "
    "does not govern it"
)
INVARIANT_1_CITES_STEP_I0 = (
    "its precondition\n   is `references/implement-phase.md`'s Step I.0 "
    "(cited, not restated\n   here)"
)


class ReworkSynthesisDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_SYNTHESIS_PATH)
        cls.invariants_section = _section(
            cls.text, INVARIANTS_HEADING, VALIDATION_HEADING
        )


class TestAC2Invariant1ScopedToReworkTransitions(ReworkSynthesisDocTestCase):
    def test_invariant_1_scoped_to_rework_derived_transitions(self):
        self.assertTrue(
            _contains(self.invariants_section, INVARIANT_1_SCOPED_OPENING)
        )

    def test_invariant_1_still_requires_registration_before_pending(self):
        self.assertTrue(
            _contains(
                self.invariants_section, INVARIANT_1_STILL_REQUIRES_REGISTRATION
            )
        )

    def test_invariant_1_names_auto_resume_as_out_of_scope(self):
        self.assertTrue(
            _contains(
                self.invariants_section, INVARIANT_1_NAMES_AUTO_RESUME_OUT_OF_SCOPE
            )
        )

    def test_invariant_1_cites_step_i0_for_auto_resume_precondition(self):
        self.assertTrue(
            _contains(self.invariants_section, INVARIANT_1_CITES_STEP_I0)
        )

    def test_other_ten_invariants_and_count_unchanged(self):
        items = re.findall(
            r"^\d+\.", self.invariants_section, re.MULTILINE
        )
        self.assertEqual(len(items), 11)
        # Invariant 2 (the very next one) is untouched by this task's edit.
        self.assertTrue(
            _contains(
                self.invariants_section,
                "Every newly synthesized task's `status` is `pending`.",
            )
        )

    def test_negative_proof_synthetic_unscoped_invariant_fails_every_matcher(
        self,
    ):
        synthetic = (
            "1. Before `implement` returns to `pending`, at least one new "
            "rework task is registered in workflow.yaml."
        )
        self.assertFalse(_contains(synthetic, INVARIANT_1_SCOPED_OPENING))
        self.assertFalse(
            _contains(synthetic, INVARIANT_1_NAMES_AUTO_RESUME_OUT_OF_SCOPE)
        )
        self.assertFalse(_contains(synthetic, INVARIANT_1_CITES_STEP_I0))
        # The registration requirement itself is unaffected by the scoping
        # edit and still holds in the OLD unscoped wording too -- proving
        # this particular matcher is not itself the discriminator (the
        # scoping/citation matchers are).
        self.assertTrue(
            _contains(synthetic, INVARIANT_1_STILL_REQUIRES_REGISTRATION)
        )


# ---------------------------------------------------------------------
# AC-3: SKILL.md auto-resume block -- write-set rationale
# ---------------------------------------------------------------------

AUTO_RESUME_HEADING = (
    "**batch: implement の failed_kind による自動再開**（FR6, FR7, FR8）:"
)
STEP_TABLE_MARKER = "| step | 実行方法 |"

TOUCHES_NO_TASKS_KEY = "この書き込みセットは `tasks.*` のいずれのキーも変更しない設計である"
WHY_NO_STATUS_RESET = (
    "`tasks.{T}.status` をリセット\nすると、I.2.a の recycled-task-id "
    "carve-out の下でそのタスクが未起動と\nして選択可能になり、I.2.c の "
    "failure handling を経由せずに再起動されて\nしまう"
)
RESUMED_PHASE_HANDLES_VIA_RECONCILE = (
    "再開後の implement フェーズは、この失敗タスクを自身の reconcile\n"
    "と failure handling（`references/implement-phase.md` の Step "
    "I.2.b /\nI.2.c、引用のみでここでは繰り返さない）を通じて扱う"
)


class SkillAutoResumeBlockTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.block = _section(cls.text, AUTO_RESUME_HEADING, STEP_TABLE_MARKER)


class TestAC3WriteSetRationale(SkillAutoResumeBlockTestCase):
    def test_states_write_set_touches_no_tasks_key(self):
        self.assertTrue(_contains(self.block, TOUCHES_NO_TASKS_KEY))

    def test_states_why_status_reset_is_not_performed(self):
        self.assertTrue(_contains(self.block, WHY_NO_STATUS_RESET))

    def test_states_resumed_phase_handles_failure_via_implement_phase_reconcile(
        self,
    ):
        self.assertTrue(_contains(self.block, RESUMED_PHASE_HANDLES_VIA_RECONCILE))
        self.assertTrue(_contains(self.block, "references/implement-phase.md"))

    def test_no_failed_kind_value_named_outside_a_branch_condition(self):
        # The block's D7 citation discipline (asserted at large by
        # tests/test_failed_kind_stop_condition.py's AC-10) must not be
        # broken by this task's own addition: no backtick-quoted `infra` /
        # `decision` literal appears anywhere in the new prose.
        self.assertNotIn("`infra`", TOUCHES_NO_TASKS_KEY + WHY_NO_STATUS_RESET)
        self.assertNotIn(
            "`decision`", TOUCHES_NO_TASKS_KEY + WHY_NO_STATUS_RESET
        )

    def test_negative_proof_synthetic_write_set_only_description_fails(self):
        # A synthetic block that states only the write set (D4's original
        # scope, pre-task0006) and nothing about task state -- the AC-3
        # matchers above must all fail against it.
        synthetic = (
            "実行済み回数が cap に達している場合 → 要ユーザー判断の場合と"
            "同じ扱いとし、停止条件 3 が発火する。それ以外の場合 → 1 つの"
            "順序付き workflow.yaml 書き込みセット: `implement` の "
            "`status` を `pending` へ戻す、`failed_kind` を null へ戻す、"
            "実行済み回数を 1 増やす。この書き込みセットを、フェーズを"
            "実行する前に commit-docs.sh で 1 回だけコミットする。"
        )
        self.assertFalse(_contains(synthetic, TOUCHES_NO_TASKS_KEY))
        self.assertFalse(_contains(synthetic, WHY_NO_STATUS_RESET))
        self.assertFalse(
            _contains(synthetic, RESUMED_PHASE_HANDLES_VIA_RECONCILE)
        )


# ---------------------------------------------------------------------
# AC-4: implement-phase.md -- route-back clear's reason corrected; Step
# I.1 names the write set carrying the lifecycle clear
# ---------------------------------------------------------------------

STEP_I2_HEADING = "## Step I.2: Task loop"
I2C_HEADING = "### I.2.c: Failed handling"
SUPPORTING_CAST_HEADING = "### Supporting cast"

PHASE_START_LIFECYCLE_CLEAR_STATEMENT = (
    "this same write also clears `failed_kind`\n(`references/"
    "workflow-schema.md`) back to null — the write set that\ncarries the "
    "field's lifecycle clear on an entry from `failed`"
)
ROUTEBACK_OWN_ROLE_STATEMENT = (
    "re-asserting the null value Step I.1's phase-start write already set "
    "on\n  this entry, so this adds no extra write and no extra commit"
)
STALE_LEAVING_FAILED_REASON = "since the step is leaving `failed`"


class ImplementPhaseStepI1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.step_i1 = _section(cls.text, STEP_I1_HEADING, STEP_I2_HEADING)
        cls.i2c = _section(cls.text, I2C_HEADING, SUPPORTING_CAST_HEADING)


class TestAC4RouteBackReasonCorrectedAndPhaseStartNamesClear(
    ImplementPhaseStepI1TestCase
):
    def test_stale_leaving_failed_reason_is_gone_from_the_whole_document(self):
        self.assertNotIn(STALE_LEAVING_FAILED_REASON, self.text)

    def test_step_i1_names_the_write_set_carrying_the_lifecycle_clear(self):
        self.assertIn(PHASE_START_LIFECYCLE_CLEAR_STATEMENT, self.step_i1)

    def test_step_i1_cites_the_lifecycle_rules_owner(self):
        idx = self.step_i1.index("failed_kind")
        window = self.step_i1[idx : idx + 60]
        self.assertIn("references/workflow-schema.md", window)

    def test_route_back_states_its_own_accurate_role(self):
        self.assertIn(ROUTEBACK_OWN_ROLE_STATEMENT, self.i2c)

    def test_route_back_still_cites_the_lifecycle_rules_owner(self):
        self.assertIn(
            "clear `failed_kind`\n  (`references/workflow-schema.md`) "
            "back to null in that same write set",
            self.i2c,
        )

    def test_exactly_one_place_names_the_write_set_carrying_the_clear(self):
        # "carries the field's lifecycle clear" (Step I.1's own naming
        # sentence) occurs exactly once in the document -- the route-back
        # clause states its OWN role (a re-assertion) instead of repeating
        # this naming sentence a second time.
        self.assertEqual(
            self.text.count("carries the field's lifecycle clear"), 1
        )

    def test_negative_proof_synthetic_pre_change_wording_would_have_failed(
        self,
    ):
        pre_change_routeback = (
            "clear `failed_kind`\n  (`references/workflow-schema.md`) back "
            "to null in that same write set\n  since the step is leaving "
            "`failed`, record each such task's failure\n  reason"
        )
        pre_change_phase_start = (
            "In all cases set `implement` status to\n`in_progress`; "
            "commit the update with\n`commit-docs.sh"
        )
        self.assertIn(STALE_LEAVING_FAILED_REASON, pre_change_routeback)
        self.assertNotIn(
            PHASE_START_LIFECYCLE_CLEAR_STATEMENT, pre_change_phase_start
        )
        self.assertNotIn(ROUTEBACK_OWN_ROLE_STATEMENT, pre_change_routeback)


# ---------------------------------------------------------------------
# Module hygiene
# ---------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_own_imports_are_all_stdlib(self):
        import ast

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
