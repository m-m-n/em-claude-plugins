"""Tests for em-workflow/references/batch-policies.yaml and the
batch-mode.md edit that migrates gate coverage into it.

- AC-4: batch-policies.yaml parses as YAML and its gate_policies key set
  equals the set of gate IDs listed in design-input.md 5.9, with no entry
  for `rework.spec-change`.
- AC-5: preserve_and_reuse / on_unavailable: abort are documented in
  comments.
- AC-6: batch-mode.md no longer contains the rework synthesis body or the
  Codex fallback detail, references the three new documents, and retains
  every non-packet decision it currently carries.

The YAML parsing below is a hand-rolled parser for the restricted subset
batch-policies.yaml actually uses (one top-level `gate_policies:` key,
2-space-indented gate IDs, 4-space-indented scalar `key: value` children;
no lists, no flow style, no anchors). PyYAML is a runtime dependency of the
em-workflow plugin, not a test dependency (IMPLEMENTATION.md, Technology
Stack), so tests must not import it.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "batch-policies.yaml"
)
DESIGN_PATH = os.path.join(
    REPO_ROOT, "feature-docs", "agent-separation", "design-input.md"
)
BATCH_MODE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "batch-mode.md"
)


def parse_gate_policies(text):
    """Parse the `gate_policies:` block out of a restricted-subset YAML
    text (see module docstring). Returns {gate_id: {key: value_str}}.

    Raises ValueError if no `gate_policies:` top-level key is found or if
    a line inside the block violates the expected 2/4-space nesting — this
    is what backs the "parses as YAML" assertion without needing PyYAML.
    """
    lines = text.splitlines()
    gate_policies = {}
    in_block = False
    current_gate = None
    saw_block = False

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not in_block:
            if line == "gate_policies:":
                in_block = True
                saw_block = True
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            # Dedent back to column 0: the gate_policies mapping ended.
            break
        if indent == 2:
            if not stripped.endswith(":"):
                raise ValueError(f"expected a gate-ID key, got: {raw!r}")
            current_gate = stripped[:-1]
            gate_policies[current_gate] = {}
        elif indent == 4:
            if current_gate is None or ":" not in stripped:
                raise ValueError(f"unexpected line in gate block: {raw!r}")
            key, _, value = stripped.partition(":")
            gate_policies[current_gate][key.strip()] = value.strip()
        else:
            raise ValueError(f"unexpected indentation: {raw!r}")

    if not saw_block:
        raise ValueError("no top-level `gate_policies:` key found")
    return gate_policies


def extract_design_input_gate_ids(design_text):
    """Extract the gate-ID set from design-input.md 5.9's `gate_policies`
    fenced YAML listing (the normative source batch-policies.yaml renders).
    """
    match = re.search(r"```yaml\n(gate_policies:.*?)\n```", design_text, re.DOTALL)
    if not match:
        raise AssertionError(
            "design-input.md 5.9 no longer has a `gate_policies:` fenced block"
        )
    return parse_gate_policies(match.group(1))


class TestBatchPoliciesYaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.policy_text = fh.read()
        with open(DESIGN_PATH, encoding="utf-8") as fh:
            cls.design_text = fh.read()
        cls.gate_policies = parse_gate_policies(cls.policy_text)
        cls.design_gate_policies = extract_design_input_gate_ids(cls.design_text)

    def test_parses_as_yaml(self):
        # parse_gate_policies raised nothing in setUpClass: the file parses.
        self.assertIsInstance(self.gate_policies, dict)
        self.assertGreater(len(self.gate_policies), 0)

    def test_gate_id_set_matches_design_input_listing(self):
        self.assertEqual(
            set(self.gate_policies.keys()),
            set(self.design_gate_policies.keys()),
        )

    def test_rework_spec_change_absent(self):
        self.assertNotIn("rework.spec-change", self.gate_policies)
        self.assertNotIn("rework.spec-change", self.design_gate_policies)

    def test_every_entry_has_an_action(self):
        for gate_id, attrs in self.gate_policies.items():
            self.assertIn("action", attrs, f"{gate_id} is missing `action`")

    def test_select_entries_carry_an_option_id(self):
        for gate_id, attrs in self.gate_policies.items():
            if attrs.get("action") == "select":
                self.assertIn(
                    "option_id", attrs, f"{gate_id} is `action: select` with no option_id"
                )

    def test_documents_preserve_and_reuse_meaning(self):
        self.assertIn("preserve_and_reuse", self.policy_text)
        # The comment block must explain what it means, not just name it.
        self.assertIn("authoritative", self.policy_text.lower())

    def test_documents_on_unavailable_abort_meaning(self):
        self.assertIn("on_unavailable: abort", self.policy_text)
        header = self.policy_text.split("gate_policies:", 1)[0]
        self.assertIn("on_unavailable", header)
        self.assertIn("abort", header)

    def test_documents_scope(self):
        header = self.policy_text.split("gate_policies:", 1)[0]
        self.assertIn("question packet", header.lower())
        self.assertIn("batch-mode.md", header)


class TestGateIdSetComparisonIsSymmetric(unittest.TestCase):
    """Edge case from the task plan: a gate ID present in one side but not
    the other must fail set equality regardless of which side it is
    invented on."""

    def test_invented_gate_in_actual_fails(self):
        actual = {"real.gate", "mytest.invented-gate"}
        expected = {"real.gate"}
        with self.assertRaises(AssertionError):
            self.assertEqual(actual, expected)

    def test_invented_gate_in_expected_fails(self):
        actual = {"real.gate"}
        expected = {"real.gate", "mytest.invented-gate"}
        with self.assertRaises(AssertionError):
            self.assertEqual(actual, expected)


# The pre-edit decision-table / fallback-paragraph coverage of
# batch-mode.md, captured as a fixture so the coverage-union assertion
# below is meaningful: every one of these must still be covered, either by
# a gate_policies entry (packet-based gate, migrated) or by a retained
# keyword in the edited batch-mode.md (non-packet gate).
ORIGINAL_COVERAGE = [
    ("Step 0 git-setup", None, "git-setup"),
    ("Step A feature selection", None, "feature selection"),
    ("Command approval gate", "create-spec.command-approval", None),
    ("create-spec interactive clarification", "create-spec.requirement-clarification", None),
    ("create-spec design-step decision", "create-spec.design-step", None),
    ("planner TBD resolution", "create-plan.tbd-resolution", None),
    ("planner license conflict", "create-plan.license-conflict", None),
    ("planner existing-files re-run", "create-plan.existing-files", None),
    ("implement I.2.c failed task", "implement.failed-task", None),
    ("review R4 conflict group", "review.auto-fix-conflict", None),
    ("review R4 needs-judgment", "review.auto-fix-judgment", None),
    ("review completion gate", "review.residual-critical-high", None),
    ("verify fail", "verify.failed", None),
    ("Step C completion choice", "develop.completion", None),
    ("review phase diff-size gate", None, "diff-size gate"),
    ("command-approval hook fallback (python3 missing)", None, "PreToolUse hook is inactive"),
]


class TestBatchModeMdMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(BATCH_MODE_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.gate_policies = parse_gate_policies(fh.read())

    def test_migrated_section_headings_are_gone(self):
        self.assertNotIn("## Fallback for gates not in the table", self.text)
        self.assertNotIn("## Rework task synthesis", self.text)

    def test_no_rework_synthesis_body(self):
        # Numbered steps that used to spell out task synthesis mechanics.
        self.assertNotIn("Number the task as the next", self.text)
        self.assertNotIn("failed_items", self.text)

    def test_no_codex_fallback_procedural_detail(self):
        self.assertNotIn("run_codex_exec.sh readonly", self.text)
        self.assertNotIn("stop at 5 turns max", self.text)

    def test_references_the_three_new_documents(self):
        self.assertIn("references/question-resolution.md", self.text)
        self.assertIn("references/batch-policies.yaml", self.text)
        self.assertIn("references/rework-task-synthesis.md", self.text)

    def test_coverage_union_matches_original(self):
        for label, gate_id, keyword in ORIGINAL_COVERAGE:
            if gate_id is not None:
                self.assertIn(
                    gate_id,
                    self.gate_policies,
                    f"{label!r} (gate_id {gate_id}) dropped from batch-policies.yaml",
                )
            if keyword is not None:
                self.assertIn(
                    keyword,
                    self.text,
                    f"{label!r} no longer retained in batch-mode.md",
                )


if __name__ == "__main__":
    unittest.main()
