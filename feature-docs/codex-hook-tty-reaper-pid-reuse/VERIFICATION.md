# Verification Document: codex-hook-tty-reaper-pid-reuse

## Overview
**Feature**: codex-hook-tty-reaper-pid-reuse / **SPEC.md**: `feature-docs/codex-hook-tty-reaper-pid-reuse/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-hook-tty-reaper-pid-reuse/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the scripts
  are run by the Python interpreter as-is)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted: `python3 -m unittest tests.test_codex_hook_tty_reaper`
- Expected: exit code 0, no failures or errors; the Linux real-process tests run
  (not skipped) on the verification host
- Coverage target: not measured (no coverage tooling in `project.components`);
  completeness is judged by every automated TS-n below having a passing test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Fake process table: anchor A; unrelated older process C (start 100) whose recorded parent is P; P recreated under A with start 200. Run `main()` | C receives neither SIGTERM nor SIGKILL | Unit |
| TS-2 | Target with start 100; the fake stat read returns 100, then the PID's instance becomes start 200 | No signal is recorded against the start-200 instance (the pidfd points at instance 100) | Unit |
| TS-3 | Parent and child with equal start times under the anchor | The child receives SIGTERM | Unit |
| TS-4 | The hook's ancestor chain has a link whose parent started later than its child; paired case with equal start times on the chain | No signal in the first case; targets are stopped in the paired case | Unit |
| TS-5 | Run once with the pidfd-open seam missing (or None) and once with pidfd open raising OSError(ENOSYS) | No signal is sent; the PID-addressed signal function is never called | Unit |
| TS-6 | ProcessLookupError from pidfd open or pidfd signal-send on one target; separately OSError(EMFILE) or PermissionError | Other targets still receive signals in the first case; no later signal is sent in the second | Unit |
| TS-7 | Record the pidfd used for each target's SIGTERM and SIGKILL; inspect fake pidfds after `main()` returns, error paths included | SIGTERM and SIGKILL of a target use the same pidfd; no fake pidfd remains open | Unit |
| TS-8 | Existing byte-identity test of the two copies, the defaults test updated for the pidfd functions, and the existing Linux real-process tests | All pass; both commands above pass | Integration |

### Additional Scenarios (planner-defined, for requirements without a SPEC.md scenario)
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-9 | Read the module docstring of `em-workflow/scripts/codex-hook-tty-reaper.py` | Flow steps 4, 6, 8 and 10 and the errors paragraph state the start-time link rule (descendants and ancestor chain), signalling through a pidfd held until SIGKILL, and that nothing is stopped when pidfd is unavailable (FR9) | Manual |
| TS-10 | Read the import list of both copies | Only standard-library modules are imported (NFR1) | Manual |
| TS-11 | Existing tests for silent operation: exit 0 on every path, no stdout / stderr, no environment reads, nothing executed on import, no `__pycache__` under the plugin directories | All pass unchanged in intent (NFR2) | Unit |
| TS-12 | Existing tests for target selection, order (deepest first, same depth by ascending PID) and timing (SIGTERM, 0.5 s grace, SIGKILL), migrated to the pidfd fakes | All pass with their assertions kept (NFR3) | Unit |
| TS-13 | Diff of the integration branch against `workflow.implement.base_commit` | `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are not changed (NFR4) | Manual |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Copies: the two copies are byte-identical (covered by TS-8)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Reproduction 1 sends no signal to C | TS-1 |
| AC-2 | Reproduction 2 sends neither SIGTERM nor SIGKILL to the start-200 instance | TS-2 |
| AC-3 | Equal-start descendant links are followed; the child stays a target | TS-3 |
| AC-4 | A later-started parent on the ancestor chain stops all signalling; equal start times do not | TS-4 |
| AC-5 | pidfd functions missing or ENOSYS: no signal, PID-addressed signalling never called | TS-5 |
| AC-6 | ProcessLookupError skips one target; other OSErrors (EMFILE included) stop later signals | TS-6 |
| AC-7 | SIGKILL goes through the pidfd opened before SIGTERM; no pidfd left open after `main()` | TS-7 |
| AC-8 | Copies byte-identical; both unittest commands pass, real-process tests included | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-7 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-6 |
| FR6 | task0001 | TS-4 |
| FR7 | task0001 | TS-8 |
| FR8 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-8 |
| FR9 | task0001 | TS-9 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-11 |
| NFR3 | task0001 | TS-12 |
| NFR4 | task0001 | TS-13 |

## Manual Testing (E2E Not Possible)
- [ ] TS-9: module docstring states the new rules (FR9)
- [ ] TS-10: both copies import standard-library modules only (NFR1)
- [ ] TS-13: no plugin version file changed (NFR4)

## Performance / Security Verification
- NFR3 timing: SIGTERM, then the 0.5 s grace, then SIGKILL — unchanged; checked by TS-12
- TM-1: descendant links adopted only when the parent's start time is not later than the child's; anchor absent stops nothing — checked by TS-1 and TS-3
- TM-2: an ancestor-chain link with a later-started parent stops all signalling — checked by TS-4
- TM-3: pidfd obtained before the identity check and SIGTERM sent only through it — checked by TS-2
- TM-4: SIGKILL sent through the same pidfd held since SIGTERM, after a repeated check — checked by TS-7
- TM-5: no fallback to PID-addressed signalling when pidfd is unavailable — checked by TS-5

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-13) | 13 | 10 | 0 | 3 |
| Success criteria (AC-1 to AC-8) | 8 | 8 | 0 | 0 |
| Performance (NFR3 timing) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
