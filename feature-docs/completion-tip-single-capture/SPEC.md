# Feature: completion-tip-single-capture

## Overview

Step I.3 of `em-workflow/references/implement-phase.md` is changed so that its
command sequence itself names the step-1 capture as the single source of both
`$COMPLETION_TIP` and `completed_at_commit`. A unittest under `tests/` detects
any later change that reintroduces a second, independent `rev-parse` as the
source of `completed_at_commit`.

## Objectives

- Step I.3 of `em-workflow/references/implement-phase.md` names exactly one
  place where the value of both `$COMPLETION_TIP` and `completed_at_commit`
  comes from: the step-1 capture.
- A reader following SPEC FR3 of `feature-docs/exit4-tip-argument/SPEC.md`
  ("both derive from that same step-1 capture") can trace that requirement in
  the Step I.3 command sequence itself, not only in the closing paragraph that
  asserts it.
- A test detects any later change that brings back a second, independent
  `rev-parse` as the source of `completed_at_commit`.

## Technical Requirements

### Functional Requirements

- **FR1:** Step I.3 step 3 writes `completed_at_commit` from `$COMPLETION_TIP`.
  Step 3 (write) of Step I.3's numbered sequence in
  `em-workflow/references/implement-phase.md` states that the
  `completed_at_commit` value written to `workflow.yaml` is the value of
  `$COMPLETION_TIP` captured in step 1. It also states that the
  `$(git rev-parse "em-workflow/{feature}/integration")` expression in the
  pinned sentence above is not evaluated as a separate command: its value is
  the one step 1 captured. The phrase "on the worktree just refreshed" remains
  in step 3 (`tests/test_exit4_tip_argument_consistency.py` uses it as the
  write anchor). Step 3 contains no command substitution or `rev-parse` of its
  own.
- **FR2:** On an exit-4 retry the write uses the fresh capture. Step I.3 states
  that on an exit-4 retry (Branch & Worktree Model's exit-4 recovery),
  `completed_at_commit` is re-written with the freshly re-captured
  `$COMPLETION_TIP`, the same value passed as `commit-docs.sh`'s third
  argument on that retry, so the two values still name the same commit across
  retries.
- **FR3:** The pinned sentence stays byte-identical. The Step I.3 sentence
  pinned by `tests/test_rework_synthesis_contract.py`
  `test_completed_at_commit_wording_is_unchanged` is kept byte-for-byte,
  including its internal newline:

  ```
  When every task is `merged`: set `implement` step `status = completed`,
  `completed_at_commit = $(git rev-parse "em-workflow/{feature}/integration")`.
  ```

  All new wording goes strictly after that sentence.
  `tests/test_rework_synthesis_contract.py` is not edited.
- **FR4:** Regression test for the single value source. A unittest under
  `tests/` asserts, on the Step I.3 section with whitespace normalized, that
  the text between step 3's write anchor and step 4's `commit-docs.sh`
  invocation binds `completed_at_commit` to `$COMPLETION_TIP` and contains no
  `rev-parse`. A negative proof shows the matcher fails against a verbatim
  sample of the current, pre-change step 3 wording
  ("`` `status = completed` and `completed_at_commit` set above ``"), and a
  non-vacuity guard shows that sample is not empty, following the existing
  pattern in `tests/test_exit4_tip_argument_consistency.py`.

### Non-Functional Requirements

- **NFR1 - Documentation-only change:** Only
  `em-workflow/references/implement-phase.md` and test files under `tests/`
  change. `em-workflow/scripts/commit-docs.sh`, hooks, scripts and agent
  definitions are not modified.
- **NFR2 - Existing tests stay green without edits:**
  `python3 -m unittest discover -s tests` passes.
  `tests/test_rework_synthesis_contract.py` and
  `tests/test_tip_capture_idiom_uniformity.py` are not edited. Every existing
  assertion on the Step I.3 section in
  `tests/test_exit4_tip_argument_consistency.py` keeps passing.
- **NFR3 - Plugin version is not touched:** The `version` fields in
  `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  are not changed.

## Acceptance Criteria

- [ ] AC-1: Step I.3 step 3 states that the `completed_at_commit` value written
  is `$COMPLETION_TIP` from step 1, and that the pinned sentence's `rev-parse`
  expression is not evaluated separately (FR1).
- [ ] AC-2: Step I.3 states that on an exit-4 retry `completed_at_commit` is
  re-written from the fresh `$COMPLETION_TIP` (FR2).
- [ ] AC-3: The pinned sentence asserted by
  `test_completed_at_commit_wording_is_unchanged` is present byte-for-byte, and
  `tests/test_rework_synthesis_contract.py` is absent from the diff (FR3).
- [ ] AC-4: A test exists that fails against the current step 3 wording and
  passes after the change; it imports only the standard library (FR4).
- [ ] AC-5: `python3 -m unittest discover -s tests` exits 0 (NFR2).
- [ ] AC-6: `em-workflow/scripts/commit-docs.sh`,
  `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` are absent from the diff (NFR1, NFR3).

## Implementation Approach

### Changed Files

```
em-workflow/references/implement-phase.md   # Step I.3 step 3 wording, exit-4 retry wording
tests/                                      # new or extended unittest (FR4)
```

### Dependencies

**Internal Dependencies:**
- `tests/test_exit4_tip_argument_consistency.py`: uses "on the worktree just
  refreshed" as the step 3 write anchor; its existing Step I.3 assertions keep
  passing.
- `tests/test_rework_synthesis_contract.py`: pins the Step I.3 completion
  sentence byte-for-byte.
- `tests/test_tip_capture_idiom_uniformity.py`: takes the first
  `COMPLETION_TIP=$(git` match and the first "reset --hard" match inside the
  Step I.3 section.

**External Dependencies:**
- None. The new test imports only the Python standard library.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/completion-tip-single-capture/**`
- `test-docs/completion-tip-single-capture/**`

`feature-docs/completion-tip-single-capture/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/completion-tip-single-capture/**` covers
`test-docs/completion-tip-single-capture/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/completion-tip-single-capture/` directory at all; the declared
`test-docs/completion-tip-single-capture/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

**Run command**: `python3 -m unittest discover -s tests`

### Unit Tests

- [ ] TS1 (new): In the whitespace-normalized Step I.3 section, the span from
  "on the worktree just refreshed" up to the following "commit-docs.sh"
  contains `completed_at_commit` and `$COMPLETION_TIP`. Covers FR1.
- [ ] TS2 (new): The same span contains no "rev-parse" and no "$(git".
  Covers FR1.
- [ ] TS3 (new): Step I.3 states that `completed_at_commit` is re-written from
  the re-captured `$COMPLETION_TIP` on an exit-4 retry. Covers FR2.
- [ ] TS4 (new): The TS1/TS2 matchers are checked against a verbatim
  pre-change sample of the current step 3 text. TS1's matcher fails on it, and
  a non-vacuity guard shows the sample contains `completed_at_commit`.
  Covers FR4.
- [ ] TS5 (existing, unmodified): `test_completed_at_commit_wording_is_unchanged`,
  `TestStepI3CompletionWriteHasTipArgument`,
  `TestStepI3PinnedCompletionSentenceByteIdentical` and the
  `tests/test_tip_capture_idiom_uniformity.py` per-site classes for
  `COMPLETION_TIP` keep passing. Covers FR3, NFR2.

### Integration Tests

None.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

Not applicable; no E2E infrastructure exists.

### Edge Cases

- [ ] Exit-4 retry: the re-capture gives a new `$COMPLETION_TIP`.
  `completed_at_commit` must be re-written with that new value, not the first
  one (FR2).
- [ ] Pinned sentence adjacency: new wording must not appear inside the pinned
  span or re-wrap it (FR3).
- [ ] Section-scoped matchers: inside the Step I.3 section, the first
  `COMPLETION_TIP=$(git` match must stay step 1's capture, and the first
  "reset --hard" must stay after it, because
  `tests/test_tip_capture_idiom_uniformity.py` takes the first match for both.
  New wording must not add a `COMPLETION_TIP=$(git ...)` or "reset --hard"
  string earlier in the section, and must never contain
  `reset --hard "$COMPLETION_TIP"`.

### Manual Checks

- [ ] Reproduction check: read Step I.3 step 1 and step 3 together and confirm
  that the single-capture origin of `completed_at_commit` follows from the
  command sequence alone.

## Assumptions

- **A1:** The fix takes the approach recommended in the task: the pinned
  sentence is left untouched and step 3 states that `completed_at_commit` is
  the value of `$COMPLETION_TIP`.
- **A2:** The closing paragraph (`implement-phase.md` lines 1450-1453, "both
  derived from the same step-1 capture ... SAME commit ... re-derived together
  from a fresh capture") may stay as written or be reworded to point at step 3.
  No existing test asserts its wording.
- **A3:** The new test may extend `tests/test_exit4_tip_argument_consistency.py`
  or be a new `tests/test_*.py` module. Both fit the `tests/` conventions in
  `test/README.md`.
- **A4:** The meaning of `completed_at_commit` (the integration tip when every
  task is merged, before the completion docs commit) does not change. Only
  where its value comes from is pinned down.
- **A5:** There is no LICENSE file at the project root, so no SPDX identifier
  is recorded. This feature adds no dependencies.

## Design Step

Skipped. The change is protocol prose in
`em-workflow/references/implement-phase.md` plus a unittest. There is no UI or
visual surface, and the design-system candidate, project design system and
visual input categories are all empty.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Acceptance criteria AC-1 through AC-6 are satisfied

## Open Questions

None. No requirement has `status: tbd`.

## References

- Implement phase protocol: `em-workflow/references/implement-phase.md`
- Related specification: `feature-docs/exit4-tip-argument/SPEC.md`
