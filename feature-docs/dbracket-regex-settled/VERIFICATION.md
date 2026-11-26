# Verification Document: dbracket-regex-settled

## Overview
**Feature**: dbracket-regex-settled / **SPEC.md**: `feature-docs/dbracket-regex-settled/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier with a single task; the design is in `feature-docs/dbracket-regex-settled/tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/dbracket-regex-settled/THREAT-MODEL.md`

All commands run from the root of the integration worktree. "The notion command" below is the array assignment `A=(json --mcp desktop-commander --tool start_process); `, then the form, then `; `, then the canonical notion call with `--session "$SID"` whose `--args-json` `command` is `git branch -D example`.

## Build Verification
- Command: none. Component `main` has an empty `build_command`.
- Expected: nothing to build.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command for this feature's unit and integration tests: `python3 -m unittest tests.test_destructive_guard_args_json`
- Expected: exit code 0 for each, with no failing case or test.
- Coverage target: not measured (no coverage tool is configured). The pass criterion is every scenario below passing.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Settled forms: `[[ x =~ a ]]`, `[[ version =~ ^v ]]`, `[[ a =~ b ]]`, `[[ x =~ ^(ab)$ ]]`, `[[ a == @(x) ]]`, `[[ a == ?(x) ]]`, `[[ a == *(x) ]]`, `[[ a == +(x) ]]`, `[[ a == !(x) ]]`, `[[ a == @(true) && true ]]`: pass each to `_args_json_nameref_scan()`, run the notion command through `Spy(...).kinds()` and through the hook | Scan false, `[KIND_NOTHING]`, decision `allow` for every form. Every form read true before the fix (regression detection). | Unit / Integration |
| TS-2 | A `]]` inside a pattern: `[[ x =~ (]]) \|\| true -eq 0 ]]` and `[[ a == @(]]) \|\| true -eq 0 ]]` | Scan true, `[KIND_INSPECTED]`, decision `deny` with the reason ID `git-branch-force-delete` | Unit / Integration |
| TS-3 | Depth left open or broken: `[[ x =~ (a\|b) ]]` and `[[ x =~ (a ]]` through the scan, `Spy` and the hook; `[[ ( x =~ a ) ]]` and `[[ x =~ (a)>b ]]` through the scan | Scan true for all four. The first two give `[KIND_INSPECTED]` and `deny` with `git-branch-force-delete`. | Unit / Integration |
| TS-4 | Continuation statements: `[[ a == b && true =~ ^(ab)$ ]]` and `[[ a == b && true == @(]]) \|\| true -eq 0 ]]` through the scan, `Spy` and the hook; `[[ a == b && true ]] >=~` through the scan | First form: scan false, `[KIND_NOTHING]`, `allow`. Second form: scan true, `[KIND_INSPECTED]`, `deny` with `git-branch-force-delete`. Third form: scan false. | Unit / Integration |
| TS-5 | Kept readings: `[[ x == =~ ]]` and `[[ a =~ "(" ]]` through the scan, `Spy` and the hook; `[[ a =~ \( ]]` through the scan; `[[ x =~ a ]]` with its `=~` written across a line continuation and `[[ a == @(x) ]]` with a line continuation between `@` and `(` through the scan, `Spy` and the hook; `echo @(x)` and `[[ a =~ b ]] @(x)` through the scan; the existing tests of `TestSourceTextReadings` and `TestDbracketOpenerArithScan` | First two: scan false, `[KIND_NOTHING]`, `allow`. `[[ a =~ \( ]]`: scan false. Both line-continuation forms: scan true, `[KIND_INSPECTED]`, `deny` with `git-branch-force-delete`. `echo @(x)` and `[[ a =~ b ]] @(x)`: scan true. The existing tests pass without being edited. | Unit / Integration / Regression |
| TS-6 | Conventions and suites: the new case-table entries (label prefix `dbracket-regex-settled`, decision, element count, `rule`, no repeated command string); the call sites of `_args_json_conditional_step()` and of every module-level function the change adds; forbidden names and the lack of a decision and a reason ID; the docstrings of `_args_json_conditional_step()` and `_args_json_nameref_scan()`; the existing label counts; then all cases of `run-destructive-guard.py`, all tests of `tests.test_destructive_guard_args_json` and the rest of `python3 -m unittest discover -s tests` | All pass. No existing case or test is removed or edited. | Unit / Integration / Regression |
| TS-7 | NFR4, version (verification-only scenario, no SPEC counterpart): list the files changed between the implement base commit and the integration HEAD | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the list | Diff check |

## Code Quality Verification
- Format: none configured (component `main` has an empty `format_command`).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every requirement maps to task0001 and to at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-7 |
| SC-3 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes | Run the command; exit code 0 |
| SC-4 | `python3 -m unittest tests.test_destructive_guard_args_json` passes | Run the command; exit code 0 |
| SC-5 | `python3 -m unittest discover -s tests` passes | Run the command; exit code 0 |
| SC-6 | Code review is completed | The review phase's result for this feature |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-5 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-1, TS-5 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-6 |
| NFR1 | task0001 | TS-5, TS-6 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-6, TS-7 |

## Manual Testing (E2E Not Possible)
- None: every scenario above is automated or a diff check. Code review (SC-6) is the review phase's own step.

## Performance / Security Verification (if applicable)
- TM-1: after a `=~` word or an extended-pattern prefix, only the first `]]` at parenthesis depth 0 closes the conditional, and a statement left with depth, a depth below 0, a fused parenthesis or a line-continuation form stays uncertain — checked by TS-2, TS-3 and TS-4 (each such form reads true, and the notion command after it is inspected and denied with the reason ID `git-branch-force-delete`).
- TM-2: only the parentheses counted inside the conditional lose their boundary role — checked by TS-5 (`echo @(x)` and `[[ a =~ b ]] @(x)` read true) and by the existing tests of `TestDbracketOpenerArithScan` that TS-5 runs (the grouping parentheses of `[[ ( true -eq 0 ) && true ]]` and `[[ ( a == b ) && true ]]` keep their reading).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Verification-only scenario (TS-7) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Success criteria (SC-1 to SC-6) | 6 | 5 | 0 | 1 |
