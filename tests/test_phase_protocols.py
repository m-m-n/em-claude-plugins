"""Tests for task0011: the create-spec and create-plan phase protocols, and
the scope verification procedure they share.

Covers task0011 Acceptance Criteria (feature-docs/agent-separation/tasks/
task0011.md):

- AC-1: both phase documents exist and contain every numbered section listed
  for them in design-input.md 5.7 / 5.8, in the same order.
- AC-2: create-spec-phase.md states the worktree is created immediately
  after the feature name is fixed, and that every answer is persisted
  before the worker is re-dispatched.
- AC-3: create-spec-phase.md states the termination conditions (no fixed
  round limit), the progress-fingerprint stop conditions, the three-way
  stalled gate, and the prohibition on automatically converting an
  unresolved item into an assumption.
- AC-4: create-spec-phase.md states that design-system determination runs
  even when the design step is skipped, with the zero-candidate exception.
- AC-5: create-plan-phase.md states the preconditions including the
  design-system cross-product check and its in-place reclassification
  branch that leaves the step status unchanged.
- AC-6: the scope verification procedure states the clean-worktree
  precondition with no automatic cleaning, computes the change set from the
  index and working tree only, and orders the post-dispatch steps with the
  change-set computation before the HEAD evaluation, giving the reason.
- AC-7: the scope verification procedure states the path normalization,
  containment, symlink and case rules, and the abort when the trash tool is
  unavailable.

These deliverables are orchestrator procedure documents (Markdown), not
executable code, so verification is structural/textual against the rendered
documents. Per the task's Test Notes, the expected section vocabulary is
parsed out of design-input.md itself (not hand-copied here) so a document
that drifts from the design fails these tests.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
FEATURE_DOCS = REPO_ROOT / "feature-docs" / "agent-separation"

CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
DESIGN_INPUT_PATH = FEATURE_DOCS / "design-input.md"

SECTION_HEADING_RE = re.compile(r"^(\d+a?)\.\s+\*\*([^*]+)\*\*", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _design_text():
    return _read(DESIGN_INPUT_PATH)


def _toc_sections(design_text, start_marker, end_marker):
    """Parse the numbered, bold-titled table-of-contents items out of a
    design-input.md phase section (e.g. "1. **Purpose and ownership**"),
    returning an ordered list of (number, title) tuples."""
    section = _slice(design_text, start_marker, end_marker)
    items = [(m.group(1), m.group(2).strip()) for m in SECTION_HEADING_RE.finditer(section)]
    return items


def _first_index(text, needle):
    idx = text.find(needle)
    if idx == -1:
        raise AssertionError(f"expected to find {needle!r} in document")
    return idx


class TestDesignInputSelfCheck(unittest.TestCase):
    """Sanity check on the TOC parser itself, so a broken parser cannot make
    the section-coverage assertions vacuously pass."""

    def test_5_7_yields_the_expected_item_count(self):
        design_text = _design_text()
        items = _toc_sections(
            design_text, "### 5.7 create-spec", "### 5.8 create-plan"
        )
        # 1..13 plus 11a
        self.assertEqual(len(items), 14)
        self.assertEqual(items[0], ("1", "Purpose and ownership"))
        self.assertEqual(items[-1], ("13", "Completion"))
        self.assertIn(("11a", "design system の確定"), items)

    def test_5_8_yields_the_expected_item_count(self):
        design_text = _design_text()
        items = _toc_sections(
            design_text, "### 5.8 create-plan", "### 5.9 question"
        )
        self.assertEqual(len(items), 11)
        self.assertEqual(items[0], ("1", "Purpose and ownership"))
        self.assertEqual(items[-1], ("11", "Completion or failure"))


class TestFilesExist(unittest.TestCase):
    def test_create_spec_phase_doc_exists(self):
        self.assertTrue(
            CREATE_SPEC_PATH.is_file(), f"expected {CREATE_SPEC_PATH} to exist"
        )

    def test_create_plan_phase_doc_exists(self):
        self.assertTrue(
            CREATE_PLAN_PATH.is_file(), f"expected {CREATE_PLAN_PATH} to exist"
        )


class TestCreateSpecSectionCoverageAndOrder(unittest.TestCase):
    """AC-1: create-spec-phase.md contains every section listed in
    design-input.md 5.7, in order."""

    # Section 11a's design-input.md title is Japanese ("design system の確定");
    # the rendered corpus is English for structural documents, so this one
    # entry is translated rather than located by literal substring. Every
    # other title below is asserted against the verbatim design-input.md
    # text.
    SECTION_11A_ENGLISH_MARKER = "Design-system determination"

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)
        design_text = _design_text()
        cls.items = _toc_sections(
            design_text, "### 5.7 create-spec", "### 5.8 create-plan"
        )

    def test_every_section_title_present(self):
        for number, title in self.items:
            if number == "11a":
                self.assertIn(
                    self.SECTION_11A_ENGLISH_MARKER,
                    self.text,
                    "expected an English rendering of design-input.md's "
                    "section 11a (design system determination)",
                )
                continue
            self.assertIn(
                title,
                self.text,
                f"create-spec-phase.md is missing section {number} {title!r}",
            )

    def test_sections_appear_in_design_order(self):
        positions = []
        for number, title in self.items:
            marker = (
                self.SECTION_11A_ENGLISH_MARKER if number == "11a" else title
            )
            positions.append(_first_index(self.text, marker))
        self.assertEqual(
            positions,
            sorted(positions),
            "create-spec-phase.md sections are out of order relative to "
            "design-input.md 5.7",
        )


class TestCreatePlanSectionCoverageAndOrder(unittest.TestCase):
    """AC-1: create-plan-phase.md contains every section listed in
    design-input.md 5.8, in order."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)
        design_text = _design_text()
        cls.items = _toc_sections(
            design_text, "### 5.8 create-plan", "### 5.9 question"
        )

    def test_every_section_title_present(self):
        for number, title in self.items:
            self.assertIn(
                title,
                self.text,
                f"create-plan-phase.md is missing section {number} {title!r}",
            )

    def test_sections_appear_in_design_order(self):
        positions = [_first_index(self.text, title) for _, title in self.items]
        self.assertEqual(
            positions,
            sorted(positions),
            "create-plan-phase.md sections are out of order relative to "
            "design-input.md 5.8",
        )


class TestCreateSpecBootstrapAndPersistence(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_worktree_created_immediately_after_feature_name_fixed(self):
        lowered = self.text.lower()
        self.assertIn("immediately after the feature name is fixed", lowered)
        self.assertIn("worktree", lowered)

    def test_every_answer_persisted_before_redispatch(self):
        lowered = self.text.lower()
        self.assertIn("persisted", lowered)
        self.assertIn("before", lowered)
        self.assertIn("re-dispatch", lowered)


class TestCreateSpecTerminationAndLoopStop(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_no_fixed_round_limit(self):
        self.assertIn("no fixed round limit", self.text.lower())

    def test_progress_fingerprint_stop_conditions(self):
        self.assertIn("progress_fingerprint", self.text)
        # The three concrete stop triggers named in design-input.md 5.7.
        self.assertIn("regenerated", self.text.lower())
        self.assertIn(
            "unchanged across two consecutive dispatches", self.text.lower()
        )

    def test_three_way_stalled_gate(self):
        self.assertIn("create-spec.stalled", self.text)
        lowered = self.text.lower()
        self.assertIn("continue", lowered)
        self.assertIn("tbd", lowered)
        self.assertIn("abort", lowered)

    def test_automatic_assumption_conversion_prohibited(self):
        self.assertIn(
            "MUST NOT automatically convert",
            self.text,
        )
        self.assertIn("explicitly select", self.text.lower())


class TestCreateSpecDesignSystemDetermination(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_runs_even_when_design_is_skipped(self):
        lowered = self.text.lower()
        self.assertIn("must run even when", lowered)
        self.assertIn("skipped", lowered)

    def test_zero_candidate_exception_stated(self):
        lowered = self.text.lower()
        self.assertIn("zero", lowered)
        self.assertIn("design_system_candidates", self.text)
        self.assertIn("kind: none", lowered)
        self.assertIn("without asking", lowered)


class TestCreatePlanPreconditions(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_design_system_cross_product_check_precondition(self):
        self.assertIn("project.design_system", self.text)
        lowered = self.text.lower()
        self.assertIn("cross-product", lowered)

    def test_reclassification_branch_leaves_step_status_unchanged(self):
        self.assertIn("design-system.reclassify", self.text)
        lowered = self.text.lower()
        self.assertIn("without changing", lowered)
        self.assertIn("status", lowered)
        self.assertIn("restart", lowered)


class TestScopeVerificationOwnershipAndReference(unittest.TestCase):
    """Scope verification is owned once, in create-spec-phase.md, and
    referenced (not duplicated) from create-plan-phase.md."""

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_create_spec_owns_the_scope_verification_section(self):
        self.assertIn("Scope verification", self.spec_text)

    def test_create_plan_references_it_by_path_not_duplicate(self):
        self.assertIn("create-spec-phase.md", self.plan_text)
        # The create-plan document must not restate the snapshot mechanics
        # that belong to the owning section.
        self.assertNotIn("git hash-object", self.plan_text)
        self.assertNotIn("gio trash", self.plan_text)


class TestScopeVerificationCleanPreconditionAndChangeSet(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_clean_worktree_precondition_no_automatic_cleaning(self):
        lowered = self.text.lower()
        self.assertIn("clean", lowered)
        self.assertIn("abort without dispatching", lowered)
        self.assertIn("never force-clean", lowered)

    def test_change_set_from_index_and_working_tree_only(self):
        self.assertIn("index + working tree", self.text)
        self.assertIn(
            "HEAD layer is",
            self.text,
        )
        self.assertIn("never", self.text.lower())

    def test_post_dispatch_order_change_set_before_head_and_reason(self):
        change_set_idx = _first_index(
            self.text, "Compute the worker's change set"
        )
        head_move_idx = _first_index(
            self.text, "Evaluate whether HEAD moved"
        )
        self.assertLess(
            change_set_idx,
            head_move_idx,
            "change-set computation must be ordered before HEAD evaluation",
        )
        lowered = self.text.lower()
        self.assertIn("never folded into the baseline", lowered)
        self.assertIn("never misreported", lowered)


class TestScopeVerificationPathRulesAndTrash(unittest.TestCase):
    """AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_path_normalization_and_containment_rules(self):
        lowered = self.text.lower()
        self.assertIn("project-root-relative", lowered)
        self.assertIn("realpath", lowered)
        self.assertIn("segments", lowered)
        self.assertIn("feature-docs/example2", self.text)
        self.assertIn("feature-docs/example", self.text)

    def test_symlink_and_case_rules(self):
        lowered = self.text.lower()
        self.assertIn("symlink", lowered)
        self.assertIn("case-sensitive", lowered)
        self.assertIn("case-insensitive", lowered)

    def test_abort_when_trash_tool_unavailable(self):
        self.assertIn("gio", self.text)
        lowered = self.text.lower()
        self.assertIn("unavailable", lowered)
        self.assertIn("do not delete or move anything", lowered)


class TestNoRestatedSiblingSsotContent(unittest.TestCase):
    """Edge case (Test Notes): neither document restates the question packet
    fields (owned by question-packet-schema.md) or the workflow patch
    application rules (owned by workflow-patch.md)."""

    QUESTION_PACKET_OWNED_TOKENS = (
        r"^[a-z][a-z0-9-]*-q[0-9]{4}$",  # packet_id pattern
        r"^[a-z][a-z0-9._-]*$",  # question_id pattern
        "confirmed_facts[]",
        "assumptions[].",
    )
    WORKFLOW_PATCH_OWNED_TOKENS = (
        "Reject unless `base_input_digest` matches the digest recomputed",
        "single-write application",
        "All sixteen rules apply",
    )

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_neither_doc_restates_question_packet_internal_fields(self):
        for token in self.QUESTION_PACKET_OWNED_TOKENS:
            self.assertNotIn(
                token,
                self.spec_text,
                f"create-spec-phase.md must not restate question-packet-schema.md token {token!r}",
            )
            self.assertNotIn(
                token,
                self.plan_text,
                f"create-plan-phase.md must not restate question-packet-schema.md token {token!r}",
            )

    def test_neither_doc_restates_workflow_patch_application_rules(self):
        for token in self.WORKFLOW_PATCH_OWNED_TOKENS:
            self.assertNotIn(
                token,
                self.spec_text,
                f"create-spec-phase.md must not restate workflow-patch.md token {token!r}",
            )
            self.assertNotIn(
                token,
                self.plan_text,
                f"create-plan-phase.md must not restate workflow-patch.md token {token!r}",
            )


class TestExplicitTaskDispatchForm(unittest.TestCase):
    """task0015 AC-1: all three dispatch sites name their subagent type in
    the explicit Task form, matching the form
    `Task(subagent_type="em-workflow:<name>")` used for the design step in
    skills/develop/SKILL.md (e.g. `Task(subagent_type="em-workflow:designer")`).

    This test only checks the two phase documents this task owns. The
    repository-wide dispatch-set/agent-definition-set parity check is
    task0021's `check-plugin-invariants.py agent_dispatch_parity` and is not
    asserted here (Test Notes)."""

    TASK_DISPATCH_RE = re.compile(r'Task\(subagent_type="em-workflow:([a-z-]+)"\)')

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_create_spec_dispatches_requirements_analyst_explicitly(self):
        self.assertIn(
            'Task(subagent_type="em-workflow:requirements-analyst")',
            self.spec_text,
        )

    def test_create_spec_dispatches_spec_writer_explicitly(self):
        self.assertIn(
            'Task(subagent_type="em-workflow:spec-writer")',
            self.spec_text,
        )

    def test_create_plan_dispatches_implementation_planner_explicitly(self):
        self.assertIn(
            'Task(subagent_type="em-workflow:implementation-planner")',
            self.plan_text,
        )

    def test_no_prose_only_dispatch_sentence_remains(self):
        # The old prose form this replaces ("Dispatch requirements-analyst
        # with" / "Dispatch implementation-planner with:") must be gone from
        # the sites this task fixes.
        self.assertNotIn("Dispatch `requirements-analyst`", self.spec_text)
        self.assertNotIn("Dispatch `implementation-planner`", self.plan_text)

    def test_dispatch_form_matches_the_pattern_used_for_design_step(self):
        # Sanity check on the regex itself: it must actually match the form
        # skills/develop/SKILL.md uses for the design step, so this test
        # cannot vacuously pass against a form that looks similar but isn't.
        design_dispatch_line = 'Task(subagent_type="em-workflow:designer")'
        self.assertRegex(design_dispatch_line, self.TASK_DISPATCH_RE)
        spec_matches = set(self.TASK_DISPATCH_RE.findall(self.spec_text))
        plan_matches = set(self.TASK_DISPATCH_RE.findall(self.plan_text))
        self.assertIn("requirements-analyst", spec_matches)
        self.assertIn("spec-writer", spec_matches)
        self.assertIn("implementation-planner", plan_matches)


class TestCreatePlanCrossProductTwoBranches(unittest.TestCase):
    """task0015 AC-2: create-plan-phase.md defines two distinct cross-product
    branches, and the token-source-absent case (`kind: em_workflow` with
    `tokens.yaml` absent and `tokens.html` present) aborts with the offending
    paths instead of entering the reclassification gate."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_two_branches_are_explicitly_distinguished(self):
        self.assertIn("These two cases are not the same branch", self.text)

    def test_none_with_tokens_present_branch_goes_to_reclassify_gate(self):
        self.assertIn(
            "`kind: none` with either token file actually present",
            self.text,
        )
        self.assertIn("design-system.reclassify", self.text)

    def test_em_workflow_yaml_absent_html_present_branch_aborts(self):
        self.assertIn(
            "`kind: em_workflow` with `design-system/tokens.yaml` absent and",
            self.text,
        )
        self.assertIn("aborts create-plan dispatch outright", self.text)
        self.assertIn(
            "offending paths (`design-system/tokens.yaml` missing,",
            self.text,
        )

    def test_abort_branch_does_not_reuse_the_reclassify_gate(self):
        self.assertIn(
            "reclassification gate above is **not** run for this case",
            self.text,
        )


class TestScopeVerificationSnapshotCost(unittest.TestCase):
    """task0015 AC-3: the pre-dispatch snapshot no longer hashes every
    tracked path; content hashing is limited to paths reported as changed,
    and deletions, mode changes and kind changes remain detectable."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_whole_tree_hashing_row_is_gone(self):
        self.assertNotIn("Working-tree content for tracked paths", self.text)
        self.assertIn(
            "No whole-tree working-tree-content hashing pass runs here",
            self.text,
        )

    def test_changed_path_limitation_is_present(self):
        self.assertIn(
            "Content hashing with `git hash-object --` is applied only to the",
            self.text,
        )

    def test_deletions_mode_and_kind_changes_remain_detectable(self):
        self.assertIn(
            "deletions, mode changes, and kind changes (file ⇔ symlink ⇔ absent)",
            self.text,
        )


class TestScopeVerificationPreDispatchContainment(unittest.TestCase):
    """task0015 AC-4: the scope procedure validates targets and allowed
    roots before launching and states that post-dispatch comparison cannot
    recover an out-of-worktree write."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_pre_dispatch_containment_section_exists_before_snapshot(self):
        containment_idx = _first_index(
            self.text, "### Pre-dispatch containment validation"
        )
        snapshot_idx = _first_index(self.text, "### Pre-dispatch snapshot")
        self.assertLess(containment_idx, snapshot_idx)
        self.containment_section = self.text[containment_idx:snapshot_idx]

    def test_containment_rules_cover_absolute_paths_dotdot_symlinks_case(self):
        # Scoped to the pre-dispatch containment section itself (not the
        # whole document) so this test actually exercises the new
        # before-dispatch validation rather than the pre-existing
        # post-dispatch containment rules, which already covered the same
        # vocabulary.
        containment_idx = _first_index(
            self.text, "### Pre-dispatch containment validation"
        )
        snapshot_idx = _first_index(self.text, "### Pre-dispatch snapshot")
        section = self.text[containment_idx:snapshot_idx]
        lowered = section.lower()
        self.assertIn("absolute path", lowered)
        self.assertIn("`..` segment", section)
        self.assertIn("symlink", lowered)
        self.assertIn("case-insensitive filesystem", lowered)

    def test_post_dispatch_comparison_cannot_recover_out_of_worktree_write(self):
        self.assertIn("the latter is an audit, not the primary control", self.text)
        self.assertIn(
            "cannot be recovered by anything the post-dispatch comparison does",
            self.text,
        )


class TestAnalystDispatchLoopCacheReuse(unittest.TestCase):
    """task0015 AC-5: the analyst dispatch loop states that glob-derived
    categories come from the cached resolution unless a documented
    re-resolution trigger fired."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_resolved_input_cache_is_named(self):
        self.assertIn("resolved_input_cache", self.text)

    def test_three_re_resolution_triggers_are_named(self):
        self.assertIn(
            "re-resolution triggers fired since the last resolution",
            self.text,
        )

    def test_cache_reuse_applies_again_on_redispatch(self):
        self.assertIn("the cache is consulted", self.text)


class TestCreatePlanValidatorImplementedSubset(unittest.TestCase):
    """task0015 AC-6: create-plan-phase.md section 9 lists only the
    invariants the validator implements, marks the others as human review,
    states the layer split, and records the canonical validator
    invocation."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_section_8_states_the_layer_split(self):
        self.assertIn(
            "implements layers 1 (syntax), 2",
            self.text,
        )
        self.assertIn("orchestrator's own responsibility", self.text)

    def test_section_9_marks_unimplemented_invariants_as_human_review(self):
        self.assertIn("validator-implemented subset", self.text)
        self.assertIn("remain human review only", self.text)
        # The three invariants task0015's design says are absent from the
        # script must appear in the human-review list, not the checked list.
        self.assertIn(
            "Task/test mapping references resolve consistently outside the rework",
            self.text,
        )
        self.assertIn(
            "No `excluded` or `tbd` requirement has a task assigned to it.",
            self.text,
        )
        self.assertIn(
            "VERIFICATION.md includes a manual visual",
            self.text,
        )
        self.assertIn(
            "comparison step.",
            self.text,
        )

    def test_optional_arguments_silently_narrow_validation(self):
        self.assertIn(
            "silently narrows validation rather than failing loudly",
            self.text,
        )

    def test_canonical_validator_invocation_is_recorded(self):
        self.assertIn("Canonical validator invocation", self.text)
        self.assertIn("validate-worker-output.py", self.text)
        self.assertIn("--dry-run-apply", self.text)
        self.assertIn(
            "coverage regression, not a smaller valid invocation", self.text
        )


class TestRuleCitationsRepointedToShippedDocs(unittest.TestCase):
    """task0025 rework round 2 AC-1 (bs7): rule R1's normalization procedure,
    rule R2, and the seven-layer validation table now live in
    worker-envelope.md / workflow-schema.md respectively. Neither protocol
    may resolve a mention of them to design-input.md alone; design-input.md
    may still be named as provenance."""

    # Matches every citation form the pre-rework documents used to resolve
    # rule R1 ("design-input.md 5.0" / "design-input.md 5.0 R1"), rule R2
    # ("design-input.md 5.0 R2") and the validation layers
    # ("design-input.md 5.11.2") directly to the design document.
    DESIGN_MENTION_RE = re.compile(r"design-input\.md 5\.(?:0(?:\s+R[12])?|11\.2)")

    @classmethod
    def setUpClass(cls):
        cls.spec_text = _read(CREATE_SPEC_PATH)
        cls.plan_text = _read(CREATE_PLAN_PATH)

    def test_regex_matches_the_old_bare_resolution_forms(self):
        # Sanity check on the regex itself, so the assertion below cannot
        # vacuously pass against a pattern that no longer matches anything.
        self.assertTrue(self.DESIGN_MENTION_RE.search("design-input.md 5.0."))
        self.assertTrue(self.DESIGN_MENTION_RE.search("design-input.md 5.0 R1)"))
        self.assertTrue(self.DESIGN_MENTION_RE.search("design-input.md 5.0 R2)"))
        self.assertTrue(self.DESIGN_MENTION_RE.search("design-input.md 5.11.2)"))

    def test_worker_envelope_and_workflow_schema_are_cited_in_both_protocols(self):
        for text in (self.spec_text, self.plan_text):
            self.assertIn("references/contracts/worker-envelope.md", text)
            self.assertIn("references/workflow-schema.md", text)

    def test_no_mention_resolves_a_rule_or_validation_layer_to_design_doc_alone(self):
        for label, text in (
            ("create-spec-phase.md", self.spec_text),
            ("create-plan-phase.md", self.plan_text),
        ):
            matches = list(self.DESIGN_MENTION_RE.finditer(text))
            self.assertTrue(matches, f"{label} lost its design-input.md citations entirely")
            for match in matches:
                start = max(0, match.start() - 60)
                end = min(len(text), match.end() + 20)
                window = text[start:end].lower()
                self.assertIn(
                    "provenance",
                    window,
                    f"{label} resolves {text[match.start():match.end()]!r} "
                    "directly to design-input.md without provenance framing",
                )


class TestAnalystRedispatchPassesPriorAnalysis(unittest.TestCase):
    """task0025 rework round 2 AC-2 (bs5, dispatch half): the analyst
    re-dispatch step (inside "## 5. Analyst dispatch loop") passes
    `prior_analysis` with both its `content` and `input_digest` members, and
    states that the field is omitted when the digest no longer matches."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)
        start = _first_index(cls.text, "## 5. Analyst dispatch loop")
        end = cls.text.index("## 6. Question normalization")
        cls.section = cls.text[start:end]

    def test_prior_analysis_field_named_in_the_dispatch_loop_section(self):
        self.assertIn("prior_analysis", self.section)

    def test_both_members_named(self):
        self.assertIn("`content`", self.section)
        self.assertIn("`input_digest`", self.section)

    def test_populated_on_every_redispatch(self):
        self.assertIn("every analyst re-dispatch", self.section.lower())

    def test_omission_on_digest_mismatch_stated(self):
        lowered = self.section.lower()
        self.assertIn("longer matches the current", lowered)
        self.assertIn("omitted", lowered)


class TestScopeVerificationCandidateDerivedEnumeration(unittest.TestCase):
    """task0025 rework round 2 AC-3/AC-4 (bs14): the pre-dispatch snapshot no
    longer lists every tracked entry, the post-dispatch comparison derives
    its candidates from the untracked-file status and the tracked
    index-versus-working-tree comparison instead, and deletions, mode
    changes and file/symlink/absent transitions remain detectable."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_whole_index_listing_row_is_gone(self):
        self.assertNotIn(
            "Index blob IDs and modes | `git ls-files -s -z`", self.text
        )

    def test_no_whole_index_listing_pass_wording_present(self):
        self.assertIn(
            "whole-index blob-id/mode listing pass runs here either",
            self.text.lower(),
        )

    def test_candidates_derived_from_status_and_index_comparison(self):
        self.assertIn(
            "Enumerate candidates from two changes-proportional sources",
            self.text,
        )
        self.assertIn("a whole-index listing of every tracked entry", self.text)

    def test_blob_ids_and_modes_queried_only_for_candidates(self):
        self.assertIn(
            "blob identifiers and modes are likewise queried", self.text
        )

    def test_deletions_mode_and_kind_changes_still_detectable(self):
        # Already asserted by TestScopeVerificationSnapshotCost (task0015);
        # re-asserted here because this task rewrites the surrounding
        # sentence and the phrase must survive that rewrite unchanged.
        self.assertIn(
            "deletions, mode changes, and kind changes (file ⇔ symlink ⇔ absent)",
            self.text,
        )


class TestCreatePlanCanonicalInvocationIncludesPhaseState(unittest.TestCase):
    """task0025 rework round 2 AC-5 (bs10, invocation half): the canonical
    `implementation-planner` validator invocation includes `--phase-state`,
    and the accompanying silently-narrowing-omission list names it."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_invocation_includes_phase_state_argument(self):
        self.assertIn("--phase-state {phase-state/create-plan.yaml}", self.text)

    def test_omission_list_names_phase_state(self):
        self.assertIn("dropping `--phase-state` skips the", self.text)
        self.assertIn("duplicate-patch-identifier idempotency check", self.text)


class TestCreateSpecCompletedPayloadKeyReference(unittest.TestCase):
    """task0025 rework round 2 AC-6 (bs1, stray reference): the design-system
    zero-candidate exception in section 11a describes requirements-analyst's
    *completed* payload, whose key is the bare `design_system_candidates` --
    not the needs_user_input payload's nested
    `analysis_snapshot.design_system_candidates`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)

    def test_stray_analysis_snapshot_prefixed_key_is_gone(self):
        self.assertNotIn("analysis_snapshot.design_system_candidates", self.text)

    def test_bare_completed_payload_key_is_used_instead(self):
        self.assertIn("completed-payload `design_system_candidates`", self.text)


if __name__ == "__main__":
    unittest.main()
