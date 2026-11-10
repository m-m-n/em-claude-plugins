"""Tests for task0004 (muse-guard-deny-recovery): em-review's Phase R2b routes
a `contributor_consent_missing` skip to the next chain entry and states how
that hop relates to consent and the chain.

Covers the task0004 Acceptance Criteria
(feature-docs/muse-guard-deny-recovery/tasks/task0004.md):

- AC-1 (FR5): the Phase R2b routing table of
  em-review/references/review-phase.md has exactly four data rows. The first
  three are the pre-existing rows, byte-identical; the fourth is the
  `contributor_consent_missing` row advancing to `the next entry in the
  chain`. Table lines are compared exactly.
- AC-2 (FR5, TM-4): the Phase R2b section, after the table, states that
  consent is a property of the contributor tier and not of the harness so
  the walk may advance within the same harness; that the walk resumes from
  the entry after the recorded chain index and never re-dispatches the same
  entry as plain `muse-spark`; that Phase R0's `contributor_consented` is
  not re-judged and the chain is not edited; and that the hop counts against
  the existing 2-hop budget. Prose is compared on whitespace-normalized text.
- AC-3 (NFR3, NFR4): the document contains no `shard` and no `dispatch cap`,
  and keeps `**At most 2 fallback dispatches per perspective**` and the
  chain-exhaustion rule verbatim.
- AC-4 (FR9): each matcher rejects the forged texts built below (new row
  removed, an old row changed, the new row advancing to a different harness,
  one note point dropped) and passes on the real text.

Standard library only. The Phase R2b section is sliced from its heading to
the next phase heading.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_PHASE_PATH = REPO_ROOT / "em-review" / "references" / "review-phase.md"

R2B_HEADING = "## Phase R2b: Cross-model fallback (chain walk)"
PHASE_HEADING_PREFIX = "## Phase "

# The routing table, line by line, exactly as the document carries it.
TABLE_HEADER = "| `skip_reason` | What it means | Advance to |"
TABLE_SEPARATOR = "|---|---|---|"
OLD_ROWS = (
    "| `rate_limited` | upstream congestion (Codex rate limit, Vertex 429) "
    "| the next entry in the chain |",
    "| `budget_exhausted` | the harness's own budget is spent (LiteLLM's "
    "monthly virtual-key cap) | the next entry of a **different** harness |",
    "| `harness_unavailable` | the harness could not be reached at all (proxy "
    "down, profile broken, wrapper missing) | the next entry of a "
    "**different** harness |",
)
NEW_ROW = (
    "| `contributor_consent_missing` | muse_guard denied the contributor tier "
    "because the repository has no recorded consent | the next entry in the "
    "chain |"
)
EXPECTED_TABLE_LINES = (TABLE_HEADER, TABLE_SEPARATOR, *OLD_ROWS, NEW_ROW)

# The four points of the note on the new row (AC-2), each as the phrases that
# carry it. Matched case-sensitively on whitespace-normalized text.
NOTE_POINTS = {
    "consent is a property of the tier, not the harness": (
        "consent is a property of the contributor tier, not of the harness",
        "so the walk may advance within the same harness",
    ),
    "resume after the recorded index, never plain muse-spark": (
        "The walk resumes from the entry after the recorded chain index",
        "never re-dispatches the same entry as plain `muse-spark`",
    ),
    "R0 consent not re-judged, chain not edited": (
        "Phase R0's `contributor_consented` is not re-judged",
        "the chain is not edited",
    ),
    "the hop counts against the existing 2-hop budget": (
        "The hop counts against the existing 2-hop budget",
    ),
}
NOTE_PHRASES = tuple(
    phrase for phrases in NOTE_POINTS.values() for phrase in phrases
)

BUDGET_RULE = "**At most 2 fallback dispatches per perspective**"
EXHAUSTION_RULE = (
    "the perspective keeps its last skip result and the Claude reviewer "
    "stands alone"
)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _read_document():
    return REVIEW_PHASE_PATH.read_text(encoding="utf-8")


def _r2b_section(text):
    """The Phase R2b section: its heading to the next phase heading (or the
    end of the text)."""
    start = text.find(R2B_HEADING)
    if start == -1:
        return ""
    body_start = start + len(R2B_HEADING)
    following = text.find("\n" + PHASE_HEADING_PREFIX, body_start)
    return text[start:] if following == -1 else text[start : following + 1]


def _table_line_indices(section):
    lines = section.splitlines()
    return lines, [i for i, line in enumerate(lines) if line.startswith("|")]


def table_matches(section):
    """AC-1: the section holds one contiguous table whose lines are exactly
    the header, the separator, the three old rows and the new row."""
    lines, indices = _table_line_indices(section)
    if not indices:
        return False
    if indices != list(range(indices[0], indices[0] + len(indices))):
        return False
    return tuple(lines[i] for i in indices) == EXPECTED_TABLE_LINES


def note_matches(section):
    """AC-2: every phrase of the four note points is present, after the
    table, on the whitespace-normalized section, and the note names the
    new reason."""
    norm = _norm(section)
    table_end = norm.find(_norm(NEW_ROW))
    if table_end == -1:
        return False
    after_table = norm[table_end + len(_norm(NEW_ROW)) :]
    if "`contributor_consent_missing`" not in after_table:
        return False
    return all(phrase in after_table for phrase in NOTE_PHRASES)


def _forge(text, old, new):
    """Replace `old` with `new` once; the replacement must hit, so a forged
    text never silently equals the real one."""
    if old not in text:
        raise AssertionError(f"forge anchor not found: {old!r}")
    return text.replace(old, new, 1)


class RealDocumentCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = _read_document()
        cls.section = _r2b_section(cls.document)


class TestAC1RoutingTable(RealDocumentCase):
    def test_r2b_section_is_found(self):
        self.assertTrue(self.section.startswith(R2B_HEADING))

    def test_table_has_exactly_four_data_rows(self):
        _, indices = _table_line_indices(self.section)
        # header + separator + four data rows
        self.assertEqual(len(indices), 6)

    def test_old_rows_are_byte_identical_and_new_row_is_last(self):
        lines, indices = _table_line_indices(self.section)
        rows = [lines[i] for i in indices]
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], TABLE_HEADER)
        self.assertEqual(rows[1], TABLE_SEPARATOR)
        self.assertEqual(tuple(rows[2:5]), OLD_ROWS)
        self.assertEqual(rows[5], NEW_ROW)

    def test_table_matcher_passes_on_real_text(self):
        self.assertTrue(table_matches(self.section))

    def test_last_row_of_the_document_advances_to_the_next_entry_in_the_chain(self):
        lines, indices = _table_line_indices(self.section)
        cells = [c.strip() for c in lines[indices[-1]].strip().strip("|").split("|")]
        self.assertEqual(cells[0], "`contributor_consent_missing`")
        self.assertEqual(cells[2], "the next entry in the chain")


class TestAC2Note(RealDocumentCase):
    def test_note_matcher_passes_on_real_text(self):
        self.assertTrue(note_matches(self.section))

    def test_each_note_point_is_stated(self):
        norm = _norm(self.section)
        for point, phrases in NOTE_POINTS.items():
            for phrase in phrases:
                with self.subTest(point=point, phrase=phrase):
                    self.assertIn(phrase, norm)

    def test_note_sits_after_the_table(self):
        norm = _norm(self.section)
        row_end = norm.find(_norm(NEW_ROW)) + len(_norm(NEW_ROW))
        for phrase in NOTE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertGreater(norm.find(phrase), row_end)


class TestAC3WordingConstraints(RealDocumentCase):
    def test_no_shard_and_no_dispatch_cap_anywhere_in_the_file(self):
        lowered = self.document.lower()
        self.assertNotIn("shard", lowered)
        self.assertIsNone(re.search(r"dispatch[\s-]+cap", lowered))

    def test_budget_rule_stays_verbatim(self):
        self.assertIn(BUDGET_RULE, self.section)

    def test_exhaustion_rule_is_unchanged(self):
        self.assertIn(EXHAUSTION_RULE, _norm(self.section))


class TestAC4MatchersRejectForgedTexts(RealDocumentCase):
    def test_table_matcher_rejects_three_row_table(self):
        forged = _forge(self.section, NEW_ROW + "\n", "")
        self.assertFalse(table_matches(forged))

    def test_table_matcher_rejects_changed_old_row(self):
        for old_row in OLD_ROWS:
            with self.subTest(row=old_row):
                forged_row = old_row.replace("the next entry", "the first entry", 1)
                self.assertNotEqual(forged_row, old_row)
                forged = _forge(self.section, old_row, forged_row)
                self.assertFalse(table_matches(forged))

    def test_table_matcher_rejects_new_row_advancing_to_a_different_harness(self):
        forged_row = NEW_ROW.replace(
            "the next entry in the chain",
            "the next entry of a **different** harness",
        )
        self.assertNotEqual(forged_row, NEW_ROW)
        forged = _forge(self.section, NEW_ROW, forged_row)
        self.assertFalse(table_matches(forged))

    def test_table_matcher_rejects_new_row_not_last(self):
        forged = _forge(self.section, NEW_ROW + "\n", "")
        forged = _forge(forged, OLD_ROWS[0] + "\n", NEW_ROW + "\n" + OLD_ROWS[0] + "\n")
        self.assertFalse(table_matches(forged))

    def test_table_matcher_rejects_fifth_row(self):
        extra = "| `unknown_reason` | something else | the next entry in the chain |"
        forged = _forge(self.section, NEW_ROW, NEW_ROW + "\n" + extra)
        self.assertFalse(table_matches(forged))

    def test_note_matcher_rejects_each_dropped_point_phrase(self):
        norm = _norm(self.section)
        for phrase in NOTE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, norm)
                forged = norm.replace(phrase, "")
                self.assertNotEqual(forged, norm)
                self.assertFalse(note_matches(forged))

    def test_note_matcher_rejects_note_placed_before_the_table(self):
        lines, indices = _table_line_indices(self.section)
        table_lines = [lines[i] for i in indices]
        rest = [line for i, line in enumerate(lines) if i not in set(indices)]
        forged = "\n".join(rest + [""] + table_lines) + "\n"
        # Only the order is forged: the table itself is still intact.
        self.assertTrue(table_matches(forged))
        self.assertFalse(note_matches(forged))

    def test_forged_texts_are_well_formed_otherwise(self):
        # Non-vacuity: a forged section still carries the heading, the
        # header line and the old rows, so a rejection is caused by the
        # forged part and not by a broken fixture.
        forged = _forge(self.section, NEW_ROW + "\n", "")
        self.assertTrue(forged.startswith(R2B_HEADING))
        self.assertIn(TABLE_HEADER, forged)
        for row in OLD_ROWS:
            self.assertIn(row, forged)
        self.assertNotEqual(forged, self.section)

    def test_matchers_pass_on_real_text(self):
        self.assertTrue(table_matches(self.section))
        self.assertTrue(note_matches(self.section))


if __name__ == "__main__":
    unittest.main()
