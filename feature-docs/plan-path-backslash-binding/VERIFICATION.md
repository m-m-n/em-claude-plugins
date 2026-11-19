# Verification Document: plan-path-backslash-binding

## Overview
**Feature**: plan-path-backslash-binding / **SPEC.md**: `feature-docs/plan-path-backslash-binding/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/plan-path-backslash-binding/IMPLEMENTATION.md`

This document covers the integrated verification run by the verify phase.
Task-level criteria live in `tasks/task0001.md` and `tasks/task0002.md`.

## Build Verification
- Command: none (`build_command` of the `main` component is empty).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failure and no error.
- Coverage: not measured (standard library only); every scenario below maps
  to at least one test or check.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Docs: the `task_plan_path` line of the Step I.2.a payload in `implement-phase.md` | The line states joining the `path_segments` segments of `tasks.{T}.plan` onto the integration worktree's `feature-docs/{feature}/` and keeps its position (after `worktree_path`, before `implementation_md_path`, before the `## Untrusted data` line); the verbatim pre-fix line ("joined with the stored tasks.{T}.plan value") is flagged | Unit (docs) |
| TS-2 | Docs: the Plan-path check paragraph | Rules 2 and 3 target the normalized joined path; four bullets of one sentence each; no forbidden phrase, at most two condition markers per sentence, no uppercase EVERY or ALL; a sample with one rule removed, a sample with the new wording removed and the verbatim pre-fix rules 2 and 3 are flagged | Unit (docs) |
| TS-3 | Docs: section 2a of `phases/create-plan-phase.md` | The resolution sentence names `path_segments`, cites the Plan-path check and is separate from the stored-value sentence; the verbatim pre-fix section 2a ("joined with that value") is flagged | Unit (docs) |
| TS-4 | Behavior against the decoy: the canonical `tasks/task0003.md` and a decoy literally named `\task0003.md`, plan values `tasks/\task0003.md` and `tasks\task0003.md` | The documented derivation equals the path `_resolve_contained_relative_path` returns, reads the canonical text and never names the decoy; the pre-fix derivation reaches the decoy or a nonexistent path | Integration |
| TS-5 | Regression | `tests/test_final_path_correction.py` (including `TestPlanBindingAdmits.test_every_spelling_of_tasks_t_md_is_bound`) and the remaining tests of `tests/test_final_path_correction_docs.py` pass | Integration |
| TS-6 | Change set (added by this plan for NFR3 and FR4; not in SPEC.md) | Between `implement.base_commit` and the integration branch tip, no file under a `.claude-plugin/` directory is changed, and `em-workflow/scripts/validate-worker-output.py` is not changed | Manual |

## Code Quality Verification
- Format: none (`format_command` is empty). Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The `task_plan_path` line joins the normalized segments onto `feature-docs/{feature}/`, does not join the stored string as-is, and keeps its position | TS-1 |
| AC-2 | Plan-path check rules 2 and 3 target the same normalized joined path; four rules, one sentence each, within the NFR1 constraints | TS-2 |
| AC-3 | The section 2a resolution sentence states the normalized join, cites the Plan-path check and is separate from the stored-value sentence | TS-3 |
| AC-4 | The attack scenario does not hold | TS-4 |
| AC-5 | The validator's existing behavior is unchanged and its existing tests pass unchanged | TS-5, TS-6 |
| AC-6 | The updated docs tests flag the pre-fix wording | TS-1, TS-2, TS-3 |
| AC-7 | `python3 -m unittest discover -s tests` passes in full | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-4 |
| FR2 | task0001 | TS-2, TS-4 |
| FR3 | task0001 | TS-3 |
| FR4 | task0002 | TS-4, TS-5, TS-6 |
| FR5 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-2 |
| NFR2 | task0001, task0002 | TS-5 and the full test command |
| NFR3 | task0001, task0002 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] TS-6: list the files changed between `implement.base_commit` and the
  integration branch tip with a read-only git command, and confirm that none
  is under a `.claude-plugin/` directory and that
  `em-workflow/scripts/validate-worker-output.py` is not among them.

## Performance / Security Verification (if applicable)
- TM-1: `task_plan_path` and section 2a join the `path_segments` segments of the stored value, the path the validator reads, never the stored string as-is — checked by TS-1, TS-3 and TS-4.
- TM-2: Plan-path check rules 2 and 3 judge the same normalized joined path that `task_plan_path` carries — checked by TS-2.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 6 | 5 | 0 | 1 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 7 | 7 | 0 | 0 |
| Requirements coverage | 8 | 7 | 0 | 1 |
| Security (TM-n) | 2 | 2 | 0 | 0 |
