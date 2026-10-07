#!/usr/bin/env python3
"""em-workflow Stop hook: queue loop guard (queue_stop_guard.py).

Deterministic net for the implement-phase work-queue loop
(IMPLEMENTATION.md, "Journal contract" / "Conventions" sections). Fires on
every Stop event; blocks the orchestrator from ending its turn while a
refillable implementer slot exists for an in-progress feature, naming the
tasks to launch. This hook is a NET, not an authority: any unexpected
condition (unreadable/malformed files, non-JSON stdin, validation failure,
no active feature) exits 0 silently rather than risk wedging the session
(fail-open convention, contrasted with bash_guard.py's fail-closed security
boundary).

Decision (per the first in-progress feature, stable ordering by feature
name, that has refillable work):
  - A task whose last journal event is `failed` is classified by a
    three-condition match. It is treated as unlaunched (the task's own id,
    returned from `failed` to `pending` by route-back, per
    references/workflow-patch.md's "Re-planning task-id allocation") only
    when all three hold: (1) its own workflow.yaml status reads exactly
    `pending`; (2) its last journal event is `failed`; (3) the physical
    line of that event in the journal equals the task's
    `routeback_failed_journal_line` record in its own workflow.yaml block.
    Any other task whose last event is `failed` is failed -> exit 0 (no
    block; user decision pending).
  - The record is read only from the direct keys of the task's own
    `taskNNNN:` mapping (lines at the mapping's direct-child indentation),
    first occurrence wins; block scalar bodies (such as `notes`) and nested
    lines are not read. It counts only as an unquoted decimal integer of
    ASCII digits whose first digit is 1-9, optionally followed by trailing
    whitespace. An absent, null or otherwise non-canonical value is no
    record. Journal lines are delimited by LF only (a CR never starts a
    line); blank, malformed, unknown-event and invalid-task-id lines
    advance the line count but never become a task's event.
  - Body lines of multi-line quoted-scalar and flow-collection values are
    never read as a task boundary, task id, status or record (for example,
    the continuation lines of a multi-line double-quoted `notes`), whatever
    their indentation, column 0 included. The line-based reader tracks the
    opening and closing of such values from the first line of the file; a
    value that never closes hides every later line, which falls to "no
    record, no block".
  - No unlaunched tasks, or no free slot (>= MAX_PARALLEL_IMPLEMENTERS
    in-flight) -> exit 0.
  - Otherwise -> BLOCK: exit 2, stderr names the feature, the free-slot
    count, and the task ids to launch (ascending id order, bounded by the
    free-slot count).

Loop cap: a sidecar file (stop-guard-state.json, sibling of the journal)
persists a fingerprint (the derived unlaunched+in-flight task-id sets) and a
consecutive-block counter. Three consecutive blocks in the same derived
state are allowed; every FURTHER stop in that same state does NOT block
(warns on stderr and exits 0 instead) so the user stays in charge — the
over-cap counter is persisted, so the guard never resumes blocking an
unchanged state (FR4 "stop blocking … let the user take over"). Any state
change resets the counter to 1 and re-arms blocking.

Only Python stdlib is imported (NFR1).
"""

import glob
import json
import os
import re
import sys
import tempfile
import time

MAX_PARALLEL_IMPLEMENTERS = 6  # SSOT duplicated per IMPLEMENTATION.md; also
                                # pinned in implement-phase.md (task0005).
MAX_CONSECUTIVE_BLOCKS = 3
FRESHNESS_THRESHOLD_SECONDS = 24 * 60 * 60  # D3: abandoned-worktree cutoff.

FEATURE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TASK_ID_RE = re.compile(r"^task[0-9]+$")
TASK_NUM_RE = re.compile(r"^task([0-9]+)$")

# workflow.yaml is read line-based on purpose (bash_guard.py pattern; NFR1 —
# no YAML library). The `workflow:` list uses `- id: <name>` items followed
# by their own indented keys; the `tasks:` mapping uses bare `taskNNNN:`
# keys at a fixed indent under the top-level `tasks:` key.
STEP_ID_RE = re.compile(r"^\s*-\s*id:\s*(\S+)\s*$")
STEP_STATUS_RE = re.compile(r"^\s*status:\s*(\S+)\s*$")
TASKS_SECTION_RE = re.compile(r"^tasks:\s*$")
TASK_KEY_RE = re.compile(r"^\s+(task[0-9]+):\s*$")
TASK_STATUS_RE = re.compile(r"^\s+status:\s*(\S+)\s*$")
# A line whose key is exactly `status` (value or not): after its leading
# whitespace it begins with `status:` and that colon is followed by a space, a
# tab or the end of the line -- the colon rule of _find_key_colon. A key that
# merely starts with `status:` (`status:detail: x`, `status:pending`) does not
# match. The direct-child status read uses it to find the deciding line, then
# TASK_STATUS_RE to extract the value from that same line.
TASK_STATUS_KEY_RE = re.compile(r"^\s+status:(?=[ \t]|$)")
# The route-back record, read from the direct keys of a task's own mapping
# only: the line's indentation must equal the task block's direct-child
# indentation (checked in task_routeback_records_from_workflow), so block
# scalar bodies and nested lines are never read. This regex only recognizes
# the key, and only an exact-key line: after its leading whitespace the line
# begins with the key name and that colon is followed by a space, a tab or the
# end of the line -- the colon rule of _find_key_colon and TASK_STATUS_KEY_RE.
# A key that merely starts with the record key and a colon
# (`routeback_failed_journal_line:x: 1`, `routeback_failed_journal_line:1`) is a
# different key: it does not match, so it never decides the task and a genuine
# record line after it is still read. The key match and the canonical-value
# match are both ASCII-only: a non-ASCII digit or whitespace character never
# qualifies. Body lines of multi-line quoted-scalar and flow-collection values
# are never read as a task boundary, task id, status or record: the block scan
# drops them before this regex sees a line, so a record-shaped line inside such
# a value is not a record.
ROUTEBACK_RECORD_KEY = "routeback_failed_journal_line"
ROUTEBACK_RECORD_LINE_RE = re.compile(
    r"^\s+" + ROUTEBACK_RECORD_KEY + r":(?=[ \t]|$)(.*)$", re.ASCII
)
ROUTEBACK_RECORD_VALUE_RE = re.compile(r"^[ \t]+([1-9][0-9]*)\s*$", re.ASCII)

KNOWN_EVENTS = ("launched", "merged", "failed")


def find_worktrees_root(cwd):
    """Stage 1 (Enumeration root): walk up from `cwd` (itself included) to
    the nearest ancestor containing `.claude/worktrees/em-workflow` as a
    directory; return that worktrees directory itself, or None if the walk
    reaches the filesystem root without a hit. No process invocation.
    Duplicated deliberately (not factored into a shared module) from
    queue_taskstop_net.py's find_worktrees_root — same semantics
    (IMPLEMENTATION.md D2)."""
    if not isinstance(cwd, str) or not cwd:
        return None
    current = os.path.abspath(cwd)
    while True:
        candidate = os.path.join(current, ".claude", "worktrees", "em-workflow")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def implement_in_progress(workflow_yaml_path):
    """True iff the `implement` step's own `status:` line reads in_progress."""
    try:
        with open(workflow_yaml_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return False

    current_step = None
    implement_status = None
    for line in lines:
        step_match = STEP_ID_RE.match(line)
        if step_match:
            current_step = step_match.group(1)
            continue
        if current_step == "implement" and implement_status is None:
            status_match = STEP_STATUS_RE.match(line)
            if status_match:
                implement_status = status_match.group(1)
    return implement_status == "in_progress"


# Multi-line quoted scalars and flow collections. A line that opens a
# double-quoted scalar, a single-quoted scalar, a flow sequence or a flow
# mapping and does not close it on the same line starts a value whose
# following lines (up to and including the line that closes it) are that
# value's BODY. A body line is free text: it is never read as a `tasks:`
# section start or end, a task key, a task block end, a status or a record,
# whatever its indentation (even column 0). The opening line itself keeps the
# ordinary line-based reading. The tracking below is stdlib-only and carries
# its state from the first line of the file (a value opened anywhere earlier
# is honoured). It never raises; a value that never closes makes every later
# line a body line, which falls to "no record, no block".
_ITEM_INDICATOR_RE = re.compile(r"-(?=[ \t]|$)")
# First characters a plain scalar never starts with (the same set for a value
# after a key and for an item's content): a quote, a bracket, a block scalar
# header, a comment, an anchor, a tag, an alias.
_NOT_PLAIN_START = "\"'[{|>#&!*"
_BLOCK_SCALAR_HEADER_RE = re.compile(
    r"^[|>](?:[+-][1-9]?|[1-9][+-]?)?(?:[ \t]+#.*|[ \t]*)$"
)


def _find_key_colon(text):
    """Index of the colon of a plain `key: value` / `key:` pair in `text`
    (the content of a line after any item indicators), or None. A colon
    counts only when followed by a space, a tab or the end of the text; a
    comment (`#` after whitespace) before it means there is no key."""
    length = len(text)
    for index, char in enumerate(text):
        if char == "#" and index > 0 and text[index - 1] in " \t":
            return None
        if char == ":" and (index + 1 == length or text[index + 1] in " \t"):
            return index if index > 0 else None
    return None


class _MultilineValueTracker:
    """Decides, line by line in file order, whether a line is a BODY line of a
    multi-line quoted scalar or flow collection (see the comment above).

    A quote or bracket opens a value only at a value-start position: after a
    mapping key on the same line, after an item indicator, or as the first
    content of the next non-blank, non-comment line that is indented deeper
    than a key (or item indicator) whose own line carried no value. Block
    scalar bodies, comment lines, plain scalars and plain-scalar continuation
    lines never open one, nor does anything after a value closed on its line.
    Anchors, tags and quoted keys before a value are not value-start
    prefixes.

    Plain-scalar continuation: once a key's or an item's value is a plain
    scalar (on the same line, or on the first deeper line after a key or item
    that carried none), every later non-blank, non-comment line indented deeper
    than the key's (or item indicator's) column is a continuation line of that
    scalar. An item indicator, a key, a quote or a bracket on it opens
    nothing. The first line at or shallower than that column ends the state
    and is read with the normal rules; blank and comment lines neither
    continue nor end it.

    Inside a flow collection a quote opens an inner string only at the start
    of a flow entry or after a real mapping indicator. A `:` is such an
    indicator when a space, a tab or the end of the line follows it, or when
    it follows the closing quote of an inner string or the closing bracket of
    a nested collection (a JSON-like key); a `?` is one only at the start of a
    flow entry (directly after `[`, `{` or `,`, with or without whitespace in
    between) and only when a space, a tab or the end of the line follows it.
    Any other `:` or `?` is an ordinary plain-scalar character, so a `?` in the
    middle of a plain flow scalar (`[retry? 'x]`) never lets a quote open.

    A blank line is a line made only of spaces (U+0020) and tabs (U+0009), the
    empty line included. A line made only of any other whitespace character
    (U+3000, U+00A0, U+000B, U+000C) is not blank: it is read by the normal
    rules, as a plain scalar at a value start, or by its indentation inside a
    block scalar."""

    def __init__(self):
        self._mode = None  # None, "dq", "sq" or "flow": the open value kind
        self._depth = 0  # flow nesting depth
        self._inner = None  # flow only: None, "dq" or "sq" (an inner string)
        self._at_start = True  # flow only: a quote here opens an inner string
        self._after_close = False  # flow only: just after a closed string / collection
        self._block_parent = None  # indent a block scalar's body must exceed
        self._pending = None  # column of a key / item whose value comes next
        self._plain_parent = None  # column a plain scalar's continuation lines exceed

    def feed(self, line):
        """Consume the next physical line; return True iff it is a body
        line."""
        text = line.rstrip("\r\n")
        if self._mode is not None:
            self._scan(text, 0)
            return True
        if self._block_parent is not None:
            if self._is_blank(text):
                return False
            if len(text) - len(text.lstrip(" \t")) > self._block_parent:
                return False  # a block scalar body line: never an opening
            self._block_parent = None
        self._read_line(text)
        return False

    @staticmethod
    def _is_blank(text):
        """The tracker's blank-line rule: a line (its line terminator already
        removed) made only of U+0020 spaces and U+0009 tabs, the empty line
        included. Any other whitespace character makes the line non-blank."""
        return text.lstrip(" \t") == ""

    def _read_line(self, text):
        stripped = text.lstrip(" \t")
        if self._is_blank(text) or stripped.startswith("#"):
            return  # blank and comment lines never open and never decide
        pos = len(text) - len(stripped)
        if self._plain_parent is not None:
            if pos > self._plain_parent:
                return  # a plain-scalar continuation line: never a value start
            self._plain_parent = None  # at or above the parent: the scalar ended
        pending, self._pending = self._pending, None
        dash_col = None
        while True:
            match = _ITEM_INDICATOR_RE.match(text, pos)
            if match is None:
                break
            dash_col = pos
            pos = match.end()
            while pos < len(text) and text[pos] in " \t":
                pos += 1
        value_start = dash_col is not None or (
            pending is not None and pos > pending
        )
        rest = text[pos:]
        if rest == "" or rest.startswith("#"):
            if dash_col is not None:
                self._pending = dash_col  # the item's value is on later lines
            return
        first = rest[0]
        if first in "\"'[{":
            if value_start:
                self._open(text, pos)
            return  # elsewhere: a quoted key or a plain continuation line
        if first in "|>":
            if value_start and _BLOCK_SCALAR_HEADER_RE.match(rest):
                self._block_parent = dash_col if dash_col is not None else pending
            return
        colon = _find_key_colon(rest)
        if colon is None:
            # A plain scalar: nothing opens inside it, and the deeper lines
            # after it continue it. An item's content continues past the item
            # indicator's column; a value that started on the line after its
            # key (or item indicator) continues past that key's column.
            if first not in _NOT_PLAIN_START:
                if dash_col is not None:
                    self._plain_parent = dash_col
                elif value_start:
                    self._plain_parent = pending
            return
        value = rest[colon + 1:].lstrip(" \t")
        value_pos = len(text) - len(value)
        if value == "" or value.startswith("#"):
            self._pending = pos  # the key's value is on later lines
        elif value[0] in "\"'[{":
            self._open(text, value_pos)
        elif value[0] in "|>" and _BLOCK_SCALAR_HEADER_RE.match(value):
            self._block_parent = pos
        elif value[0] not in _NOT_PLAIN_START:
            self._plain_parent = pos  # a plain scalar value: deeper lines continue it

    def _open(self, text, pos):
        char = text[pos]
        if char == '"':
            self._mode = "dq"
        elif char == "'":
            self._mode = "sq"
        else:
            self._mode = "flow"
            self._depth = 1
            self._inner = None
            self._at_start = True
            self._after_close = False
        self._scan(text, pos + 1)

    def _scan(self, text, index):
        """Advance the open value over `text` from `index`; a close ends the
        value and leaves the rest of the line (whitespace, a comment) unread."""
        length = len(text)
        if self._mode == "dq":
            while index < length:
                if text[index] == "\\":
                    index += 2  # an escape, an escaped newline included
                    continue
                if text[index] == '"':
                    self._mode = None
                    return
                index += 1
        elif self._mode == "sq":
            while index < length:
                if text[index] == "'":
                    if text[index + 1:index + 2] == "'":
                        index += 2  # a doubled quote is an escaped quote
                        continue
                    self._mode = None
                    return
                index += 1
        else:
            self._scan_flow(text, index)

    def _scan_flow(self, text, index):
        length = len(text)
        while index < length:
            char = text[index]
            if self._inner == "dq":
                if char == "\\":
                    index += 2
                    continue
                if char == '"':
                    self._inner = None
                    self._at_start, self._after_close = False, True
            elif self._inner == "sq":
                if char == "'":
                    if text[index + 1:index + 2] == "'":
                        index += 2
                        continue
                    self._inner = None
                    self._at_start, self._after_close = False, True
            elif char in " \t":
                pass
            elif char == "#" and (index == 0 or text[index - 1] in " \t"):
                return  # a comment: its brackets are not counted
            elif char in "[{":
                self._depth += 1
                self._at_start, self._after_close = True, False
            elif char in "]}":
                self._depth -= 1
                self._at_start, self._after_close = False, True
                if self._depth <= 0:
                    self._mode = None
                    return
            elif char == ",":
                self._at_start, self._after_close = True, False
            elif char in "\"'" and self._at_start:
                # A quote opens an inner string only at the start of a flow
                # entry or a flow mapping value, never inside a plain scalar.
                self._inner = "dq" if char == '"' else "sq"
                self._at_start = self._after_close = False
            elif char in ":?":
                # A mapping indicator only before a space, a tab or the end of
                # the line; a `:` also right after a closed inner string or
                # nested collection (a JSON-like key), and a `?` only at the
                # start of a flow entry (`_at_start`). Otherwise the `:` / `?`
                # is an ordinary plain-scalar character, so a quote after it
                # (on this line or a later one) does not open.
                before_space = text[index + 1:index + 2] in ("", " ", "\t")
                if char == ":":
                    indicator = before_space or self._after_close
                else:
                    indicator = before_space and self._at_start
                self._at_start, self._after_close = indicator, False
            else:
                self._at_start = self._after_close = False
            index += 1


def _multiline_value_body_flags(lines):
    """One bool per line of `lines` (physical lines of workflow.yaml in file
    order, as the readers below obtain them): True iff the line is a body line
    of a multi-line quoted scalar or flow collection."""
    tracker = _MultilineValueTracker()
    return [tracker.feed(line) for line in lines]


def task_ids_from_workflow(workflow_yaml_path):
    """Task ids declared as keys under the top-level `tasks:` mapping. Body
    lines of multi-line quoted-scalar and flow-collection values are never
    read as a task boundary, task id, status or record: such a line neither
    starts nor ends the `tasks:` section (not even at column 0) and is never
    a task key, whatever its indentation."""
    try:
        with open(workflow_yaml_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return []

    ids = []
    in_tasks = False
    for line, is_body in zip(lines, _multiline_value_body_flags(lines)):
        if is_body:
            continue
        if TASKS_SECTION_RE.match(line):
            in_tasks = True
            continue
        if not in_tasks:
            continue
        if line.strip() == "":
            continue
        if not line[0].isspace():
            # Dedent to another top-level key: the tasks: mapping ended.
            in_tasks = False
            continue
        match = TASK_KEY_RE.match(line)
        if match and TASK_ID_RE.match(match.group(1)):
            ids.append(match.group(1))
    return ids


def iter_task_block_lines(workflow_yaml_path):
    """Yield (task_id, line) for every line strictly inside a task's own
    indented block under the top-level `tasks:` mapping (D2). A line is
    attributed to a task id only while the scan is inside the lines
    belonging to that task's own `taskNNNN:` key -- never a workflow-step
    line, never another task's, never a line at or above the task key's own
    indent. The key line itself is not yielded. An unreadable file yields
    nothing. Body lines of multi-line quoted-scalar and flow-collection
    values are never read as a task boundary, task id, status or record: such
    a line is skipped before every other check, so it is never yielded and
    never ends the current task block or the `tasks:` section, whatever its
    indentation (the line that opens such a value is read as before)."""
    try:
        with open(workflow_yaml_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return

    in_tasks = False
    current_task = None
    current_task_indent = None
    for line, is_body in zip(lines, _multiline_value_body_flags(lines)):
        if is_body:
            continue
        if TASKS_SECTION_RE.match(line):
            in_tasks = True
            current_task = None
            current_task_indent = None
            continue
        if not in_tasks:
            continue
        if line.strip() == "":
            continue
        if not line[0].isspace():
            # Dedent to another top-level key: the tasks: mapping ended.
            in_tasks = False
            current_task = None
            current_task_indent = None
            continue

        indent = len(line) - len(line.lstrip(" "))
        if current_task is not None and indent <= current_task_indent:
            # Dedented to (or above) the current task's own key level:
            # its block has ended, whether or not this line starts a new
            # sibling task.
            current_task = None
            current_task_indent = None

        key_match = TASK_KEY_RE.match(line)
        if key_match and current_task is None:
            if TASK_ID_RE.match(key_match.group(1)):
                current_task = key_match.group(1)
                current_task_indent = indent
            continue

        if current_task is None:
            continue

        yield current_task, line


def task_statuses_from_workflow(workflow_yaml_path):
    """Per-task workflow status, scoped to each task's own indented block
    under the top-level `tasks:` mapping (D2 -- the carve-out's
    discriminator) and read from direct-child keys only.

    The direct-child indentation of a task block is the indentation of the
    first line in the block that is neither blank nor a comment line (a
    comment line before the first key never shifts it). Only lines at exactly
    that indentation are status candidates: block-scalar body lines (every
    header form, including the untrusted `notes` text) and nested-mapping
    lines sit deeper and are never read, whether the direct `status:` key
    comes before them, after them, or not at all. The first direct-child line
    whose key is exactly `status` (the colon followed by a space, a tab or the
    end of the line) decides: its value is recorded when it can be extracted,
    and otherwise the task is left out; later lines are not consulted either
    way. A direct-child line whose key only starts with `status:` (for example
    `status:detail: x` or `status:pending`) is not a status key line: it is
    skipped and the scan continues with the next line of the block. A task id
    with no direct `status:` key (or an undeterminable direct value) is simply
    absent from the returned mapping; callers treat that the same as any other
    non-`pending` classification (D1). Block content is never interpreted
    beyond indentation, so no input makes this raise."""
    statuses = {}
    direct_indent = {}  # task id -> indentation of its direct-child keys
    decided = set()  # task ids whose first direct status key was consulted
    for task_id, line in iter_task_block_lines(workflow_yaml_path):
        if task_id in decided:
            continue
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("#"):
            continue  # blank / comment lines never set the direct indent
        indent = len(line) - len(line.lstrip(" "))
        if task_id not in direct_indent:
            direct_indent[task_id] = indent
        if indent != direct_indent[task_id]:
            continue
        if not TASK_STATUS_KEY_RE.match(line):
            continue  # not a status key line: keep reading this block
        decided.add(task_id)
        status_match = TASK_STATUS_RE.match(line)
        if status_match:
            statuses[task_id] = status_match.group(1)
    return statuses


def task_routeback_records_from_workflow(workflow_yaml_path):
    """Per-task `routeback_failed_journal_line` record, read from each task's
    own block only (the same scoping as the status read) and only from the
    direct keys of that task's own mapping. The direct-child indentation is
    the space indentation of the first line in the block that is neither
    blank nor a comment; a record-shaped line indented deeper is never read,
    so block scalar bodies (every indicator form), continuation lines of
    multi-line scalars and keys nested under another direct key cannot
    create or shadow the record. Among the direct keys only a line whose key
    is exactly the record key counts as an occurrence: a key that merely
    starts with the record key and a colon (`routeback_failed_journal_line:x: 1`)
    is skipped and never hides a later genuine line. Among those occurrences
    the first one wins, and only the canonical form is a record: an unquoted run
    of ASCII digits whose first digit is 1-9, optionally followed by trailing
    whitespace. The returned value is that digit string, never an int. A task
    id whose first direct-key occurrence is absent, `null`, empty or
    otherwise non-canonical is absent from the mapping. Body lines of
    multi-line quoted-scalar and flow-collection values are never read as a
    task boundary, task id, status or record: this read consumes only the
    block scan's output, which never contains them."""
    records = {}
    seen = set()
    direct_indent = {}
    for task_id, line in iter_task_block_lines(workflow_yaml_path):
        if task_id in seen:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if task_id not in direct_indent:
            if line.lstrip(" \t").startswith("#"):
                continue  # a comment never sets the direct-child indent
            direct_indent[task_id] = indent
        if indent != direct_indent[task_id]:
            continue  # nested deeper than a direct key: never a record
        key_match = ROUTEBACK_RECORD_LINE_RE.match(line)
        if not key_match:
            continue
        seen.add(task_id)
        value_match = ROUTEBACK_RECORD_VALUE_RE.match(key_match.group(1))
        if value_match:
            records[task_id] = value_match.group(1)
    return records


def read_journal(journal_path):
    """Last event per task, as {task: (event, physical_line)}.

    `physical_line` is the 1-based line number of that event in the file.
    Lines are delimited by LF only (a CR never starts a new line, so the
    file is read as bytes), and a final non-empty segment without a
    terminating LF counts as a line. Blank lines, malformed lines, lines
    with an unknown event and lines with an invalid task id advance the
    counter but never become a task's event.

    - Journal file absent but its directory exists (implement phase started,
      no launch recorded yet): return {} — every declared task counts as
      unlaunched, so a forgotten INITIAL launch is still caught (FR4).
    - Journal directory absent (phase's worktree layout not created), or the
      file exists but is unopenable: return None — the feature is not
      evaluable; fail-open and skip it.
    """
    try:
        with open(journal_path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        if os.path.isdir(os.path.dirname(journal_path)):
            return {}
        return None
    except OSError:
        return None

    segments = raw.split(b"\n")
    if segments and segments[-1] == b"":
        segments.pop()  # the file's last LF terminates a line, it adds none

    last = {}
    for line_number, segment in enumerate(segments, start=1):
        line = segment.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            continue  # malformed line: skip (fail-safe read)
        if not isinstance(record, dict):
            continue
        task = record.get("task")
        event = record.get("event")
        if not isinstance(task, str) or not TASK_ID_RE.match(task):
            continue
        if event not in KNOWN_EVENTS:
            continue
        last[task] = (event, line_number)
    return last


def task_sort_key(task_id):
    match = TASK_NUM_RE.match(task_id)
    return int(match.group(1)) if match else task_id


def fingerprint_for(unlaunched, in_flight):
    return json.dumps(
        {"unlaunched": sorted(unlaunched, key=task_sort_key),
         "in_flight": sorted(in_flight, key=task_sort_key)},
        sort_keys=True,
    )


def decompose_enumerated_path(workflow_yaml_path):
    """Enumerated-path decomposition (single derivation, IMPLEMENTATION.md
    D1): from one workflow.yaml path produced by the layout pattern
    `{worktrees_root}/*/integration/feature-docs/*/workflow.yaml`, derive
    (feature identity, journal directory). The journal directory is the
    ancestor of the matched path that directly contains the
    `integration` directory; that same ancestor's own last segment is the
    identity. The `feature-docs/<segment>` wildcard is never read as
    identity, and nothing downstream reassembles this path from a root
    plus a name."""
    segment_dir = os.path.dirname(workflow_yaml_path)  # feature-docs/<segment>
    feature_docs_dir = os.path.dirname(segment_dir)  # .../integration/feature-docs
    integration_dir = os.path.dirname(feature_docs_dir)  # .../<feature>/integration
    journal_dir = os.path.dirname(integration_dir)  # .../<feature>
    identity = os.path.basename(journal_dir)
    return identity, journal_dir


def candidate_is_fresh(journal_dir, workflow_yaml_path, now=None):
    """D3 freshness condition: reads the journal file's modification time,
    falling back to the enumerated workflow.yaml's modification time when
    the journal file does not exist. Excludes the candidate when the
    chosen time is more than FRESHNESS_THRESHOLD_SECONDS in the past, or
    when neither time is obtainable (undecidable falls to the
    non-blocking side)."""
    if now is None:
        now = time.time()
    journal_path = os.path.join(journal_dir, "journal.jsonl")
    try:
        mtime = os.path.getmtime(journal_path)
    except OSError:
        try:
            mtime = os.path.getmtime(workflow_yaml_path)
        except OSError:
            return False
    return (now - mtime) <= FRESHNESS_THRESHOLD_SECONDS


def select_owned_unique_matches(matches):
    """Ownership + uniqueness selection step (IMPLEMENTATION.md D6, task
    plan "Ownership + uniqueness selection step"). Runs after the layout
    pattern is expanded and before the `in_progress` / freshness filters, so
    a rejected match costs zero file reads.

    Precondition: the ordered list of `workflow.yaml` paths the layout
    pattern `{worktrees_root}/*/integration/feature-docs/*/workflow.yaml`
    produced under one enumeration root.

    Postcondition: an ordered list of {"identity", "workflow_yaml_path",
    "journal_dir"} dicts, ascending and stable by identity, restricted to
    matches that satisfy all of:
      1. the identity derived by the single decomposition (D1) passes the
         existing feature-name shape check (FEATURE_RE);
      2. the match's own `feature-docs/<segment>` segment equals that
         identity -- ownership. SPEC.md's Path Contract states the SAME
         `{feature}` name in both wildcard positions of the enumerated
         location; a match whose two segments differ is outside the
         specified layout and is never enumerated or read;
      3. no other surviving match derives the same identity -- an identity
         carried by two or more surviving matches is dropped IN FULL
         (ambiguity refusal, the fail-open direction), not resolved by
         first-wins.

    Purity: decides all three conditions from the matched path strings
    alone. Opens nothing, stats nothing, spawns nothing, so it is directly
    unit-testable against paths that do not exist on disk. Condition 2
    compares two segments *of the path that was matched*; no path is ever
    reconstructed from a root plus a name, and the `feature-docs` segment is
    still never read AS identity -- it is only compared against it (NFR4).
    """
    owned = []
    for match in matches:
        identity, journal_dir = decompose_enumerated_path(match)
        if not FEATURE_RE.match(identity):
            continue
        docs_segment = os.path.basename(os.path.dirname(match))
        if docs_segment != identity:
            continue  # unowned: the two wildcard positions disagree
        owned.append(
            {
                "identity": identity,
                "workflow_yaml_path": match,
                "journal_dir": journal_dir,
            }
        )

    identity_counts = {}
    for candidate in owned:
        identity_counts[candidate["identity"]] = (
            identity_counts.get(candidate["identity"], 0) + 1
        )

    unique = [c for c in owned if identity_counts[c["identity"]] == 1]
    unique.sort(key=lambda candidate: candidate["identity"])
    return unique


def active_candidates(worktrees_root, now=None):
    """Stage 2 (Active set): expand the layout pattern under
    `worktrees_root`, run the ownership + uniqueness selection step, and
    keep only candidates whose implement step reads in_progress and that
    pass the freshness condition. Returns a list of {"identity",
    "workflow_yaml_path", "journal_dir"} dicts, stable and ascending by
    identity."""
    pattern = os.path.join(
        worktrees_root, "*", "integration", "feature-docs", "*", "workflow.yaml"
    )
    matches = sorted(glob.glob(pattern))
    candidates = []
    for candidate in select_owned_unique_matches(matches):
        if not implement_in_progress(candidate["workflow_yaml_path"]):
            continue
        if not candidate_is_fresh(
            candidate["journal_dir"], candidate["workflow_yaml_path"], now=now
        ):
            continue
        candidates.append(candidate)
    return candidates


def evaluate_feature(candidate):
    """Return a decision dict for `candidate` if it currently has
    refillable work to report, else None (nothing actionable / not
    evaluable). `candidate` is an already-resolved pair from
    active_candidates (Stage 3: reads the given workflow.yaml path
    verbatim; nothing here is joined from a root plus a feature name)."""
    feature = candidate["identity"]
    workflow_yaml_path = candidate["workflow_yaml_path"]
    journal_dir = candidate["journal_dir"]

    task_ids = task_ids_from_workflow(workflow_yaml_path)
    if not task_ids:
        return None

    journal_path = os.path.join(journal_dir, "journal.jsonl")
    last_events = read_journal(journal_path)
    if last_events is None:
        return None

    unlaunched, in_flight, failed = [], [], []
    # Lazily read: only needed when a `failed` last event is actually
    # present, so the common (no-failure) path costs no extra pass over
    # workflow.yaml (D2, NFR4).
    task_statuses = None
    task_records = None
    for task_id in task_ids:
        last_event = last_events.get(task_id)
        if last_event is None:
            unlaunched.append(task_id)
            continue
        state, event_line = last_event
        if state == "launched":
            in_flight.append(task_id)
        elif state == "failed":
            if task_statuses is None:
                task_statuses = task_statuses_from_workflow(workflow_yaml_path)
                task_records = task_routeback_records_from_workflow(
                    workflow_yaml_path
                )
            if (
                task_statuses.get(task_id) == "pending"
                and task_records.get(task_id) == str(event_line)
            ):
                # Recycled-task-id carve-out (D1): the journal's last event
                # is the one `failed` event a route-back reset returned to
                # `pending`, identified by the task's own record. Any other
                # `pending` + `failed` task is genuinely failed.
                unlaunched.append(task_id)
            else:
                failed.append(task_id)
        # "merged" tasks need no further tracking (terminal).

    if failed:
        return None  # user decision pending; never block on this feature

    free_slots = MAX_PARALLEL_IMPLEMENTERS - len(in_flight)
    if not unlaunched or free_slots <= 0:
        return None

    to_launch = sorted(unlaunched, key=task_sort_key)[:free_slots]
    return {
        "feature": feature,
        "journal_dir": journal_dir,
        "free_slots": free_slots,
        "to_launch": to_launch,
        "fingerprint": fingerprint_for(unlaunched, in_flight),
    }


def read_sidecar(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def write_sidecar(path, fingerprint, counter):
    """Atomic sidecar write via a RANDOMIZED exclusive temp file.

    mkstemp opens with O_CREAT|O_EXCL (never follows a pre-planted symlink,
    never truncates an existing target) — a repository cannot predict the
    temp name nor redirect the write. os.replace then swaps it in without
    following symlinks at the destination.
    """
    tmp_path = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(path), prefix=".stop-guard-state.", suffix=".tmp"
        )
        try:
            os.write(
                fd,
                json.dumps({"fingerprint": fingerprint, "counter": counter}).encode("utf-8"),
            )
        finally:
            os.close(fd)
        os.replace(tmp_path, path)
        tmp_path = None
    except OSError:
        pass  # sidecar persistence is best-effort; never break the merge/turn
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def hook_main():
    try:
        raw = sys.stdin.read()
    except OSError:
        return 0
    try:
        data = json.loads(raw)
    except ValueError:
        return 0  # malformed stdin: fail-open
    if not isinstance(data, dict):
        return 0

    # Claude Code's re-entry flag (true once the session is already
    # continuing due to a stop hook). Read for completeness/fail-open
    # tolerance; deliberately NOT folded into the fingerprint-reset decision
    # below — this flag stays true for the whole continuation sequence
    # regardless of our derived state, so ORing it into the counter would
    # defeat "a state change resets the cap". It is never used to force an
    # unconditional block: blocking is decided solely by evaluate_feature().
    _ = bool(data.get("stop_hook_active"))

    root = find_worktrees_root(os.getcwd())
    if root is None:
        return 0  # no enumeration root above cwd: no active feature

    for candidate in active_candidates(root):
        result = evaluate_feature(candidate)
        if result is None:
            continue

        sidecar_path = os.path.join(result["journal_dir"], "stop-guard-state.json")
        sidecar = read_sidecar(sidecar_path)
        prev_fingerprint = sidecar.get("fingerprint")
        prev_counter = sidecar.get("counter")
        if not isinstance(prev_counter, int):
            prev_counter = 0

        if result["fingerprint"] == prev_fingerprint:
            counter = prev_counter + 1
        else:
            counter = 1

        if counter > MAX_CONSECUTIVE_BLOCKS:
            # Persist the over-cap counter: further stops in this SAME
            # derived state keep passing (FR4 — the user has taken over).
            # A real state change flips the fingerprint and resets the
            # counter to 1 on its own, re-arming blocking.
            write_sidecar(sidecar_path, result["fingerprint"], counter)
            print(
                "queue_stop_guard: WARNING feature={feature} blocked {cap} "
                "consecutive times in the same state; letting the turn end "
                "— check on the implement phase.".format(
                    feature=result["feature"], cap=MAX_CONSECUTIVE_BLOCKS
                ),
                file=sys.stderr,
            )
            return 0

        write_sidecar(sidecar_path, result["fingerprint"], counter)
        print(
            "queue_stop_guard: BLOCK feature={feature} free_slots={slots} "
            "launch={tasks}".format(
                feature=result["feature"],
                slots=result["free_slots"],
                tasks=",".join(result["to_launch"]),
            ),
            file=sys.stderr,
        )
        return 2

    return 0


def main():
    try:
        return hook_main()
    except Exception:  # noqa: BLE001 - fail-open convention: never crash
        return 0


if __name__ == "__main__":
    sys.exit(main())
