"""Tests for sca-python-lockfile-audit task0001: the pip axis of
`scan-dependencies.py scan` audits a changed poetry.lock / Pipfile.lock by
converting its pins into exact `name==version` requirement lines handed to
pip-audit, and returns fixed skip reasons when the lockfile cannot be
converted or its direct-dependency declaration file cannot be resolved.

Covers the task's Acceptance Criteria
(feature-docs/sca-python-lockfile-audit/tasks/task0001.md):

- AC-1: target selection (lockfile preferred, first in list order; other
  ecosystems unchanged; uv.lock / pdm.lock / pylock.toml select nothing).
- AC-3: end-to-end findings from a poetry.lock / Pipfile.lock pin, with the
  finding's `file` and affected range, and the content of the prepared file.
- AC-4: split runs for one name at several versions; determinism; partial
  failure of one launch.
- AC-5: unconvertible lockfiles (fixed reason, no launch, nothing raises).
- AC-6: excluded entries and the counts-only summary note.
- AC-7: the declaration file (`_pip_manifest_candidate`, the
  `pip_direct_manifest_not_found` reason, Pipfile direct names).
- AC-8: PEP 503 canonical names decide directness.
- AC-9: prepared files are owner-only, outside the project root and removed
  on every exit path; the project tree is left untouched.
- AC-10 (module loading, imports): the script and these tests use only the
  standard library, and the script loads without the TOML parser.

AC-2 (the lockfile job form and the unchanged invariants) lives in
tests/test_sca_scan_invocation.py next to that module's other job-form tests.

Per the task's Test Notes: no real pip-audit and no network. A stub
`pip-audit` (a Python script with an absolute-interpreter shebang) sits on a
PATH restricted to its own directory. On each launch it records the argument
vector, the content of the `-r` file and that file's permission bits to a
record file in a test-owned directory outside the project root, and prints
pip-audit-shaped JSON built from the `-r` lines. The system temporary
location is pointed at a test-owned directory so leftover prepared files are
observable. This module's imports are standard-library only; the script
under test is loaded by file path, and the stub writer is local to this
module.
"""

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"
INVOCATION_TEST_PATH = Path(__file__).resolve().parent / "test_sca_scan_invocation.py"


def _load_script(name="scan_dependencies_pip_lockfile"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

# An advisory description embedding a critical CVSS v3.1 vector (base score
# 9.8) so the existing severity rule can determine the severity.
CRITICAL_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

# FR11 on the prepared file: every line is `name==version` where the name
# fully matches the name pattern and the version has no whitespace, ';', '#'
# and does not begin with '-'.
FR11_LINE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*==[^\s;#\-][^\s;#]*")


# ---------------------------------------------------------------------------
# Stub pip-audit and small file builders (local to this module).
# ---------------------------------------------------------------------------

_PIP_AUDIT_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

CONFIG = json.loads(__CONFIG__)
args = sys.argv[1:]
req_path = args[args.index("-r") + 1] if "-r" in args else None
content = ""
mode = None
if req_path is not None:
    with open(req_path, encoding="utf-8") as fh:
        content = fh.read()
    mode = os.stat(req_path).st_mode & 0o777
with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({
        "argv": sys.argv,
        "requirements": content,
        "mode": mode,
        "path": req_path,
        "cwd": os.getcwd(),
    }) + "\\n")
lines = [line for line in content.splitlines() if line.strip()]
if any(marker in lines for marker in CONFIG["fail_lines"]):
    sys.exit(0)
dependencies = []
for line in lines:
    name, _, version = line.partition("==")
    vulns = []
    if line in CONFIG["vulnerable"]:
        vulns.append({
            "id": "PYSEC-" + name + "-" + version,
            "fix_versions": ["9.9.9"],
            "aliases": [],
            "description": "Test advisory for " + line + ". " + CONFIG["vector"],
        })
    if line in CONFIG["undetermined"]:
        vulns.append({
            "id": "PYSEC-NOVECTOR-" + name + "-" + version,
            "fix_versions": [],
            "aliases": [],
            "description": "Advisory without any severity metadata.",
        })
    dependencies.append({"name": name, "version": version, "vulns": vulns})
sys.stdout.write(json.dumps({"dependencies": dependencies}))
sys.exit(1 if any(dep["vulns"] for dep in dependencies) else 0)
'''


def write_pip_audit_stub(bin_dir, record_path, vulnerable=(), fail_lines=(), undetermined=()):
    """Writes an executable `pip-audit` stub into `bin_dir`. `vulnerable`
    and `undetermined` are `name==version` lines that get an advisory with
    / without a critical CVSS vector; a launch whose file holds a line in
    `fail_lines` prints nothing (pip-audit's empty-output failure)."""
    config = {
        "record": str(record_path),
        "vulnerable": list(vulnerable),
        "fail_lines": list(fail_lines),
        "undetermined": list(undetermined),
        "vector": CRITICAL_VECTOR,
    }
    source = _PIP_AUDIT_STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / "pip-audit"
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def write_json_stub(bin_dir, name, payload, exit_code=0):
    path = Path(bin_dir) / name
    path.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.stdout.write({json.dumps(payload)!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _toml_string(value):
    return json.dumps(value)


def poetry_lock_text(packages):
    """A poetry.lock text. Each package dict may carry `name`, `version`,
    `groups` (list), `category`, `source` (a source type) and `hashes`."""
    blocks = []
    for pkg in packages:
        lines = ["[[package]]"]
        if "name" in pkg:
            lines.append(f"name = {_toml_string(pkg['name'])}")
        if "version" in pkg:
            lines.append(f"version = {_toml_string(pkg['version'])}")
        lines.append('description = "demo package"')
        lines.append("optional = false")
        lines.append('python-versions = ">=3.8"')
        if "groups" in pkg:
            lines.append("groups = [" + ", ".join(_toml_string(g) for g in pkg["groups"]) + "]")
        if "category" in pkg:
            lines.append(f"category = {_toml_string(pkg['category'])}")
        if pkg.get("hashes", True):
            lines.append('files = [{file = "demo-1.0.tar.gz", hash = "sha256:deadbeefdeadbeef"}]')
        if "source" in pkg:
            lines.extend(
                [
                    "",
                    "[package.source]",
                    f"type = {_toml_string(pkg['source'])}",
                    'url = "https://example.invalid/demo"',
                ]
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + '\n\n[metadata]\nlock-version = "2.0"\ncontent-hash = "abc"\n'


def pipfile_lock_text(default=None, develop=None, **extra_top_level):
    data = {"_meta": {"hash": {"sha256": "abc"}, "pipfile-spec": 6}}
    if default is not None:
        data["default"] = default
    if develop is not None:
        data["develop"] = develop
    data.update(extra_top_level)
    return json.dumps(data, indent=2)


def pin(version, **extra):
    entry = {"hashes": ["sha256:deadbeefdeadbeef"], "index": "pypi", "version": f"=={version}"}
    entry.update(extra)
    return entry


PYPROJECT_DJANGO = (
    '[tool.poetry]\nname = "demo"\nversion = "0.1.0"\n\n'
    "[tool.poetry.dependencies]\n"
    'python = "^3.9"\n'
    'django = ">=3.2"\n'
)
PIPFILE_DJANGO = (
    '[[source]]\nurl = "https://pypi.org/simple"\nverify_ssl = true\nname = "pypi"\n\n'
    '[packages]\ndjango = ">=3.2"\n\n'
    "[dev-packages]\n\n"
    '[requires]\npython_version = "3.9"\n'
)


class LockfileScanCase(unittest.TestCase):
    """A project root, a stub-only PATH, a test-owned system temporary
    directory and a record directory -- all inside one temporary tree, with
    the record and temporary directories OUTSIDE the project root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.base = base
        self.root = base / "project"
        self.bin_dir = base / "bin"
        self.outside = base / "outside"
        self.records_dir = base / "records"
        self.systmp = base / "systmp"
        for directory in (self.root, self.bin_dir, self.outside, self.records_dir, self.systmp):
            directory.mkdir()
        self.record_path = self.records_dir / "pip-audit-calls.jsonl"

    # -- fixtures ---------------------------------------------------------

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def install_pip_audit(self, **kwargs):
        return write_pip_audit_stub(self.bin_dir, self.record_path, **kwargs)

    # -- running ----------------------------------------------------------

    def scan(self, changed_files, module=None):
        module = module or SCAN
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}), \
                mock.patch.object(tempfile, "tempdir", str(self.systmp)):
            result = module.run_scan(self.root, changed_files, module.DEFAULT_REGISTRY_PATH)
        self.assertEqual(os.listdir(self.systmp), [], "prepared files were left behind")
        return result

    def calls(self):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def assertNotLaunched(self):
        self.assertTrue(
            not self.record_path.exists() or self.record_path.stat().st_size == 0,
            f"pip-audit was launched: {self.calls()}",
        )

    @staticmethod
    def lines_of(call):
        return call["requirements"].splitlines()

    def all_prepared_lines(self):
        return [line for call in self.calls() for line in self.lines_of(call)]

    def assertSkipped(self, result, reason):
        self.assertTrue(result["skipped"], result)
        self.assertEqual(result["skip_reason"], reason)
        self.assertEqual(result["source"], "tool")


# ---------------------------------------------------------------------------
# AC-1 (FR1): target selection.
# ---------------------------------------------------------------------------

class TestPipTargetSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.registry = registry
        cls.by_name = {e["ecosystem"]: e for e in registry["ecosystems"]}

    def target(self, name, changed_files):
        return SCAN.manifest_file_for(self.by_name[name], changed_files)

    def test_a_lockfile_is_preferred_over_an_earlier_pyproject_or_requirements(self):
        for changed in (
            ["pyproject.toml", "poetry.lock"],
            ["requirements.txt", "pyproject.toml", "poetry.lock"],
            ["requirements.txt", "Pipfile.lock", "pyproject.toml"],
        ):
            with self.subTest(changed=changed):
                chosen = self.target("pip", changed)
                self.assertIn(os.path.basename(chosen), ("poetry.lock", "Pipfile.lock"))

    def test_the_first_lockfile_in_list_order_is_chosen(self):
        self.assertEqual(self.target("pip", ["a/Pipfile.lock", "poetry.lock"]), "a/Pipfile.lock")
        self.assertEqual(self.target("pip", ["poetry.lock", "a/Pipfile.lock"]), "poetry.lock")
        self.assertEqual(
            self.target("pip", ["pyproject.toml", "b/poetry.lock", "a/poetry.lock"]), "b/poetry.lock"
        )

    def test_without_a_pip_lockfile_the_target_is_the_same_file_as_before(self):
        self.assertEqual(self.target("pip", ["pyproject.toml", "requirements.txt"]), "pyproject.toml")
        self.assertEqual(self.target("pip", ["requirements.txt", "pyproject.toml"]), "requirements.txt")
        self.assertEqual(self.target("pip", ["x/requirements.txt"]), "x/requirements.txt")
        self.assertEqual(self.target("pip", ["package.json", "svc/pyproject.toml"]), "svc/pyproject.toml")

    def test_targets_for_npm_cargo_and_go_are_unchanged_for_any_list(self):
        mixed_lockfiles = ["poetry.lock", "Pipfile.lock"]
        cases = [
            ("npm", mixed_lockfiles + ["package-lock.json", "package.json"], "package.json"),
            ("npm", mixed_lockfiles + ["yarn.lock"], "yarn.lock"),
            ("cargo", mixed_lockfiles + ["Cargo.lock", "Cargo.toml"], "Cargo.toml"),
            ("cargo", mixed_lockfiles + ["Cargo.lock"], "Cargo.lock"),
            ("go", mixed_lockfiles + ["go.sum", "go.mod"], "go.mod"),
            ("go", mixed_lockfiles + ["go.sum"], "go.sum"),
        ]
        for name, changed, expected in cases:
            with self.subTest(ecosystem=name, changed=changed):
                self.assertEqual(self.target(name, changed), expected)

    def test_uv_pdm_and_pylock_alone_select_no_ecosystem(self):
        for changed in (["uv.lock"], ["pdm.lock"], ["pylock.toml"], ["uv.lock", "pdm.lock", "pylock.toml"]):
            with self.subTest(changed=changed):
                self.assertEqual(SCAN.select_ecosystems(self.registry, changed), [])


class TestLockfileFormIsTheOnlyLaunch(LockfileScanCase):
    def test_pyproject_and_poetry_lock_launch_pip_audit_once_in_the_lockfile_form(self):
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.install_pip_audit()
        self.scan(["pyproject.toml", "poetry.lock"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        argv = calls[0]["argv"]
        self.assertIn("-r", argv)
        self.assertIn("--no-deps", argv)
        self.assertIn("--disable-pip", argv)
        self.assertEqual(argv[-2:], ["--format", "json"])

    def test_requirements_pyproject_and_lockfile_audit_only_the_lockfile(self):
        self.write("requirements.txt", "django==3.2.0\n")
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["requirements.txt", "pyproject.toml", "poetry.lock"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual({f["file"] for f in result["findings"]}, {"poetry.lock"})

    def test_the_first_of_two_lockfiles_is_the_one_audited(self):
        self.write("Pipfile.lock", pipfile_lock_text(default={"django": pin("3.2.0")}))
        self.write("Pipfile", PIPFILE_DJANGO)
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["Pipfile.lock", "poetry.lock"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual({f["file"] for f in result["findings"]}, {"Pipfile.lock"})


# ---------------------------------------------------------------------------
# AC-3 (FR2, FR7, FR10): end-to-end findings.
# ---------------------------------------------------------------------------

class TestEndToEndFindings(LockfileScanCase):
    def assertDjangoFinding(self, result, lockfile):
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])
        django = [f for f in result["findings"] if f["title"].startswith("django:")]
        self.assertGreaterEqual(len(django), 1)
        for finding in django:
            self.assertEqual(finding["file"], lockfile)
            self.assertIn("affected: 3.2.0", finding["description"])
            self.assertEqual(finding["category"], "vulnerability")
            self.assertEqual(finding["severity"], "critical")

    def test_poetry_lock_pin_yields_a_finding_for_the_package(self):
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["poetry.lock"])
        self.assertDjangoFinding(result, "poetry.lock")

    def test_the_finding_file_is_the_lockfile_path_in_a_subdirectory(self):
        self.write("services/api/poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("services/api/pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["services/api/poetry.lock"])
        self.assertDjangoFinding(result, "services/api/poetry.lock")

    def test_pipfile_lock_pin_with_a_pipfile_packages_declaration(self):
        self.write("Pipfile.lock", pipfile_lock_text(default={"django": pin("3.2.0")}))
        self.write("Pipfile", PIPFILE_DJANGO)
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["Pipfile.lock"])
        self.assertDjangoFinding(result, "Pipfile.lock")

    def test_pipfile_lock_in_a_subdirectory_reports_that_path(self):
        self.write("svc/Pipfile.lock", pipfile_lock_text(default={"django": pin("3.2.0")}))
        self.write("svc/Pipfile", PIPFILE_DJANGO)
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["svc/Pipfile.lock"])
        self.assertDjangoFinding(result, "svc/Pipfile.lock")

    def test_a_package_declared_only_under_dev_packages_is_direct(self):
        self.write("Pipfile.lock", pipfile_lock_text(default={}, develop={"django": pin("3.2.0")}))
        self.write("Pipfile", '[packages]\n\n[dev-packages]\ndjango = "*"\n')
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["Pipfile.lock"])
        self.assertDjangoFinding(result, "Pipfile.lock")

    def test_a_package_the_declaration_does_not_name_is_transitive_and_dropped(self):
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.9"\nrequests = "*"\n')
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"])
        self.assertEqual(result["findings"], [])

    def test_prepared_file_holds_every_pin_of_every_poetry_group_without_hashes(self):
        self.write(
            "poetry.lock",
            poetry_lock_text(
                [
                    {"name": "django", "version": "3.2.0", "groups": ["main"]},
                    {"name": "pytest", "version": "7.0.0", "groups": ["dev"]},
                    {"name": "sphinx", "version": "5.0.0", "category": "docs"},
                    {"name": "extra-lib", "version": "1.2.3"},
                    {"name": "Django", "version": "3.2.0"},
                    {"name": "django", "version": "3.2.0", "groups": ["test"]},
                ]
            ),
        )
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        lines = self.lines_of(calls[0])
        self.assertEqual(
            sorted(lines),
            ["django==3.2.0", "extra-lib==1.2.3", "pytest==7.0.0", "sphinx==5.0.0"],
        )
        self.assertEqual(lines.count("django==3.2.0"), 1)
        self.assertNotIn("sha256", calls[0]["requirements"])
        self.assertNotIn("hash", calls[0]["requirements"])

    def test_prepared_file_holds_the_default_and_develop_pins_of_a_pipfile_lock(self):
        self.write(
            "Pipfile.lock",
            pipfile_lock_text(
                default={"django": pin("3.2.0"), "Requests": pin("2.25.0")},
                develop={"pytest": pin("7.0.0"), "django": pin("3.2.0")},
            ),
        )
        self.write("Pipfile", PIPFILE_DJANGO)
        self.install_pip_audit()
        self.scan(["Pipfile.lock"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        lines = self.lines_of(calls[0])
        self.assertEqual(sorted(lines), ["django==3.2.0", "pytest==7.0.0", "requests==2.25.0"])
        self.assertEqual(lines.count("django==3.2.0"), 1)
        self.assertNotIn("sha256", calls[0]["requirements"])

    def test_pipfile_lock_top_level_keys_other_than_default_and_develop_are_ignored(self):
        text = pipfile_lock_text(default={"django": pin("3.2.0")}, other={"ignored": pin("1.0")})
        self.write("Pipfile.lock", text)
        self.write("Pipfile", PIPFILE_DJANGO)
        self.install_pip_audit()
        self.scan(["Pipfile.lock"])
        self.assertEqual(self.lines_of(self.calls()[0]), ["django==3.2.0"])

    def test_pipfile_lock_with_only_a_develop_mapping_is_convertible(self):
        self.write("Pipfile.lock", json.dumps({"develop": {"pytest": pin("7.0.0")}}))
        self.write("Pipfile", '[dev-packages]\npytest = "*"\n')
        self.install_pip_audit(vulnerable=["pytest==7.0.0"])
        result = self.scan(["Pipfile.lock"])
        self.assertFalse(result["skipped"])
        self.assertEqual(len(result["findings"]), 1)

    def test_the_child_process_runs_in_the_project_root(self):
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        self.assertEqual(self.calls()[0]["cwd"], str(self.root))


# ---------------------------------------------------------------------------
# AC-4 (FR4, NFR3): split runs.
# ---------------------------------------------------------------------------

class TestSplitRuns(LockfileScanCase):
    PYPROJECT = (
        "[tool.poetry.dependencies]\n"
        'python = "^3.9"\n'
        'foo = "*"\n'
        'bar = "*"\n'
    )

    def two_version_project(self, versions=("1.0", "2.0"), extra=()):
        packages = [{"name": "foo", "version": v} for v in versions] + list(extra)
        self.write("poetry.lock", poetry_lock_text(packages))
        self.write("pyproject.toml", self.PYPROJECT)

    def finding_ids(self, result):
        return [SCAN.recover_package_advisory(f)[1] for f in result["findings"]]

    def test_one_name_at_two_versions_launches_twice_with_the_name_once_per_file(self):
        self.two_version_project(extra=[{"name": "bar", "version": "1.0"}])
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        for call in calls:
            names = [line.partition("==")[0] for line in self.lines_of(call)]
            self.assertEqual(names.count("foo"), 1)
        self.assertEqual(self.lines_of(calls[0]), ["bar==1.0", "foo==1.0"])
        self.assertEqual(self.lines_of(calls[1]), ["foo==2.0"])

    def test_the_first_launch_receives_the_version_that_sorts_first_by_plain_string_order(self):
        self.two_version_project(versions=("9.0", "10.0"))
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        calls = self.calls()
        self.assertEqual([self.lines_of(c) for c in calls], [["foo==10.0"], ["foo==9.0"]])

    def test_three_versions_launch_three_times_in_group_order(self):
        self.two_version_project(versions=("3.0", "1.0", "2.0"))
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        self.assertEqual(
            [self.lines_of(c) for c in self.calls()],
            [["foo==1.0"], ["foo==2.0"], ["foo==3.0"]],
        )

    def test_one_result_holds_the_findings_of_both_versions_in_launch_order(self):
        self.two_version_project()
        self.install_pip_audit(vulnerable=["foo==1.0", "foo==2.0"])
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertEqual(self.finding_ids(result), ["PYSEC-foo-1.0", "PYSEC-foo-2.0"])
        self.assertEqual({f["file"] for f in result["findings"]}, {"poetry.lock"})

    def test_split_names_are_compared_in_canonical_form(self):
        self.write(
            "poetry.lock",
            poetry_lock_text(
                [
                    {"name": "Foo_Bar", "version": "1.0"},
                    {"name": "foo-bar", "version": "2.0"},
                    {"name": "foo.bar", "version": "1.0"},
                ]
            ),
        )
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        self.assertEqual(
            [self.lines_of(c) for c in self.calls()], [["foo-bar==1.0"], ["foo-bar==2.0"]]
        )

    def test_scanning_the_same_input_twice_gives_byte_identical_result_json(self):
        self.two_version_project()
        self.install_pip_audit(vulnerable=["foo==1.0", "foo==2.0"])
        first = json.dumps(self.scan(["poetry.lock"]), ensure_ascii=False)
        second = json.dumps(self.scan(["poetry.lock"]), ensure_ascii=False)
        self.assertEqual(first, second)

    def test_no_prepared_file_path_appears_in_the_result(self):
        self.two_version_project()
        self.install_pip_audit(vulnerable=["foo==1.0", "foo==2.0"], fail_lines=[])
        result = self.scan(["poetry.lock"])
        dumped = json.dumps(result, ensure_ascii=False)
        paths = [c["path"] for c in self.calls()]
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertNotIn(path, dumped)
            self.assertNotIn(os.path.basename(path), dumped)
        self.assertNotIn(str(self.systmp), dumped)

    def test_a_launch_that_does_not_complete_skips_with_its_reason_and_keeps_the_other_findings(self):
        self.two_version_project()
        self.install_pip_audit(vulnerable=["foo==1.0"], fail_lines=["foo==2.0"])
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_empty_output")
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.finding_ids(result), ["PYSEC-foo-1.0"])

    def test_the_first_launch_failing_keeps_the_second_launch_findings(self):
        self.two_version_project()
        self.install_pip_audit(vulnerable=["foo==2.0"], fail_lines=["foo==1.0"])
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_empty_output")
        self.assertEqual(self.finding_ids(result), ["PYSEC-foo-2.0"])

    def test_two_launches_failing_with_the_same_reason_list_it_once(self):
        self.two_version_project()
        self.install_pip_audit(fail_lines=["foo==1.0", "foo==2.0"])
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_empty_output")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"].count("pip_empty_output"), 1)

    def test_a_partial_failure_still_lists_pip_as_scanned_when_a_launch_completed(self):
        self.two_version_project()
        self.install_pip_audit(fail_lines=["foo==2.0"])
        result = self.scan(["poetry.lock"])
        self.assertIn("Scanned pip", result["summary"])


# ---------------------------------------------------------------------------
# AC-5 (FR5, FR12, TM-2, TM-3, TM-4): unconvertible lockfiles.
# ---------------------------------------------------------------------------

def _deep_json(depth=200000):
    return b'{"default": ' + b"[" * depth + b"]" * depth + b"}"


def _deep_toml(depth=200000):
    return b"package = " + b"[" * depth + b"]" * depth + b"\n"


class TestUnconvertibleLockfiles(LockfileScanCase):
    POETRY_CASES = [
        ("invalid TOML", b'[[package]\nname = "django"\n'),
        ("no package key", b'[metadata]\nlock-version = "2.0"\n'),
        ("package is a table, not an array", b'[package]\nname = "django"\nversion = "3.2.0"\n'),
        ("package is a string", b'package = "django"\n'),
        ("empty package array", b"package = []\n"),
        ("empty file", b""),
        (
            "every entry is git",
            poetry_lock_text(
                [
                    {"name": "gitone", "version": "1.0", "source": "git"},
                    {"name": "gittwo", "version": "2.0", "source": "git"},
                ]
            ).encode(),
        ),
        (
            "every entry is non-registry",
            poetry_lock_text(
                [
                    {"name": "a", "version": "1.0", "source": "git"},
                    {"name": "b", "version": "1.0", "source": "directory"},
                    {"name": "c", "version": "1.0", "source": "file"},
                    {"name": "d", "version": "1.0", "source": "url"},
                ]
            ).encode(),
        ),
        ("non-UTF-8 bytes", b'package = []\n# \xff\xfe\xfa\n'),
        ("non-UTF-8 inside a value", b'[[package]]\nname = "dj\xff"\nversion = "1.0"\n'),
        ("entries of the wrong type", b'package = [1, "django", [], true]\n'),
        (
            "name and version of the wrong type",
            b'[[package]]\nname = 5\nversion = 3\n\n[[package]]\nname = ["a"]\nversion = "1.0"\n',
        ),
        ("version missing", b'[[package]]\nname = "django"\n'),
        ("name missing", b'[[package]]\nversion = "1.0"\n'),
        ("TOML nested beyond the parser's limit", _deep_toml()),
    ]
    PIPFILE_CASES = [
        ("invalid JSON", b'{"default": {"django": '),
        ("empty file", b""),
        ("top level is an array", b'[{"default": {}}]'),
        ("top level is a string", b'"default"'),
        ("neither default nor develop", b'{"_meta": {}}'),
        ("neither default nor develop is a mapping", b'{"default": [], "develop": "x"}'),
        ("both sections null", b'{"default": null, "develop": null}'),
        ("empty sections", b'{"default": {}, "develop": {}}'),
        (
            "every entry is non-registry",
            json.dumps(
                {
                    "default": {
                        "a": {"git": "https://example.invalid/a.git", "ref": "main"},
                        "b": {"path": "./b", "editable": True},
                        "c": {"file": "c.whl"},
                    },
                    "develop": {"d": {"editable": True, "version": "==1.0"}},
                }
            ).encode(),
        ),
        ("non-UTF-8 bytes", b'{"default": {"dj\xff": {"version": "==1.0"}}}'),
        ("UTF-16 content", '{"default": {}}'.encode("utf-16")),
        ("entries of the wrong type", b'{"default": {"a": "x", "b": 5, "c": [], "d": null}}'),
        ("versions of the wrong type", b'{"default": {"a": {"version": 3}, "b": {"version": ["==1.0"]}}}'),
        ("version not of the form ==X", b'{"default": {"a": {"version": ">=1.0"}, "b": {"version": "=="}}}'),
        ("JSON nested beyond the parser's limit", _deep_json()),
    ]

    def run_case(self, lockfile, content, declaration_name, declaration_text, changed=None):
        with self.subTest(lockfile=lockfile, content=content[:40]):
            self.write(lockfile, content)
            self.write(declaration_name, declaration_text)
            result = self.scan(changed or [lockfile])
            self.assertSkipped(result, "pip_lockfile_unconvertible")
            self.assertEqual(result["findings"], [])
            self.assertNotLaunched()

    def test_every_unconvertible_poetry_lock_yields_the_fixed_reason_without_a_launch(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        for label, content in self.POETRY_CASES:
            with self.subTest(case=label):
                self.run_case("poetry.lock", content, "pyproject.toml", PYPROJECT_DJANGO)

    def test_every_unconvertible_pipfile_lock_yields_the_fixed_reason_without_a_launch(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        for label, content in self.PIPFILE_CASES:
            with self.subTest(case=label):
                self.run_case("Pipfile.lock", content, "Pipfile", PIPFILE_DJANGO)

    def test_a_lockfile_listed_as_changed_but_absent_on_disk_is_unconvertible(self):
        self.install_pip_audit()
        for lockfile, declaration, text in (
            ("poetry.lock", "pyproject.toml", PYPROJECT_DJANGO),
            ("Pipfile.lock", "Pipfile", PIPFILE_DJANGO),
            ("svc/poetry.lock", "svc/pyproject.toml", PYPROJECT_DJANGO),
        ):
            with self.subTest(lockfile=lockfile):
                self.write(declaration, text)
                result = self.scan([lockfile])
                self.assertSkipped(result, "pip_lockfile_unconvertible")
                self.assertNotLaunched()

    def test_a_directory_named_like_a_lockfile_is_unconvertible(self):
        self.install_pip_audit()
        (self.root / "poetry.lock").mkdir()
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_a_lockfile_symlinked_outside_the_project_root_is_unconvertible(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        valid_outside = self.outside / "poetry.lock"
        valid_outside.write_text(poetry_lock_text([{"name": "django", "version": "3.2.0"}]), encoding="utf-8")
        os.symlink(valid_outside, self.root / "poetry.lock")
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertEqual(result["findings"], [])
        self.assertNotLaunched()

    def test_a_pipfile_lock_symlinked_outside_the_project_root_is_unconvertible(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        valid_outside = self.outside / "Pipfile.lock"
        valid_outside.write_text(pipfile_lock_text(default={"django": pin("3.2.0")}), encoding="utf-8")
        os.symlink(valid_outside, self.root / "Pipfile.lock")
        self.write("Pipfile", PIPFILE_DJANGO)
        result = self.scan(["Pipfile.lock"])
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_a_symlink_that_stays_inside_the_project_root_is_followed(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("real/poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        os.symlink(self.root / "real" / "poetry.lock", self.root / "poetry.lock")
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertEqual(len(result["findings"]), 1)

    def test_a_lockfile_path_escaping_the_project_root_is_unconvertible(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        (self.outside / "poetry.lock").write_text(
            poetry_lock_text([{"name": "django", "version": "3.2.0"}]), encoding="utf-8"
        )
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        for changed in (
            "../outside/poetry.lock",
            str(self.outside / "poetry.lock"),
            "svc/../../outside/poetry.lock",
        ):
            with self.subTest(changed=changed):
                result = self.scan([changed])
                self.assertSkipped(result, "pip_lockfile_unconvertible")
                self.assertNotLaunched()

    def test_a_lockfile_path_that_cannot_be_resolved_is_unconvertible_and_never_raises(self):
        self.install_pip_audit()
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        for changed in ("a\x00b/poetry.lock", "a\x00b/Pipfile.lock", "x" * 5000 + "/poetry.lock"):
            with self.subTest(changed=changed[:20]):
                result = self.scan([changed])
                self.assertSkipped(result, "pip_lockfile_unconvertible")
                self.assertNotLaunched()

    def test_neither_the_manifest_form_nor_the_directory_form_is_used(self):
        self.install_pip_audit()
        self.write("poetry.lock", b"not toml [[")
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.write("requirements.txt", "django==3.2.0\n")
        result = self.scan(["pyproject.toml", "requirements.txt", "poetry.lock"])
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_with_cargo_absent_and_npm_completing_the_reasons_combine_and_npm_findings_stay(self):
        npm_payload = {
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
        write_json_stub(self.bin_dir, "npm", npm_payload, exit_code=1)
        self.install_pip_audit()
        self.write("package.json", "{}\n")
        self.write("Cargo.toml", "[dependencies]\n")
        self.write("poetry.lock", b"package = [")
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        result = self.scan(["package.json", "Cargo.toml", "poetry.lock"])
        self.assertSkipped(result, "cargo_tool_not_found+pip_lockfile_unconvertible")
        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["findings"][0]["title"].startswith("lodash:"))
        self.assertNotLaunched()

    def test_the_tool_absent_reason_comes_first_and_conversion_is_never_attempted(self):
        # pip-audit is not on PATH: the existing tool-absent reason is the
        # only pip reason, whatever the lockfile holds.
        self.write("poetry.lock", b"not toml [[")
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_tool_not_found")

    def test_a_missing_declaration_reason_stands_beside_a_completed_ecosystem(self):
        self.install_pip_audit()
        write_json_stub(self.bin_dir, "npm", {"vulnerabilities": {}}, exit_code=0)
        self.write("package.json", "{}\n")
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        result = self.scan(["package.json", "poetry.lock"])
        # no sibling pyproject.toml -> pip_direct_manifest_not_found
        self.assertSkipped(result, "pip_direct_manifest_not_found")
        self.assertIn("Scanned npm", result["summary"])


# ---------------------------------------------------------------------------
# AC-6 (FR6, FR11, TM-1, TM-2): excluded entries.
# ---------------------------------------------------------------------------

class TestExcludedEntries(LockfileScanCase):
    NOTE_ONE = " 1 pip lockfile entry not auditable (pip_lockfile_entries_unpinnable)."

    def note_many(self, count):
        return f" {count} pip lockfile entries not auditable (pip_lockfile_entries_unpinnable)."

    def setUp(self):
        super().setUp()
        self.install_pip_audit(vulnerable=["django==3.2.0"])

    def poetry_project(self, extra_packages):
        packages = [{"name": "django", "version": "3.2.0"}] + extra_packages
        self.write("poetry.lock", poetry_lock_text(packages))
        self.write("pyproject.toml", PYPROJECT_DJANGO)

    def assertPreparedLinesAreSafe(self, forbidden_fragments):
        lines = self.all_prepared_lines()
        self.assertTrue(lines)
        for line in lines:
            self.assertIsNotNone(FR11_LINE.fullmatch(line), repr(line))
            self.assertEqual(line, line.strip())
        text = "\n".join(lines)
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, text)

    def test_poetry_source_types_other_than_the_registry_are_excluded_and_counted(self):
        self.poetry_project(
            [
                {"name": "gitpkg", "version": "1.0", "source": "git"},
                {"name": "dirpkg", "version": "1.0", "source": "directory"},
                {"name": "filepkg", "version": "1.0", "source": "file"},
                {"name": "urlpkg", "version": "1.0", "source": "url"},
                {"name": "legacypkg", "version": "1.0", "source": "legacy"},
            ]
        )
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["summary"].endswith(self.note_many(4)), result["summary"])
        self.assertEqual(sorted(self.lines_of(self.calls()[0])), ["django==3.2.0", "legacypkg==1.0"])

    def test_one_excluded_entry_uses_the_singular_note(self):
        self.poetry_project([{"name": "gitpkg", "version": "1.0", "source": "git"}])
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"])
        self.assertTrue(result["summary"].endswith(self.NOTE_ONE), result["summary"])

    def test_no_note_when_nothing_is_excluded(self):
        self.poetry_project([])
        result = self.scan(["poetry.lock"])
        self.assertNotIn("pip_lockfile_entries_unpinnable", result["summary"])

    def test_poetry_entries_with_missing_or_invalid_names_and_versions_are_excluded(self):
        bad = [
            {"name": "nover"},
            {"version": "1.0"},
            {"name": "-r evil", "version": "1.0"},
            {"name": "bad name", "version": "1.0"},
            {"name": "semi;colon", "version": "1.0"},
            {"name": "trailing-newline\n", "version": "1.0"},
            {"name": "", "version": "1.0"},
            {"name": ".leading-dot", "version": "1.0"},
            {"name": "versions-with-space", "version": "1.0 ; python_version < '3'"},
            {"name": "versions-with-newline", "version": "1.0\n--index-url http://evil.invalid/"},
            {"name": "versions-with-cr", "version": "1.0\rother==2.0"},
            {"name": "versions-with-tab", "version": "1.0\t"},
            {"name": "versions-with-hash", "version": "1.0#comment"},
            {"name": "versions-with-semicolon", "version": "1.0;marker"},
            {"name": "versions-leading-dash", "version": "-1.0"},
            {"name": "versions-option", "version": "--hash=sha256:00"},
            {"name": "versions-empty", "version": ""},
            {"name": "versions-line-sep", "version": "1.0 2.0"},
            {"name": "versions-trailing-backslash", "version": "1.0\\"},
        ]
        self.poetry_project(bad)
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertTrue(result["summary"].endswith(self.note_many(len(bad))), result["summary"])
        self.assertEqual(self.lines_of(self.calls()[0]), ["django==3.2.0"])
        self.assertPreparedLinesAreSafe(
            ["evil", "bad name", "semi", "trailing-newline", "nover", "versions-", "python_version", "index-url"]
        )

    def test_pipfile_entries_from_other_sources_or_without_a_pin_are_excluded_and_counted(self):
        default = {
            "django": pin("3.2.0"),
            "gitpkg": {"git": "https://example.invalid/g.git", "ref": "main"},
            "pathpkg": {"path": "./local"},
            "filepkg": {"file": "https://example.invalid/f.whl"},
            "editpkg": pin("1.0", editable=True),
            "nover": {"hashes": []},
            "rangepkg": {"version": ">=1.0"},
            "emptypin": {"version": "=="},
            "numver": {"version": 3},
            "scalar": "==1.0",
            "nested": [],
        }
        self.write("Pipfile.lock", pipfile_lock_text(default=default, develop={"devgit": {"git": "x"}}))
        self.write("Pipfile", PIPFILE_DJANGO)
        result = self.scan(["Pipfile.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["summary"].endswith(self.note_many(11)), result["summary"])
        self.assertEqual(self.lines_of(self.calls()[0]), ["django==3.2.0"])

    def test_pipfile_entries_with_invalid_names_or_versions_are_excluded(self):
        default = {
            "django": pin("3.2.0"),
            "-r evil": pin("1.0"),
            "bad name": pin("1.0"),
            "trailing\n": pin("1.0"),
            "spaced": {"version": "== 1.0"},
            "newline": {"version": "==1.0\n--extra-index-url http://evil.invalid/"},
            "semi": {"version": "==1.0;python_version<'3'"},
            "hash": {"version": "==1.0#x"},
            "dash": {"version": "==-1.0"},
            "tab": {"version": "==1.0\t"},
        }
        self.write("Pipfile.lock", pipfile_lock_text(default=default))
        self.write("Pipfile", PIPFILE_DJANGO)
        result = self.scan(["Pipfile.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertTrue(result["summary"].endswith(self.note_many(9)), result["summary"])
        self.assertEqual(self.lines_of(self.calls()[0]), ["django==3.2.0"])
        self.assertPreparedLinesAreSafe(["evil", "bad name", "trailing", "spaced", "newline", "semi", "dash"])

    def test_the_version_written_is_the_remainder_after_the_double_equals(self):
        self.write("Pipfile.lock", pipfile_lock_text(default={"django": pin("3.2.0"), "other": pin("1!2.0+local.1")}))
        self.write("Pipfile", PIPFILE_DJANGO)
        self.scan(["Pipfile.lock"])
        self.assertEqual(sorted(self.lines_of(self.calls()[0])), ["django==3.2.0", "other==1!2.0+local.1"])

    def test_the_note_follows_the_undetermined_severity_note(self):
        self.install_pip_audit(vulnerable=[], undetermined=["django==3.2.0"])
        self.poetry_project([{"name": "gitpkg", "version": "1.0", "source": "git"}])
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertTrue(
            result["summary"].endswith(
                " 1 pip advisory with undetermined severity (pip_severity_undetermined)." + self.NOTE_ONE
            ),
            result["summary"],
        )

    def test_the_note_carries_counts_only_never_lockfile_text(self):
        self.poetry_project([{"name": "secret-package-name", "version": "9.9", "source": "git"}])
        result = self.scan(["poetry.lock"])
        self.assertNotIn("secret-package-name", json.dumps(result))

    def test_no_note_is_added_when_no_run_is_launched(self):
        # The declaration file is missing, so nothing is launched and no
        # excluded-entry note is reported.
        self.write(
            "poetry.lock",
            poetry_lock_text(
                [{"name": "django", "version": "3.2.0"}, {"name": "g", "version": "1", "source": "git"}]
            ),
        )
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_direct_manifest_not_found")
        self.assertNotIn("pip_lockfile_entries_unpinnable", result["summary"])
        self.assertNotLaunched()


class TestConversionUnit(LockfileScanCase):
    """The conversion stage in isolation (IMPLEMENTATION.md C3)."""

    def test_groups_are_ordered_sorted_and_hold_each_canonical_name_once(self):
        self.write(
            "poetry.lock",
            poetry_lock_text(
                [
                    {"name": "foo", "version": "2.0"},
                    {"name": "Foo", "version": "1.0"},
                    {"name": "bar", "version": "1.0"},
                    {"name": "foo", "version": "3.0"},
                    {"name": "foo", "version": "1.0"},
                    {"name": "Baz_Qux", "version": "0.1"},
                ]
            ),
        )
        converted = SCAN.convert_pip_lockfile(self.root, "poetry.lock")
        self.assertIsNotNone(converted)
        groups, excluded = converted
        self.assertEqual(excluded, 0)
        self.assertEqual(
            groups,
            [["bar==1.0", "baz-qux==0.1", "foo==1.0"], ["foo==2.0"], ["foo==3.0"]],
        )

    def test_conversion_is_deterministic_and_independent_of_entry_order(self):
        packages = [
            {"name": "foo", "version": "2.0"},
            {"name": "bar", "version": "1.0"},
            {"name": "foo", "version": "1.0"},
        ]
        self.write("poetry.lock", poetry_lock_text(packages))
        first = SCAN.convert_pip_lockfile(self.root, "poetry.lock")
        self.write("poetry.lock", poetry_lock_text(list(reversed(packages))))
        second = SCAN.convert_pip_lockfile(self.root, "poetry.lock")
        self.assertEqual(first, second)

    def test_conversion_never_raises_for_any_content(self):
        blobs = [
            b"",
            b"\x00\x00",
            b"\xff" * 10,
            b"{",
            b"[[[[",
            b"package = [{name = 1}]",
            b'{"default": {"a": {"version": {"x": 1}}}}',
            b'{"default": {"a": {"version": "==1.0", "git": null}}}',
            b'{"default": {"1": {"version": "==1"}}, "develop": 7}',
            b'package = [{name = "a", version = "1.0", source = "git"}, 5, {name = "b", version = "2.0", source = 7}]',
            _deep_json(),
            _deep_toml(),
        ]
        for lockfile in ("poetry.lock", "Pipfile.lock"):
            for blob in blobs:
                with self.subTest(lockfile=lockfile, blob=blob[:30]):
                    self.write(lockfile, blob)
                    converted = SCAN.convert_pip_lockfile(self.root, lockfile)
                    self.assertTrue(converted is None or (isinstance(converted, tuple) and len(converted) == 2))

    def test_a_non_table_source_does_not_exclude_the_entry_but_a_git_table_does(self):
        text = (
            '[[package]]\nname = "plain"\nversion = "1.0"\nsource = "odd"\n\n'
            '[[package]]\nname = "gitty"\nversion = "1.0"\n\n[package.source]\ntype = "git"\n\n'
            '[[package]]\nname = "typeless"\nversion = "1.0"\n\n[package.source]\ntype = ["git"]\n'
        )
        self.write("poetry.lock", text)
        groups, excluded = SCAN.convert_pip_lockfile(self.root, "poetry.lock")
        self.assertEqual(excluded, 1)
        self.assertEqual(groups, [["plain==1.0", "typeless==1.0"]])

    def test_canonical_names_follow_pep_503(self):
        cases = {
            "Django": "django",
            "Foo_Bar.baz": "foo-bar-baz",
            "a--b__c..d": "a-b-c-d",
            "A-_.b": "a-b",
            "already-canonical": "already-canonical",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(SCAN.canonical_pip_name(raw), expected)


# ---------------------------------------------------------------------------
# AC-7 (FR7, FR8, TM-3, TM-4): declaration file.
# ---------------------------------------------------------------------------

class TestDeclarationFile(LockfileScanCase):
    def setUp(self):
        super().setUp()
        self.install_pip_audit(vulnerable=["django==3.2.0"])

    POETRY = poetry_lock_text([{"name": "django", "version": "3.2.0"}])
    PIPFILE_LOCK = pipfile_lock_text(default={"django": pin("3.2.0")})

    def test_candidate_for_pipfile_lock_is_the_sibling_pipfile(self):
        self.write("Pipfile", PIPFILE_DJANGO)
        self.write("svc/Pipfile", PIPFILE_DJANGO)
        self.assertEqual(SCAN._pip_manifest_candidate(self.root, "Pipfile.lock"), str(self.root / "Pipfile"))
        self.assertEqual(
            SCAN._pip_manifest_candidate(self.root, "svc/Pipfile.lock"), str(self.root / "svc" / "Pipfile")
        )

    def test_candidate_for_poetry_lock_is_the_sibling_pyproject(self):
        self.assertEqual(
            SCAN._pip_manifest_candidate(self.root, "poetry.lock"), str(self.root / "pyproject.toml")
        )
        self.assertEqual(
            SCAN._pip_manifest_candidate(self.root, "a/b/poetry.lock"),
            str(self.root / "a" / "b" / "pyproject.toml"),
        )

    def test_candidate_never_returns_a_lockfile_path(self):
        for lockfile in ("poetry.lock", "Pipfile.lock", "x/poetry.lock", "x/Pipfile.lock"):
            with self.subTest(lockfile=lockfile):
                candidate = SCAN._pip_manifest_candidate(self.root, lockfile)
                self.assertNotIn(os.path.basename(candidate), ("poetry.lock", "Pipfile.lock"))

    def test_other_manifests_map_as_before(self):
        self.assertEqual(
            SCAN._pip_manifest_candidate(self.root, "requirements.txt"), str(self.root / "requirements.txt")
        )
        self.assertEqual(
            SCAN._pip_manifest_candidate(self.root, "svc/pyproject.toml"),
            str(self.root / "svc" / "pyproject.toml"),
        )

    def test_candidate_is_nothing_for_a_path_outside_the_project_root(self):
        self.assertIsNone(SCAN._pip_manifest_candidate(self.root, "../outside/poetry.lock"))
        self.assertIsNone(SCAN._pip_manifest_candidate(self.root, str(self.outside / "Pipfile.lock")))
        (self.outside / "Pipfile").write_text(PIPFILE_DJANGO, encoding="utf-8")
        os.symlink(self.outside / "Pipfile", self.root / "Pipfile")
        self.assertIsNone(SCAN._pip_manifest_candidate(self.root, "Pipfile.lock"))
        self.assertIsNone(SCAN._pip_manifest_candidate(None, "poetry.lock"))

    def run_missing_declaration(self, lockfile, content):
        self.write(lockfile, content)
        result = self.scan([lockfile])
        self.assertSkipped(result, "pip_direct_manifest_not_found")
        self.assertEqual(result["findings"], [])
        self.assertNotLaunched()

    def test_a_missing_declaration_file_is_not_found(self):
        with self.subTest(lockfile="poetry.lock"):
            self.run_missing_declaration("poetry.lock", self.POETRY)
        with self.subTest(lockfile="Pipfile.lock"):
            self.run_missing_declaration("Pipfile.lock", self.PIPFILE_LOCK)

    def test_a_pyproject_in_another_directory_does_not_count(self):
        self.write("other/pyproject.toml", PYPROJECT_DJANGO)
        self.run_missing_declaration("svc/poetry.lock", self.POETRY)

    def test_a_pipfile_lock_needs_a_pipfile_not_a_pyproject(self):
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.run_missing_declaration("Pipfile.lock", self.PIPFILE_LOCK)

    def test_a_poetry_lock_needs_a_pyproject_not_a_pipfile(self):
        self.write("Pipfile", PIPFILE_DJANGO)
        self.run_missing_declaration("poetry.lock", self.POETRY)

    def test_an_invalid_toml_declaration_file_is_not_found(self):
        broken = "[tool.poetry.dependencies\ndjango = \n"
        with self.subTest(lockfile="poetry.lock"):
            self.write("pyproject.toml", broken)
            self.run_missing_declaration("poetry.lock", self.POETRY)
        with self.subTest(lockfile="Pipfile.lock"):
            self.write("Pipfile", broken)
            self.run_missing_declaration("Pipfile.lock", self.PIPFILE_LOCK)

    def test_a_non_utf8_declaration_file_is_not_found(self):
        with self.subTest(lockfile="poetry.lock"):
            self.write("pyproject.toml", b"[tool.poetry.dependencies]\ndjango = \"\xff\"\n")
            self.run_missing_declaration("poetry.lock", self.POETRY)
        with self.subTest(lockfile="Pipfile.lock"):
            self.write("Pipfile", b"[packages]\n\xff\xfe = \"*\"\n")
            self.run_missing_declaration("Pipfile.lock", self.PIPFILE_LOCK)

    def test_a_directory_in_place_of_the_declaration_file_is_not_found(self):
        (self.root / "pyproject.toml").mkdir()
        self.run_missing_declaration("poetry.lock", self.POETRY)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_declaration_file_is_not_found(self):
        declaration = self.write("pyproject.toml", PYPROJECT_DJANGO)
        declaration.chmod(0)
        self.addCleanup(declaration.chmod, 0o600)
        self.run_missing_declaration("poetry.lock", self.POETRY)

    def test_a_declaration_file_symlinked_outside_the_project_root_is_not_found(self):
        (self.outside / "pyproject.toml").write_text(PYPROJECT_DJANGO, encoding="utf-8")
        os.symlink(self.outside / "pyproject.toml", self.root / "pyproject.toml")
        self.run_missing_declaration("poetry.lock", self.POETRY)

    def test_a_pipfile_symlinked_outside_the_project_root_is_not_found(self):
        (self.outside / "Pipfile").write_text(PIPFILE_DJANGO, encoding="utf-8")
        os.symlink(self.outside / "Pipfile", self.root / "Pipfile")
        self.run_missing_declaration("Pipfile.lock", self.PIPFILE_LOCK)

    def test_conversion_failure_is_reported_before_a_missing_declaration_file(self):
        self.write("poetry.lock", b"not toml [[")
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_with_a_valid_pipfile_the_direct_names_are_the_keys_of_both_tables(self):
        self.write(
            "Pipfile",
            (
                '[[source]]\nurl = "https://pypi.org/simple"\nname = "pypi"\n\n'
                '[packages]\nDjango = ">=3.2"\nrequests = {version = "*", extras = ["socks"]}\n\n'
                '[dev-packages]\npytest = "*"\n\n'
                '[requires]\npython_version = "3.9"\n\n[scripts]\nstart = "python x.py"\n'
            ),
        )
        self.assertEqual(
            SCAN._pip_direct_dependency_names(self.root, "Pipfile.lock"),
            {"Django", "requests", "pytest"},
        )

    def test_a_pipfile_table_that_is_not_a_table_contributes_no_names(self):
        self.write("Pipfile", 'packages = "oops"\n\n[dev-packages]\npytest = "*"\n')
        self.assertEqual(SCAN._pip_direct_dependency_names(self.root, "Pipfile.lock"), {"pytest"})

    def test_direct_names_for_a_poetry_lock_come_from_the_existing_pyproject_parser(self):
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.assertEqual(SCAN._pip_direct_dependency_names(self.root, "poetry.lock"), {"django"})

    def test_direct_names_are_empty_when_the_declaration_cannot_be_resolved(self):
        self.assertEqual(SCAN._pip_direct_dependency_names(self.root, "Pipfile.lock"), set())
        self.assertEqual(SCAN._pip_direct_dependency_names(self.root, "poetry.lock"), set())


# ---------------------------------------------------------------------------
# AC-8 (FR9): canonical names decide directness.
# ---------------------------------------------------------------------------

class TestCanonicalDirectness(LockfileScanCase):
    ECOSYSTEM = {
        "ecosystem": "pip",
        "severity_map": {"critical": "critical", "high": "high"},
        "threshold": {"direct_only": True, "min_severity": "high"},
    }

    @staticmethod
    def pip_audit_output(name, version="1.0"):
        return {
            "dependencies": [
                {
                    "name": name,
                    "version": version,
                    "vulns": [
                        {
                            "id": "PYSEC-TEST-1",
                            "fix_versions": ["9.9.9"],
                            "aliases": [],
                            "description": f"Test advisory. {CRITICAL_VECTOR}",
                        }
                    ],
                }
            ]
        }

    def normalize(self, manifest, declaration, reported):
        self.write(manifest, declaration)
        findings, _ = SCAN.normalize_pip(self.ECOSYSTEM, self.pip_audit_output(reported), manifest, self.root)
        return findings

    def test_declared_Django_matches_lockfile_and_output_django_end_to_end(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", '[tool.poetry.dependencies]\nDjango = ">=3.2"\n')
        result = self.scan(["poetry.lock"])
        self.assertFalse(result["skipped"], result)
        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))

    def test_declared_Django_in_a_pipfile_matches_end_to_end(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("Pipfile.lock", pipfile_lock_text(default={"Django": pin("3.2.0")}))
        self.write("Pipfile", '[packages]\nDjango = "*"\n')
        result = self.scan(["Pipfile.lock"])
        self.assertEqual(len(result["findings"]), 1)

    def test_declared_in_a_pep_621_dependency_list_matches(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("poetry.lock", poetry_lock_text([{"name": "Django", "version": "3.2.0"}]))
        self.write("pyproject.toml", '[project]\nname = "demo"\ndependencies = ["Django>=3.2"]\n')
        result = self.scan(["poetry.lock"])
        self.assertEqual(len(result["findings"]), 1)

    def test_a_declared_mixed_separator_name_matches_the_reported_canonical_name(self):
        findings = self.normalize("requirements.txt", "Foo_Bar.baz==1.0\n", "foo-bar-baz")
        self.assertEqual(len(findings), 1)

    def test_a_declared_canonical_name_matches_a_reported_mixed_separator_name(self):
        findings = self.normalize("requirements.txt", "foo-bar-baz==1.0\n", "Foo_Bar.baz")
        self.assertEqual(len(findings), 1)

    def test_pyproject_toml_declarations_are_compared_canonically_too(self):
        findings = self.normalize(
            "pyproject.toml", '[tool.poetry.dependencies]\n"Foo_Bar.baz" = "*"\n', "foo-bar-baz"
        )
        self.assertEqual(len(findings), 1)

    def test_a_different_name_stays_transitive(self):
        findings = self.normalize("requirements.txt", "foo-bar==1.0\n", "foo-bar-baz")
        self.assertEqual(findings, [])

    def test_a_non_string_reported_name_never_raises(self):
        self.write("requirements.txt", "foo==1.0\n")
        data = {"dependencies": [{"name": ["foo"], "version": "1.0", "vulns": []}, {"version": "1"}]}
        findings, skip = SCAN.normalize_pip(self.ECOSYSTEM, data, "requirements.txt", self.root)
        self.assertEqual((findings, skip), ([], None))


# ---------------------------------------------------------------------------
# AC-9 (NFR1, TM-6): temporary files.
# ---------------------------------------------------------------------------

class TestTemporaryFiles(LockfileScanCase):
    def project(self, versions=("3.2.0",)):
        packages = [{"name": "django", "version": v} for v in versions]
        self.write("poetry.lock", poetry_lock_text(packages))
        self.write("pyproject.toml", PYPROJECT_DJANGO)

    def test_each_prepared_file_is_owner_only_and_outside_the_project_root(self):
        self.project(versions=("3.2.0", "4.0.0"))
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        root = os.path.realpath(self.root)
        for call in calls:
            with self.subTest(path=call["path"]):
                self.assertEqual(call["mode"] & 0o077, 0, oct(call["mode"]))
                self.assertTrue(call["mode"] & 0o600 == 0o600, oct(call["mode"]))
                real = os.path.realpath(call["path"])
                self.assertFalse(real == root or real.startswith(root + os.sep), real)
                self.assertEqual(os.path.dirname(real), str(self.systmp))

    def test_prepared_files_have_unique_unpredictable_names(self):
        self.project(versions=("3.2.0", "4.0.0"))
        self.install_pip_audit()
        self.scan(["poetry.lock"])
        self.scan(["poetry.lock"])
        paths = [c["path"] for c in self.calls()]
        self.assertEqual(len(paths), 4)
        self.assertEqual(len(set(paths)), 4)

    def test_no_prepared_file_remains_after_the_scan_returns(self):
        self.project()
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.scan(["poetry.lock"])  # asserts the test-owned directory is empty
        self.assertEqual(os.listdir(self.systmp), [])

    def test_no_prepared_file_remains_when_a_launch_does_not_complete(self):
        self.project()
        self.install_pip_audit(fail_lines=["django==3.2.0"])
        result = self.scan(["poetry.lock"])
        self.assertSkipped(result, "pip_empty_output")

    def test_an_exception_from_the_execution_step_propagates_and_leaves_no_file(self):
        self.project(versions=("3.2.0", "4.0.0"))
        self.install_pip_audit()
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}), \
                mock.patch.object(tempfile, "tempdir", str(self.systmp)), \
                mock.patch.object(SCAN, "run_ecosystem_command", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                SCAN.run_scan(self.root, ["poetry.lock"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertEqual(os.listdir(self.systmp), [])

    def test_an_exception_on_the_second_launch_leaves_no_file(self):
        self.project(versions=("3.2.0", "4.0.0"))
        self.install_pip_audit()
        effects = [(SCAN.OUTCOME_COMPLETED, {"dependencies": []}), RuntimeError("boom")]
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}), \
                mock.patch.object(tempfile, "tempdir", str(self.systmp)), \
                mock.patch.object(SCAN, "run_ecosystem_command", side_effect=effects):
            with self.assertRaises(RuntimeError):
                SCAN.run_scan(self.root, ["poetry.lock"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertEqual(os.listdir(self.systmp), [])

    def test_the_prepared_file_scope_removes_files_on_normal_and_exceptional_exit(self):
        with mock.patch.object(tempfile, "tempdir", str(self.systmp)):
            with SCAN.prepared_requirements_files([["a==1.0"], ["b==2.0", "c==3.0"]]) as paths:
                self.assertEqual(len(paths), 2)
                contents = [Path(p).read_text(encoding="utf-8") for p in paths]
                self.assertEqual(contents, ["a==1.0\n", "b==2.0\nc==3.0\n"])
            self.assertEqual(os.listdir(self.systmp), [])
            with self.assertRaises(ValueError):
                with SCAN.prepared_requirements_files([["a==1.0"], ["b==2.0"]]):
                    self.assertEqual(len(os.listdir(self.systmp)), 2)
                    raise ValueError("inside the scope")
            self.assertEqual(os.listdir(self.systmp), [])

    def test_the_scope_removes_earlier_files_when_creating_a_later_one_fails(self):
        real_mkstemp = tempfile.mkstemp
        counter = {"n": 0}

        def flaky_mkstemp(*args, **kwargs):
            counter["n"] += 1
            if counter["n"] == 2:
                raise OSError("no space left")
            return real_mkstemp(*args, **kwargs)

        with mock.patch.object(tempfile, "tempdir", str(self.systmp)), \
                mock.patch.object(tempfile, "mkstemp", side_effect=flaky_mkstemp):
            with self.assertRaises(OSError):
                with SCAN.prepared_requirements_files([["a==1.0"], ["b==2.0"]]):
                    self.fail("the scope must not be entered")
        self.assertEqual(os.listdir(self.systmp), [])

    def test_git_status_porcelain_is_identical_before_and_after_a_lockfile_scan(self):
        self.project()
        self.write("README.md", "demo\n")
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)

        def porcelain():
            proc = subprocess.run(
                ["git", "-C", str(self.root), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            )
            return proc.stdout

        before = porcelain()
        self.assertTrue(before.strip())
        self.scan(["poetry.lock"])
        self.assertEqual(porcelain(), before)

    def test_the_project_tree_is_byte_identical_after_the_scan(self):
        self.project()
        self.install_pip_audit(vulnerable=["django==3.2.0"])

        def snapshot():
            return {
                str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                for p in sorted(self.root.rglob("*"))
            }

        before = snapshot()
        self.scan(["poetry.lock"])
        self.assertEqual(snapshot(), before)


# ---------------------------------------------------------------------------
# AC-10 (NFR4, NFR5, NFR7): dependencies, module loading.
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


class TestDependenciesAndModuleLoading(LockfileScanCase):
    def test_the_script_imports_only_the_standard_library_beyond_its_optional_yaml(self):
        imported = _imported_top_level_modules(SCRIPT_PATH)
        outside = {m for m in imported if m not in sys.stdlib_module_names}
        self.assertEqual(outside, {"yaml"})
        self.assertIn("json", imported)
        self.assertIn("tomllib", imported)

    def test_the_new_and_changed_test_modules_import_only_the_standard_library(self):
        for path in (Path(__file__), INVOCATION_TEST_PATH):
            with self.subTest(module=path.name):
                imported = _imported_top_level_modules(path)
                self.assertEqual({m for m in imported if m not in sys.stdlib_module_names}, set())

    def test_the_script_still_loads_when_the_toml_parser_is_unavailable(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            with self.assertRaises(ImportError):
                import tomllib  # noqa: F401
            module = _load_script("scan_dependencies_without_tomllib")
        self.assertTrue(callable(module.run_scan))

    def test_a_poetry_lock_target_is_unconvertible_without_the_toml_parser(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            module = _load_script("scan_dependencies_without_tomllib_scan")
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        result = self.scan(["poetry.lock"], module=module)
        self.assertSkipped(result, "pip_lockfile_unconvertible")
        self.assertNotLaunched()

    def test_a_toml_declaration_file_is_not_found_without_the_toml_parser(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            module = _load_script("scan_dependencies_without_tomllib_decl")
        self.install_pip_audit(vulnerable=["django==3.2.0"])
        self.write("Pipfile.lock", pipfile_lock_text(default={"django": pin("3.2.0")}))
        self.write("Pipfile", PIPFILE_DJANGO)
        result = self.scan(["Pipfile.lock"], module=module)
        self.assertSkipped(result, "pip_direct_manifest_not_found")
        self.assertNotLaunched()

    def test_other_ecosystems_keep_working_without_the_toml_parser(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            module = _load_script("scan_dependencies_without_tomllib_npm")
        write_json_stub(self.bin_dir, "npm", {"vulnerabilities": {}}, exit_code=0)
        self.write("package.json", "{}\n")
        result = self.scan(["package.json"], module=module)
        self.assertFalse(result["skipped"], result)

    def test_the_stub_is_the_only_scanner_on_path_during_a_scan(self):
        # NFR5: no real pip-audit can be reached -- PATH holds the stub dir only.
        self.install_pip_audit()
        self.write("poetry.lock", poetry_lock_text([{"name": "django", "version": "3.2.0"}]))
        self.write("pyproject.toml", PYPROJECT_DJANGO)
        self.scan(["poetry.lock"])
        for call in self.calls():
            self.assertEqual(os.path.dirname(call["argv"][0]), str(self.bin_dir))


if __name__ == "__main__":
    unittest.main()
