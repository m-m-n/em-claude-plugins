# Verification Document: merge-task-parent-symref-reject

## Overview
**Feature**: merge-task-parent-symref-reject / **SPEC.md**: `feature-docs/merge-task-parent-symref-reject/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/merge-task-parent-symref-reject/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main` defines no build command; the changed script is interpreted)
- Expected: not applicable

## Test Verification
- Command (full suite): `python3 -m unittest discover -s tests`
- Command (feature-focused): `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
- Expected: exit code 0, no failures and no errors
- Coverage target: not measured (the script is exercised as a subprocess); every scenario below is covered by at least one test or check

### Test Scenarios from SPEC.md
TS-1 to TS-8 come from SPEC.md. TS-9 to TS-12 are added here because FR2, NFR2, NFR3 and NFR4 had no scenario in SPEC.md. "Rejection line" below means: one stderr line starting with `ERROR` that names PARENT_BRANCH, with none of "uncommitted", "untracked", "commit everything".

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | During the merge-lock wait (`_run_merge_with_mutation_during_lock_wait`), `refs/heads/<parent>` is re-pointed to a symbolic ref targeting `refs/heads/em-workflow/feat/task0001` | exit 2; rejection line that also contains "symbolic ref"; no journal.jsonl; the task ref keeps its value; the integration ref still targets the task ref | Integration |
| TS-2 | During the merge-lock wait, `refs/heads/<parent>` is re-pointed to a symbolic ref targeting `refs/heads/main` (initial commit, an ancestor of the task tip) | exit 2; rejection line that also contains "symbolic ref"; `refs/heads/main` keeps its value; no journal.jsonl; the symbolic-ref query of the integration ref returns `refs/heads/main` | Integration |
| TS-3 | During the merge-lock wait, `refs/heads/<parent>` is re-pointed to a symbolic ref targeting a branch that diverged from the integration branch (merge-commit position) | exit 2; rejection line that also contains "symbolic ref"; that branch keeps its value and its history has no "merge: task0001" commit; no journal.jsonl | Integration |
| TS-4 | Before the run (no lock wait), `refs/heads/<parent>` is a symbolic ref targeting `refs/heads/main`; then `_run_merge` | exit 2; rejection line that also contains "symbolic ref"; main keeps its value; the integration ref still targets main; no journal.jsonl | Integration |
| TS-5 | `refs/heads/<parent>` is a symbolic ref targeting a `refs/heads/...` name that does not exist (dangling) | exit 2; rejection line that also contains "symbolic ref"; the target is still absent; the integration ref still targets it; no journal.jsonl | Integration |
| TS-6 | Existing tests of `tests/test_merge_task_journal.py` and `tests/test_merge_unverified_exit_doc_contract.py` (content pin, single "Parent already contains us" line followed by the ancestor check, forbidden comment phrases) | all pass | Integration / Doc-contract |
| TS-7 | During the merge-lock wait, the task ref is re-pointed to a symbolic ref targeting another existing branch (existing behaviour pinned) | exit 2 from the post-lock HEAD re-check; an ERROR line names the task ref; that branch and the integration ref keep their values; no journal.jsonl | Integration |
| TS-8 | A git shim placed first on PATH intercepts the update-ref on `refs/heads/<parent>` and, just before handing it to the real git, re-points `refs/heads/<parent>` to a symbolic ref targeting `refs/heads/main`, whose tip equals the old value; run once in a fast-forward setup and once in a merge-commit setup | in both runs `refs/heads/main` keeps its value and the shim recorded exactly one interception; exit status not asserted | Integration |
| TS-9 | A git shim makes the symbolic-ref query on `refs/heads/<parent>` exit with a status other than 0 and 1 | exit 2; rejection line; the integration ref keeps its value and has no "merge: task0001" commit; no journal.jsonl; the shim recorded the interception | Integration |
| TS-10 | Tests added by this feature (NFR2) | only standard-library imports; repositories created only under the test's temporary directory; merge-task.sh run as a subprocess | Static check (review) |
| TS-11 | Plugin version fields (NFR3) | `git diff --name-only <workflow.implement.base_commit>..HEAD -- em-workflow/.claude-plugin/plugin.json .claude-plugin/marketplace.json` prints nothing | Static check (command) |
| TS-12 | Process control in the tests (NFR4) | the lines this feature adds to `tests/test_merge_task_journal.py` invoke no kill, pkill or killall; every lock-wait mutation goes through `_run_merge_with_mutation_during_lock_wait` | Static check (review) |

## Code Quality Verification
- Format: none configured
- Static analysis: `bash -n em-workflow/scripts/merge-task.sh` — expected exit 0 (syntax only)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Lock-wait re-point to the task ref: exit 2, no merged event, ERROR line names the integration branch | TS-1 |
| AC-2 | Lock-wait re-point to another branch at a fast-forward position: exit 2, that branch unchanged, no journal.jsonl | TS-2 |
| AC-3 | Same at a merge-commit position: exit 2, value and history unchanged | TS-3 |
| AC-4 | Symbolic ref present before the run: exit 2 | TS-4 |
| AC-5 | Dangling symbolic ref: exit 2, ERROR line names the integration branch | TS-5 |
| AC-6 | After rejection the symbolic ref still targets what it was re-pointed to | TS-1, TS-2, TS-4, TS-5 |
| AC-7 | Existing tests pass and the content pin matches the changed script | TS-6 |
| AC-8 | Re-point right before update-ref leaves main unchanged on both paths, including when the referent equals the old value | TS-8 |
| SC-1 | All functional requirements implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | Test Verification commands |
| SC-3 | Documentation complete | Manual Testing: FR5 comment review |
| SC-4 | Code review completed | Review phase result |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| FR2 | task0001 | TS-9 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-9 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-9 |
| FR5 | task0001 | TS-6; Manual Testing (comment review) |
| FR6 | task0001 | TS-6; Manual Testing (same-commit pin) |
| FR7 | task0001 | TS-8 |
| NFR1 | task0001 | TS-6, TS-7 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-11 |
| NFR4 | task0001 | TS-12 |

## Manual Testing (E2E Not Possible)
- [ ] FR5: in `em-workflow/scripts/merge-task.sh`, the header paragraph about the exact integration ref and the "Merge source and parent" section comment both state that a symbolic-ref integration ref (or an undeterminable answer) ends the run with exit 2, and that both update-ref calls use `--no-deref`; the exit 2 examples name the symbolic-ref integration ref case.
- [ ] FR6: every commit of the feature that changes `em-workflow/scripts/merge-task.sh` also changes `EXPECTED_MERGE_TASK_SH_SHA256` (compare the commit lists of both files), and the provenance comment above the constant names this feature.
- [ ] TS-10 and TS-12 review items above.

## Performance / Security Verification
- TM-1: symbolic-ref rejection of the integration ref under the merge lock, before the parent value is read — checked by TS-1 to TS-5 and TS-9, and by reading `em-workflow/scripts/merge-task.sh`: the symbolic-ref query on the integration ref comes immediately before the parent value read, statuses other than 1 end the run with exit 2, and no update-ref, merge-tree, commit-tree or journal append runs between the lock and the query.
- TM-2: `--no-deref` on both update-ref calls on the integration ref — checked by TS-8 (fast-forward and merge-commit), and by reading the script: both calls carry the option and still pass PARENT as the old value.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Integration tests (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Static checks (TS-10, TS-11, TS-12, shell syntax) | 4 | 2 | 0 | 2 |
| Manual review (FR5 comments, FR6 same-commit pin) | 2 | 0 | 0 | 2 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| **Total** | 17 | 13 | 0 | 4 |
