"""Tests for task0008 (review-sca-axis rework round 1): scan-job
construction, trusted-binary resolution, and configuration isolation in
`scan-dependencies.py`.

Covers task0008 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0008.md):

- AC-1: the constructed pip job's argument vector audits a prepared
  requirements file of the REVIEWED project's pins (sca-pip-no-build-exec
  replaced the earlier reviewed-file and project-directory forms, which are
  gone); it never contains an install or write-resolution form, and the
  audited target never defaults to the ambient environment.
- AC-2: every constructed job's first argument-vector element is an
  absolute path to an allowlisted scanner binary, and no constructed
  vector has the multiplexer-front-end + subcommand form. The registry and
  the executable allowlist agree for every registered ecosystem, asserted
  directly against both files.
- AC-3: when the trusted binary is absent from PATH the ecosystem yields
  its machine-stable tool-absent skip and no alternative command form is
  constructed for it.
- AC-4: against a reviewed-project fixture containing a hostile alias
  definition in the cargo configuration file and a hostile registry line
  in the npm configuration file, the constructed job's executable path and
  the child environment's configuration/registry selection are identical
  to those constructed from the same fixture without those two files.

sca-python-lockfile-audit task0001 AC-2 (FR3, NFR2, NFR6, TM-5) extends AC-1
for a changed poetry.lock / Pipfile.lock: the pip job is built for a PREPARED
requirements file -- [executable, `-r`, prepared file, `--no-deps`,
`--disable-pip`, `--format`, `json`] with the lockfile as the job's manifest --
without reading, writing or launching anything; a lockfile manifest without a
prepared file is rejected; and ALLOWED_EXECUTABLES, ECOSYSTEM_LOCKFILES and the
pip child-environment pins hold their previous (literal) values.

sca-pip-no-build-exec task0001 (TS-6) moves pip's flag and arguments into the
registry's per-target-form table: the pip entry carries `target_forms` with
exactly the form `prepared_requirements` (`target_flag` `-r`, `args`
`--no-deps`, `--disable-pip`, `--format`, `json`) and no top-level `args` /
`target_flag`, asserted here through this module's restricted parser and the
script's loader; `validate_ecosystem_entry` checks the table
(`pip_target_forms_invalid`); the npm, cargo and go entry texts are pinned
literally. The same prepared-file job form now serves requirements.txt and
pyproject.toml too (its scenarios live in
tests/test_sca_pip_manifest_prepared_audit.py).

sca-scanner-project-config-isolation task0001 updates the npm / cargo job
expectations to the isolation contract: an npm / cargo job is built from the
prepared isolation paths of its group (`prepared_inputs`), its cwd is the
isolation directory, and cargo's argument vector carries the registry-declared
`--file <copy>` right after `audit`. The configuration-isolation cases (AC-4)
keep proving that hostile project files change nothing about the job.

sca-file-tasks-robustness task0004 (FR6): `build_scan_jobs` returns plans (one
per project-directory group, not launched), so the AC-3 checks read the plans
and their resolved executable; the constructed-job checks stay on
`build_scan_job`, and the argv / cwd a launched job really gets are asserted on
`run_scan` in tests/test_sca_run_scan_plan_units.py.

Per Test Notes / IMPLEMENTATION.md Conventions: this module's own imports
stay standard-library only (NFR7) -- the script under test is loaded by
file path (its name contains a hyphen), following
tests/test_validate_worker_output.py's pattern. `vuln-scanners.yaml` is
independently parsed here with a hand-rolled, restricted-subset parser
local to THIS module (never PyYAML in this module's own imports, never
imported from a sibling test module), matching
tests/test_reviewers_primary_chains.py's convention -- AC-2's
registry/allowlist agreement is a cross-file assertion built on it. No real
scanner is ever executed: AC-1/AC-2/AC-4 assert on the CONSTRUCTED job
alone (a pure function of registry data, a manifest path, a project root
and an already-resolved executable path); AC-3's binary-resolution step is
exercised by placing an executable stub -- or nothing -- on a temporary
PATH.
"""

import copy
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "em-workflow" / "references" / "vuln-scanners.yaml"
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_dependencies_invocation", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


SCAN = _load_module()

ISO_DIR = {"npm": "/iso/npm", "cargo": "/iso/cargo"}


def _prepared(name):
    """The prepared isolation paths of an npm / cargo group (none for the
    other ecosystems): plain values, `build_scan_job` never touches them."""
    if name == "npm":
        return SCAN.PreparedInputs(
            directory=ISO_DIR["npm"],
            files={"manifest": "/iso/npm/package.json", "anchor": "/iso/npm/package-lock.json"},
        )
    if name == "cargo":
        return SCAN.PreparedInputs(
            directory=ISO_DIR["cargo"], files={"lockfile": "/iso/cargo/Cargo.lock"}
        )
    return None


# ---------------------------------------------------------------------------
# Module-local restricted-subset YAML parser (Test Notes: "the registry is
# read with the module-local restricted YAML parser convention this
# repository's test modules already use, not with a third-party import").
# Scoped to what the registry holds: a list of ecosystem items whose keys sit
# at indent 4, flow lists (`[a, b]`), flow mappings (`{a: b}`) and -- for a
# target-form table (`target_forms:`) -- block mappings nested at indent 6
# (the form name) and indent 8 (its keys).
# ---------------------------------------------------------------------------

def _parse_flow_list(value):
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"expected a flow list, got: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(",")]


def _parse_flow_mapping(value):
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"expected a flow mapping, got: {value!r}")
    inner = value[1:-1].strip()
    result = {}
    if not inner:
        return result
    for part in inner.split(","):
        key, _, item = part.partition(":")
        result[key.strip()] = item.strip()
    return result


def _parse_value(value):
    if value.startswith("["):
        return _parse_flow_list(value)
    if value.startswith("{"):
        return _parse_flow_mapping(value)
    return value


def parse_vuln_scanners_yaml(text):
    """Restricted-subset parser for vuln-scanners.yaml's `ecosystems:` list.
    Returns a list of per-ecosystem dicts: scalars stay strings, flow lists
    become lists of strings, flow mappings become dicts of strings, and a key
    with no value opens a nested block mapping whose keys sit two columns
    deeper (the `target_forms` table). Raises ValueError if no top-level
    `ecosystems:` key is found or a line inside the block violates the
    expected nesting."""
    lines = text.splitlines()
    ecosystems = []
    in_block = False
    saw_block = False
    stack = []  # (indent of the key, the mapping it opened), innermost last

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not in_block:
            if line == "ecosystems:":
                in_block = True
                saw_block = True
            continue
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            break  # dedent back to column 0: the ecosystems block ended

        if indent == 2:
            if not stripped.startswith("- ecosystem:"):
                raise ValueError(f"expected an ecosystem list item, got: {raw!r}")
            current = {"ecosystem": stripped[len("- ecosystem:"):].strip()}
            ecosystems.append(current)
            stack = [(2, current)]
            continue

        if not stack:
            raise ValueError(f"attribute line before any ecosystem: {raw!r}")
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        if indent != 2 + 2 * len(stack):
            raise ValueError(f"unexpected indentation: {raw!r}")

        key, sep, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not sep:
            raise ValueError(f"malformed line: {raw!r}")
        container = stack[-1][1]
        if value == "":
            child = {}
            container[key] = child
            stack.append((indent, child))
        else:
            container[key] = _parse_value(value)

    if not saw_block:
        raise ValueError("no top-level `ecosystems:` key found")
    return ecosystems


# ---------------------------------------------------------------------------
# AC-2: registry / executable-allowlist agreement, and the trusted-binary
# fix itself (cargo names the standalone audit binary, not the `cargo`
# front end).
# ---------------------------------------------------------------------------

class TestRegistryAndAllowlistAgree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REGISTRY_PATH.read_text(encoding="utf-8")
        cls.ecosystems = parse_vuln_scanners_yaml(cls.text)
        cls.by_name = {e["ecosystem"]: e for e in cls.ecosystems}

    def test_every_registry_executable_is_allowlisted(self):
        for entry in self.ecosystems:
            name = entry["ecosystem"]
            with self.subTest(ecosystem=name):
                self.assertIn(name, SCAN.ALLOWED_EXECUTABLES)
                self.assertIn(entry["executable"], SCAN.ALLOWED_EXECUTABLES[name])

    def test_cargo_names_the_standalone_binary_not_the_cargo_front_end(self):
        self.assertEqual(self.by_name["cargo"]["executable"], "cargo-audit")

    def test_no_registered_ecosystem_names_cargo_itself_as_executable(self):
        # The multiplexer-front-end + subcommand form this task closes:
        # `cargo` resolving an external `audit` subcommand through a
        # project-controlled [alias] entry.
        for entry in self.ecosystems:
            with self.subTest(ecosystem=entry["ecosystem"]):
                self.assertNotEqual(entry["executable"], "cargo")

    def test_allowlist_has_no_extra_ecosystem_the_registry_lacks(self):
        self.assertEqual(set(SCAN.ALLOWED_EXECUTABLES), set(self.by_name))


# ---------------------------------------------------------------------------
# AC-2 (continued): every constructed job's argv[0] is the absolute
# executable path; the ORIGINAL args are otherwise untouched for the
# ecosystems this task does not change (npm, go).
# ---------------------------------------------------------------------------

class TestBuildScanJobArgumentVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.by_name = {e["ecosystem"]: e for e in registry["ecosystems"]}

    def test_cargo_job_argv0_is_the_absolute_standalone_binary_path(self):
        # sca-scanner-project-config-isolation FR2/FR3: the audited lockfile
        # is the copy in the isolation directory, named through the
        # registry-declared `--file` right after `audit`.
        job = SCAN.build_scan_job(
            self.by_name["cargo"], "Cargo.toml", "/proj", "/usr/local/bin/cargo-audit",
            prepared_inputs=_prepared("cargo"),
        )
        self.assertEqual(
            job["argv"],
            ["/usr/local/bin/cargo-audit", "audit", "--file", "/iso/cargo/Cargo.lock", "--json"],
        )

    def test_npm_job_argv_pins_workspaces_off(self):
        # sca-per-project-scan-binding FR11/FR14: the registry's npm args
        # gain `--workspaces=false` so npm audits the bound project only.
        job = SCAN.build_scan_job(
            self.by_name["npm"], "package.json", "/proj", "/usr/local/bin/npm",
            prepared_inputs=_prepared("npm"),
        )
        self.assertEqual(job["argv"], ["/usr/local/bin/npm", "audit", "--json", "--workspaces=false"])

    def test_go_job_argv_unaffected_by_this_task(self):
        job = SCAN.build_scan_job(self.by_name["go"], "go.mod", "/proj", "/usr/local/bin/govulncheck")
        self.assertEqual(job["argv"], ["/usr/local/bin/govulncheck", "-json", "./..."])

    def test_every_job_argv0_is_an_absolute_path(self):
        cases = [
            ("npm", "package.json", "/x/npm"),
            ("cargo", "Cargo.toml", "/x/cargo-audit"),
            ("pip", "requirements.txt", "/x/pip-audit"),
            ("go", "go.mod", "/x/govulncheck"),
        ]
        for name, manifest, executable in cases:
            with self.subTest(ecosystem=name):
                job = SCAN.build_scan_job(
                    self.by_name[name], manifest, "/proj", executable,
                    prepared_inputs=_prepared(name),
                    prepared_file="/prepared/pip-0001.txt" if name == "pip" else None,
                )
                self.assertTrue(os.path.isabs(job["argv"][0]))
                self.assertEqual(job["argv"][0], executable)

    def test_job_carries_ecosystem_manifest_cwd_and_env(self):
        # the label stays the project-relative manifest; an npm / cargo
        # job's cwd is the isolation directory, never the project root.
        job = SCAN.build_scan_job(
            self.by_name["npm"], "package.json", "/proj", "/x/npm", prepared_inputs=_prepared("npm")
        )
        self.assertEqual(job["ecosystem"], "npm")
        self.assertEqual(job["manifest"], "package.json")
        self.assertEqual(job["cwd"], ISO_DIR["npm"])
        self.assertIsInstance(job["env"], dict)

    def test_constructing_a_job_launches_nothing(self):
        # Purity check: an executable path that does not exist on disk at
        # all is accepted without error -- build_scan_job never resolves
        # or invokes it.
        job = SCAN.build_scan_job(
            self.by_name["npm"], "package.json", "/proj", "/definitely/not/a/real/path/npm",
            prepared_inputs=_prepared("npm"),
        )
        self.assertEqual(job["argv"][0], "/definitely/not/a/real/path/npm")


# ---------------------------------------------------------------------------
# AC-1 (TS-26): the pip job audits the REVIEWED PROJECT, never the ambient
# environment.
#
# sca-pip-no-build-exec task0001: the job is built for a PREPARED requirements
# file of the reviewed manifest's pins -- the reviewed requirements file and
# the project directory are never handed to pip-audit any more. Every manifest
# kind gets the same vector; the job form is exercised against the full set of
# targets in tests/test_sca_pip_manifest_prepared_audit.py.
# ---------------------------------------------------------------------------

class TestPipJobAuditsTheReviewedProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.pip_entry = {e["ecosystem"]: e for e in registry["ecosystems"]}["pip"]

    # sca-python-lockfile-audit task0001 AC-2 (FR3, NFR2, NFR6, TM-5): a
    # lockfile is never handed to pip-audit directly nor audited through its
    # directory. The job audits a PREPARED requirements file (one
    # `name==version` line per pin) that a separate stage wrote outside the
    # project root; build_scan_job only receives that file's path.
    PREPARED = "/tmp/prepared-pins-0001.txt"
    JOB_ARGV_TAIL = ["--no-deps", "--disable-pip", "--format", "json"]
    LOCKFILES = ("poetry.lock", "Pipfile.lock")
    MANIFESTS = ("requirements.txt", "pyproject.toml")

    def _build(self, manifest):
        return SCAN.build_scan_job(
            self.pip_entry, manifest, "/proj", "/x/pip-audit", prepared_file=self.PREPARED
        )

    def test_a_requirements_file_is_never_the_audited_target(self):
        job = self._build("requirements.txt")
        self.assertEqual(job["argv"], ["/x/pip-audit", "-r", self.PREPARED] + self.JOB_ARGV_TAIL)
        self.assertNotIn("requirements.txt", job["argv"])
        self.assertEqual(job["manifest"], "requirements.txt")

    def test_a_nested_requirements_path_is_the_label_only(self):
        job = self._build("backend/requirements.txt")
        self.assertEqual(job["argv"], ["/x/pip-audit", "-r", self.PREPARED] + self.JOB_ARGV_TAIL)
        self.assertNotIn("backend/requirements.txt", job["argv"])
        self.assertEqual(job["manifest"], "backend/requirements.txt")

    def test_a_pyproject_toml_never_audits_a_directory(self):
        for manifest, directory in (("pyproject.toml", "."), ("services/api/pyproject.toml", "services/api")):
            with self.subTest(manifest=manifest):
                job = self._build(manifest)
                self.assertEqual(
                    job["argv"], ["/x/pip-audit", "-r", self.PREPARED] + self.JOB_ARGV_TAIL
                )
                self.assertNotIn(directory, job["argv"])
                self.assertEqual(job["manifest"], manifest)
                self.assertEqual(job["cwd"], "/proj")

    def test_a_changed_lockfile_gets_the_same_job_form(self):
        for lockfile in ("poetry.lock", "Pipfile.lock", "services/api/poetry.lock", "svc/Pipfile.lock"):
            with self.subTest(lockfile=lockfile):
                job = self._build(lockfile)
                self.assertEqual(
                    job["argv"],
                    ["/x/pip-audit", "-r", self.PREPARED] + self.JOB_ARGV_TAIL,
                )
                self.assertEqual(job["manifest"], lockfile)
                self.assertEqual(job["ecosystem"], "pip")
                self.assertEqual(job["cwd"], "/proj")

    def test_the_job_is_built_even_when_the_prepared_path_does_not_exist(self):
        missing = "/definitely/not/a/real/dir/prepared-pins.txt"
        with mock.patch("builtins.open", side_effect=AssertionError("file opened")), \
                mock.patch("os.open", side_effect=AssertionError("file opened")), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("process launched")), \
                mock.patch("subprocess.run", side_effect=AssertionError("process launched")):
            job = SCAN.build_scan_job(
                self.pip_entry, "poetry.lock", "/proj", "/x/pip-audit", prepared_file=missing
            )
        self.assertEqual(job["argv"][:3], ["/x/pip-audit", "-r", missing])
        self.assertFalse(os.path.exists(missing))

    def test_a_manifest_without_a_prepared_file_is_rejected(self):
        for manifest in self.LOCKFILES + self.MANIFESTS + ("sub/poetry.lock", "backend/requirements.txt"):
            for kwargs in ({}, {"prepared_file": None}, {"prepared_file": ""}):
                with self.subTest(manifest=manifest, kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        SCAN.build_scan_job(
                            self.pip_entry, manifest, "/proj", "/x/pip-audit", **kwargs
                        )

    def test_the_directory_and_reviewed_file_forms_are_gone(self):
        self.assertFalse(hasattr(SCAN, "_pip_target"))

    def test_every_pip_job_carries_the_prepared_file_and_both_flags(self):
        for manifest in self.MANIFESTS + self.LOCKFILES:
            job = self._build(manifest)
            with self.subTest(manifest=manifest):
                self.assertEqual(job["argv"][1:3], ["-r", self.PREPARED])
                self.assertIn("--no-deps", job["argv"])
                self.assertIn("--disable-pip", job["argv"])

    def test_target_is_never_absent_never_the_ambient_environment(self):
        for manifest in ("requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"):
            with self.subTest(manifest=manifest):
                job = self._build(manifest)
                # More than the bare `[executable, --format, json]` form:
                # a real target token is present.
                self.assertGreater(len(job["argv"]), 3)

    def test_no_argument_form_installs_or_writes_a_resolution_artifact(self):
        forbidden_tokens = ("install", "--fix", "-o", "--output", "--require-hashes")
        for manifest in ("requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"):
            job = self._build(manifest)
            with self.subTest(manifest=manifest):
                for forbidden in forbidden_tokens:
                    self.assertNotIn(forbidden, job["argv"])


# ---------------------------------------------------------------------------
# AC-3 (TS-26/TS-4): the trusted binary absent from PATH -> machine-stable
# skip, no plan, no alternative command form.
#
# sca-file-tasks-robustness task0004: `build_scan_jobs` returns the plans of
# the scan, not built jobs, so the checks below read plans. The job a plan's
# executable ends up in (argv[0] absolute, `audit` right after it for cargo)
# is asserted on `build_scan_job` above and on `run_scan` in
# tests/test_sca_run_scan_plan_units.py.
# ---------------------------------------------------------------------------

class TestUnresolvableBinaryYieldsSkipNoPlan(unittest.TestCase):
    def test_missing_cargo_audit_yields_skip_reason_and_no_plan(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            empty_bin = Path(tmp) / "empty-bin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}, clear=False):
                plans, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(plans, [])
        self.assertEqual(skip_reasons, ["cargo_tool_not_found"])

    def test_present_binary_yields_exactly_one_plan_with_the_absolute_path(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "cargo-audit"
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                plans, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(skip_reasons, [])
        self.assertEqual(len(plans), 1)
        self.assertTrue(os.path.isabs(plans[0].executable))
        self.assertEqual(plans[0].executable, str(stub))
        self.assertEqual(plans[0].ecosystem["ecosystem"], "cargo")
        self.assertEqual(plans[0].target, "Cargo.toml")

    def test_no_plan_is_built_for_the_ecosystem_with_no_resolvable_binary(self):
        # Two ecosystems selected; only npm's stub is present. cargo
        # contributes a skip reason and no plan -- npm still gets one, and
        # no alternative command form is attempted for cargo.
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "npm"
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                plans, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["package.json", "Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(skip_reasons, ["cargo_tool_not_found"])
        self.assertEqual([p.ecosystem["ecosystem"] for p in plans], ["npm"])


# ---------------------------------------------------------------------------
# AC-4 (TS-26): configuration isolation -- a hostile alias definition in
# the cargo configuration file and a hostile registry line in the npm
# configuration file change NOTHING about the constructed job.
# ---------------------------------------------------------------------------

class TestConfigurationIsolationIgnoresProjectFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.by_name = {e["ecosystem"]: e for e in registry["ecosystems"]}

    def test_hostile_cargo_alias_does_not_change_the_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean_root = Path(tmp) / "clean"
            clean_root.mkdir()
            (clean_root / "Cargo.toml").write_text("[dependencies]\n", encoding="utf-8")

            hostile_root = Path(tmp) / "hostile"
            hostile_root.mkdir()
            (hostile_root / "Cargo.toml").write_text("[dependencies]\n", encoding="utf-8")
            cargo_dir = hostile_root / ".cargo"
            cargo_dir.mkdir()
            (cargo_dir / "config.toml").write_text(
                '[alias]\naudit = "run --bin evil"\n', encoding="utf-8"
            )

            clean_job = SCAN.build_scan_job(
                self.by_name["cargo"], "Cargo.toml", clean_root, "/usr/local/bin/cargo-audit",
                prepared_inputs=_prepared("cargo"),
            )
            hostile_job = SCAN.build_scan_job(
                self.by_name["cargo"], "Cargo.toml", hostile_root, "/usr/local/bin/cargo-audit",
                prepared_inputs=_prepared("cargo"),
            )

        self.assertEqual(clean_job["argv"][0], hostile_job["argv"][0])
        self.assertEqual(clean_job["argv"], hostile_job["argv"])
        self.assertEqual(clean_job["env"], hostile_job["env"])
        # the hostile project's directory is never the scanner's cwd
        self.assertEqual(hostile_job["cwd"], ISO_DIR["cargo"])

    def test_hostile_npmrc_registry_line_does_not_change_the_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean_root = Path(tmp) / "clean"
            clean_root.mkdir()
            (clean_root / "package.json").write_text("{}\n", encoding="utf-8")

            hostile_root = Path(tmp) / "hostile"
            hostile_root.mkdir()
            (hostile_root / "package.json").write_text("{}\n", encoding="utf-8")
            (hostile_root / ".npmrc").write_text(
                "registry=http://evil.example.com/\n", encoding="utf-8"
            )

            clean_job = SCAN.build_scan_job(
                self.by_name["npm"], "package.json", clean_root, "/usr/local/bin/npm",
                prepared_inputs=_prepared("npm"),
            )
            hostile_job = SCAN.build_scan_job(
                self.by_name["npm"], "package.json", hostile_root, "/usr/local/bin/npm",
                prepared_inputs=_prepared("npm"),
            )

        self.assertEqual(clean_job["argv"], hostile_job["argv"])
        self.assertEqual(clean_job["env"], hostile_job["env"])
        # the hostile project's directory is never the scanner's cwd
        self.assertEqual(hostile_job["cwd"], ISO_DIR["npm"])
        self.assertEqual(hostile_job["env"].get("npm_config_registry"), "https://registry.npmjs.org/")
        self.assertNotEqual(hostile_job["env"].get("npm_config_registry"), "http://evil.example.com/")

    def test_child_env_never_reads_a_file_inside_the_project(self):
        # build_child_env's signature takes no project_root at all -- a
        # structural guarantee, not just an observed outcome, that it
        # cannot open a file inside the reviewed tree.
        import inspect

        params = list(inspect.signature(SCAN.build_child_env).parameters)
        self.assertNotIn("project_root", params)


# ---------------------------------------------------------------------------
# sca-pip-no-build-exec task0001 AC-1 (FR5; TS-6): pip's flag and arguments
# live in the registry's `target_forms` table. Asserted through this module's
# restricted parser, through the script's loader (both against literals) and
# on the registry text: the header names `target_forms` and keeps its
# ownership phrases, and the npm, cargo and go entry texts are pinned.
# ---------------------------------------------------------------------------

PIP_FORM = {
    "prepared_requirements": {
        "target_flag": "-r",
        "args": ["--no-deps", "--disable-pip", "--format", "json"],
    }
}

NPM_ENTRY_TEXT = "\n".join([
    "  - ecosystem: npm",
    "    manifests: [package.json]",
    "    executable: npm",
    "    # --workspaces=false: npm does not escape to an ancestor workspace root.",
    "    args: [audit, --json, --workspaces=false]",
    "    severity_map: {critical: critical, high: high}",
    "    threshold: {direct_only: true, min_severity: high}",
])
CARGO_ENTRY_TEXT = "\n".join([
    "  - ecosystem: cargo",
    "    manifests: [Cargo.toml]",
    "    executable: cargo-audit",
    "    # cargo-audit runs from a per-group isolation directory outside the",
    "    # reviewed tree, so the reviewed project's `.cargo/audit.toml` is not on",
    "    # its discovery path. The directory holds a copy of Cargo.lock only, and",
    "    # --file (target_flag) points at that copy: scan-dependencies.py puts",
    "    # `--file <copy>` immediately after `audit`. --url and --db are never",
    "    # passed (the advisory DB stays the reviewer's own configuration).",
    "    args: [audit, --json]",
    "    target_flag: --file",
    "    severity_map: {critical: critical, high: high}",
    "    threshold: {direct_only: true, min_severity: high}",
])
GO_ENTRY_TEXT = "\n".join([
    "  - ecosystem: go",
    "    manifests: [go.mod]",
    "    executable: govulncheck",
    "    args: [-json, ./...]",
    "    severity_map: {critical: critical, high: high}",
    "    threshold: {direct_only: true, min_severity: high}",
])
PIP_ENTRY_TEXT = "\n".join([
    "  - ecosystem: pip",
    "    manifests: [pyproject.toml, requirements.txt]",
    "    executable: pip-audit",
    "    target_forms:",
    "      prepared_requirements:",
    "        target_flag: -r",
    "        args: [--no-deps, --disable-pip, --format, json]",
    "    severity_map: {critical: critical, high: high}",
    "    threshold: {direct_only: true, min_severity: high}",
])


def registry_entry_text(text, name):
    """The text of ecosystem `name`'s entry in the registry document, from its
    `- ecosystem:` line up to the next entry (trailing blank lines removed)."""
    start = text.index(f"  - ecosystem: {name}\n")
    following = text.find("\n  - ecosystem:", start + 1)
    block = text[start:] if following == -1 else text[start:following]
    return block.rstrip()


class TestPipTargetFormRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REGISTRY_PATH.read_text(encoding="utf-8")
        cls.parsed = {e["ecosystem"]: e for e in parse_vuln_scanners_yaml(cls.text)}
        cls.loaded = {
            e["ecosystem"]: e for e in SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)["ecosystems"]
        }

    def test_the_restricted_parser_reads_the_nested_form(self):
        pip = self.parsed["pip"]
        self.assertEqual(pip["target_forms"], PIP_FORM)
        self.assertNotIn("args", pip)
        self.assertNotIn("target_flag", pip)

    def test_the_script_loader_reads_the_same_form(self):
        pip = self.loaded["pip"]
        self.assertEqual(pip["target_forms"], PIP_FORM)
        self.assertNotIn("args", pip)
        self.assertNotIn("target_flag", pip)

    def test_the_whole_pip_entry_equals_its_literal_through_the_loader(self):
        self.assertEqual(
            self.loaded["pip"],
            {
                "ecosystem": "pip",
                "manifests": ["pyproject.toml", "requirements.txt"],
                "executable": "pip-audit",
                "target_forms": PIP_FORM,
                "severity_map": {"critical": "critical", "high": "high"},
                "threshold": {"direct_only": True, "min_severity": "high"},
            },
        )

    def test_the_form_table_holds_exactly_one_form(self):
        self.assertEqual(list(self.parsed["pip"]["target_forms"]), ["prepared_requirements"])
        self.assertEqual(list(self.loaded["pip"]["target_forms"]), ["prepared_requirements"])

    def test_the_pip_entry_text_is_a_block_style_nested_mapping(self):
        self.assertEqual(registry_entry_text(self.text, "pip"), PIP_ENTRY_TEXT)

    def test_the_npm_cargo_and_go_entry_texts_equal_their_pinned_literals(self):
        for name, literal in (("npm", NPM_ENTRY_TEXT), ("cargo", CARGO_ENTRY_TEXT), ("go", GO_ENTRY_TEXT)):
            with self.subTest(ecosystem=name):
                self.assertEqual(registry_entry_text(self.text, name), literal)

    def test_the_restricted_parser_can_tell_a_missing_nested_value_apart(self):
        # Regression proof (tdd-testing discipline): the parser must be able
        # to fail on the nested form, not just succeed on it.
        broken = self.text.replace("        target_flag: -r\n", "")
        parsed = {e["ecosystem"]: e for e in parse_vuln_scanners_yaml(broken)}
        self.assertNotEqual(parsed["pip"]["target_forms"], PIP_FORM)
        with self.assertRaises(ValueError):
            parse_vuln_scanners_yaml(self.text.replace("        target_flag: -r\n", "      target_flag: -r\n"))

    def test_the_header_names_target_forms_and_keeps_its_ownership_phrases(self):
        header = self.text.split("\nversion:", 1)[0]
        normalized = re.sub(r"\s+", " ", header.replace("#", "")).lower()
        self.assertIn("target_forms", header)
        self.assertIn("prepared_requirements", header)
        self.assertIn("this registry owns which tool serves each manifest", normalized)
        self.assertIn("scan-dependencies.py owns how to run", normalized)
        self.assertIn("how to normalize", normalized)

    def test_the_header_keeps_the_cargo_sentence_and_drops_the_old_pip_sentence(self):
        header = self.text.split("\nversion:", 1)[0]
        normalized = re.sub(r"\s+", " ", header.replace("#", "")).lower()
        self.assertIn(
            "cargo's come immediately after the leading `audit` subcommand in `args`", normalized
        )
        self.assertNotIn("pip's come first", normalized)


# ---------------------------------------------------------------------------
# sca-pip-no-build-exec task0001 AC-2 (FR5; TS-6): `validate_ecosystem_entry`
# checks the target-form table at planning time; a violation yields
# `<ecosystem>_target_forms_invalid`, no pip plan and no scanner launch.
# ---------------------------------------------------------------------------

class TestTargetFormValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.by_name = {e["ecosystem"]: e for e in registry["ecosystems"]}

    def pip_entry(self):
        return copy.deepcopy(self.by_name["pip"])

    def mutated(self, mutate):
        entry = self.pip_entry()
        mutate(entry)
        return entry

    @staticmethod
    def form(entry):
        return entry["target_forms"]["prepared_requirements"]

    def test_the_shipped_entries_validate(self):
        for name, entry in self.by_name.items():
            with self.subTest(ecosystem=name):
                self.assertIsNone(SCAN.validate_ecosystem_entry(entry))

    def test_each_form_violation_yields_the_fixed_reason(self):
        cases = {
            "no target_forms": lambda e: e.pop("target_forms"),
            "target_forms is None": lambda e: e.update(target_forms=None),
            "target_forms is a string": lambda e: e.update(target_forms="prepared_requirements"),
            "target_forms is a list": lambda e: e.update(target_forms=["prepared_requirements"]),
            "target_forms is empty": lambda e: e.update(target_forms={}),
            "prepared_requirements is missing": lambda e: e.update(
                target_forms={"another_form": copy.deepcopy(PIP_FORM["prepared_requirements"])}
            ),
            "the form is a string": lambda e: e["target_forms"].update(prepared_requirements="-r"),
            "the form is a list": lambda e: e["target_forms"].update(prepared_requirements=["-r"]),
            "the form is None": lambda e: e["target_forms"].update(prepared_requirements=None),
            "target_flag is missing": lambda e: self.form(e).pop("target_flag"),
            "target_flag is empty": lambda e: self.form(e).update(target_flag=""),
            "target_flag is None": lambda e: self.form(e).update(target_flag=None),
            "target_flag is a number": lambda e: self.form(e).update(target_flag=5),
            "target_flag is a list": lambda e: self.form(e).update(target_flag=["-r"]),
            "args is missing": lambda e: self.form(e).pop("args"),
            "args is a string": lambda e: self.form(e).update(args="--no-deps"),
            "args is None": lambda e: self.form(e).update(args=None),
            "args is a mapping": lambda e: self.form(e).update(args={"a": "b"}),
            "an args item is a number": lambda e: self.form(e).update(args=["--no-deps", 5]),
            "an args item is None": lambda e: self.form(e).update(args=[None]),
        }
        for label, mutate in cases.items():
            with self.subTest(case=label):
                self.assertEqual(
                    SCAN.validate_ecosystem_entry(self.mutated(mutate)), "pip_target_forms_invalid"
                )

    def test_a_token_with_a_shell_metacharacter_is_rejected_in_the_flag_and_in_every_arg(self):
        for token in (
            "-r;rm", "--a&b", "--a|b", "--a`b`", "--$HOME", "--a>b", "--a<b", "--a\nb", "--a\rb",
        ):
            with self.subTest(token=token, where="target_flag"):
                entry = self.mutated(lambda e: self.form(e).update(target_flag=token))
                self.assertEqual(SCAN.validate_ecosystem_entry(entry), "pip_target_forms_invalid")
            with self.subTest(token=token, where="args"):
                entry = self.mutated(lambda e: self.form(e).update(args=["--no-deps", token]))
                self.assertEqual(SCAN.validate_ecosystem_entry(entry), "pip_target_forms_invalid")

    def test_a_token_starting_with_a_path_separator_is_rejected(self):
        for token in ("/bin/sh", "/tmp/x", os.sep + "x"):
            with self.subTest(token=token, where="target_flag"):
                entry = self.mutated(lambda e: self.form(e).update(target_flag=token))
                self.assertEqual(SCAN.validate_ecosystem_entry(entry), "pip_target_forms_invalid")
            with self.subTest(token=token, where="args"):
                entry = self.mutated(lambda e: self.form(e).update(args=[token]))
                self.assertEqual(SCAN.validate_ecosystem_entry(entry), "pip_target_forms_invalid")

    def test_a_well_formed_variation_still_validates(self):
        entry = self.mutated(
            lambda e: e["target_forms"].update(
                prepared_requirements={"target_flag": "--requirement-file", "args": []},
                another_form={"target_flag": "-x", "args": ["--y", "z"]},
            )
        )
        self.assertIsNone(SCAN.validate_ecosystem_entry(entry))

    def test_the_old_top_level_shape_is_not_a_valid_pip_entry(self):
        old = {k: v for k, v in self.pip_entry().items() if k != "target_forms"}
        old["args"] = ["--format", "json"]
        old["target_flag"] = "-r"
        self.assertEqual(SCAN.validate_ecosystem_entry(old), "pip_target_forms_invalid")

    def test_the_checks_that_exist_keep_their_order_and_reasons(self):
        # Each earlier check wins over a broken target_forms table.
        broken = {"target_forms": None}
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "bogus", "executable": "x", **broken}),
            "bogus_ecosystem_not_allowlisted",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "pip", "executable": "", **broken}),
            "pip_executable_invalid",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "pip", "executable": "/x/pip-audit", **broken}),
            "pip_executable_invalid",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "pip", "executable": "pip", **broken}),
            "pip_executable_not_allowlisted",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry(
                {"ecosystem": "pip", "executable": "pip-audit", "args": "x", **broken}
            ),
            "pip_args_invalid",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry(
                {"ecosystem": "pip", "executable": "pip-audit", "args": ["a;b"], **broken}
            ),
            "pip_args_invalid",
        )

    def test_the_other_ecosystems_keep_their_validation_reasons(self):
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "npm", "executable": "npm", "args": ["a;b"]}),
            "npm_args_invalid",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "cargo", "executable": "cargo"}),
            "cargo_executable_not_allowlisted",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "go", "executable": "/x/govulncheck"}),
            "go_executable_invalid",
        )
        self.assertEqual(
            SCAN.validate_ecosystem_entry({"ecosystem": "go", "executable": "govulncheck", "args": ["/x"]}),
            "go_args_invalid",
        )

    def test_an_entry_that_carries_target_forms_is_checked_for_any_ecosystem(self):
        for name in ("npm", "cargo", "go"):
            entry = copy.deepcopy(self.by_name[name])
            entry["target_forms"] = {}
            with self.subTest(ecosystem=name):
                self.assertEqual(
                    SCAN.validate_ecosystem_entry(entry), f"{name}_target_forms_invalid"
                )

    def test_an_npm_cargo_or_go_entry_needs_no_target_forms(self):
        for name in ("npm", "cargo", "go"):
            self.assertNotIn("target_forms", self.by_name[name])
            self.assertIsNone(SCAN.validate_ecosystem_entry(self.by_name[name]))


class TestAnInvalidPipFormStartsNoScanner(unittest.TestCase):
    """With a registry whose pip form is invalid, planning gives the fixed
    reason once and no plan, and `run_scan` starts no scanner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.base = base
        self.root = base / "project"
        self.bin_dir = base / "bin"
        self.root.mkdir()
        self.bin_dir.mkdir()
        self.marker = base / "launched.txt"
        stub = self.bin_dir / "pip-audit"
        stub.write_text(
            f"#!{sys.executable}\nopen({str(self.marker)!r}, 'a').write('launched')\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        (self.root / "requirements.txt").write_text("django==3.2.0\n", encoding="utf-8")
        (self.root / "svc").mkdir()
        (self.root / "svc" / "requirements.txt").write_text("django==3.2.0\n", encoding="utf-8")

    def registry_with(self, pip_block):
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        text = text.replace(PIP_ENTRY_TEXT, pip_block)
        self.assertIn(pip_block, text)
        path = self.base / "registry.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    INVALID_BLOCKS = {
        "the old top-level shape": "\n".join([
            "  - ecosystem: pip",
            "    manifests: [pyproject.toml, requirements.txt]",
            "    executable: pip-audit",
            "    args: [--format, json]",
            "    target_flag: -r",
            "    severity_map: {critical: critical, high: high}",
            "    threshold: {direct_only: true, min_severity: high}",
        ]),
        "a missing prepared_requirements form": PIP_ENTRY_TEXT.replace(
            "prepared_requirements:", "another_form:"
        ),
        "an empty target_flag": PIP_ENTRY_TEXT.replace("target_flag: -r", "target_flag: ''"),
        "an absolute target_flag": PIP_ENTRY_TEXT.replace("target_flag: -r", "target_flag: /bin/sh"),
        "a shell metacharacter in args": PIP_ENTRY_TEXT.replace("--disable-pip", "'--disable-pip;id'"),
        "a non-list args": PIP_ENTRY_TEXT.replace(
            "args: [--no-deps, --disable-pip, --format, json]", "args: --no-deps"
        ),
    }

    def test_planning_gives_the_reason_once_and_no_plan(self):
        for label, block in self.INVALID_BLOCKS.items():
            with self.subTest(case=label):
                registry = SCAN.load_registry(self.registry_with(block))
                with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
                    plans, reasons = SCAN.build_scan_jobs(
                        registry, ["requirements.txt", "svc/requirements.txt", "pyproject.toml"], self.root
                    )
                self.assertEqual(plans, [])
                self.assertEqual(reasons, ["pip_target_forms_invalid"])

    def test_run_scan_reports_the_reason_and_starts_no_scanner(self):
        for label, block in self.INVALID_BLOCKS.items():
            with self.subTest(case=label):
                registry_path = self.registry_with(block)
                with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
                    result = SCAN.run_scan(
                        self.root, ["requirements.txt", "svc/requirements.txt"], registry_path
                    )
                self.assertTrue(result["skipped"], result)
                self.assertEqual(result["skip_reason"], "pip_target_forms_invalid")
                self.assertEqual(result["findings"], [])
                self.assertEqual(result["summary"], "Scan skipped: pip_target_forms_invalid")
                self.assertFalse(self.marker.exists(), "a scanner was started")

    def test_the_shipped_registry_does_launch_the_scanner(self):
        # Control for the two tests above: the same fixture, with the valid
        # registry, starts the scanner (so the stub and the PATH work).
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
            SCAN.run_scan(self.root, ["requirements.txt"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertTrue(self.marker.exists())


# ---------------------------------------------------------------------------
# sca-python-lockfile-audit task0001 AC-2 (NFR6): the executable allowlist, the
# lockfile sets and the pip child-environment pins hold their previous values
# -- asserted against literals. (The pip registry entry itself moved to the
# per-target-form table; see TestPipTargetFormRegistry.)
# ---------------------------------------------------------------------------

class TestPipInvariantsUnchanged(unittest.TestCase):
    def test_allowed_executables_are_unchanged(self):
        self.assertEqual(
            SCAN.ALLOWED_EXECUTABLES,
            {
                "npm": {"npm"},
                "cargo": {"cargo-audit"},
                "pip": {"pip-audit"},
                "go": {"govulncheck"},
            },
        )

    def test_ecosystem_lockfiles_are_unchanged(self):
        self.assertEqual(
            SCAN.ECOSYSTEM_LOCKFILES,
            {
                "npm": {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"},
                "cargo": {"Cargo.lock"},
                "pip": {"poetry.lock", "Pipfile.lock"},
                "go": {"go.sum"},
            },
        )

    def test_pip_child_environment_pins_are_unchanged(self):
        self.assertEqual(
            SCAN.ECOSYSTEM_ENV_PINS["pip"],
            {"PIP_CONFIG_FILE": os.devnull, "PIP_INDEX_URL": "https://pypi.org/simple/"},
        )
        env = SCAN.build_child_env({"ecosystem": "pip"}, environ={"PATH": "/bin", "PIP_INDEX_URL": "http://evil/"})
        self.assertEqual(env["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(env["PIP_INDEX_URL"], "https://pypi.org/simple/")


if __name__ == "__main__":
    unittest.main()
