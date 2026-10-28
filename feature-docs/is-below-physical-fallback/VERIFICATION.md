# Verification Document: is-below-physical-fallback

## Overview
**Feature**: is-below-physical-fallback / **SPEC.md**: `feature-docs/is-below-physical-fallback/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/is-below-physical-fallback/IMPLEMENTATION.md`

## Build Verification
- Command: none. This is a Python component with no build step; the workflow.yaml build_command is empty.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (workflow.yaml project.components.main.test_command), run from the integration worktree root
- Expected: exit code 0 and every test passes. The /proc-dependent case is reported as skipped where `/proc/self/root` is not a directory.
- Coverage target: no coverage tool is configured. Coverage is judged by scenario: every row of the path check's judgment rule (logical path usable, fallback allow, fallback reject, exception) is exercised by at least one scenario below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | From both Fixture working-directory kinds (repo1 and a git worktree), a cd-prefixed approved string whose path is `/proc/self/root/..` followed by the Fixture's inside directory | allow. Skipped when `/proc/self/root` is not a directory | Unit |
| TS-2 | A symbolic link hop at the Fixture root points at the area's task0001/sub directory, and the path is the Fixture root, then hop, then `..`, then sub. The logical path is absent and the physical path is an existing directory inside the area | allow | Unit |
| TS-3 | A symbolic link inside the area points at a nested directory of the area, and `..` after it gives a logical destination that is an existing directory outside the area (for example under the `em-workflow-x` sibling) and a physical destination that is an existing directory inside the area | No output (not allowed) | Unit |
| TS-4 | A symbolic link outside the area combined with `..` makes the logical path absent, while the physical path is (a) outside the area, (b) the area itself, or (c) under the `em-workflow-x` sibling. The cases are added to the existing case table | No output for each of the three forms | Unit |
| TS-5 | The full suite under the workflow.yaml test command, including the existing tests in `tests/test_bash_guard_cd_prefix.py` and `tests/test_hook_classification_pin.py` with unchanged expectations (standard-library import pin, the two `status`-substring pins, and the no-child-process pin) | Every test passes | Integration |
| TS-6 | Read the module docstring of `em-workflow/hooks/bash_guard.py` and the Verbatim execution rule in `em-workflow/references/command-execution-protocol.md` | Both state: if the logical path is an existing directory, the logical and physical paths must both be existing directories strictly below the area; otherwise the physical path alone must be. Neither keeps the single-realpath wording | Review |
| TS-7 | A cd-prefix path containing an embedded NUL character | The path check returns False. Through the hook, the command exits 0, writes nothing to stderr, and receives no allow | Unit |
| TS-8 | The logical path is an existing file, and the physical path is an existing directory strictly below the area | allow | Unit |
| TS-9 | The logical path is not an existing directory, and the physical path (a) does not exist or (b) is an existing file | No output for each | Unit |
| TS-10 | Inspect the tests this feature adds | They import only standard-library modules, use the existing Fixture isolation, and read neither the real user approval store nor the real repository's workflow.yaml | Review |

TS-1 to TS-6 come from SPEC.md. TS-7 to TS-10 cover the SPEC's Edge Cases and the NFR4 and NFR5 requirements, which the SPEC's scenario list did not key.

## Code Quality Verification
- Format: none configured (the workflow.yaml format_command is empty)
- Static analysis: none configured. The executable-text and import invariants are pinned by tests in TS-5.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage table below: every row has a task and a passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-5 and TS-7 to TS-9 pass under the test command; TS-6 and TS-10 are confirmed in review |
| SC-3 | Security requirements are satisfied (FR4, FR5) | TS-3, TS-4, TS-9 and the TM-1 to TM-4 items below |
| SC-4 | Documentation is complete (FR7) | TS-6 |
| SC-5 | Code review is completed | The review phase finishes with no residual critical or high findings |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-8 |
| FR2 | task0001 | TS-3 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-4, TS-9 |
| FR6 | task0001 | TS-5 |
| FR7 | task0001 | TS-6 |
| FR8 | task0001 | TS-1, TS-2, TS-3, TS-4 (the recurrence-detection cases exist in `tests/test_bash_guard_cd_prefix.py` and pass) |
| NFR1 | task0001 | TS-5 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-5 |
| NFR4 | task0001 | TS-7 |
| NFR5 | task0001 | TS-10 |

## Manual Testing (E2E Not Possible)
The project has no E2E framework (SPEC.md: existing E2E tests none), so these items are checked by a person.
- [ ] TS-6: the docstring and protocol wording state the rule (review)
- [ ] TS-10: the new tests are isolated and use the standard library only (review)

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md Performance Tests: none).
- TM-1: when the logical path is an existing directory, the logical and physical paths must both be existing directories strictly below the area, and the fallback is entered only when the logical path is not an existing directory. Checked by TS-3: a logical destination outside the area with a physical destination inside it produces no output.
- TM-2: in the fallback branch, only an existing directory strictly below the area, compared by path components, is allowed. Checked by TS-4 (outside the area, the area itself, the prefix-only sibling) and TS-9 (absent, a file): each produces no output.
- TM-3: the path is resolved in-process only and never given to a child process. Checked by TS-5: the existing no-child-process test passes unchanged. Review also confirms the diff adds no child-process invocation to the path check.
- TM-4: an OSError or ValueError during resolution or comparison makes the path check return False, so the remaining decisions still run, and the hook exits 0 with nothing on stderr. Checked by TS-7.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-10) | 10 | 8 | 0 | 2 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria (SC-1 to SC-5) | 5 | 3 | 0 | 2 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Total | 19 | 15 | 0 | 4 |
