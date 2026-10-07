# Verification Document: routeback-record-quoted-continuation

## Overview
**Feature**: routeback-record-quoted-continuation / **SPEC.md**: `feature-docs/routeback-record-quoted-continuation/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; task0002 is a review rework task on task0001's merged code and shares no new contract with it) / **THREAT-MODEL.md**: `feature-docs/routeback-record-quoted-continuation/THREAT-MODEL.md`

Scenario IDs use the TS-n form. TS-1 to TS-7 correspond one-to-one, by
number, to the SPEC.md Test Scenarios TS1 to TS7. TS-8 is taken from the
SPEC.md Edge Cases (NFR2) and TS-9 from NFR5; SPEC.md lists no scenario for
either. TS-10 and TS-11 are added by review round 1 rework (task0002; FR4).

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted run: `python3 -m unittest tests.test_queue_stop_guard tests.test_queue_stop_guard_routeback_record tests.test_queue_hook_status_read_pin tests.test_routeback_record_carve_out`
- Coverage target: not measured (no coverage tooling is configured); every scenario below must pass

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Load the hook module from its file path and call the record-read function on the reproduction fixture (task0001 pending; notes as `notes: "tried twice` / `routeback_failed_journal_line: 1` / `gave up"`, all at 4-space indentation), in double-quoted, single-quoted and flow forms | Empty mapping returned for every form | Unit |
| TS-2 | Forgery: journal line 1 is task0001 `failed`, task0001 pending, record-shaped `routeback_failed_journal_line: 1` only on a 4-space continuation line of multi-line notes, no direct-key record; subTests for double-quoted, single-quoted, flow sequence, flow mapping | Hook exits 0; stderr has no BLOCK | Integration |
| TS-3 | Hiding: same setup, notes continuation line carries `routeback_failed_journal_line: 3`, a later direct key carries `routeback_failed_journal_line: 1`; same four forms | Hook exits 2; launch list contains task0001 | Integration |
| TS-4 | Cross-task forgery inside task0001's quoted notes: `  task0002:` plus a 4-space record naming task0002's `failed` journal line (real task0002 pending, no record); `  task0002:` plus a 4-space `status: pending` (real task0002 `status: failed`, matching record); a `  task0099:` line | Exit 0 for both forgeries; task0099 never in the launch list | Integration |
| TS-5 | Quoted notes whose continuation lines (closing line included) sit at column 0, followed by task0002 and task0003 | task0002 and task0003 appear in the launch list | Integration |
| TS-6 | Closing / opening boundaries: escaped double quote, doubled single quote and trailing backslash do not close; escaped backslash before a double quote closes; a comment after a same-line close does not open; unclosed double quote and `[` in block scalar bodies (`|`, `>-`), comment lines, plain scalars and a top-level block scalar before `tasks:` do not open; a quoted value starting on the line after its key; nested flow with brackets inside inner strings and comments; one-line closed values | Escapes and next-line value: record-shaped body line not read (exit 0). Real closes, non-openings, nested flow after its close, one-line values: genuine direct-key record read (exit 2 naming task0001) | Integration |
| TS-7 | Regression: the targeted run above and `python3 -m unittest discover -s tests`; new test pinning the FR6 statement in the module docstring, the three function docstrings and the record-key comment | All pass; no existing assertion changed | Regression |
| TS-8 | Fail-open: quoted and flow notes values that never close before end of file (with record- and task-key-shaped lines after the opening), and a file mixing invalid UTF-8 bytes with unclosed quotes and brackets; via the hook subprocess and via direct calls of the task-id, task-block and record readers | Hook exits 0 with no BLOCK and no Traceback; direct calls do not raise; no line after the unclosed opening yields a task id or record | Integration |
| TS-9 | Change-set check on the integrated diff (implement base commit to integration tip) | Only `em-workflow/hooks/queue_stop_guard.py`, `tests/test_queue_stop_guard_routeback_record.py` and paths under `feature-docs/routeback-record-quoted-continuation/` / `test-docs/routeback-record-quoted-continuation/` change; `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are not in the diff | Change-set check |
| TS-10 | Flow plain scalars: (a) task0001 pending, journal line 1 its `failed` event, one-line notes `[retry:'failed]`, `{a:'b}` or `[retry?'failed]`, then a direct-key `routeback_failed_journal_line: 1` and a pending task0002 block with no journal event; via the hook subprocess and via direct calls of the task-id and record readers. (b) Real indicators: multi-line flow notes whose inner single-quoted string opens after `{"a":` or after `[a: ` and holds a 4-space record-shaped line before it closes, no direct-key record | (a) Hook exits 2 with task0001 and task0002 in the launch list; task ids include task0001 and task0002; the record for task0001 is `1`. (b) Hook exits 0; stderr has no BLOCK | Integration |
| TS-11 | Plain-scalar continuation: (a) same setup as TS-10 (a) with `notes: retry failed` followed by a 6-space continuation line `- 'unclosed`, `- "unclosed` or `- [unclosed`, and the next-line form `notes:` / 6-space `retry failed` / 6-space `- 'unclosed`. (b) Release at the parent indentation, no direct-key record: a plain `title:` followed by a direct-key multi-line double-quoted notes holding a 4-space record-shaped line; a 4-space quoted sequence item after a 4-space plain item, holding a 4-space record-shaped line | (a) Hook exits 2 with task0001 and task0002 in the launch list. (b) Hook exits 0; stderr has no BLOCK | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured
- Import discipline (NFR1, NFR3): covered by the stdlib-only import tests that run inside TS-7

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1-FR7 are implemented and tested | Functional Requirements Coverage table below; TS-1 to TS-7, TS-10 and TS-11 pass |
| SC-2 | TS1-TS7 of SPEC.md all pass | TS-1 to TS-7 pass |
| SC-3 | NFR1-NFR6 are met | TS-7, TS-8, TS-9 pass |
| SC-4 | The FR6 docstrings and comment are written | TS-7 (new pinning test plus the existing TestModuleDocstring and TestDirectKeyWording) |
| SC-5 | Code review is complete | workflow.yaml `review.status` is `completed` with `residual_critical_high` 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-10, TS-11 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR3 | task0001, task0002 | TS-6, TS-10 |
| FR4 | task0001, task0002 | TS-6, TS-10, TS-11 |
| FR5 | task0001, task0002 | TS-3, TS-6, TS-7, TS-10 |
| FR6 | task0001 | TS-7 |
| FR7 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-10, TS-11 (the tests themselves exist and pass) |
| NFR1 | task0001, task0002 | TS-7 (stdlib-only import test of the hook) |
| NFR2 | task0001, task0002 | TS-8, TS-7 (existing TestFailOpen) |
| NFR3 | task0001, task0002 | TS-7 (stdlib-only import test of the test module; subprocess invocation) |
| NFR4 | task0001, task0002 | TS-7 (status-read pin static scan), TS-9 |
| NFR5 | task0001, task0002 | TS-9 |
| NFR6 | task0001, task0002 | TS-7 |

## Manual Testing (E2E Not Possible)
- None. Every item is automated.

## Performance / Security Verification (if applicable)
- TM-1: value-body lines are never used as a section start/end, task key, block end or yielded block line, so a forged record, status or task key is not read — checked by TS-2 (exit 0 in all four forms), TS-4 (forged task0002 record / status ignored, task0099 absent), the escape and next-line-value cases of TS-6 (exit 0), TS-10 (b) and TS-11 (b) (exit 0).
- TM-2: value-body lines are dropped without ending any block or section, and only value-start quotes / brackets open — checked by TS-3 (exit 2 naming task0001 in all four forms), TS-5 (task0002 and task0003 still listed after a column-0 body), the real-close, non-opening, nested-flow and one-line cases of TS-6 (exit 2 naming task0001), TS-10 (a) and TS-11 (a) (exit 2 naming task0001 and task0002).
- TM-3: the open/close tracking never raises; an unclosed value marks the rest of the file as body — checked by TS-8 (exit 0, no Traceback, direct calls do not raise) and the existing TestFailOpen cases in TS-7.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-11) | 11 | 11 | 0 | 0 |
| Success criteria (SC-1 to SC-5) | 5 | 5 | 0 | 0 |
| Requirements coverage (FR1-FR7, NFR1-NFR6) | 13 | 13 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual checks | 0 | 0 | 0 | 0 |
