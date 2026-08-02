# Create-plan Phase Protocol (em-workflow)

Read and executed inline by the `/em-workflow:develop` skill when the
`create-plan` workflow step is pending. Renders design-input.md 5.8. The
orchestrator is the only writer of `workflow.yaml`, phase-state, and every
commit in this phase; `implementation-planner` runs as a `Task`-dispatched
worker that proposes a workflow patch instead of writing `workflow.yaml`
itself.

This document does not restate the shapes it builds on — it cites them:

- Question packet / answer object shape: `references/question-packet-schema.md`.
- Question deduplication, priority, and batch resolution: `references/question-resolution.md`.
- `phase-state/create-plan.yaml` schema, resume rules, exit-4 recovery:
  `references/phase-state.md`.
- `implementation-planner`'s input and output contract:
  `references/contracts/planner-contract.md`.
- Workflow patch structure and its sixteen application rules:
  `references/workflow-patch.md`.
- `input_digest` (rule R1) and `completed_at_commit` (rule R2):
  design-input.md 5.0.
- The clean-worktree precondition and the post-dispatch scope comparison:
  `references/phases/create-spec-phase.md` ("Scope verification") —
  identical here, so it is not repeated in this document.

## 1. Purpose and ownership

- **implementation-planner**: analyzes SPEC.md / REQUIREMENTS.md / DESIGN.md
  and produces IMPLEMENTATION.md, VERIFICATION.md, per-task plans, and a
  proposed workflow patch (`tasks_patch` / `requirements_patch` /
  `step_patches` / `preserve`). Writes no `workflow.yaml` field directly.
- **Orchestrator**: the question loop, patch validation and application,
  `workflow.yaml`, and every commit.

## 2. Preconditions

- The `create-spec` step is `completed`.
- The `design` step is `completed` or `skipped`.
- REQUIREMENTS.md and SPEC.md exist; DESIGN.md is additionally required when
  `design` is `completed`.
- `workflow.yaml`'s `requirements` agree with SPEC.md's FR/NFR set.
- **The integration worktree must be clean before dispatch** — see
  `references/phases/create-spec-phase.md` ("Scope verification",
  design-input.md 5.11.3). Not clean → abort without dispatching, and
  report the offending paths.
- **`project.design_system`'s cross-product check must pass**
  (design-input.md 5.4.5): the combination of `kind` and whether
  `design-system/tokens.yaml` / `tokens.html` actually exist on disk must be
  one of the design's permitted combinations, not one of its two
  inconsistent cases (`kind: none` with tokens actually present, or
  `kind: em_workflow` with `tokens.yaml` absent but `tokens.html` present).

  If the cross-product check finds an inconsistency, the planner is **not**
  dispatched. Instead the orchestrator runs the reclassification gate
  (design-input.md 5.4.5, `gate_id: design-system.reclassify`): re-detect
  design-system candidates via `requirements-analyst` with `analysis_mode:
  design_system_detection`, resolve `kind` and `paths` again (interactive:
  ask the user; batch: `references/batch-policies.yaml`'s
  `design-system.reclassify` entry), and commit the updated
  `project.design_system` to `workflow.yaml`, **without changing the
  `create-plan` step's status** — after that commit lands, the orchestrator
  restarts from these preconditions, re-reading `workflow.yaml` and
  re-checking the cross-product table before deciding whether to dispatch
  the planner.

## 3. Reconcile on entry

Apply the Resume decision table in `references/phase-state.md`: integration
branch/worktree, `workflow.yaml`'s `create-plan` step status,
`phase-state/create-plan.yaml`, the recomputed `input_digest` against the
phase-state's `last_input_digest`, the artifact bodies against their
recorded digests, and whether the proposed patch is already applied — in
that order, never from memory.

## 4. Planner dispatch

Dispatch `implementation-planner` with:

- `input_digest` (design-input.md 5.0 R1), computed from
  `references/contracts/planner-contract.md`'s `digest_inputs`.
- A `workflow.yaml` snapshot.
- The source documents: SPEC.md, REQUIREMENTS.md, and DESIGN.md when
  present.
- Prior answers already recorded in `phase-state/create-plan.yaml`.
- `write_policy` for the artifacts it may write.
- The registry paths it must consult:
  `references/impl-skills.yaml`, `references/review-rules.yaml`,
  `references/license-compat.md`, `references/workflow-schema.md`,
  `references/templates/task-plan.md`.

## 5. Question loop

Blocking questions raised by the planner fall into these categories: TBD
resolution, license conflict, an existing file the plan would touch, and
unresolved DESIGN.md open items. Only `blocking: true` questions gate
progress (`references/question-packet-schema.md`).

## 6. Packet normalization and Ask

Follow the same common rules as create-spec —
`references/question-resolution.md`'s deduplication order, priority sort,
and presentation limits. Not restated here.

## 7. Planner completion output

On `status: completed`, the planner's payload carries: the written
artifacts (IMPLEMENTATION.md, VERIFICATION.md, `tasks/*.md`), the task
index, and the proposed workflow patch — `tasks_patch`,
`requirements_patch`, `step_patches`, and `preserve`
(`references/workflow-patch.md`).

## 8. Validation

The seven validation layers defined in design-input.md 5.11.2 (rendered by
`scripts/validate-worker-output.py`) — not restated here.

## 9. Planning invariants (machine-checked)

The validation script mechanically checks:

- Every task plan has Acceptance Criteria.
- A task's `files` and its task plan's Files section agree as a union.
- `skills` / `domains` / `complexity` match their registered vocabularies.
- Every requirement ID referenced anywhere already exists in
  `workflow.yaml`.
- Task/test mapping references resolve consistently.
- Shared contracts between parallel tasks are documented in
  IMPLEMENTATION.md.
- No `excluded` or `tbd` requirement has a task assigned to it.
- When `design` is `completed`, VERIFICATION.md includes a manual visual
  comparison step.

## 10. Atomic patch application

1. Validate the proposed patch against `references/workflow-patch.md`'s
   application rules (staleness, `expected` matches, operation-specific
   permission conditions, vocabulary checks, mandatory `preserve`).
2. Apply it as a single unit and write `workflow.yaml` with exactly one
   Write call — no partial or incremental writes
   (`references/workflow-patch.md`'s application rule 15).
3. Commit following rule R2's ordering: the artifact commit first, then the
   `status: completed` / `completed_at_commit` commit.

## 11. Completion or failure

- `create-plan` becomes `completed` only once the patch above has been
  applied and committed successfully.
- If the planner's artifacts exist but the patch has not yet been applied
  (the run was interrupted between artifact validation and patch
  application), this is **not** a failure — it is treated as a resumable
  partial completion. The next entry into this phase resumes at section 3
  (Reconcile on entry), applying the pending patch per
  `references/phase-state.md`'s Resume decision table
  (`applying_patch`, not yet applied).
