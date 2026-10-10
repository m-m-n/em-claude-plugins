# Verification Document: parse-tests-tab-held-id

## Overview
**Feature**: parse-tests-tab-held-id / **SPEC.md**: `feature-docs/parse-tests-tab-held-id/SPEC.md` / **IMPLEMENTATION.md**: not written (tier `reduced`, single task, no file declared by more than one task) / **THREAT-MODEL.md**: `feature-docs/parse-tests-tab-held-id/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main` declares no build command; the change is a Python test module)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused run of the changed module: `python3 -m unittest tests.test_tests_yaml_id_resolution`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (standard-library `unittest` only, NFR2); coverage is by the scenarios below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction record 1 (SPEC.md AC-1): a readable item, then a tab line at the items' depth, then a tab line deeper than the items, then a readable item, passed to the extraction entry point | AC-1 IDs are `tests.nope.kept`, `tests.nope.after` in this order; the errors are exactly the two `tab in indentation` errors at lines 5 and 6 | Unit |
| TS-2 | Reproduction record 2 (SPEC.md AC-2): as TS-1, but line 6 is a deeper line without a tab | AC-1 IDs are `tests.nope.kept`, `tests.nope.after` in this order; the errors are exactly one `tab in indentation` at line 5 and one `continues or nests` at line 6 | Unit |
| TS-3 | Existing behavior (SPEC.md AC-3, AC-4): the existing `TestTabLinesInTestsBlock` tests and the rest of `tests/test_tests_yaml_id_resolution.py` run unmodified, including the standard-library self-inspection test, followed by the full discover run | Every existing test passes with no existing test method, record or expected value modified; the discover run exits 0 | Unit (regression) |
| TS-4 | Comment and docstring of the item loop's tab-line handling (FR5; added by planning, not in SPEC.md) | The tab-line comment and the method docstring state that no ID is held after any tab line and that only a deeper tab line directly after a readable ID takes it back; the phrase "the held state stays" appears nowhere in the file | Inspection |
| TS-5 | No raw tab character in the test module (NFR3; added by planning, not in SPEC.md) | A text search for a tab character in `tests/test_tests_yaml_id_resolution.py` finds none | Static check |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | Every functional requirement is implemented and tested | Functional Requirements Coverage below: each FR/NFR maps to task0001 and at least one TS |
| SC-2 | Every test scenario passes | TS-1 to TS-3 pass in the test run; TS-4 and TS-5 hold on inspection |
| SC-3 | `python3 -m unittest discover -s tests` passes | Run the command; exit code 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-2 |
| FR5 | task0001 | TS-4 |
| FR6 | task0001 | TS-1, TS-2 |
| NFR1 | task0001 | TS-3 |
| NFR2 | task0001 | TS-3 (existing standard-library self-inspection test) |
| NFR3 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] TS-4: read the changed tab-line comment and the method docstring of the record parser's tests-block method; confirm they match FR1 and FR2 and no longer claim that the held state stays after a tab line

## Performance / Security Verification (if applicable)
- TM-1: after every tab line no ID is held, so a deeper line following a tab line takes back nothing, and every tab line stays reported — checked by the task0001 AC-3 tests in the test run: for both reproduction records the record check lists exactly four error lines, which are both extraction errors plus one resolution error each for `tests.nope.kept` and `tests.nope.after`. TS-1 and TS-2 additionally pin the extracted IDs and the full error lists.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS-1, TS-2, TS-3) | 3 | 3 | 0 | 0 |
| Static check (TS-5) | 1 | 1 | 0 | 0 |
| Inspection (TS-4) | 1 | 0 | 0 | 1 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| **Total** | 6 | 5 | 0 | 1 |
