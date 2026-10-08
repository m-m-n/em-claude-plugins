"""Tests for task0002 (security-review-repro-steps): the reproduction
instructions carried by the review-security skills and the codex-reviewer
briefs of both plugins.

Covers task0002 Acceptance Criteria
(feature-docs/security-review-repro-steps/tasks/task0002.md):

- AC-1: both `review-security/SKILL.md` files contain a line exactly
  `## reproduction` that appears after the `## category` heading, and that
  section instructs writing, for each security finding, reproduction steps
  or an equivalent confirmation method into `reproduction`, naming the
  input, the path to the vulnerable code and the observable result.
- AC-2: that section states `reproduction` is null only when neither steps
  nor a confirmation method can be given.
- AC-3: in each skill, all text before the `## reproduction` line is
  byte-identical to its pre-change content, and the `## reproduction`
  section text is identical between the two plugins.
  `tests/test_threat_model_review_security.py` is not edited by this task;
  that it still passes is verified by running the full suite.
- AC-4: in both `codex-reviewer.md` files, Step 2 includes the skill's
  `## reproduction` section in the perspective brief when present, and
  Step 4's `<task>` bullet states that the reproduction instructions are
  part of the prompt.
- AC-5: in both `codex-reviewer.md` files, the frontmatter, the description,
  the opening body sentence and every step other than Steps 2 and 4 are
  byte-identical to their pre-change content, and every pre-change sentence
  of Steps 2 and 4 survives. The em-workflow codex-reviewer step digest in
  `tests/test_reviewer_roles_protocol.py` is replaced in place there; the
  existing codex-reviewer tests are not edited by this task.
- AC-6: this module imports the standard library only.

Per tdd-testing's "search existing tests before declaring none exist": the
test directory was searched by both path and basename for
`review-security/SKILL.md` and `codex-reviewer.md`. The modules that read
those files are `tests/test_threat_model_review_security.py`,
`tests/test_sca_axis_skill_and_version.py`,
`tests/test_reviewers_primary_chains.py`,
`tests/test_reviewer_roles_protocol.py`,
`tests/test_codex_reviewer_temp_file_isolation.py`,
`tests/test_codex_reviewer_interactive_guidance.py`,
`tests/test_codex_wrapper_timeout_alignment.py` and
`tests/test_threat_model_reviewer_inputs.py`. None of them asserts a
`reproduction` instruction, so no existing test covers AC-1 to AC-5.

Conventions follow tests/test_reviewer_roles_protocol.py: files are located
relative to this module, byte-identity is checked against sha256 digests
computed once from the pre-edit files, phrase checks are
whitespace-normalized and scoped to the section they concern, and every
matcher has a negative proof that a forged input fails.
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGINS = ("em-workflow", "em-review")

SKILL_PATHS = {
    plugin: REPO_ROOT / plugin / "skills" / "review-security" / "SKILL.md"
    for plugin in PLUGINS
}
AGENT_PATHS = {
    plugin: REPO_ROOT / plugin / "agents" / "codex-reviewer.md"
    for plugin in PLUGINS
}

REPRODUCTION_HEADING_RE = re.compile(r"^## reproduction$", re.MULTILINE)
CATEGORY_HEADING_RE = re.compile(r"^## category$", re.MULTILINE)
ANY_SECTION_HEADING_RE = re.compile(r"^## ", re.MULTILINE)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapse whitespace runs (markdown's ~79-column wraps included) to a
    single space and strip the ends."""
    return re.sub(r"\s+", " ", text).strip()


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract(text, start_marker, end_marker, label):
    """Return text[start_marker:end_marker) (end_marker None = end of file),
    raising AssertionError naming `label` when an anchor is missing."""
    if start_marker not in text:
        raise AssertionError(f"{label}: missing start marker {start_marker!r}")
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    if end_marker not in text[start:]:
        raise AssertionError(f"{label}: missing end marker {end_marker!r}")
    return text[start : text.index(end_marker, start)]


def _assert_phrases_present(normalized_text, phrases, label):
    missing = [p for p in phrases if p not in normalized_text]
    if missing:
        raise AssertionError(f"{label}: missing phrase(s) {missing!r}")


def _assert_digest(text, expected_sha256, label):
    actual = _sha256(text)
    if actual != expected_sha256:
        raise AssertionError(
            f"{label}: byte content changed "
            f"(expected sha256 {expected_sha256}, got {actual})"
        )


# ---------------------------------------------------------------------------
# Skill side (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------

# Digest of each skill file's complete pre-change content, computed once from
# the pre-edit files. The new section is appended after one blank line, so
# the text before the `## reproduction` line is the pre-change content plus
# that one separating newline.
SKILL_PRE_CHANGE_SHA256 = {
    "em-workflow": "eea2fc57de91f03c6fffefa4341c3d53e8c957d0458a8119d8125e766f43b596",
    "em-review": "d29ed16d0ece2cd06966bae7342135fecee034b06f1749f50e46dede1132943a",
}

# AC-1: what the section must instruct.
REPRODUCTION_INSTRUCTION_PHRASES = [
    "every security finding",
    "`reproduction`",
    "steps that reproduce it",
    "equivalent confirmation method",
    "the input",
    "the path by which that input reaches the vulnerable code",
    "the observable result",
]

# AC-2: when null is allowed.
REPRODUCTION_NULL_RULE_PHRASES = [
    "`reproduction` is null only when",
    "neither steps nor a confirmation method can be given",
]


def _reproduction_section(text, label):
    """Return (start_index, section_text) of the one `## reproduction` line
    through end of file."""
    matches = list(REPRODUCTION_HEADING_RE.finditer(text))
    if len(matches) != 1:
        raise AssertionError(
            f"{label}: expected exactly one line `## reproduction`, "
            f"found {len(matches)}"
        )
    start = matches[0].start()
    return start, text[start:]


def _assert_section_after_category_and_last(text, label):
    repro_start, section = _reproduction_section(text, label)
    category = CATEGORY_HEADING_RE.search(text)
    if category is None:
        raise AssertionError(f"{label}: no `## category` heading line")
    if category.start() >= repro_start:
        raise AssertionError(
            f"{label}: `## reproduction` does not appear after `## category`"
        )
    later = ANY_SECTION_HEADING_RE.findall(section[len("## reproduction") :])
    if later:
        raise AssertionError(
            f"{label}: `## reproduction` is not the last section of the file"
        )


def _assert_instruction(text, label):
    _, section = _reproduction_section(text, label)
    _assert_phrases_present(
        _normalize(section), REPRODUCTION_INSTRUCTION_PHRASES, label
    )


def _assert_null_rule(text, label):
    _, section = _reproduction_section(text, label)
    _assert_phrases_present(
        _normalize(section), REPRODUCTION_NULL_RULE_PHRASES, label
    )


def _assert_text_before_section_unchanged(text, expected_sha256, label):
    repro_start, _ = _reproduction_section(text, label)
    prefix = text[:repro_start]
    if not prefix.endswith("\n\n"):
        raise AssertionError(
            f"{label}: `## reproduction` must follow exactly one blank line"
        )
    _assert_digest(prefix[:-1], expected_sha256, f"{label} (text before section)")


def _assert_sections_identical(text_a, text_b, label):
    _, section_a = _reproduction_section(text_a, f"{label} [first]")
    _, section_b = _reproduction_section(text_b, f"{label} [second]")
    if section_a != section_b:
        raise AssertionError(f"{label}: the two `## reproduction` sections differ")


class TestSkillReproductionSection(unittest.TestCase):
    """AC-1, AC-2, AC-3 on the real review-security skills."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in SKILL_PATHS.items()}

    def test_ac1_section_follows_category_as_last_section(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_section_after_category_and_last(text, f"AC-1 {plugin}")

    def test_ac1_section_instructs_steps_input_path_and_observable_result(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_instruction(text, f"AC-1 {plugin}")

    def test_ac2_section_states_null_only_when_neither_can_be_given(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_null_rule(text, f"AC-2 {plugin}")

    def test_ac3_text_before_section_is_byte_identical_to_pre_change(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_text_before_section_unchanged(
                    text, SKILL_PRE_CHANGE_SHA256[plugin], f"AC-3 {plugin}"
                )

    def test_ac3_section_text_is_identical_between_plugins(self):
        _assert_sections_identical(
            self.texts["em-workflow"], self.texts["em-review"], "AC-3"
        )


# A well-formed section, held here as a fixture so the negative proofs below
# do not depend on the real files carrying the section.
REFERENCE_SECTION = (
    "## reproduction\n"
    "\n"
    "For every security finding, write into `reproduction` the steps that\n"
    "reproduce it, or an equivalent confirmation method. Name concretely the\n"
    "input, the path by which that input reaches the vulnerable code, and the\n"
    "observable result.\n"
    "\n"
    "`reproduction` is null only when neither steps nor a confirmation method\n"
    "can be given.\n"
)


def _text_before_section(text):
    """The skill text that precedes the `## reproduction` line, or the whole
    text plus the separating blank line when the section is not there."""
    match = REPRODUCTION_HEADING_RE.search(text)
    return text[: match.start()] if match else text + "\n"


class TestSkillMatchersRejectForgedInput(unittest.TestCase):
    """Negative proof: each skill-side matcher accepts a well-formed input
    and can fail on a forged one."""

    @classmethod
    def setUpClass(cls):
        cls.before = _text_before_section(_read(SKILL_PATHS["em-workflow"]))
        cls.good = cls.before + REFERENCE_SECTION

    def test_reference_input_passes_every_skill_matcher(self):
        _assert_section_after_category_and_last(self.good, "reference")
        _assert_instruction(self.good, "reference")
        _assert_null_rule(self.good, "reference")
        _assert_text_before_section_unchanged(
            self.good, SKILL_PRE_CHANGE_SHA256["em-workflow"], "reference"
        )
        _assert_sections_identical(self.good, self.good, "reference")

    def test_section_placed_before_category_fails_ac1(self):
        category_at = CATEGORY_HEADING_RE.search(self.before).start()
        forged = (
            self.before[:category_at]
            + REFERENCE_SECTION
            + "\n"
            + self.before[category_at:]
        )
        with self.assertRaises(AssertionError):
            _assert_section_after_category_and_last(forged, "forged order")

    def test_section_followed_by_another_section_fails_ac1(self):
        forged = self.good + "\n## trailing\n\nmore\n"
        with self.assertRaises(AssertionError):
            _assert_section_after_category_and_last(forged, "forged trailing")

    def test_wrong_case_heading_fails_ac1(self):
        forged = self.good.replace("## reproduction", "## Reproduction")
        with self.assertRaises(AssertionError):
            _assert_instruction(forged, "forged heading case")

    def test_section_without_observable_result_fails_ac1(self):
        forged = self.good.replace("observable result", "outcome")
        with self.assertRaises(AssertionError):
            _assert_instruction(forged, "forged instruction")

    def test_section_that_allows_null_freely_fails_ac2(self):
        forged = self.before + (
            "## reproduction\n\nFor every security finding, `reproduction` "
            "may be null whenever you are unsure.\n"
        )
        with self.assertRaises(AssertionError):
            _assert_null_rule(forged, "forged null rule")

    def test_edited_text_before_section_fails_ac3(self):
        forged = self.good.replace("Every finding MUST", "Every finding SHOULD")
        self.assertNotEqual(forged, self.good)
        with self.assertRaises(AssertionError):
            _assert_text_before_section_unchanged(
                forged, SKILL_PRE_CHANGE_SHA256["em-workflow"], "forged prefix"
            )

    def test_missing_separating_blank_line_fails_ac3(self):
        forged = self.good.replace("\n\n## reproduction", "\n## reproduction")
        self.assertNotEqual(forged, self.good)
        with self.assertRaises(AssertionError):
            _assert_text_before_section_unchanged(
                forged, SKILL_PRE_CHANGE_SHA256["em-workflow"], "forged spacing"
            )

    def test_diverging_section_text_fails_ac3(self):
        forged_other = self.good.replace("observable result", "result")
        self.assertNotEqual(forged_other, self.good)
        with self.assertRaises(AssertionError):
            _assert_sections_identical(self.good, forged_other, "forged parity")


# ---------------------------------------------------------------------------
# Agent side (AC-4, AC-5)
# ---------------------------------------------------------------------------

STEP2_HEADING = "## Step 2: Load the perspective skill"
STEP3_HEADING = "## Step 3: Resolve the schema path"
STEP4_HEADING = "## Step 4: Build the Codex prompt (XML blocks per codex-prompting)"
TASK_BULLET_START = "- `<task>`"
CONTRACT_BULLET_START = "- `<structured_output_contract>`"
GROUNDING_BULLET_START = "- `<grounding_rules>`"
DIG_BULLET_START = "- `<dig_deeper_nudge>`"
TEMP_FILE_HEADING = "## Temp-file discipline (only if writing a file to disk)"

# Digests of the pre-change byte ranges that must not move, computed once
# from the pre-edit files:
#   head      start of file up to the Step 2 heading (frontmatter,
#             description, opening body sentence, Steps 0 and 1)
#   step3     Step 3 heading up to the Step 4 heading
#   step4pre  Step 4 heading up to the `<task>` bullet
#   step4rest the `<structured_output_contract>` bullet up to the
#             temp-file discipline heading
#   tail      temp-file discipline heading to end of file (incl. Steps 5, 6)
UNCHANGED_RANGE_SHA256 = {
    "em-workflow": {
        "head": "d4aff4b9a96cb810599698abaa2a1133ac2246c28b6fc21f3650f8f7042b355f",
        "step3": "c873b8184432641ebd4a9ccc2127376f5e1d74abe3c00b30cdf88c3954537813",
        "step4pre": "75339de2a62cd48e20a419e3487973c533ec9968a0a025cd1aceafd9192c3e00",
        "step4rest": "6b81b6ff0b1c177cc6d2f8c1cfab5f38330a285d49418204660b0f24f6f7e534",
        "tail": "78d59febbe3f0d2a982726a16a7aef3d1898a9878a046ff2753c0fa8e8866d3b",
    },
    "em-review": {
        "head": "56a5b35584c00ca959121a9a0168f6f699539a6da04446d1d53d442bff6eb7b7",
        "step3": "2d929f478b3b6cd316f42c347d7da7c2dbbebc72d9038f1dd684aa213898c366",
        "step4pre": "75339de2a62cd48e20a419e3487973c533ec9968a0a025cd1aceafd9192c3e00",
        "step4rest": "0c68d4eac8375e6ce0f58a9b68090a5fcead8c43babb0993a83c80951100df50",
        "tail": "724729d036c2d3ad73ea73205f9f3fc923eee840c91d6547de852b386b8bfbdc",
    },
}

# Every pre-change sentence of Step 2, in order. The new text may be added
# between them; none may be reworded or dropped.
STEP2_ORIGINAL_SENTENCES = [
    "Load `perspective_skill` with the Skill tool (fail-closed skip on "
    "failure, same as Step 0).",
    'Extract from it the perspective brief: the "What to flag" / '
    '"What NOT to flag" content.',
    "That brief becomes the `<task>` block below.",
]

# The pre-change `<task>` bullet, whitespace-normalized. The new text is
# appended after it; none of it may be reworded.
TASK_BULLET_ORIGINAL = {
    "em-workflow": (
        "- `<task>` — the perspective brief (flag / don't-flag lists), the "
        "severity floor (critical/high/medium only, no style nits), and the "
        "data-fetch instructions: review_mode, the EXACT pre-quoted "
        "`diff_cmd_quoted` to run verbatim (with the `git diff` retry rule), "
        "or the changed-files list to read in whole-codebase mode; the "
        "3-file investigation budget. When `threat_model_path` is supplied "
        "(security perspective only), include it inline as a path string "
        "for Codex to read inside its read-only sandbox, stated as outside "
        "the 3-file investigation budget; an unreadable file means the "
        "review continues and the summary says so."
    ),
    "em-review": (
        "- `<task>` — the perspective brief (flag / don't-flag lists), the "
        "severity floor (critical/high/medium only, no style nits), and the "
        "data-fetch instructions: review_mode, the EXACT pre-quoted "
        "`diff_cmd_quoted` to run verbatim (with the `git diff` retry rule), "
        "the changed-files list to read in whole-codebase mode, or in "
        "pr-diff mode the `diff_path` file to read (+ `git show "
        "{pr_head_sha}:<path>` for surrounding context — local object "
        "reads only, never the working tree, never the network); the "
        "3-file investigation budget."
    ),
}

# AC-4: Step 2 carries the skill's `## reproduction` section in the brief.
STEP2_REPRODUCTION_PHRASES = [
    "`## reproduction` section",
    "only the security skill does",
    "part of the brief",
]

# AC-4: Step 4's `<task>` bullet states the instructions are part of the
# prompt.
TASK_BULLET_REPRODUCTION_PHRASES = [
    "reproduction instructions",
    "part of this `<task>` block",
]


def _step2_section(text):
    return _extract(text, STEP2_HEADING, STEP3_HEADING, "Step 2 section")


def _task_bullet(text):
    step4 = _extract(text, STEP4_HEADING, TEMP_FILE_HEADING, "Step 4 section")
    return _extract(step4, TASK_BULLET_START, CONTRACT_BULLET_START, "<task> bullet")


def _assert_step2_reproduction(text, label):
    _assert_phrases_present(
        _normalize(_step2_section(text)), STEP2_REPRODUCTION_PHRASES, label
    )


def _assert_task_bullet_reproduction(text, label):
    _assert_phrases_present(
        _normalize(_task_bullet(text)), TASK_BULLET_REPRODUCTION_PHRASES, label
    )


def _assert_step2_original_sentences_survive(text, label):
    section = _normalize(_step2_section(text))
    cursor = 0
    for sentence in STEP2_ORIGINAL_SENTENCES:
        at = section.find(sentence, cursor)
        if at < 0:
            raise AssertionError(
                f"{label}: pre-change Step 2 sentence missing or out of "
                f"order: {sentence!r}"
            )
        cursor = at + len(sentence)


def _assert_task_bullet_original_is_prefix(text, plugin, label):
    bullet = _normalize(_task_bullet(text))
    if not bullet.startswith(TASK_BULLET_ORIGINAL[plugin]):
        raise AssertionError(
            f"{label}: the pre-change `<task>` bullet text is not preserved "
            f"as the start of the bullet"
        )


def _unchanged_ranges(text):
    return {
        "head": _extract_head(text),
        "step3": _extract(text, STEP3_HEADING, STEP4_HEADING, "Step 3 range"),
        "step4pre": _extract(text, STEP4_HEADING, TASK_BULLET_START, "Step 4 preamble"),
        "step4rest": _extract(
            text, CONTRACT_BULLET_START, TEMP_FILE_HEADING, "Step 4 remaining bullets"
        ),
        "tail": _extract(text, TEMP_FILE_HEADING, None, "temp-file section to EOF"),
    }


def _extract_head(text):
    if STEP2_HEADING not in text:
        raise AssertionError(f"head range: missing marker {STEP2_HEADING!r}")
    return text[: text.index(STEP2_HEADING)]


def _assert_unchanged_ranges(text, plugin, label):
    for name, section in _unchanged_ranges(text).items():
        _assert_digest(
            section, UNCHANGED_RANGE_SHA256[plugin][name], f"{label} [{name}]"
        )


class TestCodexReviewerBriefs(unittest.TestCase):
    """AC-4 and AC-5 on the real codex-reviewer agents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}

    def test_ac4_step2_includes_reproduction_section_in_brief(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_step2_reproduction(text, f"AC-4 Step 2 {plugin}")

    def test_ac4_task_bullet_states_instructions_are_part_of_prompt(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_task_bullet_reproduction(text, f"AC-4 <task> {plugin}")

    def test_ac5_unchanged_ranges_are_byte_identical(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_unchanged_ranges(text, plugin, f"AC-5 {plugin}")

    def test_ac5_every_pre_change_step2_sentence_survives_in_order(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_step2_original_sentences_survive(text, f"AC-5 Step 2 {plugin}")

    def test_ac5_pre_change_task_bullet_text_is_preserved(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_task_bullet_original_is_prefix(
                    text, plugin, f"AC-5 <task> {plugin}"
                )


class TestAgentMatchersRejectForgedInput(unittest.TestCase):
    """Negative proof: each agent-side matcher can fail, and the scoping
    keeps the same words elsewhere from satisfying it."""

    @classmethod
    def setUpClass(cls):
        cls.real = _read(AGENT_PATHS["em-workflow"])

    def test_step2_reproduction_words_only_in_step4_fail_ac4(self):
        step2 = _step2_section(self.real)
        forged_step2 = step2.replace("`## reproduction` section", "extra section")
        self.assertNotEqual(forged_step2, step2)
        forged = self.real.replace(step2, forged_step2)
        forged = forged.replace(
            DIG_BULLET_START,
            DIG_BULLET_START
            + " (`## reproduction` section, only the security skill does, "
            "part of the brief)",
        )
        self.assertIn("(`## reproduction` section", forged)
        with self.assertRaises(AssertionError):
            _assert_step2_reproduction(forged, "forged Step 2")

    def test_task_bullet_words_only_in_grounding_bullet_fail_ac4(self):
        bullet = _task_bullet(self.real)
        added_at = bullet.index("When the perspective brief includes")
        forged = self.real.replace(bullet, bullet[:added_at])
        self.assertNotEqual(forged, self.real)
        forged = forged.replace(
            GROUNDING_BULLET_START,
            GROUNDING_BULLET_START
            + " reproduction instructions are part of this `<task>` block;",
        )
        with self.assertRaises(AssertionError):
            _assert_task_bullet_reproduction(forged, "forged <task>")

    def test_edited_step3_fails_ac5(self):
        forged = self.real.replace("Prefer orchestrator-supplied", "Prefer the")
        with self.assertRaises(AssertionError):
            _assert_unchanged_ranges(forged, "em-workflow", "forged Step 3")

    def test_edited_frontmatter_fails_ac5(self):
        forged = self.real.replace("effort: medium", "effort: high", 1)
        with self.assertRaises(AssertionError):
            _assert_unchanged_ranges(forged, "em-workflow", "forged frontmatter")

    def test_edited_step4_remaining_bullet_fails_ac5(self):
        forged = self.real.replace(
            "check\n  the surrounding context", "skip\n  the surrounding context"
        )
        self.assertNotEqual(forged, self.real)
        with self.assertRaises(AssertionError):
            _assert_unchanged_ranges(forged, "em-workflow", "forged Step 4 rest")

    def test_reworded_step2_sentence_fails_ac5(self):
        forged = self.real.replace(
            "`<task>` block below.", "task block."
        )
        self.assertNotEqual(forged, self.real)
        with self.assertRaises(AssertionError):
            _assert_step2_original_sentences_survive(forged, "forged Step 2 reword")

    def test_reworded_task_bullet_fails_ac5(self):
        forged = self.real.replace(
            "(critical/high/medium only, no style nits)",
            "(critical/high only, no style nits)",
        )
        self.assertNotEqual(forged, self.real)
        with self.assertRaises(AssertionError):
            _assert_task_bullet_original_is_prefix(
                forged, "em-workflow", "forged <task> reword"
            )


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6: this module imports the standard library only."""

    def test_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and node.level == 0:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
