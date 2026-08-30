"""Tests for task0003 (batch-quiet-output): wiring the phase protocols to
the batch output-suppression discipline.

Covers task0003 Acceptance Criteria
(feature-docs/batch-quiet-output/tasks/task0003.md):

- AC-1 (FR2, FR12): `implement-phase.md`'s launch-turn (I.2.a) and
  wake-turn (I.2.b) turn-ending instructions each state that in a
  `--batch` run the final assistant message is the marker line
  `references/batch-mode.md` defines and nothing else, naming that
  document and reproducing no literal from it.
- AC-2 (FR4, FR9, FR10): the wake phase's reconcile / cleanup / refill
  narration and I.2.c's drain-and-retry narration are stated as withheld
  in batch, each paired with a statement that the underlying writes
  (reconcile, commits, journal, worktree cleanup, task status, counters)
  are unchanged.
- AC-3 (FR11, NFR3): a declined `files` deviation's audit record is stated
  to be written, for a `--batch` run, to the persisted batch audit record
  file under `phase-state/` in the same wake commit, naming the failed
  evidence part, with the run-report obligation satisfied from that
  channel; the admitted-deviation record and the interactive wake-report
  behaviour are unchanged.

  Amended by task0005 (rework round 1, finding `9d1f4e6a2c8b0537`): the
  channel a decline's audit record rides is no longer the wake commit's
  message body -- it is `references/phase-state.md`'s
  `phase-state/batch-audit.yaml`, written in that same wake commit. This
  docstring and this module's own assertions naming that channel were
  updated to match; `_decline_channel_stated` itself asserts only the
  contract-level property (record directed away from the suppressed wake
  report, run-report obligation satisfied from elsewhere) and needed no
  change.
- AC-4 (FR4, FR9): `review-phase.md` Phase R6 states the report body is not
  emitted into the main context in `--batch` while the round record's
  content/fields/write timing are unchanged; Phase R5's auto-rework/defer
  behaviour, cap and `resolution_reason` wording are unchanged.
- AC-5 (FR6, NFR3): implement's second-failure abort and any Phase R5
  abort are covered by the stop/abort exception, stated by reference.
- AC-6 (FR12, NFR4): `phases/create-spec-phase.md` and
  `phases/create-plan-phase.md` each carry exactly one pointer sentence at
  their completion site; none of the four documents restates the marker
  format/suppressed-scope/exception list, none contains the marker prefix
  literal or any IMPLEMENTATION.md D6(b) literal, and no new `gate_id`
  mention appears.
- AC-7 (FR10, NFR1): existing gate rows / policy references / caps /
  counters / status-transition rules are retained verbatim (regression
  guards, exempt from the negative-proof requirement below).

This module never asserts what `references/batch-mode.md` itself defines
(task0001's file may not have merged into this worktree yet) -- the marker
prefix literal below is declared locally for ABSENCE checks only.

Matcher -> negative-proof inventory (each NEW matcher carries a negative
proof over a forged sample plus a non-vacuity guard; pure regression pins
over retained pre-change wording are exempt):

- `_marker_only_turn_matches` (marker-only-turn matcher): negative proof is
  `test_rejects_sample_missing_and_nothing_else`; non-vacuity guard is
  `test_accepts_well_formed_forged_sample`.
- `_pointer_by_reference` (pointer-site matcher): negative proof is
  `test_rejects_sample_without_the_pointer`; non-vacuity guard is
  `test_accepts_well_formed_forged_sample`.
- `_withheld_paired_with_unchanged` (withheld-with-unchanged-writes
  matcher): negative proof is
  `test_rejects_withheld_with_no_nearby_unchanged`; non-vacuity guard is
  `test_accepts_well_formed_forged_sample`.
- `_decline_channel_stated` (decline-channel matcher): negative proof is
  `test_rejects_sample_missing_evidence_part`; non-vacuity guard is
  `test_accepts_well_formed_forged_sample`.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

IMPLEMENT_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
REVIEW_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"

FOUR_DOC_PATHS = [IMPLEMENT_PATH, REVIEW_PATH, CREATE_SPEC_PATH, CREATE_PLAN_PATH]

POINTER_LITERAL = "references/batch-mode.md"

# --- D6(b) / marker-prefix literal absence guards -- declared locally,
# never imported from another test module or from batch-mode.md, per the
# task's Test Notes (task0001's file may not have merged into this
# worktree yet).
MARKER_PREFIX_LITERAL = "EM_WORKFLOW_PROGRESS:"
TERMINAL_PREFIX_LITERAL = "EM_WORKFLOW_TERMINAL:"
ELEVEN_REASON_CODES = [
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
]
NO_STEP_SENTINEL_LITERAL = "no-step"
PHASE_DONE_LITERAL = "phase_done"
FORBIDDEN_LITERALS = (
    [MARKER_PREFIX_LITERAL, TERMINAL_PREFIX_LITERAL]
    + ELEVEN_REASON_CODES
    + [NO_STEP_SENTINEL_LITERAL, PHASE_DONE_LITERAL]
)

# gate_id occurrence counts as this task found them when it started --
# task0003 introduces no new gate_id mention in any of the four documents
# (AC-6), so these counts must not grow.
BASELINE_GATE_ID_COUNTS = {
    IMPLEMENT_PATH: 0,
    REVIEW_PATH: 0,
    CREATE_SPEC_PATH: 5,
    CREATE_PLAN_PATH: 1,
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_marker, end_marker=None):
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


def _normalize_ws(text):
    """Collapse markdown line-wrap whitespace to single spaces, matching
    this repository's existing convention (e.g.
    `tests/test_phase_protocols.py`) so a matcher is insensitive to where a
    prose line happens to wrap."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------

_MARKER_ONLY_TURN_RE = re.compile(
    r"[Ii]n a `--batch` run,? .{0,200}?this (?:wake )?turn's final assistant "
    r"message is the marker line `references/batch-mode\.md` defines "
    r"and nothing else"
)


def _marker_only_turn_matches(text):
    """AC-1 matcher: every turn-ending clause stating that in `--batch` the
    turn's final assistant message is the marker line and nothing else."""
    return _MARKER_ONLY_TURN_RE.findall(_normalize_ws(text))


def _pointer_by_reference(text, anchor_phrase, window=500):
    """AC-5/AC-6 matcher: within `window` characters up to and including
    `anchor_phrase`, `references/batch-mode.md` is named (a pointer, never
    a restatement) and none of the forbidden literals appear in that
    window."""
    text = _normalize_ws(text)
    idx = text.find(anchor_phrase)
    if idx == -1:
        return False
    start = max(0, idx - window)
    segment = text[start: idx + len(anchor_phrase)]
    if POINTER_LITERAL not in segment:
        return False
    for forbidden in FORBIDDEN_LITERALS:
        if forbidden in segment:
            return False
    return True


def _withheld_paired_with_unchanged(text, suppression_terms, max_gap=700):
    """AC-2/AC-4 matcher: a suppression term (e.g. "withheld", "not
    emitted into the main context") is followed, within `max_gap`
    characters, by the word "unchanged" -- the withholding statement is
    paired with a statement that specific writes survive it."""
    text = _normalize_ws(text)
    for term in suppression_terms:
        idx = text.find(term)
        while idx != -1:
            gap_end = text.find("unchanged", idx)
            if gap_end != -1 and (gap_end - idx) <= max_gap:
                return True
            idx = text.find(term, idx + 1)
    return False


def _decline_channel_stated(text):
    """AC-3 matcher: a `--batch` decline's audit record is stated to be
    carried by a channel other than this wake phase's own (suppressed)
    report, naming the failed evidence part, and the run-report obligation
    is stated to be satisfied from that other channel. This validates the
    contract-level property (record directed away from the suppressed
    report) rather than hardcoding the phase protocol's literal choice of
    channel."""
    text = _normalize_ws(text)
    idx = text.find("evidence part")
    while idx != -1:
        window = text[max(0, idx - 300): idx + 500]
        if (
            "run-report obligation" in window
            and "satisfied" in window
            and "own report" in window
            and ("rather than" in window or "instead" in window)
        ):
            return True
        idx = text.find("evidence part", idx + 1)
    return False


# ---------------------------------------------------------------------------
# Matcher self-tests: negative proof + non-vacuity guard per new matcher
# ---------------------------------------------------------------------------


class TestMarkerOnlyTurnMatcher(unittest.TestCase):
    def test_rejects_sample_missing_and_nothing_else(self):
        forged = (
            "In a `--batch` run, this turn's final assistant message is "
            "the marker line `references/batch-mode.md` defines."
        )
        self.assertEqual(_marker_only_turn_matches(forged), [])

    def test_accepts_well_formed_forged_sample(self):
        forged = (
            "In a `--batch` run, this wake turn's final assistant message "
            "is the marker line `references/batch-mode.md` defines and "
            "nothing else."
        )
        self.assertEqual(len(_marker_only_turn_matches(forged)), 1)


class TestPointerByReferenceMatcher(unittest.TestCase):
    def test_rejects_sample_without_the_pointer(self):
        forged = "this is a stop under the stop/abort exception, full stop."
        self.assertFalse(_pointer_by_reference(forged, "stop/abort exception"))

    def test_rejects_sample_with_forbidden_literal_in_window(self):
        forged = (
            "references/batch-mode.md names step_stuck near the stop/abort "
            "exception."
        )
        self.assertFalse(_pointer_by_reference(forged, "stop/abort exception"))

    def test_accepts_well_formed_forged_sample(self):
        forged = "a stop under `references/batch-mode.md`'s stop/abort exception."
        self.assertTrue(_pointer_by_reference(forged, "stop/abort exception"))


class TestWithheldPairedWithUnchangedMatcher(unittest.TestCase):
    def test_rejects_withheld_with_no_nearby_unchanged(self):
        forged = "the narration is withheld from the main context in batch."
        self.assertFalse(_withheld_paired_with_unchanged(forged, ["withheld"]))

    def test_accepts_well_formed_forged_sample(self):
        forged = (
            "the narration is withheld from the main context, while the "
            "commit and the journal write are unchanged."
        )
        self.assertTrue(_withheld_paired_with_unchanged(forged, ["withheld"]))


class TestDeclineChannelMatcher(unittest.TestCase):
    def test_rejects_sample_missing_evidence_part(self):
        forged = "the decline rides elsewhere rather than in this own report."
        self.assertFalse(_decline_channel_stated(forged))

    def test_rejects_sample_missing_satisfied(self):
        forged = (
            "a decline's record rides elsewhere, naming which evidence "
            "part failed, rather than in this wake phase's own report; "
            "the run-report obligation is separate."
        )
        self.assertFalse(_decline_channel_stated(forged))

    def test_rejects_sample_not_distinguished_from_report(self):
        forged = (
            "a decline's audit record is carried elsewhere, naming which "
            "of the three evidence parts was missing; the run-report "
            "obligation is satisfied by reading it."
        )
        self.assertFalse(_decline_channel_stated(forged))

    def test_accepts_well_formed_forged_sample(self):
        forged = (
            "a decline's audit record is carried elsewhere, naming which "
            "of the three evidence parts was missing, rather than in this "
            "wake phase's own report; the run-report obligation is "
            "satisfied by reading it there."
        )
        self.assertTrue(_decline_channel_stated(forged))


# ---------------------------------------------------------------------------
# AC-1: launch-turn and wake-turn marker-only clauses
# ---------------------------------------------------------------------------


class TestAC1MarkerOnlyTurns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PATH)
        cls.i2a = _slice(cls.text, "### I.2.a: Launch phase", "### I.2.b: Wake phase")
        cls.i2b = _slice(cls.text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")

    def test_launch_turn_states_marker_only_message(self):
        matches = _marker_only_turn_matches(self.i2a)
        self.assertEqual(len(matches), 1, self.i2a)

    def test_wake_turn_states_marker_only_message(self):
        matches = _marker_only_turn_matches(self.i2b)
        self.assertEqual(len(matches), 1, self.i2b)

    def test_launch_clause_does_not_restate_marker_prefix_or_fields(self):
        clause = self.i2a
        for forbidden in FORBIDDEN_LITERALS:
            self.assertNotIn(forbidden, clause)

    def test_wake_clause_does_not_restate_marker_prefix_or_fields(self):
        clause = self.i2b
        for forbidden in FORBIDDEN_LITERALS:
            self.assertNotIn(forbidden, clause)

    def test_launch_guard_journal_write_sentence_retained(self):
        # Regression guard (FR9/FR10): the pre-existing launch-guard/journal
        # sentence is not rewritten or removed by the new clause.
        self.assertIn(
            "records\neach allowed launch as a `launched` journal event",
            self.i2a,
        )


# ---------------------------------------------------------------------------
# AC-2: wake-phase narration withheld, I.2.c drain/retry narration withheld,
# paired with unchanged writes
# ---------------------------------------------------------------------------


class TestAC2WakePhaseWithheldWritesUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PATH)
        cls.i2b = _slice(cls.text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")
        cls.i2c = _slice(cls.text, "### I.2.c: Failed handling", "### Supporting cast")

    def test_wake_reconcile_cleanup_refill_withheld_paired_with_unchanged(self):
        self.assertTrue(
            _withheld_paired_with_unchanged(self.i2b, ["withheld"]),
            self.i2b,
        )

    def test_wake_clause_names_reconcile_commit_cleanup_as_unchanged(self):
        idx = self.i2b.index("are withheld from the main context")
        tail = self.i2b[idx:]
        self.assertIn("reconcile itself", tail)
        self.assertIn("wake commit", tail)
        self.assertIn("worktree cleanup", tail)

    def test_i2c_drain_and_retry_narration_withheld_paired_with_unchanged(self):
        self.assertTrue(
            _withheld_paired_with_unchanged(self.i2c, ["withheld"]),
            self.i2c,
        )

    def test_i2c_withheld_clause_names_task_status_and_failed_write_as_unchanged(self):
        idx = self.i2c.index("are withheld\nfrom the main context")
        tail = self.i2c[idx:]
        self.assertIn("task status", tail)
        self.assertIn("`failed` write", tail)

    def test_reconcile_step_1_wording_retained(self):
        # Regression guard: step 1's reconcile enumeration itself (what is
        # being withheld) is not rewritten.
        self.assertIn("**Reconcile**", self.i2b)

    def test_cleanup_step_4_wording_retained(self):
        self.assertIn("**Clean up**", self.i2b)

    def test_refill_step_5_wording_retained(self):
        self.assertIn("**Refill**", self.i2b)

    def test_retry_once_gate_wording_retained(self):
        # Regression guard (FR10): the batch retry-once / abort-on-second
        # -failure gate wording is unchanged.
        self.assertIn("auto-select **retry** ONCE per task", self.i2c)
        self.assertIn("A task that fails a second time", self.i2c)


# ---------------------------------------------------------------------------
# AC-3: declined-deviation audit channel moves to the persisted batch
# audit record file, written in the wake commit (task0005)
# ---------------------------------------------------------------------------


class TestAC3DeclineChannel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PATH)
        cls.i2b = _slice(cls.text, "### I.2.b: Wake phase", "### I.2.c: Failed handling")

    def test_decline_channel_stated(self):
        self.assertTrue(_decline_channel_stated(self.i2b), self.i2b)

    def test_admission_record_stated_unchanged(self):
        idx = self.i2b.index("**Batch mode**: for a `--batch` run")
        tail = self.i2b[idx:]
        self.assertIn("admission's audit record is unchanged", tail)

    def test_interactive_wake_report_behaviour_stated_unchanged(self):
        idx = self.i2b.index("**Batch mode**: for a `--batch` run")
        tail = self.i2b[idx:]
        self.assertIn("An interactive run keeps", tail)
        self.assertIn("this wake phase's own report exactly as before", tail)

    def test_pre_existing_where_decision_persists_paragraph_retained(self):
        # Regression guard: the pre-existing paragraph this clause follows
        # is not rewritten or removed.
        self.assertIn(
            "**Where the decision persists**: an admission's audit record "
            "is the",
            self.i2b,
        )
        self.assertIn(
            "A decline's audit record is the\n   reason recorded in this "
            "wake phase's own report",
            self.i2b,
        )

    def test_pre_existing_batch_run_report_obligation_sentence_retained(self):
        # Regression guard (D5): the pre-existing sentence this task's
        # channel satisfies is not rewritten.
        self.assertIn(
            "and, for a `--batch` run,\n   also in the run report.",
            self.i2b,
        )


# ---------------------------------------------------------------------------
# AC-4: review-phase.md Phase R6 withheld / Phase R5 unchanged
# ---------------------------------------------------------------------------


class TestAC4ReviewPhaseR5R6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PATH)
        cls.r5 = _slice(
            cls.text,
            "## Phase R5: Persist the round record",
            "## Phase R6: Report (Japanese)",
        )
        cls.r6 = _slice(cls.text, "## Phase R6: Report (Japanese)")

    def test_r6_report_body_withheld_paired_with_round_record_unchanged(self):
        self.assertTrue(
            _withheld_paired_with_unchanged(
                self.r6, ["not emitted into the main context"]
            ),
            self.r6,
        )

    def test_r6_clause_names_round_record_content_fields_write_timing(self):
        normalized = _normalize_ws(self.r6)
        idx = normalized.index("not emitted into the main context")
        tail = normalized[idx:]
        self.assertIn("content", tail)
        self.assertIn("fields", tail)
        self.assertIn("write timing", tail)

    def test_r5_auto_rework_defer_cap_counter_record_stated_unchanged(self):
        idx = self.r5.index(
            "This batch auto-rework / defer-at-cap behaviour above"
        )
        clause = self.r5[idx:]
        self.assertIn("counter", clause)
        self.assertIn("round-record writes", clause)
        self.assertIn("unchanged", clause)

    def test_r5_abort_covered_by_pointer_to_stop_abort_exception(self):
        self.assertTrue(
            _pointer_by_reference(self.r5, "stop/abort exception"), self.r5
        )

    def test_r5_rework_cap_wording_retained(self):
        # Regression guard: the cap / resolution_reason wording is unchanged.
        self.assertIn("auto-rework with cap 1", self.r5)
        self.assertIn(
            'resolution_reason: "batch mode: rework cap reached"', self.r5
        )

    def test_r6_japanese_rendering_rules_retained(self):
        # Regression guard: the pre-existing Japanese rendering-rules
        # paragraph is not rewritten.
        self.assertIn("タメ語・女性・体言止めなし", self.text)


# ---------------------------------------------------------------------------
# AC-5: stop/abort exception coverage (implement second-failure, review R5)
# ---------------------------------------------------------------------------


class TestAC5StopAbortException(unittest.TestCase):
    def test_implement_second_failure_abort_covered_by_reference(self):
        text = _read(IMPLEMENT_PATH)
        i2c = _slice(text, "### I.2.c: Failed handling", "### Supporting cast")
        self.assertTrue(_pointer_by_reference(i2c, "stop/abort exception"), i2c)

    def test_implement_abort_report_full_output_retained(self):
        text = _read(IMPLEMENT_PATH)
        i2c = _slice(text, "### I.2.c: Failed handling", "### Supporting cast")
        idx = i2c.index("stop under\n`references/batch-mode.md`'s stop/abort exception")
        tail = i2c[idx:]
        self.assertIn("keeps\nits full output", tail)

    def test_abort_phase_existing_terminal_write_and_commit_retained(self):
        # Regression guard (FR9/FR10): the existing abort-phase write/commit
        # sequence this exception governs is not rewritten.
        text = _read(IMPLEMENT_PATH)
        i2c = _slice(text, "### I.2.c: Failed handling", "### Supporting cast")
        self.assertIn(
            'implement phase aborted" "$ABORT_TIP"`', i2c
        )


# ---------------------------------------------------------------------------
# AC-6: create-spec / create-plan pointer sentences; global literal absence;
# no new gate_id
# ---------------------------------------------------------------------------


class TestAC6PointerSites(unittest.TestCase):
    def test_create_spec_completion_site_has_exactly_one_pointer_sentence(self):
        text = _read(CREATE_SPEC_PATH)
        site = _normalize_ws(
            _slice(text, "## 13. Completion", "## Termination conditions")
        )
        matches = re.findall(
            r"In a `--batch` run, this phase's completion narration above "
            r"is withheld per `references/batch-mode\.md`'s "
            r"output-suppression discipline;[^.]*\.",
            site,
        )
        self.assertEqual(len(matches), 1, site)

    def test_create_plan_completion_site_has_exactly_one_pointer_sentence(self):
        text = _read(CREATE_PLAN_PATH)
        site = _normalize_ws(
            _slice(
                text,
                "## 11. Completion or failure",
                "## 12. Declared change set derivation",
            )
        )
        matches = re.findall(
            r"In a `--batch` run, this phase's completion narration above "
            r"is withheld per `references/batch-mode\.md`'s "
            r"output-suppression discipline;[^.]*\.",
            site,
        )
        self.assertEqual(len(matches), 1, site)

    def test_create_spec_pointer_names_batch_mode_without_forbidden_literal(self):
        text = _read(CREATE_SPEC_PATH)
        site = _slice(text, "## 13. Completion", "## Termination conditions")
        self.assertTrue(
            _pointer_by_reference(site, "output-suppression"), site
        )

    def test_create_plan_pointer_names_batch_mode_without_forbidden_literal(self):
        text = _read(CREATE_PLAN_PATH)
        site = _slice(
            text,
            "## 11. Completion or failure",
            "## 12. Declared change set derivation",
        )
        self.assertTrue(
            _pointer_by_reference(site, "output-suppression"), site
        )

    def test_create_spec_pointer_does_not_reorder_existing_steps(self):
        # Regression guard: the four numbered completion steps precede the
        # new pointer sentence; none is rewritten or reordered.
        text = _read(CREATE_SPEC_PATH)
        site = _slice(text, "## 13. Completion", "## Termination conditions")
        idx_step4 = site.index(
            "4. Set `phase-state/create-spec.yaml`'s `status` to `completed`."
        )
        idx_pointer = site.index("In a `--batch` run")
        self.assertLess(idx_step4, idx_pointer)

    def test_create_plan_pointer_does_not_reorder_existing_bullets(self):
        text = _read(CREATE_PLAN_PATH)
        site = _slice(
            text,
            "## 11. Completion or failure",
            "## 12. Declared change set derivation",
        )
        idx_bullet2 = site.index("applying_patch`, not yet applied).")
        idx_pointer = site.index("In a `--batch` run")
        self.assertLess(idx_bullet2, idx_pointer)


class TestAC6ForbiddenLiteralsAbsentAndGateIdUnchanged(unittest.TestCase):
    def test_marker_prefix_literal_absent_from_all_four_documents(self):
        for path in FOUR_DOC_PATHS:
            self.assertNotIn(MARKER_PREFIX_LITERAL, _read(path), path)

    def test_terminal_prefix_literal_absent_from_all_four_documents(self):
        for path in FOUR_DOC_PATHS:
            self.assertNotIn(TERMINAL_PREFIX_LITERAL, _read(path), path)

    def test_d6b_reason_codes_absent_from_all_four_documents(self):
        for path in FOUR_DOC_PATHS:
            text = _read(path)
            for code in ELEVEN_REASON_CODES:
                self.assertNotIn(code, text, f"{code} found in {path}")

    def test_no_step_sentinel_absent_from_all_four_documents(self):
        for path in FOUR_DOC_PATHS:
            self.assertNotIn(NO_STEP_SENTINEL_LITERAL, _read(path), path)

    def test_phase_done_literal_absent_from_all_four_documents(self):
        for path in FOUR_DOC_PATHS:
            self.assertNotIn(PHASE_DONE_LITERAL, _read(path), path)

    def test_gate_id_mention_count_unchanged_per_document(self):
        for path, baseline in BASELINE_GATE_ID_COUNTS.items():
            actual = _read(path).count("gate_id")
            self.assertEqual(
                actual,
                baseline,
                f"{path} gate_id count changed from {baseline} to {actual} "
                "-- task0003 must not introduce a new gate_id mention",
            )


# ---------------------------------------------------------------------------
# AC-7: files exist / module is standard-library-only / discoverable
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_all_four_documents_exist(self):
        for path in FOUR_DOC_PATHS:
            self.assertTrue(path.is_file(), f"expected {path} to exist")


if __name__ == "__main__":
    unittest.main()
