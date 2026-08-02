"""Tests for task0011: the create-spec and create-plan phase protocols, and
the scope verification procedure they share.

Covers task0011 Acceptance Criteria (feature-docs/agent-separation/tasks/
task0011.md):

- AC-1: both phase documents exist and contain every numbered section listed
  for them in design-input.md 5.7 / 5.8, in the same order.
- AC-2: create-spec-phase.md states the worktree is created immediately
  after the feature name is fixed, and that every answer is persisted
  before the worker is re-dispatched.
- AC-3: create-spec-phase.md states the termination conditions (no fixed
  round limit), the progress-fingerprint stop conditions, the three-way
  stalled gate, and the prohibition on automatically converting an
  unresolved item into an assumption.
- AC-4: create-spec-phase.md states that design-system determination runs
  even when the design step is skipped, with the zero-candidate exception.
- AC-5: create-plan-phase.md states the preconditions including the
  design-system cross-product check and its in-place reclassification
  branch that leaves the step status unchanged.
- AC-6: the scope verification procedure states the clean-worktree
  precondition with no automatic cleaning, computes the change set from the
  index and working tree only, and orders the post-dispatch steps with the
  change-set computation before the HEAD evaluation, giving the reason.
- AC-7: the scope verification procedure states the path normalization,
  containment, symlink and case rules, and the abort when the trash tool is
  unavailable.

These deliverables are orchestrator procedure documents (Markdown), not
executable code, so verification is structural/textual against the rendered
documents. Per the task's Test Notes, the expected section vocabulary is
parsed out of design-input.md itself (not hand-copied here) so a document
that drifts from the design fails these tests.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
FEATURE_DOCS = REPO_ROOT / "feature-docs" / "agent-separation"

CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
DESIGN_INPUT_PATH = FEATURE_DOCS / "design-input.md"

SECTION_HEADING_RE = re.compile(r"^(\d+a?)\.\s+\*\*([^*]+)\*\*", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _design_text():
    return _read(DESIGN_INPUT_PATH)


def _toc_sections(design_text, start_marker, end_marker):
    """Parse the numbered, bold-titled table-of-contents items out of a
    design-input.md phase section (e.g. "1. **Purpose and ownership**"),
    returning an ordered list of (number, title) tuples."""
    section = _slice(design_text, start_marker, end_marker)
    items = [(m.group(1), m.group(2).strip()) for m in SECTION_HEADING_RE.finditer(section)]
    return items


def _first_index(text, needle):
    idx = text.find(needle)
    if idx == -1:
        raise AssertionError(f"expected to find {needle!r} in document")
    return idx


class TestDesignInputSelfCheck(unittest.TestCase):
    """Sanity check on the TOC parser itself, so a broken parser cannot make
    the section-coverage assertions vacuously pass."""

    def test_5_7_yields_the_expected_item_count(self):
        design_text = _design_text()
        items = _toc_sections(
            design_text, "### 5.7 create-spec", "### 5.8 create-plan"
        )
        # 1..13 plus 11a
        self.assertEqual(len(items), 14)
        self.assertEqual(items[0], ("1", "Purpose and ownership"))
        self.assertEqual(items[-1], ("13", "Completion"))
        self.assertIn(("11a", "design system の確定"), items)

    def test_5_8_yields_the_expected_item_count(self):
        design_text = _design_text()
        items = _toc_sections(
            design_text, "### 5.8 create-plan", "### 5.9 question"
        )
        self.assertEqual(len(items), 11)
        self.assertEqual(items[0], ("1", "Purpose and ownership"))
        self.assertEqual(items[-1], ("11", "Completion or failure"))


class TestFilesExist(unittest.TestCase):
    def test_create_spec_phase_doc_exists(self):
        self.assertTrue(
            CREATE_SPEC_PATH.is_file(), f"expected {CREATE_SPEC_PATH} to exist"
        )

    def test_create_plan_phase_doc_exists(self):
        self.assertTrue(
            CREATE_PLAN_PATH.is_file(), f"expected {CREATE_PLAN_PATH} to exist"
        )


class TestCreateSpecSectionCoverageAndOrder(unittest.TestCase):
    """AC-1: create-spec-phase.md contains every section listed in
    design-input.md 5.7, in order."""

    # Section 11a's design-input.md title is Japanese ("design system の確定");
    # the rendered corpus is English for structural documents, so this one
    # entry is translated rather than located by literal substring. Every
    # other title below is asserted against the verbatim design-input.md
    # text.
    SECTION_11A_ENGLISH_MARKER = "Design-system determination"

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)
        design_text = _design_text()
        cls.items = _toc_sections(
            design_text, "### 5.7 create-spec", "### 5.8 create-plan"
        )

    def test_every_section_title_present(self):
        for number, title in self.items:
            if number == "11a":
                self.assertIn(
                    self.SECTION_11A_ENGLISH_MARKER,
                    self.text,
                    "expected an English rendering of design-input.md's "
                    "section 11a (design system determination)",
                )
                continue
            self.assertIn(
                title,
                self.text,
                f"create-spec-phase.md is missing section {number} {title!r}",
            )

    def test_sections_appear_in_design_order(self):
        positions = []
        for number, title in self.items:
            marker = (
                self.SECTION_11A_ENGLISH_MARKER if number == "11a" else title
            )
            positions.append(_first_index(self.text, marker))
        self.assertEqual(
            positions,
            sorted(positions),
            "create-spec-phase.md sections are out of order relative to "
            "design-input.md 5.7",
        )


class TestCreatePlanSectionCoverageAndOrder(unittest.TestCase):
    """AC-1: create-plan-phase.md contains every section listed in
    design-input.md 5.8, in order."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)
        design_text = _design_text()
        cls.items = _toc_sections(
            design_text, "### 5.8 create-plan", "### 5.9 question"
        )

    def test_every_section_title_present(self):
        for number, title in self.items:
            self.assertIn(
                title,
                self.text,
                f"create-plan-phase.md is missing section {number} {title!r}",
            )

    def test_sections_appear_in_design_order(self):
        positions = [_first_index(self.text, title) for _, title in self.items]
        self.assertEqual(
            positions,
            sorted(positions),
            "create-plan-phase.md sections are out of order relative to "
            "design-input.md 5.8",
        )


class TestCreateSpecBootstrapAndPersistence(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_worktree_created_immediately_after_feature_name_fixed(self):
        lowered = self.text.lower()
        self.assertIn("immediately after the feature name is fixed", lowered)
        self.assertIn("worktree", lowered)

    def test_every_answer_persisted_before_redispatch(self):
        lowered = self.text.lower()
        self.assertIn("persisted", lowered)
        self.assertIn("before", lowered)
        self.assertIn("re-dispatch", lowered)


class TestCreateSpecTerminationAndLoopStop(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_no_fixed_round_limit(self):
        self.assertIn("no fixed round limit", self.text.lower())

    def test_progress_fingerprint_stop_conditions(self):
        self.assertIn("progress_fingerprint", self.text)
        # The three concrete stop triggers named in design-input.md 5.7.
        self.assertIn("regenerated", self.text.lower())
        self.assertIn(
            "unchanged across two consecutive dispatches", self.text.lower()
        )

    def test_three_way_stalled_gate(self):
        self.assertIn("create-spec.stalled", self.text)
        lowered = self.text.lower()
        self.assertIn("continue", lowered)
        self.assertIn("tbd", lowered)
        self.assertIn("abort", lowered)

    def test_automatic_assumption_conversion_prohibited(self):
        self.assertIn(
            "MUST NOT automatically convert",
            self.text,
        )
        self.assertIn("explicitly select", self.text.lower())


class TestCreateSpecDesignSystemDetermination(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_runs_even_when_design_is_skipped(self):
        lowered = self.text.lower()
        self.assertIn("must run even when", lowered)
        self.assertIn("skipped", lowered)

    def test_zero_candidate_exception_stated(self):
        lowered = self.text.lower()
        self.assertIn("zero", lowered)
        self.assertIn("design_system_candidates", self.text)
        self.assertIn("kind: none", lowered)
        self.assertIn("without asking", lowered)


class TestCreatePlanPreconditions(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_design_system_cross_product_check_precondition(self):
        self.assertIn("project.design_system", self.text)
        lowered = self.text.lower()
        self.assertIn("cross-product", lowered)

    def test_reclassification_branch_leaves_step_status_unchanged(self):
        self.assertIn("design-system.reclassify", self.text)
        lowered = self.text.lower()
        self.assertIn("without changing", lowered)
        self.assertIn("status", lowered)
        self.assertIn("restart", lowered)


class TestScopeVerificationOwnershipAndReference(unittest.TestCase):
    """Scope verification is owned once, in create-spec-phase.md, and
    referenced (not duplicated) from create-plan-phase.md."""

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_create_spec_owns_the_scope_verification_section(self):
        self.assertIn("Scope verification", self.spec_text)

    def test_create_plan_references_it_by_path_not_duplicate(self):
        self.assertIn("create-spec-phase.md", self.plan_text)
        # The create-plan document must not restate the snapshot mechanics
        # that belong to the owning section.
        self.assertNotIn("git hash-object", self.plan_text)
        self.assertNotIn("gio trash", self.plan_text)


class TestScopeVerificationCleanPreconditionAndChangeSet(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_clean_worktree_precondition_no_automatic_cleaning(self):
        lowered = self.text.lower()
        self.assertIn("clean", lowered)
        self.assertIn("abort without dispatching", lowered)
        self.assertIn("never force-clean", lowered)

    def test_change_set_from_index_and_working_tree_only(self):
        self.assertIn("index + working tree", self.text)
        self.assertIn(
            "HEAD layer is",
            self.text,
        )
        self.assertIn("never", self.text.lower())

    def test_post_dispatch_order_change_set_before_head_and_reason(self):
        change_set_idx = _first_index(
            self.text, "Compute the worker's change set"
        )
        head_move_idx = _first_index(
            self.text, "Evaluate whether HEAD moved"
        )
        self.assertLess(
            change_set_idx,
            head_move_idx,
            "change-set computation must be ordered before HEAD evaluation",
        )
        lowered = self.text.lower()
        self.assertIn("never folded into the baseline", lowered)
        self.assertIn("never misreported", lowered)


class TestScopeVerificationPathRulesAndTrash(unittest.TestCase):
    """AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_path_normalization_and_containment_rules(self):
        lowered = self.text.lower()
        self.assertIn("project-root-relative", lowered)
        self.assertIn("realpath", lowered)
        self.assertIn("segments", lowered)
        self.assertIn("feature-docs/example2", self.text)
        self.assertIn("feature-docs/example", self.text)

    def test_symlink_and_case_rules(self):
        lowered = self.text.lower()
        self.assertIn("symlink", lowered)
        self.assertIn("case-sensitive", lowered)
        self.assertIn("case-insensitive", lowered)

    def test_abort_when_trash_tool_unavailable(self):
        self.assertIn("gio", self.text)
        lowered = self.text.lower()
        self.assertIn("unavailable", lowered)
        self.assertIn("do not delete or move anything", lowered)


class TestNoRestatedSiblingSsotContent(unittest.TestCase):
    """Edge case (Test Notes): neither document restates the question packet
    fields (owned by question-packet-schema.md) or the workflow patch
    application rules (owned by workflow-patch.md)."""

    QUESTION_PACKET_OWNED_TOKENS = (
        r"^[a-z][a-z0-9-]*-q[0-9]{4}$",  # packet_id pattern
        r"^[a-z][a-z0-9._-]*$",  # question_id pattern
        "confirmed_facts[]",
        "assumptions[].",
    )
    WORKFLOW_PATCH_OWNED_TOKENS = (
        "Reject unless `base_input_digest` matches the digest recomputed",
        "single-write application",
        "All sixteen rules apply",
    )

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_neither_doc_restates_question_packet_internal_fields(self):
        for token in self.QUESTION_PACKET_OWNED_TOKENS:
            self.assertNotIn(
                token,
                self.spec_text,
                f"create-spec-phase.md must not restate question-packet-schema.md token {token!r}",
            )
            self.assertNotIn(
                token,
                self.plan_text,
                f"create-plan-phase.md must not restate question-packet-schema.md token {token!r}",
            )

    def test_neither_doc_restates_workflow_patch_application_rules(self):
        for token in self.WORKFLOW_PATCH_OWNED_TOKENS:
            self.assertNotIn(
                token,
                self.spec_text,
                f"create-spec-phase.md must not restate workflow-patch.md token {token!r}",
            )
            self.assertNotIn(
                token,
                self.plan_text,
                f"create-plan-phase.md must not restate workflow-patch.md token {token!r}",
            )


if __name__ == "__main__":
    unittest.main()
