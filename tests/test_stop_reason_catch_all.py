"""Tests for task0001 (stop-reason-coverage): the catch-all reason code
`unmapped_stop`, its coverage row and Fallback rule, and the
`command-refusal` row binding the command-approval refusal-pattern hard
fail to `gate_fail_closed`.

Covers task0001 Acceptance Criteria
(feature-docs/stop-reason-coverage/tasks/task0001.md), matchers named per
the task plan's Design section 5 table:

- TS-1 (AC-1/AC-2): the reason-code table's code set equals the 13-code
  set, including `unmapped_stop` with Applies-to `stopped`.
- TS-6/"Catch-all meaning" (AC-1): the `unmapped_stop` Meaning cell states
  that no other coverage row names the stop, and never says "unknown" or
  "undetermined".
- TS-12 (AC-2/AC-3): the `command-refusal` coverage row binds to
  `gate_fail_closed` with Source `references/batch-policies.yaml`, and the
  `gate_fail_closed` Meaning cell names the refusal-pattern hard fail while
  still passing the pre-existing citation / "both modes" / "interactive"
  checks, with none of the reserved-code leaked terms.
- TS-3 (AC-4): the Fallback rule paragraph states the lowest-precedence
  rule, and the section replaces the old "bound to exactly one reason
  code above" sentence with a by-construction exactly-one statement.
- TS-4 (AC-6): a resolver over the LIVE coverage pairs maps a named key to
  its row's code, and an unnamed key to the code bound to
  `unmapped-terminating-stop` -- proving the fallback is read from the
  document, not hard-coded here.
- TS-5 (AC-5): the Scope paragraph excludes wait turns, normal completion,
  `phase_done`, the infra auto-resume and the 64 KiB outcome.
- TS-6/"Catch-all detail" (AC-4 Design item 3): the Catch-all result
  paragraph requires `detail` to name the stop site and the concrete
  cause, and states `resume_conditions` stays mandatory.

Per D5 (IMPLEMENTATION.md), this module is self-contained: its own section
splitter and table extractor, no import of any other test module, standard
library only. Every matcher below carries a negative proof and a
non-vacuity guard (NFR4).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-terminal-line.md"

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
BACKTICK_CELL_RE = re.compile(r"^`([^`]*)`$")

FALLBACK_LABEL = "Fallback rule:"
SCOPE_LABEL = "Scope:"
CATCH_ALL_RESULT_LABEL = "Catch-all result:"

# The 13-code closed set this task grows REASON_CODES to (12 pre-existing
# codes, unchanged, plus the new catch-all). Re-declared locally per this
# repository's cross-module-isolation convention -- never imported from
# tests/test_batch_stop_contract.py.
REASON_CODES_13 = frozenset(
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
        "feature_resolution_aborted",
        "docs_commit_conflict_aborted",
        "no_work_required",
        "unmapped_stop",
    }
)

CATCH_ALL_STOP_POINT_KEY = "unmapped-terminating-stop"

OLD_EXACTLY_ONE_SENTENCE = (
    "Every terminating stop point is bound to exactly one reason code above."
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses whitespace runs (including line wraps) to a single space --
    never used for table extraction, which depends on newlines."""
    return re.sub(r"\s+", " ", text)


def _sections(text):
    """Splits `text` into a dict keyed by level-2 heading text, each value
    the body up to the next level-2 heading (or end of text)."""
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row."""
    raw_rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


def _first_column_code(cell):
    """Extracts the code from a single-backticked cell, or None when the
    cell is not of that exact shape."""
    match = BACKTICK_CELL_RE.match(cell)
    if match is None:
        return None
    return match.group(1) or None


# --- TS-1: reason-code set, including unmapped_stop with Applies-to stopped


def _extract_reason_code_applies_pairs(section_text):
    rows = _table_rows(section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[2])) for row in rows]


def _assert_reason_code_set_matches_13(test, pairs):
    codes = [code for code, _applies in pairs]
    test.assertNotIn(
        None, codes, "a reason-code table row's first cell is not a single "
        "backticked, non-empty code"
    )
    test.assertEqual(len(codes), len(set(codes)), f"duplicate reason code(s) in {codes}")
    test.assertEqual(set(codes), REASON_CODES_13)
    applies_map = dict(pairs)
    test.assertEqual(applies_map.get("unmapped_stop"), "stopped")


FORGED_TABLE_MISSING_UNMAPPED_STOP = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `step_stuck` | m | `stopped` |\n"
    "| `step_needs_intervention` | m | `stopped` |\n"
    "| `workflow_yaml_unparseable` | m | `stopped` |\n"
    "| `git_setup_aborted` | m | `stopped` |\n"
    "| `gate_fail_closed` | m | `stopped` |\n"
    "| `gate_option_unavailable` | m | `stopped` |\n"
    "| `implement_task_failed` | m | `stopped` |\n"
    "| `verify_rework_cap_reached` | m | `stopped` |\n"
    "| `completion_aborted` | m | `stopped` |\n"
    "| `feature_resolution_aborted` | m | `stopped` |\n"
    "| `docs_commit_conflict_aborted` | m | `stopped` |\n"
    "| `no_work_required` | m | `stopped` |\n"
)


class TestReasonCodeSetMatcher(unittest.TestCase):
    """TS-1."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        cls.pairs = _extract_reason_code_applies_pairs(cls.section)

    def test_thirteen_code_set_including_unmapped_stop_applies_stopped(self):
        _assert_reason_code_set_matches_13(self, self.pairs)

    def test_negative_proof_forged_twelve_row_table_is_rejected(self):
        pairs = _extract_reason_code_applies_pairs(FORGED_TABLE_MISSING_UNMAPPED_STOP)
        with self.assertRaises(AssertionError):
            _assert_reason_code_set_matches_13(self, pairs)

    def test_non_vacuity_forged_table_is_otherwise_well_formed(self):
        pairs = _extract_reason_code_applies_pairs(FORGED_TABLE_MISSING_UNMAPPED_STOP)
        codes = [code for code, _applies in pairs]
        self.assertEqual(len(codes), 12)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertNotIn(None, codes)


# --- Catch-all meaning: no other row names it; never "unknown"/"undetermined"


def _reason_code_meaning(section_text, code):
    for row in _table_rows(section_text):
        if _first_column_code(row[0]) == code:
            return row[1]
    return None


def _assert_catch_all_meaning_stated(test, meaning_cell):
    test.assertIsNotNone(meaning_cell, "no `unmapped_stop` row found")
    lowered = meaning_cell.lower()
    test.assertIn("no other coverage row names", lowered)
    test.assertNotIn("unknown", lowered)
    test.assertNotIn("undetermined", lowered)


FORGED_UNMAPPED_STOP_ROW_UNKNOWN_CAUSE = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `unmapped_stop` | A terminating stop whose cause is unknown | `stopped` |\n"
)


class TestCatchAllMeaningMatcher(unittest.TestCase):
    """Catch-all meaning (design table row 2)."""

    def test_meaning_states_no_other_row_names_and_no_unknown_wording(self):
        section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        meaning = _reason_code_meaning(section, "unmapped_stop")
        _assert_catch_all_meaning_stated(self, meaning)

    def test_negative_proof_unknown_cause_wording_is_rejected(self):
        meaning = _reason_code_meaning(
            FORGED_UNMAPPED_STOP_ROW_UNKNOWN_CAUSE, "unmapped_stop"
        )
        with self.assertRaises(AssertionError):
            _assert_catch_all_meaning_stated(self, meaning)

    def test_non_vacuity_forged_row_still_carries_code_and_stopped(self):
        rows = _table_rows(FORGED_UNMAPPED_STOP_ROW_UNKNOWN_CAUSE)
        self.assertEqual(_first_column_code(rows[0][0]), "unmapped_stop")
        self.assertEqual(_first_column_code(rows[0][2]), "stopped")


# --- TS-12: command-refusal row -> gate_fail_closed, and its Meaning cell


def _extract_coverage_table(section_text):
    rows = _table_rows(section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[1]), row[2]) for row in rows]


def _assert_refusal_row_and_meaning_stated(test, coverage_triples, gate_fail_closed_meaning):
    mapping = {key: (code, source) for key, code, source in coverage_triples}
    test.assertIn("command-refusal", mapping)
    code, source = mapping["command-refusal"]
    test.assertEqual(code, "gate_fail_closed")
    test.assertEqual(source, "`references/batch-policies.yaml`")
    test.assertIsNotNone(gate_fail_closed_meaning, "no `gate_fail_closed` row found")
    test.assertIn("references/question-resolution.md", gate_fail_closed_meaning)
    test.assertIn("both modes", gate_fail_closed_meaning)
    test.assertIn("interactive", gate_fail_closed_meaning)
    test.assertIn("references/batch-policies.yaml", gate_fail_closed_meaning)
    test.assertIn("create-spec.command-approval", gate_fail_closed_meaning)
    test.assertIn("refusal", gate_fail_closed_meaning.lower())
    for leaked_term in ("category: security", "category: license", "reversible: false"):
        test.assertNotIn(leaked_term, gate_fail_closed_meaning)


# Captured from the base commit (before this task's edit) -- the real
# pre-change `gate_fail_closed` Meaning cell.
PRE_CHANGE_GATE_FAIL_CLOSED_MEANING = (
    "A gate was classified fail-closed: the aborts "
    "`references/question-resolution.md` keeps fail-closed in both modes, "
    "plus, in interactive, that mode's own additional aborts"
)

FORGED_COVERAGE_WITH_COMMAND_REFUSAL_ROW = (
    "| Stop point | Reason code | Source |\n"
    "|---|---|---|\n"
    "| `command-refusal` | `gate_fail_closed` | `references/batch-policies.yaml` |\n"
)


class TestRefusalRowMatcher(unittest.TestCase):
    """TS-12."""

    def test_refusal_row_and_meaning_stated(self):
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        reason_section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        triples = _extract_coverage_table(coverage_section)
        meaning = _reason_code_meaning(reason_section, "gate_fail_closed")
        _assert_refusal_row_and_meaning_stated(self, triples, meaning)

    def test_negative_proof_pre_change_meaning_is_rejected(self):
        triples = _extract_coverage_table(FORGED_COVERAGE_WITH_COMMAND_REFUSAL_ROW)
        with self.assertRaises(AssertionError):
            _assert_refusal_row_and_meaning_stated(
                self, triples, PRE_CHANGE_GATE_FAIL_CLOSED_MEANING
            )

    def test_non_vacuity_pre_change_meaning_passes_citation_and_modes_checks(self):
        self.assertIn(
            "references/question-resolution.md", PRE_CHANGE_GATE_FAIL_CLOSED_MEANING
        )
        self.assertIn("both modes", PRE_CHANGE_GATE_FAIL_CLOSED_MEANING)
        self.assertIn("interactive", PRE_CHANGE_GATE_FAIL_CLOSED_MEANING)


# --- TS-3: Fallback rule precedence + by-construction exactly-one statement


def _assert_fallback_precedence_and_construction_statement(test, section_text):
    idx = section_text.find(FALLBACK_LABEL)
    test.assertNotEqual(idx, -1, f"label {FALLBACK_LABEL!r} not found")
    tail = section_text[idx:]
    normalized_tail = _normalize(tail)
    test.assertIn("binds to `unmapped_stop`", normalized_tail)
    test.assertIn("precedence over", normalized_tail)
    test.assertIn("`stop-condition-N`", normalized_tail)
    test.assertIn("`command-refusal`", normalized_tail)
    test.assertIn("applies last", normalized_tail)
    normalized_full = _normalize(section_text)
    test.assertIn("exactly one code", normalized_full)
    test.assertIn("by construction", normalized_full)
    test.assertNotIn(OLD_EXACTLY_ONE_SENTENCE, section_text)


FORGED_FALLBACK_PARAGRAPH_NO_PRECEDENCE = (
    "Fallback rule: a batch-terminating stop that no other row above "
    "names binds to `unmapped_stop`."
)


class TestFallbackPrecedenceMatcher(unittest.TestCase):
    """TS-3."""

    def test_fallback_precedence_and_construction_statement(self):
        section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        _assert_fallback_precedence_and_construction_statement(self, section)

    def test_negative_proof_missing_precedence_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_fallback_precedence_and_construction_statement(
                self, FORGED_FALLBACK_PARAGRAPH_NO_PRECEDENCE
            )

    def test_non_vacuity_forged_paragraph_carries_label_and_unmapped_stop(self):
        self.assertIn(FALLBACK_LABEL, FORGED_FALLBACK_PARAGRAPH_NO_PRECEDENCE)
        self.assertIn("`unmapped_stop`", FORGED_FALLBACK_PARAGRAPH_NO_PRECEDENCE)


# --- TS-4: resolution over the LIVE coverage pairs


def _live_coverage_pairs(coverage_section_text):
    rows = _table_rows(coverage_section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[1])) for row in rows]


def _resolve_stop_point_code(key, pairs):
    """The contract's actual precedence: a named row's own code wins; only
    a key absent from every named row falls through to the code the
    catch-all row (`unmapped-terminating-stop`) itself is bound to."""
    mapping = dict(pairs)
    if key in mapping:
        return mapping[key]
    return mapping[CATCH_ALL_STOP_POINT_KEY]


def _resolve_stop_point_code_ignoring_precedence(key, pairs):
    """WRONG resolver, used only as a negative-proof fixture: treats the
    catch-all as though it had the HIGHEST precedence instead of the
    lowest, so even a named key resolves to the catch-all's code."""
    mapping = dict(pairs)
    return mapping[CATCH_ALL_STOP_POINT_KEY]


# Untabled site names: test-local strings for stops the Fallback rule's
# examples name in prose but that carry no coverage-table row of their
# own. Asserted absent from the live coverage keys below so they cannot
# collide with a real key.
UNTABLED_FIXTURE_SITES = (
    "designer-contract-kind-none-token-present-abort",
    "designer-contract-em-workflow-tokens-html-only-abort",
    "phase-state-unknown-schema-version-abort",
)

NAMED_FIXTURES = {
    "stop-condition-3": "step_needs_intervention",
    "command-refusal": "gate_fail_closed",
}


class TestResolutionMatcher(unittest.TestCase):
    """TS-4."""

    @classmethod
    def setUpClass(cls):
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        cls.pairs = _live_coverage_pairs(coverage_section)
        cls.keys = {key for key, _code in cls.pairs}

    def test_untabled_fixture_names_are_absent_from_live_coverage_keys(self):
        for site in UNTABLED_FIXTURE_SITES:
            with self.subTest(site=site):
                self.assertNotIn(site, self.keys)

    def test_named_fixtures_are_present_in_live_coverage_keys(self):
        for key in NAMED_FIXTURES:
            with self.subTest(key=key):
                self.assertIn(key, self.keys)

    def test_named_key_resolves_to_its_own_code(self):
        for key, expected_code in NAMED_FIXTURES.items():
            with self.subTest(key=key):
                self.assertEqual(_resolve_stop_point_code(key, self.pairs), expected_code)

    def test_untabled_site_resolves_to_unmapped_stop(self):
        for site in UNTABLED_FIXTURE_SITES:
            with self.subTest(site=site):
                self.assertEqual(
                    _resolve_stop_point_code(site, self.pairs), "unmapped_stop"
                )

    def test_negative_proof_precedence_ignoring_resolver_fails_stop_condition_3(self):
        resolved = _resolve_stop_point_code_ignoring_precedence(
            "stop-condition-3", self.pairs
        )
        self.assertNotEqual(resolved, NAMED_FIXTURES["stop-condition-3"])


# --- TS-5: Scope exclusions


def _fallback_tail(coverage_section_text):
    idx = coverage_section_text.find(FALLBACK_LABEL)
    if idx == -1:
        return ""
    return coverage_section_text[idx:]


def _assert_scope_exclusions_stated(test, tail_text):
    test.assertIn(SCOPE_LABEL, tail_text)
    normalized = _normalize(tail_text)
    test.assertIn("stop condition 5", normalized)
    test.assertIn("launch and wake turns", normalized)
    test.assertIn("normal completion", normalized)
    test.assertIn("`phase_done`", normalized)
    test.assertIn("infra auto-resume", normalized)
    test.assertIn("64 KiB", normalized)


FORGED_SCOPE_TEXT_MISSING_EXCLUSIONS = (
    "Fallback rule: a batch-terminating stop that no other row above "
    "names binds to `unmapped_stop`.\n\n"
    "Scope: the fallback applies only to a stop that ends a batch run "
    "with `state` `stopped`."
)


class TestScopeMatcher(unittest.TestCase):
    """TS-5."""

    def test_scope_exclusions_stated(self):
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        tail = _fallback_tail(coverage_section)
        _assert_scope_exclusions_stated(self, tail)

    def test_negative_proof_missing_exclusions_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_scope_exclusions_stated(self, FORGED_SCOPE_TEXT_MISSING_EXCLUSIONS)

    def test_non_vacuity_forged_text_carries_label_and_unmapped_stop(self):
        self.assertIn(FALLBACK_LABEL, FORGED_SCOPE_TEXT_MISSING_EXCLUSIONS)
        self.assertIn("`unmapped_stop`", FORGED_SCOPE_TEXT_MISSING_EXCLUSIONS)

    def test_consumer_constraints_64kib_no_reason_code_no_row_wording_regression(self):
        """Regression (NFR4 pure-regression exemption): `## Consumer
        constraints` still says the 64 KiB / in-full collision adds no
        reason code and no coverage row -- untouched by this task."""
        consumer_section = _sections(_read(CONTRACT_PATH))["Consumer constraints"]
        normalized = _normalize(consumer_section)
        self.assertIn("adds no reason code and no", normalized)


# --- Catch-all detail (design table row "Catch-all detail"): detail names
# the stop site and cause; resume_conditions stays mandatory


def _catch_all_result_tail(coverage_section_text):
    idx = coverage_section_text.find(CATCH_ALL_RESULT_LABEL)
    if idx == -1:
        return ""
    return coverage_section_text[idx:]


def _assert_catch_all_detail_rule_stated(test, tail_text):
    test.assertIn(CATCH_ALL_RESULT_LABEL, tail_text)
    test.assertIn("`unmapped_stop`", tail_text)
    test.assertIn("`detail`", tail_text)
    normalized = _normalize(tail_text)
    test.assertIn("stop site", normalized)
    test.assertIn("owning document", normalized)
    test.assertIn("concrete cause", normalized)
    test.assertIn("`resume_conditions`", tail_text)
    test.assertIn("mandatory", normalized)


FORGED_CATCH_ALL_RESULT_TEXT = (
    "Catch-all result: when `reason` is `unmapped_stop`, `detail` "
    "describes what happened. `resume_conditions` stays mandatory."
)


class TestCatchAllDetailMatcher(unittest.TestCase):
    """Catch-all detail (Design section 3, item 3)."""

    def test_catch_all_detail_rule_stated(self):
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        tail = _catch_all_result_tail(coverage_section)
        _assert_catch_all_detail_rule_stated(self, tail)

    def test_negative_proof_missing_stop_site_and_cause_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_catch_all_detail_rule_stated(self, FORGED_CATCH_ALL_RESULT_TEXT)

    def test_non_vacuity_forged_paragraph_names_unmapped_stop_and_detail(self):
        self.assertIn("`unmapped_stop`", FORGED_CATCH_ALL_RESULT_TEXT)
        self.assertIn("`detail`", FORGED_CATCH_ALL_RESULT_TEXT)


# --- AC-6: this module imports only the standard library --------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        source = _read(Path(__file__).resolve())
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
