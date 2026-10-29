# Verification Document: cleanup-guard-cap-sync-test

## Overview
**Feature**: cleanup-guard-cap-sync-test / **SPEC.md**: `feature-docs/cleanup-guard-cap-sync-test/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; one task, no file declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/cleanup-guard-cap-sync-test/THREAT-MODEL.md` (verdict `no-trust-boundary`)

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change is Python test code with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Targeted run: `python3 -m unittest tests.test_failed_run_cleanup_guard`
- Expected: exit code 0; none of the new cap-consistency tests is skipped
- Coverage target: not measured (standard-library-only suite with no coverage tool); every scenario below maps to at least one test or check

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The real SKILL.md text and the hook's `LINEAGE_CAP_COUNT` / `HARD_CAP_ROUNDS` are passed to the extraction-and-comparison function | Empty mismatch list | Unit |
| TS2 | In-memory copy with the lineage cap label number (`系譜 cap（値 N）`) changed to another integer; the replacement is asserted to apply exactly once | At least one mismatch, containing the changed value and naming `LINEAGE_CAP_COUNT` | Unit |
| TS3 | In-memory copy with the lineage cap reach number (`累積出現回数が N に達した`) changed; exactly-once replacement asserted | At least one mismatch, containing the changed value and naming `LINEAGE_CAP_COUNT` | Unit |
| TS4 | In-memory copy with the hard cap label number (`hard cap（値 N）`) changed; exactly-once replacement asserted | At least one mismatch, containing the changed value and naming `HARD_CAP_ROUNDS` | Unit |
| TS5 | In-memory copy with the hard cap reach number (the phrase after `batch.verify_rework.rounds` that crosses a line break, ending in `が N に達した`) changed; exactly-once replacement asserted | At least one mismatch, containing the changed value and naming `HARD_CAP_ROUNDS` | Unit |
| TS6 | Copies with the lineage cap bullet removed, with the hard cap bullet removed, and with a label reworded so its pattern no longer matches | Each yields at least one mismatch naming the missing item; never an empty list, never a skip | Unit |
| TS7 | Copy with a cap bullet duplicated inside the list | At least one mismatch naming the ambiguous item | Unit |
| TS8 | Copy in which only the number of the lineage cap bullet's "ID が N 回目" phrase is changed (SPEC Edge Cases); exactly-once replacement asserted | Empty mismatch list (that number is not read) | Unit |
| TS9 | NFR1: imports added to `tests/test_failed_run_cleanup_guard.py` | Standard-library modules only | Static (inspection) |
| TS10 | NFR2: run the targeted module, comparing `git status --porcelain` before and after | Identical output; SKILL.md and the hook are not written | Integration (command) |
| TS11 | NFR3: placement and execution of the new tests | They live in `tests/test_failed_run_cleanup_guard.py` and run and pass under both the discover command and the targeted command | Integration (command) |
| TS12 | NFR4: names of the added classes and test methods | Classes `Test<Behavior>`; methods `test_<condition>_<expected_result>` | Static (inspection) |
| TS13 | NFR5: `git diff` from the implement step's `base_commit` to HEAD | No change to `em-workflow/hooks/failed-run-cleanup-guard.py` or `em-workflow/skills/develop/SKILL.md`; outside `feature-docs/cleanup-guard-cap-sync-test/` and `test-docs/cleanup-guard-cap-sync-test/`, the only changed path is `tests/test_failed_run_cleanup_guard.py` | Static (command) |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A test reads the real SKILL.md, compares its four cap numbers with `LINEAGE_CAP_COUNT` / `HARD_CAP_ROUNDS` by the FR3 rules, and passes on the current tree | TS1 |
| AC2 | Changing any one of the four numbers in an in-memory copy is reported as a mismatch, one test case per number, with the real file untouched | TS2, TS3, TS4, TS5, TS10 |
| AC3 | A text whose cap bullets cannot be found, or match more than once, is reported as a mismatch, neither consistent nor skipped | TS6, TS7 |
| SC1 | FR1-FR6 are implemented and tested | Functional Requirements Coverage below |
| SC2 | TS1-TS7 pass | Test Verification commands |
| SC3 | NFR1-NFR5 are met | TS9, TS10, TS11, TS12, TS13 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS4, TS5 |
| FR2 | task0001 | TS1 |
| FR3 | task0001 | TS1, TS2, TS3, TS4, TS5 |
| FR4 | task0001 | TS5, TS6, TS7, TS8 |
| FR5 | task0001 | TS1, TS2, TS3, TS4, TS5, TS6, TS7, TS8 |
| FR6 | task0001 | TS2, TS3, TS4, TS5, TS10 |
| NFR1 | task0001 | TS9 |
| NFR2 | task0001 | TS10 |
| NFR3 | task0001 | TS11 |
| NFR4 | task0001 | TS12 |
| NFR5 | task0001 | TS13 |

## Manual Testing (E2E Not Possible)
- [ ] Real-file sensitivity (the goal's "changing the SKILL.md value makes the test fail"): export HEAD into a disposable directory outside the repository and outside the integration worktree, change one cap number in that copy's SKILL.md, and run the new real-file test from that copy's root. The test fails with a mismatch showing the changed value. Discard the copy; no file in the repository or the integration worktree is edited.

## Performance / Security Verification (if applicable)
- Not applicable: SPEC.md states no performance requirement, and THREAT-MODEL.md's verdict is `no-trust-boundary` (no TM-n).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS1-TS8) | 8 | 8 | 0 | 0 |
| Command checks (TS10, TS11, TS13) | 3 | 3 | 0 | 0 |
| Static inspection (TS9, TS12) | 2 | 0 | 0 | 2 |
| Manual testing (real-file sensitivity) | 1 | 0 | 0 | 1 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 14 | 11 | 0 | 3 |
