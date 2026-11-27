"""Tests for task0002 and task0004 (wake-task-cleanup-script): Step I.2.b
step 4 of `em-workflow/references/implement-phase.md` calls the cleanup script
(IMPLEMENTATION.md C1) instead of spelling git commands, reads the script's
JSON (C2), and keeps the wording the SPEC pins.

Call-line shape (C1). The one fenced line of step 4 is

    python3 {cleanup_script} --integration-worktree {integration_worktree} --feature {feature} --task {T}

The script is named only through `{cleanup_script}`, which stands for the
script's absolute path resolved per Step I.0 step 4. When the line runs,
`{cleanup_script}` is replaced by that resolved path and the other three
placeholders by the validated literal values, and each substituted value is
first escaped for the shell as one whole argument: single-quoted, an embedded
single quote written as close-quote, escaped quote, open-quote. No
placeholder, unescaped `$` or brace is left on the line that runs.

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

Covers task0004 Acceptance Criteria
(feature-docs/wake-task-cleanup-script/tasks/task0004.md), which align the
checks above to the call-line shape of C1:

- AC-1 (FR4, TM-3, TS-8): the call line is, byte for byte, the C1 line and
  is extracted as the fenced line whose first word is `python3` and that
  holds `{cleanup_script}` (TestAC1CallLineAndResolution).
- AC-2 (FR4, TM-3, TS-8): the resolution statements, six whitespace-
  normalized phrases of the current step 4 (TestAC1CallLineAndResolution).
- AC-3 (FR4, TM-3, TS-8): no occurrence of `cleanup-task.py` in the whole
  document is named by a relative path, and the call line holds none
  (TestAC1CallLineAndResolution).
- AC-4 (NFR2, TM-4, TS-9): the call line, expanded with escaped values for
  the sample set, the repository copy and the shell-special paths, leaves no
  placeholder and splits into the eight intended words
  (TestTask4AC4ExpansionYieldsTheEightIntendedWords).
- AC-5 (NFR2, TM-4, TS-9): every one of those expanded lines passes both
  guards (TestTask4AC5ExpandedLinesPassTheGuards).
- AC-6 (FR3, FR8, FR4, TM-5, TS-8, NFR3): the AC-2, AC-3 and AC-4 classes
  keep their assertions and every test name the task0002 and task0003
  records name stays.

This module reads `em-workflow/references/implement-phase.md` and runs the
repository copies of `em-workflow/hooks/destructive-guard.py` and
`em-workflow/hooks/interpreter-mismatch-guard.py` as child processes. It does
not need `em-workflow/scripts/cleanup-task.py` to exist (the repository copy
value set only uses its path as a string), does not run it, writes no files,
and does not import from, and is not imported by, any other test module.

Prose assertions compare whitespace-normalized text; byte-identity
assertions (the call line, the Batch mode opening) compare the raw text. The
two are never mixed in one assertion. Every matcher asserting NEW wording is
paired with a negative proof against a verbatim pre-change copy of step 4,
captured from task0002's base revision (commit
2d3d61fed9efa06dd45a7671e35480cf9d3b85aa) and never reconstructed, plus a
non-vacuity guard proving the copy is itself the old text.

Value sets of the expansion (AC-4, AC-5 of task0004). Sample values are the
ones `tests/test_protocol_git_ops_pass_destructive_guard.py` defines:
`{root}` = `/home/user`, feature `some-feature`, task `task0001`,
integration worktree
`{root}/.claude/worktrees/em-workflow/some-feature/integration`.

- the sample set: the script under the module's sample plugin root and the
  sample feature, task and integration worktree;
- the repository copy: the absolute path of `em-workflow/scripts/cleanup-task.py`
  in this repository, with the sample feature, task and integration worktree;
- shell-special paths: for the script path and for the integration worktree
  in turn, a value holding a space, a single quote, a double quote, a
  backtick, `$` (a variable form, a brace form, a command-substitution form),
  a newline, and every one of them together. The feature and task values stay
  the sample ones, since Step I.0 step 2 admits nothing else for them.

An expanded line is correct when no placeholder is left (nothing outside the
escaped values holds `$`, a brace) and splitting it by POSIX shell word rules
(standard library) yields exactly eight words: `python3`, the script path,
`--integration-worktree`, the integration worktree, `--feature`, the feature,
`--task`, the task, each value recovered exactly as given.

Guard invocation: the current Python interpreter, the repository copy of the
guard, stdin = one JSON object with `tool_name` `Bash` and
`tool_input.command` set to the expanded call line (no `cwd` key; a value
with a newline travels inside that JSON, never through a command line or a
file). "Passes" means exit status 0 and a verdict that is neither `ask` nor
`deny` (`allow` and no output both pass).
"""

import json
import os
import re
import shlex
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

SCRIPT_PLACEHOLDER = "{cleanup_script}"
PLACEHOLDERS = (SCRIPT_PLACEHOLDER, "{integration_worktree}", "{feature}", "{T}")
CALL_LINE = (
    "python3 {cleanup_script} --integration-worktree {integration_worktree} "
    "--feature {feature} --task {T}"
)
# The one spelling of the script path besides a bare file name that the
# document may use anywhere (Step I.0 step 4 resolves the script from it).
PLUGIN_ROOT_FORM_PREFIX = "${CLAUDE_PLUGIN_ROOT}/scripts/"
# The call line step 4 had before it named the script through a placeholder.
PLUGIN_ROOT_CALL_LINE = (
    f"python3 {PLUGIN_ROOT_FORM_PREFIX}cleanup-task.py "
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
SAMPLE_SCRIPT = f"{SAMPLE_PLUGIN_ROOT}/scripts/cleanup-task.py"
# The repository's own copy: only its path is used, as a string.
REPO_SCRIPT = str(PLUGIN_ROOT / "scripts" / "cleanup-task.py")

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
    """Each fenced block's body, as a list of its non-blank lines. Only the
    layout indentation is removed: the rest of a line is kept as written, so
    a comparison with the call line is byte for byte."""
    return [
        [line.lstrip() for line in m.group(1).split("\n") if line.strip()]
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


def _is_call_line_candidate(line):
    """A fenced-block line whose first word is `python3` and that holds
    `{cleanup_script}`."""
    words = line.split()
    return bool(words) and words[0] == "python3" and SCRIPT_PLACEHOLDER in line


def _extract_call_line(region):
    """The one fenced-block line that calls the cleanup script. Raises
    AssertionError naming the reason when the region has none or several."""
    lines = [line for line in _fenced_lines(region) if _is_call_line_candidate(line)]
    if not lines:
        raise AssertionError(
            "step 4 region has no call line (a fenced line whose first word is "
            f"python3 and that holds {SCRIPT_PLACEHOLDER})"
        )
    if len(lines) > 1:
        raise AssertionError(
            f"step 4 region has more than one call line holding {SCRIPT_PLACEHOLDER}: {lines!r}"
        )
    return lines[0]


def _relative_script_namings(text):
    """Offsets of every `cleanup-task.py` in TEXT that is named by a path
    relative to the current directory. Accepted: the occurrence written as
    `${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py`, and the bare file name
    (nothing path-like directly before it: no `/`, no backslash, so no `./`
    either). Every other occurrence is reported."""
    offsets = []
    for m in re.finditer(r"cleanup-task\.py", text):
        before = text[: m.start()]
        if before.endswith(PLUGIN_ROOT_FORM_PREFIX):
            continue
        if before.endswith(("/", "\\")):
            offsets.append(m.start())
    return offsets


def _script_name_in_fenced_line_problems(region):
    """The call line names the script only through `{cleanup_script}`: no
    fenced-block line of the region holds the file name."""
    return [
        f"fenced line holds cleanup-task.py: {line!r}"
        for line in _fenced_lines(region)
        if "cleanup-task.py" in line
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
    "the script's resolved absolute path (the whole path of `cleanup-task.py`) "
    "in place of `{cleanup_script}`",
    "Each substituted value is first escaped for the shell as one whole argument",
    "No placeholder, unescaped `$` or brace is left on the line that runs",
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


# --- Expansion, word check and guard invocation ------------------------------

_PLACEHOLDER_RE = re.compile(r"\{(cleanup_script|integration_worktree|feature|T)\}")


def _shell_escape(value):
    """The form step 4 states: the value single-quoted as one whole argument,
    an embedded single quote written as close-quote, escaped quote,
    open-quote."""
    return "'" + value.replace("'", "'\\''") + "'"


def _no_escape(value):
    return value


def _double_quote(value):
    return '"' + value + '"'


def _expand(
    call_line,
    script=SAMPLE_SCRIPT,
    integration_worktree=SAMPLE_INTEGRATION_WT,
    feature=SAMPLE_FEATURE,
    task=SAMPLE_TASK,
    escape=_shell_escape,
):
    """Replace `{cleanup_script}`, `{integration_worktree}`, `{feature}` and
    `{T}` with their values, each passed through ESCAPE. One pass over the
    line: a value that holds placeholder-looking text is never expanded again,
    so nothing of the script's own location (`${CLAUDE_PLUGIN_ROOT}` included)
    is left to the order of the replacements."""
    values = {
        "cleanup_script": escape(script),
        "integration_worktree": escape(integration_worktree),
        "feature": escape(feature),
        "T": escape(task),
    }
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], call_line)


def _escaped_values(script, integration_worktree):
    """The four values in the form step 4 states: the only text the residue
    check lets hold `$` and braces."""
    return [
        _shell_escape(v)
        for v in (script, integration_worktree, SAMPLE_FEATURE, SAMPLE_TASK)
    ]


def _expected_words(script, integration_worktree):
    return [
        "python3",
        script,
        "--integration-worktree",
        integration_worktree,
        "--feature",
        SAMPLE_FEATURE,
        "--task",
        SAMPLE_TASK,
    ]


def _residue_problems(expanded, escaped_values=()):
    """A placeholder, `$` or brace left outside the escaped values. The
    escaped values themselves may hold `$` and braces: they are quoted, so
    the shell reads them as literal text."""
    rest = expanded
    for value in sorted(escaped_values, key=len, reverse=True):
        rest = rest.replace(value, "")
    return [
        f"{residue!r} left behind outside the escaped values: {expanded!r}"
        for residue in ("$", "{", "}")
        if residue in rest
    ]


def _assert_no_residue(expanded, escaped_values=()):
    problems = _residue_problems(expanded, escaped_values)
    if problems:
        raise AssertionError("; ".join(problems))


def _word_problems(expanded, expected_words):
    """Split EXPANDED by POSIX shell word rules; the words must be exactly
    EXPECTED_WORDS (eight of them), each value recovered as given."""
    try:
        words = shlex.split(expanded)
    except ValueError as exc:
        return [f"not splittable into shell words ({exc}): {expanded!r}"]
    if len(words) != len(expected_words):
        return [f"{len(words)} words instead of {len(expected_words)}: {words!r}"]
    if words != expected_words:
        return [f"words differ from the values: {words!r} != {expected_words!r}"]
    return []


def _expansion_problems(call_line, script, integration_worktree, escape=_shell_escape):
    expanded = _expand(call_line, script, integration_worktree, escape=escape)
    return _residue_problems(
        expanded, _escaped_values(script, integration_worktree)
    ) + _word_problems(expanded, _expected_words(script, integration_worktree))


# One fragment per shell-special form; the plan's list, plus all of them at
# once. Each is placed in the project-root part of the script path and of the
# integration worktree in turn.
SPECIAL_FRAGMENTS = (
    ("a space", "with space"),
    ("a single quote", "it's"),
    ("a double quote", 'say "hi"'),
    ("a backtick", "back`tick"),
    ("a variable form of $", "$HOME"),
    ("a brace form of $", "${HOME}"),
    ("a command-substitution form of $", "$(whoami)"),
    ("a newline", "line\nbreak"),
    ("every one of them together", "it's \"a\" `b` $c ${d} $(e)\nf"),
)


def _value_sets():
    """(label, script path, integration worktree): the sample set, the
    repository copy and the shell-special paths."""
    sets = [
        ("sample set", SAMPLE_SCRIPT, SAMPLE_INTEGRATION_WT),
        ("repository copy", REPO_SCRIPT, SAMPLE_INTEGRATION_WT),
    ]
    for label, fragment in SPECIAL_FRAGMENTS:
        sets.append(
            (
                f"script path holding {label}",
                f"{SAMPLE_ROOT}/{fragment}/em-workflow/scripts/cleanup-task.py",
                SAMPLE_INTEGRATION_WT,
            )
        )
        sets.append(
            (
                f"integration worktree holding {label}",
                SAMPLE_SCRIPT,
                f"{SAMPLE_ROOT}/{fragment}/.claude/worktrees/em-workflow/"
                f"{SAMPLE_FEATURE}/integration",
            )
        )
    return sets


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


# --- AC-1 to AC-3 of task0004 / AC-1 of task0002 -----------------------------


class TestAC1CallLineAndResolution(unittest.TestCase):
    """AC-1 (FR4, TM-3, TS-8) of task0002; AC-1 to AC-3 of task0004."""

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
        self.assertEqual(_relative_script_namings(self.text), [])

    def test_call_line_names_the_script_only_through_its_placeholder(self):
        self.assertNotIn("cleanup-task.py", _extract_call_line(self.region))
        self.assertEqual(_script_name_in_fenced_line_problems(self.region), [])

    def test_trusted_root_search_literals_are_not_restated_in_the_region(self):
        for literal in ("$HOME/.claude/plugins", "$HOME/.claude/skills", "*/em-workflow/*/scripts/*"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, self.region)

    def test_negative_proof_pre_change_step4_fails_every_ac1_matcher(self):
        self.assertNotEqual(_call_line_problems(PRE_CHANGE_STEP4), [])
        self.assertEqual(len(_resolution_problems(PRE_CHANGE_STEP4)), len(RESOLUTION_PHRASES))

    def test_negative_proof_removing_each_resolution_phrase_is_detected(self):
        text = _normalize_ws(self.region)
        for phrase in RESOLUTION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
                self.assertNotEqual(_resolution_problems(text.replace(phrase, "")), [])

    def test_negative_proof_a_script_named_relative_to_the_cwd_is_detected(self):
        for naming in (
            "em-workflow/scripts/cleanup-task.py",
            "scripts/cleanup-task.py",
            "./cleanup-task.py",
        ):
            with self.subTest(naming=naming):
                forged_line = CALL_LINE.replace(SCRIPT_PLACEHOLDER, naming)
                forged_text = self.text.replace(CALL_LINE, forged_line, 1)
                self.assertIn(forged_line, forged_text)
                self.assertNotEqual(_relative_script_namings(forged_text), [])
                forged_region = _step4_region(forged_text)
                self.assertNotEqual(_script_name_in_fenced_line_problems(forged_region), [])
                self.assertNotEqual(_call_line_problems(forged_region), [])

    def test_negative_proof_a_prose_mention_by_relative_path_is_detected(self):
        forged_region = self.region + "   Run em-workflow/scripts/cleanup-task.py by hand.\n"
        forged_text = self.text.replace(self.region, forged_region, 1)
        self.assertNotEqual(forged_text, self.text)
        self.assertNotEqual(_relative_script_namings(forged_text), [])

    def test_relative_path_detection_accepts_only_the_plugin_root_form_and_the_bare_name(self):
        accepted = (
            "${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py",
            "the whole path of `cleanup-task.py`",
            "cleanup-task.py",
        )
        reported = (
            "./cleanup-task.py",
            "scripts/cleanup-task.py",
            "em-workflow/scripts/cleanup-task.py",
            "/abs/path/cleanup-task.py",
            "scripts\\cleanup-task.py",
            "${CLAUDE_PLUGIN_ROOT}/cleanup-task.py",
        )
        for sample in accepted:
            with self.subTest(accepted=sample):
                self.assertEqual(_relative_script_namings(sample), [])
        for sample in reported:
            with self.subTest(reported=sample):
                self.assertEqual(len(_relative_script_namings(sample)), 1)

    def test_negative_proof_a_second_fenced_block_is_detected(self):
        forged = self.region + "   ```bash\n   echo done\n   ```\n"
        self.assertNotEqual(_call_line_problems(forged), [])

    def test_negative_proof_an_extra_line_next_to_the_call_line_is_detected(self):
        forged = self.region.replace(CALL_LINE, CALL_LINE + " | cat")
        self.assertNotEqual(_call_line_problems(forged), [])

    def test_negative_proof_an_extra_token_after_the_call_line_is_detected(self):
        for token in ("--force", "extra", "$HOME", ""):
            with self.subTest(token=token):
                forged = self.region.replace(CALL_LINE, f"{CALL_LINE} {token}")
                self.assertNotEqual(forged, self.region)
                self.assertNotEqual(_call_line_problems(forged), [])

    def test_negative_proof_the_plugin_root_call_line_of_the_earlier_wording_is_not_accepted(self):
        forged = self.region.replace(CALL_LINE, PLUGIN_ROOT_CALL_LINE)
        self.assertNotEqual(forged, self.region)
        self.assertNotEqual(_call_line_problems(forged), [])
        with self.assertRaises(AssertionError) as ctx:
            _extract_call_line(forged)
        self.assertIn("no call line", str(ctx.exception))

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


# --- AC-5 of task0002: the sample call line passes the guards ----------------


class TestAC5CallLinePassesTheGuards(unittest.TestCase):
    """AC-5 (NFR2, TM-4, TS-9) of task0002, for the sample value set."""

    @classmethod
    def setUpClass(cls):
        cls.region = _step4_region(_read())
        cls.expanded = _expand(_extract_call_line(cls.region))

    def test_expanded_call_line_leaves_no_placeholder_dollar_or_brace(self):
        _assert_no_residue(self.expanded)

    def test_expanded_call_line_has_the_expected_shape(self):
        self.assertEqual(
            self.expanded,
            f"python3 '{SAMPLE_PLUGIN_ROOT}/scripts/cleanup-task.py' "
            f"--integration-worktree '{SAMPLE_INTEGRATION_WT}' "
            f"--feature '{SAMPLE_FEATURE}' --task '{SAMPLE_TASK}'",
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
        # No placeholder and no `CLAUDE_PLUGIN_ROOT` text survives the
        # expansion: the script is named through `{cleanup_script}` and is
        # replaced as a whole, in the same pass as the other three.
        for placeholder in PLACEHOLDERS:
            with self.subTest(placeholder=placeholder):
                self.assertNotIn(placeholder, self.expanded)
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


# --- AC-4 of task0004: expansion into the eight intended words ---------------


class TestTask4AC4ExpansionYieldsTheEightIntendedWords(unittest.TestCase):
    """AC-4 (NFR2, TM-4, TS-9): every value set, expanded with escaped values,
    leaves no placeholder and splits into the eight intended words."""

    @classmethod
    def setUpClass(cls):
        cls.call_line = _extract_call_line(_step4_region(_read()))

    def test_every_value_set_leaves_no_placeholder_and_splits_into_eight_words(self):
        for label, script, worktree in _value_sets():
            with self.subTest(values=label):
                self.assertEqual(
                    _expansion_problems(self.call_line, script, worktree), []
                )

    def test_value_sets_hold_every_special_form_in_both_positions(self):
        sets = _value_sets()
        for needle in (" ", "'", '"', "`", "$HOME", "${HOME}", "$(whoami)", "\n"):
            with self.subTest(form=needle):
                self.assertTrue(any(needle in script for _, script, _ in sets), "script path")
                self.assertTrue(any(needle in wt for _, _, wt in sets), "integration worktree")

    def test_value_sets_hold_the_sample_set_and_the_repository_copy(self):
        by_label = {label: (script, wt) for label, script, wt in _value_sets()}
        self.assertEqual(by_label["sample set"], (SAMPLE_SCRIPT, SAMPLE_INTEGRATION_WT))
        script, wt = by_label["repository copy"]
        self.assertTrue(os.path.isabs(script))
        self.assertTrue(script.endswith("/em-workflow/scripts/cleanup-task.py"))
        self.assertEqual(wt, SAMPLE_INTEGRATION_WT)

    def test_escaping_is_single_quotes_with_an_embedded_quote_written_out(self):
        self.assertEqual(_shell_escape("a b"), "'a b'")
        self.assertEqual(_shell_escape("it's"), "'it'\\''s'")
        self.assertEqual(_shell_escape("$HOME`x`\n"), "'$HOME`x`\n'")

    def test_a_value_holding_placeholder_text_is_never_expanded_again(self):
        script = f"{SAMPLE_ROOT}/{{feature}}/{{T}}/{{cleanup_script}}/cleanup-task.py"
        worktree = f"{SAMPLE_ROOT}/{{integration_worktree}}/.claude/worktrees/integration"
        expanded = _expand(self.call_line, script, worktree)
        self.assertEqual(shlex.split(expanded), _expected_words(script, worktree))

    def test_negative_proof_a_placeholder_left_on_the_line_is_detected(self):
        self.assertNotEqual(_residue_problems(self.call_line), [])
        left = _expand(self.call_line).replace(f"'{SAMPLE_TASK}'", "{T}")
        self.assertNotEqual(
            _residue_problems(left, _escaped_values(SAMPLE_SCRIPT, SAMPLE_INTEGRATION_WT)), []
        )

    def test_negative_proof_a_value_with_a_space_expanded_without_escaping_fails(self):
        cases = (
            ("script path", f"{SAMPLE_ROOT}/with space/cleanup-task.py", SAMPLE_INTEGRATION_WT),
            ("integration worktree", SAMPLE_SCRIPT, f"{SAMPLE_ROOT}/with space/integration"),
        )
        for label, script, worktree in cases:
            with self.subTest(value=label):
                self.assertNotEqual(
                    _word_problems(
                        _expand(self.call_line, script, worktree, escape=_no_escape),
                        _expected_words(script, worktree),
                    ),
                    [],
                )
                self.assertNotEqual(
                    _expansion_problems(self.call_line, script, worktree, escape=_no_escape), []
                )

    def test_negative_proof_a_value_with_dollar_and_newline_expanded_without_escaping_fails(self):
        cases = (
            ("script path", f"{SAMPLE_ROOT}/$HOME\nx/cleanup-task.py", SAMPLE_INTEGRATION_WT),
            ("integration worktree", SAMPLE_SCRIPT, f"{SAMPLE_ROOT}/$HOME\nx/integration"),
        )
        for label, script, worktree in cases:
            with self.subTest(value=label):
                self.assertNotEqual(
                    _word_problems(
                        _expand(self.call_line, script, worktree, escape=_no_escape),
                        _expected_words(script, worktree),
                    ),
                    [],
                )
                self.assertNotEqual(
                    _expansion_problems(self.call_line, script, worktree, escape=_no_escape), []
                )

    def test_negative_proof_a_value_with_a_single_quote_expanded_without_escaping_fails(self):
        script = f"{SAMPLE_ROOT}/it's/cleanup-task.py"
        problems = _word_problems(
            _expand(self.call_line, script, escape=_no_escape),
            _expected_words(script, SAMPLE_INTEGRATION_WT),
        )
        self.assertNotEqual(problems, [])

    def test_negative_proof_a_double_quoted_value_with_dollar_is_detected(self):
        # Double quotes keep the words intact but leave `$` live for the
        # shell: the residue check outside the escaped values catches it.
        script = f"{SAMPLE_ROOT}/$HOME/cleanup-task.py"
        self.assertNotEqual(
            _expansion_problems(self.call_line, script, SAMPLE_INTEGRATION_WT, escape=_double_quote),
            [],
        )

    def test_negative_proof_a_word_check_fails_for_a_changed_word_count_or_value(self):
        expanded = _expand(self.call_line)
        words = _expected_words(SAMPLE_SCRIPT, SAMPLE_INTEGRATION_WT)
        self.assertEqual(_word_problems(expanded, words), [])
        self.assertNotEqual(_word_problems(expanded + " extra", words), [])
        self.assertNotEqual(_word_problems(expanded.replace(SAMPLE_TASK, "task0002"), words), [])
        self.assertNotEqual(_word_problems(expanded.replace("'", ""), words[:1] + ["x"]), [])


# --- AC-5 of task0004: expanded lines pass the guards -------------------------


class TestTask4AC5ExpandedLinesPassTheGuards(unittest.TestCase):
    """AC-5 (NFR2, TM-4, TS-9): every expanded line of AC-4 passes
    `destructive-guard.py` and `interpreter-mismatch-guard.py`, with
    `CLAUDE_BATCH` removed and set."""

    @classmethod
    def setUpClass(cls):
        cls.call_line = _extract_call_line(_step4_region(_read()))

    def test_every_expanded_line_passes_each_guard_without_and_with_claude_batch(self):
        for label, script, worktree in _value_sets():
            expanded = _expand(self.call_line, script, worktree)
            for name, path in GUARD_PATHS.items():
                for batch in (False, True):
                    with self.subTest(values=label, guard=name, claude_batch=batch):
                        verdict = _guard_verdict(path, expanded, batch)
                        self.assertTrue(
                            _passes(verdict),
                            f"{name} (CLAUDE_BATCH {'set' if batch else 'removed'}) "
                            f"judged {expanded!r}: {verdict}",
                        )

    def test_the_value_with_a_newline_reaches_the_guard_inside_the_json_input(self):
        script = f"{SAMPLE_ROOT}/line\nbreak/cleanup-task.py"
        expanded = _expand(self.call_line, script)
        self.assertIn("\n", expanded)
        self.assertEqual(json.loads(json.dumps({"command": expanded}))["command"], expanded)
        self.assertTrue(_passes(_guard_verdict(DESTRUCTIVE_GUARD_PATH, expanded, False)))

    def test_passing_means_a_clean_exit_and_neither_ask_nor_deny(self):
        for verdict in ("allow", "(silent)"):
            with self.subTest(verdict=verdict):
                self.assertTrue(_passes(verdict))
        for verdict in ("ask", "deny", "(exit 1)", "(exit 2)"):
            with self.subTest(verdict=verdict):
                self.assertFalse(_passes(verdict))

    def test_negative_proof_a_forced_branch_deletion_does_not_pass_the_destructive_guard(self):
        for batch in (False, True):
            with self.subTest(claude_batch=batch):
                verdict = _guard_verdict(
                    DESTRUCTIVE_GUARD_PATH,
                    "git branch -D em-workflow/some-feature/task0001",
                    batch,
                )
                self.assertFalse(_passes(verdict), verdict)

    def test_negative_proof_a_python_script_run_by_bash_does_not_pass_the_interpreter_guard(self):
        command = f"bash {PLUGIN_ROOT / 'scripts' / 'merge-git.py'}"
        for batch in (False, True):
            with self.subTest(claude_batch=batch):
                verdict = _guard_verdict(INTERPRETER_GUARD_PATH, command, batch)
                self.assertFalse(_passes(verdict), verdict)

    def test_negative_proof_a_guard_that_exits_non_zero_is_not_a_pass(self):
        missing = REPO_ROOT / "em-workflow" / "hooks" / "no-such-guard.py"
        verdict = _guard_verdict(missing, "python3 x", False)
        self.assertTrue(verdict.startswith("(exit"), verdict)
        self.assertFalse(_passes(verdict))


class TestModuleHygiene(unittest.TestCase):
    """This module writes no files and needs no cleanup script."""

    def test_module_writes_no_files(self):
        source = Path(__file__).read_text(encoding="utf-8")
        before = source[: source.index("class TestModuleHygiene")]
        for needle in ("write_text(", "write_bytes(", ".mkdir(", 'open(', "tempfile"):
            self.assertNotIn(needle, before)


if __name__ == "__main__":
    unittest.main()
