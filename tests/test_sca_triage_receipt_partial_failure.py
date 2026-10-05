"""Tests for sca-file-tasks-robustness/task0003: the triage_filing receipt
records a partial filing failure, and the review report (R6) and the batch
final result say "triage filing incomplete" with the packages never filed.

Covers task0003 Acceptance Criteria
(feature-docs/sca-file-tasks-robustness/tasks/task0003.md):

- AC-1: inside the Phase R4 slice, the "The receipt" item names
  `failed_package`, `failure_reason`, `malformed_findings`,
  `listing_dropped_count` and `unattempted_packages`.
- AC-2: inside the Phase R5 slice, the `triage_filing:` block of the YAML
  example carries the five keys with the values null, null, [], 0 and []
  and still comes after `rework_required: false`.
- AC-3: the R5 prose on the receipt names the five fields, states their
  `another-round` values, and defines `unattempted_packages` as the failed
  package plus every later never-attempted package in processing order with
  malformed findings excluded.
- AC-4: the R5 prose states that receipt values come only from the
  file-tasks summary, names `task_create_failed` and `task_update_failed`
  as the only non-null `failure_reason` values, and states that no
  advisory-sourced text or OS-error message is recorded in the receipt.
- AC-5: the document states there is no automatic retry, and that
  re-running file-tasks files only the remainder through duplicate
  detection provided the latest listing reflects the packages already
  filed.
- AC-6: inside the Phase R6 slice, a non-empty `unattempted_packages` is
  reported as "triage filing incomplete" with the packages and the same
  appears in the batch final result; the completion condition does not
  change; R4 and R5 carry no `gate_id:` line.
- AC-7: this module imports only the standard library, and at least one
  matcher here has a negative control. The `tests/test_sca_axis_triage_timing.py`
  pins and the four batch-mode pin modules are covered by the whole-suite
  run (`python3 -m unittest discover -s tests`), not asserted here.
- AC-8: in batch-mode.md, the Reporting item list carries exactly one added
  item with the phrase "triage filing incomplete" before "and the kept
  integration branch name"; the audit-item source map carries exactly one
  added row for it, before the kept-integration-branch row, whose persisted
  source names the round record path, `triage_filing.unattempted_packages`
  and `triage_filing.failed_package` as its only source and cites
  `references/review-phase.md`; neither the Reporting section nor that row
  restates the receipt's definitions; batch-mode.md's `gate_id` count and
  its level-2 heading list are unchanged.

This is a documentation task: verification is by textual assertion over the
raw text of review-phase.md and batch-mode.md. review-phase.md is sliced by
the literal "## Phase R4" / "## Phase R5" / "## Phase R6" headings so a
statement landing in the wrong phase fails, and whitespace is normalized
before phrase matching. Assertions pin field names, fixed tokens and short
anchor phrases, never whole sentences.

Matcher -> negative-control inventory (each matcher is fed a forged sample
missing exactly one required element and must reject it, alongside a
non-vacuity guard that the same forged sample with the element restored is
accepted):

- `_names_every_receipt_field` (AC-1)
- `_triage_block_has_expected_values` (AC-2)
- `_defines_unattempted_packages` (AC-3)
- `_states_receipt_values_come_only_from_summary` (AC-4)
- `_new_source_map_row_is_well_formed` (AC-8)
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
R5_HEADING = "## Phase R5: Persist the round record"
R6_HEADING = "## Phase R6: Report (Japanese)"
TRIAGE_FILING_HEADING = (
    "### Triage filing: once per review phase, immediately before the "
    "final round's R5 (FR11, FR24)"
)

RECEIPT_FIELDS = (
    "failed_package",
    "failure_reason",
    "malformed_findings",
    "listing_dropped_count",
    "unattempted_packages",
)

# The another-round values of the five new receipt fields, as they appear in
# the R5 YAML example's `triage_filing:` block.
EXPECTED_BLOCK_VALUES = {
    "failed_package": "null",
    "failure_reason": "null",
    "malformed_findings": "[]",
    "listing_dropped_count": "0",
    "unattempted_packages": "[]",
}

FAILURE_REASON_TOKENS = ("task_create_failed", "task_update_failed")

INCOMPLETE_PHRASE = "triage filing incomplete"
KEPT_BRANCH_PHRASE = "and the kept integration branch name"
ROUND_RECORD_PATH = "feature-docs/{feature}/reviews/roundN.yaml"
REVIEW_PHASE_CITATION = "references/review-phase.md"

BATCH_MODE_GATE_ID_COUNT = 8
BATCH_MODE_LEVEL2_HEADINGS = [
    "Purpose & activation",
    "Non-packet gates",
    "workflow.yaml `batch` block",
    "Structured result",
    "Reporting",
    "Batch quiet output",
]

# Phrases the batch-mode.md Reporting section and the new source-map row must
# NOT carry: review-phase.md owns every one of these definitions.
RESTATEMENT_PHRASES = (
    "processing order",
    "malformed",
    "automatic retry",
    "duplicate detection",
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start + len(start_marker))
    return text[start:end]


def _table_rows(section_text):
    """Each data row of a Markdown table in `section_text` as a list of cell
    strings, skipping the header row and the `---` separator row."""
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


class ReviewPhaseFixture:
    """Reads review-phase.md once and slices out R4, R5 and R6."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r4(cls):
        return _slice(cls.text(), R4_HEADING, R5_HEADING)

    @classmethod
    def r5(cls):
        return _slice(cls.text(), R5_HEADING, R6_HEADING)

    @classmethod
    def r6(cls):
        return _slice(cls.text(), R6_HEADING)

    @classmethod
    def triage_filing(cls):
        return _slice(cls.r4(), TRIAGE_FILING_HEADING)


class BatchModeFixture:
    """Reads batch-mode.md once and slices out Reporting and the Batch quiet
    output section."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(BATCH_MODE_PATH)
        return cls._text

    @classmethod
    def reporting(cls):
        # The end marker is a blank line followed by the heading line: the
        # Reporting section's own pointer sentence mentions the section name
        # inline, so the bare heading text would end the slice too early.
        return _slice(cls.text(), "\n## Reporting\n", "\n\n## Batch quiet output\n")

    @classmethod
    def quiet_output(cls):
        return _slice(cls.text(), "\n## Batch quiet output\n")


# ---------------------------------------------------------------------------
# AC-1: R4 "The receipt" item names the five fields
# ---------------------------------------------------------------------------


def _receipt_item(r4):
    """The R4 Triage filing subsection's item 4, "The receipt"."""
    return _slice(r4, "**The receipt**", "\n\n")


def _names_every_receipt_field(text):
    return all(field in text for field in RECEIPT_FIELDS)


class TestAC1R4ReceiptItemNamesFiveFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.item = _norm(_receipt_item(ReviewPhaseFixture.r4()))

    def test_receipt_item_names_every_new_field(self):
        for field in RECEIPT_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, self.item)

    def test_receipt_item_keeps_existing_content(self):
        self.assertIn("whether triage filing ran this round", self.item)
        self.assertIn("report path", self.item)

    def test_receipt_item_ties_the_fields_to_the_summary(self):
        self.assertIn("file-tasks", self.item)
        self.assertIn("summary", self.item)

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_names_every_receipt_field(self.item))


class TestAC1MatcherCanFail(unittest.TestCase):
    WELL_FORMED = (
        "records `failed_package`, `failure_reason`, `malformed_findings`, "
        "`listing_dropped_count` and `unattempted_packages`"
    )

    def test_non_vacuity_well_formed_sample_passes(self):
        self.assertTrue(_names_every_receipt_field(self.WELL_FORMED))

    def test_forged_item_missing_one_field_fails(self):
        for field in RECEIPT_FIELDS:
            with self.subTest(missing=field):
                forged = self.WELL_FORMED.replace(field, "something_else")
                self.assertFalse(_names_every_receipt_field(forged))


# ---------------------------------------------------------------------------
# AC-2: R5 YAML example's triage_filing block
# ---------------------------------------------------------------------------


def _triage_block_pairs(r5):
    """key -> (value, comment) for the indented lines of the `triage_filing:`
    block of R5's YAML example. The block is the run of indented lines after
    the root-level `triage_filing:` line."""
    start = r5.index("\ntriage_filing:")
    lines = r5[start + 1 :].splitlines()[1:]
    pairs = {}
    for line in lines:
        if not line.startswith((" ", "\t")):
            break
        match = re.match(r"^\s+([A-Za-z_]+):\s*(.*)$", line)
        if not match:
            continue
        value_and_comment = match.group(2)
        value, _, comment = value_and_comment.partition("#")
        pairs[match.group(1)] = (value.strip(), comment.strip())
    return pairs


def _triage_block_has_expected_values(r5):
    try:
        pairs = _triage_block_pairs(r5)
    except ValueError:
        return False
    for key, expected in EXPECTED_BLOCK_VALUES.items():
        if key not in pairs or pairs[key][0] != expected:
            return False
    return True


FORGED_R5_BLOCK = (
    "rework_required: false\n"
    "triage_filing:\n"
    "  executed: false\n"
    "  branch: null\n"
    "  filed: []\n"
    "  appended: []\n"
    "  duplicates_suppressed: []\n"
    "  report_path: null\n"
    "  failed_package: null\n"
    "  failure_reason: null\n"
    "  malformed_findings: []\n"
    "  listing_dropped_count: 0\n"
    "  unattempted_packages: []\n"
    "```\n"
)


class TestAC2R5YamlBlockCarriesFiveKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = ReviewPhaseFixture.r5()
        cls.pairs = _triage_block_pairs(cls.r5)

    def test_each_new_key_carries_its_another_round_value(self):
        for key, expected in EXPECTED_BLOCK_VALUES.items():
            with self.subTest(key=key):
                self.assertIn(key, self.pairs)
                self.assertEqual(self.pairs[key][0], expected)

    def test_each_new_key_has_an_inline_comment(self):
        for key in EXPECTED_BLOCK_VALUES:
            with self.subTest(key=key):
                self.assertTrue(
                    self.pairs.get(key, ("", ""))[1], f"{key} has no inline comment"
                )

    def test_failure_reason_comment_names_both_tokens_and_null(self):
        comment = self.pairs.get("failure_reason", ("", ""))[1]
        for token in FAILURE_REASON_TOKENS:
            self.assertIn(token, comment)
        self.assertIn("null", comment)

    def test_existing_block_keys_remain(self):
        for key in (
            "executed",
            "branch",
            "filed",
            "appended",
            "duplicates_suppressed",
            "report_path",
        ):
            with self.subTest(key=key):
                self.assertIn(key, self.pairs)

    def test_block_still_comes_after_rework_required_false(self):
        self.assertLess(
            self.r5.index("rework_required: false"),
            self.r5.index("\ntriage_filing:"),
        )

    def test_block_sits_inside_the_yaml_example_not_after_it(self):
        block_start = self.r5.index("\ntriage_filing:")
        fence_close = self.r5.index("\n```", block_start)
        block = self.r5[block_start:fence_close]
        for key in EXPECTED_BLOCK_VALUES:
            with self.subTest(key=key):
                self.assertIn(f"  {key}:", block)

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_triage_block_has_expected_values(self.r5))


class TestAC2MatcherCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_block_passes(self):
        self.assertTrue(_triage_block_has_expected_values(FORGED_R5_BLOCK))

    def test_forged_block_missing_a_key_fails(self):
        for key in EXPECTED_BLOCK_VALUES:
            with self.subTest(missing=key):
                forged = re.sub(rf"  {key}: .*\n", "", FORGED_R5_BLOCK)
                self.assertFalse(_triage_block_has_expected_values(forged))

    def test_forged_block_with_a_wrong_value_fails(self):
        forged = FORGED_R5_BLOCK.replace(
            "listing_dropped_count: 0", "listing_dropped_count: 1"
        )
        self.assertFalse(_triage_block_has_expected_values(forged))

    def test_forged_block_with_key_outside_the_block_fails(self):
        forged = (
            FORGED_R5_BLOCK.replace("  unattempted_packages: []\n", "")
            + "unattempted_packages: []\n"
        )
        self.assertFalse(_triage_block_has_expected_values(forged))


# ---------------------------------------------------------------------------
# AC-3 / AC-4: R5 prose on the receipt
# ---------------------------------------------------------------------------


def _receipt_prose(r5):
    """The R5 prose from the receipt paragraph through the end of the
    receipt discussion (the paragraph before the workflow.yaml update
    paragraph)."""
    return _slice(
        r5,
        "The round record also persists the triage-filing receipt",
        "develop-駆動: update workflow.yaml",
    )


def _defines_unattempted_packages(prose_norm):
    return all(
        anchor in prose_norm
        for anchor in (
            "`unattempted_packages` is the failed package",
            "every later package",
            "never attempted",
            "in processing order",
            "malformed findings excluded",
        )
    )


def _states_receipt_values_come_only_from_summary(prose_norm):
    return (
        "copied from the `file-tasks` summary" in prose_norm
        and "nothing else enters the receipt" in prose_norm
        and "`task_create_failed`" in prose_norm
        and "`task_update_failed`" in prose_norm
        and "no advisory-sourced text" in prose_norm
        and "OS-error message" in prose_norm
        and "recorded in the receipt" in prose_norm
    )


class TestAC3R5ProseNamesFieldsAndDefinesUnattempted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prose = _norm(_receipt_prose(ReviewPhaseFixture.r5()))

    def test_prose_names_every_new_field(self):
        for field in RECEIPT_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.prose)

    def test_prose_states_the_another_round_values(self):
        self.assertIn("`another-round`", self.prose)
        self.assertIn("`executed` is `false`", self.prose)
        self.assertIn("empty/null/0", self.prose)

    def test_prose_defines_unattempted_packages(self):
        self.assertTrue(_defines_unattempted_packages(self.prose))

    def test_prose_states_unattempted_packages_is_empty_when_done_or_report(self):
        self.assertIn("empty when filing completed", self.prose)
        self.assertIn("report branch ran", self.prose)

    def test_prose_still_points_back_at_phase_r4(self):
        self.assertIn('see "Triage filing" above (Phase R4)', self.prose)

    def test_prose_stays_inside_r5(self):
        self.assertIn(
            "The round record also persists the triage-filing receipt",
            ReviewPhaseFixture.r5(),
        )
        self.assertNotIn(
            "The round record also persists the triage-filing receipt",
            ReviewPhaseFixture.r6(),
        )


class TestAC3MatcherCanFail(unittest.TestCase):
    WELL_FORMED = _norm(
        "`unattempted_packages` is the failed package followed by every "
        "later package never attempted, in processing order, with "
        "malformed findings excluded"
    )

    def test_non_vacuity_well_formed_definition_passes(self):
        self.assertTrue(_defines_unattempted_packages(self.WELL_FORMED))

    def test_forged_definition_missing_processing_order_fails(self):
        forged = self.WELL_FORMED.replace("in processing order", "in some order")
        self.assertFalse(_defines_unattempted_packages(forged))

    def test_forged_definition_missing_malformed_exclusion_fails(self):
        forged = self.WELL_FORMED.replace("malformed findings excluded", "")
        self.assertFalse(_defines_unattempted_packages(forged))

    def test_forged_definition_missing_later_packages_fails(self):
        forged = self.WELL_FORMED.replace("every later package", "the failed one")
        self.assertFalse(_defines_unattempted_packages(forged))


class TestAC4R5ProseUntrustedTextStatement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prose = _norm(_receipt_prose(ReviewPhaseFixture.r5()))

    def test_values_are_copied_from_the_summary_and_nothing_else(self):
        self.assertIn("copied from the `file-tasks` summary", self.prose)
        self.assertIn("nothing else enters the receipt", self.prose)

    def test_failure_reason_is_one_of_two_fixed_tokens_or_null(self):
        for token in FAILURE_REASON_TOKENS:
            with self.subTest(token=token):
                self.assertIn(f"`{token}`", self.prose)
        self.assertIn("or null", self.prose)

    def test_no_advisory_text_or_os_error_text_is_recorded(self):
        self.assertIn("no advisory-sourced text", self.prose)
        self.assertIn("OS-error message", self.prose)
        self.assertIn("recorded in the receipt", self.prose)

    def test_such_text_goes_to_stderr_only(self):
        self.assertIn("stderr", self.prose)

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_states_receipt_values_come_only_from_summary(self.prose))


class TestAC4MatcherCanFail(unittest.TestCase):
    WELL_FORMED = _norm(
        "Every receipt value is copied from the `file-tasks` summary and "
        "nothing else enters the receipt; `failure_reason` is "
        "`task_create_failed`, `task_update_failed` or null; no "
        "advisory-sourced text and no OS-error message text is ever "
        "recorded in the receipt."
    )

    def test_non_vacuity_well_formed_statement_passes(self):
        self.assertTrue(
            _states_receipt_values_come_only_from_summary(self.WELL_FORMED)
        )

    def test_forged_statement_missing_the_no_os_error_clause_fails(self):
        forged = self.WELL_FORMED.replace("OS-error message", "")
        self.assertFalse(_states_receipt_values_come_only_from_summary(forged))

    def test_forged_statement_missing_a_token_fails(self):
        forged = self.WELL_FORMED.replace("`task_update_failed`", "")
        self.assertFalse(_states_receipt_values_come_only_from_summary(forged))

    def test_forged_statement_missing_the_summary_source_fails(self):
        forged = self.WELL_FORMED.replace(
            "copied from the `file-tasks` summary", "computed"
        )
        self.assertFalse(_states_receipt_values_come_only_from_summary(forged))


# ---------------------------------------------------------------------------
# AC-5: no automatic retry; remainder-only re-run
# ---------------------------------------------------------------------------


class TestAC5UnattemptedPackagePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.triage = _norm(ReviewPhaseFixture.triage_filing())

    def test_states_there_is_no_automatic_retry(self):
        self.assertIn("no automatic retry", self.triage)

    def test_states_a_rerun_files_only_the_remainder(self):
        self.assertIn("only the remainder", self.triage)
        self.assertIn("duplicate detection", self.triage)

    def test_states_the_rerun_depends_on_the_latest_listing(self):
        self.assertIn("latest listing", self.triage)
        self.assertIn("filed earlier", self.triage)

    def test_policy_is_stated_once_in_the_document(self):
        self.assertEqual(_norm(ReviewPhaseFixture.text()).count("no automatic retry"), 1)

    def test_policy_sits_in_r4_not_r5_or_r6(self):
        self.assertNotIn("no automatic retry", _norm(ReviewPhaseFixture.r5()))
        self.assertNotIn("no automatic retry", _norm(ReviewPhaseFixture.r6()))


# ---------------------------------------------------------------------------
# AC-6: R6 reports "triage filing incomplete"; completion condition unchanged
# ---------------------------------------------------------------------------


class TestAC6R6ReportsIncompleteFiling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r6 = _norm(ReviewPhaseFixture.r6())

    def test_r6_names_the_receipt_field_and_the_non_empty_condition(self):
        self.assertIn("`triage_filing.unattempted_packages`", self.r6)
        self.assertIn("non-empty", self.r6)

    def test_r6_reports_triage_filing_incomplete_with_the_packages(self):
        self.assertIn(f'"{INCOMPLETE_PHRASE}"', self.r6)
        self.assertIn("package", self.r6)

    def test_r6_says_the_same_line_reaches_the_batch_final_result(self):
        self.assertIn("batch final result", self.r6)

    def test_r6_states_disclosure_only_no_gate_effect(self):
        self.assertIn("disclosure only", self.r6)
        self.assertIn("no new gate identifier", self.r6)
        self.assertIn("never affects the completion gate", self.r6)

    def test_review_completion_condition_is_stated_unchanged(self):
        triage = _norm(ReviewPhaseFixture.triage_filing())
        self.assertIn("completion condition does not change", triage)

    def test_r4_r5_and_r6_declare_no_gate_id_line(self):
        for name, text in (
            ("R4", ReviewPhaseFixture.r4()),
            ("R5", ReviewPhaseFixture.r5()),
            ("R6", ReviewPhaseFixture.r6()),
        ):
            with self.subTest(phase=name):
                self.assertNotIn("gate_id:", text)


# ---------------------------------------------------------------------------
# AC-7: standard library only
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

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


# ---------------------------------------------------------------------------
# AC-8: batch-mode.md Reporting item and audit-item source-map row
# ---------------------------------------------------------------------------


def _find_incomplete_rows(rows):
    return [row for row in rows if INCOMPLETE_PHRASE in row[0]]


def _backtick_tokens(cell):
    return re.findall(r"`([^`]+)`", cell)


def _new_source_map_row_is_well_formed(rows):
    """Exactly one row names the incomplete-filing item; it sits immediately
    before the kept-integration-branch row (the last row); its persisted
    source names the round record path and the two receipt fields as its
    only source and cites review-phase.md."""
    found = _find_incomplete_rows(rows)
    if len(found) != 1 or len(rows) < 2:
        return False
    row = found[0]
    if rows[-2] is not row or "kept integration branch name" not in rows[-1][0]:
        return False
    source = row[1]
    if set(_backtick_tokens(source)) != {
        ROUND_RECORD_PATH,
        "triage_filing.unattempted_packages",
        "triage_filing.failed_package",
        REVIEW_PHASE_CITATION,
    }:
        return False
    return not any(p in source.lower() for p in RESTATEMENT_PHRASES)


FORGED_SOURCE_MAP_ROWS = [
    ["Any deferred findings with their stable_ids", "`x` `stable_id`"],
    [
        'Every review round with "triage filing incomplete" (its unattempted packages)',
        "`feature-docs/{feature}/reviews/roundN.yaml` "
        "`triage_filing.unattempted_packages` / "
        "`triage_filing.failed_package` "
        "(`references/review-phase.md`'s triage-filing receipt)",
    ],
    ["The kept integration branch name", "`workflow.yaml` `parent_branch`"],
]


def _forged_rows(**replacements):
    rows = [list(row) for row in FORGED_SOURCE_MAP_ROWS]
    for needle, replacement in replacements.items():
        rows[1][1] = rows[1][1].replace(needle, replacement)
    return rows


class TestAC8ReportingItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = BatchModeFixture.reporting()
        cls.reporting = _norm(cls.raw)

    def test_reporting_carries_exactly_one_incomplete_filing_item(self):
        self.assertEqual(self.reporting.count(INCOMPLETE_PHRASE), 1)

    def test_item_names_the_unattempted_packages(self):
        self.assertIn(INCOMPLETE_PHRASE, self.reporting)
        index = self.reporting.index(INCOMPLETE_PHRASE)
        window = self.reporting[index : index + 160]
        self.assertIn("unattempted packages", window)

    def test_item_is_placed_before_the_kept_integration_branch_item(self):
        self.assertEqual(self.reporting.count(KEPT_BRANCH_PHRASE), 1)
        self.assertIn(INCOMPLETE_PHRASE, self.reporting)
        self.assertLess(
            self.reporting.index(INCOMPLETE_PHRASE),
            self.reporting.index(KEPT_BRANCH_PHRASE),
        )

    def test_item_follows_the_autonomous_route_item(self):
        self.assertIn(INCOMPLETE_PHRASE, self.reporting)
        self.assertLess(
            self.reporting.index("with its reasoning)"),
            self.reporting.index(INCOMPLETE_PHRASE),
        )

    def test_kept_branch_item_is_still_the_last_item(self):
        self.assertLess(
            self.reporting.index(KEPT_BRANCH_PHRASE),
            self.reporting.index("with the take-over guidance"),
        )

    def test_reporting_does_not_restate_the_receipt_definitions(self):
        lowered = self.reporting.lower()
        for phrase in RESTATEMENT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

    def test_reporting_has_no_backtick_quoted_value_key(self):
        self.assertNotIn("unattempted_packages", self.raw)
        self.assertNotIn("failed_package", self.raw)


class TestAC8SourceMapRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quiet = BatchModeFixture.quiet_output()
        cls.rows = _table_rows(cls.quiet)

    def _new_row(self):
        found = _find_incomplete_rows(self.rows)
        self.assertEqual(len(found), 1)
        return found[0]

    def test_exactly_one_row_names_the_incomplete_filing_item(self):
        self.assertEqual(len(_find_incomplete_rows(self.rows)), 1)

    def test_row_sits_immediately_before_the_kept_branch_row(self):
        self.assertIn("kept integration branch name", self.rows[-1][0])
        self.assertIn(INCOMPLETE_PHRASE, self.rows[-2][0])

    def test_row_source_names_the_round_record_and_the_two_fields_only(self):
        source = self._new_row()[1]
        self.assertEqual(
            set(_backtick_tokens(source)),
            {
                ROUND_RECORD_PATH,
                "triage_filing.unattempted_packages",
                "triage_filing.failed_package",
                REVIEW_PHASE_CITATION,
            },
        )

    def test_row_cites_review_phase_md_as_the_receipt_owner(self):
        self.assertIn(REVIEW_PHASE_CITATION, self._new_row()[1])

    def test_row_does_not_restate_the_receipt_definitions(self):
        row = " ".join(self._new_row()).lower()
        for phrase in RESTATEMENT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, row)

    def test_first_cell_uses_the_same_phrase_as_the_reporting_item(self):
        self.assertIn(INCOMPLETE_PHRASE, self._new_row()[0])

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_new_source_map_row_is_well_formed(self.rows))

    def test_source_map_has_eight_rows(self):
        self.assertEqual(len(self.rows), 8)


class TestAC8NoNewStructure(unittest.TestCase):
    def test_gate_id_count_is_unchanged(self):
        self.assertEqual(
            BatchModeFixture.text().count("gate_id"), BATCH_MODE_GATE_ID_COUNT
        )

    def test_level2_heading_list_is_unchanged(self):
        headings = re.findall(r"^## (.+?)\s*$", BatchModeFixture.text(), re.MULTILINE)
        self.assertEqual(headings, BATCH_MODE_LEVEL2_HEADINGS)


class TestAC8MatcherCanFail(unittest.TestCase):
    def test_non_vacuity_well_formed_rows_pass(self):
        self.assertTrue(_new_source_map_row_is_well_formed(_forged_rows()))

    def test_forged_row_missing_the_failed_package_field_fails(self):
        forged = _forged_rows(
            **{" / `triage_filing.failed_package`": ""}
        )
        self.assertFalse(_new_source_map_row_is_well_formed(forged))

    def test_forged_row_missing_the_review_phase_citation_fails(self):
        forged = _forged_rows(**{"`references/review-phase.md`": "review-phase"})
        self.assertFalse(_new_source_map_row_is_well_formed(forged))

    def test_forged_row_with_an_extra_source_fails(self):
        forged = _forged_rows(
            **{"(`references/review-phase.md`": "`workflow.yaml` (`references/review-phase.md`"}
        )
        self.assertFalse(_new_source_map_row_is_well_formed(forged))

    def test_forged_row_restating_a_definition_fails(self):
        forged = _forged_rows(**{"receipt": "receipt in processing order"})
        self.assertFalse(_new_source_map_row_is_well_formed(forged))

    def test_forged_row_after_the_kept_branch_row_fails(self):
        rows = _forged_rows()
        rows[1], rows[2] = rows[2], rows[1]
        self.assertFalse(_new_source_map_row_is_well_formed(rows))

    def test_forged_table_with_the_row_missing_fails(self):
        rows = _forged_rows()
        del rows[1]
        self.assertFalse(_new_source_map_row_is_well_formed(rows))


if __name__ == "__main__":
    unittest.main()
