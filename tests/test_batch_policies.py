"""Tests for em-workflow/references/batch-policies.yaml, batch-mode.md and
the referrer sites that cite them (task0017 — round1.yaml findings as3/as4).

- AC-1: the eight orchestrator-opened, non-packet gates (implement.failed-
  task, review.auto-fix-conflict, review.auto-fix-judgment,
  review.residual-critical-high, verify.failed, develop.completion,
  design.artifact-overwrite, create-plan.artifact-overwrite) live in exactly
  one place — `references/batch-mode.md`'s Non-packet gates table — and are
  absent from `references/batch-policies.yaml`, matching the scope both
  documents' own headers/preambles state.
- AC-2: none of this task's owned files still names the deleted "batch-
  mode.md decision table".
- AC-3: batch-mode.md's general non-packet fallback explicitly yields to any
  default a phase protocol or batch-policies.yaml already states.
- AC-4: no owned file contains the string `requirements-spec-creator`.
- AC-5: plugin.json's description reflects that gate resolution splits
  across batch-policies.yaml (packet gates) and batch-mode.md (non-packet
  gates), rather than claiming every gate resolves per batch-mode.md alone.
- AC-6: gate-identifier coverage between batch-policies.yaml and this task's
  other owned documents, scoped to what is decidable without reading files
  sibling rework tasks are concurrently editing (create-spec-phase.md,
  create-plan-phase.md, contracts/*.md, question-resolution.md, etc. — the
  repository-wide version of this check is task0021's).

The YAML parsing below is a hand-rolled parser for the restricted subset
batch-policies.yaml actually uses (one top-level `gate_policies:` key,
2-space-indented gate IDs, 4-space-indented scalar `key: value` children;
no lists, no flow style, no anchors). PyYAML is a runtime dependency of the
em-workflow plugin, not a test dependency (IMPLEMENTATION.md, Technology
Stack), so tests must not import it.
"""

import json
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
IMPLEMENT_PHASE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "implement-phase.md"
)
REVIEW_PHASE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "review-phase.md"
)
SKILL_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md"
)
PLUGIN_JSON_PATH = os.path.join(
    REPO_ROOT, "em-workflow", ".claude-plugin", "plugin.json"
)

# Every file this task owns (task0017's `expected_files`, minus this test
# file itself). AC-2, AC-4 and AC-6 are scoped to exactly this set.
OWNED_DOC_PATHS = [
    POLICY_PATH,
    BATCH_MODE_PATH,
    IMPLEMENT_PHASE_PATH,
    REVIEW_PHASE_PATH,
    SKILL_PATH,
]

# The eight non-packet gates task0017 relocates from batch-policies.yaml
# back to batch-mode.md's Non-packet gates table, per
# feature-docs/agent-separation/reviews/round1.yaml finding as3. Hardcoded
# from the round record rather than derived from the files under test, so
# the relocation assertions below are not tautological.
RELOCATED_NON_PACKET_GATES = [
    "implement.failed-task",
    "review.auto-fix-conflict",
    "review.auto-fix-judgment",
    "review.residual-critical-high",
    "verify.failed",
    "develop.completion",
    "design.artifact-overwrite",
    "create-plan.artifact-overwrite",
]

# gate_ids intentionally left unlisted in batch-policies.yaml per its own
# header comment: `rework.spec-change` falls through to the unlisted-gate
# fallback by design. AC-6's "one documented intentional exception excluded
# from both directions".
INTENTIONAL_FALLBACK_EXCEPTION = "rework.spec-change"

# gate_ids that remain in batch-policies.yaml (packet gates) but whose only
# referrer is a file this task does not own (create-spec-phase.md,
# create-plan-phase.md) — sibling rework tasks edit those concurrently, so
# AC-6's coverage check here does not assert anything about them (task0021
# does the repository-wide version). Two packet gates ARE also named inside
# this task's owned files (create-spec.design-system in SKILL.md,
# create-spec.command-approval in SKILL.md/implement-phase.md); those are
# asserted directly below instead of listed here.
KNOWN_EXTERNAL_ONLY_PACKET_GATES = {
    "create-spec.feature-identity",
    "create-spec.requirement-clarification",
    "create-spec.design-step",
    "create-spec.artifact-overwrite",
    "create-spec.stalled",
    "create-plan.tbd-resolution",
    "create-plan.license-conflict",
    "create-plan.existing-files",
    "design-system.reclassify",
}


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

    def test_gate_id_set_matches_design_input_minus_relocated(self):
        # design-input.md 5.9's own illustrative example still lists all
        # nineteen gates (it is fixed, out-of-scope reference material this
        # task cannot edit); the corrected jurisdiction — the direction both
        # this file's header and question-resolution.md's batch resolution
        # sequence already state — removes exactly the eight relocated
        # non-packet gates from batch-policies.yaml. AC-1.
        expected = set(self.design_gate_policies.keys()) - set(
            RELOCATED_NON_PACKET_GATES
        )
        self.assertEqual(set(self.gate_policies.keys()), expected)

    def test_relocated_gates_absent_from_policy_file(self):
        # AC-1 / AC-6 direction 1: none of the eight relocated gates is a
        # batch-policies.yaml entry.
        for gate_id in RELOCATED_NON_PACKET_GATES:
            self.assertNotIn(
                gate_id,
                self.gate_policies,
                f"{gate_id} must live only in batch-mode.md's Non-packet gates table",
            )

    def test_rework_spec_change_absent(self):
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.gate_policies)
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.design_gate_policies)

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


# Packet gates: expected as batch-policies.yaml entries, keyed by gate_id.
PACKET_GATE_COVERAGE = [
    ("Command approval gate", "create-spec.command-approval"),
    ("create-spec interactive clarification", "create-spec.requirement-clarification"),
    ("create-spec design-step decision", "create-spec.design-step"),
    ("planner TBD resolution", "create-plan.tbd-resolution"),
    ("planner license conflict", "create-plan.license-conflict"),
    ("planner existing-files re-run", "create-plan.existing-files"),
]

# Non-packet gates: expected as literal gate-ID (or descriptive keyword)
# mentions inside batch-mode.md, NEVER as batch-policies.yaml entries. The
# eight task0017 relocates are included here, restoring the coverage the
# pre-rework version of this test wrongly required in the policy file.
NON_PACKET_GATE_COVERAGE = [
    ("Step 0 git-setup", "git-setup"),
    ("Step A feature selection", "feature selection"),
    ("review phase diff-size gate", "diff-size gate"),
    ("command-approval hook fallback (python3 missing)", "PreToolUse hook is inactive"),
    ("implement I.2.c failed task", "implement.failed-task"),
    ("review R4 conflict group", "review.auto-fix-conflict"),
    ("review R4 needs-judgment", "review.auto-fix-judgment"),
    ("review completion gate", "review.residual-critical-high"),
    ("verify fail", "verify.failed"),
    ("Step C completion choice", "develop.completion"),
    ("design artifact-overwrite precondition", "design.artifact-overwrite"),
    ("create-plan artifact-overwrite precondition", "create-plan.artifact-overwrite"),
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
        for label, gate_id in PACKET_GATE_COVERAGE:
            self.assertIn(
                gate_id,
                self.gate_policies,
                f"{label!r} (gate_id {gate_id}) dropped from batch-policies.yaml",
            )
        for label, keyword in NON_PACKET_GATE_COVERAGE:
            self.assertIn(
                keyword,
                self.text,
                f"{label!r} no longer retained in batch-mode.md",
            )

    def test_relocated_gates_not_also_left_in_policy_file(self):
        # AC-1: exactly one place. A relocated gate id must not be present
        # on both sides at once.
        for gate_id in RELOCATED_NON_PACKET_GATES:
            self.assertIn(gate_id, self.text)
            self.assertNotIn(gate_id, self.gate_policies)

    def test_rework_spec_change_not_named_in_batch_mode(self):
        # AC-6's "one documented intentional exception excluded from both
        # directions": rework.spec-change resolves via the unlisted-gate
        # fallback (question-resolution.md), not via a batch-mode.md row.
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.text)


class TestCatchAllYieldsToDocumentedDefaults(unittest.TestCase):
    """AC-3: the general non-packet fallback in batch-mode.md must not be
    able to override a default a phase protocol or batch-policies.yaml
    already states for its own gate."""

    @classmethod
    def setUpClass(cls):
        with open(BATCH_MODE_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()

    def _catch_all_paragraph(self):
        marker = "Any other non-packet `AskUserQuestion` site"
        idx = self.text.find(marker)
        self.assertNotEqual(idx, -1, "catch-all paragraph not found in batch-mode.md")
        return self.text[idx : idx + 800]

    def test_catch_all_explicitly_yields(self):
        paragraph = self._catch_all_paragraph()
        self.assertIn("NEVER overrides", paragraph)
        self.assertIn("phase protocol", paragraph)
        self.assertIn("batch-policies.yaml", paragraph)

    def test_catch_all_still_covers_unlisted_gates(self):
        paragraph = self._catch_all_paragraph()
        self.assertIn("Codex consultation", paragraph)
        self.assertIn("minimum-side-effect", paragraph)


class TestNoStaleDecisionTableReference(unittest.TestCase):
    """AC-2: no owned file names the deleted batch-mode.md decision table
    (the pre-restructure single table that has since split into
    batch-policies.yaml + batch-mode.md's much smaller Non-packet gates
    table)."""

    def test_no_decision_table_phrase_in_owned_files(self):
        for path in OWNED_DOC_PATHS:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn(
                "decision table",
                text.lower(),
                f"{path} still names the deleted batch-mode.md decision table",
            )
            self.assertNotIn(
                "決定表",
                text,
                f"{path} still names the deleted batch-mode.md decision table (JP)",
            )


class TestNoStaleAgentReference(unittest.TestCase):
    """AC-4: no owned file names the deleted requirements-spec-creator
    agent (round1.yaml finding as4)."""

    def test_requirements_spec_creator_absent(self):
        for path in OWNED_DOC_PATHS + [PLUGIN_JSON_PATH]:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn(
                "requirements-spec-creator",
                text,
                f"{path} still names the deleted requirements-spec-creator agent",
            )

    def test_diff_size_gate_row_repoints_to_unlisted_gate_fallback(self):
        # Scoped to the diff-size gate's OWN table row (not just "somewhere
        # in the file") so this assertion is meaningful: the row itself must
        # name the unlisted-gate fallback procedure, not merely coexist with
        # that phrase elsewhere in the document.
        with open(BATCH_MODE_PATH, encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(r"^\|.*diff-size gate.*\|$", text, re.MULTILINE)
        self.assertIsNotNone(match, "diff-size gate row not found in batch-mode.md")
        row = match.group(0)
        self.assertNotIn("requirements-spec-creator", row)
        self.assertIn("question-resolution.md", row)
        self.assertIn("unlisted-gate fallback", row)


class TestPluginDescriptionReflectsGateJurisdiction(unittest.TestCase):
    """AC-5: plugin.json's description must not claim every batch gate
    resolves per batch-mode.md alone."""

    @classmethod
    def setUpClass(cls):
        with open(PLUGIN_JSON_PATH, encoding="utf-8") as fh:
            cls.manifest = json.load(fh)
        cls.description = cls.manifest["description"]

    def test_parses_as_json(self):
        self.assertIn("description", self.manifest)

    def test_does_not_overclaim_batch_mode_alone(self):
        self.assertNotIn(
            "every AskUserQuestion gate resolves mechanically per references/batch-mode.md",
            self.description,
        )

    def test_names_both_gate_jurisdiction_documents(self):
        self.assertIn("batch-policies.yaml", self.description)
        self.assertIn("batch-mode.md", self.description)


class TestGateIdCoverageWithinOwnedFiles(unittest.TestCase):
    """AC-6, scoped per AC-7 to the files task0017 owns. The repository-wide
    bidirectional gate-ID coverage check (spanning create-spec-phase.md,
    create-plan-phase.md, contracts/*.md and question-resolution.md, all
    edited concurrently by sibling rework tasks) is task0021's."""

    @classmethod
    def setUpClass(cls):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.gate_policies = parse_gate_policies(fh.read())
        cls.other_owned_text = ""
        for path in (BATCH_MODE_PATH, IMPLEMENT_PHASE_PATH, REVIEW_PHASE_PATH, SKILL_PATH):
            with open(path, encoding="utf-8") as fh:
                cls.other_owned_text += "\n" + fh.read()

    def test_relocated_gates_referenced_only_outside_the_policy_file(self):
        for gate_id in RELOCATED_NON_PACKET_GATES:
            self.assertNotIn(gate_id, self.gate_policies)
            self.assertIn(
                gate_id,
                self.other_owned_text,
                f"{gate_id} has no referrer among task0017's owned documents",
            )

    def test_packet_gates_named_within_owned_files_have_policy_entries(self):
        # The two packet gates this task's non-yaml owned files actually
        # name (the rest of batch-policies.yaml's entries are referenced
        # only from files this task does not own, per
        # KNOWN_EXTERNAL_ONLY_PACKET_GATES, and are out of scope here).
        for gate_id in ("create-spec.design-system", "create-spec.command-approval"):
            self.assertIn(gate_id, self.other_owned_text)
            self.assertIn(gate_id, self.gate_policies)

    def test_known_external_only_entries_are_still_declared_in_policy(self):
        # Sanity check on the fixture itself: every gate id this test
        # deliberately does not evaluate against the owned files must still
        # be a real, current batch-policies.yaml entry -- otherwise the
        # exclusion list is silently hiding a real coverage gap.
        for gate_id in KNOWN_EXTERNAL_ONLY_PACKET_GATES:
            self.assertIn(gate_id, self.gate_policies)

    def test_intentional_exception_excluded_from_both_directions(self):
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.gate_policies)
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.other_owned_text)


if __name__ == "__main__":
    unittest.main()
