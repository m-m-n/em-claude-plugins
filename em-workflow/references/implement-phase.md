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
  - `task0001/` … — per-task worktrees (created per chunk, removed after merge)
- `merge-task.sh` advances `refs/heads/em-workflow/{feature}/integration` via
  `update-ref` WITHOUT any checkout. This is only safe because the integration
  branch's own worktree is never used for uncommitted work while task chunks
  run, and the branch is never checked out in the user's main working tree.
  **After each chunk completes, refresh the integration worktree**:
  `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`
  (safe: that worktree holds no uncommitted work by invariant).
- The live `feature-docs/{feature}/` (workflow.yaml etc.) stays in the MAIN
  working tree, uncommitted, orchestrator-owned. It is copied + committed into
  the integration branch at phase start (Step I.1) and again at develop
  completion (so the merged result carries the final records). An untracked
  `test/README.md` (created by create-spec) is committed alongside at phase
  start only (Step I.1) — that makes it visible in every task worktree and
  carries it to `base_branch` via the completion merge.
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
# Bring along test/README.md ONLY while untracked (i.e. created by
# create-spec, not yet committed): tracked copies are already in
# BASE_COMMIT, and user-modified tracked files are never committed on the
# user's behalf.
if [ -f "test/README.md" ] && \
   ! git ls-files --error-unmatch "test/README.md" >/dev/null 2>&1; then
  mkdir -p "$WT_ROOT/integration/test"
  cp "test/README.md" "$WT_ROOT/integration/test/README.md"
  git -C "$WT_ROOT/integration" add test/README.md
fi
git -C "$WT_ROOT/integration" commit -m "docs({feature}): SDD artifacts at implement start"
```

Record in workflow.yaml: `base_branch`, `parent_branch`, and
`workflow[implement].base_commit = $BASE_COMMIT`. Set `implement` status to
`in_progress`.

## Step I.2: Task loop (fully parallel, chunked by the cap)

There is NO ordering mechanism between tasks. Collect ALL tasks with
`status != merged` in ascending task-id order (`failed` tasks ARE re-selected
so the I.2.a resume guard can pick up their kept worktree) and split them
into sequential chunks of at most `max_parallel_implementers` tasks
(default: 6 — a hard cap on how many implementer `Task()` calls may run
concurrently). File overlap between concurrent tasks is allowed: merge
conflicts are an expected path, resolved by each implementer's
parent-side-adoption protocol (worktree-task-workflow skill; merge-task.sh
serializes concurrent merges via flock).

For each chunk C in order:

### I.2.a: Create task worktrees

For each task T in chunk C:

```bash
git worktree add -b "em-workflow/{feature}/{T}" "$WT_ROOT/{T}" \
    "em-workflow/{feature}/integration"
```

Branch point = integration branch AT THIS MOMENT (includes every task merged
so far).
Set `tasks.{T}.status = in_progress`, `tasks.{T}.branch` in workflow.yaml.

**Resume guard**: before running `git worktree add -b` for task T, check
whether `em-workflow/{feature}/{T}` and/or `$WT_ROOT/{T}` already exist (this
happens on re-entry after a prior failed/interrupted run whose worktree was
kept for diagnosis per I.2.c). Do NOT run `git worktree add -b` blindly in
that case:
- Retry on the same worktree (user chose "retry" in I.2.c): reuse the
  existing worktree as-is and re-launch the implementer against it.
- Clean re-attempt (fresh implementer, no prior branch state to keep): first
  `git worktree remove --force "$WT_ROOT/{T}"` and
  `git branch -D "em-workflow/{feature}/{T}"`, then recreate the worktree and
  branch from the current integration branch as above.

### I.2.b: Launch the chunk's implementers

Launch one `Task(subagent_type="em-workflow:implementer")` per task in
chunk C, all in a SINGLE message (parallelism requirement). Never launch
them one at a time.

Before launching the chunk, verify every `project_commands` string
(build/test/format) used by this chunk is in the approval store
(`bash_guard.py --list`; command-execution-protocol.md). Anything
unapproved: run the protocol's approval gate now (AskUserQuestion →
`--record`) — the PreToolUse hook denies unapproved workflow.yaml strings
inside implementer worktrees, so approving up front avoids mid-chunk
failures. Commands the user rejects stay unapproved: the hook denies them
and the implementer reports failure instead of working around it
(worktree-task-workflow skill).

Prompt payload per task:

```
# Task assignment
task_id: {T}
worktree_path: {absolute path to $WT_ROOT/{T}}
task_plan_path: {absolute path to MAIN worktree's feature-docs/{feature}/tasks/{T}.md}
implementation_md_path: {absolute path to MAIN worktree's feature-docs/{feature}/IMPLEMENTATION.md}
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

### I.2.c: Collect completion reports

Each implementer returns JSON:
`{"task_id", "status": "merged"|"failed", "merge_commit", "conflict_retries",
"tests": "pass"|"fail", "deviations": [...], "notes"}`.

For each result:
- `merged` → set `tasks.{T}.status = merged` in workflow.yaml.
- `failed` → set `failed`, keep the worktree for diagnosis, and STOP after
  this chunk (do not launch later chunks on a broken base). Surface the failure
  to the user with the implementer's notes; offer via AskUserQuestion:
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
- Malformed/missing report → treat as `failed`.

Trust-but-verify: confirm the merge actually happened —
`git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration`.
A `merged` report that fails this check is a `failed` task (never mark it
merged on self-report alone).

### I.2.d: Clean up chunk worktrees

For each successfully merged task:

```bash
git worktree remove "$WT_ROOT/{T}"
git branch -D "em-workflow/{feature}/{T}"   # -D: merge already verified via
                                            # merge-base --is-ancestor (I.2.c).
                                            # -d would REFUSE here: the
                                            # orchestrator's HEAD is base_branch,
                                            # which does not contain the task
                                            # branch (it was merged into
                                            # integration, not base_branch).
```

Then refresh the integration worktree (see Branch & Worktree Model) and
proceed to the next chunk.

## Step I.3: Phase completion

When every task is `merged`: set `implement` step `status = completed`,
`completed_at_commit = $(git rev-parse "em-workflow/{feature}/integration")`.
There is no other way to complete this phase — a non-merged task always
resolves via retry, route-back-to-planning, or abort (I.2.c). Report overall
stats (tasks, chunks, conflict retries, failures) in 1-3 lines and return control to
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
