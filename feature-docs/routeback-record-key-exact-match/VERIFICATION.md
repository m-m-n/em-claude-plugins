# Verification Document: routeback-record-key-exact-match

## Overview
**Feature**: routeback-record-key-exact-match / **SPEC.md**: `feature-docs/routeback-record-key-exact-match/SPEC.md` / **IMPLEMENTATION.md**: not created (reduced tier, single task; no file is declared by two tasks)

**THREAT-MODEL.md**: `feature-docs/routeback-record-key-exact-match/THREAT-MODEL.md` (verdict: `no-applicable-threat`)

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the integration worktree root)
- Focused run: `python3 -m unittest tests.test_queue_stop_guard_routeback_record`
- Coverage target: not applicable. No coverage tool is configured for this component, so the scenario table below is the coverage measure.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The task0001 block has `routeback_failed_journal_line:x: 1` before `routeback_failed_journal_line: 1` at the direct-child indentation. `task_routeback_records_from_workflow` is called directly (AC-1, AC-5) | Returns exactly `{"task0001": "1"}`. The test fails against the pre-fix hook | Unit |
| TS-2 | Same workflow as TS-1, with task0001 `pending` and journal line 1 a `failed` event of task0001. The hook runs as a subprocess with Stop-hook JSON on stdin (AC-2, AC-5) | Exit code 2, and stderr `launch=` contains task0001. The test fails against the pre-fix hook | Integration |
| TS-3 | The task0001 block has `routeback_failed_journal_line:1` before `routeback_failed_journal_line: 1` at the direct-child indentation. The reader is called directly (AC-3, AC-5) | Returns exactly `{"task0001": "1"}`. The test fails against the pre-fix hook | Unit |
| TS-4 | Existing behaviour, reader called directly (AC-4): (a) the key, the colon, a tab and `1`; (b) an empty-value key line before `routeback_failed_journal_line: 1`; (c) `routeback_failed_journal_line:x: 1` alone | (a) record "1"; (b) no record; (c) no record. The same results before and after the change | Unit |
| TS-5 | Full suite (AC-6) | `python3 -m unittest discover -s tests` passes in full, including the existing stdlib-import tests for the hook and the test module, the wording tests, and `test_value_without_a_space_after_the_colon_is_no_record` | Integration |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR3 are implemented and tested | The Functional Requirements Coverage table below; TS-1 to TS-4 exist in `tests/test_queue_stop_guard_routeback_record.py` |
| SC-2 | TS-1 to TS-5 all pass | Run the test command |
| SC-3 | AC-1 to AC-6 are met | Rows AC-1 to AC-6 below |
| AC-1 | The reader returns `{"task0001": "1"}` for the `:x: 1` reproduction block | TS-1 |
| AC-2 | The hook exits 2 and names task0001 after `launch=` for the reproduction block | TS-2 |
| AC-3 | The reader returns `{"task0001": "1"}` when `:1` precedes the genuine record | TS-3 |
| AC-4 | The tab separator, the empty-value first occurrence and a lone `:x: 1` behave as before | TS-4 |
| AC-5 | The tests added for AC-1 to AC-3 fail on the pre-fix code | The AC-5 red check (Manual Testing), plus the "Observed red" note for this feature in the test module's docstring |
| AC-6 | Standard library only, and the full suite passes | TS-5 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-1, TS-2, TS-3, and the AC-5 red check |
| NFR1 | task0001 | TS-5 (the existing stdlib-import tests for the hook and the test module) |
| NFR2 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] AC-5 red check. Create a scratch directory outside the repository that reproduces the repository's relative layout for two files: under `em-workflow/hooks/`, the hook file as it was at `workflow.implement.base_commit` (pre-fix); under `tests/`, the post-change test module. The test module locates the hook through its own relative path. From that directory, run only the test cases added for TS-1, TS-2 and TS-3. Expected: each of them fails, while the same cases pass in the integration worktree.

## Performance / Security Verification (if applicable)
- Not applicable. The THREAT-MODEL.md verdict is `no-applicable-threat`, so there is no TM-n to verify, and SPEC.md states no performance requirement.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| SPEC compliance: AC-5 red check | 1 | 0 | 0 | 1 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 6 | 5 | 0 | 1 |
