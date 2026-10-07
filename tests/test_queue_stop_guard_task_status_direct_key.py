"""Tests for the direct-child status read in
em-workflow/hooks/queue_stop_guard.py (task-status-direct-key, task0001).

`task_statuses_from_workflow` takes each task's status only from a `status:`
key at the task block's direct-child indentation (the indentation of the
first line in the block that is neither blank nor a comment). Lines inside
block-scalar bodies (the untrusted `notes` text) and inside nested mappings
are never status candidates, whether the direct `status:` key comes before
them, after them, or not at all.

Observed red (base revision, every `status:` line in the block is a
candidate): the AC-1 `|` case, AC-2 and AC-3 fail on the base hook. AC-1 and
AC-3 read the body / nested `status: pending` as the task's status, so the
hook exits 2 (BLOCK) instead of 0 and the reader returns `pending` instead of
omitting the task; AC-2 returns `pending` (the body line) instead of
`failed` (the direct key placed after the body).

Per test/README.md the hook runs as a subprocess with Claude Code Stop-hook
JSON on stdin and fixtures are built in throwaway temporary directories. The
status reader is also called directly: the hook source is compiled and
executed into a private namespace (module-level execution is guarded by
`if __name__ == "__main__":`), so no bytecode is written next to the hook.
No other test module is imported: the fixture helpers below are rebuilt
locally (layout provenance: tests/test_queue_stop_guard_routeback_record.py).
"""

import json
import os
import subprocess
import sys
import tempfile
import types
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_stop_guard.py")

FEATURE = "status-direct-key-feature"
RECORD_KEY = "routeback_failed_journal_line"
TARGET = "task0001"
DEFAULT_STDIN = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})

# Every block-scalar header form the reader must see through (FR2).
HEADER_FORMS = ("|", ">", "|-", "|+", "|2")


# --- hook access ---------------------------------------------------------------


def load_hook_namespace():
    with open(HOOK_PATH, encoding="utf-8") as fh:
        source = fh.read()
    module = types.ModuleType("queue_stop_guard_direct_key_probe")
    module.__file__ = HOOK_PATH
    exec(compile(source, HOOK_PATH, "exec"), module.__dict__)
    return module


HOOK = load_hook_namespace()


def statuses_of(workflow_text):
    """Calls the hook's `task_statuses_from_workflow` on `workflow_text`
    (str or bytes) written to a throwaway file."""
    data = workflow_text if isinstance(workflow_text, bytes) else workflow_text.encode()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "workflow.yaml")
        with open(path, "wb") as fh:
            fh.write(data)
        return HOOK.task_statuses_from_workflow(path)


# --- fixture builders ------------------------------------------------------------


def event_line(event, task):
    record = {"event": event, "task": task, "at": "2026-10-07T15:30:00+09:00"}
    return json.dumps(record).encode("utf-8")


FAILED_ON_LINE_1 = (event_line("failed", TARGET) + b"\n")


def workflow_text(block_lines, final_newline=True, extra_tasks=()):
    """A workflow.yaml whose `implement` step is in progress and whose
    `tasks:` mapping holds task0001 with `block_lines` (each already carrying
    its own indentation) as its own block, then `extra_tasks` (lists of full
    lines, key line included)."""
    lines = [
        "schema_version: 1",
        "feature: %s" % FEATURE,
        "",
        "workflow:",
        "  - id: create-spec",
        "    status: completed",
        "  - id: implement",
        "    status: in_progress",
        "  - id: review",
        "    status: pending",
        "",
        "tasks:",
        "  %s:" % TARGET,
    ]
    lines.extend(block_lines)
    for task in extra_tasks:
        lines.extend(task)
    text = "\n".join(lines)
    return text + "\n" if final_newline else text


def notes_block(header="|", body=("status: pending", "more text")):
    """A `notes` block scalar at the direct-child indentation (4) whose body
    lines are indented deeper (6)."""
    return ["    notes: %s" % header] + ["      %s" % line for line in body]


RECORD_LINE = "    %s: 1" % RECORD_KEY
TITLE_LINE = '    title: "task %s"' % TARGET


class Layout:
    """Throwaway integration-worktree layout under a temp directory."""

    def __init__(self, tmp):
        self.journal_dir = os.path.join(
            tmp, ".claude", "worktrees", "em-workflow", FEATURE
        )
        self.docs_dir = os.path.join(
            self.journal_dir, "integration", "feature-docs", FEATURE
        )
        os.makedirs(self.docs_dir)
        self.workflow_path = os.path.join(self.docs_dir, "workflow.yaml")
        self.journal_path = os.path.join(self.journal_dir, "journal.jsonl")


def run_hook(text, journal=FAILED_ON_LINE_1):
    """Runs the Stop hook as a subprocess against `text` (workflow.yaml) and
    `journal` (bytes) and returns the completed process."""
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        layout = Layout(tmp)
        with open(layout.workflow_path, "wb") as fh:
            fh.write(data)
        with open(layout.journal_path, "wb") as fh:
            fh.write(journal)
        return subprocess.run(
            [sys.executable, HOOK_PATH],
            cwd=tmp,
            input=DEFAULT_STDIN,
            capture_output=True,
            text=True,
            timeout=15,
        )


class HookAssertions(unittest.TestCase):
    def assert_not_blocked(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BLOCK", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def assert_blocks_naming_target(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("launch=%s" % TARGET, result.stderr)


# --- AC-1: block-scalar body is never a status candidate -------------------------


class TestBlockScalarBodyIsNotAStatus(HookAssertions):
    """AC-1 (FR1, FR2, TM-1): no direct-child `status:` key; the notes body
    holds `status: pending` deeper than the direct keys; the journal's line 1
    is the task's `failed` event and the record names line 1."""

    def block(self, header):
        return [TITLE_LINE, RECORD_LINE] + notes_block(header)

    def test_hook_does_not_block_for_every_header_form(self):  # AC-1
        for header in HEADER_FORMS:
            with self.subTest(header=header):
                result = run_hook(workflow_text(self.block(header)))
                self.assert_not_blocked(result)

    def test_reader_omits_the_task_for_every_header_form(self):  # AC-1
        for header in HEADER_FORMS:
            with self.subTest(header=header):
                statuses = statuses_of(workflow_text(self.block(header)))
                self.assertNotIn(TARGET, statuses)

    def test_pipe_form_hook_does_not_block(self):  # AC-1 / AC-7 (`|` form)
        result = run_hook(workflow_text(self.block("|")))
        self.assert_not_blocked(result)

    def test_pipe_form_reader_omits_the_task(self):  # AC-1 / AC-7 (`|` form)
        statuses = statuses_of(workflow_text(self.block("|")))
        self.assertEqual(statuses, {})


# --- AC-2: a direct key after the body decides ---------------------------------------


class TestDirectStatusAfterBlockScalar(HookAssertions):
    """AC-2 (FR1, FR2): the AC-1 fixture (`|` form) plus a direct-child
    `status: failed` after the notes block scalar."""

    BLOCK = [TITLE_LINE, RECORD_LINE] + notes_block("|") + ["    status: failed"]

    def test_hook_does_not_block(self):  # AC-2
        self.assert_not_blocked(run_hook(workflow_text(self.BLOCK)))

    def test_reader_returns_the_direct_value_not_the_body_value(self):  # AC-2
        statuses = statuses_of(workflow_text(self.BLOCK))
        self.assertEqual(statuses.get(TARGET), "failed")

    def test_direct_value_wins_for_every_header_form(self):  # AC-2 (FR2)
        for header in HEADER_FORMS:
            with self.subTest(header=header):
                block = [TITLE_LINE, RECORD_LINE] + notes_block(header)
                block.append("    status: failed")
                self.assertEqual(
                    statuses_of(workflow_text(block)).get(TARGET), "failed"
                )


# --- AC-3: nested mapping lines are never a status -------------------------------------


class TestNestedMappingIsNotAStatus(HookAssertions):
    """AC-3 (FR3): a child line of a nested mapping carries `status: pending`
    and the block has no direct-child `status:` key."""

    BLOCK = [
        TITLE_LINE,
        RECORD_LINE,
        "    meta:",
        "      status: pending",
    ]

    def test_reader_omits_the_task(self):  # AC-3
        self.assertEqual(statuses_of(workflow_text(self.BLOCK)), {})

    def test_hook_does_not_block(self):  # AC-3
        self.assert_not_blocked(run_hook(workflow_text(self.BLOCK)))

    def test_nested_status_after_a_direct_status_does_not_replace_it(self):  # AC-3
        block = [
            TITLE_LINE,
            "    status: failed",
            "    meta:",
            "      status: pending",
        ]
        self.assertEqual(statuses_of(workflow_text(block)).get(TARGET), "failed")

    def test_nested_status_before_a_direct_status_is_skipped(self):  # AC-3
        block = [
            TITLE_LINE,
            "    meta:",
            "      status: failed",
            "    status: pending",
        ]
        self.assertEqual(statuses_of(workflow_text(block)).get(TARGET), "pending")


# --- AC-4: a direct pending still blocks; comments never shift the indent --------------


class TestDirectPendingStillBlocks(HookAssertions):
    """AC-4 (FR1, FR4, TM-1): the notes body contains `status: failed`; a
    direct-child `status: pending` before or after the notes block scalar
    keeps the exclusion applying, so the hook blocks and names the task."""

    BODY = ("status: failed", "more text")

    def block_pending_before(self):
        return (
            [TITLE_LINE, RECORD_LINE, "    status: pending"]
            + notes_block("|", self.BODY)
        )

    def block_pending_after(self):
        return (
            [TITLE_LINE, RECORD_LINE]
            + notes_block("|", self.BODY)
            + ["    status: pending"]
        )

    def test_pending_before_notes_blocks_and_names_the_task(self):  # AC-4
        result = run_hook(workflow_text(self.block_pending_before()))
        self.assert_blocks_naming_target(result)

    def test_pending_after_notes_blocks_and_names_the_task(self):  # AC-4
        result = run_hook(workflow_text(self.block_pending_after()))
        self.assert_blocks_naming_target(result)

    def test_reader_returns_pending_before_and_after_notes(self):  # AC-4
        for label, block in (
            ("before", self.block_pending_before()),
            ("after", self.block_pending_after()),
        ):
            with self.subTest(position=label):
                statuses = statuses_of(workflow_text(block))
                self.assertEqual(statuses.get(TARGET), "pending")

    def test_comment_before_first_key_does_not_shift_the_direct_indent(self):  # AC-4
        # Comment indentations differ from the direct keys' (4) but stay
        # deeper than the task key (2), so they remain inside the block.
        for comment_indent in (3, 6, 8):
            with self.subTest(comment_indent=comment_indent):
                comment = " " * comment_indent + "# leading comment"
                block = [comment] + self.block_pending_after()
                self.assertEqual(
                    statuses_of(workflow_text(block)).get(TARGET), "pending"
                )

    def test_comment_before_first_key_hook_still_blocks(self):  # AC-4
        comment = " " * 8 + "# leading comment"
        result = run_hook(workflow_text([comment] + self.block_pending_after()))
        self.assert_blocks_naming_target(result)

    def test_comment_line_inside_the_block_is_never_the_status(self):  # AC-4
        block = [
            TITLE_LINE,
            "    # status: failed",
            "    status: pending",
        ]
        self.assertEqual(statuses_of(workflow_text(block)).get(TARGET), "pending")


# --- AC-5: crafted content never raises -------------------------------------------------


class TestCraftedContentFailsOpen(HookAssertions):
    """AC-5 (NFR2, TM-2): no direct-child `status:` key; the reader returns
    without raising and omits the task, and the hook exits 0 with no
    traceback."""

    CASES = (
        (
            "only-blank-and-comment-lines",
            ["      # only a comment", "", "    # another comment", "   "],
            True,
        ),
        (
            "first-key-is-a-notes-block-scalar-header",
            notes_block("|") + [RECORD_LINE],
            True,
        ),
        (
            "header-with-unexpected-trailing-characters",
            [TITLE_LINE, "    notes: |garbage status: pending", RECORD_LINE]
            + ["      status: pending"],
            True,
        ),
        (
            "header-with-trailing-characters-after-indicators",
            [TITLE_LINE, "    notes: >2-x!", RECORD_LINE, "      status: pending"],
            True,
        ),
        (
            "body-reaches-end-of-file-without-final-newline",
            [TITLE_LINE, RECORD_LINE, "    notes: |", "      status: pending"],
            False,
        ),
    )

    def test_reader_returns_without_raising_and_omits_the_task(self):  # AC-5
        for label, block, final_newline in self.CASES:
            with self.subTest(case=label):
                text = workflow_text(block, final_newline=final_newline)
                self.assertEqual(statuses_of(text), {})

    def test_hook_exits_zero_without_a_traceback(self):  # AC-5
        for label, block, final_newline in self.CASES:
            with self.subTest(case=label):
                text = workflow_text(block, final_newline=final_newline)
                self.assert_not_blocked(run_hook(text))

    def test_block_with_no_lines_at_all_is_omitted(self):  # AC-5
        self.assertEqual(statuses_of(workflow_text([])), {})

    def test_crafted_bytes_do_not_raise(self):  # AC-5
        text = workflow_text([TITLE_LINE, "    notes: |", "      status: pending"])
        for suffix in (b"\xff\xfe", b"\x00", b"\r", b"\t"):
            with self.subTest(suffix=suffix):
                data = text.encode("utf-8") + suffix
                self.assertEqual(statuses_of(data), {})
                self.assert_not_blocked(run_hook(data))


# --- FR4: classification details kept ----------------------------------------------------


class TestStatusClassificationDetails(unittest.TestCase):
    """FR4 / A5: the first direct-child status key decides; a direct status
    whose value cannot be extracted leaves the task out; tasks are read
    independently of each other."""

    def test_first_direct_status_key_wins(self):
        block = [TITLE_LINE, "    status: failed", "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)).get(TARGET), "failed")

    def test_unextractable_first_direct_value_omits_the_task(self):
        for label, line in (
            ("bare-colon", "    status:"),
            ("two-tokens", "    status: pending # trailing"),
        ):
            with self.subTest(case=label):
                block = [TITLE_LINE, line, "    status: pending"]
                self.assertEqual(statuses_of(workflow_text(block)), {})

    def test_other_tasks_are_read_from_their_own_blocks(self):
        second = [
            "  task0002:",
            "      title: deeper-first-key",
            "      status: merged",
            "      notes: |",
            "        status: pending",
        ]
        third = ["  task0003:", "    status: in_progress"]
        block = [TITLE_LINE] + notes_block("|", ("status: failed",))
        block.append("    status: pending")
        statuses = statuses_of(workflow_text(block, extra_tasks=(second, third)))
        self.assertEqual(
            statuses,
            {TARGET: "pending", "task0002": "merged", "task0003": "in_progress"},
        )


# --- AC-6 guards: contract identifiers keep their names ----------------------------------


class TestContractIdentifiers(unittest.TestCase):
    """AC-6 (NFR3): the three identifiers keep their names."""

    def test_identifiers_exist(self):
        for name in ("task_statuses_from_workflow", "TASK_STATUS_RE", "TASKS_SECTION_RE"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(HOOK, name))


if __name__ == "__main__":
    unittest.main()
