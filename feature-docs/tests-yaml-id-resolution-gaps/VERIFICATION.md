# Verification Document: tests-yaml-id-resolution-gaps

## Overview
**Feature**: tests-yaml-id-resolution-gaps / **SPEC.md**: `feature-docs/tests-yaml-id-resolution-gaps/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/tests-yaml-id-resolution-gaps/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty in workflow.yaml)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0; every test passes, including each per-record test generated from `test-docs/`, the zero-record guard and the new scan-error test
- Coverage target: not measured (no coverage tool; the suite stays standard-library only, NFR1). Coverage is by scenario: each of FR1-FR5 has dedicated fixture tests (TS-1 to TS-5)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The bare `tests` is passed to canonical_id_failure and, inside a record, to check_record | Rejected with a reason starting with `not a canonical ID`; module cache and module search path unchanged; IDs of two or more segments still pass | Unit |
| TS-2 | check_record on an AC mixing a mapping element and a nonexistent ID, an AC with a duplicated tests key, a record with a duplicated AC key, and an AC holding a multi-line value fragment | Resolution errors of the readable IDs and the extraction errors are both listed; the fragment and other error elements are not resolved | Unit |
| TS-3 | Listing one subdirectory under `test-docs/` raises a permission error (simulated) | The scan-error test fails naming the repository-relative path and the reason; tests for readable records remain; a root without `test-docs/` produces no scan error | Unit |
| TS-4 | A fixture module whose `load_tests` returns None, and a substituted loader returning a suite that raises while iterated, go through resolve_id and check_record | Each becomes that ID's resolution error; judging of later IDs continues | Unit |
| TS-5 | A fixture TestCase subclass whose own `__init__` creates a marker; its `__init__` method ID goes through resolve_id | Rejected with `not a test method`; the marker is not created | Unit |
| TS-6 | The doc-contract test `tests/test_tests_yaml_id_rules_docs.py` checks the README for the two-or-more-segment wording and the non-execution guarantee range | Checks pass on the README; removing either wording makes the corresponding check fail | Integration |
| TS-7 | `python3 -m unittest discover -s tests` on the integrated tree | All suites pass, including every real-repository per-record test and the zero-record guard | Integration |
| TS-8 | (Added at planning; not in SPEC.md) The integrated diff from the implement step's `base_commit` to the integration tip | No path under `em-workflow/`, `em-review/`, `plugin-dev/` or `.claude-plugin/`; `tests/test_exit4_ac2_test_id_drift.py`, `feature-docs/tests-yaml-test-id-resolution/SPEC.md` and `feature-docs/tests-yaml-test-id-resolution/reviews/round1.yaml` unchanged | Integration |

## Code Quality Verification
- Format: none (`format_command` is empty in workflow.yaml)
- Static analysis: none configured
- Dependency check: the two changed Python test modules import only standard-library modules (NFR1; reviewed on the integrated diff)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The bare `tests` in a record is rejected as `not a canonical ID` without import; IDs of two or more segments still pass | TS-1 |
| AC-2 | A mapping element's extraction error and `tests.nope.A.b`'s resolution error are both returned; error elements are not resolved | TS-2 |
| AC-3 | A subdirectory listing failure fails a collected test naming path and reason; readable records are still checked; a missing `test-docs/` leaves only the zero-record guard failing | TS-3 |
| AC-4 | A non-suite loader result and an exception during iteration each become the ID's resolution error; later IDs are still judged | TS-4 |
| AC-5 | A method ID naming a class's own `__init__` is rejected as `not a test method` before Loader confirmation | TS-5 |
| AC-6 | README requires two or more segments and states the guarantee range; the module docstring states the same range; the README wording is pinned by the doc-contract test | TS-6 and Manual Testing item 1 |
| AC-7 | The discovery run passes; old-behavior tests are corrected; the task0001.tests.yaml ID names the renamed test and passes the record check | TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0003 | TS-2 |
| FR3 | task0004 | TS-3 |
| FR4 | task0002 | TS-4 |
| FR5 | task0002 | TS-5 |
| FR6 | task0001, task0002, task0003, task0005 | TS-6; Manual Testing items 1-3 |
| FR7 | task0001, task0002, task0003, task0004, task0005 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR8 | task0001, task0003 | TS-7 |
| NFR1 | task0001, task0002, task0003, task0004, task0005 | TS-7; Code Quality dependency check |
| NFR2 | task0001, task0002, task0003, task0004, task0005 | TS-7 |
| NFR3 | task0003, task0004 | TS-7, TS-8 |
| NFR4 | task0001, task0002, task0003, task0004, task0005 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] 1. The module docstring and the resolver-section comment of `tests/test_tests_yaml_id_resolution.py` state the same guarantee range as the README (IMPLEMENTATION.md D1) and no longer claim that resolved objects are never called or instantiated (SPEC AC-6, FR6)
- [ ] 2. The README's Structural resolution names the dunder rejection, and its Loader confirmation names the non-suite result and the exception during iteration as failure conditions (FR6)
- [ ] 3. The docstrings of canonical_id_failure, extract_text and check_record and the Extraction section comment describe the FR1 and FR2 behavior (FR6)

## Performance / Security Verification (if applicable)
- Not applicable: SPEC.md declares no performance requirement, and THREAT-MODEL.md's verdict is `no-trust-boundary` (no TM-n items)

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Code quality (dependency check) | 1 | 0 | 0 | 1 |
| Success criteria (AC-1 to AC-7) | 7 | 7 | 0 | 1 (AC-6, docstring half) |
| Manual testing | 3 | 0 | 0 | 3 |
| Performance / security | 0 | 0 | 0 | 0 |
