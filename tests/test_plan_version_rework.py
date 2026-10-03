"""Tests for task0004: the rework half of the plugin-version handling
(feature plan-version-bump-per-commit, TS-4 and the rework half of TS-5).

Covers task0004 Acceptance Criteria
(feature-docs/plan-version-bump-per-commit/tasks/task0004.md):

- AC-1 (FR4): rework-planner.md, rework-planner-contract.md and
  rework-task-synthesis.md each cite plan-writing SKILL.md's "Plugin Version
  Handling" section (repository-relative path and heading text) as applying
  to every task rework-planner synthesizes, including its `files` rule.
- AC-2 (FR4, FR7, NFR1): none of the three documents restates the version
  rule text or lets rework tasks keep the version unchanged in a non-exempt
  repository. The permissive-statement check is exercised in both
  directions against in-test samples.
- AC-3 (FR5): rework-planner-contract.md defines rework-planner's
  `plugin_versioning` input by citing planner-contract.md's subsection,
  states it is mandatory (`invalid_input` on absence) and declares it a
  `value_inputs` member of rework-planner's `input_digest`.
- AC-4 (TM-1): rework-planner-contract.md classifies `plugin_versioning` as
  untrusted input under worker-envelope.md's Untrusted-Input Handling,
  limited to the fields of the cited definition.
- AC-5 (FR5): the rework-planner dispatch procedure states that the
  orchestrator resolves `plugin_versioning` at every dispatch, passes it,
  includes it in `value_inputs` and re-resolves it on return.
- AC-6 (FR5): rework-planner.md names `plugin_versioning` among its inputs.
- AC-7 (FR7, NFR3): this module asserts AC-1 to AC-6 using only the
  standard library and repository files.

Which document holds the rework-planner dispatch procedure (AC-5): the
document that instructs the orchestrator to build rework-planner's input is
`em-workflow/references/rework-task-synthesis.md`, Section 10 (Workflow state
transition) -- every one of the four rework routes points there for the
fixed dispatch ordering (`references/review-phase.md` for the review routes,
`skills/develop/SKILL.md` for the verify routes), so one statement there
covers all four routes. AC-5 therefore asserts against
rework-task-synthesis.md (DISPATCH_DOC below) and `skills/develop/SKILL.md`
is neither read nor changed by this task.

Scope (IMPLEMENTATION.md "Test scope"): this module asserts only on the
three documents this task modifies. It never opens planner-contract.md or
plan-writing SKILL.md -- the cited headings are pinned strings here, and
their existence is those documents' owner tasks' concern.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "rework-planner.md"
CONTRACT_PATH = (
    REPO_ROOT
    / "em-workflow"
    / "references"
    / "contracts"
    / "rework-planner-contract.md"
)
SYNTHESIS_PATH = REPO_ROOT / "em-workflow" / "references" / "rework-task-synthesis.md"

# AC-5: the document that holds the rework-planner dispatch procedure.
DISPATCH_DOC_PATH = SYNTHESIS_PATH

THIS_FILE = Path(__file__).resolve()

# Pinned citation targets (IMPLEMENTATION.md Shared Components).
PLAN_WRITING_PATH = "em-workflow/skills/plan-writing/SKILL.md"
PLAN_WRITING_HEADING = "Plugin Version Handling"
PLANNER_CONTRACT_PATH = "em-workflow/references/contracts/planner-contract.md"
PLUGIN_VERSIONING_HEADING = "### plugin_versioning (dispatch-resolved value)"
FIELD = "plugin_versioning"

# The contract's own section defining the input (heading chosen by this
# task; anchored here as a cited string).
CONTRACT_INPUT_HEADING = "## Additional input: `plugin_versioning`"

DOCS = {
    "rework-planner.md": AGENT_PATH,
    "rework-planner-contract.md": CONTRACT_PATH,
    "rework-task-synthesis.md": SYNTHESIS_PATH,
}


def read(path):
    return Path(path).read_text(encoding="utf-8")


def paragraphs(text):
    """Blank-line separated blocks with wrapped lines joined by one space."""
    blocks = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", block).strip() for block in blocks if block.strip()]


def section(text, heading):
    """The text from `heading` (a line) to the next heading of the same or a
    shallower level; fails the test if the heading is absent."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    if start is None:
        raise AssertionError(f"heading not found: {heading!r}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#+)\s", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def paragraphs_with(text, *needles):
    return [p for p in paragraphs(text) if all(n in p for n in needles)]


# ---------------------------------------------------------------------------
# AC-2 helper: the permissive-statement check (FR7 negative check).
#
# A sentence is permissive when it lets a plugin-changing commit keep the
# version unchanged, unless it is the document's own prohibition wording
# (a prohibition lead-in earlier in the sentence, or a quoted prohibited
# example introduced by "such as" / "for example") or an exempt-repository
# statement.
# ---------------------------------------------------------------------------

PERMISSIVE_PATTERNS = [
    re.compile(
        r"\b(?:keep|keeps|keeping|leave|leaves|leaving|left)\b[^.]{0,50}"
        r"\bversion\b[^.]{0,40}\b(?:unchanged|as is|the same)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bversion\b[^.]{0,50}\b(?:stays|stay|remains|remain|is left|are left"
        r"|is kept|are kept)\b[^.]{0,30}\b(?:unchanged|as is|the same)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:do|does|need|needs)\s+not\s+(?:need\s+to\s+)?"
        r"(?:bump|change|touch|raise|increment|update)\b[^.]{0,50}\bversion\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:never|no)\s+(?:need\s+to\s+)?(?:bump|version\s+(?:bump|change|update))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bonly\s+the\s+first\b[^.]{0,60}\b(?:bump|bumps|changes|version)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwithout\s+(?:a\s+|any\s+)?(?:bumping|bumps?|changing)\b[^.]{0,40}"
        r"\bversion\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bskip(?:s|ping)?\s+the\s+version\b", re.IGNORECASE),
]

PROHIBITION_LEAD_INS = re.compile(
    r"\b(?:never|must\s+not|may\s+not|cannot|not\s+(?:allowed|permitted)"
    r"|prohibit\w*|forbid\w*|forbidden"
    r"|no\s+(?:plan|task|statement|instruction|sentence|text|wording)\b"
    r"|such\s+as|for\s+example|e\.g\.)",
    re.IGNORECASE,
)

EXEMPT_STATEMENT = re.compile(r"(?<!non-)\bexempt\s+repositor", re.IGNORECASE)


def sentences(text):
    out = []
    for paragraph in paragraphs(text):
        out.extend(re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph))
    return out


def permissive_sentences(text):
    """Sentences that permit keeping the version unchanged on a
    plugin-changing commit in a non-exempt repository."""
    found = []
    for sentence in sentences(text):
        if "non-exempt" not in sentence and "outside" not in sentence.lower():
            if EXEMPT_STATEMENT.search(sentence):
                continue
        for pattern in PERMISSIVE_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue
            if PROHIBITION_LEAD_INS.search(sentence[: match.start()]):
                continue
            found.append(sentence)
            break
    return found


# The rule's distinctive wording; it is owned by plan-writing SKILL.md and
# must not be restated in the three rework documents (NFR1).
RESTATEMENT_PATTERNS = [
    re.compile(r"per-commit", re.IGNORECASE),
    re.compile(r"strictly\s+greater", re.IGNORECASE),
    re.compile(r"per-component", re.IGNORECASE),
    re.compile(r"\bbump(?:s|ed|ing)?\b", re.IGNORECASE),
]

# Field-table wording owned by planner-contract.md; the rework contract
# defines the input by citation only.
FIELD_TABLE_TOKENS = ["marketplace_versioned", "plugins[]"]


class CitationTests(unittest.TestCase):
    """AC-1 (FR4): each document cites the plan-writing section."""

    def _citing(self, name):
        text = read(DOCS[name])
        found = paragraphs_with(text, PLAN_WRITING_PATH, PLAN_WRITING_HEADING)
        self.assertTrue(
            found,
            f"{name}: no paragraph cites {PLAN_WRITING_PATH} with the "
            f"heading text {PLAN_WRITING_HEADING!r}",
        )
        return found

    def _assert_scope_and_files_rule(self, name):
        found = self._citing(name)
        good = [
            p
            for p in found
            if re.search(r"\bevery\b[^.]{0,60}\btask", p, re.IGNORECASE)
            and "`files`" in p
            and re.search(r"\brule\b", p)
        ]
        self.assertTrue(
            good,
            f"{name}: the citation must say the section applies to every "
            "synthesized task and name its `files` rule",
        )

    def test_agent_cites_plan_writing_section_for_every_task(self):
        self._assert_scope_and_files_rule("rework-planner.md")

    def test_contract_cites_plan_writing_section_for_every_task(self):
        self._assert_scope_and_files_rule("rework-planner-contract.md")

    def test_synthesis_cites_plan_writing_section_for_every_task(self):
        self._assert_scope_and_files_rule("rework-task-synthesis.md")


class NoRestatementAndNoPermissionTests(unittest.TestCase):
    """AC-2 (FR4, FR7, NFR1): citation only; no permission to keep the
    version unchanged."""

    def test_real_documents_do_not_restate_the_rule_text(self):
        for name, path in DOCS.items():
            text = read(path)
            for pattern in RESTATEMENT_PATTERNS:
                match = pattern.search(text)
                self.assertIsNone(
                    match,
                    f"{name} restates version rule wording: "
                    f"{match.group(0) if match else ''!r}",
                )

    def test_contract_does_not_restate_the_field_table(self):
        text = read(CONTRACT_PATH)
        for token in FIELD_TABLE_TOKENS:
            self.assertNotIn(
                token,
                text,
                "the field table is owned by planner-contract.md; the rework "
                "contract defines the input by citation only",
            )

    def test_real_documents_contain_no_permissive_statement(self):
        for name, path in DOCS.items():
            self.assertEqual(
                permissive_sentences(read(path)),
                [],
                f"{name} contains a statement letting a plugin-changing "
                "commit keep the version unchanged",
            )

    PERMISSIVE_SAMPLES = [
        "In a non-exempt repository, rework tasks do not bump the version.",
        "Only the first rework task bumps the version; later tasks keep the "
        "version unchanged.",
        "Rework tasks may leave the plugin version unchanged.",
        "Subsequent tasks do not need to change the version.",
        "A rework task needs no version bump because the original task "
        "already bumped it.",
        "The plugin version stays unchanged for rework tasks.",
        "Outside an exempt repository, rework tasks do not bump the version.",
        "Rework tasks skip the version update.",
    ]

    ACCEPTED_SAMPLES = [
        "A plan never instructs keeping the version unchanged on a commit "
        "that changes files under a plugin.",
        'No plan may contain an instruction such as "rework tasks do not '
        'bump the version".',
        "In an exempt repository, rework tasks do not change the version.",
        "A rework task must not leave the version unchanged in a "
        "non-exempt repository.",
        'It is forbidden to write "subsequent tasks keep the version '
        'unchanged".',
        "The task plan is applied unchanged.",
        "A rework task is not an exception to that section.",
    ]

    def test_check_rejects_permissive_samples(self):
        for sample in self.PERMISSIVE_SAMPLES:
            self.assertTrue(
                permissive_sentences(sample),
                f"permissive sample was not detected: {sample!r}",
            )

    def test_check_accepts_prohibition_and_exempt_wording(self):
        for sample in self.ACCEPTED_SAMPLES:
            self.assertEqual(
                permissive_sentences(sample),
                [],
                f"prohibition/exempt wording was wrongly rejected: {sample!r}",
            )

    def test_check_detects_a_permissive_sentence_injected_into_a_real_doc(self):
        injected = (
            read(AGENT_PATH)
            + "\nIn a non-exempt repository, rework tasks do not bump the "
            "version.\n"
        )
        self.assertTrue(permissive_sentences(injected))


class ContractInputTests(unittest.TestCase):
    """AC-3 (FR5) and AC-4 (TM-1): the contract's plugin_versioning input."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(CONTRACT_PATH)

    def _input_section(self):
        # Whitespace-normalized so assertions survive line wrapping.
        return " ".join(paragraphs(section(self.text, CONTRACT_INPUT_HEADING)))

    def test_input_is_defined_by_citing_the_planner_contract_subsection(self):
        body = self._input_section()
        self.assertIn(PLANNER_CONTRACT_PATH, body)
        self.assertIn(PLUGIN_VERSIONING_HEADING, body)

    def test_input_sits_in_the_worker_specific_input(self):
        self.assertTrue(
            paragraphs_with(self.text, FIELD, "rework_source"),
            "the contract must place plugin_versioning next to rework_source "
            "in the worker-specific input",
        )

    def test_input_is_mandatory_with_invalid_input_on_absence(self):
        body = self._input_section()
        self.assertRegex(body, r"(?i)\bmandatory\b")
        self.assertIn("invalid_input", body)
        self.assertTrue(
            [
                p
                for p in paragraphs(body)
                if re.search(r"(?i)\bmandatory\b", p) and "invalid_input" in p
            ],
            "mandatory status and invalid_input must be stated together",
        )

    def test_value_inputs_membership_is_declared(self):
        found = paragraphs_with(self.text, "value_inputs", FIELD)
        self.assertTrue(found, "no paragraph declares plugin_versioning in value_inputs")
        self.assertTrue(
            [p for p in found if "rework_source" in p],
            "the declaration must keep rework_source as a value_inputs member",
        )
        self.assertTrue(
            [p for p in found if re.search(r"\bmember", p)],
            "the declaration must state membership",
        )

    def test_old_single_member_statement_is_gone(self):
        for paragraph in paragraphs_with(self.text, "value_inputs"):
            self.assertFalse(
                re.search(r"for this worker is `rework_source` itself", paragraph),
                "value_inputs must not be declared as rework_source alone",
            )

    def test_input_is_untrusted_under_the_envelope_section(self):
        body = self._input_section()
        self.assertRegex(body, r"(?i)\buntrusted\b")
        self.assertIn("Untrusted-Input Handling", body)
        self.assertIn("worker-envelope.md", body)

    def test_input_is_limited_to_the_cited_definitions_fields(self):
        body = self._input_section()
        self.assertRegex(body, r"(?i)limited to the fields of the cited definition")
        self.assertRegex(body, r"(?i)no other text copied from repository files")


class DispatchProcedureTests(unittest.TestCase):
    """AC-5 (FR5): the rework-planner dispatch procedure
    (rework-task-synthesis.md Section 10, see the module docstring)."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(DISPATCH_DOC_PATH)

    def _procedure(self):
        found = paragraphs_with(self.text, FIELD, "value_inputs", "re-resolve")
        self.assertTrue(
            found,
            "no paragraph of the dispatch document states the resolve / pass "
            "/ value_inputs / re-resolve obligations together",
        )
        return found[0]

    def test_orchestrator_resolves_per_the_planner_contract_at_every_dispatch(self):
        paragraph = self._procedure()
        self.assertIn("orchestrator", paragraph)
        self.assertRegex(paragraph, r"(?i)\bresolves\b")
        self.assertIn(PLANNER_CONTRACT_PATH, paragraph)
        self.assertIn(PLUGIN_VERSIONING_HEADING, paragraph)
        self.assertRegex(paragraph, r"(?i)every\b[^.]{0,40}\bdispatch")

    def test_value_is_passed_in_the_worker_input(self):
        self.assertRegex(
            self._procedure(),
            r"(?i)\bpasses\b[^.]{0,80}\binput\b",
        )

    def test_value_is_included_in_value_inputs(self):
        self.assertRegex(
            self._procedure(),
            r"(?i)\b(?:includes|adds)\b[^.]{0,60}`value_inputs`",
        )

    def test_value_is_re_resolved_for_the_return_time_digest(self):
        paragraph = self._procedure()
        self.assertRegex(paragraph, r"(?i)\bre-resolves\b")
        self.assertRegex(paragraph, r"(?i)\breturn\b")
        self.assertIn("input_digest", paragraph)

    def test_dispatch_statement_is_under_the_workflow_state_transition_section(self):
        body = section(self.text, "## 10. Workflow state transition")
        self.assertIn(FIELD, body)


class AgentInputTests(unittest.TestCase):
    """AC-6 (FR5): rework-planner.md names plugin_versioning as an input."""

    def test_agent_names_plugin_versioning_among_its_inputs(self):
        found = paragraphs_with(read(AGENT_PATH), FIELD)
        self.assertTrue(found, "rework-planner.md does not name plugin_versioning")
        self.assertTrue(
            [p for p in found if re.search(r"(?i)\binputs?\b", p)],
            "plugin_versioning must be named as an input",
        )

    def test_agent_points_at_the_contract_for_the_definition(self):
        found = paragraphs_with(read(AGENT_PATH), FIELD, "rework-planner-contract.md")
        self.assertTrue(found)


class ModuleHygieneTests(unittest.TestCase):
    """AC-7 (FR7, NFR3): standard library and repository files only."""

    def test_module_imports_only_the_standard_library(self):
        tree = ast.parse(read(THIS_FILE))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])
        self.assertTrue(modules)
        self.assertLessEqual(modules, set(sys.stdlib_module_names))

    def test_module_never_touches_the_user_home(self):
        tree = ast.parse(read(THIS_FILE))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"expanduser", "home"})

    def test_module_reads_only_this_tasks_own_documents(self):
        self.assertEqual(
            {p.name for p in DOCS.values()},
            {
                "rework-planner.md",
                "rework-planner-contract.md",
                "rework-task-synthesis.md",
            },
        )
        for path in DOCS.values():
            self.assertTrue(path.is_file(), f"missing document: {path}")
            self.assertIn(REPO_ROOT, path.resolve().parents)


if __name__ == "__main__":
    unittest.main()
