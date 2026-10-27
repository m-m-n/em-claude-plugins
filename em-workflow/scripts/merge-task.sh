#!/usr/bin/env bash
# merge-task.sh - Task-branch → parent-branch merge (em-workflow plugin SSOT)
#
# Called by the implementer agent from INSIDE its own worktree (task branch
# checked out) after all work is committed. Uses merge-tree + commit-tree +
# update-ref so no checkout of the parent branch is ever needed — multiple
# implementers can merge concurrently without fighting over a working tree.
#
# The script merges only when it runs inside the named task's own worktree of
# the em-workflow layout (.../em-workflow/{feature}/{taskNNNN}), with that
# task's branch (em-workflow/{feature}/{taskNNNN}) checked out and the
# feature's integration branch as <parent-branch>. Every other invocation —
# the main working tree, the feature's integration worktree, any path outside
# the layout, a detached HEAD, another branch — ends with exit 2 before the
# merge lock is taken and before any ref is updated. One identity re-check runs
# again right after the lock is acquired (HEAD's symbolic ref must still be the
# task branch); a run that waited for the lock while the worktree moved off the
# task branch ends there with exit 2, still before any ref is updated. The
# commit that gets merged is read from the exact task ref, not from HEAD, and
# the parent value from the exact integration ref refs/heads/<parent-branch>:
# both are resolved by exact ref-name match (no ambiguous-name lookup), and a
# ref that is absent, or whose object is not a commit, ends the run with exit 2
# before any ref is updated. The integration ref must also be a direct ref:
# once the lock is held, a symbolic ref at refs/heads/<parent-branch> (a
# dangling one included), or an answer to that question that cannot be
# determined, ends the run with exit 2 after the lock and before any ref
# update. All update-ref calls on the integration ref (the same-value check on
# the already-contained path, the fast-forward and the merge commit) use the
# no-deref option, so a symbolic ref placed there after that check is never
# followed to its referent. On the already-contained path, right before
# `merged` is recorded, the script confirms that the integration ref is still a
# direct ref. It then confirms by a same-value compare-and-swap that the ref's
# value is still the parent value read under the lock. If either check fails,
# the run ends with exit 2.
#
# Usage:
#   ${CLAUDE_PLUGIN_ROOT}/scripts/merge-task.sh <parent-branch> <task-id>
#
# Exit codes (semantic — the implementer branches on these):
#   0 = merge completed (parent branch now contains the task branch)
#   1 = merge conflict (conflicted files listed on stderr; the implementer
#       must incorporate the parent, re-implement conflicted files, and retry)
#   2 = other error (a run outside the task's own worktree layout or without
#       the task branch checked out, a task-id or parent-branch mismatch, a
#       switch away from the task branch while waiting for the merge lock,
#       an integration ref that is a symbolic ref, an integration ref that is
#       no longer a direct ref holding the parent value right before the
#       already-contained path records `merged`, uncommitted changes,
#       unknown branch, git failure, ...)
#
# Concurrency: the whole check→merge sequence runs under an exclusive flock
# on a lock file in the shared .git directory. Concurrent callers simply
# queue; each sees the parent ref as updated by the previous merger.
# The wait for that lock is a window in which the task's worktree can change
# underneath the run (a branch switch, a detached HEAD, a new commit on the
# task branch). The identity check done before the wait cannot see such a
# change, so the symbolic-ref re-check right after the lock closes the window
# for a different or detached HEAD, and the merge source is read from the
# exact task ref instead of HEAD, so a commit made on the task branch during
# the wait is merged and a commit of any other branch is never merged. The task
# ref and the parent ref are looked up by exact ref-name match, so a tag or any
# other ref that merely resolves under the same name is never taken for either.
#
# Requires git >= 2.40 (git merge-tree --write-tree --name-only) and the
# util-linux `flock` command (absent on stock macOS — install it, e.g.
# `brew install flock`, or run on a Linux host).

set -uo pipefail

die() { echo "ERROR: $*" >&2; exit 2; }

# --- Journal append (best-effort; never turns a successful merge into a
# failure — see IMPLEMENTATION.md "Journal contract" / D4). Journal home:
# {feature-dir}/journal.jsonl, where {feature-dir} is the parent of the
# CURRENT worktree's own top level, matching the
# `.../em-workflow/{feature}/{taskNNNN}` layout. The identity binding below
# guarantees that layout for every run that reaches this append; the
# re-derivation here stays as a defensive check, and a mismatch it finds
# skips the append silently — merging must not depend on it.
append_merged_event() {
  local event_commit="$1"
  local wt_top task_dir_name feature_dir feature_name workflow_dir_name
  local journal_path ts line status

  [[ "$TASK_ID" =~ ^task[0-9]+$ ]] || return 0

  wt_top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  task_dir_name=$(basename -- "$wt_top")
  [[ "$task_dir_name" =~ ^task[0-9]+$ ]] || return 0

  feature_dir=$(dirname -- "$wt_top")
  feature_name=$(basename -- "$feature_dir")
  [[ "$feature_name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || return 0

  workflow_dir_name=$(basename -- "$(dirname -- "$feature_dir")")
  [ "$workflow_dir_name" = "em-workflow" ] || return 0

  journal_path="$feature_dir/journal.jsonl"
  ts=$(date +"%Y-%m-%dT%H:%M:%S%:z") || return 0
  line=$(printf '{"event":"merged","task":"%s","commit":"%s","at":"%s"}' \
           "$TASK_ID" "$event_commit" "$ts")

  # Exclusive flock on the journal file itself (separate from the merge
  # lock above; nested acquisition is fine) — one line, one write.
  ( exec 8>>"$journal_path" && flock -x 8 && printf '%s\n' "$line" >&8 ) 2>/dev/null
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "WARNING: failed to append merged event for $TASK_ID to $journal_path (exit $status)" >&2
  fi
  return 0
}

PARENT_BRANCH="${1:-}"
TASK_ID="${2:-}"
[ -n "$PARENT_BRANCH" ] && [ -n "$TASK_ID" ] \
  || die "usage: merge-task.sh <parent-branch> <task-id>"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "not inside a git work tree"

# --- Identity binding (fail-closed, BEFORE the merge lock and any ref update) ---
# This run must be inside the named task's own worktree of the em-workflow
# layout (.../em-workflow/{feature}/{taskNNNN}) with that task's branch
# checked out, and <parent-branch> must be this feature's integration branch.
# Any run outside the task's own worktree layout (the main working tree, the
# integration worktree, any other path), or with a branch other than the task
# branch checked out (detached HEAD included), ends here with exit 2, before
# the lock, the clean-tree check and any merge-tree/commit-tree/update-ref.
# This holds for every invocation, and it fails closed: a top-level or HEAD
# that cannot be resolved is a rejection. The binding preserves the invariant
# that every exit-0 merge also gets its `merged` journal event — a merge that
# succeeded but skipped the append would make the failure net record a merged
# task as failed.
# The binding has two parts. The pre-lock part above (layout, TASK_ID, parent
# branch, HEAD's symbolic ref) runs before the lock. The post-lock part, right
# after the lock is acquired, reads HEAD's symbolic ref again and compares it
# with the same expected task ref; the layout, TASK_ID and parent-branch checks
# are not repeated, they cannot change while the run waits.
IB_WT_TOP=$(git rev-parse --show-toplevel 2>/dev/null) || IB_WT_TOP=""
[ -n "$IB_WT_TOP" ] \
  || die "cannot resolve this worktree's top-level directory — run merge-task.sh from the task's own worktree"
IB_TASK_DIR=$(basename -- "$IB_WT_TOP")
IB_FEATURE_DIR=$(dirname -- "$IB_WT_TOP")
IB_FEATURE=$(basename -- "$IB_FEATURE_DIR")
IB_WORKFLOW_DIR=$(basename -- "$(dirname -- "$IB_FEATURE_DIR")")
if ! { [[ "$IB_TASK_DIR" =~ ^task[0-9]+$ ]] \
       && [[ "$IB_FEATURE" =~ ^[a-z0-9][a-z0-9-]*$ ]] \
       && [ "$IB_WORKFLOW_DIR" = "em-workflow" ]; }; then
  die "$IB_WT_TOP is not a task worktree of the em-workflow layout (.../em-workflow/{feature}/{taskNNNN}) — merge-task.sh must run from the task's own worktree"
fi
[ "$IB_TASK_DIR" = "$TASK_ID" ] \
  || die "TASK_ID ($TASK_ID) does not match this worktree's task directory ($IB_TASK_DIR)"
[ "$PARENT_BRANCH" = "em-workflow/$IB_FEATURE/integration" ] \
  || die "parent branch ($PARENT_BRANCH) is not this feature's integration branch (em-workflow/$IB_FEATURE/integration)"
IB_EXPECTED_REF="refs/heads/em-workflow/$IB_FEATURE/$IB_TASK_DIR"
IB_HEAD_REF=$(git symbolic-ref --quiet HEAD 2>/dev/null) || IB_HEAD_REF=""
[ "$IB_HEAD_REF" = "$IB_EXPECTED_REF" ] \
  || die "HEAD is not the task branch: expected $IB_EXPECTED_REF, found ${IB_HEAD_REF:-a detached or unresolvable HEAD}"

# --- Exclusive lock (shared across all worktrees via --git-common-dir) ---
COMMON_DIR=$(git rev-parse --git-common-dir) || die "cannot resolve git common dir"
exec 9>"$COMMON_DIR/em-workflow-merge.lock" || die "cannot open lock file"
flock 9 || die "cannot acquire merge lock"

# --- Post-lock identity re-check (fail-closed, BEFORE the clean-tree check and
# any merge-tree/commit-tree/update-ref/journal append) ---
# The worktree may have moved off the task branch while this run waited for the
# lock. Read HEAD's symbolic ref again with the same quiet query as the pre-lock
# binding and compare it with the ref verified there.
PL_HEAD_REF=$(git symbolic-ref --quiet HEAD 2>/dev/null) || PL_HEAD_REF=""
[ "$PL_HEAD_REF" = "$IB_EXPECTED_REF" ] \
  || die "HEAD moved off the task branch while waiting for the merge lock: expected $IB_EXPECTED_REF, found ${PL_HEAD_REF:-a detached or unresolvable HEAD}"

# --- Preconditions (inside the critical section) ---
[ -z "$(git status --porcelain)" ] \
  || die "uncommitted or untracked changes in worktree — commit everything before merging"

# --- Merge source and parent: exact ref-name match, commit objects only ---
# Merge source: the tip of the exact task ref, not HEAD. HEAD is only what the
# worktree has checked out at this instant; the ref is what the identity
# binding verified. The parent value comes from the exact integration ref the
# same way. `git show-ref --verify` looks a full ref name up as that exact name
# only: unlike a revision lookup (rev-parse) it does not also try the name
# under refs/, refs/tags/, refs/heads/ and refs/remotes/, so a tag or a branch
# that happens to resolve under the same name is never taken for either ref.
# Both objects must be commits (cat-file -t, no tag peeling). Every rejection
# here exits 2 before any update-ref, merge-tree, commit-tree or journal
# append. One merge-source value feeds the already-contained, fast-forward and
# merge-commit paths below; nothing reads the task ref or HEAD again.
# The integration ref must not be a symbolic ref: a lookup of it would resolve
# through the symbolic ref to its referent, and an update of it would move
# that other branch. Immediately before the parent value is read, with the
# lock held, `git symbolic-ref --quiet` is asked about the exact ref and the
# decision is made on its exit status alone: 0 (a symbolic ref, dangling
# included) ends the run with exit 2; 1 (a direct ref, or no such ref, which
# the lookup below rejects on its own) lets the run continue; any other status
# also ends the run with exit 2, because the answer could not be determined.
# Every update-ref call on the integration ref below (the same-value check on
# the already-contained path, the fast-forward and the merge commit) passes the
# no-deref option, so a symbolic ref placed at the integration ref after this
# check is never followed to its referent; the old-value comparison against
# PARENT stays as it was. The already-contained path asks the same question
# again right before `merged` is recorded, and then confirms by a same-value
# compare-and-swap that the ref's value is still PARENT; if either check
# fails, the run ends with exit 2.
HEAD_SHA=$(git show-ref --verify --hash -- "$IB_EXPECTED_REF" 2>/dev/null) \
  || die "cannot resolve the task ref $IB_EXPECTED_REF by its exact name"
[ "$(git cat-file -t "$HEAD_SHA" 2>/dev/null)" = "commit" ] \
  || die "the task ref $IB_EXPECTED_REF does not name a commit"
PARENT_SYMREF_TARGET=$(git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH" 2>/dev/null)
PARENT_SYMREF_STATUS=$?
case "$PARENT_SYMREF_STATUS" in
  0) die "the integration ref refs/heads/$PARENT_BRANCH is a symbolic ref (pointing at ${PARENT_SYMREF_TARGET:-an unreadable target}) — merge-task.sh merges only into a direct ref of the integration branch" ;;
  1) ;;
  *) die "cannot determine whether the integration ref refs/heads/$PARENT_BRANCH is a symbolic ref (git symbolic-ref exited $PARENT_SYMREF_STATUS)" ;;
esac
PARENT=$(git show-ref --verify --hash -- "refs/heads/$PARENT_BRANCH" 2>/dev/null) \
  || die "parent branch not found: $PARENT_BRANCH"
[ "$(git cat-file -t "$PARENT" 2>/dev/null)" = "commit" ] \
  || die "parent branch $PARENT_BRANCH does not name a commit"

# Parent already contains us → nothing to do (retry after someone merged us).
if git merge-base --is-ancestor "$HEAD_SHA" "$PARENT"; then
  # Right before `merged` is recorded, confirm that the integration ref is
  # still a direct ref. A symbolic ref can appear between the symbolic-ref
  # check made before the parent value was read and that read; PARENT would
  # then be the referent's value, and the ancestor check above would have
  # judged another branch. The question and the decision on its exit status are
  # those of the earlier check: 0 (a symbolic ref, dangling included) or any
  # status other than 1 ends the run with exit 2. Then confirm by a same-value
  # compare-and-swap, with PARENT as both the new and the expected old value,
  # that the ref still holds PARENT; the no-deref option keeps a symbolic ref
  # from being followed, and a failure ends the run with exit 2. The
  # compare-and-swap is the last git call before the journal append. Neither
  # call passes git's own diagnostics through to stderr, so the ERROR line of a
  # rejection is the only line written.
  RECHECK_SYMREF_TARGET=$(git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH" 2>/dev/null)
  RECHECK_SYMREF_STATUS=$?
  case "$RECHECK_SYMREF_STATUS" in
    0) die "the integration ref refs/heads/$PARENT_BRANCH became a symbolic ref (pointing at ${RECHECK_SYMREF_TARGET:-an unreadable target}) before the merge was recorded — merge-task.sh records a merge only for a direct ref of the integration branch" ;;
    1) ;;
    *) die "cannot determine whether the integration ref refs/heads/$PARENT_BRANCH is still a direct ref (git symbolic-ref exited $RECHECK_SYMREF_STATUS)" ;;
  esac
  git update-ref --no-deref "refs/heads/$PARENT_BRANCH" "$PARENT" "$PARENT" 2>/dev/null \
    || die "update-ref check failed: the integration ref refs/heads/$PARENT_BRANCH no longer holds $PARENT, the parent value read under the lock"
  append_merged_event "$PARENT"
  echo "MERGED: $TASK_ID already contained in $PARENT_BRANCH"
  exit 0
fi

# Fast-forward case: parent is our ancestor → advance the ref, no merge commit.
if git merge-base --is-ancestor "$PARENT" "$HEAD_SHA"; then
  git update-ref --no-deref "refs/heads/$PARENT_BRANCH" "$HEAD_SHA" "$PARENT" \
    || die "update-ref failed (fast-forward)"
  append_merged_event "$HEAD_SHA"
  echo "MERGED: $TASK_ID -> $PARENT_BRANCH (fast-forward to $HEAD_SHA)"
  exit 0
fi

# --- Conflict check + tree construction (no checkout, no index) ---
MERGE_OUT=$(git merge-tree --write-tree --name-only "$PARENT" "$HEAD_SHA" 2>&1)
MERGE_STATUS=$?

if [ "$MERGE_STATUS" -eq 1 ]; then
  echo "CONFLICT: merging $TASK_ID into $PARENT_BRANCH conflicts in:" >&2
  # --name-only output: line 1 = tree OID, following lines = conflicted paths.
  printf '%s\n' "$MERGE_OUT" | tail -n +2 >&2
  exit 1
elif [ "$MERGE_STATUS" -ne 0 ]; then
  die "git merge-tree failed (exit $MERGE_STATUS): $MERGE_OUT"
fi

TREE=$(printf '%s\n' "$MERGE_OUT" | head -n 1)
[ -n "$TREE" ] || die "merge-tree returned empty tree OID"

COMMIT=$(git commit-tree "$TREE" -p "$PARENT" -p "$HEAD_SHA" \
           -m "merge: $TASK_ID") || die "commit-tree failed"

# Compare-and-swap against the PARENT value read inside this critical
# section — defense in depth on top of the flock.
git update-ref --no-deref "refs/heads/$PARENT_BRANCH" "$COMMIT" "$PARENT" \
  || die "update-ref failed (parent moved unexpectedly)"

append_merged_event "$COMMIT"
echo "MERGED: $TASK_ID -> $PARENT_BRANCH ($COMMIT)"
exit 0
