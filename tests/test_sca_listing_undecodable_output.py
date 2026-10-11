"""Tests for em-workflow/scripts/scan-dependencies.py's handling of a `task
list` output that is not valid UTF-8 (feature sca-listing-undecodable-output,
task0001).

Before this feature `list_security_tasks` captured the listing in text mode,
so a `task list` whose stdout (or stderr) held bytes that are not UTF-8 made
`subprocess.run` raise UnicodeDecodeError out of `file-tasks` as a traceback.
The listing is now received as bytes; stdout alone is decoded as strict
UTF-8, and a failure there is the sixth "listing unavailable" condition with
the fixed reason token `listing_output_undecodable`.

Acceptance criteria covered (feature-docs/sca-listing-undecodable-output/
tasks/task0001.md):

- AC-1 (TM-1, TM-3): TestCliRecurrence -- the `file-tasks` CLI against a stub
  `task list` that exits 0 with invalid UTF-8 on stdout.
- AC-2 (TM-1): TestDirectClassification -- `list_security_tasks` called
  directly: invalid bytes, a UTF-8-encoded surrogate, a valid non-ASCII
  array.
- AC-3: TestCheckOrder -- a non-zero exit wins over undecodable output; the
  decode step comes before the JSON step.
- AC-4 (TM-2): TestStderrIsNeverDecoded -- invalid stderr bytes do not make
  the listing unavailable.
- AC-5: tests/test_sca_task_filing.py::TestListingUnavailableReasons (the
  six-condition distinctness check lives there, not here).
- AC-6: TestDocstrings -- the ListingOutcome and list_security_tasks
  docstrings state six conditions in the same order.
- AC-7: TestUnchangedSurfaces (the process invocation used for `task create`
  / `task update` keeps its text-mode capture, the listing invocation is not
  in text mode and decodes strict UTF-8 only; this module imports only the
  standard library); the full-suite run and check-plugin-invariants.py are
  the definition-of-done run, not a test here.

Test Notes followed: the external task system is never contacted -- every
test points the entry point at a stub executable written into a temporary
directory by `_write_listing_standin`. The stub writes the scripted bytes to
`sys.stdout.buffer` / `sys.stderr.buffer` (raw bytes, never a text stream);
the bytes travel into the stub's source as hex, so this file and the stub
source stay valid UTF-8. This module's own imports are standard-library
only.
"""

import ast
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("_scan_dependencies_listing_undecodable_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sd = load_script_module()


UNDECODABLE = "listing_output_undecodable"

SIX_TOKENS = (
    "entry_point_invalid",
    "listing_launch_failed",
    "listing_exit_nonzero",
    UNDECODABLE,
    "listing_output_not_json",
    "listing_output_not_array",
)

SUMMARY_KEYS = frozenset({
    "branch", "filed_packages", "appended_packages", "suppressed", "report_path",
    "degraded", "degraded_reason", "malformed_findings", "listing_dropped_count",
    "failed_package", "failure_reason", "unattempted_packages",
})

# Bytes that are not valid UTF-8 (0xFF can never start a UTF-8 sequence).
INVALID_UTF8 = b"\xff\xfe"
# A surrogate code point (U+D800) encoded the way UTF-8 would encode it if
# surrogates were allowed; strict UTF-8 decoding rejects it.
UTF8_ENCODED_SURROGATE = b"\xed\xa0\x80"

MARKER = "LISTMARK-7d3e"

# Wording a leaked decode error (or the listing output itself) would carry.
LEAK_TEXTS = (
    MARKER,
    "UnicodeDecodeError",
    "codec can't decode",
    "can't decode",
    "invalid start byte",
    "invalid continuation byte",
    "0xff",
)

PKG_A = "pkg-a"


# Stub entry point. `task list` replies with the scripted exit code and raw
# bytes; any other invocation (`task create` / `task update`) records the call
# and behaves like the existing filing stubs: exit 0, "{}" on stdout.
STANDIN_TEMPLATE = '''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CALLS = Path({calls!r})

argv = sys.argv[1:]
noun = argv[0] if len(argv) > 0 else None
verb = argv[1] if len(argv) > 1 else None

if noun == "task" and verb == "list":
    sys.stderr.buffer.write(bytes.fromhex({stderr_hex!r}))
    sys.stderr.buffer.flush()
    sys.stdout.buffer.write(bytes.fromhex({stdout_hex!r}))
    sys.stdout.buffer.flush()
    sys.exit({exit_code!r})

calls = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else []
calls.append({{"noun": noun, "verb": verb, "args": argv[2:]}})
CALLS.write_text(json.dumps(calls), encoding="utf-8")
sys.stdout.write("{{}}")
sys.exit(0)
'''


def _write_listing_standin(tmp_dir, *, stdout=b"[]", stderr=b"", exit_code=0):
    """Writes the stub under `tmp_dir` and returns (standin_path,
    calls_path). `task list` exits `exit_code` after writing `stdout` and
    `stderr` as raw bytes. The calls file records every other invocation."""
    tmp_dir = Path(tmp_dir)
    calls_path = tmp_dir / "calls.json"
    standin_path = tmp_dir / "standin.py"
    standin_path.write_text(
        STANDIN_TEMPLATE.format(
            calls=str(calls_path),
            stdout_hex=stdout.hex(),
            stderr_hex=stderr.hex(),
            exit_code=exit_code,
        ),
        encoding="utf-8",
    )
    standin_path.chmod(standin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return standin_path, calls_path


def _read_calls(calls_path):
    if not calls_path.exists():
        return []
    return json.loads(calls_path.read_text(encoding="utf-8"))


def _finding(package, advisory_id, severity="high"):
    return {
        "file": "package.json",
        "line": None,
        "line_end": None,
        "severity": severity,
        "category": "vulnerability",
        "title": f"{package}: {advisory_id} — advisory",
        "description": "affected range / fixed version / advisory summary",
        "suggestion": "bump the dependency to the fixed version",
    }


def _init_git_repo(path):
    """The degraded report branch resolves its destination through `git
    worktree list`, so the project root has to be a git repository."""
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        env=env, capture_output=True, text=True, check=True,
    )


def _run_cli(tmp_dir, findings, entry_point):
    findings_path = Path(tmp_dir) / "findings.json"
    findings_path.write_text(json.dumps(findings), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable, str(SCRIPT_PATH), "file-tasks",
            "--project-root", str(tmp_dir),
            "--feature", "sca-listing-undecodable-output",
            "--findings", str(findings_path),
            "--entry-point", str(entry_point),
        ],
        capture_output=True, text=True, encoding="utf-8",
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


def _assert_no_leak(testcase, text, where):
    lowered = text.lower()
    for leak in LEAK_TEXTS:
        testcase.assertNotIn(leak.lower(), lowered, f"{where} contains {leak!r}")


def _list(entry_point):
    return sd.list_security_tasks(str(entry_point))


# ---------------------------------------------------------------------------
# AC-1 (FR3, FR5, FR8, NFR3; TM-1, TM-3): the recurrence test
# ---------------------------------------------------------------------------

class TestCliRecurrence(unittest.TestCase):
    def test_ac1_invalid_utf8_listing_ends_through_the_degraded_report_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            standin, calls = _write_listing_standin(
                tmp, stdout=INVALID_UTF8 + MARKER.encode("ascii"), exit_code=0,
            )

            proc = _run_cli(tmp, [_finding(PKG_A, "CVE-2024-1")], standin)

            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(set(summary), SUMMARY_KEYS)
            self.assertEqual(summary["branch"], "report")
            self.assertIs(summary["degraded"], True)
            self.assertEqual(summary["degraded_reason"], UNDECODABLE)
            # Nothing was filed: the run ended on the report branch.
            self.assertEqual(summary["filed_packages"], [])
            self.assertEqual(_read_calls(calls), [])

            report_path = Path(summary["report_path"])
            self.assertTrue(report_path.is_file(), summary["report_path"])
            report = report_path.read_text(encoding="utf-8")
            self.assertIn(UNDECODABLE, report)
            self.assertIn(PKG_A, report)

    def test_ac1_summary_and_report_carry_neither_the_output_nor_decode_wording(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            standin, _calls = _write_listing_standin(
                tmp,
                stdout=INVALID_UTF8 + MARKER.encode("ascii"),
                stderr=MARKER.encode("ascii"),
                exit_code=0,
            )

            proc = _run_cli(tmp, [_finding(PKG_A, "CVE-2024-1")], standin)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            _assert_no_leak(self, proc.stdout, "summary")
            self.assertEqual(summary["degraded_reason"], UNDECODABLE)
            report = Path(summary["report_path"]).read_text(encoding="utf-8")
            _assert_no_leak(self, report, "report file")


# ---------------------------------------------------------------------------
# AC-2 (FR1, FR3; TM-1): list_security_tasks called directly
# ---------------------------------------------------------------------------

class TestDirectClassification(unittest.TestCase):
    def _listing_outcome(self, **standin_kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _calls = _write_listing_standin(tmp, **standin_kwargs)
            return _list(standin)

    def test_ac2a_invalid_utf8_stdout_is_unavailable_without_raising(self):
        outcome = self._listing_outcome(stdout=INVALID_UTF8, exit_code=0)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, UNDECODABLE)
        self.assertIsNone(outcome.tasks)

    def test_ac2a_invalid_bytes_inside_otherwise_valid_json_are_unavailable(self):
        outcome = self._listing_outcome(stdout=b'[{"id": "t-1", "package": "\xff"}]', exit_code=0)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, UNDECODABLE)

    def test_ac2a_truncated_multibyte_sequence_is_unavailable(self):
        # U+3042 is E3 81 82; the final byte is missing.
        outcome = self._listing_outcome(stdout=b'["\xe3\x81', exit_code=0)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, UNDECODABLE)

    def test_ac2b_utf8_encoded_surrogate_is_unavailable(self):
        outcome = self._listing_outcome(stdout=b'["' + UTF8_ENCODED_SURROGATE + b'"]', exit_code=0)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, UNDECODABLE)

    def test_ac2b_bare_surrogate_bytes_are_unavailable(self):
        outcome = self._listing_outcome(stdout=UTF8_ENCODED_SURROGATE, exit_code=0)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, UNDECODABLE)

    def test_ac2c_valid_utf8_array_with_non_ascii_text_is_available_and_parsed(self):
        entries = [
            {"id": "t-1", "package": "パッケージ-ü", "status": "incomplete", "references": "参照 ✓ (high)"},
            {"id": "t-2", "package": "pkg-b", "status": "complete", "references": None},
        ]
        outcome = self._listing_outcome(stdout=json.dumps(entries, ensure_ascii=False).encode("utf-8"), exit_code=0)
        self.assertTrue(outcome.available)
        self.assertIsNone(outcome.reason)
        self.assertEqual(outcome.tasks, entries)
        self.assertEqual(outcome.dropped_count, 0)

    def test_reason_is_the_bare_token_not_the_decode_error_or_the_output(self):
        outcome = self._listing_outcome(stdout=INVALID_UTF8 + MARKER.encode("ascii"), exit_code=0)
        self.assertEqual(outcome.reason, UNDECODABLE)
        self.assertIsNone(outcome.tasks)


# ---------------------------------------------------------------------------
# AC-3 (FR2, NFR2): the classification order
# ---------------------------------------------------------------------------

class TestCheckOrder(unittest.TestCase):
    def _listing_outcome(self, **standin_kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _calls = _write_listing_standin(tmp, **standin_kwargs)
            return _list(standin)

    def test_ac3_nonzero_exit_with_invalid_utf8_stdout_is_exit_nonzero(self):
        outcome = self._listing_outcome(stdout=INVALID_UTF8, exit_code=1)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, "listing_exit_nonzero")

    def test_ac3_nonzero_exit_with_invalid_utf8_on_both_streams_is_exit_nonzero(self):
        outcome = self._listing_outcome(stdout=INVALID_UTF8, stderr=INVALID_UTF8, exit_code=3)
        self.assertFalse(outcome.available)
        self.assertEqual(outcome.reason, "listing_exit_nonzero")

    def test_ac3_nonzero_exit_reaches_the_report_branch_with_the_exit_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            standin, _calls = _write_listing_standin(tmp, stdout=INVALID_UTF8, exit_code=1)
            proc = _run_cli(tmp, [_finding(PKG_A, "CVE-2024-1")], standin)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = _parse_single_json_object(self, proc.stdout)
            self.assertEqual(summary["branch"], "report")
            self.assertEqual(summary["degraded_reason"], "listing_exit_nonzero")

    def test_ac3_undecodable_is_decided_before_the_json_step(self):
        # Neither stdout is JSON; the undecodable one is classified at the
        # decode step, the decodable one at the JSON step.
        undecodable = self._listing_outcome(stdout=b"not json \xff", exit_code=0)
        decodable = self._listing_outcome(stdout="not json é".encode("utf-8"), exit_code=0)
        self.assertEqual(undecodable.reason, UNDECODABLE)
        self.assertEqual(decodable.reason, "listing_output_not_json")

    def test_ac3_existing_tokens_keep_their_conditions(self):
        not_json = self._listing_outcome(stdout=b"not json", exit_code=0)
        not_array = self._listing_outcome(stdout=b'{"not": "an array"}', exit_code=0)
        self.assertEqual(not_json.reason, "listing_output_not_json")
        self.assertEqual(not_array.reason, "listing_output_not_array")
        self.assertEqual(sd.list_security_tasks("/nonexistent/entry-point-xyz").reason, "entry_point_invalid")

    def test_ac3_launch_failure_is_still_launch_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad-standin"
            bad.write_text("#!/nonexistent-interpreter-xyz\n", encoding="utf-8")
            bad.chmod(bad.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            self.assertEqual(_list(bad).reason, "listing_launch_failed")


# ---------------------------------------------------------------------------
# AC-4 (FR4; TM-2): stderr is received as bytes and never decoded
# ---------------------------------------------------------------------------

class TestStderrIsNeverDecoded(unittest.TestCase):
    def test_ac4_invalid_stderr_with_empty_array_stdout_keeps_the_listing_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, _calls = _write_listing_standin(tmp, stdout=b"[]", stderr=INVALID_UTF8, exit_code=0)
            outcome = _list(standin)
            self.assertTrue(outcome.available)
            self.assertEqual(outcome.tasks, [])

    def test_ac4_file_tasks_takes_the_filing_branch_despite_invalid_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, calls = _write_listing_standin(tmp, stdout=b"[]", stderr=INVALID_UTF8, exit_code=0)

            result = sd.file_tasks(
                Path(tmp), "sca-listing-undecodable-output", [_finding(PKG_A, "CVE-2024-1")], str(standin),
            )

            self.assertEqual(result["branch"], "ntd")
            self.assertFalse(result["degraded"])
            self.assertIsNone(result["degraded_reason"])
            self.assertIn(PKG_A, result["filed_packages"])
            creates = [c for c in _read_calls(calls) if c["verb"] == "create"]
            self.assertEqual(len(creates), 1)

    def test_ac4_invalid_stderr_with_undecodable_stdout_is_still_undecodable(self):
        # The reason comes from stdout alone, whatever stderr holds.
        with tempfile.TemporaryDirectory() as tmp:
            standin, _calls = _write_listing_standin(tmp, stdout=INVALID_UTF8, stderr=b"fine", exit_code=0)
            self.assertEqual(_list(standin).reason, UNDECODABLE)


# ---------------------------------------------------------------------------
# AC-6 (FR6): docstrings
# ---------------------------------------------------------------------------

def _flat(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _token_positions(text):
    return [text.find(token) for token in SIX_TOKENS]


class TestDocstrings(unittest.TestCase):
    def test_ac6_listing_outcome_docstring_states_six_conditions_and_names_all_tokens(self):
        doc = _flat(sd.ListingOutcome.__doc__)
        self.assertRegex(doc, r"\bsix\b")
        self.assertNotRegex(doc, r"\bfive\b")
        for token in SIX_TOKENS:
            self.assertIn(token, doc)

    def test_ac6_listing_outcome_docstring_lists_the_six_tokens_in_classification_order(self):
        doc = _flat(sd.ListingOutcome.__doc__)
        positions = _token_positions(doc)
        self.assertNotIn(-1, positions, f"a reason token is missing: {positions}")
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), 6)

    def test_ac6_list_security_tasks_docstring_describes_the_six_conditions_in_order(self):
        doc = _flat(sd.list_security_tasks.__doc__)
        self.assertRegex(doc, r"\bsix\b")
        positions = _token_positions(doc)
        self.assertNotIn(-1, positions, f"a reason token is missing: {positions}")
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), 6)

    def test_ac6_list_security_tasks_docstring_states_bytes_and_undecoded_stderr(self):
        doc = _flat(sd.list_security_tasks.__doc__)
        self.assertIn("bytes", doc)
        self.assertIn("stderr is not decoded", doc)

    def test_ac6_the_two_docstrings_agree_on_the_condition_count(self):
        outcome_doc = _flat(sd.ListingOutcome.__doc__)
        function_doc = _flat(sd.list_security_tasks.__doc__)
        for doc in (outcome_doc, function_doc):
            self.assertNotRegex(doc, r"\b(five|four|seven)\b")
            self.assertIn("six", doc)


# ---------------------------------------------------------------------------
# AC-7 (NFR1, NFR4, NFR6): unchanged surfaces and standard-library-only
# ---------------------------------------------------------------------------

def _script_function(name):
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {SCRIPT_PATH}")


def _subprocess_run_keywords(function_node):
    keywords = {}
    for node in ast.walk(function_node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ):
            for kw in node.keywords:
                keywords[kw.arg] = kw.value.value if isinstance(kw.value, ast.Constant) else kw.value
    return keywords


class TestUnchangedSurfaces(unittest.TestCase):
    def test_references_invocation_keeps_its_text_mode_capture(self):
        keywords = _subprocess_run_keywords(_script_function("_run_entry_point_with_references"))
        self.assertIs(keywords.get("text"), True)
        self.assertIs(keywords.get("capture_output"), True)

    def test_worktree_root_resolution_keeps_its_text_mode_capture(self):
        keywords = _subprocess_run_keywords(_script_function("resolve_main_worktree_root"))
        self.assertIs(keywords.get("text"), True)

    def test_listing_invocation_is_not_in_text_mode(self):
        keywords = _subprocess_run_keywords(_script_function("list_security_tasks"))
        self.assertIs(keywords.get("capture_output"), True)
        for name in ("text", "universal_newlines", "encoding", "errors"):
            self.assertNotIn(name, keywords)

    def test_listing_output_is_decoded_as_utf8_strict_whatever_the_locale(self):
        """FR1: the codec is fixed to UTF-8 and is not taken from the locale;
        no error handler other than strict is used."""
        decodes = [
            node for node in ast.walk(_script_function("list_security_tasks"))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "decode"
        ]
        self.assertEqual(len(decodes), 1, "stdout is decoded exactly once, stderr never")
        call = decodes[0]
        args = list(call.args)
        keywords = {kw.arg: kw.value for kw in call.keywords}
        encoding = args[0] if args else keywords.get("encoding")
        errors = args[1] if len(args) > 1 else keywords.get("errors")
        self.assertIsInstance(encoding, ast.Constant)
        self.assertEqual(str(encoding.value).lower().replace("_", "-"), "utf-8")
        if errors is not None:
            self.assertIsInstance(errors, ast.Constant)
            self.assertEqual(errors.value, "strict")

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
