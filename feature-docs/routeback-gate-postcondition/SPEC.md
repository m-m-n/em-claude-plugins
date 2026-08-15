# Feature: routeback-gate-postcondition

## Overview

Bug fix in em-workflow's own protocol documentation. `implement-phase.md` Step
I.2.c's route-back gate does not enforce the postcondition it declares, and the
Branch & Worktree Model document's exit-4 recovery enumeration lists a case that
the gate makes unreachable. This change widens the gate's admissibility
condition, names a single terminal state for the rejected path, and removes the
unreachable exit-4 entry.

Requirements source: `feature-docs/routeback-gate-postcondition/REQUIREMENTS.md`.

## Objectives

- **OBJ1:** Make the route-back gate at `implement-phase.md` Step I.2.c enforce
  the postcondition it declares, so that whenever route back proceeds the
  admissibility precondition of `workflow-patch.md`'s `replace_all` operation
  (every existing task is `pending`) actually holds.
- **OBJ2:** Give the path where the gate rejects route back a single defined
  terminal state, so a run that cannot legally route back halts for human
  intervention instead of continuing with a partially applied route back.
- **OBJ3:** Keep the Branch & Worktree Model's exit-4 recovery enumeration
  truthful by removing the entry the widened gate makes unreachable and stating
  why it is unreachable.

## User Stories

### US1: Route back only from a state `replace_all` accepts
As the orchestrator running the implement phase, I want Step I.2.c to admit
route back only from a state that `replace_all` accepts, so that the patch's
admissibility precondition holds whenever route back proceeds.

**Acceptance Criteria:**
- [ ] AC1: Step I.2.c states the admissibility condition as "no task has status
      `merged` AND no task has status `in_progress`", and its write set still
      resets `failed` tasks to `pending`.

### US2: Halt instead of half-applying a route back
As the orchestrator running the implement phase, I want a run that cannot
legally route back to halt for human intervention, so that no partially applied
route back is left behind.

**Acceptance Criteria:**
- [ ] AC2: Step I.2.c states that when the condition is not met, `implement` is
      set to `failed` and the run stops on develop Step B stop condition 3.
- [ ] AC3: Step I.2.c places the gate decision before any `commit-docs.sh`
      invocation and before route-back cleanup, and says nothing is committed on
      the rejected path.

### US3: A truthful exit-4 recovery enumeration
As a reader of the Branch & Worktree Model document, I want its exit-4 recovery
enumeration to list only reachable cases, so that I do not plan recovery around
a case that cannot occur.

**Acceptance Criteria:**
- [ ] AC4: The Branch & Worktree Model document no longer lists the I.2.c
      route-back commit among its exit-4 recovery cases, and states the
      unreachability justification in its place.

### US4: A documentary change that keeps the suite green
As a maintainer of em-workflow, I want this fix to stay documentary and within
its declared file scope, so that frozen files stay frozen and the test suite
stays green.

**Acceptance Criteria:**
- [ ] AC5: No new checker, validator rule or script is introduced, and
      `scripts/validate-worker-output.py`, `references/workflow-patch.md` and
      `references/contracts/*` are byte-identical to their pre-change content.
- [ ] AC6: `em-workflow/.claude-plugin/plugin.json` reads version 0.1.37 and the
      root `.claude-plugin/marketplace.json` is unmodified.
- [ ] AC7: `python3 -m unittest discover -s tests` exits 0, including any
      reference-sweep style test that pins the edited prose.

## Technical Requirements

### Functional Requirements

- **FR1 — Widen the I.2.c route-back admissibility gate** (status: resolved):
  `implement-phase.md` Step I.2.c admits route back only when no task in
  `workflow.yaml` has status `merged` AND no task has status `in_progress`. The
  existing write set is unchanged: tasks with status `failed` are reset to
  `pending`. Together the widened condition and the unchanged write set establish
  the all-`pending` state that `workflow-patch.md`'s `replace_all` admissibility
  condition requires, without relabeling work that may still be live.
- **FR2 — Terminal state when the gate rejects route back** (status: resolved):
  When the widened gate's condition is not met, Step I.2.c sets the `implement`
  step to `failed` and the run stops on develop Step B stop condition 3 (a step
  whose status is `failed` / `needs_update` requires user intervention). No
  alternative recovery path, retry loop or degraded route back is offered.
- **FR3 — Gate decision precedes every side effect** (status: resolved): The
  Step I.2.c gate decision is taken strictly before any `commit-docs.sh`
  invocation and before any route-back cleanup begins, so the rejected path
  commits nothing and mutates nothing.
- **FR4 — Exit-4 recovery enumeration entry removed as unreachable**
  (status: resolved): The I.2.c route-back commit is removed from the Branch &
  Worktree Model document's exit-4 recovery enumeration, and that document states
  why it is unreachable: the widened gate lets route back proceed only when no
  `in_progress` task exists, no implementer of this feature can therefore be
  running, and implementers are the only callers of `merge-task.sh` against this
  integration branch. The drain claim is treated as authoritative.
- **FR5 — Documentary change only, no new mechanical checker**
  (status: resolved): The change is documentary. No new mechanical checker,
  validator rule or script is added. Existing tests that pin the edited prose are
  updated within the same change so that `python3 -m unittest discover -s tests`
  stays green.
- **FR6 — Version bump scope** (status: resolved):
  `em-workflow/.claude-plugin/plugin.json` is bumped from 0.1.36 to 0.1.37. The
  root `.claude-plugin/marketplace.json` em-workflow entry carries no `version`
  field, so it is not edited and nothing needs syncing there.

### Non-Functional Requirements

- **NFR1 — Frozen files stay frozen** (status: resolved):
  `scripts/validate-worker-output.py`, `references/workflow-patch.md` and the
  worker contracts under `references/contracts/` are not modified by this change.
  The fix lives in the phase and model prose plus the plugin version file.
- **NFR2 — Independent safety net restored** (status: resolved): Route-back
  admissibility is decided from `workflow.yaml` task statuses alone, so the gate
  is an independent check rather than a restatement of an assumption that an
  earlier drain step behaved correctly. A stale or unretired `in_progress` entry
  is caught by the gate itself.
- **NFR3 — Test suite stays green** (status: resolved):
  `python3 -m unittest discover -s tests` passes after the change, with no test
  skipped or deleted to achieve it.

## Implementation Approach

### Architecture

This is a documentary change to em-workflow's protocol documents. There is no
runtime component, no UI surface and no data model; the design step was skipped
for that reason (ASM6).

**Decision structure at Step I.2.c:**

```
Step I.2.c reached
  |
  +-- read workflow.yaml task statuses            <- no side effect yet (FR3)
  |
  +-- gate: no task `merged` AND no task `in_progress` ?   (FR1)
        |
        +-- yes -> reset `failed` tasks to `pending`  (write set unchanged)
        |           -> all existing tasks are `pending`
        |           -> `replace_all` admissibility holds  (OBJ1)
        |
        +-- no  -> set `implement` step to `failed`   (FR2)
                   -> run stops on develop Step B stop condition 3
                   -> nothing committed, no cleanup started  (FR3)
```

### Data Flow

```
workflow.yaml task statuses -> Step I.2.c gate -> admit  -> failed->pending write set
                                              -> reject -> implement: failed -> halt
```

### Dependencies

**Internal Dependencies:**
- `references/workflow-patch.md`: owns the `replace_all` admissibility condition
  (every existing task is `pending`) that FR1 must establish. Read-only for this
  change (NFR1).
- develop Step B stop condition 3: the halt mechanism FR2 relies on.
- Branch & Worktree Model document: owns the exit-4 recovery enumeration edited
  by FR4.
- `merge-task.sh` / implementer call-site relationship: the basis of FR4's
  unreachability justification.

**External Dependencies:**
- None.

### File Structure

Files this change may touch:

```
em-workflow/
├── references/
│   ├── implement-phase.md            # Step I.2.c prose (FR1, FR2, FR3)
│   └── <branch & worktree model>.md  # exit-4 recovery enumeration (FR4)
├── .claude-plugin/
│   └── plugin.json                   # 0.1.36 -> 0.1.37 (FR6)
tests/                                # tests pinning the edited prose (FR5)
```

Files this change must not touch (NFR1, FR6):

```
em-workflow/scripts/validate-worker-output.py
em-workflow/references/workflow-patch.md
em-workflow/references/contracts/*
.claude-plugin/marketplace.json
```

## Test Scenarios

### Document Assertions
- [ ] **TS1** (covers AC1 / FR1): Read `implement-phase.md` Step I.2.c and
      confirm both status names (`merged`, `in_progress`) appear as conjunctive
      blockers of route back, and that `failed` -> `pending` remains in the write
      set.
- [ ] **TS5** (covers AC2 / FR2): Confirm Step I.2.c names exactly one
      rejected-path terminal — `implement: failed` plus develop Step B stop
      condition 3 — and offers no retry or degraded alternative.
- [ ] **TS7** (covers AC4 / FR4): Grep the Branch & Worktree Model document's
      exit-4 recovery section for the I.2.c route-back commit case: it is absent,
      and the unreachability justification (no `in_progress` task implies no
      running implementer implies no concurrent `merge-task.sh` caller) is
      present.

### Edge Cases
- [ ] **TS2** (covers AC1 / FR1): Reason over a `workflow.yaml` where some tasks
      are `failed` and none is `merged` or `in_progress`: the documented gate
      admits route back, and the write set turns the `failed` tasks into
      `pending`, satisfying `replace_all` admissibility.
- [ ] **TS3** (covers AC1 / FR1): Reason over a `workflow.yaml` with a stale
      `in_progress` task left by a crashed implementer: the documented gate
      rejects route back rather than admitting it on the strength of the drain
      step alone.
- [ ] **TS4** (covers AC1 / FR1): Reason over a `workflow.yaml` where every task
      is already `pending` (or there are no tasks): the gate admits route back
      and the write set is a no-op.
- [ ] **TS6** (covers AC3 / FR3): Trace the rejected path in the edited prose and
      confirm no `commit-docs.sh` call and no cleanup step can be reached after
      the gate rejects, i.e. the rejected run leaves the worktree and git history
      untouched.
- [ ] **TS8** (covers AC4 / FR4): Confirm the justification text ties
      unreachability to the widened gate rather than to the drain step in
      isolation, so the two documents do not disagree about which condition
      guarantees the exclusion.
- [ ] **TS11** (covers AC7 / FR5, NFR3): Confirm that every existing test
      asserting the old I.2.c or exit-4 wording was updated in the same change, so
      the suite does not go red on the edited sentences.

### Diff Scope
- [ ] **TS9** (covers AC5, AC6 / FR5, NFR1, FR6): Inspect the change's file list:
      it touches only the phase prose, the Branch & Worktree Model document, tests
      that pin the edited prose, and `em-workflow/.claude-plugin/plugin.json`. No
      frozen file and no `marketplace.json` entry appears.

### Commands
- [ ] **TS10** (covers AC7, AC5 / FR5, NFR3, NFR1): Run
      `python3 -m unittest discover -s tests` from the repository root and confirm
      exit 0 with no skipped or removed test.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Project Context

- Languages: Markdown, Python
- Test command: `python3 -m unittest discover -s tests`
- Build command: not applicable
- Format command: not applicable
- E2E command: not applicable
- License: none

## Design Step

**Status:** skipped

Resolved at gate `create-spec.design-step` with option `skip`: the change is
protocol-semantic prose plus a version bump, with no UI surface, no data model
and no design-system input, so the open decisions belong in SPEC.md rather than a
design document.

## Assumptions

Each assumption below was resolved upstream at the named gate and question.

- **ASM1** (gate `create-spec.requirement-clarification`, question
  `routeback.enforcement-mechanism`, option `widen-gate`, source
  `batch-codex-consultation`): Route-back admissibility is widened to "no
  `merged` AND no `in_progress`", with the write set unchanged, because
  `workflow-patch.md`'s `replace_all` admissibility requires every existing task
  to be `pending`, and this pairing reaches that state without relabeling
  possibly-live work.
- **ASM2** (gate `create-spec.requirement-clarification`, question
  `routeback.unmet-terminal-state`, option `blocked-halt`, source
  `batch-codex-consultation`): The rejected path sets `implement` to `failed` and
  halts on develop Step B stop condition 3, with the gate decision taken before
  any `commit-docs.sh` call and before route-back cleanup.
- **ASM3** (gate `create-spec.requirement-clarification`, question
  `routeback.exit4-recovery`, option `unreachable`, source
  `batch-codex-consultation`): The drain claim is authoritative; the I.2.c
  route-back commit is removed from the exit-4 recovery enumeration as
  unreachable, with the reason stated in the document.
- **ASM4** (gate `create-spec.requirement-clarification`, question
  `routeback.mechanical-enforcement`, option `prose-only`, source
  `batch-codex-consultation`): Enforcement stays documentary; no new mechanical
  checker is added and the acceptance bar is a green
  `python3 -m unittest discover -s tests`.
- **ASM5** (gate `create-spec.requirement-clarification`, question
  `routeback.version-bump-scope`, option `plugin-json-only`, source
  `batch-codex-consultation`): Only `em-workflow/.claude-plugin/plugin.json` is
  bumped (0.1.36 -> 0.1.37); the root `marketplace.json` em-workflow entry has no
  `version` field to sync (verified by the orchestrator).
- **ASM6** (gate `create-spec.design-step`, question
  `design-step.recommendation`, option `skip`, source `batch-decision-table`):
  The design step is skipped; the change has no UI surface, no data model and no
  design-system input.

## Success Criteria

- [ ] All functional requirements (FR1–FR6) are implemented
- [ ] All non-functional requirements (NFR1–NFR3) are satisfied
- [ ] All acceptance criteria AC1–AC7 hold
- [ ] All test scenarios TS1–TS11 pass
- [ ] `python3 -m unittest discover -s tests` exits 0

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1–FR6, NFR1–NFR3) has `status: resolved`.

## References

- Requirements document: `feature-docs/routeback-gate-postcondition/REQUIREMENTS.md`
- `replace_all` admissibility condition: `em-workflow/references/workflow-patch.md`
