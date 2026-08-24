# Verification Document: rework-contract-drift

## Overview

**Feature**: rework-contract-drift / **SPEC.md**: `feature-docs/rework-contract-drift/SPEC.md`
/ **IMPLEMENTATION.md**: `feature-docs/rework-contract-drift/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run, after every task has merged.
Per-task acceptance criteria live in the task plans and are not repeated here.

The design step is skipped for this feature — there is no UI surface — so no visual
comparison is part of this verification.

## Build Verification

- Command: none. The project declares no build command; the deliverables are Markdown
  documents, one Python script and stdlib test modules, none of which is compiled.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, the whole suite green, no third-party import in test code.
- Coverage target: no numeric coverage threshold is declared for this project. The
  binding coverage requirement is behavioral: each of FR1 through FR4 must have at least
  one assertion that fails against the pre-change tree, and every added assertion must
  read the live working-tree file rather than a frozen revision.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The planner prompt's two task-id allocation branches are keyed on the owning document's re-planning path | Both owner-defined states are covered; no create-plan step-status literal is used as the branch key; the assertion fails against the pre-change prompt | Unit |
| TS2 | A specification-change-transition re-planning patch, with the create-plan step at the status that transition produces and at least one merged task, is driven through the validator's dry-run apply mode | Accepted; neither the registered-identifier rejection nor the dropped-task rejection is raised | Integration |
| TS3 | Absence of the retired origin field name across the normative documents, the validator, the fixtures and the test modules, read live | Not found anywhere on the covered surface; the stated exclusions are named explicitly; each scan is non-vacuous and does not match itself | Unit |
| TS4 | The patch contract document's unspent-authorization condition is read from the live document | The condition names both members of the origin identity pair; the assertion fails against the pre-change document | Unit |
| TS5 | The validator is given failing items whose category is missing, empty, or out of vocabulary, and then each of the seven vocabulary values | The first three are rejected; all seven vocabulary values are accepted | Unit |
| TS6 | Gate behavior across every category value and every degraded evidence state | Security, license, sentinel, missing, unreadable and out-of-vocabulary all abort, in final and non-overridable wording; the four remaining values proceed to classification; a sentinel case reaches the gate rather than being stopped before it | Integration |
| TS7 | A verify-origin question packet built per the renamed schema is put through origin verification, alongside the pre-change shape | The renamed packet passes; the pre-change packet is rejected with a reason naming the missing origin identifier | Integration |
| TS8 | The validator is given an out-of-vocabulary origin kind | Rejected, mirroring the existing enforcement of the classification vocabulary | Unit |
| TS9 | A rework record written in the pre-change shape is handled per the chosen compatibility rule | Read as the current format version; its pre-change shape refused at the point of use with the named diagnostic; the named remedy is stated; never silently non-re-enterable | Integration |
| TS10 | The full suite is run under the project's own runner and both plugin manifests are read | Suite green with no third-party test dependency; both manifests carry the same raised version, differing from the pre-change value only in its patch component | Integration |
| TS11 | Each rule this feature touches is checked for a single owner | Each owning document states the rule; each citing site names the owner by repository-relative path and restates no part of the rule; a negative proof fires against a synthetic restating copy | Unit |
| TS12 | The patch contract document is checked for the interrupted-consumption recovery rule and for the ownership-boundary section's coverage of the phase-state crossing | Both are present; the recovery rule states idempotency and that a resumed run reaches the same state as an uninterrupted one | Unit |
| TS13 | The phase-state idempotency section is checked for the classification record's replay rule | Present, consistent with the section's treatment of the other append-type records | Unit |
| TS14 | The delivered change is checked for the two rejected items | No fixture is migrated on the grounds of the rejected claim, and no performance work is present in any requirement, criterion, task or test | Integration |
| TS15 | The planner prompt is checked for the high-water-mark restatement | No formula and no restated statement of which identifiers it counts survives; the owning definition is cited | Unit |
| TS16 | The gate's category check is read for its independence declaration and its reversibility arm | The declaration and the arm agree; the arm is retained with its fail-closed handling unchanged | Unit |
| TS17 | The patch contract document's interrupted-spend recovery procedure is read from the live document (review round 1 rework) | It sits outside the numbered application-rule list and the list's count statement matches the numbered rules it holds; its recognition condition defers to the phase-state document's already-applied determination for the patch in hand, identified by the patch's own identifier; a base-workflow-blob mismatch the determination does not confirm is stated to remain an ordinary rejection that spends no authorization; the idempotency properties and the ownership-boundary crossing survive | Unit |
| TS18 | A workflow record whose verify-step failing items predate the required category is driven through the validator, once with a patch that touches no verify step and once with a patch that targets it (review round 1 rework) | The first is accepted with no category error; the second is still rejected, as is a non-conforming item the patch itself supplies; the field's required-ness, its vocabulary and the gate-side abort are unchanged, and the owning schema document states the pre-change compatibility rule | Integration |

## Code Quality Verification

- Format: none declared by the project. Test modules follow the naming already used
  throughout the suite: files named for the behavior under test, classes named for the
  behavior, methods naming the condition and the expected result.
- Static analysis: none declared. The de facto static check is that the validator
  script remains importable by the test modules that drive it.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The prompt and the planner contract no longer carry the step-status-keyed re-planning condition, and both cite the owning re-planning path | TS1 |
| AC2 | The two-branch test asserts both owner-defined paths and no longer pins the erroneous literal, failing against the pre-change prompt | TS1 |
| AC3 | The retired origin field name is absent from every document, script, fixture and test module on the covered surface | TS3, plus the integrated repository-wide check below |
| AC4 | The workflow schema defines the failing-item category as required, with its closed seven-value vocabulary | TS5, TS11 |
| AC5 | The gate's category check cites that definition and states the gate-side abort in the same non-overridable wording the membership check uses | TS6 |
| AC6 | A sentinel-category case reaches the classification gate, and the gate aborts it | TS6 |
| AC7 | The specification document, the verification document format, the verification index, the retrospect phase and the rework planner are unchanged | TS14, plus the integrated out-of-scope check below |
| AC8 | The validator rejects an out-of-vocabulary origin kind and an out-of-vocabulary or missing failing-item category | TS5, TS8 |
| AC9 | An explicit, named resolution exists for the format-version question, stating what happens to a pre-change on-disk record | TS9 |
| AC10 | The suite is green in full and both manifests carry the same raised version | TS10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0007 | TS1, TS2 |
| FR2 | task0002 | TS3, TS4 |
| FR3 | task0003, task0004, task0008 | TS5, TS6, TS18 |
| FR4 | task0004 | TS3, TS7 |
| FR5 | task0002, task0008 | TS12, TS17 |
| FR6 | task0004 | TS8 |
| FR7 | task0005 | TS9 |
| FR8 | task0005 | TS13 |
| FR9 | task0004 | TS16 |
| FR10 | task0001 | TS15 |
| FR11 | task0002, task0008 | TS12, TS17 |
| NFR1 | task0003, task0004, task0008 | TS6, TS18 |
| NFR2 | task0001, task0002, task0003, task0004, task0005, task0007, task0008 | TS11, TS17 |
| NFR3 | task0004 | TS3, TS7 |
| NFR4 | task0001, task0002, task0004, task0007, task0008 | TS1, TS3, TS4, TS5, TS7, TS17, TS18 |
| NFR5 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008 | TS10 |
| NFR6 | task0006 | TS10 |
| NFR7 | task0004 | TS14 |

## Integration-only Checks

These are observable only after every task has merged, because no single task's worktree
contains the whole change set (IMPLEMENTATION.md D4).

- [ ] The union of the owner-scoped absence scans covers the whole surface named in
      IMPLEMENTATION.md D3, with no path left uncovered by every scan and no path claimed
      by two scans.
- [ ] A repository-wide search for the retired origin field name over the working tree,
      excluding only the paths named in IMPLEMENTATION.md D3, returns nothing.
- [ ] Every byte-identity pin in the shared pin module equals the digest of the file it
      covers, after all merges.
- [ ] The failing-item category definition written by task0003 and the enforcement
      written by task0004 agree on all seven values and on the required-ness of the field.
- [ ] The specification document, the verification document format, the verification
      index, the retrospect phase and the rework planner's own behavior are unchanged by
      the delivered change set.

## Manual Testing (E2E Not Possible)

There is no E2E infrastructure and no user flow to drive, so no automated end-to-end
suite applies. The following need human judgement.

- [ ] Confirm the chosen resolution of the phase-state format-version question
      (IMPLEMENTATION.md D5, a stated compatibility rule with the version unchanged) is
      the one intended. This is a planner-made choice the SPEC left open.
- [ ] Confirm the stated exclusion set for the retired-name search — this feature's own
      requirements and specification documents, the previous feature's delivered records,
      and git history — is the intended scope.
- [ ] Confirm the report to the user notes that a restart is required for the raised
      plugin version to take effect.

## Security Verification

- Fail-closed strength is not weakened anywhere: every newly written arm resolves to
  abort or reject when its evidence is absent, unreadable, or outside its vocabulary
  (TS5, TS6, TS8).
- No path lets an unattended run auto-classify a security- or license-related rework as
  a specification change: both values abort at the gate, non-overridably, and so does the
  sentinel assigned when security or license cannot be excluded (TS6).
- Input validation for both closed vocabularies is enforced in the validator (TS5, TS8).
- Authentication, authorization, data protection, cross-site scripting, injection and
  request forgery are not applicable — there is no user-facing surface, no request
  handling and no data store.

## Performance Verification

Not applicable. No performance requirement exists for this feature, and the performance
findings are excluded.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 18 | 18 | 0 | 0 |
| Success criteria | 10 | 10 | 0 | 0 |
| Integration-only checks | 5 | 5 | 0 | 0 |
| Manual confirmations | 3 | 0 | 0 | 3 |
