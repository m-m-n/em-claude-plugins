"""Tests for task0007: em-workflow/references/contracts/{planner,
rework-planner,designer}-contract.md.

Covers task0007 Acceptance Criteria (feature-docs/agent-separation/
tasks/task0007.md):

- AC-1: all three contract files exist, each referencing the common
  envelope and the write-policy model by path rather than restating them.
- AC-2: planner-contract.md documents `planning_inputs`, the single-packet
  question rule, the `completed` output triple, and the prohibition on
  setting `branch`, `notes`, running statuses and `completed_at_commit`.
- AC-3: rework-planner-contract.md documents `rework_source` for both
  source types, the document update scope table, and the mandatory
  `rework_index` with all four validation checks.
- AC-4: rework-planner-contract.md documents the specification-change
  transition as a question rather than tasks, with the five-step
  orchestrator sequence.
- AC-5: designer-contract.md documents the complete `kind` ×
  token-existence table including both abort cases, and states that
  designer returns neither a packet nor a patch.
- AC-6: designer-contract.md documents the reclassification gate as
  executed in place, shared between design and create-plan, and states the
  `project_native` exclusion of the two token files from `digest_inputs`.
- AC-7: designer-contract.md states the token yaml/html linkage with its
  bidirectional verification rule.

These deliverables are specification documents (Test Notes), so the
acceptance criteria are verified by structural/textual assertions over the
Markdown rather than behavioral tests of running code. Per the Test Notes,
the `kind` table rows are derived by parsing design-input.md 5.4.5 rather
than hard-coded, so this test cannot silently drift from the design.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_INPUT_PATH = (
    REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"
)
CONTRACTS_DIR = REPO_ROOT / "em-workflow" / "references" / "contracts"
PLANNER_PATH = CONTRACTS_DIR / "planner-contract.md"
REWORK_PATH = CONTRACTS_DIR / "rework-planner-contract.md"
DESIGNER_PATH = CONTRACTS_DIR / "designer-contract.md"

ENVELOPE_REF = "references/contracts/worker-envelope.md"
WRITE_POLICY_REF = "references/contracts/spec-writer-contract.md"

KIND_ROW_RE = re.compile(
    r"^\|\s*`(project_native|em_workflow|none)`\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|\s*$",
    re.MULTILINE,
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _targets_token_set(col4_text):
    return frozenset(re.findall(r"`([^`]+)`", col4_text))


def _kind_rows(section_text, abort_marker):
    rows = KIND_ROW_RE.findall(section_text)
    assert rows, "expected to find kind x token-existence table rows"
    result = []
    for kind, _c2, _c3, c4, c5 in rows:
        result.append((kind, _targets_token_set(c4), abort_marker in c5))
    return result


class DesignInputKindTableFixture:
    """Derives the expected kind x token-existence rows from design-input.md
    5.4.5, so the assertions below cannot drift from the design."""

    def __init__(self):
        full = _read(DESIGN_INPUT_PATH)
        section = _extract_section(
            full,
            "**`project.design_system.kind` による分岐**",
            "`project_native` の場合、designer / planner の `digest_inputs`",
        )
        self.rows = _kind_rows(section, abort_marker="不整合")


class TestContractFilesExistAndReferenceSharedModels(unittest.TestCase):
    """AC-1."""

    def test_all_three_files_exist(self):
        for path in (PLANNER_PATH, REWORK_PATH, DESIGNER_PATH):
            self.assertTrue(path.is_file(), f"{path} must exist")

    def test_all_three_reference_the_common_envelope_by_path(self):
        for path in (PLANNER_PATH, REWORK_PATH, DESIGNER_PATH):
            self.assertIn(
                ENVELOPE_REF,
                _read(path),
                f"{path} must reference the common envelope by path",
            )

    def test_all_three_reference_the_write_policy_model_by_path(self):
        for path in (PLANNER_PATH, REWORK_PATH, DESIGNER_PATH):
            self.assertIn(
                WRITE_POLICY_REF,
                _read(path),
                f"{path} must reference the write-policy model by path",
            )


class TestPlannerContract(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)

    def test_planning_inputs_fields_documented(self):
        for field in (
            "requirements_path",
            "spec_path",
            "design_path",
            "lessons_path",
            "impl_skills_registry",
            "review_rules",
            "license_compat",
        ):
            self.assertIn(field, self.text, f"planning_inputs field {field} missing")

    def test_single_packet_question_bundling_rule_documented(self):
        section = _extract_section(
            self.text,
            "## Question packet bundling rule",
            "## digest_inputs",
        )
        lowered = section.lower()
        self.assertIn("single", lowered)
        self.assertIn("tbd", lowered)
        self.assertIn("license", lowered)
        self.assertIn("existing-file", lowered)
        # the split-iteration exception
        self.assertIn("license-candidate discovery depends", section)

    def test_completed_output_triple_documented(self):
        section = _extract_section(
            self.text, "## `completed` payload", "## Prohibited fields"
        )
        self.assertIn("written_artifacts", section)
        self.assertIn("workflow_patch", section)
        self.assertIn("task_index", section)
        self.assertIn("replace_planning", section)

    def test_prohibition_list_complete(self):
        section = _extract_section(
            self.text,
            "## Prohibited fields",
            "## Task decomposition, complexity and domains vocabulary",
        )
        self.assertIn("`branch`", section)
        self.assertIn("`notes`", section)
        self.assertIn("running/in-progress", section)
        self.assertIn("`completed_at_commit`", section)
        self.assertIn("MUST NOT set", section)

    def test_decomposition_criteria_named_by_reference_not_restated(self):
        self.assertIn("skills/plan-writing/SKILL.md", self.text)
        self.assertIn("references/review-rules.yaml", self.text)
        # guard against restating the actual criteria text (NFR6): the
        # concrete complexity-level bullet wording should not appear here
        self.assertNotIn("localized change in one or few files", self.text)


class TestReworkPlannerContract(unittest.TestCase):
    """AC-3, AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_PATH)

    def test_rework_source_documents_both_source_types(self):
        self.assertIn("type: review", self.text)
        self.assertIn("type: verify", self.text)
        self.assertIn("findings", self.text)
        self.assertIn("failed_items", self.text)
        for field in (
            "existing_tasks",
            "next_task_id",
            "verification_index",
            "implementation_path",
            "spec_path",
            "verification_path",
        ):
            self.assertIn(field, self.text)

    def test_document_update_scope_table_present(self):
        section = _extract_section(
            self.text,
            "## Document update scope table",
            "## `write_policy`",
        )
        self.assertIn("tasks/taskNNNN.md", section)
        self.assertIn("VERIFICATION.md", section)
        self.assertIn("IMPLEMENTATION.md", section)
        self.assertIn("SPEC.md", section)
        self.assertIn("REQUIREMENTS.md", section)
        self.assertIn("Always created", section)
        self.assertIn("specification-change transition", section.lower())

    def test_rework_index_mandatory_and_both_empty_prohibited(self):
        section = _extract_section(
            self.text,
            "## Verification coverage rule",
            "## `payload.shared_contract_rationale`",
        )
        self.assertIn("covered_by_existing", section)
        self.assertIn("new_scenarios", section)
        self.assertIn("both", section.lower())
        self.assertIn("prohibited", section.lower())

    def test_rework_index_four_validation_checks_present(self):
        section = _extract_section(
            self.text,
            "The validation script (5.11.1) performs these four checks:",
            "## `payload.shared_contract_rationale`",
        )
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(
            len(numbered), 4, "expected exactly four numbered validation checks"
        )
        self.assertEqual(numbered, ["1", "2", "3", "4"])
        # check 1: every rework task appears in rework_index
        self.assertIn("rework_index", section)
        # check 2: covered_by_existing IDs exist in verification_index
        self.assertIn("verification_index", section)
        # check 3: new_scenarios IDs exist in the VERIFICATION.md diff
        self.assertIn("diff", section)
        # check 4: new_scenarios also appear in requirements_patch.tests_append
        self.assertIn("requirements_patch", section)
        self.assertIn("tests_append", section)

    # task0024 AC-7 (bs10 half)
    def test_check_three_depends_on_a_supplied_baseline(self):
        section = _extract_section(
            self.text,
            "The validation script (5.11.1) performs these four checks:",
            "## `payload.shared_contract_rationale`",
        )
        lowered = section.lower()
        self.assertIn("baseline", lowered)
        self.assertIn("depends", lowered)
        # the dependency statement must not be a stray mention elsewhere --
        # anchor on it following the four-item checklist.
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3", "4"])
        baseline_idx = section.lower().index("baseline")
        check_four_idx = section.index("4. ")
        self.assertGreater(
            baseline_idx,
            check_four_idx,
            "the baseline dependency statement must follow the four numbered checks",
        )

    def test_spec_change_returns_question_not_tasks(self):
        section = _extract_section(
            self.text,
            "## Specification-change transition",
            "## Other conditions",
        )
        self.assertIn("no tasks", section.lower())
        self.assertIn("gate_id: rework.spec-change", section)
        self.assertIn("needs_user_input", section)

    def test_five_step_orchestrator_sequence_present(self):
        section = _extract_section(
            self.text,
            "## Specification-change transition",
            "## Other conditions",
        )
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3", "4", "5"])
        self.assertIn("needs_update", section)
        self.assertIn("pending", section)
        self.assertIn("base_commit", section)
        self.assertIn("rework.yaml", section)
        self.assertIn("origin_id", section)
        self.assertIn("create-spec", section)

    def test_other_question_conditions_documented(self):
        section = _extract_section(
            self.text,
            "## Other conditions under which a question packet may be returned",
            "## Scope & concurrency assumption",
        )
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(len(numbered), 3)
        lowered = section.lower()
        self.assertIn("mutually exclusive", lowered)
        self.assertIn("license", lowered)
        self.assertIn("acceptance criteria", lowered)


class TestDesignerContractAutonomy(unittest.TestCase):
    """AC-5 (autonomy statement), edge case (no question-packet path)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DESIGNER_PATH)

    def test_states_neither_question_packet_nor_workflow_patch(self):
        self.assertIn("neither", self.text)
        self.assertIn("`question_packet`", self.text)
        self.assertIn("`workflow_patch`", self.text)

    def test_no_question_packet_path_described(self):
        """Edge case (Test Notes): a stray needs_user_input status would
        contradict the autonomy rule -- the only status that requires a
        question_packet per the common envelope."""
        self.assertNotIn("needs_user_input", self.text)


class TestDesignerKindTable(unittest.TestCase):
    """AC-5: complete kind x token-existence table with both abort cases."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputKindTableFixture()
        cls.text = _read(DESIGNER_PATH)
        cls.section = _extract_section(
            cls.text,
            "## `project.design_system.kind` × token-existence table",
            "## Reclassification gate",
        )
        cls.doc_rows = _kind_rows(cls.section, abort_marker="ABORT")

    def test_design_input_has_seven_rows_two_abort(self):
        # sanity check on the fixture itself
        self.assertEqual(len(self.fixture.rows), 7)
        self.assertEqual(sum(1 for r in self.fixture.rows if r[2]), 2)

    def test_designer_contract_has_matching_row_for_every_combination(self):
        design_keys = {(kind, tokens) for kind, tokens, _abort in self.fixture.rows}
        doc_keys = {(kind, tokens) for kind, tokens, _abort in self.doc_rows}
        self.assertEqual(
            design_keys,
            doc_keys,
            "designer-contract.md's kind table must have a row for every "
            "kind x token-existence combination in design-input.md 5.4.5",
        )

    def test_abort_rows_match_between_design_input_and_contract(self):
        design_abort_keys = {
            (kind, tokens) for kind, tokens, abort in self.fixture.rows if abort
        }
        doc_abort_keys = {
            (kind, tokens) for kind, tokens, abort in self.doc_rows if abort
        }
        self.assertEqual(len(design_abort_keys), 2)
        self.assertEqual(design_abort_keys, doc_abort_keys)


class TestDesignerReclassificationGate(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DESIGNER_PATH)

    def test_gate_id_present(self):
        self.assertIn("design-system.reclassify", self.text)

    def test_gate_executed_in_place_not_returning_to_create_spec(self):
        section = _extract_section(
            self.text,
            "## Reclassification gate",
            "## `digest_inputs`",
        )
        self.assertRegex(section, r"does \*\*not\*\*\s+return to create-spec")
        self.assertIn("standalone gate", section)
        self.assertIn("executed in place", section)

    def test_gate_shared_between_design_and_create_plan(self):
        section = _extract_section(
            self.text,
            "## Reclassification gate",
            "## `digest_inputs`",
        )
        self.assertIn(
            "shared by both the design and create-plan entry points", section
        )

    def test_cross_product_check_not_design_step_specific(self):
        section = _extract_section(
            self.text,
            "**This cross-product check is not design-step-specific.**",
            "## Reclassification gate",
        )
        self.assertIn("create-plan", section)
        self.assertIn("design", section)

    def test_project_native_excludes_two_token_files_from_digest_inputs(self):
        section = _extract_section(
            self.text, "## `digest_inputs`", "## `completed` payload"
        )
        self.assertIn("project_native", section)
        self.assertIn("excluded from `digest_inputs`", section)
        self.assertIn("design-system/tokens.yaml", section)
        self.assertIn("design-system/tokens.html", section)

    def test_project_native_files_arrive_only_via_resolved_input_paths(self):
        # task0019 AC-6: the digest_inputs section itself must say that
        # project-native design system files arrive only through
        # resolved_input_paths (not merely elsewhere in the document).
        section = _extract_section(
            self.text, "## `digest_inputs`", "## `completed` payload"
        )
        self.assertIn("resolved_input_paths", section)
        self.assertIn("project_design_system", section)


class TestDesignerTokenLinkage(unittest.TestCase):
    """AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DESIGNER_PATH)
        cls.section = _extract_section(
            cls.text,
            "## Token yaml/html linkage",
            "## `project.design_system.kind`",
        )

    def test_regenerate_source_relationship_documented(self):
        self.assertIn("regenerate", self.section)
        self.assertIn("source: design-system/tokens.yaml", self.section)

    def test_bidirectional_verification_documented(self):
        self.assertIn("tokens.yaml", self.section)
        self.assertIn("must also include", self.section)
        self.assertIn("tokens.html", self.section)
        self.assertIn("violation", self.section)

    def test_replace_authorized_never_applies(self):
        self.assertIn("`replace_authorized`", self.section)
        self.assertIn("never applies", self.section)


if __name__ == "__main__":
    unittest.main()
