"""Document tests for task0002 (cd-prefix-canonical-path-only): the producer
and the consumer procedures of the canonical worktree path.

The orchestrator hands each implementer a `worktree_path` that is the strict
realpath of `$WT_ROOT/{T}` and derives `tests_yaml_path` from that value. The
implementer's procedures say that the cd target is `worktree_path` exactly as
supplied and that it is assumed to be a canonical absolute path. The path
conditions themselves are stated once, in the Verbatim execution rule of
`references/command-execution-protocol.md`; the documents checked here cite
that rule and do not restate it.

Covers this task's Acceptance Criteria
(feature-docs/cd-prefix-canonical-path-only/tasks/task0002.md):

- AC-1 (FR8; TS10): Step I.2.a of `em-workflow/references/implement-phase.md`
  canonicalizes `$WT_ROOT/{T}` with a strict realpath once the task's
  worktree exists (newly created or reused under the Resume guard), passes
  that value as the worktree_path, gives no fallback to the unresolved
  string, and places the step with the worktree creation and the Resume
  guard, before the approval-gate paragraph.
- AC-2 (FR8; TS10): the `worktree_path:` placeholder of the assignment
  payload names the canonical value; the `tests_yaml_path:` placeholder and
  the `tests_yaml_path` paragraph derive the record path from the canonical
  worktree_path, not from `$WT_ROOT/{T}`.
- AC-3 (FR7; TS12): `em-workflow/agents/implementer.md` (the Inputs section
  and Step 3) and `em-workflow/skills/worktree-task-workflow/SKILL.md` (the
  command execution gate) each state that the cd target is the supplied
  worktree_path, used as is, and that it is assumed to be a canonical
  absolute path.
- AC-4 (FR7, FR8, NFR1; TS14): the changed places cite the Verbatim
  execution rule and do not restate the path conditions; this module imports
  only the standard library. The existing document tests and the full suite
  are run as the suite itself.

Method: slice by heading, normalize whitespace, assert the presence or
absence of stable phrases, never a line number. Every check is a function
from a document text to a list of problems. The live document must yield
none; each forged text, and the verbatim pre-change payload sample, must
yield the problem the check exists to catch.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENT_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "implement-phase.md"
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "worktree-task-workflow" / "SKILL.md"

I2A_NAME = "I.2.a: Launch phase"
INPUTS_NAME = "Inputs (from your invocation prompt)"
STEP_3_NAME = "Step 3: Verify the worktree"
GATE_NAME = "Command execution gate"

PROTOCOL_CITATION = "references/command-execution-protocol.md"
RULE_NAME = "Verbatim execution rule"

# Anchors that bound the producer step inside Step I.2.a.
RESUME_GUARD_LAST_ITEM = "- Clean re-attempt (fresh implementer"
GATE_PARAGRAPH_OPENING = "Before launching, verify every `project_commands`"
LAUNCH_LOOP_OPENING = "Launch each selected task as a BACKGROUND"

PAYLOAD_HEADER = "# Task assignment"
TESTS_YAML_PARAGRAPH_OPENING = "`tests_yaml_path` points INSIDE the task's own worktree"

# The verbatim pre-change placeholders and the closing sentence of the
# pre-change `tests_yaml_path` paragraph (the negative samples of AC-2).
PRE_CHANGE_WORKTREE_PATH_LINE = "worktree_path: {absolute path to $WT_ROOT/{T}}"
PRE_CHANGE_TESTS_YAML_PATH_LINE = (
    "tests_yaml_path: {absolute path to "
    "$WT_ROOT/{T}/test-docs/{feature}/{T}.tests.yaml}"
)
PRE_CHANGE_TESTS_YAML_SENTENCE = (
    "Build the path yourself and pass it — the implementer does not know "
    "`{feature}` and must not derive it from other paths."
)

# Wording of the path-condition statement. A sentence that carries several of
# these markers restates the conditions instead of citing the rule.
CONDITION_MARKERS = (
    "strictly below",
    "existing directory",
    "realpath",
    "`..`",
    "empty component",
    "link component",
    "symbolic link",
)
RESTATEMENT_THRESHOLD = 3

# Control-character check of Step I.2.a (worktree-path-control-char-stop,
# task0001). The check paragraph is located by the category phrase; the
# rejected set is pinned range by range; the stop is pinned by phrases.
CONTROL_CHECK_LOCATOR = "Unicode general category Cc"
CONTROL_CHECK_SCOPE_PHRASE = "every task selected in this entry into Step I.2.a"
CONTROL_CHECK_ALL_TASKS_PHRASE = "each of those tasks, not only the first or the current one"
CONTROL_CHECK_REJECTED_RANGES = (
    "U+0000–U+001F",
    "U+007F",
    "U+0080–U+009F",
    "U+2028",
    "U+2029",
)
CONTROL_CHECK_ABORT_PHRASE = "ABORT the implement phase"
CONTROL_CHECK_REPORT_PHRASE = "report the IDs of the offending tasks"
CONTROL_CHECK_NO_PROMPT_PHRASE = "build no implementer launch prompt for any selected task"
CONTROL_CHECK_NO_SANITIZE_PHRASE = "Never strip, escape or replace the characters"
CONTROL_CHECK_NO_FALLBACK_PHRASE = "never fall back to the unresolved path string"

# Terminal handling of the control-character stop (control-char-abort-terminal-
# state, task0001). The stop takes the terminal handling of Step I.2.c's abort
# phase: one committed write that sets the `implement` step to `failed` with
# `failed_kind` valued `decision`. The four elements below are each absent from
# the paragraph's text before this feature, so a passing check is never vacuous.
CONTROL_CHECK_TERMINAL_START_PHRASE = "After the rejection, the phase takes"
CONTROL_CHECK_TERMINAL_SOURCE_PHRASE = "Step I.2.c's abort phase"
CONTROL_CHECK_TERMINAL_STATUS_PHRASE = "the `implement` step's `status` to `failed`"
CONTROL_CHECK_TERMINAL_KIND_PHRASE = "`failed_kind` valued `decision`"
CONTROL_CHECK_TERMINAL_COMMIT_PHRASE = "`commit-docs.sh`"
CONTROL_CHECK_TERMINAL_ELEMENTS = (
    ("the abort phase as the source", CONTROL_CHECK_TERMINAL_SOURCE_PHRASE),
    ("the implement step set to failed", CONTROL_CHECK_TERMINAL_STATUS_PHRASE),
    ("failed_kind paired with decision", CONTROL_CHECK_TERMINAL_KIND_PHRASE),
    ("the commit-docs.sh commit", CONTROL_CHECK_TERMINAL_COMMIT_PHRASE),
)
CONTROL_CHECK_KIND_UNCONDITIONAL_PHRASE = "`failed_kind` is `decision` unconditionally"
CONTROL_CHECK_NO_EXTRA_WRITES_PHRASE = (
    "no `create-plan` `needs_update`, no task status or notes write and no "
    "worktree or branch cleanup"
)
CONTROL_CHECK_NO_WAIT_PHRASE = (
    "without waiting for the tasks launched by an earlier refill"
)
CONTROL_CHECK_STOP_CONDITION_PHRASE = "develop's stop condition 3"

# The paragraph's text before this feature, kept verbatim: the added text is
# appended after it and no existing sentence is reworded.
PRE_CHANGE_CONTROL_CHECK_PARAGRAPH = """\
**Control-character check**: once every task selected in this entry into
Step I.2.a has its canonical `worktree_path` (the value the Canonical
worktree path paragraph above yields, for a worktree just created and for one
reused under the Resume guard alike), check the value of each of those tasks,
not only the first or the current one. The check is a test over the
characters of the resolved value itself, not over how the value looks when
printed, because most of the characters below are invisible or render as a
line break. A value is rejected when it contains any character of Unicode
general category Cc (U+0000–U+001F, U+007F, U+0080–U+009F), U+2028 or U+2029.
When the value of one or more selected tasks contains such a character, ABORT
the implement phase, report the IDs of the offending tasks, build no
implementer launch prompt for any selected task (clean ones included) and
launch no implementer. Never strip, escape or replace the characters and
continue, and never fall back to the unresolved path string. The stop follows
the same fail-closed discipline as Step I.0's identifier validation gate
(never sanitize, never proceed), and it happens before the approval-gate
paragraph below asks about any command."""
RESUME_GUARD_PARAGRAPH_OPENING = "**Resume guard**"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_START = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


# --- Text helpers ------------------------------------------------------------


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def section_text(text, name, source="document"):
    """The section whose heading text is `name` (optionally followed by more
    words): from the line after its heading up to (not including) the next
    heading of the same or a higher level, or end of file. Headings inside
    fenced code blocks are ignored. Raises AssertionError when the heading is
    absent, so a renamed heading fails loudly instead of letting an absence
    check pass over an empty string."""
    lines = text.splitlines()
    in_fence = False
    start = None
    level = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        heading = match.group(2)
        if start is None:
            if heading == name or heading.startswith(name + " "):
                start = i + 1
                level = depth
            continue
        if depth <= level:
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"heading not found in {source}: {name}")
    return "\n".join(lines[start:])


def raw_paragraphs(text):
    """Blank-line separated paragraphs of `text`, newlines kept."""
    return [p for p in re.split(r"\n[ \t]*\n", text) if p.strip()]


def blocks(text):
    """Paragraph / list-item blocks: a blank line or a bullet start begins a
    new block. Each block is whitespace-normalized."""
    out = []
    current = []

    def flush():
        if current:
            out.append(_normalize_ws(" ".join(current)))
            current.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _BULLET_START.match(line):
            flush()
        current.append(line)
    flush()
    return out


def sentences_of_block(block):
    return [s for s in re.split(r"(?<=\.)\s+", block) if s]


def sentences(text):
    out = []
    for block in blocks(text):
        out.extend(sentences_of_block(block))
    return out


def sentences_with(text, *terms):
    """The sentences of `text` that contain every term (case-sensitive)."""
    return [s for s in sentences(text) if all(t in s for t in terms)]


def blocks_with(text, *terms):
    """The blocks of `text` that contain every term (case-sensitive)."""
    return [b for b in blocks(text) if all(t in b for t in terms)]


def without_sentences(text, *terms):
    """`text` with every sentence that contains all of `terms` removed."""
    kept = [s for s in sentences(text) if not all(t in s for t in terms)]
    return "\n\n".join(kept)


def fenced_blocks(text):
    """The bodies of the fenced code blocks of `text`, as lists of lines."""
    out = []
    current = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                out.append(current)
                current = None
            continue
        if current is not None:
            current.append(line)
    return out


def payload_lines(text):
    """The lines of the one fenced block that starts with the payload header,
    or None when there is not exactly one."""
    found = [b for b in fenced_blocks(text) if b and b[0].strip() == PAYLOAD_HEADER]
    return found[0] if len(found) == 1 else None


def field_value(lines, name):
    """The value after `name:` on the one line that starts with it, or None."""
    hits = [l for l in lines if l.startswith(name + ":")]
    if len(hits) != 1:
        return None
    return hits[0][len(name) + 1 :].strip()


# --- Documents ---------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def i2a_section():
    return section_text(_read(IMPLEMENT_PHASE_PATH), I2A_NAME, "implement-phase.md")


def inputs_section():
    return section_text(_read(IMPLEMENTER_PATH), INPUTS_NAME, "implementer.md")


def step3_section():
    return section_text(_read(IMPLEMENTER_PATH), STEP_3_NAME, "implementer.md")


def gate_section():
    return section_text(_read(SKILL_PATH), GATE_NAME, "SKILL.md")


# --- Checks (text -> list of problems) ----------------------------------------


def _producer_sentences(section):
    return sentences_with(
        section,
        "`$WT_ROOT/{T}`",
        "strict realpath",
        "worktree exists",
    )


def check_producer_statement(section):
    """AC-1: the canonicalization step of Step I.2.a."""
    problems = []
    canonical = _producer_sentences(section)
    if len(canonical) != 1:
        return problems + [
            "expected exactly one sentence that resolves `$WT_ROOT/{T}` with a "
            f"strict realpath once the worktree exists, found {len(canonical)}"
        ]
    sentence = canonical[0]
    for term in (
        "`git worktree add -b`",
        "Resume guard",
        "every component must exist",
        "links resolved",
    ):
        if term not in sentence:
            problems.append(f"the canonicalization sentence lacks: {term}")

    passed = sentences_with(
        section, "`worktree_path`", "canonical absolute path", "passed to the implementer"
    )
    if len(passed) != 1:
        problems.append(
            "expected exactly one sentence that makes the canonical value the "
            f"worktree_path passed to the implementer, found {len(passed)}"
        )

    no_fallback = sentences_with(
        section, "unresolved", "`$WT_ROOT/{T}`", "never passed"
    )
    if len(no_fallback) != 1:
        problems.append(
            "expected exactly one sentence that gives no fallback to the "
            f"unresolved string, found {len(no_fallback)}"
        )

    problems.extend(_check_producer_placement(section))
    return problems


def _check_producer_placement(section):
    """The step sits after the Resume guard items and before the approval-gate
    paragraph and the launch-loop paragraph."""
    problems = []
    all_blocks = blocks(section)

    def index_of(opening):
        hits = [i for i, b in enumerate(all_blocks) if b.startswith(opening)]
        return hits[0] if len(hits) == 1 else None

    resume_end = index_of(RESUME_GUARD_LAST_ITEM)
    gate = index_of(GATE_PARAGRAPH_OPENING)
    launch = index_of(LAUNCH_LOOP_OPENING)
    for label, idx in (
        ("the last Resume guard item", resume_end),
        ("the approval-gate paragraph", gate),
        ("the launch-loop paragraph", launch),
    ):
        if idx is None:
            problems.append(f"cannot locate {label} in Step I.2.a")
    step = [
        i
        for i, b in enumerate(all_blocks)
        if "strict realpath" in b and "`$WT_ROOT/{T}`" in b and "worktree exists" in b
    ]
    if len(step) != 1:
        problems.append("cannot locate the paragraph of the canonicalization step")
    if problems:
        return problems
    if not resume_end < step[0] < gate < launch:
        problems.append(
            "the canonicalization step is not between the Resume guard items "
            "and the approval-gate paragraph"
        )
    return problems


def check_payload_placeholders(section):
    """AC-2: the two placeholders of the assignment payload."""
    problems = []
    lines = payload_lines(section)
    if lines is None:
        return ["cannot locate exactly one assignment payload block"]

    worktree = field_value(lines, "worktree_path")
    if worktree is None:
        problems.append("the payload has no single worktree_path line")
    elif not (
        worktree.startswith("{canonical worktree_path")
        and "strict realpath" in worktree
        and "$WT_ROOT/{T}" in worktree
    ):
        problems.append(
            f"the worktree_path placeholder does not name the canonical value: {worktree!r}"
        )

    tests_yaml = field_value(lines, "tests_yaml_path")
    expected = "{canonical worktree_path}/test-docs/{feature}/{T}.tests.yaml"
    if tests_yaml is None:
        problems.append("the payload has no single tests_yaml_path line")
    elif tests_yaml != expected:
        problems.append(
            f"the tests_yaml_path placeholder is not {expected!r}: {tests_yaml!r}"
        )
    return problems


def check_tests_yaml_paragraph(section):
    """AC-2: the `tests_yaml_path` paragraph derives the record path from the
    canonical worktree_path."""
    paragraphs = blocks_with(section, TESTS_YAML_PARAGRAPH_OPENING)
    if len(paragraphs) != 1:
        return [
            "expected exactly one `tests_yaml_path` paragraph, found "
            f"{len(paragraphs)}"
        ]
    paragraph = paragraphs[0]
    problems = []
    derived = [
        s
        for s in sentences_of_block(paragraph)
        if all(
            t in s
            for t in (
                "canonical `worktree_path`",
                "`test-docs/{feature}/{T}.tests.yaml`",
            )
        )
    ]
    if len(derived) != 1:
        problems.append(
            "expected exactly one sentence that derives the record path from "
            f"the canonical `worktree_path`, found {len(derived)}"
        )
    if "$WT_ROOT/{T}/test-docs" in paragraph:
        problems.append(
            "the paragraph still builds the record path from `$WT_ROOT/{T}`"
        )
    return problems


def check_inputs_statement(section):
    """AC-3: the Inputs section of implementer.md."""
    hits = sentences_with(
        section,
        "`worktree_path`",
        "assume",
        "canonical absolute path",
        "exactly as supplied",
    )
    if len(hits) != 1:
        return [
            "expected exactly one sentence that says worktree_path is assumed "
            f"to be a canonical absolute path and used exactly as supplied, found {len(hits)}"
        ]
    return []


def check_cd_target_statement(section):
    """AC-3: Step 3 of implementer.md and the command execution gate of
    SKILL.md."""
    problems = []
    target = sentences_with(
        section,
        "cd target",
        "`worktree_path`",
        "exactly as supplied",
        "rewrite",
        "normalize",
        "resolve",
    )
    if len(target) != 1:
        problems.append(
            "expected exactly one sentence that says the cd target is "
            "`worktree_path` exactly as supplied, not rewritten, normalized "
            f"or resolved, found {len(target)}"
        )
    assumed = sentences_with(
        section, "Assume", "`worktree_path`", "canonical absolute path"
    )
    if len(assumed) != 1:
        problems.append(
            "expected exactly one sentence that assumes worktree_path is a "
            f"canonical absolute path, found {len(assumed)}"
        )
    return problems


def check_cites_rule(section, *statement_terms):
    """AC-4: the block that holds the statement cites the Verbatim execution
    rule of the protocol document."""
    holders = blocks_with(
        section, *statement_terms, RULE_NAME, PROTOCOL_CITATION
    )
    if len(holders) < 1:
        return [
            "no block holds the statement together with a citation of the "
            f"{RULE_NAME} of {PROTOCOL_CITATION}"
        ]
    return []


def find_condition_restatements(text):
    """AC-4: sentences that carry several markers of the path-condition
    wording."""
    return [
        s
        for s in sentences(text)
        if sum(1 for marker in CONDITION_MARKERS if marker in s)
        >= RESTATEMENT_THRESHOLD
    ]


def _control_check_blocks(section):
    return blocks_with(section, CONTROL_CHECK_LOCATOR)


def check_control_char_scope(section):
    """The control-character check applies to every selected task."""
    paragraphs = _control_check_blocks(section)
    if len(paragraphs) != 1:
        return [
            "expected exactly one control-character check paragraph, found "
            f"{len(paragraphs)}"
        ]
    scoped = [
        s
        for s in sentences_of_block(paragraphs[0])
        if all(
            t in s
            for t in (
                CONTROL_CHECK_SCOPE_PHRASE,
                "canonical `worktree_path`",
                CONTROL_CHECK_ALL_TASKS_PHRASE,
            )
        )
    ]
    if len(scoped) != 1:
        return [
            "expected exactly one sentence that applies the check to every "
            f"selected task, found {len(scoped)}"
        ]
    return []


def check_control_char_rejected_set(section):
    """The check paragraph names Cc and each range of the rejected set."""
    paragraphs = _control_check_blocks(section)
    if len(paragraphs) != 1:
        return [
            "expected exactly one control-character check paragraph, found "
            f"{len(paragraphs)}"
        ]
    problems = []
    for code_range in CONTROL_CHECK_REJECTED_RANGES:
        if code_range not in paragraphs[0]:
            problems.append(f"the rejected set lacks: {code_range}")
    return problems


def check_control_char_stop(section):
    """The check paragraph aborts the implement phase, reports the offending
    task IDs and builds no launch prompt for any selected task, and never
    sanitizes or falls back."""
    paragraphs = _control_check_blocks(section)
    if len(paragraphs) != 1:
        return [
            "expected exactly one control-character check paragraph, found "
            f"{len(paragraphs)}"
        ]
    paragraph = paragraphs[0]
    problems = []
    stops = [
        s for s in sentences_of_block(paragraph) if CONTROL_CHECK_ABORT_PHRASE in s
    ]
    if len(stops) != 1:
        problems.append(
            "expected exactly one sentence that ABORTs the implement phase, "
            f"found {len(stops)}"
        )
    else:
        if CONTROL_CHECK_REPORT_PHRASE not in stops[0]:
            problems.append("the stop sentence does not report the offending task IDs")
        if CONTROL_CHECK_NO_PROMPT_PHRASE not in stops[0]:
            problems.append(
                "the stop sentence does not build no launch prompt for any selected task"
            )
    if CONTROL_CHECK_NO_SANITIZE_PHRASE not in paragraph:
        problems.append("the paragraph does not rule out stripping, escaping or replacing")
    if CONTROL_CHECK_NO_FALLBACK_PHRASE not in paragraph:
        problems.append("the paragraph does not rule out the unresolved path string")
    return problems


def check_control_char_placement(section):
    """The check paragraph's block sits after the canonicalization block and
    before the approval-gate paragraph and the launch-loop paragraph."""
    all_blocks = blocks(section)

    def index_of(opening):
        hits = [i for i, b in enumerate(all_blocks) if b.startswith(opening)]
        return hits[0] if len(hits) == 1 else None

    checks = [i for i, b in enumerate(all_blocks) if CONTROL_CHECK_LOCATOR in b]
    canonical = [
        i
        for i, b in enumerate(all_blocks)
        if "strict realpath" in b and "`$WT_ROOT/{T}`" in b and "worktree exists" in b
    ]
    gate = index_of(GATE_PARAGRAPH_OPENING)
    launch = index_of(LAUNCH_LOOP_OPENING)
    problems = []
    if len(checks) != 1:
        problems.append(
            f"cannot locate exactly one control-character check block, found {len(checks)}"
        )
    if len(canonical) != 1:
        problems.append("cannot locate the paragraph of the canonicalization step")
    if gate is None:
        problems.append("cannot locate the approval-gate paragraph in Step I.2.a")
    if launch is None:
        problems.append("cannot locate the launch-loop paragraph in Step I.2.a")
    if problems:
        return problems
    if not canonical[0] < checks[0]:
        problems.append("the check paragraph does not come after the canonicalization step")
    if not checks[0] < launch:
        problems.append("the check paragraph does not come before the launch-loop paragraph")
    if not checks[0] < gate:
        problems.append("the check paragraph does not come before the approval-gate paragraph")
    return problems


def check_control_char_terminal_handling(section):
    """The check paragraph takes the terminal handling of Step I.2.c's abort
    phase: it names the abort phase as the source, sets the `implement`
    step's `status` to `failed`, pairs `failed_kind` with the `decision`
    value and commits with `commit-docs.sh`. One problem per missing
    element."""
    paragraphs = _control_check_blocks(section)
    if len(paragraphs) != 1:
        return [
            "expected exactly one control-character check paragraph, found "
            f"{len(paragraphs)}"
        ]
    return [
        f"the control-character check paragraph lacks {label}: {phrase}"
        for label, phrase in CONTROL_CHECK_TERMINAL_ELEMENTS
        if phrase not in paragraphs[0]
    ]


# --- Forged texts ---------------------------------------------------------------


FORGED_RESTATEMENT = (
    "The worktree_path must be an existing directory strictly below the area, "
    "with no `..` component, and equal to its realpath."
)
FORGED_RESTATEMENT_PLAN_EXAMPLE = (
    "The path is strictly below the area, resolved by realpath, and an existing "
    "directory."
)


def _remove_paragraph_with(section, *terms):
    kept = [p for p in raw_paragraphs(section) if not all(t in _normalize_ws(p) for t in terms)]
    forged = "\n\n".join(kept)
    assert forged != section, f"no paragraph with {terms} to remove"
    return forged


def _move_paragraph_before(section, move_terms, before_opening):
    paragraphs = raw_paragraphs(section)
    moving = [p for p in paragraphs if all(t in _normalize_ws(p) for t in move_terms)]
    assert len(moving) == 1, moving
    rest = [p for p in paragraphs if p is not moving[0]]
    at = [i for i, p in enumerate(rest) if _normalize_ws(p).startswith(before_opening)]
    assert len(at) == 1, at
    # Insert after the paragraph that opens with `before_opening`.
    rest.insert(at[0] + 1, moving[0])
    return "\n\n".join(rest)


def _replace_phrase(text, old, new):
    """`text` with `old` replaced by `new`, whatever line wrap sits between
    the words of `old`. Fails loudly when `old` is absent, so a replacement
    that matches nothing cannot make a forged-copy test pass vacuously."""
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    forged, count = re.subn(pattern, lambda _match: new, text)
    assert count >= 1, f"no text matching {old!r} to replace"
    return forged


def _all_control_char_problems(section):
    return (
        check_control_char_scope(section)
        + check_control_char_rejected_set(section)
        + check_control_char_stop(section)
        + check_control_char_placement(section)
        + check_control_char_terminal_handling(section)
    )


def _terminal_handling_text(section):
    """The raw text of the check paragraph from the start of the terminal
    handling to the end of the paragraph. Fails loudly when the paragraph or
    the start of the terminal handling is absent."""
    hits = [
        p for p in raw_paragraphs(section) if CONTROL_CHECK_LOCATOR in _normalize_ws(p)
    ]
    assert len(hits) == 1, f"expected one check paragraph, found {len(hits)}"
    pattern = r"\s+".join(
        re.escape(word) for word in CONTROL_CHECK_TERMINAL_START_PHRASE.split()
    )
    match = re.search(pattern, hits[0])
    assert match, f"no terminal handling text starting with {CONTROL_CHECK_TERMINAL_START_PHRASE!r}"
    return hits[0][match.start() :].strip()


# --- Tests -------------------------------------------------------------------------


class TestSectionLocation(unittest.TestCase):
    """The sections are found by heading and are not empty."""

    def test_every_section_is_found_and_nonempty(self):
        for name, getter in (
            (I2A_NAME, i2a_section),
            (INPUTS_NAME, inputs_section),
            (STEP_3_NAME, step3_section),
            (GATE_NAME, gate_section),
        ):
            with self.subTest(section=name):
                self.assertTrue(getter().strip())

    def test_section_text_raises_for_a_missing_heading(self):
        with self.assertRaises(AssertionError):
            section_text("## A\n\nx\n", "Missing")

    def test_section_text_ends_at_the_next_heading_of_the_same_level(self):
        text = "## A\n\nbody a\n\n### A sub\n\nsub\n\n## B\n\nbody b\n"
        a = section_text(text, "A")
        self.assertIn("sub", a)
        self.assertNotIn("body b", a)

    def test_neighbouring_sections_are_not_swallowed(self):
        self.assertNotIn("Wake phase", i2a_section().split("\n", 1)[0])
        self.assertNotIn("### I.2.b", i2a_section())
        self.assertNotIn("Step 4", step3_section())
        self.assertNotIn("Untrusted input", gate_section())
        self.assertNotIn("Data in the assignment prompt", inputs_section())


class TestAC1ProducerCanonicalizes(unittest.TestCase):
    """AC-1 (FR8; TS10): Step I.2.a of implement-phase.md."""

    def test_ac1_live_document_states_the_canonicalization_step(self):
        self.assertEqual(check_producer_statement(i2a_section()), [])

    def test_ac1_forged_copy_without_the_step_fails(self):
        forged = _remove_paragraph_with(i2a_section(), "strict realpath", "worktree exists")
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_forged_copy_without_the_strict_realpath_fails(self):
        forged = i2a_section().replace("strict realpath", "absolute path")
        self.assertNotEqual(forged, i2a_section())
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_forged_copy_that_covers_only_a_new_worktree_fails(self):
        forged = i2a_section().replace("Resume guard above", "earlier step")
        self.assertNotEqual(forged, i2a_section())
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_forged_copy_without_the_value_hand_over_fails(self):
        forged = without_sentences(
            i2a_section(), "`worktree_path`", "canonical absolute path", "passed to the implementer"
        )
        self.assertNotEqual(forged, "")
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_forged_copy_without_the_no_fallback_sentence_fails(self):
        forged = without_sentences(
            i2a_section(), "unresolved", "`$WT_ROOT/{T}`", "never passed"
        )
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_forged_copy_with_the_step_after_the_approval_gate_fails(self):
        forged = _move_paragraph_before(
            i2a_section(),
            ("strict realpath", "worktree exists"),
            GATE_PARAGRAPH_OPENING,
        )
        self.assertNotEqual(check_producer_statement(forged), [])

    def test_ac1_other_uses_of_wt_root_t_are_kept(self):
        section = _normalize_ws(i2a_section())
        for expected in (
            '"$WT_ROOT/{T}" \\ "em-workflow/{feature}/integration"',
            'git worktree remove --force "$WT_ROOT/{T}"',
            "whether `em-workflow/{feature}/{T}` and/or `$WT_ROOT/{T}` already exist",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)


class TestAC2PayloadPlaceholders(unittest.TestCase):
    """AC-2 (FR8; TS10): the payload placeholders and the `tests_yaml_path`
    paragraph."""

    def test_ac2_live_payload_names_the_canonical_value(self):
        self.assertEqual(check_payload_placeholders(i2a_section()), [])

    def test_ac2_pre_change_placeholders_fail(self):
        section = i2a_section()
        forged = section.replace(
            field_line(section, "worktree_path"), PRE_CHANGE_WORKTREE_PATH_LINE
        ).replace(
            field_line(section, "tests_yaml_path"), PRE_CHANGE_TESTS_YAML_PATH_LINE
        )
        problems = check_payload_placeholders(forged)
        self.assertEqual(len(problems), 2, problems)

    def test_ac2_pre_change_worktree_path_placeholder_alone_fails(self):
        section = i2a_section()
        forged = section.replace(
            field_line(section, "worktree_path"), PRE_CHANGE_WORKTREE_PATH_LINE
        )
        self.assertEqual(len(check_payload_placeholders(forged)), 1)

    def test_ac2_pre_change_tests_yaml_path_placeholder_alone_fails(self):
        section = i2a_section()
        forged = section.replace(
            field_line(section, "tests_yaml_path"), PRE_CHANGE_TESTS_YAML_PATH_LINE
        )
        self.assertEqual(len(check_payload_placeholders(forged)), 1)

    def test_ac2_live_tests_yaml_path_paragraph_derives_from_the_canonical_path(self):
        self.assertEqual(check_tests_yaml_paragraph(i2a_section()), [])

    def test_ac2_pre_change_paragraph_sentence_fails(self):
        section = i2a_section()
        derived = sentences_with(
            section, "canonical `worktree_path`", "`test-docs/{feature}/{T}.tests.yaml`"
        )
        self.assertEqual(len(derived), 1, derived)
        forged = _normalize_ws(section).replace(derived[0], PRE_CHANGE_TESTS_YAML_SENTENCE)
        self.assertNotEqual(forged, _normalize_ws(section))
        self.assertNotEqual(check_tests_yaml_paragraph(forged), [])

    def test_ac2_paragraph_that_builds_from_wt_root_fails(self):
        forged = (
            TESTS_YAML_PARAGRAPH_OPENING
            + ". The path is `$WT_ROOT/{T}/test-docs/{feature}/{T}.tests.yaml`."
        )
        self.assertNotEqual(check_tests_yaml_paragraph(forged), [])

    def test_ac2_payload_structure_is_kept(self):
        lines = payload_lines(i2a_section())
        self.assertIsNotNone(lines)
        self.assertEqual(lines[0], PAYLOAD_HEADER)
        self.assertTrue(lines[1].startswith("task_id:"))
        self.assertTrue(lines[2].startswith("worktree_path:"))
        self.assertTrue(lines[-1].startswith("expected_files:"))


def field_line(section, name):
    """The full payload line that starts with `name:`."""
    lines = payload_lines(section)
    hits = [l for l in lines if l.startswith(name + ":")]
    assert len(hits) == 1, hits
    return hits[0]


class TestAC3ConsumerProcedures(unittest.TestCase):
    """AC-3 (FR7; TS12): the implementer's procedures."""

    def test_ac3_inputs_section_states_the_assumption(self):
        self.assertEqual(check_inputs_statement(inputs_section()), [])

    def test_ac3_inputs_forged_copy_without_the_statement_fails(self):
        forged = without_sentences(inputs_section(), "assume", "canonical absolute path")
        self.assertNotEqual(forged, "")
        self.assertNotEqual(check_inputs_statement(forged), [])

    def test_ac3_inputs_forged_copy_that_asks_for_resolution_fails(self):
        forged = (
            "`worktree_path` (absolute — your ONLY writable area). Resolve it "
            "with realpath before use."
        )
        self.assertNotEqual(check_inputs_statement(forged), [])

    def test_ac3_step3_states_the_cd_target_and_the_assumption(self):
        self.assertEqual(check_cd_target_statement(step3_section()), [])

    def test_ac3_step3_forged_copy_without_the_statement_fails(self):
        forged = without_sentences(step3_section(), "cd target", "`worktree_path`")
        self.assertNotEqual(check_cd_target_statement(forged), [])

    def test_ac3_step3_forged_copy_without_the_assumption_fails(self):
        forged = without_sentences(step3_section(), "Assume", "canonical absolute path")
        self.assertEqual(len(check_cd_target_statement(forged)), 1)

    def test_ac3_step3_forged_copy_that_asks_for_resolution_fails(self):
        forged = (
            "Before the cd, resolve `worktree_path` with realpath and cd into "
            "the result."
        )
        self.assertNotEqual(check_cd_target_statement(forged), [])

    def test_ac3_gate_states_the_cd_target_and_the_assumption(self):
        self.assertEqual(check_cd_target_statement(gate_section()), [])

    def test_ac3_gate_forged_copy_without_the_statement_fails(self):
        forged = without_sentences(gate_section(), "cd target", "`worktree_path`")
        self.assertNotEqual(check_cd_target_statement(forged), [])

    def test_ac3_gate_forged_copy_without_the_assumption_fails(self):
        forged = without_sentences(gate_section(), "Assume", "canonical absolute path")
        self.assertEqual(len(check_cd_target_statement(forged)), 1)

    def test_ac3_gate_forged_copy_that_asks_for_resolution_fails(self):
        forged = (
            "Run each string after you resolve the cd target to its real "
            "path."
        )
        self.assertNotEqual(check_cd_target_statement(forged), [])


class TestAC4CitesTheRuleAndDoesNotRestateIt(unittest.TestCase):
    """AC-4 (FR7, FR8; TS14): the changed places cite the Verbatim execution
    rule; none restates the path conditions."""

    def test_ac4_producer_step_cites_the_rule(self):
        self.assertEqual(
            check_cites_rule(i2a_section(), "strict realpath", "worktree exists"), []
        )

    def test_ac4_step3_cites_the_rule(self):
        self.assertEqual(
            check_cites_rule(step3_section(), "cd target", "`worktree_path`"), []
        )

    def test_ac4_gate_cites_the_rule(self):
        self.assertEqual(
            check_cites_rule(gate_section(), "cd target", "`worktree_path`"), []
        )

    def test_ac4_citation_check_flags_a_block_without_the_citation(self):
        forged = (
            "The cd target is `worktree_path` exactly as supplied. Assume "
            "`worktree_path` is a canonical absolute path."
        )
        self.assertNotEqual(
            check_cites_rule(forged, "cd target", "`worktree_path`"), []
        )

    def test_ac4_no_changed_section_restates_the_path_conditions(self):
        for name, getter in (
            (I2A_NAME, i2a_section),
            (INPUTS_NAME, inputs_section),
            (STEP_3_NAME, step3_section),
            (GATE_NAME, gate_section),
        ):
            with self.subTest(section=name):
                self.assertEqual(find_condition_restatements(getter()), [])

    def test_ac4_restatement_check_flags_forged_restatements(self):
        for forged in (FORGED_RESTATEMENT, FORGED_RESTATEMENT_PLAN_EXAMPLE):
            with self.subTest(forged=forged[:40]):
                self.assertNotEqual(find_condition_restatements(forged), [])

    def test_ac4_restatement_check_flags_a_restatement_added_to_a_live_section(self):
        for getter in (i2a_section, inputs_section, step3_section, gate_section):
            with self.subTest(getter=getter.__name__):
                forged = getter() + "\n\n" + FORGED_RESTATEMENT + "\n"
                self.assertNotEqual(find_condition_restatements(forged), [])

    def test_ac4_restatement_check_accepts_a_citing_sentence(self):
        citing = (
            "Assume `worktree_path` is a canonical absolute path, the form that "
            f"the {RULE_NAME} of `{PROTOCOL_CITATION}` describes."
        )
        self.assertEqual(find_condition_restatements(citing), [])

    def test_ac4_this_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])


class TestControlCharStopLiveDocument(unittest.TestCase):
    """AC-3 (worktree-path-control-char-stop task0001): Step I.2.a of
    implement-phase.md stops the phase when a canonical worktree_path of a
    selected task carries a control character."""

    def test_ac3_live_check_applies_to_every_selected_task(self):
        self.assertEqual(check_control_char_scope(i2a_section()), [])

    def test_ac3_live_check_names_the_full_rejected_set(self):
        self.assertEqual(check_control_char_rejected_set(i2a_section()), [])

    def test_ac3_live_check_stops_before_any_launch_prompt(self):
        self.assertEqual(check_control_char_stop(i2a_section()), [])

    def test_ac2_live_check_sits_between_the_canonicalization_and_the_launch(self):
        self.assertEqual(check_control_char_placement(i2a_section()), [])

    def test_ac3_live_section_yields_no_problem(self):
        self.assertEqual(_all_control_char_problems(i2a_section()), [])

    def test_ac3_the_check_paragraph_is_one_block(self):
        self.assertEqual(len(_control_check_blocks(i2a_section())), 1)


class TestControlCharStopForgedCopies(unittest.TestCase):
    """AC-4: each forged copy is built from the live section, differs from it,
    and yields at least one problem."""

    def test_ac4_forged_copy_without_the_check_paragraph_fails(self):
        section = i2a_section()
        forged = _remove_paragraph_with(section, CONTROL_CHECK_LOCATOR)
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_scope(forged), [])
        self.assertNotEqual(check_control_char_rejected_set(forged), [])
        self.assertNotEqual(check_control_char_stop(forged), [])
        self.assertNotEqual(check_control_char_placement(forged), [])

    def test_ac4_forged_copy_with_the_rejected_set_reduced_to_the_line_feed_fails(self):
        section = i2a_section()
        forged = section
        for code_range in CONTROL_CHECK_REJECTED_RANGES:
            forged = _replace_phrase(forged, code_range, "U+000A")
        self.assertNotEqual(forged, section)
        problems = check_control_char_rejected_set(forged)
        self.assertEqual(len(problems), len(CONTROL_CHECK_REJECTED_RANGES), problems)

    def test_ac4_forged_copy_that_names_one_range_less_fails(self):
        for code_range in CONTROL_CHECK_REJECTED_RANGES:
            with self.subTest(code_range=code_range):
                section = i2a_section()
                forged = _replace_phrase(section, code_range, "U+000A")
                self.assertNotEqual(forged, section)
                self.assertNotEqual(check_control_char_rejected_set(forged), [])

    def test_ac4_forged_copy_that_escapes_the_characters_and_continues_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_ABORT_PHRASE,
            "escape the characters and continue with the implement phase",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_stop(forged), [])

    def test_ac4_forged_copy_with_the_check_after_the_launch_loop_fails(self):
        section = i2a_section()
        forged = _move_paragraph_before(
            section, (CONTROL_CHECK_LOCATOR,), LAUNCH_LOOP_OPENING
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_placement(forged), [])

    def test_ac4_forged_copy_with_the_check_before_the_canonicalization_fails(self):
        section = i2a_section()
        forged = _move_paragraph_before(
            section, (CONTROL_CHECK_LOCATOR,), RESUME_GUARD_PARAGRAPH_OPENING
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_placement(forged), [])

    def test_ac4_forged_copy_with_the_check_after_the_approval_gate_fails(self):
        section = i2a_section()
        forged = _move_paragraph_before(
            section, (CONTROL_CHECK_LOCATOR,), GATE_PARAGRAPH_OPENING
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_placement(forged), [])

    def test_ac4_forged_copy_with_the_scope_narrowed_to_one_task_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section, CONTROL_CHECK_SCOPE_PHRASE, "the task being launched"
        )
        forged = _replace_phrase(forged, CONTROL_CHECK_ALL_TASKS_PHRASE, "that task")
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_scope(forged), [])

    def test_ac4_forged_copy_with_the_scope_narrowed_to_the_current_task_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_ALL_TASKS_PHRASE,
            "the current task only",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_scope(forged), [])

    def test_ac4_forged_copy_without_the_report_of_the_offending_ids_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section, CONTROL_CHECK_REPORT_PHRASE + ",", ""
        )
        self.assertNotEqual(forged, section)
        self.assertNotIn(CONTROL_CHECK_REPORT_PHRASE, _normalize_ws(forged))
        self.assertNotEqual(check_control_char_stop(forged), [])

    def test_ac4_forged_copy_that_still_builds_a_launch_prompt_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_NO_PROMPT_PHRASE,
            "build the launch prompts of the clean tasks",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_stop(forged), [])

    def test_ac4_forged_copy_that_allows_stripping_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_NO_SANITIZE_PHRASE,
            "Strip the characters",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_stop(forged), [])

    def test_ac4_forged_copy_that_falls_back_to_the_unresolved_path_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_NO_FALLBACK_PHRASE,
            "fall back to the unresolved path string",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_stop(forged), [])

    def test_ac4_replace_phrase_fails_loudly_when_nothing_matches(self):
        with self.assertRaises(AssertionError):
            _replace_phrase("some text", "absent phrase", "x")


def _keeps_pre_change_paragraph(section):
    """True when the one control-character check paragraph of `section` still
    begins with the paragraph's pre-change text, sentence for sentence."""
    paragraphs = _control_check_blocks(section)
    return len(paragraphs) == 1 and paragraphs[0].startswith(
        _normalize_ws(PRE_CHANGE_CONTROL_CHECK_PARAGRAPH)
    )


class TestControlCharTerminalHandlingLiveDocument(unittest.TestCase):
    """AC-1 to AC-4 (control-char-abort-terminal-state task0001): the
    control-character check paragraph of Step I.2.a ends the implement phase
    in the terminal state taken from Step I.2.c's abort phase."""

    def _paragraph(self):
        paragraphs = _control_check_blocks(i2a_section())
        self.assertEqual(len(paragraphs), 1)
        return paragraphs[0]

    def test_ac1_live_check_finds_the_abort_phase_write_and_commit(self):
        self.assertEqual(check_control_char_terminal_handling(i2a_section()), [])

    def test_ac1_every_checked_element_is_absent_from_the_pre_change_paragraph(self):
        pre_change = _normalize_ws(PRE_CHANGE_CONTROL_CHECK_PARAGRAPH)
        for label, phrase in CONTROL_CHECK_TERMINAL_ELEMENTS:
            with self.subTest(element=label):
                self.assertNotIn(phrase, pre_change)
        for phrase in (
            CONTROL_CHECK_TERMINAL_START_PHRASE,
            CONTROL_CHECK_KIND_UNCONDITIONAL_PHRASE,
            CONTROL_CHECK_NO_EXTRA_WRITES_PHRASE,
            CONTROL_CHECK_NO_WAIT_PHRASE,
            CONTROL_CHECK_STOP_CONDITION_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, pre_change)

    def test_ac1_added_text_cites_the_abort_phase_and_does_not_restate_it(self):
        added = _terminal_handling_text(i2a_section())
        for restated in ("reset --hard", "rev-parse", "$", "ABORT_TIP", "TERMINAL_TIP"):
            with self.subTest(restated=restated):
                self.assertNotIn(restated, added)

    def test_ac2_live_paragraph_states_no_needs_update_status_write_or_cleanup(self):
        self.assertIn(CONTROL_CHECK_NO_EXTRA_WRITES_PHRASE, self._paragraph())

    def test_ac2_live_paragraph_does_not_wait_for_tasks_of_an_earlier_refill(self):
        self.assertIn(CONTROL_CHECK_NO_WAIT_PHRASE, self._paragraph())

    def test_ac2_live_paragraph_returns_control_through_stop_condition_3(self):
        self.assertIn(CONTROL_CHECK_STOP_CONDITION_PHRASE, self._paragraph())

    def test_ac3_live_paragraph_gives_decision_unconditionally(self):
        self.assertIn(CONTROL_CHECK_KIND_UNCONDITIONAL_PHRASE, self._paragraph())

    def test_ac3_live_paragraph_names_no_other_failed_kind_value(self):
        self.assertNotIn("`infra`", self._paragraph())

    def test_ac4_existing_stop_check_still_passes(self):
        self.assertEqual(check_control_char_stop(i2a_section()), [])

    def test_ac4_added_text_never_uses_the_abort_sentence_phrase(self):
        added = _normalize_ws(_terminal_handling_text(i2a_section()))
        self.assertNotIn(CONTROL_CHECK_ABORT_PHRASE, added)

    def test_ac4_added_text_stays_inside_the_one_paragraph_block(self):
        added = _terminal_handling_text(i2a_section())
        self.assertIsNone(re.search(r"\n[ \t]*\n", added))
        for line in added.splitlines():
            with self.subTest(line=line):
                self.assertIsNone(_BULLET_START.match(line))
        self.assertTrue(self._paragraph().endswith(_normalize_ws(added)))

    def test_ac4_existing_sentences_of_the_paragraph_are_unchanged(self):
        self.assertTrue(_keeps_pre_change_paragraph(i2a_section()))

    def test_ac4_pre_change_paragraph_text_is_the_paragraph_without_the_added_text(self):
        section = i2a_section()
        forged = _replace_phrase(section, _terminal_handling_text(section), "")
        self.assertEqual(
            _control_check_blocks(forged),
            [_normalize_ws(PRE_CHANGE_CONTROL_CHECK_PARAGRAPH)],
        )


class TestControlCharTerminalHandlingForgedCopies(unittest.TestCase):
    """AC-1, AC-3, AC-4 (control-char-abort-terminal-state task0001): each
    forged copy is built from the live section, differs from it, and yields at
    least one problem."""

    def test_ac1_forged_copy_without_the_terminal_handling_text_fails(self):
        section = i2a_section()
        forged = _replace_phrase(section, _terminal_handling_text(section), "")
        self.assertNotEqual(forged, section)
        problems = check_control_char_terminal_handling(forged)
        self.assertEqual(len(problems), len(CONTROL_CHECK_TERMINAL_ELEMENTS), problems)
        self.assertNotEqual(_all_control_char_problems(forged), [])

    def test_ac1_forged_copy_without_the_terminal_handling_keeps_the_stop_check_green(self):
        section = i2a_section()
        forged = _replace_phrase(section, _terminal_handling_text(section), "")
        self.assertNotEqual(forged, section)
        self.assertEqual(check_control_char_stop(forged), [])
        self.assertEqual(check_control_char_scope(forged), [])
        self.assertEqual(check_control_char_rejected_set(forged), [])
        self.assertEqual(check_control_char_placement(forged), [])

    def test_ac1_forged_copy_that_drops_one_element_names_that_element(self):
        for label, phrase in CONTROL_CHECK_TERMINAL_ELEMENTS:
            with self.subTest(element=label):
                section = i2a_section()
                forged = _replace_phrase(section, phrase, "an unrelated phrase")
                self.assertNotEqual(forged, section)
                problems = check_control_char_terminal_handling(forged)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(label, problems[0])

    def test_ac1_forged_copy_without_the_check_paragraph_fails(self):
        section = i2a_section()
        forged = _remove_paragraph_with(section, CONTROL_CHECK_LOCATOR)
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_terminal_handling(forged), [])

    def test_ac3_forged_copy_with_another_value_in_place_of_decision_fails(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_TERMINAL_KIND_PHRASE,
            "`failed_kind` valued `infra`",
        )
        self.assertNotEqual(forged, section)
        self.assertNotEqual(check_control_char_terminal_handling(forged), [])

    def test_ac4_forged_copy_with_a_reworded_existing_sentence_fails_the_pin(self):
        section = i2a_section()
        forged = _replace_phrase(
            section,
            CONTROL_CHECK_NO_FALLBACK_PHRASE,
            "fall back to the unresolved path string",
        )
        self.assertNotEqual(forged, section)
        self.assertFalse(_keeps_pre_change_paragraph(forged))


if __name__ == "__main__":
    unittest.main()
