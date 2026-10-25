# Verification Document: merge-task-post-lock-rebind

## Overview
**Feature**: merge-task-post-lock-rebind / **SPEC.md**: `feature-docs/merge-task-post-lock-rebind/SPEC.md` / **IMPLEMENTATION.md**: omitted (reduced tier; one task, no file declared by two tasks)

Scenarios TS-1 to TS-4 correspond one-to-one to the four numbered scenarios of
SPEC.md's Test Scenarios section, in the same order. TS-5 to TS-11 cover the
SPEC.md edge cases, the unnumbered full-suite run and the inspection-only
requirements.

## Build Verification
- Command: none (`build_command` is empty for the `main` component)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Targeted: `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
- Coverage target: none set (no coverage tooling is configured for this component)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The test holds the merge lock; merge-task.sh is launched from a task worktree with a commit to merge and waits on the lock (flock child observed via /proc within about 10 s); the worktree is switched to a newly created branch; the lock is released; the exit is awaited with an upper bound | Exit 2; stderr ERROR contains the verified task ref and `refs/heads/<other>`; integration branch ref unchanged, no 'merge: <task_id>' commit, no journal.jsonl | Unit |
| TS-2 | Same as TS-1, plus an untracked file created after the switch and before the lock is released | Exit 2 with the identity ERROR naming both refs; no worktree-dirty wording in stderr; no merge, no journal | Unit |
| TS-3 | Run the pre-existing tests of `tests/test_merge_task_journal.py` (fast-forward, merge commit, already contained, conflict, concurrent merges, pre-lock rejections including the locked-run test bounded by LOCKED_RUN_BOUND_SECONDS) with their bodies unchanged | All pass | Integration |
| TS-4 | Run `tests/test_merge_unverified_exit_doc_contract.py` with the updated content pin | All pass: the pin matches the new merge-task.sh, 'Parent already contains us' is on exactly one line followed by the `merge-base --is-ancestor` check, no forbidden phrase is present | Unit |
| TS-5 | Same as TS-1, but HEAD is detached instead of switched to a branch | Exit 2; ERROR names the expected ref and states HEAD is detached or unresolvable; no side effects as in TS-1 | Unit |
| TS-6 | Same as TS-1, but the verified task ref is deleted during the wait | Exit 2 with an ERROR line; no side effects as in TS-1 | Unit |
| TS-7 | Same as TS-1, but a new commit is added on the same task branch during the wait | Exit 0; the integration branch contains the new commit; journal.jsonl holds a `merged` event for the task | Unit |
| TS-8 | `python3 -m unittest discover -s tests` from the repository root | All pass | Integration |
| TS-9 | Read the merge-task.sh diff | HEAD_SHA is resolved from the verified task ref (not HEAD) and that value feeds the already-contained, fast-forward and merge-commit paths; the post-lock re-check sits right after the lock and before the worktree-clean check, merge-tree, commit-tree, update-ref and every journal append; the header paragraph, identity-binding block comment and concurrency note describe the re-check and the HEAD_SHA source; no new environment variable, test hook or argument; usage, exit-code meanings, MERGED: / CONFLICT: / ERROR: formats and journal line format unchanged | Inspection |
| TS-10 | Read the new tests in `tests/test_merge_task_journal.py` | Stdlib unittest only; throwaway repositories under temporary directories; synchronization through the /proc flock-child poll with a monotonic deadline of about 10 s, not short sleeps; bounded exit wait; every failure path releases the lock and terminates and reaps only the test's own child through its handle; no pattern-based kill | Inspection |
| TS-11 | List the files changed by the feature against its base | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is modified | Inspection |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | A branch switch during the merge-lock wait ends in exit 2 with an ERROR naming both refs and no side effects | TS-1 |
| AC-2 | With a switch plus an untracked file, the post-lock rejection reports the identity mismatch, not the worktree error | TS-2 |
| AC-3 | HEAD_SHA comes from IB_EXPECTED_REF; existing fast-forward, merge-commit, already-contained, conflict and concurrent-merge tests pass unchanged | TS-3, TS-9 |
| AC-4 | Existing pre-lock rejection tests, including the locked-run test bounded by LOCKED_RUN_BOUND_SECONDS, pass unchanged | TS-3 |
| AC-5 | The doc-contract test passes with the new pin and the fixed comment properties | TS-4 |
| AC-6 | `python3 -m unittest discover -s tests` passes from the repository root | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-3, TS-8 |
| FR2 | task0001 | TS-1, TS-5 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-3, TS-6, TS-7, TS-9 |
| FR5 | task0001 | TS-4, TS-9 |
| FR6 | task0001 | TS-4 |
| FR7 | task0001 | TS-1, TS-2 |
| NFR1 | task0001 | TS-1, TS-5, TS-6 |
| NFR2 | task0001 | TS-3, TS-9 |
| NFR3 | task0001 | TS-8, TS-10 |
| NFR4 | task0001 | TS-11 |

## Manual Testing (E2E Not Possible)
- [ ] TS-9: merge-task.sh diff inspection (HEAD_SHA source and its use on every merge path, re-check placement, comment content, unchanged interface). A switch after the post-lock re-check (SPEC.md A3) cannot be produced deterministically without a test hook, which NFR2 forbids, so the HEAD_SHA source is checked here.
- [ ] TS-10: new-test design inspection against NFR3.
- [ ] TS-11: plugin version files untouched by the feature's change set.

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md declares no performance requirement).
- TM-1: post-lock re-check of HEAD's symbolic ref against the verified task ref — checked by TS-1 (branch switch), TS-2 (switch plus untracked file) and TS-5 (detached HEAD): each ends in exit 2 with the identity ERROR, the integration branch ref unchanged, no 'merge: <task_id>' commit and no journal.jsonl.
- TM-2: merge source resolved from the verified task ref instead of HEAD — checked by TS-9 (the diff shows HEAD_SHA read from the verified task ref and used on all three merge paths), TS-6 (an unresolvable ref ends in exit 2 with no side effects) and TS-7 (a new commit on the same branch is merged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-11) | 11 | 8 | 0 | 3 |
| Success criteria (AC-1 to AC-6) | 6 | 6 | 0 | 1 |
| Requirements (FR1–FR7, NFR1–NFR4) | 11 | 10 | 0 | 5 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 1 |
