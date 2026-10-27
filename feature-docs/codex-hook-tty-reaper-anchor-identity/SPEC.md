# Feature: codex-hook-tty-reaper-anchor-identity

## Overview

In `codex-hook-tty-reaper.py`, the anchor's PID can be reused by another
process between the ancestor-chain check and the snapshot. This change
verifies the anchor's identity by its start time so that no signal reaches
a process that is not a descendant of the anchor. Requirements:
`feature-docs/codex-hook-tty-reaper-anchor-identity/REQUIREMENTS.md`.

## Objectives

- Even when the anchor's PID is reused by another process between the
  ancestor-chain check and the snapshot, no signal reaches a process that
  is not a descendant of the anchor.

## User Stories

### US1: Anchor PID reuse does not lead to stray signals
When the anchor's PID is reassigned to another process between the
ancestor-chain read and the snapshot, the reaper stops nothing.

**Acceptance Criteria:**
- [ ] AC1 (FR1, FR4): The anchor seen during the ancestor-chain read and
  the process with the same PID in the snapshot differ in start time, and
  a descendant of the reassigned process has stdin on `/dev/pts/*`. In this
  case neither SIGTERM nor SIGKILL is sent and no pidfd is opened. This
  test fails against the pre-fix code.

### US2: Existing behaviour is kept for an unchanged anchor
When the anchor is the same process through the snapshot, the reaper stops
its targets as before.

**Acceptance Criteria:**
- [ ] AC2 (FR1, NFR3): If the anchor is the same process through the
  snapshot (same start time), targets are stopped as before. An anchor
  whose parent (ppid) alone was reassigned is treated as the same process.

### US3: Copies, docstring and test suite stay consistent

**Acceptance Criteria:**
- [ ] AC3 (FR2): The two copies are byte-identical (`TestCopies` passes).
- [ ] AC4 (FR3): The docstring's Flow describes the FR1 check and still has
  10 steps (`TestModuleDocstring` passes).
- [ ] AC5 (NFR1, NFR2, NFR3, NFR4):
  `python3 -m unittest tests.test_codex_hook_tty_reaper` and
  `python3 -m unittest discover -s tests` pass.

## Technical Requirements

### Functional Requirements
- **FR1:** Anchor identity check. Compare the anchor's start time recorded
  when the ancestor chain was read with the anchor's start time in the
  snapshot. If they do not match, stop nothing (open no pidfd, send no
  signal). The anchor's start time is the value `_ancestor_chain` read
  while reading the ancestor chain.
- **FR2:** Identity of the two copies. Fix
  `em-workflow/scripts/codex-hook-tty-reaper.py` and
  `em-review/scripts/codex-hook-tty-reaper.py` in the same change and keep
  them byte-identical.
- **FR3:** Docstring update. Add the FR1 check to the module docstring's
  Flow. Keep the 10-step structure and the wording `TestModuleDocstring`
  pins (steps 4 / 6).
- **FR4:** Regression test. Add a test to `tests/test_codex_hook_tty_reaper.py`
  that sets up the anchor's PID being reassigned to another process between
  the ancestor-chain read and the snapshot, with a descendant of the
  reassigned process whose stdin is on `/dev/pts/*`, and confirms that no
  signal is sent.

### Non-Functional Requirements
- **NFR1 - Standard library only:** Use only the standard library.
- **NFR2 - Output and exit code:** On every path the exit code is 0 and
  nothing is written to stdout or stderr.
- **NFR3 - Existing behaviour:** All existing tests pass unchanged.
- **NFR4 - No PID-addressed signals:** Do not add PID-addressed signal
  delivery (`os.kill`).

## Implementation Approach

### Architecture

The anchor identity check (FR1) sits between the ancestor-chain read and
target selection on the snapshot:

```
_ancestor_chain (records anchor start time)
  -> snapshot
  -> anchor start time in snapshot == recorded start time ?
       no  -> stop nothing (no pidfd, no signal), exit 0
       yes -> existing target selection and stopping
```

Behaviour decided by the check:

- A start time that differs by a single tick is a mismatch.
- An anchor whose ppid alone changed, with the same start time, is the same
  process.
- If a process between the anchor and the hook exits during the hook run,
  stopping continues as long as the anchor's start time matches.

### Dependencies

**Internal Dependencies:**
- `tests/test_codex_hook_tty_reaper.py`: existing `World` seam
  (`world.sent`, `world.open_calls`, `on_stat`) used by the regression
  tests.

**External Dependencies:**
- None (standard library only, NFR1).

### File Structure

```
em-workflow/scripts/codex-hook-tty-reaper.py   # FR1, FR3
em-review/scripts/codex-hook-tty-reaper.py     # byte-identical copy (FR2)
tests/test_codex_hook_tty_reaper.py            # FR4 regression tests
```

Not changed: `plugin.json` / `marketplace.json` version,
`.claude/rules/hook-tests.md`.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-hook-tty-reaper-anchor-identity/**`
- `test-docs/codex-hook-tty-reaper-anchor-identity/**`

`feature-docs/codex-hook-tty-reaper-anchor-identity/**` covers
`REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These
are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/codex-hook-tty-reaper-anchor-identity/**` covers
`test-docs/codex-hook-tty-reaper-anchor-identity/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1; FR1, FR4): Run in-process. Replace `_snapshot` (or use
  `on_stat`) so that, after the ancestor chain is read and before the
  snapshot, the anchor PID's entry is replaced by a process X with a later
  start time, and a descendant of X has stdin on `/dev/pts/*`. Expect
  `world.sent` and `world.open_calls` to be empty.
- [ ] TS2 (AC1; FR1, FR4): Same layout as TS1, with a start-time difference
  of a single tick (one tick after the anchor). Expect nothing to be
  stopped.
- [ ] TS3 (AC2; FR1, NFR3): After the ancestor chain is read and before the
  snapshot, change only the anchor's ppid (same start time). Expect the
  anchor's descendant whose stdin is on `/dev/pts/*` to be stopped.

### Integration Tests
- [ ] TS4 (AC2, AC3, AC4, AC5; FR1, FR2, FR3, NFR1, NFR2, NFR3, NFR4): The
  whole test suite passes, including the existing `TestTargetSelection` /
  `TestAncestorChainRule` / `TestLinkRule` / `TestCopies` /
  `TestModuleDocstring`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] Start time differs by a single tick: treated as a mismatch; nothing
  is stopped (TS2).
- [ ] Only the anchor's ppid changed: treated as the same process; targets
  are stopped (TS3).

### Performance Tests
- None.

## Security Considerations

- **Signal delivery:** No PID-addressed signal delivery (`os.kill`) is
  added (NFR4). On an anchor start-time mismatch no pidfd is opened and no
  signal is sent (FR1).

## Error Handling

- Anchor start-time mismatch: stop nothing, exit code 0, no output on
  stdout / stderr (FR1, NFR2).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1 through AC5 are met

## Open Questions

None.

## References

- `feature-docs/codex-hook-tty-reaper-anchor-identity/REQUIREMENTS.md`
- `em-workflow/scripts/codex-hook-tty-reaper.py`
- `em-review/scripts/codex-hook-tty-reaper.py`
- `tests/test_codex_hook_tty_reaper.py`
