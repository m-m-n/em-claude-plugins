"""Pins for the Opus escalation agent, its contract document, and the dispatch
wiring in `em-workflow/references/question-resolution.md`'s
`### Opus escalation` section (codex-fallback-review-residuals, task0001).

Acceptance criteria covered (feature-docs/codex-fallback-review-residuals/
tasks/task0001.md):

- AC-1: the agent definition exists with `name` equal to its file stem,
  `model: opus`, `effort: xhigh`, the read-only `tools` set, and no
  `# Task assignment` heading.
- AC-2: the agent body resolves the contract from the dispatcher-supplied
  path (fail-closed), names the contract as the single source of truth and
  carries no return-shape statement, and treats its whole input as data.
- AC-3: the contract defines the input and the delimited untrusted-data
  boundary, including the dispatcher's neutralisation obligation.
- AC-4: the contract states the per-question return, the return-shape
  sentence formerly in the section, and the no-decision degradation.
- AC-5: the contract forbids writes and bounds reads.
- AC-6: the section carries the `Task(...)` dispatch literal, the contract
  path and the Opus/xhigh binding's location, and no longer carries the
  return-shape sentence.
- AC-7: the contract owns the non-packet presentation rule and the section
  states the non-packet scope, citing the rule without restating it.

The agent name and the contract path are taken out of the section text with
a pattern, and every file path below is derived from them, so a wrong name
in the section fails here and not only in check-plugin-invariants. This
module never contains the dispatch-reference form naming an agent that does
not exist (check-plugin-invariants scans tests/ for it).

Every new negative (absence) assertion has a non-vacuity proof: a forged
sample the matcher must flag, asserted next to the real-document check.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EM_WORKFLOW = os.path.join(REPO_ROOT, "em-workflow")
QUESTION_RESOLUTION_PATH = os.path.join(
    EM_WORKFLOW, "references", "question-resolution.md"
)

SECTION_HEADING = "### Opus escalation"

# Capture patterns applied to the section text. The agent name is the
# `em-workflow:` suffix of the Task(...) dispatch literal in FR2's exact
# form; the contract path is the one `references/<name>-contract.md`
# citation the section carries.
DISPATCH_RE = re.compile(r'Task\(subagent_type="em-workflow:([A-Za-z0-9_-]+)"\)')
CONTRACT_PATH_RE = re.compile(r"references/([A-Za-z0-9_-]+-contract\.md)")

# The per-question return-shape sentence the section carried before this
# task (lower-cased, whitespace-collapsed), now owned by the contract.
RETURN_SHAPE_SENTENCE = (
    "either a chosen `option_id` present in that question's own "
    "`options[].option_id` or an explicit no-decision, and in both cases "
    "its reasoning"
)

FORBIDDEN_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash"}
EXPECTED_TOOLS = {"Read", "Glob", "Grep"}

SOURCE_VALUES = (
    "batch-decision-table",
    "batch-codex-consultation",
    "batch-safe-default",
    "batch-classification-gate",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    """Read a file, or return "" when it does not exist yet.

    Returning "" lets every dependent assertion fail on content, with a
    message, instead of erroring out the whole class.
    """
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _norm_lower(text):
    return _norm(text).lower()


def _slice_section(text, heading):
    """The section from `heading` to the next heading of level <= 3."""
    if heading not in text:
        return ""
    rest = text.split(heading, 1)[1]
    following = re.search(r"(?m)^#{1,3} ", rest)
    body = rest[: following.start()] if following else rest
    return heading + body


def _contract_section(text, title):
    """The `## <title>` chunk of the contract, up to the next `## `."""
    for chunk in re.split(r"(?m)^## ", text)[1:]:
        if chunk.startswith(title):
            return chunk
    return ""


def _frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return match.group(1) if match else None


def _frontmatter_value(frontmatter, key):
    match = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
    return match.group(1).strip() if match else None


def _tools_of(frontmatter):
    value = _frontmatter_value(frontmatter, "tools")
    if value is None:
        return None
    return {tool.strip() for tool in value.split(",")}


def _has_task_assignment_heading(text):
    return re.search(r"(?m)^# Task assignment\s*$", text) is not None


def _restates_return_shape(text):
    """True when `text` carries the per-question return-shape sentence."""
    return RETURN_SHAPE_SENTENCE in _norm_lower(text)


def _names_return_field(text):
    """True when `text` names a return-shape token (agent-side matcher)."""
    low = _norm_lower(text)
    return any(token in low for token in ("option_id", "no-decision", "options[]"))


def _has_per_command_bound(section_text):
    return (
        "at most one dispatch per distinct literal command string within a run"
        in _norm_lower(section_text)
    )


def _names_source_literal(section_text):
    if any(value in section_text for value in SOURCE_VALUES):
        return True
    return re.search(r"source\s*[:=]", section_text) is not None


def _restates_presentation_rule(section_text):
    low = _norm_lower(section_text)
    return any(
        marker in low
        for marker in ("unique within that question", "exactly one question")
    )


class _EscalationDocs(unittest.TestCase):
    """Shared fixture: the section, the extracted name, and the derived
    agent / contract paths and texts."""

    @classmethod
    def setUpClass(cls):
        cls.qr_text = _read(QUESTION_RESOLUTION_PATH)
        cls.section = _slice_section(cls.qr_text, SECTION_HEADING)
        cls.section_norm = _norm(cls.section)

        dispatch = DISPATCH_RE.findall(cls.section)
        cls.agent_name = dispatch[0] if len(dispatch) == 1 else None

        contract_names = sorted(set(CONTRACT_PATH_RE.findall(cls.section)))
        cls.contract_name = contract_names[0] if len(contract_names) == 1 else None

        cls.agent_path = (
            os.path.join(EM_WORKFLOW, "agents", cls.agent_name + ".md")
            if cls.agent_name
            else None
        )
        cls.contract_path = (
            os.path.join(EM_WORKFLOW, "references", cls.contract_name)
            if cls.contract_name
            else None
        )
        cls.agent_text = _read(cls.agent_path) if cls.agent_path else ""
        cls.contract_text = _read(cls.contract_path) if cls.contract_path else ""
        cls.contract_norm = _norm(cls.contract_text)


# ---------------------------------------------------------------------------
# AC-1: the agent definition
# ---------------------------------------------------------------------------

FORGED_FRONTMATTER_WITH_WRITE = (
    "name: opus-escalation\nmodel: opus\neffort: xhigh\n"
    "tools: Read, Glob, Grep, Write"
)
FORGED_FRONTMATTER_WITH_BASH = (
    "name: opus-escalation\nmodel: opus\neffort: xhigh\n"
    "tools: Read, Glob, Grep, Bash"
)
FORGED_AGENT_WITH_TASK_ASSIGNMENT_HEADING = (
    "---\nname: x\n---\n\n# Task assignment\n\nbody\n"
)


class TestAgentDefinition(_EscalationDocs):
    """AC-1."""

    def _frontmatter(self):
        frontmatter = _frontmatter(self.agent_text)
        self.assertIsNotNone(
            frontmatter, "agent definition missing or has no frontmatter block"
        )
        return frontmatter

    def test_ac1_section_names_the_agent_and_the_file_exists(self):
        self.assertIsNotNone(
            self.agent_name,
            "the section must carry exactly one Task(...) dispatch literal",
        )
        self.assertTrue(
            os.path.isfile(self.agent_path),
            f"agent definition does not exist: {self.agent_path}",
        )

    def test_ac1_frontmatter_name_equals_file_stem(self):
        frontmatter = self._frontmatter()
        self.assertEqual(_frontmatter_value(frontmatter, "name"), self.agent_name)
        stem = os.path.splitext(os.path.basename(self.agent_path))[0]
        self.assertEqual(_frontmatter_value(frontmatter, "name"), stem)

    def test_ac1_model_is_opus_and_effort_is_xhigh(self):
        frontmatter = self._frontmatter()
        self.assertEqual(_frontmatter_value(frontmatter, "model"), "opus")
        self.assertEqual(_frontmatter_value(frontmatter, "effort"), "xhigh")

    def test_ac1_tools_are_read_glob_grep_only(self):
        tools = _tools_of(self._frontmatter())
        self.assertIsNotNone(tools, "no tools: line in frontmatter")
        self.assertEqual(tools, EXPECTED_TOOLS)
        self.assertEqual(tools & FORBIDDEN_TOOLS, set())

    def test_ac1_no_task_assignment_heading(self):
        self.assertNotEqual(self.agent_text, "", "agent definition not found")
        self.assertFalse(_has_task_assignment_heading(self.agent_text))

    # --- non-vacuity proofs -------------------------------------------------

    def test_ac1_tools_matcher_rejects_forged_write(self):
        forged = _tools_of(FORGED_FRONTMATTER_WITH_WRITE)
        self.assertNotEqual(forged, EXPECTED_TOOLS)
        self.assertEqual(forged & FORBIDDEN_TOOLS, {"Write"})

    def test_ac1_tools_matcher_rejects_forged_bash(self):
        forged = _tools_of(FORGED_FRONTMATTER_WITH_BASH)
        self.assertEqual(forged & FORBIDDEN_TOOLS, {"Bash"})

    def test_ac1_heading_matcher_flags_forged_heading(self):
        self.assertTrue(
            _has_task_assignment_heading(FORGED_AGENT_WITH_TASK_ASSIGNMENT_HEADING)
        )


# ---------------------------------------------------------------------------
# AC-2: the agent body
# ---------------------------------------------------------------------------

FORGED_AGENT_RESTATING_RETURN_SHAPE = (
    "For each question you return either a chosen `option_id` present in "
    "that question's own `options[].option_id` or an explicit no-decision, "
    "and in both cases its reasoning."
)
FORGED_AGENT_NAMING_ONLY_A_FIELD = "Return the `option_id` you picked."


class TestAgentBody(_EscalationDocs):
    """AC-2."""

    def test_ac2_contract_resolved_from_the_dispatcher_supplied_path(self):
        norm = _norm_lower(self.agent_text)
        self.assertIn("escalation_contract_path", norm)
        self.assertIn("supplies", norm)

    def test_ac2_stops_rather_than_guessing_when_unresolved(self):
        norm = _norm_lower(self.agent_text)
        self.assertIn("stop and report that the contract could not be resolved", norm)
        self.assertIn("never guess at the shape", norm)
        self.assertIn("never search for another copy", norm)

    def test_ac2_names_the_contract_as_the_single_source_of_truth(self):
        norm = _norm_lower(self.agent_text)
        self.assertIn("single source of truth", norm)
        self.assertIn("input and return shape", norm)

    def test_ac2_carries_no_return_shape_statement(self):
        self.assertNotEqual(self.agent_text, "", "agent definition not found")
        self.assertFalse(_restates_return_shape(self.agent_text))
        self.assertFalse(_names_return_field(self.agent_text))

    def test_ac2_return_shape_matchers_are_not_vacuous(self):
        self.assertTrue(_restates_return_shape(FORGED_AGENT_RESTATING_RETURN_SHAPE))
        self.assertTrue(_names_return_field(FORGED_AGENT_RESTATING_RETURN_SHAPE))
        self.assertTrue(_names_return_field(FORGED_AGENT_NAMING_ONLY_A_FIELD))

    def test_ac2_treats_the_whole_input_as_data(self):
        norm = _norm_lower(self.agent_text)
        self.assertIn("whole input", norm)
        self.assertIn("untrusted data", norm)
        self.assertIn("never followed", norm)

    def test_ac2_is_read_only(self):
        norm = _norm_lower(self.agent_text)
        self.assertIn("no writes, commits or branch operations", norm)


# ---------------------------------------------------------------------------
# AC-3: the contract's input block and untrusted-data boundary
# ---------------------------------------------------------------------------


class TestContractInput(_EscalationDocs):
    """AC-3."""

    def test_ac3_contract_exists_at_the_path_the_section_names(self):
        self.assertIsNotNone(
            self.contract_name,
            "the section must cite exactly one references/<name>-contract.md",
        )
        self.assertTrue(
            os.path.isfile(self.contract_path),
            f"contract document does not exist: {self.contract_path}",
        )

    def test_ac3_input_carries_every_item_field(self):
        input_block = _norm(_contract_section(self.contract_text, "Input Block"))
        self.assertNotEqual(input_block, "", "contract has no Input Block section")
        for field in (
            "`question_id`",
            "`prompt`",
            "`options`",
            "`option_id`",
            "`why_needed`",
            "`evidence`",
            "tentative position",
        ):
            with self.subTest(field=field):
                self.assertIn(field, input_block)

    def test_ac3_input_scope_packet_versus_non_packet(self):
        input_block = _norm_lower(_contract_section(self.contract_text, "Input Block"))
        self.assertIn("every still-unmapped question of that one packet", input_block)
        self.assertIn("exactly one item", input_block)
        self.assertIn("non-packet", input_block)

    def test_ac3_input_carries_the_contract_path(self):
        input_block = _norm(_contract_section(self.contract_text, "Input Block"))
        self.assertIn("`escalation_contract_path`", input_block)

    def test_ac3_boundary_names_both_delimiters(self):
        boundary = _contract_section(self.contract_text, "Untrusted-Data Boundary")
        self.assertNotEqual(boundary, "", "contract has no Untrusted-Data Boundary")
        self.assertIn("`<untrusted-data>`", boundary)
        self.assertIn("`</untrusted-data>`", boundary)

    def test_ac3_boundary_states_everything_between_is_data(self):
        boundary = _norm_lower(
            _contract_section(self.contract_text, "Untrusted-Data Boundary")
        )
        self.assertIn("everything between", boundary)
        self.assertIn("is data", boundary)
        self.assertIn("never followed", boundary)

    def test_ac3_boundary_requires_closing_delimiter_neutralisation(self):
        boundary = _norm_lower(
            _contract_section(self.contract_text, "Untrusted-Data Boundary")
        )
        self.assertIn("dispatcher", boundary)
        self.assertIn("neutralise", boundary)
        self.assertIn("closing delimiter", boundary)
        self.assertIn("before wrapping", boundary)
        self.assertIn("cannot end the block early", boundary)


# ---------------------------------------------------------------------------
# AC-4: the contract's return object and degradation
# ---------------------------------------------------------------------------


class TestContractReturn(_EscalationDocs):
    """AC-4."""

    def test_ac4_return_shape_sentence_lives_in_the_contract(self):
        self.assertTrue(
            _restates_return_shape(self.contract_text),
            "the contract must carry the return-shape sentence intact",
        )

    def test_ac4_return_object_section_states_the_return(self):
        section = _contract_section(self.contract_text, "Return Object")
        self.assertNotEqual(section, "", "contract has no Return Object section")
        self.assertTrue(_restates_return_shape(section))
        norm = _norm_lower(section)
        self.assertIn("`question_id`", norm)
        self.assertIn("the output is that return object only", norm)

    def test_ac4_degradation_counts_unusable_returns_as_no_decision(self):
        section = _norm_lower(
            _contract_section(self.contract_text, "Validity and Degradation")
        )
        self.assertNotEqual(section, "", "contract has no Validity and Degradation")
        for phrase in (
            "was not carried",
            "outside that question's own",
            "missing entry",
            "counts as a no-decision for that question",
            "missing or unusable",
            "counts as a no-decision for every carried question",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_ac4_degradation_defers_the_consequence_to_the_resolution_document(
        self,
    ):
        section = _norm(
            _contract_section(self.contract_text, "Validity and Degradation")
        )
        self.assertIn("`references/question-resolution.md`", section)


# ---------------------------------------------------------------------------
# AC-5: the read constraint
# ---------------------------------------------------------------------------


class TestContractReadConstraint(_EscalationDocs):
    """AC-5."""

    def test_ac5_writes_are_forbidden(self):
        section = _norm_lower(_contract_section(self.contract_text, "Read Constraint"))
        self.assertNotEqual(section, "", "contract has no Read Constraint section")
        self.assertIn("no writes of any kind", section)

    def test_ac5_reads_are_bounded_to_the_contract_and_named_evidence(self):
        section = _norm_lower(_contract_section(self.contract_text, "Read Constraint"))
        self.assertIn("this document", section)
        self.assertIn(
            "files under the project root that a carried question's `evidence` names",
            section,
        )
        self.assertIn("nothing outside the project root is read", section)


# ---------------------------------------------------------------------------
# AC-6: the section's dispatch, contract path and binding
# ---------------------------------------------------------------------------

FORGED_SECTION_WITH_RETURN_SHAPE = (
    "### Opus escalation\n\n"
    "2. **Return shape.** Per question, the escalation returns either a "
    "chosen `option_id` present in that question's own `options[].option_id` "
    "or an explicit no-decision, and in both cases its reasoning.\n"
)


class TestSectionWiring(_EscalationDocs):
    """AC-6."""

    def test_ac6_dispatch_literal_is_in_fr2_form_and_names_the_agent(self):
        self.assertIsNotNone(
            self.agent_name,
            "the section must carry exactly one Task(subagent_type=...) literal",
        )
        self.assertEqual(self.agent_name, "opus-escalation")
        self.assertIn(
            f'Task(subagent_type="em-workflow:{self.agent_name}")', self.section
        )

    def test_ac6_section_cites_the_contract_path(self):
        self.assertIsNotNone(self.contract_name)
        self.assertEqual(self.contract_name, "opus-escalation-contract.md")
        self.assertIn(f"references/{self.contract_name}", self.section)

    def test_ac6_dispatch_carries_the_contract_path(self):
        norm = _norm_lower(self.section)
        self.assertIn("carries the path of", norm)

    def test_ac6_section_cites_the_contract_for_input_and_return_shape(self):
        self.assertIn("Input and return shape", self.section_norm)
        self.assertIn("cited, not restated", self.section_norm)

    def test_ac6_binding_token_and_its_location(self):
        self.assertIn("Opus/xhigh", self.section_norm)
        self.assertIn("frontmatter `model` / `effort`", self.section_norm)

    def test_ac6_binding_origin_is_named(self):
        self.assertIn("batch-codex-autonomous-decisions", self.section_norm)
        self.assertIn("FR8 / FR9 / A4", self.section_norm)

    def test_ac6_section_no_longer_carries_the_return_shape_sentence(self):
        self.assertNotEqual(self.section, "", "section not found")
        self.assertFalse(_restates_return_shape(self.section))

    def test_ac6_return_shape_matcher_is_not_vacuous(self):
        self.assertTrue(_restates_return_shape(FORGED_SECTION_WITH_RETURN_SHAPE))

    def test_ac6_section_is_last_in_the_document(self):
        # tests/test_question_resolution_doc.py slices the section from its
        # heading to the end of the file; that stays correct only while no
        # heading of level <= 3 follows it.
        after = self.qr_text.split(SECTION_HEADING, 1)[1]
        self.assertIsNone(re.search(r"(?m)^#{1,3} ", after))


# ---------------------------------------------------------------------------
# AC-7: non-packet presentation (contract) and scope (section)
# ---------------------------------------------------------------------------

FORGED_SECTION_MISSING_PER_COMMAND_BOUND = (
    "### Opus escalation\n\n"
    "5. **Non-packet gates.** Each non-packet gate resolution gets exactly "
    "one dispatch.\n"
)
FORGED_SECTION_WITH_BOUND = (
    "5. **Non-packet gates.** For the per-command approval fallback, at "
    "most one dispatch per distinct literal command string within a run."
)
FORGED_SECTION_NAMING_A_SOURCE = (
    "6. Record the answer with `source: batch-codex-consultation`."
)
FORGED_SECTION_NAMING_A_SOURCE_VALUE_ONLY = (
    "6. The audit record carries batch-safe-default."
)
FORGED_SECTION_RESTATING_THE_RULE = (
    "5. Present the gate as exactly one question whose `options[]` each "
    "carry an `option_id` unique within that question."
)


class TestNonPacketPresentationInContract(_EscalationDocs):
    """AC-7, contract half."""

    def _rule(self):
        rule = _norm(_contract_section(self.contract_text, "Non-packet Presentation"))
        self.assertNotEqual(rule, "", "contract has no Non-packet Presentation")
        return rule

    def test_ac7_gate_decision_is_one_question(self):
        self.assertIn("exactly one question", self._rule())

    def test_ac7_question_id_is_the_gate_identifying_name_cited_from_phase_state(
        self,
    ):
        rule = self._rule()
        self.assertIn("`question_id`", rule)
        self.assertIn("`references/phase-state.md`", rule)
        self.assertIn("Batch audit record file", rule)
        self.assertIn("cited, not restated", rule)

    def test_ac7_options_carry_option_ids_including_the_minimum_side_effect_option(
        self,
    ):
        rule = _norm_lower(self._rule())
        self.assertIn("`options[]`", rule)
        self.assertIn("unique within that question", rule)
        self.assertIn("minimum-side-effect option", rule)
        self.assertIn("`references/batch-mode.md`", rule)
        self.assertIn("non-packet gates table", rule)

    def test_ac7_orchestrator_composes_the_rest_inside_the_untrusted_block(self):
        rule = _norm_lower(self._rule())
        self.assertIn("composed by the orchestrator", rule)
        self.assertIn("untrusted-data block", rule)

    def test_ac7_per_command_fallback_carries_the_literal_command_string(self):
        rule = _norm_lower(self._rule())
        self.assertIn("per-command approval fallback", rule)
        self.assertIn("literal command string", rule)

    def test_ac7_rule_makes_the_return_condition_satisfiable(self):
        rule = _norm_lower(self._rule())
        self.assertIn("satisfiable", rule)


class TestNonPacketScopeInSection(_EscalationDocs):
    """AC-7, section half."""

    def test_ac7_scope_names_the_non_packet_gates_of_batch_mode(self):
        norm = self.section_norm
        self.assertIn("`references/batch-mode.md`'s Non-packet gates", norm)
        self.assertIn("review diff-size gate", norm)
        self.assertIn("per-command approval fallback", norm)
        self.assertIn("Codex consultation procedure", norm)

    def test_ac7_one_dispatch_per_non_packet_gate_resolution(self):
        norm = _norm_lower(self.section)
        self.assertIn(
            "each non-packet gate resolution gets exactly one dispatch", norm
        )
        self.assertIn("that gate's single decision", norm)

    def test_ac7_per_command_fallback_is_bounded_per_literal_string(self):
        self.assertTrue(_has_per_command_bound(self.section))
        norm = _norm_lower(self.section)
        self.assertIn("per-string cache", norm)
        self.assertIn("causes no second dispatch", norm)

    def test_ac7_per_command_bound_matcher_is_not_vacuous(self):
        self.assertFalse(_has_per_command_bound(FORGED_SECTION_MISSING_PER_COMMAND_BOUND))
        self.assertTrue(_has_per_command_bound(FORGED_SECTION_WITH_BOUND))

    def test_ac7_no_decision_falls_to_the_minimum_side_effect_option(self):
        norm = _norm_lower(self.section)
        self.assertIn("a no-decision makes the gate take the minimum-side-effect", norm)
        self.assertIn("non-packet gates table already prescribes", norm)

    def test_ac7_escalation_still_runs_when_no_harness_is_available(self):
        norm = _norm_lower(self.section)
        self.assertIn(
            "no harness entry available, the escalation still runs for the "
            "non-packet gate",
            norm,
        )

    def test_ac7_audit_record_cites_phase_state(self):
        norm = self.section_norm
        self.assertIn("`references/phase-state.md`'s batch audit record file", norm)

    def test_ac7_section_cites_the_contract_presentation_rule(self):
        norm = _norm_lower(self.section)
        self.assertIn("non-packet presentation rule", norm)
        self.assertIn(f"references/{self.contract_name}", self.section)

    def test_ac7_section_does_not_restate_the_presentation_rule(self):
        self.assertNotEqual(self.section, "", "section not found")
        self.assertFalse(_restates_presentation_rule(self.section))

    def test_ac7_restatement_matcher_is_not_vacuous(self):
        self.assertTrue(_restates_presentation_rule(FORGED_SECTION_RESTATING_THE_RULE))

    def test_ac7_section_names_no_source_literal(self):
        self.assertNotEqual(self.section, "", "section not found")
        self.assertFalse(_names_source_literal(self.section))

    def test_ac7_source_literal_matcher_is_not_vacuous(self):
        self.assertTrue(_names_source_literal(FORGED_SECTION_NAMING_A_SOURCE))
        self.assertTrue(_names_source_literal(FORGED_SECTION_NAMING_A_SOURCE_VALUE_ONLY))


if __name__ == "__main__":
    unittest.main()
