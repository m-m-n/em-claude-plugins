"""Tests for task0009: the three new Task-dispatched worker agent
definitions (requirements-analyst / spec-writer / rework-planner).

Covers task0009 Acceptance Criteria (feature-docs/agent-separation/tasks/
task0009.md):

- AC-1: all three agent files exist with valid YAML frontmatter containing
  `name`, `description`, `model`, `effort` and `tools`, and none lists
  AskUserQuestion among its tools.
- AC-2: each prompt references its contract document by path and states
  that the final output is a single structured object conforming to the
  common envelope.
- AC-3: each prompt states that workflow.yaml is read-only, that the
  worker never commits, and that it reads only the supplied paths.
- AC-4: no prompt contains a `# Task assignment` heading.
- AC-5: the analyst prompt describes both `analysis_mode` values with their
  payload difference and states that it detects design-system candidates
  without deciding `kind`.
- AC-6: the spec-writer prompt states that it never invents requirements or
  assumptions and that a digest disagreement yields `blocked`.
- AC-7: the rework-planner prompt states that it plans only additional
  tasks, emits the coverage declaration and the shared-contract rationale,
  proposes a patch rather than writing workflow.yaml, and returns a
  question when a specification change is required.

These deliverables are agent prompt documents (Markdown + YAML
frontmatter), so verification is by structural/textual assertion against
the rendered files, per task0009.md Test Notes. A shared assertion helper
(`_assert_common_worker_rules`) covers the three rules common to every
worker in scope (task0009.md Test Notes: "so a fourth worker added later is
trivially checkable").
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
AGENTS_DIR = PLUGIN_ROOT / "agents"

ANALYST_PATH = AGENTS_DIR / "requirements-analyst.md"
SPEC_WRITER_PATH = AGENTS_DIR / "spec-writer.md"
REWORK_PLANNER_PATH = AGENTS_DIR / "rework-planner.md"

ANALYST_CONTRACT_REF = "references/contracts/analyst-contract.md"
SPEC_WRITER_CONTRACT_REF = "references/contracts/spec-writer-contract.md"
REWORK_PLANNER_CONTRACT_REF = "references/contracts/rework-planner-contract.md"
ENVELOPE_REF = "references/contracts/worker-envelope.md"

REQUIRED_FRONTMATTER_KEYS = ("name", "description", "model", "effort", "tools")

# Canonical common-rule sentences. Every one of the three new worker
# prompts must contain each of these substrings (compared against
# whitespace-normalized text, so a prose line-wrap edit does not make an
# otherwise-unchanged sentence fail) -- these are prose a later fourth
# worker can copy verbatim, per the task's shared-helper instruction.
COMMON_READONLY_NOCOMMIT_SUBSTRING = (
    "You treat `workflow.yaml` as read-only input and never commit anything "
    "to git."
)
COMMON_NO_DISCOVERY_SUBSTRING = (
    "You read only the fixed-path inputs the envelope supplies plus the "
    "entries listed in `resolved_input_paths`, and never perform your own "
    "filesystem discovery beyond that list."
)
COMMON_NO_ASK_SUBSTRING = "you have no `AskUserQuestion` tool and never ask the user directly"
COMMON_SINGLE_OUTPUT_SUBSTRING = "single structured object conforming to the common worker envelope"

FORBIDDEN_TASK_ASSIGNMENT_HEADING = re.compile(r"^# Task assignment\b", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so prose assertions survive a wrap-column edit that
    changes no word. NOT used for the frontmatter split or the
    `# Task assignment` heading check -- both of those depend on real
    line boundaries."""
    return re.sub(r"\s+", " ", text)


def _split_frontmatter(text):
    """Return (frontmatter_text, body_text) for a `---`-delimited YAML
    frontmatter block, without requiring a YAML parser dependency (PyYAML
    is a plugin runtime dependency, not a test dependency -- IMPLEMENTATION.md
    Technology Stack)."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise AssertionError(f"expected a --- delimited frontmatter block, got: {text[:80]!r}")
    return match.group(1), match.group(2)


def _parse_flat_frontmatter(frontmatter_text):
    """Parse the repository's flat agent-frontmatter schema (scalar
    `key: value` lines, plus an optional `key:` followed by indented `- item`
    list lines, as used for `skills:`) into a dict of str / list[str].

    This is a minimal hand-rolled parser for the specific shape used by
    `em-workflow/agents/*.md` -- not a general YAML parser -- kept dependency
    -free per test/README.md."""
    data = {}
    current_list_key = None
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        list_item = re.match(r"^\s+-\s+(.*)$", line)
        if list_item and current_list_key is not None:
            data[current_list_key].append(list_item.group(1).strip())
            continue
        kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$", line)
        if not kv:
            raise AssertionError(f"could not parse frontmatter line: {line!r}")
        key, value = kv.group(1), kv.group(2).strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = value
            current_list_key = None
    return data


def _assert_common_worker_rules(testcase, path, contract_ref):
    """Shared assertions for every in-scope worker agent file: valid
    frontmatter with the mandatory keys, no AskUserQuestion tool, the
    contract-path reference, the single-structured-output statement, the
    read-only/no-commit/no-discovery/no-ask sentences, and the absence of
    the forbidden `# Task assignment` heading (NFR7).

    A fourth worker added later needs only one call to this helper plus its
    own worker-specific assertions.
    """
    text = _read(path)
    frontmatter_text, body_text = _split_frontmatter(text)
    frontmatter = _parse_flat_frontmatter(frontmatter_text)
    norm_text = _normalize_ws(text)

    # AC-1
    for key in REQUIRED_FRONTMATTER_KEYS:
        testcase.assertIn(
            key, frontmatter, f"{path.name}: missing required frontmatter key {key!r}"
        )
    tools = [t.strip() for t in frontmatter["tools"].split(",")]
    testcase.assertNotIn(
        "AskUserQuestion",
        tools,
        f"{path.name}: must not declare the AskUserQuestion tool",
    )

    # AC-2
    testcase.assertIn(contract_ref, text, f"{path.name}: missing contract path reference")
    testcase.assertIn(ENVELOPE_REF, text, f"{path.name}: missing common envelope path reference")
    testcase.assertIn(
        COMMON_SINGLE_OUTPUT_SUBSTRING,
        norm_text,
        f"{path.name}: missing the single-structured-output statement",
    )

    # AC-3
    testcase.assertIn(
        COMMON_READONLY_NOCOMMIT_SUBSTRING,
        norm_text,
        f"{path.name}: missing the workflow.yaml-read-only / never-commits statement",
    )
    testcase.assertIn(
        COMMON_NO_DISCOVERY_SUBSTRING,
        norm_text,
        f"{path.name}: missing the reads-only-supplied-paths statement",
    )
    testcase.assertIn(
        COMMON_NO_ASK_SUBSTRING,
        norm_text,
        f"{path.name}: missing the never-asks-the-user statement",
    )

    # AC-4
    testcase.assertIsNone(
        FORBIDDEN_TASK_ASSIGNMENT_HEADING.search(text),
        f"{path.name}: must not contain a '# Task assignment' heading (NFR7)",
    )

    return frontmatter, body_text


class TestFilesExist(unittest.TestCase):
    def test_requirements_analyst_exists(self):
        self.assertTrue(ANALYST_PATH.is_file(), f"expected {ANALYST_PATH} to exist")

    def test_spec_writer_exists(self):
        self.assertTrue(SPEC_WRITER_PATH.is_file(), f"expected {SPEC_WRITER_PATH} to exist")

    def test_rework_planner_exists(self):
        self.assertTrue(
            REWORK_PLANNER_PATH.is_file(), f"expected {REWORK_PLANNER_PATH} to exist"
        )


class TestRequirementsAnalystCommonRules(unittest.TestCase):
    def test_common_worker_rules(self):
        _assert_common_worker_rules(self, ANALYST_PATH, ANALYST_CONTRACT_REF)


class TestSpecWriterCommonRules(unittest.TestCase):
    def test_common_worker_rules(self):
        _assert_common_worker_rules(self, SPEC_WRITER_PATH, SPEC_WRITER_CONTRACT_REF)


class TestReworkPlannerCommonRules(unittest.TestCase):
    def test_common_worker_rules(self):
        _assert_common_worker_rules(self, REWORK_PLANNER_PATH, REWORK_PLANNER_CONTRACT_REF)


class TestRequirementsAnalystSpecifics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _normalize_ws(_read(ANALYST_PATH))

    # AC-5
    def test_documents_both_analysis_mode_values(self):
        self.assertIn("analysis_mode: full", self.text)
        self.assertIn("analysis_mode: design_system_detection", self.text)

    def test_documents_payload_difference_between_modes(self):
        # full mode's payload
        for field in (
            "resolved_requirements",
            "project_detection",
            "design_system_candidates",
        ):
            self.assertIn(field, self.text)
        # design_system_detection's restricted, exclusive payload
        self.assertIn("sole payload content", self.text)
        self.assertIn("validation error", self.text)

    def test_documents_restricted_status_set_for_backfill_mode(self):
        self.assertIn(
            "never returns `needs_user_input` and never returns a "
            "`question_packet`",
            self.text,
        )
        for status in ("completed", "blocked", "failed"):
            self.assertIn(status, self.text)

    def test_states_detects_without_deciding_kind(self):
        lowered = self.text.lower()
        self.assertIn("do not decide the project's `kind`", lowered)

    def test_requires_mode_echo(self):
        self.assertIn("mode_echo", self.text)
        self.assertIn("verbatim", self.text)

    def test_unresolved_points_become_questions_not_assumptions(self):
        lowered = self.text.lower()
        self.assertIn("question", lowered)
        self.assertIn(
            "never a silently-adopted assumption",
            self.text,
        )


class TestRequirementsAnalystToolGrantAndGateTable(unittest.TestCase):
    """task0019 AC-7 (tool grant) and AC-4 (prompt-side gate table)."""

    @classmethod
    def setUpClass(cls):
        cls.raw_text = _read(ANALYST_PATH)
        cls.frontmatter_text, cls.body_text = _split_frontmatter(cls.raw_text)
        cls.frontmatter = _parse_flat_frontmatter(cls.frontmatter_text)
        cls.normalized = _normalize_ws(cls.raw_text)

    def test_tools_does_not_grant_bash(self):
        tools = [t.strip() for t in self.frontmatter["tools"].split(",")]
        self.assertNotIn(
            "Bash",
            tools,
            "requirements-analyst.md must not grant Bash (never writes, "
            "never commits)",
        )

    def test_documents_gate_identifier_table(self):
        self.assertIn("gate_id", self.normalized)
        self.assertIn("create-spec.requirement-clarification", self.normalized)
        self.assertIn("create-spec.design-step", self.normalized)


class TestSpecWriterSpecifics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _normalize_ws(_read(SPEC_WRITER_PATH))

    # AC-6
    def test_states_never_invents_requirements_or_assumptions(self):
        lowered = self.text.lower()
        self.assertIn("never invent", lowered)
        self.assertIn("requirement", lowered)
        self.assertIn("assumption", lowered)

    def test_states_digest_disagreement_yields_blocked(self):
        self.assertIn("digest disagreement is always a `blocked` return", self.text)
        self.assertIn("blocking_reason", self.text)

    def test_never_returns_question_packet(self):
        self.assertIn("never return a `question_packet`", self.text)

    def test_documents_write_policy_actions(self):
        for action in (
            "create",
            "replace_own",
            "replace_authorized",
            "preserve",
            "extend_only",
            "regenerate",
        ):
            self.assertIn(action, self.text)

    def test_documents_targets_vs_allowed_write_roots_split(self):
        self.assertIn("allowed_write_roots", self.text)
        self.assertIn("targets", self.text)


class TestReworkPlannerSpecifics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _normalize_ws(_read(REWORK_PLANNER_PATH))

    # AC-7
    def test_states_plans_only_additional_tasks(self):
        self.assertIn(
            "you never rewrite the feature's existing plan", self.text
        )

    def test_emits_coverage_declaration(self):
        self.assertIn("rework_index", self.text)
        self.assertIn("covered_by_existing", self.text)
        self.assertIn("new_scenarios", self.text)
        self.assertIn(
            "BOTH empty is forbidden",
            self.text,
        )

    def test_emits_shared_contract_rationale(self):
        self.assertIn("shared_contract_rationale", self.text)

    def test_proposes_patch_instead_of_writing_workflow_yaml(self):
        self.assertIn("You never write `workflow.yaml`", self.text)
        self.assertIn("workflow_patch", self.text)
        self.assertIn("append_rework", self.text)

    def test_returns_question_for_spec_change(self):
        self.assertIn("rework.spec-change", self.text)
        self.assertIn("needs_user_input", self.text)
        self.assertIn("create no task", self.text)


class TestFrontmatterValidationCatchesMissingKeys(unittest.TestCase):
    """Proof that the shared frontmatter check is not vacuous (tdd-testing
    discipline): a fabricated frontmatter omitting `effort` or `model` must
    fail the same assertion the three real files pass.

    task0009.md Test Notes edge case: "frontmatter that parses but omits
    `effort` or `model` must fail, since those only take effect under Task
    dispatch and their absence would silently downgrade the worker."
    """

    def test_missing_effort_key_fails(self):
        frontmatter = _parse_flat_frontmatter(
            "name: example\ndescription: x\nmodel: best\ntools: Read"
        )
        with self.assertRaises(AssertionError):
            for key in REQUIRED_FRONTMATTER_KEYS:
                assert key in frontmatter, f"missing {key!r}"

    def test_missing_model_key_fails(self):
        frontmatter = _parse_flat_frontmatter(
            "name: example\ndescription: x\neffort: high\ntools: Read"
        )
        with self.assertRaises(AssertionError):
            for key in REQUIRED_FRONTMATTER_KEYS:
                assert key in frontmatter, f"missing {key!r}"

    def test_askuserquestion_in_tools_is_detected(self):
        frontmatter = _parse_flat_frontmatter(
            "name: example\ndescription: x\nmodel: best\neffort: high\n"
            "tools: Read, AskUserQuestion"
        )
        tools = [t.strip() for t in frontmatter["tools"].split(",")]
        self.assertIn("AskUserQuestion", tools)

    def test_task_assignment_heading_is_detected(self):
        fake_text = "---\nname: x\n---\n\n# Task assignment\n\nbody\n"
        self.assertIsNotNone(FORBIDDEN_TASK_ASSIGNMENT_HEADING.search(fake_text))


if __name__ == "__main__":
    unittest.main()
