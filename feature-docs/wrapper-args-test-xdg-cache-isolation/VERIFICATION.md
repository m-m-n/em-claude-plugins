# Verification Document: wrapper-args-test-xdg-cache-isolation

## Overview
- **Feature**: wrapper-args-test-xdg-cache-isolation
- **SPEC.md**: `feature-docs/wrapper-args-test-xdg-cache-isolation/SPEC.md`
- **IMPLEMENTATION.md**: not produced (reduced tier, one task, so no file is shared between tasks)
- **THREAT-MODEL.md**: `feature-docs/wrapper-args-test-xdg-cache-isolation/THREAT-MODEL.md` (verdict `no-trust-boundary`)

## Build Verification
- Command: none. Component `main` has no build command in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command (feature scope): `python3 -m unittest tests.test_codex_hook_wrapper_args tests.test_codex_litellm_launch_home_location`
- Command (project, from workflow.yaml `project.components.main.test_command`): `python3 -m unittest discover -s tests`
- Expected: exit code 0 for both.
- Coverage target: not applicable. The tests use the standard library only
  (NFR2), with no coverage tooling. Coverage is pinned by the scenarios below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Nothing is left in an inherited absolute-path `XDG_CACHE_HOME`. The test process's `XDG_CACHE_HOME` points at a test-owned empty directory, set for that test only. `LITELLM_PATH` is launched through `_run_wrapper_pid()` in readonly and readwrite. | Each launch exits 0 with one stub invocation. The directory's contents equal its pre-launch snapshot (no `em-workflow`). | Unit |
| TS-2 | The detector does not miss the creation. The same directory is handed to the wrapper as `XDG_CACHE_HOME` through `extra_env`, so the variable is not removed. `LITELLM_PATH` is launched in readonly and readwrite. | Each launch exits 0 with one stub invocation, and `em-workflow` exists in the directory. The same checker as TS-1 raises an assertion failure. | Unit |
| TS-3 | No regression in the existing suites, and the change set stays confined. Run the feature-scope command (1) with `XDG_CACHE_HOME` unset, and (2) with it set to a fresh empty directory from `mktemp -d`. Then (3) list the change set with `git diff --name-only` from the implement step's `base_commit` in workflow.yaml to `HEAD`. | (1) and (2) pass in full, and after (2) the directory holds no `em-workflow` entry. (3) lists neither `run_codex_exec.sh`, nor `tests/test_codex_litellm_launch_home_location.py`, nor any path under `em-workflow/`, `em-review/`, `plugin-dev/` or `.claude-plugin/`. | Integration |

## Code Quality Verification
- Format: none configured in workflow.yaml.
- Static analysis: none configured in workflow.yaml.
- `test_module_imports_are_all_stdlib` checks the module's own imports. It runs inside TS-3.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | After the module runs with an absolute-path `XDG_CACHE_HOME`, `$XDG_CACHE_HOME/em-workflow` has not been created | TS-3 step (2) |
| AC-2 | A recurrence test covers `--litellm` readonly and readwrite: exit 0, one stub invocation, no `em-workflow`. Removing the removal makes it fail | TS-1, plus the mutation check under Manual Testing; TS-2 covers the same failure path automatically |
| AC-3 | A negative proof shows the same check detects `em-workflow` when `XDG_CACHE_HOME` is left in place | TS-2 |
| AC-4 | Both modules pass. Neither wrapper nor `tests/test_codex_litellm_launch_home_location.py` has a diff | TS-3 steps (1) and (3) |
| SC-all-implemented | All functional requirements are implemented and tested | Functional Requirements Coverage table below |
| SC-all-scenarios | All test scenarios pass | TS-1, TS-2, TS-3 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-2 |
| NFR1 | task0001 | TS-3 step (3): neither wrapper has a diff |
| NFR2 | task0001 | TS-3: `test_module_imports_are_all_stdlib` passes |
| NFR3 | task0001 | TS-3 steps (1) and (2): both modules pass. Step (3): the launch-home module has no diff |
| NFR4 | task0001 | TS-3 step (3): no path under a plugin directory or `.claude-plugin/` changed |

## Manual Testing (E2E Not Possible)
- [ ] Mutation check for SPEC AC-2 ("removing the removal makes the test fail"):
  1. In the working tree, without committing, take the `XDG_CACHE_HOME` removal out of `_run_wrapper_pid()`.
  2. Point the shell's `XDG_CACHE_HOME` at a scratch directory from `mktemp -d`, so nothing reaches the real cache.
  3. Run only the TS-1 test, by its test id, and confirm it fails on the `em-workflow` entry.
  4. Restore the file to its committed content.

## Performance / Security Verification (if applicable)
- No performance requirement.
- THREAT-MODEL.md's verdict is `no-trust-boundary`, so there are no TM-n items.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit test scenarios (TS-1, TS-2) | 2 | 2 | 0 | 0 |
| Integration scenarios (TS-3) | 1 | 1 | 0 | 0 |
| Mutation check (SPEC AC-2) | 1 | 0 | 0 | 1 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 4 | 3 | 0 | 1 |
