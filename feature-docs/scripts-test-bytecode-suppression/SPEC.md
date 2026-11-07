# Feature: scripts-test-bytecode-suppression

## Overview

After a full run of `python3 -m unittest discover -s tests`, no `__pycache__`
exists under `em-workflow/scripts/`. Files under the plugin are copied into the
distribution as-is, whether or not git tracks them. Requirements document:
`feature-docs/scripts-test-bytecode-suppression/REQUIREMENTS.md`.

## Objectives

- After a full run of `python3 -m unittest discover -s tests`, no `__pycache__`
  is created under `em-workflow/scripts/`. Files under the plugin are copied
  into the distribution as-is, whether or not git tracks them.

## User Stories

No user stories are defined in the requirements analysis. Acceptance criteria:

- [ ] AC1 (FR1, FR2, FR3): Starting from a state where
  `em-workflow/scripts/__pycache__` does not exist, after running
  `python3 -m unittest discover -s tests` at the repository root, no
  `__pycache__` exists under `em-workflow/scripts/`.
- [ ] AC2 (NFR4): In the same full run, every existing test passes.
- [ ] AC3 (FR1, FR3): After an in-process load, `sys.dont_write_bytecode` is
  back to its pre-call value (whether True or False). It is restored even when
  the module body raises.
- [ ] AC4 (FR2, FR3): After running the test that launches
  `report-name-entry.py` on its own, no `__pycache__` exists under
  `em-workflow/scripts/`.

## Technical Requirements

### Functional Requirements
- **FR1:** Every place where a test module under tests/ loads
  `em-workflow/scripts/*.py` into the process with
  `importlib.util.spec_from_file_location` + `exec_module` sets
  `sys.dont_write_bytecode` to True only for the duration of the load, and
  afterwards restores the pre-call value (also when the module body raises).
  Both module-level calls (at test-module import time) and calls made during
  test execution are in scope.
- **FR2:** When a test launches a script under `em-workflow/scripts/` as a
  child process and that child process loads a sibling script into its own
  process (currently the path where `report-name-entry.py` loads
  `validate-worker-output.py` with `exec_module`, launched from `run_entry` in
  `tests/test_report_name_entry.py`), that launch carries bytecode suppression
  (the interpreter's `-B`, or the environment variable
  `PYTHONDONTWRITEBYTECODE=1` passed at launch).
- **FR3:** The suppression of FR1 / FR2 is performed by each load site and each
  launch site itself, and does not depend on a `sys.dont_write_bytecode` value
  set by another test module (currently `tests/test_merge_ci_wait.py` sets it
  to True at module level and never restores it) or on execution order.

### Non-Functional Requirements
- **NFR1:** The script bodies under `em-workflow/scripts/` are not changed.
  Changes are limited to the test code (tests/).
- **NFR2:** The process-wide `os.environ` is not modified. Bytecode suppression
  for child processes is limited to the arguments or env of each individual
  launch (tests such as `tests/test_sca_child_env_path_filtering.py` inspect
  child-process environment variables, so changing the process-wide
  environment could affect their verdicts).
- **NFR3:** Test code uses only the standard library (the convention in
  test/README.md).
- **NFR4:** The verification content of existing tests (assertions and the
  behavior under test) is not changed.

## Implementation Approach

### Architecture

- In-process loads (FR1): save `sys.dont_write_bytecode`, set it to True, load,
  and restore it in `finally` — the same form as the existing precedents
  (`load_hook` in `tests/test_destructive_guard_extglob_units.py`, and
  `tests/test_codex_hook_tty_reaper.py`). Whether this is written in each file
  or collected into a shared helper under tests/ is decided at planning.
- Child-process launches that load a sibling script (FR2): add `-B` or
  `PYTHONDONTWRITEBYTECODE=1` to that single launch's arguments or env (NFR2).

### Dependencies

**Internal Dependencies:**
- None

**External Dependencies:**
- Python standard library only (NFR3)

### File Structure

Changes are limited to tests/ (NFR1).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/scripts-test-bytecode-suppression/**`
- `test-docs/scripts-test-bytecode-suppression/**`

`feature-docs/scripts-test-bytecode-suppression/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/scripts-test-bytecode-suppression/**` covers
`test-docs/scripts-test-bytecode-suppression/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/scripts-test-bytecode-suppression/` directory at all; the declared
`test-docs/scripts-test-bytecode-suppression/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

- [ ] TS-1: Check whether `em-workflow/scripts/__pycache__` exists before and
  after a full run (`python3 -m unittest discover -s tests`) - it does not
  exist after the run. (FR1, FR2, FR3)
- [ ] TS-2: Point the load routine at a probe module placed in a test-only
  temporary directory, and check that the flag is True during the load, that
  it returns to the starting value afterwards for each of the starting values
  True and False, and that it is restored even when the module body raises
  (precedent: `TestHookLoadWritesNoBytecode` in
  `tests/test_destructive_guard_extglob_units.py`; because a probe is used, a
  broken load routine still writes nothing under `em-workflow/`). (FR1, FR3)
- [ ] TS-3: Run a test module that loads at module level (for example
  `tests/test_check_plugin_invariants.py`,
  `tests/test_decide_tier_final_score.py`,
  `tests/test_final_path_correction.py`) on its own - no
  `em-workflow/scripts/__pycache__` is created. (FR1, FR3)
- [ ] TS-4: Run `tests/test_report_name_entry.py` on its own - no bytecode for
  `validate-worker-output` is written via the child process. (FR2, FR3)

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

Not applicable.

## Error Handling

- When the loaded module body raises, `sys.dont_write_bytecode` is still
  restored to its pre-call value (FR1, AC3).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC1 through AC4 (see User Stories) are satisfied
- [ ] All test scenarios pass

## Assumptions

- Only `em-workflow/scripts/` is in scope. Loads under `em-workflow/hooks/`
  (for example the `queue_stop_guard.py` load in
  `tests/test_report_name_entry.py`) belong to hook-test-bytecode-suppression
  and are not handled by this feature.
- Suppression for in-process loads takes the same "save, set True, restore in
  finally" form as the existing precedents (`load_hook` in
  `tests/test_destructive_guard_extglob_units.py`, and
  `tests/test_codex_hook_tty_reaper.py`). Whether it is written in each file
  or collected into a shared helper under tests/ is decided at planning.
- The module-level `sys.dont_write_bytecode = True` (never restored) in
  `tests/test_merge_ci_wait.py` is not changed by this feature.
- Production execution of `report-name-entry.py` (which may write bytecode
  when loading its sibling `validate-worker-output.py`) is out of scope. The
  goal of this feature is limited to the full test run.
- A file launched directly as the main script (`python3 <script>.py`) does not
  write bytecode for itself, so child-process launches that do not load a
  sibling need no suppression. Source execution via `runpy.run_path` also
  writes no bytecode.
- The plugin version is not touched (`.claude/rules/core-plugin-version-bump.md`).
  Changes are only under tests/, so no file under the plugin changes.

## Open Questions

None. No requirement has `status: tbd`.

## References

- Requirements: `feature-docs/scripts-test-bytecode-suppression/REQUIREMENTS.md`
- Precedents: `tests/test_destructive_guard_extglob_units.py`,
  `tests/test_codex_hook_tty_reaper.py`
- Test code convention: test/README.md
