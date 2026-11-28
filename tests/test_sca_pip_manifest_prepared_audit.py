"""Tests for sca-pip-no-build-exec task0001: every pip scan unit of
`scan-dependencies.py scan` is audited by starting pip-audit only on a
PREPARED requirements file that holds statically extracted, validated
`name==version` lines. The registry's per-target-form table supplies the
flag and arguments, an input that cannot be fully pinned reports a fixed
`skip_reason` token, and no reviewed file is ever handed to pip-audit.

Scenarios covered here (feature-docs/sca-pip-no-build-exec/tasks/task0001.md):

- AC-3 (TS-1, TM-1): the pip job form for every manifest kind, built from the
  registry's `prepared_requirements` form and a prepared file outside the
  project root; no argv element names the project root or the reviewed file.
- AC-4 (TS-2, TM-2, TM-3, TM-4): static extraction from requirements files
  (pin rule, excluded count, confinement, never-opened constraint files,
  read-only, no process, never raises).
- AC-5 (TS-2): static extraction from pyproject.toml.
- AC-6 (TS-3, TS-4, TM-1, TM-2): routing -- fully pinned, mixed and
  unpinnable units, and the fixed skip tokens.
- AC-7 (TS-2, TS-3, TS-8, TM-6): one name at two versions, determinism and
  untrusted text staying out of the result.
- AC-8 (TS-7, TM-7): prepared files are owner-only and removed on every exit
  path, and the project tree is left byte-identical.

The registry shape and the registry validation (AC-1, AC-2) live in
tests/test_sca_scan_invocation.py next to that module's restricted parser.

Per the task's Test Notes: no real scanner and no network. A stub `pip-audit`
(a Python script with an absolute-interpreter shebang) sits on a PATH that
holds only its own directory. On each launch it records the argument vector,
the content of the `-r` file and that file's permission bits to a record file
in a test-owned directory outside the project root, and prints
pip-audit-shaped JSON built from the `-r` lines. The system temporary
location is pointed at a test-owned directory so leftover prepared files are
observable. This module's imports are standard-library only and the script
under test is loaded by file path; the stub writer and the recorders are
local copies of the patterns the sibling modules use.
"""

import builtins
import copy
import importlib.util
import inspect
import json
import os
import random
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script(name="scan_dependencies_pip_manifest_prepared"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


SCAN = _load_script()

# An advisory description embedding a critical CVSS v3.1 vector (base score
# 9.8) so the existing severity rule can determine the severity.
CRITICAL_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

JOB_TAIL = ["--no-deps", "--disable-pip", "--format", "json"]

UNPINNABLE = "pip_manifest_unpinnable"
ENTRIES_UNPINNABLE = "pip_manifest_entries_unpinnable"


# ---------------------------------------------------------------------------
# Stub pip-audit and recorders (local to this module).
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
    dependencies.append({"name": name, "version": version, "vulns": vulns})
sys.stdout.write(json.dumps({"dependencies": dependencies}))
sys.exit(1 if any(dep["vulns"] for dep in dependencies) else 0)
'''


def write_pip_audit_stub(bin_dir, record_path, vulnerable=(), fail_lines=()):
    """Writes an executable `pip-audit` stub into `bin_dir`. `vulnerable` is
    a list of `name==version` lines that get a critical advisory; a launch
    whose file holds a line in `fail_lines` prints nothing (pip-audit's
    empty-output failure, a run that does not complete)."""
    config = {
        "record": str(record_path),
        "vulnerable": list(vulnerable),
        "fail_lines": list(fail_lines),
        "vector": CRITICAL_VECTOR,
    }
    source = _PIP_AUDIT_STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / "pip-audit"
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


class NetworkGuard:
    """Every attempt at the network layer is recorded and then refused."""

    def __enter__(self):
        self.calls = []

        def refuse(label):
            def attempt(*args, **kwargs):
                self.calls.append(label)
                raise OSError("network access is not allowed in this test")

            return attempt

        self._patches = [
            mock.patch.object(socket, "create_connection", refuse("create_connection")),
            mock.patch.object(socket, "getaddrinfo", refuse("getaddrinfo")),
            mock.patch.object(socket.socket, "connect", refuse("connect")),
            mock.patch.object(socket.socket, "connect_ex", refuse("connect_ex")),
            mock.patch.object(urllib.request, "urlopen", refuse("urlopen")),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc_info):
        for patch in reversed(self._patches):
            patch.stop()
        return False


class ProcessGuard:
    """Every attempt to start a process is recorded and then refused."""

    def __enter__(self):
        self.calls = []

        def refuse(label):
            def attempt(*args, **kwargs):
                self.calls.append(label)
                raise OSError("starting a process is not allowed in this test")

            return attempt

        self._patches = [
            mock.patch.object(subprocess, "Popen", refuse("Popen")),
            mock.patch.object(subprocess, "run", refuse("run")),
            mock.patch.object(os, "system", refuse("system")),
            mock.patch.object(os, "popen", refuse("popen")),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc_info):
        for patch in reversed(self._patches):
            patch.stop()
        return False


class OpenRecorder:
    """Records the real path and the mode of every file opened through
    builtins.open while active (and still performs the open)."""

    def __enter__(self):
        self.opened = []
        self.modes = []
        real_open = builtins.open
        recorder = self

        def recording_open(file, mode="r", *args, **kwargs):
            try:
                recorder.opened.append(os.path.realpath(os.fspath(file)))
                recorder.modes.append(mode)
            except (TypeError, ValueError):
                pass
            return real_open(file, mode, *args, **kwargs)

        self._patch = mock.patch.object(builtins, "open", recording_open)
        self._patch.start()
        return self

    def __exit__(self, *exc_info):
        self._patch.stop()
        return False


def tree_snapshot(root):
    """The byte-level state of the tree under `root`: every directory, file
    (with its bytes) and symlink (with its target), in sorted order."""
    state = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        rel_dir = os.path.relpath(current, root)
        state.append(("dir", rel_dir))
        for name in sorted(files):
            path = os.path.join(current, name)
            rel = os.path.relpath(path, root)
            if os.path.islink(path):
                state.append(("link", rel, os.readlink(path)))
            else:
                with open(path, "rb") as handle:
                    state.append(("file", rel, handle.read()))
        for name in dirs:
            path = os.path.join(current, name)
            if os.path.islink(path):
                state.append(("dirlink", os.path.relpath(path, root), os.readlink(path)))
    return state


# ---------------------------------------------------------------------------
# AC-3 (TS-1, TM-1): the pip job form.
# ---------------------------------------------------------------------------

class TestPipJobFromThePreparedRequirementsForm(unittest.TestCase):
    ROOT = "/work/reviewed-project"
    PREPARED = "/scratch/pip-prepared-0001.txt"
    EXECUTABLE = "/x/pip-audit"
    TARGETS = (
        "requirements.txt",
        "x/requirements.txt",
        "pyproject.toml",
        "svc/pyproject.toml",
        "poetry.lock",
        "Pipfile.lock",
    )

    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.pip_entry = {e["ecosystem"]: e for e in registry["ecosystems"]}["pip"]

    def build(self, target, entry=None, **kwargs):
        return SCAN.build_scan_job(
            entry or self.pip_entry, target, self.ROOT, self.EXECUTABLE, **kwargs
        )

    def test_every_target_gets_the_prepared_requirements_vector(self):
        for target in self.TARGETS:
            with self.subTest(target=target):
                job = self.build(target, prepared_file=self.PREPARED)
                self.assertEqual(
                    job["argv"],
                    [self.EXECUTABLE, "-r", self.PREPARED] + JOB_TAIL,
                )
                self.assertEqual(job["cwd"], self.ROOT)
                self.assertEqual(job["manifest"], target)
                self.assertEqual(job["ecosystem"], "pip")

    def test_no_argv_element_names_the_project_root_or_the_reviewed_file(self):
        for target in self.TARGETS:
            job = self.build(target, prepared_file=self.PREPARED)
            for element in job["argv"]:
                with self.subTest(target=target, element=element):
                    self.assertNotIn(self.ROOT, element)
                    self.assertNotIn(target, element)
                    self.assertNotIn(os.path.basename(target), element)

    def test_without_a_prepared_file_every_target_is_rejected(self):
        for target in self.TARGETS:
            for kwargs in ({}, {"prepared_file": None}, {"prepared_file": ""}):
                with self.subTest(target=target, kwargs=kwargs):
                    with self.assertRaises(SCAN.JobConstructionError):
                        self.build(target, **kwargs)

    def test_an_entry_without_the_form_is_rejected(self):
        for mutate in (
            lambda e: e.pop("target_forms"),
            lambda e: e["target_forms"].pop("prepared_requirements"),
            lambda e: e.update(target_forms="prepared_requirements"),
            lambda e: e["target_forms"]["prepared_requirements"].pop("target_flag"),
            lambda e: e["target_forms"]["prepared_requirements"].update(target_flag=""),
            lambda e: e["target_forms"]["prepared_requirements"].pop("args"),
        ):
            entry = copy.deepcopy(self.pip_entry)
            mutate(entry)
            with self.subTest(entry=entry.get("target_forms")):
                with self.assertRaises(SCAN.JobConstructionError):
                    self.build("requirements.txt", entry=entry, prepared_file=self.PREPARED)

    def test_the_argv_follows_the_entry_that_is_passed_in(self):
        entry = copy.deepcopy(self.pip_entry)
        entry["target_forms"]["prepared_requirements"] = {
            "target_flag": "--requirement-file",
            "args": ["--alpha", "--format", "json", "--beta"],
        }
        for target in self.TARGETS:
            with self.subTest(target=target):
                job = self.build(target, entry=entry, prepared_file=self.PREPARED)
                self.assertEqual(
                    job["argv"],
                    [self.EXECUTABLE, "--requirement-file", self.PREPARED,
                     "--alpha", "--format", "json", "--beta"],
                )

    def test_the_job_form_is_built_without_reading_writing_or_launching(self):
        with mock.patch("builtins.open", side_effect=AssertionError("file opened")), \
                mock.patch("os.open", side_effect=AssertionError("file opened")), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("process launched")), \
                mock.patch("subprocess.run", side_effect=AssertionError("process launched")):
            job = self.build("requirements.txt", prepared_file="/definitely/not/real/p.txt")
        self.assertEqual(job["argv"][:3], [self.EXECUTABLE, "-r", "/definitely/not/real/p.txt"])

    def test_the_source_of_build_scan_job_names_neither_pip_flag(self):
        source = inspect.getsource(SCAN.build_scan_job)
        self.assertNotIn("--no-deps", source)
        self.assertNotIn("--disable-pip", source)

    def test_the_directory_and_reviewed_file_forms_no_longer_exist(self):
        self.assertFalse(hasattr(SCAN, "_pip_target"))


# ---------------------------------------------------------------------------
# AC-4 (TS-2, TM-2, TM-3, TM-4): extraction from requirements files.
# ---------------------------------------------------------------------------

class ExtractionCase(unittest.TestCase):
    """A project root and an outside directory beside it, in one temporary
    tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.base = base
        self.root = base / "project"
        self.outside = base / "outside"
        self.root.mkdir()
        self.outside.mkdir()

    def write(self, rel, data, base=None):
        path = (base or self.root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def extract(self, rel="requirements.txt"):
        return SCAN.extract_pip_manifest_pins(self.root, rel)

    def assertWellFormed(self, result):
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        pins, excluded = result
        self.assertIsInstance(pins, set)
        self.assertIsInstance(excluded, int)
        self.assertGreaterEqual(excluded, 0)
        for name, version in pins:
            self.assertEqual(name, SCAN.canonical_pip_name(name))
            self.assertTrue(SCAN._pip_pin_is_valid(name, version), (name, version))


class TestRequirementsPinRule(ExtractionCase):
    PIN_CASES = [
        ("exact", "django==3.2.0", {("django", "3.2.0")}),
        ("extras", "Requests[security, socks]==2.31.0", {("requests", "2.31.0")}),
        ("spaces around the operator", "Flask_Login  ==  0.6.3", {("flask-login", "0.6.3")}),
        ("space before the operator", "pkg ==1.0", {("pkg", "1.0")}),
        ("hash option in the = form", "django==3.2.0 --hash=sha256:aaaa --hash=sha256:bbbb",
         {("django", "3.2.0")}),
        ("hash option in the separated form", "django==3.2.0 --hash sha256:aaaa --hash sha256:bbbb",
         {("django", "3.2.0")}),
        ("spaces and hash options together", "Django == 3.2.0 \\\n    --hash=sha256:aaaa \\\n    --hash sha256:bbbb\n",
         {("django", "3.2.0")}),
        ("local version label", "torch==2.1.0+cpu", {("torch", "2.1.0+cpu")}),
        ("epoch and post release", "pkg==1!2.0.post1", {("pkg", "1!2.0.post1")}),
        ("underscore in the version", "pkg==1.0_1", {("pkg", "1.0_1")}),
        ("trailing comment", "django==3.2.0  # pinned on purpose", {("django", "3.2.0")}),
        ("non-canonical name spelling", "Foo.Bar__Baz==1.0", {("foo-bar-baz", "1.0")}),
    ]

    EXCLUDED_CASES = [
        ("editable dot", "-e .", 1),
        ("editable with =", "--editable=./x", 1),
        ("editable with a name", "-e git+https://example.invalid/r.git#egg=pkg", 1),
        ("two editables on one line", "-e ./a -e ./b", 2),
        ("local path", "./local/pkg", 1),
        ("absolute local path", "/abs/path/pkg-1.0.tar.gz", 1),
        ("url", "https://example.invalid/pkg-1.0.tar.gz", 1),
        ("vcs reference", "git+https://example.invalid/r.git@main#egg=pkg", 1),
        ("direct reference", "pkg @ https://example.invalid/pkg-1.0-py3-none-any.whl", 1),
        ("marker", 'pkg==1.0 ; python_version < "3.9"', 1),
        ("marker without spaces", 'pkg==1.0;sys_platform=="linux"', 1),
        ("wildcard version", "pkg==1.*", 1),
        ("arbitrary equality", "pkg===1.0", 1),
        ("range", "pkg>=1.0,<2", 1),
        ("compatible release", "pkg~=1.4", 1),
        ("exclusion", "pkg!=1.0", 1),
        ("pair of pins", "pkg==1.0,==1.1", 1),
        ("bare name", "pkg", 1),
        ("bare name with extras", "pkg[extra]", 1),
        ("unexpected version character", "pkg==1.0/evil", 1),
        ("fragment glued to the version", "pkg==1.0#frag", 1),
        ("trailing words after the pin", "pkg==1.0 extra", 1),
        ("an unrelated per-requirement option", "pkg==1.0 --global-option=--x", 1),
        ("abbreviated option", "--trusted example.invalid", 1),
        ("abbreviated include option", "--require other.txt", 1),
        ("unsplittable option line", '--index-url "https://example.invalid/simple', 1),
        ("include leaving the root", "-r ../outside/outside.txt", 1),
        ("include through an absolute path outside the root", None, 1),
        ("url include", "-r https://example.invalid/r.txt", 1),
        ("missing include", "-r missing.txt", 1),
        ("empty include", "-r", 1),
    ]

    NOTHING_CASES = [
        ("constraint file", "-c constraints.txt"),
        ("constraint with =", "--constraint=constraints.txt"),
        ("index url", "--index-url https://example.invalid/simple"),
        ("short index url", "-i https://example.invalid/simple"),
        ("extra index url", "--extra-index-url=https://example.invalid/simple"),
        ("find links", "-f ./wheels"),
        ("trusted host", "--trusted-host example.invalid"),
        ("no binary", "--no-binary :all:"),
        ("self include", "-r requirements.txt"),
        ("blank and comment lines", "\n# just a comment\n\n"),
    ]

    def setUp(self):
        super().setUp()
        self.write("constraints.txt", "django==1.0\n")
        self.write("outside.txt", "outsider==1.0\n", base=self.outside)

    def test_a_pin_line_gives_exactly_its_canonical_pin(self):
        for label, line, expected in self.PIN_CASES:
            with self.subTest(label=label):
                self.write("requirements.txt", line + "\n")
                result = self.extract()
                self.assertWellFormed(result)
                self.assertEqual(result, (expected, 0))

    def test_a_line_that_is_not_a_pin_adds_to_the_excluded_count_only(self):
        for label, line, count in self.EXCLUDED_CASES:
            if line is None:
                line = f"-r {self.outside / 'outside.txt'}"
            with self.subTest(label=label):
                self.write("requirements.txt", line + "\n")
                result = self.extract()
                self.assertWellFormed(result)
                self.assertEqual(result, (set(), count))

    def test_options_that_carry_no_requirement_add_nothing(self):
        for label, line in self.NOTHING_CASES:
            with self.subTest(label=label):
                self.write("requirements.txt", line + "\n")
                result = self.extract()
                self.assertWellFormed(result)
                self.assertEqual(result, (set(), 0))

    def test_a_pin_in_an_in_root_include_is_extracted(self):
        self.write("requirements.txt", "-r base/common.txt\ndjango==3.2.0\n")
        self.write("base/common.txt", "Requests[security]==2.31.0 --hash=sha256:aaaa\n")
        result = self.extract()
        self.assertEqual(result, ({("django", "3.2.0"), ("requests", "2.31.0")}, 0))

    def test_an_include_is_taken_relative_to_the_including_file(self):
        self.write("svc/requirements.txt", "-r ../shared/common.txt\n")
        self.write("shared/common.txt", "pkg==1.0\n")
        self.assertEqual(self.extract("svc/requirements.txt"), ({("pkg", "1.0")}, 0))

    def test_mixed_fixture_counts_each_excluded_line_once(self):
        lines = [
            "django==3.2.0",
            "-e .",
            "--editable=./x",
            "./local/pkg",
            "https://example.invalid/pkg-1.0.tar.gz",
            "git+https://example.invalid/r.git#egg=pkg",
            'pkg==1.0 ; python_version < "3.9"',
            "other==1.*",
            "other===1.0",
            "other>=1,<2",
            "other~=1.4",
            "other",
            "--trusted example.invalid",
            '--index-url "https://example.invalid/simple',
            "-r ../outside/outside.txt",
            "-r https://example.invalid/r.txt",
            "-r missing.txt",
            "-c constraints.txt",
            "--index-url https://example.invalid/simple",
        ]
        self.write("requirements.txt", "\n".join(lines) + "\n")
        pins, excluded = self.extract()
        self.assertEqual(pins, {("django", "3.2.0")})
        self.assertEqual(excluded, 16)

    def test_a_target_that_cannot_be_read_counts_one(self):
        (self.root / "dir-target").mkdir()
        self.write("binary.txt", b"\xff\xfe\x00\x01 not utf-8 \x80\x81")
        os.symlink(self.outside / "outside.txt", self.root / "link.txt")
        for label, rel in (
            ("missing", "nowhere/requirements.txt"),
            ("a directory", "dir-target"),
            ("not UTF-8", "binary.txt"),
            ("a symlink leaving the root", "link.txt"),
            ("an absolute path outside the root", str(self.outside / "outside.txt")),
            ("a path escaping with ..", "../outside/outside.txt"),
        ):
            with self.subTest(label=label):
                result = self.extract(rel)
                self.assertWellFormed(result)
                self.assertEqual(result, (set(), 1))

    def test_an_unreadable_include_counts_one_and_the_rest_is_still_extracted(self):
        self.write("requirements.txt", "-r bad.txt\n-r dir-include\npkg==1.0\n")
        self.write("bad.txt", b"\xff\xfe\x00 broken")
        (self.root / "dir-include").mkdir()
        self.assertEqual(self.extract(), ({("pkg", "1.0")}, 2))

    def test_a_byte_order_mark_does_not_hide_the_first_line(self):
        self.write("requirements.txt", b"\xef\xbb\xbfdjango==3.2.0\r\nrequests==2.0.0\r\n")
        self.assertEqual(self.extract(), ({("django", "3.2.0"), ("requests", "2.0.0")}, 0))

    def test_a_nested_target_is_extracted_from_its_own_path(self):
        self.write("x/requirements.txt", "pkg==1.0\n")
        self.assertEqual(self.extract("x/requirements.txt"), ({("pkg", "1.0")}, 0))

    def test_the_same_input_gives_the_same_output(self):
        self.write("requirements.txt", "b==2.0\na==1.0\n-r more.txt\nbare\n")
        self.write("more.txt", "c==3.0\n")
        first = self.extract()
        second = self.extract()
        self.assertEqual(first, second)
        self.assertEqual(first, ({("a", "1.0"), ("b", "2.0"), ("c", "3.0")}, 1))


class TestRequirementsWalkContainment(ExtractionCase):
    def setUp(self):
        super().setUp()
        self.write("constraints.txt", "constrained==1.0\n")
        self.write("evil.txt", "outsider==1.0\n", base=self.outside)
        self.write(
            "requirements.txt",
            "django==3.2.0\n"
            "-r base/common.txt\n"
            "-c constraints.txt\n"
            "-r base/../base/common.txt\n"
            "-r ../outside/evil.txt\n",
        )
        self.write(
            "base/common.txt",
            "requests==2.31.0\n"
            "-r ../requirements.txt\n"
            f"-r {self.outside / 'evil.txt'}\n"
            "--constraint ../constraints.txt\n",
        )
        os.symlink(self.outside / "evil.txt", self.root / "linked.txt")

    def run_extract(self, rel="requirements.txt"):
        with OpenRecorder() as recorder, NetworkGuard() as network, ProcessGuard() as processes:
            result = self.extract(rel)
        return result, recorder, network, processes

    def test_only_in_root_files_are_opened_and_each_exactly_once(self):
        result, recorder, _network, _processes = self.run_extract()
        root = os.path.realpath(self.root)
        self.assertEqual(
            sorted(recorder.opened),
            sorted([os.path.join(root, "requirements.txt"), os.path.join(root, "base", "common.txt")]),
        )
        self.assertEqual(len(recorder.opened), len(set(recorder.opened)))
        self.assertEqual(result, ({("django", "3.2.0"), ("requests", "2.31.0")}, 2))

    def test_a_constraint_file_and_an_outside_file_are_never_opened(self):
        _result, recorder, _network, _processes = self.run_extract()
        self.assertNotIn(os.path.realpath(self.root / "constraints.txt"), recorder.opened)
        self.assertNotIn(os.path.realpath(self.outside / "evil.txt"), recorder.opened)

    def test_a_symlink_include_leaving_the_root_is_never_opened(self):
        self.write("requirements.txt", "-r linked.txt\npkg==1.0\n")
        result, recorder, _network, _processes = self.run_extract()
        self.assertNotIn(os.path.realpath(self.outside / "evil.txt"), recorder.opened)
        self.assertEqual(result, ({("pkg", "1.0")}, 1))

    def test_an_include_cycle_ends(self):
        self.write("a/requirements.txt", "-r ../b/requirements.txt\npkg==1.0\n")
        self.write("b/requirements.txt", "-r ../a/requirements.txt\nother==2.0\n")
        result, recorder, _network, _processes = self.run_extract("a/requirements.txt")
        self.assertEqual(result, ({("pkg", "1.0"), ("other", "2.0")}, 0))
        self.assertEqual(len(recorder.opened), len(set(recorder.opened)))

    def test_nothing_is_written_no_process_starts_and_no_network_is_used(self):
        before = tree_snapshot(self.base)
        _result, recorder, network, processes = self.run_extract()
        self.assertEqual(tree_snapshot(self.base), before)
        for mode in recorder.modes:
            self.assertNotIn("w", mode)
            self.assertNotIn("a", mode)
            self.assertNotIn("x", mode)
            self.assertNotIn("+", mode)
        self.assertEqual(network.calls, [])
        self.assertEqual(processes.calls, [])


class TestRequirementsExtractionNeverRaises(ExtractionCase):
    POOL = [
        "django==3.2.0", "requests[security]==2.31.0", "pkg", "pkg>=1", "pkg==1.*", "-e .",
        "-r requirements.txt", "-r sub/other.txt", "-r ../outside/outside.txt", "-c constraints.txt",
        "--hash=sha256:aaaa", "--hash", "--index-url", '"', "'", "\\", "#", "; python_version",
        "@", "https://example.invalid/x", "==", "[", "]", " ", "\t", "\x00", "﻿", "é", "\r",
        "-", "--", "---", "--trusted", "-r", "-e", "-c", "-i", "-f", "-C", "pkg==", "==1.0",
    ]

    def test_random_text_never_raises(self):
        rng = random.Random(20240601)
        self.write("sub/other.txt", "inner==1.0\n")
        for index in range(250):
            pieces = [rng.choice(self.POOL) for _ in range(rng.randint(0, 24))]
            separators = [rng.choice([" ", "\n", "\n", "\\\n", ""]) for _ in pieces]
            text = "".join(piece + sep for piece, sep in zip(pieces, separators))
            self.write("requirements.txt", text)
            with self.subTest(index=index):
                self.assertWellFormed(self.extract())

    def test_random_bytes_never_raise(self):
        rng = random.Random(7)
        for index in range(120):
            data = bytes(rng.randrange(256) for _ in range(rng.randint(0, 200)))
            self.write("requirements.txt", data)
            with self.subTest(index=index):
                self.assertWellFormed(self.extract())

    def test_malformed_targets_never_raise(self):
        (self.root / "requirements.txt").mkdir()
        for label, rel in (
            ("a directory", "requirements.txt"),
            ("an empty string", ""),
            ("a NUL byte in the path", "a\x00b/requirements.txt"),
            ("an unrelated basename", "setup.cfg"),
            ("a very deep path", "/".join(["d"] * 300) + "/requirements.txt"),
        ):
            with self.subTest(label=label):
                self.assertWellFormed(self.extract(rel))

    def test_a_missing_project_root_never_raises(self):
        for root in (None, "", self.root / "no-such-root"):
            with self.subTest(root=root):
                self.assertWellFormed(SCAN.extract_pip_manifest_pins(root, "requirements.txt"))


# ---------------------------------------------------------------------------
# AC-5 (TS-2): extraction from pyproject.toml.
# ---------------------------------------------------------------------------

@unittest.skipIf(SCAN.tomllib is None, "this interpreter has no TOML parser")
class TestPyprojectExtraction(ExtractionCase):
    def extract_text(self, text, rel="pyproject.toml"):
        self.write(rel, text)
        result = self.extract(rel)
        self.assertWellFormed(result)
        return result

    def test_project_dependencies_follow_the_requirements_pin_rule(self):
        result = self.extract_text(
            "[project]\n"
            'name = "demo"\n'
            'version = "1"\n'
            "dependencies = [\n"
            '  "Django==3.2.0",\n'
            '  "requests[security] == 2.31.0",\n'
            '  "flask>=2",\n'
            '  "numpy",\n'
            '  "pkg==1.*",\n'
            "  \"pkg2==1.0 ; python_version < '3.9'\",\n"
            '  "pkg3 @ https://example.invalid/p.whl",\n'
            "]\n"
        )
        self.assertEqual(result, ({("django", "3.2.0"), ("requests", "2.31.0")}, 5))

    def test_a_nested_pyproject_is_extracted_from_its_own_path(self):
        result = self.extract_text(
            '[project]\nname = "d"\nversion = "1"\ndependencies = ["pkg==1.0"]\n',
            rel="svc/pyproject.toml",
        )
        self.assertEqual(result, ({("pkg", "1.0")}, 0))

    def test_poetry_entries_are_pins_only_for_an_exact_string_value(self):
        result = self.extract_text(
            "[tool.poetry.dependencies]\n"
            'python = "^3.9"\n'
            'django = "==3.2.0"\n'
            'requests = "2.31.0"\n'
            'flask = "^2.0"\n'
            'numpy = "~1.2"\n'
            'pandas = "*"\n'
            'scipy = ">=1,<2"\n'
            'pillow = {version = "==9.0.0", extras = ["x"]}\n'
            'wild = "==1.*"\n'
            "[tool.poetry.dev-dependencies]\n"
            'pytest = "==7.0.0"\n'
        )
        self.assertEqual(result, ({("django", "3.2.0"), ("pytest", "7.0.0")}, 7))

    def test_the_python_entry_is_ignored_and_not_counted(self):
        result = self.extract_text(
            '[tool.poetry.dependencies]\npython = "^3.9"\nPython = ">=3"\ndjango = "==3.2.0"\n'
        )
        self.assertEqual(result, ({("django", "3.2.0")}, 0))

    def test_tables_the_resolver_never_reads_contribute_nothing(self):
        result = self.extract_text(
            "[project.optional-dependencies]\n"
            'dev = ["pytest==7.0.0", "other"]\n'
            "[dependency-groups]\n"
            'test = ["tox==4.0.0"]\n'
            "[tool.poetry.group.dev.dependencies]\n"
            'black = "==23.1.0"\n'
            'isort = "^5"\n'
        )
        self.assertEqual(result, (set(), 0))

    def test_unexpected_shapes_each_add_one_excluded_item(self):
        cases = [
            ("a non-string list item", '[project]\ndependencies = ["pkg==1.0", 5]\n', ({("pkg", "1.0")}, 1)),
            ("a table in the list", '[project]\ndependencies = ["pkg==1.0", {a = 1}]\n', ({("pkg", "1.0")}, 1)),
            ("a non-list dependencies value", '[project]\ndependencies = "pkg==1.0"\n', (set(), 1)),
            ("a non-mapping poetry table", '[tool.poetry]\ndependencies = "x"\n', (set(), 1)),
            ("a non-mapping dev table", '[tool.poetry]\ndev-dependencies = ["x"]\n', (set(), 1)),
            ("a dynamic-only declaration", '[project]\nname = "d"\ndynamic = ["dependencies"]\n', (set(), 1)),
        ]
        for label, text, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(self.extract_text(text), expected)

    def test_a_static_list_beats_a_dynamic_entry(self):
        result = self.extract_text(
            '[project]\nname = "d"\ndynamic = ["dependencies"]\ndependencies = ["pkg==1.0"]\n'
        )
        self.assertEqual(result, ({("pkg", "1.0")}, 0))

    def test_no_declaration_gives_no_pins_and_a_zero_count(self):
        for label, text in (
            ("an empty file", ""),
            ("only comments", "# nothing here\n"),
            ("unrelated tables", "[tool.black]\nline-length = 100\n"),
            ("a project table without dependencies", '[project]\nname = "d"\nversion = "1"\n'),
            ("an empty static list", '[project]\ndependencies = []\n'),
        ):
            with self.subTest(label=label):
                self.assertEqual(self.extract_text(text), (set(), 0))

    def test_a_file_that_cannot_be_used_gives_no_pins_and_a_count_of_one(self):
        self.write("bad-utf8/pyproject.toml", b"\xff\xfe[project]\n\x80")
        self.write("invalid/pyproject.toml", "[project\ndependencies = [\n")
        (self.root / "dir" / "pyproject.toml").mkdir(parents=True)
        self.write("pyproject.toml", '[project]\ndependencies = ["pkg==1.0"]\n', base=self.outside)
        (self.root / "link").mkdir()
        os.symlink(self.outside / "pyproject.toml", self.root / "link" / "pyproject.toml")
        for label, rel in (
            ("invalid TOML", "invalid/pyproject.toml"),
            ("non-UTF-8 content", "bad-utf8/pyproject.toml"),
            ("a directory", "dir/pyproject.toml"),
            ("a missing file", "none/pyproject.toml"),
            ("a symlink leaving the root", "link/pyproject.toml"),
            ("a path escaping with ..", "../outside/pyproject.toml"),
        ):
            with self.subTest(label=label):
                result = self.extract(rel)
                self.assertWellFormed(result)
                self.assertEqual(result, (set(), 1))

    def test_a_missing_toml_parser_gives_no_pins_and_a_count_of_one(self):
        self.write("pyproject.toml", '[project]\ndependencies = ["pkg==1.0"]\n')
        with mock.patch.object(SCAN, "tomllib", None):
            self.assertEqual(self.extract("pyproject.toml"), (set(), 1))

    def test_a_pyproject_read_opens_only_that_file_for_reading(self):
        self.write("pyproject.toml", '[project]\ndependencies = ["pkg==1.0"]\n')
        before = tree_snapshot(self.base)
        with OpenRecorder() as recorder, NetworkGuard() as network, ProcessGuard() as processes:
            self.extract("pyproject.toml")
        self.assertEqual(recorder.opened, [os.path.realpath(self.root / "pyproject.toml")])
        self.assertEqual(tree_snapshot(self.base), before)
        self.assertEqual(network.calls, [])
        self.assertEqual(processes.calls, [])

    def test_random_toml_never_raises(self):
        rng = random.Random(11)
        pool = [
            "[project]", "[tool.poetry.dependencies]", "[tool.poetry]", "[tool]", "dependencies = [",
            "dependencies = 5", "dependencies = []", '"pkg==1.0",', "]", 'django = "==1.0"',
            "python = 3", "dynamic = [1]", 'dynamic = ["dependencies"]', "x = {", "}", "[[tool.a]]",
            "project = 1", "tool = 1", "tool.poetry = 2", "dev-dependencies = {}",
        ]
        for index in range(150):
            text = "\n".join(rng.choice(pool) for _ in range(rng.randint(0, 14)))
            with self.subTest(index=index):
                self.extract_text(text)

    def test_a_deeply_nested_array_never_raises(self):
        self.write("pyproject.toml", "[project]\ndependencies = " + "[" * 5000 + "]" * 5000 + "\n")
        self.assertWellFormed(self.extract("pyproject.toml"))


# ---------------------------------------------------------------------------
# The scan flow (AC-6, AC-7, AC-8).
# ---------------------------------------------------------------------------

class ManifestScanCase(unittest.TestCase):
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

    def scan_raw(self, changed_files):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}), \
                mock.patch.object(tempfile, "tempdir", str(self.systmp)):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def scan(self, changed_files):
        result = self.scan_raw(changed_files)
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


DJANGO = "django==3.2.0"


class TestPinnedUnitsLaunchOnPreparedFiles(ManifestScanCase):
    def test_a_fully_pinned_requirements_unit_launches_once_with_the_sorted_canonical_pins(self):
        self.write("requirements.txt", "Requests[security]==2.31.0\nDjango == 3.2.0 --hash=sha256:aa\n")
        self.install_pip_audit()
        result = self.scan(["requirements.txt"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.lines_of(calls[0]), ["django==3.2.0", "requests==2.31.0"])
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])
        self.assertTrue(result["summary"].startswith("Scanned pip;"), result["summary"])

    def test_the_launched_argv_is_the_prepared_requirements_form_from_the_project_root(self):
        self.write("requirements.txt", DJANGO + "\n")
        stub = self.install_pip_audit()
        self.scan(["requirements.txt"])
        call = self.calls()[0]
        argv = call["argv"]
        self.assertEqual(argv[0], str(stub))
        self.assertEqual(argv[1], "-r")
        self.assertEqual(argv[3:], JOB_TAIL)
        self.assertEqual(call["cwd"], str(self.root))
        for element in argv:
            self.assertNotIn(str(self.root), element)
            self.assertNotIn("requirements.txt", element)

    def test_a_pinned_pyproject_unit_launches_once_with_its_pins(self):
        self.write(
            "pyproject.toml",
            '[project]\nname = "d"\nversion = "1"\ndependencies = ["Django==3.2.0", "requests[security]==2.31.0"]\n',
        )
        self.install_pip_audit()
        result = self.scan(["pyproject.toml"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.lines_of(calls[0]), ["django==3.2.0", "requests==2.31.0"])
        self.assertEqual(calls[0]["argv"][3:], JOB_TAIL)
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])

    def test_a_poetry_exact_pin_unit_launches_once(self):
        self.write("svc/pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.9"\ndjango = "==3.2.0"\n')
        self.install_pip_audit(vulnerable=[DJANGO])
        result = self.scan(["svc/pyproject.toml"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual({f["file"] for f in result["findings"]}, {"svc/pyproject.toml"})

    def test_findings_carry_the_reviewed_manifest_as_their_file(self):
        self.write("x/requirements.txt", DJANGO + "\n")
        self.install_pip_audit(vulnerable=[DJANGO])
        result = self.scan(["x/requirements.txt"])
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["file"], "x/requirements.txt")
        self.assertEqual(finding["severity"], "critical")
        self.assertIn("affected: 3.2.0", finding["description"])

    def test_a_pin_in_an_in_root_include_is_audited(self):
        self.write("requirements.txt", "-r base.txt\n")
        self.write("base.txt", DJANGO + "\n")
        self.install_pip_audit(vulnerable=[DJANGO])
        result = self.scan(["requirements.txt"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(result["findings"]), 1)
        self.assertFalse(result["skipped"], result)


class TestMixedUnits(ManifestScanCase):
    def test_a_mixed_requirements_unit_audits_its_pins_and_reports_the_entries_token(self):
        self.write("requirements.txt", f"{DJANGO}\nflask>=2\n-e .\n")
        self.install_pip_audit(vulnerable=[DJANGO])
        result = self.scan(["requirements.txt"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.lines_of(calls[0]), [DJANGO])
        self.assertEqual(len(result["findings"]), 1)
        self.assertIn(ENTRIES_UNPINNABLE, result["skip_reason"])
        self.assertEqual(result["skip_reason"], ENTRIES_UNPINNABLE)
        self.assertTrue(result["skipped"])
        self.assertTrue(result["summary"].startswith("Scanned pip;"), result["summary"])

    def test_a_mixed_pyproject_unit_audits_its_pins_and_reports_the_entries_token(self):
        self.write(
            "pyproject.toml",
            '[project]\nname = "d"\nversion = "1"\ndependencies = ["django==3.2.0", "flask>=2"]\n',
        )
        self.install_pip_audit(vulnerable=[DJANGO])
        result = self.scan(["pyproject.toml"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["skip_reason"], ENTRIES_UNPINNABLE)
        self.assertTrue(result["skipped"])
        self.assertTrue(result["summary"].startswith("Scanned pip;"), result["summary"])

    def test_the_lockfile_note_never_appears_for_a_manifest_unit(self):
        self.write("requirements.txt", f"{DJANGO}\nflask>=2\n")
        self.install_pip_audit()
        result = self.scan(["requirements.txt"])
        self.assertNotIn("pip_lockfile_entries_unpinnable", result["summary"])
        self.assertNotIn("pip_lockfile_entries_unpinnable", result["skip_reason"])
        self.assertNotIn("lockfile", result["summary"])

    def test_a_failed_launch_of_a_mixed_unit_reports_the_run_reason_and_completes_nothing(self):
        self.write("requirements.txt", f"{DJANGO}\nflask>=2\n")
        self.install_pip_audit(fail_lines=[DJANGO])
        result = self.scan(["requirements.txt"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["findings"], [])
        self.assertIn("pip_empty_output", result["skip_reason"])
        self.assertTrue(result["summary"].startswith("Scan skipped:"), result["summary"])


class TestUnitsWithNoAuditableItem(ManifestScanCase):
    REQUIREMENTS_CASES = [
        ("bare names", "django\nflask\n"),
        ("ranges only", "django>=3\nflask~=2.0\n"),
        ("only editable and local items", "-e .\n./local/pkg\n"),
        ("only urls", "https://example.invalid/pkg-1.0.tar.gz\n"),
        ("only an unsatisfiable include", "-r missing.txt\n"),
        ("only options", "--index-url https://example.invalid/simple\n"),
        ("an empty file", ""),
        ("not UTF-8", b"\xff\xfe\x00\x80"),
    ]
    PYPROJECT_CASES = [
        ("ranges", '[project]\nname = "d"\nversion = "1"\ndependencies = ["django>=3", "flask"]\n'),
        ("a dynamic-only declaration", '[project]\nname = "d"\ndynamic = ["dependencies"]\n'),
        ("no declaration", "[tool.black]\nline-length = 100\n"),
        ("invalid TOML", "[project\n"),
        ("non-UTF-8 content", b"\xff\xfe[project]\n"),
        ("poetry without exact pins", '[tool.poetry.dependencies]\npython = "^3.9"\ndjango = "^3.2"\nflask = "2.0.0"\n'),
        ("an empty static list", "[project]\ndependencies = []\n"),
    ]

    def test_a_requirements_unit_without_a_pin_never_starts_the_scanner(self):
        for label, content in self.REQUIREMENTS_CASES:
            with self.subTest(label=label):
                self.write("requirements.txt", content)
                self.install_pip_audit()
                result = self.scan(["requirements.txt"])
                self.assertNotLaunched()
                self.assertEqual(result["skip_reason"], UNPINNABLE)
                self.assertTrue(result["skipped"])
                self.assertEqual(result["findings"], [])
                self.assertNotIn(ENTRIES_UNPINNABLE, result["skip_reason"])
                self.assertTrue(result["summary"].startswith("Scan skipped:"), result["summary"])

    @unittest.skipIf(SCAN.tomllib is None, "this interpreter has no TOML parser")
    def test_a_pyproject_unit_without_a_pin_never_starts_the_scanner(self):
        for label, content in self.PYPROJECT_CASES:
            with self.subTest(label=label):
                self.write("pyproject.toml", content)
                self.install_pip_audit()
                result = self.scan(["pyproject.toml"])
                self.assertNotLaunched()
                self.assertEqual(result["skip_reason"], UNPINNABLE)
                self.assertTrue(result["skipped"])
                self.assertNotIn(ENTRIES_UNPINNABLE, result["skip_reason"])

    def test_a_missing_target_file_reports_the_unpinnable_token_alone(self):
        self.install_pip_audit()
        result = self.scan(["requirements.txt"])
        self.assertNotLaunched()
        self.assertEqual(result["skip_reason"], UNPINNABLE)

    def test_a_missing_toml_parser_is_reported_before_any_extraction(self):
        self.write("pyproject.toml", '[project]\nname = "d"\ndependencies = ["django==3.2.0"]\n')
        self.install_pip_audit()
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["pyproject.toml"])
        self.assertNotLaunched()
        self.assertEqual(result["skip_reason"], SCAN.PIP_TOML_PARSER_UNAVAILABLE)

    def test_a_missing_toml_parser_does_not_affect_a_requirements_unit(self):
        self.write("requirements.txt", DJANGO + "\n")
        self.install_pip_audit()
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["requirements.txt"])
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(result["skipped"], result)

    def test_the_unit_does_not_complete_so_pip_is_not_counted_as_scanned(self):
        self.write("requirements.txt", "django\n")
        self.install_pip_audit()
        result = self.scan(["requirements.txt"])
        self.assertNotIn("Scanned pip", result["summary"])


class TestOneNameAtTwoVersions(ManifestScanCase):
    def setUp(self):
        super().setUp()
        self.write("requirements.txt", "django==3.2.0\n-r extra.txt\n")
        self.write("extra.txt", "django==4.0.0\nrequests==2.31.0\n")
        self.install_pip_audit(vulnerable=["django==3.2.0", "django==4.0.0"])

    def test_two_prepared_files_and_two_launches_in_group_order(self):
        result = self.scan(["requirements.txt"])
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.lines_of(calls[0]), ["django==3.2.0", "requests==2.31.0"])
        self.assertEqual(self.lines_of(calls[1]), ["django==4.0.0"])
        self.assertNotEqual(calls[0]["path"], calls[1]["path"])
        for call in calls:
            names = [line.partition("==")[0] for line in self.lines_of(call)]
            self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(result["findings"]), 2)
        self.assertFalse(result["skipped"], result)

    def test_scanning_the_same_input_twice_is_byte_identical(self):
        first = self.scan(["requirements.txt"])
        first_calls = self.calls()
        self.record_path.unlink()
        second = self.scan(["requirements.txt"])
        second_calls = self.calls()
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual(
            [call["requirements"] for call in first_calls],
            [call["requirements"] for call in second_calls],
        )

    def test_one_run_that_does_not_complete_leaves_the_other_findings(self):
        self.install_pip_audit(vulnerable=["django==3.2.0"], fail_lines=["django==4.0.0"])
        result = self.scan(["requirements.txt"])
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["skip_reason"], "pip_empty_output")
        self.assertTrue(result["skipped"])
        self.assertTrue(result["summary"].startswith("Scanned pip;"), result["summary"])

    def test_every_run_that_does_not_complete_reports_its_reason_once(self):
        self.install_pip_audit(fail_lines=["django==3.2.0", "django==4.0.0"])
        result = self.scan(["requirements.txt"])
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(result["skip_reason"], "pip_empty_output")
        self.assertEqual(result["findings"], [])
        self.assertTrue(result["summary"].startswith("Scan skipped:"), result["summary"])


class TestUntrustedTextStaysOutOfTheResult(ManifestScanCase):
    NAMES = ("zqx-secret-pkg", "zqx-range-pkg", "zqx-pinned-pkg", "zqx_local_pkg", "zqx-marker-pkg")
    PATHS = ("zqx-outside-dir", "zqx-secret-include.txt", "zqx-missing-dir")

    def test_neither_skip_reason_nor_summary_carries_a_name_a_path_or_the_root(self):
        self.write(
            "requirements.txt",
            "zqx-pinned-pkg==1.2.3\n"
            "zqx-range-pkg>=1.0\n"
            "zqx-secret-pkg\n"
            "./zqx_local_pkg\n"
            'zqx-marker-pkg==1.0 ; python_version < "3.9"\n'
            "-r ../zqx-outside-dir/zqx-secret-include.txt\n"
            "-r zqx-missing-dir/zqx-secret-include.txt\n",
        )
        self.install_pip_audit(vulnerable=["zqx-pinned-pkg==1.2.3"])
        result = self.scan(["requirements.txt"])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(result["skip_reason"], ENTRIES_UNPINNABLE)
        for field in ("skip_reason", "summary"):
            text = result[field]
            for needle in self.NAMES + self.PATHS + (str(self.root), str(self.base), self.root.name):
                with self.subTest(field=field, needle=needle):
                    self.assertNotIn(needle, text)

    def test_a_unit_with_nothing_to_audit_leaks_nothing_either(self):
        self.write(
            "requirements.txt",
            "zqx-secret-pkg>=1\n./zqx_local_pkg\n-r zqx-missing-dir/zqx-secret-include.txt\n",
        )
        self.install_pip_audit()
        result = self.scan(["requirements.txt"])
        self.assertEqual(result["skip_reason"], UNPINNABLE)
        for field in ("skip_reason", "summary"):
            for needle in self.NAMES + self.PATHS + (str(self.root), str(self.base)):
                with self.subTest(field=field, needle=needle):
                    self.assertNotIn(needle, result[field])


class TestPreparedFilesAreOwnerOnlyAndRemoved(ManifestScanCase):
    def assertPreparedFilesGone(self, paths):
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(os.path.exists(path))
                self.assertFalse(Path(path).resolve().is_relative_to(self.root))
                self.assertTrue(Path(path).is_relative_to(self.systmp))
        self.assertEqual(os.listdir(self.systmp), [])

    def assertOwnerOnly(self, modes):
        self.assertTrue(modes)
        for mode in modes:
            self.assertEqual(stat.S_IMODE(mode) & 0o077, 0, oct(mode))

    def test_normal_completion(self):
        self.write("requirements.txt", "a==1.0\n-r extra.txt\n")
        self.write("extra.txt", "a==2.0\n")
        self.install_pip_audit()
        before = tree_snapshot(self.root)
        self.scan(["requirements.txt"])
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertOwnerOnly([call["mode"] for call in calls])
        self.assertPreparedFilesGone([call["path"] for call in calls])
        self.assertEqual(tree_snapshot(self.root), before)

    def test_a_launch_that_does_not_complete(self):
        self.write("requirements.txt", "a==1.0\nflask>=2\n")
        self.install_pip_audit(fail_lines=["a==1.0"])
        before = tree_snapshot(self.root)
        result = self.scan(["requirements.txt"])
        self.assertTrue(result["skipped"])
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertOwnerOnly([call["mode"] for call in calls])
        self.assertPreparedFilesGone([call["path"] for call in calls])
        self.assertEqual(tree_snapshot(self.root), before)

    def test_an_exception_in_the_execution_step_propagates_and_the_files_are_removed(self):
        self.write("requirements.txt", "a==1.0\n-r extra.txt\n")
        self.write("extra.txt", "a==2.0\n")
        self.install_pip_audit()
        before = tree_snapshot(self.root)
        seen = []

        def explode(job):
            for name in sorted(os.listdir(self.systmp)):
                path = os.path.join(self.systmp, name)
                seen.append((path, os.stat(path).st_mode))
            raise RuntimeError("injected")

        with mock.patch.object(SCAN, "run_ecosystem_command", explode):
            with self.assertRaises(RuntimeError):
                self.scan_raw(["requirements.txt"])
        self.assertEqual(len(seen), 2)  # both prepared files exist when the launch step fails
        self.assertOwnerOnly([mode for _path, mode in seen])
        self.assertPreparedFilesGone([path for path, _mode in seen])
        self.assertEqual(tree_snapshot(self.root), before)

    def test_the_prepared_files_live_in_the_redirected_temporary_directory(self):
        self.write("requirements.txt", "a==1.0\n")
        self.install_pip_audit()
        self.scan(["requirements.txt"])
        path = self.calls()[0]["path"]
        self.assertEqual(os.path.dirname(path), str(self.systmp))


if __name__ == "__main__":
    unittest.main()
