"""Tests for task0007 (goal-vs-spec-divergence): create-spec-phase.md writes
the `goal` block verbatim during workflow.yaml construction, never rewrites
it on re-entry, and resolves the reference-impact scan's targets before
dispatching the analyst.

Covers task0007 Acceptance Criteria (feature-docs/goal-vs-spec-divergence/
tasks/task0007.md):

- AC-1 (FR1): the workflow.yaml construction section lists the `goal` block
  among the fields the orchestrator builds and states that the launch-time
  task description is stored verbatim, citing
  `references/workflow-schema.md` for the block's definition.
- AC-2 (FR1): the document states that the orchestrator is the sole writer
  and that the value is never derived from REQUIREMENTS.md or SPEC.md.
- AC-3 (FR2): the document states that a create-spec re-entry with
  `status: needs_update` leaves an existing `goal` block unchanged.
- AC-4 (FR1, EC-7): the document states that no `goal` block is written when
  there is no launch-time task description, that no goal is synthesized in
  that case, and it cites `references/question-resolution.md` for the
  consequence at the gate.
- AC-5 (FR17): the analyst dispatch loop's pre-dispatch resolution step
  names the reference-scan target category and states that the orchestrator
  resolves it before dispatch, with the analyst performing no discovery of
  its own.
- AC-6 (NFR1): the section restates neither the schema rules nor the
  analyst contract's field definitions; both are cited by path.
- AC-7 (NFR8): the document's numbered section titles and their order are
  unchanged, and the full suite passes (verified by running the whole
  suite, not by this module alone).

Extended for task0014 (goal-vs-spec-divergence rework, review round 1
finding 7223862537d2283c):

- AC-5 (NFR1): the construction section states the write-time procedure
  (indentation + re-parse check) and the failure outcome, citing
  `references/workflow-schema.md` for the rule itself rather than
  restating it, and adds no second statement of the verbatim /
  immutability / untrusted rules.

Per the task's Test Notes: assertions here scan only
`em-workflow/references/phases/create-spec-phase.md` (C4) — the schema
document (task0001) and the analyst contract (task0008) are sibling tasks'
files and are not read by this module. Each assertion is scoped to the
section it belongs to, not the whole document, since several tokens
(`goal`, `resolve`) appear in unrelated places.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

CONSTRUCTION_START = "## 11. workflow.yaml construction"
CONSTRUCTION_END = "## 11a. Design-system determination"
DISPATCH_START = "## 5. Analyst dispatch loop"
DISPATCH_END = "## 6. Question normalization"

# The re-entry statement must be tied to `needs_update` specifically, not to
# any generic mention of "re-entry" (Test Notes edge case). This matcher
# requires `needs_update` to appear, followed (within a bounded window) by
# `goal` and then an "unchanged" phrasing.
NEEDS_UPDATE_GOAL_UNCHANGED_RE = re.compile(
    r"needs_update.{0,300}goal.{0,300}(unchanged|left exactly as it is)",
    re.IGNORECASE | re.DOTALL,
)

# The full, pinned heading list for create-spec-phase.md (AC-7 / C3 / C5):
# this task must extend existing sections only, never renumber or insert a
# new numbered section.
EXPECTED_HEADINGS = [
    "## 1. Purpose and ownership",
    "## 2. Inputs and preconditions",
    "## 3. Bootstrap and durable-state boundary",
    "## 4. Reconcile on entry",
    "## 5. Analyst dispatch loop",
    "## 6. Question normalization",
    "## 7. Interactive answer handling",
    "## 8. Batch answer handling",
    "## 9. Spec writer dispatch",
    "## 10. Artifact validation",
    "## 11. workflow.yaml construction",
    "## 11a. Design-system determination",
    "## 12. Command approval gate",
    "## 13. Completion",
    "## Termination conditions",
    "## Loop-stop conditions (progress fingerprint)",
    "## Scope verification",
    "## Gate option vocabulary",
]

HEADING_RE = re.compile(r"^## .+$", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class TestFileExists(unittest.TestCase):
    def test_create_spec_phase_doc_exists(self):
        self.assertTrue(
            CREATE_SPEC_PATH.is_file(), f"expected {CREATE_SPEC_PATH} to exist"
        )


class TestConstructionSectionSliceIsLocatedAndNonEmpty(unittest.TestCase):
    """Non-vacuity guard (Test Notes): confirm the section slice used by the
    tests below was actually located and is non-empty, so an accidental
    marker typo cannot make every other test in this module vacuously
    pass (or silently scan the whole document instead of the section)."""

    def test_construction_section_slice_non_empty(self):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)
        self.assertGreater(len(section), 0)
        self.assertIn("workflow.yaml construction", section)

    def test_dispatch_section_slice_non_empty(self):
        text = _read(CREATE_SPEC_PATH)
        section = _slice(text, DISPATCH_START, DISPATCH_END)
        self.assertGreater(len(section), 0)
        self.assertIn("Analyst dispatch loop", section)


class TestGoalFieldListedAndVerbatim(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_goal_listed_among_constructed_fields(self):
        self.assertIn("`goal`", self.section)

    def test_launch_time_description_stored_verbatim(self):
        lowered = self.section.lower()
        self.assertIn("launch-time task description", lowered)
        self.assertIn("verbatim", lowered)

    def test_cites_workflow_schema_for_the_blocks_definition(self):
        self.assertIn("references/workflow-schema.md", self.section)


class TestGoalNegativeProofNoVerbatimStatementInSyntheticSample(unittest.TestCase):
    """Negative proof (Test Notes): a synthetic sample lacking the verbatim
    statement must not satisfy the same substring checks used above, so
    those checks are shown to be non-trivial."""

    def test_synthetic_sample_without_verbatim_wording_fails_the_check(self):
        sample = (
            "The orchestrator builds workflow.yaml with fields feature, "
            "created, and requirements."
        ).lower()
        self.assertNotIn("verbatim", sample)
        self.assertNotIn("launch-time task description", sample)


class TestGoalSoleWriterAndNeverDerived(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_orchestrator_is_sole_writer(self):
        self.assertIn("sole writer", self.section.lower())

    def test_never_derived_from_requirements_or_spec(self):
        self.assertIn("REQUIREMENTS.md", self.section)
        self.assertIn("SPEC.md", self.section)
        self.assertIn("never derived", self.section.lower())

    def test_synthetic_sample_missing_the_statement_fails_the_check(self):
        sample = "the orchestrator writes workflow.yaml."
        self.assertNotIn("sole writer", sample.lower())
        self.assertNotIn("never derived", sample.lower())


class TestGoalReentryTiedToNeedsUpdate(unittest.TestCase):
    """AC-3, plus the Test Notes edge case: the re-entry assertion must be
    tied to the `needs_update` wording specifically, not to any mention of
    re-entry."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_regex_matches_a_positive_synthetic_sample(self):
        sample = (
            "when re-entered with `status: needs_update`, an existing "
            "`goal` block is left exactly as it is."
        )
        self.assertRegex(sample, NEEDS_UPDATE_GOAL_UNCHANGED_RE)

    def test_regex_rejects_generic_re_entry_wording_without_needs_update(self):
        # Edge case (Test Notes): a document that only ever says "on
        # re-entry ... goal ... unchanged" without tying it to
        # `needs_update` must NOT satisfy the matcher.
        sample = "on re-entry, an existing `goal` block is left unchanged."
        self.assertNotRegex(sample, NEEDS_UPDATE_GOAL_UNCHANGED_RE)

    def test_document_states_reentry_leaves_goal_unchanged_tied_to_needs_update(self):
        self.assertRegex(self.section, NEEDS_UPDATE_GOAL_UNCHANGED_RE)

    def test_needs_update_status_literal_present(self):
        self.assertIn("needs_update", self.section)


class TestGoalNoSourceCase(unittest.TestCase):
    """AC-4 (EC-7)."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_ec7_marker_present(self):
        self.assertIn("EC-7", self.section)

    def test_no_source_case_states_no_goal_block_written(self):
        lowered = self.section.lower()
        self.assertIn("no launch-time task description", lowered)
        self.assertIn("no `goal` block is written", lowered)

    def test_no_goal_synthesized_in_that_case(self):
        self.assertIn("no goal is synthesized", self.section.lower())

    def test_cites_question_resolution_for_the_gate_consequence(self):
        self.assertIn("references/question-resolution.md", self.section)

    def test_no_source_outcome_is_not_an_empty_scalar(self):
        # task0014 Test Notes edge case: an empty description resolves to
        # the already-defined no-block state, never to an empty scalar.
        self.assertIn("never as an empty scalar", self.section.lower())

    def test_synthetic_sample_missing_the_statement_fails_the_check(self):
        sample = "the orchestrator always writes a goal block."
        self.assertNotIn("no launch-time task description", sample.lower())
        self.assertNotIn("no goal is synthesized", sample.lower())
        self.assertNotIn("never as an empty scalar", sample.lower())


class TestWriteTimeProcedureAndFailureOutcome(unittest.TestCase):
    """task0014 AC-5: the construction section states the write-time
    procedure (indentation + re-parse check) and the failure outcome,
    citing `references/workflow-schema.md` for the rule itself rather than
    restating it, and adds no second statement of the verbatim /
    immutability / untrusted rules."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, CONSTRUCTION_START, CONSTRUCTION_END)

    def test_construction_section_located_and_nonempty(self):
        # Non-vacuity guard.
        self.assertGreater(len(self.section.strip()), 0)

    def test_states_indentation_and_reparse_are_performed_at_construction(self):
        lowered = self.section.lower()
        self.assertIn("indent", lowered)
        self.assertIn("re-parsing", lowered)

    def test_cites_workflow_schema_for_the_indentation_and_reparse_rule(self):
        # Cited at least twice in this section: once for the verbatim
        # field (AC-1), once for the write-time procedure (AC-5). The
        # write-time bullet itself must not restate the rule's own detail.
        self.assertIn("references/workflow-schema.md", self.section)
        self.assertNotIn("YAML block scalar", self.section)
        self.assertNotIn("blank line", self.section.lower())
        self.assertNotIn("document marker", self.section.lower())

    def test_states_failure_outcome_without_restating_it(self):
        lowered = self.section.lower()
        self.assertIn("failure is reported", lowered)
        self.assertIn("no-source outcome", lowered)
        self.assertNotIn("partially written or unverified", lowered)

    def test_does_not_add_a_second_verbatim_immutability_untrusted_statement(self):
        # These rules already have exactly one statement each in this
        # section (existing bullets); the new write-time/failure bullets
        # must not duplicate them.
        self.assertEqual(
            self.section.count("Untrusted-Input Handling"), 1
        )

    def test_synthetic_sample_missing_the_statement_fails_the_check(self):
        sample = "the orchestrator writes the goal field."
        lowered = sample.lower()
        self.assertNotIn("indent", lowered)
        self.assertNotIn("re-parsing", lowered)
        self.assertNotIn("no-source outcome", lowered)


class TestReferenceScanTargetResolution(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, DISPATCH_START, DISPATCH_END)

    def test_reference_scan_targets_category_named(self):
        self.assertIn("resolved_input_paths.reference_scan_targets", self.section)

    def test_orchestrator_resolves_before_dispatch(self):
        lowered = self.section.lower()
        self.assertIn("resolves", lowered)
        self.assertIn("before dispatch", lowered)

    def test_analyst_performs_no_discovery_of_its_own(self):
        self.assertIn(
            "no filesystem discovery of its own", self.section.lower()
        )

    def test_synthetic_sample_missing_the_statement_fails_the_check(self):
        sample = "the orchestrator resolves E2E discovery paths before dispatch."
        self.assertNotIn(
            "resolved_input_paths.reference_scan_targets", sample
        )
        self.assertNotIn("no filesystem discovery of its own", sample.lower())


class TestReferenceScanCachingParticipation(unittest.TestCase):
    """Design B.2: the reference-scan resolution participates in the same
    caching / re-resolution-trigger rules already stated for the other
    categories, and the pre-existing pinned phrases for that machinery must
    survive this task's edit unchanged (C5 guard preservation)."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.section = _slice(text, DISPATCH_START, DISPATCH_END)

    def test_resolved_input_cache_still_named(self):
        self.assertIn("resolved_input_cache", self.section)

    def test_three_re_resolution_triggers_still_named(self):
        self.assertIn(
            "re-resolution triggers fired since the last resolution",
            self.section,
        )

    def test_reference_scan_category_shares_the_same_caching_discipline(self):
        lowered = self.section.lower()
        self.assertIn("same caching", lowered)


class TestNoRestatedSiblingContent(unittest.TestCase):
    """AC-6: the section restates neither the schema rules (task0001, owned
    by references/workflow-schema.md) nor the analyst contract's field
    definitions (task0008, owned by references/contracts/analyst-contract.md)
    -- both are cited by path instead."""

    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.construction_section = _slice(
            text, CONSTRUCTION_START, CONSTRUCTION_END
        )
        cls.dispatch_section = _slice(text, DISPATCH_START, DISPATCH_END)

    def test_construction_section_cites_schema_path_rather_than_copying_it(self):
        self.assertIn("references/workflow-schema.md", self.construction_section)
        # Schema-internal syntax vocabulary (task0001's own wording for how
        # the value is represented) must not be copied in here.
        self.assertNotIn("YAML block scalar", self.construction_section)

    def test_dispatch_section_cites_analyst_contract_rather_than_copying_it(self):
        self.assertIn(
            "references/contracts/analyst-contract.md", self.dispatch_section
        )
        # The result field's own definition (task0008's wording for what
        # `reference_impact` entries contain) must not be copied in here.
        self.assertNotIn(
            "entries pair the symbol or string", self.dispatch_section
        )

    def test_request_side_flag_is_named_but_not_defined(self):
        # It is fine to name the flag (design B.3 requires it), but its type
        # / validation rules are the contract's job, not this document's.
        self.assertIn(
            "analysis_scope.inspect_reference_impact", self.dispatch_section
        )


class TestSectionHeadingsUnchangedAndInOrder(unittest.TestCase):
    """AC-7 / C3 / C5: the document's numbered section titles and their
    order are unchanged by this task's edits -- no renumbering, no new
    numbered section inserted."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_expected_headings_all_present_in_order(self):
        found = HEADING_RE.findall(self.text)
        self.assertEqual(found, EXPECTED_HEADINGS)


if __name__ == "__main__":
    unittest.main()
