# Feature: worker-self-write-digest

## Overview

When a worker returns, the orchestrator's Rule R1 `input_digest` recheck substitutes the dispatch-time digest for every path the worker legitimately wrote under its `write_policy` (the self-write set). Every other input is recomputed from current state, so real changes outside the permitted self-writes are still detected as stale. Requirements: `feature-docs/worker-self-write-digest/REQUIREMENTS.md`.

## Objectives

- When a worker returns, the Rule R1 `input_digest` recheck must not treat paths the worker itself legitimately wrote under its `write_policy` as stale input.
- Real changes made outside the worker's permitted self-writes during the dispatch window must still be detected as stale.

## User Stories

User stories are expressed as the acceptance criteria below.

**Acceptance Criteria:**
- [ ] AC1 (FR1, FR2, FR3, FR11): With an existing `design-system/tokens.yaml`, a designer dispatched with `extend_only` adds a key to `tokens.yaml` and regenerates `tokens.html`. The return-time recheck does not judge the result stale.
- [ ] AC2 (FR1, FR3, FR5, FR11): implementation-planner rewrites existing `IMPLEMENTATION.md` and `VERIFICATION.md` with `replace_own` and creates new files under `tasks/`. Neither the R1 recheck nor `validate-worker-output.py --dry-run-apply` reports stale.
- [ ] AC3 (FR1, FR5, FR11): rework-planner writes `IMPLEMENTATION.md` and `VERIFICATION.md` with `replace_own` and creates new files under `tasks/`. Neither the R1 recheck nor `--dry-run-apply` reports stale.
- [ ] AC4 (FR4, FR11): A change during the dispatch window to a `digest_inputs` path that no `write_policy` entry permits (for example `SPEC.md`) is still judged stale.
- [ ] AC5 (FR2): A path listed in `written_artifacts` that the orchestrator did not observe changing is not in the self-write set.
- [ ] AC6 (FR3): A modified existing file that is covered only by `allowed_write_roots` is not in the self-write set, so the result is judged stale or fails scope verification. The same holds for a modified `preserve` target and for a `regenerate` target whose `source` was not written.
- [ ] AC7 (FR1, FR3): A `create` target that was absent at dispatch and then written by the worker is substituted as an absent key, and the recomputed digest matches the dispatch-time digest.
- [ ] AC8 (FR6, FR7): After an interruption that follows a planner's self-writes, resuming does not report a false `input_digest` mismatch. A change to a self-written artifact after its digest was recorded is still detected by the recorded-artifact-digest check.
- [ ] AC9 (FR9): `worker-envelope.md` R1 states the conditional self-write rule. The designer, planner and rework-planner contracts cite it and list their overlapping paths.
- [ ] AC10 (FR11, NFR4): The new tests fail against the pre-fix behaviour, and the full test suite passes after the fix.

## Technical Requirements

### Functional Requirements
- **FR1:** Substitute dispatch-time digests for self-writes. When the orchestrator recomputes `input_digest` on a worker's return, it uses the dispatch-time `digest_inputs` value for every path in the self-write set. For a path that was absent at dispatch, the key stays absent. Every other `digest_inputs` path and `value_inputs` / `answers_digest` / `write_policy_digest` / `workflow_blob` are recomputed from current state as before. The aggregate digest comparison is kept.
- **FR2:** Self-write set identification. A path joins the self-write set only if (a) it is in the change set the orchestrator observed for the dispatch window (the layer 4 pre/post-dispatch comparison) and (b) that change is permitted by the action of the `write_policy` entry covering the path. The worker's `written_artifacts` alone never decides membership, and neither does a plain intersection of paths with `write_policy`.
- **FR3:** Per-action permission. `allowed_write_roots` only permits creating a file that was absent at dispatch and never permits modifying an existing file. A changed existing file under an `allowed_write_roots` directory that is not listed in `targets` is not a self-write. `preserve` targets are never self-writes. A `regenerate` target is a self-write only when its `source` is also a self-write in the same dispatch. A `create` target is a self-write only when the path was absent at dispatch.
- **FR4:** Non-self-write changes stay stale. A `digest_inputs` change outside the self-write set, and any change to `value_inputs` / `answers_digest` / `write_policy_digest` / `workflow_blob`, still produces a mismatch, and the result is treated as stale.
- **FR5:** Patch application rule 1. The `digest_source` used for `workflow-patch.md` application rule 1 and for `validate-worker-output.py --dry-run-apply` is built with the same self-write substitution as FR1, so legitimate planner and rework-planner self-writes do not reject their patches.
- **FR6:** Resume comparison. create-plan's resume comparison of the recomputed `input_digest` against phase-state's `last_input_digest` applies the same self-write substitution. The recorded-artifact-digest comparison on resume is kept, so a change to a self-written artifact after its digest was recorded is still detected.
- **FR7:** Persistence. The orchestrator persists the dispatch-time per-path `digest_inputs` map and, after return, the self-write set of the run in phase-state, so the FR1, FR5 and FR6 comparisons can be reproduced after an interruption. The schema location is decided against `references/phase-state.md`.
- **FR8:** Ordering. The return-time recomputation happens after the dispatch-window change set has been observed (layer 4 scope comparison), because FR2 depends on it.
- **FR9:** Envelope-generic rule. The rule is stated once in `worker-envelope.md` Rule R1 ("Recomputation and comparison timing") as a conditional rule. It applies to any envelope worker whose `digest_inputs` overlap its `write_policy`. `designer-contract.md`, `planner-contract.md` and `rework-planner-contract.md` cite it and name their overlapping paths: designer has `design-system/tokens.yaml` and `tokens.html`; implementation-planner has `IMPLEMENTATION.md`, `VERIFICATION.md`, `THREAT-MODEL.md` and `tasks/`; rework-planner has `IMPLEMENTATION.md`, `VERIFICATION.md` and `tasks/`.
- **FR10:** Script function. A function in a script under `em-workflow/scripts/` takes the dispatch-time `digest_source` with its per-path map, the current per-path digests, the observed change set and `write_policy`. It returns the self-write set and the substituted return-time `digest_source`. Hashing remains orchestrator-side (`references/artifact-digest.md` Calculation, R1 normalization). The orchestrator procedures at the dispatch sites call this function: the design-step branch in `skills/develop/SKILL.md`, `create-plan-phase.md`, and `rework-task-synthesis.md` section 10.
- **FR11:** Regression tests. unittest tests reproduce designer `extend_only`, implementation-planner re-plan and rework-planner self-writes as not stale, and reproduce non-self-write changes as stale, through the FR10 function.

### Non-Functional Requirements
- **NFR1 - Digest structure unchanged:** R1's normalization procedure and the structural keys of `digest_source` (`worker`, `mode`, `workflow_blob`, `digest_inputs`, `value_inputs`, `answers_digest`, `write_policy_digest`) are unchanged.
- **NFR2 - worker_digest_stance invariant:** `check-plugin-invariants.py` `worker_digest_stance` passes: `worker-envelope.md`'s "`written_artifacts` reporting" section keeps "The worker does not compute digests", and no contract cited by a Bash-less writing worker contains a worker-directed digest instruction. The new rule is phrased with the orchestrator as subject.
- **NFR3 - dispatch_digest_wiring invariant:** `check-plugin-invariants.py` `dispatch_digest_wiring` passes: each dispatch-site section registered in `artifact-digest.md` "Dispatch sites" still cites `references/artifact-digest.md` with its Covers names and does not contain `git hash-object`.
- **NFR4 - Full test suite:** `python3 -m unittest discover -s tests` passes in full.
- **NFR5 - Plugin version:** The plugin version is not changed.
- **NFR6 - Single statement of each rule:** Each rule is stated once and cited elsewhere by path and section; the contracts do not restate R1.

## Implementation Approach

### Architecture

**Component Diagram:**
```
worker-envelope.md Rule R1  <-- cited by -- designer-contract.md
  (conditional self-write rule)            planner-contract.md
                                           rework-planner-contract.md

self-write function in a script under em-workflow/scripts/ (FR10)
  ^ called by orchestrator procedures at the dispatch sites:
  |   skills/develop/SKILL.md (design-step branch)
  |   create-plan-phase.md
  |   rework-task-synthesis.md section 10
  ^ used for: R1 return-time recheck (FR1), workflow-patch.md rule 1 and
              validate-worker-output.py --dry-run-apply (FR5),
              create-plan resume comparison (FR6)

phase-state: dispatch-time per-path digest_inputs map + self-write set (FR7)
```

### Data Flow

```
dispatch:  orchestrator computes digest_source (per-path digest_inputs map)
           -> persists the map in phase-state (FR7)
return:    layer 4 scope comparison -> observed change set (FR8)
           -> self-write function(dispatch digest_source, current per-path
              digests, observed change set, write_policy) (FR10)
           -> self-write set (FR2, FR3) + substituted digest_source (FR1)
           -> persists the self-write set in phase-state (FR7)
           -> input_digest of substituted digest_source compared with the
              dispatch-time input_digest (FR1, FR4)
```

### API Design

Function in a script under `em-workflow/scripts/` (FR10):

- Inputs: the dispatch-time `digest_source` with its per-path map, the current per-path digests, the observed change set, `write_policy`.
- Outputs: the self-write set, the substituted return-time `digest_source`.
- Hashing is not performed by this function; it remains orchestrator-side (`references/artifact-digest.md` Calculation, R1 normalization).

### Database Schema

Not applicable. The phase-state persistence (FR7) location is decided against `references/phase-state.md`.

### Dependencies

**Internal Dependencies:**
- `references/contracts/worker-envelope.md`: Rule R1, "`written_artifacts` reporting", exclusivity assumption
- `references/artifact-digest.md`: Calculation, Dispatch sites
- `references/phase-state.md`: persistence schema (FR7)
- `workflow-patch.md`: application rule 1 (FR5)
- `validate-worker-output.py`: `--dry-run-apply` (FR5)
- `check-plugin-invariants.py`: `worker_digest_stance`, `dispatch_digest_wiring` (NFR2, NFR3)

**External Dependencies:**
- None.

### File Structure

Files named by the requirements:

- `worker-envelope.md` — R1 conditional self-write rule (FR9)
- `designer-contract.md`, `planner-contract.md`, `rework-planner-contract.md` — cite R1 and list overlapping paths (FR9)
- `workflow-patch.md` — application rule 1 (FR5)
- `validate-worker-output.py` — `--dry-run-apply` (FR5)
- `references/phase-state.md` — persistence location (FR7)
- a script under `em-workflow/scripts/` — the FR10 function
- `skills/develop/SKILL.md` (design-step branch), `create-plan-phase.md`, `rework-task-synthesis.md` section 10 — call the FR10 function (FR10); `create-plan-phase.md` also covers the resume comparison (FR6)
- `tests/` — unittest regression tests (FR11)

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/worker-self-write-digest/**`
- `test-docs/worker-self-write-digest/**`

`feature-docs/worker-self-write-digest/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/worker-self-write-digest/**` covers `test-docs/worker-self-write-digest/{T}.tests.yaml`, the
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
- [ ] TS-1 (AC1): Designer `extend_only`: `tokens.yaml` (key added) and `tokens.html` (regenerated) change; recomputed digest equals dispatch digest.
- [ ] TS-2 (AC2): Planner re-plan: `IMPLEMENTATION.md` / `VERIFICATION.md` `replace_own` plus a new `tasks/task000N.md`; R1 and `--dry-run-apply` pass.
- [ ] TS-3 (AC3): Rework-planner: `VERIFICATION.md` `replace_own` plus a new `tasks/` file; not stale.
- [ ] TS-4 (AC4): `SPEC.md` changes during the window alongside legitimate self-writes; the result is stale.
- [ ] TS-5 (AC5): `written_artifacts` lists `SPEC.md` but the observed change set excludes it; `SPEC.md` is not substituted.
- [ ] TS-6 (AC6): An existing `tasks/` file is modified under `allowed_write_roots` only; a `preserve` target is modified; `tokens.html` is changed without `tokens.yaml`. None of these is a self-write.
- [ ] TS-7 (AC7): A `create` target is absent at dispatch and present after; its key is omitted in the substituted `digest_source`.
- [ ] TS-8 (AC8): Resume after self-writes with the persisted map and self-write set: no false mismatch. Editing a recorded artifact afterwards is detected.
- [ ] TS-9 (AC9): Document assertions on `worker-envelope.md` R1 and the three contracts' citations and overlap lists.

### Integration Tests
- [ ] TS-10 (AC10, NFR2, NFR3, NFR4): `python3 -m unittest discover -s tests` passes, including `check-plugin-invariants` `worker_digest_stance` and `dispatch_digest_wiring`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-5: a path in `written_artifacts` that was not observed changing is not substituted.
- [ ] TS-6: `allowed_write_roots`-only modification of an existing file, a modified `preserve` target, and a `regenerate` target without its `source` written are not self-writes.
- [ ] TS-7: a `create` target absent at dispatch stays an absent key.

### Performance Tests
Not applicable.

## Security Considerations

Not applicable.

## Error Handling

- A `digest_inputs` change outside the self-write set, or any change to `value_inputs` / `answers_digest` / `write_policy_digest` / `workflow_blob`, produces a mismatch and the result is treated as stale (FR4).
- A modified existing file covered only by `allowed_write_roots` is judged stale or fails scope verification (AC6).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` passes in full (NFR4)
- [ ] The plugin version is not changed (NFR5)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## Assumptions

- **A1** (impact: high, reversible, mechanism.self-write; answer source: batch-codex-consultation): Mechanism: substitute dispatch-time digests for self-written paths. This keeps the aggregate comparison, and `exclude_write_targets` would lose re-plan drift detection.
- **A2** (impact: medium, reversible, testing.regression-form; answer source: batch-codex-consultation): Regression detection is a script function wired into the real call path, with unittest coverage.
- **A3** (impact: medium, reversible, scope.resume-reconcile; answer source: batch-codex-consultation): The resume comparison is in scope, and the recorded-artifact-digest check is kept.
- **A4** (impact: medium, reversible, scope.workers; answer source: batch-codex-consultation): The rule is stated once in `worker-envelope.md` R1 as a conditional rule for any envelope worker, and the three contracts cite it.
- **A5** (impact: low, reversible, scope.task-md; answer source: batch-codex-consultation): TASK.md is out of scope because it is not in the planner's `digest_inputs`. Adding it would be a separate change.
- **A6** (impact: medium, reversible, mechanism.self-write; source: Codex consultation note, `worker-envelope.md` exclusivity assumption): Known limit: when the worker and an external actor change the same permitted path, the orchestrator cannot tell the changes apart. This case relies on the dispatch exclusivity assumption (design-input.md 5.11.3), which is not lock-enforced.
- **A7** (impact: medium, reversible; source: `tests/test_worker_contract_docs.py` and `check-plugin-invariants.py` `digest_reproducibility` pin them): R1's normalization procedure and the `digest_source` structural keys are unchanged.
- **A8** (impact: medium, reversible; source: `worker-envelope.md` "`written_artifacts` reporting", `check-plugin-invariants` `worker_digest_stance`): Hashing stays orchestrator-side, and workers never compute digests.
- **A9** (impact: low, reversible; source: `.claude/rules/core-plugin-version-bump.md`): The plugin version is not changed.

## References

- Requirements: `feature-docs/worker-self-write-digest/REQUIREMENTS.md`
- Rule R1: `references/contracts/worker-envelope.md`
- Artifact digest: `references/artifact-digest.md`
- Phase state: `references/phase-state.md`
- Workflow patch: `workflow-patch.md`
