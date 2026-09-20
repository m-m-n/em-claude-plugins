"""Subprocess-driven tests for task0001: removing the provider fallback
chain from the em-workflow Codex wrapper
(feature-docs/codex-wrapper-fallback-removal/tasks/task0001.md).

Replaces tests/test_codex_wrapper_provider_fallback.py, which made the
chain's existence its contract and therefore could not be repaired in
place (task plan Files to Modify).

Covers task0001 Acceptance Criteria:

- AC-1 (FR1, NFR2): a usage-limit diagnostic on stderr with a non-zero exit
  produces exactly one launch, the wrapper's own exit code, and the stub's
  stderr text reaching the caller verbatim.
- AC-2 (FR1): same for a provider-error diagnostic, and also for a
  usage-limit diagnostic while the former fallback prerequisites (the proxy
  credential and the profile file) are both present -- the gate no longer
  exists and configuring it changes nothing.
- AC-3 (FR1, NFR3): under every stub behaviour, no output line begins with
  either fallback marker prefix, and neither prefix string occurs anywhere
  in the script's text; a switch-shaped text present only on stdout
  produces exactly one launch and an outcome identical to the
  unrelated-error case.
- AC-4 (FR2): a schema-shaped reply on stdout plus a multi-line banner on
  stderr keeps every byte of the stdout content ahead of every byte of the
  stderr content in the wrapper's combined output, and the script never
  redirects the launch to a combined stream.
- AC-5 (FR3): a run that outlives the configured timeout exits 124 with a
  stderr diagnostic naming the configured timeout; an unrelated non-zero
  exit surfaces with its own exit code and output, with no diagnostic
  added.
- AC-6 (FR3): the argument-handling surface (invalid mode, missing prompt,
  unknown flag, each optional flag missing its argument, and the accepted
  flag set on the launch) is unchanged.
- AC-7 (FR6): the superseded module no longer exists; this module covers
  AC-1 through AC-5.
- AC-8 (NFR5): this module imports only the standard library and touches
  no network, no real provider, and no location outside its own temporary
  directories; both project test commands must pass.

Test Notes' TDD-awkward point (Configured-timeout read rule,
IMPLEMENTATION.md Shared Components): the timeout case runs an isolated
copy of the wrapper paired with a reduced configured value and asserts the
diagnostic names exactly that reduced value; it never waits for or asserts
the production timeout literal (task0002's concern). The diagnostic's
wording is asserted separately against the production script's own text.

Non-vacuity (IMPLEMENTATION.md Conventions): the launch-count matcher and
the fallback-marker-line matcher each carry a negative proof against forged
input, following the pattern of the existing version-bump and doc-pinning
modules.

Style note: this module follows the subprocess-harness pattern of the
module it replaces (stubbed `codex` first on PATH, isolated HOME, an
append-only JSON-lines log) -- see git history of
tests/test_codex_wrapper_provider_fallback.py -- adapted to a single
launch instead of a three-entry chain.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "run_codex_exec.sh"

# Fallback marker prefixes the chain used to emit (AC-3). Both must be
# permanently gone: from every stub behaviour's output AND from the
# script's own text.
FALLBACK_MARKER_PREFIXES = ("CODEX_FALLBACK:", "CODEX_FALLBACK_UNCONFIGURED:")

USAGE_MESSAGE = (
    'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
    '[--output-schema F] [--litellm MODEL] "prompt"'
)

STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys
import time

argv = sys.argv[1:]

log_path = os.environ.get("CODEX_STUB_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": argv}) + "\\n")

behavior = os.environ.get("CODEX_STUB_BEHAVIOR", "success")

if behavior == "success":
    print("STUB_ANSWER: ok")
    sys.exit(0)
elif behavior == "usage_limit":
    # The CLI's own diagnostic, stderr only -- there is no recognizer left
    # to react to it, so this must be treated as a plain non-zero exit.
    print("Error: usage limit reached for this account.", file=sys.stderr)
    sys.exit(1)
elif behavior == "provider_error":
    print("Error: provider error - stream disconnected unexpectedly.", file=sys.stderr)
    sys.exit(1)
elif behavior == "switch_text_stdout_only":
    # AC-3: a switch-shaped phrase present ONLY on stdout (the
    # model-generated reply), with the SAME exit code "other_error" below
    # uses, so the two behaviours can be compared for an identical outcome.
    print("Error: usage limit reached for this account.")
    sys.exit(5)
elif behavior == "other_error":
    print("Error: something unrelated broke.")
    sys.exit(5)
elif behavior == "schema_reply":
    print('{"result": "ok"}')
    print("BANNER line one.", file=sys.stderr)
    print("BANNER line two.", file=sys.stderr)
    print("BANNER line three.", file=sys.stderr)
    sys.exit(0)
elif behavior == "sleep_past_timeout":
    time.sleep(float(os.environ.get("CODEX_STUB_SLEEP_SECONDS", "5")))
    print("STUB_ANSWER: should not be seen")
    sys.exit(0)
else:
    print("Error: unknown stub behavior {}".format(behavior), file=sys.stderr)
    sys.exit(1)
"""


def _write_stub(stub_dir):
    stub_path = stub_dir / "codex"
    stub_path.write_text(STUB_SOURCE, encoding="utf-8")
    stub_path.chmod(0o755)
    return stub_path


def _read_log(log_path):
    log_lines = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                log_lines.append(json.loads(line))
    return log_lines


def _assert_exactly_one_launch(log_lines):
    """The launch-count matcher (AC-1 / AC-2 / AC-3 / AC-4 / AC-6). Raises
    with a descriptive message rather than returning a bool, so a caller
    that forgets to assert on the return value still gets caught."""
    if len(log_lines) != 1:
        raise AssertionError(
            f"expected exactly one launch, got {len(log_lines)} records: {log_lines}"
        )


def _lines_starting_with_marker(text):
    """The fallback-marker-line matcher (AC-3)."""
    return [line for line in text.splitlines() if line.startswith(FALLBACK_MARKER_PREFIXES)]


def _run_wrapper(behavior, wrapper_args=None, timeout=15, fallback_configured=True, extra_env=None):
    """Runs the real wrapper script as a subprocess with a stub `codex`
    placed first on PATH, an isolated HOME, and an append-only log the stub
    writes one record per launch into. `fallback_configured` reproduces the
    former fallback prerequisites (LITELLM_API_KEY + the litellm profile
    file under the isolated HOME) so AC-2 can show that configuring them no
    longer changes anything. Returns (CompletedProcess, log_lines)."""
    with tempfile.TemporaryDirectory() as stub_dir_s:
        stub_dir = Path(stub_dir_s)
        log_path = stub_dir / "stub.log"
        _write_stub(stub_dir)

        fake_home = stub_dir / "home"
        fake_home.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
        env["CODEX_STUB_BEHAVIOR"] = behavior
        env["HOME"] = str(fake_home)
        if fallback_configured:
            codex_home = fake_home / ".codex"
            codex_home.mkdir()
            (codex_home / "litellm.config.toml").write_text(
                "# stub litellm profile\n", encoding="utf-8"
            )
            env["LITELLM_API_KEY"] = "test-litellm-key"
        else:
            env.pop("LITELLM_API_KEY", None)
        if extra_env:
            env.update(extra_env)

        args = wrapper_args if wrapper_args is not None else ["readonly", "do the thing"]
        proc = subprocess.run(
            ["bash", str(SCRIPT_PATH), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc, _read_log(log_path)


def _run_wrapper_with_reduced_timeout(behavior, configured_timeout_seconds, wrapper_args=None,
                                       timeout=15, extra_env=None):
    """Configured-timeout read rule (IMPLEMENTATION.md Shared Components):
    copies the real wrapper script's TEXT into an isolated directory tree
    paired with its own codex-cli.yaml carrying a small, deterministic
    `configured_timeout_seconds`, so the timeout path is exercised without
    waiting for or asserting the production timeout literal (task0002's
    concern -- see the Configured-timeout read rule)."""
    with tempfile.TemporaryDirectory() as root_s:
        root = Path(root_s)
        scripts_dir = root / "scripts"
        references_dir = root / "references"
        scripts_dir.mkdir()
        references_dir.mkdir()

        isolated_script = scripts_dir / "run_codex_exec.sh"
        isolated_script.write_text(SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        isolated_script.chmod(0o755)
        (references_dir / "codex-cli.yaml").write_text(
            f"timeout: {configured_timeout_seconds}\n", encoding="utf-8"
        )

        stub_dir = root / "stub"
        stub_dir.mkdir()
        log_path = stub_dir / "stub.log"
        _write_stub(stub_dir)

        fake_home = root / "home"
        fake_home.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
        env["CODEX_STUB_BEHAVIOR"] = behavior
        env["HOME"] = str(fake_home)
        if extra_env:
            env.update(extra_env)

        args = wrapper_args if wrapper_args is not None else ["readonly", "do the thing"]
        proc = subprocess.run(
            ["bash", str(isolated_script), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc, _read_log(log_path)


class TestNonVacuousLaunchCountMatcher(unittest.TestCase):
    """Non-vacuity (IMPLEMENTATION.md Conventions / Test Notes): the
    launch-count matcher used throughout this module must be shown to fail
    against a forged two-launch log -- otherwise "exactly one launch"
    could pass on a broken reading of the log."""

    def test_matcher_accepts_a_single_record(self):
        _assert_exactly_one_launch([{"argv": []}])  # must not raise

    def test_matcher_rejects_a_forged_two_launch_log(self):
        with self.assertRaises(AssertionError):
            _assert_exactly_one_launch([{"argv": []}, {"argv": []}])

    def test_matcher_rejects_an_empty_log(self):
        with self.assertRaises(AssertionError):
            _assert_exactly_one_launch([])


class TestUsageLimitNoLongerSwitches(unittest.TestCase):
    """AC-1 (FR1, NFR2): a usage-limit diagnostic on stderr with a
    non-zero exit produces exactly one launch, the wrapper's own exit
    code, and the stub's stderr text reaching the caller verbatim (via the
    stdout-then-stderr concatenation, D3)."""

    def test_usage_limit_diagnostic_is_a_single_launch_passthrough(self):
        proc, log_lines = _run_wrapper("usage_limit")

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "Error: usage limit reached for this account.\n")
        self.assertEqual(proc.stderr, "")


class TestProviderErrorAndPrerequisitesNoLongerMatter(unittest.TestCase):
    """AC-2 (FR1): a provider-error diagnostic behaves the same way, and a
    usage-limit diagnostic while the former fallback prerequisites are
    present changes nothing -- the prerequisite gate no longer exists."""

    def test_provider_error_diagnostic_is_a_single_launch_passthrough(self):
        proc, log_lines = _run_wrapper("provider_error")

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(
            proc.stdout, "Error: provider error - stream disconnected unexpectedly.\n"
        )
        self.assertEqual(proc.stderr, "")

    def test_usage_limit_with_former_prerequisites_present_is_unaffected(self):
        proc, log_lines = _run_wrapper("usage_limit", fallback_configured=True)

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "Error: usage limit reached for this account.\n")
        self.assertEqual(proc.stderr, "")

    def test_configuring_the_former_prerequisites_changes_nothing(self):
        proc_with, log_with = _run_wrapper("usage_limit", fallback_configured=True)
        proc_without, log_without = _run_wrapper("usage_limit", fallback_configured=False)

        self.assertEqual(proc_with.returncode, proc_without.returncode)
        self.assertEqual(proc_with.stdout, proc_without.stdout)
        self.assertEqual(proc_with.stderr, proc_without.stderr)
        self.assertEqual(len(log_with), len(log_without))


class TestNoFallbackMarkerSurvives(unittest.TestCase):
    """AC-3 (FR1, NFR3): no output line begins with either fallback marker
    prefix under any stub behaviour, neither prefix occurs in the script's
    text, and a switch-shaped stdout-only text produces exactly one launch
    with an outcome identical to the unrelated-error case."""

    def test_no_behavior_emits_a_fallback_marker_line(self):
        for behavior in (
            "usage_limit",
            "provider_error",
            "success",
            "other_error",
            "switch_text_stdout_only",
            "schema_reply",
        ):
            with self.subTest(behavior=behavior):
                proc, log_lines = _run_wrapper(behavior)
                _assert_exactly_one_launch(log_lines)
                self.assertEqual(_lines_starting_with_marker(proc.stdout), [])
                self.assertEqual(_lines_starting_with_marker(proc.stderr), [])

    def test_script_text_contains_neither_marker_prefix(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        for marker in FALLBACK_MARKER_PREFIXES:
            self.assertNotIn(marker, text)

    def test_marker_line_matcher_catches_a_forged_marker_line(self):
        forged = "some output\nCODEX_FALLBACK: entry 2 answered\nmore text"
        self.assertEqual(
            _lines_starting_with_marker(forged), ["CODEX_FALLBACK: entry 2 answered"]
        )

    def test_switch_shaped_stdout_only_text_matches_the_unrelated_error_outcome(self):
        switch_proc, switch_log = _run_wrapper("switch_text_stdout_only")
        other_proc, other_log = _run_wrapper("other_error")

        _assert_exactly_one_launch(switch_log)
        _assert_exactly_one_launch(other_log)
        self.assertEqual(switch_proc.returncode, other_proc.returncode)
        self.assertEqual(switch_proc.stderr, other_proc.stderr)


class TestStreamOrderingPreserved(unittest.TestCase):
    """AC-4 (FR2): a schema-shaped reply on stdout and a multi-line banner
    on stderr keep every byte of the stdout content ahead of every byte of
    the stderr content in the combined output (D3), and the script never
    redirects the launch to a combined stream."""

    def test_stdout_content_precedes_stderr_content_in_combined_output(self):
        proc, log_lines = _run_wrapper("schema_reply")

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 0)
        schema_text = '{"result": "ok"}'
        banner_text = "BANNER line one."
        self.assertIn(schema_text, proc.stdout)
        self.assertIn(banner_text, proc.stdout)
        schema_end = proc.stdout.index(schema_text) + len(schema_text)
        banner_start = proc.stdout.index(banner_text)
        self.assertLess(
            schema_end,
            banner_start,
            "every byte of stdout content must precede every byte of stderr content",
        )

    def test_script_never_redirects_the_launch_to_a_combined_stream(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("2>&1", text)


class TestTimeoutPath(unittest.TestCase):
    """AC-5 (FR3): a run that outlives the configured timeout exits 124
    with a stderr diagnostic naming the configured timeout; an unrelated
    non-zero exit surfaces with its own exit code and output, with no
    diagnostic added."""

    def test_run_outliving_the_configured_timeout_exits_124_naming_it(self):
        reduced_timeout = 1
        proc, log_lines = _run_wrapper_with_reduced_timeout(
            "sleep_past_timeout",
            configured_timeout_seconds=reduced_timeout,
            extra_env={"CODEX_STUB_SLEEP_SECONDS": "5"},
        )

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 124)
        self.assertIn(f"{reduced_timeout} seconds", proc.stderr)

    def test_production_script_diagnostic_wording_matches(self):
        # Wording asserted separately from the numeric value (Test Notes /
        # Configured-timeout read rule): the literal production timeout
        # value belongs to task0002, never to this module.
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn('Codex did not respond within ${TIMEOUT} seconds', text)

    def test_unrelated_non_zero_exit_surfaces_with_own_code_and_no_diagnostic(self):
        proc, log_lines = _run_wrapper("other_error")

        _assert_exactly_one_launch(log_lines)
        self.assertEqual(proc.returncode, 5)
        self.assertEqual(proc.stdout, "Error: something unrelated broke.\n")
        self.assertEqual(proc.stderr, "")


class TestArgumentHandlingSurfaceUnchanged(unittest.TestCase):
    """AC-6 (FR3): invalid mode, missing prompt, unknown flag, and each
    optional flag missing its argument each produce the same message and
    non-zero exit as before this task; the accepted flag set on the launch
    is unchanged. A stub is still placed on PATH for hermeticity, but none
    of these cases should reach it."""

    def test_missing_all_arguments_produces_usage_message(self):
        proc, log_lines = _run_wrapper("success", wrapper_args=[])

        self.assertEqual(proc.returncode, 1)
        self.assertIn(USAGE_MESSAGE, proc.stderr)
        self.assertEqual(log_lines, [])

    def test_mode_only_with_no_further_args_produces_usage_message(self):
        proc, log_lines = _run_wrapper("success", wrapper_args=["readonly"])

        self.assertEqual(proc.returncode, 1)
        self.assertIn(USAGE_MESSAGE, proc.stderr)
        self.assertEqual(log_lines, [])

    def test_invalid_mode_produces_existing_message(self):
        proc, log_lines = _run_wrapper(
            "success", wrapper_args=["bogus-mode", "prompt text"]
        )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR: Invalid mode 'bogus-mode'. Use 'readonly' or 'readwrite'.", proc.stderr)
        self.assertEqual(log_lines, [])

    def test_unknown_flag_produces_existing_message(self):
        proc, log_lines = _run_wrapper(
            "success", wrapper_args=["readonly", "--bogus-flag", "prompt"]
        )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR: Unknown flag '--bogus-flag'", proc.stderr)
        self.assertEqual(log_lines, [])

    def test_dash_c_missing_argument_produces_existing_message(self):
        proc, log_lines = _run_wrapper("success", wrapper_args=["readonly", "-C"])

        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR: -C requires a directory argument", proc.stderr)
        self.assertEqual(log_lines, [])

    def test_output_schema_missing_argument_produces_existing_message(self):
        proc, log_lines = _run_wrapper(
            "success", wrapper_args=["readonly", "--output-schema"]
        )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR: --output-schema requires a file argument", proc.stderr)
        self.assertEqual(log_lines, [])

    def test_no_prompt_message_text_is_preserved_verbatim(self):
        # Structural, not behavioural: tracing the parser shows every valid
        # flag consumption requires (and leaves) at least one remaining
        # token, so this branch is unreachable through any input -- an
        # existing quirk, not something this task's chain removal may fix
        # (Design: "The chain's removal must not turn into a rewrite of the
        # argument parser."). The message text must still survive
        # byte-for-byte.
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("ERROR: No prompt provided", text)

    def test_accepted_flag_set_on_the_launch_is_unchanged(self):
        with tempfile.TemporaryDirectory() as workdir:
            proc, log_lines = _run_wrapper(
                "success",
                wrapper_args=[
                    "readonly", "-C", workdir, "--output-schema", "schema.json", "do the thing",
                ],
            )

        self.assertEqual(proc.returncode, 0)
        _assert_exactly_one_launch(log_lines)
        argv = log_lines[0]["argv"]
        for expected in (
            "--color", "never", "--skip-git-repo-check", "--ignore-rules",
            "-s", "read-only", "-c", 'model_reasoning_effort="xhigh"',
            "-C", workdir, "--output-schema", "schema.json", "--ignore-user-config",
        ):
            self.assertIn(expected, argv, f"{expected!r} missing from launch argv: {argv}")


class TestSupersededModuleRemoved(unittest.TestCase):
    """AC-7 (FR6): tests/test_codex_wrapper_provider_fallback.py no longer
    exists; this module is its replacement and covers AC-1 through AC-5
    above."""

    def test_provider_fallback_test_module_no_longer_exists(self):
        old_module_path = REPO_ROOT / "tests" / "test_codex_wrapper_provider_fallback.py"
        self.assertFalse(
            old_module_path.is_file(), f"{old_module_path} should have been deleted"
        )


class TestHermeticAndStdlibOnly(unittest.TestCase):
    """AC-8 (NFR5): this module imports only the Python standard library
    (every subprocess test above runs a stubbed `codex` placed first on
    PATH under an isolated HOME, touching no network and no real
    provider)."""

    def test_module_imports_are_all_stdlib(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
