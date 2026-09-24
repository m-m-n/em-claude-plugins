# Verification Document: version-bump-entry-count-guard

## Overview

**Feature**: version-bump-entry-count-guard / **SPEC.md**: `feature-docs/version-bump-entry-count-guard/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/version-bump-entry-count-guard/IMPLEMENTATION.md`

## Build Verification

- Command: none. `build_command` is empty in workflow.yaml `project.components.main`, so there is no build step to verify.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Coverage target: not measured. No coverage tool is configured, and the suite is standard-library unittest. Coverage is judged per scenario below.

### Test Scenarios from SPEC.md

TS-1 to TS-5 come from SPEC.md. TS-6 to TS-9 are derived from SPEC.md AC-3, AC-4 and AC-5, which TS-1 to TS-5 do not fully cover.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | AC-1: build, inside the test, a marketplace mapping with em-review, em-workflow and a third plugin entry, and pass it to the em-workflow entry name/source check | The check passes | Unit |
| TS-2 | AC-2: build, inside the test, a mapping whose em-workflow entry has a source other than ./em-workflow, and pass it to the same check | Assertion failure | Unit |
| TS-3 | AC-2: build, inside the test, a mapping in which the em-workflow entry is renamed, so no entry is named em-workflow, and pass it to the same check | Assertion failure | Unit |
| TS-4 | AC-3, AC-4: text search of `tests/test_recycled_task_id_contract_version_bump.py` and `test-docs/recycled-task-id-contract/task0002.tests.yaml` for MARKETPLACE_NAME_SOURCE_BASELINE, test_entry_count_unchanged, test_every_entry_name_and_source_matches_baseline, TestMarketplaceOtherFieldsUnchanged | No match in either file | Static check |
| TS-5 | AC-5: run the full suite from the repository root | 0 failures and 0 errors. The retained em-workflow name/source test passes against the current marketplace.json (em-review / em-workflow) | Integration |
| TS-6 | AC-3 (derived): read the module's docstrings and comments | The module docstring's AC-3 description covers only the em-workflow entry's name and source. No docstring or comment describes checking the entry count, the array gaining or losing entries, or every entry's name/source | Static check (review) |
| TS-7 | AC-4 (derived): read `acceptance_tests.AC-3` in task0002.tests.yaml and run each ID in its tests list alone with unittest | tests lists exactly one ID, which runs and passes the retained em-workflow test. red_reason does not mention the entry count. The AC-4 red_reason counts ("10 tests", "1462 tests") are unchanged. The file parses as YAML | Static check + Unit |
| TS-8 | AC-5 (derived): list the files changed on the integration branch since the implement base commit, excluding feature-docs/version-bump-entry-count-guard/** and test-docs/version-bump-entry-count-guard/** | Exactly the two files in NFR1. Nothing under em-workflow/, no change to .claude-plugin/marketplace.json, no plugin version change | Static check |
| TS-9 | AC-5 (derived): inspect the module's imports and how it reads marketplace.json | Imports come only from unittest / json / re / pathlib. marketplace.json is read by JSON parsing, not by pattern matching over its text | Static check |

## Code Quality Verification

- Format: none. `format_command` is empty in workflow.yaml.
- Static analysis: none configured. The import constraint (NFR2) is checked by TS-9.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every row verified |
| SC-2 | All test scenarios pass | TS-1 to TS-9 all meet their expected results |
| SC-3 | `python3 -m unittest discover -s tests` passes at the repository root (NFR4) | TS-5 |
| SC-4 | Changes stay within the two NFR1 files | TS-8 |
| SC-5 | SPEC AC-1: a third plugin entry does not fail the module | TS-1 |
| SC-6 | SPEC AC-2: em-workflow name or source drift fails the module | TS-2, TS-3, TS-5 (retained test present and passing) |
| SC-7 | SPEC AC-3: removed identifiers and count/whole-array descriptions are gone from the module | TS-4, TS-6 |
| SC-8 | SPEC AC-4: the task0002 AC-3 tests list names only existing tests and none of the removed ones | TS-4, TS-7 |
| SC-9 | SPEC AC-5: the suite passes and the change set is limited | TS-5, TS-8, TS-9 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4, TS-5 |
| FR2 | task0001 | TS-2, TS-3, TS-5 |
| FR3 | task0001 | TS-6 |
| FR4 | task0001 | TS-4, TS-7 |
| FR5 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-9 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-5 |

## E2E Testing

None. The project has no E2E framework (`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)

- [ ] TS-6: a human judges the wording of the module's docstrings. It must describe AC-3 as the em-workflow entry's name/source check only.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit | TS-1, TS-2, TS-3 | 3 | 0 | 0 |
| Integration | TS-5 | 1 | 0 | 0 |
| Static check | TS-4, TS-7, TS-8, TS-9 | 4 | 0 | 0 |
| Static check (review) | TS-6 | 0 | 0 | 1 |
| Total | 9 | 8 | 0 | 1 |
