# Verification Document: merge-pr-test-git-env-isolation

## Overview
**Feature**: merge-pr-test-git-env-isolation / **SPEC.md**: `feature-docs/merge-pr-test-git-env-isolation/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, one task, no file declared by more than one task) / **THREAT-MODEL.md**: `feature-docs/merge-pr-test-git-env-isolation/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change is a Python test module).
- Expected: nothing to build.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from `project.components.main.test_command`), plus the focused run `python3 -m unittest tests.test_merge_pr`.
- Expected: exit code 0 for both. The verify run's environment holds no `GIT_` variable unless a check below says otherwise.
- Coverage: not measured (the project registers no coverage tool). Completeness is judged by TS-1 to TS-3 and the TM items below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A decoy repository with one commit is created and its refs, HEAD and local configuration listing are recorded. The process environment is changed, in a scoped way, so that `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` point at the decoy. `MergePrTestCase.setUp` and the cleanups of an instance are then run in-process. | The decoy's record is unchanged (no new commit, no `user.name` / `user.email` / `commit.gpgsign` entry). The fixture repository under the instance's temporary directory has the `initial` commit. | Unit |
| TS-2 | setUp runs with `GIT_DIR`, `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_PARAMETERS` set in the changed environment. | The `GIT_`-prefixed key sets of `self.env` and `self.real_env` are exactly {`GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL`}, and `GIT_CONFIG_GLOBAL` equals `os.devnull`. | Unit |
| TS-3 | The whole existing `tests.test_merge_pr` suite runs with no `GIT_` variable in the environment. | Every existing test passes. | Integration |

## Code Quality Verification
- Format: none registered (`format_command` is empty).
- Static analysis: none registered.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | With `GIT_DIR` pointing at another repository, `python3 -m unittest tests.test_merge_pr` adds no commit and no `user.name` / `user.email` setting to that repository. | TS-1 (in-process) and M1 (the module run with `GIT_DIR` set in the shell) |
| AC2 | After setUp, the environment setUp built has no `GIT_` key other than `GIT_CONFIG_NOSYSTEM` and `GIT_CONFIG_GLOBAL`, and `GIT_CONFIG_GLOBAL` equals `os.devnull`. | TS-2 |
| AC3 | The regression test in `tests/test_merge_pr.py` covers inherited `GIT_` variables, fails against the old setUp and passes after the fix. | TS-1 and TS-2 pass; the red observation before the fix is in `test-docs/merge-pr-test-git-env-isolation/task0001.tests.yaml` |
| AC4 | `python3 -m unittest tests.test_merge_pr` passes in full, and no file under `em-workflow/` changes. | TS-3 and M2 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TM-1 |
| FR2 | task0001 | TS-1, TS-2, TM-2 |
| FR3 | task0001 | TS-1; red-before-green record in the task's test record |
| FR4 | task0001 | TS-3 |
| NFR1 | task0001 | TS-3, M2 |
| NFR2 | task0001 | TS-3; review of the module's imports (standard library only) |
| NFR3 | task0001 | TS-1, TM-3, M1 |
| NFR4 | task0001 | TS-3; review that no test reaches the network or the real `~/.claude` |

## Manual Testing (E2E Not Possible)
Both items are shell checks the verify phase can run without a human. Every path they create lives in a scratch directory outside the repository.
- [ ] M1: Reproduction check from the goal (SPEC.md AC1). Create a scratch repository with one commit in a temporary directory outside the repository. Record its refs (every ref with its object id), HEAD and local configuration listing. From the integration worktree root, run `python3 -m unittest tests.test_merge_pr` with `GIT_DIR` set to the scratch repository's git directory and `GIT_WORK_TREE` set to the scratch repository. The run exits 0. Record the scratch repository again with `GIT_DIR` and `GIT_WORK_TREE` unset: the record is identical, so it has no new commit and no `user.name`, `user.email` or `commit.gpgsign` entry. This also covers the regression test's own isolation when the outer process already carries `GIT_` variables (NFR3).
- [ ] M2: Change-set check (NFR1). The diff from `workflow.implement.base_commit` to the integration tip names only `tests/test_merge_pr.py`, `test-docs/merge-pr-test-git-env-isolation/` and `feature-docs/merge-pr-test-git-env-isolation/`. It names no path under `em-workflow/` and not `.claude-plugin/marketplace.json`.

## Performance / Security Verification
- TM-1: setUp removes every inherited `GIT_`-prefixed key before adding its own values (THREAT-MODEL.md TB-1). Checked by TS-1 (the decoy repository is unchanged, the fixture commit is in the temporary directory) and TS-2 (exact `GIT_` key set of `self.env` and `self.real_env`).
- TM-2: setUp sets `GIT_CONFIG_GLOBAL` to `os.devnull` next to `GIT_CONFIG_NOSYSTEM=1`. Checked by TS-2 (`GIT_CONFIG_GLOBAL` equals `os.devnull` in both environments, also when a different value was inherited).
- TM-3: the regression test builds its decoy inside its own temporary directory with a `GIT_`-free environment, and changes the process environment only in a scoped way that is restored on failure too. Checked by TS-1 (the process environment is the same before and after each regression test, and a second repository named by outer `GIT_DIR` / `GIT_WORK_TREE` is unchanged) and by M1.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-3) | 3 | 3 | 0 | 0 |
| Success criteria (AC1 to AC4) | 4 | 4 | 0 | 0 |
| Requirements coverage | 8 | 8 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Shell checks (M1, M2) | 2 | 0 | 0 | 2 |
