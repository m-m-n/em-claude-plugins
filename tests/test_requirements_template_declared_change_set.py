"""Tests for task0002 (spec-file-set-completeness): the REQUIREMENTS
template's Japanese half of the "declared change set" default-membership
statement, in
`em-workflow/references/templates/requirements-document.md`.

Covers task0002 Acceptance Criteria
(feature-docs/spec-file-set-completeness/tasks/task0002.md):

- AC-1 (FR2, NFR3): `### 9.4 宣言された変更集合` exists under `## 9. 制約条件`;
  its offset lies after `### 9.3 スケジュール制約`, before
  `## 10. 想定される課題とリスク`, and strictly between the outer opening and
  closing fences of the template body.
- AC-2 (FR2): every pre-existing top-level heading `## 1. 概要` ..
  `## 15. 参考資料` is present with its number and title unchanged and in
  unchanged relative order.
- AC-3 (FR3, FR4): the new subsection contains both root literals, names
  every feature-docs member and the test-docs member, and (as of task0009,
  goal-vs-spec-divergence) states the create-plan derivation for the
  feature-specific paths instead of a placeholder slot for the author to
  hand-enumerate them.
- AC-4 (FR4, FR5, NFR2): the new subsection cites `implement-phase.md` and
  the phase documents / `references/phase-state.md` without restating their
  rules, and states the default-unless-removed rule, the superset /
  containment rule and the zero-implement-task non-violation instance.
- AC-5 (NFR3, FR6, FR8): the addition carries no rationale beyond the
  requirements and introduces no rule excluding workflow-generated
  artifacts from the observed change set.
- AC-6 (NFR5): this module exists, is discovered, imports nothing outside
  the standard library, and implements TS-3, TS-4 and the
  requirements-document half of TS-5, TS-6 and TS-7.
- AC-7 (NFR4, NFR5, NFR6): every NEW matcher has a negative-proof test
  against a captured pre-change sample; the numbering guard (TS-4) is
  RETENTION and is exempt -- it is expected to pass before and after this
  task's edit, so it has no negative proof. Every pre-change sample is
  guarded for non-vacuity by a positively-asserted retained anchor.

Content assertions read the whitespace-normalized slice (`_normalize_ws`);
position, fence and uniqueness assertions read raw, un-normalized offsets.

Matcher -> negative-proof inventory (every NEW matcher this module adds):

- TestSectionPosition.test_anchor_present ->
  TestValidationDetectsRegressions.test_position_matcher_flags_absence_in_pre_change_section
- TestRootLiterals.test_both_root_literals_present_in_subsection ->
  TestValidationDetectsRegressions.test_root_literals_matcher_flags_absence_in_pre_change_section
- TestEnumerationAndCitation.test_all_feature_docs_members_named ->
  TestValidationDetectsRegressions.test_feature_docs_members_matcher_flags_absence_in_pre_change_section
- TestEnumerationAndCitation.test_test_docs_member_named_with_path_form ->
  TestValidationDetectsRegressions.test_test_docs_member_matcher_flags_absence_in_pre_change_section
- TestDerivationStatementPresent.test_derivation_statement_present
  (task0009, goal-vs-spec-divergence; replaces the removed
  test_placeholder_slot_present) ->
  TestValidationDetectsRegressions.test_derivation_statement_matcher_flags_absence_in_pre_change_section
- TestEnumerationAndCitation.test_cites_implement_phase_and_phase_state ->
  TestValidationDetectsRegressions.test_citation_matcher_flags_absence_in_pre_change_section
- TestSemantics.* (DM-5, DM-6, DM-7) ->
  TestValidationDetectsRegressions.test_semantics_matchers_flag_absence_in_pre_change_section
- TestNoExtraRationaleOrExclusionRule.* (DM-9, regression guards, no
  pre-change sample exists since these phrases are never written) ->
  TestValidationDetectsRegressions.test_exclusion_rule_and_rationale_guards_flag_synthetic_bad_sample
- TestNumberingGuard.* -> RETENTION matcher, exempt (see AC-7 above).
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
REQUIREMENTS_TEMPLATE_PATH = (
    PLUGIN_ROOT / "references" / "templates" / "requirements-document.md"
)

# --- Contract AN anchors ---------------------------------------------------
HEADING_9 = "## 9. 制約条件"
HEADING_91 = "### 9.1 技術的制約"
HEADING_92 = "### 9.2 ビジネス上の制約"
HEADING_93 = "### 9.3 スケジュール制約"
HEADING_94 = "### 9.4 宣言された変更集合"
HEADING_10 = "## 10. 想定される課題とリスク"

# Every pre-existing top-level heading, in file order (TS-4 / AC-2).
TOP_LEVEL_HEADINGS = (
    "## 1. 概要",
    "## 2. ビジネス要件",
    "## 3. ユースケース",
    "## 4. 機能要件",
    "## 5. 非機能要件",
    "## 6. UI/UX要件",
    "## 7. データ要件",
    "## 8. 外部連携",
    HEADING_9,
    HEADING_10,
    "## 11. 成功基準",
    "## 12. テストシナリオ",
    "## 13. 用語定義",
    "## 14. 確認事項",
    "## 15. 参考資料",
)

# --- Contract DM literals ---------------------------------------------------
# DM-1: root literals, verbatim.
ROOT_FEATURE_DOCS = "feature-docs/{feature}/**"
ROOT_TEST_DOCS = "test-docs/{feature}/**"

# DM-2: the nine feature-docs members, verbatim.
FEATURE_DOCS_MEMBERS = (
    "REQUIREMENTS.md",
    "SPEC.md",
    "IMPLEMENTATION.md",
    "workflow.yaml",
    "phase-state/",
    "tasks/",
    "reviews/roundN.yaml",
    "VERIFICATION.md",
    "retrospect.yaml",
)

# DM-3: the test-docs member and its path form, verbatim.
TEST_DOCS_MEMBER = "{T}.tests.yaml"
TEST_DOCS_PATH_FORM = "test-docs/{feature}/{T}.tests.yaml"

# DM-4: citation-only literals.
CITATION_IMPLEMENT_PHASE = "implement-phase.md"
CITATION_PHASE_STATE = "references/phase-state.md"
CITATION_PHASE_DOCUMENTS_PHRASE = "各フェーズドキュメント"

# DM-8 (task0009, goal-vs-spec-divergence): the create-plan derivation
# statement that replaces the removed author-enumeration placeholder.
DERIVATION_STATEMENT_PHRASE = (
    "このフィーチャー固有のパスは手動で列挙せず、create-plan で "
    "`workflow.yaml` の各タスクの `files` から導出する"
)
CREATE_PLAN_PHASE_CITATION = "`references/phases/create-plan-phase.md`"

# Regression guard (AC-3): the removed placeholder pattern must not
# reappear.
REMOVED_PLACEHOLDER_PATTERN = re.compile(r"\{変更対象パス\d*\}")

# DM-5: default-unless-removed.
DEFAULT_UNLESS_REMOVED_PHRASE = "明示的に除外しない限り"
DELIBERATE_NARROWING_PHRASE = "除外は意図的な絞り込みであり、記載漏れによる省略ではない"

# DM-6: superset / containment.
SUPERSET_PHRASE = "スーパーセット"
CONTAINED_IN_PHRASE = "宣言に含まれる（CONTAINED IN）"

# DM-7: zero-implement-task instance and the "never materializes" claim.
NOT_MATERIALIZE_NOT_VIOLATION_PHRASE = "実際には生成されないパスが宣言されていても違反にはならない"
ZERO_IMPLEMENT_TASK_PHRASE = (
    "implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` "
    "ディレクトリを生成しない"
)

# DM-9: forbidden phrasing this subsection must never contain -- a
# verify-side exclusion rule, or rationale beyond what the requirements
# state. No pre-change sample exists for these (the phrases were never
# written anywhere), so the negative proof below uses a synthetic sample
# that a violating document would contain (NFR5).
EXCLUSION_RULE_PHRASE = "観測される変更集合から除外"
RATIONALE_MARKER_WORDS = ("なぜなら", "理由は")

# The pre-change (base-revision) content of section 9, captured verbatim --
# from `## 9. 制約条件` up to (not including) `## 10. ...`. Its three
# existing subsections (9.1, 9.2, 9.3) are the RETAINED anchors: all three
# survive this task's edit unchanged (Design / Test Notes).
PRE_CHANGE_SECTION_9_SAMPLE = (
    "## 9. 制約条件\n"
    "\n"
    "### 9.1 技術的制約\n"
    "- {制約1}\n"
    "- {制約2}\n"
    "\n"
    "### 9.2 ビジネス上の制約\n"
    "- {制約1}\n"
    "- {制約2}\n"
    "\n"
    "### 9.3 スケジュール制約\n"
    "- {制約}\n"
    "\n"
)


def _read():
    return REQUIREMENTS_TEMPLATE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _outer_fence_bounds(text):
    """The outer fenced template body's [start, end) offsets, taken from
    the file's FIRST opening fence and LAST closing fence (D5) -- the body
    already contains nested fenced blocks, so scanning for the first fence
    terminator would find a nested one instead."""
    first = text.index("```markdown")
    last = text.rindex("```") + len("```")
    return first, last


def _subsection_94_slice(text):
    """Section slicing runs from the subsection anchor to the following
    anchor (Contract AN)."""
    start = text.index(HEADING_94)
    end = text.index(HEADING_10, start)
    return text[start:end]


class TestSectionPosition(unittest.TestCase):
    """TS-3 / AC-1: the subsection anchor exists, its offset lies after
    `### 9.3 スケジュール制約` and before `## 10. 想定される課題とリスク`, and
    it lies strictly between the outer opening and closing fences."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_anchor_present(self):
        self.assertIn(HEADING_94, self.text)

    def test_anchor_occurs_exactly_once(self):
        # Uniqueness is required for the slice in _subsection_94_slice to
        # be well-defined (Test Notes edge case).
        self.assertEqual(self.text.count(HEADING_94), 1)

    def test_93_heading_occurs_exactly_once(self):
        self.assertEqual(self.text.count(HEADING_93), 1)

    def test_10_heading_occurs_exactly_once(self):
        self.assertEqual(self.text.count(HEADING_10), 1)

    def test_anchor_after_93_before_10(self):
        idx_94 = self.text.index(HEADING_94)
        idx_93 = self.text.index(HEADING_93)
        idx_10 = self.text.index(HEADING_10)
        self.assertGreater(idx_94, idx_93)
        self.assertLess(idx_94, idx_10)

    def test_anchor_strictly_inside_outer_fences(self):
        fence_start, fence_end = _outer_fence_bounds(self.text)
        idx_94 = self.text.index(HEADING_94)
        self.assertGreater(idx_94, fence_start)
        self.assertLess(idx_94, fence_end)


class TestNumberingGuard(unittest.TestCase):
    """TS-4 / AC-2: every pre-existing top-level heading `## 1. 概要` ..
    `## 15. 参考資料` is present with its number and title unchanged, in
    unchanged relative order.

    RETENTION matcher, exempt from a negative proof (AC-7 / module
    docstring): it is expected to be green both before and after this
    task's edit, since numbering is never touched.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_all_top_level_headings_present_and_unchanged(self):
        for heading in TOP_LEVEL_HEADINGS:
            self.assertIn(heading, self.text)

    def test_top_level_headings_relative_order_unchanged(self):
        indices = [self.text.index(h) for h in TOP_LEVEL_HEADINGS]
        self.assertEqual(indices, sorted(indices))


class TestRootLiterals(unittest.TestCase):
    """TS-5 (requirements half) / AC-3: the sliced subsection contains
    both root literals of Contract MK."""

    @classmethod
    def setUpClass(cls):
        cls.slice = _normalize_ws(_subsection_94_slice(_read()))

    def test_both_root_literals_present_in_subsection(self):
        self.assertIn(ROOT_FEATURE_DOCS, self.slice)
        self.assertIn(ROOT_TEST_DOCS, self.slice)


class TestEnumerationAndCitation(unittest.TestCase):
    """TS-6 (requirements half) / AC-3, AC-4: the sliced subsection names
    every DM-2 member and the DM-3 member, and cites `implement-phase.md`
    and the phase documents / `references/phase-state.md` (DM-4)."""

    @classmethod
    def setUpClass(cls):
        cls.slice = _normalize_ws(_subsection_94_slice(_read()))

    def test_all_feature_docs_members_named(self):
        for member in FEATURE_DOCS_MEMBERS:
            self.assertIn(member, self.slice)

    def test_test_docs_member_named_with_path_form(self):
        self.assertIn(TEST_DOCS_MEMBER, self.slice)
        self.assertIn(TEST_DOCS_PATH_FORM, self.slice)

    def test_cites_implement_phase_and_phase_state(self):
        self.assertIn(CITATION_IMPLEMENT_PHASE, self.slice)
        self.assertIn(CITATION_PHASE_STATE, self.slice)
        self.assertIn(CITATION_PHASE_DOCUMENTS_PHRASE, self.slice)


class TestDerivationStatementPresent(unittest.TestCase):
    """DM-8 (task0009, goal-vs-spec-divergence) / AC-3: the subsection
    states the create-plan derivation for the feature-specific paths,
    citing `references/phases/create-plan-phase.md`, instead of asking the
    author to hand-enumerate them via the removed `{変更対象パスN}`
    placeholder."""

    @classmethod
    def setUpClass(cls):
        cls.slice = _normalize_ws(_subsection_94_slice(_read()))

    def test_derivation_statement_present(self):
        self.assertIn(DERIVATION_STATEMENT_PHRASE, self.slice)

    def test_create_plan_phase_cited(self):
        self.assertIn(CREATE_PLAN_PHASE_CITATION, self.slice)

    def test_author_enumeration_placeholder_removed(self):
        self.assertIsNone(REMOVED_PLACEHOLDER_PATTERN.search(self.slice))


class TestSemantics(unittest.TestCase):
    """TS-7 (requirements half) / AC-4: the sliced subsection states DM-5,
    DM-6 and DM-7, including the zero-implement-task instance."""

    @classmethod
    def setUpClass(cls):
        cls.slice = _normalize_ws(_subsection_94_slice(_read()))

    def test_default_unless_removed_stated(self):
        self.assertIn(DEFAULT_UNLESS_REMOVED_PHRASE, self.slice)

    def test_removal_is_deliberate_narrowing_not_silent_omission(self):
        self.assertIn(DELIBERATE_NARROWING_PHRASE, self.slice)

    def test_superset_and_contained_in_stated(self):
        self.assertIn(SUPERSET_PHRASE, self.slice)
        self.assertIn(CONTAINED_IN_PHRASE, self.slice)

    def test_declared_path_never_materializing_not_a_violation(self):
        self.assertIn(NOT_MATERIALIZE_NOT_VIOLATION_PHRASE, self.slice)

    def test_zero_implement_task_instance_named(self):
        self.assertIn(ZERO_IMPLEMENT_TASK_PHRASE, self.slice)


class TestNoExtraRationaleOrExclusionRule(unittest.TestCase):
    """AC-5 / DM-9: the addition carries no rationale beyond what the
    requirements state, and introduces no rule that subtracts anything
    from the observed change set at verification time. Regression
    guards -- these phrases must never appear."""

    @classmethod
    def setUpClass(cls):
        cls.slice = _normalize_ws(_subsection_94_slice(_read()))

    def test_no_exclusion_rule_phrase(self):
        self.assertNotIn(EXCLUSION_RULE_PHRASE, self.slice)

    def test_no_rationale_marker_words(self):
        for word in RATIONALE_MARKER_WORDS:
            self.assertNotIn(word, self.slice)


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully (a test that can
    never fail is not a test) -- one negative-proof per NEW matcher,
    demonstrated against the captured pre-change section-9 sample or,
    where no pre-change text exists, a synthetic sample a violating
    document would contain (NFR5). TestNumberingGuard is a RETENTION
    matcher and is exempt (see module docstring)."""

    def test_position_matcher_flags_absence_in_pre_change_section(self):
        self.assertNotIn(HEADING_94, PRE_CHANGE_SECTION_9_SAMPLE)

    def test_root_literals_matcher_flags_absence_in_pre_change_section(self):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        self.assertNotIn(ROOT_FEATURE_DOCS, sample)
        self.assertNotIn(ROOT_TEST_DOCS, sample)

    def test_feature_docs_members_matcher_flags_absence_in_pre_change_section(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        for member in FEATURE_DOCS_MEMBERS:
            self.assertNotIn(member, sample)

    def test_test_docs_member_matcher_flags_absence_in_pre_change_section(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        self.assertNotIn(TEST_DOCS_MEMBER, sample)
        self.assertNotIn(TEST_DOCS_PATH_FORM, sample)

    def test_derivation_statement_matcher_flags_absence_in_pre_change_section(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        self.assertNotIn(DERIVATION_STATEMENT_PHRASE, sample)
        self.assertNotIn(CREATE_PLAN_PHASE_CITATION, sample)

    def test_citation_matcher_flags_absence_in_pre_change_section(self):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        self.assertNotIn(CITATION_IMPLEMENT_PHASE, sample)
        self.assertNotIn(CITATION_PHASE_STATE, sample)

    def test_semantics_matchers_flag_absence_in_pre_change_section(self):
        sample = _normalize_ws(PRE_CHANGE_SECTION_9_SAMPLE)
        self.assertNotIn(DEFAULT_UNLESS_REMOVED_PHRASE, sample)
        self.assertNotIn(DELIBERATE_NARROWING_PHRASE, sample)
        self.assertNotIn(SUPERSET_PHRASE, sample)
        self.assertNotIn(CONTAINED_IN_PHRASE, sample)
        self.assertNotIn(NOT_MATERIALIZE_NOT_VIOLATION_PHRASE, sample)
        self.assertNotIn(ZERO_IMPLEMENT_TASK_PHRASE, sample)

    def test_exclusion_rule_and_rationale_guards_flag_synthetic_bad_sample(
        self,
    ):
        # No pre-change sample can demonstrate these (the phrases are
        # never written anywhere, including in the base revision) --
        # NFR5 permits a synthetic sample that a violating document would
        # contain.
        bad_sample = (
            "検証時には、ワークフローが自動生成したファイルは"
            "観測される変更集合から除外する。なぜなら手動編集ではないからです。"
        )
        self.assertIn(EXCLUSION_RULE_PHRASE, bad_sample)
        self.assertIn(RATIONALE_MARKER_WORDS[0], bad_sample)


class TestPreChangeSampleGuard(unittest.TestCase):
    """Non-vacuity guard (Contract 4 precedent): the pre-change section-9
    sample carries its three RETAINED subsection anchors, asserted
    positively, so the negative proofs above cannot silently degrade into
    an assertion against empty text."""

    def test_sample_retains_91_anchor(self):
        self.assertIn(HEADING_91, PRE_CHANGE_SECTION_9_SAMPLE)

    def test_sample_retains_92_anchor(self):
        self.assertIn(HEADING_92, PRE_CHANGE_SECTION_9_SAMPLE)

    def test_sample_retains_93_anchor(self):
        self.assertIn(HEADING_93, PRE_CHANGE_SECTION_9_SAMPLE)


if __name__ == "__main__":
    unittest.main()
