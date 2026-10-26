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
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
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

# Post-lock tests: merge-task.sh is started while the test holds the merge
# lock and is mutated underneath while it waits. The test synchronizes on the
# waiting `flock` child appearing in the process table (no fixed sleep); the
# deadline covers the script's pre-lock git calls plus process start-up.
FLOCK_CHILD_APPEARANCE_BOUND_SECONDS = 10
FLOCK_CHILD_POLL_INTERVAL_SECONDS = 0.02
# Upper bound (seconds) for the run to finish once the lock is released.
POST_LOCK_RUN_BOUND_SECONDS = 30
# Upper bound (seconds) for reaping the test's own child on a failure path.
CHILD_REAP_BOUND_SECONDS = 10

# RFC 3339 with an explicit offset (or "Z"); we assert the *format*, not an
# exact value, per the task plan's test notes.
RFC3339_OFFSET_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _has_flock_child(parent_pid):
    """True when the process table holds a process whose parent is
    `parent_pid` and whose command name is `flock` (Linux /proc)."""
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as stat_file:
                stat = stat_file.read()
        except OSError:
            continue  # the process ended between listing and reading
        # "<pid> (<comm>) <state> <ppid> ...": comm may itself hold spaces or
        # parentheses, so split around the last closing parenthesis.
        comm_end = stat.rfind(b")")
        comm = stat[stat.find(b"(") + 1 : comm_end].decode("utf-8", "replace")
        ppid = int(stat[comm_end + 2 :].split()[1])
        if ppid == parent_pid and comm == "flock":
            return True
    return False


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

    def _run_merge(self, worktree, task_id, parent_branch=PARENT_BRANCH, env=None):
        return subprocess.run(
            [str(MERGE_SCRIPT), parent_branch, task_id],
            cwd=str(worktree),
            env=self.git_env if env is None else env,
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

    # -- harness for the post-lock tests -----------------------------------

    def _wait_for_flock_child(self, child):
        """Block until `child` (the launched merge-task.sh) is waiting on the
        merge lock, i.e. a `flock` process whose parent is `child` exists. A
        child that ends first, or no `flock` child by the deadline, fails the
        test."""
        deadline = time.monotonic() + FLOCK_CHILD_APPEARANCE_BOUND_SECONDS
        while not _has_flock_child(child.pid):
            if child.poll() is not None:
                stdout, stderr = child.communicate()
                self.fail(
                    f"merge-task.sh ended with exit {child.returncode} before it "
                    f"waited on the merge lock\n{stdout}{stderr}"
                )
            if time.monotonic() >= deadline:
                self.fail(
                    f"no flock child of merge-task.sh appeared within "
                    f"{FLOCK_CHILD_APPEARANCE_BOUND_SECONDS}s"
                )
            time.sleep(FLOCK_CHILD_POLL_INTERVAL_SECONDS)

    def _reap_own_child(self, child):
        """End and reap the test's own launched child, through its handle
        only, when it is still running. The waiting `flock` grandchild is not
        signalled: the lock is already released, so it finishes by itself."""
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=CHILD_REAP_BOUND_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=CHILD_REAP_BOUND_SECONDS)
        for pipe in (child.stdout, child.stderr):
            if pipe is not None:
                pipe.close()

    def _run_merge_with_mutation_during_lock_wait(self, worktree, task_id, mutate):
        """Start merge-task.sh in `worktree` while the test holds the merge
        lock, wait until the script is blocked on that lock, call `mutate()`
        (the caller's change to the worktree), release the lock and return
        the finished run as a CompletedProcess. Every exit path releases the
        lock first, then ends and reaps the launched child if it still runs."""
        child = None
        try:
            with self._hold_merge_lock():
                child = subprocess.Popen(
                    [str(MERGE_SCRIPT), PARENT_BRANCH, task_id],
                    cwd=str(worktree),
                    env=self.git_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self._wait_for_flock_child(child)
                mutate()
            try:
                stdout, stderr = child.communicate(timeout=POST_LOCK_RUN_BOUND_SECONDS)
            except subprocess.TimeoutExpired:
                self.fail(
                    f"merge-task.sh still running {POST_LOCK_RUN_BOUND_SECONDS}s "
                    "after the merge lock was released"
                )
            return subprocess.CompletedProcess(
                child.args, child.returncode, stdout, stderr
            )
        finally:
            if child is not None:
                self._reap_own_child(child)

    def _assert_identity_error_names(self, result, *refs):
        """One ERROR line on stderr carries every ref in `refs`."""
        error_lines = [
            line for line in result.stderr.splitlines() if line.startswith("ERROR")
        ]
        self.assertTrue(
            any(all(ref in line for ref in refs) for line in error_lines),
            f"no ERROR line names {refs}: {result.stderr!r}",
        )

    def _assert_no_dirty_worktree_wording(self, result):
        for wording in ("uncommitted", "untracked", "commit everything"):
            self.assertNotIn(wording, result.stderr)

    def _exact_ref_value(self, ref):
        """The object ID stored under the exact full ref name `ref` (git's
        exact verification lookup, no ambiguous-name resolution), or None when
        that exact ref is absent."""
        result = self._git(
            self.main_repo, "show-ref", "--verify", "--hash", "--", ref, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _assert_failed_without_ref_or_journal_side_effects(self, result):
        """Exit 2 with an ERROR line and no journal.jsonl anywhere under the
        test's temporary directory. The ref checks stay with the caller: these
        tests plant refs the integration-branch helper above would resolve by
        name."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ERROR", result.stderr)
        self.assertEqual(list(self.tmp_path.rglob("journal.jsonl")), [])

    # -- helpers for the integration-ref symbolic-ref tests ----------------
    # (merge-task-parent-symref-reject task0001). The helpers that resolve the
    # integration branch by name (_parent_sha, _assert_rejected_without_side_
    # effects) follow a symbolic ref, so the symref cases judge ref values
    # through exact lookups (_exact_ref_value) of the referent and the task
    # ref, and the symbolic ref itself through _parent_symbolic_target.

    def _point_parent_ref_at(self, target):
        """Make refs/heads/<integration branch> a symbolic ref targeting the
        full ref name `target` (the referent need not exist)."""
        self._git(
            self.main_repo, "symbolic-ref", f"refs/heads/{PARENT_BRANCH}", target
        )

    def _parent_symbolic_target(self):
        """The ref name refs/heads/<integration branch> points at, or None
        when that ref is not a symbolic ref."""
        result = self._git(
            self.main_repo,
            "symbolic-ref",
            "--quiet",
            f"refs/heads/{PARENT_BRANCH}",
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _assert_symref_case_rejected(self, result, names_symbolic_ref=False):
        """Exit 2; exactly one ERROR line, and it names PARENT_BRANCH (and, when
        requested, says "symbolic ref"); no dirty-worktree wording; no
        journal.jsonl anywhere under the test's temporary directory."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        error_lines = [
            line for line in result.stderr.splitlines() if line.startswith("ERROR")
        ]
        self.assertEqual(len(error_lines), 1, result.stderr)
        self.assertIn(PARENT_BRANCH, error_lines[0])
        if names_symbolic_ref:
            self.assertIn("symbolic ref", error_lines[0])
        self._assert_no_dirty_worktree_wording(result)
        self.assertEqual(list(self.tmp_path.rglob("journal.jsonl")), [])

    def _create_branch_diverged_from_task(self, branch):
        """A branch with one commit (on a file the task commit does not touch)
        on top of the integration tip, built in a side worktree so the main
        working tree's checkout is untouched. Returns its full ref name."""
        side_worktree = self.tmp_path / "side-worktree"
        self._git(
            self.main_repo,
            "worktree",
            "add",
            "-q",
            "-b",
            branch,
            str(side_worktree),
            PARENT_BRANCH,
        )
        self._commit_file(
            side_worktree, "side.txt", "side change\n", "side: diverging commit"
        )
        return f"refs/heads/{branch}"

    def _build_git_shim(self, mode):
        """Write an executable `git` into a fresh directory under the test's
        temporary directory and return (env, record_dir): `env` is the git
        environment with that directory first on PATH, `record_dir` holds one
        file per interception. Every invocation goes to the real git
        (absolute path resolved here, before the shim exists) with its
        arguments, working directory, output and exit status, except:

        - "repoint": the first invocation whose subcommand is update-ref and
          whose arguments include refs/heads/<integration branch> first makes
          that ref a symbolic ref targeting refs/heads/main through the real
          git and records the interception, then hands the original
          invocation to the real git.
        - "status": every invocation whose subcommand is symbolic-ref and
          whose arguments include refs/heads/<integration branch> records the
          interception and exits 128 without calling git.

        The returned env is meant for the merge-task.sh subprocess only; the
        test's own git calls use self.git_env."""
        self.assertIn(mode, ("repoint", "status"))
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git not found on PATH")
        shim_dir = Path(tempfile.mkdtemp(dir=self.tmp_path, prefix="git-shim-"))
        record_dir = Path(tempfile.mkdtemp(dir=self.tmp_path, prefix="git-shim-records-"))
        parent_ref = f"refs/heads/{PARENT_BRANCH}"
        record = (
            'n=1; while [ -e "$RECORD_DIR/interception-$n" ]; do n=$((n+1)); done; '
            ': > "$RECORD_DIR/interception-$n"'
        )
        if mode == "repoint":
            body = (
                'if [ "$1" = update-ref ]; then\n'
                '  for arg in "$@"; do\n'
                '    if [ "$arg" = "$PARENT_REF" ]; then\n'
                '      if [ ! -e "$RECORD_DIR/interception-1" ]; then\n'
                '        "$REAL_GIT" symbolic-ref "$PARENT_REF" refs/heads/main \\\n'
                '          || { echo "git shim: re-point failed" >&2; exit 99; }\n'
                f"        {record}\n"
                "      fi\n"
                "      break\n"
                "    fi\n"
                "  done\n"
                "fi\n"
            )
        else:
            body = (
                'if [ "$1" = symbolic-ref ]; then\n'
                '  for arg in "$@"; do\n'
                '    if [ "$arg" = "$PARENT_REF" ]; then\n'
                f"      {record}\n"
                "      exit 128\n"
                "    fi\n"
                "  done\n"
                "fi\n"
            )
        script = (
            "#!/bin/sh\n"
            f"REAL_GIT={shlex.quote(real_git)}\n"
            f"PARENT_REF={shlex.quote(parent_ref)}\n"
            f"RECORD_DIR={shlex.quote(str(record_dir))}\n"
            + body
            + 'exec "$REAL_GIT" "$@"\n'
        )
        shim_path = shim_dir / "git"
        shim_path.write_text(script)
        os.chmod(shim_path, 0o755)
        env = dict(self.git_env)
        env["PATH"] = f"{shim_dir}{os.pathsep}{self.git_env['PATH']}"
        return env, record_dir

    def _count_interceptions(self, record_dir):
        return len(list(Path(record_dir).iterdir()))

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

    # -- merge-task-post-lock-rebind task0001: identity re-check after the
    # merge lock. The test holds the lock, merge-task.sh waits on it, the
    # worktree is changed during the wait, then the lock is released.

    def _task_worktree_with_commit_to_merge(self, task_id):
        wt = self._add_task_worktree(FEATURE, task_id)
        self._commit_file(wt, "feature.txt", "hello\n", f"{task_id}: add feature file")
        return wt

    def test_branch_switch_during_lock_wait_is_rejected_without_side_effects(self):
        # references AC-1 / TS-1
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()

        result = self._run_merge_with_mutation_during_lock_wait(
            wt,
            task_id,
            lambda: self._git(wt, "checkout", "-q", "-b", "switched-during-wait"),
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self._assert_identity_error_names(
            result,
            f"refs/heads/em-workflow/{FEATURE}/{task_id}",
            "refs/heads/switched-during-wait",
        )

    def test_branch_switch_with_untracked_file_during_lock_wait_reports_identity_rejection(
        self,
    ):
        # references AC-2 / TS-2
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()

        def switch_and_dirty():
            self._git(wt, "checkout", "-q", "-b", "switched-during-wait")
            (wt / "untracked.txt").write_text("not committed\n")

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, switch_and_dirty
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self._assert_identity_error_names(
            result,
            f"refs/heads/em-workflow/{FEATURE}/{task_id}",
            "refs/heads/switched-during-wait",
        )
        self._assert_no_dirty_worktree_wording(result)

    def test_detached_head_during_lock_wait_is_rejected_without_side_effects(self):
        # references AC-3 / TS-5
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: self._git(wt, "checkout", "-q", "--detach")
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self._assert_identity_error_names(
            result, f"refs/heads/em-workflow/{FEATURE}/{task_id}", "detached"
        )

    def test_task_ref_deleted_during_lock_wait_is_rejected_without_side_effects(self):
        # references AC-4 / TS-6 (the run may already stop at the
        # clean-tree check: only exit 2, an ERROR line and no side effects
        # are required)
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()

        result = self._run_merge_with_mutation_during_lock_wait(
            wt,
            task_id,
            lambda: self._git(
                wt, "update-ref", "-d", f"refs/heads/em-workflow/{FEATURE}/{task_id}"
            ),
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_task_ref_deleted_in_a_clean_worktree_is_rejected_at_the_merge_source(self):
        # references AC-4 / TS-6: with the tracked files removed as well, the
        # worktree is clean on the unborn branch, so only the merge-source
        # resolution from the verified task ref can reject the run.
        # references FR6 / TS-1 of merge-task-exact-ref-resolve: the tag
        # refs/tags/<task ref> sits at a commit that is a child of the
        # integration tip and is on no branch. A name lookup of the deleted
        # task ref would resolve to that tag and fast-forward the integration
        # branch to it; the exact-ref lookup must not.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()
        parent_tree = self._git(
            self.main_repo, "rev-parse", f"{parent_before}^{{tree}}"
        ).stdout.strip()
        tagged_commit = self._git(
            self.main_repo,
            "commit-tree",
            parent_tree,
            "-p",
            parent_before,
            "-m",
            "off-branch commit under a same-named tag",
        ).stdout.strip()
        tag_ref = f"refs/tags/refs/heads/em-workflow/{FEATURE}/{task_id}"
        self._git(self.main_repo, "update-ref", tag_ref, tagged_commit)

        def delete_ref_and_empty_worktree():
            self._git(wt, "update-ref", "-d", f"refs/heads/em-workflow/{FEATURE}/{task_id}")
            self._git(wt, "rm", "-r", "-q", "-f", ".")

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, delete_ref_and_empty_worktree
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self._assert_identity_error_names(
            result, f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        )
        self._assert_no_dirty_worktree_wording(result)
        self.assertEqual(self._exact_ref_value(tag_ref), tagged_commit)

    def test_parent_ref_deleted_with_a_same_named_tag_is_rejected_without_side_effects(
        self,
    ):
        # references FR7 / FR8 / TS-3 of merge-task-exact-ref-resolve: with the
        # exact integration ref gone and the tag refs/tags/<integration ref>
        # at the task tip, a name lookup of the parent would resolve to that
        # tag and report the task as already contained (exit 0, a `merged`
        # event); the exact-ref lookup must reject the run instead. The
        # integration branch is absent, so the side effects are checked on the
        # exact refs and the journal rather than on the integration history.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_ref = f"refs/heads/{PARENT_BRANCH}"
        tag_ref = f"refs/tags/{parent_ref}"
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        task_tip = self._exact_ref_value(task_ref)
        self.assertIsNotNone(task_tip)

        def delete_parent_and_plant_tag():
            self._git(self.main_repo, "update-ref", "-d", parent_ref)
            self._git(self.main_repo, "update-ref", tag_ref, task_tip)

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, delete_parent_and_plant_tag
        )

        self._assert_failed_without_ref_or_journal_side_effects(result)
        self._assert_identity_error_names(result, PARENT_BRANCH)
        self.assertIsNone(self._exact_ref_value(parent_ref))
        self.assertEqual(self._exact_ref_value(tag_ref), task_tip)
        self.assertEqual(self._exact_ref_value(task_ref), task_tip)

    def test_task_ref_pointing_at_a_non_commit_during_lock_wait_is_rejected_without_side_effects(
        self,
    ):
        # references FR3 / TS-4 of merge-task-exact-ref-resolve: git refuses
        # to update a branch ref to a non-commit object, so the loose ref file
        # is written directly. The run may stop at the clean-tree check or at
        # the commit-type check: only exit 2, an ERROR line and no side
        # effects are required.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()
        tree_oid = self._git(wt, "rev-parse", "HEAD^{tree}").stdout.strip()
        task_ref_file = (
            self.main_repo / ".git" / "refs" / "heads" / "em-workflow" / FEATURE / task_id
        )
        self.assertTrue(task_ref_file.is_file())

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: task_ref_file.write_text(tree_oid + "\n")
        )

        self._assert_rejected_without_side_effects(result, task_id, parent_before)

    def test_parent_ref_pointing_at_a_non_commit_is_rejected_without_side_effects(self):
        # references SPEC.md A3 of merge-task-exact-ref-resolve: the pre-lock
        # binding compares only the parent branch's name, so the integration
        # ref can point at a non-commit object before the run. The
        # integration-branch history cannot be read here, so the side effects
        # are checked on the exact refs and the journal.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_ref = f"refs/heads/{PARENT_BRANCH}"
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        task_tip = self._exact_ref_value(task_ref)
        tree_oid = self._git(wt, "rev-parse", "HEAD^{tree}").stdout.strip()
        parent_ref_file = (
            self.main_repo / ".git" / "refs" / "heads" / "em-workflow" / FEATURE / "integration"
        )
        self.assertTrue(parent_ref_file.is_file())
        parent_ref_file.write_text(tree_oid + "\n")
        self.assertEqual(self._exact_ref_value(parent_ref), tree_oid)

        result = self._run_merge(wt, task_id)

        self._assert_failed_without_ref_or_journal_side_effects(result)
        self.assertEqual(self._exact_ref_value(parent_ref), tree_oid)
        self.assertEqual(self._exact_ref_value(task_ref), task_tip)

    def test_new_commit_on_task_branch_during_lock_wait_is_merged(self):
        # references AC-4 / TS-7
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)

        def commit_late():
            self._commit_file(wt, "late.txt", "late\n", f"{task_id}: late commit")

        result = self._run_merge_with_mutation_during_lock_wait(wt, task_id, commit_late)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        late_sha = self._git(wt, "rev-parse", "HEAD").stdout.strip()
        contained = self._git(
            self.main_repo, "merge-base", "--is-ancestor", late_sha, PARENT_BRANCH, check=False
        )
        self.assertEqual(contained.returncode, 0, "the late commit is not in the integration branch")
        merged = [
            json.loads(line)
            for line in self._read_journal_lines(FEATURE)
            if json.loads(line)["event"] == "merged" and json.loads(line)["task"] == task_id
        ]
        self.assertEqual(len(merged), 1)

    # -- merge-task-parent-symref-reject task0001: the integration ref must be
    # a direct ref. Under the merge lock, a symbolic ref at
    # refs/heads/<integration branch> (dangling included), or an
    # undeterminable answer, ends the run with exit 2 before any ref update;
    # both update-ref calls on the integration ref use the no-deref option.

    def test_parent_ref_repointed_to_task_ref_during_lock_wait_is_rejected(self):
        # references AC-1 (a) / TS-1: the unmodified script resolves the
        # parent through the symbolic ref to the task tip, takes the
        # already-contained path and appends a `merged` event.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        task_tip = self._exact_ref_value(task_ref)
        self.assertIsNotNone(task_tip)

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: self._point_parent_ref_at(task_ref)
        )

        self._assert_symref_case_rejected(result, names_symbolic_ref=True)
        self.assertEqual(self._exact_ref_value(task_ref), task_tip)
        self.assertEqual(self._parent_symbolic_target(), task_ref)

    def test_parent_ref_repointed_to_main_at_fast_forward_position_during_lock_wait_is_rejected(
        self,
    ):
        # references AC-1 (b) / TS-2: main is the initial commit, an ancestor
        # of the task tip, so the unmodified script would fast-forward main.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        main_ref = "refs/heads/main"
        task_tip = self._exact_ref_value(task_ref)
        main_before = self._exact_ref_value(main_ref)
        self.assertIsNotNone(main_before)
        self.assertEqual(
            self._git(
                self.main_repo, "merge-base", "--is-ancestor", main_before, task_tip,
                check=False,
            ).returncode,
            0,
            "fixture: main must sit at a fast-forward position",
        )

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: self._point_parent_ref_at(main_ref)
        )

        self._assert_symref_case_rejected(result, names_symbolic_ref=True)
        self.assertEqual(self._exact_ref_value(main_ref), main_before)
        self.assertEqual(self._exact_ref_value(task_ref), task_tip)
        self.assertEqual(self._parent_symbolic_target(), main_ref)

    def test_parent_ref_repointed_to_diverged_branch_during_lock_wait_is_rejected(self):
        # references AC-1 (c) / TS-3: the side branch and the task tip are
        # unrelated by ancestry and touch different files, so the unmodified
        # script would create a merge commit on the side branch.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        task_tip = self._exact_ref_value(task_ref)
        side_ref = self._create_branch_diverged_from_task("diverged-side")
        side_before = self._exact_ref_value(side_ref)
        self.assertIsNotNone(side_before)

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: self._point_parent_ref_at(side_ref)
        )

        self._assert_symref_case_rejected(result, names_symbolic_ref=True)
        self.assertEqual(self._exact_ref_value(side_ref), side_before)
        self.assertEqual(self._exact_ref_value(task_ref), task_tip)
        subjects = self._git(
            self.main_repo, "log", "--format=%s", side_ref
        ).stdout.splitlines()
        self.assertNotIn(f"merge: {task_id}", subjects)
        self.assertEqual(self._parent_symbolic_target(), side_ref)

    def test_parent_ref_already_a_symbolic_ref_to_main_is_rejected(self):
        # references AC-2 (a) / TS-4: no lock wait; the symbolic ref exists
        # before the run.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        main_ref = "refs/heads/main"
        main_before = self._exact_ref_value(main_ref)
        self._point_parent_ref_at(main_ref)

        result = self._run_merge(wt, task_id)

        self._assert_symref_case_rejected(result, names_symbolic_ref=True)
        self.assertEqual(self._exact_ref_value(main_ref), main_before)
        self.assertEqual(self._parent_symbolic_target(), main_ref)

    def test_parent_ref_a_dangling_symbolic_ref_is_rejected_as_a_symbolic_ref(self):
        # references AC-2 (b) / TS-5: the unmodified script already ends with
        # exit 2 here (the parent lookup fails) but with a different message.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        absent_ref = "refs/heads/no-such-target"
        self.assertIsNone(self._exact_ref_value(absent_ref))
        self._point_parent_ref_at(absent_ref)

        result = self._run_merge(wt, task_id)

        self._assert_symref_case_rejected(result, names_symbolic_ref=True)
        self.assertIsNone(self._exact_ref_value(absent_ref))
        self.assertEqual(self._parent_symbolic_target(), absent_ref)

    def test_undeterminable_symbolic_ref_status_of_parent_ref_is_rejected(self):
        # references AC-3 / TS-9: the git shim makes the symbolic-ref query on
        # the integration ref exit 128 (neither 0 nor 1). The unmodified
        # script never asks, so the shim sees no interception and the merge
        # succeeds.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        parent_before = self._parent_sha()
        env, records = self._build_git_shim("status")

        result = self._run_merge(wt, task_id, env=env)

        self._assert_symref_case_rejected(result)
        self.assertIn("128", result.stderr)
        self._assert_rejected_without_side_effects(result, task_id, parent_before)
        self.assertGreaterEqual(self._count_interceptions(records), 1)

    def test_update_ref_does_not_follow_symbolic_ref_planted_before_fast_forward(self):
        # references AC-4 / TS-8 (fast-forward path): main's tip equals the
        # integration tip (true in the base fixture), and the shim re-points
        # the integration ref to main right before the update-ref. Only main's
        # value and the interception count are asserted: with the no-deref
        # option git may reject the update or replace the symbolic ref by a
        # direct ref.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        main_ref = "refs/heads/main"
        main_before = self._exact_ref_value(main_ref)
        self.assertEqual(main_before, self._parent_sha())
        env, records = self._build_git_shim("repoint")

        self._run_merge(wt, task_id, env=env)

        self.assertEqual(self._exact_ref_value(main_ref), main_before)
        self.assertEqual(self._count_interceptions(records), 1)

    def test_update_ref_does_not_follow_symbolic_ref_planted_before_merge_commit(self):
        # references AC-4 / TS-8 (merge-commit path): the integration branch is
        # advanced with an unrelated commit first, then main is moved to the
        # integration tip so the old values are equal.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        self._commit_file(
            self.main_repo,
            "parent-file.txt",
            "parent change\n",
            "integration: unrelated advance",
        )
        main_ref = "refs/heads/main"
        self._git(self.main_repo, "branch", "-f", "main", PARENT_BRANCH)
        main_before = self._exact_ref_value(main_ref)
        self.assertEqual(main_before, self._parent_sha())
        env, records = self._build_git_shim("repoint")

        self._run_merge(wt, task_id, env=env)

        self.assertEqual(self._exact_ref_value(main_ref), main_before)
        self.assertEqual(self._count_interceptions(records), 1)

    def test_task_ref_repointed_to_symbolic_ref_of_another_branch_during_lock_wait_is_rejected(
        self,
    ):
        # references AC-5 / TS-7 (existing behaviour pinned): the post-lock HEAD
        # re-check resolves the task ref recursively and rejects the run.
        task_id = "task0001"
        wt = self._task_worktree_with_commit_to_merge(task_id)
        self._git(self.main_repo, "branch", "other-branch", "main")
        task_ref = f"refs/heads/em-workflow/{FEATURE}/{task_id}"
        other_ref = "refs/heads/other-branch"
        parent_ref = f"refs/heads/{PARENT_BRANCH}"
        other_before = self._exact_ref_value(other_ref)
        parent_before = self._exact_ref_value(parent_ref)
        self.assertIsNotNone(other_before)

        result = self._run_merge_with_mutation_during_lock_wait(
            wt, task_id, lambda: self._git(wt, "symbolic-ref", task_ref, other_ref)
        )

        self._assert_failed_without_ref_or_journal_side_effects(result)
        self._assert_identity_error_names(result, task_ref)
        self.assertEqual(self._exact_ref_value(other_ref), other_before)
        self.assertEqual(self._exact_ref_value(parent_ref), parent_before)


if __name__ == "__main__":
    unittest.main()
