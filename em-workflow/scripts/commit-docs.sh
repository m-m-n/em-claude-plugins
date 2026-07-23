#!/usr/bin/env bash
# commit-docs.sh - Serialized doc commit inside an integration worktree
# (em-workflow plugin SSOT; see IMPLEMENTATION.md "Contract: commit-docs.sh").
#
# Called by the em-workflow orchestrator, from INSIDE the integration
# worktree, after every workflow.yaml / document write, so doc commits and
# merge-task.sh's task merges into the SAME branch never race — both hold
# the same lock file.
#
# Usage:
#   ${CLAUDE_PLUGIN_ROOT}/scripts/commit-docs.sh <worktree-path> <message>
#
# Exit codes (semantic — callers branch on these):
#   0 = committed, or nothing to commit (no-op success; ref unchanged)
#   1 = argument failure (missing/non-worktree path, or empty message);
#       no git state touched
#   2 = lock failure (cannot open or acquire the shared lock file)
#   3 = git failure (staging or commit itself failed); ref not advanced
#
# Concurrency: acquires an exclusive flock on the SAME lock file
# merge-task.sh uses ($(git rev-parse --git-common-dir)/em-workflow-merge.lock)
# before touching the index or ref, so a concurrent merge-task.sh ref advance
# and a commit-docs.sh commit always serialize — no lost update.
#
# Requires the util-linux `flock` command (same prerequisite as
# merge-task.sh; its absence is out of scope here).

set -uo pipefail

die() {
  local code="$1"
  shift
  echo "ERROR: $*" >&2
  exit "$code"
}

WORKTREE_PATH="${1:-}"
MESSAGE="${2:-}"

[ -n "$WORKTREE_PATH" ] && [ -n "$MESSAGE" ] \
  || die 1 "usage: commit-docs.sh <worktree-path> <message>"

[ -d "$WORKTREE_PATH" ] \
  || die 1 "worktree path does not exist or is not a directory: $WORKTREE_PATH"

# --- Validate: a linked git worktree (not a bare dir, not the main working
# tree) ---
IS_WORK_TREE=$(git -C "$WORKTREE_PATH" rev-parse --is-inside-work-tree 2>/dev/null) \
  || die 1 "not a git work tree: $WORKTREE_PATH"
[ "$IS_WORK_TREE" = "true" ] \
  || die 1 "not a git work tree: $WORKTREE_PATH"

GIT_COMMON_DIR=$(git -C "$WORKTREE_PATH" rev-parse --git-common-dir 2>/dev/null) \
  || die 1 "cannot resolve git common dir: $WORKTREE_PATH"
GIT_DIR=$(git -C "$WORKTREE_PATH" rev-parse --git-dir 2>/dev/null) \
  || die 1 "cannot resolve git dir: $WORKTREE_PATH"

case "$GIT_COMMON_DIR" in
  /*) ;;
  *) GIT_COMMON_DIR="$WORKTREE_PATH/$GIT_COMMON_DIR" ;;
esac
case "$GIT_DIR" in
  /*) ;;
  *) GIT_DIR="$WORKTREE_PATH/$GIT_DIR" ;;
esac
GIT_COMMON_DIR=$(cd "$GIT_COMMON_DIR" 2>/dev/null && pwd -P) \
  || die 1 "cannot resolve git common dir: $WORKTREE_PATH"
GIT_DIR_ABS=$(cd "$GIT_DIR" 2>/dev/null && pwd -P) \
  || die 1 "cannot resolve git dir: $WORKTREE_PATH"

# In a linked worktree, --git-dir (…/worktrees/<name>) differs from
# --git-common-dir (the shared .git); in the main working tree they're equal.
[ "$GIT_DIR_ABS" != "$GIT_COMMON_DIR" ] \
  || die 1 "not a linked worktree (this is the main working tree): $WORKTREE_PATH"

# --- Exclusive lock (shared with merge-task.sh via --git-common-dir) ---
exec 9>"$GIT_COMMON_DIR/em-workflow-merge.lock" || die 2 "cannot open lock file"
flock 9 || die 2 "cannot acquire commit lock"

# --- Stage + commit (inside the critical section) ---
git -C "$WORKTREE_PATH" add -A \
  || die 3 "git add failed"

if git -C "$WORKTREE_PATH" diff --cached --quiet; then
  echo "NOOP: nothing to commit in $WORKTREE_PATH"
  exit 0
fi

git -C "$WORKTREE_PATH" commit -q -m "$MESSAGE" \
  || die 3 "git commit failed"

COMMIT=$(git -C "$WORKTREE_PATH" rev-parse --verify HEAD) \
  || die 3 "cannot resolve new HEAD"

echo "COMMITTED: $COMMIT"
exit 0
