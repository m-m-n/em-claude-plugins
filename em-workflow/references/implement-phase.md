# Implement Phase Protocol (em-workflow)

Read and executed inline by the `/em-workflow:develop` skill when the
`implement` workflow step is pending. The main session performs this
orchestration itself — parallel `Task()` fan-out only works from the main
context.

## Branch & Worktree Model (READ FIRST)

The workflow NEVER commits to, resets, or force-updates the user's branch or
the user's main working tree. All workflow commits land on a dedicated
integration branch, materialized in its own worktree:

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
  - `integration/` — the integration worktree (created in Step I.1, kept until
    the develop run finishes)
  - `task0001/` … — per-task worktrees (created when a task is launched,
    removed after its merge)
- `merge-task.sh` advances `refs/heads/em-workflow/{feature}/integration` via
  `update-ref` WITHOUT any checkout. This is only safe because the integration
  branch's own worktree is never used for uncommitted work while task
  implementers run, and the branch is never checked out in the user's main
  working tree. **After every wake-phase reconcile that merges/cleans up
  tasks, refresh the integration worktree**:
  `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
  (safe: that worktree holds no uncommitted work by invariant).
- The live `feature-docs/{feature}/` (workflow.yaml etc.) stays in the MAIN
  working tree, uncommitted, orchestrator-owned. It is copied + committed into
  the integration branch at phase start (Step I.1) and again at develop
  completion (so the merged result carries the final records). Untracked
  workflow-generated project docs (`test/README.md` from create-spec,
  `design-system/` from the design step) are committed alongside at phase
  start only (Step I.1) — that makes them visible in every task worktree and
  carries them to `base_branch` via the completion merge.
- At develop completion the user is offered — via AskUserQuestion — a merge of
  the integration branch into `base_branch` (executed as a normal `git merge`
  in the main working tree after a cleanliness check). After a successful
  merge the integration branch is deleted (worktree removed first, then
  `git branch -d`). Declining leaves the integration branch in place for
  manual handling.

## Step I.0: Preconditions

1. Read `feature-docs/{feature}/workflow.yaml`. Require: `create-plan` step
   `completed`, non-empty `tasks`, every task has `plan` / `files` /
   `skills` / `domains` / `complexity`.
2. **Fail-closed identifier validation gate**: `feature` MUST match
   `^[a-z0-9][a-z0-9-]*$` and every task id in `tasks` MUST match
   `^task[0-9]+$`. Validate BEFORE any of these values are interpolated into
   any shell command in Step I.1/I.2 (branch names, worktree paths, cp/rm
   targets) — these validated values are the ONLY forms that may be
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

## Step I.1: Create the integration branch (once per feature)

Skip if `parent_branch` already exists (resume case).

**Pre-step — .gitignore guard**: dispatch
`Task(subagent_type="em-workflow:gitignore-guard")` with `project_root`. It
probes `git check-ignore` for `.claude/worktrees/` coverage and, only when
not covered, appends `.claude/worktrees/` to the root `.gitignore` (creating
the file if absent). The edit stays uncommitted — committing it is the
user's choice; the develop completion merge tolerates exactly this diff. A
`failed` report aborts the phase (un-ignored worktree contents would pollute
`git status` in the main tree).

```bash
BASE_COMMIT=$(git rev-parse HEAD)
git branch "em-workflow/{feature}/integration" "$BASE_COMMIT"
WT_ROOT="$(git rev-parse --show-toplevel)/.claude/worktrees/em-workflow/{feature}"
mkdir -p "$WT_ROOT"
git worktree add "$WT_ROOT/integration" "em-workflow/{feature}/integration"
# Copy feature-docs into the integration worktree and commit them there:
mkdir -p "$WT_ROOT/integration/feature-docs"
cp -r "feature-docs/{feature}" "$WT_ROOT/integration/feature-docs/"
git -C "$WT_ROOT/integration" add feature-docs
# Bring along workflow-generated project docs (test/README.md from
# create-spec, design-system/ from the design step) ONLY while untracked:
# tracked copies are already in BASE_COMMIT, and user-modified tracked
# files are never committed on the user's behalf. File-granular on purpose
# — a partially-tracked design-system/ still gets its new files carried.
git ls-files -z --others --exclude-standard -- test/README.md design-system/ |
while IFS= read -r -d '' f; do
  mkdir -p "$WT_ROOT/integration/$(dirname "$f")"
  cp "$f" "$WT_ROOT/integration/$f"
  git -C "$WT_ROOT/integration" add -- "$f"
done
git -C "$WT_ROOT/integration" commit -m "docs({feature}): SDD artifacts at implement start"
```

Record in workflow.yaml: `base_branch`, `parent_branch`, and
`workflow[implement].base_commit = $BASE_COMMIT`. Set `implement` status to
`in_progress`.

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
instead of working around it (worktree-task-workflow skill).

Launch each selected task as a BACKGROUND `Task(subagent_type="em-workflow:implementer")`
call. Synchronous fan-out-and-wait for a batch of implementers is explicitly
FORBIDDEN: it reintroduces the barrier this feature removes, and it starves
the Stop hook of the turn-end event it needs to catch a forgotten refill.

Prompt payload per task (unchanged):

```
# Task assignment
task_id: {T}
worktree_path: {absolute path to $WT_ROOT/{T}}
task_plan_path: {absolute path to MAIN worktree's feature-docs/{feature}/tasks/{T}.md}
implementation_md_path: {absolute path to MAIN worktree's feature-docs/{feature}/IMPLEMENTATION.md}
lessons_path: {absolute path to MAIN worktree's feature-docs/LESSONS.md; OMIT this line when the file does not exist}
parent_branch: em-workflow/{feature}/integration
merge_script: {resolved MERGE_SCRIPT absolute path}
skills_to_load: {tasks.{T}.skills, prefixed em-workflow: — e.g. ["em-workflow:backend-impl"]; may be empty}
project_commands:
  build: {workflow.yaml project.components.*.build_command}
  test: {...test_command}
  format: {...format_command}
expected_files: {tasks.{T}.files}
```

Do NOT inline task-plan content into the prompt — the implementer Reads its
plan itself. Command strings come from workflow.yaml and are subject to the
implementer's command-approval discipline (worktree-task-workflow skill).

**End the turn** immediately after launching — no polling, no synchronous
wait. The PreToolUse(Task|Agent) launch guard (`queue_launch_guard.py`) records
each allowed launch as a `launched` journal event as the call goes through
(the only writer of `launched`); it also denies double-launching a task
that is already in flight or already merged, as a net under the
orchestrator's own bookkeeping.

### I.2.b: Wake phase (on completion notification)

Triggered whenever a launched implementer's `Task()` call returns.

1. **Reconcile** — replay the journal (last-event-per-task rule: no event →
   unlaunched; `launched` → in-flight; `merged` → merged; `failed` →
   failed) and cross-check against git actual state, trust-but-verify:
   - Worktree/branch existence for tasks the journal claims are in-flight.
   - `git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration`
     for tasks the journal (or the implementer's own report) claims are
     `merged` — a claim that fails this check is NOT merged; never mark a
     task merged on self-report or journal entry alone.
2. **Update workflow.yaml**: collect each returning implementer's
   completion report — `{"task_id", "status": "merged"|"failed",
   "merge_commit", "conflict_retries", "tests": "pass"|"fail",
   "deviations": [...], "notes"}` (malformed/missing report → treat as
   `failed`) — and set `tasks.{T}.status = merged` for every task verified
   merged, `= failed` for every task whose last journal event is `failed`
   or whose report is `failed`/malformed.
3. **Clean up** every newly-merged task's worktree and branch:
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
   Then refresh the integration worktree (Branch & Worktree Model).
4. **Refill**: if no task's reconciled status is `failed`, re-enter the
   launch phase (I.2.a) with the freed slot(s) and any still-unlaunched
   tasks, then end the turn again. If every task is now `merged`, proceed to
   Step I.3.

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
  here. Set `create-plan` to `needs_update`, set the `implement` step back
  to `pending`, record the failure reason in `tasks.{T}.notes`, clean up
  the failed task's worktree and branch (`git worktree remove --force
  "$WT_ROOT/{T}"`; `git branch -D "em-workflow/{feature}/{T}"`), and end
  the phase with a clear report. The develop state machine stops on
  `needs_update` (stop condition 3); the next `/em-workflow:develop` run
  re-enters the planner, which re-scopes the failed task (split it, change
  the approach) — or, when a requirement itself must be dropped, routes
  that change through the normal SPEC.md update path first. Merged tasks
  keep their status; only the failed task is re-planned.
- **abort phase** — leave `implement` as `failed` for manual handling.

There is NO skip option: a task is either merged, retried, or re-planned —
never dropped mid-phase. "実装完了 = 親ブランチへのマージ完了" admits no
carve-out; scope changes belong to the planning/spec layer, not to the
implement phase.

### Supporting cast: journal, hooks, resume

**Journal** (`journal.jsonl`, sibling of the per-task worktree directories
under `.claude/worktrees/em-workflow/{feature}/`): a machine-written,
append-only event log — `launched` / `merged` / `failed`, one JSON object
per line, each carrying `task` and an RFC 3339 `at`. The orchestrator NEVER
writes it; only `merge-task.sh` and the two hooks below append to it. The
raw log is never rewritten or deleted — it is the primary source for
post-mortem diagnosis, distinct from workflow.yaml's LLM-managed summary
(full schema: IMPLEMENTATION.md's Journal contract).

**The three hooks** (`em-workflow/hooks/`, wired in `hooks.json`):

- **Stop hook** (`queue_stop_guard.py`) — fires when the orchestrator's turn
  ends. Replays the journal and workflow.yaml; if refillable slots and
  unlaunched tasks exist and no task has failed, it BLOCKS (exit 2) naming
  the tasks to launch — catching a forgotten refill after a wake phase. A
  consecutive-block cap (3, tracked in a sidecar next to the journal)
  prevents it from wedging the session on unexpected state; exceeding the
  cap yields a warning and lets the turn end.
- **PreToolUse(Task|Agent) launch guard** (`queue_launch_guard.py`) — fires on
  every subagent-launch call (the tool is named `Agent` in current Claude
  Code versions, `Task` in older ones — both are matched); identifies
  em-workflow implementer launches and
  denies double-launching an already in-flight or already-merged task (a
  retry after `failed` is allowed). The sole writer of `launched` events.
- **SubagentStop failure net** (`queue_failure_net.py`) — fires when any
  subagent stops; for em-workflow implementers whose task has no `merged`
  event yet, appends `failed` — turning a swallowed or crashed implementer
  into a visible, actionable state instead of a silent stall. Always exits 0
  (never blocks the stop).

All three are fail-open nets, not authorities: on any unexpected state
(missing files, unparsable input, no active feature) they exit 0 silently.
The orchestrator protocol above plus the resume guard remain authoritative;
a hook wrongly blocking the session is worse than missing one violation.

**Stale-`launched` caveat**: the launch guard appends `launched` at allow
time, before the subagent actually starts — if the `Task()` call is then
allowed but never actually runs, a stale `launched` line can persist with no
corresponding implementer in flight. This is bounded, never silently masked:
the Stop hook's consecutive-block cap prevents an infinite blocking loop
over a wedged slot, and the wake-phase git-state reconcile (worktree/branch
existence check) catches it on the next reconcile pass.

**Resume**: a `/em-workflow:develop` re-entry mid-implement rebuilds state
from three sources, never from memory: workflow.yaml (`tasks.*.status`), the
journal (last-event-per-task replay), and git actual state (worktree
existence, `merge-base --is-ancestor`). The I.2.a resume guard governs
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
