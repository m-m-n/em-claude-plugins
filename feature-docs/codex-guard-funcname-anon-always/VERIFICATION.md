# Verification Document: codex-guard-funcname-anon-always

## Overview
**Feature**: codex-guard-funcname-anon-always / **SPEC.md**: `feature-docs/codex-guard-funcname-anon-always/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-funcname-anon-always/IMPLEMENTATION.md`

Scenario IDs use the `TSn` form, matching SPEC.md and workflow.yaml (IMPLEMENTATION.md D2).

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script run as is)

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Hook-specific command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (standard-library `unittest` only, NFR3); coverage is by the scenarios below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `zsh -c 'echo "$(function f g case { :; })"; python3 -i'` | deny on both copies | Unit (`CASES`) |
| TS2 | A reserved word, a head word, `[[`, `esac` or `always` after a second or later function name in `$( )` (e.g. `function f g if {`, `function f g for {`, `function f g [[ {`, `function f g always {`), followed by `python3 -i` | deny on both copies | Unit (`CASES`) |
| TS3 | `case` right after the first name (A-4 of codex-guard-brace-case-group-depth); `function a b { ... }`, `function a b () { ... }`, `function a b ((echo a) ) { ... }` | Verdict of the base guard, unchanged | Unit (`CASES`) |
| TS4 | Reproduction steps 3, 4 and 5 | deny on both copies | Unit (`CASES`) |
| TS5 | Reproduction steps 3 to 5 written with `function () { :; }` and with `() { :; }` | deny on both copies | Unit (`CASES`) |
| TS6 | In a brace-form case item body, an `always` after an anonymous body's `}` raises no depth (the `quoted_launch_in_a_later_item` shape) | deny on both copies | Unit (`CASES`) |
| TS7 | The `quoted_launch_in_a_later_case` shape with the body `{ function { :; } } always`: the argument-position `}` closes the outer ordinary group, `always` is a reserved word, the next `{` is at a command position | silent on both copies | Unit (`CASES`) |
| TS8 | `echo "$(function { function { :; } } always { case y in y) echo '"; python3 -i; "';; esac; })"`: the argument-position `}` closes the outer anonymous body and the words after it stay arguments | deny on both copies | Unit (`CASES`) |
| TS9 | A quoted `"}"`, an escaped `\}`, `a}` and `}a` in anonymous arguments | Stay arguments; the close position does not change | Unit (`CASES`) |
| TS10 | `always` after a separator that follows anonymous arguments (`function { :; } x; always ...`) | deny on both copies | Unit (`CASES`) |
| TS11 | DEPTH anonymous functions in a row, DEPTH nested anonymous functions, and a `function` head with DEPTH names followed by `case` | deny on both copies within the existing timeout | Unit (timing, `TestCaseStatementsInASubstitution`) |
| TS12 | An arithmetic re-read after a second name (`function a b ((echo a) ) case ...`) and after an anonymous function (`function { :; } ((echo a) ) always ...`) | Verdict of the base guard, unchanged | Unit (`CASES`) |
| TS13 | Every `CASES` row of the base revision (the `{ :; } always { ... }` silent rows included) and every existing test class | Same verdicts and results as at the base revision | Integration |
| TS14 | The em-workflow and em-review copies | Byte-identical (`TestCopies` passes) | Unit |
| TS15 | The `_skip_substitution` docstring states the reading of FR1 to FR4 (rules 1, 2, 5, 6, 7, 9) | `TestSubstitutionSkipDocumentation` passes with the new markers on both copies | Unit |
| TS16 | The module comment before the head-state constants, and every other comment or docstring outside `_skip_substitution`'s docstring touched by the reading | Matches the reading of FR1 to FR4 | Manual (review) |
| TS17 | Standard library only | `TestStaticConstraints` passes; the test file imports only standard-library modules | Unit |
| TS18 | No recursion | `TestNoRecursion` passes | Unit |
| TS19 | Plugin versions | `git diff --name-only` between the base commit and the integration branch lists no file under `.claude-plugin/` (neither plugin's `plugin.json`, nor the root `marketplace.json`) | Automated (command) |
| TS20 | The full test command and the hook-specific command | Exit code 0 | Integration |

## Code Quality Verification
- Format: none (`format_command` is empty)
- Static analysis: none configured; `TestStaticConstraints` covers the guard's runtime constraints

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction step 2 is denied | TS1 |
| AC2 | Reproduction step 3 is denied | TS4 |
| AC3 | Reproduction step 4 is denied | TS4 |
| AC4 | Reproduction step 5 is denied | TS4 |
| AC5 | Steps 3 to 5 with `function () { :; }` and `() { :; }` are denied | TS5 |
| AC6 | The reproduction inputs and the FR1 to FR5 rows are in `CASES` and pass on both copies | TS1 to TS10, TS12 |
| AC7 | Existing `CASES` rows and test classes keep their verdicts | TS13 |
| AC8 | Both copies are byte-identical | TS14 |
| AC9 | `python3 -m unittest tests.test_codex_hook_interactive_guard` and `python3 -m unittest discover -s tests` pass | TS20 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2 |
| FR2 | task0001 | TS3, TS13 |
| FR3 | task0001 | TS4, TS5, TS6, TS10 |
| FR4 | task0001 | TS7, TS8, TS9 |
| FR5 | task0001 | TS3, TS10, TS13 |
| FR6 | task0001, task0002 | TS14 |
| FR7 | task0001, task0002 | TS15, TS16 |
| NFR1 | task0001 | TS11, TS18 |
| NFR2 | task0001 | TS12 |
| NFR3 | task0001, task0002 | TS17 |
| NFR4 | task0001, task0002 | TS19 |

## Manual Testing (E2E Not Possible)
- [ ] TS16: read the module comment before the head-state constants and every other comment or method docstring task0001 changed, against IMPLEMENTATION.md M1 to M9.
- [ ] Read the `_skip_substitution` docstring (task0002) against the merged reading (task0001): each statement of rules 1, 2, 5, 6, 7 and 9 describes what the code does (the two tasks were written in parallel against IMPLEMENTATION.md M1 to M9).

## Performance / Security Verification
- NFR1: TS11 runs within `TestMalformedAndDeepInput.TIMEOUT` per command on both copies; TS18 passes.
- TM-1: after the second function name every word other than a standalone `{` or `}`, an empty `()` and a separator is a name — TS1 and TS2 are denied by both copies.
- TM-2: the anonymous body's `}` sets no group-closed state and no command position, and the words up to the separator are arguments in which only a standalone `}` closes the innermost open group — TS4 to TS10 give their expected verdicts on both copies.
- TM-3: the arithmetic re-read restores the head state and the open `{` group records to their values at the `((` — TS12 gives the base guard's verdicts on both copies.
- TM-4: the reading stays linear with no recursion — TS11 within the timeout, TS18.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1 to TS20) | 20 | 19 | 0 | 1 |
| Success criteria (AC1 to AC9) | 9 | 9 | 0 | 0 |
| Docstring / code cross-check | 1 | 0 | 0 | 1 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Total | 35 | 33 | 0 | 2 |
