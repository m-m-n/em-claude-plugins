"""Tests for em-workflow/scripts/scan-dependencies.py's `file-tasks`
robustness against OS errors (sca-file-tasks-robustness/task0002, extended by
file-tasks-temp-unlink-oserror/task0001).

An OS error raised while filing -- launching the entry point, or writing the
temporary references file -- must no longer kill `file-tasks`: the run ends
through the existing break-and-return path, prints exactly one JSON summary,
exits 0, and the summary names the failed package and every package never
attempted (`unattempted_packages`).

An OS error raised while deleting the temporary references file is a
different case: it is reported on stderr only and changes no outcome. The
filing result is decided by the entry-point launch and its exit status alone.

Acceptance criteria covered (feature-docs/sca-file-tasks-robustness/tasks/
task0002.md):

- AC-1 (TM-2): TestCliCreatePathLaunchFailure -- the real CLI, create path,
  the entry point stops being launchable after the 1st create.
- AC-2 (TM-2): TestCliAppendPathLaunchFailure -- the same on the append path.
- AC-3 (TM-2): TestTempFileWriteFailure (in-process, a writer test double
  raising an OS error on its 2nd call; create and append path) and
  TestFilingHelpersConvertOsErrors (the helper-level postcondition: write and
  launch errors leave the helper as EntryPointError).
- AC-4 (TM-3): TestUnattemptedPackagesWhenFirstPackageFails.
- AC-5 (TM-3, NFR5): TestSummaryKeySetAndEmptyUnattempted.
- AC-6 (TM-4, NFR2): TestUntrustedTextStaysOffTheSummary.
- AC-7 (NFR3, NFR5): TestDocstringAndModuleDiscipline (the `file_tasks`
  docstring and this module's own imports); tests/test_sca_task_filing.py
  is not modified by this task and keeps passing as-is.

Acceptance criteria covered (feature-docs/file-tasks-temp-unlink-oserror/
tasks/task0001.md):

- AC-1: TestFileTasksSurvivesTempFileDeletionFailure -- `file_tasks` over
  three packages, create path and append path.
- AC-2: TestFilingHelpersConvertOsErrors.
  test_temp_file_removal_failure_becomes_entry_point_error (identifier kept,
  body rewritten).
- AC-3, AC-4, AC-5: TestTempFileDeletionFailureNeverOverridesTheOutcome.
- AC-6: TestDocstringAndModuleDiscipline.test_deletion_failure_docstrings_*.

Test Notes followed: the external task system is never contacted -- every
filing test points the entry point at a stand-in executable defined in THIS
module (`_write_standin`) that records each call into a JSON log and replies
from a control file. To make the 2nd launch fail, the stand-in rewrites its
own first line to a nonexistent interpreter while serving one call, keeping
its executable mode so the entry-point validity check still passes. This
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
    spec = importlib.util.spec_from_file_location("_scan_dependencies_oserror_under_test", SCRIPT_PATH)
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

BAD_INTERPRETER_LINE = "#!/nonexistent-interpreter-for-file-tasks-oserror-test\n"

PKG_A, PKG_B, PKG_C = "pkg-a", "pkg-b", "pkg-c"


# A recording / scripted stand-in for the notion-task-dispatch entry point.
# The control file may carry `"break_interpreter_after": "<noun> <verb>"`:
# after serving a call with that key the stand-in rewrites its own first line
# to a nonexistent interpreter (the file keeps its executable mode), so every
# LATER launch fails in the parent process with an OS error.
STANDIN_TEMPLATE = '''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

SELF = Path({self_path!r})
CONTROL = Path({control!r})
CALLS = Path({calls!r})
BAD_INTERPRETER_LINE = {bad_line!r}

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
identifier = read_flag("--title")
if identifier is None:
    identifier = read_flag("--id")
specific_key = f"{{key}}:{{identifier}}" if identifier is not None else None
default_stdout = "[]" if key == "task list" else "{{}}"
if specific_key is not None and specific_key in control:
    resp = control[specific_key]
else:
    resp = control.get(key, {{"exit_code": 0, "stdout": default_stdout, "stderr": ""}})

if control.get("break_interpreter_after") == key:
    source = SELF.read_text(encoding="utf-8")
    SELF.write_text(BAD_INTERPRETER_LINE + source.split("\\n", 1)[1], encoding="utf-8")

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
        STANDIN_TEMPLATE.format(
            self_path=str(standin_path),
            control=str(control_path),
            calls=str(calls_path),
            bad_line=BAD_INTERPRETER_LINE,
        ),
        encoding="utf-8",
    )
    _make_executable(standin_path)
    return standin_path, control_path, calls_path


def _write_bad_interpreter_entry_point(tmp_dir):
    """An entry point that passes the validity check (an executable regular
    file) but cannot be launched at all (bad interpreter line)."""
    path = Path(tmp_dir) / "bad-entry-point"
    path.write_text(BAD_INTERPRETER_LINE, encoding="utf-8")
    _make_executable(path)
    return path


def _set_control(control_path, mapping):
    control_path.write_text(json.dumps(mapping), encoding="utf-8")


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


def _malformed_finding(title):
    return {
        "file": "package.json",
        "line": None,
        "line_end": None,
        "severity": "high",
        "category": "vulnerability",
        "title": title,
        "description": "n/a",
        "suggestion": "n/a",
    }


def _write_findings(tmp_dir, findings):
    path = Path(tmp_dir) / "findings.json"
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


def _incomplete_task(package):
    return {
        "id": f"task-{package}",
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


def _append_path_listing():
    return [_incomplete_task(p) for p in (PKG_A, PKG_B, PKG_C)]


def _listing_control(listing, **extra):
    control = {"task list": {"exit_code": 0, "stdout": json.dumps(listing)}}
    control.update(extra)
    return control


def _run_cli(tmp_dir, findings, entry_point):
    findings_path = _write_findings(tmp_dir, findings)
    return subprocess.run(
        [
            sys.executable, str(SCRIPT_PATH), "file-tasks",
            "--project-root", str(tmp_dir),
            "--feature", "sca-file-tasks-robustness",
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
def _captured_streams():
    """Captures what is written to stdout and stderr. Yields (stdout,
    stderr) as StringIO objects."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


@contextlib.contextmanager
def _unlink_failing_with(error):
    """Makes the OS-level unlink (`os.unlink`, which `Path.unlink` goes
    through) raise `error` for the duration of the block. Every temporary
    references file the real writer creates meanwhile is removed with the
    REAL unlink on exit, so the deletion failure leaves nothing behind.
    Yields (created_paths, unlink_mock)."""
    real_unlink = os.unlink
    real_writer = sd._write_references_tempfile
    created = []

    def recording_writer(lines):
        path = real_writer(lines)
        created.append(path)
        return path

    try:
        with patch.object(sd, "_write_references_tempfile", recording_writer), \
                patch.object(os, "unlink", side_effect=error) as unlink_mock:
            yield created, unlink_mock
    finally:
        for path in created:
            with contextlib.suppress(FileNotFoundError):
                real_unlink(path)


# ---------------------------------------------------------------------------
# AC-1 (TM-2): the real CLI, create path
# ---------------------------------------------------------------------------

class TestCliCreatePathLaunchFailure(unittest.TestCase):
    def test_launch_failure_on_second_create_ends_the_run_through_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control([], break_interpreter_after="task create"))

            proc = _run_cli(tmp, _create_path_findings(), standin)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(
                summary,
                _expected_summary(
                    filed_packages=[PKG_A],
                    failed_package=PKG_B,
                    failure_reason="task_create_failed",
                    unattempted_packages=[PKG_B, PKG_C],
                ),
            )
            # The 1st create was served; the 2nd never launched, the 3rd was
            # never attempted.
            self.assertEqual([c["--title"] for c in _calls_for(calls, "create")], [PKG_A])
            self.assertNotIn(PKG_C, json.dumps(_read_calls(calls)))
            self.assertIn("task_create_failed", proc.stderr)


# ---------------------------------------------------------------------------
# AC-2 (TM-2): the real CLI, append path
# ---------------------------------------------------------------------------

class TestCliAppendPathLaunchFailure(unittest.TestCase):
    def test_launch_failure_on_second_update_ends_the_run_through_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(
                control,
                _listing_control(_append_path_listing(), break_interpreter_after="task update"),
            )

            proc = _run_cli(tmp, _append_path_findings(), standin)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(
                summary,
                _expected_summary(
                    appended_packages=[PKG_A],
                    failed_package=PKG_B,
                    failure_reason="task_update_failed",
                    unattempted_packages=[PKG_B, PKG_C],
                ),
            )
            self.assertEqual([c["--id"] for c in _calls_for(calls, "update")], [f"task-{PKG_A}"])
            self.assertNotIn(PKG_C, json.dumps(_read_calls(calls)))
            self.assertIn("task_update_failed", proc.stderr)


# ---------------------------------------------------------------------------
# AC-3 (TM-2): an OS error while writing the temporary references file
# ---------------------------------------------------------------------------

class TestTempFileWriteFailure(unittest.TestCase):
    def _run_with_writer_failing_on_second_call(self, tmp, findings, listing):
        standin, control, calls = _write_standin(tmp)
        _set_control(control, _listing_control(listing))
        writer = _FailingWriter(2, OSError(errno.ENOSPC, "No space left on device"))
        with patch.object(sd, "_write_references_tempfile", writer), \
                contextlib.redirect_stderr(io.StringIO()):
            result = sd.file_tasks(Path(tmp), "sca-file-tasks-robustness", findings, str(standin))
        return result, calls, writer

    def test_create_path_write_failure_equals_the_launch_failure_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls, writer = self._run_with_writer_failing_on_second_call(
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

    def test_append_path_write_failure_equals_the_launch_failure_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls, writer = self._run_with_writer_failing_on_second_call(
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


class TestFilingHelpersConvertOsErrors(unittest.TestCase):
    """The helper postcondition: an OS error raised inside a filing helper
    while writing the temporary references file or while launching the
    subprocess leaves the helper as EntryPointError with the OS error kept as
    its cause. An OS error raised while deleting the temporary file is not
    part of this conversion: it is reported on stderr only and the helper
    outcome is unchanged."""

    OS_ERROR_TEXT = "simulated I/O failure"
    OS_ERROR = OSError(errno.EIO, OS_ERROR_TEXT)

    def _helpers(self, entry_point):
        return _filing_helpers(entry_point)

    def _assert_entry_point_failure_with_os_cause(self, call):
        with self.assertRaises(sd.EntryPointError) as ctx:
            call()
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertIs(ctx.exception.__cause__, self.OS_ERROR)
        return ctx.exception

    def test_write_failure_becomes_entry_point_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for name, call in self._helpers(standin).items():
                with self.subTest(helper=name), \
                        patch.object(sd, "_write_references_tempfile", side_effect=self.OS_ERROR):
                    self._assert_entry_point_failure_with_os_cause(call)

    def test_launch_failure_becomes_entry_point_error_and_temp_file_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for name, call in self._helpers(standin).items():
                written = []
                real_writer = sd._write_references_tempfile

                def recording_writer(lines, _real=real_writer, _written=written):
                    path = _real(lines)
                    _written.append(path)
                    return path

                with self.subTest(helper=name), \
                        patch.object(sd, "_write_references_tempfile", recording_writer), \
                        patch.object(sd.subprocess, "run", side_effect=self.OS_ERROR):
                    self._assert_entry_point_failure_with_os_cause(call)
                    self.assertEqual(len(written), 1)
                    self.assertFalse(os.path.exists(written[0]))

    def test_temp_file_removal_failure_becomes_entry_point_error(self):
        """AC-2: a failure to delete the temporary file is reported on
        stderr only. Both helpers, run against a stand-in that exits 0, return
        without raising; the error text is on stderr, once, and not on
        stdout; the deletion is attempted once. The identifier is kept
        unchanged so that records naming it stay resolvable."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for name, call in self._helpers(standin).items():
                with self.subTest(helper=name), \
                        _unlink_failing_with(self.OS_ERROR) as (created, unlink_mock), \
                        _captured_streams() as (out, err):
                    call()
                    self.assertEqual(len(created), 1)
                    self.assertEqual(unlink_mock.call_count, 1)
                    self.assertEqual(err.getvalue().count(self.OS_ERROR_TEXT), 1, err.getvalue())
                    self.assertNotIn(self.OS_ERROR_TEXT, out.getvalue())

    def test_failure_while_writing_leaves_no_temporary_file_behind(self):
        created = []
        real_factory = tempfile.NamedTemporaryFile

        def failing_factory(*args, **kwargs):
            handle = real_factory(*args, **kwargs)
            created.append(handle.name)

            def failing_write(_text):
                raise self.OS_ERROR

            handle.write = failing_write
            return handle

        try:
            with patch.object(sd.tempfile, "NamedTemporaryFile", failing_factory):
                with self.assertRaises(OSError):
                    sd._write_references_tempfile(["CVE-1 (high)"])
            self.assertEqual(len(created), 1)
            self.assertFalse(os.path.exists(created[0]))
        finally:
            for path in created:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(path)

    def test_non_zero_exit_keeps_its_existing_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, {
                "task create": {"exit_code": 1, "stdout": "", "stderr": "create refused"},
                "task update": {"exit_code": 1, "stdout": "", "stderr": "update refused"},
            })
            expected = {
                "create": ("task create failed", "create refused"),
                "append": ("task update failed", "update refused"),
            }
            for name, call in self._helpers(standin).items():
                with self.subTest(helper=name):
                    with self.assertRaises(sd.EntryPointError) as ctx:
                        call()
                    for fragment in expected[name]:
                        self.assertIn(fragment, str(ctx.exception))
                    self.assertIsNone(ctx.exception.__cause__)


# ---------------------------------------------------------------------------
# file-tasks-temp-unlink-oserror AC-3, AC-4, AC-5: an OS error raised while
# deleting the temporary references file never overrides the outcome decided
# by the launch and the exit status
# ---------------------------------------------------------------------------

class TestTempFileDeletionFailureNeverOverridesTheOutcome(unittest.TestCase):
    LAUNCH_ERROR_TEXT = "simulated launch failure"
    DELETION_ERROR_TEXT = "simulated deletion failure"
    LAUNCH_ERROR = OSError(errno.EIO, LAUNCH_ERROR_TEXT)
    DELETION_ERROR = OSError(errno.EACCES, DELETION_ERROR_TEXT)

    def test_launch_error_stays_the_cause_when_the_deletion_also_fails(self):
        """AC-3: the helper raises EntryPointError chained to the LAUNCH
        error object, never to the deletion error; the deletion error text
        goes to stderr only."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for name, call in _filing_helpers(standin).items():
                with self.subTest(helper=name), \
                        _unlink_failing_with(self.DELETION_ERROR) as (_created, unlink_mock), \
                        patch.object(sd.subprocess, "run", side_effect=self.LAUNCH_ERROR), \
                        _captured_streams() as (out, err):
                    with self.assertRaises(sd.EntryPointError) as ctx:
                        call()
                    self.assertIs(ctx.exception.__cause__, self.LAUNCH_ERROR)
                    self.assertIn(self.LAUNCH_ERROR_TEXT, str(ctx.exception))
                    self.assertNotIn(self.DELETION_ERROR_TEXT, str(ctx.exception))
                    self.assertEqual(unlink_mock.call_count, 1)
                    self.assertIn(self.DELETION_ERROR_TEXT, err.getvalue())
                    self.assertNotIn(self.DELETION_ERROR_TEXT, out.getvalue())

    def test_non_zero_exit_error_is_kept_when_the_deletion_fails(self):
        """AC-4: the existing non-zero-exit EntryPointError is raised: its
        message carries the entry point's stderr but not the deletion error
        text, and it has no chained cause."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, {
                "task create": {"exit_code": 1, "stdout": "", "stderr": "create refused"},
                "task update": {"exit_code": 1, "stdout": "", "stderr": "update refused"},
            })
            expected = {"create": "create refused", "append": "update refused"}
            for name, call in _filing_helpers(standin).items():
                with self.subTest(helper=name), \
                        _unlink_failing_with(self.DELETION_ERROR) as (_created, unlink_mock), \
                        _captured_streams() as (out, err):
                    with self.assertRaises(sd.EntryPointError) as ctx:
                        call()
                    self.assertIn(expected[name], str(ctx.exception))
                    self.assertNotIn(self.DELETION_ERROR_TEXT, str(ctx.exception))
                    self.assertIsNone(ctx.exception.__cause__)
                    self.assertEqual(unlink_mock.call_count, 1)
                    self.assertIn(self.DELETION_ERROR_TEXT, err.getvalue())
                    self.assertNotIn(self.DELETION_ERROR_TEXT, out.getvalue())

    def test_already_absent_file_is_accepted_silently(self):
        """AC-5: a file that is already gone at deletion time is not an
        error and is not reported."""
        absent = FileNotFoundError(errno.ENOENT, "No such file or directory")
        with tempfile.TemporaryDirectory() as tmp:
            standin, _control, _calls = _write_standin(tmp)
            for name, call in _filing_helpers(standin).items():
                with self.subTest(helper=name), \
                        _unlink_failing_with(absent) as (_created, unlink_mock), \
                        _captured_streams() as (out, err):
                    call()
                    self.assertEqual(unlink_mock.call_count, 1)
                    self.assertEqual(err.getvalue(), "")
                    self.assertEqual(out.getvalue(), "")


# ---------------------------------------------------------------------------
# file-tasks-temp-unlink-oserror AC-1: file_tasks over three packages while
# every deletion of the temporary references file fails
# ---------------------------------------------------------------------------

class TestFileTasksSurvivesTempFileDeletionFailure(unittest.TestCase):
    OS_ERROR_TEXT = "simulated deletion I/O failure"

    def _run_file_tasks(self, tmp, findings, listing):
        standin, control, calls = _write_standin(tmp)
        _set_control(control, _listing_control(listing))
        error = OSError(errno.EIO, self.OS_ERROR_TEXT)
        with _unlink_failing_with(error) as (created, _unlink_mock), \
                _captured_streams() as (out, err):
            result = sd.file_tasks(Path(tmp), "file-tasks-temp-unlink-oserror", findings, str(standin))
        return result, calls, created, out.getvalue(), err.getvalue()

    def test_create_path_files_all_three_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls, created, out, err = self._run_file_tasks(tmp, _create_path_findings(), [])
            self.assertEqual(result, _expected_summary(filed_packages=[PKG_A, PKG_B, PKG_C]))
            self.assertEqual(
                [c["--title"] for c in _calls_for(calls, "create")], [PKG_A, PKG_B, PKG_C],
            )
            # One failed deletion per package, each reported on stderr only.
            self.assertEqual(len(created), 3)
            self.assertEqual(err.count(self.OS_ERROR_TEXT), 3)
            self.assertNotIn(self.OS_ERROR_TEXT, out)

    def test_append_path_appends_to_all_three_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls, created, out, err = self._run_file_tasks(
                tmp, _append_path_findings(), _append_path_listing(),
            )
            self.assertEqual(result, _expected_summary(appended_packages=[PKG_A, PKG_B, PKG_C]))
            self.assertEqual(
                [c["--id"] for c in _calls_for(calls, "update")],
                [f"task-{p}" for p in (PKG_A, PKG_B, PKG_C)],
            )
            self.assertEqual(len(created), 3)
            self.assertEqual(err.count(self.OS_ERROR_TEXT), 3)
            self.assertNotIn(self.OS_ERROR_TEXT, out)


# ---------------------------------------------------------------------------
# AC-4 (TM-3): unattempted_packages when the 1st package fails
# ---------------------------------------------------------------------------

class TestUnattemptedPackagesWhenFirstPackageFails(unittest.TestCase):
    LONG_PACKAGE = "L" * 5000

    def _findings(self):
        return [
            _finding(PKG_A, "CVE-1"),
            _malformed_finding("no separator one"),
            _finding(PKG_B, "CVE-2"),
            _finding(PKG_A, "CVE-3"),  # a second finding for an already-seen package
            _finding(self.LONG_PACKAGE, "CVE-4"),
            _malformed_finding("no separator two"),
            _finding(PKG_C, "CVE-5"),
        ]

    def _assert_result(self, result):
        truncated = sd.truncate_untrusted(self.LONG_PACKAGE)
        # The scenario really exercises truncation.
        self.assertNotEqual(truncated, self.LONG_PACKAGE)
        self.assertTrue(truncated.endswith(sd.TRUNCATION_MARKER))

        self.assertEqual(result["filed_packages"], [])
        self.assertEqual(result["appended_packages"], [])
        self.assertEqual(result["failed_package"], PKG_A)
        self.assertEqual(result["failure_reason"], "task_create_failed")
        self.assertEqual(result["unattempted_packages"], [PKG_A, PKG_B, truncated, PKG_C])
        self.assertEqual([m["position"] for m in result["malformed_findings"]], [1, 5])
        for entry in result["unattempted_packages"]:
            self.assertNotIn("no separator", entry)

    def test_first_package_rejected_by_the_task_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control(
                [],
                **{f"task create:{PKG_A}": {"exit_code": 1, "stdout": "", "stderr": "refused"}},
            ))
            with contextlib.redirect_stderr(io.StringIO()):
                result = sd.file_tasks(Path(tmp), "feature", self._findings(), str(standin))
            self._assert_result(result)
            self.assertEqual([c["--title"] for c in _calls_for(calls, "create")], [PKG_A])

    def test_first_package_hits_an_os_error_writing_the_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, _listing_control([]))
            writer = _FailingWriter(1, OSError(errno.ENOSPC, "No space left on device"))
            with patch.object(sd, "_write_references_tempfile", writer), \
                    contextlib.redirect_stderr(io.StringIO()):
                result = sd.file_tasks(Path(tmp), "feature", self._findings(), str(standin))
            self._assert_result(result)
            self.assertEqual(_calls_for(calls, "create"), [])


# ---------------------------------------------------------------------------
# AC-5 (TM-3, NFR5): empty unattempted_packages elsewhere; the key set
# ---------------------------------------------------------------------------

class TestSummaryKeySetAndEmptyUnattempted(unittest.TestCase):
    def test_full_success_has_twelve_keys_and_nothing_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, _listing_control([]))
            result = sd.file_tasks(Path(tmp), "feature", _create_path_findings(), str(standin))
            self.assertEqual(set(result), SUMMARY_KEYS)
            self.assertEqual(result["unattempted_packages"], [])
            self.assertEqual(result["filed_packages"], [PKG_A, PKG_B, PKG_C])
            self.assertIsNone(result["failed_package"])
            self.assertIsNone(result["failure_reason"])

    def test_full_success_on_the_append_path_has_nothing_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, _listing_control(_append_path_listing()))
            result = sd.file_tasks(Path(tmp), "feature", _append_path_findings(), str(standin))
            self.assertEqual(set(result), SUMMARY_KEYS)
            self.assertEqual(result["unattempted_packages"], [])
            self.assertEqual(result["appended_packages"], [PKG_A, PKG_B, PKG_C])

    def test_mid_batch_failure_has_exactly_twelve_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, _listing_control(
                [],
                **{f"task create:{PKG_B}": {"exit_code": 1, "stdout": "", "stderr": "refused"}},
            ))
            with contextlib.redirect_stderr(io.StringIO()):
                result = sd.file_tasks(Path(tmp), "feature", _create_path_findings(), str(standin))
            self.assertEqual(set(result), SUMMARY_KEYS)
            self.assertEqual(result["unattempted_packages"], [PKG_B, PKG_C])

    def test_report_branch_has_twelve_keys_and_nothing_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            result = sd.file_tasks(Path(tmp), "feature", _create_path_findings(), None)
            self.assertEqual(result["branch"], "report")
            self.assertEqual(set(result), SUMMARY_KEYS)
            self.assertEqual(result["unattempted_packages"], [])

    def test_degraded_report_branch_has_twelve_keys_and_nothing_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            entry_point = _write_bad_interpreter_entry_point(tmp)
            result = sd.file_tasks(Path(tmp), "feature", _create_path_findings(), str(entry_point))
            self.assertEqual(result["branch"], "report")
            self.assertTrue(result["degraded"])
            self.assertEqual(result["degraded_reason"], "listing_launch_failed")
            self.assertEqual(set(result), SUMMARY_KEYS)
            self.assertEqual(result["unattempted_packages"], [])


# ---------------------------------------------------------------------------
# AC-6 (TM-4, NFR2): untrusted text stays off the machine-readable summary
# ---------------------------------------------------------------------------

OS_MARKER = "OSERR-MARKER-7f3a91"
ADVISORY_MARKER = "ADVISORY-MARKER-c42e08"


class TestUntrustedTextStaysOffTheSummary(unittest.TestCase):
    def _findings(self, base):
        findings = [
            _finding(package, advisory_id, advisory_title=f"short title {ADVISORY_MARKER}")
            for package, advisory_id in base
        ]
        findings.insert(1, _malformed_finding(f"no separator {ADVISORY_MARKER}"))
        return findings

    def _run_main_in_process(self, tmp, findings, entry_point):
        findings_path = _write_findings(tmp, findings)
        argv = [
            "file-tasks",
            "--project-root", str(tmp),
            "--feature", "sca-file-tasks-robustness",
            "--findings", str(findings_path),
            "--entry-point", str(entry_point),
        ]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exit_code = sd.main(argv)
        return exit_code, out.getvalue(), err.getvalue()

    def _assert_markers_stay_off_the_summary(self, exit_code, stdout, stderr, expected_reason):
        self.assertEqual(exit_code, sd.EXIT_OK, stderr)
        summary = _parse_single_json_object(self, stdout)
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(summary["failure_reason"], expected_reason)
        self.assertIn(summary["failure_reason"], FAILURE_REASON_TOKENS)
        self.assertEqual(summary["unattempted_packages"], [PKG_B, PKG_C])
        self.assertEqual(len(summary["malformed_findings"]), 1)

        self.assertNotIn(OS_MARKER, stdout)
        self.assertNotIn(ADVISORY_MARKER, stdout)
        self.assertNotIn(OS_MARKER, summary["failure_reason"])
        self.assertNotIn(ADVISORY_MARKER, summary["failure_reason"])
        for malformed in summary["malformed_findings"]:
            self.assertNotIn(OS_MARKER, malformed["reason"])
            self.assertNotIn(ADVISORY_MARKER, malformed["reason"])
        for package in summary["unattempted_packages"]:
            self.assertNotIn(OS_MARKER, package)
            self.assertNotIn(ADVISORY_MARKER, package)
        # The OS-error text is not lost: it goes to stderr.
        self.assertIn(OS_MARKER, stderr)

    def test_create_path_os_error_text_reaches_stderr_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, _listing_control([]))
            findings = self._findings([(PKG_A, "CVE-1"), (PKG_B, "CVE-2"), (PKG_C, "CVE-3")])
            writer = _FailingWriter(2, OSError(errno.EIO, f"I/O error {OS_MARKER}"))
            with patch.object(sd, "_write_references_tempfile", writer):
                exit_code, stdout, stderr = self._run_main_in_process(tmp, findings, standin)
            self._assert_markers_stay_off_the_summary(exit_code, stdout, stderr, "task_create_failed")

    def test_append_path_os_error_text_reaches_stderr_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, _calls = _write_standin(tmp)
            _set_control(control, _listing_control(_append_path_listing()))
            findings = self._findings(
                [(PKG_A, "CVE-NEW-1"), (PKG_B, "CVE-NEW-2"), (PKG_C, "CVE-NEW-3")]
            )
            writer = _FailingWriter(2, OSError(errno.EIO, f"I/O error {OS_MARKER}"))
            with patch.object(sd, "_write_references_tempfile", writer):
                exit_code, stdout, stderr = self._run_main_in_process(tmp, findings, standin)
            self._assert_markers_stay_off_the_summary(exit_code, stdout, stderr, "task_update_failed")

    def test_real_launch_failure_text_reaches_stderr_only(self):
        # A real OS error from the real CLI: the entry point's own path
        # carries the marker, and the OS error text names that path.
        with tempfile.TemporaryDirectory() as tmp:
            marked_dir = Path(tmp) / f"entry-{OS_MARKER}"
            standin, control, _calls = _write_standin(marked_dir)
            _set_control(control, _listing_control([], break_interpreter_after="task create"))
            findings = self._findings([(PKG_A, "CVE-1"), (PKG_B, "CVE-2"), (PKG_C, "CVE-3")])

            proc = _run_cli(marked_dir, findings, standin)

            self._assert_markers_stay_off_the_summary(
                proc.returncode, proc.stdout, proc.stderr, "task_create_failed",
            )


# ---------------------------------------------------------------------------
# AC-7 (NFR3, NFR5): docstring and module discipline
# ---------------------------------------------------------------------------

class TestDocstringAndModuleDiscipline(unittest.TestCase):
    ADDED_KEYS = (
        "malformed_findings", "listing_dropped_count", "failed_package",
        "failure_reason", "unattempted_packages",
    )

    def test_file_tasks_docstring_names_five_added_keys(self):
        doc = " ".join((sd.file_tasks.__doc__ or "").split())
        self.assertIn("five keys are added", doc.lower())
        self.assertNotIn("four keys are added", doc.lower())
        added = doc[doc.lower().index("five keys are added"):]
        for key in self.ADDED_KEYS:
            with self.subTest(key=key):
                self.assertIn(f"`{key}`", added)

    @staticmethod
    def _removal_sentences(doc):
        """The sentences of `doc` (whitespace-normalised, split after a full
        stop or semicolon) that speak about removing / deleting a file."""
        text = " ".join((doc or "").split())
        return [
            sentence for sentence in re.split(r"(?<=[.;])\s+", text)
            if re.search(r"remov|delet|unlink", sentence, re.IGNORECASE)
        ]

    def _assert_no_deletion_error_conversion_claim(self, doc, label):
        for sentence in self._removal_sentences(doc):
            with self.subTest(doc=label, sentence=sentence):
                self.assertNotIn("EntryPointError", sentence)
                self.assertNotIn("propagat", sentence.lower())

    def test_deletion_failure_docstrings_of_the_helpers_state_stderr_only(self):
        # AC-6: no claim that a deletion error propagates or becomes
        # EntryPointError; a statement that it is reported on stderr only and
        # leaves the result unchanged.
        for name in ("_run_entry_point_with_references", "create_security_task"):
            doc = getattr(sd, name).__doc__
            self._assert_no_deletion_error_conversion_claim(doc, name)
            with self.subTest(doc=name):
                self.assertTrue(
                    any("stderr" in s and "unchanged" in s for s in self._removal_sentences(doc)),
                    f"{name}: no sentence says a deletion error goes to stderr and leaves the result unchanged",
                )
        self._assert_no_deletion_error_conversion_claim(
            sd.append_security_task_references.__doc__, "append_security_task_references",
        )

    def test_deletion_failure_docstrings_of_this_module_claim_no_conversion(self):
        # AC-2: the rewritten test's docstring, the class docstring and the
        # module docstring do not say a deletion error becomes EntryPointError.
        method = TestFilingHelpersConvertOsErrors.test_temp_file_removal_failure_becomes_entry_point_error
        for label, doc in (
            ("module", sys.modules[__name__].__doc__),
            ("TestFilingHelpersConvertOsErrors", TestFilingHelpersConvertOsErrors.__doc__),
            ("test_temp_file_removal_failure_becomes_entry_point_error", method.__doc__),
        ):
            self._assert_no_deletion_error_conversion_claim(doc, label)

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
