"""Subprocess-driven tests for task0005: provider fallback chain inside the
Codex wrapper (feature-docs/batch-codex-autonomous-decisions/tasks/task0005.md).

Covers task0005 Acceptance Criteria:

- AC-1: the wrapper tries three chain entries in a fixed order, and the
  order/entry-definitions/switch-conditions live only in
  em-workflow/scripts/run_codex_exec.sh (proven behaviourally here by the
  observed attempt order, and by AC-6's scoped absence check).
- AC-2: a usage-limit response from entry 1 advances to entry 2, and a
  provider error from entry 2 advances to entry 3, driven end to end
  through a stubbed `codex` command placed first on PATH.
- AC-3: a failure that is NOT a switch condition -- including the existing
  timeout diagnostic/exit code -- surfaces unchanged and stops the chain.
- AC-4: the wrapper's own argument surface (mode / -C / --output-schema /
  prompt) is unchanged; proven by a direct run in the exact invocation form
  the consultation procedure (references/question-resolution.md) uses, plus
  a structural check that the parsing vocabulary is still present. The
  separate byte-for-byte wrapper-invocation-line pin lives in
  tests/test_codex_reviewer_temp_file_isolation.py and is left untouched.
- AC-5: on entry 1 the wrapper emits no marker and stdout is byte-identical
  to the stub's answer; when a later entry answered, exactly one additional
  stderr line appears with the declared `CODEX_FALLBACK:` prefix, and
  stdout still carries only the answer (never an earlier failed attempt's
  output).
- AC-6 (NFR4): none of the six batch resolution documents
  (IMPLEMENTATION.md C3) names a provider or describes usage-limit
  detection; scoped to exactly that document set, with a negative proof
  that the scan is not vacuous.
- AC-7 (NFR9): this module is hermetic (stubbed command on PATH, no
  network, no real provider) and imports only the Python standard library.

Test Notes' TDD-awkward point: the usage-limit and provider-error response
shapes are recognized from the underlying CLI's output, so this module
defines those shapes (via the stub's replies) as the contract
run_codex_exec.sh is written against, per the task plan's own instruction.
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
REFERENCES_DIR = REPO_ROOT / "em-workflow" / "references"

# IMPLEMENTATION.md C3: the batch resolution document set, exactly six files.
# Provider identifiers and usage-limit/provider-error detection descriptions
# must never appear in any of these -- this task's own scope is limited to
# asserting that, never repository-wide (the review reviewer chains
# legitimately name providers in reviewers.yaml / review-protocol.md /
# review-phase.md).
BATCH_RESOLUTION_DOCS = [
    REFERENCES_DIR / "question-resolution.md",
    REFERENCES_DIR / "batch-mode.md",
    REFERENCES_DIR / "batch-policies.yaml",
    REFERENCES_DIR / "phase-state.md",
    REFERENCES_DIR / "batch-terminal-line.md",
    REFERENCES_DIR / "question-packet-schema.md",
]

# Provider-name discipline (task0005 Design): these identifiers, and the
# detection-shape phrases below, are deliberately defined ONLY here and in
# the script itself -- never in a protocol document.
BETA_PROVIDER = "codex-fallback-provider-beta"
GAMMA_PROVIDER = "codex-fallback-provider-gamma"

FORBIDDEN_PROVIDER_MARKERS = (BETA_PROVIDER, GAMMA_PROVIDER)
FORBIDDEN_DETECTION_MARKERS = ("usage limit", "provider error")

# The stub's replies define the two response shapes the wrapper must
# recognize (Test Notes: "Fix those two shapes in the test module first and
# treat them as the contract the script is written against").
USAGE_LIMIT_TEXT = "Error: usage limit reached for this account."
PROVIDER_ERROR_TEXT = "Error: provider error - stream disconnected unexpectedly."

STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

BETA_MARKER = "codex-fallback-provider-beta"
GAMMA_MARKER = "codex-fallback-provider-gamma"

argv = sys.argv[1:]
joined = " ".join(argv)
if GAMMA_MARKER in joined:
    entry = 3
elif BETA_MARKER in joined:
    entry = 2
else:
    entry = 1

log_path = os.environ.get("CODEX_STUB_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"entry": entry, "argv": argv}) + "\\n")

behavior = os.environ.get("CODEX_STUB_BEHAVIOR_{}".format(entry), "success")

if behavior == "success":
    print("STUB_ANSWER: ok from entry {}".format(entry))
    sys.exit(0)
elif behavior == "usage_limit":
    print("Error: usage limit reached for this account.")
    sys.exit(1)
elif behavior == "provider_error":
    print("Error: provider error - stream disconnected unexpectedly.")
    sys.exit(1)
elif behavior == "timeout":
    sys.exit(124)
elif behavior == "other_error":
    print("Error: something unrelated broke.")
    sys.exit(3)
else:
    print("Error: unknown stub behavior {}".format(behavior))
    sys.exit(1)
"""


def _write_stub(stub_dir):
    stub_path = stub_dir / "codex"
    stub_path.write_text(STUB_SOURCE, encoding="utf-8")
    stub_path.chmod(0o755)
    return stub_path


def _run_chain(behaviors, wrapper_args=None, timeout=15):
    """Runs the real wrapper script as a subprocess with a stub `codex`
    placed first on PATH. `behaviors` maps chain-entry number (1/2/3) to one
    of: "success", "usage_limit", "provider_error", "timeout", "other_error".
    Returns (CompletedProcess, log_lines) -- log_lines is the parsed
    CODEX_STUB_LOG content, one {"entry": int, "argv": [...]} per attempt,
    in call order."""
    with tempfile.TemporaryDirectory() as stub_dir_s:
        stub_dir = Path(stub_dir_s)
        log_path = stub_dir / "stub.log"
        _write_stub(stub_dir)

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
        for entry, behavior in behaviors.items():
            env[f"CODEX_STUB_BEHAVIOR_{entry}"] = behavior

        args = wrapper_args if wrapper_args is not None else ["readonly", "do the thing"]
        proc = subprocess.run(
            ["bash", str(SCRIPT_PATH), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        log_lines = []
        if log_path.is_file():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    log_lines.append(json.loads(line))
        return proc, log_lines


def _find_leaks(text):
    """Returns the list of forbidden markers found in `text` (case
    insensitive). Empty list means clean."""
    lowered = text.lower()
    return [
        marker
        for marker in FORBIDDEN_PROVIDER_MARKERS + FORBIDDEN_DETECTION_MARKERS
        if marker.lower() in lowered
    ]


class TestFirstEntrySuccessIsUnchanged(unittest.TestCase):
    """AC-1 (order) + AC-5 (no marker on the primary path): entry 1
    succeeding tries only entry 1, and produces byte-identical stdout with
    no fallback marker anywhere."""

    def test_only_entry_one_is_attempted_on_success(self):
        proc, log_lines = _run_chain({1: "success"})

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(log_lines), 1, f"expected exactly one attempt, got {log_lines}")
        self.assertEqual(log_lines[0]["entry"], 1)
        for marker in (BETA_PROVIDER, GAMMA_PROVIDER):
            self.assertNotIn(marker, " ".join(log_lines[0]["argv"]))

    def test_stdout_is_byte_identical_to_stub_answer_with_no_marker(self):
        proc, _ = _run_chain({1: "success"})

        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 1\n")
        self.assertNotIn("CODEX_FALLBACK", proc.stdout)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)


class TestFallbackChainEndToEnd(unittest.TestCase):
    """AC-2: usage-limit at entry 1 advances to entry 2; provider error at
    entry 2 advances to entry 3; entry 3 answers."""

    def test_usage_limit_then_provider_error_falls_through_to_third_entry(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error", 3: "success"}
        )

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 3\n")

        self.assertEqual([line["entry"] for line in log_lines], [1, 2, 3])
        self.assertNotIn(BETA_PROVIDER, " ".join(log_lines[0]["argv"]))
        self.assertNotIn(GAMMA_PROVIDER, " ".join(log_lines[0]["argv"]))
        self.assertIn(BETA_PROVIDER, " ".join(log_lines[1]["argv"]))
        self.assertIn(GAMMA_PROVIDER, " ".join(log_lines[2]["argv"]))

    def test_exactly_one_fallback_line_names_the_answering_entry(self):
        proc, _ = _run_chain({1: "usage_limit", 2: "provider_error", 3: "success"})

        stderr_lines = [line for line in proc.stderr.splitlines() if "CODEX_FALLBACK" in line]
        self.assertEqual(len(stderr_lines), 1, f"stderr was: {proc.stderr!r}")
        self.assertTrue(stderr_lines[0].startswith("CODEX_FALLBACK:"))
        self.assertIn("3", stderr_lines[0])


class TestStdoutCleanlinessOnFallback(unittest.TestCase):
    """AC-5 edge case (Test Notes): stdout on the fallback path carries only
    the answering entry's output, never an earlier failed attempt's text."""

    def test_stdout_excludes_earlier_failed_attempts_text(self):
        proc, _ = _run_chain({1: "usage_limit", 2: "provider_error", 3: "success"})

        self.assertNotIn(USAGE_LIMIT_TEXT, proc.stdout)
        self.assertNotIn(PROVIDER_ERROR_TEXT, proc.stdout)
        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 3\n")


class TestNonSwitchFailuresSurfaceUnchanged(unittest.TestCase):
    """AC-3: only entry-1-usage-limit and entry-2-provider-error are switch
    conditions. Every other non-zero outcome, at any entry, surfaces to the
    caller exactly as today and stops the chain there."""

    def test_timeout_at_entry_one_stops_chain_with_existing_diagnostic(self):
        proc, log_lines = _run_chain({1: "timeout"})

        self.assertEqual(proc.returncode, 124)
        self.assertEqual(len(log_lines), 1)
        self.assertIn("CODEX_TIMEOUT:", proc.stderr)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)

    def test_generic_error_at_entry_one_stops_chain_unchanged(self):
        proc, log_lines = _run_chain({1: "other_error"})

        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "Error: something unrelated broke.\n")
        self.assertEqual(len(log_lines), 1)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)

    def test_provider_error_at_entry_one_does_not_advance_to_entry_two(self):
        # entry 1's ONLY switch condition is a usage-limit response -- a
        # provider error there is just another non-switch failure.
        proc, log_lines = _run_chain({1: "provider_error"})

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, PROVIDER_ERROR_TEXT + "\n")
        self.assertEqual(len(log_lines), 1)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)

    def test_usage_limit_shaped_response_from_entry_two_does_not_advance(self):
        # entry 2's ONLY switch condition is a provider error -- a
        # usage-limit-shaped response there does not reach entry 3.
        proc, log_lines = _run_chain({1: "usage_limit", 2: "usage_limit"})

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, USAGE_LIMIT_TEXT + "\n")
        self.assertEqual([line["entry"] for line in log_lines], [1, 2])
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)

    def test_last_entry_failure_surfaces_that_entrys_outcome_not_a_synthetic_success(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error", 3: "other_error"}
        )

        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "Error: something unrelated broke.\n")
        self.assertEqual([line["entry"] for line in log_lines], [1, 2, 3])
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)


class TestArgumentSurfaceUnchanged(unittest.TestCase):
    """AC-4: the wrapper's own argument surface (mode / -C / --output-schema
    / prompt) does not change. The byte-for-byte wrapper-invocation-line pin
    lives in test_codex_reviewer_temp_file_isolation.py and is untouched by
    this task; this class covers the direct-run half of AC-4."""

    def test_direct_run_in_consultation_procedure_invocation_form(self):
        # references/question-resolution.md's Codex consultation procedure
        # invokes the wrapper as: readonly -C "{project_root}" "$PROMPT"
        # (no --output-schema).
        with tempfile.TemporaryDirectory() as project_root:
            proc, log_lines = _run_chain(
                {1: "success"},
                wrapper_args=["readonly", "-C", project_root, "What should we do?"],
            )

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 1\n")
        self.assertEqual(len(log_lines), 1)

    def test_argument_parsing_vocabulary_is_still_present(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        for literal in ("readonly)", "readwrite)", "-C)", "--output-schema)"):
            self.assertIn(literal, text, f"missing {literal!r} in wrapper argument parsing")
        # The raw script source has the prompt's quotes backslash-escaped
        # (it lives inside a double-quoted bash string), so the literal text
        # on disk carries `\"prompt\"`, not `"prompt"`.
        self.assertIn(
            'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
            '[--output-schema F] \\"prompt\\"',
            text,
        )


class TestProviderNamesScopedToScriptAndTestModule(unittest.TestCase):
    """AC-6 (NFR4): none of the six batch resolution documents
    (IMPLEMENTATION.md C3) names a provider or describes usage-limit
    detection. Scoped to exactly that document set -- never
    repository-wide."""

    def test_no_batch_resolution_document_leaks_provider_info(self):
        for path in BATCH_RESOLUTION_DOCS:
            with self.subTest(doc=path.name):
                self.assertTrue(path.is_file(), f"missing {path}")
                text = path.read_text(encoding="utf-8")
                leaks = _find_leaks(text)
                self.assertEqual(
                    leaks, [],
                    f"{path.name} must not name a provider or describe "
                    f"usage-limit detection; found {leaks}",
                )

    def test_scan_catches_a_forged_provider_name_leak(self):
        forged = (
            "The wrapper may retry through codex-fallback-provider-beta "
            "before giving up."
        )
        self.assertIn(BETA_PROVIDER, _find_leaks(forged))

    def test_scan_catches_a_forged_usage_limit_detection_leak(self):
        forged = "The wrapper checks the reply text for a usage limit phrase."
        self.assertIn("usage limit", _find_leaks(forged))

    def test_scan_catches_a_forged_provider_error_detection_leak(self):
        forged = "A provider error in the reply text triggers the next entry."
        self.assertIn("provider error", _find_leaks(forged))


class TestHermeticAndStdlibOnly(unittest.TestCase):
    """AC-7 (NFR9): this module contacts no network and no real provider
    (every test above runs a stubbed `codex` placed first on PATH) and
    imports only the Python standard library."""

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
