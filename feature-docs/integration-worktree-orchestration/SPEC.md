# Feature: Integration Worktree Orchestration

## Overview

Relocate every workflow artifact (feature-docs/{feature}/, test/README.md,
design-system/) from the main working tree into the integration worktree, with
every state update committed to the integration branch. The user's main
working tree stays free of workflow-caused changes and untracked files for the
entire run. Applies to both interactive and --batch mode.

## Objectives

- Zero workflow-caused untracked files or modifications in the main working tree
- Zero state loss on crash: every state update is committed before it can be hit
  by a `reset --hard`
- Remove Step C's untracked-identity-check / trash-evacuation logic entirely

## User Stories

### US1: Clean main working tree
As a developer running /em-workflow:develop from main, I want all workflow
artifacts confined to the integration worktree, so that `git status` on my
branch stays clean throughout the run.

**Acceptance Criteria:**
- [ ] At any point of a run (before the final merge), `git status` in the main
  working tree shows no workflow-caused entries
- [ ] The final merge (or PR) delivers the same artifacts as before

### US2: Robust resume
As a developer, I want an interrupted run to resume from the integration
branch alone, so that a lost worktree or session does not lose state.

**Acceptance Criteria:**
- [ ] Re-running /em-workflow:develop with no arguments finds the feature via
  branch enumeration and resumes from workflow.yaml in the worktree
- [ ] A missing worktree is re-materialized with `git worktree add`

## Technical Requirements

### Functional Requirements

- **FR1:** create-spec creates the integration branch
  `em-workflow/{feature}/integration` (from base_branch HEAD) and its worktree
  at `{project_root}/.claude/worktrees/em-workflow/{feature}/integration`
  immediately after the feature name is confirmed (Phase 3), before writing
  any document. A pre-existing branch of the same name triggers resume
  handling or a user ask (batch: abort with report).
- **FR2:** All workflow artifacts — feature-docs/{feature}/ (REQUIREMENTS.md,
  SPEC.md, workflow.yaml, IMPLEMENTATION.md, VERIFICATION.md, tasks/,
  reviews/, retrospect.yaml), test/README.md, design-system/ — are written
  under the integration worktree at their project-relative paths. Nothing is
  written to the main working tree. The implement Step I.1 copy-and-commit of
  docs and the Step C.1 final sync are removed.
- **FR3:** A new script `em-workflow/scripts/commit-docs.sh` commits state
  updates inside the integration worktree under an exclusive flock on the
  SAME lock file merge-task.sh uses
  (`$(git rev-parse --git-common-dir)/em-workflow-merge.lock`). Usage:
  `commit-docs.sh {worktree_path} {message}`; it stages the workflow artifact
  paths and commits with message `docs({feature}): {summary}`. Exit codes
  distinguish nothing-to-commit (success/no-op), lock failure, and git
  failure. The orchestrator calls it after every workflow.yaml / document
  update. No code path may advance the integration ref without holding that
  lock.
- **FR4:** Feature discovery (develop Step A) enumerates
  `git branch --list 'em-workflow/*/integration'` and `git worktree list`
  instead of globbing feature-docs/ in the main tree. Branch present but
  worktree missing → re-materialize via `git worktree add`. Multiple branches
  → AskUserQuestion (batch: abort with report). Zero branches → new feature
  via create-spec. Old-layout features (docs untracked in the main tree) are
  NOT detected; no compatibility path.
- **FR5:** Step C is simplified: cleanliness check of the main working tree →
  `git merge em-workflow/{feature}/integration` (or, for the batch PR
  variant, push + `gh pr create` — unchanged). The untracked identity check,
  `gio trash` / `mv` evacuation, and their fail-closed `realpath` validation
  are deleted. The `.gitignore` gitignore-guard line remains the only
  tolerated dirty exception.
- **FR6:** All protocol documents and agent instructions are updated to the
  worktree-based paths and the two-layer (main live copy + integration
  snapshot) model description is removed: skills/develop/SKILL.md,
  references/implement-phase.md, references/review-phase.md,
  references/batch-mode.md, references/workflow-schema.md,
  agents/requirements-spec-creator.md, agents/implementation-planner.md,
  agents/designer.md. The verify phase already runs in the integration
  worktree and keeps doing so.
- **FR7:** em-workflow/README.md and .claude-plugin/plugin.json (description +
  patch version bump) reflect the new branch/worktree model.

### Non-Functional Requirements

- **NFR1 - Main-tree invariance:** No em-workflow code path writes, deletes,
  or stages anything in the main working tree during a run, except the
  pre-existing gitignore-guard append (unchanged) and the final Step C merge.
- **NFR2 - Crash safety:** Every workflow.yaml / document update is committed
  via commit-docs.sh in the same orchestrator turn that wrote it; the
  integration worktree never carries uncommitted state across turns, so
  reconcile's `reset --hard` and session crashes lose nothing.
- **NFR3 - Concurrency safety:** Document commits and merge-task.sh task
  merges are serialized by one shared flock; concurrent invocations never
  lose a commit or produce a non-fast-forward ref move.
- **NFR4 - Tests:** New/changed script behavior is covered by stdlib unittest
  under tests/ (`python3 -m unittest discover -s tests`); no new runtime
  dependencies beyond util-linux flock (already required by merge-task.sh).

## Implementation Approach

### Architecture

```
main (base_branch, never committed to, never dirtied)
 └─ em-workflow/{feature}/integration          ← created by create-spec (FR1)
      • ALL artifacts live here, committed per update via commit-docs.sh (FR2/FR3)
      ├─ em-workflow/{feature}/task0001         ← task worktrees (unchanged)
      └─ ...
Lock: $GIT_COMMON_DIR/em-workflow-merge.lock   ← shared by merge-task.sh + commit-docs.sh
```

Orchestrator session cwd stays at the project root; it addresses artifacts by
absolute worktree paths. "Where it runs" is unchanged — "what paths it
reads/writes" changes.

### Data Flow

```
create-spec:  confirm name → branch+worktree (FR1) → write docs in worktree → commit-docs.sh
each phase:   read workflow.yaml (worktree) → run → update yaml/docs → commit-docs.sh
implement:    task worktrees branch off integration (unchanged); reconcile
              reset --hard is safe because state is always committed (NFR2)
Step C:       clean-check main → git merge (or push + gh pr create) → cleanup
```

### File Structure

```
em-workflow/
├── scripts/
│   ├── merge-task.sh            # unchanged semantics; stays lock owner
│   └── commit-docs.sh           # NEW (FR3)
├── skills/develop/SKILL.md      # Step A/A.5/B/C rewrite (FR4/FR5)
├── references/
│   ├── implement-phase.md       # branch model + Step I.1 rewrite (FR2/FR6)
│   ├── review-phase.md          # artifact paths (FR6)
│   ├── batch-mode.md            # decision table paths (FR6)
│   └── workflow-schema.md       # artifact location notes (FR6)
├── agents/
│   ├── requirements-spec-creator.md  # Phase 3 rewrite (FR1)
│   ├── implementation-planner.md     # output paths (FR6)
│   └── designer.md                   # output paths (FR6)
├── README.md                    # model description (FR7)
└── .claude-plugin/plugin.json   # description + version (FR7)
tests/
└── test_commit_docs.py          # NEW (NFR4)
```

## Test Scenarios

### Unit Tests
- [ ] TS1: commit-docs.sh commits staged doc changes under flock; integration
  ref advances by exactly one commit with the `docs({feature}):` message
- [ ] TS2: commit-docs.sh with no changes exits as a success no-op (ref
  unchanged)
- [ ] TS3: commit-docs.sh fails cleanly (non-zero, no commit) when the
  worktree path is missing or not a worktree
- [ ] TS4: concurrent commit-docs.sh + merge-task.sh (background processes on
  a fixture repo) → both commits present, ref history linear, no lost update

### Integration Tests
- [ ] TS5: fixture-driven develop-shaped sequence (branch+worktree creation →
  doc writes → commits → simulated reset --hard) leaves zero untracked files
  in the main working tree and loses no committed state

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Manual scenario: run /em-workflow:develop on a scratch feature from
  main; verify `git status` stays clean until the final merge

### Edge Cases
- [ ] EC1: resume with branch present but worktree deleted → re-materialized,
  run continues
- [ ] EC2: pre-existing integration branch at create-spec (FR1) → resume/ask,
  never silently reused in batch
- [ ] EC3: lock contention — commit-docs.sh blocks until merge-task.sh
  releases; no timeout deadlock in normal operation

## Security Considerations

- **Input Validation:** feature / task identifiers pass the existing
  fail-closed patterns (`^[a-z0-9][a-z0-9-]*$`, `^task[0-9]+$`) before being
  interpolated into branch names, worktree paths, or commit messages.
- **Data Protection:** the gitleaks pre-commit hook applies to commit-docs.sh
  commits exactly as to task commits (no `--no-verify`).

## Error Handling

| Code | Description | Handling |
|------|-------------|----------|
| lock failure | flock cannot be acquired/opened | commit-docs.sh exits non-zero; orchestrator reports and stops the step |
| not a worktree | target path missing or not a linked worktree | commit-docs.sh exits non-zero without touching git state |
| dirty main tree at Step C | non-exempt changes present | abort with report (unchanged policy, now without evacuation) |

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Main working tree stays clean for a full develop run (US1)
- [ ] Resume works from branch-only state (US2)
- [ ] Documentation is complete (FR6/FR7)
- [ ] Code review is completed

## Open Questions

None — all requirements confirmed (see REQUIREMENTS.md §14.1).

## References

- Investigation report: tmp/report-integration-worktree-orchestrator-20260723-175049.md
- Requirements: feature-docs/integration-worktree-orchestration/REQUIREMENTS.md
- Current branch model: em-workflow/references/implement-phase.md
