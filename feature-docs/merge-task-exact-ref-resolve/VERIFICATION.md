# Verification Document: merge-task-exact-ref-resolve

## Overview
**Feature**: merge-task-exact-ref-resolve / **SPEC.md**: `feature-docs/merge-task-exact-ref-resolve/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier with a single task, so no file is shared between tasks) / **THREAT-MODEL.md**: `feature-docs/merge-task-exact-ref-resolve/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the change consists of a shell script and Python tests.
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (`project.components.main.test_command`)
- Focused command (SPEC.md AC-5): `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
- Expected: exit code 0 for both
- Coverage target: no coverage tool is configured. Coverage is judged by the scenario table below, where every FR/NFR maps to at least one scenario.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (FR1, FR2, FR6) The extended test `test_task_ref_deleted_in_a_clean_worktree_is_rejected_at_the_merge_source`. Before the run, the tag `refs/tags/refs/heads/em-workflow/feat/task0001` is created at a commit whose parent is the integration tip and which is not on the task branch. During the lock wait, the task ref is deleted and the worktree is emptied | Exit 2; an ERROR line naming the task ref; no dirty-worktree wording; integration ref unchanged; no `merge: task0001` commit; no `journal.jsonl` | Integration |
| TS-2 | (FR2) The existing test `test_task_ref_deleted_during_lock_wait_is_rejected_without_side_effects`, unmodified: the task ref is deleted during the wait, and no same-named ref exists | Exit 2; no side effects | Integration |
| TS-3 | (FR7, FR8) A new parent-side test. During the lock wait, `refs/heads/em-workflow/feat/integration` is deleted and the tag `refs/tags/refs/heads/em-workflow/feat/integration` is created at the task tip | Exit 2; an ERROR line naming the parent branch; the exact integration ref still absent; tag and task ref unchanged; no `journal.jsonl` | Integration |
| TS-4 | (FR3) A new test. During the lock wait, the task ref is made to point at a non-commit object by writing its loose ref file directly (SPEC.md A4) | Exit 2; no side effects. A stop at the clean-tree check and a stop at the commit-type check are both accepted | Integration |
| TS-5 | (FR4, NFR1) The existing fast-forward, merge-commit, already-contained, subdirectory and late-commit-during-wait tests, unmodified | Exit 0 with exactly the expected `merged` events; the commit made during the wait is the one merged | Integration |
| TS-6 | (FR5, NFR2) `tests/test_merge_unverified_exit_doc_contract.py` | Passes: the content pin equals the changed script's sha256; exactly one "Parent already contains us" line, followed by `merge-base --is-ancestor`; the out-of-layout permission phrases are absent | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The goal's reproduction steps no longer reproduce: exit 2, the integration branch does not advance to the tagged commit, and no `merged` event is written | TS-1 |
| AC-2 | With the integration branch deleted and a same-named tag at the task tip, the run exits 2 instead of exiting 0 through the already-contained path, and writes no `merged` event | TS-3 |
| AC-3 | A task ref whose object is not a commit ends the run with exit 2 and no side effects | TS-4 |
| AC-4 | The extended task-side test and the new parent-side test each fail against the pre-change script and pass against the changed script | Passing side: TS-1 and TS-3. Failing side: see Manual Testing |
| AC-5 | The focused command passes | The focused command in Test Verification |
| Error Handling | Every row of SPEC.md's Error Handling table: task ref absent, task ref not a commit, parent ref absent, parent ref not a commit (A3) | TS-1 and TS-2 (task ref absent), TS-4 (task ref not a commit), TS-3 (parent ref absent), and task0001's non-commit parent ref test (A3) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-6 |
| FR6 | task0001 | TS-1 |
| FR7 | task0001 | TS-3 |
| FR8 | task0001 | TS-3 |
| NFR1 | task0001 | TS-5 and the focused command |
| NFR2 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] SPEC.md AC-4, failing side: confirm that TS-1 and TS-3 fail against the pre-change `merge-task.sh`. Use either the red phase in task0001's test record or a run of the two tests against the base commit's script in a scratch worktree.
- [ ] FR5: in the task's commits, every commit that changes `em-workflow/scripts/merge-task.sh` also changes `EXPECTED_MERGE_TASK_SH_SHA256` in `tests/test_merge_unverified_exit_doc_contract.py` to that commit's script sha256.
- [ ] FR1 / FR7 / FR4 / SPEC.md A2: read the post-lock section of `merge-task.sh`. Check four points:
  - The merge source and the parent are each resolved once, through the exact ref verification lookup that FR1 / FR7 name.
  - No revision-parsing (ambiguous-name) lookup of either remains.
  - No path re-reads the task ref or HEAD.
  - The comments that describe both resolutions state exact ref-name match.

## Performance / Security Verification
- TM-1: The merge source is resolved only from the exact task ref, and an absent task ref gives exit 2 with no side effects. Checked by TS-1, which plants a same-named tag at a child commit of the integration tip and fails against the pre-change script.
- TM-2: The parent is resolved only from the exact integration ref, and an absent integration ref gives exit 2 before the three paths. Checked by TS-3.
- TM-3: Both resolved values pass a commit-type check, and a non-commit value gives exit 2 with no side effects. Checked by TS-4 (task ref) and by task0001's non-commit parent ref test (A3).
- TM-4: One merge-source value feeds all three paths. Checked by TS-5: the late-commit-during-wait test shows that the commit made during the wait is the one merged and recorded. The Manual Testing inspection above also confirms that no path re-reads the task ref or HEAD.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Success criteria | 6 | 5 | 0 | 1 |
| Requirements coverage | 10 | 10 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
