"""Tests for task0003 (sca-directness-resolution): the requirements-file
direct-name resolver with `-r` include following, and the pip classifier's
counts-only report of advisories whose directness cannot be decided.

Covers task0003 Acceptance Criteria
(feature-docs/sca-directness-resolution/tasks/task0003.md):

- AC-1: includes (`-r X`, `-rX`, `--requirement X`, `--requirement=X`),
  nested includes relative to the including file's directory, and
  backslash-continued lines resolve to direct names.
- AC-2: includes leaving the project root (`..`, an absolute path, a
  symlink) are never opened; the set is incomplete.
- AC-3: URL includes are never fetched; missing / unreadable includes,
  URL-only lines, local-path-only lines and editable lines make the set
  incomplete, and nothing raises.
- AC-4: include cycles terminate; constraint files are neither opened nor
  counted as incompleteness.
- AC-5: canonical-name comparison on both sides; the complete / incomplete
  classification of an advisory for an undeclared package.
- AC-6: the exact wording, position and order of the pip undetermined note;
  `skipped` / `skip_reason` untouched.
- AC-7: the script imports nothing outside the standard library (the full
  suite is run separately as `python3 -m unittest discover -s tests`).

Scanners are never executed: a stand-in `pip-audit` on a PATH that holds
only that stand-in prints a fixed payload, and the cargo / go scan unit is
replaced by name where the cross-ecosystem order is exercised. Fixture
projects live in temporary directories created by each test. This module's
own imports stay standard-library only; the script under test is loaded by
file path (its name contains a hyphen).
"""

import ast
import builtins
import importlib.util
import json
import os
import re
import shlex
import socket
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_dependencies", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_module()

HIGH_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"  # 7.5, high
MEDIUM_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"  # 5.3, medium

PIP_NOTE_ONE = " 1 pip advisory with undetermined directness (pip_directness_undetermined)."
PIP_NOTE_TWO = " 2 pip advisories with undetermined directness (pip_directness_undetermined)."
SEVERITY_NOTE_ONE = " 1 pip advisory with undetermined severity (pip_severity_undetermined)."
UNPINNABLE_NOTE_ONE = " 1 pip lockfile entry not auditable (pip_lockfile_entries_unpinnable)."
GO_NOTE_ONE = " 1 go advisory with undetermined severity (go_severity_undetermined)."
CARGO_NOTE_TWO = " 2 cargo advisories with undetermined directness (cargo_directness_undetermined)."


def advisory(name, severity="high"):
    """One pip-audit dependency entry with one advisory. `severity` is
    "high", "medium" or "unknown" (no CVSS vector in the description)."""
    description = "Test advisory text."
    if severity == "high":
        description += " " + HIGH_VECTOR
    elif severity == "medium":
        description += " " + MEDIUM_VECTOR
    return {
        "name": name,
        "version": "1.0.0",
        "vulns": [
            {
                "id": f"PYSEC-TEST-{name}",
                "fix_versions": ["9.9.9"],
                "aliases": [],
                "description": description,
            }
        ],
    }


def payload(*dependencies):
    return {"dependencies": list(dependencies)}


class NetworkGuard:
    """A stand-in for the network layer: every attempt is recorded and then
    refused. Used as a context manager; `calls` lists the attempts."""

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


class OpenRecorder:
    """Records the real path of every file opened through builtins.open
    while active (and still performs the open)."""

    def __enter__(self):
        self.opened = []
        real_open = builtins.open
        recorder = self

        def recording_open(file, *args, **kwargs):
            try:
                recorder.opened.append(os.path.realpath(os.fspath(file)))
            except (TypeError, ValueError):
                pass
            return real_open(file, *args, **kwargs)

        self._patch = mock.patch.object(builtins, "open", recording_open)
        self._patch.start()
        return self

    def __exit__(self, *exc_info):
        self._patch.stop()
        return False


class TestTestDoublesWork(unittest.TestCase):
    """The recorders the containment and no-network assertions rely on
    really observe what they claim to observe."""

    def test_the_network_guard_records_and_refuses_an_attempt(self):
        with NetworkGuard() as network:
            with self.assertRaises(OSError):
                urllib.request.urlopen("http://example.invalid/reqs.txt")
            with self.assertRaises(OSError):
                socket.getaddrinfo("example.invalid", 80)
        self.assertEqual(network.calls, ["urlopen", "getaddrinfo"])

    def test_the_open_recorder_records_the_real_path_of_an_opened_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "f.txt"
            target.write_text("x", encoding="utf-8")
            with OpenRecorder() as recorder:
                with open(target, encoding="utf-8") as handle:
                    handle.read()
        self.assertIn(os.path.realpath(target), recorder.opened)


class PipDirectnessCase(unittest.TestCase):
    """A project root and an outside directory beside it, plus a PATH
    directory that holds only stand-in executables."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        self.root = base / "project"
        self.outside = base / "outside"
        self.bin_dir = base / "bin"
        for directory in (self.root, self.outside, self.bin_dir):
            directory.mkdir()

    def write(self, rel, text, base=None):
        path = (base or self.root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def resolve(self, rel="requirements.txt"):
        return SCAN._pip_requirements_direct_names(self.root / rel, self.root)

    def install_pip_audit(self, pip_payload):
        script = self.bin_dir / "pip-audit"
        script.write_text(
            f"#!{sys.executable}\nimport sys\nsys.stdout.write({json.dumps(pip_payload)!r})\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def install_executable(self, name):
        script = self.bin_dir / name
        script.write_text(f"#!{sys.executable}\n", encoding="utf-8")
        script.chmod(0o755)

    def scan(self, changed_files, pip_payload=None):
        if pip_payload is not None:
            self.install_pip_audit(pip_payload)
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def scan_requirements(self, requirements_text, pip_payload, extra_files=None):
        self.write("requirements.txt", requirements_text)
        for rel, text in (extra_files or {}).items():
            self.write(rel, text)
        return self.scan(["requirements.txt"], pip_payload)

    def assertUndeterminedOne(self, result):
        self.assertEqual(result["findings"], [], result)
        self.assertIn(PIP_NOTE_ONE, result["summary"])
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])


# ---------------------------------------------------------------------------
# Shared contracts this task creates when its worktree lacks them
# (IMPLEMENTATION.md, Shared Components).
# ---------------------------------------------------------------------------


class TestDirectNamesContract(unittest.TestCase):
    def test_reads_like_an_immutable_set_of_the_names(self):
        names = SCAN.DirectNames({"Django", "requests"}, complete=False)
        self.assertEqual(names, {"Django", "requests"})
        self.assertIn("Django", names)
        self.assertNotIn("django", names)  # never canonicalized
        self.assertEqual(len(names), 2)
        self.assertEqual(sorted(names), ["Django", "requests"])
        self.assertFalse(hasattr(names, "add"))

    def test_complete_is_exposed_read_only(self):
        self.assertTrue(SCAN.DirectNames({"a"}, complete=True).complete)
        self.assertFalse(SCAN.DirectNames({"a"}, complete=False).complete)
        with self.assertRaises(AttributeError):
            SCAN.DirectNames({"a"}, complete=True).complete = False

    def test_an_empty_complete_set_is_an_empty_set(self):
        self.assertEqual(SCAN.DirectNames((), complete=True), set())


class TestRequirementNameContract(unittest.TestCase):
    def test_a_pep_508_name_followed_by_each_allowed_character_is_a_name(self):
        cases = {
            "django": "django",
            "Django==3.2.0": "Django",
            "requests[socks]>=2": "requests",
            "Foo_Bar.baz ~= 1.0": "Foo_Bar.baz",
            "pkg (>=1.0)": "pkg",
            "pkg; python_version < '3.9'": "pkg",
            "pkg!=1.0,<2": "pkg",
            "pkg>=1,<2": "pkg",
            "pkg===1.0": "pkg",
            "pkg @ https://example.invalid/pkg-1.0.tar.gz": "pkg",
            "pkg@https://example.invalid/pkg-1.0.tar.gz": "pkg",
            "pkg --hash=sha256:abc": "pkg",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(SCAN._requirement_name(text), expected)

    def test_urls_and_local_paths_have_no_name(self):
        cases = [
            "https://example.invalid/pkg-1.0.tar.gz",
            "http://example.invalid/pkg.zip",
            "file:///srv/pkg",
            "git+https://example.invalid/pkg.git#egg=pkg",
            "git+ssh://git@example.invalid/pkg.git",
            ".",
            "./pkg",
            "../pkg",
            "/abs/pkg",
            "~/pkg",
            "dir/pkg",
            "pkg/sub",
            "pkg-1.0-py3-none-any.whl",
            "pkg-1.0.tar.gz",
            "pkg.zip",
            "dist/pkg-1.0-py3-none-any.whl",
            "",
            "   ",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertIsNone(SCAN._requirement_name(text))

    def test_never_raises(self):
        for value in (None, 5, b"x", "\x00", "[", "=="):
            with self.subTest(value=value):
                try:
                    SCAN._requirement_name(value)
                except Exception as exc:  # pragma: no cover - failure path
                    self.fail(f"raised {exc!r}")


class TestUndeterminedDirectnessNotesContract(unittest.TestCase):
    def test_notes_are_exact_text_pip_first_then_cargo(self):
        cases = {
            (0, 0): "",
            (1, 0): PIP_NOTE_ONE,
            (2, 0): PIP_NOTE_TWO,
            (0, 1): " 1 cargo advisory with undetermined directness (cargo_directness_undetermined).",
            (0, 2): CARGO_NOTE_TWO,
            (1, 2): PIP_NOTE_ONE + CARGO_NOTE_TWO,
            (3, 1): " 3 pip advisories with undetermined directness (pip_directness_undetermined)."
            + " 1 cargo advisory with undetermined directness (cargo_directness_undetermined).",
        }
        for (pip_count, cargo_count), expected in cases.items():
            with self.subTest(pip=pip_count, cargo=cargo_count):
                self.assertEqual(SCAN._undetermined_directness_notes(pip_count, cargo_count), expected)


# ---------------------------------------------------------------------------
# AC-1 (FR4): includes, nesting, option forms, continuation. TS-9, TS-21.
# ---------------------------------------------------------------------------


class TestIncludeResolution(PipDirectnessCase):
    def test_an_include_only_requirements_file_resolves_the_included_names(self):
        self.write("requirements.txt", "-r requirements/base.txt\n")
        self.write("requirements/base.txt", "django==3.2.0\nrequests>=2\n")
        names = self.resolve()
        self.assertEqual(names, {"django", "requests"})
        self.assertTrue(names.complete)

    def test_a_high_advisory_for_an_included_name_produces_a_finding(self):
        result = self.scan_requirements(
            "-r requirements/base.txt\n",
            payload(advisory("django")),
            extra_files={"requirements/base.txt": "django==3.2.0\n"},
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))
        self.assertNotIn("undetermined directness", result["summary"])
        self.assertFalse(result["skipped"])

    def test_nested_includes_are_relative_to_the_including_files_directory(self):
        self.write("requirements.txt", "-r requirements/base.txt\nroot-pkg\n")
        self.write("requirements/base.txt", "-r common/core.txt\n-r ../extra.txt\nbase-pkg\n")
        self.write("requirements/common/core.txt", "core-pkg\n")
        self.write("extra.txt", "extra-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"root-pkg", "base-pkg", "core-pkg", "extra-pkg"})
        self.assertTrue(names.complete)

    def test_a_nested_include_is_not_taken_relative_to_the_root_file(self):
        # `core.txt` exists only at the root; the include sits in a
        # subdirectory, so it is looked up there and is therefore missing.
        self.write("requirements.txt", "-r sub/inner.txt\n")
        self.write("sub/inner.txt", "-r core.txt\ninner-pkg\n")
        self.write("core.txt", "core-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"inner-pkg"})
        self.assertFalse(names.complete)

    def test_every_include_option_form_is_followed(self):
        forms = {
            "short with space": "-r inc.txt",
            "short attached": "-rinc.txt",
            "long with space": "--requirement inc.txt",
            "long with equals": "--requirement=inc.txt",
            "short with extra spaces": "-r    inc.txt",
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                self.write("requirements.txt", line + "\nown-pkg\n")
                self.write("inc.txt", "included-pkg\n")
                names = self.resolve()
                self.assertEqual(names, {"own-pkg", "included-pkg"})
                self.assertTrue(names.complete)

    def test_a_trailing_comment_on_an_include_line_is_ignored(self):
        self.write("requirements.txt", "-r inc.txt  # shared pins\n# whole-line comment\n")
        self.write("inc.txt", "included-pkg  # comment\n")
        names = self.resolve()
        self.assertEqual(names, {"included-pkg"})
        self.assertTrue(names.complete)

    def test_a_continued_include_line_is_read_as_one_line(self):
        self.write("requirements.txt", "-r \\\n    requirements/base.txt\n")
        self.write("requirements/base.txt", "django==3.2.0\n")
        names = self.resolve()
        self.assertEqual(names, {"django"})
        self.assertTrue(names.complete)

    def test_a_continued_requirement_line_is_read_as_one_line(self):
        self.write(
            "requirements.txt",
            "django==3.2.0 \\\n    --hash=sha256:aaaa \\\n    --hash=sha256:bbbb\nrequests\n",
        )
        names = self.resolve()
        self.assertEqual(names, {"django", "requests"})
        self.assertTrue(names.complete)

    def test_a_continuation_in_an_included_file_is_followed_too(self):
        self.write("requirements.txt", "-r inc.txt\n")
        self.write("inc.txt", "--requirement \\\n  deeper.txt\n")
        self.write("deeper.txt", "deep-pkg\n")
        self.assertEqual(self.resolve(), {"deep-pkg"})

    def test_other_option_lines_and_blank_lines_are_ignored_and_stay_complete(self):
        self.write(
            "requirements.txt",
            "\n--index-url https://example.invalid/simple\n--extra-index-url https://x.invalid\n"
            "-f ./wheels\n--no-binary :all:\n--hash=sha256:abc\n\ndjango==3.2.0\n",
        )
        names = self.resolve()
        self.assertEqual(names, {"django"})
        self.assertTrue(names.complete)

    def test_requirement_names_are_kept_as_written(self):
        self.write("requirements.txt", "Foo_Bar.baz==1.0\nrequests[socks]>=2; python_version>'3'\n")
        self.assertEqual(self.resolve(), {"Foo_Bar.baz", "requests"})

    def test_a_utf8_byte_order_mark_does_not_hide_the_first_name(self):
        path = self.root / "requirements.txt"
        path.write_bytes(b"\xef\xbb\xbfdjango==3.2.0\n")
        names = self.resolve()
        self.assertEqual(names, {"django"})
        self.assertTrue(names.complete)

    def test_a_long_include_chain_does_not_exhaust_the_recursion_limit(self):
        depth = sys.getrecursionlimit() + 100
        for index in range(depth):
            text = f"-r chain{index + 1}.txt\n" if index < depth - 1 else "last-pkg\n"
            self.write("requirements.txt" if index == 0 else f"chain{index}.txt", text)
        # chain0 is requirements.txt itself: it includes chain1.txt.
        names = self.resolve()
        self.assertEqual(names, {"last-pkg"})
        self.assertTrue(names.complete)


# ---------------------------------------------------------------------------
# AC-2 (FR4, NFR2, TM-1): includes leaving the project root. TS-10.
# ---------------------------------------------------------------------------


class TestIncludeContainment(PipDirectnessCase):
    def setUp(self):
        super().setUp()
        self.outside_file = self.write("outside-reqs.txt", "outside-pkg==1.0\n", base=self.outside)

    def assert_contained(self, include_line, extra_files=None):
        self.write("requirements.txt", include_line + "\nown-pkg\n")
        for rel, text in (extra_files or {}).items():
            self.write(rel, text)
        with OpenRecorder() as recorder:
            names = self.resolve()
        self.assertNotIn(os.path.realpath(self.outside_file), recorder.opened)
        self.assertNotIn("outside-pkg", names)
        self.assertEqual(names, {"own-pkg"})
        self.assertFalse(names.complete)

    def test_a_dot_dot_include_is_never_opened(self):
        self.assert_contained("-r ../outside/outside-reqs.txt")

    def test_an_absolute_include_outside_the_root_is_never_opened(self):
        self.assert_contained(f"-r {self.outside_file}")

    def test_an_absolute_include_in_every_option_form_is_never_opened(self):
        for line in (
            f"-r{self.outside_file}",
            f"--requirement {self.outside_file}",
            f"--requirement={self.outside_file}",
        ):
            with self.subTest(line=line):
                self.assert_contained(line)

    def test_a_symlink_to_a_file_outside_the_root_is_never_opened(self):
        link = self.root / "linked.txt"
        try:
            os.symlink(self.outside_file, link)
        except (OSError, NotImplementedError):
            self.skipTest("this platform cannot create symlinks")
        self.assert_contained("-r linked.txt")

    def test_a_symlinked_directory_leading_outside_the_root_is_never_opened(self):
        try:
            os.symlink(self.outside, self.root / "linkdir")
        except (OSError, NotImplementedError):
            self.skipTest("this platform cannot create symlinks")
        self.assert_contained("-r linkdir/outside-reqs.txt")

    def test_a_nested_include_escaping_the_root_is_never_opened(self):
        self.assert_contained(
            "-r requirements/base.txt",
            extra_files={"requirements/base.txt": "-r ../../outside/outside-reqs.txt\n"},
        )

    def test_an_include_that_stays_inside_via_dot_dot_is_still_followed(self):
        self.write("requirements.txt", "-r sub/../other.txt\n")
        self.write("other.txt", "other-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"other-pkg"})
        self.assertTrue(names.complete)

    def test_an_include_name_containing_a_null_byte_is_rejected_without_raising(self):
        self.write("requirements.txt", "-r bad\x00name.txt\nown-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"own-pkg"})
        self.assertFalse(names.complete)

    def test_a_requirements_file_outside_the_root_is_not_read(self):
        with OpenRecorder() as recorder:
            names = SCAN._pip_requirements_direct_names(self.outside_file, self.root)
        self.assertNotIn(os.path.realpath(self.outside_file), recorder.opened)
        self.assertEqual(names, set())
        self.assertFalse(names.complete)

    def test_an_escaping_include_makes_an_undeclared_advisory_undetermined(self):
        result = self.scan_requirements(
            "-r ../outside/outside-reqs.txt\ndjango==3.2.0\n",
            payload(advisory("outside-pkg"), advisory("django", "medium")),
        )
        # outside-pkg would be a finding had the outside file been read.
        self.assertUndeterminedOne(result)
        self.assertEqual(result["summary"].count("undetermined directness"), 1)

    def test_an_advisory_for_a_name_resolved_before_the_escape_is_still_a_finding(self):
        result = self.scan_requirements(
            "-r ../outside/outside-reqs.txt\ndjango==3.2.0\n",
            payload(advisory("django")),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertNotIn("undetermined directness", result["summary"])


# ---------------------------------------------------------------------------
# AC-3 (FR4, FR5, NFR2, NFR3, TM-2, TM-4): URL includes, missing and
# unreadable targets, URL / path / editable lines. TS-13, TS-22, TS-25.
# ---------------------------------------------------------------------------


class TestUnresolvableDeclarations(PipDirectnessCase):
    def assert_incomplete(self, requirements_text, extra_files=None):
        """The resolver result is incomplete and keeps `own-pkg`; the scan
        counts an undeclared high advisory as pip undetermined."""
        self.write("requirements.txt", requirements_text + "\nown-pkg\n")
        for rel, text in (extra_files or {}).items():
            self.write(rel, text)
        names = self.resolve()
        self.assertFalse(names.complete, requirements_text)
        self.assertIn("own-pkg", names)
        result = self.scan(["requirements.txt"], payload(advisory("undeclared-pkg")))
        self.assertUndeterminedOne(result)

    def test_a_url_include_is_never_fetched_and_makes_the_set_incomplete(self):
        for target in (
            "https://example.invalid/reqs.txt",
            "http://example.invalid/reqs.txt",
            "file:///etc/hostname",
            "ftp://example.invalid/reqs.txt",
        ):
            with self.subTest(target=target), NetworkGuard() as network:
                self.assert_incomplete(f"-r {target}")
                self.assertEqual(network.calls, [])

    def test_a_url_include_in_every_option_form_is_never_fetched(self):
        target = "https://example.invalid/reqs.txt"
        for line in (f"-r{target}", f"--requirement {target}", f"--requirement={target}"):
            with self.subTest(line=line), NetworkGuard() as network:
                self.assert_incomplete(line)
                self.assertEqual(network.calls, [])

    def test_a_missing_include_target_makes_the_set_incomplete(self):
        self.assert_incomplete("-r missing.txt")

    def test_an_include_without_a_target_makes_the_set_incomplete(self):
        self.assert_incomplete("-r")
        self.assert_incomplete("--requirement=")

    def test_an_include_target_that_is_a_directory_makes_the_set_incomplete(self):
        (self.root / "adir").mkdir()
        self.assert_incomplete("-r adir")

    def test_an_unreadable_include_target_makes_the_set_incomplete(self):
        target = self.write("locked.txt", "locked-pkg\n")
        target.chmod(0)
        self.addCleanup(target.chmod, 0o644)
        try:
            target.read_text(encoding="utf-8")
        except OSError:
            pass
        else:
            self.skipTest("file permissions are not enforced for this user")
        self.assert_incomplete("-r locked.txt")
        self.assertNotIn("locked-pkg", self.resolve())

    def test_an_include_target_that_is_not_utf8_makes_the_set_incomplete(self):
        (self.root / "binary.txt").write_bytes(b"\xff\xfe\x00bad\xff")
        self.assert_incomplete("-r binary.txt")

    def test_a_missing_requirements_file_is_incomplete_and_empty(self):
        names = self.resolve("absent.txt")
        self.assertEqual(names, set())
        self.assertFalse(names.complete)

    def test_a_line_holding_only_a_url_makes_the_set_incomplete(self):
        for line in (
            "https://example.invalid/pkg-1.0.tar.gz",
            "http://example.invalid/pkg-1.0-py3-none-any.whl",
            "git+https://example.invalid/org/pkg.git#egg=pkg",
            "file:///srv/wheels/pkg-1.0-py3-none-any.whl",
        ):
            with self.subTest(line=line), NetworkGuard() as network:
                self.assert_incomplete(line)
                self.assertEqual(network.calls, [])

    def test_a_line_holding_only_a_local_path_makes_the_set_incomplete(self):
        for line in (
            "./local/pkg",
            "../sibling/pkg",
            "/abs/path/pkg",
            "~/pkg",
            "vendor/pkg",
            "pkg-1.0-py3-none-any.whl",
            "dist/pkg-1.0.tar.gz",
            ".",
        ):
            with self.subTest(line=line):
                self.assert_incomplete(line)

    def test_an_editable_line_without_a_resolvable_name_makes_the_set_incomplete(self):
        for line in (
            "-e .",
            "-e ./pkg",
            "-e../pkg",
            "--editable ./pkg",
            "--editable=./pkg",
            "-e git+https://example.invalid/org/pkg.git#egg=pkg",
            "-e",
        ):
            with self.subTest(line=line):
                self.assert_incomplete(line)

    def test_a_requirement_in_an_included_file_that_has_no_name_makes_the_set_incomplete(self):
        self.assert_incomplete("-r inc.txt", extra_files={"inc.txt": "./local/pkg\n"})

    def test_a_complete_file_stays_complete(self):
        self.write("requirements.txt", "django==3.2.0\nrequests[socks]>=2\n")
        self.assertTrue(self.resolve().complete)

    def test_the_scan_returns_normally_for_every_unresolvable_shape(self):
        shapes = "\n".join(
            [
                "-r https://example.invalid/reqs.txt",
                "-r missing.txt",
                "-e .",
                "https://example.invalid/pkg.tar.gz",
                "./pkg",
                "-r bad\x00name",
                "--requirement",
                "-r adir",
            ]
        )
        (self.root / "adir").mkdir()
        result = self.scan_requirements(shapes, payload(advisory("undeclared-pkg")))
        self.assertUndeterminedOne(result)


# ---------------------------------------------------------------------------
# AC-4 (FR4, TM-3): cycles and constraints. TS-11, TS-12.
# ---------------------------------------------------------------------------


class TestCyclesAndConstraints(PipDirectnessCase):
    def test_two_files_that_include_each_other_terminate_with_both_names(self):
        self.write("requirements.txt", "-r other.txt\nfirst-pkg\n")
        self.write("other.txt", "-r requirements.txt\nsecond-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"first-pkg", "second-pkg"})
        self.assertTrue(names.complete)

    def test_a_file_that_includes_itself_terminates(self):
        self.write("requirements.txt", "-r requirements.txt\nown-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"own-pkg"})
        self.assertTrue(names.complete)

    def test_a_longer_cycle_terminates_with_every_name(self):
        self.write("requirements.txt", "-r a.txt\nroot-pkg\n")
        self.write("a.txt", "-r b.txt\na-pkg\n")
        self.write("b.txt", "-r c.txt\n-r a.txt\nb-pkg\n")
        self.write("c.txt", "-r requirements.txt\n-r a.txt\nc-pkg\n")
        names = self.resolve()
        self.assertEqual(names, {"root-pkg", "a-pkg", "b-pkg", "c-pkg"})
        self.assertTrue(names.complete)

    def test_a_diamond_include_is_visited_once_and_is_not_incomplete(self):
        self.write("requirements.txt", "-r left.txt\n-r right.txt\n")
        self.write("left.txt", "-r shared.txt\nleft-pkg\n")
        self.write("right.txt", "-r shared.txt\nright-pkg\n")
        self.write("shared.txt", "shared-pkg\n")
        with OpenRecorder() as recorder:
            names = self.resolve()
        self.assertEqual(names, {"left-pkg", "right-pkg", "shared-pkg"})
        self.assertTrue(names.complete)
        shared = os.path.realpath(self.root / "shared.txt")
        self.assertEqual(recorder.opened.count(shared), 1)

    def test_a_cycle_through_a_symlink_alias_terminates(self):
        self.write("requirements.txt", "-r alias.txt\nown-pkg\n")
        try:
            os.symlink(self.root / "requirements.txt", self.root / "alias.txt")
        except (OSError, NotImplementedError):
            self.skipTest("this platform cannot create symlinks")
        names = self.resolve()
        self.assertEqual(names, {"own-pkg"})
        self.assertTrue(names.complete)

    def test_a_cycle_scan_yields_a_finding_and_no_undetermined_note(self):
        result = self.scan_requirements(
            "-r other.txt\nfirst-pkg\n",
            payload(advisory("second-pkg"), advisory("transitive-pkg")),
            extra_files={"other.txt": "-r requirements.txt\nsecond-pkg\n"},
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("second-pkg:"))
        self.assertNotIn("undetermined directness", result["summary"])

    def test_constraint_files_are_not_opened_and_their_names_are_not_direct(self):
        forms = {
            "short with space": "-c constraints.txt",
            "short attached": "-cconstraints.txt",
            "long with space": "--constraint constraints.txt",
            "long with equals": "--constraint=constraints.txt",
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                self.write("requirements.txt", line + "\nown-pkg\n")
                constraints = self.write("constraints.txt", "pinned-pkg==1.0\n")
                with OpenRecorder() as recorder:
                    names = self.resolve()
                self.assertNotIn(os.path.realpath(constraints), recorder.opened)
                self.assertEqual(names, {"own-pkg"})
                self.assertTrue(names.complete)

    def test_a_missing_constraint_file_does_not_make_the_set_incomplete(self):
        self.write("requirements.txt", "-c missing-constraints.txt\nown-pkg\n")
        self.assertTrue(self.resolve().complete)

    def test_a_constraint_file_outside_the_root_is_neither_opened_nor_incomplete(self):
        outside = self.write("c.txt", "pinned-pkg==1.0\n", base=self.outside)
        self.write("requirements.txt", f"-c {outside}\nown-pkg\n")
        with OpenRecorder() as recorder:
            names = self.resolve()
        self.assertNotIn(os.path.realpath(outside), recorder.opened)
        self.assertTrue(names.complete)

    def test_a_constraint_in_an_included_file_is_ignored_too(self):
        self.write("requirements.txt", "-r sub/inc.txt\n")
        self.write("sub/inc.txt", "-c ../constraints.txt\nincluded-pkg\n")
        constraints = self.write("constraints.txt", "pinned-pkg==1.0\n")
        with OpenRecorder() as recorder:
            names = self.resolve()
        self.assertNotIn(os.path.realpath(constraints), recorder.opened)
        self.assertEqual(names, {"included-pkg"})
        self.assertTrue(names.complete)

    def test_a_constraint_scan_keeps_a_constraint_only_name_transitive_without_a_note(self):
        result = self.scan_requirements(
            "-c constraints.txt\ndjango==3.2.0\n",
            payload(advisory("django"), advisory("pinned-pkg")),
            extra_files={"constraints.txt": "pinned-pkg==1.0\n"},
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))
        self.assertNotIn("undetermined directness", result["summary"])


# ---------------------------------------------------------------------------
# AC-5 (FR5, TM-5): classification. TS-8, TS-14, TS-20, TS-23.
# ---------------------------------------------------------------------------

INCOMPLETE_REQUIREMENTS = "django==3.2.0\n./local/pkg\n"
PIP_ECOSYSTEM = {
    "ecosystem": "pip",
    "severity_map": {"critical": "critical", "high": "high"},
    "threshold": {"direct_only": True, "min_severity": "high"},
}
DJANGO_POETRY_LOCK = (
    '[[package]]\nname = "django"\nversion = "3.2.0"\ndescription = "d"\noptional = false\n'
    'python-versions = ">=3.8"\nfiles = [{file = "d.tar.gz", hash = "sha256:aa"}]\n\n'
)
POETRY_LOCK_METADATA = '[metadata]\nlock-version = "2.0"\ncontent-hash = "abc"\n'


class TestClassification(PipDirectnessCase):
    def test_canonical_names_are_compared_on_both_sides(self):
        self.write("pyproject.toml", '[project]\nname = "demo"\ndependencies = ["Django==3.2.0"]\n')
        result = self.scan(["pyproject.toml"], payload(advisory("django")))
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))

    def test_requirements_declaration_and_report_differ_in_case_and_separators(self):
        for declared, reported in (
            ("Foo_Bar.baz==1.0", "foo-bar-baz"),
            ("foo-bar-baz==1.0", "Foo_Bar.baz"),
            ("Django==3.2.0", "django"),
        ):
            with self.subTest(declared=declared, reported=reported):
                result = self.scan_requirements(declared + "\n", payload(advisory(reported)))
                self.assertEqual(len(result["findings"]), 1, result)

    def test_a_complete_set_keeps_an_undeclared_advisory_transitive(self):
        result = self.scan_requirements(
            "django==3.2.0\n",
            payload(advisory("transitive-pkg"), advisory("transitive-unknown", "unknown")),
        )
        self.assertEqual(result["findings"], [])
        self.assertNotIn("undetermined", result["summary"])
        self.assertFalse(result["skipped"])

    def test_an_incomplete_set_counts_an_undeclared_high_advisory_once(self):
        result = self.scan_requirements(INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-pkg")))
        self.assertUndeterminedOne(result)

    def test_an_incomplete_set_drops_a_known_below_threshold_advisory_uncounted(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-pkg", "medium"))
        )
        self.assertEqual(result["findings"], [])
        self.assertNotIn("undetermined", result["summary"])

    def test_an_incomplete_set_counts_an_unknown_severity_advisory_once_and_only_once(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-pkg", "unknown"))
        )
        self.assertUndeterminedOne(result)
        self.assertNotIn("pip_severity_undetermined", result["summary"])

    def test_an_incomplete_set_counts_each_undeclared_advisory(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS,
            payload(
                advisory("undeclared-a", "high"),
                advisory("undeclared-b", "unknown"),
                advisory("undeclared-c", "medium"),
            ),
        )
        self.assertEqual(result["findings"], [])
        self.assertIn(PIP_NOTE_TWO, result["summary"])
        self.assertNotIn("pip_severity_undetermined", result["summary"])

    def test_an_incomplete_set_still_classifies_declared_names_as_before(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS,
            payload(advisory("django", "high"), advisory("django-unknown", "unknown")),
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))
        # django-unknown is undeclared: counted as directness, not severity.
        self.assertIn(PIP_NOTE_ONE, result["summary"])
        self.assertNotIn("pip_severity_undetermined", result["summary"])

    def test_a_declared_unknown_severity_advisory_stays_in_the_severity_note(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS, payload(advisory("django", "unknown"))
        )
        self.assertEqual(result["findings"], [])
        self.assertIn(SEVERITY_NOTE_ONE, result["summary"])
        self.assertNotIn("pip_directness_undetermined", result["summary"])

    def test_normalize_pip_reports_the_directness_count_beside_the_findings(self):
        self.write("requirements.txt", INCOMPLETE_REQUIREMENTS)
        findings, skip_info = SCAN.normalize_pip(
            PIP_ECOSYSTEM,
            payload(advisory("django"), advisory("undeclared-pkg")),
            "requirements.txt",
            self.root,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(skip_info["directness_undetermined"], 1)

    def test_normalize_pip_without_any_undetermined_advisory_returns_no_skip_info(self):
        self.write("requirements.txt", "django==3.2.0\n")
        findings, skip_info = SCAN.normalize_pip(
            PIP_ECOSYSTEM, payload(advisory("django"), advisory("other")), "requirements.txt", self.root
        )
        self.assertEqual(len(findings), 1)
        self.assertIsNone(skip_info)

    def test_an_unresolvable_manifest_leaves_the_set_incomplete(self):
        findings, skip_info = SCAN.normalize_pip(
            PIP_ECOSYSTEM, payload(advisory("undeclared-pkg")), "../outside/requirements.txt", self.root
        )
        self.assertEqual(findings, [])
        self.assertEqual(skip_info["directness_undetermined"], 1)

    # -- the pyproject seam (IMPLEMENTATION.md D5) -------------------------

    def run_with_pyproject_resolver(self, resolver_result, pip_payload):
        self.write("pyproject.toml", '[project]\nname = "demo"\n')
        with mock.patch.object(SCAN, "_pip_pyproject_direct_names", lambda *a, **k: resolver_result):
            return self.scan(["pyproject.toml"], pip_payload)

    def test_an_incomplete_pyproject_set_is_counted_like_any_incomplete_set(self):
        incomplete = SCAN.DirectNames({"django"}, complete=False)
        result = self.run_with_pyproject_resolver(
            incomplete,
            payload(
                advisory("django", "high"),
                advisory("undeclared-high", "high"),
                advisory("undeclared-unknown", "unknown"),
                advisory("undeclared-medium", "medium"),
            ),
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("django:"))
        self.assertIn(PIP_NOTE_TWO, result["summary"])
        self.assertNotIn("pip_severity_undetermined", result["summary"])
        self.assertFalse(result["skipped"])

    def test_a_complete_pyproject_set_keeps_an_undeclared_advisory_transitive(self):
        complete = SCAN.DirectNames({"django"}, complete=True)
        result = self.run_with_pyproject_resolver(complete, payload(advisory("undeclared-high")))
        self.assertEqual(result["findings"], [])
        self.assertNotIn("undetermined", result["summary"])

    def test_a_resolver_result_without_completeness_is_treated_as_complete(self):
        result = self.run_with_pyproject_resolver({"django"}, payload(advisory("undeclared-high")))
        self.assertEqual(result["findings"], [])
        self.assertNotIn("undetermined", result["summary"])

    def test_an_incomplete_pyproject_set_is_counted_for_a_lockfile_unit_too(self):
        self.write("poetry.lock", DJANGO_POETRY_LOCK + POETRY_LOCK_METADATA)
        self.write("pyproject.toml", '[tool.poetry.dependencies]\ndjango = ">=3.2"\n')
        incomplete = SCAN.DirectNames({"django"}, complete=False)
        with mock.patch.object(SCAN, "_pip_pyproject_direct_names", lambda *a, **k: incomplete):
            result = self.scan(["poetry.lock"], payload(advisory("django"), advisory("undeclared-high")))
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertIn(PIP_NOTE_ONE, result["summary"])


# ---------------------------------------------------------------------------
# AC-6 (FR5, NFR4, TM-6): the note's wording, position and order. TS-16.
# ---------------------------------------------------------------------------


class TestUndeterminedNote(PipDirectnessCase):
    PREFIX = "Scanned pip; 0 finding(s) at or above threshold."

    def test_the_note_for_one_advisory_is_exact(self):
        result = self.scan_requirements(INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-pkg")))
        self.assertEqual(result["summary"], self.PREFIX + PIP_NOTE_ONE)

    def test_the_note_for_two_advisories_uses_the_plural(self):
        result = self.scan_requirements(
            INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-a"), advisory("undeclared-b"))
        )
        self.assertEqual(result["summary"], self.PREFIX + PIP_NOTE_TWO)

    def test_the_note_carries_no_package_name_path_or_advisory_text(self):
        result = self.scan_requirements(
            "-r ../outside/distinctive-include.txt\n",
            payload(advisory("distinctive-package-name")),
        )
        self.assertEqual(result["summary"], self.PREFIX + PIP_NOTE_ONE)
        for fragment in ("distinctive", str(self.root), "outside", "Test advisory"):
            self.assertNotIn(fragment, result["summary"])
        self.assertIsNone(result["skip_reason"])

    def test_the_note_does_not_change_skipped_or_skip_reason(self):
        result = self.scan_requirements(INCOMPLETE_REQUIREMENTS, payload(advisory("undeclared-pkg")))
        self.assertIs(result["skipped"], False)
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(result["source"], "tool")

    def test_a_skip_elsewhere_keeps_its_reason_and_the_note_still_appears(self):
        self.write("go.mod", "module example.invalid/demo\n")
        self.write("requirements.txt", INCOMPLETE_REQUIREMENTS)
        # No govulncheck stand-in: the go unit reports its tool as missing.
        result = self.scan(["requirements.txt", "go.mod"], payload(advisory("undeclared-pkg")))
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "go_tool_not_found")
        self.assertTrue(result["summary"].endswith(PIP_NOTE_ONE), result["summary"])

    def test_the_note_follows_the_severity_go_notes_and_precedes_the_cargo_note(self):
        self.write("go.mod", "module example.invalid/demo\n")
        self.write("Cargo.toml", "[dependencies]\n")
        self.write("requirements.txt", INCOMPLETE_REQUIREMENTS)
        self.install_executable("govulncheck")
        self.install_executable("cargo-audit")

        def stand_in_unit(plan, project_root):
            unit = SCAN._group_audit(completed=True)
            if plan.ecosystem["ecosystem"] == "go":
                unit["undetermined"] = 1
            else:
                unit["directness_undetermined"] = 2
            return unit

        pip_payload = payload(
            advisory("django", "unknown"),  # declared, severity unknown
            advisory("undeclared-pkg", "high"),  # undeclared, set incomplete
        )
        with mock.patch.object(SCAN, "_scan_bound_group", stand_in_unit):
            result = self.scan(["requirements.txt", "go.mod", "Cargo.toml"], pip_payload)
        self.assertEqual(
            result["summary"],
            "Scanned cargo, go, pip; 0 finding(s) at or above threshold."
            + SEVERITY_NOTE_ONE
            + GO_NOTE_ONE
            + PIP_NOTE_ONE
            + CARGO_NOTE_TWO,
        )
        self.assertFalse(result["skipped"])

    def test_the_note_follows_the_unpinnable_note_of_a_lockfile_unit(self):
        self.write(
            "poetry.lock",
            DJANGO_POETRY_LOCK
            + '[[package]]\nname = "vendored"\nversion = "1.0"\ndescription = "d"\noptional = false\n'
            'python-versions = ">=3.8"\nfiles = []\n\n[package.source]\ntype = "git"\n'
            'url = "https://example.invalid/vendored"\n\n'
            + POETRY_LOCK_METADATA,
        )
        self.write("pyproject.toml", '[tool.poetry.dependencies]\ndjango = ">=3.2"\n')
        incomplete = SCAN.DirectNames({"django"}, complete=False)
        pip_payload = payload(advisory("django", "unknown"), advisory("undeclared-pkg"))
        with mock.patch.object(SCAN, "_pip_pyproject_direct_names", lambda *a, **k: incomplete):
            result = self.scan(["poetry.lock"], pip_payload)
        self.assertEqual(
            result["summary"],
            self.PREFIX + SEVERITY_NOTE_ONE + UNPINNABLE_NOTE_ONE + PIP_NOTE_ONE,
        )

    def test_a_cargo_count_alone_produces_only_the_cargo_note(self):
        self.write("Cargo.toml", "[dependencies]\n")
        self.install_executable("cargo-audit")

        def stand_in_unit(plan, project_root):
            unit = SCAN._group_audit(completed=True)
            unit["directness_undetermined"] = 2
            return unit

        with mock.patch.object(SCAN, "_scan_bound_group", stand_in_unit):
            result = self.scan(["Cargo.toml"])
        self.assertEqual(
            result["summary"], "Scanned cargo; 0 finding(s) at or above threshold." + CARGO_NOTE_TWO
        )

    def test_counts_are_summed_over_every_pip_unit(self):
        self.write("requirements.txt", INCOMPLETE_REQUIREMENTS)
        self.write("sub/requirements.txt", INCOMPLETE_REQUIREMENTS)
        result = self.scan(
            ["requirements.txt", "sub/requirements.txt"], payload(advisory("undeclared-pkg"))
        )
        self.assertEqual(result["summary"], self.PREFIX + PIP_NOTE_TWO)


# ---------------------------------------------------------------------------
# AC-7 (NFR1): standard library only. TS-28.
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


class TestStandardLibraryOnly(unittest.TestCase):
    def setUp(self):
        self.stdlib = getattr(sys, "stdlib_module_names", None)
        if self.stdlib is None:
            self.skipTest("sys.stdlib_module_names is unavailable on this interpreter")

    def test_the_script_imports_nothing_new_outside_the_standard_library(self):
        # `yaml` is the script's pre-existing, guarded optional import.
        outside = _imported_top_level_modules(SCRIPT_PATH) - set(self.stdlib) - {"yaml"}
        self.assertEqual(outside, set())

    def test_tomllib_is_imported_only_inside_the_existing_guard(self):
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        guarded = [
            node
            for node in tree.body
            if isinstance(node, ast.Try)
            and any(isinstance(n, ast.Import) and n.names[0].name == "tomllib" for n in node.body)
        ]
        self.assertEqual(len(guarded), 1)
        unguarded = [
            node
            for node in tree.body
            if isinstance(node, ast.Import) and any(alias.name == "tomllib" for alias in node.names)
        ]
        self.assertEqual(unguarded, [])

    def test_this_test_module_imports_only_the_standard_library(self):
        outside = _imported_top_level_modules(__file__) - set(self.stdlib)
        self.assertEqual(outside, set())


# ---------------------------------------------------------------------------
# task0001 (sca-requirements-multi-option-lines): an option line is split into
# tokens and an include (`-r`) or editable (`-e`) is read at any position on
# it; a line that cannot be interpreted leaves the name set incomplete.
#
# - AC-1 / AC-2: an include after a constraint or an index option is followed;
#   several includes on one line are all followed; a constraint is never
#   opened; a repeated target is opened at most once.
# - AC-3: an unsplittable line takes nothing and is incomplete; a missing
#   include value is incomplete.
# - AC-4: a mid-line include outside the root, or a URL, is never opened.
# - AC-5: `-e` / `--editable` is read at any position.
# - AC-6: abbreviated long options are incomplete; `--` and other options
#   are ignored.
# - AC-7: the summary carries the existing note token and a count only.
# ---------------------------------------------------------------------------

EXAMPLE_INDEX_URL = "https://example.invalid/simple"
UNDETERMINED_NOTE_TOKEN = "pip_directness_undetermined"
# A note token in a scan summary: a parenthesized snake_case word.
NOTE_TOKEN_RE = re.compile(r"\(([a-z]+(?:_[a-z]+)+)\)")


class MultiOptionLineCase(PipDirectnessCase):
    def real(self, rel):
        return os.path.realpath(self.root / rel)

    def resolve_line(self, line, files=None, tail="own-pkg\n"):
        """Resolve a requirements.txt made of `line` and `tail`; returns the
        direct names, the real paths opened and the network attempts."""
        self.write("requirements.txt", line + "\n" + tail)
        for rel, text in (files or {}).items():
            self.write(rel, text)
        with OpenRecorder() as recorder, NetworkGuard() as network:
            names = self.resolve()
        return names, recorder.opened, network.calls


class TestOptionLineIncludeFollowing(MultiOptionLineCase):
    LEADING_FORMS = (
        "-c constraints.txt -r deps.txt",
        f"--index-url {EXAMPLE_INDEX_URL} -r deps.txt",
    )

    def test_ac1_ac2_the_resolver_follows_an_include_that_is_not_the_first_option(self):
        for line in self.LEADING_FORMS:
            with self.subTest(line=line):
                self.write("deps.txt", "vuln-pkg==1.0\n")
                constraints = self.write("constraints.txt", "pinned-pkg==1.0\n")
                names, opened, network_calls = self.resolve_line(line, tail="")
                self.assertEqual(names, {"vuln-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)
                self.assertNotIn(os.path.realpath(constraints), opened)
                self.assertEqual(network_calls, [])

    def test_ac1_ac2_the_scan_gives_one_finding_and_no_undetermined_note(self):
        for line in self.LEADING_FORMS:
            with self.subTest(line=line), OpenRecorder() as recorder, NetworkGuard() as network:
                result = self.scan_requirements(
                    line + "\n",
                    payload(advisory("vuln-pkg")),
                    extra_files={
                        "deps.txt": "vuln-pkg==1.0\n",
                        "constraints.txt": "pinned-pkg==1.0\n",
                    },
                )
                self.assertEqual(len(result["findings"]), 1, result)
                self.assertTrue(result["findings"][0]["title"].startswith("vuln-pkg:"))
                self.assertNotIn(UNDETERMINED_NOTE_TOKEN, result["summary"])
                self.assertFalse(result["skipped"], result)
                self.assertNotIn(self.real("constraints.txt"), recorder.opened)
                self.assertEqual(network.calls, [])

    def test_ac2_several_includes_on_one_line_are_all_followed(self):
        names, opened, _ = self.resolve_line(
            "-r a.txt -r b.txt", {"a.txt": "a-pkg\n", "b.txt": "b-pkg\n"}
        )
        self.assertEqual(names, {"own-pkg", "a-pkg", "b-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("a.txt"), opened)
        self.assertIn(self.real("b.txt"), opened)

    def test_ac2_an_include_after_another_option_is_followed_and_the_constraint_is_not_opened(self):
        forms = {
            "long equals after a constraint": "-c c.txt --requirement=b.txt",
            "attached after a constraint": "-c c.txt -rb.txt",
            "long with space after an index option": f"--index-url {EXAMPLE_INDEX_URL} --requirement b.txt",
            "short after a long constraint": "--constraint c.txt -r b.txt",
            "short after an attached constraint": "-cc.txt -r b.txt",
            "short after a long equals constraint": "--constraint=c.txt -r b.txt",
            "constraint after the include": "-r b.txt -c c.txt",
            "include between two constraints": "-c c.txt -r b.txt -c c.txt",
            "short after a hash option": "--hash=sha256:abc -r b.txt",
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                constraints = self.write("c.txt", "pinned-pkg==1.0\n")
                names, opened, network_calls = self.resolve_line(line, {"b.txt": "b-pkg\n"})
                self.assertEqual(names, {"own-pkg", "b-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("b.txt"), opened)
                self.assertNotIn(os.path.realpath(constraints), opened)
                self.assertEqual(network_calls, [])

    def test_ac2_a_constraint_value_that_looks_like_an_include_is_not_followed(self):
        # `-c -r`: the constraint takes the next token as its value.
        names, opened, _ = self.resolve_line("-c -r b.txt", {"b.txt": "b-pkg\n"})
        self.assertEqual(names, {"own-pkg"})
        self.assertTrue(names.complete)
        self.assertNotIn(self.real("b.txt"), opened)

    def test_ac2_the_same_target_named_more_than_once_on_one_line_is_opened_once(self):
        names, opened, _ = self.resolve_line(
            "-c c.txt -r b.txt -r b.txt -rb.txt --requirement=b.txt --requirement b.txt",
            {"b.txt": "b-pkg\n"},
        )
        self.assertEqual(names, {"own-pkg", "b-pkg"})
        self.assertTrue(names.complete)
        self.assertEqual(opened.count(self.real("b.txt")), 1)

    def test_ac2_a_cycle_formed_by_mid_line_includes_terminates_and_opens_each_file_once(self):
        names, opened, _ = self.resolve_line(
            "-c c.txt -r other.txt",
            {
                "other.txt": f"--index-url {EXAMPLE_INDEX_URL} -r requirements.txt\nsecond-pkg\n",
                "c.txt": "pinned-pkg==1.0\n",
            },
            tail="first-pkg\n",
        )
        self.assertEqual(names, {"first-pkg", "second-pkg"})
        self.assertTrue(names.complete)
        self.assertEqual(opened.count(self.real("requirements.txt")), 1)
        self.assertEqual(opened.count(self.real("other.txt")), 1)
        self.assertNotIn(self.real("c.txt"), opened)

    def test_ac2_an_include_in_an_included_file_after_an_option_is_relative_to_that_file(self):
        names, _, _ = self.resolve_line(
            "-r sub/inc.txt",
            {"sub/inc.txt": "-c c.txt -r deeper.txt\n", "sub/deeper.txt": "deep-pkg\n"},
        )
        self.assertEqual(names, {"own-pkg", "deep-pkg"})
        self.assertTrue(names.complete)


class TestUnsplittableAndValuelessOptionLines(MultiOptionLineCase):
    UNSPLITTABLE = {
        "unclosed double quote": '-c a -r "deps.txt',
        "unclosed single quote": "-c a -r 'deps.txt",
        "unclosed quote after an include": '-r deps.txt -r "other.txt',
        # The trailing space keeps the backslash from joining the next line;
        # the logical line is stripped, which leaves the escape trailing.
        "trailing escape": "-r deps.txt \\ ",
    }

    def test_ac3_the_unsplittable_forms_really_cannot_be_split(self):
        for label, line in self.UNSPLITTABLE.items():
            with self.subTest(form=label):
                logical = SCAN._requirements_logical_lines(line + "\nown-pkg\n")[0]
                with self.assertRaises(ValueError):
                    shlex.split(logical)

    def test_ac3_an_unsplittable_line_takes_nothing_and_is_incomplete(self):
        for label, line in self.UNSPLITTABLE.items():
            with self.subTest(form=label):
                names, opened, network_calls = self.resolve_line(
                    line, {"deps.txt": "deps-pkg\n", "other.txt": "other-pkg\n"}
                )
                self.assertFalse(names.complete)
                self.assertEqual(names, {"own-pkg"})
                self.assertNotIn(self.real("deps.txt"), opened)
                self.assertNotIn(self.real("other.txt"), opened)
                self.assertEqual(network_calls, [])

    def test_ac3_an_unsplittable_line_does_not_stop_other_lines_and_files(self):
        for label, line in self.UNSPLITTABLE.items():
            with self.subTest(form=label):
                self.write("requirements.txt", f"first-pkg\n-r inc.txt\n{line}\n-r after.txt\nlast-pkg\n")
                self.write("inc.txt", f"{line}\ninc-pkg\n")
                self.write("after.txt", "after-pkg\n")
                self.write("deps.txt", "deps-pkg\n")
                names = self.resolve()
                self.assertFalse(names.complete)
                self.assertEqual(names, {"first-pkg", "inc-pkg", "after-pkg", "last-pkg"})

    def test_ac3_an_unsplittable_line_raises_nothing_and_counts_an_undeclared_advisory_once(self):
        for label, line in self.UNSPLITTABLE.items():
            with self.subTest(form=label):
                result = self.scan_requirements(
                    line + "\nown-pkg\n", payload(advisory("undeclared-pkg"))
                )
                self.assertUndeterminedOne(result)
                self.assertEqual(result["summary"].count(UNDETERMINED_NOTE_TOKEN), 1)

    def test_ac3_a_missing_include_value_makes_the_set_incomplete(self):
        forms = {
            "short after an index option": f"--index-url {EXAMPLE_INDEX_URL} -r",
            "trailing long option": "--requirement",
            "trailing long option after a constraint": "-c a --requirement",
            "empty long equals": "--requirement=",
            "empty long equals after an index option": f"--index-url {EXAMPLE_INDEX_URL} --requirement=",
            "quoted empty value": '-c a -r ""',
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                names, opened, network_calls = self.resolve_line(line)
                self.assertFalse(names.complete)
                self.assertEqual(names, {"own-pkg"})
                self.assertEqual(network_calls, [])

    def test_ac3_a_missing_include_value_counts_an_undeclared_advisory_once(self):
        result = self.scan_requirements(
            f"--index-url {EXAMPLE_INDEX_URL} -r\nown-pkg\n", payload(advisory("undeclared-pkg"))
        )
        self.assertUndeterminedOne(result)

    def test_ac3_a_constraint_without_a_value_leaves_the_set_complete(self):
        for line in ("-c", "--constraint", f"--index-url {EXAMPLE_INDEX_URL} -c"):
            with self.subTest(line=line):
                names, _, _ = self.resolve_line(line)
                self.assertTrue(names.complete)
                self.assertEqual(names, {"own-pkg"})


class TestMidLineIncludeContainment(MultiOptionLineCase):
    def setUp(self):
        super().setUp()
        self.outside_file = self.write("outside-reqs.txt", "outside-pkg==1.0\n", base=self.outside)

    def assert_contained(self, line):
        names, opened, network_calls = self.resolve_line(line)
        self.assertNotIn(os.path.realpath(self.outside_file), opened, line)
        self.assertEqual(names, {"own-pkg"}, line)
        self.assertFalse(names.complete, line)
        self.assertEqual(network_calls, [], line)

    def test_ac4_a_mid_line_include_outside_the_root_is_never_opened(self):
        absolute = shlex.quote(str(self.outside_file))
        forms = {
            "dot dot after a constraint": "-c a -r ../outside/outside-reqs.txt",
            "absolute after a constraint": f"-c a -r {absolute}",
            "absolute long form after an index option": (
                f"--index-url {EXAMPLE_INDEX_URL} --requirement {absolute}"
            ),
            "dot dot long equals": "-c a --requirement=../outside/outside-reqs.txt",
            "dot dot attached": "-c a -r../outside/outside-reqs.txt",
            "dot dot after another include": "-r ok.txt -r ../outside/outside-reqs.txt",
        }
        self.write("ok.txt", "ok-pkg\n")
        for label, line in forms.items():
            with self.subTest(form=label):
                names, opened, network_calls = self.resolve_line(line)
                self.assertNotIn(os.path.realpath(self.outside_file), opened, line)
                self.assertFalse(names.complete, line)
                self.assertNotIn("outside-pkg", names)
                self.assertEqual(network_calls, [], line)

    def test_ac4_a_mid_line_symlink_leading_outside_the_root_is_never_opened(self):
        try:
            os.symlink(self.outside_file, self.root / "linked.txt")
        except (OSError, NotImplementedError):
            self.skipTest("this platform cannot create symlinks")
        self.assert_contained("-c a -r linked.txt")

    def test_ac4_a_mid_line_url_include_is_never_fetched(self):
        targets = (
            "https://example.invalid/reqs.txt",
            "http://example.invalid/reqs.txt",
            "file:///etc/hostname",
            "ftp://example.invalid/reqs.txt",
        )
        for target in targets:
            for prefix in (f"--index-url {EXAMPLE_INDEX_URL} -r", "-c a --requirement"):
                with self.subTest(target=target, prefix=prefix):
                    self.assert_contained(f"{prefix} {target}")
            with self.subTest(target=target, form="equals"):
                self.assert_contained(f"-c a --requirement={target}")
            with self.subTest(target=target, form="attached"):
                self.assert_contained(f"-c a -r{target}")


class TestMidLineEditable(MultiOptionLineCase):
    def test_ac5_a_named_editable_is_read_at_any_position(self):
        forms = {
            "leading short": "-e named-pkg",
            "leading attached": "-enamed-pkg",
            "leading long": "--editable named-pkg",
            "leading long equals": "--editable=named-pkg",
            "short after an index option": f"--index-url {EXAMPLE_INDEX_URL} -e named-pkg",
            "attached after a constraint": "-c a -enamed-pkg",
            "long after an index option": f"--index-url {EXAMPLE_INDEX_URL} --editable named-pkg",
            "long equals after an index option": f"--index-url {EXAMPLE_INDEX_URL} --editable=named-pkg",
            "long equals with extras": "-c a --editable=named-pkg[extra]",
            "short after an include": "-r inc.txt -e named-pkg",
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                names, _, network_calls = self.resolve_line(line, {"inc.txt": "inc-pkg\n"})
                self.assertIn("named-pkg", names, line)
                self.assertIn("own-pkg", names, line)
                self.assertTrue(names.complete, line)
                self.assertEqual(network_calls, [], line)

    def test_ac5_an_editable_without_a_name_or_a_value_makes_the_set_incomplete(self):
        forms = {
            "local path after a constraint": "-c a -e ./pkg",
            "local path attached": "-c a -e../pkg",
            "current directory": "-c a -e .",
            "long local path": "-c a --editable ./pkg",
            "long equals local path": "-c a --editable=./pkg",
            "url without a name": f"--index-url {EXAMPLE_INDEX_URL} -e git+https://example.invalid/org/pkg.git#egg=pkg",
            "short without a value": f"--index-url {EXAMPLE_INDEX_URL} -e",
            "long without a value": "-c a --editable",
            "empty long equals": "-c a --editable=",
            "quoted empty value": '-c a -e ""',
        }
        for label, line in forms.items():
            with self.subTest(form=label):
                names, _, network_calls = self.resolve_line(line)
                self.assertFalse(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertEqual(network_calls, [], line)

    def test_ac5_an_unnamed_editable_counts_an_undeclared_advisory_once(self):
        result = self.scan_requirements(
            "-c a -e ./pkg\nown-pkg\n", payload(advisory("undeclared-pkg"))
        )
        self.assertUndeterminedOne(result)

    def test_ac5_a_named_editable_after_an_option_makes_its_advisory_a_finding(self):
        result = self.scan_requirements(
            f"--index-url {EXAMPLE_INDEX_URL} --editable=named-pkg\n",
            payload(advisory("named-pkg")),
        )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("named-pkg:"))
        self.assertNotIn(UNDETERMINED_NOTE_TOKEN, result["summary"])

    def test_ac5_a_leading_editable_takes_only_the_next_token_as_its_value(self):
        names, opened, _ = self.resolve_line(
            "-e named-pkg -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
        )
        self.assertEqual(names, {"named-pkg", "deps-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("deps.txt"), opened)

    def test_ac5_a_leading_editable_without_a_name_does_not_hide_a_later_include(self):
        names, opened, _ = self.resolve_line(
            "-e ./pkg -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
        )
        self.assertEqual(names, {"deps-pkg"})
        self.assertFalse(names.complete)
        self.assertIn(self.real("deps.txt"), opened)

    def test_ac5_a_quoted_editable_value_is_one_token(self):
        names, _, _ = self.resolve_line('-c a -e "named-pkg>=1.0"', tail="")
        self.assertEqual(names, {"named-pkg"})
        self.assertTrue(names.complete)


class TestAbbreviatedAndIgnoredOptions(MultiOptionLineCase):
    def test_ac6_an_abbreviated_long_option_makes_the_set_incomplete_and_opens_nothing(self):
        forms = (
            "--requirem deps.txt",
            "--requirem=deps.txt",
            "-c a --editab ./pkg",
            "--re deps.txt",
            "--re=deps.txt",
            "--e ./pkg",
            "--e=./pkg",
            "--r deps.txt",
            "--requireme deps.txt",
            "--edit=deps.txt",
            "--editabl deps.txt",
            f"--index-url {EXAMPLE_INDEX_URL} --requirem deps.txt",
            "-c a --requirem=deps.txt",
        )
        for line in forms:
            with self.subTest(line=line):
                names, opened, network_calls = self.resolve_line(line, {"deps.txt": "deps-pkg\n"})
                self.assertFalse(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertNotIn(self.real("deps.txt"), opened, line)
                self.assertEqual(network_calls, [], line)

    def test_ac6_an_abbreviation_does_not_consume_the_following_token(self):
        for line in ("--requirem -r other.txt", "--e -r other.txt", "--editab -r other.txt"):
            with self.subTest(line=line):
                names, opened, _ = self.resolve_line(
                    line, {"other.txt": "other-pkg\n", "deps.txt": "deps-pkg\n"}
                )
                self.assertFalse(names.complete, line)
                self.assertEqual(names, {"own-pkg", "other-pkg"}, line)
                self.assertIn(self.real("other.txt"), opened, line)

    def test_ac6_an_abbreviated_value_is_never_read_as_a_name_or_a_file(self):
        names, opened, _ = self.resolve_line(
            "--editab named-pkg --requirem deps.txt", {"deps.txt": "deps-pkg\n"}
        )
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})
        self.assertNotIn(self.real("deps.txt"), opened)

    def test_ac6_a_lone_double_dash_and_other_options_are_ignored_and_stay_complete(self):
        forms = (
            "--",
            f"--index-url {EXAMPLE_INDEX_URL}",
            "--hash=sha256:abc",
            "--no-binary :all:",
            "--unknown-option value",
            "--unknown-option=value stray-word",
            "--extra-index-url https://x.invalid --trusted-host x.invalid",
            "-f ./wheels --",
            "--prefer-binary",
            "-i",
            f"--index-url {EXAMPLE_INDEX_URL} -- --no-index",
        )
        for line in forms:
            with self.subTest(line=line):
                names, opened, network_calls = self.resolve_line(line, {"deps.txt": "deps-pkg\n"})
                self.assertTrue(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertEqual(network_calls, [], line)

    def test_ac6_a_constraint_abbreviation_is_not_flagged(self):
        # task0001 (sca-requirements-option-value-consumption), AC-5: `--con`
        # abbreviates the value-taking `--constraint` (and `--config-settings`),
        # so a line holding it leaves the set incomplete. The method name is
        # kept: this record is cited by other test records.
        names, _, _ = self.resolve_line("--constraint-extra x --con y")
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})


class TestIncompleteSetsReportOnlyThroughTheExistingNote(MultiOptionLineCase):
    UNSPLITTABLE_SECRET = '-c secret-constraint.txt -r "secret-deps.txt'

    def split_error_texts(self):
        texts = set()
        for line in ('x "y', "x \\"):
            try:
                shlex.split(line)
            except ValueError as error:
                texts.add(str(error))
        return texts

    def test_ac7_the_splitter_error_texts_are_known(self):
        self.assertEqual(len(self.split_error_texts()), 2)

    def test_ac7_every_incomplete_case_is_reported_through_the_existing_note_only(self):
        outside_file = self.write("secret-outside.txt", "outside-pkg==1.0\n", base=self.outside)
        cases = {
            "unsplittable line": self.UNSPLITTABLE_SECRET,
            "trailing escape": "-r secret-deps.txt \\ ",
            "include outside the root": "-c secret-constraint.txt -r ../outside/secret-outside.txt",
            "absolute include outside the root": f"-c a -r {shlex.quote(str(outside_file))}",
            "url include": "--index-url https://secret-host.invalid/simple -r https://secret-host.invalid/secret-deps.txt",
            "missing include value": "--index-url https://secret-host.invalid/simple -r",
            "empty long equals": "--requirement=",
            "unnamed editable": "-c a -e ./secret-pkg-dir",
            "missing editable value": "-c a --editable",
            "abbreviation": "--requirem secret-deps.txt",
            "editable abbreviation": "-c secret-constraint.txt --editab ./secret-pkg-dir",
        }
        forbidden = {
            "secret",
            str(self.root),
            str(self.outside),
            "undeclared-pkg",
            "constraint",
            "deps.txt",
        } | self.split_error_texts()
        for label, line in cases.items():
            with self.subTest(case=label):
                result = self.scan_requirements(
                    line + "\nown-pkg\n", payload(advisory("undeclared-pkg"))
                )
                self.assertUndeterminedOne(result)
                summary = result["summary"]
                self.assertEqual(summary.count(UNDETERMINED_NOTE_TOKEN), 1, summary)
                self.assertEqual(set(NOTE_TOKEN_RE.findall(summary)), {UNDETERMINED_NOTE_TOKEN}, summary)
                for text in forbidden | {line}:
                    self.assertNotIn(text, summary)

    def test_ac7_the_note_counts_each_undeclared_advisory_with_the_fixed_wording(self):
        result = self.scan_requirements(
            "-c a --requirem deps.txt\nown-pkg\n",
            payload(advisory("undeclared-one"), advisory("undeclared-two"), advisory("own-pkg")),
        )
        self.assertIn(PIP_NOTE_TWO, result["summary"])
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertEqual(set(NOTE_TOKEN_RE.findall(result["summary"])), {UNDETERMINED_NOTE_TOKEN})


# ---------------------------------------------------------------------------
# task0001 (sca-requirements-option-value-consumption): the value of every
# value-taking pip option on a requirements option line is consumed and
# discarded, so a value token is never read as `-r` / `-c` / `-e`, and every
# abbreviation of a value-taking long option leaves the name set incomplete.
#
# - AC-1: the separated form of every value-only option consumes the next
#   token (`--trusted-host -c -r deps.txt` still follows deps.txt), at the top
#   level, in an included file and across a continuation line.
# - AC-2: a consumed value is never interpreted.
# - AC-3: `long=value` and short-with-value forms are self-contained.
# - AC-4: abbreviations of value-taking long options are undetermined and
#   consume nothing.
# - AC-5: constraint, ambiguous and over-long names.
# - AC-6: unchanged behaviour: a value-less option at line end and a lone `--`.
# - AC-7: the summary and findings carry nothing from the line.
# ---------------------------------------------------------------------------

# Every option whose separated form takes a value that is only consumed.
VALUE_ONLY_OPTIONS = (
    "-i",
    "--index-url",
    "--pypi-url",
    "--extra-index-url",
    "-f",
    "--find-links",
    "--trusted-host",
    "--no-binary",
    "--only-binary",
    "--use-feature",
    "--hash",
    "--global-option",
    "-C",
    "--config-settings",
)
# The long names of those options, and the three interpreted long options.
VALUE_ONLY_LONG_OPTIONS = tuple(option for option in VALUE_ONLY_OPTIONS if option.startswith("--"))
VALUE_TAKING_LONG_OPTIONS = ("--requirement", "--constraint", "--editable") + VALUE_ONLY_LONG_OPTIONS


class TestValueOnlyOptionConsumption(MultiOptionLineCase):
    def test_ac1_the_separated_form_of_every_value_only_option_consumes_the_next_token(self):
        for option in VALUE_ONLY_OPTIONS:
            with self.subTest(option=option):
                names, opened, network_calls = self.resolve_line(
                    f"{option} -c -r deps.txt", {"deps.txt": "vuln-pkg==1.0\n"}, tail=""
                )
                self.assertEqual(names, {"vuln-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)
                self.assertEqual(network_calls, [])

    def test_ac1_the_scan_gives_one_finding_and_no_undetermined_note(self):
        with OpenRecorder() as recorder, NetworkGuard() as network:
            result = self.scan_requirements(
                "--trusted-host -c -r deps.txt\n",
                payload(advisory("vuln-pkg")),
                extra_files={"deps.txt": "vuln-pkg==1.0\n"},
            )
        self.assertEqual(len(result["findings"]), 1, result)
        self.assertTrue(result["findings"][0]["title"].startswith("vuln-pkg:"))
        self.assertNotIn(UNDETERMINED_NOTE_TOKEN, result["summary"])
        self.assertFalse(result["skipped"], result)
        self.assertIn(self.real("deps.txt"), recorder.opened)
        self.assertEqual(network.calls, [])

    def test_ac1_the_include_after_the_consumed_value_is_followed_in_an_included_file(self):
        names, opened, network_calls = self.resolve_line(
            "-r inc.txt",
            {"inc.txt": "--trusted-host -c -r deeper.txt\n", "deeper.txt": "deeper-pkg\n"},
            tail="",
        )
        self.assertEqual(names, {"deeper-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("deeper.txt"), opened)
        self.assertEqual(network_calls, [])

    def test_ac1_the_include_after_the_consumed_value_is_followed_across_a_continuation(self):
        names, opened, network_calls = self.resolve_line(
            "--trusted-host \\\n-c -r deeper.txt", {"deeper.txt": "deeper-pkg\n"}, tail=""
        )
        self.assertEqual(names, {"deeper-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("deeper.txt"), opened)
        self.assertEqual(network_calls, [])

    def test_ac2_a_consumed_value_shaped_like_an_editable_adds_no_name(self):
        for option in VALUE_ONLY_OPTIONS:
            with self.subTest(option=option):
                names, opened, _ = self.resolve_line(
                    f'{option} "-enamed-pkg" -r actual.txt', {"actual.txt": "actual-pkg\n"}, tail=""
                )
                self.assertNotIn("named-pkg", names)
                self.assertEqual(names, {"actual-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("actual.txt"), opened)

    def test_ac2_a_consumed_value_shaped_like_an_include_is_not_opened(self):
        for option in VALUE_ONLY_OPTIONS:
            with self.subTest(option=option):
                names, opened, network_calls = self.resolve_line(
                    f'{option} "-rdeps.txt" -r actual.txt',
                    {"deps.txt": "deps-pkg\n", "actual.txt": "actual-pkg\n"},
                    tail="",
                )
                self.assertNotIn(self.real("deps.txt"), opened)
                self.assertNotIn("deps-pkg", names)
                self.assertEqual(names, {"actual-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("actual.txt"), opened)
                self.assertEqual(network_calls, [])

    def test_ac2_a_consumed_value_shaped_like_a_constraint_does_not_hide_the_include_after_it(self):
        for option in VALUE_ONLY_OPTIONS:
            with self.subTest(option=option):
                names, opened, _ = self.resolve_line(
                    f"{option} -cconstraints.txt -r deps.txt",
                    {"deps.txt": "deps-pkg\n", "constraints.txt": "pinned-pkg\n"},
                    tail="",
                )
                self.assertEqual(names, {"deps-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)
                self.assertNotIn(self.real("constraints.txt"), opened)

    def test_ac2_a_lone_double_dash_is_consumed_as_the_value(self):
        for option in VALUE_ONLY_OPTIONS:
            with self.subTest(option=option):
                names, opened, network_calls = self.resolve_line(
                    f"{option} -- -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
                )
                self.assertEqual(names, {"deps-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)
                self.assertEqual(network_calls, [])

    def test_ac2_a_value_only_option_consumes_exactly_one_token(self):
        names, opened, _ = self.resolve_line(
            "-f one two -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
        )
        self.assertEqual(names, {"deps-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("deps.txt"), opened)

    def test_ac2_consecutive_value_only_options_each_consume_their_own_value(self):
        names, opened, _ = self.resolve_line(
            "-i -c --find-links -r --trusted-host -e -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
        )
        self.assertEqual(names, {"deps-pkg"})
        self.assertTrue(names.complete)
        self.assertIn(self.real("deps.txt"), opened)


class TestSelfContainedValueForms(MultiOptionLineCase):
    def test_ac3_the_equals_and_attached_forms_consume_no_following_token(self):
        forms = (
            "--trusted-host=x -r deps.txt",
            "--index-url= -r deps.txt",
            "-ihttps://example.invalid/simple -r deps.txt",
            "-f./wheels -r deps.txt",
            "-Ckey=val -r deps.txt",
        )
        for line in forms:
            with self.subTest(line=line):
                names, opened, network_calls = self.resolve_line(
                    line, {"deps.txt": "deps-pkg\n"}, tail=""
                )
                self.assertEqual(names, {"deps-pkg"}, line)
                self.assertTrue(names.complete, line)
                self.assertIn(self.real("deps.txt"), opened, line)
                self.assertEqual(network_calls, [], line)

    def test_ac3_every_value_only_long_option_in_its_equals_form_is_self_contained(self):
        for option in VALUE_ONLY_LONG_OPTIONS:
            for value in ("", "x"):
                with self.subTest(option=option, value=value):
                    names, opened, _ = self.resolve_line(
                        f"{option}={value} -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
                    )
                    self.assertEqual(names, {"deps-pkg"})
                    self.assertTrue(names.complete)
                    self.assertIn(self.real("deps.txt"), opened)

    def test_ac3_every_value_only_short_option_with_an_attached_value_is_self_contained(self):
        for option in ("-i", "-f", "-C"):
            with self.subTest(option=option):
                names, opened, _ = self.resolve_line(
                    f"{option}value -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
                )
                self.assertEqual(names, {"deps-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)

    def test_ac3_a_self_contained_value_is_never_interpreted(self):
        forms = (
            '--find-links="-rdeps.txt" -r actual.txt',
            "--find-links=-rdeps.txt -r actual.txt",
            "-f-rdeps.txt -r actual.txt",
            "-C-rdeps.txt -r actual.txt",
            "--trusted-host=-enamed-pkg -r actual.txt",
            "-i-enamed-pkg -r actual.txt",
        )
        for line in forms:
            with self.subTest(line=line):
                names, opened, _ = self.resolve_line(
                    line, {"deps.txt": "deps-pkg\n", "actual.txt": "actual-pkg\n"}, tail=""
                )
                self.assertEqual(names, {"actual-pkg"}, line)
                self.assertTrue(names.complete, line)
                self.assertNotIn(self.real("deps.txt"), opened, line)
                self.assertIn(self.real("actual.txt"), opened, line)

    def test_ac3_the_short_forms_are_case_sensitive(self):
        # The upper-case letters of `-i`, `-f`, `-r` and `-e` are not options
        # of the reader: they consume nothing, so the include after them is read.
        for option in ("-I", "-F", "-R", "-E"):
            with self.subTest(option=option):
                names, opened, _ = self.resolve_line(
                    f"{option} -r deps.txt", {"deps.txt": "deps-pkg\n"}, tail=""
                )
                self.assertEqual(names, {"deps-pkg"})
                self.assertTrue(names.complete)
                self.assertIn(self.real("deps.txt"), opened)


class TestValueTakingLongOptionAbbreviations(MultiOptionLineCase):
    def test_ac4_an_abbreviation_makes_the_set_incomplete_and_opens_nothing_after_c(self):
        for line in ("--trusted -c -r deps.txt", "--index -c -r deps.txt", "--find -c -r deps.txt"):
            with self.subTest(line=line):
                names, opened, network_calls = self.resolve_line(line, {"deps.txt": "deps-pkg\n"})
                self.assertFalse(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertNotIn(self.real("deps.txt"), opened, line)
                self.assertEqual(network_calls, [], line)

    def test_ac4_the_scan_counts_the_undeclared_advisory_once_and_reports_no_finding(self):
        for line in ("--trusted -c -r deps.txt", "--index -c -r deps.txt", "--find -c -r deps.txt"):
            with self.subTest(line=line), OpenRecorder() as recorder, NetworkGuard() as network:
                result = self.scan_requirements(
                    line + "\nown-pkg\n",
                    payload(advisory("undeclared-pkg")),
                    extra_files={"deps.txt": "deps-pkg\n"},
                )
                self.assertUndeterminedOne(result)
                self.assertEqual(result["summary"].count(UNDETERMINED_NOTE_TOKEN), 1)
                self.assertNotIn(self.real("deps.txt"), recorder.opened)
                self.assertEqual(network.calls, [])

    def test_ac4_an_abbreviation_does_not_consume_the_following_token(self):
        names, opened, _ = self.resolve_line("--trusted -r deps.txt", {"deps.txt": "deps-pkg\n"})
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg", "deps-pkg"})
        self.assertIn(self.real("deps.txt"), opened)

    def test_ac4_the_value_after_an_equals_is_never_a_name_or_a_file(self):
        names, opened, network_calls = self.resolve_line(
            "--trusted=-rdeps.txt", {"deps.txt": "deps-pkg\n"}
        )
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})
        self.assertNotIn(self.real("deps.txt"), opened)
        self.assertEqual(network_calls, [])
        names, opened, _ = self.resolve_line("--index=-enamed-pkg")
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})

    def test_ac4_every_proper_prefix_of_every_value_taking_long_option_is_undetermined(self):
        for long in VALUE_TAKING_LONG_OPTIONS:
            for end in range(3, len(long)):
                abbreviation = long[:end]
                for line in (
                    f"{abbreviation} -r deps.txt",
                    f"{abbreviation}=-rother.txt -r deps.txt",
                ):
                    with self.subTest(line=line):
                        names, opened, _ = self.resolve_line(
                            line, {"deps.txt": "deps-pkg\n", "other.txt": "other-pkg\n"}
                        )
                        self.assertFalse(names.complete, line)
                        self.assertEqual(names, {"own-pkg", "deps-pkg"}, line)
                        self.assertIn(self.real("deps.txt"), opened, line)
                        self.assertNotIn(self.real("other.txt"), opened, line)

    def test_ac4_an_abbreviation_inside_an_included_file_is_undetermined_too(self):
        names, opened, _ = self.resolve_line(
            "-r inc.txt", {"inc.txt": "--trusted -c -r deeper.txt\n", "deeper.txt": "deeper-pkg\n"}
        )
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})
        self.assertNotIn(self.real("deeper.txt"), opened)


class TestAbbreviationBoundaries(MultiOptionLineCase):
    def test_ac5_constraint_and_ambiguous_abbreviations_are_undetermined(self):
        for line in ("--constraint-extra x --con y", "--con y", "--no x"):
            with self.subTest(line=line):
                names, _, network_calls = self.resolve_line(line)
                self.assertFalse(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertEqual(network_calls, [], line)

    def test_ac5_a_name_longer_than_a_long_option_is_not_an_abbreviation(self):
        for line in (
            "--constraint-extra x",
            "--hash-extra x",
            "--index-urls x",
            "--requirement-extra x",
            "--editable-extra=x",
            "--trusted-host-extra x",
        ):
            with self.subTest(line=line):
                names, _, _ = self.resolve_line(line)
                self.assertTrue(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)

    def test_ac5_the_flags_without_a_value_are_not_abbreviations_of_a_value_taking_option(self):
        for line in (
            "--no-index",
            "--prefer-binary",
            "--require-hashes",
            "--pre",
            "--install-option=--x",
            "--install-option --x",
            "--no-index --prefer-binary --require-hashes --pre",
        ):
            with self.subTest(line=line):
                names, _, _ = self.resolve_line(line)
                self.assertTrue(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)

    def test_ac5_an_exact_long_name_is_never_its_own_abbreviation(self):
        for option in VALUE_TAKING_LONG_OPTIONS:
            with self.subTest(option=option):
                names, _, _ = self.resolve_line(f"{option}=x", {"x": "x-pkg\n"})
                self.assertTrue(names.complete, option)

    def test_ac5_a_bare_double_dash_is_not_an_abbreviation(self):
        for line in ("--", "--=x"):
            with self.subTest(line=line):
                names, _, _ = self.resolve_line(line)
                self.assertTrue(names.complete, line)
                self.assertEqual(names, {"own-pkg"}, line)


class TestUnchangedOptionLineBehaviour(MultiOptionLineCase):
    def test_ac6_a_value_taking_option_at_the_end_of_the_line_leaves_the_set_complete(self):
        for option in VALUE_ONLY_OPTIONS:
            for line in (option, f"-r deps.txt {option}"):
                with self.subTest(line=line):
                    names, opened, network_calls = self.resolve_line(line, {"deps.txt": "deps-pkg\n"})
                    self.assertTrue(names.complete, line)
                    self.assertLessEqual({"own-pkg"}, set(names), line)
                    self.assertEqual(network_calls, [], line)

    def test_ac6_the_value_less_forms_of_the_spec_resolve_to_the_own_name_only(self):
        for line in ("-i", "-f", "--trusted-host"):
            with self.subTest(line=line):
                names, _, _ = self.resolve_line(line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertTrue(names.complete, line)

    def test_ac6_a_lone_double_dash_that_is_not_a_value_is_ignored(self):
        forms = (
            "--",
            "-f ./wheels --",
            f"--index-url {EXAMPLE_INDEX_URL} -- --no-index",
            "-- --trusted-host",
        )
        for line in forms:
            with self.subTest(line=line):
                names, _, network_calls = self.resolve_line(line)
                self.assertEqual(names, {"own-pkg"}, line)
                self.assertTrue(names.complete, line)
                self.assertEqual(network_calls, [], line)

    def test_ac6_the_interpreted_options_keep_their_meaning(self):
        names, opened, _ = self.resolve_line(
            "-c c.txt -r deps.txt -e named-pkg --requirement=more.txt",
            {"deps.txt": "deps-pkg\n", "more.txt": "more-pkg\n", "c.txt": "pinned-pkg\n"},
        )
        self.assertEqual(names, {"own-pkg", "deps-pkg", "named-pkg", "more-pkg"})
        self.assertTrue(names.complete)
        self.assertNotIn(self.real("c.txt"), opened)

    def test_ac6_an_include_outside_the_root_after_a_consumed_value_is_still_refused(self):
        outside_file = self.write("outside-reqs.txt", "outside-pkg==1.0\n", base=self.outside)
        names, opened, network_calls = self.resolve_line(
            "--trusted-host x -r ../outside/outside-reqs.txt"
        )
        self.assertNotIn(os.path.realpath(outside_file), opened)
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})
        self.assertEqual(network_calls, [])
        names, opened, network_calls = self.resolve_line(
            "--trusted-host x -r https://example.invalid/reqs.txt"
        )
        self.assertFalse(names.complete)
        self.assertEqual(names, {"own-pkg"})
        self.assertEqual(network_calls, [])


class TestOptionValuesStayOutOfTheSummary(MultiOptionLineCase):
    SECRET_URL = "https://user:secret-token@secret-host.invalid/simple"

    def assert_nothing_from_the_line(self, result, line):
        summary = result["summary"]
        texts = [summary] + [finding["title"] for finding in result["findings"]]
        forbidden = (
            "secret",
            "user:",
            "deps.txt",
            "-c -r",
            str(self.root),
            str(self.outside),
            line,
        )
        for text in texts:
            for fragment in forbidden:
                self.assertNotIn(fragment, text)
        self.assertLessEqual(summary.count(UNDETERMINED_NOTE_TOKEN), 1, summary)
        self.assertLessEqual(set(NOTE_TOKEN_RE.findall(summary)), {UNDETERMINED_NOTE_TOKEN}, summary)

    def test_ac7_an_abbreviation_with_a_secret_looking_value_reaches_the_summary_nowhere(self):
        lines = (
            "--trusted=secret-host.invalid",
            f"--index={self.SECRET_URL}",
            "--find=secret-host.invalid -c -r deps.txt",
            "--trusted secret-host.invalid",
        )
        for line in lines:
            with self.subTest(line=line):
                result = self.scan_requirements(
                    line + "\nown-pkg\n",
                    payload(advisory("undeclared-pkg")),
                    extra_files={"deps.txt": "deps-pkg\n"},
                )
                self.assertUndeterminedOne(result)
                self.assertEqual(result["summary"].count(UNDETERMINED_NOTE_TOKEN), 1)
                self.assert_nothing_from_the_line(result, line)

    def test_ac7_consumed_credentials_before_a_constraint_reach_nothing(self):
        # The index URL is consumed; `-c -r deps.txt` is then a constraint that
        # takes `-r`, so the set stays complete and the undeclared advisory is
        # transitive: no finding and no note.
        lines = (
            f"--index-url {self.SECRET_URL} -c -r deps.txt",
            f"-i {self.SECRET_URL} -c -r deps.txt",
            f"--extra-index-url {self.SECRET_URL} --trusted-host secret-host.invalid -c -r deps.txt",
            f"--index-url={self.SECRET_URL} -c -r deps.txt",
        )
        for line in lines:
            with self.subTest(line=line):
                result = self.scan_requirements(
                    line + "\nown-pkg\n",
                    payload(advisory("undeclared-pkg")),
                    extra_files={"deps.txt": "deps-pkg\n"},
                )
                self.assertEqual(result["findings"], [], result)
                self.assertNotIn(UNDETERMINED_NOTE_TOKEN, result["summary"])
                self.assert_nothing_from_the_line(result, line)

    def test_ac7_consumed_credentials_before_an_include_reach_neither_the_summary_nor_a_finding(self):
        lines = (
            f"--index-url {self.SECRET_URL} -r deps.txt",
            f"-i {self.SECRET_URL} -r deps.txt",
            f"--extra-index-url {self.SECRET_URL} --trusted-host secret-host.invalid -r deps.txt",
            f"--index-url={self.SECRET_URL} -r deps.txt",
        )
        for line in lines:
            with self.subTest(line=line):
                result = self.scan_requirements(
                    line + "\n",
                    payload(advisory("deps-pkg"), advisory("undeclared-pkg")),
                    extra_files={"deps.txt": "deps-pkg\n"},
                )
                self.assertEqual(len(result["findings"]), 1, result)
                self.assertTrue(result["findings"][0]["title"].startswith("deps-pkg:"))
                self.assertNotIn(UNDETERMINED_NOTE_TOKEN, result["summary"])
                self.assert_nothing_from_the_line(result, line)


if __name__ == "__main__":
    unittest.main()
