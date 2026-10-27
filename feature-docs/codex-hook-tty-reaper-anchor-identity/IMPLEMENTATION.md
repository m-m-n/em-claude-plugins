# Implementation Plan: codex-hook-tty-reaper-anchor-identity

## Overview
Add an anchor identity check to the Codex Stop hook's TTY reaper: the anchor
start time read during the ancestor-chain read must equal the anchor's start
time in the snapshot, otherwise nothing is stopped. One task carries the fix
to both script copies, the docstring update and the regression tests.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1).
- **New dependencies**: none. No license to record (`project.license` is
  `none`).

## Layer Structure
- Script module: `codex-hook-tty-reaper.py`, kept as two byte-identical
  copies (`em-workflow/scripts/`, `em-review/scripts/`).
- Test module: `tests/test_codex_hook_tty_reaper.py`, which exercises the
  script in-process through its existing test seam.
- No new layer, module or dependency direction is introduced.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

The feature has a single task; no component is built by one task and used
by another.

## Conventions
No cross-task convention: with a single task, every rule (copy identity,
output and exit code, signal delivery, docstring wording) is stated in
`tasks/task0001.md`.

## Cross-task Design Decisions

### Single-task decomposition
- **Decision**: the script fix (both copies, docstring included) and the
  regression tests form one task.
- **Rationale**: tasks run fully in parallel in separate worktrees. The
  regression test must fail against the pre-fix script and pass after the
  fix (FR4, SPEC.md AC1), and the byte identity of the two copies is pinned
  by an existing test (FR2). A test-only task or a single-copy task could
  not pass its own acceptance criteria in its own worktree.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Changing what the ancestor-chain read hands back breaks an existing test that calls or inspects it (NFR3) | Medium | Medium | task0001 constrains the start-time carrier to leave existing tests passing unchanged |
| The docstring edit changes the 10-step count or the pinned step 4 / step 6 wording | Low | Low | task0001 AC-6 runs the existing docstring test |
| The two copies drift apart | Low | Medium | task0001 AC-6 runs the existing copy-identity test |

## Open Questions
- None.
