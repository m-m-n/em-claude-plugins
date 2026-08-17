"""Tests for task0002 (abort-phase-terminal): the `implement.failed-task`
Non-packet gate row in `em-workflow/references/batch-mode.md` restates
IMPLEMENTATION.md SC-1's abort terminal (the `implement` step's `status`
being WRITTEN to `failed` and that write being committed) instead of
asserting a status no write produces.

Covers task0002 Acceptance Criteria
(feature-docs/abort-phase-terminal/tasks/task0002.md):

- AC-1 (FR7, NFR6): the row's Batch behavior cell states that the second
  failure on the same task takes the abort terminal in which the
  `implement` step's `status` is written to `failed` and that write is
  committed, and no longer contains the phrase "`implement` stays
  `failed`".
- AC-2 (FR7): the same row still contains the retry clause, the
  route-back-never-automatic clause, the gate id, and the detail pointer.
- AC-4 (FR7): this module exists, asserts AC-1 and AC-2, and includes a
  paired negative proof that the removed phrase is exactly the literal
  that was in the row before this task's edit.

This module reads only `em-workflow/references/batch-mode.md`, imports no
sibling test module, and uses the standard library only (test/README.md).
It does not modify or import `tests/test_batch_policies.py` (AC-3): that
module's own coverage of this row (its Non-packet gate id list and its
(description, keyword) pairing) is exercised by running the whole suite,
per the task plan's Test Notes.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BATCH_MODE_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-mode.md"

GATE_ID = "implement.failed-task"

# The exact phrase this task's edit removes from the row's Batch behavior
# cell (task plan AC-1).
REMOVED_PHRASE = "`implement` stays `failed`"

# The row's Batch behavior cell, byte-for-byte, exactly as it read before
# this task's edit (captured verbatim via `repr()` against the base-commit
# file so the negative proof below is provably about the same literal the
# positive assertion checks the absence of -- the regression-guard pattern
# in tests/test_recycled_task_id_consistency.py).
PRE_CHANGE_ROW = (
    "| `implement.failed-task` — Step I.2.c task failure after the "
    "parent-side-adoption protocol is exhausted "
    "(`references/implement-phase.md` Step I.2.c: retry / "
    "route-back-to-planning / abort via AskUserQuestion) | Auto-select "
    "**retry** once per task (kept worktree, I.2.a resume guard). A "
    "second failure on the SAME task → **abort phase** (`implement` "
    "stays `failed`). Route-back-to-planning is never taken "
    "automatically. Full detail: `references/implement-phase.md` Step "
    "I.2.c |"
)

# Elements that must survive the edit unchanged in substance (task plan
# Design section, "Elements of the row that MUST survive unchanged").
RETRY_CLAUSE = (
    "Auto-select **retry** once per task (kept worktree, I.2.a resume "
    "guard)"
)
ROUTE_BACK_CLAUSE = "Route-back-to-planning is never taken automatically"
DETAIL_POINTER = "Full detail: `references/implement-phase.md` Step I.2.c"

# The new wording this task introduces to state SC-1's write-and-commit
# terminal (task plan AC-1).
STATUS_WRITTEN_FAILED_PHRASE = (
    "`implement` step's `status` is written to `failed`"
)
WRITE_COMMITTED_PHRASE = "that write is committed"


def _read():
    return BATCH_MODE_PATH.read_text(encoding="utf-8")


def _gate_row(text):
    """Locates the single line of the Non-packet gates table containing
    the gate id (task plan Test Notes: "read the file, select the single
    line containing the gate id")."""
    matches = [line for line in text.splitlines() if GATE_ID in line]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one line containing {GATE_ID!r} in "
            f"{BATCH_MODE_PATH}, found {len(matches)}"
        )
    return matches[0]


class TestImplementFailedTaskRowStatesWriteAndCommitTerminal(
    unittest.TestCase
):
    """AC-1 (FR7, NFR6)."""

    @classmethod
    def setUpClass(cls):
        cls.row = _gate_row(_read())

    def test_row_states_status_written_to_failed(self):
        self.assertIn(STATUS_WRITTEN_FAILED_PHRASE, self.row)

    def test_row_states_the_write_is_committed(self):
        self.assertIn(WRITE_COMMITTED_PHRASE, self.row)

    def test_row_no_longer_claims_implement_stays_failed(self):
        self.assertNotIn(REMOVED_PHRASE, self.row)


class TestImplementFailedTaskRowRetainsExistingClauses(unittest.TestCase):
    """AC-2 (FR7)."""

    @classmethod
    def setUpClass(cls):
        cls.row = _gate_row(_read())

    def test_gate_id_present(self):
        self.assertIn(f"`{GATE_ID}`", self.row)

    def test_retry_clause_survives(self):
        self.assertIn(RETRY_CLAUSE, self.row)

    def test_route_back_clause_survives(self):
        self.assertIn(ROUTE_BACK_CLAUSE, self.row)

    def test_detail_pointer_survives(self):
        self.assertIn(DETAIL_POINTER, self.row)


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4: a paired negative proof that REMOVED_PHRASE is exactly the
    literal that was in the row before this task's edit -- the absence
    matcher in TestImplementFailedTaskRowStatesWriteAndCommitTerminal
    would have failed against the row as it read pre-change, and the
    write-and-commit matcher would likewise have failed to find its new
    wording there."""

    def test_removed_phrase_matcher_flags_pre_change_row(self):
        self.assertIn(REMOVED_PHRASE, PRE_CHANGE_ROW)

    def test_pre_change_row_sample_is_not_vacuous(self):
        # Non-vacuity guard: the captured sample is genuinely the row
        # (not an empty or unrelated string) -- scoped by the same gate
        # id and retained clauses the live lookup keys off, so the proof
        # above is not `assertIn(X, "")`-style vacuous.
        self.assertIn(f"`{GATE_ID}`", PRE_CHANGE_ROW)
        self.assertIn(RETRY_CLAUSE, PRE_CHANGE_ROW)
        self.assertIn(ROUTE_BACK_CLAUSE, PRE_CHANGE_ROW)
        self.assertIn(DETAIL_POINTER, PRE_CHANGE_ROW)

    def test_new_wording_matcher_flags_absence_in_pre_change_row(self):
        # Proof the new-wording matcher would have failed against the
        # pre-change row too -- the write-and-commit phrasing is new.
        self.assertNotIn(STATUS_WRITTEN_FAILED_PHRASE, PRE_CHANGE_ROW)


if __name__ == "__main__":
    unittest.main()
