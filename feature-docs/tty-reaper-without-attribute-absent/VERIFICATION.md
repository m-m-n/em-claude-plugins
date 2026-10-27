# Verification Document: tty-reaper-without-attribute-absent

## Overview
**Feature**: tty-reaper-without-attribute-absent / **SPEC.md**: `feature-docs/tty-reaper-without-attribute-absent/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier, single task with no shared files)

## Build Verification
- Command: none configured (workflow.yaml project.components.repo-tests has an empty build_command)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (workflow.yaml project.components.repo-tests)
- Targeted command: `python3 -m unittest tests.test_codex_hook_tty_reaper`
- Coverage target: none configured

### Test Scenarios from SPEC.md
TS-1 to TS-4 are SPEC.md's unit scenarios. TS-5 to TS-7 turn SPEC.md AC-4,
FR4, NFR1-NFR3 and the Success Criteria into checkable scenarios. These TS-n
IDs are this feature's own; the acN / tsN tokens inside existing test method
names belong to an earlier feature's numbering.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Apply without_attribute to a stand-in module that has no attribute `name` (AC-1; FR1, FR2) | No error; `name` is absent inside and after the block; a stand-in that records attribute deletions and assignments records none for `name` | Unit |
| TS-2 | Apply without_attribute to a stand-in module whose `name` holds a unique object, with a normal exit and with an exception raised inside the block (AC-2; FR3) | `name` is absent inside the block; after the block it holds the identical original object in both cases; the raised exception propagates as the same object | Unit |
| TS-3 | On a stand-in module without `name`, raise an exception inside the block (AC-1; FR1, FR2) | The exception propagates as the same object; `name` is still absent after the block | Unit |
| TS-4 | Nest without_attribute twice on the os module's pidfd_open, and separately on the signal module's pidfd_send_signal (AC-3; FR1, FR5) | The inner use raises no error although the attribute is already absent; after both blocks each attribute is back in its pre-test state (identical object if present, absent if absent) | Unit |
| TS-5 | Run the two existing missing-function tests test_ac5_ts5_a_missing_pidfd_open_function_leaves_a_default_that_stops_nothing and test_ac5_ts5_a_missing_pidfd_send_signal_function_leaves_a_default_that_stops_nothing with their helper calls unmodified (FR4) | Both pass; the helper's name and its parameters (module, name) are unchanged | Unit |
| TS-6 | Run `python3 -m unittest tests.test_codex_hook_tty_reaper` and `python3 -m unittest discover -s tests` (AC-4; NFR1, NFR3) | Both exit 0 with no failures or errors, including TestThisModule.test_ts14_module_imports_are_all_stdlib | Integration |
| TS-7 | List the files changed on the integration branch relative to its base branch (NFR2) | Outside feature-docs/tty-reaper-without-attribute-absent/ and test-docs/tty-reaper-without-attribute-absent/, only tests/test_codex_hook_tty_reaper.py is changed; em-workflow/scripts/codex-hook-tty-reaper.py and em-review/scripts/codex-hook-tty-reaper.py are unchanged | Repository check |

## Code Quality Verification
- Format: none configured (empty format_command) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC.md AC-1 through AC-4 are satisfied | TS-1 to TS-7 all pass |
| SC-2 | `python3 -m unittest tests.test_codex_hook_tty_reaper` passes | TS-6 |
| SC-3 | `python3 -m unittest discover -s tests` passes | TS-6 |
| SC-4 | TestThisModule.test_ts14_module_imports_are_all_stdlib passes | TS-6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3, TS-4 |
| FR2 | task0001 | TS-1, TS-3 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-1, TS-4 (the regression tests exist and pass) |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-7 |
| NFR3 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- None. TS-4 reproduces the missing-function condition in-process, so no
  Python build without the pidfd functions is required.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-7) | 7 | 7 | 0 | 0 |
| Success criteria (SC-1 to SC-4) | 4 | 4 | 0 | 0 |
| Build / format / static analysis | 0 | 0 | 0 | 0 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 11 | 11 | 0 | 0 |
