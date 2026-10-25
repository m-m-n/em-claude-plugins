"""Integration tests for merge-task.sh's journal append behavior.

Exercises em-workflow/scripts/merge-task.sh against throwaway git
repositories built in a temporary directory, per test/README.md. Covers
AC-1..AC-7 of feature-docs/implement-phase-queue/tasks/task0001.md.
"""

import contextlib
import fcntl
import json
import os
import re
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MERGE_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-task.sh"

FEATURE = "feat"
PARENT_BRANCH = f"em-workflow/{FEATURE}/integration"

# Upper bound (seconds) a rejected run may take while the test itself holds
# the shared merge lock: a rejection happens before the lock is taken, so it
# must finish far inside this bound; a run still blocked at the bound fails
# the test.
LOCKED_RUN_BOUND_SECONDS = 5

# RFC 3339 with an explicit offset (or "Z"); we assert the *format*, not an
# exact value, per the task plan's test notes.
RFC3339_OFFSET_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class TestMergeTaskJournal(unittest.TestCase):
    """Base fixture: a main repo + integration branch + task worktrees
    matching the `.claude/worktrees/em-workflow/{feature}/{task_id}` layout,
    then merge-task.sh invoked as a subprocess from inside each worktree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

        # Isolate git from the host's real config (no gpgsign prompts, no
        # global hooks/aliases bleeding into throwaway repos).
        git_home = self.tmp_path / "git-home"
        git_home.mkdir()
        self.git_env = dict(os.environ)
        self.git_env.update(
            {
                "HOME": str(git_home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )

        self.main_repo = self.tmp_path / "main-repo"
        self._init_main_repo()

    # -- fixture helpers ---------------------------------------------------

    def _git(self, cwd, *args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=self.git_env,
            capture_output=True,
            text=True,
            check=check,
        )

    def _init_main_repo(self):
        self.main_repo.mkdir()
        self._git(self.main_repo, "init", "-q", "-b", "main")
        self._git(self.main_repo, "config", "commit.gpgsign", "false")
        (self.main_repo / "README.md").write_text("base\n")
        self._git(self.main_repo, "add", "README.md")
        self._git(self.main_repo, "commit", "-q", "-m", "initial commit")
        # The main repo's own working tree stays checked out on
        # PARENT_BRANCH for the whole test; committing directly here
        # simulates other work landing on the integration branch while a
        # task worktree merges.
        self._git(self.main_repo, "checkout", "-q", "-b", PARENT_BRANCH)

    def _add_task_worktree(self, feature, task_id, base_ref=PARENT_BRANCH, valid_layout=True):
        """Create a task branch forked from base_ref and its worktree.

        valid_layout=True places the worktree under the real
        `.claude/worktrees/em-workflow/{feature}/{task_id}` layout so
        merge-task.sh can find a journal home; False places it somewhere
        the layout validation rejects (AC-5).
        """
        if valid_layout:
            wt_path = (
                self.main_repo
                / ".claude"
                / "worktrees"
                / "em-workflow"
                / feature
                / task_id
            )
        else:
            wt_path = self.tmp_path / "outside-layout" / task_id
            wt_path.parent.mkdir(parents=True, exist_ok=True)
        branch = f"em-workflow/{feature}/{task_id}"
        self._git(self.main_repo, "worktree", "add", "-b", branch, str(wt_path), base_ref)
        return wt_path

    def _commit_file(self, worktree, filename, content, message):
        path = Path(worktree) / filename
        path.write_text(content)
        self._git(worktree, "add", filename)
        self._git(worktree, "commit", "-q", "-m", message)

    def _run_merge(self, worktree, task_id, parent_branch=PARENT_BRANCH):
        return subprocess.run(
            [str(MERGE_SCRIPT), parent_branch, task_id],
            cwd=str(worktree),
            env=self.git_env,
            capture_output=True,
            text=True,
        )

    def _journal_path(self, feature):
        return (
            self.main_repo
            / ".claude"
            / "worktrees"
            / "em-workflow"
            / feature
            / "journal.jsonl"
        )

    def _read_journal_lines(self, feature):
        path = self._journal_path(feature)
        if not path.exists():
            return []
        return [line for line in path.read_text().splitlines() if line.strip()]

    def _assert_rfc3339_with_offset(self, value):
        self.assertRegex(value, RFC3339_OFFSET_RE)

    # -- helpers for the identity-binding rejection tests ----------------

    def _parent_sha(self):
        return self._git(self.main_repo, "rev-parse", PARENT_BRANCH).stdout.strip()

    def _assert_rejected_without_side_effects(self, result, task_id, parent_before):
        """The run ended with exit 2 and an ERROR line, left the integration
        ref alone, created no "merge: <task_id>" commit on it, and wrote no
        journal.jsonl anywhere under the test's temporary directory."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ERROR", result.stderr)
        self.assertEqual(self._parent_sha(), parent_before)
        subjects = self._git(
            self.main_repo, "log", "--format=%s", f"refs/heads/{PARENT_BRANCH}"
        ).stdout.splitlines()
        self.assertNotIn(f"merge: {task_id}", subjects)
        self.assertEqual(list(self.tmp_path.rglob("journal.jsonl")), [])

    @contextlib.contextmanager
    def _hold_merge_lock(self):
        """Hold the shared merge lock (the file merge-task.sh and
        commit-docs.sh both lock, in the git common directory) from the test
        process itself, releasing it on exit."""
        common_dir = Path(
            self._git(self.main_repo, "rev-parse", "--git-common-dir").stdout.strip()
        )
        if not common_dir.is_absolute():
            common_dir = self.main_repo / common_dir
        fd = os.open(str(common_dir / "em-workflow-merge.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)  # closing the descriptor releases the lock

    def _run_merge_while_lock_held(self, worktree, task_id):
        """Run merge-task.sh with a bounded wait; a run still blocked at the
        bound fails the test (subprocess.run ends the child on its own
        timeout; nothing is killed from outside)."""
        try:
            return subprocess.run(
                [str(MERGE_SCRIPT), PARENT_BRANCH, task_id],
                cwd=str(worktree),
                env=self.git_env,
                capture_output=True,
                text=True,
                timeout=LOCKED_RUN_BOUND_SECONDS,
            )
        except subprocess.TimeoutExpired:
            self.fail(
                f"merge-task.sh still blocked after {LOCKED_RUN_BOUND_SECONDS}s "
                "while the merge lock was held (the rejection must come before the lock)"
            )

    # -- AC-1 ----------------------------------------------------------

    def test_fast_forward_merge_appends_one_well_formed_merged_line(self):
        # references AC-1
        feature = FEATURE
        task_id = "task0001"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        head_sha = self._git(wt, "rev-parse", "HEAD").stdout.strip()

        result = self._run_merge(wt, task_id)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("fast-forward", result.stdout)
        lines = self._read_journal_lines(feature)
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["event"], "merged")
        self.assertEqual(event["task"], task_id)
        self.assertEqual(event["commit"], head_sha)
        self._assert_rfc3339_with_offset(event["at"])

    # -- AC-2 ----------------------------------------------------------

    def test_merge_commit_merge_appends_one_well_formed_merged_line(self):
        # references AC-2
        feature = FEATURE
        task_id = "task0002"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "task-file.txt", "task change\n", "task0002: add task file")
        # Advance the parent branch independently (different file, so no
        # conflict) so the branches diverge and a real merge commit is
        # required.
        self._commit_file(
            self.main_repo,
            "parent-file.txt",
            "parent change\n",
            "integration: unrelated advance",
        )

        result = self._run_merge(wt, task_id)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        parent_head = self._git(self.main_repo, "rev-parse", PARENT_BRANCH).stdout.strip()
        # A real merge commit lands on a new sha distinct from both
        # pre-merge tips.
        pre_merge_head = self._git(wt, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(parent_head, pre_merge_head)

        lines = self._read_journal_lines(feature)
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["event"], "merged")
        self.assertEqual(event["task"], task_id)
        self.assertEqual(event["commit"], parent_head)
        self._assert_rfc3339_with_offset(event["at"])

    # -- AC-3 ----------------------------------------------------------

    def test_idempotent_already_merged_path_appends_merged_line_and_tolerates_duplicates(self):
        # references AC-3
        feature = FEATURE
        task_id = "task0003"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0003: add feature file")

        first = self._run_merge(wt, task_id)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        second = self._run_merge(wt, task_id)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already contained in", second.stdout)

        lines = self._read_journal_lines(feature)
        self.assertEqual(len(lines), 2)
        parent_head = self._git(self.main_repo, "rev-parse", PARENT_BRANCH).stdout.strip()
        for line in lines:
            event = json.loads(line)
            self.assertEqual(event["event"], "merged")
            self.assertEqual(event["task"], task_id)
            self.assertEqual(event["commit"], parent_head)
            self._assert_rfc3339_with_offset(event["at"])

    # -- AC-4 ------------------------------------------------------------

    def test_conflicting_merge_appends_nothing(self):
        # references AC-4 (conflict path)
        feature = FEATURE
        task_id = "task0004"
        self._commit_file(
            self.main_repo, "shared.txt", "base line\n", "integration: add shared file"
        )
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "shared.txt", "task change\n", "task0004: change shared line")
        self._commit_file(
            self.main_repo,
            "shared.txt",
            "integration change\n",
            "integration: change shared line differently",
        )

        result = self._run_merge(wt, task_id)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])

    def test_precondition_error_appends_nothing(self):
        # references AC-4 (error path)
        feature = FEATURE
        task_id = "task0005"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0005: add feature file")

        result = self._run_merge(wt, task_id, parent_branch="no-such-branch")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])

    # -- AC-5 (converted by merge-task-worktree-binding task0001) -------
    # Formerly a merge-only success test outside the em-workflow layout;
    # outside the layout the identity binding now rejects the run.

    def test_out_of_layout_task_worktree_is_rejected_without_merge_or_journal(self):
        # references AC-1 (c) / TS3 of merge-task-worktree-binding task0001
        task_id = "task0006"
        wt = self._add_task_worktree("unused-feature", task_id, valid_layout=False)
        self._commit_file(wt, "feature.txt", "hello\n", "task0006: add feature file")
        parent_before = self._parent_sha()

        result = self._run_merge(wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    # -- AC-6 ----------------------------------------------------------

    def test_journal_write_failure_does_not_change_exit_code(self):
        # references AC-6
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("cannot exercise an unwritable-directory failure as root")

        feature = FEATURE
        task_id = "task0007"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0007: add feature file")

        feature_dir = self._journal_path(feature).parent
        self.assertTrue(feature_dir.is_dir())
        original_mode = feature_dir.stat().st_mode
        os.chmod(feature_dir, 0o555)
        try:
            result = self._run_merge(wt, task_id)
        finally:
            os.chmod(feature_dir, original_mode)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING", result.stderr)
        self.assertFalse((feature_dir / "journal.jsonl").exists())

    # -- AC-7 ----------------------------------------------------------

    def test_concurrent_merges_produce_no_torn_or_interleaved_journal_lines(self):
        # references AC-7
        feature = FEATURE
        task_ids = [f"task10{i:02d}" for i in range(5)]
        worktrees = []
        for i, task_id in enumerate(task_ids):
            wt = self._add_task_worktree(feature, task_id)
            self._commit_file(
                wt, f"file-{i}.txt", f"content {i}\n", f"{task_id}: add file {i}"
            )
            worktrees.append(wt)

        results = [None] * len(worktrees)

        def _run(idx, worktree, task_id):
            results[idx] = self._run_merge(worktree, task_id)

        threads = [
            threading.Thread(target=_run, args=(i, wt, task_ids[i]))
            for i, wt in enumerate(worktrees)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        for i, result in enumerate(results):
            self.assertIsNotNone(result, f"worktree {i} merge did not complete in time")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        lines = self._read_journal_lines(feature)
        self.assertEqual(len(lines), len(task_ids))
        seen_tasks = set()
        for line in lines:
            event = json.loads(line)  # raises ValueError on a torn/interleaved line
            self.assertEqual(event["event"], "merged")
            seen_tasks.add(event["task"])
        self.assertEqual(seen_tasks, set(task_ids))

    # -- Review round 1 loops 2-3 regression: journal identity binding --
    # Inside the em-workflow worktree layout, TASK_ID must equal the
    # worktree's task directory and PARENT_BRANCH must be this feature's
    # integration branch. A mismatch aborts BEFORE any merge/ref update
    # (exit 2) — an exit-0 merge with no `merged` event would make the
    # failure net record a merged task as failed.

    def test_mismatched_task_id_aborts_before_merge(self):
        feature = FEATURE
        task_id = "task0001"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        parent_before = self._git(self.main_repo, "rev-parse", PARENT_BRANCH).stdout.strip()

        result = self._run_merge(wt, "task0002")  # wrong task id on purpose

        self.assertEqual(result.returncode, 2)
        self.assertIn("does not match", result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])
        parent_after = self._git(self.main_repo, "rev-parse", PARENT_BRANCH).stdout.strip()
        self.assertEqual(parent_before, parent_after)  # no ref update happened

    def test_mismatched_parent_branch_feature_aborts_before_merge(self):
        feature = FEATURE
        task_id = "task0001"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        # A different feature's integration branch, pointing at the same base.
        other_parent = "em-workflow/other-feat/integration"
        self._git(self.main_repo, "branch", other_parent, PARENT_BRANCH)
        other_before = self._git(self.main_repo, "rev-parse", other_parent).stdout.strip()

        result = self._run_merge(wt, task_id, parent_branch=other_parent)

        self.assertEqual(result.returncode, 2)
        self.assertIn("integration branch", result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])
        other_after = self._git(self.main_repo, "rev-parse", other_parent).stdout.strip()
        self.assertEqual(other_before, other_after)  # no ref update happened

    # -- merge-task-worktree-binding task0001: identity binding ----------
    # merge-task.sh merges only when run inside the named task's own
    # worktree of the em-workflow layout with that task's branch checked
    # out; every other placement ends with exit 2 before the merge lock.

    def test_main_working_tree_run_is_rejected_without_merge(self):
        # references AC-1 (a) / TS1
        task_id = "task0001"
        # The fixture keeps the main working tree on the integration branch,
        # which would then be contained in itself; move it to a branch that
        # carries a commit the integration branch lacks.
        self._git(self.main_repo, "checkout", "-q", "-b", "main-work")
        self._commit_file(
            self.main_repo, "main-only.txt", "main\n", "main work: commit integration lacks"
        )
        parent_before = self._parent_sha()

        result = self._run_merge(self.main_repo, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_integration_worktree_run_is_rejected_even_when_parent_contains_head(self):
        # references AC-1 (b) / TS2
        task_id = "task0001"
        # A branch is checked out in one worktree only: free the integration
        # branch from the main working tree first.
        self._git(self.main_repo, "checkout", "-q", "main")
        integration_wt = (
            self.main_repo / ".claude" / "worktrees" / "em-workflow" / FEATURE / "integration"
        )
        self._git(self.main_repo, "worktree", "add", str(integration_wt), PARENT_BRANCH)
        parent_before = self._parent_sha()

        result = self._run_merge(integration_wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_detached_head_in_layout_is_rejected(self):
        # references AC-2 / TS4
        task_id = "task0001"
        wt = self._add_task_worktree(FEATURE, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        self._git(wt, "checkout", "-q", "--detach")
        parent_before = self._parent_sha()

        result = self._run_merge(wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self.assertIn(f"refs/heads/em-workflow/{FEATURE}/{task_id}", result.stderr)

    def test_other_branch_checked_out_in_layout_is_rejected(self):
        # references AC-2 / TS5
        task_id = "task0001"
        wt = self._add_task_worktree(FEATURE, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        self._git(wt, "checkout", "-q", "-b", "some-other-branch")
        parent_before = self._parent_sha()

        result = self._run_merge(wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self.assertIn(f"refs/heads/em-workflow/{FEATURE}/{task_id}", result.stderr)
        self.assertIn("refs/heads/some-other-branch", result.stderr)

    # -- ordering (FR4): the rejection precedes the merge lock and the
    # clean-tree precondition ---------------------------------------------

    def test_main_working_tree_run_is_rejected_while_merge_lock_is_held(self):
        # references AC-3 / TS8
        task_id = "task0001"
        self._git(self.main_repo, "checkout", "-q", "-b", "main-work")
        self._commit_file(
            self.main_repo, "main-only.txt", "main\n", "main work: commit integration lacks"
        )
        parent_before = self._parent_sha()

        with self._hold_merge_lock():
            result = self._run_merge_while_lock_held(self.main_repo, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_detached_head_in_layout_is_rejected_while_merge_lock_is_held(self):
        # references AC-3 / TS8
        task_id = "task0001"
        wt = self._add_task_worktree(FEATURE, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        self._git(wt, "checkout", "-q", "--detach")
        parent_before = self._parent_sha()

        with self._hold_merge_lock():
            result = self._run_merge_while_lock_held(wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_detached_head_with_untracked_file_reports_identity_rejection(self):
        # references AC-3 / TS8
        task_id = "task0001"
        wt = self._add_task_worktree(FEATURE, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        self._git(wt, "checkout", "-q", "--detach")
        (wt / "untracked.txt").write_text("not committed\n")
        parent_before = self._parent_sha()

        result = self._run_merge(wt, task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self.assertIn(f"refs/heads/em-workflow/{FEATURE}/{task_id}", result.stderr)
        self.assertNotIn("uncommitted", result.stderr)

    # -- fail-closed (NFR1) and subdirectory (SPEC.md A4) ----------------

    def test_unresolvable_top_level_run_is_rejected(self):
        # references AC-4 / TS9: inside the git directory there is no work
        # tree, so the top-level cannot be resolved (git versions differ in
        # whether that is an error or an empty result; only the outcome is
        # asserted).
        task_id = "task0001"
        parent_before = self._parent_sha()

        result = self._run_merge(self.main_repo / ".git", task_id)

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_run_from_committed_subdirectory_of_own_worktree_merges(self):
        # references AC-4 / TS10: the binding resolves the worktree's
        # top-level, not the working directory.
        task_id = "task0001"
        wt = self._add_task_worktree(FEATURE, task_id)
        (wt / "subdir").mkdir()
        self._commit_file(wt, "subdir/nested.txt", "nested\n", "task0001: add nested file")

        result = self._run_merge(wt / "subdir", task_id)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        merged = [
            json.loads(line)
            for line in self._read_journal_lines(FEATURE)
            if json.loads(line)["event"] == "merged" and json.loads(line)["task"] == task_id
        ]
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
