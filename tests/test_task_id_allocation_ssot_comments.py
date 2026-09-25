"""Wording tests for task0002 (task-id-allocation-ssot): the module
docstring of `em-workflow/hooks/queue_stop_guard.py` and the re-planning
allocation comment in `em-workflow/scripts/validate-worker-output.py`.

Covers task0002 Acceptance Criteria
(feature-docs/task-id-allocation-ssot/tasks/task0002.md):

- AC-1 (FR6, SPEC AC-6): the whitespace-normalized module docstring of
  queue_stop_guard.py does not contain 'a recycled task id left behind by
  a route-back re-plan'. The same matcher detects that phrase in the
  pre-change docstring sample.
- AC-2 (FR6, SPEC AC-6): the docstring describes the pending+failed
  exception as the task's own id returned to `pending` by route-back.
  Every carve-out reference label present in the pre-change docstring is
  still present. The new-description matcher does not fire on the
  pre-change sample.
- AC-3 (FR7, SPEC AC-8): the comment block for the re-planning allocation
  check no longer states that `entries` must re-declare every registered
  id. It states that registered ids are carried via `carried_task_ids`
  and are not re-declared under `entries`. Both matchers are proven
  against the pre-change comment sample.

Per IMPLEMENTATION.md C6: both pre-change samples below were captured
verbatim from the repository BEFORE this task's edit (git show of the
fork-point revision), and every wording matcher, positive or negative, is
paired with a negative proof run against its sample. Live text and samples
go through the same whitespace normalization (runs of whitespace collapse
to one space).

The module docstring is read by parsing the module source with `ast`,
never by importing it, so no hook side effects run (Test Notes). The
validator comment block is located dynamically through the
'replace-all-task-id-reused' error-code identifier rather than a hardcoded
line number, since that identifier is the check's stable name and the
surrounding line numbers are not (Test Notes).

Matcher -> negative-proof inventory:

- `_assert_removed_stop_guard_phrase_absent` (AC-1 absence matcher):
  negative proof is
  `TestStopGuardDocstringRemovedPhrase.test_matcher_detects_phrase_in_pre_change_sample`.
- `_assert_own_id_description_present` (AC-2 presence matcher): negative
  proof is
  `TestStopGuardDocstringOwnIdDescription.test_matcher_absent_from_pre_change_sample`.
- `_assert_removed_validator_phrase_absent` (AC-3 absence matcher):
  negative proof is
  `TestValidatorCommentReDeclareRemoved.test_matcher_detects_phrase_in_pre_change_sample`.
- `_assert_carried_description_present` (AC-3 presence matcher): negative
  proof is
  `TestValidatorCommentCarriedDescription.test_matcher_absent_from_pre_change_sample`.
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STOP_GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_stop_guard.py"
VALIDATOR_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"

# --- Pre-change samples (C6): captured verbatim BEFORE this task's edit. ---

PRE_CHANGE_STOP_GUARD_DOCSTRING = (
    "em-workflow Stop hook: queue loop guard (queue_stop_guard.py).\n"
    "\n"
    "Deterministic net for the implement-phase work-queue loop\n"
    '(IMPLEMENTATION.md, "Journal contract" / "Conventions" sections). Fires on\n'
    "every Stop event; blocks the orchestrator from ending its turn while a\n"
    "refillable implementer slot exists for an in-progress feature, naming the\n"
    "tasks to launch. This hook is a NET, not an authority: any unexpected\n"
    "condition (unreadable/malformed files, non-JSON stdin, validation failure,\n"
    "no active feature) exits 0 silently rather than risk wedging the session\n"
    "(fail-open convention, contrasted with bash_guard.py's fail-closed security\n"
    "boundary).\n"
    "\n"
    "Decision (per the first in-progress feature, stable ordering by feature\n"
    "name, that has refillable work):\n"
    "  - Any task's last journal event is `failed`, UNLESS that task's own\n"
    "    workflow.yaml status still reads exactly `pending` (a recycled task id\n"
    "    left behind by a route-back re-plan) -> exit 0 (no block; user decision\n"
    "    pending). A recycled id is instead treated as unlaunched.\n"
    "  - No unlaunched tasks, or no free slot (>= MAX_PARALLEL_IMPLEMENTERS\n"
    "    in-flight) -> exit 0.\n"
    "  - Otherwise -> BLOCK: exit 2, stderr names the feature, the free-slot\n"
    "    count, and the task ids to launch (ascending id order, bounded by the\n"
    "    free-slot count).\n"
    "\n"
    "Loop cap: a sidecar file (stop-guard-state.json, sibling of the journal)\n"
    "persists a fingerprint (the derived unlaunched+in-flight task-id sets) and a\n"
    "consecutive-block counter. Three consecutive blocks in the same derived\n"
    "state are allowed; every FURTHER stop in that same state does NOT block\n"
    "(warns on stderr and exits 0 instead) so the user stays in charge — the\n"
    "over-cap counter is persisted, so the guard never resumes blocking an\n"
    'unchanged state (FR4 "stop blocking … let the user take over"). Any state\n'
    "change resets the counter to 1 and re-arms blocking.\n"
    "\n"
    "Only Python stdlib is imported (NFR1).\n"
)

PRE_CHANGE_VALIDATOR_COMMENT_BLOCK = [
    "    # Rule 5 / 5.5.1: replace_all permission conditions. Two permitted",
    '    # paths (workflow-patch.md "replace_all permission conditions"):',
    "    # initial-planning (create-plan: pending, no re-entry signal) and",
    "    # re-planning (create-plan: needs_update, OR create-plan: pending on a",
    "    # SPEC-change re-entry -- workflow_replace_all_spec_change_reentry).",
    "    # Rule 3, common to both: any in_progress/failed task is a protocol",
    "    # error regardless of path.",
    "    #",
    "    # task0017 (review round 2 rework): the re-planning path carries two",
    "    # further, path-dependent obligations that can only be checked here --",
    "    # neither is knowable without the workflow.yaml this dry-run-apply",
    "    # already has in hand:",
    "    #",
    "    # - Mandatory `preserve` per operation (workflow-patch.md's table row):",
    "    #   `workflow.implement.base_commit` is mandatory on the re-planning",
    "    #   path, not mandatory at all on the initial-planning path.",
    "    # - Re-planning task-id allocation: `entries` must re-declare every",
    "    #   task id already registered in `workflow.yaml` (never drop one), and",
    "    #   any genuinely new id must be allocated above the highest registered",
    "    #   id -- the high-water mark is `max(registered ids)`, read directly",
    "    #   from `workflow`, never a number the validator has to store itself.",
]

# --- Wording constants ---

REMOVED_STOP_GUARD_PHRASE = "a recycled task id left behind by a route-back re-plan"
NEW_OWN_ID_DESCRIPTION = "the task's own id, returned from `failed` to `pending` by route-back"
CARVEOUT_LABELS = ("recycled-task-id carve-out", "recycled-task-id rule")

REMOVED_VALIDATOR_PHRASE = "`entries` must re-declare every task id already registered in `workflow.yaml`"
CARRIED_DESCRIPTION = (
    "ids already registered in `workflow.yaml` are carried via "
    "`tasks_patch.carried_task_ids` and are not re-declared under "
    "`tasks_patch.entries`"
)

COMMENT_ANCHOR_IDENTIFIER = "replace-all-task-id-reused"
MODE_GUARD_LINE = 'if mode == "replace_all":'


def _normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def _module_docstring(path):
    """Parses the module source with `ast` (never imports it, so no hook
    side effects run) and returns its module-level docstring, or None."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return ast.get_docstring(tree, clean=False)


def _strip_comment_prefix(line):
    return re.sub(r"^\s*#\s?", "", line)


def _comment_block_text(block_lines):
    """Joins a contiguous run of raw `#`-prefixed source lines into
    continuous prose: strips each line's comment marker/indentation before
    joining, so a phrase split across lines is not corrupted by an
    interleaved '#' (Test Notes)."""
    return _normalize_whitespace(" ".join(_strip_comment_prefix(line) for line in block_lines))


def _replanning_allocation_comment_block(source_lines):
    """Locates the contiguous comment block that belongs to the
    re-planning allocation check, anchored on the stable
    'replace-all-task-id-reused' error-code identifier rather than a
    hardcoded line number (Test Notes). There is exactly one
    `if mode == "replace_all":` guard in this module; the comment block is
    the maximal run of comment lines immediately preceding it."""
    anchor_index = next(
        i for i, line in enumerate(source_lines) if COMMENT_ANCHOR_IDENTIFIER in line
    )
    guard_index = next(
        i
        for i in range(anchor_index, -1, -1)
        if source_lines[i].strip() == MODE_GUARD_LINE
    )
    block = []
    i = guard_index - 1
    while i >= 0 and source_lines[i].strip().startswith("#"):
        block.append(source_lines[i])
        i -= 1
    block.reverse()
    return block


def _live_validator_comment_text():
    source_lines = VALIDATOR_PATH.read_text(encoding="utf-8").split("\n")
    block = _replanning_allocation_comment_block(source_lines)
    return _comment_block_text(block)


# --- Matchers (each paired with a negative proof below) ---


def _assert_removed_stop_guard_phrase_absent(test, docstring_text):
    """AC-1 absence matcher."""
    normalized = _normalize_whitespace(docstring_text)
    test.assertNotIn(REMOVED_STOP_GUARD_PHRASE, normalized)


def _assert_own_id_description_present(test, docstring_text):
    """AC-2 presence matcher."""
    normalized = _normalize_whitespace(docstring_text)
    test.assertIn(NEW_OWN_ID_DESCRIPTION, normalized)


def _labels_present(text, labels):
    normalized = _normalize_whitespace(text)
    return {label for label in labels if label in normalized}


def _assert_removed_validator_phrase_absent(test, comment_text):
    """AC-3 absence matcher."""
    test.assertNotIn(REMOVED_VALIDATOR_PHRASE, comment_text)


def _assert_carried_description_present(test, comment_text):
    """AC-3 presence matcher."""
    test.assertIn(CARRIED_DESCRIPTION, comment_text)


class TestStopGuardDocstringRemovedPhrase(unittest.TestCase):
    """AC-1 (FR6; SPEC AC-6)."""

    def test_removed_phrase_absent_from_live_docstring(self):
        live_docstring = _module_docstring(STOP_GUARD_PATH)
        self.assertIsNotNone(live_docstring)
        _assert_removed_stop_guard_phrase_absent(self, live_docstring)

    def test_matcher_detects_phrase_in_pre_change_sample(self):
        """Negative proof: the same matcher, run against the pre-change
        sample, must fail -- proving the matcher actually detects the
        phrase rather than vacuously passing."""
        with self.assertRaises(AssertionError):
            _assert_removed_stop_guard_phrase_absent(self, PRE_CHANGE_STOP_GUARD_DOCSTRING)


class TestStopGuardDocstringOwnIdDescription(unittest.TestCase):
    """AC-2 (FR6; SPEC AC-6)."""

    def test_own_id_description_present_in_live_docstring(self):
        live_docstring = _module_docstring(STOP_GUARD_PATH)
        self.assertIsNotNone(live_docstring)
        _assert_own_id_description_present(self, live_docstring)

    def test_matcher_absent_from_pre_change_sample(self):
        """Negative proof: the new-description matcher does not fire on
        the pre-change sample (AC-2)."""
        with self.assertRaises(AssertionError):
            _assert_own_id_description_present(self, PRE_CHANGE_STOP_GUARD_DOCSTRING)


class TestStopGuardDocstringLabelRetention(unittest.TestCase):
    """AC-2 (C4): every carve-out reference label present in the
    pre-change docstring is still present in the live docstring."""

    def test_pre_change_sample_carries_no_carveout_label(self):
        # Documents the actual pre-change content: neither exact label
        # string ('recycled-task-id carve-out', 'recycled-task-id rule')
        # occurs in this module's docstring -- they occur only in the
        # narrative reference docs (implement-phase.md) and in a
        # *different* function's docstring in this same module, out of
        # this task's scope. AC-2's retention clause is therefore
        # vacuously satisfied for this docstring; this test pins the
        # (checked) fact that makes it vacuous, so it fails loudly if a
        # future edit adds a label to the pre-change sample without this
        # test being revisited.
        self.assertEqual(_labels_present(PRE_CHANGE_STOP_GUARD_DOCSTRING, CARVEOUT_LABELS), set())

    def test_every_pre_change_label_still_present_live(self):
        pre_labels = _labels_present(PRE_CHANGE_STOP_GUARD_DOCSTRING, CARVEOUT_LABELS)
        live_docstring = _module_docstring(STOP_GUARD_PATH)
        self.assertIsNotNone(live_docstring)
        live_labels = _labels_present(live_docstring, CARVEOUT_LABELS)
        self.assertTrue(pre_labels <= live_labels, f"labels lost: {pre_labels - live_labels}")


class TestValidatorCommentReDeclareRemoved(unittest.TestCase):
    """AC-3 (FR7; SPEC AC-8): the comment no longer claims `entries` must
    re-declare every registered id."""

    def test_removed_phrase_absent_from_live_comment(self):
        _assert_removed_validator_phrase_absent(self, _live_validator_comment_text())

    def test_matcher_detects_phrase_in_pre_change_sample(self):
        """Negative proof: the matcher fires on the pre-change sample."""
        pre_change_text = _comment_block_text(PRE_CHANGE_VALIDATOR_COMMENT_BLOCK)
        with self.assertRaises(AssertionError):
            _assert_removed_validator_phrase_absent(self, pre_change_text)


class TestValidatorCommentCarriedDescription(unittest.TestCase):
    """AC-3 (FR7; SPEC AC-8): the comment states that registered ids are
    carried via `carried_task_ids` and are not re-declared under
    `entries`."""

    def test_carried_description_present_in_live_comment(self):
        _assert_carried_description_present(self, _live_validator_comment_text())

    def test_matcher_absent_from_pre_change_sample(self):
        """Negative proof: the matcher does not fire on the pre-change
        sample."""
        pre_change_text = _comment_block_text(PRE_CHANGE_VALIDATOR_COMMENT_BLOCK)
        with self.assertRaises(AssertionError):
            _assert_carried_description_present(self, pre_change_text)


class TestCommentBlockLocator(unittest.TestCase):
    """Non-vacuity guard for `_replanning_allocation_comment_block`: it
    actually finds the block via the identifier anchor, and the anchor
    identifier itself is present in the live file (so the locator does not
    silently return an empty block because the identifier moved or was
    renamed)."""

    def test_anchor_identifier_present_in_validator(self):
        source = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertIn(COMMENT_ANCHOR_IDENTIFIER, source)

    def test_locator_returns_non_empty_block(self):
        source_lines = VALIDATOR_PATH.read_text(encoding="utf-8").split("\n")
        block = _replanning_allocation_comment_block(source_lines)
        self.assertTrue(block)
        self.assertTrue(all(line.strip().startswith("#") for line in block))


if __name__ == "__main__":
    unittest.main()
