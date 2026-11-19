# Threat Model: plan-path-backslash-binding

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md, Step I.2.a of
`em-workflow/references/implement-phase.md` (the `task_plan_path` line of the
prompt payload and the Plan-path check), section 2a of
`em-workflow/references/phases/create-plan-phase.md`, and `path_segments`,
`is_safe_relative_path`, `_resolve_contained_relative_path` and
`_plan_is_bound_to_task_md` of `em-workflow/scripts/validate-worker-output.py`.
The tier is full. The domains `input-handling` and `external-io` of task0001
set the depth of the boundary below to deep.

The untrusted party is a worker whose patch sets `tasks.{T}.plan` and that can
write files under `feature-docs/{feature}/tasks/` (implementation-planner on
the correction entry). The validator binds every spelling that `path_segments`
normalizes to `tasks/{T}.md`, the backslash spellings included (FR4, SPEC.md
A2). The threats below arise only where the implement phase resolves the same
stored value differently from the validator.

task0002 declares `input-handling` but only adds a test module that exercises
this boundary against the unchanged validator. It implements no part of the
boundary, so its file is in no `Boundary files` line. The validator is listed
as a boundary file because its `path_segments` is the normalization the
documents cite; FR4 keeps it unchanged. A backslash spelling written without
malice reaches a nonexistent path through the same divergence, and TM-1 covers
it. No rejection rule for non-canonical spellings is added (SPEC.md A1), so
none is modeled. The interval between the Plan-path check and the
implementer's own read of the plan is outside the requirements of this feature
and has no row.

## Trust Boundaries

### TB-1: Registered plan value to the implementer's instruction input
Crossing: the `tasks.{T}.plan` value of `workflow.yaml`, written from a worker
patch, and the files under `feature-docs/{feature}/tasks/` that the same worker
can write, from the orchestrator's launch step (Step I.2.a) into the trusted
`task_plan_path` field of the implementer's assignment prompt, where it selects
the document the implementer follows as instructions.
Boundary files: `em-workflow/references/implement-phase.md`, `em-workflow/references/phases/create-plan-phase.md`, `em-workflow/scripts/validate-worker-output.py`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A plan value spelled `tasks/\task0003.md` or `tasks\task0003.md` is bound to `tasks/task0003.md` by the validator, which reads the `path_segments` normalized path, while the payload joins the stored string as-is; the implementer then follows a decoy literally named `\task0003.md` that never passed validation, so the canonical-text enforcement of the correction entry (feature final-path-plan-binding, its TM-1 and TM-4) misses the implementer's instruction input (FR1, FR3) | TM-1 | `task_plan_path` is the integration worktree's `feature-docs/{feature}/` joined with the segments that `path_segments` returns for the stored value, which is the path `_resolve_contained_relative_path` reads; section 2a states the same resolution; the stored string is never joined as-is | task0001 AC-1, AC-4; task0002 AC-1, AC-2, AC-3 | VERIFICATION.md TM-1 |
| Elevation of privilege | Plan-path check rules 2 and 3 judge the stored string joined as-is while the payload carries the normalized path, so a symlink component or an out-of-tree realpath on the path actually handed to the implementer is never examined, and the implementer can be pointed outside `feature-docs/{feature}` (FR2) | TM-2 | Rules 2 and 3 judge the same normalized joined path that `task_plan_path` carries; rules 1 and 4 are unchanged | task0001 AC-2 | VERIFICATION.md TM-2 |
