# Verification Document: merge-tip-binding

## Overview
**Feature**: merge-tip-binding / **SPEC.md**: `feature-docs/merge-tip-binding/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/merge-tip-binding/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/merge-tip-binding/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty).
- Expected: nothing to build.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root of the integration worktree)
- Expected: exit code 0, no failures, no errors.
- Coverage target: no coverage tool is configured; coverage is judged by the scenario and requirement mapping below.

### Test Scenarios from SPEC.md
TS1–TS8 are SPEC.md's scenarios; TS9–TS11 are added by this plan to give FR5's held-values clause and the cross-cutting NFRs their own check.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Doc test of SKILL.md step 6: Bash blocks in document order are the `--wait` verify, a standalone `cd "<project_root>"`, the read `git rev-parse --verify refs/heads/em-workflow/<feature>/integration`, then `merge-pr.py resolve`; each has its own timeout line; the resolve form passes `--integration-tip <locked_tip>`; item 4 states the 40-lowercase-hex rule, 手順 14 and `internal_error` for a failed or invalid read, and that `integration_tip` is not overwritten | All assertions hold on SKILL.md; each matcher fires on a forged document (no read, read before the wait, resolve still carrying `<integration_tip>`) | Unit |
| TS2 | Existing `test_task0010_ac4_*` in `tests/test_merge_pr.py`: a MERGED PR whose head is T2 | `--integration-tip T2` gives `merged`, T1 gives `none`; `merge-pr.py` unchanged | Integration |
| TS3 | `tests/test_merge_git.py`: `integrate` with a mismatching `--expected-head` in a temporary repository with a remote; with a matching value; with the option missing, uppercase, too short, too long or non-hex | Mismatch: `stop` / `verification_failed` / `integration branch moved after preflight`, `head` and `integrated_base` null, no `fetch` or `merge` in the shim log, refs and worktree unchanged; earlier checks still win (dirty, absent, merge in progress). Match: every existing outcome unchanged. Invalid option: exit 2, empty stdout | Unit |
| TS4 | `tests/test_merge_local_route.py`: the integration tip is taken (by preflight in the full chain), a commit is made inside the integration worktree, then `integrate` runs with that tip; and the same chain without the commit | With the commit: `verification_failed`, base tip unchanged, the commit not reachable from base. Without it: the chain lands the merge commit as before | Integration |
| TS5 | Doc test of SKILL.md step 8 | Exactly two integrate forms: `--expected-head <integration_tip>` (first integration) and `--expected-head <head_sha>` (return from the step 12 redo, including after step 9), each with a timeout line, none with `<locked_tip>`; the stop bullet names `verification_failed` and 手順 14 | Unit |
| TS6 | Doc test of the `verification_failed` rows | SKILL.md row: 手順 {8, 10, 13}, 出どころ contains `merge-git integrate`, detail contains the step 8 and step 13 fixed texts. `merge-result.md` row: Condition has the pre-integration HEAD mismatch, Emitted by has `merge-git integrate`. Both tables hold exactly 28 codes; `merge-result.py` unchanged | Unit |
| TS7 | Doc test of step 6 item 4's opening statement | No 「手順 4 / 5.2 と同じ `integration_tip`」; the local route is stated to judge the tip at the time `merge-git.py merged` is called, the PR route to judge `locked_tip`; the matcher fires on a forged item 4 that keeps the old phrase | Unit |
| TS8 | Full suite | `python3 -m unittest discover -s tests` exits 0 | Integration |
| TS9 | Doc test of 「保持する値」 | `integration_tip` is described as also used for the step 8 check and not overwritten; `locked_tip` is listed as the post-lock tip passed only to the step 6.4 `resolve`; the matcher fires on a forged list without `locked_tip` | Unit |
| TS10 | Cross-cutting constraints keep holding: existing doc tests for literal command forms, foreground timeout lines, the closed script-call set and script-option agreement, no state file and no `workflow.yaml` write, no Notion URL or home path; the `decide` helper of `tests/test_merge_git.py` rejecting a temporary-directory path in `detail` | All pass on the integrated tree | Unit |
| TS11 | Version check on the integrated diff (implement `base_commit` to the integration tip) | The diff contains no change to `em-workflow/.claude-plugin/plugin.json` and none to the `em-workflow` entry of `.claude-plugin/marketplace.json` | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty). Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | Every FR row below has at least one task and one passing scenario |
| SC2 | All test scenarios pass | TS1–TS11 pass |
| SC3 | AC-1 to AC-8 of SPEC.md hold | AC-1 → TS1; AC-2 → TS2, TS1; AC-3 → TS3; AC-4 → TS4; AC-5 → TS5; AC-6 → TS6; AC-7 → TS7; AC-8 → TS8 |
| SC4 | `python3 -m unittest discover -s tests` passes | TS8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS1, TS2 |
| FR2 | task0001 | TS3, TS4 |
| FR3 | task0001 | TS4, TS5 |
| FR4 | task0001 | TS6 |
| FR5 | task0002 | TS7, TS9 |
| FR6 | task0001, task0002 | TS1, TS3, TS4, TS5, TS6, TS7, TS8, TS9 |
| NFR1 | task0001, task0002 | TS1, TS3, TS4 |
| NFR2 | task0001, task0002 | TS1, TS5, TS10 |
| NFR3 | task0001, task0002 | TS10 |
| NFR4 | task0001, task0002 | TS3, TS4, TS8, manual review below |
| NFR5 | task0001, task0002 | TS3, TS10 |
| NFR6 | task0001, task0002 | TS11 |

## E2E Testing
No E2E framework (`e2e_test_command` is empty); no E2E items.

## Manual Testing (E2E Not Possible)
- [ ] NFR4 review: the new tests in `tests/test_merge_git.py` and `tests/test_merge_local_route.py` reproduce the moved branch by committing at a fixed point; none uses a busy loop, a sleep loop, a load tool or parallel processes.

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md).
- TM-1: `integrate` refuses a worktree HEAD other than the expected head before any fetch or merge, and step 8 passes `integration_tip` / `head_sha` and stops via 手順 14 on `verification_failed` — checked by TS3 (mismatch stop, no `fetch` / `merge` in the shim log, refs unchanged), TS4 (a commit added after preflight never reaches base) and TS5 (step 8 forms and stop handling).
- TM-2: `--expected-head` is required and only 40 lowercase hex is accepted — checked by TS3's exit-2 cases (missing, uppercase, too short, too long, non-hex; stdout empty).
- TM-3: the post-lock read becomes `locked_tip` only as exactly 40 lowercase hex, otherwise 手順 14 then `internal_error` — checked by TS1 (rule text present, read form shell-safe, forged controls).
- TM-4: `locked_tip` is used only by the step 6.4 `resolve` and `integration_tip` is never overwritten — checked by TS1 (step 6 resolve carries `<locked_tip>`), TS5 (step 8's first form carries `<integration_tip>`, no form carries `<locked_tip>`) and TS9 (held values).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS11) | 11 | 11 | 0 | 0 |
| Security (TM-1–TM-4) | 4 | 4 | 0 | 0 |
| Manual review (NFR4) | 1 | 0 | 0 | 1 |
| Total | 16 | 15 | 0 | 1 |
