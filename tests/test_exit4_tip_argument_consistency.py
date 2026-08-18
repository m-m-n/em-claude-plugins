"""Tests for task0001 (exit4-tip-argument): making Step I.2.a's launch-time
task status / task branch write and Step I.3's implement-completed /
completed-commit write pass a captured `expected_base_tip` as
`commit-docs.sh`'s third argument, in
`em-workflow/references/implement-phase.md`.

Covers task0001 Acceptance Criteria
(feature-docs/exit4-tip-argument/tasks/task0001.md):

- AC-1 (FR2, NFR1): Step I.2.a's text contains, in order, the tip capture
  into a named variable, the refresh of the integration worktree to exactly
  that captured tip, the `tasks.{T}.status = in_progress` /
  `tasks.{T}.branch` write for every task selected in that single entry, and
  a `commit-docs.sh` invocation naming every such task whose third argument
  is the captured variable; ordering is normative (capture precedes
  refresh, refresh precedes write, write precedes commit) and exit-4
  cross-references the Branch & Worktree Model.
- AC-2 (FR3, NFR1): Step I.3's text contains the same four elements in the
  same order (capture, refresh to the captured tip, write, commit) for the
  implement-completed / completed-commit write, with the same exit-4
  cross-reference.
- AC-3 (FR4): the Step I.3 completion sentence survives byte-for-byte
  including its internal newline; every element AC-2 adds lies strictly
  before or strictly after that span; the rework-synthesis contract test
  module is absent from this task's diff (not asserted here -- a diff
  property, not a document property).
- AC-4 (FR5): Step I.2.a states that this capture/refresh/write/commit
  sequence runs ONCE per entry into Step I.2.a, including the refill
  re-entry from Step I.2.b step 5, covering every task selected in that
  entry with a single capture, a single refresh, one write set, and one
  commit; a fresh tip is captured on every such entry; `$RECONCILE_TIP` is
  never reused as the third argument; every occurrence of `RECONCILE_TIP`
  inside the I.2.a section lies within that statement.
- AC-5 (FR1, NFR4): every call site the exit-4 recovery bullet enumerates
  has a three-argument `commit-docs.sh` invocation in its own step's text;
  the bullet's enumeration wording and Step I.2.c's route-back carve-out are
  unchanged.
- AC-6 (NFR2, NFR3): full-suite green and retention inventory hold (checked
  by running the whole suite, not by this module alone).
- AC-7: this module exists, is discovered by
  `python3 -m unittest discover -s tests`, imports only the standard
  library and no other test module, covers TS3 / TS4 / TS5 and the
  six-site correspondence, and gives every new-wording matcher a negative
  proof against a captured pre-change sample plus a non-vacuity guard.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import from, and is not imported by, any other test module.

Content assertions compare against a whitespace-normalized copy of the
relevant section (line-wrap choices never make a prose assertion brittle);
byte-identity assertions compare the raw, un-normalized text -- the two are
never mixed in one assertion (IMPLEMENTATION.md Conventions).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
STEP_I3_HEADING = "## Step I.3: Phase completion"
FAILURE_CONTAINMENT_HEADING = "## Failure containment"
BRANCH_WORKTREE_HEADING = "## Branch & Worktree Model"
STEP_I0_HEADING = "## Step I.0"

# --- module-level constants for every matcher asserting NEW post-change
# wording. Each constant is read by both its positive test and its
# negative-proof test below -- the literal is never spelled twice.

LAUNCH_TIP_CAPTURE = (
    "LAUNCH_TIP=$(git -C {integration_worktree} rev-parse "
    "em-workflow/{feature}/integration)"
)
LAUNCH_REFRESH_CMD = 'git -C {integration_worktree} reset --hard "$LAUNCH_TIP"'
LAUNCH_TIP_WRITE_STATUS = "tasks.{T}.status = in_progress"
LAUNCH_TIP_WRITE_BRANCH = "tasks.{T}.branch"
LAUNCH_TIP_COMMIT_THIRD_ARG = '"$LAUNCH_TIP"'

COMPLETION_TIP_CAPTURE = (
    "COMPLETION_TIP=$(git -C {integration_worktree} rev-parse "
    "em-workflow/{feature}/integration)"
)
COMPLETION_REFRESH_CMD = (
    'git -C {integration_worktree} reset --hard "$COMPLETION_TIP"'
)
COMPLETION_TIP_WRITE = "status = completed"
COMPLETION_TIP_COMMIT_THIRD_ARG = '"$COMPLETION_TIP"'

# The pre-change/defective refresh: resets to the branch name rather than to
# the just-captured variable, reopening the race the capture-first ordering
# closes. Used only as a negative anchor (must NOT appear in either section).
BRANCH_NAME_REFRESH_CMD = (
    "git -C {integration_worktree} reset --hard "
    "em-workflow/{feature}/integration"
)

REFILL_STATEMENT_PHRASE = "ONCE per entry into Step I.2.a"
REFILL_REENTRY_NAMED_PHRASE = "refill re-entry from Step I.2.b step 5"
RECONCILE_TIP_NOT_REUSED_PHRASE = "$RECONCILE_TIP` is never reused"

# Pinned Step I.3 completion sentence, byte-for-byte including its internal
# newline (task0001.md Design, "Site B").
PINNED_COMPLETION_SENTENCE = (
    "When every task is `merged`: set `implement` step `status = completed`,\n"
    '`completed_at_commit = $(git rev-parse "em-workflow/{feature}/integration")`.'
)

EXIT4_CROSS_REFERENCE_PHRASE = "exit-4 recovery: Branch & Worktree Model above"

# --- pre-change wording samples, captured BEFORE this task's edit landed --
# verbatim excerpts of em-workflow/references/implement-phase.md as it read
# prior to this change. Not paraphrased, not reconstructed after the edit.

SAMPLE_I2A_PRE_CHANGE = (
    "For each selected task T, create its worktree:\n"
    "\n"
    "```bash\n"
    'git worktree add -b "em-workflow/{feature}/{T}" "$WT_ROOT/{T}" \\\n'
    '    "em-workflow/{feature}/integration"\n'
    "```\n"
    "\n"
    "Branch point = integration branch AT THIS MOMENT (includes every task "
    "merged\n"
    "so far). Set `tasks.{T}.status = in_progress`, `tasks.{T}.branch` in\n"
    "workflow.yaml.\n"
)

SAMPLE_I3_PRE_CHANGE = (
    "## Step I.3: Phase completion\n"
    "\n"
    "When every task is `merged`: set `implement` step `status = "
    "completed`,\n"
    '`completed_at_commit = $(git rev-parse "em-workflow/{feature}/'
    'integration")`.\n'
    "There is no other way to complete this phase — a non-merged task "
    "always\n"
    "resolves via retry, route-back-to-planning, or abort (I.2.c). Report "
    "overall\n"
    "stats (tasks, conflict retries, failures) in 1-3 lines and return "
    "control to\n"
    "the develop state machine (review phase follows; no test run here —\n"
    "integrated verification is the review/verify phases' job).\n"
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


def _i3_section(text):
    start = text.index(STEP_I3_HEADING)
    end = text.index(FAILURE_CONTAINMENT_HEADING, start)
    return text[start:end]


def _branch_worktree_model_section(text):
    start = text.index(BRANCH_WORKTREE_HEADING)
    end = text.index(STEP_I0_HEADING, start)
    return text[start:end]


def _bare_git_commit_or_add_lines(text):
    """Lines that are actual shell invocations (start with `git`, ignoring
    markdown backticks/indentation) touching `commit` or `add -A` -- as
    opposed to prose that merely mentions "git commit" inside a sentence."""
    out = []
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if re.match(r"^git\s", stripped) and re.search(
            r"\b(commit\b|add -A\b)", stripped
        ):
            out.append(line.strip())
    return out


class TestStepI2aLaunchTimeWriteHasTipArgument(unittest.TestCase):
    """AC-1 / TS3: Step I.2.a's text contains, in order, the tip capture,
    the refresh to that captured tip, the workflow.yaml write, and a
    commit-docs.sh invocation whose third argument is the captured
    variable."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2a_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_refresh_command_present(self):
        self.assertIn(_normalize_ws(LAUNCH_REFRESH_CMD), self.section)

    def test_tip_capture_present(self):
        self.assertIn(_normalize_ws(LAUNCH_TIP_CAPTURE), self.section)

    def test_workflow_yaml_write_present(self):
        self.assertIn(LAUNCH_TIP_WRITE_STATUS, self.section)
        self.assertIn(LAUNCH_TIP_WRITE_BRANCH, self.section)

    def test_commit_docs_invocation_with_captured_tip_present(self):
        self.assertIn("commit-docs.sh", self.section)
        self.assertIn(LAUNCH_TIP_COMMIT_THIRD_ARG, self.section)

    def test_four_elements_are_in_strictly_increasing_order(self):
        section = self.section
        capture_idx = section.index(_normalize_ws(LAUNCH_TIP_CAPTURE))
        refresh_idx = section.index(_normalize_ws(LAUNCH_REFRESH_CMD), capture_idx)
        write_idx = section.index(LAUNCH_TIP_WRITE_STATUS, refresh_idx)
        commit_idx = section.index(
            "commit-docs.sh", write_idx
        )
        arg_idx = section.index(LAUNCH_TIP_COMMIT_THIRD_ARG, commit_idx)
        self.assertLess(capture_idx, refresh_idx)
        self.assertLess(refresh_idx, write_idx)
        self.assertLess(write_idx, commit_idx)
        self.assertLess(commit_idx, arg_idx)

    def test_refresh_resets_to_captured_tip_not_branch_name(self):
        # Regression lock (capture-first ordering): the refresh must reset
        # to the just-captured variable, not to the branch name -- a
        # revert to `reset --hard em-workflow/{feature}/integration`
        # followed by `rev-parse HEAD` reopens the race the capture-first
        # ordering closes.
        self.assertIn(_normalize_ws(LAUNCH_REFRESH_CMD), self.section)
        self.assertNotIn(_normalize_ws(BRANCH_NAME_REFRESH_CMD), self.section)

    def test_ordering_stated_as_normative(self):
        # "task-id order" already occurs pre-change in the launch-selection
        # paragraph -- a bare substring check on "order" would pass without
        # the new sequence existing at all, so this anchors on the specific
        # normative-ordering phrase the new sequence introduces.
        self.assertIn("in this normative order", self.section)

    def test_exit4_case_cross_references_branch_worktree_model(self):
        self.assertIn(EXIT4_CROSS_REFERENCE_PHRASE, self.section)

    def test_branch_point_sentence_survives(self):
        self.assertIn(
            "Branch point = integration branch AT THIS MOMENT (includes "
            "every task merged so far).",
            self.section,
        )


class TestStepI3CompletionWriteHasTipArgument(unittest.TestCase):
    """AC-2 / TS4: Step I.3's text contains the same four elements in the
    same order for the implement-completed / completed-commit write, with
    the same exit-4 cross-reference."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i3_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_refresh_command_present(self):
        self.assertIn(_normalize_ws(COMPLETION_REFRESH_CMD), self.section)

    def test_tip_capture_present(self):
        self.assertIn(_normalize_ws(COMPLETION_TIP_CAPTURE), self.section)

    def test_workflow_yaml_write_present(self):
        # The write itself is stated by the pinned sentence (status =
        # completed / completed_at_commit); the new sequence's own write
        # step references it rather than re-stating the assignment.
        self.assertIn(COMPLETION_TIP_WRITE, self.section)
        self.assertIn("completed_at_commit", self.section)

    def test_commit_docs_invocation_with_captured_tip_present(self):
        self.assertIn("commit-docs.sh", self.section)
        self.assertIn(COMPLETION_TIP_COMMIT_THIRD_ARG, self.section)

    def test_four_elements_are_in_strictly_increasing_order(self):
        section = self.section
        capture_idx = section.index(_normalize_ws(COMPLETION_TIP_CAPTURE))
        refresh_idx = section.index(
            _normalize_ws(COMPLETION_REFRESH_CMD), capture_idx
        )
        # The pinned sentence's status=completed occurs BEFORE the new
        # sequence (it is the write the new sequence's step 3 refers back
        # to) -- so anchor the "write" element to the new sequence's own
        # step-3 text, not to the pinned sentence itself.
        write_idx = section.index("on the worktree just refreshed", refresh_idx)
        commit_idx = section.index("commit-docs.sh", write_idx)
        arg_idx = section.index(COMPLETION_TIP_COMMIT_THIRD_ARG, commit_idx)
        self.assertLess(capture_idx, refresh_idx)
        self.assertLess(refresh_idx, write_idx)
        self.assertLess(write_idx, commit_idx)
        self.assertLess(commit_idx, arg_idx)

    def test_refresh_resets_to_captured_tip_not_branch_name(self):
        # Regression lock (capture-first ordering): same guard as
        # Step I.2.a's, scoped to Step I.3's own section.
        self.assertIn(_normalize_ws(COMPLETION_REFRESH_CMD), self.section)
        self.assertNotIn(_normalize_ws(BRANCH_NAME_REFRESH_CMD), self.section)

    def test_ordering_stated_as_normative(self):
        self.assertIn("in this normative order", self.section)

    def test_exit4_case_cross_references_branch_worktree_model(self):
        self.assertIn(EXIT4_CROSS_REFERENCE_PHRASE, self.section)

    def test_pinned_sentence_precedes_new_sequence(self):
        pinned_idx = self.section.index(_normalize_ws(PINNED_COMPLETION_SENTENCE))
        capture_idx = self.section.index(_normalize_ws(COMPLETION_TIP_CAPTURE))
        self.assertLess(pinned_idx, capture_idx)


class TestStepI3PinnedCompletionSentenceByteIdentical(unittest.TestCase):
    """AC-3: the completion sentence survives byte-for-byte, including its
    internal newline, and every element the new sequence adds lies strictly
    before or strictly after that span. Raw-text assertion -- never
    normalized, since a normalized comparison would pass even if the
    internal newline were lost (the exact regression this guards)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.raw_section = _i3_section(cls.text)

    def test_pinned_sentence_present_byte_for_byte(self):
        self.assertIn(PINNED_COMPLETION_SENTENCE, self.text)

    def test_new_sequence_lies_strictly_after_the_pinned_span(self):
        pinned_start = self.raw_section.index(PINNED_COMPLETION_SENTENCE)
        pinned_end = pinned_start + len(PINNED_COMPLETION_SENTENCE)
        # Every new element (refresh / capture / commit-docs.sh) must occur
        # at or after the end of the pinned span.
        refresh_idx = self.raw_section.index(
            "git -C {integration_worktree} reset --hard", pinned_end
        )
        self.assertGreaterEqual(refresh_idx, pinned_end)
        capture_idx = self.raw_section.index("COMPLETION_TIP=", pinned_end)
        self.assertGreaterEqual(capture_idx, pinned_end)
        commit_idx = self.raw_section.index("commit-docs.sh", pinned_end)
        self.assertGreaterEqual(commit_idx, pinned_end)

    def test_there_is_no_other_way_sentence_follows_the_new_sequence(self):
        section = self.raw_section
        commit_idx = section.index("commit-docs.sh")
        no_other_way_idx = section.index(
            "There is no other way to complete this phase"
        )
        self.assertLess(commit_idx, no_other_way_idx)


class TestRefillStatement(unittest.TestCase):
    """AC-4 / TS5: the fresh-capture-on-every-entry statement names the
    refill re-entry; every occurrence of RECONCILE_TIP inside the I.2.a
    section lies within that statement and none is a commit-docs.sh third
    argument."""

    @classmethod
    def setUpClass(cls):
        cls.raw_section = _i2a_section(_read())
        cls.section = _normalize_ws(cls.raw_section)

    def test_fresh_capture_on_every_entry_stated(self):
        self.assertIn(REFILL_STATEMENT_PHRASE, self.section)

    def test_refill_reentry_named(self):
        self.assertIn(REFILL_REENTRY_NAMED_PHRASE, self.section)

    def test_reconcile_tip_never_reused_statement_present(self):
        self.assertIn(RECONCILE_TIP_NOT_REUSED_PHRASE, self.section)

    def test_every_reconcile_tip_occurrence_is_inside_the_statement(self):
        section = self.section
        not_reused_idx = section.index(RECONCILE_TIP_NOT_REUSED_PHRASE)
        # Locate the sentence boundaries around the not-reused statement:
        # the statement starts at the nearest preceding sentence break
        # (". ") or section start, and ends at the next ". " or section end.
        occurrences = [
            m.start() for m in re.finditer(r"RECONCILE_TIP", section)
        ]
        self.assertTrue(
            occurrences, "RECONCILE_TIP must be named in the refill statement"
        )
        # Determine the statement span: from the start of the sentence
        # containing "is never reused" to its terminating period.
        sentence_start = section.rfind(". ", 0, not_reused_idx)
        sentence_start = 0 if sentence_start == -1 else sentence_start + 2
        # The statement may span multiple sentences (reason clause); take
        # the whole remainder up to the next paragraph break as the
        # permitted zone, then verify no commit-docs.sh third argument
        # named RECONCILE_TIP appears anywhere in the section.
        for idx in occurrences:
            self.assertGreaterEqual(
                idx,
                sentence_start,
                "RECONCILE_TIP occurs outside the not-reused statement",
            )

    def test_reconcile_tip_never_passed_as_commit_docs_third_argument(self):
        self.assertNotIn('"$RECONCILE_TIP"', self.raw_section)


class TestSixSiteCorrespondence(unittest.TestCase):
    """FR1 / NFR4 mechanical part: each of the six enumerated call sites'
    own section contains a commit-docs.sh invocation carrying a third
    argument; the route-back carve-out is the only site excluded."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def _commit_docs_calls_with_third_arg(self, section):
        # A commit-docs.sh invocation with 3 quoted arguments: script,
        # message, tip.
        pattern = re.compile(
            r'commit-docs\.sh[^\n`]*"\$[A-Z_]+"'
        )
        return pattern.findall(_normalize_ws(section))

    def test_step_i1_baseline_commit_has_tip_argument(self):
        idx = self.text.index("## Step I.1")
        end = self.text.index("## Step I.2", idx)
        section = self.text[idx:end]
        self.assertTrue(self._commit_docs_calls_with_third_arg(section))

    def test_step_i2a_launch_time_write_has_tip_argument(self):
        section = _i2a_section(self.text)
        self.assertTrue(self._commit_docs_calls_with_third_arg(section))

    def test_step_i2b_wake_phase_commit_has_tip_argument(self):
        start = self.text.index(I2B_HEADING)
        end = self.text.index(I2C_HEADING, start)
        section = self.text[start:end]
        self.assertTrue(self._commit_docs_calls_with_third_arg(section))

    def test_step_i2c_rejected_path_terminal_commit_has_tip_argument(self):
        start = self.text.index(I2C_HEADING)
        end = self.text.index("### Supporting cast", start)
        section = self.text[start:end]
        rejected_idx = section.index("When the gate does not hold")
        abort_idx = section.index("- **abort phase**", rejected_idx)
        rejected_section = section[rejected_idx:abort_idx]
        self.assertTrue(self._commit_docs_calls_with_third_arg(rejected_section))

    def test_step_i2c_abort_phase_terminal_commit_has_tip_argument(self):
        start = self.text.index(I2C_HEADING)
        end = self.text.index("### Supporting cast", start)
        section = self.text[start:end]
        abort_idx = section.index("- **abort phase**")
        batch_idx = section.index("Batch mode (", abort_idx)
        abort_section = section[abort_idx:batch_idx]
        self.assertTrue(self._commit_docs_calls_with_third_arg(abort_section))

    def test_step_i3_completion_write_has_tip_argument(self):
        section = _i3_section(self.text)
        self.assertTrue(self._commit_docs_calls_with_third_arg(section))

    def test_step_i2c_routeback_commit_has_no_tip_argument_carve_out(self):
        start = self.text.index(I2C_HEADING)
        end = self.text.index("When the gate does not hold", start)
        routeback_section = self.text[start:end]
        self.assertIn("ROUTEBACK_TIP", routeback_section)
        # The carve-out: this call site is documented as unreachable for
        # exit 4, not as bound by the bounded recovery this task extends to
        # the other five sites.
        self.assertIn("cannot occur at this call site", routeback_section)


class TestExit4RecoveryBulletUnchanged(unittest.TestCase):
    """AC-5: the exit-4 recovery bullet's enumeration wording and Step
    I.2.c's route-back carve-out are unchanged by this task."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_branch_worktree_model_section(_read()))

    def test_bullet_names_step_i2a_launch_time_write(self):
        self.assertIn(
            "Step I.2.a's launch-time task status / task branch write",
            self.section,
        )

    def test_bullet_names_step_i3_completion_write(self):
        self.assertIn(
            "Step I.3's implement-completed / completed-commit write",
            self.section,
        )

    def test_bullet_names_all_six_sites(self):
        for phrase in (
            "Step I.1's baseline commit",
            "Step I.2.a's launch-time task status / task branch write",
            "Step I.2.b's wake-phase commit",
            "Step I.2.c's rejected-path terminal status commit",
            "Step I.2.c's abort-phase terminal status commit",
            "Step I.3's implement-completed / completed-commit write",
        ):
            self.assertIn(phrase, self.section)

    def test_routeback_carve_out_survives(self):
        self.assertIn(
            "The single carve-out is Step I.2.c's **route-back** commit",
            self.section,
        )


class TestRegressionGuards(unittest.TestCase):
    """AC-6 / NFR2, NFR3: retention inventory items scoped to this module --
    heading byte-identity, the whole-file bare-git-line invariant, and the
    Step I.2.b commit literal this task must not disturb."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_i2a_heading_is_byte_identical(self):
        idx = self.text.index(I2A_HEADING)
        self.assertEqual(self.text[idx : idx + len(I2A_HEADING)], I2A_HEADING)

    def test_i3_heading_is_byte_identical(self):
        idx = self.text.index(STEP_I3_HEADING)
        self.assertEqual(
            self.text[idx : idx + len(STEP_I3_HEADING)], STEP_I3_HEADING
        )

    def test_step_i2b_commit_literal_survives(self):
        literal = (
            '`commit-docs.sh {integration_worktree} "docs({feature}): '
            "implement wake\n"
            '   phase reconcile" "$RECONCILE_TIP"`'
        )
        self.assertIn(literal, self.text)

    def test_step_i1_commit_literal_survives(self):
        self.assertIn(
            '"docs({feature}): implement phase start" "$BASE_COMMIT"`',
            self.text,
        )

    def test_no_bare_git_commit_or_add_lines(self):
        lines = _bare_git_commit_or_add_lines(self.text)
        self.assertEqual(
            lines, [], f"unexpected raw git commit/add lines: {lines}"
        )

    def test_i2c_section_still_has_no_routeback_tip_leak_outside_routeback(self):
        section = self.text[
            self.text.index(I2C_HEADING) : self.text.index(
                "### Supporting cast"
            )
        ]
        rejected_idx = section.index("When the gate does not hold")
        after_rejected = section[rejected_idx:]
        self.assertNotIn("ROUTEBACK_TIP", after_rejected)


class TestValidationDetectsRegressions(unittest.TestCase):
    """D8 / TS-8: proof that every new-wording matcher above fails
    meaningfully -- demonstrated against captured pre-change wording
    samples, each with a non-vacuity guard so the proof cannot silently
    degrade into a tautology."""

    def test_i2a_matchers_fail_against_pre_change_sample(self):
        sample = _normalize_ws(SAMPLE_I2A_PRE_CHANGE)
        self.assertNotIn(_normalize_ws(LAUNCH_TIP_CAPTURE), sample)
        self.assertNotIn(_normalize_ws(LAUNCH_REFRESH_CMD), sample)
        self.assertNotIn(LAUNCH_TIP_COMMIT_THIRD_ARG, sample)
        self.assertNotIn(REFILL_STATEMENT_PHRASE, sample)
        self.assertNotIn(RECONCILE_TIP_NOT_REUSED_PHRASE, sample)

    def test_i2a_sample_retains_branch_point_anchor(self):
        # Non-vacuity guard: the sample still contains a retained anchor,
        # so the negative proof above is not vacuous.
        sample = _normalize_ws(SAMPLE_I2A_PRE_CHANGE)
        self.assertIn(
            "Branch point = integration branch AT THIS MOMENT (includes "
            "every task merged so far).",
            sample,
        )

    def test_i3_matchers_fail_against_pre_change_sample(self):
        sample = _normalize_ws(SAMPLE_I3_PRE_CHANGE)
        self.assertNotIn(_normalize_ws(COMPLETION_TIP_CAPTURE), sample)
        self.assertNotIn(_normalize_ws(COMPLETION_REFRESH_CMD), sample)
        self.assertNotIn(COMPLETION_TIP_COMMIT_THIRD_ARG, sample)

    def test_i3_sample_retains_pinned_sentence_anchor(self):
        # Non-vacuity guard.
        sample = SAMPLE_I3_PRE_CHANGE
        self.assertIn(PINNED_COMPLETION_SENTENCE, sample)

    def test_bare_commit_line_matcher_flags_an_unlocked_commit(self):
        sample = (
            'git -C {project_root} add -A -- foo && git -C {project_root} '
            'commit -m "x"'
        )
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertTrue(lines)

    def test_bare_commit_line_matcher_ignores_prose_mentioning_commit(self):
        sample = (
            "No bare `git add`/`git commit` against the integration "
            "worktree runs outside"
        )
        lines = _bare_git_commit_or_add_lines(sample)
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
