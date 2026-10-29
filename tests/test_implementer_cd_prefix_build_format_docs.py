"""Document-contract tests for task0001 (cd-prefix-excluded-build-format-tests):
what the report's `tests` holds, and what `notes` says, when the approved
string that the cd prefix form does not cover is the build command or the
format command. The statements live in `em-workflow/agents/implementer.md`
(Step 3) and in `em-workflow/skills/worktree-task-workflow/SKILL.md` (Command
execution gate).

The test command's counterpart is already written and pinned by
`tests/test_implementer_cd_prefix_exclusion_docs.py`; this module pins the two
statements that sit beside it:

- build command: it is not run, the report sets `tests: "fail"`, and `notes`
  says the build command was not run because the cd prefix form does not cover
  it;
- format command: it is not run, the report's `tests` follows the result of the
  test command (not running the format command is not, on its own, a reason to
  set `tests: "fail"`), and `notes` says the format command was not run because
  the cd prefix form does not cover it.

Scope: assertions touch only these two documents. Each assertion is scoped to
one section: the text between the section heading and the next heading of the
same or a higher level. Text is located by section headings, never by line
numbers, and is whitespace-normalized so that line wrapping does not matter.
Matching is sentence by sentence. A missing heading raises, so a renamed
section never lets an assertion pass over an empty string.

Covers this task's Acceptance Criteria
(feature-docs/cd-prefix-excluded-build-format-tests/tasks/task0001.md):

- AC-1 (FR1, FR3, TM-1): both sections hold exactly one build sentence.
- AC-2 (FR2, FR3, TM-1): both sections hold exactly one format sentence.
- AC-3 (FR4, TM-1): the existing sentences stay as they are. The existing
  modules `test_implementer_cd_prefix_exclusion_docs` and
  `test_implementer_untrusted_data_rule` assert it; they are separate modules
  of the same suite and are not imported here.
- AC-4 (FR5): sections are taken by heading; a renamed heading raises.
- AC-5 (FR5): every matcher is paired with a sentence it accepts and forged
  sentences it rejects.
- AC-6 (NFR1, NFR2, NFR3, NFR5): the neighbouring modules run unedited in the
  same suite; this module imports the standard library only.

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


def sentences_with(text, *terms):
    """The sentences of `text` that contain every term (case-sensitive)."""
    return [s for s in sentences(text) if all(t in s for t in terms)]


# --- matchers ---------------------------------------------------------------


def find_build_sentences(text):
    """AC-1: sentences that tie the not-covered string to the build command:
    `project_commands.build`, `tests: "fail"` and `notes` in one sentence, the
    build command not run, the report setting `tests: "fail"`, and `notes`
    saying the build command was not run because the cd prefix form does not
    cover it."""
    return [
        s
        for s in sentences(text)
        if all(
            t in s
            for t in (
                "`project_commands.build`",
                'tests: "fail"',
                "`notes`",
                "not run",
                "does not cover",
            )
        )
        and re.search(r"\bthe build command is not run\b", s)
        and re.search(r"\bthe report sets `tests: \"fail\"`", s)
        and re.search(
            r"`notes` says that the build command was not run because the cd "
            r"prefix form does not cover it",
            s,
        )
    ]


def find_format_sentences(text):
    """AC-2: sentences that tie the not-covered string to the format command:
    `project_commands.format` and `notes` in one sentence, the format command
    not run, `tests` following the result of the test command, not running the
    format command not on its own making `tests` "fail", and `notes` saying the
    format command was not run because the cd prefix form does not cover it. A
    sentence that has the report setting `tests: "fail"` for the format case is
    rejected."""
    return [
        s
        for s in sentences(text)
        if all(
            t in s
            for t in (
                "`project_commands.format`",
                "`notes`",
                "not run",
                "does not cover",
            )
        )
        and re.search(r"\bthe format command is not run\b", s)
        and re.search(r"`tests` follows the result of the test command", s)
        and re.search(
            r"\bnot running the format command does not, on its own, "
            r"(?:make|set) `tests` \"fail\"",
            s,
        )
        and re.search(
            r"`notes` says that the format command was not run because the cd "
            r"prefix form does not cover it",
            s,
        )
        and not re.search(r"\bthe report sets `tests: \"fail\"`", s)
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
GOOD_BUILD = (
    "- When the approved string that the cd prefix form does not cover is the "
    "build command (`project_commands.build`), the build command is not run, "
    'the report sets `tests: "fail"`, and `notes` says that the build command '
    "was not run because the cd prefix form does not cover it.\n"
)
GOOD_FORMAT = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, the report's `tests` follows the result of the test command, not "
    'running the format command does not, on its own, make `tests` "fail", and '
    "`notes` says that the format command was not run because the cd prefix "
    "form does not cover it.\n"
)
EXISTING_TEST_COMMAND_SENTENCE = (
    "When the approved string that the cd prefix form does not cover is the "
    "test command (`project_commands.test`), the test command is not run at "
    'any point, the baseline run included, the report sets `tests: "fail"`, '
    "and `notes` says that the test command was not run because the cd prefix "
    "form does not cover it.\n"
)
EXISTING_DENY_SENTENCE = (
    "- If the hook denies a command: do NOT retry, rephrase, or restructure the\n"
    "  command to evade the match. Run nothing, set `tests: \"fail\"`, and explain\n"
    "  in `notes` (per-command AskUserQuestion is unavailable to you).\n"
)
FORGED_BUILD_WITHOUT_NOTES = (
    "- When the approved string that the cd prefix form does not cover is the "
    "build command (`project_commands.build`), the build command is not run "
    'and the report sets `tests: "fail"`.\n'
)
FORGED_BUILD_WITHOUT_FAIL = (
    "- When the approved string that the cd prefix form does not cover is the "
    "build command (`project_commands.build`), the build command is not run "
    "and `notes` says that the build command was not run because the cd prefix "
    "form does not cover it.\n"
)
FORGED_BUILD_WITHOUT_REASON = (
    "- When the approved string that the cd prefix form does not cover is the "
    "build command (`project_commands.build`), the build command is not run, "
    'the report sets `tests: "fail"`, and `notes` says that the build command '
    "was not run.\n"
)
FORGED_BUILD_RUN_ANYWAY = (
    "- When the approved string that the cd prefix form does not cover is the "
    "build command (`project_commands.build`), the build command is run "
    'later, the report sets `tests: "fail"`, and `notes` says that the build '
    "command was not run because the cd prefix form does not cover it.\n"
)
FORGED_FORMAT_SETS_FAIL = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    'run, the report sets `tests: "fail"`, and `notes` says that the format '
    "command was not run because the cd prefix form does not cover it.\n"
)
FORGED_FORMAT_FOLLOWS_WITHOUT_NEGATION = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, the report's `tests` follows the result of the test command, and "
    "`notes` says that the format command was not run because the cd prefix "
    "form does not cover it.\n"
)
FORGED_FORMAT_NEGATION_WITHOUT_FOLLOWS = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, not running the format command does not, on its own, make `tests` "
    '"fail", and `notes` says that the format command was not run because the '
    "cd prefix form does not cover it.\n"
)
FORGED_FORMAT_WITHOUT_NOTES = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, the report's `tests` follows the result of the test command, and not "
    'running the format command does not, on its own, make `tests` "fail".\n'
)
FORGED_FORMAT_WITH_NEGATION_AND_FAIL_SETTING = (
    "- When the approved string that the cd prefix form does not cover is the "
    "format command (`project_commands.format`), the format command is not "
    "run, the report's `tests` follows the result of the test command, not "
    'running the format command does not, on its own, make `tests` "fail", the '
    'report sets `tests: "fail"`, and `notes` says that the format command was '
    "not run because the cd prefix form does not cover it.\n"
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

    def test_ac4_a_renamed_step3_heading_raises_instead_of_passing_on_empty_text(self):
        renamed = "### Step 3: Check the worktree\n\nbody\n"
        with self.assertRaises(AssertionError):
            section_text(renamed, STEP_3_NAME, "implementer.md")

    def test_ac4_a_renamed_gate_heading_raises_instead_of_passing_on_empty_text(self):
        renamed = "## Command execution check (workflow.yaml strings)\n\nbody\n"
        with self.assertRaises(AssertionError):
            section_text(renamed, GATE_NAME, "SKILL.md")

    def test_ac4_matching_on_a_document_with_a_renamed_heading_never_reaches_a_match(self):
        renamed = "### Step 3: Check the worktree\n\n" + GOOD_BUILD + "\n" + GOOD_FORMAT
        with self.assertRaises(AssertionError):
            find_build_sentences(section_text(renamed, STEP_3_NAME, "implementer.md"))

    def test_every_section_is_found_and_nonempty(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                self.assertTrue(getter().strip())

    def test_neighbouring_sections_are_not_swallowed(self):
        self.assertNotIn("Step 4", step3_section())
        self.assertNotIn("Untrusted input", gate_section())


class TestMatchersAreNotVacuous(unittest.TestCase):
    """AC-5: each matcher is shown to accept the intended wording and to reject
    near misses, so a passing assertion on the real documents means something."""

    def test_build_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_build_sentences(GOOD_BUILD)), 1)

    def test_build_matcher_finds_nothing_in_the_existing_test_command_sentence(self):
        self.assertEqual(find_build_sentences(EXISTING_TEST_COMMAND_SENTENCE), [])

    def test_build_matcher_finds_nothing_in_the_existing_deny_sentence(self):
        self.assertEqual(find_build_sentences(EXISTING_DENY_SENTENCE), [])

    def test_build_matcher_rejects_a_sentence_without_notes(self):
        self.assertEqual(find_build_sentences(FORGED_BUILD_WITHOUT_NOTES), [])

    def test_build_matcher_rejects_a_sentence_without_the_fail_value(self):
        self.assertEqual(find_build_sentences(FORGED_BUILD_WITHOUT_FAIL), [])

    def test_build_matcher_rejects_a_notes_entry_without_the_cover_reason(self):
        self.assertEqual(find_build_sentences(FORGED_BUILD_WITHOUT_REASON), [])

    def test_build_matcher_rejects_a_sentence_that_runs_the_build_later(self):
        self.assertEqual(find_build_sentences(FORGED_BUILD_RUN_ANYWAY), [])

    def test_build_matcher_rejects_the_format_sentence(self):
        self.assertEqual(find_build_sentences(GOOD_FORMAT), [])

    def test_format_matcher_accepts_the_intended_sentence(self):
        self.assertEqual(len(find_format_sentences(GOOD_FORMAT)), 1)

    def test_format_matcher_finds_nothing_in_the_existing_test_command_sentence(self):
        self.assertEqual(find_format_sentences(EXISTING_TEST_COMMAND_SENTENCE), [])

    def test_format_matcher_finds_nothing_in_the_existing_deny_sentence(self):
        self.assertEqual(find_format_sentences(EXISTING_DENY_SENTENCE), [])

    def test_format_matcher_rejects_a_sentence_that_sets_fail_for_the_format_case(self):
        self.assertEqual(find_format_sentences(FORGED_FORMAT_SETS_FAIL), [])

    def test_format_matcher_rejects_a_sentence_without_notes(self):
        self.assertEqual(find_format_sentences(FORGED_FORMAT_WITHOUT_NOTES), [])

    def test_format_matcher_rejects_follows_without_the_negation(self):
        self.assertEqual(
            find_format_sentences(FORGED_FORMAT_FOLLOWS_WITHOUT_NEGATION), []
        )

    def test_format_matcher_rejects_the_negation_without_follows(self):
        self.assertEqual(
            find_format_sentences(FORGED_FORMAT_NEGATION_WITHOUT_FOLLOWS), []
        )

    def test_format_matcher_rejects_a_negation_that_also_sets_fail(self):
        self.assertEqual(
            find_format_sentences(FORGED_FORMAT_WITH_NEGATION_AND_FAIL_SETTING), []
        )

    def test_format_matcher_rejects_the_build_sentence(self):
        self.assertEqual(find_format_sentences(GOOD_BUILD), [])

    def test_sentence_splitting_keeps_the_intended_sentences_whole(self):
        for label, text in (("build", GOOD_BUILD), ("format", GOOD_FORMAT)):
            with self.subTest(sentence=label):
                self.assertEqual(len(sentences(text)), 1)


class TestAC1BuildStatement(unittest.TestCase):
    """AC-1 (FR1, FR3, TM-1): a build command that the cd prefix form does not
    cover is not run, the report sets `tests: "fail"`, and `notes` says why."""

    def test_ac1_each_section_holds_exactly_one_build_sentence(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                hits = find_build_sentences(getter())
                self.assertEqual(len(hits), 1, sentences(getter()))

    def test_ac1_the_build_sentence_is_not_the_test_command_sentence(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                hits = find_build_sentences(getter())
                self.assertEqual(len(hits), 1, sentences(getter()))
                self.assertNotIn("`project_commands.test`", hits[0])


class TestAC2FormatStatement(unittest.TestCase):
    """AC-2 (FR2, FR3, TM-1): a format command that the cd prefix form does not
    cover is not run, `tests` follows the test command's result, and `notes`
    says why."""

    def test_ac2_each_section_holds_exactly_one_format_sentence(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                hits = find_format_sentences(getter())
                self.assertEqual(len(hits), 1, sentences(getter()))

    def test_ac2_no_sentence_sets_fail_for_the_format_case(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                offenders = [
                    s
                    for s in sentences_with(getter(), "`project_commands.format`")
                    if re.search(r"\bthe report sets `tests: \"fail\"`", s)
                ]
                self.assertEqual(offenders, [])

    def test_ac2_the_format_sentence_is_not_the_build_sentence(self):
        for label, getter in SECTIONS:
            with self.subTest(section=label):
                format_hits = find_format_sentences(getter())
                build_hits = find_build_sentences(getter())
                self.assertEqual(len(format_hits), 1, sentences(getter()))
                self.assertEqual(len(build_hits), 1, sentences(getter()))
                self.assertNotEqual(format_hits[0], build_hits[0])


class TestAC6Mechanics(unittest.TestCase):
    """AC-6 (NFR5): this module imports the standard library only. The
    neighbouring modules run unedited in the same suite."""

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
