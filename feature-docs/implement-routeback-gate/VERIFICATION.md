# Verification Document: implement-routeback-gate

## Overview

**Feature**: implement-routeback-gate /
**SPEC.md**: `feature-docs/implement-routeback-gate/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/implement-routeback-gate/IMPLEMENTATION.md`

This document describes the INTEGRATED verification of the feature, run after
every task has merged into the integration branch. Task-level acceptance
criteria live in `feature-docs/implement-routeback-gate/tasks/`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty
  (markdown + Python standard library; nothing is compiled).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: not defined by the project (no coverage tooling
  configured). Coverage is expressed as requirement coverage in the
  Functional Requirements Coverage table below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Parse the `### I.2.c: Failed handling` section and inspect the route-back bullet | The bullet states the failed task's `pending` reset together with the `tasks.{T}.notes` preservation clause | Unit (document contract) |
| TS-2 | Inspect the I.2.c section for the route-back commit instruction | A `commit-docs.sh` call exists, positioned after the status-write instructions and before the end-of-phase report sentence | Unit (document contract) |
| TS-3 | Inspect the Branch & Worktree Model's exit-4 recovery bullet | Its call-site enumeration names I.2.c's route-back commit in addition to Step I.1 and Step I.2.b | Unit (document contract) |
| TS-4 | Inspect the I.2.c gate sentence | The gate reads as the absence of any `merged` task; the string "every existing task is still `pending`" is absent from the section | Unit (document contract) |
| TS-5 | Inspect the merged-task branch of I.2.c | It states `failed` retention and develop's stop condition 3; neither "rework" nor "`append`" appears in that branch | Unit (document contract) |
| TS-6 | Inspect the delegation sentence of I.2.c | It cites Step B's stop-condition-3 precedence clause; the "create-plan exemption owns that precedence" wording is gone | Unit (document contract) |
| TS-7 | Run `tests/test_review_implement_develop_lock_contracts.py` unchanged | Passes: the I.2.c heading anchor resolves, the wake-phase assertions hold, and implement-phase.md yields zero bare `git commit` / `git add -A` lines | Regression |
| TS-8 | Run `tests/test_develop_skill_rewiring.py` unchanged | Passes: develop SKILL.md and its carve-out assertions are undisturbed | Regression |
| TS-9 | Compare the batch-mode paragraph following I.2.c against its pre-change text | Byte-identical | Unit (document contract) |
| TS-10 | Read `em-workflow/.claude-plugin/plugin.json` | `version` reads `0.1.36`; the file is valid JSON with all other fields unchanged | Inspection (manual) |
| TS-11 | Read the edited prose of implement-phase.md | English narrative, existing bullet structure and backtick conventions retained, no justification added beyond the requirement | Inspection (manual) |
| TS-12 | List the integration branch's changed files against `base_branch` (name-only) | Only `em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, `feature-docs/implement-routeback-gate/**`, and the test module added by this feature appear | Inspection (manual) |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty.
- Static analysis: none configured. The document-contract assertions in
  `tests/` are the structural check for the protocol markdown.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Route-back bullet states the `pending` reset and the notes preservation | TS-1 |
| AC-2 | Route-back sequence ends with a `commit-docs.sh` commit, ordered before the phase ends, with unambiguous ordering against worktree/branch cleanup | TS-2 |
| AC-3 | Exit-4 recovery bullet names the I.2.c route-back commit | TS-3 |
| AC-4 | Gate expresses the absence of any `merged` task; old phrasing gone | TS-4 |
| AC-5 | Merged-task branch terminates at `failed` + develop stop condition 3, with no rework/`append` handoff | TS-5 |
| AC-6 | Delegation sentence names Step B's stop-condition-3 precedence clause | TS-6 |
| AC-7 | The change's name-only file list contains only the allowed set | TS-12 |
| AC-8 | Batch-mode paragraph byte-identical | TS-9 |
| AC-9 | `python3 -m unittest discover -s tests` passes, including both existing regression modules unchanged | TS-7, TS-8 (full suite run) |
| AC-10 | `plugin.json` reads `"version": "0.1.36"` | TS-10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-6 |
| FR7 | task0001, task0002 | TS-7, TS-8, TS-12 |
| FR8 | task0001 | TS-7, TS-9 |
| FR9 | task0002 | TS-8, TS-10, TS-12 |
| NFR1 | task0001, task0002 | TS-7, TS-8 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001, task0002 | TS-7, TS-12 |
| NFR4 | task0001 | TS-7, TS-11 |

## E2E Testing

Not applicable — `project.components.main.e2e_test_command` is empty and the
change has no executable surface.

## Manual Testing (E2E Not Possible)

- [ ] TS-10: `em-workflow/.claude-plugin/plugin.json` reads
      `"version": "0.1.36"` and is otherwise unchanged (no automated
      assertion by design — IMPLEMENTATION.md D3).
- [ ] TS-11: The edited prose in `em-workflow/references/implement-phase.md`
      matches the surrounding file's style (English narrative, bullet
      structure, backtick conventions) and adds no justification beyond the
      requirement.
- [ ] TS-12: The integration branch's name-only diff against `base_branch`
      contains only `em-workflow/references/implement-phase.md`,
      `em-workflow/.claude-plugin/plugin.json`,
      `feature-docs/implement-routeback-gate/**`, and the test module added
      by this feature. In particular `em-workflow/skills/develop/SKILL.md`,
      `em-workflow/references/rework-task-synthesis.md`,
      `em-workflow/references/workflow-patch.md`,
      `em-workflow/references/contracts/*`,
      `tests/test_review_implement_develop_lock_contracts.py`,
      `tests/test_develop_skill_rewiring.py` and the root
      `.claude-plugin/marketplace.json` do not appear.

## Performance / Security Verification

Not applicable — documentation-only change with no executable behaviour, no
input handling and no data surface (NFR3).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Document contract (I.2.c + exit-4) | 7 (TS-1…TS-6, TS-9) | 7 | 0 | 0 |
| Regression | 2 (TS-7, TS-8) | 2 | 0 | 0 |
| Inspection | 3 (TS-10, TS-11, TS-12) | 0 | 0 | 3 |
| **Total** | **12** | **9** | **0** | **3** |
