"""Subprocess-driven tests for task0007: making the wrapper's fallback
entries resolvable and restoring the chain
(feature-docs/batch-codex-autonomous-decisions/tasks/task0007.md).

Covers task0007 Acceptance Criteria:

- AC-1: each non-primary entry's invocation carries a resolvable provider
  selection (the litellm proxy profile) and the model behind it, and no
  flag that suppresses the source that selection depends on -- asserted
  against the recorded invocation arguments field-by-field, not a literal
  argument string or a provider name alone.
- AC-2: the two non-primary entries resolve to distinct providers, in
  specification order (primary, then Vertex-fronted, then Muse-fronted),
  from the recorded invocation arguments of attempts 2 and 3.
- AC-3: the script's header comment declares which stream carries a switch
  shape (stderr) and which environment inputs the non-primary entries
  require (LITELLM_API_KEY, ~/.codex/litellm.config.toml); the stub emits
  both switch shapes on that same declared stream.
- AC-4: driven end to end through the harness, a usage-limit response at
  entry 1 advances to entry 2 and a provider error at entry 2 advances to
  entry 3; entry 3's answer is the only content on stdout, and exactly one
  stderr line with the declared prefix names the answering entry.
- AC-5 (NFR7): an attempt that fails with a switch shape present ONLY in
  the model-generated reply text (stdout) never advances the chain -- a
  negative proof that a repository or a model reply cannot force a
  provider switch.
- AC-6: when a switch condition fires but the non-primary entry's
  environment prerequisites are absent, no further invocation is
  attempted, the caller receives the failing entry's own exit code and
  output, and one stderr diagnostic states the fallback entry was not
  configured.
- AC-7: non-switch outcomes are unchanged -- the timeout keeps its
  existing diagnostic and exit code, an unrelated error surfaces verbatim
  and stops the chain, a provider error at entry 1 does not advance, and a
  usage-limit response at entry 2 does not advance.
- AC-8 (NFR4): none of the six batch resolution documents
  (IMPLEMENTATION.md C3) names a provider or describes usage-limit
  detection; scoped to exactly that document set, with a negative proof
  that the scan is not vacuous, and a marker list that matches the
  identifiers the script actually uses.
- AC-9 (NFR9): `python3 -m unittest discover -s tests` exits 0; this
  module stays hermetic (stubbed command on PATH, isolated HOME, no
  network, no real provider) and imports only the Python standard library.

Test Notes' TDD-awkward point: the usage-limit and provider-error response
shapes are recognized from the underlying CLI's own diagnostic stream
(stderr), so this module defines those shapes (via the stub's replies) as
the contract run_codex_exec.sh is written against, per the task plan's own
instruction. Order of work followed here: the stream contract (stub
shapes moved onto stderr) first, then the entry definitions (litellm
profile + model, per-entry environment gate) second, exactly as the task
plan's Test Notes direct.
"""

import ast
import json
import os
import re
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

# Provider-name discipline (task0007 Design): these identifiers -- the
# actual model names the script passes via `-m` -- are deliberately defined
# ONLY here and in the script itself, never in a protocol document. They
# replace the placeholder `codex-fallback-provider-{beta,gamma}` names a
# prior round invented, which resolved to nothing.
VERTEX_MODEL = "vertex-glm-5.2"
MUSE_MODEL = "muse-spark"

FORBIDDEN_PROVIDER_MARKERS = (VERTEX_MODEL, MUSE_MODEL)
FORBIDDEN_DETECTION_MARKERS = ("usage limit", "provider error")

# The stub's replies define the two response shapes the wrapper must
# recognize -- on the CLI's own diagnostic stream (stderr), never on the
# model-generated reply (stdout).
USAGE_LIMIT_TEXT = "Error: usage limit reached for this account."
PROVIDER_ERROR_TEXT = "Error: provider error - stream disconnected unexpectedly."

STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

VERTEX_MODEL = "vertex-glm-5.2"
MUSE_MODEL = "muse-spark"

argv = sys.argv[1:]

model = None
if "-m" in argv:
    idx = argv.index("-m")
    if idx + 1 < len(argv):
        model = argv[idx + 1]

if model == MUSE_MODEL:
    entry = 3
elif model == VERTEX_MODEL:
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
    # The CLI's own diagnostic: stderr only.
    print("Error: usage limit reached for this account.", file=sys.stderr)
    sys.exit(1)
elif behavior == "provider_error":
    # The CLI's own diagnostic: stderr only.
    print("Error: provider error - stream disconnected unexpectedly.", file=sys.stderr)
    sys.exit(1)
elif behavior == "usage_limit_in_reply":
    # AC-5 negative proof: the switch-shape text appears ONLY in the
    # model-generated reply (stdout) -- spoofed / attacker-influenceable --
    # and must NOT be recognized as a switch condition.
    print("Error: usage limit reached for this account.")
    sys.exit(1)
elif behavior == "provider_error_in_reply":
    # AC-5 negative proof, entry-2 variant.
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


def _model_arg(argv):
    """Returns the value following a `-m` flag in `argv`, or None."""
    if "-m" in argv:
        idx = argv.index("-m")
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def _run_chain(behaviors, wrapper_args=None, timeout=15, fallback_configured=True):
    """Runs the real wrapper script as a subprocess with a stub `codex`
    placed first on PATH. `behaviors` maps chain-entry number (1/2/3) to one
    of: "success", "usage_limit", "provider_error", "usage_limit_in_reply",
    "provider_error_in_reply", "timeout", "other_error".

    `fallback_configured` controls the AC-6 environment prerequisites
    (LITELLM_API_KEY + ~/.codex/litellm.config.toml) inside an isolated
    HOME, so neither outcome depends on whatever the developer's machine
    happens to have. Defaults to True so chain-advancing tests do not need
    to configure it themselves.

    Returns (CompletedProcess, log_lines) -- log_lines is the parsed
    CODEX_STUB_LOG content, one {"entry": int, "argv": [...]} per attempt,
    in call order."""
    with tempfile.TemporaryDirectory() as stub_dir_s:
        stub_dir = Path(stub_dir_s)
        log_path = stub_dir / "stub.log"
        _write_stub(stub_dir)

        fake_home = stub_dir / "home"
        fake_home.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
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


def _header_comment_block(text):
    """Returns the leading '#'-comment block at the top of the script
    (everything up to, but not including, the first non-comment,
    non-blank line -- e.g. `set -euo pipefail`), WITH the leading `#`
    markers kept intact (used for verbatim/marker-presence checks)."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            lines.append(line)
            continue
        break
    return "\n".join(lines)


def _header_comment_prose(text):
    """Like `_header_comment_block`, but strips each line's leading `#`
    marker first, so line-wrapped sentences read as continuous prose (used
    for phrase checks that must survive the header's own line-wrapping)."""
    stripped_lines = []
    for line in _header_comment_block(text).splitlines():
        content = line.strip()
        if content.startswith("#"):
            content = content[1:]
        stripped_lines.append(content)
    return "\n".join(stripped_lines)


def _normalize_whitespace(text):
    """Collapse whitespace runs (including comment line-wraps) to a single
    space, so a multi-word phrase check survives reflowing that does not
    change meaning."""
    return re.sub(r"\s+", " ", text)


class TestFirstEntrySuccessIsUnchanged(unittest.TestCase):
    """AC-1 (order) + AC-4 (no marker on the primary path): entry 1
    succeeding tries only entry 1, and produces byte-identical stdout with
    no fallback marker anywhere."""

    def test_only_entry_one_is_attempted_on_success(self):
        proc, log_lines = _run_chain({1: "success"})

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(log_lines), 1, f"expected exactly one attempt, got {log_lines}")
        self.assertEqual(log_lines[0]["entry"], 1)
        for marker in (VERTEX_MODEL, MUSE_MODEL):
            self.assertNotIn(marker, " ".join(log_lines[0]["argv"]))

    def test_entry_one_still_carries_ignore_user_config(self):
        proc, log_lines = _run_chain({1: "success"})

        self.assertEqual(proc.returncode, 0)
        self.assertIn("--ignore-user-config", log_lines[0]["argv"])

    def test_stdout_is_byte_identical_to_stub_answer_with_no_marker(self):
        proc, _ = _run_chain({1: "success"})

        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 1\n")
        self.assertNotIn("CODEX_FALLBACK", proc.stdout)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)


class TestNonPrimaryEntryArgumentSurface(unittest.TestCase):
    """AC-1 + AC-2: each non-primary entry's invocation carries a
    resolvable provider selection (the litellm proxy profile) and the
    model behind it, and carries no flag that suppresses the source that
    selection depends on. Assert the presence of these fields individually
    (Test Notes), not a literal argument string, and check the two
    non-primary entries resolve to distinct providers in specification
    order."""

    def test_entry_two_selects_the_litellm_profile_and_the_vertex_model(self):
        proc, log_lines = _run_chain({1: "usage_limit", 2: "success"})

        self.assertEqual(proc.returncode, 0)
        entry_two_argv = log_lines[1]["argv"]
        self.assertIn("-p", entry_two_argv)
        self.assertEqual(entry_two_argv[entry_two_argv.index("-p") + 1], "litellm")
        self.assertEqual(_model_arg(entry_two_argv), VERTEX_MODEL)
        self.assertNotIn(
            "--ignore-user-config",
            entry_two_argv,
            "entry 2 must not suppress the config source its profile depends on",
        )

    def test_entry_three_selects_the_litellm_profile_and_the_muse_model(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error", 3: "success"}
        )

        self.assertEqual(proc.returncode, 0)
        entry_three_argv = log_lines[2]["argv"]
        self.assertIn("-p", entry_three_argv)
        self.assertEqual(entry_three_argv[entry_three_argv.index("-p") + 1], "litellm")
        self.assertEqual(_model_arg(entry_three_argv), MUSE_MODEL)
        self.assertNotIn(
            "--ignore-user-config",
            entry_three_argv,
            "entry 3 must not suppress the config source its profile depends on",
        )

    def test_non_primary_entries_resolve_to_distinct_providers_in_spec_order(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error", 3: "success"}
        )

        self.assertEqual(proc.returncode, 0)
        self.assertEqual([line["entry"] for line in log_lines], [1, 2, 3])
        entry_two_model = _model_arg(log_lines[1]["argv"])
        entry_three_model = _model_arg(log_lines[2]["argv"])
        self.assertEqual(entry_two_model, VERTEX_MODEL)
        self.assertEqual(entry_three_model, MUSE_MODEL)
        self.assertNotEqual(entry_two_model, entry_three_model)


class TestHeaderCommentDeclaresStreamAndEnvironmentContract(unittest.TestCase):
    """AC-3: the script's header comment declares which stream carries a
    switch shape and which environment inputs the non-primary entries
    require. The stream-declaration check is specific (not a bare
    "stderr" substring match) because the header already mentions stderr
    for an unrelated reason (the CODEX_FALLBACK: marker line), which would
    let a weaker assertion pass without an actual declaration."""

    def test_header_declares_which_stream_carries_a_switch_shape(self):
        header = _normalize_whitespace(
            _header_comment_prose(SCRIPT_PATH.read_text(encoding="utf-8")).lower()
        )
        self.assertIn("a switch is recognized only from an attempt's stderr", header)
        self.assertIn("never from stdout", header)

    def test_header_declares_required_environment_inputs(self):
        header = _header_comment_block(SCRIPT_PATH.read_text(encoding="utf-8"))
        self.assertIn("LITELLM_API_KEY", header)
        self.assertIn("litellm.config.toml", header)


class TestFallbackChainEndToEnd(unittest.TestCase):
    """AC-4: usage-limit at entry 1 advances to entry 2; provider error at
    entry 2 advances to entry 3; entry 3 answers."""

    def test_usage_limit_then_provider_error_falls_through_to_third_entry(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error", 3: "success"}
        )

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 3\n")

        self.assertEqual([line["entry"] for line in log_lines], [1, 2, 3])
        self.assertIsNone(_model_arg(log_lines[0]["argv"]))
        self.assertEqual(_model_arg(log_lines[1]["argv"]), VERTEX_MODEL)
        self.assertEqual(_model_arg(log_lines[2]["argv"]), MUSE_MODEL)

    def test_exactly_one_fallback_line_names_the_answering_entry(self):
        proc, _ = _run_chain({1: "usage_limit", 2: "provider_error", 3: "success"})

        stderr_lines = [
            line for line in proc.stderr.splitlines() if line.startswith("CODEX_FALLBACK:")
        ]
        self.assertEqual(len(stderr_lines), 1, f"stderr was: {proc.stderr!r}")
        self.assertIn("3", stderr_lines[0])


class TestStdoutCleanlinessOnFallback(unittest.TestCase):
    """AC-4 edge case (Test Notes): stdout on the fallback path carries only
    the answering entry's output, never an earlier failed attempt's text."""

    def test_stdout_excludes_earlier_failed_attempts_text(self):
        proc, _ = _run_chain({1: "usage_limit", 2: "provider_error", 3: "success"})

        self.assertNotIn(USAGE_LIMIT_TEXT, proc.stdout)
        self.assertNotIn(PROVIDER_ERROR_TEXT, proc.stdout)
        self.assertEqual(proc.stdout, "STUB_ANSWER: ok from entry 3\n")


class TestSpoofedSwitchShapeInReplyNeverAdvances(unittest.TestCase):
    """AC-5 (NFR7): a switch shape present ONLY in the model-generated
    reply text (stdout) -- never the CLI's own diagnostic (stderr) -- must
    never advance the chain. Proves a reviewed repository or a model reply
    cannot force a provider switch."""

    def test_usage_limit_phrase_in_reply_text_does_not_advance_from_entry_one(self):
        proc, log_lines = _run_chain({1: "usage_limit_in_reply"})

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, USAGE_LIMIT_TEXT + "\n")
        self.assertEqual(len(log_lines), 1)
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)

    def test_provider_error_phrase_in_reply_text_does_not_advance_from_entry_two(self):
        proc, log_lines = _run_chain(
            {1: "usage_limit", 2: "provider_error_in_reply"}
        )

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, PROVIDER_ERROR_TEXT + "\n")
        self.assertEqual([line["entry"] for line in log_lines], [1, 2])
        self.assertNotIn("CODEX_FALLBACK", proc.stderr)


class TestFallbackPrerequisitesAbsent(unittest.TestCase):
    """AC-6: when a switch condition fires but the non-primary entry's
    environment prerequisites (LITELLM_API_KEY / ~/.codex/litellm.config.toml)
    are absent, no further invocation is attempted, the caller receives the
    failing entry's own exit code and output, and one stderr diagnostic
    states that the fallback entry was not configured."""

    def test_usage_limit_at_entry_one_does_not_advance_when_fallback_unconfigured(self):
        proc, log_lines = _run_chain({1: "usage_limit"}, fallback_configured=False)

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, USAGE_LIMIT_TEXT + "\n")
        self.assertEqual(len(log_lines), 1, f"expected no attempt beyond entry 1: {log_lines}")
        self.assertNotIn("CODEX_FALLBACK:", proc.stderr)

        unconfigured_lines = [
            line for line in proc.stderr.splitlines() if line.startswith("CODEX_FALLBACK_UNCONFIGURED:")
        ]
        self.assertEqual(len(unconfigured_lines), 1, f"stderr was: {proc.stderr!r}")
        self.assertIn("not configured", unconfigured_lines[0].lower())


class TestNonSwitchFailuresSurfaceUnchanged(unittest.TestCase):
    """AC-7: only entry-1-usage-limit and entry-2-provider-error are switch
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
    """The wrapper's own argument surface (mode / -C / --output-schema
    / prompt) does not change. The byte-for-byte wrapper-invocation-line pin
    lives in test_codex_reviewer_temp_file_isolation.py and is untouched by
    this task; this class covers the direct-run half of that guarantee."""

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
    """AC-8 (NFR4): none of the six batch resolution documents
    (IMPLEMENTATION.md C3) names a provider or describes usage-limit
    detection. Scoped to exactly that document set -- never
    repository-wide -- and the marker list matches the identifiers the
    script actually uses."""

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

    def test_marker_list_matches_identifiers_the_script_uses(self):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PROVIDER_MARKERS:
            self.assertIn(
                marker, script_text,
                f"{marker!r} is asserted absent from the docs but is not "
                "actually used by the script -- the marker list is stale",
            )

    def test_scan_catches_a_forged_provider_name_leak(self):
        forged = (
            f"The wrapper may retry through {VERTEX_MODEL} before giving up."
        )
        self.assertIn(VERTEX_MODEL, _find_leaks(forged))

    def test_scan_catches_a_forged_usage_limit_detection_leak(self):
        forged = "The wrapper checks the reply text for a usage limit phrase."
        self.assertIn("usage limit", _find_leaks(forged))

    def test_scan_catches_a_forged_provider_error_detection_leak(self):
        forged = "A provider error in the reply text triggers the next entry."
        self.assertIn("provider error", _find_leaks(forged))


class TestHermeticAndStdlibOnly(unittest.TestCase):
    """AC-9 (NFR9): this module contacts no network and no real provider
    (every test above runs a stubbed `codex` placed first on PATH, under an
    isolated HOME) and imports only the Python standard library."""

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
