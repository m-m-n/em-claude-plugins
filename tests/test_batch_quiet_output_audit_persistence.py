"""Tests for task0005 (batch-quiet-output): persisting the two batch audit
records that previously had no persisted home -- the non-packet
unlisted-gate fallback resolutions (the review diff-size gate and the
per-command approval fallback) and the implement wake phase's declined
`files` deviations -- into one new shared file,
`feature-docs/{feature}/phase-state/batch-audit.yaml`, and removing the two
volatile/mode-divergent channels that carried them before this task: the
`## Batch quiet output` Exceptions section's fourth bullet in
`batch-mode.md` (an unsuppressed resolution line), and the batch-only wake
commit-message construction in `implement-phase.md` (the `DECLINED` body
line).

Covers task0005 Acceptance Criteria
(feature-docs/batch-quiet-output/tasks/task0005.md):

- AC-1 (FR11, FR5): delegated to
  `tests/test_batch_quiet_output_discipline.py`'s
  `TestAuditItemSourceMap.test_source_map_has_one_row_per_audit_item`
  (unmodified by this task -- watching it turn green unmodified is this
  task's primary red-to-green signal, per the task plan's Test Notes).
  This module adds one supplementary check with the same
  persisted-source-row matcher used for AC-3, confirming the row also
  names this task's `references/phase-state.md` pointer.
- AC-2 (FR2, FR4): the Exceptions list contains exactly three bullets, and
  the phrase pairing an unlisted-gate fallback with an unsuppressed
  emitted line is absent from the whole document.
- AC-3 (FR10, FR12): both Non-packet gates rows for the diff-size gate and
  the per-command approval fallback name the persisted record site and
  state the run report is assembled from it; the table still has exactly
  ten data rows; the catch-all paragraph, `unlisted-gate fallback`,
  `question-resolution.md`, `per literal command string`, the
  Codex-consultation-first order and the minimum-side-effect fallback are
  unchanged.
- AC-4 (FR9, NFR1): `implement-phase.md` I.2.b step 3 states one
  `commit-docs.sh` call whose message construction does not depend on
  `--batch`; the literal `DECLINED` and the message-body-extension rule
  are absent; `$RECONCILE_TIP` is still stated as `expected_base_tip`.
- AC-5 (FR11, NFR3): the wake "Batch mode" paragraph states a declined
  deviation's audit record is written to the persisted source under
  `phase-state/` in the same wake commit, and that the run-report
  obligation is satisfied by reading it from there rather than this wake
  phase's own report.
- AC-6 (FR11, FR9): `phase-state.md` defines the batch audit record file
  in its File layout and in one new subsection stating its purpose, its
  entry shape (reusing the existing `answers` entry shape), its two
  writers, its append-only rule, and that it is committed by an existing
  `commit-docs.sh` call and never causes an additional commit.
- AC-7 (FR12, NFR4): `batch-mode.md` cites `references/phase-state.md` for
  the record's shape, and `implement-phase.md` cites both documents for
  the channel it writes; delegated in full to
  `tests/test_check_plugin_invariants.py` for the no-new-`gate_id`
  obligation.
- AC-8 (FR13): delegated in full to
  `tests/test_batch_quiet_output_version_bump.py`.
- AC-9 (FR10, NFR1): delegated to the whole-suite run
  (`python3 -m unittest discover -s tests`); this module itself imports
  the standard library only and is discoverable from the repository root.

Test authoring follows `tests/test_batch_quiet_output_discipline.py`'s
form: standard library only, no import from another test module, every
constant re-declared locally (including the record file's path literal,
this task's own new shared literal).

Matcher -> negative-proof inventory (Test Notes: every NEW matcher carries
a negative proof over a forged sample plus a non-vacuity guard; pure
regression guards over retained pre-change wording are exempt):

- `_row_names_persisted_site` (persisted-source-row matcher): negative
  proof `test_rejects_forged_row_missing_the_path_literal`; non-vacuity
  guard `test_forged_row_is_well_formed_and_found`.
- `_exceptions_bullet_count` (exception-set matcher): negative proof
  `test_rejects_forged_four_bullet_exceptions`; non-vacuity guard
  `test_forged_three_and_four_bullet_samples_are_well_formed`.
- `_unlisted_gate_unsuppressed_phrase_present` (exception-set matcher,
  absence half): negative proof
  `test_rejects_forged_sample_without_the_pairing`; non-vacuity guard
  `test_forged_pairing_sample_is_well_formed_and_found`.
- `_mode_independent_single_line_commit_stated` (mode-independent-commit
  matcher): negative proof
  `test_rejects_forged_sample_naming_batch_in_the_commit_clause`;
  non-vacuity guard `test_forged_mode_independent_sample_is_well_formed`.
- `_decline_persisted_under_phase_state` (decline-persistence matcher):
  negative proof `test_rejects_forged_sample_missing_the_path_literal`;
  non-vacuity guard `test_forged_decline_sample_is_well_formed_and_found`.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
IMPLEMENT_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"

# This task's own new shared literal -- declared locally, matching the
# repository's convention of re-declaring constants per test module rather
# than importing them.
BATCH_AUDIT_PATH_LITERAL = "feature-docs/{feature}/phase-state/batch-audit.yaml"
PHASE_STATE_DOC_LITERAL = "references/phase-state.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse markdown line-wrap whitespace to single spaces, matching
    this repository's existing convention (e.g.
    tests/test_batch_quiet_output_discipline.py) so a matcher is
    insensitive to where a prose line happens to wrap."""
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
    matching tests/test_batch_quiet_output_discipline.py's convention."""
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
# Matcher: persisted-source-row (AC-1 supplementary check, AC-3)
# ---------------------------------------------------------------------------


def _row_names_persisted_site(table_text, item_phrase, path_literal, assembled_required):
    """Finds the row whose first cell contains `item_phrase`; True when its
    last cell names `path_literal` and, if `assembled_required`, also
    contains "assembled"."""
    for row in _table_rows(table_text):
        if item_phrase in row[0]:
            cell = row[-1]
            if path_literal not in cell:
                return False
            if assembled_required and "assembled" not in cell:
                return False
            return True
    return False


FORGED_TABLE_MISSING_PATH_LITERAL = (
    "| Audit item | Persisted source |\n"
    "|---|---|\n"
    "| Every unlisted-gate fallback resolution | recorded in the run report |\n"
)

FORGED_TABLE_WELL_FORMED = (
    "| Audit item | Persisted source |\n"
    "|---|---|\n"
    "| Every unlisted-gate fallback resolution | `feature-docs/{feature}/"
    "phase-state/batch-audit.yaml`, from which the run report is assembled |\n"
)


class TestPersistedSourceRowMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_row_names_persisted_site`."""

    def test_forged_row_is_well_formed_and_found(self):
        rows = _table_rows(FORGED_TABLE_WELL_FORMED)
        self.assertEqual(len(rows), 1)
        self.assertTrue(
            _row_names_persisted_site(
                FORGED_TABLE_WELL_FORMED,
                "unlisted-gate fallback resolution",
                BATCH_AUDIT_PATH_LITERAL,
                assembled_required=True,
            )
        )

    def test_rejects_forged_row_missing_the_path_literal(self):
        rows = _table_rows(FORGED_TABLE_MISSING_PATH_LITERAL)
        self.assertEqual(len(rows), 1)
        self.assertFalse(
            _row_names_persisted_site(
                FORGED_TABLE_MISSING_PATH_LITERAL,
                "unlisted-gate fallback resolution",
                BATCH_AUDIT_PATH_LITERAL,
                assembled_required=True,
            )
        )


# ---------------------------------------------------------------------------
# Matcher: exception-set (AC-2)
# ---------------------------------------------------------------------------


def _exceptions_bullet_count(section_text):
    return len([line for line in section_text.splitlines() if line.strip().startswith("- ")])


_UNLISTED_GATE_UNSUPPRESSED_RE = re.compile(
    r"unlisted-gate fallback[\s\S]{0,200}?unsuppressed"
)


def _unlisted_gate_unsuppressed_phrase_present(text):
    """True when the document pairs 'unlisted-gate fallback' with
    'unsuppressed' within 200 characters -- the phrasing this task removes
    from the Exceptions section."""
    return bool(_UNLISTED_GATE_UNSUPPRESSED_RE.search(_normalize_ws(text)))


FORGED_THREE_BULLET_EXCEPTIONS = (
    "- A turn that reaches any stop point keeps its full output.\n"
    "- Step C's completion processing emits its final report in full.\n"
    "- A `--once` phase-boundary turn emits the terminal line and withholds\n"
    "  all other narration.\n"
)

FORGED_FOUR_BULLET_EXCEPTIONS = FORGED_THREE_BULLET_EXCEPTIONS + (
    "- A turn that resolves a non-packet unlisted-gate fallback emits that\n"
    "  resolution line unsuppressed.\n"
)

FORGED_PAIRING_SAMPLE = (
    "A turn that resolves a non-packet unlisted-gate fallback (the review "
    "phase diff-size gate or the per-command approval fallback) emits that "
    "resolution line unsuppressed."
)

FORGED_NON_PAIRING_SAMPLE = (
    "A turn that resolves a non-packet unlisted-gate fallback records its "
    "resolution in a persisted file, and the persisted file is what the "
    "run report is later assembled from, so the resolution never appears "
    "as running output at all, and the whole point of persisting it this "
    "way instead of the old channel is exactly to avoid emitting anything "
    "for it. Some unrelated turn elsewhere in the document stays "
    "unsuppressed for a completely different reason."
)


class TestExceptionSetMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_exceptions_bullet_count`."""

    def test_forged_three_and_four_bullet_samples_are_well_formed(self):
        self.assertEqual(_exceptions_bullet_count(FORGED_THREE_BULLET_EXCEPTIONS), 3)
        self.assertEqual(_exceptions_bullet_count(FORGED_FOUR_BULLET_EXCEPTIONS), 4)

    def test_rejects_forged_four_bullet_exceptions(self):
        self.assertNotEqual(_exceptions_bullet_count(FORGED_FOUR_BULLET_EXCEPTIONS), 3)


class TestUnlistedGateUnsuppressedPhraseMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_unlisted_gate_unsuppressed_phrase_present`."""

    def test_forged_pairing_sample_is_well_formed_and_found(self):
        self.assertIn("unlisted-gate fallback", FORGED_PAIRING_SAMPLE)
        self.assertIn("unsuppressed", FORGED_PAIRING_SAMPLE)
        self.assertTrue(_unlisted_gate_unsuppressed_phrase_present(FORGED_PAIRING_SAMPLE))

    def test_rejects_forged_sample_without_the_pairing(self):
        self.assertIn("unlisted-gate fallback", FORGED_NON_PAIRING_SAMPLE)
        self.assertIn("unsuppressed", FORGED_NON_PAIRING_SAMPLE)
        self.assertFalse(
            _unlisted_gate_unsuppressed_phrase_present(FORGED_NON_PAIRING_SAMPLE)
        )


# ---------------------------------------------------------------------------
# Matcher: mode-independent-commit (AC-4)
# ---------------------------------------------------------------------------


def _mode_independent_single_line_commit_stated(text):
    """True when, within 400 characters after 'Then commit', the text
    states a single-line message and never mentions `--batch` -- i.e. the
    message construction does not branch on mode."""
    idx = text.find("Then commit")
    if idx == -1:
        return False
    window = text[idx : idx + 400]
    return "single-line message" in window and "--batch" not in window


FORGED_MODE_DEPENDENT_COMMIT = (
    "Then commit — for an interactive run, with a single-line message; "
    "for a `--batch` run, whose message's first line is the subject and "
    "one additional body line per declined task."
)

FORGED_MODE_INDEPENDENT_COMMIT = (
    "Then commit, with a single-line message mode-independently (the "
    "third argument is the expected_base_tip check value): "
    "`commit-docs.sh ... \"docs(...): implement wake phase reconcile\" "
    "\"$RECONCILE_TIP\"`."
)


class TestModeIndependentCommitMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_mode_independent_single_line_commit_stated`."""

    def test_forged_mode_independent_sample_is_well_formed(self):
        self.assertIn("Then commit", FORGED_MODE_INDEPENDENT_COMMIT)
        self.assertIn("single-line message", FORGED_MODE_INDEPENDENT_COMMIT)
        self.assertTrue(
            _mode_independent_single_line_commit_stated(FORGED_MODE_INDEPENDENT_COMMIT)
        )

    def test_rejects_forged_sample_naming_batch_in_the_commit_clause(self):
        self.assertIn("Then commit", FORGED_MODE_DEPENDENT_COMMIT)
        self.assertIn("single-line message", FORGED_MODE_DEPENDENT_COMMIT)
        self.assertFalse(
            _mode_independent_single_line_commit_stated(FORGED_MODE_DEPENDENT_COMMIT)
        )


# ---------------------------------------------------------------------------
# Matcher: decline-persistence (AC-5)
# ---------------------------------------------------------------------------


def _decline_persisted_under_phase_state(text):
    """True when, within 400 characters of an 'evidence part' occurrence,
    the text names `BATCH_AUDIT_PATH_LITERAL`, states the write happens in
    the same wake commit, and states the run-report obligation is
    satisfied from that channel rather than this wake phase's own
    report."""
    text = _normalize_ws(text)
    idx = text.find("evidence part")
    while idx != -1:
        window = text[max(0, idx - 400) : idx + 400]
        if (
            BATCH_AUDIT_PATH_LITERAL in window
            and "same wake commit" in window
            and "own report" in window
            and ("rather than" in window or "instead" in window)
        ):
            return True
        idx = text.find("evidence part", idx + 1)
    return False


FORGED_DECLINE_SAMPLE_WELL_FORMED = (
    "a decline's audit record is written to "
    f"`{BATCH_AUDIT_PATH_LITERAL}` in the same wake commit, naming which "
    "of the three evidence parts was missing, rather than in this wake "
    "phase's own report; the run-report obligation is satisfied by "
    "reading it from there."
)

FORGED_DECLINE_SAMPLE_MISSING_PATH = (
    "a decline's audit record is written elsewhere in the same wake "
    "commit, naming which of the three evidence parts was missing, "
    "rather than in this wake phase's own report; the run-report "
    "obligation is satisfied by reading it from there."
)


class TestDeclinePersistenceMatcherNegativeProof(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_decline_persisted_under_phase_state`."""

    def test_forged_decline_sample_is_well_formed_and_found(self):
        self.assertIn("evidence part", FORGED_DECLINE_SAMPLE_WELL_FORMED)
        self.assertIn(BATCH_AUDIT_PATH_LITERAL, FORGED_DECLINE_SAMPLE_WELL_FORMED)
        self.assertTrue(
            _decline_persisted_under_phase_state(FORGED_DECLINE_SAMPLE_WELL_FORMED)
        )

    def test_rejects_forged_sample_missing_the_path_literal(self):
        self.assertIn("evidence part", FORGED_DECLINE_SAMPLE_MISSING_PATH)
        self.assertNotIn(BATCH_AUDIT_PATH_LITERAL, FORGED_DECLINE_SAMPLE_MISSING_PATH)
        self.assertFalse(
            _decline_persisted_under_phase_state(FORGED_DECLINE_SAMPLE_MISSING_PATH)
        )


# ---------------------------------------------------------------------------
# AC-1 (supplementary): the source-map row also points at phase-state.md
# ---------------------------------------------------------------------------


class TestAC1SourceMapRowPointsAtPhaseStateDoc(unittest.TestCase):
    """AC-1 supplementary: the primary red-to-green signal is
    tests/test_batch_quiet_output_discipline.py's
    TestAuditItemSourceMap.test_source_map_has_one_row_per_audit_item
    (unmodified). This module additionally confirms the row cites
    references/phase-state.md, using the same persisted-source-row
    matcher AC-3 uses below."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.quiet_section = _slice(cls.text, "## Batch quiet output")

    def test_source_map_row_names_batch_audit_path(self):
        self.assertTrue(
            _row_names_persisted_site(
                self.quiet_section,
                "unlisted-gate fallback resolution",
                BATCH_AUDIT_PATH_LITERAL,
                assembled_required=False,
            )
        )

    def test_source_map_row_cites_phase_state_doc(self):
        for row in _table_rows(self.quiet_section):
            if "unlisted-gate fallback resolution" in row[0]:
                self.assertIn(PHASE_STATE_DOC_LITERAL, row[-1])
                return
        self.fail("no source-map row found for 'unlisted-gate fallback resolution'")


# ---------------------------------------------------------------------------
# AC-2: exactly three exceptions; the fourth-bullet phrase is gone
# ---------------------------------------------------------------------------


class TestAC2ExceptionsAreExactlyThree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.exceptions_section = _slice(
            cls.text, "**Exceptions.**", "**Audit-item source map.**"
        )

    def test_exceptions_section_has_exactly_three_bullets(self):
        self.assertEqual(_exceptions_bullet_count(self.exceptions_section), 3)

    def test_unlisted_gate_unsuppressed_pairing_absent_from_whole_document(self):
        self.assertFalse(_unlisted_gate_unsuppressed_phrase_present(self.text))

    def test_stop_abort_step_c_once_boundary_exceptions_retained(self):
        # Regression guard: the three retained exceptions are untouched.
        normalized = _normalize_ws(self.exceptions_section)
        self.assertIn("keeps its full output", normalized)
        self.assertIn("Step C's completion processing emits its final report in full", normalized)
        self.assertIn("withholds all other narration", normalized)


# ---------------------------------------------------------------------------
# AC-3: both Non-packet gates rows name the persisted record site
# ---------------------------------------------------------------------------


class TestAC3NonPacketGatesRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.gates_section = _slice(cls.text, "## Non-packet gates", "## workflow.yaml")

    def test_diff_size_gate_row_names_persisted_site_and_assembly(self):
        self.assertTrue(
            _row_names_persisted_site(
                self.gates_section,
                "Review phase diff-size gate",
                BATCH_AUDIT_PATH_LITERAL,
                assembled_required=True,
            )
        )

    def test_per_command_approval_row_names_persisted_site_and_assembly(self):
        self.assertTrue(
            _row_names_persisted_site(
                self.gates_section,
                "Per-command approval fallback",
                BATCH_AUDIT_PATH_LITERAL,
                assembled_required=True,
            )
        )

    def test_table_still_has_exactly_ten_data_rows(self):
        self.assertEqual(len(_table_rows(self.gates_section)), 10)

    def test_catch_all_paragraph_retained(self):
        # Regression guard: the catch-all paragraph after the table.
        self.assertIn(
            "follows Codex consultation first, the minimum-side-effect option",
            self.gates_section,
        )

    def test_unlisted_gate_fallback_wording_retained(self):
        self.assertIn(
            "unlisted-gate fallback procedure", self.gates_section
        )

    def test_question_resolution_doc_cited(self):
        self.assertIn("references/question-resolution.md", self.gates_section)

    def test_per_literal_command_string_wording_retained(self):
        self.assertIn("per literal command string", self.gates_section)

    def test_codex_consultation_precedes_minimum_side_effect_fallback(self):
        for row in _table_rows(self.gates_section):
            if "Per-command approval fallback" in row[0]:
                cell = row[-1]
                self.assertLess(
                    cell.index("Codex consultation"),
                    cell.index("minimum-side-effect option"),
                )
                return
        self.fail("Per-command approval fallback row not found")


# ---------------------------------------------------------------------------
# AC-4: I.2.b step 3's commit is mode-independent; DECLINED is gone
# ---------------------------------------------------------------------------


class TestAC4ModeIndependentWakeCommit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PATH)
        cls.i2b = _slice(cls.text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")

    def test_step3_commit_message_construction_is_mode_independent(self):
        self.assertTrue(_mode_independent_single_line_commit_stated(self.i2b))

    def test_declined_literal_absent_from_whole_document(self):
        self.assertNotIn("DECLINED", self.text)

    def test_message_extension_rule_absent(self):
        self.assertNotIn("message extended by", self.text)
        self.assertNotIn("additional body line per declined task", self.text)

    def test_reconcile_tip_still_stated_as_expected_base_tip(self):
        self.assertIn(
            "`$RECONCILE_TIP` third argument is\n   `commit-docs.sh`'s "
            "`expected_base_tip` check value",
            self.i2b,
        )

    def test_commit_literal_survives_the_edit(self):
        # Regression guard: the exact line-wrap literal other pre-existing
        # modules pin is untouched by this task's edit.
        self.assertIn(
            '`commit-docs.sh {integration_worktree} "docs({feature}): '
            'implement wake\n   phase reconcile" "$RECONCILE_TIP"`',
            self.i2b,
        )


# ---------------------------------------------------------------------------
# AC-5: the wake "Batch mode" paragraph persists the decline to phase-state
# ---------------------------------------------------------------------------


class TestAC5DeclinePersistedUnderPhaseState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PATH)
        cls.i2b = _slice(cls.text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")
        idx = cls.i2b.index("**Batch mode**: for a `--batch` run")
        cls.batch_mode_paragraph = cls.i2b[idx:]

    def test_decline_persisted_under_phase_state(self):
        self.assertTrue(_decline_persisted_under_phase_state(self.batch_mode_paragraph))

    def test_admission_record_stated_unchanged(self):
        self.assertIn("admission's audit record is unchanged", self.batch_mode_paragraph)

    def test_interactive_wake_report_behaviour_stated_unchanged(self):
        self.assertIn("An interactive run keeps", self.batch_mode_paragraph)
        self.assertIn(
            "this wake phase's own report exactly as before", self.batch_mode_paragraph
        )

    def test_where_the_decision_persists_paragraph_retained(self):
        # Regression guard: the pre-existing paragraph this clause follows.
        self.assertIn(
            "**Where the decision persists**: an admission's audit record "
            "is the",
            self.i2b,
        )

    def test_batch_run_report_obligation_sentence_retained(self):
        # Regression guard (D5, carried into D9): the sentence this
        # task's channel satisfies is unchanged.
        self.assertIn(
            "and, for a `--batch` run,\n   also in the run report.",
            self.i2b,
        )


# ---------------------------------------------------------------------------
# AC-6: phase-state.md defines the batch audit record file
# ---------------------------------------------------------------------------


class TestAC6PhaseStateDocDefinesBatchAuditFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.file_layout = _slice(cls.text, "## File layout", "## Schema")
        cls.subsection = _slice(
            cls.text, "## Batch audit record file", "## Legacy feature compatibility"
        )

    def test_file_layout_lists_batch_audit_yaml(self):
        self.assertIn("batch-audit.yaml", self.file_layout)

    def test_subsection_exists_before_legacy_compatibility(self):
        idx_subsection = self.text.index("## Batch audit record file")
        idx_legacy = self.text.index("## Legacy feature compatibility")
        self.assertLess(idx_subsection, idx_legacy)

    def test_subsection_states_purpose(self):
        self.assertIn(
            "holds the batch audit\nrecords that no per-phase phase-state "
            "file owns",
            self.subsection,
        )

    def test_subsection_states_entry_shape_reuses_answers(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn("reuses the `answers` entry shape", normalized)

    def test_subsection_states_two_writers(self):
        self.assertIn("references/batch-mode.md", self.subsection)
        self.assertIn("references/implement-phase.md", self.subsection)
        self.assertEqual(
            self.subsection.count("Two writers append to this file"), 1
        )

    def test_subsection_states_append_only_rule(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn("append-only", normalized)
        self.assertIn("never rewritten or removed", normalized)

    def test_subsection_states_committed_by_existing_call_never_extra_commit(self):
        normalized = _normalize_ws(self.subsection)
        self.assertIn("commit-docs.sh", normalized)
        self.assertIn(
            "never itself the reason to create a commit that would not "
            "otherwise happen",
            normalized,
        )

    def test_backfill_discovery_persistence_sibling_untouched(self):
        # Regression guard: the precedent subsection this task cites is
        # not rewritten.
        self.assertIn("### Backfill discovery persistence", self.text)


# ---------------------------------------------------------------------------
# AC-7: pointers between documents (delegated in full to
# tests/test_check_plugin_invariants.py for the no-new-gate_id obligation)
# ---------------------------------------------------------------------------


class TestAC7DocumentsPointAtEachOther(unittest.TestCase):
    def test_batch_mode_source_map_row_cites_phase_state_doc(self):
        text = _read(BATCH_MODE_PATH)
        quiet_section = _slice(text, "## Batch quiet output")
        self.assertIn(PHASE_STATE_DOC_LITERAL, quiet_section)

    def test_implement_phase_batch_mode_paragraph_cites_phase_state_doc(self):
        text = _read(IMPLEMENT_PATH)
        i2b = _slice(text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")
        idx = i2b.index("**Batch mode**: for a `--batch` run")
        self.assertIn(PHASE_STATE_DOC_LITERAL, i2b[idx:])

    def test_no_new_gate_id_mention_in_batch_mode_or_implement_phase(self):
        # Regression guard: this task's edits (the two Non-packet gates
        # cells, the source-map row, the Exceptions bullet removal, the
        # wake commit clause and the "Batch mode" paragraph) introduce no
        # NEW `gate_id` mention -- the count stays at each document's
        # pre-task0005 baseline (implement-phase.md already carries none,
        # per tests/test_batch_quiet_output_phase_wiring.py's
        # BASELINE_GATE_ID_COUNTS; batch-mode.md's eight pre-existing
        # mentions are all in `## Purpose & activation` / `## Non-packet
        # gates`' prose, none of which this task touches).
        self.assertEqual(_read(BATCH_MODE_PATH).count("gate_id"), 8)
        self.assertEqual(_read(IMPLEMENT_PATH).count("gate_id"), 0)


# ---------------------------------------------------------------------------
# Files exist / module is standard-library-only / discoverable
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_all_three_documents_exist(self):
        for path in (BATCH_MODE_PATH, IMPLEMENT_PATH, PHASE_STATE_PATH):
            self.assertTrue(path.is_file(), f"expected {path} to exist")


if __name__ == "__main__":
    unittest.main()
