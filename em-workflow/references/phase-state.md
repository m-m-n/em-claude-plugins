# phase-state Schema and Persistence (em-workflow SSOT)

`feature-docs/{feature}/phase-state/` holds the dialogue and worker-execution
state that `workflow.yaml` never carries. **`workflow.yaml` carries no
dialogue history** — question packets, answers, worker run records, and the
derived input-resolution cache all live here instead.

## File layout

```text
feature-docs/{feature}/phase-state/
├── create-spec.yaml
├── create-plan.yaml
├── rework.yaml
└── backfill.yaml            # present only while a project.design_system
                              # backfill's discovery result is unresolved
                              # into workflow.yaml (see "Backfill discovery
                              # persistence" below)
```

One file per phase. These files are committed to the integration branch like
every other feature-docs artifact. `commit-docs.sh`'s `ARTIFACT_PATHS`
(`scripts/commit-docs.sh:147`) already stages the whole `feature-docs`
directory, so **no script change is required** to persist them — this
applies equally to `backfill.yaml`, which is not tied to any single phase.

## Schema

```yaml
schema_version: 1
feature: example-feature
phase: create-plan
status: awaiting_answers      # initialized | dispatching | awaiting_answers | applying_patch | completed | failed
generation: 4                 # incremented each time the phase restarts from scratch
base_revision: a3c91f2...     # HEAD captured immediately before this write; informational only
last_input_digest: sha256:... # input_digest of the most recent dispatch
active_request_id: create-plan-run-0002   # current worker run; null before dispatch / after completion
packets:
  create-plan-q0001:
    status: answered          # issued | answered | obsolete
    issued_at: "2026-08-02T15:50:00+09:00"
    questions:
      - question_id: requirement.fr4.tbd-resolution
        status: answered
answers:
  requirement.fr4.tbd-resolution:
    packet_id: create-plan-q0001
    answered_at: "2026-08-02T16:00:00+09:00"
    source: user
    answer_mode: select_or_freeform
    selected_option_ids: [assume]
    freeform: "..."
    normalized_answer: "..."
worker_runs:                   # status: dispatched | needs_user_input | completed | blocked
  - request_id: create-plan-run-0001   #         | invalid_input | stale_input | failed | discarded_stale
    status: needs_user_input
    input_digest: sha256:...
    output_digest: sha256:...
artifacts:
  - path: feature-docs/example/IMPLEMENTATION.md
    sha256: sha256:...
    produced_by: create-plan-run-0002
patches:
  - patch_id: create-plan-p0001
    status: proposed          # proposed | validated | applied | rejected
    base_input_digest: sha256:...
    base_workflow_blob: 8f17c04...
progress_fingerprint: sha256:...
stale_redispatch_count: 0     # consecutive re-dispatches caused by an artifact-commit exit 4 (cap: 1)
resolved_input_cache:          # derived cache of dynamic-input resolution (see below); initial value: empty map
  design_system_candidates:
    generation_digest: sha256:...   # digest over the sorted candidate path set + each path's blob hash
    resolved_at_generation: 4       # the phase-state `generation` this cache entry was built under
    paths:
      - src/design-system/tokens.ts
    digests:
      src/design-system/tokens.ts: sha256:...
    truncated: false                # true once the 500-file / 5 MB discovery cap was hit
last_error: null
```

Every top-level field:

| Field | Meaning |
|---|---|
| `schema_version` | Format version. Currently `1`. See "Unknown `schema_version`" below. |
| `feature` | Feature name, matches `feature-docs/{feature}/`. |
| `phase` | `create-spec` \| `create-plan` \| `rework` — matches the file name. |
| `status` | Top-level phase status: `initialized` \| `dispatching` \| `awaiting_answers` \| `applying_patch` \| `completed` \| `failed`. |
| `generation` | Counts phase restarts from scratch (see resolved_input_cache's "new phase run", below). |
| `base_revision` | HEAD immediately before writing this phase-state. **Informational only** — never compared for staleness (that is `input_digest`'s job). |
| `last_input_digest` | `input_digest` of the most recent worker dispatch. |
| `active_request_id` | The current worker run's `request_id`, or `null`. See "active_request_id lifecycle". |
| `packets` | Map keyed by `packet_id`. Each value: `status` (`issued` \| `answered` \| `obsolete`), `issued_at`, `questions[]` (each: `question_id`, `status`). |
| `answers` | Map keyed by `question_id`. Each value: `packet_id`, `answered_at`, `source`, `answer_mode`, `selected_option_ids`, `freeform`, `normalized_answer`. |
| `worker_runs` | List. Each entry: `request_id`, `status` (see transitions below), `input_digest`, `output_digest` (digest only — see Size management). |
| `artifacts` | List. Each entry: `path`, `sha256`, `produced_by` (a `request_id`). |
| `patches` | List. Each entry: `patch_id`, `status` (`proposed` \| `validated` \| `applied` \| `rejected`), `base_input_digest`, `base_workflow_blob`. |
| `progress_fingerprint` | Digest summarizing dialogue+worker progress; used for the loop-termination check. |
| `stale_redispatch_count` | See "Consecutive retry limit". |
| `resolved_input_cache` | See "resolved_input_cache" below. |
| `last_error` | `null`, or the last recorded phase-state/artifact-commit failure. |

## ID uniqueness and idempotency

`packet_id` / `request_id` / `patch_id` are unique within a feature.
Re-appearance of an ID is a **re-statement of the same entity**: if the new
content matches, it is a no-op; if it diverges, it is a **protocol error**.

- `answers` is a map keyed by `question_id`. **Re-answering the same
  question is a protocol error, not an overwrite** — a changed answer
  requires a new question ID with `supersedes` pointing at the original.
- Appending to `artifacts` / `patches`: same ID + matching content → no-op;
  same ID + diverging content → protocol error.
- `worker_runs` follows the same rule, **except that its `status` field
  alone may be updated** along the transitions below (any other field
  differing is a protocol error).

### worker_runs[].status transitions

| From | To | Trigger |
|---|---|---|
| `dispatched` | `needs_user_input` / `completed` / `blocked` / `invalid_input` / `stale_input` / `failed` | Worker returns |
| `dispatched` / `completed` | `discarded_stale` | Artifact-commit exit 4 (see below) |

`discarded_stale` is a **terminal state** — no transition leaves it.

### active_request_id lifecycle

`active_request_id` is set immediately before dispatching a new
`request_id`, and reset to `null` once that worker run reaches a terminal
state (`completed` with its artifacts committed, or `failed`).

**Exception**: a run that reaches `discarded_stale` **keeps**
`active_request_id` pointing at it, from step 2 through the next dispatch
(step 4) of the Artifact-commit exit-4 recovery below — it is the only way
to tell, on resume, which run was discarded.

### resolved_input_cache

`resolved_input_cache` is a map keyed by category name (e.g.
`design_system_candidates`); the initial value is an empty map, never
`null`. Unlike `artifacts` / `patches` / `worker_runs`, **re-resolving the
same category may overwrite without a content match** — the cache is a
derived value, not a record (the content-invariance rule above does not
apply to it).

- **Reset to an empty map** when `generation` increases, or when the
  phase-state is (re-)created with `status: initialized`.
- **Staleness signal**: not HEAD (`commit-docs.sh` always advances HEAD, so
  a HEAD comparison would invalidate on every commit and defeat caching).
  Instead, each cached entry's `generation_digest` — the sha256 of the
  normalized JSON of the sorted candidate path set plus each path's blob
  hash — is what identifies "this resolution".
- **Re-resolution triggers** (re-run discovery and recompute
  `generation_digest`; otherwise reuse the cached entry no matter how many
  phase-state commits land in between):
  1. a new phase run starts (`status` becomes `initialized`, or
     `generation` increases);
  2. a worker's `written_artifacts` reports a path under the candidate
     glob since the last resolution;
  3. the most recent `commit-docs.sh` call returned exit 4 and the worktree
     was refreshed (an external commit may have changed the candidates).
- **Resume**: a resume that continues the same `generation` reuses the
  cached entry; a resume that bumps `generation` resets to an empty map.
  Each entry MUST carry `generation_digest`, `resolved_at_generation`,
  `paths`, `digests`, `truncated`; `resolved_at_generation` MUST be `<=` the
  current `generation`.
- **Discovery exclusions and extension allowlist**: `design_system_candidates`
  resolution excludes `node_modules/`, `vendor/`, `.git/`,
  `.claude/worktrees/`, and any path covered by `.gitignore`. A directory
  match is not expanded to every file beneath it — only files with one of
  the extensions `.yaml`, `.yml`, `.json`, `.css`, `.scss`, `.ts`, `.js`,
  `.kt` are enumerated (images, fonts and build output do not inform
  candidate detection). Both filters apply **during enumeration**, so an
  excluded path or a non-matching extension never counts toward the
  discovery caps below.
- **Discovery caps**: resolution stops once it has found 500 files or 5 MB
  total, and records `truncated: true`. Handling is the same across every
  path that resolves candidates, and takes priority over that path's normal
  default:

  | Mode | Behavior on `truncated: true` |
  |---|---|
  | interactive | Present the relevant gate ID with "too many candidates to auto-detect", and require a manual `kind` + `paths` |
  | batch | **Abort the phase.** The `batch-policies.yaml` default for the gate does NOT apply — auto-deciding from an incomplete candidate list would permanently misclassify the project |

## Update, commit, and exit-4 recovery

Every phase-state update is written via `commit-docs.sh {integration
worktree} "{message}" {expected_base_tip}`; the third argument is
**mandatory** for phase-state writes.

There are two distinct recoveries for a `commit-docs.sh` exit 4 (stale
worktree), depending on what was being committed. They MUST NOT be
conflated: the phase-state recovery below assumes the write can simply be
replayed against a refreshed worktree; the artifact-commit recovery assumes
it cannot, because worker output bodies are never retained (digest only).

### Phase-state exit-4 recovery

Applies whenever the commit being retried is a phase-state write only (no
worker artifact is at stake).

1. `git -C {integration worktree} reset --hard em-workflow/{feature}/integration` to refresh to the latest tip.
2. Re-read the latest phase-state.
3. Upsert the packet / answer / worker_run / artifact / patch that was
   being written into the **re-read** phase-state, following the ID
   uniqueness and idempotency rules above — never overwrite the whole
   re-read phase-state with the in-memory (stale) copy.
4. `resolved_input_cache` takes the **freshly re-read** value, never the
   in-memory one — an exit 4 means an external commit landed, which may
   have changed the candidates. This refresh is itself re-resolution
   trigger (3) above, so re-resolve before the next dispatch.
5. Update `base_revision` to the post-refresh HEAD.
6. Retry `commit-docs.sh` once.
7. If the retry also returns exit 4, abort the phase and report to the
   user, including the answer object that would otherwise be lost.

An answer received from `AskUserQuestion` MUST be written to phase-state
immediately, before the next worker dispatch — otherwise a session
interruption between the two loses the answer.

### Artifact-commit exit-4 recovery

**Does not use the phase-state recovery above.** A worker's Markdown/HTML
output body is held in neither the worker result nor phase-state (digest
only — see Size management), so it cannot be replayed after
`reset --hard`. The conflict this handles:

1. a worker writes its artifact and returns;
2. scope verification and artifact verification succeed;
3. a concurrent `merge-task.sh` advances the integration branch;
4. the `commit-docs.sh` call committing the artifact returns exit 4.

Fixed order — **the `discarded_stale` record and its commit MUST precede
re-dispatch**:

1. `git -C {integration worktree} reset --hard em-workflow/{feature}/integration` to sync to the latest tip (the artifact is lost).
2. Update the discarded `request_id`'s `worker_runs[]` entry to `status: discarded_stale` (a permitted transition) and increment `stale_redispatch_count` by 1 in that same `commit-docs.sh` call. Leave the top-level `status` as `dispatching` and `active_request_id` pointing at the discarded run.
3. Recompute `input_digest` and `write_policy`.
4. Update `active_request_id` to a new `request_id` and re-dispatch the worker.
5. Verify and commit the new artifact as usual.
6. Once the artifact commit succeeds, reset `stale_redispatch_count` to `0` in a **later, separate** phase-state commit — never combined with the artifact commit itself.

Step 2 MUST NOT be reordered after the re-dispatch in step 4:
`commit-docs.sh` stages entire directories (`feature-docs`,
`design-system` — `scripts/commit-docs.sh:147`), so a phase-state commit
made after re-dispatch would sweep in the new worker's **unverified**
artifact alongside the `discarded_stale` record.

If step 2's own commit returns exit 4, follow the Phase-state exit-4
recovery above (one retry) for that commit.

Falling back to staging the artifact in a temp location and re-applying it
onto the fresh tip is not used — it would require a second round of
conflict verification and leaves the worker's judgment based on stale
input.

### Consecutive retry limit

Re-dispatch caused by an artifact-commit exit 4 is capped at **one
consecutive** occurrence.

| Point | `stale_redispatch_count` |
|---|---|
| Phase start | `0` |
| First exit 4 (persisted at step 2 above) | `1` |
| Second exit 4 | Step 2 is NOT executed; the phase is set to `failed` with the counter left at `1` |
| After a successful artifact commit (step 6) | `0` |

The counter and the `discarded_stale` record are persisted in the **same**
commit at step 2 precisely so that an interruption between "record
persisted" and "counter incremented" cannot make a resumed run
misidentify a retry as a first attempt and bypass the cap.

If step 6's commit itself returns exit 4, follow the Phase-state exit-4
recovery (one retry). If that also fails, the counter stays at `1`, but the
artifact is already committed — a resume can tell the run is complete from
`artifacts` matching the on-disk digest (see Resume decision table).

When the phase is set to `failed` at the second exit 4, report that
concurrent merges are outpacing worker execution time. This cap mirrors the
phase-state commit's own one-retry rule.

## Resume decision table

Resume reads state in this order — never from memory:

1. integration branch / worktree
2. `workflow.yaml` step status
3. phase-state
4. recomputed `input_digest` vs. phase-state's `last_input_digest`
5. artifact bodies vs. their recorded digest
6. whether a patch is already applied

| phase-state `status` | Action |
|---|---|
| `initialized` | Start from the first worker dispatch |
| `dispatching` (no artifact; `active_request_id`'s run is `discarded_stale`) | Steps 1-2 of the Artifact-commit exit-4 recovery completed, interrupted before re-dispatch. If `stale_redispatch_count == 1`: recompute `input_digest` and `write_policy`, re-dispatch under a **new** `request_id` (do not increment the counter again). If `>= 2`: set the phase to `failed` |
| `dispatching` (no artifact; otherwise) | Recompute `input_digest`; if unchanged, re-dispatch with the same input; if changed, use a new `request_id` |
| `dispatching` (artifact present, no patch proposed) | Verify the artifact, then re-dispatch the worker |
| `awaiting_answers` | Re-present only the unanswered questions |
| `applying_patch` (not yet applied) | Apply only if the workflow-patch application rules are satisfied; otherwise re-dispatch the worker to regenerate the patch |
| `applying_patch` (applied; step not yet `completed`) | Verify workflow.yaml + artifacts, and re-run only the `completed` transition |
| `completed` | `workflow.yaml` is authoritative; reconcile phase-state to match |

**When `workflow.yaml`'s step is `completed` but phase-state lags behind,
`workflow.yaml` wins.**

## Size management

A phase is bounded to roughly 32 questions across however many iterations
that phase runs (a guideline, not a hard field) — exceeding it triggers the
phase's loop-termination condition.

`worker_runs[].output_digest` retains **only a digest**; the full worker
output body is never stored in phase-state.

## Legacy feature compatibility

An existing `workflow.yaml` created before this phase-state model has no
`phase-state/` directory. Handling is fixed:

| Upstream step state | phase-state | Behavior |
|---|---|---|
| `create-spec` / `create-plan` both `completed` | absent | **Do not require phase-state.** Continue `implement` onward on the new flow |
| `create-spec` or `create-plan` is `in_progress` / `pending` | absent | Restart that phase on the new flow. Treat the existing REQUIREMENTS.md / SPEC.md / IMPLEMENTATION.md as a write-policy digest mismatch: interactive asks whether to overwrite; batch uses `preserve_and_reuse` and continues with the existing document as authoritative |
| any | present | Ordinary resume (Resume decision table, above) |

### project.design_system backfill

An existing `workflow.yaml` without `project.design_system` is backfilled,
because the orchestrator never explores for it outside this procedure (see
"resolved_input_cache" above — resolution reads `workflow.yaml` only, it
never searches at dispatch time).

**Placement inside develop's Step B.** Step B normally runs "select the
first incomplete step → set it `in_progress` → execute the phase". Backfill
is inserted **between the first and second of those**:

1. Read `workflow.yaml` and select the first incomplete step.
2. If the selected step is `design` or `create-plan` and
   `project.design_system` is unset, run backfill **before** setting the
   step `in_progress`.
3. After backfill completes, **re-read `workflow.yaml` and restart step
   selection from step 1**.
4. If backfill is unnecessary (or already done), proceed to set the step
   `in_progress` and execute the phase as normal.

**Why not set `in_progress` first**: if the session ends while the backfill
question is unanswered, a step stuck `in_progress` with no phase-state
would be unrecoverable by the Resume decision table above.

A feature past both `design` and `create-plan` (e.g. only `implement`
onward remains) never runs this backfill.

**Interrupted backfill**: if the backfill question is answered but the
session ends before the `workflow.yaml` commit, the answer is lost (this
procedure has no phase-state of its own to persist it in). Resume re-asks
the same question — a single selection, so re-asking is cheap enough that
no dedicated persistence is added. This loss is scoped to the **answer**
only, and is an accepted trade-off about it; the **discovery result** that
produced the candidates being asked about is a separate concern, persisted
as described next, and is not re-run on resume.

### Backfill discovery persistence

Step 1 of the backfill procedure below dispatches the analyst before
`design` or `create-plan`'s own phase-state necessarily exists — the
backfill runs ahead of both — so its discovery result has no phase file of
its own to live in. It is written to
`feature-docs/{feature}/phase-state/backfill.yaml` immediately after step 1
completes, via `commit-docs.sh`, before step 2 or step 3 asks or decides
anything:

```yaml
schema_version: 1
feature: example-feature
design_system_candidates:
  generation_digest: sha256:...
  paths:
    - src/design-system/tokens.ts
  digests:
    src/design-system/tokens.ts: sha256:...
  truncated: false
```

Same fields as a `resolved_input_cache` entry (`generation_digest`, `paths`,
`digests`, `truncated`) — it is the same kind of derived value, just kept
outside any single phase-state file because backfill is not owned by one
phase.

An **ordinary resume** that finds `backfill.yaml` present and
`project.design_system` still unset reuses its `design_system_candidates`
rather than re-dispatching the analyst, and proceeds directly to step 2
(interactive) or step 3 (batch) below — the discovery itself is not
repeated. `backfill.yaml` becomes moot once `workflow.yaml` carries
`project.design_system`, since that field — not the file's presence — is
backfill's own once-only guard (see below); step 4 MAY delete
`backfill.yaml` in the same `commit-docs.sh` call that writes
`workflow.yaml`, but leaving it in place is harmless.

**Backfill procedure:**

1. Dispatch `requirements-analyst` with `analysis_mode:
   design_system_detection` to get `design_system_candidates`, then persist
   it as described above.
2. interactive: present the candidates under gate ID
   `create-spec.design-system`; ask for `kind` and `paths` even when there
   are zero candidates (forcing an explicit `none`).
3. batch: follow `batch-policies.yaml`'s `create-spec.design-system` entry
   (top candidate → `project_native`; none → `none`).
4. Write the resolved value to `workflow.yaml` and commit via
   `commit-docs.sh` with message `docs({feature}): backfill design_system`.
5. If the `kind` × token-existence cross-product table finds an
   inconsistency (e.g. `kind: none` but tokens actually exist on disk),
   return to step 2 and re-confirm.

Backfill runs **at most once** per feature; afterward the ordinary
resolution rule applies.

**Unknown `schema_version`**: if a phase-state file's `schema_version` is
not the value this document defines (currently `1`; anything greater is
unknown), abort and report a plugin version mismatch. Do not attempt to
interpret an unknown schema.
