"""Tests for em-workflow/scripts/commit-docs.sh.

Exercises the script against throwaway git repositories built in a
temporary directory, per test/README.md. Covers AC-1..AC-4 of
feature-docs/integration-worktree-orchestration/tasks/task0006.md (the
recovery-contract + hardening + test-alignment rework of the original
task0001 contract).
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMIT_DOCS_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "commit-docs.sh"

FEATURE = "feat"
PARENT_BRANCH = f"em-workflow/{FEATURE}/integration"

# The default artifact-scoped path tests write pending doc changes under
# (feature-docs/{feature}/...) — matches SPEC FR3's artifact roots, unlike a
# bare "doc.txt" at the worktree root which the staging step never touches.
DEFAULT_ARTIFACT_REL_PATH = f"feature-docs/{FEATURE}/notes.md"

# Exit codes per commit-docs.sh's header contract.
EXIT_OK = 0
EXIT_ARG_FAILURE = 1
EXIT_LOCK_FAILURE = 2
EXIT_GIT_FAILURE = 3
EXIT_STALE = 4


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

    def _commit_file(self, worktree, filename, content, message):
        path = Path(worktree) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self._git(worktree, "add", filename)
        self._git(worktree, "commit", "-q", "-m", message)

    def _write_artifact_change(self, worktree, rel_path=DEFAULT_ARTIFACT_REL_PATH, content="pending\n"):
        path = Path(worktree) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

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

    def _fabricate_child_commit(self, parent_sha, filename, content):
        """Build a new commit, as a direct child of parent_sha, that adds
        `filename` — via plumbing only (read-tree/update-index/write-tree/
        commit-tree). Never touches any worktree's checked-out files or
        index, so it is inherently checkout-free with respect to
        self.integ_wt, mirroring how merge-task.sh advances a branch without
        ever checking it out."""
        scratch_index = self.tmp_path / f"scratch-index-{os.urandom(4).hex()}"
        index_env = dict(self.git_env)
        index_env["GIT_INDEX_FILE"] = str(scratch_index)

        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=str(self.main_repo),
            input=content,
            env=self.git_env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        subprocess.run(
            ["git", "read-tree", parent_sha],
            cwd=str(self.main_repo),
            env=index_env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{filename}"],
            cwd=str(self.main_repo),
            env=index_env,
            check=True,
            capture_output=True,
            text=True,
        )
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=str(self.main_repo),
            env=index_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        commit = subprocess.run(
            ["git", "commit-tree", tree, "-p", parent_sha, "-m", f"external: add {filename}"],
            cwd=str(self.main_repo),
            env=self.git_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return commit

    # -- AC-1 ------------------------------------------------------------

    def test_non_artifact_byproduct_present_without_ref_advance_commits(self):
        # references AC-1: a verify-phase-shaped byproduct sitting outside
        # every artifact root must never cause a false die-4.
        before = self._head(self.integ_wt)
        (Path(self.integ_wt) / "build-output.log").write_text("byproduct\n")
        self._write_artifact_change(self.integ_wt, content="pending notes\n")

        result = self._run_commit_docs(self.integ_wt, "docs(feat): update notes")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertNotEqual(before, after)
        subjects = self._log_subjects(self.integ_wt, 2)
        self.assertEqual(subjects, ["docs(feat): update notes", "initial commit"])
        # The byproduct was never staged/committed — it is still sitting
        # there, untracked, exactly as verify left it.
        status = self._git(self.integ_wt, "status", "--porcelain").stdout
        self.assertIn("?? build-output.log", status)

    def test_no_pending_changes_is_a_noop(self):
        # references AC-1 (no-op contract: nothing to commit, ref unchanged)
        before = self._head(self.integ_wt)

        result = self._run_commit_docs(self.integ_wt, "docs(feat): nothing changed")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertEqual(before, after)
        self.assertIn("NOOP", result.stdout)

    # -- AC-2 --------------------------------------------------------------

    def test_external_ref_advance_via_update_ref_dies_stale_then_refresh_and_retry_succeeds(self):
        # references AC-2 (dedicated die-4 test): a minimal, checkout-free
        # `update-ref` advance built purely from plumbing (no second
        # worktree), raced against a live commit-docs.sh run via a
        # lock-holder that performs the advance while holding the very lock
        # commit-docs.sh blocks on.
        hold_seconds = 1.0
        lock_path = self._resolve_lock_path(self.integ_wt)
        old_tip = self._head(self.integ_wt)
        new_tip = self._fabricate_child_commit(old_tip, "external.txt", "external content\n")

        holder_script = (
            f'exec 8>"{lock_path}" && flock 8 && sleep {hold_seconds} && '
            f'git -C "{self.main_repo}" update-ref "refs/heads/{PARENT_BRANCH}" {new_tip} {old_tip}'
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

        self._write_artifact_change(self.integ_wt, content="pending-before-die4\n")
        result = self._run_commit_docs(self.integ_wt, "docs(feat): should not commit")
        finished_at = time.monotonic() - holder_start

        holder_stdout, holder_stderr = holder.communicate(timeout=30)
        self.assertEqual(holder.returncode, 0, holder_stdout.decode() + holder_stderr.decode())
        # Proves real blocking (the advance genuinely landed inside
        # commit-docs.sh's before/after-lock window), not a lucky race.
        self.assertGreaterEqual(finished_at, hold_seconds - 0.2)

        self.assertEqual(result.returncode, EXIT_STALE, result.stdout + result.stderr)
        # Only the external advance landed; nothing of ours was committed.
        self.assertEqual(self._head(self.integ_wt), new_tip)

        # Recovery: refresh the worktree to the new tip, re-apply the doc
        # edit, retry once.
        self._git(self.integ_wt, "reset", "-q", "--hard", new_tip)
        self._write_artifact_change(self.integ_wt, content="pending-after-die4-refresh\n")
        retry = self._run_commit_docs(self.integ_wt, "docs(feat): after die-4 refresh")

        self.assertEqual(retry.returncode, EXIT_OK, retry.stdout + retry.stderr)
        subjects = self._log_subjects(self.integ_wt, 3)
        self.assertEqual(
            subjects,
            [
                "docs(feat): after die-4 refresh",
                "external: add external.txt",
                "initial commit",
            ],
        )
        # No merged content was reverted: the externally-added file survives.
        final_tree = self._git(self.integ_wt, "ls-tree", "-r", "--name-only", "HEAD").stdout
        self.assertIn("external.txt", final_tree)

    def test_concurrent_external_ref_advance_detected_and_recovers_with_linear_history(self):
        # references AC-2 (TS-4): a REAL checkout-free ref advance made from
        # a second worktree (mirrors merge-task.sh's fast-forward
        # update-ref mechanism — not a same-worktree commit), raced against
        # a live commit-docs.sh run.
        hold_seconds = 1.0
        lock_path = self._resolve_lock_path(self.integ_wt)
        old_tip = self._head(self.integ_wt)

        task_wt = self._add_worktree("task0099", PARENT_BRANCH)
        self._commit_file(task_wt, "external-change.txt", "external\n", "task0099: external change")
        new_tip = self._head(task_wt)

        holder_script = (
            f'exec 8>"{lock_path}" && flock 8 && sleep {hold_seconds} && '
            f'git -C "{self.main_repo}" update-ref "refs/heads/{PARENT_BRANCH}" {new_tip} {old_tip}'
        )
        holder_start = time.monotonic()
        holder = subprocess.Popen(
            ["bash", "-c", holder_script],
            env=self.git_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.3)

        self._write_artifact_change(self.integ_wt, content="pending-under-race\n")
        result = self._run_commit_docs(self.integ_wt, "docs(feat): update during race")
        finished_at = time.monotonic() - holder_start

        holder_stdout, holder_stderr = holder.communicate(timeout=30)
        self.assertEqual(holder.returncode, 0, holder_stdout.decode() + holder_stderr.decode())
        self.assertGreaterEqual(finished_at, hold_seconds - 0.2)

        self.assertEqual(result.returncode, EXIT_STALE, result.stdout + result.stderr)
        self.assertEqual(self._head(self.integ_wt), new_tip)

        # Recovery: refresh, re-apply, retry.
        self._git(self.integ_wt, "reset", "-q", "--hard", new_tip)
        self._write_artifact_change(self.integ_wt, content="pending-after-refresh\n")
        retry = self._run_commit_docs(self.integ_wt, "docs(feat): update after refresh")

        self.assertEqual(retry.returncode, EXIT_OK, retry.stdout + retry.stderr)
        subjects = self._log_subjects(self.integ_wt, 3)
        # Both commits survive, in linear order: neither the external
        # merge-task.sh-style advance nor commit-docs.sh's own commit is
        # lost or reverted.
        self.assertEqual(
            subjects,
            [
                "docs(feat): update after refresh",
                "task0099: external change",
                "initial commit",
            ],
        )
        final_tree = self._git(self.integ_wt, "ls-tree", "-r", "--name-only", "HEAD").stdout
        self.assertIn("external-change.txt", final_tree)

    # -- AC-3 ----------------------------------------------------------

    def test_tracked_deletion_under_artifact_root_is_staged_and_committed(self):
        # references AC-3
        artifact_path = self._write_artifact_change(self.integ_wt, content="v1\n")
        first = self._run_commit_docs(self.integ_wt, "docs(feat): add notes")
        self.assertEqual(first.returncode, EXIT_OK, first.stdout + first.stderr)

        artifact_path.unlink()

        result = self._run_commit_docs(self.integ_wt, "docs(feat): remove notes")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        subjects = self._log_subjects(self.integ_wt, 3)
        self.assertEqual(
            subjects,
            ["docs(feat): remove notes", "docs(feat): add notes", "initial commit"],
        )
        tracked = self._git(self.integ_wt, "ls-tree", "-r", "--name-only", "HEAD").stdout
        self.assertNotIn("notes.md", tracked)

    def test_top_level_artifact_file_deletion_is_staged_and_committed(self):
        # references AC-3 (cb2a99347619de01: the whole top-level artifact
        # FILE is removed, not just a file nested inside a directory
        # artifact root — the entry must not disappear from staging just
        # because `-e` on the root itself now fails).
        readme_path = Path(self.integ_wt) / "test" / "README.md"
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text("test conventions\n")
        first = self._run_commit_docs(self.integ_wt, "docs(feat): add test README")
        self.assertEqual(first.returncode, EXIT_OK, first.stdout + first.stderr)

        readme_path.unlink()
        self.assertFalse(readme_path.exists())

        result = self._run_commit_docs(self.integ_wt, "docs(feat): remove test README")

        self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)
        subjects = self._log_subjects(self.integ_wt, 3)
        self.assertEqual(
            subjects,
            [
                "docs(feat): remove test README",
                "docs(feat): add test README",
                "initial commit",
            ],
        )
        tracked = self._git(self.integ_wt, "ls-tree", "-r", "--name-only", "HEAD").stdout
        self.assertNotIn("test/README.md", tracked)

    def test_rename_from_artifact_to_non_artifact_path_fails_without_commit(self):
        # references AC-3 (e8313f5cad581a23: a staged rename must not let
        # content escape the artifact allowlist)
        self._write_artifact_change(self.integ_wt, content="v1\n")
        setup = self._run_commit_docs(self.integ_wt, "docs(feat): add notes")
        self.assertEqual(setup.returncode, EXIT_OK, setup.stdout + setup.stderr)
        before = self._head(self.integ_wt)

        self._git(self.integ_wt, "mv", DEFAULT_ARTIFACT_REL_PATH, "escaped-notes.md")

        result = self._run_commit_docs(self.integ_wt, "docs(feat): rename escape attempt")

        self.assertEqual(result.returncode, EXIT_GIT_FAILURE, result.stdout + result.stderr)
        self.assertEqual(self._head(self.integ_wt), before)  # no commit landed

    # -- AC-4 (full-suite alignment; contract regression coverage) --------

    def test_missing_path_fails_with_argument_failure_code(self):
        # references AC-4
        missing_path = self.tmp_path / "does-not-exist"

        result = self._run_commit_docs(missing_path, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)

    def test_non_git_directory_fails_with_argument_failure_code(self):
        # references AC-4
        plain_dir = self.tmp_path / "plain-dir"
        plain_dir.mkdir()

        result = self._run_commit_docs(plain_dir, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)

    def test_main_working_tree_is_rejected_as_not_linked(self):
        # references AC-4 (non-worktree path: the main working tree itself)
        before = self._head(self.main_repo)

        result = self._run_commit_docs(self.main_repo, "docs(feat): x")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)
        after = self._head(self.main_repo)
        self.assertEqual(before, after)

    def test_empty_message_fails_with_argument_failure_code(self):
        # references AC-4
        before = self._head(self.integ_wt)
        self._write_artifact_change(self.integ_wt)

        result = self._run_commit_docs(self.integ_wt, "")

        self.assertEqual(result.returncode, EXIT_ARG_FAILURE, result.stdout + result.stderr)
        after = self._head(self.integ_wt)
        self.assertEqual(before, after)

    # NOTE: the pre-task0006 version of this suite had a
    # "test_blocks_while_lock_held_then_commits_after_release_no_lost_update"
    # test here whose lock-holder committed DIRECTLY inside the same
    # worktree (self.integ_wt) while holding the lock, then asserted
    # commit-docs.sh succeeded afterward. That fixture encoded exactly the
    # "same-worktree commit" pattern residual finding dee0a6aac12247d6 calls
    # out as unfaithful to production (merge-task.sh always advances the
    # ref from a DIFFERENT worktree, checkout-free, never by committing
    # inside the parent's own worktree). Under the new ref-movement
    # contract (design point 1) that scenario IS genuine tip movement
    # during the lock wait and now correctly dies stale — the blocking +
    # serialization + no-lost-update guarantee that test intended to prove
    # is now covered faithfully by
    # test_concurrent_external_ref_advance_detected_and_recovers_with_linear_history
    # above, which races a REAL checkout-free advance from a second
    # worktree instead.

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
            self._write_artifact_change(self.integ_wt, "feature-docs/feat/for-lock-failure.md", "x\n")
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
        self._write_artifact_change(self.integ_wt, "feature-docs/feat/for-git-failure.md", "y\n")
        git_failure_result = self._run_commit_docs(self.integ_wt, "docs(feat): y")
        after = self._head(self.integ_wt)

        self.assertEqual(
            git_failure_result.returncode,
            EXIT_GIT_FAILURE,
            git_failure_result.stdout + git_failure_result.stderr,
        )
        self.assertEqual(before, after)

        self.assertNotEqual(lock_failure_result.returncode, git_failure_result.returncode)

    # -- TS-5: develop-shaped integration sequence ------------------------

    def test_develop_shaped_sequence_keeps_main_tree_clean_and_survives_hard_reset(self):
        # references AC-4 (TS-5): branch+worktree creation, per-update doc
        # commits, then a reconcile-style hard reset — the main working
        # tree stays clean throughout and no committed state is lost.
        feature = "ts5-feat"
        branch = f"em-workflow/{feature}/integration"

        # Ignore-guard (mirrors requirements-spec-creator Phase 3): gate on
        # `.claude/worktrees/` being ignored in the main tree BEFORE the
        # first `git worktree add`, so the main tree's status stays clean
        # from branch/worktree creation onward — including the base
        # fixture's own "feat" integration worktree created in setUp.
        probe = self._git(
            self.main_repo, "check-ignore", "-q", ".claude/worktrees/probe", check=False
        )
        if probe.returncode != 0:
            with open(self.main_repo / ".gitignore", "a") as f:
                f.write(".claude/worktrees/\n")

        self._git(self.main_repo, "branch", branch)
        wt_path = self.main_repo / ".claude" / "worktrees" / "em-workflow" / feature / "integration"
        self._git(self.main_repo, "worktree", "add", str(wt_path), branch)

        updates = [
            (
                f"feature-docs/{feature}/REQUIREMENTS.md",
                "requirements v1\n",
                f"docs({feature}): write REQUIREMENTS.md",
            ),
            (
                f"feature-docs/{feature}/SPEC.md",
                "spec v1\n",
                f"docs({feature}): write SPEC.md",
            ),
            (
                f"feature-docs/{feature}/workflow.yaml",
                "phase: plan\n",
                f"docs({feature}): update workflow.yaml",
            ),
        ]
        for rel_path, content, message in updates:
            path = wt_path / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            result = self._run_commit_docs(wt_path, message)
            self.assertEqual(result.returncode, EXIT_OK, result.stdout + result.stderr)

        head_before_reset = self._head(wt_path)

        # Reconcile-style recovery: safe because the worktree never carries
        # uncommitted state across turns (IMPLEMENTATION.md D2 / NFR2).
        self._git(wt_path, "reset", "-q", "--hard")

        self.assertEqual(self._head(wt_path), head_before_reset)
        subjects = self._log_subjects(wt_path, 4)
        self.assertEqual(
            subjects,
            [
                f"docs({feature}): update workflow.yaml",
                f"docs({feature}): write SPEC.md",
                f"docs({feature}): write REQUIREMENTS.md",
                "initial commit",
            ],
        )

        main_status = self._git(self.main_repo, "status", "--porcelain").stdout
        # Tolerate only a .gitignore-guard line; everything else in the main
        # tree must stay untouched throughout the whole sequence.
        unexpected_lines = [
            line
            for line in main_status.splitlines()
            if line.strip() and ".gitignore" not in line
        ]
        self.assertEqual(unexpected_lines, [], main_status)


if __name__ == "__main__":
    unittest.main()
