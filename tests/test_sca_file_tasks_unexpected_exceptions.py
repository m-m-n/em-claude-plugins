"""Tests for em-workflow/scripts/scan-dependencies.py's `file-tasks`
robustness against exceptions that are not OSError (feature
sca-file-tasks-unexpected-exceptions, task0001).

Two reproductions are pinned here:

- A package name (or a listed task id) containing NUL: `subprocess.run`
  raises ValueError for a NUL in an argv entry. A UnicodeEncodeError (a
  ValueError subclass) is the same kind of failure when it is raised by the
  temporary references-file writer. Both must end the batch through the
  existing break-and-return route, with one JSON summary and exit code 0.
- A finding whose recovered package, recovered advisory id or string
  severity cannot be encoded as UTF-8 (a lone surrogate): grouping skips it
  and records `{position, reason}` with a fixed reason of its own, and every
  other finding is processed.

Acceptance criteria covered (feature-docs/sca-file-tasks-unexpected-exceptions/
tasks/task0001.md):

- AC-1 (TM-2, TM-3): TestFilingHelpersConvertValueErrors.
- AC-2: TestTempFileWriter.
- AC-3 (TM-2): TestCliCreatePathNulPackageName.
- AC-4 (TM-2, TM-3): TestInProcessFilingFailures.
- AC-5 (TM-1): TestGroupingSkipsUnencodableText (direct grouping),
  TestCliUnencodableAdvisoryId (real CLI) and
  TestReportBranchesSkipUnencodableText (report and degraded report branch).
- AC-6 (NFR1, TM-4): the shared `_assert_summary_discipline` check applied
  inside every AC-3, AC-4 and AC-5 run, plus TestSummaryDisciplineMarkers.
- AC-7 (FR6, NFR4): TestDocstringAndCommentContent.
- AC-8 (NFR2): TestDocstringAndCommentContent.test_only_standard_library_imports.

Test Notes followed: the external task system is never contacted -- every
filing test points the entry point at a stand-in executable defined in THIS
module (`_write_standin`) that records each call into a JSON log and replies
from a control file. Findings that carry NUL or a lone surrogate reach the
CLI as JSON escapes, so the findings file itself stays valid UTF-8. This
module's own imports are standard-library only.
"""

import ast
import contextlib
import errno
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location(
        "_scan_dependencies_unexpected_exceptions_under_test", SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sd = load_script_module()


SUMMARY_KEYS = frozenset({
    "branch", "filed_packages", "appended_packages", "suppressed", "report_path",
    "degraded", "degraded_reason", "malformed_findings", "listing_dropped_count",
    "failed_package", "failure_reason", "unattempted_packages",
})

FAILURE_REASON_TOKENS = frozenset({"task_create_failed", "task_update_failed"})

PKG_A, PKG_B, PKG_C = "pkg-a", "pkg-b", "pkg-c"

LONE_SURROGATE = "\ud800"
NUL_EMBEDDED_TEXT = "embedded null byte"


# A recording / scripted stand-in for the notion-task-dispatch entry point.
# Each call is appended to a JSON log; the reply comes from a control file
# keyed by "<noun> <verb>" (default: exit 0, "[]" for `task list`, "{}"
# otherwise).
STANDIN_TEMPLATE = '''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CONTROL = Path({control!r})
CALLS = Path({calls!r})

argv = sys.argv[1:]
noun = argv[0] if len(argv) > 0 else None
verb = argv[1] if len(argv) > 1 else None
rest = argv[2:]


def read_flag(name):
    if name in rest:
        return rest[rest.index(name) + 1]
    return None


record = {{"noun": noun, "verb": verb, "args": rest}}
for flag in ("--title", "--type", "--priority", "--id", "--format"):
    val = read_flag(flag)
    if val is not None:
        record[flag] = val
for file_flag in ("--references-file", "--append-references-file"):
    path = read_flag(file_flag)
    if path is not None:
        record[file_flag + "-content"] = Path(path).read_text(encoding="utf-8")

calls = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else []
calls.append(record)
CALLS.write_text(json.dumps(calls), encoding="utf-8")

control = json.loads(CONTROL.read_text(encoding="utf-8")) if CONTROL.exists() else {{}}
key = f"{{noun}} {{verb}}"
default_stdout = "[]" if key == "task list" else "{{}}"
resp = control.get(key, {{"exit_code": 0, "stdout": default_stdout, "stderr": ""}})

sys.stderr.write(resp.get("stderr", ""))
sys.stdout.write(resp.get("stdout", ""))
sys.exit(resp.get("exit_code", 0))
'''


def _make_executable(path):
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_standin(tmp_dir):
    """Writes the stand-in under `tmp_dir`. Returns (standin_path,
    control_path, calls_path)."""
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    control_path = tmp_dir / "control.json"
    calls_path = tmp_dir / "calls.json"
    standin_path = tmp_dir / "standin.py"
    control_path.write_text("{}", encoding="utf-8")
    standin_path.write_text(
        STANDIN_TEMPLATE.format(control=str(control_path), calls=str(calls_path)),
        encoding="utf-8",
    )
    _make_executable(standin_path)
    return standin_path, control_path, calls_path


def _set_control(control_path, mapping):
    control_path.write_text(json.dumps(mapping), encoding="utf-8")


def _listing_control(listing, **extra):
    control = {"task list": {"exit_code": 0, "stdout": json.dumps(listing)}}
    control.update(extra)
    return control


def _read_calls(calls_path):
    if not calls_path.exists():
        return []
    return json.loads(calls_path.read_text(encoding="utf-8"))


def _calls_for(calls_path, verb):
    return [c for c in _read_calls(calls_path) if c["noun"] == "task" and c["verb"] == verb]


def _finding(package, advisory_id, severity="high", advisory_title="advisory"):
    return {
        "file": "package.json",
        "line": None,
        "line_end": None,
        "severity": severity,
        "category": "vulnerability",
        "title": f"{package}: {advisory_id} — {advisory_title}",
        "description": "affected range / fixed version / advisory summary",
        "suggestion": "bump the dependency to the fixed version",
    }


def _title_violating_finding(title="no separator here"):
    finding = _finding(PKG_A, "CVE-0")
    finding["title"] = title
    return finding


def _write_findings(tmp_dir, findings):
    path = Path(tmp_dir) / "findings.json"
    # json.dumps escapes NUL and lone surrogates, so the file is valid UTF-8.
    path.write_text(json.dumps(findings), encoding="utf-8")
    return path


def _init_git_repo(path):
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        env=env, capture_output=True, text=True, check=True,
    )


def _expected_summary(**overrides):
    """The twelve-key summary of an ntd-branch run with nothing to report;
    `overrides` replace individual keys."""
    summary = {
        "branch": "ntd",
        "filed_packages": [],
        "appended_packages": [],
        "suppressed": [],
        "report_path": None,
        "degraded": False,
        "degraded_reason": None,
        "malformed_findings": [],
        "listing_dropped_count": 0,
        "failed_package": None,
        "failure_reason": None,
        "unattempted_packages": [],
    }
    unknown = set(overrides) - set(summary)
    assert not unknown, unknown
    summary.update(overrides)
    return summary


def _run_cli(tmp_dir, findings, entry_point):
    findings_path = _write_findings(tmp_dir, findings)
    return subprocess.run(
        [
            sys.executable, str(SCRIPT_PATH), "file-tasks",
            "--project-root", str(tmp_dir),
            "--feature", "sca-file-tasks-unexpected-exceptions",
            "--findings", str(findings_path),
            "--entry-point", str(entry_point),
        ],
        capture_output=True, text=True,
    )


def _parse_single_json_object(testcase, stdout):
    """Parses the WHOLE of stdout as one JSON document (trailing text or a
    second document makes json.loads raise) and requires it to be an object."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        testcase.fail(f"stdout is not exactly one JSON document ({exc}): {stdout!r}")
    testcase.assertIsInstance(payload, dict)
    return payload


def _assert_summary_discipline(testcase, summary, forbidden_texts):
    """AC-6 (NFR1, TM-4): exactly the twelve keys; `failure_reason` null or
    one of the two tokens; neither `failure_reason` nor any
    `malformed_findings[].reason` contains any of `forbidden_texts` (the
    exception, package and advisory-id text of the run)."""
    testcase.assertEqual(set(summary), SUMMARY_KEYS)
    reason = summary["failure_reason"]
    testcase.assertTrue(
        reason is None or reason in FAILURE_REASON_TOKENS, f"unexpected failure_reason {reason!r}",
    )
    for text in forbidden_texts:
        if reason is not None:
            testcase.assertNotIn(text, reason)
        for malformed in summary["malformed_findings"]:
            testcase.assertNotIn(text, malformed["reason"])


def _has_surrogate(text):
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def _unicode_encode_error(reason="surrogates not allowed"):
    """A UnicodeEncodeError needs all five constructor arguments."""
    return UnicodeEncodeError("utf-8", LONE_SURROGATE, 0, 1, reason)


class _FailingWriter:
    """Test double for `_write_references_tempfile`: delegates to the real
    writer, except that call number `fail_on_call` raises `error`."""

    def __init__(self, fail_on_call, error):
        self._real = sd._write_references_tempfile
        self.fail_on_call = fail_on_call
        self.error = error
        self.calls = 0

    def __call__(self, reference_lines):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise self.error
        return self._real(reference_lines)


def _filing_helpers(entry_point):
    """Both public filing helpers, each as a zero-argument callable."""
    return {
        "create": lambda: sd.create_security_task(str(entry_point), PKG_A, ["CVE-1 (high)"]),
        "append": lambda: sd.append_security_task_references(
            str(entry_point), "task-1", ["CVE-1 (high)"],
        ),
    }


@contextlib.contextmanager
def _recording_writer():
    """Wraps the real writer so every path it returns is recorded; every
    recorded file is removed (if still present) on exit."""
    real_writer = sd._write_references_tempfile
    written = []

    def recording(lines):
        path = real_writer(lines)
        written.append(path)
        return path

    try:
        with patch.object(sd, "_write_references_tempfile", recording):
            yield written
    finally:
        for path in written:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)


def _incomplete_task(package, task_id=None):
    return {
        "id": task_id if task_id is not None else f"task-{package}",
        "package": package,
        "status": "incomplete",
        "references": "CVE-OLD (high)",
    }


def _create_path_findings():
    """Three packages, none of which has a task yet."""
    return [_finding(PKG_A, "CVE-1"), _finding(PKG_B, "CVE-2"), _finding(PKG_C, "CVE-3")]


def _append_path_findings():
    """Three packages that each already have an incomplete task and bring a
    NEW advisory."""
    return [_finding(PKG_A, "CVE-NEW-1"), _finding(PKG_B, "CVE-NEW-2"), _finding(PKG_C, "CVE-NEW-3")]


def _append_path_listing(nul_task_id_for=None):
    tasks = []
    for package in (PKG_A, PKG_B, PKG_C):
        task_id = f"task-{package}"
        if package == nul_task_id_for:
            task_id = f"task-{package}\x00tail"
        tasks.append(_incomplete_task(package, task_id))
    return tasks


# ---------------------------------------------------------------------------
# AC-1 (FR1; TM-2, TM-3): the filing helpers convert OSError and ValueError
# ---------------------------------------------------------------------------

class TestFilingHelpersConvertValueErrors(unittest.TestCase):
    """The helper postcondition: a ValueError (UnicodeEncodeError included)
    raised while writing the temporary references file or while launching the
    entry point leaves the helper as EntryPointError whose cause is that very
    exception object. Any other type (TypeError) is not converted."""

    def _chosen_errors(self):
        return {
            "ValueError": ValueError("simulated value error"),
            "UnicodeEncodeError": _unicode_encode_error(),
        }

    def test_ac1_writer_error_becomes_entry_point_error_with_the_exact_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for error_name, error in self._chosen_errors().items():
                for helper_name, call in _filing_helpers(standin).items():
                    with self.subTest(error=error_name, helper=helper_name), \
                            patch.object(sd, "_write_references_tempfile", side_effect=error):
                        with self.assertRaises(sd.EntryPointError) as ctx:
                            call()
                        self.assertIs(ctx.exception.__cause__, error)

    def test_ac1_launch_error_becomes_entry_point_error_and_temp_file_is_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for error_name, error in self._chosen_errors().items():
                for helper_name, call in _filing_helpers(standin).items():
                    with self.subTest(error=error_name, helper=helper_name), \
                            _recording_writer() as written, \
                            patch.object(sd.subprocess, "run", side_effect=error):
                        with self.assertRaises(sd.EntryPointError) as ctx:
                            call()
                        self.assertIs(ctx.exception.__cause__, error)
                        self.assertEqual(len(written), 1)
                        self.assertFalse(os.path.exists(written[0]))

    def test_ac1_type_error_at_the_writer_is_not_converted(self):
        error = TypeError("simulated type error")
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for helper_name, call in _filing_helpers(standin).items():
                with self.subTest(helper=helper_name), \
                        patch.object(sd, "_write_references_tempfile", side_effect=error):
                    with self.assertRaises(TypeError) as ctx:
                        call()
                    self.assertIs(ctx.exception, error)
                    self.assertNotIsInstance(ctx.exception, sd.EntryPointError)

    def test_ac1_type_error_at_the_launch_is_not_converted(self):
        error = TypeError("simulated type error")
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for helper_name, call in _filing_helpers(standin).items():
                with self.subTest(helper=helper_name), \
                        _recording_writer() as written, \
                        patch.object(sd.subprocess, "run", side_effect=error):
                    with self.assertRaises(TypeError) as ctx:
                        call()
                    self.assertIs(ctx.exception, error)
                    self.assertNotIsInstance(ctx.exception, sd.EntryPointError)
                    # The unchanged cleanup still removes the file.
                    self.assertEqual(len(written), 1)
                    self.assertFalse(os.path.exists(written[0]))

    def test_ac1_non_zero_exit_still_raises_entry_point_error_without_a_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, {
                "task create": {"exit_code": 1, "stdout": "", "stderr": "create refused"},
                "task update": {"exit_code": 1, "stdout": "", "stderr": "update refused"},
            })
            expected = {"create": "create refused", "append": "update refused"}
            for helper_name, call in _filing_helpers(standin).items():
                with self.subTest(helper=helper_name):
                    with self.assertRaises(sd.EntryPointError) as ctx:
                        call()
                    self.assertIn(expected[helper_name], str(ctx.exception))
                    self.assertIsNone(ctx.exception.__cause__)

    def test_ac1_non_executable_entry_point_raises_without_launching(self):
        with tempfile.TemporaryDirectory() as tmp:
            not_executable = Path(tmp) / "not-executable"
            not_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            not_executable.chmod(0o644)
            for helper_name, call in _filing_helpers(not_executable).items():
                with self.subTest(helper=helper_name), \
                        patch.object(sd.subprocess, "run") as run_mock, \
                        patch.object(sd, "_write_references_tempfile") as writer_mock:
                    with self.assertRaises(sd.EntryPointError):
                        call()
                    run_mock.assert_not_called()
                    writer_mock.assert_not_called()


# ---------------------------------------------------------------------------
# AC-2 (FR3): the writer removes the partial file for OSError and ValueError
# ---------------------------------------------------------------------------

class TestTempFileWriter(unittest.TestCase):
    def setUp(self):
        self.created = []
        real_factory = sd.tempfile.NamedTemporaryFile
        created = self.created

        def recording_factory(*args, **kwargs):
            handle = real_factory(*args, **kwargs)
            created.append(handle.name)
            return handle

        self._real_factory = real_factory
        self._recording_factory = recording_factory

    def tearDown(self):
        for path in self.created:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)

    def _factory_with_failing_write(self, error):
        created = self.created
        real_factory = self._real_factory

        def failing_factory(*args, **kwargs):
            handle = real_factory(*args, **kwargs)
            created.append(handle.name)

            def failing_write(_text):
                raise error

            handle.write = failing_write
            return handle

        return failing_factory

    def test_ac2_lone_surrogate_line_raises_unicode_encode_error_and_leaves_no_file(self):
        with patch.object(sd.tempfile, "NamedTemporaryFile", self._recording_factory):
            with self.assertRaises(UnicodeEncodeError) as ctx:
                sd._write_references_tempfile([f"{LONE_SURROGATE} (high)"])
        self.assertNotIsInstance(ctx.exception, sd.EntryPointError)
        self.assertEqual(len(self.created), 1)
        self.assertFalse(os.path.exists(self.created[0]))

    def test_ac2_value_error_while_writing_surfaces_raw_and_leaves_no_file(self):
        error = ValueError("simulated value error")
        with patch.object(sd.tempfile, "NamedTemporaryFile", self._factory_with_failing_write(error)):
            with self.assertRaises(ValueError) as ctx:
                sd._write_references_tempfile(["CVE-1 (high)"])
        self.assertIs(ctx.exception, error)
        self.assertEqual(len(self.created), 1)
        self.assertFalse(os.path.exists(self.created[0]))

    def test_ac2_os_error_while_writing_surfaces_raw_and_leaves_no_file(self):
        error = OSError(errno.EIO, "simulated I/O failure")
        with patch.object(sd.tempfile, "NamedTemporaryFile", self._factory_with_failing_write(error)):
            with self.assertRaises(OSError) as ctx:
                sd._write_references_tempfile(["CVE-1 (high)"])
        self.assertIs(ctx.exception, error)
        self.assertNotIsInstance(ctx.exception, sd.EntryPointError)
        self.assertEqual(len(self.created), 1)
        self.assertFalse(os.path.exists(self.created[0]))

    def test_ac2_failing_removal_of_the_partial_file_stays_suppressed(self):
        error = ValueError("simulated value error")
        removal_error = OSError(errno.EACCES, "simulated removal failure")
        with patch.object(sd.tempfile, "NamedTemporaryFile", self._factory_with_failing_write(error)), \
                patch.object(os, "unlink", side_effect=removal_error):
            with self.assertRaises(ValueError) as ctx:
                sd._write_references_tempfile(["CVE-1 (high)"])
        # The ORIGINAL exception is re-raised, never the removal error.
        self.assertIs(ctx.exception, error)

    def test_ac2_successful_write_returns_the_path_of_the_written_file(self):
        with patch.object(sd.tempfile, "NamedTemporaryFile", self._recording_factory):
            path = sd._write_references_tempfile(["CVE-1 (high)", "CVE-2 (low)"])
        self.assertEqual(self.created, [path])
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "CVE-1 (high)\nCVE-2 (low)\n")


# ---------------------------------------------------------------------------
# AC-3 (FR1, FR2, FR5; TM-2): the real CLI, create path, NUL in a package name
# ---------------------------------------------------------------------------

NUL_PACKAGE = "pkg-NULMARK\x00-b"


class TestCliCreatePathNulPackageName(unittest.TestCase):
    def test_ac3_nul_package_name_ends_the_batch_through_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control([]))
            findings = [
                _finding(PKG_A, "CVE-1"),
                _finding(NUL_PACKAGE, "CVE-2-ADVMARK"),
                _finding(PKG_C, "CVE-3"),
            ]

            proc = _run_cli(tmp, findings, standin)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn("task_create_failed", proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(
                summary,
                _expected_summary(
                    filed_packages=[PKG_A],
                    failed_package=NUL_PACKAGE,
                    failure_reason="task_create_failed",
                    unattempted_packages=[NUL_PACKAGE, PKG_C],
                ),
            )
            # Exactly one create call (pkg-a); pkg-c was never launched.
            self.assertEqual([c["--title"] for c in _calls_for(calls, "create")], [PKG_A])
            self.assertNotIn(PKG_C, json.dumps(_read_calls(calls)))
            # AC-6: the exception text is on stderr, never in a reason field.
            self.assertIn(NUL_EMBEDDED_TEXT, proc.stderr)
            _assert_summary_discipline(self, summary, [NUL_EMBEDDED_TEXT, "NULMARK", "ADVMARK"])


# ---------------------------------------------------------------------------
# AC-4 (FR1, FR2; TM-2, TM-3): file_tasks in-process against the stand-in
# ---------------------------------------------------------------------------

class TestInProcessFilingFailures(unittest.TestCase):
    ENCODE_MARKER = "ENCODEMARK-91c4"

    def _file_tasks(self, tmp, findings, entry_point):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result = sd.file_tasks(Path(tmp), "sca-file-tasks-unexpected-exceptions", findings, str(entry_point))
        return result, err.getvalue()

    def test_ac4a_nul_in_a_listed_task_id_ends_the_append_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control(_append_path_listing(nul_task_id_for=PKG_B)))

            result, stderr = self._file_tasks(tmp, _append_path_findings(), standin)

            self.assertEqual(
                result,
                _expected_summary(
                    appended_packages=[PKG_A],
                    failed_package=PKG_B,
                    failure_reason="task_update_failed",
                    unattempted_packages=[PKG_B, PKG_C],
                ),
            )
            self.assertEqual([c["--id"] for c in _calls_for(calls, "update")], [f"task-{PKG_A}"])
            self.assertNotIn(PKG_C, json.dumps(_read_calls(calls)))
            self.assertIn("task_update_failed", stderr)
            self.assertIn(NUL_EMBEDDED_TEXT, stderr)
            _assert_summary_discipline(self, result, [NUL_EMBEDDED_TEXT])

    def _writer_failing_on_second_call(self, tmp, findings, listing):
        standin, control, calls = _write_standin(tmp)
        _set_control(control, _listing_control(listing))
        writer = _FailingWriter(2, _unicode_encode_error(self.ENCODE_MARKER))
        with patch.object(sd, "_write_references_tempfile", writer):
            result, stderr = self._file_tasks(tmp, findings, standin)
        return result, stderr, calls, writer

    def test_ac4b_unicode_encode_error_from_the_writer_ends_the_create_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, stderr, calls, writer = self._writer_failing_on_second_call(
                tmp, _create_path_findings(), [],
            )
            self.assertEqual(writer.calls, 2)
            self.assertEqual(
                result,
                _expected_summary(
                    filed_packages=[PKG_A],
                    failed_package=PKG_B,
                    failure_reason="task_create_failed",
                    unattempted_packages=[PKG_B, PKG_C],
                ),
            )
            self.assertEqual([c["--title"] for c in _calls_for(calls, "create")], [PKG_A])
            self.assertIn("task_create_failed", stderr)
            self.assertIn(self.ENCODE_MARKER, stderr)
            _assert_summary_discipline(self, result, [self.ENCODE_MARKER])

    def test_ac4b_unicode_encode_error_from_the_writer_ends_the_append_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, stderr, calls, writer = self._writer_failing_on_second_call(
                tmp, _append_path_findings(), _append_path_listing(),
            )
            self.assertEqual(writer.calls, 2)
            self.assertEqual(
                result,
                _expected_summary(
                    appended_packages=[PKG_A],
                    failed_package=PKG_B,
                    failure_reason="task_update_failed",
                    unattempted_packages=[PKG_B, PKG_C],
                ),
            )
            self.assertEqual([c["--id"] for c in _calls_for(calls, "update")], [f"task-{PKG_A}"])
            self.assertIn("task_update_failed", stderr)
            self.assertIn(self.ENCODE_MARKER, stderr)
            _assert_summary_discipline(self, result, [self.ENCODE_MARKER])


# ---------------------------------------------------------------------------
# AC-5 (FR4; TM-1): findings whose text cannot be encoded as UTF-8
# ---------------------------------------------------------------------------

class TestGroupingSkipsUnencodableText(unittest.TestCase):
    def _bad_findings(self):
        """One finding per kind of unencodable text, each at position 1 of a
        three-finding input."""
        return {
            "package": _finding(f"pkg-b{LONE_SURROGATE}", "CVE-2"),
            "advisory id": _finding(PKG_B, f"CVE-2-{LONE_SURROGATE}"),
            "severity": _finding(PKG_B, "CVE-2", severity=f"hi{LONE_SURROGATE}gh"),
        }

    def _assert_skipped(self, bad_finding):
        findings = [_finding(PKG_A, "CVE-1"), bad_finding, _finding(PKG_C, "CVE-3")]
        groups, malformed = sd.group_findings_by_package(findings)
        self.assertEqual(list(groups), [PKG_A, PKG_C])
        self.assertEqual(groups[PKG_A], [("CVE-1", "high")])
        self.assertEqual(groups[PKG_C], [("CVE-3", "high")])
        self.assertEqual(malformed, [{"position": 1, "reason": sd.UNENCODABLE_FINDING_REASON}])
        self.assertNotEqual(sd.UNENCODABLE_FINDING_REASON, sd.MALFORMED_FINDING_REASON)
        return groups, malformed

    def test_ac5_each_kind_of_unencodable_text_is_skipped_and_recorded(self):
        for kind, bad_finding in self._bad_findings().items():
            with self.subTest(kind=kind):
                self._assert_skipped(bad_finding)

    def test_ac5_skipped_finding_joins_no_group_and_no_deduplication(self):
        # The bad finding shares its (encodable) package with a good one; the
        # good one is still grouped, and the bad finding's advisory id never
        # reaches the group.
        bad = _finding(PKG_A, f"CVE-BAD-{LONE_SURROGATE}")
        findings = [bad, _finding(PKG_A, "CVE-1")]
        groups, malformed = sd.group_findings_by_package(findings)
        self.assertEqual(groups, {PKG_A: [("CVE-1", "high")]})
        self.assertEqual([m["position"] for m in malformed], [0])

    def test_ac5_the_new_reason_is_a_fixed_text_and_never_finding_content(self):
        reason = sd.UNENCODABLE_FINDING_REASON
        self.assertIsInstance(reason, str)
        self.assertTrue(reason)
        self.assertFalse(_has_surrogate(reason))
        for kind, bad_finding in self._bad_findings().items():
            with self.subTest(kind=kind):
                _groups, malformed = sd.group_findings_by_package([bad_finding])
                self.assertEqual(malformed, [{"position": 0, "reason": reason}])
                self.assertNotIn("pkg-b", malformed[0]["reason"])
                self.assertNotIn("CVE-2", malformed[0]["reason"])

    def test_ac5_title_contract_and_encoding_failures_are_recorded_in_input_order(self):
        findings = [
            _title_violating_finding("no separator one"),
            _finding(PKG_A, "CVE-1"),
            _finding(f"pkg-x{LONE_SURROGATE}", "CVE-2"),
            _title_violating_finding("no separator two"),
            _finding(PKG_B, f"CVE-{LONE_SURROGATE}"),
            _finding(PKG_C, "CVE-5", severity=f"{LONE_SURROGATE}"),
        ]
        groups, malformed = sd.group_findings_by_package(findings)
        self.assertEqual(list(groups), [PKG_A])
        self.assertEqual(
            malformed,
            [
                {"position": 0, "reason": sd.MALFORMED_FINDING_REASON},
                {"position": 2, "reason": sd.UNENCODABLE_FINDING_REASON},
                {"position": 3, "reason": sd.MALFORMED_FINDING_REASON},
                {"position": 4, "reason": sd.UNENCODABLE_FINDING_REASON},
                {"position": 5, "reason": sd.UNENCODABLE_FINDING_REASON},
            ],
        )

    def test_ac5_a_severity_that_is_not_a_string_is_not_checked(self):
        findings = [
            _finding(PKG_A, "CVE-1", severity=None),
            _finding(PKG_B, "CVE-2", severity=7),
            _finding(PKG_C, "CVE-3", severity=[LONE_SURROGATE]),
        ]
        groups, malformed = sd.group_findings_by_package(findings)
        self.assertEqual(malformed, [])
        self.assertEqual(list(groups), [PKG_A, PKG_B, PKG_C])
        self.assertEqual(groups[PKG_B], [("CVE-2", 7)])

    def test_ac5_the_check_precedes_truncation(self):
        # A surrogate beyond the truncation budget is still detected: the
        # encodability check looks at the recovered value, not the truncated
        # one (which would have dropped the surrogate silently or crashed).
        long_package = "L" * (sd.UNTRUSTED_TEXT_MAX_BYTES + 100) + LONE_SURROGATE
        groups, malformed = sd.group_findings_by_package([_finding(long_package, "CVE-1")])
        self.assertEqual(groups, {})
        self.assertEqual(malformed, [{"position": 0, "reason": sd.UNENCODABLE_FINDING_REASON}])

    def test_ac5_encodable_text_is_grouped_exactly_as_before(self):
        findings = [
            _finding("pkg-é", "CVE-1"),
            _finding("pkg-é", "CVE-1"),  # de-duplicated
            _finding("pkg-é", "CVE-2", severity="critical"),
        ]
        groups, malformed = sd.group_findings_by_package(findings)
        self.assertEqual(malformed, [])
        self.assertEqual(groups, {"pkg-é": [("CVE-1", "high"), ("CVE-2", "critical")]})


class TestCliUnencodableAdvisoryId(unittest.TestCase):
    ADVISORY_MARKER = "CVE-ADVMARK"

    def test_ac5_cli_skips_the_finding_and_files_the_other_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control([]))
            findings = [
                _finding(PKG_A, "CVE-1"),
                _finding(PKG_B, f"{self.ADVISORY_MARKER}-{LONE_SURROGATE}"),
                _finding(PKG_C, "CVE-3"),
            ]

            proc = _run_cli(tmp, findings, standin)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(_has_surrogate(proc.stdout))
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(
                summary,
                _expected_summary(
                    filed_packages=[PKG_A, PKG_C],
                    malformed_findings=[{"position": 1, "reason": sd.UNENCODABLE_FINDING_REASON}],
                ),
            )
            self.assertEqual([c["--title"] for c in _calls_for(calls, "create")], [PKG_A, PKG_C])
            _assert_summary_discipline(self, summary, [self.ADVISORY_MARKER, PKG_B])


class TestReportBranchesSkipUnencodableText(unittest.TestCase):
    def _findings_with(self, bad_finding):
        return [_finding(PKG_A, "CVE-1"), bad_finding, _finding(PKG_C, "CVE-3")]

    def _bad_findings(self):
        return {
            "package": _finding(f"pkg-b{LONE_SURROGATE}", "CVE-2"),
            "advisory id": _finding(PKG_B, f"CVE-2-{LONE_SURROGATE}"),
            "severity": _finding(PKG_B, "CVE-2", severity=f"hi{LONE_SURROGATE}gh"),
        }

    def _assert_report_written(self, result, expected_degraded, expected_degraded_reason):
        self.assertEqual(result["branch"], "report")
        self.assertEqual(result["degraded"], expected_degraded)
        self.assertEqual(result["degraded_reason"], expected_degraded_reason)
        self.assertEqual(
            result["malformed_findings"],
            [{"position": 1, "reason": sd.UNENCODABLE_FINDING_REASON}],
        )
        self.assertEqual(set(result), SUMMARY_KEYS)
        report = Path(result["report_path"])
        self.assertTrue(report.is_file())
        text = report.read_text(encoding="utf-8")
        self.assertIn(f"## {PKG_A}", text)
        self.assertIn(f"## {PKG_C}", text)
        self.assertIn(sd.UNENCODABLE_FINDING_REASON, text)
        self.assertFalse(_has_surrogate(text))
        _assert_summary_discipline(self, result, ["pkg-b", "CVE-2"])

    def test_ac5_report_branch_writes_the_report_and_records_the_finding(self):
        for kind, bad_finding in self._bad_findings().items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                _init_git_repo(tmp)
                result = sd.file_tasks(
                    Path(tmp), "sca-file-tasks-unexpected-exceptions",
                    self._findings_with(bad_finding), None,
                )
                self._assert_report_written(result, False, None)

    def test_ac5_degraded_report_branch_writes_the_report_and_records_the_finding(self):
        for kind, bad_finding in self._bad_findings().items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                _init_git_repo(tmp)
                standin, control, _calls = _write_standin(tmp)
                _set_control(control, {"task list": {"exit_code": 1, "stdout": "", "stderr": "down"}})
                result = sd.file_tasks(
                    Path(tmp), "sca-file-tasks-unexpected-exceptions",
                    self._findings_with(bad_finding), str(standin),
                )
                self._assert_report_written(result, True, "listing_exit_nonzero")


# ---------------------------------------------------------------------------
# AC-6 (NFR1; TM-4): the summary-discipline check itself
# ---------------------------------------------------------------------------

class TestSummaryDisciplineMarkers(unittest.TestCase):
    """The discipline check is applied inside the AC-3, AC-4 and AC-5 runs;
    this class pins its behaviour on hand-built summaries so a vacuous check
    is detected."""

    def test_a_clean_summary_passes(self):
        _assert_summary_discipline(
            self,
            _expected_summary(
                failure_reason="task_create_failed",
                malformed_findings=[{"position": 0, "reason": sd.UNENCODABLE_FINDING_REASON}],
            ),
            ["MARKER"],
        )

    def test_a_failure_reason_carrying_the_marker_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_summary_discipline(
                self, _expected_summary(failure_reason="task_create_failed MARKER"), ["MARKER"],
            )

    def test_a_malformed_reason_carrying_the_marker_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_summary_discipline(
                self,
                _expected_summary(malformed_findings=[{"position": 0, "reason": "bad MARKER"}]),
                ["MARKER"],
            )

    def test_an_unknown_failure_token_or_extra_key_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_summary_discipline(self, _expected_summary(failure_reason="other"), [])
        extra = _expected_summary()
        extra["extra"] = 1
        with self.assertRaises(AssertionError):
            _assert_summary_discipline(self, extra, [])


# ---------------------------------------------------------------------------
# AC-7 (FR6, NFR4) and AC-8 (NFR2): docstring, comment and module discipline
# ---------------------------------------------------------------------------

class TestDocstringAndCommentContent(unittest.TestCase):
    ADDED_KEYS = (
        "malformed_findings", "listing_dropped_count", "failed_package",
        "failure_reason", "unattempted_packages",
    )

    @staticmethod
    def _normalise(doc):
        return " ".join((doc or "").split())

    @classmethod
    def _sentences(cls, doc):
        """Sentences of `doc`, split after a full stop or a semicolon
        followed by whitespace."""
        return re.split(r"(?<=[.;])\s+", cls._normalise(doc))

    @classmethod
    def _removal_sentences(cls, doc):
        return [s for s in cls._sentences(doc) if re.search(r"remov|delet|unlink", s, re.IGNORECASE)]

    def test_ac7_helpers_and_runner_name_value_error_alongside_os_error(self):
        for name in (
            "_run_entry_point_with_references", "create_security_task",
            "append_security_task_references",
        ):
            doc = self._normalise(getattr(sd, name).__doc__)
            with self.subTest(doc=name):
                self.assertIn("OSError", doc)
                self.assertIn("ValueError", doc)

    def test_ac7_filing_helper_docstrings_name_unicode_encode_error(self):
        for name in ("create_security_task", "append_security_task_references"):
            with self.subTest(doc=name):
                self.assertIn("UnicodeEncodeError", self._normalise(getattr(sd, name).__doc__))

    def test_ac7_writer_docstring_states_removal_on_both_and_the_raw_reraise(self):
        doc = sd._write_references_tempfile.__doc__
        text = self._normalise(doc)
        self.assertIn("UnicodeEncodeError", text)
        removal = self._removal_sentences(doc)
        self.assertTrue(
            any("OSError" in s and "ValueError" in s for s in removal),
            f"no removal sentence names OSError and ValueError: {removal}",
        )
        self.assertRegex(text, r"(?i)re-?raised")

    def test_ac7_grouping_docstring_states_the_utf8_encodability_skip(self):
        text = self._normalise(sd.group_findings_by_package.__doc__)
        for fragment in ("UTF-8", "package", "advisory id", "severity"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertRegex(text, r"(?i)skip")
        self.assertRegex(text, r"(?i)encod")

    def test_ac7_file_tasks_docstring_names_value_error_among_mid_batch_failures(self):
        text = self._normalise(sd.file_tasks.__doc__)
        self.assertIn("ValueError", text)
        self.assertIn("UnicodeEncodeError", text)
        failure_bullet = text[text.index("`failed_package`"):text.index("`unattempted_packages`")]
        self.assertIn("ValueError", failure_bullet)

    def test_ac7_file_tasks_docstring_keeps_the_five_added_keys(self):
        doc = self._normalise(sd.file_tasks.__doc__)
        self.assertIn("Five keys are ADDED", doc)
        added = doc[doc.index("Five keys are ADDED"):]
        positions = []
        for key in self.ADDED_KEYS:
            with self.subTest(key=key):
                self.assertIn(f"`{key}`", added)
            positions.append(added.find(f"`{key}`"))
        self.assertEqual(positions, sorted(positions))

    def test_ac7_nfr4_removal_sentences_never_claim_conversion_or_propagation(self):
        for name in (
            "_run_entry_point_with_references", "create_security_task",
            "append_security_task_references",
        ):
            for sentence in self._removal_sentences(getattr(sd, name).__doc__):
                with self.subTest(doc=name, sentence=sentence):
                    self.assertNotIn("EntryPointError", sentence)
                    self.assertNotIn("propagat", sentence.lower())

    def test_ac7_nfr4_runner_and_create_keep_a_removal_sentence_with_stderr_and_unchanged(self):
        for name in ("_run_entry_point_with_references", "create_security_task"):
            with self.subTest(doc=name):
                self.assertTrue(
                    any(
                        "stderr" in s and "unchanged" in s
                        for s in self._removal_sentences(getattr(sd, name).__doc__)
                    ),
                    f"{name}: no removal sentence contains both stderr and unchanged",
                )

    def test_ac7_malformed_reason_comment_does_not_claim_to_be_the_only_reason(self):
        lines = SCRIPT_PATH.read_text(encoding="utf-8").splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("MALFORMED_FINDING_REASON = ("))
        comment = []
        for line in reversed(lines[:index]):
            if not line.startswith("#"):
                break
            comment.append(line.lstrip("#").strip())
        comment_text = " ".join(reversed(comment)).lower()
        self.assertTrue(comment_text, "the malformed reason constant has no comment")
        for claim in ("the one reason", "every malformed finding", "only reason", "sole reason"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, comment_text)

    def test_ac7_new_reason_constant_sits_next_to_the_existing_one(self):
        lines = SCRIPT_PATH.read_text(encoding="utf-8").splitlines()
        old = next(i for i, line in enumerate(lines) if line.startswith("MALFORMED_FINDING_REASON = ("))
        new = next(i for i, line in enumerate(lines) if line.startswith("UNENCODABLE_FINDING_REASON = ("))
        self.assertLess(abs(new - old), 15)

    def test_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
