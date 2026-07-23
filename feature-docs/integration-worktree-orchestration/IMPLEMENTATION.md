# Implementation Plan: Integration Worktree Orchestration

## Overview

Move every workflow artifact into the integration worktree with per-update
commits, so the main working tree stays free of workflow-caused changes.
Mostly protocol/agent document rewrites plus one new shell script.

## Technology Stack

- **Language**: POSIX shell (script), Markdown (protocol/agent documents),
  Python stdlib unittest (tests)
- **New dependencies**: none (util-linux `flock` is an existing merge-task.sh
  requirement). License recording: no new dependencies → nothing to record
  (`project.license: none`).

## Layer Structure

Unchanged plugin layout: `scripts/` (deterministic git operations),
`skills/develop/` (orchestrator protocol), `references/` (phase protocols +
schema SSOT), `agents/` (phase agent instructions). Documents reference
scripts by `${CLAUDE_PLUGIN_ROOT}`-resolved paths.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| commit-docs.sh | Serialized commit of workflow artifacts inside the integration worktree | See "Contract: commit-docs.sh" below | task0001 (builds), task0002/task0003/task0004 (documents reference it) |
| Worktree layout convention | Single naming scheme for branch and worktree paths | Branch `em-workflow/{feature}/integration` from base_branch HEAD; worktree at `{project_root}/.claude/worktrees/em-workflow/{feature}/integration`; artifacts at project-relative paths inside it | all tasks |
| Discovery semantics | How a feature is found/resumed | Enumerate branches matching `em-workflow/*/integration` + `git worktree list`; branch without worktree → re-materialize via worktree add; no feature-docs main-tree scan | task0003 (SKILL.md), task0004 (batch-mode.md) |
| Doc-commit message convention | Uniform history on the integration branch | `docs({feature}): {summary}` | task0001, task0002, task0003, task0004 |

### Contract: commit-docs.sh

- Invocation: `commit-docs.sh {worktree_path} {message}`.
- Precondition: `{worktree_path}` is a linked git worktree with the
  integration branch checked out; message non-empty.
- Behavior: acquire exclusive flock on
  `$(git rev-parse --git-common-dir)/em-workflow-merge.lock` (same file as
  merge-task.sh), stage all changes inside the worktree, commit with the
  given message.
- Postcondition / exit codes: 0 = committed, or nothing to commit (no-op
  success, ref unchanged); non-zero, distinct codes for lock failure and for
  git/argument failure; on any failure the ref is not advanced.
- Invariant it enforces: no em-workflow code path advances the integration
  ref without holding the shared lock.

## Conventions

- Fail-closed identifier validation (feature `^[a-z0-9][a-z0-9-]*$`, task
  `^task[0-9]+$`) stays mandatory before any path/branch interpolation.
- No `--no-verify` on any commit (gitleaks pre-commit applies to doc commits).
- Protocol documents keep the existing style: English references/, Japanese
  user-facing strings in SKILL.md.

## Cross-task Design Decisions

### D1: Worktree creation moves to create-spec Phase 3

The integration branch + worktree is created when the feature name is
confirmed, before any document is written (FR1). All later phases assume the
worktree exists; develop Step A re-materializes it when missing (FR4).
Affected: task0002, task0003, task0004.

### D2: Per-update commits replace the two-layer live-copy model

Every workflow.yaml / document update is followed by a commit-docs.sh call in
the same step. The implement Step I.1 docs copy and Step C.1 final sync are
deleted; reconcile's `reset --hard` stays and is safe because the worktree
never carries uncommitted state across turns (NFR2). Affected: task0002,
task0003, task0004.

### D3: No old-layout compatibility

Discovery is branch-based only. Documents drop all references to untracked
feature-docs in the main tree; no fallback scan, no migration code.
Affected: task0003, task0004, task0005.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Doc commit vs merge-task.sh ref race | 中 | 高 | Single shared flock (commit-docs.sh contract); TS-4 concurrency test |
| Protocol docs left internally inconsistent (stale main-tree references) | 中 | 中 | M-1 grep audit in VERIFICATION.md; review spec perspective |
| Resume gap when worktree missing | 低 | 中 | Re-materialize semantics pinned in Discovery contract; manual M-3 |

## Open Questions

- [ ] None
