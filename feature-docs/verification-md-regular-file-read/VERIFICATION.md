# Verification Document: verification-md-regular-file-read

## Overview
**Feature**: verification-md-regular-file-read / **SPEC.md**: `feature-docs/verification-md-regular-file-read/SPEC.md` / **IMPLEMENTATION.md**: none (reduced tier, single task) / **THREAT-MODEL.md**: `feature-docs/verification-md-regular-file-read/THREAT-MODEL.md`

## Build Verification
- Command: none. workflow.yaml `build_command` is empty, and the Python
  scripts need no build step.
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (workflow.yaml
  `test_command`)
- Focused command: `python3 -m unittest tests.test_rework_docs_only_validator_rules`
- Coverage target: not measured, because no coverage tool is configured.
  Every task Acceptance Criterion maps to at least one test.
- Expected: exit code 0 for both commands. On Linux the FIFO and /dev/zero
  cases run and are not reported as skipped.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The feature-dir VERIFICATION.md is a FIFO, and the CLI validates rework-planner output in a subprocess with a timeout | No timeout. Exit 1 and exactly one rework-index error, containing "cannot be read as text" and the path | Integration |
| TS-2 | The feature-dir VERIFICATION.md is a symlink to /dev/zero, and the CLI validates in a subprocess with a timeout | No timeout. Exit 1 and exactly one rework-index error | Integration |
| TS-3 | The baseline-dir VERIFICATION.md is a FIFO or a symlink to /dev/zero, a declared rename needs the baseline set, and the CLI validates in a subprocess with a timeout | No timeout. Exit 1 and exactly one rework-index error naming the baseline-side path | Integration |
| TS-4 | The loader is given a FIFO, a symlink to /dev/zero and a symlink to a regular file | Each returns the unreadable state without blocking | Unit |
| TS-5 | The loader is given a regular file over the byte limit | Returns the unreadable state, and the file is not loaded in full | Unit |
| TS-6 | The existing AC-7 tests run: directory, bytes that are not UTF-8, missing file, valid rename | Same results as before the change | Unit/Integration |

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty)
- Static analysis: none configured
- Standard library only (NFR1): `TestStandardLibraryOnly` in the focused
  module passes, and the change adds no import from outside the standard
  library to the validator or to the test module.
- Version fields untouched (NFR3): the diff from the implement step's base
  commit to the integration branch head changes no `version` value in
  `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SPEC AC-1 | Feature-dir FIFO: exit 1 without a timeout, and a rework-index error naming the path | TS-1 |
| SPEC AC-2 | Feature-dir symlink to /dev/zero: exit 1 and a rework-index error | TS-2 |
| SPEC AC-3 | Baseline-dir FIFO or symlink to /dev/zero, when the baseline set is needed: exit 1 and a rework-index error | TS-3 |
| SPEC AC-4 | An over-limit regular file is unreadable and is not read in full | TS-5 |
| SPEC AC-5 | `TestRenameCoverageDiff` and `TestRenameDiffFixtures` all pass | TS-6 |
| SPEC AC-6 | The new tests are in `tests/test_rework_docs_only_validator_rules.py`, and the focused command passes | Focused command |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | Full test command |
| SC-3 | `python3 -m unittest tests.test_rework_docs_only_validator_rules` passes | Focused command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR2 | task0001 | TS-5 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-6 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| NFR1 | task0001 | `TestStandardLibraryOnly` (Code Quality Verification); no scenario ID |
| NFR2 | task0001 | TS-1, TS-2, TS-3 (subprocess timeout and memory cap), plus the manual review item below |
| NFR3 | task0001 | Version-field diff check (Code Quality Verification); no scenario ID |

## Manual Testing (E2E Not Possible)
- [ ] Review the new tests (NFR2):
  - every case that gives the loader or the CLI a FIFO or a /dev/zero link
    runs in a child process with a timeout of seconds and a memory cap, and
    none calls the loader inside the test runner itself;
  - no case is repeated in a loop or run in parallel.

## Performance / Security Verification (if applicable)
- NFR2: each FIFO and /dev/zero case is bounded by a subprocess timeout of
  seconds and by a memory cap for the child. With the fix reverted, a case
  fails at the timeout or the cap and does not hang the run or exhaust
  memory. This is checked by the task's TDD red phase and by the manual
  review item above.
- TM-1: the loader opens without following a symlink and without blocking,
  and confirms a regular file before reading. A non-regular file gives the
  unreadable state and the loader never raises. This is checked by TS-4 (each
  non-regular case returns unreadable in its child process before the
  timeout) and by TS-1, TS-2 and TS-3 (each CLI run ends before the timeout
  with exit 1 and exactly one rework-index error).
- TM-2: the read is bounded at the byte limit plus one byte. This is checked
  by TS-5: an over-limit file is unreadable, and for a sparse file many times
  the limit, the memory the call allocates stays under twice the limit.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 6 | 6 | 0 | 0 |
| Code quality (NFR1, NFR3) | 2 | 2 | 0 | 0 |
| Success criteria | 9 | 9 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Performance (NFR2) | 1 | 1 | 0 | 0 |
| Manual review | 1 | 0 | 0 | 1 |
