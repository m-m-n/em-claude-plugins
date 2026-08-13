"""Tests for task0001 (implement-routeback-gate): the I.2.c route-back path
correction plus the Branch & Worktree Model's exit-4 call-site enumeration
in `em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/implement-routeback-gate/tasks/task0001.md):

- AC-1: the route-back bullet resets the failed task's `tasks.{T}.status`
  to `pending` and preserves the failure reason in `tasks.{T}.notes`, as
  part of the same write-back that sets `create-plan` to `needs_update`
  and `implement` back to `pending`.
- AC-2: the route-back bullet commits the write-back via `commit-docs.sh`
  with an expected-tip third argument and an exit-4 recovery pointer,
  positioned after the status-write instructions and before the
  end-of-phase report sentence, with unambiguous ordering relative to the
  failed task's worktree/branch cleanup.
- AC-3: the Branch & Worktree Model's exit-4 recovery bullet enumerates
  the I.2.c route-back commit alongside Step I.1's and Step I.2.b's.
- AC-4: the gate is expressed as the absence of any `merged` task; the old
  "every existing task is still `pending`" phrasing is gone from the
  section.
- AC-5: the merged-task branch states `implement` stays `failed` and
  control returns via develop's stop condition 3, with no "rework" or
  "`append`" in that branch's text.
- AC-6: the delegation sentence names Step B's stop-condition-3 precedence
  clause and no longer attributes that precedence to the create-plan
  exemption.
- AC-7 (partial -- the rest is covered by the two existing regression
  suites and by this task's own file-set discipline): the
  `### I.2.c: Failed handling` heading and the batch-mode paragraph that
  follows the section are byte-identical to their pre-change text.

This is a documentation task (Test Notes: unit-level document-contract
assertions), following the pattern established by
tests/test_review_implement_develop_lock_contracts.py (task0007). Content
assertions compare against a whitespace-normalized copy of the section so
that line-wrap choices inside the prose never make an assertion brittle;
byte-identity assertions (AC-7) compare the raw, un-normalized text.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"

# Pre-change literal (captured before the task0001 edit landed) -- AC-7's
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

# The removed, self-falsifying gate phrasing (AC-4).
OLD_GATE_PHRASE = "every existing task is still `pending`"

# The removed delegation mis-citation (AC-6).
OLD_DELEGATION_PHRASE = "create-plan exemption owns that precedence"


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


class TestRouteBackResetsFailedTaskAndPreservesNotes(unittest.TestCase):
    """AC-1 / FR1: the route-back bullet resets `tasks.{T}.status` to
    `pending` and preserves the failure reason in `tasks.{T}.notes`, as
    part of the same write-back that also sets `create-plan` to
    `needs_update` and `implement` back to `pending`."""

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


class TestRouteBackCommitsTheWriteBack(unittest.TestCase):
    """AC-2 / FR2: a `commit-docs.sh` call for the route-back write-back,
    with an expected-tip third argument and an exit-4 recovery pointer,
    positioned after the status-write instructions and before the
    end-of-phase report sentence; unambiguous ordering relative to the
    failed task's worktree/branch cleanup."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_commit_docs_sh_call_present_with_expected_tip_and_recovery_pointer(self):
        self.assertIn("commit-docs.sh", self.section)
        self.assertIn('"$WT_ROOT/integration"', self.section)
        self.assertIn("exit-4 recovery: Branch & Worktree Model above", self.section)

    def test_commit_follows_status_writes_and_precedes_end_of_phase_report(self):
        section = self.section
        status_write_idx = section.index("tasks.{T}.status` back to `pending`")
        commit_idx = section.index("commit-docs.sh")
        report_idx = section.index("End the phase with a")
        self.assertLess(status_write_idx, commit_idx)
        self.assertLess(commit_idx, report_idx)

    def test_cleanup_precedes_commit_unambiguously(self):
        section = self.section
        cleanup_idx = section.index("git worktree remove --force")
        commit_idx = section.index("commit-docs.sh")
        self.assertLess(cleanup_idx, commit_idx)


class TestExit4RecoveryEnumeratesRouteBackCommit(unittest.TestCase):
    """AC-3 / FR3: the Branch & Worktree Model's exit-4 recovery bullet
    enumerates the I.2.c route-back commit alongside Step I.1's baseline
    commit and Step I.2.b's wake-phase commit."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        start = text.index("## Branch & Worktree Model")
        end = text.index("## Step I.0")
        cls.section = _normalize_ws(text[start:end])

    def test_exit4_bullet_names_all_three_call_sites(self):
        section = self.section
        self.assertIn("exit-4 recovery", section)
        self.assertIn("Step I.1's baseline commit", section)
        self.assertIn("Step I.2.b's wake-phase commit", section)
        self.assertIn("Step I.2.c's route-back commit", section)

    def test_recovery_procedure_sentences_survive(self):
        # IMPLEMENTATION.md D4: only the enumeration changes; the recovery
        # procedure sentences themselves stay as they are.
        section = self.section
        self.assertIn("retry `commit-docs.sh` once", section)
        self.assertIn("second exit 4", section)
        self.assertIn("stops the phase", section)


class TestGateIsAbsenceOfMergedTask(unittest.TestCase):
    """AC-4 / FR4: the gate is expressed as the absence of any task with
    status `merged`; the old self-falsifying phrasing is gone."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_gate_expressed_as_no_merged_task(self):
        self.assertIn("no task has status `merged`", self.section)

    def test_old_falsifiable_phrasing_is_gone(self):
        # Checked against the normalized copy only: the phrase's own
        # words can straddle a line-wrap boundary in the raw markdown
        # (on either side of an edit), which would make a raw substring
        # search pass by accident rather than by the phrase's absence.
        self.assertNotIn(OLD_GATE_PHRASE, self.section)


class TestMergedTaskBranchHasDefinedTerminal(unittest.TestCase):
    """AC-5 / FR5: when a task has already merged, `implement` stays
    `failed` and control returns to the user via develop's stop condition
    3 -- the same terminal as "abort phase" -- with no rework/`append`
    handoff."""

    @classmethod
    def setUpClass(cls):
        # Slice on the normalized copy: the split point's anchor phrase
        # can straddle a line-wrap boundary in the raw markdown, which
        # would make `.index()` raise on a value that is genuinely
        # present.
        section = _normalize_ws(_i2c_section(_read()))
        start = section.index("If any task has already merged")
        end = section.index("- **abort phase**", start)
        cls.branch = section[start:end]

    def test_implement_stays_failed(self):
        self.assertIn("implement` stays `failed`", self.branch)

    def test_control_returns_via_stop_condition_3(self):
        self.assertIn("stop condition 3", self.branch)
        self.assertIn("abort phase", self.branch)

    def test_no_rework_or_append_handoff(self):
        self.assertNotIn("rework", self.branch)
        self.assertNotIn("append", self.branch)


class TestDelegationCitesStopCondition3Clause(unittest.TestCase):
    """AC-6 / FR6, NFR2: the delegation sentence names Step B's
    stop-condition-3 precedence clause and no longer attributes that
    precedence to the create-plan exemption."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_names_stop_condition_3_precedence_clause(self):
        self.assertIn("skills/develop/SKILL.md", self.section)
        self.assertIn("Step B's stop-condition-3 precedence clause", self.section)

    def test_no_longer_attributes_precedence_to_create_plan_exemption(self):
        # Checked against the normalized copy only -- see the matching
        # comment in TestGateIsAbsenceOfMergedTask.
        self.assertNotIn(OLD_DELEGATION_PHRASE, self.section)


class TestContainmentAndInvariants(unittest.TestCase):
    """AC-7 (partial) / NFR1: the heading and the batch-mode paragraph
    stay byte-identical, and implement-phase.md has no bare `git commit` /
    `git add -A` line. The rest of AC-7 (file-set containment; the two
    existing regression suites) is covered by this task's own file-set
    discipline and by tests/test_review_implement_develop_lock_contracts.py
    / tests/test_develop_skill_rewiring.py, run unchanged."""

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
    against the pre-change wording itself."""

    def test_old_gate_phrase_matcher_flags_the_pre_change_wording(self):
        sample = (
            "This automatic re-entry applies only when every existing "
            "task is still `pending` (i.e. none has merged yet)."
        )
        self.assertIn(OLD_GATE_PHRASE, sample)

    def test_old_delegation_phrase_matcher_flags_the_pre_change_wording(self):
        sample = (
            "`skills/develop/SKILL.md` Step B's create-plan exemption "
            "owns that precedence"
        )
        self.assertIn(OLD_DELEGATION_PHRASE, sample)

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
