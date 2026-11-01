# Implementation Plan: launch-guard-common-dir-fallback

## Overview

Adds three rules to the launch guard's segment-free path (the git-common-dir
fallback) so that submodule and separate-git-dir layouts, and a project root
that is itself a linked worktree, no longer have correct launches denied. The
change is pinned by new tests, and the launch guard's content pin is refreshed
in the same change. The whole feature is one task (task0001).

## Technology Stack

- **Language**: Python 3, standard library only (NFR1)
- **Test framework**: the standard unittest runner, invoked as
  `python3 -m unittest discover -s tests` (workflow.yaml
  `project.components.main.test_command`)
- **New dependencies**: none. No license to record; `project.license` is
  `none`.

## Layer Structure

| Layer | File | Responsibility |
|-------|------|----------------|
| Hook (PreToolUse) | `em-workflow/hooks/queue_launch_guard.py` | Allow/deny decision for implementer launches; project-root derivation; fail-open on every undecidable state |
| Behaviour tests | `tests/test_queue_launch_guard_linked_layout.py` | Pins the project-root derivation and the cwd check, with a stubbed process runner (unit) and real temporary git repositories (integration) |
| Content pin | `tests/test_merge_unverified_exit_doc_contract.py` | Pins the exact bytes of the hook file by sha256 |

Allowed dependency direction: tests load or read the hook; the hook depends on
nothing under `tests/`. The behaviour test module imports no other test module
(an existing pinned rule of that module).

## Shared Components

No component is shared between tasks: the feature has a single task. The hook
functions the tests call directly are listed so that a later rework task keeps
their contracts.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `project_root_for(worktree_path)` | Project root a task worktree belongs to | Pre: an absolute, validated worktree path. Post: a root path, or undetermined (no value). Segment path unchanged (FR5). Segment-free path: undetermined when the git-common-dir call fails, when the lexically normalized common dir's last element is not exactly `.git` (FR1), or when the derived root does not contain the worktree path (FR2); otherwise the parent of the normalized common dir | task0001 |
| `cwd_outside_project_root(cwd, worktree_path)` | The cwd check | Post: the root to name in a denial, or no value (no denial). No value for every undecidable state, and on the segment-free path also when the root contains the cwd's toplevel and that toplevel strictly contains the worktree path (FR3) | task0001 |
| `git_common_dir_root(worktree_path)` | The single fallback git call | Post: exactly one git-common-dir call with the existing command shape, working directory and timeout (NFR3); the parent of the normalized output, or no value | task0001 |
| `EXPECTED_LAUNCH_GUARD_SHA256` | Content pin of the hook file | Post: equals the sha256 of the hook file's bytes at every commit | task0001 |

## Conventions

- **Fail-open (NFR2)**: every state the hook cannot decide resolves to no
  denial and exit 0. A rule added by this feature only removes denials; none
  adds one. No new exception may escape the hook's entry point.
- **Containment vocabulary**: "contains" and "strictly contains" are the
  REQUIREMENTS.md §13 definitions — both sides resolved to real paths first,
  then compared by their common path; "strictly" excludes equality.
- **Content pin (A5)**: any commit that changes the hook file sets
  `EXPECTED_LAUNCH_GUARD_SHA256` to the new content's sha256 in the same
  commit. This applies to every later task that edits the hook, rework tasks
  included.
- **Test determinism (NFR5)**: no sleeping, no timing or concurrency modules,
  no load generation. Unit tests replace the hook's process runner; integration
  tests use temporary git repositories with the module's existing
  environment-isolation helper.

## Cross-task Design Decisions

### D1: The feature is one task

The content pin must equal the hook's final bytes, and the docstring rules and
the decision logic live in the same file as the code they describe. Parallel
tasks over these files would require one task to pin bytes it cannot see.
Affected tasks: task0001.

### D2: The segment path is out of reach of the new rules

FR1 to FR3 apply only when the worktree path lacks the
`/.claude/worktrees/em-workflow/` segment (FR5). Whether the segment is present
is a pure function of the worktree path, so the cwd check can tell which path
determined the root without starting a process (FR4). Affected tasks: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A new no-denial rule re-opens a standard linked-layout denial (NFR4) | Low | Medium | Strict containment in FR3; existing TestLinkedLayoutOtherWorktreeLaunch kept unchanged; FR3 boundary tests (THREAT-MODEL.md TM-2) |
| The existing fixtures pair `/proj/.git` with a worktree path outside `/proj`, so under FR2 the existing denial control test would flip to no denial | Certain without the fixture rewrite | Low (suite red) | FR7 rewrites both fixture paths to segment-free paths under `/proj` |
| The content pin is left stale after a late hook edit | Medium | Low (suite red) | Pin computed after the last hook edit and re-computed on any later edit (Conventions) |
| Real-git fixtures pick up the host's git configuration | Low | Low | Reuse of the module's existing git environment isolation |

## Open Questions

- [ ] None.
