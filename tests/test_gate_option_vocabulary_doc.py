"""Tests for task0002: em-workflow/references/gate-option-vocabulary.md and
the two pointer additions at its referrer sites.

Covers task0002 Acceptance Criteria
(feature-docs/batch-policy-option-id-consistency/tasks/task0002.md):

- AC-1: the document exists, states the correspondence rule, names the
  policy file as the authoritative side, and names the protocol-error abort
  as the failure mode the rule prevents.
- AC-2: the document specifies the canonical declaration format completely
  (heading, column order, one row per option, backtick-quoted identifiers,
  prose meaning) and states why the format does not reuse the
  `## Gate identifiers` heading the frozen validator parses.
- AC-3: the document carries the exemption registry as a three-column
  table, states it is the only source of exemptions and that an absent
  registry means zero exemptions, and holds zero rows -- said so in words.
- AC-4: a hand-rolled registry validator (test-only, mirroring the
  restricted-subset parsing convention in tests/test_batch_policies.py)
  fails against synthetic exemption rows missing a reason, missing a
  compensating guarantee, or naming a gate that is not an `action: select`
  entry of batch-policies.yaml -- proven against synthetic documents, not
  only asserted about the current (empty) registry.
- AC-5: batch-policies.yaml's header comment and question-resolution.md's
  protocol-error step both point at the new document; no gate entry,
  option_id, action or resolution step changes; neither file gains the
  forbidden "decision table" phrase.
- AC-6: the document introduces no second policy table and no option
  vocabulary of its own, and cites (never restates) the issuing-site map.
- AC-7: exercised by running the whole suite, not by a test in this module.

The `gate_policies:` parsing below is the same restricted-subset hand-rolled
parser convention as tests/test_batch_policies.py (module docstring there):
one top-level `gate_policies:` key, 2-space-indented gate IDs, 4-space-
indented scalar `key: value` children; no lists, no flow style, no anchors.
PyYAML is a runtime dependency of the em-workflow plugin, not a test
dependency, so this module does not import it (IMPLEMENTATION.md,
Technology Stack).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "gate-option-vocabulary.md"
)
POLICY_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "batch-policies.yaml"
)
QUESTION_RESOLUTION_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)


def parse_gate_policies(text):
    """Restricted-subset parser for the `gate_policies:` block (see module
    docstring). Returns {gate_id: {key: value_str}}."""
    lines = text.splitlines()
    gate_policies = {}
    in_block = False
    current_gate = None
    saw_block = False

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not in_block:
            if line == "gate_policies:":
                in_block = True
                saw_block = True
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            break
        if indent == 2:
            if not stripped.endswith(":"):
                raise ValueError(f"expected a gate-ID key, got: {raw!r}")
            current_gate = stripped[:-1]
            gate_policies[current_gate] = {}
        elif indent == 4:
            if current_gate is None or ":" not in stripped:
                raise ValueError(f"unexpected line in gate block: {raw!r}")
            key, _, value = stripped.partition(":")
            gate_policies[current_gate][key.strip()] = value.strip()
        else:
            raise ValueError(f"unexpected indentation: {raw!r}")

    if not saw_block:
        raise ValueError("no top-level `gate_policies:` key found")
    return gate_policies


def select_gate_ids(gate_policies):
    return {
        gate_id
        for gate_id, attrs in gate_policies.items()
        if attrs.get("action") == "select"
    }


def _section(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def parse_exemption_table_rows(section_text):
    """Parse the data rows of a Markdown pipe table inside
    `section_text` (skips the header row and the `---` separator row).
    Returns a list of 3-tuples of raw, stripped cell text. Raises
    ValueError if a data row does not have exactly 3 cells -- a malformed
    row fails loudly rather than being silently dropped, matching this
    feature's error-handling policy for the verification layer
    (IMPLEMENTATION.md Conventions)."""
    table_lines = [
        line for line in section_text.splitlines() if line.strip().startswith("|")
    ]
    if not table_lines:
        raise ValueError("no Markdown table found in exemption registry section")
    data_lines = table_lines[2:]  # skip header row + `---` separator row
    rows = []
    for line in data_lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            raise ValueError(f"exemption row does not have exactly 3 cells: {line!r}")
        rows.append(tuple(cells))
    return rows


def validate_exemption_rows(rows, select_ids):
    """Return a list of violation strings for `rows` (as returned by
    parse_exemption_table_rows); an empty list means every row is
    well-formed. A row is invalid if its gate_id is not an `action: select`
    entry of batch-policies.yaml, if its reason cell is empty, or if its
    compensating-guarantee cell is empty."""
    violations = []
    for gate_cell, reason_cell, guarantee_cell in rows:
        gate_id = gate_cell.strip("`").strip()
        if gate_id not in select_ids:
            violations.append(
                f"{gate_id!r} is not an `action: select` entry of batch-policies.yaml"
            )
        if not reason_cell:
            violations.append(f"{gate_id!r} row is missing a reason")
        if not guarantee_cell:
            violations.append(
                f"{gate_id!r} row is missing a compensating guarantee"
            )
    return violations


class GateOptionVocabularyDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOC_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.policy_text = fh.read()
        cls.gate_policies = parse_gate_policies(cls.policy_text)
        cls.select_ids = select_gate_ids(cls.gate_policies)


class TestDocExists(GateOptionVocabularyDocTestCase):
    def test_doc_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))


# --- AC-1: correspondence rule, authoritative side, protocol-error abort --


class TestCorrespondenceRuleStated(GateOptionVocabularyDocTestCase):
    def test_states_the_correspondence_rule(self):
        section = _section(self.text, "## Correspondence rule", "## Why it matters")
        self.assertIn("action: select", section)
        self.assertIn("option_id", section)
        self.assertIn(
            "must be among the option_ids the gate's issuing site declares",
            re.sub(r"\s+", " ", section),
        )

    def test_names_policy_file_as_authoritative_side(self):
        section = _section(self.text, "## Correspondence rule", "## Why it matters")
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("authoritative side", norm_section)
        self.assertIn(
            "reconciliation always moves the issuing site toward the "
            "policy file, never the policy file toward the issuing site",
            norm_section,
        )

    def test_names_protocol_error_abort_as_the_prevented_failure_mode(self):
        section = _section(self.text, "## Why it matters", "## Canonical declaration format")
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("protocol error", norm_section)
        self.assertIn("aborts the phase", norm_section)
        self.assertIn("non-blocking preference", norm_section)


# --- AC-2: canonical declaration format -----------------------------------


class TestCanonicalDeclarationFormat(GateOptionVocabularyDocTestCase):
    def _format_section(self):
        return _section(
            self.text, "## Canonical declaration format", "## Issuing-site map"
        )

    def test_states_the_exact_heading(self):
        section = self._format_section()
        self.assertIn("`## Gate option vocabulary`", section)

    def test_states_column_order(self):
        section = self._format_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "a gate-id column, an option-id column and a meaning column",
            norm_section,
        )

    def test_states_one_row_per_option(self):
        section = self._format_section()
        self.assertIn("One row per offered option", section)

    def test_states_backtick_quoted_identifiers(self):
        section = self._format_section()
        self.assertIn("backtick-quoted `gate_id`", section)
        self.assertIn("backtick-quoted `option_id`", section)

    def test_states_prose_meaning(self):
        section = self._format_section()
        self.assertIn("non-empty prose meaning", section)

    def test_states_why_not_gate_identifiers_heading(self):
        section = self._format_section()
        self.assertIn("### Why not `## Gate identifiers`", section)
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("validate-worker-output.py", norm_section)
        self.assertIn("frozen script", norm_section)
        self.assertIn("worker-unattributed", norm_section)

    def test_format_is_complete_enough_to_write_a_conforming_block(self):
        # A synthetic block, hand-built purely from the format section's
        # stated rules (heading text, column order, backtick-quoting, one
        # row per option, non-empty prose meaning) -- not copied from any
        # existing document -- must satisfy every rule the section states.
        section = self._format_section()
        block = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `create-spec.feature-identity` | `derive_from_task_description` | "
            "derive the feature name from the task description |\n"
        )
        self.assertIn("## Gate option vocabulary", block)
        header_row = block.splitlines()[2]
        self.assertEqual(
            [c.strip() for c in header_row.strip("|").split("|")],
            ["gate_id", "option_id", "meaning"],
        )
        data_row = block.splitlines()[4]
        cells = [c.strip() for c in data_row.strip("|").split("|")]
        self.assertEqual(len(cells), 3)
        self.assertTrue(cells[0].startswith("`") and cells[0].endswith("`"))
        self.assertTrue(cells[1].startswith("`") and cells[1].endswith("`"))
        self.assertTrue(cells[2])
        # Sanity: the format section is what states each of these rules --
        # otherwise this test would be checking the synthetic block against
        # nothing.
        self.assertIn("gate-id column, an option-id column", re.sub(r"\s+", " ", section))


# --- AC-3: exemption registry ----------------------------------------------


class TestExemptionRegistryStructure(GateOptionVocabularyDocTestCase):
    def _registry_section(self):
        return _section(self.text, "## Exemption registry", "## Scope")

    def test_table_has_three_named_columns(self):
        section = self._registry_section()
        header_line = next(
            line for line in section.splitlines() if line.strip().startswith("|")
        )
        cells = [c.strip() for c in header_line.strip().strip("|").split("|")]
        self.assertEqual(cells, ["gate_id", "reason", "compensating guarantee"])

    def test_states_only_source_of_exemptions(self):
        section = self._registry_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("ONLY source", norm_section)
        self.assertIn("holds no exemption list of its own", norm_section)

    def test_states_absent_registry_means_zero_exemptions(self):
        section = self._registry_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("absent registry file", norm_section.lower())
        self.assertIn("read as zero exemptions", norm_section)

    def test_registry_holds_zero_rows(self):
        section = self._registry_section()
        rows = parse_exemption_table_rows(section)
        self.assertEqual(rows, [])

    def test_states_zero_rows_in_words(self):
        section = self._registry_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("currently holds zero rows", norm_section)


# --- AC-4: registry validator proven against synthetic documents ----------


class TestExemptionRegistryValidatorAgainstSyntheticRows(GateOptionVocabularyDocTestCase):
    def setUp(self):
        # Any real `action: select` gate works as the "valid gate" fixture;
        # the first one in sorted order keeps this deterministic.
        self.assertTrue(self.select_ids, "no select gates found -- fixture is empty")
        self.valid_select_gate = sorted(self.select_ids)[0]
        # A real gate that exists but is NOT `action: select` -- proves the
        # "not a select entry" branch against a genuine non-select gate,
        # not only an invented one.
        non_select = {
            gid: attrs
            for gid, attrs in self.gate_policies.items()
            if attrs.get("action") != "select"
        }
        self.assertTrue(non_select, "no non-select gates found -- fixture is empty")
        self.non_select_gate = sorted(non_select.keys())[0]

    def _row_section(self, gate_id, reason, guarantee):
        return (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate_id}` | {reason} | {guarantee} |\n"
        )

    def test_well_formed_row_has_no_violations(self):
        section = self._row_section(
            self.valid_select_gate,
            "mechanical check cannot reach this gate",
            "manual review at every merge",
        )
        rows = parse_exemption_table_rows(section)
        violations = validate_exemption_rows(rows, self.select_ids)
        self.assertEqual(violations, [])

    def test_row_missing_reason_is_flagged(self):
        section = self._row_section(self.valid_select_gate, "", "manual review")
        rows = parse_exemption_table_rows(section)
        violations = validate_exemption_rows(rows, self.select_ids)
        self.assertTrue(
            any("missing a reason" in v for v in violations),
            f"expected a missing-reason violation, got: {violations}",
        )

    def test_row_missing_guarantee_is_flagged(self):
        section = self._row_section(self.valid_select_gate, "some reason", "")
        rows = parse_exemption_table_rows(section)
        violations = validate_exemption_rows(rows, self.select_ids)
        self.assertTrue(
            any("missing a compensating guarantee" in v for v in violations),
            f"expected a missing-guarantee violation, got: {violations}",
        )

    def test_row_naming_a_non_select_gate_is_flagged(self):
        section = self._row_section(
            self.non_select_gate, "some reason", "some guarantee"
        )
        rows = parse_exemption_table_rows(section)
        violations = validate_exemption_rows(rows, self.select_ids)
        self.assertTrue(
            any("not an `action: select` entry" in v for v in violations),
            f"expected a non-select-gate violation, got: {violations}",
        )

    def test_the_real_documents_zero_rows_produce_zero_violations(self):
        # Non-vacuity: the empty real registry alone would trivially pass
        # `validate_exemption_rows([], ...) == []`, which the four tests
        # above prove is a meaningful check, not a vacuous one.
        section = _section(self.text, "## Exemption registry", "## Scope")
        rows = parse_exemption_table_rows(section)
        violations = validate_exemption_rows(rows, self.select_ids)
        self.assertEqual(violations, [])


# --- AC-5: the two pointers -------------------------------------------------


class TestPolicyFilePointer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_header_points_at_the_new_document(self):
        header = self.text.split("gate_policies:", 1)[0]
        self.assertIn("references/gate-option-vocabulary.md", header)

    def test_no_forbidden_phrase_gained(self):
        self.assertNotIn("decision table", self.text.lower())
        self.assertNotIn("決定表", self.text)

    def test_gate_entries_unchanged(self):
        gate_policies = parse_gate_policies(self.text)
        expected = {
            "create-spec.feature-identity": {
                "action": "select",
                "option_id": "derive_from_task_description",
            },
            "design-system.reclassify": {
                "action": "select",
                "option_id": "em_workflow",
            },
            "create-plan.existing-files": {"action": "select", "option_id": "merge"},
        }
        for gate_id, attrs in expected.items():
            with self.subTest(gate_id=gate_id):
                self.assertEqual(gate_policies[gate_id], attrs)


class TestQuestionResolutionPointer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(QUESTION_RESOLUTION_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def _batch_sequence_section(self):
        marker = "## Batch resolution sequence"
        end_marker = "## Unlisted-gate fallback"
        start = self.text.index(marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def test_protocol_error_step_points_at_the_new_document(self):
        section = self._batch_sequence_section()
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("protocol error", norm_section)
        self.assertIn("references/gate-option-vocabulary.md", norm_section)

    def test_no_forbidden_phrase_gained(self):
        self.assertNotIn("decision table", self.text.lower())
        self.assertNotIn("決定表", self.text)

    def test_protocol_error_step_still_present_verbatim(self):
        # The pre-existing statement must survive unmodified alongside the
        # new pointer sentence -- pre-existing coverage kept passing.
        self.assertIn(
            "this is a protocol error and the phase aborts", self.text
        )
        self.assertIn("label matching is never substituted", self.text)

    def test_no_feature_docs_task_identifier_introduced(self):
        # Pre-existing invariant (AC-7, round2.yaml bs8): no task00NN
        # attribution anywhere in this document.
        self.assertIsNone(re.search(r"task\d{4}", self.text))


# --- AC-6: no second policy table, no restated issuing-site map -----------


class TestNoSecondPolicyTableOrRestatedMap(GateOptionVocabularyDocTestCase):
    def test_scope_section_states_no_second_policy_table(self):
        section = _section(self.text, "## Scope")
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn(
            "introduces no policy decision and no gate's option vocabulary "
            "of its own",
            norm_section,
        )
        self.assertIn("single policy table", norm_section)

    def test_issuing_site_map_is_cited_not_restated(self):
        section = _section(self.text, "## Issuing-site map", "## Exemption registry")
        norm_section = re.sub(r"\s+", " ", section)
        self.assertIn("correspondence-check module under `tests/`", norm_section)
        self.assertIn("does not restate its rows", norm_section)
        # Not restated: no gate_id -> document-path row is spelled out here.
        self.assertNotIn("| `create-spec.feature-identity` |", section)

    def test_does_not_contain_a_second_gate_policies_key(self):
        self.assertNotIn("gate_policies:", self.text)


if __name__ == "__main__":
    unittest.main()
