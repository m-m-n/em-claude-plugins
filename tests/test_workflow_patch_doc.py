"""Tests for task0002: em-workflow/references/workflow-patch.md.

Covers task0002 Acceptance Criteria (feature-docs/agent-separation/
tasks/task0002.md):

- AC-1: the doc exists and documents both operations with the
  operation/mode/target/issuer matrix from design-input.md 5.5.
- AC-2: tasks_patch, including replace_all permission conditions and the
  append provenance / expected_next_task_id requirements.
- AC-3: step_patches addressed by step_id, only `status` settable,
  base_commit / completed_at_commit not worker-settable.
- AC-4: the complete preserve path vocabulary and per-operation mandatory
  sets, including workflow.implement.base_commit for append_rework.
- AC-5: all sixteen application rules, ordered, including single-write
  application and the rule R2 commit sequence.
- AC-6: project / review summary block are orchestrator-updated and
  absent from worker patches; domains SSOT is review-rules.yaml.

This is a documentation task (Test Notes: "Verified structurally"), so these
are structural/textual assertions over the Markdown, not behavioral tests of
running code. Per the Test Notes, the expected vocabularies/counts are
derived by parsing design-input.md 5.5 rather than hard-coded, so this test
does not become a second, independently-drifting copy of the same table
(NFR6 applies to tests too).

task0003 (feature-docs/create-plan-status-conflict/tasks/task0003.md) adds
TestReplaceAllPermissionConditionsPinned below, covering that task's AC-2:
the `replace_all` permission-conditions section is pinned precisely (exactly
two permitted create-plan entry statuses, the tasks-empty-or-all-pending
floor, application rule 5 still pointing at the section) so an accidental
future relaxation of `workflow-patch.md` -- which this feature's D1 requires
to stay byte-identical -- fails loudly. Scoped to the permission-conditions
section and the application-rule list so an occurrence of the same words
elsewhere in the document cannot satisfy them.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_INPUT_PATH = (
    REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"
)
DOC_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


class DesignInputFixture:
    """Derives the expected vocabularies/counts from design-input.md 5.5."""

    def __init__(self):
        full = _read(DESIGN_INPUT_PATH)
        self.section = _extract_section(
            full, "### 5.5 workflow patch", "### 5.6 phase-state"
        )

    def operation_mode_pairs(self):
        pairs = re.findall(
            r"`(replace_planning|append_rework)`\s*\|\s*`(replace_all|append)`",
            self.section,
        )
        assert pairs, "expected to find the operation/mode matrix rows"
        return pairs

    def preserve_vocabulary(self):
        match = re.search(r"許可語彙:\n\n((?:- `[^\n]+`\n)+)", self.section)
        assert match, "expected the preserve permitted-vocabulary bullet list"
        return re.findall(r"`([^`]+)`", match.group(1))

    def application_rules(self):
        rules_section = _extract_section(
            self.section, "#### 5.5.5 適用規則", "#### 5.5.6 domains"
        )
        rules = re.findall(r"^(\d+)\. (.+)$", rules_section, re.MULTILINE)
        assert rules, "expected the numbered application rules list"
        return rules

    def append_rework_mandatory_preserve(self):
        # Scope to 5.5.4 specifically -- `append_rework` also appears in the
        # earlier 5.5 operation/mode matrix row (bound to mode `append`),
        # which an unscoped search would match first.
        mandatory_section = _extract_section(
            self.section, "#### 5.5.4 preserve", "#### 5.5.5 適用規則"
        )
        match = re.search(
            r"\| `append_rework` \| (`[^`]+`) \|", mandatory_section
        )
        assert match, "expected the mandatory-preserve-per-operation table row"
        return re.findall(r"`([^`]+)`", match.group(1))


class TestWorkflowPatchDocExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(DOC_PATH.is_file(), f"{DOC_PATH} must exist (AC-1)")


class TestOperationModeMatrix(unittest.TestCase):
    """AC-1: both operations documented with their bound tasks_patch mode."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)

    def test_design_input_binds_the_two_expected_pairs(self):
        # Sanity check on the fixture itself, so a future edit to
        # design-input.md 5.5 that changes this matrix is visible here too.
        self.assertEqual(
            set(self.fixture.operation_mode_pairs()),
            {
                ("replace_planning", "replace_all"),
                ("append_rework", "append"),
            },
        )

    def test_both_operations_appear_bound_to_their_tasks_patch_mode(self):
        for operation, mode in self.fixture.operation_mode_pairs():
            row_pattern = re.compile(
                r"`%s`[^\n]*\|[^\n]*`%s`"
                % (re.escape(operation), re.escape(mode))
            )
            self.assertRegex(
                self.text,
                row_pattern,
                f"{operation} must be documented bound to tasks_patch mode "
                f"{mode} (same table row)",
            )


class TestTasksPatchContract(unittest.TestCase):
    """AC-2: tasks_patch, replace_all conditions, append provenance."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_append_provenance_and_expected_next_task_id_documented(self):
        for token in (
            "expected_next_task_id",
            "provenance",
            "source_ids",
            "review_round",
        ):
            self.assertIn(token, self.text)

    def test_replace_all_permission_conditions_section_present(self):
        section = _extract_section(
            self.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        lowered = section.lower()
        self.assertIn("empty", lowered)
        self.assertIn("pending", lowered)
        self.assertIn("create-plan", section)
        self.assertIn("needs_update", section)


class TestStepPatchesContract(unittest.TestCase):
    """AC-3: step_patches addressed by step_id, only status settable."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_addressed_by_step_id_not_array_index(self):
        self.assertIn("step_id", self.text)
        # Markdown line-wrapping may split the phrase across a line break;
        # match on whitespace (including a wrap newline), not a literal
        # single space.
        self.assertRegex(self.text.lower(), r"array[\s-]+index")

    def test_only_status_field_settable(self):
        self.assertIn("only field `set` may touch", self.text)

    def test_base_commit_and_completed_at_commit_not_worker_settable(self):
        self.assertIn("base_commit", self.text)
        self.assertIn("completed_at_commit", self.text)
        self.assertIn("NOT worker-settable", self.text)


class TestPreserveVocabulary(unittest.TestCase):
    """AC-4: complete preserve vocabulary + per-operation mandatory sets."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)

    def test_complete_preserve_vocabulary_present(self):
        vocab = self.fixture.preserve_vocabulary()
        self.assertEqual(
            len(vocab), 5, "sanity: design-input.md lists 5 preserve paths"
        )
        for path in vocab:
            self.assertIn(
                f"`{path}`", self.text, f"preserve path {path} missing"
            )

    def test_append_rework_mandatory_preserve_includes_base_commit(self):
        mandatory = self.fixture.append_rework_mandatory_preserve()
        self.assertIn("workflow.implement.base_commit", mandatory)
        self.assertIn("workflow.implement.base_commit", self.text)

    def test_no_preserve_path_outside_permitted_vocabulary(self):
        """Edge case (Test Notes): guard against an invented preserve path
        extension by scanning only the preserve section of the doc."""
        vocab = set(self.fixture.preserve_vocabulary())
        section = _extract_section(
            self.text, "## `preserve`", "## Application rules"
        )
        candidates = re.findall(r"`((?:[\w<>]+\.)+[\w<>]+)`", section)
        non_paths = {"workflow.yaml"}
        paths = [c for c in candidates if c not in non_paths]
        self.assertTrue(paths, "expected at least one preserve path token")
        for path in paths:
            self.assertIn(
                path,
                vocab,
                f"{path} is not in the permitted preserve vocabulary -- "
                "looks like an invented extension",
            )


class TestApplicationRules(unittest.TestCase):
    """AC-5: all sixteen application rules, ordered, single-write + R2."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)
        cls.doc_rules_section = _extract_section(
            cls.text, "## Application rules", "## Ownership boundary"
        )

    def test_rule_count_matches_design_input(self):
        design_rules = self.fixture.application_rules()
        self.assertEqual(
            len(design_rules),
            16,
            "sanity: design-input.md 5.5.5 states sixteen rules",
        )
        doc_rule_numbers = re.findall(
            r"^(\d+)\. ", self.doc_rules_section, re.MULTILINE
        )
        self.assertEqual(len(doc_rule_numbers), len(design_rules))

    def test_rules_are_ordered_one_through_sixteen(self):
        doc_rule_numbers = [
            int(n)
            for n in re.findall(r"^(\d+)\. ", self.doc_rules_section, re.MULTILINE)
        ]
        self.assertEqual(doc_rule_numbers, list(range(1, 17)))

    def test_single_write_application_rule_present(self):
        self.assertIn("single-write", self.text.lower())
        self.assertIn("Write", self.doc_rules_section)

    def test_rule_r2_commit_sequence_present(self):
        self.assertIn("R2", self.doc_rules_section)
        self.assertIn("commit", self.doc_rules_section.lower())


class TestOwnershipBoundaryAndDomainsSSOT(unittest.TestCase):
    """AC-6: project/review summary not worker-patchable; domains SSOT."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_project_and_review_summary_are_orchestrator_updated(self):
        self.assertIn("orchestrator-updated", self.text)
        self.assertIn("review summary", self.text.lower())
        self.assertIn("needs_rework", self.text)

    def test_domains_ssot_is_review_rules_yaml(self):
        self.assertIn("references/review-rules.yaml", self.text)


class TestReplaceAllPermissionConditionsPinned(unittest.TestCase):
    """task0003 AC-2: the `replace_all` permission conditions are pinned
    precisely, scoped to their own section (and, for rule 5, to the
    application-rule list) rather than to a substring match anywhere in the
    document. `workflow-patch.md` is frozen by this feature (IMPLEMENTATION.md
    D1); these assertions are the regression guard that makes a future
    relaxation of the section fail loudly instead of silently."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        cls.doc_rules_section = _extract_section(
            cls.text, "## Application rules", "## Ownership boundary"
        )

    def test_exactly_two_create_plan_entry_statuses_are_permitted(self):
        statuses = re.findall(
            r"the `create-plan` step is `([a-z_]+)`", self.section
        )
        self.assertEqual(
            set(statuses),
            {"pending", "needs_update"},
            "the permitted create-plan entry statuses must be exactly "
            "pending and needs_update",
        )
        self.assertEqual(
            len(statuses),
            2,
            "no third create-plan entry status may be listed as permitted",
        )

    def test_tasks_empty_or_all_pending_condition_still_required(self):
        # The security floor (5.5.1's first condition): must not silently
        # widen or disappear.
        self.assertIn("`tasks` is empty", self.section)
        self.assertRegex(
            self.section,
            r"every existing task's `status` is `pending`",
        )

    def test_application_rule_5_still_refers_to_the_permission_conditions(self):
        match = re.search(
            r"^5\. (.*?)(?=^\d+\. )",
            self.doc_rules_section,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(match, "expected application rule 5 to exist")
        rule_text = match.group(1)
        self.assertIn("replace_all", rule_text)
        self.assertIn("permission conditions", rule_text.lower())


if __name__ == "__main__":
    unittest.main()
