# Verification Document: codex-guard-extglob-funcname

## Overview
**Feature**: codex-guard-extglob-funcname / **SPEC.md**: `feature-docs/codex-guard-extglob-funcname/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; one task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/codex-guard-extglob-funcname/THREAT-MODEL.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) declare an empty build command; the changed files are Python scripts run directly.
- Expected: not applicable.

## Test Verification
- Commands, run from the integration worktree root:
  - `python3 -m unittest tests.test_codex_hook_interactive_guard` — focused suite; the repository's hook-tests rule requires it whenever either guard copy changes
  - `python3 -m unittest discover -s tests` — component `repo-tests`
  - `python3 em-workflow/scripts/check-plugin-invariants.py .` — component `plugin-invariants`
- Expected: every command exits 0.
- Coverage target: no coverage tool is configured. Coverage is judged by the case table instead: each of the five operator characters, each FR2 form (no reserved word, after a reserved word, after a reserved word with an option, with `function`) and the nested `bash -O extglob -c` form has at least one deny case, and every case runs against both copies.

### Test Scenarios from SPEC.md
Command strings write a newline as `\n`. TS-1 to TS-6 follow the SPEC.md Unit Tests list in order. TS-7 covers the FR2 example with an option after the reserved word, and TS-8 covers the SPEC.md assumptions A1 and A3. TS-9 to TS-11 are the SPEC.md Documentation / Copy Tests, TS-12 is the SPEC.md run commands, and TS-13 is NFR3. TS-1 to TS-8 are entries of CASES in tests/test_codex_hook_interactive_guard.py and run against both copies.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `bash -O extglob -c 'time /bin/true?()\n(python3 -i)'` — reserved word present, inside the bash -c string | deny on both copies | Unit (CASES) |
| TS-2 | `bash -O extglob -c 'f?()\n(python3 -i)'` — no reserved word, inside the bash -c string | deny on both copies | Unit (CASES) |
| TS-3 | `if true; then f?()\n(python3 -i)\nfi` — right after then, top level | deny on both copies | Unit (CASES) |
| TS-4 | `f*()\n(python3 -i)`, `f+()\n(python3 -i)`, `f@()\n(python3 -i)`, `f!()\n(python3 -i)` — one case per remaining operator character | each deny on both copies | Unit (CASES) |
| TS-5 | `function f?()\n{ python3 -i; }` — function keyword, brace group | deny on both copies | Unit (CASES) |
| TS-6 | Existing `foo()\n(python3 -i)`, `then()\n(python3 -i)`, `time f() { python3 -i; }` and the other existing function-definition cases | silent on both copies, unchanged | Unit (existing CASES) |
| TS-7 | `time -p f?()\n(python3 -i)` — reserved word with an option | deny on both copies | Unit (CASES) |
| TS-8 | `'f?'()\n(python3 -i)`, `f\?()\n(python3 -i)`, `f? ()\n(python3 -i)`, `!()\n(python3 -i)` — quoted or escaped final character, whitespace before the parenthesis, reserved-word-only word | each deny on both copies | Unit (CASES) |
| TS-9 | TestGuardDocumentation checks the FR1 rule text in the module docstring's procedure step 4, the _Group head description and the _names_function docstring | pass | Unit (documentation) |
| TS-10 | TestCopies checks that the two copies are byte-identical | pass | Unit (copy) |
| TS-11 | TestStaticConstraints checks standard-library-only imports and no file, network or child-process access | pass | Unit (static constraints) |
| TS-12 | `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` | both exit 0 | Integration (full suite) |
| TS-13 | Integrated diff against the feature's base commit | no change to em-workflow/.claude-plugin/plugin.json, em-review/.claude-plugin/plugin.json or .claude-plugin/marketplace.json | Static (diff inspection) |

## Code Quality Verification
- Format: none configured (empty format command in both components).
- Static analysis: none configured. Byte identity of the two copies is checked by TS-10 and the standard-library-only constraint by TS-11.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC.md AC1: the reserved-word form inside `bash -O extglob -c` is denied by both copies | TS-1 |
| SC-2 | SPEC.md AC2: the form without a reserved word inside `bash -O extglob -c` is denied by both copies | TS-2 |
| SC-3 | SPEC.md AC3: each of `?` `*` `+` `@` `!` as the final character leads to deny | TS-2, TS-3, TS-4 |
| SC-4 | SPEC.md AC4: every existing case keeps its expected decision on both copies | TS-6 and the focused suite |
| SC-5 | SPEC.md AC5: the three documentation places state the FR1 rule and TestGuardDocumentation checks them | TS-9 |
| SC-6 | SPEC.md AC6: the two copies are byte-identical | TS-10 |
| SC-7 | SPEC.md AC7: the full test suite passes | TS-12 |
| SC-8 | Both SPEC.md run commands pass | the focused suite and TS-12 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-7, TS-8 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-7 |
| FR3 | task0001 | TS-1, TS-2 |
| FR4 | task0001 | TS-6, TS-12 |
| FR5 | task0001 | TS-9 |
| FR6 | task0001 | TS-1, TS-2 |
| NFR1 | task0001 | TS-10, TS-12 |
| NFR2 | task0001 | TS-11, TS-12 |
| NFR3 | task0001 | TS-13 |

## Manual Testing (E2E Not Possible)
- None. Every scenario above is automated or a mechanical diff check; the project has no E2E framework.

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md states no performance requirement).
- TM-1: the function-name judgment rejects a candidate name whose content ends in an extglob operator character, so the group after `()` is evaluated — checked by TS-1 to TS-5, TS-7 and TS-8 returning deny on both copies.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit scenarios in CASES (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Documentation, copy and static-constraint tests (TS-9 to TS-11) | 3 | 3 | 0 | 0 |
| Full suite and plugin invariants (TS-12) | 1 | 1 | 0 | 0 |
| Version-unchanged diff check (TS-13) | 1 | 1 | 0 | 0 |
| Security mitigations (TM-1) | 1 | 1 | 0 | 0 |
| Total | 14 | 14 | 0 | 0 |
