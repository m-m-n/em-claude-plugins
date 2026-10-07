"""Tests for the exact status key match in the direct-child status read of
em-workflow/hooks/queue_stop_guard.py (task-status-key-exact-match, task0001).

`task_statuses_from_workflow` decides a task's status from the first
direct-child line of its block that is a status key line: after its leading
whitespace the line begins with `status:` and that colon is immediately
followed by a space, a tab or the end of the line (the colon rule of the
hook's `_find_key_colon`). A direct-child line whose key merely starts with
`status:` (`status:detail: ignored`, `status:detail:`, `status:pending`,
`status:failed`) is not a status key line: it is skipped and the scan goes on
with the next line of the same block. Everything else about the read is
unchanged: the first status key line decides, a value-less `status:` decides
and leaves the task out, and block-scalar bodies, nested mappings and comment
lines are never read.

Observed red (base revision hook, where any direct-child line starting with
`status:` was the deciding line): the AC-1 `status:detail: ignored` case, the
AC-2 `status:pending` case and the AC-2 `status:failed` then `status: pending`
case fail on the base hook.

    AC-1 `status:detail: ignored` then `status: pending`:
        AssertionError: {} != {'task0001': 'pending'}
        (the `status:detail: ignored` line decided and its value could not be
        extracted, so the task was left out)
    AC-1 `status:detail:` then `status: failed`:
        AssertionError: {'task0001': 'detail:'} != {'task0001': 'failed'}
    AC-2 `status:pending` as the only status-like line:
        AssertionError: {'task0001': 'pending'} != {}
    AC-2 `status:failed` then `status: pending`:
        AssertionError: {'task0001': 'failed'} != {'task0001': 'pending'}
    AC-5 hook run on the AC-1 block plus the route-back record:
        AssertionError: 0 != 2 (the task was left out, so the hook did not
        block)

The AC-6 cases that place a direct `status: pending` after the skipped line
(a body `status: failed` before it, a comment line before it) fail on the base
hook for the same reason as AC-1 (`{}` instead of `{'task0001': 'pending'}`).

The tab case (AC-3), the value-less `status:` cases (AC-4) and the AC-6 cases
that have no direct status key line (block-scalar body, nested mapping, glued
`status:pending` inside a body, skipped first line setting the direct indent)
pass on the base hook by design: they are regression guards for the behavior
the fix keeps.

Per test/README.md the hook runs as a subprocess with Claude Code Stop-hook
JSON on stdin and fixtures are built in throwaway temporary directories. The
status reader is also called directly: the hook source is compiled and
executed into a private namespace (module-level execution is guarded by
`if __name__ == "__main__":`), so no bytecode is written next to the hook.
No other test module is imported: the fixture helpers below are rebuilt
locally (layout provenance:
tests/test_queue_stop_guard_task_status_direct_key.py).
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

FEATURE = "status-key-exact-match-feature"
RECORD_KEY = "routeback_failed_journal_line"
TARGET = "task0001"
DEFAULT_STDIN = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False})


# --- hook access ---------------------------------------------------------------


def load_hook_namespace():
    with open(HOOK_PATH, encoding="utf-8") as fh:
        source = fh.read()
    module = types.ModuleType("queue_stop_guard_key_exact_match_probe")
    module.__file__ = HOOK_PATH
    exec(compile(source, HOOK_PATH, "exec"), module.__dict__)
    return module


HOOK = load_hook_namespace()


def statuses_of(workflow_text_value):
    """Calls the hook's `task_statuses_from_workflow` on the given workflow
    text (str or bytes) written to a throwaway file."""
    data = (
        workflow_text_value
        if isinstance(workflow_text_value, bytes)
        else workflow_text_value.encode()
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "workflow.yaml")
        with open(path, "wb") as fh:
            fh.write(data)
        return HOOK.task_statuses_from_workflow(path)


# --- fixture builders ------------------------------------------------------------


def event_line(event, task):
    record = {"event": event, "task": task, "at": "2026-10-07T15:30:00+09:00"}
    return json.dumps(record).encode("utf-8")


FAILED_ON_LINE_1 = event_line("failed", TARGET) + b"\n"


def workflow_text(block_lines, final_newline=True):
    """A workflow.yaml whose `implement` step is in progress and whose
    `tasks:` mapping holds task0001 with `block_lines` (each already carrying
    its own indentation) as its own block. `final_newline=False` leaves the
    last line of the file without a line terminator."""
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
    text = "\n".join(lines)
    return text + "\n" if final_newline else text


def notes_block(header="|", body=("status: pending", "more text")):
    """A `notes` block scalar at the direct-child indentation (4) whose body
    lines are indented deeper (6)."""
    return ["    notes: %s" % header] + ["      %s" % line for line in body]


RECORD_LINE = "    %s: 1" % RECORD_KEY
TITLE_LINE = '    title: "task %s"' % TARGET
OTHER_KEY_IGNORED = "    status:detail: ignored"
OTHER_KEY_VALUELESS = "    status:detail:"


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


# --- AC-1: a differently named `status:`-prefixed key is skipped ------------------


class TestOtherKeyWithStatusPrefixIsSkipped(unittest.TestCase):
    """AC-1 (FR1, FR3; TS-1, TS-3): the reader called directly."""

    def test_ignored_other_key_does_not_hide_the_direct_status(self):  # AC-1
        block = [TITLE_LINE, OTHER_KEY_IGNORED, "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})

    def test_valueless_other_key_does_not_hide_the_direct_status(self):  # AC-1
        block = [TITLE_LINE, OTHER_KEY_VALUELESS, "    status: failed"]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "failed"})


# --- AC-2: `status:` glued to a value is not a key line ---------------------------


class TestStatusColonWithoutSeparatorIsNotAKeyLine(unittest.TestCase):
    """AC-2 (FR1, FR3; TS-4, TS-7): the colon must be followed by a space, a
    tab or the end of the line."""

    def test_only_status_colon_pending_without_space_omits_the_task(self):  # AC-2
        block = [TITLE_LINE, "    status:pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {})

    def test_status_colon_failed_without_space_is_skipped(self):  # AC-2
        block = [TITLE_LINE, "    status:failed", "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})


# --- AC-3: a tab after the colon qualifies -----------------------------------------


class TestTabAfterColonIsAKeyLine(unittest.TestCase):
    """AC-3 (FR1; TS-5)."""

    def test_status_colon_tab_value_decides(self):  # AC-3
        block = [TITLE_LINE, "    status:\tpending"]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})

    def test_tab_form_decides_before_a_later_status_line(self):  # AC-3
        block = [TITLE_LINE, "    status:\tpending", "    status: failed"]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})


# --- AC-4: a value-less `status:` still decides and leaves the task out ------------


class TestValuelessStatusStillDecides(unittest.TestCase):
    """AC-4 (FR2; TS-6): the end of the line after the colon qualifies, the
    value cannot be extracted, so the task is left out and later lines are
    not read."""

    def test_bare_colon_with_newline_omits_the_task(self):  # AC-4
        block = [TITLE_LINE, "    status:", "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {})

    def test_bare_colon_as_last_line_without_final_newline_omits_the_task(self):  # AC-4
        block = [TITLE_LINE, "    status:"]
        text = workflow_text(block, final_newline=False)
        self.assertTrue(text.endswith("    status:"))
        self.assertEqual(statuses_of(text), {})

    def test_bare_colon_then_status_line_without_final_newline_omits_the_task(self):  # AC-4
        block = [TITLE_LINE, "    status:", "    status: pending"]
        text = workflow_text(block, final_newline=False)
        self.assertEqual(statuses_of(text), {})

    def test_bare_colon_after_a_skipped_other_key_still_decides(self):  # AC-4
        block = [TITLE_LINE, OTHER_KEY_IGNORED, "    status:", "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {})


# --- AC-5: the hook blocks for the task once its direct status is read --------------


class TestHookBlocksAfterSkippedOtherKey(HookAssertions):
    """AC-5 (FR1; TS-2): the AC-1 block plus the route-back record and a
    journal whose line 1 is the task's `failed` event."""

    BLOCK = [TITLE_LINE, OTHER_KEY_IGNORED, "    status: pending", RECORD_LINE]

    def test_hook_blocks_and_names_the_task(self):  # AC-5
        self.assert_blocks_naming_target(run_hook(workflow_text(self.BLOCK)))

    def test_hook_blocks_with_the_value_less_other_key_form(self):  # AC-5
        block = [TITLE_LINE, OTHER_KEY_VALUELESS, "    status: pending", RECORD_LINE]
        self.assert_blocks_naming_target(run_hook(workflow_text(block)))


# --- AC-6: skipping a non-key line never exposes bodies or nested lines (TM-1) ------


class TestSkippedOtherKeyKeepsReadScope(HookAssertions):
    """AC-6 (TM-1, FR2; TS-8): after a skipped `status:detail: ignored` line,
    a `status: pending` inside a deeper notes block-scalar body, or inside a
    nested mapping, is never read; the block has no direct status key line."""

    NOTES_CASE = [TITLE_LINE, OTHER_KEY_IGNORED, RECORD_LINE] + notes_block("|")
    NESTED_CASE = [
        TITLE_LINE,
        OTHER_KEY_IGNORED,
        RECORD_LINE,
        "    meta:",
        "      status: pending",
    ]

    def test_reader_never_reads_the_block_scalar_body(self):  # AC-6
        for header in ("|", ">", "|-", "|+", "|2"):
            with self.subTest(header=header):
                block = [TITLE_LINE, OTHER_KEY_IGNORED, RECORD_LINE]
                block += notes_block(header)
                self.assertEqual(statuses_of(workflow_text(block)), {})

    def test_reader_never_reads_the_nested_mapping(self):  # AC-6
        self.assertEqual(statuses_of(workflow_text(self.NESTED_CASE)), {})

    def test_hook_does_not_block_for_the_block_scalar_body(self):  # AC-6
        self.assert_not_blocked(run_hook(workflow_text(self.NOTES_CASE)))

    def test_hook_does_not_block_for_the_nested_mapping(self):  # AC-6
        self.assert_not_blocked(run_hook(workflow_text(self.NESTED_CASE)))

    def test_body_value_after_a_skipped_line_does_not_replace_a_direct_status(self):  # AC-6
        block = (
            [TITLE_LINE, OTHER_KEY_IGNORED]
            + notes_block("|", ("status: failed", "more text"))
            + ["    status: pending"]
        )
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})

    def test_glued_status_line_inside_a_body_is_never_read(self):  # AC-6
        block = [TITLE_LINE, OTHER_KEY_IGNORED, RECORD_LINE] + notes_block(
            "|", ("status:pending", "status: pending")
        )
        self.assertEqual(statuses_of(workflow_text(block)), {})

    def test_comment_line_after_a_skipped_line_is_never_the_status(self):  # AC-6
        block = [
            TITLE_LINE,
            OTHER_KEY_IGNORED,
            "    # status: failed",
            "    status: pending",
        ]
        self.assertEqual(statuses_of(workflow_text(block)), {TARGET: "pending"})

    def test_skipped_first_line_still_sets_the_direct_indent(self):  # AC-6 (FR2)
        # The block's first line is the skipped non-key line at indentation 6;
        # the direct-child indentation is 6, so the later 4-space line is not
        # a candidate.
        block = ["      status:detail: ignored", "    status: pending"]
        self.assertEqual(statuses_of(workflow_text(block)), {})


# --- AC-7: contract identifiers keep their names ------------------------------------


class TestContractIdentifiers(unittest.TestCase):
    """AC-7 (NFR3): the identifiers named by the contract keep their names."""

    def test_identifiers_exist(self):  # AC-7
        for name in (
            "task_statuses_from_workflow",
            "TASK_STATUS_RE",
            "TASKS_SECTION_RE",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(HOOK, name))


if __name__ == "__main__":
    unittest.main()
