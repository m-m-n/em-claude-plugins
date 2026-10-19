# Verification Document: codex-guard-case-paren-rescue

## Overview
**Feature**: codex-guard-case-paren-rescue / **SPEC.md**: `feature-docs/codex-guard-case-paren-rescue/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-case-paren-rescue/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not applicable (no coverage tool is configured); behavior coverage is the CASES rows TS-1 to TS-9, each run against both guard copies

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'` — review 5e71ff00fdbe5aff reproduction | deny from both copies | Unit (CASES row) |
| TS-2 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'` — `case` after reserved word `!` | deny from both copies | Unit (CASES row) |
| TS-3 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'` — `case` after reserved word `time` | deny from both copies | Unit (CASES row) |
| TS-4 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'` — inheritance along the provisional chain | deny from both copies | Unit (CASES row) |
| TS-5 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'` — redirect after the outer subshell connects the body | silent from both copies | Unit (CASES row) |
| TS-6 | `zsh -c 'setopt nobadpattern; echo x \| ( function { python3; } foo(a; case x in x) :;; esac; )'` — pipe into the outer subshell connects the body | silent from both copies | Unit (CASES row) |
| TS-7 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'` — argument-position `case` is not marked | silent from both copies | Unit (CASES row) |
| TS-8 | `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'` — quoted `case` is not marked | silent from both copies | Unit (CASES row) |
| TS-9 | `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'` — existing limitation, labelled as a known miss | silent from both copies (unchanged) | Unit (CASES row) |
| TS-10 | `python3 -m unittest tests.test_codex_hook_interactive_guard` from the repository root — all existing CASES rows (paren-rescue and brace-rescue rows included), `test_the_two_copies_are_byte_identical`, the docstring-marker tests and the depth / linearity tests | all pass | Unit (suite) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Both guards deny TS-1 | TS-1 CASES row passes on both copies |
| AC2 | Both guards deny TS-2 and TS-3 | TS-2 and TS-3 CASES rows pass on both copies |
| AC3 | Both guards deny TS-4 | TS-4 CASES row passes on both copies |
| AC4 | TS-5 to TS-8 stay silent | TS-5 to TS-8 CASES rows pass on both copies |
| AC5 | TS-9 result (silent) is unchanged | TS-9 CASES row passes on both copies |
| AC6 | TS-10 passes | `python3 -m unittest tests.test_codex_hook_interactive_guard` exits 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3 (marked forms deny); TS-5, TS-6, TS-7, TS-8 (connected or unmarked forms stay silent) |
| FR2 | task0001 | TS-4 (inherited value on the provisional child) |
| FR3 | task0001 | TS-1 to TS-8 (no paren rescue on marked chains; rescue unchanged otherwise) |
| FR4 | task0001 | TS-7, TS-8, TS-9 and the existing CASES rows in TS-10 |
| FR5 | task0001 | TS-10 (docstring-marker tests) plus review of the seven docstring locations |
| FR6 | task0001 | TS-10 (byte-identity test; every row runs on both copies) |
| FR7 | task0001 | TS-1 to TS-9 present as CASES rows |
| NFR1 | task0001 | TS-10 (depth / linearity tests) |
| NFR2 | task0001 | TS-10 (`test_the_two_copies_are_byte_identical`) |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction from the goal (step 1): feed the stdin JSON `{"tool_input":{"command":"zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'"}}` to each guard copy run directly from the repository root; each answers deny instead of exiting 0 with no output.

## Performance / Security Verification (if applicable)
- NFR1: parse stays linear with no recursion — the existing depth / linearity tests in TS-10 pass on both copies.
- TM-1: case mark, chain inheritance and no paren rescue on marked chains — TS-1, TS-2, TS-3 and TS-4 are denied by both copies.
- TM-2: constant-time marking, inheritance and paren check with no recursion or ancestor walk — the depth / linearity tests in TS-10 pass on both copies.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-10) | 10 | 10 | 0 | 0 |
| Success criteria (AC1 to AC6) | 6 | 6 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Performance / Security (NFR1, TM-1, TM-2) | 3 | 3 | 0 | 0 |
| **Total** | 20 | 19 | 0 | 1 |
