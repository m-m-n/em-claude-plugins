# Feature: create-plan-status-conflict

## Overview

Executing the create-plan phase exactly as the protocol prescribes always fails with `replace-all-not-permitted`: `skills/develop/SKILL.md` Step B requires every step to be set to `in_progress` before dispatch, while `references/workflow-patch.md` application rule 5 permits a `replace_all` patch only when create-plan is `pending` or `needs_update`. This feature removes that contradiction by exempting create-plan from Step B's pre-dispatch `in_progress` update, and by adding a deterministic recovery rule for features already interrupted in `in_progress`. Requirement source of truth: `feature-docs/create-plan-status-conflict/REQUIREMENTS.md`.

## Objectives

- Resolve the contradiction that makes a protocol-conformant create-plan phase always fail with `replace-all-not-permitted`, so that unattended (`--batch`) execution can pass through create-plan.
- Bring `skills/develop/SKILL.md` Step B, `references/workflow-patch.md` rule 5, and `scripts/validate-worker-output.py` to a state where all three share one single specification for how a `replace_planning` patch against an `in_progress` create-plan step is handled.

## User Stories

### US1: Unattended run passes create-plan
As a `--batch` run of `/em-workflow:develop`, I want create-plan to reach `completed` without user interaction, so that the workflow is not blocked by a protocol-internal contradiction.

**Acceptance Criteria:**
- [ ] AC1: The handling of a `replace_planning` patch against an `in_progress` create-plan step is uniquely determined — create-plan is never `in_progress` at dispatch time; if it was interrupted in `in_progress`, Reconcile on entry resets it to `pending` before dispatch; a patch submitted while still `in_progress` is rejected by rule 5.
- [ ] AC2: `skills/develop/SKILL.md` Step B and `references/workflow-patch.md` rule 5 do not contradict each other (Step B exempts create-plan, rule 5 unchanged).
- [ ] AC3: The behaviour of `scripts/validate-worker-output.py` matches the updated specification (it matches without any functional change, and that match is pinned by a regression test).

### US2: Deterministic recovery of an interrupted feature
As a maintainer resuming a feature whose create-plan step was left at `in_progress`, I want the recovery procedure to be readable directly from the phase protocol, so that recovery is deterministic and needs no ad-hoc judgement.

**Acceptance Criteria:**
- [ ] AC4: Reading `references/phases/create-plan-phase.md`'s Reconcile on entry alone is sufficient to follow the recovery procedure for an existing feature interrupted at `in_progress`.
- [ ] AC5: `python3 -m unittest discover -s tests` passes in full.
- [ ] AC6: The `version` in `em-workflow/.claude-plugin/plugin.json` is bumped.

## Technical Requirements

### Functional Requirements

- **FR1 — Exempt create-plan from Step B's pre-dispatch `in_progress` update:** `skills/develop/SKILL.md` Step B treats the create-plan step as the sole exception to the rule "update status to `in_progress` before executing the step". create-plan does not change its status before dispatch, and advances directly to `completed` (plus `completed_at_commit`, rule R2) after the phase completes (patch applied and commit succeeded).
- **FR2 — The exception preserves the entry status, keeping the `needs_update` branch reachable:** The exception never overwrites create-plan's entry status. Entering as `pending` (first planning) dispatches the planner as `pending`; entering as `needs_update` (explicit re-planning) dispatches as `needs_update`. Both branches permitted by rule 5 thereby become actually reachable.
- **FR3 — State the rationale of the exception in Step B:** The exception text carries its reasons — (a) `replace_all` is permitted only while create-plan is `pending` / `needs_update` (reference `references/workflow-patch.md` rule 5 only; do not duplicate the condition text), and (b) create-plan's interrupt recovery is carried by `phase-state/create-plan.yaml`, so no `in_progress` marker is needed. The wording follows the same layout as the existing design-system backfill section "**`in_progress` へ先に更新しない理由**".
- **FR4 — Do not change workflow-patch.md rule 5:** The "`replace_all` permission conditions" section and application rule 5 in `references/workflow-patch.md` keep their current wording (permitted only while create-plan is `pending` or `needs_update`).
- **FR5 — Do not change the validator's permission condition (behaviour already matches the updated spec):** The replace_all check inside `_validate_dry_run_apply` in `scripts/validate-worker-output.py` (currently lines 1168-1176, `current_status not in ("pending", "needs_update")`) is not functionally changed. Under FR1/FR2 the create-plan status at planner dispatch is always `pending` or `needs_update`, so the current implementation already matches the updated specification. The only change is the added regression test (FR8).
- **FR6 — Add the interrupt-recovery rule to create-plan-phase.md's Reconcile on entry:** Add one rule to "3. Reconcile on entry" in `references/phases/create-plan-phase.md` — if, on entry, the create-plan step in `workflow.yaml` is `in_progress` and a proposed patch has not been applied, reset create-plan to `pending` before dispatching the planner and commit via `commit-docs.sh` per Step B's discipline. If the patch has already been applied, do not perform this reset; instead perform only the transition to `completed`, following the existing §11 and the `references/phase-state.md` Resume decision table (`applying_patch`(applied) row).
- **FR7 — Documentation consistency inside the plugin:** No other SSOT — starting with `references/phase-state.md` (Resume decision table, legacy compatibility table, backfill section) — may retain wording that contradicts FR1's exception by stating that every step is set to `in_progress` before execution. The Resume decision table is keyed on the phase-state `status` and does not depend on the workflow step status, so this feature's default judgement is that `phase-state.md` needs no change. Any place found to need a change is updated within the same change.
- **FR8 — Update and add tests:** Add assertions under the repository-root `tests/` verifying that (a) develop SKILL.md Step B documents the create-plan exception and its rationale, (b) create-plan-phase.md §3 documents the in_progress → pending reset rule, (c) workflow-patch.md rule 5 still reads `pending` / `needs_update`, and (d) the validator still rejects `replace_all` against an `in_progress` create-plan. Guarantee that the existing `tests/test_develop_skill_rewiring.py` (Step B strings and backfill ordering), `tests/test_phase_protocols.py` (create-plan-phase.md section structure), `tests/test_workflow_patch_doc.py` and `tests/test_validate_worker_output.py` keep passing, updating them within the same change if required.
- **FR9 — Plugin version bump:** Patch-bump `version` in `em-workflow/.claude-plugin/plugin.json` from 0.1.34 to 0.1.35. The em-workflow entry in the root `.claude-plugin/marketplace.json` carries no `version` field (only name / description / author / category / source), so it needs no change.

### Non-Functional Requirements

- **NFR1 - Out-of-scope preservation:** The `append_rework` (rework-planner path) permission conditions, the validator's `mode == "append"` branch, and `references/rework-task-synthesis.md` are not changed at all.
- **NFR2 - No runtime logic change:** Changes are limited to documentation (SSOT prose), tests, and the version. The decision logic of `validate-worker-output.py`, the hooks, and the shell scripts' behaviour are unchanged.
- **NFR3 - SSOT ownership boundaries preserved:** develop SKILL.md references rule 5 rather than duplicating its condition text. No document breaks the existing "do not restate" discipline (the must-not-restate assertions in `tests/test_phase_protocols.py`).
- **NFR4 - Unattended completion:** After the change, a `--batch` create-plan phase reaches `completed` without user interaction.

## Implementation Approach

### Architecture

**Affected artifacts:**

```
em-workflow/
├── skills/develop/SKILL.md                     # FR1, FR2, FR3 — Step B exception + rationale
├── references/
│   ├── phases/create-plan-phase.md             # FR6 — §3 Reconcile on entry reset rule
│   ├── workflow-patch.md                       # FR4 — unchanged (pinned by test)
│   └── phase-state.md                          # FR7 — change only if a contradiction is found
├── scripts/validate-worker-output.py           # FR5 — unchanged (pinned by regression test)
└── .claude-plugin/plugin.json                  # FR9 — 0.1.34 → 0.1.35
tests/                                          # FR8 — doc assertions + validator regression
```

**Component relationships:** Step B (execution discipline) determines the create-plan step status at planner dispatch time; rule 5 (permission conditions) and the validator's `_validate_dry_run_apply` check consume that status. This feature adjusts only the producer side (Step B) and adds a recovery path (Reconcile on entry) so the consumer side stays untouched.

### Data Flow

```
workflow.yaml create-plan status
  pending / needs_update ──> Step B (no pre-dispatch update, FR1/FR2)
                              └─> planner dispatch ─> replace_planning (replace_all) patch
                                    └─> rule 5 permits ─> apply + commit ─> completed (+completed_at_commit)
  in_progress (interrupted)
    ├─ patch not applied ──> Reconcile on entry resets to pending (FR6) ─> flow above
    └─ patch applied ─────> no reset; §11 / phase-state Resume table (applying_patch applied) ─> completed
```

### API Design

Not applicable — this feature exposes no API.

### Database Schema

Not applicable — this feature introduces no persisted data model.

### Dependencies

**Internal Dependencies:**
- `skills/develop/SKILL.md` Step B: owns the pre-dispatch status-update discipline that FR1/FR2/FR3 amend.
- `references/workflow-patch.md` rule 5: owns the `replace_all` permission conditions that FR4 keeps unchanged and NFR3 forbids duplicating.
- `references/phases/create-plan-phase.md`: owns the Reconcile on entry procedure extended by FR6, and §11 referenced by EC2.
- `references/phase-state.md`: owns the Resume decision table, legacy compatibility table and backfill section examined by FR7 / EC2 / EC3.
- `scripts/validate-worker-output.py`: enforces the permission condition at `--dry-run-apply` time; unchanged per FR5.

**External Dependencies:**
- `python3` `unittest` (standard library): test runner for AC5.

### File Structure

```
em-workflow/skills/develop/SKILL.md
em-workflow/references/phases/create-plan-phase.md
em-workflow/references/workflow-patch.md
em-workflow/references/phase-state.md
em-workflow/scripts/validate-worker-output.py
em-workflow/.claude-plugin/plugin.json
tests/test_develop_skill_rewiring.py
tests/test_phase_protocols.py
tests/test_workflow_patch_doc.py
tests/test_validate_worker_output.py
```

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1, FR3, FR8): A doc-assertion test verifying that the Step B text in develop SKILL.md contains the create-plan exception and its rationale, and that the existing backfill ordering assertion (the backfill description precedes the generic `in_progress` update sentence) still holds at the same time.
- [ ] TS-2 (FR6, FR8): A doc-assertion test verifying that create-plan-phase.md §3 contains the rule "if create-plan is `in_progress` and the patch is not applied, reset to `pending` before dispatch", and also states that no reset is done when the patch is already applied.
- [ ] TS-3 (FR4, FR8): A test verifying that the `replace_all` permission conditions section in workflow-patch.md retains the two conditions `pending` / `needs_update` (extension of the existing `tests/test_workflow_patch_doc.py`, or a new test).
- [ ] TS-4 (FR2, FR5, FR8): A validator regression test verifying that validating a `replace_all` patch with `--dry-run-apply` against a workflow.yaml whose create-plan step is `in_progress` exits 1 with `replace-all-not-permitted`, and that `pending` and `needs_update` pass.

### Integration Tests
- [ ] TS-5 (FR8, FR9): Full run of `python3 -m unittest discover -s tests`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] EC1: Entering Step B for re-planning with create-plan at `needs_update`. Because the exception does not rewrite the status, the planner is dispatched as `needs_update` and is permitted by rule 5's second branch.
- [ ] EC2: Interrupted at `in_progress` but the patch was already applied. Reconcile performs no reset; only the `completed` transition is executed, following §11 and the `applying_patch`(applied) row of the `references/phase-state.md` Resume decision table.
- [ ] EC3: A legacy feature with no phase-state whose create-plan is `in_progress`. Confirm that the legacy compatibility table in phase-state.md (restart that phase under the new flow) and FR6's reset rule land on the same conclusion (re-run from pending).
- [ ] EC4: Interaction with stop condition 2 (a step executed twice in a row without status progress = stuck). Since a successful create-plan no longer passes through `in_progress`, the stuck check is made on whether `pending` (or `needs_update`) repeats twice. Confirm no false positive occurs on a normal single run, which reaches `completed`.
- [ ] EC5: Confirm that no other mechanism depends on the create-plan step being `in_progress` (queue-related hooks are expected to reference only the implement step / task statuses).

### Performance Tests
Not applicable.

## Security Considerations

- **Permission condition floor:** The first condition of `replace_all` (tasks empty, or all tasks pending) is not relaxed.
- **Terminal-status protection:** `replace_all` against a `completed` / `failed` create-plan continues to be rejected.
- **Write ownership boundary:** The boundary under which a worker never writes `workflow.yaml` directly (Write ownership in workflow-schema.md) is unchanged.

## Error Handling

| Condition | Outcome |
|---|---|
| `replace_all` submitted while create-plan is `in_progress` | Rejected by rule 5; validator `--dry-run-apply` exits 1 with `replace-all-not-permitted` (FR5, TS-4) |
| create-plan is `in_progress` on entry with the patch not applied | Reconcile on entry resets to `pending`, commits via `commit-docs.sh`, then dispatches (FR6) |
| create-plan is `in_progress` on entry with the patch already applied | No reset; only the `completed` transition per §11 / phase-state Resume table (EC2) |
| Patch application or commit does not succeed | create-plan is not advanced to `completed` (FR1) |

## Performance Optimization

Not applicable — the change is documentation, tests and version only (NFR2).

## Success Criteria

- [ ] All functional requirements (FR1–FR9) are implemented and tested
- [ ] All test scenarios (TS-1–TS-5) pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1–AC6 in REQUIREMENTS.md §11.1 are all satisfied

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement is `status: ok`.

## Assumptions

- **A1 (question_id: requirement.status-conflict-direction):** Adopt the direction of exempting develop SKILL.md Step B. create-plan runs while still pending rather than being set to `in_progress` before dispatch, and advances to completed after the patch is applied. The permission conditions in workflow-patch.md rule 5 and in the validator are not changed. *Basis:* gate `create-spec.requirement-clarification` resolved via `codex_consultation` in batch-policies.yaml (source: batch-codex-consultation, selected_option_id: exempt-create-plan, record_as_assumption: true). Codex grounded it on preserving the meaning of `in_progress` while making both the `pending` and `needs_update` branches of rule 5 reachable. It also agrees with the hand-off note in the task description (consider option (b) first).
- **A2 (question_id: requirement.existing-in-progress-recovery):** Recovery of features already interrupted at `in_progress` is handled by adding a rule to create-plan-phase.md's Reconcile on entry: "if interrupted at `in_progress` with the patch not applied, reset create-plan to `pending` before dispatch". *Basis:* gate `create-spec.requirement-clarification` resolved via `codex_consultation` in batch-policies.yaml (source: batch-codex-consultation, selected_option_id: reconcile-resets, record_as_assumption: true). Codex grounded it on giving unattended runs a deterministic recovery path without permanently relaxing the validator.
- **A3:** The em-workflow entry in `.claude-plugin/marketplace.json` has no `version` field, so plugin.json is the only target of the version bump. *Basis:* direct inspection of marketplace.json (the plugins[] entry carries only name / description / author / category / source).

## Design Step

Skipped — the change consists solely of plugin-internal SSOT documents and tests, with no visual element or UI.

## References

- Requirements document: `feature-docs/create-plan-status-conflict/REQUIREMENTS.md`
- Step B execution discipline: `em-workflow/skills/develop/SKILL.md`
- `replace_all` permission conditions / application rule 5: `em-workflow/references/workflow-patch.md`
- Reconcile on entry, §11: `em-workflow/references/phases/create-plan-phase.md`
- Resume decision table, legacy compatibility table, backfill section: `em-workflow/references/phase-state.md`
- replace_all check in `_validate_dry_run_apply` (currently lines 1168-1176): `em-workflow/scripts/validate-worker-output.py`
- Existing tests: `tests/test_develop_skill_rewiring.py`, `tests/test_phase_protocols.py`, `tests/test_workflow_patch_doc.py`, `tests/test_validate_worker_output.py`
- Plugin version: `em-workflow/.claude-plugin/plugin.json`
