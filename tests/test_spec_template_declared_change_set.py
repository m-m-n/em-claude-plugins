"""Tests for task0001 (spec-file-set-completeness): pins the new
`## Declared Change Set` section inside
`em-workflow/references/templates/spec-document.md`'s outer fenced
template body.

Covers task0001 Acceptance Criteria
(feature-docs/spec-file-set-completeness/tasks/task0001.md):

- AC-1 (FR1, NFR3): the heading `## Declared Change Set` exists; its offset
  lies after `### File Structure`, before `## Test Scenarios`, and strictly
  between the outer opening and closing fences of the template body ->
  TestSectionPosition (TS-1), TestSectionInsideOuterFencedBody (TS-2).
- AC-2 (FR3, FR4): the section contains both root literals of Contract MK,
  names every DM-2 feature-docs member and the DM-3 `{T}.tests.yaml`
  member, and (as of task0009, goal-vs-spec-divergence) states the
  create-plan derivation for the feature-specific paths instead of a
  `{placeholder}` slot for the author to hand-enumerate them (DM-8) ->
  TestRootLiteralsPresent, TestEnumerationAndCitation (member /
  design-artifacts / test-docs-member tests), TestDerivationStatementPresent
  (TS-5 / TS-6, spec-document half).
- AC-3 (FR4, NFR2): the section cites `implement-phase.md` as the owner of
  the per-task test record and the phase documents /
  `references/phase-state.md` as the owners of the feature-docs artifacts,
  restating none of their rules -> TestEnumerationAndCitation citation
  tests (TS-6, spec-document half).
- AC-4 (FR5): the section states DM-5 (default-unless-removed), DM-6
  (superset/containment) and DM-7 (the zero-implement-task instance) ->
  TestSemanticsStated (TS-7, spec-document half).
- AC-5 (NFR3, FR6, FR8): English text, the `{placeholder}` / heading
  convention, no rationale beyond the requirements, no rule excluding
  workflow-generated artifacts from the observed change set, every other
  byte of the template unchanged and no file outside this task's declared
  set touched -- satisfied by construction (the task plan's Design table
  assigns this module TS-1, TS-2 and the spec-document half of TS-5, TS-6,
  TS-7 only; not a separate TS here) and re-checked by VERIFICATION.md's
  integrated run.
- AC-6 (NFR5): this module's existence, discovery, stdlib-only imports and
  TS-1 / TS-2 / TS-5..7 (spec-document half) coverage.
- AC-7 (NFR4, NFR5, NFR6): every matcher below has a negative-proof test
  reporting absence against a captured pre-change sample
  (TestValidationDetectsRegressions), each sample guarded for non-vacuity
  by a positively asserted retained anchor (TestPreChangeSampleGuards);
  this module reads only the template it owns (SPEC_TEMPLATE_PATH) and
  touches no file under `feature-docs/`; no pre-existing module under
  `tests/` is edited by this task.

Retention / structural checks exempt from a dedicated negative proof (they
assert content already present before this task's edit, or are
non-vacuity guards rather than content matchers, per IMPLEMENTATION.md's
Conventions section):
- TestSectionPosition.test_file_structure_anchor_is_unique (retention:
  `### File Structure` predates this task's edit).
- TestSectionInsideOuterFencedBody.test_at_least_two_fence_lines_exist
  (non-vacuity guard, not a content matcher).
- TestSectionInsideOuterFencedBody.test_heading_lies_strictly_between_outer_fences
  (derivative of test_heading_present's negative proof, on the same
  DECLARED_CHANGE_SET_HEADING literal; no separate proof needed).
- TestPreChangeSampleGuards.* (guards themselves, not matchers).

Every NEW matcher keeps the literal it matches in a single module-level
constant shared by its positive test and its negative-proof test (never
spelled twice). Content assertions read a whitespace-normalized copy of the
sliced section (line-wrap choices never make an assertion brittle); the
fence-boundary and position assertions read raw, un-normalized offsets
(IMPLEMENTATION.md D5 / TS-2).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_TEMPLATE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "templates" / "spec-document.md"
)

# Contract AN: the new section's anchor and its two neighbouring anchors.
DECLARED_CHANGE_SET_HEADING = "## Declared Change Set"
FILE_STRUCTURE_HEADING = "### File Structure"
TEST_SCENARIOS_HEADING = "## Test Scenarios"

# D5: a fenced-markdown line, used to locate the outer opening fence (the
# first match) and the outer closing fence (the last match) -- never by
# scanning for the first fence terminator, since the body already contains
# nested fenced blocks (architecture diagram, API examples, file-structure
# tree).
FENCE_LINE_PATTERN = re.compile(r"^```", re.MULTILINE)

# Contract MK: the co-occurrence marker's two root literals.
FEATURE_DOCS_ROOT_LITERAL = "feature-docs/{feature}/**"
TEST_DOCS_ROOT_LITERAL = "test-docs/{feature}/**"

# DM-2: the feature-docs members, named verbatim.
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
DESIGN_ARTIFACTS_PHRASE = "the design artifacts the design step produces"

# DM-3: the test-docs member, in its full path form.
TEST_DOCS_MEMBER_PATH = "test-docs/{feature}/{T}.tests.yaml"

# DM-4: citation-only attribution (NFR2 -- cite, never restate).
IMPLEMENT_PHASE_CITATION = "`implement-phase.md`"
PHASE_STATE_CITATION = "`references/phase-state.md`"
PHASE_DOCUMENTS_PHRASE = "phase documents"

# DM-5 .. DM-7: the three semantics claims.
DEFAULT_UNLESS_REMOVED_PHRASE = (
    "are part of the declaration unless the SPEC author explicitly "
    "removes them"
)
SUPERSET_PHRASE = "SUPERSET assertion"
CONTAINED_IN_PHRASE = "CONTAINED IN the declared set"
ZERO_IMPLEMENT_TASK_PHRASE = "produces no implement tasks generates no"
NO_VIOLATION_PHRASE = (
    "a declared path that never materializes is not a violation"
)

# DM-8 (task0009, goal-vs-spec-divergence): the create-plan derivation
# statement that replaces the removed author-enumeration placeholder. The
# feature-specific paths are no longer hand-authored; this section states
# the derivation and cites create-plan-phase.md as its owner (NFR2 --
# cite, never restate).
DERIVATION_STATEMENT_PHRASE = (
    "the feature-specific paths above are derived at create-plan from "
    "every task's `files` entries in `workflow.yaml`"
)
CREATE_PLAN_PHASE_CITATION = "`references/phases/create-plan-phase.md`"

# Regression guard (AC-4): the removed instruction must not reappear.
REMOVED_AUTHOR_PLACEHOLDER = (
    "{Enumerate every file and directory this feature creates or modifies.}"
)

# TS-13 / AC-7: a verbatim pre-change excerpt of
# em-workflow/references/templates/spec-document.md at this task's base
# revision, spanning both retained anchors (`### File Structure` through
# the `## Test Scenarios` opening) -- the exact region this task's section
# is inserted into, captured before the insertion.
PRE_CHANGE_SAMPLE = (
    "### File Structure\n"
    "\n"
    "```\n"
    "internal/\n"
    "├── {feature}/\n"
    "│   ├── handler.go           # HTTP handlers\n"
    "│   ├── handler_test.go\n"
    "│   ├── service.go           # Business logic\n"
    "│   ├── service_test.go\n"
    "│   ├── repository.go        # Data access\n"
    "│   ├── repository_test.go\n"
    "│   ├── model.go             # Data models\n"
    "│   └── errors.go            # Error definitions\n"
    "```\n"
    "\n"
    "## Test Scenarios\n"
    "\n"
    "### Unit Tests\n"
    "- [ ] Test 1: {Description} - {Expected behavior}\n"
)


def _read():
    return SPEC_TEMPLATE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where a line
    happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _declared_change_set_section(text):
    """Slice from the new section's anchor to the following anchor
    (Contract AN), so an assertion can never be satisfied by text
    belonging to a neighbouring section."""
    start = text.index(DECLARED_CHANGE_SET_HEADING)
    end = text.index(TEST_SCENARIOS_HEADING, start)
    return text[start:end]


class TestSectionPosition(unittest.TestCase):
    """TS-1 / AC-1: the anchor exists; its offset in the whitespace-
    normalized text lies after `### File Structure` and before
    `## Test Scenarios`."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read()
        cls.normalized = _normalize_ws(cls.raw)

    def test_heading_present(self):
        self.assertIn(DECLARED_CHANGE_SET_HEADING, self.raw)

    def test_heading_follows_file_structure_and_precedes_test_scenarios(self):
        file_structure_idx = self.normalized.index(FILE_STRUCTURE_HEADING)
        declared_idx = self.normalized.index(DECLARED_CHANGE_SET_HEADING)
        test_scenarios_idx = self.normalized.index(TEST_SCENARIOS_HEADING)
        self.assertLess(file_structure_idx, declared_idx)
        self.assertLess(declared_idx, test_scenarios_idx)

    def test_file_structure_anchor_is_unique(self):
        # Test Notes edge case: if a future edit made this anchor
        # ambiguous, the slice this module (and Contract AN) depends on
        # would silently move.
        self.assertEqual(self.raw.count(FILE_STRUCTURE_HEADING), 1)


class TestSectionInsideOuterFencedBody(unittest.TestCase):
    """TS-2 / AC-1: the anchor's raw offset lies strictly between the
    outer opening fence and the outer closing fence, both located per
    IMPLEMENTATION.md D5 -- the first opening fence and the last closing
    fence of the file."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.fence_offsets = [
            m.start() for m in FENCE_LINE_PATTERN.finditer(cls.text)
        ]

    def test_at_least_two_fence_lines_exist(self):
        # Non-vacuity: the strict-between assertion below is meaningless
        # if there are fewer than two fence lines to bound it.
        self.assertGreaterEqual(len(self.fence_offsets), 2)

    def test_heading_lies_strictly_between_outer_fences(self):
        outer_open = self.fence_offsets[0]
        outer_close = self.fence_offsets[-1]
        declared_idx = self.text.index(DECLARED_CHANGE_SET_HEADING)
        self.assertLess(outer_open, declared_idx)
        self.assertLess(declared_idx, outer_close)


class TestRootLiteralsPresent(unittest.TestCase):
    """TS-5 (spec-document half) / AC-2: the sliced section contains both
    root literals of Contract MK."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_declared_change_set_section(_read()))

    def test_feature_docs_root_literal_present(self):
        self.assertIn(FEATURE_DOCS_ROOT_LITERAL, self.section)

    def test_test_docs_root_literal_present(self):
        self.assertIn(TEST_DOCS_ROOT_LITERAL, self.section)


class TestEnumerationAndCitation(unittest.TestCase):
    """TS-6 (spec-document half) / AC-2, AC-3: the sliced section names
    every DM-2 member and the DM-3 member, and cites `implement-phase.md`
    and the phase documents / `references/phase-state.md` -- citation
    only, per NFR2."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_declared_change_set_section(_read()))

    def test_every_feature_docs_member_named(self):
        for member in FEATURE_DOCS_MEMBERS:
            self.assertIn(f"`{member}`", self.section)

    def test_design_artifacts_phrase_named(self):
        self.assertIn(DESIGN_ARTIFACTS_PHRASE, self.section)

    def test_test_docs_member_named(self):
        self.assertIn(f"`{TEST_DOCS_MEMBER_PATH}`", self.section)

    def test_cites_implement_phase_as_test_record_owner(self):
        self.assertIn(IMPLEMENT_PHASE_CITATION, self.section)

    def test_cites_phase_documents_and_phase_state_as_feature_docs_owners(
        self,
    ):
        self.assertIn(PHASE_DOCUMENTS_PHRASE, self.section)
        self.assertIn(PHASE_STATE_CITATION, self.section)


class TestSemanticsStated(unittest.TestCase):
    """TS-7 (spec-document half) / AC-4: the sliced section states DM-5
    (default-unless-removed), DM-6 (superset/containment) and DM-7 (the
    zero-implement-task instance)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_declared_change_set_section(_read()))

    def test_default_unless_removed_stated(self):
        self.assertIn(DEFAULT_UNLESS_REMOVED_PHRASE, self.section)

    def test_superset_containment_stated(self):
        self.assertIn(SUPERSET_PHRASE, self.section)
        self.assertIn(CONTAINED_IN_PHRASE, self.section)

    def test_zero_implement_task_instance_stated(self):
        self.assertIn(ZERO_IMPLEMENT_TASK_PHRASE, self.section)
        self.assertIn(NO_VIOLATION_PHRASE, self.section)


class TestDerivationStatementPresent(unittest.TestCase):
    """DM-8 (task0009, goal-vs-spec-divergence) / AC-4: the section states
    the create-plan derivation for the feature-specific paths, citing
    `references/phases/create-plan-phase.md`, instead of asking the SPEC
    author to hand-enumerate them."""

    @classmethod
    def setUpClass(cls):
        cls.section = _normalize_ws(_declared_change_set_section(_read()))

    def test_derivation_statement_present(self):
        self.assertIn(DERIVATION_STATEMENT_PHRASE, self.section)

    def test_create_plan_phase_cited(self):
        self.assertIn(CREATE_PLAN_PHASE_CITATION, self.section)

    def test_author_enumeration_placeholder_removed(self):
        self.assertNotIn(REMOVED_AUTHOR_PLACEHOLDER, self.section)


class TestValidationDetectsRegressions(unittest.TestCase):
    """TS-13: proof that every matcher above fails meaningfully -- each is
    exercised against PRE_CHANGE_SAMPLE, a verbatim pre-change excerpt of
    the exact template region this task's section is inserted into, and
    reports absence there."""

    def test_position_matcher_flags_absence_in_pre_change_sample(self):
        self.assertNotIn(DECLARED_CHANGE_SET_HEADING, PRE_CHANGE_SAMPLE)

    def test_root_literals_matcher_flags_absence_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_SAMPLE)
        self.assertNotIn(FEATURE_DOCS_ROOT_LITERAL, sample)
        self.assertNotIn(TEST_DOCS_ROOT_LITERAL, sample)

    def test_enumeration_and_citation_matcher_flags_absence_in_pre_change_sample(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_SAMPLE)
        for member in FEATURE_DOCS_MEMBERS:
            self.assertNotIn(f"`{member}`", sample)
        self.assertNotIn(DESIGN_ARTIFACTS_PHRASE, sample)
        self.assertNotIn(f"`{TEST_DOCS_MEMBER_PATH}`", sample)
        self.assertNotIn(IMPLEMENT_PHASE_CITATION, sample)
        self.assertNotIn(PHASE_STATE_CITATION, sample)

    def test_semantics_matcher_flags_absence_in_pre_change_sample(self):
        sample = _normalize_ws(PRE_CHANGE_SAMPLE)
        self.assertNotIn(DEFAULT_UNLESS_REMOVED_PHRASE, sample)
        self.assertNotIn(SUPERSET_PHRASE, sample)
        self.assertNotIn(CONTAINED_IN_PHRASE, sample)
        self.assertNotIn(ZERO_IMPLEMENT_TASK_PHRASE, sample)
        self.assertNotIn(NO_VIOLATION_PHRASE, sample)

    def test_derivation_statement_matcher_flags_absence_in_pre_change_sample(
        self,
    ):
        sample = _normalize_ws(PRE_CHANGE_SAMPLE)
        self.assertNotIn(DERIVATION_STATEMENT_PHRASE, sample)
        self.assertNotIn(CREATE_PLAN_PHASE_CITATION, sample)


class TestPreChangeSampleGuards(unittest.TestCase):
    """AC-7: PRE_CHANGE_SAMPLE carries both retained anchors, asserted
    positively, so the negative proofs above can never degrade into
    assertions against empty or unrelated text."""

    def test_sample_retains_file_structure_anchor(self):
        self.assertIn(FILE_STRUCTURE_HEADING, PRE_CHANGE_SAMPLE)

    def test_sample_retains_test_scenarios_anchor(self):
        self.assertIn(TEST_SCENARIOS_HEADING, PRE_CHANGE_SAMPLE)


if __name__ == "__main__":
    unittest.main()
