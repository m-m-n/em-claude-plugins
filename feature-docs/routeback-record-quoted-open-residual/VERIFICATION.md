# Verification Document: routeback-record-quoted-open-residual

## Overview
**Feature**: routeback-record-quoted-open-residual / **SPEC.md**: `feature-docs/routeback-record-quoted-open-residual/SPEC.md` / **IMPLEMENTATION.md**: not written (tier `reduced`; single task, no file declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/routeback-record-quoted-open-residual/THREAT-MODEL.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty; the hook is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Targeted command: `python3 -m unittest tests.test_queue_stop_guard_routeback_record` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not set (workflow.yaml configures no coverage command)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Hook subprocess with Stop-hook JSON on stdin, one sub-case per AC-1 `notes` form: `[retry? 'failed]`, `{reason: retry? 'failed}`, two-line `[retry?` / `'failed]`, two-line `{reason: retry?` / `'failed}` (SPEC.md AC-1; FR1) | BLOCK output, exit 2, launch list contains task0001 and task0002 (red at base: exit 0) | Integration |
| TS-2 | Hook module loaded from its file path; readers called directly on the AC-1 and AC-3 fixtures (SPEC.md AC-2, AC-3; FR1, FR2) | Task IDs are task0001 and task0002; the record for task0001 is `"1"` (red at base: records empty, task IDs only task0001) | Unit |
| TS-3 | Hook subprocess, U+3000 and U+00A0 whitespace-only line × follow-up `- '…`, `"…`, `[…` — 6 sub-cases (SPEC.md AC-3; FR2) | BLOCK output, exit 2, launch list contains task0001 and task0002 | Integration |
| TS-4 | Block-scalar non-regression: `notes: \|`, a body line, 6 spaces + U+3000, `      - 'x`, then the direct child record key (FR2) | The U+3000 line stays a block-scalar body line; exit 2 naming task0001 | Integration |
| TS-5 | Regression: both test commands above from the repository root (SPEC.md AC-4; FR3, NFR4) | All tests pass, including the existing `{? 'tried }` test; no existing assertion changed or removed | Regression |
| TS-6 | Readers on every new fixture, including values unclosed to end of file (SPEC.md AC-5; NFR2) | The task-ID reader, the task-block iterator and the record reader return without raising | Unit |
| TS-7 | Inspection of the tracker class docstring and the `_scan_flow` `:` / `?` comment (SPEC.md AC-6; FR4) | Both state the FR1 condition for `?`; the docstring states the FR2 blank-line definition (spaces and tabs only) | Inspection |
| TS-8 | Inspection of the hook's imports (NFR1) | Only standard-library modules are imported | Inspection |
| TS-9 | Changed-path check: the paths changed between `workflow.implement.base_commit` and the integration branch head (NFR3) | Changed paths are within `em-workflow/hooks/queue_stop_guard.py`, `tests/test_queue_stop_guard_routeback_record.py`, `feature-docs/routeback-record-quoted-open-residual/**`, and the workflow-generated `test-docs/routeback-record-quoted-open-residual/**` of SPEC.md's Declared Change Set; `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are unchanged | Inspection |
| TS-10 | SPEC.md Test Scenarios > Edge Cases: `?` at a flow-entry start followed by space/tab/end of line stays an indicator (`[a, ? 'x]` opens); `[retry?` + `'failed]` closes at `]`; `[retry?'failed]` unchanged; column-0 U+3000 / U+00A0 line followed by `"…` or `[…` opens nothing, followed by `- '…` still opens; U+000B-only and U+000C-only lines are not blank (FR1, FR2, FR3) | Each edge case behaves as stated | Unit |

TS-1 through TS-6 are SPEC.md's scenarios. TS-7 through TS-10 are derived here from SPEC.md AC-6, NFR1, NFR3 and the Edge Cases list, which carry no SPEC.md scenario ID.

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1–FR4 are all implemented and tested | TS-1, TS-2, TS-3, TS-4, TS-5, TS-7, TS-10 |
| SC-2 | TS-1–TS-6 all pass | Run both test commands; TS-1 through TS-6 pass |
| SC-3 | NFR1–NFR4 are met | TS-8 (NFR1), TS-6 (NFR2), TS-9 (NFR3), TS-5 (NFR4) |
| SC-4 | The FR4 docstring and comment are written | TS-7 |
| SC-5 | Code review is complete | The review phase is completed in workflow.yaml |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-10 |
| FR2 | task0001 | TS-2, TS-3, TS-4, TS-10 |
| FR3 | task0001 | TS-5, TS-10 |
| FR4 | task0001 | TS-7 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-9 |
| NFR4 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] TS-7: read the tracker class docstring and the `_scan_flow` `:` / `?` comment and confirm the FR1 condition and the FR2 blank-line definition are stated

## Performance / Security Verification (if applicable)
- TM-1: `?` is the flow mapping-key indicator only at a flow-entry start and only when followed by a space, a tab or the end of the line — checked by TS-1 (the four `?` forms exit 2 with task0001 and task0002 in the launch list) and TS-2 (the readers see the record and task0002)
- TM-2: the tracker's blank-line rule accepts only spaces and tabs, in the line reader and the block-scalar branch — checked by TS-3 (the six U+3000 / U+00A0 forms exit 2 with both tasks), TS-2 (direct reader calls) and TS-4 (block-scalar branch)
- TM-3: the tracker and every reader return normally for any line content — checked by TS-6

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS-2, TS-6, TS-10) | 3 | 3 | 0 | 0 |
| Integration tests (TS-1, TS-3, TS-4) | 3 | 3 | 0 | 0 |
| Regression (TS-5) | 1 | 1 | 0 | 0 |
| Inspection (TS-7, TS-8, TS-9) | 3 | 2 | 0 | 1 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Total | 13 | 12 | 0 | 1 |
