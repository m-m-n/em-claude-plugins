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
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PLANNER_AGENT_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
PLANNER_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"
CREATE_PLAN_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"

WORKFLOW_PATCH_REF = "references/workflow-patch.md"

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

    def test_two_branches_present_keyed_on_create_plan_status(self):
        self.assertIn("**Initial planning**", self.section)
        self.assertIn("**Re-planning**", self.section)
        self.assertIn("`create-plan` is `pending`", self.section)
        self.assertIn("`create-plan` is `needs_update`", self.section)

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


if __name__ == "__main__":
    unittest.main()
