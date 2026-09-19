"""Tests for task0001 (batch-quiet-output): the output-suppression
discipline SSOT section in `batch-mode.md`, and the one non-normative
cross-reference sentence added to `batch-terminal-line.md`.

Covers task0001 Acceptance Criteria
(feature-docs/batch-quiet-output/tasks/task0001.md):

- AC-1 (FR12, NFR4): `batch-mode.md` carries exactly one new level-2
  section defining the discipline, positioned after `## Reporting` as the
  document's last level-2 section; `## Terminal line` and `## Reporting`
  keep their headings and relative order; the Non-packet gates table still
  has exactly ten data rows with its catch-all wording intact.
- AC-2 (FR1, NFR1): the section states the discipline is active exactly
  when the current invocation's arguments contain `--batch`, that the
  workflow.yaml `batch` block never activates it, and that an interactive
  launch's output is unchanged.
- AC-3 (FR4, FR9, FR10): the section names all eight suppressed output
  kinds, each individually assertable, and states suppression targets
  main-context assistant text only.
- AC-4 (FR2, FR3, NFR2): the section defines the marker line exactly as
  IMPLEMENTATION.md D1 fixes it, names the three non-terminal turns in
  scope, and states the non-collision property by naming
  `references/batch-terminal-line.md` -- with that document's prefix
  literal, its eleven reason codes, its `no-step` sentinel, its four field
  names as a group, any `state={value}` shape and the bare `phase_done`
  literal all still absent from the whole file.
- AC-5 (FR5, FR6, FR8, NFR3): the section states the three exceptions; the
  stop/abort exception is a set-level rule referring to the terminal-line
  contract's stop-point coverage table (so all eleven of its stop points
  are covered) rather than an enumeration.
- AC-6 (FR11): the section carries the audit-item source map with one row
  per audit item `## Reporting` requires, and `## Reporting` carries a
  pointer sentence to it while its own item list is unchanged.
- AC-7 (FR7): `batch-terminal-line.md` differs only by the one
  cross-reference sentence inside `## No line on a wait turn`; its seven
  level-2 headings and their order are unchanged, and the marker prefix
  literal does not appear in it.

Test authoring follows `tests/test_batch_stop_contract.py`'s form: standard
library only, no import from another test module, constants re-declared
locally. Both documents are read so the module may hold BOTH prefix
literals -- that is how AC-4's non-collision check is realized (TS-3)
while the documents themselves stay literal-free of each other's prefix.

Matcher -> negative-proof inventory (Test Notes: every NEW matcher carries
a negative proof over a forged sample plus a non-vacuity guard; pure
regression guards over retained pre-change wording are exempt):

- `_assert_new_section_positioned_last` (section slicer / placement):
  negative proof `test_missing_new_section_is_rejected`; non-vacuity guard
  `test_forged_sections_without_new_heading_otherwise_well_formed`.
- `_assert_marker_line_format_stated` (marker-format matcher): negative
  proof `test_incomplete_marker_section_is_rejected`; non-vacuity guard
  `test_forged_marker_section_otherwise_well_formed`.
- `_assert_message_shape_disjointness_stated` (message-shape disjointness
  matcher, batch-structured-result-output task0002 -- replaces the retired
  `_assert_non_collision_stated`): negative proof
  `test_missing_absence_signal_is_rejected`; non-vacuity guard
  `test_forged_disjointness_text_otherwise_well_formed`.
- `_assert_stop_abort_exception_is_set_level` (exception set-level-rule
  matcher): negative proofs `test_enumerated_stop_point_is_rejected` and
  `test_missing_table_reference_is_rejected`; non-vacuity guards
  `test_forged_enumeration_text_otherwise_well_formed` and
  `test_forged_no_table_reference_text_otherwise_well_formed`.
- `_assert_source_map_row_present` (source-map matcher): negative proof
  `test_missing_source_row_is_rejected`; non-vacuity guard
  `test_forged_source_map_missing_one_row_otherwise_well_formed`.

Regression guards over retained pre-change wording -- the ten-row
Non-packet gates table with its catch-all wording and the `## Reporting`
item list -- carry no negative proof, per IMPLEMENTATION.md's Test
authoring note.

TDD-awkward (Test Notes): there is no runtime behaviour to exercise here,
so "red" means the assertion fails against the current document text before
either document is edited.

Extended for task0002 (batch-codex-autonomous-decisions; see
feature-docs/batch-codex-autonomous-decisions/tasks/task0002.md AC-3, AC-4,
AC-5): `## Reporting`'s item list and the audit-item source map both gain
one item -- the autonomous fail-closed-route resolutions -- moving
`REPORTING_ITEM_LIST_SENTENCE` and `SOURCE_MAP_EXPECTATIONS` from six
entries to seven. `test_source_map_has_one_row_per_audit_item` and
`test_source_map_row_count_matches_reporting_item_count` are unmodified:
both are already generic over `SOURCE_MAP_EXPECTATIONS`'s length, so they
exercise the new item without any test-code change, exactly as task0005's
docstring (`tests/test_batch_quiet_output_audit_persistence.py`) already
relied on for its own new row.

Extended for task0002 (batch-structured-result-output; see
feature-docs/batch-structured-result-output/tasks/task0002.md): the
prefixed four-field terminal line this module pinned is replaced by a bare
eight-key structured result owned by `references/batch-terminal-line.md`
(task0001, out of scope here). `## Terminal line` is renamed
`## Structured result`; the whole-file absence set is retargeted from the
old line's literals to IMPLEMENTATION.md SC5's full forbidden set (the
eight SC1 key names as a group, `state` / `step` / `reason` value shapes,
the eleven-plus-one reason codes, the `no-step` sentinel and the removed
SC6 prefix); `_assert_non_collision_stated` (a two-PREFIX comparison) is
replaced by `_assert_message_shape_disjointness_stated` (a two
whole-message-SHAPE comparison), since the new result has no prefix to
compare. `TestContractDocumentUnchangedExceptOneSentence` is removed
rather than retargeted -- see the comment at its former location.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"

# IMPLEMENTATION.md D1: this task's own new marker literal.
MARKER_PREFIX = "EM_WORKFLOW_PROGRESS:"
MARKER_FIELDS = ("phase", "point")
POINT_VALUES = ("wait", "launch", "wake")

# IMPLEMENTATION.md SC5 (batch-structured-result-output task0002): the
# forbidden-literal set a pointer document may never restate. Re-declared
# locally rather than imported from tests/test_batch_stop_contract.py, per
# the cross-module isolation convention. `batch-terminal-line.md` (task0001)
# is the sole owner of these values; this module reads that document's real
# content only for the stable, cross-task Stop point coverage invariant used
# by `TestExceptions` below (D5) -- never to bind its structure, which is
# task0001's job alone.
#
# SC6's removed prefix literal -- permanently forbidden, part of SC5's union.
TERMINAL_PREFIX = "EM_WORKFLOW_TERMINAL:"

# Every `reason` code SC1's domain documents, including the twelfth value
# (`context_budget_reached`) that em-workflow never emits (D8). All twelve
# are unambiguous snake_case tokens with no ordinary-English-word collision,
# so a bare whole-file absence check is sound (contrast `state` / `step`
# below, whose values ARE ordinary words and need the shaped check instead).
TERMINAL_REASON_CODES = (
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
    "context_budget_reached",
)
TERMINAL_SENTINEL = "no-step"

# SC1's eight key names, as the group-of-backticked-tokens this file must
# never restate together (a wholesale copy of the SSOT's key list) --
# generalizes the pre-task0002 four-field group check to all eight keys.
RESULT_KEY_TOKENS = (
    "`state`",
    "`step`",
    "`reason`",
    "`detail`",
    "`feature`",
    "`branch`",
    "`pr_url`",
    "`resume_conditions`",
)

# `state`'s three documented values (unchanged domain, A4/A5): ordinary
# English words in general use elsewhere in this document (Test Notes edge
# case: `completed` / `stopped` are also workflow.yaml step-status
# vocabulary), so checked only in the `key=value`-shaped citation form,
# never as a bare word. `phase_done` has no such collision and is also
# checked bare, via ONCE_BOUNDARY_STATE_VALUE.
TERMINAL_STATE_VALUES = ("completed", "stopped", "phase_done")
ONCE_BOUNDARY_STATE_VALUE = "phase_done"

# `step`'s seven workflow.yaml-step-id values (the `no-step` sentinel is
# handled separately, via TERMINAL_SENTINEL above): every one of these is
# ordinary vocabulary this document already uses constantly as a phase name
# (e.g. "the implement phase's launch turn"), so -- like `state`'s values --
# these are checked only in the `key=value`-shaped citation form, never bare.
RESULT_STEP_VALUES = (
    "create-spec",
    "design",
    "create-plan",
    "implement",
    "review",
    "verify",
    "retrospect",
)

# `reason`'s reserved-for-non-stop value: an ordinary English word, so
# checked only in the `key=value`-shaped citation form, matching `state`
# and `step` above.
RESERVED_REASON_VALUE = "none"

# batch-mode.md's pre-existing level-2 headings, in order, BEFORE this
# task's new section is appended.
PRE_EXISTING_BATCH_MODE_HEADINGS = [
    "Purpose & activation",
    "Non-packet gates",
    "workflow.yaml `batch` block",
    "Structured result",
    "Reporting",
]

# Design item 2's eight suppressed output kinds, verbatim from the task
# plan -- each individually assertable.
SUPPRESSED_ITEMS = (
    "phase start/completion narration",
    "forwarding of sub-agent reports (implementer / reviewer / each worker)",
    "per-step interim summaries",
    "the review phase's Phase R6 report body",
    "the reconcile results the implement wake turn enumerates",
    "the verify result-summary body",
    "design-step progress",
    "the running presentation of Step A.5's command-approval results",
)

# The seven audit items `## Reporting` requires (its existing wording,
# verbatim), used both as a regression pin on that paragraph and as the key
# set for the audit-item source map (AC-6).
#
# Extended for task0002 (batch-codex-autonomous-decisions; see
# feature-docs/batch-codex-autonomous-decisions/tasks/task0002.md AC-3,
# AC-5): the relaxed route's autonomous fail-closed-route resolutions join
# the list as a seventh item, moving this pin from six items to seven --
# updated in place per IMPLEMENTATION.md C5, not deleted.
REPORTING_ITEM_LIST_SENTENCE = (
    "every auto-approved command string, every assumption recorded during "
    "create-spec/planning, auto-rework rounds consumed (review / verify), "
    "any deferred findings with their stable_ids, every unlisted-gate "
    "fallback resolution (gate / options / choice / Codex consulted or "
    "not), every autonomous fail-closed-route resolution (gate / option "
    "chosen / options not chosen / the discussion's key points / whether "
    "Codex was consulted / whether the Opus escalation ran, with its "
    "reasoning), and the kept integration branch name"
)

# IMPLEMENTATION.md D4: audit item -> the phrase its source-map row must
# name. Seven items, matching `## Reporting`'s seven-item list above.
SOURCE_MAP_EXPECTATIONS = (
    ("auto-approved command string", "create-spec.command-approval"),
    ("assumption recorded during create-spec/planning", "phase-state"),
    ("Auto-rework rounds consumed", "batch` block"),
    ("deferred findings", "stable_id"),
    ("unlisted-gate fallback resolution", "phase-state"),
    ("autonomous fail-closed-route resolution", "phase-state"),
    ("kept integration branch name", "parent_branch"),
)

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses all whitespace runs (including line wraps) to a single
    space, matching tests/test_batch_stop_contract.py's convention, so a
    multi-word prose phrase check does not depend on exactly where the
    source file happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _sections(text):
    """Splits `text` into a dict keyed by level-2 heading text (without the
    leading `## `), each value the body up to the next level-2 heading (or
    end of text). Dict insertion order matches document order."""
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row,
    matching tests/test_batch_stop_contract.py's convention."""
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


def _extract_stop_point_keys(contract_text):
    """Extracts the set of backticked stop-point keys (first column) from
    the contract document's `## Stop point coverage` table."""
    section = _sections(contract_text)["Stop point coverage"]
    rows = _table_rows(section)
    keys = set()
    for row in rows:
        match = re.match(r"^`([^`]+)`$", row[0])
        if match:
            keys.add(match.group(1))
    return keys


# ---------------------------------------------------------------------------
# Matcher: new-section placement (section slicer)
# ---------------------------------------------------------------------------


def _assert_new_section_positioned_last(test, sections, heading, prior_headings):
    """Validates that `heading` is present in `sections`, is the LAST key,
    and every heading before it matches `prior_headings` exactly, in
    order (AC-1)."""
    test.assertIn(heading, sections, f"expected new section {heading!r} to exist")
    keys = list(sections.keys())
    test.assertEqual(keys[-1], heading, f"expected {heading!r} to be the last section")
    test.assertEqual(keys[:-1], prior_headings)


class TestNewSectionPlacementMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_assert_new_section_positioned_last`."""

    def test_forged_sections_without_new_heading_otherwise_well_formed(self):
        forged = {h: "" for h in PRE_EXISTING_BATCH_MODE_HEADINGS}
        self.assertEqual(list(forged.keys()), PRE_EXISTING_BATCH_MODE_HEADINGS)

    def test_missing_new_section_is_rejected(self):
        forged = {h: "" for h in PRE_EXISTING_BATCH_MODE_HEADINGS}
        with self.assertRaises(AssertionError):
            _assert_new_section_positioned_last(
                self, forged, "Batch quiet output", PRE_EXISTING_BATCH_MODE_HEADINGS
            )


# ---------------------------------------------------------------------------
# Matcher: marker-line format
# ---------------------------------------------------------------------------


def _assert_marker_line_format_stated(test, section_text):
    """Validates the marker line is defined exactly as IMPLEMENTATION.md
    D1 fixes it: the prefix literal, the two fields in fixed order, each
    field's value domain, the one-physical-line / nothing-else guarantee
    (AC-4)."""
    normalized = _normalize(section_text)
    test.assertIn(MARKER_PREFIX, section_text)
    for field in MARKER_FIELDS:
        test.assertIn(f"`{field}`", section_text, f"marker field {field!r} not named")
    order = [section_text.index(f"`{f}`") for f in MARKER_FIELDS]
    test.assertEqual(order, sorted(order), "marker fields not in fixed order")
    test.assertIn("one ASCII space", normalized)
    test.assertIn("one physical line", normalized)
    for value in POINT_VALUES:
        test.assertIn(f"`{value}`", section_text, f"point value {value!r} not named")
    test.assertIn("workflow.yaml", normalized)
    test.assertIn("step id", normalized)


class TestMarkerFormatMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_assert_marker_line_format_stated`."""

    FORGED_INCOMPLETE = (
        "Prefix literal `EM_WORKFLOW_PROGRESS:` is used for a non-terminal "
        "turn. It carries the `phase` field."
    )

    def test_forged_marker_section_otherwise_well_formed(self):
        self.assertIn(MARKER_PREFIX, self.FORGED_INCOMPLETE)
        self.assertIn("`phase`", self.FORGED_INCOMPLETE)

    def test_incomplete_marker_section_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_marker_line_format_stated(self, self.FORGED_INCOMPLETE)


# ---------------------------------------------------------------------------
# Matcher: message-shape disjointness statement
#
# batch-structured-result-output task0002: replaces the retired
# `_assert_non_collision_stated` (which compared two line PREFIXES -- a
# comparison the new structured result cannot support, since it has no
# prefix at all). The new matcher validates disjointness structurally: two
# whole-message SHAPES, never two prefixes, per IMPLEMENTATION.md's Design
# section for this task ("## Batch quiet output" (FR18, FR19, NFR6)) points
# 1-3.
# ---------------------------------------------------------------------------


def _assert_message_shape_disjointness_stated(test, section_text):
    """Validates the rewritten disjointness paragraph (AC-2): it names
    `EM_WORKFLOW_PROGRESS:` (point 1), states the two whole-message shapes
    are disjoint without naming any terminal prefix (point 2), and
    preserves the "no result = abnormal outcome" signal explicitly
    (point 3)."""
    normalized = _normalize(section_text)
    test.assertIn(MARKER_PREFIX, section_text)
    test.assertIn("references/batch-terminal-line.md", section_text)
    test.assertIn("disjoint", normalized)
    test.assertIn("no result", normalized)
    test.assertIn("abnormal outcome", normalized)
    test.assertNotIn(TERMINAL_PREFIX, section_text)


class TestMessageShapeDisjointnessMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_assert_message_shape_disjointness_stated`."""

    # Names the marker prefix and claims disjointness (points 1-2) but
    # drops the "no result = abnormal outcome" signal (point 3) --
    # exercises exactly the failure mode AC-2 requires the matcher to catch.
    FORGED_DISJOINT_NO_ABSENCE_SIGNAL = (
        f"A non-terminal turn's whole message is one line beginning with "
        f"the prefix literal `{MARKER_PREFIX}`; a terminal turn's whole "
        "message is instead the structured result "
        "references/batch-terminal-line.md defines. The two message "
        "shapes are disjoint."
    )

    def test_forged_disjointness_text_otherwise_well_formed(self):
        self.assertIn(MARKER_PREFIX, self.FORGED_DISJOINT_NO_ABSENCE_SIGNAL)
        self.assertIn(
            "references/batch-terminal-line.md",
            self.FORGED_DISJOINT_NO_ABSENCE_SIGNAL,
        )
        self.assertIn("disjoint", self.FORGED_DISJOINT_NO_ABSENCE_SIGNAL)
        self.assertNotIn(TERMINAL_PREFIX, self.FORGED_DISJOINT_NO_ABSENCE_SIGNAL)

    def test_missing_absence_signal_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_message_shape_disjointness_stated(
                self, self.FORGED_DISJOINT_NO_ABSENCE_SIGNAL
            )


# ---------------------------------------------------------------------------
# Matcher: stop/abort exception as a set-level rule
# ---------------------------------------------------------------------------


def _assert_stop_abort_exception_is_set_level(test, exceptions_text, stop_point_keys):
    """Validates the stop/abort exception is stated as a SET-LEVEL rule
    over the terminal-line contract's stop-point coverage table, rather
    than an enumeration of individual stop points (AC-5, D7): the text
    must reference "stop-point coverage table" AND must not contain any
    individual stop-point key as a backticked literal."""
    normalized = _normalize(exceptions_text)
    test.assertIn("stop-point coverage table", normalized)
    for key in stop_point_keys:
        test.assertNotIn(
            f"`{key}`",
            exceptions_text,
            f"exception text enumerates stop point {key!r} instead of "
            "referring to the table as a set",
        )


class TestStopAbortExceptionMatcherNegativeProof(unittest.TestCase):
    """Negative proofs + non-vacuity guards for
    `_assert_stop_abort_exception_is_set_level`."""

    FORGED_ENUMERATION = (
        "A turn that reaches `stop-condition-2` or `stop-condition-3` keeps "
        "its full output, per the stop-point coverage table."
    )
    FORGED_NO_TABLE_REFERENCE = (
        "A turn that stops or aborts keeps its full output -- cause, "
        "affected paths, recovery hints."
    )

    def test_forged_enumeration_text_otherwise_well_formed(self):
        self.assertIn("stop-point coverage table", self.FORGED_ENUMERATION)

    def test_enumerated_stop_point_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_stop_abort_exception_is_set_level(
                self, self.FORGED_ENUMERATION, {"stop-condition-2", "stop-condition-3"}
            )

    def test_forged_no_table_reference_text_otherwise_well_formed(self):
        self.assertIn("stops or aborts", self.FORGED_NO_TABLE_REFERENCE)
        self.assertIn("full output", self.FORGED_NO_TABLE_REFERENCE)

    def test_missing_table_reference_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_stop_abort_exception_is_set_level(
                self, self.FORGED_NO_TABLE_REFERENCE, {"stop-condition-2"}
            )


# ---------------------------------------------------------------------------
# Matcher: audit-item source map
# ---------------------------------------------------------------------------


def _assert_source_map_row_present(test, table_text, item_phrase, source_phrase):
    """Validates that the source-map table contains a row naming
    `item_phrase` whose Persisted-source cell contains `source_phrase`
    (AC-6)."""
    rows = _table_rows(table_text)
    for row in rows:
        if item_phrase in row[0]:
            test.assertIn(
                source_phrase,
                row[1],
                f"row for {item_phrase!r} does not name source {source_phrase!r}",
            )
            return
    test.fail(f"no source-map row found for audit item {item_phrase!r}")


FORGED_SOURCE_MAP_MISSING_ONE_ROW = (
    "| Audit item | Persisted source |\n"
    "|---|---|\n"
    "| Every assumption recorded during create-spec/planning | "
    "`feature-docs/{feature}/phase-state/*.yaml` `answers` |\n"
    "| Auto-rework rounds consumed (review / verify) | "
    "`workflow.yaml`'s `batch` block |\n"
)


class TestSourceMapMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_assert_source_map_row_present`."""

    def test_forged_source_map_missing_one_row_otherwise_well_formed(self):
        rows = _table_rows(FORGED_SOURCE_MAP_MISSING_ONE_ROW)
        self.assertEqual(len(rows), 2)
        _assert_source_map_row_present(
            self,
            FORGED_SOURCE_MAP_MISSING_ONE_ROW,
            "assumption recorded during create-spec/planning",
            "phase-state",
        )

    def test_missing_source_row_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_source_map_row_present(
                self,
                FORGED_SOURCE_MAP_MISSING_ONE_ROW,
                "auto-approved command string",
                "create-spec.command-approval",
            )


# ---------------------------------------------------------------------------
# AC-1: new section exists, positioned last; pre-existing structure intact
# ---------------------------------------------------------------------------


class TestBatchModeSectionStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.sections = _sections(cls.text)

    def test_document_exists(self):
        self.assertTrue(BATCH_MODE_PATH.is_file())

    def test_new_section_positioned_last(self):
        _assert_new_section_positioned_last(
            self, self.sections, "Batch quiet output", PRE_EXISTING_BATCH_MODE_HEADINGS
        )

    def test_exactly_one_new_level_2_section(self):
        """AC-1: the pre-existing five headings plus exactly one new one --
        no additional level-2 heading was introduced."""
        self.assertEqual(len(self.sections), len(PRE_EXISTING_BATCH_MODE_HEADINGS) + 1)

    def test_structured_result_and_reporting_headings_present(self):
        self.assertIn("Structured result", self.sections)
        self.assertIn("Reporting", self.sections)

    def test_non_packet_gates_table_still_has_ten_data_rows(self):
        rows = _table_rows(self.sections["Non-packet gates"])
        self.assertEqual(len(rows), 10)

    def test_non_packet_gates_catch_all_wording_intact(self):
        normalized = _normalize(self.sections["Non-packet gates"])
        self.assertIn(
            "Any other non-packet `AskUserQuestion` site not listed above",
            normalized,
        )


# ---------------------------------------------------------------------------
# AC-2: activation
# ---------------------------------------------------------------------------


class TestActivation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(BATCH_MODE_PATH))["Batch quiet output"]
        cls.normalized = _normalize(cls.section)

    def test_active_exactly_when_batch_flag_present(self):
        self.assertIn(
            "Active exactly when the current invocation's arguments "
            "contain `--batch`",
            self.normalized,
        )

    def test_batch_block_never_activates_it(self):
        self.assertIn("`batch` block", self.section)
        self.assertIn("never activates it", self.normalized)

    def test_interactive_launch_unaffected(self):
        self.assertIn("interactive launch", self.normalized)
        self.assertIn("unaffected", self.normalized)


# ---------------------------------------------------------------------------
# AC-3: suppressed scope + what is NOT touched
# ---------------------------------------------------------------------------


class TestSuppressedScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(BATCH_MODE_PATH))["Batch quiet output"]
        cls.normalized = _normalize(cls.section)

    def test_all_eight_suppressed_items_named(self):
        for item in SUPPRESSED_ITEMS:
            with self.subTest(item=item):
                self.assertIn(item, self.normalized)

    def test_suppression_targets_main_context_assistant_text_only(self):
        self.assertIn("main-context assistant text only", self.normalized)

    def test_file_writes_and_commits_unchanged(self):
        self.assertIn("file writes and commits", self.normalized)

    def test_gate_resolution_unchanged(self):
        self.assertIn("gate resolution", self.normalized)

    def test_auto_rework_caps_unchanged(self):
        self.assertIn("auto-rework caps", self.normalized)

    def test_counters_and_status_transitions_unchanged(self):
        self.assertIn("counters", self.normalized)
        self.assertIn("status transitions", self.normalized)
        self.assertIn("same path as before", self.normalized)


# ---------------------------------------------------------------------------
# AC-1, AC-2: non-terminal turns, marker line, message-shape disjointness,
# whole-file SC5 absence (batch-structured-result-output task0002)
# ---------------------------------------------------------------------------


class TestNonTerminalTurnsAndMarkerLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.section = _sections(cls.text)["Batch quiet output"]
        cls.normalized = _normalize(cls.section)

    def test_three_non_terminal_turns_named(self):
        self.assertIn("stop condition 5's wait turn", self.normalized)
        self.assertIn("implement phase's launch turn", self.normalized)
        self.assertIn("its wake turn", self.normalized)

    def test_marker_line_format_stated(self):
        _assert_marker_line_format_stated(self, self.section)

    def test_message_shape_disjointness_stated(self):
        _assert_message_shape_disjointness_stated(self, self.section)

    def test_whole_file_absence_of_terminal_prefix(self):
        self.assertNotIn(TERMINAL_PREFIX, self.text)

    def test_whole_file_absence_of_reason_codes(self):
        for code in TERMINAL_REASON_CODES:
            with self.subTest(code=code):
                self.assertNotIn(code, self.text)

    def test_whole_file_absence_of_no_step_sentinel(self):
        self.assertNotIn(TERMINAL_SENTINEL, self.text)

    def test_whole_file_absence_of_eight_key_names_as_group(self):
        """SC5 point 1 (batch-structured-result-output task0002): the eight
        SC1 key names, backticked, never all appear together -- a wholesale
        restatement of the SSOT's key list. Generalizes the pre-task0002
        four-field group check to all eight keys."""
        self.assertFalse(
            all(token in self.text for token in RESULT_KEY_TOKENS),
            "all eight result key names appear together in batch-mode.md",
        )

    def test_whole_file_absence_of_state_value_shape(self):
        for value in TERMINAL_STATE_VALUES:
            for spelling in (f"state={value}", f"`state={value}`", f'"state={value}"'):
                with self.subTest(spelling=spelling):
                    self.assertNotIn(spelling, self.text)

    def test_whole_file_absence_of_bare_phase_done_literal(self):
        self.assertNotIn(ONCE_BOUNDARY_STATE_VALUE, self.text)

    def test_whole_file_absence_of_step_value_shape(self):
        """SC5 (batch-structured-result-output task0002): `step`'s seven
        workflow.yaml-step-id values, checked only in the `key=value`-shaped
        citation form -- each value is ordinary phase-name vocabulary this
        document uses constantly bare (Test Notes edge case)."""
        for value in RESULT_STEP_VALUES:
            for spelling in (f"step={value}", f"`step={value}`", f'"step={value}"'):
                with self.subTest(spelling=spelling):
                    self.assertNotIn(spelling, self.text)

    def test_whole_file_absence_of_reserved_reason_value_shape(self):
        """SC5 (batch-structured-result-output task0002): `reason`'s
        reserved-for-non-stop value `none` is an ordinary English word, so
        checked only in the `key=value`-shaped citation form, matching
        `state` and `step` above."""
        for spelling in (
            f"reason={RESERVED_REASON_VALUE}",
            f"`reason={RESERVED_REASON_VALUE}`",
            f'"reason={RESERVED_REASON_VALUE}"',
        ):
            with self.subTest(spelling=spelling):
                self.assertNotIn(spelling, self.text)


# ---------------------------------------------------------------------------
# AC-5: exceptions
# ---------------------------------------------------------------------------


class TestExceptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(BATCH_MODE_PATH))["Batch quiet output"]
        cls.normalized = _normalize(cls.section)
        cls.stop_point_keys = _extract_stop_point_keys(_read(CONTRACT_PATH))

    def test_stop_point_coverage_table_has_eleven_keys(self):
        """Non-vacuity for the coverage read: the contract's stop-point
        coverage table extracts to eleven keys, matching the real
        document -- proves the set-level rule below actually ranges over
        all eleven, per Test Notes."""
        self.assertEqual(len(self.stop_point_keys), 11)

    def test_stop_abort_exception_is_set_level_rule(self):
        _assert_stop_abort_exception_is_set_level(
            self, self.section, self.stop_point_keys
        )

    def test_stop_abort_exception_keeps_full_output(self):
        self.assertIn("keeps its full output", self.normalized)

    def test_step_c_exception_stated(self):
        self.assertIn(
            "Step C's completion processing emits its final report in full",
            self.normalized,
        )
        self.assertIn("result following it", self.normalized)

    def test_once_boundary_exception_stated(self):
        self.assertIn("`--once` phase-boundary turn", self.section)
        self.assertIn("withholds all other narration", self.normalized)


# ---------------------------------------------------------------------------
# AC-6: audit-item source map + Reporting pointer sentence
# ---------------------------------------------------------------------------


class TestAuditItemSourceMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = _sections(_read(BATCH_MODE_PATH))
        cls.quiet_section = cls.sections["Batch quiet output"]
        cls.reporting_section = cls.sections["Reporting"]

    def test_reporting_item_list_unchanged(self):
        self.assertIn(
            REPORTING_ITEM_LIST_SENTENCE, _normalize(self.reporting_section)
        )

    def test_reporting_carries_pointer_sentence(self):
        self.assertIn(
            "Batch quiet output", self.reporting_section,
            "## Reporting does not point at the new section by name",
        )

    def test_source_map_has_one_row_per_audit_item(self):
        for item_phrase, source_phrase in SOURCE_MAP_EXPECTATIONS:
            with self.subTest(item=item_phrase):
                _assert_source_map_row_present(
                    self, self.quiet_section, item_phrase, source_phrase
                )

    def test_source_map_row_count_matches_reporting_item_count(self):
        # The source-map table lives inside the "Batch quiet output"
        # section; locate its rows directly (the section may also contain
        # the marker-format bullets, which are not table rows).
        rows = _table_rows(self.quiet_section)
        self.assertEqual(len(rows), len(SOURCE_MAP_EXPECTATIONS))


# ---------------------------------------------------------------------------
# batch-structured-result-output task0002: `TestContractDocumentUnchanged
# ExceptOneSentence` (task0003-of-batch-quiet-output's AC-7) is REMOVED, not
# retargeted. It bound `batch-terminal-line.md`'s real structure (exact
# seven-heading list, the removed prefix literal's PRESENCE, the eleven
# reason codes' presence) from a module this feature does NOT make the
# owner of that file -- task0001 owns `batch-terminal-line.md` end to end,
# including the binding assertion, inside `tests/test_batch_stop_contract.py`
# (IMPLEMENTATION.md D5: "A guard module NOT owned by the file's task ...
# never [binds] against the file"). Every one of this class's assertions is
# also factually superseded by task0001's rewrite (SC2's nine headings, SC6's
# prefix removal) regardless of this task's own edits, so retargeting it
# in place -- rather than removing it -- would recreate the same
# duplicate-binding violation against the NEW shape instead of the old one.
# `CONTRACT_PATH` itself is retained above: `TestExceptions` still reads it,
# but only for the Stop point coverage table's eleven-key invariant, which
# task0001's plan states explicitly stays unchanged by this feature.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
