# Verification Document: final-path-plan-binding

## Overview
**Feature**: final-path-plan-binding / **SPEC.md**: `feature-docs/final-path-plan-binding/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/final-path-plan-binding/IMPLEMENTATION.md`

This document covers the integrated verification run by the verify phase.
Task-level criteria live in `tasks/task0001.md` to `tasks/task0003.md`.

## Build Verification
- Command: none (`build_command` of the `main` component is empty).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failure and no error.
- Coverage: not measured (standard library only); every scenario below maps
  to at least one test or check.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Attack reproduction: a decoy plan `tasks/task0003-safe.md` with the canonical text and an unregistered `tasks/task0003.md` with other text, on the correction entry | `path-correction-entries` with `task_id` `task0003` and path `tasks/task0003.md`, through `validate_workflow_patch` (dry run) and through `validate_worker_result` | Unit |
| TS-2 | Bound plan: plan `tasks/{T}.md` with the canonical text, no other plan file | No error | Unit |
| TS-3 | Free plan path with nothing at `tasks/{T}.md` | No new error; the existing TestCreatedDocuments and TestEntryLimits tests pass unchanged | Unit |
| TS-4 | `tasks/{T}.md` as a directory, a dangling symlink, a symlink to a file, a regular file beside a `TASK.md` plan, and an indeterminate lookup | Rejected with `path-correction-entries` naming `tasks/{T}.md` | Unit |
| TS-5 | Plan spellings that normalize to `tasks/{T}.md` (leading `./`, doubled separator, `.` segment, backslash) | Treated as bound; no error | Unit |
| TS-6 | Re-planning path (both cases) and patches without `path_corrections` | The binding check does not run; no binding error | Unit |
| TS-7 | Docs: `implement-phase.md` resolves `task_plan_path` from `tasks.{T}.plan`, states the Plan-path check and its abort; section 2a of `phases/create-plan-phase.md` states the stored value and the resolved path separately | The docs tests pass; each matcher fails on its pre-change or forged sample | Integration |
| TS-8 | Code read: `_correction_entries_errors` and its binding helper reach git only through the base readers | The existing code-read test of TestEntryLimits and the new code-read test pass | Integration |
| TS-9 | Docs: `batch-terminal-line.md` binds the Plan-path check stop to the `stop-condition-3` row and `step_needs_intervention` | The docs test passes; the "Precedence rule:" paragraph is unchanged; the coverage table keeps fourteen rows | Integration |
| TS-10 | Docs: the `path-correction-entries` bullet of `workflow-patch.md` states the binding rejection | The docs test passes and fails on the pre-change bullet; every `LIMITS_NEEDLES` string stays | Integration |
| TS-11 | Module hygiene: `tests/test_final_path_correction.py` and `tests/test_final_path_correction_docs.py` import only the standard library | The hygiene test passes and its negative proof fires on a forged third-party import | Unit |
| TS-12 | Version fields: the change set of the feature against `implement.base_commit` | No file under any `.claude-plugin/` directory is changed | Manual |
| TS-13 | The `failed_kind` Required-ness paragraph of `workflow-schema.md` counts the Plan-path check stop as a write path | The refreshed byte-identical capture test passes | Integration |

## Code Quality Verification
- Format: none (`format_command` is empty). Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The attack reproduction yields `path-correction-entries` naming `task0003` and `tasks/task0003.md` through both entry points | TS-1 |
| AC-2 | A bound plan yields no error; a free plan path without `tasks/{T}.md` yields no new error | TS-2, TS-3 |
| AC-3 | A `TASK.md` plan beside an existing `tasks/{T}.md`, a directory and a dangling symlink at `tasks/{T}.md` are rejected | TS-4 |
| AC-4 | The payload gives `task_plan_path` from `tasks.{T}.plan`; the fixed `tasks/{T}.md` payload text is gone | TS-7 |
| AC-5 | `implement-phase.md` states the Plan-path check over each selected task and its abort before any launch prompt is built | TS-7 |
| AC-6 | The `path-correction-entries` bullet states the binding rejection; the existing docs tests pass | TS-10, TS-3 |
| AC-7 | `python3 -m unittest discover -s tests` passes | Test Verification command |
| AC-8 | `batch-terminal-line.md` binds the Plan-path check stop to the `stop-condition-3` row and `step_needs_intervention` | TS-9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR2 | task0003 | TS-7 |
| FR3 | task0003 | TS-7, TS-13 |
| FR4 | task0002 | TS-10 |
| FR5 | task0001, task0003 | TS-1, TS-2, TS-3, TS-4, TS-7 |
| FR6 | task0003 | TS-9 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-4 |
| NFR3 | task0001, task0002, task0003 | TS-11 |
| NFR4 | task0001, task0002, task0003 | TS-12 |
| NFR5 | task0001, task0002, task0003 | TS-3 and the full test command |

## Manual Testing (E2E Not Possible)
- [ ] TS-12: list the files changed between `implement.base_commit` and the
  integration branch tip with a read-only git command, and confirm that none
  is under a `.claude-plugin/` directory.

## Performance / Security Verification (if applicable)
- TM-1: a correction-entry item whose plan is not `tasks/{T}.md` while an entry exists at `tasks/{T}.md` is rejected as `path-correction-entries` — checked by TS-1 and TS-4.
- TM-2: a dangling symlink, an indeterminate lookup and a key that is not a task id count as existing — checked by TS-4 and the non-task-id case of task0001's tests.
- TM-3: the binding reads the working tree only and starts no process — checked by TS-8.
- TM-4: `task_plan_path` comes from `tasks.{T}.plan` and the payload names no fixed `tasks/{T}.md` — checked by TS-7.
- TM-5: the Plan-path check requires a safe relative path, no symlink among the components and realpath containment in `feature-docs/{feature}` — checked by TS-7.
- TM-6: the Plan-path check rejects Cc, U+2028 and U+2029 in the stored and the resolved value — checked by TS-7.
- TM-7: a failing value aborts the phase with no launch prompt for any selected task, no repair, no fallback to `tasks/{T}.md` and one `failed` / `decision` write — checked by TS-7.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 13 | 12 | 0 | 1 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 8 | 8 | 0 | 0 |
| Requirements coverage | 11 | 10 | 0 | 1 |
| Security (TM-n) | 7 | 7 | 0 | 0 |
