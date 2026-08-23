"""Tests for task0002: em-workflow/references/workflow-patch.md.

Covers task0002 Acceptance Criteria (feature-docs/agent-separation/
tasks/task0002.md):

- AC-1: the doc exists and documents both operations with the
  operation/mode/target/issuer matrix from design-input.md 5.5.
- AC-2: tasks_patch, including replace_all permission conditions and the
  append provenance / expected_next_task_id requirements.
- AC-3: step_patches addressed by step_id, only `status` settable,
  base_commit / completed_at_commit not worker-settable.
- AC-4: the complete preserve path vocabulary and per-operation mandatory
  sets, including workflow.implement.base_commit for append_rework.
- AC-5: all sixteen application rules, ordered, including single-write
  application and the rule R2 commit sequence.
- AC-6: project / review summary block are orchestrator-updated and
  absent from worker patches; domains SSOT is review-rules.yaml.

This is a documentation task (Test Notes: "Verified structurally"), so these
are structural/textual assertions over the Markdown, not behavioral tests of
running code. Per the Test Notes, the expected vocabularies/counts are
derived by parsing design-input.md 5.5 rather than hard-coded, so this test
does not become a second, independently-drifting copy of the same table
(NFR6 applies to tests too).

task0003 (feature-docs/create-plan-status-conflict/tasks/task0003.md) adds
TestReplaceAllPermissionConditionsPinned below, covering that task's AC-2:
the `replace_all` permission-conditions section is pinned precisely (exactly
two permitted create-plan entry statuses, the tasks-empty-or-all-pending
floor, application rule 5 still pointing at the section) so an accidental
future relaxation of `workflow-patch.md` -- which this feature's D1 requires
to stay byte-identical -- fails loudly. Scoped to the permission-conditions
section and the application-rule list so an occurrence of the same words
elsewhere in the document cannot satisfy them.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_INPUT_PATH = (
    REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"
)
DOC_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


class DesignInputFixture:
    """Derives the expected vocabularies/counts from design-input.md 5.5."""

    def __init__(self):
        full = _read(DESIGN_INPUT_PATH)
        self.section = _extract_section(
            full, "### 5.5 workflow patch", "### 5.6 phase-state"
        )

    def operation_mode_pairs(self):
        pairs = re.findall(
            r"`(replace_planning|append_rework)`\s*\|\s*`(replace_all|append)`",
            self.section,
        )
        assert pairs, "expected to find the operation/mode matrix rows"
        return pairs

    def preserve_vocabulary(self):
        match = re.search(r"許可語彙:\n\n((?:- `[^\n]+`\n)+)", self.section)
        assert match, "expected the preserve permitted-vocabulary bullet list"
        return re.findall(r"`([^`]+)`", match.group(1))

    def application_rules(self):
        rules_section = _extract_section(
            self.section, "#### 5.5.5 適用規則", "#### 5.5.6 domains"
        )
        rules = re.findall(r"^(\d+)\. (.+)$", rules_section, re.MULTILINE)
        assert rules, "expected the numbered application rules list"
        return rules

    def append_rework_mandatory_preserve(self):
        # Scope to 5.5.4 specifically -- `append_rework` also appears in the
        # earlier 5.5 operation/mode matrix row (bound to mode `append`),
        # which an unscoped search would match first.
        mandatory_section = _extract_section(
            self.section, "#### 5.5.4 preserve", "#### 5.5.5 適用規則"
        )
        match = re.search(
            r"\| `append_rework` \| (`[^`]+`) \|", mandatory_section
        )
        assert match, "expected the mandatory-preserve-per-operation table row"
        return re.findall(r"`([^`]+)`", match.group(1))


class TestWorkflowPatchDocExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(DOC_PATH.is_file(), f"{DOC_PATH} must exist (AC-1)")


class TestOperationModeMatrix(unittest.TestCase):
    """AC-1: both operations documented with their bound tasks_patch mode."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)

    def test_design_input_binds_the_two_expected_pairs(self):
        # Sanity check on the fixture itself, so a future edit to
        # design-input.md 5.5 that changes this matrix is visible here too.
        self.assertEqual(
            set(self.fixture.operation_mode_pairs()),
            {
                ("replace_planning", "replace_all"),
                ("append_rework", "append"),
            },
        )

    def test_both_operations_appear_bound_to_their_tasks_patch_mode(self):
        for operation, mode in self.fixture.operation_mode_pairs():
            row_pattern = re.compile(
                r"`%s`[^\n]*\|[^\n]*`%s`"
                % (re.escape(operation), re.escape(mode))
            )
            self.assertRegex(
                self.text,
                row_pattern,
                f"{operation} must be documented bound to tasks_patch mode "
                f"{mode} (same table row)",
            )


class TestTasksPatchContract(unittest.TestCase):
    """AC-2: tasks_patch, replace_all conditions, append provenance."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_append_provenance_and_expected_next_task_id_documented(self):
        for token in (
            "expected_next_task_id",
            "provenance",
            "source_ids",
            "review_round",
        ):
            self.assertIn(token, self.text)

    def test_replace_all_permission_conditions_section_present(self):
        section = _extract_section(
            self.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        lowered = section.lower()
        self.assertIn("empty", lowered)
        self.assertIn("pending", lowered)
        self.assertIn("create-plan", section)
        self.assertIn("needs_update", section)


class TestStepPatchesContract(unittest.TestCase):
    """AC-3: step_patches addressed by step_id, only status settable."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_addressed_by_step_id_not_array_index(self):
        self.assertIn("step_id", self.text)
        # Markdown line-wrapping may split the phrase across a line break;
        # match on whitespace (including a wrap newline), not a literal
        # single space.
        self.assertRegex(self.text.lower(), r"array[\s-]+index")

    def test_only_status_field_settable(self):
        self.assertIn("only field `set` may touch", self.text)

    def test_base_commit_and_completed_at_commit_not_worker_settable(self):
        self.assertIn("base_commit", self.text)
        self.assertIn("completed_at_commit", self.text)
        self.assertIn("NOT worker-settable", self.text)


class TestPreserveVocabulary(unittest.TestCase):
    """AC-4: complete preserve vocabulary + per-operation mandatory sets."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)

    def test_complete_preserve_vocabulary_present(self):
        vocab = self.fixture.preserve_vocabulary()
        self.assertEqual(
            len(vocab), 5, "sanity: design-input.md lists 5 preserve paths"
        )
        for path in vocab:
            self.assertIn(
                f"`{path}`", self.text, f"preserve path {path} missing"
            )

    def test_append_rework_mandatory_preserve_includes_base_commit(self):
        mandatory = self.fixture.append_rework_mandatory_preserve()
        self.assertIn("workflow.implement.base_commit", mandatory)
        self.assertIn("workflow.implement.base_commit", self.text)

    def test_no_preserve_path_outside_permitted_vocabulary(self):
        """Edge case (Test Notes): guard against an invented preserve path
        extension by scanning only the preserve section of the doc."""
        vocab = set(self.fixture.preserve_vocabulary())
        section = _extract_section(
            self.text, "## `preserve`", "## Application rules"
        )
        candidates = re.findall(r"`((?:[\w<>]+\.)+[\w<>]+)`", section)
        non_paths = {"workflow.yaml"}
        paths = [c for c in candidates if c not in non_paths]
        self.assertTrue(paths, "expected at least one preserve path token")
        for path in paths:
            self.assertIn(
                path,
                vocab,
                f"{path} is not in the permitted preserve vocabulary -- "
                "looks like an invented extension",
            )


class TestApplicationRules(unittest.TestCase):
    """AC-5: all sixteen application rules, ordered, single-write + R2."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputFixture()
        cls.text = _read(DOC_PATH)
        cls.doc_rules_section = _extract_section(
            cls.text, "## Application rules", "## Ownership boundary"
        )

    def test_rule_count_matches_design_input(self):
        design_rules = self.fixture.application_rules()
        self.assertEqual(
            len(design_rules),
            16,
            "sanity: design-input.md 5.5.5 states sixteen rules",
        )
        doc_rule_numbers = re.findall(
            r"^(\d+)\. ", self.doc_rules_section, re.MULTILINE
        )
        self.assertEqual(len(doc_rule_numbers), len(design_rules))

    def test_rules_are_ordered_one_through_sixteen(self):
        doc_rule_numbers = [
            int(n)
            for n in re.findall(r"^(\d+)\. ", self.doc_rules_section, re.MULTILINE)
        ]
        self.assertEqual(doc_rule_numbers, list(range(1, 17)))

    def test_single_write_application_rule_present(self):
        self.assertIn("single-write", self.text.lower())
        self.assertIn("Write", self.doc_rules_section)

    def test_rule_r2_commit_sequence_present(self):
        self.assertIn("R2", self.doc_rules_section)
        self.assertIn("commit", self.doc_rules_section.lower())


class TestOwnershipBoundaryAndDomainsSSOT(unittest.TestCase):
    """AC-6: project/review summary not worker-patchable; domains SSOT."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_project_and_review_summary_are_orchestrator_updated(self):
        self.assertIn("orchestrator-updated", self.text)
        self.assertIn("review summary", self.text.lower())
        self.assertIn("needs_rework", self.text)

    def test_domains_ssot_is_review_rules_yaml(self):
        self.assertIn("references/review-rules.yaml", self.text)


class TestReplaceAllPermissionConditionsPinned(unittest.TestCase):
    """task0003 AC-2: the `replace_all` permission conditions are pinned
    precisely, scoped to their own section (and, for rule 5, to the
    application-rule list) rather than to a substring match anywhere in the
    document. `workflow-patch.md` is frozen by this feature (IMPLEMENTATION.md
    D1); these assertions are the regression guard that makes a future
    relaxation of the section fail loudly instead of silently."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        cls.doc_rules_section = _extract_section(
            cls.text, "## Application rules", "## Ownership boundary"
        )

    def test_exactly_two_create_plan_entry_statuses_are_permitted(self):
        statuses = re.findall(
            r"the `create-plan` step is `([a-z_]+)`", self.section
        )
        self.assertEqual(
            set(statuses),
            {"pending", "needs_update"},
            "the permitted create-plan entry statuses must be exactly "
            "pending and needs_update",
        )
        self.assertEqual(
            len(statuses),
            2,
            "no third create-plan entry status may be listed as permitted",
        )

    def test_tasks_empty_or_all_pending_condition_still_required(self):
        # The security floor (5.5.1's first condition): must not silently
        # widen or disappear.
        self.assertIn("`tasks` is empty", self.section)
        self.assertRegex(
            self.section,
            r"every existing task's `status` is `pending`",
        )

    def test_application_rule_5_still_refers_to_the_permission_conditions(self):
        match = re.search(
            r"^5\. (.*?)(?=^\d+\. )",
            self.doc_rules_section,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(match, "expected application rule 5 to exist")
        rule_text = match.group(1)
        self.assertIn("replace_all", rule_text)
        self.assertIn("permission conditions", rule_text.lower())

    def test_floor_condition_is_scoped_to_the_initial_planning_path(self):
        # task0002 AC-1: the tasks-empty-or-all-pending floor is stated
        # inside the initial-planning path's own bullet, not as a
        # blanket condition covering both paths.
        start = self.section.index("Initial-planning path")
        end = self.section.index("Re-planning path", start)
        initial_bullet = self.section[start:end]
        self.assertIn("`tasks` is empty", initial_bullet)
        self.assertRegex(
            initial_bullet, r"every existing task's `status` is `pending`"
        )

    def test_needs_update_path_explicitly_permits_merged_tasks(self):
        # task0002 AC-2: merged tasks no longer block replace_all when
        # create-plan is needs_update.
        start = self.section.index("Re-planning path")
        end = self.section.index("A `replace_all` received", start)
        replanning_bullet = self.section[start:end]
        self.assertIn("merged", replanning_bullet)

    def test_protocol_error_sentence_no_longer_lists_merged(self):
        # task0002 AC-3: in_progress / failed remain a protocol error on
        # both paths; merged must not be listed there any more (it is
        # explicitly permitted on the re-planning path instead).
        match = re.search(
            r"A `replace_all` received.*?protocol error[^\n]*\.",
            self.section,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "expected the protocol-error sentence")
        sentence = match.group(0)
        self.assertIn("in_progress", sentence)
        self.assertIn("failed", sentence)
        self.assertNotIn("merged", sentence)


# task0002: the wording that ANDed the task-state floor with either
# create-plan path -- making the floor apply unconditionally to both paths
# -- is superseded and must not remain anywhere in the document (AC-4).
OLD_BLANKET_CONDITION_PATTERN = re.compile(
    r"ALL of the following hold.*?"
    r"`tasks` is empty, OR every existing task's `status` is `pending`.*?"
    r"AND, additionally, one of:",
    re.DOTALL,
)


class TestSupersededBlanketConditionRemoved(unittest.TestCase):
    """task0002 AC-4: the superseded blanket condition ('every existing
    task must be `pending`' as an unconditional requirement of both paths)
    must not remain anywhere in the document."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)

    def test_pattern_trips_on_a_synthetic_sample_of_the_old_wording(self):
        # Non-vacuity guard: prove the pattern can match something, so the
        # absence assertion below is not vacuously true.
        synthetic = (
            "`replace_all` is permitted ONLY when ALL of the following "
            "hold; otherwise the patch is rejected:\n\n"
            "- `tasks` is empty, OR every existing task's `status` is "
            "`pending`\n"
            "- AND, additionally, one of:\n"
            "  - the `create-plan` step is `pending` (first planning "
            "pass), OR\n"
            "  - the `create-plan` step is `needs_update` (an explicit "
            "re-plan)\n"
        )
        self.assertRegex(synthetic, OLD_BLANKET_CONDITION_PATTERN)

    def test_superseded_blanket_condition_absent_from_document(self):
        self.assertNotRegex(self.text, OLD_BLANKET_CONDITION_PATTERN)


class TestBaseCommitPreservedOnReplanningPath(unittest.TestCase):
    """task0002 AC-5: workflow.implement.base_commit is preserved on the
    re-planning path, stated consistently with the rework invariant that a
    rework patch never changes base_commit."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )

    def test_base_commit_mentioned_within_permission_conditions_section(self):
        self.assertIn("workflow.implement.base_commit", self.section)
        self.assertIn("`preserve`", self.section)

    def test_consistency_with_rework_invariant_is_stated(self):
        lowered = self.section.lower()
        self.assertIn("does not contradict", lowered)
        self.assertIn("rework invariant", lowered)


class TestReplanningPathWidenedForSpecChangeReentry(unittest.TestCase):
    """task0013 AC-1 (FR4, FR6): the Re-planning path is satisfied by the
    state the SPEC-change transition actually produces (`create-plan:
    pending` after a `create-spec: needs_update` re-entry), names the
    recognizable signal for that case, and still admits the unchanged
    `create-plan: needs_update` case. The transition documents themselves
    (`rework-task-synthesis.md` Section 10, the two documents citing it)
    are not modified by this task (AC-3) -- verified separately by this
    task's own file-set discipline, not by an assertion here (Test Notes:
    cross-document agreement is a verify-phase item)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        cls.normalized = re.sub(r"\s+", " ", cls.section)

    def test_needs_update_case_still_present(self):
        self.assertIn(
            "the `create-plan` step is `needs_update`", self.normalized
        )

    def test_pending_reentry_case_states_recognizable_signal(self):
        self.assertIn(
            "a `spec_change` record present in `phase-state/rework.yaml`",
            self.normalized,
        )
        self.assertIn(
            "`workflow.implement.base_commit` already being set",
            self.normalized,
        )

    def test_states_transition_produces_pending_not_needs_update(self):
        self.assertIn(
            "sets `create-plan` to `pending`, not `needs_update`",
            self.normalized,
        )
        self.assertIn("rework-task-synthesis.md", self.normalized)

    def test_new_case_matcher_fails_on_needs_update_only_wording(self):
        # Non-vacuity / negative proof (Test Notes): a Re-planning path
        # stated only as `create-plan: needs_update` -- the pre-task0013
        # wording -- must not satisfy the widened matcher above.
        synthetic_old_wording = (
            "- **Re-planning path** -- the `create-plan` step is "
            "`needs_update` (an explicit re-plan, e.g. the SPEC-change "
            "transition): permitted regardless of task status, including "
            "existing `merged` tasks."
        )
        self.assertNotIn(
            "a `spec_change` record present in `phase-state/rework.yaml`",
            synthetic_old_wording,
        )
        self.assertNotIn(
            "`workflow.implement.base_commit` already being set",
            synthetic_old_wording,
        )


class TestUnchangedHalvesStatedExplicitly(unittest.TestCase):
    """task0013 AC-2 (FR4): the Initial-planning path's condition and the
    `in_progress` / `failed` protocol error are stated as unchanged by the
    Re-planning path's widening, on both paths."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### `replace_all` permission conditions",
            "### `append` requirements",
        )
        cls.normalized = re.sub(r"\s+", " ", cls.section)

    def test_unchanged_statement_present(self):
        self.assertIn(
            "Neither this protocol-error rule nor the Initial-planning "
            "path's floor condition above changes",
            self.normalized,
        )

    def test_referenced_halves_still_present(self):
        # Retention: both halves the "unchanged" sentence refers to.
        self.assertIn("`tasks` is empty", self.normalized)
        self.assertIn("in_progress", self.normalized)
        self.assertIn("protocol error", self.normalized)

    def test_unchanged_statement_matcher_fails_on_pre_change_wording(self):
        # Negative proof: the pre-task0013 protocol-error sentence had no
        # such explicit "unchanged" statement at all.
        synthetic_old_wording = (
            "A `replace_all` received while any task is `in_progress` or "
            "`failed` is a protocol error on BOTH paths above."
        )
        self.assertNotIn(
            "Neither this protocol-error rule nor the Initial-planning "
            "path's floor condition above changes",
            synthetic_old_wording,
        )


class TestReplanningTaskIdAllocationRule(unittest.TestCase):
    """task0013 AC-4: a `replace_all` re-planning pass never re-issues a
    task id the feature has already used, and allocates above the highest
    previously registered id."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### Re-planning task-id allocation",
            "### `append` requirements",
        )
        cls.normalized = re.sub(r"\s+", " ", cls.section)

    def test_allocates_above_highest_registered_id(self):
        self.assertIn(
            "allocates its new task ids continuing ABOVE the highest",
            self.normalized,
        )
        self.assertIn("the feature has ever registered", self.normalized)

    def test_retired_id_never_reissued(self):
        self.assertIn(
            "is never re-issued to a different task", self.normalized
        )

    def test_allocation_matcher_fails_on_reissuing_wording(self):
        # Negative proof (Test Notes): an allocation sentence that permits
        # re-issuing an id must fail this matcher.
        synthetic_permissive_wording = (
            "A re-planning pass may reuse any task id below "
            "`next_task_id`, including a retired one, as long as its "
            "content is replaced."
        )
        self.assertNotIn(
            "is never re-issued to a different task",
            synthetic_permissive_wording,
        )
        self.assertNotIn("ABOVE the highest", synthetic_permissive_wording)


class TestMandatoryPreserveReplanningRowRequiresBaseCommit(unittest.TestCase):
    """task0013 AC-6 (FR5): the Mandatory `preserve` table's
    `replace_planning` row requires `workflow.implement.base_commit` on the
    Re-planning path, states the Initial-planning (first-pass) case
    explicitly, and no longer reads `(none)`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DOC_PATH)
        cls.section = _extract_section(
            cls.text,
            "### Mandatory `preserve` per operation",
            "## Application rules",
        )
        cls.normalized = re.sub(r"\s+", " ", cls.section)

    def test_row_no_longer_reads_none(self):
        self.assertNotRegex(
            self.normalized, r"\| `replace_planning` \| \(none\) \|"
        )

    def test_row_requires_base_commit_on_replanning_path(self):
        match = re.search(
            r"\| `replace_planning` \| (.*?) \|", self.normalized
        )
        self.assertIsNotNone(match, "expected the replace_planning row")
        row = match.group(1)
        self.assertIn("workflow.implement.base_commit", row)
        self.assertIn("Re-planning path", row)

    def test_initial_planning_case_stated(self):
        self.assertIn(
            "Initial-planning path has no `implement` base commit yet",
            self.normalized,
        )

    def test_row_matcher_fails_on_none_wording(self):
        # Negative proof: a preserve row reading `(none)` must fail.
        synthetic_old_row = "| `replace_planning` | (none) |"
        self.assertRegex(
            synthetic_old_row, r"\| `replace_planning` \| \(none\) \|"
        )
        self.assertNotIn("workflow.implement.base_commit", synthetic_old_row)


if __name__ == "__main__":
    unittest.main()
