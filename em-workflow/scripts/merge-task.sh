#!/usr/bin/env bash
# merge-task.sh - Task-branch → parent-branch merge (em-workflow plugin SSOT)
#
# Called by the implementer agent from INSIDE its own worktree (task branch
# checked out) after all work is committed. Uses merge-tree + commit-tree +
# update-ref so no checkout of the parent branch is ever needed — multiple
# implementers can merge concurrently without fighting over a working tree.
#
# Usage:
#   ${CLAUDE_PLUGIN_ROOT}/scripts/merge-task.sh <parent-branch> <task-id>
#
# Exit codes (semantic — the implementer branches on these):
#   0 = merge completed (parent branch now contains the task branch)
#   1 = merge conflict (conflicted files listed on stderr; the implementer
#       must incorporate the parent, re-implement conflicted files, and retry)
#   2 = other error (uncommitted changes, unknown branch, git failure, ...)
#
# Concurrency: the whole check→merge sequence runs under an exclusive flock
# on a lock file in the shared .git directory. Concurrent callers simply
# queue; each sees the parent ref as updated by the previous merger.
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
# `.../em-workflow/{feature}/{taskNNNN}` layout. Any mismatch (wrong shape,
# outside that layout, e.g. manual invocation or tests exercising only merge
# behavior) skips the append silently — merging must not depend on it.
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

  # Identity binding: the terminal `merged` event must describe THIS
  # worktree's task and THIS feature's integration branch. A mismatched
  # TASK_ID or PARENT_BRANCH argument (LLM/argument mistake) must never
  # publish a terminal event for a different task or feature — warn and
  # skip the append instead (the orchestrator's git-state reconcile still
  # sees the merge itself).
  if [ "$task_dir_name" != "$TASK_ID" ]; then
    echo "WARNING: journal append skipped: TASK_ID ($TASK_ID) does not match worktree task directory ($task_dir_name)" >&2
    return 0
  fi
  if [ "$PARENT_BRANCH" != "em-workflow/$feature_name/integration" ]; then
    echo "WARNING: journal append skipped: parent branch ($PARENT_BRANCH) is not this feature's integration branch (em-workflow/$feature_name/integration)" >&2
    return 0
  fi

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

# --- Exclusive lock (shared across all worktrees via --git-common-dir) ---
COMMON_DIR=$(git rev-parse --git-common-dir) || die "cannot resolve git common dir"
exec 9>"$COMMON_DIR/em-workflow-merge.lock" || die "cannot open lock file"
flock 9 || die "cannot acquire merge lock"

# --- Preconditions (inside the critical section) ---
[ -z "$(git status --porcelain)" ] \
  || die "uncommitted or untracked changes in worktree — commit everything before merging"

PARENT=$(git rev-parse --verify --quiet "refs/heads/$PARENT_BRANCH") \
  || die "parent branch not found: $PARENT_BRANCH"
HEAD_SHA=$(git rev-parse --verify HEAD) || die "cannot resolve HEAD"

# Parent already contains us → nothing to do (retry after someone merged us).
if git merge-base --is-ancestor "$HEAD_SHA" "$PARENT"; then
  append_merged_event "$PARENT"
  echo "MERGED: $TASK_ID already contained in $PARENT_BRANCH"
  exit 0
fi

# Fast-forward case: parent is our ancestor → advance the ref, no merge commit.
if git merge-base --is-ancestor "$PARENT" "$HEAD_SHA"; then
  git update-ref "refs/heads/$PARENT_BRANCH" "$HEAD_SHA" "$PARENT" \
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
git update-ref "refs/heads/$PARENT_BRANCH" "$COMMIT" "$PARENT" \
  || die "update-ref failed (parent moved unexpectedly)"

append_merged_event "$COMMIT"
echo "MERGED: $TASK_ID -> $PARENT_BRANCH ($COMMIT)"
exit 0
