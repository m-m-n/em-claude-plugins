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

sca-python-lockfile-audit task0001 AC-2 (FR3, NFR2, NFR6, TM-5) extends AC-1
for a changed poetry.lock / Pipfile.lock: the pip job is built for a PREPARED
requirements file -- [executable, `-r`, prepared file, `--no-deps`,
`--disable-pip`, `--format`, `json`] with the lockfile as the job's manifest --
without reading, writing or launching anything; a lockfile manifest without a
prepared file is rejected and never yields the directory form; requirements.txt
and pyproject.toml jobs keep their previous vectors with neither new flag; and
the registry pip entry, ALLOWED_EXECUTABLES, ECOSYSTEM_LOCKFILES and the pip
child-environment pins hold their previous (literal) values.

sca-scanner-project-config-isolation task0001 updates the npm / cargo job
expectations to the isolation contract: an npm / cargo job is built from the
prepared isolation paths of its group (`prepared_inputs`), its cwd is the
isolation directory, and cargo's argument vector carries the registry-declared
`--file <copy>` right after `audit`. The configuration-isolation cases (AC-4)
keep proving that hostile project files change nothing about the job.

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

    # sca-python-lockfile-audit task0001 AC-2 (FR3, NFR2, NFR6, TM-5): a
    # lockfile is never handed to pip-audit directly nor audited through its
    # directory. The lockfile job audits a PREPARED requirements file (one
    # `name==version` line per pin) that a separate stage wrote outside the
    # project root; build_scan_job only receives that file's path.
    PREPARED = "/tmp/prepared-requirements.txt"
    LOCKFILE_JOB_ARGV_TAIL = ["--no-deps", "--disable-pip", "--format", "json"]

    def _build(self, manifest):
        prepared = self.PREPARED if os.path.basename(manifest) in ("poetry.lock", "Pipfile.lock") else None
        return SCAN.build_scan_job(
            self.pip_entry, manifest, "/proj", "/x/pip-audit", prepared_file=prepared
        )

    def test_a_changed_lockfile_gets_the_lockfile_job_form(self):
        for lockfile in ("poetry.lock", "Pipfile.lock", "services/api/poetry.lock", "svc/Pipfile.lock"):
            with self.subTest(lockfile=lockfile):
                job = SCAN.build_scan_job(
                    self.pip_entry, lockfile, "/proj", "/x/pip-audit", prepared_file=self.PREPARED
                )
                self.assertEqual(
                    job["argv"],
                    ["/x/pip-audit", "-r", self.PREPARED] + self.LOCKFILE_JOB_ARGV_TAIL,
                )
                self.assertEqual(job["manifest"], lockfile)
                self.assertEqual(job["ecosystem"], "pip")
                self.assertEqual(job["cwd"], "/proj")

    def test_lockfile_job_is_built_even_when_the_prepared_path_does_not_exist(self):
        missing = "/definitely/not/a/real/dir/prepared-requirements.txt"
        with mock.patch("builtins.open", side_effect=AssertionError("file opened")), \
                mock.patch("os.open", side_effect=AssertionError("file opened")), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("process launched")), \
                mock.patch("subprocess.run", side_effect=AssertionError("process launched")):
            job = SCAN.build_scan_job(
                self.pip_entry, "poetry.lock", "/proj", "/x/pip-audit", prepared_file=missing
            )
        self.assertEqual(job["argv"][:3], ["/x/pip-audit", "-r", missing])
        self.assertFalse(os.path.exists(missing))

    def test_a_lockfile_manifest_without_a_prepared_file_is_rejected(self):
        for lockfile in ("poetry.lock", "Pipfile.lock", "sub/poetry.lock"):
            for kwargs in ({}, {"prepared_file": None}, {"prepared_file": ""}):
                with self.subTest(lockfile=lockfile, kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        SCAN.build_scan_job(
                            self.pip_entry, lockfile, "/proj", "/x/pip-audit", **kwargs
                        )

    def test_the_directory_form_is_never_produced_for_a_lockfile(self):
        for lockfile in ("poetry.lock", "Pipfile.lock"):
            with self.subTest(lockfile=lockfile):
                with self.assertRaises(ValueError):
                    SCAN._pip_target(lockfile)

    def test_non_lockfile_jobs_ignore_a_prepared_file_and_carry_neither_flag(self):
        for manifest in ("requirements.txt", "pyproject.toml", "backend/requirements.txt"):
            with self.subTest(manifest=manifest):
                with_file = SCAN.build_scan_job(
                    self.pip_entry, manifest, "/proj", "/x/pip-audit", prepared_file=self.PREPARED
                )
                without = SCAN.build_scan_job(self.pip_entry, manifest, "/proj", "/x/pip-audit")
                self.assertEqual(with_file["argv"], without["argv"])
                self.assertNotIn("--no-deps", without["argv"])
                self.assertNotIn("--disable-pip", without["argv"])

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

    def test_no_deps_and_disable_pip_appear_only_on_lockfile_jobs(self):
        for manifest in ("requirements.txt", "pyproject.toml"):
            job = self._build(manifest)
            with self.subTest(manifest=manifest, kind="non-lockfile"):
                self.assertNotIn("--no-deps", job["argv"])
                self.assertNotIn("--disable-pip", job["argv"])
        for manifest in ("poetry.lock", "Pipfile.lock"):
            job = self._build(manifest)
            with self.subTest(manifest=manifest, kind="lockfile"):
                self.assertIn("--no-deps", job["argv"])
                self.assertIn("--disable-pip", job["argv"])


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
                    registry, ["Cargo.toml"], Path(tmp) / "proj",
                    prepared_inputs={"Cargo.toml": _prepared("cargo")},
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
                    registry, ["Cargo.toml"], Path(tmp) / "proj",
                    prepared_inputs={"Cargo.toml": _prepared("cargo")},
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
                    registry, ["package.json", "Cargo.toml"], Path(tmp) / "proj",
                    prepared_inputs={
                        "package.json": _prepared("npm"),
                        "Cargo.toml": _prepared("cargo"),
                    },
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
# sca-python-lockfile-audit task0001 AC-2 (NFR6): the pip registry entry, the
# executable allowlist, the lockfile sets and the pip child-environment pins
# hold their previous values -- asserted against literals.
# ---------------------------------------------------------------------------

class TestPipInvariantsUnchanged(unittest.TestCase):
    def test_pip_registry_entry_is_unchanged(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        pip_entry = {e["ecosystem"]: e for e in registry["ecosystems"]}["pip"]
        self.assertEqual(
            pip_entry,
            {
                "ecosystem": "pip",
                "manifests": ["pyproject.toml", "requirements.txt"],
                "executable": "pip-audit",
                "args": ["--format", "json"],
                "target_flag": "-r",
                "severity_map": {"critical": "critical", "high": "high"},
                "threshold": {"direct_only": True, "min_severity": "high"},
            },
        )

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
