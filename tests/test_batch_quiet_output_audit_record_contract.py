"""Tests for task0006 (batch-quiet-output): aligning the batch audit record
file's consumers and rules with its own schema in
`em-workflow/references/phase-state.md` (deferred round-2 review findings
SC-6, SC-6-b; feature-docs/batch-quiet-output/tasks/task0006.md).

All five underlying findings share one root cause: `phase-state.md`'s
`## Batch audit record file` section is the schema SSOT (`records` is a
list, not a map), and three statements written before rework round 1 turned
it into a list still assumed the old `answers` map shape.

Covers task0006 Acceptance Criteria:

- AC-1 (FR11, NFR4): `batch-mode.md`'s audit-item source map rows for "Every
  auto-approved command string" and "Every unlisted-gate fallback
  resolution" name `records[]` / `records[].resolution_note`, not `answers`,
  while keeping the path literal, the `references/phase-state.md` citation
  and (for the first row) `create-spec.command-approval`.
- AC-2 (FR11, NFR4): the source map still has exactly one row per
  `## Reporting` audit item (six rows); the assumption row is unchanged,
  character for character.
- AC-3 (FR10, FR12): `## Non-packet gates` still has exactly ten data rows;
  its diff-size-gate and per-command-approval-fallback rows are unchanged;
  the document's `gate_id` count is still 8.
- AC-4 (FR11, NFR4): `phase-state.md`'s `question_id` rule for the two
  gate-id-less writers is stated by that section itself, not by citing
  `references/question-resolution.md` step 7; the one step 7 citation left
  in the section sits only within the `create-spec.command-approval`
  statement, the section's only `batch-decision-table` writer.
- AC-5 (FR11, NFR4): every `question_id` value the section prescribes
  matches `^[a-z][a-z0-9._-]*$`, none of them `null`, and the section cites
  `references/question-packet-schema.md` as that pattern's owner without
  restating the pattern's role for `resolution_note`.
- AC-6 (FR9, NFR4): the first writer bullet states a commit reach-point
  that covers the per-command approval fallback firing outside any phase
  step (an immediate self-commit) and names the loss it prevents (implement
  I.2.b step 2's `reset --hard`); the append-only closing sentence keeps its
  wording and extends its exception list; "Three writers append to this
  file" still occurs exactly once.
- AC-7 (FR9, FR10): out of this module's scope by construction -- this task
  does not touch `references/implement-phase.md`, `skills/develop/SKILL.md`,
  `references/question-resolution.md`, `references/question-packet-schema.md`
  or `references/command-execution-protocol.md` at all (none is in this
  task's file set), so their byte-identity to the pre-task state is a
  property of the diff this task produces, verified by inspecting that diff
  before merging, not by a full-file pin baked into a test that would then
  block any UNRELATED future task from ever touching these shared protocol
  documents again.
- AC-8 (FR13): delegated in full to
  `tests/test_batch_quiet_output_version_bump.py`.
- AC-9 (FR10): delegated to the whole-suite run
  (`python3 -m unittest discover -s tests`); this module itself imports the
  standard library only and is discoverable from the repository root.

Test authoring follows `tests/test_batch_quiet_output_audit_persistence.py`'s
form: standard library only, no import from another test module, every
constant re-declared locally.

Matcher -> negative-proof inventory (Test Notes: every NEW matcher carries a
negative proof over a forged sample plus a non-vacuity guard; pure
regression guards over retained pre-change wording are exempt):

- `_row_names_records_container` (container-key matcher): negative proof
  `test_rejects_forged_row_naming_answers`; non-vacuity guard
  `test_forged_row_naming_records_is_well_formed_and_found`.
- `_step7_citation_scope_ok` (citation-scope matcher): negative proof
  `test_rejects_forged_section_citing_step7_for_a_gate_id_less_writer`;
  non-vacuity guard
  `test_forged_well_scoped_section_is_well_formed_and_found`.
- `_question_id_values_pattern_conforming_no_null` (question_id-pattern
  matcher): negative proof
  `test_rejects_forged_section_with_question_id_null`; non-vacuity guard
  `test_forged_pattern_conforming_section_is_well_formed_and_found`.
- `_first_writer_bullet_states_out_of_step_reach_point` (reach-point
  matcher): negative proof
  `test_rejects_forged_bullet_with_only_the_in_step_reach_point`;
  non-vacuity guard
  `test_forged_bullet_with_out_of_step_reach_point_is_well_formed_and_found`.

Regression guards over retained pre-change wording -- the assumption row,
the ten Non-packet gates rows, the `gate_id` count, and the "Three writers
append to this file" singleton -- carry no negative proof, per
IMPLEMENTATION.md's Test authoring note.

TDD-awkward (Test Notes): there is no runtime behaviour in this task, so
"red" means the assertion fails against the current document text before
either document is edited. AC-1's `records[]` assertion, AC-4's
no-step-7-citation assertion, AC-5's pattern assertion over the wake
decline value, and AC-6's out-of-step reach-point assertion each fail
against the tree as committed before this task's edits -- confirmed by
running this module before touching either document.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"

QUESTION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9._-]*$")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse markdown line-wrap whitespace to single spaces, matching
    tests/test_batch_quiet_output_audit_persistence.py's convention."""
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row,
    matching the repository's existing convention."""
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
# Matcher: container-key (AC-1)
# ---------------------------------------------------------------------------


def _row_names_records_container(row_cell):
    """True when `row_cell` names `records[]` as the container and
    `records[].resolution_note` for the note field, and never contains the
    bare word `answers`."""
    return (
        "records[]" in row_cell
        and "records[].resolution_note" in row_cell
        and "answers" not in row_cell
    )


FORGED_ROW_NAMING_ANSWERS = (
    "| Every unlisted-gate fallback resolution | `feature-docs/{feature}/"
    "phase-state/batch-audit.yaml` `answers` / `resolution_note` "
    "(`references/phase-state.md`'s batch audit record file) |"
)

FORGED_ROW_NAMING_RECORDS = (
    "| Every unlisted-gate fallback resolution | `feature-docs/{feature}/"
    "phase-state/batch-audit.yaml` `records[]` / `records[].resolution_note` "
    "(`references/phase-state.md`'s batch audit record file) |"
)


class TestContainerKeyMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_row_names_records_container`."""

    def test_forged_row_naming_records_is_well_formed_and_found(self):
        self.assertIn("records[]", FORGED_ROW_NAMING_RECORDS)
        self.assertIn("records[].resolution_note", FORGED_ROW_NAMING_RECORDS)
        self.assertTrue(_row_names_records_container(FORGED_ROW_NAMING_RECORDS))

    def test_rejects_forged_row_naming_answers(self):
        self.assertIn("answers", FORGED_ROW_NAMING_ANSWERS)
        self.assertFalse(_row_names_records_container(FORGED_ROW_NAMING_ANSWERS))


# ---------------------------------------------------------------------------
# AC-1: the two live source-map rows in batch-mode.md
# ---------------------------------------------------------------------------


class TestAC1SourceMapRowsNameRecordsContainer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.quiet_section = _slice(cls.text, "## Batch quiet output")

    def _row_for(self, item_phrase):
        for row in _table_rows(self.quiet_section):
            if item_phrase in row[0]:
                return row
        self.fail(f"no source-map row found for {item_phrase!r}")

    def test_auto_approved_command_string_row_names_records_container(self):
        row = self._row_for("Every auto-approved command string")
        self.assertTrue(_row_names_records_container(row[-1]))
        self.assertIn(
            "feature-docs/{feature}/phase-state/batch-audit.yaml", row[-1]
        )
        self.assertIn("references/phase-state.md", row[-1])
        self.assertIn("create-spec.command-approval", row[-1])

    def test_unlisted_gate_fallback_row_names_records_container(self):
        row = self._row_for("Every unlisted-gate fallback resolution")
        self.assertTrue(_row_names_records_container(row[-1]))
        self.assertIn(
            "feature-docs/{feature}/phase-state/batch-audit.yaml", row[-1]
        )
        self.assertIn("references/phase-state.md", row[-1])


# ---------------------------------------------------------------------------
# AC-2: exactly six rows; the assumption row is byte-identical
# ---------------------------------------------------------------------------

ASSUMPTION_ROW = (
    "| Every assumption recorded during create-spec/planning | "
    "`feature-docs/{feature}/phase-state/*.yaml` `answers` / "
    "resolution notes |"
)


class TestAC2SourceMapRegressionGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.quiet_section = _slice(cls.text, "## Batch quiet output")

    def test_source_map_still_has_six_rows(self):
        self.assertEqual(len(_table_rows(self.quiet_section)), 6)

    def test_assumption_row_unchanged_character_for_character(self):
        self.assertIn(ASSUMPTION_ROW, self.quiet_section)


# ---------------------------------------------------------------------------
# AC-3: Non-packet gates table -- ten rows, two unchanged rows, gate_id count
# ---------------------------------------------------------------------------

DIFF_SIZE_GATE_ROW = (
    "| Review phase diff-size gate (`references/review-phase.md`) | Codex "
    "consultation per `references/question-resolution.md`'s unlisted-gate "
    "fallback procedure; no decision reached → take the option with the "
    "smallest / most reversible side effect and continue. The resolution is "
    "recorded in `feature-docs/{feature}/phase-state/batch-audit.yaml` "
    "(`references/phase-state.md`'s batch audit record file), from which "
    "the run report is assembled |"
)

PER_COMMAND_APPROVAL_ROW = (
    "| Per-command approval fallback used when the PreToolUse hook is "
    "inactive (`references/command-execution-protocol.md`, python3 "
    "missing) | Same as the diff-size gate above: Codex consultation, "
    "falling back to the minimum-side-effect option, recorded in "
    "`feature-docs/{feature}/phase-state/batch-audit.yaml` "
    "(`references/phase-state.md`'s batch audit record file), from which "
    "the run report is assembled. Caches the resolution per literal "
    "command string within the run — matching the interactive "
    "fallback's per-literal-string cache in "
    "`references/command-execution-protocol.md` — so an identical "
    "command string is decided once, not re-consulted on every "
    "occurrence |"
)


class TestAC3NonPacketGatesRegressionGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.gates_section = _slice(cls.text, "## Non-packet gates", "## workflow.yaml")

    def test_table_still_has_ten_data_rows(self):
        self.assertEqual(len(_table_rows(self.gates_section)), 10)

    def test_diff_size_gate_row_unchanged(self):
        self.assertIn(DIFF_SIZE_GATE_ROW, self.gates_section)

    def test_per_command_approval_row_unchanged(self):
        self.assertIn(PER_COMMAND_APPROVAL_ROW, self.gates_section)

    def test_gate_id_count_still_eight(self):
        self.assertEqual(self.text.count("gate_id"), 8)


# ---------------------------------------------------------------------------
# Matcher: step7 citation scope (AC-4)
# ---------------------------------------------------------------------------


def _step7_citation_scope_ok(subsection_text):
    """True when 'step 7' is cited exactly once in `subsection_text`, and
    the single SENTENCE carrying that citation (bounded by the nearest
    surrounding ". " markers, so it does not bleed into a neighbouring
    sentence about a different writer) names BOTH
    `create-spec.command-approval` and `batch-decision-table`, and names
    NEITHER gate-id-less writer."""
    idx = subsection_text.find("step 7")
    if idx == -1:
        return False
    if subsection_text.find("step 7", idx + 1) != -1:
        return False  # more than one citation
    sentence_start = subsection_text.rfind(". ", 0, idx)
    sentence_start = 0 if sentence_start == -1 else sentence_start + 2
    sentence_end = subsection_text.find(". ", idx)
    sentence_end = len(subsection_text) if sentence_end == -1 else sentence_end + 1
    sentence = subsection_text[sentence_start:sentence_end]
    if "create-spec.command-approval" not in sentence:
        return False
    if "batch-decision-table" not in sentence:
        return False
    if "diff-size gate" in sentence or "per-command approval fallback" in sentence:
        return False
    return True


FORGED_SECTION_MISSCOPED_STEP7 = (
    "For a gate with no `gate_id` — the review phase diff-size gate "
    "and the per-command approval fallback — `question_id` is "
    "present, per `references/question-resolution.md` step 7's rule for "
    "an orchestrator-opened gate with no worker packet and no `gate_id`. "
    "For the one writer with a `gate_id` — "
    "`create-spec.command-approval` — `question_id` is that "
    "`gate_id`, with `source` `batch-decision-table`."
)

FORGED_SECTION_WELL_SCOPED_STEP7 = (
    "For a gate with no `gate_id` — the review phase diff-size gate "
    "and the per-command approval fallback — `question_id` is an "
    "identifying name of the gate itself, stated by this section on its "
    "own authority. For the one writer with a `gate_id` — "
    "`create-spec.command-approval`, the only writer here whose `source` "
    "is `batch-decision-table` — `question_id` is that `gate_id`, "
    "per `references/question-resolution.md` step 7's rule for an "
    "orchestrator-opened gate with no worker packet and no `gate_id`."
)


class TestStep7CitationScopeMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_step7_citation_scope_ok`."""

    def test_forged_well_scoped_section_is_well_formed_and_found(self):
        self.assertIn("step 7", FORGED_SECTION_WELL_SCOPED_STEP7)
        self.assertIn(
            "create-spec.command-approval", FORGED_SECTION_WELL_SCOPED_STEP7
        )
        self.assertTrue(
            _step7_citation_scope_ok(FORGED_SECTION_WELL_SCOPED_STEP7)
        )

    def test_rejects_forged_section_citing_step7_for_a_gate_id_less_writer(self):
        self.assertIn("step 7", FORGED_SECTION_MISSCOPED_STEP7)
        self.assertIn("diff-size gate", FORGED_SECTION_MISSCOPED_STEP7)
        self.assertFalse(
            _step7_citation_scope_ok(FORGED_SECTION_MISSCOPED_STEP7)
        )


# ---------------------------------------------------------------------------
# AC-4: phase-state.md's real question_id rule cites step 7 only once,
# scoped to create-spec.command-approval
# ---------------------------------------------------------------------------


class TestAC4QuestionIdRuleCitationScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.subsection = _slice(
            cls.text, "## Batch audit record file", "## Legacy feature compatibility"
        )

    def test_step7_citation_scoped_to_create_spec_command_approval(self):
        self.assertTrue(_step7_citation_scope_ok(self.subsection))

    def test_rule_stated_on_the_sections_own_authority(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn("on its own authority", normalized)


# ---------------------------------------------------------------------------
# Matcher: question_id pattern conformance + no null (AC-5)
# ---------------------------------------------------------------------------

QUESTION_ID_ASSIGNMENT_RE = re.compile(r"`question_id` is `([^`]+)`")


def _question_id_values_pattern_conforming_no_null(text):
    """Extracts every literal directly assigned to `question_id` (the text
    "`question_id` is `<value>`"), and returns True only when at least one
    value was found, every value matches `QUESTION_ID_PATTERN`, and no
    assignment anywhere in `text` sets `question_id` to `null`."""
    values = QUESTION_ID_ASSIGNMENT_RE.findall(text)
    if not values:
        return False
    if any(v == "null" for v in values):
        return False
    if "question_id` is `null`" in text or "question_id is `null`" in text:
        return False
    return all(QUESTION_ID_PATTERN.match(v) for v in values)


FORGED_SECTION_WITH_NULL = (
    "`question_id` is `review.diff-size-gate` for the diff-size gate. "
    "`question_id` is `null` for the implement wake decline record, "
    "which is not a gate."
)

FORGED_SECTION_PATTERN_CONFORMING = (
    "`question_id` is `review.diff-size-gate` for the diff-size gate, "
    "and `question_id` is "
    "`command-execution.per-command-approval-fallback` for the "
    "per-command approval fallback. `question_id` is "
    "`implement.wake-decline` for the implement wake decline record."
)


class TestQuestionIdPatternMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_question_id_values_pattern_conforming_no_null`."""

    def test_forged_pattern_conforming_section_is_well_formed_and_found(self):
        values = QUESTION_ID_ASSIGNMENT_RE.findall(FORGED_SECTION_PATTERN_CONFORMING)
        self.assertEqual(len(values), 3)
        self.assertTrue(
            _question_id_values_pattern_conforming_no_null(
                FORGED_SECTION_PATTERN_CONFORMING
            )
        )

    def test_rejects_forged_section_with_question_id_null(self):
        self.assertIn("question_id` is `null`", FORGED_SECTION_WITH_NULL)
        self.assertFalse(
            _question_id_values_pattern_conforming_no_null(FORGED_SECTION_WITH_NULL)
        )


# ---------------------------------------------------------------------------
# AC-5: phase-state.md's real question_id values all conform; pattern
# ownership is cited without restating it for resolution_note
# ---------------------------------------------------------------------------


class TestAC5QuestionIdValuesPatternConforming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.subsection = _slice(
            cls.text, "## Batch audit record file", "## Legacy feature compatibility"
        )

    def test_all_prescribed_question_id_values_conform_and_no_null(self):
        self.assertTrue(
            _question_id_values_pattern_conforming_no_null(self.subsection)
        )

    def test_at_least_the_three_task_literals_are_present_and_conforming(self):
        for literal in (
            "review.diff-size-gate",
            "command-execution.per-command-approval-fallback",
            "implement.wake-decline",
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, self.subsection)
                self.assertRegex(literal, QUESTION_ID_PATTERN)

    def test_question_packet_schema_cited_as_pattern_owner(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn(
            "question_id` pattern `references/question-packet-schema.md` owns",
            normalized,
        )

    def test_pattern_ownership_not_restated_for_resolution_note(self):
        self.assertNotIn("resolution_note` pattern", self.subsection)


# ---------------------------------------------------------------------------
# Matcher: out-of-step commit reach-point (AC-6)
# ---------------------------------------------------------------------------


def _first_writer_bullet(subsection_text):
    idx = subsection_text.index("Three writers append to this file")
    after = subsection_text[idx:]
    bullet_start = after.index("\n- ") + 1
    bullet_end = after.index("\n- ", bullet_start + 1)
    return after[bullet_start:bullet_end]


def _first_writer_bullet_states_out_of_step_reach_point(bullet_text):
    normalized = _normalize_ws(bullet_text)
    return (
        "outside any phase step" in normalized
        and "immediately" in normalized
        and "reset --hard" in normalized
    )


FORGED_BULLET_IN_STEP_ONLY = (
    "- `references/batch-mode.md`'s Non-packet gates table: the review "
    "phase diff-size gate and the per-command approval fallback each "
    "append one entry. The entry is committed by the next "
    "`commit-docs.sh` call the same phase step already makes for its "
    "own reasons.\n"
)

FORGED_BULLET_WITH_OUT_OF_STEP_REACH_POINT = (
    "- `references/batch-mode.md`'s Non-packet gates table: the review "
    "phase diff-size gate and the per-command approval fallback each "
    "append one entry. Inside a phase step, the entry is committed by "
    "the step's next existing `commit-docs.sh` call. The per-command "
    "approval fallback can also fire outside any phase step; there, the "
    "writer commits its own entry immediately, since an uncommitted "
    "record would otherwise be destroyed by "
    "`git -C {integration_worktree} reset --hard`.\n"
)


class TestReachPointMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_first_writer_bullet_states_out_of_step_reach_point`."""

    def test_forged_bullet_with_out_of_step_reach_point_is_well_formed_and_found(
        self,
    ):
        self.assertIn("outside any phase step", FORGED_BULLET_WITH_OUT_OF_STEP_REACH_POINT)
        self.assertIn("reset --hard", FORGED_BULLET_WITH_OUT_OF_STEP_REACH_POINT)
        self.assertTrue(
            _first_writer_bullet_states_out_of_step_reach_point(
                FORGED_BULLET_WITH_OUT_OF_STEP_REACH_POINT
            )
        )

    def test_rejects_forged_bullet_with_only_the_in_step_reach_point(self):
        self.assertNotIn("outside any phase step", FORGED_BULLET_IN_STEP_ONLY)
        self.assertFalse(
            _first_writer_bullet_states_out_of_step_reach_point(
                FORGED_BULLET_IN_STEP_ONLY
            )
        )


# ---------------------------------------------------------------------------
# AC-6: phase-state.md's real first writer bullet + append-only exception
# ---------------------------------------------------------------------------


class TestAC6FirstWriterBulletAndAppendOnlyException(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.subsection = _slice(
            cls.text, "## Batch audit record file", "## Legacy feature compatibility"
        )
        cls.bullet = _first_writer_bullet(cls.subsection)

    def test_first_writer_bullet_states_out_of_step_reach_point(self):
        self.assertTrue(
            _first_writer_bullet_states_out_of_step_reach_point(self.bullet)
        )

    def test_first_writer_bullet_names_the_loss_prevented(self):
        normalized = _normalize_ws(self.bullet)
        self.assertIn("references/implement-phase.md", normalized)
        self.assertIn("I.2.b step 2", normalized)

    def test_three_writers_sentence_occurs_exactly_once(self):
        self.assertEqual(
            self.subsection.count("Three writers append to this file"), 1
        )

    def test_append_only_sentence_retains_core_phrase(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn(
            "never itself the reason to create a commit that would not "
            "otherwise happen",
            normalized,
        )

    def test_exception_list_names_both_step_a5_and_per_command_fallback(self):
        idx = self.subsection.find("except for Step A.5")
        self.assertNotEqual(idx, -1, "exception clause not found")
        window = self.subsection[idx : idx + 300]
        self.assertIn("per-command approval fallback", window)

    def test_append_only_rule_retained(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn("append-only", normalized)
        self.assertIn("never rewritten or removed", normalized)


# ---------------------------------------------------------------------------
# Files exist / module is standard-library-only / discoverable
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_both_documents_exist(self):
        for path in (BATCH_MODE_PATH, PHASE_STATE_PATH):
            self.assertTrue(path.is_file(), f"expected {path} to exist")


if __name__ == "__main__":
    unittest.main()
