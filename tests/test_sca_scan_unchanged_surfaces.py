"""Tests for sca-scanner-project-config-isolation task0002: the scan surfaces
the isolation change must not alter, and the axis 2 text that documents the
new npm / cargo execution location.

Covers the task's Acceptance Criteria
(feature-docs/sca-scanner-project-config-isolation/tasks/task0002.md):

- AC-1 (FR10): pip and go jobs made through `run_scan` -- argv and cwd equal
  literal values pinned from the behavior before the isolation change, and
  the environment each scanner receives is the runner's environment
  restricted to the pass-through keys, with that ecosystem's existing pins
  applied, nothing added and nothing missing.
- AC-2 (FR10, FR11): `ECOSYSTEM_ENV_PINS` equals a literal snapshot of its
  content before the isolation change, for every ecosystem key.
- AC-3 (FR11): the npm, cargo, pip and go child processes each receive the
  runner's HOME unchanged.
- AC-4 (FR11, FR13): the axis 2 section of review-phase.md states the
  per-group isolation directory as the npm / cargo cwd, cargo-audit's
  `--file` (no `--url` / `--db`), the isolation failure tokens with no in-tree
  fallback and the trusted configuration scope, and no longer says that npm /
  cargo run in the reviewed project's own directory. The tests check the
  presence of the tokens and phrases; the wording is reviewed by inspection.
- AC-5 (NFR4): this module imports only the standard library and needs no
  network and no real scanner. That `python3 -m unittest discover -s tests`
  and `python3 em-workflow/scripts/check-plugin-invariants.py .` pass is
  verified by running both commands; a suite cannot assert its own
  full-suite outcome.

Design constraint (IMPLEMENTATION.md D2): these are characterization tests.
They hold both before and after the isolation change merges, so no assertion
depends on the npm / cargo cwd or on the cargo argv -- the two things that
change is allowed to alter. The recorded npm / cargo-audit launches are used
for their HOME only.

Harness: this module owns its stubs (IMPLEMENTATION.md Conventions). Each
scanner is an executable stub on a PATH that holds only the stub directory.
On every launch it appends its argv, working directory and the environment it
was started with to a record file and prints a well-formed clean result for
its ecosystem. The record path is written into the stub itself: the runner
builds each child's environment explicitly, so a variable set by the test
would never reach the child. The temp parent is a test-owned directory next
to the project tree, so assertions stay valid once npm / cargo run from an
isolation directory. Every environment variable and the process-wide temp
directory setting the tests change are restored. The script under test is
loaded by file path (scan-dependencies.py is not a package).
"""

import ast
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
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"
REVIEW_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"


def _load_script(name="scan_dependencies_unchanged_surfaces"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

# ---------------------------------------------------------------------------
# Literal values pinned from the behavior before the isolation change.
# ---------------------------------------------------------------------------

# ECOSYSTEM_ENV_PINS as it stood before the change, every ecosystem key.
# `os.devnull` is the platform's null device, which is what the pin means.
PRE_CHANGE_ENV_PINS = {
    "npm": {
        "npm_config_registry": "https://registry.npmjs.org/",
        "npm_config_userconfig": os.devnull,
    },
    "cargo": {},
    "pip": {
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_INDEX_URL": "https://pypi.org/simple/",
    },
    "go": {
        "GOENV": "off",
        "GOWORK": "off",
        "GOFLAGS": "-mod=readonly",
        "GOPROXY": "https://proxy.golang.org,direct",
    },
}

# The runner keys that reach a child process; every other runner variable is
# left out.
PASS_THROUGH_KEYS = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE")

CLEAN_PAYLOADS = {
    "npm": {"vulnerabilities": {}},
    "cargo-audit": {"vulnerabilities": {"found": False, "list": []}},
    "pip-audit": {"dependencies": []},
    "govulncheck": {"vulns": []},
}

PYPROJECT_DJANGO = (
    '[tool.poetry]\nname = "demo"\nversion = "0.1.0"\n\n'
    '[tool.poetry.dependencies]\npython = "^3.9"\ndjango = ">=3.2"\n'
)
POETRY_LOCK_DJANGO = (
    "[[package]]\n"
    'name = "django"\n'
    'version = "3.2.0"\n'
    'description = "demo package"\n'
    "optional = false\n"
    'python-versions = ">=3.8"\n'
    'files = [{file = "demo-1.0.tar.gz", hash = "sha256:deadbeefdeadbeef"}]\n'
    "\n"
    '[metadata]\nlock-version = "2.0"\ncontent-hash = "abc"\n'
)

_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

CONFIG = json.loads(__CONFIG__)


def launch_environment():
    # The environment exactly as the scanner runner handed it over. The
    # interpreter may add variables of its own while starting up (a locale
    # coercion variable), so /proc is read where it exists.
    try:
        with open("/proc/self/environ", "rb") as handle:
            raw = handle.read()
    except OSError:
        return dict(os.environ)
    env = {}
    for item in raw.split(b"\\0"):
        if item:
            key, _, value = item.partition(b"=")
            env[os.fsdecode(key)] = os.fsdecode(value)
    return env


with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({
        "tool": CONFIG["tool"],
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "env": launch_environment(),
    }) + "\\n")
sys.stdout.write(CONFIG["payload"])
sys.exit(0)
'''


def write_recording_stub(bin_dir, name, record_path, payload):
    """An executable `name` in `bin_dir`: on every launch it appends its tool
    name, argument vector, working directory and launch environment to
    `record_path`, prints `payload` as JSON and exits 0. The shebang is the
    absolute interpreter because PATH holds the stub directory only."""
    config = {"tool": name, "record": str(record_path), "payload": json.dumps(payload)}
    source = _STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / name
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


# ---------------------------------------------------------------------------
# Shared fixture: a project root, a stub-only PATH, a record file, a temp
# parent next to the project and a reviewer HOME -- all inside one temporary
# tree.
# ---------------------------------------------------------------------------


class ScanHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.bin_dir = self.base / "bin"
        self.records_dir = self.base / "records"
        self.temp_parent = self.base / "tmp"
        self.home = self.base / "reviewer-home"
        for directory in (
            self.root, self.bin_dir, self.records_dir, self.temp_parent, self.home
        ):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"

    # -- fixtures ---------------------------------------------------------

    def write(self, rel, data="{}\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def npm_project(self):
        self.write("package.json")
        self.write("package-lock.json")

    def cargo_project(self):
        self.write("Cargo.toml", "[dependencies]\n")
        self.write("Cargo.lock", "# lock\n")

    def go_project(self, rel_dir=""):
        prefix = f"{rel_dir}/" if rel_dir else ""
        self.write(f"{prefix}go.mod", "module example.invalid/demo\n")

    def install(self, name):
        return write_recording_stub(
            self.bin_dir, name, self.record_path, CLEAN_PAYLOADS[name]
        )

    def real(self, rel=""):
        return str((self.root / rel).resolve()) if rel else str(self.root.resolve())

    # -- the runner's environment and what a child must receive ------------

    def runner_environment(self):
        """The environment `run_scan` runs in: every pass-through key with a
        distinct value, plus variables that must never reach a child -- some
        of them for the very settings the ecosystem pins fix, to show that
        the pin wins."""
        environment = {
            "PATH": str(self.bin_dir),
            "HOME": str(self.home),
            "TMPDIR": str(self.temp_parent),
            "TEMP": str(self.temp_parent),
            "TMP": str(self.temp_parent),
            "SYSTEMROOT": "/nonexistent/systemroot",
            "USERPROFILE": str(self.home),
        }
        environment.update({
            "NPM_TOKEN": "decoy-token",
            "HTTPS_PROXY": "http://decoy.invalid:3128",
            "npm_config_registry": "https://decoy.invalid/",
            "PIP_INDEX_URL": "https://decoy.invalid/simple/",
            "GOFLAGS": "-mod=mod",
            "GOPROXY": "https://decoy.invalid",
        })
        return environment

    def expected_env(self, ecosystem):
        """The literal environment a child of `ecosystem` must receive: the
        runner's pass-through keys as they are, then the pre-change pins."""
        environment = self.runner_environment()
        expected = {key: environment[key] for key in PASS_THROUGH_KEYS}
        expected.update(PRE_CHANGE_ENV_PINS[ecosystem])
        return expected

    # -- running ----------------------------------------------------------

    def scan(self, changed_files):
        with mock.patch.dict(os.environ, self.runner_environment(), clear=True), \
                mock.patch.object(tempfile, "tempdir", str(self.temp_parent)):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def launches(self):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def only_launch(self, tool):
        calls = [call for call in self.launches() if call["tool"] == tool]
        self.assertEqual(len(calls), 1, f"expected one {tool} launch, got {calls}")
        return calls[0]


# ---------------------------------------------------------------------------
# AC-1 (FR10): pip and go jobs -- argv, cwd and environment.
# ---------------------------------------------------------------------------


class TestAC1GoJobIsUnchanged(ScanHarness):
    def test_ac1_go_at_the_root_runs_in_the_project_root_with_its_literal_argv(self):
        self.go_project()
        self.install("govulncheck")
        result = self.scan(["go.mod"])
        self.assertFalse(result["skipped"], result)
        call = self.only_launch("govulncheck")
        self.assertEqual(call["argv"], ["-json", "./..."])
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_go_in_a_nested_project_runs_in_that_directory(self):
        self.go_project("services/api")
        self.install("govulncheck")
        result = self.scan(["services/api/go.mod"])
        self.assertFalse(result["skipped"], result)
        call = self.only_launch("govulncheck")
        self.assertEqual(call["argv"], ["-json", "./..."])
        self.assertEqual(call["cwd"], self.real("services/api"))

    def test_ac1_go_environment_is_the_runners_with_the_existing_go_pins(self):
        self.go_project()
        self.install("govulncheck")
        self.scan(["go.mod"])
        call = self.only_launch("govulncheck")
        self.assertEqual(call["env"], self.expected_env("go"))


class TestAC1PipJobIsUnchanged(ScanHarness):
    def test_ac1_pip_requirements_file_runs_in_the_project_root_with_its_literal_argv(self):
        self.write("req/requirements.txt", "django==3.2.0\n")
        self.install("pip-audit")
        result = self.scan(["req/requirements.txt"])
        self.assertFalse(result["skipped"], result)
        call = self.only_launch("pip-audit")
        self.assertEqual(call["argv"], ["-r", "req/requirements.txt", "--format", "json"])
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_pip_requirements_file_at_the_root(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.install("pip-audit")
        self.scan(["requirements.txt"])
        call = self.only_launch("pip-audit")
        self.assertEqual(call["argv"], ["-r", "requirements.txt", "--format", "json"])
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_pip_pyproject_audits_its_directory_as_a_bare_target(self):
        self.write("lock/pyproject.toml", PYPROJECT_DJANGO)
        self.install("pip-audit")
        self.scan(["lock/pyproject.toml"])
        call = self.only_launch("pip-audit")
        self.assertEqual(call["argv"], ["lock", "--format", "json"])
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_pip_pyproject_at_the_root_audits_the_current_directory(self):
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install("pip-audit")
        self.scan(["pyproject.toml"])
        call = self.only_launch("pip-audit")
        self.assertEqual(call["argv"], [".", "--format", "json"])
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_pip_lockfile_audits_a_prepared_file_from_the_project_root(self):
        self.write("lock/pyproject.toml", PYPROJECT_DJANGO)
        self.write("lock/poetry.lock", POETRY_LOCK_DJANGO)
        self.install("pip-audit")
        result = self.scan(["lock/poetry.lock"])
        self.assertFalse(result["skipped"], result)
        call = self.only_launch("pip-audit")
        argv = call["argv"]
        self.assertEqual(len(argv), 6, argv)
        self.assertEqual(argv[0], "-r")
        self.assertEqual(argv[2:], ["--no-deps", "--disable-pip", "--format", "json"])
        prepared = Path(argv[1])
        self.assertEqual(prepared.parent, self.temp_parent)
        self.assertRegex(prepared.name, r"^pip-lockfile-.+\.txt$")
        self.assertFalse(prepared.exists(), "the prepared file was left behind")
        self.assertEqual(call["cwd"], self.real())

    def test_ac1_pip_environment_is_the_runners_with_the_existing_pip_pins(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.install("pip-audit")
        self.scan(["requirements.txt"])
        call = self.only_launch("pip-audit")
        self.assertEqual(call["env"], self.expected_env("pip"))

    def test_ac1_pip_lockfile_environment_is_the_runners_with_the_existing_pip_pins(self):
        self.write("lock/pyproject.toml", PYPROJECT_DJANGO)
        self.write("lock/poetry.lock", POETRY_LOCK_DJANGO)
        self.install("pip-audit")
        self.scan(["lock/poetry.lock"])
        call = self.only_launch("pip-audit")
        self.assertEqual(call["env"], self.expected_env("pip"))


# ---------------------------------------------------------------------------
# AC-2 (FR10, FR11): ECOSYSTEM_ENV_PINS.
# ---------------------------------------------------------------------------


class TestAC2EnvPinsKeepEveryEcosystemValue(unittest.TestCase):
    def test_ac2_pins_equal_the_literal_snapshot(self):
        self.assertEqual(SCAN.ECOSYSTEM_ENV_PINS, PRE_CHANGE_ENV_PINS)

    def test_ac2_no_ecosystem_key_is_added_or_removed(self):
        self.assertEqual(
            sorted(SCAN.ECOSYSTEM_ENV_PINS), sorted(PRE_CHANGE_ENV_PINS)
        )

    def test_ac2_each_ecosystem_keeps_exactly_its_own_variables_and_values(self):
        for ecosystem, pins in PRE_CHANGE_ENV_PINS.items():
            with self.subTest(ecosystem=ecosystem):
                self.assertEqual(SCAN.ECOSYSTEM_ENV_PINS[ecosystem], pins)

    def test_ac2_the_child_environment_is_the_pass_through_keys_plus_the_pins(self):
        runner = {key: f"runner-{key}" for key in PASS_THROUGH_KEYS}
        runner.update({"NPM_TOKEN": "decoy", "GOFLAGS": "-mod=mod"})
        for ecosystem, pins in PRE_CHANGE_ENV_PINS.items():
            with self.subTest(ecosystem=ecosystem):
                expected = {key: f"runner-{key}" for key in PASS_THROUGH_KEYS}
                expected.update(pins)
                self.assertEqual(
                    SCAN.build_child_env({"ecosystem": ecosystem}, runner), expected
                )


# ---------------------------------------------------------------------------
# AC-3 (FR11): HOME reaches every child as the runner has it.
# ---------------------------------------------------------------------------


class TestAC3HomeIsPassedThrough(ScanHarness):
    def test_ac3_each_child_receives_the_runners_home(self):
        self.npm_project()
        self.cargo_project()
        self.go_project()
        self.write("requirements.txt", "django==3.2.0\n")
        for tool in ("npm", "cargo-audit", "pip-audit", "govulncheck"):
            self.install(tool)
        result = self.scan(["package.json", "Cargo.toml", "requirements.txt", "go.mod"])
        self.assertFalse(result["skipped"], result)
        calls = self.launches()
        self.assertEqual(
            sorted(call["tool"] for call in calls),
            ["cargo-audit", "govulncheck", "npm", "pip-audit"],
        )
        for call in calls:
            with self.subTest(tool=call["tool"]):
                self.assertEqual(call["env"]["HOME"], str(self.home))

    def test_ac3_the_child_home_is_not_one_of_the_ecosystem_pins(self):
        for ecosystem, pins in PRE_CHANGE_ENV_PINS.items():
            with self.subTest(ecosystem=ecosystem):
                self.assertNotIn("HOME", pins)

    def test_ac3_build_child_env_passes_home_through_for_every_ecosystem(self):
        for ecosystem in PRE_CHANGE_ENV_PINS:
            with self.subTest(ecosystem=ecosystem):
                env = SCAN.build_child_env({"ecosystem": ecosystem}, {"HOME": "/reviewer/home"})
                self.assertEqual(env["HOME"], "/reviewer/home")


# ---------------------------------------------------------------------------
# AC-4 (FR11, FR13): the axis 2 section of review-phase.md.
# ---------------------------------------------------------------------------

AXIS2_START = "**Axis 2 (`vulnerability`"
AXIS2_END = "### Contributor-tier pre-dispatch criteria"


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _axis2_section():
    """The axis 2 section of Phase R2, whitespace-normalized: from the axis 2
    marker to the next section heading."""
    text = REVIEW_PHASE_PATH.read_text(encoding="utf-8")
    start = text.index(AXIS2_START)
    end = text.index(AXIS2_END, start)
    return _norm(text[start:end])


class TestAC4Axis2DocumentsTheIsolationDirectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _axis2_section()

    def assertStated(self, phrase):
        # A short message: assertIn would print the whole section.
        if phrase not in self.section:
            self.fail(f"the axis 2 section does not contain {phrase!r}")

    def test_ac4_both_isolation_tokens_and_the_file_flag_appear(self):
        for token in ("npm_isolation_failed", "cargo_isolation_failed", "--file"):
            with self.subTest(token=token):
                self.assertStated(token)

    def test_ac4a_the_isolation_directory_outside_the_reviewed_tree_is_the_npm_cargo_cwd(self):
        for phrase in (
            "per-group isolation directory",
            "outside the reviewed tree",
            "working directory",
            "copies",
            "selected anchor",
            "`package.json`",
            "`npm-shrinkwrap.json`",
            "`package-lock.json`",
            "`Cargo.lock`",
        ):
            with self.subTest(phrase=phrase):
                self.assertStated(phrase)

    def test_ac4b_cargo_audit_receives_the_copy_via_file_with_no_url_or_db(self):
        for phrase in ("`--file`", "no `--url`", "no `--db`"):
            with self.subTest(phrase=phrase):
                self.assertStated(phrase)

    def test_ac4c_failure_is_not_completed_with_no_in_tree_fallback_and_other_groups_continue(self):
        for phrase in (
            "`not_completed`",
            "`npm_isolation_failed`",
            "`cargo_isolation_failed`",
            "falls back to the reviewed tree",
            "other groups continue",
        ):
            with self.subTest(phrase=phrase):
                self.assertStated(phrase)

    def test_ac4d_the_trusted_configuration_scope_is_stated(self):
        for phrase in (
            "HOME",
            "globalconfig",
            "`audit.toml`",
            "advisory DB",
            "managed by the reviewer",
            "cannot be changed by the PR author",
        ):
            with self.subTest(phrase=phrase):
                self.assertStated(phrase)

    def test_ac4_no_statement_that_npm_or_cargo_run_in_the_reviewed_projects_directory(self):
        forbidden = (
            r"project root as (the |its )?(cwd|working directory)",
            r"(cwd|working directory)[^.]*\bis (the )?(reviewed )?project root",
            r"(npm|cargo)[^.]*\b(runs?|scanned) (inside|in|from) (the |its )?"
            r"(own |reviewed )?project (root|directory)",
            r"in its own directory",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.section, re.IGNORECASE))


# ---------------------------------------------------------------------------
# AC-5 (NFR4): standard library only.
# ---------------------------------------------------------------------------


class TestAC5OwnModuleStdlibOnly(unittest.TestCase):
    def test_ac5_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
