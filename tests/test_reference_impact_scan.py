"""Tests for task0008: referenced-side impact scan in the analyst contract
and prompt.

Covers task0008 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0008.md):

- AC-1: worker-envelope.md's `resolved_input_paths` table lists the
  `reference_scan_targets` category with the same requiredness and
  may-be-empty semantics as its siblings.
- AC-2: analyst-contract.md documents the
  `analysis_scope.inspect_reference_impact` request flag and states that it
  is meaningful only in `analysis_mode: full`.
- AC-3: analyst-contract.md documents the `reference_impact` result field
  in both the interim snapshot and the full-mode completed payload, and
  states that affected test files are included.
- AC-4: analyst-contract.md states that the orchestrator resolves the scan
  targets before dispatch and that the analyst performs no filesystem
  discovery of its own.
- AC-5: the full-mode `digest_inputs` row includes the resolved
  reference-scan paths, and the design-system-detection mode's payload
  exclusivity is unchanged.
- AC-6: requirements-analyst.md states the investigation step and what it
  reports, consistent with the contract's field names.
- AC-7: the contract does not name any of the envelope-only bookkeeping
  fields it is forbidden to restate, and the full suite passes.

These deliverables are specification documents (Markdown contracts), so
verification is by structural/textual assertion against the rendered
documents (task0008.md Test Notes). Assertions cover only this task's three
documents (C4): `worker-envelope.md`, `analyst-contract.md`,
`requirements-analyst.md`.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"

ENVELOPE_DOC_PATH = PLUGIN_ROOT / "references" / "contracts" / "worker-envelope.md"
ANALYST_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "analyst-contract.md"
AGENT_PATH = PLUGIN_ROOT / "agents" / "requirements-analyst.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _has_exact_token(text, token):
    """True iff `token` occurs as an exact inline-code span, not merely as a
    substring of a longer identifier or of surrounding prose."""
    pattern = r"`" + re.escape(token) + r"`"
    return re.search(pattern, text) is not None


def _extract_section(text, start_heading, end_heading):
    assert start_heading in text, f"missing heading {start_heading!r}"
    start = text.index(start_heading)
    assert end_heading in text[start:], (
        f"missing heading {end_heading!r} after {start_heading!r}"
    )
    end = text.index(end_heading, start)
    return text[start:end]


def _resolved_input_paths_category_rows(text):
    """Parse every `resolved_input_paths`.`<category>` row from the
    envelope's Input fields table, returning
    {category: (meaning_cell, mandatory_cell)}."""
    rows = re.findall(
        r"^\|\s*`resolved_input_paths`\.`([a-z0-9_]+)`\s*\|([^|]*)\|([^|]*)\|\s*$",
        text,
        re.MULTILINE,
    )
    return {
        name: (meaning.strip(), mandatory.strip()) for name, meaning, mandatory in rows
    }


def _first_yaml_block(text):
    match = re.search(r"```yaml\n(.*?)```", text, re.DOTALL)
    assert match, "expected a yaml code block"
    return match.group(1)


def _analysis_scope_keys(yaml_block):
    """Return the mapping keys nested under `analysis_scope:` in a yaml
    block (2-space indented children only)."""
    keys = []
    in_scope = False
    for line in yaml_block.splitlines():
        if re.match(r"^analysis_scope:", line):
            in_scope = True
            continue
        if in_scope:
            match = re.match(r"^\s{2}([a-z_]+):", line)
            if match:
                keys.append(match.group(1))
            elif line.strip() and not line.startswith(" "):
                break
    return keys


def _digest_inputs_row(text, mode):
    """Return the `digest_inputs` cell of the mode-table row for `mode`.
    Raises AssertionError (never silently returns nothing) when the row is
    absent, so a caller's non-vacuity checks have something to fail on."""
    header_idx = text.index("| mode | `digest_inputs`")
    table_text = text[header_idx:]
    lines = table_text.splitlines()
    for line in lines[1:]:
        if not line.startswith("|"):
            break
        if "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0].strip("`") == mode:
            return cells[1]
    raise AssertionError(f"digest_inputs row for mode {mode!r} not found")


class TestExtractionHelpersSelfCheck(unittest.TestCase):
    """Sanity that the parsing helpers above actually derive non-trivial
    values from the shipped documents, rather than vacuously returning
    empty results (Test Notes: non-vacuity)."""

    def test_resolved_input_paths_rows_helper_is_non_vacuous(self):
        rows = _resolved_input_paths_category_rows(_read(ENVELOPE_DOC_PATH))
        self.assertGreaterEqual(len(rows), 5)
        self.assertIn("e2e", rows)

    def test_analysis_scope_keys_helper_is_non_vacuous(self):
        block = _first_yaml_block(_read(ANALYST_CONTRACT_PATH))
        keys = _analysis_scope_keys(block)
        self.assertGreaterEqual(len(keys), 5)
        self.assertIn("inspect_license", keys)

    def test_digest_inputs_row_helper_is_non_vacuous(self):
        text = _read(ANALYST_CONTRACT_PATH)
        full_row = _digest_inputs_row(text, "full")
        detection_row = _digest_inputs_row(text, "design_system_detection")
        self.assertIn("CLAUDE.md", full_row)
        self.assertIn("design-system candidate", detection_row)


class TestResolvedInputPathsRowsRejectMissingCategory(unittest.TestCase):
    """Negative proof for `_resolved_input_paths_category_rows` against a
    synthetic sample that lacks the new category."""

    def test_rejects_synthetic_table_without_new_row(self):
        synthetic = (
            "| `resolved_input_paths`.`e2e` | Resolved E2E input paths | "
            "Yes (may be empty) |\n"
        )
        rows = _resolved_input_paths_category_rows(synthetic)
        self.assertNotIn("reference_scan_targets", rows)
        self.assertIn("e2e", rows)


class TestAnalysisScopeKeysRejectMissingFlag(unittest.TestCase):
    """Negative proof for `_analysis_scope_keys` against a synthetic sample
    that lacks the new flag."""

    def test_rejects_synthetic_block_without_new_flag(self):
        synthetic = "analysis_scope:\n  inspect_license: true\n"
        keys = _analysis_scope_keys(synthetic)
        self.assertNotIn("inspect_reference_impact", keys)
        self.assertIn("inspect_license", keys)


class TestDigestInputsRowRejectsMissingMode(unittest.TestCase):
    """Negative proof for `_digest_inputs_row` against a synthetic sample
    missing the mode row being looked up."""

    def test_rejects_synthetic_table_missing_the_mode(self):
        synthetic = (
            "| mode | `digest_inputs` (files) | `value_inputs` |\n"
            "|---|---|---|\n"
            "| `full` | `CLAUDE.md` | `task_description` |\n"
        )
        with self.assertRaises(AssertionError):
            _digest_inputs_row(synthetic, "design_system_detection")


class TestReferenceScanTargetsCategory(unittest.TestCase):
    """AC-1: worker-envelope.md's `resolved_input_paths` table lists
    `reference_scan_targets` with the same requiredness/may-be-empty
    semantics as its siblings."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_row_present(self):
        rows = _resolved_input_paths_category_rows(self.text)
        self.assertIn("reference_scan_targets", rows)

    def test_matches_sibling_requiredness_and_may_be_empty_semantics(self):
        rows = _resolved_input_paths_category_rows(self.text)
        sibling_mandatory = rows["e2e"][1]
        self.assertEqual(sibling_mandatory, "Yes (may be empty)")
        self.assertEqual(rows["reference_scan_targets"][1], sibling_mandatory)


class TestInspectReferenceImpactFlag(unittest.TestCase):
    """AC-2: the analyst contract documents the
    `analysis_scope.inspect_reference_impact` request flag and states it is
    meaningful only in `analysis_mode: full`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ANALYST_CONTRACT_PATH)

    def test_flag_listed_alongside_existing_inspection_categories(self):
        block = _first_yaml_block(self.text)
        keys = _analysis_scope_keys(block)
        self.assertIn("inspect_reference_impact", keys)

    def test_flag_documented_as_exact_token(self):
        # task0008.md Design B1: the contract states the flag under its full
        # dotted request path, matching the design's own literal phrasing.
        self.assertTrue(
            _has_exact_token(self.text, "analysis_scope.inspect_reference_impact")
        )

    def test_states_meaningful_only_in_full_mode(self):
        self.assertIn(
            "analysis_scope.inspect_reference_impact",
            self.text,
        )
        idx = self.text.index("analysis_scope.inspect_reference_impact")
        window = self.text[idx : idx + 400]
        self.assertIn("analysis_mode: full", window)


class TestReferenceImpactResultField(unittest.TestCase):
    """AC-3: `reference_impact` documented in both the interim snapshot and
    the full-mode completed payload; affected test files stated as
    included."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ANALYST_CONTRACT_PATH)

    def test_present_in_analysis_snapshot_section(self):
        section = _extract_section(
            self.text,
            "## `analysis_snapshot` (returned with `status: needs_user_input`)",
            "## `completed` payload (`analysis_mode: full`)",
        )
        self.assertTrue(_has_exact_token(section, "reference_impact"))

    def test_present_in_completed_payload_section(self):
        section = _extract_section(
            self.text,
            "## `completed` payload (`analysis_mode: full`)",
            "## `analysis_mode: design_system_detection` (lightweight, backfill-only)",
        )
        self.assertTrue(_has_exact_token(section, "reference_impact"))

    def test_states_affected_test_files_are_included(self):
        self.assertIn("reference_impact", self.text)
        lowered = self.text.lower()
        self.assertIn("test file", lowered)


class TestResolutionPointStatement(unittest.TestCase):
    """AC-4: the orchestrator resolves the scan targets before dispatch;
    the analyst performs no filesystem discovery of its own (retained)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ANALYST_CONTRACT_PATH)

    def test_glob_derived_category_list_covers_reference_scan(self):
        idx = self.text.index("resolves every glob-derived category")
        window = self.text[idx : idx + 800]
        self.assertIn("reference", window.lower())

    def test_retains_no_own_filesystem_discovery_statement(self):
        idx = self.text.index("resolves every glob-derived category")
        window = self.text[idx : idx + 800]
        self.assertIn("it never performs its own filesystem discovery", window)


class TestDigestInputsReferenceScanPaths(unittest.TestCase):
    """AC-5: the full-mode `digest_inputs` row includes the resolved
    reference-scan paths; the design-system-detection mode's payload
    exclusivity is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ANALYST_CONTRACT_PATH)

    def test_full_mode_row_includes_reference_scan_paths(self):
        row = _digest_inputs_row(self.text, "full")
        self.assertIn("reference-scan paths", row.lower())

    def test_design_system_detection_row_unaffected(self):
        row = _digest_inputs_row(self.text, "design_system_detection")
        self.assertNotIn("reference", row.lower())

    def test_reference_impact_not_a_detection_mode_payload_key(self):
        # Edge case (task0008.md Test Notes): the exclusivity rule is easy
        # to break by describing the field too generally.
        section = _extract_section(
            self.text,
            "## `analysis_mode: design_system_detection` (lightweight, backfill-only)",
            "## `digest_inputs`",
        )
        self.assertNotIn("reference_impact", section)

    def test_detection_mode_payload_exclusivity_statement_unchanged(self):
        section = _extract_section(
            self.text,
            "## `analysis_mode: design_system_detection` (lightweight, backfill-only)",
            "## `digest_inputs`",
        )
        self.assertIn("resolved_requirements", section)
        self.assertIn("project_detection", section)
        self.assertIn("prohibited", section.lower())


class TestAgentPromptInvestigationStep(unittest.TestCase):
    """AC-6: requirements-analyst.md states the investigation step and what
    it reports, consistent with the contract's field names."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(AGENT_PATH)

    def test_step_placed_alongside_other_inspection_categories(self):
        section = _extract_section(
            self.text,
            "### `analysis_mode: full`",
            "### `analysis_mode: design_system_detection`",
        )
        self.assertTrue(_has_exact_token(section, "inspect_reference_impact"))
        self.assertTrue(_has_exact_token(section, "inspect_license"))

    def test_mentions_deletion_or_renaming(self):
        lowered = self.text.lower()
        self.assertIn("delet", lowered)
        self.assertIn("renam", lowered)

    def test_reports_using_the_contract_field_name(self):
        idx = self.text.index("inspect_reference_impact")
        window = self.text[idx : idx + 600]
        self.assertTrue(_has_exact_token(window, "reference_impact"))

    def test_reinforces_reading_only_envelope_supplied_paths(self):
        idx = self.text.index("inspect_reference_impact")
        window = self.text[idx : idx + 600]
        self.assertIn("resolved_input_paths.reference_scan_targets", window)


class TestNoEnvelopeOnlyFieldRestatement(unittest.TestCase):
    """AC-7: the contract does not name any of the envelope-only bookkeeping
    fields it is forbidden to restate (NFR8)."""

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


if __name__ == "__main__":
    unittest.main()
