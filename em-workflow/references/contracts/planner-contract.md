# implementation-planner Contract (em-workflow SSOT)

Input/output contract for the `implementation-planner` worker. Renders
design-input.md 5.4.3 and the `implementation-planner` row of 5.0 R1. This
document adds only planner-specific content; the dispatch envelope shape
(input fields, output fields, the six `status` values and their
exclusivity constraints, `mode_echo`, `written_artifacts` reporting, the
read-restriction rule) is defined once in
`references/contracts/worker-envelope.md` and is not restated here. The
question packet / answer shape is defined once in
`references/question-packet-schema.md` and is not restated here.

## Responsibility

Analysis, `IMPLEMENTATION.md`, task plans (`tasks/taskNNNN.md`) and
`VERIFICATION.md`. The planner never calls AskUserQuestion itself — that
tool has exactly one caller, the orchestrator (design-input.md 4.1) — and
never writes `workflow.yaml` directly (workers treat it read-only; the
planner's only channel for a `workflow.yaml` change is the `workflow_patch`
it returns, per `references/workflow-patch.md`). The planner MAY still
return `status: needs_user_input` with a `question_packet` (see "Question
packet bundling rule" below) — "no user questions" means the planner does
not perform the asking, not that it never has anything to ask.

## Additional input: `planning_inputs`

```yaml
planning_inputs:
  requirements_path: /absolute/.../REQUIREMENTS.md
  spec_path: /absolute/.../SPEC.md
  design_path: /absolute/.../DESIGN.md        # null if design step was skipped
  lessons_path: /absolute/.../LESSONS.md      # null if the project has none
  impl_skills_registry: /absolute/.../references/impl-skills.yaml
  review_rules: /absolute/.../references/review-rules.yaml
  license_compat: /absolute/.../references/license-compat.md
```

`write_policy` is also part of the input, in the common path-level form
defined by `references/contracts/spec-writer-contract.md` (the write-policy
model's owning document — the six actions, the `targets` /
`allowed_write_roots` split, `expect_digest` requirements). This contract
does not restate that model. The planner's `write_policy.targets` cover
`IMPLEMENTATION.md` and `VERIFICATION.md` (action `create` on a first pass,
`replace_own` on a same-phase rewrite); task plan files are new per task and
so are governed by `allowed_write_roots` (`tasks/`) with `written_artifacts`
reporting each path created.

## Question packet bundling rule

Questions covering TBD resolution, license conflict, and existing-file
disposition MUST be bundled into a single `question_packet` (one
`needs_user_input` iteration), not split across several. The one exception:
if license-candidate discovery depends on the answer to a TBD question,
those two MAY be split across separate iterations, because the second
question cannot be formed until the first is answered.

## digest_inputs

Per 5.0 R1, the orchestrator builds `input_digest` from exactly the set this
contract declares — the planner does not expand it:

- `REQUIREMENTS.md`, `SPEC.md`, `DESIGN.md`, `LESSONS.md`, `workflow.yaml`
- `references/impl-skills.yaml`, `references/review-rules.yaml`,
  `references/license-compat.md`, `references/workflow-schema.md`
- `references/templates/task-plan.md`, `skills/plan-writing/SKILL.md`
- `design-system/tokens.yaml` (design system tokens — see exception below),
  or the project-native design system's own files
- the existing `IMPLEMENTATION.md` / `VERIFICATION.md` / everything under
  `tasks/` (so a re-plan detects drift against what is already written)
- this contract document itself (a contract change alters the planner's
  output shape)

There are no `value_inputs` for the planner (`task_description` is not part
of its input; that belongs to requirements-analyst).

**`project.design_system.kind` exception** (design-input.md 5.4.5): when
`kind: project_native`, `design-system/tokens.yaml` and
`design-system/tokens.html` are excluded from `digest_inputs` — the planner
must not use leftover em-workflow tokens as a judgment input when the
project has its own design system. The full `kind` × token-existence
cross-product this exception is drawn from is owned by
`references/contracts/designer-contract.md`; this contract only states the
consequence for the planner's own `digest_inputs`.

## `completed` payload

```yaml
written_artifacts: [...]        # IMPLEMENTATION.md, VERIFICATION.md, tasks/taskNNNN.md — each with sha256
workflow_patch: {...}           # operation: replace_planning — see references/workflow-patch.md
payload:
  task_index:
    task0001: { title: ..., complexity: medium, domains: [...], requirements: [FR1] }
```

The `completed` output is this triple: `written_artifacts`, `workflow_patch`
and `payload.task_index`. The `workflow_patch` the planner returns uses
`operation: replace_planning` (bound to `tasks_patch.mode: replace_all`,
targeting the `create-plan` step); the operation's permission conditions,
the `tasks_patch` entry shape, and the sixteen application rules are owned
by `references/workflow-patch.md` and are not restated here.

## Prohibited fields

The planner MUST NOT set: `branch`, `notes`, any running/in-progress
`status` value, or `completed_at_commit` on any task or step. These are
orchestrator-owned — `completed_at_commit` specifically is reserved to the
orchestrator by rule R2 (design-input.md 5.0), and `references/workflow-patch.md`'s
`step_patches` contract permits only `status` as a settable field with
`base_commit` / `completed_at_commit` excluded even there.

## Task decomposition, complexity and domains vocabulary

The criteria the planner applies when splitting work into tasks (worktree
independence, size, `files` prediction as a contract, interface contracts
instead of sequencing, Acceptance Criteria, integration wiring ownership)
and the `complexity` levels (`low` / `medium` / `high`) are owned by
`skills/plan-writing/SKILL.md` ("Task decomposition rules" and "complexity
criteria" sections) and are not restated here — the planner is dispatched
with that skill loaded and follows it directly.

The `domains` vocabulary used in `tasks_patch` entries is described (not
owned) by `skills/plan-writing/SKILL.md`; its single source of truth is
`references/review-rules.yaml`, per `references/workflow-patch.md`'s
"Domains vocabulary SSOT" section and design-input.md 5.5.6.

## Scope & concurrency assumption

During dispatch, only the orchestrator and the dispatched worker may create,
modify or delete files in the integration worktree (design-input.md
5.11.3); this assumption applies for the interval from scope-snapshot
capture through scope verification, and is not a permanent constraint on
the plugin as a whole.
