# Verification Document: implement-failed-kind

## Overview

**Feature**: implement-failed-kind /
**SPEC.md**: `feature-docs/implement-failed-kind/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/implement-failed-kind/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature.
Per-task acceptance criteria live in `feature-docs/implement-failed-kind/tasks/`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty —
  the deliverables are Markdown protocol documents, two JSON registries and
  Python test modules, none of which has a build step.
- Expected: not applicable; this section is satisfied by the Test
  Verification below.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0.
- Coverage target: line/branch coverage tooling is not configured for this
  project and none is introduced by this feature. The applicable target is
  assertion coverage: every task acceptance criterion maps to at least one
  assertion, and every matcher carries a negative proof.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Start `--batch --once` on a workflow.yaml whose `implement` step is `failed` with the external-cause `failed_kind`, below the resume cap | The run does not stop at stop condition 3; `implement` is reset to `pending`, `failed_kind` is cleared and the resume count is incremented in one write set; that write set is committed before the phase runs; the implement phase then executes | Manual |
| TS-2 | Start `--batch --once` on a workflow.yaml whose `implement` step is `failed` with the decision-required `failed_kind` | The run stops at stop condition 3 and emits the terminal line `EM_WORKFLOW_TERMINAL: state=stopped step=implement reason=step_needs_intervention ...` | Manual |
| TS-3 | Start `--batch --once` on a workflow.yaml whose `implement` step is `failed` and carries no `failed_kind` key | Identical stopping behaviour and terminal line to TS-2 (the missing value reads as decision-required) | Manual |
| TS-4 | Start `--batch --once` on a workflow.yaml whose `implement` step is `failed` with the external-cause `failed_kind` and whose resume count has already reached the cap | The run stops as in TS-2, with the report naming the cap as the reason, and no workflow.yaml write is made | Manual |
| TS-5 | Run the project test command over the whole suite | Exit code 0 | Unit |
| TS-6 | Assert the schema document's `failed_kind` section and the `batch` auto-resume record: vocabulary, single ownership, required-ness, lifecycle, missing-value rule, key names and unset-read defaults | `tests/test_failed_kind_schema.py` passes, including its negative proofs | Unit |
| TS-7 | Assert the implement phase's three terminal write paths carry `failed_kind` with the pinned classification, that the route-back write set clears it, and that each path's single-write / single-commit statement survives | `tests/test_failed_kind_write_paths.py` passes, including its negative proofs | Unit |
| TS-8 | Assert the develop skill's stop-condition-3 branch, the auto-resume write set and its commit ordering, the cap and its at-cap no-write behaviour, the batch-only scope, and the two unchanged neighbouring carve-outs | `tests/test_failed_kind_stop_condition.py` passes, including its negative proofs | Unit |
| TS-9 | Assert the batch-mode and terminal-line documents' updated rows, and that the eleven stop reason codes and the `stop-condition-3` mapping are unchanged | `tests/test_failed_kind_batch_docs.py` passes, including its negative proofs | Unit |
| TS-10 | Assert plugin version parity across both registries, the past-baseline comparison, and the untouched sibling entry | `tests/test_failed_kind_version_bump.py` passes, including its negative proofs | Unit |
| TS-11 | Assert the auto-resume re-entry contract across the three documents that describe it: the implement phase's precondition recognises the auto-resume entry route and its own satisfying condition, the rework invariant is scoped to rework-derived transitions, the develop skill states why its write set touches no task state, the route-back clear's reason is accurate, and the develop-skill module's section extraction is anchored on the block's own heading | `tests/test_failed_kind_resume_reentry.py` and the repaired `tests/test_failed_kind_stop_condition.py` pass, including the anchor's exclusion guard and each matcher's negative proof | Unit |
| TS-12 | Start `--batch --once` on a workflow.yaml whose `implement` step is `failed` with the external-cause `failed_kind`, below the resume cap, where every task is `merged` except one that is `failed` — the state the auto-resume actually leaves behind | The resumed implement phase does not abort on its re-entry precondition; it reconciles the failed task and reaches its failure-handling branch, and the run neither repeats the same report nor ends at the stuck-step stop with the resume round already spent | Manual |
| TS-13 | Assert the `batch.infra_resume` record's cross-document consistency: the two documents' `batch` snippet key sets are equal, the block's persisted content is described to include the auto-resume record, the cap's ownership is cited per part, the record's materialising write path is named, and the external-cause gloss separates meaning from detection while leaving the vocabulary, required-ness and missing-value rules intact | `tests/test_failed_kind_batch_docs.py` and `tests/test_failed_kind_schema.py` pass, including their negative proofs | Unit |

TS-11 through TS-13 were added by the round-1 rework (task0006, task0007).

TS-1 through TS-4 are SPEC.md's own integration scenarios. They exercise an
LLM-driven orchestrator loop rather than a callable unit, and the project
declares no E2E framework, so they are executed as manual scenarios (see
Manual Testing below). TS-6 through TS-10 are the automated
document-contract counterparts that make the same statements checkable on
every suite run.

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; no
  formatter is configured for this repository.
- Static analysis: none configured. The equivalent guard for this feature is
  the document-invariant test suite above, plus the standard-library-only
  import assertion each new test module carries.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The schema document defines `failed_kind` with its two values and their meanings, in one place | TS-6 |
| AC2 | All three write paths that set `implement` to `failed` write `failed_kind`, with the value each path writes pinned by IMPLEMENTATION.md D2: orphan-origin is the external-cause value on the interactive abort entrance, while the batch second-failure entrance and the route-back gate-rejected terminal write the decision-required value unconditionally (the adopted resolutions of FR4 and FR5, recorded in workflow.yaml's `requirements` block; SPEC.md's AC2 sentence predates those resolutions and states the pre-resolution blanket rule) | TS-7 |
| AC3 | Stop condition 3 fires for the `implement` step's `failed` only on the decision-required value | TS-2, TS-8 |
| AC4 | The external-cause branch resets `implement` to `pending` and commits that write before executing the phase | TS-1, TS-8 |
| AC5 | The auto-resume is capped, stops as decision-required at the cap, and the cap and count live in the `batch` section as defined by the schema document | TS-4, TS-6, TS-8 |
| AC6 | The terminal-line document, the develop skill's stop condition 3 and the batch-mode document are updated | TS-8, TS-9 |
| AC7 | A workflow.yaml with no `failed_kind` is treated as decision-required | TS-3, TS-6 |
| AC8 | Both registries carry the same, raised version | TS-10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0007 | TS-6, TS-13 |
| FR2 | task0001, task0002, task0003, task0006 | TS-6, TS-7, TS-8, TS-11 |
| FR3 | task0002 | TS-7 |
| FR4 | task0002 | TS-7 |
| FR5 | task0002 | TS-7 |
| FR6 | task0003, task0006 | TS-1, TS-2, TS-8, TS-11, TS-12 |
| FR7 | task0001, task0003, task0006, task0007 | TS-4, TS-6, TS-8, TS-11, TS-13 |
| FR8 | task0003 | TS-8 |
| FR9 | task0001 | TS-3, TS-6 |
| FR10 | task0004, task0007 | TS-9, TS-13 |
| NFR1 | task0001, task0002, task0003, task0004, task0006, task0007 | TS-6, TS-7, TS-8, TS-9, TS-11, TS-13 |
| NFR2 | task0002, task0003, task0006 | TS-1, TS-7, TS-8, TS-12 |
| NFR3 | task0005 | TS-10 |
| NFR4 | task0001, task0002, task0003, task0004, task0005, task0006, task0007 | TS-5 |

## E2E Testing

The project declares no E2E framework and no E2E run command
(`project.components.main.e2e_test_command` is empty; SPEC.md records
"Existing E2E tests: None"). No E2E automation is introduced by this
feature — the scenarios that would qualify drive an unattended Claude Code
run and are listed under Manual Testing instead.

## Manual Testing (E2E Not Possible)

Each scenario below is set up by placing a crafted `workflow.yaml` for a
throwaway feature and launching an unattended run against it. Record the
observed terminal line and the resulting `workflow.yaml` state for each.

- [ ] TS-1 (FR6, NFR2): external-cause `failed_kind`, resume count below the
      cap → confirm the run does not stop, that `implement` reads `pending`
      with `failed_kind` cleared and the count incremented by exactly one,
      that those three changes arrived in a single commit made before the
      phase ran, and that the implement phase then executed.
- [ ] TS-2 (FR6): decision-required `failed_kind` → confirm the run stops
      and the terminal line reports `state=stopped step=implement
      reason=step_needs_intervention`.
- [ ] TS-3 (FR9): no `failed_kind` key at all → confirm the behaviour is
      identical to TS-2, and that no migration write was made to the file.
- [ ] TS-4 (FR7): external-cause `failed_kind` with the resume count already
      at the cap → confirm the run stops as in TS-2, that the report names
      the cap as the reason, and that `workflow.yaml` was not written.
- [ ] Interactive counterpart of TS-1 (FR8): the same external-cause state
      run WITHOUT `--batch` → confirm it stops exactly as TS-2 does, since
      the auto-resume is batch-only.
- [ ] TS-12 (FR6, NFR2): external-cause `failed_kind` below the cap, with
      the task set in the state an abort actually leaves — one task `failed`,
      every other task `merged`, none `pending` → confirm the resumed
      implement phase does not abort on its re-entry precondition, that it
      reconciles the failed task and reaches its failure-handling branch,
      and that the run does not fall into a repeat of the same report ending
      at the stuck-step stop with the resume round already consumed.

No mockup comparison applies: the design step is `skipped` for this feature
and no visual artefact exists.

## Performance / Security Verification

- Not applicable as a measured threshold. The one safety-relevant property
  is the fail-closed direction of both defaults: an absent `failed_kind`
  and an absent auto-resume record resolve to the stopping behaviour and a
  finite cap respectively, never to unbounded continuation. TS-3, TS-4 and
  TS-6 verify this.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1..TS-13) | 13 | 8 | 0 | 5 |
| Success criteria (AC1..AC8) | 8 | 8 | 0 | 4 |
| Requirements (FR1..FR10, NFR1..NFR4) | 14 | 14 | 0 | 6 |

Manual and automated counts overlap by design: AC3, AC4, AC5 and AC7 each
have both an automated document-contract check and a manual behavioural
check, and the interactive counterpart of TS-1 is a manual-only check of
FR8 alongside its automated document check. TS-11 and TS-13 are the
round-1 rework's automated document-contract checks; TS-12 is its
manual behavioural counterpart, covering the task-state situation TS-1
leaves unspecified.
