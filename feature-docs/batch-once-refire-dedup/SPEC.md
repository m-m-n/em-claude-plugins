# Feature: batch-once-refire-dedup

## Overview

State, in em-workflow's own documents, the operating contract under which firing `--batch --once` repeatedly from an external service does not create duplicate features (duplicate integration branches) for the same task, and pin that contract with tests. The continuation of a run that ended at a `--once` phase boundary is re-launched by passing the structured result's `feature` value as the path argument, without passing the task description again. The existing Step A rules are kept unchanged.

Requirements document: `feature-docs/batch-once-refire-dedup/REQUIREMENTS.md`.

## Objectives

- State in em-workflow's documents the operating contract under which firing `--batch --once` repeatedly from an external service creates no duplicate feature (duplicate integration branch) for the same task, and pin it with tests.
- Keep the existing Step A rules: no path argument always means a new feature; existing branches are never enumerated or guessed from; resuming is possible only through the explicit feature name.

## User Stories

### US1: Re-launch after a `--once` phase boundary
As an external dispatcher, I want to re-launch a run that ended at a `--once` phase boundary by passing the result's `feature` value as the path argument, so that the same task does not get a duplicate feature.

**Acceptance Criteria:**
- [ ] AC1 (FR1): The Step A feature resolution row of `batch-mode.md` states that a re-launch after a `--once` phase boundary passes the result's `feature` value as the path argument and does not pass the task description again.
- [ ] AC2 (FR1, FR2): The existing rules of the `batch-mode.md` Step A row (no path argument → always a new feature; existing branches are never enumerated or guessed from; resuming requires the explicit feature name) remain, and the existing wording of SKILL.md's 「パス引数なし」 item and Step A 「feature の決定」 remains.
- [ ] AC3 (FR3): The `phase_done` description in `batch-terminal-line.md` still contains "re-launches the same feature" and states that the result's `feature` value is passed as the path argument and the task description is not passed again.

### US2: Contract pinned by tests
As a maintainer, I want the re-launch contract wording and the existing Step A rules pinned by regression tests, and the em-workflow version bumped by a patch step, so that the contract stated in em-workflow's documents is fixed by tests.

**Acceptance Criteria:**
- [ ] AC4 (FR4, NFR1, NFR2): The FR4 tests exist and `python3 -m unittest discover -s tests` passes in full. For each FR4 check there is a test showing the check fails on forged text lacking the wording.
- [ ] AC5 (FR5): The `version` in em-workflow's `plugin.json` and in `marketplace.json` are the same value, raised by a patch step from before the change.

## Technical Requirements

### Functional Requirements
- **FR1:** batch-mode.md Step A row states the re-launch contract. In the Non-packet gates table of `em-workflow/references/batch-mode.md`, the "Step A feature resolution" row states that the continuation of a run that ended at a `--once` phase boundary is re-launched by passing the structured result's `feature` value as the path argument, and that the task description is not passed again. The row's existing text (Explicit feature-name/path argument wins / No path argument → always a new feature / Existing branches are never enumerated, and a feature is never guessed from them — resuming requires the explicit feature name) is kept.
- **FR2:** SKILL.md Step A rules are not changed. The 「パス引数なし」 item under 「引数処理」 in `em-workflow/skills/develop/SKILL.md`, and the Step A 「feature の決定」 text (resuming an existing feature is possible only through this path / no path argument means a new feature / existing branches are never enumerated or guessed from), are not changed. develop's feature resolution rules are not changed.
- **FR3:** batch-terminal-line.md clarifies the `phase_done` re-launch. The `state` item (the `phase_done` description) under `## Field values` in `em-workflow/references/batch-terminal-line.md` states that a re-launch passes the result's `feature` value as the path argument and does not pass the task description again. The existing phrase "re-launches the same feature" is kept.
- **FR4:** Regression tests are added. Under `tests/`, add tests that check: (1) the `batch-mode.md` Step A row contains the re-launch contract (pass the `feature` value as the path argument; do not pass the task description again); (2) the `phase_done` description in `batch-terminal-line.md` contains the same contract; (3) the existing no-enumeration and new-feature rules of the `batch-mode.md` Step A row remain. Each check is shown to fail on forged text lacking the wording.
- **FR5:** The em-workflow plugin version is bumped. Raise `version` in `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry's `version` in the repository-root `.claude-plugin/marketplace.json` to the same value by a patch step, in the same change.

### Non-Functional Requirements
- **NFR1 - Test suite:** `python3 -m unittest discover -s tests` passes in full.
- **NFR2 - Test dependencies:** The added tests use only the Python standard library (unittest).
- **NFR3 - SKILL.md literal guard:** Do not bring terminal-line `state` value literals or SC5-forbidden literals into SKILL.md (the existing guard in `tests/test_develop_once_option.py` is kept).
- **NFR4 - Format ownership:** Do not break the relationship in which `batch-terminal-line.md` is the sole owner of the structured result's format. `batch-mode.md` does not redefine the format and states only how the `feature` value is used.

## Implementation Approach

### Architecture

Not applicable. The change touches reference documents, tests and version fields only; develop's feature resolution rules are not changed.

**Component Diagram:**
```
batch-terminal-line.md  -- sole owner of the structured result format (incl. `feature`, `state`)
batch-mode.md           -- Step A row: how the `feature` value is used on re-launch (no format redefinition)
skills/develop/SKILL.md -- Step A rules, unchanged
tests/                  -- pin the contract wording and the existing Step A rules
```

### Data Flow

```
--batch --once run ends at a phase boundary (state phase_done, feature = Step A slug)
  → external dispatcher re-launches with the `feature` value as the path argument (no task description)
  → Step A resumes the explicitly named feature
```

### API Design

Not applicable. The structured result format is owned by `em-workflow/references/batch-terminal-line.md` and is not changed.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-terminal-line.md`: the `feature` item's existing rule that a `phase_done` result always carries the slug fixed at Step A (A3).
- `tests/test_batch_stop_contract.py`: pins the phrase "re-launches the same feature" (A5).
- `tests/test_develop_once_option.py`: SC5 / `state` literal guard on SKILL.md (NFR3).
- `tests/test_review_implement_develop_lock_contracts.py`: existing checks on SKILL.md's Step A wording (TS2).

**External Dependencies:**
- Python standard library `unittest` only (NFR2).

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json          # FR5: version patch bump
├── references/batch-mode.md            # FR1: Step A feature resolution row
├── references/batch-terminal-line.md   # FR3: `state` item, `phase_done` description
└── skills/develop/SKILL.md             # FR2: unchanged
.claude-plugin/marketplace.json         # FR5: em-workflow entry version
tests/                                  # FR4: new regression tests
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/batch-once-refire-dedup/**`
- `test-docs/batch-once-refire-dedup/**`

`feature-docs/batch-once-refire-dedup/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/batch-once-refire-dedup/**` covers `test-docs/batch-once-refire-dedup/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/batch-once-refire-dedup/` directory at all; the declared
`test-docs/batch-once-refire-dedup/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1; FR1): Read `batch-mode.md`, extract the Step A feature resolution row of the Non-packet gates table, and confirm it contains the re-launch contract wording (pass the `feature` value as the path argument; do not pass the task description again).
- [ ] TS2 (AC2; FR1, FR2): Confirm the same `batch-mode.md` row contains the existing new-feature rule and the no-enumeration / no-guessing wording, and that SKILL.md's existing Step A wording remains (the SKILL.md side keeps the existing checks in `tests/test_review_implement_develop_lock_contracts.py`).
- [ ] TS3 (AC3; FR3): Extract the `state` item under `## Field values` in `batch-terminal-line.md` and confirm it contains "re-launches the same feature" and the re-launch contract wording.
- [ ] TS4 (AC4; FR4, NFR1, NFR2): Feed each TS1-TS3 matcher forged text lacking the contract wording and confirm it fails (non-vacuity check).

### Integration Tests
- [ ] TS5 (AC4, NFR3; FR4, NFR1, NFR2, NFR3): Run `python3 -m unittest discover -s tests` and confirm the existing tests (including the SC5 / `state` literal checks in `test_develop_once_option.py` and `test_batch_stop_contract.py`) and the new tests all pass.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] When a re-launch receives both a path argument and a task description, the path argument wins (existing rule).
- [ ] A `state` `stopped` result (e.g. Step A abort) with an empty `feature` is outside the re-launch contract; only `phase_done` is covered.
- [ ] A re-launch after ending at the retrospect boundary runs Step C; if a PR is needed, pass `--pr` on the re-launch (existing rule).
- [ ] A path-argument feature name not matching `^[a-z0-9][a-z0-9-]*$` aborts at Step A (existing rule).
- [ ] Even if the integration worktree has been deleted, re-launching with the path argument recreates it via `git worktree add` (existing rule).

### Performance Tests
Not applicable.

## Security Considerations

- **Input Validation:** The feature name passes the existing fail-closed identifier gate before being interpolated into shell commands (unchanged).
- **Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF:** Not applicable.

## Error Handling

Not applicable. No new error paths are introduced; the Step A abort on an invalid feature name is an existing rule.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1-AC5 are satisfied

## Assumptions

- **A1:** The re-fire countermeasure adopts approach (a) (the external dispatcher carries the feature name). develop's feature resolution rules are not changed; the em-workflow side only states the re-launch contract and pins it with tests. Approach (b) external-ID matching and (c) duplicate reporting are not adopted.
- **A2:** Changing the out-of-repository `~/.claude/skills/notion-batch-develop/SKILL.md` (implementing feature-name carry-over) is out of scope for this feature and handled separately.
- **A3:** The `feature` of a result ending at a `--once` phase boundary (`state` `phase_done`) always carries the slug fixed at Step A (existing rule in the `feature` item of `batch-terminal-line.md`).
- **A4:** If a dispatcher ignores the contract and re-fires with the task description, a new feature is created as before (develop's behavior is not changed).
- **A5:** `tests/test_batch_stop_contract.py:1042` pins the phrase "re-launches the same feature" in `batch-terminal-line.md`.

## Out of Scope

- Changes to `~/.claude/skills/notion-batch-develop/SKILL.md`
- Changes to develop's feature resolution rules (external-ID matching, enumerating existing branches)
- Detecting or reporting duplicate features

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None

## References

- Requirements: `feature-docs/batch-once-refire-dedup/REQUIREMENTS.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/skills/develop/SKILL.md`
