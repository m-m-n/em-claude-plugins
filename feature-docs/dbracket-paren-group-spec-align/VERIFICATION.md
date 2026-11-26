# Verification Document: dbracket-paren-group-spec-align

## Overview
**Feature**: dbracket-paren-group-spec-align / **SPEC.md**: `feature-docs/dbracket-paren-group-spec-align/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier with a single task; the design is in `feature-docs/dbracket-paren-group-spec-align/tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/dbracket-paren-group-spec-align/THREAT-MODEL.md`

All commands run from the root of the integration worktree.

The amendments to `feature-docs/dbracket-opener-arith-scan/SPEC.md` (FR2, FR3)
and `feature-docs/dbracket-opener-arith-scan/VERIFICATION.md` (FR7) are made by
the planner at create-plan, not by a task. TS-5 verifies them.

## Build Verification
- Command: none. Component `main` has an empty `build_command`.
- Expected: nothing to build.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused commands: `python3 em-workflow/hooks/tests/run-destructive-guard.py` (the case table) and `python3 -m unittest tests.test_destructive_guard_args_json` (the new and the aligned tests)
- Expected: exit code 0 for each, with no failing case or test.
- Coverage target: not measured (no coverage tool is configured). The pass criterion is every scenario below passing.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run the array assignment `A=(json --mcp desktop-commander --tool start_process); `, then `[[ ( a == b ) && true ]]`, then `; `, then the canonical notion call with `--session "$SID"` whose `--args-json` command is `git branch -D example`, through `Spy(...).kinds()`. Run the hook judgment on the same command. | `[KIND_INSPECTED]`. The hook judgment is `("deny", "git-branch-force-delete")`. | Integration |
| TS-2 | Case table: the new row of `em-workflow/hooks/tests/destructive-guard-cases.json` for the TS-1 command, run by `run-destructive-guard.py`, and the membership test in `tests/test_destructive_guard_args_json.py` | Exactly one new deny row, whose label starts with `dbracket-paren-group-spec-align` and whose fourth element is `{"rule": "git-branch-force-delete"}`. The runner matches both the decision and the reason ID. The membership test passes. | Integration |
| TS-3 | The existing PAREN_FORM test, the `[[ ( true == x ) && true ]]` allow test and its allow row | The PAREN_FORM test passes with its assertions unchanged: the conditional reading reports no uncertain statement and the scan returns true. The `[[ ( true == x ) && true ]]` test and row still give KIND_NOTHING / allow. | Unit / Integration |
| TS-4 | The full suites (`run-destructive-guard.py` and `python3 -m unittest discover -s tests`), and the list of files changed between the implement base commit and the integration HEAD | Both suites pass, and no existing case or test is removed. The list holds none of `em-workflow/hooks/destructive-guard.py`, `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. | Regression |
| TS-5 | Read FR3, AC-5 and TS-3 of `feature-docs/dbracket-opener-arith-scan/SPEC.md`, the TS-3 note of `feature-docs/dbracket-opener-arith-scan/VERIFICATION.md`, the PAREN_FORM comment and the docstring of its test | Each states that `[[ ( a == b ) && true ]]` is uncertain and that the following notion call with `--session "$SID"` is KIND_INSPECTED. SPEC AC-5 also states deny with `git-branch-force-delete`. None calls the form certain, and none cites a task plan's "SPEC discrepancy". `[[ ( true == x ) && true ]]` stays a certain / KIND_NOTHING example in SPEC FR3. | Review |

## Code Quality Verification
- Format: none configured (component `main` has an empty `format_command`).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | AC-1 through AC-6 are satisfied | AC-1: TS-4. AC-2: TS-5. AC-3: TS-3, TS-5. AC-4: TS-1. AC-5: TS-2. AC-6: TS-4. |
| SC-2 | TS-1 through TS-5 pass | The scenarios above |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4 |
| FR2 | none (planner amendment at create-plan) | TS-5 |
| FR3 | none (planner amendment at create-plan) | TS-5 |
| FR4 | task0001 | TS-3, TS-5 |
| FR5 | task0001 | TS-1, TS-3 |
| FR6 | task0001 | TS-2 |
| FR7 | none (planner amendment at create-plan) | TS-3, TS-5 |
| NFR1 | task0001 | TS-4 |
| NFR2 | task0001 | TS-4 |
| NFR3 | task0001 | TS-4 |
| NFR4 | task0001 | TS-2 |

## Manual Testing (E2E Not Possible)
- [ ] TS-5: read the amended FR3, AC-5 and TS-3 of the dbracket-opener-arith-scan SPEC, its VERIFICATION TS-3 note, the PAREN_FORM comment and the docstring of its test, and confirm each states the judgment of TS-5.

## Performance / Security Verification (if applicable)
- NFR2 (static analysis only): `em-workflow/hooks/destructive-guard.py` is unchanged — checked by TS-4.
- TM-1: the command-level reading keeps `[[ ( a == b ) && true ]]` uncertain, and the notion call with `--session "$SID"` after it is inspected and denied — checked by TS-1 (`[KIND_INSPECTED]` and `("deny", "git-branch-force-delete")`), TS-2 (the deny row with its reason ID), TS-4 (the hook is unchanged) and TS-5 (the dbracket-opener-arith-scan SPEC no longer asks for KIND_NOTHING after the form).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-4) | 4 | 4 | 0 | 0 |
| Review scenario (TS-5) | 1 | 0 | 0 | 1 |
| Security (NFR2, TM-1) | 2 | 1 | 0 | 1 |
| Success criteria (SC-1, SC-2) | 2 | 0 | 0 | 2 |
