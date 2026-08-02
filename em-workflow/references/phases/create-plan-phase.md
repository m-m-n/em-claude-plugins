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
  inconsistent cases. **These two cases are not the same branch** — each
  routes to a different outcome, and only one of them opens a gate:

  - **`kind: none` with either token file actually present**: the planner
    is **not** dispatched. Instead the orchestrator runs the
    reclassification gate (design-input.md 5.4.5, `gate_id:
    design-system.reclassify`): re-detect design-system candidates via
    `requirements-analyst` with `analysis_mode: design_system_detection`,
    resolve `kind` and `paths` again (interactive: ask the user; batch:
    `references/batch-policies.yaml`'s `design-system.reclassify` entry),
    and commit the updated `project.design_system` to `workflow.yaml`,
    **without changing the `create-plan` step's status** — after that
    commit lands, the orchestrator restarts from these preconditions,
    re-reading `workflow.yaml` and re-checking the cross-product table
    before deciding whether to dispatch the planner.
  - **`kind: em_workflow` with `design-system/tokens.yaml` absent and
    `tokens.html` present**: the planner is **not** dispatched, and the
    reclassification gate above is **not** run for this case — recomputing
    `kind` from candidates cannot restore a missing source file, so
    settling `kind` again through that gate would leave `tokens.yaml`
    still absent and re-enter this exact same inconsistency the next time
    the cross-product table is checked, never terminating. Instead the
    orchestrator **aborts create-plan dispatch outright**: it reports the
    offending paths (`design-system/tokens.yaml` missing,
    `design-system/tokens.html` present) and waits for the user to either
    delete the stale `tokens.html` or restore `tokens.yaml` before
    re-entering this phase.

## 3. Reconcile on entry

Apply the Resume decision table in `references/phase-state.md`: integration
branch/worktree, `workflow.yaml`'s `create-plan` step status,
`phase-state/create-plan.yaml`, the recomputed `input_digest` against the
phase-state's `last_input_digest`, the artifact bodies against their
recorded digests, and whether the proposed patch is already applied — in
that order, never from memory.

## 4. Planner dispatch

`Task(subagent_type="em-workflow:implementation-planner")`, with:

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

The seven validation layers defined in design-input.md 5.11.2 — not
restated in full here, but the split between them matters for section 9
below: `scripts/validate-worker-output.py` implements layers 1 (syntax), 2
(structure), 3 (revision) and 6 (cross-artifact) — the script's own
docstring states this. Layers 4 (scope verification), 5 (artifact
verification) and 7 (state-machine postconditions) are **deliberately not
implemented in the script**; they are the orchestrator's own responsibility
(Bash), run outside it. A check belonging to a layer neither side
implements does not happen at all.

## 9. Planning invariants — the validator-implemented subset, and human review for the rest

Of the invariants a planning result could in principle be checked against,
`scripts/validate-worker-output.py` mechanically implements only the
following. This list is restricted to what the script actually does, not
to every invariant that would be desirable:

- Every task plan has a non-empty Acceptance Criteria section.
- A task's `files` and its task plan's Files section agree as a union.
- `skills` / `domains` / `complexity` match their registered vocabularies —
  **only when `--registries` is supplied**; the check silently does not run
  if it is omitted, it does not fail.
- A task's declared `requirements` already exist in `workflow.yaml` —
  **only when `--workflow` is supplied**; likewise silently skipped, not
  failed, when omitted.
- Shared contracts between parallel tasks are documented in
  IMPLEMENTATION.md, checked as: whenever more than one task declares the
  same file in `files`, IMPLEMENTATION.md must contain a `## Shared
  Components` section. This is a deliberate approximation of "a shared
  contract exists where one is needed" (same-file overlap is neither
  necessary nor sufficient for that), not a defect to fix in this task.

The following are named as planning invariants but are **not implemented
by the script** — they remain human review only, with no automated gate
blocking on them:

- Task/test mapping references resolve consistently outside the rework
  path (the script's rework-index coverage check exists, but it applies
  only to `rework-planner` output, not to a fresh `implementation-planner`
  patch).
- No `excluded` or `tbd` requirement has a task assigned to it.
- When `design` is `completed`, VERIFICATION.md includes a manual visual
  comparison step.

**Canonical validator invocation** for an `implementation-planner` result,
covering every invariant above that the script can check:

```
python3 scripts/validate-worker-output.py \
    --kind worker-result \
    --worker implementation-planner \
    --input {worker-output.json} \
    --input-envelope {dispatch-input.json} \
    --workflow {workflow.yaml} \
    --registries {references-dir} \
    --feature-dir {feature-docs/{feature}} \
    --digest-source {digest-source.json} \
    --dry-run-apply
```

`--input-envelope` is mandatory for `--kind worker-result` — the script
exits 2 without it. `--workflow`, `--registries` and `--feature-dir` are
optional in the script's own argument parser, but each one that is omitted
here silently narrows validation rather than failing loudly: dropping
`--workflow` skips the requirement-existence check, dropping `--registries`
skips the vocabulary check, and dropping `--feature-dir` skips the
Acceptance-Criteria, files-union and Shared-Components checks together
(all three are read from the task plan and IMPLEMENTATION.md files under
`--feature-dir`). Running anything less than the invocation above is a
coverage regression, not a smaller valid invocation.

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
