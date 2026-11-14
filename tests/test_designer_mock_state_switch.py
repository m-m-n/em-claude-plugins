"""Tests for task0002 (design-mock-hot-reload): the Mockups item of
em-workflow/agents/designer.md (Design Artifact Rules) states the
`?state=<name>` state switch.

Covers task0002 Acceptance Criteria (feature-docs/design-mock-hot-reload/
tasks/task0002.md):

- AC-1: the Mockups item states that the query `?state=<name>` shows only the
  sections whose `data-state` equals the value, and that the value is used
  only in a literal equality comparison with each section's `data-state`
  value, never inserted into the document and never used to compose markup,
  selectors or code (TM-3).
- AC-2: the same item states that with no query, or with a value that matches
  no section, every state section is shown side by side, and that nothing is
  hidden unless at least one section matches (TM-3).
- AC-3: the same item allows one small inline plain JavaScript for the state
  switch only, keeps "no JS frameworks" and no external requests, and states
  that the mock file holds no reload code.
- AC-4: the same item still requires a self-contained single file (inline
  CSS, no external requests, no JS frameworks), tokens embedded as CSS custom
  properties, and every state that SPEC names.
- AC-5 (designer.md half): the tools line is unchanged (no Bash) and
  designer.md gains no dev-server step. The pinned phrases of
  tests/test_refitted_worker_agents.py and the full suite are covered by
  those tests themselves; the change set (no plugin.json / marketplace.json)
  is checked by diff against the implement base commit, not by a test.

These are static tests of the rule text. No mock file is read or created and
no process is started.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
DESIGNER_PATH = PLUGIN_ROOT / "agents" / "designer.md"

RULES_HEADING = "## Design Artifact Rules"
MOCKUPS_LABEL = "- **Mockups**:"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapse every whitespace run (including line wraps) to one space."""
    return re.sub(r"\s+", " ", text)


def _slice_mockups_item(text):
    """Return the Mockups item: from its `- **Mockups**:` label up to (not
    including) the next top-level `- **` item of the Design Artifact Rules
    section, or the end of that section."""
    start = text.index(RULES_HEADING)
    following_heading = re.search(
        r"^## ", text[start + len(RULES_HEADING):], re.MULTILINE
    )
    end = (
        start + len(RULES_HEADING) + following_heading.start()
        if following_heading
        else len(text)
    )
    rules = text[start:end]
    item_start = rules.index(MOCKUPS_LABEL)
    after_label = item_start + len(MOCKUPS_LABEL)
    next_item = re.search(r"^- \*\*", rules[after_label:], re.MULTILINE)
    item_end = after_label + next_item.start() if next_item else len(rules)
    return rules[item_start:item_end]


def _split_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise AssertionError("expected a --- delimited frontmatter block")
    return match.group(1), match.group(2)


def _tools_list(frontmatter_text):
    tools_line = next(
        line for line in frontmatter_text.splitlines() if line.startswith("tools:")
    )
    return [t.strip() for t in tools_line.split(":", 1)[1].split(",")]


class MockupsItemTestCase(unittest.TestCase):
    """Base: loads designer.md once and exposes the whitespace-normalized
    Mockups item as `self.item`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DESIGNER_PATH)
        cls.item = _normalize(_slice_mockups_item(cls.text))

    def assertItemMatches(self, pattern):
        self.assertRegex(self.item, re.compile(pattern, re.IGNORECASE))


class TestMockupsItemSlicing(unittest.TestCase):
    """The slicing helper scopes every other assertion to the Mockups item."""

    SAMPLE = (
        "## Design Artifact Rules\n\n"
        "- **tokens.html**: sheet\n"
        "- **Mockups**: first line\n  second line\n"
        "- **DESIGN.md**: Decisions / Rationale / Open items\n\n"
        "## Process\n- **Mockups**: later and unrelated\n"
    )

    def test_slice_stops_at_next_top_level_item(self):
        sliced = _slice_mockups_item(self.SAMPLE)
        self.assertEqual(sliced, "- **Mockups**: first line\n  second line\n")

    def test_real_item_does_not_leak_into_neighbouring_items(self):
        sliced = _slice_mockups_item(_read(DESIGNER_PATH))
        self.assertTrue(sliced.startswith(MOCKUPS_LABEL))
        self.assertNotIn("- **DESIGN.md**", sliced)
        self.assertNotIn("- **input**", sliced)
        self.assertNotIn("- **tokens.html**", sliced)


class TestAC1QueryStateShowsOnlyMatchingSections(MockupsItemTestCase):
    """AC-1 (FR4, TM-3)."""

    def test_ac1_names_the_state_query(self):
        self.assertIn("?state=<name>", self.item)

    def test_ac1_shows_only_sections_whose_data_state_equals_the_value(self):
        self.assertItemMatches(
            r"only the sections whose `data-state` value equals the query value"
        )

    def test_ac1_value_is_used_only_in_a_literal_equality_comparison(self):
        self.assertItemMatches(
            r"only in a literal equality comparison with each section's "
            r"`data-state` value"
        )

    def test_ac1_value_is_never_inserted_into_the_document(self):
        self.assertItemMatches(r"never inserted into the document")

    def test_ac1_nothing_is_composed_from_the_value(self):
        self.assertItemMatches(
            r"no markup, selector or code is composed from it"
        )


class TestAC2FallbackShowsEveryState(MockupsItemTestCase):
    """AC-2 (FR4, TM-3)."""

    def test_ac2_no_query_or_unmatched_value_shows_every_state_section(self):
        self.assertItemMatches(
            r"with no query, or with a value that matches no section, every "
            r"state section is shown side by side"
        )

    def test_ac2_nothing_is_hidden_unless_a_section_matches(self):
        self.assertItemMatches(
            r"nothing is hidden unless at least one section matches"
        )


class TestAC3ScriptAllowanceAndNoReloadCode(MockupsItemTestCase):
    """AC-3 (FR4, FR3)."""

    def test_ac3_allows_one_small_inline_plain_javascript(self):
        self.assertItemMatches(r"one small inline plain JavaScript")

    def test_ac3_script_is_for_the_state_switch_only(self):
        self.assertItemMatches(r"for the state switch only")

    def test_ac3_keeps_no_js_frameworks(self):
        self.assertIn("no JS frameworks", self.item)

    def test_ac3_keeps_no_external_requests(self):
        self.assertIn("no external requests", self.item)

    def test_ac3_mock_file_holds_no_reload_code(self):
        self.assertItemMatches(r"the mock file holds no reload code")

    def test_ac3_browser_update_on_edit_belongs_to_the_dev_server(self):
        self.assertItemMatches(
            r"browser update on edit is the dev server's job and is not part "
            r"of the file"
        )


class TestAC4KeptMockPoints(MockupsItemTestCase):
    """AC-4 (FR6): the three pre-existing mock-discipline points stay."""

    def test_ac4_requires_self_contained_single_file_html(self):
        self.assertIn("self-contained single-file HTML", self.item)

    def test_ac4_keeps_the_inline_css_no_requests_no_frameworks_group(self):
        self.assertIn(
            "(inline CSS, no external requests, no JS frameworks)", self.item
        )

    def test_ac4_embeds_tokens_as_css_custom_properties(self):
        self.assertIn("CSS custom properties", self.item)
        self.assertIn("`--color-primary`", self.item)

    def test_ac4_states_are_sibling_sections_with_data_state(self):
        self.assertIn("sibling sections", self.item)
        self.assertIn('`data-state="empty"`', self.item)

    def test_ac4_every_state_spec_mentions_is_mandatory(self):
        self.assertItemMatches(
            r"every state SPEC\.md mentions for the screen "
            r"\(empty / error / loading / boundary\) is MANDATORY"
        )

    def test_ac4_mockups_remain_design_specs_not_implementation(self):
        self.assertIn("Mockups are design specs, NOT implementation", self.item)


class TestAC5DesignerStaysServerFree(MockupsItemTestCase):
    """AC-5, designer.md half (D4): no Bash tool and no server step."""

    SERVER_STEP_MARKERS = ("TaskStop", "run_in_background", "Bash")

    def test_ac5_tools_line_is_unchanged(self):
        frontmatter, _ = _split_frontmatter(self.text)
        self.assertEqual(
            _tools_list(frontmatter), ["Read", "Write", "Glob", "Grep"]
        )

    def test_ac5_tools_do_not_gain_bash(self):
        frontmatter, _ = _split_frontmatter(self.text)
        self.assertNotIn("Bash", _tools_list(frontmatter))

    def test_ac5_no_server_lifecycle_step_anywhere_in_designer_md(self):
        for marker in self.SERVER_STEP_MARKERS:
            self.assertNotIn(marker, self.text)

    def test_ac5_dev_server_is_named_only_inside_the_mockups_item(self):
        outside = self.text.replace(_slice_mockups_item(self.text), "")
        self.assertNotIn("dev server", _normalize(outside))


if __name__ == "__main__":
    unittest.main()
