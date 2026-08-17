# Verification Document: stopguard-worktree-paths

## Overview

**Feature**: stopguard-worktree-paths /
**SPEC.md**: `feature-docs/stopguard-worktree-paths/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/stopguard-worktree-paths/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature.
Per-task acceptance criteria live in `tasks/task0001.md`,
`tasks/task0002.md` and `tasks/task0003.md`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the
  component is interpreted Python with no build step.
- Expected: not applicable; nothing is compiled or packaged in this
  repository.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors.
- Coverage target: none. No coverage tooling is configured for this project,
  so no minimum or target percentage is asserted.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Real-layout fixture, working directory = main tree root; implement step `in_progress`, two declared tasks, journal with no launched events | Exit 2; stderr BLOCK line names the feature, the free-slot count and both task ids ascending | Unit |
| TS2 | Same fixture, working directory = the integration-worktree directory | Identical exit code and identical stderr to TS1 | Unit |
| TS3 | Journal file deleted but its directory present; then the whole worktree-side feature directory absent | First: every task counts as unlaunched and the hook still blocks. Second: exit 0, no crash | Unit |
| TS4 | Freshness, four cases: (a) journal time now minus 25 hours, (b) journal time now, (c) no journal and `workflow.yaml` time now minus 25 hours, (d) no journal and `workflow.yaml` time now | (a) exit 0, (b) exit 2, (c) exit 0, (d) exit 2 | Unit |
| TS5 | Working directory is a temporary directory with no em-workflow worktrees directory anywhere above it | Exit 0, empty stderr, no exception | Unit |
| TS6 | `workflow.yaml` written only at the main-tree flat path with implement `in_progress`, no integration worktree present | Exit 0 — the flat layout is not an enumeration source | Unit |
| TS7 | Fixture-migration regression sweep across the eight pre-existing test classes | All pass with their intent unchanged; no test depends on the flat layout being enumerated | Integration |
| TS8 | Two features enumerated at once, both `in_progress` and both refillable | The first by stable ascending feature-name ordering is reported | Unit |
| TS9 | Standard-library-only assertion, plus absence of the repository-top-level probe and of any process spawn on the Stop path | Assertion passes; no external command reference remains in the hook | Static |
| TS10 | Enumerated-path ownership, three cases inside one integration worktree named `alpha`: (a) only a foreign `feature-docs/beta/workflow.yaml`, `in_progress` with unlaunched tasks; (b) both `feature-docs/alpha` (`task0001`, `task0002`) and `feature-docs/beta` (`task0007`–`task0009`), both `in_progress`; (c) own docs `completed` while the foreign docs read `in_progress` with unlaunched tasks | (a) exit 0, empty stderr; (b) exit 2 naming `alpha` with exactly `task0001`, `task0002` and no mention of `beta` or `task0007`–`task0009`; (c) exit 0, empty stderr and no `stop-guard-state.json` created | Unit |
| TS11 | Ambiguity refusal, exercised directly on the ownership + uniqueness selection step with hand-built match lists under a non-existent root | An identity carried by two admitted matches yields no entry at all while other identities survive in ascending order; without the duplicate the identity appears exactly once; a segment-mismatched match yields no entry; no filesystem access and no exception | Unit |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; no
  formatter is configured for this repository.
- Static analysis: the suite's own standard-library-only assertion (TS9) is the
  configured static check. No separate linter is configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Main-tree working directory resolves both files and emits the expected BLOCK line, exit 2 | TS1 |
| AC2 | Integration-worktree working directory produces the identical decision | TS2 |
| AC3 | A feature stale by more than 24 hours never blocks; the same feature fresh does block | TS4 (a), (b) |
| AC4 | Journal absent with fresh `workflow.yaml` stays active; journal absent with stale `workflow.yaml` is excluded | TS4 (d), (c) |
| AC5 | A flat-layout `workflow.yaml` is never enumerated and never blocks | TS6 |
| AC6 | Every previously existing hook behaviour is unchanged under the migrated fixture | TS7, plus TS3 |
| AC7 | No process is spawned on the Stop path; standard-library imports only | TS9 |
| AC8 | `python3 -m unittest discover -s tests` passes with the real-layout tests added | Test Verification command above |
| AC9 | Both manifests carry the same bumped version | Release check under Manual Verification |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS1, TS2, TS3 — the decision stage reads the enumerated path verbatim and reaches the journal through the same path's worktree-side ancestor; TS10 — the path it reads is the one the identity owns, not a foreign `feature-docs` directory in the same worktree |
| FR2 | task0001, task0003 | TS1, TS8 — enumeration from the main tree yields pairs and preserves stable feature-name ordering; TS10, TS11 — the enumerated set is restricted to owned paths and refuses an ambiguous identity |
| FR3 | task0001 | TS3, TS4 — freshness with journal time, fallback time, and the undecidable case |
| FR4 | task0001 | TS6, TS7 — the flat layout is not an enumeration source and the fixture has migrated off it |
| FR5 | task0001 | TS1, TS2, TS5, TS9 — ancestor walk resolves from both positions, misses silently, and spawns nothing |
| NFR1 | task0001 | TS9 — standard-library-only assertion |
| NFR2 | task0001, task0003 | TS3, TS5, plus the whole TS7 sweep — every abnormal condition still exits 0; TS10 (a), (c) and TS11 — the two exclusions added for ownership and ambiguity also fall to the non-blocking side |
| NFR3 | task0001 | TS9 for the no-subprocess half; the cost bound (one pattern expansion, one time-stamp read per candidate, no recursive scan) is confirmed structurally in review against IMPLEMENTATION.md D3 |
| NFR4 | task0001, task0003 | No SPEC test scenario. Verified by review as a blocking invariant, plus TS10 — the mixed-worktree probe that replaces task0001 AC-8's divergent-segment probe — see Gaps below |
| NFR5 | task0001 | TS7 for the preserved semantics; the untouched-hooks half is confirmed against the diff — the change set must contain no other hook file |
| NFR6 | task0002 | No SPEC test scenario. Verified by the release check under Manual Verification — see Gaps below |

### Coverage Gaps

- **NFR4** — no TS id covers the invariant itself. It is a structural
  invariant, not an observable behaviour, and the review phase treats it as
  blocking. TS10 is the closest automated proxy: case (b) fails if the hook
  reads a `workflow.yaml` other than the one its identity owns, whether
  because a path was rebuilt from an enumeration root plus a feature name or
  because an unowned match was taken. It replaces task0001 AC-8's
  divergent-segment probe, which asserted a block for a layout that
  task0003 excludes (IMPLEMENTATION.md D6).
- **NFR6** — no TS id and no automated check. Adding a manifest-parity unit
  test would widen SPEC's declared change set, so it is deliberately verified
  manually.

## E2E Testing

No E2E framework exists in this project and
`project.components.main.e2e_test_command` is empty. Nothing in this feature is
E2E-automatable: the hook's real trigger is a Claude Code Stop event, which the
unit tests already reproduce faithfully by invoking the script as a subprocess
with the same stdin payload.

## Manual Verification

- [ ] **Change-set containment** — the files changed by the merged feature are
      contained in SPEC's Declared Change Set:
      `em-workflow/hooks/queue_stop_guard.py`,
      `tests/test_queue_stop_guard.py`,
      `em-workflow/.claude-plugin/plugin.json`,
      `.claude-plugin/marketplace.json`, plus the
      `feature-docs/stopguard-worktree-paths/**` and
      `test-docs/stopguard-worktree-paths/**` defaults. In particular
      `queue_launch_guard.py`, `queue_failure_net.py` and
      `queue_taskstop_net.py` do not appear (NFR5).
- [ ] **Release check (AC9, NFR6)** — both manifests parse as JSON; the plugin
      manifest's version and the em-workflow marketplace entry's version are
      the identical string; that string is the pre-change value with its patch
      component incremented by one; no other key in either file changed.
- [ ] **Cache-refresh note** — the completion report tells the user that
      Claude Code must be restarted for the bumped plugin version to be served
      from the cache, without which the fix does not take effect (assumption
      a4).
- [ ] **Single-derivation read-through (NFR4)** — reading the merged hook,
      confirm that no path which is later opened is constructed by joining an
      enumeration root with a feature name, that the feature-docs wildcard
      segment is never read as feature identity, and that the ownership check
      compares two segments of the matched path rather than reconstructing one
      (IMPLEMENTATION.md D6).

No mockup comparison applies: the design step is `skipped` and the feature has
no visual surface.

## Performance / Security Verification

- **NFR3 (cost bound)**: per Stop, one pattern expansion over the layout
  pattern, one time-stamp read per candidate (plus the fallback read only when
  the journal file is absent), zero subprocesses, no recursive scan. Confirmed
  by reading the merged hook against IMPLEMENTATION.md D3 and by TS9's
  no-subprocess assertion.
- **Security**: the hook has no principal and no access-control surface. The
  relevant property is that no input is interpolated into a command, which
  holds trivially once the Stop path spawns no process at all (TS9). Malformed
  or hostile file content resolves to a silent exit 0 (TS3, TS5, TS7).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1–TS11) | 11 | 11 | 0 | 0 |
| Success criteria (AC1–AC9) | 9 | 8 | 0 | 1 |
| Requirements (FR1–FR5, NFR1–NFR6) | 11 | 9 | 0 | 2 |
| Manual verification items | 4 | 0 | 0 | 4 |
