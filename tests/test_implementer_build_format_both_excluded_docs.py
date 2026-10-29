"""Document-contract tests for task0001 (build-format-both-excluded-tests):
what decides the report's `tests` when the approved build string and the
approved format string both fall outside the cd prefix form. The statement
lives in `em-workflow/agents/implementer.md` (Step 3) and in
`em-workflow/skills/worktree-task-workflow/SKILL.md` (Command execution gate).

The existing format sentence says the report's `tests` follows the result of
the test command, and the existing build sentence says the report sets
`tests: "fail"`. Read together, the two leave no single value when both
strings are excluded and the test command passes. Each document therefore
carries one more sentence (the FR1 sentence): not running the format command
does not override a `tests: "fail"` that another rule decides, and the case
where the build command is also an approved string that the cd prefix form
does not cover is cited as the example of "another rule". This module pins that
sentence, one per section.

Scope: assertions touch only these two documents. Each assertion is scoped to
one section: the text between the section heading and the next heading of the
same or a higher level. Text is located by section headings, never by line
numbers, and is whitespace-normalized so that line wrapping does not matter.
Matching is sentence by sentence. A missing heading raises, so a renamed
section never lets an assertion pass over an empty string.

Covers this task's Acceptance Criteria
(feature-docs/build-format-both-excluded-tests/tasks/task0001.md):

- AC-1 (FR1, FR2, TM-1): the Step 3 section holds exactly one FR1 sentence,
  and it is not the existing format sentence.
- AC-2 (FR1, FR2, TM-1): the gate section holds exactly one FR1 sentence, and
  it is not the existing format sentence.
- AC-3 (FR3): the FR1 matcher accepts the intended sentence and rejects the
  false sentences.
- AC-4 (FR3): sections are taken by heading; a renamed heading raises.
- AC-5 (NFR1, NFR2, NFR3, NFR5): the neighbouring modules run unedited in the
  same suite; they are separate modules and are not imported here.
- AC-6 (NFR5): this module imports the standard library only.
- AC-7 (FR2, NFR4): the two documents change by added lines only and the plugin
  version is untouched. This is a property of the task branch's diff, checked
  with git, not a unit test.

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
    absent, so a renamed heading fails loudly instead of letting an assertion
    pass over an empty string."""
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


# --- matchers ---------------------------------------------------------------


# The three elements of the FR1 sentence, each keyed on a literal phrase.
# Element 1 and 2 share one phrase: the subject of the sentence is the format
# command not being run, and what it does not do is override a
# `tests: "fail"` that another rule decides.
_FORMAT_NOT_RUN_DOES_NOT_OVERRIDE_ANOTHER_RULES_FAIL = re.compile(
    r"\bnot running the format command does not override a `tests: \"fail\"` "
    r"that another rule decides\b",
    re.IGNORECASE,
)
# Element 3: the cited example, the build command also being an approved string
# that the cd prefix form does not cover.
_BUILD_COMMAND_ALSO_NOT_COVERED = re.compile(
    r"\bthe build command is also an approved string that the cd prefix form "
    r"does not cover\b",
    re.IGNORECASE,
)


def find_fr1_sentences(text):
    """The FR1 sentences: sentences that carry, within the sentence itself, all
    three elements. (1) the format command not being run, (2) that this does not
    override a `tests: "fail"` decided by another rule, (3) the case where the
    build command is also an approved string that the cd prefix form does not
    cover. A sentence missing, flipping or negating any one element is not
    returned, and elements spread over two sentences do not count."""
    return [
        s
        for s in sentences(text)
        if _FORMAT_NOT_RUN_DOES_NOT_OVERRIDE_ANOTHER_RULES_FAIL.search(s)
        and _BUILD_COMMAND_ALSO_NOT_COVERED.search(s)
    ]


def find_existing_format_sentences(text):
    """The existing format sentence: `project_commands.format` and the format
    command not run in one sentence. Used only to show that the FR1 sentence is
    a different sentence from it."""
    return [
        s
        for s in sentences(text)
        if "`project_commands.format`" in s
        and re.search(r"\bthe format command is not run\b", s)
    ]


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


# Intended wording, and forged text for the paired accept / reject assertions.
GOOD_FR1 = (
    "Not running the format command does not override a `tests: \"fail\"` that "
    "another rule decides, for example when the build command is also an "
    "approved string that the cd prefix form does not cover."
)
GOOD_FR1_AS_WRAPPED_BULLET = (
    "- Not running the format command does not override a `tests: \"fail\"`\n"
    "  that another rule decides, for example when the build command is also\n"
    "  an approved string that the cd prefix form does not cover.\n"
)
# False sentence 1: both strings excluded, but `tests` follows the test command.
FALSE_1_FOLLOWS_TEST_COMMAND = (
    "Even when the build command and the format command both fall outside the "
    "cd prefix form, the report's `tests` follows the result of the test "
    "command."
)
# False sentence 2: the not-override statement without the build case.
FALSE_2_WITHOUT_BUILD_CASE = (
    "Not running the format command does not override a `tests: \"fail\"` that "
    "another rule decides."
)
# False sentence 3: the existing format sentence, verbatim as it stands in the
# two documents (prose form in implementer.md, bullet form in SKILL.md).
FALSE_3_EXISTING_FORMAT_PROSE = (
    "When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, the report's `tests` follows the result of the test command, not "
    'running the format command does not, on its own, make `tests` "fail", and '
    "`notes` says that the format command was not run because the cd prefix "
    "form does not cover it.\n"
)
FALSE_3_EXISTING_FORMAT_BULLET = (
    "- When the approved string that the cd prefix form does not cover is the\n"
    "  format command (`project_commands.format`), the format command is not run,\n"
    "  the report's `tests` follows the result of the test command, not running the\n"
    '  format command does not, on its own, make `tests` "fail", and `notes` says\n'
    "  that the format command was not run because the cd prefix form does not\n"
    "  cover it.\n"
)
# Each element of the FR1 matcher is load-bearing: drop or flip exactly one.
FALSE_NO_NEGATION = (
    "Not running the format command does override a `tests: \"fail\"` that "
    "another rule decides, for example when the build command is also an "
    "approved string that the cd prefix form does not cover."
)
FALSE_NOT_THE_FORMAT_COMMAND = (
    "Not running the build command does not override a `tests: \"fail\"` that "
    "another rule decides, for example when the build command is also an "
    "approved string that the cd prefix form does not cover."
)
FALSE_WITHOUT_ANOTHER_RULE = (
    "Not running the format command does not override a `tests: \"fail\"` that "
    "the test command reports, for example when the build command is also an "
    "approved string that the cd prefix form does not cover."
)
FALSE_BUILD_CASE_IN_ANOTHER_SENTENCE = (
    "Not running the format command does not override a `tests: \"fail\"` that "
    "another rule decides. Likewise the build command is also an approved "
    "string that the cd prefix form does not cover."
)
FALSE_BUILD_CASE_NEGATED = (
    "Not running the format command does not override a `tests: \"fail\"` that "
    "another rule decides, for example when the build command is not also an "
    "approved string that the cd prefix form does not cover."
)


class TestSectionScoping(unittest.TestCase):
    """The sections are located and scoped by heading (AC-4)."""

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

    def test_every_section_is_found_and_nonempty(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                self.assertTrue(getter().strip())

    def test_neighbouring_sections_are_not_swallowed(self):
        self.assertNotIn("Step 4", step3_section())
        self.assertNotIn("Untrusted input", gate_section())


class TestAC4RenamedHeadings(unittest.TestCase):
    """AC-4 (FR3): a renamed heading raises; matching never passes over empty
    text."""

    def test_ac4_a_renamed_step3_heading_raises_instead_of_passing_on_empty_text(self):
        renamed = "### Step 3: Check the worktree\n\nbody\n"
        with self.assertRaises(AssertionError):
            section_text(renamed, STEP_3_NAME, "implementer.md")

    def test_ac4_a_renamed_gate_heading_raises_instead_of_passing_on_empty_text(self):
        renamed = "## Command execution check (workflow.yaml strings)\n\nbody\n"
        with self.assertRaises(AssertionError):
            section_text(renamed, GATE_NAME, "SKILL.md")

    def test_ac4_matching_on_a_renamed_step3_document_never_reaches_a_match(self):
        renamed = "### Step 3: Check the worktree\n\n" + GOOD_FR1 + "\n"
        with self.assertRaises(AssertionError):
            find_fr1_sentences(section_text(renamed, STEP_3_NAME, "implementer.md"))

    def test_ac4_matching_on_a_renamed_gate_document_never_reaches_a_match(self):
        renamed = "## Command execution check (workflow.yaml strings)\n\n" + GOOD_FR1 + "\n"
        with self.assertRaises(AssertionError):
            find_fr1_sentences(section_text(renamed, GATE_NAME, "SKILL.md"))

    def test_ac4_the_real_step3_document_with_its_heading_renamed_raises(self):
        text = _read(IMPLEMENTER_PATH)
        heading = "### " + STEP_3_NAME
        self.assertIn(heading, text)
        renamed = text.replace(heading, "### Step 3: Check the worktree")
        with self.assertRaises(AssertionError):
            section_text(renamed, STEP_3_NAME, "implementer.md")

    def test_ac4_the_real_gate_document_with_its_heading_renamed_raises(self):
        text = _read(SKILL_PATH)
        heading = "## " + GATE_NAME + " (workflow.yaml strings)"
        self.assertIn(heading, text)
        renamed = text.replace(heading, "## Command execution check (workflow.yaml strings)")
        with self.assertRaises(AssertionError):
            section_text(renamed, GATE_NAME, "SKILL.md")


class TestAC3MatcherIsNotVacuous(unittest.TestCase):
    """AC-3 (FR3): the FR1 matcher is shown to accept the intended wording and
    to reject near misses, so a passing assertion on the real documents means
    something."""

    def test_ac3_the_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_fr1_sentences(GOOD_FR1)), 1)

    def test_ac3_the_intended_sentence_splits_into_exactly_one_sentence(self):
        self.assertEqual(len(sentences(GOOD_FR1)), 1)

    def test_ac3_the_matcher_accepts_the_intended_sentence_in_a_wrapped_bullet(self):
        self.assertEqual(len(find_fr1_sentences(GOOD_FR1_AS_WRAPPED_BULLET)), 1)

    def test_ac3_false_sentence_1_both_excluded_but_tests_follows_the_test_command(self):
        self.assertEqual(find_fr1_sentences(FALSE_1_FOLLOWS_TEST_COMMAND), [])

    def test_ac3_false_sentence_2_the_not_override_statement_without_the_build_case(self):
        self.assertEqual(find_fr1_sentences(FALSE_2_WITHOUT_BUILD_CASE), [])

    def test_ac3_false_sentence_3_the_existing_format_sentence_in_prose_form(self):
        self.assertEqual(find_fr1_sentences(FALSE_3_EXISTING_FORMAT_PROSE), [])

    def test_ac3_false_sentence_3_the_existing_format_sentence_in_bullet_form(self):
        self.assertEqual(find_fr1_sentences(FALSE_3_EXISTING_FORMAT_BULLET), [])

    def test_ac3_the_matcher_rejects_a_statement_that_the_override_does_happen(self):
        self.assertEqual(find_fr1_sentences(FALSE_NO_NEGATION), [])

    def test_ac3_the_matcher_rejects_a_sentence_about_a_command_other_than_format(self):
        self.assertEqual(find_fr1_sentences(FALSE_NOT_THE_FORMAT_COMMAND), [])

    def test_ac3_the_matcher_rejects_a_sentence_without_another_rule(self):
        self.assertEqual(find_fr1_sentences(FALSE_WITHOUT_ANOTHER_RULE), [])

    def test_ac3_the_matcher_rejects_elements_spread_over_two_sentences(self):
        self.assertEqual(find_fr1_sentences(FALSE_BUILD_CASE_IN_ANOTHER_SENTENCE), [])

    def test_ac3_the_matcher_rejects_a_negated_build_case(self):
        self.assertEqual(find_fr1_sentences(FALSE_BUILD_CASE_NEGATED), [])

    def test_ac3_the_existing_format_matcher_recognises_the_existing_sentence(self):
        # Guards the "different from the existing format sentence" assertions
        # against a helper that silently matches nothing.
        for label, text in (
            ("prose", FALSE_3_EXISTING_FORMAT_PROSE),
            ("bullet", FALSE_3_EXISTING_FORMAT_BULLET),
        ):
            with self.subTest(form=label):
                self.assertEqual(len(find_existing_format_sentences(text)), 1)

    def test_ac3_the_existing_format_matcher_does_not_recognise_the_fr1_sentence(self):
        self.assertEqual(find_existing_format_sentences(GOOD_FR1), [])


class TestAC1Step3Statement(unittest.TestCase):
    """AC-1 (FR1, FR2, TM-1): Step 3 holds exactly one FR1 sentence, distinct
    from the existing format sentence."""

    def test_ac1_step3_holds_exactly_one_fr1_sentence(self):
        hits = find_fr1_sentences(step3_section())
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_the_step3_fr1_sentence_is_not_the_existing_format_sentence(self):
        hits = find_fr1_sentences(step3_section())
        existing = find_existing_format_sentences(step3_section())
        self.assertEqual(len(hits), 1, sentences(step3_section()))
        self.assertEqual(len(existing), 1, sentences(step3_section()))
        self.assertNotEqual(hits[0], existing[0])


class TestAC2GateStatement(unittest.TestCase):
    """AC-2 (FR1, FR2, TM-1): the gate section holds exactly one FR1 sentence,
    distinct from the existing format sentence."""

    def test_ac2_gate_section_holds_exactly_one_fr1_sentence(self):
        hits = find_fr1_sentences(gate_section())
        self.assertEqual(len(hits), 1, sentences(gate_section()))

    def test_ac2_the_gate_fr1_sentence_is_not_the_existing_format_sentence(self):
        hits = find_fr1_sentences(gate_section())
        existing = find_existing_format_sentences(gate_section())
        self.assertEqual(len(hits), 1, sentences(gate_section()))
        self.assertEqual(len(existing), 1, sentences(gate_section()))
        self.assertNotEqual(hits[0], existing[0])


class TestAC6Mechanics(unittest.TestCase):
    """AC-6 (NFR5): this module imports the standard library only. The
    neighbouring modules run unedited in the same suite."""

    def test_ac6_this_module_imports_only_the_standard_library(self):
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
