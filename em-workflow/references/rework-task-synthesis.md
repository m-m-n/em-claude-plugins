# Rework Task Synthesis Contract (em-workflow)

Referenced by all four rework routes: `references/review-phase.md`'s
interactive and batch rework branches, and `skills/develop/SKILL.md`'s
interactive and batch verify rework branches. Those four call sites point
here instead of restating anything below (NFR6).

## 1. Purpose

When review findings or verify failed items require code changes beyond
what a completed `implement` phase already covers, additional tasks are
synthesized and routed back through `implement`. This document's subject is
the CONTRACT the synthesis result must satisfy — not who writes the prose
that produces it. The executing worker today is `agents/rework-planner.md`,
but the contract survives a change of executing worker (Section 13).

## 2. Applicable modes

Four routes share this contract:

- Interactive review rework
- Batch review rework
- Interactive verify rework
- Batch verify rework

Task synthesis rules (Sections 4-9, 11) are IDENTICAL across all four routes.
What differs between interactive and batch is only how a rework round gets
selected (a user's choice vs. an auto-rework cap) and the retry/round limit —
never the shape of what gets synthesized (Section 11, Invariant 7).

## 3. Inputs

The synthesizing worker receives:

```yaml
rework_source:
  type: review                   # review | verify
  review_round: 2
  findings:                      # populated when type == review
    - stable_id: abc123
      severity: high
      category: security
      file: src/auth.go
      title: "…"
      description: "…"
      suggestion: "…"
  failed_items: []                # populated when type == verify
existing_tasks: {}                # workflow.yaml tasks snapshot
next_task_id: task0007
verification_index:               # VERIFICATION.md scenario IDs -> requirement IDs
  TS-1: [FR1]
  TS-2: [NFR1]
implementation_path: /absolute/.../IMPLEMENTATION.md
spec_path: /absolute/.../SPEC.md
verification_path: /absolute/.../VERIFICATION.md
```

The full input/output envelope (including the common worker envelope fields)
is owned by `references/contracts/rework-planner-contract.md` (see
Section 13); this section states only the rework-specific payload shape.

## 4. Grouping rules

Findings and failed items are NOT mapped one-file-to-one-task. Findings (or
failed items) that share a root cause, a contract, or an Acceptance
Criterion are grouped into ONE task. Beyond grouping, ordinary task
decomposition applies unchanged — `skills/plan-writing/SKILL.md`'s Task
decomposition rules (worktree independence, size, `files` as a contract,
interface contracts over sequencing, objective Acceptance Criteria) govern
rework tasks exactly as they govern first-pass planning; this document does
not restate them.

## 5. Task ID allocation

New task IDs are allocated sequentially starting from the `next_task_id`
supplied in the input. No gaps, no reuse of any ID already present in
`existing_tasks`.

## 6. Task plan requirements

Every rework task gets a `tasks/taskNNNN.md` built from
`references/templates/task-plan.md`, exactly like a first-pass task plan.
Its Acceptance Criteria must be objective and test-translatable — the
implementer's TDD contract is unchanged by the task's rework origin. The
task plan records its origin as `provenance` (Section 11, Invariant 6).

## 7. Metadata derivation

`files` / `skills` / `domains` / `requirements` are derived from the
MEANING of the finding or failed item — what it is actually about — never
from inheriting the file set of whichever existing task happens to overlap
on file path alone (Section 11, Invariant 4). `domains` values are drawn
ONLY from the vocabulary in `references/review-rules.yaml` (the SSOT
`references/workflow-schema.md` and `agents/implementation-planner.md`
already point to); this document does not restate that vocabulary.

## 8. Verification coverage rules

Every rework task MUST declare its verification coverage in
`payload.rework_index`:

```yaml
rework_index:
  task0007:
    covered_by_existing: [TS-3]   # existing VERIFICATION.md scenario IDs, when they suffice
    new_scenarios: []             # newly added scenario IDs, when they don't
    rationale: "TS-3 already exercises the authorization boundary; no new case is needed"
```

A rework task whose `covered_by_existing` AND `new_scenarios` are BOTH empty
is FORBIDDEN — every rework task must be covered by an existing scenario, a
new one, or both.

## 9. Related document updates

| Document | Update condition |
|---|---|
| `tasks/taskNNNN.md` | Always created, one per synthesized task |
| `VERIFICATION.md` | Per Section 8's coverage rules |
| `IMPLEMENTATION.md` | Only when the rework task introduces a NEW shared contract (interface, data format) with an existing task; the synthesizing worker always emits `payload.shared_contract_rationale` (summary of what was added, or why nothing needed adding) regardless of which branch it took, so the decision has a human-readable trail |
| `SPEC.md` / `REQUIREMENTS.md` | Never updated by this synthesis; a rework that needs a SPEC change takes the transition in Section 10 instead |

### Wording-correction route

Before a needed change to `IMPLEMENTATION.md` or `VERIFICATION.md` is routed
to rework-task synthesis above or to the SPEC-change transition (Section
10), route selection checks first whether it qualifies for this
independent route.

**Applies to**: a change confined to the wording of the two create-plan-owned
documents — `IMPLEMENTATION.md` and `VERIFICATION.md`.

**Eligibility (all three, conjunctive — every condition below must hold)**:

1. No planner re-entry is needed.
2. No plan or task metadata changes: the task set, `files`, `skills`,
   `domains`, `complexity`, or plan paths.
3. No requirement metadata changes: requirement statements, IDs, `status`,
   or the task/test mapping.

**Outcome when eligible**: the correction is applied through this section's
document-update channel with no task synthesized, `create-plan` is NOT set
to `needs_update`, and no workflow patch touching planning is produced.

**Guard**: failing any ONE of the three conditions above makes this route
inapplicable, and the change instead goes through rework-task synthesis or
the SPEC-change transition (Section 10). Each condition names the concrete
artefact whose change disqualifies the route, so a change that turns out to
have touched, for example, requirement metadata is recognizable after the
fact rather than only by the intent behind it.

**Ordering**: this route is checked first; only a change that fails it can
reach the SPEC-change transition and, through it, the classification gate
(`references/question-resolution.md`).

## 10. Workflow state transition

**Review-sourced rework** proceeds in this fixed order:

1. The orchestrator writes `review.needs_rework = true` and
   `review.status = pending` directly to workflow.yaml (orchestrator
   responsibility — this write is NEVER carried inside a worker patch).
2. The orchestrator dispatches rework-planner.
3. The orchestrator validates and applies rework-planner's patch
   (`tasks_patch` + `step_patches` + `preserve`; `references/workflow-patch.md`).
4. `implement` returning to `pending` happens INSIDE that patch's
   `step_patches` in step 3 — it is never a separate write, and it never
   precedes step 3 registering at least one pending rework task
   (Section 11, Invariant 1).

**Verify-sourced rework** skips step 1 entirely and starts at step 2:
`review.needs_rework` is a review-specific field, so verify-sourced rework
never sets it (Section 11, Invariant 11).

**When rework needs a SPEC.md change**: the synthesizing worker creates no
task. Instead it returns `status: needs_user_input` with
`gate_id: rework.spec-change`. Once the user (interactive) selects the SPEC
change, the orchestrator's transition is fixed:

1. `create-spec` step → `needs_update`
2. `create-plan` / `implement` / `review` steps → `pending`
3. `workflow[implement].base_commit` is preserved unchanged
4. phase-state `rework.yaml` records `reason`, `origin_kind`, `origin_id`,
   `recorded_at_commit`, and `replan_authorized: true` (field definitions
   owned by `references/phase-state.md`; this document does not restate
   them)
5. The develop state machine re-enters at `create-spec`

Step 2's `create-plan` re-entry is not rejected merely because merged tasks
already exist in `workflow.yaml` at that point. The permission conditions
that decide when a re-entry is admitted are owned by
`references/workflow-patch.md`; this document does not restate them.

In batch mode, `rework.spec-change` is resolved through the classification
gate defined in `references/question-resolution.md`, which this document
does not restate. Interactive mode is unchanged: the user is asked
directly.

**Other question conditions** — the synthesizing worker returns a question
packet instead of tasks only when: the same finding still has mutually
exclusive fix approaches; a requirement exclusion or license change is
required; or the finding alone cannot make its Acceptance Criteria
objective.

## 11. Invariants

1. Before `implement` returns to `pending`, at least one new rework task is
   registered in workflow.yaml.
2. Every newly synthesized task's `status` is `pending`.
3. Every rework task plan states objective, test-translatable Acceptance
   Criteria.
4. `files` / `skills` / `domains` / `requirements` are derived from the
   finding's or failed item's meaning; file-overlap inheritance from an
   existing task alone is not sufficient.
5. `workflow[implement].base_commit` is never changed by a rework patch; it
   is always listed in the patch's `preserve` set.
6. Review-sourced tasks carry the finding's `stable_id`, verify-sourced
   tasks carry the failed item's ID, as `provenance`. Named as a pair, this
   is `origin_kind` (`review` | `verify`) and `origin_id`: for
   `origin_kind: review`, `origin_id` is the finding's `stable_id`; for
   `origin_kind: verify`, `origin_id` is the failed item's ID. This
   document is the pair's one definition; every consumer of a
   rework-derived question's origin — `references/question-resolution.md`
   for what origin verification matches against and what set the
   security / license / irreversible check runs over,
   `references/phase-state.md` for what the `spec_change` record stores —
   cites this pair rather than defining its own.
7. Interactive and batch never differ in task synthesis rules; they differ
   only in how a rework round is selected and in the retry/round cap.
8. Patch application and every workflow.yaml write are always performed by
   the orchestrator, never by the synthesizing worker itself.
9. When rework requires a SPEC.md change, no task is created — the
   SPEC-change transition (Section 10) applies instead.
10. Every rework task declares its verification coverage via `rework_index`
    (Section 8).
11. Verify-sourced rework never sets `review.needs_rework` — that field is
    review-specific, and the verify-sourced transition begins directly at
    dispatch (Section 10).

## 12. Validation

Machine-checkable rules a validator applies against the synthesis output:

- Every synthesized task appears as a key in `rework_index`.
- Every ID listed in a task's `covered_by_existing` exists in the input's
  `verification_index`.
- Every ID listed in a task's `new_scenarios` exists in the VERIFICATION.md
  diff the synthesis produced.
- When `new_scenarios` is non-empty, the same IDs also appear in the
  `requirements_patch`'s `tests_append`.
- No task has BOTH `covered_by_existing` and `new_scenarios` empty
  (Section 8).

## 13. Execution adapter

The worker that performs this synthesis today is `agents/rework-planner.md`;
its input/output envelope (including the common worker envelope fields) is
`references/contracts/rework-planner-contract.md`. This document states the
contract the RESULT must satisfy; the adapter document states how the
current worker is invoked to produce it. A future change of executing
worker updates only the adapter, never this contract.
