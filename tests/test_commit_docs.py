"""Tests for em-workflow/scripts/commit-docs.sh.

Exercises the script against throwaway git repositories built in a
temporary directory, per test/README.md. Covers AC-1..AC-4 of
feature-docs/integration-worktree-orchestration/tasks/task0001.md.
"""

import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMIT_DOCS_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "commit-docs.sh"

FEATURE = "feat"
PARENT_BRANCH = f"em-workflow/{FEATURE}/integration"

# Exit codes per commit-docs.sh's header contract.
EXIT_OK = 0
EXIT_ARG_FAILURE = 1
EXIT_LOCK_FAILURE = 2
EXIT_GIT_FAILURE = 3


class TestCommitDocs(unittest.TestCase):
    """Base fixture: a main repo + integration branch + a linked worktree
    with that branch checked out (the shape commit-docs.sh targets),
    matching the `.claude/worktrees/em-workflow/{feature}/integration`
    layout used in production."""

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
        self.integ_wt = self._add_worktree("integration", PARENT_BRANCH)

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
        self._git(self.main_repo, "branch", PARENT_BRANCH)

    def _add_worktree(self, name, base_ref):
        """Create a linked worktree at the real
        `.claude/worktrees/em-workflow/{feature}/{name}` layout, with a
        branch named after it forked from base_ref."""
        wt_path = (
            self.main_repo / ".claude" / "worktrees" / "em-workflow" / FEATURE / name
        )
        branch = f"em-workflow/{FEATURE}/{name}"
        existing = self._git(
            self.main_repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False
        )
        if existing.returncode == 0:
            self._git(self.main_repo, "worktree", "add", str(wt_path), branch)
        else:
            self._git(self.main_repo, "worktree", "add", "-b", branch, str(wt_path), base_ref)
        return wt_path

    def _write_pending_change(self, worktree, filename="doc.txt", content="pending\n"):
        (Path(worktree) / filename).write_text(content)

    def _run_commit_docs(self, worktree_path, message):
        return subprocess.run(
            [str(COMMIT_DOCS_SCRIPT), str(worktree_path), message],
            cwd=str(self.tmp_path),
            env=self.git_env,
            capture_output=True,
            text=True,
        )

    def _head(self, worktree):
        return self._git(worktree, "rev-parse", "HEAD").stdout.strip()

    def _log_subjects(self, worktree, n):
        out = self._git(worktree, "log", f"-{n}", "--format=%s").stdout
        return [line for line in out.splitlines() if line]

    def _resolve_lock_path(self, worktree):
        common_dir = self._git(worktree, "rev-parse", "--git-common-dir").stdout.strip()
        common_dir_path = Path(common_dir)
        if not common_dir_path.is_absolute():
            common_dir_path = Path(worktree) / common_dir_path
        return common_dir_path.resolve() / "em-workflow-merge.lock"

    # -- AC-1 ------------------------------------------------------------

    def test_pending_changes_commit_and_advance_ref_by_one(self):
        # references AC-1
        before = self._head(self.integ_wt)
        self._write_pending_change(self.integ_wt)

        result = self._run_commit_docs(self.integ_wt, "docs(feat): update notes")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertNotEqual(before, after)
        subjects = self._log_subjects(self.integ_wt, 2)
        self.assertEqual(subjects, ["docs(feat): update notes", "initial commit"])

    # -- AC-2 ------------------------------------------------------------

    def test_no_pending_changes_is_a_noop(self):
        # references AC-2
        before = self._head(self.integ_wt)

        result = self._run_commit_docs(self.integ_wt, "docs(feat): nothing changed")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertEqual(before, after)
        self.assertIn("NOOP", result.stdout)

    # -- AC-3 ------------------------------------------------------------

    def test_missing_path_fails_with_argument_failure_code(self):
        # references AC-3
        missing_path = self.tmp_path / "does-not-exist"

        result = self._run_commit_docs(missing_path, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)

    def test_non_git_directory_fails_with_argument_failure_code(self):
        # references AC-3
        plain_dir = self.tmp_path / "plain-dir"
        plain_dir.mkdir()

        result = self._run_commit_docs(plain_dir, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)

    def test_main_working_tree_is_rejected_as_not_linked(self):
        # references AC-3 (non-worktree path: the main working tree itself)
        before = self._head(self.main_repo)

        result = self._run_commit_docs(self.main_repo, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)
        after = self._head(self.main_repo)
        self.assertEqual(before, after)

    def test_empty_message_fails_with_argument_failure_code(self):
        # references AC-3
        before = self._head(self.integ_wt)
        self._write_pending_change(self.integ_wt)

        result = self._run_commit_docs(self.integ_wt, "")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertEqual(before, after)

    # -- AC-4 --------------------------------------------------------------

    def test_blocks_while_lock_held_then_commits_after_release_no_lost_update(self):
        # references AC-4 (blocking + serialization; both effects survive)
        hold_seconds = 1.5
        lock_path = self._resolve_lock_path(self.integ_wt)

        # Background lock-holder: acquires the SAME lock file commit-docs.sh
        # uses, holds it for hold_seconds, then makes its OWN commit in the
        # same worktree before releasing — standing in for a
        # merge-task.sh-style ref advance serialized under the same lock.
        holder_script = (
            f'exec 8>"{lock_path}" && flock 8 && sleep {hold_seconds} && '
            f'git -C "{self.integ_wt}" commit -q --allow-empty '
            f'-m "lockholder: simulated merge-task advance"'
        )
        holder_start = time.monotonic()
        holder = subprocess.Popen(
            ["bash", "-c", holder_script],
            env=self.git_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give the holder a moment to actually acquire the lock before we
        # start racing commit-docs.sh against it.
        time.sleep(0.3)

        self._write_pending_change(self.integ_wt, "doc.txt", "pending-under-lock\n")
        result = self._run_commit_docs(self.integ_wt, "docs(feat): update while locked")
        finished_at = time.monotonic() - holder_start

        holder_stdout, holder_stderr = holder.communicate(timeout=30)
        self.assertEqual(holder.returncode, 0, holder_stdout.decode() + holder_stderr.decode())

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        # Proves real blocking, not a lucky race: commit-docs.sh could not
        # have finished before the holder released the lock (measured from
        # the holder's own start, not from after our warm-up sleep).
        self.assertGreaterEqual(finished_at, hold_seconds - 0.2)

        subjects = self._log_subjects(self.integ_wt, 3)
        # Both commits survive, in order: neither the lock-holder's
        # "merge-task.sh-style" commit nor commit-docs.sh's own commit is
        # lost or overwritten.
        self.assertEqual(
            subjects,
            [
                "docs(feat): update while locked",
                "lockholder: simulated merge-task advance",
                "initial commit",
            ],
        )

    def test_lock_open_failure_and_git_commit_failure_use_distinct_codes(self):
        # references AC-4 (distinct exit codes: lock failure vs git failure)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("cannot exercise a read-only-directory failure as root")

        # -- lock failure: make the git common dir read-only so the lock
        # file itself cannot be created. --
        common_dir = Path(
            self._git(self.integ_wt, "rev-parse", "--git-common-dir").stdout.strip()
        )
        if not common_dir.is_absolute():
            common_dir = self.integ_wt / common_dir
        common_dir = common_dir.resolve()
        original_mode = common_dir.stat().st_mode
        os.chmod(common_dir, 0o555)
        try:
            self._write_pending_change(self.integ_wt, "doc.txt", "for-lock-failure\n")
            lock_failure_result = self._run_commit_docs(self.integ_wt, "docs(feat): x")
        finally:
            os.chmod(common_dir, original_mode)

        self.assertEqual(
            lock_failure_result.returncode,
            EXIT_LOCK_FAILURE,
            lock_failure_result.stdout + lock_failure_result.stderr,
        )

        # -- git failure: a failing pre-commit hook rejects the commit
        # itself, after staging succeeds. --
        hooks_dir = Path(
            self._git(self.integ_wt, "rev-parse", "--git-path", "hooks").stdout.strip()
        )
        if not hooks_dir.is_absolute():
            hooks_dir = self.integ_wt / hooks_dir
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "pre-commit"
        hook_path.write_text("#!/bin/sh\nexit 1\n")
        hook_path.chmod(0o755)

        before = self._head(self.integ_wt)
        self._write_pending_change(self.integ_wt, "doc2.txt", "for-git-failure\n")
        git_failure_result = self._run_commit_docs(self.integ_wt, "docs(feat): y")
        after = self._head(self.integ_wt)

        self.assertEqual(
            git_failure_result.returncode,
            EXIT_GIT_FAILURE,
            git_failure_result.stdout + git_failure_result.stderr,
        )
        self.assertEqual(before, after)

        self.assertNotEqual(lock_failure_result.returncode, git_failure_result.returncode)


if __name__ == "__main__":
    unittest.main()
