# Feature: implement-routeback-gate

## Overview

Step I.2.c of `em-workflow/references/implement-phase.md` describes a "route back to planning" path that is unreachable in practice: the sequence never returns the failed task to `pending`, so the planner's only operation (`replace_planning` / `replace_all`) is rejected by `references/workflow-patch.md`'s permission conditions the moment create-plan re-enters. The same paragraph carries a self-contradictory gate condition, points the merged-task case at an undefined rework trigger, and cites the wrong develop-side clause as the owner of the stop-condition-3 precedence.

This feature is a documentation-only change to that one protocol document, plus the mandated plugin version bump. Requirement details are defined in `feature-docs/implement-routeback-gate/REQUIREMENTS.md`; this document is the implementation-facing rendering of the same requirements.

## Objectives

- Make Step I.2.c's "route back to planning" path actually reachable, so that create-plan re-entry satisfies the planner operation's permission conditions.
- Restate the gate in terms of the condition that is observable at route-back time: no task has merged.
- Give the merged-task case a defined terminal — leave `implement` as `failed` and return control to the user through develop's stop condition 3, the same terminal as "abort phase" — instead of pointing at an undefined rework trigger.
- Correct the delegation naming so implement-phase.md cites the develop-side clause that actually owns the stop-condition-3 precedence.
- Keep the change confined to one protocol document plus the plugin version bump, so no owned SSOT (develop SKILL.md, workflow-patch.md, rework-task-synthesis.md) and no existing regression test is disturbed.

## User Stories

### US1: Route back to planning after a task failure with no merged task
As the em-workflow orchestrator, I want Step I.2.c's route-back sequence to reset the failed task to `pending` and commit that write-back, so that create-plan re-entry is accepted by the planner operation's permission conditions.

**Acceptance Criteria:**
- [ ] AC-1: I.2.c's route-back bullet states that the failed task's status is set back to `pending` and that the failure reason remains in `tasks.{T}.notes`. (FR1)
- [ ] AC-2: The route-back sequence ends with a `commit-docs.sh` commit of the workflow.yaml write-back, ordered before the phase ends / create-plan re-enters, and the ordering relative to the failed task's worktree and branch cleanup is unambiguous in the text. (FR2)
- [ ] AC-3: The exit-4 recovery bullet's call-site enumeration names the I.2.c route-back commit alongside Step I.1's and Step I.2.b's commits. (FR3)
- [ ] AC-4: The gate sentence expresses the condition as the absence of any `merged` task; the string "every existing task is still `pending`" no longer appears in I.2.c. (FR4)

### US2: Terminate at a defined stop when a merged task exists
As the em-workflow orchestrator, I want the merged-task branch to terminate at `failed` plus develop's stop condition 3, so that the case has a defined terminal instead of an undefined rework trigger.

**Acceptance Criteria:**
- [ ] AC-5: The merged-task branch states that `implement` stays `failed` and control returns to the user via develop's stop condition 3, and contains no instruction to hand scope to the rework path or to use `append`. (FR5)
- [ ] AC-6: The delegation sentence names develop SKILL.md Step B's stop-condition-3 precedence clause and no longer attributes that precedence to the create-plan `in_progress` exemption. (FR6)
- [ ] AC-8: The batch-mode paragraph after I.2.c is byte-identical to its pre-change text. (FR8)

## Technical Requirements

### Functional Requirements

- **FR1 — Route-back resets the failed task to `pending`:** Step I.2.c's "route back to planning" sequence explicitly sets the failed task's `tasks.{T}.status` from `failed` back to `pending`, while the failure reason stays recorded in `tasks.{T}.notes`. The reset is stated as part of the same ordered write set that sets `create-plan` to `needs_update` and the `implement` step back to `pending`.
- **FR2 — The route-back write-back is committed before create-plan re-entry:** The whole route-back workflow.yaml write (create-plan `needs_update`, implement `pending`, task status `pending`, failure notes) is committed with `commit-docs.sh` against the integration worktree before the phase ends and create-plan re-enters — matching the file's standing discipline that every workflow.yaml write is followed by a `commit-docs.sh` commit in the same step. The instruction states the expected-tip third argument the way the file's other call sites do.
- **FR3 — The exit-4 recovery enumeration covers the new call site:** The Branch & Worktree Model's exit-4 recovery bullet, which currently enumerates "Step I.1's baseline commit and Step I.2.b's wake-phase commit" as the phase's `commit-docs.sh` call sites, is extended to name the new I.2.c route-back commit, so the bounded recovery rule demonstrably applies to it.
- **FR4 — The gate is restated as "no merged task exists":** The condition governing automatic re-entry is restated as "applies only when no task has merged (there is no task with status `merged`)". The current phrasing "applies only when every existing task is still `pending` (i.e. none has merged yet)" — which the failed task itself falsifies at the moment the decision is taken — is removed.
- **FR5 — Merged-task branch terminates at `failed` + develop stop condition 3:** When at least one task has merged, automatic re-entry does not apply: `create-plan` is NOT set to `needs_update`, `implement` stays `failed`, and the phase reports and returns control to the user via develop's stop condition 3 — the same terminal as the "abort phase" option. The existing instruction to "hand the additional scope to the rework path (`append`)" is removed, together with its `replace_all`-rejection rationale sentence, since no defined trigger routes implement into rework.
- **FR6 — Delegation citation names the clause that owns the precedence:** In the same paragraph, the sentence currently reading "`skills/develop/SKILL.md` Step B's create-plan exemption owns that precedence" is corrected to cite Step B's stop-condition-3 precedence clause, whose auto-re-entry exclusion list explicitly enumerates the create-plan route-back transition owned by implement-phase.md. The create-plan `in_progress` exemption — a different Step B block — is no longer named as the owner. implement-phase.md continues to cite rather than restate develop's rule.
- **FR7 — Change containment:** All protocol edits are confined to `em-workflow/references/implement-phase.md`. `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/references/contracts/*`, and `tests/test_develop_skill_rewiring.py` are not modified.
- **FR8 — Batch-mode paragraph stays intact:** The batch-mode paragraph that follows I.2.c is left unchanged: route-back-to-planning is still never taken automatically in batch mode, so the new reset-and-commit sequence is scoped to the interactive route-back selection and creates no new batch behaviour.
- **FR9 — Plugin version patch bump:** `em-workflow/.claude-plugin/plugin.json` `version` is patch-bumped from 0.1.35 to 0.1.36 in the same change. The root `.claude-plugin/marketplace.json` entries carry no `version` field and are therefore untouched.

### Non-Functional Requirements

- **NFR1 - Existing test contracts preserved:** The literal heading `### I.2.c: Failed handling` stays byte-identical (it is `tests/test_review_implement_develop_lock_contracts.py`'s section-slice anchor), and no line in implement-phase.md may start with `git ` while containing `commit` or `add -A`. The new commit instruction therefore goes through `commit-docs.sh`, never a raw git line. The wake-phase assertions on the slice preceding that heading remain satisfied.
- **NFR2 - SSOT non-duplication:** implement-phase.md cites owner documents rather than restating them: `references/workflow-patch.md` for `replace_all` permission conditions and `skills/develop/SKILL.md` Step B for stop-condition-3 precedence. No rule owned elsewhere is copied into I.2.c.
- **NFR3 - Documentation-only change:** No executable behaviour changes: no scripts, hooks, agents, or skill prompts are edited. The deliverable is protocol markdown plus the version bump.
- **NFR4 - Local style consistency:** Edited prose matches the surrounding file: English narrative in implement-phase.md, existing bullet structure and backtick conventions retained, no added justification beyond what the requirement states.

## Implementation Approach

### Architecture

This is a protocol-document change. There is no runtime component, no service layer, and no data store involved. The affected structure is the document hierarchy of the implement phase protocol:

```
em-workflow/references/implement-phase.md
├── Branch & Worktree Model
│   └── exit-4 recovery bullet          # FR3: extend commit-docs.sh call-site enumeration
└── ### I.2.c: Failed handling          # heading byte-identical (NFR1)
    ├── route-back-to-planning bullet   # FR1, FR2, FR4
    ├── merged-task branch              # FR5, FR6
    └── batch-mode paragraph            # FR8: unchanged, byte-identical
```

### Data Flow

Route-back path (no merged task exists):

```
task {T} failed
  → record failure reason in tasks.{T}.notes
  → ordered write set on workflow.yaml:
       create-plan       := needs_update
       implement step    := pending
       tasks.{T}.status  := pending          (FR1)
  → failed task worktree / branch cleanup    (ordering unambiguous in the text, AC-2)
  → commit-docs.sh commit of the write-back  (FR2, expected-tip third argument as elsewhere in the file)
  → phase ends → create-plan re-enters
```

Terminal path (at least one merged task exists):

```
task {T} failed, some task merged
  → automatic re-entry does NOT apply       (FR4 gate: no merged task)
  → create-plan NOT set to needs_update
  → implement stays failed                  (FR5)
  → report and return control to the user via develop stop condition 3
```

### API Design

Not applicable — no API surface.

### Database Schema

Not applicable — no schema. The workflow.yaml fields written on the route-back path are `create-plan`'s status, the `implement` step's status, `tasks.{T}.status`, and `tasks.{T}.notes`.

### Dependencies

**Internal Dependencies (cited, not modified):**
- `em-workflow/references/workflow-patch.md`: owner of `replace_all` permission conditions (NFR2).
- `em-workflow/skills/develop/SKILL.md` Step B: owner of the stop-condition-3 precedence, whose auto-re-entry exclusion list enumerates the create-plan route-back transition (FR6, NFR2).
- `em-workflow/references/implement-phase.md` Branch & Worktree Model: owner of the exit-4 bounded recovery rule (FR3).

**External Dependencies:**
- None.

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md          # the only protocol document edited (FR1–FR6, FR8, NFR1–NFR4)
└── .claude-plugin/
    └── plugin.json                 # version 0.1.35 → 0.1.36 (FR9)

tests/
├── test_review_implement_develop_lock_contracts.py   # existing regression, unchanged (TS-7)
└── test_develop_skill_rewiring.py                    # existing regression, unchanged (FR7, TS-8)
```

Not modified: `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/references/contracts/*`, root `.claude-plugin/marketplace.json` (FR7, FR9).

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (unittest, document contract) — Parse the `### I.2.c: Failed handling` section of implement-phase.md and assert the route-back bullet contains the failed-task `pending` reset together with the notes-preservation clause. Covers AC-1 → FR1.
- [ ] **TS-2** (unittest, document contract) — Assert the I.2.c section contains a `commit-docs.sh` call and that its index follows the status-write instructions and precedes the end-of-phase report sentence. Covers AC-2 → FR2.
- [ ] **TS-3** (unittest, document contract) — Assert the exit-4 recovery bullet's call-site list mentions I.2.c in addition to I.1 and I.2.b. Covers AC-3 → FR3.
- [ ] **TS-4** (unittest, document contract) — Assert the I.2.c gate sentence expresses "no merged task" and that the old "every existing task is still `pending`" phrasing is absent from the section. Covers AC-4 → FR4.
- [ ] **TS-5** (unittest, document contract) — Assert the merged-task branch mentions `failed` retention and develop's stop condition 3, and that neither "rework" nor "`append`" appears in that branch's text. Covers AC-5 → FR5.
- [ ] **TS-6** (unittest, document contract) — Assert the delegation sentence cites Step B's stop-condition-3 precedence clause and does not read "create-plan exemption owns that precedence". Covers AC-6 → FR6.

### Integration Tests

Not applicable — the change has no executable surface (NFR3).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Regression Tests

- [ ] **TS-7** (unittest, existing regression) — Run the existing `tests/test_review_implement_develop_lock_contracts.py` suite unchanged: the I.2.c heading anchor resolves and implement-phase.md still yields zero bare git commit / git add -A lines. Covers AC-9 → FR7, NFR1.
- [ ] **TS-8** (unittest, existing regression) — Run `tests/test_develop_skill_rewiring.py` unchanged to confirm develop SKILL.md and its carve-out assertions were not disturbed. Covers AC-7, AC-9 → FR7, FR9, NFR1.

### Edge Cases

- [ ] The failed task itself is not `pending` at decision time — the gate must still evaluate, which is why it is expressed as the absence of any `merged` task rather than as "every existing task is still `pending`" (FR4, AC-4).
- [ ] At least one task has merged — automatic re-entry does not apply and the phase terminates at `failed` plus develop stop condition 3, with no rework/`append` handoff (FR5, AC-5).
- [ ] Batch mode — route-back-to-planning is never taken automatically, so the new reset-and-commit sequence introduces no batch behaviour; the batch-mode paragraph stays byte-identical (FR8, AC-8).

### Performance Tests

Not applicable.

## Security Considerations

Not applicable — documentation-only change with no executable behaviour, no input handling, and no data surface (NFR3).

## Error Handling

The exit-4 recovery bullet in the Branch & Worktree Model is the error-handling rule that applies to `commit-docs.sh` call sites. FR3 extends its call-site enumeration to include the new I.2.c route-back commit so that the bounded recovery rule demonstrably applies to it.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC-1: I.2.c's route-back bullet states that the failed task's status is set back to `pending` and that the failure reason remains in `tasks.{T}.notes`. (FR1)
- [ ] AC-2: The route-back sequence ends with a `commit-docs.sh` commit of the workflow.yaml write-back, ordered before the phase ends / create-plan re-enters, and the ordering relative to the failed task's worktree and branch cleanup is unambiguous in the text. (FR2)
- [ ] AC-3: The exit-4 recovery bullet's call-site enumeration names the I.2.c route-back commit alongside Step I.1's and Step I.2.b's commits. (FR3)
- [ ] AC-4: The gate sentence expresses the condition as the absence of any `merged` task; the string "every existing task is still `pending`" no longer appears in I.2.c. (FR4)
- [ ] AC-5: The merged-task branch states that `implement` stays `failed` and control returns to the user via develop's stop condition 3, and contains no instruction to hand scope to the rework path or to use `append`. (FR5)
- [ ] AC-6: The delegation sentence names develop SKILL.md Step B's stop-condition-3 precedence clause and no longer attributes that precedence to the create-plan `in_progress` exemption. (FR6)
- [ ] AC-7: The change's name-only file list contains only `em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, the feature-docs artifacts, and the test file(s) added or extended for this feature. (FR7, FR9)
- [ ] AC-8: The batch-mode paragraph after I.2.c is byte-identical to its pre-change text. (FR8)
- [ ] AC-9: `python3 -m unittest discover -s tests` passes, including `tests/test_review_implement_develop_lock_contracts.py` and `tests/test_develop_skill_rewiring.py` unchanged. (FR7, NFR1)
- [ ] AC-10: `em-workflow/.claude-plugin/plugin.json` reads `"version": "0.1.36"`. (FR9)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement has `status: ok`.

## Assumptions

- **AS-1**: The requirement set was reconstructed from the recorded phase-state answers plus the target text in the integration worktree.
- **AS-2**: The `arch-implementphase-delegation` correction target was verified by reading develop SKILL.md: the auto-re-entry exclusion that names implement-phase.md's route-back transition lives in Step B's 「停止条件 3 との優先関係」 block, which is a different block from the create-plan `in_progress` exemption that the current implement-phase.md sentence names.
- **AS-3**: Since implement-phase.md is written in English while the develop clause's heading is Japanese, the corrected citation may quote the Japanese heading literal; that is treated as acceptable style rather than a rule violation.
- **AS-4**: The version bump target is 0.1.35 to 0.1.36 (patch), and the root `.claude-plugin/marketplace.json` needs no edit because its entries carry no `version` field.
- **AS-5**: New assertions land as Python `unittest` tests under `tests/`, run by `python3 -m unittest discover -s tests`; the project defines no build, format, or e2e command.
- **AS-6**: `cmp-exemption-slice-widened` (the widened slice in `tests/test_develop_skill_rewiring.py`) is explicitly out of scope per the answered `routeback.adjacent-findings-scope` question and is not represented by any requirement.
- **AS-7**: This worktree forks from the open PR #3 branch `em-workflow/create-plan-status-conflict/integration`, so the target text is the post-PR-#3 wording; the change is expressed against that wording.

## Design Step

Skipped. Reason: protocol markdown plus a version-number change only. The feature has no UI surface, no rendered output, and zero design-system candidates.

## References

- Requirements document (Japanese): `feature-docs/implement-routeback-gate/REQUIREMENTS.md`
- Target protocol document: `em-workflow/references/implement-phase.md`
- Cited owner of stop-condition-3 precedence: `em-workflow/skills/develop/SKILL.md` Step B
- Cited owner of `replace_all` permission conditions: `em-workflow/references/workflow-patch.md`
- Version bump target: `em-workflow/.claude-plugin/plugin.json`
- Existing regression suites: `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_develop_skill_rewiring.py`
