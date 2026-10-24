# Feature: rework-recheck-before-patch-write

## Overview

In `em-workflow/references/rework-task-synthesis.md` section 10, the
return-time recheck of a rework-planner result is placed after step 3's
validation and before step 3's application of the rework patch. A stale
recheck therefore leaves no workflow.yaml write and no commit from the patch.
A regression probe in `tests/test_recheck_dispatch_sites_docs.py` asserts this
order.

## Objectives

- When the return-time recheck of a rework-planner result returns stale, the
  rework patch has not written workflow.yaml and has not been committed. The
  stale result leaves nothing in the workflow.

## Technical Requirements

### Functional Requirements

- **FR1: Recheck before the patch write in rework section 10.** In
  `em-workflow/references/rework-task-synthesis.md` section 10, the
  "Return-time digest (steps 2 and 3, all four routes)" paragraph puts the
  return-time recheck after step 3's validation (application rules 1-14 of
  `references/workflow-patch.md`, including rule 1's comparison of the
  substituted `digest_source`) and before step 3's application (rule 15's
  single Write to workflow.yaml and rule 16's R2 commit sequence). The
  paragraph states that the patch is applied only after a passing recheck. A
  recheck mismatch, or a recheck that cannot run, makes the result stale
  before any workflow.yaml write or commit made by the patch.
- **FR2: Keep the citation form and the recording-write order.** The recheck
  sentence keeps its current form. It cites
  `references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
  comparison timing", names the orchestrator as the actor, and states that a
  mismatch or a recheck that cannot run is stale. It does not restate what the
  recheck compares, the membership matrix or the substitution. The recheck
  still comes before the phase-state write that records `self_write_set`
  together with the Layer 5 recording of `written_artifacts` into
  `phase-state/rework.yaml`.
- **FR3: Keep the step numbering of section 10.** Section 10's fixed-order
  steps 1-4 keep their numbers and their meaning. The recheck is stated inside
  step 3 / the Return-time digest paragraph, not as a new numbered step.
  External citations depend on the numbering: `review-phase.md` "after step
  1", develop `SKILL.md` "step 1 は行わず step 2 から", and the paragraph's
  own "steps 2 and 3".
- **FR4: Regression test for the recheck-before-application order.**
  `tests/test_recheck_dispatch_sites_docs.py` gets a probe asserting that, in
  the rework section 10 Return-time digest paragraph, the "return-time
  recheck" token comes after step 3's validation token and before the first
  mention of the patch application (rule 15's write / rule 16's commits). The
  probe has a forged-text control. The control is the text as it stands at
  this feature's base, where the recheck follows "Step 3 validates and
  applies", and the probe must fire on it. The pre-change sentence set that
  the `REWORK_SITE` checks keep is updated to match the reworded paragraph,
  and the existing "missing" forged control still fires.

### Non-Functional Requirements

- **NFR1 - Test conventions:** Tests use only the Python standard library and
  follow test/README.md naming (`test_<target>.py`,
  `Test<Behavior>(unittest.TestCase)`, `test_<condition>_<expected_result>`).
- **NFR2 - Probe style:** Probes slice by heading/paragraph and compare
  whitespace-insensitive token positions. They never compare a whole document
  or depend on where a line breaks, which is the existing convention of
  `tests/test_recheck_dispatch_sites_docs.py`.
- **NFR3 - Existing suites:** The existing suites
  (`tests/test_recheck_dispatch_sites_docs.py` for the design step 5 and
  create-plan section 8 sites, `tests/test_return_time_recheck_docs.py`) keep
  passing unchanged, except for the `REWORK_SITE` pre-change/order data FR4
  names.
- **NFR4 - Plugin version:** The plugin version is not changed.

## Acceptance Criteria

- [ ] AC-1 (FR1): In the rework section 10 Return-time digest paragraph, the
  first position of "return-time recheck" comes after the step 3 validation
  wording and after the rule-1 compare/stale sentence, and before the first
  mention of the patch application (rule 15 write / rule 16 commit).
- [ ] AC-2 (FR1): The paragraph states that the patch is applied only after a
  passing recheck, so a stale recheck reaches no workflow.yaml write or commit
  from the patch.
- [ ] AC-3 (FR2): The `REWORK_SITE` checks that already exist (citation,
  actor, stale wording, no restatement, recheck before the `self_write_set` /
  Layer 5 recording sentence) pass on the reworded paragraph.
- [ ] AC-4 (FR3): Section 10's numbered steps 1-4 are still present with
  unchanged numbers. The citations in `review-phase.md` and develop `SKILL.md`
  still resolve to the same steps.
- [ ] AC-5 (FR4, NFR1, NFR2): The new order probe passes on the real document
  and fires on the forged control (the base-revision paragraph, with the
  recheck after "validates and applies"). `python3 -m unittest discover -s
  tests` passes.

## Implementation Approach

### Changed Documents

- `em-workflow/references/rework-task-synthesis.md` section 10, the
  "Return-time digest (steps 2 and 3, all four routes)" paragraph (FR1, FR2,
  FR3).
- `tests/test_recheck_dispatch_sites_docs.py` (FR4).

### Order in Section 10, Step 3

```
step 3 validation (workflow-patch.md rules 1-14, incl. rule 1 compare)
  -> return-time recheck (mismatch / cannot run -> stale)
  -> step 3 application (rule 15 single Write to workflow.yaml, rule 16 R2 commits)
```

The recheck also precedes the phase-state write that records
`self_write_set` with the Layer 5 recording of `written_artifacts` into
`phase-state/rework.yaml` (FR2).

### Unchanged Documents (Assumptions)

- `create-plan-phase.md` does not have the same ordering defect. Section 8
  runs `validate-worker-output.py` with `--dry-run-apply` (no write), then the
  return-time recheck, then the recording write. The patch is written and
  committed only in section 10 (Atomic patch application: rule 15 Write, rule
  16/R2 commits), which follows section 8. So `create-plan-phase.md` is not
  changed.
- The design-step site (develop `SKILL.md`, design step branch, step 5)
  already runs the recheck before its recording write and before the
  workflow.yaml status write / `commit-docs.sh` commit. It is not changed.
- `references/workflow-patch.md` application rules 1-18 are not changed. Rule
  15's "After all validations succeed" stays generic. The recheck placement is
  stated at the rework dispatch site (`rework-task-synthesis.md` section 10),
  the same way create-plan states its placement in its own phase document.
- `references/contracts/worker-envelope.md` Rule R1 ("Order", "Known limit",
  the Exclusivity interval) is not changed. R1 requires only that the recheck
  precede the recording phase-state write, and the fix keeps that.
- The relative order of the recording phase-state write (`self_write_set` +
  Layer 5 recording) and the patch write is not redefined beyond R1's
  requirement. Both follow a passing recheck.
- `review-phase.md` (line ~1180 "THEN validates and applies rework-planner's
  patch") and develop `SKILL.md` (lines ~860/870 "検証・適用") summarize
  section 10 by citation. They state no recheck position, so they do not
  conflict with the fix and are not changed.
- After a stale recheck, the stale handling of `create-spec-phase.md` "Scope
  verification" (discard output, reset --hard to the integration ref,
  recompute, re-dispatch) is unchanged. The fix only ensures that no patch
  write or commit exists for it to leave behind. Orchestrator writes made
  before dispatch (step 1's `review.needs_rework` / `review.status`) are out
  of scope.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/rework-recheck-before-patch-write/**`
- `test-docs/rework-recheck-before-patch-write/**`

`feature-docs/rework-recheck-before-patch-write/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rework-recheck-before-patch-write/**` covers
`test-docs/rework-recheck-before-patch-write/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rework-recheck-before-patch-write/` directory at all; the declared
`test-docs/rework-recheck-before-patch-write/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1 (FR1, FR4, NFR1, NFR2; AC-1, AC-2, AC-5): The order probe on the
  real rework section 10 paragraph finds validation, then the recheck, then
  the application, and passes.
- [ ] TS-2 (FR4, NFR1, NFR2; AC-5): The forged control (the current base
  paragraph, with the recheck after the "validates and applies" sentence)
  makes the order probe fire.
- [ ] TS-3 (FR2, NFR3; AC-3): The full suite (`python3 -m unittest discover
  -s tests`) passes, including the unchanged design-step-5 and
  create-plan-section-8 site checks and
  `tests/test_return_time_recheck_docs.py`.
- [ ] TS-4 (FR3; AC-4): A probe confirms that section 10's numbered steps 1-4
  still exist (optional; may be folded into TS-1).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass

## Open Questions

None.

## References

- Rework section 10: `em-workflow/references/rework-task-synthesis.md`
- Workflow patch application rules: `em-workflow/references/workflow-patch.md`
- Rule R1: `em-workflow/references/contracts/worker-envelope.md`
- Regression tests: `tests/test_recheck_dispatch_sites_docs.py`,
  `tests/test_return_time_recheck_docs.py`
