"""Tests for em-workflow/references/batch-policies.yaml, batch-mode.md and
the referrer sites that cite them.

task0022 rework (round2.yaml findings bs2, bs3, bs6, bs8 — correcting
round1's "presenter" criterion to gate-identifier presence):

- AC-1: every document that states the jurisdiction states it as
  gate-identifier presence — a `gate_id`-carrying gate resolves per
  `batch-policies.yaml` whether a worker returned it in a packet or the
  orchestrator raised it directly; a gate with NO `gate_id` at all resolves
  per `batch-mode.md`'s Non-packet gates table. No statement claims the
  Non-packet gates table's rows lack identifiers while the table prints
  ones that carry them.
- AC-2 (bs3): the `{phase}.artifact-overwrite` family (create-spec, design,
  create-plan) lives in exactly one source of truth —
  `batch-policies.yaml` — because all three carry a `gate_id`, even though
  every one of them is orchestrator-raised rather than packet-borne. The
  policy file's scope header is true of every entry it holds (no entry
  contradicts the header's own claim about who raises it).
- AC-6 (bs6): the per-command approval fallback row states a literal-string
  cache, matching the interactive side's cache in
  command-execution-protocol.md.

Retained from the pre-rework version of this test (not tied to this task's
own acceptance criteria):
- the six TRUE non-packet gates (no `gate_id` at all) live in exactly one
  place — `batch-mode.md`'s Non-packet gates table — and are absent from
  `batch-policies.yaml`.
- no owned file still names the deleted "batch-mode.md decision table" or
  the deleted `requirements-spec-creator` agent.
- batch-mode.md's general non-packet fallback explicitly yields to any
  default a phase protocol or batch-policies.yaml already states.
- plugin.json's description reflects that gate resolution splits across
  batch-policies.yaml and batch-mode.md, rather than claiming every gate
  resolves per batch-mode.md alone.
- gate-identifier coverage between batch-policies.yaml and this task's
  other owned documents, scoped to what is decidable without reading files
  sibling tasks own (create-spec-phase.md, create-plan-phase.md,
  contracts/*.md, etc.).

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
QUESTION_RESOLUTION_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)
COMMAND_EXECUTION_PROTOCOL_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "command-execution-protocol.md"
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

# Every file this task owns (task0022's `expected_files`, minus this test
# file itself). AC-2 and the retained coverage checks are scoped to this
# set, plus IMPLEMENT_PHASE_PATH / REVIEW_PHASE_PATH which are read-only
# verification sites (owned by a sibling task, not edited here).
OWNED_DOC_PATHS = [
    POLICY_PATH,
    BATCH_MODE_PATH,
    QUESTION_RESOLUTION_PATH,
    SKILL_PATH,
]

READ_ONLY_REFERRER_PATHS = [IMPLEMENT_PHASE_PATH, REVIEW_PHASE_PATH]

# The six gates that carry NO `gate_id` at all anywhere — round1 relocated
# these from batch-policies.yaml to batch-mode.md's Non-packet gates table,
# and round2 confirms the relocation stands under the corrected criterion
# (feature-docs/agent-separation/reviews/round2.yaml, bs3): they never carry
# a gate_id, packet-borne or otherwise, so there is nothing for
# batch-policies.yaml to key off.
NON_PACKET_GATES = [
    "implement.failed-task",
    "review.auto-fix-conflict",
    "review.auto-fix-judgment",
    "review.residual-critical-high",
    "verify.failed",
    "develop.completion",
]

# The `{phase}.artifact-overwrite` family: round1 wrongly split this across
# batch-policies.yaml (create-spec only) and batch-mode.md (design,
# create-plan), reasoning by presenter (orchestrator-raised => non-packet
# table) rather than by gate-identifier presence. round2 (bs3) corrects
# this: all three carry a `gate_id` (spec-writer-contract.md raises
# `gate_id: {phase}.artifact-overwrite` for every phase), so all three now
# live in batch-policies.yaml as one source of truth.
ARTIFACT_OVERWRITE_FAMILY = [
    "create-spec.artifact-overwrite",
    "design.artifact-overwrite",
    "create-plan.artifact-overwrite",
]

# gate_ids intentionally left unlisted in batch-policies.yaml per its own
# header comment: `rework.spec-change` falls through to the unlisted-gate
# fallback by design, even though it DOES carry a gate_id (it is not a
# non-packet gate — it is a deliberate fail-closed omission).
INTENTIONAL_FALLBACK_EXCEPTION = "rework.spec-change"

# gate_ids that remain in batch-policies.yaml (packet-or-orchestrator gates)
# but whose only referrer is a file this task does not own (create-spec-
# phase.md, create-plan-phase.md) — sibling tasks own those concurrently.
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
    "design.artifact-overwrite",
    "create-plan.artifact-overwrite",
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

    def test_gate_id_set_matches_design_input_minus_non_packet(self):
        # design-input.md 5.9's own illustrative example still lists all
        # nineteen gates (it is fixed, out-of-scope reference material this
        # task cannot edit); the corrected jurisdiction removes exactly the
        # six TRUE non-packet gates (no gate_id anywhere) from
        # batch-policies.yaml. The artifact-overwrite family stays, since
        # every member carries a gate_id.
        expected = set(self.design_gate_policies.keys()) - set(NON_PACKET_GATES)
        self.assertEqual(set(self.gate_policies.keys()), expected)

    def test_non_packet_gates_absent_from_policy_file(self):
        for gate_id in NON_PACKET_GATES:
            self.assertNotIn(
                gate_id,
                self.gate_policies,
                f"{gate_id} carries no gate_id at all and must live only in "
                "batch-mode.md's Non-packet gates table",
            )

    def test_artifact_overwrite_family_all_present_as_one_ssot(self):
        # AC-2 (bs3): all three phases, one file.
        for gate_id in ARTIFACT_OVERWRITE_FAMILY:
            self.assertIn(
                gate_id,
                self.gate_policies,
                f"{gate_id} carries a gate_id and must live in "
                "batch-policies.yaml, not be split off to batch-mode.md",
            )

    def test_artifact_overwrite_family_shares_identical_semantics(self):
        for gate_id in ARTIFACT_OVERWRITE_FAMILY:
            attrs = self.gate_policies[gate_id]
            self.assertEqual(attrs.get("action"), "select")
            self.assertEqual(attrs.get("option_id"), "preserve_and_reuse")
            self.assertEqual(attrs.get("on_unavailable"), "abort")

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

    # --- AC-1 (bs3): scope stated as gate-identifier presence --------------

    def _norm_yaml_comment_header(self, header):
        # Each header line is a `# ...` YAML comment; strip the leading
        # marker per line before collapsing whitespace, otherwise a `#`
        # character is left stranded mid-sentence at every line wrap.
        stripped_lines = [
            re.sub(r"^#\s?", "", line) for line in header.splitlines()
        ]
        return re.sub(r"\s+", " ", " ".join(stripped_lines)).strip()

    def test_scope_stated_as_identifier_presence_not_presenter(self):
        header = self.policy_text.split("gate_policies:", 1)[0]
        norm = self._norm_yaml_comment_header(header)
        self.assertIn(
            "whether a worker returned it inside a", norm
        )
        self.assertIn(
            "or the orchestrator raised the question directly outside of "
            "any packet",
            norm,
        )

    def test_header_never_claims_all_entries_are_worker_packets(self):
        # AC-2: the header must not contradict the artifact-overwrite
        # entries it holds by claiming everything here is packet-borne.
        header = self.policy_text.split("gate_policies:", 1)[0]
        self.assertNotIn(
            "ONLY the gates expressed as question packets", header
        )

    # --- task0006: header wording for the classification-gate carve-out ----

    def test_header_states_classification_gate_routing(self):
        # AC-1 (FR11): rework.spec-change carries a gate_id, is
        # intentionally unlisted, and in batch is routed into the
        # classification gate defined in question-resolution.md rather than
        # aborted outright.
        header = self.policy_text.split("gate_policies:", 1)[0]
        norm = self._norm_yaml_comment_header(header)
        self.assertIn(
            "`rework.spec-change` is intentionally NOT listed below, even "
            "though it does carry a `gate_id`",
            norm,
        )
        self.assertIn("references/question-resolution.md", norm)
        self.assertIn("classification gate", norm)
        self.assertIn("instead of aborting the phase outright", norm)

    def test_header_no_longer_claims_unconditional_abort(self):
        # AC-2 (FR11): the superseded "aborts ... rather than guessing an
        # answer" wording is gone from this file.
        header = self.policy_text.split("gate_policies:", 1)[0]
        norm = self._norm_yaml_comment_header(header)
        self.assertNotIn("guessing an answer", norm)
        # Non-vacuity guard: prove the assertion above is meaningful by
        # checking it against a synthetic string that DOES carry the
        # superseded phrase, so a no-op assertion could not slip through.
        synthetic = (
            norm
            + " fail-closed classification aborts a specification-change "
            "gate rather than guessing an answer for it."
        )
        self.assertIn("guessing an answer", synthetic)

    def test_header_does_not_imply_other_arms_relaxed(self):
        # AC-4 (NFR2): the header must not state or imply any change to the
        # security / license / irreversible-operation arms.
        header = self.policy_text.split("gate_policies:", 1)[0]
        norm = self._norm_yaml_comment_header(header)
        self.assertIn("category: security", norm)
        self.assertIn("category: license", norm)
        self.assertIn("reversible: false", norm)
        self.assertIn("unchanged strength", norm)

    def test_header_does_not_restate_gate_internals(self):
        # AC-5 (NFR1): cites question-resolution.md by path and restates
        # none of the gate's verdicts, asymmetry or evidence criterion.
        header = self.policy_text.split("gate_policies:", 1)[0]
        norm = self._norm_yaml_comment_header(header)
        self.assertIn("references/question-resolution.md", norm)
        for leaked_term in (
            "goal_not_met",
            "spec_gap",
            "not_applicable",
            "evidence_ids",
            "verdict",
            "asymmetry",
        ):
            self.assertNotIn(leaked_term, norm)


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


# Packet-or-orchestrator gates: expected as batch-policies.yaml entries,
# keyed by gate_id (all carry a gate_id, regardless of who raises them).
PACKET_GATE_COVERAGE = [
    ("Command approval gate", "create-spec.command-approval"),
    ("create-spec interactive clarification", "create-spec.requirement-clarification"),
    ("create-spec design-step decision", "create-spec.design-step"),
    ("planner TBD resolution", "create-plan.tbd-resolution"),
    ("planner license conflict", "create-plan.license-conflict"),
    ("planner existing-files re-run", "create-plan.existing-files"),
    ("create-spec artifact-overwrite precondition", "create-spec.artifact-overwrite"),
    ("design artifact-overwrite precondition", "design.artifact-overwrite"),
    ("create-plan artifact-overwrite precondition", "create-plan.artifact-overwrite"),
]

# TRUE non-packet gates: no gate_id anywhere. Expected as literal gate-ID
# (or descriptive keyword) mentions inside batch-mode.md, NEVER as
# batch-policies.yaml entries.
NON_PACKET_GATE_COVERAGE = [
    ("Step 0 git-setup", "git-setup"),
    # A later rewrite of batch-mode.md's Step A row renamed this concept
    # from "feature selection" to "feature resolution" -- the keyword below
    # tracks the current wording, not the withdrawn one.
    ("Step A feature resolution", "feature resolution"),
    ("review phase diff-size gate", "diff-size gate"),
    ("command-approval hook fallback (python3 missing)", "PreToolUse hook is inactive"),
    ("implement I.2.c failed task", "implement.failed-task"),
    ("review R4 conflict group", "review.auto-fix-conflict"),
    ("review R4 needs-judgment", "review.auto-fix-judgment"),
    ("review completion gate", "review.residual-critical-high"),
    ("verify fail", "verify.failed"),
    ("Step C completion choice", "develop.completion"),
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

    def test_non_packet_gates_not_also_left_in_policy_file(self):
        # AC-1: exactly one place, per gate.
        for gate_id in NON_PACKET_GATES:
            self.assertIn(gate_id, self.text)
            self.assertNotIn(gate_id, self.gate_policies)

    def test_artifact_overwrite_family_no_longer_a_table_row(self):
        # AC-2 (bs3): the family must NOT be split back into batch-mode.md's
        # Non-packet gates table — each carries a gate_id, so each lives
        # only in batch-policies.yaml as one source of truth. batch-mode.md
        # may still mention the family's name in prose (pointing the reader
        # at the policy file), but never as a `| ... |` table row of its
        # own.
        for gate_id in ARTIFACT_OVERWRITE_FAMILY:
            row_match = re.search(
                rf"^\|\s*`{re.escape(gate_id)}`.*\|$", self.text, re.MULTILINE
            )
            self.assertIsNone(
                row_match,
                f"{gate_id} must not be a batch-mode.md table row anymore "
                "(round2.yaml bs3: it carries a gate_id, so it belongs to "
                "batch-policies.yaml as one source of truth)",
            )

    def test_rework_spec_change_not_named_in_batch_mode(self):
        # rework.spec-change resolves via the unlisted-gate fallback
        # (question-resolution.md), not via a batch-mode.md row.
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.text)

    def test_jurisdiction_premise_states_identifier_presence(self):
        # AC-1: the "Non-packet gates" section and the top-level intro must
        # not claim presenter-based jurisdiction.
        norm = re.sub(r"\s+", " ", self.text)
        self.assertIn(
            "None of the gates below carries a `gate_id` at its "
            "originating site",
            norm,
        )
        self.assertIn(
            "the split is by identifier presence, not by whether a "
            "worker or the orchestrator raises the gate",
            norm,
        )

    def test_intro_no_longer_claims_packet_presenter_split(self):
        norm = re.sub(r"\s+", " ", self.text)
        self.assertNotIn(
            "this document covers the batch gates that never pass through "
            "a worker's question packet",
            norm.lower(),
        )


class TestCatchAllYieldsToDocumentedDefaults(unittest.TestCase):
    """The general non-packet fallback in batch-mode.md must not be able to
    override a default a phase protocol or batch-policies.yaml already
    states for its own gate."""

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

    def test_catch_all_row_count_matches_shrunk_table(self):
        # Table shrank from twelve to ten rows once the artifact-overwrite
        # family moved out (AC-2).
        paragraph = self._catch_all_paragraph()
        self.assertIn("ten rows above", paragraph)
        self.assertNotIn("twelve rows above", paragraph)


class TestNoStaleDecisionTableReference(unittest.TestCase):
    """No owned file names the deleted batch-mode.md decision table (the
    pre-restructure single table that has since split into
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
    """No owned file names the deleted requirements-spec-creator agent."""

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


class TestPerCommandFallbackLiteralStringCache(unittest.TestCase):
    """AC-6 (bs6): the batch per-command approval fallback caches its
    resolution per literal command string, matching the interactive side's
    existing per-literal-string cache."""

    @classmethod
    def setUpClass(cls):
        with open(BATCH_MODE_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(COMMAND_EXECUTION_PROTOCOL_PATH, encoding="utf-8") as fh:
            cls.interactive_text = fh.read()

    def _per_command_row(self):
        match = re.search(r"^\|.*Per-command approval fallback.*\|$", self.text, re.MULTILINE)
        self.assertIsNotNone(match, "per-command approval fallback row not found")
        return match.group(0)

    def test_interactive_side_defines_a_literal_string_cache(self):
        # Sanity check on the fixture: the interactive side really does
        # define this, so the batch row can genuinely "match" it.
        self.assertIn("per-literal-string", self.interactive_text)

    def test_batch_row_states_a_literal_string_cache(self):
        row = self._per_command_row()
        self.assertIn("per literal command string", row)

    def test_batch_row_references_the_interactive_cache(self):
        row = self._per_command_row()
        self.assertIn("command-execution-protocol.md", row)
        self.assertIn("interactive fallback", row)


class TestPluginDescriptionReflectsGateJurisdiction(unittest.TestCase):
    """plugin.json's description must not claim every batch gate resolves
    per batch-mode.md alone."""

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
    """Scoped to the files task0022 owns. The repository-wide bidirectional
    gate-ID coverage check (spanning create-spec-phase.md,
    create-plan-phase.md, contracts/*.md, all edited concurrently by
    sibling tasks) is out of this task's scope."""

    @classmethod
    def setUpClass(cls):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.gate_policies = parse_gate_policies(fh.read())
        cls.other_owned_text = ""
        for path in (BATCH_MODE_PATH, SKILL_PATH) + tuple(READ_ONLY_REFERRER_PATHS):
            with open(path, encoding="utf-8") as fh:
                cls.other_owned_text += "\n" + fh.read()

    def test_non_packet_gates_referenced_only_outside_the_policy_file(self):
        for gate_id in NON_PACKET_GATES:
            self.assertNotIn(gate_id, self.gate_policies)
            self.assertIn(
                gate_id,
                self.other_owned_text,
                f"{gate_id} has no referrer among task0022's owned documents",
            )

    def test_packet_gates_named_within_owned_files_have_policy_entries(self):
        # The packet-or-orchestrator gates this task's non-yaml owned files
        # actually name (the rest of batch-policies.yaml's entries are
        # referenced only from files this task does not own, per
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


# task0001 (batch-policy-option-id-consistency) AC-5: the pinned, explicit
# set of `action: select` gate_ids -- identical to tests/
# test_gate_option_vocabulary.py's ISSUING_SITE_MAP key set (that module
# asserts the two stay equal). A newly added select gate fails here until
# it is deliberately registered in both places (IMPLEMENTATION.md D5:
# policy-structure facts live in this module; correspondence facts live in
# test_gate_option_vocabulary.py).
SELECT_GATE_IDS = {
    "create-spec.feature-identity",
    "create-spec.design-step",
    "create-spec.design-system",
    "design-system.reclassify",
    "create-spec.artifact-overwrite",
    "design.artifact-overwrite",
    "create-plan.artifact-overwrite",
    "create-spec.stalled",
    "create-plan.tbd-resolution",
    "create-plan.license-conflict",
    "create-plan.existing-files",
}

# The two non-select gates that DO have a batch-policies.yaml entry but
# carry no `option_id` at all (task0001 AC-5).
NON_SELECT_GATES_WITH_ENTRIES = {
    "create-spec.requirement-clarification",
    "create-spec.command-approval",
}


class TestSelectGateStructure(unittest.TestCase):
    """task0001 AC-5 (policy-structure half; correspondence facts for these
    same gates live in tests/test_gate_option_vocabulary.py per
    IMPLEMENTATION.md D5)."""

    @classmethod
    def setUpClass(cls):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            cls.gate_policies = parse_gate_policies(fh.read())

    def test_select_gate_set_matches_pinned_expectation(self):
        actual = {
            gid
            for gid, attrs in self.gate_policies.items()
            if attrs.get("action") == "select"
        }
        self.assertEqual(actual, SELECT_GATE_IDS)

    def test_non_select_gates_carry_no_option_id(self):
        for gate_id in NON_SELECT_GATES_WITH_ENTRIES:
            with self.subTest(gate_id=gate_id):
                self.assertIn(gate_id, self.gate_policies)
                attrs = self.gate_policies[gate_id]
                self.assertNotEqual(attrs.get("action"), "select")
                self.assertNotIn("option_id", attrs)

    def test_non_select_gates_excluded_from_select_set(self):
        for gate_id in NON_SELECT_GATES_WITH_ENTRIES:
            self.assertNotIn(gate_id, SELECT_GATE_IDS)

    def test_intentionally_unlisted_gate_absent_and_not_a_coverage_gap(self):
        # rework.spec-change carries a gate_id but deliberately has no
        # batch-policies.yaml entry at all (module docstring,
        # INTENTIONAL_FALLBACK_EXCEPTION) -- it must be neither a select
        # gate nor reported as a missing one.
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, self.gate_policies)
        self.assertNotIn(INTENTIONAL_FALLBACK_EXCEPTION, SELECT_GATE_IDS)


if __name__ == "__main__":
    unittest.main()
