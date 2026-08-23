# Create-spec Phase Protocol (em-workflow)

Read and executed inline by the `/em-workflow:develop` skill when the
`create-spec` workflow step is pending. Renders design-input.md 5.7. The
orchestrator is the only writer of `workflow.yaml`, phase-state, and every
commit in this phase; `requirements-analyst` and `spec-writer` run as
`Task`-dispatched workers that never write those files themselves.

This document does not restate the shapes it builds on — it cites them:

- Question packet / answer object shape: `references/question-packet-schema.md`.
- Question deduplication, priority, and batch resolution: `references/question-resolution.md`.
- `phase-state/create-spec.yaml` schema, resume rules, exit-4 recovery:
  `references/phase-state.md`.
- `requirements-analyst` / `spec-writer` input and output contracts:
  `references/contracts/analyst-contract.md`,
  `references/contracts/spec-writer-contract.md`.
- `input_digest` (rule R1) and the seven validation layers:
  `references/contracts/worker-envelope.md` (provenance: design-input.md 5.0
  R1, 5.11.2).
- `completed_at_commit` (rule R2): `references/workflow-schema.md`
  (provenance: design-input.md 5.0 R2).
- Command approval: `references/command-execution-protocol.md`.

## 1. Purpose and ownership

- **Orchestrator**: dialogue (`AskUserQuestion`), branch/worktree creation,
  `phase-state/create-spec.yaml`, `workflow.yaml`, every commit, the
  command-approval gate.
- **requirements-analyst**: investigation of the project and generation of
  question packets (`references/contracts/analyst-contract.md`). Writes no
  files, makes no commits, never calls `AskUserQuestion` directly.
- **spec-writer**: renders REQUIREMENTS.md and SPEC.md from
  requirements-analyst's resolved requirements
  (`references/contracts/spec-writer-contract.md`). Never writes
  `workflow.yaml`, never returns a question packet.

## 2. Inputs and preconditions

- The task description supplied to `/em-workflow:develop`, the batch flag,
  and the project root.
- Any existing integration branch/worktree and `phase-state/create-spec.yaml`
  (this is a resume, not a fresh start — see section 4).
- Feature identifier validation: the feature name must match
  `^[a-z0-9][a-z0-9-]*$` before it is interpolated into a branch name or
  worktree path.
- **The integration worktree must be clean before dispatch.** See
  "Scope verification" below (design-input.md 5.11.3). If it is not clean,
  the phase does not dispatch — it aborts and reports the offending paths.

## 3. Bootstrap and durable-state boundary

1. If the feature name is already unambiguous from the input, validate it
   and secure the integration branch/worktree.
2. If the feature name itself is undetermined, the orchestrator asks that
   alone first, before anything else (`gate_id: create-spec.feature-identity`).
3. **Immediately after the feature name is fixed**, create the integration
   worktree and initialize `feature-docs/{feature}/phase-state/create-spec.yaml`
   (`references/phase-state.md`).
4. From that point on, **every subsequent question and its answer is
   persisted** (`references/phase-state.md`, "Update, commit, and exit-4
   recovery") before the worker is re-dispatched.

This moves worktree creation earlier than the previous monolithic agent,
which created the worktree only after detailed clarification had already
happened. Bringing worktree creation forward to immediately after the
feature name is fixed means every answer given from that point on is
persisted and the phase is resumable — nothing after step 3 depends on
in-memory dialogue state.

## 4. Reconcile on entry

Apply the Resume decision table in `references/phase-state.md` before doing
anything else: read the integration branch/worktree, `workflow.yaml`'s
`create-spec` step status, `phase-state/create-spec.yaml`, the recomputed
`input_digest` against the phase-state's `last_input_digest`, the artifact
bodies against their recorded digests, and whether a patch (not applicable
to create-spec) is already applied — in that order, never from memory.

## 5. Analyst dispatch loop

1. Resolve every glob-derived category (E2E discovery, design-system
   candidates, and the reference-impact scan's targets —
   `resolved_input_paths.reference_scan_targets`) at the point
   `references/contracts/analyst-contract.md` names as the resolution point
   (before dispatch, into `resolved_input_paths`). **This resolution is
   cached** (`resolved_input_cache`, `references/phase-state.md`) and is
   reused as-is on every iteration of this loop unless one of that
   document's three re-resolution triggers fired since the last resolution:
   a new phase run started; a worker's `written_artifacts` reported a path
   under a candidate glob; or the last `commit-docs.sh` call returned exit 4
   and the worktree was refreshed. An analyst
   clarification round that hits none of these three re-reads nothing and
   re-scans nothing — it reuses the cached paths and digests. The
   reference-impact scan's targets are resolved here under that same
   category name and participate in this same caching and
   re-resolution-trigger discipline — no separate cache or trigger set
   exists for that category. The orchestrator resolves them before
   dispatch, preserving the discipline that requirements-analyst performs
   no filesystem discovery of its own (assumption A-4). The request-side
   flag it reads (`analysis_scope.inspect_reference_impact`) and the
   result field it returns are owned by
   `references/contracts/analyst-contract.md`, named here only where
   necessary and cited rather than restated.
2. Compute `input_digest` (rule R1, `references/contracts/worker-envelope.md`;
   provenance: design-input.md 5.0 R1) from
   `references/contracts/analyst-contract.md`'s `digest_inputs` list, using
   the resolved (possibly cached) paths from step 1.
3. `Task(subagent_type="em-workflow:requirements-analyst")`, with input
   `analysis_mode: full`.
4. Validate the result (`scripts/validate-worker-output.py`,
   `references/contracts/worker-envelope.md`'s Validation layers table;
   provenance: design-input.md 5.11.2).
5. If the result is `needs_user_input`: normalize the packet (section 6),
   deduplicate and prioritize it (`references/question-resolution.md`),
   present it via `AskUserQuestion`, persist every answer to phase-state
   immediately (section 3, step 4), then re-dispatch with the answers folded
   in — step 1 applies again on this re-dispatch, so the cache is consulted
   before any re-scan. The re-dispatch's input additionally carries
   `prior_analysis`, with `content` (the previous round's
   `analysis_snapshot`) and `input_digest` (the digest of the input that
   produced it) — populated on every analyst re-dispatch within this
   clarification loop, so a high-effort analyst continues from what it
   already found instead of rebuilding it from scratch. When that digest no
   longer matches the current `input_digest`, `prior_analysis` is omitted
   instead: the prior findings were derived from an input that has since
   changed, so they are not safe to hand back as a starting point.
6. Repeat until the result is `status: completed`.

## 6. Question normalization

Follow the common rules in `references/question-resolution.md` — the
deduplication order, the stable priority sort, and the presentation limits.
Not restated here.

## 7. Interactive answer handling

- A selected option is converted to its `option_id`, never its label.
- A freeform answer's verbatim text stays separate from its normalized
  rendering (`question-packet-schema.md`'s `freeform` / `normalized_answer`
  fields) — the orchestrator never collapses the two into one.
- When a freeform answer's meaning is not unambiguous, the orchestrator
  never guesses at a normalization: it raises a follow-up question under a
  new `question_id` instead (question-packet-schema.md consistency rule 7).
- An unanswered `blocking` question is never skipped — the phase does not
  advance past it under any circumstance.

## 8. Batch answer handling

Follow `references/question-resolution.md`'s batch resolution sequence and
unlisted-gate fallback. Not restated here.

## 9. Spec writer dispatch

- `Task(subagent_type="em-workflow:spec-writer")`, once
  requirements-analyst's `completed` payload (`resolved_requirements`) and
  `write_policy` are ready — passed as spec-writer's fixed input;
  spec-writer never re-derives or invents requirement content of its own.
- `write_policy` is built per the per-target decision procedure in
  `references/contracts/spec-writer-contract.md` ("How the orchestrator
  chooses each target's action before dispatch"): a target that does not yet
  exist gets `action: create`; one whose digest matches the immediately
  preceding same-phase output gets `replace_own`; a digest mismatch raises
  the `create-spec.artifact-overwrite` gate (interactive) or follows
  `references/batch-policies.yaml` (batch).

## 10. Artifact validation

- spec-writer's post-conditions (`references/contracts/spec-writer-contract.md`):
  the FR/NFR ID pattern, `spec_index.requirements` agreement with SPEC.md,
  every `tbd` requirement carrying a `tbd_reason`, and no invented
  requirement or assumption.
- The template's mandatory sections
  (`references/templates/requirements-document.md`,
  `references/templates/spec-document.md`).
- Scope verification (below).

## 11. workflow.yaml construction

The orchestrator builds `workflow.yaml` directly here — no worker patch is
used for this step; workers never write `workflow.yaml` themselves
(`references/workflow-patch.md`). Fields, per
`references/workflow-schema.md`: `schema_version`, `feature`, `created`,
`base_branch`, `parent_branch`, `project.license`, `project.components`, the
seven-step `workflow` array with `create-spec` set to `completed` and its
`completed_at_commit` (rule R2, section 13 below), the `design` step set to
`pending` or `skipped` per requirements-analyst's recommendation, `tasks: {}`,
`review`, `requirements` (one entry per FR/NFR from spec-writer's
`spec_index`), and `goal`.

**The `goal` field**: `references/workflow-schema.md` defines its schema and
semantics — cited here, not restated.

- The value is the `/em-workflow:develop` launch-time task description,
  stored **verbatim**: no summarizing, no normalizing, no truncating, and no
  size limit.
- The orchestrator is the sole writer of `goal`. Neither requirements-analyst
  nor spec-writer ever produces it, and it is never derived from
  REQUIREMENTS.md or SPEC.md.
- **Re-entry**: when create-spec is re-entered with `status: needs_update`
  (the SPEC-change transition), an existing `goal` block is left exactly as it is.
  Only a first construction of `workflow.yaml` writes it.
- **No source (EC-7)**: when there is no launch-time task description — an
  empty description, or a resumed feature reached without one — no `goal` block is written.
  This is a valid outcome; no goal is synthesized from any
  other document. The consequence at the batch classification gate is
  defined in `references/question-resolution.md`, cited here rather than
  restated.
- The `goal` block's content is untrusted data — see
  `references/contracts/worker-envelope.md`'s Untrusted-Input Handling
  rather than re-deriving that rule here.

## 11a. Design-system determination

Design-system determination **MUST run even when the design step is
`skipped`** — `project.design_system`'s `kind` (`project_native` \|
`em_workflow` \| `none`) and `paths` are confirmed here regardless of that
status.

The design-step decision collapses two different situations into one
`skipped` status: "a project-native design system already fully determines
the UI, so no new visual decision is needed" and "there is no UI at all".
Deriving `kind: none` from `skipped` would silently hide a real,
already-existing design system from the planner and the design step.

- **Exception**: if the design step is `skipped` **and**
  requirements-analyst's completed-payload `design_system_candidates`
  reported zero candidates, the orchestrator may record `kind: none`
  without asking the user — there is nothing to draft, so no downstream
  harm follows from skipping confirmation.
- In every other case — `skipped` with one or more candidates, or `design`
  left `pending` — the value is confirmed exactly as it would be for a
  `pending` design step.
- **interactive**: present the candidates under `gate_id:
  create-spec.design-system`; the user chooses `project_native` (naming
  which candidate), `em_workflow`, or `none`. Ask even when zero candidates
  were found, so `none` is an explicit user choice rather than a silent
  default.
- **batch**: follow `references/batch-policies.yaml`'s
  `create-spec.design-system` entry (top candidate → `project_native`; no
  candidates → `none`).
- Once confirmed here, neither the `design` step nor `create-plan`
  re-searches for it — both read `project.design_system` from `workflow.yaml`
  only (rule R1, `references/contracts/worker-envelope.md`; provenance:
  design-input.md 5.0 R1).

## 12. Command approval gate

After `workflow.yaml` is written, run the approval gate from
`references/command-execution-protocol.md` (`gate_id:
create-spec.command-approval`) as an orchestrator responsibility — moved
here from the previous monolithic agent. Every detected build / test /
format / e2e command is shown to the user verbatim before anything may
execute it.

## 13. Completion

1. Commit the artifacts (commit B: REQUIREMENTS.md, SPEC.md).
2. Write `workflow.yaml` with the `create-spec` step's `status: completed`
   and `completed_at_commit: B` (rule R2 — the HEAD immediately before this
   commit) and commit it (commit C).
3. Set the `design` step to `pending` or `skipped` per section 11a.
4. Set `phase-state/create-spec.yaml`'s `status` to `completed`.

## Termination conditions

No fixed round limit is imposed. The phase ends when ALL of the following
hold:

- `requirements-analyst` returns `status: completed`.
- Zero `blocking` questions remain.
- Every requirement category is confirmed, recorded `tbd`, or explicitly
  excluded.
- No already-answered question has been regenerated.
- `spec-writer`'s artifacts pass validation (section 10).

## Loop-stop conditions (progress fingerprint)

`progress_fingerprint` is the sha256 of a normalized JSON object built from
the `confirmed_facts` fact-ID set, the unanswered `question_id` set, and the
`assumptions` assumption-ID set. It is recomputed every iteration and
persisted to phase-state.

The loop stops when any of the following is true:

- The same question, in substance, was regenerated after already being
  answered.
- `progress_fingerprint` is unchanged across two consecutive dispatches.
- The worker returned the same validation error twice.
- The user chose to stop create-spec here.
- An answer genuinely depends on an external condition and the user
  explicitly chose to record it as TBD.

**On stopping, the orchestrator MUST NOT automatically convert an
unresolved item into an assumption.** Instead it presents the three-way
stalled gate (`gate_id: create-spec.stalled`):

1. Continue with more information.
2. Record specific items as TBD.
3. Abort create-spec as `needs_update` or `failed`.

Converting an item to an assumption is permitted only when the user
explicitly selects that option — it is never the automatic outcome of any
`on_unanswered` value.

## Scope verification

Referenced (not duplicated) by `references/phases/create-plan-phase.md`,
since the procedure is identical there. Applies to every dispatch of the
five in-scope workers named in design-input.md 2.3. Renders design-input.md
5.11.3.

A plain pre/post `git diff` is not used: a concurrent doc commit or task
merge landing on the integration branch during dispatch would mix in
changes the worker never made, and an uncommitted change that predated
dispatch and was overwritten by the worker would not surface in a
name-only diff either.

### Precondition: the worktree must be clean before dispatch

Before dispatching a worker, confirm the integration worktree is clean — no
staged changes, no uncommitted tracked changes, no unexpected untracked
files. **This is not a claim that the existing flow guarantees
cleanliness — it is a fail-closed check performed at every single
dispatch.**

`commit-docs.sh` only stages `feature-docs/`, `test/README.md`, and
`design-system/` (`scripts/commit-docs.sh:147`), so the worktree can be left
dirty by:

- a build / test / format command that modified tracked source;
- an untracked byproduct created outside an allowed root;
- uncommitted leftovers from a prior phase failure (in particular, the path
  where `rework-planner` is dispatched after a failed `verify`).

If the worktree is not clean, **abort without dispatching, and report the
offending paths**. The phase never force-cleans automatically — no
automatic delete, no `reset --hard` to force cleanliness — because that
could destroy work the user has not committed yet.

`.gitignore`d build artifacts are excluded from the clean check (
`git status --porcelain`'s default behavior already omits ignored paths).

A dirty state is never snapshotted and restored later; that would conflict
with the `reset --hard` used for staleness handling below.

### Separating the worker's change set from external changes

A linked worktree's HEAD tracks its branch ref. A concurrent
`merge-task.sh` can advance the integration branch while the worker touches
nothing at all, so the current HEAD tree can move even when the worker made
no change whatsoever.

**The HEAD layer's diff must never be counted as part of the worker's
change set.** Each layer has exactly one job:

| Layer | Use |
|---|---|
| HEAD SHA / HEAD tree | Staleness detection only — how an external commit is detected. |
| index + working tree | The worker's change set. Scope judgment uses only these two layers. |

Given the worktree was clean before dispatch, any difference found in the
index or working tree afterward is attributable to the worker. An external
commit only advances the branch ref — it never rewrites the linked
worktree's index or working tree (`merge-task.sh` builds its tree in the
task's own worktree and only runs `update-ref` against the integration
branch).

### Exclusivity assumption (normative)

A snapshot-based approach cannot, by itself, distinguish the dispatched
worker from some other process that touched the same worktree's files
directly. This is stated as an explicit assumption:

> While a worker is dispatched, only the orchestrator and that worker may
> create, modify, or delete files directly in the integration worktree.
> Other processes may advance the integration branch's ref, but must never
> touch the worktree's files directly.

**Scope of applicability**: this assumption applies only to the five
workers in design-input.md 2.3, for the interval from taking the scope
snapshot through the end of verification — it is not a standing constraint
on the plugin as a whole.

The review phase's auto-fix loop runs multiple `review-editor` workers
concurrently against different files in the same integration worktree, in
its wave-parallel mode (`references/review-phase.md`). That is an explicit
exception governed by `review-phase.md`'s own per-wave verification rules;
this design does not change how the review phase verifies (design-input.md
2.2).

**Why the assumption holds** (verified against the scripts as written):

- `merge-task.sh` builds its tree in the task worktree and only runs
  `update-ref` against the integration branch.
- Implementers work in their own per-task worktree
  (`references/implement-phase.md`).
- The queue hooks write `journal.jsonl` / `agents.jsonl` outside any feature
  worktree.
- `commit-docs.sh` and `merge-task.sh`'s ref updates are serialized under
  the same flock.

**This exclusivity is not enforced by a lock or a hook.** When it is
violated, the outcome is not always fail-closed:

| External change | Outcome |
|---|---|
| Outside the permitted scope (an existing file not in `targets`, or a new file outside `allowed_write_roots`) | Rejected as a violation (fail-closed). |
| Inside the permitted scope, and the worker reported that same path in `written_artifacts` | Accepted as the worker's own output — **the snapshot approach cannot tell the two apart.** |

The second case is an inherent limit of snapshot-based detection without
OS-level writer identification; it is covered by adherence to the
assumption above, not by the mechanism itself.

### Pre-dispatch containment validation

Before dispatching a worker, validate every `write_policy.targets` path and
every `allowed_write_roots` entry against the containment rules —
the same rules the post-dispatch comparison applies below, run here
against the *intended* targets rather than against an observed change set:

- Reject any target or root that is an absolute path, or whose
  project-root-relative form contains a `..` segment.
- Reject any target or root where the path itself, or any segment beneath
  it, is a symlink (`lstat` every segment; a `realpath` resolution that
  lands outside the project root is rejected outright).
- Reject any target or root that collides with another on a
  case-insensitive filesystem, even though comparison elsewhere is
  case-sensitive.

A target or root that fails this check is a plan-time defect: abort before
dispatch and report the offending path. Do not launch the worker and rely
on the post-dispatch comparison to catch it instead — it cannot.

**This pre-dispatch check and the post-dispatch comparison below are not
interchangeable; the latter is an audit, not the primary control.** The
post-dispatch comparison only ever inspects the integration worktree's own
index and working tree. A worker write that goes through a symlink hop to
a location outside the worktree, or straight to an absolute path outside
it, never enters that index or working tree — so the comparison has
nothing to compare and cannot detect it, let alone undo it. Validating
containment before dispatch is the only point at which such an escape can
be prevented; once it has happened, a write made outside the worktree
cannot be recovered by anything the post-dispatch comparison does.

### Pre-dispatch snapshot

| What | How | Use |
|---|---|---|
| HEAD SHA | `git rev-parse HEAD` | Staleness, and the pinned tree baseline the post-dispatch comparison below diffs against |
| Untracked files | `git status --porcelain -z -uall` | Scope |
| `extend_only` target key sets | Parse `design-system/tokens.yaml` | Scope |

**No whole-tree working-tree-content hashing pass runs here, and no
whole-index blob-ID/mode listing pass runs here either.** The precondition
above already guarantees the tracked working tree matches the index, which
in turn matches the tree at the pinned HEAD SHA — so that single SHA already
pins every tracked path's baseline identity, and a separate `git ls-files -s
-z` listing of the whole tracked set would add nothing before dispatch on
top of what git already durably records at that commit. Both blob-ID/mode
lookup and content hashing (`git hash-object --`) happen only in the
post-dispatch comparison below, and only for the candidate paths that
comparison has already enumerated — never for the whole tracked set. A
symlink is stored by git as a blob (the link string itself), so
`git hash-object` on a changed symlink path also detects a change to what
the link points at.

### Post-dispatch comparison (in this order)

1. **Compute the worker's change set** — always, regardless of whether HEAD
   moved.
   - Enumerate candidates from two changes-proportional sources, never from
     a whole-index listing of every tracked entry: `git status --porcelain
     -z -uall` (untracked and ignored-aware) for untracked paths, and the
     index-versus-working-tree comparison against the snapshot's pinned HEAD
     SHA — not the live `HEAD` ref, which may have moved — for tracked
     paths. That tracked-path comparison reports each candidate's old and
     new blob IDs and modes directly, so this step alone already reports
     deletions, mode changes, and kind changes (file ⇔ symlink ⇔ absent) —
     none of those require reading file content.
   - **Content hashing with `git hash-object --` is applied only to the
     paths this comparison already reports as changed** — never to the
     whole tracked tree, and blob identifiers and modes are likewise queried
     only for those same candidate paths, never for the whole tracked set.
     Combined with dropping the pre-dispatch working-tree hash and the
     pre-dispatch whole-index listing (above), this is what brings the cost
     of scope verification down from O(repository bytes) to O(changed paths)
     per dispatch.
   - The HEAD layer is **never** part of this comparison — meaning the live,
     possibly-moved `HEAD` ref, not the pinned SHA captured before dispatch.
     That pinned SHA is fixed reference data; diffing against it is diffing
     against the recorded baseline, exactly as diffing against a table of
     recorded blob IDs would be. An external commit advancing the branch tip
     is never folded into the candidate set this step enumerates.
2. **Judge permitted scope.** Split changed paths by whether they existed at
   snapshot time; each half has its own rule.
   - The changed-path set must equal the set of paths the worker listed in
     `written_artifacts`.
   - **Paths that existed at snapshot time** (modified or deleted): every
     one must be enumerated in `write_policy.targets`, and must not have
     been changed beyond what its `action` allows. Not enumerated →
     violation.
   - **Paths that did not exist at snapshot time** (newly created): must
     fall under `allowed_write_roots`, or be enumerated in `targets`.
   - `extend_only` targets: none of their pre-existing keys may be changed
     or removed.

   **Path normalization and containment (applies to every comparison
   above)**:

   - Normalize every path to a project-root-relative form. An absolute path
     is relativized only if its `realpath` resolves inside the project
     root; otherwise it is rejected outright. A path that resolves to
     contain a `..` segment after relativization is also rejected.
   - Containment is judged by comparing normalized path **segments**, never
     by string-prefix comparison — `feature-docs/example2` must never be
     treated as contained in `feature-docs/example`.
   - If the root itself, or any path segment beneath it, is a symlink, the
     path is a violation (this blocks writing outside the root via a
     symlink hop).
   - Comparison is case-sensitive; if two normalized paths collide on a
     case-insensitive filesystem, that collision is itself a violation.
3. **Remove any violation** before the next snapshot is taken.
   - Tracked files: restore both the index and the working tree from the
     snapshot's blob (identical content in both, since the worktree was
     clean before dispatch).
   - Untracked violators: move them aside with `gio trash --`. **If `gio` is
     unavailable, do not delete or move anything** — list the offending
     paths and abort the phase instead.
4. **Evaluate whether HEAD moved** (staleness).
   - If it did not move: no violations → success; violations present → the
     phase aborts after step 3's removal.
   - If it did move: continue to step 5.
5. **Stale handling**:
   - Discard the worker's output even if it was not in violation — it was
     produced against a tip that is no longer current.
   - `git -C {integration worktree} reset --hard
     em-workflow/{feature}/integration` to resync to the latest tip (a
     linked worktree does not auto-follow an external ref update).
   - Recompute `input_digest` and `write_policy`.
   - Re-dispatch under a new `request_id`.

Running step 1 before evaluating HEAD movement means the worker's
unpermitted changes are never folded into the baseline of the next
snapshot. Excluding the HEAD layer from step 1 means an external commit is
never misreported as the worker's violation.

## Gate option vocabulary

The option vocabulary a batch-policies.yaml `option_id` is checked against
(`references/gate-option-vocabulary.md` states the correspondence rule and
format this table follows).

| gate_id | option_id | meaning |
|---|---|---|
| `create-spec.feature-identity` | `derive_from_task_description` | Batch mode derives the feature name automatically from the supplied task description, without asking the user. |
| `create-spec.design-system` | `top_candidate_or_none` | Batch mode resolves the design-system `kind` automatically: `project_native` when a candidate was found, `none` when none were found. |
| `create-spec.design-system` | `project_native` | Interactive mode: the user picks the top design-system candidate that was found (section 11a). |
| `create-spec.design-system` | `em_workflow` | Interactive mode: the user picks em-workflow's own design system instead of any detected candidate (section 11a). |
| `create-spec.design-system` | `none` | Interactive mode: the user picks no design system for this feature (section 11a). |
| `create-spec.stalled` | `record_tbd` | Batch mode records the specific stalled items as TBD and continues (the three-way stalled gate's branch 2). |
| `create-spec.stalled` | `continue_with_more_info` | The user chooses to continue create-spec with more information rather than stopping (branch 1). |
| `create-spec.stalled` | `abort_create_spec` | The user chooses to abort create-spec as `needs_update` or `failed` (branch 3). |

`create-spec.feature-identity`'s interactive counterpart is not a selectable
`option_id`: the orchestrator asks the user directly to name the feature
identifier as free text (section 3, step 2), so there is no second row for
it here.
