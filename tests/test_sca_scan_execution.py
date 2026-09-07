"""Tests for task0009 (review-sca-axis): scan execution outcomes and the
partial-coverage result contract.

Covers task0009 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0009.md):

- AC-1 (TS-28): a job whose process exits zero with empty stdout yields
  `not_completed` with a machine-stable reason and contributes no findings.
- AC-2 (TS-28): a payload that is the npm missing-lockfile error envelope,
  and an exit status outside the tool's documented set, each yield
  `not_completed` with their own distinct reason -- distinguishable from
  each other and from the tool-absent reason.
- AC-3 (TS-28): a documented advisory-found non-zero exit accompanied by
  that tool's success payload yields `completed`, and its findings reach
  the emitted result.
- AC-4 (TS-29, TS-2): with two ecosystems selected and one not completing,
  the emitted object has `skipped: true`, a `skip_reason` naming the
  non-completing ecosystem's reason, and still carries the completed
  ecosystem's findings; the object validates against
  `review-output-schema.json`. With both completing, `skipped` is `false`
  and `skip_reason` is `null`.
- AC-5 (TS-29, TS-19): `skip_reason`'s combined form is deterministic --
  the same set of per-ecosystem reasons produces the identical string
  independently of registry/selection order.
- AC-6 (TS-29, TS-8, TS-15): `review-phase.md`'s axis-2 run paragraph
  states the partial-coverage case additively; the pre-existing pins in
  tests/test_sca_axis_review_phase_r0_r3.py are exercised by running the
  full suite alongside this module (Test Notes), not re-asserted here.
- AC-7/AC-8: the plugin version bump and the full suite / invariants
  checker exit 0 -- not unit-testable from inside this module (a suite
  cannot assert its own full-suite outcome, and the version bump is
  covered by tests/test_sca_axis_skill_and_version.py's pattern); verified
  by actually running both commands, recorded in the implementer report.

Per Test Notes: no real scanner runs. Each execution case is an executable
stub placed on a temporary PATH that prints the scripted stdout and exits
with the scripted status; the npm error-envelope case and the
advisory-found case differ only in payload, which is what makes "status and
shape together" testable. This module's own imports are standard-library
only (NFR7); the script under test is loaded by file path
(scan-dependencies.py is not a package), following
tests/test_sca_scan_normalization.py's convention. Schema conformance is
checked by a structural assertion against the schema document, not a
third-party validator.
"""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "review-output-schema.json"
REVIEW_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "review-phase.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_dependencies_execution", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_module()


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_conforms_to_schema(testcase, obj, schema):
    """Structural assertion against review-output-schema.json -- not a
    third-party validator (Test Notes), matching
    tests/test_sca_scan_normalization.py's convention."""
    root_props = schema["properties"]
    for key in schema["required"]:
        testcase.assertIn(key, obj, f"missing required root key {key!r}")
    if schema.get("additionalProperties") is False:
        extra = set(obj) - set(root_props)
        testcase.assertFalse(extra, f"unexpected root keys: {extra}")
    testcase.assertIn(obj["source"], root_props["source"]["enum"])
    testcase.assertIsInstance(obj["findings"], list)
    testcase.assertIsInstance(obj["summary"], str)
    testcase.assertIsInstance(obj["skipped"], bool)
    if obj["skipped"]:
        testcase.assertIsInstance(obj["skip_reason"], str)
    else:
        testcase.assertIsNone(obj["skip_reason"])

    finding_schema = root_props["findings"]["items"]
    finding_props = finding_schema["properties"]
    for finding in obj["findings"]:
        for key in finding_schema["required"]:
            testcase.assertIn(key, finding, f"finding missing required key {key!r}")
        if finding_schema.get("additionalProperties") is False:
            extra = set(finding) - set(finding_props)
            testcase.assertFalse(extra, f"unexpected finding keys: {extra}")
        testcase.assertIn(finding["category"], finding_props["category"]["enum"])
        testcase.assertIn(finding["severity"], finding_props["severity"]["enum"])


def _write_stub(bin_dir, name, stdout_text, exit_code=0):
    """Writes an executable named `name` into `bin_dir` that prints
    `stdout_text` verbatim to stdout and exits with `exit_code` -- a
    stand-in for the real SCA tool (Test Notes: "an executable stub placed
    on a temporary PATH that prints the scripted stdout and exits with the
    scripted status"). The shebang uses sys.executable's absolute path
    rather than `/usr/bin/env python3` -- these tests deliberately restrict
    PATH to `bin_dir` alone."""
    script = bin_dir / name
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.stdout.write({stdout_text!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


NPM_SUCCESS_FIXTURE = {
    "vulnerabilities": {
        "lodash": {
            "name": "lodash",
            "severity": "critical",
            "isDirect": True,
            "range": "<4.17.21",
            "fixAvailable": {"name": "lodash", "version": "4.17.21"},
            "via": [
                {
                    "source": 1096742,
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

# npm's documented missing-lockfile error envelope (task plan Design's
# "concrete case"): a well-formed JSON object reporting a TOOL-side
# failure, never a scan result.
NPM_ERROR_ENVELOPE = {
    "error": {
        "code": "ENOLOCK",
        "summary": "This command requires an existing lockfile.",
        "detail": "Try creating one first with: npm i --package-lock-only",
    }
}

CARGO_SUCCESS_FIXTURE = {
    "vulnerabilities": {
        "found": True,
        "list": [
            {
                "advisory": {
                    "id": "RUSTSEC-2023-0001",
                    "title": "Integer overflow in foo",
                    "description": "A crafted input can cause an integer overflow.",
                },
                "package": {"name": "foo", "version": "1.0.0"},
                "versions": {"patched": [">=1.0.1"]},
                "severity": "high",
                "is_direct": True,
            }
        ],
    }
}


def _run_scan_with_path(bin_dir, project_root, changed_files, registry_path=None):
    with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
        return SCAN.run_scan(
            project_root, changed_files, registry_path or SCAN.DEFAULT_REGISTRY_PATH
        )


# ---------------------------------------------------------------------------
# AC-1 (TS-28): exit zero + empty stdout => not_completed, no findings.
# ---------------------------------------------------------------------------


class TestEmptyStdoutIsNotCompleted(unittest.TestCase):
    def test_judge_scan_outcome_direct(self):
        outcome, reason = SCAN.judge_scan_outcome("npm", 0, "")
        self.assertEqual(outcome, SCAN.OUTCOME_NOT_COMPLETED)
        self.assertIsInstance(reason, str)

    def test_whitespace_only_stdout_is_also_not_completed(self):
        outcome, reason = SCAN.judge_scan_outcome("npm", 0, "   \n  ")
        self.assertEqual(outcome, SCAN.OUTCOME_NOT_COMPLETED)
        self.assertIsInstance(reason, str)

    def test_run_scan_end_to_end_yields_skipped_with_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", "", exit_code=0)
            result = _run_scan_with_path(bin_dir, project_root, ["package.json"])
        self.assertTrue(result["skipped"])
        self.assertIsInstance(result["skip_reason"], str)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["source"], "tool")


# ---------------------------------------------------------------------------
# AC-2 (TS-28): npm missing-lockfile error envelope, and an undocumented
# exit status, each yield their own distinct not_completed reason.
# ---------------------------------------------------------------------------


class TestErrorEnvelopeAndUndocumentedExitAreDistinctReasons(unittest.TestCase):
    def test_error_envelope_is_not_completed_regardless_of_documented_exit(self):
        # exit=1 is npm's OWN documented "found something" status -- the
        # payload shape is what disqualifies this case, not the exit code.
        outcome, reason = SCAN.judge_scan_outcome("npm", 1, json.dumps(NPM_ERROR_ENVELOPE))
        self.assertEqual(outcome, SCAN.OUTCOME_NOT_COMPLETED)
        self.assertEqual(reason, "npm_error_envelope")

    def test_undocumented_exit_status_is_not_completed_even_with_valid_payload(self):
        # The payload is a genuinely valid success structure; only the
        # exit code (2, outside npm's documented {0, 1}) disqualifies it.
        outcome, reason = SCAN.judge_scan_outcome("npm", 2, json.dumps(NPM_SUCCESS_FIXTURE))
        self.assertEqual(outcome, SCAN.OUTCOME_NOT_COMPLETED)
        self.assertEqual(reason, "npm_undocumented_exit_status")

    def test_the_two_reasons_and_the_tool_absent_reason_are_all_distinct(self):
        _, error_envelope_reason = SCAN.judge_scan_outcome("npm", 1, json.dumps(NPM_ERROR_ENVELOPE))
        _, undocumented_reason = SCAN.judge_scan_outcome("npm", 2, json.dumps(NPM_SUCCESS_FIXTURE))
        tool_absent_reason = "npm_tool_not_found"  # FR3's existing reason
        self.assertNotEqual(error_envelope_reason, undocumented_reason)
        self.assertNotEqual(error_envelope_reason, tool_absent_reason)
        self.assertNotEqual(undocumented_reason, tool_absent_reason)

    def test_error_envelope_end_to_end_via_run_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", json.dumps(NPM_ERROR_ENVELOPE), exit_code=1)
            result = _run_scan_with_path(bin_dir, project_root, ["package.json"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["findings"], [])
        self.assertIn("npm", result["skip_reason"])

    def test_undocumented_exit_end_to_end_via_run_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", json.dumps(NPM_SUCCESS_FIXTURE), exit_code=2)
            result = _run_scan_with_path(bin_dir, project_root, ["package.json"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["findings"], [])


# ---------------------------------------------------------------------------
# AC-3 (TS-28): documented advisory-found exit + success payload =>
# completed, findings reach the emitted result.
# ---------------------------------------------------------------------------


class TestDocumentedAdvisoryFoundExitIsCompleted(unittest.TestCase):
    def test_judge_scan_outcome_direct(self):
        outcome, data = SCAN.judge_scan_outcome("npm", 1, json.dumps(NPM_SUCCESS_FIXTURE))
        self.assertEqual(outcome, SCAN.OUTCOME_COMPLETED)
        self.assertEqual(data, NPM_SUCCESS_FIXTURE)

    def test_run_scan_end_to_end_findings_reach_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", json.dumps(NPM_SUCCESS_FIXTURE), exit_code=1)
            result = _run_scan_with_path(bin_dir, project_root, ["package.json"])
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["category"], "vulnerability")


# ---------------------------------------------------------------------------
# AC-4 (TS-29, TS-2): partial coverage across two selected ecosystems.
# ---------------------------------------------------------------------------


class TestPartialCoverageAcrossTwoEcosystems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()

    def test_one_not_completing_yields_skipped_true_with_completed_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", json.dumps(NPM_SUCCESS_FIXTURE), exit_code=0)
            # cargo is never placed on PATH -> tool_not_found for cargo.
            result = _run_scan_with_path(bin_dir, project_root, ["package.json", "Cargo.toml"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertTrue(result["skipped"])
        self.assertIn("cargo", result["skip_reason"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["findings"][0]["title"].startswith("lodash"))

    def test_both_completing_yields_skipped_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", json.dumps(NPM_SUCCESS_FIXTURE), exit_code=0)
            _write_stub(bin_dir, "cargo", json.dumps(CARGO_SUCCESS_FIXTURE), exit_code=0)
            result = _run_scan_with_path(bin_dir, project_root, ["package.json", "Cargo.toml"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(len(result["findings"]), 2)


# ---------------------------------------------------------------------------
# AC-5 (TS-29, TS-19): skip_reason's combined form is deterministic --
# independent of registry/ecosystem order.
# ---------------------------------------------------------------------------


class TestCombinedSkipReasonIsDeterministic(unittest.TestCase):
    """Determinism specifically in the PARTIAL-coverage case (one ecosystem
    completes, two do not) -- not the all-skipped case, whose combined
    reason was already sorted before this task (tdd-testing discipline: a
    property that already held pre-implementation proves nothing new).
    Here `skipped: true` only exists at all once the completing ecosystem
    no longer forces `skipped: false` (task plan Design), so this test
    depends on that behavior AND on the combination being order-
    independent."""

    NPM_ENTRY = (
        "  - ecosystem: npm\n"
        "    manifests: [package.json]\n"
        "    executable: npm\n"
        "    args: [audit, --json]\n"
        "    severity_map: {critical: critical, high: high}\n"
        "    threshold: {direct_only: true, min_severity: high}\n"
    )
    CARGO_ENTRY = (
        "  - ecosystem: cargo\n"
        "    manifests: [Cargo.toml]\n"
        "    executable: cargo\n"
        "    args: [audit, --json]\n"
        "    severity_map: {critical: critical, high: high}\n"
        "    threshold: {direct_only: true, min_severity: high}\n"
    )
    PIP_ENTRY = (
        "  - ecosystem: pip\n"
        "    manifests: [requirements.txt]\n"
        "    executable: pip-audit\n"
        "    args: [--format, json]\n"
        "    severity_map: {critical: critical, high: high}\n"
        "    threshold: {direct_only: true, min_severity: high}\n"
    )

    def _run_with_order(self, tmp, entries):
        registry_path = Path(tmp) / "registry.yaml"
        registry_path.write_text(
            "version: 1\necosystems:\n" + "".join(entries),
            encoding="utf-8",
        )
        project_root = Path(tmp) / "project"
        project_root.mkdir(exist_ok=True)
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir(exist_ok=True)
        # Only npm resolves on PATH -- cargo and pip-audit both contribute
        # a not_completed (tool_not_found) reason.
        _write_stub(bin_dir, "npm", json.dumps(NPM_SUCCESS_FIXTURE), exit_code=0)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
            return SCAN.run_scan(
                project_root,
                ["package.json", "Cargo.toml", "requirements.txt"],
                registry_path,
            )

    def test_partial_coverage_combined_reason_is_order_independent(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            r1 = self._run_with_order(tmp1, [self.NPM_ENTRY, self.CARGO_ENTRY, self.PIP_ENTRY])
            r2 = self._run_with_order(tmp2, [self.PIP_ENTRY, self.CARGO_ENTRY, self.NPM_ENTRY])
        self.assertTrue(r1["skipped"])
        self.assertTrue(r2["skipped"])
        self.assertEqual(r1["skip_reason"], r2["skip_reason"])
        self.assertIn("+", r1["skip_reason"])
        self.assertEqual(len(r1["findings"]), 1)
        self.assertEqual(len(r2["findings"]), 1)


# ---------------------------------------------------------------------------
# AC-6 (TS-29, TS-8, TS-15): review-phase.md's axis-2 run paragraph states
# the partial-coverage case additively.
# ---------------------------------------------------------------------------


class TestReviewPhasePartialCoverageStatement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REVIEW_PHASE_PATH.read_text(encoding="utf-8")
        start = cls.text.index("## Phase R2: Fan-out")
        end = cls.text.index("## Phase R2b: Cross-model fallback")
        cls.r2_section = cls.text[start:end]
        cls.norm = re.sub(r"\s+", " ", cls.r2_section)

    def test_r2_axis_2_section_states_partial_coverage(self):
        self.assertIn("partial coverage", self.norm)

    def test_states_combined_reason_on_the_run_row(self):
        self.assertIn("skip_reason", self.norm)
        self.assertIn("combined", self.norm)

    def test_states_findings_still_enter_the_evaluator_inputs(self):
        self.assertIn("evaluator", self.norm.lower())
        self.assertIn("findings", self.norm)

    def test_existing_ordinary_skip_pin_still_present(self):
        # This task's edit must not reflow or reword the pre-existing
        # sentence several other test modules pin (task plan Design:
        # "the edit is additive").
        self.assertIn("recorded exactly as this", self.norm)
        self.assertIn("ordinary skip", self.norm)
        self.assertIn("never as a retryable chain-walk `skip_reason`", self.norm)


if __name__ == "__main__":
    unittest.main()
