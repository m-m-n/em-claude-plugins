"""Document-contract tests for task0003 (cd-prefix-toplevel-operators): the
handling of an approved string that the cd prefix form does not cover, in
`em-workflow/agents/implementer.md` (Step 3) and in
`em-workflow/skills/worktree-task-workflow/SKILL.md` (Command execution gate).

The hook stops allowing `cd "{worktree_path}" && <approved string>` when the
approved string holds a lone `&`, a `;`, a `||` or a line break at its top
level (or meets another exclusion condition of the protocol). Both
instruction sources of the implementer have to say that such a string is not
run (not with the cd prefix, not without it, not rewritten or split) and is
reported in `notes`, and that when the string is the test command the report
sets `tests: "fail"` with a `notes` entry saying the test command was not run
because the cd prefix form does not cover it. The full list of conditions
lives in `references/command-execution-protocol.md`; the two summaries cite it
and do not restate the safe-side constructs.

Scope: assertions touch only these two documents. Each assertion is scoped to
one section: the text between the section heading and the next heading of the
same or a higher level. Text is located by section headings and stable
phrases, never by line numbers, and is whitespace-normalized so that line
wrapping does not matter. A missing heading raises, so a renamed section never
lets an absence assertion pass over an empty string.

Covers this task's Acceptance Criteria
(feature-docs/cd-prefix-toplevel-operators/tasks/task0003.md):

- AC-1 (FR7, TM-4): implementer.md Step 3 holds one sentence that names the
  operators `&`, `;`, `||` and the line break with "top level" and states
  that such an approved string is not run and is reported in `notes`; Step 3
  cites `references/command-execution-protocol.md` for the full conditions.
- AC-2 (FR7, TM-4): the SKILL.md Command execution gate section holds the
  same statement and the same citation.
- AC-3 (FR7, TM-4): in both sections the handling text says the string is not
  run with the cd prefix, not run without it, and not rewritten or split.
- AC-4 (FR7): in both sections one sentence names `project_commands.test`,
  `tests: "fail"` and `notes` and states that when the string the cd prefix
  form does not cover is the test command, it is not run, the report sets
  `tests: "fail"`, and `notes` says it was not run because the cd prefix form
  does not cover it. The existing gate deny sentence alone does not satisfy
  the check.
- AC-5 (FR10): neither section restates the safe-side constructs (`$'`, `$"`,
  `${`, and a `#` condition); each absence assertion is paired with a
  forged-text case that its matcher flags.
- AC-6 (NFR5, NFR6): `tests/test_implementer_cd_chain_docs.py` and
  `tests/test_worktree_skill_instruction_source.py` pass unedited; they are
  separate modules of the same suite and are not imported here.
- AC-7 (FR10, NFR7): this module locates text by heading, normalizes
  whitespace, imports the standard library only, and
  `python3 -m unittest discover -s tests` passing is the suite run itself.

Follows the established convention: standard library only, repository root
computed from this module's own path, whitespace-normalized matching.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "worktree-task-workflow" / "SKILL.md"

STEP_3_NAME = "Step 3: Verify the worktree"
GATE_NAME = "Command execution gate"

CD_PREFIX = 'cd "{worktree_path}" &&'
PROTOCOL_CITATION = "references/command-execution-protocol.md"
PLUGIN_ROOT_CITATION = "${CLAUDE_PLUGIN_ROOT}"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_START = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def section_text(text, name, source="document"):
    """The section whose heading text is `name` (optionally followed by more
    words): from the line after its heading up to (not including) the next
    heading of the same or a higher level, or end of file. Headings inside
    fenced code blocks are ignored. Raises AssertionError when the heading is
    absent, so a renamed heading fails loudly instead of letting an absence
    check pass over an empty string."""
    lines = text.splitlines()
    in_fence = False
    start = None
    level = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        heading = match.group(2)
        if start is None:
            if heading == name or heading.startswith(name + " "):
                start = i + 1
                level = depth
            continue
        if depth <= level:
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"heading not found in {source}: {name}")
    return "\n".join(lines[start:])


def blocks(text):
    """Split into paragraph / list-item blocks: a blank line or a bullet or
    numbered-list start begins a new block. Each block is whitespace-
    normalized, so wrapped continuation lines join their item."""
    out = []
    current = []

    def flush():
        if current:
            out.append(_normalize_ws(" ".join(current)))
            current.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _BULLET_START.match(line):
            flush()
        current.append(line)
    flush()
    return out


def sentences(text):
    """Sentences of every block of `text`, whitespace-normalized. A sentence
    ends at a full stop followed by whitespace."""
    out = []
    for block in blocks(text):
        out.extend(s for s in re.split(r"(?<=\.)\s+", block) if s)
    return out


def sentences_with(text, *terms):
    """The sentences of `text` that contain every term (case-sensitive)."""
    return [s for s in sentences(text) if all(t in s for t in terms)]


# --- matchers ---------------------------------------------------------------


def find_operator_sentences(text):
    """AC-1 / AC-2: sentences that name the four top-level operators in their
    backtick form (`&`, `;`, `||` and the line break) with "top level" and say
    the approved string is not run and is reported in `notes`. The backtick
    form keeps the `&&` of the cd prefix from standing in for `&`."""
    return [
        s
        for s in sentences(text)
        if all(t in s for t in ("`&`", "`;`", "`||`", "line break", "top level", "`notes`"))
        and re.search(r"\bnot run\b|\bdo not run\b", s)
    ]


def find_citation_sentences(text):
    """AC-1 / AC-2: sentences that cite the Verbatim execution rule of the
    protocol document for the full list of conditions."""
    return [
        s
        for s in sentences(text)
        if all(
            t in s
            for t in ("Verbatim execution rule", PROTOCOL_CITATION, "conditions")
        )
    ]


def find_handling_sentences(text):
    """AC-3: sentences that say the string is not run with the cd prefix, not
    run without it, and not rewritten or split."""
    return [
        s
        for s in sentences(text)
        if all(
            t in s
            for t in (CD_PREFIX, "not run", "without the prefix", "rewrite", "split")
        )
    ]


def find_test_command_sentences(text):
    """AC-4: sentences that tie the not-covered string to the test command:
    `project_commands.test`, `tests: "fail"` and `notes` in one sentence, the
    test command not run (the baseline run included), and the reason that the
    cd prefix form does not cover it."""
    return [
        s
        for s in sentences(text)
        if all(
            t in s
            for t in (
                "`project_commands.test`",
                'tests: "fail"',
                "`notes`",
                "not run",
                "baseline",
                "does not cover",
            )
        )
    ]


def find_safe_side_hits(text):
    """AC-5: the safe-side constructs a summary must not restate: `$'`, `$"`,
    `${` and a `#`. The plugin-root path variable the gate section already uses
    in its protocol citation is not a restatement and is removed first."""
    cleaned = text.replace(PLUGIN_ROOT_CITATION, "")
    return [token for token in ("$'", '$"', "${", "#") if token in cleaned]


# --- documents --------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def step3_section():
    return section_text(_read(IMPLEMENTER_PATH), STEP_3_NAME, "implementer.md")


def gate_section():
    return section_text(_read(SKILL_PATH), GATE_NAME, "SKILL.md")


SECTIONS = (
    ("implementer.md Step 3", step3_section),
    ("SKILL.md Command execution gate", gate_section),
)


# Forged text for the paired absence / presence assertions.
FORGED_DENY_ONLY = (
    "- If the hook denies a command: do NOT retry, rephrase, or restructure the\n"
    "  command to evade the match. Run nothing, set `tests: \"fail\"`, and explain\n"
    "  in `notes` (per-command AskUserQuestion is unavailable to you).\n"
)
FORGED_TEST_COMMAND_WITHOUT_REASON = (
    "- When the approved string is the test command (`project_commands.test`), "
    "run nothing, set `tests: \"fail\"` and explain in `notes`.\n"
)
FORGED_OPERATORS_WITH_CD_PREFIX_ONLY = (
    "- An approved string with a `&&` at its top level is not run, and you "
    "report it in `notes`.\n"
)
FORGED_OPERATORS_MISSING_ONE = (
    "- An approved string with a lone `&`, a `;` or a line break at its top "
    "level is not run, and you report it in `notes`.\n"
)
FORGED_OPERATORS_WITHOUT_REPORT = (
    "- An approved string with a lone `&`, a `;`, a `||` or a line break at "
    "its top level is not run.\n"
)
FORGED_HANDLING_MISSING_SPLIT = (
    'Do not run such a string with the `cd "{worktree_path}" &&` prefix, do '
    "not run it without the prefix, and do not rewrite it.\n"
)
FORGED_HANDLING_MISSING_WITHOUT = (
    'Do not run such a string with the `cd "{worktree_path}" &&` prefix, and '
    "do not rewrite or split it.\n"
)
FORGED_CITATION_WITHOUT_RULE = (
    "The full list is in `references/command-execution-protocol.md`.\n"
)


class TestSectionScoping(unittest.TestCase):
    """The sections are located and scoped by heading (AC-7)."""

    def test_section_text_ends_at_next_heading_of_same_or_higher_level(self):
        text = (
            "# Top\n\n"
            "## A\n\nbody a\n\n### A sub\n\nsub body\n\n"
            "## B\n\nbody b\n\n"
            "# Top 2\n\nbody top 2\n"
        )
        a = section_text(text, "A")
        self.assertIn("body a", a)
        self.assertIn("sub body", a)
        self.assertNotIn("body b", a)
        self.assertEqual(_normalize_ws(section_text(text, "B")), "body b")

    def test_section_text_ignores_headings_inside_fenced_code(self):
        text = "## A\n\nbefore\n\n```\n## not a heading\n```\n\nafter\n\n## B\n\nb\n"
        a = section_text(text, "A")
        self.assertIn("before", a)
        self.assertIn("after", a)

    def test_section_text_raises_for_missing_heading(self):
        with self.assertRaises(AssertionError):
            section_text("## A\n\nx\n", "Missing")

    def test_a_renamed_heading_fails_loudly_instead_of_passing_on_empty_text(self):
        renamed = "## Step 3: Check the worktree\n\nbody\n"
        with self.assertRaises(AssertionError):
            section_text(renamed, STEP_3_NAME, "implementer.md")

    def test_every_section_is_found_and_nonempty(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                self.assertTrue(getter().strip())

    def test_neighbouring_sections_are_not_swallowed(self):
        self.assertNotIn("Step 4", step3_section())
        self.assertNotIn("Untrusted input", gate_section())


class TestMatchersAreNotVacuous(unittest.TestCase):
    """Each matcher is shown to accept the intended wording and to reject near
    misses, so a passing assertion on the real documents means something."""

    GOOD_OPERATORS = (
        "- An approved string with a lone `&`, a `;`, a `||` or a line break at "
        "its top level is not covered by the cd prefix form, so it is not run, "
        "and you report it in `notes`.\n"
    )
    GOOD_CITATION = (
        "The full list of conditions is in the Verbatim execution rule of "
        "`references/command-execution-protocol.md`.\n"
    )
    GOOD_HANDLING = (
        'Do not run such a string with the `cd "{worktree_path}" &&` prefix, do '
        "not run it without the prefix, and do not rewrite or split it.\n"
    )
    GOOD_TEST_COMMAND = (
        "When the approved string that the cd prefix form does not cover is the "
        "test command (`project_commands.test`), the test command is not run at "
        'any point, the baseline run included, the report sets `tests: "fail"`, '
        "and `notes` says that the test command was not run because the cd "
        "prefix form does not cover it.\n"
    )

    def test_operator_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_operator_sentences(self.GOOD_OPERATORS)), 1)

    def test_operator_matcher_rejects_the_cd_prefix_ampersands_alone(self):
        self.assertEqual(find_operator_sentences(FORGED_OPERATORS_WITH_CD_PREFIX_ONLY), [])

    def test_operator_matcher_rejects_a_sentence_missing_an_operator(self):
        self.assertEqual(find_operator_sentences(FORGED_OPERATORS_MISSING_ONE), [])

    def test_operator_matcher_rejects_a_sentence_without_the_notes_report(self):
        self.assertEqual(find_operator_sentences(FORGED_OPERATORS_WITHOUT_REPORT), [])

    def test_citation_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_citation_sentences(self.GOOD_CITATION)), 1)

    def test_citation_matcher_rejects_a_bare_path_mention(self):
        self.assertEqual(find_citation_sentences(FORGED_CITATION_WITHOUT_RULE), [])

    def test_handling_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_handling_sentences(self.GOOD_HANDLING)), 1)

    def test_handling_matcher_rejects_a_sentence_missing_split(self):
        self.assertEqual(find_handling_sentences(FORGED_HANDLING_MISSING_SPLIT), [])

    def test_handling_matcher_rejects_a_sentence_missing_the_no_prefix_case(self):
        self.assertEqual(find_handling_sentences(FORGED_HANDLING_MISSING_WITHOUT), [])

    def test_test_command_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_test_command_sentences(self.GOOD_TEST_COMMAND)), 1)

    def test_test_command_matcher_rejects_the_existing_deny_wording_alone(self):
        self.assertEqual(find_test_command_sentences(FORGED_DENY_ONLY), [])

    def test_test_command_matcher_rejects_a_sentence_without_the_cover_reason(self):
        self.assertEqual(
            find_test_command_sentences(FORGED_TEST_COMMAND_WITHOUT_REASON), []
        )

    def test_safe_side_matcher_flags_each_construct(self):
        forged = {
            "$'": "A `$'` anywhere in the string excludes it.",
            '$"': 'A `$"` anywhere in the string excludes it.',
            "${": "A `${` anywhere in the string excludes it.",
            "#": "A `#` anywhere in the string excludes it.",
        }
        for token, text in forged.items():
            with self.subTest(token=token):
                self.assertEqual(find_safe_side_hits(text), [token])

    def test_safe_side_matcher_accepts_the_plugin_root_path_variable(self):
        text = (
            "(`${CLAUDE_PLUGIN_ROOT}/references/command-execution-protocol.md`)"
        )
        self.assertEqual(find_safe_side_hits(text), [])

    def test_safe_side_matcher_still_flags_a_brace_next_to_the_plugin_root(self):
        text = "`${CLAUDE_PLUGIN_ROOT}` and also a `${HOME}` expansion."
        self.assertEqual(find_safe_side_hits(text), ["${"])


class TestAC1ImplementerStep3(unittest.TestCase):
    """AC-1 (FR7, TM-4): implementer.md Step 3."""

    def test_ac1_one_sentence_names_the_operators_and_says_not_run_and_noted(self):
        hits = find_operator_sentences(step3_section())
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_cites_the_protocol_verbatim_execution_rule_for_the_conditions(self):
        hits = find_citation_sentences(step3_section())
        self.assertEqual(len(hits), 1, sentences(step3_section()))


class TestAC2SkillCommandExecutionGate(unittest.TestCase):
    """AC-2 (FR7, TM-4): SKILL.md Command execution gate."""

    def test_ac2_one_sentence_names_the_operators_and_says_not_run_and_noted(self):
        hits = find_operator_sentences(gate_section())
        self.assertEqual(len(hits), 1, sentences(gate_section()))

    def test_ac2_cites_the_protocol_verbatim_execution_rule_for_the_conditions(self):
        hits = find_citation_sentences(gate_section())
        self.assertEqual(len(hits), 1, sentences(gate_section()))


class TestAC3HandlingInBothSections(unittest.TestCase):
    """AC-3 (FR7, TM-4): not run with the prefix, not run without it, not
    rewritten or split."""

    def test_ac3_handling_sentence_is_in_both_sections(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                hits = find_handling_sentences(getter())
                self.assertEqual(len(hits), 1, sentences(getter()))


class TestAC4TestCommandReportValue(unittest.TestCase):
    """AC-4 (FR7): the test command that the cd prefix form does not cover is
    not run and the report sets `tests: "fail"`."""

    def test_ac4_one_sentence_ties_the_not_covered_string_to_the_test_command(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                hits = find_test_command_sentences(getter())
                self.assertEqual(len(hits), 1, sentences(getter()))

    def test_ac4_the_existing_gate_deny_sentence_alone_does_not_satisfy_it(self):
        # The gate section keeps its deny bullet; the check must be satisfied
        # by a different sentence.
        deny = sentences_with(
            gate_section(), "Run nothing, set", 'tests: "fail"', "`notes`"
        )
        self.assertEqual(len(deny), 1, sentences(gate_section()))
        self.assertEqual(find_test_command_sentences(" ".join(deny)), [])
        self.assertNotIn(deny[0], find_test_command_sentences(gate_section()))

    def test_ac4_the_existing_deny_bullet_is_unchanged(self):
        section = _normalize_ws(gate_section())
        for expected in (
            "If the hook denies a command: do NOT retry, rephrase, or restructure",
            'Run nothing, set `tests: "fail"`, and explain in `notes`',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)


class TestAC5NoSafeSideRestatement(unittest.TestCase):
    """AC-5 (FR10): neither section restates the safe-side constructs. Each
    absence assertion is paired with a forged-text case in
    TestMatchersAreNotVacuous.test_safe_side_matcher_flags_each_construct."""

    def test_ac5_neither_section_restates_the_safe_side_constructs(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                self.assertEqual(find_safe_side_hits(getter()), [])

    def test_ac5_sections_name_no_other_exclusion_construct_words(self):
        for label, getter in SECTIONS:
            section = _normalize_ws(getter()).lower()
            for phrase in (
                "unclosed",
                "trailing backslash",
                "parenthes",
                "command substitution",
                "backtick",
            ):
                with self.subTest(section=label, phrase=phrase):
                    self.assertNotIn(phrase, section)


class TestAC6ExistingConstraintsStayIntact(unittest.TestCase):
    """AC-6 (NFR5, NFR6): the two existing modules run unedited in the same
    suite. The wording constraints they pin on these sections are re-checked
    here against the added text, so a violation is named in this module too."""

    @staticmethod
    def _cd_and_separate(s):
        return bool(re.search(r"\bseparate\b", s) and re.search(r"\bcd\b", s))

    @staticmethod
    def _chain_prohibition(s):
        return bool(
            "chain" in s
            and "&&" in s
            and re.search(r"\b(?:never|not|don't)\b", s, re.IGNORECASE)
        )

    def test_no_sentence_asks_for_a_separate_cd_or_forbids_chaining_or_says_may_reset(self):
        for label, getter in SECTIONS:
            for s in sentences(getter()):
                with self.subTest(section=label, sentence=s[:50]):
                    self.assertFalse(self._cd_and_separate(s), s)
                    self.assertFalse(self._chain_prohibition(s), s)
                    self.assertNotIn("may reset", s)
                    self.assertNotIn("may have reset", s)

    def test_gate_section_keeps_byte_for_byte_once_and_no_other_byte_wording(self):
        section = _normalize_ws(gate_section())
        self.assertEqual(section.count("(byte-for-byte)"), 1)
        self.assertNotIn("byte", section.replace("(byte-for-byte)", ""))
        for phrase in ("identical to", "equal to the line"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, section)

    def test_gate_section_adds_no_second_copy_of_the_pinned_sentences(self):
        section = gate_section()
        checks = (
            ("The only prefix allowed is", CD_PREFIX, "same Bash call"),
            ("cwd", "does not persist between Bash calls"),
            ("Never prefix", "environment assignments"),
            ("JSON-decoded value",),
            ("decoded value", "verbatim rule", "approval rule"),
            ("empty string", "no such command"),
        )
        for terms in checks:
            with self.subTest(terms=terms):
                self.assertEqual(len(sentences_with(section, *terms)), 1)

    def test_step3_adds_no_second_copy_of_the_pinned_sentences(self):
        section = step3_section()
        checks = (
            ("cwd", "does not persist between Bash calls"),
            (
                'cd "{worktree_path}" && <command>',
                "single Bash call",
                "tests",
                "builds",
                "formats",
                "`merge_script`",
            ),
            ('git -C "{worktree_path}"', "for git"),
            ("`<command>`", "approved string", "environment assignment"),
            ("main tree", "`base_branch`"),
        )
        for terms in checks:
            with self.subTest(terms=terms):
                self.assertEqual(len(sentences_with(section, *terms)), 1)

    def test_step3_keeps_the_read_and_write_boundary_sentence(self):
        self.assertIn(
            "You MUST NOT read from or write to any path outside `worktree_path` "
            "except: reading `task_plan_path` / `implementation_md_path` / "
            "`lessons_path`, and executing `merge_script`.",
            _normalize_ws(step3_section()),
        )


class TestAC7Mechanics(unittest.TestCase):
    """AC-7 (FR10, NFR7)."""

    def test_this_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])


if __name__ == "__main__":
    unittest.main()
