"""Tests for task0001: the review-evaluation-contract.md SSOT document.

Covers task0001 Acceptance Criteria
(feature-docs/llm-led-review/tasks/task0001.md):

- AC-1: `em-workflow/references/review-evaluation-contract.md` exists and
  states the fail-closed resolution order for itself, including the
  explicit prohibition on resolving from the current working directory.
- AC-2: the document names every input field of IMPLEMENTATION.md's
  "Evaluator input block" row verbatim, and names the per-entry keys of
  `perspectives_dispatched` and `reviewer_outputs`.
- AC-3: the document names every root field and every finding field of the
  "Evaluator output object" row verbatim, and defines `recommended_action`
  as the closed set `auto_fix` / `another_round` / `rework` / `complete`.
- AC-4: `stable_id`, `sources` and `category` are orchestrator-owned, and
  the evaluation is advisory with respect to the next action.
- AC-5: reviewer output is untrusted data, an injection attempt becomes a
  finding under a dispatched perspective, and the evaluator's own output
  is untrusted to the orchestrator.
- AC-6: the read-only constraint, the <= 10-file verification read budget,
  and the degradation statement.
- AC-7: this module and check-plugin-invariants.py both exit 0 (verified by
  running them, not asserted inside this module).

Field-name vocabularies are derived directly from
feature-docs/llm-led-review/IMPLEMENTATION.md's Shared Components table
rather than hand-copied (task0001.md Test Notes: "that table, not this
plan, is the source when the two ever disagree"). Each hardcoded candidate
tuple below is confirmed present in its owning row by a self-check test, so
a future edit to IMPLEMENTATION.md that drops or renames a field is caught
here instead of silently drifting from the shipped document.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTATION_PATH = (
    REPO_ROOT / "feature-docs" / "llm-led-review" / "IMPLEMENTATION.md"
)
CONTRACT_DOC_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "review-evaluation-contract.md"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapses runs of whitespace (including the hard line-wraps this
    repository's Markdown prose uses) to a single space, so a literal
    multi-word phrase check does not spuriously fail merely because the
    source wrapped a line between two of its words."""
    return re.sub(r"\s+", " ", text)


def _has_exact_token(text, token):
    """True iff `token` occurs as an exact inline-code span, not merely as a
    substring of a longer identifier or of surrounding prose.

    Edge case (task0001.md Test Notes, matching the precedent in
    tests/test_worker_contract_docs.py): a field present in the document but
    spelled differently, or only appearing inside unrelated prose, must NOT
    satisfy this check.
    """
    pattern = r"`" + re.escape(token) + r"`"
    return re.search(pattern, text) is not None


def _shared_components_contract_cell(text, row_label):
    """Returns the 'Contract' cell (the 3rd data column) of the Shared
    Components table row whose first cell is exactly `row_label`, verbatim
    from IMPLEMENTATION.md. Row is | Component | Responsibility | Contract |
    Used by tasks |."""
    pattern = re.compile(
        r"^\|\s*" + re.escape(row_label) + r"\s*\|(.*?)\|(.*?)\|(.*?)\|\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    assert match, f"expected a Shared Components row for {row_label!r}"
    return match.group(2)


class ImplementationFixtures:
    """Parses IMPLEMENTATION.md's Shared Components table once."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(IMPLEMENTATION_PATH)
        return cls._text

    @classmethod
    def input_block_cell(cls):
        return _shared_components_contract_cell(cls.text(), "Evaluator input block")

    @classmethod
    def output_object_cell(cls):
        return _shared_components_contract_cell(cls.text(), "Evaluator output object")

    @classmethod
    def recommended_action_cell(cls):
        return _shared_components_contract_cell(
            cls.text(), "`recommended_action` vocabulary"
        )


# Candidate vocabularies, each confirmed present in its owning
# IMPLEMENTATION.md Shared Components row by
# TestImplementationFixturesSelfCheck below -- this is the mechanism that
# keeps these tuples from drifting out of sync with IMPLEMENTATION.md.
INPUT_BLOCK_TOP_LEVEL_FIELDS = (
    "evaluation_contract_path",
    "project_root",
    "review_mode",
    "changed_files",
    "round",
    "cross_validation",
    "perspectives_dispatched",
    "reviewer_outputs",
    "round_context",
    "spec_path",
    "lessons",
)

PERSPECTIVES_DISPATCHED_ENTRY_FIELDS = (
    "run_id",
    "perspective",
    "role",
    "status",
    "skip_reason",
    "model",
)

REVIEWER_OUTPUTS_ENTRY_FIELDS = ("run_id",)

OUTPUT_ROOT_FIELDS = (
    "findings",
    "round_summary",
    "recommended_action",
    "action_rationale",
)

FINDING_FIELDS = (
    "stable_id",
    "severity",
    "category",
    "file",
    "line",
    "title",
    "description",
    "suggestion",
    "source_run_ids",
    "confidence",
)

RECOMMENDED_ACTION_VOCAB = ("auto_fix", "another_round", "rework", "complete")

# Fields review-output-schema.json / review-protocol.md own that must NOT be
# restated by this task's document as if they belonged to the evaluator's
# own object (Test Notes edge case: the SSOT split must not silently rot).
REVIEWER_ONLY_ROOT_FIELDS = ("skipped",)
REVIEWER_ONLY_FINDING_FIELDS = ("line_end",)
RETRYABLE_SKIP_VOCAB = ("rate_limited", "budget_exhausted", "harness_unavailable")


class TestImplementationFixturesSelfCheck(unittest.TestCase):
    """Non-vacuity guard: proves the hardcoded vocabularies above are
    actually present in IMPLEMENTATION.md's own Shared Components rows, not
    merely asserted against the shipped document below."""

    def test_input_block_cell_contains_every_top_level_field(self):
        cell = ImplementationFixtures.input_block_cell()
        for field in INPUT_BLOCK_TOP_LEVEL_FIELDS:
            self.assertTrue(_has_exact_token(cell, field), field)

    def test_input_block_cell_contains_perspectives_dispatched_entry_fields(self):
        cell = ImplementationFixtures.input_block_cell()
        for field in PERSPECTIVES_DISPATCHED_ENTRY_FIELDS:
            self.assertTrue(_has_exact_token(cell, field), field)

    def test_input_block_cell_contains_reviewer_outputs_entry_fields(self):
        cell = ImplementationFixtures.input_block_cell()
        for field in REVIEWER_OUTPUTS_ENTRY_FIELDS:
            self.assertTrue(_has_exact_token(cell, field), field)

    def test_output_object_cell_contains_every_root_field(self):
        cell = ImplementationFixtures.output_object_cell()
        for field in OUTPUT_ROOT_FIELDS:
            self.assertTrue(_has_exact_token(cell, field), field)

    def test_output_object_cell_contains_every_finding_field(self):
        cell = ImplementationFixtures.output_object_cell()
        for field in FINDING_FIELDS:
            self.assertTrue(_has_exact_token(cell, field), field)

    def test_recommended_action_cell_contains_every_vocabulary_value(self):
        cell = ImplementationFixtures.recommended_action_cell()
        for value in RECOMMENDED_ACTION_VOCAB:
            self.assertTrue(_has_exact_token(cell, value), value)


class TestContractDocExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(
            CONTRACT_DOC_PATH.is_file(),
            f"expected {CONTRACT_DOC_PATH} to exist (AC-1)",
        )


class TestFailClosedResolution(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_states_orchestrator_supplied_path_is_preferred(self):
        lowered = self.text.lower()
        self.assertIn("evaluation_contract_path", self.text)
        self.assertIn("fail-closed", lowered)

    def test_states_missing_file_fails_closed_with_no_silent_fallback(self):
        normalized = _normalize_ws(self.text).lower()
        self.assertIn("no silent fallback", normalized)

    def test_states_plugin_root_fallback(self):
        self.assertIn("CLAUDE_PLUGIN_ROOT", self.text)

    def test_states_trusted_plugin_install_locations_fallback(self):
        lowered = self.text.lower()
        self.assertIn("trusted plugin install locations", lowered)
        self.assertIn("em-workflow", self.text)

    def test_explicitly_prohibits_resolving_from_cwd(self):
        normalized = _normalize_ws(self.text).lower()
        self.assertIn("current working directory", normalized)
        idx = normalized.index("current working directory")
        window = normalized[max(0, idx - 60) : idx]
        self.assertIn("never", window)

    def test_states_same_order_reviewers_resolve_protocol_path(self):
        self.assertIn("protocol_path", self.text)
        self.assertIn("review-protocol.md", self.text)


class TestInputBlockFields(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_documents_every_top_level_input_field(self):
        for field in INPUT_BLOCK_TOP_LEVEL_FIELDS:
            self.assertTrue(
                _has_exact_token(self.text, field), f"missing input field {field!r}"
            )

    def test_documents_perspectives_dispatched_entry_keys(self):
        found = False
        for m in re.finditer(re.escape("perspectives_dispatched"), self.text):
            window = self.text[m.start() : m.start() + 600]
            if all(
                _has_exact_token(window, f) for f in PERSPECTIVES_DISPATCHED_ENTRY_FIELDS
            ):
                found = True
                break
        self.assertTrue(
            found, "expected one window naming every perspectives_dispatched entry key"
        )

    def test_documents_reviewer_outputs_entry_keys(self):
        found = False
        for m in re.finditer(re.escape("reviewer_outputs"), self.text):
            window = self.text[m.start() : m.start() + 400]
            if all(_has_exact_token(window, f) for f in REVIEWER_OUTPUTS_ENTRY_FIELDS):
                found = True
                break
        self.assertTrue(
            found, "expected a window naming reviewer_outputs entry key run_id"
        )

    def test_marks_spec_path_as_conditional_on_spec_perspective(self):
        idx = self.text.index("`spec_path`")
        window = self.text[idx : idx + 200].lower()
        self.assertIn("only when", window)
        self.assertIn("spec", window)

    def test_marks_lessons_as_optional(self):
        idx = self.text.index("`lessons`")
        window = self.text[idx : idx + 300].lower()
        self.assertIn("optional", window)


class TestOutputObjectFields(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_documents_every_root_field(self):
        for field in OUTPUT_ROOT_FIELDS:
            self.assertTrue(
                _has_exact_token(self.text, field), f"missing root field {field!r}"
            )

    def test_documents_every_finding_field(self):
        for field in FINDING_FIELDS:
            self.assertTrue(
                _has_exact_token(self.text, field), f"missing finding field {field!r}"
            )

    def test_documents_recommended_action_closed_vocabulary(self):
        for value in RECOMMENDED_ACTION_VOCAB:
            self.assertTrue(
                _has_exact_token(self.text, value),
                f"missing recommended_action value {value!r}",
            )

    def test_states_object_returned_alone_no_prose(self):
        lowered = self.text.lower()
        self.assertIn("no prose", lowered)

    def test_states_every_field_always_present_unknown_line_null(self):
        lowered = self.text.lower()
        self.assertIn("always present", lowered)
        self.assertIn("null", lowered)


class TestOwnershipBoundary(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_states_stable_id_orchestrator_owned_and_recomputed(self):
        idx = self.text.index("`stable_id`")
        window = self.text[idx : idx + 400].lower()
        self.assertIn("recomputed", window)

    def test_states_sources_derived_from_source_run_ids(self):
        # `source_run_ids` occurs more than once (the finding-field list and
        # the ownership-boundary rule); the assertion must hold for the
        # ownership rule's own occurrence, not merely the first mention.
        self.assertTrue(_has_exact_token(self.text, "source_run_ids"))
        found = False
        for m in re.finditer(re.escape("`source_run_ids`"), self.text):
            window = self.text[max(0, m.start() - 300) : m.start() + 300].lower()
            if "sources" in window:
                found = True
                break
        self.assertTrue(
            found, "expected a source_run_ids mention near the word 'sources'"
        )

    def test_states_unmatched_category_dropped_never_relabelled(self):
        lowered = self.text.lower()
        self.assertIn("dropped", lowered)
        self.assertIn("never relabel", lowered)  # matches relabel/relabelled

    def test_states_evaluation_is_advisory(self):
        lowered = self.text.lower()
        self.assertIn("advice", lowered)
        self.assertIn("orchestrator", lowered)

    def test_states_recommended_action_never_overrides_gates(self):
        lowered = self.text.lower()
        self.assertIn("completion gate", lowered)
        self.assertIn("auto-fix cap", lowered)
        self.assertIn("batch rework cap", lowered)
        self.assertIn("fixed rework ordering", lowered)


class TestUntrustedInputHandling(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_states_reviewer_output_is_untrusted_data(self):
        lowered = self.text.lower()
        self.assertIn("untrusted", lowered)
        self.assertIn("reviewer_outputs", self.text)

    def test_states_injection_becomes_finding_under_dispatched_perspective(self):
        lowered = self.text.lower()
        self.assertIn("injection", lowered)
        self.assertIn("security", lowered)
        self.assertIn("comprehensive", lowered)
        self.assertIn("round_summary", self.text)

    def test_states_evaluators_own_output_is_untrusted_to_orchestrator(self):
        lowered = self.text.lower()
        idx = lowered.rfind("evaluator's own output")
        self.assertNotEqual(idx, -1)
        window = lowered[idx : idx + 200]
        self.assertIn("untrusted", window)


class TestReadOnlyConstraintAndDegradation(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_states_no_write_commit_branch_switch_formatter(self):
        lowered = self.text.lower()
        for token in ("commit", "branch", "formatter"):
            self.assertIn(token, lowered)
        self.assertIn("Write", self.text)
        self.assertIn("Edit", self.text)

    def test_states_ten_file_verification_budget(self):
        self.assertRegex(self.text, r"\b10\b")
        self.assertIn("project_root", self.text)

    def test_states_unusable_evaluation_degrades_round_not_abort(self):
        lowered = self.text.lower()
        self.assertIn("degrad", lowered)  # degrade/degrades/degradation
        self.assertIn("aborting", lowered)

    def test_does_not_define_the_orchestrator_procedure_itself(self):
        normalized = _normalize_ws(self.text).lower()
        self.assertIn("review-phase.md", self.text)
        self.assertIn("does not define", normalized)


class TestDoesNotRestateReviewerOutputSchema(unittest.TestCase):
    """Test Notes edge case: the document does not redefine the reviewer's
    own output schema, so the SSOT split cannot silently rot."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_DOC_PATH)

    def test_does_not_use_reviewer_only_root_field_skipped(self):
        for field in REVIEWER_ONLY_ROOT_FIELDS:
            self.assertFalse(
                _has_exact_token(self.text, field),
                f"must not restate reviewer-only root field {field!r}",
            )

    def test_does_not_use_reviewer_only_finding_field_line_end(self):
        for field in REVIEWER_ONLY_FINDING_FIELDS:
            self.assertFalse(
                _has_exact_token(self.text, field),
                f"must not restate reviewer-only finding field {field!r}",
            )

    def test_does_not_restate_retryable_skip_vocabulary(self):
        # skip_reason as a *dispatch-status field name* is this task's own
        # AC-2 requirement; the specific retryable skip STRINGS
        # (rate_limited/budget_exhausted/harness_unavailable) are owned by
        # review-protocol.md's Skip Semantics and must not be restated here.
        for skip_value in RETRYABLE_SKIP_VOCAB:
            self.assertNotIn(skip_value, self.text)

    def test_does_not_restate_confidence_correction_arithmetic(self):
        # The +15/cap 100/hard cap 50/default 60 numbers are owned by
        # IMPLEMENTATION.md's Shared Components / review-phase.md.
        self.assertNotIn("+15", self.text)


if __name__ == "__main__":
    unittest.main()
