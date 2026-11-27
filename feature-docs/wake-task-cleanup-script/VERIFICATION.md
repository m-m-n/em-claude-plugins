# Verification Document: wake-task-cleanup-script

## Overview

**Feature**: wake-task-cleanup-script / **SPEC.md**: `feature-docs/wake-task-cleanup-script/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/wake-task-cleanup-script/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the
  feature adds a Python script and Markdown only).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (from the repository root).
- Feature modules, runnable on their own:
  `python3 -m unittest tests.test_cleanup_task tests.test_implement_phase_step4_cleanup_script tests.test_implement_phase_guard_compatible_wording tests.test_protocol_git_ops_pass_destructive_guard tests.test_tests_yaml_id_resolution`
- Coverage target: no coverage tool is configured (standard library only).
  Instead, every Acceptance Criterion of task0001 and task0002 maps to at least
  one test, recorded in `test-docs/wake-task-cleanup-script/{T}.tests.yaml`.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Task branch and worktree merged into the integration branch; the script is run with the main tree (not containing the task branch) as the working directory | Worktree registration and branch are gone; exit 0; JSON reports both as `removed` | Integration |
| TS-2 | Task branch not merged into the integration branch | Worktree removed; branch remains; JSON holds the branch name and git's reason; exit 0 | Integration |
| TS-3 | Uncommitted change in the task worktree | Worktree and branch both remain; branch deletion not attempted; JSON holds both reasons; exit 0 | Integration |
| TS-4 | Only the branch absent; only the worktree absent; both absent | Each absent target is `absent`; the other target gets its normal result | Integration |
| TS-5 | Worktree directory deleted, registration left | The worktree is not reported as `absent` | Integration |
| TS-6 | Invalid feature / task ID / integration worktree (path separator, `integration`, empty, leading hyphen, and so on) | Non-zero exit with no git command run; integration branch and integration worktree unchanged | Integration |
| TS-7 | Static scan of the script | No `-D`, `--force` or `-f` in the script text | Unit (static) |
| TS-8 | Static scan of `implement-phase.md` step 4 | No git command line; the script call line is present; JSON-reading and reporting of kept branch name and reason are stated; the no-forced-fallback, step 3 status and step 5 wording remain | Unit (static) |
| TS-9 | Step 4's call line through `destructive-guard.py` and `interpreter-mismatch-guard.py` | Neither guard returns `ask` or `deny` | Unit (guard subprocess) |

## Code Quality Verification

- Format: none configured (`format_command` is empty).
- Static analysis: none configured. TS-7 and TS-8 are the feature's static
  checks.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Every row of the coverage table below has a task and a passing verification |
| SC-2 | All test scenarios pass | `python3 -m unittest discover -s tests` exits 0 on the integrated tree |
| SC-3 | Documentation is complete | TS-8 passes: Step I.2.b step 4 of `em-workflow/references/implement-phase.md` calls the script and states how its JSON is reported |
| SC-4 | Code review is completed | The review phase records no residual critical or high finding |
| SC-5 | The script the step 4 call line names exists and answers its CLI | On the integrated tree, `em-workflow/scripts/cleanup-task.py` exists, and `python3 -B em-workflow/scripts/cleanup-task.py` with no arguments exits 2 with empty standard output |
| SC-6 | NFR4: no version change | The diff between `workflow.implement.base_commit` and the integrated tip changes neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6 |
| FR2 | task0001 | TS-1, TS-2, TS-7 |
| FR3 | task0001, task0002 | TS-2, TS-8 |
| FR4 | task0002 | TS-8, TS-9 |
| FR5 | task0001 | TS-6 |
| FR6 | task0001 | TS-3, TS-5 |
| FR7 | task0001 | TS-1, TS-4, TS-5 |
| FR8 | task0001, task0002 | TS-1, TS-2, TS-3, TS-6, TS-8 |
| NFR1 | task0001 | TS-1 |
| NFR2 | task0002 | TS-9 |
| NFR3 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 (unittest on disposable git repositories) |
| NFR4 | task0001, task0002 | SC-6 (no SPEC scenario) |

## Manual Testing (E2E Not Possible)

None. Every scenario is automated.

## Performance / Security Verification

- Performance: not applicable (SPEC.md has no performance requirement).
- TM-1: inputs validated before any git command — TS-6 (task0001 AC-1):
  every invalid value exits 2 with zero git invocations in the shim log and
  leaves the integration branch, the worktree list and the task branch
  unchanged.
- TM-2: only non-forced removal and deletion, branch skipped after a failed
  worktree removal — TS-7 (no forcing token in the script; no forcing flag
  or prune in any logged git invocation; branch deletion runs from the
  integration worktree) and TS-3 (no branch invocation after a refused
  worktree removal) (task0001 AC-4, AC-7).
- TM-3: script resolved per Step I.0 step 4, never from the current
  directory — TS-8 (task0002 AC-1): step 4 names
  `${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py`, cites Step I.0 step 4, and
  states that an unresolvable script invokes nothing and tries no other
  location.
- TM-4: the call line passes both guards — TS-9 (task0002 AC-5), with and
  without `CLAUDE_BATCH`.
- TM-5: no git command in place of the script on any outcome, reason texts
  treated as data — TS-8 (task0002 AC-2).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Success criteria (SC-1 to SC-6) | 6 | 5 | 0 | 1 (SC-4, review phase) |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
| Requirements coverage (FR1 to FR8, NFR1 to NFR4) | 12 | 12 | 0 | 0 |
