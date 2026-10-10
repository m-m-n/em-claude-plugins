# Verification Document: parse-tests-tab-handling

## Overview
**Feature**: parse-tests-tab-handling / **SPEC.md**: `feature-docs/parse-tests-tab-handling/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; a single task, no file declared by more than one task) / **THREAT-MODEL.md**: `feature-docs/parse-tests-tab-handling/THREAT-MODEL.md`

## Build Verification
- Command: none (Python; `project.components.main.build_command` is empty)
- Expected: not applicable — the module is compiled when the test run imports it

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Module-level command: `python3 -m unittest tests.test_tests_yaml_id_resolution` (from the repository root)
- Expected: exit code 0, no failures and no errors
- Coverage target: not measured (no coverage tooling in the project; NFR1 keeps the module on the standard library). FR1-FR4 coverage is asserted scenario by scenario through TS-1 to TS-4.

`<TAB>` below denotes one literal tab character.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A `tests` block whose first item is a tab line (`      <TAB>- tests.nope.bad`) followed by `      - tests.nope.good` (ticket reproduction step 1) | `acs['AC-1'] == ['tests.nope.good']`; AC-1 errors include `tab in indentation` and none is `inconsistent indentation of fields`; `check_record` reports exactly one resolution error, for `tests.nope.good` of AC-1 | Unit |
| TS-2 | A `tests` block consisting only of tab lines, followed by another field (`    red_confirmed: true`) and followed by end of file | AC-1 has exactly one `tab in indentation` error per tab line and no other error; `neither a value nor items` is not reported; `acs['AC-1'] == []` | Unit |
| TS-3 | A tab continuation line deeper than the item (`        <TAB>continued` after `      - tests.nope.fragment`), followed by `      - tests.nope.control` (ticket reproduction step 2) | `acs['AC-1'] == ['tests.nope.control']`; AC-1 reports `tab in indentation`; `tests.nope.fragment` appears in no error line of `check_record` | Unit |
| TS-4 | A tab line at the item's own depth (`      <TAB>x`) between `      - tests.nope.kept` and `      - tests.nope.after` | `acs['AC-1'] == ['tests.nope.kept', 'tests.nope.after']`; AC-1 has exactly one error, `tab in indentation` | Unit |
| TS-5 | The module-level run and the full run via `discover` | Both exit 0; every existing test case is still present with unchanged expected values | Integration |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | SPEC AC-1: IDs after a first-item tab line are extracted and resolved (FR1) | TS-1 passes |
| AC-2 | SPEC AC-2: a tab-only `tests` block reports only the tab errors (FR2) | TS-2 passes for both terminations |
| AC-3 | SPEC AC-3: the fragment before a deeper tab continuation line is dropped (FR3) | TS-3 passes |
| AC-4 | SPEC AC-4: a same-depth tab line keeps the IDs around it (FR4) | TS-4 passes |
| AC-5 | SPEC AC-5: both runs succeed, no existing test removed or changed (FR5, NFR1, NFR2, NFR3) | TS-5 passes; `git diff --name-only {workflow.implement.base_commit}..HEAD` lists only `tests/test_tests_yaml_id_resolution.py` plus paths under `feature-docs/parse-tests-tab-handling/` and `test-docs/parse-tests-tab-handling/`; the manual diff review below holds |
| S-1 | All functional requirements are implemented and tested | Every row of the coverage table below maps to task0001 and to passing scenarios |
| S-2 | All test scenarios pass | TS-1 to TS-5 pass |
| S-3 | Code review is completed | The `review` step of `workflow.yaml` is `completed` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-1, TS-2, TS-3, TS-4 (the regression tests themselves, including ticket reproduction steps 1 and 2), TS-5 |
| NFR1 | task0001 | TS-5 (the module's existing standard-library self-inspection test runs in both commands) |
| NFR2 | task0001 | TS-5, plus the manual diff review below |
| NFR3 | task0001 | TS-5, plus the changed-path check in Success Criteria AC-5 |

## Manual Testing (E2E Not Possible)
- [ ] NFR2 diff review: in the diff of `tests/test_tests_yaml_id_resolution.py` against `workflow.implement.base_commit`, no existing test method or subTest case is removed and no existing expected value (assertion target, expected reason string, expected ID list, expected error count) is changed.

## Performance / Security Verification (if applicable)
- TM-1: every tab line inside a `tests` block yields its own `tab in indentation` error, so a record whose `tests` block holds only tab lines (or whose tab lines hide or cut items) fails instead of passing as an empty or shorter list — checked by TS-2 (exactly one tab error per tab line, including the two-tab-line variant) and by the task0001 test that the generated per-record test fails, listing the tab errors with the resolution errors, for each record of TS-1 to TS-4.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Success criteria (AC-1 to AC-5, S-1 to S-3) | 8 | 7 | 0 | 1 |
| Manual diff review (NFR2) | 1 | 0 | 0 | 1 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| **Total** | 15 | 13 | 0 | 2 |
