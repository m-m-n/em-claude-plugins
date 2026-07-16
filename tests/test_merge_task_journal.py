"""Integration tests for merge-task.sh's journal append behavior.

Exercises em-workflow/scripts/merge-task.sh against throwaway git
repositories built in a temporary directory, per test/README.md. Covers
AC-1..AC-7 of feature-docs/implement-phase-queue/tasks/task0001.md.
"""

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

    # -- AC-5 ----------------------------------------------------------

    def test_no_journal_home_merge_succeeds_without_append_or_error(self):
        # references AC-5
        task_id = "task0006"
        wt = self._add_task_worktree("unused-feature", task_id, valid_layout=False)
        self._commit_file(wt, "feature.txt", "hello\n", "task0006: add feature file")

        result = self._run_merge(wt, task_id)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("WARNING", result.stderr)
        found = list(self.tmp_path.rglob("journal.jsonl"))
        self.assertEqual(found, [])

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

    # -- Review round 1 loop 2 regression: journal identity binding -----
    # The terminal `merged` event is bound to THIS worktree's task and THIS
    # feature's integration branch — a mismatched TASK_ID or PARENT_BRANCH
    # argument merges normally but skips the journal append with a warning.

    def test_mismatched_task_id_merges_but_skips_journal_append(self):
        feature = FEATURE
        task_id = "task0001"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")

        result = self._run_merge(wt, "task0002")  # wrong task id on purpose

        self.assertEqual(result.returncode, 0)
        self.assertIn("journal append skipped", result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])

    def test_mismatched_parent_branch_feature_skips_journal_append(self):
        feature = FEATURE
        task_id = "task0001"
        wt = self._add_task_worktree(feature, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", "task0001: add feature file")
        # A different feature's integration branch, pointing at the same base.
        other_parent = "em-workflow/other-feat/integration"
        self._git(self.main_repo, "branch", other_parent, PARENT_BRANCH)

        result = self._run_merge(wt, task_id, parent_branch=other_parent)

        self.assertEqual(result.returncode, 0)
        self.assertIn("journal append skipped", result.stderr)
        self.assertEqual(self._read_journal_lines(feature), [])


if __name__ == "__main__":
    unittest.main()
