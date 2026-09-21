"""Tests for task0002: the `tier` field and `tier_decision` decision block
in the schema SSOT, `em-workflow/references/workflow-schema.md`, and the
widened `skipped` status semantics.

Covers task0002 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0002.md):

- AC-1 (TS-12): the schema document defines the `tier` field with its
  three-value domain (`full` / `reduced` / `minimal`), and the
  `tier_decision` block with exactly its four named sub-fields (`by`,
  `confidence`, `at`, `reductions`) -- no more and no fewer.
- AC-2: the schema's worked "Full structure" example carries both `tier`
  and `tier_decision`, positioned alongside the other top-level blocks
  (between `parent_branch` and `project`).
- AC-3: the "## Status semantics" section no longer restricts `skipped` to
  the `design` step, states `skipped_reason` is mandatory whenever `status`
  is `skipped`, and states a `skipped` step is passed over by step
  selection.
- AC-4: the completion rule in the same section is restated so a workflow
  with a skipped non-design step can be complete, with `design`'s own case
  still described rather than removed.
- AC-5: the document states `tier` may be raised and never lowered, that
  re-transcription from persisted state must not lower it, and cites the
  raise mechanism's owner (the develop skill) rather than describing the
  mechanism.
- AC-6: the `tier_decision` description contains no threshold value and no
  confidence-only criterion, and cites `references/tier-rules.yaml` as the
  thresholds' owner.
- AC-7: this module asserts AC-1 through AC-6 against the raw document
  text, is discovered by `python3 -m unittest discover -s tests`, imports
  only standard-library modules, and pairs each matcher with a negative
  proof and a non-vacuity guard.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-schema.md"

TIER_SECTION_HEADING = "## `tier` and `tier_decision`"
STATUS_SEMANTICS_HEADING = "## Status semantics"
WRITE_OWNERSHIP_HEADING = "## Write ownership"

# tier_decision's closed four-sub-field vocabulary (SPEC.md FR2): the
# deciding agent, the confidence record, the decision timestamp, the list
# of subtractions applied.
DECISION_SUBFIELDS = ["by", "confidence", "at", "reductions"]

TIER_DOMAIN = ["full", "reduced", "minimal"]

OLD_RESTRICTED_SENTENCE = (
    "`skipped` is valid ONLY for the `design` step (with `skipped_reason` "
    "set)."
)
OLD_COMPLETION_SENTENCE = (
    "The workflow is complete when every step is `completed`, except that "
    "`design` may be `skipped`."
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-collapsed rendering so phrase assertions are insensitive
    to Markdown line-wrapping (matches the convention already used by
    tests/test_goal_block_schema.py and tests/test_failed_kind_schema.py)."""
    return re.sub(r"\s+", " ", text)


def _heading_index(text, heading, start=0):
    # Headings are always alone on their own line; several in-yaml
    # comments elsewhere in this document quote a heading's literal text
    # verbatim to point readers at it (e.g. `# below)`), so a plain
    # text.index() could match such a quoted mention instead of the real
    # heading. Anchor the search to a line start.
    match = re.search(r"(?m)^" + re.escape(heading), text[start:])
    if match is None:
        raise ValueError(f"heading not found as its own line: {heading!r}")
    return start + match.start()


def _heading_section(text, start_heading, end_heading=None):
    """Content from `start_heading`'s own line up to `end_heading`'s own
    line, or to end-of-text when `end_heading` is None (the new
    `tier`/`tier_decision` section is the last section in the document)."""
    start = _heading_index(text, start_heading)
    if end_heading is None:
        return text[start:]
    end = _heading_index(text, end_heading, start)
    return text[start:end]


def _full_structure_block(text):
    # The "## Full structure" heading is followed by a fenced ```yaml
    # block; several in-comment lines inside that fence quote later
    # heading text verbatim, so slicing up to the next literal heading text
    # would stop early. Slice to the fence's own closing ``` instead
    # (mirrors tests/test_failed_kind_schema.py's `_full_structure_block`).
    fence_start = text.index("```yaml", text.index("## Full structure"))
    fence_end = text.index("```", fence_start + len("```yaml"))
    return text[fence_start:fence_end]


class SchemaDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)

    def _tier_section(self):
        return _heading_section(self.text, TIER_SECTION_HEADING)

    def _status_semantics_section(self):
        return _heading_section(self.text, STATUS_SEMANTICS_HEADING, TIER_SECTION_HEADING)


# --- AC-7 (part 1): doc exists, sections are locatable and citable --------


class TestDocAndSectionsExist(SchemaDocTestCase):
    def test_doc_exists(self):
        self.assertTrue(SCHEMA_PATH.is_file())

    def test_tier_section_heading_present_verbatim(self):
        self.assertIn(TIER_SECTION_HEADING, self.text)

    def test_tier_section_is_locatable_and_nonempty(self):
        section = self._tier_section()
        self.assertGreater(len(section.strip()), 100)

    def test_status_semantics_section_is_locatable_and_nonempty(self):
        section = self._status_semantics_section()
        self.assertGreater(len(section.strip()), 100)


# --- AC-2: Full structure example carries both, alongside other top-level -
# blocks ---------------------------------------------------------------


class TestFullStructureCarriesTierAndDecisionBlock(SchemaDocTestCase):
    def test_tier_key_present_as_a_top_level_sibling(self):
        block = _full_structure_block(self.text)
        self.assertRegex(block, r"(?m)^tier:")

    def test_tier_decision_key_present_as_a_top_level_sibling(self):
        block = _full_structure_block(self.text)
        self.assertRegex(block, r"(?m)^tier_decision:")

    def test_tier_positioned_alongside_other_top_level_blocks(self):
        # AC-2: "positioned so that a reader sees them alongside the other
        # top-level blocks" -- verified here as sitting between the
        # pre-existing `parent_branch` and `project` top-level keys, not
        # off on its own past the end of the listing.
        block = _full_structure_block(self.text)
        parent_branch_idx = block.index("\nparent_branch:")
        project_idx = block.index("\nproject:")
        tier_idx = block.index("\ntier:")
        tier_decision_idx = block.index("\ntier_decision:")
        self.assertLess(parent_branch_idx, tier_idx)
        self.assertLess(tier_idx, tier_decision_idx)
        self.assertLess(tier_decision_idx, project_idx)

    def test_negative_proof_matcher_fails_on_synthetic_block_without_tier(self):
        sample = (
            "schema_version: 1\n"
            "feature: x\n"
            "parent_branch: em-workflow/x/integration\n"
            "project:\n"
            "  license: none\n"
        )
        self.assertNotRegex(sample, r"(?m)^tier:")
        self.assertNotRegex(sample, r"(?m)^tier_decision:")


# --- AC-1 (part 1): tier field's three-value domain -------------------


class TestTierFieldDomain(SchemaDocTestCase):
    def test_states_three_value_domain_in_order(self):
        section = _norm(self._tier_section())
        match = re.search(
            r"one of three values: `([a-z]+)`, `([a-z]+)`, or `([a-z]+)`",
            section,
        )
        self.assertIsNotNone(match)
        self.assertEqual(list(match.groups()), TIER_DOMAIN)

    def test_states_write_owner_is_the_orchestrator(self):
        section = _norm(self._tier_section())
        self.assertIn("Its write owner is the orchestrator", section)

    def test_does_not_restate_the_single_writer_rule(self):
        section = _norm(self._tier_section())
        self.assertIn("is not restated here", section)

    def test_negative_proof_wrong_order_fails_to_match_domain(self):
        synthetic = (
            "`tier` is a top-level field holding one of three values: "
            "`reduced`, `full`, or `minimal`."
        )
        match = re.search(
            r"one of three values: `([a-z]+)`, `([a-z]+)`, or `([a-z]+)`",
            synthetic,
        )
        self.assertIsNotNone(match)
        self.assertNotEqual(list(match.groups()), TIER_DOMAIN)

    def test_negative_proof_missing_value_fails_to_match_domain(self):
        synthetic = (
            "`tier` is a top-level field holding one of two values: "
            "`full` or `reduced`."
        )
        match = re.search(
            r"one of three values: `([a-z]+)`, `([a-z]+)`, or `([a-z]+)`",
            synthetic,
        )
        self.assertIsNone(match)


# --- AC-1 (part 2): decision block's exactly-four sub-fields -----------


class TestDecisionBlockSubfieldsExactlyFour(SchemaDocTestCase):
    def test_subfields_exact_four_values_in_order(self):
        section = self._tier_section()
        found = re.findall(r"^- `([a-z]+)`", section, re.MULTILINE)
        self.assertEqual(found, DECISION_SUBFIELDS)

    def test_negative_proof_extra_subfield_is_detected(self):
        synthetic = "- `by`\n- `confidence`\n- `at`\n- `reductions`\n- `extra`\n"
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, DECISION_SUBFIELDS)

    def test_negative_proof_missing_subfield_is_detected(self):
        synthetic = "- `by`\n- `confidence`\n- `at`\n"  # `reductions` dropped
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, DECISION_SUBFIELDS)

    def test_glosses_each_subfield(self):
        section = _norm(self._tier_section())
        self.assertIn("the agent that decided", section)
        self.assertIn("the decision timestamp", section)
        self.assertIn("the list of subtractions the decision applied", section)


# --- AC-3: status semantics no longer restricted to design ---------------


class TestStatusSemanticsNoLongerRestrictedToDesign(SchemaDocTestCase):
    def test_old_restricted_sentence_is_gone(self):
        self.assertNotIn(OLD_RESTRICTED_SENTENCE, self.text)

    def test_non_vacuity_matcher_would_fire_against_a_forged_copy_with_the_old_sentence(
        self,
    ):
        # Prove the matcher above is not vacuously passing because the
        # sentence could never have been found in the first place.
        forged = self._status_semantics_section() + "\n" + OLD_RESTRICTED_SENTENCE
        self.assertIn(OLD_RESTRICTED_SENTENCE, forged)

    def test_states_skipped_valid_for_any_tier_subtracted_step(self):
        section = _norm(self._status_semantics_section())
        self.assertIn(
            "`skipped` is valid for any step that a tier subtracted, not "
            "only for `design`",
            section,
        )

    def test_states_skip_reason_mandatory_in_every_case(self):
        section = _norm(self._status_semantics_section())
        self.assertIn(
            "`skipped_reason` is MANDATORY whenever `status` is `skipped`, "
            "in every case",
            section,
        )

    def test_states_skipped_step_passed_over_by_step_selection(self):
        section = _norm(self._status_semantics_section())
        self.assertIn(
            "A `skipped` step is passed over by the step-selection rule "
            "above, exactly as before",
            section,
        )

    def test_design_step_own_case_still_described(self):
        section = _norm(self._status_semantics_section())
        self.assertIn("create-spec-decided skip", section)
        self.assertIn("requirements-analyst's design-step recommendation", section)

    def test_negative_proof_matcher_fails_on_synthetic_section_without_the_rule(self):
        synthetic = "This section says nothing about tier-subtracted skips."
        self.assertNotIn(
            "`skipped` is valid for any step that a tier subtracted", synthetic
        )


# --- AC-4: completion rule restated, design's case not removed -----------


class TestCompletionRuleAllowsSkippedNonDesignSteps(SchemaDocTestCase):
    def test_old_design_only_completion_sentence_is_gone(self):
        self.assertNotIn(OLD_COMPLETION_SENTENCE, self.text)

    def test_non_vacuity_matcher_would_fire_against_a_forged_copy_with_the_old_sentence(
        self,
    ):
        forged = self._status_semantics_section() + "\n" + OLD_COMPLETION_SENTENCE
        self.assertIn(OLD_COMPLETION_SENTENCE, forged)

    def test_states_workflow_complete_with_tier_subtracted_step_skipped(self):
        section = _norm(self._status_semantics_section())
        self.assertIn(
            "The workflow is complete when every step is `completed`, "
            "except that a step a tier subtracted",
            section,
        )
        self.assertIn("may instead be `skipped`", section)

    def test_design_own_case_named_inside_the_completion_rule(self):
        section = _norm(self._status_semantics_section())
        self.assertIn(
            "`design`'s own create-spec-decided case included", section
        )

    def test_negative_proof_matcher_fails_on_synthetic_section_missing_the_rule(self):
        synthetic = "The workflow is complete when every step is completed."
        self.assertNotIn("a step a tier subtracted", synthetic)


# --- AC-5: upgrade-only rule ------------------------------------------


class TestUpgradeOnlyRule(SchemaDocTestCase):
    def test_states_may_be_raised_and_never_lowered(self):
        section = _norm(self._tier_section())
        self.assertIn(
            "The `tier` value may be raised and never lowered", section
        )

    def test_states_retranscription_must_not_lower(self):
        section = _norm(self._tier_section())
        self.assertIn(
            "re-transcription from persisted state", section
        )
        self.assertIn("must not lower the value already recorded", section)

    def test_cites_persisted_state_locations(self):
        section = self._tier_section()
        self.assertIn("feature-docs/{feature}/phase-state/tier.yaml", section)
        self.assertIn("workflow.yaml", section)

    def test_cites_develop_skill_as_mechanism_owner(self):
        section = self._tier_section()
        self.assertIn("`skills/develop/SKILL.md`", section)
        self.assertIn("not described", section)

    def test_does_not_describe_the_mechanism_procedurally(self):
        # The mechanism is cited by owner, not walked through: no mention
        # of the develop skill's own procedural vocabulary for it (its
        # turn-ending conditions / carve-out enumeration / step names --
        # task0005's region per IMPLEMENTATION.md D3).
        section = self._tier_section()
        self.assertNotIn("carve-out", section.lower())
        self.assertNotIn("step b", section.lower())
        self.assertNotIn("step c", section.lower())

    def test_negative_proof_matcher_fails_on_synthetic_section_missing_the_rule(self):
        synthetic = "The tier value may be changed freely at any time."
        self.assertNotIn("may be raised and never lowered", synthetic)


# --- AC-6: decision block cites thresholds' owner, no threshold, no -------
# confidence-only criterion ----------------------------------------------


class TestDecisionBlockNoThresholdNoConfidenceOnlyCriterion(SchemaDocTestCase):
    def test_cites_tier_rules_yaml_as_thresholds_owner(self):
        section = self._tier_section()
        self.assertIn("references/tier-rules.yaml", section)
        self.assertIn("are not restated here", section)

    def test_states_confidence_is_not_a_single_scalar(self):
        section = _norm(self._tier_section())
        self.assertIn("not a single confidence scalar", section)

    def test_no_numeric_threshold_literal_present(self):
        # A restated threshold row would contain a decimal literal like
        # 0.80 or 0.40 (SPEC.md's Decision Thresholds table); the schema's
        # decision-block description must contain none.
        section = self._tier_section()
        self.assertNotRegex(section, r"\d+\.\d+")

    def test_no_probability_symbol_vocabulary_restated(self):
        section = self._tier_section()
        self.assertNotIn("P(0)", section)
        self.assertNotIn("expectation_clear", section)

    def test_negative_proof_matcher_detects_a_forged_threshold_value(self):
        synthetic = "`confidence` decides `minimal` when P(0) >= 0.80."
        self.assertRegex(synthetic, r"\d+\.\d+")

    def test_negative_proof_matcher_fails_on_synthetic_section_without_citation(self):
        synthetic = "The confidence record holds observed probabilities."
        self.assertNotIn("references/tier-rules.yaml", synthetic)


# --- AC-7 (part 2): stdlib-only imports, discoverable ----------------------


class TestModuleIsStdlibOnlyAndDiscoverable(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])

    def test_module_file_name_matches_discovery_convention(self):
        # `python3 -m unittest discover -s tests` discovers files matching
        # test*.py by default; this file's own name is the proof.
        self.assertTrue(Path(__file__).name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
