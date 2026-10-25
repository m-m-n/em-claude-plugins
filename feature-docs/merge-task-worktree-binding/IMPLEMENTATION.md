# Implementation Plan: merge-task-worktree-binding

## Overview
merge-task.sh gains an unconditional, fail-closed identity binding (worktree
layout, parent branch, checked-out branch) evaluated before the merge lock, and
every reference to the script's "Parent already contains us" case moves from
line numbers to the case name. Two tasks run in parallel: task0001 (the script,
its behavior tests and its content pins) and task0002 (the implement-phase.md
citation and its phrase pin).

## Technology Stack
- **Language**: Bash (`em-workflow/scripts/merge-task.sh`), Python 3 (tests)
- **Test framework**: Python standard library `unittest` with throwaway git
  repositories under a temporary directory (NFR3)
- **New dependencies**: none

## Layer Structure
| Layer | Files | Responsibility | May depend on |
|---|---|---|---|
| Script | `em-workflow/scripts/merge-task.sh` | The merge and its identity binding | git and util-linux flock (existing prerequisites) |
| Reference docs | `em-workflow/references/implement-phase.md` | Orchestrator protocol; cites the script's cases by name | Script, by citation only |
| Tests | `tests/test_merge_task_journal.py`, `tests/test_merge_unverified_exit_doc_contract.py` | Behavior tests (run the script); doc-contract tests (read script and document text) | Script, Reference docs |

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| "Parent already contains us" case marker in `em-workflow/scripts/merge-task.sh` | Names the case where the parent branch already contains HEAD, so documents and tests cite it by name | Postcondition, held by every version of the script task0001 produces: exactly one line of the script contains the literal phrase "Parent already contains us"; the line immediately after it is the ancestor check that decides whether HEAD is already contained in the parent; that case still re-appends `merged` and exits 0 (FR5). No task changes the phrase's wording. | task0001 (owns the script; replaces the line-slice test with a test of this contract), task0002 (cites the case by this name in implement-phase.md I.2.b) |
| Region ownership in `tests/test_merge_unverified_exit_doc_contract.py` | Lets both tasks edit the module in parallel without overlapping hunks | task0002 edits only the R2 constant `R2_MERGE_TASK_RECORDS_AGAIN_PHRASE` and the test class that asserts the R2 phrases against I.2.b, where it may add its absence assertion. task0001 edits only the pinned-hash block (`EXPECTED_MERGE_TASK_SH_SHA256` and the comment above it), the class that pins merge-task.sh (`TestNeverModifiedFilesAreByteIdentical`), and any new class it adds for merge-task.sh content, placed directly after that class. Neither task changes the import block, the shared helper functions, the launch-guard pin, or any other class. | task0001, task0002 |

## Conventions
- Exit codes keep their meaning: 0 merged, 1 conflict, 2 any other error,
  identity rejections included (NFR2). No new exit code.
- Every rejection goes through the script's existing error path: one stderr
  line starting with `ERROR:`, then exit 2.
- Stderr substrings that existing tests assert stay: "does not match" for a
  task-id mismatch and "integration branch" for a parent-branch mismatch.
- Content pin: any commit that changes merge-task.sh also sets
  `EXPECTED_MERGE_TASK_SH_SHA256` to the new content's sha256 in the same
  commit, including commits made later in review or rework.
- Tests use the standard library only and build every git repository under a
  per-test temporary directory with an isolated git configuration, as the
  existing fixture does. Doc-contract matching is whitespace-normalized unless
  byte identity is the point (the module's existing convention).
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  are in no task's file set (NFR4).

## Cross-task Design Decisions

### D1: The script and its content pin live in one task
`EXPECTED_MERGE_TASK_SH_SHA256` can be computed only from merge-task.sh's
final bytes, and the old line-slice test breaks as soon as the script's lines
shift, so both belong to task0001, which edits the script. task0002 owns the
implement-phase.md citation together with the R2 phrase constant that pins it,
because that pin can be written only together with the sentence it matches.
Affected tasks: task0001, task0002.

### D2: Cite the case by name, not by line number
implement-phase.md I.2.b and the doc-contract tests refer to the case through
the case-marker contract above. After this feature no document or test refers
to merge-task.sh by line number. Affected tasks: task0001, task0002.

### D3: Each worktree is consistent on its own
task0001's worktree keeps the old I.2.b citation and the old R2 phrase, which
still agree with each other. task0002's worktree keeps the old merge-task.sh,
so the old content pin and the old line-slice test still hold there. The
integrated state is consistent once both tasks merge. Affected tasks:
task0001, task0002.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A later change to merge-task.sh (review auto-fix, rework) misses the content pin | Medium | Low | Same-commit pin convention above; TS7 fails visibly |
| Another test module pins text this feature changes, outside the predicted files | Low | Medium | Full test suite in each task's Acceptance Criteria and in verify (TS12); handled as a plan deviation |
| A caller that relied on the removed out-of-layout merge now gets exit 2 | Low | Low | Intended by FR1 and SPEC.md A1; the in-repository caller (the former AC-5 test) is converted by task0001 |
| Git versions differ in how top-level resolution fails inside a git directory | Low | Low | NFR1 treats both an error and an empty result as a rejection; TS9 asserts only the outcome |
| Both tasks edit the doc-contract test module | Medium | Low | Region ownership above keeps the hunks apart; any conflict follows the parent-side adoption protocol |

## Open Questions
- [ ] `em-workflow/skills/worktree-task-workflow/SKILL.md` says a run from the
  main tree "would merge the wrong HEAD", and its exit-2 guidance names only
  uncommitted files as the caller's own fixable cause. After this feature such
  a run is rejected with exit 2. SPEC.md does not include that file; aligning
  it is left outside this feature.
