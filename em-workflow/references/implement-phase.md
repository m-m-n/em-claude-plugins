# Implement Phase Protocol (em-workflow)

Read and executed inline by the `/em-workflow:develop` skill when the
`implement` workflow step is pending. The main session performs this
orchestration itself — parallel `Task()` fan-out only works from the main
context.

## Branch & Worktree Model (READ FIRST)

The workflow NEVER commits to, resets, or force-updates the user's branch or
the user's main working tree. All workflow commits land on a dedicated
integration branch, materialized in its own worktree. This branch and
worktree are a PRECONDITION of this phase: create-spec creates both at
Phase 3, immediately after the feature name is confirmed and before any
document is written; this phase never creates them itself.

```
{base_branch}  (user's branch — untouched)
    └─ em-workflow/{feature}/integration   (parent_branch — workflow-owned)
         ├─ em-workflow/{feature}/task0001 (task branch, own worktree)
         ├─ em-workflow/{feature}/task0002 (task branch, own worktree)
         └─ ...
```

- Worktree root: `{project_root}/.claude/worktrees/em-workflow/{feature}/`
  (the Claude Code standard worktree location; the gitignore-guard pre-step
  in I.1 ensures it is git-ignored in the main tree).
  - `integration/` — the integration worktree (created at create-spec
    Phase 3; this phase only confirms it in Step I.1, kept until the develop
    run finishes)
  - `task0001/` … — per-task worktrees (created when a task is launched,
    removed after its merge)
- `merge-task.sh` advances `refs/heads/em-workflow/{feature}/integration` via
  `update-ref` WITHOUT any checkout. This is only safe because the integration
  branch's own worktree is never used for uncommitted work while task
  implementers run, and the branch is never checked out in the user's main
  working tree. **After every wake-phase reconcile that merges/cleans up
  tasks, refresh the integration worktree**:
  `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
  (safe: the integration worktree never carries uncommitted state across
  turns — every workflow.yaml / document write, in every phase, is followed
  by a `commit-docs.sh` commit in the same step; NFR2).
- **exit-4 recovery** (bounded; applies to every `commit-docs.sh` call site
  in the implement phase EXCEPT Step I.2.c's route-back commit (carved out
  below) — for example, Step I.1's baseline commit, Step
  I.2.a's launch-time task status / task branch write, Step I.2.b's
  wake-phase commit, Step I.2.c's rejected-path terminal status commit,
  Step I.2.c's abort-phase terminal status commit, and Step I.3's
  implement-completed / completed-commit write): exit 4
  means a concurrent
  `merge-task.sh` advanced the branch ref
  between that call site's last refresh and its commit attempt. Recovery:
  refresh the integration worktree again (the `reset --hard` above), RE-CAPTURE
  the tip (`git -C {integration_worktree} rev-parse HEAD`) and use the fresh
  value as `commit-docs.sh`'s third argument on the retry, re-apply the SAME
  intended state transition on top of the refreshed tree — re-derived from
  source (the recorded base_commit, or the journal/report facts), never a
  replay of a stale diff — and retry `commit-docs.sh` once. A second exit 4
  stops the phase immediately with a report naming the call site and the
  task(s) involved; never loop unbounded. The single carve-out is Step
  I.2.c's **route-back** commit — distinct from the rejected-path terminal
  status commit enumerated above, which IS bound by this bounded recovery —
  unreachable for exit 4, tied to the widened I.2.c gate below. The
  unreachability proof enumerates the paths able to advance
  `refs/heads/em-workflow/{feature}/integration` during a develop run:
  `merge-task.sh`, run only by this feature's implementers against this
  integration branch, and the orchestrator's own `commit-docs.sh` calls
  elsewhere in this phase, which never race each other because the
  orchestrator is single-threaded (one turn runs at a time) and every
  `commit-docs.sh` invocation additionally serializes on the shared lock.
  The widened I.2.c gate's `in_progress` union rule — blocked when
  workflow.yaml reports a task `in_progress` OR Step I.2.b's
  last-event-per-task rule reports a task in-flight — excludes the first
  path: route back proceeds only when
  no implementer of this feature can be running, so no `merge-task.sh` call
  against this branch can be in flight either; therefore no concurrent ref
  advance can occur between the route-back call site's refresh and its
  commit attempt. The residual assumption is that no process outside this
  develop run advances this ref; the route-back call site's own
  stop-with-report terminal (Step I.2.c below) covers the case where that
  assumption fails and an unexpected non-zero exit occurs there anyway.
- Every workflow artifact — `feature-docs/{feature}/` (REQUIREMENTS.md,
  SPEC.md, workflow.yaml, IMPLEMENTATION.md, VERIFICATION.md, tasks/,
  reviews/, retrospect.yaml), `test/README.md`, `design-system/` — is written
  directly at its project-relative path inside the integration worktree, each
  write followed by a `commit-docs.sh` commit (`docs({feature}): {summary}`).
  Nothing is ever written to the main working tree by the workflow (the sole
  exceptions are the gitignore-guard `.gitignore` append and the final Step C
  merge below). There is no separate main-tree copy of any artifact and no
  copy/sync step at any phase boundary.
- At develop completion the user chooses — via AskUserQuestion — between
  merging the integration branch into `base_branch` (a normal `git merge` in
  the main working tree after a cleanliness check, then `git branch -d`),
  keeping the branch (the batch default — no merge, no push, no PR), or
  pushing it and opening a PR via `gh pr create`. In every variant the
  integration worktree is removed first, freeing the branch for checkout from
  the main working tree; only the merge variant deletes the branch.

## Step I.0: Preconditions

1. Read `feature-docs/{feature}/workflow.yaml`. Require: `create-plan` step
   `completed`, non-empty `tasks`, every task has `plan` / `files` /
   `skills` / `domains` / `complexity`.
2. **Fail-closed identifier validation gate**: `feature` MUST match
   `^[a-z0-9][a-z0-9-]*$` and every task id in `tasks` MUST match
   `^task[0-9]+$`. Validate BEFORE any of these values are interpolated into
   any shell command in Step I.1/I.2 (branch names, worktree paths, `git
   worktree add`/`remove` and `git branch` targets) — these validated values
   are the ONLY forms that may be
   interpolated there. A non-matching value ABORTS the phase with a clear
   error naming the offending value; never sanitize, never proceed (same
   fail-closed discipline as the changed_files path gate in
   review-phase.md). Rationale: `feature` arrives from a cloned repository's
   directory name and task ids from repository-controlled workflow.yaml, so
   both are attacker-influenceable inputs.
3. Verify the environment merge-task.sh depends on:
   - git ≥ 2.40, probed with the EXACT flag combination the script uses:
     `git merge-tree --write-tree --name-only HEAD HEAD` exits 0
     (`--name-only` landed in 2.40 — probing plain `--write-tree` would
     false-pass on 2.38/2.39 and fail at merge time).
   - `command -v flock` succeeds — flock is a util-linux tool, absent on
     stock macOS; without it every merge exits 2.
   On failure abort the phase with a clear message naming the missing piece.
4. Resolve `MERGE_SCRIPT=${CLAUDE_PLUGIN_ROOT}/scripts/merge-task.sh`;
   fail-closed with the same trusted-root fallback discipline as the review
   protocol (search `$HOME/.claude/plugins` / `$HOME/.claude/skills` with
   path filter `*/em-workflow/*/scripts/*`, never cwd).
5. **Rework re-entry precondition**: when this phase is entered because
   review or verify sent `implement` back to `pending` (rework, not a fresh
   first pass), require at least one task in `tasks` whose
   `status == pending` — this is Invariant 1 of
   `references/rework-task-synthesis.md`: the synthesis step that flips
   `implement` to `pending` never does so without registering a pending
   rework task alongside it. Entering this phase with every task `merged`
   (or otherwise none `pending`) is therefore a protocol error, not a fresh
   idle state to wait out: ABORT the phase immediately with a clear report
   naming the offending workflow.yaml state, rather than looping through
   Step I.2 with nothing to launch.

## Step I.1: Confirm the integration worktree, record the implement baseline

The integration branch and its worktree already exist by this point (Branch
& Worktree Model above) — created at create-spec Phase 3 and, on a resume
where the branch survived but its worktree was removed, re-materialized by
develop Step A's discovery. This step creates neither; it runs the
gitignore guard and records the implement-phase baseline.

**Pre-step — .gitignore guard**: dispatch
`Task(subagent_type="em-workflow:gitignore-guard")` with `project_root`. It
probes `git check-ignore` for `.claude/worktrees/` coverage and, only when
not covered, appends `.claude/worktrees/` to the root `.gitignore` (creating
the file if absent). The edit stays uncommitted — committing it is the
user's choice; the develop completion merge tolerates exactly this diff. A
`failed` report aborts the phase (un-ignored worktree contents would pollute
`git status` in the main tree).

```bash
WT_ROOT="$(git rev-parse --show-toplevel)/.claude/worktrees/em-workflow/{feature}"
BASE_COMMIT=$(git -C "$WT_ROOT/integration" rev-parse HEAD)
```

`$BASE_COMMIT` is the integration branch's HEAD at implement start —
everything create-spec, design, and create-plan already committed to it.
`base_commit` は初回のみ記録する — resume/rework 再突入では絶対に上書きしない。
Record in workflow.yaml: only when `workflow[implement].base_commit` is
absent/unset, set `workflow[implement].base_commit = $BASE_COMMIT` (first
implement entry for the feature); on resume (implement already
`in_progress`) or rework re-entry (implement `pending` after review/verify
sent it back) the existing `base_commit` value is preserved unchanged, per
`references/rework-task-synthesis.md` Section 10 point 3 / Section 11
Invariant 5. In all cases set `implement` status to
`in_progress`; commit the update with
`commit-docs.sh "$WT_ROOT/integration" "docs({feature}): implement phase start" "$BASE_COMMIT"`
(the third argument is `expected_base_tip`; exit-4 recovery: Branch &
Worktree Model above).

## Step I.2: Task loop (work queue, background launch + wake-phase refill)

There is NO ordering mechanism between tasks. `max_parallel_implementers`
(default: 6, `MAX_PARALLEL_IMPLEMENTERS` in IMPLEMENTATION.md) is a hard cap
on how many implementer `Task()` calls may be in flight at once — the same
constant the Stop hook enforces; both sites stay verbatim-identical. File
overlap between concurrent tasks is allowed: merge conflicts are an expected
path, resolved by each implementer's parent-side-adoption protocol
(worktree-task-workflow skill; merge-task.sh serializes concurrent merges
via flock).

The loop alternates two phases across turns: a **launch phase** (the turn
ends immediately after launching) and a **wake phase** (entered when an
implementer's `Task()` call returns / a subagent completion notification
arrives). There is no synchronous fan-out-and-wait: the orchestrator never
blocks a turn waiting on implementers; it launches, ends the turn, and
reconciles on the next wake.

### I.2.a: Launch phase

Determine the in-flight set and the unlaunched task set by replaying the
journal (state derivation rule; never carry in-flight state across turns
from memory) — read
`{project_root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl`
line-by-line and reconcile with workflow.yaml `tasks.*.status`. Select
unlaunched tasks (no journal event yet and `status != merged`, ascending
task-id order) up to `min(6 - in_flight_count, count(unlaunched))`.
Recycled task id: workflow.yaml's status wins over a stale journal event
here — a task whose workflow.yaml `status` is `pending` while the
journal's last event for that id is `failed` counts as **unlaunched**, not
failed. This carve-out is deliberately scoped to `failed` only, to stay
consistent with `queue_launch_guard.py`, which reads only the journal's
last event (never workflow.yaml) and allows a post-`failed` launch as the
legitimate retry path. A task whose journal last event is `launched` is
always in-flight, regardless of workflow.yaml `status` — never reinterpret
it as unlaunched, since the launch guard would deny that launch. Reason:
I.2.c's route back to planning is the only writer that resets a task's
status to `pending`, and no re-planning pass ever re-issues a retired task
id to a different task — `references/workflow-patch.md`'s re-planning
task-id allocation rule (cited here, never restated) allocates every new
id above the highest the feature has ever registered, so the `pending` +
`failed` combination arises only from I.2.c's own reset of a task's own
prior `failed` status, never from a task inheriting a different task's
retired id. Given I.2.c's route-back precondition below, which admits only
tasks with a terminal journal last event, and the allocation rule's
guarantee that a `replace_all` never re-issues a retired id, a task can
only ever carry its OWN journal's terminal event — so workflow.yaml
`status: pending` combined with journal last event `launched` can never
arise. Because Step I.2.c's route-back gate below blocks route-back
whenever any task's journal last event is `merged` — read from the
journal directly, independent of the ancestor check — that gate never
admits route-back while such an event stands. No retired task id is ever
re-issued, so a task whose workflow.yaml `status` is `pending` can never
carry an inherited `merged` journal last event; the recycled-task-id
carve-out above stays correctly scoped to `failed` only. The
recycled-task-id carve-out above is applied by two parties: the
orchestrator's own interpretation of the journal (this rule), and the Stop
hook, `queue_stop_guard.py`, which reads `tasks.{T}.status` and applies the
identical carve-out itself
(see the Stop-hook bullet under 'Supporting cast: journal, hooks, resume'
below, which states the same classification and cites the classification
table). The other three queue hooks — `queue_launch_guard.py`,
`queue_failure_net.py` and `queue_taskstop_net.py` — derive a task's state
from the journal's last event alone and never consult `tasks.{T}.status`.
The full per-hook classification is the hook classification table under
'Supporting cast: journal, hooks, resume' below, which this paragraph and
the Stop-hook bullet both cite as its source. The journal itself stays
append-only (see Supporting cast below) — only the interpretation of its
events is scoped by this rule.

The other three queue hooks detect a task as **unlaunched** solely from the absence of
any journal event for that task id — never from `tasks.{T}.status`.
`queue_stop_guard.py` is the exception: as described above, it also reads
`tasks.{T}.status` to apply the recycled-task-id carve-out that reclassifies
a `failed` + `pending` task as unlaunched. This is
narrower than the orchestrator's own selection rule above, which
additionally excludes any task whose `status` reads `merged`; the hooks
carry no equivalent exclusion. This divergence is recorded, not fixed: the
hooks are fail-open nets, not authorities (see 'Supporting cast: journal,
hooks, resume' below), and the orchestrator protocol above together with
the I.2.a resume guard remain the authoritative source of task state.
Tasks whose reconciled state is `failed` are NEVER selected here: a failure
always routes through I.2.c's user decision first (FR1 — no automatic
retry). Only after the user chooses "retry" is that task re-dispatched (on
its kept worktree via the resume guard below); the launch guard then admits
it because a post-`failed` launch is the legitimate retry path.

For each selected task T, create its worktree:

```bash
git worktree add -b "em-workflow/{feature}/{T}" "$WT_ROOT/{T}" \
    "em-workflow/{feature}/integration"
```

Branch point = integration branch AT THIS MOMENT (includes every task merged
so far). Set `tasks.{T}.status = in_progress`, `tasks.{T}.branch` in
workflow.yaml.

**Resume guard**: before running `git worktree add -b` for task T, check
whether `em-workflow/{feature}/{T}` and/or `$WT_ROOT/{T}` already exist (this
happens on re-entry after a prior failed/interrupted run whose worktree was
kept for diagnosis per I.2.c, or an in-flight retry). Do NOT run
`git worktree add -b` blindly in that case:
- Retry on the same worktree (user chose "retry" in I.2.c): reuse the
  existing worktree as-is and re-launch the implementer against it.
- Clean re-attempt (fresh implementer, no prior branch state to keep): first
  `git worktree remove --force "$WT_ROOT/{T}"` and
  `git branch -D "em-workflow/{feature}/{T}"`, then recreate the worktree and
  branch from the current integration branch as above.

Before launching, verify every `project_commands` string (build/test/format)
used by the selected tasks is in the approval store (`bash_guard.py
--list`; command-execution-protocol.md). Anything unapproved: run the
protocol's approval gate now (AskUserQuestion → `--record`) — the PreToolUse
hook denies unapproved workflow.yaml strings inside implementer worktrees,
so approving up front avoids mid-launch failures. Commands the user rejects
stay unapproved: the hook denies them and the implementer reports failure
instead of working around it (worktree-task-workflow skill). Batch mode:
auto-record instead of asking; refusal patterns still hard-fail
(`references/batch-policies.yaml`'s `create-spec.command-approval` entry —
the same approval gate, regardless of which phase's task launch triggers
it).

Launch each selected task as a BACKGROUND `Task(subagent_type="em-workflow:implementer")`
call. Synchronous fan-out-and-wait for a batch of implementers is explicitly
FORBIDDEN: it reintroduces the barrier this feature removes, and it starves
the Stop hook of the turn-end event it needs to catch a forgotten refill.

Prompt payload per task:

```
# Task assignment
task_id: {T}
worktree_path: {absolute path to $WT_ROOT/{T}}
task_plan_path: {absolute path to the integration worktree's feature-docs/{feature}/tasks/{T}.md}
implementation_md_path: {absolute path to the integration worktree's feature-docs/{feature}/IMPLEMENTATION.md}
lessons_path: {absolute path to the MAIN working tree's feature-docs/LESSONS.md; OMIT this line when the file does not exist — LESSONS.md is the one cross-feature artifact that stays outside the integration worktree}
parent_branch: em-workflow/{feature}/integration
merge_script: {resolved MERGE_SCRIPT absolute path}
skills_to_load: {tasks.{T}.skills, prefixed em-workflow: — e.g. ["em-workflow:backend-impl"]; may be empty}
project_commands:
  build: {workflow.yaml project.components.*.build_command}
  test: {...test_command}
  format: {...format_command}
expected_files: {tasks.{T}.files}
tests_yaml_path: {absolute path to $WT_ROOT/{T}/test-docs/{feature}/{T}.tests.yaml}
```

Do NOT inline task-plan content into the prompt — the implementer Reads its
plan itself. Command strings come from workflow.yaml and are subject to the
implementer's command-approval discipline (worktree-task-workflow skill).

`tests_yaml_path` points INSIDE the task's own worktree, never into the
integration worktree: the implementer writes its test record there and
commits it with the implementation, so the record merges into the parent
along with the code it describes. One file per task
(`{T}.tests.yaml`) means parallel tasks never write the same path and the
records cannot conflict. It carries the implementer's `baseline_failures` /
`final_failures` (which tests were already red when the task started, so a
later failure is attributed by set difference instead of re-investigated)
and the AC → test mapping with the observed red for each criterion. Build
the path yourself and pass it — the implementer does not know `{feature}`
and must not derive it from other paths.

**End the turn** immediately after launching — no polling, no synchronous
wait. In a `--batch` run, this turn's final assistant message is the
marker line `references/batch-mode.md` defines and nothing else. The
PreToolUse(Task|Agent) launch guard (`queue_launch_guard.py`) records
each allowed launch as a `launched` journal event as the call goes through
(the only writer of `launched`); it also denies double-launching a task
that is already in flight or already merged, as a net under the
orchestrator's own bookkeeping.

### I.2.b: Wake phase (on completion notification)

Triggered whenever a launched implementer's `Task()` call returns.

1. **Reconcile** — replay the journal (last-event-per-task rule: no event →
   unlaunched; `launched` → in-flight; `merged` → merged; `failed` →
   failed — except that a task whose journal last event is `failed` AND
   whose workflow.yaml `status` is `pending` is unlaunched instead, the
   recycled-task-id rule in I.2.a above; a `launched` last event is always
   in-flight regardless of workflow.yaml `status`) and cross-check against
   git actual state, trust-but-verify:
   - Worktree/branch existence, PLUS live-agent absence, for tasks the
     journal claims are in-flight — the check FAILS only when a task's
     journal last event is `launched`, the task worktree and the task
     branch both exist, AND the Agent index writer's orchestrator-read
     rule — cited from its own bullet under 'Supporting cast: journal,
     hooks, resume' below, not restated here — resolves no live agent for
     that task's recorded agent. This is the allowed-but-never-started
     (or since-died) state: I.2.a creates both artifacts before the
     launch call that records `launched`, but a live agent is what
     distinguishes that stale state from a normally in-flight implementer
     that also has both artifacts. A task whose recorded agent IS live is
     never touched by this check, regardless of how long it has been
     running — this recovery only ever acts on tasks the current wake
     did not just hear back from and that have no live agent, which is
     what keeps it from conflicting with I.2.c's drain guarantee that a
     failure never rolls back or cancels siblings already running. A
     failed check does not reclassify the task by itself: the last-event
     rule owned by I.2.a above stays authoritative, cited here rather
     than restated. Effect of the failure: it triggers the
     recovery below and names the task in the phase report. Recovery: the
     wake phase stops the (already-known-dead) recorded agent through the
     harness stop tool; the stop-tool recorder — cited from its own
     bullet under 'Supporting cast: journal, hooks, resume' below, not
     restated here — records the task's terminal `failed` event, so the
     next replay reconciles the task as `failed` and it reaches the
     normal failed handling in I.2.c, where retry and route-back are both
     available. Residual: when the Agent index lookup is ambiguous rather
     than cleanly resolving to "no live agent", the journal is unchanged,
     the task stays in-flight, the route-back gate blocks, and the phase
     takes the existing gate-rejected terminal (I.2.c) with the task
     named in the report. A second, independent condition triggers this
     same recovery without an Agent index lookup: a task's journal last
     event is `launched` AND the task worktree does not exist AND the
     task branch does not exist — neither artifact remains to correlate
     a live agent against, so this condition is checked on its own,
     never gated on the Agent index resolving "no live agent". This
     recovery runs during this wake-phase reconcile step, hence before
     I.2.c's user-facing menu is offered.
   - `git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration`
     for tasks the journal (or the implementer's own report) claims are
     `merged` — a claim that fails this check is NOT merged; never mark a
     task merged on self-report or journal entry alone. That task's
     reconciled state instead becomes `failed` — the same treatment as
     any other implementer failure — for the purpose of I.2.c's surfaced
     report and the route-back gate's admissibility check, but no writer
     in this design records that `failed` state to the journal: the
     journal's own last event for that task keeps reading `merged`
     permanently. Because the launch guard (its own bullet under
     'Supporting cast: journal, hooks, resume', not restated here) reads
     only the journal's last event, it denies any retry of this task
     forever. **Retry is therefore not an available option** for a task
     reconciled this way, even though it is offered for every other
     failed task in I.2.c; the only ways out are abort, or a user/operator
     correcting the journal or branch state by hand before retrying.
2. **Refresh the integration worktree FIRST** (Branch & Worktree Model):
   `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`,
   then capture `RECONCILE_TIP=$(git -C {integration_worktree} rev-parse HEAD)`.
   Any reconcile that observed a ref advance means a concurrent
   `merge-task.sh` moved the branch tip via `update-ref` without touching
   this worktree — refreshing before step 3's edit is what keeps that edit
   built on the CURRENT tip instead of a stale one a later commit could lose
   work against.
3. **Update workflow.yaml, then commit**: collect each returning
   implementer's completion report — `{"task_id", "status": "merged"|"failed",
   "merge_commit", "conflict_retries", "tests": "pass"|"fail",
   "deviations": [...], "notes"}` (malformed/missing report → treat as
   `failed`) — set `tasks.{T}.status = merged` for every task verified
   merged, `= failed` for every task whose step 1 reconciled state is
   `failed` or whose report is `failed`/malformed, and, for each admitted
   deviation (the Deviation auto-addition rule below), an append to that
   same task's `files`. This step's enumeration of what it writes to
   `workflow.yaml` is exactly these two: the `tasks.{T}.status` update and
   this `files` append — both performed by the orchestrator, on the
   worktree just refreshed in step 2, in the same commit as the status
   update: never a second write, never a second commit, never a new patch
   operation. The append is stated as an append: an existing entry is
   never removed or rewritten by this rule, and re-admitting an already
   listed path is a no-op. Then commit, with a single-line message
   mode-independently (the `$RECONCILE_TIP` third argument is
   `commit-docs.sh`'s `expected_base_tip` check value):
   `commit-docs.sh {integration_worktree} "docs({feature}): implement wake
   phase reconcile" "$RECONCILE_TIP"` (exit-4 recovery: Branch & Worktree
   Model above — on a second exit 4, stop the wake phase with a report
   naming the task(s) involved rather than looping).

   **Deviation auto-addition rule**: a reported deviation (the
   `deviations` entries in that same completion report — the completion
   report stays the channel the evidence arrives on, the same
   completion-report `deviations` channel already defined above, and is
   never itself the record's resting place) is auto-added to the declared
   change set derivation — defined in
   `references/phases/create-plan-phase.md`, cited here and never
   restated — only when it carries, as three named parts, evidence that an
   existing acceptance criterion would otherwise be dropped: the path
   being added; the identifier of the acceptance criterion or requirement
   that would otherwise be dropped — an `AC-n` of the reporting task's own
   plan, restricted the same way as the requirement id below: existence
   means the AC-n was already present in that plan document as written by
   create-plan / rework-planner, never something the reporting
   implementer's own branch added to the plan document — or a requirement
   id already registered in `workflow.yaml`; and
   how it fails without the path, stated as an observable outcome (a named
   test that cannot be written or cannot pass), never as a preference. The
   named identifier must resolve to something that exists — for a
   requirement id, existence means it is already registered in
   `workflow.yaml` prior to this report, never something the report
   itself introduces. The path being added must independently pass the
   same shape check `is_safe_relative_path` applies to every
   patch-written `tasks.*.files` entry — cited here, not restated;
   `is_safe_relative_path` does not check for symlink escapes, and no
   such check is claimed — applied here by
   the orchestrator itself before the append, not merely asserted by the
   report; and it must not fall under a workflow control path — matched,
   like every other `tasks.*.files` entry, as a project-relative path:
   `.claude/**`, `em-workflow/**` (the whole plugin tree —
   `references/**`, `.claude-plugin/**`, `hooks/**`, `scripts/**`,
   `agents/**`, `skills/**`, and so on, not individually enumerated),
   `CLAUDE.md` (including nested occurrences), `.github/workflows/**`,
   `feature-docs/*/workflow.yaml`, `feature-docs/*/phase-state/**`, or
   `feature-docs/*/tasks/**`.
   When the target repository is this plugin's own repository,
   `em-workflow/**` matches its project-relative occurrences there
   exactly as any other path does — this rule is not suspended for that
   case. Such a path is never
   auto-added regardless of how the other two parts read. A deviation
   failing any one of these parts — a missing identifier, an identifier
   that resolves to nothing or was not already registered, a path that
   fails the shape check, a path under a workflow control path, or a
   rationale of implementer convenience, a nicer structure, an unrelated
   cleanup — is not auto-added; it surfaces as an ordinary deviation and
   the containment check (observed change set ⊆ declared change set)
   handles it exactly as before, and unjustified scope expansion is
   still stopped. The containment check itself is unchanged by this
   rule. Every admission or rejection of a deviation under this rule —
   admitted path, or declined path with which check it failed — is
   listed in this wake phase's own report, and, for a `--batch` run,
   also in the run report.

   **Where the decision persists**: an admission's audit record is the
   `files` entry this step just appended plus the wake commit that added
   it — nothing further is written for it. A decline's audit record is the
   reason recorded in this wake phase's own report for that task, naming
   which of the three evidence parts was missing or unresolved. No new
   phase-state field is introduced for this record (D7 unchanged) — the
   channel is the one this step already defines.

   **Batch mode**: for a `--batch` run, a decline's audit record instead
   is written to `feature-docs/{feature}/phase-state/batch-audit.yaml`
   (`references/phase-state.md`'s batch audit record file) in the same
   wake commit — one entry per declined task, naming the `task_id` and
   which of the three evidence parts was missing or unresolved — rather
   than in this wake phase's own report; the run-report obligation stated
   above for a `--batch` run is satisfied by reading that persisted
   record rather than this wake phase's own report.
   An admission's audit record is unchanged. An interactive run keeps
   recording a decline in this wake phase's own report exactly as before.
4. **Clean up** every newly-merged task's worktree and branch:
   ```bash
   git worktree remove "$WT_ROOT/{T}"
   git branch -D "em-workflow/{feature}/{T}"   # -D: merge already verified
                                               # via merge-base --is-ancestor.
                                               # -d would REFUSE here: the
                                               # orchestrator's HEAD is
                                               # base_branch, which does not
                                               # contain the task branch (it
                                               # was merged into integration,
                                               # not base_branch).
   ```
5. **Refill**: if no task's reconciled status is `failed`, re-enter the
   launch phase (I.2.a) with the freed slot(s) and any still-unlaunched
   tasks, then end the turn again. If every task is now `merged`, proceed to
   Step I.3.

**Batch mode**: in a `--batch` run, this applies only when step 5 re-enters
the launch phase (I.2.a) and ends the turn again — in that case, this wake
turn's final assistant message is the marker line `references/batch-mode.md`
defines and nothing else: step 1's reconcile enumeration, step 4's cleanup
listing and step 5's refill narration are withheld from the main context,
while the reconcile itself, the wake commit in step 3, the journal it
records against, the worktree cleanup in step 4 and step 5's re-entry into
I.2.a are unchanged. If instead every task is now `merged` and step 5
proceeds to Step I.3, this turn has not reached a terminal state and does
not end here, so the marker line is not emitted; execution continues into
Step I.3 and beyond, with output suppression still applying to this wake
turn's own steps 1/4/5 narration as above.

### I.2.c: Failed handling

The moment any task's reconciled status is `failed`: stop launching new
tasks (do not refill), let already in-flight tasks drain (their wake
notifications still arrive and are reconciled normally — a failure never
rolls back or cancels siblings already running), then surface the failure
to the user with the implementer's notes and offer, via AskUserQuestion:

- **retry** — dispatch a fresh implementer on the kept worktree (I.2.a
  resume guard).
- **route back to planning** — a task that cannot be implemented as planned
  means the plan (or the spec behind it) is wrong; fix it upstream, not
  here. This automatic re-entry applies only when the gate holds: no task
  has status `merged`, and no task has status `in_progress` — both
  re-read from workflow.yaml task statuses at this point, as an
  independent check, not inferred from the drain above (which only
  describes the normal case, not the admissibility test); a stale or
  unretired `in_progress` entry left by a crashed implementer blocks this
  path exactly as a `merged` task does. The `merged` half is likewise a
  union of two independent sources, either of which blocks: workflow.yaml
  reporting a task `merged`, OR Step I.2.b step 1's reconciled state
  reporting a task `merged` (journal last event `merged`, verified by
  `git merge-base --is-ancestor` as that step already requires) — cited
  here as the owning rule, not restated. The `in_progress` half is a union
  of two independent sources, either of which blocks: workflow.yaml
  reporting a task `in_progress`, OR Step I.2.b's last-event-per-task
  rule reporting a task in-flight (a `launched` last event, with the
  recycled-task-id carve-out that step already defines) — cited here as
  the owning rule, not restated. The second source is what makes the gate
  admit route-back only when every task in the current plan whose journal
  carries any event has a terminal journal last event (`merged` or
  `failed`) — the planner's `replace_all` recycles every id, not only the
  failed ones, so a task with no journal event at all has nothing to
  inherit and never blocks route-back. A third conjunct blocks
  independently of both halves above, closing a gap neither sees: whenever
  the last-event-per-task replay alone reports any task's journal last
  event as `merged`, route-back is inadmissible — this holds regardless of
  the `git merge-base --is-ancestor` verification the `merged` half's
  second source requires, so it blocks a task whose journal reports
  `merged` even when that verification fails. The reason is one fact,
  cited here from its owning bullet under 'Supporting cast: journal,
  hooks, resume' below rather than restated: the launch guard denies a
  launch whose journal last event is `merged`, so a renumbered task id
  inheriting such an event could never be launched. This narrows the
  terminal journal last event named just above: of `merged` and `failed`,
  only the failed one leaves a recycled id launchable. This conjunct is
  never narrowed to admit route-back for that state: no recycled id can
  ever inherit a journal `merged` the launch guard denies through this
  phase's own write set. The state it protects still has a way out that
  is not this section's own gate-rejected or abort terminal: when the
  ancestor verification fails for a task the journal (or its own report)
  claims `merged`, Step I.2.b step 1's reconciled state for that task is
  `failed` — cited there, not restated here — so the ordinary retry /
  route back to planning / abort menu opens for it like any other
  failure; choosing retry there reaches the launch guard's permission
  denial, which the harness-level-failure path under 'Failure
  containment' below diagnoses, an outcome reached without selecting
  abort. A task the journal
  reports in-flight whose worktree and branch are both gone is decided
  elsewhere — Step I.2.b step 1's recovery, cited there, not here. Refresh
  the integration worktree first (`git -C "$WT_ROOT/integration"
  reset --hard em-workflow/{feature}/integration`), then capture
  `ROUTEBACK_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)`,
  then make one ordered workflow.yaml write set over the reset target
  set — every task whose Step I.2.b step 1 reconciled state is
  `failed`: set `create-plan` to `needs_update`, set the `implement`
  step back to `pending`, record each such task's failure reason (the
  implementer's report `notes`) in `tasks.{T}.notes`, and set
  `tasks.{T}.status` back to `pending` for every task in that set — the
  gate above already established that no task is `merged` or
  `in_progress` at this point, so the result is that no task is left
  `merged` or `in_progress` or `failed`, which is exactly what makes the
  planner's `replace_planning` operation admissible on re-entry
  (`references/workflow-patch.md`'s `replace_all` permission
  conditions own the full condition set and the protocol-error rule —
  not restated here). Commit that write set next, BEFORE any cleanup:
  `commit-docs.sh "$WT_ROOT/integration"
  "docs({feature}): implement route back to planning" "$ROUTEBACK_TIP"`
  (exit 4 cannot occur at this call site — see the Branch & Worktree
  Model's exit-4 recovery bullet above for why; an unexpected non-zero
  exit here stops the phase immediately with a report, at a point where
  no worktree or branch has been deleted). Only once that commit
  succeeds, clean up worktrees and branches for exactly the tasks the
  write set just reset — confirmed not merged; a task whose reconciled
  state is `merged` is never a cleanup target, whatever workflow.yaml
  says (`git worktree remove --force
  "$WT_ROOT/{T}"`; `git branch -D "em-workflow/{feature}/{T}"`, for
  every {T} just reset) — this order's one residual leftover state is the
  commit succeeding and the cleanup not yet running, i.e. stale
  worktrees for tasks now `pending`, which Step I.2.a's resume guard and
  its recycled-task-id rule already cover. End the phase with a
  clear report; create-plan re-enters afterwards. The develop state
  machine does **not** stop on this `needs_update` —
  `skills/develop/SKILL.md` Step B's stop-condition-3 precedence clause
  ("停止条件 3 との優先関係") owns that precedence and dispatches the
  planner with the step still `needs_update` (not restated here). The
  planner re-scopes the failed task (split it, change the approach) — or,
  when a requirement itself must be dropped, routes that change through
  the normal SPEC.md update path first. When the gate does not hold —
  because a task has status `merged`, because Step I.2.b step 1's
  reconciled state reports a task `merged` though workflow.yaml does
  not, because a task has status `in_progress`, because Step I.2.b's
  last-event-per-task rule reports a task in-flight, or because the
  last-event-per-task replay alone reports a task's journal last event
  as `merged` though Step I.2.b step 1's reconciled state does not
  verify it — this automatic
  re-entry does not apply:
  `create-plan` is NOT set to `needs_update`. The phase instead refreshes
  the integration worktree first (the same `reset --hard` as above),
  captures `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse
  HEAD)`, sets the `implement` step's `status` to `failed` in
  workflow.yaml — the single write this path makes — and commits exactly
  that write: `commit-docs.sh "$WT_ROOT/integration" "docs({feature}):
  implement route-back gate rejected" "$TERMINAL_TIP"`. There is no
  route-back write set, no worktree/branch cleanup and no route-back
  commit on this path — the terminal status write and its own commit are
  the ONLY side effect. The phase then reports and returns control to
  the user via develop's stop condition 3, which fires on the next Step B
  iteration reading `implement: failed` — the same terminal as the
  "abort phase" option below. No retry loop, no alternative recovery
  route, and no degraded route back is offered for this path.
- **abort phase** — refresh the integration worktree first (the same
  `reset --hard em-workflow/{feature}/integration` the rejected path
  above uses), capture `ABORT_TIP=$(git -C "$WT_ROOT/integration"
  rev-parse HEAD)`, set the `implement` step's `status` to `failed` in
  workflow.yaml — the single write this path makes — and commit exactly
  that write: `commit-docs.sh "$WT_ROOT/integration" "docs({feature}):
  implement phase aborted" "$ABORT_TIP"` (no `create-plan`
  `needs_update`, no task status or notes write set, no worktree or
  branch cleanup — the terminal status write and its own commit are the
  ONLY side effect). The phase then reports and returns control to the
  user via develop's stop condition 3, which fires on the next Step B
  iteration reading `implement: failed`.

There is NO skip option: a task is either merged, retried, or re-planned —
never dropped mid-phase. "実装完了 = 親ブランチへのマージ完了" admits no
carve-out; scope changes belong to the planning/spec layer, not to the
implement phase.

The drain narration below and the retry narration below are withheld
from the main context in `--batch` (`references/batch-mode.md`); the
task status, the `implement` step's `failed` write and their commits are
unchanged. The **abort phase** branch below is a stop under
`references/batch-mode.md`'s stop/abort exception, so its report keeps
its full output.

Batch mode (`references/batch-mode.md`'s Non-packet gates table,
`implement.failed-task`): no AskUserQuestion —
after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a
resume guard). A task that fails a second time → **abort phase**: refresh
the integration worktree, capture the tip, then set and commit the
`implement` step's `status` to `failed` via `commit-docs.sh` (no
`create-plan` `needs_update`, no task status or notes write set, no
worktree or branch cleanup — the terminal status write and its own commit
are the ONLY side effect), then report and stop; control returns via
develop's stop condition 3, firing on the next Step B iteration reading
`implement: failed`. The external service cuts a follow-up task.
Route-back-to-planning is never taken automatically. Track the
retry-consumed state per task in `tasks.{T}.notes`.

### Supporting cast: journal, hooks, resume

**Journal** (`journal.jsonl`, sibling of the per-task worktree directories
under `.claude/worktrees/em-workflow/{feature}/`): a machine-written,
append-only event log — `launched` / `merged` / `failed`, one JSON object
per line, each carrying `task` and an RFC 3339 `at`. The orchestrator NEVER
writes it; only `merge-task.sh` and the journal-writing hooks below append
to it. The raw log is never rewritten or deleted — it is the primary source
for post-mortem diagnosis, distinct from workflow.yaml's LLM-managed
summary (full schema: IMPLEMENTATION.md's Journal contract).

**The hooks** (`em-workflow/hooks/`, wired in `hooks.json`):

Scope note: this section covers the queue loop's own hooks only. The same
directory also ships guardrail hooks unrelated to the queue (the gitleaks
scanners, `kill-guard.py`, `destructive-guard.py`) — those are documented in
`em-workflow/README.md`, are never consulted by this phase, and are outside
every classification below.

**Hook classification table** — source of truth for which of the four
queue hooks below read `tasks.{T}.status`; both I.2.a above and the
Stop-hook bullet below cite it as this classification's source.

| Hook | Classification |
|---|---|
| `em-workflow/hooks/queue_launch_guard.py` | does not read `tasks.{T}.status` |
| `em-workflow/hooks/queue_stop_guard.py` | reads `tasks.{T}.status` |
| `em-workflow/hooks/queue_failure_net.py` | does not read `tasks.{T}.status` |
| `em-workflow/hooks/queue_taskstop_net.py` | does not read `tasks.{T}.status` |

- **Stop hook** (`queue_stop_guard.py`) — fires when the orchestrator's turn
  ends. Replays the journal and workflow.yaml, applying the same
  recycled-task-id carve-out as I.2.a above — a task whose journal last
  event is `failed` and whose workflow.yaml `status` reads `pending`
  reclassifies as unlaunched, not failed; if refillable slots and
  unlaunched tasks exist and no task's reconciled state is `failed`, it
  BLOCKS (exit 2) naming the tasks to launch — catching a forgotten refill
  after a wake phase. Classification (hook classification table above):
  **reads** `tasks.{T}.status`, the sole exception among the four queue
  hooks named in I.2.a — matching I.2.a's classification exactly. A
  consecutive-block cap (3, tracked in a sidecar next to the journal)
  prevents it from wedging the session on unexpected state; exceeding the
  cap yields a warning and lets the turn end. Does not write the journal.
- **PreToolUse(Task|Agent) launch guard** (`queue_launch_guard.py`) — fires on
  every subagent-launch call (the tool is named `Agent` in current Claude
  Code versions, `Task` in older ones — both are matched); identifies
  em-workflow implementer launches and
  denies double-launching an already in-flight or already-merged task (a
  retry after `failed` is allowed). The sole writer of `launched` events.
- **Agent index writer** (`queue_agent_index.py`) — fires on the same
  subagent-launch call as the launch guard above, after the tool completes.
  For em-workflow implementer launches it appends one entry to that
  feature's agent index (`agents.jsonl`, a sibling of `journal.jsonl`),
  mapping every harness agent-identifier candidate it can recover from the
  launch response (the exact identifier field the response carries is
  unverified, so more than one candidate may be recorded per entry) to the
  launched task id and worktree path. It writes ONLY the agent index — it
  never touches `journal.jsonl` — and is fail-open exactly like every hook
  here: an unrecognized launch, an unparsable input, or a missing feature
  directory is a silent no-op. The index is diagnostic plumbing, not a
  second journal (workflow-schema.md states this explicitly): it carries no
  status semantics of its own, may be absent or stale, and is never a source
  of task status — only of the task/worktree a stop or a recovery check
  resolves to. It exists so the stop-tool recorder below and, per the
  Orchestrator-side read below, the orchestrator itself can each resolve a
  stop or a recovery check back to a task (full matching/staleness rule:
  IMPLEMENTATION.md's Agent index contract).
  **Orchestrator-side read** (I.2.b step 1's stale-`launched` recovery
  cites this rule, not restated there): for a task, the orchestrator
  selects that task's most recently appended entry; when the selected
  entry carries more than one identifier candidate, the orchestrator
  passes the first-recorded candidate to the harness stop tool; an
  unresolvable lookup (no entry for the task) or an ambiguous one (the
  selected entry names no usable candidate) resolves to NO LIVE AGENT for
  that task and stops nothing — this lookup resolves a stop target, it
  never supplies or overrides `tasks.{T}.status`.
- **SubagentStop failure net** (`queue_failure_net.py`) — fires when any
  subagent stops; for em-workflow implementers whose task has no `merged`
  event yet, appends `failed` — turning a swallowed or crashed implementer
  into a visible, actionable state instead of a silent stall. Always exits 0
  (never blocks the stop).
- **Stop-tool recorder** (`queue_taskstop_net.py`) — fires after the
  orchestrator's `TaskStop` tool call completes. A stop delivered through
  this tool does NOT reach the `SubagentStop` failure net above — this was
  confirmed empirically before this feature was planned: two implementers
  were launched identically into a throwaway journal, one stopped via the
  `TaskStop` tool and the other left to complete naturally; only the
  naturally-completed one produced a `SubagentStop`-triggered `failed`
  append, while the `TaskStop`-stopped one left only its `launched` line
  with no failure ever recorded (full probe table: IMPLEMENTATION.md's
  Investigation result). The recorder closes exactly that gap: it resolves
  the stopped agent to a task via the agent index above, replays the
  journal for that task, and appends `failed` only when the last event is
  not already terminal — idempotent with the failure net, so at most one
  `failed` line ever results for a given task regardless of which of the
  two writers fires (or if, on some future harness version, both do). Its
  reason string is distinct from the failure net's so a post-mortem can
  tell a deliberate stop from a swallowed crash.

All of the hooks above are fail-open nets, not authorities: on any
unexpected state (missing files, unparsable input, no active feature) they
exit 0 silently. The orchestrator protocol above plus the resume guard
remain authoritative; a hook wrongly blocking the session is worse than
missing one violation.

**Stale-`launched` caveat**: the launch guard appends `launched` at allow
time, before the subagent actually starts — if the `Task()` call is then
allowed but never actually runs, a stale `launched` line can persist with no
corresponding implementer in flight. This is bounded, never silently masked:
the Stop hook's consecutive-block cap prevents an infinite blocking loop
over a wedged slot, the wake-phase git-state reconcile (worktree/branch
existence check) triggers I.2.b step 1's recovery on the next reconcile
pass — the outcome that check produces is defined there, not restated
here — and, specifically for the deliberate-stop case, the stop-tool
recorder appends `failed` as soon as the `TaskStop` call completes,
closing the gap before a reconcile pass is even needed.

**Resume**: a `/em-workflow:develop` re-entry mid-implement rebuilds state
from three sources, never from memory: workflow.yaml (`tasks.*.status`), the
journal (last-event-per-task replay), and git actual state (worktree
existence, `merge-base --is-ancestor`). The agent index (`agents.jsonl`,
cited from the Agent index writer bullet above, not restated here) is
consulted alongside these as a resolution aid for stops and for I.2.b step
1's recovery check, not as a fourth state source — it carries no status
semantics of its own. The
I.2.a resume guard governs
worktree re-creation exactly as before; the wake-phase reconcile (I.2.b) is
what re-derives in-flight/failed/merged classification on that first
post-resume wake.

## Step I.3: Phase completion

When every task is `merged`: set `implement` step `status = completed`,
`completed_at_commit = $(git rev-parse "em-workflow/{feature}/integration")`.
There is no other way to complete this phase — a non-merged task always
resolves via retry, route-back-to-planning, or abort (I.2.c). Report overall
stats (tasks, conflict retries, failures) in 1-3 lines and return control to
the develop state machine (review phase follows; no test run here —
integrated verification is the review/verify phases' job).

## Failure containment

- One failed task never rolls back merged siblings (merges are already in
  integration history; review/verify phases evaluate the integrated result).
- An implementer that reports a conflict it could not resolve after the
  parent-side-adoption protocol (worktree-task-workflow skill) counts as
  `failed` — its report includes the conflicting files.
- Never run `git reset` / `git update-ref` on the integration branch from the
  orchestrator side to "undo" a merge; corrective work is a new task or a
  rework loop from the review phase.
- An implementer that fails at the **harness** level rather than returning a
  task result — the launch call comes back `is_error`, its output carries a
  permission denial, or it reports `skipped: true` unexpectedly — is not a
  planning problem and I.2.c's retry / route-back choice cannot be judged
  without knowing why it died. Diagnose it first per
  `references/workflow-failure-recovery.md` (dispatch `workflow-doctor` over
  the failed agents' JSONL logs), then surface the failure with that
  diagnosis included.
