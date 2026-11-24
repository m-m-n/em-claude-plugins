# Verification Document: env-route-partial-overrun-check

## Overview
**Feature**: env-route-partial-overrun-check / **SPEC.md**: `feature-docs/env-route-partial-overrun-check/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/env-route-partial-overrun-check/IMPLEMENTATION.md`

## Build Verification
- Command: none (`build_command` of component `main` in workflow.yaml is empty; the Python sources are not built)
- Expected: not applicable

## Test Verification
- Command (workflow.yaml `test_command`, run from the worktree root): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused commands (NFR3): `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest tests.test_destructive_guard_env_route`
- Expected: exit code 0 for each command, and no FAIL line from `run-destructive-guard.py`
- Coverage target: not measured (no coverage tool is configured in project.components; acceptance is by the scenarios below)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Whole-hook case in `destructive-guard-cases.json`, no `batch`: an env-route body lifted through a `BASH_FUNC_mcp-bridge` assignment in which exactly one extglob reading overruns and the other decodes the notion command `git branch -D example`; a unit test on the real readings confirms the one-sided overrun of the same body | Decision deny with rule `git-branch-force-delete`, not `scan-budget-exceeded` | Integration |
| TS-2 | Same shape as TS-1 with a harmless in-limit command (for example `echo hi`), no `batch` | Decision ask with rule `scan-budget-exceeded` | Integration |
| TS-3 | Unit tests with `fake_read_values`: the overrunning reading (first or second) times the extglob setting on entry (off or on), plus both readings returning the same string in either order | Only the in-limit reading's bodies and commands are in the result, charged by the existing rule (a shared string once); overrun is still reported; the three lexer states are back at their entry values | Unit |
| TS-4 | Both readings overrun; a single reading is returned and it overruns | Nothing is queued; the scan-budget ask is held | Unit |
| TS-5 | One-sided overrun whose in-limit charge exceeds the scan budget | Nothing is queued; the scan-budget ask is held | Unit |
| TS-6 | Regression: the full `run-destructive-guard.py` suite and `tests.test_destructive_guard_env_route` | Every case and test passes | Regression |
| TS-7 | Added by this plan for NFR2 (not in SPEC.md): compare `em-workflow/hooks/tests/destructive-guard-cases.json` and `tests/test_destructive_guard_env_route.py` between the feature's base commit and the integrated result | No existing case and no existing test is removed; among existing tests only the two whose expected values SPEC.md AC-6 allows to change differ, and both still assert that overrun is reported | Diff check |
| TS-8 | Added by this plan for NFR4 (not in SPEC.md): compare `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` between the feature's base commit and the integrated result | Neither file changes | Diff check |

## Code Quality Verification
- Format: none (`format_command` of component `main` is empty) / Static analysis: none configured
- Standard library only (NFR1): the tests added by this feature import only the standard library and the hook under test

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR7 are implemented and tested | Functional Requirements Coverage below; TS-1 to TS-6 pass |
| SC-2 | TS-1 to TS-6 all pass | The test commands under Test Verification exit 0 |
| SC-3 | NFR1 to NFR5 are met | TS-6, TS-7, TS-8 and the standard-library check under Code Quality Verification |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-3 |
| FR6 | task0001 | TS-5 |
| FR7 | task0001 | TS-4, TS-6 |
| NFR1 | task0001 | TS-1, TS-2, TS-3, TS-5 and the standard-library check |
| NFR2 | task0001 | TS-6, TS-7 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-8 |
| NFR5 | task0001 | TS-3, TS-6 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is an automated test or a mechanical diff check.

## Performance / Security Verification (if applicable)
- TM-1: in a one-sided overrun the in-limit reading's bodies and commands are rescanned and a deny from them wins over the held scan-budget ask — checked by TS-1 (whole-hook deny) and TS-3 (in-limit items present in all four combinations).
- TM-2: de-duplication and charge use the in-limit reading only, whatever the read order — checked by TS-3 (the same string returned by both readings, in either order, is present once and charged once).
- TM-3: the in-limit charge is added to the scan budget before queuing, and over budget nothing is queued and the scan-budget ask is held — checked by TS-5.
- TM-4: the three lexer states are restored on every exit path and no extglob unit is recorded — checked by TS-3 (restore asserted in all four combinations) and TS-6 (the existing lexer-state tests).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-8; TS-7 and TS-8 are diff checks) | 8 | 8 | 0 | 0 |
| Code quality (standard-library check) | 1 | 1 | 0 | 0 |
| Success criteria | 3 | 3 | 0 | 0 |
| Requirements coverage | 12 | 12 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
