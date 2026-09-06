"""Tests for task0001: the `failed_kind` definition and the infra-resume
record in the schema SSOT, `em-workflow/references/workflow-schema.md`.

Covers task0001 Acceptance Criteria
(feature-docs/implement-failed-kind/tasks/task0001.md):

- AC-1 (FR1): a `failed_kind` section enumerates exactly the two permitted
  values and states this document is the single owner of the field's
  meaning, required-ness and permitted values. Negative proof: the
  vocabulary matcher rejects a synthetic list with an extra value and one
  with a value dropped.
- AC-2 (FR1): the section states the field belongs to the `implement` step
  and is required on every write that sets that step's `status` to
  `failed`, and cites `references/implement-phase.md` as the owner of
  those write paths without restating which value each path writes.
- AC-3 (FR2): the section states the lifecycle in full -- set only by the
  write that sets `failed`, held for the duration of that status, returned
  to null by the same write set that leaves `failed`, with no separate
  write and no separate commit for either.
- AC-4 (FR9): the section states the missing-value compatibility rule (an
  `implement` `failed` with no `failed_kind` reads as `decision`, no
  migration runs), with a non-vacuity companion showing the required-ness
  statement (AC-2) still stands in the same section.
- AC-5 (FR7): the `batch` block section defines `batch.infra_resume` with
  both member keys, states `rounds` is monotonic and never reset, states
  the unset-read rule (independently for both defaults), and states the
  consuming judgment lives in `skills/develop/SKILL.md` and is not
  restated in the schema.
- AC-6 (FR1): the `implement` step's entry in the Full structure block
  names `failed_kind` and points at the defining section, and the `batch`
  mapping in that block names the `infra_resume` record; neither restates
  the vocabulary.
- AC-7 (NFR1): no document other than the schema document is touched by
  this task, and the new section is reachable at a stable, citable path.
- AC-8 (NFR4): exercised by running the whole suite, not by a test in this
  module.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "workflow-schema.md"
)

FAILED_KIND_HEADING = "## `failed_kind`"
BATCH_BLOCK_HEADING = "## `batch` block"
# `failed_kind` sits after "## Command approval store" and before
# "## `completed_at_commit`" -- placed there (rather than immediately
# after "## `failed_items[].category`", which would also fit the task
# plan's "alongside the existing field-definition sections" placement)
# so this task's new vocabulary bullets never fall inside
# test_failed_items_category.py's own (pre-existing, over-inclusive)
# `_category_section()` extraction, which runs from that file's first
# textual mention of "## `failed_items[].category`" -- an in-YAML-comment
# citation of the heading, not the heading itself -- through to
# "## Command approval store". Landing new `- `word`` bullets inside that
# already-over-inclusive range would silently break that file's
# positional vocabulary matcher; this file owns none of that risk once
# its own section sits after the range's end marker.
NEXT_HEADING_AFTER_FAILED_KIND = "## `completed_at_commit`"
NEXT_HEADING_AFTER_BATCH_BLOCK = "## Command approval store"

# The closed two-value vocabulary this task's schema section defines
# (IMPLEMENTATION.md C1): an external-cause value and a decision-required
# value.
VOCAB_VALUES = ["infra", "decision"]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _heading_index(text, heading, start=0):
    # Some in-yaml comments quote a heading's literal text verbatim (e.g.
    # `# ... (see "## \`goal\` block" below)`) to point readers at it. A
    # plain text.index() would match that quoted mention instead of the
    # real heading further down. Headings are always alone on their own
    # line, so anchor the search to a line start/end.
    match = re.search(
        r"(?m)^" + re.escape(heading), text[start:]
    )
    if match is None:
        raise ValueError(f"heading not found as its own line: {heading!r}")
    return start + match.start()


def _heading_section(text, start_heading, end_heading):
    start = _heading_index(text, start_heading)
    end = _heading_index(text, end_heading, start)
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text)


def backtick_quoted_vocab_terms_present(text):
    """Return the subset of VOCAB_VALUES that occur backtick-quoted (e.g.
    `` `infra` ``) in `text` -- the shape a restated vocabulary bullet list
    would use, as distinct from an incidental bare-word mention."""
    return [v for v in VOCAB_VALUES if f"`{v}`" in text]


class SchemaDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)

    def _failed_kind_section(self):
        return _heading_section(
            self.text, FAILED_KIND_HEADING, NEXT_HEADING_AFTER_FAILED_KIND
        )

    def _batch_block_section(self):
        return _heading_section(
            self.text, BATCH_BLOCK_HEADING, NEXT_HEADING_AFTER_BATCH_BLOCK
        )

    def _full_structure_block(self):
        # The "## Full structure" heading is followed by a fenced ```yaml
        # block; several in-comment lines inside that fence quote later
        # heading text verbatim (e.g. `# held verbatim (see "## \`goal\`
        # block" below)`), so slicing up to the next literal heading text
        # would stop early. Slice to the fence's own closing ``` instead.
        fence_start = self.text.index("```yaml", self.text.index("## Full structure"))
        fence_end = self.text.index("```", fence_start + len("```yaml"))
        return self.text[fence_start:fence_end]


# --- AC-1: section enumerates exactly the two permitted values, states ----
# single ownership --------------------------------------------------------


class TestFailedKindSectionDefinesVocabulary(SchemaDocTestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(SCHEMA_PATH))

    def test_section_exists(self):
        # Raises ValueError (via str.index) if the heading is absent.
        self._failed_kind_section()

    def test_vocabulary_exact_two_values_in_order(self):
        section = self._failed_kind_section()
        found = re.findall(r"^- `([a-z]+)`", section, re.MULTILINE)
        self.assertEqual(found, VOCAB_VALUES)

    def test_negative_proof_extra_value_is_detected(self):
        synthetic = "- `infra`\n- `decision`\n- `extra`\n"
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, VOCAB_VALUES)

    def test_negative_proof_missing_value_is_detected(self):
        synthetic = "- `infra`\n"  # `decision` dropped
        found = re.findall(r"^- `([a-z]+)`", synthetic, re.MULTILINE)
        self.assertNotEqual(found, VOCAB_VALUES)

    def test_states_single_owner_of_the_definition(self):
        section = _norm(self._failed_kind_section())
        self.assertIn("single owner of the field's meaning", section)
        self.assertIn("required-ness and its permitted values", section)

    def test_glosses_external_cause_meaning(self):
        section = _norm(self._failed_kind_section())
        self.assertIn("orphaned", section)
        self.assertIn("harness failure", section)

    def test_glosses_decision_required_meaning(self):
        section = _norm(self._failed_kind_section())
        self.assertIn("implementation itself", section)
        self.assertIn("plan", section)


# --- AC-2: belongs to implement step, required-ness, cites owner of write -
# paths ----------------------------------------------------------------


class TestFailedKindRequiredness(SchemaDocTestCase):
    def test_states_belongs_to_implement_step(self):
        section = _norm(self._failed_kind_section())
        self.assertIn("`implement` step", section)

    def test_states_required_on_every_failed_write(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "REQUIRED on every write that sets the `implement` step's "
            "`status` to `failed`",
            section,
        )

    def test_cites_implement_phase_as_write_path_owner(self):
        section = self._failed_kind_section()
        self.assertIn("references/implement-phase.md", section)

    def test_does_not_restate_which_value_each_path_writes(self):
        # The section must name the citation without describing the D2
        # per-path classification table (that table's own wording lives in
        # implement-phase.md, owned by task0002).
        section = self._failed_kind_section()
        self.assertNotIn("second failure", section.lower())
        self.assertNotIn("route-back", section.lower())


# --- AC-3: full lifecycle statement ----------------------------------------


class TestFailedKindLifecycle(SchemaDocTestCase):
    def test_states_set_only_by_the_failing_write(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "set only by the same write that sets `status` to `failed`",
            section,
        )

    def test_states_held_for_duration_of_failed_status(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "held for exactly as long as that `failed` status", section
        )

    def test_states_cleared_by_same_write_set_leaving_failed(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "returned to null by the same write set that moves the "
            "`implement` step off `failed`",
            section,
        )

    def test_states_no_separate_write_or_commit(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "No separate write and no separate commit exists for the set "
            "or for the clear",
            section,
        )


# --- AC-4: missing-value compatibility + non-vacuity companion -----------


class TestFailedKindMissingValueCompatibility(SchemaDocTestCase):
    def test_states_missing_value_reads_as_decision(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "An `implement` `failed` carrying no `failed_kind` reads as "
            "the `decision` value",
            section,
        )

    def test_states_no_migration_runs(self):
        section = _norm(self._failed_kind_section())
        self.assertIn("No migration runs", section)

    def test_states_compatibility_does_not_weaken_requiredness(self):
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "does not weaken the required-ness above for the write paths "
            "that are in scope",
            section,
        )

    def test_non_vacuity_requiredness_statement_still_present(self):
        # A compatibility paragraph that silently replaced the
        # required-ness statement would otherwise pass AC-4 vacuously.
        section = _norm(self._failed_kind_section())
        self.assertIn(
            "REQUIRED on every write that sets the `implement` step's "
            "`status` to `failed`",
            section,
        )

    def test_negative_proof_matcher_rejects_synthetic_without_the_rule(self):
        synthetic = "This section says nothing about missing values."
        self.assertNotIn(
            "An `implement` `failed` carrying no `failed_kind` reads as "
            "the `decision` value",
            synthetic,
        )


# --- AC-5: `batch.infra_resume` record -------------------------------------


class TestBatchInfraResumeRecord(SchemaDocTestCase):
    def test_names_both_member_keys(self):
        section = self._batch_block_section()
        self.assertIn("`infra_resume`", section)
        self.assertIn("`rounds`", section)
        self.assertIn("`cap`", section)

    def test_states_rounds_is_monotonic_and_never_reset(self):
        section = _norm(self._batch_block_section())
        self.assertIn("monotonic, never reset", section)

    def test_states_unset_read_rule_rounds_default_independently(self):
        section = self._batch_block_section()
        self.assertIn("`rounds: 0`", section)

    def test_states_unset_read_rule_cap_default_independently(self):
        section = self._batch_block_section()
        self.assertIn("`cap: 2`", section)

    def test_negative_proof_partial_statement_fails_both_checks(self):
        synthetic = "reads as unset (`rounds: 0`)"
        self.assertIn("`rounds: 0`", synthetic)
        self.assertNotIn("`cap: 2`", synthetic)

    def test_states_no_migration_runs_for_infra_resume(self):
        section = _norm(self._batch_block_section())
        self.assertIn(
            "No migration runs: an absent `batch` block, an absent "
            "`infra_resume` block, or an absent member key is read as "
            "unset",
            section,
        )

    def test_cites_develop_skill_as_judgment_owner_not_restated_here(self):
        section = _norm(self._batch_block_section())
        self.assertIn("`skills/develop/SKILL.md`", section)
        self.assertIn("is not restated here", section)

    def test_mirrors_verify_rework_citation_shape(self):
        # The section already does this for `verify_rework`; the new
        # paragraph must say so explicitly rather than leave it implicit.
        section = _norm(self._batch_block_section())
        self.assertIn("verify_rework", section)


# --- AC-6: Full structure block pointers, no restated vocabulary ----------


class TestFullStructurePointers(SchemaDocTestCase):
    def test_implement_step_entry_names_failed_kind(self):
        idx = self.text.index("- id: implement")
        next_step_idx = self.text.index("- id: review", idx)
        window = self.text[idx:next_step_idx]
        self.assertIn("failed_kind", window)

    def test_implement_step_entry_points_at_defining_section(self):
        idx = self.text.index("- id: implement")
        next_step_idx = self.text.index("- id: review", idx)
        window = self.text[idx:next_step_idx]
        self.assertIn(FAILED_KIND_HEADING, window)

    def test_implement_step_entry_does_not_restate_vocabulary(self):
        idx = self.text.index("- id: implement")
        next_step_idx = self.text.index("- id: review", idx)
        window = self.text[idx:next_step_idx]
        self.assertEqual(backtick_quoted_vocab_terms_present(window), [])

    def _batch_mapping(self):
        # `batch:` is the last top-level mapping in the Full structure
        # yaml block, so its own text runs to the end of that block.
        full_structure = self._full_structure_block()
        start = full_structure.index("\nbatch:")
        return full_structure[start:]

    def test_batch_mapping_names_infra_resume_record(self):
        self.assertIn("infra_resume", self._batch_mapping())

    def test_batch_mapping_does_not_restate_vocabulary(self):
        self.assertEqual(
            backtick_quoted_vocab_terms_present(self._batch_mapping()), []
        )


# --- AC-7: reachable at a stable, citable path -----------------------------


class TestSectionIsCitable(SchemaDocTestCase):
    def test_heading_text_is_present_verbatim(self):
        self.assertIn(FAILED_KIND_HEADING, self.text)

    def test_section_is_well_formed_between_its_own_heading_boundaries(self):
        # Use the line-anchored heading lookup, not a plain substring
        # search: an in-yaml comment earlier in the document quotes this
        # same heading text verbatim to point readers at it, and a plain
        # index() would match that mention instead of the real heading.
        # A well-formed, citable section is one whose own heading is
        # findable and strictly precedes the next heading that bounds it.
        section_idx = _heading_index(self.text, FAILED_KIND_HEADING)
        next_idx = _heading_index(
            self.text, NEXT_HEADING_AFTER_FAILED_KIND, section_idx
        )
        self.assertLess(section_idx, next_idx)


if __name__ == "__main__":
    unittest.main()
