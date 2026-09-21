"""Tests for task0013: one owner for the tier-decision record and its two
projections.

Covers task0013 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0013.md):

- AC-1: `references/phases/create-spec-phase.md`'s transcription section
  owns a single mapping table from every field of the persisted tier record
  to `tier_decision`'s four sub-fields and to the retrospect tier signal's
  members; `references/workflow-schema.md` and `skills/develop/SKILL.md`
  cite that table by path and restate no row of it.
- AC-2: `tier_decision` still carries exactly its four sub-fields, and the
  mapping table defines `reductions` as a projection of `tier` through the
  develop skill's reduction table -- no document outside that table
  enumerates subtractions.
- AC-3: every decision-basis identifier appearing in the phase-state
  schema, in the tier-decision procedure, and in the retrospect signal is
  one of `references/tier-rules.yaml`'s `decision_basis` values; the
  divergent spelling (`with_pre_survey`) appears nowhere in the plugin.
- AC-4: the workflow schema (and every other document) names the persisted
  record at `feature-docs/{feature}/phase-state/tier.yaml`; the wrongly
  ordered segments never appear anywhere in the plugin.
- AC-5: the tier-decision procedure states the number of judgement-skill
  invocations, the basis each corresponds to, what is compared between the
  two readings, and that a disagreement resolves to the tier that removes
  nothing, attributing that resolution to the evaluator's input contract.
- AC-6: this module asserts AC-1 through AC-5, pairs every matcher with a
  negative proof against a forged sample carrying the pre-change text, plus
  a non-vacuity guard, and imports standard-library modules only.

This module is discovered by ``python3 -m unittest discover -s tests``
(AC-7).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_ROOT = REPO_ROOT / "em-workflow"

CREATE_SPEC_PHASE_PATH = (
    EM_WORKFLOW_ROOT / "references" / "phases" / "create-spec-phase.md"
)
WORKFLOW_SCHEMA_PATH = EM_WORKFLOW_ROOT / "references" / "workflow-schema.md"
PHASE_STATE_PATH = EM_WORKFLOW_ROOT / "references" / "phase-state.md"
SKILL_PATH = EM_WORKFLOW_ROOT / "skills" / "develop" / "SKILL.md"
TIER_RULES_PATH = EM_WORKFLOW_ROOT / "references" / "tier-rules.yaml"

DOC_PATHS = {
    "create_spec_phase": CREATE_SPEC_PHASE_PATH,
    "workflow_schema": WORKFLOW_SCHEMA_PATH,
    "phase_state": PHASE_STATE_PATH,
    "skill": SKILL_PATH,
}

CORRECT_TIER_PATH = "feature-docs/{feature}/phase-state/tier.yaml"
WRONG_TIER_PATH = "phase-state/{feature}/tier.yaml"
DIVERGENT_BASIS = "with_pre_survey"

MAPPING_TABLE_HEADING = "**Tier-decision record mapping.**"
MAPPING_TABLE_END_MARKER = (
    "After this point `workflow.yaml`'s `tier` is the value read."
)

# A phrase unique to create-spec-phase.md's owned mapping table row for
# `tier_decision.by` -- used to prove single ownership: present in the
# owning document, absent everywhere else (Test Notes: "the negative proof
# is a forged sample in which a second document restates a row").
UNIQUE_MAPPING_ROW_PHRASE = (
    "the only agent Step A's tier-decision procedure ever dispatches as "
    "decider"
)

# The pre-change phrase (SKILL.md step 6, before this task) that folded the
# two-reading disagreement resolution into the availability-fallback
# paragraph instead of attributing it to the evaluator's input contract.
OLD_MIXED_DISAGREEMENT_PHRASE = (
    "判定結果が割れた場合、あるいはフォールバック表が解決しないその他の条件は"
)

EVALUATOR_CONTRACT_PHRASE = "評価器の入力契約"

REDUCTION_TABLE_ENUMERATION_NEEDLE = "REQUIREMENTS.md、IMPLEMENTATION.md、design step"

TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".py", ".json"}


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-collapsed rendering, insensitive to Markdown line-wrap
    (same convention as tests/test_tier_workflow_schema.py's ``_norm``)."""
    return re.sub(r"\s+", " ", text)


def _iter_plugin_text_files():
    """Every text-ish file under em-workflow/ -- the scan population for
    AC-3's and AC-4's repository-wide absence checks (Test Notes: "cheap
    text scans over the plugin directory")."""
    for path in EM_WORKFLOW_ROOT.rglob("*"):
        if path.is_file() and path.suffix in TEXT_EXTENSIONS:
            yield path


def _heading_index(text, heading, start=0):
    """Index of `heading` as its own line, not a quoted mention elsewhere
    (several documents cite a heading's literal text verbatim to point
    readers at it -- e.g. workflow-schema.md line 39 cites the
    `tier`/`tier_decision` heading inside an earlier YAML comment, and
    SKILL.md line 174 cites the tier-decision procedure's own heading
    inside its own prose before the heading itself appears). Mirrors
    tests/test_tier_workflow_schema.py's `_heading_index`."""
    match = re.search(r"(?m)^" + re.escape(heading), text[start:])
    if match is None:
        raise ValueError(f"heading not found as its own line: {heading!r}")
    return start + match.start()


class TestDocsExist(unittest.TestCase):
    def test_all_documents_exist(self):
        for name, path in DOC_PATHS.items():
            self.assertTrue(path.is_file(), f"missing ({name}): {path}")

    def test_tier_rules_yaml_exists(self):
        self.assertTrue(TIER_RULES_PATH.is_file())


# --- AC-1: single-owner mapping table; the other two documents cite it ---
# by path and restate no row -----------------------------------------------


class TestMappingTableSingleOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts = {name: _read(path) for name, path in DOC_PATHS.items()}

    def _mapping_section(self):
        text = self.texts["create_spec_phase"]
        start = text.index(MAPPING_TABLE_HEADING)
        end = text.index(MAPPING_TABLE_END_MARKER, start)
        return text[start:end]

    def test_create_spec_phase_owns_the_mapping_table_heading(self):
        self.assertIn(MAPPING_TABLE_HEADING, self.texts["create_spec_phase"])

    def test_mapping_table_is_locatable_and_nonempty(self):
        section = self._mapping_section()
        self.assertGreater(len(section.strip()), 200)

    def test_mapping_table_covers_every_persisted_record_field(self):
        section = self._mapping_section()
        for field in (
            "`tier`",
            "`bases`",
            "`decided_at`",
            "`pre_survey_estimate`",
            "`schema_version`",
            "`feature`",
        ):
            self.assertIn(field, section)

    def test_mapping_table_accounts_for_subfields_with_no_direct_source(self):
        section = self._mapping_section()
        self.assertIn("`by`:", section)
        self.assertIn("`reductions`:", section)

    def test_mapping_table_accounts_for_retrospect_only_rationale(self):
        section = self._mapping_section()
        self.assertIn("`rationale`:", section)

    def test_mapping_table_cites_basis_vocabulary_owner(self):
        section = self._mapping_section()
        self.assertIn("references/tier-rules.yaml", section)
        self.assertIn("decision_basis", section)

    def test_unique_mapping_row_phrase_present_only_in_owning_document(self):
        for name, text in self.texts.items():
            if name == "create_spec_phase":
                self.assertIn(UNIQUE_MAPPING_ROW_PHRASE, text)
            else:
                self.assertNotIn(UNIQUE_MAPPING_ROW_PHRASE, text)

    def test_workflow_schema_cites_the_mapping_table_by_path(self):
        text = self.texts["workflow_schema"]
        idx = _heading_index(text, "## `tier` and `tier_decision`")
        section = text[idx:]
        self.assertIn("references/phases/create-spec-phase.md", section)
        self.assertIn("Tier transcription section", section)

    def test_skill_tier_decision_procedure_cites_the_mapping_table_by_path(self):
        # The literal path citation lives in the tier-decision procedure
        # (step 7), not inside the retrospect section itself: the
        # retrospect section text is scanned by
        # tests/test_retrospect_verification_handoff.py for the
        # `failed_items[].category` vocabulary, and the file name
        # `create-spec-phase.md` contains the word `spec` as an isolated
        # token there. The retrospect paragraph instead cross-references
        # this same procedure step (see the next test).
        text = self.texts["skill"]
        start = _heading_index(text, "### tier 決定")
        end = _heading_index(text, "### design ステップ分岐", start)
        section = text[start:end]
        self.assertIn("references/phases/create-spec-phase.md", section)
        self.assertIn("Tier transcription", section)

    def test_skill_retrospect_signal_cross_references_the_citing_procedure_step(self):
        text = self.texts["skill"]
        idx = _heading_index(text, "### retrospect フェーズ")
        section = text[idx : idx + 4000]
        self.assertIn("上記「tier 決定」手順・手順 7", section)
        # And it must NOT restate the file path itself here (that citation
        # lives in the tier-decision procedure, per the test above).
        self.assertNotIn("create-spec-phase.md", section)

    def test_negative_proof_a_second_document_restating_a_row_is_detected(self):
        forged_second_document = (
            "workflow-schema.md now also spells out: `by` is "
            + UNIQUE_MAPPING_ROW_PHRASE
        )
        self.assertIn(UNIQUE_MAPPING_ROW_PHRASE, forged_second_document)

    def test_non_vacuity_the_unique_phrase_would_be_found_if_present(self):
        # Proves the absence-checks above are not vacuously passing because
        # the phrase could never be found in these documents at all.
        forged = self.texts["workflow_schema"] + "\n" + UNIQUE_MAPPING_ROW_PHRASE
        self.assertIn(UNIQUE_MAPPING_ROW_PHRASE, forged)


# --- AC-2: exactly four sub-fields; reductions is a projection, owned ----
# solely by the mapping table -----------------------------------------------


class TestReductionsIsAProjectionNotAnEnumeration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_schema_text = _read(WORKFLOW_SCHEMA_PATH)
        cls.create_spec_phase_text = _read(CREATE_SPEC_PHASE_PATH)
        cls.skill_text = _read(SKILL_PATH)
        cls.phase_state_text = _read(PHASE_STATE_PATH)

    def test_tier_decision_still_carries_exactly_four_subfields_in_order(self):
        idx = _heading_index(
            self.workflow_schema_text, "## `tier` and `tier_decision`"
        )
        section = self.workflow_schema_text[idx:]
        found = re.findall(r"^- `([a-z]+)`", section, re.MULTILINE)
        self.assertEqual(found, ["by", "confidence", "at", "reductions"])

    def test_mapping_table_defines_reductions_as_a_projection_of_tier(self):
        idx = self.create_spec_phase_text.index(MAPPING_TABLE_HEADING)
        end = self.create_spec_phase_text.index(MAPPING_TABLE_END_MARKER, idx)
        section = self.create_spec_phase_text[idx:end]
        self.assertIn("a projection of `tier`", section)
        self.assertIn("skills/develop/SKILL.md", section)
        self.assertIn("never a second enumeration", section)

    def test_reduction_table_enumeration_owned_solely_by_the_develop_skill(self):
        # SKILL.md's own Tier 削減表 is the one place that enumerates what
        # each tier subtracts; no other document this task touches may
        # duplicate that enumeration.
        self.assertIn(REDUCTION_TABLE_ENUMERATION_NEEDLE, self.skill_text)
        for text in (
            self.workflow_schema_text,
            self.create_spec_phase_text,
            self.phase_state_text,
        ):
            self.assertNotIn(REDUCTION_TABLE_ENUMERATION_NEEDLE, text)

    def test_negative_proof_extra_subfield_is_detected(self):
        synthetic = "- `by`\n- `confidence`\n- `at`\n- `reductions`\n- `extra`\n"
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, ["by", "confidence", "at", "reductions"])

    def test_non_vacuity_enumeration_needle_would_be_found_if_duplicated(self):
        forged = self.workflow_schema_text + "\n" + REDUCTION_TABLE_ENUMERATION_NEEDLE
        self.assertIn(REDUCTION_TABLE_ENUMERATION_NEEDLE, forged)


# --- AC-3: basis identifiers unified to tier-rules.yaml's vocabulary -----


class TestBasisVocabularyUnified(unittest.TestCase):
    def test_tier_rules_yaml_declares_the_two_reading_basis_values(self):
        text = _read(TIER_RULES_PATH)
        self.assertIn("decision_basis: description_only", text)
        self.assertIn("decision_basis: description_plus_code", text)

    def test_phase_state_persistence_section_uses_only_rules_file_values(self):
        text = _read(PHASE_STATE_PATH)
        idx = text.index("## tier decision persistence")
        section = text[idx:]
        self.assertIn("description_only", section)
        self.assertIn("description_plus_code", section)
        self.assertNotIn(DIVERGENT_BASIS, section)

    def test_skill_procedure_uses_only_rules_file_values(self):
        text = _read(SKILL_PATH)
        start = _heading_index(text, "### tier 決定")
        end = _heading_index(text, "### design ステップ分岐", start)
        section = text[start:end]
        self.assertIn("description_only", section)
        self.assertIn("description_plus_code", section)
        self.assertNotIn(DIVERGENT_BASIS, section)

    def test_skill_retrospect_signal_uses_only_rules_file_values(self):
        text = _read(SKILL_PATH)
        idx = _heading_index(text, "### retrospect フェーズ")
        section = text[idx : idx + 4000]
        self.assertIn("description_only", section)
        self.assertIn("description_plus_code", section)
        self.assertNotIn(DIVERGENT_BASIS, section)

    def test_divergent_spelling_absent_from_the_whole_plugin_tree(self):
        offenders = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in _iter_plugin_text_files()
            if DIVERGENT_BASIS in _read(path)
        )
        self.assertEqual(offenders, [])

    def test_negative_proof_forged_sample_with_divergent_spelling_is_detected(self):
        forged = "  - basis: with_pre_survey\n"
        self.assertIn(DIVERGENT_BASIS, forged)

    def test_non_vacuity_scan_actually_walks_plugin_files(self):
        # Proves the repo-wide scan's file discovery is not vacuously
        # empty (which would make the absence check above meaningless).
        scanned = list(_iter_plugin_text_files())
        self.assertGreater(len(scanned), 20)
        self.assertIn(SKILL_PATH, scanned)


# --- AC-4: persisted-record path named consistently, no wrong order ------


class TestPersistedRecordPathConsistent(unittest.TestCase):
    def test_correct_path_appears_in_workflow_schema(self):
        self.assertIn(CORRECT_TIER_PATH, _read(WORKFLOW_SCHEMA_PATH))

    def test_correct_path_appears_in_create_spec_phase(self):
        self.assertIn(CORRECT_TIER_PATH, _read(CREATE_SPEC_PHASE_PATH))

    def test_correct_path_appears_in_phase_state(self):
        self.assertIn(CORRECT_TIER_PATH, _read(PHASE_STATE_PATH))

    def test_correct_path_appears_in_skill(self):
        self.assertIn(CORRECT_TIER_PATH, _read(SKILL_PATH))

    def test_wrong_order_path_absent_from_the_whole_plugin_tree(self):
        offenders = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in _iter_plugin_text_files()
            if WRONG_TIER_PATH in _read(path)
        )
        self.assertEqual(offenders, [])

    def test_negative_proof_forged_sample_with_wrong_order_is_detected(self):
        forged = "persisted at `phase-state/{feature}/tier.yaml`"
        self.assertIn(WRONG_TIER_PATH, forged)

    def test_non_vacuity_wrong_order_needle_is_not_a_substring_of_the_correct_path(self):
        # Sanity check on the needle itself: if it were a substring of the
        # correct path, the absence check above could never fire even on a
        # genuinely broken document.
        self.assertNotIn(WRONG_TIER_PATH, CORRECT_TIER_PATH)


# --- AC-5: two-reading procedure fully specified, attributed to the ------
# evaluator's input contract ------------------------------------------------


class TestTwoReadingProcedureAttributesToEvaluatorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = _read(SKILL_PATH)
        start = _heading_index(text, "### tier 決定")
        end = _heading_index(text, "### design ステップ分岐", start)
        cls.section = text[start:end]

    def test_states_two_invocations(self):
        self.assertIn("2 回呼ぶ", self.section)

    def test_states_the_basis_each_invocation_corresponds_to(self):
        self.assertIn("description_only", self.section)
        self.assertIn("description_plus_code", self.section)

    def test_states_what_is_compared_between_the_two_readings(self):
        self.assertIn(
            "評価器は各読みがそれぞれ決定する tier を比較し", self.section
        )

    def test_states_disagreement_resolves_to_full(self):
        self.assertIn("何も引かない tier（`full`）を返す", self.section)

    def test_attributes_the_resolution_to_the_evaluators_input_contract(self):
        self.assertIn(EVALUATOR_CONTRACT_PHRASE, self.section)

    def test_old_mixed_into_availability_fallback_phrasing_is_gone(self):
        self.assertNotIn(OLD_MIXED_DISAGREEMENT_PHRASE, self.section)

    def test_non_vacuity_old_phrase_would_be_found_in_a_forged_pre_change_copy(self):
        forged = self.section + "\n" + OLD_MIXED_DISAGREEMENT_PHRASE
        self.assertIn(OLD_MIXED_DISAGREEMENT_PHRASE, forged)

    def test_negative_proof_synthetic_procedure_missing_attribution_is_detected(self):
        synthetic = "集めた値を評価器へ渡し、返された tier を採用する。"
        self.assertNotIn(EVALUATOR_CONTRACT_PHRASE, synthetic)


# --- AC-6 (part 2): stdlib-only imports, discoverable ----------------------


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
        self.assertTrue(Path(__file__).name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
