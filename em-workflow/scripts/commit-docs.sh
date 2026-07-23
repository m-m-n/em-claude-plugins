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
#   3 = git failure (staging, staged-path validation, or the commit itself
#       failed); ref not advanced
#   4 = stale worktree (a concurrent merge-task.sh advanced the branch ref
#       via update-ref while this worktree's index/working tree still
#       reflects the old tree) — detected by comparing the branch tip
#       captured BEFORE this invocation acquired the shared lock against the
#       tip observed immediately AFTER acquiring it; any divergence means an
#       external ref move landed in that window. No git state touched.
#
#       RECOVERY CONTRACT (binding on every caller): on exit 4 the caller
#       MUST (1) refresh this worktree to the new branch tip (e.g. `git
#       reset --hard` to the current branch ref — safe per NFR2, this
#       worktree never carries uncommitted state across turns), (2)
#       re-apply the artifact edits this invocation was trying to commit,
#       and (3) retry this script once. The protocol-side implementation of
#       that loop (which caller performs steps 1-2, at which point in the
#       orchestrator flow) is out of this script's scope.
#
# Non-artifact untracked/modified files (verify/build/test/format
# byproducts) never cause exit 4 by themselves — staleness is decided
# purely by branch-tip movement, never by scanning `git status` for
# unrelated paths.
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

# --- Capture the branch tip BEFORE acquiring the lock: this is the baseline
# this worktree's checked-out index/working tree is built on. HEAD is an
# attached symref in a linked worktree, so it always resolves to whatever the
# branch currently points at — a concurrent merge-task.sh that lands its
# update-ref between this read and our lock acquisition below moves that
# resolution out from under us while our files stay built on the OLD tree.
# We check for exactly that divergence once we hold the lock, instead of
# scanning `git status` for byproduct paths (f5084f2afab5d3fe /
# 16702654a8c83434: that proxy misfired on ordinary verify-phase byproducts
# and had no real bearing on ref movement). ---
BEFORE_TIP=$(git -C "$WORKTREE_PATH" rev-parse HEAD 2>/dev/null) \
  || die 3 "cannot resolve worktree HEAD"

# --- Exclusive lock (shared with merge-task.sh via --git-common-dir) ---
exec 9>"$GIT_COMMON_DIR/em-workflow-merge.lock" || die 2 "cannot open lock file"
flock 9 || die 2 "cannot acquire commit lock"

# --- Staleness check (inside the critical section): ref movement, not
# byproducts. Once we hold the lock, no other holder (merge-task.sh included
# — it takes this same lock before its own update-ref) can move the branch
# ref concurrently, so any difference from BEFORE_TIP can only be a move
# that happened while we were waiting for the lock. ---
AFTER_TIP=$(git -C "$WORKTREE_PATH" rev-parse HEAD 2>/dev/null) \
  || die 3 "cannot resolve worktree HEAD"
[ "$BEFORE_TIP" = "$AFTER_TIP" ] \
  || die 4 "branch tip advanced from $BEFORE_TIP to $AFTER_TIP while acquiring the lock (an external update-ref, e.g. a concurrent merge-task.sh) — reset this worktree to the new tip, re-apply the doc edits, and retry"

# --- Stage + commit (inside the critical section) ---
# Scoped to the workflow artifact paths per SPEC FR3 — never `git add -A`
# over the whole worktree, which would sweep in unrelated build/test/format
# byproducts.
ARTIFACT_PATHS=(feature-docs test/README.md design-system)

STAGE_PATHS=()
for p in "${ARTIFACT_PATHS[@]}"; do
  if [ -e "$WORKTREE_PATH/$p" ]; then
    STAGE_PATHS+=("$p")
    continue
  fi
  # The root itself is gone from disk (e.g. the whole file/dir was removed):
  # still stage it if git is tracking a deletion under it, so the deletion
  # gets committed (cb2a99347619de01). Skip silently if nothing was ever
  # tracked there — `git add -A` errors on a pathspec matching no files.
  if [ -n "$(git -C "$WORKTREE_PATH" ls-files --deleted -- "$p" 2>/dev/null)" ]; then
    STAGE_PATHS+=("$p")
  fi
done

if [ "${#STAGE_PATHS[@]}" -gt 0 ]; then
  git -C "$WORKTREE_PATH" add -A -- "${STAGE_PATHS[@]}" \
    || die 3 "git add failed"
fi

# --- Staging hardening: no staged path may escape the artifact allowlist,
# whether staged by our own `add -A` above or already staged before this
# script ran (e.g. `git mv` stages both sides of a rename atomically, so a
# rename FROM an artifact root TO a non-artifact path can leave the
# non-artifact side sitting in the index untouched by our scoped `add`).
# Enumerated via a NUL-delimited, rename-suppressed listing so a porcelain
# "old -> new" rename arrow can never be mis-parsed as a single path
# (e8313f5cad581a23). ---
while IFS= read -r -d '' staged_path; do
  is_artifact=0
  for p in "${ARTIFACT_PATHS[@]}"; do
    case "$staged_path" in
      "$p"|"$p"/*) is_artifact=1; break ;;
    esac
  done
  [ "$is_artifact" -eq 1 ] \
    || die 3 "staged path outside artifact roots: $staged_path"
done < <(git -C "$WORKTREE_PATH" diff --cached --name-only -z --no-renames)

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
