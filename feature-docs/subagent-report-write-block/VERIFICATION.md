# Verification Document: subagent-report-write-block

## Overview
**Feature**: subagent-report-write-block / **SPEC.md**: `feature-docs/subagent-report-write-block/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/subagent-report-write-block/IMPLEMENTATION.md`

TS-1 to TS-16 come from SPEC.md. TS-17 to TS-23 are added by this plan, for
requirements and mitigations SPEC.md's scenarios do not reach.

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: no coverage tool is configured; every scenario below has a test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Validate a replace_planning patch whose files hold a new `test-docs/x/REPORT.md` | Exit 1, dedicated error code, task id and path shown | Unit |
| TS-2 | Validate a patch whose new files hold `report.md`, `Analysis-notes.md`, `SUMMARY_x.MD`, `findings.md` | All rejected | Unit |
| TS-3 | Validate a patch whose files hold `report.txt`, `reports/foo.md`, `audit-report.md`, `README.md` | All pass | Unit |
| TS-4 | Validate a patch whose files hold a matching name existing as a regular file at the base commit | Passes | Unit |
| TS-5 | Validate a patch whose files hold a matching name existing as a directory at the base commit | Rejected as new | Unit |
| TS-6 | Validate a patch with a matching name without the base input, and with an unresolvable base | Both exit 2 and do not pass | Unit |
| TS-7 | Validate a patch without a matching name and without the base input | Passes as before | Unit |
| TS-8 | Validate an append_rework patch, and a plan with a new matching name in a TASK.md task | Both rejected | Unit |
| TS-9 | Validate with `--dry-run-apply` a re-planning patch with matching names in a carried non-merged task and a merged task | Only the non-merged task's violation is rejected | Unit |
| TS-10 | Apply a correction meeting the FR5 conditions, and corrections each breaking one | Only the correction meeting them is applied | Unit |
| TS-11 | Validate with a corrected task's Files section disagreeing with files | Rejected with `task-plan-files-mismatch` | Unit |
| TS-12 | Read the implementer.md and worktree-task-workflow rules | Immediate failure, report of target path and rejection text, and the workaround ban are written | Document contract |
| TS-13 | Read the implement-phase.md and batch-mode.md rules | Retry suppression, recording in `tasks.{T}.notes` and the resume condition are written | Document contract |
| TS-14 | Read the develop entry rule | Judgment at the start of a re-run, not entering inside the failed run, and stopping when conditions are not met are written | Document contract |
| TS-15 | Compare the plan-writing regex with the validation script's constant | They match | Document contract |
| TS-16 | Read the resume procedure in SPEC.md | Check of actual state, entry from failed, restart, and handling when conditions are not met are present | Manual |
| TS-17 | Read plan-writing, implementation-planner and rework-planner rules | The FR1 rules are in `## Report Artifact Names`; the agent documents cite it and contain no regex | Document contract |
| TS-18 | Inspect the new git-using test modules | Each builds its repository in a temporary directory, sets identity per command, and touches no real Claude Code configuration | Manual |
| TS-19 | Validate paths with a leading `-` or pathspec magic, and non-hexadecimal base commits | Paths are judged as literal text; such a base exits 2 | Unit |
| TS-20 | Search this feature's deliverables for Notion URLs and absolute paths under the home directory, and check that no change targets web-sip-phone | None found | Manual |
| TS-21 | Run `report-name-entry.py` on not-failed, no-violation, violation and broken-condition states | `none`, `none`, `dispatch` and `blocked` respectively; exit 2 on a missing argument or unresolvable base | Unit |
| TS-22 | Validate `path_corrections` in each permission state of IMPLEMENTATION.md D2 | Admitted only in the listed states; `in_progress` and non-empty `step_patches` rejected; a patch without the field behaves as before | Unit |
| TS-23 | Read the implement-phase.md rule for honoring `write_rejection` | Honoring conditions are written, and an unhonored report is an ordinary failure | Document contract |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | A plan with a new `test-docs/<feature>/REPORT.md` is rejected and does not proceed to implement | TS-1 |
| AC-2 | A non-matching report artifact passes validation, is not rejected by Write, and merges | TS-3, plus the manual reproduction check below |
| AC-3 | A plan updating a matching-name file at the base commit passes | TS-4 |
| AC-4 | A correction meeting FR5 is applied with everything aligned; one failing a condition is not | TS-9, TS-10, TS-11, TS-22 |
| AC-5 | A re-run enters FR5 from failed and the target restarts; the entry is not taken inside the failed run | TS-14, TS-21 |
| AC-6 | The implementer reports and the parent does not retry the same cause, including after an interruption | TS-12, TS-13, TS-23 |
| AC-7 | Recurrence tests exist and the suite passes | `python3 -m unittest discover -s tests` |
| AC-8 | SPEC.md holds the resume procedure | TS-16 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-1, TS-17 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-15 |
| FR3 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-8, TS-9 |
| FR4 | task0001, task0004 | TS-4, TS-6, TS-7 |
| FR5 | task0002, task0003, task0004 | TS-9, TS-10, TS-11, TS-22 |
| FR6 | task0002, task0006, task0007 | TS-14, TS-21 |
| FR7 | task0005 | TS-12 |
| FR8 | task0006 | TS-13, TS-23 |
| FR9 | task0001, task0002, task0003, task0004, task0005, task0006, task0007 | TS-1, TS-12, TS-13, TS-14 |
| FR10 | none (held by SPEC.md) | TS-16 |
| NFR1 | task0001, task0005 | TS-12 |
| NFR2 | task0001, task0002, task0006 | TS-3, TS-7 |
| NFR3 | task0001, task0003 | TS-15 |
| NFR4 | task0001, task0002 | TS-18 |
| NFR5 | task0001, task0002 | TS-19 |
| NFR6 | task0001, task0002, task0003, task0004, task0005, task0006, task0007 | TS-20 |

## Manual Testing (E2E Not Possible)
- [ ] TS-16: read SPEC.md's `## Resume Procedure: tcp-send-path-fr8-race-audit`.
- [ ] TS-18: inspect the new git-using test modules.
- [ ] TS-20: search the deliverables and the diff.
- [ ] Reproduction check for AC-1 and AC-2, after a Claude Code restart: in a throwaway
      project, a plan with a new `test-docs/<feature>/REPORT.md` stops at validation, and
      a plan with a non-matching report name merges into the parent branch.

## Performance / Security Verification
- TM-1: paths reach git as literal text — TS-19.
- TM-2: only a full hexadecimal commit ID is accepted — TS-6, TS-19.
- TM-3: missing or unresolvable base input never passes — TS-6.
- TM-4: conditions 1 to 4 reject a correction — TS-10.
- TM-5: condition 5 compares documents at the base commit — TS-10.
- TM-6: `path_corrections` is admitted only in the listed states — TS-22.
- TM-7: an unqualified `write_rejection` is an ordinary failure — TS-23.
- TM-8: an absolute path is not honored or recorded — TS-12, TS-23.
- TM-9: the routes around the rejection are forbidden — TS-12, TS-17.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 23 | 20 | 0 | 3 |
| Success criteria | 8 | 7 | 0 | 1 |
| Reproduction check | 1 | 0 | 0 | 1 |
| Security mitigations (TM-n) | 9 | 9 | 0 | 0 |
