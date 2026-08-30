"""Tests for task0001: `goal` block definition in
em-workflow/references/workflow-schema.md
(feature-docs/goal-vs-spec-divergence/tasks/task0001.md).

Scope (Test Notes / C4): every assertion below scans
`em-workflow/references/workflow-schema.md` only -- this task's worktree
contains none of the sibling tasks' document edits (task0004's
question-resolution.md gate behaviour, task0007's create-spec writer
procedure).

Acceptance criteria covered:
- AC-1 (FR1): the full-structure listing carries a top-level `goal` key, and
  the document states verbatim storage with no summarizing, normalizing, or
  truncation, and no size limit.
- AC-2 (FR1): the create-spec phase orchestrator is named as the sole
  writer, extending (not duplicating) the existing Write-ownership section.
- AC-3 (FR2): the block never changes once written; a `needs_update`
  re-entry into create-spec still leaves it unchanged.
- AC-4 (FR3): the block's content is untrusted data, citing the envelope
  contract's Untrusted-Input Handling section rather than restating it.
- AC-5 (FR20, D3/D4): the key is optional; absence means "created before
  this block existed, or no source at launch"; absence is never backfilled
  from SPEC.md or REQUIREMENTS.md.
- AC-6 (NFR1): the classification gate's own behaviour is not restated here
  -- only cited by path (references/question-resolution.md).
- AC-7 (NFR5, NFR8): this module exists, is discovered by
  `python3 -m unittest discover -s tests`, imports only the standard
  library, and the full suite passes unchanged otherwise.

Extended for task0014 (goal-vs-spec-divergence rework, review round 1
finding 7223862537d2283c): the `goal` block's structural-integrity
requirement and its post-write verification.

- AC-1 (FR1): the document distinguishes the value's verbatimness from its
  serialization and requires every line of the goal -- blank lines and
  lines shaped like YAML keys, list items or document markers included --
  to be written inside the block scalar's indentation.
- AC-2 (FR1, FR3): it requires a post-write re-parse confirming the file
  parses, `goal` reads back as one scalar equal to the launch-time
  description, and every other key/value is unchanged from the intended
  content.
- AC-3 (FR1): a failed verification results in no `goal` block being
  written -- the existing optional-absence state -- and in the failure
  being reported, never in a partially written or unverified block.
- AC-4 (FR2): the pre-existing verbatim, immutability and optionality
  statements remain present and unweakened (retention pin).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-schema.md"

GOAL_BLOCK_HEADING = "## `goal` block"
WRITE_OWNERSHIP_HEADING = "## Write ownership"


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-collapsed rendering so phrase assertions are insensitive
    to Markdown line-wrapping (matches tests/test_question_resolution_doc.py
    convention)."""
    return re.sub(r"\s+", " ", text)


def _first_yaml_fence(text):
    """The (single) ```yaml fenced block in workflow-schema.md -- the
    "Full structure" listing."""
    match = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise AssertionError("no ```yaml fenced block found in the given text")
    return match.group(1)


def _section(text, heading):
    """Content from `heading` (exclusive of the heading line itself) up to
    the next level-2 (`## `) heading, or end of text if there is none.

    `heading` is matched only at the START of a line -- a prose mention of
    the same heading text elsewhere (e.g. a "(see ... below)" cross-
    reference) is not the section boundary."""
    match = re.search(r"(?m)^" + re.escape(heading), text)
    if not match:
        raise ValueError(f"heading {heading!r} not found at line start")
    start = match.end()
    next_idx = text.find("\n## ", start)
    return text[start:] if next_idx == -1 else text[start:next_idx]


class TestFullStructureListingCarriesGoalKey(unittest.TestCase):
    """AC-1 (part 1): the full-structure listing carries a top-level `goal`
    key -- not merely somewhere in the document."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.yaml_block = _first_yaml_fence(cls.text)

    def test_full_structure_yaml_block_is_located_and_nonempty(self):
        # Non-vacuity guard: prove the fenced block found really is the
        # full-structure listing, not an empty or unrelated fence.
        self.assertGreater(len(self.yaml_block), 500)
        self.assertIn("schema_version", self.yaml_block)
        self.assertIn("tasks:", self.yaml_block)

    def test_goal_key_present_as_a_top_level_sibling(self):
        # Top-level keys carry zero leading whitespace; a nested field named
        # "goal" somewhere else would not match this anchored pattern.
        self.assertRegex(self.yaml_block, r"(?m)^goal:")

    def test_matcher_fails_on_a_synthetic_block_without_the_key(self):
        sample = (
            "schema_version: 1\n"
            "feature: x\n"
            "created: 2026-01-01\n"
            "tasks:\n"
            "  task0001:\n"
            "    files: []\n"
        )
        self.assertNotRegex(sample, r"(?m)^goal:")


class TestGoalBlockSectionExtractionIsScoped(unittest.TestCase):
    """Proof the section-scoping helper used below works, can fail
    meaningfully (tdd-testing discipline), and is not fooled by an
    unrelated occurrence of a keyword elsewhere in the document (Test
    Notes edge case: the "verbatim" matcher must not be satisfied by an
    unrelated occurrence elsewhere)."""

    def test_extraction_excludes_an_unrelated_earlier_occurrence(self):
        sample = (
            "## Earlier section\n"
            "This mentions verbatim in a place that is not the goal block.\n"
            "## `goal` block\n"
            "The goal content here never uses that word.\n"
            "## Later section\n"
            "more text\n"
        )
        section = _section(sample, GOAL_BLOCK_HEADING)
        self.assertNotIn("verbatim", section)
        self.assertIn("never uses that word", section)

    def test_extraction_stops_before_the_next_heading(self):
        sample = "## `goal` block\ncontent here\n## Next\nunrelated content\n"
        section = _section(sample, GOAL_BLOCK_HEADING)
        self.assertIn("content here", section)
        self.assertNotIn("unrelated content", section)


class TestVerbatimStorageWording(unittest.TestCase):
    """AC-1 (part 2): the value is the launch-time task description stored
    verbatim, with no summarizing, normalizing or truncation, and no size
    limit."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_goal_block_section_present_and_nonempty(self):
        self.assertIn(GOAL_BLOCK_HEADING, self.text)
        self.assertGreater(len(self.section.strip()), 50)

    def test_states_launch_time_task_description(self):
        self.assertIn("launch-time task description", self.norm)

    def test_states_verbatim_storage(self):
        self.assertIn("verbatim", self.section)

    def test_states_no_summarizing_normalizing_or_truncation(self):
        lowered = self.section.lower()
        self.assertIn("summariz", lowered)
        self.assertIn("normaliz", lowered)
        self.assertIn("truncat", lowered)

    def test_states_no_size_limit(self):
        self.assertIn("no size limit", self.norm.lower())

    def test_matcher_fails_on_synthetic_section_missing_the_statements(self):
        sample_section = "The value is a short label with no further rules."
        lowered = sample_section.lower()
        self.assertNotIn("verbatim", sample_section)
        self.assertNotIn("summariz", lowered)
        self.assertNotIn("no size limit", lowered)


class TestSingleWriterOwnership(unittest.TestCase):
    """AC-2: the create-spec phase orchestrator is named as the only
    writer, consistent with (an extension of) the existing Write-ownership
    section -- not a second, separate statement."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, WRITE_OWNERSHIP_HEADING)
        cls.norm = _norm(cls.section)

    def test_write_ownership_section_present_and_nonempty(self):
        self.assertIn(WRITE_OWNERSHIP_HEADING, self.text)
        self.assertGreater(len(self.section.strip()), 50)

    def test_states_create_spec_orchestrator_writes_the_goal_block_once(self):
        self.assertIn("goal", self.section.lower())
        self.assertIn("create-spec phase orchestrator", self.section)
        self.assertIn("once", self.section)

    def test_existing_no_worker_writes_statement_is_retained(self):
        # Guard preservation (C5): editing this section to add the goal
        # rule must not weaken or remove the pre-existing single-writer
        # sentence for workflow.yaml as a whole.
        self.assertIn(
            "Only the orchestrator (the `/em-workflow:develop` main "
            "session) writes workflow.yaml.",
            self.norm,
        )

    def test_matcher_fails_on_synthetic_section_without_the_statement(self):
        sample = (
            "## Write ownership\n"
            "Some unrelated ownership text about a different file.\n"
            "## Full structure\n"
            "more\n"
        )
        section = _section(sample, WRITE_OWNERSHIP_HEADING)
        self.assertNotIn("create-spec phase orchestrator", section)


class TestImmutability(unittest.TestCase):
    """AC-3: the block is never changed after it is written; the
    create-spec `needs_update` re-entry still leaves it unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_states_value_never_changes_once_written(self):
        lowered = self.norm.lower()
        self.assertIn("once written", lowered)
        self.assertIn("never changes", lowered)

    def test_needs_update_reentry_leaves_it_unchanged(self):
        self.assertIn("needs_update", self.section)
        self.assertIn("as-is", self.norm.lower())

    def test_matcher_fails_on_synthetic_section_missing_the_statement(self):
        sample_section = "The value may be updated whenever needed."
        self.assertNotIn("needs_update", sample_section)
        self.assertNotIn("never changes", sample_section.lower())


class TestUntrustedReadCitation(unittest.TestCase):
    """AC-4: readers treat the content as untrusted data, never as
    instructions, by citing the envelope's Untrusted-Input Handling section
    rather than re-deriving the rule (C7)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_cites_worker_envelope_untrusted_input_handling_section(self):
        self.assertIn("references/contracts/worker-envelope.md", self.section)
        self.assertIn("Untrusted-Input Handling", self.section)

    def test_states_data_to_analyse_never_instructions_to_follow(self):
        lowered = self.norm.lower()
        self.assertIn("data to analy", lowered)
        self.assertIn("instructions to follow", lowered)

    def test_does_not_re_derive_the_envelope_injection_rule(self):
        # Cite, never restate (C2/C7): the envelope's own injection-detection
        # wording is not duplicated here.
        self.assertNotIn("role overrides", self.section)
        self.assertNotIn("ignore previous instructions", self.section)

    def test_matcher_fails_on_synthetic_section_without_the_citation(self):
        sample_section = "This content should be handled with care."
        self.assertNotIn("worker-envelope.md", sample_section)


class TestOptionalityAndAbsenceSemantics(unittest.TestCase):
    """AC-5: the key is optional; absence means "created before this block
    existed, or no source at launch"; absence is never backfilled from
    SPEC.md or REQUIREMENTS.md."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_states_the_key_is_optional(self):
        self.assertIn("OPTIONAL", self.section)

    def test_states_the_absence_meaning(self):
        self.assertIn("created before this block existed", self.norm)
        self.assertIn("no source for the goal at launch", self.norm)

    def test_states_no_backfill_from_spec_or_requirements(self):
        self.assertIn("SPEC.md", self.section)
        self.assertIn("REQUIREMENTS.md", self.section)
        self.assertIn("never repaired", self.norm.lower())

    def test_matcher_fails_on_synthetic_section_missing_the_absence_rule(self):
        sample_section = "The key is always present in every feature."
        self.assertNotIn("SPEC.md", sample_section)
        self.assertNotIn("created before this block existed", sample_section)


class TestClassificationGateNotRestated(unittest.TestCase):
    """AC-6: the document does not restate the classification gate's own
    behaviour; it refers to references/question-resolution.md by path for
    what absence implies at the gate."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)

    def test_cites_question_resolution_by_path(self):
        self.assertIn("references/question-resolution.md", self.section)

    def test_does_not_restate_the_gates_own_verdict_vocabulary(self):
        # This vocabulary belongs to the classification audit record
        # (IMPLEMENTATION.md Shared Components row 2, owned by task0004/
        # task0005); its total absence from workflow-schema.md is the
        # observable proof this document doesn't restate the gate's own
        # behaviour.
        for term in ("goal_not_met", "spec_gap", "not_applicable", "evidence_ids"):
            self.assertNotIn(term, self.text)

    def test_matcher_fails_on_synthetic_text_with_restated_vocabulary(self):
        sample = "the gate returns verdict: spec_gap when evidence_ids is non-empty"
        self.assertIn("spec_gap", sample)


class TestSerializationDistinctionAndIndentation(unittest.TestCase):
    """task0014 AC-1: verbatimness constrains the VALUE, not the
    serialization; every line of the value -- blank lines and lines shaped
    like a YAML key, a list item, or a document marker included -- must be
    written inside the block scalar's indentation."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_goal_block_section_located_and_nonempty(self):
        # Non-vacuity guard (Test Notes): the region must be located and
        # non-empty before any content assertion below means anything.
        self.assertGreater(len(self.section.strip()), 50)

    def test_states_verbatimness_constrains_value_not_serialization(self):
        self.assertIn("constrains the value, not the serialization", self.norm)

    def test_requires_every_line_inside_the_indentation(self):
        lowered = self.norm.lower()
        self.assertIn("blank line", lowered)
        self.assertIn("yaml key", lowered)
        self.assertIn("list item", lowered)
        self.assertIn("document marker", lowered)
        self.assertIn("block scalar's indentation", lowered)

    def test_states_indentation_is_not_normalization_of_the_value(self):
        self.assertIn(
            "not normalization of the value",
            self.norm,
        )

    def test_matcher_fails_on_synthetic_section_missing_indentation_statement(self):
        # Negative proof (Test Notes): a section that requires verbatim
        # storage but says nothing about indentation must fail.
        sample_section = (
            "The value is stored verbatim as a YAML block scalar: no "
            "summarizing, normalizing, or truncation is applied, and no "
            "size limit exists."
        )
        lowered = sample_section.lower()
        self.assertNotIn("blank line", lowered)
        self.assertNotIn("document marker", lowered)
        self.assertNotIn("block scalar's indentation", lowered)


class TestPostWriteVerification(unittest.TestCase):
    """task0014 AC-2: after writing workflow.yaml, the written file is
    re-parsed and checked before the write is accepted -- stated as a
    required step, not advice."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_goal_block_section_located_and_nonempty(self):
        self.assertGreater(len(self.section.strip()), 50)

    def test_requires_reparse_after_write(self):
        self.assertIn("re-parsed", self.norm.lower())

    def test_requires_file_parses(self):
        self.assertIn("the file parses", self.norm.lower())

    def test_requires_goal_reads_back_as_single_scalar_equal_to_description(self):
        self.assertIn(
            "reads back as a single scalar equal to the launch-time "
            "description",
            self.norm,
        )

    def test_requires_every_other_key_and_value_unchanged(self):
        self.assertIn(
            "every other top-level key and value in the file matches the "
            "content that was intended to be written",
            self.norm,
        )

    def test_states_required_not_advisory(self):
        self.assertIn("required, not advisory", self.norm)

    def test_matcher_fails_on_synthetic_section_missing_reparse_statement(self):
        # Negative proof (Test Notes): a section that says nothing about
        # re-parsing must fail.
        sample_section = (
            "The value is stored verbatim as a YAML block scalar. Once "
            "written, it is trusted to be correct."
        )
        lowered = sample_section.lower()
        self.assertNotIn("re-parsed", lowered)
        self.assertNotIn("reads back as a single scalar", lowered)


class TestFailureOutcome(unittest.TestCase):
    """task0014 AC-3: a failed post-write verification means the `goal`
    block is NOT written -- the existing optional-absence state -- and the
    failure is reported; never a partially written or unverified block."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.section = _section(cls.text, GOAL_BLOCK_HEADING)
        cls.norm = _norm(cls.section)

    def test_goal_block_section_located_and_nonempty(self):
        self.assertGreater(len(self.section.strip()), 50)

    def test_failed_verification_means_block_not_written(self):
        self.assertIn("block is NOT written", self.section)

    def test_failure_outcome_is_the_existing_optional_absence_state(self):
        self.assertIn("optional-absence state", self.norm)

    def test_failure_is_reported(self):
        self.assertIn("the failure is reported", self.norm.lower())

    def test_never_a_partially_written_or_unverified_block(self):
        self.assertIn("partially written or unverified", self.norm.lower())
        self.assertIn("never left behind", self.norm.lower())

    def test_matcher_fails_on_synthetic_section_missing_failure_outcome(self):
        sample_section = (
            "The value is stored verbatim as a YAML block scalar and is "
            "written unconditionally."
        )
        lowered = sample_section.lower()
        self.assertNotIn("block is not written", lowered)
        self.assertNotIn("partially written or unverified", lowered)


class TestGoalBlockTestModuleIsStdlibOnly(unittest.TestCase):
    """AC-7: tests/test_goal_block_schema.py imports only the standard
    library (NFR5)."""

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


if __name__ == "__main__":
    unittest.main()
