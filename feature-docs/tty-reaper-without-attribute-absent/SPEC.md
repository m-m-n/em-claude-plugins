# Feature: tty-reaper-without-attribute-absent

## Overview

The test helper `without_attribute(module, name)` in
`tests/test_codex_hook_tty_reaper.py` must not raise when `name` is already
absent from `module`, and must leave `name` absent inside the block. This lets
the two tests that cover a missing `os.pidfd_open` / `signal.pidfd_send_signal`
run past their setup on a Python that lacks those functions.

## Objectives

- `without_attribute()` does not raise when the target attribute is absent from
  the start, and the attribute is absent inside the block.
- On a Python without `os.pidfd_open` or `signal.pidfd_send_signal`, the two
  tests that cover the missing-function case run without stopping at setup.

## Acceptance Criteria

- [ ] **AC-1** (FR1, FR2): Running `with without_attribute(target, name):` on a
  target that has no attribute `name` raises no `AttributeError`; `name` is
  absent from the target both inside the block and after leaving it.
- [ ] **AC-2** (FR3): Using `without_attribute()` on a target that has attribute
  `name` leaves `name` absent inside the block, and the identical original
  object is restored after leaving it. When an exception is raised inside the
  block, the object is still restored and the exception propagates.
- [ ] **AC-3** (FR1): Reproduction steps (with `os.pidfd_open` already removed,
  run `with without_attribute(os, "pidfd_open"):`; same for
  `signal.pidfd_send_signal`) raise no `AttributeError`. After the outer removal
  ends, `os.pidfd_open` and `signal.pidfd_send_signal` are back in their
  original state.
- [ ] **AC-4** (FR4, FR5, NFR1, NFR3): Tests verifying AC-1 through AC-3 exist in
  `tests/test_codex_hook_tty_reaper.py`, and both
  `python3 -m unittest tests.test_codex_hook_tty_reaper` and
  `python3 -m unittest discover -s tests` pass.

## Technical Requirements

### Functional Requirements

- **FR1:** Do not raise when the attribute is absent from the start.
  If `module` has no `name` when the block is entered,
  `without_attribute(module, name)` runs the block without raising
  `AttributeError`. Inside the block, `module` has no `name`.
- **FR2:** Delete and restore nothing when the attribute is absent from the
  start. If `name` is absent when the block is entered, `without_attribute()`
  does not call `delattr` on entry and does not call `setattr` on exit. After
  leaving the block, `module` still has no `name`.
- **FR3:** Preserve the behavior when the attribute is present. If `name` is
  present when the block is entered, `name` is absent inside the block, and
  after leaving the block the identical object that was there before entry is
  restored to `name`. This also holds when the block ends with an exception,
  and the exception propagates to the caller unchanged.
- **FR4:** Keep existing callers unchanged. The name of `without_attribute()`
  and its arguments `(module, name)` stay the same. The calls in
  `test_ac5_ts5_a_missing_pidfd_open_function_leaves_a_default_that_stops_nothing`
  and
  `test_ac5_ts5_a_missing_pidfd_send_signal_function_leaves_a_default_that_stops_nothing`
  work as they are.
- **FR5:** Add a regression test. Add a test to
  `tests/test_codex_hook_tty_reaper.py` that verifies using
  `without_attribute()` on a target whose attribute is absent from the start
  raises no error.

### Non-Functional Requirements

- **NFR1 - Standard library only:** Test code uses only the standard library
  (`test/README.md`). `TestThisModule.test_ts14_module_imports_are_all_stdlib`
  keeps passing.
- **NFR2 - Change scope:** Changes are limited to
  `tests/test_codex_hook_tty_reaper.py`. The hook itself
  (`em-workflow/scripts/codex-hook-tty-reaper.py` and
  `em-review/scripts/codex-hook-tty-reaper.py`) is not changed.
- **NFR3 - No regressions:** All existing tests keep passing.

## Implementation Approach

### Approach

- `without_attribute()` determines whether the attribute exists with
  `getattr(module, name, sentinel)` using a sentinel object, and deletes and
  restores the attribute only when it existed (FR1, FR2, FR3).
- The case where the caller sets `name` inside the block while the attribute
  was absent from the start is out of scope; no existing caller uses it that
  way.

### Dependencies

**Internal Dependencies:**
- `tests/test_codex_hook_tty_reaper.py`: the only file changed (NFR2).

**External Dependencies:**
- None (standard library only, NFR1).

### File Structure

```
tests/
└── test_codex_hook_tty_reaper.py   # without_attribute() fix and new tests
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/tty-reaper-without-attribute-absent/**`
- `test-docs/tty-reaper-without-attribute-absent/**`

`feature-docs/tty-reaper-without-attribute-absent/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/tty-reaper-without-attribute-absent/**` covers
`test-docs/tty-reaper-without-attribute-absent/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/tty-reaper-without-attribute-absent/` directory at all; the
declared `test-docs/tty-reaper-without-attribute-absent/**` entry is still
correct in that case — a declared path that never materializes is not a
violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (AC-1; FR1, FR2): Apply `without_attribute()` to a stand-in
  module (e.g. `types.ModuleType`) that has no `name` - no error is raised, and
  `hasattr` is `False` both inside and after the block.
- [ ] **TS-2** (AC-2; FR3): Apply `without_attribute()` to a stand-in module
  that has `name` - `hasattr` is `False` inside the block, and after the block
  the attribute is the identical original object (`assertIs`). When an
  exception is raised inside the block, the object is likewise restored and the
  exception propagates.
- [ ] **TS-3** (AC-1; FR1, FR2): On a target without `name`, raise an exception
  inside the block - after leaving, `name` is still absent and the exception
  propagates.
- [ ] **TS-4** (AC-3; FR1): Nest `without_attribute(os, "pidfd_open")` twice -
  the inner one raises no error even though it starts with the attribute
  absent, and after leaving both, `os.pidfd_open` is back in its original
  state. Same for `signal.pidfd_send_signal`.

### Integration Tests

- None.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] Attribute absent from the start, block ends with an exception: covered by
  TS-3.
- [ ] Nested use on the same attribute: covered by TS-4.

## Success Criteria

- [ ] AC-1 through AC-4 are satisfied.
- [ ] `python3 -m unittest tests.test_codex_hook_tty_reaper` passes.
- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] `TestThisModule.test_ts14_module_imports_are_all_stdlib` passes.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- Target test file: `tests/test_codex_hook_tty_reaper.py`
- Test conventions: `test/README.md`
