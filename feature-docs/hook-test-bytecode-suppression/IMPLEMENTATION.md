# Implementation Plan: hook-test-bytecode-suppression

## Overview

Two test modules in `tests/` load `em-workflow/hooks/destructive-guard.py`
in-process. After this change, their loader helpers turn bytecode writing
off only while the hook module body executes, then restore the caller's
value. The hook then leaves no `__pycache__/` next to itself. One task
(task0001) carries the whole change. The per-task contract, flow and tests
live in `tasks/task0001.md`.

## Technology Stack

- **Language**: Python 3 (test/README.md: Python 3.14).
- **Test framework**: the standard library's unittest only (NFR2).
- **New dependencies**: none. `project.license` is `none` and no dependency
  is added, so there is no license to check or record.

## Layer Structure

Not applicable. The change is confined to two helper functions and their
new tests, in two modules under `tests/`. Nothing under `em-workflow/`
changes (SPEC A-1).

## Shared Components

None. The feature has a single task, so no component is shared between
tasks. Both loaders follow one contract, stated once in `tasks/task0001.md`
("Loader contract").

## Conventions

- **Process-wide flag discipline**: any code in this change that changes
  `sys.dont_write_bytecode` puts back the value it found, on every exit
  path: normal return, exception, and a failing test. The flag is
  process-wide, so in a whole-suite run every later test module inherits
  whatever is left behind (NFR3).
- **Nothing written under the plugin**: no code in this change, tests
  included, creates, deletes or renames a file under `em-workflow/`. Test
  material lives in a test-owned temporary directory.

## Cross-task Design Decisions

### D1: One task for both test modules

- **Decision**: both loaders change in the same task.
- **Rationale**: FR3's whole-run outcome depends on both modules. With one
  task per module, no single task could own the whole-run check. A worktree
  holding only the extglob_units change would still leave bytecode from
  lexer_agreement's import-time load.
- **Affected tasks**: task0001.

### D2: Do not rely on the whole-run flag ordering

- **Facts**:
    - `python3 -m unittest discover -s tests` imports every test module, in
      file-name order, before it runs any test.
    - `tests/test_merge_ci_wait.py` sets `sys.dont_write_bytecode` to True
      when imported and never restores it.
- **Effect in a whole run today**:
    - lexer_agreement's import-time load (the module-level hook binding)
      runs before that import, so it writes bytecode. This is the observed
      `destructive-guard.cpython-*.pyc`.
    - extglob_units loads the hook only while its tests run, after that
      import. So it writes nothing in a whole run, but does when the module
      runs alone (SPEC TS-1).
- **Decision**: each loader sets the flag itself and never depends on
  another module having set it.
- **Testing consequence**: tests for NFR3 set the starting value explicitly
  instead of inheriting it. In a whole run the inherited value is already
  True, so a bare before/after comparison would pass even if a loader never
  restored the flag.
- **Affected tasks**: task0001.

### D3: Starting state of the bytecode checks

- `__pycache__/` is git-ignored, so leftovers from earlier runs do not show
  in `git status`. One such source is a test run before the fix, such as the
  TDD red step.
- Every check of "no `__pycache__` under `em-workflow/hooks/`" (task0001
  AC-6, VERIFICATION.md TS-1 to TS-3) first confirms that none exists.
- A leftover is removed with `gio trash`, never with `rm`.
- The checks prove nothing if the environment already disables or
  redirects bytecode writing. They run with `PYTHONDONTWRITEBYTECODE` and
  `PYTHONPYCACHEPREFIX` unset, and without the interpreter's `-B` option.
- **Affected**: task0001, VERIFICATION.md.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A new NFR3 test changes the process-wide flag and exits without restoring it. Later modules in the same run then write bytecode | Low | Medium: an FR3 regression caused by the test itself | task0001 AC-5: every new test restores the flag on every exit path |
| A new test loads the real hook while the flag is False. During the red step it writes under `em-workflow/hooks/` and spoils the starting state of the command-level checks | Medium (during TDD) | Low: git-ignored, but makes AC-6 run from a dirty state | The flag tests load a probe module in a test-owned temporary directory (task0001 Design). D3 removes leftovers before the checks |
| Other in-process hook loaders under `tests/` (see Open Questions) still write bytecode when run alone. In a whole run only `tests/test_merge_ci_wait.py`'s import-time setting covers them | Medium | Medium: if that module changes, FR3 regresses for those hooks | Out of scope (SPEC A-1); raised as an open question |

## Open Questions

- [ ] Other test modules load hook files in-process with no bytecode
  suppression:
    - `tests/test_queue_stop_guard.py` and
      `tests/test_queue_stop_guard_routeback_record.py` load
      `queue_stop_guard.py`.
    - `tests/test_failed_run_cleanup_guard.py` loads
      `failed-run-cleanup-guard.py`.
    - `tests/test_hooks_registration.py` loads `queue_launch_guard.py`,
      `queue_agent_index.py` and `queue_failure_net.py`.
    - `tests/test_queue_failure_net_cross_hook.py` loads
      `queue_failure_net.py` and `queue_launch_guard.py`.
    - `tests/test_muse_guard.py` and
      `tests/test_consultation_harness_chain.py` load `muse_guard.py` from
      both `em-workflow/hooks/` and `em-review/hooks/`.

  Run alone, these modules would write `__pycache__` under
  `em-workflow/hooks/` (and `em-review/hooks/`). In a whole run they write
  nothing only because of `tests/test_merge_ci_wait.py` (D2). This feature
  leaves them unchanged (SPEC A-1). Whether to handle them is a separate
  decision.
