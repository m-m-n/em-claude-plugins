"""Tests for sca-per-project-scan-binding task0001 (per-group scan job
construction and workspace-escape pins) in `scan-dependencies.py`.

Covers task0001 Acceptance Criteria
(feature-docs/sca-per-project-scan-binding/tasks/task0001.md):

- AC-1: with the real registry, the npm job's argument vector carries
  `--workspaces=false` as its third registry argument; cargo, go and pip
  vectors are unchanged.
- AC-2: the go job's child environment pins GOWORK=off, GOFLAGS=-mod=readonly,
  GOENV=off and GOPROXY at its existing value, whatever the caller's
  environment carries; npm / cargo / pip pins equal their previous values.
- AC-3: `build_scan_jobs` returns one job per (ecosystem, project directory)
  group, groups in ascending plain-string order of the directory, ecosystems
  in registry order.
- AC-4: lexically equivalent spellings of one directory fall into one group;
  the job's manifest follows the Target convention (directory + "/" +
  basename of the file `manifest_file_for` selected; the bare basename at the
  root).
- AC-5: npm / cargo / go paths that are absolute, escape through `..` or
  contain NUL join no group and add `<ecosystem>_project_unbindable` exactly
  once per ecosystem; pip paths are never filtered that way.
- AC-6: an ecosystem that fails validation or whose executable is absent
  contributes its existing reason exactly once, no job and no unbindable
  reason, however many groups it has.
- AC-7: `build_scan_job` / `build_scan_jobs` open no file and launch no
  process (patched to fail).
- AC-8: this module imports the standard library only.

Test Notes: the script is loaded by file path (its name contains a hyphen),
following the sibling `tests/test_sca_scan_*.py` modules. No real scanner is
ever executed: executables are stubs on a temporary PATH, or nothing at all.
The working directory of nested jobs is deliberately NOT asserted here (that
rule ships with run_scan's task, D2): grouping is asserted through job
manifests and skip reasons only.
"""

import ast
import contextlib
import copy
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


def _entries():
    return {e["ecosystem"]: e for e in _registry()["ecosystems"]}


@contextlib.contextmanager
def scanner_path(*executables):
    """A temporary PATH holding an executable stub for each given name (or
    nothing at all when none is given). Yields a project-root path that is
    never created: build_scan_jobs must not need it to exist."""
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        for name in executables:
            stub = bin_dir / name
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            yield Path(tmp) / "proj"


ALL_STUBS = ("npm", "cargo-audit", "pip-audit", "govulncheck")


def _manifests(jobs, ecosystem=None):
    return [j["manifest"] for j in jobs if ecosystem is None or j["ecosystem"] == ecosystem]


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
        job = SCAN.build_scan_job(self.entries["npm"], "package.json", "/proj", "/x/npm")
        self.assertEqual(job["argv"], ["/x/npm", "audit", "--json", "--workspaces=false"])

    def test_npm_entry_still_passes_validation(self):
        self.assertIsNone(SCAN.validate_ecosystem_entry(self.entries["npm"]))

    def test_cargo_argv_is_unchanged(self):
        job = SCAN.build_scan_job(self.entries["cargo"], "Cargo.toml", "/proj", "/x/cargo-audit")
        self.assertEqual(job["argv"], ["/x/cargo-audit", "audit", "--json"])

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

    def test_jobs_built_by_build_scan_jobs_carry_the_same_vectors(self):
        jobs, reasons = _build(
            ["package.json", "Cargo.toml", "go.mod"], "npm", "cargo-audit", "govulncheck"
        )
        self.assertEqual(reasons, [])
        by_ecosystem = {j["ecosystem"]: j["argv"][1:] for j in jobs}
        self.assertEqual(by_ecosystem["npm"], ["audit", "--json", "--workspaces=false"])
        self.assertEqual(by_ecosystem["cargo"], ["audit", "--json"])
        self.assertEqual(by_ecosystem["go"], ["-json", "./..."])


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
                    self.entries[name], manifest, "/proj", f"/x/{name}", environ=self.HOSTILE
                )
                self.assertFalse([k for k in job["env"] if k.startswith("GO")])


# ---------------------------------------------------------------------------
# AC-3, AC-4: one job per (ecosystem, lexical project directory) group.
# ---------------------------------------------------------------------------

class TestJobPerLexicalGroup(unittest.TestCase):
    def test_two_npm_directories_yield_two_jobs_in_ascending_directory_order(self):
        jobs, reasons = _build(
            ["services/web/package.json", "services/api/package.json"], "npm"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(
            _manifests(jobs), ["services/api/package.json", "services/web/package.json"]
        )
        self.assertEqual({j["ecosystem"] for j in jobs}, {"npm"})

    def test_root_group_comes_first(self):
        jobs, _ = _build(["a/package.json", "package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["package.json", "a/package.json"])

    def test_order_is_plain_string_order_of_the_directory(self):
        # Plain-string order puts "a-b" (0x2d) before "a/b" (0x2f); a
        # segment-wise order would put "a/b" first.
        jobs, _ = _build(["a/b/package.json", "a-b/package.json", "a/package.json"], "npm")
        self.assertEqual(
            _manifests(jobs), ["a/package.json", "a-b/package.json", "a/b/package.json"]
        )

    def test_order_does_not_depend_on_input_order(self):
        changed = ["z/package.json", "m/package.json", "a/package.json", "package.json"]
        forward, _ = _build(changed, "npm")
        backward, _ = _build(list(reversed(changed)), "npm")
        self.assertEqual(_manifests(forward), _manifests(backward))
        self.assertEqual(_manifests(forward), ["package.json", "a/package.json", "m/package.json", "z/package.json"])

    def test_every_npm_job_precedes_every_cargo_job_whatever_the_input_order(self):
        changed = ["svc/Cargo.toml", "b/package.json", "Cargo.toml", "a/package.json"]
        jobs, reasons = _build(changed, "npm", "cargo-audit")
        self.assertEqual(reasons, [])
        self.assertEqual([j["ecosystem"] for j in jobs], ["npm", "npm", "cargo", "cargo"])
        self.assertEqual(_manifests(jobs, "npm"), ["a/package.json", "b/package.json"])
        self.assertEqual(_manifests(jobs, "cargo"), ["Cargo.toml", "svc/Cargo.toml"])

    def test_ecosystems_follow_registry_order_across_all_four(self):
        changed = ["go.mod", "requirements.txt", "Cargo.toml", "package.json"]
        jobs, reasons = _build(changed, *ALL_STUBS)
        self.assertEqual(reasons, [])
        self.assertEqual([j["ecosystem"] for j in jobs], ["npm", "cargo", "pip", "go"])

    def test_go_and_cargo_group_per_directory_too(self):
        jobs, _ = _build(
            ["svc/b/go.mod", "svc/a/go.mod", "x/Cargo.toml", "y/Cargo.toml"], "cargo-audit", "govulncheck"
        )
        self.assertEqual(_manifests(jobs, "cargo"), ["x/Cargo.toml", "y/Cargo.toml"])
        self.assertEqual(_manifests(jobs, "go"), ["svc/a/go.mod", "svc/b/go.mod"])

    def test_a_manifest_and_its_lockfile_in_one_directory_yield_one_job(self):
        jobs, _ = _build(["a/package-lock.json", "a/package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_a_lockfile_only_directory_is_still_a_group(self):
        jobs, _ = _build(["a/package-lock.json", "b/package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["a/package-lock.json", "b/package.json"])

    def test_unrelated_changed_files_form_no_group(self):
        jobs, reasons = _build(["README.md", "src/app.js", "a/package.json"], "npm")
        self.assertEqual(reasons, [])
        self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_pip_groups_by_directory_and_keeps_the_raw_selected_file_as_target(self):
        jobs, reasons = _build(
            ["y/pyproject.toml", "x/./requirements.txt", "x/pyproject.toml"], "pip-audit"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(_manifests(jobs), ["x/./requirements.txt", "y/pyproject.toml"])

    def test_pip_aliases_of_one_directory_form_one_group(self):
        jobs, _ = _build(["a/requirements.txt", "a/./pyproject.toml", "./a//requirements.txt"], "pip-audit")
        self.assertEqual(_manifests(jobs), ["a/requirements.txt"])


class TestLexicalAliasesJoinOneGroup(unittest.TestCase):
    def test_manifest_lockfile_alias_and_repeat_yield_one_job_with_the_manifest(self):
        jobs, reasons = _build(
            ["a/package.json", "a/./package-lock.json", "a/package.json"], "npm"
        )
        self.assertEqual(reasons, [])
        self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_lockfile_only_change_with_a_dot_segment_keeps_the_lockfile_basename(self):
        jobs, _ = _build(["a/./go.sum"], "govulncheck")
        self.assertEqual([j["ecosystem"] for j in jobs], ["go"])
        self.assertEqual(_manifests(jobs), ["a/go.sum"])

    def test_root_level_change_keeps_the_bare_basename(self):
        jobs, _ = _build(["package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["package.json"])

    def test_root_aliases_keep_the_bare_basename(self):
        for spelling in ("./package.json", ".//package.json", "a/../package.json", "a/b/../../package.json"):
            with self.subTest(spelling=spelling):
                jobs, reasons = _build([spelling], "npm")
                self.assertEqual(reasons, [])
                self.assertEqual(_manifests(jobs), ["package.json"])

    def test_dot_dot_segments_that_cancel_inside_the_tree_are_normalized(self):
        for spelling in ("b/../a/package.json", "./a//package.json", "a/./b/../package.json", "x/../a/./package.json"):
            with self.subTest(spelling=spelling):
                jobs, reasons = _build([spelling, "a/package.json"], "npm")
                self.assertEqual(reasons, [])
                self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_target_is_normalized_even_when_the_selected_input_was_spelled_oddly(self):
        jobs, _ = _build(["./a//./package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_nested_lockfile_alias_for_cargo(self):
        jobs, _ = _build(["x//y/./Cargo.lock"], "cargo-audit")
        self.assertEqual(_manifests(jobs), ["x/y/Cargo.lock"])

    def test_manifest_first_selection_holds_whatever_the_input_order_inside_a_group(self):
        jobs, _ = _build(["a/./package-lock.json", "a/package.json"], "npm")
        self.assertEqual(_manifests(jobs), ["a/package.json"])

    def test_distinct_directories_are_not_merged(self):
        jobs, _ = _build(["a/package.json", "a/b/package.json", "ab/package.json"], "npm")
        self.assertEqual(
            _manifests(jobs), ["a/package.json", "a/b/package.json", "ab/package.json"]
        )


# ---------------------------------------------------------------------------
# AC-5: lexically unbindable npm / cargo / go paths; pip is never filtered.
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


class TestLexicallyUnbindablePaths(unittest.TestCase):
    def test_each_unbindable_kind_is_dropped_with_one_reason_and_a_valid_group_still_yields_its_job(self):
        for name, manifest, lockfile, stub in FILTERED:
            for kind, bad in _unbindable_spellings(manifest).items():
                with self.subTest(ecosystem=name, kind=kind):
                    jobs, reasons = _build([bad, f"ok/{manifest}"], stub)
                    self.assertEqual(reasons, [f"{name}_project_unbindable"])
                    self.assertEqual(_manifests(jobs), [f"ok/{manifest}"])

    def test_unbindable_lockfile_paths_are_dropped_too(self):
        for name, _manifest, lockfile, stub in FILTERED:
            for kind, bad in _unbindable_spellings(lockfile).items():
                with self.subTest(ecosystem=name, kind=kind):
                    jobs, reasons = _build([bad], stub)
                    self.assertEqual(jobs, [])
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
                jobs, reasons = _build(bad + [f"ok/{manifest}", f"ok2/{manifest}"], stub)
                self.assertEqual(reasons, [f"{name}_project_unbindable"])
                self.assertEqual(_manifests(jobs), [f"ok/{manifest}", f"ok2/{manifest}"])

    def test_only_unbindable_paths_yield_no_job_and_the_reason(self):
        for name, manifest, _lockfile, stub in FILTERED:
            with self.subTest(ecosystem=name):
                jobs, reasons = _build([f"/abs/{manifest}", f"../x/{manifest}"], stub)
                self.assertEqual(jobs, [])
                self.assertEqual(reasons, [f"{name}_project_unbindable"])

    def test_reasons_follow_registry_order(self):
        changed = []
        for _name, manifest, _lockfile, _stub in reversed(FILTERED):
            changed.append(f"/abs/{manifest}")
        _jobs, reasons = _build(changed, "npm", "cargo-audit", "govulncheck")
        self.assertEqual(reasons, ["npm_project_unbindable", "cargo_project_unbindable", "go_project_unbindable"])

    def test_a_path_that_stays_inside_after_cancelling_is_not_unbindable(self):
        for name, manifest, _lockfile, stub in FILTERED:
            with self.subTest(ecosystem=name):
                jobs, reasons = _build([f"a/b/../../{manifest}"], stub)
                self.assertEqual(reasons, [])
                self.assertEqual(_manifests(jobs), [manifest])

    def test_names_that_merely_start_with_two_dots_are_not_escaping(self):
        jobs, reasons = _build(["..hidden/package.json", "a/..b/package.json"], "npm")
        self.assertEqual(reasons, [])
        self.assertEqual(_manifests(jobs), ["..hidden/package.json", "a/..b/package.json"])

    def test_the_reason_token_carries_no_path_derived_text(self):
        _jobs, reasons = _build(["/secret/location/package.json"], "npm")
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
        jobs, reasons = _build(raw, "pip-audit")
        self.assertEqual(reasons, [])
        self.assertEqual(sorted(_manifests(jobs)), sorted(raw))

    def test_pip_pyproject_paths_of_the_same_kinds_are_not_filtered_either(self):
        raw = ["/abs/pyproject.toml", "../up/pyproject.toml", "bad\x00dir/pyproject.toml"]
        jobs, reasons = _build(raw, "pip-audit")
        self.assertEqual(reasons, [])
        self.assertEqual(sorted(_manifests(jobs)), sorted(raw))

    def test_pip_directory_spellings_that_differ_only_by_an_absolute_prefix_stay_apart(self):
        jobs, _ = _build(["/a/requirements.txt", "a/requirements.txt"], "pip-audit")
        self.assertEqual(sorted(_manifests(jobs)), ["/a/requirements.txt", "a/requirements.txt"])


# ---------------------------------------------------------------------------
# AC-6: ecosystem-level reasons come once, with no job and no unbindable
# reason, however many groups the ecosystem has.
# ---------------------------------------------------------------------------

class TestEcosystemGateReasons(unittest.TestCase):
    def test_absent_executable_gives_exactly_one_tool_not_found_for_several_groups(self):
        jobs, reasons = _build(["a/package.json", "b/package.json"])
        self.assertEqual(jobs, [])
        self.assertEqual(reasons, ["npm_tool_not_found"])

    def test_absent_executable_adds_no_unbindable_reason_for_unbindable_paths(self):
        jobs, reasons = _build(["a/package.json", "/abs/package.json", "../up/package.json"])
        self.assertEqual(jobs, [])
        self.assertEqual(reasons, ["npm_tool_not_found"])

    def test_validation_failure_gives_its_reason_once_no_job_and_no_unbindable_reason(self):
        registry = copy.deepcopy(_registry())
        for entry in registry["ecosystems"]:
            if entry["ecosystem"] == "npm":
                entry["executable"] = "bash"
        jobs, reasons = _build(
            ["a/package.json", "b/package.json", "/abs/package.json"], "npm", "bash", registry=registry
        )
        self.assertEqual(jobs, [])
        self.assertEqual(reasons, ["npm_executable_not_allowlisted"])

    def test_a_failing_ecosystem_does_not_stop_its_neighbours(self):
        jobs, reasons = _build(
            ["a/package.json", "b/package.json", "x/Cargo.toml", "y/Cargo.toml"], "cargo-audit"
        )
        self.assertEqual(reasons, ["npm_tool_not_found"])
        self.assertEqual(_manifests(jobs), ["x/Cargo.toml", "y/Cargo.toml"])

    def test_reasons_from_different_ecosystems_follow_registry_order(self):
        _jobs, reasons = _build(["go.mod", "Cargo.toml", "package.json"])
        self.assertEqual(reasons, ["npm_tool_not_found", "cargo_tool_not_found", "go_tool_not_found"])


# ---------------------------------------------------------------------------
# AC-7 (FR12): pure construction -- nothing is opened, nothing is launched.
# ---------------------------------------------------------------------------

class TestConstructionIsPure(unittest.TestCase):
    PATCH_TARGETS = (
        "builtins.open",
        "io.open",
        "os.open",
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
                job = SCAN.build_scan_job(entries[name], target, "/definitely/not/there", f"/x/{name}")
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
                jobs, reasons = SCAN.build_scan_jobs(registry, changed, root)
        self.assertEqual(
            reasons, ["npm_project_unbindable", "cargo_project_unbindable", "go_project_unbindable"]
        )
        self.assertEqual(_manifests(jobs, "npm"), ["a/package-lock.json", "services/api/package.json"])
        self.assertEqual(_manifests(jobs, "cargo"), ["x/Cargo.toml"])
        self.assertEqual(_manifests(jobs, "go"), ["svc/go.mod"])
        self.assertEqual(len(_manifests(jobs, "pip")), 3)

    def test_the_project_root_is_never_touched(self):
        with scanner_path("npm") as root:
            self.assertFalse(root.exists())
            SCAN.build_scan_jobs(_registry(), ["a/package.json", "b/package.json"], root)
            self.assertFalse(root.exists())


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
