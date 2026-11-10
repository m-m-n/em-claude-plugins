"""Tests for the `contributor-consent` skill shipped identically in
em-workflow and em-review.

Covers task0002 Acceptance Criteria (feature-docs/muse-spark-contributor-
consent/tasks/task0002.md):

- AC-1: both skill documents exist at the stated paths, carry valid skill
  frontmatter, and no `commands/` file was added for this feature in either
  plugin.
- AC-2: each document describes the availability probe by reference to its
  own plugin's review-phase definition and states the not-installed exit
  with the exact message, ending the run before any fact collection,
  question or store access.
- AC-3: each document presents exactly three facts as one explicitly
  labeled group, with the fixed labels, the fixed order and the stated
  value vocabulary including the unavailable-value rendering; neither
  document lists the unpushed-commit state as a presented fact.
- AC-4: each document specifies exactly one interactive question round,
  with both state-dependent wordings and two options each, and states that
  dismissal takes the non-mutating branch and writes nothing.
- AC-5: each document queries state through the guard CLI's `--list`, and
  neither document reads or writes the store file directly. (Recording and
  revoking go through the same CLI, which the skill itself runs -- see the
  task0009 and contributor-consent-command-path parts below.)
- AC-6: neither document is referenced from any develop-phase document in
  either plugin (this task never edits an existing file, so it also adds
  no occurrence of the interactive-question tool name to any develop-phase
  or review-phase document -- that half of AC-6 is a structural guarantee
  of the task's file scope rather than a separate assertion here).
- AC-7: this module itself -- imports no third-party package and passes
  under `python3 -m unittest discover -s tests` (verified by running the
  suite, not by a test within this module).

Covers task0009 Acceptance Criteria (feature-docs/muse-spark-contributor-
consent/tasks/task0009.md), restated for the skill-executed design: the
skill is a slash command the user launches, and after the explicit answer of
its one question the skill itself runs the guard CLI -- `--record` after the
consent answer, `--remove` after the revoke answer:

- AC-1: both documents have the skill run the recording command after the
  consent answer and the removal command after the revoke answer, each
  naming that plugin's own guard script and the project-directory option.
  Asserted structurally by the checks of the next part, not by a pinned
  command string.
- AC-2: both documents still describe, in order, the same six steps as
  task0002 (probe/exit, read-only check, three facts, one question round,
  command execution, no-write line on dismissal); neither presents
  unpushed-commit state.
- AC-3: both documents carry the CLI-only line: the skill reaches the
  consent store only through the guard CLI and takes no other route to the
  store file.
- AC-4: neither document gains an occurrence of the interactive-question
  tool name relative to task0002 (still exactly one `AskUserQuestion` per
  document) and neither is referenced by any develop-phase document (reuses
  the AC-6 check above).
- AC-5: both documents keep valid skill frontmatter, no `commands/` file
  was added for either plugin, and the two documents differ only where
  they name their own plugin (asserted structurally).
- AC-6: this module asserts AC-1 through AC-3 and AC-5 mechanically for
  both documents, imports the standard library only, and
  `python3 -m unittest discover -s tests` passes.

Covers contributor-consent-command-path task0001 Acceptance Criteria
(feature-docs/contributor-consent-command-path/SPEC.md and tasks/
task0001.md). The skill itself runs the guard CLI: `--list` in step 2,
`--record` and `--remove` in step 5. The checks are structural. They split a
document into steps, sort every fenced block and every user-facing literal of
step 4 into one of two kinds (a command the skill runs, or text the user
reads), and bind each answer of step 5 to the commands the skill runs for it.
No check matches a whole command string or a path spelling.

- Check 1, classification (`check_classification`): every element is exactly
  one kind; text the user reads holds no unresolved environment-variable
  reference (`${NAME}` or `$NAME`); the commands of step 2 and step 5 are
  classified as run by the skill and carry `--list`, `--record` and
  `--remove`. A reference inside a command the skill runs is never flagged.
- Check 2, branch binding (`check_branch_binding`): the consent branch of
  step 5 is bound to exactly one command carrying `--record` and
  `--project-dir`, the revoke branch to exactly one carrying `--remove` and
  `--project-dir`, the decline and keep branches to none, and step 6 holds no
  guard invocation and outputs the no-write line only.
- Check 3, run statement (`check_run_statement`): every branch bound to a
  command states that the command is run, and step 5 holds no instruction to
  paste or run a command in the user's own terminal.
- Checks 1 and 2 together are THREAT-MODEL.md mitigation TM-1: a mutating
  guard command is reachable only from the explicit consent answer or the
  explicit revoke answer.
- Every check has failing synthetic inputs (NFR4): copies of a real document
  edited by removing, duplicating, moving or inserting blocks and paragraphs,
  and short free-standing strings. Neither kind of input spells out a full
  guard command line.
- Checks 1 to 3 also run on two rewrapped variants of each real document
  (NFR3): one joins each prose paragraph into one line, the other splits it
  at a narrow column. Prose terms are compared with all whitespace removed,
  so a wrap cannot split a term, including in Japanese text.

Frontmatter is parsed with a hand-rolled scalar `key: value` splitter (no
PyYAML), the same dependency-free convention `tests/test_new_worker_agents.py`
documents for agent frontmatter (PyYAML is a plugin runtime dependency, not
a test dependency -- IMPLEMENTATION.md Technology Stack).
"""

import re
import unittest
from collections import namedtuple
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGINS = {
    "em-workflow": {
        "plugin_root": REPO_ROOT / "em-workflow",
        "skill_path": REPO_ROOT
        / "em-workflow"
        / "skills"
        / "contributor-consent"
        / "SKILL.md",
        # em-workflow/references/review-phase.md, "## Phase R0" step 6 is
        # the litellm availability probe definition.
        "probe_step": "6",
    },
    "em-review": {
        "plugin_root": REPO_ROOT / "em-review",
        "skill_path": REPO_ROOT
        / "em-review"
        / "skills"
        / "contributor-consent"
        / "SKILL.md",
        # em-review/references/review-phase.md, "## Phase R0" step 8 is the
        # litellm availability probe definition.
        "probe_step": "8",
    },
}

NOT_INSTALLED_LINE = (
    "vertex-review の LiteLLM ハーネスが見つからない。"
    "contributor ティアはこの環境では使えないため、同意の記録は不要。"
)
NO_WRITE_LINE = "同意ストアは変更していない。"

FACT_LABELS = ["リモートの可視性", "ライセンス", "コントリビューター"]

QUESTION_NOT_CONSENTED = (
    "このリポジトリの差分を muse-spark contributor ティアへ送ることに同意する?"
)
OPTIONS_NOT_CONSENTED = ["同意する", "同意しない"]

QUESTION_ALREADY_CONSENTED = (
    "このリポジトリの contributor ティア同意は記録済み。どうする?"
)
OPTIONS_ALREADY_CONSENTED = ["維持する", "撤回する"]

UNPUSHED_WORDINGS = ["未push", "未プッシュ", "unpushed", "un-pushed"]

STORE_INTERNALS = ["muse-consent.json", "EM_WORKFLOW_MUSE_CONSENT"]

# task0009 AC-3: one exact, single-line sentence (authored to fit on one
# physical source line, so no Japanese no-space line-wrap can silently
# insert a token into the middle of the checked text -- _normalize_ws only
# recovers word-for-word text across a wrap for space-delimited prose).
# CLI_ONLY_LINE states that the skill reaches the consent store only through
# the guard CLI. There is no mechanical enforcement behind it: recording is
# gated by this skill being a user-launched slash command (SPEC a12).
CLI_ONLY_LINE = (
    "ストアに触れる経路はこの CLI だけで、ファイルを直接書き換える手段は取らない。"
)

HEADING_RE = re.compile(r"^#{1,6}\s")

# --- contributor-consent-command-path: structural vocabulary ---------------

# A guard invocation is any text that contains this path segment.
GUARD_PATH_SEGMENT = "hooks/muse_guard.py"

# Fenced guard invocations in these steps are commands the skill runs.
COMMAND_STEPS = (2, 5)
# Fenced blocks that are not guard invocations, in these steps, are text the
# user reads.
VISIBLE_BLOCK_STEPS = (1, 6)

KIND_COMMAND = "command the skill runs"
KIND_VISIBLE = "text the user reads"

# The role of each option of step 4, taken from the option constants that the
# question-round check (task0002 AC-4) already pins.
ROLE_LABELS = {
    "consent": OPTIONS_NOT_CONSENTED[0],
    "decline": OPTIONS_NOT_CONSENTED[1],
    "keep": OPTIONS_ALREADY_CONSENTED[0],
    "revoke": OPTIONS_ALREADY_CONSENTED[1],
}
# The mutating roles: the flag the bound command must carry, and the flag it
# must not carry.
MUTATING_ROLES = {
    "consent": ("--record", "--remove"),
    "revoke": ("--remove", "--record"),
}
PROJECT_DIR_FLAG = "--project-dir"

# Characters skipped before and between option labels at the start of a
# branch paragraph (markup and list separators), after whitespace removal.
LEADING_MARKUP = "*_`>-•"
TRAILING_MARKUP = "*_`"
LABEL_SEPARATORS = "/／、,・と"

# Check 3: the verbs by which a branch states that the command is run, and
# the closed vocabulary of an instruction to use the user's own terminal or to
# copy or paste a command (Japanese and English, matched case-insensitively
# after whitespace removal).
RUN_VERB_TERMS = ("実行する", "実行して", "呼び出す", "呼び出して")
USER_TERMINAL_TERMS = (
    "端末",
    "ターミナル",
    "貼り付",
    "貼付",
    "貼って",
    "貼る",
    "ペースト",
    "コピー",
    "terminal",
    "paste",
    "pasting",
    "copy",
)

# Rewrap variants (NFR3). The narrow column splits the run verb of the
# command-bound branches across two lines.
NARROW_COLUMN = 8
LINE_START_FORBIDDEN = "#>-*+|="

Node = namedtuple("Node", ["kind", "lines"])

FENCE_OPEN_RE = re.compile(r"^\s*```")
FENCE_CLOSE_RE = re.compile(r"^\s*```\s*$")
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
STEP_HEADING_RE = re.compile(r"^###\s+(\d+)\.")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
OPTION_SEPARATOR_RE = re.compile(r"\s*[—–]\s*|\s+-\s+")
UNRESOLVED_REFERENCE_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to a single
    space, so a prose assertion survives a wrap-column edit that changes no
    word. NOT used for line-anchored extraction (headings, bullet counts,
    numbered-list parsing) -- only for multi-word substring checks below."""
    return re.sub(r"\s+", " ", text)


def _squash(text):
    """Remove all whitespace. Term matching in prose compares text and term
    in this form, so a wrap at any column cannot split a term."""
    return re.sub(r"\s+", "", text)


def _split_frontmatter(text):
    """Return (frontmatter_text, body_text) for a `---`-delimited YAML
    frontmatter block, without requiring a YAML parser dependency."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise AssertionError(f"expected a --- delimited frontmatter block, got: {text[:80]!r}")
    return match.group(1), match.group(2)


def _parse_flat_frontmatter(frontmatter_text):
    """Minimal hand-rolled parser for scalar `key: value` frontmatter lines
    (the shape every SKILL.md in this repository uses)."""
    data = {}
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if not kv:
            raise AssertionError(f"could not parse frontmatter line: {line!r}")
        data[kv.group(1)] = kv.group(2).strip()
    return data


def _extract_section(body, heading_pattern):
    """Return the text strictly between the first line matching
    heading_pattern and the next markdown heading line (or EOF)."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(heading_pattern, line):
            start = i + 1
            break
    if start is None:
        raise AssertionError(f"heading not found: {heading_pattern!r}")
    end = len(lines)
    for j in range(start, len(lines)):
        if HEADING_RE.match(lines[j]):
            end = j
            break
    return "\n".join(lines[start:end])


def _skill_body(plugin):
    _fm, body = _split_frontmatter(_read(PLUGINS[plugin]["skill_path"]))
    return body


# --- document model: nodes, steps, elements --------------------------------


def _parse_nodes(body):
    """Split a body into nodes in document order: a heading (one line), a
    fenced block (its fence lines included) or a paragraph (a run of
    non-blank lines outside fenced blocks, headings excluded)."""
    nodes = []
    paragraph = []
    lines = body.splitlines()

    def flush():
        nonlocal paragraph
        if paragraph:
            nodes.append(Node("para", paragraph))
            paragraph = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if FENCE_OPEN_RE.match(line):
            flush()
            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                closing = FENCE_CLOSE_RE.match(lines[i]) is not None
                i += 1
                if closing:
                    break
            nodes.append(Node("fence", block))
            continue
        if MD_HEADING_RE.match(line):
            flush()
            nodes.append(Node("heading", [line]))
        elif line.strip():
            paragraph.append(line)
        else:
            flush()
        i += 1
    flush()
    return nodes


def _render(nodes):
    return "\n\n".join("\n".join(node.lines) for node in nodes) + "\n"


def _fence_text(node):
    inner = node.lines[1:]
    if inner and FENCE_CLOSE_RE.match(inner[-1]):
        inner = inner[:-1]
    return "\n".join(inner)


def _node_text(node):
    return _fence_text(node) if node.kind == "fence" else "\n".join(node.lines)


def _node_steps(nodes):
    """The step of each node. Step N runs from the `### N.` heading up to the
    next heading of level 1, 2 or 3; level-4 headings stay inside their step.
    The preamble, the `## 手順` heading and the constraints section belong to
    no step (None)."""
    steps = []
    current = None
    for node in nodes:
        if node.kind == "heading":
            level = len(MD_HEADING_RE.match(node.lines[0]).group(1))
            if level <= 3:
                match = STEP_HEADING_RE.match(node.lines[0])
                current = int(match.group(1)) if match else None
        steps.append(current)
    return steps


def _entries(body):
    nodes = _parse_nodes(body)
    return list(zip(_node_steps(nodes), nodes))


def _render_entries(entries):
    return _render([node for _step, node in entries])


def _step_nodes(entries, step):
    return [node for s, node in entries if s == step]


def _step_text(entries, step):
    return "\n".join(_node_text(node) for node in _step_nodes(entries, step))


def _is_guard_invocation(text):
    return GUARD_PATH_SEGMENT in text


def _has_flag(text, flag):
    return re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", text) is not None


def _unresolved_references(text):
    """`${NAME}` and `$NAME` (NAME: a letter or underscore, then letters,
    digits or underscores). A command substitution `$(...)` is not one."""
    return UNRESOLVED_REFERENCE_RE.findall(text)


def _fence_kind(step, text):
    guard = _is_guard_invocation(text)
    if guard and step in COMMAND_STEPS:
        return KIND_COMMAND
    if not guard and step in VISIBLE_BLOCK_STEPS:
        return KIND_VISIBLE
    return None


def _option_label(item):
    """The text of an option list item before its description separator."""
    return OPTION_SEPARATOR_RE.split(item, maxsplit=1)[0].strip()


def _option_lists(entries):
    """The option lists of step 4: for each list paragraph, the labels of
    its items in order."""
    lists = []
    for node in _step_nodes(entries, 4):
        if node.kind != "para":
            continue
        items = []
        for line in node.lines:
            match = re.match(r"^-\s+(.*)$", line)
            if match:
                items.append(match.group(1))
            elif items:
                items[-1] += " " + line.strip()
        if items:
            lists.append([_option_label(item) for item in items])
    return lists


def _option_roles(entries, failures):
    """Role -> label (whitespace removed), from the two option lists of
    step 4: consent and decline for the not-consented list, keep and revoke
    for the consented list. None, with a failure recorded, when the lists do
    not have that shape or a label differs from the pinned option constant."""
    lists = _option_lists(entries)
    if len(lists) != 2 or any(len(options) != 2 for options in lists):
        failures.append(
            "option-lists: expected two option lists of two options, got "
            f"{[len(options) for options in lists]}"
        )
        return None
    parsed = {
        "consent": lists[0][0],
        "decline": lists[0][1],
        "keep": lists[1][0],
        "revoke": lists[1][1],
    }
    roles = {}
    for role, label in parsed.items():
        if _squash(label) != _squash(ROLE_LABELS[role]):
            failures.append(
                f"option-role[{role}]: step 4 label {label!r} differs from "
                f"the pinned option {ROLE_LABELS[role]!r}"
            )
            return None
        roles[role] = _squash(label)
    return roles


def _leading_roles(text, role_labels):
    """The roles whose labels a paragraph begins with, in order. One
    paragraph may name several labels, separated by LABEL_SEPARATORS."""
    rest = _squash(text).lstrip(LEADING_MARKUP)
    roles = []
    while True:
        for role, label in role_labels.items():
            if rest.startswith(label):
                roles.append(role)
                rest = rest[len(label) :].lstrip(TRAILING_MARKUP + LABEL_SEPARATORS)
                break
        else:
            return roles


def _step5_branches(entries, role_labels):
    """The branches of step 5 and the guard commands bound to them. A branch
    is a paragraph that begins with one or more option labels; the commands
    bound to it are the skill-executed commands between it and the next
    branch paragraph or the end of step 5. Commands before the first branch
    paragraph are unbound."""
    branches = []
    unbound = []
    current = None
    for node in _step_nodes(entries, 5):
        if node.kind == "para":
            text = "\n".join(node.lines)
            roles = _leading_roles(text, role_labels)
            if roles:
                current = {"roles": roles, "text": text, "commands": []}
                branches.append(current)
        elif node.kind == "fence":
            text = _fence_text(node)
            if _is_guard_invocation(text):
                if current is None:
                    unbound.append(text)
                else:
                    current["commands"].append(text)
    return branches, unbound


# --- the three checks -------------------------------------------------------
# Each check takes the body of one skill copy and returns the list of its
# failures; an empty list means the check passes. A failure is a string that
# starts with a short code, then a colon.


def check_classification(body):
    """Check 1 (FR4): every element is exactly one kind, no text the user
    reads holds an unresolved environment-variable reference, and the
    commands of step 2 and step 5 are classified as run by the skill."""
    entries = _entries(body)
    failures = []
    commands = {step: [] for step in COMMAND_STEPS}
    visible = []  # (description, text)

    for step, node in entries:
        if node.kind != "fence":
            continue
        text = _fence_text(node)
        where = "outside any step" if step is None else f"step {step}"
        kind = _fence_kind(step, text)
        if kind == KIND_COMMAND:
            commands[step].append(text)
        elif kind == KIND_VISIBLE:
            visible.append((f"fenced block in {where}", step, text))
        else:
            first = text.strip().splitlines()[0][:40] if text.strip() else ""
            failures.append(f"unclassified-element: fenced block {where}: {first!r}")

    for step, node in entries:
        if step == 4 and node.kind in ("heading", "para"):
            for match in INLINE_CODE_RE.finditer("\n".join(node.lines)):
                visible.append(("inline code span in step 4", 4, match.group(1)))
    for options in _option_lists(entries):
        for label in options:
            visible.append(("option label in step 4", 4, label))

    # non-vacuity: the places that hold text the user reads were found
    for step in VISIBLE_BLOCK_STEPS:
        if not any(s == step and w.startswith("fenced block") for w, s, _t in visible):
            failures.append(f"missing-visible-text: step {step} holds no block")
    for what in ("inline code span in step 4", "option label in step 4"):
        if not any(w == what for w, _s, _t in visible):
            failures.append(f"missing-visible-text: no {what}")

    for where, _step, text in visible:
        references = _unresolved_references(text)
        if references:
            failures.append(f"unresolved-reference: {where}: {references}")

    if not any(_has_flag(text, "--list") for text in commands[2]):
        failures.append("missing-command: step 2 holds no command with --list")
    for flag in ("--record", "--remove"):
        if not any(_has_flag(text, flag) for text in commands[5]):
            failures.append(f"missing-command: step 5 holds no command with {flag}")
    return failures


def check_branch_binding(body):
    """Check 2 (FR3, TM-1): each answer of step 5 is bound to the commands
    the skill runs for it, and nothing else reaches a mutating command."""
    entries = _entries(body)
    failures = []

    for step in (5, 6):
        if not _step_nodes(entries, step):
            failures.append(f"missing-step: step {step} not found")
    role_labels = _option_roles(entries, failures)

    if role_labels is not None and _step_nodes(entries, 5):
        branches, unbound = _step5_branches(entries, role_labels)
        for text in unbound:
            failures.append(f"unbound-command: a command precedes every branch: {text!r}")
        for role in ("consent", "revoke", "decline", "keep"):
            named = [branch for branch in branches if role in branch["roles"]]
            if not named:
                failures.append(f"missing-branch[{role}]: no branch paragraph begins with its label")
                continue
            bound = [text for branch in named for text in branch["commands"]]
            if role not in MUTATING_ROLES:
                if bound:
                    failures.append(f"command-bound[{role}]: {len(bound)} command(s) bound")
                continue
            required, forbidden = MUTATING_ROLES[role]
            if len(bound) != 1:
                failures.append(f"command-count[{role}]: expected 1 command, got {len(bound)}")
                continue
            command = bound[0]
            if not (
                _is_guard_invocation(command)
                and _has_flag(command, required)
                and _has_flag(command, PROJECT_DIR_FLAG)
                and not _has_flag(command, forbidden)
            ):
                failures.append(
                    f"command-content[{role}]: the command must name the guard, "
                    f"{required} and {PROJECT_DIR_FLAG}, and not {forbidden}"
                )

    # a mutating flag in a fenced block outside step 5 reaches no branch
    for step, node in entries:
        if node.kind == "fence" and step != 5:
            text = _fence_text(node)
            if _has_flag(text, "--record") or _has_flag(text, "--remove"):
                failures.append(f"mutating-outside-step5: fenced block in step {step}")

    # step 6 runs nothing and outputs the no-write line only
    step6 = _step_nodes(entries, 6)
    if step6:
        if _is_guard_invocation("\n".join(_node_text(node) for node in step6)):
            failures.append("step6-guard-invocation: step 6 names the guard")
        blocks = [
            _fence_text(node)
            for node in step6
            if node.kind == "fence" and not _is_guard_invocation(_fence_text(node))
        ]
        if len(blocks) != 1 or _squash(blocks[0]) != _squash(NO_WRITE_LINE):
            failures.append(
                "step6-block: step 6 must hold exactly one user-visible block, "
                f"the no-write line; got {len(blocks)}"
            )
    return failures


def check_run_statement(body):
    """Check 3 (FR5): every branch bound to a command states that the
    command is run, and step 5 holds no instruction to use the user's own
    terminal or to copy or paste a command."""
    entries = _entries(body)
    failures = []

    if not _step_nodes(entries, 5):
        failures.append("missing-step: step 5 not found")
        return failures
    role_labels = _option_roles(entries, failures)
    if role_labels is not None:
        branches, _unbound = _step5_branches(entries, role_labels)
        bound = [branch for branch in branches if branch["commands"]]
        if not bound:
            failures.append("no-bound-branch: no branch of step 5 is bound to a command")
        for branch in bound:
            if not any(_squash(term) in _squash(branch["text"]) for term in RUN_VERB_TERMS):
                failures.append(
                    "no-run-statement: a command-bound branch does not state that "
                    f"the command is run: {_squash(branch['text'])[:30]!r}"
                )

    text = _squash(_step_text(entries, 5)).lower()
    for term in USER_TERMINAL_TERMS:
        if _squash(term).lower() in text:
            failures.append(f"user-terminal-instruction: step 5 contains {term!r}")
    return failures


def _codes(failures):
    return [failure.split(":", 1)[0] for failure in failures]


# --- rewrap variants --------------------------------------------------------


def _is_prose_paragraph(node):
    return node.kind == "para" and not any(LIST_ITEM_RE.match(line) for line in node.lines)


def _tokens(text):
    """Characters, with each inline code span kept whole."""
    tokens = []
    position = 0
    for match in re.finditer(r"`[^`]+`", text):
        tokens.extend(text[position : match.start()])
        tokens.append(match.group(0))
        position = match.end()
    tokens.extend(text[position:])
    return tokens


def _wrap(text, width):
    """Split text into lines of about `width` characters. It never splits
    inside an inline code span, and never starts a line with a character
    that would turn it into a heading, a list item or a quote."""
    lines = []
    current = ""
    for token in _tokens(text):
        can_break = (
            len(current) >= width
            and current.strip()
            and not token.isspace()
            and token[0] not in LINE_START_FORBIDDEN
            and not token[0].isdigit()
        )
        if can_break:
            lines.append(current.strip())
            current = ""
        current += token
    if current.strip():
        lines.append(current.strip())
    return lines


def _reflowed(body, reflow):
    nodes = []
    for node in _parse_nodes(body):
        if _is_prose_paragraph(node):
            joined = " ".join(line.strip() for line in node.lines)
            node = Node("para", reflow(joined))
        nodes.append(node)
    return _render(nodes)


def _joined_variant(body):
    return _reflowed(body, lambda text: [text])


def _narrow_variant(body):
    return _reflowed(body, lambda text: _wrap(text, NARROW_COLUMN))


# --- synthetic inputs: edits of a real copy --------------------------------


def _command_with(flag):
    def matches(node):
        if node.kind != "fence":
            return False
        text = _fence_text(node)
        return _is_guard_invocation(text) and _has_flag(text, flag)

    return matches


def _find_command(entries, flag):
    for index, (_step, node) in enumerate(entries):
        if _command_with(flag)(node):
            return index
    raise AssertionError(f"synthetic input needs a {flag} command in the copy")


def _end_of_step(entries, step):
    """The index just after the last node of the step."""
    indexes = [i for i, (s, _node) in enumerate(entries) if s == step]
    if not indexes:
        raise AssertionError(f"synthetic input needs step {step} in the copy")
    return indexes[-1] + 1


def _branch_index(entries, role):
    labels = {r: _squash(label) for r, label in ROLE_LABELS.items()}
    for index, (step, node) in enumerate(entries):
        if step == 5 and node.kind == "para":
            if role in _leading_roles("\n".join(node.lines), labels):
                return index
    raise AssertionError(f"synthetic input needs the {role} branch in step 5")


def _without_command(body, flag):
    entries = _entries(body)
    del entries[_find_command(entries, flag)]
    return _render_entries(entries)


def _with_command_copy(body, flag, *, step=None, after_role=None):
    """Copy the real `flag` command to the end of `step`, or right after the
    branch paragraph of `after_role` in step 5."""
    entries = _entries(body)
    node = entries[_find_command(entries, flag)][1]
    if after_role is not None:
        index, target = _branch_index(entries, after_role) + 1, 5
    else:
        index, target = _end_of_step(entries, step), step
    entries.insert(index, (target, node))
    return _render_entries(entries)


def _with_command_before_branches(body, flag):
    """Move the real `flag` command to the start of step 5, before every
    branch paragraph."""
    entries = _entries(body)
    _step, node = entries.pop(_find_command(entries, flag))
    first = min(i for i, (s, _n) in enumerate(entries) if s == 5)
    entries.insert(first + 1, (5, node))
    return _render_entries(entries)


def _with_edited_command(body, flag, edit):
    entries = _entries(body)
    index = _find_command(entries, flag)
    step, node = entries[index]
    old = _fence_text(node)
    new = edit(old)
    assert new != old, "synthetic edit changed nothing"
    entries[index] = (step, Node("fence", [node.lines[0], new, node.lines[-1]]))
    return _render_entries(entries)


def _with_block(body, step, content):
    """Insert a free-standing fenced block at the end of the step."""
    entries = _entries(body)
    node = Node("fence", ["```", content, "```"])
    entries.insert(_end_of_step(entries, step), (step, node))
    return _render_entries(entries)


def _with_paragraph(body, step, text):
    entries = _entries(body)
    node = Node("para", [text])
    entries.insert(_end_of_step(entries, step), (step, node))
    return _render_entries(entries)


def _with_edited_visible_block(body, step, edit):
    """Edit the user-visible fenced block of the step."""
    entries = _entries(body)
    for index, (s, node) in enumerate(entries):
        if s == step and node.kind == "fence" and not _is_guard_invocation(_fence_text(node)):
            old = _fence_text(node)
            new = edit(old)
            assert new != old, "synthetic edit changed nothing"
            entries[index] = (s, Node("fence", [node.lines[0], new, node.lines[-1]]))
            return _render_entries(entries)
    raise AssertionError(f"synthetic input needs a user-visible block in step {step}")


def _with_edited_step4_span(body, suffix):
    """Append the suffix to the first inline code span of step 4."""
    entries = _entries(body)
    for index, (s, node) in enumerate(entries):
        if s == 4 and node.kind == "para" and INLINE_CODE_RE.search("\n".join(node.lines)):
            text = INLINE_CODE_RE.sub(
                lambda m: f"`{m.group(1)}{suffix}`", "\n".join(node.lines), count=1
            )
            entries[index] = (s, Node("para", text.split("\n")))
            return _render_entries(entries)
    raise AssertionError("synthetic input needs an inline code span in step 4")


def _with_edited_first_option_label(body, suffix):
    """Append the suffix to the label of the first option of step 4."""
    entries = _entries(body)
    for index, (s, node) in enumerate(entries):
        if s == 4 and node.kind == "para" and node.lines[0].startswith("- "):
            first = OPTION_SEPARATOR_RE.sub(lambda m: f"{suffix}{m.group(0)}", node.lines[0], count=1)
            assert first != node.lines[0], "synthetic edit changed nothing"
            entries[index] = (s, Node("para", [first] + node.lines[1:]))
            return _render_entries(entries)
    raise AssertionError("synthetic input needs an option list in step 4")


def _with_edited_branch(body, role, edit):
    """Replace the branch paragraph of the role by the edited one-line text."""
    entries = _entries(body)
    index = _branch_index(entries, role)
    step, node = entries[index]
    old = " ".join(line.strip() for line in node.lines)
    new = edit(old)
    assert new != old, "synthetic edit changed nothing"
    entries[index] = (step, Node("para", [new]))
    return _render_entries(entries)


def _without_run_verbs(text):
    squashed = _squash(text)
    for term in RUN_VERB_TERMS:
        squashed = squashed.replace(term, "示す")
    return squashed


class ContributorConsentSkillTest(unittest.TestCase):
    def _load(self, plugin):
        info = PLUGINS[plugin]
        text = _read(info["skill_path"])
        fm_text, body = _split_frontmatter(text)
        return _parse_flat_frontmatter(fm_text), body

    # AC-1
    def test_ac1_files_exist_with_valid_frontmatter_and_no_commands_dir(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                self.assertTrue(
                    info["skill_path"].is_file(),
                    f"missing {info['skill_path']}",
                )
                fm, _body = self._load(plugin)
                self.assertEqual(fm.get("name"), "contributor-consent")
                self.assertTrue(fm.get("description"))

                commands_dir = info["plugin_root"] / "commands"
                if commands_dir.is_dir():
                    for f in commands_dir.rglob("*"):
                        self.assertNotIn(
                            "contributor-consent",
                            f.name,
                            f"unexpected commands/ file for this feature: {f}",
                        )

    # AC-2
    def test_ac2_probe_by_reference_and_not_installed_exit(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                self.assertIn("review-phase.md", body)
                self.assertIn(f"Phase R0 手順 {info['probe_step']}", body)

                step1 = _extract_section(body, r"^### 1\.")
                self.assertIn(NOT_INSTALLED_LINE, step1)
                self.assertIn(
                    "事実収集・質問・ストアへのアクセスを一切行わずに終了する",
                    _normalize_ws(step1),
                )
                # the exit happens inside step 1, strictly before step 2
                # (state determination), step 3 (facts) and step 4
                # (question) begin
                self.assertLess(
                    body.index("### 1."),
                    body.index("### 2."),
                )
                self.assertLess(body.index("### 2."), body.index("### 3."))
                self.assertLess(body.index("### 3."), body.index("### 4."))

    # AC-3
    def test_ac3_exactly_three_facts_fixed_labels_order_and_vocabulary(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                facts_heading_idx = body.index("提示する 3 つの事実")
                step3 = _extract_section(body, r"^### 3\.")

                # the subject line is described before the facts heading,
                # inside step 3, and is never itself inside the facts list
                self.assertLess(body.index("### 3."), facts_heading_idx)
                subject_prose = body[body.index("### 3.") : facts_heading_idx]
                self.assertIn("対象", subject_prose)
                self.assertIn("同じキーを共有", subject_prose)

                facts_section = _extract_section(
                    body, r"^#### 提示する 3 つの事実"
                )
                item_lines = re.findall(
                    r"^\d+\.\s+\*\*(.+?)\*\*:\s*(.*)$",
                    facts_section,
                    re.MULTILINE,
                )
                self.assertEqual(
                    len(item_lines),
                    3,
                    f"expected exactly 3 labeled facts, got: {item_lines}",
                )
                labels = [label for label, _value in item_lines]
                self.assertEqual(labels, FACT_LABELS)

                by_label = dict(item_lines)
                self.assertIn("public", by_label["リモートの可視性"])
                self.assertIn("private", by_label["リモートの可視性"])
                self.assertIn("internal", by_label["リモートの可視性"])
                self.assertIn("取得できず", by_label["リモートの可視性"])

                self.assertIn("なし", by_label["ライセンス"])
                self.assertIn("取得できず", by_label["ライセンス"])

                self.assertIn("あなたのみ", by_label["コントリビューター"])
                self.assertIn("あなたを含む N 名", by_label["コントリビューター"])
                self.assertIn("取得できず", by_label["コントリビューター"])

                # each fixed label occurs exactly once within the group
                for label in FACT_LABELS:
                    self.assertEqual(
                        facts_section.count(f"**{label}**"),
                        1,
                        f"{label} should appear exactly once in the facts group",
                    )

                for wording in UNPUSHED_WORDINGS:
                    self.assertNotIn(wording, body)

    # AC-4
    def test_ac4_exactly_one_question_round_with_two_options_each(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                self.assertEqual(
                    body.count("AskUserQuestion"),
                    1,
                    "expected exactly one interactive-question construct",
                )

                not_consented = _extract_section(
                    body, r"^#### 未同意のとき"
                )
                self.assertIn(QUESTION_NOT_CONSENTED, not_consented)
                for option in OPTIONS_NOT_CONSENTED:
                    self.assertIn(f"- {option}", not_consented)
                self.assertEqual(
                    len(re.findall(r"^- ", not_consented, re.MULTILINE)), 2
                )

                already_consented = _extract_section(
                    body, r"^#### 同意済みのとき"
                )
                self.assertIn(QUESTION_ALREADY_CONSENTED, already_consented)
                for option in OPTIONS_ALREADY_CONSENTED:
                    self.assertIn(f"- {option}", already_consented)
                self.assertEqual(
                    len(re.findall(r"^- ", already_consented, re.MULTILINE)), 2
                )

                step6 = _extract_section(body, r"^### 6\.")
                self.assertIn(NO_WRITE_LINE, step6)
                self.assertIn("非破壊側", step6)
                self.assertIn("CLI を呼び出さず", step6)

    # AC-5
    def test_ac5_record_remove_via_cli_never_the_store_file(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)

                self.assertIn("--record", body)
                self.assertIn("--remove", body)
                self.assertIn("--list", body)
                self.assertIn(
                    "ストアファイルを直接読み書きしない", body
                )

                for internal in STORE_INTERNALS:
                    self.assertNotIn(internal, body)

    # AC-6
    def test_ac6_no_develop_phase_document_references_the_skill(self):
        skill_paths = {info["skill_path"] for info in PLUGINS.values()}
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                for md_path in info["plugin_root"].rglob("*.md"):
                    if md_path in skill_paths:
                        continue
                    text = _read(md_path)
                    self.assertNotIn(
                        "contributor-consent",
                        text,
                        f"{md_path} unexpectedly references the skill",
                    )

    # task0009 AC-2
    def test_task0009_ac2_all_six_steps_present_in_order(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                positions = [body.index(f"### {n}.") for n in range(1, 7)]
                self.assertEqual(positions, sorted(positions))
                for wording in UNPUSHED_WORDINGS:
                    self.assertNotIn(wording, body)

    # task0009 AC-3
    def test_task0009_ac3_store_is_reached_only_through_the_cli(self):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                _fm, body = self._load(plugin)
                self.assertIn(CLI_ONLY_LINE, body)

    # task0009 AC-5
    def test_task0009_ac5_valid_frontmatter_and_only_plugin_naming_differs(
        self,
    ):
        for plugin, info in PLUGINS.items():
            with self.subTest(plugin=plugin):
                fm, _body = self._load(plugin)
                self.assertEqual(fm.get("name"), "contributor-consent")
                self.assertTrue(fm.get("description"))

                commands_dir = info["plugin_root"] / "commands"
                if commands_dir.is_dir():
                    for f in commands_dir.rglob("*"):
                        self.assertNotIn(
                            "contributor-consent",
                            f.name,
                            f"unexpected commands/ file for this feature: {f}",
                        )

        # structural cross-plugin equality: normalize the two known,
        # documented divergences (own plugin name; own review-phase step
        # number) and assert the two documents are then identical, so any
        # other drift between them fails this test
        workflow_info = PLUGINS["em-workflow"]
        review_info = PLUGINS["em-review"]
        workflow_text = _read(workflow_info["skill_path"]).replace(
            "em-workflow", "<PLUGIN>"
        ).replace(f"手順 {workflow_info['probe_step']}", "手順 <N>")
        review_text = _read(review_info["skill_path"]).replace(
            "em-review", "<PLUGIN>"
        ).replace(f"手順 {review_info['probe_step']}", "手順 <N>")
        self.assertEqual(workflow_text, review_text)


class ContributorConsentCommandPathTest(unittest.TestCase):
    """contributor-consent-command-path task0001: structural checks of the
    skill-executed design, with failing synthetic inputs for every check."""

    # AC-2: Check 2 on the real text
    def test_ac2_branches_bind_each_answer_to_the_commands_the_skill_runs(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                self.assertEqual(check_branch_binding(_skill_body(plugin)), [])

    # AC-3: Check 1 on the real text
    def test_ac3_every_element_is_a_skill_command_or_user_visible_text(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                self.assertEqual(check_classification(_skill_body(plugin)), [])

    # AC-3: a reference inside a command the skill runs is never flagged
    def test_ac3_reference_in_a_skill_command_is_not_flagged(self):
        for plugin in PLUGINS:
            for flag in ("--list", "--record", "--remove"):
                with self.subTest(plugin=plugin, flag=flag):
                    body = _skill_body(plugin)
                    edited = _with_edited_command(body, flag, lambda text: text + " $HOME")
                    entries = _entries(edited)
                    command = _fence_text(entries[_find_command(entries, flag)][1])
                    self.assertTrue(_unresolved_references(command))
                    self.assertEqual(check_classification(edited), [])

    # AC-4: Check 3 on the real text
    def test_ac4_commands_are_run_by_the_skill_not_in_a_user_terminal(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                self.assertEqual(check_run_statement(_skill_body(plugin)), [])

    # AC-5 (a): the variable check, on free-standing strings
    def test_ac5a_reference_detection_on_free_standing_strings(self):
        flagged = [
            "root is ${CLAUDE_PLUGIN_ROOT}/x here",
            "home is $HOME now",
            "name is $name_1 now",
        ]
        not_flagged = [
            "dir is $(pwd) now",
            "no reference at all",
            "price is 5$ today",
        ]
        for text in flagged:
            with self.subTest(flagged=text):
                self.assertTrue(_unresolved_references(text))
        for text in not_flagged:
            with self.subTest(not_flagged=text):
                self.assertEqual(_unresolved_references(text), [])

    # AC-5 (a): the variable check inside Check 1, on edits of a real copy
    def test_ac5a_check_1_flags_references_in_every_kind_of_user_visible_text(self):
        placements = {
            "step 1 block": lambda body, suffix: _with_edited_visible_block(
                body, 1, lambda text: text + suffix
            ),
            "step 6 block": lambda body, suffix: _with_edited_visible_block(
                body, 6, lambda text: text + suffix
            ),
            "step 4 inline span": _with_edited_step4_span,
            "step 4 option label": _with_edited_first_option_label,
        }
        references = [" ${CLAUDE_PLUGIN_ROOT}/x", " $HOME"]
        harmless = [" $(pwd)", " plain"]
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for name, place in placements.items():
                for suffix in references:
                    with self.subTest(plugin=plugin, placement=name, suffix=suffix):
                        failures = check_classification(place(body, suffix))
                        self.assertIn("unresolved-reference", _codes(failures))
                for suffix in harmless:
                    with self.subTest(plugin=plugin, placement=name, suffix=suffix):
                        self.assertEqual(check_classification(place(body, suffix)), [])

    # AC-5 (b): Check 2 needs the record and the remove command
    def test_ac5b_check_2_fails_when_a_mutating_command_is_removed(self):
        expected = {"--record": "command-count[consent]", "--remove": "command-count[revoke]"}
        for plugin in PLUGINS:
            for flag, code in expected.items():
                with self.subTest(plugin=plugin, removed=flag):
                    body = _without_command(_skill_body(plugin), flag)
                    self.assertIn(code, _codes(check_branch_binding(body)))
                    self.assertIn("missing-command", _codes(check_classification(body)))

    # AC-5 (b): Check 1 needs the read-only command of step 2
    def test_ac5b_check_1_fails_when_the_list_command_is_removed(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                body = _without_command(_skill_body(plugin), "--list")
                self.assertIn("missing-command", _codes(check_classification(body)))

    # AC-5 (b): the project-directory argument and the flag exclusivity
    def test_ac5b_check_2_fails_on_a_command_without_its_arguments(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for flag, role in (("--record", "consent"), ("--remove", "revoke")):
                with self.subTest(plugin=plugin, flag=flag, case="project-dir"):
                    edited = _with_edited_command(
                        body, flag, lambda text: text.replace(PROJECT_DIR_FLAG, "--dir")
                    )
                    self.assertIn(f"command-content[{role}]", _codes(check_branch_binding(edited)))
                with self.subTest(plugin=plugin, flag=flag, case="other-flag"):
                    other = "--remove" if flag == "--record" else "--record"
                    edited = _with_edited_command(body, flag, lambda text: text + " " + other)
                    self.assertIn(f"command-content[{role}]", _codes(check_branch_binding(edited)))

    # AC-5 (c): Check 1 needs every block to be one of the two kinds
    def test_ac5c_check_1_fails_on_a_block_that_is_neither_kind(self):
        placements = {
            "step 3": lambda body: _with_block(body, 3, "plain note"),
            "step 4": lambda body: _with_block(body, 4, "plain note"),
            "step 5, not a guard invocation": lambda body: _with_block(body, 5, "plain note"),
            "step 2, not a guard invocation": lambda body: _with_block(body, 2, "plain note"),
            "outside any step": lambda body: _with_block(body, None, "plain note"),
            "guard invocation in step 1": lambda body: _with_command_copy(body, "--list", step=1),
            "guard invocation in step 6": lambda body: _with_command_copy(body, "--list", step=6),
        }
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for name, place in placements.items():
                with self.subTest(plugin=plugin, placement=name):
                    failures = check_classification(place(body))
                    self.assertIn("unclassified-element", _codes(failures))

    # AC-5 (d): Check 2 needs the decline and keep branches to run nothing
    def test_ac5d_check_2_fails_on_a_command_bound_to_decline_or_keep(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for flag in ("--record", "--remove"):
                for role in ("decline", "keep"):
                    with self.subTest(plugin=plugin, flag=flag, role=role):
                        edited = _with_command_copy(body, flag, after_role=role)
                        failures = check_branch_binding(edited)
                        self.assertIn(f"command-bound[{role}]", _codes(failures))

    # AC-5 (d): Check 2 needs step 6 to hold no guard invocation
    def test_ac5d_check_2_fails_on_a_guard_invocation_in_step_6(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for flag in ("--record", "--remove", "--list"):
                with self.subTest(plugin=plugin, flag=flag):
                    edited = _with_command_copy(body, flag, step=6)
                    failures = check_branch_binding(edited)
                    self.assertIn("step6-guard-invocation", _codes(failures))

    # AC-5 (d): Check 2 needs step 6 to output the no-write line only
    def test_ac5d_check_2_fails_when_step_6_outputs_something_else(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            with self.subTest(plugin=plugin, case="other line"):
                edited = _with_edited_visible_block(body, 6, lambda text: "別の行")
                self.assertIn("step6-block", _codes(check_branch_binding(edited)))
            with self.subTest(plugin=plugin, case="second block"):
                edited = _with_block(body, 6, "別の行")
                self.assertIn("step6-block", _codes(check_branch_binding(edited)))

    # AC-5 (d): a mutating command outside step 5, or outside every branch
    def test_ac5d_check_2_fails_on_a_mutating_command_outside_its_branch(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for flag in ("--record", "--remove"):
                with self.subTest(plugin=plugin, flag=flag, case="step 2"):
                    edited = _with_command_copy(body, flag, step=2)
                    self.assertIn("mutating-outside-step5", _codes(check_branch_binding(edited)))
                with self.subTest(plugin=plugin, flag=flag, case="before the branches"):
                    edited = _with_command_before_branches(body, flag)
                    self.assertIn("unbound-command", _codes(check_branch_binding(edited)))
            for flag, role in (("--record", "consent"), ("--remove", "revoke")):
                with self.subTest(plugin=plugin, flag=flag, case="second command"):
                    edited = _with_command_copy(body, flag, after_role=role)
                    self.assertIn(f"command-count[{role}]", _codes(check_branch_binding(edited)))

    # AC-5 (e): Check 3 needs step 5 to hold no user-terminal instruction
    def test_ac5e_check_3_fails_on_an_instruction_to_use_the_user_terminal(self):
        instructions = [
            "次のコマンドを自分の端末に貼り付けて実行する。",
            "Paste the command into your own terminal and run it.",
        ]
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for text in instructions:
                with self.subTest(plugin=plugin, text=text, placement="new paragraph"):
                    edited = _with_paragraph(body, 5, text)
                    failures = check_run_statement(edited)
                    self.assertIn("user-terminal-instruction", _codes(failures))
                with self.subTest(plugin=plugin, text=text, placement="consent branch"):
                    edited = _with_edited_branch(body, "consent", lambda old: old + " " + text)
                    failures = check_run_statement(edited)
                    self.assertIn("user-terminal-instruction", _codes(failures))

    # AC-5 (e): Check 3 needs every command-bound branch to state the run
    def test_ac5e_check_3_fails_when_a_bound_branch_no_longer_states_the_run(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            for role in ("consent", "revoke"):
                with self.subTest(plugin=plugin, role=role):
                    edited = _with_edited_branch(body, role, _without_run_verbs)
                    self.assertIn("no-run-statement", _codes(check_run_statement(edited)))

    # AC-5 (e): Check 3 needs a branch bound to a command to exist
    def test_ac5e_check_3_fails_when_no_branch_is_bound_to_a_command(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                body = _without_command(_without_command(_skill_body(plugin), "--record"), "--remove")
                self.assertIn("no-bound-branch", _codes(check_run_statement(body)))

    # AC-6: Checks 1 to 3 on both rewrap variants of each real copy
    def test_ac6_checks_hold_on_both_rewrap_variants(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            variants = {"joined": _joined_variant(body), "narrow": _narrow_variant(body)}
            for name, variant in variants.items():
                with self.subTest(plugin=plugin, variant=name):
                    self.assertEqual(check_classification(variant), [])
                    self.assertEqual(check_branch_binding(variant), [])
                    self.assertEqual(check_run_statement(variant), [])

    # AC-6: the variants really re-flow the prose and nothing else
    def test_ac6_variants_reflow_prose_paragraphs_only(self):
        for plugin in PLUGINS:
            body = _skill_body(plugin)
            original = _parse_nodes(body)
            joined = _parse_nodes(_joined_variant(body))
            narrow = _parse_nodes(_narrow_variant(body))
            with self.subTest(plugin=plugin):
                self.assertEqual(len(original), len(joined))
                self.assertEqual(len(original), len(narrow))
                for kept in ("fence", "heading"):
                    self.assertEqual(
                        [n.lines for n in original if n.kind == kept],
                        [n.lines for n in joined if n.kind == kept],
                    )
                    self.assertEqual(
                        [n.lines for n in original if n.kind == kept],
                        [n.lines for n in narrow if n.kind == kept],
                    )
                lists = [n.lines for n in original if n.kind == "para" and not _is_prose_paragraph(n)]
                self.assertTrue(lists)
                for variant in (joined, narrow):
                    self.assertEqual(
                        lists,
                        [n.lines for n in variant if n.kind == "para" and not _is_prose_paragraph(n)],
                    )
                prose = [n for n in joined if _is_prose_paragraph(n)]
                self.assertTrue(all(len(n.lines) == 1 for n in prose))
                self.assertTrue(any(len(n.lines) > 1 for n in original if _is_prose_paragraph(n)))
                self.assertGreater(
                    len(_narrow_variant(body).splitlines()),
                    len(_joined_variant(body).splitlines()),
                )

    # AC-6: the narrow variant wraps a branch paragraph and splits a term
    def test_ac6_narrow_variant_wraps_branches_and_splits_a_run_verb(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                entries = _entries(_narrow_variant(_skill_body(plugin)))
                shared = entries[_branch_index(entries, "decline")][1]
                self.assertGreater(len(shared.lines), 1)
                consent = entries[_branch_index(entries, "consent")][1]
                text = "\n".join(consent.lines)
                split = [t for t in RUN_VERB_TERMS if t in _squash(text) and t not in text]
                self.assertTrue(split, f"no run verb split by a wrap in {text!r}")


if __name__ == "__main__":
    unittest.main()
