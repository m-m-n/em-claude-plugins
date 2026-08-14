"""Tests for task0001 (recycled-task-id-consistency): harmonizing the
recycled-task-id rule across its four sites and gating the I.2.c route-back
on a terminal-journal-event precondition, in
`em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/recycled-task-id-consistency/tasks/task0001.md):

- AC-1 (FR1): Step I.2.b step 3's `failed` write-back is keyed off step 1's
  reconciled state, not off the journal last event directly; the
  journal-only phrasing is gone; the `merged` half and the
  report-is-`failed`/malformed clause are unchanged.
- AC-2 (FR2): I.2.a keeps the sole normative recycled-task-id statement;
  I.2.b step 1 keeps its citation of it unchanged.
- AC-3 (FR3): the I.2.c route-back bullet gains a terminal-journal-last-
  event precondition, positioned before the ordered workflow.yaml write
  set; the existing "no task has status `merged`" gate survives.
- AC-4 (FR4): a non-terminal journal last event makes route-back
  INAPPLICABLE -- no partial write, `implement` stays `failed`, report
  names the offending tasks, control returns via develop's stop condition
  3 / "abort phase"; no "rework" or "append" anywhere in I.2.c.
- AC-5 (FR5): I.2.a states id recycling arises only through I.2.c's
  route-back plus the planner's `replace_all` renumbering, and that,
  given AC-3's precondition, `status: pending` + journal last event
  `launched` can never arise; the retained in-flight sentence survives.
- AC-6 (FR6): a sentence scopes the recycled-task-id rule to the
  orchestrator's interpretation of the journal, naming all four hooks and
  stating they never consult `tasks.{T}.status` (never the stronger,
  false "never reads workflow.yaml").
- AC-7 (NFR1, NFR3, NFR4): the full suite (including the six protected
  pre-existing modules) stays green; no bare `git ... commit`/`add -A`
  line is introduced -- verified by the untouched
  tests/test_implement_routeback_gate.py and by running the whole suite.
- AC-8 (NFR5): this module exists, is discovered, implements TS-1 .. TS-10,
  and gives each new matcher a negative-proof test.

Content assertions compare against a whitespace-normalized copy of each
section (line-wrap choices never make an assertion brittle); byte-identity
assertions (TS-7, TS-8, TS-9) compare the raw, un-normalized text.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
NEXT_SECTION_HEADING = "### Supporting cast"

# The removed, journal-only write-back phrasing (TS-1 / AC-1).
OLD_JOURNAL_ONLY_PHRASE = "for every task whose last journal event is `failed`"

# TS-9's byte-identical literal, copied here per the task plan rather than
# imported from tests/test_implement_routeback_gate.py (that module is not
# imported and not modified).
PRE_CHANGE_BATCH_MODE_PARAGRAPH = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase** (implement\n"
    "stays `failed`, report and stop; the external service cuts a follow-up\n"
    "task). Route-back-to-planning is never taken automatically. Track the\n"
    "retry-consumed state per task in `tasks.{T}.notes`.\n"
    "\n"
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _i2b_section(text):
    start = text.index(I2B_HEADING, text.index(I2A_HEADING))
    end = text.index(I2C_HEADING, start)
    return text[start:end]


def _i2c_section(text):
    start = text.index(I2C_HEADING)
    end = text.index(NEXT_SECTION_HEADING, start)
    return text[start:end]


class TestWakePhaseWriteBackKeyedOffReconciledState(unittest.TestCase):
    """TS-1 / AC-1 (FR1): step 3's `failed` write-back names step 1's
    reconciled state; the journal-only phrasing is gone; the `merged` half
    and the report-is-`failed`/malformed clause survive."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2b_section(_read()))

    def test_reconciled_state_phrasing_present(self):
        self.assertIn("step 1 reconciled state is `failed`", self.section)

    def test_journal_only_phrasing_absent(self):
        self.assertNotIn(OLD_JOURNAL_ONLY_PHRASE, self.section)

    def test_merged_half_unchanged(self):
        self.assertIn(
            "set `tasks.{T}.status = merged` for every task verified merged",
            self.section,
        )

    def test_report_failed_or_malformed_clause_survives(self):
        self.assertIn("or whose report is `failed`/malformed", self.section)


class TestRecycledTaskIdRuleStaysSingleSource(unittest.TestCase):
    """TS-2 / AC-2 (FR2): I.2.a keeps the sole normative statement; I.2.b
    step 1 keeps its citation of it unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.i2a = _normalize_ws(_i2a_section(cls.text))
        cls.i2b = _normalize_ws(_i2b_section(cls.text))

    def test_i2a_normative_statement_present(self):
        self.assertIn(
            "Recycled task id: workflow.yaml's status wins over a stale "
            "journal event here",
            self.i2a,
        )

    def test_i2b_step1_citation_present(self):
        self.assertIn("the recycled-task-id rule in I.2.a above", self.i2b)


class TestRouteBackPreconditionRequiresTerminalEvent(unittest.TestCase):
    """TS-3 / AC-3 (FR3): the precondition names a terminal journal last
    event with both `merged` and `failed`, positioned before the ordered
    write set; the existing "no task has status `merged`" gate survives."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_precondition_names_terminal_event_with_merged_and_failed(self):
        self.assertIn(
            "terminal journal last event (`merged` or `failed`)", self.section
        )

    def test_precondition_precedes_ordered_write_set(self):
        precondition_idx = self.section.index(
            "terminal journal last event (`merged` or `failed`)"
        )
        write_set_idx = self.section.index("`create-plan` to `needs_update`")
        self.assertLess(precondition_idx, write_set_idx)

    def test_existing_merged_gate_survives(self):
        self.assertIn("no task has status `merged`", self.section)


class TestNonTerminalEventMakesRouteBackInapplicable(unittest.TestCase):
    """TS-4 / AC-4 (FR4): a non-terminal journal last event makes
    route-back INAPPLICABLE: `implement` stays `failed`, control returns
    via develop's stop condition 3 / "abort phase"; no "rework" or
    "append" anywhere in I.2.c."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2c_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_inapplicable_branch_states_implement_stays_failed(self):
        self.assertIn("INAPPLICABLE", self.section)
        self.assertIn("implement` stays `failed`", self.section)

    def test_inapplicable_branch_cites_stop_condition_3_and_abort_phase(self):
        # Anchor on "INAPPLICABLE" (new text) so this proves the NEW
        # branch cites stop condition 3 / abort phase, not merely that
        # the pre-existing merged-task branch already did.
        idx = self.section.index("INAPPLICABLE")
        branch = self.section[idx:]
        self.assertIn("stop condition 3", branch)
        self.assertIn('the same terminal as the "abort phase" option below', branch)

    def test_inapplicable_branch_names_no_partial_write(self):
        self.assertIn("no part of the write set runs", self.section)
        self.assertIn("no partial-write path", self.section)

    def test_no_rework_or_append_anywhere_in_i2c(self):
        self.assertNotIn("rework", self.section)
        self.assertNotIn("append", self.section)


class TestUnreachablePendingLaunchedCombination(unittest.TestCase):
    """TS-5 / AC-5 (FR5): the unreachability sentence mentions the
    planner's `replace_all` renumbering together with `launched` and
    `pending`; the retained in-flight sentence survives."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2a_section(_read()))

    def test_unreachability_sentence_present(self):
        idx = self.section.index("Given I.2.c's route-back precondition")
        end = self.section.index("can never arise.", idx) + len("can never arise.")
        sentence = self.section[idx:end]
        self.assertIn("replace_all", sentence)
        self.assertIn("launched", sentence)
        self.assertIn("pending", sentence)

    def test_retained_in_flight_sentence_survives(self):
        self.assertIn(
            "A task whose journal last event is `launched` is always "
            "in-flight, regardless of workflow.yaml `status`",
            self.section,
        )


class TestRecycledTaskIdRuleScopedToOrchestrator(unittest.TestCase):
    """TS-6 / AC-6 (FR6): the scope sentence names all four hook
    filenames and states `tasks.{T}.status` is never consulted; the
    document nowhere contains "never read workflow.yaml"."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.i2a = _normalize_ws(_i2a_section(cls.text))

    def test_scope_sentence_names_all_four_hooks(self):
        for hook in (
            "queue_launch_guard.py",
            "queue_stop_guard.py",
            "queue_failure_net.py",
            "queue_taskstop_net.py",
        ):
            self.assertIn(f"`{hook}`", self.i2a)

    def test_scope_sentence_states_status_never_consulted(self):
        self.assertIn("never consult `tasks.{T}.status`", self.i2a)

    def test_scope_sentence_governs_only_orchestrator_interpretation(self):
        self.assertIn(
            "governs only the orchestrator's interpretation of the journal",
            self.i2a,
        )

    def test_no_never_reads_workflow_yaml_claim_anywhere(self):
        self.assertNotIn("never read workflow.yaml", self.text)
        self.assertNotIn("never reads workflow.yaml", self.text)


class TestProtectedRawLiteralsSurvive(unittest.TestCase):
    """TS-7: both line-wrap-sensitive literals of IMPLEMENTATION.md D3 are
    present in the raw (un-normalized) text, with the Step I.0 one
    occurring earlier in the file than the Step I.2.a one."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_step_i2a_select_literal_survives(self):
        literal = (
            "`tasks.*.status`. Select\n"
            "unlaunched tasks (no journal event yet and `status != merged`, "
            "ascending"
        )
        self.assertIn(
            literal,
            self.text,
            "Step I.2.a's `Select` / `unlaunched tasks (...) ascending` "
            "line-wrap literal was reflowed",
        )

    def test_step_i0_pending_literal_survives(self):
        literal = 'in `tasks` whose\n   `status == pending`'
        self.assertIn(
            literal,
            self.text,
            "Step I.0's `require at least one task in `tasks` whose` / "
            "`status == pending` line-wrap literal was reflowed",
        )

    def test_step_i0_literal_precedes_step_i2a_literal(self):
        i0_idx = self.text.index('in `tasks` whose\n   `status == pending`')
        i2a_idx = self.text.index(
            "`tasks.*.status`. Select\nunlaunched tasks (no journal event "
            "yet and `status != merged`, ascending"
        )
        self.assertLess(i0_idx, i2a_idx)


class TestWakePhaseCommitLiteralSurvives(unittest.TestCase):
    """TS-8: the I.2.b step 3 commit literal survives with its exact
    newline and three-space continuation indent."""

    def test_commit_literal_survives(self):
        literal = (
            '`commit-docs.sh {integration_worktree} "docs({feature}): '
            "implement wake\n"
            '   phase reconcile" "$RECONCILE_TIP"`'
        )
        self.assertIn(
            literal,
            _read(),
            "I.2.b step 3's commit-docs.sh line-wrap literal was reflowed",
        )


class TestI2cHeadingAndBatchModeParagraphByteIdentical(unittest.TestCase):
    """TS-9: the I.2.c heading is byte-identical, and the batch-mode
    paragraph is still the byte-identical tail of the I.2.c section."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_is_byte_identical(self):
        idx = self.text.index(I2C_HEADING)
        self.assertEqual(self.text[idx: idx + len(I2C_HEADING)], I2C_HEADING)

    def test_batch_mode_paragraph_is_byte_identical_tail(self):
        section = _i2c_section(self.text)
        start = section.index("Batch mode (`references/batch-mode.md`")
        actual = section[start:]
        self.assertEqual(actual, PRE_CHANGE_BATCH_MODE_PARAGRAPH)


class TestI2cOrderings(unittest.TestCase):
    """TS-10: normalized I.2.c orderings survive -- first `tasks.{T}.status`
    has `pending` within 60 characters; the four write tokens precede
    `git worktree remove --force`; cleanup precedes the first
    `commit-docs.sh`, which precedes `End the phase with a`."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i2c_section(_read()))

    def test_first_tasks_status_has_pending_within_60_chars(self):
        idx = self.section.index("tasks.{T}.status")
        window = self.section[idx: idx + 60]
        self.assertIn("pending", window)

    def test_write_tokens_precede_cleanup(self):
        cleanup_idx = self.section.index("git worktree remove --force")
        for token in (
            "`create-plan` to `needs_update`",
            "`implement` step back to `pending`",
            "`tasks.{T}.status` back to `pending`",
            "`tasks.{T}.notes`",
        ):
            self.assertLess(self.section.index(token), cleanup_idx)

    def test_cleanup_precedes_commit_precedes_end_of_phase_report(self):
        cleanup_idx = self.section.index("git worktree remove --force")
        commit_idx = self.section.index("commit-docs.sh")
        report_idx = self.section.index("End the phase with a")
        self.assertLess(cleanup_idx, commit_idx)
        self.assertLess(commit_idx, report_idx)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test) -- one
    negative-proof per new matcher, demonstrated against pre-change (or
    hypothetically-bad) wording samples."""

    def test_journal_only_phrase_matcher_flags_the_pre_change_wording(self):
        sample = (
            "set `tasks.{T}.status = merged` for every task verified "
            "merged, `= failed` for every task whose last journal event "
            "is `failed` or whose report is `failed`/malformed"
        )
        self.assertIn(OLD_JOURNAL_ONLY_PHRASE, sample)

    def test_never_reads_workflow_yaml_matcher_flags_the_bad_wording(self):
        sample = (
            "these hooks derive a task's state from the journal alone "
            "and never read workflow.yaml"
        )
        self.assertIn("never read workflow.yaml", sample)

    def test_precondition_matcher_flags_absence_in_pre_change_wording(self):
        # The I.2.c route-back bullet's opening, as it read before this
        # task's edit -- no terminal-journal-event precondition anywhere.
        sample = _normalize_ws(
            "This automatic re-entry applies only when no task has status "
            "`merged` — the absence of any `merged` task; the drain above "
            "has already retired every `in_progress` sibling by this "
            "point. Refresh the integration worktree first (`git -C "
            '"$WT_ROOT/integration" reset --hard '
            "em-workflow/{feature}/integration`), then capture..."
        )
        self.assertNotIn("terminal journal last event", sample)

    def test_rework_append_matcher_flags_the_bad_wording(self):
        sample = "the failed task is queued for rework before the next retry"
        self.assertIn("rework", sample)
        other_sample = "the failure reason is appended to the report"
        self.assertIn("append", other_sample)


if __name__ == "__main__":
    unittest.main()
