"""Tests for task0005 (rework-contract-drift): the phase-state
format-version compatibility rule and the classification replay rule
(em-workflow/references/phase-state.md).

Covers task0005 Acceptance Criteria
(feature-docs/rework-contract-drift/tasks/task0005.md):

- AC-1: the document states that a record written before the shape change
  is read as the current format version and is not reported as an unknown
  version.
- AC-2: the document states that such a record's pre-change spec-change
  shape is refused at the point of use, with a named diagnostic
  identifying the pre-change shape as the cause, and that the same
  treatment applies to a pre-change classification shape.
- AC-3: the document names the remedy in the same place, so a pre-change
  record is never left silently non-re-enterable.
- AC-4: the declared format version is unchanged.
- AC-5: the idempotency section defines the classification record's
  replay rule.
- AC-6: the compatibility rule and the replay rule restate no rule owned
  by another document; each cites its owner by repository-relative path.
- AC-7: the retired `spec_change` origin field name appears nowhere in
  this task's owned surface (see TestRetiredOriginFieldNameAbsenceScan
  below, the "Retired-identifier absence scan" this task contributes per
  IMPLEMENTATION.md Shared Components).

This is a documentation task (Test Notes: "assertions are textual pins
over the rule's substance ... rather than exact prose"), so these are
structural/textual checks over the reference markdown, reading the
document live (NFR4). Follows the pattern established by
tests/test_phase_state_doc.py.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
TEST_PHASE_STATE_DOC_PATH = REPO_ROOT / "tests" / "test_phase_state_doc.py"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapses whitespace runs (including the newlines Markdown's own
    line-wrapping introduces mid-sentence) to single spaces, so a
    multi-word phrase pin does not depend on exactly where the source
    happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _format_version_section(text):
    start = text.index("### Format-version compatibility")
    # The section runs to end-of-file: it is the last subsection under
    # "## Legacy feature compatibility".
    return text[start:]


def _pre_change_compatibility_block(section):
    idx = section.index("**Pre-change record compatibility**")
    return _normalize_ws(section[idx:])


def _idempotency_section(text):
    start = text.index("## ID uniqueness and idempotency")
    end = text.index("### worker_runs[].status transitions")
    return text[start:end]


def _classification_replay_bullet(idempotency_section):
    start = idempotency_section.index("- `classification` has no per-entry ID")
    # This is the last bullet in the list, immediately followed by the
    # section's trailing blank line(s) before the next heading.
    return _normalize_ws(idempotency_section[start:])


class TestFormatVersionCompatibilitySectionPresent(unittest.TestCase):
    """Sanity: the format-version section exists and carries both the
    pre-existing unknown-schema_version rule and the new compatibility
    rule in one place (Design: "the format-version section states the
    compatibility rule for pre-change records")."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)

    def test_section_heading_present(self):
        self.assertIn("### Format-version compatibility", self.text)

    def test_unknown_schema_version_rule_and_compatibility_rule_share_the_section(self):
        section = _format_version_section(self.text)
        self.assertIn("Unknown `schema_version`", section)
        self.assertIn("Pre-change record compatibility", section)
        self.assertLess(
            section.index("Unknown `schema_version`"),
            section.index("Pre-change record compatibility"),
        )


class TestPreChangeRecordReadAsCurrentVersion(unittest.TestCase):
    """AC-1: a record written before the shape change is read as the
    current format version and is not reported as an unknown version."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.block = _pre_change_compatibility_block(_format_version_section(cls.text))

    def test_pre_change_record_is_not_an_unknown_version(self):
        self.assertIn("not an unknown version", self.block)

    def test_pre_change_record_reads_as_schema_version_1(self):
        self.assertIn("schema_version: 1", self.block)

    def test_pre_change_record_never_triggers_the_version_mismatch_abort(self):
        self.assertIn("never triggers the abort", self.block)

    def test_non_vacuity_a_synthetic_block_lacking_the_statement_fails(self):
        synthetic = "spec_change becoming mandatory did not move schema_version.\n"
        self.assertNotIn("not an unknown version", synthetic)
        self.assertNotIn("schema_version: 1", synthetic)


class TestPreChangeShapeRefusedWithNamedDiagnostic(unittest.TestCase):
    """AC-2: a pre-change record's spec-change shape is refused at the
    point of use, with a named diagnostic identifying the pre-change
    shape as the cause (rather than a generic missing field), and the
    same treatment applies to a pre-change classification shape."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.block = _pre_change_compatibility_block(_format_version_section(cls.text))

    def test_spec_change_named_diagnostic_present(self):
        self.assertIn("pre-change spec-change shape", self.block)

    def test_classification_named_diagnostic_present(self):
        self.assertIn("pre-change classification shape", self.block)

    def test_refusal_is_at_the_point_of_use_not_at_read_time(self):
        self.assertIn("refused at the point of use", self.block)

    def test_diagnostic_distinguishes_from_an_unrelated_missing_field(self):
        # Substance pin (Test Notes: pin the rule's substance, not exact
        # prose): the diagnostic must distinguish "this predates the pair"
        # from "some other field is simply missing".
        self.assertIn("distinguishing a record that predates the pair", self.block)
        self.assertIn("missing an unrelated field", self.block)

    def test_origin_pair_presence_and_non_emptiness_requirement_named(self):
        self.assertIn("origin_kind", self.block)
        self.assertIn("origin_id", self.block)
        self.assertIn("present and non-empty", self.block)

    def test_non_vacuity_a_synthetic_block_lacking_either_diagnostic_fails(self):
        synthetic_missing_spec_change = "the classification shape is refused with a diagnostic.\n"
        self.assertNotIn("pre-change spec-change shape", synthetic_missing_spec_change)
        synthetic_missing_classification = "the spec_change shape is refused with a diagnostic.\n"
        self.assertNotIn("pre-change classification shape", synthetic_missing_classification)


class TestRemedyNamedForBothRecords(unittest.TestCase):
    """AC-3: the remedy is named in the same place -- the spec-change
    transition rewrites the record wholesale on its next occurrence -- so
    a pre-change record is never left silently non-re-enterable."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.block = _pre_change_compatibility_block(_format_version_section(cls.text))

    def test_spec_change_remedy_is_wholesale_replacement_on_next_occurrence(self):
        self.assertIn("wholesale", self.block)
        self.assertIn("next occurrence", self.block)
        self.assertIn("re-entry is restored", self.block)

    def test_classification_remedy_is_its_own_append_semantics(self):
        self.assertIn("append semantics", self.block)
        self.assertIn("never rewritten", self.block)

    def test_never_left_silently_non_reenterable_is_stated(self):
        self.assertIn("never left silently non-re-enterable", self.block)

    def test_neither_refusal_is_silent_each_states_reason_and_remedy(self):
        self.assertIn("Neither refusal is silent", self.block)
        self.assertIn("states its reason", self.block)
        self.assertIn("its remedy", self.block)

    def test_non_vacuity_a_synthetic_block_lacking_the_remedy_fails(self):
        synthetic = "the record's shape is refused at the point of use.\n"
        self.assertNotIn("wholesale", synthetic)
        self.assertNotIn("never left silently non-re-enterable", synthetic)


class TestDeclaredFormatVersionUnchanged(unittest.TestCase):
    """AC-4: the declared format version is unchanged. (The other half of
    AC-4 -- no validator, no fixture, no other document changed -- is a
    file-scope fact about this task's diff, not a property of this
    document's text; it is not testable from a live read of phase-state.md
    alone.)"""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)

    def test_schema_version_is_still_declared_as_1(self):
        idx = self.text.index("`schema_version`")
        row = self.text[idx : idx + 200]
        self.assertIn("Currently `1`", row)

    def test_schema_example_block_still_pins_schema_version_1(self):
        schema_start = self.text.index("## Schema")
        fence_end = self.text.index("\n```\n", schema_start)
        schema_block = self.text[schema_start:fence_end]
        self.assertIn("schema_version: 1", schema_block)


class TestCompatibilityRuleCitesOwnersWithoutRestating(unittest.TestCase):
    """AC-6: the compatibility rule restates no rule owned by another
    document; it cites its owner by repository-relative path. A negative
    proof shows the assertion fires against a synthetic copy that
    restates one."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.block = _pre_change_compatibility_block(_format_version_section(cls.text))

    def test_origin_pair_definition_is_cited_not_restated(self):
        self.assertIn("references/rework-task-synthesis.md", self.block)
        self.assertIn("Invariant 6", self.block)
        self.assertIn("cited here, not restated", self.block)

    @staticmethod
    def _restates_origin_pair_closed_values(text):
        """A restatement of rework-task-synthesis.md Invariant 6's own
        closed value set would spell out `origin_kind`'s two permitted
        values side by side, as a definition rather than a citation."""
        return "origin_kind" in text and "review" in text and "verify" in text

    def test_compatibility_block_does_not_restate_the_origin_pairs_closed_values(self):
        self.assertFalse(self._restates_origin_pair_closed_values(self.block))

    def test_non_vacuity_the_restatement_detector_fires_on_a_synthetic_copy(self):
        synthetic_restatement = (
            "spec_change requires origin_kind, one of review or verify, "
            "and a non-empty origin_id."
        )
        self.assertTrue(self._restates_origin_pair_closed_values(synthetic_restatement))

    def test_wholesale_remedy_is_an_internal_reference_not_a_restated_procedure(self):
        # The remedy points at this document's own "ID uniqueness and
        # idempotency" section by name rather than re-deriving the
        # spec_change replace-wholesale mechanism's own wording about
        # rework's spec-change transition.
        self.assertIn('see "ID uniqueness and idempotency"', self.block)


class TestClassificationReplayRule(unittest.TestCase):
    """AC-5: the idempotency section defines the classification record's
    replay rule, stating the outcome of a repeated write of the same pass
    and that a resumed run produces the same list as an uninterrupted
    one."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.idempotency_section = _idempotency_section(cls.text)
        cls.bullet = _classification_replay_bullet(cls.idempotency_section)

    def test_classification_bullet_present_in_idempotency_section(self):
        self.assertIn("classification", self.idempotency_section)

    def test_repeated_write_of_the_same_pass_states_no_op_vs_protocol_error(self):
        self.assertIn("no-op", self.bullet)
        self.assertIn("protocol error", self.bullet)
        self.assertIn("matching content", self.bullet)
        self.assertIn("diverging content", self.bullet)

    def test_resumed_run_produces_the_same_list_as_an_uninterrupted_one(self):
        self.assertIn("resumed run", self.bullet)
        self.assertIn("identical, in length and content", self.bullet)

    def test_does_not_restate_the_records_field_definitions(self):
        # Test Notes: "do not restate the record's field definitions,
        # which the field table already owns."
        for field_name in ("classifier", "verdict", "evidence_ids", "decision"):
            self.assertNotIn(field_name, self.bullet)

    def test_non_vacuity_a_synthetic_bullet_lacking_the_rule_fails(self):
        synthetic = "- `classification` is an append-only list.\n"
        self.assertNotIn("no-op", synthetic)
        self.assertNotIn("resumed run", synthetic)


def _retired_spec_change_origin_field_name():
    """The pre-rename `spec_change` origin field name -- the single field
    `origin_kind` / `origin_id` replaced. Built from parts at run time per
    the "Retired-identifier absence scan" contract (IMPLEMENTATION.md
    Shared Components, feature-docs/rework-contract-drift/
    IMPLEMENTATION.md), so this scan's own source never carries it as a
    contiguous literal and can never match itself."""
    return "_".join(["finding", "stable", "id"])


class TestRetiredOriginFieldNameAbsenceScan(unittest.TestCase):
    """AC-7: the retired `spec_change` origin field name appears nowhere
    in this task's owned surface -- em-workflow/references/phase-state.md
    and tests/test_phase_state_doc.py (IMPLEMENTATION.md D3's site list
    for task0005; feature-docs/rework-contract-drift/IMPLEMENTATION.md).

    Per the Shared Components "Retired-identifier absence scan" contract:
    reads live files, covers this task's own closed path set, and builds
    its search term at run time so the scan can never match its own
    source. This scan's site set is disjoint from every other task's
    (task0002, task0004) per D3, and their union is D3's stated surface."""

    OWNED_PATHS = (PHASE_STATE_PATH, TEST_PHASE_STATE_DOC_PATH)

    def test_retired_term_absent_from_every_owned_path(self):
        term = _retired_spec_change_origin_field_name()
        offenders = [str(path) for path in self.OWNED_PATHS if term in _read(path)]
        self.assertEqual(offenders, [], f"retired identifier found in: {offenders}")

    def test_non_vacuity_the_scan_fires_against_a_synthetic_violating_sample(self):
        term = _retired_spec_change_origin_field_name()
        synthetic = "spec_change:\n  " + term + ": abc123\n"
        self.assertIn(term, synthetic)


if __name__ == "__main__":
    unittest.main()
