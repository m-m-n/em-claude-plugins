# Verification Document: codex-guard-case-paren-rescue

## Overview
**Feature**: codex-guard-case-paren-rescue / **SPEC.md**: `feature-docs/codex-guard-case-paren-rescue/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-case-paren-rescue/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not applicable (no coverage tool is configured); behavior coverage is the CASES rows TS-1 to TS-9 and TS-11 to TS-19 plus the A9 rows, each run against both guard copies

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'` — review 5e71ff00fdbe5aff reproduction | deny from both copies | Unit (CASES row) |
| TS-2 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'` — `case` after a bare `!` | deny from both copies | Unit (CASES row) |
| TS-3 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'` — `case` after a bare `time` | deny from both copies | Unit (CASES row) |
| TS-4 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'` — inheritance along the provisional chain | deny from both copies | Unit (CASES row) |
| TS-5 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'` — redirect after the outer subshell connects the body | silent from both copies | Unit (CASES row) |
| TS-6 | `zsh -c 'setopt nobadpattern; echo x \| ( function { python3; } foo(a; case x in x) :;; esac; )'` — pipe into the outer subshell connects the body | silent from both copies | Unit (CASES row) |
| TS-7 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'` — argument-position `case` is not marked (the existing TS-7b row is kept) | silent from both copies | Unit (CASES row) |
| TS-8 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'` — quoted `case` is not marked (the existing TS-8b row is kept) | silent from both copies | Unit (CASES row) |
| TS-9 | `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'` — existing limitation, labelled as a known miss | silent from both copies (unchanged) | Unit (CASES row) |
| TS-10 | `python3 -m unittest tests.test_codex_hook_interactive_guard` from the repository root — all CASES rows, `test_the_two_copies_are_byte_identical`, the docstring-marker tests (the new `esac` checks included) and the depth / linearity tests | all pass | Unit (suite) |
| TS-11 | `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x in esac; )'` — finding 285d9bc33784bb3d reproduction; the `esac` right after `in` returns the mark to 0 | deny from both copies | Unit (CASES row) |
| TS-12 | `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in esac; python3 -i; )'` — finding df4afa83e782d56a; launch after an empty `case` | deny from both copies | Unit (CASES row) |
| TS-13 | `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in (x) :;; esac; python3 -i; )'` — finding df4afa83e782d56a; command-position `esac` after `;;` | deny from both copies | Unit (CASES row) |
| TS-14 | `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; "time" case; python3 -i; )'` — finding b374e6b3c3d4b471; a quoted `time` is not in the run | deny from both copies | Unit (CASES row) |
| TS-15 | `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; \! case; python3 -i; )'` — finding b374e6b3c3d4b471; an escaped `!` is not in the run | deny from both copies | Unit (CASES row) |
| TS-16 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (x) case y in (y) :;; esac;; z) < /dev/null :;; esac; )'` — nested `case`; the mark is 1 after the inner `esac` | deny from both copies | Unit (CASES row) |
| TS-17 | `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in (x) :;; esac; )'` — the `esac` inside P2 decrements its inherited value | deny from both copies | Unit (CASES row) |
| TS-18 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) echo esac;; x) < /dev/null :;; esac; )'` — argument-position `esac` does not decrement | deny from both copies | Unit (CASES row) |
| TS-19 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) "esac";; x) < /dev/null :;; esac; )'` — quoted `esac` does not decrement | deny from both copies | Unit (CASES row) |

### Edge Cases from SPEC.md
- [ ] A9: an `esac` on the line after `case x` (a newline between `case x` and `in esac`), and zsh's brace form `case x { ... }`, do not decrement the mark — checked by the CASES rows labelled A9 (task0002), which run in TS-10 on both copies.

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Both guards deny TS-1 | TS-1 CASES row passes on both copies |
| AC2 | Both guards deny TS-2 and TS-3 | TS-2 and TS-3 CASES rows pass on both copies |
| AC3 | Both guards deny TS-4 | TS-4 CASES row passes on both copies |
| AC4 | TS-5 to TS-8 stay silent; TS-7b and TS-8b stay deny | TS-5 to TS-8, TS-7b and TS-8b CASES rows pass on both copies |
| AC5 | TS-9 result (silent) is unchanged | TS-9 CASES row passes on both copies |
| AC6 | TS-10 passes | `python3 -m unittest tests.test_codex_hook_interactive_guard` exits 0 |
| AC7 | Both guards deny TS-11, TS-12 and TS-13 | TS-11 to TS-13 CASES rows pass on both copies |
| AC8 | Both guards deny TS-14 and TS-15 | TS-14 and TS-15 CASES rows pass on both copies |
| AC9 | Both guards deny TS-16 and TS-17 | TS-16 and TS-17 CASES rows pass on both copies |
| AC10 | Both guards deny TS-18 and TS-19 | TS-18 and TS-19 CASES rows pass on both copies |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-11 to TS-19 (marked, decremented or unmarked forms deny); TS-5 to TS-8 (connected or unmarked forms stay silent); A9 rows |
| FR2 | task0001, task0002 | TS-4 (inherited value on the provisional child); TS-17 (inherited value decremented by `esac`) |
| FR3 | task0001, task0002 | TS-1 to TS-8, TS-11, TS-12, TS-13, TS-16, TS-17 (no paren rescue while marked; rescue once the mark is back to 0) |
| FR4 | task0001, task0002 | TS-7, TS-8, TS-9, TS-18, TS-19, A9 rows, and the existing CASES rows in TS-10 |
| FR5 | task0001, task0002 | TS-10 (docstring-marker tests, the new `esac` checks included) plus review of the docstring locations for the count, the decrement and the absence of permanence statements |
| FR6 | task0001, task0002 | TS-10 (byte-identity test; every row runs on both copies) |
| FR7 | task0001, task0002 | TS-1 to TS-9 and TS-11 to TS-19 present as CASES rows; the revised case-mark comment; the `esac` docstring checks in TS-10 |
| NFR1 | task0001, task0002 | TS-10 (depth / linearity tests) |
| NFR2 | task0001, task0002 | TS-10 (`test_the_two_copies_are_byte_identical`) |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction from the goal (step 1): feed the stdin JSON `{"tool_input":{"command":"zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'"}}` to each guard copy run directly from the repository root; each answers deny instead of exiting 0 with no output.

## Performance / Security Verification (if applicable)
- NFR1: parse stays linear with no recursion — the existing depth / linearity tests in TS-10 pass on both copies.
- TM-1: counted case mark, chain inheritance and no paren rescue while marked — TS-1, TS-2, TS-3 and TS-4 are denied by both copies.
- TM-2: constant-time mark change, run state, after-`in` state, inheritance and paren check with no recursion or ancestor walk — the depth / linearity tests in TS-10 pass on both copies.
- TM-3: a bare `esac` at an FR1 position removes the mark, and a quoted or escaped reserved word does not extend the run — TS-11 to TS-15 and TS-17 are denied by both copies.
- TM-4: an `esac` outside an FR1 position, or the inner `esac` of a nested `case`, does not remove the mark — TS-16, TS-18, TS-19 are denied by both copies and the A9 rows pass.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-19) | 19 | 19 | 0 | 0 |
| Edge cases (A9, two forms) | 2 | 2 | 0 | 0 |
| Success criteria (AC1 to AC10) | 10 | 10 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Performance / Security (NFR1, TM-1 to TM-4) | 5 | 5 | 0 | 0 |
| **Total** | 37 | 36 | 0 | 1 |
