# Verification Document: hook-test-bytecode-suppression

## Overview
- **Feature**: hook-test-bytecode-suppression
- **SPEC.md**: `feature-docs/hook-test-bytecode-suppression/SPEC.md`
- **IMPLEMENTATION.md**: `feature-docs/hook-test-bytecode-suppression/IMPLEMENTATION.md`
- **THREAT-MODEL.md**: `feature-docs/hook-test-bytecode-suppression/THREAT-MODEL.md` (verdict `no-trust-boundary`)

## Build Verification
- Command: none. Neither component (`main`, `destructive-guard`) has a build
  command in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command (component `main`): `python3 -m unittest discover -s tests`
- Command (component `destructive-guard`):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: exit code 0 for both.
- Coverage target: not applicable. The tests use the standard library only
  (NFR2) and there is no coverage tooling. The scenarios below pin the
  coverage.

### Precondition for TS-1, TS-2 and TS-3 (IMPLEMENTATION.md D3)
1. The environment neither disables nor redirects bytecode writing:
   `PYTHONDONTWRITEBYTECODE` and `PYTHONPYCACHEPREFIX` are unset, and
   `python3` runs without its `-B` option. Otherwise the three scenarios
   pass without proving anything.
2. No `__pycache__` directory exists anywhere under `em-workflow/hooks/`.
   Check with `find em-workflow/hooks -name __pycache__`, which must print
   nothing. `__pycache__/` is git-ignored, so leftovers do not show in
   `git status`. Remove any leftover with `gio trash`, never with `rm`.
3. Run TS-1, TS-2 and TS-3 in that order from the repository root, and
   repeat the step-2 check after each one. A passing scenario leaves the
   starting state for the next.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC-1 / FR1) From the precondition state, run `python3 -m unittest tests.test_destructive_guard_extglob_units` | Exit 0. Afterwards `find em-workflow/hooks -name __pycache__` prints nothing | Integration |
| TS-2 | (AC-2 / FR2) From the precondition state, run `python3 -m unittest tests.test_destructive_guard_lexer_agreement` | Exit 0. Afterwards `find em-workflow/hooks -name __pycache__` prints nothing | Integration |
| TS-3 | (AC-3, AC-4 / FR3, NFR1, NFR2, NFR3) From the precondition state, run `python3 -m unittest discover -s tests` | Exit 0, all tests pass, including the `TestModuleContract` class of both modules (standard-library-only imports). Afterwards `find em-workflow/hooks -name __pycache__` prints nothing, which covers `em-workflow/hooks/tests/` | Integration |
| TS-4 | (AC-4 / NFR1) Run `python3 em-workflow/hooks/tests/run-destructive-guard.py` | Exit 0, every case passes | Integration |
| TS-5 | (NFR3) Call `load_hook()` (extglob_units) and `_load_hook()` (lexer_agreement) with `sys.dont_write_bytecode` set explicitly to False, then to True. The new test class of each module does this; it runs inside TS-1, TS-2 and TS-3 | For each starting value, the flag is True while the loaded module body executes, and equals the starting value after the call. Each test leaves the flag at the value it held when the test started | Unit |
| TS-6 | (FR1, FR2, NFR3; SPEC Edge Cases) Call each helper with a loaded module body that raises, with starting values False and True. The new test classes do this; it runs inside TS-1, TS-2 and TS-3 | After the call the flag equals the starting value, and the caller receives the raised exception | Unit |
| TS-7 | (SPEC A-1, REQUIREMENTS.md 9.1) List the change set with `git diff --name-only` from the implement step's `base_commit` in workflow.yaml to `HEAD` | Outside `feature-docs/hook-test-bytecode-suppression/` and `test-docs/hook-test-bytecode-suppression/`, only `tests/test_destructive_guard_extglob_units.py` and `tests/test_destructive_guard_lexer_agreement.py` appear. No path under `em-workflow/`, `em-review/`, `plugin-dev/` or `.claude-plugin/` appears | Integration |

## Code Quality Verification
- Format: none configured in workflow.yaml.
- Static analysis: none configured in workflow.yaml.
- Each module's `TestModuleContract` checks its own imports (NFR2). It runs
  inside TS-3.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | After `python3 -m unittest tests.test_destructive_guard_extglob_units` runs from a state with no `__pycache__` under `em-workflow/hooks/`, there is still none | TS-1 |
| AC-2 | After `python3 -m unittest tests.test_destructive_guard_lexer_agreement` runs from that state, there is still none | TS-2 |
| AC-3 | After `python3 -m unittest discover -s tests` runs from that state, there is still none | TS-3 |
| AC-4 | All existing tests pass | TS-3, TS-4 |
| SC-all-implemented | All functional and non-functional requirements are implemented and tested | Functional Requirements Coverage table below |
| SC-all-scenarios | All test scenarios pass | TS-1 to TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-5, TS-6 |
| FR2 | task0001 | TS-2, TS-5, TS-6 |
| FR3 | task0001 | TS-3 |
| NFR1 | task0001 | TS-3, TS-4 |
| NFR2 | task0001 | TS-3: both modules' `TestModuleContract` passes |
| NFR3 | task0001 | TS-3, TS-5, TS-6 |

## E2E Testing
None. The project has no E2E framework (SPEC.md Test Scenarios).

## Performance / Security Verification (if applicable)
- No performance requirement.
- THREAT-MODEL.md's verdict is `no-trust-boundary`, so there are no TM-n
  items.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit test scenarios (TS-5, TS-6) | 2 | 2 | 0 | 0 |
| Integration scenarios (TS-1 to TS-4, TS-7) | 5 | 5 | 0 | 0 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 7 | 7 | 0 | 0 |
