# Verification Document: Integration Worktree Orchestration

## Overview
**Feature**: integration-worktree-orchestration /
**SPEC.md**: `feature-docs/integration-worktree-orchestration/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/integration-worktree-orchestration/IMPLEMENTATION.md`

## Build Verification
- Command: (none — no build step)

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: every commit-docs.sh exit-code path exercised

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | commit-docs.sh with pending changes in a fixture worktree | exit 0; integration ref advances by exactly one commit with the given `docs({feature}):` message | Unit |
| TS-2 | commit-docs.sh with no pending changes | exit 0; ref unchanged; no empty commit | Unit |
| TS-3 | commit-docs.sh with missing/non-worktree path or empty message | non-zero argument-failure exit; no commit created | Unit |
| TS-4 | Concurrent commit-docs.sh and a merge-task.sh-style ref advance on one fixture repo | both commits present; linear history; no lost update; lock vs git failures have distinct exit codes | Integration |
| TS-5 | Develop-shaped sequence on a fixture repo: branch+worktree creation → doc writes → commits → simulated `reset --hard` | zero workflow-caused untracked/modified entries in the main working tree; no committed state lost | Integration |

## Code Quality Verification
- Format: (none configured)
- Static analysis: plugin.json parses as valid JSON (covered by test suite conventions)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | Main working tree stays clean for a full run | TS-5 (automated) + M-2 (manual scratch run) |
| SC-2 | Resume works from branch-only state | M-3 |
| SC-3 | No evacuation logic remains in Step C | M-1 (grep audit of SKILL.md) |
| SC-4 | All tests pass | test command exit 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | M-1 (Phase 3 content check) |
| FR2 | task0002, task0003, task0004 | M-1, TS-5 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR4 | task0003 | M-1, M-3 |
| FR5 | task0003 | M-1 |
| FR6 | task0003, task0004, task0005 | M-1 |
| FR7 | task0005 | M-4 |
| NFR1 | task0002, task0003, task0004 | TS-5, M-2 |
| NFR2 | task0001, task0003, task0004 | TS-5 |
| NFR3 | task0001 | TS-4 |
| NFR4 | task0001 | TS-1..TS-4 pass under `python3 -m unittest discover -s tests` |

## E2E Testing
No project E2E framework.

## Manual Testing (E2E Not Possible)
- [ ] M-1: Grep audit — across em-workflow/skills/develop/SKILL.md,
  references/{implement-phase,review-phase,batch-mode,workflow-schema}.md,
  agents/{requirements-spec-creator,implementation-planner,designer}.md:
  no instruction writes workflow artifacts to the main working tree; no
  "untracked in main" model wording; no docs copy/sync or evacuation steps;
  every artifact write is followed by a commit-docs.sh reference.
- [ ] M-2: Scratch develop run from main — `git status` in the main working
  tree shows no workflow-caused entries at any checkpoint before the final
  merge.
- [ ] M-3: Delete the integration worktree (keep the branch), re-run
  /em-workflow:develop with no arguments — the feature is found via branch
  enumeration, the worktree is re-materialized, and the run resumes.
- [ ] M-4: em-workflow/README.md describes the new model;
  .claude-plugin/plugin.json description updated and version bumped exactly
  one patch.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Script behavior | TS-1..TS-4 | 4 | 0 | 0 |
| Model invariants | TS-5, M-2, M-3 | 1 | 0 | 2 |
| Documentation consistency | M-1, M-4 | 0 | 0 | 2 |
