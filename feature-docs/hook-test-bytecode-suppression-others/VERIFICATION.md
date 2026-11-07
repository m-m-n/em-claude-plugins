# Verification Document: hook-test-bytecode-suppression-others

## Overview

**Feature**: hook-test-bytecode-suppression-others / **SPEC.md**: `feature-docs/hook-test-bytecode-suppression-others/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/hook-test-bytecode-suppression-others/IMPLEMENTATION.md`

All commands run from the integration worktree root. Run TS-1 before TS-2, so
that the single-module checks start from a state no full-suite run has
touched. Run every command in the foreground, one at a time.

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Coverage target: not measured (the test setup uses the Python standard
  library only and has no coverage tool)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | For each of the seven modules in turn: confirm that no directory named `__pycache__` exists anywhere beneath `em-workflow/hooks/` or `em-review/hooks/`; run `python3 -m unittest tests.<module>`; confirm again. Modules: `test_queue_stop_guard`, `test_queue_stop_guard_routeback_record`, `test_failed_run_cleanup_guard`, `test_hooks_registration`, `test_queue_failure_net_cross_hook`, `test_muse_guard`, `test_consultation_harness_chain` | Every run exits with code 0, and after every run no `__pycache__` exists anywhere beneath either directory | Integration (command-level) |
| TS-2 | Run `python3 -m unittest discover -s tests` | Exit code 0; all tests pass, as before the change | Integration |
| TS-3 | The regression tests added to the seven modules set the bytecode flag's starting value to off and to on inside the test, and check the flag's value after each load and that loading suppresses bytecode writing | The regression tests pass, and each restores the process's flag value afterwards; they run as part of TS-1 and TS-2 | Unit |

### Edge cases (SPEC.md)

| Edge case | Where it is checked |
|-----------|---------------------|
| EC1: the module execution step raises | Regression tests in each modified module (task AC-3), run by TS-2 |
| EC2: in-process `main()` of `run_hook_in_process` imports a hook module after the load | TS-1, run of `test_failed_run_cleanup_guard` |
| EC3: a hook body imports a sibling hook module during the load | TS-1, all seven runs |
| EC4: `test_neither_plugins_hooks_tests_directory_gained_a_file` does not inspect the hook directory root | TS-1, runs of `test_muse_guard` and `test_consultation_harness_chain` |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured
- Diff check: the change touches only the seven modules under `tests/` named in
  SPEC.md FR1 (plus feature documents); no file under `em-workflow/` or
  `em-review/` changes, and `tests/test_merge_ci_wait.py`,
  `tests/test_destructive_guard_extglob_units.py` and
  `tests/test_destructive_guard_lexer_agreement.py` are unchanged.
- Import check: the seven modules import only Python standard library modules
  (NFR1).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS-1, TS-3 |
| SC-2 | All test scenarios pass | TS-1, TS-2, TS-3 |
| SC-3 | AC-1: each of the seven modules run alone leaves no `__pycache__` beneath either hook directory | TS-1 |
| SC-4 | AC-2: the full suite passes as before | TS-2 |
| SC-5 | Code review is completed | Review phase result |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1 (no `__pycache__` after single-module runs); TS-3 (flag on during the load) |
| FR2 | task0001, task0002 | TS-1 (single-module runs, no reliance on `tests/test_merge_ci_wait.py`); TS-3 (starting value set inside the test) |
| NFR1 | task0001, task0002 | TS-2; import check under Code Quality Verification |
| NFR2 | task0001, task0002 | TS-2 (discover run); TS-1 (single-module runs) |

## Manual Testing (E2E Not Possible)

- None. Every scenario above is checked by commands.

## Performance / Security Verification (if applicable)

- Not applicable: SPEC.md has no performance requirement, and THREAT-MODEL.md's
  verdict is `no-trust-boundary` (no mitigation to verify).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 3 (TS-1, TS-2, TS-3) | 3 | 0 | 0 |
| Code quality | 2 (diff check, import check) | 2 | 0 | 0 |
| Success criteria | 5 | 4 | 0 | 1 (review result) |
| Security (TM-n) | 0 | 0 | 0 | 0 |
