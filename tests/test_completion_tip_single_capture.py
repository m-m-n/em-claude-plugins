"""Tests for task0001 (completion-tip-single-capture): Step I.3 of
`em-workflow/references/implement-phase.md` names the step-1
`$COMPLETION_TIP` capture as the single source of the `completed_at_commit`
value in the command sequence itself, including on an exit-4 retry.

Covers task0001 Acceptance Criteria
(feature-docs/completion-tip-single-capture/tasks/task0001.md):

- AC-1 (FR1, TS1): in the whitespace-normalized Step I.3 section, the span
  from "on the worktree just refreshed" up to the next "commit-docs.sh"
  contains `completed_at_commit` and `$COMPLETION_TIP`, and states that the
  written `completed_at_commit` is step 1's `$COMPLETION_TIP` and that the
  opening sentence's command substitution is not evaluated separately.
- AC-2 (FR1, TS2): that same span contains neither "rev-parse" nor "$(git",
  and step 3 as a whole contains no command substitution of its own.
- AC-3 (FR2, TS3): one sentence-or-paragraph of Step I.3 refers to the exit-4
  retry and contains `completed_at_commit` and `$COMPLETION_TIP`, stating that
  `completed_at_commit` is re-written with the freshly re-captured
  `$COMPLETION_TIP`, the value passed as `commit-docs.sh`'s third argument on
  that retry.
- AC-4 (FR4, TS4): a verbatim pre-change step 3 sample is held in this
  module; the TS1 matcher yields no match on it; a non-vacuity guard asserts
  the sample is non-empty and contains `completed_at_commit`; the module
  imports only the standard library and no other test module.

AC-5 / AC-6 / AC-7 are covered by the existing tests passing unmodified
(`tests/test_rework_synthesis_contract.py`,
`tests/test_exit4_tip_argument_consistency.py`,
`tests/test_tip_capture_idiom_uniformity.py`), a full-suite run, and the
task's diff scope; they are not re-asserted here.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import from, and is not imported by, any other test module.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

STEP_I3_HEADING = "## Step I.3: Phase completion"
FAILURE_CONTAINMENT_HEADING = "## Failure containment"

# The write anchor: step 3 of Step I.3's normative sequence. Also the anchor
# used by tests/test_exit4_tip_argument_consistency.py.
WRITE_ANCHOR = "on the worktree just refreshed"
COMMIT_DOCS = "commit-docs.sh"
COMPLETED_AT_COMMIT = "completed_at_commit"
COMPLETION_TIP = "$COMPLETION_TIP"

STEP3_MARKER = "3. **write**"
STEP4_MARKER = "4. **commit**"

# Binding wording asserted in step 3 (AC-1). Each constant is read by its
# positive test; the pre-change sample below lacks both.
BINDING_PHRASE = "captured in step 1"
NOT_EVALUATED_PHRASE = "is not evaluated as a separate command"

# Exit-4 retry wording asserted in Step I.3 (AC-3).
EXIT4_RETRY_PHRASE = "exit-4 retry"
REWRITTEN_PHRASE = "re-written"
RECAPTURED_PHRASE = "re-captured"
THIRD_ARGUMENT_PHRASE = "third argument"

# --- pre-change wording samples, copied verbatim from the base revision of
# em-workflow/references/implement-phase.md BEFORE this task's edit landed.
# Not paraphrased, not reconstructed after the edit.

SAMPLE_STEP3_PRE_CHANGE = (
    "3. **write**, on the worktree just refreshed, the `implement` step's\n"
    "   `status = completed` and `completed_at_commit` set above\n"
    "4. **commit** that write with the captured tip as the third argument —\n"
    '   `commit-docs.sh {integration_worktree} "docs({feature}): implement phase\n'
    '   completed" "$COMPLETION_TIP"` (the third argument is `expected_base_tip`;\n'
    "   exit-4 recovery: Branch & Worktree Model above)\n"
)

SAMPLE_CLOSING_PARAGRAPH_PRE_CHANGE = (
    "`$COMPLETION_TIP` and the `completed_at_commit` value above are both\n"
    "derived from the same step-1 capture, so they denote the SAME commit. On\n"
    "an exit-4 retry, both values are re-derived together from a fresh\n"
    "capture, so this invariant continues to hold across retries.\n"
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _i3_section(text):
    start = text.index(STEP_I3_HEADING)
    end = text.index(FAILURE_CONTAINMENT_HEADING, start)
    return text[start:end]


def _write_span(normalized):
    """The text from the first write anchor up to the next `commit-docs.sh`
    in an already whitespace-normalized text. Fails explicitly when either
    end is missing -- a missing anchor never yields an empty span that a
    matcher could pass or fail vacuously."""
    start = normalized.find(WRITE_ANCHOR)
    if start == -1:
        raise AssertionError(f"write anchor {WRITE_ANCHOR!r} not found")
    end = normalized.find(COMMIT_DOCS, start)
    if end == -1:
        raise AssertionError(
            f"{COMMIT_DOCS!r} not found after the write anchor"
        )
    return normalized[start:end]


def _ts1_matches(text):
    """TS1 matcher: the write span contains `completed_at_commit` and
    `$COMPLETION_TIP`."""
    span = _write_span(_normalize_ws(text))
    return COMPLETED_AT_COMMIT in span and COMPLETION_TIP in span


def _step3_text(normalized_section):
    """Step 3 of the normative sequence, from its marker up to step 4's
    marker, in an already whitespace-normalized section."""
    start = normalized_section.index(STEP3_MARKER)
    end = normalized_section.index(STEP4_MARKER, start)
    return normalized_section[start:end]


def _paragraphs(raw_section):
    """Blank-line-separated blocks of a raw (un-normalized) section, each
    whitespace-normalized."""
    return [
        _normalize_ws(block).strip()
        for block in re.split(r"\n\s*\n", raw_section)
        if block.strip()
    ]


def _is_exit4_retry_rewrite_unit(unit):
    """TS3 matcher: a unit (sentence-or-paragraph) that refers to the
    exit-4 retry, contains `completed_at_commit` and `$COMPLETION_TIP`, and
    states the re-write from the re-captured value passed as
    `commit-docs.sh`'s third argument. Excludes the step 1-4 list block,
    which carries the exit-4 cross-reference and both tokens but is not the
    retry statement."""
    return (
        WRITE_ANCHOR not in unit
        and EXIT4_RETRY_PHRASE in unit
        and COMPLETED_AT_COMMIT in unit
        and COMPLETION_TIP in unit
        and REWRITTEN_PHRASE in unit
        and RECAPTURED_PHRASE in unit
        and THIRD_ARGUMENT_PHRASE in unit
    )


class TestStep3BindsCompletedAtCommitToStepOneCapture(unittest.TestCase):
    """AC-1 / TS1: step 3's span names step 1's `$COMPLETION_TIP` as the
    `completed_at_commit` value and says the opening sentence's command
    substitution is not evaluated separately."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i3_section(_read()))
        cls.span = _write_span(cls.section)

    def test_span_contains_completed_at_commit_and_completion_tip(self):
        self.assertIn(COMPLETED_AT_COMMIT, self.span)
        self.assertIn(COMPLETION_TIP, self.span)
        self.assertTrue(_ts1_matches(_i3_section(_read())))

    def test_span_binds_the_written_value_to_the_step_one_capture(self):
        self.assertIn(BINDING_PHRASE, self.span)

    def test_span_states_the_opening_substitution_is_not_evaluated(self):
        self.assertIn(NOT_EVALUATED_PHRASE, self.span)

    def test_binding_wording_does_not_repeat_the_write_anchor(self):
        self.assertEqual(self.section.count(WRITE_ANCHOR), 1)


class TestStep3HasNoCommandSubstitutionOfItsOwn(unittest.TestCase):
    """AC-2 / TS2: the write span and step 3 as a whole carry no capture
    expression of their own."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i3_section(_read()))
        cls.span = _write_span(cls.section)
        cls.step3 = _step3_text(cls.section)

    def test_span_contains_no_rev_parse(self):
        self.assertNotIn("rev-parse", self.span)

    def test_span_contains_no_git_command_substitution(self):
        self.assertNotIn("$(git", self.span)

    def test_step3_as_a_whole_contains_no_rev_parse(self):
        self.assertNotIn("rev-parse", self.step3)

    def test_step3_as_a_whole_contains_no_command_substitution(self):
        self.assertNotIn("$(", self.step3)


class TestExit4RetryRewritesFromRecapturedTip(unittest.TestCase):
    """AC-3 / TS3: Step I.3 states, in one unit, that on an exit-4 retry
    `completed_at_commit` is re-written with the freshly re-captured
    `$COMPLETION_TIP`, the value passed as `commit-docs.sh`'s third argument
    on that retry."""

    @classmethod
    def setUpClass(cls):
        cls.units = _paragraphs(_i3_section(_read()))

    def test_one_unit_states_the_exit4_retry_rewrite(self):
        matching = [u for u in self.units if _is_exit4_retry_rewrite_unit(u)]
        self.assertTrue(
            matching,
            "no Step I.3 paragraph states that completed_at_commit is "
            "re-written from the re-captured $COMPLETION_TIP on an exit-4 "
            "retry",
        )

    def test_retry_statement_sits_after_the_commit_step(self):
        section = _normalize_ws(_i3_section(_read()))
        commit_idx = section.index(COMMIT_DOCS, section.index(WRITE_ANCHOR))
        statement = next(
            (u for u in self.units if _is_exit4_retry_rewrite_unit(u)), None
        )
        self.assertIsNotNone(statement, "exit-4 retry statement not found")
        self.assertGreater(section.index(statement), commit_idx)


class TestWritePathIsNotRewordedAroundThePinnedSentence(unittest.TestCase):
    """Guard for the section-wide constraints the new wording must obey
    (the existing modules assert the same things on the whole section; this
    pins the part this task adds)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_i3_section(_read()))

    def test_section_has_exactly_one_tip_capture_expression(self):
        self.assertEqual(self.section.count("COMPLETION_TIP=$(git"), 1)

    def test_section_has_exactly_one_hard_reset(self):
        self.assertEqual(self.section.count("reset --hard"), 1)

    def test_no_hard_reset_onto_the_completion_tip(self):
        self.assertNotIn('reset --hard "$COMPLETION_TIP"', self.section)
        self.assertNotIn("reset --hard $COMPLETION_TIP", self.section)

    def test_first_commit_docs_after_the_anchor_is_step_fours_invocation(self):
        span_end = self.section.index(WRITE_ANCHOR)
        span_end = self.section.index(COMMIT_DOCS, span_end)
        invocation = self.section[span_end:]
        self.assertTrue(
            invocation.startswith(
                'commit-docs.sh {integration_worktree} "docs({feature}): '
                'implement phase completed" "$COMPLETION_TIP"'
            )
        )


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4 / TS4: proof that the matchers fail meaningfully -- demonstrated
    against verbatim pre-change samples, each with a non-vacuity guard so
    the proof cannot silently degrade into a tautology."""

    def test_ts1_matcher_yields_no_match_on_pre_change_step3(self):
        self.assertFalse(_ts1_matches(SAMPLE_STEP3_PRE_CHANGE))

    def test_pre_change_sample_is_non_vacuous(self):
        # Non-vacuity guard: the sample is non-empty, still carries
        # `completed_at_commit`, and still has both ends of the span, so the
        # no-match above comes from the missing `$COMPLETION_TIP` rather than
        # from a missing anchor.
        self.assertTrue(SAMPLE_STEP3_PRE_CHANGE.strip())
        self.assertIn(COMPLETED_AT_COMMIT, SAMPLE_STEP3_PRE_CHANGE)
        self.assertIn(
            "`status = completed` and `completed_at_commit` set above",
            _normalize_ws(SAMPLE_STEP3_PRE_CHANGE),
        )
        span = _write_span(_normalize_ws(SAMPLE_STEP3_PRE_CHANGE))
        self.assertIn(COMPLETED_AT_COMMIT, span)
        self.assertNotIn(COMPLETION_TIP, span)

    def test_binding_phrases_absent_from_pre_change_sample(self):
        sample = _normalize_ws(SAMPLE_STEP3_PRE_CHANGE)
        self.assertNotIn(BINDING_PHRASE, sample)
        self.assertNotIn(NOT_EVALUATED_PHRASE, sample)

    def test_ts3_matcher_yields_no_match_on_pre_change_closing_paragraph(self):
        self.assertFalse(
            _is_exit4_retry_rewrite_unit(
                _normalize_ws(SAMPLE_CLOSING_PARAGRAPH_PRE_CHANGE)
            )
        )

    def test_pre_change_closing_paragraph_is_non_vacuous(self):
        # Non-vacuity guard: the paragraph carries the exit-4 reference and
        # both tokens, so only the re-write / re-capture statement is
        # missing.
        unit = _normalize_ws(SAMPLE_CLOSING_PARAGRAPH_PRE_CHANGE)
        self.assertIn(EXIT4_RETRY_PHRASE, unit)
        self.assertIn(COMPLETED_AT_COMMIT, unit)
        self.assertIn(COMPLETION_TIP, unit)

    def test_write_span_fails_explicitly_when_anchor_is_missing(self):
        with self.assertRaises(AssertionError):
            _write_span(_normalize_ws("3. **write** the status, then commit"))

    def test_write_span_fails_explicitly_when_commit_docs_is_missing(self):
        with self.assertRaises(AssertionError):
            _write_span(
                _normalize_ws("3. **write**, on the worktree just refreshed, x")
            )


if __name__ == "__main__":
    unittest.main()
