# Verification Document: routeback-record-direct-key

## Overview
**Feature**: routeback-record-direct-key / **SPEC.md**: `feature-docs/routeback-record-direct-key/SPEC.md` / **IMPLEMENTATION.md**: not produced (tier `reduced`, single task, no file declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/routeback-record-direct-key/THREAT-MODEL.md`

Scenario IDs TS-1 to TS-7 correspond one-to-one to SPEC.md's test scenarios
with the same number. TS-8 to TS-11 cover the SPEC.md edge case and the
requirements that SPEC.md's scenarios do not exercise directly.

## Build Verification
- Command: none declared (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted command: `python3 -m unittest tests.test_queue_stop_guard tests.test_queue_stop_guard_routeback_record tests.test_queue_hook_status_read_pin`
- Expected: exit code 0, no failures or errors
- Coverage target: not set (the project declares no coverage tooling)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Hook module loaded from its file path; reproduction fixture: task0001 `pending`, `notes: \|` body line `routeback_failed_journal_line: 3`, direct-key `routeback_failed_journal_line: 1`; call `task_routeback_records_from_workflow` | Returns `{'task0001': '1'}` | Unit |
| TS-2 | Journal line 1 is task0001's `failed` event; task0001 `pending`; a `notes` block scalar body contains `routeback_failed_journal_line: 1`; no direct-key record; repeated for the `\|`, `\|-`, `>`, `>-` indicators and a form with an explicit indentation indicator | Hook exits 0, no BLOCK on stderr, for every indicator | Integration |
| TS-3 | Journal line 1 is task0001's `failed` event; task0001 `pending`; `notes: \|` body line `routeback_failed_journal_line: 3` placed before the direct-key `routeback_failed_journal_line: 1` | Hook exits 2; stderr's launch list names task0001 | Integration |
| TS-4 | As TS-3, but the notes body carries the matching value 1 and the direct-key record carries the different value 2 | Hook exits 0 (the direct-key record decides) | Integration |
| TS-5 | Journal line 1 is task0001's `failed` event; task0001 `pending`; `routeback_failed_journal_line: 1` is a key of a mapping nested one level under another direct key; no direct-key record | Hook exits 0 | Integration |
| TS-6 | Journal line 1 is task0001's `failed` event; task0001 `pending`; a continuation line of a multi-line double-quoted `notes` value reads `routeback_failed_journal_line: 1`; no direct-key record | Hook exits 0 | Integration |
| TS-7 | Run the targeted command and the full-suite command above | Both exit 0; existing tests pass with their assertions unchanged (first occurrence, canonical value, block range, `TestFailOpen`, `TestModuleDocstring`) | Regression |
| TS-8 | Empty `notes: \|` immediately followed by `routeback_failed_journal_line: 1` at the direct-child indentation (SPEC.md edge case, assumption A1); call `task_routeback_records_from_workflow` | Returns `{'task0001': '1'}` (read as a sibling key) | Unit |
| TS-9 | Inspect the hook's module docstring, the record-read function docstring and the record regex comment | All three state that only direct keys of the task's own mapping are read and that block scalar bodies and nested lines are not; the pinned phrases remain and the excluded phrase is absent | Inspection |
| TS-10 | Inspect the import lines of `em-workflow/hooks/queue_stop_guard.py` and `tests/test_queue_stop_guard_routeback_record.py`, and how the new tests invoke the hook | Hook: standard library only, no YAML library, line-based read. Tests: standard library only, no import of another test module, hook behavior run as a subprocess with Stop-hook JSON on stdin; only the function-level tests load the module by file path | Inspection |
| TS-11 | Diff of the integration branch against the implement base commit | Contains no change to `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | Inspection |

## Code Quality Verification
- Format: none declared (`project.components.main.format_command` is empty)
- Static analysis: none declared

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR4 are implemented and tested | TS-1 to TS-9 pass |
| SC-2 | NFR1 to NFR5 hold | TS-7, TS-10, TS-11 |
| SC-3 | SPEC.md AC1 to AC6 hold | AC1: TS-1. AC2: TS-2, TS-4. AC3: TS-3. AC4: TS-5, TS-6. AC5: TS-7. AC6: TS-7, TS-9 |
| SC-4 | SPEC.md's test scenarios all pass | TS-1 to TS-7 pass |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-8 |
| FR2 | task0001 | TS-7 (existing first-occurrence, canonical-value and block-range tests) |
| FR3 | task0001 | TS-7 (`TestModuleDocstring`), TS-9 |
| FR4 | task0001 | TS-2, TS-3 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-7 (`TestFailOpen`) |
| NFR3 | task0001 | TS-10 |
| NFR4 | task0001 | TS-11 |
| NFR5 | task0001 | TS-7 |

## Manual Testing (E2E Not Possible)
- [ ] TS-9: docstring and comment inspection
- [ ] TS-10: import and test-structure inspection
- [ ] TS-11: version-file diff inspection

## Performance / Security Verification (if applicable)
- TM-1: the route-back record is read only from direct keys of the task's own mapping — checked by TS-2, TS-5 and TS-6 (a matching record-shaped line in a block scalar body, under a nested key, or in a quoted-scalar continuation line creates no record: exit 0), by TS-3 and TS-4 (a record-shaped line in the notes body placed before the real record does not shadow it), and by TS-1 (function-level result).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit (TS-1, TS-8) | 2 | 2 | 0 | 0 |
| Integration (TS-2 to TS-6) | 5 | 5 | 0 | 0 |
| Regression (TS-7) | 1 | 1 | 0 | 0 |
| Inspection (TS-9 to TS-11) | 3 | 0 | 0 | 3 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 12 | 9 | 0 | 3 |
