# Implementation Plan: merge-task-parent-symref-reject

## Overview
merge-task.sh rejects (exit 2) an integration ref `refs/heads/<parent-branch>`
that is a symbolic ref, checked once under the merge lock before the parent
value is read, and passes the no-deref option to both of its update-ref calls.
A single task (task0001) delivers the script change, its content pin and the
integration tests.

## Technology Stack
- **Language / Framework**: Bash (existing `em-workflow/scripts/merge-task.sh`);
  git >= 2.40 (existing requirement of the script — the quiet symbolic-ref
  query and the update-ref no-deref option are pre-existing git features).
- **Tests**: Python 3 `unittest`, standard library only (test/README.md).
- **New dependencies**: none. `project.license` is `none`, so there is no
  license constraint and no dependency license to record.

## Layer Structure
- **Script**: `em-workflow/scripts/merge-task.sh` — distributed with the
  em-workflow plugin.
- **Tests**: `tests/` at the repository root — not distributed; drives the
  script as a subprocess against throwaway repositories.

Dependency direction: tests → script only.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| — | — | — | — |

None: the feature is one task, so no component crosses a task boundary.

## Conventions
- **Error policy**: every new rejection goes through the script's existing
  error helper — one `ERROR:` line on stderr, exit 2 — and happens before any
  update-ref, merge-tree, commit-tree or journal append. The meanings of
  exit 0 / 1 / 2 do not change (NFR1).
- **Content pin**: any commit that changes merge-task.sh also sets
  `EXPECTED_MERGE_TASK_SH_SHA256` in
  `tests/test_merge_unverified_exit_doc_contract.py` to that commit's script
  sha256 (FR6).
- **Tests**: standard library only; throwaway repositories under a temporary
  directory; merge-task.sh run as a subprocess; no kill / pkill; changes made
  during the lock wait go through the existing
  `_run_merge_with_mutation_during_lock_wait` helper (NFR2, NFR4).
- **Plugin version**: this repository is exempt from per-commit version
  bumps; the plugin version fields are in no task's file set (NFR3).

## Cross-task Design Decisions

### D1. One task for the script, its pin and its tests
- **Decision**: task0001 owns every change of this feature.
- **Rationale**: FR6 requires the content pin to change in the same commit as
  the script; TS-8 (FR7) passes only with the script change in place. Tasks
  run in parallel with no ordering, so splitting the script from its tests —
  or FR1 from FR7, which both change the script and therefore the same pin
  value — would leave a task whose tests cannot pass in its own worktree, or
  two tasks writing competing values into the same pin.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The quiet symbolic-ref query returns a status other than 0 / 1 for an ordinary direct ref on some setup (e.g. packed refs) | Low | Ordinary merges rejected with exit 2 | Fail-closed is the required direction (FR2); the existing suite (TS-6) exercises ordinary direct refs |
| update-ref with the no-deref option replaces a symbolic ref planted after the check with a direct ref | Medium (only under an active re-point) | The integration name becomes a direct ref; the referent does not move | Accepted (SPEC.md Assumptions); TS-8 asserts only that the referent is unmoved |
| The test-only git shim leaks into the test's own git calls | Low | Misleading test results | The shim environment is passed only to the merge-task.sh subprocess (task0001 Design) |
| Lock-wait tests are timing-sensitive | Low | Intermittent failures | Reuse the existing helper that synchronizes on the waiting flock child |
| A commit changes merge-task.sh without updating the pin | Medium | Pin test fails | Content-pin convention above; TS-6 |
| Re-point between the check and the already-contained ancestor check | Low | A false `merged` record by a party that can already write refs | Out of scope (REQUIREMENTS.md 14.1); recorded as an accepted residual in THREAT-MODEL.md |

## Open Questions
- None
