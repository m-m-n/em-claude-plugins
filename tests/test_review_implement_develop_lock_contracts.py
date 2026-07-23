"""Tests for task0007: protocol contracts -- lock-aware fix commits,
wake-phase refresh, bootstrap resume.

Covers task0007 Acceptance Criteria
(feature-docs/integration-worktree-orchestration/tasks/task0007.md):

- AC-1: review-phase.md's develop-driven fix-commit instruction holds the
  shared lock across staging + commit; no bare integration-worktree commit
  remains anywhere in the document.
- AC-2: implement-phase.md's wake phase orders refresh -> read/edit ->
  commit, and defines the bounded exit-4 recovery loop (refresh, re-apply,
  retry once, then stop with report).
- AC-3: SKILL.md Step A defines the branch-without-workflow.yaml state with
  a deterministic route back into create-spec, and its shell templates
  reference the project root via a captured shell variable (no literal
  {project_root} inside command text).
- AC-4: Grep audit -- none of the three documents contains an
  integration-ref-advancing command outside the shared-lock discipline.

This is a documentation task (Test Notes: "verification by
inspection/grep, M-1-style audit"), so these are structural/textual checks
over the protocol markdown, following the pattern established by
tests/test_planner_designer_worktree_docs.py (task0005).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"


def _read(path):
    return path.read_text(encoding="utf-8")


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


class TestReviewPhaseFixCommitHoldsSharedLock(unittest.TestCase):
    """AC-1: the develop-driven fix-commit acquires the shared flock across
    staging + commit; no bare integration-worktree commit remains anywhere
    in review-phase.md."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PHASE_PATH)

    def test_fix_commit_block_acquires_shared_lock_file(self):
        self.assertIn("em-workflow-merge.lock", self.text)
        self.assertIn("flock 9", self.text)

    def test_lock_acquired_before_staging_and_commit(self):
        text = self.text
        lock_idx = text.index("flock 9")
        add_idx = text.index(
            'git -C "$PROJECT_ROOT" add -A -- "${authorized_files[@]}" || exit 1'
        )
        commit_idx = text.index(
            'git -C "$PROJECT_ROOT" commit -m "fix({feature}): review round '
            '{round} loop {N}" || exit 1'
        )
        self.assertLess(lock_idx, add_idx, "staging must happen AFTER acquiring the lock")
        self.assertLess(add_idx, commit_idx, "commit must happen after staging")

    def test_no_bare_commit_banner_present(self):
        self.assertIn(
            "No bare `git add`/`git commit` against the integration worktree "
            "runs outside",
            self.text,
        )

    def test_only_the_locked_add_and_commit_lines_exist(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        allowed = {
            'git -C "$PROJECT_ROOT" add -A -- "${authorized_files[@]}" || exit 1',
            'git -C "$PROJECT_ROOT" commit -m "fix({feature}): review round '
            '{round} loop {N}" || exit 1',
        }
        self.assertEqual(set(lines), allowed)


class TestImplementPhaseWakePhaseOrdering(unittest.TestCase):
    """AC-2: wake phase orders refresh -> read/edit -> commit, and defines
    the bounded exit-4 recovery loop."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        i1 = cls.text.index("### I.2.b: Wake phase")
        i2 = cls.text.index("### I.2.c: Failed handling")
        cls.wake_phase_section = cls.text[i1:i2]

    def test_wake_phase_refresh_precedes_workflow_yaml_edit_and_commit(self):
        section = self.wake_phase_section
        refresh_idx = section.index("Refresh the integration worktree FIRST")
        edit_idx = section.index("Update workflow.yaml, then commit")
        commit_idx = section.index(
            '"docs({feature}): implement wake\n   phase reconcile"'
        )
        self.assertLess(refresh_idx, edit_idx, "refresh must precede the workflow.yaml edit")
        self.assertLess(edit_idx, commit_idx, "the edit must precede its commit")

    def test_exit4_recovery_loop_is_bounded(self):
        text = self.text
        self.assertIn("exit-4 recovery", text)
        self.assertIn("retry `commit-docs.sh` once", text)
        self.assertIn("second exit 4", text)
        self.assertIn("stops the phase", text)

    def test_step_i1_commit_references_exit4_recovery(self):
        self.assertIn(
            '"docs({feature}): implement phase start"`\n'
            "(exit-4 recovery: Branch & Worktree Model above).",
            self.text,
        )

    def test_wake_phase_commit_references_exit4_recovery(self):
        self.assertIn(
            'phase reconcile"` (exit-4 recovery: Branch & Worktree Model above',
            self.wake_phase_section,
        )


class TestSkillStepABootstrapStates(unittest.TestCase):
    """AC-3: SKILL.md Step A defines the branch-without-workflow.yaml state
    with a deterministic route back into create-spec, and its shell
    templates reference the project root via a captured shell variable (no
    literal {project_root} inside command text)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        step_a_start = cls.text.index("## Step A: feature")
        step_a5_start = cls.text.index("## Step A.5:")
        cls.step_a_section = cls.text[step_a_start:step_a5_start]

    def test_project_root_captured_as_shell_variable(self):
        self.assertIn(
            'PROJECT_ROOT="$(git rev-parse --show-toplevel)"', self.step_a_section
        )

    def test_worktree_add_commands_use_captured_variable_not_literal_project_root(self):
        worktree_add_lines = [
            line
            for line in self.step_a_section.splitlines()
            if "git worktree add" in line
        ]
        self.assertTrue(
            worktree_add_lines, "expected at least one git worktree add template"
        )
        for line in worktree_add_lines:
            self.assertNotIn("{project_root}", line)
            self.assertIn("$PROJECT_ROOT", line)

    def test_branch_without_workflow_yaml_state_routes_to_create_spec(self):
        section = self.step_a_section
        self.assertIn("feature-docs/{feature}/workflow.yaml", section)
        self.assertIn("create-spec フェーズへ直接", section)
        self.assertIn("requirements-spec-creator.md Phase 3", section)

    def test_three_bootstrap_states_are_all_present(self):
        section = self.step_a_section
        # (a) branch + workflow.yaml -> resume Step B
        self.assertIn("Step A.5 → Step B へ進む", section)
        # (b) branch without workflow.yaml -> resume the incomplete create-spec
        self.assertIn("中断された状態", section)
        # (c) zero branches -> new feature
        self.assertIn("0件: 新規 feature", section)


class TestNoIntegrationRefAdvanceOutsideSharedLock(unittest.TestCase):
    """AC-4: grep audit -- none of the three documents contains an
    integration-ref-advancing command outside the shared-lock discipline."""

    def test_review_phase_bare_commits_confined_to_locked_block(self):
        text = _read(REVIEW_PHASE_PATH)
        lines = _bare_git_commit_or_add_lines(text)
        allowed = {
            'git -C "$PROJECT_ROOT" add -A -- "${authorized_files[@]}" || exit 1',
            'git -C "$PROJECT_ROOT" commit -m "fix({feature}): review round '
            '{round} loop {N}" || exit 1',
        }
        for line in lines:
            self.assertIn(
                line, allowed, f"unexpected unlocked git commit/add line: {line!r}"
            )

    def test_implement_phase_has_no_raw_git_commit_or_add(self):
        text = _read(IMPLEMENT_PHASE_PATH)
        lines = _bare_git_commit_or_add_lines(text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")

    def test_skill_has_no_raw_git_commit_or_add(self):
        text = _read(SKILL_PATH)
        lines = _bare_git_commit_or_add_lines(text)
        self.assertEqual(lines, [], f"unexpected raw git commit/add lines: {lines}")


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test)."""

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
