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
#   4 = stale worktree (a concurrent merge-task.sh advanced the branch ref
#       via update-ref while this worktree's index/working tree still
#       reflects the old tree — detected via a non-artifact change in
#       `git status --porcelain`, since HEAD-vs-branch-tip is always equal
#       in an attached worktree); no git state touched — caller must reset
#       the worktree to the new tip, re-apply the doc changes, and retry
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

# --- Stale-worktree check (inside the critical section): if a concurrent
# merge-task.sh already advanced the branch ref past this worktree's HEAD
# via `git update-ref` (no checkout), the worktree's index/working tree is
# still built on the OLD tree even though HEAD now resolves to the NEW
# commit (HEAD is a symref to the same branch in an attached worktree, so
# comparing HEAD to the branch tip is always equal and can never detect
# this). Detect staleness instead by checking whether `git status
# --porcelain` reports any changed/untracked path OUTSIDE the artifact
# paths we're about to stage — that is the signature of an index left
# behind by an externally advanced ref. Fail fast so the caller can reset
# + retry, without staging or committing anything. ---
# Scoped to the workflow artifact paths per SPEC FR3 — never `git add -A`,
# which would sweep in unrelated build/test/format byproducts.
ARTIFACT_PATHS=(feature-docs test/README.md design-system)

STATUS_OUT=$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null) \
  || die 3 "cannot read worktree status"
while IFS= read -r line; do
  [ -z "$line" ] && continue
  path="${line:3}"
  is_artifact=0
  for p in "${ARTIFACT_PATHS[@]}"; do
    case "$path" in
      "$p"|"$p"/*) is_artifact=1; break ;;
    esac
  done
  [ "$is_artifact" -eq 1 ] \
    || die 4 "worktree has a non-artifact change outside ARTIFACT_PATHS ($path); the index is stale relative to an externally advanced branch ref (concurrent merge-task.sh) — reset the worktree to the branch tip, re-apply the doc edits, and retry"
done <<< "$STATUS_OUT"

# --- Stage + commit (inside the critical section) ---
STAGE_PATHS=()
for p in "${ARTIFACT_PATHS[@]}"; do
  [ -e "$WORKTREE_PATH/$p" ] && STAGE_PATHS+=("$p")
done

if [ "${#STAGE_PATHS[@]}" -gt 0 ]; then
  git -C "$WORKTREE_PATH" add -A -- "${STAGE_PATHS[@]}" \
    || die 3 "git add failed"
fi

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
