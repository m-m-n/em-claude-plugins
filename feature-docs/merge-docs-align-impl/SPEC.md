# Feature: merge-docs-align-impl

## Overview

This feature aligns the merge documentation with its implementation. The
conditions of three reason codes in `em-workflow/references/merge-result.md`
are made to match their emission sites in `em-workflow/skills/merge/SKILL.md`,
and the destructive-guard row of `em-workflow/README.md` states the conditions
of the `gh pr merge` exception. Tests detect drift between these documents and
the implementation.

## Objectives

- Make the reason code conditions in `merge-result.md` match the actual
  emission sites in `SKILL.md`.
- State the conditions of the `gh pr merge` exception in the README's
  destructive-guard row as implemented.
- Make drift between the documents and the implementation detectable by tests.

## User Stories

None defined.

## Acceptance Criteria

- [ ] AC-1: The `verification_failed` Condition in `merge-result.md` contains
  all of FR1 (a) through (e). (FR1)
- [ ] AC-2: The `git_failed` Condition in `merge-result.md` contains all of FR2
  (a) through (g) and does not include the failures FR2 excludes. (FR2)
- [ ] AC-3: The `remote_unresolved` Condition in `merge-result.md` contains the
  two existing conditions and all of FR3 (a) through (d). (FR3)
- [ ] AC-4: The 結果の値 section of `SKILL.md` names `merge-result.md` as the
  owner of the conditions, the `git_failed` row's steps are
  {3, 4, 6, 7, 8, 9, 10, 12, 13}, the `verification_failed` row's detail
  contains the step 10 uncommitted changes and HEAD mismatch, and the table
  stays at 28 rows. (FR4, NFR1, NFR3)
- [ ] AC-5: The README's destructive-guard row states the two conditions (sole
  statement, registered integration worktree) and does not contain
  「同じコマンドの後続の区間も通常どおり判定する」. (FR5)
- [ ] AC-6: The FR6 tests exist, fire on forged text, and
  `python3 -m unittest discover -s tests` passes. (FR6, NFR2, NFR4)

## Technical Requirements

### Functional Requirements

Step numbers in FR1 through FR3 identify the emission sites in `SKILL.md`. They
are not written into the `merge-result.md` Condition cells (A-2).

- **FR1:** `verification_failed` condition. The `verification_failed` Condition
  in the Reason codes table of `em-workflow/references/merge-result.md` states
  all of the following. Emitted by stays `the skill, merge-git integrate`.
  - (a) A build / test / e2e command failed or timed out (step 10).
  - (b) Before integration, the HEAD of the integration worktree differs from
    the expected tip (`head_sha` on a retry) (step 8, `merge-git integrate`).
  - (c) After the verification commands, tracked files have uncommitted changes
    (step 10).
  - (d) After the verification commands, HEAD differs from the verified
    `head_sha` (step 10).
  - (e) Immediately before the local merge, the tip of the integration branch
    differs from the verified `head_sha` (step 13.3).
- **FR2:** `git_failed` condition. The `git_failed` Condition in
  `merge-result.md` states all of the following.
  - (a) A failure with which a `merge-git` subcommand stopped as `git_failed`,
    including a git command failure, a launch failure, a timeout, and reaching
    the script-wide time limit. This covers: `route` reading remote / config;
    `merged` reading the tip and the ancestor check; `main-tree`;
    `worktree-state` running worktree list / git-path / status; `integrate`
    running fetch and a non-conflict merge failure; `base-check`
    (steps 3, 4, 6, 7, 8, 9, 12).
  - (b) `git worktree add` failed (step 7).
  - (c) `git merge --abort` failed for `merge_in_progress` in step 7, or for the
    unattributable case in step 9.
  - (d) `worktree-state` after the add / abort is neither `clean` nor `stop`
    (steps 7, 9).
  - (e) The conflict-resolution `git commit` failed (step 9).
  - (f) `git status` / `git rev-parse HEAD` failed after verification (step 10).
  - (g) `git rev-parse` of the integration tip failed immediately before the
    local merge (step 13.3).

  The following are not part of `git_failed`:
  - Git failures in step 2, the failure to read the tip on the PR route in step
    6.4, and an invalid value from the post-commit rev-parse in step 9 (each is
    `internal_error`).
  - `main-tree` not being ready in step 13.3 (`main_tree_not_ready`).
  - `git merge --abort` failing after a merge failure in step 13.3 (the result
    is `merge_failed`).
  - Reads after a successful merge and step 15 failures (the result stays
    `merged` / `already_merged`).
- **FR3:** `remote_unresolved` condition. The `remote_unresolved` Condition in
  `merge-result.md` states the two existing conditions (no remote can be chosen,
  the remote name is unsafe) and all of the following from `merge-pr repo`.
  Emitted by stays `merge-git route, merge-pr repo`.
  - (a) The remote does not exist.
  - (b) The gh default repository cannot be determined.
  - (c) On either the remote side or the default side, the host of the URL gh
    reported is malformed.
  - (d) The default repository and the remote differ in host or owner/name
    (case-insensitive).

  The following are not part of `remote_unresolved`:
  - Zero remotes (the local route).
  - The gh default repository query output not being JSON, and `url` being
    missing or not a string (`internal_error`).
- **FR4:** `SKILL.md` result value table. The 結果の値 section of
  `em-workflow/skills/merge/SKILL.md` states that the owner of each reason's
  condition is Reason codes in `references/merge-result.md`. The table's columns
  (reason / 出どころ / 手順 / detail) and its 28 rows are kept. The `git_failed`
  row's 手順 becomes 3, 4, 6, 7, 8, 9, 10, 12, 13. The `verification_failed`
  row's detail gains the step 10 uncommitted changes and HEAD mismatch.
- **FR5:** README destructive-guard row. The `hooks/destructive-guard.py` row of
  the hook table in `em-workflow/README.md` states these two conditions of the
  `gh pr merge` exception:
  - (a) The canonical form is the only statement in the command.
  - (b) The working directory is a registered integration worktree or is under
    one.

  「同じコマンドの後続の区間も通常どおり判定する」 is removed. The row states that
  the exception does not hold when the same command has another statement,
  before or after, and that a deny in another statement gives that verdict.
- **FR6:** Drift detection tests. Tests added to `tests/test_merge_skill_doc.py`
  and `tests/test_destructive_guard_merge_allow.py` detect the following.
  - (a) For each of `verification_failed`, `git_failed` and `remote_unresolved`,
    the set of `SKILL.md` steps that write the code is contained in the 手順
    column of the result value table. For `verification_failed` and
    `remote_unresolved` the two match. For `git_failed` the column also contains
    the steps that call `merge-git.py` and pass its stop straight to the result.
  - (b) The three Condition cells in `merge-result.md` contain the terms of each
    condition in FR1 through FR3.
  - (c) The README destructive-guard row contains the terms of the two
    conditions and does not contain 「後続の区間も通常どおり判定する」.

### Non-Functional Requirements

- **NFR1 - Change scope:** The set of 28 reason codes does not change. The code
  in `em-workflow/hooks/` and `em-workflow/scripts/` does not change.
- **NFR2 - Consistency with existing tests:** The following stay true.
  - The `verification_failed` Condition in `merge-result.md` contains
    `HEAD before integration differs from the expected`, and its Emitted by
    contains `merge-git integrate`.
  - The `verification_failed` row in `SKILL.md` has 4 cells, its steps are
    {8, 10, 13}, its 出どころ contains `merge-git integrate`, and its detail
    contains `component.field`, `integration branch moved after preflight` and
    `integration branch moved after verification`.
  - The README row is one line starting with `hooks/destructive-guard.py`, and
    contains `gh pr merge` and `integration worktree`.
- **NFR3 - Table format:** `merge-result.md` rows stay at 3 cells and `SKILL.md`
  rows stay at 4 cells. Cell bodies do not contain `|`.
- **NFR4 - Test conventions:** Tests use only the standard library's `unittest`.
  Every assertion of absence is paired with a forged-text case that shows the
  matcher fires.
- **NFR5 - Document redaction:** Documents and tests contain no Notion URL and no
  absolute path under the home directory.

## Assumptions

- **A-1:** 「SKILL.md 側の表は SSOT を引用する形に寄せる」 means keeping the table
  and stating that `merge-result.md` owns the conditions. No table row or column
  is removed. The `SKILL.md` table has no condition column; it holds source,
  step and detail, and `tests/test_merge_skill_doc.py` pins the 28 rows and the
  4 cells of the `verification_failed` row.
- **A-2:** `merge-result.md` Conditions are written in terms of operations, with
  no step numbers. Only the `SKILL.md` table carries step numbers. The
  `merge-result.md` Reason codes table has no step numbers today.
- **A-3:** The README states only the two requested conditions. It does not state
  symlinks or nested repositories under the worktree, or the registration check
  details (HEAD being the feature's integration branch). The acceptance criteria
  specify the two conditions; the details live in the docstring and
  implementation of `merge_pr_allow.py`.
- **A-4:** Following the acceptance criterion "contains all emission sites in
  SKILL.md", emission sites not named in the request are in scope: the paths to
  `git_failed` from the `worktree-state` recheck, a nonexistent remote, an
  undeterminable default repository, and differing hosts. The paths to
  `git_failed` from all `merge-git` subcommands, and the paths excluded from
  `remote_unresolved`, are also in scope. These paths exist in steps 7 and 9 of
  `SKILL.md` and in the `repo` subcommand of `merge-pr.py`.

## Implementation Approach

### Architecture

Not applicable. The change is limited to three documents and tests, with no
screen or UI. The design step was skipped.

### Dependencies

**Internal Dependencies:**
- `tests/test_merge_skill_doc.py`: pins the `SKILL.md` table (NFR2).
- `tests/test_destructive_guard_merge_allow.py`: verifies the behavior the README
  row states (TS-5).

**External Dependencies:**
- None. Tests use the Python standard library's `unittest`.

### File Structure

```
em-workflow/
├── README.md                              # FR5
├── references/
│   └── merge-result.md                    # FR1, FR2, FR3
└── skills/
    └── merge/
        └── SKILL.md                       # FR4
tests/
├── test_merge_skill_doc.py                # FR6
└── test_destructive_guard_merge_allow.py  # FR6
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-docs-align-impl/**`
- `test-docs/merge-docs-align-impl/**`

`feature-docs/merge-docs-align-impl/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-docs-align-impl/**` covers
`test-docs/merge-docs-align-impl/{T}.tests.yaml`, the per-task test record. It
is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/merge-docs-align-impl/` directory at all; the declared
`test-docs/merge-docs-align-impl/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1: Reason emission steps match the table's step column - For each of
  the three codes, the set of steps whose per-heading body contains the code is
  compared with the 手順 column of the result value table. The column is
  {8, 10, 13} for `verification_failed`, {3, 4, 6, 7, 8, 9, 10, 12, 13} for
  `git_failed` and {3, 5} for `remote_unresolved`. `git_failed` is confirmed to
  include the steps that call `merge-git.py` and pass its stop straight to the
  result. The table before this change fails, because it lacks 3, 4, 6 and 10.
  (Covers AC-4, AC-6)
- [ ] TS-2: Condition content - The three Condition cells in `merge-result.md`
  contain the terms of each condition in FR1 through FR3. A forged row with one
  condition removed makes the check fire. (Covers AC-1, AC-2, AC-3, AC-6)
- [ ] TS-3: Paths excluded from `git_failed` - In `SKILL.md`, step 2, the tip read
  on the PR route in step 6.4 and the rev-parse in step 9 stay `internal_error`,
  `main-tree` in step 13.3 stays `main_tree_not_ready`, and a merge failure there
  stays `merge_failed`. (Covers AC-2, AC-6)
- [ ] TS-4: SSOT citation - The 結果の値 section names
  `references/merge-result.md` as the owner of the conditions, and the table has
  each of the 28 codes exactly once. (Covers AC-4, AC-6)
- [ ] TS-5: README conditions - The destructive-guard row contains the terms of
  the two conditions and does not contain the removed sentence. A forged row
  keeping the original sentence makes the check fire. The behavior the document
  claims (the canonical form plus `&& echo done` is ask, and deny in batch; an
  unregistered working directory is ask) is verified by the existing
  `tests/test_destructive_guard_merge_allow.py`. (Covers AC-5, AC-6)

### Integration Tests

None.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

None.

### Performance Tests

None.

## Security Considerations

NFR5 applies. No other security requirement is defined.

## Error Handling

Not applicable. No code in `em-workflow/hooks/` or `em-workflow/scripts/` changes
(NFR1).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] All acceptance criteria are met
- [ ] Code review is completed

## Open Questions

None.

## References

- Reason code SSOT: `em-workflow/references/merge-result.md`
- Merge skill: `em-workflow/skills/merge/SKILL.md`
- Hook table: `em-workflow/README.md`
- `gh pr merge` exception implementation: `em-workflow/hooks/merge_pr_allow.py`
