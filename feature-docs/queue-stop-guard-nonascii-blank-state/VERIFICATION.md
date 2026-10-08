# Verification Document: queue-stop-guard-nonascii-blank-state

## Overview
**Feature**: queue-stop-guard-nonascii-blank-state / **SPEC.md**: `feature-docs/queue-stop-guard-nonascii-blank-state/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier; single task, no file declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/queue-stop-guard-nonascii-blank-state/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: N/A

## Test Verification
- Command: `python3 -m unittest discover -s tests` (repository root)
- Targeted command: `python3 -m unittest tests.test_queue_stop_guard_routeback_record` (repository root)
- Coverage target: none set by SPEC.md

### Test Scenarios from SPEC.md
TS-1 to TS-7 come from SPEC.md. TS-8 to TS-10 are added here for
requirements that SPEC.md's scenarios do not verify (FR6, NFR1, NFR3, NFR4).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | AC-1: run the hook as a subprocess with Stop-hook JSON on stdin, for the six fixtures (forms a, b, c × U+3000, U+00A0) as subTests | Exit 2, BLOCK printed, launch list contains task0001 and task0002 (SPEC.md: red at 65714d9f, exit 0) | Integration |
| TS-2 | AC-2: on each AC-1 fixture, call the reader functions of the module loaded from its file path | `task_ids_from_workflow` returns `[task0001, task0002]`; `task_routeback_records_from_workflow` maps task0001 to `"1"` | Unit |
| TS-3 | AC-6: the rewritten FR5 test (`    notes: \|` / `      body line` / column-0 U+3000 line / `      - 'x` / `      y'`) | The block scalar does not end at the column-0 U+3000 line; `      body line`, `      - 'x`, `      y'` all appear in the `iter_task_block_lines` scan | Unit |
| TS-4 | AC-4: the new fixtures and forms with a value unclosed until end of file | `task_ids_from_workflow`, `iter_task_block_lines`, `task_routeback_records_from_workflow` return without raising | Unit |
| TS-5 | FR1, FR2, FR3 edge cases: lines of only U+000B / U+000C; a non-ASCII blank line at column 2; item-content plain scalar (`      - hello`, column-0 U+3000 line, `      - 'x`); headers `>`, `\|-`, item `- \|`; consecutive non-ASCII blank lines | The record and task0002 are read in every case | Unit |
| TS-6 | AC-3, AC-7: run `python3 -m unittest tests.test_queue_stop_guard_routeback_record` and `python3 -m unittest discover -s tests` at the repository root | Both pass; `TestColumnZeroNonAsciiBlankLine`, `TestNonAsciiBlankLineDoesNotOpen`, `TestOtherNonAsciiWhitespaceIsNotBlank`, `TestBlockScalarKeepsANonAsciiBlankLine`, `TestBlockScalarEndsAtANonAsciiBlankLineByIndentation.test_a_deeper_non_ascii_line_stays_a_body_line` pass unchanged | Regression |
| TS-7 | AC-5: read the class docstring of `_MultilineValueTracker` | Both the blank-line paragraph and the plain-continuation paragraph carry the FR4 statement; "or by its indentation inside a block scalar" is absent; the module docstring is unchanged | Inspection |
| TS-8 | NFR3, FR6: diff from the implement step's base commit to the integration branch tip | Only `em-workflow/hooks/queue_stop_guard.py`, `tests/test_queue_stop_guard_routeback_record.py`, `feature-docs/queue-stop-guard-nonascii-blank-state/**` and `test-docs/queue-stop-guard-nonascii-blank-state/**` change; `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `feature-docs/routeback-record-quoted-open-residual/` and `test-docs/routeback-record-quoted-open-residual/` are unchanged | Inspection |
| TS-9 | NFR4: diff of `tests/test_queue_stop_guard_routeback_record.py` from the implement step's base commit | No existing assertion is changed or deleted except in the FR5 test | Inspection |
| TS-10 | NFR1: imports of `em-workflow/hooks/queue_stop_guard.py` | Every imported module is from the Python standard library | Inspection |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every requirement has passing scenarios |
| SC-2 | All test scenarios pass | TS-1 to TS-10 |
| SC-3 | Security requirements are satisfied | TM-1 and TM-2 in Performance / Security Verification |
| SC-4 | AC-1 to AC-7 are met | AC-1: TS-1; AC-2: TS-2; AC-3: TS-6; AC-4: TS-4; AC-5: TS-7; AC-6: TS-3; AC-7: TS-6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR2 | task0001 | TS-1, TS-2, TS-5 |
| FR3 | task0001 | TS-5, TS-6 |
| FR4 | task0001 | TS-7 |
| FR5 | task0001 | TS-3 |
| FR6 | task0001 | TS-6, TS-8 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-4 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-6, TS-9 |

## Manual Testing (E2E Not Possible)
None. The project has no E2E framework (SPEC.md), and every item is covered
by an automated test or a repository inspection above.

## Performance / Security Verification
- TM-1: in the block-scalar and plain-continuation states, a non-ASCII blank line neither continues nor ends the state, so `- '…` cannot open a quoted value that hides the record and later tasks — checked by TS-1, TS-2, TS-3 and TS-5.
- TM-2: the tracker and the three reader functions return without raising for any line content, including values unclosed at end of file — checked by TS-4.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Tests (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Inspection (TS-7 to TS-10) | 4 | 0 | 0 | 4 |
| Code quality | 0 | 0 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 12 | 8 | 0 | 4 |
