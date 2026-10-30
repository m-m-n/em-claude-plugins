# Verification Document: cd-prefix-relative-link-target

## Overview
**Feature**: cd-prefix-relative-link-target / **SPEC.md**: `feature-docs/cd-prefix-relative-link-target/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier, single task, no file declared by more than one task) / **THREAT-MODEL.md**: `feature-docs/cd-prefix-relative-link-target/THREAT-MODEL.md`

## Build Verification
- Command: none (component `main` declares no build command)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failure or error, the same skips as before the change
- Coverage target: not measured (the project declares no coverage tool); every scenario below maps to at least one test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Links inside the area whose relative targets are `proc`, `./proc` and `dev/fd`, each naming a real in-area directory (SPEC AC-1; FR1) | The path check (`is_below`) returns True for all three; the cd prefix form with an approved string gets the allow decision through the hook | Unit (plus one hook-level check) |
| TS-2 | The same three locations reached through links with absolute targets `<dir>/proc`, `<dir>/./proc`, `<dir>/dev/fd` (SPEC AC-1; FR1, control) | The path check returns True for all three | Unit |
| TS-3 | A link whose relative target climbs back to the root with `..` and reaches `/proc/self/cwd`, followed by a name that otherwise lands below the area (SPEC AC-3; FR3, NFR2) | The path check returns False, and no location under /proc or /dev/fd is probed or read while it is judged | Unit |
| TS-4 | The existing absolute-target cases: link to `/proc/self/cwd`, link to `/proc/self` followed by `cwd/<name>`, link to `/dev/fd/<N>` (SPEC AC-2; FR2) | The existing tests pass unmodified; the path check returns False | Unit |
| TS-5 | The full test suite, including `tests/test_bash_guard_cd_prefix.py` and `tests/test_bash_guard_cd_prefix_operators.py`, and the wording tests for the hook docstrings and the protocol's Verbatim execution rule (SPEC AC-4, AC-5; FR4, FR5, NFR3) | No failure and the same skips as before; existing wording needles still match; the added wording test confirms the absolute/relative statement in all four places | Integration |
| TS-6 | The integrated diff (`workflow.implement.base_commit` to the integration branch tip) leaves the plugin versions alone (NFR1) | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` appears in the diff | Inspection |

## Code Quality Verification
- Format: none (component `main` declares no format command)
- Static analysis: none declared

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC AC-1 to AC-5 are satisfied | TS-1 (AC-1), TS-2 (AC-1 control), TS-4 (AC-2), TS-3 (AC-3), TS-5 (AC-4, AC-5) |
| SC-2 | TS-1 to TS-5 pass | `python3 -m unittest discover -s tests` exits 0 with the same skips as before |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-4 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-5 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-3 |
| NFR3 | task0001 | TS-5 (the existing standard-library-only import test of the cd prefix module) |

## Manual Testing (E2E Not Possible)
- [ ] TS-6: inspect the integrated diff's file list for the two plugin manifests named above; neither is listed.

## Performance / Security Verification (if applicable)
- TM-1: a relative link target is joined to the link's directory and refused at the first resolution stage under /proc or /dev/fd, before anything inside /proc is probed — checked by TS-3 (the climbing relative target makes the path check False, and no probe or link read under /proc or /dev/fd is recorded while it is judged).
- TM-2: the lexical check of the target text stays in place for absolute targets — checked by TS-4 (the existing absolute-target tests pass with their assertions unmodified).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests | 4 (TS-1 to TS-4) | 4 | 0 | 0 |
| Integration tests | 1 (TS-5) | 1 | 0 | 0 |
| Inspection | 1 (TS-6) | 0 | 0 | 1 |
| Security (TM-n) | 2 (TM-1, TM-2) | 2 | 0 | 0 |
| Total | 8 | 7 | 0 | 1 |
