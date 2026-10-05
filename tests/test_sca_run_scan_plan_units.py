"""Tests for sca-file-tasks-robustness task0004 (FR6): `run_scan` consumes the
plans `build_scan_jobs` returns, so the code path the tests exercise is the
code path production runs.

Covers the task's Acceptance Criteria
(feature-docs/sca-file-tasks-robustness/tasks/task0004.md):

- AC-4 (FR6, TM-5): with `build_scan_jobs` replaced by a recording test
  double that returns a plan whose `target` differs from what
  `manifest_file_for` would pick from the plan's `files`, `run_scan` calls it
  exactly once and launches the scanner for the plan's `target`.
- AC-5 (TM-5, NFR1): with a test double that calls the real
  `build_scan_jobs` and then swaps an npm / cargo (go as well) plan's project
  directory for a symlink escaping the root, `run_scan` launches nothing for
  that plan, creates no isolation directory for it and reports
  `<ecosystem>_project_unbindable`; the run side keeps its order -- plan, then
  per group the binding check, the isolation directory (npm / cargo only),
  `build_scan_job` and the launch.
- AC-3 (run side): an ecosystem whose entry fails validation or whose
  executable does not resolve gets its reason once, and no path verification
  or binding check runs for it.
- AC-6: the argument vector, environment and working directory assertions
  that used to be made on the jobs `build_scan_jobs` built are made here on
  what `run_scan` really launches: npm argv with the workspace flag, cargo
  argv with the target flag and the copied lockfile, go argv, pip argv,
  absolute argv[0], npm / cargo cwd in their own isolation directory, go cwd
  in the group directory, pip cwd the project root. (The npm / cargo job
  without prepared inputs being rejected by `build_scan_job` is asserted in
  tests/test_sca_scanner_project_config_isolation.py.)
- AC-8: this module and the three modules task0004 rewrote import the
  standard library only.

Per the task's Test Notes: no real scanner runs. Each tool is a recording
stub on a PATH restricted to its own directory; on every launch it records
its working directory, argument vector, environment and the regular files in
its working directory BEFORE the isolation directory is removed. The
isolation temp parent is a dedicated, empty directory beside the project
tree; the process-wide temp-directory cache is reset before and restored
after every run. Replacing `build_scan_jobs` on the loaded module is the
intended technique (SPEC TS9). This module owns its own harness and imports
the standard library only.
"""

import ast
import contextlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"
TESTS_DIR = REPO_ROOT / "tests"
SIBLING_MODULES = (
    "test_sca_run_scan_plan_units.py",
    "test_sca_scan_job_grouping.py",
    "test_sca_scan_invocation.py",
    "test_sca_scanner_project_config_isolation.py",
)


def _load_script(name="scan_dependencies_run_scan_plan_units"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

NPM_CLEAN = {"vulnerabilities": {}}
CARGO_CLEAN = {"vulnerabilities": {"found": False, "list": []}}
GO_CLEAN = {"config": {"protocol_version": "v1.0.0", "scanner_name": "govulncheck"}}
PIP_CLEAN = {"dependencies": []}
NPM_VULN = {
    "vulnerabilities": {
        "lodash": {
            "name": "lodash",
            "severity": "critical",
            "isDirect": True,
            "range": "<4.17.21",
            "fixAvailable": {"name": "lodash", "version": "4.17.21"},
            "via": [
                {
                    "source": 1,
                    "name": "lodash",
                    "title": "Prototype Pollution in lodash",
                    "url": "https://github.com/advisories/GHSA-p6mc-m468-83gw",
                    "severity": "critical",
                    "range": "<4.17.21",
                }
            ],
        }
    }
}

# tool -> (stdout payload, exit status): every scanner reports a clean scan.
CLEAN_STUBS = {
    "npm": (NPM_CLEAN, 0),
    "cargo-audit": (CARGO_CLEAN, 0),
    "govulncheck": (GO_CLEAN, 0),
    "pip-audit": (PIP_CLEAN, 0),
}

_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.basename(__file__)
with open(os.path.join(HERE, TOOL + ".config.json"), encoding="utf-8") as fh:
    CONFIG = json.load(fh)

cwd = os.path.realpath(os.getcwd())
files = {}
for name in sorted(os.listdir(cwd)):
    path = os.path.join(cwd, name)
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            files[name] = fh.read().decode("latin-1")

record = {
    "tool": TOOL,
    "argv": sys.argv,
    "cwd": cwd,
    "env": dict(os.environ),
    "files": files,
}
with open(CONFIG["record"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
sys.stdout.write(json.dumps(CONFIG["payload"]))
sys.exit(CONFIG["exit_code"])
'''


def inside(root, path):
    """True when `path` equals `root` or lies under it, by path components."""
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(root))


class RunScanCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.outside = self.base / "outside"
        self.bin_dir = self.base / "bin"
        self.iso_tmp = self.base / "iso-tmp"
        self.records_dir = self.base / "records"
        self.home = self.base / "home"
        for directory in (
            self.root, self.outside, self.bin_dir, self.iso_tmp, self.records_dir, self.home
        ):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"
        for tool, (payload, exit_code) in CLEAN_STUBS.items():
            self.configure(tool, payload, exit_code)
            stub = self.bin_dir / tool
            stub.write_text(_STUB_SOURCE.replace("__PYTHON__", sys.executable), encoding="utf-8")
            stub.chmod(0o755)
        self.registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        self.entries = {e["ecosystem"]: e for e in self.registry["ecosystems"]}

    # -- fixtures ---------------------------------------------------------

    def configure(self, tool, payload, exit_code=0):
        config = {"record": str(self.record_path), "payload": payload, "exit_code": exit_code}
        (self.bin_dir / f"{tool}.config.json").write_text(json.dumps(config), encoding="utf-8")

    def write(self, rel, text, base=None):
        path = (self.root if base is None else base) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def npm_project(self, rel_dir="", base=None):
        """package.json and package-lock.json whose content names the
        directory, so a launch can be traced back to its project."""
        prefix = f"{rel_dir}/" if rel_dir else ""
        tag = rel_dir or "root"
        self.write(f"{prefix}package.json", f'{{"name": "{tag}"}}\n', base)
        self.write(f"{prefix}package-lock.json", f'{{"lock": "{tag}"}}\n', base)

    def cargo_project(self, rel_dir="", base=None):
        prefix = f"{rel_dir}/" if rel_dir else ""
        tag = rel_dir or "root"
        self.write(f"{prefix}Cargo.toml", f'[package]\nname = "{tag}"\n\n[dependencies]\n', base)
        self.write(f"{prefix}Cargo.lock", f"# Cargo.lock of {tag}\n", base)

    def go_project(self, rel_dir="", base=None):
        prefix = f"{rel_dir}/" if rel_dir else ""
        self.write(f"{prefix}go.mod", "module example.com/m\n\ngo 1.21\n", base)

    # -- running ----------------------------------------------------------

    @contextlib.contextmanager
    def runner_environment(self):
        """PATH is the stub directory only and the temp parent the dedicated
        empty directory; the cached temp selection is reset before and
        restored after. A secret in the reviewing process's environment is
        planted so a leak into a child environment is visible."""
        saved_cache = tempfile.tempdir
        with mock.patch.dict(os.environ):
            for key in ("TMPDIR", "TEMP", "TMP"):
                os.environ.pop(key, None)
            os.environ["PATH"] = str(self.bin_dir)
            os.environ["HOME"] = str(self.home)
            os.environ["TMPDIR"] = str(self.iso_tmp)
            os.environ["SCA_TEST_SECRET"] = "must-not-reach-a-scanner"
            tempfile.tempdir = None
            try:
                yield
            finally:
                tempfile.tempdir = saved_cache

    def scan(self, changed_files, registry_path=None):
        with self.runner_environment():
            return SCAN.run_scan(
                self.root, changed_files, registry_path or SCAN.DEFAULT_REGISTRY_PATH
            )

    def launches(self, tool=None):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        return [r for r in records if tool is None or r["tool"] == tool]

    def project_of(self, record, name):
        """The tag of the project a launch belonged to, read from the copy of
        its input the scanner found in its working directory."""
        return json.loads(record["files"][name])["name" if name == "package.json" else "lock"]

    def assertNoIsolationDirectoryRemains(self):
        self.assertEqual(sorted(p.name for p in self.iso_tmp.iterdir()), [])

    # -- test doubles -----------------------------------------------------

    def planner(self, transform=None):
        """A `build_scan_jobs` double: it calls the real function, lets
        `transform(plans, reasons)` change what it returns, and keeps the
        returned values. Returns `(patch, returned)`."""
        real = SCAN.build_scan_jobs
        returned = []

        def double(*args, **kwargs):
            plans, reasons = real(*args, **kwargs)
            if transform is not None:
                plans, reasons = transform(plans, reasons)
            returned.append((list(plans), list(reasons)))
            return plans, reasons

        return mock.patch.object(SCAN, "build_scan_jobs", side_effect=double), returned

    def plan_for(self, name, files, target, directory=""):
        """A plan built by hand for ecosystem `name`."""
        executable = {"npm": "npm", "cargo": "cargo-audit", "go": "govulncheck", "pip": "pip-audit"}[name]
        return SCAN.ScanPlan(
            ecosystem=self.entries[name],
            directory=directory,
            real_root=os.path.realpath(self.root),
            files=tuple(files),
            target=target,
            executable=str(self.bin_dir / executable),
        )

    @contextlib.contextmanager
    def traced(self):
        """Records, in call order, the planning stage, each binding check, each
        isolation directory, each job construction and each launch."""
        events = []

        def traced_call(label, name):
            real = getattr(SCAN, name)

            def wrapper(*args, **kwargs):
                events.append(label)
                return real(*args, **kwargs)

            return wrapper

        with contextlib.ExitStack() as stack:
            for label, name in (
                ("plan", "build_scan_jobs"),
                ("binding", "_binding_check"),
                ("isolation", "isolation_workspace"),
                ("job", "build_scan_job"),
                ("launch", "run_ecosystem_command"),
            ):
                stack.enter_context(mock.patch.object(SCAN, name, traced_call(label, name)))
            yield events


# ---------------------------------------------------------------------------
# AC-4 (FR6, TM-5): run_scan goes through build_scan_jobs and launches exactly
# the plans it returns.
# ---------------------------------------------------------------------------

class TestRunScanLaunchesThePlansBuildScanJobsReturns(RunScanCase):
    def test_build_scan_jobs_is_called_exactly_once_and_one_scanner_is_launched_per_plan(self):
        self.npm_project("a")
        self.npm_project("b")
        self.cargo_project("")
        changed = ["b/package.json", "a/package.json", "Cargo.toml"]
        patch, returned = self.planner()
        with patch as planner:
            result = self.scan(changed)
        self.assertEqual(planner.call_count, 1)
        registry, changed_files, project_root = planner.call_args.args
        self.assertEqual(registry["ecosystems"], self.registry["ecosystems"])
        self.assertEqual(changed_files, changed)
        self.assertEqual(project_root, self.root)
        ((plans, reasons),) = returned
        self.assertEqual(reasons, [])
        self.assertEqual(
            [(p.ecosystem["ecosystem"], p.target) for p in plans],
            [("npm", "a/package.json"), ("npm", "b/package.json"), ("cargo", "Cargo.toml")],
        )
        launches = self.launches()
        self.assertEqual([r["tool"] for r in launches], ["npm", "npm", "cargo-audit"])
        self.assertEqual(
            [self.project_of(r, "package.json") for r in launches[:2]], ["a", "b"]
        )
        self.assertFalse(result["skipped"], result)

    def test_the_scan_launches_exactly_the_plans_the_planner_returns(self):
        self.npm_project("a")
        self.npm_project("b")
        patch, _returned = self.planner(lambda plans, reasons: (plans[:1], reasons))
        with patch:
            result = self.scan(["a/package.json", "b/package.json"])
        (record,) = self.launches("npm")
        self.assertEqual(self.project_of(record, "package.json"), "a")
        self.assertFalse(result["skipped"], result)

    def test_the_reasons_the_planner_returns_reach_the_result(self):
        self.npm_project("")
        patch, _returned = self.planner(
            lambda plans, reasons: (plans, reasons + ["cargo_tool_not_found"])
        )
        with patch:
            result = self.scan(["package.json"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "cargo_tool_not_found")
        self.assertEqual(len(self.launches("npm")), 1)

    def test_a_planner_that_returns_nothing_launches_nothing(self):
        self.npm_project("")
        patch, _returned = self.planner(lambda plans, reasons: ([], []))
        with patch:
            self.scan(["package.json"])
        self.assertEqual(self.launches(), [])

    def test_an_npm_plan_is_launched_for_its_own_target_not_for_a_reselected_one(self):
        self.npm_project("")
        self.configure("npm", NPM_VULN, exit_code=1)
        plan = self.plan_for("npm", files=("package.json",), target="package-lock.json")
        # The premise: manifest_file_for would pick package.json from the files.
        self.assertEqual(SCAN.manifest_file_for(plan.ecosystem, list(plan.files)), "package.json")
        with mock.patch.object(
            SCAN, "build_scan_jobs", return_value=([plan], [])
        ) as planner, mock.patch.object(
            SCAN, "manifest_file_for", side_effect=AssertionError("target selected again")
        ):
            result = self.scan(["package.json"])
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(len(self.launches("npm")), 1)
        self.assertEqual([f["file"] for f in result["findings"]], ["package-lock.json"])

    def test_a_pip_plan_is_launched_for_its_own_target_not_for_a_reselected_one(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.write("pyproject.toml", "[project]\nname = 'p'\n")
        plan = self.plan_for(
            "pip", files=("pyproject.toml", "requirements.txt"), target="requirements.txt"
        )
        self.assertEqual(SCAN.manifest_file_for(plan.ecosystem, list(plan.files)), "pyproject.toml")
        with mock.patch.object(
            SCAN, "build_scan_jobs", return_value=([plan], [])
        ) as planner, mock.patch.object(
            SCAN, "manifest_file_for", side_effect=AssertionError("target selected again")
        ):
            self.scan(["pyproject.toml", "requirements.txt"])
        self.assertEqual(planner.call_count, 1)
        (record,) = self.launches("pip-audit")
        self.assertEqual(
            record["argv"], [str(self.bin_dir / "pip-audit"), "-r", "requirements.txt", "--format", "json"]
        )

    def test_the_binding_check_runs_against_the_basename_of_the_plans_target(self):
        self.go_project("svc")
        plan = self.plan_for("go", files=("svc/go.mod",), target="svc/go.sum", directory="svc")
        with mock.patch.object(SCAN, "build_scan_jobs", return_value=([plan], [])):
            result = self.scan(["svc/go.mod"])
        # svc/go.sum does not exist: a deleted target is unbindable, although
        # go.mod, the file manifest_file_for would pick, is there.
        self.assertEqual(self.launches(), [])
        self.assertEqual(result["skip_reason"], "go_project_unbindable")
        self.write("svc/go.sum", "")
        with mock.patch.object(SCAN, "build_scan_jobs", return_value=([plan], [])):
            result = self.scan(["svc/go.mod"])
        self.assertEqual(len(self.launches("govulncheck")), 1)
        self.assertFalse(result["skipped"], result)

    def test_the_early_return_for_a_change_without_a_manifest_does_not_plan(self):
        with mock.patch.object(SCAN, "build_scan_jobs", side_effect=AssertionError("planned")):
            result = self.scan(["README.md", "src/app.js"])
        self.assertFalse(result["skipped"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(self.launches(), [])

    def test_the_early_return_for_an_unsupported_manifest_does_not_plan(self):
        with mock.patch.object(SCAN, "build_scan_jobs", side_effect=AssertionError("planned")):
            result = self.scan(["composer.json"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "composer_unsupported")


# ---------------------------------------------------------------------------
# AC-5 (TM-5, NFR1): the run side keeps its binding check after planning.
# ---------------------------------------------------------------------------

class TestTheRunSideBindingCheckGuardsTheWindowAfterPlanning(RunScanCase):
    def swap_directory_for_escaping_symlink(self, rel):
        """What an attacker could do between planning and launch: the project
        directory becomes a symlink to a complete project outside the root."""
        shutil.rmtree(self.root / rel)
        (self.root / rel).symlink_to(self.outside / rel)

    def scan_with_swap(self, changed, swap):
        """Plans for real, then runs `swap(plans)` before `run_scan` goes on.
        Returns `(result, planner, isolation)`: the mocks of the planner and of
        the isolation directory."""
        patch, _returned = self.planner(lambda plans, reasons: (swap(plans) or plans, reasons))
        with patch as planner, mock.patch.object(
            SCAN, "isolation_workspace", wraps=SCAN.isolation_workspace
        ) as isolation:
            result = self.scan(changed)
        return result, planner, isolation

    def assertNotLaunchedForTheSwappedPlan(self, result, planner, isolation, name):
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(self.launches(), [])
        self.assertEqual(isolation.call_count, 0, "an isolation directory was prepared")
        self.assertNoIsolationDirectoryRemains()
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], f"{name}_project_unbindable")
        self.assertEqual(result["findings"], [])

    def test_a_swapped_npm_project_directory_launches_nothing_and_gets_no_isolation_directory(self):
        self.npm_project("svc")
        self.npm_project("svc", base=self.outside)
        result, planner, isolation = self.scan_with_swap(
            ["svc/package.json"], lambda plans: self.swap_directory_for_escaping_symlink("svc")
        )
        self.assertNotLaunchedForTheSwappedPlan(result, planner, isolation, "npm")

    def test_a_swapped_cargo_project_directory_launches_nothing_and_gets_no_isolation_directory(self):
        self.cargo_project("svc")
        self.cargo_project("svc", base=self.outside)
        result, planner, isolation = self.scan_with_swap(
            ["svc/Cargo.toml"], lambda plans: self.swap_directory_for_escaping_symlink("svc")
        )
        self.assertNotLaunchedForTheSwappedPlan(result, planner, isolation, "cargo")

    def test_a_swapped_go_project_directory_launches_nothing(self):
        self.go_project("svc")
        self.go_project("svc", base=self.outside)
        result, planner, isolation = self.scan_with_swap(
            ["svc/go.mod"], lambda plans: self.swap_directory_for_escaping_symlink("svc")
        )
        self.assertNotLaunchedForTheSwappedPlan(result, planner, isolation, "go")

    def test_without_the_swap_the_same_plans_are_launched(self):
        self.npm_project("svc")
        self.cargo_project("crate")
        self.go_project("mod")
        result, planner, isolation = self.scan_with_swap(
            ["svc/package.json", "crate/Cargo.toml", "mod/go.mod"], lambda plans: None
        )
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(
            [r["tool"] for r in self.launches()], ["npm", "cargo-audit", "govulncheck"]
        )
        self.assertEqual(isolation.call_count, 2)
        self.assertFalse(result["skipped"], result)

    def test_a_target_swapped_for_a_link_into_another_directory_is_not_launched(self):
        self.npm_project("svc")
        self.npm_project("svc", base=self.outside)

        def swap(plans):
            (self.root / "svc" / "package.json").unlink()
            (self.root / "svc" / "package.json").symlink_to(self.outside / "svc" / "package.json")

        result, planner, isolation = self.scan_with_swap(["svc/package.json"], swap)
        self.assertNotLaunchedForTheSwappedPlan(result, planner, isolation, "npm")

    def test_a_target_deleted_after_planning_is_not_launched(self):
        self.npm_project("svc")

        def swap(plans):
            (self.root / "svc" / "package.json").unlink()

        result, planner, isolation = self.scan_with_swap(["svc/package.json"], swap)
        self.assertNotLaunchedForTheSwappedPlan(result, planner, isolation, "npm")

    def test_a_swapped_plan_does_not_disturb_the_valid_plans_beside_it(self):
        self.npm_project("bad")
        self.npm_project("bad", base=self.outside)
        self.npm_project("ok")
        result, planner, isolation = self.scan_with_swap(
            ["bad/package.json", "ok/package.json"],
            lambda plans: self.swap_directory_for_escaping_symlink("bad"),
        )
        (record,) = self.launches("npm")
        self.assertEqual(self.project_of(record, "package.json"), "ok")
        self.assertEqual(isolation.call_count, 1)
        self.assertEqual(result["skip_reason"], "npm_project_unbindable")
        self.assertNoIsolationDirectoryRemains()


class TestTheRunSideOrder(RunScanCase):
    def setUp(self):
        super().setUp()
        self.npm_project("")
        self.cargo_project("")
        self.go_project("")
        self.write("requirements.txt", "django==3.2.0\n")

    def test_each_ecosystem_runs_its_stages_in_order_after_one_planning_step(self):
        expected = {
            "package.json": ["plan", "binding", "isolation", "job", "launch"],
            "Cargo.toml": ["plan", "binding", "isolation", "job", "launch"],
            "go.mod": ["plan", "binding", "job", "launch"],
            "requirements.txt": ["plan", "job", "launch"],
        }
        for changed, events_expected in expected.items():
            with self.subTest(changed=changed):
                with self.traced() as events:
                    result = self.scan([changed])
                self.assertEqual(events, events_expected)
                self.assertFalse(result["skipped"], result)

    def test_planning_comes_before_the_first_launch_and_the_check_before_each_isolation(self):
        self.npm_project("a")
        self.npm_project("b")
        with self.traced() as events:
            self.scan(["b/package.json", "a/package.json"])
        self.assertEqual(
            events,
            ["plan"] + ["binding", "isolation", "job", "launch"] * 2,
        )

    def test_a_group_that_fails_the_binding_check_gets_no_isolation_directory_and_no_job(self):
        (self.root / "package-lock.json").unlink()
        with self.traced() as events:
            result = self.scan(["package.json"])
        self.assertEqual(events, ["plan", "binding"])
        self.assertEqual(result["skip_reason"], "npm_project_unbindable")
        self.assertEqual(self.launches(), [])
        self.assertNoIsolationDirectoryRemains()


# ---------------------------------------------------------------------------
# AC-3 (FR6, TM-5), run side: no path verification for an ecosystem that
# failed its gate.
# ---------------------------------------------------------------------------

class TestAnEcosystemThatFailedItsGateGetsNoPathWork(RunScanCase):
    STEPS = ("_verified_real_root", "_verified_groups", "_verified_directory", "_binding_check")

    @contextlib.contextmanager
    def recorded(self):
        with contextlib.ExitStack() as stack:
            yield {
                name: stack.enter_context(mock.patch.object(SCAN, name, wraps=getattr(SCAN, name)))
                for name in self.STEPS
            }

    def test_an_unresolvable_executable_gives_its_reason_once_and_no_path_work(self):
        self.npm_project("")
        (self.bin_dir / "npm").unlink()
        with self.recorded() as steps:
            result = self.scan(["package.json", "/abs/package.json"])
        self.assertEqual(result["skip_reason"], "npm_tool_not_found")
        for name, mock_ in steps.items():
            with self.subTest(step=name):
                self.assertEqual(mock_.call_count, 0)
        self.assertEqual(self.launches(), [])

    def test_a_failing_ecosystem_leaves_the_path_work_to_the_others(self):
        self.npm_project("")
        self.cargo_project("")
        (self.bin_dir / "npm").unlink()
        with self.recorded() as steps:
            result = self.scan(["package.json", "Cargo.toml"])
        self.assertEqual(result["skip_reason"], "npm_tool_not_found")
        self.assertEqual(
            [call.args[0] for call in steps["_verified_groups"].call_args_list], ["cargo"]
        )
        self.assertEqual(steps["_binding_check"].call_count, 1)
        self.assertEqual([r["tool"] for r in self.launches()], ["cargo-audit"])

    def test_a_failed_validation_gives_its_reason_once_and_no_path_work(self):
        self.npm_project("")
        text = SCAN.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("    executable: npm\n", text)
        registry_path = self.base / "registry.yaml"
        registry_path.write_text(
            text.replace("    executable: npm\n", "    executable: bash\n", 1), encoding="utf-8"
        )
        with self.recorded() as steps:
            result = self.scan(["package.json"], registry_path=registry_path)
        self.assertEqual(result["skip_reason"], "npm_executable_not_allowlisted")
        for name, mock_ in steps.items():
            with self.subTest(step=name):
                self.assertEqual(mock_.call_count, 0)
        self.assertEqual(self.launches(), [])


# ---------------------------------------------------------------------------
# AC-6 (NFR1): the argument vector, environment and working directory of what
# run_scan launches (moved from the build_scan_jobs tests).
# ---------------------------------------------------------------------------

class TestWhatRunScanLaunches(RunScanCase):
    def test_npm_runs_with_the_workspace_flag_from_its_own_isolation_directory(self):
        self.npm_project("")
        self.write(".npmrc", "registry=http://evil.example.invalid/\n")
        result = self.scan(["package.json"])
        (record,) = self.launches("npm")
        self.assertEqual(
            record["argv"], [str(self.bin_dir / "npm"), "audit", "--json", "--workspaces=false"]
        )
        self.assertTrue(os.path.isabs(record["argv"][0]))
        self.assertTrue(inside(self.iso_tmp, record["cwd"]))
        self.assertFalse(inside(self.root, record["cwd"]))
        self.assertNotIn(".npmrc", record["files"])
        self.assertEqual(sorted(record["files"]), ["package-lock.json", "package.json"])
        self.assertFalse(result["skipped"], result)
        self.assertNoIsolationDirectoryRemains()

    def test_a_nested_npm_group_keeps_its_own_label_and_isolation_directory(self):
        self.npm_project("services/api")
        self.configure("npm", NPM_VULN, exit_code=1)
        result = self.scan(["services/api/package.json"])
        (record,) = self.launches("npm")
        self.assertTrue(inside(self.iso_tmp, record["cwd"]))
        self.assertEqual([f["file"] for f in result["findings"]], ["services/api/package.json"])

    def test_cargo_runs_with_the_target_flag_and_the_copied_lockfile_from_its_isolation_directory(self):
        self.cargo_project("")
        self.write(".cargo/audit.toml", "[advisories]\nignore = []\n")
        self.scan(["Cargo.toml"])
        (record,) = self.launches("cargo-audit")
        copy_path = os.path.join(record["cwd"], "Cargo.lock")
        self.assertEqual(
            record["argv"],
            [str(self.bin_dir / "cargo-audit"), "audit", "--file", copy_path, "--json"],
        )
        self.assertTrue(os.path.isabs(record["argv"][0]))
        self.assertTrue(inside(self.iso_tmp, record["cwd"]))
        self.assertFalse(inside(self.root, record["cwd"]))
        self.assertEqual(record["files"]["Cargo.lock"], "# Cargo.lock of root\n")
        self.assertEqual(sorted(record["files"]), ["Cargo.lock"])
        self.assertNoIsolationDirectoryRemains()

    def test_go_runs_from_the_group_directory(self):
        self.go_project("svc")
        self.scan(["svc/go.mod"])
        (record,) = self.launches("govulncheck")
        self.assertEqual(record["argv"], [str(self.bin_dir / "govulncheck"), "-json", "./..."])
        self.assertTrue(os.path.isabs(record["argv"][0]))
        self.assertEqual(record["cwd"], str(self.root / "svc"))

    def test_go_at_the_root_runs_from_the_project_root(self):
        self.go_project("")
        self.scan(["go.mod"])
        (record,) = self.launches("govulncheck")
        self.assertEqual(record["cwd"], str(self.root))

    def test_pip_runs_from_the_project_root_whatever_the_target_directory(self):
        self.write("backend/requirements.txt", "django==3.2.0\n")
        self.scan(["backend/requirements.txt"])
        (record,) = self.launches("pip-audit")
        self.assertEqual(
            record["argv"],
            [str(self.bin_dir / "pip-audit"), "-r", "backend/requirements.txt", "--format", "json"],
        )
        self.assertTrue(os.path.isabs(record["argv"][0]))
        self.assertEqual(record["cwd"], str(self.root))

    def test_a_pip_pyproject_target_audits_its_own_directory(self):
        self.write("services/api/pyproject.toml", "[project]\nname = 'api'\n")
        self.scan(["services/api/pyproject.toml"])
        (record,) = self.launches("pip-audit")
        self.assertEqual(
            record["argv"], [str(self.bin_dir / "pip-audit"), "services/api", "--format", "json"]
        )

    def test_every_launched_argv0_is_the_absolute_path_of_the_resolved_executable(self):
        self.npm_project("")
        self.cargo_project("")
        self.go_project("")
        self.write("requirements.txt", "django==3.2.0\n")
        self.scan(["package.json", "Cargo.toml", "go.mod", "requirements.txt"])
        launches = self.launches()
        self.assertEqual(
            [r["tool"] for r in launches], ["npm", "cargo-audit", "pip-audit", "govulncheck"]
        )
        for record in launches:
            with self.subTest(tool=record["tool"]):
                self.assertTrue(os.path.isabs(record["argv"][0]))
                self.assertEqual(record["argv"][0], str(self.bin_dir / record["tool"]))

    def test_the_child_environment_carries_the_pins_and_nothing_inherited_wholesale(self):
        self.npm_project("")
        self.go_project("")
        self.scan(["package.json", "go.mod"])
        npm_env = self.launches("npm")[0]["env"]
        go_env = self.launches("govulncheck")[0]["env"]
        self.assertEqual(npm_env["npm_config_registry"], "https://registry.npmjs.org/")
        self.assertEqual(go_env["GOWORK"], "off")
        self.assertEqual(go_env["GOENV"], "off")
        self.assertEqual(go_env["GOFLAGS"], "-mod=readonly")
        for env in (npm_env, go_env):
            self.assertNotIn("SCA_TEST_SECRET", env)

    def test_a_symlinked_alias_and_the_plain_spelling_launch_one_scanner_in_the_real_directory(self):
        self.go_project("svc")
        (self.root / "alias").symlink_to(self.root / "svc")
        result = self.scan(["alias/go.mod", "svc/go.mod"])
        (record,) = self.launches("govulncheck")
        self.assertEqual(record["cwd"], str(self.root / "svc"))
        self.assertFalse(result["skipped"], result)

    def test_a_symlinked_npm_alias_and_the_plain_spelling_launch_one_scanner(self):
        self.npm_project("svc")
        (self.root / "alias").symlink_to(self.root / "svc")
        result = self.scan(["alias/package.json", "svc/package.json"])
        (record,) = self.launches("npm")
        self.assertEqual(self.project_of(record, "package.json"), "svc")
        self.assertFalse(result["skipped"], result)


# ---------------------------------------------------------------------------
# AC-7: the docstrings and comments describe plan-units, and the lexical
# grouping helper is gone.
# ---------------------------------------------------------------------------

def _docstring(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_docstring(node) or ""
    raise AssertionError(f"no function {name}")


def _comment_block_above(lines, marker):
    """The block of consecutive `#` comment lines that contains the first
    line starting with `marker` (a comment line itself)."""
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    first = index
    while first > 0 and lines[first - 1].startswith("#"):
        first -= 1
    last = index
    while last + 1 < len(lines) and lines[last + 1].startswith("#"):
        last += 1
    return "\n".join(lines[first:last + 1])


class TestTheDocumentationDescribesPlanUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.lines = cls.source.splitlines()
        cls.tree = ast.parse(cls.source)

    def test_the_build_scan_jobs_docstring_no_longer_says_run_scan_does_not_use_it(self):
        doc = _docstring(self.tree, "build_scan_jobs")
        self.assertNotIn("run_scan does not use this function", doc)
        self.assertNotIn("does not use this function", doc)

    def test_the_build_scan_jobs_docstring_describes_plans_and_real_path_grouping(self):
        doc = _docstring(self.tree, "build_scan_jobs")
        self.assertIn("plan", doc)
        self.assertRegex(doc, r"(?i)real path")
        for stale in ("LEXICAL", "prepared_inputs", "Grouping is LEXICAL"):
            self.assertNotIn(stale, doc)

    def test_no_reference_to_the_lexical_grouping_helper_remains(self):
        self.assertNotIn("_lexical_project_directory", self.source)
        self.assertFalse(
            [n for n in ast.walk(self.tree)
             if isinstance(n, ast.FunctionDef) and n.name == "_lexical_project_directory"]
        )

    def test_manifest_file_for_names_build_scan_jobs_as_its_caller(self):
        doc = " ".join(_docstring(self.tree, "manifest_file_for").split())
        self.assertIn("`build_scan_jobs` calls this", doc)
        self.assertNotIn("`run_scan` calls this", doc)

    def test_the_scan_job_construction_comment_says_no_plan_where_it_said_no_job(self):
        block = _comment_block_above(self.lines, "# Scan job construction")
        self.assertIn("build_scan_jobs", block)
        self.assertIn("no plan", block)
        self.assertNotIn("no job", block)

    def test_the_run_side_docstrings_keep_the_pinned_phrases_and_name_the_plan(self):
        bound = _docstring(self.tree, "_scan_bound_group")
        run = _docstring(self.tree, "run_scan")
        self.assertIn("ScanPlan", bound)
        self.assertIn("isolation directory", bound)
        self.assertIn("_isolation_failed", bound)
        self.assertIn("build_scan_jobs", run)
        for token in ("npm_isolation_failed", "cargo_isolation_failed"):
            self.assertIn(token, run)


# ---------------------------------------------------------------------------
# AC-8 (NFR3): this module and the modules task0004 rewrote import the standard
# library only.
# ---------------------------------------------------------------------------

def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


class TestTheModulesImportOnlyTheStandardLibrary(unittest.TestCase):
    def test_imports_are_standard_library_only(self):
        for name in SIBLING_MODULES:
            with self.subTest(module=name):
                modules = _imported_modules(TESTS_DIR / name)
                self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), [])
                self.assertFalse({m for m in modules if m.startswith("test_")})


if __name__ == "__main__":
    unittest.main()
