"""Scenario test: a verify re-run on a legacy workflow.yaml, from the stuck state
to a proceed result of merge-preflight.py.

Covers AC-1..AC-6 of
feature-docs/verify-rerun-legacy-deferred-resolution/tasks/task0002.md.

The fixture is a git repository in a temporary directory with the integration
branch of one feature. Its committed state is the stuck one: every step is
completed or skipped, the verify step has neither `round` nor `passed_ids`, and
the latest review round record (round 2) holds one deferred high finding with
category spec whose claim is one acceptance criterion's miss, written together
with a cause-analysis add-on. The test then plays the orchestrator's side of the
legacy re-run procedure: one workflow.yaml write that records round 1, the
passed IDs and result pass; a mapping file that ties the finding's stable_id to
the criterion ID; a run of resolve-verified-findings.py; a commit of the changed
files to the integration branch; and a second run of merge-preflight.py.

Both scripts run as child processes with the running interpreter and neither is
imported, so no bytecode cache is written under em-workflow/. Every git command
and every script run uses the temporary repository as its working tree. The
commit identity is set inside that repository only, user-level and system-level
git configuration are switched off for the child processes, and the temporary
directory is removed when the test ends. The YAML that the script writes is
parsed in a child process, so this module imports the standard library only (the
scripts need PyYAML at run time all the same).

The orchestrator's mapping judgment is not under test: the mapping file is
written by the test. Nothing here returns verify to pending.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVE_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "resolve-verified-findings.py"
PREFLIGHT_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-preflight.py"

FEATURE = "sample-feature"
BRANCH = f"em-workflow/{FEATURE}/integration"
STABLE_ID = "sample-finding-1"
CRITERION_ID = "AC-1"
OTHER_PASSED_ID = "AC-2"

WORKFLOW_REL = f"feature-docs/{FEATURE}/workflow.yaml"
ROUND1_REL = f"feature-docs/{FEATURE}/reviews/round1.yaml"
ROUND2_REL = f"feature-docs/{FEATURE}/reviews/round2.yaml"

STEP_IDS = (
    "create-spec",
    "design",
    "create-plan",
    "implement",
    "review",
    "verify",
    "retrospect",
)

VERIFY_RESOLUTION_KEYS = {
    "verify_round",
    "verified_commit",
    "criteria_ids",
    "previous_resolution",
    "previous_resolution_reason",
}


def dump_yaml(doc):
    """YAML text for doc. JSON is a YAML subset, and this module imports only the stdlib."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# The YAML that the script writes is parsed in a child process, so that this
# module imports nothing outside the standard library.
PARSE_YAML_SNIPPET = (
    "import json, sys, yaml\n"
    "print(json.dumps(yaml.safe_load(sys.stdin.read()), default=str))\n"
)


def parse_yaml(text):
    proc = subprocess.run(
        [sys.executable, "-B", "-c", PARSE_YAML_SNIPPET],
        input=text,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"the YAML text could not be parsed: {proc.stderr}")
    return json.loads(proc.stdout)


def make_workflow(rerun=False):
    """A workflow.yaml document whose steps are all completed or skipped.

    The legacy form leaves the verify step without `round` and `passed_ids`. With
    `rerun` the document is what one workflow.yaml write of the re-run holds:
    round 1 (one added to the absent round, read as 0), the passed IDs and
    result pass.
    """
    steps = []
    for step_id in STEP_IDS:
        step = {"id": step_id, "status": "skipped" if step_id == "design" else "completed"}
        if step_id == "design":
            step["skipped_reason"] = "no UI"
        if step_id == "verify":
            step["result"] = "pass"
            step["failed_items"] = []
            if rerun:
                step["round"] = 1
                step["passed_ids"] = [CRITERION_ID, OTHER_PASSED_ID]
        steps.append(step)
    return {
        "schema_version": 1,
        "feature": FEATURE,
        "base_branch": "main",
        "goal": "a plain goal",
        "workflow": steps,
    }


def make_round(number, findings):
    return {"round": number, "executed_at": "2026-10-31T00:00:00+09:00", "findings": findings}


def make_finding():
    """One deferred high finding with category spec. Its claim is the miss of
    one acceptance criterion; the cause analysis and the fix suggestion are
    add-ons to that claim (the shape the mapping rule maps)."""
    return {
        "stable_id": STABLE_ID,
        "severity": "high",
        "category": "spec",
        "file": "src/widget.py",
        "line": 12,
        "title": f"Acceptance criterion {CRITERION_ID} is not met",
        "description": (
            f"{CRITERION_ID} requires the widget list to be sorted, and it is not. "
            "Cause: the sort runs before the loader fills the list."
        ),
        "suggestion": "Run the sort after the loader.",
        "reproduction": None,
        "sources": ["claude:spec"],
        "confidence": 90,
        "resolution": "deferred",
        "resolution_reason": "left for a human decision",
    }


class Scenario:
    """The temporary repository and the steps of the legacy re-run scenario."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(os.path.realpath(self._tmp.name))

        home = self.tmp / "home"
        home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(
            {
                "HOME": str(home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        self.env.pop("XDG_CONFIG_HOME", None)

        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        # The commit identity lives in the temporary repository's own config.
        self.git("config", "user.name", "Scenario Test")
        self.git("config", "user.email", "scenario@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / "README.md").write_text("readme\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.feature_dir = self.repo / "feature-docs" / FEATURE
        self.reviews_dir = self.feature_dir / "reviews"
        self.workflow_path = self.feature_dir / "workflow.yaml"
        self.mapping_path = self.tmp / "mapping.json"

    def close(self):
        self._tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    # -- git ----------------------------------------------------------------

    def git(self, *args):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout.strip()

    def head(self):
        return self.git("rev-parse", "HEAD")

    def show_committed(self, relative_path):
        return self.git("show", f"HEAD:{relative_path}")

    # -- the state before the re-run ----------------------------------------

    def build_legacy_fixture(self):
        """Write and commit the stuck state on the integration branch; return
        the commit that the verify commands would have run against."""
        self.feature_dir.mkdir(parents=True)
        self.reviews_dir.mkdir()
        self.workflow_path.write_text(dump_yaml(make_workflow()), encoding="utf-8")
        (self.reviews_dir / "round1.yaml").write_text(
            dump_yaml(make_round(1, [])), encoding="utf-8"
        )
        (self.reviews_dir / "round2.yaml").write_text(
            dump_yaml(make_round(2, [make_finding()])), encoding="utf-8"
        )
        self.git("checkout", "-q", "-b", BRANCH, "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feature records")
        return self.head()

    # -- the orchestrator's side of the re-run ------------------------------

    def record_rerun(self):
        """One workflow.yaml write: round 1, the passed IDs and result pass."""
        self.workflow_path.write_text(dump_yaml(make_workflow(rerun=True)), encoding="utf-8")

    def write_mapping(self):
        self.mapping_path.write_text(json.dumps({STABLE_ID: [CRITERION_ID]}), encoding="utf-8")

    def run_resolve(self, verified_commit):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(RESOLVE_SCRIPT),
                "--feature-dir",
                str(self.feature_dir),
                "--mapping",
                str(self.mapping_path),
                "--verified-commit",
                verified_commit,
            ],
            cwd=str(self.tmp),
            env=self.env,
            capture_output=True,
            text=True,
        )

    def commit_result(self):
        """Commit the changed files to the integration branch; return their names."""
        self.git("add", "--", WORKFLOW_REL, ROUND2_REL)
        self.git("commit", "-q", "-m", "verify result and resolved findings")
        names = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        return sorted(names.splitlines())

    def preflight(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(PREFLIGHT_SCRIPT),
                "--project-root",
                str(self.repo),
                "--feature",
                FEATURE,
            ],
            cwd=str(self.tmp),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"merge-preflight.py exited {proc.returncode}: {proc.stderr}")
        return json.loads(proc.stdout)

    # -- reading back -------------------------------------------------------

    def committed_workflow(self):
        return parse_yaml(self.show_committed(WORKFLOW_REL))

    def committed_round(self, number):
        return parse_yaml(self.show_committed(f"feature-docs/{FEATURE}/reviews/round{number}.yaml"))

    # -- the whole flow -----------------------------------------------------

    def run_to_resolution(self):
        """Fixture, re-run record, mapping and script run (no commit yet).
        Return (the verified commit, the finished script process)."""
        verified_commit = self.build_legacy_fixture()
        self.record_rerun()
        self.write_mapping()
        return verified_commit, self.run_resolve(verified_commit)


def verify_step(workflow):
    steps = [s for s in workflow["workflow"] if s["id"] == "verify"]
    if len(steps) != 1:
        raise AssertionError(f"exactly one verify step is expected: {steps!r}")
    return steps[0]


class ScenarioTestCase(unittest.TestCase):
    def setUp(self):
        self.sc = Scenario()
        self.addCleanup(self.sc.close)

    def assert_resolve_succeeded(self, proc):
        """The run succeeded; return the parsed one-line stdout summary."""
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 1, f"stdout must be exactly one line: {proc.stdout!r}")
        return json.loads(lines[0])


class TestAc1BeforeTheRerun(ScenarioTestCase):
    """AC-1 (TS-3): the stuck state stops at the review-findings check."""

    def setUp(self):
        super().setUp()
        self.sc.build_legacy_fixture()

    def test_ac1_the_committed_workflow_is_legacy_and_every_step_is_completed_or_skipped(self):
        workflow = self.sc.committed_workflow()
        self.assertTrue(all(s["status"] in ("completed", "skipped") for s in workflow["workflow"]))
        verify = verify_step(workflow)
        self.assertEqual(verify["status"], "completed")
        self.assertNotIn("round", verify)
        self.assertNotIn("passed_ids", verify)

    def test_ac1_the_latest_round_holds_one_deferred_high_spec_finding(self):
        record = self.sc.committed_round(2)
        self.assertEqual(len(record["findings"]), 1)
        finding = record["findings"][0]
        self.assertEqual(finding["stable_id"], STABLE_ID)
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["category"], "spec")
        self.assertEqual(finding["resolution"], "deferred")
        self.assertIn(CRITERION_ID, finding["title"])

    def test_ac1_preflight_returns_unresolved_findings_before_the_rerun(self):
        result = self.sc.preflight()
        self.assertEqual(result["outcome"], "stop", result)
        self.assertEqual(result["reason"], "unresolved_findings", result)
        self.assertIn(STABLE_ID, result["detail"])


class TestAc2TheRerunRecordAndTheScript(ScenarioTestCase):
    """AC-2 (TS-4): after the re-run is recorded, the script reports success."""

    def test_ac2_the_rerun_write_holds_round_1_the_passed_ids_and_result_pass(self):
        self.sc.build_legacy_fixture()
        self.sc.record_rerun()
        verify = verify_step(parse_yaml(self.sc.workflow_path.read_text(encoding="utf-8")))
        self.assertEqual(verify["result"], "pass")
        self.assertEqual(verify["round"], 1)
        self.assertIn(CRITERION_ID, verify["passed_ids"])

    def test_ac2_resolve_verified_findings_reports_success_with_the_finding_fixed(self):
        _, proc = self.sc.run_to_resolution()
        summary = self.assert_resolve_succeeded(proc)
        self.assertEqual(
            summary,
            {
                "review_round": 2,
                "verify_round": 1,
                "fixed": [{"stable_id": STABLE_ID, "criteria_ids": [CRITERION_ID]}],
                "not_applied": 0,
            },
        )


class TestAc3AfterTheCommit(ScenarioTestCase):
    """AC-3 (TS-4): after the commit, the finding is fixed and preflight proceeds."""

    def test_ac3_the_resolution_is_not_seen_before_it_is_committed(self):
        _, proc = self.sc.run_to_resolution()
        self.assert_resolve_succeeded(proc)
        result = self.sc.preflight()
        self.assertEqual(result["outcome"], "stop", result)
        self.assertEqual(result["reason"], "unresolved_findings", result)

    def test_ac3_the_commit_holds_the_workflow_and_the_round_record_only(self):
        _, proc = self.sc.run_to_resolution()
        self.assert_resolve_succeeded(proc)
        self.assertEqual(self.sc.commit_result(), sorted([WORKFLOW_REL, ROUND2_REL]))

    def test_ac3_the_finding_has_resolution_fixed_and_a_verify_resolution_field(self):
        verified_commit, proc = self.sc.run_to_resolution()
        self.assert_resolve_succeeded(proc)
        self.sc.commit_result()
        finding = self.sc.committed_round(2)["findings"][0]
        self.assertEqual(finding["stable_id"], STABLE_ID)
        self.assertEqual(finding["resolution"], "fixed")
        provenance = finding["verify_resolution"]
        self.assertEqual(set(provenance), VERIFY_RESOLUTION_KEYS)
        self.assertEqual(provenance["verify_round"], 1)
        self.assertEqual(provenance["verified_commit"], verified_commit)
        self.assertEqual(provenance["criteria_ids"], [CRITERION_ID])
        self.assertEqual(provenance["previous_resolution"], "deferred")

    def test_ac3_preflight_proceeds_after_the_result_is_committed(self):
        _, proc = self.sc.run_to_resolution()
        self.assert_resolve_succeeded(proc)
        self.sc.commit_result()
        result = self.sc.preflight()
        self.assertEqual(result["outcome"], "proceed", result)
        self.assertIsNone(result["reason"])
        self.assertEqual(result["integration_branch"], BRANCH)
        self.assertEqual(result["integration_tip"], self.sc.head())
        self.assertEqual(result["review_round"], 2)


def imported_modules(path):
    modules = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def real_repository_state():
    """The real repository's working-tree status and the user-level git
    configuration files, as this process sees them. Everything is read, nothing
    is written (GIT_OPTIONAL_LOCKS=0 keeps `git status` from refreshing the index)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        env=env,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    configs = {}
    home = Path(os.path.expanduser("~"))
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    for path in (home / ".gitconfig", Path(xdg) / "git" / "config"):
        try:
            configs[str(path)] = path.read_bytes()
        except OSError:
            configs[str(path)] = None
    return {"status": proc.stdout, "user_configs": configs}


class TestAc4Isolation(unittest.TestCase):
    """AC-4: the standard library only, child processes, a temporary repository."""

    def test_ac4_this_module_imports_the_standard_library_only(self):
        names = getattr(sys, "stdlib_module_names", None)
        if names is None:
            self.skipTest("sys.stdlib_module_names is not available")
        self.assertEqual(imported_modules(__file__) - set(names), set())

    def test_ac4_neither_script_is_loaded_into_this_process(self):
        self.assertEqual(imported_modules(__file__) & {"importlib", "runpy", "imp"}, set())

    def test_ac4_the_scenario_leaves_the_real_repository_and_user_git_config_unchanged(self):
        before = real_repository_state()
        if before is None:
            self.skipTest("the real repository status is not readable")
        with Scenario() as sc:
            tmp = sc.tmp
            self.assertTrue(str(tmp).startswith(os.path.realpath(tempfile.gettempdir())))
            self.assertNotEqual(sc.repo, REPO_ROOT)
            _, proc = sc.run_to_resolution()
            self.assertEqual(proc.returncode, 0, proc.stderr)
            sc.commit_result()
            self.assertEqual(sc.preflight()["outcome"], "proceed")
            # The commit identity is in the temporary repository's own config.
            self.assertEqual(
                sc.git("config", "--local", "user.email"), "scenario@example.invalid"
            )
        self.assertFalse(tmp.exists(), "the temporary directory must be removed")
        self.assertEqual(real_repository_state(), before)


if __name__ == "__main__":
    unittest.main()
