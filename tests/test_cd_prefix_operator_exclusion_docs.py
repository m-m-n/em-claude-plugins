"""Document tests for cd-prefix-toplevel-operators task0002.

The hook (`em-workflow/hooks/bash_guard.py`) stops allowing the implementer's
cd prefix form `cd "{worktree_path}" && <approved string>` when the approved
string could run partly outside the worktree: a lone `&`, `;`, `||` or a
line break at its top level, or a construct the hook does not parse
(feature-docs/cd-prefix-toplevel-operators/IMPLEMENTATION.md, C1 and C4).
This module checks that the documents state that exclusion.

Covers task0002's Acceptance Criteria
(feature-docs/cd-prefix-toplevel-operators/tasks/task0002.md):

- AC-1 (FR6): `references/command-execution-protocol.md`, section
  "Verbatim execution rule": the four top-level operators, the six
  recognized tokens and the single-quote / double-quote escape rules.
- AC-2 (FR6): the same section: the safe-side constructs E5-E10 with their
  positions, and that nesting is not parsed.
- AC-3 (FR6): the same section: the implementer does not run an approved
  string the conditions exclude, and reports it in `notes`.
- AC-4 (FR8): `README.md`, the numbered item for the runtime enforcement, and
  `references/workflow-schema.md`, section "Command approval store": the
  exclusion summary and the citation of the protocol.
- AC-5 (FR8, FR10): neither summary restates the safe-side constructs; every
  absence assertion is paired with a forged-text case its matcher flags.
- AC-6 (NFR6): the four existing document-test modules are not edited here;
  they keep passing under `python3 -m unittest discover -s tests`.
- AC-7 (FR10, NFR7): text is located by heading (the README by its numbered
  item), whitespace is normalized, a missing heading fails loudly, and this
  module imports the standard library only.

Method: slice by heading, whitespace-normalize, assert presence or absence
of stable phrases. Never a line number. Operator tokens are matched in the
backtick form the documents use, so a stray `&` in other prose does not
satisfy an assertion. Standard library only.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PROTOCOL_PATH = PLUGIN_ROOT / "references" / "command-execution-protocol.md"
README_PATH = PLUGIN_ROOT / "README.md"
SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"

PROTOCOL_CITATION = "references/command-execution-protocol.md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


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


def _numbered_item(text, marker):
    """The numbered-list item (`1. ...`) whose first line contains `marker`.

    The item runs to the next numbered item or the next blank line.
    """
    lines = text.splitlines()
    item_re = re.compile(r"^\d+\.\s")
    for index, line in enumerate(lines):
        if item_re.match(line) and marker in line:
            collected = [line]
            for follower in lines[index + 1:]:
                if not follower.strip() or item_re.match(follower):
                    break
                collected.append(follower)
            return "\n".join(collected)
    return None


# Matchers for the safe-side constructs (rules E5-E10 of the shared design).
# The protocol states them; the README item and the schema section must not
# restate them (FR8, FR10). Each is a predicate over normalized text; the
# backtick-quoted forms are matched as the documents write them.
SAFE_SIDE_MATCHERS = {
    "dollar-single-quote": lambda text: "$'" in text,
    "dollar-double-quote": lambda text: '$"' in text,
    "dollar-brace": lambda text: "${" in text,
    "dollar-paren": lambda text: "$(" in text,
    "hash-condition": lambda text: "`#`" in text,
    "unclosed-quote": lambda text: "unclosed quote" in text.lower(),
    "trailing-backslash": lambda text: "trailing backslash" in text.lower(),
}

FORGED_SAFE_SIDE_TEXT = {
    "dollar-single-quote": "A string holding $'x' is excluded.",
    "dollar-double-quote": 'A string holding $"x" is excluded.',
    "dollar-brace": "A string holding ${HOME} is excluded.",
    "dollar-paren": "A string holding $(date) is excluded.",
    "hash-condition": "A string holding `#` is excluded.",
    "unclosed-quote": "A string with an unclosed quote is excluded.",
    "trailing-backslash": "A string with a trailing backslash is excluded.",
}


def _restated_constructs(text):
    """Names of the safe-side constructs that `text` restates."""
    normalized = _normalize(text)
    return sorted(
        name for name, matcher in SAFE_SIDE_MATCHERS.items()
        if matcher(normalized)
    )


class TestVerbatimSectionOperators(unittest.TestCase):
    """AC-1: the top-level operators, recognized tokens and escape rules."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), "Verbatim execution rule")
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Verbatim execution rule' not found"
        )

    def test_ac1_names_the_four_top_level_operators(self):
        self.assertRegex(
            self.text,
            r"lone `&`, no `;`, no `\|\|` and no line break at its top level",
        )

    def test_ac1_names_the_six_recognized_tokens(self):
        self.assertRegex(
            self.text,
            r"recognized token[^.]*`&&`[^.]*`\|&`[^.]*`>&`[^.]*`<&`"
            r"[^.]*`&>`[^.]*`&>>`",
        )

    def test_ac1_states_that_the_ampersand_of_a_token_is_not_counted(self):
        self.assertRegex(
            self.text,
            r"`&` that is not part of a recognized token",
        )

    def test_ac1_states_the_longest_token_rule(self):
        self.assertIn("longest token is taken first", self.text)
        self.assertIn("`&&&`", self.text)

    def test_ac1_states_that_a_plain_pipe_is_not_counted(self):
        self.assertRegex(self.text, r"pipe, which is not counted")

    def test_ac1_states_the_unquoted_escape_rule(self):
        self.assertRegex(
            self.text,
            r"unquoted[^;]*`'` opens a single-quoted span"
            r"[^;]*`\"` opens a double-quoted span"
            r"[^;]*backslash escapes the next character",
        )

    def test_ac1_states_the_single_quote_escape_rule(self):
        self.assertRegex(
            self.text,
            r"single-quoted[^;]*every character is ordinary, "
            r"a backslash included[^;]*only `'` ends the span",
        )

    def test_ac1_states_the_double_quote_escape_rule(self):
        self.assertRegex(
            self.text,
            r"double-quoted[^;]*backslash followed by `\$`, a backtick, "
            r"`\"`, a backslash or a line break escapes that character"
            r"[^;]*any other backslash is an ordinary character"
            r"[^;]*unescaped `\"` ends the span",
        )

    def test_ac1_states_where_each_operator_counts(self):
        self.assertRegex(
            self.text,
            r"lone `&`, a `;` and a `\|\|` count only when unquoted and "
            r"unescaped; a line break \(LF or CR\) counts anywhere, "
            r"inside quotes included",
        )

    def test_ac1_keeps_the_cd_prefix_form_and_its_existing_conditions(self):
        # The exclusion narrows the form; the form itself stays as written.
        self.assertIn('cd "{worktree_path}" && <approved string>', self.text)
        self.assertIn("single Bash call", self.text)
        self.assertIn("double-quoted absolute path", self.text)
        self.assertIn("realpath", self.text)


class TestVerbatimSectionSafeSide(unittest.TestCase):
    """AC-2: the safe-side constructs E5-E10, each with its position."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), "Verbatim execution rule")
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Verbatim execution rule' not found"
        )

    def test_ac2_unclosed_quote_at_the_end_of_the_scan(self):
        self.assertRegex(
            self.text,
            r"unclosed quote[^;.]*scan ends inside a single-quoted or "
            r"double-quoted span",
        )

    def test_ac2_trailing_backslash_at_the_end_of_the_scan(self):
        self.assertRegex(
            self.text,
            r"trailing backslash[^;.]*scan ends on a backslash that has no "
            r"following character[^;.]*outside single quotes",
        )

    def test_ac2_dollar_single_and_double_quote_anywhere(self):
        self.assertRegex(
            self.text,
            r"`\$'` or `\$\"`[^;.]*anywhere",
        )

    def test_ac2_hash_anywhere_inside_quotes_included(self):
        self.assertRegex(
            self.text,
            r"`#`[^;.]*anywhere[^;.]*inside quotes included",
        )

    def test_ac2_parentheses_and_braces_when_unquoted_and_unescaped(self):
        self.assertRegex(
            self.text,
            r"`\(`, `\)`, `\{` or `\}`[^;.]*unquoted and unescaped",
        )

    def test_ac2_command_and_parameter_substitution_and_backtick_anywhere(self):
        self.assertRegex(
            self.text,
            r"`\$\(`, `\$\{` or a backtick[^;.]*anywhere"
            r"[^;.]*unquoted[^;.]*inside double quotes"
            r"[^;.]*inside single quotes too",
        )

    def test_ac2_states_that_nesting_is_not_parsed(self):
        self.assertIn("Nesting is not parsed", self.text)
        self.assertRegex(
            self.text,
            r"Nesting is not parsed[^.]*one occurrence[^.]*enough",
        )

    def test_ac2_states_that_the_hook_does_not_parse_these_constructs(self):
        self.assertRegex(
            self.text,
            r"constructs[^:]*hook does not parse[^:]*excludes",
        )


class TestVerbatimSectionImplementerHandling(unittest.TestCase):
    """AC-3: the implementer does not run an excluded approved string."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), "Verbatim execution rule")
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Verbatim execution rule' not found"
        )

    def test_ac3_implementer_does_not_run_an_excluded_approved_string(self):
        self.assertRegex(
            self.text,
            r"implementer does not run an approved string[^.]*exclude"
            r"[^.]*in any form",
        )

    def test_ac3_implementer_reports_it_in_notes(self):
        self.assertRegex(
            self.text,
            r"implementer does not run an approved string[^.]*"
            r"reports it in `notes`",
        )

    def test_ac3_handling_sits_in_the_implementer_bullet(self):
        # The sentence belongs to the Implementer bullet, which comes after
        # the Orchestrator bullet and before the "Every role" bullet.
        orchestrator = self.text.index("**Orchestrator")
        implementer = self.text.index("**Implementer")
        handling = self.text.index("implementer does not run an approved string")
        every_role = self.text.index("**Every role**")
        self.assertLess(orchestrator, implementer)
        self.assertLess(implementer, handling)
        self.assertLess(handling, every_role)


class TestReadmeExclusionSummary(unittest.TestCase):
    """AC-4 (README): the 実行時強制 item names the exclusion."""

    @classmethod
    def setUpClass(cls):
        raw = _numbered_item(_read(README_PATH), "実行時強制")
        cls.raw = raw
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "numbered item containing '実行時強制' not found"
        )

    def test_ac4_names_the_operators_with_toplevel_and_exclusion(self):
        self.assertRegex(
            self.text,
            r"トップレベル[^。]*`&`[^。]*`;`[^。]*`\|\|`[^。]*対象外",
        )

    def test_ac4_names_the_line_break(self):
        self.assertRegex(self.text, r"トップレベル[^。]*改行[^。]*対象外")

    def test_ac4_still_cites_the_protocol(self):
        self.assertIn(PROTOCOL_CITATION, self.text)

    def test_ac4_stays_one_numbered_item_without_a_blank_line(self):
        self.assertNotIn("\n\n", self.raw)
        self.assertEqual(len(self.raw.splitlines()), 1)

    def test_ac4_keeps_the_existing_decisions(self):
        self.assertIn("承認済み文字列と完全一致 → allow", self.text)
        self.assertIn("workflow.yaml 記載かつ未承認 → deny", self.text)
        self.assertIn("禁止パターン", self.text)
        self.assertIn("承認済みでも deny", self.text)


class TestSchemaExclusionSummary(unittest.TestCase):
    """AC-4 (schema): Command approval store names the exclusion."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(SCHEMA_PATH), "Command approval store")
        cls.raw = raw
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Command approval store' not found"
        )

    def test_ac4_names_the_operators_with_top_level_and_not_covered(self):
        self.assertRegex(
            self.text,
            r"lone `&`, `;`, `\|\|` or line break at its top level"
            r"[^.]*not covered",
        )

    def test_ac4_still_carries_the_details_line(self):
        self.assertIn("Details: `" + PROTOCOL_CITATION + "`", self.text)

    def test_ac4_adds_no_bullet_to_the_section_before_schema_consequences(self):
        # The bullet extraction of tests/test_failed_items_category.py ends
        # at this section's heading; the exclusion is prose, not a bullet.
        head = self.raw.split("Schema consequences:")[0]
        bullets = [
            line for line in head.splitlines()
            if line.lstrip().startswith(("- ", "* "))
        ]
        self.assertEqual(bullets, [])


class TestSummariesDoNotRestateSafeSideConstructs(unittest.TestCase):
    """AC-5: the summaries leave rules E5-E10 to the protocol."""

    @classmethod
    def setUpClass(cls):
        readme = _numbered_item(_read(README_PATH), "実行時強制")
        schema = _section(_read(SCHEMA_PATH), "Command approval store")
        cls.readme = readme
        cls.schema = schema

    def test_readme_item_and_schema_section_are_found(self):
        self.assertIsNotNone(self.readme, "README item not found")
        self.assertIsNotNone(self.schema, "schema section not found")

    def _assert_absent(self, name):
        matcher = SAFE_SIDE_MATCHERS[name]
        for label, text in (("README item", self.readme),
                            ("schema section", self.schema)):
            self.assertIsNotNone(text, label + " not found")
            self.assertFalse(
                matcher(_normalize(text)),
                "%s restates the construct %r" % (label, name),
            )

    def _assert_matcher_fires(self, name):
        forged = FORGED_SAFE_SIDE_TEXT[name]
        self.assertEqual(_restated_constructs(forged).count(name), 1, forged)

    def test_ac5_no_dollar_single_quote(self):
        self._assert_absent("dollar-single-quote")

    def test_ac5_dollar_single_quote_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("dollar-single-quote")

    def test_ac5_no_dollar_double_quote(self):
        self._assert_absent("dollar-double-quote")

    def test_ac5_dollar_double_quote_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("dollar-double-quote")

    def test_ac5_no_dollar_brace(self):
        self._assert_absent("dollar-brace")

    def test_ac5_dollar_brace_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("dollar-brace")

    def test_ac5_no_dollar_paren(self):
        self._assert_absent("dollar-paren")

    def test_ac5_dollar_paren_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("dollar-paren")

    def test_ac5_no_hash_condition(self):
        self._assert_absent("hash-condition")

    def test_ac5_hash_condition_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("hash-condition")

    def test_ac5_no_unclosed_quote(self):
        self._assert_absent("unclosed-quote")

    def test_ac5_unclosed_quote_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("unclosed-quote")

    def test_ac5_no_trailing_backslash(self):
        self._assert_absent("trailing-backslash")

    def test_ac5_trailing_backslash_matcher_fires_on_forged_text(self):
        self._assert_matcher_fires("trailing-backslash")

    def test_ac5_matchers_leave_a_clean_summary_alone(self):
        clean = (
            "An approved string with a lone `&`, `;`, `||` or line break at "
            "its top level is not covered. トップレベルに `&` がある場合は対象外。"
        )
        self.assertEqual(_restated_constructs(clean), [])

    def test_ac5_every_matcher_has_a_forged_case(self):
        self.assertEqual(set(SAFE_SIDE_MATCHERS), set(FORGED_SAFE_SIDE_TEXT))


class TestLocatingText(unittest.TestCase):
    """AC-7: text is located by heading; a missing heading fails loudly."""

    def test_section_of_a_renamed_heading_is_none_not_empty(self):
        text = "# Title\n\n## Renamed heading\n\nbody\n"
        self.assertIsNone(_section(text, "Verbatim execution rule"))
        self.assertEqual(
            _normalize(_section(text, "Renamed heading")), "body"
        )

    def test_section_skips_headings_inside_fenced_code(self):
        text = "## Target\n\n```\n## not a heading\n```\n\ntail\n\n## Next\n"
        body = _section(text, "Target")
        self.assertIn("not a heading", body)
        self.assertIn("tail", body)
        self.assertNotIn("Next", body)

    def test_numbered_item_is_none_when_the_marker_is_absent(self):
        self.assertIsNone(_numbered_item("1. one\n2. two\n", "実行時強制"))

    def test_numbered_item_runs_to_the_next_item(self):
        item = _numbered_item("1. a\n   cont\n2. 実行時強制 b\n3. c\n", "実行時強制")
        self.assertEqual(_normalize(item), "2. 実行時強制 b")

    def test_normalize_collapses_line_wraps(self):
        self.assertEqual(_normalize("a\n   b\t\tc  "), "a b c")


class TestStandardLibraryOnly(unittest.TestCase):
    """AC-7: this module imports the standard library only."""

    def test_ac7_imports_are_standard_library(self):
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
