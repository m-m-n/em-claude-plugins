# Verification Document: merge-docs-align-impl

## Overview
**Feature**: merge-docs-align-impl / **SPEC.md**: `feature-docs/merge-docs-align-impl/SPEC.md` / **IMPLEMENTATION.md**: omitted (reduced tier; no two tasks declare the same file)

## Build Verification
- Command: none (`build_command` is empty in workflow.yaml)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: none defined

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reason emission steps match the table's step column | For each of the three codes, the set of steps whose per-heading body contains the code is compared with the 手順 column. The column is {8, 10, 13} for `verification_failed`, {3, 4, 6, 7, 8, 9, 10, 12, 13} for `git_failed` and {3, 5} for `remote_unresolved`. `git_failed` includes the steps that call `merge-git.py` and pass its stop straight to the result | Unit |
| TS-2 | Condition content | The three Condition cells in `merge-result.md` contain the terms of each condition in FR1 through FR3. A forged row with one condition removed makes the check fire | Unit |
| TS-3 | Paths excluded from `git_failed` | In `SKILL.md`, step 2, the tip read on the PR route in step 6.4 and the rev-parse in step 9 stay `internal_error`, `main-tree` in step 13.3 stays `main_tree_not_ready`, and a merge failure there stays `merge_failed` | Unit |
| TS-4 | SSOT citation | The 結果の値 section names `references/merge-result.md` as the owner of the conditions, and the table has each of the 28 codes exactly once | Unit |
| TS-5 | README conditions | The destructive-guard row contains the terms of the two conditions and does not contain the removed sentence. A forged row keeping the original sentence makes the check fire. The canonical form plus `&& echo done` is ask, and deny in batch; an unregistered working directory is ask | Unit |

## Code Quality Verification
- Format: none (`format_command` is empty in workflow.yaml)
- Static analysis: none defined

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The `verification_failed` Condition contains all of FR1 (a) through (e) | TS-2 |
| AC-2 | The `git_failed` Condition contains all of FR2 (a) through (g) and does not include the failures FR2 excludes | TS-2, TS-3 |
| AC-3 | The `remote_unresolved` Condition contains the two existing conditions and all of FR3 (a) through (d) | TS-2 |
| AC-4 | The 結果の値 section names `merge-result.md` as the owner, the `git_failed` and `verification_failed` rows are updated, and the table stays at 28 rows | TS-1, TS-4 |
| AC-5 | The README's destructive-guard row states the two conditions and does not contain the removed sentence | TS-5 |
| AC-6 | The FR6 tests exist, fire on forged text, and `python3 -m unittest discover -s tests` passes | TS-1 through TS-5, Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-2 |
| FR2 | task0001 | TS-2, TS-3 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-1, TS-4 |
| FR5 | task0002 | TS-5 |
| FR6 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| NFR1 | task0001, task0002 | TS-1, TS-4, Performance / Security Verification |
| NFR2 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| NFR3 | task0001 | TS-1, TS-2, TS-4 |
| NFR4 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| NFR5 | task0001, task0002 | Performance / Security Verification (no scenario assigned) |

## E2E Testing
None. SPEC.md records no existing E2E tests.

## Manual Testing (E2E Not Possible)
None.

## Performance / Security Verification (if applicable)
- NFR1: no file under `em-workflow/hooks/` or `em-workflow/scripts/` differs between the `implement` step's `base_commit` and the integration branch tip.
- NFR5: searching every file changed by this feature finds no Notion URL and no absolute path under the home directory (`em-workflow/references/doc-redaction.md`).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 5 | 5 | 0 | 0 |
| Acceptance criteria | 6 | 6 | 0 | 0 |
| Requirements coverage | 11 | 11 | 0 | 0 |
| Performance / Security | 2 | 2 | 0 | 0 |
