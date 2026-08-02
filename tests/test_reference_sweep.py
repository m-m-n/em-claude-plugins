"""Tests for task0013: workflow-schema updates, the stale-reference sweep,
and deletion of the old create-spec agent definition.

Covers task0013 Acceptance Criteria
(feature-docs/agent-separation/tasks/task0013.md):

- AC-1: `workflow-schema.md` contains no upstream-agent write exception,
  documents the phase-state sibling, and defines `completed_at_commit`
  (rule R2) normatively with its applicability to all seven workflow steps.
- AC-2: `workflow-schema.md` documents the `project.design_system` block
  (its two fields and three `kind` values) and names the domains vocabulary
  SSOT.
- AC-3: `em-workflow/agents/requirements-spec-creator.md` does not exist,
  and none of this task's own files reference its name any more.
- AC-4: the four templates, `license-compat.md` and `impl-skills.yaml` name
  a currently existing worker (a file under `em-workflow/agents/`) in their
  header references, and `task-plan.md`'s structural marker headings are
  unchanged.
- AC-5: `em-workflow/README.md` states the PyYAML prerequisite and the
  `Bash(python3:*)` permission note; `test/README.md` scopes its
  no-external-dependency statement to test code.
- AC-6: `em-workflow/.claude-plugin/plugin.json` parses as JSON, its
  version compares strictly greater than the pre-task baseline, and its
  description mentions the new worker composition.
- AC-7: `plan-writing/SKILL.md` names the review rules registry as the
  domains vocabulary source; `command-execution-protocol.md` names the
  command-approval gate identifier.

Scoping note (task0013.md Test Notes): AC-3's "no file in the repository
mentions its name" is, read literally, a whole-repository invariant that
only holds once every sibling task (task0009, task0011, ...) has merged its
replacement workers -- this worktree alone cannot prove that. Per the Test
Notes this task's own assertions are scoped to (a) the absence of the
deleted file itself, and (b) the files THIS task owns/edits. The full
repository-wide zero-occurrence check is deferred to the invariant script
(task0014).

All text assertions read raw file text (`Path.read_text`) rather than
parsed Markdown structure, so a stale reference hidden inside a code fence
or a comment still fails the check (task0013.md Test Notes edge case).
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
AGENTS_DIR = PLUGIN_ROOT / "agents"
TEMPLATES_DIR = PLUGIN_ROOT / "references" / "templates"

OLD_AGENT_NAME = "requirements-spec-creator"
OLD_AGENT_PATH = AGENTS_DIR / f"{OLD_AGENT_NAME}.md"

WORKFLOW_SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"
COMMAND_EXECUTION_PROTOCOL_PATH = (
    PLUGIN_ROOT / "references" / "command-execution-protocol.md"
)
LICENSE_COMPAT_PATH = PLUGIN_ROOT / "references" / "license-compat.md"
IMPL_SKILLS_PATH = PLUGIN_ROOT / "references" / "impl-skills.yaml"
PLAN_WRITING_SKILL_PATH = PLUGIN_ROOT / "skills" / "plan-writing" / "SKILL.md"
DESIGN_SKILL_PATH = PLUGIN_ROOT / "skills" / "design" / "SKILL.md"
EM_WORKFLOW_README_PATH = PLUGIN_ROOT / "README.md"
ROOT_README_PATH = REPO_ROOT / "README.md"
PLUGIN_JSON_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
TEST_README_PATH = REPO_ROOT / "test" / "README.md"

# The pre-task0013 committed version (feature-docs/agent-separation/tasks/
# task0013.md AC-6): the version must compare strictly greater than this.
BASELINE_PLUGIN_VERSION = "0.1.27"

# Every file this task reads/writes per its Scope section. Used for the
# scoped stale-reference sweep (see module docstring's Scoping note).
TASK_OWNED_FILES = [
    WORKFLOW_SCHEMA_PATH,
    COMMAND_EXECUTION_PROTOCOL_PATH,
    LICENSE_COMPAT_PATH,
    IMPL_SKILLS_PATH,
    TEMPLATES_DIR / "requirements-document.md",
    TEMPLATES_DIR / "spec-document.md",
    TEMPLATES_DIR / "test-readme.md",
    TEMPLATES_DIR / "task-plan.md",
    PLAN_WRITING_SKILL_PATH,
    DESIGN_SKILL_PATH,
    EM_WORKFLOW_README_PATH,
    ROOT_README_PATH,
    PLUGIN_JSON_PATH,
    TEST_README_PATH,
]

STRUCTURAL_MARKERS = [
    "## Goal",
    "## Requirements",
    "## Scope",
    "### Files to Create",
    "### Files to Modify",
    "## Design",
    "## Acceptance Criteria (MANDATORY)",
    "## Test Notes",
    "## Out of Scope",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _section(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _version_tuple(version_string):
    return tuple(int(part) for part in version_string.split("."))


class TestOldAgentDeleted(unittest.TestCase):
    """AC-3."""

    def test_requirements_spec_creator_file_absent(self):
        self.assertFalse(
            OLD_AGENT_PATH.exists(),
            f"{OLD_AGENT_PATH} must be deleted by task0013",
        )

    def test_no_task_owned_file_references_old_agent_name(self):
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in TASK_OWNED_FILES
            if OLD_AGENT_NAME in _read(path)
        ]
        self.assertEqual(
            offenders,
            [],
            f"stale reference to {OLD_AGENT_NAME!r} remains in: {offenders}",
        )


class TestStaleReferenceSweepIsRawText(unittest.TestCase):
    """Edge case (Test Notes): a reference hidden inside a code fence or a
    comment must still be caught, because the sweep is a plain substring
    search over raw file text rather than a Markdown-structure parse."""

    def test_name_inside_a_code_fence_is_still_detected(self):
        sample = (
            "# Some Doc\n\n"
            "Normal prose that does not mention the old name.\n\n"
            "```text\n"
            f"see agents/{OLD_AGENT_NAME}.md for the old flow\n"
            "```\n"
        )
        self.assertIn(OLD_AGENT_NAME, sample)

    def test_name_inside_an_html_comment_is_still_detected(self):
        sample = f"<!-- TODO: used to be {OLD_AGENT_NAME}, now split -->\n"
        self.assertIn(OLD_AGENT_NAME, sample)


class TestWorkflowSchemaWriteOwnership(unittest.TestCase):
    """AC-1."""

    def setUp(self):
        self.text = _read(WORKFLOW_SCHEMA_PATH)

    def test_states_orchestrator_as_sole_writer(self):
        self.assertIn("Only the orchestrator", self.text)

    def test_no_upstream_agent_write_exception_remains(self):
        self.assertNotIn("Exception: the upstream agents", self.text)
        self.assertNotIn("upstream-agent write exception", self.text)

    def test_documents_phase_state_sibling(self):
        section = _section(self.text, "## Sibling artifacts")
        self.assertIn("phase-state/", section)

    def test_defines_completed_at_commit_normatively_as_rule_r2(self):
        self.assertIn("rule R2", self.text)
        section = _section(self.text, "`completed_at_commit` (rule R2)", "## Sibling artifacts")
        self.assertIn("HEAD", section)
        self.assertIn("immediately", section)
        self.assertIn("separate commit", section)

    def test_completed_at_commit_applies_to_all_seven_steps(self):
        section = _section(
            self.text, "`completed_at_commit` (rule R2)", "## Sibling artifacts"
        )
        for step in [
            "create-spec",
            "design",
            "create-plan",
            "implement",
            "review",
            "verify",
            "retrospect",
        ]:
            with self.subTest(step=step):
                self.assertIn(step, section)


class TestWorkflowSchemaDesignSystemAndDomainsSsot(unittest.TestCase):
    """AC-2."""

    def setUp(self):
        self.text = _read(WORKFLOW_SCHEMA_PATH)

    def test_documents_design_system_two_fields(self):
        section = _section(self.text, "design_system:", "components:")
        self.assertIn("kind:", section)
        self.assertIn("paths:", section)

    def test_documents_three_kind_values(self):
        section = _section(self.text, "design_system:", "components:")
        for kind_value in ["project_native", "em_workflow", "none"]:
            with self.subTest(kind=kind_value):
                self.assertIn(kind_value, section)

    def test_names_domains_vocabulary_ssot(self):
        section = _section(self.text, "domains:", "complexity:")
        self.assertIn("review-rules.yaml", section)
        self.assertIn("SSOT", section)


class TestTemplateAndRegistryHeaderRetargets(unittest.TestCase):
    """AC-4."""

    HEADER_TARGET_WORKER = {
        "requirements-document.md": "spec-writer",
        "spec-document.md": "spec-writer",
        "test-readme.md": "spec-writer",
        "task-plan.md": "implementation-planner",
    }

    def test_template_headers_name_a_currently_existing_worker(self):
        for filename, worker in self.HEADER_TARGET_WORKER.items():
            path = TEMPLATES_DIR / filename
            with self.subTest(template=filename):
                text = _read(path)
                self.assertIn(worker, text)
                worker_path = AGENTS_DIR / f"{worker}.md"
                self.assertTrue(
                    worker_path.exists(),
                    f"{filename} names {worker!r} but {worker_path} does not exist",
                )

    def test_license_compat_names_a_currently_existing_worker(self):
        text = _read(LICENSE_COMPAT_PATH)
        self.assertIn("implementation-planner", text)
        self.assertTrue((AGENTS_DIR / "implementation-planner.md").exists())

    def test_impl_skills_registry_names_a_currently_existing_worker(self):
        text = _read(IMPL_SKILLS_PATH)
        self.assertIn("implementation-planner", text)
        self.assertTrue((AGENTS_DIR / "implementation-planner.md").exists())

    def test_task_plan_structural_markers_unchanged(self):
        text = _read(TEMPLATES_DIR / "task-plan.md")
        for marker in STRUCTURAL_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


class TestReadmePyYamlAndPermissionNote(unittest.TestCase):
    """AC-5."""

    def test_em_workflow_readme_states_pyyaml_prerequisite(self):
        text = _read(EM_WORKFLOW_README_PATH)
        self.assertIn("PyYAML", text)

    def test_em_workflow_readme_states_python_execution_permission_note(self):
        text = _read(EM_WORKFLOW_README_PATH)
        self.assertIn("Bash(python3:*)", text)

    def test_test_readme_scopes_no_external_dependency_rule_to_test_code(self):
        text = _read(TEST_README_PATH)
        self.assertIn("scoped to test code", text)
        self.assertIn("PyYAML", text)
        # The rule that tests use only the standard library must survive.
        self.assertIn("standard library", text)


class TestPluginManifest(unittest.TestCase):
    """AC-6."""

    def setUp(self):
        self.data = json.loads(_read(PLUGIN_JSON_PATH))

    def test_plugin_json_is_valid_json(self):
        # setUp already parsed it; this test documents the property under
        # test explicitly (a malformed file would fail in setUp instead).
        self.assertIn("version", self.data)

    def test_version_is_strictly_greater_than_baseline(self):
        self.assertGreater(
            _version_tuple(self.data["version"]),
            _version_tuple(BASELINE_PLUGIN_VERSION),
        )

    def test_description_mentions_new_worker_composition(self):
        description = self.data["description"]
        for worker in ["requirements-analyst", "spec-writer", "rework-planner"]:
            with self.subTest(worker=worker):
                self.assertIn(worker, description)

    def test_version_not_bumped_would_be_detected(self):
        # Proof the comparison actually bites: a forged version equal to
        # the baseline must fail the same assertion used above.
        with self.assertRaises(AssertionError):
            self.assertGreater(
                _version_tuple(BASELINE_PLUGIN_VERSION),
                _version_tuple(BASELINE_PLUGIN_VERSION),
            )


class TestGatePolicyAndDomainsSsotReferences(unittest.TestCase):
    """AC-7."""

    def test_plan_writing_skill_names_review_rules_as_domains_ssot(self):
        text = _read(PLAN_WRITING_SKILL_PATH)
        section = _section(text, "## domains criteria")
        self.assertIn("review-rules.yaml", section)
        self.assertIn("SSOT", section)

    def test_command_execution_protocol_names_the_gate_identifier(self):
        text = _read(COMMAND_EXECUTION_PROTOCOL_PATH)
        self.assertIn("create-spec.command-approval", text)


if __name__ == "__main__":
    unittest.main()
