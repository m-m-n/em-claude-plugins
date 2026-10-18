# Verification Document: codex-guard-subshell-anon-arg-semicolon

## Overview
**Feature**: codex-guard-subshell-anon-arg-semicolon / **SPEC.md**: `feature-docs/codex-guard-subshell-anon-arg-semicolon/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-subshell-anon-arg-semicolon/IMPLEMENTATION.md`

Scenario numbering: TS-1 to TS-15 below are SPEC.md's numbered test scenarios,
one to one — the same number, the same input and the same expected verdict.
TS-16 to TS-20 cover what SPEC.md lists without a number (the existing rows,
the documentation tests, the two copies) and the NFR1 to NFR3 constraint checks.
Every scenario runs against both copies of the guard. Line numbers are at the
base revision of `tests/test_codex_hook_interactive_guard.py`.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script and is not built)
- Expected: not applicable

## Test Verification
- Command (project, from workflow.yaml): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (this guard, `.claude/rules/hook-tests.md`): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, every test passes
- Coverage target: no coverage tool is configured; every scenario below has its own case-table row or test method

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'` (row 661, verdict flipped) | deny on both copies | Unit (case-table row) |
| TS-2 | A lone `&` as the first separator: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a & python3 -i; )'` | deny | Unit (case-table row) |
| TS-3 | Words pending before the `)`: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i )'` | deny | Unit (case-table row) |
| TS-4 | A launch after the closed subshell: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; :; ); python3 -i'` | deny | Unit (case-table row) |
| TS-5 | Nested provisional chain: `zsh -c 'setopt nobadpattern; ( function { :; } foo(function { :; } bar(a; python3 -i; )'` | deny | Unit (case-table row) |
| TS-6 | `&&` as the first separator: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a && python3 -i; )'` | no output | Unit (case-table row) |
| TS-7 | A newline as the first separator: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a` newline `python3 -i; )'` | no output | Unit (case-table row) |
| TS-8 | A stdin redirect after the closed subshell reaches the rescued commands: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3; ) < /dev/null'` | no output | Unit (case-table row) |
| TS-9 | A pipe into the subshell reaches the rescued commands: `zsh -c 'setopt nobadpattern; echo x \| ( function { :; } foo(a; python3; )'` | no output | Unit (case-table row) |
| TS-10 | Inside a function-definition body, skipped: `zsh -c 'setopt nobadpattern; f() ( function { :; } foo(a; python3 -i; )'` | no output | Unit (case-table row) |
| TS-11 | Row 672 rewritten, `}` does not close: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } #)'` | no output | Unit (case-table row) |
| TS-12 | Known false deny (zsh 5.9 parse error), the original row 672 input: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; } )'` | deny, label contains 既知の誤拒否 | Unit (case-table row) |
| TS-13 | Known false deny (zsh 5.9 parse error), unmatched `)` after the rescued close is a separator: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3) ) < /dev/null'` | deny, label contains 既知の誤拒否 | Unit (case-table row) |
| TS-14 | A quoted `)` is no trigger and the group stays open: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; ")"'` | no output | Unit (case-table row) |
| TS-15 | Scale, rescuable: `( `, then `function { :; } x(` repeated depth times, then `; python3 -i; )`, depth at least 60,000 | deny; exit 0, empty stderr, within the deep-input time limit (60 s) | Performance |
| TS-16 | Scale, blocked chain: `( function { :; } x(a && `, then `function { :; } x(` repeated depth times, then `; )` repeated depth times, depth at least 60,000 | no output; exit 0, empty stderr, within the deep-input time limit (60 s) | Performance |
| TS-17 | Every other existing case-table row keeps its expected verdict (row 560, rows 591-633, the `}` rescue rows 641-676 other than 661 and 672, and all the rest) | each row passes on both copies | Regression |
| TS-18 | Documentation tests: every existing marker present, no stale sentence written back, and a new marker for the `)` rescue found in the module and `_Parser` docstrings | all documentation tests pass | Unit (static) |
| TS-19 | The two copies are byte-identical, and the case table runs against both | byte-identity test and table runner pass | Unit (static) |
| TS-20 | No function calls itself and no call cycle exists; standard library only, no file, network or process access | no-recursion and static-constraint tests pass | Unit (static) |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: the structural checks inside the test module (TS-19, TS-20)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The reproduction is denied by both copies | TS-1 |
| AC2 | The lone `&`, nested chain, words-pending and after-the-close forms are denied | TS-2, TS-3, TS-4, TS-5 |
| AC3 | The `&&` and newline forms, the connected forms, the function-body form and the comment form give no output | TS-6, TS-7, TS-8, TS-9, TS-10, TS-11 |
| AC4 | Row 672 rewritten and silent; the original input and the `) ) < /dev/null` form added as known false denies | TS-11, TS-12, TS-13 |
| AC5 | The top-level rows and the `}` rescue rows keep their results | TS-17 |
| AC6 | The deep chain closed by `)` is answered in time with deny | TS-15, TS-16, TS-20 |
| AC7 | The guard's test module passes in full, the copies stay byte-identical and the documentation tests pass | TS-18, TS-19, TS-20, full module run |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-3, TS-5, TS-14 |
| FR3 | task0001 | TS-2, TS-6, TS-7 |
| FR4 | task0001 | TS-11, TS-17 |
| FR5 | task0001 | TS-3 |
| FR6 | task0001 | TS-4, TS-8, TS-9, TS-10, TS-13 |
| FR7 | task0001 | TS-11, TS-12 |
| FR8 | task0001 | TS-1 |
| FR9 | task0001 | TS-18 |
| FR10 | task0001 | TS-19 |
| NFR1 | task0001 | TS-15, TS-16 |
| NFR2 | task0001 | TS-15, TS-20 |
| NFR3 | task0001 | TS-20 |
| NFR4 | task0001 | TS-6, TS-7, TS-14 |

## Manual Testing (E2E Not Possible)
- [ ] Where zsh 5.9 is installed, `zsh -f -c 'setopt nobadpattern; ( function { :; } foo(a; printf REACHED; )'` prints REACHED (the reachability the deny of TS-1 rests on, A1). Informational: the guard's verdict itself is verified by TS-1.
- [ ] Where zsh 5.9 is installed, the TS-12 and TS-13 inputs, with `python3` replaced by a harmless command, end in a parse error and run nothing (the ground for accepting them as known false denies, A2). Informational.

## Performance / Security Verification
- NFR1: TS-15 and TS-16 answer within the deep-input time limit (60 s) with exit status 0 and empty standard error, on both copies.
- TM-1: constant-time check at `)`, each provisional group removed once, no recursion — checked by TS-15 and TS-16 (deep inputs answered in time) and TS-20 (no-recursion test).
- TM-2: launches inside the rescued chain and after the closed subshell are judged, and an unmatched `)` after the close is a separator — checked by TS-1 to TS-5 and TS-13 (deny on both copies).
- TM-3: the rescue fires only under its three conditions and every other `)` keeps its reading; false denies are limited to TS-12 and TS-13, both labelled 既知の誤拒否 — checked by TS-6 to TS-11 and TS-14 (no output), the labels of TS-12 and TS-13, and TS-17 (every other row unchanged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-20) | 20 | 20 | 0 | 0 |
| Success criteria (AC1 to AC7) | 7 | 7 | 0 | 0 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
