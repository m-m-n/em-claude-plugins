"""Document tests for approval-unicode-whitespace task0003.

The approval trim rule (feature-docs/approval-unicode-whitespace/
IMPLEMENTATION.md, C1) removes only spaces (U+0020) and tabs (U+0009) from
both ends of a command string, and refuses approval, on every path, for a
value that still has another whitespace character at either end.
`references/command-execution-protocol.md` states that rule wherever it
describes trimming. This module checks those statements.

Covers task0003's Acceptance Criteria
(feature-docs/approval-unicode-whitespace/tasks/task0003.md):

- AC-1 (FR9): section "Approval gate", step 1: only spaces and tabs are
  removed from both ends, a value empty after that is skipped, and a value
  with any other whitespace at either end is never approved.
- AC-2 (FR9): section "Verbatim execution rule": the space/tab-only trim for
  the exact-string comparison and for the cd prefix remainder, and that other
  surrounding whitespace is never allowed. The phrases "Trim surrounding
  whitespace; skip empty", "(after trimming)" and "(surrounding whitespace
  aside)" no longer appear in the document.
- AC-3 (FR9, NFR3): text is located by heading (the numbered step by its
  number inside its section), whitespace is normalized, a missing heading
  fails loudly, every absence assertion is paired with a presence assertion
  and a forged-text case its matcher flags, and this module imports the
  standard library only.

Method: slice by heading, whitespace-normalize, assert presence or absence of
stable phrases. Never a line number. Standard library only.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "command-execution-protocol.md"
)

GATE_HEADING = "Approval gate"
VERBATIM_HEADING = "Verbatim execution rule"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
NUMBERED_RE = re.compile(r"^(\d+)\.\s")

# The three statements this task replaces. The document must not carry any of
# them any more; each is matched on whitespace-normalized text.
OLD_PHRASES = {
    "gate step 1": "Trim surrounding whitespace; skip empty",
    "exact comparison": "(after trimming)",
    "cd prefix remainder": "(surrounding whitespace aside)",
}


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _normalize(text):
    """Collapse every whitespace run (line wraps included) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _section(text, heading):
    """Body of the section whose heading text starts with `heading`.

    The section runs from the heading line to the next heading of the same
    or a higher level (fenced code is not scanned for headings). Returns
    None when no such heading exists, so a renamed heading fails loudly
    instead of letting an absence assertion pass on empty text.
    """
    lines = text.splitlines()
    start = None
    level = None
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if match.group(2).startswith(heading):
                start = index
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return "\n".join(lines[start + 1:index])
    if start is None:
        return None
    return "\n".join(lines[start + 1:])


def _numbered_step(section_text, number):
    """The top-level numbered step `number` of a section body.

    The step runs from its `<number>. ` line to the next top-level numbered
    line or the end of the section; indented continuation lines and a
    following paragraph before the next step are part of it. Fenced code is
    not scanned. Returns None when the step does not exist.
    """
    collected = None
    in_fence = False
    for line in section_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if collected is not None:
                collected.append(line)
            continue
        match = None if in_fence else NUMBERED_RE.match(line)
        if match:
            if collected is not None:
                break
            if int(match.group(1)) == number:
                collected = [line]
            continue
        if collected is not None:
            collected.append(line)
    if collected is None:
        return None
    return "\n".join(collected)


def _old_phrases_in(text):
    """Names of the replaced statements that `text` still carries."""
    normalized = _normalize(text)
    return sorted(
        name for name, phrase in OLD_PHRASES.items() if phrase in normalized
    )


class TestApprovalGateStepOne(unittest.TestCase):
    """AC-1: step 1 of the approval gate states the space/tab-only trim."""

    @classmethod
    def setUpClass(cls):
        section = _section(_read(PROTOCOL_PATH), GATE_HEADING)
        step = _numbered_step(section, 1) if section is not None else None
        cls.section = section
        cls.text = _normalize(step) if step is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.section, "section %r not found" % GATE_HEADING
        )
        self.assertIsNotNone(self.text, "step 1 of the approval gate not found")

    def test_ac1_step_one_is_the_command_resolution_step(self):
        self.assertIn("Resolve every command string", self.text)
        self.assertIn("`project.components`", self.text)

    def test_ac1_removes_only_spaces_and_tabs_from_both_ends(self):
        self.assertRegex(
            self.text,
            r"only spaces and tabs[^.]*from both ends",
        )

    def test_ac1_skips_a_value_that_is_empty_after_that(self):
        self.assertRegex(
            self.text,
            r"empty after that[^.]*skip|skip[^.]*empty after that",
        )

    def test_ac1_never_approves_other_whitespace_at_either_end(self):
        self.assertRegex(
            self.text,
            r"any other whitespace character at either end[^.]*"
            r"never approved",
        )

    def test_ac1_names_the_paths_that_refuse_it(self):
        self.assertRegex(
            self.text,
            r"`bash_guard\.py`[^.]*`merge-preflight\.py`[^.]*refuse",
        )
        self.assertRegex(
            self.text,
            r"`--record` refuses an input that carries it",
        )

    def test_ac1_step_one_does_not_state_the_per_path_table(self):
        # The document states C1 in prose; it does not restate the table.
        self.assertNotIn("non-matchable", self.text)
        self.assertNotIn("`commands_unapproved`", self.text)

    def test_ac1_step_two_is_still_the_diff_against_the_list(self):
        step_two = _numbered_step(self.section, 2)
        self.assertIsNotNone(step_two, "step 2 of the approval gate not found")
        self.assertIn("Diff against `bash_guard.py --list`", _normalize(step_two))


class TestVerbatimExecutionRuleTrim(unittest.TestCase):
    """AC-2: the Verbatim execution rule states the space/tab-only trim."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), VERBATIM_HEADING)
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section %r not found" % VERBATIM_HEADING
        )

    def test_ac2_exact_comparison_after_removing_spaces_and_tabs_only(self):
        self.assertRegex(
            self.text,
            r"compares exact strings[^.;]*surrounding spaces and tabs only",
        )

    def test_ac2_other_surrounding_whitespace_is_never_allowed(self):
        self.assertRegex(
            self.text,
            r"any other surrounding whitespace is never allowed",
        )

    def test_ac2_the_statement_opens_the_section(self):
        # It is the first sentence of the section, before the instruction to
        # run approved commands byte-for-byte.
        statement = self.text.index("compares exact strings")
        byte_for_byte = self.text.index("byte-for-byte as recorded")
        self.assertLess(statement, byte_for_byte)
        self.assertLess(statement, self.text.index("**Orchestrator"))

    def test_ac2_cd_prefix_remainder_trim_is_spaces_and_tabs_aside(self):
        self.assertRegex(
            self.text,
            r"everything after the first `&&` matches an approved string "
            r"exactly \(surrounding spaces and tabs aside\)",
        )

    def test_ac2_other_whitespace_at_either_end_excludes_the_cd_prefix(self):
        self.assertRegex(
            self.text,
            r"any other whitespace at either end of the remainder excludes "
            r"the cd prefix allow",
        )

    def test_ac2_the_cd_prefix_statement_sits_in_the_implementer_bullet(self):
        implementer = self.text.index("**Implementer")
        remainder = self.text.index("surrounding spaces and tabs aside")
        every_role = self.text.index("**Every role**")
        self.assertLess(implementer, remainder)
        self.assertLess(remainder, every_role)

    def test_ac2_the_cd_prefix_statement_follows_the_path_conditions(self):
        # The remainder condition stays between the "only spaces or tabs sit
        # between the closing quote and the first `&&`" condition and the
        # "no lone `&`" condition.
        before = self.text.index("only spaces or tabs sit between")
        remainder = self.text.index("surrounding spaces and tabs aside")
        after = self.text.index("no lone `&`")
        self.assertLess(before, remainder)
        self.assertLess(remainder, after)


class TestReplacedPhrasesAreGone(unittest.TestCase):
    """AC-2: the three old statements no longer appear in the document.

    Each absence assertion is paired with a presence assertion on the same
    text, so a missing section fails loudly instead of passing vacuously.
    """

    @classmethod
    def setUpClass(cls):
        cls.document = _read(PROTOCOL_PATH)
        cls.gate = _section(cls.document, GATE_HEADING)
        cls.verbatim = _section(cls.document, VERBATIM_HEADING)

    def test_both_sections_are_found(self):
        self.assertIsNotNone(self.gate, "section %r not found" % GATE_HEADING)
        self.assertIsNotNone(
            self.verbatim, "section %r not found" % VERBATIM_HEADING
        )
        self.assertIn("Resolve every command string", _normalize(self.gate))
        self.assertIn("compares exact strings", _normalize(self.verbatim))

    def test_ac2_the_gate_step_phrase_is_gone(self):
        self.assertIn("Resolve every command string", _normalize(self.gate))
        self.assertNotIn(
            OLD_PHRASES["gate step 1"], _normalize(self.document)
        )

    def test_ac2_the_after_trimming_phrase_is_gone(self):
        self.assertIn("compares exact strings", _normalize(self.verbatim))
        self.assertNotIn(
            OLD_PHRASES["exact comparison"], _normalize(self.document)
        )

    def test_ac2_the_surrounding_whitespace_aside_phrase_is_gone(self):
        self.assertIn("matches an approved string", _normalize(self.verbatim))
        self.assertNotIn(
            OLD_PHRASES["cd prefix remainder"], _normalize(self.document)
        )

    def test_ac2_no_replaced_statement_remains_anywhere(self):
        self.assertEqual(_old_phrases_in(self.document), [])

    def test_ac2_the_matcher_flags_each_old_statement(self):
        forged = {
            "gate step 1": (
                "1. Resolve it (build / test).\n   Trim surrounding\n"
                "   whitespace; skip empty.\n"
            ),
            "exact comparison": "The hook compares exact strings (after\ntrimming).",
            "cd prefix remainder": (
                "matches an approved string exactly\n(surrounding whitespace "
                "aside);"
            ),
        }
        self.assertEqual(set(forged), set(OLD_PHRASES))
        for name, text in forged.items():
            self.assertEqual(_old_phrases_in(text), [name], name)

    def test_ac2_the_matcher_leaves_the_new_wording_alone(self):
        new_wording = (
            "Remove only spaces and tabs from both ends. The hook compares "
            "exact strings after removing surrounding spaces and tabs only. "
            "(surrounding spaces and tabs aside)"
        )
        self.assertEqual(_old_phrases_in(new_wording), [])


class TestLocatingText(unittest.TestCase):
    """AC-3: text is located by heading; a missing heading fails loudly."""

    def test_section_of_a_renamed_heading_is_none_not_empty(self):
        text = "# Title\n\n## Renamed heading\n\nbody\n"
        self.assertIsNone(_section(text, GATE_HEADING))
        self.assertIsNone(_section(text, VERBATIM_HEADING))
        self.assertEqual(
            _normalize(_section(text, "Renamed heading")), "body"
        )

    def test_section_matches_a_heading_that_starts_with_the_name(self):
        text = "## Approval gate (orchestrator / create-spec)\n\nbody\n\n## Next\n"
        self.assertEqual(_normalize(_section(text, GATE_HEADING)), "body")

    def test_section_skips_headings_inside_fenced_code(self):
        text = "## Target\n\n```\n## not a heading\n```\n\ntail\n\n## Next\n"
        body = _section(text, "Target")
        self.assertIn("not a heading", body)
        self.assertIn("tail", body)
        self.assertNotIn("Next", body)

    def test_numbered_step_runs_to_the_next_step(self):
        section = "1. one\n   cont\n2. two\n3. three\n"
        self.assertEqual(_normalize(_numbered_step(section, 1)), "1. one cont")
        self.assertEqual(_normalize(_numbered_step(section, 2)), "2. two")

    def test_numbered_step_is_none_when_the_number_is_absent(self):
        self.assertIsNone(_numbered_step("1. one\n2. two\n", 3))

    def test_numbered_step_ignores_numbers_inside_fenced_code(self):
        section = "1. one\n```\n2. not a step\n```\n2. two\n"
        step = _normalize(_numbered_step(section, 1))
        self.assertIn("not a step", step)
        self.assertNotIn("2. two", step)

    def test_normalize_collapses_line_wraps(self):
        self.assertEqual(_normalize("a\n   b\t\tc  "), "a b c")

    def test_gate_step_one_is_found_in_the_document(self):
        section = _section(_read(PROTOCOL_PATH), GATE_HEADING)
        self.assertIsNotNone(section, "section %r not found" % GATE_HEADING)
        self.assertIsNotNone(_numbered_step(section, 1))


class TestStandardLibraryOnly(unittest.TestCase):
    """AC-3: this module imports the standard library only."""

    def test_ac3_imports_are_standard_library(self):
        tree = ast.parse(_read(__file__))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertFalse(
            imported - set(sys.stdlib_module_names),
            sorted(imported - set(sys.stdlib_module_names)),
        )


if __name__ == "__main__":
    unittest.main()
