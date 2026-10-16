# Verification Document: codex-guard-anon-stdin-args

## Overview
**Feature**: codex-guard-anon-stdin-args / **SPEC.md**: `feature-docs/codex-guard-anon-stdin-args/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-stdin-args/IMPLEMENTATION.md`

Scenario IDs use the hyphen-less form so that they string-match SPEC.md and
the `requirements` test lists in workflow.yaml. TS1 to TS21 come from SPEC.md's
Test Scenarios; TS22 to TS25 are the SPEC.md Integration Tests and
non-functional requirements that SPEC.md lists without an ID.

## Build Verification
- Command: none (`build_command` of component `main` is empty; the hook is an interpreted script)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Targeted command (repository rule for changes to codex-hook-interactive-guard): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for both commands, every test passes
- Coverage target: not measured (no coverage tool is configured for this project); scenario coverage is tracked by the IDs below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `zsh -c 'function < /dev/null { python3; }'` | silent (no output) for both copies | Unit (CASES) |
| TS2 | `zsh -c '< /dev/null function { python3; }'` | silent for both copies | Unit (CASES) |
| TS3 | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` | silent for both copies | Unit (CASES) |
| TS4 | `zsh -c '< /dev/null () { python3; }'` | silent for both copies | Unit (CASES) |
| TS5 | `zsh -c '< /dev/null function () { python3; }'` | silent for both copies | Unit (CASES) |
| TS6 | `zsh -c '< /dev/null function { { python3; }; }'` | silent for both copies | Unit (CASES) |
| TS7 | `zsh -c '< /dev/null function { python3 -i; }'` | deny for both copies | Unit (CASES) |
| TS8 | `zsh -c '< /dev/null function { :; } arg; python3'` | deny for both copies | Unit (CASES) |
| TS9 | `zsh -c '2> /dev/null function { python3; }'` | deny for both copies | Unit (CASES) |
| TS10 | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } (x) < /dev/null'` | silent for both copies | Unit (CASES) |
| TS11 | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(a b\|c) < /dev/null'` | silent for both copies | Unit (CASES) |
| TS12 | `zsh -c "setopt nonomatch nobareglobqual; function { python3; } foo(';') < /dev/null"` | silent for both copies | Unit (CASES) |
| TS13 | `zsh -c 'setopt nonomatch nobareglobqual; () { python3; } foo(x) < /dev/null'` | silent for both copies | Unit (CASES) |
| TS14 | `zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(x) < /dev/null'` | deny for both copies | Unit (CASES) |
| TS15 | `zsh -c 'setopt nonomatch nobareglobqual; function { :; } foo(x); python3'` | deny for both copies | Unit (CASES) |
| TS16 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i)'` | deny for both copies | Unit (CASES) |
| TS17 | `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i)'` | deny for both copies | Unit (CASES) |
| TS18 | `zsh -c 'setopt nobadpattern; function { :; } foo(a<NEWLINE>python3 -i)'` (`<NEWLINE>` is a literal newline character) | deny for both copies | Unit (CASES) |
| TS19 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` | silent for both copies (existing miss, unchanged) | Unit (CASES) |
| TS20 | Input of `function { :; } x(` repeated 6000 times, then `; :`, then 6000 `)` | exit code 0, no stderr output, output empty or a single deny, for both copies, within the existing 60-second limit | Unit (input size) |
| TS21 | `TestGuardDocumentation` | passes; every existing marker remains | Unit (existing test) |
| TS22 | `TestCopies` | passes; the two copies are byte-identical | Unit (existing test) |
| TS23 | Every `CASES` entry present at `workflow.implement.base_commit` | each keeps its expected verdict and passes; the diff of `CASES` from that commit adds entries only | Unit + diff check |
| TS24 | `TestNoRecursion` and `TestStaticConstraints` | both pass | Unit (existing test) |
| TS25 | Changed-file list from `workflow.implement.base_commit` to the integration branch | contains none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Diff check |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured; the hook's static constraints are checked by TS24

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | `zsh -c 'function < /dev/null { python3; }'` is silent | TS1 |
| AC2 | `zsh -c '< /dev/null function { python3; }'` is silent | TS2 |
| AC3 | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` is silent | TS3 |
| AC4 | `() { ...; }` and `function () { ...; }` are connected by a stdin redirect before the head | TS4, TS5, TS6 |
| AC5 | Body `-i`, a launch after the separator following the arguments, and a body with only non-stdin redirects remain deny | TS7, TS8, TS9, TS14, TS15 |
| AC6 | `(x)`, `foo(a b\|c)` and `foo(';')` are each read as one argument and the following stdin redirect connects the body | TS10, TS11, TS12, TS13 |
| AC7 | An unquoted `;`, `&` or newline in the argument `(`…`)` range gives the pre-change verdict | TS16, TS17, TS18, TS19 |
| AC8 | The module docstring describes FR1–FR3 and every existing marker remains | TS21, M-1 |
| AC9 | Both copies are byte-identical | TS22 |
| AC10 | `python3 -m unittest tests.test_codex_hook_interactive_guard` passes in full | Targeted command; TS20, TS23, TS24 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS4, TS5, TS6 |
| FR2 | task0001 | TS7, TS8, TS9, TS14, TS15 |
| FR3 | task0001 | TS3, TS10, TS11, TS12, TS13, TS14, TS15, TS16, TS17, TS18, TS19 |
| FR4 | task0001 | TS21, M-1 |
| FR5 | task0001 | TS22 |
| FR6 | task0001 | TS1, TS2, TS3 (the reproduction commands); the other `CASES` additions are traced under FR1–FR3 |
| NFR1 | task0001 | TS23 |
| NFR2 | task0001 | TS20 |
| NFR3 | task0001 | TS24 |
| NFR4 | task0001 | TS21 |
| NFR5 | task0001 | TS25 |

## Manual Testing (E2E Not Possible)
- [ ] M-1 (FR4, AC8): Read module docstring step 4 and the `_Group` / `_Parser` docstrings in either copy. They describe the head stdin redirect inheritance into the anonymous body and its scope, how `(` inside the arguments is read, and the exception for an unquoted `;`, `&` or newline in the range; the description of where arguments end does not contradict a `|` inside a `(`…`)` range; the paren search is not called fully quote-aware.

## Performance / Security Verification
- NFR2: TS20 passes, and the existing `TestMalformedAndDeepInput` passes within its 60-second limit.
- TM-1: The argument range check keeps parsing linear in input length — checked by TS20 and the existing `TestMalformedAndDeepInput` passing within the 60-second limit, and by TS24 (`TestNoRecursion`) confirming no recursion was introduced.
- TM-2: The widened silent reading does not let an interactive launch through — checked by TS7, TS8, TS9, TS14, TS15, TS16, TS17 and TS18 returning deny, TS19 staying silent, and TS23 (every pre-existing `CASES` verdict unchanged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1–TS25) | 25 | 25 | 0 | 0 |
| Manual checks (M-1) | 1 | 0 | 0 | 1 |
| Performance / Security (NFR2, TM-1, TM-2) | 3 | 3 | 0 | 0 |
| Total | 29 | 28 | 0 | 1 |
