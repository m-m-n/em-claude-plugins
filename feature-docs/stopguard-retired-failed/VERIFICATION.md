# Verification Document: stopguard-retired-failed

## Overview

**Feature**: stopguard-retired-failed /
**SPEC.md**: `feature-docs/stopguard-retired-failed/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/stopguard-retired-failed/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature branch.
Per-task completion is governed by the Acceptance Criteria in
`feature-docs/stopguard-retired-failed/tasks/task0001.md` and
`feature-docs/stopguard-retired-failed/tasks/task0002.md`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the
  repository ships Python scripts, Markdown and JSON, with no build step.
- Expected: not applicable. The closest equivalent is that both registry
  files parse as JSON, asserted inside the test suite (TS10).

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root, i.e. the integration worktree root).
- Expected: exit code 0, no failures and no errors.
- Coverage target: no coverage tooling is configured for this repository. The
  binding target is scenario coverage — every scenario below passes, and no
  pre-existing test regresses.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Retired id: implement in progress, three declared tasks all at status `pending`, journal contains only a `failed` event for the first task | Hook exits 2; stderr names all three task ids in ascending order in the existing BLOCK format | Unit |
| TS2 | Genuine failure: the same shape, but the failed task's workflow status is `failed` | Hook exits 0 | Unit |
| TS3 | Unreconciled failure: the failed task's workflow status is `in_progress` | Hook exits 0 | Unit |
| TS4 | Mixed: one retired id (`pending` + journal `failed`) and one genuine failure (`failed` + journal `failed`) | Hook exits 0 | Unit |
| TS5 | Retired id alongside in-flight tasks | Free-slot arithmetic against the parallel-implementer limit and the ascending bounded launch list are both still correct | Unit |
| TS6 | Retired id then relaunched: journal `failed` followed by `launched`, workflow status `pending` | Counted as in-flight, not unlaunched | Unit |
| TS7 | Per-task status key absent, unrecognized, or task block undeterminable, with journal `failed` | Hook exits 0, no traceback | Unit (edge case) |
| TS8 | Retired id no longer declared under the `tasks:` mapping | The id is ignored entirely; the remaining tasks are still evaluated | Unit (edge case) |
| TS9 | Consecutive-block cap over a retired-id-derived block state | Blocks three times, then warns and exits 0; a derived-state change re-arms blocking | Integration |
| TS10 | Regression sweep: the whole suite from the repository root | All modules pass, including the pre-existing hook, document-literal and registry-invariant modules | Integration |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; no
  formatter is configured for this repository.
- Static analysis: none configured. The stdlib-only import assertion inside
  the hook's own test module is the standing structural check (NFR2), and it
  runs as part of TS10.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Retired-id case exits 2 and names the three task ids | TS1 |
| AC2 | Genuine failure (`failed`) exits 0 | TS2 |
| AC3 | `in_progress` plus journal `failed` exits 0 | TS3 |
| AC4 | Mixed retired plus genuine exits 0 | TS4 |
| AC5 | Fail-open intact across missing journal directory, malformed journal line, malformed stdin, missing feature-docs, and undeterminable per-task status — each exits 0 without a traceback | TS7 and TS10 (the fail-open scenarios live in the hook's own module) |
| AC6 | The SSOT document no longer claims the Stop hook never consults the per-task status, and still claims it for the other three hooks | M1 (document read) plus TS10 for the retained literals |
| AC7 | Both registries read version 0.1.42 | M2 (direct file read) plus TS10 for the durable invariants |
| AC8 | The suite passes with no regression in the pre-existing hook tests | TS10 |
| SC-extra | The other three queue hooks are unmodified | M3 (change-set inspection) plus TS10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS4, TS6 |
| FR2 | task0001 | TS2, TS3, TS4, TS7 |
| FR3 | task0001 | TS7 (plus the scoping assertion inside TS1's fixture, which carries both step and task status lines) |
| FR4 | task0001 | TS1, TS5, TS6, TS9 |
| FR5 | task0001 | TS8 |
| FR6 | task0002 | TS10 for the retained document literals; M1 for the amended wording itself |
| FR7 | task0001 | TS10; M3 for the byte-unchanged assertion |
| FR8 | task0001 | TS10 (the new scenarios are the module's own content) |
| FR9 | task0002 | TS10 for the durable version invariants; M2 for the literal 0.1.42 |
| NFR1 | task0001 | TS7, TS10 |
| NFR2 | task0001 | TS10 (the stdlib-only import assertion) |
| NFR3 | task0001 | M4 (inspection: the hook still reads only the journal and workflow.yaml, and writes only its existing sidecar) |
| NFR4 | task0001 | M5 (inspection: one line-based pass per file, no added subprocess, network call or filesystem scan) |

## E2E Testing

The repository has no E2E framework and no E2E command
(`project.components.main.e2e_test_command` is empty). The hook's own tests
already exercise it end to end as a subprocess with real files, which is the
closest available equivalent; no separate E2E layer is added.

## Manual Testing (E2E Not Possible)

- [ ] M1 (FR6, AC6): read the amended section I.2.a of
      `em-workflow/references/implement-phase.md` and confirm it names the
      Stop hook as the explicit exception, still states the
      journal-last-event-only and never-consult claims for the other three
      hooks, and that the supporting-cast Stop-hook bullet agrees with it.
- [ ] M2 (FR9, AC7): read `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` and confirm both literally read
      version 0.1.42.
- [ ] M3 (FR7): inspect the integrated change set and confirm it is contained
      in SPEC.md's declared change set, and in particular that
      `queue_launch_guard.py`, `queue_failure_net.py` and
      `queue_taskstop_net.py` and every test module other than
      `tests/test_queue_stop_guard.py` are byte-unchanged.
- [ ] M4 (NFR3): confirm by reading the hook that it opens only the journal
      and workflow.yaml for reading and writes only its existing sidecar,
      still through the atomic temp-file-then-replace technique.
- [ ] M5 (NFR4): confirm by reading the hook that per-task status collection
      stays within the existing single line-based pass family and adds no
      subprocess, network call or filesystem scan.

## Performance / Security Verification

- NFR4 (bounded hook latency): no numeric target. Satisfied structurally and
  checked by M5.
- Security: no dedicated scenario. The hook performs local reads only; its
  sidecar write keeps the existing atomic technique, which never follows a
  pre-planted symlink and never truncates an existing target (M4).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 10 | 10 | 0 | 0 |
| Success criteria | 9 | 6 | 0 | 3 |
| Requirements (FR1–FR9, NFR1–NFR4) | 13 | 11 | 0 | 2 |
| Manual checks | 5 | 0 | 0 | 5 |
