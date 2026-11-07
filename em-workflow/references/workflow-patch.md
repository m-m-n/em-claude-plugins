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

`tasks_patch.path_corrections` is present only on a `replace_planning` patch
that corrects the final path of an existing plan (`## Final-path correction`,
below): a non-empty list of mappings with exactly `task_id`, `old_path` and
`new_path`, every `task_id` also listed in `carried_task_ids`. It is absent
from every other patch.

`tasks_patch.feature_docs_removals` is present only on a `replace_planning`
patch that removes feature-docs paths from an existing plan
(`## Feature-docs correction`, below): a non-empty list of mappings with
exactly `task_id` and `path`, every `task_id` also listed in
`carried_task_ids`. It is absent from every other patch, and it is never
together with `path_corrections`.

### `replace_all` permission conditions

`replace_all` is permitted through exactly two paths, and through the one
further state that `## Final-path correction` (below) admits for a patch
carrying `tasks_patch.path_corrections` and that `## Feature-docs correction`
(below) admits for a patch carrying `tasks_patch.feature_docs_removals`; a
patch matching none of these is rejected:

- **Initial-planning path** — the `create-plan` step is `pending` (first
  planning pass), permitted only when:
  - `tasks` is empty, OR every existing task's `status` is `pending`
- **Re-planning path** — an explicit re-plan (e.g. the SPEC-change
  transition, or `skills/develop/SKILL.md`'s tier-upgrade procedure —
  the record it writes before setting `create-plan` to `needs_update` is
  an authorized `spec_change` record on the same terms as the SPEC-change
  transition's own): permitted regardless of task status, including
  existing `merged` tasks. Either of two states satisfies this path:
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
    re-planning authorization means the record carries `reason`, the
    origin pair `origin_kind` and `origin_id`, and `recorded_at_commit`
    (all non-empty), carries `replan_authorized` as a boolean, and
    `replan_authorized` is `true` — a record whose authorization is
    already spent (`replan_authorized: false`) is not a standing
    permission. The origin pair's own meaning is
    `references/rework-task-synthesis.md` Invariant 6's — cited here, not
    restated. `consumed`'s value plays no part in this decision
    (`references/phase-state.md`'s `spec_change` flag pair). Any one of
    these conditions missing means this is not the
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
the Re-planning path's widening. The correction entry of `## Final-path
correction` (below), which `## Feature-docs correction` (below) shares, is the
one state in which a `failed` task is not a protocol error, and an
`in_progress` task stays one there.

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
  `notes`, `routeback_failed_journal_line` — and the patch supplies no body
  for it: a carried id must not also be a key of `tasks_patch.entries`.
- `tasks_patch.entries` — only task ids NOT yet registered in that
  `workflow.yaml`. Every field of an entry (including `initial_status:
  pending`, application rule 12) is worker-supplied and validated exactly as
  on the Initial-planning path.

Omitting a registered id from `carried_task_ids`, naming an unregistered id
in `carried_task_ids`, or naming a registered id under `entries`, is
rejected. Because a carried id's record is copied verbatim, a `merged` task
keeps its `status`, its `branch` and its `files` across the patch without
either field entering the `preserve` vocabulary.

The two exceptions to this verbatim copy are the final-path correction
(`## Final-path correction`, below) and the feature-docs correction
(`## Feature-docs correction`, below).

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
`tasks` and `tests`, the `tests_replace` replacement of scenario IDs in
`tests`, and direct assignment of `status`, `tbd_reason`, and
`excluded_reason`. No other field of a requirements entry is patchable.

### Tests replacement

```yaml
requirements_patch:
  mode: merge_entries
  entries:
    FR3:
      expected: { tests_contains: [TS3] }
      set: { tests_replace: [{ from: TS3, to: TS-3 }] }
```

`tests_replace` replaces scenario IDs in the requirement's `tests`. Its value
is a non-empty list of pairs, each a mapping with `from` (the old ID) and
`to` (the new ID), both non-empty strings, `from` different from `to`, and
no `from` repeated within one requirement entry.

Within one entry no ID may appear both as a `from` and as a `to`. A chain
(`TS-1` to `TS-2` together with `TS-2` to `TS-3`) and a swap (`TS-1` to
`TS-2` together with `TS-2` to `TS-1`) are both covered: each is rejected as
malformed (code `requirements_patch`) by the structural check, whether or
not `--dry-run-apply` is given. Pairs that share a `to` (`TS1` to `X`, `TS2`
to `X`) are not affected by this rule and keep the application rule below.

The `expected` key `tests_contains` is a list of scenario IDs. Every `from`
of an entry's `tests_replace` must also be listed in that same entry's
`tests_contains`, so a replacement never skips the expectation check; an
entry that replaces an ID it does not list there is rejected as malformed.
Application rule 3 below covers `tests_contains` like every other `expected`
value: when any listed ID is absent from the requirement's current `tests`,
the patch is rejected with `expected-mismatch`.

Applying an entry replaces each `from` by its `to` at the same position in
`tests`; when `to` is already present, `from` is removed and `to` is not
duplicated. Within one entry, `tests_replace` is applied before
`tests_append`.

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

All eighteen rules apply, in order, to every patch:

1. Reject unless `base_input_digest` matches the digest recomputed from the
   current input (rule R1). The orchestrator builds the recomputed
   `digest_source` under the self-write rule of
   `references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
   comparison timing".
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
18. Once a re-planning `replace_all` (Re-planning path) has been applied,
    the orchestrator sets that record's `spec_change.replan_authorized` to
    `false`, in the same phase-state write that records the application
    (`references/phase-state.md`) — an authorization grounds exactly one
    re-planning pass. Does not apply to the Initial-planning path, which
    has no `spec_change` record to spend.

## Interrupted authorization-spend recovery

Rule 18's authorization-spending write is recoverable and idempotent
across an interruption between rule 15's patch write and rule 18's own
write. This procedure is not one of the numbered application rules above —
its whole effect is to recognize a patch as already applied and thereby
short-circuit rule 2, so stating it inside a list declared to apply "in
order" would contradict that ordering. It is a recovery procedure the
orchestrator runs on resume, not a rule every patch is checked against.

**Recognition.** For the patch in hand, a resumed run recognizes that this
patch has already been applied only when BOTH of the following hold:

- `references/phase-state.md` owns the already-applied determination — the
  Resume decision table's own read input "whether a patch is already
  applied", backed by the recorded per-patch entry (`patches[]`) whose
  `status` is `applied` — and that determination returns applied for this
  patch, matched on the patch's own `patch_id` against that entry's
  `patch_id`. How the determination itself is computed is
  `references/phase-state.md`'s own — cited here, not restated.
- the `spec_change` record this patch's re-planning pass was authorized
  under still stands: rework's spec-change transition has not since
  replaced it wholesale with a fresh record (`references/phase-state.md`'s
  "ID uniqueness and idempotency" — every occurrence of the transition
  replaces the record afresh).

A `base_workflow_blob` mismatch (rule 2) that the already-applied
determination above does not confirm remains an ordinary rejection under
rule 2 on its own — no authorization is ever spent on a rejected patch. No
sentence in this section makes a bare blob mismatch a recognized case on
its own; recognition depends only on the determination above.

**Idempotency.** Under the recognized case, the resumed run performs only
rule 18's write instead of treating a `base_workflow_blob` mismatch as an
ordinary rejection. If `replan_authorized` is already `false` (a prior
resumption already performed the spend), repeating the write is a no-op,
not an error: the resumed run leaves the record unchanged and reports
success. The state reached after any number of resumptions is the same as
the state reached by one uninterrupted run. Where `replan_authorized`
lives is `references/phase-state.md`'s own definition — cited here, not
restated.

## Feature-docs correction

A feature-docs correction removes feature-docs paths from the `files` of the
tasks of an existing plan. What a feature-docs path is, is defined by
`skills/plan-writing/SKILL.md`, section `## Feature-docs Files`; this document
cites that section and does not restate it. The correction is carried by
`tasks_patch.feature_docs_removals`. It is an exception to copying a carried
record verbatim (Re-planning task-id allocation, above), like
`## Final-path correction` (below), and it adds no application rule: the
eighteen rules above apply to a patch carrying it as to any other.

**Field.** `feature_docs_removals` is a non-empty list of mappings with exactly
`task_id` and `path`, on `replace_planning` only. Each `task_id` is listed in
`carried_task_ids`, each (`task_id`, `path`) pair appears once, and the field
is never together with `path_corrections`. The task a mapping's `task_id`
names is its target task. A malformed field, a `task_id` that is unknown or not
in `carried_task_ids`, a duplicate pair, use together with `path_corrections`
and use on `append_rework` are rejected as `feature-docs-removal-shape`.

**Permission states.**

| State | Result |
|---|---|
| `create-plan` is `completed` and `implement` is `failed` (the correction entry) | Admitted. The carry-over and `preserve` obligations of the Re-planning path apply. A `failed` task is permitted; an `in_progress` task stays rejected as `replace-all-not-permitted`. The limits below apply |
| The Re-planning path | Rejected, `feature-docs-removal-not-permitted` |
| The Initial-planning path | Rejected, `feature-docs-removal-not-permitted` |
| Any other state | Rejected, `feature-docs-removal-not-permitted` |

**Conditions.** All five are required; a removal that fails any condition is
not applied: the patch is rejected with that condition's code and
`workflow.yaml` is not changed. The checks read `workflow.yaml` and the
feature's journal.

- `feature-docs-removal-in-flight` — No task is in flight: no task's `status`
  is `in_progress` and no task's last journal event is `launched`.
- `feature-docs-removal-merged` — Neither the target task's `status` nor its
  last journal event is `merged`.
- `feature-docs-removal-path` — `path` is a feature-docs path and is in the
  target task's `files`.
- `feature-docs-removal-empty-files` — The target task's `files` is not empty
  once the removals for it are applied.
- `feature-docs-removal-incomplete` — After the patch, no task that is not
  `merged` holds a feature-docs path in its `files`.

**Limits.** On the correction entry, a patch carrying `feature_docs_removals`
is limited in three more fields, under the one code
`feature-docs-removal-limits`, outside the five conditions. `step_patches` is
empty, `tasks_patch.entries` is empty, and `requirements_patch` is null or has
no entries.

**Inputs.** Under `--dry-run-apply`, a patch carrying `feature_docs_removals`
needs `--workflow`, `--journal` and `--feature-dir`: the checks read
`workflow.yaml` and the feature's journal, and the plan agreement below reads
the target tasks' plans. A missing input is an execution error (exit 2), never
a pass.

**Application.** In the in-memory application, every occurrence of `path` is
removed from the target task's `files` and `notes` is set to null. Every other
field of the target and every other record is copied verbatim.

**Plan agreement.** Each target task's plan has Files sections that equal the
task's `files` after the removal, as for an entry; a plan that disagrees is
rejected as `task-plan-files-mismatch`.

**Ownership.** `implementation-planner` corrects the plan documents and
proposes the removals through `feature_docs_removals`; the orchestrator applies
the patch to `workflow.yaml`. The implementer and `rework-planner` do not.

**Restoration and ordering.** Restoring the failed feature after the patch is
applied, and the order of this correction and `## Final-path correction`, are
owned by `skills/develop/SKILL.md`'s `## Step A.6: failed からの入口`, and are
not restated here.

A `replace_all` without `feature_docs_removals` behaves as before in every
state.

## Final-path correction

A final-path correction changes the path of a file in an existing plan from a
matching name to a name that does not match. A matching name is one that
`skills/plan-writing/SKILL.md`, section `## Report Artifact Names`, defines;
this document cites that section and does not restate it. The correction is
carried by `tasks_patch.path_corrections`. It is the exception to copying a
carried record verbatim (Re-planning task-id allocation, above), and it adds
no application rule: the eighteen rules above apply to a patch carrying it as
to any other.

**Field.** `path_corrections` is a non-empty list of mappings with exactly
`task_id`, `old_path` and `new_path`, on `replace_planning` only. Each
`task_id` is listed in `carried_task_ids`, each (`task_id`, `old_path`) pair
appears once, and `new_path` differs from `old_path`. The task a mapping's
`task_id` names is its target task. A malformed field is rejected as
`path-correction-shape`.

**Permission states.**

| State | Result |
|---|---|
| `create-plan` is `completed` and `implement` is `failed` (the correction entry) | Admitted. The carry-over and `preserve` obligations of the Re-planning path apply. A `failed` task is permitted; an `in_progress` task stays rejected as `replace-all-not-permitted`. `step_patches` must be empty, else `path-correction-step-patches` |
| The Re-planning path, including re-planning entered through route back | Admitted under that path's existing rules |
| The Initial-planning path | Rejected, `path-correction-not-permitted` |

A `replace_all` without `path_corrections` behaves as before in every state.

**Conditions.** All five are required; a correction that fails any condition
is not applied: the patch is rejected with that condition's code and
`workflow.yaml` is not changed. The checks read `workflow.yaml`, the feature's
journal and the base commit. The repository is the integration worktree and
the base commit is the full commit ID of the tip of the integration branch;
the orchestrator resolves both before validation and passes them, with the
journal, as `--target-repo`, `--base-commit` and `--journal`. A missing or
unresolvable value is an execution error (exit 2), never a pass. A path has no
entry at the base commit when the base tree holds nothing there, whether file,
directory, symlink or submodule.

1. `path-correction-in-flight` — No task is in flight: no task's `status` is
   `in_progress` and no task's last journal event is `launched`.
2. `path-correction-merged` — Neither the target task's `status` nor its last
   journal event is `merged`.
3. `path-correction-old-path` — `old_path` is in the target task's `files`, is
   a matching name, and has no entry at the base commit.
4. `path-correction-new-path` — `new_path` is not a matching name, passes the
   project-relative check of application rule 7, and has no entry at the base
   commit. It is also a plain path: it fully matches `[\w./-]+` (Unicode word
   characters, `.`, `/` and `-`), it equals its normalized form, the segments
   that `path_segments` returns joined by `/`, so `.`, `./`, `a//b.md`,
   `a/./b.md` and a trailing `/` are rejected, and its first segment does not
   start with `-`.
5. `path-correction-content` — The change is limited to replacing path strings
   and does not change the meaning of requirements or acceptance criteria, as
   the comparison below decides. On the Re-planning path the comparison does
   not run, and condition 5 requires only that no old path and no bare old
   file name remain.

**Comparison for condition 5.** For IMPLEMENTATION.md, VERIFICATION.md and
each target task's plan, take the version at the base commit and the current
version, and compare them positionally in a single left-to-right pass over the
base version. The pass fixes the occurrences defined below, longer match first,
and replaces each old path by its new path and each old file name by its new
file name at those occurrences only. A replacement is literal and is never
rescanned. The same positions are read in the current version. The two results
must be equal: only at an occurrence may the current version differ from the
base version, and there it holds the old text or a permitted replacement; all
other text is identical. Because the comparison is positional, one old file
name may map to different new names: with `a/REPORT.md` corrected to
`a/enabled` and `b/REPORT.md` corrected to `b/disabled`, changing
`Authentication is enabled` to `Authentication is disabled` is rejected, since
that text is outside an occurrence. In IMPLEMENTATION.md, VERIFICATION.md and a
target task's plan the current version must not contain an old path or a bare
old file name as an occurrence either (the left-behind check); the old text may
not remain there. New task plans under `entries` are outside the set, except a
plan whose normalized path equals one of the documents named under Document
classes below.

**Occurrences.** The scan runs left to right. At one position the longer token
wins, and occurrences never overlap. A token is an old path of several
segments or a bare old file name. A bare occurrence of an old file name is the
literal, case-sensitive file name not preceded by an ASCII letter, digit, `_`,
`-`, `.`, `/` or `\`, and not followed by an ASCII letter, digit, `_`, `-`, `/`
or `\`, or by `.` plus one of letter, digit, `_`, `-`. An old path of several
segments is an occurrence under the same boundary rule, except that a
preceding `./`, the two characters before the token, still counts. A
one-segment old path, judged after `path_segments`, is matched only as a bare
name. So `existing/REPORT.md`, `PREREPORT.md` and `REPORT.md.bak` are neither
replaced nor flagged, and rewriting them fails the comparison;
`existing/a/REPORT.md` and `a/release-REPORT.md` are not occurrences of
`a/REPORT.md` and may not change.

**Permitted replacements.** The old text itself is always permitted at an
occurrence; the left-behind check rejects it where it may not remain.
Otherwise:

| Occurrence | Document | Permitted replacements |
|---|---|---|
| Old path of several segments | Any | That correction's `new_path` |
| Bare old file name | A target task's plan | The new file names of the corrections of the target tasks using that plan that hold this old file name; when there are none, those of all corrections of the patch that hold it |
| Bare old file name | Any other document | The new file names of all corrections of the patch that hold it |
| One-segment old path | As for a bare old file name | The bare replacements above, plus the `new_path` of each selected correction whose old path is that one segment |

A plan's Files section holds the full `new_path` of a one-segment old path
that moves to another directory. For a plan used by several target tasks, the
candidates are the union of those tasks' corrections, and the plan's Files
sections are checked against the union of those tasks' files.

**Document classes.** On the correction entry, condition 5 covers the plan of
every task in `workflow.yaml` that is not a target of the patch, whatever its
status, as well as the documents above. A document takes the first class that
fits, with paths compared after `path_segments` normalization:

| Class | Document | Comparison with the base commit | Left-behind check |
|---|---|---|---|
| Merged plan | A plan used by a task whose `status` or last journal event is `merged`, a plan shared with a target task included | Byte-equal | No |
| Target plan | A plan used by a target task | Positional | Yes |
| Shared document | IMPLEMENTATION.md, VERIFICATION.md | Positional | Yes |
| Non-target plan | The plan of any other task in `workflow.yaml` | Positional | No |

A plan used by a target task and by a merged task is a merged plan. A merged
plan that differs from the base commit is rejected as
`path-correction-content` naming the document, and this takes precedence over
any replacement a target task would need. In a non-target plan an old
reference may remain, and replacing it with a permitted replacement is
allowed, not required; nothing else may change. For every class:

- A document with no entry at the base commit and present now is rejected as
  `path-correction-content`.
- A document with no entry at the base commit and absent now has nothing to
  compare, and is not an error.
- A document with an entry at the base commit and absent now is rejected.
- A document that is not a regular file at the base commit, or cannot be read
  now, is rejected.

The one exception to the first of these rules is the plan of a new task under
`entries`, when its path is none of those documents and collides with none of
them after path normalization (`./` and repeated separators removed). Where a
path is both, the constraint on the existing document wins.

**Condition 5 on the Re-planning path.** The Re-planning path is `create-plan`
`needs_update`, or `pending` on a SPEC-change re-entry. There the comparison
above does not run, and the body of the documents may change. Condition 5
requires only that the current IMPLEMENTATION.md, VERIFICATION.md and target
task plans hold no old path and no bare old file name as an occurrence, else
`path-correction-content`; only these documents are read, and a document that
does not exist now is not an error. Conditions 1 to 4 and the agreement of a
plan's Files section with `files` stay. The skip of the scenario-ID scan for
VERIFICATION.md applies only on the correction entry: a correction patch on
the Re-planning path, or one validated without `workflow.yaml`, scans
VERIFICATION.md. A patch in any other state is already rejected as
`path-correction-not-permitted`; condition 5 runs on it as on the correction
entry, and the limits below do not run.

**Limits on entries and requirements.** On the correction entry, a patch
carrying `path_corrections` is limited in two more fields. The limits stand
outside the five numbered conditions, each under its own code:

- `path-correction-requirements` — `requirements_patch` is null or has no
  entries, or every item names a requirement already in `workflow.yaml` and
  its `set` holds only `tasks_append` whose values are all ids under
  `tasks_patch.entries`.
- `path-correction-entries` — every item of `tasks_patch.entries` has a
  non-empty `files`, and every file is a regular file at the base commit whose
  text holds an old path or a bare old file name of the patch's corrections
  (an occurrence as defined above). A file that cannot be read as text within
  the existing read limit is rejected. Each file of an entry, and each old
  path and new path rendered into its plan, passes the form check of
  condition 4. The plan of an entry is byte-equal to the canonical text that
  the validator renders from the task's id, its `files` and the corrections
  whose old path or bare old file name occurs in those files at the base
  commit: a title, the Files section, and one acceptance criterion for each
  such correction stating that the old reference is replaced by the new one,
  and nothing else, a plan named TASK.md included.

The Re-planning path is not limited.

**Ownership.** `implementation-planner` corrects the plan documents and
proposes `files` through `path_corrections`; the orchestrator applies the
patch to `workflow.yaml`. The implementer and `rework-planner` do not correct
the plan.

**References in tests.** A reference is an occurrence of the old path in a test
file. An unmerged reference is corrected by that task's implementer, following
the corrected plan. A merged reference is corrected by a new task, registered
under `entries` in the same correction.

**Application.** In the in-memory application, a corrected task's `files`
entry equal to `old_path` is replaced by `new_path` at the same list position,
`notes` is set to null, and every other field is copied verbatim.

**Where it applies.** On the correction entry (the permission states above)
and in re-planning entered through route back. A re-planning `replace_all` that
carries a task that is not `merged`, and whose `files` hold a matching name,
corrects it through the same field.

## Ownership boundary

`project` and the review summary block (including `needs_rework`) are
orchestrator-updated only. No operation, mode, or field of this contract
targets them — they are absent from every worker patch by construction, not
by convention workers are expected to honor voluntarily.

Application rule 18's write is this contract's one crossing into
`references/phase-state.md`: the orchestrator, never a worker, owns the
write that sets `spec_change.replan_authorized` to `false`, and the
crossing is permitted only once a re-planning `replace_all` (Re-planning
path) has been applied, in the same phase-state write that records the
application. The record's own definition is
`references/phase-state.md`'s — cited here, not restated.

## Domains vocabulary SSOT

The SSOT for the `domains` vocabulary is `references/review-rules.yaml`.
This contract does not restate the vocabulary; it only requires that
`domains` values used in a `tasks_patch` entry are members of that file's
vocabulary (rule 9 above).
