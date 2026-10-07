# Verification Document: task-status-direct-key

## Overview
**Feature**: task-status-direct-key / **SPEC.md**: `feature-docs/task-status-direct-key/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier; the single task shares no file with another task) / **THREAT-MODEL.md**: `feature-docs/task-status-direct-key/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0; every scenario below passes
- Coverage target: not measured (no coverage tooling is configured for this component); completion is judged by the scenarios below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Stop hook run as a subprocess on a task block with no direct-child status key, a literal notes block scalar whose body holds `status: pending` deeper than the direct keys, a route-back record of journal line 1, and journal line 1 being that task's `failed` event | Exit code 0; no BLOCK on stderr | Integration |
| TS2 | The TS1 fixture plus a direct-child `status: failed` after the notes block scalar | Exit code 0; `task_statuses_from_workflow` returns `failed` for the task | Unit |
| TS3 | TS1 repeated with subTest for each block-scalar header form named in SPEC.md AC3 | Exit code 0 and no BLOCK for every form | Integration |
| TS4 | No direct-child status key; a nested mapping under a direct key holds `status: pending` | Task absent from the `task_statuses_from_workflow` result; exit code 0 with the TS1 record and journal | Unit |
| TS5 | TS1 record and journal; notes body holds `status: failed`; a direct-child `status: pending` placed before the notes block scalar, and separately after it | Exit code 2 in both cases; the task appears in `launch=` | Integration |
| TS6 | A comment line placed before the task block's first key, at an indentation different from the direct keys | Direct-child indentation unchanged; the direct `status: pending` is still read | Unit |
| TS7 | Whole suite via the test command above, including the three existing queue hook test files named in SPEC.md AC6, unmodified | All tests pass | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | SPEC.md AC1: a notes block-scalar body never supplies the status; the hook does not block | TS1 |
| AC2 | SPEC.md AC2: a direct `status: failed` after the notes block scalar is the status read | TS2 |
| AC3 | SPEC.md AC3: AC1 holds for the other block-scalar header forms | TS3 |
| AC4 | SPEC.md AC4: nested-mapping status lines are not read | TS4 |
| AC5 | SPEC.md AC5: a direct `status: pending` before or after the notes block scalar still blocks and names the task | TS5, TS6 |
| AC6 | SPEC.md AC6: the existing queue hook tests pass unchanged | TS7, plus the diff check under Manual Testing |
| AC7 | SPEC.md AC7: new tests sit under `tests/` as `test_*.py`, and the AC1 / AC2 / AC4 tests fail against the base revision's hook | Manual Testing item for AC7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS5, TS6 |
| FR2 | task0001 | TS1, TS2, TS3 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS5, TS6, TS7 |
| NFR1 | task0001 | TS7; import check under Manual Testing |
| NFR2 | task0001 | TS7; TM-2 check |
| NFR3 | task0001 | TS7 |
| NFR4 | task0001 | TS7 (existing module-docstring pin test) |
| NFR5 | task0001 | TS7; diff check under Manual Testing |

## Manual Testing (E2E Not Possible)
- [ ] NFR1: the import list of `em-workflow/hooks/queue_stop_guard.py` holds standard-library modules only and no YAML library.
- [ ] AC6 / NFR5: the diff from the base revision leaves the three existing queue hook test files, `iter_task_block_lines` and `task_routeback_records_from_workflow` unmodified.
- [ ] AC7: the new tests are `test_*.py` files under `tests/`, and the tests covering SPEC.md AC1, AC2 and AC4 fail when run against the base revision's hook.

## Performance / Security Verification
- TM-1: only lines at the task block's direct-child indentation are status candidates; block-scalar body lines and nested-mapping lines are never read — checked by TS1 and TS3 (a notes body `status: pending` does not trigger a block) and TS5 (a notes body `status: failed` does not mask a direct `pending`).
- TM-2: the status reader raises no uncaught exception on crafted task-block content and the hook stays fail-open — checked by the crafted-content tests of task0001 AC-5 (exit code 0, no traceback on stderr), run within TS7.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 7 | 7 | 0 | 0 |
| Success criteria | 7 | 6 | 0 | 1 |
| Manual checks | 3 | 0 | 0 | 3 |
| Security (TM-n) | 2 | 2 | 0 | 0 |
