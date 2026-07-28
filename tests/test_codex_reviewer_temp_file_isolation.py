"""Tests for task0001: codex-reviewer temp-file discipline in both plugins.

Covers task0001 Acceptance Criteria
(feature-docs/codex-reviewer-temp-file-isolation/tasks/task0001.md):

- AC-1: em-workflow/agents/codex-reviewer.md contains a temp-file discipline
  section stating all five required elements (when it applies, the hazard,
  the mktemp mechanism, the prohibition, the failure route).
- AC-2: em-review/agents/codex-reviewer.md contains the equivalent section,
  with the same five elements.
- AC-3: both sections name `mktemp` and show a template containing the
  `XXXXXX` placeholder.
- AC-4: both sections explicitly forbid fixed and perspective-derived names
  and state that uniqueness is per invocation, not per perspective.
- AC-5: both sections route allocation failure to the standard skip object.
- AC-6: this file asserts AC-1 through AC-5 over both files, plus the
  unchanged wrapper invocation (NFR1); the whole suite must stay green.
- AC-7: both .claude-plugin/plugin.json files carry a patch-bumped version.

This is a documentation task (Test Notes: "the deliverable is prose... the
tests are structural checks over markdown text"), following the pattern of
tests/test_planner_designer_worktree_docs.py and
tests/test_review_implement_develop_lock_contracts.py: locate files relative
to this test file's own path, assert on required elements rather than whole
sentences, and extract the relevant section via literal heading/marker
anchors so assertions cannot pass against unrelated content elsewhere in the
file.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / "agents" / "codex-reviewer.md",
    "em-review": REPO_ROOT / "em-review" / "agents" / "codex-reviewer.md",
}

PLUGIN_JSON_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json",
    "em-review": REPO_ROOT / "em-review" / ".claude-plugin" / "plugin.json",
}

# Expected patch-bumped versions (baseline was em-workflow 0.1.23, em-review
# 0.5.1 at task0001 authoring time).
EXPECTED_PLUGIN_VERSIONS = {
    "em-workflow": "0.1.24",
    "em-review": "0.5.2",
}

SECTION_HEADING = "## Temp-file discipline (only if writing the prompt to disk)"
NEXT_HEADING = "## Step 5: Execute Codex"

WRAPPER_INVOCATION_LINE = (
    '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C '
    '"{project_root}" --output-schema "$SCHEMA" "$PROMPT"'
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_whitespace(text):
    """Collapse all whitespace runs (including the line-wraps markdown
    prose uses at ~79 columns) to a single space, so multi-word phrase
    checks survive reflowing that does not change meaning."""
    return re.sub(r"\s+", " ", text)


def _extract_discipline_section(text, plugin_name):
    """Return the text of the temp-file discipline section, anchored by its
    literal heading and the (unchanged) heading of the following step. Raises
    AssertionError with a message naming the plugin if the section is
    missing entirely -- this is what makes the test genuinely fail before
    the section is added, rather than passing on unrelated content."""
    if SECTION_HEADING not in text:
        raise AssertionError(
            f"AC-1/AC-2 ({plugin_name}): missing temp-file discipline "
            f"section heading {SECTION_HEADING!r}"
        )
    if NEXT_HEADING not in text:
        raise AssertionError(
            f"({plugin_name}): expected unchanged heading {NEXT_HEADING!r} "
            "to bound the new section -- has 'Execute Codex' step been "
            "renamed or removed?"
        )
    start = text.index(SECTION_HEADING)
    end = text.index(NEXT_HEADING, start)
    return text[start:end]


class TestTempFileDisciplineSectionPresentInBothFiles(unittest.TestCase):
    """AC-1, AC-2: both agent definitions carry the discipline section, and
    it states all five required elements from the task plan's Design
    section."""

    @classmethod
    def setUpClass(cls):
        cls.full_texts = {name: _read(path) for name, path in AGENT_PATHS.items()}
        cls.sections = {
            name: _extract_discipline_section(text, name)
            for name, text in cls.full_texts.items()
        }

    def test_when_it_applies_is_stated_in_both_files(self):
        # Element 1 / FR6: only applies when writing a temp file into the
        # session scratchpad; passing the prompt straight to the wrapper as
        # a shell variable needs no file.
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                lowered = _normalize_whitespace(section.lower())
                self.assertIn(
                    "temp file",
                    lowered,
                    f"AC-1/AC-2 ({name}): must state when the rule applies "
                    "(writing a temp file)",
                )
                self.assertIn(
                    "scratchpad",
                    lowered,
                    f"AC-1/AC-2 ({name}): must name the session scratchpad",
                )

    def test_hazard_of_parallel_overwrite_is_stated_in_both_files(self):
        # Element 2: parallel codex-reviewer instances share the scratchpad;
        # a fixed name lets a sibling overwrite the file between write/read.
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                lowered = section.lower()
                self.assertIn(
                    "parallel",
                    lowered,
                    f"AC-1/AC-2 ({name}): must name the parallel-instance hazard",
                )
                self.assertIn(
                    "overwrite",
                    lowered,
                    f"AC-1/AC-2 ({name}): must state the overwrite hazard",
                )

    def test_mktemp_mechanism_with_xxxxxx_template_in_both_files(self):
        # AC-3
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                self.assertIn(
                    "mktemp",
                    section,
                    f"AC-3 ({name}): must name mktemp as the allocation mechanism",
                )
                self.assertIn(
                    "XXXXXX",
                    section,
                    f"AC-3 ({name}): must show a template with the XXXXXX placeholder",
                )

    def test_prohibition_of_fixed_and_perspective_derived_names_in_both_files(self):
        # AC-4
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                lowered = _normalize_whitespace(section.lower())
                self.assertIn(
                    "prompt.txt",
                    section,
                    f"AC-4 ({name}): must give a forbidden fixed-name example",
                )
                self.assertIn(
                    "security-prompt.txt",
                    section,
                    f"AC-4 ({name}): must give a forbidden perspective-derived-name example",
                )
                self.assertIn(
                    "per invocation",
                    lowered,
                    f"AC-4 ({name}): must state uniqueness is per invocation",
                )
                self.assertIn(
                    "per perspective",
                    lowered,
                    f"AC-4 ({name}): must contrast with per-perspective uniqueness",
                )

    def test_allocation_failure_routes_to_standard_skip_object_in_both_files(self):
        # AC-5
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                self.assertIn(
                    '"skipped": true',
                    section,
                    f"AC-5 ({name}): failure route must use the standard skip object",
                )
                self.assertIn(
                    '"source": "codex"',
                    section,
                    f"AC-5 ({name}): standard skip object must carry source codex",
                )

    def test_section_is_positioned_before_execute_codex_step(self):
        # IMPLEMENTATION.md Conventions: section placement is immediately
        # before the existing "Execute Codex" step.
        for name, text in self.full_texts.items():
            with self.subTest(plugin=name):
                self.assertLess(
                    text.index(SECTION_HEADING),
                    text.index(NEXT_HEADING),
                    f"({name}): discipline section must precede the Execute Codex step",
                )


class TestWrapperInvocationUnchanged(unittest.TestCase):
    """AC-6 (NFR1): the Codex wrapper invocation still uses the same mode,
    working-directory, output-schema and prompt arguments, and no
    prompt-file flag was introduced."""

    @classmethod
    def setUpClass(cls):
        cls.full_texts = {name: _read(path) for name, path in AGENT_PATHS.items()}

    def test_wrapper_invocation_line_is_unchanged_in_both_files(self):
        for name, text in self.full_texts.items():
            with self.subTest(plugin=name):
                self.assertIn(
                    WRAPPER_INVOCATION_LINE,
                    text,
                    f"NFR1 ({name}): run_codex_exec.sh invocation must be "
                    "byte-for-byte unchanged",
                )

    def test_no_prompt_file_flag_was_introduced_in_either_file(self):
        for name, text in self.full_texts.items():
            with self.subTest(plugin=name):
                self.assertNotIn(
                    "--prompt-file",
                    text,
                    f"NFR1 ({name}): no prompt-file flag may be introduced "
                    "on the wrapper invocation",
                )


class TestPluginJsonVersionBump(unittest.TestCase):
    """AC-7: both plugin.json files have a patch-bumped version."""

    @classmethod
    def setUpClass(cls):
        cls.raws = {name: _read(path) for name, path in PLUGIN_JSON_PATHS.items()}
        cls.data = {name: json.loads(raw) for name, raw in cls.raws.items()}

    def test_plugin_json_files_are_valid_json(self):
        for name, raw in self.raws.items():
            with self.subTest(plugin=name):
                try:
                    json.loads(raw)
                except json.JSONDecodeError as exc:
                    self.fail(f"AC-7 ({name}): plugin.json is not valid JSON: {exc}")

    def test_version_is_patch_bumped_in_both_files(self):
        for name, data in self.data.items():
            with self.subTest(plugin=name):
                self.assertEqual(
                    data["version"],
                    EXPECTED_PLUGIN_VERSIONS[name],
                    f"AC-7 ({name}): version must be patch-bumped to "
                    f"{EXPECTED_PLUGIN_VERSIONS[name]}",
                )


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test)."""

    def test_missing_discipline_section_is_detected(self):
        with self.assertRaises(AssertionError):
            _extract_discipline_section(
                "## Step 5: Execute Codex\nno discipline section here\n",
                "fake-plugin",
            )

    def test_missing_execute_codex_heading_is_detected(self):
        with self.assertRaises(AssertionError):
            _extract_discipline_section(
                f"{SECTION_HEADING}\nsome content but no next heading\n",
                "fake-plugin",
            )

    def test_wrong_version_bump_is_detected(self):
        fake = {"version": "0.1.23"}
        self.assertNotEqual(fake["version"], EXPECTED_PLUGIN_VERSIONS["em-workflow"])

    def test_prompt_file_flag_introduction_is_detected(self):
        sample = WRAPPER_INVOCATION_LINE.replace(
            '"$PROMPT"', '--prompt-file "$PROMPT_FILE"'
        )
        self.assertIn("--prompt-file", sample)


if __name__ == "__main__":
    unittest.main()
