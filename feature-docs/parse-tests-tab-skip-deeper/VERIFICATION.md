# Verification Document: parse-tests-tab-skip-deeper

## Overview
**Feature**: parse-tests-tab-skip-deeper / **SPEC.md**: `feature-docs/parse-tests-tab-skip-deeper/SPEC.md` / **IMPLEMENTATION.md**: not created (reduced tier, single task) / **THREAT-MODEL.md**: `feature-docs/parse-tests-tab-skip-deeper/THREAT-MODEL.md` (verdict `no-applicable-threat`)

Target file: `tests/test_tests_yaml_id_resolution.py` (`_RecordParser.parse_tests` and `TestTabLinesInTestsBlock`).

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0
- Coverage target: not measured (no coverage tool configured); every scenario below is covered by at least one test or check

### Test Scenarios from SPEC.md

In the records below, a tab is a tab character written right after a line's leading spaces. The records are the ones defined in `tasks/task0001.md` (R1 is the ticket's reproduction record: line 4 is a tab line holding `- tests.nope.bad`, line 5 is a deeper line `continued` without a tab, line 6 is `- tests.nope.after`).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC TS-1 / AC-1: extract R1 | AC-1 IDs are exactly `[tests.nope.after]`; errors are exactly `tab in indentation` at line 4 and `tests item continues or nests on a deeper line (multi-line or nested value)` at line 5 | Unit |
| TS-2 | SPEC TS-2 / AC-2: run the record check on R1 | Exactly three lines: the line-4 tab error, the line-5 continues-or-nests error, and one resolution error for `tests.nope.after` under AC-1; no line mentions `tests.nope.bad` | Integration (record check on a temporary root) |
| TS-3 | SPEC TS-3 / AC-3: no tab line precedes a non-dash line deeper than the `tests` key | `tests value is not a block sequence of scalars` is the only error; the deeper lines after it, a dash line included, yield no ID | Unit |
| TS-4 | SPEC TS-4 / AC-4: run the whole suite; existing tests unchanged | `python3 -m unittest discover -s tests` exits 0; the diff modifies no existing test method and no existing attribute of `TestTabLinesInTestsBlock` (`RECORDS` and `TAB_ONLY` included) | Integration (regression) + diff check |
| TS-5 | FR2 boundary: a tab line followed by a non-dash line exactly as deep as the tab line (deeper than the `tests` key) | Unchanged handling: errors are the tab error and `tests value is not a block sequence of scalars`; no ID | Unit |
| TS-6 | SPEC Edge Cases (task0001 AC-5 (a)-(f)): several continuation lines; a deeper tab line inside the continuation range; nothing readable after the range (another field / end of record); another tab line after the range; comparison with the most recent tab line; blank and comment lines between the tab line and the continuation | Each case yields exactly the IDs and errors stated in task0001 AC-5; in particular only the first continuation line is reported, a deeper tab line inside the range is not reported, `tests key has neither a value nor items` is never reported, and a tab line after the range is reported as `tab in indentation` | Unit |
| TS-7 | FR3: the `parse_tests` docstring and the pre-item-scan comments | They describe the continuation handling of a leading tab line (report once, pass over the lines deeper than that tab line, resume the scan for the first item) and that other deeper non-dash lines keep the not-a-block-sequence handling; nothing in them contradicts that | Manual (inspection) |
| TS-8 | NFR2 / NFR3: test-code constraints | The file imports no third-party package (standard library and `unittest` only) and contains no raw tab character (tabs are escape sequences in string literals) | Static check |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured; TS-8 is the only static check for this feature

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR maps to task0001 and at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-6 and TS-8 pass; TS-7 is confirmed by inspection |
| SC-3 | `python3 -m unittest discover -s tests` passes | TS-4 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-6 |
| FR2 | task0001 | TS-3, TS-5 |
| FR3 | task0001 | TS-7 |
| FR4 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-4 |
| NFR2 | task0001 | TS-8 |
| NFR3 | task0001 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] TS-7: read the `parse_tests` docstring and the comments of its pre-item scan and confirm they match the continuation handling of a leading tab line (FR1) and the unchanged handling of other deeper non-dash lines (FR2).

## Performance / Security Verification (if applicable)
- Not applicable: THREAT-MODEL.md's verdict is `no-applicable-threat`, so there is no TM-n item.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Static check (TS-8) | 1 | 1 | 0 | 0 |
| Docstring / comment inspection (TS-7) | 1 | 0 | 0 | 1 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| Total | 8 | 7 | 0 | 1 |
