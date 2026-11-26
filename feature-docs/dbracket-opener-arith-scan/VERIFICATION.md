# Verification Document: dbracket-opener-arith-scan

## Overview
**Feature**: dbracket-opener-arith-scan / **SPEC.md**: `feature-docs/dbracket-opener-arith-scan/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier with a single task; the design is in `feature-docs/dbracket-opener-arith-scan/tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/dbracket-opener-arith-scan/THREAT-MODEL.md`

All commands run from the root of the integration worktree.

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
| TS-1 | Pass each AC-1 / AC-4 form of SPEC to `_args_json_nameref_scan()`: `[[ ( true -eq 0 ) && true ]]`, the same with `-ne` / `-lt` / `-le` / `-gt` / `-ge`, with `\|\|` in place of `&&`, with `false` / `echo` / `:` / `mcp-bridge` in place of `true` inside the parentheses, `if [[ ( true -eq 0 ) && true ]]; then :; fi`, and `[[ ( -v x ) && true ]]` | Returns true for every form. Every form whose name inside the parentheses is allow-listed returned false before the fix (regression detection). | Unit |
| TS-2 | Run the array assignment `A=(json --mcp desktop-commander --tool start_process); `, then `[[ ( true -eq 0 ) && true ]]` / `if [[ ( true -eq 0 ) && true ]]; then :; fi` / `[[ ( -v x ) && true ]]`, then `; `, then the canonical notion call with `--session "$SID"` whose `--args-json` `command` is `git branch -D example`, through `Spy(...).kinds()` | `[KIND_INSPECTED]` for each | Integration |
| TS-3 | False-positive prevention: `[[ ( true == x ) && true ]]` (with the array assignment), each existing `CONDITIONAL_ALLOW` form (with the array assignment) and each existing `certain_forms()` form (without it), followed by the notion call with `--session "$SID"`. Range bounds: `[[ a == b ]] >-eq` and `>-eq [[ a == b ]]`. Uncertain form: `[[ ( a == b ) && true ]]` | `[KIND_NOTHING]` after each listed form other than the uncertain form, and the scan returns false for `[[ ( true == x ) && true ]]` and for both range-bound forms. For `[[ ( a == b ) && true ]]`, the conditional reading reports no statement as uncertain, and the chunk answer stays what it was before the fix (true); see the note below. | Unit / Integration |
| TS-4 | Case table: the deny / allow cases added to `destructive-guard-cases.json` under labels starting with `dbracket-opener-arith-scan`, run by `run-destructive-guard.py` | Each matches its decision. Each deny case matches the reason ID `git-branch-force-delete`. No added command string repeats an existing one. | Integration |
| TS-5 | The existing suites: all cases of `run-destructive-guard.py`, all tests of `tests.test_destructive_guard_args_json` (including the call-site, no-decision and docstring tests), and the rest of `python3 -m unittest discover -s tests` | All pass. No existing case or test is removed. | Regression |
| TS-6 | NFR4, static analysis only (verification-only scenario, no SPEC counterpart): read the diff of `em-workflow/hooks/destructive-guard.py` between the implement base commit and the integration HEAD | The diff adds no process launch, no evaluation of a string as code, and no file or network access | Review |
| TS-7 | NFR5, version (verification-only scenario, no SPEC counterpart): list the files changed between the implement base commit and the integration HEAD | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the list | Diff check |

Note on TS-3 (`[[ ( a == b ) && true ]]`): SPEC FR3 / AC-5 / TS-3 state that
this form stays uncertain. The `(` boundary makes `a == b` a simple command
whose name `a` is outside the allow-list, and the command-level reading,
unchanged by this feature (FR3, NFR1), reads that command as uncertain, as at
the base commit. The new FR1 scan adds nothing for this form, and its chunk
answer is unchanged (true). The following notion call with `--session "$SID"`
is `[KIND_INSPECTED]`: with the array assignment, the hook's decision is
`deny` with the reason ID `git-branch-force-delete`. It is not in the case
table as an allow case.

## Code Quality Verification
- Format: none configured (component `main` has an empty `format_command`).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR maps to task0001 and to at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-7 |
| SC-3 | Code review is completed | The review phase's result for this feature |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-4 |
| FR2 | task0001 | TS-2, TS-4 |
| FR3 | task0001 | TS-3, TS-4 |
| NFR1 | task0001 | TS-4, TS-5 |
| NFR2 | task0001 | TS-5 (the existing call-site and no-decision tests) |
| NFR3 | task0001 | TS-5 (the existing docstring tests) |
| NFR4 | task0001 | TS-6 |
| NFR5 | task0001 | TS-7 |

## Manual Testing (E2E Not Possible)
- [ ] TS-6: read the diff of `em-workflow/hooks/destructive-guard.py` and confirm the change only reads the words already lexed, with no process launch, no evaluation of a string as code and no file or network access.

## Performance / Security Verification (if applicable)
- TM-1: in the statement that opens a `[[ ]]` conditional, the words between the opener and the closer are scanned for the arithmetic comparison operators and `-v` — checked by TS-1 (every form whose name inside the parentheses is allow-listed reads uncertain) and by TS-2 and TS-4 (the notion call with `--session "$SID"` after each form is inspected, and the hook denies it with the reason ID `git-branch-force-delete`).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Verification-only scenarios (TS-6, TS-7) | 2 | 1 | 0 | 1 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Success criteria (SC-1 to SC-3) | 3 | 2 | 0 | 1 |
