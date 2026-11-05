"""Tests for task0005 (subagent-report-write-block): the Write rejection rule
in `em-workflow/agents/implementer.md` and in
`em-workflow/skills/worktree-task-workflow/SKILL.md`
(feature-docs/subagent-report-write-block/tasks/task0005.md).

This is a document-contract test: it reads the two documents as text and
asserts that the new `## Write rejection` sections and the Step 7 report carry
the contract an implementer subagent is instructed by. It never executes the
agent.

Covers task0005 Acceptance Criteria:

- AC-1 (TS-12): `TestAc1ImmediateFailure` -- implementer.md states the trigger
  (the rejection text), the immediate `status: failed`, and that `merge_script`
  is not run.
- AC-2 (TS-12, TM-8): `TestAc2ReportField` -- the Step 7 report block has the
  top-level `write_rejection` key, and the text after the block describes it
  as null or a mapping of a repository-relative `path` and `rejection_text`.
- AC-3 (TS-12, TM-9, NFR1): `TestAc3BannedRoutes` -- each banned route is
  named in its own list item: renaming, another name, Edit creating the file,
  Bash, and the parent writing it.
- AC-4 (TS-12): `TestAc4BaseCommitScope` -- the rule covers a file at the base
  commit, and such a file is updated with Edit from the start.
- AC-5 (TS-12): `TestAc5WorktreeTaskWorkflow` -- worktree-task-workflow states
  the immediate failure, the report of target path and rejection text, and the
  ban on workarounds, and cites implementer.md.
- AC-6: `TestAc6ExpectedReportKeys` -- `EXPECTED_REPORT_KEYS` of
  tests/test_implementer_untrusted_data_rule.py holds `write_rejection`. That
  the module passes is checked by running it, not asserted here.

Negative check: `TestNoRegexInDocuments` -- neither document carries the
file-name regex (the rule text owns it; other documents cite it).

Section extraction is fence-aware and locates a heading by a distinctive
substring; the section runs up to the next heading of the same or a shallower
level. A missing heading raises AssertionError, so a negative check never
passes vacuously over an empty string. Phrase checks are whitespace-normalized.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"
SKILL_PATH = (
    REPO_ROOT / "em-workflow" / "skills" / "worktree-task-workflow" / "SKILL.md"
)
UNTRUSTED_TEST_PATH = REPO_ROOT / "tests" / "test_implementer_untrusted_data_rule.py"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

RULE_HEADING = "## Write rejection"
HARD_CONSTRAINTS_HEADING = "## Hard constraints"
STEP_7_HEADING = "Step 7: Report"

REJECTION_TEXT = "Subagents should return findings as text, not write report files."
NAME_RULE_PATH = "em-workflow/skills/plan-writing/SKILL.md"
NAME_RULE_HEADING = "## Report Artifact Names"

# The four stems of the file-name rule. A document that carries the regex has
# two of them side by side as a regex alternation, with or without the table
# escape in front of the bar.
_STEMS = ("REPORT", "SUMMARY", "FINDINGS", "ANALYSIS")


def _read(path):
    return path.read_text(encoding="utf-8")


def _heading_lines(text):
    """Yields (index, level, line) for each Markdown heading line outside a
    fenced code block."""
    in_fence = False
    for index, line in enumerate(text.splitlines()):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            yield index, len(match.group(1)), line


def _extract_section(text, heading_substring, source="document"):
    """Returns (level, section_text): the section whose heading line contains
    `heading_substring`, from that heading up to (excluding) the next heading
    of the same or a shallower level. Raises AssertionError when no heading
    matches."""
    lines = text.splitlines()
    headings = list(_heading_lines(text))
    for position, (index, level, line) in enumerate(headings):
        if heading_substring in line:
            end_index = len(lines)
            for next_index, next_level, _ in headings[position + 1:]:
                if next_level <= level:
                    end_index = next_index
                    break
            return level, "\n".join(lines[index:end_index])
    raise AssertionError(
        f"no heading line containing {heading_substring!r} found in {source}"
    )


def _heading_index(text, heading_substring):
    for index, _, line in _heading_lines(text):
        if heading_substring in line:
            return index
    raise AssertionError(f"no heading line containing {heading_substring!r}")


def _normalize_ws(text):
    """Collapse Markdown line-wrap whitespace to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _blocks(section):
    """Splits a section into list items and paragraphs. A list item starts at
    a line beginning with `- ` or `N. ` and runs through its continuation
    lines; a paragraph is a blank-line-separated block. Returns normalized
    strings."""
    blocks = []
    current = []
    for line in section.splitlines():
        if not line.strip():
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        if re.match(r"^\s*(?:-|\d+\.)\s+", line) and current:
            blocks.append(" ".join(current))
            current = []
        current.append(line.strip())
    if current:
        blocks.append(" ".join(current))
    return [_normalize_ws(block) for block in blocks]


def _list_items(section):
    return [b for b in _blocks(section) if re.match(r"^(?:-|\d+\.)\s+", b)]


def carries_name_regex(text):
    """True when `text` carries the file-name regex: two neighbouring stems of
    the rule as a bar-separated alternation (optionally with a backslash before
    the bar), or the group opener with the first stem."""
    for left, right in zip(_STEMS, _STEMS[1:]):
        if re.search(left + r"\\?\|" + right, text, re.IGNORECASE):
            return True
    return False


class Document:
    """Loads each document once and extracts each section once."""

    _cache = {}

    @classmethod
    def _get(cls, key, builder):
        if key not in cls._cache:
            cls._cache[key] = builder()
        return cls._cache[key]

    @classmethod
    def implementer(cls):
        return cls._get("implementer", lambda: _read(IMPLEMENTER_PATH))

    @classmethod
    def skill(cls):
        return cls._get("skill", lambda: _read(SKILL_PATH))

    @classmethod
    def implementer_rule(cls):
        return cls._get(
            "implementer_rule",
            lambda: _extract_section(
                cls.implementer(), RULE_HEADING, str(IMPLEMENTER_PATH)
            ),
        )

    @classmethod
    def skill_rule(cls):
        return cls._get(
            "skill_rule",
            lambda: _extract_section(cls.skill(), RULE_HEADING, str(SKILL_PATH)),
        )

    @classmethod
    def step_7(cls):
        return cls._get(
            "step_7",
            lambda: _extract_section(
                cls.implementer(), STEP_7_HEADING, str(IMPLEMENTER_PATH)
            ),
        )


def _report_block(step_7_text):
    match = re.search(r"```json\n(.*?)\n```", step_7_text, re.DOTALL)
    assert match, "Step 7 JSON block not found"
    return match.group(1)


class TestSectionsFound(unittest.TestCase):
    """Non-vacuity guard: every section the checks below are scoped to is found
    and non-empty first."""

    def test_implementer_rule_section_found_nonempty_and_top_level(self):
        level, section = Document.implementer_rule()
        self.assertEqual(level, 2)
        self.assertTrue(section.strip())

    def test_implementer_rule_section_precedes_hard_constraints(self):
        text = Document.implementer()
        self.assertLess(
            _heading_index(text, RULE_HEADING),
            _heading_index(text, HARD_CONSTRAINTS_HEADING),
        )

    def test_skill_rule_section_found_nonempty_and_top_level(self):
        level, section = Document.skill_rule()
        self.assertEqual(level, 2)
        self.assertTrue(section.strip())

    def test_step_7_section_found_and_nonempty(self):
        self.assertTrue(Document.step_7()[1].strip())

    def test_extraction_fails_loudly_on_a_missing_heading(self):
        with self.assertRaises(AssertionError):
            _extract_section(Document.implementer(), "no such heading exists")


class TestAc1ImmediateFailure(unittest.TestCase):
    """AC-1 / TS-12."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(Document.implementer_rule()[1])

    def test_trigger_is_the_write_rejection_text(self):
        self.assertIn(f"`{REJECTION_TEXT}`", self.normalized)

    def test_trigger_is_a_write_returning_the_text(self):
        self.assertRegex(self.normalized, r"Write (?:tool )?returns")

    def test_name_definition_is_cited_not_restated(self):
        self.assertIn(NAME_RULE_PATH, self.normalized)
        self.assertIn(f"`{NAME_RULE_HEADING}`", self.normalized)

    def test_returns_status_failed_immediately(self):
        self.assertRegex(
            self.normalized,
            r"(?i)return `status: failed` immediately",
        )

    def test_stops_work_at_once(self):
        self.assertRegex(self.normalized, r"(?i)stop work at once")

    def test_merge_script_is_not_run(self):
        self.assertRegex(self.normalized, r"(?i)do not run `merge_script`")


class TestAc2ReportField(unittest.TestCase):
    """AC-2 / TS-12, TM-8."""

    @classmethod
    def setUpClass(cls):
        cls.step_7 = Document.step_7()[1]
        cls.block = _report_block(cls.step_7)
        cls.after_block = _normalize_ws(cls.step_7.split("```")[-1])

    def test_report_block_has_write_rejection_as_a_top_level_key(self):
        keys = set(re.findall(r'^\s{2}"(\w+)":', self.block, re.MULTILINE))
        self.assertIn("write_rejection", keys)

    def test_mapping_is_kept_on_one_line_with_path_and_rejection_text(self):
        lines = [l for l in self.block.splitlines() if '"write_rejection"' in l]
        self.assertEqual(len(lines), 1)
        self.assertIn('"path"', lines[0])
        self.assertIn('"rejection_text"', lines[0])
        self.assertIn("null", lines[0])

    def test_description_after_the_block_names_null_and_both_members(self):
        self.assertIn("`write_rejection`", self.after_block)
        self.assertIn("`null`", self.after_block)
        self.assertIn("`path`", self.after_block)
        self.assertIn("`rejection_text`", self.after_block)

    def test_description_says_path_is_repository_relative_never_absolute(self):
        self.assertIn("repository-relative", self.after_block)
        self.assertIn("never absolute", self.after_block)

    def test_rule_section_names_the_report_field(self):
        normalized = _normalize_ws(Document.implementer_rule()[1])
        self.assertIn("`write_rejection`", normalized)


class TestAc3BannedRoutes(unittest.TestCase):
    """AC-3 / TS-12, TM-9, NFR1: each route is its own list item of the rule
    section."""

    @classmethod
    def setUpClass(cls):
        cls.items = _list_items(Document.implementer_rule()[1])

    def _items_matching(self, pattern):
        return [i for i in self.items if re.search(pattern, i, re.IGNORECASE)]

    def test_lead_in_forbids_working_around_the_rejection(self):
        normalized = _normalize_ws(Document.implementer_rule()[1])
        self.assertRegex(normalized, r"(?i)do not work around")

    def test_renaming_is_banned(self):
        self.assertTrue(self._items_matching(r"\brenam"))

    def test_writing_under_another_name_is_banned(self):
        self.assertTrue(self._items_matching(r"another name"))

    def test_creating_the_file_with_edit_is_banned(self):
        self.assertTrue(self._items_matching(r"\bEdit\b[^.]*creat|creat[^.]*\bEdit\b"))

    def test_writing_through_bash_is_banned(self):
        self.assertTrue(self._items_matching(r"\bBash\b"))

    def test_asking_the_parent_to_write_it_is_banned(self):
        self.assertTrue(self._items_matching(r"\bparent\b[^.]*\bwrit|ask[^.]*\bparent\b"))


class TestAc4BaseCommitScope(unittest.TestCase):
    """AC-4 / TS-12."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(Document.implementer_rule()[1])

    def test_rule_applies_to_a_file_that_exists_at_the_base_commit(self):
        self.assertRegex(
            self.normalized,
            r"(?i)also applies to a Write rejection on a file that exists at the base commit",
        )

    def test_such_a_file_is_updated_with_edit_from_the_start(self):
        self.assertRegex(
            self.normalized,
            r"(?i)exists there is updated with Edit from the start",
        )

    def test_edit_is_not_a_switch_after_a_rejection(self):
        self.assertRegex(
            self.normalized,
            r"(?i)not by switching to Edit after a rejection",
        )


class TestAc5WorktreeTaskWorkflow(unittest.TestCase):
    """AC-5 / TS-12."""

    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(Document.skill_rule()[1])
        cls.items = _list_items(Document.skill_rule()[1])

    def test_trigger_is_the_write_rejection_text(self):
        self.assertIn(f"`{REJECTION_TEXT}`", self.normalized)

    def test_states_the_immediate_failure(self):
        self.assertRegex(self.normalized, r"(?i)`status: failed` immediately")

    def test_merge_script_is_not_run(self):
        self.assertRegex(self.normalized, r"(?i)do not run `merge-task\.sh`")

    def test_reports_target_path_and_rejection_text(self):
        self.assertIn("`write_rejection`", self.normalized)
        self.assertRegex(self.normalized, r"(?i)target path")
        self.assertIn("rejection text", self.normalized)

    def test_bans_each_workaround(self):
        self.assertRegex(self.normalized, r"(?i)never work around")
        for label, pattern in (
            ("renaming", r"\brenam"),
            ("another name", r"another name"),
            ("Edit creating the file", r"\bEdit\b[^.]*creat|creat[^.]*\bEdit\b"),
            ("Bash", r"\bBash\b"),
            ("the parent writing it", r"\bparent\b"),
        ):
            with self.subTest(route=label):
                self.assertRegex(self.normalized, pattern)

    def test_cites_the_implementer_section_for_detail(self):
        self.assertIn("implementer.md", self.normalized)
        self.assertIn("`## Write rejection`", self.normalized)


class TestAc6ExpectedReportKeys(unittest.TestCase):
    """AC-6: the existing report-key guard holds `write_rejection`."""

    def test_expected_report_keys_hold_write_rejection(self):
        tree = ast.parse(_read(UNTRUSTED_TEST_PATH))
        keys = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "EXPECTED_REPORT_KEYS"
                    for t in node.targets
                )
            ):
                keys = {ast.literal_eval(e) for e in node.value.elts}
        self.assertIsNotNone(keys, "EXPECTED_REPORT_KEYS not found")
        self.assertIn("write_rejection", keys)


class TestNoRegexInDocuments(unittest.TestCase):
    """Negative check: documents other than the rule text cite the name
    definition and never carry the regex."""

    def test_detector_flags_a_synthetic_alternation(self):
        # Built at run time so this module itself carries no alternation.
        plain = "|".join(_STEMS)
        escaped = "\\|".join(_STEMS)
        self.assertTrue(carries_name_regex(f"^({plain}).*"))
        self.assertTrue(carries_name_regex(f"| {escaped} |"))
        self.assertTrue(carries_name_regex(f"^({plain.lower()})"))

    def test_detector_ignores_the_four_stems_in_prose(self):
        self.assertFalse(
            carries_name_regex("A report, a summary, findings or analysis.")
        )

    def test_implementer_md_does_not_contain_the_regex(self):
        self.assertFalse(carries_name_regex(Document.implementer()))

    def test_worktree_task_workflow_does_not_contain_the_regex(self):
        self.assertFalse(carries_name_regex(Document.skill()))


class TestStdlibOnly(unittest.TestCase):
    """This module imports the standard library only."""

    def test_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
