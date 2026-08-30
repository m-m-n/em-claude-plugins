"""Tests for task0027: the re-planning carry-over rule reaches its producer
and its consumers.

Covers task0027 Acceptance Criteria (feature-docs/goal-vs-spec-divergence/
tasks/task0027.md):

- AC-1: neither `references/phases/create-plan-phase.md` nor
  `references/contracts/planner-contract.md` states a count of
  `workflow-patch.md`'s application rules (no number word, no numeral), and
  each of the two sites that carried the count now cites
  `references/workflow-patch.md` by path instead.
- AC-2: `references/contracts/planner-contract.md` states that a
  re-planning `replace_all`'s `tasks_patch` carries `carried_task_ids`
  alongside `entries`, deferring to `references/workflow-patch.md` for what
  the two fields mean, and states no eligibility/disjointness/copying rule
  of its own.
- AC-3: `agents/implementation-planner.md`'s task-id allocation instruction
  has two branches keyed on the `create-plan` step's status.
- AC-4: `agents/implementation-planner.md`'s description of the returned
  `workflow_patch` names `carried_task_ids` as a field emitted on a
  re-planning pass, with no surviving instruction to place every task in
  `entries`.

Per Convention C4, this module asserts only over the three documents this
task owns; it does not assert anything over `references/workflow-patch.md`
itself (Test Notes / Out of Scope), which stays task0029's to change.

These deliverables are specification/prompt documents, so acceptance
criteria are verified by structural/textual assertions over the Markdown
rather than behavioral tests of running code (Test Notes).

Extended for task0001 (rework-contract-drift,
feature-docs/rework-contract-drift/tasks/task0001.md): the prompt's second
task-id allocation branch and the contract's mirroring sentence keyed the
Re-planning path on a single `create-plan` status literal (`needs_update`)
that the specification-change transition does not actually produce (it
produces `pending`, recognized instead through a `spec_change` re-entry
signal -- `references/workflow-patch.md`'s `replace_all` permission
conditions, Re-planning path, second case). A planner following the
erroneous literal took the Initial-planning branch on a real re-planning
pass and emitted a patch the validator rejects. This task's own Acceptance
Criteria covered here:

- AC-1: `TestImplementationPlannerTwoBranchAllocation.
  test_re_planning_branch_no_longer_keyed_on_a_single_status_literal` /
  `test_re_planning_branch_cites_owning_document_and_re_planning_path` (the
  prompt) and `TestPlannerContractReplanningNotKeyedOnStatusLiteral` (the
  contract) -- neither document keys the Re-planning condition on a
  `create-plan` status literal any longer; both name
  `references/workflow-patch.md` by path and identify its Re-planning path
  as the source of the rule.
- AC-2: `TestImplementationPlannerTwoBranchAllocation.
  test_re_planning_branch_states_no_high_water_mark_formula` -- the prompt
  carries no restated `max(carried_task_ids ...)` formula and no restated
  characterization of which identifiers the high-water mark counts; it
  cites the owning definition instead.
- AC-3: `test_two_branches_present_initial_planning_keyed_on_pending_status`
  plus the two tests under AC-1 above -- this is the same two-branch test
  task0027 wrote, rewritten so it no longer pins the erroneous literal and
  instead asserts the erroneous literal's absence and the citation form's
  presence. Confirmed (TDD) to fail against the pre-change prompt before
  the prompt was edited.
- AC-4: every absence assertion above (`test_re_planning_branch_no_longer_
  keyed_on_a_single_status_literal`, `test_re_planning_branch_states_no_
  high_water_mark_formula`, `TestPlannerContractReplanningNotKeyedOnStatus
  Literal.test_no_single_status_literal_condition`) is paired with a
  `test_matcher_detects_a_synthetic_...` negative proof in the same class.
- AC-5: `TestReplanningReentryDryRunAcceptance` -- a synthetic re-planning
  patch representing the specification-change transition (create-plan
  `pending`, a `spec_change` re-entry signal, one already-`merged` task) is
  accepted by the validator's `--dry-run-apply` mode via a direct
  `validate_workflow_patch()` call, with neither
  `replace-all-entry-for-registered-id` nor `replace-all-drops-task` among
  the reported error codes. Self-contained in this module (Test Notes: does
  not depend on `em-workflow/references/fixtures/`, which task0004 owns).
  Its synthetic `spec_change` record follows IMPLEMENTATION.md Shared
  Components' "Synthetic spec-change record shape in tests" contract.
- AC-6: the full suite (`python3 -m unittest discover -s tests`) is green
  and this task adds no third-party import -- `TestReplanningReentryDryRun
  Acceptance` loads `scripts/validate-worker-output.py` the same way
  `tests/test_spec_change_replan_authorization.py` already does, PyYAML
  being that script's existing runtime dependency (IMPLEMENTATION.md
  Technology Stack), not a new one this task adds.

Extended for task0007 (rework-contract-drift,
feature-docs/rework-contract-drift/tasks/task0007.md): task0001 fixed the
Re-planning branch's key but left the Initial-planning branch keyed on a
single `create-plan` status literal (`pending`) that the Re-planning
path's second case also satisfies -- a planner following the prompt
literally on a specification-change re-entry matched the Initial-planning
branch instead, numbering from the first task id and emitting no
carry-over declaration. This task's own Acceptance Criteria covered here:

- AC-1: `test_initial_planning_branch_cites_owning_document_and_initial_
  planning_path` -- the Initial-planning branch now names
  `references/workflow-patch.md` by path and identifies its
  Initial-planning path as the owner of which states satisfy the branch.
- AC-2: `test_neither_branch_keyed_on_a_single_step_status_literal` (with
  its negative proof) and `test_initial_planning_branch_states_condition_
  not_restated` -- neither branch carries a bare step-status literal as
  its key, and the Initial-planning branch states the condition is not
  restated there.
- AC-3: `test_prompt_does_not_restate_the_floor_condition_wording` and
  `test_prompt_does_not_restate_the_re_entry_signal_field_names`, each
  paired with a `test_matcher_detects_a_synthetic_...` negative proof --
  the prompt names the floor condition and the re-entry signal by concept
  only, never restating their own wording or field names.
- AC-4: `test_two_branch_headers_present` replaces the old test that
  pinned the now-removed `create-plan` is `pending` literal, keeping only
  the header-presence check; every new absence assertion above is paired
  with a negative-proof test in the same class.
- AC-5: confirmed (TDD) to fail against the pre-change prompt where the
  assertion is a presence check (AC-1, AC-2's `not restated here`) or an
  absence check the pre-change literal actually violated (AC-2's combined
  literal check); the AC-3 absence checks already held pre-change (the
  pre-change Initial-planning branch restated neither the floor condition
  nor the re-entry signal, it simply keyed on the bare literal), so their
  negative-proof samples stand in for a violating pre-change text per
  NFR4's demonstration allowance.
- AC-6: the full suite is green and this task adds no third-party import.
"""

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PLANNER_AGENT_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
PLANNER_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"
CREATE_PLAN_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
VALIDATOR_SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"

WORKFLOW_PATCH_REF = "references/workflow-patch.md"
REPLANNING_PATH_TERM = "Re-planning path"
INITIAL_PLANNING_PATH_TERM = "Initial-planning path"

# Distinctive wording owned by workflow-patch.md's Initial-planning path
# floor condition. A consumer containing this would be restating the
# condition, not citing it (task0007 AC-3).
FLOOR_CONDITION_PHRASE = "every existing task's `status` is `pending`"

# Field names distinctive to the Re-planning path's second-case re-entry
# signal (the `spec_change` record). A consumer containing any of these
# would be restating that condition too (task0007 AC-3).
REENTRY_SIGNAL_FIELD_NAMES = ("origin_kind", "replan_authorized", "recorded_at_commit")


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output_replanning_producer_alignment", VALIDATOR_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

NUMBER_WORDS = (
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    r"eighteen|nineteen|twenty"
)

# Matches a numeral or number word immediately followed by (optionally
# "application ") "rules" -- the shape a restated rule-set count takes,
# whether spelled ("sixteen application rules") or digit ("16 rules").
RULE_COUNT_RE = re.compile(
    rf"\b(?:\d+|{NUMBER_WORDS})\b\s+(?:application\s+)?rules\b",
    re.IGNORECASE,
)

# Text distinctive to workflow-patch.md's OWN statement of the carry-over
# rule's substance (eligibility / disjointness / copying / high-water
# mark). A consumer containing any of these would be restating the rule,
# not citing it (NFR1 / C2).
WORKFLOW_PATCH_OWNED_CARRY_OVER_SUBSTANCE = (
    "copied from that `workflow.yaml` **verbatim**",
    "must not also be a key of `tasks_patch.entries`",
    "max(carried_task_ids",
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _norm(text):
    """Collapse whitespace runs (including line-wrap newlines inside a
    prose sentence) to a single space, so a multi-word phrase assertion
    does not depend on where Markdown happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


class TestNoRestatedApplicationRuleCount(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.create_plan_text = _read(CREATE_PLAN_PHASE_PATH)
        cls.planner_contract_text = _read(PLANNER_CONTRACT_PATH)

    def test_matcher_fires_on_synthetic_spelled_out_count(self):
        """Negative proof: the regex must actually detect a restated count,
        spelled out, before its absence in the real docs means anything."""
        sample = "Workflow patch structure and its sixteen application rules."
        self.assertRegex(sample, RULE_COUNT_RE)

    def test_matcher_fires_on_synthetic_numeral_count(self):
        """Negative proof, numeral form."""
        sample = "the tasks_patch entry shape, and the 17 application rules"
        self.assertRegex(sample, RULE_COUNT_RE)

    def test_matcher_does_not_fire_on_an_unrelated_numbered_rule_reference(self):
        """A specific rule reference ('application rule 15') is not a count
        of the rule set and must not trip the matcher."""
        sample = "single-write application (`references/workflow-patch.md`'s application rule 15)."
        self.assertNotRegex(sample, RULE_COUNT_RE)

    def test_create_plan_phase_reading_list_entry_found_non_vacuous(self):
        """Non-vacuity guard: the reading-list bullet this AC targets must
        actually be found before its content is asserted about -- otherwise
        an absence assertion over an empty read would pass vacuously."""
        section = _extract_section(
            self.create_plan_text,
            "Workflow patch structure and its",
            WORKFLOW_PATCH_REF,
        )
        self.assertTrue(section, "expected a non-empty reading-list bullet")

    def test_create_plan_phase_reading_list_cites_workflow_patch_by_path(self):
        section = _extract_section(
            self.create_plan_text,
            "Workflow patch structure and its",
            "\n\n",
        )
        self.assertIn(WORKFLOW_PATCH_REF, section)

    def test_create_plan_phase_states_no_rule_count(self):
        self.assertNotRegex(self.create_plan_text, RULE_COUNT_RE)

    def test_planner_contract_completed_payload_found_non_vacuous(self):
        section = _extract_section(
            self.planner_contract_text,
            "## `completed` payload",
            "## Prohibited fields",
        )
        self.assertTrue(section, "expected a non-empty `completed` payload section")
        self.assertIn("application rules are owned by", section)

    def test_planner_contract_completed_payload_cites_workflow_patch_by_path(self):
        section = _extract_section(
            self.planner_contract_text,
            "## `completed` payload",
            "## Prohibited fields",
        )
        self.assertIn(WORKFLOW_PATCH_REF, section)

    def test_planner_contract_states_no_rule_count(self):
        self.assertNotRegex(self.planner_contract_text, RULE_COUNT_RE)


class TestPlannerContractCarryOverField(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.section = _extract_section(
            cls.text, "## `completed` payload", "## Prohibited fields"
        )

    def test_section_found_non_vacuous(self):
        self.assertTrue(self.section)

    def test_states_carried_task_ids_alongside_entries(self):
        self.assertIn("carried_task_ids", self.section)
        self.assertIn("entries", self.section)
        self.assertIn("re-planning", self.section.lower())

    def test_defers_to_workflow_patch_for_field_meaning(self):
        self.assertIn(WORKFLOW_PATCH_REF, self.section)
        self.assertIn("Re-planning task-id allocation", _norm(self.section))
        self.assertIn("not restated here", self.section)

    def test_states_no_eligibility_disjointness_or_copying_rule_of_its_own(self):
        for distinctive in WORKFLOW_PATCH_OWNED_CARRY_OVER_SUBSTANCE:
            self.assertNotIn(
                distinctive,
                self.text,
                f"planner-contract.md must not restate workflow-patch.md's "
                f"own carry-over rule text ({distinctive!r})",
            )

    def test_matcher_detects_a_synthetic_doc_omitting_carried_task_ids(self):
        """Negative proof (Test Notes: 'one that omits carried_task_ids')."""
        violating_sample = (
            "## `completed` payload\n"
            "The `workflow_patch` carries `entries` for every task.\n"
            "## Prohibited fields\n"
        )
        section = _extract_section(
            violating_sample, "## `completed` payload", "## Prohibited fields"
        )
        self.assertNotIn("carried_task_ids", section)


class TestPlannerContractReplanningNotKeyedOnStatusLiteral(unittest.TestCase):
    """task0001 AC-1: planner-contract.md's re-planning sentence is aligned
    to the same citation form as the prompt -- it no longer keys the
    re-planning condition on a single `create-plan` status literal, and
    instead names the owning document by path and its Re-planning path as
    the source."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.section = _extract_section(
            cls.text, "## `completed` payload", "## Prohibited fields"
        )

    def test_section_found_non_vacuous(self):
        self.assertTrue(self.section)

    def test_no_single_status_literal_condition(self):
        self.assertNotIn("the `create-plan` step is `needs_update`", self.section)
        self.assertNotIn("needs_update", self.section)

    def test_matcher_detects_a_synthetic_needs_update_literal_sentence(self):
        """Negative proof for the absence check above."""
        violating_sample = (
            "On a re-planning pass (the `create-plan` step is "
            "`needs_update`), `tasks_patch` also carries `carried_task_ids`."
        )
        self.assertIn("the `create-plan` step is `needs_update`", violating_sample)
        self.assertIn("needs_update", violating_sample)

    def test_re_planning_sentence_cites_owning_document_and_re_planning_path(self):
        self.assertIn(WORKFLOW_PATCH_REF, self.section)
        self.assertIn(REPLANNING_PATH_TERM, self.section)


class TestImplementationPlannerTwoBranchAllocation(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_AGENT_PATH)
        cls.section = _extract_section(
            cls.text,
            "### 4. Task decomposition",
            "### 5. VERIFICATION.md",
        )

    def test_section_found_non_vacuous(self):
        self.assertTrue(self.section)

    def test_two_branch_headers_present(self):
        """task0007 AC-4: replaces the old literal-pinning test (which
        asserted the Initial-planning branch's now-removed `create-plan`
        is `pending` key) with the header-presence check alone; the
        literal's absence is covered by
        test_neither_branch_keyed_on_a_single_step_status_literal below."""
        self.assertIn("**Initial planning**", self.section)
        self.assertIn("**Re-planning**", self.section)

    def test_initial_planning_branch_cites_owning_document_and_initial_planning_path(self):
        """task0007 AC-1: the Initial-planning branch names the owning
        document by repository-relative path and identifies its
        Initial-planning path as the source of which states satisfy the
        branch, instead of restating the condition itself -- the same
        citation form the Re-planning branch already uses."""
        branch = _extract_section(
            self.section, "**Initial planning**", "**Re-planning**"
        )
        self.assertIn(WORKFLOW_PATCH_REF, branch)
        self.assertIn(INITIAL_PLANNING_PATH_TERM, branch)

    def test_initial_planning_branch_states_condition_not_restated(self):
        """task0007 AC-2: the Initial-planning branch states that which
        states satisfy the Initial-planning path is not restated here."""
        branch = _extract_section(
            self.section, "**Initial planning**", "**Re-planning**"
        )
        self.assertIn("not restated here", branch)

    def test_neither_branch_keyed_on_a_single_step_status_literal(self):
        """task0007 AC-2: the section contains no branch key of the form
        '`create-plan` is `pending`' or '`create-plan` is `needs_update`'
        -- both branches now cite the owning document instead."""
        self.assertNotIn("`create-plan` is `pending`", self.section)
        self.assertNotIn("`create-plan` is `needs_update`", self.section)

    def test_matcher_detects_a_synthetic_branch_keyed_on_pending_literal(self):
        """Negative proof for the `pending` half of the check above (the
        `needs_update` half is already proven by
        test_matcher_detects_a_synthetic_needs_update_literal_branch)."""
        violating_sample = (
            "- **Initial planning** (`create-plan` is `pending`): number "
            "every task taskNNNN in order, starting at `task0001`."
        )
        self.assertIn("`create-plan` is `pending`", violating_sample)

    def test_prompt_does_not_restate_the_floor_condition_wording(self):
        """task0007 AC-3: the prompt names the Initial-planning path's
        floor condition by concept only ('its floor condition on existing
        task status'); it never restates the condition's own wording,
        which stays owned by workflow-patch.md."""
        self.assertNotIn(FLOOR_CONDITION_PHRASE, self.text)

    def test_matcher_detects_a_synthetic_floor_condition_restatement(self):
        """Negative proof for the check above."""
        violating_sample = (
            "permitted only when `tasks` is empty, OR every existing "
            "task's `status` is `pending`"
        )
        self.assertIn(FLOOR_CONDITION_PHRASE, violating_sample)

    def test_prompt_does_not_restate_the_re_entry_signal_field_names(self):
        """task0007 AC-3: the prompt never restates the Re-planning
        path's second-case re-entry signal (the `spec_change` record's
        field names) -- that stays owned by workflow-patch.md too."""
        for term in REENTRY_SIGNAL_FIELD_NAMES:
            self.assertNotIn(term, self.text, f"prompt must not restate {term!r}")

    def test_matcher_detects_a_synthetic_re_entry_signal_restatement(self):
        """Negative proof for the check above."""
        violating_sample = (
            "recognizable via an unspent re-planning authorization "
            "carrying origin_kind, replan_authorized and "
            "recorded_at_commit"
        )
        for term in REENTRY_SIGNAL_FIELD_NAMES:
            self.assertIn(term, violating_sample)

    def test_re_planning_branch_no_longer_keyed_on_a_single_status_literal(self):
        """task0001 AC-1/AC-3: the erroneous single-literal re-planning
        condition (`create-plan` is `needs_update`) is gone. The owning
        document permits the Re-planning path through two distinct states,
        and the specification-change transition produces the OTHER one, so
        keying on this single literal caused a planner following the prompt
        to take the Initial-planning branch on a real re-planning pass."""
        branch = self.section[self.section.index("**Re-planning**"):]
        self.assertNotIn("`create-plan` is `needs_update`", branch)
        self.assertNotIn("needs_update", branch)

    def test_matcher_detects_a_synthetic_needs_update_literal_branch(self):
        """Negative proof: the substring checks above must actually detect
        the erroneous shape before their absence in the real prompt means
        anything."""
        violating_sample = (
            "- **Re-planning** (`create-plan` is `needs_update`): every id "
            "already registered ..."
        )
        self.assertIn("`create-plan` is `needs_update`", violating_sample)
        self.assertIn("needs_update", violating_sample)

    def test_re_planning_branch_cites_owning_document_and_re_planning_path(self):
        """task0001 AC-1: the Re-planning branch names the owning document
        by repository-relative path and identifies its Re-planning path as
        the source of the rule, instead of restating the condition itself."""
        branch = self.section[self.section.index("**Re-planning**"):]
        self.assertIn(WORKFLOW_PATCH_REF, branch)
        self.assertIn(REPLANNING_PATH_TERM, branch)

    def test_re_planning_branch_states_no_high_water_mark_formula(self):
        """task0001 AC-2: no restated high-water-mark formula and no
        restated statement of which identifiers it counts survive in the
        prompt; the "high-water mark" term itself may remain (other tests
        pin its surrounding obligations), but the union-of-ids formula that
        characterizes what it counts must not."""
        self.assertNotIn("max(carried_task_ids", self.text)
        self.assertIn("high-water mark", self.section)

    def test_matcher_detects_a_synthetic_high_water_mark_formula(self):
        """Negative proof for the high-water-mark formula absence check
        above."""
        violating_sample = (
            "continuing above the high-water mark "
            "(`max(carried_task_ids ∪ entries)`), and these go under "
            "`entries`"
        )
        self.assertIn("max(carried_task_ids", violating_sample)

    def test_initial_planning_branch_numbers_from_task0001(self):
        branch = _extract_section(
            self.section, "**Initial planning**", "**Re-planning**"
        )
        self.assertIn("task0001", branch)

    def test_re_planning_branch_requires_carried_task_ids_for_registered_ids(self):
        branch = self.section[self.section.index("**Re-planning**") :]
        self.assertIn("carried_task_ids", branch)
        self.assertIn("already registered", _norm(branch))
        self.assertIn("MUST be listed", branch)

    def test_re_planning_branch_requires_entries_only_unregistered_above_high_water_mark(self):
        branch = self.section[self.section.index("**Re-planning**") :]
        self.assertIn("not yet registered", branch)
        self.assertIn("high-water mark", branch)
        self.assertIn("entries", branch)
        self.assertIn("disjoint", branch)

    def test_re_planning_branch_states_no_body_for_carried_id(self):
        branch = self.section[self.section.index("**Re-planning**") :]
        self.assertIn("no body", branch)

    def test_branches_stated_in_imperative_form(self):
        """The rest of the prompt states obligations imperatively ('Write
        ...', 'Determine ...', 'MUST NOT ...'); the re-planning branch must
        match that register rather than a passive/descriptive one."""
        branch = self.section[self.section.index("**Re-planning**") :]
        self.assertIn("MUST be listed", branch)

    def test_re_planning_branch_reachable_from_dispatch_description(self):
        """Nothing earlier in the prompt restricts dispatch to the
        initial-planning case only -- the only dispatch precondition stated
        is 'not before create-spec', which does not exclude re-planning."""
        self.assertIn("this agent never runs before create-spec", self.text)
        self.assertNotIn("only ever runs on the initial planning pass", self.text)
        self.assertNotIn("create-plan` is `pending` (mandatory)", self.text)

    def test_matcher_detects_a_synthetic_single_branch_doc(self):
        """Negative proof (Test Notes: 'one whose allocation instruction has
        a single branch')."""
        violating_sample = (
            "### 4. Task decomposition\n"
            "For each task, in order taskNNNN (task0001, task0002, ...):\n"
            "### 5. VERIFICATION.md\n"
        )
        section = _extract_section(
            violating_sample, "### 4. Task decomposition", "### 5. VERIFICATION.md"
        )
        self.assertNotIn("**Re-planning**", section)


class TestImplementationPlannerOutputNamesCarriedTaskIds(unittest.TestCase):
    """AC-4."""

    EVERY_TASK_INTO_ENTRIES_RE = re.compile(
        r"every task[^.]{0,80}entries", re.IGNORECASE
    )

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_AGENT_PATH)
        cls.output_section = _extract_section(
            cls.text, "## Output", "## Important Guidelines"
        )

    def test_output_section_found_non_vacuous(self):
        self.assertTrue(self.output_section)

    def test_output_names_carried_task_ids_emitted_on_re_planning_pass(self):
        self.assertIn("carried_task_ids", self.output_section)
        self.assertIn("re-planning", self.output_section.lower())

    def test_no_surviving_instruction_to_place_every_task_in_entries(self):
        self.assertNotRegex(self.text, self.EVERY_TASK_INTO_ENTRIES_RE)

    def test_matcher_detects_a_synthetic_every_task_in_entries_instruction(self):
        """Negative proof: the regex must actually catch the shape of the
        superseded instruction before its absence means anything."""
        violating_sample = "every task goes in `entries` with initial_status: pending"
        self.assertRegex(violating_sample, self.EVERY_TASK_INTO_ENTRIES_RE)


# ---------------------------------------------------------------------------
# task0001 AC-5
# ---------------------------------------------------------------------------


class TestReplanningReentryDryRunAcceptance(unittest.TestCase):
    """task0001 AC-5: a synthetic re-planning patch representing the
    specification-change transition -- the create-plan step at the status
    that transition actually produces (`pending`, recognized via the
    `spec_change` re-entry signal, never `needs_update`), with at least one
    already-`merged` task -- is accepted by the validator's
    `--dry-run-apply` mode, with neither the registered-identifier
    rejection (`replace-all-entry-for-registered-id`) nor the dropped-task
    rejection (`replace-all-drops-task`) raised.

    Kept self-contained in this module (not depending on
    `em-workflow/references/fixtures/`, which task0004 owns) per Test
    Notes. Its synthetic `spec_change` record follows IMPLEMENTATION.md
    Shared Components' "Synthetic spec-change record shape in tests"
    contract: a valid `origin_kind`, non-empty `origin_id`, `reason` and
    `recorded_at_commit`, and a boolean `replan_authorized`."""

    FEATURE = "rework-contract-drift-example"

    @classmethod
    def setUpClass(cls):
        cls.vwo = _load_validator_module()

    def _workflow(self):
        return {
            "feature": self.FEATURE,
            "requirements": {},
            "tasks": {
                "task0009": {
                    "branch": "em-workflow/rework-contract-drift-example/task0009",
                    "complexity": "low",
                    "domains": [],
                    "files": ["x.go"],
                    "notes": None,
                    "plan": "tasks/task0009.md",
                    "requirements": [],
                    "skills": [],
                    "status": "merged",
                    "title": "existing merged task",
                }
            },
            "workflow": [
                {"id": "create-plan", "status": "pending"},
                {"id": "implement", "status": "pending", "base_commit": "deadbeef"},
            ],
        }

    def _phase_state(self):
        return {
            "phase": "rework",
            "feature": self.FEATURE,
            "spec_change": {
                "reason": "spec changed after review",
                "origin_kind": "review",
                "origin_id": "abc123",
                "recorded_at_commit": "deadbeef",
                "consumed": False,
                "replan_authorized": True,
            },
        }

    def _digest_source(self):
        return {
            "answers_digest": "sha256:" + "2" * 64,
            "digest_inputs": {},
            "mode": "interactive",
            "value_inputs": {"task_description": None},
            "worker": "implementation-planner",
            "workflow_blob": "8f17c04",
            "write_policy_digest": "sha256:" + "3" * 64,
        }

    def _patch(self, base_input_digest):
        return {
            "base_input_digest": base_input_digest,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "patch_id": "create-plan-p0002",
            "preserve": ["workflow.implement.base_commit"],
            "requirements_patch": None,
            "schema_version": 1,
            "step_patches": [],
            "tasks_patch": {
                "carried_task_ids": ["task0009"],
                "entries": {},
                "mode": "replace_all",
            },
        }

    def _validate(self, phase_state):
        digest_source = self._digest_source()
        base_input_digest = self.vwo.normalize_json_sha256(digest_source)
        return self.vwo.validate_workflow_patch(
            self._patch(base_input_digest),
            workflow=self._workflow(),
            registries=None,
            digest_source=digest_source,
            phase_state=phase_state,
            dry_run=True,
            feature_dir=None,
        )

    def test_create_plan_status_used_is_the_one_the_transition_actually_produces(self):
        """Non-vacuity: confirms the workflow this test builds keys
        create-plan at `pending`, not `needs_update` -- the state the
        erroneous prompt literal missed (task plan Design: 'the state the
        specification-change transition actually produces is the other
        one')."""
        create_plan = next(
            s for s in self._workflow()["workflow"] if s["id"] == "create-plan"
        )
        self.assertEqual(create_plan["status"], "pending")

    def test_spec_change_transition_replanning_patch_is_accepted(self):
        errors = self._validate(self._phase_state())
        self.assertEqual(errors, [], errors)

    def test_neither_registered_identifier_nor_dropped_task_rejection_raised(self):
        errors = self._validate(self._phase_state())
        codes = {e.get("code") for e in errors}
        self.assertNotIn("replace-all-entry-for-registered-id", codes)
        self.assertNotIn("replace-all-drops-task", codes)

    def test_without_the_reentry_signal_the_same_patch_is_rejected(self):
        """Negative proof: the acceptance above is not a coincidence of some
        other fixture detail -- without the `spec_change` re-entry signal,
        the validator falls back to the Initial-planning rule and this same
        patch (a `merged` task present, not all `pending`) is rejected."""
        errors = self._validate(None)
        codes = {e.get("code") for e in errors}
        self.assertIn("replace-all-not-permitted", codes)


if __name__ == "__main__":
    unittest.main()
