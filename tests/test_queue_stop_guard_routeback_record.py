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
"""

import ast
import importlib.util
import json
import os
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
