"""Tests for control-char-abort-stop-reason/task0001: the "Precedence rule:"
paragraph in `em-workflow/references/batch-terminal-line.md` binds the batch
stop raised by the Control-character check of Step I.2.a (in
`references/implement-phase.md`) to the `stop-condition-3` row
(`step_needs_intervention`), not to `unmapped_stop`, as a named exception to
the `stop-condition-3` row's current-run exclusion stated earlier in the same
paragraph.

Covers task0001 Acceptance Criteria
(feature-docs/control-char-abort-stop-reason/tasks/task0001.md):

- AC-1 (FR1, TS-1): the paragraph names the Control-character check of
  Step I.2.a, states the check writes `implement: failed` /
  `failed_kind: decision` in the current run and that control returns
  through develop's stop condition 3, binds the stop to the
  `stop-condition-3` row (`step_needs_intervention`), carries the negated
  `unmapped_stop` binding, and states no affirmative binding to
  `unmapped_stop`.
- AC-2 (FR2, TS-2): the current-run exclusion anchor is still in the
  paragraph; after it comes a named exception to that exclusion, confined to
  this one stop.
- AC-3 (FR3, NFR4, TS-3): this module imports only the standard library,
  reads the document relative to itself, slices the paragraph from its label
  to the next blank line and normalizes whitespace before phrase matching.
  The binding and exception matchers each fail against a verbatim pre-change
  paragraph constant, and a non-vacuity guard proves the constant is that
  paragraph and does not yet name the Control-character check.
- AC-4 (NFR1, NFR3, TS-4): the live paragraph has no blank line and the
  `## Stop point coverage` table has exactly fourteen rows, none for the
  control-character stop. Each guard rejects a forged sample and accepts the
  unforged pre-change text.

AC-5 (the full suite exits 0 with the neighbouring pinned modules
unmodified) and AC-6 (the change set touches only the planned files) are
change-set criteria checked by running the suite and by inspecting the diff;
they are not unit tests.

Test authoring follows this repository's doc-contract convention (see
tests/test_batch_stop_contract.py): read the file relative to the test
module, slice the owned region, normalize whitespace before phrase
matching, assert on distinctive phrases rather than whole sentences, and
give every new matcher a negative proof plus a non-vacuity guard.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"

PRECEDENCE_LABEL = "Precedence rule:"
COVERAGE_HEADING = "## Stop point coverage"

# The exclusion the `stop-condition-3` row already carries (NFR2: it stays
# byte-for-byte). The new exception is worded after it.
EXCLUSION_ANCHOR = (
    "binds a stop at Step B's entry evaluation that reads a `failed` / "
    "`needs_update` status no route of the current run produced"
)

# Phrases only the new text contains. The pre-change paragraph already holds
# `stop-condition-3`, `step_needs_intervention`, "Step I.2.a",
# `implement: failed` / `failed_kind: decision` and the word "exception"
# ("abort terminal-commit exception"), so no matcher keys on any of those
# alone.
CHECK_NAME_PHRASE = (
    "Control-character check of Step I.2.a in `references/implement-phase.md`"
)
WRITE_PHRASE = (
    "In the current run, that check writes `implement: failed` / "
    "`failed_kind: decision`"
)
STOP_CONDITION_PHRASE = "control returns through develop's stop condition 3"
BINDING_PHRASE = "binds to the `stop-condition-3` row, `step_needs_intervention`"
NEGATED_UNMAPPED_PHRASE = "not to `unmapped_stop`"
EXCEPTION_PHRASE = (
    "named exception to the `stop-condition-3` row's current-run exclusion"
)
CONFINEMENT_PHRASE = "covers this one stop only"

UNMAPPED_TOKEN = "`unmapped_stop`"

# Pre-change paragraph, captured verbatim from the base revision
# (`git show HEAD:em-workflow/references/batch-terminal-line.md`, this
# task's starting commit, before its own edit) -- never paraphrased or
# reconstructed. Used as the negative-proof sample of the binding and
# exception matchers, and as the "unforged pre-change text" of the
# blank-line guard.
PRE_CHANGE_PRECEDENCE_PARAGRAPH = (
    "Precedence rule: when a stop matches more than one row above, the\n"
    "phase-specific stop point takes precedence over the generic\n"
    "`stop-condition-N` rows, so exactly one code applies.\n"
    "`implement-second-failure` and `verify-rework-cap` write a step's status\n"
    "`failed`, which is `stop-condition-3`'s own trigger; `docs-commit-conflict`\n"
    "aborts without writing any status, because the failed status write is\n"
    "itself its stop cause. A phase-specific row wins when the current run\n"
    "reaches the stop through that phase's own abort route. This includes\n"
    "`implement-second-failure`, which the same run realizes through its next\n"
    "Step B evaluation when that evaluation reads the `failed` the run wrote.\n"
    "Correspondingly, the `stop-condition-3` row's meaning binds a stop at Step\n"
    "B's entry evaluation that reads a `failed` / `needs_update` status no\n"
    "route of the current run produced — for example, a `failed` left by an\n"
    "earlier run's `implement-second-failure` — and, for the `implement`\n"
    "step's `failed`, further restricted to the cases where `failed_kind`\n"
    "reads `decision`, or where the automatic-resume attempt count has reached\n"
    "its cap per `skills/develop/SKILL.md` (see the `step_needs_intervention`\n"
    "row above). The one such collision: the batch second-failure abort's\n"
    "terminal status commit (Step I.2.c abort-phase terminal status commit)\n"
    "returns exit 4 on its first attempt and exit 4 again on its single\n"
    "exit-4 retry. That stop matches both `implement-second-failure` and\n"
    "`docs-commit-conflict`. The row whose commit failure directly caused the\n"
    "stop wins, and this stop binds to `docs_commit_conflict_aborted`, not to\n"
    "`implement_task_failed`. This stop ends the run: the run never reaches a\n"
    "Step B entry evaluation that reads the uncommitted `implement: failed`,\n"
    "so neither `implement-second-failure` nor `stop-condition-3` applies to\n"
    "that run. A first exit 4 followed by a successful retry instead commits\n"
    "the terminal status write, and that stop keeps `implement_task_failed`.\n"
    "In this collision's case, the terminal status write — the pair\n"
    "`implement: failed` / `failed_kind: decision` — exists in the\n"
    "integration worktree but stays uncommitted and never reaches the\n"
    'branch; this is distinct from "no status written". How that leftover is\n'
    "disposed of and handled by the next run is defined by the abort\n"
    "terminal-commit exception in implement-phase.md's Branch & Worktree\n"
    "Model. This resolution is confined to that one collision: the Step I.1\n"
    "baseline, Step I.2.a launch, Step I.2.b wake and Step I.3 completion\n"
    "exit-4 stops keep their binding to `docs_commit_conflict_aborted` alone."
)

# The `## Stop point coverage` table, captured verbatim from the same base
# revision. The edit does not touch it; the coverage-table guard's invariant
# (fourteen rows, none for the control-character stop) predates the edit.
PRE_CHANGE_COVERAGE_TABLE = (
    "| Stop point | Reason code | Source |\n"
    "|---|---|---|\n"
    "| `stop-condition-2` | `step_stuck` | `skills/develop/SKILL.md` |\n"
    "| `stop-condition-3` | `step_needs_intervention` | `skills/develop/SKILL.md` |\n"
    "| `stop-condition-4` | `workflow_yaml_unparseable` | `skills/develop/SKILL.md` |\n"
    "| `stop-condition-6` | `git_setup_aborted` | `skills/develop/SKILL.md` |\n"
    "| `fail-closed-abort` | `gate_fail_closed` | `references/question-resolution.md` |\n"
    "| `policy-option-unavailable` | `gate_option_unavailable` | `references/batch-policies.yaml` |\n"
    "| `command-refusal` | `gate_fail_closed` | `references/batch-policies.yaml` |\n"
    "| `implement-second-failure` | `implement_task_failed` | `references/implement-phase.md` |\n"
    "| `verify-rework-cap` | `verify_rework_cap_reached` | `skills/develop/SKILL.md` |\n"
    "| `step-c-abort` | `completion_aborted` | `skills/develop/SKILL.md` |\n"
    "| `step-a-abort` | `feature_resolution_aborted` | `skills/develop/SKILL.md` |\n"
    "| `docs-commit-conflict` | `docs_commit_conflict_aborted` | `references/phase-state.md` |\n"
    "| `no-work-required` | `no_work_required` | `skills/develop/SKILL.md` |\n"
    "| `unmapped-terminating-stop` | `unmapped_stop` | `references/batch-terminal-line.md` |\n"
)

EXPECTED_COVERAGE_ROW_COUNT = 14

# Words that would make a coverage row's stop-point key name the
# Control-character check (the check's name is "Control-character check").
CONTROL_CHAR_KEY_MARKERS = ("control", "char")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses whitespace runs (including line wraps) to a single space,
    mirroring tests/test_batch_stop_contract.py's `_normalize` -- a prose
    phrase check must not depend on exactly where the source happens to
    wrap a line."""
    return re.sub(r"\s+", " ", text)


def _extract_precedence_paragraph(text):
    """Slices the "Precedence rule:" paragraph out of the full document
    text, from its label to the next blank line -- the same slicing as
    test_abort_terminal_commit_precedence.py's
    `_extract_precedence_paragraph`. Returns "" when the label is absent, so
    a caller's assertion fails cleanly."""
    idx = text.find(PRECEDENCE_LABEL)
    if idx == -1:
        return ""
    end = text.find("\n\n", idx)
    if end == -1:
        end = len(text)
    return text[idx:end]


def _extract_coverage_section(text):
    """Slices the `## Stop point coverage` section: from its heading to the
    next level-2 heading. Returns "" when the heading is absent."""
    idx = text.find(COVERAGE_HEADING)
    if idx == -1:
        return ""
    end = text.find("\n## ", idx + len(COVERAGE_HEADING))
    if end == -1:
        end = len(text)
    return text[idx:end]


def _coverage_data_rows(section_text):
    """Returns the table's data rows as lists of cell strings. The header
    row and the separator row are not data rows."""
    rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:]


# --- matchers (each gets a negative proof in TestNegativeProofs) -----------


def _assert_binding_stated(test, paragraph):
    """AC-1: the paragraph names the Control-character check, states what
    the check writes and where control returns, binds the stop to
    `stop-condition-3` / `step_needs_intervention`, carries the negated
    `unmapped_stop` binding, and never states an affirmative binding to
    `unmapped_stop`."""
    normalized = _normalize(paragraph)
    test.assertIn(CHECK_NAME_PHRASE, normalized)
    test.assertIn(WRITE_PHRASE, normalized)
    test.assertIn(STOP_CONDITION_PHRASE, normalized)
    test.assertIn(BINDING_PHRASE, normalized)
    test.assertIn(NEGATED_UNMAPPED_PHRASE, normalized)
    # Every mention of `unmapped_stop` must be the negated one: the text
    # immediately before it is "not to ".
    positions = [m.start() for m in re.finditer(re.escape(UNMAPPED_TOKEN), normalized)]
    test.assertTrue(positions, "no `unmapped_stop` mention found")
    for pos in positions:
        test.assertTrue(
            normalized[:pos].endswith("not to "),
            f"affirmative `unmapped_stop` mention at offset {pos}: "
            f"...{normalized[max(0, pos - 40):pos + len(UNMAPPED_TOKEN)]!r}",
        )


def _assert_exception_stated(test, paragraph):
    """AC-2: the full exclusion anchor is present, and after it comes a
    phrase marking the control-character binding as a named exception to
    that exclusion, followed by the confinement to this one stop."""
    normalized = _normalize(paragraph)
    anchor_at = normalized.find(EXCLUSION_ANCHOR)
    test.assertNotEqual(anchor_at, -1, "exclusion anchor not found")
    anchor_end = anchor_at + len(EXCLUSION_ANCHOR)
    exception_at = normalized.find(EXCEPTION_PHRASE, anchor_end)
    test.assertNotEqual(
        exception_at, -1, "named exception not found after the exclusion anchor"
    )
    confinement_at = normalized.find(
        CONFINEMENT_PHRASE, exception_at + len(EXCEPTION_PHRASE)
    )
    test.assertNotEqual(
        confinement_at, -1, "confinement to this one stop not found after the exception"
    )


def _assert_no_blank_line(test, paragraph):
    """AC-4 / NFR1: the paragraph is non-empty and is one blank-line-free
    block. The check reads the RAW paragraph, because whitespace
    normalization would itself collapse a blank line and defeat it."""
    test.assertTrue(paragraph, "no 'Precedence rule:' paragraph found")
    test.assertNotIn("\n\n", paragraph)


def _assert_coverage_table_unchanged(test, section_text):
    """AC-4 / NFR3: the coverage table has exactly fourteen data rows, and
    no row's stop-point key names the control-character check."""
    rows = _coverage_data_rows(section_text)
    test.assertEqual(
        len(rows),
        EXPECTED_COVERAGE_ROW_COUNT,
        f"coverage table has {len(rows)} data rows",
    )
    for cells in rows:
        key = cells[0].lower()
        for marker in CONTROL_CHAR_KEY_MARKERS:
            test.assertNotIn(
                marker, key, f"coverage row key {cells[0]!r} names the control-character stop"
            )


class _LiveDocumentCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.paragraph = _extract_precedence_paragraph(cls.text)
        cls.coverage_section = _extract_coverage_section(cls.text)


class TestDocumentExists(unittest.TestCase):
    def test_document_exists(self):
        self.assertTrue(CONTRACT_PATH.is_file())


class TestBindingStated(_LiveDocumentCase):
    """AC-1."""

    def test_binding_stated(self):
        _assert_binding_stated(self, self.paragraph)


class TestExceptionStated(_LiveDocumentCase):
    """AC-2."""

    def test_exception_stated_after_exclusion_anchor(self):
        _assert_exception_stated(self, self.paragraph)


class TestStructuralGuards(_LiveDocumentCase):
    """AC-4: regression invariants that already held before the edit."""

    def test_paragraph_has_no_blank_line(self):
        _assert_no_blank_line(self, self.paragraph)

    def test_coverage_table_has_fourteen_rows_and_none_for_the_control_char_stop(self):
        self.assertTrue(self.coverage_section, "no '## Stop point coverage' section")
        _assert_coverage_table_unchanged(self, self.coverage_section)


class TestPreChangeSamplesAreTheRealText(unittest.TestCase):
    """Non-vacuity guards (AC-3, AC-4): the captured pre-change samples are
    the real paragraph and the real table, not unrelated or empty strings,
    and they predate the edit."""

    def test_paragraph_begins_with_the_label(self):
        self.assertTrue(PRE_CHANGE_PRECEDENCE_PARAGRAPH.startswith(PRECEDENCE_LABEL))

    def test_paragraph_carries_existing_anchors(self):
        normalized = _normalize(PRE_CHANGE_PRECEDENCE_PARAGRAPH)
        for anchor in (
            "phase-specific stop point takes precedence over the generic",
            "no route of the current run produced",
            "confined to that one collision",
            EXCLUSION_ANCHOR,
        ):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, normalized)

    def test_paragraph_has_no_blank_line(self):
        self.assertNotIn("\n\n", PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_paragraph_does_not_name_the_control_character_check(self):
        normalized = _normalize(PRE_CHANGE_PRECEDENCE_PARAGRAPH)
        self.assertNotIn("Control-character check", normalized)
        self.assertNotIn(UNMAPPED_TOKEN, normalized)

    def test_table_has_header_and_fourteen_data_rows(self):
        self.assertTrue(
            PRE_CHANGE_COVERAGE_TABLE.startswith("| Stop point | Reason code | Source |")
        )
        self.assertEqual(
            len(_coverage_data_rows(PRE_CHANGE_COVERAGE_TABLE)),
            EXPECTED_COVERAGE_ROW_COUNT,
        )

    def test_table_carries_the_stop_condition_3_row(self):
        self.assertIn(
            "| `stop-condition-3` | `step_needs_intervention` |",
            PRE_CHANGE_COVERAGE_TABLE,
        )

    def test_table_matches_the_live_document(self):
        """The edit leaves the table alone, so the captured table is still
        a verbatim block of the live coverage section."""
        live = _extract_coverage_section(_read(CONTRACT_PATH))
        self.assertIn(PRE_CHANGE_COVERAGE_TABLE, live)


class TestNegativeProofs(unittest.TestCase):
    """AC-3, AC-4: each new matcher or guard rejects a sample that lacks
    the statement or breaks the invariant it asserts."""

    def test_binding_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_binding_stated(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_exception_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_exception_stated(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_binding_matcher_rejects_an_affirmative_unmapped_stop_binding(self):
        forged = (
            _live_paragraph_or_skip(self)
            + "\nThis stop also binds to `unmapped_stop`."
        )
        self.assertIn("binds to `unmapped_stop`", _normalize(forged))
        with self.assertRaises(AssertionError):
            _assert_binding_stated(self, forged)

    def test_exception_matcher_rejects_text_that_drops_the_confinement(self):
        # The phrase wraps across a source line break, so the forgery works
        # on the whitespace-normalized text.
        forged = _normalize(_live_paragraph_or_skip(self))
        self.assertIn(CONFINEMENT_PHRASE, forged)
        forged = forged.replace(CONFINEMENT_PHRASE, "covers it")
        self.assertNotIn(CONFINEMENT_PHRASE, forged)
        with self.assertRaises(AssertionError):
            _assert_exception_stated(self, forged)

    def test_exception_matcher_rejects_an_exception_placed_before_the_anchor(self):
        """The exception must come after the exclusion it is an exception
        to: a paragraph whose only exception phrase precedes the anchor is
        rejected."""
        live = _live_paragraph_or_skip(self)
        exception_at = _normalize(live).find(EXCEPTION_PHRASE)
        self.assertNotEqual(exception_at, -1)
        forged = (
            f"{EXCEPTION_PHRASE} {CONFINEMENT_PHRASE}. "
            + PRE_CHANGE_PRECEDENCE_PARAGRAPH
        )
        with self.assertRaises(AssertionError):
            _assert_exception_stated(self, forged)

    def test_blank_line_guard_rejects_a_paragraph_with_a_blank_line_inserted(self):
        live = _extract_precedence_paragraph(_read(CONTRACT_PATH))
        self.assertTrue(live)
        forged = live.replace("\n", "\n\n", 1)
        self.assertIn("\n\n", forged)
        with self.assertRaises(AssertionError):
            _assert_no_blank_line(self, forged)

    def test_blank_line_guard_rejects_an_empty_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_no_blank_line(self, "")

    def test_blank_line_guard_accepts_the_unforged_pre_change_paragraph(self):
        _assert_no_blank_line(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_table_guard_rejects_a_table_with_a_control_char_row_added(self):
        forged = PRE_CHANGE_COVERAGE_TABLE + (
            "| `control-character-check` | `step_needs_intervention` | "
            "`references/implement-phase.md` |\n"
        )
        self.assertEqual(
            len(_coverage_data_rows(forged)), EXPECTED_COVERAGE_ROW_COUNT + 1
        )
        with self.assertRaises(AssertionError):
            _assert_coverage_table_unchanged(self, forged)

    def test_table_guard_rejects_a_control_char_key_even_at_fourteen_rows(self):
        forged = PRE_CHANGE_COVERAGE_TABLE.replace(
            "`unmapped-terminating-stop`", "`control-character-check`"
        )
        self.assertNotEqual(forged, PRE_CHANGE_COVERAGE_TABLE)
        self.assertEqual(len(_coverage_data_rows(forged)), EXPECTED_COVERAGE_ROW_COUNT)
        with self.assertRaises(AssertionError):
            _assert_coverage_table_unchanged(self, forged)

    def test_table_guard_rejects_a_table_with_a_row_removed(self):
        forged = PRE_CHANGE_COVERAGE_TABLE.replace(
            "| `step-c-abort` | `completion_aborted` | `skills/develop/SKILL.md` |\n", ""
        )
        self.assertNotEqual(forged, PRE_CHANGE_COVERAGE_TABLE)
        with self.assertRaises(AssertionError):
            _assert_coverage_table_unchanged(self, forged)

    def test_table_guard_accepts_the_unforged_pre_change_table(self):
        _assert_coverage_table_unchanged(self, PRE_CHANGE_COVERAGE_TABLE)


def _live_paragraph_or_skip(test):
    """The live paragraph, used as the base of a forged sample. A forged
    sample derived from the live text only proves a matcher non-vacuous
    when the live text carries the statement; when it does not, the
    dedicated live-document tests above already fail, so the derived proof
    is skipped rather than reported twice."""
    paragraph = _extract_precedence_paragraph(_read(CONTRACT_PATH))
    if EXCEPTION_PHRASE not in _normalize(paragraph):
        test.skipTest("live paragraph does not carry the new statement yet")
    return paragraph


class TestModuleHygiene(unittest.TestCase):
    """AC-3: the module imports nothing outside the Python standard library
    and locates the document relative to its own file."""

    def test_imports_only_the_standard_library(self):
        tree = ast.parse(_read(Path(__file__)))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import")
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertLessEqual(imported, set(sys.stdlib_module_names))

    def test_document_path_is_relative_to_this_module(self):
        module_dir = Path(__file__).resolve().parent
        self.assertEqual(REPO_ROOT, module_dir.parent)
        self.assertEqual(
            CONTRACT_PATH,
            module_dir.parent / "em-workflow" / "references" / "batch-terminal-line.md",
        )


if __name__ == "__main__":
    unittest.main()
