# Verification Document: merge-task-worktree-binding

## Overview
**Feature**: merge-task-worktree-binding / **SPEC.md**: `feature-docs/merge-task-worktree-binding/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/merge-task-worktree-binding/IMPLEMENTATION.md`

Scenario IDs keep SPEC.md's hyphen-less form (the first seven come from
SPEC.md; the rest are added here) so they string-match workflow.yaml
`requirements[].tests`.

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused run: `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
- Coverage target: not measured (no coverage tooling; tests use the standard library only, NFR3)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | In a throwaway repository, the main working tree is on a branch carrying a commit that em-workflow/feat/integration lacks; merge-task.sh em-workflow/feat/integration task0001 runs with the main working tree as its working directory | Exit 2; stderr has ERROR; integration branch ref unchanged; no "merge: task0001" commit; no journal.jsonl anywhere under the temporary directory | Integration |
| TS2 | A worktree at .claude/worktrees/em-workflow/feat/integration has the integration branch checked out (the parent already contains HEAD); merge-task.sh runs from it | Exit 2, not the former already-contained exit 0; ref unchanged; no journal line | Integration |
| TS3 | The former AC-5 test, converted: a task worktree outside the layout with a task commit runs merge-task.sh | Exit 2; parent ref unchanged; no journal.jsonl anywhere under the temporary directory | Integration |
| TS4 | An in-layout task worktree with a task commit, HEAD detached, runs merge-task.sh | Exit 2; parent ref unchanged; no journal line | Integration |
| TS5 | An in-layout task worktree with a task commit and another branch checked out runs merge-task.sh | Exit 2; parent ref unchanged; no journal line | Integration |
| TS6 | The existing in-layout tests of tests/test_merge_task_journal.py (fast-forward, merge commit, idempotent already-merged re-append, conflict, precondition error, journal write failure, concurrent merges, task-id mismatch, parent-branch mismatch) re-run with unchanged bodies | All pass | Integration |
| TS7 | Doc-contract tests: implement-phase.md I.2.b cites the already-contained case by name with no line numbers; the case-name test finds the single "Parent already contains us" line in merge-task.sh with the ancestor check on the next line; the content pin matches the new merge-task.sh | tests/test_merge_unverified_exit_doc_contract.py passes | Unit |
| TS8 | Ordering (FR4): while the test holds the shared merge lock, the main-working-tree run and an in-layout detached-HEAD run each execute; a detached-HEAD run in a worktree with an untracked file executes | Each locked-out run ends with exit 2 within a bounded wait; the untracked-file run reports the identity rejection, not the uncommitted-changes precondition | Integration |
| TS9 | Unresolvable top-level (NFR1): merge-task.sh runs with the main repository's git directory as its working directory | Exit 2; stderr has ERROR; integration ref unchanged; no journal anywhere | Integration |
| TS10 | Subdirectory (SPEC.md A4): an in-layout task worktree on its own branch runs merge-task.sh from a committed subdirectory | Exit 0; exactly one merged line for that task | Integration |
| TS11 | Comment update (FR6): merge-task.sh is checked for the phrases "manual invocation", "merge-only" and "exercising only merge"; each matcher is checked against a verbatim pre-change excerpt | Phrases absent from merge-task.sh; each matcher finds its phrase in the excerpt | Unit |
| TS12 | Full suite: python3 -m unittest discover -s tests | Exit 0 | Integration |
| TS13 | NFR3: the two modified test modules are checked for imports and repository locations | The module's standard-library-only import test passes; inspection of tests/test_merge_task_journal.py finds only standard-library imports and no git repository outside the temporary directory | Static (inspection) |
| TS14 | NFR4: the integrated diff from the feature base commit to the integration branch tip is checked for em-workflow/.claude-plugin/plugin.json and .claude-plugin/marketplace.json | Neither file is changed | Static (diff) |

## Code Quality Verification
- Format: none (workflow.yaml `format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A run from the main working tree ends with exit 2; integration ref unchanged; no merge commit | TS1 |
| AC2 | A run from the integration worktree ends with exit 2 before any ref update, including when the parent already contains HEAD; no journal line | TS2 |
| AC3 | A run from the former AC-5 out-of-layout task worktree ends with exit 2; parent ref unchanged; no journal.jsonl | TS3 |
| AC4 | Detached HEAD inside the layout ends with exit 2; parent ref unchanged; no journal line | TS4 |
| AC5 | Another branch checked out inside the layout ends with exit 2; parent ref unchanged; no journal line | TS5 |
| AC6 | Existing in-layout tests pass unchanged | TS6 |
| AC7 | implement-phase.md cites the case by name; the doc-contract module pins the new merge-task.sh and finds the case by name | TS7 |
| AC8 | python3 -m unittest discover -s tests passes | TS12 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS9, TS10 |
| FR2 | task0001 | TS6 |
| FR3 | task0001 | TS4, TS5 |
| FR4 | task0001 | TS1, TS2, TS3, TS4, TS5, TS8 |
| FR5 | task0001 | TS6, TS10 |
| FR6 | task0001 | TS11, manual item M1 |
| FR7 | task0001, task0002 | TS7 |
| FR8 | task0001 | TS3 |
| NFR1 | task0001 | TS4, TS9 |
| NFR2 | task0001 | TS1, TS2, TS3, TS4, TS5, TS6 |
| NFR3 | task0001, task0002 | TS13 |
| NFR4 | task0001, task0002 | TS14 |

## Manual Testing (E2E Not Possible)
- [ ] M1 (FR6): Read merge-task.sh's header comment, its identity-binding comment and its journal-append comment. Each describes a run outside the task's own worktree layout, or with a branch other than the task branch checked out, as rejected with exit 2, and none describes such a run as permitted.

## Performance / Security Verification (if applicable)
- TM-1: layout and task-id binding before the merge lock — checked by TS1, TS2 and TS3 (rejection, ref unchanged, no journal) and TS8 (the rejection completes while the lock is held).
- TM-2: checked-out branch binding — checked by TS4 and TS5 (rejection, ref unchanged, no journal) and TS8 (the detached-HEAD rejection completes while the lock is held and precedes the clean-tree precondition).
- TM-3: fail-closed on resolution failure — checked by TS9 (unresolvable top-level) and TS4 (detached HEAD, whose symbolic ref does not resolve).
- TM-4: parent bound to the feature's integration branch for every accepted run — checked by TS6 (the existing parent-branch mismatch test) and TS1 (a main-working-tree run leaves the integration ref unchanged).
- TM-5: every exit 0 carries a merged event — checked by TS3 (an out-of-layout run no longer exits 0 without an event), TS6 (each in-layout exit-0 path appends) and TS10.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 14 | 13 | 0 | 1 |
| Success criteria | 8 | 8 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-n) | 5 | 5 | 0 | 0 |
