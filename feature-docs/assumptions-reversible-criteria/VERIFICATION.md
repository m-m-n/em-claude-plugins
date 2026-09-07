# Verification Document: assumptions-reversible-criteria

## Overview

**Feature**: assumptions-reversible-criteria
**SPEC.md**: `feature-docs/assumptions-reversible-criteria/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/assumptions-reversible-criteria/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature. Per-task
acceptance criteria live in `tasks/task0001.md`, `tasks/task0002.md` and
`tasks/task0003.md`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the change
  surface is Markdown, JSON and Python test modules, and the repository has no
  build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures, no errors, no skipped test that was
  previously running.
- Coverage target: not measured. The repository configures no coverage tool;
  coverage of this feature is expressed as the per-scenario assertions below,
  each of which must be present and non-vacuous.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The `assumptions[].reversible` row of `em-workflow/references/question-packet-schema.md` contains the irreversible-operation half and the preserved-constraint half of the criterion | Both halves present on the row | Unit |
| TS-2 | Each of `em-workflow/agents/requirements-analyst.md`, `implementation-planner.md`, `rework-planner.md` carries the criterion, asserted once per file | Three independent assertions pass; removing the criterion from one file fails that file's assertion alone | Unit |
| TS-3 | Each of `em-workflow/references/contracts/analyst-contract.md`, `planner-contract.md`, `rework-planner-contract.md` carries the criterion, asserted once per file | Three independent assertions pass | Unit |
| TS-4 | `em-workflow/references/question-resolution.md` still carries the four abort arms, the Precedence reservation, the surviving-abort enumeration, the batch relaxation, the Classification gate's direction-2 irreversibility check and the worker-declared-basis paragraph | All present; the file is unmodified by the feature | Unit |
| TS-5 | Negative proof: each criterion matcher rejects forged document text with the criterion removed, and its non-vacuity companion shows it accepts forged text containing it | Rejection and acceptance both asserted for every matcher | Unit |
| TS-6 | The new counter-example fixture parses, declares `reversible: true` on a test-pinned constraint assumption, and `scripts/validate-worker-output.py` accepts it directly and under the fixture sweep; the pre-existing irreversible fixture still declares `reversible: false` and is still accepted | Validator exits 0 in both invocations; both fixtures accepted | Integration |
| TS-7 | Version-bump module: both registries report a version past the 0.1.64 baseline and equal to each other, the em-review entry stays 0.5.7, each matcher carries a negative proof | All assertions pass with non-vacuity companions | Unit |
| TS-8 | No `gate_id` new to this feature appears in any changed plugin document, `em-workflow/references/batch-policies.yaml` is unchanged, and the new test modules import only the standard library | Gate-id set does not grow; batch-policies.yaml untouched; import check passes | Unit |

## Code Quality Verification

- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Supplementary invariant check (cited by SPEC NFR2): run the repository's
  plugin-invariant script, `scripts/check-plugin-invariants.py`, if present at
  that path, and expect exit code 0 — its gate-id coverage check must still be
  satisfied. Its absence at that path is not a verification failure; the
  property is also covered by TS-8.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The schema row states both halves of the criterion | TS-1 |
| AC-2 | Each of the three agent prompts carries the criterion, per file | TS-2 |
| AC-3 | Each of the three worker contracts carries the criterion, per file | TS-3 |
| AC-4 | The fail-closed arms and their non-overridable wording are byte-for-byte retained; the existing arm tests pass unmodified | TS-4 plus the full suite run, confirming `tests/test_question_resolution_doc.py`, `tests/test_classification_gate.py`, `tests/test_spec_change_origin_binding.py`, `tests/test_batch_stop_contract.py` and `tests/test_batch_policies.py` pass without edits |
| AC-5 | The new module fails when the criterion is removed from any one of the seven documents, and passes against the real tree | TS-5 (forged-content proofs) plus TS-1 / TS-2 / TS-3 against the tree |
| AC-6 | The new fixture declares a test-pinned preserved constraint as `reversible: true` and the validator exits 0 directly and in the sweep | TS-6 |
| AC-7 | Both registries report the same version, strictly greater than 0.1.64 at the patch component, major.minor unchanged, em-review left at 0.5.7 | TS-7 |
| AC-8 | `python3 -m unittest discover -s tests` passes | Test Verification section above |
| AC-9 | An assumption of the reported shape — a constraint preserved because a test pins it — classifies as `reversible: true` under the documented criterion and no longer names a question into the irreversibility arm | TS-6 as the worked instance, plus the manual reading below |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4, plus the unmodified pre-existing arm tests |
| FR5 | task0001 | TS-5 |
| FR6 | task0002 | TS-6 |
| FR7 | task0003 | TS-7 |
| NFR1 | task0001 | TS-1, TS-2, TS-3 (one definition site; six sites carrying the pointer), plus the manual citation-discipline reading below |
| NFR2 | task0001 | TS-8 |
| NFR3 | task0001, task0002 | TS-8 |
| NFR4 | task0001, task0002, task0003 | TS-5, TS-8 |
| NFR5 | task0001, task0002 | TS-4, TS-6 |
| NFR6 | task0001 | No automated test — manual reading below (coverage gap, recorded deliberately) |

## E2E Testing

Not applicable. The feature has no runtime surface and the project defines no
E2E command (`e2e_test_command` is empty, and no E2E input paths were resolved).

## Manual Testing (E2E Not Possible)

- [ ] **NFR6 minimality**: read the added text at all seven documents and
      confirm it states the criterion only — no justification narrative, no
      reference to the originating incident, no restatement of the resolution
      procedure owned by `em-workflow/references/question-resolution.md`.
- [ ] **NFR1 citation discipline**: confirm the six citing sites cite the owning
      schema document rather than presenting a second definition, and that the
      condensed forms agree with the definition site in meaning as well as in
      the pinned tokens.
- [ ] **AC-9 reproduction reading**: take the reported assumption shape — a
      constraint that survives because an existing test pins it — and confirm
      that applying the documented criterion yields `reversible: true`, so the
      fail-closed irreversibility arm is not reached for it. The criterion is a
      semantic judgement and is not machine-checkable; this reading is the check.
- [ ] **Do-not-touch set**: confirm the feature's diff contains no change to
      `em-workflow/references/question-resolution.md`,
      `em-workflow/references/batch-policies.yaml`,
      `em-workflow/scripts/validate-worker-output.py`, the existing
      `valid-irreversible-assumption-blocking` fixture, or any pre-existing test
      module.

## Performance / Security Verification

Not applicable. No runtime behaviour changes and no security surface is added or
changed; the `category: security` abort arm keeps its current behaviour, which
TS-4 pins.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1..TS-8) | 8 | 8 | 0 | 0 |
| Success criteria (AC-1..AC-9) | 9 | 8 | 0 | 1 (AC-9 reading) |
| Requirements (FR1..FR7, NFR1..NFR6) | 13 | 12 | 0 | 1 (NFR6) |
| Manual checks | 4 | 0 | 0 | 4 |
