"""Tests for task0002 (wake-task-cleanup-script): Step I.2.b step 4 of
`em-workflow/references/implement-phase.md` calls the cleanup script
(IMPLEMENTATION.md C1) instead of spelling git commands, reads the script's
JSON (C2), and keeps the wording the SPEC pins.

Covers task0002 Acceptance Criteria
(feature-docs/wake-task-cleanup-script/tasks/task0002.md):

- AC-1 (FR4, TM-3, TS-8): the step 4 region holds exactly one fenced block,
  whose only line is the call line of C1; the region states that the script
  is resolved per Step I.0 step 4 and that, when it cannot be resolved,
  nothing is invoked and no other location (a path relative to the current
  directory included) is tried.
- AC-2 (FR4, TM-5, TS-8): no fenced-block line and no inline code span in
  the region starts with `git` followed by whitespace, and the region holds
  none of `git worktree remove`, `git branch` and `git -C`; the region
  states that no git command is run in place of the script on any outcome,
  forced or not, and that the reason texts are data.
- AC-3 (FR3, FR8, TS-8): the region states that the JSON is read and not
  only the exit status, that exit status 0 is also returned when something
  was kept or skipped, which branch fields are written into the wake phase's
  own report, and what is written on a non-zero exit.
- AC-4 (FR4, TS-8): the heading line, the failure rule (after whitespace
  normalization) and the opening of the Batch mode paragraph survive.
- AC-5 (NFR2, TM-4, TS-9): the call line extracted from the region, with
  its placeholders expanded to sample values, leaves no placeholder, `$` or
  brace behind and passes `destructive-guard.py` and
  `interpreter-mismatch-guard.py`, with `CLAUDE_BATCH` removed and set.

This module reads `em-workflow/references/implement-phase.md` and runs the
repository copies of `em-workflow/hooks/destructive-guard.py` and
`em-workflow/hooks/interpreter-mismatch-guard.py` as child processes. It does
not need `em-workflow/scripts/cleanup-task.py` to exist, does not run it,
writes no files, and does not import from, and is not imported by, any other
test module.

Prose assertions compare whitespace-normalized text; byte-identity
assertions (the call line, the Batch mode opening) compare the raw text. The
two are never mixed in one assertion. Every matcher asserting NEW wording is
paired with a negative proof against a verbatim pre-change copy of step 4,
captured from this task's base revision (commit
2d3d61fed9efa06dd45a7671e35480cf9d3b85aa) and never reconstructed, plus a
non-vacuity guard proving the copy is itself the old text.

Guard invocation: the current Python interpreter, the repository copy of the
guard, stdin = one JSON object with `tool_name` `Bash` and
`tool_input.command` set to the expanded call line (no `cwd` key). "Passes"
means exit status 0 and a verdict that is neither `ask` nor `deny` (`allow`
and no output both pass).

Sample values are the ones `tests/test_protocol_git_ops_pass_destructive_guard.py`
defines: `{root}` = `/home/user`, feature `some-feature`, task `task0001`,
integration worktree `{root}/.claude/worktrees/em-workflow/some-feature/integration`.
"""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
DESTRUCTIVE_GUARD_PATH = PLUGIN_ROOT / "hooks" / "destructive-guard.py"
INTERPRETER_GUARD_PATH = PLUGIN_ROOT / "hooks" / "interpreter-mismatch-guard.py"
GUARD_PATHS = {
    "destructive-guard.py": DESTRUCTIVE_GUARD_PATH,
    "interpreter-mismatch-guard.py": INTERPRETER_GUARD_PATH,
}

WAKE_HEADING = "### I.2.b: Wake phase"
FAILED_HEADING = "### I.2.c: Failed handling"
STEP4_HEADING_LINE = "4. **Clean up** every newly-merged task's worktree and branch:"
STEP5_START = "5. **Refill**:"

SCRIPT_PATH_IN_DOC = "${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py"
CALL_LINE = (
    f"python3 {SCRIPT_PATH_IN_DOC} "
    '--integration-worktree "{integration_worktree}" '
    "--feature {feature} --task {T}"
)

# Sample values (see the module docstring).
SAMPLE_ROOT = "/home/user"
SAMPLE_FEATURE = "some-feature"
SAMPLE_TASK = "task0001"
SAMPLE_INTEGRATION_WT = (
    f"{SAMPLE_ROOT}/.claude/worktrees/em-workflow/{SAMPLE_FEATURE}/integration"
)
SAMPLE_PLUGIN_ROOT = (
    f"{SAMPLE_ROOT}/.claude/plugins/cache/em-claude-plugins/em-workflow/1.2.3"
)

FAILURE_RULE = (
    "If this branch deletion fails, do NOT fall back to a forced deletion "
    "(`-D` / `--force`): leave the branch in place and write its name into "
    "this wake phase's own report. The task's status set in step 3 above is "
    "unaffected, and step 5 below proceeds as before."
)
BATCH_MODE_PARAGRAPH_OPEN = (
    "**Batch mode**: in a `--batch` run, this applies only when step 5 "
    "re-enters\nthe launch phase (I.2.a) and ends the turn again"
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse every whitespace run (line-wrap newlines included) to one
    space, so a prose assertion never depends on where a line wraps."""
    return re.sub(r"\s+", " ", text)


def _slice(text, start_anchor, end_anchor):
    start = text.index(start_anchor)
    end = text.index(end_anchor, start)
    return text[start:end]


def _step4_region(text):
    """The step 4 region, located inside the wake phase first so that an
    identical phrase elsewhere in the file cannot be picked up."""
    wake = _slice(text, WAKE_HEADING, FAILED_HEADING)
    return _slice(wake, STEP4_HEADING_LINE, STEP5_START)


# --- Fenced blocks, code spans, the call line --------------------------------

_FENCE_RE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_CODE_SPAN_RE = re.compile(r"`([^`]+)`", re.DOTALL)


def _fenced_blocks(region):
    """Each fenced block's body, as a list of its non-blank lines (stripped)."""
    return [
        [line.strip() for line in m.group(1).split("\n") if line.strip()]
        for m in _FENCE_RE.finditer(region)
    ]


def _fenced_lines(region):
    return [line for block in _fenced_blocks(region) for line in block]


def _inline_code_spans(region):
    """Inline code spans, outside fenced blocks (a fenced block's own triple
    backticks would otherwise read as single-backtick delimiters)."""
    masked = _FENCE_RE.sub(lambda m: " " * len(m.group(0)), region)
    return [_normalize_ws(m.group(1)).strip() for m in _CODE_SPAN_RE.finditer(masked)]


def _starts_with_git_command(text):
    return re.match(r"git\s", text) is not None


def _git_shaped_items(region):
    """Fenced-block lines and inline code spans that start with `git` and
    whitespace."""
    items = [line for line in _fenced_lines(region) if _starts_with_git_command(line)]
    items += [span for span in _inline_code_spans(region) if _starts_with_git_command(span)]
    return items


def _extract_call_line(region):
    """The one fenced-block line naming the cleanup script. Raises
    AssertionError naming the reason when the region has none or several."""
    lines = [line for line in _fenced_lines(region) if "cleanup-task.py" in line]
    if not lines:
        raise AssertionError("step 4 region has no call line naming cleanup-task.py")
    if len(lines) > 1:
        raise AssertionError(
            f"step 4 region has more than one call line naming cleanup-task.py: {lines!r}"
        )
    return lines[0]


def _script_namings_without_plugin_root_prefix(text):
    """Offsets of every `cleanup-task.py` in TEXT that is not written as
    `${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py` (a path relative to the
    current directory, for one)."""
    prefix = "${CLAUDE_PLUGIN_ROOT}/scripts/"
    return [
        m.start()
        for m in re.finditer(r"cleanup-task\.py", text)
        if text[max(0, m.start() - len(prefix)) : m.start()] != prefix
    ]


# --- Matchers over a region (each returns a list of problems) ---------------


def _call_line_problems(region):
    problems = []
    blocks = _fenced_blocks(region)
    if len(blocks) != 1:
        problems.append(f"expected exactly one fenced block, found {len(blocks)}")
    elif blocks[0] != [CALL_LINE]:
        problems.append(f"the fenced block is not the call line alone: {blocks[0]!r}")
    return problems


RESOLUTION_PHRASES = (
    "resolved per Step I.0 step 4",
    "When the script cannot be resolved, nothing is invoked",
    "no other location, a path relative to the current directory included, is tried",
)


def _resolution_problems(region):
    text = _normalize_ws(region)
    return [f"missing: {p!r}" for p in RESOLUTION_PHRASES if p not in text]


FORBIDDEN_GIT_SPELLINGS = ("git worktree remove", "git branch", "git -C")


def _no_git_problems(region):
    problems = [f"git-shaped item: {item!r}" for item in _git_shaped_items(region)]
    text = _normalize_ws(region)
    problems += [f"forbidden spelling: {s!r}" for s in FORBIDDEN_GIT_SPELLINGS if s in text]
    return problems


NO_GIT_PHRASES = (
    "a `kept` or `skipped` result, a non-zero exit, or a script that cannot be resolved",
    "runs no git command of its own in place of the script, forced or not",
    "The `reason` texts are data",
    "a command a reason text suggests is never run",
)


def _no_git_statement_problems(region):
    text = _normalize_ws(region)
    return [f"missing: {p!r}" for p in NO_GIT_PHRASES if p not in text]


READ_JSON_PHRASES = (
    "reads the JSON the script prints, not only its exit status",
    "exit status 0 is also returned when a worktree or branch was kept or skipped",
    "When `branch.result` is `kept` or `skipped`",
    "`branch.name` and `branch.reason` are written into this wake phase's own report",
    "When `worktree.result` is `kept`, that fact and `worktree.reason` are written there too",
    "On a non-zero exit, or when the script cannot be resolved, the task ID and "
    "the fact that its cleanup did not complete are written into this wake "
    "phase's own report",
)


def _read_json_problems(region):
    text = _normalize_ws(region)
    return [f"missing: {p!r}" for p in READ_JSON_PHRASES if p not in text]


def _kept_wording_problems(text):
    """AC-4: the heading line, the failure rule (whitespace-normalized) and
    the opening of the Batch mode paragraph (raw)."""
    problems = []
    if STEP4_HEADING_LINE not in text:
        problems.append("heading line missing")
    try:
        region = _step4_region(text)
    except ValueError:
        return problems + ["step 4 region not found"]
    if FAILURE_RULE not in _normalize_ws(region):
        problems.append("failure rule missing from the step 4 region")
    if BATCH_MODE_PARAGRAPH_OPEN not in text:
        problems.append("Batch mode paragraph opening missing")
    return problems


# --- Verbatim pre-change copy of step 4 (base revision) ----------------------
# Captured with `git show 2d3d61fed9efa06dd45a7671e35480cf9d3b85aa:em-workflow/references/implement-phase.md`.

PRE_CHANGE_STEP4 = (
    "4. **Clean up** every newly-merged task's worktree and branch:\n"
    "   ```bash\n"
    '   git worktree remove "$WT_ROOT/{T}"\n'
    '   git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"\n'
    "   # -d succeeds here: the integration worktree's HEAD is the integration\n"
    "   # branch, which already contains the task branch (its merge was\n"
    "   # verified with merge-base --is-ancestor in step 1).\n"
    "   ```\n"
    "   If this branch deletion fails, do NOT fall back to a forced deletion\n"
    "   (`-D` / `--force`): leave the branch in place and write its name into\n"
    "   this wake phase's own report. The task's status set in step 3 above is\n"
    "   unaffected, and step 5 below proceeds as before.\n"
)


# --- Expansion and guard invocation -----------------------------------------


def _expand(call_line):
    """`${CLAUDE_PLUGIN_ROOT}` first (it contains braces itself), then the
    three brace placeholders."""
    text = call_line.replace("${CLAUDE_PLUGIN_ROOT}", SAMPLE_PLUGIN_ROOT)
    text = text.replace("{integration_worktree}", SAMPLE_INTEGRATION_WT)
    text = text.replace("{feature}", SAMPLE_FEATURE)
    text = text.replace("{T}", SAMPLE_TASK)
    return text


def _assert_no_residue(expanded):
    for residue in ("$", "{", "}"):
        if residue in expanded:
            raise AssertionError(f"{residue!r} left behind in {expanded!r}")


def _guard_verdict(guard_path, command, batch):
    """'allow' / 'deny' / 'ask', '(silent)' when the guard prints nothing,
    or '(exit N)' when the guard itself fails."""
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)
    if batch:
        env["CLAUDE_BATCH"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(guard_path)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return "(exit %d)" % proc.returncode
    if not proc.stdout.strip():
        return "(silent)"
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def _passes(verdict):
    return verdict not in ("ask", "deny") and not verdict.startswith("(exit")


# --- AC-1 --------------------------------------------------------------------


class TestAC1CallLineAndResolution(unittest.TestCase):
    """AC-1 (FR4, TM-3, TS-8)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()
        cls.region = _step4_region(cls.text)

    def test_region_holds_the_call_line_as_the_only_line_of_one_fenced_block(self):
        self.assertEqual(_call_line_problems(self.region), [])

    def test_call_line_is_the_only_line_naming_the_script_in_a_fenced_block(self):
        self.assertEqual(_extract_call_line(self.region), CALL_LINE)

    def test_script_resolved_per_step_i0_step4_and_no_other_location_is_tried(self):
        self.assertEqual(_resolution_problems(self.region), [])

    def test_script_is_never_named_by_a_path_relative_to_the_current_directory(self):
        self.assertIn("cleanup-task.py", self.text)
        self.assertEqual(_script_namings_without_plugin_root_prefix(self.text), [])

    def test_trusted_root_search_literals_are_not_restated_in_the_region(self):
        for literal in ("$HOME/.claude/plugins", "$HOME/.claude/skills", "*/em-workflow/*/scripts/*"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, self.region)

    def test_negative_proof_pre_change_step4_fails_every_ac1_matcher(self):
        self.assertNotEqual(_call_line_problems(PRE_CHANGE_STEP4), [])
        self.assertEqual(len(_resolution_problems(PRE_CHANGE_STEP4)), len(RESOLUTION_PHRASES))

    def test_negative_proof_a_script_named_relative_to_the_cwd_is_detected(self):
        forged = self.text.replace(SCRIPT_PATH_IN_DOC, "em-workflow/scripts/cleanup-task.py", 1)
        self.assertNotEqual(_script_namings_without_plugin_root_prefix(forged), [])

    def test_negative_proof_a_second_fenced_block_is_detected(self):
        forged = self.region + "   ```bash\n   echo done\n   ```\n"
        self.assertNotEqual(_call_line_problems(forged), [])

    def test_negative_proof_an_extra_line_next_to_the_call_line_is_detected(self):
        forged = self.region.replace(CALL_LINE, CALL_LINE + " | cat")
        self.assertNotEqual(_call_line_problems(forged), [])

    def test_negative_proof_pre_change_samples_are_the_old_text(self):
        self.assertIn('git worktree remove "$WT_ROOT/{T}"', PRE_CHANGE_STEP4)
        self.assertNotIn("cleanup-task.py", PRE_CHANGE_STEP4)


# --- AC-2 --------------------------------------------------------------------


class TestAC2NoGitCommandInTheRegion(unittest.TestCase):
    """AC-2 (FR4, TM-5, TS-8)."""

    @classmethod
    def setUpClass(cls):
        cls.region = _step4_region(_read())

    def test_no_git_shaped_line_or_code_span_and_no_forbidden_spelling(self):
        self.assertEqual(_no_git_problems(self.region), [])

    def test_region_states_no_git_command_replaces_the_script_on_any_outcome(self):
        self.assertEqual(_no_git_statement_problems(self.region), [])

    def test_negative_proof_pre_change_step4_is_git_shaped(self):
        problems = _no_git_problems(PRE_CHANGE_STEP4)
        self.assertTrue(any("git-shaped item" in p for p in problems), problems)
        self.assertTrue(any("forbidden spelling" in p for p in problems), problems)
        self.assertEqual(
            len(_no_git_statement_problems(PRE_CHANGE_STEP4)), len(NO_GIT_PHRASES)
        )

    def test_negative_proof_a_git_inline_code_span_is_detected(self):
        forged = self.region + "   Run `git branch -D {T}` instead.\n"
        self.assertNotEqual(_no_git_problems(forged), [])

    def test_negative_proof_a_git_line_in_a_fenced_block_is_detected(self):
        forged = self.region + "   ```bash\n   git status\n   ```\n"
        self.assertNotEqual(_no_git_problems(forged), [])

    def test_negative_proof_each_forbidden_spelling_is_detected_in_prose(self):
        for spelling in FORBIDDEN_GIT_SPELLINGS:
            with self.subTest(spelling=spelling):
                forged = self.region + f"   Never write {spelling} here.\n"
                self.assertNotEqual(_no_git_problems(forged), [])

    def test_negative_proof_removing_each_statement_phrase_is_detected(self):
        text = _normalize_ws(self.region)
        for phrase in NO_GIT_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotEqual(
                    _no_git_statement_problems(text.replace(phrase, "")), []
                )


# --- AC-3 --------------------------------------------------------------------


class TestAC3ReadsTheJsonAndReports(unittest.TestCase):
    """AC-3 (FR3, FR8, TS-8)."""

    @classmethod
    def setUpClass(cls):
        cls.region = _step4_region(_read())

    def test_region_states_what_is_read_and_what_is_reported(self):
        self.assertEqual(_read_json_problems(self.region), [])

    def test_negative_proof_pre_change_step4_states_none_of_it(self):
        self.assertEqual(
            len(_read_json_problems(PRE_CHANGE_STEP4)), len(READ_JSON_PHRASES)
        )

    def test_negative_proof_removing_each_phrase_is_detected(self):
        text = _normalize_ws(self.region)
        for phrase in READ_JSON_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotEqual(_read_json_problems(text.replace(phrase, "")), [])


# --- AC-4 --------------------------------------------------------------------


class TestAC4PinnedWordingStays(unittest.TestCase):
    """AC-4 (FR4, TS-8)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_heading_failure_rule_and_batch_mode_opening_are_present(self):
        self.assertEqual(_kept_wording_problems(self.text), [])

    def test_failure_rule_sits_inside_the_step4_region(self):
        self.assertIn(FAILURE_RULE, _normalize_ws(_step4_region(self.text)))

    def test_batch_mode_paragraph_follows_step5_outside_the_region(self):
        self.assertNotIn("**Batch mode**: in a `--batch` run, this applies only", _step4_region(self.text))
        self.assertGreater(
            self.text.index(BATCH_MODE_PARAGRAPH_OPEN), self.text.index(STEP5_START)
        )

    def test_negative_proof_each_pinned_item_is_detected_when_removed(self):
        forged_heading = self.text.replace(STEP4_HEADING_LINE, "4. **Clean up**:", 1)
        self.assertNotEqual(_kept_wording_problems(forged_heading), [])
        forged_rule = self.text.replace("do NOT fall back to a forced deletion", "may fall back", 1)
        self.assertNotEqual(_kept_wording_problems(forged_rule), [])
        forged_batch = self.text.replace(BATCH_MODE_PARAGRAPH_OPEN, "**Batch mode**: changed", 1)
        self.assertNotEqual(_kept_wording_problems(forged_batch), [])

    def test_pre_change_step4_carries_the_pinned_rule_too(self):
        # The pinned wording is the same before and after: only the new
        # statements are new, so the pre-change copy is a valid base here.
        self.assertIn(FAILURE_RULE, _normalize_ws(PRE_CHANGE_STEP4))
        self.assertIn(STEP4_HEADING_LINE, PRE_CHANGE_STEP4)


# --- AC-5 --------------------------------------------------------------------


class TestAC5CallLinePassesTheGuards(unittest.TestCase):
    """AC-5 (NFR2, TM-4, TS-9)."""

    @classmethod
    def setUpClass(cls):
        cls.region = _step4_region(_read())
        cls.expanded = _expand(_extract_call_line(cls.region))

    def test_expanded_call_line_leaves_no_placeholder_dollar_or_brace(self):
        _assert_no_residue(self.expanded)

    def test_expanded_call_line_has_the_expected_shape(self):
        self.assertEqual(
            self.expanded,
            f"python3 {SAMPLE_PLUGIN_ROOT}/scripts/cleanup-task.py "
            f'--integration-worktree "{SAMPLE_INTEGRATION_WT}" '
            f"--feature {SAMPLE_FEATURE} --task {SAMPLE_TASK}",
        )

    def test_call_line_passes_each_guard_without_and_with_claude_batch(self):
        for name, path in GUARD_PATHS.items():
            for batch in (False, True):
                with self.subTest(guard=name, claude_batch=batch):
                    verdict = _guard_verdict(path, self.expanded, batch)
                    self.assertTrue(
                        _passes(verdict),
                        f"{name} (CLAUDE_BATCH {'set' if batch else 'removed'}) "
                        f"judged {self.expanded!r}: {verdict}",
                    )

    def test_negative_proof_extraction_fails_naming_the_reason_with_no_call_line(self):
        with self.assertRaises(AssertionError) as ctx:
            _extract_call_line(PRE_CHANGE_STEP4)
        self.assertIn("no call line", str(ctx.exception))

    def test_negative_proof_extraction_fails_naming_the_reason_with_two_call_lines(self):
        forged = self.region + f"   ```bash\n   {CALL_LINE}\n   ```\n"
        with self.assertRaises(AssertionError) as ctx:
            _extract_call_line(forged)
        self.assertIn("more than one call line", str(ctx.exception))

    def test_negative_proof_an_unexpanded_placeholder_is_detected(self):
        for residue_line in (
            CALL_LINE,
            self.expanded + " {extra}",
            self.expanded + " $HOME",
        ):
            with self.subTest(line=residue_line):
                with self.assertRaises(AssertionError):
                    _assert_no_residue(residue_line)

    def test_negative_proof_expansion_order_leaves_no_brace_from_plugin_root(self):
        # `${CLAUDE_PLUGIN_ROOT}` carries braces itself: it is expanded as a
        # whole, so nothing of it survives.
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", self.expanded)

    def test_negative_proof_the_guard_check_rejects_a_forced_deletion(self):
        verdict = _guard_verdict(
            DESTRUCTIVE_GUARD_PATH, "git branch -D em-workflow/some-feature/task0001", False
        )
        self.assertFalse(_passes(verdict), verdict)

    def test_negative_proof_the_guard_check_rejects_a_script_run_through_a_shell(self):
        # An existing repository Python script run by `bash`: the one
        # verdict the interpreter-mismatch guard exists to return.
        command = f"bash {PLUGIN_ROOT / 'scripts' / 'merge-git.py'}"
        verdict = _guard_verdict(INTERPRETER_GUARD_PATH, command, False)
        self.assertFalse(_passes(verdict), verdict)

    def test_negative_proof_a_guard_failure_is_not_a_pass(self):
        self.assertFalse(_passes("(exit 1)"))


class TestModuleHygiene(unittest.TestCase):
    """This module writes no files and needs no cleanup script."""

    def test_module_writes_no_files(self):
        source = Path(__file__).read_text(encoding="utf-8")
        before = source[: source.index("class TestModuleHygiene")]
        for needle in ("write_text(", "write_bytes(", ".mkdir(", 'open(', "tempfile"):
            self.assertNotIn(needle, before)


if __name__ == "__main__":
    unittest.main()
