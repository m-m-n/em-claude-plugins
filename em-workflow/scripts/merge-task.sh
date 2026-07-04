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
  echo "MERGED: $TASK_ID already contained in $PARENT_BRANCH"
  exit 0
fi

# Fast-forward case: parent is our ancestor → advance the ref, no merge commit.
if git merge-base --is-ancestor "$PARENT" "$HEAD_SHA"; then
  git update-ref "refs/heads/$PARENT_BRANCH" "$HEAD_SHA" "$PARENT" \
    || die "update-ref failed (fast-forward)"
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

echo "MERGED: $TASK_ID -> $PARENT_BRANCH ($COMMIT)"
exit 0
