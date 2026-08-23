# rework-planner Contract (em-workflow SSOT)

Input/output contract for the `rework-planner` worker. Renders
design-input.md 5.4.4. This document adds only rework-planner-specific
content; the common dispatch envelope is defined once in
`references/contracts/worker-envelope.md` and the question packet / answer
shape once in `references/question-packet-schema.md` — neither is restated
here. The shape the rework-planner's output must satisfy (grouping, task ID
allocation, metadata derivation, the `rework_index` coverage rules, state
transition ordering, the eleven invariants) is owned by
`references/rework-task-synthesis.md`; this contract states the
rework-planner's dispatch input/output around that shape without restating
its content. The common `write_policy` field's path-level model (the six
actions, the `targets` / `allowed_write_roots` split, `expect_digest`
requirements) is owned by `references/contracts/spec-writer-contract.md`
and is cited by path below, not restated.

## Responsibility

Plan **only the additional tasks** arising from review findings or verify
`failed_items` — never rewrite the existing plan as a whole. The
rework-planner never calls AskUserQuestion itself and never writes
`workflow.yaml` directly; its only channel for a `workflow.yaml` change is
the `workflow_patch` it returns (operation `append_rework`, per
`references/workflow-patch.md`).

## Additional input: `rework_source`

```yaml
rework_source:
  type: review                   # review | verify
  review_round: 2                # review-sourced only
  findings:                      # review-sourced only
    - stable_id: abc123
      severity: high
      category: security
      file: src/auth.go
      title: "…"
      description: "…"
      suggestion: "…"
  failed_items: []                # verify-sourced only
existing_tasks: {}                # workflow.yaml tasks snapshot
next_task_id: task0007
verification_index:               # VERIFICATION.md scenario IDs -> requirement IDs
  TS-1: [FR1]
  TS-2: [NFR1]
implementation_path: /absolute/.../IMPLEMENTATION.md
spec_path: /absolute/.../SPEC.md
verification_path: /absolute/.../VERIFICATION.md
```

`type: review` populates `findings` (and `review_round`); `type: verify`
populates `failed_items` instead and `review_round` does not apply.
`existing_tasks`, `next_task_id`, `verification_index` and the three
document paths (`implementation_path` / `spec_path` / `verification_path`)
are present for both source types.

The `value_inputs` component of `input_digest` (rule R1) for this worker is
`rework_source` itself — a content change to findings/failed_items requires
a fresh digest regardless of whether any file input changed.

## digest_inputs

- `SPEC.md`, `IMPLEMENTATION.md`, `VERIFICATION.md`, `workflow.yaml`
- everything under `tasks/` (existing task plans)
- `references/impl-skills.yaml`, `references/review-rules.yaml`,
  `references/license-compat.md`
- `references/templates/task-plan.md`, `skills/plan-writing/SKILL.md`
- this contract document itself

## Grouping rule

Findings are not converted 1:1 into "one task per file". Findings that
share a root cause, a contract, or an Acceptance Criterion are grouped into
one task. This reuses the normal decomposition rules
(`skills/plan-writing/SKILL.md`, "Task decomposition rules") — rework does
not define a separate splitting rule.

## Document update scope table

| Document | Update condition |
|---|---|
| `tasks/taskNNNN.md` | Always created (new task plans only) |
| `VERIFICATION.md` | Per the verification coverage rules below |
| `IMPLEMENTATION.md` | Only when a rework task introduces a new shared contract (interface, data format) with an existing task; otherwise left unchanged |
| `SPEC.md` / `REQUIREMENTS.md` | Never updated by rework-planner. A rework that requires a SPEC change instead takes the specification-change transition below |

## `write_policy`

The document update scope table above is what determines each target's
`action`, applying the shared path-level model
(`references/contracts/spec-writer-contract.md`) rather than a
rework-specific one: new `tasks/taskNNNN.md` files are new-file creation
(`allowed_write_roots: [tasks/]`, `written_artifacts` reporting each path);
`VERIFICATION.md` and `IMPLEMENTATION.md` are pre-existing files being
extended, so they must be listed in `write_policy.targets` with
`action: replace_own` (same-phase rewrite of the rework-planner's own prior
output) whenever the update condition above says they are touched, and are
absent from `targets` entirely on a run that does not touch them.

## Verification coverage rule: `payload.rework_index`

Every rework task MUST have an entry in `payload.rework_index`:

```yaml
rework_index:
  task0007:
    covered_by_existing: [TS-3]      # existing scenario IDs that already cover it
    new_scenarios: []                # newly added VERIFICATION.md scenario IDs
    rationale: "TS-3 already covers the authorization boundary; no new case needed"
```

A rework task whose `covered_by_existing` AND `new_scenarios` are **both
empty is prohibited** — every rework task must declare either existing
coverage or new scenarios (or both).

The validation script (5.11.1) performs these four checks:

1. Every rework task appears in `rework_index`.
2. Every ID in `covered_by_existing` already exists in `verification_index`.
3. Every ID in `new_scenarios` actually exists in the `VERIFICATION.md` diff
   (i.e. the scenario was really added, not merely claimed).
4. If `new_scenarios` is non-empty, the same IDs also appear in the
   `workflow_patch`'s `requirements_patch.entries.*.set.tests_append`.

Check 3 depends on a supplied baseline: it establishes "really added" only
by diffing the rework-planner's `VERIFICATION.md` against a baseline copy of
that document, so it can determine newness only when both the feature
directory and a baseline directory are supplied to the validator. Without a
baseline, newness cannot be established from the current document alone —
the rework-planner itself wrote it, so its mere presence there proves
nothing.

## `payload.shared_contract_rationale`

Whether `IMPLEMENTATION.md` needed extending is not mechanically checkable,
so the rework-planner MUST always output
`payload.shared_contract_rationale`: a summary of what was added if
`IMPLEMENTATION.md` was extended, or the reason it was not, if it was left
unchanged. This is the human-readable basis reviewers use to judge that
decision.

## Specification-change transition

If the rework-planner determines a SPEC.md change is required, it creates
**no tasks**. Instead it returns `status: needs_user_input` with
`gate_id: rework.spec-change` asking the user whether to change the
specification. If the user chooses to change the specification, the
orchestrator's follow-up sequence is fixed to these five steps:

1. Set the `create-spec` step to `needs_update`.
2. Set the `create-plan` / `implement` / `review` steps to `pending`.
3. Preserve `workflow.implement.base_commit`.
4. Record the interruption reason and the finding's `stable_id` in the
   `rework.yaml` phase-state.
5. The `develop` state machine re-enters at `create-spec`.

In batch mode, `rework.spec-change` is resolved through the classification
gate defined in `references/question-resolution.md`, which this document
does not restate. Interactive mode is unchanged: the user is asked
directly.

The question packet returned for `gate_id: rework.spec-change` names each
originating review finding's `stable_id` and the review round record path
in the question's `evidence[]` entries — the gate's origin verification
(`references/question-resolution.md`) reads them from there.

## Other conditions under which a question packet may be returned

Outside the specification-change transition, the rework-planner returns a
`question_packet` only under these three conditions:

1. Mutually exclusive fix approaches remain for the same finding.
2. A requirement exclusion or a license change is required.
3. The review finding alone is not enough to make the Acceptance Criteria
   objectively verifiable.

## Scope & concurrency assumption

During dispatch, only the orchestrator and the dispatched worker may create,
modify or delete files in the integration worktree (design-input.md
5.11.3); this assumption applies for the interval from scope-snapshot
capture through scope verification, and is not a permanent constraint on
the plugin as a whole.
