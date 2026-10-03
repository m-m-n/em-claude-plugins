"""Tests for task0003 (plan-version-bump-per-commit): the dispatch-resolved
`plugin_versioning` value as seen by implementation-planner, its create-plan
dispatch procedure and its agent prompt (planner half of TS-5).

Covers task0003 Acceptance Criteria
(feature-docs/plan-version-bump-per-commit/tasks/task0003.md):

- AC-1: planner-contract.md lists `plugin_versioning` among `planning_inputs`
  as a value, and owns a subsection headed exactly
  `### plugin_versioning (dispatch-resolved value)` that defines `exempt`,
  `plugins`, `plugins[].dir`, `plugins[].name` and
  `plugins[].marketplace_versioned` with the resolution rules.
- AC-2: planner-contract.md's digest_inputs section declares
  `plugin_versioning` as a `value_inputs` member and no longer states that
  the planner has no `value_inputs`.
- AC-3: planner-contract.md states the value is mandatory on every
  create-plan dispatch and that a dispatch without it is answered with
  `invalid_input`.
- AC-4: planner-contract.md classifies the value as untrusted input by
  citing worker-envelope.md's Untrusted-Input Handling (TM-1) and states
  what the value carries.
- AC-5: create-plan-phase.md's Planner dispatch resolves, passes and
  digests the value, including re-dispatches and the return-time
  recomputation.
- AC-6: implementation-planner.md names the value among its
  `planning_inputs` and points at plan-writing SKILL.md's "Plugin Version
  Handling" section without restating any version rule.
- AC-7: this module uses only the standard library and repository files,
  and every matcher below is exercised against in-test samples in both
  directions (a negative proof per matcher, FR7).

These deliverables are Markdown documents, so verification is textual and
anchored on pinned headings, field names and key literals -- not on whole
sentences.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PLANNER_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
PLANNER_AGENT_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"

SUBSECTION_HEADING = "### plugin_versioning (dispatch-resolved value)"
PLANNING_INPUTS_HEADING = "## Additional input: `planning_inputs`"
DIGEST_INPUTS_HEADING = "## digest_inputs"
PLANNER_DISPATCH_HEADING = "## 4. Planner dispatch"
AGENT_INPUTS_HEADING = "## Inputs"
PLAN_WRITING_SECTION_NAME = "Plugin Version Handling"

FIELD_NAMES = (
    "exempt",
    "plugins",
    "plugins[].dir",
    "plugins[].name",
    "plugins[].marketplace_versioned",
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space, so an anchor survives the
    documents' hard line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


_HEADING_RE = re.compile(r"^(#{1,6}) \S")


def _heading_level(line):
    match = _HEADING_RE.match(line)
    return len(match.group(1)) if match else None


def _headings(text):
    """Yield (line_index, level, line) for every Markdown heading outside a
    fenced code block."""
    in_fence = False
    for index, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        level = _heading_level(line)
        if level is not None:
            yield index, level, line


def find_heading_lines(text, heading):
    """Line indexes where `heading` appears verbatim as a heading line."""
    return [index for index, _level, line in _headings(text) if line == heading]


def section(text, heading):
    """Body of the section opened by `heading` (heading line excluded), up to
    the next heading of the same or a higher level. Raises when the heading
    is absent or ambiguous."""
    lines = text.split("\n")
    starts = find_heading_lines(text, heading)
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one heading line {heading!r}, found {len(starts)}"
        )
    start = starts[0]
    level = _heading_level(lines[start])
    end = len(lines)
    for index, other_level, _line in _headings(text):
        if index > start and other_level <= level:
            end = index
            break
    return "\n".join(lines[start + 1 : end])


# --- FR7 negative check: permissive statement matcher -----------------------

_PERMISSIVE_RE = re.compile(
    r"(?:\b(?:may|can|could|might|allowed to|permitted to|free to|"
    r"need not|does not need to|do not need to)\b"
    r"[^.\n]{0,80}?\b(?:keep|leave|retain|preserve|skip|omit|defer|postpone)\b"
    r"[^.\n]{0,60}?\bversion\b)"
    r"|(?:\bversion\b[^.\n]{0,60}?\b(?:may|can)\b[^.\n]{0,30}?"
    r"\b(?:stay|remain|be left|be kept|be unchanged)\b)"
    r"|(?:\b(?:later|subsequent|following|another|other)\s+tasks?\b"
    r"[^.\n]{0,80}?\b(?:keep|leave|retain)\b[^.\n]{0,40}?\bversion\b)",
    re.IGNORECASE,
)

_PROHIBITION_RE = re.compile(
    r"\b(?:must not|never|do not|does not|not allowed|prohibit\w*|forbid\w*|"
    r"forbidden|cannot|may not|no task)\b",
    re.IGNORECASE,
)

_EXEMPT_ONLY_RE = re.compile(r"(?<!non-)\bexempt (?:repository|repositories)\b", re.IGNORECASE)
_NON_EXEMPT_RE = re.compile(r"\bnon-exempt\b", re.IGNORECASE)


def _sentences(text):
    sentences = []
    for paragraph in re.split(r"\n\s*\n", text):
        sentences.extend(
            s for s in re.split(r"(?<=[.!?])\s+", _flat(paragraph)) if s.strip()
        )
    return sentences


def permissive_statements(text):
    """Sentences that permit an unchanged version on a plugin-changing commit
    in a non-exempt repository.

    A sentence is excused when it is itself a prohibition (it carries a
    prohibition marker, so a quoted prohibited example does not count) or
    when it speaks only of an exempt repository (where leaving the version
    alone is the rule, not a violation)."""
    found = []
    for sentence in _sentences(text):
        if not _PERMISSIVE_RE.search(sentence):
            continue
        if _PROHIBITION_RE.search(sentence):
            continue
        if _EXEMPT_ONLY_RE.search(sentence) and not _NON_EXEMPT_RE.search(sentence):
            continue
        found.append(sentence)
    return found


class TestPermissiveMatcherProof(unittest.TestCase):
    """Negative proof for the FR7 matcher: it must reject permissive samples
    and accept the prohibition wording the documents actually use."""

    PERMISSIVE_SAMPLES = (
        "Later tasks may keep the version unchanged.",
        "In a non-exempt repository the plan may leave the version as is for follow-up work.",
        "The plugin version can stay unchanged until the last task.",
        "Subsequent tasks are free to skip the version change.",
        "Later tasks\nmay keep the\nversion unchanged, wrapped over several lines.",
    )
    ACCEPTED_SAMPLES = (
        'A task must never leave the version unchanged (for example, "later tasks may keep the version" is prohibited).',
        "In an exempt repository the plan may keep the version unchanged.",
        "Never write that later tasks may keep the version.",
        "The planner does not decide whether a repository is exempt.",
    )

    def test_permissive_samples_are_rejected(self):
        for sample in self.PERMISSIVE_SAMPLES:
            with self.subTest(sample=sample):
                self.assertTrue(
                    permissive_statements(sample),
                    "matcher failed to flag a permissive sample",
                )

    def test_prohibition_and_exempt_wording_is_accepted(self):
        for sample in self.ACCEPTED_SAMPLES:
            with self.subTest(sample=sample):
                self.assertEqual(permissive_statements(sample), [])


class TestSectionHelperProof(unittest.TestCase):
    SAMPLE = (
        "# Title\n"
        "\n"
        "## A\n"
        "intro\n"
        "```yaml\n"
        "# not a heading\n"
        "key: value\n"
        "```\n"
        "### A1\n"
        "nested\n"
        "## B\n"
        "other\n"
    )

    def test_section_includes_nested_subsection_and_stops_at_sibling(self):
        body = section(self.SAMPLE, "## A")
        self.assertIn("nested", body)
        self.assertIn("key: value", body)
        self.assertNotIn("other", body)

    def test_section_stops_at_next_same_level_heading(self):
        body = section(self.SAMPLE, "### A1")
        self.assertEqual(body.strip(), "nested")

    def test_fenced_comment_line_is_not_a_heading(self):
        self.assertEqual(find_heading_lines(self.SAMPLE, "# not a heading"), [])

    def test_missing_heading_raises(self):
        with self.assertRaises(AssertionError):
            section(self.SAMPLE, "## Missing")


# --- planner-contract.md ---------------------------------------------------


class TestPlannerContractPlanningInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.planning_inputs = section(cls.text, PLANNING_INPUTS_HEADING)

    def test_ac1_planning_inputs_lists_plugin_versioning_as_a_value(self):
        # AC-1: the entry sits in the planning_inputs yaml block and is
        # marked as a value rather than a path.
        entries = [
            line
            for line in self.planning_inputs.split("\n")
            if re.match(r"\s*plugin_versioning:", line)
        ]
        self.assertEqual(len(entries), 1, "planning_inputs must list plugin_versioning once")
        self.assertRegex(entries[0], r"(?i)\bvalue\b")
        self.assertRegex(entries[0], r"(?i)not a path")

    def test_ac1_pinned_subsection_heading_exists_exactly_once(self):
        self.assertEqual(len(find_heading_lines(self.text, SUBSECTION_HEADING)), 1)

    def test_ac1_subsection_is_inside_planning_inputs_section(self):
        self.assertIn(SUBSECTION_HEADING, self.planning_inputs)


class TestPlannerContractSubsection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.body = _flat(section(cls.text, SUBSECTION_HEADING))

    def test_ac1_defines_every_field(self):
        for field in FIELD_NAMES:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.body)

    def test_ac1_resolution_rule_workflow_file_presence_at_worktree_root(self):
        self.assertIn(".github/workflows/plugin-version-bump.yml", self.body)
        self.assertRegex(self.body, r"(?i)worktree root")

    def test_ac1_resolution_rule_git_tracked_plugin_directories(self):
        self.assertRegex(self.body, r"(?i)git-tracked")
        self.assertIn(".claude-plugin/plugin.json", self.body)

    def test_ac1_resolution_rule_marketplace_entry_carrying_a_version(self):
        self.assertIn(".claude-plugin/marketplace.json", self.body)
        self.assertRegex(self.body, r"(?i)same name")
        self.assertRegex(self.body, r"(?i)carr(?:y|ies) a version")

    def test_ac1_resolution_rule_ordering_by_dir_ascending(self):
        self.assertRegex(self.body, r"(?is)sorted by\s+`dir`\s+ascending")

    def test_ac1_re_resolution_per_dispatch_and_on_return(self):
        self.assertRegex(self.body, r"(?i)every\s+(?:implementation-planner|create-plan)\s+dispatch")
        self.assertRegex(self.body, r"(?i)re-dispatch")
        self.assertRegex(self.body, r"(?i)re-resolv")
        self.assertRegex(self.body, r"(?i)\breturn\b")

    def test_ac1_workers_do_not_discover_the_state_themselves(self):
        self.assertRegex(self.body, r"(?i)never discover")

    def test_ac3_value_is_mandatory_and_absence_is_invalid_input(self):
        self.assertRegex(self.body, r"(?i)\bmandatory\b")
        self.assertRegex(self.body, r"(?i)create-plan dispatch")
        self.assertIn("`invalid_input`", self.body)

    def test_ac4_untrusted_classification_cites_envelope_section(self):
        self.assertRegex(self.body, r"(?i)\buntrusted\b")
        self.assertIn("worker-envelope.md", self.body)
        self.assertIn("Untrusted-Input Handling", self.body)
        self.assertIn("TM-1", self.body)

    def test_ac4_untrusted_handling_is_cited_not_restated(self):
        # Phrases that belong to the cited section's own body.
        for restated in (
            "ignore previous instructions",
            "attacker-influenceable",
            "role overrides",
        ):
            with self.subTest(restated=restated):
                self.assertNotIn(restated, self.body.lower())

    def test_ac4_states_what_the_value_carries(self):
        self.assertRegex(self.body, r"(?i)exemption boolean")
        self.assertRegex(self.body, r"(?i)project-relative plugin directory paths")
        self.assertRegex(self.body, r"(?i)plugin names")
        self.assertRegex(self.body, r"(?i)per-plugin marketplace flag")
        self.assertRegex(self.body, r"(?i)no other text")
        self.assertRegex(self.body, r"(?i)repository files")

    def test_fr7_subsection_contains_no_permissive_statement(self):
        self.assertEqual(permissive_statements(self.body), [])


class TestPlannerContractDigestInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.digest = _flat(section(cls.text, DIGEST_INPUTS_HEADING))

    def test_ac2_declares_plugin_versioning_as_a_value_inputs_member(self):
        self.assertIn("`value_inputs`", self.digest)
        self.assertIn("`plugin_versioning`", self.digest)
        self.assertRegex(self.digest, r"(?is)`value_inputs`[^.]*`plugin_versioning`|`plugin_versioning`[^.]*`value_inputs`")

    def test_ac2_old_no_value_inputs_statement_is_gone(self):
        self.assertNotRegex(self.digest, r"(?i)no\s+`value_inputs`")
        self.assertNotRegex(self.digest, r"(?i)there are no\s+`?value_inputs")

    def test_ac2_digest_follows_rule_r1_normalization(self):
        self.assertRegex(self.digest, r"(?i)\bR1\b")
        self.assertIn("worker-envelope.md", self.digest)
        self.assertRegex(self.digest, r"(?i)normaliz")

    def test_ac2_existing_file_inputs_remain_listed(self):
        for kept in ("REQUIREMENTS.md", "skills/plan-writing/SKILL.md", "this contract document itself"):
            with self.subTest(kept=kept):
                self.assertIn(kept, self.digest)


class TestPlannerContractNegativeProof(unittest.TestCase):
    def test_no_value_inputs_matcher_flags_the_old_statement(self):
        old = "There are no `value_inputs` for the planner (`task_description` is not part of its input)."
        self.assertRegex(old, r"(?i)no\s+`value_inputs`")

    def test_no_value_inputs_matcher_accepts_the_new_declaration(self):
        new = "The planner's `value_inputs` has one member, `plugin_versioning`."
        self.assertNotRegex(new, r"(?i)no\s+`value_inputs`")
        self.assertNotRegex(new, r"(?i)there are no\s+`?value_inputs")

    def test_whole_contract_contains_no_permissive_statement(self):
        self.assertEqual(permissive_statements(_read(PLANNER_CONTRACT_PATH)), [])


# --- create-plan-phase.md --------------------------------------------------


class TestCreatePlanPlannerDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)
        cls.dispatch = _flat(section(cls.text, PLANNER_DISPATCH_HEADING))

    def test_ac5_orchestrator_resolves_value_per_planner_contract(self):
        self.assertIn("`plugin_versioning`", self.dispatch)
        self.assertIn("references/contracts/planner-contract.md", self.dispatch)
        self.assertRegex(self.dispatch, r"(?i)resolv")

    def test_ac5_resolution_covers_every_dispatch_including_answer_redispatches(self):
        self.assertRegex(self.dispatch, r"(?i)every\s+(?:`?implementation-planner`?\s+)?dispatch")
        self.assertRegex(self.dispatch, r"(?i)re-dispatch")
        self.assertRegex(self.dispatch, r"(?i)answers")

    def test_ac5_value_is_passed_in_planning_inputs(self):
        self.assertIn("`planning_inputs`", self.dispatch)
        self.assertRegex(
            self.dispatch,
            r"(?is)`planning_inputs(?:\.plugin_versioning)?`.{0,400}?`plugin_versioning`"
            r"|`plugin_versioning`.{0,400}?`planning_inputs`",
        )

    def test_ac5_value_is_part_of_the_digest_value_inputs(self):
        self.assertIn("`value_inputs`", self.dispatch)
        self.assertRegex(
            self.dispatch,
            r"(?is)`value_inputs`.{0,400}?`plugin_versioning`|`plugin_versioning`.{0,400}?`value_inputs`",
        )

    def test_ac5_value_is_re_resolved_for_the_return_time_digest(self):
        self.assertRegex(self.dispatch, r"(?i)re-resolv")
        self.assertRegex(self.dispatch, r"(?i)\breturn\b")
        self.assertRegex(self.dispatch, r"(?i)recomput")

    def test_ac5_field_table_is_cited_not_restated(self):
        for field in ("plugins[].dir", "plugins[].name", "plugins[].marketplace_versioned"):
            with self.subTest(field=field):
                self.assertNotIn(field, self.dispatch)

    def test_ac5_existing_dispatch_items_are_preserved(self):
        for kept in (
            "`input_digest`",
            "`write_policy`",
            "`planning_inputs.threat_model_template`",
        ):
            with self.subTest(kept=kept):
                self.assertIn(kept, self.dispatch)

    def test_fr7_phase_document_contains_no_permissive_statement(self):
        self.assertEqual(permissive_statements(self.text), [])


# --- implementation-planner.md ---------------------------------------------


class TestPlannerAgentPrompt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_AGENT_PATH)
        cls.inputs = _flat(section(cls.text, AGENT_INPUTS_HEADING))

    def test_ac6_inputs_enumeration_names_plugin_versioning(self):
        self.assertIn("`plugin_versioning`", self.inputs)
        self.assertIn("`threat_model_template`", self.inputs)
        # Named in the same enumeration as the other planning_inputs.
        self.assertRegex(
            self.inputs,
            r"(?s)`planning_inputs`[^)]*`threat_model_template`[^)]*`plugin_versioning`"
            r"|`planning_inputs`[^)]*`plugin_versioning`",
        )

    def test_ac6_points_to_plan_writing_section_by_name(self):
        self.assertIn(PLAN_WRITING_SECTION_NAME, self.inputs)
        self.assertRegex(self.inputs, r"plan-writing")
        self.assertIn("SKILL.md", self.inputs)

    def test_ac6_pointer_covers_the_files_rule(self):
        self.assertRegex(self.inputs, r"`files`")

    def test_ac6_cites_the_contract_for_the_value_shape(self):
        self.assertIn("plugin_versioning (dispatch-resolved value)", _flat(self.text))

    def test_ac6_no_version_rule_statements(self):
        lowered = self.text.lower()
        for banned in (
            "per-commit",
            "per commit",
            "bump",
            "strictly greater",
            "per-component",
            "numeric comparison",
            "numerically",
        ):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, lowered)

    def test_fr7_agent_prompt_contains_no_permissive_statement(self):
        self.assertEqual(permissive_statements(self.text), [])


class TestPlannerAgentNegativeProof(unittest.TestCase):
    """AC-6's negative half and the FR7 check, exercised against in-test
    samples in both directions."""

    BANNED = ("per-commit", "per commit", "bump", "strictly greater", "per-component")

    def _violations(self, text):
        lowered = text.lower()
        return [word for word in self.BANNED if word in lowered]

    def test_rule_restating_sample_is_flagged(self):
        sample = "Every commit that changes a plugin must bump the version, strictly greater than before."
        self.assertTrue(self._violations(sample))

    def test_pointer_only_sample_is_accepted(self):
        sample = (
            "How the value is applied, including the `files` rule, is governed by "
            "plan-writing SKILL.md's \"Plugin Version Handling\" section."
        )
        self.assertEqual(self._violations(sample), [])

    def test_permissive_sentence_appended_to_the_agent_prompt_is_flagged(self):
        sample = "Later tasks may keep the version unchanged."
        self.assertEqual(permissive_statements(_read(PLANNER_AGENT_PATH)), [])
        self.assertTrue(
            permissive_statements(_read(PLANNER_AGENT_PATH) + "\n\n" + sample)
        )


# --- AC-7: module discipline -----------------------------------------------


class TestModuleDiscipline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _imported_top_level_modules(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        return names

    def test_ac7_imports_are_standard_library_only(self):
        stdlib = set(sys.stdlib_module_names)
        non_stdlib = self._imported_top_level_modules() - stdlib
        self.assertEqual(non_stdlib, set())

    def test_ac7_reads_no_path_outside_the_repository(self):
        attribute_names = {
            node.attr for node in ast.walk(self.tree) if isinstance(node, ast.Attribute)
        }
        self.assertNotIn("home", attribute_names)
        self.assertNotIn("expanduser", attribute_names)

    def test_ac7_documents_under_test_are_repository_files(self):
        for path in (PLANNER_CONTRACT_PATH, CREATE_PLAN_PATH, PLANNER_AGENT_PATH):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())
                path.relative_to(REPO_ROOT)

    def test_ac7_import_matcher_flags_a_third_party_module(self):
        tree = ast.parse("import requests\nfrom yaml import safe_load\n")
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertEqual(names - set(sys.stdlib_module_names), {"requests", "yaml"})


if __name__ == "__main__":
    unittest.main()
