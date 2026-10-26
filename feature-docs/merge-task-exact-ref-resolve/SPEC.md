# Feature: merge-task-exact-ref-resolve

## Overview

`merge-task.sh` resolves the merge source only from the exact task ref
`refs/heads/em-workflow/{feature}/{taskNNNN}` and the integration branch only
from the exact parent ref `refs/heads/{parent-branch}`. When either exact ref
is absent, or its object is not a commit, the run exits 2 without changing
any ref or the journal.

## Objectives

- `merge-task.sh` never merges a commit taken from a ref other than the exact
  task ref `refs/heads/em-workflow/{feature}/{taskNNNN}`, and never treats a
  ref other than the exact parent ref `refs/heads/{parent-branch}` as the
  integration branch.
- When either exact ref is absent, the run ends with exit 2 and leaves no side
  effects on refs or the journal.

## Technical Requirements

### Functional Requirements

- **FR1 - Exact-match merge-source resolution:** After the post-lock identity
  re-check, `merge-task.sh` gets the merge-source object ID only from the
  exact ref `$IB_EXPECTED_REF` via
  `git show-ref --verify --hash "$IB_EXPECTED_REF"`. It does not use
  gitrevisions ambiguous-name resolution.
- **FR2 - Absent task ref is rejected without side effects:** When the
  exact-match resolution of FR1 fails, `merge-task.sh` exits 2 with an ERROR
  line naming `$IB_EXPECTED_REF`. No ref is changed, no `merge: {TASK_ID}`
  commit is created, and no journal line is appended.
- **FR3 - Commit-type verification of the merge source:** `merge-task.sh`
  confirms that the object ID resolved in FR1 is a commit. When it is not,
  the run exits 2 with the same no-side-effect guarantee as FR2.
- **FR4 - Single merge-source value across the three paths:** The one value
  resolved and verified in FR1/FR3 is the merge source used by the
  already-contained, fast-forward and merge-commit paths, including their
  `update-ref`, journal append and output message.
- **FR5 - Hash pin update:** `EXPECTED_MERGE_TASK_SH_SHA256` in
  `tests/test_merge_unverified_exit_doc_contract.py` is set to the sha256 of
  the changed `merge-task.sh` in the same commit that changes the script.
- **FR6 - Task-side regression test with a same-named tag:** The existing test
  `test_task_ref_deleted_in_a_clean_worktree_is_rejected_at_the_merge_source`
  is extended. It adds the tag
  `refs/tags/refs/heads/em-workflow/feat/task0001`, pointing at a child commit
  of the integration branch. The test asserts exit 2 and no side effects.
- **FR7 - Exact-match parent resolution:** `merge-task.sh` resolves the parent
  value only from the exact ref `refs/heads/$PARENT_BRANCH`. It does not use
  gitrevisions ambiguous-name resolution (it uses
  `git show-ref --verify --hash`). When that ref is absent, the run exits 2
  with an ERROR line naming the parent branch, before the already-contained,
  fast-forward and merge-commit paths. No ref is changed, no merge commit is
  created, and no journal line is appended.
- **FR8 - Parent-side regression test:** A new test in
  `tests/test_merge_task_journal.py` uses
  `_run_merge_with_mutation_during_lock_wait`. During the lock wait it deletes
  `refs/heads/em-workflow/feat/integration` and creates the tag
  `refs/tags/refs/heads/em-workflow/feat/integration` pointing at the task
  branch tip. It asserts exit 2, an ERROR line naming the parent branch, and
  no side effects. Side effects are checked without relying on the parent ref
  existing: `refs/heads/em-workflow/feat/integration` is still absent, the tag
  and the task ref are unchanged, and no `journal.jsonl` exists under the
  test's temporary directory.

### Non-Functional Requirements

- **NFR1 - Existing behavior preserved:** Every other test in
  `tests/test_merge_task_journal.py` and
  `tests/test_merge_unverified_exit_doc_contract.py` passes without
  modification. This includes the fast-forward, merge-commit,
  already-contained, conflict, concurrent and late-commit-during-wait tests.
- **NFR2 - Script text constraints:** `merge-task.sh` keeps exactly one line
  naming "Parent already contains us", followed by a line with
  `merge-base --is-ancestor`. No comment contains "manual invocation",
  "merge-only" or "exercising only merge".

## Acceptance Criteria

- [ ] **AC-1** (FR1, FR2, FR4, FR6): The task's reproduction steps no longer
  reproduce: the run exits 2, the integration branch does not advance to the
  tagged commit, and no `merged` event is written.
- [ ] **AC-2** (FR7, FR8): With the integration branch deleted and a
  same-named tag at the task tip, the run exits 2 instead of exiting 0 through
  the already-contained path, and writes no `merged` event.
- [ ] **AC-3** (FR3): A task ref whose object is not a commit ends the run
  with exit 2 and no side effects.
- [ ] **AC-4** (FR6, FR8): The extended task-side test and the new parent-side
  test each fail against the pre-change script and pass against the changed
  script.
- [ ] **AC-5** (FR5, NFR1, NFR2):
  `python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`
  passes.

## Implementation Approach

### Resolution Flow

```
post-lock identity re-check
  → task ref:   git show-ref --verify --hash "$IB_EXPECTED_REF"
                  absent      → ERROR naming $IB_EXPECTED_REF, exit 2 (FR2)
                  not commit  → exit 2 (FR3)
  → parent ref: git show-ref --verify --hash "refs/heads/$PARENT_BRANCH"
                  absent      → ERROR naming the parent branch, exit 2 (FR7)
                  not commit  → exit 2 (A3)
  → already-contained / fast-forward / merge-commit path
      uses the single resolved merge-source value (FR4)
```

### Files

- `merge-task.sh`: exact-match resolution of the merge source and the parent
  (FR1-FR4, FR7), comment wording (A2), text constraints (NFR2).
- `tests/test_merge_unverified_exit_doc_contract.py`: hash pin (FR5), history
  comment above the pin (A5).
- `tests/test_merge_task_journal.py`: extended task-side test (FR6), new
  parent-side test (FR8), non-commit task ref test (TS-4).

## Assumptions

- **A1:** The ERROR line emitted when task-ref resolution fails names the full
  task ref, which keeps the assertion at
  `tests/test_merge_task_journal.py:804-806` valid.
- **A2:** Comments describing the merge source and the parent resolution are
  reworded to say that both are resolved by exact ref-name match (header lines
  16-19 and 36-42, and lines 160-163). The NFR2 wording constraints are kept.
- **A3:** The parent value resolved in FR7 is also confirmed to be a commit,
  with exit 2 and no side effects otherwise, in the same way as FR3.
- **A4:** TS-4 makes the task ref point at a non-commit object by writing the
  loose ref file directly, because git refuses `update-ref` of a non-commit
  object into `refs/heads/`.
- **A5:** The history comment above `EXPECTED_MERGE_TASK_SH_SHA256` (lines
  963-967) may also name this feature as one that set the pin.
- **A6:** The parent-branch exact-match resolution (FR7/FR8) is in scope
  although the task text names only the merge source.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-task-exact-ref-resolve/**`
- `test-docs/merge-task-exact-ref-resolve/**`

`feature-docs/merge-task-exact-ref-resolve/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-task-exact-ref-resolve/**` covers
`test-docs/merge-task-exact-ref-resolve/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/merge-task-exact-ref-resolve/` directory at all; the declared
`test-docs/merge-task-exact-ref-resolve/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Integration Tests

- [ ] **TS-1** (FR1, FR2, FR6): Extended existing test. Before the run, create
  the tag `refs/tags/refs/heads/em-workflow/feat/task0001` at a commit whose
  parent is the integration tip and which is not on the task branch. During
  the lock wait, delete `refs/heads/em-workflow/feat/task0001` and run
  `git rm -r -q -f .`. Expect exit 2, an ERROR line naming the task ref, no
  dirty-worktree wording, an unchanged integration ref, no `merge: task0001`
  commit and no `journal.jsonl`.
- [ ] **TS-2** (FR2): Existing test
  `test_task_ref_deleted_during_lock_wait_is_rejected_without_side_effects`,
  unchanged: task ref deleted during the wait, no same-named ref. Expect exit 2
  and no side effects.
- [ ] **TS-3** (FR7, FR8): During the lock wait, delete
  `refs/heads/em-workflow/feat/integration` and create the tag
  `refs/tags/refs/heads/em-workflow/feat/integration` at the task tip. Expect
  exit 2 and an ERROR line naming the parent branch;
  `refs/heads/em-workflow/feat/integration` still absent, tag and task ref
  unchanged, no `journal.jsonl`.
- [ ] **TS-4** (FR3): During the lock wait, the task ref is made to point at a
  non-commit object. Expect exit 2 and no side effects. The run may stop at
  the clean-tree check or at the commit-type check; only exit 2 and no side
  effects are required.
- [ ] **TS-5** (FR4, NFR1): Existing fast-forward, merge-commit,
  already-contained, subdirectory and late-commit-during-wait tests still exit
  0 with exactly the expected `merged` events; the late commit made during the
  wait is the one merged.
- [ ] **TS-6** (FR5, NFR2): `tests/test_merge_unverified_exit_doc_contract.py`
  passes: hash pin, single "Parent already contains us" line followed by
  `merge-base --is-ancestor`, absence of the out-of-layout permission phrases.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Error Handling

| Condition | Exit | Output | Side effects |
|-----------|------|--------|--------------|
| Exact task ref `$IB_EXPECTED_REF` absent | 2 | ERROR line naming `$IB_EXPECTED_REF` | None |
| Task ref object is not a commit | 2 | - | None |
| Exact parent ref `refs/heads/$PARENT_BRANCH` absent | 2 | ERROR line naming the parent branch | None |
| Parent ref object is not a commit (A3) | 2 | - | None |

"None" means no ref is changed, no merge commit is created, and no journal
line is appended.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 through AC-5 are satisfied

## Open Questions

None.
