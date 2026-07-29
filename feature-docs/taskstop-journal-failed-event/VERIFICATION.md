# Verification Document: TaskStop journal `failed` event

## Overview

**Feature**: taskstop-journal-failed-event /
**SPEC.md**: `feature-docs/taskstop-journal-failed-event/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/taskstop-journal-failed-event/IMPLEMENTATION.md`

## Build Verification

- Command: none (this repository has no build step; `project.components.main.build_command`
  is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors
- Coverage target: no numeric coverage gate is configured for this repository; the gate
  is that every acceptance criterion in the three task plans has at least one
  corresponding test.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Stop event for an implementer whose task's last journal event is `launched` | Exactly one `failed` line appended for that task; exit 0 | Unit |
| TS-2 | Stop event where the task's last journal event is `merged` | Nothing appended; exit 0 | Unit |
| TS-3 | Stop event where the task's last journal event is already `failed` | Nothing appended; exit 0 (idempotency) | Unit |
| TS-4 | Launch event for a non-implementer subagent | No agent-index entry; exit 0 | Unit |
| TS-5 | Stop event whose agent identifier is absent from every agent index | Nothing appended; exit 0 | Unit |
| TS-6 | Journal directory absent for the derived path | Nothing appended; no file or directory created; exit 0 | Unit |
| TS-7 | Malformed JSON on standard input, for each new hook | Exit 0; no output; no file writes | Unit |
| TS-8 | Index entry carrying an invalid task identifier, a relative worktree path, or a `..`-containing path | Nothing appended; exit 0 | Unit |
| TS-9 | Appended journal line's field shape | Contains event name, task identifier, RFC 3339 timestamp with offset, and reason | Unit |
| TS-10 | Three tasks `launched`; stop event for one of them | Only that task gains `failed`; the other two remain `launched` | Integration |
| TS-11 | Recorder appends `failed`, then the launch guard is fed a launch for the same task | Guard emits no deny decision and appends `launched` — retry path open | Integration |
| TS-12 | Existing `SubagentStop` failure-net behavior | `tests/test_queue_failure_net.py` passes unmodified | Integration |
| TS-13 | Hook manifest after both hook tasks merge | Manifest parses; every registered hook's script exists, uses the plugin-root-relative `python3` command form, and carries the standard timeout | Integration |
| TS-14 | Concurrent index appends for two tasks in one feature | Both entries present; every line parses as JSON | Integration |
| TS-15 | Agent identifier recovered from each accepted payload layout (structured field / embedded in text), on both new hooks | Entry written / `failed` appended respectively; exit 0 | Unit |
| TS-16 | Two index entries for the same agent identifier | The last entry determines the task | Unit |
| TS-17 | Reason strings of the two `failed` writers | The recorder's reason differs from the failure net's reason | Unit |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured; no linter is installed in this environment

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | After a stop-tool stop of an implementer, the journal holds a `failed` event for that task | TS-1, and manual item MV-1 for the live path |
| SC-2 | A develop re-entry after such a stop is not denied by the launch guard | TS-11, and MV-1 |
| SC-3 | The orchestrator never writes the journal | Review the diff: no journal write appears outside `merge-task.sh` and `em-workflow/hooks/` |
| SC-4 | The existing `SubagentStop` failure net is unchanged | TS-12, plus a diff check that `queue_failure_net.py` has no behavioral edit |
| SC-5 | Documentation matches the implemented writer set | Read `implement-phase.md` and `workflow-schema.md` against the merged hook manifest (task0003 AC-1..AC-5) |
| SC-6 | All hooks stay fail-open | TS-7 for each new hook, plus every negative-path scenario asserting exit 0 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0003 | No automated test (documented gap): the investigation's deliverable is a recorded finding. Verified by reading IMPLEMENTATION.md's investigation table and task0003 AC-2 |
| FR2 | task0002 | TS-1, TS-9, TS-17 |
| FR3 | task0001, task0002 | TS-15, TS-16, TS-5 |
| FR4 | task0002 | TS-2, TS-3 |
| FR5 | task0001, task0002 | TS-4, TS-5, TS-6, TS-7, TS-8 |
| FR6 | task0001, task0002, task0003 | TS-13 |
| FR7 | task0003 | Documentation read-through (task0003 AC-1..AC-5) |
| NFR1 | task0001, task0002 | TS-7; every negative scenario asserts exit 0 |
| NFR2 | task0001, task0002 | TS-8; symlink-refusing open asserted in the hook tests |
| NFR3 | task0001, task0002, task0003 | Full suite passes on Python 3.14 with no third-party import in the diff |
| NFR4 | task0001, task0002 | TS-10, TS-14 |
| NFR5 | task0001, task0002, task0003 | Test files exist under `tests/` and run via the project test command |

## E2E Testing

No E2E framework exists in this repository. The live hook path cannot be exercised
automatically, because hook registrations are read at session start — a session that
adds a hook cannot fire it.

## Manual Testing (E2E Not Possible)

- [ ] MV-1 (**required before this feature can be trusted in production**): in a FRESH
      Claude Code session started after these changes are installed, run
      `/em-workflow:develop` on any feature, launch an implementer, stop it with
      `TaskStop`, then inspect that feature's `journal.jsonl`. Expected: a `failed`
      event for the stopped task, carrying the recorder's reason string. Then re-enter
      `/em-workflow:develop` and confirm the task relaunches without the launch guard's
      "すでに実行中" denial.
- [ ] MV-2: inspect the same feature's agent index and confirm one entry per implementer
      launch, each carrying a resolvable agent identifier.
- [ ] MV-3: confirm that a normally-completing implementer still produces exactly one
      `failed` (or `merged`) event and no duplicate — i.e. the two writers do not both
      fire for one stop.

If MV-1 fails, the payload-shape tolerance in IMPLEMENTATION.md D3 did not match the
harness's actual layout. The failure is safe (behavior equals today's) but the feature
is not delivering its purpose; the correct response is a follow-up task carrying the
observed payload, not a change to the launch guard.

## Performance / Security Verification

- NFR2: journal and agent-index opens use the symlink-refusing flag; assert that a
  symlink planted at either path results in no write and exit 0.
- NFR4: journal appends and index appends hold an exclusive whole-file lock; asserted
  by TS-14 and by the existing lock-discipline pattern in
  `tests/test_queue_launch_guard.py`.
- No hook in this feature executes a subprocess or interpolates hook input into a
  shell; verify by reading the diff.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 17 | 17 | 0 | 0 |
| Success criteria | 6 | 4 | 0 | 2 (SC-1, SC-2 also need MV-1) |
| Manual verification | 3 | 0 | 0 | 3 |
