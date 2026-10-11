# Verification Document: codex-guard-nested-parse-error

## Overview
**Feature**: codex-guard-nested-parse-error / **SPEC.md**: `feature-docs/codex-guard-nested-parse-error/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-nested-parse-error/IMPLEMENTATION.md`

## Build Verification
- Command: none (no build command is configured for `repo-tests` or `plugin-invariants`)
- Expected: not applicable

## Test Verification
- Command (component `repo-tests`): `python3 -m unittest discover -s tests`
- Command (component `plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for each command
- Coverage target: no coverage tool is configured; coverage is by scenario (TS-1 to TS-9 below)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction input: 5000-nine fd word at depth 2, followed by `python3 -i` at depth 0, run against both copies | `deny` for both copies; the entry point prints exactly one deny decision | Unit |
| TS-2 | Same 5000-nine shape at depth 0 followed by `python3 -i` | `deny` for both copies | Unit |
| TS-3 | Same 5000-nine shape at depth 1 followed by `python3 -i` | `deny` for both copies | Unit |
| TS-4 | All-zero multi-digit fd: `python3 00< f` | `silent` for both copies | Unit |
| TS-5 | Range boundary: `python3 2147483648>/dev/null` and `python3 2147483647>/dev/null` | `silent` and `deny` respectively, for both copies | Unit |
| TS-6 | Static syntax-tree check of the handler around the nested parse in `_scan` | Handler catches the general exception class in addition to `_Undecidable` and neither returns nor raises | Unit (static) |
| TS-7 | Docstring step 7 marker | The added sentence is in `TestGuardDocumentation.DOCSTRING_MARKERS` and in both copies' module docstring | Unit |
| TS-8 | Whole suite, copy identity, static constraints | `python3 -m unittest discover -s tests` (including the copy-identity, case-table, static-constraint and no-recursion tests) and `python3 em-workflow/scripts/check-plugin-invariants.py .` exit 0; every pre-existing case keeps its verdict | Integration |
| TS-9 | Version fields unchanged | Diff from the implement base commit shows no change to any `.claude-plugin/plugin.json` or to `.claude-plugin/marketplace.json` | Integration |

## Code Quality Verification
- Format: none configured / Static analysis: none configured (static constraints are covered by TS-8)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction input yields exactly one deny on standard output (both copies) | TS-1 |
| AC2 | Depth-0 and depth-1 5000-nine forms are deny | TS-2, TS-3 |
| AC3 | `python3 00< f` and `python3 2147483648>/dev/null` are silent; `python3 2147483647>/dev/null` is deny | TS-4, TS-5 |
| AC4 | Nested-parse handler in `_scan` also catches unexpected errors and continues | TS-6 |
| AC5 | Docstring step 7 states the added case and the marker pins it | TS-7 |
| AC6 | Existing case verdicts unchanged; copies byte-identical; suite and plugin invariants pass | TS-8 |
| AC7 | No diff in version files | TS-9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-4 |
| FR2 | task0001 | TS-6 |
| FR3 | task0001 | TS-1, TS-2 |
| FR4 | task0001 | TS-8 |
| FR5 | task0001 | TS-1, TS-2, TS-5 |
| FR6 | task0001 | TS-7 |
| FR7 | task0001 | TS-3, TS-4, TS-5 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-8 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-9 |
| NFR5 | task0001 | TS-8 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated.

## Performance / Security Verification
- TM-1: The fd digit word is classified without numeric conversion; an over-range word is an ordinary word — checked by TS-1 to TS-5 on both copies (no huge-digit deny row is silent; boundary rows match their verdicts).
- TM-2: An unexpected error in a nested parse skips that string and the scan continues without a deny — checked by TS-6; TS-8 confirms no existing case changes verdict.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Security mitigations (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 11 | 11 | 0 | 0 |
