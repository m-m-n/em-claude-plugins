# Implementation Plan: hook-test-bytecode-suppression-others

## Overview

Seven test modules load hook modules from `em-workflow/hooks/` and
`em-review/hooks/` into the test process. Every such load runs with bytecode
writing suppressed for the duration of the module execution step only, so that
running any one of the seven modules alone leaves no `__pycache__` beneath
either hook directory (SPEC.md FR1, FR2).

## Technology Stack

- **Language**: Python 3
- **Framework**: the standard library test runner (`unittest`), as today
- **Key libraries**: Python standard library only (NFR1). No new dependency is
  introduced, so there is no new license to record.

## Layer Structure

| Layer | Contents | Changed by this feature |
|-------|----------|-------------------------|
| Test modules | The seven modules under `tests/` named in SPEC.md FR1 | Yes: their hook-loading sites, plus regression tests |
| Hook modules | `em-workflow/hooks/*.py`, `em-review/hooks/muse_guard.py` | No: load targets only, read but never modified |

Dependency direction: test modules load hook modules; nothing under
`em-workflow/` or `em-review/` is modified by any task.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | Each test module keeps its own loading function and gets its own suppression window inline (see Cross-task Design Decisions, D1). No helper module is shared between tasks. | — | — |

## Conventions

### Term: the bytecode flag

"The bytecode flag" is the interpreter's process-wide switch that stops
bytecode caches from being written (`sys.dont_write_bytecode`, the name SPEC.md
uses). "On" means bytecode writing is suppressed.

### Suppression window (applies to every loading site in every task)

Every loading site listed in SPEC.md FR1 wraps its module execution step (the
step that runs the hook file's body after the module spec is created from the
file location) in a suppression window with this contract:

- **Precondition**: the bytecode flag holds some value V set by the caller
  (off or on; never assumed).
- **During the module execution step**: the flag is on. Imports the hook body
  performs of sibling hook modules happen inside this step and are suppressed
  too (SPEC.md EC3).
- **Postcondition, normal return**: the flag equals V, and the loading site
  returns the same module object it returned before this feature.
- **Postcondition, the module execution step raises**: the flag equals V, and
  the exception propagates unchanged (SPEC.md EC1).
- **Never**: set the flag at module import time, or leave it changed after the
  loading site returns (the form `tests/test_merge_ci_wait.py` uses is not
  followed).

This is the form already used by `load_hook` in
`tests/test_destructive_guard_extglob_units.py` and by `load_hook_module` in
`tests/test_queue_launch_guard_linked_layout.py` (SPEC.md A1).

### Residual write sites

The single-module run (VERIFICATION.md TS-1) is the final judge. When a
single-module run still leaves a `__pycache__` beneath a hook directory, the
task owning that module locates the writing site inside its own files and
applies one of these, in this order of preference:

1. An in-process call made after the load returns (for example a hook's
   `main()` whose deferred imports run after the window closed, SPEC.md EC2):
   the same suppression window, with the same contract, around that call.
2. A hook run as a child interpreter whose body imports a sibling hook module
   (SPEC.md A3): the child interpreter is started with bytecode writing
   disabled; its arguments, input, working directory and other environment
   stay as they were.

A writing site found outside the task's own files is a reportable plan
deviation, not a license to expand the file set.

### Regression tests

- Each task adds regression tests inside the modules it modifies, one test
  class per module, following `TestHookLoadWritesNoBytecode` in
  `tests/test_destructive_guard_extglob_units.py`.
- A test sets the bytecode flag's starting value itself and covers both off
  and on (SPEC.md TS-3): the full-suite run leaves the flag on because of
  `tests/test_merge_ci_wait.py`, so a test that relied on the inherited value
  would pass vacuously.
- A test restores the flag to the value the process had before the test,
  whatever the outcome, so test order never changes another module's
  behavior.
- A test creates no file beneath `em-workflow/hooks/` or `em-review/hooks/`
  other than what a failing suppression itself would write.

### Out of scope for every task

- `tests/test_merge_ci_wait.py`, `tests/test_destructive_guard_extglob_units.py`
  and `tests/test_destructive_guard_lexer_agreement.py` are not modified
  (SPEC.md A2).
- No file under `em-workflow/` or `em-review/` is modified.
- Bytecode written beneath `tests/` (for example by `_pinned_consent_check_command`
  in `tests/test_consultation_harness_chain.py`) is not addressed (SPEC.md A4).

## Cross-task Design Decisions

### D1: Inline window per loading site, no shared helper

- **Decision**: each loading site gets its own inline suppression window; no
  new helper module under `tests/` is introduced.
- **Rationale**: SPEC.md's File Structure lists only the seven modules; both
  precedents keep the window inside the module's own loader; a shared helper
  would be a cross-task component that every task depends on.
- **Affected tasks**: task0001, task0002.

### D2: Split by hook origin

- **Decision**: task0001 covers the five modules that load hooks from
  `em-workflow/hooks/` only; task0002 covers the two modules that load
  `muse_guard.py` from both `em-workflow/hooks/` and `em-review/hooks/`.
- **Rationale**: the two groups share no file, so the tasks run in parallel
  without merge conflicts.
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A hook's `main()`, called in process after the load, imports a sibling hook module after the window closed (SPEC.md EC2) | Medium | `__pycache__` still written on a single-module run | Residual write sites, rule 1; detected by TS-1 |
| A hook run as a child interpreter imports a sibling hook module (SPEC.md A3) | Low | `__pycache__` still written on a single-module run | Residual write sites, rule 2; detected by TS-1 |
| A regression test leaves the flag off after it ends | Low | Later modules in the full-suite run write bytecode | Regression tests convention: restore the process's value whatever the outcome |
| A `__pycache__` left by an earlier unsuppressed run hides a new write | Medium | A broken window passes the single-module check | TS-1 starts from a state with no `__pycache__` beneath either hook directory |

## Open Questions

- None.
