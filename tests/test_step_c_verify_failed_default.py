"""Tests for task0004 (batch-verify-rework-lineage-cap): Step C's completion-
method AskUserQuestion switches its recommended default when `verify.status`
is `failed`, plus the FR10 non-change guard over review's cap behaviour and
the NFR2 non-change guard over `rework-task-synthesis.md`.

Covers task0004 Acceptance Criteria
(feature-docs/batch-verify-rework-lineage-cap/tasks/task0004.md):

- AC-1 (FR9): Step C's completion-method step still offers the three choices
  (merge into `{base_branch}` / keep the branch / create a PR) -- the choice
  set is not narrowed.
- AC-2 (FR9): the recommended default switches to "keep the branch" ONLY
  when `verify.status` is `failed`; the old unconditional
  "default is merge" wording is gone.
- AC-3 (FR9): when `verify.status` is `failed`, the question text discloses
  both the failed fact and the `failed_items` count.
- AC-4 (FR9, regression): batch's auto-selection (no question, "keep the
  branch" chosen automatically, no merge/push/PR) wording is unchanged.
- AC-5 (FR10): review-phase.md's Phase R5 batch paragraph still carries its
  three elements (`batch.review_rework_count` / `resolution: deferred` /
  the `"batch mode: rework cap reached"` reason string), and batch-mode.md's
  `review.residual-critical-high` row is unchanged.
- AC-6 (FR10): review-phase.md never references the verify-side lineage
  counter names.
- AC-7 (NFR2): `rework-task-synthesis.md`'s Invariant 7 wording is present
  (this task does not modify that file).
- AC-8 (NFR3, NFR4): this module imports the Python standard library only,
  and the conditional-default matcher used for AC-2/AC-3 is proven able to
  fail against a synthetic text carrying the old unconditional
  "default is merge" wording.

This is a documentation-contract task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following the
pattern established by tests/test_batch_stop_contract_skill_wiring.py --
independent helper functions local to this module (no cross-module import).

Section-boundary note (Test Notes / IMPLEMENTATION.md D3): Step C's own
level-2 heading is task0002's sole property in this feature and may change
text before this task's worktree merges with task0002's. This module never
uses that heading as a slice boundary; it slices on the numbered-step labels
("1. **完了方式の決定**" / "2. **worktree / ブランチ掃除**"), which neither
task0004 nor task0002 renames.

Matcher -> negative-proof inventory:

- `_states_conditional_default_and_failed_disclosure` (AC-2/AC-3's
  combined matcher): negative proof is
  TestConditionalDefaultMatcherCanFail.test_matcher_rejects_old_unconditional_default_text
  (a forged excerpt reproducing the pre-task0004 unconditional
  "default is merge" wording verbatim), non-vacuity guard is
  TestConditionalDefaultMatcherCanFail.test_forged_old_unconditional_text_is_well_formed_and_found.
- `_has_review_cap_regression_markers` (AC-5's review-phase.md batch
  paragraph pin): negative proof is
  TestReviewCapRegressionMatcherCanFail.test_matcher_rejects_text_missing_cap_markers
  (a forged paragraph with the cap markers replaced), non-vacuity guard is
  TestReviewCapRegressionMatcherCanFail.test_forged_text_is_well_formed_and_missing_markers.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
REWORK_SYNTHESIS_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"

# Step C's numbered-step labels: stable across task0002 (which owns only the
# section's level-2 heading and later paragraphs, per IMPLEMENTATION.md D3)
# and task0004 (this task, which owns only step 1's body). Neither task
# renames these labels, so they are safe slice boundaries (Test Notes).
STEP_1_LABEL = "1. **完了方式の決定**"
STEP_2_LABEL = "2. **worktree / ブランチ掃除**"

# AC-1: the three completion-method choices, unchanged bullet markers.
CHOICE_MARKERS = (
    "**`{base_branch}` にマージ**",
    "**ブランチを残す**",
    "**PR を作成**",
)

# AC-2: the conditional default-switch wording this task introduces.
NON_FAILED_DEFAULT_PHRASE = (
    "`verify.status` が `failed` 以外なら「`{base_branch}` にマージ」"
)
FAILED_DEFAULT_PHRASE = "`verify.status` が `failed` なら「ブランチを残す」"

# AC-3: the failed-fact + failed_items-count disclosure requirement.
FAILED_DISCLOSURE_PHRASE = (
    "`verify.status` が `failed` のときは、質問文に verify が failed で"
    "ある事実と `failed_items` の件数を明記する"
)

# AC-2 negative proof: the pre-task0004 unconditional "default is merge"
# wording (contiguous: default clause immediately followed by the batch
# auto-select clause, with no condition on verify.status in between).
OLD_UNCONDITIONAL_DEFAULT_PHRASE = (
    "デフォルト（推奨表示）は「`{base_branch}` にマージ」（batch:"
)

# AC-4 regression: batch's auto-selection wording, unchanged by this task.
BATCH_AUTO_SELECT_PHRASE = (
    "batch: 質問せず自動で「ブランチを残す」を選ぶ。マージ・push・"
    "PR 作成のいずれも行わない"
)

# AC-5: review-phase.md's Phase R5 batch paragraph boundaries and its three
# cap-behaviour elements (FR10 non-change guard). Boundaries are markers no
# task in this feature touches (Design section 2 / IMPLEMENTATION.md D2
# exception): the batch-mode paragraph's own opening sentence and the next
# heading.
REVIEW_PHASE_BATCH_START = "Batch mode (develop-駆動 only): no offer"
REVIEW_PHASE_NEXT_HEADING = "## Phase R6: Report (Japanese)"

REVIEW_REWORK_COUNTER = "batch.review_rework_count"
REVIEW_DEFERRED_RESOLUTION = "resolution: deferred"
REVIEW_DEFERRED_REASON = '"batch mode: rework cap reached"'

# AC-6: verify-side lineage counter names that review-phase.md must never
# reference (IMPLEMENTATION.md Shared Components: the `batch` block's
# verify-side keys, plus the old pre-feature key for good measure).
VERIFY_SIDE_COUNTER_NAMES = (
    "verify_rework_count",
    "verify_rework.rounds",
    "verify_rework.failed_id_counts",
)

# AC-7: rework-task-synthesis.md's Invariant 7 (Section 11), which this task
# does not modify.
INVARIANT_7_PHRASE = (
    "Interactive and batch never differ in task synthesis rules; they "
    "differ only in how a rework round is selected and in the retry/round "
    "cap."
)


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): the Japanese prose
    # in these documents hard-wraps without a space at the break point, so
    # collapsing to a single space would inject whitespace the source never
    # had and break substring matches that span a wrap (same rationale as
    # tests/test_batch_stop_contract_skill_wiring.py's helper of the same
    # name). Applied identically on both sides of every comparison below,
    # this remains a correct exact-content check for the English Invariant
    # 7 sentence too.
    return re.sub(r"\s+", "", text)


def _states_conditional_default_and_failed_disclosure(text):
    """AC-2/AC-3's combined matcher: true iff `text` states the default
    switch conditionally on `verify.status` (both branches), states the
    failed-fact + failed_items-count disclosure requirement, AND does not
    also carry the old unconditional "default is merge" wording."""
    stripped = _strip_ws(text)
    has_condition = (
        _strip_ws(NON_FAILED_DEFAULT_PHRASE) in stripped
        and _strip_ws(FAILED_DEFAULT_PHRASE) in stripped
    )
    has_disclosure = _strip_ws(FAILED_DISCLOSURE_PHRASE) in stripped
    old_unconditional_present = _strip_ws(OLD_UNCONDITIONAL_DEFAULT_PHRASE) in stripped
    return has_condition and has_disclosure and not old_unconditional_present


def _has_review_cap_regression_markers(text):
    """AC-5's review-phase.md batch-paragraph pin matcher: true iff `text`
    carries all three of the FR10 cap-behaviour elements."""
    return (
        REVIEW_REWORK_COUNTER in text
        and REVIEW_DEFERRED_RESOLUTION in text
        and REVIEW_DEFERRED_REASON in text
    )


class TestStepCCompletionMethodChoicesRetained(unittest.TestCase):
    """AC-1: the three-choice AskUserQuestion is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_1_LABEL, STEP_2_LABEL)

    def test_three_choice_markers_present(self):
        for marker in CHOICE_MARKERS:
            self.assertIn(marker, self.section)

    def test_askuserquestion_and_three_way_wording_present(self):
        self.assertIn("AskUserQuestion", self.section)
        self.assertIn("の三択", self.section)


class TestStepCVerifyFailedDefaultWiring(unittest.TestCase):
    """AC-2, AC-3: the conditional default switch and failed-disclosure
    wording are present in Step C's completion-method step."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_1_LABEL, STEP_2_LABEL)

    def test_conditional_default_and_disclosure_present_without_old_wording(self):
        self.assertTrue(
            _states_conditional_default_and_failed_disclosure(self.section),
            "expected the conditional default switch and the failed-fact / "
            "failed_items-count disclosure to be present, with the old "
            "unconditional 'default is merge' wording gone",
        )

    def test_non_failed_branch_default_is_merge(self):
        self.assertIn(
            _strip_ws(NON_FAILED_DEFAULT_PHRASE), _strip_ws(self.section)
        )

    def test_failed_branch_default_is_keep_branch(self):
        self.assertIn(_strip_ws(FAILED_DEFAULT_PHRASE), _strip_ws(self.section))

    def test_failed_disclosure_requirement_present(self):
        self.assertIn(
            _strip_ws(FAILED_DISCLOSURE_PHRASE), _strip_ws(self.section)
        )


class TestConditionalDefaultMatcherCanFail(unittest.TestCase):
    """AC-8 / Test Notes: negative proof plus non-vacuity guard for
    `_states_conditional_default_and_failed_disclosure` -- a forged excerpt
    reproducing the pre-task0004 unconditional "default is merge" wording
    verbatim, with no condition and no disclosure."""

    FORGED_OLD_UNCONDITIONAL_TEXT = (
        f"{STEP_1_LABEL}: AskUserQuestion —\n"
        "「integration ブランチ `em-workflow/{feature}/integration` を"
        "どうする？」の三択。デフォルト（推奨表示）は「`{base_branch}` に"
        "マージ」（batch: 質問せず自動で「ブランチを残す」を選ぶ。マージ・"
        "push・PR 作成のいずれも行わない）\n"
        f"{STEP_2_LABEL}: ...\n"
    )

    def test_forged_old_unconditional_text_is_well_formed_and_found(self):
        # Non-vacuity guard: the slicer finds it, and it genuinely carries
        # the old unconditional phrase -- so the rejection below exercises
        # the conditional-wording check, not a slicing or fixture defect.
        section = _section(
            self.FORGED_OLD_UNCONDITIONAL_TEXT, STEP_1_LABEL, STEP_2_LABEL
        )
        self.assertIn(
            _strip_ws(OLD_UNCONDITIONAL_DEFAULT_PHRASE), _strip_ws(section)
        )

    def test_matcher_rejects_old_unconditional_default_text(self):
        section = _section(
            self.FORGED_OLD_UNCONDITIONAL_TEXT, STEP_1_LABEL, STEP_2_LABEL
        )
        self.assertFalse(
            _states_conditional_default_and_failed_disclosure(section),
            "matcher failed to detect the old unconditional 'default is "
            "merge' wording",
        )


class TestBatchAutoSelectRegressionUnchanged(unittest.TestCase):
    """AC-4: batch's auto-selection wording (no question, 'keep the
    branch' chosen automatically, no merge/push/PR) is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, STEP_1_LABEL, STEP_2_LABEL)

    def test_batch_auto_select_wording_present(self):
        self.assertIn(
            _strip_ws(BATCH_AUTO_SELECT_PHRASE), _strip_ws(self.section)
        )

    def test_batch_non_packet_gates_reference_present(self):
        self.assertIn("`batch-mode.md` の Non-packet gates 表", self.section)
        self.assertIn("`develop.completion`", self.section)


class TestReviewPhaseCapNonRegression(unittest.TestCase):
    """AC-5 (FR10): review-phase.md's Phase R5 batch paragraph still
    carries its three cap-behaviour elements, unchanged. This task does not
    modify review-phase.md; no other task in this feature does either
    (Design section 2 / IMPLEMENTATION.md D2 exception)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PHASE_PATH)
        cls.section = _section(
            cls.text, REVIEW_PHASE_BATCH_START, REVIEW_PHASE_NEXT_HEADING
        )

    def test_review_cap_regression_markers_present(self):
        self.assertTrue(
            _has_review_cap_regression_markers(self.section),
            "expected the batch.review_rework_count counter, the "
            "resolution: deferred marking, and the rework-cap-reached "
            "reason string to all be present in review-phase.md's Phase R5 "
            "batch paragraph",
        )


class TestReviewCapRegressionMatcherCanFail(unittest.TestCase):
    """AC-5 / Test Notes: negative proof plus non-vacuity guard for
    `_has_review_cap_regression_markers` -- a synthetic paragraph where the
    cap-behaviour markers have been replaced (review's cap description has
    disappeared)."""

    FORGED_TEXT_MISSING_CAP_MARKERS = (
        "Batch mode (develop-駆動 only): no offer. When the counter is "
        "already >= 1: mark each residual finding `resolution: dismissed` "
        "with `resolution_reason: \"batch mode: something else\"` and "
        "complete the step.\n\n"
        "## Phase R6: Report (Japanese)\n"
    )

    def test_forged_text_is_well_formed_and_missing_markers(self):
        section = _section(
            self.FORGED_TEXT_MISSING_CAP_MARKERS,
            REVIEW_PHASE_BATCH_START,
            REVIEW_PHASE_NEXT_HEADING,
        )
        self.assertNotIn(REVIEW_DEFERRED_RESOLUTION, section)
        self.assertNotIn(REVIEW_DEFERRED_REASON, section)

    def test_matcher_rejects_text_missing_cap_markers(self):
        section = _section(
            self.FORGED_TEXT_MISSING_CAP_MARKERS,
            REVIEW_PHASE_BATCH_START,
            REVIEW_PHASE_NEXT_HEADING,
        )
        self.assertFalse(_has_review_cap_regression_markers(section))


class TestBatchModeResidualCriticalHighRowUnchanged(unittest.TestCase):
    """AC-5 (FR10): batch-mode.md's `review.residual-critical-high`
    Non-packet gates row is unchanged. Scoped to this single row (Test
    Notes: task0001 changes other rows/sections of this same file, e.g. the
    `verify.failed` row and the `batch` block section, so a whole-file
    check would break on task0001's unrelated changes)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.row_line = next(
            line
            for line in cls.text.splitlines()
            if "`review.residual-critical-high`" in line
        )

    def test_row_present(self):
        self.assertIn("`review.residual-critical-high`", self.row_line)

    def test_row_states_completion_gate_and_auto_rework_cap_behaviour(self):
        self.assertIn(
            "Phase R5 completion gate when `residual_critical_high > 0`",
            self.row_line,
        )
        self.assertIn(
            "Auto-rework once (`batch.review_rework_count` cap 1)",
            self.row_line,
        )
        self.assertIn(
            'mark residuals `deferred` with reason '
            '`"batch mode: rework cap reached"`',
            self.row_line,
        )
        self.assertIn("references/review-phase.md` Phase R5", self.row_line)


class TestReviewPhaseNeverReferencesVerifySideCounters(unittest.TestCase):
    """AC-6 (FR10): review-phase.md never references the verify-side
    lineage counter names."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PHASE_PATH)

    def test_verify_side_counter_names_absent(self):
        for name in VERIFY_SIDE_COUNTER_NAMES:
            self.assertNotIn(
                name,
                self.text,
                f"review-phase.md must not reference the verify-side "
                f"counter name {name!r}",
            )

    def test_verify_side_counter_names_are_non_trivial_non_vacuity(self):
        # Non-vacuity: these names are real, non-empty tokens (not e.g. an
        # empty string that would trivially pass the absence check above).
        for name in VERIFY_SIDE_COUNTER_NAMES:
            self.assertTrue(name)


class TestReworkTaskSynthesisInvariant7Unchanged(unittest.TestCase):
    """AC-7 (NFR2): `rework-task-synthesis.md`'s Invariant 7 wording is
    present. This task does not modify this file."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_SYNTHESIS_PATH)

    def test_invariant_7_present(self):
        self.assertIn(_strip_ws(INVARIANT_7_PHRASE), _strip_ws(self.text))


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-8 / NFR3, NFR4: this module imports the Python standard library
    only."""

    def test_own_imports_are_all_stdlib(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
