"""Tests for task0006: create-spec side worker contracts (analyst /
spec-writer).

Covers task0006 Acceptance Criteria (feature-docs/agent-separation/tasks/
task0006.md):

- AC-1: analyst-contract.md exists, references the common envelope by path,
  and documents analysis_mode, analysis_scope, task_description and
  known_feature_name.
- AC-2: analyst-contract.md documents the analysis_snapshot fields and the
  full-mode completed payload from design-input.md 5.4.1.
- AC-3: analyst-contract.md documents the design_system_detection mode with
  its payload exclusivity, its restricted status set and its digest_inputs,
  and states that the analyst detects candidates without deciding kind.
- AC-4: spec-writer-contract.md exists, references the common envelope by
  path, and documents all six write_policy actions with their expect_digest
  requirement and worker behaviour.
- AC-5: spec-writer-contract.md states the protection split between
  targets and allowed_write_roots, including that an existing file not
  enumerated in targets may not be modified even under an allowed root.
- AC-6: spec-writer-contract.md documents the completed payload and all
  four post-conditions, including the prohibition on inventing
  requirements.
- AC-7: neither contract restates the common envelope's fields or the
  question packet schema; both reference them by path.

These deliverables are specification documents (Markdown contracts), so
verification is by structural/textual assertion against the rendered
documents, deriving expected vocabulary from design-input.md itself so the
assertions cannot silently drift from the design (task0006.md Test Notes).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
FEATURE_DOCS = (
    Path(__file__).resolve().parent.parent
    / "feature-docs"
    / "agent-separation"
)

ANALYST_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "analyst-contract.md"
SPEC_WRITER_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "spec-writer-contract.md"
DESIGN_INPUT_PATH = FEATURE_DOCS / "design-input.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_analysis_snapshot_fields(design_text):
    """Pull the backtick-quoted field names out of the design-input.md 5.4.1
    sentence describing payload.analysis_snapshot, so the expected
    vocabulary is derived from the design rather than hand-copied."""
    match = re.search(
        r"payload\.analysis_snapshot`:\s*(.+)", design_text
    )
    if not match:
        raise AssertionError(
            "could not locate the analysis_snapshot description line in "
            "design-input.md"
        )
    line = match.group(1)
    tokens = re.findall(r"`([a-z_][a-z0-9_]*)`", line)
    # Exclude the anchor token itself if regex machinery ever picks it up.
    return [t for t in tokens if t not in ("needs_user_input",)]


def _extract_write_policy_actions(design_text):
    """Parse the action/expect_digest/behaviour table in design-input.md
    5.4.2 and return the list of action names (first column)."""
    header_idx = design_text.index("| action | 意味 |")
    table_text = design_text[header_idx:]
    lines = table_text.splitlines()
    actions = []
    for line in lines[1:]:
        if not line.startswith("|"):
            break
        if "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        action = cells[0].strip("`")
        if action:
            actions.append(action)
    return actions


class TestFilesExist(unittest.TestCase):
    def test_analyst_contract_exists(self):
        self.assertTrue(
            ANALYST_CONTRACT_PATH.is_file(),
            f"expected {ANALYST_CONTRACT_PATH} to exist",
        )

    def test_spec_writer_contract_exists(self):
        self.assertTrue(
            SPEC_WRITER_CONTRACT_PATH.is_file(),
            f"expected {SPEC_WRITER_CONTRACT_PATH} to exist",
        )


class TestAnalystContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ANALYST_CONTRACT_PATH)
        cls.design_text = _read(DESIGN_INPUT_PATH)

    # AC-1
    def test_references_common_envelope_by_path(self):
        self.assertIn("references/contracts/worker-envelope.md", self.text)

    def test_documents_additional_input_fields(self):
        for field in (
            "analysis_mode",
            "analysis_scope",
            "task_description",
            "known_feature_name",
        ):
            self.assertIn(field, self.text)

    # AC-2
    def test_documents_analysis_snapshot_fields(self):
        expected_fields = _extract_analysis_snapshot_fields(self.design_text)
        # Sanity: the design line must actually yield a non-trivial set,
        # otherwise the parser itself is broken and the assertion below
        # would vacuously pass.
        self.assertGreaterEqual(len(expected_fields), 10)
        for field in expected_fields:
            self.assertIn(
                field,
                self.text,
                f"analysis_snapshot field {field!r} missing from analyst-contract.md",
            )

    def test_documents_full_mode_completed_payload(self):
        for field in (
            "resolved_requirements",
            "feature_name",
            "business_objectives",
            "functional_requirements",
            "non_functional_requirements",
            "acceptance_criteria",
            "test_scenarios",
            "assumptions",
            "design_step",
            "project_detection",
            "design_system_candidates",
        ):
            self.assertIn(field, self.text)

    # AC-3
    def test_documents_design_system_detection_mode_exclusivity(self):
        self.assertIn("design_system_detection", self.text)
        # resolved_requirements / project_detection must be stated as
        # prohibited in this mode, not merely mentioned once for full mode.
        self.assertIn("prohibited", self.text.lower())

    def test_documents_restricted_status_set(self):
        for status in ("completed", "blocked", "failed"):
            self.assertIn(status, self.text)
        # The restriction excludes needs_user_input / question packets in
        # this mode.
        self.assertIn("question_packet", self.text)

    def test_documents_digest_inputs_for_both_modes(self):
        self.assertIn("digest_inputs", self.text)

    def test_states_analyst_detects_without_deciding_kind(self):
        lowered = self.text.lower()
        self.assertIn("does not decide", lowered)
        self.assertIn("kind", lowered)


class TestSpecWriterContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_WRITER_CONTRACT_PATH)
        cls.design_text = _read(DESIGN_INPUT_PATH)

    # AC-4
    def test_references_common_envelope_by_path(self):
        self.assertIn("references/contracts/worker-envelope.md", self.text)

    def test_documents_all_six_write_policy_actions(self):
        expected_actions = _extract_write_policy_actions(self.design_text)
        self.assertEqual(
            set(expected_actions),
            {
                "create",
                "replace_own",
                "replace_authorized",
                "preserve",
                "extend_only",
                "regenerate",
            },
        )
        for action in expected_actions:
            self.assertIn(
                action,
                self.text,
                f"write_policy action {action!r} missing from spec-writer-contract.md",
            )

    def test_documents_expect_digest_requirement(self):
        self.assertIn("expect_digest", self.text)
        # replace_authorized still requires re-verification, per design.
        self.assertIn("replace_authorized", self.text)
        self.assertIn("regenerate", self.text)
        self.assertIn("source", self.text)

    # AC-5
    def test_documents_targets_vs_allowed_write_roots_split(self):
        self.assertIn("allowed_write_roots", self.text)
        self.assertIn("targets", self.text)
        self.assertIn(
            "may not be modified even",
            self.text,
            "expected an explicit statement that an unenumerated existing "
            "file cannot be modified even under an allowed_write_roots "
            "directory",
        )

    # AC-6
    def test_documents_completed_payload(self):
        for field in ("spec_index", "assumptions_written", "test_scenarios"):
            self.assertIn(field, self.text)

    def test_documents_all_four_postconditions(self):
        self.assertIn(r"^(FR|NFR)[1-9][0-9]*$", self.text)
        self.assertIn("spec_index.requirements", self.text)
        self.assertIn("tbd_reason", self.text)
        lowered = self.text.lower()
        self.assertIn("invent", lowered)
        self.assertIn("analyst", lowered)


class TestNoRestatement(unittest.TestCase):
    """AC-7: neither contract restates the common envelope's own generic
    field list. These field names belong exclusively to the envelope's
    dispatch bookkeeping and have no worker-specific meaning of their own,
    so their presence would indicate the envelope table was copied in
    rather than referenced (NFR6)."""

    ENVELOPE_ONLY_FIELDS = (
        "integration_worktree",
        "plugin_root",
        "prior_packets",
        "feature_dir",
    )

    def test_analyst_contract_does_not_restate_envelope_fields(self):
        text = _read(ANALYST_CONTRACT_PATH)
        for field in self.ENVELOPE_ONLY_FIELDS:
            self.assertNotIn(field, text)

    def test_spec_writer_contract_does_not_restate_envelope_fields(self):
        text = _read(SPEC_WRITER_CONTRACT_PATH)
        for field in self.ENVELOPE_ONLY_FIELDS:
            self.assertNotIn(field, text)


if __name__ == "__main__":
    unittest.main()
