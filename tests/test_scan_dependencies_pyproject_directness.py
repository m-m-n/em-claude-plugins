"""Tests for sca-directness-resolution task0002: the pip scan units whose
direct names come from pyproject.toml read them with tomllib (any quoting,
extras, markers, direct references; the Poetry dependency tables), mark the
set incomplete wherever a declaration cannot be resolved, and skip explicitly
(`pip_toml_parser_unavailable`) when tomllib is unavailable.

Covers the task's Acceptance Criteria
(feature-docs/sca-directness-resolution/tasks/task0002.md):

- AC-1 (FR3, TS-7): single / double quotes, extras, environment markers and
  `name @ url` direct references give their names; a scan produces a finding
  for a high-severity advisory on each declared package.
- AC-2 (FR3, TS-19): the Poetry tables count (except `python`); optional
  dependencies, dependency groups and Poetry group tables do not.
- AC-3 (FR5, TM-5, TS-8, TS-20): every unresolvable declaration marks the set
  incomplete without skipping the scan unit.
- AC-4 (NFR3, TM-4, TS-25): unexpected shapes never raise; the set is
  incomplete.
- AC-5 (FR6, NFR4, TM-6, TS-15): without tomllib a pyproject.toml unit reports
  `pip_toml_parser_unavailable` and the scanner is not started.
- AC-6 (FR6, TS-24): without tomllib the lockfile tokens are unchanged and a
  requirements-derived unit never reports `pip_toml_parser_unavailable`.
- AC-7 (NFR1, TS-28): standard library only; tomllib only through the existing
  guarded import.

Scanners are never executed: a stand-in `pip-audit` (a Python script with an
absolute-interpreter shebang) sits alone on PATH, records each launch and
prints a pip-audit-shaped payload. The script under test is loaded by file
path (scan-dependencies.py is not a package). Fixture projects live in
temporary directories created by each test. This module's imports are
standard-library only.
"""

import ast
import copy
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script(name="scan_dependencies_pyproject_directness"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

# An advisory description embedding a CVSS v3.1 vector with base score 7.5
# (band: high), so the existing severity rule can determine the severity.
HIGH_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"

PIP_TOML_PARSER_UNAVAILABLE = "pip_toml_parser_unavailable"


# ---------------------------------------------------------------------------
# Stand-in pip-audit and small builders (local to this module).
# ---------------------------------------------------------------------------

_PIP_AUDIT_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

CONFIG = json.loads(__CONFIG__)
with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({"argv": sys.argv, "cwd": os.getcwd()}) + "\\n")
sys.stdout.write(json.dumps(CONFIG["payload"]))
sys.exit(1 if any(dep.get("vulns") for dep in CONFIG["payload"]["dependencies"]) else 0)
'''


def vulnerable(name, version="1.0.0"):
    """A pip-audit dependency entry carrying one high-severity advisory."""
    return {
        "name": name,
        "version": version,
        "vulns": [
            {
                "id": f"PYSEC-{name}",
                "fix_versions": ["9.9.9"],
                "aliases": [],
                "description": f"Advisory for {name}. {HIGH_VECTOR}",
            }
        ],
    }


def write_pip_audit_stub(bin_dir, record_path, dependencies):
    config = {"record": str(record_path), "payload": {"dependencies": dependencies}}
    source = _PIP_AUDIT_STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / "pip-audit"
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def pipfile_lock_text(packages):
    return json.dumps(
        {
            "_meta": {"hash": {"sha256": "abc"}, "pipfile-spec": 6},
            "default": {
                name: {"hashes": ["sha256:deadbeefdeadbeef"], "index": "pypi", "version": f"=={version}"}
                for name, version in packages.items()
            },
            "develop": {},
        },
        indent=2,
    )


def poetry_lock_text(packages):
    blocks = []
    for name, version in packages.items():
        blocks.append(
            "[[package]]\n"
            f'name = "{name}"\n'
            f'version = "{version}"\n'
            'description = "demo package"\n'
            "optional = false\n"
            'python-versions = ">=3.8"\n'
            'files = [{file = "demo-1.0.tar.gz", hash = "sha256:deadbeefdeadbeef"}]'
        )
    return "\n\n".join(blocks) + '\n\n[metadata]\nlock-version = "2.0"\ncontent-hash = "abc"\n'


PYPROJECT_HEADER = '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n\n'


def project_table(body):
    """A pyproject.toml with a [project] table holding `body` lines."""
    return PYPROJECT_HEADER + '[project]\nname = "demo"\nversion = "0.1.0"\n' + body + "\n"


class ProjectCase(unittest.TestCase):
    """A project root, a stub-only PATH and a record directory (outside the
    project root), all inside one temporary tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.root = base / "project"
        self.bin_dir = base / "bin"
        self.records_dir = base / "records"
        for directory in (self.root, self.bin_dir, self.records_dir):
            directory.mkdir()
        self.record_path = self.records_dir / "pip-audit-calls.jsonl"

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    # -- the resolver ------------------------------------------------------

    def resolve(self, text, rel="pyproject.toml"):
        path = self.write(rel, text)
        return SCAN._pip_pyproject_direct_names(str(path))

    def assertResolved(self, result, names, complete):
        self.assertEqual(set(result), set(names))
        self.assertIs(result.complete, complete)

    # -- the scan ----------------------------------------------------------

    def install_pip_audit(self, dependencies):
        return write_pip_audit_stub(self.bin_dir, self.record_path, dependencies)

    def scan(self, changed_files):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def calls(self):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def assertNotLaunched(self):
        self.assertEqual(self.calls(), [], "pip-audit was launched")

    def assertCompletedWithoutSkip(self, result):
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"], result)


def finding_packages(result):
    return sorted(f["title"].split(":", 1)[0] for f in result["findings"])


# ---------------------------------------------------------------------------
# Shared components: DirectNames and _requirement_name (IMPLEMENTATION.md).
# ---------------------------------------------------------------------------

class TestDirectNamesContract(unittest.TestCase):
    def test_it_reads_like_an_immutable_set_of_the_names(self):
        names = SCAN.DirectNames(["requests", "django"], complete=False)
        self.assertIn("requests", names)
        self.assertNotIn("flask", names)
        self.assertEqual(len(names), 2)
        self.assertEqual(sorted(names), ["django", "requests"])
        self.assertEqual(names, {"requests", "django"})
        self.assertEqual({"requests", "django"}, names)
        self.assertFalse(hasattr(names, "add"))

    def test_complete_is_exposed_read_only(self):
        names = SCAN.DirectNames(["a"], complete=False)
        self.assertIs(names.complete, False)
        self.assertIs(SCAN.DirectNames(["a"]).complete, True)
        with self.assertRaises(AttributeError):
            names.complete = True
        with self.assertRaises(AttributeError):
            names.extra = 1

    def test_names_are_kept_as_written(self):
        self.assertEqual(set(SCAN.DirectNames(["Foo_Bar.baz"])), {"Foo_Bar.baz"})

    def test_a_copy_keeps_completeness(self):
        names = SCAN.DirectNames(["a"], complete=False)
        self.assertIs(copy.copy(names).complete, False)
        self.assertIs(copy.deepcopy(names).complete, False)


class TestRequirementName(unittest.TestCase):
    def test_the_name_as_written_for_each_following_form(self):
        cases = {
            "requests": "requests",
            "requests>=2": "requests",
            "django==3.2.0": "django",
            "Foo_Bar.baz[extra1,extra2]>=1": "Foo_Bar.baz",
            "pkg (>=1.0)": "pkg",
            "pkg(>=1.0)": "pkg",
            "pkg;python_version<'3'": "pkg",
            "pkg ; python_version<'3'": "pkg",
            "pkg @ https://example.com/pkg-1.0.zip": "pkg",
            "pkg@https://example.com/pkg-1.0.zip": "pkg",
            "pkg[extra] @ git+https://example.com/pkg.git": "pkg",
            "pkg~=1.0": "pkg",
            "pkg!=1.0": "pkg",
            "pkg===1.0": "pkg",
            "pkg<2": "pkg",
            "pkg, >=1": "pkg",
            "  pkg  ": "pkg",
            "a": "a",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(SCAN._requirement_name(text), expected)

    def test_no_name_for_a_url_a_local_path_or_an_archive(self):
        for text in (
            "https://example.com/pkg-1.0.zip",
            "git+https://example.com/pkg.git",
            "file:///srv/pkg",
            "./pkg",
            "../pkg",
            "/srv/pkg",
            "~/pkg",
            "dir/pkg",
            "dir\\pkg",
            "pkg-1.0-py3-none-any.whl",
            "pkg-1.0.tar.gz",
            "pkg.zip",
            "pkg-1.0.TAR.GZ",
            "-e .",
            "",
            "   ",
        ):
            with self.subTest(text=text):
                self.assertIsNone(SCAN._requirement_name(text))

    def test_it_never_raises_for_a_non_string(self):
        for value in (None, 5, 1.5, [], {}, b"pkg"):
            with self.subTest(value=value):
                self.assertIsNone(SCAN._requirement_name(value))


# ---------------------------------------------------------------------------
# AC-1 (FR3): names read through tomllib, whatever the quoting.
# ---------------------------------------------------------------------------

class TestPyprojectDirectNames(ProjectCase):
    def test_single_quoted_entries_with_extras_give_requests_and_django(self):
        # AC-1 / TS-7
        result = self.resolve(project_table("dependencies = ['requests[socks]>=2', 'django==3.2.0']"))
        self.assertResolved(result, {"requests", "django"}, True)

    def test_double_quoted_entries_give_the_same_names(self):
        result = self.resolve(project_table('dependencies = ["requests[socks]>=2", "django==3.2.0"]'))
        self.assertResolved(result, {"requests", "django"}, True)

    def test_environment_markers_and_direct_references_yield_their_names(self):
        body = (
            "dependencies = [\n"
            "    \"requests>=2; python_version >= '3.8'\",\n"
            "    'django==3.2.0 ; sys_platform == \"linux\"',\n"
            "    'pkg @ https://example.com/pkg-1.0.zip',\n"
            '    "other[extra] @ git+https://example.com/other.git@v1",\n'
            "    # a comment inside the array\n"
            '    "last",\n'
            "]"
        )
        result = self.resolve(project_table(body))
        self.assertResolved(result, {"requests", "django", "pkg", "other", "last"}, True)

    def test_a_multi_line_literal_string_and_a_trailing_table_are_read(self):
        text = project_table("dependencies = [\n  'a>=1',\n  'b',\n]") + "\n[tool.black]\nline-length = 100\n"
        self.assertResolved(self.resolve(text), {"a", "b"}, True)

    def test_names_are_returned_as_written(self):
        result = self.resolve(project_table("dependencies = ['Django==3.2.0', 'Foo_Bar.baz']"))
        self.assertResolved(result, {"Django", "Foo_Bar.baz"}, True)

    def test_a_static_empty_list_is_a_complete_declaration_of_zero_names(self):
        self.assertResolved(self.resolve(project_table("dependencies = []")), set(), True)

    def test_the_resolver_returns_a_direct_names_value(self):
        result = self.resolve(project_table("dependencies = ['a']"))
        self.assertIsInstance(result, SCAN.DirectNames)

    def test_a_scan_reports_a_finding_for_each_declared_package(self):
        # AC-1 through the scan: a severity-high advisory for requests and one
        # for django each produce a finding (the single-quoted spelling),
        # while a transitive package stays out.
        self.write("pyproject.toml", project_table("dependencies = ['requests[socks]>=2', 'django==3.2.0']"))
        self.install_pip_audit([vulnerable("requests"), vulnerable("django"), vulnerable("urllib3")])
        result = self.scan(["pyproject.toml"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(finding_packages(result), ["django", "requests"])
        self.assertEqual({f["file"] for f in result["findings"]}, {"pyproject.toml"})
        self.assertEqual(len(self.calls()), 1)

    def test_a_scan_in_a_subdirectory_resolves_the_manifest_there(self):
        self.write("svc/pyproject.toml", project_table("dependencies = ['Django==3.2.0']"))
        self.install_pip_audit([vulnerable("django")])
        result = self.scan(["svc/pyproject.toml"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(finding_packages(result), ["django"])


# ---------------------------------------------------------------------------
# AC-2 (FR3): the Poetry tables and the tables that are not declarations.
# ---------------------------------------------------------------------------

class TestPoetryAndNonDeclarationTables(ProjectCase):
    def test_poetry_dependencies_and_dev_dependencies_are_direct_except_python(self):
        text = (
            '[tool.poetry]\nname = "demo"\nversion = "0.1.0"\n\n'
            "[tool.poetry.dependencies]\n"
            'python = "^3.9"\n'
            'django = ">=3.2"\n'
            'requests = {version = "^2", extras = ["socks"]}\n\n'
            "[tool.poetry.dev-dependencies]\n"
            'pytest = "*"\n'
        )
        self.assertResolved(self.resolve(text), {"django", "requests", "pytest"}, True)

    def test_python_is_excluded_however_it_is_spelled(self):
        text = '[tool.poetry.dependencies]\nPython = "^3.9"\ndjango = "*"\n'
        self.assertResolved(self.resolve(text), {"django"}, True)

    def test_a_poetry_table_next_to_a_static_project_list_adds_up(self):
        text = project_table("dependencies = ['a']") + '\n[tool.poetry.dependencies]\npython = "^3.9"\nb = "*"\n'
        self.assertResolved(self.resolve(text), {"a", "b"}, True)

    def test_a_poetry_table_holding_only_python_declares_zero_names_completely(self):
        text = '[tool.poetry.dependencies]\npython = "^3.9"\n'
        self.assertResolved(self.resolve(text), set(), True)

    def test_names_only_in_non_declaration_tables_are_not_direct(self):
        text = (
            project_table(
                "dependencies = ['a']\n\n"
                "[project.optional-dependencies]\n"
                "extra = ['opt-pkg']\n"
            )
            + "\n[dependency-groups]\n"
            "dev = ['group-pkg']\n\n"
            "[tool.poetry.group.test.dependencies]\n"
            'poetry-group-pkg = "*"\n'
        )
        self.assertResolved(self.resolve(text), {"a"}, True)

    def test_a_manifest_declaring_only_non_declaration_tables_is_incomplete(self):
        text = (
            '[project]\nname = "demo"\nversion = "0.1.0"\n\n'
            "[project.optional-dependencies]\n"
            "extra = ['opt-pkg']\n\n"
            "[dependency-groups]\n"
            "dev = ['group-pkg']\n\n"
            "[tool.poetry.group.test.dependencies]\n"
            'poetry-group-pkg = "*"\n'
        )
        self.assertResolved(self.resolve(text), set(), False)

    def test_malformed_non_declaration_tables_never_affect_completeness(self):
        text = (
            project_table("dependencies = ['a']\n\n[project.optional-dependencies]\nextra = 5\n")
            + "\n[dependency-groups]\ndev = 'oops'\n\n"
            "[tool.poetry.group]\ntest = 'oops'\n"
        )
        self.assertResolved(self.resolve(text), {"a"}, True)

    def test_a_scan_does_not_report_a_package_only_in_an_optional_table(self):
        text = project_table("dependencies = ['a']\n\n[project.optional-dependencies]\nextra = ['opt-pkg']\n")
        self.write("pyproject.toml", text)
        self.install_pip_audit([vulnerable("a"), vulnerable("opt-pkg")])
        result = self.scan(["pyproject.toml"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(finding_packages(result), ["a"])


# ---------------------------------------------------------------------------
# AC-3 (FR5, TM-5): an unresolvable declaration marks the set incomplete and
# never skips the scan unit.
# ---------------------------------------------------------------------------

class TestIncompleteSets(ProjectCase):
    def test_dynamic_dependencies_without_a_static_list_are_incomplete(self):
        text = '[project]\nname = "demo"\ndynamic = ["version", "dependencies"]\n'
        self.assertResolved(self.resolve(text), set(), False)

    def test_dynamic_dependencies_keep_the_names_that_were_resolved(self):
        text = (
            '[project]\nname = "demo"\ndynamic = ["dependencies"]\n\n'
            "[tool.poetry.dependencies]\n"
            'python = "^3.9"\n'
            'django = "*"\n'
        )
        self.assertResolved(self.resolve(text), {"django"}, False)

    def test_dynamic_without_dependencies_does_not_make_the_set_incomplete(self):
        text = project_table("dependencies = ['a']\ndynamic = ['readme']")
        self.assertResolved(self.resolve(text), {"a"}, True)

    def test_neither_a_static_list_nor_a_poetry_table_is_incomplete(self):
        for label, text in (
            ("project without dependencies", '[project]\nname = "demo"\nversion = "1"\n'),
            ("only build-system", PYPROJECT_HEADER),
            ("empty manifest", ""),
            ("only another tool", "[tool.black]\nline-length = 100\n"),
        ):
            with self.subTest(label=label):
                self.assertResolved(self.resolve(text), set(), False)

    def test_invalid_toml_is_incomplete(self):
        self.assertResolved(self.resolve("[project\ndependencies = ['a'\n"), set(), False)

    def test_content_that_is_not_utf8_is_incomplete(self):
        path = self.root / "pyproject.toml"
        path.write_bytes(b"[project]\ndependencies = ['a\xff']\n")
        self.assertResolved(SCAN._pip_pyproject_direct_names(str(path)), set(), False)

    def test_a_missing_file_is_incomplete(self):
        result = SCAN._pip_pyproject_direct_names(str(self.root / "absent" / "pyproject.toml"))
        self.assertResolved(result, set(), False)

    def test_an_unresolvable_location_is_incomplete(self):
        self.assertResolved(SCAN._pip_pyproject_direct_names(None), set(), False)

    def test_a_directory_in_place_of_the_manifest_is_incomplete(self):
        (self.root / "pyproject.toml").mkdir()
        self.assertResolved(SCAN._pip_pyproject_direct_names(str(self.root / "pyproject.toml")), set(), False)

    def test_an_unreadable_manifest_is_incomplete(self):
        path = self.write("pyproject.toml", project_table("dependencies = ['a']"))
        path.chmod(0)
        self.addCleanup(path.chmod, stat.S_IRUSR | stat.S_IWUSR)
        if os.access(path, os.R_OK):
            self.skipTest("file permissions are not enforced for this user")
        self.assertResolved(SCAN._pip_pyproject_direct_names(str(path)), set(), False)

    def test_an_item_with_no_name_is_incomplete_and_the_others_are_still_read(self):
        for item in (
            "https://example.com/pkg-1.0.zip",
            "git+https://example.com/pkg.git",
            "./local-pkg",
            "pkg-1.0-py3-none-any.whl",
            "",
        ):
            with self.subTest(item=item):
                result = self.resolve(project_table(f"dependencies = ['a>=1', '{item}', 'b']"))
                self.assertResolved(result, {"a", "b"}, False)

    def _assert_scan_runs_without_skip(self, changed_file="pyproject.toml"):
        self.install_pip_audit([vulnerable("django")])
        result = self.scan([changed_file])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(len(self.calls()), 1, "the scan unit must still launch pip-audit")

    def test_scan_unit_with_dynamic_dependencies_is_not_skipped(self):
        self.write("pyproject.toml", '[project]\nname = "demo"\ndynamic = ["dependencies"]\n')
        self._assert_scan_runs_without_skip()

    def test_scan_unit_without_any_declaration_is_not_skipped(self):
        self.write("pyproject.toml", PYPROJECT_HEADER)
        self._assert_scan_runs_without_skip()

    def test_scan_unit_with_invalid_toml_is_not_skipped(self):
        self.write("pyproject.toml", "[project\n")
        self._assert_scan_runs_without_skip()

    def test_scan_unit_with_an_unreadable_manifest_is_not_skipped(self):
        path = self.write("pyproject.toml", project_table("dependencies = ['a']"))
        path.chmod(0)
        self.addCleanup(path.chmod, stat.S_IRUSR | stat.S_IWUSR)
        if os.access(path, os.R_OK):
            self.skipTest("file permissions are not enforced for this user")
        self._assert_scan_runs_without_skip()

    def test_a_poetry_lock_unit_reads_the_sibling_pyproject_through_the_same_resolver(self):
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.write("pyproject.toml", '[project]\nname = "demo"\ndynamic = ["dependencies"]\n')
        self.assertResolved(SCAN._pip_direct_dependency_names(self.root, "poetry.lock"), set(), False)
        self.write("pyproject.toml", project_table("dependencies = ['Django']"))
        self.assertResolved(SCAN._pip_direct_dependency_names(self.root, "poetry.lock"), {"Django"}, True)

    def test_a_pyproject_outside_the_project_root_is_incomplete(self):
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        outside = self.root.parent / "elsewhere.toml"
        outside.write_text(project_table("dependencies = ['django']"), encoding="utf-8")
        try:
            os.symlink(outside, self.root / "pyproject.toml")
        except OSError:
            self.skipTest("symbolic links cannot be created here")
        result = SCAN._pip_direct_dependency_names(self.root, "poetry.lock")
        self.assertResolved(result, set(), False)


# ---------------------------------------------------------------------------
# AC-4 (NFR3, TM-4): unexpected shapes never raise and are incomplete.
# ---------------------------------------------------------------------------

class TestUnexpectedShapes(ProjectCase):
    SHAPES = {
        "dependencies is a string": project_table("dependencies = 'requests'"),
        "dependencies is a table": project_table("[project.dependencies]\nrequests = '*'"),
        "dependencies is a number": project_table("dependencies = 5"),
        "dynamic is a string": project_table("dependencies = ['a']\ndynamic = 'dependencies'"),
        "dynamic is a table": '[project]\nname = "demo"\n[project.dynamic]\nx = 1\n',
        "poetry dependencies is a string": '[tool.poetry]\nname = "demo"\ndependencies = "oops"\n',
        "poetry dev-dependencies is a string": '[tool.poetry]\nname = "demo"\ndev-dependencies = "oops"\n',
        "project is a string": 'project = "oops"\n',
        "tool is a string": 'tool = "oops"\n' + project_table("dependencies = ['a']"),
        "poetry is a string": '[tool]\npoetry = "oops"\n',
    }

    def test_a_non_string_list_item_is_incomplete_and_the_rest_is_read(self):
        for label, item in (("number", "5"), ("table", "{name = 'x'}"), ("array", "['x']"), ("bool", "true")):
            with self.subTest(item=label):
                result = self.resolve(project_table(f"dependencies = ['a', {item}, 'b']"))
                self.assertResolved(result, {"a", "b"}, False)

    def test_every_unexpected_shape_is_incomplete_without_raising(self):
        for label, text in self.SHAPES.items():
            with self.subTest(shape=label):
                result = self.resolve(text)
                self.assertFalse(result.complete)

    def test_unexpected_shapes_keep_the_names_that_were_resolved(self):
        text = project_table("dependencies = 'requests'") + '\n[tool.poetry.dependencies]\ndjango = "*"\n'
        self.assertResolved(self.resolve(text), {"django"}, False)

    def test_a_malformed_poetry_table_next_to_a_static_list_makes_the_set_incomplete(self):
        text = project_table("dependencies = ['a']") + '\n[tool.poetry]\ndev-dependencies = "oops"\n'
        self.assertResolved(self.resolve(text), {"a"}, False)

    def test_a_scan_returns_normally_for_each_unexpected_shape(self):
        for label, text in self.SHAPES.items():
            with self.subTest(shape=label):
                self.write("pyproject.toml", text)
                self.install_pip_audit([vulnerable("django")])
                result = self.scan(["pyproject.toml"])
                self.assertEqual(result["findings"], [])
                self.assertIn("summary", result)

    def test_a_scan_returns_normally_for_a_non_string_item(self):
        self.write("pyproject.toml", project_table("dependencies = ['django', 5]"))
        self.install_pip_audit([vulnerable("django")])
        result = self.scan(["pyproject.toml"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(finding_packages(result), ["django"])


# ---------------------------------------------------------------------------
# AC-5 (FR6, NFR4, TM-6): the explicit skip without tomllib.
# ---------------------------------------------------------------------------

class TestTomlParserUnavailable(ProjectCase):
    def test_a_pyproject_unit_is_skipped_with_the_fixed_token_and_pip_audit_is_not_started(self):
        self.write("pyproject.toml", project_table("dependencies = ['django']"))
        self.install_pip_audit([vulnerable("django")])
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["pyproject.toml"])
        self.assertTrue(result["skipped"], result)
        self.assertEqual(result["skip_reason"], PIP_TOML_PARSER_UNAVAILABLE)
        self.assertEqual(result["source"], "tool")
        self.assertEqual(result["findings"], [])
        self.assertNotLaunched()

    def test_the_summary_names_only_fixed_tokens(self):
        self.write("svc/pyproject.toml", project_table("dependencies = ['secret-package-name']"))
        self.install_pip_audit([vulnerable("secret-package-name")])
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["svc/pyproject.toml"])
        self.assertEqual(result["skip_reason"], PIP_TOML_PARSER_UNAVAILABLE)
        self.assertIn(PIP_TOML_PARSER_UNAVAILABLE, result["summary"])
        for text in (result["summary"], result["skip_reason"]):
            self.assertNotIn("svc", text)
            self.assertNotIn("secret-package-name", text)
            self.assertNotIn(str(self.root), text)

    def test_a_requirements_unit_in_the_same_scan_completes(self):
        self.write("svc/pyproject.toml", project_table("dependencies = ['django']"))
        self.write("tools/requirements.txt", "django==3.2.0\n")
        self.install_pip_audit([vulnerable("django")])
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["svc/pyproject.toml", "tools/requirements.txt"])
        self.assertTrue(result["skipped"], result)
        self.assertEqual(result["skip_reason"], PIP_TOML_PARSER_UNAVAILABLE)
        calls = self.calls()
        self.assertEqual(len(calls), 1, calls)
        self.assertIn("-r", calls[0]["argv"])
        self.assertIn("tools/requirements.txt", calls[0]["argv"])
        self.assertNotIn("svc", calls[0]["argv"])
        # The completed unit's finding survives the skip of the other unit.
        self.assertEqual(finding_packages(result), ["django"])
        self.assertTrue(result["summary"].startswith("Scanned pip;"), result["summary"])

    def test_the_skip_follows_the_binding_at_call_time(self):
        # The same module: with the parser the unit completes, and with the
        # binding replaced by None the very next scan skips.
        self.write("pyproject.toml", project_table("dependencies = ['django']"))
        self.install_pip_audit([vulnerable("django")])
        first = self.scan(["pyproject.toml"])
        self.assertCompletedWithoutSkip(first)
        with mock.patch.object(SCAN, "tomllib", None):
            second = self.scan(["pyproject.toml"])
        self.assertEqual(second["skip_reason"], PIP_TOML_PARSER_UNAVAILABLE)
        third = self.scan(["pyproject.toml"])
        self.assertCompletedWithoutSkip(third)
        self.assertEqual(len(self.calls()), 2)

    def test_a_poetry_lock_unit_that_passes_the_lockfile_checks_is_skipped(self):
        # With the real checks a poetry.lock unit never gets past conversion
        # without the parser (AC-6); the lockfile checks are stood in for here
        # so that the unit "passes the existing lockfile checks".
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.write("pyproject.toml", project_table("dependencies = ['django']"))
        self.install_pip_audit([vulnerable("django")])
        with mock.patch.object(SCAN, "tomllib", None), \
                mock.patch.object(SCAN, "convert_pip_lockfile", return_value=([["django==3.2.0"]], 0)), \
                mock.patch.object(SCAN, "pip_declaration_found", return_value=True):
            result = self.scan(["poetry.lock"])
        self.assertTrue(result["skipped"], result)
        self.assertEqual(result["skip_reason"], PIP_TOML_PARSER_UNAVAILABLE)
        self.assertNotLaunched()
        self.assertNotIn("not auditable", result["summary"])

    def test_without_the_skip_condition_the_same_lockfile_unit_launches(self):
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.write("pyproject.toml", project_table("dependencies = ['django']"))
        self.install_pip_audit([vulnerable("django")])
        result = self.scan(["poetry.lock"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(finding_packages(result), ["django"])


# ---------------------------------------------------------------------------
# AC-6 (FR6): the lockfile tokens keep their conditions and run first;
# requirements-derived units never take the skip.
# ---------------------------------------------------------------------------

class TestLockfileTokensWithoutTomllib(ProjectCase):
    def scan_without_tomllib(self, changed_files):
        with mock.patch.object(SCAN, "tomllib", None):
            return self.scan(changed_files)

    def test_an_unconvertible_poetry_lock_keeps_its_token(self):
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.write("pyproject.toml", project_table("dependencies = ['django']"))
        self.install_pip_audit([vulnerable("django")])
        result = self.scan_without_tomllib(["poetry.lock"])
        self.assertEqual(result["skip_reason"], "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_an_unconvertible_pipfile_lock_keeps_its_token(self):
        self.write("Pipfile.lock", "not json")
        self.write("Pipfile", '[packages]\ndjango = "*"\n')
        self.install_pip_audit([vulnerable("django")])
        result = self.scan_without_tomllib(["Pipfile.lock"])
        self.assertEqual(result["skip_reason"], "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_a_toml_declaration_that_cannot_be_read_without_the_parser_keeps_its_token(self):
        self.write("Pipfile.lock", pipfile_lock_text({"django": "3.2.0"}))
        self.write("Pipfile", '[packages]\ndjango = "*"\n')
        self.install_pip_audit([vulnerable("django")])
        result = self.scan_without_tomllib(["Pipfile.lock"])
        self.assertEqual(result["skip_reason"], "pip_direct_manifest_not_found")
        self.assertNotLaunched()

    def test_a_missing_declaration_keeps_its_token_with_the_parser(self):
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.install_pip_audit([vulnerable("django")])
        result = self.scan(["poetry.lock"])
        self.assertEqual(result["skip_reason"], "pip_direct_manifest_not_found")
        self.assertNotLaunched()

    def test_the_lockfile_checks_run_before_the_parser_skip(self):
        # tomllib unavailable AND the checks fail: the lockfile tokens win.
        self.write("poetry.lock", poetry_lock_text({"django": "3.2.0"}))
        self.install_pip_audit([vulnerable("django")])
        with mock.patch.object(SCAN, "convert_pip_lockfile", return_value=None):
            result = self.scan_without_tomllib(["poetry.lock"])
        self.assertEqual(result["skip_reason"], "pip_lockfile_unconvertible")
        with mock.patch.object(SCAN, "convert_pip_lockfile", return_value=([["django==3.2.0"]], 0)), \
                mock.patch.object(SCAN, "pip_declaration_found", return_value=False):
            result = self.scan_without_tomllib(["poetry.lock"])
        self.assertEqual(result["skip_reason"], "pip_direct_manifest_not_found")
        self.assertNotLaunched()

    def test_a_pipfile_lock_unit_never_reports_the_parser_skip(self):
        # Its direct names come from a Pipfile, not from pyproject.toml.
        self.write("Pipfile.lock", pipfile_lock_text({"django": "3.2.0"}))
        self.install_pip_audit([vulnerable("django")])
        with mock.patch.object(SCAN, "convert_pip_lockfile", return_value=([["django==3.2.0"]], 0)), \
                mock.patch.object(SCAN, "pip_declaration_found", return_value=True):
            result = self.scan_without_tomllib(["Pipfile.lock"])
        self.assertNotIn(PIP_TOML_PARSER_UNAVAILABLE, result["skip_reason"] or "")
        self.assertEqual(len(self.calls()), 1)

    def test_a_requirements_unit_never_reports_the_parser_skip(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.install_pip_audit([vulnerable("django")])
        result = self.scan_without_tomllib(["requirements.txt"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(finding_packages(result), ["django"])

    def test_requirements_units_in_subdirectories_never_report_the_parser_skip(self):
        self.write("a/requirements.txt", "django==3.2.0\n")
        self.write("b/requirements.txt", "requests\n")
        self.install_pip_audit([vulnerable("django")])
        result = self.scan_without_tomllib(["a/requirements.txt", "b/requirements.txt"])
        self.assertCompletedWithoutSkip(result)
        self.assertEqual(len(self.calls()), 2)


# ---------------------------------------------------------------------------
# AC-7 (NFR1): standard library only, tomllib only through the guarded import.
# ---------------------------------------------------------------------------

def _imported_top_level_modules(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def _imports_tomllib(node):
    if isinstance(node, ast.Import):
        return any(alias.name.split(".")[0] == "tomllib" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.level == 0 and (node.module or "").split(".")[0] == "tomllib"
    return False


def _tomllib_import_sites(path):
    """For every import of tomllib in the file, the innermost `try` whose BODY
    holds it (None when it is not inside a try body)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    sites = []

    def walk(node, enclosing_try):
        for child in ast.iter_child_nodes(node):
            inner = node if isinstance(node, ast.Try) and child in node.body else enclosing_try
            if _imports_tomllib(child):
                sites.append(inner)
            walk(child, inner)

    walk(tree, None)
    return sites


class TestStandardLibraryOnly(unittest.TestCase):
    def test_the_script_imports_only_the_standard_library_beyond_its_optional_yaml(self):
        outside = {m for m in _imported_top_level_modules(SCRIPT_PATH) if m not in sys.stdlib_module_names}
        self.assertEqual(outside, {"yaml"})

    def test_this_module_imports_only_the_standard_library(self):
        outside = {m for m in _imported_top_level_modules(__file__) if m not in sys.stdlib_module_names}
        self.assertEqual(outside, set())

    def test_tomllib_is_imported_only_through_the_guarded_import(self):
        sites = _tomllib_import_sites(SCRIPT_PATH)
        self.assertEqual(len(sites), 1, "tomllib must be imported exactly once")
        enclosing = sites[0]
        self.assertIsNotNone(enclosing, "the tomllib import must sit inside a try body")
        caught = {h.type.id for h in enclosing.handlers if isinstance(h.type, ast.Name)}
        self.assertIn("ImportError", caught)

    def test_the_script_still_loads_when_the_toml_parser_is_unavailable(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            module = _load_script("scan_dependencies_pyproject_directness_without_tomllib")
        self.assertIsNone(module.tomllib)
        self.assertTrue(callable(module.run_scan))
        # The resolver itself never raises without the parser either.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pyproject.toml"
            path.write_text(project_table("dependencies = ['a']"), encoding="utf-8")
            result = module._pip_pyproject_direct_names(str(path))
        self.assertFalse(result.complete)


if __name__ == "__main__":
    unittest.main()
