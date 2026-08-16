"""Tests for task0001 (batch-stop-contract): the terminal-line contract SSOT
document and its pointer in `batch-mode.md`.

Covers task0001 Acceptance Criteria
(feature-docs/batch-stop-contract/tasks/task0001.md):

- AC-1: `em-workflow/references/batch-terminal-line.md` exists, carries the
  seven fixed level-2 headings in order, defines the prefix literal and the
  fixed four-field order, states that the same prefix/fields are used for
  both terminal states, states no external tool is needed, and states
  emission happens only in a batch-mode run.
- AC-2: the `## Stop reason codes` section's table extracts to exactly the
  nine fixed codes (no duplicate, no empty member), documents `none` as
  reserved for `state=completed`, and states every stop line also carries a
  `step` field and a `detail` field.
- AC-3: the `## Stop point coverage` section binds each of the nine
  stop-point keys to exactly one reason code (bidirectional coverage), each
  row naming a source document.
- AC-4: the `## No line on a wait turn` section states stop condition 5
  emits no line; the `## Field values` section defines the `no-step`
  sentinel and its condition.
- AC-5: the `## Responsibility boundary` section states no status operation
  against the external task-management service, and that `detail` carries
  no confidential information.
- AC-6: `batch-mode.md` names the contract document, restates none of its
  literals, keeps its Non-packet gates table row count unchanged, and still
  satisfies IMPLEMENTATION.md D7's constraints.
- AC-7: the prefix literal occurs, among all files under `em-workflow/`,
  only in `references/batch-terminal-line.md`, and within that file only
  inside fenced example blocks.
- AC-8: this module is discovered by `python3 -m unittest discover -s
  tests`, imports the Python standard library only (`os`, `re`, `unittest`,
  `pathlib` -- no third-party or project dependency), and every matcher it
  defines carries a negative proof plus a non-vacuity guard.

Test authoring follows IMPLEMENTATION.md's "Test authoring (NFR4)"
convention (the pattern of `tests/test_routeback_reset_scope_version_bump.py`):
durable invariants over fixed literals wherever a literal would go stale,
negative proof + non-vacuity guard per matcher, pure regression guards over
retained wording exempted. All assertions read raw file text
(`Path.read_text`), matching `tests/test_reference_sweep.py`'s convention, so
a literal hidden inside a fenced block is still seen by the sweep in AC-7.

Matcher -> negative-proof inventory:

- `_assert_well_formed_code_list` (reason-code table extractor validation):
  negative proofs are `test_duplicate_code_is_rejected` and
  `test_empty_first_cell_is_rejected`; non-vacuity guards are
  `test_duplicate_table_is_otherwise_well_formed` and
  `test_empty_cell_table_is_otherwise_well_formed`.
- `_assert_bidirectional_coverage` (coverage table extractor validation):
  negative proofs are `test_missing_key_is_rejected`,
  `test_code_outside_set_is_rejected` and
  `test_duplicate_stop_point_key_is_rejected`; non-vacuity guards are the
  corresponding `..._parses_into_a_non_empty_pair_of_sets` tests.
- Regression guards over retained `batch-mode.md` wording (AC-6's row-count,
  catch-all, diff-size-row and per-command-row checks) are exempt from a
  negative proof per IMPLEMENTATION.md's Test authoring note -- they pin
  content this task does not change, they do not introduce a new matcher.

Edge cases (Test Notes): a reason code mentioned only in prose (not a table
row) must not be picked up by the extractor
(`test_extractor_ignores_reason_codes_mentioned_only_in_prose`); a
stop-point key listed twice must fail
(`test_duplicate_stop_point_key_is_rejected`); the AC-7 sweep walks every
file under `em-workflow/` via `os.walk`, never a hand-maintained allowlist.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

PREFIX = "EM_WORKFLOW_TERMINAL:"
SENTINEL = "no-step"

# IMPLEMENTATION.md Shared Components -- fixed by the plan, not renegotiated
# here.
CONTRACT_HEADINGS = [
    "Purpose",
    "Line format",
    "Field values",
    "Stop reason codes",
    "Stop point coverage",
    "No line on a wait turn",
    "Responsibility boundary",
]

REASON_CODES = frozenset(
    {
        "step_stuck",
        "step_needs_intervention",
        "workflow_yaml_unparseable",
        "git_setup_aborted",
        "gate_fail_closed",
        "gate_option_unavailable",
        "implement_task_failed",
        "verify_rework_cap_reached",
        "completion_aborted",
    }
)

STOP_POINT_KEYS = frozenset(
    {
        "stop-condition-2",
        "stop-condition-3",
        "stop-condition-4",
        "stop-condition-6",
        "fail-closed-abort",
        "policy-option-unavailable",
        "implement-second-failure",
        "verify-rework-cap",
        "step-c-abort",
    }
)

# Ordered pairing used only to build forged coverage samples below -- the
# contract itself treats both STOP_POINT_KEYS and REASON_CODES as unordered.
_KEY_CODE_PAIRS_IN_ORDER = [
    ("stop-condition-2", "step_stuck"),
    ("stop-condition-3", "step_needs_intervention"),
    ("stop-condition-4", "workflow_yaml_unparseable"),
    ("stop-condition-6", "git_setup_aborted"),
    ("fail-closed-abort", "gate_fail_closed"),
    ("policy-option-unavailable", "gate_option_unavailable"),
    ("implement-second-failure", "implement_task_failed"),
    ("verify-rework-cap", "verify_rework_cap_reached"),
    ("step-c-abort", "completion_aborted"),
]

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
BACKTICK_CELL_RE = re.compile(r"^`([^`]*)`$")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses all whitespace runs (including line wraps) to a single
    space, matching the convention in tests/test_batch_policies.py, so a
    multi-word prose phrase check does not depend on exactly where the
    source file happens to wrap a line. Never used for table extraction,
    which depends on newlines to delimit rows."""
    return re.sub(r"\s+", " ", text)


def _sections(text):
    """Splits `text` into a dict keyed by level-2 heading text (without the
    leading `## `), each value the body up to the next level-2 heading (or
    end of text). Dict insertion order matches document order, so a caller
    can check heading order via `list(sections.keys())`."""
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row.
    Rows are located by the leading/trailing `|` convention used throughout
    this repository's docs (see tests/test_reference_sweep.py)."""
    raw_rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row, e.g. |---|---|---|
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


def _first_column_code(cell):
    """Extracts the code from a single-backticked cell (`` `code` ``), or
    None when the cell is not of that exact shape -- covers both "not
    backticked" and "empty" malformed cells uniformly."""
    match = BACKTICK_CELL_RE.match(cell)
    if match is None:
        return None
    return match.group(1) or None


def _extract_reason_code_table(section_text):
    """Parses the `## Stop reason codes` table's first column into a list
    of codes, duplicates and malformed (None) entries preserved rather than
    deduplicated -- validation is the caller's job
    (`_assert_well_formed_code_list`). Returns [] when no table rows are
    found (a bare list, not None, since a Markdown table with zero data
    rows and one with a wholly absent table are both "nothing to extract"
    here; callers needing to distinguish parse failure use the row count)."""
    rows = _table_rows(section_text)
    return [_first_column_code(row[0]) for row in rows]


def _assert_well_formed_code_list(test, codes):
    """Validation for the reason-code extractor: no cell failed to parse as
    a single backticked code (a None entry), and no code repeats."""
    test.assertNotIn(
        None, codes, "a reason-code table row's first cell is not a single "
        "backticked, non-empty code"
    )
    test.assertEqual(
        len(codes), len(set(codes)), f"duplicate reason code(s) in {codes}"
    )


def _extract_coverage_table(section_text):
    """Parses the `## Stop point coverage` table into (stop_point_key,
    reason_code) pairs from the first two backticked columns."""
    rows = _table_rows(section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[1])) for row in rows]


def _assert_bidirectional_coverage(test, pairs, expected_keys, expected_codes):
    """Validation for the coverage extractor: every stop-point key appears
    exactly once (multiset equality against `expected_keys`), every bound
    code is a member of `expected_codes`, and every one of `expected_codes`
    is used by at least one row (multiset equality collapsed to set
    equality, since a code used twice still satisfies "at least one")."""
    keys_seen = [key for key, _code in pairs]
    codes_seen = [code for _key, code in pairs]
    test.assertNotIn(
        None, keys_seen, "a coverage row's stop-point key is not a single "
        "backticked, non-empty token"
    )
    test.assertNotIn(
        None, codes_seen, "a coverage row's reason code is not a single "
        "backticked, non-empty token"
    )
    test.assertEqual(
        sorted(keys_seen),
        sorted(expected_keys),
        "every stop-point key must appear exactly once",
    )
    test.assertEqual(
        set(codes_seen),
        set(expected_codes),
        "every reason code must be used by at least one row, and no bound "
        "code may lie outside the closed set",
    )


def _forged_coverage_table(pairs):
    # `_table_rows` always drops its first parsed row as the table header
    # (matching every real table in this document), so a forged sample must
    # carry a header + separator row too, or it silently loses one data row.
    header = "| Stop point | Reason code | Source |\n|---|---|---|\n"
    return header + "".join(
        f"| `{key}` | `{code}` | `skills/develop/SKILL.md` |\n" for key, code in pairs
    )


def _iter_em_workflow_files(plugin_root):
    for dirpath, _dirnames, filenames in os.walk(plugin_root):
        for filename in filenames:
            yield Path(dirpath) / filename


class TestContractDocumentStructure(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.sections = _sections(cls.text)

    def test_document_exists(self):
        self.assertTrue(CONTRACT_PATH.is_file())

    def test_seven_level_2_headings_in_order(self):
        self.assertEqual(list(self.sections.keys()), CONTRACT_HEADINGS)

    def test_prefix_literal_is_defined(self):
        self.assertIn(PREFIX, self.text)

    def test_fixed_four_field_order(self):
        section = self.sections["Line format"]
        for field in ("state", "step", "reason", "detail"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", section)
        order = [section.index(f"`{f}`") for f in ("state", "step", "reason", "detail")]
        self.assertEqual(order, sorted(order))

    def test_states_same_prefix_and_fields_for_both_terminal_states(self):
        section = self.sections["Line format"]
        self.assertIn("same prefix and the same four fields", _normalize(section))
        self.assertIn("`state=completed`", section)
        self.assertIn("`state=stopped`", section)

    def test_states_no_external_tool_needed(self):
        self.assertIn("no external tool", _normalize(self.sections["Line format"]))

    def test_states_batch_only_emission(self):
        self.assertIn(
            "only in a batch-mode run", _normalize(self.sections["Line format"])
        )


class TestStopReasonCodes(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        cls.codes = _extract_reason_code_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.codes)

    def test_codes_are_well_formed(self):
        _assert_well_formed_code_list(self, self.codes)

    def test_extracted_set_equals_the_nine_fixed_codes(self):
        self.assertEqual(set(self.codes), REASON_CODES)

    def test_none_documented_as_reserved_for_completed(self):
        self.assertIn("`none`", self.section)
        self.assertIn("reserved", self.section)
        self.assertIn("`state=completed`", self.section)

    def test_states_step_and_detail_fields_also_carried(self):
        self.assertIn("`step`", self.section)
        self.assertIn("`detail`", self.section)

    def test_extractor_ignores_reason_codes_mentioned_only_in_prose(self):
        sample = (
            "| Code | Meaning | Applies to `state` |\n"
            "|---|---|---|\n"
            "| `step_stuck` | a stuck step | `stopped` |\n"
            "\n"
            "The code `git_setup_aborted` is mentioned here in prose only, "
            "never as a table row.\n"
        )
        self.assertEqual(_extract_reason_code_table(sample), ["step_stuck"])


FORGED_DUPLICATE_CODE_TABLE = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `step_stuck` | first occurrence | `stopped` |\n"
    "| `step_stuck` | second occurrence | `stopped` |\n"
)

FORGED_EMPTY_CELL_TABLE = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `step_stuck` | well formed row | `stopped` |\n"
    "|  | missing code | `stopped` |\n"
)


class TestReasonCodeExtractorNegativeProofs(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the reason-code table
    validator (`_assert_well_formed_code_list`)."""

    def test_duplicate_table_is_otherwise_well_formed(self):
        codes = _extract_reason_code_table(FORGED_DUPLICATE_CODE_TABLE)
        self.assertEqual(codes, ["step_stuck", "step_stuck"])

    def test_duplicate_code_is_rejected(self):
        codes = _extract_reason_code_table(FORGED_DUPLICATE_CODE_TABLE)
        with self.assertRaises(AssertionError):
            _assert_well_formed_code_list(self, codes)

    def test_empty_cell_table_is_otherwise_well_formed(self):
        codes = _extract_reason_code_table(FORGED_EMPTY_CELL_TABLE)
        self.assertEqual(len(codes), 2)
        self.assertEqual(codes[0], "step_stuck")

    def test_empty_first_cell_is_rejected(self):
        codes = _extract_reason_code_table(FORGED_EMPTY_CELL_TABLE)
        with self.assertRaises(AssertionError):
            _assert_well_formed_code_list(self, codes)


class TestStopPointCoverage(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        cls.pairs = _extract_coverage_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.pairs)

    def test_bidirectional_coverage(self):
        _assert_bidirectional_coverage(self, self.pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_each_row_names_a_source_document(self):
        rows = _table_rows(self.section)
        for row in rows:
            with self.subTest(row=row):
                self.assertTrue(row[2].strip())


FORGED_MISSING_KEY_TABLE = _forged_coverage_table(_KEY_CODE_PAIRS_IN_ORDER[:-1])
FORGED_CODE_OUTSIDE_SET_TABLE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER[:-1] + [("step-c-abort", "bogus_code")]
)
FORGED_DUPLICATE_KEY_TABLE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER[:-1] + [("stop-condition-2", "completion_aborted")]
)


class TestCoverageMatcherNegativeProofs(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the bidirectional
    coverage validator (`_assert_bidirectional_coverage`)."""

    def test_missing_key_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_MISSING_KEY_TABLE)
        self.assertEqual(len(pairs), 8)
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_missing_key_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_MISSING_KEY_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_code_outside_set_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_CODE_OUTSIDE_SET_TABLE)
        self.assertEqual(len(pairs), 9)
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_code_outside_set_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_CODE_OUTSIDE_SET_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_duplicate_stop_point_key_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_DUPLICATE_KEY_TABLE)
        self.assertEqual(len(pairs), 9)
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_duplicate_stop_point_key_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_DUPLICATE_KEY_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)


class TestNoLineOnWaitTurnAndSentinel(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.sections = _sections(_read(CONTRACT_PATH))

    def test_states_stop_condition_5_emits_no_line(self):
        section = _normalize(self.sections["No line on a wait turn"])
        self.assertIn("stop condition 5", section)
        self.assertIn("no terminal line", section)

    def test_field_values_defines_the_sentinel_and_its_condition(self):
        section = self.sections["Field values"]
        self.assertIn(f"`{SENTINEL}`", section)
        self.assertIn("no `workflow.yaml` step is in effect", _normalize(section))


class TestResponsibilityBoundary(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Responsibility boundary"]

    def test_states_no_status_operation_against_external_service(self):
        section = _normalize(self.section)
        self.assertIn("no status operation", section)
        self.assertIn("external task-management service", section)

    def test_states_detail_carries_no_confidential_information(self):
        self.assertIn("`detail`", self.section)
        self.assertIn("no confidential information", _normalize(self.section))


class TestBatchModePointer(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.sections = _sections(cls.text)

    def test_names_the_contract_document(self):
        self.assertIn("references/batch-terminal-line.md", self.text)

    def test_restates_no_contract_literal(self):
        self.assertNotIn(PREFIX, self.text)
        for code in sorted(REASON_CODES):
            with self.subTest(code=code):
                self.assertNotIn(code, self.text)
        self.assertNotIn(SENTINEL, self.text)
        for field in ("state=", "step=", "reason=", "detail="):
            with self.subTest(field=field):
                self.assertNotIn(field, self.text)

    def test_non_packet_gates_table_row_count_unchanged(self):
        rows = _table_rows(self.sections["Non-packet gates"])
        self.assertEqual(len(rows), 10)

    def test_d7_pinned_strings_still_absent(self):
        self.assertNotIn("decision table", self.text.lower())
        self.assertNotIn("決定表", self.text)
        self.assertNotIn("rework.spec-change", self.text)
        self.assertNotIn("failed_items", self.text)

    def test_catch_all_paragraph_unchanged(self):
        self.assertIn("ten rows above", self.text)

    def test_diff_size_gate_row_unchanged(self):
        match = re.search(r"^\|.*diff-size gate.*\|$", self.text, re.MULTILINE)
        self.assertIsNotNone(match, "diff-size gate row not found in batch-mode.md")
        self.assertIn("unlisted-gate fallback", match.group(0))

    def test_per_command_approval_row_unchanged(self):
        match = re.search(
            r"^\|.*Per-command approval fallback.*\|$", self.text, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "per-command approval fallback row not found in batch-mode.md"
        )
        self.assertIn("per literal command string", match.group(0))


class TestPrefixUniqueness(unittest.TestCase):
    """AC-7. The sweep walks every file under em-workflow/ via os.walk --
    never a hand-maintained allowlist (Test Notes edge case)."""

    def test_prefix_occurs_only_in_the_contract_document(self):
        offenders = []
        for path in _iter_em_workflow_files(PLUGIN_ROOT):
            if path == CONTRACT_PATH:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if PREFIX in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], f"prefix leaked into: {offenders}")

    def test_prefix_appears_in_the_contract_document(self):
        self.assertIn(PREFIX, _read(CONTRACT_PATH))

    def test_prefix_occurs_only_inside_fenced_blocks(self):
        text = _read(CONTRACT_PATH)
        segments = text.split("```")
        outside_segments = segments[0::2]
        inside_segments = segments[1::2]
        for segment in outside_segments:
            self.assertNotIn(PREFIX, segment)
        self.assertTrue(any(PREFIX in segment for segment in inside_segments))


if __name__ == "__main__":
    unittest.main()
