# Verification Document: codex-guard-anon-arg-escaped-backquote

## Overview
**Feature**: codex-guard-anon-arg-escaped-backquote / **SPEC.md**: `feature-docs/codex-guard-anon-arg-escaped-backquote/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-arg-escaped-backquote/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Guard-specific run (the project rule for this guard; runs the case table against both copies): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for both
- Coverage target: none set (the project has no coverage tooling)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The SPEC FR3 command is run as a CASES row through each copy, using the hook's standard-input JSON (FR1, FR2, FR3) | Each copy outputs `permissionDecision: deny` | Unit (hook entry point) |
| TS-2 | The existing CASES rows (including the backquote-related deny and silent rows), TestFailOpen's backquote case, TestNoRecursion, TestMalformedAndDeepInput and TestStaticConstraints are run against the changed copies (NFR1, NFR2, NFR3) | Every existing decision is unchanged and every test passes; no existing row is edited or removed | Unit |
| TS-3 | The copy-identity test is run (FR2) | `TestCopies.test_the_two_copies_are_byte_identical` passes | Unit |
| TS-4 | Each of these unquoted backquote spans is fed in: one where every later backquote is backslash-escaped, one whose text ends in a lone backslash, and one of deep-input length made only of backslash pairs (FR1 unclosed rule, NFR1) | Each is read as unclosed and gives the `quote` undecidable result, with the guard's fail-open output; the deep-input case finishes | Unit |
| TS-5 | A backquote inside an unquoted span is preceded by an even-length run of backslashes, then by an odd-length run (FR1 pair rule) | The even-length run closes the span; the odd-length run does not | Unit |

## Code Quality Verification
- Format: none declared (`format_command` is empty)
- Static analysis: none declared. TestStaticConstraints, which is part of the test command, enforces the standard-library-only constraint (NFR2).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | The Functional Requirements Coverage table below; TS-1, TS-4 and TS-5 pass |
| SC-2 | All test scenarios pass | The test command exits 0 |
| SC-3 | Both copies remain byte-identical | TS-3 |
| SPEC AC-1 | Each copy denies the FR3 command fed on standard input | TS-1 |
| SPEC AC-2 | CASES has exactly one deny row with the FR3 command, and the guard test module passes against both copies | TS-1, plus reading the test module: exactly one row carries the FR3 command |
| SPEC AC-3 | The two copies are byte-identical | TS-3 |
| SPEC AC-4 | The full test command passes | The test command exits 0 (TS-2) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4, TS-5 |
| FR2 | task0001 | TS-1, TS-3 |
| FR3 | task0001 | TS-1 |
| NFR1 | task0001 | TS-2, TS-4 |
| NFR2 | task0001 | TS-2 |
| NFR3 | task0001 | TS-2 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated. TS-1 covers the goal's reproduction step (feeding the JSON to the hook's standard input).

## Performance / Security Verification (if applicable)
- NFR1: the closing search runs in linear time with no recursion. Checked by TestNoRecursion and TestMalformedAndDeepInput passing (TS-2) and by TS-4's deep-input case finishing with the `quote` result.
- TM-1: both copies skip backslash pairs in the closing search, so the explicit `-i` is denied. Checked by TS-1 (deny from each copy) and TS-3 (the copies are byte-identical).
- TM-2: the closing search is one forward pass with no recursion, and an unclosed span gives the `quote` undecidable result. Checked by TS-4 and by TS-2's TestNoRecursion and TestMalformedAndDeepInput.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 5 (TS-1 to TS-5) | 5 | 0 | 0 |
| Code quality | 1 (TestStaticConstraints, inside the test run) | 1 | 0 | 0 |
| SPEC compliance | 7 (SC-1 to SC-3, SPEC AC-1 to AC-4) | 7 | 0 | 0 |
| Performance / Security | 3 (NFR1, TM-1, TM-2) | 3 | 0 | 0 |
| Total | 16 | 16 | 0 | 0 |
