# Verification Document: launch-guard-common-dir-fallback

## Overview
**Feature**: launch-guard-common-dir-fallback / **SPEC.md**: `feature-docs/launch-guard-common-dir-fallback/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/launch-guard-common-dir-fallback/IMPLEMENTATION.md`

Scenario IDs below use the TS-n form. TS-1 to TS-11 correspond one to one to
SPEC.md's TS1 to TS11. TS-12 is added by the plan so that NFR1 and NFR5 have a
verifying scenario; it restates SPEC.md AC8's full-suite run.

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused set: `python3 -m unittest tests.test_queue_launch_guard_linked_layout tests.test_queue_launch_guard tests.test_merge_unverified_exit_doc_contract`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tool is configured); scenario coverage is tracked by the table below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Stubbed runner returns the common dir `/super/.git/modules/sub` for a segment-free worktree path; the cwd's toplevel is another directory | Project root undetermined; `cwd_outside_project_root` returns no value; exactly one git-common-dir call | Unit |
| TS-2 | Same as TS-1 with `/store/proj.git` | Same as TS-1 | Unit |
| TS-3 | Hook entry point with the TS-1 and TS-2 outputs | Returns 0, stdout empty, exactly one `launched` event | Integration |
| TS-4 | Outputs with a trailing slash or `.` / `..` segments (`/proj/.git/`, `/proj/./x/../.git`) | Normalized first; last element recognized as `.git`; root `/proj` | Unit |
| TS-5 | Common dir `/proj/.git`, worktree path `/elsewhere/em-workflow/f/task0001`, cwd toplevel elsewhere | No denial; root undetermined; no show-toplevel call | Unit |
| TS-6 | Real git: linked worktree L outside the main worktree M, used as project root with a linked layout inside L; launch with cwd L | Allowed, exactly one `launched` event (allow comes from FR2: M does not contain the task path) | Integration |
| TS-7 | Real git: L inside M, otherwise as TS-6 | Allowed, exactly one `launched` event (allow comes from FR3) | Integration |
| TS-8 | FR3 boundaries on the segment-free path | Toplevel equal to the worktree path: denied naming the root. Toplevel outside the root (a proper ancestor of it): denied naming the root | Unit |
| TS-9 | Existing TestLinkedLayoutOtherWorktreeLaunch | Passes with assertions unchanged (integration and task worktree as cwd denied, naming the main worktree, no journal) | Integration |
| TS-10 | Existing TestFallbackCallShape, TestFallbackFailures (fixture paths rewritten under `/proj`) and TestHookDocstring (with presence checks for the new rules) | All pass; one git-common-dir call with the existing shape, cwd and timeout; segment path starts no process; pinned docstring statements present | Unit |
| TS-11 | `tests.test_merge_unverified_exit_doc_contract.TestNeverModifiedFilesAreByteIdentical.test_launch_guard_untouched` | Passes against the changed hook | Unit |
| TS-12 | Full suite, including TestStdlibAndDeterminism | Passes; hook and test module import only the standard library; no sleep or timing module | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A normalized common dir whose last element is not `.git` skips the cwd check | TS-1, TS-2, TS-4 |
| AC2 | A linked-worktree project root does not have correct launches denied, both outside and inside the main worktree | TS-6, TS-7 |
| AC3 | `/super/.git/modules/sub` and `/store/proj.git` are not denied, shown by tests | TS-1, TS-2, TS-3 |
| AC4 | A derived root that does not contain the worktree path skips the cwd check | TS-5 |
| AC5 | Standard linked layout: integration and task worktree launches stay denied | TS-8, TS-9 |
| AC6 | One git-common-dir call | TS-1, TS-10 |
| AC7 | Pinned docstring statements remain and the new rules are written | TS-10 |
| AC8 | Content pin matches the changed hook; the full suite passes | TS-11, TS-12 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR2 | task0001 | TS-5, TS-6 |
| FR3 | task0001 | TS-6, TS-7, TS-8 |
| FR4 | task0001 | TS-1, TS-2, TS-10 (call counts) |
| FR5 | task0001 | TS-10 (segment-path tests) |
| FR6 | task0001 | TS-10 (TestHookDocstring) |
| FR7 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-6, TS-7, TS-8, TS-10 |
| FR8 | task0001 | TS-11 |
| NFR1 | task0001 | TS-12 |
| NFR2 | task0001 | TS-3, TS-5, TS-10 (TestFallbackFailures) |
| NFR3 | task0001 | TS-1, TS-10 |
| NFR4 | task0001 | TS-8, TS-9 |
| NFR5 | task0001 | TS-12 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated.

## Performance / Security Verification (if applicable)
- NFR3: the segment-free path makes exactly one git-common-dir call, with the existing command shape, working directory and timeout — TS-1, TS-2, TS-10.
- NFR4: the standard linked layout keeps its denials, with no `launched` event left behind — TS-8, TS-9.
- TM-1: a common dir whose normalized last element is not `.git`, or a derived root that does not contain the worktree path, leaves the root undetermined; a root containing the cwd's toplevel that strictly contains the worktree path is not denied; every new outcome is exit 0 — checked by TS-1 to TS-7 (unit results, hook entry point exit code and stdout, `launched` count).
- TM-2: FR3's boundaries (toplevel equal to the worktree path; toplevel outside the root) stay denied, FR1 to FR3 never affect the segment path, and existing denial tests keep their assertions — checked by TS-8, TS-9, TS-10.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit scenarios (TS-1, TS-2, TS-4, TS-5, TS-8, TS-10, TS-11) | 7 | 7 | 0 | 0 |
| Integration scenarios (TS-3, TS-6, TS-7, TS-9, TS-12) | 5 | 5 | 0 | 0 |
| Performance / Security (NFR3, NFR4, TM-1, TM-2) | 4 | 4 | 0 | 0 |
| Total | 16 | 16 | 0 | 0 |
