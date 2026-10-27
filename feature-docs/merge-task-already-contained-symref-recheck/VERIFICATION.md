# Verification Document: merge-task-already-contained-symref-recheck

## Overview
**Feature**: merge-task-already-contained-symref-recheck / **SPEC.md**: `feature-docs/merge-task-already-contained-symref-recheck/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/merge-task-already-contained-symref-recheck/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty: the change is a Bash script plus Python tests.
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted command: `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
- Expected: exit code 0, no failures or errors
- Coverage target: no coverage tool is configured for the shell script. Coverage is measured by scenario: every TS-n below passes.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run merge-task.sh on a task worktree that has a commit to merge, with a git shim. On the first show-ref invocation naming the integration ref, the shim makes that ref a symbolic ref to the task ref, then passes the call through. | Exit 2. Exactly one ERROR line, containing PARENT_BRANCH and "symbolic ref". No dirty-worktree wording, no journal.jsonl, no `MERGED:` line. The task ref value is unchanged, the integration ref still points at the task ref, and the shim acted exactly once. The pre-change script gives exit 0 and a `merged` event (red evidence). | Integration |
| TS-2 | The TS-1 swap, plus one more shim action: right before the second symbolic-ref invocation naming the integration ref, the shim restores that ref to its original value as a direct ref. | Exit 2. Exactly one ERROR line, containing PARENT_BRANCH and "update-ref". No journal.jsonl, no `MERGED:` line. The integration ref is a direct ref holding its original value. | Integration |
| TS-3 | Merge a task normally, then re-run it with a shim that returns exit 128 for the second symbolic-ref invocation naming the integration ref only. | Exit 2. Exactly one ERROR line, containing PARENT_BRANCH and "128". The journal still has one line. The integration ref value is unchanged, and the ref is direct. | Integration |
| TS-4 | Existing suites: `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract` and `python3 -m unittest discover -s tests`. A new test also re-runs an already-merged task on a normal integration branch. | All pass. The re-run exits 0 with "already contained in" and appends one `merged` line, and the integration ref value is unchanged and direct. The content pin matches. "Parent already contains us" is on exactly one line, and the next line is the `merge-base --is-ancestor` check. | Integration (regression) |
| TS-5 | SPEC.md edge case: merge a task normally, then re-run it with a shim that deletes the integration ref right before the second symbolic-ref invocation naming it. | Exit 2. Exactly one ERROR line, containing PARENT_BRANCH and "update-ref". The journal still has one line, and the integration ref stays absent. | Integration |
| TS-6 | Change-scope inspection of the diff against the implement base commit. | The fast-forward path, the merge-commit path and the code of the existing post-lock symbolic-ref check are unchanged. No plugin.json or marketplace.json change. | Static (diff inspection) |
| TS-7 | Test-form inspection of the diff against the implement base commit. | New tests import only the standard library, use throwaway repositories under a temporary directory and run merge-task.sh as a subprocess. Neither the tests nor the script add any kill, pkill or killall. | Static (diff inspection) |
| TS-8 | Dependency inspection of merge-task.sh against the implement base commit. | The script uses no command other than those it already used, and no git feature beyond git 2.40. The "Requires" comment is unchanged. | Static (diff inspection) |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: `bash -n em-workflow/scripts/merge-task.sh`. Expected: exit code 0.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SPEC AC-1 | A symbolic-ref swap between the post-lock check and the parent-value read ends with exit 2 and has no side effects | TS-1 |
| SPEC AC-2 | Restoring the original direct value before the re-check makes the same-value CAS fail, with exit 2 | TS-2 (deletion variant: TS-5) |
| SPEC AC-3 | A re-check status other than 0 and 1 ends with exit 2, and the journal does not grow | TS-3 |
| SPEC AC-4 | A normal already-contained re-run is unchanged | TS-4 |
| SPEC AC-5 | Existing tests pass; the content pin and the case-name line pin hold | TS-4 |
| SPEC Success Criteria | All functional requirements are implemented and tested, and all scenarios pass | TS-1 to TS-8 all pass |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR4 | task0001 | TS-4, plus the manual comment review below |
| FR5 | task0001 | TS-4 |
| FR6 | task0001 | TS-1 |
| NFR1 | task0001 | TS-4, TS-6 |
| NFR2 | task0001 | TS-7 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-7 |
| NFR5 | task0001 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] FR4: read the four comment locations in `em-workflow/scripts/merge-task.sh`: the header paragraph on the direct-ref requirement, the exit 2 examples, the "Merge source and parent" section and the already-contained branch. Confirm that each states the re-check: still a direct ref, then a same-value CAS against PARENT, otherwise exit 2. Confirm that any count of no-deref update-ref calls is accurate.
- [ ] FR6: confirm that task0001's test record shows the TS-1 test failing against the pre-change merge-task.sh (exit 0 with a `merged` event).

## Performance / Security Verification
- TM-1: the symbolic-ref re-check right before recording `merged` (status 0, or any status other than 0 and 1, gives exit 2 with no journal append, no `MERGED:` line and no ref write). Checked by TS-1 and TS-3.
- TM-2: the same-value no-deref CAS as the last git call before the journal append (any failure gives exit 2 with an ERROR line naming update-ref, and no journal append). Checked by TS-2 and TS-5.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Code quality (bash -n) | 1 | 1 | 0 | 0 |
| Integration test scenarios (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Static diff inspection (TS-6 to TS-8) | 3 | 0 | 0 | 3 |
| Manual checks (FR4 comments, FR6 red evidence) | 2 | 0 | 0 | 2 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| **Total** | 13 | 8 | 0 | 5 |
