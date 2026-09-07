"""Tests for task0008 (review-sca-axis rework round 1): scan-job
construction, trusted-binary resolution, and configuration isolation in
`scan-dependencies.py`.

Covers task0008 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0008.md):

- AC-1: for a changed requirements file the constructed pip job's argument
  vector audits THAT file; for a changed pyproject.toml it audits THAT
  project's directory; in neither case does the vector contain an install
  or write-resolution form, and in neither case does the audited target
  default to the ambient environment.
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

import importlib.util
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
    spec.loader.exec_module(module)
    return module


SCAN = _load_module()


# ---------------------------------------------------------------------------
# Module-local restricted-subset YAML parser (Test Notes: "the registry is
# read with the module-local restricted YAML parser convention this
# repository's test modules already use, not with a third-party import").
# Deliberately scoped to just what AC-2 needs: `ecosystem` and `executable`.
# ---------------------------------------------------------------------------

def parse_vuln_scanners_yaml(text):
    """Restricted-subset parser for vuln-scanners.yaml's `ecosystems:` list.
    Returns a list of per-ecosystem dicts (string values only). Raises
    ValueError if no top-level `ecosystems:` key is found or a line inside
    the block violates the expected nesting."""
    lines = text.splitlines()
    ecosystems = []
    in_block = False
    saw_block = False
    current = None

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
            continue

        if current is None:
            raise ValueError(f"attribute line before any ecosystem: {raw!r}")
        if indent != 4:
            raise ValueError(f"unexpected indentation: {raw!r}")

        key, sep, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not sep:
            raise ValueError(f"malformed line: {raw!r}")
        if not (value.startswith("[") or value.startswith("{")):
            current[key] = value

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
        job = SCAN.build_scan_job(self.by_name["cargo"], "Cargo.toml", "/proj", "/usr/local/bin/cargo-audit")
        self.assertEqual(job["argv"], ["/usr/local/bin/cargo-audit", "audit", "--json"])

    def test_npm_job_argv_unaffected_by_this_task(self):
        job = SCAN.build_scan_job(self.by_name["npm"], "package.json", "/proj", "/usr/local/bin/npm")
        self.assertEqual(job["argv"], ["/usr/local/bin/npm", "audit", "--json"])

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
                job = SCAN.build_scan_job(self.by_name[name], manifest, "/proj", executable)
                self.assertTrue(os.path.isabs(job["argv"][0]))
                self.assertEqual(job["argv"][0], executable)

    def test_job_carries_ecosystem_manifest_cwd_and_env(self):
        job = SCAN.build_scan_job(self.by_name["npm"], "package.json", "/proj", "/x/npm")
        self.assertEqual(job["ecosystem"], "npm")
        self.assertEqual(job["manifest"], "package.json")
        self.assertEqual(job["cwd"], "/proj")
        self.assertIsInstance(job["env"], dict)

    def test_constructing_a_job_launches_nothing(self):
        # Purity check: an executable path that does not exist on disk at
        # all is accepted without error -- build_scan_job never resolves
        # or invokes it.
        job = SCAN.build_scan_job(
            self.by_name["npm"], "package.json", "/proj", "/definitely/not/a/real/path/npm"
        )
        self.assertEqual(job["argv"][0], "/definitely/not/a/real/path/npm")


# ---------------------------------------------------------------------------
# AC-1 (TS-26): the pip job audits the REVIEWED PROJECT, never the ambient
# environment.
# ---------------------------------------------------------------------------

class TestPipJobAuditsTheReviewedProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.pip_entry = {e["ecosystem"]: e for e in registry["ecosystems"]}["pip"]

    def test_requirements_file_is_itself_the_audited_target(self):
        job = SCAN.build_scan_job(self.pip_entry, "requirements.txt", "/proj", "/x/pip-audit")
        self.assertEqual(job["argv"], ["/x/pip-audit", "-r", "requirements.txt", "--format", "json"])

    def test_nested_requirements_file_path_is_preserved_verbatim(self):
        job = SCAN.build_scan_job(self.pip_entry, "backend/requirements.txt", "/proj", "/x/pip-audit")
        self.assertIn("backend/requirements.txt", job["argv"])
        self.assertEqual(job["argv"][1], "-r")

    def test_pyproject_toml_at_project_root_audits_the_current_directory(self):
        job = SCAN.build_scan_job(self.pip_entry, "pyproject.toml", "/proj", "/x/pip-audit")
        self.assertEqual(job["argv"], ["/x/pip-audit", ".", "--format", "json"])

    def test_pyproject_toml_in_a_subdirectory_audits_that_directory(self):
        job = SCAN.build_scan_job(self.pip_entry, "services/api/pyproject.toml", "/proj", "/x/pip-audit")
        self.assertEqual(job["argv"], ["/x/pip-audit", "services/api", "--format", "json"])

    def test_a_changed_lockfile_audits_its_own_directory_not_pyproject_via_r(self):
        # poetry.lock / Pipfile.lock are not pip-format requirement files;
        # -r would misparse them, so they get the directory-targeting form
        # too, same as pyproject.toml.
        job = SCAN.build_scan_job(self.pip_entry, "poetry.lock", "/proj", "/x/pip-audit")
        self.assertEqual(job["argv"], ["/x/pip-audit", ".", "--format", "json"])

    def test_target_is_never_absent_never_the_ambient_environment(self):
        for manifest in ("requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"):
            with self.subTest(manifest=manifest):
                job = SCAN.build_scan_job(self.pip_entry, manifest, "/proj", "/x/pip-audit")
                # More than the bare `[executable, --format, json]` form:
                # a real target token is present.
                self.assertGreater(len(job["argv"]), 3)

    def test_no_argument_form_installs_or_writes_a_resolution_artifact(self):
        forbidden_tokens = ("install", "--fix", "-o", "--output", "--require-hashes", "--no-deps")
        for manifest in ("requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"):
            job = SCAN.build_scan_job(self.pip_entry, manifest, "/proj", "/x/pip-audit")
            with self.subTest(manifest=manifest):
                for forbidden in forbidden_tokens:
                    self.assertNotIn(forbidden, job["argv"])


# ---------------------------------------------------------------------------
# AC-3 (TS-26/TS-4): the trusted binary absent from PATH -> machine-stable
# skip, no job, no alternative command form.
# ---------------------------------------------------------------------------

class TestUnresolvableBinaryYieldsSkipNoJob(unittest.TestCase):
    def test_missing_cargo_audit_yields_skip_reason_and_no_job(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            empty_bin = Path(tmp) / "empty-bin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}, clear=False):
                jobs, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(jobs, [])
        self.assertEqual(skip_reasons, ["cargo_tool_not_found"])

    def test_present_binary_yields_exactly_one_job_with_absolute_path(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "cargo-audit"
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                jobs, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(skip_reasons, [])
        self.assertEqual(len(jobs), 1)
        self.assertTrue(os.path.isabs(jobs[0]["argv"][0]))
        self.assertEqual(jobs[0]["argv"][1], "audit")

    def test_no_job_is_built_for_the_ecosystem_with_no_resolvable_binary(self):
        # Two ecosystems selected; only npm's stub is present. cargo
        # contributes a skip reason and no job -- npm still gets one, and
        # no alternative command form is attempted for cargo.
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "npm"
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                jobs, skip_reasons = SCAN.build_scan_jobs(
                    registry, ["package.json", "Cargo.toml"], Path(tmp) / "proj"
                )
        self.assertEqual(skip_reasons, ["cargo_tool_not_found"])
        self.assertEqual([j["ecosystem"] for j in jobs], ["npm"])


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
                self.by_name["cargo"], "Cargo.toml", clean_root, "/usr/local/bin/cargo-audit"
            )
            hostile_job = SCAN.build_scan_job(
                self.by_name["cargo"], "Cargo.toml", hostile_root, "/usr/local/bin/cargo-audit"
            )

        self.assertEqual(clean_job["argv"][0], hostile_job["argv"][0])
        self.assertEqual(clean_job["argv"], hostile_job["argv"])
        self.assertEqual(clean_job["env"], hostile_job["env"])

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
                self.by_name["npm"], "package.json", clean_root, "/usr/local/bin/npm"
            )
            hostile_job = SCAN.build_scan_job(
                self.by_name["npm"], "package.json", hostile_root, "/usr/local/bin/npm"
            )

        self.assertEqual(clean_job["argv"], hostile_job["argv"])
        self.assertEqual(clean_job["env"], hostile_job["env"])
        self.assertEqual(hostile_job["env"].get("npm_config_registry"), "https://registry.npmjs.org/")
        self.assertNotEqual(hostile_job["env"].get("npm_config_registry"), "http://evil.example.com/")

    def test_child_env_never_reads_a_file_inside_the_project(self):
        # build_child_env's signature takes no project_root at all -- a
        # structural guarantee, not just an observed outcome, that it
        # cannot open a file inside the reviewed tree.
        import inspect

        params = list(inspect.signature(SCAN.build_child_env).parameters)
        self.assertNotIn("project_root", params)


if __name__ == "__main__":
    unittest.main()
