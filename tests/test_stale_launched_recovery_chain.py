"""Tests for task0002: em-workflow/scripts/recover-orphaned-task.py's opt-in
evidence chain (feature-docs/stale-launched-retry-recovery/tasks/task0002.md).

The legacy (no-evidence) pipeline's own Acceptance Criteria and regression
coverage live in tests/test_recover_orphaned_task.py; AC-5 here is proven
there (its pre-existing tests continue to pass unmodified). This module
covers the NEW chain only:

- AC-1: TestChainRecoveredPath -- all seven evidence inputs proving, against
  a fixture whose journal last event is `launched`, whose newest agent
  index entry is launch-bound and records the same identity as the
  supplied current session: `recovered`, and the injected stub helper is
  invoked exactly once with the task id, reason `stale-launched`, the
  journal path, and the launch identity equal to the last `launched`
  event's raw `at`.
- AC-2: TestChainOrderedUnmetConditions -- one case per unmet condition, in
  the chain's fixed order, each asserting the exact reason string and a
  byte-identical journal; TestChainEntryGating covers the FR5 no-evidence
  case (see AC-5 note above).
- AC-3: TestChainInsufficientEvidence -- the three insufficient-evidence
  termination tokens plus a very-old `launched` timestamp all yield
  `agent-termination-unproven`, never `recovered` -- no elapsed-time
  threshold exists in the chain.
- AC-4: TestChainAgentIdentitySecurityPin -- a recorded session identity
  byte-equal to a genuine candidate never becomes the stop target, pinned
  at source level (direct inspection of `resolve_bound_stop_target`'s
  source) and at behaviour level (an ambiguous-candidate fixture where the
  coincidence could otherwise slip through).
- AC-5: no new test here -- proven by tests/test_recover_orphaned_task.py's
  pre-existing tests continuing to pass unmodified (the identity-equality
  case and the payload-shape assertion); TestChainEntryGating additionally
  proves the no-evidence case directly against a fixture that WOULD
  otherwise satisfy the whole new chain, so its `same-session` outcome is
  attributable only to the missing evidence.
- AC-6: TestChainStepOrderDirect -- calls `evaluate_stale_launched_chain`
  directly (decide()'s own pre-existing agent-index read would otherwise
  short-circuit first) with a nonexistent `agents.jsonl` path, proving the
  artifact check runs before any agent index read or file open.
- AC-7: covered by the byte-identity + zero-invocation assertions embedded
  in every TestChainOrderedUnmetConditions/TestChainInsufficientEvidence
  case, plus TestChainByteIdentityAndNoCreation's dedicated
  no-file-created proof.
- AC-8: no new test module -- tests/test_plugin_version_parity.py already
  asserts parity; this module and recover-orphaned-task.py import only the
  standard library (verified by inspection: no `import` beyond
  `importlib.util`, `inspect`, `json`, `os`, `subprocess`, `sys`,
  `tempfile`, `unittest`, `pathlib`).

TestCLIEntryPoint exercises the new flags through the command-line entry
point (IMPLEMENTATION.md Conventions: "scripts are exercised through their
command-line entry point plus function-level calls"), on top of the
function-level coverage above.
"""

import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "recover-orphaned-task.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("recover_orphaned_task_chain", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROT = _load_module()


def write_jsonl(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


STUB_HELPER_TEMPLATE = '''#!/usr/bin/env python3
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--launch-at", default=None)
    args = parser.parse_args()
    with open({record_path!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {{"journal": args.journal, "task": args.task, "reason": args.reason,
              "launch_at": args.launch_at}}
        ) + "\\n")
    print(json.dumps(
        {{"outcome": {outcome!r}, "task": args.task, "reason": args.reason}}
    ))
    return {exit_code}


if __name__ == "__main__":
    sys.exit(main())
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


def read_stub_calls(record_path):
    if not os.path.exists(record_path):
        return []
    with open(record_path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


TASK_ID = "task0077"
SESSION_ID = "sess-retry-abc123"
CURRENT_SESSION_START = "2026-02-01T00:00:00+00:00"
AGENT_IDENTITY = "agent-xyz-001"
TASK_WORKTREE = "/x/worktrees/task0077"
LAST_LAUNCHED_AT = "2026-02-01T00:00:05+00:00"


def _agent_index_entry(at=LAST_LAUNCHED_AT, agent_ids=None, worktree_path=TASK_WORKTREE,
                        session_id=SESSION_ID, include_session_id=True):
    entry = {
        "task": TASK_ID,
        "at": at,
        "agent_id": AGENT_IDENTITY,
        "agent_ids": agent_ids if agent_ids is not None else [AGENT_IDENTITY],
        "worktree_path": worktree_path,
    }
    if include_session_id:
        entry["session_id"] = session_id
    return entry


def _build_proving_fixture(tmp_dir):
    """A fixture satisfying EVERY step of both the legacy pre-check (agent
    entry present + D7-bound, valid session id, current session resolves,
    recorded identity equal to current -- i.e. the same-session branch) and
    the new chain's own seven steps (artifacts present, journal state
    `launched`, D7-bound entry, valid+resolving session identity, bound
    stop target, terminated, stop result proving). AC-2/AC-3/AC-4 cases are
    built by mutating exactly one field of this fixture, per the Test
    Notes' "one-value mutation of one shared proving fixture" guidance."""
    journal_path = os.path.join(tmp_dir, "journal.jsonl")
    agents_index_path = os.path.join(tmp_dir, "agents.jsonl")
    transcripts_dir = os.path.join(tmp_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    write_jsonl(journal_path, [
        {"event": "launched", "task": TASK_ID, "at": LAST_LAUNCHED_AT},
    ])
    write_jsonl(agents_index_path, [_agent_index_entry()])

    return {
        "task_id": TASK_ID,
        "journal_path": journal_path,
        "agents_index_path": agents_index_path,
        "transcripts_dir": transcripts_dir,
        "current_session_id": SESSION_ID,
        "current_session_start": CURRENT_SESSION_START,
        "worktree_present": "yes",
        "branch_present": "yes",
        "task_worktree": TASK_WORKTREE,
        "stop_target": AGENT_IDENTITY,
        "launch_termination": "terminated",
        "stop_result": "not-running",
        "stop_result_target": AGENT_IDENTITY,
    }


def _decide_from_fixture(fx, **overrides):
    kwargs = dict(fx)
    kwargs.update(overrides)
    return ROT.decide(**kwargs)


def _assert_residual(test, fx, expected_reason, **overrides):
    record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
    helper_path = write_stub_helper(
        os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
    )
    before = Path(fx["journal_path"]).read_bytes()

    kwargs = dict(overrides)
    kwargs.setdefault("journal_helper", helper_path)
    outcome, exit_code = _decide_from_fixture(fx, **kwargs)

    test.assertEqual(exit_code, 0)
    test.assertEqual(
        outcome, {"outcome": "residual", "task": TASK_ID, "reason": expected_reason}
    )
    after = Path(fx["journal_path"]).read_bytes()
    test.assertEqual(before, after, "journal must stay byte-identical")
    test.assertEqual(read_stub_calls(record_path), [], "helper must not be invoked")


def _assert_noop_terminal(test, fx, **overrides):
    record_path = os.path.join(os.path.dirname(fx["journal_path"]), "calls.jsonl")
    helper_path = write_stub_helper(
        os.path.dirname(fx["journal_path"]), record_path, outcome="appended"
    )
    before = Path(fx["journal_path"]).read_bytes()

    kwargs = dict(overrides)
    kwargs.setdefault("journal_helper", helper_path)
    outcome, exit_code = _decide_from_fixture(fx, **kwargs)

    test.assertEqual(exit_code, 0)
    test.assertEqual(outcome, {"outcome": "noop_terminal", "task": TASK_ID, "reason": ""})
    after = Path(fx["journal_path"]).read_bytes()
    test.assertEqual(before, after)
    test.assertEqual(read_stub_calls(record_path), [])


class TestChainRecoveredPath(unittest.TestCase):
    """AC-1."""

    def test_ac1_all_evidence_proving_reports_recovered_and_invokes_stub_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
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
            self.assertEqual(calls[0]["reason"], "stale-launched")
            self.assertEqual(calls[0]["journal"], fx["journal_path"])
            self.assertEqual(calls[0]["launch_at"], LAST_LAUNCHED_AT)


class TestChainEntryGating(unittest.TestCase):
    """AC-5 / D-A: supplying none of the seven evidence inputs reproduces
    the legacy same-session outcome exactly, even against a fixture that
    would otherwise satisfy the entire new chain."""

    def test_no_evidence_supplied_keeps_same_session_on_a_fully_proving_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            for key in (
                "worktree_present", "branch_present", "task_worktree",
                "stop_target", "launch_termination", "stop_result",
                "stop_result_target",
            ):
                fx[key] = None
            before = Path(fx["journal_path"]).read_bytes()

            outcome, exit_code = ROT.decide(**fx)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome, {"outcome": "residual", "task": TASK_ID, "reason": "same-session"}
            )
            after = Path(fx["journal_path"]).read_bytes()
            self.assertEqual(before, after)


class TestChainOrderedUnmetConditions(unittest.TestCase):
    """AC-2: one case per unmet condition, in the chain's fixed order."""

    # -- step 1: artifacts, then journal state ---------------------------

    def test_terminal_journal_event_reports_noop_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["journal_path"], [
                {"event": "launched", "task": TASK_ID, "at": LAST_LAUNCHED_AT},
                {"event": "merged", "task": TASK_ID, "at": "2026-02-01T01:00:00+00:00"},
            ])
            _assert_noop_terminal(self, fx)

    def test_non_launched_final_event_reports_journal_not_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["journal_path"], [
                {"event": "launched", "task": TASK_ID, "at": LAST_LAUNCHED_AT},
                {"event": "queued", "task": TASK_ID, "at": "2026-02-01T01:00:00+00:00"},
            ])
            _assert_residual(self, fx, "journal-not-launched")

    def test_worktree_absent_reports_task_artifacts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", worktree_present="no")

    def test_branch_absent_reports_task_artifacts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", branch_present="no")

    # -- step 2: agent index entry + D7 binding (reused) ------------------

    def test_no_agent_entry_reports_no_agent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [])
            _assert_residual(self, fx, "no-agent-entry")

    def test_entry_outside_binding_tolerance_reports_stale_agent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(at="2026-01-01T00:00:00+00:00"),
            ])
            _assert_residual(self, fx, "stale-agent-entry")

    # -- step 3: session identity (reused) --------------------------------

    def test_absent_session_id_reports_no_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(include_session_id=False),
            ])
            _assert_residual(self, fx, "no-session-id")

    def test_malformed_session_id_reports_invalid_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(session_id="../evil"),
            ])
            _assert_residual(self, fx, "invalid-session-id")

    def test_unresolvable_current_session_reports_current_session_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "current-session-unknown",
                current_session_id=None, current_session_start=None, marker=None,
            )

    # -- step 4: bound stop target -----------------------------------------

    def test_stop_target_mismatch_reports_agent_identity_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "agent-identity-unproven", stop_target="not-the-bound-agent"
            )

    def test_task_worktree_mismatch_reports_agent_identity_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "agent-identity-unproven", task_worktree="/somewhere/else"
            )

    def test_ambiguous_candidates_reports_agent_identity_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(agent_ids=[AGENT_IDENTITY, "another-agent"]),
            ])
            _assert_residual(self, fx, "agent-identity-unproven")

    # -- step 5: harness termination ---------------------------------------

    def test_termination_absent_reports_agent_termination_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "agent-termination-unproven", launch_termination=None)

    def test_termination_running_reports_agent_still_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "agent-still-live", launch_termination="running")

    # -- step 6: stop result -------------------------------------------------

    def test_stop_result_error_reports_stop_result_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "stop-result-unproven", stop_result="error")

    def test_stop_result_target_mismatch_reports_stop_result_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "stop-result-unproven", stop_result_target="someone-else"
            )

    # -- step 7: in-lock launch identity -------------------------------------

    def test_helper_reports_launch_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="launch_changed")
            before = Path(fx["journal_path"]).read_bytes()

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome, {"outcome": "residual", "task": TASK_ID, "reason": "launch-changed"}
            )
            after = Path(fx["journal_path"]).read_bytes()
            self.assertEqual(before, after, "this script itself never writes the journal")
            calls = read_stub_calls(record_path)
            self.assertEqual(len(calls), 1, "step 7 does invoke the helper once")


class TestChainInsufficientEvidence(unittest.TestCase):
    """AC-3: no elapsed-time threshold or idle-interval proxy anywhere in
    the chain."""

    def test_launch_accepted_token_is_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "agent-termination-unproven", launch_termination="launch-accepted"
            )

    def test_error_token_is_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "agent-termination-unproven", launch_termination="error"
            )

    def test_output_idle_token_is_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(
                self, fx, "agent-termination-unproven", launch_termination="output-idle"
            )

    def test_very_old_launched_timestamp_still_unproven_never_recovered(self):
        # No elapsed-time threshold exists anywhere in the chain -- an
        # ancient `launched` timestamp proves nothing about termination on
        # its own, no matter how old.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            ancient_at = "2000-01-01T00:00:00+00:00"
            write_jsonl(fx["journal_path"], [
                {"event": "launched", "task": TASK_ID, "at": ancient_at},
            ])
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(at=ancient_at),
            ])
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            outcome, exit_code = _decide_from_fixture(
                fx, journal_helper=helper_path, launch_termination=None
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome,
                {"outcome": "residual", "task": TASK_ID, "reason": "agent-termination-unproven"},
            )
            self.assertNotEqual(outcome["outcome"], "recovered")
            self.assertEqual(read_stub_calls(record_path), [])


class TestChainAgentIdentitySecurityPin(unittest.TestCase):
    """AC-4: the session-identity field is never read into the stop-target
    candidate set, at both source level and behaviour level."""

    def test_source_level_resolve_bound_stop_target_never_reads_session_id(self):
        source = inspect.getsource(ROT.resolve_bound_stop_target)
        self.assertNotIn("session_id", source)

    def test_behaviour_level_coincidental_identity_equality_never_proves_binding(self):
        # Zero real candidates (`agent_ids` empty) -- binding must fail for
        # lack of a candidate, even though the recorded session identity
        # (which MUST equal the current session's to reach this branch at
        # all) is byte-equal to the supplied `--stop-target`. If the
        # implementation ever fell back to session_id as a candidate when
        # `agent_ids` is empty, this coincidence would let it slip through.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(agent_ids=[], session_id=SESSION_ID),
            ])
            _assert_residual(self, fx, "agent-identity-unproven", stop_target=SESSION_ID)


class TestChainStepOrderDirect(unittest.TestCase):
    """AC-6: `evaluate_stale_launched_chain` decides artifacts before any
    agent index read or file open. Calling it directly (rather than through
    `decide()`, whose own PRE-EXISTING agent-index read would otherwise
    short-circuit first with `no-agent-entry`) with an agents_index_path
    that does not exist at all proves the chain function's own internal
    ordering."""

    def test_artifact_check_precedes_any_agent_index_read_or_file_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            nonexistent_agents_index = os.path.join(tmp, "does-not-exist", "agents.jsonl")
            nonexistent_journal = os.path.join(tmp, "also-does-not-exist", "journal.jsonl")

            outcome, exit_code = ROT.evaluate_stale_launched_chain(
                task_id=TASK_ID,
                journal_path=nonexistent_journal,
                agents_index_path=nonexistent_agents_index,
                worktree_present="no",
                branch_present="yes",
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome,
                {"outcome": "residual", "task": TASK_ID, "reason": "task-artifacts-missing"},
            )


class TestChainByteIdentityAndNoCreation(unittest.TestCase):
    """AC-7: a residual/noop_terminal creates neither the journal file nor
    its parent directory."""

    def test_residual_creates_neither_journal_file_nor_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_journal = os.path.join(tmp, "not-yet-created", "journal.jsonl")
            missing_agents_index = os.path.join(tmp, "not-yet-created", "agents.jsonl")

            outcome, exit_code = ROT.evaluate_stale_launched_chain(
                task_id=TASK_ID,
                journal_path=missing_journal,
                agents_index_path=missing_agents_index,
                worktree_present="yes",
                branch_present="yes",
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(outcome["outcome"], "residual")
            self.assertFalse(os.path.exists(os.path.dirname(missing_journal)))
            self.assertFalse(os.path.exists(missing_journal))


class TestCLIEntryPoint(unittest.TestCase):
    """New evidence flags wired through argparse into decide() (this
    module's own coverage on top of the function-level tests above --
    IMPLEMENTATION.md Conventions: "scripts are exercised through their
    command-line entry point plus function-level calls")."""

    def test_cli_all_evidence_flags_report_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT_PATH),
                    "--journal", fx["journal_path"],
                    "--agents-index", fx["agents_index_path"],
                    "--task", fx["task_id"],
                    "--transcripts-dir", fx["transcripts_dir"],
                    "--current-session-id", fx["current_session_id"],
                    "--current-session-start", fx["current_session_start"],
                    "--journal-helper", helper_path,
                    "--worktree-present", "yes",
                    "--branch-present", "yes",
                    "--task-worktree", TASK_WORKTREE,
                    "--stop-target", AGENT_IDENTITY,
                    "--launch-termination", "terminated",
                    "--stop-result", "not-running",
                    "--stop-result-target", AGENT_IDENTITY,
                ],
                capture_output=True, text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip())
            self.assertEqual(payload, {"outcome": "recovered", "task": TASK_ID, "reason": ""})


if __name__ == "__main__":
    unittest.main()
