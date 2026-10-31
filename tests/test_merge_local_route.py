"""TS1: the local-route chain end to end (task0003, AC-7).

The chain is route -> merged -> worktree-state -> integrate -> base-check ->
main-tree, all through merge-git.py, followed by emulation of the skill's own
direct operations (the main-tree merge of D9 and a worktree removal without
force). The full-chain case runs merge-preflight.py first and is skipped, with
a reason naming that script, only when the script is absent.

Every test uses its own temporary repository with no remote. A PATH-prepended
git logging shim records the git invocations of the scripts under test, and
every run is checked against the operation boundary: no push, rebase, reset,
worktree add / remove, force option, hook bypass or forced refspec.
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
SCRIPTS = REPO_ROOT / "em-workflow" / "scripts"
MERGE_GIT = SCRIPTS / "merge-git.py"
PREFLIGHT = SCRIPTS / "merge-preflight.py"
REAL_GIT = shutil.which("git")

FEATURE = "ts1-feature"
BRANCH = "em-workflow/%s/integration" % FEATURE
SEP = "\x1f"

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

WORKFLOW_YAML = """\
schema_version: 1
feature: %(feature)s
created: '2026-10-31'
base_branch: main
parent_branch: %(branch)s
tier: full
project:
  license: none
  design_system:
    kind: none
    paths: []
  components:
    main:
      language: python
      build_command: ''
      test_command: ''
      format_command: ''
      e2e_test_command: ''
workflow:
- id: create-spec
  status: completed
- id: design
  status: skipped
  skipped_reason: not needed
- id: create-plan
  status: completed
- id: implement
  status: completed
- id: review
  status: completed
- id: verify
  status: completed
  result: pass
  failed_items: []
- id: retrospect
  status: completed
""" % {"feature": FEATURE, "branch": BRANCH}


def subcommand_of(argv):
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


class LocalRouteBase(unittest.TestCase):
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
                "EM_WORKFLOW_APPROVALS": str(self.tmp / "no-approvals.json"),
            }
        )
        self.env = env
        self.script_env = dict(env)
        self.script_env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
        self.script_env["MERGE_GIT_TEST_LOG"] = str(self.log)
        self.script_env["MERGE_GIT_TEST_REAL_GIT"] = REAL_GIT

        self.build_fixture()

    # ---- fixture ----

    def git(self, cwd, *args):
        proc = subprocess.run(
            [REAL_GIT, "-C", str(cwd)] + list(args),
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            self.fail("git %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout.strip()

    def commit_file(self, cwd, relpath, content, message):
        target = Path(cwd) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)
        return self.git(cwd, "rev-parse", "HEAD")

    def build_fixture(self):
        """No remote; .claude/worktrees/ ignored; base advanced after the fork."""
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.git(self.root, "init", "-q", "-b", "main")
        (self.root / ".gitignore").write_text(".claude/worktrees/\n")
        (self.root / "README.md").write_text("project\n")
        self.git(self.root, "add", "-A")
        self.git(self.root, "commit", "-q", "-m", "initial")

        self.worktree = (
            self.root / ".claude" / "worktrees" / "em-workflow" / FEATURE / "integration"
        )
        self.git(self.root, "worktree", "add", "-q", "-b", BRANCH, str(self.worktree))
        self.commit_file(
            self.worktree,
            "feature-docs/%s/workflow.yaml" % FEATURE,
            WORKFLOW_YAML,
            "docs: workflow completed",
        )
        self.integration_tip_before = self.commit_file(
            self.worktree, "src/feature.txt", "feature\n", "feature work"
        )
        # The base moves on after the integration branch forked.
        self.base_tip_before = self.git(self.root, "rev-parse", "main")
        self.base_advance = self.commit_file(
            self.root, "base-only.txt", "base only\n", "base moves on"
        )

    # ---- script runner ----

    def check_log(self):
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

    def run_json(self, script, *args):
        proc = subprocess.run(
            ["python3", str(script)] + [str(a) for a in args],
            env=self.script_env,
            cwd=str(self.tmp),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.check_log()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.split("\n")
        self.assertEqual(len(lines), 2, proc.stdout)
        data = json.loads(lines[0])
        self.assertIsInstance(data, dict)
        return data

    def merge_git(self, command, *args):
        return self.run_json(MERGE_GIT, command, "--project-root", self.root, *args)

    # ---- the chain ----

    def run_chain(self):
        """Run every decision script of the local route; return the decisions."""
        steps = {}
        steps["route"] = self.merge_git("route", "--base", "main")
        self.assertEqual(steps["route"]["outcome"], "local")

        steps["merged"] = self.merge_git("merged", "--feature", FEATURE, "--base", "main")
        self.assertEqual(steps["merged"]["outcome"], "not_merged")

        steps["state"] = self.merge_git("worktree-state", "--feature", FEATURE)
        self.assertEqual(steps["state"]["outcome"], "clean")
        self.assertEqual(steps["state"]["worktree_path"], str(self.worktree))

        steps["integrate"] = self.merge_git(
            "integrate", "--feature", FEATURE, "--base", "main"
        )
        self.assertEqual(steps["integrate"]["outcome"], "merged_clean")
        self.assertEqual(steps["integrate"]["integrated_base"], self.base_advance)

        steps["base_check"] = self.merge_git(
            "base-check",
            "--base",
            "main",
            "--integrated-base",
            steps["integrate"]["integrated_base"],
            "--redo-count",
            "0",
        )
        self.assertEqual(steps["base_check"]["outcome"], "unchanged")

        steps["main_tree"] = self.merge_git("main-tree", "--base", "main")
        self.assertEqual(steps["main_tree"]["outcome"], "ready")
        return steps

    def emulate_skill_operations(self, integration_tip):
        """The skill's direct operations: main-tree merge, then worktree removal."""
        self.git(self.root, "merge", "--no-ff", "--no-edit", BRANCH)
        self.git(self.root, "worktree", "remove", str(self.worktree))

    def assert_final_state(self, integration_tip):
        parents = self.git(self.root, "rev-list", "--parents", "-n", "1", "main").split()
        self.assertEqual(len(parents), 3, "main tip is not a merge commit")
        self.assertEqual(parents[1], self.base_advance)
        self.assertEqual(parents[2], integration_tip)
        self.assertFalse(self.worktree.exists())
        listing = self.git(self.root, "worktree", "list", "--porcelain")
        self.assertNotIn(str(self.worktree), listing)
        self.git(self.root, "rev-parse", "--verify", "refs/heads/main")
        self.git(self.root, "rev-parse", "--verify", "refs/heads/" + BRANCH)
        self.assertTrue(
            (self.root / "feature-docs" / FEATURE / "workflow.yaml").is_file()
        )
        self.assertEqual(self.git(self.root, "status", "--porcelain=v1"), "")


class LocalRouteCoreTests(LocalRouteBase):
    """TS1 core case: merge-git.py alone plus emulated direct operations."""

    def test_ac7_core_case_lands_a_merge_commit_and_removes_the_worktree(self):
        steps = self.run_chain()
        integration_tip = steps["integrate"]["head"]
        self.assertEqual(integration_tip, self.git(self.root, "rev-parse", BRANCH))
        self.assertNotEqual(integration_tip, self.integration_tip_before)
        self.emulate_skill_operations(integration_tip)
        self.assert_final_state(integration_tip)

    def test_ac7_core_case_is_resumable_after_the_merge(self):
        steps = self.run_chain()
        self.emulate_skill_operations(steps["integrate"]["head"])
        merged = self.merge_git("merged", "--feature", FEATURE, "--base", "main")
        self.assertEqual(merged["outcome"], "merged")
        state = self.merge_git("worktree-state", "--feature", FEATURE)
        self.assertEqual(state["outcome"], "absent")


@unittest.skipUnless(
    PREFLIGHT.is_file(),
    "em-workflow/scripts/merge-preflight.py is not present",
)
class LocalRouteFullChainTests(LocalRouteBase):
    """TS1 full-chain case: merge-preflight.py runs before the core sequence."""

    def test_ac7_full_chain_passes_with_preflight_first(self):
        preflight = self.run_json(
            PREFLIGHT, "--project-root", self.root, "--feature", FEATURE
        )
        self.assertEqual(preflight["outcome"], "proceed", preflight)
        self.assertEqual(preflight["base_branch"], "main")
        self.assertEqual(preflight["integration_branch"], BRANCH)
        self.assertEqual(preflight["integration_tip"], self.integration_tip_before)
        self.assertEqual(
            os.path.realpath(preflight["project_root"]), os.path.realpath(self.root)
        )
        self.assertEqual(preflight["worktree_path"], str(self.worktree))

        steps = self.run_chain()
        self.assertEqual(steps["state"]["worktree_path"], preflight["worktree_path"])
        self.emulate_skill_operations(steps["integrate"]["head"])
        self.assert_final_state(steps["integrate"]["head"])


if __name__ == "__main__":
    unittest.main()
