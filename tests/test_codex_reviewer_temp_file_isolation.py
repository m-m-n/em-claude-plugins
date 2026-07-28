"""Tests for task0001 + task0002 rework: codex-reviewer temp-file discipline
in both plugins.

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

Covers task0002 Acceptance Criteria
(feature-docs/codex-reviewer-temp-file-isolation/tasks/task0002.md), which
reworked review round 1 residuals:

- AC-1: the mktemp example is self-contained -- no bare $IDENTIFIER left
  undefined by the repository (round 1 F-1: `$SCRATCHPAD_DIR` was never
  defined anywhere in either plugin).
- AC-2: the section states it applies to any file written into the session
  scratchpad (prompt, schema copy, intermediate output), not narrowed to
  `$PROMPT` alone (round 1 F-2).
- AC-3: the skip summary string is identical across both agent definitions
  and SPEC.md's Error Handling table (round 1 F-3).
- AC-4: plugin.json versions are checked against a pre-feature baseline
  rather than pinned by exact bumped literal, so this file does not break on
  an unrelated later patch bump (round 1 F-4).
- AC-5: every test in this module fails when the production artifact it
  claims to check is broken -- TestValidationDetectsRegressions now runs the
  actual production-check helpers against forged input inside
  `assertRaises`, instead of asserting on unrelated local literals (round 1
  F-5).
- AC-6: wording stays parallel between the two agent definitions, and
  `python3 -m unittest discover -s tests` passes with no regressions.

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

SPEC_PATH = (
    REPO_ROOT / "feature-docs" / "codex-reviewer-temp-file-isolation" / "SPEC.md"
)

# Baseline versions from before this feature bumped plugin.json (task0001).
# task0002 AC-4: compare the current version against this fixed pre-feature
# baseline instead of pinning the bumped literal. Pinning the bumped literal
# means an unrelated later patch bump of either plugin also breaks this file
# -- the exact pattern that broke test_planner_designer_worktree_docs.py at
# commit 15a18e9.
BASELINE_PLUGIN_VERSIONS = {
    "em-workflow": "0.1.23",
    "em-review": "0.5.1",
}

SECTION_HEADING = "## Temp-file discipline (only if writing a file to disk)"
NEXT_HEADING = "## Step 5: Execute Codex"

WRAPPER_INVOCATION_LINE = (
    '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C '
    '"{project_root}" --output-schema "$SCHEMA" "$PROMPT"'
)

# task0002 AC-3: the exact skip summary string that must appear verbatim in
# both agent definitions and in SPEC.md's Error Handling table.
TEMP_FILE_SKIP_SUMMARY = "skipped: scratchpad temp file unavailable"

MKTEMP_TEMPLATE_PATTERN = re.compile(r'mktemp\s+"([^"]*XXXXXX[^"]*)"')
VAR_REF_PATTERN = re.compile(r"\$(\{[^}]*\}|[A-Za-z_][A-Za-z0-9_]*)")
GUARDED_VAR_FORM = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*:-.*\}$")


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


def _extract_mktemp_template(section, plugin_name):
    """Return the quoted mktemp template argument (the string containing the
    XXXXXX placeholder) from the discipline section. Raises AssertionError
    naming the plugin if no such template is present."""
    match = MKTEMP_TEMPLATE_PATTERN.search(section)
    if not match:
        raise AssertionError(
            f'AC-1/AC-3 ({plugin_name}): no mktemp "...XXXXXX..." template '
            "found in the discipline section"
        )
    return match.group(1)


def _assert_mktemp_template_is_self_contained(template, plugin_name):
    """task0002 AC-1 (F-1): every $-variable reference inside the mktemp
    template must be a guarded parameter expansion with a literal default
    (${VAR:-default}), so the allocated path resolves to a real filesystem
    location even when VAR is unset in the environment. A bare reference
    like $SCRATCHPAD_DIR -- defined nowhere in either plugin and never
    exported -- expands to empty and produces a path rooted at "/",
    reproducing review round 1's F-1."""
    for match in VAR_REF_PATTERN.finditer(template):
        token = match.group(1)
        if not GUARDED_VAR_FORM.match(token):
            raise AssertionError(
                f"AC-1 ({plugin_name}): mktemp template {template!r} "
                f"references unguarded variable '${token}' with no default "
                "fallback"
            )


def _version_tuple(version_string):
    return tuple(int(part) for part in version_string.split("."))


def _assert_version_is_patch_bumped_above_baseline(version, baseline, plugin_name):
    """AC-7: the real check behind the plugin.json version assertion,
    extracted into a helper so TestValidationDetectsRegressions can run it
    against forged input and prove it fails (task0002 AC-5)."""
    if _version_tuple(version) <= _version_tuple(baseline):
        raise AssertionError(
            f"AC-7 ({plugin_name}): version {version!r} is not a patch "
            f"bump above baseline {baseline!r}"
        )


def _assert_wrapper_invocation_unchanged(text, plugin_name):
    """NFR1: the real check behind the wrapper-invocation assertion,
    extracted into a helper so TestValidationDetectsRegressions can run it
    against forged input and prove it fails (task0002 AC-5)."""
    if WRAPPER_INVOCATION_LINE not in text:
        raise AssertionError(
            f"NFR1 ({plugin_name}): run_codex_exec.sh invocation must be "
            "byte-for-byte unchanged"
        )


class TestTempFileDisciplineSectionPresentInBothFiles(unittest.TestCase):
    """AC-1, AC-2 (task0001): both agent definitions carry the discipline
    section, and it states all five required elements from the task plan's
    Design section. Also task0002's rework of F-1 (self-contained mktemp
    example) and F-2 (widened scope beyond $PROMPT)."""

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

    def test_applies_to_any_scratchpad_temp_file_not_only_prompt(self):
        # task0002 AC-2 (F-2): FR1's enumeration (prompt, schema copy,
        # intermediate output), not narrowed to $PROMPT with an explicit
        # "only".
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                lowered = _normalize_whitespace(section.lower())
                self.assertIn(
                    "schema copy",
                    lowered,
                    f"AC-2 ({name}): scope must enumerate a schema copy",
                )
                self.assertIn(
                    "intermediate output",
                    lowered,
                    f"AC-2 ({name}): scope must enumerate intermediate output",
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

    def test_mktemp_template_is_self_contained_in_both_files(self):
        # task0002 AC-1 (F-1): no bare/unguarded variable reference (e.g.
        # $SCRATCHPAD_DIR, defined nowhere in either plugin) in the mktemp
        # template.
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                template = _extract_mktemp_template(section, name)
                _assert_mktemp_template_is_self_contained(template, name)

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


class TestSkipSummaryStringMatchesSpec(unittest.TestCase):
    """task0002 AC-3 (F-3): the temp-file-allocation-failure skip summary
    string is identical across both agent definitions and SPEC.md's Error
    Handling table, so the SSOT and the shipped artifact cannot silently
    diverge."""

    @classmethod
    def setUpClass(cls):
        cls.sections = {
            name: _extract_discipline_section(_read(path), name)
            for name, path in AGENT_PATHS.items()
        }
        cls.spec_text = _read(SPEC_PATH)

    def test_skip_summary_string_matches_in_both_agent_files(self):
        for name, section in self.sections.items():
            with self.subTest(plugin=name):
                self.assertIn(
                    f'"summary": "{TEMP_FILE_SKIP_SUMMARY}"',
                    section,
                    f"AC-3 ({name}): skip summary string must read "
                    f"{TEMP_FILE_SKIP_SUMMARY!r}",
                )

    def test_skip_summary_string_matches_spec_error_handling_table(self):
        self.assertIn(
            TEMP_FILE_SKIP_SUMMARY,
            self.spec_text,
            "AC-3: SPEC.md's Error Handling table must use the same skip "
            f"summary string {TEMP_FILE_SKIP_SUMMARY!r}",
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
                _assert_wrapper_invocation_unchanged(text, name)

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
    """AC-7: both plugin.json files have a patch-bumped version. task0002
    AC-4 (F-4): checked against a fixed pre-feature baseline rather than
    pinned by exact bumped literal."""

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

    def test_version_is_patch_bumped_above_baseline_in_both_files(self):
        for name, data in self.data.items():
            with self.subTest(plugin=name):
                _assert_version_is_patch_bumped_above_baseline(
                    data["version"], BASELINE_PLUGIN_VERSIONS[name], name
                )


class TestValidationDetectsRegressions(unittest.TestCase):
    """Proof that the checks above fail meaningfully, per the tdd-testing
    discipline (a test that can never fail is not a test). task0002 AC-5
    (F-5): each regression test below runs the real production-check helper
    against forged input inside `assertRaises`, rather than asserting on an
    unrelated local literal."""

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

    def test_version_not_bumped_is_detected(self):
        # Forge a version equal to the baseline (no bump happened) and
        # confirm the real production-check helper rejects it.
        with self.assertRaises(AssertionError):
            _assert_version_is_patch_bumped_above_baseline(
                BASELINE_PLUGIN_VERSIONS["em-workflow"],
                BASELINE_PLUGIN_VERSIONS["em-workflow"],
                "em-workflow",
            )

    def test_version_bumped_above_baseline_passes(self):
        # Sanity check: the same helper does not raise for a genuine bump.
        _assert_version_is_patch_bumped_above_baseline(
            "0.1.24", BASELINE_PLUGIN_VERSIONS["em-workflow"], "em-workflow"
        )

    def test_prompt_file_flag_introduction_is_detected(self):
        # Forge the wrapper line broken by a --prompt-file flag and confirm
        # the real production-check helper rejects it.
        forged_text = WRAPPER_INVOCATION_LINE.replace(
            '"$PROMPT"', '--prompt-file "$PROMPT_FILE"'
        )
        with self.assertRaises(AssertionError):
            _assert_wrapper_invocation_unchanged(forged_text, "fake-plugin")

    def test_unguarded_mktemp_variable_is_detected(self):
        # Forge the round-1 defect ($SCRATCHPAD_DIR, never defined) and
        # confirm the real production-check helper rejects it.
        with self.assertRaises(AssertionError):
            _assert_mktemp_template_is_self_contained(
                "$SCRATCHPAD_DIR/codex-reviewer-prompt.XXXXXX", "fake-plugin"
            )

    def test_guarded_mktemp_variable_passes(self):
        # Sanity check: the same helper does not raise for the compliant
        # guarded form.
        _assert_mktemp_template_is_self_contained(
            "${TMPDIR:-/tmp}/codex-reviewer-prompt.XXXXXX", "fake-plugin"
        )


if __name__ == "__main__":
    unittest.main()
