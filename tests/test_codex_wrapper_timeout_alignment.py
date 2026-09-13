"""Structural assertions for task0002: timeout nesting and caller-side doc
alignment.

See feature-docs/codex-wrapper-fallback-removal/tasks/task0002.md for the
acceptance criteria this module proves:

- AC-1 (FR4): both plugins' codex-cli.yaml files report a wrapper timeout of
  540 seconds, read as a key lookup -- never a whole-file substring match,
  so an unrelated occurrence of the number cannot satisfy it.
- AC-2 (FR4): all three invocation sites -- both reviewer prompts' Step 5
  and the consultation procedure's wrapper-invocation step -- state a
  Bash-tool timeout of 600000 milliseconds, each scoped to its own section
  so one site satisfying the assertion cannot cover for another.
- AC-3 (FR4, NFR1): the nesting relation (wrapper seconds * 1000 strictly
  less than caller milliseconds) is asserted between the two values read
  in AC-1 and AC-2 -- never as two independent literals -- so a future edit
  that moves one side without the other fails here.
- AC-4 (NFR6): the fenced wrapper-invocation command in each reviewer
  prompt is unchanged. The byte-level guarantee itself is
  tests/test_codex_reviewer_temp_file_isolation.py's job, run unmodified
  (Test Notes); this module adds a companion positive presence check.
- AC-7 (FR5): em-review/scripts/run_codex_exec.sh is not modified by this
  task; a positive structural check (IMPLEMENTATION.md D6) proves it still
  carries a single external launch, no fallback marker prefix, and no
  proxy-profile selection anywhere in its text.
- AC-8 (NFR5): this module imports only the standard library.

Per the Non-vacuity convention (IMPLEMENTATION.md), every matcher below has
a companion in TestValidationDetectsRegressions proving it fails
meaningfully against forged input.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EM_WORKFLOW_CONFIG = os.path.join(
    REPO_ROOT, "em-workflow", "references", "codex-cli.yaml"
)
EM_REVIEW_CONFIG = os.path.join(
    REPO_ROOT, "em-review", "references", "codex-cli.yaml"
)
EM_WORKFLOW_AGENT = os.path.join(
    REPO_ROOT, "em-workflow", "agents", "codex-reviewer.md"
)
EM_REVIEW_AGENT = os.path.join(REPO_ROOT, "em-review", "agents", "codex-reviewer.md")
QUESTION_RESOLUTION_DOC = os.path.join(
    REPO_ROOT, "em-workflow", "references", "question-resolution.md"
)
EM_REVIEW_WRAPPER_SCRIPT = os.path.join(
    REPO_ROOT, "em-review", "scripts", "run_codex_exec.sh"
)

# Byte-identical to the fenced invocation line inside each reviewer prompt's
# Step 5 (IMPLEMENTATION.md "Byte-identical invocation lines"; the same
# literal test_codex_reviewer_temp_file_isolation.py pins).
WRAPPER_INVOCATION_LINE = (
    '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C '
    '"{project_root}" --output-schema "$SCHEMA" "$PROMPT"'
)

STEP5_START = "## Step 5: Execute Codex"
STEP6_END = "## Step 6: Parse and return"

WRAPPER_INVOCATION_START = "2. **Wrapper invocation.**"
ONE_TURN_PER_CALL_END = "3. **One turn per call.**"

TIMEOUT_KEY_PATTERN = re.compile(r"^timeout:\s*(\d+)\s*$", re.MULTILINE)
BASH_TIMEOUT_MS_PATTERN = re.compile(r"timeout of (\d+) milliseconds")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_config_timeout_seconds(config_text, config_name):
    """Key lookup on the `timeout:` YAML key's own value line -- mirrors the
    parse `run_codex_exec.sh`'s own `parse_yaml_value()` shell function
    performs -- never a whole-file substring match on the number."""
    match = TIMEOUT_KEY_PATTERN.search(config_text)
    if not match:
        raise AssertionError(
            f"{config_name}: no `timeout:` key found in codex-cli.yaml"
        )
    return int(match.group(1))


def _extract_section(text, start_marker, end_marker, label):
    if start_marker not in text:
        raise AssertionError(f"{label}: missing start marker {start_marker!r}")
    if end_marker not in text:
        raise AssertionError(f"{label}: missing end marker {end_marker!r}")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _find_declared_bash_timeout_ms(section_text, site_name):
    """Scoped to the caller's own section: a Bash-tool timeout stated in
    prose as "timeout of <N> milliseconds", never a shell construct inside
    a fenced command (Design: restating it inside the fence would be wrong
    as well as breaking the byte-level pin)."""
    match = BASH_TIMEOUT_MS_PATTERN.search(section_text)
    if not match:
        raise AssertionError(
            f"{site_name}: no Bash-tool timeout declared as 'timeout of "
            "<N> milliseconds' in its own section"
        )
    return int(match.group(1))


def _assert_wrapper_timeout_strictly_nested(wrapper_seconds, caller_ms, label):
    if not (wrapper_seconds * 1000 < caller_ms):
        raise AssertionError(
            f"{label}: wrapper timeout {wrapper_seconds}s * 1000 = "
            f"{wrapper_seconds * 1000}ms is not strictly less than the "
            f"caller's declared Bash-tool timeout {caller_ms}ms"
        )


def _strip_full_line_comments(script_text):
    """Drop lines that are entirely a `#` comment, so a prose mention of a
    shell construct inside a comment (e.g. "stdin is redirected so `codex
    exec` does not block...") cannot masquerade as the construct itself."""
    return "\n".join(
        line for line in script_text.splitlines() if not line.strip().startswith("#")
    )


def _assert_single_external_launch_no_fallback_markers(script_text, label):
    """AC-7 / IMPLEMENTATION.md D6 positive side: exactly one external
    launch, no fallback marker prefix, no proxy-profile selection --
    scoped to non-comment lines only."""
    code_text = _strip_full_line_comments(script_text)
    launch_count = code_text.count("codex exec")
    if launch_count != 1:
        raise AssertionError(
            f"{label}: expected exactly one 'codex exec' launch, found "
            f"{launch_count}"
        )
    if "CODEX_FALLBACK" in code_text:
        raise AssertionError(f"{label}: fallback marker prefix present")
    if re.search(r"-p\s+litellm", code_text):
        raise AssertionError(f"{label}: proxy-profile selection present")


class TestConfigTimeoutIsWrapperValue(unittest.TestCase):
    """AC-1 (FR4): both plugins' codex-cli.yaml report a wrapper timeout of
    540 seconds, read as a key lookup."""

    def test_em_workflow_config_timeout_is_540(self):
        text = _read(EM_WORKFLOW_CONFIG)
        self.assertEqual(_parse_config_timeout_seconds(text, "em-workflow"), 540)

    def test_em_review_config_timeout_is_540(self):
        text = _read(EM_REVIEW_CONFIG)
        self.assertEqual(_parse_config_timeout_seconds(text, "em-review"), 540)


class TestBashToolTimeoutDeclaredAtEachInvocationSite(unittest.TestCase):
    """AC-2 (FR4): all three invocation sites each declare a Bash-tool
    timeout of 600000 milliseconds, scoped to their own section."""

    def test_em_workflow_step5_declares_600000ms(self):
        section = _extract_section(
            _read(EM_WORKFLOW_AGENT), STEP5_START, STEP6_END, "em-workflow Step 5"
        )
        self.assertEqual(
            _find_declared_bash_timeout_ms(section, "em-workflow Step 5"), 600000
        )

    def test_em_review_step5_declares_600000ms(self):
        section = _extract_section(
            _read(EM_REVIEW_AGENT), STEP5_START, STEP6_END, "em-review Step 5"
        )
        self.assertEqual(
            _find_declared_bash_timeout_ms(section, "em-review Step 5"), 600000
        )

    def test_question_resolution_wrapper_invocation_declares_600000ms(self):
        section = _extract_section(
            _read(QUESTION_RESOLUTION_DOC),
            WRAPPER_INVOCATION_START,
            ONE_TURN_PER_CALL_END,
            "question-resolution.md Wrapper invocation step",
        )
        self.assertEqual(
            _find_declared_bash_timeout_ms(
                section, "question-resolution.md Wrapper invocation step"
            ),
            600000,
        )


class TestTimeoutNestingRelation(unittest.TestCase):
    """AC-3 (FR4, NFR1): wrapper seconds * 1000 is strictly less than the
    declared Bash-tool timeout in milliseconds, asserted as a relation
    between the values read from the files -- never as two independent
    literals."""

    def test_em_workflow_nesting_holds(self):
        wrapper_seconds = _parse_config_timeout_seconds(
            _read(EM_WORKFLOW_CONFIG), "em-workflow"
        )
        section = _extract_section(
            _read(EM_WORKFLOW_AGENT), STEP5_START, STEP6_END, "em-workflow Step 5"
        )
        caller_ms = _find_declared_bash_timeout_ms(section, "em-workflow Step 5")
        _assert_wrapper_timeout_strictly_nested(wrapper_seconds, caller_ms, "em-workflow")

    def test_em_review_nesting_holds(self):
        wrapper_seconds = _parse_config_timeout_seconds(
            _read(EM_REVIEW_CONFIG), "em-review"
        )
        section = _extract_section(
            _read(EM_REVIEW_AGENT), STEP5_START, STEP6_END, "em-review Step 5"
        )
        caller_ms = _find_declared_bash_timeout_ms(section, "em-review Step 5")
        _assert_wrapper_timeout_strictly_nested(wrapper_seconds, caller_ms, "em-review")

    def test_question_resolution_wrapper_invocation_nesting_holds(self):
        # The consultation procedure calls the em-workflow wrapper directly
        # (references/question-resolution.md), so it nests against the
        # em-workflow configuration value.
        wrapper_seconds = _parse_config_timeout_seconds(
            _read(EM_WORKFLOW_CONFIG), "em-workflow"
        )
        section = _extract_section(
            _read(QUESTION_RESOLUTION_DOC),
            WRAPPER_INVOCATION_START,
            ONE_TURN_PER_CALL_END,
            "question-resolution.md Wrapper invocation step",
        )
        caller_ms = _find_declared_bash_timeout_ms(
            section, "question-resolution.md Wrapper invocation step"
        )
        _assert_wrapper_timeout_strictly_nested(
            wrapper_seconds, caller_ms, "question-resolution.md"
        )


class TestFencedInvocationLinesUnchanged(unittest.TestCase):
    """AC-4 (NFR6): the fenced wrapper-invocation command in each reviewer
    prompt is byte-for-byte what it was before this task. The full
    byte-level guarantee is delegated to
    tests/test_codex_reviewer_temp_file_isolation.py (run unmodified, per
    Test Notes); these are a companion positive presence check."""

    def test_em_workflow_invocation_line_present(self):
        self.assertIn(WRAPPER_INVOCATION_LINE, _read(EM_WORKFLOW_AGENT))

    def test_em_review_invocation_line_present(self):
        self.assertIn(WRAPPER_INVOCATION_LINE, _read(EM_REVIEW_AGENT))


class TestEmReviewWrapperUntouched(unittest.TestCase):
    """AC-7 (FR5): em-review/scripts/run_codex_exec.sh is not modified by
    this task; positive structural proof that it still carries a single
    external launch, no fallback marker prefix, and no proxy-profile
    selection anywhere in its text (IMPLEMENTATION.md D6, positive side of
    the em-review no-change claim)."""

    def test_single_external_launch_no_fallback_markers_no_proxy_profile(self):
        text = _read(EM_REVIEW_WRAPPER_SCRIPT)
        _assert_single_external_launch_no_fallback_markers(text, "em-review wrapper")


class TestValidationDetectsRegressions(unittest.TestCase):
    """Non-vacuity companion (IMPLEMENTATION.md Conventions, Test Notes):
    every matcher above fails meaningfully against forged input."""

    def test_config_timeout_key_lookup_rejects_absent_key(self):
        forged = "# note: issue 540 was fixed\nother_key: 540\n"
        with self.assertRaises(AssertionError):
            _parse_config_timeout_seconds(forged, "forged")

    def test_config_timeout_key_lookup_is_a_key_not_a_substring_match(self):
        # A file with the target VALUE attached to comment text (not the
        # `timeout:` key) must not let that unrelated occurrence satisfy a
        # check for 540 -- proves the parser reads the key, never any
        # occurrence of the digits.
        forged = "timeout: 600\n# see comment referencing 540 elsewhere\n"
        self.assertEqual(_parse_config_timeout_seconds(forged, "forged"), 600)

    def test_section_extraction_rejects_missing_markers(self):
        with self.assertRaises(AssertionError):
            _extract_section("no headings here", "## Step 5", "## Step 6", "forged")

    def test_bash_timeout_ms_lookup_rejects_absent_declaration(self):
        with self.assertRaises(AssertionError):
            _find_declared_bash_timeout_ms(
                "Always readonly mode. No timeout stated here.", "forged"
            )

    def test_bash_timeout_ms_lookup_rejects_shell_construct_phrasing(self):
        # Design: restating the caller timeout as a shell construct inside
        # the fence (rather than the required prose phrase) must not
        # satisfy the matcher.
        with self.assertRaises(AssertionError):
            _find_declared_bash_timeout_ms("timeout 600000 codex exec ...", "forged")

    def test_nesting_relation_rejects_equal_values(self):
        with self.assertRaises(AssertionError):
            _assert_wrapper_timeout_strictly_nested(600, 600000, "forged")

    def test_nesting_relation_rejects_wrapper_side_exceeding_caller(self):
        with self.assertRaises(AssertionError):
            _assert_wrapper_timeout_strictly_nested(601, 600000, "forged")

    def test_nesting_relation_passes_for_the_real_margin(self):
        # Sanity check: the actual configured pair (540s / 600000ms) passes.
        _assert_wrapper_timeout_strictly_nested(540, 600000, "sanity")

    def test_single_launch_check_rejects_a_second_launch(self):
        forged = "codex exec ...\ncodex exec ...\n"
        with self.assertRaises(AssertionError):
            _assert_single_external_launch_no_fallback_markers(forged, "forged")

    def test_single_launch_check_ignores_comment_only_mentions(self):
        # A prose mention of "codex exec" inside a full-line `#` comment
        # (e.g. explaining stdin redirection) must not be counted as a
        # second launch alongside the real invocation.
        forged = (
            "# stdin is redirected so `codex exec` does not block\n"
            "timeout 540 codex exec --color never\n"
        )
        _assert_single_external_launch_no_fallback_markers(forged, "forged")

    def test_single_launch_check_rejects_fallback_marker(self):
        forged = "codex exec ...\necho CODEX_FALLBACK: entry 2 answered\n"
        with self.assertRaises(AssertionError):
            _assert_single_external_launch_no_fallback_markers(forged, "forged")

    def test_single_launch_check_rejects_proxy_profile_selection(self):
        forged = "codex exec -p litellm -m vertex-glm-5.2 ...\n"
        with self.assertRaises(AssertionError):
            _assert_single_external_launch_no_fallback_markers(forged, "forged")

    def test_single_launch_check_passes_for_the_real_script(self):
        _assert_single_external_launch_no_fallback_markers(
            _read(EM_REVIEW_WRAPPER_SCRIPT), "em-review wrapper"
        )


if __name__ == "__main__":
    unittest.main()
