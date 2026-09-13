"""Tests for task0003 (codex-wrapper-fallback-removal): the batch reporting
list in `em-workflow/references/batch-mode.md` and the audit-record
obligation in `em-workflow/references/phase-state.md` stop asking whether a
run recorded that a fallback provider answered, while every surrounding
clause of the same list, the orchestrator's Phase R2b chain walk and its
`rate_limited` / `budget_exhausted` / `harness_unavailable` routing table
(`em-workflow/references/review-phase.md`), and the superseded
`batch-codex-autonomous-decisions` feature's SPEC.md all stay exactly as
they are.

Covers task0003 Acceptance Criteria
(feature-docs/codex-wrapper-fallback-removal/tasks/task0003.md):

- AC-1 (FR7): neither owned document states that a run records whether a
  fallback provider answered, checked within the section that carried the
  clause in each file.
- AC-2 (FR7): every surviving clause of the same list is individually
  present in both documents; the reporting list's item count and the
  audit-item source map row count are unchanged.
- AC-3 (FR7): delegated to `tests/test_batch_quiet_output_discipline.py` and
  `tests/test_batch_quiet_output_audit_record_contract.py` -- both updated
  to the post-edit wording in the same commit as this module, with no
  assertion silently deleted.
- AC-4 (FR7, preservation): the chain-walk description and the
  `rate_limited` / `budget_exhausted` / `harness_unavailable` routing table
  in `review-phase.md` are unchanged, asserted positively here.
- AC-5 (FR8): `feature-docs/batch-codex-autonomous-decisions/SPEC.md` is not
  modified by this task -- its FR13 / FR14 requirement entries and its TS-7
  / TS-8 / TS-11 test-scenario entries are still present, and it contains no
  reference to this feature's name.
- AC-6 (NFR4): neither owned document names a provider or model, and
  neither describes usage-limit detection.
- AC-7 (NFR5): delegated to the whole-suite run
  (`python3 -m unittest discover -s tests`); this module itself imports the
  standard library only.

Test authoring follows
`tests/test_batch_quiet_output_audit_record_contract.py`'s form: standard
library only, no import from another test module, every constant
re-declared locally.

Matcher -> negative-proof inventory (every NEW matcher carries a negative
proof over a forged sample plus a non-vacuity guard):

- `_assert_clause_absent` (removed-clause matcher): negative proof
  `test_forged_section_with_clause_is_rejected`; non-vacuity guard
  `test_forged_section_with_clause_is_well_formed`; edge-case guard
  `test_bare_word_fallback_does_not_trigger_false_positive` (Test Notes:
  the bare word "fallback" survives legitimately elsewhere in both
  documents, so the matcher must key on the full clause, never the word).
- `_assert_clauses_present` (surviving-clauses matcher): negative proof
  `test_missing_sibling_is_rejected`; non-vacuity guard
  `test_forged_missing_sibling_is_well_formed_otherwise`.
- `_assert_routing_table_and_chain_walk_present` (chain-walk / routing-table
  matcher): negative proof `test_missing_row_is_rejected`; non-vacuity guard
  `test_forged_missing_row_is_well_formed_otherwise`.
- `_assert_superseded_spec_untouched` (superseded-SPEC matcher): negative
  proofs `test_forged_mention_of_feature_name_is_rejected` and
  `test_forged_missing_entry_is_rejected`; non-vacuity guard
  `test_forged_mention_is_well_formed_otherwise`.
- `_assert_no_provider_or_usage_limit_language` (NFR4 matcher): negative
  proof `test_forged_doc_with_provider_name_is_rejected`; non-vacuity
  guards `test_forged_doc_with_provider_name_is_well_formed_otherwise` and
  `test_forged_clean_doc_is_accepted`.

TDD-awkward (Test Notes): AC-2 and AC-4 are preservation criteria that pass
trivially before either document is edited; their value is as regression
guards for the edit itself. AC-1's two real-document tests
(`TestAC1RemovedClauseAbsentFromOwnedDocs`) are the ones confirmed red
before either document is edited -- that red state is what proves the
section-scoped absence check actually reaches the clause.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
SUPERSEDED_SPEC_PATH = (
    REPO_ROOT / "feature-docs" / "batch-codex-autonomous-decisions" / "SPEC.md"
)

FEATURE_NAME = "codex-wrapper-fallback-removal"
REMOVED_CLAUSE = "whether a fallback provider answered"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses all whitespace runs (including line wraps) to a single
    space, matching the repository's existing doc-pinning tests'
    convention, so a multi-word prose phrase check does not depend on
    exactly where the source file happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def _sections(text):
    """Splits `text` into a dict keyed by level-2 heading text (without the
    leading `## `), each value the body up to the next level-2 heading (or
    end of text)."""
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


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


# ---------------------------------------------------------------------------
# Matcher: removed-clause absence (AC-1)
# ---------------------------------------------------------------------------


def _assert_clause_absent(test, section_text, clause):
    test.assertNotIn(clause, _normalize(section_text))


FORGED_SECTION_WITH_REMOVED_CLAUSE = (
    "every autonomous fail-closed-route resolution (gate / option chosen / "
    "options not chosen / the discussion's key points / whether Codex was "
    "consulted / whether a fallback provider answered / whether the Opus "
    "escalation ran, with its reasoning), and the kept integration branch "
    "name"
)

FORGED_SECTION_BARE_WORD_ONLY = (
    "every unlisted-gate fallback resolution (gate / options / choice / "
    "Codex consulted or not), every autonomous fail-closed-route resolution "
    "(gate / option chosen / options not chosen / the discussion's key "
    "points / whether Codex was consulted / whether the Opus escalation "
    "ran, with its reasoning), and the kept integration branch name"
)


class TestClauseAbsentMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_assert_clause_absent`, plus
    the bare-word edge case (Test Notes)."""

    def test_forged_section_with_clause_is_well_formed(self):
        self.assertIn(REMOVED_CLAUSE, FORGED_SECTION_WITH_REMOVED_CLAUSE)

    def test_forged_section_with_clause_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_clause_absent(
                self, FORGED_SECTION_WITH_REMOVED_CLAUSE, REMOVED_CLAUSE
            )

    def test_bare_word_fallback_does_not_trigger_false_positive(self):
        self.assertIn("fallback", FORGED_SECTION_BARE_WORD_ONLY)
        self.assertNotIn(REMOVED_CLAUSE, FORGED_SECTION_BARE_WORD_ONLY)
        _assert_clause_absent(self, FORGED_SECTION_BARE_WORD_ONLY, REMOVED_CLAUSE)


# ---------------------------------------------------------------------------
# AC-1: the removed clause is absent from the section that carried it
# ---------------------------------------------------------------------------


class TestAC1RemovedClauseAbsentFromOwnedDocs(unittest.TestCase):
    def test_batch_mode_reporting_section_lacks_removed_clause(self):
        section = _sections(_read(BATCH_MODE_PATH))["Reporting"]
        _assert_clause_absent(self, section, REMOVED_CLAUSE)

    def test_phase_state_batch_audit_section_lacks_removed_clause(self):
        section = _slice(
            _read(PHASE_STATE_PATH),
            "## Batch audit record file",
            "## Legacy feature compatibility",
        )
        _assert_clause_absent(self, section, REMOVED_CLAUSE)


# ---------------------------------------------------------------------------
# Matcher: surviving clauses present (AC-2)
# ---------------------------------------------------------------------------


def _assert_clauses_present(test, section_text, clauses):
    normalized = _normalize(section_text)
    for clause in clauses:
        test.assertIn(
            clause, normalized, f"expected surviving clause {clause!r} to remain"
        )


BATCH_MODE_SURVIVING_CLAUSES = (
    "option chosen",
    "options not chosen",
    "the discussion's key points",
    "whether Codex was consulted",
    "whether the Opus escalation ran",
)

PHASE_STATE_SURVIVING_CLAUSES = (
    "the gate",
    "the option chosen",
    "the options not chosen",
    "the discussion's key points",
    "whether Codex was consulted",
    "whether the Opus escalation ran",
)

FORGED_MISSING_ONE_SIBLING = (
    "every autonomous fail-closed-route resolution (gate / option chosen / "
    "the discussion's key points / whether Codex was consulted / whether "
    "the Opus escalation ran, with its reasoning), and the kept integration "
    "branch name"
)  # "options not chosen" dropped


class TestClausesPresentMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_assert_clauses_present`."""

    def test_forged_missing_sibling_is_well_formed_otherwise(self):
        self.assertIn("option chosen", FORGED_MISSING_ONE_SIBLING)
        self.assertIn("whether Codex was consulted", FORGED_MISSING_ONE_SIBLING)
        self.assertNotIn("options not chosen", FORGED_MISSING_ONE_SIBLING)

    def test_missing_sibling_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_clauses_present(
                self, FORGED_MISSING_ONE_SIBLING, BATCH_MODE_SURVIVING_CLAUSES
            )


# ---------------------------------------------------------------------------
# AC-2: surviving clauses present; item count / source map row count intact
# ---------------------------------------------------------------------------


class TestAC2SurvivingClausesAndCountsUnchanged(unittest.TestCase):
    def test_batch_mode_surviving_clauses_each_present(self):
        section = _sections(_read(BATCH_MODE_PATH))["Reporting"]
        _assert_clauses_present(self, section, BATCH_MODE_SURVIVING_CLAUSES)

    def test_phase_state_surviving_clauses_each_present(self):
        section = _slice(
            _read(PHASE_STATE_PATH),
            "## Batch audit record file",
            "## Legacy feature compatibility",
        )
        _assert_clauses_present(self, section, PHASE_STATE_SURVIVING_CLAUSES)

    def test_reporting_list_still_ends_the_same_way_once(self):
        section = _sections(_read(BATCH_MODE_PATH))["Reporting"]
        self.assertEqual(
            section.count("and the kept integration branch name"), 1
        )

    def test_batch_quiet_output_source_map_still_has_seven_rows(self):
        section = _sections(_read(BATCH_MODE_PATH))["Batch quiet output"]
        self.assertEqual(len(_table_rows(section)), 7)


# ---------------------------------------------------------------------------
# Matcher: chain-walk description + routing table present (AC-4)
# ---------------------------------------------------------------------------

CHAIN_WALK_HEADING = "Phase R2b: Cross-model fallback (chain walk)"

ROUTING_TABLE_ROWS = (
    ("rate_limited", "the next entry in the chain"),
    ("budget_exhausted", "the next entry of a **different** harness"),
    ("harness_unavailable", "the next entry of a **different** harness"),
)


def _assert_routing_table_and_chain_walk_present(test, review_phase_text):
    test.assertIn(f"## {CHAIN_WALK_HEADING}", review_phase_text)
    sections = _sections(review_phase_text)
    test.assertIn(CHAIN_WALK_HEADING, sections)
    section = sections[CHAIN_WALK_HEADING]
    rows = _table_rows(section)
    keys = {row[0].strip("`") for row in rows}
    normalized_section = _normalize(section)
    for skip_reason, advance_to in ROUTING_TABLE_ROWS:
        test.assertIn(skip_reason, keys, f"routing table missing {skip_reason!r} row")
        test.assertIn(
            advance_to,
            normalized_section,
            f"routing table row for {skip_reason!r} changed wording",
        )


FORGED_REVIEW_PHASE_MISSING_ROW = (
    "## Phase R2b: Cross-model fallback (chain walk)\n\n"
    "| `skip_reason` | What it means | Advance to |\n"
    "|---|---|---|\n"
    "| `rate_limited` | upstream congestion | the next entry in the chain |\n"
    "| `harness_unavailable` | harness unreachable | the next entry of a "
    "**different** harness |\n"
)


class TestRoutingTableMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_assert_routing_table_and_chain_walk_present`."""

    def test_forged_missing_row_is_well_formed_otherwise(self):
        self.assertIn(
            f"## {CHAIN_WALK_HEADING}", FORGED_REVIEW_PHASE_MISSING_ROW
        )
        self.assertIn("`rate_limited`", FORGED_REVIEW_PHASE_MISSING_ROW)
        self.assertNotIn("`budget_exhausted`", FORGED_REVIEW_PHASE_MISSING_ROW)

    def test_missing_row_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_routing_table_and_chain_walk_present(
                self, FORGED_REVIEW_PHASE_MISSING_ROW
            )


# ---------------------------------------------------------------------------
# AC-4: review-phase.md's chain walk + routing table, unchanged
# ---------------------------------------------------------------------------


class TestAC4ChainWalkAndRoutingTableUnchanged(unittest.TestCase):
    def test_review_phase_chain_walk_and_routing_table_present(self):
        _assert_routing_table_and_chain_walk_present(self, _read(REVIEW_PHASE_PATH))


# ---------------------------------------------------------------------------
# Matcher: superseded SPEC untouched (AC-5)
# ---------------------------------------------------------------------------

FR13_SNIPPET = "**FR13 — Provider fallback chain inside the wrapper:**"
FR14_SNIPPET = "**FR14 — Audit record for every autonomous resolution:**"
TS7_SNIPPET = "TS-7 (FR16, FR14): batch-mode.md's `## Reporting` list"
TS8_SNIPPET = "TS-8 (FR15, FR14): phase-state.md's batch audit record writers list"
TS11_SNIPPET = (
    "TS-11 (FR13, NFR4): the wrapper script falls through to the second provider"
)


def _assert_superseded_spec_untouched(test, spec_text, feature_name):
    normalized = _normalize(spec_text)
    for snippet in (FR13_SNIPPET, FR14_SNIPPET, TS7_SNIPPET, TS8_SNIPPET, TS11_SNIPPET):
        test.assertIn(snippet, normalized, f"superseded SPEC lost {snippet!r}")
    test.assertNotIn(feature_name, spec_text)


FORGED_SPEC_MENTIONING_FEATURE = (
    "**FR13 — Provider fallback chain inside the wrapper:** superseded by "
    "codex-wrapper-fallback-removal."
)

FORGED_SPEC_MISSING_ENTRY = "Only FR14 survives here; FR13 was deleted."


class TestSupersededSpecMatcherNegativeProof(unittest.TestCase):
    """Negative proofs + non-vacuity guard for
    `_assert_superseded_spec_untouched`."""

    def test_forged_mention_is_well_formed_otherwise(self):
        self.assertIn(FR13_SNIPPET, FORGED_SPEC_MENTIONING_FEATURE)
        self.assertIn(FEATURE_NAME, FORGED_SPEC_MENTIONING_FEATURE)

    def test_forged_mention_of_feature_name_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_superseded_spec_untouched(
                self, FORGED_SPEC_MENTIONING_FEATURE, FEATURE_NAME
            )

    def test_forged_missing_entry_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_superseded_spec_untouched(
                self, FORGED_SPEC_MISSING_ENTRY, FEATURE_NAME
            )


# ---------------------------------------------------------------------------
# AC-5: the superseded SPEC keeps its entries and names no feature
# ---------------------------------------------------------------------------


class TestAC5SupersededSpecUntouched(unittest.TestCase):
    def test_superseded_spec_keeps_its_entries_and_names_no_feature(self):
        _assert_superseded_spec_untouched(
            self, _read(SUPERSEDED_SPEC_PATH), FEATURE_NAME
        )


# ---------------------------------------------------------------------------
# Matcher: no provider/model naming, no usage-limit description (AC-6)
# ---------------------------------------------------------------------------

FORBIDDEN_PROVIDER_TOKENS = ("GPT", "Vertex", "Muse", "GLM")
FORBIDDEN_USAGE_LIMIT_PHRASES = ("usage-limit", "usage limit")


def _assert_no_provider_or_usage_limit_language(test, doc_text):
    lowered = doc_text.lower()
    for token in FORBIDDEN_PROVIDER_TOKENS:
        test.assertNotIn(
            token.lower(), lowered, f"document names provider/model token {token!r}"
        )
    for phrase in FORBIDDEN_USAGE_LIMIT_PHRASES:
        test.assertNotIn(
            phrase, lowered, f"document describes usage-limit detection ({phrase!r})"
        )


FORGED_DOC_WITH_PROVIDER_NAME = (
    "The wrapper may answer via GPT or fall through to Vertex AI on a "
    "usage-limit response."
)

FORGED_DOC_CLEAN = (
    "The wrapper launches Codex exec once; the Opus escalation runs when "
    "the consultation route needs one."
)


class TestNoProviderLanguageMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guards for
    `_assert_no_provider_or_usage_limit_language`."""

    def test_forged_doc_with_provider_name_is_well_formed_otherwise(self):
        self.assertIn("GPT", FORGED_DOC_WITH_PROVIDER_NAME)
        self.assertIn("usage-limit", FORGED_DOC_WITH_PROVIDER_NAME)

    def test_forged_doc_with_provider_name_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_no_provider_or_usage_limit_language(
                self, FORGED_DOC_WITH_PROVIDER_NAME
            )

    def test_forged_clean_doc_is_accepted(self):
        _assert_no_provider_or_usage_limit_language(self, FORGED_DOC_CLEAN)


# ---------------------------------------------------------------------------
# AC-6: neither owned document names a provider/model or describes
# usage-limit detection
# ---------------------------------------------------------------------------


class TestAC6NoProviderOrUsageLimitLanguage(unittest.TestCase):
    def test_batch_mode_has_no_provider_or_usage_limit_language(self):
        _assert_no_provider_or_usage_limit_language(self, _read(BATCH_MODE_PATH))

    def test_phase_state_has_no_provider_or_usage_limit_language(self):
        _assert_no_provider_or_usage_limit_language(self, _read(PHASE_STATE_PATH))


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_all_referenced_documents_exist(self):
        for path in (
            BATCH_MODE_PATH,
            PHASE_STATE_PATH,
            REVIEW_PHASE_PATH,
            SUPERSEDED_SPEC_PATH,
        ):
            self.assertTrue(path.is_file(), f"expected {path} to exist")


if __name__ == "__main__":
    unittest.main()
