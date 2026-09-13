# Verification Document: stale-launched-retry-recovery

## Overview

**Feature**: stale-launched-retry-recovery /
**SPEC.md**: `feature-docs/stale-launched-retry-recovery/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/stale-launched-retry-recovery/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature.
Per-task acceptance criteria live in `tasks/task000N.md` and are verified by
the implementer.

## Build Verification

- Command: none — `project.components.main.build_command` is empty (a Python
  plugin distributed as source; there is no build step).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root).
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: no numeric coverage gate is configured for this project.
  The substitute gate is scenario coverage: every TS below has at least one
  test and every FR/NFR maps to at least one TS.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Recovered path end to end against an injected stub helper: journal last event `launched`, launch-bound agent index entry recording the current identity, both evidence conjuncts proving | stdout is one JSON line with outcome `recovered`, task id, empty reason; exit 0; the stub is invoked exactly once with the task id, reason `stale-launched` and the launch identity | Integration |
| TS2 | Reason-code table, one case per unmet condition of the fixed evidence order | Each case reports the exact residual reason string and leaves the journal byte-identical | Unit |
| TS3 | Insufficient-evidence pins: launch-acceptance only, generic error only, output-idle only, and a very old launch timestamp | `agent-termination-unproven` in all four cases; no elapsed-time threshold exists anywhere in the chain | Unit |
| TS4 | The recorded session identity is never a stop target, even when it coincides with a harness agent-identifier candidate | Outcome `agent-identity-unproven`; no stop target derived from that field; pinned at source level and behaviour level | Unit |
| TS5 | In-lock launch-identity race: the last `launched` event changes between the decision and the append; plus N concurrent invocations carrying the same launch identity | No append and the mismatch outcome for the race; at most one `failed` line total for the concurrent run | Unit |
| TS6 | Closed reason set widened: exactly `orphaned` and `stale-launched` accepted; `manual`, empty and missing rejected; the new value appends with the pinned field order | Membership assertion passes on exactly two values; unknown values exit non-zero with no write | Unit |
| TS7 | Retry reachability: the launch guard driven as a subprocess against a journal whose last event is a `failed` with reason `stale-launched`, and against `launched` and `merged` journals | Allow plus exactly one appended `launched` line in the first case; deny with no append in the other two | Integration |
| TS8 | Documentation contract: the I.2.b Orphan recovery block, the Stale-`launched` caveat, the abort-phase bullet and the writer-set paragraph | The six new codes present in the fixed order, both conjuncts stated, the caveat covering the no-subagent-stop / no-stop-tool stop, the new reason value named additively, the writer set unchanged | Integration |
| TS9 | Hook classification and status-read pins | `tests/test_hook_classification_pin.py` and `tests/test_queue_hook_status_read_pin.py` pass unmodified | Integration |
| TS10 | Version parity: both version fields bumped to the same new value | Manifest and marketplace entry equal, strictly greater than the `0.1.77` baseline at the patch component | Unit |

## Code Quality Verification

- Format: none configured — `project.components.main.format_command` is
  empty. Follow the surrounding file's existing style instead.
- Static analysis: none configured. The substitute check is the plugin
  invariant test suite already inside the discovered `tests/` run
  (`tests/test_check_plugin_invariants.py`, `tests/test_reference_sweep.py`).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The fully-evidenced same-session case reaches `recovered` with exactly one `failed` line carrying reason `stale-launched` and the pinned field order | TS1 plus the integrated pair run below |
| AC2 | After AC1 the launch guard allows the relaunch and appends exactly one `launched` line | TS7 |
| AC3 | Harness reporting the launch still running → `agent-still-live`, journal byte-identical, no helper invocation | TS2 |
| AC4 | Launch-acceptance only, generic error only, output-idle only → `agent-termination-unproven` each | TS3 |
| AC5 | Termination proven but stop result a generic error, or about a different target → `stop-result-unproven` | TS2, TS3 |
| AC6 | Identity not uniquely bound → `agent-identity-unproven`; the session identity is never the stop target | TS2, TS4 |
| AC7 | Worktree or branch absent → `task-artifacts-missing`, decided before any agent index read or file open | TS2 |
| AC8 | A newer `launched` between the decision and the in-lock check → no append and `launch-changed`; an event-name-only comparison fails this | TS5, TS2 |
| AC9 | An existing writer already wrote a terminal event → `noop_terminal` with empty reason, nothing appended | TS2 |
| AC10 | Every residual and every `noop_terminal` leaves the journal byte-for-byte identical and creates neither file nor parent directory | TS2, TS5, TS6 |
| AC11 | An invocation supplying no new evidence inputs still reports `same-session` | TS2 (its FR5 case) |
| AC12 | Unknown `--reason` still rejected non-zero with no write; the closed set is exactly the two values | TS6 |
| AC13 | The launch guard's source is unchanged and its three behaviours are re-proven | TS7, plus the change-set check below |
| AC14 | The three documentation sites name the new reason value and the new codes, with the writer set unchanged | TS8 |
| AC15 | Both version fields equal and strictly greater than `0.1.77` | TS10 |
| AC16 | The discovered test suite passes from the repository root | The Test Verification command above |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS2 (existing codes unchanged), TS1 |
| FR2 | task0002 | TS1, TS3, TS4 |
| FR3 | task0001, task0002 | TS1, TS2, TS3, TS4 |
| FR4 | task0002 | TS2 |
| FR5 | task0002 | TS2 |
| FR6 | task0001 | TS5 |
| FR7 | task0001 | TS1, TS6 |
| FR8 | task0004 | TS7, TS9 |
| FR9 | task0001, task0002 | TS2, TS5, TS6 |
| FR10 | task0003 | TS8 |
| FR11 | task0004 | TS10 |
| FR12 | task0003 | TS8 |
| FR13 | task0001, task0002, task0003, task0004 | TS1-TS10 |
| NFR1 | task0001, task0002 | TS2, TS3 |
| NFR2 | task0001 | TS5 |
| NFR3 | task0001, task0002 | TS1 |
| NFR4 | task0004 | TS9 |
| NFR5 | task0001, task0002 | TS2 |
| NFR6 | task0001, task0002, task0003, task0004 | TS1 (stdlib-only assertions in each new module) |

## E2E Testing

**Existing E2E framework**: none — `project.components.main.e2e_test_command`
is empty. The discovered `unittest` run is the only automated gate.

- [ ] `python3 -m unittest discover -s tests` passes from the repository root
      (AC16).

## Manual Testing (E2E Not Possible)

The one check no single task's worktree can perform, because every task is
implemented in isolation and no worktree contains a sibling task's code
(IMPLEMENTATION.md D-F). Run it on the integrated tree.

- [ ] **Integrated pair run (AC1)**: in a throwaway temporary directory,
      create a journal containing one `launched` event for a test task id and
      an agent index file containing one matching entry whose timestamp binds
      to that launch, whose candidate list holds exactly one identifier,
      whose worktree path is the one to be supplied, and whose session
      identity equals the current-session identity to be supplied. Invoke
      `em-workflow/scripts/recover-orphaned-task.py` with those two paths,
      the task id, the current-session identity and start, both
      artifact-presence inputs proving, the worktree path, the bound
      identifier as the stop target and as the stop-result target, the
      termination token proving termination, and the stop-result token
      proving not-running — with NO helper override, so the real sibling
      helper is used. Confirm: stdout is one JSON line with outcome
      `recovered` and an empty reason; exit code is 0; the journal gained
      exactly one line; that line's fields are `event`, `task`, `at`,
      `reason` in that order, with `event` `failed` and `reason`
      `stale-launched`.
- [ ] **Residual pair run (AC3, AC10)**: repeat the run above with only the
      termination token changed to the still-running value. Confirm outcome
      `residual` with reason `agent-still-live`, exit code 0, and a journal
      byte-for-byte identical to its pre-call content.
- [ ] **Change-set check (AC13, FR8)**: confirm the integrated diff against
      the feature's base contains no hunk touching
      `em-workflow/hooks/queue_launch_guard.py` or any other file under
      `em-workflow/hooks/`.

## Performance / Security Verification

- Performance: not applicable — no performance goal is specified.
- Security (input validation): the recorded session identity is validated by
  the existing format rule before use and is never the stop target — TS4.
- Security (data protection): the journal must already exist, its parent
  directory is never created, the path must not be a symbolic link, and the
  open refuses to follow one — re-proven by the pre-existing precondition
  tests in `tests/test_journal_append_failed.py` continuing to pass.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS10) | 10 | 10 | 0 | 0 |
| Success criteria (AC1-AC16) | 16 | 15 | 0 | 1 (AC1 also has an integrated manual run) |
| Functional requirements (FR1-FR13) | 13 | 13 | 0 | 0 |
| Non-functional requirements (NFR1-NFR6) | 6 | 6 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
