# Feature: rework-replan-artifact-digest

## Overview

create-plan's per-target action decision also accepts a match against the
last `artifacts` entry for the path in `phase-state/rework.yaml`, in addition
to `phase-state/create-plan.yaml`, and gives such a target `replace_own`.
The rule lives in `references/contracts/spec-writer-contract.md`, section
"How the orchestrator chooses each target's action before dispatch", and
`references/phases/create-plan-phase.md` sections 4 and 13 cite it. Document
pin tests in `tests/test_artifact_digest_docs.py` fix the rule.

## Objectives

- After a spec-change transition, create-plan re-planning in batch does not
  stop when rework-planner earlier rewrote planning artifacts
  (VERIFICATION.md, IMPLEMENTATION.md, task plans), and the planner can
  update them to the revised SPEC.
- A regression test detects this false digest mismatch if it comes back.

## User Stories

### US1: Re-planning after rework does not stop on a false digest mismatch
As an em-workflow user running a batch workflow, I want create-plan
re-planning after a spec-change transition to treat planning artifacts that
rework-planner rewrote as the planner's own output, so that the planner can
update them to the revised SPEC.

**Acceptance Criteria:**
- [ ] AC-1 (FR1, FR3): spec-writer-contract.md's action-decision section
  states that, for create-plan, a match with the last artifacts entry for the
  path in `phase-state/create-plan.yaml` or in `phase-state/rework.yaml` gives
  `replace_own`.
- [ ] AC-2 (FR2): The same section states that a create-plan target matching
  neither entry takes the existing `create-plan.artifact-overwrite` gate /
  `batch-policies.yaml` decision.
- [ ] AC-3 (FR5, FR6): The same section states the rework.yaml read
  conditions (phase `rework`, matching feature, otherwise no record) and that
  Legacy records applies to rework.yaml values.
- [ ] AC-4 (FR4, NFR3): create-plan-phase.md sections 4 and 13 (including
  "Feature-docs correction dispatch") each cite
  `references/contracts/spec-writer-contract.md` and "How the orchestrator
  chooses each target's action before dispatch", without `git hash-object`
  and without restatement markers.
- [ ] AC-5 (NFR1, NFR2): artifact-digest.md still has its six level-2
  sections and six registry rows, and every NFR2 pinned statement is
  present.

### US2: A regression test catches the false mismatch
As an em-workflow maintainer, I want document pin tests for the new rule, so
that a regression of this false digest mismatch is detected.

**Acceptance Criteria:**
- [ ] AC-6 (FR7, NFR4): New tests in `tests/test_artifact_digest_docs.py`
  cover AC-1 to AC-4, each with a forged-text non-vacuity case, and the full
  test command passes.

## Technical Requirements

### Functional Requirements
- **FR1: Planning-lineage match in create-plan's action decision** — In
  `references/contracts/spec-writer-contract.md`, section "How the
  orchestrator chooses each target's action before dispatch", for an
  implementation-planner dispatch of create-plan, a target path that exists
  and whose current digest equals the last `artifacts` entry for that path in
  `phase-state/create-plan.yaml`, or the last `artifacts` entry for that path
  in `phase-state/rework.yaml`, gets the action `replace_own`.
- **FR2: Mismatch branch unchanged** — A create-plan target whose current
  digest matches neither of the two last entries in FR1 takes the existing
  digest-mismatch branch: the `create-plan.artifact-overwrite` gate in
  interactive mode, and the `references/batch-policies.yaml` decision in
  batch mode.
- **FR3: Every create-plan action decision** — FR1 applies to every
  create-plan action decision: the section 4 planner dispatch (first pass,
  re-dispatches, and re-planning after a spec-change transition or tier
  upgrade), and the section 13 final-path correction dispatch and
  feature-docs correction dispatch.
- **FR4: Site sections cite the action-decision owner** —
  `references/phases/create-plan-phase.md` section "4. Planner dispatch",
  section "13. Final-path correction dispatch" and its subsection
  "Feature-docs correction dispatch" cite
  `references/contracts/spec-writer-contract.md`, "How the orchestrator
  chooses each target's action before dispatch", by path and section name,
  without restating the rule.
- **FR5: rework.yaml read conditions** — A rework.yaml record counts for FR1
  only when the file's mapping has phase `rework` and a feature equal to the
  workflow's feature. An absent file, an unreadable or malformed file, a
  mismatched phase or feature, or no `artifacts` entry for the path all count
  as no record from rework.yaml.
- **FR6: Legacy records apply to rework.yaml values** — A rework.yaml
  recorded value that differs from the file's current digest is compared as
  `references/artifact-digest.md` "Legacy records" states, the same way as a
  create-plan.yaml recorded value.
- **FR7: Regression document tests** — `tests/test_artifact_digest_docs.py`
  pins FR1 (both phase-state files named in the owner section), FR2 and FR4
  (each site section cites the owner by path and section name). Each
  assertion has a forged-text case proving its matcher fails without the
  rule.

### Non-Functional Requirements
- **NFR1 - Recording and owner structure unchanged:**
  `references/artifact-digest.md` keeps exactly its six level-2 sections and
  its six Dispatch sites rows. Layer 5 recording keeps its destination:
  rework-planner writes go to `phase-state/rework.yaml`, create-plan writes
  to `phase-state/create-plan.yaml`.
- **NFR2 - Pinned statements kept:** These stay: "Rework's action choice is
  unchanged" in artifact-digest.md Legacy records and in
  rework-task-synthesis.md section 10's "Dispatch input (step 2, all four
  routes)" paragraph; artifact-digest.md's statement that plan-patch
  permissions, re-planning authorization and rework's action choice are not
  changed by that document; the `spec_change` flag-pair row in
  phase-state.md; and `create-plan.artifact-overwrite = preserve_and_reuse`
  in batch-policies.yaml.
- **NFR3 - No restatement in site sections:** create-plan-phase.md does not
  contain `git hash-object`, and sections 4 and 13 carry none of the
  owner-restatement markers that `tests/test_artifact_digest_docs.py`
  checks.
- **NFR4 - Test constraints:** Tests use the Python standard library only,
  and `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
  passes.

## Implementation Approach

### Architecture

**Component Diagram:**
```
references/contracts/spec-writer-contract.md
  "How the orchestrator chooses each target's action before dispatch"
    owns the create-plan matching rule (FR1, FR2, FR5, FR6)
        ^ cited by path and section name (FR4)
references/phases/create-plan-phase.md
  "4. Planner dispatch"
  "13. Final-path correction dispatch"
    "Feature-docs correction dispatch"

references/artifact-digest.md
  "Legacy records" applied to rework.yaml values (FR6)
  structure unchanged (NFR1, NFR2)

tests/test_artifact_digest_docs.py
  document pin tests with forged-text cases (FR7)
```

### Data Flow

```
create-plan action decision for an existing target path
  → current digest
  → compare with last artifacts entry for the path in phase-state/create-plan.yaml
  → compare with last artifacts entry for the path in phase-state/rework.yaml
      (counts only when phase is rework and feature matches; otherwise no record)
  → either matches → replace_own
  → neither matches → create-plan.artifact-overwrite gate (interactive)
                      / references/batch-policies.yaml decision (batch)
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `references/artifact-digest.md` "Legacy records": comparison of recorded
  values that differ from the current digest (FR6).
- `references/batch-policies.yaml`: batch-mode decision for
  `create-plan.artifact-overwrite` (FR2).

**External Dependencies:**
- Python standard library only (NFR4).

### File Structure

```
em-workflow/references/contracts/spec-writer-contract.md   # matching rule (FR1, FR2, FR3, FR5, FR6)
em-workflow/references/phases/create-plan-phase.md         # citations in sections 4 and 13 (FR4)
tests/test_artifact_digest_docs.py                         # document pin tests (FR7)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/rework-replan-artifact-digest/**`
- `test-docs/rework-replan-artifact-digest/**`

`feature-docs/rework-replan-artifact-digest/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rework-replan-artifact-digest/**` covers
`test-docs/rework-replan-artifact-digest/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rework-replan-artifact-digest/` directory at all; the declared
`test-docs/rework-replan-artifact-digest/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1, FR3): Slice spec-writer-contract.md's action-decision
  section. Assert that it names `phase-state/create-plan.yaml` and
  `phase-state/rework.yaml`, the last-entry rule, and `replace_own` for
  create-plan. A forged section without rework.yaml fails the matcher.
- [ ] TS-2 (FR2): Assert that the same section routes a create-plan target
  with no match to `create-plan.artifact-overwrite` /
  `references/batch-policies.yaml`. A forged section without that routing
  fails.
- [ ] TS-3 (FR5, FR6): Assert that the same section states the
  phase/feature read conditions, the fail-closed no-record case, and a
  citation of "Legacy records" for rework.yaml values.
- [ ] TS-4 (FR4, NFR3): For create-plan-phase.md "4. Planner dispatch",
  "13. Final-path correction dispatch" and "Feature-docs correction
  dispatch", assert a citation of the spec-writer-contract.md path and
  section name, no `git hash-object`, and no restatement markers. A forged
  section without the citation fails.

### Integration Tests
- [ ] TS-5 (NFR1, NFR2): The existing tests `TestOwnerDocumentStructure`,
  `TestDispatchSitesRegistry`, `TestLegacyRecords`,
  `test_rework_dispatch_input_paragraph_records_into_rework_yaml` and
  `tests/test_spec_change_replan_authorization.py` still pass unchanged.
- [ ] TS-6 (NFR4): The full test command passes.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

Not applicable.

## Error Handling

A rework.yaml that is absent, unreadable or malformed, or whose phase or
feature does not match, counts as no record from rework.yaml (FR5).

## Performance Optimization

Not applicable.

## Assumptions

- **A1:** Fix mechanism: planning-lineage records. create-plan's action
  decision also reads `phase-state/rework.yaml` artifacts (answer
  `requirement.fix-mechanism` = `planning_lineage_records`, via batch Codex
  consultation).
- **A2:** Match rule: the last entry for the path in either file (answer
  `requirement.match-scope` = `last_entry_in_either_file`).
- **A3:** Scope: every create-plan action decision, the section 13
  correction dispatches included (answer `requirement.applicability` =
  `every_create_plan_action_decision`).
- **A4:** Test form: document pin tests in
  `tests/test_artifact_digest_docs.py` (answer `requirement.test-form` =
  `document_pin_tests`).
- **A5:** Placement: the matching rule lives in spec-writer-contract.md "How
  the orchestrator chooses each target's action before dispatch", and
  create-plan-phase.md sections 4 and 13 cite it. artifact-digest.md keeps
  its six level-2 sections.
- **A6:** Layer 5 recording destinations, rework's action choice and batch
  policy `create-plan.artifact-overwrite` stay unchanged.
- **A7:** The earlier failed feature run's artifacts are not repaired by
  this change.
- **A8:** The plugin version is not changed manually. Actions bumps the
  patch on push.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- spec-writer contract: `em-workflow/references/contracts/spec-writer-contract.md`
- create-plan phase: `em-workflow/references/phases/create-plan-phase.md`
- Artifact digest: `em-workflow/references/artifact-digest.md`
- Batch policies: `em-workflow/references/batch-policies.yaml`
- Phase state: `em-workflow/references/phase-state.md`
- Rework task synthesis: `rework-task-synthesis.md` (section 10)
- Document pin tests: `tests/test_artifact_digest_docs.py`
