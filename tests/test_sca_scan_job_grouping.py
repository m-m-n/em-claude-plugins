"""Tests for sca-per-project-scan-binding task0001 (per-group scan job
construction and workspace-escape pins) in `scan-dependencies.py`, with the
`build_scan_jobs` checks rewritten as plan checks by sca-file-tasks-robustness
task0004.

Covers task0001 Acceptance Criteria
(feature-docs/sca-per-project-scan-binding/tasks/task0001.md):

- AC-1: with the real registry, the npm job's argument vector carries
  `--workspaces=false` as its third registry argument; cargo, go and pip
  vectors are unchanged.
- AC-2: the go job's child environment pins GOWORK=off, GOFLAGS=-mod=readonly,
  GOENV=off and GOPROXY at its existing value, whatever the caller's
  environment carries; npm / cargo / pip pins equal their previous values.
- AC-3: `build_scan_jobs` returns one plan per (ecosystem, project directory)
  group, groups in ascending plain-string order of the directory, ecosystems
  in registry order.
- AC-4: equivalent spellings of one directory fall into one group; the plan's
  target follows the Target convention (directory + "/" + basename of the
  file `manifest_file_for` selected; the bare basename at the root).
- AC-5: npm / cargo / go paths that are absolute, escape through `..` or
  contain NUL join no group and add `<ecosystem>_project_unbindable` exactly
  once per ecosystem; pip paths are never filtered that way.
- AC-6: an ecosystem that fails validation or whose executable is absent
  contributes its existing reason exactly once, no plan and no unbindable
  reason, however many groups it has.
- AC-7: `build_scan_job` / `build_scan_jobs` open no file and launch no
  process (patched to fail).
- AC-8: this module imports the standard library only.

sca-file-tasks-robustness task0004 (FR6): `build_scan_jobs(registry,
changed_files, project_root)` returns `(plans, skip_reasons)`. A plan is one
group's unit that has not been launched, with exactly six fields (ecosystem,
directory, real_root, files, target, executable). Grouping is by REAL path
(`_verified_groups`): a symlinked alias of a directory and a `..` spelling
that stays inside the root fall into the plan of the plain spelling, and a
path that escapes the root through a symlink yields no plan. The grouping,
order, reason and purity tests below therefore assert plans. The argument
vector, environment and working directory of a job are asserted on
`build_scan_job` here and on `run_scan` in
`tests/test_sca_run_scan_plan_units.py`.

sca-scanner-project-config-isolation task0001: an npm / cargo job is built
from the prepared isolation paths of its group (`prepared_inputs`), so every
npm / cargo `build_scan_job` call below passes one -- a nominal value,
because construction is pure and never touches those paths. cargo's argument
vector carries the registry-declared `--file <copy>` right after `audit`;
npm's, go's and pip's are unchanged.

Test Notes: the script is loaded by file path (its name contains a hyphen),
following the sibling `tests/test_sca_scan_*.py` modules. No real scanner is
ever executed: executables are stubs on a temporary PATH, or nothing at all.
Lexical-only cases keep a project root that does not exist; real-path cases
build a real project tree with symlinks in a temporary directory.
"""

import ast
import contextlib
import copy
import dataclasses
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"

GO_PROXY = "https://proxy.golang.org,direct"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_dependencies_job_grouping", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_module()


def _registry():
    return SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)


def _nominal_prepared(target):
    """Prepared isolation paths for the group whose job target is `target`:
    one directory per target, and a copy path for every role."""
    directory = "/iso/" + target.replace("/", "~")
    return SCAN.PreparedInputs(
        directory=directory,
        files={
            "manifest": directory + "/package.json",
            "anchor": directory + "/package-lock.json",
            "lockfile": directory + "/Cargo.lock",
        },
    )


def _entries():
    return {e["ecosystem"]: e for e in _registry()["ecosystems"]}


def _install_stubs(bin_dir, executables):
    bin_dir.mkdir()
    for name in executables:
        stub = bin_dir / name
        stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
        stub.chmod(0o755)


@contextlib.contextmanager
def scanner_path(*executables):
    """A temporary PATH holding an executable stub for each given name (or
    nothing at all when none is given), in `<root>.parent / "bin"`. Yields a
    project-root path that is never created: build_scan_jobs must not need it
    to exist."""
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        _install_stubs(bin_dir, executables)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            yield Path(tmp) / "proj"


@contextlib.contextmanager
def project_tree(*executables):
    """Like `scanner_path`, but the project root exists and is a real
    directory; a sibling `outside` directory (beside the root, so outside it)
    exists too. Yields `(root, outside)` as resolved paths."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        _install_stubs(base / "bin", executables)
        root = base / "proj"
        outside = base / "outside"
        root.mkdir()
        outside.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(base / "bin")}):
            yield root, outside


ALL_STUBS = ("npm", "cargo-audit", "pip-audit", "govulncheck")

PLAN_FIELDS = ["ecosystem", "directory", "real_root", "files", "target", "executable"]


def _name(plan):
    return plan.ecosystem["ecosystem"]


def _targets(plans, ecosystem=None):
    return [p.target for p in plans if ecosystem is None or _name(p) == ecosystem]


def _directories(plans, ecosystem=None):
    return [p.directory for p in plans if ecosystem is None or _name(p) == ecosystem]


def _build(changed, *stubs, registry=None):
    with scanner_path(*stubs) as root:
        return SCAN.build_scan_jobs(registry or _registry(), changed, root)


# ---------------------------------------------------------------------------
# AC-1 (TM-3): argument vectors built from the real registry.
# ---------------------------------------------------------------------------

class TestArgumentVectorsFromTheRealRegistry(unittest.TestCase):
    PREPARED = "/tmp/prepared-requirements.txt"

    @classmethod
    def setUpClass(cls):
        cls.entries = _entries()

    def test_npm_registry_args_carry_the_workspace_flag_as_third_element(self):
        self.assertEqual(self.entries["npm"]["args"], ["audit", "--json", "--workspaces=false"])

    def test_npm_job_argv_is_exactly_executable_audit_json_workspaces_false(self):
        job = SCAN.build_scan_job(
            self.entries["npm"], "package.json", "/proj", "/x/npm",
            prepared_inputs=_nominal_prepared("package.json"),
        )
        self.assertEqual(job["argv"], ["/x/npm", "audit", "--json", "--workspaces=false"])

    def test_npm_entry_still_passes_validation(self):
        self.assertIsNone(SCAN.validate_ecosystem_entry(self.entries["npm"]))

    def test_cargo_argv_carries_the_declared_target_flag_and_the_copy_right_after_audit(self):
        prepared = _nominal_prepared("Cargo.toml")
        job = SCAN.build_scan_job(
            self.entries["cargo"], "Cargo.toml", "/proj", "/x/cargo-audit", prepared_inputs=prepared
        )
        self.assertEqual(
            job["argv"],
            ["/x/cargo-audit", "audit", "--file", prepared.files["lockfile"], "--json"],
        )

    def test_go_argv_is_unchanged(self):
        job = SCAN.build_scan_job(self.entries["go"], "go.mod", "/proj", "/x/govulncheck")
        self.assertEqual(job["argv"], ["/x/govulncheck", "-json", "./..."])

    def test_pip_vectors_are_unchanged(self):
        pip = self.entries["pip"]
        requirements = SCAN.build_scan_job(pip, "requirements.txt", "/proj", "/x/pip-audit")
        pyproject = SCAN.build_scan_job(pip, "pyproject.toml", "/proj", "/x/pip-audit")
        lockfile = SCAN.build_scan_job(
            pip, "poetry.lock", "/proj", "/x/pip-audit", prepared_file=self.PREPARED
        )
        self.assertEqual(requirements["argv"], ["/x/pip-audit", "-r", "requirements.txt", "--format", "json"])
        self.assertEqual(pyproject["argv"], ["/x/pip-audit", ".", "--format", "json"])
        self.assertEqual(
            lockfile["argv"],
            ["/x/pip-audit", "-r", self.PREPARED, "--no-deps", "--disable-pip", "--format", "json"],
        )

    def test_plans_carry_the_absolute_executable_the_job_argv0_is_built_from(self):
        # The argument vectors of the jobs run_scan builds from these plans are
        # asserted on run_scan in tests/test_sca_run_scan_plan_units.py.
        with scanner_path("npm", "cargo-audit", "govulncheck") as root:
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["package.json", "Cargo.toml", "go.mod"], root
            )
            bin_dir = root.parent / "bin"
        self.assertEqual(reasons, [])
        self.assertEqual(
            {_name(p): p.executable for p in plans},
            {
                "npm": str(bin_dir / "npm"),
                "cargo": str(bin_dir / "cargo-audit"),
                "go": str(bin_dir / "govulncheck"),
            },
        )
        for plan in plans:
            self.assertTrue(os.path.isabs(plan.executable))


# ---------------------------------------------------------------------------
# AC-2 (TM-3, TM-4): child-environment pins.
# ---------------------------------------------------------------------------

class TestChildEnvironmentPins(unittest.TestCase):
    HOSTILE = {
        "PATH": "/usr/bin",
        "HOME": "/home/x",
        "GOWORK": "/elsewhere/go.work",
        "GOFLAGS": "-mod=mod",
        "GOENV": "/elsewhere/goenv",
        "GOPROXY": "http://evil.example.com",
    }

    @classmethod
    def setUpClass(cls):
        cls.entries = _entries()

    def test_go_job_env_pins_workspace_off_readonly_modules_goenv_off_and_proxy(self):
        job = SCAN.build_scan_job(
            self.entries["go"], "go.mod", "/proj", "/x/govulncheck", environ=self.HOSTILE
        )
        env = job["env"]
        self.assertEqual(env["GOWORK"], "off")
        self.assertEqual(env["GOFLAGS"], "-mod=readonly")
        self.assertEqual(env["GOENV"], "off")
        self.assertEqual(env["GOPROXY"], GO_PROXY)

    def test_go_job_env_is_pinned_when_the_caller_sets_none_of_them(self):
        job = SCAN.build_scan_job(
            self.entries["go"], "go.mod", "/proj", "/x/govulncheck", environ={"PATH": "/usr/bin"}
        )
        self.assertEqual(
            job["env"],
            {
                "PATH": "/usr/bin",
                "GOENV": "off",
                "GOWORK": "off",
                "GOFLAGS": "-mod=readonly",
                "GOPROXY": GO_PROXY,
            },
        )

    def test_go_job_env_does_not_inherit_caller_values_for_pinned_names(self):
        env = SCAN.build_child_env(self.entries["go"], environ=self.HOSTILE)
        for value in ("/elsewhere/go.work", "-mod=mod", "/elsewhere/goenv", "http://evil.example.com"):
            self.assertNotIn(value, env.values())

    def test_go_pin_table_holds_exactly_the_four_pins(self):
        self.assertEqual(
            SCAN.ECOSYSTEM_ENV_PINS["go"],
            {
                "GOENV": "off",
                "GOWORK": "off",
                "GOFLAGS": "-mod=readonly",
                "GOPROXY": GO_PROXY,
            },
        )

    def test_npm_cargo_and_pip_pins_equal_their_previous_values(self):
        self.assertEqual(
            SCAN.ECOSYSTEM_ENV_PINS["npm"],
            {
                "npm_config_registry": "https://registry.npmjs.org/",
                "npm_config_userconfig": os.devnull,
            },
        )
        self.assertEqual(SCAN.ECOSYSTEM_ENV_PINS["cargo"], {})
        self.assertEqual(
            SCAN.ECOSYSTEM_ENV_PINS["pip"],
            {"PIP_CONFIG_FILE": os.devnull, "PIP_INDEX_URL": "https://pypi.org/simple/"},
        )

    def test_non_go_job_envs_gain_no_go_variables(self):
        for name, manifest in (("npm", "package.json"), ("cargo", "Cargo.toml"), ("pip", "requirements.txt")):
            with self.subTest(ecosystem=name):
                job = SCAN.build_scan_job(
                    self.entries[name], manifest, "/proj", f"/x/{name}", environ=self.HOSTILE,
                    prepared_inputs=_nominal_prepared(manifest),
                )
                self.assertFalse([k for k in job["env"] if k.startswith("GO")])




# ---------------------------------------------------------------------------
# sca-file-tasks-robustness AC-1 (FR6): the plan record.
# ---------------------------------------------------------------------------

class TestThePlanRecord(unittest.TestCase):
    def test_a_plan_carries_exactly_the_six_named_fields(self):
        plans, _ = _build(["package.json"], "npm")
        (plan,) = plans
        self.assertEqual([f.name for f in dataclasses.fields(plan)], PLAN_FIELDS)

    def test_a_plan_is_read_only(self):
        plans, _ = _build(["package.json"], "npm")
        (plan,) = plans
        for field in PLAN_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(AttributeError):
                    setattr(plan, field, "changed")

    def test_the_fields_of_a_nested_npm_plan(self):
        changed = ["svc/api/package.json", "README.md", "svc/api/./package-lock.json"]
        with scanner_path("npm") as root:
            plans, reasons = SCAN.build_scan_jobs(_registry(), changed, root)
            expected_executable = str(root.parent / "bin" / "npm")
        self.assertEqual(reasons, [])
        (plan,) = plans
        self.assertEqual(plan.ecosystem, _entries()["npm"])
        self.assertEqual(plan.directory, "svc/api")
        self.assertEqual(plan.real_root, os.path.realpath(str(root)))
        self.assertEqual(list(plan.files), ["svc/api/package.json", "svc/api/./package-lock.json"])
        self.assertEqual(plan.target, "svc/api/package.json")
        self.assertEqual(plan.executable, expected_executable)

    def test_the_fields_of_a_root_plan_use_the_empty_directory_and_the_bare_basename(self):
        plans, _ = _build(["./Cargo.lock", "Cargo.toml"], "cargo-audit")
        (plan,) = plans
        self.assertEqual(plan.directory, "")
        self.assertEqual(plan.target, "Cargo.toml")
        self.assertEqual(list(plan.files), ["./Cargo.lock", "Cargo.toml"])

    def test_a_pip_plan_targets_the_raw_selected_file(self):
        plans, _ = _build(["x/./requirements.txt", "x/pyproject.toml"], "pip-audit")
        (plan,) = plans
        self.assertEqual(plan.directory, "x")
        self.assertEqual(plan.target, "x/./requirements.txt")
        self.assertEqual(list(plan.files), ["x/./requirements.txt", "x/pyproject.toml"])

    def test_a_pip_plan_prefers_a_lockfile_as_target(self):
        plans, _ = _build(["a/pyproject.toml", "a/poetry.lock"], "pip-audit")
        (plan,) = plans
        self.assertEqual(plan.target, "a/poetry.lock")

    def test_the_target_follows_manifest_file_for_over_the_group_files(self):
        changed = ["a/package-lock.json", "a/package.json", "b/package-lock.json"]
        with scanner_path("npm") as root:
            plans, _ = SCAN.build_scan_jobs(_registry(), changed, root)
        npm = _entries()["npm"]
        for plan in plans:
            with self.subTest(directory=plan.directory):
                selected = SCAN.manifest_file_for(npm, list(plan.files))
                self.assertEqual(plan.target, f"{plan.directory}/{os.path.basename(selected)}")


# ---------------------------------------------------------------------------
# AC-3, AC-4: one plan per (ecosystem, project directory) group.
# ---------------------------------------------------------------------------

class TestPlanPerProjectDirectoryGroup(unittest.TestCase):
    def test_two_npm_directories_yield_two_plans_in_ascending_directory_order(self):
        plans, reasons = _build(
            ["services/web/package.json", "services/api/package.json"], "npm"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(
            _targets(plans), ["services/api/package.json", "services/web/package.json"]
        )
        self.assertEqual(_directories(plans), ["services/api", "services/web"])
        self.assertEqual({_name(p) for p in plans}, {"npm"})

    def test_root_group_comes_first(self):
        plans, _ = _build(["a/package.json", "package.json"], "npm")
        self.assertEqual(_targets(plans), ["package.json", "a/package.json"])
        self.assertEqual(_directories(plans), ["", "a"])

    def test_order_is_plain_string_order_of_the_directory(self):
        # Plain-string order puts "a-b" (0x2d) before "a/b" (0x2f); a
        # segment-wise order would put "a/b" first.
        plans, _ = _build(["a/b/package.json", "a-b/package.json", "a/package.json"], "npm")
        self.assertEqual(
            _targets(plans), ["a/package.json", "a-b/package.json", "a/b/package.json"]
        )

    def test_order_does_not_depend_on_input_order(self):
        changed = ["z/package.json", "m/package.json", "a/package.json", "package.json"]
        forward, _ = _build(changed, "npm")
        backward, _ = _build(list(reversed(changed)), "npm")
        self.assertEqual(_targets(forward), _targets(backward))
        self.assertEqual(
            _targets(forward), ["package.json", "a/package.json", "m/package.json", "z/package.json"]
        )

    def test_every_npm_plan_precedes_every_cargo_plan_whatever_the_input_order(self):
        changed = ["svc/Cargo.toml", "b/package.json", "Cargo.toml", "a/package.json"]
        plans, reasons = _build(changed, "npm", "cargo-audit")
        self.assertEqual(reasons, [])
        self.assertEqual([_name(p) for p in plans], ["npm", "npm", "cargo", "cargo"])
        self.assertEqual(_targets(plans, "npm"), ["a/package.json", "b/package.json"])
        self.assertEqual(_targets(plans, "cargo"), ["Cargo.toml", "svc/Cargo.toml"])

    def test_ecosystems_follow_registry_order_across_all_four(self):
        changed = ["go.mod", "requirements.txt", "Cargo.toml", "package.json"]
        plans, reasons = _build(changed, *ALL_STUBS)
        self.assertEqual(reasons, [])
        self.assertEqual([_name(p) for p in plans], ["npm", "cargo", "pip", "go"])

    def test_go_and_cargo_group_per_directory_too(self):
        plans, _ = _build(
            ["svc/b/go.mod", "svc/a/go.mod", "x/Cargo.toml", "y/Cargo.toml"], "cargo-audit", "govulncheck"
        )
        self.assertEqual(_targets(plans, "cargo"), ["x/Cargo.toml", "y/Cargo.toml"])
        self.assertEqual(_targets(plans, "go"), ["svc/a/go.mod", "svc/b/go.mod"])

    def test_a_manifest_and_its_lockfile_in_one_directory_yield_one_plan(self):
        plans, _ = _build(["a/package-lock.json", "a/package.json"], "npm")
        self.assertEqual(_targets(plans), ["a/package.json"])
        (plan,) = plans
        self.assertEqual(list(plan.files), ["a/package-lock.json", "a/package.json"])

    def test_a_lockfile_only_directory_is_still_a_group(self):
        plans, _ = _build(["a/package-lock.json", "b/package.json"], "npm")
        self.assertEqual(_targets(plans), ["a/package-lock.json", "b/package.json"])

    def test_unrelated_changed_files_form_no_group_and_join_no_plan(self):
        plans, reasons = _build(["README.md", "src/app.js", "a/package.json"], "npm")
        self.assertEqual(reasons, [])
        self.assertEqual(_targets(plans), ["a/package.json"])
        self.assertEqual(list(plans[0].files), ["a/package.json"])

    def test_pip_groups_by_directory_and_keeps_the_raw_selected_file_as_target(self):
        plans, reasons = _build(
            ["y/pyproject.toml", "x/./requirements.txt", "x/pyproject.toml"], "pip-audit"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(_targets(plans), ["x/./requirements.txt", "y/pyproject.toml"])

    def test_pip_aliases_of_one_directory_form_one_plan(self):
        plans, _ = _build(["a/requirements.txt", "a/./pyproject.toml", "./a//requirements.txt"], "pip-audit")
        self.assertEqual(_targets(plans), ["a/requirements.txt"])
        self.assertEqual(
            list(plans[0].files), ["a/requirements.txt", "a/./pyproject.toml", "./a//requirements.txt"]
        )


class TestAliasSpellingsJoinOnePlan(unittest.TestCase):
    def test_manifest_lockfile_alias_and_repeat_yield_one_plan_with_the_manifest(self):
        plans, reasons = _build(
            ["a/package.json", "a/./package-lock.json", "a/package.json"], "npm"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(_targets(plans), ["a/package.json"])
        self.assertEqual(
            list(plans[0].files), ["a/package.json", "a/./package-lock.json", "a/package.json"]
        )

    def test_lockfile_only_change_with_a_dot_segment_keeps_the_lockfile_basename(self):
        plans, _ = _build(["a/./go.sum"], "govulncheck")
        self.assertEqual([_name(p) for p in plans], ["go"])
        self.assertEqual(_targets(plans), ["a/go.sum"])

    def test_root_level_change_keeps_the_bare_basename(self):
        plans, _ = _build(["package.json"], "npm")
        self.assertEqual(_targets(plans), ["package.json"])

    def test_root_aliases_keep_the_bare_basename(self):
        for spelling in ("./package.json", ".//package.json", "a/../package.json", "a/b/../../package.json"):
            with self.subTest(spelling=spelling):
                plans, reasons = _build([spelling], "npm")
                self.assertEqual(reasons, [])
                self.assertEqual(_targets(plans), ["package.json"])
                self.assertEqual(_directories(plans), [""])

    def test_dot_dot_segments_that_cancel_inside_the_tree_are_normalized(self):
        for spelling in ("b/../a/package.json", "./a//package.json", "a/./b/../package.json", "x/../a/./package.json"):
            with self.subTest(spelling=spelling):
                plans, reasons = _build([spelling, "a/package.json"], "npm")
                self.assertEqual(reasons, [])
                self.assertEqual(_targets(plans), ["a/package.json"])

    def test_target_is_normalized_even_when_the_selected_input_was_spelled_oddly(self):
        plans, _ = _build(["./a//./package.json"], "npm")
        self.assertEqual(_targets(plans), ["a/package.json"])

    def test_nested_lockfile_alias_for_cargo(self):
        plans, _ = _build(["x//y/./Cargo.lock"], "cargo-audit")
        self.assertEqual(_targets(plans), ["x/y/Cargo.lock"])

    def test_manifest_first_selection_holds_whatever_the_input_order_inside_a_group(self):
        plans, _ = _build(["a/./package-lock.json", "a/package.json"], "npm")
        self.assertEqual(_targets(plans), ["a/package.json"])

    def test_distinct_directories_are_not_merged(self):
        plans, _ = _build(["a/package.json", "a/b/package.json", "ab/package.json"], "npm")
        self.assertEqual(
            _targets(plans), ["a/package.json", "a/b/package.json", "ab/package.json"]
        )


# ---------------------------------------------------------------------------
# AC-2 (FR6): grouping is by REAL path. A symlinked alias of a directory and a
# `..` spelling that stays inside the root fall into the plan of the plain
# spelling; a path that escapes the root through a symlink yields no plan.
# ---------------------------------------------------------------------------

def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")


class TestRealPathGrouping(unittest.TestCase):
    def test_a_symlinked_alias_of_a_directory_joins_the_plan_of_the_plain_spelling(self):
        with project_tree("npm") as (root, _outside):
            _touch(root / "real" / "package.json")
            (root / "alias").symlink_to(root / "real")
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["alias/package.json", "real/package.json"], root
            )
        self.assertEqual(reasons, [])
        (plan,) = plans
        self.assertEqual(plan.directory, "real")
        self.assertEqual(plan.target, "real/package.json")
        self.assertEqual(list(plan.files), ["alias/package.json", "real/package.json"])

    def test_a_relative_symlink_into_a_nested_directory_resolves_to_that_directory(self):
        with project_tree("cargo-audit") as (root, _outside):
            _touch(root / "svc" / "api" / "Cargo.toml")
            (root / "link").symlink_to("svc/api")
            plans, reasons = SCAN.build_scan_jobs(_registry(), ["link/Cargo.toml"], root)
        self.assertEqual(reasons, [])
        self.assertEqual(_directories(plans), ["svc/api"])
        self.assertEqual(_targets(plans), ["svc/api/Cargo.toml"])

    def test_a_dot_dot_spelling_that_stays_inside_the_root_joins_the_plain_spelling(self):
        with project_tree("govulncheck") as (root, _outside):
            _touch(root / "a" / "go.mod")
            _touch(root / "b" / "go.mod")
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["a/../b/go.mod", "b/go.mod", "a/go.mod"], root
            )
        self.assertEqual(reasons, [])
        self.assertEqual(_directories(plans), ["a", "b"])
        by_directory = {p.directory: list(p.files) for p in plans}
        self.assertEqual(by_directory["b"], ["a/../b/go.mod", "b/go.mod"])

    def test_a_group_key_is_the_real_directory_relative_to_the_real_root(self):
        with project_tree("npm") as (root, _outside):
            _touch(root / "real" / "package.json")
            (root / "alias").symlink_to(root / "real")
            plans, _ = SCAN.build_scan_jobs(_registry(), ["alias/package.json"], root)
        (plan,) = plans
        self.assertEqual(plan.directory, "real")
        self.assertEqual(plan.real_root, os.path.realpath(str(root)))

    def test_a_directory_symlink_that_escapes_the_root_yields_no_plan_and_one_reason(self):
        for name, manifest, stub in (
            ("npm", "package.json", "npm"),
            ("cargo", "Cargo.toml", "cargo-audit"),
            ("go", "go.mod", "govulncheck"),
        ):
            with self.subTest(ecosystem=name):
                with project_tree(stub) as (root, outside):
                    _touch(outside / "deep" / manifest)
                    _touch(root / "ok" / manifest)
                    (root / "esc").symlink_to(outside)
                    plans, reasons = SCAN.build_scan_jobs(
                        _registry(),
                        [f"esc/deep/{manifest}", f"esc/{manifest}", f"ok/{manifest}"],
                        root,
                    )
                self.assertEqual(reasons, [f"{name}_project_unbindable"])
                self.assertEqual(_targets(plans), [f"ok/{manifest}"])

    def test_a_file_symlink_that_leaves_the_root_yields_no_plan_for_npm_cargo_and_go(self):
        for name, manifest, stub in (
            ("npm", "package.json", "npm"),
            ("cargo", "Cargo.toml", "cargo-audit"),
            ("go", "go.mod", "govulncheck"),
        ):
            with self.subTest(ecosystem=name):
                with project_tree(stub) as (root, outside):
                    _touch(outside / manifest)
                    (root / "a").mkdir()
                    (root / "a" / manifest).symlink_to(outside / manifest)
                    plans, reasons = SCAN.build_scan_jobs(_registry(), [f"a/{manifest}"], root)
                self.assertEqual(plans, [])
                self.assertEqual(reasons, [f"{name}_project_unbindable"])

    def test_a_dot_dot_spelling_through_an_escaping_symlink_yields_no_plan(self):
        with project_tree("npm") as (root, outside):
            (outside / "deep").mkdir()
            _touch(root / "x" / "package.json")
            (root / "link").symlink_to(outside / "deep")
            # `link/..` is `outside`, not the root: the file lands outside it.
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["link/../x/package.json", "x/package.json"], root
            )
        self.assertEqual(reasons, ["npm_project_unbindable"])
        self.assertEqual(_targets(plans), ["x/package.json"])
        self.assertEqual(list(plans[0].files), ["x/package.json"])

    def test_an_absolute_path_that_points_inside_the_root_is_still_unbindable(self):
        with project_tree("npm") as (root, _outside):
            _touch(root / "a" / "package.json")
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), [str(root / "a" / "package.json")], root
            )
        self.assertEqual(plans, [])
        self.assertEqual(reasons, ["npm_project_unbindable"])

    def test_a_symlinked_project_root_is_resolved_once_into_every_plan(self):
        with project_tree("npm", "cargo-audit") as (root, outside):
            link = outside / "root-link"
            link.symlink_to(root)
            _touch(root / "a" / "package.json")
            _touch(root / "b" / "Cargo.toml")
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["a/package.json", "b/Cargo.toml"], link
            )
        self.assertEqual(reasons, [])
        self.assertEqual({p.real_root for p in plans}, {os.path.realpath(str(root))})
        self.assertEqual(_targets(plans), ["a/package.json", "b/Cargo.toml"])

    def test_pip_paths_are_never_rejected_and_a_verifiable_one_is_keyed_by_its_real_directory(self):
        with project_tree("pip-audit") as (root, outside):
            _touch(root / "real" / "requirements.txt")
            (root / "alias").symlink_to(root / "real")
            (root / "esc").symlink_to(outside)
            plans, reasons = SCAN.build_scan_jobs(
                _registry(),
                ["alias/requirements.txt", "real/pyproject.toml", "esc/requirements.txt"],
                root,
            )
        self.assertEqual(reasons, [])
        by_directory = {p.directory: p for p in plans}
        self.assertEqual(sorted(by_directory), ["esc", "real"])
        self.assertEqual(list(by_directory["real"].files), ["alias/requirements.txt", "real/pyproject.toml"])
        self.assertEqual(by_directory["real"].target, "alias/requirements.txt")

    def test_an_unverifiable_pip_path_keeps_its_raw_directory_key_apart_from_verified_keys(self):
        with project_tree("pip-audit") as (root, _outside):
            _touch(root / "a" / "requirements.txt")
            plans, reasons = SCAN.build_scan_jobs(
                _registry(), ["/a/requirements.txt", "a/requirements.txt"], root
            )
        self.assertEqual(reasons, [])
        self.assertEqual(sorted(_directories(plans)), ["/a", "a"])
        by_directory = {p.directory: p for p in plans}
        self.assertEqual(by_directory["/a"].target, "/a/requirements.txt")
        self.assertEqual(by_directory["a"].target, "a/requirements.txt")


# ---------------------------------------------------------------------------
# AC-5: unbindable npm / cargo / go paths; pip is never filtered.
# ---------------------------------------------------------------------------

# (ecosystem, manifest basename, lockfile basename, stub executable)
FILTERED = (
    ("npm", "package.json", "package-lock.json", "npm"),
    ("cargo", "Cargo.toml", "Cargo.lock", "cargo-audit"),
    ("go", "go.mod", "go.sum", "govulncheck"),
)


def _unbindable_spellings(basename):
    return {
        "absolute": f"/abs/dir/{basename}",
        "absolute-at-root": f"/{basename}",
        "escaping": f"../up/{basename}",
        "escaping-bare": f"../{basename}",
        "escaping-after-cancel": f"a/../../up/{basename}",
        "nul": f"bad\x00dir/{basename}",
    }


class TestUnbindablePaths(unittest.TestCase):
    def test_each_unbindable_kind_is_dropped_with_one_reason_and_a_valid_group_still_yields_its_plan(self):
        for name, manifest, lockfile, stub in FILTERED:
            for kind, bad in _unbindable_spellings(manifest).items():
                with self.subTest(ecosystem=name, kind=kind):
                    plans, reasons = _build([bad, f"ok/{manifest}"], stub)
                    self.assertEqual(reasons, [f"{name}_project_unbindable"])
                    self.assertEqual(_targets(plans), [f"ok/{manifest}"])
                    self.assertEqual(list(plans[0].files), [f"ok/{manifest}"])

    def test_unbindable_lockfile_paths_are_dropped_too(self):
        for name, _manifest, lockfile, stub in FILTERED:
            for kind, bad in _unbindable_spellings(lockfile).items():
                with self.subTest(ecosystem=name, kind=kind):
                    plans, reasons = _build([bad], stub)
                    self.assertEqual(plans, [])
                    self.assertEqual(reasons, [f"{name}_project_unbindable"])

    def test_the_reason_appears_exactly_once_however_many_paths_were_dropped(self):
        for name, manifest, lockfile, stub in FILTERED:
            with self.subTest(ecosystem=name):
                bad = [
                    f"/abs/{manifest}",
                    f"/other/{lockfile}",
                    f"../up/{manifest}",
                    f"../../up/{lockfile}",
                    f"bad\x00dir/{manifest}",
                    f"bad2\x00dir/{lockfile}",
                ]
                plans, reasons = _build(bad + [f"ok/{manifest}", f"ok2/{manifest}"], stub)
                self.assertEqual(reasons, [f"{name}_project_unbindable"])
                self.assertEqual(_targets(plans), [f"ok/{manifest}", f"ok2/{manifest}"])

    def test_only_unbindable_paths_yield_no_plan_and_the_reason(self):
        for name, manifest, _lockfile, stub in FILTERED:
            with self.subTest(ecosystem=name):
                plans, reasons = _build([f"/abs/{manifest}", f"../x/{manifest}"], stub)
                self.assertEqual(plans, [])
                self.assertEqual(reasons, [f"{name}_project_unbindable"])

    def test_reasons_follow_registry_order(self):
        changed = []
        for _name_, manifest, _lockfile, _stub in reversed(FILTERED):
            changed.append(f"/abs/{manifest}")
        _plans, reasons = _build(changed, "npm", "cargo-audit", "govulncheck")
        self.assertEqual(reasons, ["npm_project_unbindable", "cargo_project_unbindable", "go_project_unbindable"])

    def test_a_path_that_stays_inside_after_cancelling_is_not_unbindable(self):
        for name, manifest, _lockfile, stub in FILTERED:
            with self.subTest(ecosystem=name):
                plans, reasons = _build([f"a/b/../../{manifest}"], stub)
                self.assertEqual(reasons, [])
                self.assertEqual(_targets(plans), [manifest])

    def test_names_that_merely_start_with_two_dots_are_not_escaping(self):
        plans, reasons = _build(["..hidden/package.json", "a/..b/package.json"], "npm")
        self.assertEqual(reasons, [])
        self.assertEqual(_targets(plans), ["..hidden/package.json", "a/..b/package.json"])

    def test_the_reason_token_carries_no_path_derived_text(self):
        _plans, reasons = _build(["/secret/location/package.json"], "npm")
        self.assertEqual(reasons, ["npm_project_unbindable"])
        for reason in reasons:
            self.assertNotIn("secret", reason)
            self.assertNotIn("/", reason)

    def test_pip_paths_of_the_same_three_kinds_are_not_filtered_and_add_no_reason(self):
        raw = [
            "/abs/dir/requirements.txt",
            "../up/requirements.txt",
            "bad\x00dir/requirements.txt",
            "ok/requirements.txt",
        ]
        plans, reasons = _build(raw, "pip-audit")
        self.assertEqual(reasons, [])
        self.assertEqual(sorted(_targets(plans)), sorted(raw))

    def test_an_unverifiable_pip_path_keeps_its_raw_directory_part_as_the_plan_directory(self):
        raw = ["/abs/dir/requirements.txt", "../up/requirements.txt", "bad\x00dir/requirements.txt"]
        plans, _ = _build(raw + ["ok/requirements.txt"], "pip-audit")
        self.assertEqual(
            sorted(_directories(plans)), sorted(["/abs/dir", "../up", "bad\x00dir", "ok"])
        )

    def test_pip_pyproject_paths_of_the_same_kinds_are_not_filtered_either(self):
        raw = ["/abs/pyproject.toml", "../up/pyproject.toml", "bad\x00dir/pyproject.toml"]
        plans, reasons = _build(raw, "pip-audit")
        self.assertEqual(reasons, [])
        self.assertEqual(sorted(_targets(plans)), sorted(raw))

    def test_pip_directory_spellings_that_differ_only_by_an_absolute_prefix_stay_apart(self):
        plans, _ = _build(["/a/requirements.txt", "a/requirements.txt"], "pip-audit")
        self.assertEqual(sorted(_targets(plans)), ["/a/requirements.txt", "a/requirements.txt"])


# ---------------------------------------------------------------------------
# AC-6 / AC-3 (FR6, TM-5): ecosystem-level reasons come once, with no plan and
# no unbindable reason, however many groups the ecosystem has -- and no path
# verification runs for an ecosystem that did not pass the gate.
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def recorded_path_verification():
    """Wraps the path-verification steps of the module so a test can see
    which ecosystems reached them. Yields a dict of the three mocks."""
    names = ("_verified_real_root", "_verified_groups", "_verified_directory")
    with contextlib.ExitStack() as stack:
        yield {
            name: stack.enter_context(mock.patch.object(SCAN, name, wraps=getattr(SCAN, name)))
            for name in names
        }


def _ecosystems_verified(mocks):
    return [call.args[0] for call in mocks["_verified_groups"].call_args_list]


class TestEcosystemGateReasons(unittest.TestCase):
    def test_absent_executable_gives_exactly_one_tool_not_found_for_several_groups(self):
        plans, reasons = _build(["a/package.json", "b/package.json"])
        self.assertEqual(plans, [])
        self.assertEqual(reasons, ["npm_tool_not_found"])

    def test_absent_executable_adds_no_unbindable_reason_for_unbindable_paths(self):
        plans, reasons = _build(["a/package.json", "/abs/package.json", "../up/package.json"])
        self.assertEqual(plans, [])
        self.assertEqual(reasons, ["npm_tool_not_found"])

    def test_validation_failure_gives_its_reason_once_no_plan_and_no_unbindable_reason(self):
        registry = copy.deepcopy(_registry())
        for entry in registry["ecosystems"]:
            if entry["ecosystem"] == "npm":
                entry["executable"] = "bash"
        plans, reasons = _build(
            ["a/package.json", "b/package.json", "/abs/package.json"], "npm", "bash", registry=registry
        )
        self.assertEqual(plans, [])
        self.assertEqual(reasons, ["npm_executable_not_allowlisted"])

    def test_a_failing_ecosystem_does_not_stop_its_neighbours(self):
        plans, reasons = _build(
            ["a/package.json", "b/package.json", "x/Cargo.toml", "y/Cargo.toml"], "cargo-audit"
        )
        self.assertEqual(reasons, ["npm_tool_not_found"])
        self.assertEqual(_targets(plans), ["x/Cargo.toml", "y/Cargo.toml"])

    def test_reasons_from_different_ecosystems_follow_registry_order(self):
        _plans, reasons = _build(["go.mod", "Cargo.toml", "package.json"])
        self.assertEqual(reasons, ["npm_tool_not_found", "cargo_tool_not_found", "go_tool_not_found"])

    def test_no_path_verification_runs_for_an_ecosystem_whose_executable_does_not_resolve(self):
        with recorded_path_verification() as mocks:
            plans, reasons = _build(["a/package.json", "/abs/package.json", "../up/package.json"])
        self.assertEqual((plans, reasons), ([], ["npm_tool_not_found"]))
        for name, mock_ in mocks.items():
            with self.subTest(step=name):
                self.assertEqual(mock_.call_count, 0)

    def test_no_path_verification_runs_for_an_ecosystem_whose_entry_fails_validation(self):
        registry = copy.deepcopy(_registry())
        for entry in registry["ecosystems"]:
            if entry["ecosystem"] == "npm":
                entry["executable"] = "bash"
        with recorded_path_verification() as mocks:
            plans, reasons = _build(
                ["a/package.json", "/abs/package.json"], "npm", "bash", registry=registry
            )
        self.assertEqual((plans, reasons), ([], ["npm_executable_not_allowlisted"]))
        for name, mock_ in mocks.items():
            with self.subTest(step=name):
                self.assertEqual(mock_.call_count, 0)

    def test_path_verification_reaches_only_the_ecosystems_that_passed_both_gates(self):
        registry = copy.deepcopy(_registry())
        for entry in registry["ecosystems"]:
            if entry["ecosystem"] == "npm":
                entry["args"] = ["audit", "$HOME"]  # fails validation
        changed = ["a/package.json", "b/Cargo.toml", "go.mod", "/abs/requirements.txt"]
        with recorded_path_verification() as mocks:
            plans, reasons = _build(changed, "npm", "cargo-audit", "pip-audit", registry=registry)
        self.assertEqual(reasons, ["npm_args_invalid", "go_tool_not_found"])
        self.assertEqual(_ecosystems_verified(mocks), ["cargo", "pip"])
        self.assertEqual([_name(p) for p in plans], ["cargo", "pip"])


# ---------------------------------------------------------------------------
# AC-7 (FR12) / AC-3 (FR6): planning only resolves paths and looks up the
# executable -- nothing is opened, launched or created.
# ---------------------------------------------------------------------------

class TestPlanningIsPure(unittest.TestCase):
    PATCH_TARGETS = (
        "builtins.open",
        "io.open",
        "os.open",
        "os.mkdir",
        "os.makedirs",
        "os.system",
        "subprocess.Popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_output",
    )

    @contextlib.contextmanager
    def forbidden_entry_points(self):
        with contextlib.ExitStack() as stack:
            patched = [
                stack.enter_context(mock.patch(target, side_effect=AssertionError(f"{target} called")))
                for target in self.PATCH_TARGETS
            ]
            yield
            for target, patch in zip(self.PATCH_TARGETS, patched):
                self.assertEqual(patch.call_count, 0, f"{target} was called")

    def test_build_scan_job_completes_for_root_and_nested_targets(self):
        entries = _entries()
        cases = (
            ("npm", "package.json"),
            ("npm", "services/api/package.json"),
            ("cargo", "Cargo.toml"),
            ("cargo", "x/y/Cargo.lock"),
            ("go", "go.mod"),
            ("go", "svc/go.sum"),
            ("pip", "requirements.txt"),
            ("pip", "backend/pyproject.toml"),
        )
        with self.forbidden_entry_points():
            for name, target in cases:
                job = SCAN.build_scan_job(
                    entries[name], target, "/definitely/not/there", f"/x/{name}",
                    prepared_inputs=_nominal_prepared(target),
                )
                self.assertEqual(job["manifest"], target)

    def test_build_scan_jobs_completes_for_nested_alias_absolute_escaping_and_nul_inputs(self):
        changed = [
            "services/api/package.json",
            "a/./package-lock.json",
            "/abs/package.json",
            "../up/package.json",
            "bad\x00dir/package.json",
            "x/Cargo.toml",
            "/abs/Cargo.lock",
            "svc/go.mod",
            "../go.sum",
            "bad\x00/go.mod",
            "/abs/requirements.txt",
            "../up/requirements.txt",
            "bad\x00dir/pyproject.toml",
        ]
        registry = _registry()
        with scanner_path(*ALL_STUBS) as root:
            with self.forbidden_entry_points():
                plans, reasons = SCAN.build_scan_jobs(registry, changed, root)
        self.assertEqual(
            reasons, ["npm_project_unbindable", "cargo_project_unbindable", "go_project_unbindable"]
        )
        self.assertEqual(_targets(plans, "npm"), ["a/package-lock.json", "services/api/package.json"])
        self.assertEqual(_targets(plans, "cargo"), ["x/Cargo.toml"])
        self.assertEqual(_targets(plans, "go"), ["svc/go.mod"])
        self.assertEqual(len(_targets(plans, "pip")), 3)

    def test_planning_a_real_tree_with_symlinks_opens_and_creates_nothing(self):
        registry = _registry()
        with project_tree("npm") as (root, outside):
            _touch(root / "real" / "package.json")
            (root / "alias").symlink_to(root / "real")
            (root / "esc").symlink_to(outside)
            with self.forbidden_entry_points():
                plans, reasons = SCAN.build_scan_jobs(
                    registry, ["alias/package.json", "esc/package.json"], root
                )
        self.assertEqual(reasons, ["npm_project_unbindable"])
        self.assertEqual(_targets(plans), ["real/package.json"])

    def test_a_nonexistent_project_root_stays_nonexistent(self):
        with scanner_path("npm") as root:
            self.assertFalse(root.exists())
            plans, _reasons = SCAN.build_scan_jobs(
                _registry(), ["a/package.json", "b/package.json"], root
            )
            self.assertFalse(root.exists())
        self.assertEqual(_targets(plans), ["a/package.json", "b/package.json"])

    def test_the_planning_signature_takes_neither_an_environment_nor_prepared_inputs(self):
        import inspect

        self.assertEqual(
            list(inspect.signature(SCAN.build_scan_jobs).parameters),
            ["registry", "changed_files", "project_root"],
        )


# ---------------------------------------------------------------------------
# AC-8: this module's own imports stay standard-library only.
# ---------------------------------------------------------------------------

class TestOwnImportsAreStandardLibraryOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), [])


if __name__ == "__main__":
    unittest.main()
