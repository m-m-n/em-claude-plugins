"""Behavior and static tests of em-workflow/scripts/cleanup-task.py.

Covers AC-1..AC-7 of feature-docs/wake-task-cleanup-script/tasks/task0001.md.

Every behavior test builds a disposable git repository in a temporary
directory (system and global git configuration disabled, fixed author
identity): a repository on `main`, the integration branch checked out as a
worktree at `.claude/worktrees/em-workflow/<feature>/integration`, and, where a
test needs one, a task branch with one commit checked out as a worktree next to
it. The script runs as a child process with bytecode writing off and is never
imported, so no bytecode cache is written under em-workflow/scripts/. Its
`PATH` carries a logging shim in front of the real git; the fixture's own git
commands run without the shim.

Every exit-0 run of the script is checked against the result JSON contract
(one line, one object, exactly the keys of IMPLEMENTATION.md C2), and the git
invocations the shim logged are checked against the invocation policy (no
forcing flag, no prune, the integration worktree as repository location, the
exact `branch -d <task branch>` deletion).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "cleanup-task.py"

FEATURE = "demo-feature"
TASK = "task0001"
INTEGRATION_BRANCH = f"em-workflow/{FEATURE}/integration"
TASK_BRANCH = f"em-workflow/{FEATURE}/{TASK}"
TASK_REF = f"refs/heads/{TASK_BRANCH}"

RESULT_KEYS = {"feature", "task", "worktree", "branch"}
WORKTREE_RESULTS = {"removed", "absent", "kept"}
BRANCH_RESULTS = {"removed", "absent", "kept", "skipped"}

# A flag that removes by force, or a prune, in the argument list of a git call.
FORCING_SHORT_FLAG = re.compile(r"-[A-Za-z]*[Df][A-Za-z]*")

# AC-7 static scan: a forcing flag as a standalone token (not preceded or
# followed by a letter, a digit, "_" or "-").
STANDALONE_FORCING_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])(?:-D|--force|-f)(?![A-Za-z0-9_-])")


# --------------------------------------------------------------------------
# The shim log and the invocation policy (AC-7 dynamic part)
# --------------------------------------------------------------------------


def parse_invocation(args):
    """Split one git argument list into (repository locations, subcommand part).

    Leading options are skipped; `-C <path>` contributes a repository
    location, `-c <key=value>` is skipped together with its value.
    """
    locations = []
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C":
            if i + 1 < len(args):
                locations.append(args[i + 1])
            i += 2
        elif args[i] == "-c":
            i += 2
        else:
            i += 1
    return locations, args[i:]


def forbidden_token(token):
    if token == "prune" or token.startswith("--prune"):
        return True
    if token.startswith("--force"):
        return True
    return FORCING_SHORT_FLAG.fullmatch(token) is not None


def policy_violations(calls, integration_worktree, branch):
    """Every way the logged git calls break the invocation policy of AC-7."""
    problems = []
    for args in calls:
        for token in args:
            if forbidden_token(token):
                problems.append(f"forbidden token {token!r} in {args}")
        locations, sub = parse_invocation(args)
        if locations != [integration_worktree]:
            problems.append(f"repository location {locations} is not the integration worktree in {args}")
        if sub[:1] == ["branch"] and sub != ["branch", "-d", branch]:
            problems.append(f"branch invocation is not 'branch -d <task branch>' in {args}")
    return problems


# --------------------------------------------------------------------------
# Fixture
# --------------------------------------------------------------------------


class CleanupBase(unittest.TestCase):
    """A temporary repository with the integration worktree, plus the shim."""

    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "the script under test does not exist: em-workflow/scripts/cleanup-task.py")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Real path first, so registered paths and expected paths agree on
        # systems whose temporary directory is a symbolic link.
        self.tmp = Path(os.path.realpath(self._tmp.name))

        home = self.tmp / "home"
        home.mkdir()
        self.git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.git_env.update(
            {
                "HOME": str(home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )

        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("readme\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.wt_dir = self.repo / ".claude" / "worktrees" / "em-workflow" / FEATURE
        self.iw = self.wt_dir / "integration"
        self.task_wt = self.wt_dir / TASK
        self.git("worktree", "add", "-q", "-b", INTEGRATION_BRANCH, str(self.iw), "main")

        self.git_log = self.tmp / "git-shim.log"
        self.shim_dir = self.tmp / "shims"
        self.shim_dir.mkdir()
        real_git = shutil.which("git")
        shim = self.shim_dir / "git"
        shim.write_text(
            "#!/bin/sh\n"
            '{ for a in "$@"; do printf \'%s\\n\' "$a"; done; printf -- \'--END--\\n\'; }'
            ' >> "$GIT_SHIM_LOG"\n'
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)

    # -- fixture builders -------------------------------------------------

    def git(self, *args, cwd=None):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo),
            env=self.git_env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout.strip()

    def git_rc(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo),
            env=self.git_env,
            capture_output=True,
            text=True,
        ).returncode

    def add_task(self):
        """The task branch (one commit on top of the integration branch) checked out at the task worktree."""
        self.git("worktree", "add", "-q", "-b", TASK_BRANCH, str(self.task_wt), INTEGRATION_BRANCH)
        (self.task_wt / "task.txt").write_text("task work\n", encoding="utf-8")
        self.git("add", "-A", cwd=self.task_wt)
        self.git("commit", "-q", "-m", "task work", cwd=self.task_wt)

    def add_detached_task_worktree(self):
        """A task worktree on a detached HEAD; no task branch exists."""
        self.git("worktree", "add", "-q", "--detach", str(self.task_wt), INTEGRATION_BRANCH)

    def merge_task_into_integration(self):
        self.git("merge", "-q", "--no-ff", "-m", "merge task", TASK_BRANCH, cwd=self.iw)

    def remove_task_worktree_keeping_branch(self):
        self.git("worktree", "remove", str(self.task_wt))

    # -- repository state -------------------------------------------------

    def ref_sha(self, ref):
        proc = subprocess.run(
            ["git", "show-ref", "--verify", "--hash", "--", ref],
            cwd=str(self.repo),
            env=self.git_env,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None

    def registered_paths(self):
        out = self.git("worktree", "list", "--porcelain")
        return [line[len("worktree "):] for line in out.splitlines() if line.startswith("worktree ")]

    def state(self):
        """Integration branch tip, registration list and the task ref."""
        return (
            self.ref_sha(f"refs/heads/{INTEGRATION_BRANCH}"),
            self.registered_paths(),
            self.ref_sha(TASK_REF),
        )

    # -- running the script -----------------------------------------------

    def script_env(self, extra=None):
        env = dict(self.git_env)
        env["PATH"] = str(self.shim_dir) + os.pathsep + env.get("PATH", "")
        env["GIT_SHIM_LOG"] = str(self.git_log)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.update(extra or {})
        return env

    def argv(self, iw=None, feature=FEATURE, task=TASK):
        iw = str(self.iw) if iw is None else iw
        return ["--integration-worktree", iw, "--feature", feature, "--task", task]

    def run_raw(self, argv, cwd=None, env_extra=None, env=None):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *argv],
            cwd=str(cwd or self.tmp),
            env=self.script_env(env_extra) if env is None else env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def run_cleanup(self, cwd=None, env_extra=None, argv=None):
        """Run with the valid inputs, require exit 0 and a conforming result."""
        proc = self.run_raw(self.argv() if argv is None else argv, cwd=cwd, env_extra=env_extra)
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")
        result = self.parse_result(proc.stdout)
        self.assert_git_policy()
        return result

    # -- the shim log -----------------------------------------------------

    def git_calls(self):
        if not self.git_log.exists():
            return []
        calls, current = [], []
        for line in self.git_log.read_text(encoding="utf-8").splitlines():
            if line == "--END--":
                calls.append(current)
                current = []
            else:
                current.append(line)
        return calls

    def git_subcommands(self):
        return [(parse_invocation(args)[1] or [""])[0] for args in self.git_calls()]

    def git_subcommand_prefixes(self):
        """The subcommand and its first argument of every logged git call."""
        return [parse_invocation(args)[1][:2] for args in self.git_calls()]

    def assert_git_policy(self, integration_worktree=None):
        iw = str(self.iw) if integration_worktree is None else integration_worktree
        self.assertEqual(policy_violations(self.git_calls(), iw, TASK_BRANCH), [])

    # -- result contract (IMPLEMENTATION.md C2) -----------------------------

    def parse_result(self, stdout):
        self.assertTrue(stdout.endswith("\n"), repr(stdout))
        lines = stdout.splitlines()
        self.assertEqual(len(lines), 1, f"stdout must be exactly one line: {stdout!r}")
        result = json.loads(lines[0])
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result), RESULT_KEYS, result)
        self.assertEqual(result["feature"], FEATURE)
        self.assertEqual(result["task"], TASK)

        worktree, branch = result["worktree"], result["branch"]
        self.assertIsInstance(worktree, dict)
        self.assertEqual(set(worktree), {"result", "reason"}, worktree)
        self.assertIn(worktree["result"], WORKTREE_RESULTS, worktree)
        if worktree["result"] == "kept":
            self.assertIsInstance(worktree["reason"], str, worktree)
            self.assertTrue(worktree["reason"].strip(), worktree)
        else:
            self.assertIsNone(worktree["reason"], worktree)

        self.assertIsInstance(branch, dict)
        self.assertEqual(set(branch), {"name", "result", "reason"}, branch)
        self.assertEqual(branch["name"], TASK_BRANCH)
        self.assertIn(branch["result"], BRANCH_RESULTS, branch)
        if branch["result"] in ("kept", "skipped"):
            self.assertIsInstance(branch["reason"], str, branch)
            self.assertTrue(branch["reason"].strip(), branch)
        else:
            self.assertIsNone(branch["reason"], branch)

        # FR6: the branch deletion is skipped exactly when the worktree is kept.
        self.assertEqual(branch["result"] == "skipped", worktree["result"] == "kept", result)
        return result


# --------------------------------------------------------------------------
# AC-1: invalid input
# --------------------------------------------------------------------------


class TestAC1InvalidInput(CleanupBase):
    """AC-1 (FR1, FR5, TM-1, TS-6): invalid input exits 2 before any git command."""

    def setUp(self):
        super().setUp()
        self.add_task()

    def make_dir(self, *parts):
        path = self.tmp.joinpath(*parts)
        path.mkdir(parents=True)
        return path

    def assert_rejected(self, label, argv, cwd=None):
        before = self.state()
        if self.git_log.exists():
            self.git_log.unlink()
        proc = self.run_raw(argv, cwd=cwd)
        self.assertEqual(proc.returncode, 2, f"{label}: stderr: {proc.stderr}")
        self.assertEqual(proc.stdout, "", label)
        self.assertEqual(self.git_calls(), [], label)
        self.assertEqual(self.state(), before, label)

    def test_a_valid_run_on_the_same_fixture_is_accepted(self):
        # Control: every rejection below changes one element of exactly this command line.
        result = self.run_cleanup()
        self.assertEqual(result["worktree"]["result"], "removed")

    def test_invalid_feature_values_exit_2(self):
        iw = str(self.iw)
        cases = [
            ("a/b", self.argv(feature="a/b")),
            ("../x", self.argv(feature="../x")),
            ("empty", self.argv(feature="")),
            ("-x separate word", ["--integration-worktree", iw, "--feature", "-x", "--task", TASK]),
            ("-x attached", ["--integration-worktree", iw, "--feature=-x", "--task", TASK]),
            ("--task as the value", ["--integration-worktree", iw, "--feature", "--task", "--task", TASK]),
            ("uppercase", self.argv(feature="Feature")),
            ("underscore", self.argv(feature="demo_feature")),
            ("leading hyphen", self.argv(feature="-demo")),
            ("trailing newline", self.argv(feature=FEATURE + "\n")),
            ("attached with a path separator", ["--integration-worktree", iw, "--feature=a/b", "--task", TASK]),
        ]
        for label, argv in cases:
            with self.subTest(label):
                self.assert_rejected(label, argv)

    def test_invalid_task_values_exit_2(self):
        iw = str(self.iw)
        cases = [
            ("integration", self.argv(task="integration")),
            ("task without digits", self.argv(task="task")),
            ("task1/x", self.argv(task="task1/x")),
            ("empty", self.argv(task="")),
            ("-task1 separate word", ["--integration-worktree", iw, "--feature", FEATURE, "--task", "-task1"]),
            ("-task1 attached", ["--integration-worktree", iw, "--feature", FEATURE, "--task=-task1"]),
            ("trailing newline", self.argv(task=TASK + "\n")),
            ("capital T", self.argv(task="Task0001")),
            ("trailing letter", self.argv(task="task0001x")),
            ("hyphen inside", self.argv(task="task-1")),
            ("parent reference", self.argv(task="..")),
        ]
        for label, argv in cases:
            with self.subTest(label):
                self.assert_rejected(label, argv)

    def test_invalid_integration_worktree_values_exit_2(self):
        # Directories that exist on disk, so that only the shape rule can reject them.
        other_feature = self.repo / ".claude" / "worktrees" / "em-workflow" / "other-feature" / "integration"
        other_feature.mkdir(parents=True)
        other_tool = self.repo / ".claude" / "worktrees" / "other-tool" / FEATURE / "integration"
        other_tool.mkdir(parents=True)
        not_claude = self.make_dir("x", "worktrees", "em-workflow", FEATURE, "integration")
        file_leaf = self.tmp / "file-case" / ".claude" / "worktrees" / "em-workflow" / FEATURE
        file_leaf.mkdir(parents=True)
        (file_leaf / "integration").write_text("not a directory\n", encoding="utf-8")
        control_char = self.make_dir("ctl\x01dir", ".claude", "worktrees", "em-workflow", FEATURE, "integration")
        newline_char = self.make_dir("nl\ndir", ".claude", "worktrees", "em-workflow", FEATURE, "integration")
        missing = self.tmp / "missing" / ".claude" / "worktrees" / "em-workflow" / FEATURE / "integration"

        tail = f".claude/worktrees/em-workflow/{FEATURE}/integration"
        relative = tail
        cases = [
            ("relative", self.argv(iw=relative), self.repo),
            ("bare name", self.argv(iw="integration"), self.wt_dir),
            ("empty", self.argv(iw=""), None),
            ("root", self.argv(iw="/"), None),
            ("dot-dot segment", self.argv(iw=f"{self.wt_dir}/../{FEATURE}/integration"), None),
            ("dot-dot through the task worktree", self.argv(iw=f"{self.task_wt}/../integration"), None),
            ("dot segment", self.argv(iw=f"{self.wt_dir}/./integration"), None),
            # These end in the right five segments and name a directory that exists.
            ("dot-dot segment before the tail", self.argv(iw=f"{self.repo}/../repo/{tail}"), None),
            ("dot segment before the tail", self.argv(iw=f"{self.repo}/./{tail}"), None),
            ("doubled separator before the tail", self.argv(iw=f"{self.repo}//{tail}"), None),
            ("relative with all five tail segments", self.argv(iw=f"repo/{tail}"), self.tmp),
            ("trailing separator", self.argv(iw=str(self.iw) + "/"), None),
            ("doubled separator", self.argv(iw=f"{self.wt_dir}//integration"), None),
            ("trailing newline", self.argv(iw=str(self.iw) + "\n"), None),
            ("another feature's integration worktree", self.argv(iw=str(other_feature)), None),
            ("not under .claude/worktrees/em-workflow", self.argv(iw=str(other_tool)), None),
            ("no .claude segment", self.argv(iw=str(not_claude)), None),
            ("the task worktree itself", self.argv(iw=str(self.task_wt)), None),
            ("the main tree", self.argv(iw=str(self.repo)), None),
            ("a file at the integration position", self.argv(iw=str(file_leaf / "integration")), None),
            ("control character", self.argv(iw=str(control_char)), None),
            ("newline", self.argv(iw=str(newline_char)), None),
            ("does not exist", self.argv(iw=str(missing)), None),
        ]
        for label, argv, cwd in cases:
            with self.subTest(label):
                self.assert_rejected(label, argv, cwd=cwd)

    def test_missing_repeated_and_unknown_options_exit_2(self):
        iw = str(self.iw)
        full = self.argv()
        cases = [
            ("no arguments", []),
            ("missing --integration-worktree", full[2:]),
            ("missing --feature", full[:2] + full[4:]),
            ("missing --task", full[:4]),
            ("repeated --integration-worktree", full + ["--integration-worktree", iw]),
            ("repeated --feature", full + ["--feature", FEATURE]),
            ("repeated --task", full + ["--task", TASK]),
            ("repeated --feature, different value", full + ["--feature", "other"]),
            ("repeated through the attached form", full + [f"--task={TASK}"]),
            ("unknown option with a value", full + ["--bogus", "x"]),
            ("unknown attached option", full + ["--bogus=x"]),
            ("unknown flag", full + ["--verbose"]),
            ("positional argument", full + ["extra"]),
            ("abbreviated option name", ["--integration-worktree", iw, "--feat", FEATURE, "--task", TASK]),
            ("option name with a different case", ["--integration-worktree", iw, "--Feature", FEATURE, "--task", TASK]),
            ("option without a value at the end", full + ["--task"]),
        ]
        for label, argv in cases:
            with self.subTest(label):
                self.assert_rejected(label, argv)

    def test_a_shape_valid_directory_that_is_not_a_git_worktree_exits_1(self):
        plain = self.make_dir("plain", ".claude", "worktrees", "em-workflow", FEATURE, "integration")
        proc = self.run_raw(
            self.argv(iw=str(plain)),
            env_extra={"GIT_CEILING_DIRECTORIES": str(self.tmp)},
        )
        self.assertEqual(proc.returncode, 1, f"stderr: {proc.stderr}")
        self.assertEqual(proc.stdout, "")
        self.assert_git_policy(integration_worktree=str(plain))
        self.assertIsNotNone(self.ref_sha(TASK_REF))
        self.assertIn(str(self.task_wt), self.registered_paths())


# --------------------------------------------------------------------------
# AC-2: merged task, any working directory
# --------------------------------------------------------------------------


class TestAC2MergedTaskFromAnyDirectory(CleanupBase):
    """AC-2 (FR2, FR7, FR8, NFR1, TS-1): merged into the integration branch, not into main."""

    def setUp(self):
        super().setUp()
        self.add_task()
        self.merge_task_into_integration()
        # The fixture is what the criterion describes.
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual(self.git_rc("merge-base", "--is-ancestor", TASK_BRANCH, "main"), 1)
        self.assertEqual(self.git_rc("merge-base", "--is-ancestor", TASK_BRANCH, INTEGRATION_BRANCH), 0)

    def assert_cleaned_up(self, result):
        self.assertEqual(result["worktree"], {"result": "removed", "reason": None})
        self.assertEqual(result["branch"], {"name": TASK_BRANCH, "result": "removed", "reason": None})
        self.assertNotIn(str(self.task_wt), self.registered_paths())
        self.assertFalse(self.task_wt.exists())
        self.assertIsNone(self.ref_sha(TASK_REF))

    def test_run_from_the_main_tree_removes_the_worktree_and_the_branch(self):
        self.assert_cleaned_up(self.run_cleanup(cwd=self.repo))

    def test_run_from_outside_any_repository_removes_the_worktree_and_the_branch(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        ceiling = {"GIT_CEILING_DIRECTORIES": str(self.tmp)}
        probe = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(outside),
            env={**self.git_env, **ceiling},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(probe.returncode, 0, "the directory must be outside any repository")
        self.assert_cleaned_up(self.run_cleanup(cwd=outside, env_extra=ceiling))

    def test_repository_redirecting_environment_does_not_change_the_outcome(self):
        # A caller that exports GIT_DIR / GIT_WORK_TREE at the main repository
        # must not steer the deletion to main (where the branch is not merged).
        redirect = {
            "GIT_DIR": str(self.repo / ".git"),
            "GIT_WORK_TREE": str(self.repo),
            "GIT_INDEX_FILE": str(self.repo / ".git" / "index"),
        }
        self.assert_cleaned_up(self.run_cleanup(cwd=self.repo, env_extra=redirect))

    def test_every_git_call_names_the_integration_worktree_as_its_location(self):
        self.run_cleanup(cwd=self.repo)
        calls = self.git_calls()
        self.assertTrue(calls)
        for args in calls:
            self.assertEqual(parse_invocation(args)[0], [str(self.iw)], args)


# --------------------------------------------------------------------------
# Behavior outside the acceptance criteria (IMPLEMENTATION.md C1, C3)
# --------------------------------------------------------------------------


class TestOptionSyntaxAndInternalErrors(CleanupBase):
    """C1: values may be attached with an equals sign. C3: an internal error exits 1 with empty stdout."""

    def test_option_values_may_be_attached_with_an_equals_sign(self):
        self.add_task()
        self.merge_task_into_integration()
        argv = [f"--integration-worktree={self.iw}", f"--feature={FEATURE}", f"--task={TASK}"]
        result = self.run_cleanup(cwd=self.repo, argv=argv)
        self.assertEqual(result["worktree"]["result"], "removed")
        self.assertEqual(result["branch"]["result"], "removed")

    def test_a_missing_git_is_an_internal_error_with_empty_stdout(self):
        self.add_task()
        empty_bin = self.tmp / "empty-bin"
        empty_bin.mkdir()
        env = dict(self.git_env)
        env["PATH"] = str(empty_bin)
        proc = self.run_raw(self.argv(), cwd=self.repo, env=env)
        self.assertEqual(proc.returncode, 1, f"stderr: {proc.stderr}")
        self.assertEqual(proc.stdout, "")
        self.assertIsNotNone(self.ref_sha(TASK_REF))
        self.assertIn(str(self.task_wt), self.registered_paths())


# --------------------------------------------------------------------------
# AC-3: task branch not merged into the integration branch
# --------------------------------------------------------------------------


class TestAC3UnmergedBranchIsKept(CleanupBase):
    """AC-3 (FR2, FR3, FR8, TS-2)."""

    def test_the_worktree_is_removed_and_the_unmerged_branch_is_kept_with_a_reason(self):
        self.add_task()
        tip = self.ref_sha(TASK_REF)
        self.assertEqual(self.git_rc("merge-base", "--is-ancestor", TASK_BRANCH, INTEGRATION_BRANCH), 1)

        result = self.run_cleanup(cwd=self.repo)

        self.assertEqual(result["worktree"], {"result": "removed", "reason": None})
        self.assertEqual(result["branch"]["result"], "kept")
        self.assertEqual(result["branch"]["name"], TASK_BRANCH)
        self.assertIsInstance(result["branch"]["reason"], str)
        self.assertTrue(result["branch"]["reason"].strip())
        self.assertNotIn(str(self.task_wt), self.registered_paths())
        self.assertEqual(self.ref_sha(TASK_REF), tip)

    def test_the_branch_reason_is_the_git_message_of_the_refused_deletion(self):
        self.add_task()
        result = self.run_cleanup(cwd=self.repo)
        self.assertIn("not fully merged", result["branch"]["reason"])


# --------------------------------------------------------------------------
# AC-4: uncommitted change in the task worktree
# --------------------------------------------------------------------------


class TestAC4DirtyWorktreeIsKept(CleanupBase):
    """AC-4 (FR6, FR8, TM-2, TS-3)."""

    def setUp(self):
        super().setUp()
        self.add_task()
        # Merged, so the branch deletion would succeed if it were attempted.
        self.merge_task_into_integration()

    def assert_kept(self, result, tip):
        worktree, branch = result["worktree"], result["branch"]
        self.assertEqual(worktree["result"], "kept")
        self.assertIsInstance(worktree["reason"], str)
        self.assertTrue(worktree["reason"].strip())
        self.assertEqual(branch["result"], "skipped")
        self.assertEqual(branch["name"], TASK_BRANCH)
        self.assertIsInstance(branch["reason"], str)
        self.assertTrue(branch["reason"].strip())
        self.assertIn(str(self.task_wt), self.registered_paths())
        self.assertEqual(self.ref_sha(TASK_REF), tip)
        self.assertNotIn("branch", self.git_subcommands())

    def test_a_modified_tracked_file_keeps_the_worktree_and_skips_the_branch(self):
        tip = self.ref_sha(TASK_REF)
        (self.task_wt / "README.md").write_text("uncommitted change\n", encoding="utf-8")

        result = self.run_cleanup(cwd=self.repo)

        self.assert_kept(result, tip)
        self.assertEqual((self.task_wt / "README.md").read_text(encoding="utf-8"), "uncommitted change\n")

    def test_an_untracked_file_keeps_the_worktree_and_skips_the_branch(self):
        tip = self.ref_sha(TASK_REF)
        (self.task_wt / "scratch.txt").write_text("not committed\n", encoding="utf-8")

        result = self.run_cleanup(cwd=self.repo)

        self.assert_kept(result, tip)
        self.assertEqual((self.task_wt / "scratch.txt").read_text(encoding="utf-8"), "not committed\n")

    def test_the_worktree_reason_is_the_git_message(self):
        (self.task_wt / "README.md").write_text("uncommitted change\n", encoding="utf-8")
        result = self.run_cleanup(cwd=self.repo)
        self.assertIn("modified or untracked files", result["worktree"]["reason"])


# --------------------------------------------------------------------------
# AC-5: targets that are already gone
# --------------------------------------------------------------------------


class TestAC5AlreadyGoneTargets(CleanupBase):
    """AC-5 (FR7, TS-4)."""

    def test_branch_already_gone_worktree_on_a_detached_head(self):
        self.add_detached_task_worktree()
        self.assertIsNone(self.ref_sha(TASK_REF))

        result = self.run_cleanup(cwd=self.repo)

        self.assertEqual(result["worktree"], {"result": "removed", "reason": None})
        self.assertEqual(result["branch"], {"name": TASK_BRANCH, "result": "absent", "reason": None})
        self.assertNotIn(str(self.task_wt), self.registered_paths())

    def test_worktree_already_gone_branch_merged(self):
        self.add_task()
        self.merge_task_into_integration()
        self.remove_task_worktree_keeping_branch()
        self.assertNotIn(str(self.task_wt), self.registered_paths())
        self.assertIsNotNone(self.ref_sha(TASK_REF))

        result = self.run_cleanup(cwd=self.repo)

        self.assertEqual(result["worktree"], {"result": "absent", "reason": None})
        self.assertEqual(result["branch"], {"name": TASK_BRANCH, "result": "removed", "reason": None})
        self.assertIsNone(self.ref_sha(TASK_REF))

    def test_both_already_gone(self):
        result = self.run_cleanup(cwd=self.repo)

        self.assertEqual(result["worktree"], {"result": "absent", "reason": None})
        self.assertEqual(result["branch"], {"name": TASK_BRANCH, "result": "absent", "reason": None})

    def test_a_directory_at_the_task_path_without_a_registration_is_not_a_worktree(self):
        # FR7: the registration list decides, not the existence of the path.
        self.task_wt.mkdir()
        (self.task_wt / "note.txt").write_text("not a worktree\n", encoding="utf-8")

        result = self.run_cleanup(cwd=self.repo)

        self.assertEqual(result["worktree"], {"result": "absent", "reason": None})
        self.assertEqual(result["branch"], {"name": TASK_BRANCH, "result": "absent", "reason": None})
        self.assertEqual((self.task_wt / "note.txt").read_text(encoding="utf-8"), "not a worktree\n")
        self.assertNotIn(["worktree", "remove"], self.git_subcommand_prefixes())


# --------------------------------------------------------------------------
# AC-6: registered worktree whose directory is gone
# --------------------------------------------------------------------------


class TestAC6RegistrationWithoutDirectory(CleanupBase):
    """AC-6 (FR6, FR7, TS-5): git versions differ on removing such a worktree; assert only the criterion."""

    def test_the_result_is_not_absent_and_nothing_is_pruned(self):
        self.add_task()
        shutil.rmtree(self.task_wt)
        self.assertIn(str(self.task_wt), self.registered_paths())

        result = self.run_cleanup(cwd=self.repo)

        worktree, branch = result["worktree"], result["branch"]
        self.assertNotEqual(worktree["result"], "absent", result)
        if worktree["result"] == "kept":
            self.assertTrue(worktree["reason"].strip())
            self.assertEqual(branch["result"], "skipped")
        self.assertNotIn("prune", self.git_subcommands())
        self.assertFalse(any("prune" in token for args in self.git_calls() for token in args))

    def test_the_registration_of_a_missing_directory_is_matched_by_its_registered_path(self):
        # Same state with a detached worktree, so no branch is involved.
        self.add_detached_task_worktree()
        shutil.rmtree(self.task_wt)

        result = self.run_cleanup(cwd=self.repo)

        self.assertNotEqual(result["worktree"]["result"], "absent", result)
        self.assertNotIn("prune", self.git_subcommands())


# --------------------------------------------------------------------------
# AC-7: no forcing flag, no prune
# --------------------------------------------------------------------------


class TestAC7StaticScan(unittest.TestCase):
    """AC-7 (FR2, TM-2, TS-7): the text of the script."""

    def test_the_script_text_has_no_standalone_forcing_token(self):
        self.assertTrue(SCRIPT.is_file(), "the script under test does not exist")
        text = SCRIPT.read_text(encoding="utf-8")
        hits = [
            f"line {number}: {line.strip()}"
            for number, line in enumerate(text.splitlines(), start=1)
            if STANDALONE_FORCING_TOKEN.search(line)
        ]
        self.assertEqual(hits, [])

    def test_the_scan_pattern_finds_forcing_tokens_and_ignores_look_alikes(self):
        for text in ('git branch -D x', 'args = ["-f"]', "(--force)", "run --force.", "x -f", "-D"):
            with self.subTest(text):
                self.assertIsNotNone(STANDALONE_FORCING_TOKEN.search(text))
        for text in ("--feature", "non-forced", "branch -d", "wake-f", "--force-with-lease", "-fx", "_-D", "a-D", "-C"):
            with self.subTest(text):
                self.assertIsNone(STANDALONE_FORCING_TOKEN.search(text))


class TestAC7InvocationPolicy(unittest.TestCase):
    """AC-7: the policy checker detects each violation it guards against."""

    IW = "/r/.claude/worktrees/em-workflow/f/integration"
    BRANCH = "em-workflow/f/task0001"

    def violations(self, *calls):
        return policy_violations([list(c) for c in calls], self.IW, self.BRANCH)

    def test_a_conforming_log_has_no_violation(self):
        self.assertEqual(
            self.violations(
                ["-C", self.IW, "worktree", "list", "--porcelain"],
                ["-C", self.IW, "worktree", "remove", "/r/.claude/worktrees/em-workflow/f/task0001"],
                ["-C", self.IW, "show-ref", "--verify", "--quiet", "--", "refs/heads/" + self.BRANCH],
                ["-C", self.IW, "branch", "-d", self.BRANCH],
            ),
            [],
        )

    def test_forcing_flags_and_prune_are_violations(self):
        bad = [
            ["-C", self.IW, "branch", "-D", self.BRANCH],
            ["-C", self.IW, "branch", "-d", "-f", self.BRANCH],
            ["-C", self.IW, "branch", "-df", self.BRANCH],
            ["-C", self.IW, "branch", "--force", "-d", self.BRANCH],
            ["-C", self.IW, "worktree", "remove", "--force", "/r/x"],
            ["-C", self.IW, "worktree", "remove", "-f", "/r/x"],
            ["-C", self.IW, "worktree", "prune"],
            ["-C", self.IW, "gc", "--prune=now"],
        ]
        for call in bad:
            with self.subTest(call):
                self.assertNotEqual(self.violations(call), [])

    def test_a_branch_deletion_must_name_the_task_branch_only_from_the_integration_worktree(self):
        bad = [
            ["branch", "-d", self.BRANCH],
            ["-C", "/r", "branch", "-d", self.BRANCH],
            ["-C", self.IW, "branch", "-d", "main"],
            ["-C", self.IW, "branch", "-d", self.BRANCH, "main"],
            ["-C", self.IW, "branch", "--delete", self.BRANCH],
            ["-C", self.IW, "branch", "-m", self.BRANCH, "x"],
            ["-C", self.IW, "-C", "/r", "branch", "-d", self.BRANCH],
        ]
        for call in bad:
            with self.subTest(call):
                self.assertNotEqual(self.violations(call), [])


class TestAC7RunsHonourThePolicy(CleanupBase):
    """AC-7 (FR2, TM-2, TS-7): the shim log of every kind of run."""

    def test_merged_task_run_deletes_the_branch_with_exactly_branch_d(self):
        self.add_task()
        self.merge_task_into_integration()
        self.run_cleanup(cwd=self.repo)
        deletions = [args for args in self.git_calls() if parse_invocation(args)[1][:1] == ["branch"]]
        self.assertEqual(deletions, [["-C", str(self.iw), "branch", "-d", TASK_BRANCH]])

    def test_unmerged_task_run(self):
        self.add_task()
        self.run_cleanup(cwd=self.repo)

    def test_dirty_worktree_run(self):
        self.add_task()
        (self.task_wt / "README.md").write_text("uncommitted change\n", encoding="utf-8")
        self.run_cleanup(cwd=self.repo)

    def test_branch_gone_run(self):
        self.add_detached_task_worktree()
        self.run_cleanup(cwd=self.repo)

    def test_worktree_gone_run(self):
        self.add_task()
        self.merge_task_into_integration()
        self.remove_task_worktree_keeping_branch()
        self.run_cleanup(cwd=self.repo)

    def test_missing_directory_run(self):
        self.add_task()
        shutil.rmtree(self.task_wt)
        self.run_cleanup(cwd=self.repo)

    def test_rejected_input_runs_no_git_at_all(self):
        self.add_task()
        proc = self.run_raw(self.argv(task="integration"), cwd=self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.git_calls(), [])


if __name__ == "__main__":
    unittest.main()
