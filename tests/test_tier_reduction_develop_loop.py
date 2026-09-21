"""Tests for task0005 (task-tier-reduction): the reduction table, the
skipped-outside-design discipline, the new no-work-required turn-ending
condition, and the upgrade procedure inside
`em-workflow/skills/develop/SKILL.md`.

Covers task0005 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0005.md):

- AC-1 (TS-15): the develop skill carries a reduction table listing, per
  tier, the subtracted artifacts and the kept ones; `reduced`'s and
  `minimal`'s subtraction lists match IMPLEMENTATION.md Shared Components,
  and the kept list names the whole test suite and the Step 0 git-setup
  gate.
- AC-2 (TS-15, SPEC AC-11): no sentence in the file subtracts the
  integration worktree in any tier, and the parallelism subtraction is
  stated as a single task in a single task worktree.
- AC-3 (TS-5): the first turn-ending condition, the Step B status sentence,
  the Step C entry condition and its heading, and the phase-boundary
  table's ordinary-step row all admit a skipped step outside the design
  step, and none of them treats it as an error; the skip reason stays
  mandatory.
- AC-4: the turn-ending conditions list carries one new entry naming the
  no-work stop point in its hyphenated form; the underscored reason code
  appears nowhere in this file.
- AC-5 (TS-16): the upgrade procedure is expressed only as skipped becoming
  pending, introduces no new status value, names the critical-finding and
  failed-verification triggers, forbids downgrading, and includes
  re-running the completed create-spec step for the most-reducing tier.
- AC-6 (TS-16): the automatic-re-entry carve-out enumerates three
  transitions, names the owning document for the new one, and its
  exhaustiveness sentence states the new count.
- AC-7: this module asserts AC-1 through AC-6, is discovered by
  `python3 -m unittest discover -s tests`, imports only standard-library
  modules, and pairs each matcher with a negative proof and a non-vacuity
  guard.

Pinned-length search (Test Notes): before adding item 8 to the
turn-ending conditions list, the repository was searched for an assertion
pinning that list's length (a count, not the byte-for-byte item 1-7
content already pinned by tests/test_develop_once_option.py's
ITEMS_1_TO_6_VERBATIM / ITEM_7_VERBATIM, which this task's own item-1
rewrite required updating in place). No such length-pinning assertion was
found -- `test_anchor_sentence_follows_item_7` in that module only checks
that the closing anchor sentence occurs AFTER item 7's own text, which
remains true with item 8 inserted between them.

Region-ownership regression (Test Notes): pins the Step A anchor sentences
and the retrospect section's own concluding sentence as unchanged by this
task's diff (task0005 does not own Step A or the retrospect section per
IMPLEMENTATION.md D3).

Test isolation: every assertion below targets only
`em-workflow/skills/develop/SKILL.md` -- the file this task owns (plus its
own existence-only reference to
`em-workflow/references/templates/task-document.md`'s path, never its
content). Constants are redeclared locally rather than imported from
sibling test modules (Cross-module isolation convention).

Deviations from the literal "four places" list (recorded in the
implementer report): this task also generalized the single-line intro
paraphrase of stop condition 1 in the file's own "READ FIRST" section
(`design のみ skipped も可` -> the same `skipped` の step があっても可
wording), for internal consistency with the four AC-3 places -- it was not
individually pinned by any pre-existing test and is not treated as one of
AC-3's four named places, so it is not separately asserted here either;
its old wording's absence is covered by this module's whole-file check for
AC-3.

Matcher -> negative-proof inventory (Test Notes: every matcher carries a
negative proof over a forged/synthetic sample plus a non-vacuity guard):

- `_find_reduction_table_violations` (AC-1): negative proof is
  TestReductionTableMatcherCanFail.test_matcher_detects_a_missing_subtraction_term,
  non-vacuity guard is
  TestReductionTableMatcherCanFail.test_forged_table_is_well_formed_and_found.
- `_find_integration_worktree_subtraction_violations` (AC-2): negative
  proof is
  TestIntegrationWorktreeAbsenceMatcherCanFail.test_matcher_detects_a_forged_subtraction_sentence,
  non-vacuity guard is
  TestIntegrationWorktreeAbsenceMatcherCanFail.test_forged_sentence_is_well_formed_and_found.
- per-place AC-3 checks: each of the four
  `TestSkippedOutsideDesignAdmitted*` classes below pairs its own presence
  assertion with a sibling `assertNotIn` over the OLD restrictive wording,
  which doubles as the negative proof (the old wording is real text this
  repository carried until this task's own edit, captured verbatim in the
  `OLD_*` constants below) -- exercised directly, not through a separate
  boolean-returning matcher function.
- `_find_no_work_required_underscore_literal` (AC-4): negative proof is
  TestNoWorkStopEntryMatcherCanFail.test_matcher_detects_the_underscored_literal,
  non-vacuity guard is
  TestNoWorkStopEntryMatcherCanFail.test_forged_text_is_well_formed_and_found.
- `_find_upgrade_procedure_violations` (AC-5): negative proof is
  TestUpgradeProcedureMatcherCanFail.test_matcher_detects_a_missing_element,
  non-vacuity guard is
  TestUpgradeProcedureMatcherCanFail.test_forged_procedure_is_well_formed_and_found.
- `_carve_out_counts_match` (AC-6): negative proof is
  TestCarveOutCountMatcherCanFail.test_matcher_detects_a_count_mismatch,
  non-vacuity guard is
  TestCarveOutCountMatcherCanFail.test_forged_carve_out_is_well_formed_and_found.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

# --- section boundaries, taken verbatim from skills/develop/SKILL.md ------

TURN_END_HEADING = "### ターンを終わらせていい唯一の条件"
TURN_END_ANCHOR = "これらに該当しない限り"
STEP_B_HEADING = "## Step B: 自走ループ"
STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — `skipped` の step（design "
    "自身の skip、または tier による skip）があっても可 — か、cap 到達に"
    "より verify が `failed` のまま残る場合のみ）"
)
ONCE_SECTION_HEADING = "## `--once` のフェーズ境界"
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"

TIER_TABLE_LABEL = "**Tier 削減表**"
UPGRADE_LABEL = "**アップグレード手順**"
STEP_TABLE_MARKER = "| step | 実行方法 |"

STOP_CONDITION_3_LABEL = "**停止条件 3 との優先関係**"
CREATE_PLAN_EXEMPTION_RATIONALE_LABEL = "**create-plan が `in_progress` を経ない理由**"

# Region-ownership regression anchors (task0005 does not own Step A or the
# retrospect section, IMPLEMENTATION.md D3): unchanged by this task's diff.
STEP_A_ANCHOR = "## Step A: feature の決定"
STEP_A_IDENTIFIER_GATE_ANCHOR = "**fail-closed 識別子ゲート**"
RETROSPECT_CONCLUDING_SENTENCE = (
    "スキル・ルール表への反映はここでは**行わない**（判断は\n"
    "`/em-workflow:retrospect` の手動フローに委ねる）。書き出したら step を\n"
    "`completed` にし、commit-docs.sh で\n"
    "`docs({feature}): retrospect signals` としてコミットする。"
)

# The hyphenated stop point this task adds (Shared Components "No-work
# terminal stop"); the underscored reason code literal must never occur in
# this file (NFR3 -- owned solely by references/batch-terminal-line.md).
NO_WORK_STOP_POINT = "no-work-required"
NO_WORK_REASON_CODE_LITERAL = "no_work_required"

# The OLD restrictive wording this task's four AC-3 places replaced,
# captured verbatim (used as both a whole-file absence check and, per the
# module docstring, as the negative-proof fixture for each per-place test).
OLD_ITEM_1_FRAGMENT = "design のみ `skipped` も"
OLD_STEP_B_SENTENCE = (
    "design 以外の step に `skipped` があったら YAML エラー扱いで停止"
)
OLD_STEP_C_FRAGMENT = "design のみ skipped 可"
OLD_BOUNDARY_ROW_FRAGMENT = "`design` のみ `skipped`）になり"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # This document hard-wraps Japanese prose without a space at the wrap
    # point, so markers are matched after stripping ALL whitespace (never
    # collapsed to a single space) -- the convention already used by
    # tests/test_develop_skill_rewiring.py and
    # tests/test_failed_kind_stop_condition.py.
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


class SkillDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)


# === AC-1: reduction table ==================================================

# IMPLEMENTATION.md Shared Components, "Tier reduction table" row, declared
# locally (Cross-module isolation convention): the terms `reduced` and
# `minimal` must subtract, and the terms every tier must keep.
REDUCED_SUBTRACTS = ("REQUIREMENTS.md", "IMPLEMENTATION.md", "design step")
MINIMAL_ADDITIONALLY_SUBTRACTS = (
    "SPEC.md",
    "TASK.md",
    "タスク分割",
    "VERIFICATION.md",
    "task レベルの並列性",
)
EVERY_TIER_KEEPS = ("テストスイート", "git-setup")


def _find_reduction_table_violations(section):
    """AC-1 matcher: returns a list of human-readable violation
    descriptions if `section` (the Tier 削減表 block) is missing any
    required subtraction or kept term, empty when none is missing."""
    violations = []
    for term in REDUCED_SUBTRACTS:
        if term not in section:
            violations.append(f"reduced subtraction term {term!r} missing")
    for term in REDUCED_SUBTRACTS + MINIMAL_ADDITIONALLY_SUBTRACTS:
        if term not in section:
            violations.append(f"minimal subtraction term {term!r} missing")
    for term in EVERY_TIER_KEEPS:
        if term not in section:
            violations.append(f"kept term {term!r} missing")
    return violations


class TestReductionTableListsSubtractionsAndKept(SkillDocTestCase):
    """AC-1: the reduction table exists, `reduced`'s and `minimal`'s
    subtraction lists match IMPLEMENTATION.md Shared Components, and the
    kept list names the whole test suite and the Step 0 git-setup gate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.section = _section(cls.text, TIER_TABLE_LABEL, UPGRADE_LABEL)

    def test_no_reduction_table_violation(self):
        self.assertEqual(_find_reduction_table_violations(self.section), [])

    def test_full_tier_states_no_subtraction(self):
        full_row = next(
            line
            for line in self.section.splitlines()
            if line.startswith("| `full` |")
        )
        self.assertIn("削減なし", full_row)

    def test_minimal_row_is_additive_over_reduced(self):
        # AC-1's "additionally subtracts" relationship (Design): the
        # minimal row must literally contain the phrase connecting it to
        # reduced's own list, not just a coincidentally-overlapping list.
        self.assertIn("に加えて", self.section)


class TestReductionTableMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_find_reduction_table_violations`."""

    FORGED_TABLE_MISSING_VERIFICATION_MD = (
        "| tier | 削減する対象 |\n"
        "|------|-------------|\n"
        "| `full` | 削減なし |\n"
        "| `reduced` | REQUIREMENTS.md、IMPLEMENTATION.md、design step |\n"
        "| `minimal` | REQUIREMENTS.md、IMPLEMENTATION.md、design step に"
        "加えて、SPEC.md（TASK.md に置換）、タスク分割、task レベルの並列性 |\n"
        "\n全 tier で維持されるもの: テストスイート全体、git-setup ゲート。\n"
    )

    def test_forged_table_is_well_formed_and_found(self):
        # Non-vacuity: every OTHER required term is present in the forgery,
        # so the violation below is attributable solely to the missing one.
        for term in REDUCED_SUBTRACTS + ("SPEC.md", "TASK.md", "タスク分割"):
            self.assertIn(term, self.FORGED_TABLE_MISSING_VERIFICATION_MD)
        self.assertNotIn(
            "VERIFICATION.md", self.FORGED_TABLE_MISSING_VERIFICATION_MD
        )

    def test_matcher_detects_a_missing_subtraction_term(self):
        violations = _find_reduction_table_violations(
            self.FORGED_TABLE_MISSING_VERIFICATION_MD
        )
        self.assertTrue(
            any("VERIFICATION.md" in v for v in violations),
            "expected the matcher to flag the missing VERIFICATION.md term",
        )


# === AC-2: integration worktree never subtracted; parallelism precisely ===

FORBIDDEN_INTEGRATION_WORKTREE_SUBTRACTION_PATTERNS = (
    "integrationworktreeを削減",
    "integrationworktreeを引く",
    "integrationworktreeも削減",
    "integrationworktreeの削減",
    "integrationworktreeを引き算",
)


def _find_integration_worktree_subtraction_violations(text):
    """AC-2 matcher: returns a list of human-readable violation
    descriptions if whitespace-stripped `text` contains any sentence shape
    that reads as subtracting the integration worktree, empty otherwise."""
    stripped = _strip_ws(text)
    return [
        p
        for p in FORBIDDEN_INTEGRATION_WORKTREE_SUBTRACTION_PATTERNS
        if p in stripped
    ]


class TestIntegrationWorktreeNeverSubtracted(SkillDocTestCase):
    """AC-2: no sentence anywhere in the file subtracts the integration
    worktree in any tier, and the parallelism subtraction is stated as a
    single task in a single task worktree."""

    def test_whole_file_has_no_integration_worktree_subtraction(self):
        self.assertEqual(
            _find_integration_worktree_subtraction_violations(self.text), []
        )

    def test_integration_worktree_named_as_kept(self):
        self.assertIn("integration worktree", self.text)
        self.assertTrue(
            _contains(self.text, "integration worktree はどの tier でも削減しない")
        )

    def test_parallelism_stated_as_single_task_single_worktree(self):
        self.assertTrue(
            _contains(
                self.text,
                "単一の task を単一の task worktree で実行することを意味し",
            )
        )


class TestIntegrationWorktreeAbsenceMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_find_integration_worktree_subtraction_violations`."""

    FORGED_SUBTRACTION_SENTENCE = (
        "minimal tier では、並列性に加えて integration worktree を削減する。"
    )

    def test_forged_sentence_is_well_formed_and_found(self):
        self.assertIn("integration worktree", self.FORGED_SUBTRACTION_SENTENCE)
        self.assertIn("削減する", self.FORGED_SUBTRACTION_SENTENCE)

    def test_matcher_detects_a_forged_subtraction_sentence(self):
        violations = _find_integration_worktree_subtraction_violations(
            self.FORGED_SUBTRACTION_SENTENCE
        )
        self.assertNotEqual(violations, [])


# === AC-3: skipped outside design admitted in all four places =============


class TestSkippedOutsideDesignAdmittedInTurnEndCondition1(SkillDocTestCase):
    """AC-3, place 1: the first turn-ending condition admits a skipped
    step outside design, and no longer treats it as design-only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        turn_end_section = _section(cls.text, TURN_END_HEADING, TURN_END_ANCHOR)
        cls.bullet_1 = turn_end_section[
            turn_end_section.index("1. `workflow`") : turn_end_section.index(
                "2. ある step"
            )
        ]

    def test_admits_skipped_step_generally(self):
        self.assertIn("`skipped`", self.bullet_1)
        self.assertIn("design 自身の判断による skip", self.bullet_1)
        self.assertIn("tier によるスキップ", self.bullet_1)

    def test_old_design_only_wording_absent(self):
        self.assertNotIn(OLD_ITEM_1_FRAGMENT, self.bullet_1)

    def test_old_wording_absent_from_whole_file(self):
        self.assertNotIn(OLD_ITEM_1_FRAGMENT, self.text)


class TestSkippedOutsideDesignAdmittedInStepBSentence(SkillDocTestCase):
    """AC-3, place 2: the Step B status sentence admits a skipped step
    outside design without treating it as a YAML error, and keeps
    `skipped_reason` mandatory."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sentence = _section(
            cls.text,
            "`skipped` は create-spec が設定する",
            "`completed_at_commit` の規範的定義",
        )

    def test_admits_skipped_step_generally_not_as_error(self):
        self.assertIn("design 自身の判断による skip", self.sentence)
        self.assertIn("tier によるスキップ", self.sentence)
        self.assertIn("正常な状態として扱い", self.sentence)
        self.assertTrue(_contains(self.sentence, "YAML エラー扱いにはしない"))

    def test_skip_reason_still_mandatory(self):
        self.assertIn("`skipped_reason` は引き続き必須", self.sentence)
        self.assertIn("references/workflow-schema.md", self.sentence)

    def test_old_error_wording_absent(self):
        self.assertNotIn(OLD_STEP_B_SENTENCE, self.sentence)

    def test_old_wording_absent_from_whole_file(self):
        self.assertNotIn(OLD_STEP_B_SENTENCE, self.text)


class TestSkippedOutsideDesignAdmittedInStepCHeading(SkillDocTestCase):
    """AC-3, place 3: the Step C heading admits a skipped step outside
    design."""

    def test_new_heading_present(self):
        self.assertIn(STEP_C_HEADING, self.text)

    def test_heading_names_both_design_and_tier(self):
        self.assertIn("design", STEP_C_HEADING)
        self.assertIn("tier", STEP_C_HEADING)

    def test_old_design_only_wording_absent(self):
        self.assertNotIn(OLD_STEP_C_FRAGMENT, self.text)


class TestSkippedOutsideDesignAdmittedInPhaseBoundaryTable(SkillDocTestCase):
    """AC-3, place 4: the `--once` phase-boundary table's ordinary-step row
    admits a skipped step outside design."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        section = _section(cls.text, ONCE_SECTION_HEADING, STOP_REPORT_HEADING)
        cls.row = next(
            line for line in section.splitlines() if line.startswith("| 通常の step")
        )

    def test_row_admits_skipped_generally(self):
        self.assertIn("`skipped`", self.row)
        self.assertIn("design 自身の skip", self.row)
        self.assertIn("tier による skip", self.row)
        self.assertIn("コミット済み", self.row)

    def test_old_design_only_wording_absent(self):
        self.assertNotIn(OLD_BOUNDARY_ROW_FRAGMENT, self.row)

    def test_old_wording_absent_from_whole_file(self):
        self.assertNotIn(OLD_BOUNDARY_ROW_FRAGMENT, self.text)


# === AC-4: new no-work-required turn-ending condition ======================


def _find_no_work_required_underscore_literal(text):
    """AC-4 matcher: returns True iff the forbidden underscored reason-code
    literal occurs anywhere in `text` (NFR3 -- this file may only ever name
    the hyphenated stop point)."""
    return NO_WORK_REASON_CODE_LITERAL in text


class TestNoWorkStopEntryAddedToTurnEndConditions(SkillDocTestCase):
    """AC-4: the turn-ending conditions list carries one new entry naming
    the no-work stop point by its hyphenated form; the underscored reason
    code never occurs in this file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.turn_end_section = _section(cls.text, TURN_END_HEADING, TURN_END_ANCHOR)

    def test_item_8_present_and_names_hyphenated_stop_point(self):
        self.assertIn("8. Step A", self.turn_end_section)
        self.assertIn(f"`{NO_WORK_STOP_POINT}`", self.turn_end_section)

    def test_item_8_follows_item_7(self):
        item_7_idx = self.turn_end_section.index("7. `--once`")
        item_8_idx = self.turn_end_section.index("8. Step A")
        self.assertGreater(item_8_idx, item_7_idx)

    def test_anchor_still_follows_item_8(self):
        item_8_idx = self.text.index("8. Step A")
        anchor_idx = self.text.index(TURN_END_ANCHOR, item_8_idx)
        self.assertGreater(anchor_idx, item_8_idx)

    def test_underscored_reason_code_absent_from_whole_file(self):
        self.assertFalse(_find_no_work_required_underscore_literal(self.text))


class TestNoWorkStopEntryMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_find_no_work_required_underscore_literal`."""

    FORGED_TEXT_WITH_UNDERSCORE_LITERAL = (
        "stop point `no-work-required`（reason code: no_work_required）"
    )

    def test_forged_text_is_well_formed_and_found(self):
        self.assertIn(
            NO_WORK_REASON_CODE_LITERAL, self.FORGED_TEXT_WITH_UNDERSCORE_LITERAL
        )

    def test_matcher_detects_the_underscored_literal(self):
        self.assertTrue(
            _find_no_work_required_underscore_literal(
                self.FORGED_TEXT_WITH_UNDERSCORE_LITERAL
            )
        )


# === AC-5: upgrade procedure ================================================

UPGRADE_REQUIRED_ELEMENTS = (
    "`skipped` の step を\n`pending` に戻す",
    "新しい\nstatus\n値は一切\n導入しない",
    "review で critical severity の finding が出たとき",
    "verify が `failed` になったとき",
    "降格",
    "create-spec",
    "needs_update",
    "SPEC.md",
)


def _find_upgrade_procedure_violations(section):
    """AC-5 matcher: returns a list of human-readable violation
    descriptions if `section` (the アップグレード手順 block) is missing any
    required element, empty when none is missing. Matched on
    whitespace-stripped text (this document hard-wraps mid-phrase)."""
    stripped = _strip_ws(section)
    violations = []
    for element in UPGRADE_REQUIRED_ELEMENTS:
        if _strip_ws(element) not in stripped:
            violations.append(f"required element {element!r} missing")
    return violations


class TestUpgradeProcedureExpressedAsSkippedToPending(SkillDocTestCase):
    """AC-5: the upgrade procedure is expressed only as skipped becoming
    pending, introduces no new status value, names both triggers, forbids
    downgrading, and includes re-running the completed create-spec step for
    the most-reducing tier."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.section = _section(cls.text, UPGRADE_LABEL, STEP_TABLE_MARKER)

    def test_no_upgrade_procedure_violation(self):
        self.assertEqual(_find_upgrade_procedure_violations(self.section), [])

    def test_downgrade_forbidden_explicitly(self):
        self.assertTrue(_contains(self.section, "降格の禁止"))
        self.assertTrue(_contains(self.section, "元へ戻す操作は一切無く"))

    def test_no_new_status_value_sentence_present(self):
        self.assertTrue(_contains(self.section, "新しい status 値は一切導入しない"))

    def test_minimal_tier_create_spec_re_execution_present(self):
        self.assertTrue(_contains(self.section, "`minimal` tier では"))
        self.assertTrue(
            _contains(self.section, "create-spec の再実行を含める")
        )
        self.assertTrue(
            _contains(
                self.section,
                "create-spec の `status` を `needs_update` に\n設定し",
            )
        )


class TestUpgradeProcedureMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_find_upgrade_procedure_violations`."""

    # Missing the failed-verification trigger and the create-spec
    # re-execution element, on purpose.
    FORGED_PROCEDURE_MISSING_ELEMENTS = (
        "tier の変更は昇格のみを許し、降格は行わない。昇格は `skipped` の "
        "step を `pending` に戻すことで表現し、新しい status 値は一切導入"
        "しない。トリガーは review で critical severity の finding が出た"
        "とき。"
    )

    def test_forged_procedure_is_well_formed_and_found(self):
        self.assertIn("`pending`", self.FORGED_PROCEDURE_MISSING_ELEMENTS)
        self.assertIn(
            "review で critical severity の finding が出たとき",
            self.FORGED_PROCEDURE_MISSING_ELEMENTS,
        )
        self.assertNotIn(
            "verify が `failed` になったとき", self.FORGED_PROCEDURE_MISSING_ELEMENTS
        )
        self.assertNotIn("create-spec", self.FORGED_PROCEDURE_MISSING_ELEMENTS)

    def test_matcher_detects_a_missing_element(self):
        violations = _find_upgrade_procedure_violations(
            self.FORGED_PROCEDURE_MISSING_ELEMENTS
        )
        self.assertTrue(
            any("failed" in v for v in violations),
            "expected the matcher to flag the missing failed-verification trigger",
        )
        self.assertTrue(
            any("create-spec" in v for v in violations),
            "expected the matcher to flag the missing create-spec re-execution",
        )


# === AC-6: automatic-re-entry carve-out enumerates three transitions ======

CARVE_OUT_INTRO_COUNT_PATTERN = re.compile(r"次の\s*(\d+)\s*つで")
CARVE_OUT_EXHAUSTIVENESS_COUNT_PATTERN = re.compile(r"この\s*(\d+)\s*つで網羅的")
CARVE_OUT_BULLET_PATTERN = re.compile(r"^- ", re.MULTILINE)


def _carve_out_counts(section):
    """AC-6: independently reads (a) the enumeration's own bullet count,
    (b) the intro sentence's stated count, and (c) the exhaustiveness
    sentence's stated count from `section`. Returns a 3-tuple of ints, or
    None for any element that cannot be found (so a caller can tell
    "missing" apart from "mismatched")."""

    def _first_int(pattern):
        match = pattern.search(section)
        return int(match.group(1)) if match else None

    bullet_count = len(CARVE_OUT_BULLET_PATTERN.findall(section))
    intro_count = _first_int(CARVE_OUT_INTRO_COUNT_PATTERN)
    exhaustiveness_count = _first_int(CARVE_OUT_EXHAUSTIVENESS_COUNT_PATTERN)
    return (bullet_count, intro_count, exhaustiveness_count)


def _carve_out_counts_match(section, expected):
    """AC-6 matcher: true iff all three of `_carve_out_counts(section)`
    are present and equal to `expected`. This is the Test Notes-required
    independent comparison -- a rewrite that lists `expected` bullets while
    leaving the exhaustiveness sentence's number at the old count fails
    here even though a bare presence check on the sentence would still
    pass."""
    counts = _carve_out_counts(section)
    return all(c == expected for c in counts)


class TestCarveOutEnumeratesThreeTransitions(SkillDocTestCase):
    """AC-6: the automatic-re-entry carve-out enumerates three transitions,
    names the owning document for the new one, and its exhaustiveness
    sentence states the new count."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        step_b_section = _section(cls.text, STEP_B_HEADING, STEP_C_HEADING)
        cls.carve_out_section = _section(
            step_b_section, STOP_CONDITION_3_LABEL, CREATE_PLAN_EXEMPTION_RATIONALE_LABEL
        )

    def test_three_transitions_independently_counted_and_matching(self):
        self.assertTrue(_carve_out_counts_match(self.carve_out_section, 3))

    def test_existing_two_transitions_still_present(self):
        self.assertIn("references/implement-phase.md", self.carve_out_section)
        self.assertIn("route back to planning", self.carve_out_section)
        self.assertIn(
            "references/rework-task-synthesis.md", self.carve_out_section
        )
        self.assertIn(
            "references/contracts/rework-planner-contract.md",
            self.carve_out_section,
        )

    def test_third_transition_names_tier_upgrade_and_owning_section(self):
        self.assertTrue(_contains(self.carve_out_section, "tier 昇格による再エントリ"))
        self.assertTrue(
            _contains(self.carve_out_section, f"下記「{UPGRADE_LABEL.strip('*')}」")
        )

    def test_exhaustiveness_sentence_still_declares_exhaustive(self):
        self.assertIn("網羅的", self.carve_out_section)


class TestCarveOutCountMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_carve_out_counts_match`:
    per the module docstring / task Test Notes, a forged copy whose bullet
    list has three items but whose exhaustiveness sentence still states
    the OLD count ("2") must be rejected -- proving the comparison reads
    the two counts independently rather than trusting the sentence alone."""

    FORGED_MISMATCHED_CARVE_OUT = (
        "該当する遷移は現時点で厳密に次の 3 つで、それぞれ所有ドキュメントを"
        "明記する:\n"
        "- create-plan の route back to planning\n"
        "- rework の spec-change 遷移\n"
        "- tier 昇格による再エントリ\n\n"
        "この列挙は、所有 SSOT 自身がフェーズの自動再エントリを明記している"
        "遷移だけが対象という構成上の理由でこの 2 つで網羅的であり、他の"
        "遷移はこの除外の対象外。"
    )

    def test_forged_carve_out_is_well_formed_and_found(self):
        bullet_count, intro_count, exhaustiveness_count = _carve_out_counts(
            self.FORGED_MISMATCHED_CARVE_OUT
        )
        self.assertEqual(bullet_count, 3)
        self.assertEqual(intro_count, 3)
        self.assertEqual(exhaustiveness_count, 2)

    def test_matcher_detects_a_count_mismatch(self):
        self.assertFalse(
            _carve_out_counts_match(self.FORGED_MISMATCHED_CARVE_OUT, 3)
        )


# === AC-2 (NFR6) / AC-7 (NFR2, NFR6): no gate_id, no review-branch, no
#     confirmation prompt introduced by this task's new content ===========


class TestNoGateIdOrReviewBranchIntroduced(SkillDocTestCase):
    """AC-7: no gate identifier or user question is introduced (NFR6), and
    no tier-conditional branch is added to review perspective selection
    anywhere in this file (NFR2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tier_and_upgrade_section = _section(
            cls.text, TIER_TABLE_LABEL, STEP_TABLE_MARKER
        )
        turn_end_section = _section(cls.text, TURN_END_HEADING, TURN_END_ANCHOR)
        cls.item_8 = turn_end_section[turn_end_section.index("8. Step A") :]

    def test_tier_and_upgrade_section_names_no_gate_id(self):
        self.assertNotIn("gate_id", self.tier_and_upgrade_section)
        self.assertNotIn("AskUserQuestion", self.tier_and_upgrade_section)

    def test_item_8_names_no_gate_id(self):
        self.assertNotIn("gate_id", self.item_8)
        self.assertNotIn("AskUserQuestion", self.item_8)

    def test_tier_and_upgrade_section_does_not_mention_review_perspective_selection(self):
        self.assertNotIn("perspective", self.tier_and_upgrade_section.lower())
        self.assertNotIn("観点", self.tier_and_upgrade_section)


# === Region-ownership regression: Step A and retrospect untouched ========


class TestRegionOwnershipUnchanged(SkillDocTestCase):
    """Test Notes: pin the Step A anchor sentences and the retrospect
    section's own concluding sentence as unchanged by this task's diff --
    task0005 does not own either region (IMPLEMENTATION.md D3)."""

    def test_step_a_heading_and_gate_anchor_present(self):
        self.assertIn(STEP_A_ANCHOR, self.text)
        self.assertIn(STEP_A_IDENTIFIER_GATE_ANCHOR, self.text)

    def test_retrospect_concluding_sentence_present_verbatim(self):
        self.assertIn(RETROSPECT_CONCLUDING_SENTENCE, self.text)


# === AC-7: this module's own standard-library-only import discipline =====


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_own_imports_are_all_stdlib(self):
        import ast

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib_allowed = {"re", "unittest", "pathlib", "ast"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    self.assertIn(top_level, stdlib_allowed)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    top_level = node.module.split(".")[0]
                    self.assertIn(top_level, stdlib_allowed)


if __name__ == "__main__":
    unittest.main()
