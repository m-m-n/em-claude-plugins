"""Unit tests for em-workflow/scripts/merge-git.py (task0003, AC-1 .. AC-6, AC-7).

Every test builds its own temporary repositories; a local bare repository
stands in for a remote, so no network is touched. A PATH-prepended git
logging shim records the script's git invocations so that every run can be
checked against the operation boundary of the script (AC-7): no push, rebase,
reset, worktree add / remove, force option, hook bypass or forced refspec.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-git.py"
REAL_GIT = shutil.which("git")

FEATURE = "feat"
BRANCH = "em-workflow/%s/integration" % FEATURE
SEP = "\x1f"

COMMON_KEYS = ("outcome", "reason", "detail")
FORBIDDEN_SUBCOMMANDS = {"push", "rebase", "reset", "pull", "checkout", "switch"}
FORBIDDEN_WORKTREE_ACTIONS = {"add", "remove", "prune", "move", "lock", "unlock", "repair"}
FORBIDDEN_OPTIONS = {
    "-f",
    "--force",
    "--force-with-lease",
    "--force-if-includes",
    "--no-verify",
    "--hard",
    "--soft",
    "--mixed",
}

SHIM = """#!/bin/sh
{ for a in "$@"; do printf '%s\\037' "$a"; done; printf '\\n'; } >> "$MERGE_GIT_TEST_LOG"
exec "$MERGE_GIT_TEST_REAL_GIT" "$@"
"""


def subcommand_of(argv):
    """(subcommand, remaining args) of one logged git invocation."""
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("-c", "-C"):
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            return token, argv[index + 1:]
    return None, []


class GitCase(unittest.TestCase):
    """Common fixture: temporary directory, isolated git, logging shim."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        home = self.tmp / "home"
        home.mkdir()
        shim_dir = self.tmp / "shim"
        shim_dir.mkdir()
        shim = shim_dir / "git"
        shim.write_text(SHIM)
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
        self.log = self.tmp / "git.log"
        self.log.write_text("")
        self.log_offset = 0

        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.pop("EM_WORKFLOW_APPROVALS", None)
        env.update(
            {
                "HOME": str(home),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        self.env = env
        self.script_env = dict(env)
        self.script_env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
        self.script_env["MERGE_GIT_TEST_LOG"] = str(self.log)
        self.script_env["MERGE_GIT_TEST_REAL_GIT"] = REAL_GIT

    # ---- git helpers (the test's own git, never through the shim) ----

    def git(self, cwd, *args, check=True):
        proc = subprocess.run(
            [REAL_GIT, "-C", str(cwd)] + list(args),
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout.strip() if check else proc

    def make_repo(self, name="repo", gitignore=".claude/worktrees/\n"):
        root = self.tmp / name
        root.mkdir()
        self.git(root, "init", "-q", "-b", "main")
        (root / "base.txt").write_text("base\n")
        (root / "dir").mkdir()
        (root / "dir" / "sub.txt").write_text("sub\n")
        if gitignore is not None:
            (root / ".gitignore").write_text(gitignore)
        self.git(root, "add", "-A")
        self.git(root, "commit", "-q", "-m", "base")
        return root

    def worktree_path(self, root, feature=FEATURE):
        return root / ".claude" / "worktrees" / "em-workflow" / feature / "integration"

    def add_integration(self, root, feature=FEATURE):
        """Integration branch with its worktree and one feature commit."""
        path = self.worktree_path(root, feature)
        self.git(
            root,
            "worktree",
            "add",
            "-q",
            "-b",
            "em-workflow/%s/integration" % feature,
            str(path),
        )
        self.commit_file(path, "feature.txt", "feature\n", "feature work")
        return path

    def commit_file(self, cwd, relpath, content, message):
        target = Path(cwd) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)
        return self.git(cwd, "rev-parse", "HEAD")

    def make_bare(self, name):
        path = self.tmp / name
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(path))
        return path

    def tip(self, cwd, ref):
        return self.git(cwd, "rev-parse", "--verify", ref)

    def snapshot(self, root, *worktrees):
        """Refs plus the working state of the given trees."""
        state = {"refs": self.git(root, "for-each-ref", "--format=%(refname) %(objectname)")}
        for tree in (root,) + worktrees:
            state[str(tree)] = (
                self.git(tree, "rev-parse", "HEAD"),
                self.git(tree, "status", "--porcelain=v1", "--untracked-files=all"),
            )
        return state

    # ---- script runner ----

    def check_log(self):
        """Every git invocation logged since the last call stays inside the boundary."""
        data = self.log.read_text()[self.log_offset:]
        self.log_offset += len(data)
        for record in data.split("\n"):
            if not record:
                continue
            argv = record.split(SEP)[:-1]
            sub, rest = subcommand_of(argv)
            self.assertNotIn(sub, FORBIDDEN_SUBCOMMANDS, argv)
            if sub == "worktree":
                self.assertTrue(rest and rest[0] not in FORBIDDEN_WORKTREE_ACTIONS, argv)
            for token in argv:
                self.assertNotIn(token, FORBIDDEN_OPTIONS, argv)
                self.assertFalse(token.startswith("+"), argv)
                self.assertFalse(token.startswith("--force"), argv)

    def run_script(self, *args, cwd=None):
        proc = subprocess.run(
            ["python3", str(SCRIPT)] + [str(a) for a in args],
            env=self.script_env,
            cwd=str(cwd or self.tmp),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.check_log()
        return proc

    def decide(self, *args, cwd=None):
        """Run the script and return its one JSON decision (exit 0 required)."""
        proc = self.run_script(*args, cwd=cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.split("\n")
        self.assertEqual(len(lines), 2, proc.stdout)
        self.assertEqual(lines[1], "")
        data = json.loads(lines[0])
        self.assertIsInstance(data, dict)
        for key in COMMON_KEYS:
            self.assertIn(key, data)
        if data["outcome"] == "stop":
            self.assertIsInstance(data["reason"], str)
            self.assertTrue(data["detail"])
        else:
            self.assertIsNone(data["reason"])
        self.assertNotIn(str(self.tmp), data["detail"])
        return data

    def route(self, root, base="main", cwd=None):
        return self.decide("route", "--project-root", root, "--base=" + base, cwd=cwd)

    def merged(self, root, base="main"):
        return self.decide(
            "merged", "--project-root", root, "--feature", FEATURE, "--base", base
        )

    def state(self, root, feature=FEATURE):
        return self.decide("worktree-state", "--project-root", root, "--feature", feature)

    def integrate(self, root, remote=None, base="main"):
        args = ["integrate", "--project-root", root, "--feature", FEATURE, "--base", base]
        if remote:
            args += ["--remote", remote]
        return self.decide(*args)

    def base_check(self, root, integrated_base, redo_count, remote=None, base="main"):
        args = [
            "base-check",
            "--project-root",
            root,
            "--base",
            base,
            "--integrated-base",
            integrated_base,
            "--redo-count",
            redo_count,
        ]
        if remote:
            args += ["--remote", remote]
        return self.decide(*args)

    def main_tree(self, root, base="main"):
        return self.decide("main-tree", "--project-root", root, "--base", base)

    def assertStop(self, data, reason, detail_part=None):
        self.assertEqual(data["outcome"], "stop", data)
        self.assertEqual(data["reason"], reason, data)
        if detail_part is not None:
            self.assertIn(detail_part, data["detail"])


class RouteTests(GitCase):
    """AC-1 (TS5): every route selection rule."""

    def test_ac1_upstream_remote_among_two_remotes(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "other", str(self.make_bare("other.git")))
        self.git(root, "remote", "add", "up", str(self.make_bare("up.git")))
        self.git(root, "config", "branch.main.remote", "up")
        self.git(root, "config", "branch.main.merge", "refs/heads/main")
        data = self.route(root)
        self.assertEqual(data["outcome"], "remote")
        self.assertEqual(data["remote"], "up")

    def test_ac1_single_remote_without_upstream(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "origin", str(self.make_bare("origin.git")))
        data = self.route(root)
        self.assertEqual(data["outcome"], "remote")
        self.assertEqual(data["remote"], "origin")

    def test_ac1_two_remotes_without_upstream_stops(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "a", str(self.make_bare("a.git")))
        self.git(root, "remote", "add", "b", str(self.make_bare("b.git")))
        data = self.route(root)
        self.assertStop(data, "remote_unresolved")
        self.assertIsNone(data["remote"])

    def test_ac1_no_remote_is_local(self):
        root = self.make_repo()
        data = self.route(root)
        self.assertEqual(data["outcome"], "local")
        self.assertIsNone(data["remote"])
        self.assertEqual(data["reason"], None)

    def test_ac1_no_remote_and_base_absent_locally_stops(self):
        root = self.make_repo()
        data = self.route(root, base="release/9")
        self.assertStop(data, "base_branch_invalid")

    def test_ac1_upstream_of_dot_counts_as_no_upstream(self):
        root = self.make_repo()
        self.git(root, "config", "branch.main.remote", ".")
        self.git(root, "config", "branch.main.merge", "refs/heads/main")
        self.git(root, "remote", "add", "a", str(self.make_bare("a.git")))
        self.git(root, "remote", "add", "b", str(self.make_bare("b.git")))
        self.assertStop(self.route(root), "remote_unresolved")

    def test_ac1_upstream_of_dot_with_one_remote_uses_it(self):
        root = self.make_repo()
        self.git(root, "config", "branch.main.remote", ".")
        self.git(root, "config", "branch.main.merge", "refs/heads/main")
        self.git(root, "remote", "add", "only", str(self.make_bare("only.git")))
        data = self.route(root)
        self.assertEqual((data["outcome"], data["remote"]), ("remote", "only"))

    def test_ac1_upstream_naming_a_missing_remote_is_ignored(self):
        root = self.make_repo()
        self.git(root, "config", "branch.main.remote", "ghost")
        self.git(root, "remote", "add", "only", str(self.make_bare("only.git")))
        data = self.route(root)
        self.assertEqual((data["outcome"], data["remote"]), ("remote", "only"))

    def test_ac1_unsafe_remote_name_stops(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "a+b", str(self.make_bare("plus.git")))
        self.assertStop(self.route(root), "remote_unresolved")

    def test_ac1_unsafe_upstream_remote_name_stops(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "a+b", str(self.make_bare("plus.git")))
        self.git(root, "remote", "add", "safe", str(self.make_bare("safe.git")))
        self.git(root, "config", "branch.main.remote", "a+b")
        self.assertStop(self.route(root), "remote_unresolved")

    def test_ac1_unsafe_base_name_stops(self):
        root = self.make_repo()
        self.assertStop(self.route(root, base="ma;in"), "base_branch_invalid")
        self.assertStop(self.route(root, base="-x"), "base_branch_invalid")

    def test_ac1_works_from_a_linked_worktree(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        data = self.route(root, cwd=wt)
        self.assertEqual(data["outcome"], "local")


class MergedTests(GitCase):
    """AC-2 (TS2): merged / not_merged without any change."""

    def test_ac2_not_merged_and_nothing_changes(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        before = self.snapshot(root, wt)
        data = self.merged(root)
        self.assertEqual(data["outcome"], "not_merged")
        self.assertEqual(self.snapshot(root, wt), before)

    def test_ac2_merged_when_base_contains_the_integration_tip(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(root, "merge", "-q", "--no-ff", "--no-edit", BRANCH)
        before = self.snapshot(root, wt)
        data = self.merged(root)
        self.assertEqual(data["outcome"], "merged")
        self.assertEqual(self.snapshot(root, wt), before)

    def test_ac2_not_merged_when_base_only_advanced(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        self.assertEqual(self.merged(root)["outcome"], "not_merged")
        self.assertTrue(wt.is_dir())

    def test_ac2_merged_after_the_worktree_is_gone(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(root, "merge", "-q", "--no-ff", "--no-edit", BRANCH)
        self.git(root, "worktree", "remove", str(wt))
        self.assertEqual(self.merged(root)["outcome"], "merged")

    def test_ac2_missing_base_stops(self):
        root = self.make_repo()
        self.add_integration(root)
        self.assertStop(self.merged(root, base="nope"), "base_branch_invalid")


class WorktreeStateTests(GitCase):
    """AC-3 (TS19): worktree-state fixtures."""

    def test_ac3_absent(self):
        root = self.make_repo()
        self.git(root, "branch", BRANCH)
        data = self.state(root)
        self.assertEqual(data["outcome"], "absent")
        self.assertEqual(data["worktree_path"], str(self.worktree_path(root)))

    def test_ac3_clean(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        data = self.state(root)
        self.assertEqual(data["outcome"], "clean")
        self.assertEqual(data["worktree_path"], str(wt))

    def test_ac3_untracked_files_do_not_make_it_unclean(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        (wt / "scratch.txt").write_text("untracked\n")
        self.assertEqual(self.state(root)["outcome"], "clean")

    def test_ac3_merge_in_progress_then_clean_after_abort(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        self.git(wt, "merge", "--no-ff", "--no-commit", "main")
        self.assertEqual(self.state(root)["outcome"], "merge_in_progress")
        self.git(wt, "merge", "--abort")
        self.assertEqual(self.state(root)["outcome"], "clean")

    def test_ac3_conflicted_merge_is_merge_in_progress(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "base.txt", "main side\n", "main edit")
        self.commit_file(wt, "base.txt", "integration side\n", "integration edit")
        self.git(wt, "merge", "--no-ff", "--no-edit", "main", check=False)
        self.assertEqual(self.state(root)["outcome"], "merge_in_progress")
        self.git(wt, "merge", "--abort")
        self.assertEqual(self.state(root)["outcome"], "clean")

    def test_ac3_dirty_worktree_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        (wt / "feature.txt").write_text("edited\n")
        self.assertStop(self.state(root), "worktree_not_clean", "uncommitted")

    def test_ac3_staged_change_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        (wt / "feature.txt").write_text("staged\n")
        self.git(wt, "add", "feature.txt")
        self.assertStop(self.state(root), "worktree_not_clean", "uncommitted")

    def test_ac3_another_branch_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(wt, "switch", "-q", "-c", "scratch-branch")
        self.assertStop(self.state(root), "worktree_not_clean", "another branch")

    def test_ac3_detached_head_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(wt, "switch", "-q", "--detach")
        self.assertStop(self.state(root), "worktree_not_clean", "detached")

    def test_ac3_unregistered_directory_stops(self):
        root = self.make_repo()
        self.git(root, "branch", BRANCH)
        path = self.worktree_path(root)
        path.mkdir(parents=True)
        (path / "stray.txt").write_text("stray\n")
        self.assertStop(self.state(root), "worktree_not_clean", "not a registered")

    def test_ac3_registration_with_missing_directory_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        shutil.rmtree(wt)
        self.assertStop(self.state(root), "worktree_not_clean", "missing")

    def test_ac3_branch_checked_out_elsewhere_stops(self):
        root = self.make_repo()
        self.git(root, "branch", BRANCH)
        self.git(root, "switch", "-q", BRANCH)
        self.assertStop(self.state(root), "worktree_not_clean", "another worktree")

    def test_ac3_other_operation_in_progress_stops(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(root, "branch", "side", "main")
        side = self.tmp / "side-tree"
        self.git(root, "worktree", "add", "-q", str(side), "side")
        side_commit = self.commit_file(side, "base.txt", "side\n", "side edit")
        self.commit_file(wt, "base.txt", "integration\n", "integration edit")
        self.git(wt, "cherry-pick", side_commit, check=False)
        self.assertStop(self.state(root), "worktree_not_clean", "cherry-pick")

    def test_ac3_symlink_in_place_of_the_worktree_stops(self):
        root = self.make_repo()
        self.git(root, "branch", BRANCH)
        target = self.tmp / "elsewhere"
        target.mkdir()
        path = self.worktree_path(root)
        path.parent.mkdir(parents=True)
        path.symlink_to(target)
        self.assertStop(self.state(root), "worktree_not_clean", "not a registered")

    def test_ac3_state_never_modifies_anything(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        before = self.snapshot(root, wt)
        self.state(root)
        self.assertEqual(self.snapshot(root, wt), before)


class IntegrateTests(GitCase):
    """AC-4 (TS18): integrate."""

    def test_ac4_clean_case_creates_one_merge_commit(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        base_tip = self.commit_file(root, "other.txt", "other\n", "base moves")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "merged_clean")
        self.assertEqual(data["integrated_base"], base_tip)
        self.assertEqual(data["conflicted_paths"], [])
        new_tip = self.tip(root, BRANCH)
        self.assertEqual(data["head"], new_tip)
        self.assertNotEqual(new_tip, old_tip)
        parents = self.git(wt, "rev-list", "--parents", "-n", "1", new_tip).split()
        self.assertEqual(parents, [new_tip, old_tip, base_tip])
        self.assertEqual(
            self.git(wt, "rev-list", "--count", "%s..%s" % (old_tip, new_tip)), "2"
        )
        self.assertEqual(self.git(wt, "rev-list", "--merges", "--count", "%s..%s" % (old_tip, new_tip)), "1")
        subject = self.git(wt, "log", "-1", "--format=%s")
        self.assertIn("main", subject)
        self.assertIn(BRANCH, subject)
        self.assertTrue((wt / "other.txt").is_file())
        self.git(wt, "merge-base", "--is-ancestor", old_tip, new_tip)
        self.assertEqual(self.state(root)["outcome"], "clean")

    def test_ac4_local_base_branch_is_not_modified(self):
        root = self.make_repo()
        self.add_integration(root)
        base_tip = self.commit_file(root, "other.txt", "other\n", "base moves")
        self.integrate(root)
        self.assertEqual(self.tip(root, "main"), base_tip)
        self.assertEqual(self.git(root, "status", "--porcelain=v1"), "")

    def test_ac4_already_contained_base_is_up_to_date(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        before = self.snapshot(root, wt)
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "up_to_date")
        self.assertEqual(data["head"], old_tip)
        self.assertEqual(data["integrated_base"], self.tip(root, "main"))
        self.assertEqual(self.snapshot(root, wt), before)

    def test_ac4_second_integration_after_the_first_is_up_to_date(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        self.assertEqual(self.integrate(root)["outcome"], "merged_clean")
        tip = self.tip(wt, "HEAD")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "up_to_date")
        self.assertEqual(self.tip(wt, "HEAD"), tip)

    def test_ac4_conflict_lists_paths_and_leaves_the_merge_in_progress(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "base.txt", "main side\n", "main edit")
        self.commit_file(root, "dir/sub.txt", "main sub\n", "main sub edit")
        self.commit_file(wt, "base.txt", "integration side\n", "integration edit")
        self.commit_file(wt, "dir/sub.txt", "integration sub\n", "integration sub edit")
        old_tip = self.tip(wt, "HEAD")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "conflict")
        self.assertEqual(data["conflicted_paths"], ["base.txt", "dir/sub.txt"])
        self.assertEqual(data["integrated_base"], self.tip(root, "main"))
        self.assertEqual(data["head"], old_tip)
        self.assertEqual(self.tip(root, BRANCH), old_tip)
        merge_head = self.git(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
        self.assertEqual(merge_head.returncode, 0)
        self.assertEqual(merge_head.stdout.strip(), self.tip(root, "main"))
        self.assertEqual(self.state(root)["outcome"], "merge_in_progress")
        self.git(wt, "merge", "--abort")
        self.assertEqual(self.tip(root, BRANCH), old_tip)

    def test_ac4_conflict_with_a_delete_modify_pair(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.git(root, "rm", "-q", "base.txt")
        self.git(root, "commit", "-q", "-m", "main removes base")
        self.commit_file(wt, "base.txt", "integration edit\n", "integration edit")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "conflict")
        self.assertEqual(data["conflicted_paths"], ["base.txt"])

    def test_ac4_conflicted_paths_keep_unusual_but_valid_names(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        name = "sp ace/\u00fcn\u00ef\\x.txt"
        self.commit_file(root, name, "main\n", "main adds")
        self.commit_file(wt, name, "integration\n", "integration adds")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "conflict")
        self.assertEqual(data["conflicted_paths"], [name])
        self.assertEqual(data["detail"], "")

    def test_ac4_remote_fetched_tip_is_what_gets_integrated(self):
        root = self.make_repo()
        bare = self.make_bare("origin.git")
        self.git(root, "remote", "add", "origin", str(bare))
        self.git(root, "push", "-q", "origin", "main")
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        local_main = self.tip(root, "main")
        clone = self.tmp / "clone"
        self.git(self.tmp, "clone", "-q", str(bare), str(clone))
        remote_tip = self.commit_file(clone, "remote.txt", "remote\n", "remote moves")
        self.git(clone, "push", "-q", "origin", "main")
        self.assertNotEqual(remote_tip, local_main)

        data = self.integrate(root, remote="origin")
        self.assertEqual(data["outcome"], "merged_clean")
        self.assertEqual(data["integrated_base"], remote_tip)
        parents = self.git(wt, "rev-list", "--parents", "-n", "1", data["head"]).split()
        self.assertEqual(parents, [data["head"], old_tip, remote_tip])
        self.assertTrue((wt / "remote.txt").is_file())
        self.assertEqual(self.tip(root, "main"), local_main)
        self.git(wt, "merge-base", "--is-ancestor", old_tip, data["head"])

    def test_ac4_remote_without_news_is_up_to_date(self):
        root = self.make_repo()
        bare = self.make_bare("origin.git")
        self.git(root, "remote", "add", "origin", str(bare))
        self.git(root, "push", "-q", "origin", "main")
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        data = self.integrate(root, remote="origin")
        self.assertEqual(data["outcome"], "up_to_date")
        self.assertEqual(data["head"], old_tip)

    def test_ac4_fetch_failure_stops_with_git_failed(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        self.git(root, "remote", "add", "broken", str(self.tmp / "no-such-remote.git"))
        data = self.integrate(root, remote="broken")
        self.assertStop(data, "git_failed")
        self.assertEqual(self.tip(wt, "HEAD"), old_tip)

    def test_ac4_hooks_are_not_bypassed(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        old_tip = self.tip(wt, "HEAD")
        self.commit_file(root, "other.txt", "other\n", "base moves")
        hook = root / ".git" / "hooks" / "pre-merge-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        data = self.integrate(root)
        self.assertStop(data, "git_failed")
        self.assertEqual(data["conflicted_paths"], [])
        self.assertEqual(self.tip(root, BRANCH), old_tip)

    def test_ac4_requires_a_clean_worktree(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        (wt / "feature.txt").write_text("edited\n")
        old_tip = self.tip(wt, "HEAD")
        data = self.integrate(root)
        self.assertStop(data, "worktree_not_clean")
        self.assertEqual(self.tip(wt, "HEAD"), old_tip)

    def test_ac4_absent_worktree_is_not_created(self):
        root = self.make_repo()
        self.git(root, "branch", BRANCH)
        data = self.integrate(root)
        self.assertStop(data, "git_failed", "absent")
        self.assertFalse(self.worktree_path(root).exists())

    def test_ac4_merge_in_progress_is_not_continued(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        self.git(wt, "merge", "--no-ff", "--no-commit", "main")
        data = self.integrate(root)
        self.assertStop(data, "git_failed", "merge_in_progress")

    def test_ac4_missing_local_base_stops(self):
        root = self.make_repo()
        self.add_integration(root)
        data = self.integrate(root, base="nope")
        self.assertStop(data, "git_failed")


class BaseCheckTests(GitCase):
    """AC-5 (TS7): base-check."""

    def test_ac5_unchanged_when_the_tip_equals_the_integrated_base(self):
        root = self.make_repo()
        tip = self.tip(root, "main")
        for count in (0, 1, 2, 3):
            data = self.base_check(root, tip, count)
            self.assertEqual(data["outcome"], "unchanged")
            self.assertEqual(data["current_base"], tip)

    def test_ac5_redo_counts_0_1_2_redo_and_3_stops(self):
        root = self.make_repo()
        integrated = self.tip(root, "main")
        for count in (0, 1, 2):
            moved = self.commit_file(root, "n%d.txt" % count, "x\n", "base moves %d" % count)
            data = self.base_check(root, integrated, count)
            self.assertEqual(data["outcome"], "redo", count)
            self.assertEqual(data["current_base"], moved)
            integrated = moved
        self.commit_file(root, "n3.txt", "x\n", "base moves 3")
        data = self.base_check(root, integrated, 3)
        self.assertStop(data, "base_moving")
        self.assertEqual(data["current_base"], self.tip(root, "main"))

    def test_ac5_remote_is_fetched_first(self):
        root = self.make_repo()
        bare = self.make_bare("origin.git")
        self.git(root, "remote", "add", "origin", str(bare))
        self.git(root, "push", "-q", "origin", "main")
        integrated = self.tip(root, "main")
        self.assertEqual(self.base_check(root, integrated, 0, remote="origin")["outcome"], "unchanged")
        clone = self.tmp / "clone"
        self.git(self.tmp, "clone", "-q", str(bare), str(clone))
        remote_tip = self.commit_file(clone, "remote.txt", "remote\n", "remote moves")
        self.git(clone, "push", "-q", "origin", "main")
        data = self.base_check(root, integrated, 1, remote="origin")
        self.assertEqual(data["outcome"], "redo")
        self.assertEqual(data["current_base"], remote_tip)
        self.assertEqual(self.tip(root, "main"), integrated)
        self.assertStop(self.base_check(root, integrated, 3, remote="origin"), "base_moving")

    def test_ac5_fetch_failure_stops_with_git_failed(self):
        root = self.make_repo()
        self.git(root, "remote", "add", "broken", str(self.tmp / "no-such-remote.git"))
        data = self.base_check(root, self.tip(root, "main"), 0, remote="broken")
        self.assertStop(data, "git_failed")

    def test_ac5_malformed_arguments_exit_2(self):
        root = self.make_repo()
        tip = self.tip(root, "main")
        base = ["base-check", "--project-root", root, "--base", "main"]
        for extra in (
            ["--integrated-base", tip, "--redo-count", "4"],
            ["--integrated-base", tip, "--redo-count", "-1"],
            ["--integrated-base", tip, "--redo-count", "x"],
            ["--integrated-base", tip.upper(), "--redo-count", "0"],
            ["--integrated-base", "abc", "--redo-count", "0"],
            ["--redo-count", "0"],
            ["--integrated-base", tip],
        ):
            proc = self.run_script(*(base + extra))
            self.assertEqual(proc.returncode, 2, extra)
            self.assertIn("usage:", proc.stderr)
            self.assertEqual(proc.stdout, "")


class MainTreeTests(GitCase):
    """AC-6 (TS14): main-tree."""

    def test_ac6_ready_on_a_clean_base_branch(self):
        root = self.make_repo()
        before = self.snapshot(root)
        data = self.main_tree(root)
        self.assertEqual(data["outcome"], "ready")
        self.assertEqual(self.snapshot(root), before)

    def test_ac6_ready_while_integration_worktree_exists(self):
        root = self.make_repo()
        self.add_integration(root)
        self.assertEqual(self.main_tree(root)["outcome"], "ready")

    def test_ac6_another_branch_stops(self):
        root = self.make_repo()
        self.git(root, "switch", "-q", "-c", "other")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "other than the base")

    def test_ac6_detached_head_stops(self):
        root = self.make_repo()
        self.git(root, "switch", "-q", "--detach")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "detached")

    def test_ac6_tracked_modification_stops(self):
        root = self.make_repo()
        (root / "base.txt").write_text("modified\n")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "uncommitted")

    def test_ac6_staged_modification_stops(self):
        root = self.make_repo()
        (root / "base.txt").write_text("modified\n")
        self.git(root, "add", "base.txt")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "uncommitted")

    def test_ac6_untracked_file_stops(self):
        root = self.make_repo()
        (root / "stray.txt").write_text("stray\n")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "untracked")

    def test_ac6_uncommitted_worktrees_ignore_line_is_tolerated(self):
        root = self.make_repo(gitignore="*.log\n")
        (root / ".gitignore").write_text("*.log\n.claude/worktrees/\n")
        self.assertEqual(self.main_tree(root)["outcome"], "ready")

    def test_ac6_untracked_gitignore_with_only_the_worktrees_line_is_tolerated(self):
        root = self.make_repo(gitignore=None)
        (root / ".gitignore").write_text(".claude/worktrees/\n")
        self.assertEqual(self.main_tree(root)["outcome"], "ready")

    def test_ac6_gitignore_with_any_other_change_stops(self):
        root = self.make_repo(gitignore="*.log\n")
        (root / ".gitignore").write_text("*.log\n.claude/worktrees/\n*.tmp\n")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "uncommitted")
        (root / ".gitignore").write_text(".claude/worktrees/\n")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "uncommitted")

    def test_ac6_gitignore_exception_does_not_cover_other_dirt(self):
        root = self.make_repo(gitignore="*.log\n")
        (root / ".gitignore").write_text("*.log\n.claude/worktrees/\n")
        (root / "base.txt").write_text("modified\n")
        self.assertStop(self.main_tree(root), "main_tree_not_ready", "uncommitted")

    def test_ac6_project_root_must_be_the_main_working_tree(self):
        root = self.make_repo()
        wt = self.add_integration(root)
        data = self.decide("main-tree", "--project-root", wt, "--base", BRANCH)
        self.assertStop(data, "main_tree_not_ready", "main working tree")

    def test_ac6_merge_in_progress_stops(self):
        root = self.make_repo()
        self.git(root, "branch", "side")
        self.commit_file(root, "base.txt", "main side\n", "main edit")
        self.git(root, "switch", "-q", "side")
        self.commit_file(root, "base.txt", "side side\n", "side edit")
        self.git(root, "switch", "-q", "main")
        self.git(root, "merge", "--no-edit", "side", check=False)
        self.assertStop(self.main_tree(root), "main_tree_not_ready")


class BoundaryTests(GitCase):
    """AC-7: the logged git subcommands stay inside the operation boundary."""

    ALLOWED = {
        "remote",
        "config",
        "rev-parse",
        "worktree",
        "merge-base",
        "status",
        "symbolic-ref",
        "ls-tree",
        "cat-file",
        "diff",
        "fetch",
        "merge",
        "rev-list",
    }

    def logged(self):
        records = [r for r in self.log.read_text().split("\n") if r]
        return [subcommand_of(r.split(SEP)[:-1]) for r in records]

    def test_ac7_shim_records_the_scripts_git_invocations(self):
        root = self.make_repo()
        self.route(root)
        self.assertIn("remote", [sub for sub, _ in self.logged()])

    def test_ac7_boundary_check_rejects_forbidden_invocations(self):
        forbidden = (
            ["push", "origin", "main"],
            ["rebase", "main"],
            ["reset", "--hard", "HEAD"],
            ["worktree", "add", "path"],
            ["worktree", "remove", "path"],
            ["merge", "--force", "x"],
            ["fetch", "-f", "origin"],
            ["merge", "--no-verify", "x"],
            ["fetch", "origin", "+refs/heads/main:refs/remotes/origin/main"],
        )
        for argv in forbidden:
            record = "".join(arg + SEP for arg in ["-C", "/x"] + argv) + "\n"
            self.log.write_text(self.log.read_text() + record)
            with self.assertRaises(AssertionError, msg=argv):
                self.check_log()

    def test_ac7_every_subcommand_runs_only_allowed_git_operations(self):
        root = self.make_repo()
        bare = self.make_bare("origin.git")
        self.git(root, "remote", "add", "origin", str(bare))
        self.git(root, "push", "-q", "origin", "main")
        wt = self.add_integration(root)
        self.commit_file(root, "other.txt", "other\n", "base moves")
        self.route(root)
        self.merged(root)
        self.state(root)
        self.assertEqual(self.integrate(root, remote="origin")["outcome"], "up_to_date")
        data = self.integrate(root)
        self.assertEqual(data["outcome"], "merged_clean")
        self.base_check(root, data["integrated_base"], 0)
        self.main_tree(root)
        # a conflicting run as well
        self.commit_file(root, "base.txt", "main side\n", "main edit")
        self.commit_file(wt, "base.txt", "integration side\n", "integration edit")
        self.assertEqual(self.integrate(root)["outcome"], "conflict")
        subs = {sub for sub, _ in self.logged()}
        self.assertTrue(subs, "the shim recorded nothing")
        self.assertLessEqual(subs, self.ALLOWED)
        self.assertIn("merge", subs)
        self.assertIn("fetch", subs)


class ArgumentTests(GitCase):
    """C1: malformed arguments exit 2 and print no decision."""

    def test_missing_and_malformed_arguments_exit_2(self):
        root = self.make_repo()
        cases = [
            [],
            ["unknown-subcommand"],
            ["route", "--project-root", root],
            ["route", "--base", "main"],
            ["merged", "--project-root", root, "--base", "main"],
            ["merged", "--project-root", root, "--feature", "Bad;Name", "--base", "main"],
            ["merged", "--project-root", root, "--feature", "-x", "--base", "main"],
            ["merged", "--project-root", root, "--feature", FEATURE, "--base", "-x"],
            ["merged", "--project-root", root, "--feature", FEATURE, "--base", "a b"],
            ["worktree-state", "--project-root", root, "--feature", "UPPER"],
            ["integrate", "--project-root", root, "--feature", FEATURE, "--base", "main", "--remote", "-r"],
            ["integrate", "--project-root", root, "--feature", FEATURE, "--base", "main", "--remote", "a;b"],
            ["main-tree", "--project-root", root, "--base", "ma$in"],
            ["main-tree", "--project-root", str(root / "missing"), "--base", "main"],
            ["route", "--project-root", root, "--base", "main", "--bogus", "1"],
        ]
        for args in cases:
            proc = self.run_script(*args)
            self.assertEqual(proc.returncode, 2, args)
            self.assertIn("usage:", proc.stderr, args)
            self.assertEqual(proc.stdout, "", args)

    def test_long_option_abbreviations_are_rejected(self):
        root = self.make_repo()
        proc = self.run_script("route", "--project", root, "--base", "main")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
