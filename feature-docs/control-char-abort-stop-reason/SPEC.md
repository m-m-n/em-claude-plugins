# Feature: control-char-abort-stop-reason

## Overview

The "Precedence rule:" paragraph of `em-workflow/references/batch-terminal-line.md`
binds the batch stop raised by the Control-character check of Step I.2.a
(`em-workflow/references/implement-phase.md`) to the `stop-condition-3` row
(`step_needs_intervention`), not to `unmapped_stop`. A new document test pins
that binding and the existing current-run exclusion of the `stop-condition-3`
row.

## Objectives

- When the Step I.2.a Control-character check stops a batch run, the
  structured result's `reason` reads the same way for every batch consumer:
  `step_needs_intervention`.

## Acceptance Criteria

- [ ] **AC1** (FR1): Read against `batch-terminal-line.md`'s Stop point
  coverage and Precedence rule, the batch stop from the Step I.2.a
  Control-character check binds to `step_needs_intervention`, not
  `unmapped_stop`.
- [ ] **AC2** (FR2): The Precedence rule paragraph still restricts the
  `stop-condition-3` row to statuses no route of the current run produced.
  The control-character stop is the named exception.
- [ ] **AC3** (FR3, NFR4): A new document test passes against the live
  document. Each of its matchers fails against the verbatim pre-change
  Precedence rule paragraph.
- [ ] **AC4** (NFR1, NFR2, NFR3): The full suite
  `python3 -m unittest discover -s tests` passes, including the existing
  Precedence-rule, coverage-table and control-character-paragraph tests.

## Technical Requirements

### Functional Requirements

- **FR1: Bind the control-character stop to stop-condition-3 in the Precedence rule.**
  The "Precedence rule:" paragraph of
  `em-workflow/references/batch-terminal-line.md` states that the stop raised
  by the Control-character check of Step I.2.a in
  `references/implement-phase.md` binds to the `stop-condition-3` row
  (`step_needs_intervention`) and not to `unmapped_stop`. The stop's route:
  the check writes `implement: failed` / `failed_kind: decision` in the
  current run, has no phase-specific row of its own, and control returns
  through develop's stop condition 3.
- **FR2: Keep the current-run exclusion of stop-condition-3.**
  The existing restriction of the `stop-condition-3` row stays as it is: it
  binds a stop at Step B's entry evaluation that reads a `failed` /
  `needs_update` status no route of the current run produced, further
  restricted for `implement` to `failed_kind` reading `decision` or to the
  automatic-resume cap. The control-character stop is stated as a named
  exception to that exclusion, not as a rewording of it.
- **FR3: Document test pinning the binding.**
  A document test pins the binding of FR1 and the preservation of FR2. It
  fails when the paragraph no longer binds the Step I.2.a control-character
  stop to `stop-condition-3` / `step_needs_intervention`. It also fails when
  the current-run exclusion phrase is removed.

### Non-Functional Requirements

- **NFR1 - Precedence rule paragraph stays one block:** The
  "Precedence rule:" paragraph stays one block with no blank line inside it.
  Existing tests slice it from its label to the next blank line:
  `tests/test_batch_stop_contract.py`,
  `tests/test_abort_terminal_commit_precedence.py` and
  `tests/test_failed_kind_batch_docs.py`.
- **NFR2 - Pinned anchor phrases survive:** Every anchor phrase existing
  tests pin inside the paragraph survives unchanged. These include:
    - "phase-specific stop point takes precedence over the generic"
    - "through that phase's own abort route"
    - "no route of the current run produced"
    - "binds a stop at Step B's entry evaluation that reads a `failed` /
      `needs_update` status no route of the current run produced" (it must
      stay before "`failed_kind` reads `decision`")
    - "write a step's status"
    - "aborts without writing any status"
    - "the failed status write is itself its stop cause"
    - the collision sentences
    - "confined to that one collision"
    - "exit-4 stops keep their binding to `docs_commit_conflict_aborted` alone"

  The retired phrases "no phase-specific row covers" and "all three leave a
  step's status `failed`" and the token `no-work-required` do not appear in
  the paragraph.
- **NFR3 - Reason codes and coverage rows unchanged:** The stop reason code
  set (thirteen codes) and the Stop point coverage table (fourteen rows) stay
  unchanged. No new reason code and no new coverage row are added.
- **NFR4 - Standard-library document test convention:** The new test uses
  only the Python standard library `unittest`. It follows the repository's
  document-test convention: read the file relative to the test module, slice
  the owned region, normalize whitespace, assert distinctive phrases, and give
  every new matcher a negative proof against the verbatim pre-change
  paragraph.
- **NFR5 - Plugin version unchanged:** The em-workflow plugin version is not
  changed by this feature.

## Implementation Approach

### Files

- `em-workflow/references/batch-terminal-line.md` — the "Precedence rule:"
  paragraph is edited (FR1, FR2). This is the only document edited (A1).
- `em-workflow/references/implement-phase.md` — the Control-character check
  paragraph of Step I.2.a stays as it is (A1).
- `tests/test_control_char_abort_stop_reason.py` (example name) — a new test
  module holding the document test of FR3 (A4). Existing pinned test modules
  are not rewritten.

### Dependencies

**Internal Dependencies:**
- `tests/test_batch_stop_contract.py`,
  `tests/test_abort_terminal_commit_precedence.py`,
  `tests/test_failed_kind_batch_docs.py`: existing tests that slice the
  "Precedence rule:" paragraph and pin phrases inside it (NFR1, NFR2).

**External Dependencies:**
- Python standard library `unittest` (NFR4).

## Assumptions

- **A1:** Only `em-workflow/references/batch-terminal-line.md` is edited. The
  Control-character check paragraph in
  `em-workflow/references/implement-phase.md` stays as it is: it already says
  control returns through develop's stop condition 3.
- **A2:** The exception names the Step I.2.a control-character stop
  specifically. It is not a general rule for every current-run route that
  writes `implement: failed` / `failed_kind: decision`. The other such route,
  Step I.2.c's "route-back gate rejected" path, is interactive-only: in batch,
  route-back-to-planning is never taken automatically. So it is out of this
  batch contract's reach.
- **A3:** If the control-character stop's terminal status commit runs out of
  `commit-docs.sh` exit-4 recovery, it keeps binding to
  `docs_commit_conflict_aborted`. The run ends before any Step B evaluation
  reads the uncommitted `failed`. This feature does not change that binding,
  and the existing "Step I.2.a ... exit-4 stops keep their binding to
  `docs_commit_conflict_aborted` alone" sentence stays.
- **A4:** The new test goes in a new module under `tests/` (e.g.
  `tests/test_control_char_abort_stop_reason.py`). Existing pinned test
  modules are not rewritten.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/control-char-abort-stop-reason/**`
- `test-docs/control-char-abort-stop-reason/**`

`feature-docs/control-char-abort-stop-reason/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/control-char-abort-stop-reason/**` covers
`test-docs/control-char-abort-stop-reason/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/control-char-abort-stop-reason/` directory at all; the declared
`test-docs/control-char-abort-stop-reason/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests (document tests)

- [ ] **TS1** (AC1): Slice the "Precedence rule:" paragraph and normalize
  whitespace. Assert it names the Step I.2.a control-character check,
  `stop-condition-3` and `step_needs_intervention` as that stop's binding.
  Assert it does not bind that stop to `unmapped_stop`.
- [ ] **TS2** (AC2): Assert the phrase "no route of the current run produced"
  is still present, and that the control-character binding is stated as an
  exception to it.
- [ ] **TS3** (AC3): Negative proof: every new matcher yields a failure
  against the verbatim pre-change paragraph (current base revision text). A
  non-vacuity guard confirms the sample is the real Precedence paragraph.
- [ ] **TS4** (AC4): Assert the paragraph contains no blank line, and that the
  coverage table still has fourteen rows with no row added for the
  control-character stop.

### Integration Tests

- [ ] **TS5** (AC4): Run the full suite `python3 -m unittest discover -s tests`.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Batch terminal line contract: `em-workflow/references/batch-terminal-line.md`
- Implement phase (Step I.2.a Control-character check): `em-workflow/references/implement-phase.md`
