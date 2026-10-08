"""Subprocess-driven tests for the record-match classification in
em-workflow/hooks/queue_stop_guard.py (prelaunch-inprogress-routeback,
task0005).

A `pending` task whose last journal event is `failed` is unlaunched (the Stop
hook blocks to request a refill) only when that event's physical line in the
journal equals the task's `routeback_failed_journal_line` record in its own
workflow.yaml block. Otherwise the task is failed and the hook lets the turn
end for that feature (exit 0).

Observed red (base revision, record ignored by the hook): case (b), a
`pending` + `failed` task with no record, exits 2 instead of 0. Every case
that expects exit 0 for a missing, null, mismatching or non-canonical record
fails the same way on the base revision.

Per test/README.md the hook runs as a subprocess with Claude Code Stop-hook
JSON on stdin, and fixtures are built in throwaway temporary directories. No
other test module is imported: the fixture helpers below are rebuilt locally
(layout provenance: tests/test_queue_stop_guard.py's StopGuardFixture).

Each journal case is built from explicit physical lines, so the physical line
of the target `failed` event is known by construction.

routeback-record-quoted-continuation (task0001): the sections headed with that
name pin that the body lines of a multi-line double-quoted scalar, single-quoted
scalar, flow sequence or flow mapping (notably `tasks.{T}.notes`) are never read
as a task boundary, task id, status or record, whatever their indentation, while
a quote or bracket that is not at a value-start position never opens a value.
Observed red (base revision, body lines read like any other line): the 4-space
record-shaped continuation line of a `notes` value is taken as the record, so a
forged record exits 2 instead of 0 and a non-matching one hides the genuine
direct-key record (exit 0 instead of 2).

routeback-record-quoted-continuation (task0002): the sections headed "task0002"
pin two further non-openings. A quote after a `:` or `?` that is not a mapping
indicator inside a plain flow scalar (`[retry:'failed]`) never opens an inner
string, while a quote after a real indicator (`{"a":'b`, `[a: 'b`) still does.
An item indicator, quote or bracket at the start of a plain-scalar continuation
line never opens a value, and the continuation state ends at the parent
indentation. Observed red (base revision): the genuine direct-key record and
task0002 are swallowed, so the hook exits 0 instead of 2.

routeback-record-quoted-open-residual (task0001): the sections headed with that
name pin two more non-openings. A `?` in the middle of a flow scalar
(`[retry? 'failed]`) is an ordinary character, a mapping-key indicator only at
a flow-entry start before a space, a tab or the end of the line, and a line
made only of whitespace other than U+0020 / U+0009 (U+3000, U+00A0, U+000B,
U+000C) is not blank for the tracker. Observed red (base revision): the
genuine direct-key record and task0002 are swallowed, so the hook exits 0
instead of 2.

routeback-record-key-exact-match (task0001): the sections headed with that name
pin that a direct-child line is a record key line only when its key is exactly
`routeback_failed_journal_line` (the colon after the name is followed by a
space, a tab or the end of the line). A line whose key merely starts with
`routeback_failed_journal_line:` (`routeback_failed_journal_line:x: 1`,
`routeback_failed_journal_line:1`) is not a key line and never hides the genuine
record after it. Observed red (base revision, such a line taken as the first
occurrence): the reader returns {} instead of {"task0001": "1"} for the
reproduction block and for the glued-value block, and the hook exits 0 instead
of 2 for the reproduction block. The preservation cases (tab after the colon,
empty value before a record, a lone lookalike line) pass on both revisions.

queue-stop-guard-nonascii-blank-state (task0001): the sections headed with that
name pin that, in the block-scalar state and in the plain-scalar continuation
state, a line made only of non-ASCII whitespace (U+3000, U+00A0, U+000B,
U+000C) neither continues nor ends the state, whatever its indentation, so a
following `- 'x` line opens nothing. Observed red (base revision): that line
ends the state, the `- 'x` line opens a single-quoted value, and the genuine
direct-key record and task0002 are swallowed, so the hook exits 0 instead of 2.
"""

import ast
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_stop_guard.py")

FEATURE = "routeback-record-feature"
RECORD_KEY = "routeback_failed_journal_line"
TARGET = "task0001"
TASK_IDS = ("task0001", "task0002", "task0003")
DEFAULT_STDIN = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})

ABSENT = object()  # the record key is not written at all


# --- fixture builders ------------------------------------------------------


def event_line(event, task, **extra):
    record = {"event": event, "task": task, "at": "2026-07-15T09:00:00+09:00"}
    record.update(extra)
    return json.dumps(record).encode("utf-8")


def record_lines(value):
    """The workflow.yaml line(s) for a record whose raw value text is `value`
    (ABSENT writes nothing; an empty value writes the bare key)."""
    if value is ABSENT:
        return []
    if value == "":
        return ["    %s:" % RECORD_KEY]
    return ["    %s: %s" % (RECORD_KEY, value)]


def notes_block_scalar(indicator, body_lines, body_indent=6):
    """The workflow.yaml lines of a non-null `notes` value written as a block
    scalar: `notes: <indicator>` at the task mapping's direct-child indent,
    then each body line indented by `body_indent` spaces."""
    return ["    notes: %s" % indicator] + [
        " " * body_indent + line for line in body_lines
    ]


def notes_double_quoted(*parts, continuation_indent=6):
    """The workflow.yaml lines of a non-null `notes` value written as a
    multi-line double-quoted scalar: the first part opens the quote, the last
    part closes it, and every part after the first is a continuation line
    indented by `continuation_indent` spaces."""
    if len(parts) < 2:
        raise ValueError("a multi-line scalar needs at least two parts")
    lines = ['    notes: "%s' % parts[0]]
    lines.extend(" " * continuation_indent + part for part in parts[1:-1])
    lines.append(" " * continuation_indent + parts[-1] + '"')
    return lines


def notes_single_quoted(*parts, continuation_indent=6):
    """The workflow.yaml lines of a non-null `notes` value written as a
    multi-line single-quoted scalar: the first part opens the quote, the last
    part closes it, and every part after the first is a continuation line
    indented by `continuation_indent` spaces. `parts` are written verbatim
    (a doubled quote is the caller's to write)."""
    if len(parts) < 2:
        raise ValueError("a multi-line scalar needs at least two parts")
    lines = ["    notes: '%s" % parts[0]]
    lines.extend(" " * continuation_indent + part for part in parts[1:-1])
    lines.append(" " * continuation_indent + parts[-1] + "'")
    return lines


def _notes_flow(opener, closer, parts, continuation_indent, closer_indent):
    if len(parts) < 2:
        raise ValueError("a multi-line flow collection needs at least two parts")
    if closer_indent is None:
        closer_indent = continuation_indent
    lines = ["    notes: %s%s" % (opener, parts[0])]
    lines.extend(" " * continuation_indent + part for part in parts[1:])
    lines.append(" " * closer_indent + closer)
    return lines


def notes_flow_sequence(*parts, continuation_indent=6, closer_indent=None):
    """The workflow.yaml lines of a non-null `notes` value written as a
    multi-line flow sequence: the first part follows `[` on the opening line,
    every part after the first is a continuation line indented by
    `continuation_indent` spaces, and the closing `]` is on a line of its own
    after the last part, indented by `closer_indent` (default: the
    continuation indent). `parts` are written verbatim: the caller supplies
    any `,` separator, so a record- or status-shaped last part stays
    canonical on its own (no trailing comma)."""
    return _notes_flow("[", "]", parts, continuation_indent, closer_indent)


def notes_flow_mapping(*parts, continuation_indent=6, closer_indent=None):
    """Like notes_flow_sequence, for a multi-line flow mapping: `{` opens on
    the `notes:` line and a closing `}` is on a line of its own."""
    return _notes_flow("{", "}", parts, continuation_indent, closer_indent)


def task_spec(
    task_id, status="pending", extra=(), after=(), notes=None, head=()
):
    """`extra`: lines emitted verbatim inside the task's own block, after its
    status line. `after`: lines emitted right after the block, at whatever
    indentation the caller wrote. `notes`: the lines of a non-null `notes`
    entry (see notes_block_scalar / notes_double_quoted), emitted right after
    the status line and before `extra`; None keeps the historical
    `notes: null` line after `extra`. `head`: lines emitted right after the
    `taskNNNN:` key line, before `title`."""
    return {
        "id": task_id,
        "status": status,
        "extra": list(extra),
        "after": list(after),
        "notes": None if notes is None else list(notes),
        "head": list(head),
    }


def build_workflow(tasks, top_lines=(), step_lines=(), tail_lines=()):
    lines = ["schema_version: 1", "feature: %s" % FEATURE]
    lines.extend(top_lines)
    lines.extend(
        [
            "",
            "workflow:",
            "  - id: create-spec",
            "    status: completed",
            "  - id: implement",
            "    status: in_progress",
        ]
    )
    lines.extend(step_lines)
    lines.extend(["  - id: review", "    status: pending", "", "tasks:"])
    for task in tasks:
        lines.append("  %s:" % task["id"])
        lines.extend(task["head"])
        lines.append('    title: "task %s"' % task["id"])
        lines.append("    status: %s" % task["status"])
        if task["notes"] is None:
            lines.extend(task["extra"])
            lines.append("    notes: null")
        else:
            lines.extend(task["notes"])
            lines.extend(task["extra"])
        lines.extend(task["after"])
    lines.extend(tail_lines)
    return "\n".join(lines) + "\n"


def standard_tasks(target_record=ABSENT):
    """task0001..task0003, all `pending`; only task0001 carries a record."""
    return [
        task_spec(TARGET, extra=record_lines(target_record)),
        task_spec("task0002"),
        task_spec("task0003"),
    ]


def journal_bytes(lines, final_lf=True):
    data = b"\n".join(lines)
    if final_lf and lines:
        data += b"\n"
    return data


class Layout:
    """Throwaway integration-worktree layout under a temp directory."""

    def __init__(self, tmp):
        self.root = tmp
        self.journal_dir = os.path.join(
            tmp, ".claude", "worktrees", "em-workflow", FEATURE
        )
        self.docs_dir = os.path.join(
            self.journal_dir, "integration", "feature-docs", FEATURE
        )
        os.makedirs(self.docs_dir)
        self.workflow_path = os.path.join(self.docs_dir, "workflow.yaml")
        self.journal_path = os.path.join(self.journal_dir, "journal.jsonl")

    def write_workflow(self, text):
        data = text if isinstance(text, bytes) else text.encode("utf-8")
        with open(self.workflow_path, "wb") as fh:
            fh.write(data)

    def write_journal(self, data):
        with open(self.journal_path, "wb") as fh:
            fh.write(data)


def invoke_hook(cwd):
    return subprocess.run(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input=DEFAULT_STDIN,
        capture_output=True,
        text=True,
        timeout=15,
    )


def run_scenario(journal, record=ABSENT, workflow_text=None):
    """Runs the hook against one fixture and returns the completed process.
    `journal` is the raw journal file content (bytes). The workflow is the
    standard three pending tasks with `record` on task0001 unless
    `workflow_text` is given."""
    with tempfile.TemporaryDirectory() as tmp:
        layout = Layout(tmp)
        if workflow_text is None:
            workflow_text = build_workflow(standard_tasks(record))
        layout.write_workflow(workflow_text)
        layout.write_journal(journal)
        return invoke_hook(tmp)


class HookAssertions(unittest.TestCase):
    def assert_unlaunched(self, result, launch="task0001,task0002,task0003"):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("launch=%s" % launch, result.stderr)

    def assert_failed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BLOCK", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


# --- AC-1: the three-condition match --------------------------------------


class TestRecordMatch(HookAssertions):
    """AC-1 (a)-(d): `pending` task whose journal last event is `failed`."""

    def test_record_equal_to_the_failed_line_blocks_and_names_the_task(self):  # AC-1 (a)
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), record="1")
        self.assert_unlaunched(result)

    def test_record_equal_to_a_later_failed_line_blocks(self):  # AC-1 (a)
        journal = journal_bytes(
            [
                event_line("launched", "task0002"),
                event_line("merged", "task0002"),
                event_line("failed", TARGET),
            ]
        )
        result = run_scenario(journal, record="3")
        self.assert_unlaunched(result, launch="task0001,task0003")

    def test_no_record_is_failed(self):  # AC-1 (b)
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]))
        self.assert_failed(result)

    def test_null_record_is_failed(self):  # AC-1 (c)
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), record="null")
        self.assert_failed(result)

    def test_record_naming_a_different_line_is_failed(self):  # AC-1 (d)
        journal = journal_bytes(
            [event_line("failed", TARGET), event_line("launched", "task0002")]
        )
        for record in ("2", "3", "100"):
            with self.subTest(record=record):
                self.assert_failed(run_scenario(journal, record=record))

    def test_relaunched_and_failed_again_no_longer_matches_the_old_record(self):  # AC-1 (d)
        journal = journal_bytes(
            [
                event_line("failed", TARGET),  # line 1: the route-back reset
                event_line("launched", TARGET),  # line 2
                event_line("failed", TARGET),  # line 3: the later failure
            ]
        )
        self.assert_failed(run_scenario(journal, record="1"))
        self.assert_failed(run_scenario(journal, record="2"))
        # The same journal does match once the record names the later line.
        self.assert_unlaunched(run_scenario(journal, record="3"))

    def test_trailing_whitespace_after_the_digits_is_still_canonical(self):  # AC-1 (a)
        journal = journal_bytes([event_line("failed", TARGET)])
        for value in ("1   ", "1\t"):
            with self.subTest(value=value):
                self.assert_unlaunched(run_scenario(journal, record=value))

    def test_status_other_than_pending_is_failed_even_with_a_matching_record(self):
        journal = journal_bytes([event_line("failed", TARGET)])
        for status in ("failed", "in_progress", "merged", "cancelled"):
            with self.subTest(status=status):
                workflow = build_workflow(
                    [
                        task_spec(TARGET, status=status, extra=record_lines("1")),
                        task_spec("task0002"),
                    ]
                )
                self.assert_failed(run_scenario(journal, workflow_text=workflow))


class TestUnchangedClassifications(HookAssertions):
    """AC-4: no-event, `launched` and `merged` classifications do not depend
    on the record."""

    def test_no_event_task_is_unlaunched_with_or_without_a_record(self):
        for record in (ABSENT, "7"):
            with self.subTest(record=record):
                result = run_scenario(b"", record=record)
                self.assert_unlaunched(result)

    def test_launched_last_event_is_in_flight_even_when_the_record_matched_an_earlier_failure(self):
        journal = journal_bytes(
            [event_line("failed", TARGET), event_line("launched", TARGET)]
        )
        result = run_scenario(journal, record="1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("free_slots=5", result.stderr)
        self.assertIn("launch=task0002,task0003", result.stderr)

    def test_merged_last_event_is_terminal_even_when_the_record_matched_an_earlier_failure(self):
        journal = journal_bytes(
            [event_line("failed", TARGET), event_line("merged", TARGET)]
        )
        result = run_scenario(journal, record="1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("free_slots=6", result.stderr)
        self.assertIn("launch=task0002,task0003", result.stderr)


# --- AC-2: record value parsing and block scoping ----------------------------


class TestRecordValueParsing(HookAssertions):
    """AC-2: only an unquoted run of ASCII digits whose first digit is 1-9
    (plus trailing whitespace) is a record. The journal's `failed` event sits
    on physical line 1 so every value below would match if it were read
    leniently."""

    NON_CANONICAL = [
        ("zero", "0"),
        ("negative", "-1"),
        ("non-integer", "1.5"),
        ("integral-float", "1.0"),
        ("double-quoted", '"1"'),
        ("single-quoted", "'1'"),
        ("empty", ""),
        ("leading-zero", "01"),
        ("explicit-plus", "+1"),
        ("hex", "0x1"),
        ("tilde-null", "~"),
        ("inline-comment", "1 # comment"),
        ("trailing-text", "1x"),
        ("two-tokens", "1 2"),
        ("flow-sequence", "[1]"),
        ("fullwidth-digit", "１"),
        ("arabic-indic-digit", "١"),
    ]

    def test_non_canonical_values_are_no_record(self):
        journal = journal_bytes([event_line("failed", TARGET)])
        for label, value in self.NON_CANONICAL:
            with self.subTest(value=label):
                self.assert_failed(run_scenario(journal, record=value))

    def test_underscore_separated_digits_are_not_canonical(self):
        # int("1_0") == 10 in Python, so a lenient reader would match line 10.
        lines = [event_line("launched", "task0002")] * 9 + [event_line("failed", TARGET)]
        journal = journal_bytes(lines)
        self.assert_unlaunched(
            run_scenario(journal, record="10"), launch="task0001,task0003"
        )
        self.assert_failed(run_scenario(journal, record="1_0"))

    def test_value_without_a_space_after_the_colon_is_no_record(self):
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=["    %s:1" % RECORD_KEY]),
                task_spec("task0002"),
            ]
        )
        journal = journal_bytes([event_line("failed", TARGET)])
        self.assert_failed(run_scenario(journal, workflow_text=workflow))

    def test_first_occurrence_in_the_block_wins(self):
        journal = journal_bytes(
            [event_line("failed", TARGET), event_line("launched", "task0002")]
        )
        cases = [
            ("valid-then-other", ["1", "2"], True),
            ("other-then-valid", ["2", "1"], False),
            ("null-then-valid", ["null", "1"], False),
            ("zero-then-valid", ["0", "1"], False),
        ]
        for label, values, expect_unlaunched in cases:
            with self.subTest(case=label):
                extra = [line for value in values for line in record_lines(value)]
                workflow = build_workflow(
                    [task_spec(TARGET, extra=extra), task_spec("task0002")]
                )
                result = run_scenario(journal, workflow_text=workflow)
                if expect_unlaunched:
                    self.assert_unlaunched(result, launch="task0001")
                else:
                    self.assert_failed(result)


class TestRecordBlockScoping(HookAssertions):
    """AC-2 (g): the record is read only from the task's own `taskNNNN:`
    block."""

    def setUp(self):
        self.journal = journal_bytes([event_line("failed", TARGET)])

    def test_record_in_another_tasks_block_is_not_this_tasks_record(self):
        workflow = build_workflow(
            [
                task_spec(TARGET),
                task_spec("task0002", extra=record_lines("1")),
                task_spec("task0003"),
            ]
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_record_in_the_previous_tasks_block_is_not_this_tasks_record(self):
        journal = journal_bytes([event_line("failed", "task0002")])
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=record_lines("1")),
                task_spec("task0002"),
                task_spec("task0003"),
            ]
        )
        self.assert_failed(run_scenario(journal, workflow_text=workflow))

    def test_own_record_is_read_when_other_tasks_carry_other_records(self):
        journal = journal_bytes(
            [event_line("failed", "task0002"), event_line("failed", TARGET)]
        )
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=record_lines("2")),
                task_spec("task0002", extra=record_lines("1")),
                task_spec("task0003"),
            ]
        )
        # Both pending tasks match their own records: both are unlaunched.
        self.assert_unlaunched(
            run_scenario(journal, workflow_text=workflow), launch="task0001,task0002,task0003"
        )

    def test_step_level_record_line_is_not_read(self):
        workflow = build_workflow(
            standard_tasks(), step_lines=record_lines("1")
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_top_level_record_line_is_not_read(self):
        workflow = build_workflow(
            standard_tasks(), top_lines=["%s: 1" % RECORD_KEY]
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_record_line_after_the_tasks_mapping_ended_is_not_read(self):
        workflow = build_workflow(
            standard_tasks(),
            tail_lines=["review_notes:", "  %s: 1" % RECORD_KEY],
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_record_line_at_the_task_key_indent_is_not_read(self):
        # A sibling-level line right after task0001's block is outside it.
        workflow = build_workflow(
            [
                task_spec(TARGET, after=["  %s: 1" % RECORD_KEY]),
                task_spec("task0002"),
            ]
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_commented_out_record_line_is_not_read(self):
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=["    # %s: 1" % RECORD_KEY]),
                task_spec("task0002"),
            ]
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))

    def test_key_with_a_longer_name_is_not_the_record(self):
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=["    %s_extra: 1" % RECORD_KEY]),
                task_spec("task0002"),
            ]
        )
        self.assert_failed(run_scenario(self.journal, workflow_text=workflow))


# --- AC-3: physical line counting -------------------------------------------


def valid_event_line_number(lines, target_index):
    """The 1-based number of lines[target_index] when every line that cannot
    become a task's event (blank, malformed, non-object, unknown event,
    invalid task id) is skipped instead of counted -- the number a reader
    that does not count physical lines would compute."""
    position = 0
    for index, raw in enumerate(lines):
        try:
            record = json.loads(raw.decode("utf-8", errors="replace").strip() or "x")
        except ValueError:
            record = None
        valid = (
            isinstance(record, dict)
            and record.get("event") in ("launched", "merged", "failed")
            and isinstance(record.get("task"), str)
            and re.match(r"^task[0-9]+$", record["task"]) is not None
        )
        if valid:
            position += 1
        if index == target_index:
            return position
    raise AssertionError("target index out of range")


SKIPPED_LINE_KINDS = [
    ("blank", b""),
    ("whitespace-only", b"   \t "),
    ("malformed-json", b"{not valid json"),
    ("unknown-event", event_line("retried", "task0001")),
    ("invalid-task-id", event_line("failed", "task-1")),
    ("non-string-task-id", json.dumps({"event": "failed", "task": 1}).encode()),
    ("non-object-json", b"[1, 2]"),
    ("missing-event", json.dumps({"task": "task0001"}).encode()),
]


class TestPhysicalLineCounting(HookAssertions):
    """AC-3 (f): lines that cannot become a task's event still advance the
    line counter."""

    def test_each_skipped_line_kind_before_the_target_is_counted(self):
        target = event_line("failed", TARGET)
        for label, skipped in SKIPPED_LINE_KINDS:
            with self.subTest(kind=label):
                lines = [skipped, target]
                journal = journal_bytes(lines)
                physical = 2
                skipping = valid_event_line_number(lines, 1)
                self.assertEqual(skipping, 1)
                self.assertNotEqual(physical, skipping)
                self.assert_unlaunched(run_scenario(journal, record=str(physical)))
                self.assert_failed(run_scenario(journal, record=str(skipping)))

    def test_all_skipped_kinds_together_before_the_target_are_counted(self):
        lines = [event_line("launched", "task0002")]
        lines.extend(raw for _label, raw in SKIPPED_LINE_KINDS)
        lines.append(event_line("failed", TARGET))
        target_index = len(lines) - 1
        physical = target_index + 1
        skipping = valid_event_line_number(lines, target_index)
        self.assertEqual(physical, 10)
        self.assertEqual(skipping, 2)
        self.assertNotEqual(physical, skipping)

        journal = journal_bytes(lines)
        self.assert_unlaunched(
            run_scenario(journal, record=str(physical)), launch="task0001,task0003"
        )
        self.assert_failed(run_scenario(journal, record=str(skipping)))

    def test_lines_after_the_target_do_not_change_its_line(self):
        lines = [event_line("failed", TARGET), b"", b"{garbage", b"   "]
        journal = journal_bytes(lines)
        self.assert_unlaunched(run_scenario(journal, record="1"))

    def test_final_segment_without_a_terminating_lf_counts_as_a_line(self):
        lines = [b"", b"{garbage", event_line("failed", TARGET)]
        journal = journal_bytes(lines, final_lf=False)
        self.assertFalse(journal.endswith(b"\n"))
        self.assert_unlaunched(run_scenario(journal, record="3"))
        self.assert_failed(run_scenario(journal, record="2"))

    def test_a_trailing_lf_does_not_add_a_line(self):
        # The target is the last line either way; its number is unchanged.
        lines = [b"", event_line("failed", TARGET)]
        for final_lf in (True, False):
            with self.subTest(final_lf=final_lf):
                journal = journal_bytes(lines, final_lf=final_lf)
                self.assert_unlaunched(run_scenario(journal, record="2"))

    def test_cr_inside_a_line_does_not_shift_the_count(self):
        lines = [b"garbage\rmore garbage", event_line("failed", TARGET)]
        journal = journal_bytes(lines)
        # LF-only counting: the target is line 2. A reader that also split on
        # CR would call it line 3.
        self.assert_unlaunched(run_scenario(journal, record="2"))
        self.assert_failed(run_scenario(journal, record="3"))

    def test_crlf_terminated_lines_count_once_each(self):
        lines = [event_line("launched", "task0002"), b"", event_line("failed", TARGET)]
        journal = b"\r\n".join(lines) + b"\r\n"
        self.assert_unlaunched(run_scenario(journal, record="3"), launch="task0001,task0003")
        self.assert_failed(run_scenario(journal, record="2"))

    def test_a_line_of_only_a_cr_counts_as_one_blank_line(self):
        journal = b"\r\n" + event_line("failed", TARGET) + b"\n"
        self.assert_unlaunched(run_scenario(journal, record="2"))
        self.assert_failed(run_scenario(journal, record="1"))

    def test_other_unicode_line_separators_do_not_split_a_line(self):
        separators = [
            ("vertical-tab", b"\x0b"),
            ("form-feed", b"\x0c"),
            ("file-separator", b"\x1c"),
            ("next-line", "\u0085".encode("utf-8")),
            ("line-separator", " ".encode("utf-8")),
            ("paragraph-separator", " ".encode("utf-8")),
        ]
        for label, separator in separators:
            with self.subTest(separator=label):
                lines = [b"garbage" + separator + b"more garbage", event_line("failed", TARGET)]
                journal = journal_bytes(lines)
                self.assert_unlaunched(run_scenario(journal, record="2"))
                self.assert_failed(run_scenario(journal, record="3"))


# --- routeback-record-direct-key: fixture builder (AC-6) -----------------------


class TestFixtureBuilderNotes(unittest.TestCase):
    """AC-6 (routeback-record-direct-key task0001): the builder emits a
    non-null multi-line `notes` value when asked, and `notes: null` when not."""

    def test_default_fixture_still_contains_notes_null(self):
        text = build_workflow(standard_tasks("1"))
        self.assertEqual(text.count("    notes: null\n"), 3)

    def test_block_scalar_notes_option_emits_a_non_null_multi_line_value(self):
        notes = notes_block_scalar("|", ["first line", "second line"])
        text = build_workflow([task_spec(TARGET, notes=notes)])
        self.assertNotIn("notes: null", text)
        self.assertIn("    notes: |\n      first line\n      second line\n", text)

    def test_double_quoted_notes_option_emits_a_non_null_multi_line_value(self):
        notes = notes_double_quoted("first part", "second part", "last part")
        text = build_workflow([task_spec(TARGET, notes=notes)])
        self.assertNotIn("notes: null", text)
        self.assertIn(
            '    notes: "first part\n      second part\n      last part"\n', text
        )

    def test_notes_option_places_notes_before_the_record_key(self):
        notes = notes_block_scalar("|", ["body"])
        text = build_workflow(
            [task_spec(TARGET, notes=notes, extra=record_lines("1"))]
        )
        self.assertLess(text.index("    notes: |"), text.index("    " + RECORD_KEY))


# --- routeback-record-direct-key: only direct keys are read (AC-1..AC-3) -------

# (label, indicator, body indent in spaces). A block scalar's body is indented
# deeper than its `notes` key (4 spaces); an explicit indentation indicator
# counts from the key's own indent.
BLOCK_SCALAR_INDICATORS = [
    ("literal", "|", 6),
    ("literal-strip", "|-", 6),
    ("folded", ">", 6),
    ("folded-strip", ">-", 6),
    ("literal-indent-2", "|2", 6),
    ("literal-keep-indent-2", "|+2", 6),
    ("folded-strip-indent-1", ">-1", 5),
]


def forged_body(value):
    """A notes body whose middle line looks like the route-back record."""
    return ["reason text", "%s: %s" % (RECORD_KEY, value), "more text"]


def load_hook_module():
    """The hook module loaded from its file path (module-level execution is
    guarded by `if __name__ == "__main__":`, so loading does no hook work).
    Only the AC-1 function-level tests use this."""
    spec = importlib.util.spec_from_file_location(
        "queue_stop_guard_direct_key_probe", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRecordReadFunction(unittest.TestCase):
    """AC-1: task_routeback_records_from_workflow, called directly."""

    def records_for(self, workflow_text):
        module = load_hook_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "workflow.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(workflow_text)
            return module.task_routeback_records_from_workflow(path)

    def test_notes_body_record_does_not_shadow_the_direct_key_record(self):  # AC-1 (a)
        workflow = build_workflow(
            [
                task_spec(
                    TARGET,
                    notes=notes_block_scalar("|", ["%s: 3" % RECORD_KEY]),
                    extra=record_lines("1"),
                )
            ]
        )
        self.assertEqual(self.records_for(workflow), {TARGET: "1"})

    def test_record_after_an_empty_block_scalar_at_the_direct_indent_is_read(self):  # AC-1 (b)
        # An empty `notes: |` has no body: the next line at the direct-child
        # indent is a sibling key of `notes`, and is read as the record.
        workflow = build_workflow(
            [
                task_spec(
                    TARGET,
                    notes=notes_block_scalar("|", []),
                    extra=record_lines("1"),
                )
            ]
        )
        self.assertEqual(self.records_for(workflow), {TARGET: "1"})

    def test_notes_body_record_alone_is_no_record(self):  # AC-1
        workflow = build_workflow(
            [task_spec(TARGET, notes=notes_block_scalar("|", forged_body("1")))]
        )
        self.assertEqual(self.records_for(workflow), {})

    def test_blank_and_comment_lines_before_the_first_key_keep_the_direct_indent(self):  # AC-1
        # The direct-child indent comes from the first line that is neither
        # blank nor a comment, so deeper-indented comments above `title:` must
        # not become the reference indent.
        head = ["", "        # deeper comment", "      # another comment"]
        workflow = build_workflow(
            [task_spec(TARGET, head=head, extra=record_lines("1"))]
        )
        self.assertEqual(self.records_for(workflow), {TARGET: "1"})

    def test_block_with_only_blank_and_comment_lines_yields_no_record(self):  # AC-1
        workflow = "\n".join(
            [
                "tasks:",
                "  task0001:",
                "",
                "    # %s: 1" % RECORD_KEY,
                "  task0002:",
                '    title: "task0002"',
                "    %s: 2" % RECORD_KEY,
                "",
            ]
        )
        self.assertEqual(self.records_for(workflow), {"task0002": "2"})


class TestForgedRecordIsNotRead(HookAssertions):
    """AC-2 (TM-1): the journal's `failed` event sits on physical line 1 and
    the task is `pending`, so a record-shaped line with value 1 would make the
    hook demand a relaunch if it were read. No direct-key record exists, so
    the task is failed and the hook exits 0."""

    def setUp(self):
        self.journal = journal_bytes([event_line("failed", TARGET)])

    def run_with_task(self, **spec):
        workflow = build_workflow([task_spec(TARGET, **spec), task_spec("task0002")])
        return run_scenario(self.journal, workflow_text=workflow)

    def test_block_scalar_body_is_not_read_for_every_indicator(self):
        for label, indicator, body_indent in BLOCK_SCALAR_INDICATORS:
            with self.subTest(indicator=indicator, form=label):
                notes = notes_block_scalar(indicator, forged_body("1"), body_indent)
                self.assert_failed(self.run_with_task(notes=notes))

    def test_key_of_a_mapping_nested_under_another_direct_key_is_not_read(self):
        extra = ["    context:", "      %s: 1" % RECORD_KEY]
        self.assert_failed(self.run_with_task(extra=extra))

    def test_key_of_a_mapping_inside_a_sequence_item_is_not_read(self):
        extra = [
            "    attempts:",
            "      - number: 1",
            "        %s: 1" % RECORD_KEY,
        ]
        self.assert_failed(self.run_with_task(extra=extra))

    def test_continuation_line_of_a_multi_line_double_quoted_notes_is_not_read(self):
        notes = notes_double_quoted(
            "tried twice", "%s: 1" % RECORD_KEY, "gave up"
        )
        self.assert_failed(self.run_with_task(notes=notes))

    def test_a_genuine_direct_key_record_is_still_read_next_to_such_content(self):
        notes = notes_block_scalar("|", forged_body("9"))
        result = self.run_with_task(notes=notes, extra=record_lines("1"))
        self.assert_unlaunched(result, launch="task0001,task0002")


class TestNotesBodyDoesNotShadowTheRecord(HookAssertions):
    """AC-3 (TM-1): `notes` precedes the record in the schema key order, so a
    `notes` body line comes before the direct-key record. The journal's
    `failed` event sits on physical line 1 and the task is `pending`."""

    def setUp(self):
        self.journal = journal_bytes([event_line("failed", TARGET)])

    def run_with_notes(self, notes, record):
        workflow = build_workflow(
            [
                task_spec(TARGET, notes=notes, extra=record_lines(record)),
                task_spec("task0002"),
                task_spec("task0003"),
            ]
        )
        return run_scenario(self.journal, workflow_text=workflow)

    def test_non_matching_notes_body_value_does_not_hide_a_matching_record(self):  # AC-3 (a)
        for label, indicator, body_indent in BLOCK_SCALAR_INDICATORS:
            with self.subTest(indicator=indicator, form=label):
                notes = notes_block_scalar(indicator, forged_body("3"), body_indent)
                result = self.run_with_notes(notes, record="1")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("task0001", result.stderr.split("launch=")[1])
                self.assert_unlaunched(result)

    def test_matching_notes_body_value_does_not_replace_a_non_matching_record(self):  # AC-3 (b)
        for label, indicator, body_indent in BLOCK_SCALAR_INDICATORS:
            with self.subTest(indicator=indicator, form=label):
                notes = notes_block_scalar(indicator, forged_body("1"), body_indent)
                self.assert_failed(self.run_with_notes(notes, record="2"))


# --- AC-5: module docstring -------------------------------------------------

# Verbatim module docstring of queue_stop_guard.py at this task's base
# revision (ast.get_docstring(clean=False)), captured before the edit.
PRE_CHANGE_DOCSTRING = (
    'em-workflow Stop hook: queue loop guard (queue_stop_guard.py).\n'
    '\n'
    'Deterministic net for the implement-phase work-queue loop\n'
    '(IMPLEMENTATION.md, "Journal contract" / "Conventions" sections). Fires on\n'
    'every Stop event; blocks the orchestrator from ending its turn while a\n'
    'refillable implementer slot exists for an in-progress feature, naming the\n'
    'tasks to launch. This hook is a NET, not an authority: any unexpected\n'
    'condition (unreadable/malformed files, non-JSON stdin, validation failure,\n'
    'no active feature) exits 0 silently rather than risk wedging the session\n'
    "(fail-open convention, contrasted with bash_guard.py's fail-closed security\n"
    'boundary).\n'
    '\n'
    'Decision (per the first in-progress feature, stable ordering by feature\n'
    'name, that has refillable work):\n'
    "  - Any task's last journal event is `failed`, UNLESS that task's own\n"
    "    workflow.yaml status still reads exactly `pending` (the task's own id,\n"
    '    returned from `failed` to `pending` by route-back, per\n'
    '    references/workflow-patch.md\'s "Re-planning task-id allocation") ->\n'
    '    exit 0 (no block; user decision pending). Such a task is instead\n'
    '    treated as unlaunched.\n'
    '  - No unlaunched tasks, or no free slot (>= MAX_PARALLEL_IMPLEMENTERS\n'
    '    in-flight) -> exit 0.\n'
    '  - Otherwise -> BLOCK: exit 2, stderr names the feature, the free-slot\n'
    '    count, and the task ids to launch (ascending id order, bounded by the\n'
    '    free-slot count).\n'
    '\n'
    'Loop cap: a sidecar file (stop-guard-state.json, sibling of the journal)\n'
    'persists a fingerprint (the derived unlaunched+in-flight task-id sets) and a\n'
    'consecutive-block counter. Three consecutive blocks in the same derived\n'
    'state are allowed; every FURTHER stop in that same state does NOT block\n'
    '(warns on stderr and exits 0 instead) so the user stays in charge — the\n'
    'over-cap counter is persisted, so the guard never resumes blocking an\n'
    'unchanged state (FR4 "stop blocking … let the user take over"). Any state\n'
    'change resets the counter to 1 and re-arms blocking.\n'
    '\n'
    'Only Python stdlib is imported (NFR1).\n'
)

NEW_WORDING_ALL_THREE = "only when all three hold"
NEW_WORDING_RECORD = "`routeback_failed_journal_line` record"
NEW_WORDING_FAILED_OUTCOME = "Any other task whose last event is `failed` is failed"
KEPT_OWN_ID = "the task's own id, returned from `failed` to `pending` by route-back"
REMOVED_RECYCLED = "a recycled task id left behind by a route-back re-plan"
NEW_WORDINGS = (NEW_WORDING_ALL_THREE, NEW_WORDING_RECORD, NEW_WORDING_FAILED_OUTCOME)


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def live_docstring():
    with open(HOOK_PATH, encoding="utf-8") as fh:
        return ast.get_docstring(ast.parse(fh.read()), clean=False)


class TestModuleDocstring(unittest.TestCase):
    """AC-5: the docstring states the three-condition classification and the
    failed outcome, keeps the own-id description and does not reintroduce the
    recycled-id description."""

    def test_live_docstring_states_the_new_classification(self):
        text = normalize_whitespace(live_docstring())
        for wording in NEW_WORDINGS:
            with self.subTest(wording=wording):
                self.assertIn(wording, text)

    def test_new_wordings_are_absent_from_the_pre_change_docstring(self):
        # Negative proof: the same matchers do not fire on the base sample.
        text = normalize_whitespace(PRE_CHANGE_DOCSTRING)
        for wording in NEW_WORDINGS:
            with self.subTest(wording=wording):
                self.assertNotIn(wording, text)

    def test_anchor_is_present_in_both_the_sample_and_the_live_docstring(self):
        # Non-vacuity guard for the negative proof above.
        self.assertIn(KEPT_OWN_ID, normalize_whitespace(PRE_CHANGE_DOCSTRING))
        self.assertIn(KEPT_OWN_ID, normalize_whitespace(live_docstring()))

    def test_live_docstring_keeps_the_own_id_description(self):
        self.assertIn(KEPT_OWN_ID, normalize_whitespace(live_docstring()))

    def test_live_docstring_does_not_reintroduce_the_recycled_id_description(self):
        self.assertNotIn(REMOVED_RECYCLED, normalize_whitespace(live_docstring()))


DIRECT_KEY_WORDINGS = ("direct keys", "block scalar bodies", "nested")
RECORD_READ_FUNCTION = "task_routeback_records_from_workflow"


def live_record_read_docstring():
    with open(HOOK_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == RECORD_READ_FUNCTION:
            return ast.get_docstring(node, clean=False)
    raise AssertionError("%s not found" % RECORD_READ_FUNCTION)


def live_record_regex_comment():
    """The comment block directly above `ROUTEBACK_RECORD_KEY = ...`."""
    with open(HOOK_PATH, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    anchor = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("ROUTEBACK_RECORD_KEY =")
    )
    comment = []
    index = anchor - 1
    while index >= 0 and lines[index].startswith("#"):
        comment.insert(0, lines[index].lstrip("#"))
        index -= 1
    return " ".join(comment)


class TestDirectKeyWording(unittest.TestCase):
    """AC-5 (routeback-record-direct-key task0001): the module docstring, the
    record-read function docstring and the record regex comment state that
    only direct keys of the task's own mapping are read and that block scalar
    bodies and nested lines are not."""

    def assert_states_direct_keys(self, text):
        text = normalize_whitespace(text)
        self.assertTrue(text, "expected a non-empty docstring or comment")
        for wording in DIRECT_KEY_WORDINGS:
            with self.subTest(wording=wording):
                self.assertIn(wording, text)

    def test_module_docstring_states_direct_keys_only(self):
        self.assert_states_direct_keys(live_docstring())

    def test_record_read_function_docstring_states_direct_keys_only(self):
        self.assert_states_direct_keys(live_record_read_docstring())

    def test_record_regex_comment_states_direct_keys_only(self):
        self.assert_states_direct_keys(live_record_regex_comment())

    def test_wording_matchers_do_not_fire_on_the_pre_change_docstring(self):
        # Negative proof: the same matchers do not fire on the base sample.
        text = normalize_whitespace(PRE_CHANGE_DOCSTRING)
        self.assertNotIn("direct keys", text)
        self.assertNotIn("block scalar bodies", text)


# --- AC-6: fail-open on unreadable or garbled input ----------------------------


class TestFailOpen(HookAssertions):
    """AC-6: an unreadable or garbled workflow.yaml or journal never crashes
    the hook and never blocks."""

    def test_journal_that_is_a_directory_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.write_workflow(build_workflow(standard_tasks("1")))
            os.makedirs(layout.journal_path)
            result = invoke_hook(tmp)
        self.assert_failed(result)

    def test_workflow_that_is_a_directory_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = Layout(tmp)
            layout.write_journal(journal_bytes([event_line("failed", TARGET)]))
            os.makedirs(layout.workflow_path)
            result = invoke_hook(tmp)
        self.assert_failed(result)

    def test_binary_garbage_workflow_exits_0(self):
        garbage = bytes(range(256)) * 4
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), workflow_text=garbage)
        self.assert_failed(result)

    def test_garbled_bytes_in_the_record_line_are_no_record(self):
        workflow = build_workflow(standard_tasks("RECORD_PLACEHOLDER")).encode("utf-8")
        workflow = workflow.replace(b"RECORD_PLACEHOLDER", b"1\xff\xfe")
        self.assertIn(b"1\xff\xfe", workflow)
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), workflow_text=workflow)
        self.assert_failed(result)

    def test_garbled_bytes_in_the_status_line_are_not_pending(self):
        tasks = [
            task_spec(TARGET, status="STATUS_PLACEHOLDER", extra=record_lines("1")),
            task_spec("task0002"),
        ]
        workflow = build_workflow(tasks).encode("utf-8")
        workflow = workflow.replace(b"STATUS_PLACEHOLDER", b"pend\xffing")
        self.assertIn(b"pend\xffing", workflow)
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), workflow_text=workflow)
        self.assert_failed(result)

    def test_extremely_long_digit_record_exits_0(self):
        value = "1" + "0" * 6000
        result = run_scenario(journal_bytes([event_line("failed", TARGET)]), record=value)
        self.assert_failed(result)

    def test_invalid_utf8_and_nul_lines_before_the_target_are_counted(self):
        lines = [b"\xff\xfe\xfd", b"\x00\x00{\x00", event_line("failed", TARGET)]
        journal = journal_bytes(lines)
        self.assert_unlaunched(run_scenario(journal, record="3"))
        self.assert_failed(run_scenario(journal, record="1"))

    def test_record_naming_a_garbled_journal_line_does_not_match(self):
        # The recorded line cannot be parsed, so the task's last event is the
        # earlier valid `failed` line, which the record does not name.
        lines = [event_line("failed", TARGET), b"\xff\xfe garbled"]
        journal = journal_bytes(lines)
        self.assert_failed(run_scenario(journal, record="2"))


# --- routeback-record-quoted-continuation: fixture helpers ---------------------

FORM_LABELS = ("double-quoted", "single-quoted", "flow-sequence", "flow-mapping")


def record_entry(value):
    return "%s: %s" % (RECORD_KEY, value)


def form_notes(
    label, middle, continuation_indent=4, last="gave up", closer_indent=None
):
    """`notes` lines of the `label` form: an opening line holding "tried
    twice", then the `middle` parts as continuation lines. The quoted forms
    end with a closing part (`last`) that carries the closing quote; the flow
    forms end with the last `middle` part and a closing bracket on a line of
    its own (indented by `closer_indent`, default the continuation indent), so
    a record- or status-shaped last `middle` part has no trailing comma."""
    middle = list(middle)
    kwargs = {"continuation_indent": continuation_indent}
    if label == "double-quoted":
        return notes_double_quoted("tried twice", *middle, last, **kwargs)
    if label == "single-quoted":
        return notes_single_quoted("tried twice", *middle, last, **kwargs)
    kwargs["closer_indent"] = closer_indent
    if label == "flow-sequence":
        return notes_flow_sequence("tried twice,", *middle, **kwargs)
    if label == "flow-mapping":
        return notes_flow_mapping("reason: tried twice,", *middle, **kwargs)
    raise ValueError(label)


def call_reader(name, content):
    """Calls the hook module's reader `name` on a workflow.yaml holding
    `content` (text or bytes) and returns its result; a generator reader is
    fully consumed into a list."""
    module = load_hook_module()
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "workflow.yaml")
        with open(path, "wb") as fh:
            fh.write(data)
        result = getattr(module, name)(path)
        if name == "iter_task_block_lines":
            result = list(result)
        return result


class QuotedValueHookCase(HookAssertions):
    """Base for the hook-subprocess cases: the journal's `failed` event of
    task0001 sits on physical line 1, and task0001 is `pending`."""

    def setUp(self):
        self.journal = journal_bytes([event_line("failed", TARGET)])

    def run_target(self, notes=None, extra=(), head=(), journal=None, **build):
        tasks = [
            task_spec(TARGET, notes=notes, extra=extra, head=head),
            task_spec("task0002"),
            task_spec("task0003"),
        ]
        workflow = build_workflow(tasks, **build)
        data = self.journal if journal is None else journal
        return run_scenario(data, workflow_text=workflow)

    def assert_launches_target(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("BLOCK", result.stderr)
        launched = result.stderr.split("launch=")[1].strip().split(",")
        self.assertIn(TARGET, launched)


class TestQuotedFormFixtureBuilders(unittest.TestCase):
    """The builders for single-quoted and flow-form multi-line `notes`."""

    def test_single_quoted_notes_emits_a_multi_line_value(self):
        notes = notes_single_quoted("first part", "second part", "last part")
        text = build_workflow([task_spec(TARGET, notes=notes)])
        self.assertNotIn("notes: null", text)
        self.assertIn(
            "    notes: 'first part\n      second part\n      last part'\n", text
        )

    def test_flow_sequence_notes_emits_a_multi_line_value(self):
        notes = notes_flow_sequence("first,", "second")
        text = build_workflow([task_spec(TARGET, notes=notes)])
        self.assertIn("    notes: [first,\n      second\n      ]\n", text)

    def test_flow_mapping_notes_emits_a_multi_line_value(self):
        notes = notes_flow_mapping("a: 1,", "b: 2")
        text = build_workflow([task_spec(TARGET, notes=notes)])
        self.assertIn("    notes: {a: 1,\n      b: 2\n      }\n", text)

    def test_continuation_indent_applies_to_every_continuation_line(self):
        for indent in (4, 2, 0):
            with self.subTest(indent=indent):
                pad = " " * indent
                self.assertEqual(
                    notes_single_quoted("a", "b", "c", continuation_indent=indent),
                    ["    notes: 'a", pad + "b", pad + "c'"],
                )
                self.assertEqual(
                    notes_flow_sequence("a,", "b", continuation_indent=indent),
                    ["    notes: [a,", pad + "b", pad + "]"],
                )
                self.assertEqual(
                    notes_flow_mapping("a: 1,", "b: 2", continuation_indent=indent),
                    ["    notes: {a: 1,", pad + "b: 2", pad + "}"],
                )

    def test_flow_closer_indent_overrides_only_the_closing_line(self):
        self.assertEqual(
            notes_flow_sequence("a,", "b", continuation_indent=0, closer_indent=4),
            ["    notes: [a,", "b", "    ]"],
        )

    def test_form_notes_covers_every_form_with_the_record_as_the_last_flow_entry(self):
        for label in FORM_LABELS:
            with self.subTest(form=label):
                lines = form_notes(label, [record_entry(1)])
                self.assertEqual(lines[0].split(":", 1)[0], "    notes")
                self.assertIn("    " + record_entry(1), lines)
        self.assertEqual(
            form_notes("double-quoted", [record_entry(1)]),
            ['    notes: "tried twice', "    " + record_entry(1), '    gave up"'],
        )
        self.assertEqual(
            form_notes("flow-sequence", [record_entry(1)]),
            ["    notes: [tried twice,", "    " + record_entry(1), "    ]"],
        )

    def test_a_single_part_is_rejected(self):
        for builder in (notes_single_quoted, notes_flow_sequence, notes_flow_mapping):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(ValueError):
                    builder("only")


# --- routeback-record-quoted-continuation: AC-1 (the reader, called directly) ---


class TestQuotedValueBodyRecordRead(unittest.TestCase):
    """AC-1: task_routeback_records_from_workflow on the reproduction fixture
    returns no record. The body lines sit at the direct keys' indentation (4)
    and, for the shallower cases, at 2 and 0."""

    def test_reproduction_fixture_has_no_record_in_every_form(self):  # AC-1
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, [record_entry(1)], 4)
                workflow = build_workflow([task_spec(TARGET, notes=notes)])
                self.assertEqual(
                    call_reader("task_routeback_records_from_workflow", workflow), {}
                )

    def test_the_literal_reproduction_lines_have_no_record(self):  # AC-1
        workflow = "\n".join(
            [
                "tasks:",
                "  task0001:",
                '    title: "task task0001"',
                "    status: pending",
                '    notes: "tried twice',
                "    routeback_failed_journal_line: 1",
                '    gave up"',
                "",
            ]
        )
        self.assertEqual(
            call_reader("task_routeback_records_from_workflow", workflow), {}
        )

    def test_shallower_body_lines_are_not_read_either(self):  # AC-1
        for label in FORM_LABELS:
            for indent in (2, 0):
                with self.subTest(form=label, indent=indent):
                    notes = form_notes(label, [record_entry(1)], indent)
                    workflow = build_workflow([task_spec(TARGET, notes=notes)])
                    self.assertEqual(
                        call_reader("task_routeback_records_from_workflow", workflow),
                        {},
                    )

    def test_direct_key_record_after_the_value_is_read_in_every_form(self):  # AC-1
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, [record_entry(3)], 4)
                workflow = build_workflow(
                    [task_spec(TARGET, notes=notes, extra=record_lines("1"))]
                )
                self.assertEqual(
                    call_reader("task_routeback_records_from_workflow", workflow),
                    {TARGET: "1"},
                )

    def test_body_lines_are_not_yielded_and_the_opening_line_is(self):  # AC-1
        notes = form_notes("double-quoted", [record_entry(1), "status: merged"], 4)
        workflow = build_workflow([task_spec(TARGET, notes=notes)])
        yielded = call_reader("iter_task_block_lines", workflow)
        self.assertEqual({task for task, _line in yielded}, {TARGET})
        texts = [line for _task, line in yielded]
        self.assertIn('    notes: "tried twice\n', texts)
        self.assertFalse([line for line in texts if RECORD_KEY in line])
        self.assertFalse([line for line in texts if "gave up" in line])


# --- routeback-record-quoted-continuation: AC-2 / AC-3 (forgery and hiding) -----


class TestQuotedValueRecordForgery(QuotedValueHookCase):
    """AC-2 (TM-1): the only record-shaped line is a 4-space continuation line
    of a multi-line `notes` value; there is no direct-key record, so the task
    is failed and the hook exits 0 without BLOCK."""

    def test_record_shaped_continuation_line_is_not_read_in_every_form(self):  # AC-2
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, [record_entry(1)], 4)
                self.assert_failed(self.run_target(notes=notes))

    def test_shallower_continuation_lines_are_not_read_either(self):  # AC-2
        for label in FORM_LABELS:
            for indent in (2, 0):
                with self.subTest(form=label, indent=indent):
                    notes = form_notes(label, [record_entry(1)], indent)
                    self.assert_failed(self.run_target(notes=notes))


class TestQuotedValueDoesNotHideTheRecord(QuotedValueHookCase):
    """AC-3 (TM-2): a non-matching record-shaped continuation line comes
    before the genuine direct-key record; the genuine one is still read."""

    def test_non_matching_body_value_does_not_hide_the_genuine_record(self):  # AC-3
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, [record_entry(3)], 4)
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_target(result)

    def test_shallower_body_lines_do_not_hide_the_genuine_record(self):  # AC-3
        for label in FORM_LABELS:
            for indent in (2, 0):
                with self.subTest(form=label, indent=indent):
                    notes = form_notes(label, [record_entry(3)], indent)
                    result = self.run_target(notes=notes, extra=record_lines("1"))
                    self.assert_launches_target(result)

    def test_matching_body_value_does_not_replace_a_non_matching_record(self):  # AC-3
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, [record_entry(1)], 4)
                self.assert_failed(self.run_target(notes=notes, extra=record_lines("2")))


# --- routeback-record-quoted-continuation: AC-4 (task keys inside a body) ---------


def task_key_shaped_notes(label, middle, last="    gave up"):
    """A `notes` value whose body holds the `middle` lines, written verbatim
    (explicit leading spaces), with the closing line at 4 spaces."""
    return form_notes(
        label, middle, continuation_indent=0, last=last, closer_indent=4
    )


class TestQuotedValueTaskKeys(QuotedValueHookCase):
    """AC-4 (TM-1, TM-2): a task-key-shaped line inside a body never moves the
    lines after it to another task and never ends the section."""

    def test_forged_record_for_another_task_is_not_read(self):  # AC-4 (a)
        # task0002's `failed` event is journal line 1; real task0002 is
        # `pending` with no record, so it is failed -> exit 0. task0001 has no
        # event, so exit 0 can only come from task0002 being failed.
        journal = journal_bytes([event_line("failed", "task0002")])
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = task_key_shaped_notes(
                    label, ["  task0002:", "    " + record_entry(1)]
                )
                self.assert_failed(self.run_target(notes=notes, journal=journal))

    def test_forged_status_for_another_task_is_not_read(self):  # AC-4 (b)
        journal = journal_bytes([event_line("failed", "task0002")])
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = task_key_shaped_notes(
                    label, ["  task0002:", "    status: pending"]
                )
                workflow = build_workflow(
                    [
                        task_spec(TARGET, notes=notes),
                        task_spec(
                            "task0002", status="failed", extra=record_lines("1")
                        ),
                    ]
                )
                self.assert_failed(
                    run_scenario(journal, workflow_text=workflow)
                )

    def test_forged_task_key_never_reaches_the_launch_list(self):  # AC-4 (c)
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = task_key_shaped_notes(label, ["  task0099:"])
                result = self.run_target(notes=notes, journal=b"")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("task0099", result.stderr)
                self.assertIn("launch=task0001,task0002,task0003", result.stderr)

    def test_column_zero_continuation_does_not_end_the_section(self):  # AC-4 (d)
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, ["middle line"], continuation_indent=0)
                result = self.run_target(notes=notes, journal=b"")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("launch=task0001,task0002,task0003", result.stderr)

    def test_column_zero_continuation_values_enumerate_the_following_tasks(self):  # AC-4 (d)
        for label in FORM_LABELS:
            with self.subTest(form=label):
                notes = form_notes(label, ["middle line"], continuation_indent=0)
                workflow = build_workflow(
                    [task_spec(TARGET, notes=notes), task_spec("task0002")]
                )
                self.assertEqual(
                    call_reader("task_ids_from_workflow", workflow),
                    ["task0001", "task0002"],
                )


# --- routeback-record-quoted-continuation: AC-5 (opening and closing boundaries) --

ROW = "    " + record_entry(1)  # a record-shaped line at the direct keys' indent


class TestQuotedValueEscapesDoNotClose(QuotedValueHookCase):
    """AC-5 (a): an escaped quote never closes, so the 4-space record-shaped
    line before the real close is body (exit 0, no direct-key record)."""

    def test_backslash_escaped_double_quote_does_not_close(self):
        notes = [
            '    notes: "tried twice',
            '      he said \\"stop\\" and left',
            ROW,
            '      gave up"',
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_doubled_single_quote_does_not_close(self):
        notes = [
            "    notes: 'tried twice",
            "      it''s done",
            ROW,
            "      gave up'",
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_double_quoted_line_ending_in_a_backslash_continues(self):
        notes = [
            '    notes: "tried twice \\',
            ROW,
            '      gave up"',
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_escaped_quote_on_the_opening_line_does_not_close(self):
        notes = ['    notes: "tried \\" twice', ROW, '      gave up"']
        self.assert_failed(self.run_target(notes=notes))


class TestQuotedValueRealClosesClose(QuotedValueHookCase):
    """AC-5 (b): a real close closes; the genuine direct-key record after it
    is read (exit 2, task0001 named)."""

    def test_escaped_backslash_then_quote_closes(self):
        notes = ['    notes: "tried twice', '      path C:\\\\"']
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )

    def test_one_line_value_followed_by_a_comment_with_a_lone_quote(self):
        extra = ['    title: "x" # "'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_one_line_single_quoted_value_followed_by_a_comment_with_a_quote(self):
        extra = ["    label: 'x' # '", '    other: [a] # ["'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_doubled_quote_then_a_real_single_quote_close(self):
        notes = ["    notes: 'it''s", "      done'"]
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )

    def test_closing_line_text_after_the_quote_is_not_an_opening(self):
        notes = ['    notes: "tried twice', '      gave up" # "lone quote']
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )


class TestQuotedValueNotOpenings(QuotedValueHookCase):
    """AC-5 (c): a quote or bracket that is not at a value-start position never
    opens, so the genuine direct-key record after it is read (exit 2)."""

    def test_block_scalar_bodies_never_open(self):
        for label, indicator, body_indent in BLOCK_SCALAR_INDICATORS:
            with self.subTest(indicator=indicator, form=label):
                notes = notes_block_scalar(
                    indicator,
                    ['said "never', "and an unclosed [ bracket", "{ brace"],
                    body_indent,
                )
                self.assert_launches_target(
                    self.run_target(notes=notes, extra=record_lines("1"))
                )

    def test_block_scalar_body_lines_starting_with_a_quote_or_bracket_never_open(self):
        for indicator in ("|", ">-"):
            with self.subTest(indicator=indicator):
                notes = notes_block_scalar(
                    indicator, ['"unclosed', "'unclosed", "[unclosed", "{unclosed"]
                )
                self.assert_launches_target(
                    self.run_target(notes=notes, extra=record_lines("1"))
                )

    def test_sequence_item_block_scalar_body_never_opens(self):
        extra = ["    attempts:", "      - |", '        unclosed " and [ here'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_comment_lines_never_open(self):
        extra = [
            '    # an unclosed " quote',
            "    # an unclosed ' quote",
            "    # an unclosed [ bracket",
            "    # an unclosed { brace",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_comment_line_inside_a_nested_mapping_never_opens(self):
        extra = ["    context:", '      # "unclosed', "      key: value"] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_plain_scalars_never_open(self):
        extra = [
            "    reason: don't give up",
            "    memo: it's [fine",
            '    said: he said "hi',
            "    brace: a { b",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_plain_scalar_continuation_lines_never_open(self):
        extra = [
            "    reason: first part",
            '      "second part [',
            "      it's {here",
            "      '[third",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_top_level_block_scalar_before_the_tasks_section_never_opens(self):
        for indicator in ("|", ">-"):
            with self.subTest(indicator=indicator):
                top = [
                    "summary: %s" % indicator,
                    '  unclosed " quote',
                    "  and an unclosed [ bracket",
                ]
                result = self.run_target(
                    extra=record_lines("1"), top_lines=top
                )
                self.assert_launches_target(result)

    def test_step_level_block_scalar_never_opens(self):
        step = ["    notes: |", '      unclosed " quote', "      and [ bracket"]
        self.assert_launches_target(
            self.run_target(extra=record_lines("1"), step_lines=step)
        )

    def test_quoted_key_value_is_not_a_value_start(self):
        # A quote after a quoted key is not an opening (SPEC A6): the line is
        # read as it was before, the genuine record after it is still read.
        extra = ['    "quoted key": "value'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_anchor_or_tag_prefixed_values_are_not_openings(self):
        extra = ['    a: &anchor "unclosed', '    b: !!str "unclosed'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))


class TestQuotedValueStartsOnTheNextLine(QuotedValueHookCase):
    """AC-5 (d): a value that starts on the line after its key is a value
    start too."""

    def test_double_quoted_value_on_the_next_line_hides_its_body(self):
        notes = [
            "    notes:",
            '      "tried twice',
            ROW,
            '      gave up"',
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_single_quoted_and_flow_values_on_the_next_line_hide_their_body(self):
        cases = {
            "single-quoted": ["    notes:", "      'tried twice", ROW, "      gave up'"],
            "flow-sequence": ["    notes:", "      [tried twice,", ROW, "      ]"],
            "flow-mapping": ["    notes:", "      {reason: tried twice,", ROW, "      }"],
        }
        for label, notes in cases.items():
            with self.subTest(form=label):
                self.assert_failed(self.run_target(notes=notes))

    def test_value_after_a_comment_line_following_the_key_is_a_value_start(self):
        notes = ["    notes:", "      # a comment", "", '      "tried twice', ROW, '      gave up"']
        self.assert_failed(self.run_target(notes=notes))

    def test_genuine_record_after_such_a_value_is_read(self):
        notes = ["    notes:", '      "tried twice', '      gave up"']
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )

    def test_a_less_indented_quoted_line_after_a_null_key_is_not_a_value_start(self):
        # `notes:` has no value; the next line is a sibling (a quoted key), so
        # its unclosed quote does not hide the record that follows.
        extra = ["    notes:", '    "sibling": "unclosed'] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))


class TestQuotedValueNestedAndItemValues(QuotedValueHookCase):
    """AC-5: values in nested keys and sequence items are value starts."""

    def test_nested_key_value_hides_its_body(self):
        extra = [
            "    context:",
            '      reason: "tried twice',
            ROW,
            '      gave up"',
        ]
        self.assert_failed(self.run_target(extra=extra))

    def test_sequence_item_value_hides_its_body(self):
        extra = [
            "    attempts:",
            '      - "tried twice',
            ROW,
            '        gave up"',
        ]
        self.assert_failed(self.run_target(extra=extra))

    def test_sequence_item_key_value_hides_its_body(self):
        extra = [
            "    attempts:",
            "      - reason: 'tried twice",
            ROW,
            "        gave up'",
        ]
        self.assert_failed(self.run_target(extra=extra))

    def test_flow_sequence_item_value_hides_its_body(self):
        extra = [
            "    attempts:",
            "      - [tried twice,",
            ROW,
            "      ]",
        ]
        self.assert_failed(self.run_target(extra=extra))

    def test_item_whose_value_starts_on_the_next_line_hides_its_body(self):
        extra = [
            "    attempts:",
            "      -",
            '        "tried twice',
            ROW,
            '        gave up"',
        ]
        self.assert_failed(self.run_target(extra=extra))

    def test_top_level_and_step_level_values_hide_their_body(self):
        top = ['summary: "tried twice', "tasks:", "  task0099:", 'gave up"']
        step = ["    notes: 'tried twice", "tasks:", "  task0098:", "    gave up'"]
        result = self.run_target(extra=record_lines("1"), top_lines=top, step_lines=step)
        self.assert_launches_target(result)
        self.assertNotIn("task0099", result.stderr)
        self.assertNotIn("task0098", result.stderr)


class TestFlowValueBoundaries(QuotedValueHookCase):
    """AC-5 (e): flow collections nest, and a bracket inside an inner quoted
    string or a comment is not counted."""

    FLOW_LINES = [
        "    notes: [tried twice,",
        "      {nested: [1, 2]},",
        '      "closing ] and } in a string",',
        "      'another ] in a string',",
        "      # a comment with ] and }",
        "      plain, # trailing comment ]",
    ]

    def flow_notes(self, last_entry):
        return list(self.FLOW_LINES) + [last_entry, "      ]"]

    def test_record_shaped_entry_inside_the_flow_value_is_not_read(self):
        self.assert_failed(self.run_target(notes=self.flow_notes(ROW)))

    def test_genuine_record_after_the_real_close_is_read(self):
        notes = self.flow_notes("      last entry")
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )

    def test_flow_mapping_with_nested_collections(self):
        lines = [
            "    notes: {reason: tried twice,",
            '      detail: {text: "a } in a string", list: [1, {x: 2}]},',
            "      # } in a comment",
            ROW,
            "      }",
        ]
        self.assert_failed(self.run_target(notes=lines))
        lines[3] = "      last: entry"
        self.assert_launches_target(
            self.run_target(notes=lines, extra=record_lines("1"))
        )

    def test_nesting_depth_must_return_to_zero_before_the_value_closes(self):
        notes = [
            "    notes: [[tried twice,",
            "      ],",
            ROW,
            "      ]",
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_inner_quoted_string_may_span_lines(self):
        notes = [
            "    notes: [tried twice,",
            '      "a string with ] that',
            "    continues and has a } too\",",
            ROW,
            "      ]",
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_quote_inside_a_plain_flow_scalar_is_not_an_inner_string(self):
        # The apostrophe in `it's` is inside a plain flow scalar, so the `]`
        # on the same line is counted and closes the value there.
        notes = ["    notes: [it's a plain entry]"]
        self.assert_launches_target(
            self.run_target(notes=notes, extra=record_lines("1"))
        )


class TestOneLineValuesAreUnchanged(QuotedValueHookCase):
    """AC-5 (f): a value that closes on its own line leaves every following
    line read as before."""

    def test_one_line_quoted_and_flow_values_before_the_record(self):
        extra = [
            "    files: []",
            "    skills: [infra-impl]",
            "    requirements: [FR1, FR2]",
            '    label: "a"',
            "    other: 'b'",
            "    map: {a: 1, b: [2, 3]}",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_one_line_values_in_sequence_items_before_the_record(self):
        extra = [
            "    files:",
            '      - "em-workflow/hooks/queue_stop_guard.py"',
            "      - 'tests/test_x.py'",
            "      - [a, b]",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_one_line_value_with_trailing_comment_before_the_record(self):
        extra = [
            '    a: "x" # "',
            "    b: 'y' # '",
            "    c: [z] # [",
            "    d: {k: v} # {",
        ] + record_lines("1")
        self.assert_launches_target(self.run_target(extra=extra))

    def test_one_line_value_status_is_still_read(self):
        workflow = build_workflow(
            [
                task_spec(TARGET, head=['    label: "x"', "    list: [a, b]"]),
                task_spec("task0002", status="failed"),
            ]
        )
        self.assertEqual(
            call_reader("task_statuses_from_workflow", workflow),
            {TARGET: "pending", "task0002": "failed"},
        )


# --- routeback-record-quoted-continuation: direct task-id enumeration cases -------

# (label, workflow.yaml text, expected task ids). Every body line below looks
# like a task key or a `tasks:` line; none of them is read.
ENUMERATION_CASES = [
    (
        "double-quoted-with-task-key-and-tasks-line",
        'tasks:\n  task0001:\n    notes: "a\n  task0002:\ntasks:\nb"\n  task0003:\n',
        ["task0001", "task0003"],
    ),
    (
        "single-quoted-with-doubled-quote",
        "tasks:\n  task0001:\n    notes: 'it''s\n  task0002:\n''s done'\n  task0003:\n",
        ["task0001", "task0003"],
    ),
    (
        "flow-sequence-column-zero",
        "tasks:\n  task0001:\n    notes: [a,\n  task0002:\nb\n]\n  task0003:\n",
        ["task0001", "task0003"],
    ),
    (
        "flow-mapping-nested",
        "tasks:\n  task0001:\n    notes: {a: [1,\n  task0002:\n], b: {c: 1}\n}\n  task0003:\n",
        ["task0001", "task0003"],
    ),
    (
        "value-opened-before-the-tasks-section",
        'summary: "line\ntasks:\n  task0099:\nend"\ntasks:\n  task0001:\n',
        ["task0001"],
    ),
    (
        "step-list-value-opened-before-the-tasks-section",
        "workflow:\n  - id: implement\n    notes: 'x\ntasks:\n  task0099:\n    y'\ntasks:\n  task0001:\n",
        ["task0001"],
    ),
    (
        "sequence-item-value",
        'tasks:\n  task0001:\n    files:\n      - "a\n  task0002:\n      b"\n  task0003:\n',
        ["task0001", "task0003"],
    ),
    (
        "nested-key-value",
        "tasks:\n  task0001:\n    ctx:\n      k: [a,\n  task0002:\n      ]\n  task0003:\n",
        ["task0001", "task0003"],
    ),
    (
        "next-line-value",
        'tasks:\n  task0001:\n    notes:\n      "a\n  task0002:\n      b"\n  task0003:\n',
        ["task0001", "task0003"],
    ),
    (
        "block-scalar-body-quote-does-not-open",
        'tasks:\n  task0001:\n    notes: |\n      a " b\n  task0002:\n    title: x\n',
        ["task0001", "task0002"],
    ),
    (
        "comment-quote-does-not-open",
        'tasks:\n  task0001:\n    # a " b\n  task0002:\n',
        ["task0001", "task0002"],
    ),
    (
        "plain-apostrophe-does-not-open",
        "tasks:\n  task0001:\n    title: don't\n  task0002:\n",
        ["task0001", "task0002"],
    ),
    (
        "crlf-line-endings",
        'tasks:\r\n  task0001:\r\n    notes: "a\r\n  task0002:\r\nb"\r\n  task0003:\r\n',
        ["task0001", "task0003"],
    ),
    (
        "escaped-backslash-closes",
        'tasks:\n  task0001:\n    notes: "a\\\\"\n  task0002:\n',
        ["task0001", "task0002"],
    ),
    (
        "escaped-quote-does-not-close",
        'tasks:\n  task0001:\n    notes: "a\\"\n  task0002:\nb"\n  task0003:\n',
        ["task0001", "task0003"],
    ),
]


class TestTaskIdEnumeration(unittest.TestCase):
    """FR1: task_ids_from_workflow reads no body line of a multi-line quoted
    scalar or flow collection, whatever its indentation."""

    def test_enumeration_cases(self):
        for label, text, expected in ENUMERATION_CASES:
            with self.subTest(case=label):
                self.assertEqual(
                    call_reader("task_ids_from_workflow", text), expected
                )

    def test_block_scan_attributes_lines_only_to_real_tasks(self):
        for label, text, expected in ENUMERATION_CASES:
            with self.subTest(case=label):
                scanned = call_reader("iter_task_block_lines", text)
                self.assertLessEqual({task for task, _line in scanned}, set(expected))


# --- routeback-record-quoted-continuation: AC-6 (fail-open) ---------------------


class TestUnclosedValuesFailOpen(QuotedValueHookCase):
    """AC-6 (a) (TM-3): a value that never closes before end of file hides
    every later line from the hook, which then falls to the non-blocking side
    without crashing."""

    UNCLOSED_FORMS = {
        "double-quoted": ['    notes: "tried twice'],
        "single-quoted": ["    notes: 'tried twice"],
        "flow-sequence": ["    notes: [tried twice,"],
        "flow-mapping": ["    notes: {reason: tried twice,"],
        "nested-flow": ["    notes: [tried twice, [{a: 1},"],
    }

    def test_unclosed_value_with_record_and_task_key_lines_after_it(self):
        for label, opening in self.UNCLOSED_FORMS.items():
            with self.subTest(form=label):
                notes = opening + [ROW, "  task0002:", "    status: pending"]
                self.assert_failed(self.run_target(notes=notes))

    def test_unclosed_value_never_lets_later_tasks_be_launched(self):
        # The lines after the opening hold no quote, so a double-quoted or
        # single-quoted value really is unclosed up to the end of the file.
        tail = [
            "  task0002:",
            "    title: plain",
            "    status: pending",
            "  task0003:",
            "    title: plain",
            "    status: pending",
        ]
        for label, opening in self.UNCLOSED_FORMS.items():
            with self.subTest(form=label):
                workflow = build_workflow(
                    [task_spec(TARGET, notes=opening)], tail_lines=tail
                )
                result = run_scenario(b"", workflow_text=workflow)
                # task0001 is the only task the hook can see: it blocks to
                # launch exactly that one.
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("launch=task0001\n", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


class TestUnclosedValuesReadDirectly(unittest.TestCase):
    """AC-6 (b): the readers, called directly on unclosed values and on bytes
    that are not valid UTF-8, return without raising and take nothing from
    the lines after the unclosed opening."""

    READERS = (
        "task_ids_from_workflow",
        "iter_task_block_lines",
        "task_routeback_records_from_workflow",
        "task_statuses_from_workflow",
    )

    def unclosed_text(self, opening):
        lines = (
            ["tasks:", "  task0001:", '    title: "task task0001"', "    status: pending"]
            + [opening, ROW, "    status: merged", "  task0002:", ROW, "    status: pending"]
        )
        return "\n".join(lines) + "\n"

    def test_unclosed_values_contribute_nothing_after_the_opening(self):
        for opening in (
            '    notes: "tried twice',
            "    notes: 'tried twice",
            "    notes: [tried twice,",
            "    notes: {a: [1,",
        ):
            with self.subTest(opening=opening):
                text = self.unclosed_text(opening)
                self.assertEqual(call_reader("task_ids_from_workflow", text), [TARGET])
                self.assertEqual(
                    call_reader("task_routeback_records_from_workflow", text), {}
                )
                self.assertEqual(
                    call_reader("task_statuses_from_workflow", text),
                    {TARGET: "pending"},
                )
                scanned = call_reader("iter_task_block_lines", text)
                self.assertEqual({task for task, _line in scanned}, {TARGET})
                self.assertEqual(scanned[-1][1], opening + "\n")

    def test_invalid_utf8_mixed_with_unclosed_quotes_and_brackets(self):
        data = (
            b'tasks:\n  task0001:\n    title: "t\xff"\n    status: pending\n'
            b'    notes: "bad \xff\xfe bytes [{\n    '
            + RECORD_KEY.encode("ascii")
            + b": 1\n  task0002:\n    notes: [unclosed \xc3(\n    "
            + RECORD_KEY.encode("ascii")
            + b": 1\n"
        )
        for reader in self.READERS:
            with self.subTest(reader=reader):
                call_reader(reader, data)  # must not raise
        self.assertEqual(call_reader("task_ids_from_workflow", data), [TARGET])
        self.assertEqual(
            call_reader("task_routeback_records_from_workflow", data), {}
        )

    def test_invalid_utf8_inside_closed_values_still_closes(self):
        data = (
            b'tasks:\n  task0001:\n    notes: "bad \xff\n    \xfe"\n  task0002:\n'
            b"    notes: [\xc3(,\n  task0099:\n]\n  task0003:\n"
        )
        self.assertEqual(
            call_reader("task_ids_from_workflow", data),
            ["task0001", "task0002", "task0003"],
        )

    def test_seeded_random_input_never_raises(self):
        rng = random.Random(20260707)
        fragments = [
            b'"', b"'", b"[", b"]", b"{", b"}", b"\\", b"#", b":", b": ", b" ",
            b"- ", b"-", b"|", b">", b"|-", b">+2", b"tasks:", b"task0001:",
            b"task0002:", b"status: pending", b"notes:", b"key: ", b"\xff",
            "\u3000".encode("utf-8"), b"\t", b"'' ", b'\\"', b"# ", b", ",
        ]
        for case in range(300):
            lines = [
                b"".join(rng.choice(fragments) for _ in range(rng.randint(0, 7)))
                for _ in range(rng.randint(1, 14))
            ]
            data = b"\n".join(lines)
            with self.subTest(case=case):
                ids = call_reader("task_ids_from_workflow", data)
                scanned = call_reader("iter_task_block_lines", data)
                records = call_reader("task_routeback_records_from_workflow", data)
                call_reader("task_statuses_from_workflow", data)
                self.assertLessEqual({task for task, _line in scanned}, set(ids))
                self.assertLessEqual(set(records), set(ids))


# --- routeback-record-quoted-continuation (task0002): value-start positions -------
#
# Review round 1 rework. Two kinds of plain-scalar text never open a quoted
# scalar or flow collection: a quote after a `:` or `?` that is not a mapping
# indicator inside a plain flow scalar, and an item indicator, quote or bracket
# at the start of a plain-scalar continuation line.

# One-line flow `notes` values whose quote follows a `:` or `?` that is part of
# a plain flow scalar (no space after it, no closed value before it).
FLOW_PLAIN_VALUES = ("[retry:'failed]", "{a:'b}", "[retry?'failed]")

# Plain-scalar `notes` followed by a continuation line that starts with an item
# indicator and an unclosed quote or bracket (a valid multi-line plain scalar).
PLAIN_CONTINUATION_NOTES = {
    "single-quoted-item": ["    notes: retry failed", "      - 'unclosed"],
    "double-quoted-item": ["    notes: retry failed", '      - "unclosed'],
    "bracketed-item": ["    notes: retry failed", "      - [unclosed"],
    "next-line-value": ["    notes:", "      retry failed", "      - 'unclosed"],
}

# Multi-line flow `notes` values whose inner single-quoted string opens after a
# real mapping indicator. The record-shaped line is inside the inner string; the
# bracket in the first line only stays uncounted while that string is open.
REAL_INDICATOR_NOTES = {
    "json-like-key-bracket-in-string": [
        "    notes: {\"a\":'tried }",
        ROW,
        "    gave up'",
        "    }",
    ],
    "json-like-key-string-spans-lines": [
        "    notes: {\"a\":'tried",
        ROW,
        "    gave up'}",
    ],
    "indicator-and-space-bracket-in-string": [
        "    notes: [a: 'tried ]",
        ROW,
        "    gave up'",
        "    ]",
    ],
    "indicator-and-space-string-spans-lines": [
        "    notes: [a: 'tried",
        ROW,
        "    gave up']",
    ],
}

# The continuation state ends at the parent indentation (forgery setup: the
# record-shaped line is inside a quoted value that really opens).
CONTINUATION_RELEASE_NOTES = {
    "plain-title-then-direct-key-quoted-notes": [
        "    title: plain title",
        '    notes: "tried twice',
        ROW,
        '    gave up"',
    ],
    "quoted-item-at-the-column-of-a-plain-item": [
        "    notes:",
        "    - retry",
        "    - 'tried",
        ROW,
        "    gave up'",
    ],
}


def plain_flow_workflow(value):
    """task0001 (pending, one-line flow `notes` `value`, direct-key record 1)
    followed by a pending task0002 block."""
    return build_workflow(
        [
            task_spec(TARGET, notes=["    notes: " + value], extra=record_lines("1")),
            task_spec("task0002"),
        ]
    )


def continuation_workflow(notes):
    """task0001 (pending, `notes` lines `notes`, direct-key record 1) followed
    by a pending task0002 block."""
    return build_workflow(
        [
            task_spec(TARGET, notes=notes, extra=record_lines("1")),
            task_spec("task0002"),
        ]
    )


class OpeningPositionHookCase(QuotedValueHookCase):
    """Hook-subprocess base: task0001's `failed` event is journal line 1,
    task0001 and task0002 are `pending`, task0002 has no journal event."""

    def assert_launches_both(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("BLOCK", result.stderr)
        launched = result.stderr.split("launch=")[1].strip().split(",")
        self.assertIn(TARGET, launched)
        self.assertIn("task0002", launched)


class TestFlowPlainScalarQuotesAreNotOpenings(OpeningPositionHookCase):
    """task0002 AC-1 (FR4, FR5, FR1; TM-2): a quote after a `:` or `?` that is
    not a mapping indicator is plain-scalar text, so the one-line flow value
    closes on its own line and the genuine record and task0002 are read."""

    def test_quote_after_a_non_indicator_colon_or_question_mark_does_not_open(self):  # AC-1
        for value in FLOW_PLAIN_VALUES:
            with self.subTest(notes=value):
                result = self.run_target(
                    notes=["    notes: " + value], extra=record_lines("1")
                )
                self.assert_launches_both(result)


class TestFlowPlainScalarQuotesAreNotOpeningsDirectly(unittest.TestCase):
    """task0002 AC-2 (FR1, FR4): the task-id and record readers, called
    directly on the AC-1 fixtures."""

    def test_task_ids_include_task0001_and_task0002(self):  # AC-2
        for value in FLOW_PLAIN_VALUES:
            with self.subTest(notes=value):
                ids = call_reader("task_ids_from_workflow", plain_flow_workflow(value))
                self.assertEqual(ids, [TARGET, "task0002"])

    def test_record_of_task0001_is_read(self):  # AC-2
        for value in FLOW_PLAIN_VALUES:
            with self.subTest(notes=value):
                records = call_reader(
                    "task_routeback_records_from_workflow", plain_flow_workflow(value)
                )
                self.assertEqual(records[TARGET], "1")


class TestRealMappingIndicatorsStillOpen(QuotedValueHookCase):
    """task0002 AC-3 (FR3, FR4; TM-1): a quote after a real mapping indicator
    (a JSON-like key with no space, or an indicator followed by a space) still
    opens an inner quoted string, so the record-shaped line inside it is body."""

    def test_inner_string_opens_after_a_real_indicator(self):  # AC-3
        for label, notes in REAL_INDICATOR_NOTES.items():
            with self.subTest(form=label):
                self.assert_failed(self.run_target(notes=notes))

    def test_question_mark_indicator_followed_by_a_space_still_opens(self):  # AC-3
        notes = ["    notes: {? 'tried }", ROW, "    gave up': x", "    }"]
        self.assert_failed(self.run_target(notes=notes))

    def test_whitespace_between_the_closed_key_and_the_colon_is_ignored(self):  # AC-3
        notes = ["    notes: {\"a\" :'tried }", ROW, "    gave up'", "    }"]
        self.assert_failed(self.run_target(notes=notes))

    def test_nested_collection_as_the_key_makes_the_colon_an_indicator(self):  # AC-3
        notes = ["    notes: {[x]:'tried }", ROW, "    gave up'", "    }"]
        self.assert_failed(self.run_target(notes=notes))

    def test_apostrophe_inside_a_plain_word_before_a_colon_is_not_a_closed_string(self):  # AC-3
        # `it's:` has an apostrophe in a plain word, not a closed inner string,
        # so the colon without a space after it is a plain character and the
        # quote after it does not open: the value closes on its first line.
        notes = ["    notes: [it's:'x]"]
        result = self.run_target(notes=notes, extra=record_lines("1"))
        self.assert_launches_target(result)


class TestPlainScalarContinuationLinesAreNotOpenings(OpeningPositionHookCase):
    """task0002 AC-4 (FR4, FR1; TM-2): a plain-scalar value followed by a
    deeper line that starts with an item indicator and an unclosed quote or
    bracket is one multi-line plain scalar; nothing opens, so the genuine
    record and task0002 are read."""

    def test_item_indicator_quote_or_bracket_on_a_continuation_line_does_not_open(self):  # AC-4
        for label, notes in PLAIN_CONTINUATION_NOTES.items():
            with self.subTest(form=label):
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_both(result)

    def test_continuation_after_a_blank_line_or_a_comment_line_is_still_a_continuation(self):  # AC-4
        # Blank lines and comment lines neither continue nor end the state.
        for filler in ("", "      # a comment", "    # a shallow comment"):
            with self.subTest(filler=filler):
                notes = ["    notes: retry failed", filler, "      - 'unclosed"]
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_both(result)

    def test_nested_key_value_continuation_does_not_open(self):  # AC-4
        extra = [
            "    context:",
            "      reason: first part",
            "        - 'unclosed",
        ] + record_lines("1")
        self.assert_launches_both(self.run_target(extra=extra))

    def test_sequence_item_content_continuation_does_not_open(self):  # AC-4
        extra = [
            "    attempts:",
            "      - first part",
            "        - 'unclosed",
        ] + record_lines("1")
        self.assert_launches_both(self.run_target(extra=extra))

    def test_key_after_an_item_indicator_continuation_does_not_open(self):  # AC-4
        extra = [
            "    attempts:",
            "      - reason: first part",
            "          - \"unclosed",
        ] + record_lines("1")
        self.assert_launches_both(self.run_target(extra=extra))

    def test_item_whose_plain_value_starts_on_the_next_line_does_not_open(self):  # AC-4
        extra = [
            "    attempts:",
            "      -",
            "        first part",
            "        - 'unclosed",
        ] + record_lines("1")
        self.assert_launches_both(self.run_target(extra=extra))

    def test_a_key_line_on_a_continuation_line_does_not_open_its_value(self):  # AC-4
        extra = [
            "    reason: first part",
            "      second: 'unclosed",
        ] + record_lines("1")
        self.assert_launches_both(self.run_target(extra=extra))


class TestContinuationStateEndsAtTheParentIndentation(QuotedValueHookCase):
    """task0002 AC-5 (FR4, FR1; TM-1): the first line at or shallower than the
    parent indentation ends the continuation state and is read with the normal
    rules, so a quoted value that really opens hides its record-shaped body."""

    def test_the_state_ends_at_the_parent_indentation(self):  # AC-5
        for label, notes in CONTINUATION_RELEASE_NOTES.items():
            with self.subTest(form=label):
                self.assert_failed(self.run_target(notes=notes))

    def test_a_shallower_line_ends_the_state_and_may_open(self):  # AC-5
        notes = [
            "    context:",
            "      reason: first part",
            "        more text",
            "      other: 'tried",
            ROW,
            "      gave up'",
        ]
        self.assert_failed(self.run_target(extra=notes))

    def test_a_comment_line_does_not_end_the_state_but_the_next_shallow_line_does(self):  # AC-5
        notes = [
            "    notes: retry failed",
            "      # a deeper comment",
            "    # a shallow comment",
            "      - 'unclosed",
            "    other: 'tried",
            ROW,
            "    gave up'",
        ]
        self.assert_failed(self.run_target(notes=notes))

    def test_a_sibling_task_key_ends_the_state(self):  # AC-5
        workflow = build_workflow(
            [
                task_spec(TARGET, notes=["    notes: retry failed"]),
                task_spec("task0002", notes=["    notes: 'tried", ROW, "    gave up'"]),
            ]
        )
        # task0002's `failed` event is journal line 1; its only record-shaped
        # line is inside a quoted value that really opens, so it is failed.
        journal = journal_bytes([event_line("failed", "task0002")])
        self.assert_failed(run_scenario(journal, workflow_text=workflow))


class TestOpeningPositionReadersNeverRaise(unittest.TestCase):
    """task0002 AC-6 (NFR2): the task-id, block-scan and record readers, called
    directly, return without raising on every fixture above and on files whose
    plain-scalar continuation lines and plain flow scalars are followed by
    unclosed quotes and brackets up to the end of the file."""

    READERS = (
        "task_ids_from_workflow",
        "iter_task_block_lines",
        "task_routeback_records_from_workflow",
    )

    def fixtures(self):
        texts = {}
        for value in FLOW_PLAIN_VALUES:
            texts["flow-plain %s" % value] = plain_flow_workflow(value)
        for table in (
            PLAIN_CONTINUATION_NOTES,
            REAL_INDICATOR_NOTES,
            CONTINUATION_RELEASE_NOTES,
        ):
            for label, notes in table.items():
                texts[label] = continuation_workflow(notes)
        return texts

    def test_every_fixture_of_the_acceptance_criteria(self):  # AC-6
        for label, text in self.fixtures().items():
            for reader in self.READERS:
                with self.subTest(fixture=label, reader=reader):
                    call_reader(reader, text)  # must not raise

    UNCLOSED_TAILS = {
        "continuation-then-unclosed-quotes-and-brackets": [
            "    notes: retry failed",
            "      - 'unclosed",
            '      - "unclosed',
            "      - [unclosed",
            "      - {unclosed",
            "    flow: [retry:'failed, {a?'b",
            "    more: [x:'",
        ],
        "next-line-plain-then-unclosed": [
            "    notes:",
            "      retry failed",
            "      - 'unclosed",
            "      - [a, {b",
        ],
        "plain-flow-scalars-then-unclosed": [
            "    a: [retry:'failed, \"unclosed",
            "    b: {k:'v, [x",
            "    c: [a?'b",
        ],
        "plain-flow-scalar-closed-then-unclosed-quote": [
            "    a: [retry:'failed]",
            "    b: 'unclosed",
        ],
    }

    def test_unclosed_quotes_and_brackets_up_to_the_end_of_the_file(self):  # AC-6
        for label, tail in self.UNCLOSED_TAILS.items():
            text = build_workflow([task_spec(TARGET, notes=tail), task_spec("task0002")])
            for reader in self.READERS:
                with self.subTest(tail=label, reader=reader):
                    call_reader(reader, text)  # must not raise

    def test_invalid_utf8_in_continuation_lines_and_plain_flow_scalars(self):  # AC-6
        data = (
            b"tasks:\n  task0001:\n    status: pending\n"
            b"    notes: retry \xff failed\n      - '\xfe unclosed\n      - [\xc3(\n"
            b"    flow: [retry:'\xff, {a?'\xfe\n"
            b"    " + RECORD_KEY.encode("ascii") + b": 1\n"
            b"  task0002:\n    notes:\n      plain \xff\n      - \"x\n"
        )
        for reader in self.READERS:
            with self.subTest(reader=reader):
                call_reader(reader, data)  # must not raise

    def test_seeded_random_input_with_continuation_fragments_never_raises(self):  # AC-6
        rng = random.Random(20261007)
        fragments = [
            b"notes:", b"notes: plain", b"key: ", b"- ", b"-", b"  ", b"    ",
            b"      ", b"'", b'"', b"[", b"]", b"{", b"}", b":", b"?", b"retry:'",
            b"a?'", b": ", b"? ", b", ", b"#", b"# ", b"|", b">", b"\xff",
            b"tasks:", b"task0001:", b"task0002:", b"status: pending", b"\\",
        ]
        for case in range(300):
            lines = [
                b"".join(rng.choice(fragments) for _ in range(rng.randint(0, 7)))
                for _ in range(rng.randint(1, 14))
            ]
            data = b"\n".join(lines)
            with self.subTest(case=case):
                ids = call_reader("task_ids_from_workflow", data)
                scanned = call_reader("iter_task_block_lines", data)
                records = call_reader("task_routeback_records_from_workflow", data)
                self.assertLessEqual({task for task, _line in scanned}, set(ids))
                self.assertLessEqual(set(records), set(ids))


# --- routeback-record-quoted-open-residual (task0001): the two remaining false opens --
#
# Two kinds of plain-scalar text never open a quoted scalar or flow collection:
# a `?` in the middle of a flow scalar (it is a mapping-key indicator only at a
# flow-entry start and only before a space, a tab or the end of the line), and a
# line made only of whitespace other than U+0020 / U+0009 (U+3000, U+00A0,
# U+000B, U+000C), which is not a blank line for the multiline value tracker.
# Observed red (base revision): the genuine direct-key record and task0002 are
# swallowed, so the hook exits 0 instead of 2.

# Flow `notes` values whose `?` follows a plain word (`_at_start` is false), so
# the quote after it opens no inner string, on the same line or on a later one.
MID_SCALAR_QUESTION_MARK_NOTES = {
    "one-line-sequence": ["    notes: [retry? 'failed]"],
    "one-line-mapping": ["    notes: {reason: retry? 'failed}"],
    "two-line-sequence": ["    notes: [retry?", "      'failed]"],
    "two-line-mapping": ["    notes: {reason: retry?", "      'failed}"],
}

# A line of 6 spaces followed only by a non-ASCII whitespace character.
NON_ASCII_BLANKS = {"U+3000": "　", "U+00A0": " "}
# The same for the vertical-tab and form-feed characters (AC-5 case 4).
CONTROL_BLANKS = {"U+000B": "\x0b", "U+000C": "\x0c"}
# The follow-up line, indented deeper than the `notes` key.
BLANK_FOLLOW_UPS = {
    "single-quoted-item": "      - 'unclosed",
    "double-quoted": '      "unclosed',
    "bracketed": "      [unclosed",
}


def blank_like_notes(blank, follow_up, blank_indent=6):
    """`notes:` with no value, then a line of `blank_indent` spaces followed
    only by `blank`, then `follow_up`."""
    return ["    notes:", " " * blank_indent + blank, follow_up]


def blank_like_fixtures(blanks):
    return {
        "%s %s" % (blank_label, follow_label): blank_like_notes(blank, follow_up)
        for blank_label, blank in blanks.items()
        for follow_label, follow_up in BLANK_FOLLOW_UPS.items()
    }


NON_ASCII_BLANK_NOTES = blank_like_fixtures(NON_ASCII_BLANKS)
CONTROL_BLANK_NOTES = blank_like_fixtures(CONTROL_BLANKS)


def entry_start_notes(opening_lines, closer):
    """A multi-line flow `notes` value whose `?` sits at a flow-entry start and
    is followed by a space, a tab or the end of the line: the quote after it
    opens an inner string that holds the closing bracket of the first lines and
    the record-shaped line, so the value only closes at the end."""
    return list(opening_lines) + [ROW, "    gave up'", "    " + closer]


# `?` at a flow-entry start (after `[`, `{` or `,`, with or without whitespace
# in between) before a space, a tab or the end of the line: still an indicator.
ENTRY_START_INDICATOR_NOTES = {
    "after-bracket": entry_start_notes(["    notes: [? 'tried ]"], "]"),
    "after-bracket-and-space": entry_start_notes(["    notes: [ ? 'tried ]"], "]"),
    "after-brace": entry_start_notes(["    notes: {? 'tried }"], "}"),
    "after-brace-and-space": entry_start_notes(["    notes: { ? 'tried }"], "}"),
    "after-comma": entry_start_notes(["    notes: [a,? 'tried ]"], "]"),
    "after-comma-and-space": entry_start_notes(["    notes: [a, ? 'tried ]"], "]"),
    "after-comma-and-tabs": entry_start_notes(["    notes: [a,\t?\t'tried ]"], "]"),
    "followed-by-a-tab": entry_start_notes(["    notes: [?\t'tried ]"], "]"),
    "at-end-of-line-after-bracket": entry_start_notes(
        ["    notes: [?", "      'tried ]"], "]"
    ),
    "at-end-of-line-after-brace": entry_start_notes(
        ["    notes: {?", "      'tried }"], "}"
    ),
    "at-end-of-line-after-comma": entry_start_notes(
        ["    notes: [a, ?", "      'tried ]"], "]"
    ),
}


class TestMidScalarQuestionMarkDoesNotOpen(OpeningPositionHookCase):
    """task0001 AC-1 (FR1; TM-1): a `?` in the middle of a flow scalar is an
    ordinary character, so the quote after it opens no inner string and the
    genuine record and task0002 are read."""

    def test_quote_after_a_mid_scalar_question_mark_does_not_open(self):  # AC-1
        for label, notes in MID_SCALAR_QUESTION_MARK_NOTES.items():
            with self.subTest(form=label):
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_both(result)


class TestNonAsciiBlankLineDoesNotOpen(OpeningPositionHookCase):
    """task0001 AC-2 (FR2; TM-2): a line made only of U+3000 or U+00A0 is not
    blank for the tracker; it is a plain scalar at the value start and the
    deeper follow-up line continues it, so nothing opens."""

    def test_follow_up_after_a_non_ascii_blank_line_does_not_open(self):  # AC-2
        for label, notes in NON_ASCII_BLANK_NOTES.items():
            with self.subTest(form=label):
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_both(result)


class TestNonAsciiBlankFixturesCarryTheRealCodePoints(unittest.TestCase):
    """The fixtures hold the actual code points, never ASCII spaces, so the
    AC-2 and AC-5 tests cannot pass vacuously."""

    def test_blank_lines_carry_the_real_code_point(self):
        for table in (NON_ASCII_BLANKS, CONTROL_BLANKS):
            for label, char in table.items():
                with self.subTest(code_point=label):
                    self.assertEqual(ord(char), int(label[2:], 16))
                    self.assertNotIn(char, " \t")
                    workflow = continuation_workflow(
                        blank_like_notes(char, BLANK_FOLLOW_UPS["double-quoted"])
                    )
                    self.assertIn(("      " + char + "\n").encode("utf-8"),
                                  workflow.encode("utf-8"))


class TestBlockScalarKeepsANonAsciiBlankLine(QuotedValueHookCase):
    """task0001 AC-3 (FR2): block-scalar non-regression. A line of 6 spaces and
    U+3000 inside a block scalar body is indented deeper than the key, so it
    stays a body line and so does the `- 'x` line after it; the direct child
    record key ends the block scalar and is read."""

    def test_the_non_ascii_line_stays_a_block_scalar_body_line(self):  # AC-3
        notes = ["    notes: |", "      body line", "      　", "      - 'x"]
        result = self.run_target(notes=notes, extra=record_lines("1"))
        self.assert_launches_target(result)


class TestQuestionMarkAndNonAsciiBlankReadersDirectly(unittest.TestCase):
    """task0001 AC-4 (FR1, FR2): the task-id and record readers, called
    directly on every AC-1 and AC-2 fixture."""

    def fixtures(self):
        tables = (MID_SCALAR_QUESTION_MARK_NOTES, NON_ASCII_BLANK_NOTES)
        return {
            label: continuation_workflow(notes)
            for table in tables
            for label, notes in table.items()
        }

    def test_task_ids_include_task0001_and_task0002(self):  # AC-4
        for label, text in self.fixtures().items():
            with self.subTest(fixture=label):
                ids = call_reader("task_ids_from_workflow", text)
                self.assertEqual(ids, [TARGET, "task0002"])

    def test_record_of_task0001_is_read(self):  # AC-4
        for label, text in self.fixtures().items():
            with self.subTest(fixture=label):
                records = call_reader("task_routeback_records_from_workflow", text)
                self.assertEqual(records[TARGET], "1")


class TestQuestionMarkIndicatorAtAnEntryStartStillOpens(QuotedValueHookCase):
    """task0001 AC-5 (1) (FR1, FR3): a `?` at a flow-entry start followed by a
    space, a tab or the end of the line is still a mapping-key indicator, so
    the quote after it opens an inner string and hides the record-shaped line
    (the bracket on the opening line stays uncounted while the string is open)."""

    def test_indicator_at_an_entry_start_still_opens(self):  # AC-5
        for label, notes in ENTRY_START_INDICATOR_NOTES.items():
            with self.subTest(form=label):
                self.assert_failed(self.run_target(notes=notes))

    def test_a_flow_sequence_entry_after_a_comma_still_opens(self):  # AC-5
        notes = ["    notes: [a, ? 'x]", ROW, "    gave up']"]
        self.assert_failed(self.run_target(notes=notes))


class TestQuestionMarkBeforeAQuoteWithoutASpaceStaysNonOpening(OpeningPositionHookCase):
    """task0001 AC-5 (2) (FR1): `[retry?'failed]` keeps its non-opening
    behavior."""

    def test_no_space_after_the_question_mark_does_not_open(self):  # AC-5
        notes = ["    notes: [retry?'failed]"]
        result = self.run_target(notes=notes, extra=record_lines("1"))
        self.assert_launches_both(result)

    def test_readers_read_the_record_and_task0002(self):  # AC-5
        text = continuation_workflow(["    notes: [retry?'failed]"])
        self.assertEqual(
            call_reader("task_ids_from_workflow", text), [TARGET, "task0002"]
        )
        records = call_reader("task_routeback_records_from_workflow", text)
        self.assertEqual(records[TARGET], "1")


class TestColumnZeroNonAsciiBlankLine(OpeningPositionHookCase):
    """task0001 AC-5 (3) (FR2): a column-0 line made only of U+3000 or only of
    U+00A0 is read as a plain scalar that decides nothing about the next line
    (it is not deeper than the key). A `"…` or `[…` follow-up line opens
    nothing; a `- '…` follow-up line still opens, as at the base revision."""

    def test_double_quote_or_bracket_follow_up_opens_nothing(self):  # AC-5
        for label, char in NON_ASCII_BLANKS.items():
            for follow_label in ("double-quoted", "bracketed"):
                with self.subTest(blank=label, follow_up=follow_label):
                    notes = ["    notes:", char, BLANK_FOLLOW_UPS[follow_label]]
                    result = self.run_target(notes=notes, extra=record_lines("1"))
                    self.assert_launches_both(result)

    def test_dash_quote_follow_up_still_opens(self):  # AC-5
        for label, char in NON_ASCII_BLANKS.items():
            with self.subTest(blank=label):
                notes = ["    notes:", char, BLANK_FOLLOW_UPS["single-quoted-item"]]
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_failed(result)

    def test_dash_quote_follow_up_hides_the_record_and_task0002(self):  # AC-5
        for label, char in NON_ASCII_BLANKS.items():
            with self.subTest(blank=label):
                text = continuation_workflow(
                    ["    notes:", char, BLANK_FOLLOW_UPS["single-quoted-item"]]
                )
                self.assertEqual(call_reader("task_ids_from_workflow", text), [TARGET])
                records = call_reader("task_routeback_records_from_workflow", text)
                self.assertNotIn(TARGET, records)


class TestOtherNonAsciiWhitespaceIsNotBlank(OpeningPositionHookCase):
    """task0001 AC-5 (4) (FR2): a line of 6 spaces followed only by U+000B or
    only by U+000C behaves like the U+3000 case: the record and task0002 are
    read."""

    def test_the_record_and_task0002_are_read_by_the_hook(self):  # AC-5
        for label, notes in CONTROL_BLANK_NOTES.items():
            with self.subTest(form=label):
                result = self.run_target(notes=notes, extra=record_lines("1"))
                self.assert_launches_both(result)

    def test_the_record_and_task0002_are_read_by_the_readers(self):  # AC-5
        for label, notes in CONTROL_BLANK_NOTES.items():
            with self.subTest(form=label):
                text = continuation_workflow(notes)
                self.assertEqual(
                    call_reader("task_ids_from_workflow", text), [TARGET, "task0002"]
                )
                records = call_reader("task_routeback_records_from_workflow", text)
                self.assertEqual(records[TARGET], "1")


class TestBlockScalarEndsAtANonAsciiBlankLineByIndentation(unittest.TestCase):
    """task0001 AC-5 (additional case) (FR2), as rewritten by
    queue-stop-guard-nonascii-blank-state (FR5): in block-scalar state a
    non-ASCII blank line neither continues nor ends the state, whatever its
    indentation. A column-0 line of U+3000 does not end the block scalar: the
    `- 'x` line after it is still a body line of the block scalar and opens
    nothing, so the `y'` line after that is yielded by the block scan too. The
    class name is kept: the sibling test below is referenced by it."""

    def test_the_block_scalar_does_not_end_at_the_column_zero_non_ascii_line(self):  # AC-5
        notes = ["    notes: |", "      body line", "　", "      - 'x", "      y'"]
        text = continuation_workflow(notes)
        lines = [line for _task, line in call_reader("iter_task_block_lines", text)]
        self.assertIn("      body line\n", lines)
        self.assertIn("      - 'x\n", lines)
        self.assertIn("      y'\n", lines)

    def test_a_deeper_non_ascii_line_stays_a_body_line(self):  # AC-5
        notes = ["    notes: |", "      body line", "      　", "      - 'x", "      y'"]
        text = continuation_workflow(notes)
        lines = [line for _task, line in call_reader("iter_task_block_lines", text)]
        self.assertIn("      - 'x\n", lines)
        self.assertIn("      y'\n", lines)


class TestQuestionMarkAndNonAsciiBlankReadersNeverRaise(unittest.TestCase):
    """task0001 AC-6 (NFR2; TM-3): the task-id, block-scan and record readers,
    called directly, return without raising on every fixture of AC-1 through
    AC-5, including values left unclosed to the end of the file."""

    READERS = (
        "task_ids_from_workflow",
        "iter_task_block_lines",
        "task_routeback_records_from_workflow",
    )

    def fixtures(self):
        texts = {}
        for table in (
            MID_SCALAR_QUESTION_MARK_NOTES,
            NON_ASCII_BLANK_NOTES,
            CONTROL_BLANK_NOTES,
            ENTRY_START_INDICATOR_NOTES,
        ):
            for label, notes in table.items():
                texts[label] = continuation_workflow(notes)
        texts["no-space-quote"] = continuation_workflow(["    notes: [retry?'failed]"])
        texts["block-scalar-non-ascii-line"] = continuation_workflow(
            ["    notes: |", "      body line", "      　", "      - 'x"]
        )
        texts["block-scalar-column-zero-line"] = continuation_workflow(
            ["    notes: |", "      body line", "　", "      - 'x", "      y'"]
        )
        for label, char in NON_ASCII_BLANKS.items():
            for follow_label, follow_up in BLANK_FOLLOW_UPS.items():
                texts["column-zero %s %s" % (label, follow_label)] = (
                    continuation_workflow(["    notes:", char, follow_up])
                )
        return texts

    def test_every_fixture_of_the_acceptance_criteria(self):  # AC-6
        for label, text in self.fixtures().items():
            for reader in self.READERS:
                with self.subTest(fixture=label, reader=reader):
                    call_reader(reader, text)  # must not raise

    UNCLOSED_TAILS = {
        "unclosed-flow-after-a-mid-scalar-question-mark": [
            "    notes: [retry? 'failed, {a?",
            "      'x, [y?",
            "      \"z",
        ],
        "unclosed-inner-string-after-an-entry-start-indicator": [
            "    notes: [a, ? 'tried ]",
            ROW,
        ],
        "unclosed-indicator-at-end-of-line": ["    notes: {?", "      'tried }"],
        "unclosed-after-a-non-ascii-blank-line": [
            "    notes:",
            "      　",
            "      - 'unclosed",
            "      - [unclosed",
        ],
        "unclosed-after-a-column-zero-non-ascii-line": [
            "    notes:",
            " ",
            "      - 'unclosed",
            "      \"unclosed",
        ],
        "unclosed-block-scalar-with-non-ascii-lines": [
            "    notes: |",
            "　",
            "      \x0b",
            "      \x0c",
            "      - \"unclosed",
        ],
    }

    def test_unclosed_values_up_to_the_end_of_the_file(self):  # AC-6
        for label, tail in self.UNCLOSED_TAILS.items():
            text = build_workflow([task_spec(TARGET, notes=tail), task_spec("task0002")])
            for reader in self.READERS:
                with self.subTest(tail=label, reader=reader):
                    call_reader(reader, text)  # must not raise

    def test_seeded_random_input_with_question_marks_and_non_ascii_blanks(self):  # AC-6
        rng = random.Random(20261008)
        fragments = [
            b"notes:", b"notes: |", b"notes: [", b"notes: {", b"- ", b"-", b"  ",
            b"    ", b"      ", b"'", b'"', b"[", b"]", b"{", b"}", b":", b"?",
            b"? ", b"?\t", b", ", b",", b"retry?", b"retry? '", b"a?'", b"#",
            "　".encode("utf-8"), " ".encode("utf-8"), b"\x0b", b"\x0c",
            b"\xff", b"tasks:", b"task0001:", b"task0002:", b"status: pending",
            b"|", b">", b"\\",
        ]
        for case in range(300):
            lines = [
                b"".join(rng.choice(fragments) for _ in range(rng.randint(0, 7)))
                for _ in range(rng.randint(1, 14))
            ]
            data = b"\n".join(lines)
            with self.subTest(case=case):
                ids = call_reader("task_ids_from_workflow", data)
                scanned = call_reader("iter_task_block_lines", data)
                records = call_reader("task_routeback_records_from_workflow", data)
                self.assertLessEqual({task for task, _line in scanned}, set(ids))
                self.assertLessEqual(set(records), set(ids))


# --- routeback-record-key-exact-match: only an exact-key line is a record key ------
#
# A direct-child line is a record key line only when its key is exactly
# `routeback_failed_journal_line`: the colon right after the name is followed by
# a space, a tab or the end of the line (the colon rule of `_find_key_colon` and
# TASK_STATUS_KEY_RE). A line whose key merely starts with
# `routeback_failed_journal_line:` is not a key line, so it never becomes the
# first occurrence and never hides the genuine record after it.
#
# "The reproduction block" below is a task0001 block, `pending`, in which a
# `routeback_failed_journal_line:x: 1` line comes before a
# `routeback_failed_journal_line: 1` line, both at the block's direct-child
# indentation (the indentation of `title:` and `status:`: 4 spaces).
# Observed red (base revision): the lookalike line is taken as the first
# occurrence and its non-canonical value yields no record, so the reader returns
# {} instead of {"task0001": "1"} and the hook exits 0 instead of 2.

RECORD_READER = "task_routeback_records_from_workflow"
LOOKALIKE_BEFORE_THE_RECORD = [
    "    %s:x: 1" % RECORD_KEY,
    "    %s: 1" % RECORD_KEY,
]


def records_read_from(extra):
    """The record reader's result on a workflow.yaml whose task0001 block carries
    `extra` lines (4-space direct-child indentation) after its status line."""
    workflow = build_workflow([task_spec(TARGET, extra=extra)])
    return call_reader(RECORD_READER, workflow)


class TestKeyLookalikeDoesNotHideTheRecord(unittest.TestCase):
    """The reader, called directly: a line whose key only starts with the record
    key never decides the task, so the exact-key line after it is read."""

    def test_reproduction_block_yields_the_record(self):  # AC-1
        self.assertEqual(
            records_read_from(LOOKALIKE_BEFORE_THE_RECORD), {TARGET: "1"}
        )

    def test_a_value_glued_to_the_colon_does_not_hide_the_record(self):  # AC-3
        extra = ["    %s:1" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertEqual(records_read_from(extra), {TARGET: "1"})

    def test_a_second_colon_after_the_name_is_not_a_key_line(self):
        extra = ["    %s::" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertEqual(records_read_from(extra), {TARGET: "1"})

    def test_a_letter_after_the_colon_is_not_a_key_line(self):
        extra = ["    %s:a" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertEqual(records_read_from(extra), {TARGET: "1"})

    def test_non_ascii_whitespace_after_the_colon_is_not_a_key_line(self):
        # U+3000 is whitespace, but only an ASCII space or tab ends the key.
        extra = ["    %s:\u3000" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertEqual(records_read_from(extra), {TARGET: "1"})

    def test_several_lookalikes_in_a_row_are_all_skipped(self):
        extra = [
            "    %s:x: 7" % RECORD_KEY,
            "    %s:2" % RECORD_KEY,
            "    %s: 3" % RECORD_KEY,
            "    %s: 4" % RECORD_KEY,
        ]
        # The first exact-key line decides: "3", never a later "4".
        self.assertEqual(records_read_from(extra), {TARGET: "3"})

    def test_lookalike_in_another_task_does_not_touch_this_tasks_record(self):
        workflow = build_workflow(
            [
                task_spec(TARGET, extra=LOOKALIKE_BEFORE_THE_RECORD),
                task_spec("task0002", extra=["    %s:x: 2" % RECORD_KEY]),
            ]
        )
        self.assertEqual(call_reader(RECORD_READER, workflow), {TARGET: "1"})


class TestExactKeyLinesKeepTheirReading(unittest.TestCase):
    """The reader, called directly: reading that does not depend on the colon
    rule is unchanged (preservation, not red)."""

    def test_a_tab_after_the_colon_is_an_exact_key_line(self):  # AC-4 (a)
        extra = ["    %s:\t1" % RECORD_KEY]
        self.assertEqual(records_read_from(extra), {TARGET: "1"})

    def test_an_empty_value_line_is_the_first_occurrence(self):  # AC-4 (b)
        extra = ["    %s:" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertNotIn(TARGET, records_read_from(extra))

    def test_a_lone_lookalike_line_is_no_record(self):  # AC-4 (c)
        extra = ["    %s:x: 1" % RECORD_KEY]
        self.assertNotIn(TARGET, records_read_from(extra))

    def test_a_lone_value_glued_to_the_colon_is_no_record(self):
        extra = ["    %s:1" % RECORD_KEY]
        self.assertNotIn(TARGET, records_read_from(extra))

    def test_a_first_exact_key_line_with_a_bad_value_still_decides(self):
        extra = ["    %s: x" % RECORD_KEY, "    %s: 1" % RECORD_KEY]
        self.assertNotIn(TARGET, records_read_from(extra))

    def test_a_lookalike_deeper_than_the_direct_keys_is_still_never_read(self):
        # Indentation rule unchanged: a deeper exact-key line is not a direct key.
        extra = ["    context:", "      %s: 1" % RECORD_KEY]
        self.assertNotIn(TARGET, records_read_from(extra))


class TestKeyLookalikeHookScenario(QuotedValueHookCase):
    """The hook as a subprocess: the journal's `failed` event of task0001 sits
    on physical line 1 and task0001 is `pending`."""

    def test_reproduction_block_is_unlaunched(self):  # AC-2
        result = self.run_target(extra=LOOKALIKE_BEFORE_THE_RECORD)
        self.assert_launches_target(result)

    def test_a_lone_lookalike_line_is_failed(self):
        result = self.run_target(extra=["    %s:x: 1" % RECORD_KEY])
        self.assert_failed(result)


# --- routeback-record-quoted-continuation: AC-7 (docstrings and comments) --------

BODY_STATEMENT = (
    "body lines of multi-line quoted-scalar and flow-collection values are "
    "never read as a task boundary, task id, status or record"
)
BODY_STATEMENT_FUNCTIONS = (
    "iter_task_block_lines",
    "task_ids_from_workflow",
    "task_routeback_records_from_workflow",
)


def live_function_docstring(name):
    with open(HOOK_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_docstring(node, clean=False)
    raise AssertionError("%s not found" % name)


class TestBodyLineStatements(unittest.TestCase):
    """AC-7 (a): each of the five locations states that body lines of
    quoted-scalar and flow-collection values are not read as a task boundary,
    task id, status or record."""

    def assert_states_it(self, text):
        text = normalize_whitespace(text or "").lower()
        self.assertTrue(text, "expected a non-empty docstring or comment")
        self.assertIn(BODY_STATEMENT, text)

    def test_module_docstring_states_it(self):
        self.assert_states_it(live_docstring())

    def test_function_docstrings_state_it(self):
        for name in BODY_STATEMENT_FUNCTIONS:
            with self.subTest(function=name):
                self.assert_states_it(live_function_docstring(name))

    def test_record_key_comment_states_it(self):
        self.assert_states_it(live_record_regex_comment())

    def test_statement_is_absent_from_the_pre_change_docstring(self):
        # Negative proof: the same matcher does not fire on the base sample.
        self.assertNotIn(
            BODY_STATEMENT, normalize_whitespace(PRE_CHANGE_DOCSTRING).lower()
        )


class TestHookImportsStdlibOnly(unittest.TestCase):
    """AC-7 (c): the hook imports only the standard library."""

    def test_only_stdlib_imports(self):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=HOOK_PATH)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported)
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        for name in imported:
            if stdlib_names is not None:
                self.assertIn(name, stdlib_names, "%s is not a stdlib module" % name)


# --- queue-stop-guard-nonascii-blank-state (task0001): state kept across non-ASCII blank lines ---
#
# In the block-scalar state and in the plain-scalar continuation state, a line
# made only of non-ASCII whitespace (U+3000, U+00A0, U+000B, U+000C) neither
# continues nor ends the state, whatever its indentation (column 0, the parent's
# indentation or deeper); the next line that is not such a line is judged
# against the unchanged state, as if the line were absent. Such a line is a
# "non-ASCII blank line": empty after `str.strip()`, yet not made only of
# U+0020 spaces and U+0009 tabs.
#
# Observed red (base revision): the line ends the state, the `- 'x` line after
# it opens a single-quoted value, and the genuine record and task0002 are
# swallowed (the hook exits 0 instead of 2, the readers return {} and
# ['task0001']).
#
# The hook reads workflow.yaml with `readlines()` in text mode, which splits
# lines at LF, CR and CRLF only: a line of U+000B or U+000C stays one physical
# line of its own and does not reduce to an empty line.

U3000 = "　"
U00A0 = " "
U000B = "\x0b"
U000C = "\x0c"


def is_non_ascii_blank_line(line):
    """The tracker's non-ASCII blank class, spelled out for the fixtures."""
    return line.strip() == "" and line.strip(" \t") != ""


def reported_form_notes(form, char):
    """`notes` lines of the three reported forms; `char` is the whitespace
    character that makes up the blank line."""
    if form == "block-scalar-column-zero":
        return ["    notes: |", "      body line", char, "      - 'x"]
    if form == "block-scalar-parent-indent":
        return ["    notes: |", "      body line", "    " + char, "      - 'x"]
    if form == "plain-continuation":
        return ["    notes: hello", char, "      - 'x"]
    raise ValueError(form)


REPORTED_FORMS = (
    "block-scalar-column-zero",
    "block-scalar-parent-indent",
    "plain-continuation",
)
# The three reported forms x {U+3000, U+00A0}: six fixtures.
REPORTED_FORM_NOTES = {
    "%s %s" % (form, code_point): reported_form_notes(form, char)
    for form in REPORTED_FORMS
    for code_point, char in (("U+3000", U3000), ("U+00A0", U00A0))
}

# Edge cases: every one keeps the genuine record and task0002 readable. A
# `- 'x` line after the blank line is a body line of the block scalar (deeper
# than its parent) or a continuation line of the plain scalar (deeper than the
# key's or the item indicator's column), so it opens nothing.
EDGE_CASE_NOTES = {
    "U+000B column zero in a block scalar": [
        "    notes: |", "      body line", U000B, "      - 'x",
    ],
    "U+000C column zero in a block scalar": [
        "    notes: |", "      body line", U000C, "      - 'x",
    ],
    "U+000B column zero in a plain continuation": [
        "    notes: hello", U000B, "      - 'x",
    ],
    "U+000C column zero in a plain continuation": [
        "    notes: hello", U000C, "      - 'x",
    ],
    "U+3000 at column 2 in a block scalar": [
        "    notes: |", "      body line", "  " + U3000, "      - 'x",
    ],
    "U+00A0 at column 2 in a plain continuation": [
        "    notes: hello", "  " + U00A0, "      - 'x",
    ],
    "item content plain scalar": [
        "    notes:", "      - hello", U3000, "        - 'x",
    ],
    "plain scalar on the line after the key": [
        "    notes:", "      retry failed", U3000, "      - 'x",
    ],
    "block scalar header >": [
        "    notes: >", "      body line", U3000, "      - 'x",
    ],
    "block scalar header |-": [
        "    notes: |-", "      body line", U3000, "      - 'x",
    ],
    "block scalar header item - |": [
        "    notes:", "      - |", "        body line", U3000, "        - 'x",
    ],
    "two consecutive blank lines in a block scalar": [
        "    notes: |", "      body line", U3000, U00A0, "      - 'x",
    ],
    "three consecutive blank lines at mixed columns in a block scalar": [
        "    notes: |", "      body line", U3000, "  " + U00A0, "    " + U000B,
        "      - 'x",
    ],
    "two consecutive blank lines in a plain continuation": [
        "    notes: hello", U3000, U00A0, "      - 'x",
    ],
    "three consecutive blank lines at mixed columns in a plain continuation": [
        "    notes: hello", "    " + U000C, U3000, "  " + U00A0, "      - 'x",
    ],
}


def non_blank_lines(notes):
    return [line for line in notes if not is_non_ascii_blank_line(line)]


def read_all(text):
    """The three readers' results on `text`, as comparable values."""
    return (
        call_reader("task_ids_from_workflow", text),
        call_reader("iter_task_block_lines", text),
        call_reader("task_routeback_records_from_workflow", text),
    )


class TestStateFixturesCarryNonAsciiBlankLines(unittest.TestCase):
    """Every fixture holds a real non-ASCII blank line (never a space or tab
    line), so the tests below cannot pass vacuously."""

    def test_each_fixture_holds_a_non_ascii_blank_line(self):
        for table in (REPORTED_FORM_NOTES, EDGE_CASE_NOTES):
            for label, notes in table.items():
                with self.subTest(fixture=label):
                    self.assertTrue(any(is_non_ascii_blank_line(l) for l in notes))

    def test_the_six_reported_fixtures_are_distinct(self):
        self.assertEqual(len(REPORTED_FORM_NOTES), 6)
        distinct = {tuple(notes) for notes in REPORTED_FORM_NOTES.values()}
        self.assertEqual(len(distinct), 6)


class TestNonAsciiBlankLineKeepsTheStateHook(OpeningPositionHookCase):
    """task0001 AC-1 (FR1, FR2; TM-1): the hook, run as a subprocess with
    Stop-hook JSON on stdin, blocks (BLOCK, exit 2) and launches task0001 and
    task0002 on each of the six reported fixtures."""

    def test_the_hook_blocks_and_launches_task0001_and_task0002(self):  # AC-1
        for label, notes in REPORTED_FORM_NOTES.items():
            with self.subTest(fixture=label):
                result = run_scenario(
                    self.journal, workflow_text=continuation_workflow(notes)
                )
                self.assert_launches_both(result)


class TestNonAsciiBlankLineKeepsTheStateReaders(unittest.TestCase):
    """task0001 AC-2 (FR1, FR2; TM-1) and AC-3 (FR1, FR2, FR3; TM-1): the
    readers, called directly on the module loaded from its file path, return
    `[task0001, task0002]` and map task0001 to "1" on every reported fixture
    and every edge case."""

    def assert_record_and_task0002_are_read(self, notes):
        text = continuation_workflow(notes)
        self.assertEqual(
            call_reader("task_ids_from_workflow", text), [TARGET, "task0002"]
        )
        records = call_reader("task_routeback_records_from_workflow", text)
        self.assertEqual(records.get(TARGET), "1")

    def test_the_reported_forms_read_the_record_and_task0002(self):  # AC-2
        for label, notes in REPORTED_FORM_NOTES.items():
            with self.subTest(fixture=label):
                self.assert_record_and_task0002_are_read(notes)

    def test_the_edge_cases_read_the_record_and_task0002(self):  # AC-3
        for label, notes in EDGE_CASE_NOTES.items():
            with self.subTest(fixture=label):
                self.assert_record_and_task0002_are_read(notes)

    def test_the_state_is_judged_as_if_the_blank_lines_were_absent(self):  # AC-2, AC-3
        # The postcondition of the rule: with the non-ASCII blank lines
        # removed the readers return exactly the same results.
        for table in (REPORTED_FORM_NOTES, EDGE_CASE_NOTES):
            for label, notes in table.items():
                with self.subTest(fixture=label):
                    with_blanks = read_all(continuation_workflow(notes))
                    without = read_all(continuation_workflow(non_blank_lines(notes)))
                    self.assertEqual(with_blanks, without)


class TestNonAsciiWhitespaceWithTextStillEndsTheState(OpeningPositionHookCase):
    """task0001 AC-3 (FR3): a line of non-ASCII whitespace followed by a
    non-whitespace character is not a non-ASCII blank line; it is judged by
    its indentation and still ends the state, so the `- 'x` line after it
    opens a quoted value that hides the record (unchanged behavior)."""

    def test_whitespace_followed_by_text_is_judged_by_indentation(self):  # AC-3
        forms = {
            "block-scalar": [
                "    notes: |", "      body line", U3000 + "x", "      - 'x",
            ],
            "plain-continuation": ["    notes: hello", U3000 + "x", "      - 'x"],
        }
        for label, notes in forms.items():
            with self.subTest(fixture=label):
                result = run_scenario(
                    self.journal, workflow_text=continuation_workflow(notes)
                )
                self.assert_failed(result)


class TestNonAsciiBlankLineStateReadersNeverRaise(unittest.TestCase):
    """task0001 AC-4 (NFR2; TM-2): the task-id, block-scan and record readers
    return without raising on every reported fixture, every edge case, and on
    block-scalar, plain-continuation and single-quoted values that stay
    unclosed to the end of the file and contain non-ASCII blank lines."""

    READERS = (
        "task_ids_from_workflow",
        "iter_task_block_lines",
        "task_routeback_records_from_workflow",
    )

    UNCLOSED_TAILS = {
        "block-scalar-to-end-of-file": [
            "  task0003:", "    notes: |", "      body line", U3000, "      more",
            "  " + U00A0,
        ],
        "plain-continuation-to-end-of-file": [
            "  task0003:", "    notes: hello", U3000, "      more text", U00A0,
        ],
        "single-quoted-item-to-end-of-file": [
            "  task0003:", "    notes:", "      - 'unclosed", U3000, "      more",
            "  " + U00A0,
        ],
        "non-ascii-blank-line-as-the-last-line": [
            "  task0003:", "    notes: |", "      body line", U3000,
        ],
    }

    def test_every_reported_fixture_and_edge_case(self):  # AC-4
        for table in (REPORTED_FORM_NOTES, EDGE_CASE_NOTES):
            for label, notes in table.items():
                text = continuation_workflow(notes)
                for reader in self.READERS:
                    with self.subTest(fixture=label, reader=reader):
                        call_reader(reader, text)  # must not raise

    def test_values_left_unclosed_to_the_end_of_the_file(self):  # AC-4
        for label, tail in self.UNCLOSED_TAILS.items():
            text = build_workflow(
                [task_spec(TARGET, extra=record_lines("1")), task_spec("task0002")],
                tail_lines=tail,
            )
            for reader in self.READERS:
                with self.subTest(tail=label, reader=reader):
                    call_reader(reader, text)  # must not raise


# AC-5 (FR5) is the rewritten test in
# TestBlockScalarEndsAtANonAsciiBlankLineByIndentation above.


def live_class_docstring(name):
    with open(HOOK_PATH, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return ast.get_docstring(node, clean=False)
    raise AssertionError("%s not found" % name)


class TestTrackerClassDocstring(unittest.TestCase):
    """task0001 AC-6 (FR4): the tracker's class docstring no longer says that a
    non-ASCII blank line is read "by its indentation inside a block scalar".
    The positive statement (such a line neither continues nor ends the
    block-scalar and plain-continuation states) is checked by reading the
    docstring: the SPEC fixes its meaning, not its wording."""

    REMOVED_PHRASE = "or by its indentation inside a block scalar"

    def test_the_removed_phrase_is_absent(self):  # AC-6
        text = normalize_whitespace(live_class_docstring("_MultilineValueTracker"))
        self.assertTrue(text)
        self.assertNotIn(self.REMOVED_PHRASE, text)

    def test_the_class_docstring_mentions_the_non_ascii_blank_line_rule(self):  # AC-6
        text = normalize_whitespace(live_class_docstring("_MultilineValueTracker"))
        self.assertIn("neither continues nor ends", text)
        self.assertIn("non-ASCII blank line", text)


# --- AC-7: module discipline -------------------------------------------------


class TestModuleImportsStdlibOnly(unittest.TestCase):
    """AC-7: this module imports only the standard library, so it also
    imports no other test module. Provenance: the AST-walk approach mirrors
    tests/test_queue_hook_status_read_pin.py's TestModuleImportsStdlibOnly,
    reproduced locally rather than imported."""

    def test_only_stdlib_imports(self):
        this_module_path = os.path.abspath(__file__)
        with open(this_module_path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=this_module_path)

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported_names.add(node.module.split(".")[0])

        self.assertTrue(imported_names, "expected at least one import")
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        for name in imported_names:
            if stdlib_names is not None:
                self.assertIn(name, stdlib_names, "%s is not a stdlib module" % name)


if __name__ == "__main__":
    unittest.main()
