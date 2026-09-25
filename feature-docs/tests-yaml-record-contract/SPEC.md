# Feature: tests-yaml-record-contract

## Overview

Tighten the tests.yaml record contract owned by `em-workflow/agents/implementer.md`
Step 4c so that `red_confirmed` and `final_failures` record only what was actually
observed. Step 4c gains an explicit rule for criteria that have no executable red
(e.g. documentation-only tasks) and a recording discipline for `final_failures`;
Step 6 requires a re-run after parent-side adoption. A document-contract test pins
these rules. Requirements document: `feature-docs/tests-yaml-record-contract/REQUIREMENTS.md`.

## Objectives

- Make `test-docs/{feature}/{task}.tests.yaml`, as written by the implementer, evidence that subsequent tasks, verify, and the `unconfirmed_reds` aggregation can read mechanically without misattributing failures.
- State in the contract (`em-workflow/agents/implementer.md` Step 4c) how to write tests.yaml for tasks that have no executable red (documentation-type tasks, etc.), so the implementer does not have to invent its own interpretation.
- Make it distinguishable from the record whether `final_failures` is an actually observed run result or was inherited from the baseline without a re-run.

## User Stories

### US1: Criteria without an executable red
As the implementer agent, I want Step 4c to state how to record an Acceptance Criterion that has no executable check, so that I do not invent a local interpretation.

**Acceptance Criteria:**
- [ ] AC-1 (FR1)
- [ ] AC-2 (FR2)
- [ ] AC-3 (FR3)

### US2: `final_failures` recording discipline
As a reader of tests.yaml (subsequent tasks, verify phase, `unconfirmed_reds` aggregation), I want `final_failures` to state whether it reflects an actual re-run, so that failures are attributed correctly.

**Acceptance Criteria:**
- [ ] AC-4 (FR4)
- [ ] AC-5 (FR4)
- [ ] AC-6 (FR5)

### US3: Contract pinned by tests and released
As a maintainer, I want the new rules pinned by a document-contract test and shipped with a version bump.

**Acceptance Criteria:**
- [ ] AC-7 (FR6)
- [ ] AC-8 (FR7)
- [ ] AC-9 (NFR5)

## Technical Requirements

### Functional Requirements
- **FR1:** Recording form for a criterion with no executable red. `em-workflow/agents/implementer.md` Step 4c states that, for an Acceptance Criterion for which no executable check that can be made to fail (test, build, lint, etc.) exists, the implementer writes `tests: []`, `red_confirmed: false`, the reason no executable red exists in `red_reason`, and lists the criterion in the report's `unconfirmed_reds`. Tasks whose only deliverable is documentation are named explicitly as covered by this rule.
- **FR2:** Fix the meaning of `red_confirmed: true` and forbid local redefinition. Step 4c states that `red_confirmed: true` means only "with no implementation present, the executed check was actually observed to fail". It states that reading or searching for a document or anchor does not constitute observing a red. It forbids locally redefining the meaning of `tests` / `red_confirmed` / `red_reason` in `notes` or any other text.
- **FR3:** Align the report destination of `red_confirmed: false` with `unconfirmed_reds`. The current Step 4c wording that puts `red_confirmed: false` criteria "in the report's notes" is changed to put them in Step 7's report field `unconfirmed_reds`.
- **FR4:** `final_failures` recording discipline (comment form). Step 4c defines the recording discipline for `final_failures`. No key is added to tests.yaml; the record goes in the `final_failures` comment.
  - (a) The comment records the output of the run actually re-executed after implementation.
  - (b) The re-run may be skipped only when no file the suite reads (source, tests, documents the tests read) was changed at all. In that case the comment states "not re-run; baseline inherited" with the reason, and the report also states that no re-run was performed.
  - (c) If it cannot be confirmed that the skip condition holds, re-run.
  - (d) Do not write the same run result into both `baseline_failures` and `final_failures` as if they were two independent observations.
- **FR5:** Mandatory re-run after parent-side adoption. Step 6 states that after parent-side adoption the FR4 (b) skip condition does not apply, and the suite is always re-run and `baseline_failures` and `final_failures` are updated.
- **FR6:** Document-contract test. Add a document-contract test under `tests/` that pins the rules written into Step 4c / Step 6 by FR1-FR5. The test reads `em-workflow/agents/implementer.md` and checks that each rule is present.
- **FR7:** Plugin version bump. In the same change, raise the `version` in `em-workflow/.claude-plugin/plugin.json` and the `version` of the em-workflow entry in `.claude-plugin/marketplace.json` to the same value, by a patch increment.

### Non-Functional Requirements
- **NFR1 - Schema stability:** The tests.yaml schema (key structure) is not changed. Whether `final_failures` was re-run is expressed in a comment.
- **NFR2 - No machine validation:** No mechanism that machine-validates tests.yaml (validator, hook) is added.
- **NFR3 - Single owner:** The owner of the tests.yaml contract remains `em-workflow/agents/implementer.md` Step 4c; the same rules are not duplicated in other documents.
- **NFR4 - Test conventions:** Tests use only the Python standard library `unittest` and are placed at `tests/test_*.py` (convention in `test/README.md`).
- **NFR5 - No regression:** No regression in the existing test suite (`python3 -m unittest discover -s tests`).

## Implementation Approach

### Architecture

Documentation-contract change only. No runtime components, APIs, or data stores.

**Component Diagram:**
```
em-workflow/agents/implementer.md
  Step 4c  (tests.yaml contract owner)  <- FR1, FR2, FR3, FR4
  Step 6   (parent-side adoption)       <- FR5
  Step 7   (report: unconfirmed_reds, notes)  referenced by FR1, FR3, FR4 (b)

tests/test_*.py (document-contract test)  -- reads --> em-workflow/agents/implementer.md   (FR6)

em-workflow/.claude-plugin/plugin.json  \
.claude-plugin/marketplace.json          >-- same patch-bumped version (FR7)
```

### Data Flow

Not applicable.

### API Design

Not applicable.

### Database Schema

Not applicable. The tests.yaml key structure is unchanged (NFR1).

### Dependencies

**Internal Dependencies:**
- `em-workflow/agents/implementer.md` Step 7: the `unconfirmed_reds` and `notes` report fields referenced by FR1, FR3 and FR4 (b).

**External Dependencies:**
- Python standard library `unittest` (NFR4).

### File Structure

```
em-workflow/
├── agents/
│   └── implementer.md          # Step 4c / Step 6 edited (FR1-FR5)
└── .claude-plugin/
    └── plugin.json             # version bump (FR7)
.claude-plugin/
└── marketplace.json            # em-workflow version bump (FR7)
tests/
└── test_*.py                   # new document-contract test (FR6, NFR4)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/tests-yaml-record-contract/**`
- `test-docs/tests-yaml-record-contract/**`

`feature-docs/tests-yaml-record-contract/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/tests-yaml-record-contract/**` covers `test-docs/tests-yaml-record-contract/{T}.tests.yaml`, the
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
- [ ] TS-1 (AC-1; FR1): Extract the Step 4c section of `implementer.md` and check that it contains the rule for criteria with no executable check (`tests: []` / `red_confirmed: false` / `red_reason` / `unconfirmed_reds`) and a mention of documentation-only tasks.
- [ ] TS-2 (AC-2; FR2): Check that the Step 4c section contains the meaning of `red_confirmed: true` (observed failure of an executed check), that reading a document is not an observation, and the prohibition on locally redefining field meanings.
- [ ] TS-3 (AC-3; FR3): Check that in the Step 4c section the report destination for `red_confirmed: false` is `unconfirmed_reds`, and that no wording to "put it in notes" remains.
- [ ] TS-4 (AC-4, AC-5; FR4): Check that the Step 4c section contains: recording the re-run output in `final_failures`, the skip condition (no change to files the suite reads), the "baseline inherited" wording and the report statement when skipping, re-running when the condition cannot be confirmed, and the prohibition on presenting the same run result twice.
- [ ] TS-5 (AC-6; FR5): Check that the Step 6 section states that the re-run after parent-side adoption is not subject to the skip condition.

### Integration Tests
- [ ] TS-6 (AC-7; FR6): Run the document-contract test against `implementer.md` before the change and observe it fail; confirm it passes after the change.
- [ ] TS-7 (AC-8; FR7): Confirm the em-workflow version in plugin.json and marketplace.json match and are a patch increment above the previous value.
- [ ] TS-8 (AC-9; NFR5): Run `python3 -m unittest discover -s tests` at the repository root and confirm there is no regression.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] A task mixing criteria with and without executable tests: apply FR1 or the normal rule per criterion.
- [ ] A criterion verified by a build or lint result: `red_confirmed: true` only if the failure of that check was actually observed before implementation.
- [ ] A documentation-only task for which a document-contract test reading that document can be written: an executable red exists, so the normal rule applies.
- [ ] A task that changed a document the tests read: the `final_failures` re-run cannot be skipped.
- [ ] It cannot be confirmed whether a changed file is read by the suite: re-run.
- [ ] Step 6 conflict loop: re-run after every parent-side adoption.

### Performance Tests
Not applicable.

## Security Considerations

Not applicable.

## Error Handling

Not applicable.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC-1: `implementer.md` Step 4c states that a criterion with no executable check gets `tests: []`, `red_confirmed: false`, a reason in `red_reason`, and an entry in the report's `unconfirmed_reds`, and names documentation-only tasks as covered.
- [ ] AC-2: Step 4c states that `red_confirmed: true` means only that the failure of an executed check was observed before implementation, that reading a document is not observing a red, and that the meaning of `tests` / `red_confirmed` / `red_reason` must not be locally redefined in `notes` or elsewhere.
- [ ] AC-3: Step 4c points to `unconfirmed_reds` as the report destination for `red_confirmed: false` criteria, and no wording pointing to `notes` remains.
- [ ] AC-4: Step 4c states that the `final_failures` comment records the output of the run actually re-executed; that the re-run may be skipped only when no file the suite reads (source, tests, documents the tests read) was changed at all; that when skipped, "not re-run; baseline inherited" is written with the reason and also stated in the report; and that the re-run happens if the skip condition cannot be confirmed.
- [ ] AC-5: Step 4c states that the same run result must not be presented as two independent observations in `baseline_failures` and `final_failures`.
- [ ] AC-6: Step 6 states that after parent-side adoption the skip condition does not apply and a re-run is always performed.
- [ ] AC-7: The document-contract test under `tests/` checks the rules of AC-1 to AC-6, fails against the pre-change `implementer.md`, and passes after the change.
- [ ] AC-8: The em-workflow version in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` is the same value and is a patch increment above the previous value.
- [ ] AC-9: `python3 -m unittest discover -s tests` passes with no regression.

## Assumptions

- ASM-1: The `final_failures` recording form follows the answer to create-spec-q0001 (`comment_rerun_required_unless_untouched`): comment form, no new key.
- ASM-2: The report destination for stating that the re-run was skipped is the existing Step 7 report field `notes` (no field is added to the report schema).
- ASM-3: The existing example `test-docs/i2c-routeback-reconciliation/task0001.tests.yaml` is not modified; the definition of done is limited to the `implementer.md` contract and the document-contract test.
- ASM-4: `em-workflow/skills/tdd-testing/SKILL.md` and `em-workflow/skills/worktree-task-workflow/SKILL.md` are not changed; the SSOT for the tests.yaml contract is `implementer.md` Step 4c.
- ASM-5: The `tests_yaml_path` description in `em-workflow/references/implement-phase.md` (`baseline_failures` / `final_failures` and the per-criterion AC -> test mapping of observed reds) does not conflict with the changed contract and is not changed.
- ASM-6: The version increment is a patch (0.2.8 -> 0.2.9 at the base revision; if other changes have advanced the value by implementation time, bump by a patch from that value).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- Requirements document: `feature-docs/tests-yaml-record-contract/REQUIREMENTS.md`
- tests.yaml contract owner: `em-workflow/agents/implementer.md` (Step 4c, Step 6, Step 7)
- `tests_yaml_path` hand-off: `em-workflow/references/implement-phase.md`
