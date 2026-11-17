# Threat Model: final-path-plan-binding

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md, `_correction_entries_errors` and the plan
readers of `em-workflow/scripts/validate-worker-output.py`, Step I.2.a of
`em-workflow/references/implement-phase.md` (the Control-character check and
the implementer prompt payload), section 2a of
`em-workflow/references/phases/create-plan-phase.md` and the stop point
coverage of `em-workflow/references/batch-terminal-line.md`. The tier is full.
The domains `input-handling` and `external-io` of task0001 and task0003 set the
depth to deep on both boundaries below.

The untrusted party is implementation-planner on the correction entry: it reads
repository text, returns the patch and writes the files under `tasks/` that the
validator then reads. The `tasks.{T}.plan` value of `workflow.yaml` comes from
such a patch, and the orchestrator later reads it to build the implementer's
prompt.

task0002 declares `api-contract` only; it changes a contract document and its
pins. FR6 changes how a batch run reports the FR3 stop and moves no data across
a boundary, so it has no row. The `workflow-schema.md` count that task0003
updates is a statement about write paths and moves no data either. The interval
between the Plan-path check and the implementer's own read of the plan is
outside the requirements of this feature and has no row.

## Trust Boundaries

### TB-1: Correction-entry patch to the validator
Crossing: the items of `tasks_patch.entries` (their keys and `plan` values) and
the files the planner wrote under the feature directory during the correction
dispatch, from implementation-planner to the validator that admits the patch.
Boundary files: `em-workflow/scripts/validate-worker-output.py`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The canonical text sits in a decoy plan while an unregistered `tasks/{T}.md` carries other instructions, so the canonical-text check passes on a document the implementer may not read (FR1; the attack scenario of SPEC.md US1) | TM-1 | On the correction entry, an item whose plan, after `path_segments` normalization, is not `tasks/{T}.md` while an entry of any kind exists at `tasks/{T}.md` is rejected as `path-correction-entries` naming the task and `tasks/{T}.md` | task0001 AC-1, AC-4 | VERIFICATION.md TM-1 |
| Tampering | A lookup error, a dangling symlink or a malformed task id reads as "no `tasks/{T}.md`", so the decoy plan passes (NFR2) | TM-2 | Only a lookup that reports no entry counts as absent; a dangling symlink, any other lookup outcome and a key that is not a task id count as existing | task0001 AC-4, AC-6 | VERIFICATION.md TM-2 |
| Elevation of privilege | The worker-chosen task id that builds the looked-up path reaches git or a process as an argument (NFR1) | TM-3 | The binding decision reads the working tree only and starts no process; the entries limit reaches git only through `_read_base_document` | task0001 AC-6 | VERIFICATION.md TM-3 |

### TB-2: Registered plan path to the implementer's instructions
Crossing: the `tasks.{T}.plan` value of `workflow.yaml`, written from a worker
patch, and the document it names in the integration worktree, from the
orchestrator's launch step into the trusted part of the implementer's
assignment prompt, where it selects the document the implementer follows.
Boundary files: `em-workflow/references/implement-phase.md`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The implementer is pointed at a fixed `tasks/{T}.md` while the validator checked `tasks.{T}.plan`, so the canonical-text requirement of the correction entry (feature final-path-correction-medium-fixes) misses the implementer's instruction input (FR2) | TM-4 | `task_plan_path` is resolved from `tasks.{T}.plan`; the payload holds no fixed `tasks/{T}.md` | task0003 AC-1 | VERIFICATION.md TM-4 |
| Elevation of privilege | The plan value is absolute, has a `..` segment or passes through a symlink, so the implementer follows a document outside `feature-docs/{feature}` (FR3) | TM-5 | Before any launch prompt is built, the value of every selected task must be a safe relative path, have no symlink among its components and resolve inside `feature-docs/{feature}` by realpath | task0003 AC-2 | VERIFICATION.md TM-5 |
| Tampering | A Cc character, U+2028 or U+2029 in the stored or the resolved value adds a line to the trusted part of the assignment prompt (FR3) | TM-6 | The stored value and the resolved absolute path are rejected when either holds such a character | task0003 AC-2 | VERIFICATION.md TM-6 |
| Tampering | A failing value is repaired, falls back to `tasks/{T}.md`, or the launch goes on for the clean tasks, so an unchecked document still reaches an implementer (FR3) | TM-7 | Any failure aborts the phase: the offending task IDs are reported, no launch prompt is built for any selected task, no implementer is launched, nothing is sanitized and nothing falls back, and `implement` is written `failed` with `failed_kind` `decision` in one commit | task0003 AC-3 | VERIFICATION.md TM-7 |
