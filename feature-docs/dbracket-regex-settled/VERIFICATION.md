# Verification Document: dbracket-regex-settled

## Overview
**Feature**: dbracket-regex-settled / **SPEC.md**: `feature-docs/dbracket-regex-settled/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; task0001 is merged and task0002 builds on it, so no contract is shared between tasks run in parallel; the design is in `feature-docs/dbracket-regex-settled/tasks/task0001.md` and `feature-docs/dbracket-regex-settled/tasks/task0002.md`) / **THREAT-MODEL.md**: `feature-docs/dbracket-regex-settled/THREAT-MODEL.md`

All commands run from the root of the integration worktree. "The notion command" below is the array assignment `A=(json --mcp desktop-commander --tool start_process); `, then the form, then `; `, then the canonical notion call with `--session "$SID"` whose `--args-json` `command` is `git branch -D example`. "Both scans" means `_args_json_nameref_scan()` and `_args_json_shadow_scan()`, each called on the plain marked text of the form.

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
| TS-1 | Settled forms: `[[ x =~ a ]]`, `[[ version =~ ^v ]]`, `[[ a =~ b ]]`, `[[ x =~ ^(ab)$ ]]`, `[[ x =~ ^(ab)c ]]`, `[[ a == @(x) ]]`, `[[ a == ?(x) ]]`, `[[ a == *(x) ]]`, `[[ a == +(x) ]]`, `[[ a == !(x) ]]`, `[[ a == @(true) && true ]]`: pass each to both scans, run the notion command through `Spy(...).kinds()` and through the hook | Both scans false, `[KIND_NOTHING]`, decision `allow` for every form, `[[ x =~ ^(ab)$ ]]` included | Unit / Integration |
| TS-2 | A `]]` inside a pattern or touching a pattern's parenthesis: `[[ x =~ (]]) \|\| true -eq 0 ]]`, `[[ a == @(]]) \|\| true -eq 0 ]]`, `[[ x =~ (x)]] \|\| true -eq 0 ]]`, `[[ a == @(x)]] \|\| true -eq 0 ]]`, `[[ a == b && true =~ (x)]] \|\| true -eq 0 ]]` and `[[ x =~ ]](x) \|\| true -eq 0 ]]` through `_args_json_nameref_scan()`, `Spy` and the hook | Scan true, `[KIND_INSPECTED]`, decision `deny` with the reason ID `git-branch-force-delete` for every form | Unit / Integration |
| TS-3 | Depth left open or broken: `[[ x =~ (a\|b) ]]` and `[[ x =~ (a ]]` through `_args_json_nameref_scan()`, `Spy` and the hook; `[[ ( x =~ a ) ]]` and `[[ x =~ (a)>b ]]` through `_args_json_nameref_scan()` | Scan true for all four. The first two give `[KIND_INSPECTED]` and `deny` with `git-branch-force-delete`. | Unit / Integration |
| TS-4 | Continuation statements: `[[ a == b && true =~ ^(ab)$ ]]` and `[[ a == b && true =~ ^(ab)c ]]` through both scans, `Spy` and the hook; `[[ a == b && true == @(]]) \|\| true -eq 0 ]]` through `_args_json_nameref_scan()`, `Spy` and the hook; `[[ a == b && true ]] >=~` through `_args_json_nameref_scan()` | First two forms: both scans false, `[KIND_NOTHING]`, `allow`. Third form: scan true, `[KIND_INSPECTED]`, `deny` with `git-branch-force-delete`. Fourth form: scan false. | Unit / Integration |
| TS-5 | Kept readings: `[[ x == =~ ]]` and `[[ a =~ "(" ]]` through both scans, `Spy` and the hook; `[[ a =~ \( ]]` through `_args_json_nameref_scan()`; `[[ x =~ a ]]` with its `=~` written across a line continuation and `[[ a == @(x) ]]` with a line continuation between `@` and `(` through `_args_json_nameref_scan()`, `Spy` and the hook; `echo @(x)` and `[[ a =~ b ]] @(x)` through `_args_json_nameref_scan()`; the existing tests of `TestSourceTextReadings` and `TestDbracketOpenerArithScan` | First two: both scans false, `[KIND_NOTHING]`, `allow`. `[[ a =~ \( ]]`: scan false. Both line-continuation forms: scan true, `[KIND_INSPECTED]`, `deny` with `git-branch-force-delete`. `echo @(x)` and `[[ a =~ b ]] @(x)`: scan true. The existing tests pass, and the only one edited is the call-site test NFR1 names. | Unit / Integration / Regression |
| TS-6 | Conventions and suites: the case-table entries labelled `dbracket-regex-settled` (the two `$` allow forms, the three touching-closer deny forms and the existing entries, the two `^(ab)c` entries kept; decision, element count, `rule`, no repeated command string, exactly the forms the class lists, neither of the two other label prefixes); the functions referencing `_args_json_conditional_step()` and `_args_json_simple_commands()` (exactly the two scans) and `_args_json_fd_variable_deferred()` (only `_args_json_nameref_scan()`); forbidden names and the lack of a decision and a reason ID in the conditional reading and every function the feature adds; the existing label counts; then all cases of `run-destructive-guard.py`, all tests of `tests.test_destructive_guard_args_json` and the rest of `python3 -m unittest discover -s tests` | All pass. No existing case is removed or edited; no test outside the feature's class is edited or removed except `test_the_readings_are_called_only_from_the_scan`. | Unit / Integration / Regression |
| TS-7 | Docstrings: `_args_json_conditional_step()` states the depth rule and `COUNTED`; `_args_json_nameref_scan()` states the depth rule and names no command; `_args_json_shadow_scan()` item 3 names `_args_json_conditional_step()` and `_args_json_simple_commands()`; the docstrings of `_args_json_conditional_step()` and `_args_json_simple_commands()` and the comment opening the section of `_args_json_word_source()` name both scans as callers | Each check passes; the shadow-scan docstring still holds "Fail safe", "Only the chunk's own text is read", "the static-run match" and "_args_json_static_runs()"; no docstring says it is called only from `_args_json_nameref_scan()` | Unit |
| TS-8 | Item 3 of the shadow scan: `_args_json_shadow_scan()` on `[[ x =~ ^(ab)$ ]]`, `[[ a == b && true =~ ^(ab)$ ]]`, `[[ a == @(eval) ]]` and `[[ x =~ (eval) && true ]]`; on `[[ ( $y == b ) ]]`, `[[ x =~ (a) ]] && ( eval x )`, `echo @(eval)`, `[[ a =~ b ]] @(eval)`, `[[ x =~ (eval) && y =~ (a\|b) ]]` and `[[ x =~ (eval) && true`; a recording spy on `_args_json_conditional_step()` during the call on `[[ x =~ ^(ab)$ ]]` | First four: false. Next six: true. The spy sees at least one call, every counted token is one of the token objects passed to that call, and `_args_json_nameref_scan()` is not called. | Unit |
| TS-9 | NFR4, version (verification-only scenario, no SPEC counterpart): list the files changed between the implement base commit and the integration HEAD | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the list | Diff check |

## Code Quality Verification
- Format: none configured (component `main` has an empty `format_command`).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every requirement maps to a task and to at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-9 |
| SC-3 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes | Run the command; exit code 0 |
| SC-4 | `python3 -m unittest tests.test_destructive_guard_args_json` passes | Run the command; exit code 0 |
| SC-5 | `python3 -m unittest discover -s tests` passes | Run the command; exit code 0 |
| SC-6 | Code review is completed | The review phase's result for this feature |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-5 |
| FR2 | task0001, task0002 | TS-1, TS-2, TS-3 |
| FR3 | task0001, task0002 | TS-2, TS-4 |
| FR4 | task0001 | TS-1, TS-5 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001, task0002 | TS-6 |
| FR7 | task0002 | TS-1, TS-4, TS-8 |
| NFR1 | task0001, task0002 | TS-5, TS-6 |
| NFR2 | task0001, task0002 | TS-6 |
| NFR3 | task0001, task0002 | TS-6 |
| NFR4 | task0001, task0002 | TS-6, TS-7, TS-9 |

## Manual Testing (E2E Not Possible)
- None: every scenario above is automated or a diff check. Code review (SC-6) is the review phase's own step.

## Performance / Security Verification (if applicable)
- TM-1: after a `=~` word or an extended-pattern prefix, only the first `]]` at parenthesis depth 0 that touches no parenthesis closes the conditional, and a statement left with depth, a depth below 0, a fused parenthesis, a `]]` touching a parenthesis or a line-continuation form stays uncertain — checked by TS-2, TS-3 and TS-4 (each such form reads true, and the notion command after it is inspected and denied with the reason ID `git-branch-force-delete`).
- TM-2: only the parentheses counted inside the conditional lose their boundary role in the nameref reading — checked by TS-5 (`echo @(x)` and `[[ a =~ b ]] @(x)` read true) and by the existing tests of `TestDbracketOpenerArithScan` that TS-5 runs (the grouping parentheses of `[[ ( true -eq 0 ) && true ]]` and `[[ ( a == b ) && true ]]` keep their reading).
- TM-3: item 3 of the shadow scan keeps only the counted parentheses of a settled conditional, taken from its own tokens, inside their simple command — checked by TS-8 (the grouping parentheses, the parentheses after a closer or without a conditional, a statement read uncertain before the closer and a conditional still open at the end of the chunk all read true; the counted tokens are the objects passed to the call, and the nameref reading is not called) and by the existing tests of the shadow scan and the notion lift that TS-6 runs.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Verification-only scenario (TS-9) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Success criteria (SC-1 to SC-6) | 6 | 5 | 0 | 1 |
