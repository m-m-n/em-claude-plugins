"""Tests for task0001 (routeback-gate-postcondition): widening the I.2.c
route-back gate to a conjunction of both blockers, collapsing the rejected
path to a single generalized terminal, and correcting the Branch & Worktree
Model's exit-4 call-site enumeration in
`em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/routeback-gate-postcondition/tasks/task0001.md):

- AC-1 (FR1, NFR2): the gate is the conjunction of "no task has status
  `merged`" and "no task has status `in_progress`", both read from
  workflow.yaml task statuses, independent of the preceding drain.
- AC-2 (FR1): the four write-set instructions stay present and ordered
  before the worktree/branch cleanup, and the section still cites
  `references/workflow-patch.md`'s `replace_all` permission conditions as
  the owner without restating them.
- AC-3 (FR2): the rejected path states exactly one terminal, phrased to
  cover both blockers, with no retry/alternative/degraded route back
  offered; the sibling retry/abort options, the "NO skip option"
  paragraph, the heading and the batch-mode paragraph stay unchanged
  (heading and batch-mode paragraph byte-identical).
- AC-4 (FR3): in document order, the gate decision precedes the
  integration-worktree refresh, the tip capture, the write set, the
  cleanup and the `commit-docs.sh` invocation; an explicit sentence states
  the rejected path commits nothing and starts no cleanup.
- AC-5 (FR4): the Branch & Worktree Model's exit-4 recovery bullet no
  longer lists the I.2.c route-back commit as an applicable call site,
  still names Step I.1's and Step I.2.b's commits, and states the
  unreachability justification chain tied to the widened gate; the I.2.c
  call site no longer points at the bounded recovery procedure and
  instead states the unreachability plus a stop-with-report terminal.
- AC-6 (FR5, NFR3): all test changes live in this module; the module's
  test method count does not decrease; no test is skipped; every new
  absence assertion is paired with a proof that its matcher flags the
  pre-change wording.
- AC-7 (NFR1, NFR3): covered by this task's own file-set discipline (the
  diff touches only this file and the target document) and by the full
  suite passing.

This is a documentation task (Test Notes: unit-level document-contract
assertions), following the pattern established by
tests/test_review_implement_develop_lock_contracts.py (task0007). Content
assertions compare against a whitespace-normalized copy of the section so
that line-wrap choices inside the prose never make an assertion brittle;
byte-identity assertions (AC-3's heading/batch-mode-paragraph clause)
compare the raw, un-normalized text.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"

# Pre-change literal (captured before the task0001 edit landed) -- AC-3's
# byte-identity assertion needs this exact value. Captured via:
#   text.index("Batch mode (`references/batch-mode.md`")
#   .. text.index("### Supporting cast")
PRE_CHANGE_BATCH_MODE_PARAGRAPH = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase** (implement\n"
    "stays `failed`, report and stop; the external service cuts a follow-up\n"
    "task). Route-back-to-planning is never taken automatically. Track the\n"
    "retry-consumed state per task in `tasks.{T}.notes`.\n"
    "\n"
)

# Historical regression guards, pre-dating this feature: the self-falsifying
# gate phrasing and the delegation mis-citation from an earlier round of
# this same section. This task neither introduces nor removes either, but
# both remain standing proof that the section has not regressed to them.
OLD_SELF_FALSIFYING_GATE_PHRASE = "every existing task is still `pending`"
OLD_DELEGATION_MISCITATION_PHRASE = "create-plan exemption owns that precedence"

# This task's own removed wording (task0001, routeback-gate-postcondition),
# captured before the edit landed -- needed for the absence assertions'
# paired regression proofs (AC-6).
OLD_DRAIN_AS_JUSTIFICATION_PHRASE = (
    "the drain above has already retired every `in_progress` sibling by "
    "this point"
)
OLD_MERGED_ONLY_TERMINAL_PHRASE = (
    "If any task has already merged, this automatic re-entry does not apply"
)
OLD_EXIT4_ENUMERATION_TAIL = (
    "Step I.2.b's wake-phase commit, and Step I.2.c's route-back commit"
)
OLD_I2C_RECOVERY_POINTER = "(exit-4 recovery: Branch & Worktree Model above)"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where this
    task's prose happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _i2c_section(text):
    """The `### I.2.c: Failed handling` section, sliced from its heading to
    the next section heading -- includes the route-back/retry/abort
    bullets, the "NO skip option" paragraph and the batch-mode paragraph."""
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    """The `## Branch & Worktree Model` section, sliced from its heading to
    the next top-level step heading -- includes the exit-4 recovery
    bullet."""
    start = text.index("## Branch & Worktree Model")
    end = text.index("## Step I.0")
    return text[start:end]


def _bare_git_commit_or_add_lines(text):
    """Lines that are actual shell invocations (start with `git`, ignoring
    markdown backticks/indentation) touching `commit` or `add -A` -- as
    opposed to prose that merely mentions "git commit" inside a sentence."""
    out = []
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if re.match(r"^git\s", stripped) and re.search(r"\b(commit\b|add -A\b)", stripped):
            out.append(line.strip())
    return out


class TestRouteBackGateIsConjunctionOfBothBlockers(unittest.TestCase):
    """AC-1 / FR1, NFR2: route-back admissibility is the conjunction of "no
    task has status `merged`" and "no task has status `in_progress`", both
    read from workflow.yaml task statuses, as an independent check -- never
    inferred from the preceding drain."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_gate_states_no_merged_task_conjunct(self):
        self.assertIn("no task has status `merged`", self.section)

    def test_gate_states_no_in_progress_task_conjunct(self):
        self.assertIn("no task has status `in_progress`", self.section)

    def test_conjuncts_are_joined_in_one_sentence(self):
        section = self.section
        idx1 = section.index("no task has status `merged`")
        idx2 = section.index("no task has status `in_progress`")
        self.assertLess(idx1, idx2)
        between = section[idx1:idx2]
        self.assertNotIn(". ", between)

    def test_conjuncts_are_read_from_workflow_yaml_task_statuses(self):
        self.assertIn("re-read from workflow.yaml task statuses", self.section)

    def test_gate_is_independent_of_the_drain(self):
        self.assertIn("not inferred from the drain above", self.section)

    def test_drain_not_presented_as_in_progress_justification(self):
        self.assertNotIn(OLD_DRAIN_AS_JUSTIFICATION_PHRASE, self.section)

    def test_stale_in_progress_entry_blocks_like_a_merged_task(self):
        self.assertIn("stale or unretired `in_progress` entry", self.section)
        self.assertIn(
            "blocks this path exactly as a `merged` task does", self.section
        )

    def test_old_self_falsifying_gate_phrasing_absent(self):
        # Historical regression guard (pre-dates this feature).
        self.assertNotIn(OLD_SELF_FALSIFYING_GATE_PHRASE, self.section)


class TestRouteBackWriteSetUnchanged(unittest.TestCase):
    """AC-2 / FR1: the four write-set instructions (`create-plan` ->
    `needs_update`; `implement` -> `pending`; failure reason into
    `tasks.{T}.notes`; every failed task's status -> `pending`) stay
    present and ordered before the worktree/branch cleanup, and the
    section still cites `references/workflow-patch.md`'s `replace_all`
    permission conditions as the owner without restating them."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_failure_reason_stays_recorded_in_notes(self):
        self.assertIn("tasks.{T}.notes", self.section)
        self.assertIn("failure reason", self.section)

    def test_failed_task_status_is_reset_to_pending(self):
        self.assertIn("tasks.{T}.status", self.section)
        # the reset targets `pending`, distinct from a bare mention of the
        # field -- assert the two tokens are close together, not merely
        # both present somewhere in the (large) section.
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx: idx + 60]
        self.assertIn("pending", window)

    def test_status_reset_create_plan_and_implement_are_one_write_set(self):
        section = self.section
        self.assertIn("create-plan` to `needs_update`", section)
        self.assertIn("implement` step back to `pending`", section)
        self.assertIn("tasks.{T}.status` back to `pending`", section)
        # all three writes, plus the notes-preservation clause, occur
        # before the worktree/branch cleanup starts -- i.e. they belong to
        # one coherent write description, not scattered after cleanup.
        cleanup_idx = section.index("git worktree remove --force")
        for token in (
            "create-plan` to `needs_update`",
            "implement` step back to `pending`",
            "tasks.{T}.status` back to `pending`",
            "tasks.{T}.notes",
        ):
            self.assertLess(section.index(token), cleanup_idx)

    def test_status_reset_cites_workflow_patch_as_owner_without_restating(self):
        # the reset is explained as what makes `replace_planning`
        # admissible on re-entry, citing workflow-patch.md's `replace_all`
        # permission conditions as the owner -- never restating the rule.
        self.assertIn("replace_planning", self.section)
        self.assertIn("references/workflow-patch.md", self.section)
        self.assertIn("replace_all", self.section)


class TestGateDecisionPrecedesAllSideEffects(unittest.TestCase):
    """AC-4 / FR3: in document order, the gate decision precedes the
    integration-worktree refresh, the tip capture, the write set, the
    worktree/branch cleanup and the `commit-docs.sh` invocation; an
    explicit sentence states that the rejected path commits nothing and
    starts no cleanup."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_document_order_gate_before_refresh_tip_writeset_cleanup_commit(self):
        section = self.section
        gate_idx = section.index(
            "This automatic re-entry applies only when the gate holds"
        )
        refresh_idx = section.index("Refresh the integration worktree first")
        tip_idx = section.index("ROUTEBACK_TIP")
        write_set_idx = section.index("make one ordered workflow.yaml write set")
        cleanup_idx = section.index("git worktree remove --force")
        commit_idx = section.index("commit-docs.sh")
        self.assertLess(gate_idx, refresh_idx)
        self.assertLess(refresh_idx, tip_idx)
        self.assertLess(tip_idx, write_set_idx)
        self.assertLess(write_set_idx, cleanup_idx)
        self.assertLess(cleanup_idx, commit_idx)

    def test_rejected_path_commits_nothing_and_starts_no_cleanup(self):
        self.assertIn(
            "nothing is committed and no worktree/branch cleanup is started",
            self.section,
        )


class TestRejectedPathHasSingleGeneralizedTerminal(unittest.TestCase):
    """AC-3 / FR2: when the gate does not hold -- for either blocker -- the
    section states exactly one terminal: `create-plan` not set to
    `needs_update`, `implement` stays `failed`, control returned via
    develop's stop condition 3 (the same terminal as "abort phase"), with
    no retry, alternative recovery or degraded route back offered."""

    @classmethod
    def setUpClass(cls):
        # Slice on the normalized copy: the split point's anchor phrase
        # can straddle a line-wrap boundary in the raw markdown, which
        # would make `.index()` raise on a value that is genuinely
        # present.
        cls.section = _normalize_ws(_i2c_section(_read()))
        start = cls.section.index("When the gate does not hold")
        end = cls.section.index("- **abort phase**", start)
        cls.branch = cls.section[start:end]

    def test_covers_the_merged_blocker(self):
        self.assertIn("because a task has status `merged`", self.branch)

    def test_covers_the_in_progress_blocker(self):
        self.assertIn("because a task has status `in_progress`", self.branch)

    def test_create_plan_not_set_to_needs_update(self):
        self.assertIn(
            "create-plan` is NOT set to `needs_update`", self.branch
        )

    def test_implement_stays_failed(self):
        self.assertIn("implement` stays `failed`", self.branch)

    def test_control_returns_via_stop_condition_3(self):
        self.assertIn("stop condition 3", self.branch)
        self.assertIn("abort phase", self.branch)

    def test_no_retry_alternative_or_degraded_route_back_offered(self):
        self.assertIn(
            "No retry loop, no alternative recovery route, and no "
            "degraded route back is offered",
            self.branch,
        )

    def test_no_rework_or_append_handoff(self):
        self.assertNotIn("rework", self.branch)
        self.assertNotIn("append", self.branch)

    def test_old_single_blocker_only_phrasing_absent(self):
        self.assertNotIn(OLD_MERGED_ONLY_TERMINAL_PHRASE, self.section)


class TestExit4EnumerationExcludesRouteBackCommit(unittest.TestCase):
    """AC-5 / FR4: the Branch & Worktree Model's exit-4 recovery bullet no
    longer lists the I.2.c route-back commit as an applicable call site,
    still names Step I.1's baseline commit and Step I.2.b's wake-phase
    commit, and states the unreachability justification chain tied to the
    widened I.2.c gate; the bounded recovery procedure sentences
    themselves are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_branch_worktree_model_section(_read()))

    def test_enumeration_names_step_i1_and_step_i2b(self):
        self.assertIn("Step I.1's baseline commit", self.section)
        self.assertIn("Step I.2.b's wake-phase commit", self.section)

    def test_enumeration_no_longer_lists_i2c_route_back_commit(self):
        self.assertNotIn(OLD_EXIT4_ENUMERATION_TAIL, self.section)

    def test_states_unreachability_chain_tied_to_widened_gate(self):
        section = self.section
        self.assertIn("no task has status `in_progress`", section)
        self.assertIn("no implementer of this feature can be running", section)
        self.assertIn(
            "implementers are the only callers of `merge-task.sh`", section
        )
        self.assertIn("no concurrent ref advance can occur", section)

    def test_recovery_procedure_sentences_survive(self):
        # IMPLEMENTATION.md D4: only the enumeration changes; the recovery
        # procedure sentences themselves stay as they are.
        section = self.section
        self.assertIn("retry `commit-docs.sh` once", section)
        self.assertIn("second exit 4", section)
        self.assertIn("stops the phase", section)


class TestI2cCallSiteNoLongerPointsAtRecoveryProcedure(unittest.TestCase):
    """AC-5 / FR4 (second half): the I.2.c route-back commit no longer
    points at the bounded exit-4 recovery procedure -- it states that exit
    4 cannot occur at this call site and that an unexpected non-zero exit
    stops the phase with a report."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_old_recovery_pointer_removed(self):
        self.assertNotIn(OLD_I2C_RECOVERY_POINTER, self.section)

    def test_states_exit4_unreachable_at_this_call_site(self):
        self.assertIn("exit 4 cannot occur at this call site", self.section)

    def test_states_stop_with_report_terminal_for_unexpected_exit(self):
        self.assertIn(
            "stops the phase immediately with a report", self.section
        )

    def test_points_to_branch_worktree_model_for_justification(self):
        self.assertIn(
            "Branch & Worktree Model's exit-4 recovery bullet above",
            self.section,
        )


class TestDelegationCitesStopCondition3Clause(unittest.TestCase):
    """Regression coverage (out of this task's scope, per task0001.md
    Surface B's out-of-scope note): the delegation sentence naming Step
    B's stop-condition-3 precedence clause is untouched by this task's
    edits."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_names_stop_condition_3_precedence_clause(self):
        self.assertIn("skills/develop/SKILL.md", self.section)
        self.assertIn("Step B's stop-condition-3 precedence clause", self.section)

    def test_no_longer_attributes_precedence_to_create_plan_exemption(self):
        # Historical regression guard (pre-dates this feature).
        self.assertNotIn(OLD_DELEGATION_MISCITATION_PHRASE, self.section)


class TestContainmentAndInvariants(unittest.TestCase):
    """AC-3 (heading/batch-mode-paragraph clause) / NFR1: the heading and
    the batch-mode paragraph stay byte-identical, and implement-phase.md
    has no bare `git commit` / `git add -A` line. The rest of AC-7
    (file-set containment; the full suite passing unmodified elsewhere) is
    covered by this task's own file-set discipline and by the suites
    outside this file, run unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_is_byte_identical(self):
        self.assertIn(I2C_HEADING, self.text)
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx: idx + len(I2C_HEADING)], I2C_HEADING)

    def test_batch_mode_paragraph_is_byte_identical(self):
        section = _i2c_section(self.text)
        start = section.index("Batch mode (`references/batch-mode.md`")
        actual = section[start:]
        self.assertEqual(actual, PRE_CHANGE_BATCH_MODE_PARAGRAPH)

    def test_no_bare_git_commit_or_add_lines(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- demonstrated
    against the pre-change wording itself (AC-6: every new absence
    assertion is paired with such a proof)."""

    def test_old_self_falsifying_gate_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "This automatic re-entry applies only when every existing "
            "task is still `pending` (i.e. none has merged yet)."
        )
        self.assertIn(OLD_SELF_FALSIFYING_GATE_PHRASE, sample)

    def test_old_delegation_miscitation_matcher_flags_pre_change_wording(self):
        sample = (
            "`skills/develop/SKILL.md` Step B's create-plan exemption "
            "owns that precedence"
        )
        self.assertIn(OLD_DELEGATION_MISCITATION_PHRASE, sample)

    def test_drain_justification_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "This automatic re-entry applies only when no task has status "
            "`merged` — the absence of any `merged` task; the drain above "
            "has already retired every `in_progress` sibling by this "
            "point. Refresh the integration worktree first."
        )
        self.assertIn(OLD_DRAIN_AS_JUSTIFICATION_PHRASE, sample)

    def test_merged_only_terminal_phrase_matcher_flags_pre_change_wording(self):
        sample = (
            "the normal SPEC.md update path first. If any task has "
            "already merged, this automatic re-entry does not apply: "
            "`create-plan` is NOT set to `needs_update`."
        )
        self.assertIn(OLD_MERGED_ONLY_TERMINAL_PHRASE, sample)

    def test_exit4_enumeration_tail_matcher_flags_pre_change_wording(self):
        sample = (
            "applies to every `commit-docs.sh` call site in this phase — "
            "Step I.1's baseline commit, Step I.2.b's wake-phase commit, "
            "and Step I.2.c's route-back commit): exit 4 means a "
            "concurrent `merge-task.sh` advanced the branch ref"
        )
        self.assertIn(OLD_EXIT4_ENUMERATION_TAIL, sample)

    def test_i2c_recovery_pointer_matcher_flags_pre_change_wording(self):
        sample = (
            '"docs({feature}): implement route back to planning" '
            '"$ROUTEBACK_TIP"` (exit-4 recovery: Branch & Worktree Model '
            "above). End the phase with a clear report."
        )
        self.assertIn(OLD_I2C_RECOVERY_POINTER, sample)

    def test_bare_commit_line_matcher_flags_an_unlocked_commit(self):
        sample = 'git -C {project_root} add -A -- foo && git -C {project_root} commit -m "x"'
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertTrue(lines)

    def test_bare_commit_line_matcher_ignores_prose_mentioning_commit(self):
        sample = "No bare `git add`/`git commit` against the integration worktree runs outside"
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
