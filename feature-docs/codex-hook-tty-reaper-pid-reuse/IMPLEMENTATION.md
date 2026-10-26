# Implementation Plan: codex-hook-tty-reaper-pid-reuse

## Overview
Close the two PID-reuse races in the Codex Stop hook `codex-hook-tty-reaper.py`
(both plugin copies): adopt process links only in start-time order, and deliver
every signal through a pidfd obtained before the identity check and held
through SIGKILL. The feature is a single task, task0001.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1). The pidfd open and
  pidfd signal-send functions named in SPEC.md FR2 belong to the standard
  library; the repository runs Python 3.14.
- **Tests**: the standard-library unittest runner
  (`python3 -m unittest discover -s tests`).
- **New dependencies**: none. `project.license` is `none`; there is no
  dependency license to record.

## Layer Structure
One script with the existing pipeline and no new layers:

snapshot -> ancestor-chain check -> anchor check -> descendant computation ->
ordering -> stopping

- Two byte-identical copies: `em-workflow/scripts/codex-hook-tty-reaper.py`
  and `em-review/scripts/codex-hook-tty-reaper.py` (FR7).
- Callers (`run_codex_exec.sh` in both plugins) are unchanged: same file name,
  same single `ANCHOR` argument (A2).
- `tests/test_codex_hook_tty_reaper.py` drives the copies in-process through
  `main()`'s injectable seams and also runs the existing Linux real-process
  tests.

## Shared Components
None. The feature has one task, so no component is built by one task and
consumed by another.

## Conventions
- **Fail closed**: when the hook cannot establish that a process descends from
  the anchor, or cannot signal it without a PID-reuse window, it stops nothing
  (existing policy; A3, A4, FR4).
- **Error policy**: "the process no longer exists" is not an error — skip that
  target and continue; any other error ends all signalling for the run (A4,
  FR5).
- **Silent operation**: exit 0 on every path, nothing on stdout or stderr, no
  environment reads, nothing executed on import, no `__pycache__` left under
  the plugin directories (NFR2).
- **Two copies**: edited in the same change and kept byte-identical (FR7).
- **Versioning**: the plugin versions are not changed (NFR4, A1).

## Cross-task Design Decisions

### D1: Single-task decomposition
- **Decision**: FR1-FR9 and NFR1-NFR4 are delivered by one task (task0001).
- **Rationale**: every requirement lands in the same three files. The
  test-seam change of FR8 rewrites how every in-process test observes signals,
  including the tests for the link rule of FR1 / FR6, and the module docstring
  of FR9 spans both halves. Parallel tasks on these files would collide on the
  seam and the docstring, and no contract pinned here could keep them apart.
  The task carries eight acceptance criteria, at the size limit.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The fake pidfd does not bind to the process instance that held the PID at open time, so the reproduction-2 test passes without exercising the race | Medium | High | task0001 AC-3 and AC-7 require the instance binding and a test that fails against the current code |
| A host kernel without pidfd support makes the hook stop nothing, so the real-process tests fail there | Low | Medium | FR4 makes this a defined no-op; verification runs the real-process tests on a Linux host with pidfd support |
| The two copies drift apart | Low | High | Existing byte-identity test (TS-8) |
| The new link rule changes target selection beyond FR1 / FR6 | Low | Medium | Existing selection, ordering and timing tests are kept and migrated to the pidfd fakes (TS-12) |

## Open Questions
- None.
