# Verification Document: cd-prefix-non-directory-dotdot

## Overview
**Feature**: cd-prefix-non-directory-dotdot / **SPEC.md**: `feature-docs/cd-prefix-non-directory-dotdot/SPEC.md` / **IMPLEMENTATION.md**: not written (tier `reduced`, single task; the task plan is `feature-docs/cd-prefix-non-directory-dotdot/tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/cd-prefix-non-directory-dotdot/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (`project.components.main.test_command`)
- Targeted command: `python3 -m unittest tests.test_bash_guard_cd_prefix`
- Expected: exit code 0 for both. A skipped test is allowed only for the `/proc/self/root` tests, and only when `/proc/self/root` is not a directory.
- Coverage target: not measured (no coverage tool configured). Every task Acceptance Criterion maps to at least one test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `cd "<area>/afile/../task0001" && make test` through the hook (logical path `<area>/task0001` exists; the realpath used to remove `afile/..` lexically) | No output (silent), exit 0, empty stderr; the case is in `PATH_CASES` | Unit |
| TS-2 | `cd "<area>/task0001/does-not-exist/.." && make test` through the hook (logical path `<area>/task0001`) | No output (silent), exit 0, empty stderr; the case is in `PATH_CASES` | Unit |
| TS-3 | `cd "/proc/self/root/..<area>/afile/../task0001" && make test` through the hook, from the main worktree and from a git worktree (logical path absent, fallback branch) | Silent; skipped when `/proc/self/root` is not a directory | Unit |
| TS-4 | Fixture check for each added form: the operating system's resolution of the path as written is not an existing directory, while the lenient (non-strict) realpath is an existing directory strictly below the area. With the realpath function made to ignore any strict request, `is_below()` still returns False for the added forms | Both facts hold for every added form; the decision does not depend on strict-mode realpath | Unit |
| TS-5 | Existing `FALLBACK_ALLOW_CASES` (link, `..`, name) and the `/proc/self/root/..` + worktree-path AC-1 test | Still allow (the component before `..` is a link to a directory, so the as-written resolution succeeds) | Unit |
| TS-6 | Regression: `python3 -m unittest tests.test_bash_guard_cd_prefix` and `python3 -m unittest discover -s tests` | Both pass. Includes `TestAc7StandardLibraryOnly`, `TestNulInPath`, `test_ac1_no_child_process_uses_the_prefixed_path`, and `TestPathConditionWording`. | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured. The standard-library-only and no-`status`-substring constraints are enforced by `TestAc7StandardLibraryOnly` (TS-6).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | A regular file or a missing component followed by `..` is never allowed as a cd prefix, whether or not the logical path exists (SPEC AC-1) | TS-1, TS-2, TS-3 silent |
| SC-2 | The forms are pinned as silent cases in `PATH_CASES` and pass (SPEC AC-2) | TS-1, TS-2 in `PATH_CASES`; TS-3 test present |
| SC-3 | Every existing cd-prefix test passes (SPEC AC-3) | TS-5, TS-6 |
| SC-4 | The decision does not depend on strict-mode realpath behavior (SPEC AC-4) | TS-4 |
| SC-5 | All functional requirements implemented and tested; all test scenarios pass | Coverage table below; TS-1 to TS-6 pass |
| SC-6 | Code review completed | `workflow.yaml` review step completed with no residual critical/high finding |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-1, TS-2, TS-3 |
| FR5 | task0001 | TS-1, TS-2, TS-4 |
| FR6 | task0001 | TS-3 |
| NFR1 | task0001 | TS-4 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- None required. The project has no E2E framework, and every scenario is automated through the hook subprocess tests.

## Performance / Security Verification (if applicable)
- TM-1: the allowance is not widened and no deny is added. Check: every pre-existing case in `tests/test_bash_guard_cd_prefix.py` passes without modification: `ALLOW_CASES`, `FALLBACK_ALLOW_CASES`, the `/proc/self/root` AC-1 test, `SYNTAX_CASES`, the pre-existing `PATH_CASES` entries including the TM1 / TM2 cases, and the refusal and declared-unapproved deny tests (TS-5, TS-6). Also check the diff: the logical-side computation and the strictly-below comparison of `is_below()` are unchanged.
- TM-2: the cd-prefix path never reaches a child process. Check: a direct test calls `is_below()` for the added forms with the child-process entry points replaced by failing stand-ins and observes no call. `test_ac1_no_child_process_uses_the_prefixed_path` passes (TS-6). Also check the diff: no process is spawned and the working directory is not changed inside `is_below()`.
- TM-3: a resolution error yields False, never an exception out of the hook. Check: a direct test makes the new as-written resolution raise OSError and ValueError and expects False. A NUL inserted into an added form returns False, and `TestNulInPath` passes without modification (TS-6).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Success criteria (SC-1 to SC-6) | 6 | 5 | 0 | 1 |
| Requirements coverage (FR1–FR6, NFR1–NFR4) | 10 | 10 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual testing | 0 | 0 | 0 | 0 |
