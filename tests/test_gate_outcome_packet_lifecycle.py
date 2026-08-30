"""Tests for task0025 (feature-docs/goal-vs-spec-divergence review round3
rework): the classification gate's outcome closes its question.

Covers task0025's own acceptance criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0025.md) that span more than
one owned document, per C4's one-module-per-owned-document convention (the
single-document pins for the Classification gate's new "Outcome" step live
in tests/test_classification_gate.py, and the Batch resolution sequence's
citation of it plus the NFR1 non-duplication guard live in
tests/test_question_resolution_doc.py; the validator's own half of AC-2
lives in tests/test_validate_worker_output.py):

- AC-2 (FR7): the cross-document half -- `references/question-packet-
  schema.md`'s `source` vocabulary and `em-workflow/scripts/validate-
  worker-output.py`'s `ANSWER_SOURCE_VALUES` constant agree on the exact
  same set, rather than being asserted separately (Test Notes).
- AC-4 (FR7, FR8): `em-workflow/skills/develop/SKILL.md` Step B's
  spec-change transition branch names the gate's call point in batch (after
  the packet's `gate_id` is identified and the routed arm has sent it to
  the Classification gate, before any of the transition's five steps
  runs), names the stop branch that halts the run before any step of the
  transition runs, and states that interactive is unchanged.
- AC-6 (this task's own new matchers, Step B half): a synthetic Step B
  variant that states the call point but omits any stop branch is detected
  as violating the stop-branch matcher above. (The other two AC-6 negative
  proofs -- a gate outcome with no answer record, and one with a packet
  still `issued` -- are pinned in tests/test_classification_gate.py,
  alongside the Outcome step content they defend.)
- AC-7 (NFR8, C10): no assertion here weakens or removes a pre-existing
  pin; this module is entirely new (Files to Create).
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKET_SCHEMA_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "question-packet-schema.md"
)
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "develop" / "SKILL.md"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _load_validator_module():
    import importlib.util

    script_path = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output_gate_outcome", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_validator_module()

BACKTICK_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_-]*)`")


def parse_source_vocabulary(text):
    """Extracts the backtick-quoted tokens from question-packet-schema.md's
    `### `source` vocabulary` block (the section body up to the next
    heading of the same or higher level)."""
    marker = "### `source` vocabulary"
    assert marker in text, "expected the `source` vocabulary heading"
    start = text.index(marker) + len(marker)
    next_heading = re.search(r"^#{2,3} ", text[start:], re.MULTILINE)
    body = text[start : start + next_heading.start()] if next_heading else text[start:]
    return set(BACKTICK_TOKEN_RE.findall(body))


class TestSourceVocabularyAgreement(unittest.TestCase):
    """AC-2: the schema document (the vocabulary's SSOT) and the validator's
    own constant must agree on the exact same set -- one assertion, not two
    separate ones (Test Notes)."""

    @classmethod
    def setUpClass(cls):
        cls.schema_text = _read(PACKET_SCHEMA_PATH)

    def test_schema_and_validator_source_vocabulary_are_identical(self):
        schema_values = parse_source_vocabulary(self.schema_text)
        self.assertEqual(schema_values, VWO.ANSWER_SOURCE_VALUES)

    def test_batch_classification_gate_is_in_the_agreed_set(self):
        schema_values = parse_source_vocabulary(self.schema_text)
        self.assertIn("batch-classification-gate", schema_values)
        self.assertIn("batch-classification-gate", VWO.ANSWER_SOURCE_VALUES)

    def test_parser_negative_proof_a_value_missing_from_the_document_is_detected(
        self,
    ):
        # Non-vacuity guard: proves the parser/comparison actually catches
        # drift instead of vacuously agreeing on any input.
        fake_text = (
            "### `source` vocabulary\n\n"
            "`user`, `batch-decision-table`.\n\n"
            "### Consistency rules\n"
        )
        fake_values = parse_source_vocabulary(fake_text)
        self.assertNotEqual(fake_values, VWO.ANSWER_SOURCE_VALUES)


class TestDevelopSkillStepBSpecChangeGateCall(unittest.TestCase):
    """AC-4: Step B's spec-change transition branch names the gate's call
    point in batch, the stop branch, and states interactive is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)

    def _step_b_section(self):
        start_marker = "## Step B: 自走ループ"
        end_marker = "### design ステップ分岐"
        self.assertIn(start_marker, self.text)
        self.assertIn(end_marker, self.text)
        start = self.text.index(start_marker)
        end = self.text.index(end_marker, start)
        return self.text[start:end]

    def _gate_call_paragraph(self, normalize=True):
        section = self._step_b_section()
        marker = "**spec-change 遷移のゲート呼び出し（バッチのみ）**"
        self.assertIn(
            marker, section, "expected the spec-change gate-call paragraph in Step B"
        )
        start = section.index(marker)
        # Bounded by the next paragraph break (blank line) or section end.
        rest = section[start:]
        next_break = rest.find("\n\n")
        paragraph = rest if next_break == -1 else rest[:next_break]
        if normalize:
            # Line-wrapping inside the paragraph is incidental (Markdown
            # soft-wraps at a column, not at word boundaries carrying
            # meaning); collapse it so content matchers below are not
            # fragile against re-wrapping.
            paragraph = re.sub(r"\s+", " ", paragraph)
        return paragraph

    def test_gate_call_paragraph_present_and_non_empty(self):
        # Non-vacuity guard (Test Notes).
        paragraph = self._gate_call_paragraph()
        self.assertTrue(paragraph.strip())
        self.assertGreater(len(paragraph), len("**spec-change 遷移のゲート呼び出し（バッチのみ）**"))

    def test_gate_call_paragraph_follows_the_transition_enumeration(self):
        # Structural anchor (Test Notes: match the step heading and the
        # transition's own enumeration, not a translated phrase): the
        # gate-call paragraph must come after the two-item bullet list that
        # names the spec-change transition, not before it.
        section = self._step_b_section()
        bullet_idx = section.index("- rework の spec-change 遷移")
        paragraph_idx = section.index("**spec-change 遷移のゲート呼び出し（バッチのみ）**")
        self.assertLess(bullet_idx, paragraph_idx)

    def test_call_point_named_after_gate_id_and_routed_arm_before_any_step(self):
        paragraph = self._gate_call_paragraph()
        self.assertIn("`gate_id` が特定され", paragraph)
        self.assertIn("routed arm", paragraph)
        self.assertIn("Classification gate", paragraph)
        # The paragraph must place the call before any of the five steps.
        self.assertIn("5 つの step のいずれも実行する前に", paragraph)

    def test_stop_branch_halts_before_any_step_and_records_reason(self):
        paragraph = self._gate_call_paragraph()
        self.assertIn("verdict が stop", paragraph)
        self.assertIn("inapplicable", paragraph)
        self.assertIn("5 つの step は 1 つも実行せず", paragraph)
        self.assertIn("run を停止し、理由を記録する", paragraph)

    def test_proceed_continues_all_five_steps(self):
        paragraph = self._gate_call_paragraph()
        self.assertIn("verdict が proceed のときだけ", paragraph)
        self.assertIn("続けて実行される", paragraph)

    def test_interactive_stated_unchanged(self):
        paragraph = self._gate_call_paragraph()
        self.assertIn("interactive はこの改訂で変更しない", paragraph)
        self.assertIn("新しい interactive の質問は追加され", paragraph)

    # --- AC-6 (this task's own new matcher, Step B half): negative proof --

    def test_negative_twin_call_point_without_stop_branch_fails(self):
        # A synthetic Step B paragraph that states the call point but omits
        # any stop-branch language must not satisfy the stop-branch matcher
        # above -- proving that matcher actually distinguishes presence
        # from absence rather than passing vacuously.
        fake_paragraph = (
            "**spec-change 遷移のゲート呼び出し（バッチのみ）**: バッチ実行で "
            "`rework.spec-change` の question の `gate_id` が特定され、"
            "routed arm がそれを Classification gate へ送った直後、"
            "その Classification gate を呼ぶ。"
        )
        self.assertNotIn("verdict が stop", fake_paragraph)
        self.assertNotIn("run を停止し、理由を記録する", fake_paragraph)


if __name__ == "__main__":
    unittest.main()
