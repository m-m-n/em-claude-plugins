# Workflow Patch Contract (em-workflow SSOT)

The restricted format through which workers propose `workflow.yaml` changes,
and the rules that govern its atomic application. Renders design-input.md
5.5. This is the ONLY channel a worker uses to request a `workflow.yaml`
change — workers never write the file directly (`workflow-schema.md`, Write
ownership).

## Why not generic JSON Patch

Generic JSON Patch (RFC 6902) is not adopted: a worker able to write an
arbitrary JSON Pointer breaks the state machine's ownership boundary, and
array-index addressing is fragile against step reordering. This contract
instead exposes two closed operations, each with a fixed shape the
orchestrator can validate mechanically before applying anything.

## Common fields

| Field | Required | Content |
|---|---|---|
| `schema_version` | yes | `1` |
| `patch_id` | yes | `^[a-z][a-z0-9-]*-p[0-9]{4}$` |
| `base_input_digest` | yes | the `input_digest` (rule R1) the patch was generated against — the staleness anchor for the input side |
| `base_workflow_blob` | yes | the `workflow.yaml` blob hash at generation time — the staleness anchor for the state side |
| `operation` | yes | `replace_planning` \| `append_rework` |
| `tasks_patch` | depends on `operation` | 5.5.1 below |
| `requirements_patch` | no | 5.5.2 below |
| `step_patches` | yes | 5.5.3 below (array) |
| `preserve` | yes | 5.5.4 below |

## Operation / mode / target / issuer matrix

| operation | `tasks_patch.mode` | `step_patches` target | issuer |
|---|---|---|---|
| `replace_planning` | `replace_all` | `create-plan` only | implementation-planner |
| `append_rework` | `append` | `implement` / `review` / `verify` | rework-planner |

`project_patch` and `review_patch` do not exist as patch fields. The
`project` block and the review summary block (including `needs_rework`) are
updated directly by the orchestrator — no worker patch may target them.

## `tasks_patch`

```yaml
tasks_patch:
  mode: replace_all              # replace_all | append
  expected_next_task_id: task0007   # append only; mandatory
  entries:
    task0001:
      title: user registration API
      plan: tasks/task0001.md
      files: [src/api/register.go, src/api/register_test.go]
      skills: [backend-impl]
      domains: [input-handling, api-contract]
      complexity: medium
      requirements: [FR1, NFR1]
      initial_status: pending
      provenance:                # append only; mandatory
        source: review           # review | verify
        source_ids: [abc123]
        review_round: 2
```

A task entry is upserted atomically — never partial. `workflow-schema.md`
requires `files` / `skills` / `domains` / `complexity` / `requirements` on
every task entry, so a partial apply must never leave that mandatory set
incomplete.

`tasks_patch.carried_task_ids` (a list of `taskNNNN` strings) is present
only on a re-planning `replace_all` (Re-planning task-id allocation,
below): it is empty or absent on the Initial-planning path and on
`append`. `carried_task_ids` and `entries` are disjoint — a carried id's
body is never re-supplied under `entries`.

### `replace_all` permission conditions

`replace_all` is permitted through exactly two paths; a patch matching
neither is rejected:

- **Initial-planning path** — the `create-plan` step is `pending` (first
  planning pass), permitted only when:
  - `tasks` is empty, OR every existing task's `status` is `pending`
- **Re-planning path** — an explicit re-plan (e.g. the SPEC-change
  transition): permitted regardless of task status, including existing
  `merged` tasks. Either of two states satisfies this path:
  - the `create-plan` step is `needs_update`, OR
  - `create-plan` reads `pending` on a re-entry recognizable as having come
    through a `create-spec: needs_update` cycle — the signal is a
    `spec_change` record (`references/phase-state.md`) carrying an
    **unspent re-planning authorization** together with
    `workflow.implement.base_commit` already being set. The record is read
    from `{feature-dir}/phase-state/rework.yaml`, or from a `--phase-state`
    mapping whose own `phase` is `rework` (an equivalent source for a
    caller that already has that file open) — either source's mapping must
    also carry a `feature` matching the workflow's `feature`. An unspent
    re-planning authorization means the record carries `reason`,
    `finding_stable_id` and `recorded_at_commit` (all non-empty), carries
    `replan_authorized` as a boolean, and `replan_authorized` is `true` —
    a record whose authorization is already spent (`replan_authorized:
    false`) is not a standing permission. `consumed`'s value plays no part
    in this decision (`references/phase-state.md`'s `spec_change` flag
    pair). Any one of these conditions missing means this is not the
    second case: the invocation falls back to the Initial-planning path's
    rule (fail-closed — a narrower invocation never widens what
    `replace_all` permits). The SPEC-change transition
    (`references/rework-task-synthesis.md` Section 10) sets `create-plan`
    to `pending`, not `needs_update` — this second case is the state that
    transition actually produces, which is why the first case alone does
    not cover it.

  A `replace_all` reaching either case of this path after implementation
  has already produced `merged` tasks is the intended flow, not an
  accident.

  On this path, `workflow.implement.base_commit` appears in the patch's
  `preserve` list. This does not contradict the rework invariant that an
  `append_rework` patch never changes `base_commit` (see Mandatory
  `preserve` per operation, below) — the two state the same fact about
  `base_commit` survival from different sides of the SPEC-change /
  implementation boundary.

A `replace_all` received while any task is `in_progress` or `failed` is a
protocol error on BOTH paths above. Neither this protocol-error rule nor
the Initial-planning path's floor condition above changes as a result of
the Re-planning path's widening.

### Re-planning task-id allocation

A `replace_all` re-planning pass allocates its new task ids continuing
ABOVE the highest `taskNNNN` id the feature has ever registered. A task id
already used by any task — retired or not — is never re-issued to a
different task, on either case of the Re-planning path above.

Because `replace_all` replaces `tasks` wholesale, a re-planning pass
declares two disjoint sets rather than re-declaring registered ids as
`entries`:

- `tasks_patch.carried_task_ids` — every task id already registered in the
  `workflow.yaml` the patch is applied to. Each carried id's record is
  copied from that `workflow.yaml` **verbatim** — `title`, `plan`, `files`,
  `skills`, `domains`, `complexity`, `requirements`, `status`, `branch`,
  `notes` — and the patch supplies no body for it: a carried id must not
  also be a key of `tasks_patch.entries`.
- `tasks_patch.entries` — only task ids NOT yet registered in that
  `workflow.yaml`. Every field of an entry (including `initial_status:
  pending`, application rule 12) is worker-supplied and validated exactly as
  on the Initial-planning path.

Omitting a registered id from `carried_task_ids`, naming an unregistered id
in `carried_task_ids`, or naming a registered id under `entries`, is
rejected. Because a carried id's record is copied verbatim, a `merged` task
keeps its `status`, its `branch` and its `files` across the patch without
either field entering the `preserve` vocabulary.

The high-water mark is `max(carried_task_ids ∪ entries)`, still readable
directly from the `workflow.yaml` the patch is applied to — any genuinely
new task in `entries` is numbered above it.

### `append` requirements

- `expected_next_task_id` is mandatory and must equal the actual next
  `taskNNNN` in sequence.
- Every entry under `append` carries a `provenance` block: `source`
  (`review` | `verify`), `source_ids`, and `review_round`.
- `append` never overwrites an existing task ID (5.5.5 rule 4).

## `requirements_patch`

```yaml
requirements_patch:
  mode: merge_entries
  entries:
    FR3:
      expected: { tasks_contains: [task0003] }
      set: { tasks_append: [task0007], tests_append: [TS-9] }
```

The only operations permitted under `set` are the `_append` forms of
`tasks` and `tests`, and direct assignment of `status`, `tbd_reason`, and
`excluded_reason`. No other field of a requirements entry is patchable.

## `step_patches` (array)

`workflow` is an array, so a step is addressed by `step_id` — never by array
index (index addressing is fragile against step reordering). Virtual fields
(e.g. an `implement_status` shortcut) do not exist.

```yaml
step_patches:
  - step_id: implement
    expected: { status: completed }
    set: { status: pending }
  - step_id: review
    expected: { status: in_progress }
    set: { status: pending }
```

`status` is the only field `set` may touch. `base_commit` and
`completed_at_commit` are NOT worker-settable — rule R2 reserves them to the
orchestrator.

## `preserve` and the mandatory preserve sets

The list of logical paths whose value must be unchanged after the patch is
applied. Paths are dot-separated logical paths; array indices are never
used.

### Permitted vocabulary

- `workflow.implement.base_commit`
- `workflow.<step_id>.completed_at_commit`
- `project.license`
- `tasks.<task_id>.status`
- `tasks.<task_id>.branch`

No path outside this vocabulary may appear in a `preserve` list.

### Mandatory `preserve` per operation

Applying a patch that omits its operation's mandatory preserve set is
rejected.

| operation | mandatory `preserve` |
|---|---|
| `append_rework` | `workflow.implement.base_commit` |
| `replace_planning` | `workflow.implement.base_commit`, mandatory on the Re-planning path; the Initial-planning path has no `implement` base commit yet, so nothing is mandatory there |

`append_rework` also needs the status of every pre-existing task to survive
the patch. Listing `tasks.<task_id>.status` for each ID in `existing_tasks`
is RECOMMENDED, not mandatory — rule 4 below already forbids `append` from
overwriting an existing task ID, so the recommendation is a belt-and-braces
check rather than the only thing preventing the overwrite.

A re-planning `replace_all`'s carried task ids (Re-planning task-id
allocation, above) need no `tasks.<task_id>.status` / `tasks.<task_id>.branch`
entry in `preserve` to survive the patch — the carry-over declaration
guarantees it structurally. A patch MAY still list them; because the carried
record is copied verbatim, the invariance check (rule 14) holds.

## Application rules (in order)

All seventeen rules apply, in order, to every patch:

1. Reject unless `base_input_digest` matches the digest recomputed from the
   current input (rule R1).
2. Reject unless `base_workflow_blob` matches the current `workflow.yaml`
   blob hash.
3. Reject unless every `expected` value matches the corresponding current
   value.
4. `append` must not overwrite an existing task ID, and
   `expected_next_task_id` must match the actual next task number.
5. `replace_all` is permitted only when its 5.5.1 permission conditions are
   met.
6. Task IDs must match `^task[0-9]+$`.
7. `files` entries must be project-relative; absolute paths, `..`, and NUL
   are rejected.
8. `skills` values must be registered in `references/impl-skills.yaml`.
9. `domains` values must be in the vocabulary of `references/review-rules.yaml`
   (see Domains vocabulary SSOT below).
10. `complexity` must be one of `low` / `medium` / `high`.
11. `requirements` entries must be IDs that already exist in `workflow.yaml`.
12. Every entry under `tasks_patch.entries` must set `initial_status` to
    `pending`. This rule applies to `entries` only — a `carried_task_ids`
    id carries no entry at all (Re-planning task-id allocation, above).
13. The operation's mandatory `preserve` set must be present.
14. Every path listed in `preserve` must hold the same value before and
    after the patch.
15. After all validations succeed, the patch is applied in memory as a
    single unit and written out with exactly one Write to `workflow.yaml`
    (single-write application — no partial or incremental writes).
16. The commit sequence follows rule R2: the artifact commit first, then the
    status-update commit.
17. A re-planning `replace_all` must carry `tasks_patch.carried_task_ids`
    listing every task id already registered in the current `workflow.yaml`,
    and `tasks_patch.entries` must name only ids not registered there
    (Re-planning task-id allocation, above); omitting a registered id from
    `carried_task_ids`, or naming a registered id in `entries`, is rejected.

## Ownership boundary

`project` and the review summary block (including `needs_rework`) are
orchestrator-updated only. No operation, mode, or field of this contract
targets them — they are absent from every worker patch by construction, not
by convention workers are expected to honor voluntarily.

## Domains vocabulary SSOT

The SSOT for the `domains` vocabulary is `references/review-rules.yaml`.
This contract does not restate the vocabulary; it only requires that
`domains` values used in a `tasks_patch` entry are members of that file's
vocabulary (rule 9 above).
