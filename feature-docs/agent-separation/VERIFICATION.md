# Verification Document: em-workflow Agent Responsibility Separation

## Overview

**Feature**: agent-separation / **SPEC.md**: `feature-docs/agent-separation/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/agent-separation/IMPLEMENTATION.md`

Normative detailed specification: `feature-docs/agent-separation/design-input.md`. Its sections 8.1 through 8.9 are the acceptance conditions this document verifies.

## Build Verification

- Command: none (the project has no build step; `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: not tracked numerically. The coverage contract is structural instead — every acceptance criterion in every task plan maps to at least one test, and every branch in the fixture coverage table has at least one fixture.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run the validator over every fixture in `em-workflow/references/fixtures/` | Valid fixtures exit 0, invalid fixtures exit 1 | Unit |
| TS-2 | Feed answer objects violating each answer-mode consistency rule | Each is rejected with exit 1 | Unit |
| TS-3 | Run `--dry-run-apply` against stale anchors, duplicate patch identifiers, expected mismatch, `replace_all` after implementation started, and `append_rework` missing the mandatory preserve path | Each is rejected | Unit |
| TS-4 | Feed analyst results with a detection-mode payload containing full-mode keys, a missing `mode_echo`, a mismatched `mode_echo`, and a worker result without `--input-envelope` | First three exit 1, the last exits 2 | Unit |
| TS-5 | Validate phase-state fixtures for every resume status, plus one whose cache generation exceeds the current generation | Valid statuses pass, the inconsistent generation is rejected | Unit |
| TS-6 | Invoke the validator in an environment where PyYAML cannot be imported | Exit code 2 with a message naming PyYAML | Unit |
| TS-7 | Run the agent/dispatch parity and forbidden-heading checks over the integrated repository | Parity holds; no agent definition carries the task-assignment heading | Integration |
| TS-8 | Search the integrated repository for the removed agent name and the inline-execution phrase | No occurrence outside this feature's own documents | Integration |
| TS-9 | Compare the gate identifiers used by the phase protocols and the develop skill against the batch policy file | Sets agree in both directions, with the one documented exception excluded | Integration |
| TS-10 | Compare the domains vocabulary in the review rules registry against the plan-writing skill | The two agree exactly | Integration |
| TS-11 | Compute an input digest twice over an identical input mapping | The two values are identical | Unit |
| TS-12 | Run a small feature end to end interactively through every phase | All steps reach completed (design may be skipped); every workflow.yaml-changing commit originates from the orchestrator | E2E (manual) |
| TS-13 | Run the same feature under `--batch` | Completes with zero AskUserQuestion calls; the report lists each automatic answer's source and note | E2E (manual) |
| TS-14 | Trigger interactive rework from review findings | At least one pending rework task exists before implement returns to pending; the implement phase launches it; `base_commit` is unchanged | E2E (manual) |
| TS-15 | Trigger batch rework from review findings | Same outcome, decided from the policy table | E2E (manual) |
| TS-16 | Trigger interactive rework from verify failures | Same outcome via the verify branch | E2E (manual) |
| TS-17 | Trigger batch rework from verify failures | Same outcome, decided from the policy table | E2E (manual) |
| TS-18 | Interrupt create-spec mid-dialogue and resume | Answered questions are not re-presented; phase-state is committed on the integration branch | E2E (manual) |
| TS-19 | Interrupt create-plan during worker dispatch and resume | The phase resumes from phase-state per the resume table | E2E (manual) |
| TS-20 | Choose a specification change during rework | No tasks are created; create-spec returns to needs-update and the downstream steps return to pending | E2E (manual) |
| TS-21 | Dispatch spec-writer against an existing SPEC.md whose digest disagrees | The worker returns blocked | Integration (manual) |
| TS-22 | Encounter a digest-mismatched existing artifact under batch | The preserve-and-reuse branch continues when post-conditions hold and aborts when they do not | Integration (manual) |
| TS-23 | Advance the integration branch from another process during worker dispatch | The change set is computed before the HEAD evaluation, violations are removed, the worktree is refreshed, and the concurrent merge is not reported as a violation | Integration (manual) |
| TS-24 | Enter a phase with a dirty integration worktree | The phase aborts before dispatch listing the offending paths, and nothing is cleaned automatically | Integration (manual) |
| TS-25 | Enter the design step with no design system recorded but tokens present, and separately with the source token file missing but its generated sheet present | The first runs the reclassification gate and resumes from the same step; the second aborts before dispatch | Integration (manual) |
| TS-26 | Exceed the discovery cap during design-system candidate resolution | Interactive asks for manual specification; batch aborts | Integration (manual) |
| TS-27 | Enter design or create-plan with a workflow file lacking the design-system field | Backfill runs before the step is set to in-progress, and step selection restarts afterwards | Integration (manual) |
| TS-28 | Receive two consecutive stale-tip responses when committing worker artifacts | The first records the discard and increments the counter in one commit before re-dispatch; the second sets the phase to failed | Integration (manual) |
| TS-29 | Report a written artifact reached through a symlinked path segment leading outside the project root | Detected as a scope violation | Unit |
| TS-30 | Encounter an untracked scope violator with no trash tool available | Nothing is deleted or moved; the phase aborts listing the paths | Integration (manual) |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured. Quality is enforced by the review phase and by the invariant script below.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | Every functional requirement is implemented | Requirements coverage table below shows a task and a test for each |
| SC-2 | All automated test scenarios pass | `python3 -m unittest discover -s tests` exits 0 |
| SC-3 | The repository invariants hold | `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0 |
| SC-4 | Security requirements are satisfied | TS-23, TS-29, TS-30 plus the review phase's security perspective |
| SC-5 | Documentation is complete | `README.md`, `test/README.md` and the plugin description reviewed against NFR5 and FR29 |
| SC-6 | Acceptance conditions 8.1–8.9 of design-input.md are met | Walk each condition against the evidence in this document |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0004 | TS-14, TS-15, TS-16, TS-17 |
| FR2 | task0004 | TS-14, TS-16 |
| FR3 | task0001 | TS-1 |
| FR4 | task0006 | TS-4 |
| FR5 | task0006 | TS-21 |
| FR6 | task0007 | TS-1 |
| FR7 | task0007 | TS-20 |
| FR8 | task0007 | TS-25 |
| FR9 | task0008 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR10 | task0008 | TS-1 |
| FR11 | task0008 | TS-1 |
| FR12 | task0002 | TS-3 |
| FR13 | task0003 | TS-5, TS-28 |
| FR14 | task0001 | TS-2 |
| FR15 | task0005 | TS-13 |
| FR16 | task0005 | TS-9, TS-13, TS-15, TS-17, TS-22 |
| FR17 | task0010, task0012 | TS-12, TS-25 |
| FR18 | task0010 | TS-12 |
| FR19 | task0011 | TS-19 |
| FR20 | task0009 | TS-12 |
| FR21 | task0009 | TS-12, TS-21 |
| FR22 | task0011 | TS-18 |
| FR23 | task0009 | TS-14, TS-20 |
| FR24 | task0005 | TS-13 |
| FR25 | task0013 | TS-7, TS-8 |
| FR26 | task0004, task0013 | TS-8, TS-10 |
| FR27 | task0012 | TS-12, TS-16, TS-27 |
| FR28 | task0013 | TS-7, TS-8 |
| FR29 | task0013 | TS-8 |
| FR30 | task0014 | TS-7, TS-8, TS-9, TS-10, TS-11 |
| FR31 | task0011 | TS-23, TS-24, TS-29, TS-30 |
| FR32 | task0003, task0012 | TS-26, TS-27 |
| NFR1 | task0002, task0010, task0013 | TS-12 |
| NFR2 | task0011 | TS-18 |
| NFR3 | task0003, task0011 | TS-18, TS-19 |
| NFR4 | task0005 | TS-13, TS-22 |
| NFR5 | task0008, task0013 | TS-6, TS-30 |
| NFR6 | task0013, task0014 | TS-10 |
| NFR7 | task0009, task0014 | TS-7 |
| NFR8 | task0008, task0011 | TS-23, TS-29 |
| NFR9 | task0003, task0011 | TS-26 |

## E2E Testing

No E2E framework exists in this project, and the product is a set of prompts and protocols rather than an application. The end-to-end scenarios TS-12 through TS-20 are executed by running the plugin itself against a throwaway feature, and are therefore recorded under manual testing below.

## Manual Testing (E2E Not Possible)

Run these against a scratch repository with the integration branch's plugin content installed, never against the main working tree of this repository (design-input.md 10.1: the plugin does not operate until the whole change lands).

- [ ] TS-12: interactive full run of a one-to-two-task feature
- [ ] TS-13: batch full run of the same feature
- [ ] TS-14 / TS-15: interactive and batch review rework
- [ ] TS-16 / TS-17: interactive and batch verify rework
- [ ] TS-18 / TS-19: interruption and resume in create-spec and create-plan
- [ ] TS-20: specification change chosen during rework
- [ ] TS-21 / TS-22: digest-mismatched artifact, interactive and batch
- [ ] TS-23 / TS-24: concurrent branch advance, and dirty worktree entry
- [ ] TS-25 / TS-26 / TS-27: design-system inconsistency, discovery cap, and backfill
- [ ] TS-28: consecutive stale-tip artifact commits
- [ ] TS-30: missing trash tool

Before and after each run, capture `git log --name-status` and a workflow.yaml snapshot, then confirm: every workflow.yaml-changing commit originates from the orchestrator; phase-state is actually committed; `base_commit` is unchanged across rework; the completion commit's recorded revision is its parent; and any worker scope violation was detected and reported.

## Security Verification

- NFR8 path rules: covered by TS-29 and by the unit tests of the scope-verification helpers.
- NFR4 fail-closed batch: covered by TS-13 and TS-22, plus a reading of `references/question-resolution.md` confirming the four abort categories.
- Codex output treated as untrusted: confirmed by reading the unlisted-gate fallback section.
- Secret scanning is unchanged; the existing pre-commit gate continues to apply to every documentation commit.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 30 | 11 | 9 | 10 |
| Success criteria | 6 | 2 | 0 | 4 |
| Requirements | 41 | 41 mapped | — | — |
