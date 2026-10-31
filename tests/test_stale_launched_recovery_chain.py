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

Extended by feature-docs/routeback-deferred-findings/tasks/task0002.md
(SC-2, D1, D2): step 1's artifact observations become genuine evidence
(`yes` or `no`, both kept) rather than a `yes`-only gate. Its own
Acceptance Criteria (distinct from the AC numbering above, which belongs to
the stale-launched-retry-recovery feature):

- AC-1: TestChainMissingArtifactRecovery -- each of the three
  missing-artifact pairs reaches `recovered`, via `decide()` and via a
  direct `evaluate_stale_launched_chain` call.
- AC-2: the unrecognized-token/absent-observation conversions and additions
  in TestChainOrderedUnmetConditions, and the unrecognized-token conversion
  in TestChainStepOrderDirect.
- AC-3: TestChainMissingArtifactLaterStepsUnaffected -- the termination and
  stop-result checks are unaffected by which artifact is missing.
- AC-4: TestChainTaskWorktreeExistenceIrrelevant -- a nonexistent
  `--task-worktree` path still binds when it matches the recorded
  worktree (pre-existing, unchanged behaviour, pinned as a regression
  guard).
- AC-5: no new test here -- tests/test_recover_orphaned_task.py's
  pre-existing tests continue to pass unmodified.
- AC-6: TestCLIEntryPoint's two added cases -- `--worktree-present no
  --branch-present no` reaches `recovered`; `--worktree-present maybe`
  (same flags) reports `task-artifacts-missing`.
- AC-7: TestModuleDocstringChain -- the removed phrases are absent from the
  live docstring, proven with a negative-proof control and a
  retained-anchor guard against a verbatim pre-change excerpt.

Extended by feature-docs/canonical-worktree-path-guards/tasks/task0002.md
(SC-2, D1, D2): chain step 4 compares the entry's recorded worktree with
`--task-worktree` after resolving links on both sides. Its own Acceptance
Criteria (distinct from the numbering of the two features above):

- AC-1: TestLinkedLayoutBinding -- in a linked layout the entry records the
  canonical path and `--task-worktree` is the same worktree spelled through
  the link: `recovered` through `decide()` and through the command-line
  entry point, the stub helper invoked exactly once.
- AC-2: TestLinkedLayoutBinding -- the same fixture after the task worktree
  directory was removed is still `recovered`.
- AC-3: TestWorktreeBindingMalformedPaths -- an empty or relative value on
  either side (and equal malformed values on both) is `residual` /
  `agent-identity-unproven`.
- AC-4: TestWorktreeBindingNeverRaises -- non-string, NUL-carrying and
  resolution-error cases are binding failures; nothing is raised.
- AC-5: TestWorktreeBindingOtherWorktree -- the canonical path of a
  different existing worktree is not a match.
- AC-6: TestWorktreeBindingKeepsOtherRules plus the pre-existing
  TestChainAgentIdentitySecurityPin -- the candidate, `agent_ids`-only and
  stop-target rules are unchanged and no `session_id` reaches the binding
  code; the pre-existing tests of this module and of
  tests/test_recover_orphaned_task.py pass unmodified.
- AC-7: TestBindingDocstringContract (the docstring of
  `resolve_bound_stop_target` and of TestChainTaskWorktreeExistenceIrrelevant,
  each assertion paired with a negative proof) and
  TestStandardLibraryOnlyImports (the script and this module, checked by
  parsing their import statements).
"""

import ast
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_worktree_unrecognized_token_reports_task_artifacts_missing(self):
        # "Yes" (wrong case) is a token that is neither exactly "yes" nor
        # exactly "no" -- SC-2 case-sensitivity.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", worktree_present="Yes")

    def test_branch_unrecognized_token_reports_task_artifacts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", branch_present="absent")

    def test_worktree_observation_absent_reports_task_artifacts_missing(self):
        # An absent observation (None, i.e. the flag was never supplied) is
        # distinct from an unrecognized token, but yields the same residual.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", worktree_present=None)

    def test_branch_observation_absent_reports_task_artifacts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", branch_present=None)

    def test_empty_string_observation_reports_task_artifacts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            _assert_residual(self, fx, "task-artifacts-missing", worktree_present="")

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

            # "maybe" is an unrecognized token (not "no"): under the
            # narrowed SC-2 meaning, "no" is now recognized evidence and
            # would no longer short-circuit here on its own.
            outcome, exit_code = ROT.evaluate_stale_launched_chain(
                task_id=TASK_ID,
                journal_path=nonexistent_journal,
                agents_index_path=nonexistent_agents_index,
                worktree_present="maybe",
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


# -----------------------------------------------------------------------
# routeback-deferred-findings task0002 (SC-2, D1, D2): the artifact
# observations become genuine evidence rather than a `yes`-only gate.
# -----------------------------------------------------------------------

MISSING_ARTIFACT_PAIRS = (("no", "yes"), ("yes", "no"), ("no", "no"))
INSUFFICIENT_TERMINATION_TOKENS = (None, "launch-accepted", "error", "output-idle")


class TestChainMissingArtifactRecovery(unittest.TestCase):
    """AC-1: each of the three missing-artifact pairs still reaches
    `recovered`, both through `decide()` and through a direct
    `evaluate_stale_launched_chain` call, with the stub helper invoked
    exactly once with the task id, reason `stale-launched`, the journal
    path, and the last `launched` event's raw `at` as launch identity."""

    def test_missing_artifact_pairs_reach_recovered_via_decide(self):
        for worktree_present, branch_present in MISSING_ARTIFACT_PAIRS:
            with self.subTest(worktree_present=worktree_present, branch_present=branch_present):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    record_path = os.path.join(tmp, "calls.jsonl")
                    helper_path = write_stub_helper(tmp, record_path, outcome="appended")

                    outcome, exit_code = _decide_from_fixture(
                        fx,
                        journal_helper=helper_path,
                        worktree_present=worktree_present,
                        branch_present=branch_present,
                    )

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

    def test_missing_artifact_pairs_reach_recovered_via_direct_chain_call(self):
        for worktree_present, branch_present in MISSING_ARTIFACT_PAIRS:
            with self.subTest(worktree_present=worktree_present, branch_present=branch_present):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    record_path = os.path.join(tmp, "calls.jsonl")
                    helper_path = write_stub_helper(tmp, record_path, outcome="appended")
                    kwargs = dict(fx)
                    kwargs.pop("task_id")
                    kwargs["worktree_present"] = worktree_present
                    kwargs["branch_present"] = branch_present
                    kwargs["journal_helper"] = helper_path

                    outcome, exit_code = ROT.evaluate_stale_launched_chain(
                        task_id=TASK_ID, **kwargs
                    )

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


class TestChainMissingArtifactLaterStepsUnaffected(unittest.TestCase):
    """AC-3: with a missing artifact, the termination and stop-result steps
    behave exactly as in the both-present case -- no artifact-driven
    shortcut and no elapsed-time proxy anywhere in the chain."""

    def test_insufficient_termination_tokens_report_agent_termination_unproven(self):
        for worktree_present, branch_present in MISSING_ARTIFACT_PAIRS:
            for token in INSUFFICIENT_TERMINATION_TOKENS:
                with self.subTest(
                    worktree_present=worktree_present, branch_present=branch_present, token=token
                ):
                    with tempfile.TemporaryDirectory() as tmp:
                        fx = _build_proving_fixture(tmp)
                        _assert_residual(
                            self, fx, "agent-termination-unproven",
                            worktree_present=worktree_present,
                            branch_present=branch_present,
                            launch_termination=token,
                        )

    def test_running_termination_reports_agent_still_live(self):
        for worktree_present, branch_present in MISSING_ARTIFACT_PAIRS:
            with self.subTest(worktree_present=worktree_present, branch_present=branch_present):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _assert_residual(
                        self, fx, "agent-still-live",
                        worktree_present=worktree_present,
                        branch_present=branch_present,
                        launch_termination="running",
                    )

    def test_non_proving_stop_result_reports_stop_result_unproven(self):
        for worktree_present, branch_present in MISSING_ARTIFACT_PAIRS:
            with self.subTest(worktree_present=worktree_present, branch_present=branch_present):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _assert_residual(
                        self, fx, "stop-result-unproven",
                        worktree_present=worktree_present,
                        branch_present=branch_present,
                        stop_result="error",
                    )


class TestChainTaskWorktreeExistenceIrrelevant(unittest.TestCase):
    """AC-4: `--task-worktree` is compared after resolving links on both
    sides; a value that names the entry's recorded worktree still binds even
    when that path does not exist on disk. This behaviour is pre-existing
    (Design: "no existence check may be introduced there") -- pinned here
    as a regression guard rather than proven red first."""

    def test_nonexistent_task_worktree_path_still_binds_when_it_matches_the_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            self.assertFalse(os.path.exists(fx["task_worktree"]))
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            outcome, exit_code = _decide_from_fixture(fx, journal_helper=helper_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                outcome, {"outcome": "recovered", "task": TASK_ID, "reason": ""}
            )


# Verbatim excerpts captured from this task's base commit (before task0002's
# docstring edit), used only as a negative-proof control -- proving the
# search method used against the live docstring is actually capable of
# finding the phrase it is supposed to detect.
PRE_CHANGE_CALLER_PRECONDITION_EXCERPT = (
    "step after it has already established the candidate conditions it owns: the\n"
    "task worktree and task branch exist, and the Agent index resolves no live\n"
    "agent."
)
PRE_CHANGE_STEP1_EXCERPT = (
    "  1. both `--worktree-present` and `--branch-present` read `yes`, decided\n"
    "     before any agent index read, any path assembly and any file open\n"
    "     -> task-artifacts-missing;"
)
REMOVED_PHRASE_WORKTREE_BRANCH_EXIST = "the task worktree and task branch exist"
REMOVED_PHRASE_BOTH_READ_YES = "both `--worktree-present` and `--branch-present` read `yes`"
CALLER_PRECONDITION_ANCHOR = "the candidate conditions it owns"
STEP1_ANCHOR = "before any agent index read, any path assembly and any file open"


def _normalize_ws(text):
    return " ".join(text.split())


class TestModuleDocstringChain(unittest.TestCase):
    """AC-7: the module docstring no longer states the old caller
    precondition or the old `yes`-only step-1 gate, and instead states that
    `yes`/`no` observations are accepted as evidence and that
    `task-artifacts-missing` means an absent or unrecognized observation."""

    def test_pre_change_excerpts_actually_contain_the_removed_phrases(self):
        # Negative-proof control: proves the exact phrases below are really
        # findable by substring search, against a verbatim pre-change
        # sample -- so the absence assertions below cannot pass vacuously
        # due to a typo in the search string.
        self.assertIn(
            REMOVED_PHRASE_WORKTREE_BRANCH_EXIST,
            _normalize_ws(PRE_CHANGE_CALLER_PRECONDITION_EXCERPT),
        )
        self.assertIn(
            REMOVED_PHRASE_BOTH_READ_YES,
            _normalize_ws(PRE_CHANGE_STEP1_EXCERPT),
        )

    def test_retained_anchor_present_in_both_sample_and_live_docstring(self):
        # Retained-anchor guard: a phrase present in both the pre-change
        # sample and the live document, so the excerpts above are proven to
        # be genuinely taken from the same region they claim to replace.
        self.assertIn(CALLER_PRECONDITION_ANCHOR, PRE_CHANGE_CALLER_PRECONDITION_EXCERPT)
        self.assertIn(CALLER_PRECONDITION_ANCHOR, _normalize_ws(ROT.__doc__))
        self.assertIn(STEP1_ANCHOR, PRE_CHANGE_STEP1_EXCERPT)
        self.assertIn(STEP1_ANCHOR, _normalize_ws(ROT.__doc__))

    def test_live_docstring_no_longer_states_worktree_and_branch_exist_precondition(self):
        self.assertNotIn(REMOVED_PHRASE_WORKTREE_BRANCH_EXIST, _normalize_ws(ROT.__doc__))

    def test_live_docstring_no_longer_states_both_flags_must_read_yes(self):
        self.assertNotIn(REMOVED_PHRASE_BOTH_READ_YES, _normalize_ws(ROT.__doc__))

    def test_live_docstring_states_yes_no_observations_accepted_as_evidence(self):
        self.assertIn("accepted as evidence", _normalize_ws(ROT.__doc__))

    def test_live_docstring_states_narrowed_meaning_of_task_artifacts_missing(self):
        self.assertIn("absent or unrecognized observation", _normalize_ws(ROT.__doc__))


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

    def test_cli_worktree_no_branch_no_reports_recovered(self):
        """AC-6."""
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
                    "--worktree-present", "no",
                    "--branch-present", "no",
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

    def test_cli_worktree_unrecognized_token_reports_task_artifacts_missing(self):
        """AC-6: same flags as the passing no/no case above, but
        `--worktree-present maybe` reports the residual instead."""
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
                    "--worktree-present", "maybe",
                    "--branch-present", "no",
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
            self.assertEqual(
                payload,
                {"outcome": "residual", "task": TASK_ID, "reason": "task-artifacts-missing"},
            )



# -----------------------------------------------------------------------
# canonical-worktree-path-guards task0002 (SC-2, D1, D2): chain step 4 binds
# the Agent index entry's recorded worktree to `--task-worktree` after
# resolving links on both sides, so a canonical recorded path binds to the
# same worktree spelled through a link -- also once that worktree no longer
# exists -- while malformed values and resolution errors stay binding
# failures that never raise.
# -----------------------------------------------------------------------


def _build_linked_fixture(tmp_dir, create_task_worktree=True):
    """The proving fixture in a linked layout.

    Inside `tmp_dir` a project directory holds a real store directory and
    the `.claude/worktrees/em-workflow` symlink to it (the store's own name
    does not recreate the `/.claude/worktrees/em-workflow/` segment).
    `$WT_ROOT/{T}` is created THROUGH the link. The Agent index entry
    records its strict realpath (the canonical path); `task_worktree` is
    the same worktree spelled through the link. Returns `(fx, layout)`;
    `layout` carries `linked` (the link spelling), `canonical`, `linked_root`
    (`$WT_ROOT` spelled through the link) and `store`."""
    fx = _build_proving_fixture(tmp_dir)
    project = os.path.join(tmp_dir, "project")
    store = os.path.join(project, "wt-store")
    worktrees_dir = os.path.join(project, ".claude", "worktrees")
    linked_root = os.path.join(worktrees_dir, "em-workflow")
    os.makedirs(store)
    os.makedirs(worktrees_dir)
    os.symlink(store, linked_root)
    linked = os.path.join(linked_root, TASK_ID)
    os.makedirs(linked)
    canonical = os.path.realpath(linked, strict=True)

    segment = "/.claude/worktrees/em-workflow/"
    assert segment in linked + "/", linked
    assert segment not in canonical + "/", canonical
    assert canonical != linked

    write_jsonl(fx["agents_index_path"], [_agent_index_entry(worktree_path=canonical)])
    fx["task_worktree"] = linked
    layout = {
        "linked": linked,
        "canonical": canonical,
        "linked_root": linked_root,
        "store": store,
    }
    return fx, layout


def _write_entry_worktree(fx, value, absent=False):
    """Rewrite the Agent index with ONE entry whose recorded `worktree_path`
    is `value` (or has no such field at all when `absent`)."""
    entry = _agent_index_entry(worktree_path=value)
    if absent:
        del entry["worktree_path"]
    write_jsonl(fx["agents_index_path"], [entry])


def _recorded_worktree(agents_index_path):
    with open(agents_index_path, encoding="utf-8") as fh:
        return json.loads(fh.readline())["worktree_path"]


def _assert_recovered_once(test, fx, **overrides):
    """`decide()` reports `recovered` and the stub helper is invoked exactly
    once, with reason `stale-launched`."""
    directory = os.path.dirname(fx["journal_path"])
    record_path = os.path.join(directory, "calls.jsonl")
    helper_path = write_stub_helper(directory, record_path, outcome="appended")

    kwargs = dict(overrides)
    kwargs.setdefault("journal_helper", helper_path)
    outcome, exit_code = _decide_from_fixture(fx, **kwargs)

    test.assertEqual(exit_code, 0)
    test.assertEqual(outcome, {"outcome": "recovered", "task": TASK_ID, "reason": ""})
    calls = read_stub_calls(record_path)
    test.assertEqual(len(calls), 1)
    test.assertEqual(calls[0]["task"], TASK_ID)
    test.assertEqual(calls[0]["reason"], "stale-launched")


def _cli_command(fx, helper_path, task_worktree):
    return [
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
        "--task-worktree", task_worktree,
        "--stop-target", AGENT_IDENTITY,
        "--launch-termination", "terminated",
        "--stop-result", "not-running",
        "--stop-result-target", AGENT_IDENTITY,
    ]


class TestLinkedLayoutBinding(unittest.TestCase):
    """AC-1 and AC-2 (FR4, FR7, TS6, TS7): the entry records the canonical
    path and `--task-worktree` names the same worktree through a link."""

    def test_ac1_linked_fixture_has_differing_spellings_of_one_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)

            self.assertNotEqual(layout["canonical"], fx["task_worktree"])
            self.assertEqual(fx["task_worktree"], layout["linked"])
            self.assertTrue(os.path.samefile(layout["canonical"], fx["task_worktree"]))
            self.assertEqual(
                _recorded_worktree(fx["agents_index_path"]), layout["canonical"]
            )

    def test_ac1_canonical_recorded_path_binds_to_link_spelled_argument_via_decide(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, _layout = _build_linked_fixture(tmp)

            _assert_recovered_once(self, fx)

    def test_ac1_canonical_recorded_path_binds_to_link_spelled_argument_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            record_path = os.path.join(tmp, "calls.jsonl")
            helper_path = write_stub_helper(tmp, record_path, outcome="appended")

            proc = subprocess.run(
                _cli_command(fx, helper_path, layout["linked"]),
                capture_output=True, text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip())
            self.assertEqual(payload, {"outcome": "recovered", "task": TASK_ID, "reason": ""})
            calls = read_stub_calls(record_path)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["reason"], "stale-launched")

    def test_ac2_removed_task_worktree_still_binds_through_the_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            shutil.rmtree(layout["canonical"])
            self.assertFalse(os.path.exists(layout["canonical"]))
            self.assertFalse(os.path.exists(fx["task_worktree"]))
            # The link itself is intact: only the task worktree is gone.
            self.assertTrue(os.path.isdir(layout["linked_root"]))

            _assert_recovered_once(self, fx)


MALFORMED_PATH_VALUES = (
    ("empty string", ""),
    ("relative path", "x/worktrees/task0077"),
)


class TestWorktreeBindingMalformedPaths(unittest.TestCase):
    """AC-3 (TM-2, FR4, FR7, NFR3, TS8): an empty or relative worktree value
    is a binding failure on either side, and equal malformed values on both
    sides never bind."""

    def test_ac3_malformed_value_on_the_entry_side_is_unproven(self):
        for label, value in MALFORMED_PATH_VALUES:
            with self.subTest(value=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value)

                    _assert_residual(self, fx, "agent-identity-unproven")

    def test_ac3_malformed_value_on_the_argument_side_is_unproven(self):
        for label, value in MALFORMED_PATH_VALUES:
            with self.subTest(value=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)

                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac3_equal_malformed_values_on_both_sides_never_bind(self):
        for label, value in MALFORMED_PATH_VALUES:
            with self.subTest(value=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value)

                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac3_unmutated_fixture_still_recovers(self):
        # Control: the same fixture with neither side mutated proves, so
        # each residual above is attributable to the one mutated value.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)

            _assert_recovered_once(self, fx)


class TestWorktreeBindingNeverRaises(unittest.TestCase):
    """AC-4 (TM-3, FR4, FR7, NFR3, TS8): a non-string value, an embedded
    NUL and a resolution forced to raise are binding failures; no exception
    leaves `decide()`, the journal stays byte-identical and the helper is
    not invoked."""

    NON_STRING_RECORDED = (
        ("number", 5, False),
        ("list", ["/x/worktrees/task0077"], False),
        ("object", {"path": "/x/worktrees/task0077"}, False),
        ("null", None, False),
        ("field absent", None, True),
    )
    NON_STRING_ARGUMENTS = (
        ("number", 5),
        ("zero", 0),
        ("true", True),
        ("empty list", []),
        ("list", ["/x/worktrees/task0077"]),
        ("object", {"path": "/x/worktrees/task0077"}),
        ("bytes", b"/x/worktrees/task0077"),
    )
    NUL_VALUES = (
        ("trailing", TASK_WORKTREE + "\x00"),
        ("embedded", "/x/work\x00trees/task0077"),
        ("only", "\x00"),
    )

    def test_ac4_non_string_recorded_value_is_unproven(self):
        for label, value, absent in self.NON_STRING_RECORDED:
            with self.subTest(recorded=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value, absent=absent)

                    _assert_residual(self, fx, "agent-identity-unproven")

    def test_ac4_non_string_recorded_value_never_binds_to_an_equal_argument(self):
        for label, value, absent in self.NON_STRING_RECORDED:
            with self.subTest(recorded=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value, absent=absent)

                    # Equal on both sides; `None` leaves the other evidence
                    # inputs supplied, so the chain still runs.
                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac4_non_string_argument_is_unproven(self):
        for label, value in self.NON_STRING_ARGUMENTS:
            with self.subTest(argument=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)

                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac4_nul_on_the_entry_side_is_unproven(self):
        for label, value in self.NUL_VALUES:
            with self.subTest(nul=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value)
                    # The NUL reaches the script through a JSON escape.
                    raw = Path(fx["agents_index_path"]).read_text(encoding="utf-8")
                    self.assertIn("\\u0000", raw)

                    _assert_residual(self, fx, "agent-identity-unproven")

    def test_ac4_nul_on_the_argument_side_is_unproven(self):
        for label, value in self.NUL_VALUES:
            with self.subTest(nul=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)

                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac4_equal_nul_values_on_both_sides_never_bind(self):
        for label, value in self.NUL_VALUES:
            with self.subTest(nul=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)
                    _write_entry_worktree(fx, value)

                    _assert_residual(
                        self, fx, "agent-identity-unproven", task_worktree=value
                    )

    def test_ac4_resolution_raising_an_error_is_unproven(self):
        errors = (
            ("OSError", OSError("forced resolution failure")),
            ("PermissionError", PermissionError("forced resolution failure")),
            ("ValueError", ValueError("embedded null byte")),
        )
        for label, error in errors:
            with self.subTest(error=label):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = _build_proving_fixture(tmp)

                    with mock.patch.object(os.path, "realpath", side_effect=error) as stand_in:
                        _assert_residual(self, fx, "agent-identity-unproven")

                    self.assertTrue(
                        stand_in.called, "the binding step must resolve links through realpath"
                    )

    def test_ac4_pass_through_stand_in_does_not_by_itself_break_the_binding(self):
        # Control for the test above: the same stand-in mechanism, delegating
        # to the genuine resolution, still binds -- so the residuals above
        # come from the raised error, not from the replacement.
        with tempfile.TemporaryDirectory() as tmp:
            fx = _build_proving_fixture(tmp)
            genuine = os.path.realpath

            with mock.patch.object(os.path, "realpath", side_effect=genuine) as stand_in:
                _assert_recovered_once(self, fx)

            self.assertTrue(stand_in.called)


class TestWorktreeBindingOtherWorktree(unittest.TestCase):
    """AC-5 (FR4, FR7, NFR3, TS8): a recorded canonical path naming a
    different, existing worktree is not a match."""

    def test_ac5_canonical_path_of_a_different_existing_worktree_is_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            other_linked = os.path.join(layout["linked_root"], "task0078")
            os.makedirs(other_linked)
            other_canonical = os.path.realpath(other_linked, strict=True)
            self.assertNotEqual(other_canonical, layout["canonical"])
            _write_entry_worktree(fx, other_canonical)

            _assert_residual(self, fx, "agent-identity-unproven")

    def test_ac5_link_spelled_path_of_a_different_existing_worktree_is_unproven(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            other_linked = os.path.join(layout["linked_root"], "task0078")
            os.makedirs(other_linked)

            _assert_residual(
                self, fx, "agent-identity-unproven", task_worktree=other_linked
            )

    def test_ac5_control_matching_worktree_through_the_link_binds(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            os.makedirs(os.path.join(layout["linked_root"], "task0078"))

            _assert_recovered_once(self, fx)


class TestWorktreeBindingKeepsOtherRules(unittest.TestCase):
    """AC-6 (TM-4, FR4, TS9): the worktree rule change leaves the
    single-candidate, `agent_ids`-only and stop-target rules unchanged, and
    no `session_id` reaches the binding code."""

    def test_ac6_ambiguous_candidates_stay_unproven_when_the_worktree_binds_through_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(
                    agent_ids=[AGENT_IDENTITY, "another-agent"],
                    worktree_path=layout["canonical"],
                ),
            ])

            _assert_residual(self, fx, "agent-identity-unproven")

    def test_ac6_session_id_is_still_no_candidate_when_the_worktree_binds_through_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, layout = _build_linked_fixture(tmp)
            write_jsonl(fx["agents_index_path"], [
                _agent_index_entry(
                    agent_ids=[], session_id=SESSION_ID, worktree_path=layout["canonical"]
                ),
            ])

            _assert_residual(self, fx, "agent-identity-unproven", stop_target=SESSION_ID)

    def test_ac6_stop_target_mismatch_stays_unproven_when_the_worktree_binds_through_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx, _layout = _build_linked_fixture(tmp)

            _assert_residual(
                self, fx, "agent-identity-unproven", stop_target="not-the-bound-agent"
            )

    def test_ac6_worktree_resolution_helper_source_never_mentions_session_id(self):
        # The helper that resolves the two worktree values reads nothing
        # else; its source (docstring included) is as free of the token as
        # `resolve_bound_stop_target`'s own.
        source = inspect.getsource(ROT._resolved_worktree_path)
        self.assertNotIn("session_id", source)


# Verbatim docstring text captured from this task's base commit (before the
# docstring edits), used only as a negative-proof control: it shows the
# document predicates below do reject the pre-change statement.
PRE_CHANGE_BINDING_DOC = (
    "The stop target's identity is uniquely bound when ALL hold against\n"
    "    the given (already D7-bound) agent index entry: its candidate list\n"
    "    (`agent_ids`) names exactly one distinct value; its recorded\n"
    "    `worktree_path` equals `task_worktree`; and `stop_target` equals that\n"
    "    one candidate. Returns the bound identity string on success, else None\n"
    "    (-> agent-identity-unproven) -- no candidate, two or more distinct\n"
    "    candidates, a worktree mismatch, a stop-target mismatch, and an absent\n"
    "    or non-string `stop_target` are all a binding failure."
)
PRE_CHANGE_EXISTENCE_IRRELEVANT_DOC = (
    "AC-4: `--task-worktree` is compared as a plain string; a value that\n"
    "    equals the entry's recorded worktree still binds even when that path\n"
    "    does not exist on disk. This behaviour is pre-existing and unchanged by\n"
    "    this task (Design: \"no existence check may be introduced there\") --\n"
    "    pinned here as a regression guard rather than proven red first."
)
# Forged statements that carry the new wording, used as positive controls.
FORGED_BINDING_DOC = (
    "Bound when the recorded worktree_path and task_worktree are non-empty "
    "absolute path strings, both resolved through links with the path not "
    "required to exist, and the resolved values must be equal; a resolution "
    "error on either side is a binding failure, never an exception."
)
FORGED_EXISTENCE_IRRELEVANT_DOC = (
    "`--task-worktree` is compared after resolving links on both sides; a "
    "path that does not exist still binds."
)

BINDING_DOC_REQUIRED_PHRASES = (
    "non-empty absolute path strings",
    "resolved through links",
    "not required to exist",
    "the resolved values must be equal",
    "is a binding failure, never an exception",
)
BINDING_DOC_REMOVED_PHRASE = "`worktree_path` equals `task_worktree`"
EXISTENCE_DOC_REQUIRED_PHRASE = "compared after resolving links on both sides"
EXISTENCE_DOC_REMOVED_PHRASE = "plain string"
EXISTENCE_DOC_RETAINED_ANCHOR = "still binds even when that path does not exist on disk"
BINDING_DOC_RETAINED_ANCHOR = "names exactly one distinct value"


def _missing_binding_doc_phrases(doc):
    text = _normalize_ws(doc)
    return [phrase for phrase in BINDING_DOC_REQUIRED_PHRASES if phrase not in text]


class TestBindingDocstringContract(unittest.TestCase):
    """AC-7 (FR5, NFR1, TS13, TS14): the docstrings state the link-resolving
    comparison. Each assertion is paired with a negative proof."""

    def test_pre_change_binding_docstring_is_rejected_by_the_predicate(self):
        # Negative proof: the verbatim pre-change statement carries the
        # removed phrase and lacks every required phrase.
        self.assertIn(BINDING_DOC_REMOVED_PHRASE, _normalize_ws(PRE_CHANGE_BINDING_DOC))
        self.assertEqual(
            _missing_binding_doc_phrases(PRE_CHANGE_BINDING_DOC),
            list(BINDING_DOC_REQUIRED_PHRASES),
        )

    def test_forged_binding_docstring_is_accepted_by_the_predicate(self):
        # Positive control: the predicate is capable of passing.
        self.assertEqual(_missing_binding_doc_phrases(FORGED_BINDING_DOC), [])

    def test_binding_docstring_retains_the_single_candidate_anchor(self):
        # Retained-anchor guard: the pre-change sample and the live
        # docstring share this phrase, so the sample is taken from the
        # region it claims to replace.
        self.assertIn(BINDING_DOC_RETAINED_ANCHOR, _normalize_ws(PRE_CHANGE_BINDING_DOC))
        self.assertIn(
            BINDING_DOC_RETAINED_ANCHOR, _normalize_ws(ROT.resolve_bound_stop_target.__doc__)
        )

    def test_live_binding_docstring_states_the_link_resolving_comparison(self):
        self.assertEqual(
            _missing_binding_doc_phrases(ROT.resolve_bound_stop_target.__doc__), []
        )

    def test_live_binding_docstring_no_longer_states_plain_equality(self):
        self.assertNotIn(
            BINDING_DOC_REMOVED_PHRASE, _normalize_ws(ROT.resolve_bound_stop_target.__doc__)
        )

    def test_pre_change_existence_docstring_is_rejected_by_the_predicate(self):
        # Negative proof for the two assertions below.
        text = _normalize_ws(PRE_CHANGE_EXISTENCE_IRRELEVANT_DOC)
        self.assertIn(EXISTENCE_DOC_REMOVED_PHRASE, text)
        self.assertNotIn(EXISTENCE_DOC_REQUIRED_PHRASE, text)

    def test_forged_existence_docstring_is_accepted_by_the_predicate(self):
        text = _normalize_ws(FORGED_EXISTENCE_IRRELEVANT_DOC)
        self.assertNotIn(EXISTENCE_DOC_REMOVED_PHRASE, text)
        self.assertIn(EXISTENCE_DOC_REQUIRED_PHRASE, text)

    def test_existence_docstring_retains_the_nonexistent_path_anchor(self):
        self.assertIn(
            EXISTENCE_DOC_RETAINED_ANCHOR, _normalize_ws(PRE_CHANGE_EXISTENCE_IRRELEVANT_DOC)
        )
        self.assertIn(
            EXISTENCE_DOC_RETAINED_ANCHOR,
            _normalize_ws(TestChainTaskWorktreeExistenceIrrelevant.__doc__),
        )

    def test_live_existence_docstring_has_no_plain_string(self):
        self.assertNotIn(
            EXISTENCE_DOC_REMOVED_PHRASE,
            _normalize_ws(TestChainTaskWorktreeExistenceIrrelevant.__doc__),
        )

    def test_live_existence_docstring_states_the_resolved_comparison(self):
        self.assertIn(
            EXISTENCE_DOC_REQUIRED_PHRASE,
            _normalize_ws(TestChainTaskWorktreeExistenceIrrelevant.__doc__),
        )


def _non_stdlib_imports(source):
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    return sorted(imported - set(sys.stdlib_module_names))


class TestStandardLibraryOnlyImports(unittest.TestCase):
    """AC-7 (NFR1): the script and this test module import only the
    standard library, checked by parsing their import statements."""

    def test_import_check_flags_a_forged_third_party_import(self):
        # Negative proof: the check is capable of failing.
        self.assertEqual(_non_stdlib_imports("import os\nimport requests\n"), ["requests"])
        self.assertEqual(
            _non_stdlib_imports("from yaml import safe_load\nimport json\n"), ["yaml"]
        )
        self.assertEqual(_non_stdlib_imports("import os.path\nfrom json import loads\n"), [])

    def test_script_imports_only_the_standard_library(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("import os", source)  # the parsed text is the script
        self.assertEqual(_non_stdlib_imports(source), [])

    def test_this_module_imports_only_the_standard_library(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertIn("import unittest", source)  # the parsed text is this module
        self.assertEqual(_non_stdlib_imports(source), [])


if __name__ == "__main__":
    unittest.main()
