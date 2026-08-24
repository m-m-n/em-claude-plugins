"""Tests for task0003: the required failed-item `category` field --
definition in em-workflow/references/workflow-schema.md and its
verify-step assignment procedure in em-workflow/skills/develop/SKILL.md.

Covers task0003 Acceptance Criteria
(feature-docs/rework-contract-drift/tasks/task0003.md):

- AC-1: workflow-schema.md defines `failed_items[].category` as a
  required, non-empty field with exactly the seven-value closed
  vocabulary, and states a missing/empty/out-of-vocabulary value is never
  interpreted as a default.
- AC-2: the develop skill's verify step states the orchestrator assigns
  the category when it records a failing item, derived from the failing
  verification scenario and the requirement identifiers that scenario
  maps to through the verification index.
- AC-3: the develop skill's verify step states the sentinel is assigned
  whenever the evidence is insufficient, unmapped, contradictory, or
  cannot exclude a security or license concern.
- AC-4: the develop skill's verify step states the verify phase never
  aborts on any category value, so every case reaches the classification
  gate; it cites the gate as where the abort lives without describing the
  abort itself.
- AC-5: the develop skill restates neither the vocabulary nor the field
  definition, naming the owning document by repository-relative path; a
  negative proof shows the same detector fires against a synthetic copy
  that does restate the vocabulary.
- AC-6: the specification document, the verification document format, the
  verification index, the retrospect phase and the rework planner are
  unchanged by this task (SPEC.md's own FR3 statement names this exact
  out-of-scope set). Per the task plan's Test Notes, this is checked by
  asserting the out-of-scope documents this task could plausibly touch --
  the VERIFICATION.md format template (plan-writing SKILL.md), the
  verification-index-owning document (rework-task-synthesis.md), the
  develop skill's own retrospect section, and the rework-planner agent
  prompt -- carry no restated failed-item category vocabulary, rather
  than by comparing revisions. SPEC.md itself is out of this task's write
  access entirely (worktree-task-workflow: never modify feature-docs/**);
  its guard here is a presence check of the FR3 text already there, not
  an absence check, since SPEC.md is the requirement's own source and
  legitimately names the vocabulary already.
- AC-7: exercised by running the whole suite, not by a test in this
  module.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "workflow-schema.md"
)
SKILL_PATH = os.path.join(REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md")
PLAN_WRITING_SKILL_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "skills", "plan-writing", "SKILL.md"
)
REWORK_SYNTHESIS_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "rework-task-synthesis.md"
)
REWORK_PLANNER_AGENT_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "agents", "rework-planner.md"
)
SPEC_PATH = os.path.join(REPO_ROOT, "feature-docs", "rework-contract-drift", "SPEC.md")

# The closed seven-value vocabulary this task's schema section defines: the
# six review perspectives (review-rules.yaml / reviewers.yaml) plus the
# `unknown` fail-closed sentinel (IMPLEMENTATION.md Shared Components).
VOCAB_VALUES = [
    "comprehensive",
    "spec",
    "security",
    "performance",
    "architecture",
    "license",
    "unknown",
]

# --- exact-wording markers for the develop skill's verify-step prose ------
# Copied verbatim from the sentences task0003 writes; matched via
# _strip_ws (below) so wrapping/indentation differences never break the
# match.

CATEGORY_ASSIGNMENT_TIMING_MARKER = (
    "失敗項目を記録する時点で、orchestrator はその項目の `category` を確定する"
)
CATEGORY_DERIVATION_MARKER = (
    "対応する failing な検証シナリオと、`verification_index`"
    "（`references/rework-task-synthesis.md` 参照）を通してそのシナリオが"
    "写像する要件 ID から導出する"
)
SENTINEL_CONDITION_MARKER = (
    "根拠が不十分、シナリオが要件に写像しない、矛盾する、または"
    "セキュリティ・ライセンス上の懸念を排除できない場合は sentinel 値を"
    "割り当てる"
)
NO_RESTATEMENT_CITATION_MARKER = (
    "`category` の定義・必須性・閉じた語彙は `references/workflow-schema.md` の "
    "`failed_items[].category` 節が唯一の定義元であり、ここでは繰り返さない"
)
NO_ABORT_MARKER = "verify フェーズは `category` がどの値であっても中断しない"
REACHES_GATE_MARKER = (
    "sentinel を含め、すべてのケースを classification gate まで到達させる"
)
GATE_CITATION_MARKER = (
    "gate 側の中断は `references/question-resolution.md` の "
    "Classification gate 節が定義し、ここでは記述しない"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _strip_ws(text):
    # Matches the convention in tests/test_develop_skill_rewiring.py: this
    # file's Japanese prose hard-wraps without a space at the break point,
    # so collapsing to a single space would inject whitespace the source
    # never had and could break a match that spans a wrap.
    return re.sub(r"\s+", "", text)


def backtick_quoted_vocab_terms_present(text):
    """Return the subset of VOCAB_VALUES that occur backtick-quoted (e.g.
    `` `security` ``) in `text` -- the shape a restated vocabulary bullet
    list or table would use, as distinct from an incidental bare-word
    mention elsewhere in prose."""
    return [v for v in VOCAB_VALUES if f"`{v}`" in text]


class SchemaDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)


class SkillDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def _verify_phase_section(self):
        return _section(self.text, "### verify フェーズ", "### retrospect フェーズ")


# --- AC-1: schema defines the field, required-ness, and closed vocabulary -


class TestSchemaDefinesCategoryField(SchemaDocTestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(SCHEMA_PATH))

    def _category_section(self):
        return _section(
            self.text,
            "## `failed_items[].category`",
            "## Command approval store",
        )

    def test_field_is_stated_required_and_non_empty(self):
        section = self._category_section()
        self.assertIn("REQUIRED and non-empty", _norm(section))

    def test_vocabulary_exact_seven_values_in_order(self):
        section = self._category_section()
        found = re.findall(r"^- `([a-z]+)`", section, re.MULTILINE)
        self.assertEqual(found, VOCAB_VALUES)

    def test_negative_proof_extra_value_is_detected(self):
        synthetic = (
            "- `comprehensive`\n- `spec`\n- `security`\n- `performance`\n"
            "- `architecture`\n- `license`\n- `unknown`\n- `extra`\n"
        )
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, VOCAB_VALUES)

    def test_negative_proof_missing_value_is_detected(self):
        synthetic = (
            "- `comprehensive`\n- `spec`\n- `security`\n- `performance`\n"
            "- `architecture`\n- `license`\n"  # `unknown` dropped
        )
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, VOCAB_VALUES)

    def test_states_never_interpreted_as_default(self):
        section = self._category_section()
        self.assertIn(
            "missing, empty or out-of-vocabulary value is never "
            "interpreted as a default",
            _norm(section),
        )

    def test_states_single_owner_of_the_definition(self):
        section = self._category_section()
        self.assertIn("single owner of the field's meaning", _norm(section))

    def test_verify_step_yaml_points_at_the_new_section(self):
        # The `failed_items` comment inside the verify step's YAML block
        # must point readers at the defining section rather than silently
        # growing an undocumented field.
        idx = self.text.index("failed_items: []")
        window = self.text[idx : idx + 400]
        self.assertIn("failed_items[].category", window)


# --- AC-2: assignment timing + derivation from scenario/requirement IDs ---


class TestVerifyStepAssignsCategoryAtRecordTime(SkillDocTestCase):
    def test_states_orchestrator_assigns_at_record_time(self):
        section = self._verify_phase_section()
        self.assertIn(
            _strip_ws(CATEGORY_ASSIGNMENT_TIMING_MARKER), _strip_ws(section)
        )

    def test_states_derivation_via_verification_index(self):
        section = self._verify_phase_section()
        self.assertIn(_strip_ws(CATEGORY_DERIVATION_MARKER), _strip_ws(section))


# --- AC-3: sentinel assignment condition -----------------------------------


class TestVerifyStepAssignsSentinelOnInsufficientEvidence(SkillDocTestCase):
    def test_states_sentinel_condition(self):
        section = self._verify_phase_section()
        self.assertIn(_strip_ws(SENTINEL_CONDITION_MARKER), _strip_ws(section))


# --- AC-4: verify never aborts; cites (not describes) the gate ------------


class TestVerifyPhaseDoesNotAbortOnCategory(SkillDocTestCase):
    def test_states_no_abort_on_any_category_value(self):
        section = self._verify_phase_section()
        self.assertIn(_strip_ws(NO_ABORT_MARKER), _strip_ws(section))

    def test_states_every_case_reaches_the_gate(self):
        section = self._verify_phase_section()
        self.assertIn(_strip_ws(REACHES_GATE_MARKER), _strip_ws(section))

    def test_cites_the_gate_by_path_and_section(self):
        section = self._verify_phase_section()
        self.assertIn(_strip_ws(GATE_CITATION_MARKER), _strip_ws(section))

    def test_does_not_describe_the_abort_itself(self):
        # The abort's own wording ("non-overridable" per SPEC.md FR3) is
        # task0004's to write into question-resolution.md; this section
        # must cite the gate, never describe the abort in that wording.
        section = self._verify_phase_section()
        self.assertNotIn("non-overridable", section)
        self.assertNotIn("最終的で覆せない", section)


# --- AC-5: no restated vocabulary or field definition; cites by path ------


class TestVerifyStepDoesNotRestateVocabulary(SkillDocTestCase):
    def test_no_vocabulary_terms_backtick_quoted_in_verify_section(self):
        section = self._verify_phase_section()
        self.assertEqual(backtick_quoted_vocab_terms_present(section), [])

    def test_cites_owning_document_and_field_by_path(self):
        section = self._verify_phase_section()
        self.assertIn(
            _strip_ws(NO_RESTATEMENT_CITATION_MARKER), _strip_ws(section)
        )
        self.assertIn("references/workflow-schema.md", section)

    def test_negative_proof_detector_fires_on_a_restating_synthetic_copy(self):
        section = self._verify_phase_section()
        synthetic = (
            section
            + "\n\n`comprehensive` `spec` `security` `performance` "
            "`architecture` `license` `unknown`\n"
        )
        self.assertEqual(
            backtick_quoted_vocab_terms_present(synthetic), VOCAB_VALUES
        )


# --- AC-6: out-of-scope documents unchanged / carry no restated vocabulary


class TestOutOfScopeDocumentsAreUntouched(unittest.TestCase):
    def test_verification_format_template_has_no_restated_vocabulary(self):
        text = _read(PLAN_WRITING_SKILL_PATH)
        section = _section(
            text,
            "## VERIFICATION.md Template (feature-wide)",
            "## Pre-Save Self-Verification Checklist (MANDATORY)",
        )
        self.assertEqual(backtick_quoted_vocab_terms_present(section), [])

    def test_verification_index_document_has_no_restated_vocabulary(self):
        text = _read(REWORK_SYNTHESIS_PATH)
        self.assertEqual(backtick_quoted_vocab_terms_present(text), [])

    def test_retrospect_phase_has_no_restated_vocabulary(self):
        text = _read(SKILL_PATH)
        section = _section(text, "### retrospect フェーズ", "## Step C")
        self.assertEqual(backtick_quoted_vocab_terms_present(section), [])

    def test_rework_planner_agent_has_no_restated_vocabulary(self):
        text = _read(REWORK_PLANNER_AGENT_PATH)
        self.assertEqual(backtick_quoted_vocab_terms_present(text), [])

    def test_negative_proof_detector_fires_on_synthetic_restatement(self):
        synthetic = (
            "some unrelated document text\n"
            "`comprehensive` `spec` `security` `performance` "
            "`architecture` `license` `unknown`\n"
        )
        self.assertEqual(
            backtick_quoted_vocab_terms_present(synthetic), VOCAB_VALUES
        )

    def test_specification_document_still_states_its_own_fr3_text(self):
        # SPEC.md is out of this task's write access entirely (never
        # modify feature-docs/**); this is a presence check of content
        # already there, not an absence check -- SPEC.md is the
        # requirement's own source and legitimately names the vocabulary.
        text = _read(SPEC_PATH)
        self.assertIn(
            "verify-origin failed_items carry a required category", _norm(text)
        )


if __name__ == "__main__":
    unittest.main()
