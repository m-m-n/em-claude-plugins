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
            "git@example.invalid:org/repo.git",
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

        def stand_in_unit(ecosystem, directory, files, project_root, real_root, executable_path):
            unit = SCAN._group_audit(completed=True)
            if ecosystem["ecosystem"] == "go":
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

        def stand_in_unit(ecosystem, directory, files, project_root, real_root, executable_path):
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


if __name__ == "__main__":
    unittest.main()
