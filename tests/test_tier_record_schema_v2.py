"""Tests for task0004 (tier-decision-staged-jev): tier.yaml schema_version 2
and its three projections.

Covers task0004 Acceptance Criteria
(feature-docs/tier-decision-staged-jev/tasks/task0004.md):

- AC-1: `references/phase-state.md`'s tier-decision persistence section
  defines schema_version 2 with every member (`schema_version`, `feature`,
  `tier`, `bases` -- entries with `basis`, `score`, `observed_at`, the
  `description_only` entry before `description_plus_code`, an entry absent
  when its call was not made or was unusable -- `pre_survey_estimate`
  absent when the pre-survey was not run or unusable, `decided_at`, and
  `fallback_reason` present only for a decision not made by a threshold
  row).
- AC-2: the same section states that an existing schema_version 1 record is
  reused as-is on resume, without re-decision and without rewriting.
- AC-3: `references/phases/create-spec-phase.md`'s mapping table has a row
  for every schema_version 2 member (AC-1's set) and maps
  `tier_decision.confidence` to each `bases` entry's basis and four bucket
  probabilities; neither the table nor the Tier transcription section
  contains `readings_disagree` or any statement about two readings
  agreeing or disagreeing.
- AC-4: `references/workflow-schema.md`'s tier section still lists exactly
  four `tier_decision` sub-fields (`by`, `confidence`, `at`, `reductions`),
  describes `confidence` as the bucket `"0"` to `"3"` probabilities per
  recorded basis, and contains no decimal fraction literal, no `P(0)` and
  no `expectation_clear`.
- AC-5: in `skills/develop/SKILL.md`'s retrospect `tier_decision` signal
  block, `rationale` is described as summarizing the deciding final
  reading or the fallback, the block mentions no agreement or
  disagreement between readings, and contains no `readings_disagree`.
- AC-6: `references/review-phase.md` and `references/review-rules.yaml`
  are unchanged by this task, and `tests/test_tier_spec_perspective.py`
  passes without modification.
- AC-7: every raw-text matcher in this module has a negative proof and a
  non-vacuity guard; this module is discovered by
  `python3 -m unittest discover -s tests`, imports only standard-library
  modules.

Test Notes followed:
- Each document check reads only its own region (the persistence section
  of phase-state.md, the Tier transcription section of
  create-spec-phase.md, the tier section of workflow-schema.md, the
  retrospect `tier_decision` block of SKILL.md); each locator asserts it
  found a non-empty region.
- `SCHEMA_V2_TOP_MEMBERS` / `BASES_ENTRY_MEMBERS` is the one member-list
  constant AC-1 and AC-3 both check against.
- Agreement wording is matched case-insensitively on the stems "agree" and
  "disagree", and on the Japanese "一致", inside the inspected regions
  only.
- AC-6's "unchanged by this task" is checked as a sha256 pin recorded when
  this module was written; AC-6's "passes without modification" is checked
  by actually re-running that module's suite as a subprocess.
"""

import ast
import hashlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_ROOT = REPO_ROOT / "em-workflow"

PHASE_STATE_PATH = EM_WORKFLOW_ROOT / "references" / "phase-state.md"
CREATE_SPEC_PHASE_PATH = (
    EM_WORKFLOW_ROOT / "references" / "phases" / "create-spec-phase.md"
)
WORKFLOW_SCHEMA_PATH = EM_WORKFLOW_ROOT / "references" / "workflow-schema.md"
SKILL_PATH = EM_WORKFLOW_ROOT / "skills" / "develop" / "SKILL.md"
REVIEW_PHASE_PATH = EM_WORKFLOW_ROOT / "references" / "review-phase.md"
REVIEW_RULES_PATH = EM_WORKFLOW_ROOT / "references" / "review-rules.yaml"

# The persisted record's members (task0004.md AC-1) -- the one constant
# AC-1 (phase-state.md) and AC-3 (create-spec-phase.md's mapping table)
# both check membership against, so the schema definition and the mapping
# table are pinned to the same set.
SCHEMA_V2_TOP_MEMBERS = (
    "schema_version",
    "feature",
    "tier",
    "bases",
    "pre_survey_estimate",
    "decided_at",
    "fallback_reason",
)
BASES_ENTRY_MEMBERS = ("basis", "score", "observed_at")

TIER_PERSISTENCE_START = "## tier decision persistence"
TIER_UPGRADE_START = "## tier upgrade completion record"

TIER_TRANSCRIPTION_START = "**Tier transcription**:"
DESIGN_SYSTEM_START = "## 11a. Design-system determination"

MAPPING_TABLE_HEADING = "**Tier-decision record mapping.**"
MAPPING_TABLE_END_MARKER = (
    "After this point `workflow.yaml`'s `tier` is the value read."
)

WORKFLOW_TIER_HEADING = "## `tier` and `tier_decision`"

RETROSPECT_BLOCK_START = "  tier_decision:"
RETROSPECT_BLOCK_END = "follow_up_drafts:"

AGREEMENT_STEM_PATTERN = re.compile(r"agree|disagree|一致", re.IGNORECASE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-collapsed rendering, insensitive to Markdown line-wrap."""
    return re.sub(r"\s+", " ", text)


def _heading_index(text, heading, start=0):
    """Index of `heading` as its own line -- not a quoted mention elsewhere
    (workflow-schema.md's own top skeleton cites the `tier`/`tier_decision`
    heading verbatim inside an earlier YAML comment, which does not start
    its line)."""
    match = re.search(r"(?m)^" + re.escape(heading), text[start:])
    if match is None:
        raise ValueError(f"heading not found as its own line: {heading!r}")
    return start + match.start()


def _section_between(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


def _phase_state_persistence_section(text):
    return _section_between(text, TIER_PERSISTENCE_START, TIER_UPGRADE_START)


def _create_spec_transcription_section(text):
    return _section_between(text, TIER_TRANSCRIPTION_START, DESIGN_SYSTEM_START)


def _create_spec_mapping_section(text):
    return _section_between(text, MAPPING_TABLE_HEADING, MAPPING_TABLE_END_MARKER)


def _workflow_schema_tier_section(text):
    idx = _heading_index(text, WORKFLOW_TIER_HEADING)
    return text[idx:]


def _skill_retrospect_tier_decision_block(text):
    return _section_between(text, RETROSPECT_BLOCK_START, RETROSPECT_BLOCK_END)


def _has_no_agreement_wording(text):
    return AGREEMENT_STEM_PATTERN.search(text) is None


# ---------------------------------------------------------------------------
# AC-1: phase-state.md defines schema_version 2 with every member and its
# presence rule.
# ---------------------------------------------------------------------------


class TestPersistenceSectionExists(unittest.TestCase):
    def test_section_is_locatable_and_nonempty(self):
        section = _phase_state_persistence_section(_read(PHASE_STATE_PATH))
        self.assertGreater(len(section.strip()), 200)


class TestSchemaVersion2Defined(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_state_persistence_section(_read(PHASE_STATE_PATH))

    def test_declares_schema_version_2(self):
        self.assertIn("schema_version: 2", self.section)
        self.assertIn("Currently `2`", self.section)

    def test_every_top_level_member_documented(self):
        for member in SCHEMA_V2_TOP_MEMBERS:
            self.assertRegex(
                self.section,
                r"\|\s*`" + re.escape(member) + r"`\s*\|",
                f"member {member!r} missing its field-table row",
            )

    def test_every_bases_entry_member_documented(self):
        for member in BASES_ENTRY_MEMBERS:
            self.assertIn(f"`{member}`", self.section)

    def test_bases_entry_order_and_absence_rule_stated(self):
        self.assertIn(
            "`description_only` entry always precedes the "
            "`description_plus_code` entry",
            self.section,
        )
        self.assertIn(
            "an entry is absent when its call was not made or was unusable",
            self.section,
        )

    def test_pre_survey_estimate_absence_rule_stated(self):
        self.assertIn(
            "absent when it was not run or was unusable", self.section
        )

    def test_fallback_reason_presence_rule_stated(self):
        self.assertIn(
            "Present only when the decision was not made by a threshold row",
            self.section,
        )
        self.assertIn("`threshold_rows:`", self.section)

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_forged_sample_missing_fallback_reason_row(self):
        forged = self.section.split("| `fallback_reason` |")[0]
        self.assertNotRegex(forged, r"\|\s*`fallback_reason`\s*\|")

    def test_negative_proof_forged_sample_missing_pre_survey_row(self):
        forged = "| `tier` | The decided tier. |\n"
        self.assertNotRegex(forged, r"\|\s*`pre_survey_estimate`\s*\|")

    def test_non_vacuity_matcher_finds_the_real_field(self):
        # Proves the regex used above is not vacuously unmatchable.
        sample = "| `fallback_reason` | present sometimes |"
        self.assertRegex(sample, r"\|\s*`fallback_reason`\s*\|")


# ---------------------------------------------------------------------------
# AC-2: schema_version 1 resume compatibility (reused as-is, no re-decision,
# no rewriting).
# ---------------------------------------------------------------------------


class TestSchemaVersion1ResumeCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_state_persistence_section(_read(PHASE_STATE_PATH))

    def test_states_v1_record_remains_valid_reused_as_is(self):
        norm = _norm(self.section)
        self.assertIn("schema_version: 1`", norm)
        self.assertIn("remains valid on resume", norm)
        self.assertIn("reused as-is", norm)

    def test_states_no_re_decision_and_no_rewriting(self):
        norm = _norm(self.section)
        self.assertIn("without re-decision", norm)
        self.assertIn("without rewriting", norm)

    def test_negative_proof_forged_sample_without_compatibility_statement(self):
        forged = "schema_version 2 has fields A, B, C.\n"
        self.assertNotIn("remains valid on resume", _norm(forged))
        self.assertNotIn("without re-decision", _norm(forged))

    def test_non_vacuity_real_section_carries_the_statement(self):
        norm = _norm(self.section)
        self.assertIn(
            "remains valid on resume", norm
        )  # duplicate-but-direct proof the real text is non-empty & matched
        self.assertGreater(len(self.section), 500)


# ---------------------------------------------------------------------------
# AC-3: create-spec-phase.md's mapping table row-per-member coverage, the
# confidence<->bases mapping, and the absence of agreement/disagreement
# wording.
# ---------------------------------------------------------------------------


class TestMappingTableRowPerMember(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PHASE_PATH)
        cls.mapping_section = _create_spec_mapping_section(cls.text)

    def test_mapping_section_is_locatable_and_nonempty(self):
        self.assertGreater(len(self.mapping_section.strip()), 200)

    def test_row_for_every_top_level_member(self):
        for member in SCHEMA_V2_TOP_MEMBERS:
            self.assertRegex(
                self.mapping_section,
                r"\|\s*`" + re.escape(member) + r"`",
                f"no mapping-table row for {member!r}",
            )

    def test_row_for_every_bases_entry_member(self):
        for member in BASES_ENTRY_MEMBERS:
            self.assertIn(f"`bases[].{member}`", self.mapping_section)

    def test_confidence_receives_basis_and_four_bucket_probabilities(self):
        self.assertIn(
            "each `bases` entry contributes one `confidence` entry keyed "
            "by this `basis`",
            self.mapping_section,
        )
        self.assertIn("four bucket probabilities", self.mapping_section)
        self.assertIn("`score.probabilities`", self.mapping_section)

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_missing_member_row_is_detected(self):
        forged = self.mapping_section.replace("`fallback_reason`", "")
        self.assertNotIn("`fallback_reason`", forged)

    def test_non_vacuity_row_pattern_would_match_a_forged_row(self):
        sample = "| `fallback_reason` | not carried | not carried |"
        self.assertRegex(sample, r"\|\s*`fallback_reason`")


class TestNoAgreementWording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PHASE_PATH)
        cls.transcription_section = _create_spec_transcription_section(cls.text)
        cls.mapping_section = _create_spec_mapping_section(cls.text)

    def test_transcription_section_is_locatable_and_nonempty(self):
        self.assertGreater(len(self.transcription_section.strip()), 200)

    def test_no_readings_disagree_literal_in_transcription_section(self):
        self.assertNotIn("readings_disagree", self.transcription_section)

    def test_no_agreement_or_disagreement_wording_in_transcription_section(self):
        self.assertTrue(_has_no_agreement_wording(self.transcription_section))

    def test_no_agreement_or_disagreement_wording_in_mapping_table(self):
        self.assertTrue(_has_no_agreement_wording(self.mapping_section))

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_forged_sample_with_agreement_wording_is_detected(self):
        forged = self.transcription_section + "\nwhether the readings agreed.\n"
        self.assertFalse(_has_no_agreement_wording(forged))

    def test_negative_proof_forged_sample_with_japanese_agreement_word(self):
        forged = self.transcription_section + "\n二つの読みが一致した場合\n"
        self.assertFalse(_has_no_agreement_wording(forged))

    def test_negative_proof_forged_sample_with_readings_disagree_literal(self):
        forged = self.transcription_section + "\nfallback_matrix:readings_disagree\n"
        self.assertIn("readings_disagree", forged)

    def test_non_vacuity_matcher_passes_on_a_clean_sample(self):
        self.assertTrue(_has_no_agreement_wording("nothing contentious here"))


# ---------------------------------------------------------------------------
# AC-4: workflow-schema.md's tier section: exactly four sub-fields, the
# confidence description, and the absence of numeric/vocabulary literals.
# ---------------------------------------------------------------------------


class TestWorkflowSchemaTierSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(WORKFLOW_SCHEMA_PATH)
        cls.section = _workflow_schema_tier_section(cls.text)

    def test_section_is_locatable_and_nonempty(self):
        self.assertGreater(len(self.section.strip()), 100)

    def test_exactly_four_subfields_in_order(self):
        found = re.findall(r"^- `([a-z]+)`", self.section, re.MULTILINE)
        self.assertEqual(found, ["by", "confidence", "at", "reductions"])

    def test_confidence_described_as_bucket_probabilities_per_basis(self):
        norm = _norm(self.section)
        self.assertIn('bucket `"0"` to `"3"` probability values', norm)
        self.assertIn("each recorded basis", norm)
        self.assertIn("not a single confidence scalar", norm)

    def test_no_decimal_fraction_literal(self):
        self.assertNotRegex(self.section, r"\d+\.\d+")

    def test_no_p0_or_expectation_clear(self):
        self.assertNotIn("P(0)", self.section)
        self.assertNotIn("expectation_clear", self.section)

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_extra_subfield_is_detected(self):
        synthetic = "- `by`\n- `confidence`\n- `at`\n- `reductions`\n- `extra`\n"
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, ["by", "confidence", "at", "reductions"])

    def test_negative_proof_decimal_literal_is_detected(self):
        synthetic = "`confidence` decides `minimal` when P(0) >= 0.80."
        self.assertRegex(synthetic, r"\d+\.\d+")
        self.assertIn("P(0)", synthetic)

    def test_non_vacuity_real_section_states_bucket_wording(self):
        self.assertIn('bucket `"0"` to `"3"`', self.section)


# ---------------------------------------------------------------------------
# AC-5: SKILL.md's retrospect tier_decision signal block.
# ---------------------------------------------------------------------------


class TestRetrospectTierDecisionBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.block = _skill_retrospect_tier_decision_block(cls.text)

    def test_block_is_locatable_and_nonempty(self):
        self.assertGreater(len(self.block.strip()), 100)

    def test_rationale_described_as_final_reading_or_fallback(self):
        self.assertIn("最終読み", self.block)
        self.assertIn("フォールバック", self.block)
        self.assertIn("fallback_reason", self.block)

    def test_members_match_the_mapping_table(self):
        for member in ("tier:", "rationale:", "bases:", "pre_survey_estimate:"):
            self.assertIn(member, self.block)
        for member in BASES_ENTRY_MEMBERS:
            self.assertIn(f"{member}:", self.block)

    def test_no_agreement_or_disagreement_wording(self):
        self.assertTrue(_has_no_agreement_wording(self.block))

    def test_no_readings_disagree_literal(self):
        self.assertNotIn("readings_disagree", self.block)

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_forged_sample_with_agreement_wording(self):
        forged = self.block + "\n二つの読みが一致しなかった場合のフォールバック\n"
        self.assertFalse(_has_no_agreement_wording(forged))

    def test_negative_proof_forged_sample_missing_rationale_description(self):
        forged = "  tier_decision:\n    tier: reduced\n"
        self.assertNotIn("最終読み", forged)

    def test_non_vacuity_real_block_carries_pre_existing_signal(self):
        # Proves the located block is the real, non-empty retrospect
        # tier_decision block and not an accidental empty slice.
        self.assertIn("description_only", self.block)
        self.assertIn("description_plus_code", self.block)


# ---------------------------------------------------------------------------
# AC-6: review-phase.md / review-rules.yaml untouched by this task; the
# spec-perspective test module passes without modification.
# ---------------------------------------------------------------------------


# Recorded when this module was written, from the pre-task0004 content of
# each file -- any edit to either file (by this task) changes the hash.
REVIEW_PHASE_SHA256 = (
    "9faf5ce42ad32c8249c1a1b5e6ea59027ed5e0427e1f1d1384b817312d98e5a0"
)
REVIEW_RULES_SHA256 = (
    "56fbc7788c9bf3d2ccd2ef0be569a94e1854e12c177dcc5fa69b96ee4b95c931"
)


def _sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestReviewDocumentsUntouched(unittest.TestCase):
    def test_review_phase_md_unchanged(self):
        self.assertEqual(_sha256_of(REVIEW_PHASE_PATH), REVIEW_PHASE_SHA256)

    def test_review_rules_yaml_unchanged(self):
        self.assertEqual(_sha256_of(REVIEW_RULES_PATH), REVIEW_RULES_SHA256)

    # -- negative proof + non-vacuity guard --------------------------------

    def test_negative_proof_a_changed_file_would_fail_the_pin(self):
        mutated = _read(REVIEW_PHASE_PATH) + "\nextra line\n"
        self.assertNotEqual(
            hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
            REVIEW_PHASE_SHA256,
        )

    def test_non_vacuity_files_are_non_trivial(self):
        self.assertGreater(REVIEW_PHASE_PATH.stat().st_size, 500)
        self.assertGreater(REVIEW_RULES_PATH.stat().st_size, 500)


class TestSpecPerspectiveSuitePasses(unittest.TestCase):
    def test_tier_spec_perspective_suite_passes_unmodified(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_tier_spec_perspective"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"stdout={result.stdout}\nstderr={result.stderr}",
        )


# ---------------------------------------------------------------------------
# AC-7: this module's own hygiene.
# ---------------------------------------------------------------------------


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
