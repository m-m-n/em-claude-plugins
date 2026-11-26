# Verification Document: dbracket-was-open-close-scan

## Overview
**Feature**: dbracket-was-open-close-scan / **SPEC.md**: `feature-docs/dbracket-was-open-close-scan/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, a single task with no shared file) / **THREAT-MODEL.md**: `feature-docs/dbracket-was-open-close-scan/THREAT-MODEL.md`

## Build Verification
- Command: none (`build_command` is empty in workflow.yaml; Python with no build step)
- Expected: not applicable

## Test Verification
- Command (from the repository root): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0; the runner prints no FAIL line; unittest reports OK.
- Coverage target: no coverage tool is configured; every scenario below maps to at least one automated check.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `_args_json_nameref_scan()` on the chunks `[[ true && true ]] >=~` and `[[ true && true ]] >-eq`, with a spy on `_args_json_conditional_step()` | The scan reads false for both; the closing (second) statement reports (false, false). Before the fix both read true (regression detection) | Unit |
| TS-2 | Spy kinds and the hook judgment for each TS-1 form followed by `; ` and the notion call with `--session "$SID"` (args-json command `git branch -D example`), with and without the array assignment `A=(json --mcp desktop-commander --tool start_process); ` in front | Kinds exactly [KIND_NOTHING]; decision `allow` | Integration |
| TS-3 | Detection kept: `[[ true && true =~ true ]]` and `[[ true && true -eq 0 ]]` after the array assignment, followed by `; ` and the same notion call | Scan reads true; kinds exactly [KIND_INSPECTED]; hook result (`deny`, `git-branch-force-delete`) | Integration |
| TS-4 | Non-closer `]]` in a continuation statement, for each escaped or quoted closer operand X of TestSourceTextReadings.CLOSER_OPERANDS: `[[ a && true == X ]] >=~` and `>-eq`; `[[ a && true == X \|\| true -eq 0 ]]`; `[[ a && true -eq \]\]` (no real closer); `[[ a && true == b ]]` followed directly by a carriage return, a blank and `>=~`; and the SPEC example `[[ a && \]\] == x ]] >=~` | The first pair reads false with (false, false) for the statement holding X; the `\|\|` form reads true with (false, true) for the statement holding X; the no-closer form reads true; the carriage-return form reads true with (true, true) for its second statement; the SPEC example's second statement reports (false, false). The scan of the SPEC example stays true from the command-level reading (its continuation statement's command name, an escaped `]]`, is not an allowlisted name), so only the conditional reading's report is checked for it | Unit |
| TS-5 | Regression: the case table and the full suites | The six new rows (four allow rows with no fourth element, two deny rows with `{"rule": "git-branch-force-delete"}`), labels starting with `dbracket-was-open-close-scan`, each command string once in the table, match decision and reason ID under `run-destructive-guard.py`; every entry of the case table at the merge base with `main` is present unchanged; every test method of `tests/test_destructive_guard_args_json.py` at the merge base is still defined; both commands of Test Verification exit 0 | Integration |
| TS-6 | Planner-added (FR4): the docstring of `_args_json_conditional_step()` | The whitespace-normalized docstring contains "In a later statement that holds the closer, the words up to just before the closer are read and the words after the closer are not read here." and still contains "Words before the opener and words after the closer are not read here." | Unit |
| TS-7 | Planner-added (NFR5): the change set of the integration branch | `git diff --name-only` of the integration branch tip against its merge base with `main` lists only `em-workflow/hooks/destructive-guard.py`, `em-workflow/hooks/tests/destructive-guard-cases.json`, `tests/test_destructive_guard_args_json.py` and paths under `feature-docs/dbracket-was-open-close-scan/` and `test-docs/dbracket-was-open-close-scan/` | Automated (git) |

## Code Quality Verification
- Format: not configured (`format_command` is empty in workflow.yaml)
- Static analysis: not configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR maps to task0001 and at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-7 pass |
| SC-3 | AC-1 to AC-5 of SPEC.md are satisfied | AC-1: TS-1; AC-2: TS-2; AC-3: TS-3; AC-4: TS-6; AC-5: TS-5 |
| SC-4 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` pass | Test Verification command exits 0 |
| SC-5 | Code review is completed | The review phase of workflow.yaml is completed |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001 | TS-3, TS-4; manual diff review below (opener-statement branch unchanged) |
| FR4 | task0001 | TS-6 |
| FR5 | task0001 | TS-5 |
| NFR1 | task0001 | TS-5 (base entries and test methods still present, all pass) |
| NFR2 | task0001 | TS-5 (existing tests: called only from the scan, no decision, no reason ID, no launch, no file read) |
| NFR3 | task0001 | TS-5 (existing static-only tests) |
| NFR4 | task0001 | TS-5 (new labels start with `dbracket-was-open-close-scan`; the existing label-count and label-prefix tests pass) |
| NFR5 | task0001 | TS-7 |

## Manual Testing (E2E Not Possible)
- [ ] Read the diff of `_args_json_conditional_step()` against the merge base with `main`: only the `was_open` branch and the docstring change; the opener-statement branch (`was_open` false) and the tail that handles a `;` or lone `&` separator are unchanged (FR3, TM-1).

## Performance / Security Verification (if applicable)
- Performance: not applicable.
- NFR3 (static analysis only): the existing tests that the conditional reading launches nothing, reads no file, makes no decision and names no reason ID pass (part of TS-5).
- TM-1: only the first word written exactly `]]` with no stripped trailing carriage return ends the reading of a continuation statement; non-closer `]]` forms are read past and every word before the closer keeps its checks — checked by TS-3 and TS-4 passing, by the existing conditional tables of TestSourceTextReadings (CONDITIONAL_DENY, CLOSER_OPERANDS) and the DENY_FORMS tests of TestDbracketOpenerArithScan passing unchanged (TS-5), and by the manual diff review above.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 7 | 7 | 0 | 0 |
| Success criteria | 5 | 4 | 0 | 1 |
| Requirements coverage | 10 | 10 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (NFR3) | 1 | 1 | 0 | 0 |
| Security (TM-n) | 1 | 1 | 0 | 0 |
