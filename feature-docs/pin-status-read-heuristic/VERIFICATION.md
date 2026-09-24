# Verification Document: pin-status-read-heuristic

## Overview

**Feature**: pin-status-read-heuristic / **SPEC.md**: `feature-docs/pin-status-read-heuristic/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/pin-status-read-heuristic/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the change is a Python test module with no build step)
- Expected: not applicable. Import-time errors surface in Test Verification.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Focused command: `python3 -m unittest discover -s tests -p test_hook_classification_pin.py`
- Expected: the focused run exits with code 0; the full run ends with no new failures compared with the base revision.
- Coverage target: not measured (no coverage tooling in the project; test code is standard-library only). Coverage is judged by the scenario and requirement mapping below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1) Synthetic hook in a temporary file: helper `pending_from_workflow` builds a workflow.yaml path, opens it, extracts each task's status with a line-anchored regular expression for an indented status key, and is called from another function. One row classifying its absolute path as not reading per-task status is passed to `compare_table_to_sources` | Exactly one mismatch: (that path, `DOES_NOT_READ_STATUS`, `READS_STATUS`) | Unit |
| TS-2 | (SPEC TS2) The same synthetic source as TS-1 | `reads_per_task_status` returns True | Unit |
| TS-3 | (SPEC TS3) Synthetic source that defines and calls `statuses_from_workflow`, builds the workflow.yaml path and reads status | `reads_per_task_status` returns True | Unit |
| TS-4 | (SPEC TS4) Synthetic source that builds a workflow.yaml path and holds status only as uppercase STATUS; lowercase status appears nowhere in its executable code | `reads_per_task_status` returns False | Unit |
| TS-5 | (SPEC TS5) Synthetic source that builds a workflow.yaml path and defines a helper reading status with an indented-status-key regular expression, never called | `reads_per_task_status` returns True | Unit |
| TS-6 | (SPEC TS6) Pre-existing `TestHookClassificationPin`, `TestPinIsNotAVacuousCheck` and `TestObserveHookSource` run under the new rule | All pass with unchanged expected outcomes; queue_stop_guard.py observed True, queue_launch_guard.py / queue_failure_net.py / queue_taskstop_net.py / bash_guard.py observed False | Unit |
| TS-7 | (SPEC AC7) Search `tests/test_hook_classification_pin.py` for `_TASK_STATUS_NAME_RE`, `task_status_fn_names`, `called_names`, and for imports left unused by their removal | No occurrence of the three names; no unused import (`re` is gone unless still used) | Static check |
| TS-8 | (SPEC AC8) Read the `reads_per_task_status` docstring, module docstring item 2 and the pre-existing test comments | The function docstring states the substring co-occurrence approximation (not a proof) and the queue_stop_guard.py limitation (`STEP_STATUS_RE` / `implement_in_progress`); no text still describes the accessor-name/call rule | Manual |
| TS-9 | (NFR3) Read the observation rule and count the test methods of `TestHookClassificationPin` | A single rule with no per-hook branch; `TestHookClassificationPin` has exactly one test method | Manual |
| TS-10 | (NFR4) Diff the integration branch against `workflow.implement.base_commit` | Outside `feature-docs/pin-status-read-heuristic/` and `test-docs/pin-status-read-heuristic/`, only `tests/test_hook_classification_pin.py` changed; no plugin.json or marketplace.json change | Static check |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured
- Import check: the module imports standard-library modules only (NFR1), confirmed by reading its import statements

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A synthetic hook reading per-task status through a helper whose name lacks the task/status co-occurrence, classified as not reading, yields one mismatch | TS-1 |
| AC2 | The five real hooks are observed as before; the pin test on the implemented Hook classification table passes | TS-6 |
| AC3 | A test pins True for a status read whose helper name does not match the removed rule | TS-2 |
| AC4 | The helper renamed to `statuses_from_workflow` is still observed True | TS-3 |
| AC5 | workflow.yaml plus uppercase-only STATUS is observed False | TS-4 |
| AC6 | workflow.yaml plus an uncalled status-reading helper is observed True | TS-5 |
| AC7 | `_TASK_STATUS_NAME_RE`, `task_status_fn_names`, `called_names` are gone | TS-7 |
| AC8 | The `reads_per_task_status` docstring states the approximation and the queue_stop_guard.py limitation | TS-8 |
| AC9 | Pre-existing tests pass and the full suite ends with no new failures | TS-6 plus the full-suite command above |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4, TS-5, TS-6 |
| FR2 | task0001 | TS-7 |
| FR3 | task0001 | TS-6 |
| FR4 | task0001 | TS-2 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-3 |
| FR7 | task0001 | TS-4 |
| FR8 | task0001 | TS-5 |
| FR9 | task0001 | TS-8 |
| NFR1 | task0001 | TS-6, import check |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-9 |
| NFR4 | task0001 | TS-10 |

## Manual Testing (E2E Not Possible)

- [ ] TS-8: read the rewritten docstrings and comments and confirm the stated approximation, the queue_stop_guard.py limitation, and the absence of the accessor-name/call rule description
- [ ] TS-9: confirm the observation rule has no per-hook branch and `TestHookClassificationPin` still has one test method

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Static checks (TS-7, TS-10) | 2 | 2 | 0 | 0 |
| Manual reading (TS-8, TS-9) | 2 | 0 | 0 | 2 |
| Total | 10 | 8 | 0 | 2 |
