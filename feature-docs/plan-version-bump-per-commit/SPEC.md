# Feature: plan-version-bump-per-commit

## Overview

Defines how create-plan and rework plans handle plugin versions so that they
never contradict plugin-version-guard's per-commit check. In a non-exempt
repository every commit that changes files under a plugin bumps that plugin's
version in the same commit; in an exempt repository plans never instruct a
version change. Requirements document: `feature-docs/plan-version-bump-per-commit/REQUIREMENTS.md`.

## Objectives

- Define version handling for create-plan / rework plans that does not contradict plugin-version-guard's per-commit check, so that implementer never receives instructions that conflict with the guard.
- In batch runs with multiple tasks touching the same plugin, prevent the implement phase from being interrupted by version-related `git commit` rejections.

## User Stories

### US1: Plan multiple tasks touching the same plugin in a non-exempt repository
As implementation-planner, I want rules that require a version bump on every commit that changes files under a plugin, so that implementer's commits are never rejected by plugin-version-guard.

**Acceptance Criteria:**
- [ ] AC1: When two or more tasks touching the same plugin are planned in a non-exempt repository, the plan instructs a version bump on every commit that changes files under the plugin and never instructs keeping the version unchanged (FR1, FR2)

### US2: Plan in an exempt repository
As implementation-planner, I want rules that forbid version-change instructions in an exempt repository.

**Acceptance Criteria:**
- [ ] AC2: A plan in an exempt repository does not instruct a version change (FR3)

### US3: Synthesize rework tasks
As rework-planner, I want the same version rules applied to the additional tasks I synthesize.

**Acceptance Criteria:**
- [ ] AC3: The rework-side documents reference that the same rules apply to rework-planner's additional tasks (FR4)

### US4: Receive exemption and plugin location as dispatch inputs
As implementation-planner / rework-planner, I want the orchestrator to resolve the exemption status and plugin locations at each dispatch and pass them as values.

**Acceptance Criteria:**
- [ ] AC4: The inputs of implementation-planner and rework-planner define the exemption status and plugin locations as values, those values are included in `input_digest`'s `value_inputs`, and the create-plan / rework dispatch procedures state that they are passed (FR5)

### US5: Resolve conflicts in a non-exempt repository
As implementer following worktree-task-workflow, I want version rules for adoption and re-implementation commits.

**Acceptance Criteria:**
- [ ] AC5: worktree-task-workflow's conflict protocol states the version rules for adoption commits and re-implementation commits in a non-exempt repository (FR6)

### US6: Detect regressions
**Acceptance Criteria:**
- [ ] AC6: Tests detecting the above exist under `tests/`, and `python3 -m unittest discover -s tests` passes (FR7, NFR3)

## Technical Requirements

### Functional Requirements
- **FR1:** Per-commit version bump rule for non-exempt repositories (status: assumed, A1). The plan-writing skill's planning rules state the following. In a non-exempt repository (no `.github/workflows/plugin-version-bump.yml` at the repository root), every commit that changes a file under a plugin (under a directory that has `.claude-plugin/plugin.json`) bumps the patch of that plugin's `plugin.json` version in the same commit. If the same-named plugin entry in `.claude-plugin/marketplace.json` has a version, it is set to the same value. If a task contains multiple such commits, the version advances on each commit. The bumped value is greater than the value at the immediately preceding HEAD (strictly greater by per-component numeric comparison).
- **FR2:** No plan instructions that contradict the guard (status: confirmed). Plans in a non-exempt repository (IMPLEMENTATION.md / task plans) contain no instruction that keeps the version unchanged on a commit that changes files under a plugin, such as "only the first task bumps the version" or "subsequent tasks / rework tasks do not bump the version". The `files` of a task that changes files under a plugin include that plugin's `plugin.json` and, if an entry with a version exists, `marketplace.json`.
- **FR3:** Handling in exempt repositories (status: confirmed). In an exempt repository (`.github/workflows/plugin-version-bump.yml` exists), the plan does not instruct tasks to change the version. Only when bumping minor / major does it state where to bump, without concrete values.
- **FR4:** Same rules applied to rework-planner (status: confirmed). The same version handling as FR1-FR3 applies to the additional tasks rework-planner synthesizes. `rework-planner.md`, `rework-planner-contract.md` and `rework-task-synthesis.md` reference the plan-writing rules and do not restate the rule text.
- **FR5:** Dispatch-time resolution of exemption status and plugin locations (status: assumed, A3). At each create-plan and rework dispatch, the orchestrator resolves whether the target worktree's repository is exempt (presence of `.github/workflows/plugin-version-bump.yml`) and the plugin locations (directories that have `.claude-plugin/plugin.json`, and `marketplace.json` entries that have a version), and passes them as values in implementation-planner's `planning_inputs` and in rework-planner's input. These values are included in both workers' `input_digest` `value_inputs`. The statement in `planner-contract.md` that the planner has no `value_inputs` is revised accordingly. The Planner dispatch in `create-plan-phase.md` and the rework dispatch procedure state that these values are passed.
- **FR6:** Version in the conflict protocol (status: assumed, A2). worktree-task-workflow skill's parent-side adoption protocol gains an exception for non-exempt repositories. When a parent-side adoption commit (`{task_id}: resolve via parent-side adoption`) changes files under a plugin, that commit's version is greater than both the parent-side value and the task-side HEAD value. A re-implementation commit (`{task_id}: re-implement on updated parent`) is greater than the HEAD value after adoption. The corresponding `marketplace.json` entry is set to the same value. In an exempt repository no additional step is performed.
- **FR7:** Regression tests (status: confirmed). Tests under `tests/` detect that the FR1-FR6 rules are stated in the relevant documents, and that no statement permits keeping the version unchanged in a non-exempt repository.

### Non-Functional Requirements
- **NFR1 - SSOT:** The rule text for version handling lives in the plan-writing skill (planning side) and the worktree-task-workflow skill (implementation side on conflict); contract / agent / phase documents reference it and do not restate it.
- **NFR2 - No code in plans:** Following plan-writing's No Concrete Code rule, the added rules stay at the level of behavior descriptions.
- **NFR3 - Test dependencies:** Tests use only Python standard library `unittest` and run with `python3 -m unittest discover -s tests`. They neither read nor write anything under the real `~/.claude`.
- **NFR4 - Version in this repository:** This repository is an exempt repository, so this feature's implementation tasks do not change the version in em-workflow's `plugin.json` / `marketplace.json`. SPEC, plans and acceptance criteria contain no concrete version values.

## Implementation Approach

### Architecture

Documentation and planning-rule change; no runtime components.

**Component Diagram:**
```
orchestrator
  ├─ create-plan dispatch ── planning_inputs (exemption, plugin locations) ──> implementation-planner ── follows ──> plan-writing skill (rule text, FR1-FR3)
  └─ rework dispatch ─────── input (exemption, plugin locations) ───────────> rework-planner ───────── references ─> plan-writing skill (FR4)
implementer ── on conflict ──> worktree-task-workflow skill (rule text, FR6)
tests/ ── checks ──> the documents above (FR7)
```

### Data Flow

```
orchestrator resolves exemption + plugin locations (per dispatch)
  → value passed to planner input, included in input_digest value_inputs
  → planner applies plan-writing version rules
  → plan / tasks (files include plugin.json / marketplace.json when non-exempt)
```

### API Design

N/A

### Database Schema

N/A

### Dependencies

**Internal Dependencies:**
- plan-writing skill: holds the planning-side rule text (FR1-FR3)
- worktree-task-workflow skill: holds the conflict-side rule text (FR6)
- `planner-contract.md`, `rework-planner-contract.md`: define the new input values and their inclusion in `value_inputs` (FR5)
- `create-plan-phase.md` and the rework dispatch procedure: pass the values (FR5)
- `rework-planner.md`, `rework-planner-contract.md`, `rework-task-synthesis.md`: reference the plan-writing rules (FR4)

**External Dependencies:**
- `~/.claude/hooks/plugin-version-guard.py`: not changed (A5)

### File Structure

Documents named in the requirements:

```
plan-writing SKILL.md
worktree-task-workflow SKILL.md
planner-contract.md
rework-planner-contract.md
rework-planner.md
rework-task-synthesis.md
create-plan-phase.md
rework dispatch procedure
tests/   # regression tests (FR7)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/plan-version-bump-per-commit/**`
- `test-docs/plan-version-bump-per-commit/**`

`feature-docs/plan-version-bump-per-commit/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/plan-version-bump-per-commit/**` covers `test-docs/plan-version-bump-per-commit/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/plan-version-bump-per-commit/` directory at all; the declared
`test-docs/plan-version-bump-per-commit/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1): plan-writing SKILL.md contains the per-commit version bump rule for non-exempt repositories (aligning `marketplace.json`, multiple bumps within one task, strictly greater value) - stated, and the test passes
- [ ] TS-2 (FR2): plan-writing SKILL.md contains the prohibition of keep-unchanged instructions and the rule that a task changing files under a plugin includes `plugin.json` / `marketplace.json` in its `files` - stated, and the test passes
- [ ] TS-3 (FR3): plan-writing SKILL.md contains the rule that exempt repositories get no version instructions, and the criterion (presence of `.github/workflows/plugin-version-bump.yml`) - stated, and the test passes
- [ ] TS-4 (FR4): `rework-planner.md` / `rework-planner-contract.md` / `rework-task-synthesis.md` reference the plan-writing version rules - referenced, and the test passes
- [ ] TS-5 (FR5): `planner-contract.md` and `rework-planner-contract.md` define the exemption / plugin-location inputs and their inclusion in `value_inputs`, and `create-plan-phase.md` and the rework dispatch procedure state that they are passed - stated, and the test passes
- [ ] TS-6 (FR6): worktree-task-workflow SKILL.md's conflict protocol contains the non-exempt rule that an adoption commit exceeds both the parent-side and task-side HEAD values, and a re-implementation commit exceeds the post-adoption HEAD value - stated, and the test passes

### Integration Tests
- [ ] TS-7 (FR7, NFR3): run `python3 -m unittest discover -s tests` - exit 0

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] Newly added plugins (no `plugin.json` at base) and marketplace entries without a version are outside the guard's scope and are not bumped or aligned (A7)
- [ ] When two tasks bump to the same value, merge-task.sh (which composes via commit-tree) merges them without conflict; the integration branch's version is still ahead of base, and no additional handling is required (A6)

### Performance Tests

N/A

## Security Considerations

N/A

## Error Handling

N/A

## Performance Optimization

N/A

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1-AC6 are satisfied

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None (no requirement has `status: tbd`).

## Assumptions

- A1: In a non-exempt repository, every commit that changes files under a plugin bumps the patch in the same commit (create-spec-q0001: per_commit_bump)
- A2: worktree-task-workflow's conflict protocol is also revised in this feature (create-spec-q0001: include_worktree_task_workflow)
- A3: The orchestrator resolves the exemption status and plugin locations at each dispatch and passes them as values in the planner input (create-spec-q0001: orchestrator_resolves_per_dispatch)
- A4: The suspended feature destructive-guard-heredoc-reset-hard (rewriting IMPLEMENTATION.md D3, resuming task0003) is out of scope for this feature (create-spec-q0001: out_of_scope)
- A5: `~/.claude/hooks/plugin-version-guard.py` itself is not changed. The guard rejects only value mismatches and does not verify increases, so the requirement to increase is defined on the planning-rule side
- A6: merge-task.sh composes via commit-tree, so when two tasks bump to the same value they merge without conflict. Even then the integration branch's version is ahead of base, and no additional handling is required
- A7: Newly added plugins (no `plugin.json` at base) and marketplace entries without a version are outside the guard's scope and are not bumped or aligned

## References

- Requirements document: `feature-docs/plan-version-bump-per-commit/REQUIREMENTS.md`
