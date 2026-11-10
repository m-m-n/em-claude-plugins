"""Document contract tests for task0006 (subagent-report-write-block): the
parent's handling of an implementer's `write_rejection` report -- the marker
recorded in `tasks.{T}.notes` by the wake commit, the suppression of any
retry of the same cause in both modes and after a resume, the stop report's
content and its batch stop binding, and the restart of a task restored by
the failed entry on its kept worktree.

Covers task0006 Acceptance Criteria
(feature-docs/subagent-report-write-block/tasks/task0006.md):

- AC-1 (TS-13): Step I.2.b step 3 records the marker in `tasks.{T}.notes`
  in the wake commit, and counts three writes.
- AC-2 (TS-23, TM-7, TM-8): when `write_rejection` is honored, that an
  absolute path is not honored and not written, and that an unhonored
  report is an ordinary failure.
- AC-3 (TS-13): Step I.2.c -- interactive offers no retry for the task;
  batch consumes no automatic retry and aborts with `failed_kind` valued
  `decision`, draining in-flight tasks as before.
- AC-4 (TS-13): a resume after an interruption does not auto-retry, reading
  the marker from committed `notes`.
- AC-5 (TS-13): the stop report's content and the resume condition, in both
  implement-phase.md and batch-mode.md; batch-terminal-line.md binds the
  stop.
- AC-6 (NFR2): failures without the marker keep their handling and the
  pinned wording stays.
- AC-7 (FR6): Step I.0 and the paragraph after the Resume guard state the
  restart.

The module reads only `em-workflow/references/implement-phase.md`,
`em-workflow/references/batch-mode.md` and
`em-workflow/references/batch-terminal-line.md`. It does not import from,
and is not imported by, any other test module. The documents cite the file
name rule of `em-workflow/skills/plan-writing/SKILL.md`; none of them holds
the regular expression, which a test below checks.

Content assertions compare against a whitespace-normalized copy of the
section, so a line-wrap choice never makes a prose assertion brittle.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
TERMINAL_LINE_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"

MARKER = "report-name-write-rejected:"
LABEL = "**Same-cause write rejection**"
HONORING_LABEL = "**Honoring `write_rejection`**"
MARKER_LABEL = "**Write-rejection marker**"

STEP_I0_HEADING = "## Step I.0: Preconditions"
STEP_I1_HEADING = "## Step I.1:"
STEP3_START = "3. **Update workflow.yaml, then commit**"
STEP4_START = "4. **Clean up**"
I2C_HEADING = "### I.2.c: Failed handling"
SUPPORTING_CAST_HEADING = "### Supporting cast: journal, hooks, resume"
RESUME_GUARD_START = "**Resume guard**"
CANONICAL_PATH_START = "**Canonical worktree path**"
BATCH_PARAGRAPH_START = "Batch mode (`references/batch-mode.md`'s Non-packet gates table,"
COVERAGE_HEADING = "## Stop point coverage"

STEP_A6_CITATION = "`skills/develop/SKILL.md` Step A.6"
RESUME_CONDITION_PHRASE = (
    "complete the final-path correction by re-running develop naming the "
    "feature"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapse every whitespace run (line wraps included) to one space."""
    return re.sub(r"\s+", " ", text)


def _slice(text, start, end):
    """Text from the first `start` to the next `end` after it, or "" when
    either anchor is absent."""
    begin = text.find(start)
    if begin == -1:
        return ""
    stop = text.find(end, begin + len(start))
    if stop == -1:
        return ""
    return text[begin:stop]


def _paragraph(text, label):
    """The blank-line-delimited block that begins at `label`, or ""."""
    begin = text.find(label)
    if begin == -1:
        return ""
    stop = text.find("\n\n", begin)
    if stop == -1:
        stop = len(text)
    return text[begin:stop]


def _step3(text):
    return _slice(text, STEP3_START, STEP4_START)


def _i2c(text):
    return _slice(text, I2C_HEADING, SUPPORTING_CAST_HEADING)


def _same_cause(text):
    """The Same-cause write rejection paragraph and its bullets: from the
    label to the end of Step I.2.c, where this block is the last item."""
    i2c = _i2c(text)
    begin = i2c.find(LABEL)
    if begin == -1:
        return ""
    return i2c[begin:]


def _step_i0(text):
    return _slice(text, STEP_I0_HEADING, STEP_I1_HEADING)


def _resume_guard(text):
    return _slice(text, RESUME_GUARD_START, CANONICAL_PATH_START)


def _failed_task_row(text):
    for line in text.splitlines():
        if line.startswith("| `implement.failed-task`"):
            return line
    return ""


def _coverage_section(text):
    begin = text.find(COVERAGE_HEADING)
    if begin == -1:
        return ""
    stop = text.find("\n## ", begin + len(COVERAGE_HEADING))
    if stop == -1:
        stop = len(text)
    return text[begin:stop]


# --- matchers (each gets a negative proof in TestNegativeProofs) -----------


def _assert_marker_recorded_in_wake_commit(test, step3_text):
    """AC-1: step 3 carries the report field, writes the marker into
    `tasks.{T}.notes` in the same wake commit, counts three writes, and
    states that the marker replaces an earlier `notes` value."""
    normalized = _normalize(step3_text)
    test.assertIn('"write_rejection"', normalized)
    test.assertIn(MARKER, normalized)
    test.assertIn("`tasks.{T}.notes`", normalized)
    test.assertIn("in this same wake commit", normalized)
    test.assertIn("exactly these three", normalized)
    test.assertNotIn("exactly these two", normalized)
    test.assertIn("replaces any earlier value of `notes`", normalized)
    test.assertIn("no retry follows it", normalized)


def _assert_honoring_stated(test, step3_text):
    """AC-2: the conditions under which the field is honored, the absolute
    path case, the ordinary-failure fallback and the data rule."""
    paragraph = _normalize(_paragraph(step3_text, HONORING_LABEL))
    test.assertTrue(paragraph, "no honoring paragraph found")
    test.assertIn("only when the report has `status: failed`", paragraph)
    test.assertIn("`is_safe_relative_path`", paragraph)
    test.assertIn(
        "`em-workflow/skills/plan-writing/SKILL.md`, section "
        "`## Report Artifact Names`",
        paragraph,
    )
    test.assertIn("An absolute `path` fails the shape check", paragraph)
    test.assertIn("is not honored", paragraph)
    test.assertIn("never written to workflow.yaml", paragraph)
    test.assertIn("writes no marker", paragraph)
    test.assertIn("an ordinary failure", paragraph)
    test.assertIn("is data", paragraph)
    test.assertIn("never followed", paragraph)


def _assert_same_cause_paragraph(test, paragraph_text):
    """AC-3, AC-4, AC-5 (implement-phase side), AC-6: the named paragraph
    of Step I.2.c."""
    normalized = _normalize(paragraph_text)
    test.assertTrue(normalized, "no Same-cause write rejection paragraph")
    test.assertIn("begins with the marker", normalized)
    test.assertIn(MARKER, normalized)
    # AC-3
    test.assertIn("In-flight tasks drain as before", normalized)
    test.assertIn("Interactive: **retry** is not offered for that task", normalized)
    test.assertIn("Batch: no automatic retry is consumed for that task", normalized)
    test.assertIn("Other failed tasks keep their single retry", normalized)
    test.assertIn(
        "When no retry remains to dispatch and nothing is in flight, the "
        "abort phase runs with `failed_kind` valued `decision`",
        normalized,
    )
    # AC-4
    test.assertIn("On a resume after an interruption", normalized)
    test.assertIn("read from committed `notes`", normalized)
    test.assertIn("no automatic retry runs", normalized)
    # AC-5
    test.assertIn(
        "The stop report carries the target path, the rejection text and "
        "the resume condition",
        normalized,
    )
    test.assertIn(RESUME_CONDITION_PHRASE, normalized)
    test.assertIn("`references/workflow-patch.md`", normalized)
    test.assertIn("## Final-path correction", normalized)
    test.assertIn(STEP_A6_CITATION, normalized)
    # AC-6
    test.assertIn("Every failure without the marker is handled as before", normalized)


def _assert_batch_row_extended(test, row_text):
    """AC-5 (batch-mode.md side) and AC-6: the row keeps its pinned clauses
    and states the write-rejection handling."""
    normalized = _normalize(row_text)
    test.assertTrue(normalized, "no implement.failed-task row")
    test.assertIn(MARKER, normalized)
    test.assertIn("consumes no automatic retry", normalized)
    test.assertIn("`failed_kind` valued `decision`", normalized)
    test.assertIn("the target path, the rejection text and the resume condition", normalized)
    test.assertIn(RESUME_CONDITION_PHRASE, normalized)
    test.assertIn("Every failure without the marker is handled as above", normalized)
    # pinned clauses of the existing row
    test.assertIn("Auto-select **retry** once per task", normalized)
    test.assertIn("Route-back-to-planning is never taken automatically", normalized)
    test.assertTrue(normalized.endswith("Full detail: `references/implement-phase.md` Step I.2.c |"))


def _assert_stop_bound(test, coverage_text):
    """AC-5 (batch-terminal-line.md side): the paragraph that binds the
    write-rejection abort to `implement-second-failure`."""
    paragraph = _normalize(_paragraph(coverage_text, "The batch abort that"))
    test.assertTrue(paragraph, "no write-rejection binding paragraph")
    test.assertIn(LABEL.strip("*"), paragraph)
    test.assertIn("binds to the `implement-second-failure` row", paragraph)
    test.assertIn("`implement_task_failed`", paragraph)
    test.assertIn("though the task failed once", paragraph)
    test.assertIn("`detail` carries the target path and the rejection text", paragraph)
    test.assertIn("`resume_conditions` carries the resume condition", paragraph)
    test.assertIn(RESUME_CONDITION_PHRASE, paragraph)


def _assert_i0_restart(test, step_i0_text):
    """AC-7: Step I.0 treats the failed-entry restoration as the rework
    re-entry route."""
    normalized = _normalize(step_i0_text)
    test.assertIn(STEP_A6_CITATION, normalized)
    test.assertIn("`## Step A.6: failed からの入口`", normalized)
    test.assertIn("meets the rework re-entry's condition", normalized)
    test.assertIn("is treated as that route here", normalized)


def _assert_resume_guard_restart(test, text):
    """AC-7: the paragraph after the Resume guard's bullets."""
    guard = _normalize(_resume_guard(text))
    test.assertTrue(guard, "no Resume guard section")
    test.assertIn(STEP_A6_CITATION, guard)
    test.assertIn("reuses its kept worktree and branch as they are", guard)
    test.assertIn("uncommitted changes in that worktree are not discarded", guard)


# --- live documents --------------------------------------------------------


class _ImplementPhaseCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)


class TestRegionsAreLocated(_ImplementPhaseCase):
    """Non-vacuity guard: every region the tests below scope to exists."""

    def test_step3_region_exists(self):
        self.assertGreater(len(_step3(self.text)), 0)

    def test_i2c_region_exists(self):
        self.assertGreater(len(_i2c(self.text)), 0)

    def test_step_i0_region_exists(self):
        self.assertGreater(len(_step_i0(self.text)), 0)

    def test_resume_guard_region_exists(self):
        self.assertGreater(len(_resume_guard(self.text)), 0)

    def test_batch_mode_row_exists(self):
        self.assertTrue(_failed_task_row(_read(BATCH_MODE_PATH)))

    def test_coverage_section_exists(self):
        self.assertTrue(_coverage_section(_read(TERMINAL_LINE_PATH)))


class TestAC1MarkerRecordedInWakeCommit(_ImplementPhaseCase):
    def test_step3_records_marker_in_notes_in_the_wake_commit(self):
        _assert_marker_recorded_in_wake_commit(self, _step3(self.text))

    def test_marker_paragraph_is_inside_step3(self):
        self.assertIn(MARKER_LABEL, _step3(self.text))

    def test_marker_is_written_only_in_the_wake_commit(self):
        paragraph = _normalize(_paragraph(_step3(self.text), MARKER_LABEL))
        self.assertIn("only here, and only in the wake commit", paragraph)


class TestAC2HonoringConditions(_ImplementPhaseCase):
    def test_honoring_conditions_are_stated(self):
        _assert_honoring_stated(self, _step3(self.text))

    def test_absolute_path_is_not_honored_and_not_written(self):
        paragraph = _normalize(_paragraph(_step3(self.text), HONORING_LABEL))
        absolute = paragraph.index("An absolute `path` fails the shape check")
        self.assertLess(absolute, paragraph.index("never written to workflow.yaml"))

    def test_the_file_name_rule_is_cited_not_restated(self):
        # NFR3 convention: no document other than plan-writing holds the
        # regular expression of the file name rule.
        for path in (IMPLEMENT_PHASE_PATH, BATCH_MODE_PATH, TERMINAL_LINE_PATH):
            with self.subTest(document=path.name):
                text = _read(path)
                self.assertNotIn("^(REPORT", text)
                self.assertNotIn("REPORT|SUMMARY", text)


class TestAC3AC4AC5SameCauseParagraph(_ImplementPhaseCase):
    def test_paragraph_states_suppression_resume_and_stop_report(self):
        _assert_same_cause_paragraph(self, _same_cause(self.text))

    def test_paragraph_sits_after_the_batch_mode_paragraph(self):
        i2c = _i2c(self.text)
        batch_at = i2c.index(BATCH_PARAGRAPH_START)
        label_at = i2c.index(LABEL)
        self.assertLess(batch_at, label_at)
        # a blank line separates the two paragraphs
        self.assertIn("\n\n", i2c[batch_at:label_at])

    def test_paragraph_is_inside_i2c(self):
        self.assertIn(LABEL, _i2c(self.text))

    def test_batch_abort_does_not_write_a_task_status_or_notes_set(self):
        normalized = _normalize(_same_cause(self.text))
        self.assertIn("the marker stays in `notes`", normalized)


class TestAC5BatchModeRow(unittest.TestCase):
    def test_row_states_the_write_rejection_handling(self):
        _assert_batch_row_extended(self, _failed_task_row(_read(BATCH_MODE_PATH)))

    def test_the_table_stays_at_ten_rows(self):
        text = _read(BATCH_MODE_PATH)
        table = _slice(text, "| Gate (interactive behavior) | Batch behavior |", "\n\n")
        rows = [
            line
            for line in table.splitlines()
            if line.startswith("|") and not re.fullmatch(r"[|\-\s]+", line)
        ]
        # header plus ten rows (the Non-packet gates table's pinned size)
        self.assertEqual(len(rows) - 1, 10)


class TestAC5StopBinding(unittest.TestCase):
    def test_paragraph_binds_the_stop_to_implement_second_failure(self):
        _assert_stop_bound(self, _coverage_section(_read(TERMINAL_LINE_PATH)))

    def test_paragraph_sits_after_the_precedence_paragraph(self):
        section = _coverage_section(_read(TERMINAL_LINE_PATH))
        self.assertLess(
            section.index("Precedence rule:"),
            section.index("The batch abort that"),
        )

    def test_coverage_table_keeps_fourteen_rows(self):
        section = _coverage_section(_read(TERMINAL_LINE_PATH))
        rows = [
            line
            for line in section.splitlines()
            if line.startswith("| `")
        ]
        self.assertEqual(len(rows), 14)

    def test_paragraph_states_that_no_row_and_no_code_is_added(self):
        section = _coverage_section(_read(TERMINAL_LINE_PATH))
        paragraph = _normalize(_paragraph(section, "The batch abort that"))
        self.assertIn("The table above gains no row and no code", paragraph)


class TestAC6ExistingHandlingKept(_ImplementPhaseCase):
    PINNED = (
        "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a "
        "resume guard). A task that fails a second time",
        "Route-back-to-planning is never taken automatically. Track the retry-consumed "
        "state per task in `tasks.{T}.notes`.",
        "There is NO skip option: a task is either merged, retried, or re-planned",
    )

    def test_pinned_i2c_sentences_are_retained(self):
        normalized = _normalize(_i2c(self.text))
        for phrase in self.PINNED:
            with self.subTest(phrase=phrase[:40]):
                self.assertIn(phrase, normalized)

    def test_only_the_marked_failure_is_handled_differently(self):
        normalized = _normalize(_same_cause(self.text))
        self.assertIn("Every failure without the marker is handled as before", normalized)

    def test_step_i0_opening_and_resume_guard_bullets_are_retained(self):
        normalized = _normalize(self.text)
        self.assertIn("Step I.0 recognises four entry routes into", normalized)
        self.assertIn(
            "- Retry on the same worktree (user chose \"retry\" in I.2.c): reuse the "
            "existing worktree as-is and re-launch the implementer against it.",
            normalized,
        )
        self.assertIn(
            "- Clean re-attempt (fresh implementer, no prior branch state to keep): "
            "first `git worktree remove --force \"$WT_ROOT/{T}\"` and "
            "`git branch -D \"em-workflow/{feature}/{T}\"`, then recreate the "
            "worktree and branch from the current integration branch as above.",
            normalized,
        )

    def test_deliverables_hold_no_notion_url_or_home_path(self):
        # NFR6
        for path in (IMPLEMENT_PHASE_PATH, BATCH_MODE_PATH, TERMINAL_LINE_PATH):
            with self.subTest(document=path.name):
                text = _read(path)
                self.assertNotIn("notion.so", text)
                self.assertNotIn("/home/", text)


class TestAC7Restart(_ImplementPhaseCase):
    def test_step_i0_treats_the_failed_entry_as_the_rework_route(self):
        _assert_i0_restart(self, _step_i0(self.text))

    def test_resume_guard_paragraph_states_the_restart(self):
        _assert_resume_guard_restart(self, self.text)

    def test_restart_sentence_follows_the_abort_text_of_step_i0(self):
        step = _normalize(_step_i0(self.text))
        self.assertLess(
            step.index("with nothing to launch"),
            step.index(STEP_A6_CITATION),
        )

    def test_restart_paragraph_follows_the_resume_guard_bullets(self):
        guard = _normalize(_resume_guard(self.text))
        self.assertLess(
            guard.index("- Clean re-attempt"),
            guard.index(STEP_A6_CITATION),
        )


class TestNegativeProofs(unittest.TestCase):
    """Each matcher rejects a sample that lacks the statement it asserts."""

    def _must_fail(self, matcher, sample):
        with self.assertRaises(AssertionError):
            matcher(self, sample)

    def test_marker_matcher_rejects_text_without_the_marker(self):
        self._must_fail(
            _assert_marker_recorded_in_wake_commit,
            "3. **Update workflow.yaml, then commit**: exactly these two writes",
        )

    def test_honoring_matcher_rejects_text_without_the_paragraph(self):
        self._must_fail(_assert_honoring_stated, "3. **Update workflow.yaml**")

    def test_honoring_matcher_rejects_a_paragraph_without_the_absolute_path_rule(self):
        sample = (
            f"{HONORING_LABEL}: the field is honored only when the report has "
            "`status: failed` and `is_safe_relative_path` passes."
        )
        self._must_fail(_assert_honoring_stated, sample)

    def test_same_cause_matcher_rejects_the_pre_change_i2c(self):
        self._must_fail(
            _assert_same_cause_paragraph,
            "auto-select **retry** ONCE per task. Track the retry-consumed state.",
        )

    def test_same_cause_matcher_rejects_a_paragraph_that_still_offers_retry(self):
        sample = (
            f"{LABEL}: a failed task whose notes begins with the marker "
            f"{MARKER}. In-flight tasks drain as before. Interactive: retry is "
            "offered."
        )
        self._must_fail(_assert_same_cause_paragraph, sample)

    def test_row_matcher_rejects_the_pre_change_row(self):
        sample = (
            "| `implement.failed-task` | Auto-select **retry** once per task. "
            "Route-back-to-planning is never taken automatically. Full detail: "
            "`references/implement-phase.md` Step I.2.c |"
        )
        self._must_fail(_assert_batch_row_extended, sample)

    def test_binding_matcher_rejects_a_section_without_the_paragraph(self):
        self._must_fail(_assert_stop_bound, "## Stop point coverage\n\nPrecedence rule: x")

    def test_i0_matcher_rejects_step_i0_without_the_sentence(self):
        self._must_fail(_assert_i0_restart, "5. **Re-entry precondition**: three routes")

    def test_resume_guard_matcher_rejects_the_guard_without_the_paragraph(self):
        sample = f"{RESUME_GUARD_START}: x\n- Retry on the same worktree\n\n{CANONICAL_PATH_START}"
        self._must_fail(_assert_resume_guard_restart, sample)


if __name__ == "__main__":
    unittest.main()
