"""Tests for sca-absolute-executable-path task0001: absolute-only executable
resolution for scan jobs.

Covers the task's Acceptance Criteria
(feature-docs/sca-absolute-executable-path/tasks/task0001.md):

- AC-1 (FR1, TM-1): with relative and empty PATH entries ahead of an absolute
  stub directory, every entry holding an executable `npm`, resolution returns
  the absolute entry joined with the name, exactly as written.
- AC-2 (FR1): with PATH removed, resolution searches the default search path
  (`os.defpath`, read at call time) and still skips its relative and empty
  entries.
- AC-3 (FR1, FR2, TM-1): with only relative / empty / `~` entries on PATH,
  resolution returns none and planning reports `npm_tool_not_found` once, with
  no plan.
- AC-4 (FR1): among several absolute entries, a directory or a non-executable
  file named like the scanner is passed over.
- AC-5 (FR3, TM-1): the attack scenario through `run_scan` launches the
  recording stub by its absolute path and neither planted file.
- AC-6 (FR3): every scan job (nested go, root go, pip, npm, cargo) is
  launched by the absolute path that resolution returns, whatever the job's
  working directory.
- AC-7 (FR5): the `resolve_executable` docstring, the Scan job construction
  section comment and the `build_scan_jobs` docstring each state the
  absolute-only rule and the existing not-found reason (the wording is
  reviewed by inspection; the tests check the statements are present).
- AC-8 (NFR1, NFR2, NFR3): the script adds no import beyond the standard
  library (its one existing non-standard import is the guarded PyYAML import
  of the registry loader) and this module imports only the standard
  library. That `python3 -m unittest discover -s tests` passes and
  that no existing test file is modified is verified by running the command
  and by the diff; a suite cannot assert its own full-suite outcome.

Cross-task independence (IMPLEMENTATION.md Conventions): the tests never
assert the child environment's PATH, so they hold whether or not the sibling
child-PATH change is merged.

Harness: this module owns its stubs and fixtures and imports nothing from
another test module. A scan runs on an explicit PATH; the recording stub
writes its tool name, the path it was launched through (its own argv[0] as
the interpreter sees it), argv and cwd to a record file whose path is written
into the stub itself. The planted files write a marker file at an absolute
path outside the scanned tree. Relative PATH entries resolve against the
process cwd, so tests that need one change into a temporary directory and
restore the cwd; every environment variable, module attribute and the
process-wide temp directory setting a test changes is restored. The script
under test is loaded by file path (scan-dependencies.py is not a package).
"""

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script(name="scan_dependencies_absolute_executable_resolution"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

CLEAN_PAYLOADS = {
    "npm": {"vulnerabilities": {}},
    "cargo-audit": {"vulnerabilities": {"found": False, "list": []}},
    "pip-audit": {"dependencies": []},
    "govulncheck": {"config": {"protocol_version": "v1.0.0", "scanner_name": "govulncheck"}},
}

_RECORDING_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

CONFIG = json.loads(__CONFIG__)

with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({
        "tool": CONFIG["tool"],
        "launch_path": sys.argv[0],
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
    }) + "\\n")
sys.stdout.write(CONFIG["payload"])
sys.exit(0)
'''

_MARKER_STUB_SOURCE = '''#!__PYTHON__
import sys

with open(__MARKER__, "a", encoding="utf-8") as handle:
    handle.write("launched\\n")
sys.exit(0)
'''


def write_recording_stub(bin_dir, name, record_path, payload):
    """An executable `name` in `bin_dir`: on every launch it appends its tool
    name, the path it was launched through, its argument vector and working
    directory to `record_path`, prints `payload` as JSON and exits 0. The
    shebang is the absolute interpreter because PATH holds no system
    directory."""
    config = {"tool": name, "record": str(record_path), "payload": json.dumps(payload)}
    source = _RECORDING_STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def write_marker_stub(path, marker_path):
    """An executable at `path` that, when launched, leaves a marker file at the
    absolute path `marker_path` (outside every scanned tree) and exits 0."""
    source = _MARKER_STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__MARKER__", repr(str(marker_path))
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def write_executable(path):
    """An executable file at `path`; resolution only inspects the mode, so the
    content is irrelevant."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


# ---------------------------------------------------------------------------
# Shared fixture: a project root, a stub directory, a record file, a marker
# directory, a temp parent next to the project, a reviewer HOME and a scratch
# working directory -- all inside one temporary tree.
# ---------------------------------------------------------------------------


class ResolutionHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.bin_dir = self.base / "bin"
        self.records_dir = self.base / "records"
        self.markers_dir = self.base / "markers"
        self.temp_parent = self.base / "tmp"
        self.home = self.base / "reviewer-home"
        self.workdir = self.base / "workdir"
        for directory in (
            self.root, self.bin_dir, self.records_dir, self.markers_dir,
            self.temp_parent, self.home, self.workdir,
        ):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"

    # -- process state a test changes, restored on cleanup -----------------

    def chdir(self, directory):
        """Changes the process cwd for the rest of the test and restores it
        before the temporary tree is removed (cleanups run last-in first-out,
        and this one is registered after the tree's)."""
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        os.chdir(directory)

    def patch_environ(self):
        """Snapshots os.environ; the test then edits it freely and the
        snapshot is restored on cleanup."""
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_path(self, value):
        self.patch_environ()
        os.environ["PATH"] = value

    def unset_path(self):
        self.patch_environ()
        os.environ.pop("PATH", None)

    # -- fixtures ---------------------------------------------------------

    def write(self, rel, data="{}\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def npm_project(self, rel_dir=""):
        prefix = f"{rel_dir}/" if rel_dir else ""
        self.write(f"{prefix}package.json")
        self.write(f"{prefix}package-lock.json")

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

    def marker(self, label):
        return self.markers_dir / label

    # -- running ----------------------------------------------------------

    def runner_environment(self, path_value):
        """The environment `run_scan` runs in: the given PATH, the reviewer
        HOME and the temp-directory variables."""
        return {
            "PATH": path_value,
            "HOME": str(self.home),
            "TMPDIR": str(self.temp_parent),
            "TEMP": str(self.temp_parent),
            "TMP": str(self.temp_parent),
        }

    def scan(self, changed_files, path_value):
        with mock.patch.dict(os.environ, self.runner_environment(path_value), clear=True), \
                mock.patch.object(tempfile, "tempdir", str(self.temp_parent)):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def resolve_under(self, path_value, name):
        """What `resolve_executable` returns under the PATH `path_value`."""
        with mock.patch.dict(os.environ, {"PATH": path_value}):
            return SCAN.resolve_executable(name)

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
# AC-1 (FR1, TM-1): absolute entry wins over relative and empty entries.
# ---------------------------------------------------------------------------


class TestAC1AbsoluteEntryWins(ResolutionHarness):
    def _plant_relative_npm(self):
        """An executable `npm` under every relative spelling the PATH below
        uses, resolved against the process cwd (the empty entry and `.` both
        mean the cwd itself)."""
        self.chdir(self.workdir)
        for rel in ("tools/npm", "node_modules/.bin/npm", "npm"):
            write_executable(self.workdir / rel)

    def test_ac1_resolution_returns_the_absolute_entry_joined_with_the_name(self):
        self._plant_relative_npm()
        write_executable(self.bin_dir / "npm")
        entries = ["tools", "./node_modules/.bin", ".", "", str(self.bin_dir)]
        self.set_path(os.pathsep.join(entries))
        resolved = SCAN.resolve_executable("npm")
        self.assertEqual(resolved, os.path.join(str(self.bin_dir), "npm"))

    def test_ac1_the_result_is_absolute_and_not_under_any_relative_entry(self):
        self._plant_relative_npm()
        write_executable(self.bin_dir / "npm")
        entries = ["tools", "./node_modules/.bin", ".", "", str(self.bin_dir)]
        self.set_path(os.pathsep.join(entries))
        resolved = SCAN.resolve_executable("npm")
        self.assertTrue(os.path.isabs(resolved), resolved)
        for relative in ("tools", "./node_modules/.bin", "."):
            self.assertFalse(
                resolved.startswith(relative + os.sep) or resolved == relative,
                f"{resolved} is under the relative entry {relative!r}",
            )

    def test_ac1_the_entry_is_joined_as_written_with_no_normalization(self):
        self._plant_relative_npm()
        write_executable(self.bin_dir / "npm")
        # A spelling that normalization would change: a `..` component.
        spelled = f"{self.bin_dir}{os.sep}..{os.sep}{self.bin_dir.name}"
        entries = ["tools", ".", "", spelled]
        self.set_path(os.pathsep.join(entries))
        resolved = SCAN.resolve_executable("npm")
        self.assertEqual(resolved, os.path.join(spelled, "npm"))

    def test_ac1_the_first_absolute_entry_in_original_order_wins(self):
        self._plant_relative_npm()
        second = self.base / "second-bin"
        write_executable(self.bin_dir / "npm")
        write_executable(second / "npm")
        self.set_path(os.pathsep.join(["tools", str(second), str(self.bin_dir)]))
        self.assertEqual(SCAN.resolve_executable("npm"), os.path.join(str(second), "npm"))


# ---------------------------------------------------------------------------
# AC-2 (FR1): PATH unset -> the default search path, read at call time.
# ---------------------------------------------------------------------------


class TestAC2DefaultSearchPath(ResolutionHarness):
    def test_ac2_with_path_unset_the_substituted_default_search_path_is_searched(self):
        self.chdir(self.workdir)
        for rel in ("tools/npm", "npm"):
            write_executable(self.workdir / rel)
        write_executable(self.bin_dir / "npm")
        self.unset_path()
        default = os.pathsep.join(["tools", "", ".", str(self.bin_dir)])
        with mock.patch.object(os, "defpath", default):
            resolved = SCAN.resolve_executable("npm")
        self.assertEqual(resolved, os.path.join(str(self.bin_dir), "npm"))

    def test_ac2_a_default_search_path_with_only_relative_entries_finds_nothing(self):
        self.chdir(self.workdir)
        for rel in ("tools/npm", "npm"):
            write_executable(self.workdir / rel)
        self.unset_path()
        default = os.pathsep.join(["tools", "", "."])
        with mock.patch.object(os, "defpath", default):
            self.assertIsNone(SCAN.resolve_executable("npm"))

    def test_ac2_an_empty_path_counts_as_present_and_yields_no_entries(self):
        write_executable(self.bin_dir / "npm")
        self.set_path("")
        with mock.patch.object(os, "defpath", str(self.bin_dir)):
            self.assertIsNone(SCAN.resolve_executable("npm"))


# ---------------------------------------------------------------------------
# AC-3 (FR1, FR2, TM-1): found only under relative / empty entries -> not
# found, with the existing skip reason.
# ---------------------------------------------------------------------------


class TestAC3OnlyRelativeEntries(ResolutionHarness):
    RELATIVE_ENTRIES = ["tools", "./node_modules/.bin", ".", "", "~/bin"]

    def _plant_relative_npm(self):
        self.chdir(self.workdir)
        # `.` and the empty entry both mean the cwd; `~/bin` is a literal
        # directory named `~` -- nothing expands it.
        for rel in ("tools/npm", "node_modules/.bin/npm", "npm", "~/bin/npm"):
            write_executable(self.workdir / rel)

    def test_ac3_resolution_returns_none(self):
        self._plant_relative_npm()
        self.set_path(os.pathsep.join(self.RELATIVE_ENTRIES))
        self.assertIsNone(SCAN.resolve_executable("npm"))

    def test_ac3_planning_reports_the_existing_tool_not_found_reason_once(self):
        self._plant_relative_npm()
        self.npm_project()
        self.set_path(os.pathsep.join(self.RELATIVE_ENTRIES))
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        plans, reasons = SCAN.build_scan_jobs(
            registry, ["package.json", "package-lock.json"], self.root
        )
        self.assertEqual(plans, [])
        self.assertEqual(reasons, ["npm_tool_not_found"])


# ---------------------------------------------------------------------------
# AC-4 (FR1): the executable test is unchanged -- a directory and a
# non-executable file are passed over.
# ---------------------------------------------------------------------------


class TestAC4ExecutableTest(ResolutionHarness):
    def test_ac4_a_directory_and_a_non_executable_file_are_passed_over(self):
        directory_entry = self.base / "bin-directory"
        plain_entry = self.base / "bin-plain-file"
        later_entry = self.base / "bin-later"
        (directory_entry / "npm").mkdir(parents=True)
        plain_entry.mkdir()
        plain_file = plain_entry / "npm"
        plain_file.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        plain_file.chmod(0o644)
        write_executable(later_entry / "npm")
        write_executable(self.bin_dir / "npm")
        self.set_path(os.pathsep.join(
            [str(directory_entry), str(plain_entry), str(later_entry), str(self.bin_dir)]
        ))
        self.assertEqual(SCAN.resolve_executable("npm"), os.path.join(str(later_entry), "npm"))

    def test_ac4_an_absent_name_in_every_absolute_entry_returns_none(self):
        empty_entry = self.base / "bin-empty"
        empty_entry.mkdir()
        self.set_path(os.pathsep.join([str(empty_entry), str(self.bin_dir)]))
        self.assertIsNone(SCAN.resolve_executable("npm"))


# ---------------------------------------------------------------------------
# AC-5 (FR3, TM-1): the attack scenario through run_scan.
# ---------------------------------------------------------------------------


class TestAC5AttackScenario(ResolutionHarness):
    def _path_with_relative_tools(self):
        return os.pathsep.join(["tools", str(self.bin_dir)])

    def test_ac5_npm_is_launched_by_the_stubs_absolute_path_and_no_planted_file_runs(self):
        self.npm_project("services/api")
        self.install("npm")
        write_marker_stub(self.root / "services/api/tools/npm", self.marker("api-tools-npm"))
        write_marker_stub(self.root / "tools/npm", self.marker("cwd-tools-npm"))
        self.chdir(self.root)
        result = self.scan(
            ["services/api/package.json", "services/api/package-lock.json"],
            self._path_with_relative_tools(),
        )
        self.assertFalse(self.marker("api-tools-npm").exists())
        self.assertFalse(self.marker("cwd-tools-npm").exists())
        call = self.only_launch("npm")
        self.assertEqual(call["launch_path"], os.path.join(str(self.bin_dir), "npm"))
        self.assertFalse(result["skipped"], result)

    def test_ac5_go_in_the_attacked_directory_never_runs_the_planted_file(self):
        # The same attack against a job whose cwd is the attacker's own
        # directory: before the change, a relative `tools/govulncheck` found
        # through the process cwd was launched from `services/api` -- and
        # resolved to the planted file there.
        self.go_project("services/api")
        self.install("govulncheck")
        write_marker_stub(
            self.root / "services/api/tools/govulncheck", self.marker("api-tools-go")
        )
        write_marker_stub(self.root / "tools/govulncheck", self.marker("cwd-tools-go"))
        self.chdir(self.root)
        result = self.scan(["services/api/go.mod"], self._path_with_relative_tools())
        self.assertFalse(self.marker("api-tools-go").exists())
        self.assertFalse(self.marker("cwd-tools-go").exists())
        call = self.only_launch("govulncheck")
        self.assertEqual(call["launch_path"], os.path.join(str(self.bin_dir), "govulncheck"))
        self.assertEqual(call["cwd"], str((self.root / "services/api").resolve()))
        self.assertFalse(result["skipped"], result)


# ---------------------------------------------------------------------------
# AC-6 (FR3): every launch path is the absolute path resolution returns,
# whatever the job's cwd.
# ---------------------------------------------------------------------------


class TestAC6LaunchPathIsTheResolvedAbsolutePath(ResolutionHarness):
    EXECUTABLES = ("npm", "cargo-audit", "pip-audit", "govulncheck")

    def setUp(self):
        super().setUp()
        # A relative `tools` entry ahead of the stub directory, with a planted
        # executable of every scanner's name under it in the process cwd.
        self.path_value = os.pathsep.join(["tools", str(self.bin_dir)])
        for name in self.EXECUTABLES:
            write_marker_stub(self.root / "tools" / name, self.marker(f"cwd-tools-{name}"))
        self.chdir(self.root)

    def _assert_launched_by_the_resolved_absolute_path(self, tool):
        call = self.only_launch(tool)
        resolved = self.resolve_under(self.path_value, tool)
        self.assertEqual(resolved, os.path.join(str(self.bin_dir), tool))
        self.assertTrue(os.path.isabs(call["launch_path"]), call)
        self.assertEqual(call["launch_path"], resolved)
        for name in self.EXECUTABLES:
            self.assertFalse(self.marker(f"cwd-tools-{name}").exists(), name)
        return call

    def test_ac6_a_nested_go_project_is_launched_by_the_absolute_path(self):
        self.go_project("services/api")
        self.install("govulncheck")
        result = self.scan(["services/api/go.mod"], self.path_value)
        call = self._assert_launched_by_the_resolved_absolute_path("govulncheck")
        self.assertEqual(call["cwd"], str((self.root / "services/api").resolve()))
        self.assertFalse(result["skipped"], result)

    def test_ac6_a_root_go_project_is_launched_by_the_absolute_path(self):
        self.go_project()
        self.install("govulncheck")
        result = self.scan(["go.mod"], self.path_value)
        call = self._assert_launched_by_the_resolved_absolute_path("govulncheck")
        self.assertEqual(call["cwd"], str(self.root.resolve()))
        self.assertFalse(result["skipped"], result)

    def test_ac6_a_pip_requirements_file_is_launched_by_the_absolute_path(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.install("pip-audit")
        result = self.scan(["requirements.txt"], self.path_value)
        call = self._assert_launched_by_the_resolved_absolute_path("pip-audit")
        self.assertEqual(call["cwd"], str(self.root.resolve()))
        self.assertFalse(result["skipped"], result)

    def test_ac6_an_npm_project_is_launched_by_the_absolute_path_from_its_isolation_directory(self):
        self.npm_project()
        self.install("npm")
        result = self.scan(["package.json", "package-lock.json"], self.path_value)
        call = self._assert_launched_by_the_resolved_absolute_path("npm")
        self.assertNotEqual(call["cwd"], str(self.root.resolve()))
        self.assertFalse(result["skipped"], result)

    def test_ac6_a_cargo_project_is_launched_by_the_absolute_path_from_its_isolation_directory(self):
        self.cargo_project()
        self.install("cargo-audit")
        result = self.scan(["Cargo.toml", "Cargo.lock"], self.path_value)
        call = self._assert_launched_by_the_resolved_absolute_path("cargo-audit")
        self.assertNotEqual(call["cwd"], str(self.root.resolve()))
        self.assertFalse(result["skipped"], result)


# ---------------------------------------------------------------------------
# AC-7 (FR5): the three explanations state the absolute-only rule and the
# existing not-found reason. The wording itself is reviewed by inspection;
# these tests check the load-bearing statements are present and that none of
# the three describes resolution as a plain PATH lookup.
# ---------------------------------------------------------------------------


def _docstring_of(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return " ".join((ast.get_docstring(node) or "").split())
    raise AssertionError(f"no function {name}")


def _comment_block_containing(lines, marker):
    """The consecutive `#` comment lines around the first line that starts
    with `marker`, joined into one whitespace-normalized string."""
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    first = index
    while first > 0 and lines[first - 1].startswith("#"):
        first -= 1
    last = index
    while last + 1 < len(lines) and lines[last + 1].startswith("#"):
        last += 1
    return " ".join(" ".join(line.lstrip("#") for line in lines[first:last + 1]).split())


class TestAC7ExplanationsStateTheAbsoluteOnlyRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        cls.texts = {
            "resolve_executable docstring": _docstring_of(tree, "resolve_executable"),
            "Scan job construction comment": _comment_block_containing(
                lines, "# Scan job construction"
            ),
            "build_scan_jobs docstring": _docstring_of(tree, "build_scan_jobs"),
        }

    def test_ac7_each_states_that_only_absolute_entries_are_searched(self):
        for label, text in self.texts.items():
            with self.subTest(location=label):
                self.assertRegex(text, r"(?i)\bonly\b[^.]*\babsolute\b")
                self.assertRegex(text, r"(?i)\brelative\b")
                self.assertRegex(text, r"(?i)\bempty\b")

    def test_ac7_each_names_the_default_search_path_for_an_unset_path(self):
        for label, text in self.texts.items():
            with self.subTest(location=label):
                self.assertRegex(text, r"(?i)default search path")
                self.assertRegex(text, r"(?i)\bunset\b")

    def test_ac7_each_names_the_existing_tool_not_found_reason(self):
        for label, text in self.texts.items():
            with self.subTest(location=label):
                self.assertIn("_tool_not_found", text)

    def test_ac7_none_describes_resolution_as_a_plain_path_lookup(self):
        for label, text in self.texts.items():
            with self.subTest(location=label):
                self.assertNotRegex(text, r"(?i)resolves? (its|the) executable on PATH")
                self.assertNotIn("on PATH (resolve_executable)", text)


# ---------------------------------------------------------------------------
# AC-8 (NFR1): standard library only, in the script and in this module.
# ---------------------------------------------------------------------------


def _imported_top_level_modules(source):
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


class TestAC8StandardLibraryOnly(unittest.TestCase):
    def test_ac8_the_script_adds_no_import_beyond_the_standard_library(self):
        # The one non-standard import the script has always carried is the
        # guarded PyYAML import its registry loader needs (`yaml = None` when
        # absent). Resolution adds no import of its own.
        modules = _imported_top_level_modules(SCRIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), ["yaml"])

    def test_ac8_this_module_imports_only_the_standard_library(self):
        modules = _imported_top_level_modules(Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), [])


if __name__ == "__main__":
    unittest.main()
