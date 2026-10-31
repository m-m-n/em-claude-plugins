"""Tests for task0002: the rework-planner documents describe the docs-only
correction route from the worker's side (feature rework-docs-only-task-routing).

Covers task0002 Acceptance Criteria
(feature-docs/rework-docs-only-task-routing/tasks/task0002.md):

- AC-1: both documents' document update scope tables carry a row for the
  existing `tasks/*.md` limited to the docs-only correction route, and
  docs-only conditions for `VERIFICATION.md` and `IMPLEMENTATION.md`; the
  contract's table still carries `Always created` and the
  specification-change transition row.
- AC-2: `agents/rework-planner.md` keeps "you never rewrite the feature's
  existing plan", names the docs-only correction route as the only exception
  (cited by heading and file), and describes the route-order check, the
  direct correction without a task, the requirement test references changed
  through the tests replacement, the `doc_corrections` declaration and the
  mixed-round split within the same dispatch.
- AC-3: `agents/rework-planner.md` states a synthesized task's `files` never
  include a path whose first path segment is `feature-docs`, citing
  `references/rework-task-synthesis.md` Section 7.
- AC-4 (TM-6): the contract's `write_policy` section lists each existing
  `tasks/*.md` a round rewrites as a `replace_own` target (none otherwise),
  states how this use of `replace_own` aligns with the spec-writer contract,
  and states SPEC.md / REQUIREMENTS.md never become targets.
- AC-5 (TM-4): the contract has a `payload.doc_corrections` section after
  the `payload.shared_contract_rationale` section defining `origin_kind`,
  `origin_id`, `documents` and `scenario_renames` and the obligation to
  declare every docs-only correction; coverage check 2 accepts a renamed ID
  only through a declared `scenario_renames` pair, the checklist keeps
  exactly four numbered items and "baseline" first appears after item 4.
- AC-6: `agents/rework-planner.md` describes the docs-only patch shape and
  keeps the description for rounds with tasks.
- AC-7: this module pins AC-1 to AC-6, asserts the implementer's
  `feature-docs/**` constraint is unchanged (TS-12), asserts the contract's
  `## Gate identifiers` section keeps exactly its base backticked gate
  tokens and that `Phase R5` / `reviews/round` stay absent, and uses only
  standard-library modules.

Every pin is accompanied by a non-vacuity negative sample (a text lacking
the pinned statement) so a vacuous helper cannot pass unnoticed.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "rework-planner.md"
CONTRACT_PATH = (
    REPO_ROOT
    / "em-workflow"
    / "references"
    / "contracts"
    / "rework-planner-contract.md"
)
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"

SYNTHESIS_REF = "references/rework-task-synthesis.md"
ROUTE_HEADING = "### Docs-only correction route"
ROUTE_NAME = "docs-only correction route"

# Gate-shaped token grammar the validator applies to the "## Gate
# identifiers" section (em-workflow/scripts/validate-worker-output.py).
GATE_ID_SHAPE_RE = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$")
BASE_GATE_TOKENS = {"rework.spec-change"}

FOUR_CHECKS_START = "The validation script (5.11.1) performs these four checks:"
RATIONALE_HEADING = "## `payload.shared_contract_rationale`"
DOC_CORRECTIONS_HEADING = "## `payload.doc_corrections`"
SPEC_CHANGE_HEADING = "## Specification-change transition"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read(path):
    return Path(path).read_text(encoding="utf-8")


def norm(text):
    """Whitespace-normalized text, so prose assertions survive line wraps."""
    return re.sub(r"\s+", " ", text).strip()


def paragraphs(text):
    """Blank-line separated blocks with wrapped lines joined by one space."""
    blocks = re.split(r"\n\s*\n", text)
    return [norm(block) for block in blocks if block.strip()]


def paragraphs_with(text, *needles):
    return [p for p in paragraphs(text) if all(n in p for n in needles)]


def _heading_level(line):
    match = re.match(r"^(#+)\s", line)
    return len(match.group(1)) if match else None


def heading_line_index(text, heading):
    """Index of the first line equal to `heading` outside fenced code, or
    None when absent."""
    in_fence = False
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.strip() == heading:
            return index
    return None


def section(text, heading):
    """Text from `heading` (an exact heading line) up to the next heading of
    the same or a shallower level; headings inside fenced code are ignored.
    Raises AssertionError when the heading is absent."""
    lines = text.splitlines()
    start = heading_line_index(text, heading)
    if start is None:
        raise AssertionError(f"heading not found: {heading!r}")
    level = _heading_level(heading)
    end = len(lines)
    in_fence = False
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found = _heading_level(line)
        if found is not None and found <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def between(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def table_rows(section_text):
    """Rows of every pipe table in `section_text` as lists of stripped
    cells."""
    rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


def row_for(section_text, first_cell):
    """The table row whose first cell is `first_cell` (optionally followed
    by a parenthesised qualifier), or None."""
    for cells in table_rows(section_text):
        if cells and (cells[0] == first_cell or cells[0].startswith(first_cell + " (")):
            return cells
    return None


def row_condition(section_text, first_cell):
    """The normalized second-column text of the row, or '' when absent."""
    cells = row_for(section_text, first_cell)
    if cells is None or len(cells) < 2:
        return ""
    return norm(" ".join(cells[1:]))


def numbered_items(region):
    return re.findall(r"^(\d+)\. ", region, re.MULTILINE)


def item_text(region, number):
    """Text of list item `number.` up to the next numbered item (or the end
    of the region)."""
    match = re.search(
        rf"^{number}\. (.*?)(?=^\d+\. |\Z)", region, re.MULTILINE | re.DOTALL
    )
    return norm(match.group(1)) if match else ""


def baseline_follows_item_four(region):
    lowered = region.lower()
    if "baseline" not in lowered:
        return False
    item_four = region.find("\n4. ")
    if item_four == -1:
        return False
    return lowered.index("baseline") > item_four


def agent_opening(text):
    """The agent body between the title heading and the first `##` heading."""
    body = text.split("# rework-planner Agent (em-workflow)", 1)[1]
    return body.split("\n## ", 1)[0]


FORBIDDEN_CONTRACT_STRINGS = ("Phase R5", "reviews/round")


def forbidden_strings_in(text):
    return [needle for needle in FORBIDDEN_CONTRACT_STRINGS if needle in text]


def gate_tokens(gate_section):
    return {
        token
        for token in re.findall(r"`([^`]+)`", gate_section)
        if GATE_ID_SHAPE_RE.match(token)
    }


# Samples used for non-vacuity checks -----------------------------------------

OLD_SCOPE_TABLE = """\
| Document | Update condition |
|---|---|
| `tasks/taskNNNN.md` | Always created (new task plans only) |
| `VERIFICATION.md` | Per the verification coverage rules below |
| `IMPLEMENTATION.md` | Only when a rework task introduces a new shared contract |
| `SPEC.md` / `REQUIREMENTS.md` | Never updated by rework-planner |
"""

OLD_FOUR_CHECKS = """\
The validation script (5.11.1) performs these four checks:

1. Every rework task appears in `rework_index`.
2. Every ID in `covered_by_existing` already exists in `verification_index`.
3. Every ID in `new_scenarios` actually exists in the `VERIFICATION.md` diff.
4. If `new_scenarios` is non-empty, the same IDs also appear in the patch.

Check 3 depends on a supplied baseline.
"""


# ---------------------------------------------------------------------------
# AC-1: document update scope tables
# ---------------------------------------------------------------------------


class ScopeTableTests(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.agent_table = section(read(AGENT_PATH), "## Document update scope")
        cls.contract_table = section(
            read(CONTRACT_PATH), "## Document update scope table"
        )

    def _assert_docs_only_rows(self, table):
        existing = row_condition(table, "`tasks/*.md`")
        self.assertTrue(existing, "no row for the existing `tasks/*.md`")
        self.assertIn(f"only through the {ROUTE_NAME}", existing.lower())
        for document in ("`VERIFICATION.md`", "`IMPLEMENTATION.md`"):
            condition = row_condition(table, document)
            self.assertIn(
                ROUTE_NAME,
                condition.lower(),
                f"{document} row lacks the docs-only condition",
            )

    def test_agent_table_has_existing_task_row_and_docs_only_conditions(self):
        self._assert_docs_only_rows(self.agent_table)

    def test_contract_table_has_existing_task_row_and_docs_only_conditions(self):
        self._assert_docs_only_rows(self.contract_table)

    def test_contract_table_keeps_always_created_and_spec_change_row(self):
        self.assertIn("Always created", self.contract_table)
        spec_row = row_condition(self.contract_table, "`SPEC.md` / `REQUIREMENTS.md`")
        self.assertIn("specification-change transition", spec_row.lower())

    def test_agent_table_keeps_existing_rows(self):
        self.assertIn("one new file per synthesized task", self.agent_table)
        spec_row = row_condition(self.agent_table, "`SPEC.md` / `REQUIREMENTS.md`")
        self.assertIn("Never", spec_row)

    def test_negative_sample_table_without_the_row_is_detected(self):
        self.assertEqual(row_condition(OLD_SCOPE_TABLE, "`tasks/*.md`"), "")
        self.assertNotIn(
            ROUTE_NAME, row_condition(OLD_SCOPE_TABLE, "`VERIFICATION.md`").lower()
        )
        self.assertNotIn(
            ROUTE_NAME, row_condition(OLD_SCOPE_TABLE, "`IMPLEMENTATION.md`").lower()
        )


# ---------------------------------------------------------------------------
# AC-2, AC-3, AC-6: agent document
# ---------------------------------------------------------------------------


class AgentRouteTests(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(AGENT_PATH)
        cls.opening = agent_opening(cls.text)
        cls.process = section(cls.text, "## Route check and docs-only corrections")

    def test_existing_never_rewrite_sentence_is_kept(self):
        self.assertIn("you never rewrite the feature's existing plan", norm(self.text))

    def test_opening_names_the_route_as_the_only_exception_with_citation(self):
        found = paragraphs_with(
            self.opening,
            f"{ROUTE_NAME} is the only exception",
            ROUTE_HEADING,
            SYNTHESIS_REF,
        )
        self.assertTrue(found, "opening lacks the cited only-exception sentence")

    def test_process_checks_the_route_decision_order_first(self):
        found = paragraphs_with(
            self.process,
            "Before you synthesize any task",
            "route decision order",
            SYNTHESIS_REF,
        )
        self.assertTrue(found)

    def test_process_corrects_directly_with_no_task_and_declares(self):
        found = paragraphs_with(
            self.process,
            "create no task",
            "`VERIFICATION.md`",
            "`IMPLEMENTATION.md`",
            "`tasks/*.md`",
            "`payload.doc_corrections`",
        )
        self.assertTrue(found, "no paragraph states the direct correction")

    def test_process_changes_test_references_through_the_tests_replacement(self):
        found = paragraphs_with(
            self.process,
            "`tests_replace`",
            "`references/workflow-patch.md`",
            "requirement",
        )
        self.assertTrue(found)

    def test_process_splits_a_mixed_round_within_the_same_dispatch(self):
        found = paragraphs_with(
            self.process, "mixed round", "same dispatch", "docs-only", "synthesized"
        )
        self.assertTrue(found)

    def test_negative_sample_without_the_route_is_detected(self):
        sample = "You plan ONLY additional tasks -- you never rewrite the plan.\n"
        self.assertEqual(
            paragraphs_with(sample, f"{ROUTE_NAME} is the only exception"), []
        )
        self.assertEqual(paragraphs_with(sample, "mixed round", "same dispatch"), [])


class AgentFilesRuleTests(unittest.TestCase):
    """AC-3."""

    NEEDLES = (
        "`files`",
        "never include",
        "first path segment",
        "`feature-docs`",
        SYNTHESIS_REF,
        "Section 7",
    )

    def test_agent_states_the_feature_docs_files_rule_with_owner_citation(self):
        found = paragraphs_with(read(AGENT_PATH), *self.NEEDLES)
        self.assertTrue(found)

    def test_negative_sample_without_the_rule_is_detected(self):
        sample = "Every task's `files` is derived from meaning (Section 7).\n"
        self.assertEqual(paragraphs_with(sample, *self.NEEDLES), [])


class AgentPatchShapeTests(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.patch = section(read(AGENT_PATH), "## Workflow patch, never a direct write")

    def test_round_with_tasks_description_remains(self):
        flat = norm(self.patch)
        self.assertIn("You never write `workflow.yaml`", flat)
        self.assertIn("`operation: append_rework`", flat)
        self.assertIn("`tasks_patch.mode: append`", flat)
        self.assertIn("`step_patches` returning `implement`", flat)
        self.assertIn("`workflow.implement.base_commit` listed in `preserve`", flat)

    def test_docs_only_patch_shape_is_described(self):
        found = paragraphs_with(
            self.patch,
            "docs-only round",
            "`tasks_patch.mode: append`",
            "`expected_next_task_id`",
            "empty `tasks_patch.entries`",
            "origin step",
            "`verify`",
            "`review`",
            "`pending`",
            "no `step_patches` entry targets `implement`",
            "`workflow.implement.base_commit`",
            "`payload.rework_index`",
            "empty mapping",
        )
        self.assertTrue(found, "no paragraph carries the whole docs-only shape")

    def test_negative_sample_without_docs_only_shape_is_detected(self):
        sample = (
            "Your result carries a `workflow_patch` with `operation: "
            "append_rework` returning `implement` to `pending`.\n"
        )
        self.assertEqual(
            paragraphs_with(sample, "docs-only round", "empty mapping"), []
        )


class AgentOutputTests(unittest.TestCase):
    """AC-2 (the `doc_corrections` declaration in the output section)."""

    def test_output_names_doc_corrections_and_points_to_the_contract(self):
        output = section(read(AGENT_PATH), "## Output")
        found = paragraphs_with(
            output,
            "`payload.doc_corrections`",
            "`references/contracts/rework-planner-contract.md`",
        )
        self.assertTrue(found)

    def test_negative_sample_output_without_it_is_detected(self):
        sample = "`payload.rework_index` and `payload.shared_contract_rationale`.\n"
        self.assertEqual(paragraphs_with(sample, "`payload.doc_corrections`"), [])


# ---------------------------------------------------------------------------
# AC-4: write_policy (TM-6)
# ---------------------------------------------------------------------------


class WritePolicyTests(unittest.TestCase):
    """AC-4 (TM-6)."""

    @classmethod
    def setUpClass(cls):
        cls.section = section(read(CONTRACT_PATH), "## `write_policy`")

    def test_each_rewritten_existing_task_plan_is_a_replace_own_target(self):
        found = paragraphs_with(
            self.section,
            "`tasks/*.md`",
            "`write_policy.targets`",
            "`action: replace_own`",
            "none is listed",
        )
        self.assertTrue(found)

    def test_alignment_with_the_spec_writer_replace_own_definition(self):
        found = paragraphs_with(
            self.section,
            "`references/contracts/spec-writer-contract.md`",
            "`replace_own`",
            "same-phase output the worker itself produced",
            "planning",
            "implementation-planner",
            "rework-planner",
            "`references/artifact-digest.md`",
            "orchestrator",
        )
        self.assertTrue(found, "no paragraph states the replace_own alignment")

    def test_spec_and_requirements_never_become_targets(self):
        found = paragraphs_with(
            self.section,
            "`SPEC.md`",
            "`REQUIREMENTS.md`",
            "never become",
            "targets",
        )
        self.assertTrue(found)

    def test_negative_sample_without_the_listing_is_detected(self):
        sample = (
            "`VERIFICATION.md` and `IMPLEMENTATION.md` are listed in "
            "`write_policy.targets` with `action: replace_own`.\n"
        )
        self.assertEqual(paragraphs_with(sample, "`tasks/*.md`", "none is listed"), [])
        self.assertEqual(paragraphs_with(sample, "never become"), [])


# ---------------------------------------------------------------------------
# AC-5: payload.doc_corrections and coverage check 2 (TM-4)
# ---------------------------------------------------------------------------


class DocCorrectionsSectionTests(unittest.TestCase):
    """AC-5 (TM-4): the new payload section."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(CONTRACT_PATH)
        cls.section = section(cls.text, DOC_CORRECTIONS_HEADING)

    def test_section_sits_between_rationale_and_spec_change_sections(self):
        rationale = heading_line_index(self.text, RATIONALE_HEADING)
        new = heading_line_index(self.text, DOC_CORRECTIONS_HEADING)
        spec_change = heading_line_index(self.text, SPEC_CHANGE_HEADING)
        self.assertIsNotNone(rationale)
        self.assertIsNotNone(new, "payload.doc_corrections section is missing")
        self.assertIsNotNone(spec_change)
        self.assertLess(rationale, new)
        self.assertLess(new, spec_change)

    def test_section_defines_the_four_fields(self):
        for field in ("origin_kind", "origin_id", "documents", "scenario_renames"):
            self.assertIn(f"`{field}`", self.section, f"{field} is not defined")

    def test_origin_pair_is_the_invariant_six_pair_cited(self):
        found = paragraphs_with(
            self.section, "Invariant 6", SYNTHESIS_REF, "`origin_kind`", "`origin_id`"
        )
        self.assertTrue(found)

    def test_obligation_to_declare_every_docs_only_correction(self):
        found = paragraphs_with(
            self.section, "every", "docs-only correction", "non-empty"
        )
        self.assertTrue(found)

    def test_declaration_is_the_traceability_record(self):
        self.assertIn("traceability record", norm(self.section))

    def test_section_holds_no_numbered_list(self):
        self.assertEqual(numbered_items(self.section), [])

    def test_negative_sample_missing_section_is_detected(self):
        sample = f"{RATIONALE_HEADING}\n\ntext\n\n{SPEC_CHANGE_HEADING}\n"
        self.assertIsNone(heading_line_index(sample, DOC_CORRECTIONS_HEADING))
        with self.assertRaises(AssertionError):
            section(sample, DOC_CORRECTIONS_HEADING)


class CoverageCheckTwoTests(unittest.TestCase):
    """AC-5: coverage check 2 is rename-aware and the checklist keeps its
    shape."""

    @classmethod
    def setUpClass(cls):
        cls.region = between(read(CONTRACT_PATH), FOUR_CHECKS_START, RATIONALE_HEADING)

    def test_checklist_has_exactly_four_numbered_items(self):
        self.assertEqual(numbered_items(self.region), ["1", "2", "3", "4"])

    def test_check_two_accepts_a_renamed_id_only_through_a_declared_pair(self):
        item = item_text(self.region, 2)
        self.assertIn("`covered_by_existing`", item)
        self.assertIn("`verification_index`", item)
        self.assertIn("only through a declared `scenario_renames` pair", item)
        self.assertIn("`from`", item)
        self.assertIn("`to`", item)

    def test_baseline_first_appears_after_item_four(self):
        self.assertTrue(baseline_follows_item_four(self.region))

    def test_negative_sample_old_check_two_lacks_the_rename_rule(self):
        self.assertNotIn("scenario_renames", item_text(OLD_FOUR_CHECKS, 2))

    def test_negative_sample_fifth_numbered_item_fails_the_count_pin(self):
        sample = OLD_FOUR_CHECKS.replace(
            "\nCheck 3 depends", "5. A fifth item.\n\nCheck 3 depends"
        )
        self.assertNotEqual(numbered_items(sample), ["1", "2", "3", "4"])
        self.assertEqual(numbered_items(sample), ["1", "2", "3", "4", "5"])

    def test_negative_sample_baseline_before_item_four_is_detected(self):
        sample = OLD_FOUR_CHECKS.replace(
            "2. Every ID", "2. A baseline mention. Every ID"
        )
        self.assertFalse(baseline_follows_item_four(sample))
        self.assertTrue(baseline_follows_item_four(OLD_FOUR_CHECKS))


# ---------------------------------------------------------------------------
# AC-7: unchanged constraints (TS-12, gate identifiers, absent strings)
# ---------------------------------------------------------------------------


class UnchangedConstraintTests(unittest.TestCase):
    """AC-7."""

    def test_implementer_feature_docs_constraint_is_unchanged(self):
        self.assertIn("Never modify `feature-docs/**`", read(IMPLEMENTER_PATH))

    def test_gate_identifiers_section_keeps_exactly_its_base_tokens(self):
        gate_section = section(read(CONTRACT_PATH), "## Gate identifiers")
        self.assertEqual(gate_tokens(gate_section), BASE_GATE_TOKENS)

    def test_negative_sample_added_gate_token_is_detected(self):
        sample = "`rework.spec-change` and `rework.docs-only` are raised.\n"
        self.assertNotEqual(gate_tokens(sample), BASE_GATE_TOKENS)
        self.assertEqual(
            gate_tokens(sample), {"rework.spec-change", "rework.docs-only"}
        )

    def test_contract_carries_neither_phase_r5_nor_reviews_round(self):
        self.assertEqual(forbidden_strings_in(read(CONTRACT_PATH)), [])

    def test_negative_sample_forbidden_strings_are_detectable(self):
        sample = "see Phase R5 and reviews/round1.yaml"
        self.assertEqual(
            forbidden_strings_in(sample), ["Phase R5", "reviews/round"]
        )
        self.assertEqual(forbidden_strings_in("neither string appears"), [])


if __name__ == "__main__":
    unittest.main()
