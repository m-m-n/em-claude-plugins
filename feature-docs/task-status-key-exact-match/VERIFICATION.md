# Verification Document: task-status-key-exact-match

## Overview
**Feature**: task-status-key-exact-match / **SPEC.md**: `feature-docs/task-status-key-exact-match/SPEC.md` / **IMPLEMENTATION.md**: none (reduced tier; a single task, so no file is declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/task-status-key-exact-match/THREAT-MODEL.md`

## Build Verification
- Command: none (Python; `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors
- Coverage target: no coverage tooling is configured (standard-library unittest only); every scenario below maps to at least one test or static check

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reader called directly; task0001 direct-child lines are a title line, `status:detail: ignored`, `status: pending` | Returns `{'task0001': 'pending'}`; the same test fails against the base-revision hook | Unit |
| TS-2 | Hook run as a subprocess on the TS-1 block plus `routeback_failed_journal_line: 1`; journal line 1 is a failed event for task0001 | Exit code 2; stderr contains `launch=task0001` | Integration |
| TS-3 | Direct `status:detail:` (value-less other key ending in a colon), then `status: failed` | Returns `{'task0001': 'failed'}` | Unit |
| TS-4 | The only status-like direct-child line is `status:pending` (no space) | Returns `{}`; the same test fails against the base-revision hook | Unit |
| TS-5 | Direct `status:` followed by a tab and `pending` | Returns `{'task0001': 'pending'}` | Unit |
| TS-6 | Value-less direct `status:` first, then `status: pending`; with a trailing newline and as the last line of a file without one; plus the existing bare-colon and undeterminable-status cases | task0001 is absent from the result; the existing cases pass unchanged | Unit |
| TS-7 | Direct `status:failed` (no space), then `status: pending` | Returns `{'task0001': 'pending'}`; the same test fails against the base-revision hook | Unit |
| TS-8 | Direct `status:detail: ignored`, then `status: pending` only inside a deeper notes block-scalar body, or only inside a nested mapping; no direct status key line; reader, and hook with the TS-2 record and journal | Reader returns `{}`; hook exits 0 with no `BLOCK` in stderr | Unit / Integration |
| TS-9 | Full suite, including the direct-key module (contract identifiers, crafted-content fail-open, block-scalar / nested-mapping / comment-line cases) and the base queue_stop_guard module | Every test passes; no existing test was modified or removed | Regression |
| TS-10 | Imports of `em-workflow/hooks/queue_stop_guard.py` at the integrated revision | Standard-library modules only; import set unchanged from the base revision | Static |
| TS-11 | The new test module against `test/README.md` | Under `tests/` as `test_*.py`; unittest only; fixtures in temporary directories; hook run as a subprocess with Stop-hook JSON on stdin | Static |

TS-8 to TS-11 are added by this plan: TS-8 checks FR2 and TM-1 on the new
skip path, and TS-9 to TS-11 make NFR2, NFR3, NFR1 and NFR4 checkable.

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `status:detail: ignored` then `status: pending` returns `{'task0001': 'pending'}` | TS-1 (TS-3 as companion case) |
| AC-2 | Same block plus the route-back record and a failed journal line 1: exit 2, stderr names `launch=task0001` | TS-2 |
| AC-3 | Value-less direct `status:` first still leaves the task out; existing bare-colon case passes | TS-6 |
| AC-4 | FR3 tests fail on the base-revision hook and pass after the fix | Run the new test module against a scratch checkout of the base revision with only that module added: the TS-1, TS-4 and TS-7 tests fail there and pass at the integrated revision. The implementer's test record also carries the observed red. |
| AC-5 | `python3 -m unittest discover -s tests` passes | TS-9 |
| AC-6 | Only `status:pending` (no space) leaves the task out | TS-4 |
| AC-7 | `status:failed` (no space) then `status: pending` returns pending | TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-7 |
| FR2 | task0001 | TS-6, TS-8, TS-9 |
| FR3 | task0001 | TS-1, TS-4, TS-7, plus the base-revision red check (AC-4 row above) |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-9 |
| NFR3 | task0001 | TS-9 |
| NFR4 | task0001 | TS-11 |

## Manual Testing (E2E Not Possible)
- [ ] TS-10: inspect the hook's import statements in the integrated diff against the base revision.
- [ ] TS-11: inspect the new test module's placement, imports, fixture handling and hook invocation.

## Performance / Security Verification (if applicable)
- TM-1: the exact key-name check applies only to lines past the direct-child indentation filter, and a skipped non-key line leaves the direct-indent state and the multi-line value tracking untouched — checked by TS-8 (reader returns `{}` and the hook does not block when the only `status: pending` after a skipped `status:detail: ignored` line sits in a notes block-scalar body or a nested mapping) and TS-9 (the direct-key module's block-scalar, nested-mapping and comment-line tests pass unchanged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit / Integration scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Regression suite (TS-9) | 1 | 1 | 0 | 0 |
| Static checks (TS-10, TS-11) | 2 | 0 | 0 | 2 |
| Base-revision red check (SPEC AC-4) | 1 | 1 | 0 | 0 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| **Total** | 13 | 11 | 0 | 2 |
