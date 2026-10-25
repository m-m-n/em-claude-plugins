# Feature: wrapper-args-test-xdg-cache-isolation

## Overview

`tests/test_codex_hook_wrapper_args.py` launches the Codex wrapper through
`_run_wrapper_pid()`. This feature makes that harness remove `XDG_CACHE_HOME`
from the environment it passes to the wrapper, and adds tests that detect a
regression. Only the test side changes.

## Objectives

- Running `tests/test_codex_hook_wrapper_args.py` creates nothing in the
  user's real cache (under `XDG_CACHE_HOME`), and the test results do not
  depend on the `XDG_CACHE_HOME` of the execution environment.

## Technical Requirements

### Functional Requirements

- **FR1: The harness removes `XDG_CACHE_HOME`.** `_run_wrapper_pid()` in
  `tests/test_codex_hook_wrapper_args.py` removes `XDG_CACHE_HOME` from the
  environment it passes to the wrapper, in the same way it removes
  `CODEX_HOME` and `CODEX_OTLP_ENDPOINT`. An explicit override through
  `extra_env` is applied after the removal, as before.
- **FR2: A test that detects recurrence.**
  `tests/test_codex_hook_wrapper_args.py` contains a test that, with the
  caller's environment `XDG_CACHE_HOME` pointing at an absolute path (a
  test-owned directory outside the run's working directory), launches the
  `--litellm` path (readonly / readwrite) through `_run_wrapper_pid()` and
  confirms that no `em-workflow` directory is created in that directory (its
  contents are the same as before the launch).
- **FR3: The detector is non-vacuous.** A negative proof shows that, when the
  wrapper is launched without removing `XDG_CACHE_HOME`, the same check
  detects the creation of the `em-workflow` directory and fails (the same
  style as the module's existing `TestCheckerDetectsRegressions`).

### Non-Functional Requirements

- **NFR1 - Wrapper behavior unchanged:** `em-workflow/scripts/run_codex_exec.sh`
  and `em-review/scripts/run_codex_exec.sh` are not changed. The fix is made
  on the test side only.
- **NFR2 - Standard library only:** The tests import only the standard
  library (`test_module_imports_are_all_stdlib` continues to pass).
- **NFR3 - Existing tests maintained:** All existing tests in
  `tests.test_codex_hook_wrapper_args` and all of
  `tests.test_codex_litellm_launch_home_location` pass.
  `tests/test_codex_litellm_launch_home_location.py` is not changed.
- **NFR4 - Version untouched:** The change is confined to `tests/` and alters
  no file under a plugin directory, so the `version` in `plugin.json` /
  `marketplace.json` is not changed.

## Acceptance Criteria

- [ ] **AC-1** (FR1): After running
  `python3 -m unittest tests.test_codex_hook_wrapper_args` with
  `XDG_CACHE_HOME` set to an absolute-path directory,
  `$XDG_CACHE_HOME/em-workflow` has not been created (the reproduction steps
  no longer produce the phenomenon).
- [ ] **AC-2** (FR1, FR2): A test exists that, with the caller's environment
  `XDG_CACHE_HOME` set to a test-owned absolute path, launches the
  `--litellm` path in both readonly and readwrite, and confirms that the
  wrapper exits with 0, calls the stub exactly once, and that no
  `em-workflow` is created in that directory. Removing the `XDG_CACHE_HOME`
  removal from `_run_wrapper_pid()` makes this test fail.
- [ ] **AC-3** (FR3): A test exists showing that, when the wrapper is launched
  with `XDG_CACHE_HOME` left in place, the same check as AC-2 detects the
  creation of the `em-workflow` directory and fails.
- [ ] **AC-4** (NFR1, NFR2, NFR3): `tests.test_codex_hook_wrapper_args` and
  `tests.test_codex_litellm_launch_home_location` all pass, and the two
  wrappers and `tests/test_codex_litellm_launch_home_location.py` have no
  diff.

## Implementation Approach

### Architecture

Within `tests/test_codex_hook_wrapper_args.py`, `_run_wrapper_pid()` is the
only function that launches the wrapper; `_run_wrapper` / `_launch_record` /
`_launch_argv` go through it, and `_run_command_through_shell` does not launch
the wrapper (assumption A-2). The removal in FR1 is therefore made in one
place and applies to every `--litellm` test.

```
test case → _run_wrapper / _launch_record / _launch_argv
          → _run_wrapper_pid()  (removes CODEX_HOME, CODEX_OTLP_ENDPOINT, XDG_CACHE_HOME; then applies extra_env)
          → run_codex_exec.sh (unchanged) → stub codex
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/run_codex_exec.sh`, `em-review/scripts/run_codex_exec.sh`:
  the wrappers under test; not modified (NFR1).
- `tests/test_codex_litellm_launch_home_location.py`: fixes the `--litellm`
  launch-home behavior under an absolute `XDG_CACHE_HOME`; not modified
  (NFR3, assumption A-1).

**External Dependencies:**
- Python standard library only (`unittest`) (NFR2).

### File Structure

```
tests/
└── test_codex_hook_wrapper_args.py   # FR1 harness change, FR2 / FR3 tests
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/wrapper-args-test-xdg-cache-isolation/**`
- `test-docs/wrapper-args-test-xdg-cache-isolation/**`

`feature-docs/wrapper-args-test-xdg-cache-isolation/**` covers
`REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These
are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/wrapper-args-test-xdg-cache-isolation/**` covers
`test-docs/wrapper-args-test-xdg-cache-isolation/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/wrapper-args-test-xdg-cache-isolation/` directory at all; the
declared `test-docs/wrapper-args-test-xdg-cache-isolation/**` entry is still
correct in that case — a declared path that never materializes is not a
violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1: Nothing is left in an inherited absolute-path `XDG_CACHE_HOME`**
  (covers AC-2; FR1, FR2)
  - Steps: Prepare a test-owned empty directory and point the caller's
    environment `XDG_CACHE_HOME` at it (by a method closed within the test,
    such as `unittest.mock.patch.dict(os.environ)`). Launch `LITELLM_PATH`
    readonly / readwrite through `_run_wrapper_pid()`.
  - Expected: Exit code 0, one stub call, and the prepared directory's
    contents are the same as before the launch (no `em-workflow`).
- [ ] **TS-2: The detector does not miss the creation** (covers AC-3; FR3)
  - Steps: Launch the wrapper with `--litellm` in an environment where
    `XDG_CACHE_HOME` is not removed.
  - Expected: The same check as TS-1 detects the creation of the
    `em-workflow` directory.

### Integration Tests

- [ ] **TS-3: No regression in the existing suites** (covers AC-1, AC-4;
  FR1, NFR1, NFR2, NFR3)
  - Steps: Run
    `python3 -m unittest tests.test_codex_hook_wrapper_args tests.test_codex_litellm_launch_home_location`.
  - Expected: All pass.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A-1:** The `--litellm` path's behavior of making `em-workflow` under
  `XDG_CACHE_HOME` (when absolute) the parent of the launch home is the
  correct specification, and `tests.test_codex_litellm_launch_home_location`
  fixes it. Only the test harness is the target of the fix.
- **A-2:** In `tests/test_codex_hook_wrapper_args.py`, only
  `_run_wrapper_pid()` launches the wrapper (`_run_wrapper` /
  `_launch_record` / `_launch_argv` go through it).
  `_run_command_through_shell` does not launch the wrapper. Therefore the
  removal in one place applies to every `--litellm` test.
- **A-3:** Handling of inherited environment variables other than
  `XDG_CACHE_HOME` (such as `TMPDIR`) is out of scope for this feature.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 through AC-4 are satisfied

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Tests under change: `tests/test_codex_hook_wrapper_args.py`
- Related tests: `tests/test_codex_litellm_launch_home_location.py`
- Wrappers: `em-workflow/scripts/run_codex_exec.sh`,
  `em-review/scripts/run_codex_exec.sh`
