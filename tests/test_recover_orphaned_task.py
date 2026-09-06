"""Tests for task0003: em-workflow/scripts/recover-orphaned-task.py

Covers task0003 Acceptance Criteria (feature-docs/orphaned-implementer-recovery/
tasks/task0003.md):

- AC-1: TestEndToEndDecide.test_ac1_* -- the proven fixture reports
  `recovered` and invokes the injected stub helper (SC2's outcome contract)
  exactly once with the task identifier and reason `orphaned`.
- AC-2: TestEndToEndDecide.test_ac2_* -- each of the four unproven cases
  (identity absent, identity equal to current, transcript unreadable,
  transcript active) reports `residual` with its distinct SC6 reason code,
  leaves the journal byte-identical, and never invokes the helper (TS-3).
- AC-3: TestEndToEndDecide.test_ac3_* -- a malformed identity (path
  separator, dot segment, empty, over-length) reports `residual` with
  `invalid-session-id` without opening anything outside the transcripts
  directory (TS-5, TS-9); TestSessionIdValidation is the direct pure-function
  coverage and TestTranscriptPathContainment is the direct containment
  coverage the Test Notes ask for.
- AC-4: TestTranscriptsDirDerivation -- the D1 pure function maps a known
  absolute working directory to the expected directory name, and
  `--transcripts-dir` replaces the derivation entirely (no test below ever
  resolves a path under the real `~/.claude`).
- AC-5: TestCurrentSessionResolution -- D2 form 1 (explicit id+start)
  precedence over form 2 (marker scan), marker scan resolving both identity
  and start, and the unresolved case.
- AC-6: TestEndToEndDecide.test_ac6_* -- an already-terminal final journal
  event yields `noop_terminal` with no helper invocation and no write.
- AC-7: TestDefaultJournalHelperPath -- the no-override default path
  resolves to the sibling `journal-append-failed.py`, outcome reporting
  matches SC3, and a helper failure never leaves the journal modified.

TestCLIEntryPoint exercises the command-line entry point itself (argparse
wiring, stdout JSON, exit codes) on top of the function-level coverage above
(IMPLEMENTATION.md Conventions: "scripts are exercised through their
command-line entry point plus function-level calls").

Covers task0006 Acceptance Criteria (feature-docs/orphaned-implementer-recovery/
tasks/task0006.md) -- D7's binding step, inserted between the "agent index
entry exists" and "entry carries a session identity" steps above:

- AC-1: TestAgentEntryBinding.test_ac1_* -- a `launched` -> `failed` ->
  `launched` journal history whose single agent index entry's `at` is far
  older than the last `launched` event's `at` reports `residual` with
  `stale-agent-entry`, leaves the journal byte-identical, and invokes the
  helper zero times.
- AC-2: TestAgentEntryBinding.test_ac2_* -- the same fixture with the
  entry's `at` equal to, later than, or exactly `AGENT_ENTRY_BINDING_TOLERANCE`
  earlier than the last `launched` event's `at` is admitted and reaches the
  pre-existing `recovered` outcome.
- AC-3: TestAgentEntryBinding.test_ac3_* -- each of the six data shapes that
  cannot be compared (both sides in turn: absent, non-string, unparsable
  `at`; plus the two aware/naive combinations) is a binding failure, not a
  pass, reporting `stale-agent-entry` with no write and no helper call.
- AC-4: TestAgentEntryBinding.test_ac4_* -- the tolerance is
  `ROT.AGENT_ENTRY_BINDING_TOLERANCE`, pinned to exactly 2 seconds, with a
  parameterised admitted/rejected pair straddling the boundary.
- AC-5: no new test -- the pre-existing TestEndToEndDecide cases pass
  unchanged (the binding step is satisfied by every existing fixture's
  matching `at` values), which is the no-regression proof itself.
- AC-6: TestAgentEntryBinding.test_ac6_* -- an entry that is both unbindable
  AND carries no `session_id` reports `stale-agent-entry`, proving the
  binding step runs before the session-identity read.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "recover-orphaned-task.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("recover_orphaned_task", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROT = _load_module()


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def write_jsonl(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_transcript(transcripts_dir, session_id, entries):
    path = os.path.join(transcripts_dir, f"{session_id}.jsonl")
    write_jsonl(path, entries)
    return path


STUB_HELPER_TEMPLATE = '''#!/usr/bin/env python3
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    with open({record_path!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {{"journal": args.journal, "task": args.task, "reason": args.reason}}
        ) + "\\n")
    print(json.dumps(
        {{"outcome": {outcome!r}, "task": args.task, "reason": args.reason}}
    ))
    return {exit_code}


if __name__ == "__main__":
    sys.exit(main())
'''

FAILING_STUB_HELPER_TEMPLATE = '''#!/usr/bin/env python3
import sys

sys.stderr.write("stub helper: simulated internal error\\n")
sys.exit(3)
'''


def write_stub_helper(directory, record_path, outcome="appended", exit_code=0,
                       name="stub-journal-helper.py"):
    path = os.path.join(directory, name)
    content = STUB_HELPER_TEMPLATE.format(
        record_path=record_path, outcome=outcome, exit_code=exit_code
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def write_failing_stub_helper(directory, name="failing-stub-journal-helper.py"):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(FAILING_STUB_HELPER_TEMPLATE)
    return path


def read_stub_calls(record_path):
    if not os.path.exists(record_path):
        return []
    with open(record_path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


TASK_ID = "task0099"
RECORDED_SESSION_ID = "sess-old"
CURRENT_SESSION_ID = "sess-new"
CURRENT_SESSION_START = "2026-01-02T00:00:00+00:00"
TRANSCRIPT_OLD_TIMESTAMP = "2026-01-01T00:00:00+00:00"


def _build_proven_fixture(tmp_dir, final_event="launched", worktree_path=None):
    """A fixture satisfying every evidence-pipeline step: the recorded
    session (`sess-old`) differs from the current one (`sess-new`), whose
    transcript's newest activity is strictly older than the current
    session's start.

    `final_event` controls the journal pre-check: "launched" (default)
    lets the pipeline reach the helper invocation; "merged"/"failed" make
    it terminal (AC-6); None leaves the task absent from the journal
    entirely (journal-not-launched coverage).
    """
    journal_path = os.path.join(tmp_dir, "journal.jsonl")
    agents_index_path = os.path.join(tmp_dir, "agents.jsonl")
    transcripts_dir = os.path.join(tmp_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    journal_lines = []
    if final_event is not None:
        journal_lines.append(
            {"event": "launched", "task": TASK_ID, "at": "2026-01-01T00:00:00+00:00"}
        )
        if final_event != "launched":
            journal_lines.append(
                {"event": final_event, "task": TASK_ID, "at": "2026-01-01T01:00:00+00:00"}
            )
    write_jsonl(journal_path, journal_lines)

    write_jsonl(agents_index_path, [
        {
            "agent_id": "a1",
            "agent_ids": ["a1"],
            "task": TASK_ID,
            "worktree_path": worktree_path or "/x/task0099",
            "at": "2026-01-01T00:00:00+00:00",
            "session_id": RECORDED_SESSION_ID,
        },
    ])

    write_transcript(transcripts_dir, RECORDED_SESSION_ID, [
        {"timestamp": TRANSCRIPT_OLD_TIMESTAMP, "type": "assistant"},
    ])

    return {
        "task_id": TASK_ID,
        "journal_path": journal_path,
        "agents_index_path": agents_index_path,
        "transcripts_dir": transcripts_dir,
        "current_session_id": CURRENT_SESSION_ID,
        "current_session_start": CURRENT_SESSION_START,
    }


def _decide_from_fixture(fx, **overrides):
    kwargs = dict(
        task_id=fx["task_id"],
        journal_path=fx["journal_path"],
        agents_index_path=fx["agents_index_path"],
        transcripts_dir=fx["transcripts_dir"],
        current_session_id=fx["current_session_id"],
        current_session_start=fx["current_session_start"],
    )
    kwargs.update(overrides)
    return ROT.decide(**kwargs)


# ---------------------------------------------------------------------------
# task0006 (D7 binding step) fixtures.
# ---------------------------------------------------------------------------

# Sentinel meaning "omit the `at` field entirely" -- distinct from any real
# value (including None/JSON null), so a fixture can build the "no `at`
# field at all" case (AC-3) explicitly rather than accidentally.
_OMIT_AT = object()

# The launch under recovery's own `launched` event `at` -- two hours after
# the fixture's earlier launched/failed pair, which is "far apart" per the
# Test Notes (an hour is enough) so AC-1's stale case is unambiguously about
# the binding rule, not the tolerance.
LAST_LAUNCHED_AT = "2026-01-01T02:00:00+00:00"


def _build_binding_fixture(
    tmp_dir,
    entry_at=LAST_LAUNCHED_AT,
    last_launched_at=LAST_LAUNCHED_AT,
    include_session_id=True,
    worktree_path=None,
):
    """A fixture whose journal holds, for the task, `launched` -> `failed`
    -> `launched` (the last `launched` being the launch under recovery,
    its `at` given by `last_launched_at`), and whose agent index holds
    exactly one entry for the task at `entry_at`. Every OTHER
    evidence-pipeline step is already satisfied when `include_session_id`
    is True (a valid, differing session id whose transcript's newest
    activity is strictly older than the current session's start), so a
    `residual`/`stale-agent-entry` outcome can only be attributed to the D7
    binding step itself (task0006 AC-1). `entry_at` / `last_launched_at`
    accept `_OMIT_AT` to build the "no `at` field at all" cases (AC-3)."""
    journal_path = os.path.join(tmp_dir, "journal.jsonl")
    agents_index_path = os.path.join(tmp_dir, "agents.jsonl")
    transcripts_dir = os.path.join(tmp_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    last_launched_event = {"event": "launched", "task": TASK_ID}
    if last_launched_at is not _OMIT_AT:
        last_launched_event["at"] = last_launched_at
    write_jsonl(journal_path, [
        {"event": "launched", "task": TASK_ID, "at": "2025-12-01T00:00:00+00:00"},
        {"event": "failed", "task": TASK_ID, "at": "2025-12-01T01:00:00+00:00", "reason": "net"},
        last_launched_event,
    ])

    entry = {
        "agent_id": "a1",
        "agent_ids": ["a1"],
        "task": TASK_ID,
        "worktree_path": worktree_path or "/x/task0099",
    }
    if entry_at is not _OMIT_AT:
        entry["at"] = entry_at
    if include_session_id:
        entry["session_id"] = RECORDED_SESSION_ID
    write_jsonl(agents_index_path, [entry])

    write_transcript(transcripts_dir, RECORDED_SESSION_ID, [
        {"timestamp": TRANSCRIPT_OLD_TIMESTAMP, "type": "assistant"},
    ])

    return {
        "task_id": TASK_ID,
        "journal_path": journal_path,
        "agents_index_path": agents_index_path,
        "transcripts_dir": transcripts_dir,
        "current_session_id": CURRENT_SESSION_ID,
        "current_session_start": CURRENT_SESSION_START,
    }


class TestSessionIdValidation(unittest.TestCase):
    """SC5, direct pure-function coverage (supports AC-3 / TS-9)."""

    def test_valid_uuid_like_identity_accepted(self):
        self.assertTrue(ROT.is_valid_session_id("550e8400-e29b-41d4-a716-446655440000"))

    def test_valid_alnum_with_underscore_and_hyphen_accepted(self):
        self.assertTrue(ROT.is_valid_session_id("Ab9_session-42"))

    def test_exactly_64_chars_accepted(self):
        value = "a" + "1" * 63
        self.assertEqual(len(value), 64)
        self.assertTrue(ROT.is_valid_session_id(value))

    def test_65_chars_over_length_rejected(self):
        value = "a" + "1" * 64
        self.assertEqual(len(value), 65)
        self.assertFalse(ROT.is_valid_session_id(value))

    def test_empty_string_rejected(self):
        self.assertFalse(ROT.is_valid_session_id(""))

    def test_path_separator_rejected(self):
        self.assertFalse(ROT.is_valid_session_id("abc/def"))

    def test_dot_segment_rejected(self):
        self.assertFalse(ROT.is_valid_session_id(".."))
        self.assertFalse(ROT.is_valid_session_id("abc.def"))

    def test_leading_hyphen_rejected(self):
        self.assertFalse(ROT.is_valid_session_id("-abc"))

    def test_leading_underscore_rejected(self):
        self.assertFalse(ROT.is_valid_session_id("_abc"))

    def test_whitespace_rejected(self):
        self.assertFalse(ROT.is_valid_session_id("abc def"))

    def test_nul_byte_rejected(self):
        self.assertFalse(ROT.is_valid_session_id("abc\x00def"))

    def test_non_string_rejected(self):
        self.assertFalse(ROT.is_valid_session_id(None))
        self.assertFalse(ROT.is_valid_session_id(12345))


class TestTranscriptsDirDerivation(unittest.TestCase):
    """D1, direct pure-function coverage (AC-4)."""

    def test_encode_cwd_maps_known_path(self):
        self.assertEqual(ROT.encode_cwd("/home/user/project"), "-home-user-project")

    def test_encode_cwd_replaces_dot_and_underscore_individually(self):
        self.assertEqual(
            ROT.encode_cwd("/home/user/my.project_x"), "-home-user-my-project-x"
        )

    def test_encode_cwd_does_not_collapse_consecutive_replacements(self):
        # Two consecutive disallowed characters (two spaces) become two
        # separate hyphens, not one.
        self.assertEqual(ROT.encode_cwd("/a  b"), "-a--b")

    def test_default_transcripts_dir_maps_known_cwd_to_expected_directory(self):
        expected = os.path.join(
            os.path.expanduser("~/.claude/projects"), "-x-y-project"
        )
        self.assertEqual(ROT.default_transcripts_dir(cwd="/x/y/project"), expected)

    def test_transcripts_dir_flag_replaces_derivation_entirely(self):
        # decide() must use the injected --transcripts-dir verbatim rather
        # than the default derivation -- proven by succeeding against a
        # fixture placed entirely under a temp directory unrelated to any
        # real ~/.claude layout.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path)
            outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)
            self.assertEqual(exit_code, 0)
            self.assertEqual(outcome["outcome"], "recovered")


class TestTranscriptPathContainment(unittest.TestCase):
    """Direct coverage of the pure containment function (defense-in-depth;
    Test Notes: localise a containment regression quickly)."""

    def test_normal_session_id_resolves_inside_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ROT.resolve_transcript_path(tmp, "abc123", False)
            expected = os.path.realpath(os.path.join(tmp, "abc123.jsonl"))
            self.assertEqual(result, expected)

    def test_dot_dot_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_dir = os.path.join(tmp, "transcripts")
            os.makedirs(transcripts_dir)
            # A session_id embedding a path separator and a `..` segment:
            # `{id}.jsonl` becomes two components ("..", "evil.jsonl"), the
            # first of which climbs out of transcripts_dir. Bypasses
            # is_valid_session_id on purpose (it would reject the "/" long
            # before this runs) -- this function must refuse the escape on
            # its own, independent of the SC5 gate.
            result = ROT.resolve_transcript_path(transcripts_dir, "../evil", False)
            self.assertIsNone(result)

    def test_symlinked_transcript_escaping_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcripts_dir = os.path.join(tmp, "transcripts")
            outside_dir = os.path.join(tmp, "outside")
            os.makedirs(transcripts_dir)
            os.makedirs(outside_dir)
            target = os.path.join(outside_dir, "target.jsonl")
            write_jsonl(target, [{"timestamp": "2020-01-01T00:00:00+00:00"}])
            symlink_path = os.path.join(transcripts_dir, "escape-session.jsonl")
            os.symlink(target, symlink_path)
            result = ROT.resolve_transcript_path(transcripts_dir, "escape-session", False)
            self.assertIsNone(result)

    def test_check_under_claude_projects_rejects_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            # tmp is never under ~/.claude/projects.
            result = ROT.resolve_transcript_path(tmp, "abc123", True)
            self.assertIsNone(result)


class TestCurrentSessionResolution(unittest.TestCase):
    """D2, direct pure-function coverage (AC-5)."""

    def test_form1_explicit_pair_takes_precedence_over_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A transcript that WOULD resolve via the marker, to a
            # different identity/start than the explicit pair.
            write_transcript(tmp, "sess-marker", [
                {"timestamp": "2020-01-01T00:00:00+00:00", "text": "TOKEN present"},
            ])
            result = ROT.resolve_current_session(
                "sess-explicit", "2026-01-02T00:00:00+00:00", "TOKEN", tmp
            )
            self.assertEqual(
                result,
                ("sess-explicit", ROT.parse_timestamp("2026-01-02T00:00:00+00:00")),
            )

    def test_form1_requires_both_id_and_start_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, "sess-marker", [
                {"timestamp": "2020-01-01T00:00:00+00:00", "text": "TOKEN present"},
            ])
            # Only the id is given (no start): falls through to the marker.
            result = ROT.resolve_current_session("sess-explicit", None, "TOKEN", tmp)
            self.assertEqual(result[0], "sess-marker")

    def test_marker_scan_picks_newest_matching_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            older = write_transcript(tmp, "sess-older", [
                {"timestamp": "2020-01-01T00:00:00+00:00", "text": "no token here"},
            ])
            newer = write_transcript(tmp, "sess-newer", [
                {"timestamp": "2021-06-01T12:00:00+00:00", "text": "carries TOKEN"},
            ])
            newest_no_match = write_transcript(tmp, "sess-newest-no-match", [
                {"timestamp": "2022-01-01T00:00:00+00:00", "text": "irrelevant"},
            ])
            now = 1_700_000_000
            os.utime(older, (now, now))
            os.utime(newer, (now + 10, now + 10))
            os.utime(newest_no_match, (now + 20, now + 20))

            result = ROT.resolve_current_session(None, None, "TOKEN", tmp)
            self.assertEqual(
                result, ("sess-newer", ROT.parse_timestamp("2021-06-01T12:00:00+00:00"))
            )

    def test_marker_match_with_unusable_first_entry_fails_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, "sess-bad-first-entry", [
                {"text": "carries TOKEN but no timestamp field"},
                {"timestamp": "2021-06-01T12:00:00+00:00", "text": "TOKEN"},
            ])
            result = ROT.resolve_current_session(None, None, "TOKEN", tmp)
            self.assertIsNone(result)

    def test_no_form_provided_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ROT.resolve_current_session(None, None, None, tmp)
            self.assertIsNone(result)

    def test_marker_with_no_matching_transcript_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, "sess-a", [
                {"timestamp": "2020-01-01T00:00:00+00:00", "text": "no match here"},
            ])
            result = ROT.resolve_current_session(None, None, "MISSING-TOKEN", tmp)
            self.assertIsNone(result)

    def test_form1_with_unparsable_start_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ROT.resolve_current_session("sess-a", "not-a-timestamp", None, tmp)
            self.assertIsNone(result)


class TestDefaultJournalHelperPath(unittest.TestCase):
    """AC-7: no-override default path resolves to the sibling
    journal-append-failed.py, outcome reporting matches SC3, and a helper
    failure never leaves the journal modified."""

    def setUp(self):
        self._saved_script_dir = ROT._SCRIPT_DIR

    def tearDown(self):
        ROT._SCRIPT_DIR = self._saved_script_dir

    def test_default_path_is_the_real_sibling_script(self):
        expected = str(SCRIPT_PATH.parent / "journal-append-failed.py")
        self.assertEqual(ROT.default_journal_helper_path(), expected)

    def test_no_override_wiring_invokes_default_sibling_and_reports_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            # Monkeypatch the module's notion of "this script's directory"
            # to a temp dir holding a stub named exactly like the real
            # sibling -- exercises the *default* resolution path (no
            # --journal-helper) without touching the real script directory
            # or depending on the real journal-append-failed.py existing.
            fake_dir = os.path.join(tmp, "fake-scripts-dir")
            os.makedirs(fake_dir)
            write_stub_helper(
                fake_dir, record_path, outcome="appended",
                name=ROT.DEFAULT_JOURNAL_HELPER_NAME,
            )
            ROT._SCRIPT_DIR = fake_dir

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=None)

            self.assertEqual(exit_code, 0)
            self.assertEqual(outcome, {"outcome": "recovered", "task": TASK_ID, "reason": ""})
            calls = read_stub_calls(record_path)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["reason"], "orphaned")

    def test_helper_failure_is_non_zero_exit_and_never_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            before = Path(fx["journal_path"]).read_bytes()
            failing_helper = write_failing_stub_helper(tmp)

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=failing_helper)

            self.assertNotEqual(exit_code, 0)
            self.assertIsNone(outcome)
            after = Path(fx["journal_path"]).read_bytes()
            self.assertEqual(before, after)

    def test_helper_unparsable_stdout_is_non_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            before = Path(fx["journal_path"]).read_bytes()
            garbage_helper_path = os.path.join(tmp, "garbage-helper.py")
            with open(garbage_helper_path, "w", encoding="utf-8") as fh:
                fh.write("#!/usr/bin/env python3\nprint('not json')\n")

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=garbage_helper_path)

            self.assertNotEqual(exit_code, 0)
            self.assertIsNone(outcome)
            after = Path(fx["journal_path"]).read_bytes()
            self.assertEqual(before, after)


class TestEndToEndDecide(unittest.TestCase):
    """AC-1, AC-2, AC-3, AC-6: the full evidence pipeline via decide()."""

    def test_ac1_proven_orphan_reports_recovered_and_invokes_helper_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome, {"outcome": "recovered", "task": TASK_ID, "reason": ""}
            )
            calls = read_stub_calls(record_path)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["task"], TASK_ID)
            self.assertEqual(calls[0]["reason"], "orphaned")
            self.assertEqual(calls[0]["journal"], fx["journal_path"])

    def _assert_residual_no_write_no_invoke(self, fx, decide_kwargs, expected_reason):
        record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
        helper_path = write_stub_helper(
            os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
        )
        before = Path(fx["journal_path"]).read_bytes()

        kwargs = dict(decide_kwargs)
        kwargs.setdefault("journal_helper", helper_path)
        outcome, exit_code = _decide_from_fixture(fx, **kwargs)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            outcome, {"outcome": "residual", "task": TASK_ID, "reason": expected_reason}
        )
        after = Path(fx["journal_path"]).read_bytes()
        self.assertEqual(before, after, "journal must stay byte-identical")
        self.assertEqual(read_stub_calls(record_path), [], "helper must not be invoked")

    def test_ac2a_identity_absent_reports_no_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            # Overwrite the agent index entry with no session_id field.
            write_jsonl(fx["agents_index_path"], [
                {
                    "agent_id": "a1", "agent_ids": ["a1"], "task": TASK_ID,
                    "worktree_path": "/x/task0099", "at": "2026-01-01T00:00:00+00:00",
                },
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "no-session-id")

    def test_ac2b_identity_equal_to_current_reports_same_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            self._assert_residual_no_write_no_invoke(
                fx, {"current_session_id": RECORDED_SESSION_ID}, "same-session"
            )

    def test_ac2c_transcript_unreadable_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            os.remove(os.path.join(fx["transcripts_dir"], f"{RECORDED_SESSION_ID}.jsonl"))
            self._assert_residual_no_write_no_invoke(fx, {}, "transcript-unreadable")

    def test_ac2c_transcript_unreadable_when_no_usable_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_transcript(fx["transcripts_dir"], RECORDED_SESSION_ID, [
                {"text": "no timestamp field at all"},
                "not even a json object",
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "transcript-unreadable")

    def test_ac2d_transcript_active_reports_transcript_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_transcript(fx["transcripts_dir"], RECORDED_SESSION_ID, [
                {"timestamp": "2026-01-02T00:00:01+00:00", "type": "assistant"},
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "transcript-active")

    def test_ac3_malformed_identity_with_path_separator_is_invalid_and_decoy_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            # A decoy transcript placed OUTSIDE the injected transcripts
            # directory, at exactly the path a "../decoy-session" identity
            # would reach if containment were missing. Its content is
            # deliberately "proof of a gone session" so that if it were
            # ever consulted, the outcome would flip to `recovered` instead
            # of `residual`/`invalid-session-id`.
            base_dir = os.path.dirname(fx["transcripts_dir"])
            decoy_path = os.path.join(base_dir, "decoy-session.jsonl")
            write_jsonl(decoy_path, [{"timestamp": "2020-01-01T00:00:00+00:00"}])
            decoy_before = Path(decoy_path).read_bytes()

            write_jsonl(fx["agents_index_path"], [
                {
                    "agent_id": "a1", "agent_ids": ["a1"], "task": TASK_ID,
                    "worktree_path": "/x/task0099", "at": "2026-01-01T00:00:00+00:00",
                    "session_id": "../decoy-session",
                },
            ])

            self._assert_residual_no_write_no_invoke(fx, {}, "invalid-session-id")
            self.assertEqual(Path(decoy_path).read_bytes(), decoy_before)

    def test_ac3_empty_identity_is_no_session_id_not_invalid(self):
        # An explicit empty string is "no session id recorded" (SC1 says
        # absence must degrade to unknown); it never reaches SC5.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                {
                    "agent_id": "a1", "agent_ids": ["a1"], "task": TASK_ID,
                    "worktree_path": "/x/task0099", "at": "2026-01-01T00:00:00+00:00",
                    "session_id": "",
                },
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "no-session-id")

    def test_ac3_over_length_identity_is_invalid_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            over_length = "a" + "1" * 64
            write_jsonl(fx["agents_index_path"], [
                {
                    "agent_id": "a1", "agent_ids": ["a1"], "task": TASK_ID,
                    "worktree_path": "/x/task0099", "at": "2026-01-01T00:00:00+00:00",
                    "session_id": over_length,
                },
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "invalid-session-id")

    def test_ac6_already_merged_reports_noop_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp, final_event="merged")
            self._assert_residual_noop(fx)

    def test_ac6_already_failed_reports_noop_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp, final_event="failed")
            self._assert_residual_noop(fx)

    def _assert_residual_noop(self, fx):
        record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
        helper_path = write_stub_helper(
            os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
        )
        before = Path(fx["journal_path"]).read_bytes()

        outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            outcome, {"outcome": "noop_terminal", "task": TASK_ID, "reason": ""}
        )
        after = Path(fx["journal_path"]).read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(read_stub_calls(record_path), [])

    def test_no_event_at_all_for_task_reports_journal_not_launched(self):
        # Extra coverage beyond the mandatory ACs: an evidence-proven task
        # absent from the journal entirely is "anything else", not terminal.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp, final_event=None)
            self._assert_residual_no_write_no_invoke(fx, {}, "journal-not-launched")

    def test_no_agent_entry_reports_no_agent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [])
            self._assert_residual_no_write_no_invoke(fx, {}, "no-agent-entry")

    def test_transcripts_dir_missing_reports_transcripts_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            fx["transcripts_dir"] = os.path.join(tmp, "does-not-exist")
            self._assert_residual_no_write_no_invoke(fx, {}, "transcripts-dir-missing")

    def test_current_session_unknown_when_neither_form_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            self._assert_residual_no_write_no_invoke(
                fx,
                {"current_session_id": None, "current_session_start": None, "marker": None},
                "current-session-unknown",
            )

    def test_timestamp_boundary_equal_start_is_transcript_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_transcript(fx["transcripts_dir"], RECORDED_SESSION_ID, [
                {"timestamp": CURRENT_SESSION_START, "type": "assistant"},
            ])
            self._assert_residual_no_write_no_invoke(fx, {}, "transcript-active")

    def test_timestamp_boundary_one_microsecond_before_start_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            write_transcript(fx["transcripts_dir"], RECORDED_SESSION_ID, [
                {"timestamp": "2026-01-01T23:59:59.999999+00:00", "type": "assistant"},
            ])
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(outcome["outcome"], "recovered")


class TestAgentEntryBinding(unittest.TestCase):
    """task0006 (orphaned-implementer-recovery review-round-2): D7's binding
    step, inserted between the "agent index entry exists" step and the
    "entry carries a session identity" step (AC-1 through AC-6)."""

    def _assert_residual_stale_no_write_no_invoke(self, fx):
        record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
        helper_path = write_stub_helper(
            os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
        )
        before = Path(fx["journal_path"]).read_bytes()

        outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            outcome, {"outcome": "residual", "task": TASK_ID, "reason": "stale-agent-entry"}
        )
        after = Path(fx["journal_path"]).read_bytes()
        self.assertEqual(before, after, "journal must stay byte-identical")
        self.assertEqual(read_stub_calls(record_path), [], "helper must not be invoked")

    def _assert_recovered(self, fx):
        record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
        helper_path = write_stub_helper(
            os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
        )

        outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            outcome, {"outcome": "recovered", "task": TASK_ID, "reason": ""}
        )
        calls = read_stub_calls(record_path)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["task"], TASK_ID)
        self.assertEqual(calls[0]["reason"], "orphaned")

    # -- AC-1 ----------------------------------------------------------

    def test_ac1_stale_entry_far_older_than_last_launched_reports_stale_agent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp,
                entry_at="2026-01-01T00:00:00+00:00",  # two hours older than LAST_LAUNCHED_AT
                last_launched_at=LAST_LAUNCHED_AT,
            )
            self._assert_residual_stale_no_write_no_invoke(fx)

    # -- AC-2 ----------------------------------------------------------

    def test_ac2_entry_at_equal_to_last_launched_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(tmp, entry_at=LAST_LAUNCHED_AT, last_launched_at=LAST_LAUNCHED_AT)
            self._assert_recovered(fx)

    def test_ac2_entry_at_later_than_last_launched_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at="2026-01-01T02:00:05+00:00", last_launched_at=LAST_LAUNCHED_AT
            )
            self._assert_recovered(fx)

    def test_ac2_entry_at_earlier_by_exactly_tolerance_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at="2026-01-01T01:59:58+00:00", last_launched_at=LAST_LAUNCHED_AT
            )
            self._assert_recovered(fx)

    # -- AC-3 ------------------------------------------------------------

    def test_ac3_entry_has_no_at_field_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(tmp, entry_at=_OMIT_AT, last_launched_at=LAST_LAUNCHED_AT)
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_entry_at_not_a_string_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(tmp, entry_at=1735689600, last_launched_at=LAST_LAUNCHED_AT)
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_entry_at_unparsable_string_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at="not-a-timestamp", last_launched_at=LAST_LAUNCHED_AT
            )
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_last_launched_event_has_no_at_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(tmp, entry_at=LAST_LAUNCHED_AT, last_launched_at=_OMIT_AT)
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_last_launched_event_at_unparsable_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at=LAST_LAUNCHED_AT, last_launched_at="not-a-timestamp"
            )
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_entry_aware_last_launched_naive_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at="2026-01-01T02:00:00+00:00", last_launched_at="2026-01-01T02:00:00"
            )
            self._assert_residual_stale_no_write_no_invoke(fx)

    def test_ac3_entry_naive_last_launched_aware_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp, entry_at="2026-01-01T02:00:00", last_launched_at="2026-01-01T02:00:00+00:00"
            )
            self._assert_residual_stale_no_write_no_invoke(fx)

    # -- AC-4 ------------------------------------------------------------

    def test_ac4_tolerance_constant_is_two_seconds(self):
        self.assertEqual(ROT.AGENT_ENTRY_BINDING_TOLERANCE, timedelta(seconds=2))

    def test_ac4_boundary_exactly_at_tolerance_admitted_one_second_beyond_stale(self):
        last_dt = ROT.parse_timestamp(LAST_LAUNCHED_AT)
        admitted_at = (last_dt - ROT.AGENT_ENTRY_BINDING_TOLERANCE).isoformat()
        rejected_at = (
            last_dt - ROT.AGENT_ENTRY_BINDING_TOLERANCE - timedelta(seconds=1)
        ).isoformat()
        self.assertTrue(ROT.agent_entry_is_bound(admitted_at, LAST_LAUNCHED_AT))
        self.assertFalse(ROT.agent_entry_is_bound(rejected_at, LAST_LAUNCHED_AT))

    # -- AC-6 ------------------------------------------------------------

    def test_ac6_unbindable_entry_with_no_session_id_reports_stale_agent_entry(self):
        # Proves ordering: if the session-identity read ran first, an entry
        # with no session_id would report `no-session-id` instead.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_binding_fixture(
                tmp,
                entry_at="2026-01-01T00:00:00+00:00",  # unbindable
                last_launched_at=LAST_LAUNCHED_AT,
                include_session_id=False,
            )
            self._assert_residual_stale_no_write_no_invoke(fx)


class TestCLIEntryPoint(unittest.TestCase):
    """Command-line entry point wiring (argparse, stdout JSON, exit codes)."""

    def test_cli_reports_recovered_via_stub_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            proc = run_cli([
                "--journal", fx["journal_path"],
                "--agents-index", fx["agents_index_path"],
                "--task", fx["task_id"],
                "--transcripts-dir", fx["transcripts_dir"],
                "--current-session-id", fx["current_session_id"],
                "--current-session-start", fx["current_session_start"],
                "--journal-helper", helper_path,
            ])

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip())
            self.assertEqual(payload, {"outcome": "recovered", "task": TASK_ID, "reason": ""})

    def test_cli_reports_residual_reason_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proven_fixture(tmp)
            proc = run_cli([
                "--journal", fx["journal_path"],
                "--agents-index", fx["agents_index_path"],
                "--task", fx["task_id"],
                "--transcripts-dir", fx["transcripts_dir"],
                "--current-session-id", RECORDED_SESSION_ID,
                "--current-session-start", fx["current_session_start"],
            ])

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip())
            self.assertEqual(
                payload, {"outcome": "residual", "task": TASK_ID, "reason": "same-session"}
            )

    def test_cli_missing_required_argument_is_usage_error(self):
        proc = run_cli(["--task", "task0001"])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
