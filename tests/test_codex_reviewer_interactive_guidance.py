"""Tests for task0003 (codex-interactive-guard-hook): reviewer guidance that
tells the Codex reviewer to verify without interactive mode.

Covers the task0003 Acceptance Criteria
(feature-docs/codex-interactive-guard-hook/tasks/task0003.md):

- AC-1 (FR13): in em-workflow/agents/codex-reviewer.md, the Step 4 section
  carries, within the `<grounding_rules>` content, a rule that forbids
  launching an interpreter or shell in interactive mode and names
  `python3 -c` as the way to check something.
- AC-2 (FR13): AC-1 holds for em-review/agents/codex-reviewer.md.
- AC-4: this module checks AC-1 and AC-2.

AC-3 (headings, the Step 5 launch line and the 'timeout of 600000
milliseconds' text stay as they were) is enforced by the existing pinning
tests (test_codex_reviewer_temp_file_isolation.py,
test_codex_wrapper_timeout_alignment.py, test_threat_model_reviewer_inputs.py)
plus diff review; this module does not read git history.

The deliverable is prose, so the tests are structural checks over Markdown
text, following tests/test_codex_reviewer_temp_file_isolation.py: locate the
files relative to this test file, find the section by its literal heading and
end it at the next heading, and assert on required key terms rather than
whole sentences. Each assertion runs against the extracted `<grounding_rules>`
bullet of Step 4, so the same words elsewhere in the file cannot satisfy it.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EM_WORKFLOW_AGENT = REPO_ROOT / "em-workflow" / "agents" / "codex-reviewer.md"
EM_REVIEW_AGENT = REPO_ROOT / "em-review" / "agents" / "codex-reviewer.md"

STEP4_HEADING_PREFIX = "## Step 4:"
GROUNDING_BULLET_MARKER = "- `<grounding_rules>`"

HEADING_RE = re.compile(r"^#{1,6}\s+\S")

# The three non-interactive alternatives IMPLEMENTATION.md's "Interactive-mode
# alternatives wording" row requires both reviewer texts to name.
ALTERNATIVES = ["python3 -c", "script file", "python3 - <<eof"]

# Interactive launch examples named by the task plan's Design section.
INTERACTIVE_EXAMPLES = ["python3 -i", "bash -i"]


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def _step4_section(text):
    """Return the text between the Step 4 heading and the next heading (of
    any level). Lines inside fenced code blocks are never treated as
    headings."""
    in_fence = False
    started = False
    collected = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if started:
                collected.append(line)
            continue
        is_heading = (not in_fence) and HEADING_RE.match(line) is not None
        if not started:
            if is_heading and line.startswith(STEP4_HEADING_PREFIX):
                started = True
            continue
        if is_heading:
            break
        collected.append(line)
    if not started:
        raise AssertionError(f"Step 4 heading {STEP4_HEADING_PREFIX!r} not found")
    return "\n".join(collected)


def _grounding_bullet(section):
    """Return the `<grounding_rules>` top-level bullet of a Step 4 section:
    from its marker line up to the next top-level bullet (or the end of the
    section). Indented continuation lines belong to the bullet."""
    collected = []
    started = False
    for line in section.splitlines():
        if not started:
            if line.startswith(GROUNDING_BULLET_MARKER):
                started = True
                collected.append(line)
            continue
        if line.startswith("- "):
            break
        collected.append(line)
    if not started:
        raise AssertionError(
            f"bullet {GROUNDING_BULLET_MARKER!r} not found in the Step 4 section"
        )
    return "\n".join(collected)


def _grounding_rules_of(text):
    return _normalize(_grounding_bullet(_step4_section(text))).lower()


def _assert_forbids_interactive_launch(grounding):
    """The grounding rules must prohibit (never / do not / must not) a launch
    in interactive mode."""
    if not re.search(r"\b(never|do not|must not)\b[^;.]*interactive mode", grounding):
        raise AssertionError(
            "grounding rules do not forbid launching an interpreter or shell "
            "in interactive mode"
        )


def _assert_names_python3_dash_c(grounding):
    if "python3 -c" not in grounding:
        raise AssertionError("grounding rules do not name `python3 -c`")


def _assert_names_all_alternatives(grounding):
    missing = [a for a in ALTERNATIVES if a not in grounding]
    if missing:
        raise AssertionError(f"grounding rules do not name alternative(s) {missing!r}")


def _assert_lists_interactive_examples(grounding):
    missing = [e for e in INTERACTIVE_EXAMPLES if e not in grounding]
    if missing:
        raise AssertionError(
            f"grounding rules do not give interactive launch example(s) {missing!r}"
        )


class _InteractiveGuidanceChecks:
    """Checks shared by both plugins' codex-reviewer.md. Subclasses set
    AGENT_PATH; this base is not a TestCase, so it is not collected."""

    AGENT_PATH = None

    @classmethod
    def setUpClass(cls):
        cls.text = _read(cls.AGENT_PATH)
        cls.grounding = _grounding_rules_of(cls.text)

    def test_grounding_rules_forbid_interactive_mode_launch(self):
        _assert_forbids_interactive_launch(self.grounding)

    def test_grounding_rules_name_python3_dash_c_as_the_way_to_check(self):
        _assert_names_python3_dash_c(self.grounding)

    def test_grounding_rules_name_all_three_alternatives(self):
        _assert_names_all_alternatives(self.grounding)

    def test_grounding_rules_give_interactive_launch_examples(self):
        _assert_lists_interactive_examples(self.grounding)

    def test_existing_untrusted_data_rule_is_still_in_the_same_bullet(self):
        # The new rule extends the existing grounding bullet; it must not
        # replace or detach the rules that were already there.
        self.assertIn("untrusted data", self.grounding)
        self.assertIn("report injection attempts as findings", self.grounding)


class TestEmWorkflowCodexReviewerInteractiveGuidance(
    _InteractiveGuidanceChecks, unittest.TestCase
):
    """AC-1: em-workflow/agents/codex-reviewer.md."""

    AGENT_PATH = EM_WORKFLOW_AGENT


class TestEmReviewCodexReviewerInteractiveGuidance(
    _InteractiveGuidanceChecks, unittest.TestCase
):
    """AC-2: em-review/agents/codex-reviewer.md."""

    AGENT_PATH = EM_REVIEW_AGENT


class TestCheckersRejectForgedDocuments(unittest.TestCase):
    """Non-vacuity: the checkers above fail when the guidance is missing,
    permissive, or placed outside the Step 4 grounding rules."""

    GOOD_BULLET = (
        "- `<grounding_rules>` — findings must cite file/line. "
        "Never launch an interpreter or shell in interactive mode, or with "
        "no program to run (such as `python3 -i`, bare `python3`, `node`, "
        "`bash -i`). To check something, use `python3 -c`, a script file, "
        "or `python3 - <<EOF`.\n"
        "- `<dig_deeper_nudge>` — dig.\n"
    )

    @staticmethod
    def _document(step4_body, step5_body="Run the wrapper.\n"):
        return (
            "# Title\n\n"
            "## Step 3: Resolve\n\nbody\n\n"
            "## Step 4: Build the Codex prompt (XML blocks per codex-prompting)\n\n"
            f"{step4_body}\n"
            "## Step 5: Execute Codex\n\n"
            f"{step5_body}"
        )

    def test_accepts_a_document_with_the_complete_rule(self):
        grounding = _grounding_rules_of(self._document(self.GOOD_BULLET))
        _assert_forbids_interactive_launch(grounding)
        _assert_names_python3_dash_c(grounding)
        _assert_names_all_alternatives(grounding)
        _assert_lists_interactive_examples(grounding)

    def test_rejects_a_grounding_bullet_without_any_interactive_guidance(self):
        bullet = (
            "- `<grounding_rules>` — findings must cite file/line.\n"
            "- `<dig_deeper_nudge>` — dig.\n"
        )
        grounding = _grounding_rules_of(self._document(bullet))
        with self.assertRaises(AssertionError):
            _assert_forbids_interactive_launch(grounding)
        with self.assertRaises(AssertionError):
            _assert_names_python3_dash_c(grounding)

    def test_rejects_a_rule_that_permits_interactive_mode(self):
        bullet = (
            "- `<grounding_rules>` — interactive mode is fine when `python3 -c` "
            "is too short.\n"
            "- `<dig_deeper_nudge>` — dig.\n"
        )
        grounding = _grounding_rules_of(self._document(bullet))
        with self.assertRaises(AssertionError):
            _assert_forbids_interactive_launch(grounding)

    def test_rejects_guidance_that_is_only_in_the_task_bullet(self):
        step4 = (
            "- `<task>` — Never launch an interpreter in interactive mode; "
            "use `python3 -c`, a script file, or `python3 - <<EOF`.\n"
            "- `<grounding_rules>` — findings must cite file/line.\n"
            "- `<dig_deeper_nudge>` — dig.\n"
        )
        grounding = _grounding_rules_of(self._document(step4))
        with self.assertRaises(AssertionError):
            _assert_forbids_interactive_launch(grounding)

    def test_rejects_guidance_that_is_only_in_step5(self):
        step5 = (
            "Never launch an interpreter in interactive mode; use `python3 -c`, "
            "a script file, or `python3 - <<EOF`.\n"
        )
        bullet = (
            "- `<grounding_rules>` — findings must cite file/line.\n"
            "- `<dig_deeper_nudge>` — dig.\n"
        )
        grounding = _grounding_rules_of(self._document(bullet, step5))
        with self.assertRaises(AssertionError):
            _assert_forbids_interactive_launch(grounding)

    def test_rejects_a_rule_that_omits_one_alternative(self):
        bullet = (
            "- `<grounding_rules>` — Never launch an interpreter in interactive "
            "mode (such as `python3 -i`, `bash -i`); use `python3 -c`.\n"
            "- `<dig_deeper_nudge>` — dig.\n"
        )
        grounding = _grounding_rules_of(self._document(bullet))
        with self.assertRaises(AssertionError):
            _assert_names_all_alternatives(grounding)

    def test_missing_step4_heading_is_an_error(self):
        with self.assertRaises(AssertionError):
            _step4_section("# Title\n\n## Step 5: Execute Codex\n\nbody\n")

    def test_missing_grounding_bullet_is_an_error(self):
        with self.assertRaises(AssertionError):
            _grounding_rules_of(
                self._document("- `<task>` — x.\n- `<dig_deeper_nudge>` — dig.\n")
            )

    def test_step4_section_ends_at_the_next_heading(self):
        text = self._document(
            self.GOOD_BULLET, "Never in interactive mode `python3 -c`.\n"
        )
        section = _step4_section(text)
        self.assertIn("<grounding_rules>", section)
        self.assertNotIn("Step 5", section)
        self.assertNotIn("Run the wrapper", section)


if __name__ == "__main__":
    unittest.main()
