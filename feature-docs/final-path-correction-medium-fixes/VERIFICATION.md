# Verification Document: final-path-correction-medium-fixes

## Overview

**Feature**: final-path-correction-medium-fixes / **SPEC.md**: `feature-docs/final-path-correction-medium-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/final-path-correction-medium-fixes/IMPLEMENTATION.md`

## Build Verification

- Command: none (`build_command` is empty in workflow.yaml).

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0.
- Coverage target: not measured. Every scenario below maps to at least one test.

### Test Scenarios from SPEC.md

TS-15 and TS-16 are added here: no SPEC.md scenario covers NFR1, or NFR2 as a whole.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Correction entry, entries with an unrelated file and `requirements_patch` `set.status: excluded`, through `validate_worker_result` dry run | Rejected with both new codes | Unit |
| TS-2 | `requirements_patch` variants: `tests_append`, `status`, `tests_replace`, an unregistered requirement id, `tasks_append` of a carried id | Each rejected with `path-correction-requirements` | Unit |
| TS-3 | Entry files: new file, directory, regular file without a reference, non-UTF-8 file, empty list, regular file referencing the old path, regular file referencing the bare name; plan differing from the canonical text; a file with a newline or backtick in its name | Only the two reference cases with the canonical plan pass | Unit |
| TS-4 | The same entries and `requirements_patch` on the Re-planning path | Not rejected by the new codes | Unit |
| TS-5 | `new_path` with spaces, a newline, a backtick, `:(top)README.md`, `-x.md`, `.`, `./`, `a//b.md`, `a/`, and a non-ASCII directory | All rejected except the non-ASCII directory | Unit |
| TS-6 | Non-target plan edited and reference-replaced, for pending, failed, merged by status and merged by journal; shared TASK.md plan with path replacement only; shared plan including a merged task | Edits rejected; replacement passes only unmerged; shared plan passes unless a merged task shares it | Unit |
| TS-7 | Entry with failed and unstarted tasks holding violations; merged task holding a name; unstarted task whose last journal event is merged; unstarted task whose name is a directory at the base | Both listed with a null line for the unstarted task; merged task not listed; the last two blocked | Unit |
| TS-8 | Entry output of two targets fed through a corrected patch and validated | No `report-name-new-file` error | Unit |
| TS-9 | Re-planning with `path_corrections`, body updates, `needs_update` and route-back states | Pass with the residual check only; old path or bare name left is rejected | Unit |
| TS-10 | Scenario-ID scan on a correction patch: correction entry, Re-planning path, workflow absent | Skipped on the correction entry only | Unit |
| TS-11 | Two corrections sharing an old file name: shared documents, each target plan, a plan of a task with neither; candidate names swapped outside an occurrence; old file name inside `a/release-REPORT.md`; plan shared by two targets | Per FR6 | Unit |
| TS-12 | Boundary cases of the bare name: backtick, parenthesis, sentence-final period, Japanese text directly adjacent, `#anchor`, directory prefix, name prefix, `.bak` suffix, different case, one-segment old path; multi-segment old path under a longer path and after `./` | Per FR7 | Unit |
| TS-13 | Document tests read workflow-patch.md, implementation-planner.md and create-plan-phase.md | The rules and the two new codes are stated | Unit |
| TS-14 | Correction entry with a plan document absent at the base: VERIFICATION.md, IMPLEMENTATION.md, an existing task's plan, an entry plan naming VERIFICATION.md or `./VERIFICATION.md`, a new task's own plan | Only the last passes | Unit |
| TS-15 | A patch without `path_corrections` holding entries and `requirements_patch`, in the initial-planning and re-planning states | Validates as before | Unit |
| TS-16 | A compared document or entry file that is a symlink, over the read limit or not UTF-8; a missing validator input; entry script exit codes | Each document or file is a rejection; a missing input exits 2; the entry script's exit codes are unchanged | Unit |

## Code Quality Verification

- Format: none (`format_command` is empty in workflow.yaml).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The round 1 reproduction of 73c084892e91326c is rejected with both new codes | TS-1 |
| AC-2 | An entry with its canonical plan and `tasks_append` passes; an added line is rejected, TASK.md included | TS-3 |
| AC-3 | The round 1 `new_path` sentence and the newline form on a TASK.md plan are rejected | TS-5 |
| AC-4 | Non-target plan edits are rejected for pending, failed and merged; replacement passes only unmerged; an unchanged plan passes | TS-6 |
| AC-5 | The entry returns `dispatch` listing failed and unstarted tasks, and correcting both passes the validator | TS-7, TS-8 |
| AC-6 | A failed task with no violation beside a pending task with one returns `none` | TS-7 |
| AC-7 | A re-planning patch with body updates passes; a left reference is rejected; a hyphen-less ID in VERIFICATION.md is reported | TS-9, TS-10 |
| AC-8 | On the correction entry the comparison rejects a body change and VERIFICATION.md is not scanned | TS-9, TS-10 |
| AC-9 | The a/REPORT.md and b/REPORT.md example passes; the wrong new name and `enabled` to `disabled` are rejected | TS-11 |
| AC-10 | A left bare name is rejected; `existing/REPORT.md`, `PREREPORT.md` and `REPORT.md.bak` left unchanged pass | TS-12 |
| AC-11 | The test command passes, with a recurrence test per finding and the Reference Impact tests updated | Test command; manual check below |
| AC-12 | A newly created VERIFICATION.md is rejected, also when an entry names it as its plan; a new task's own plan at a free path passes | TS-14 |
| AC-13 | A plan shared by two targets passes with both tasks' replacements and the union of their files | TS-11 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR2 | task0001 | TS-5 |
| FR3 | task0001 | TS-6 |
| FR4 | task0002 | TS-7, TS-8 |
| FR5 | task0001 | TS-4, TS-9, TS-10 |
| FR6 | task0001 | TS-11 |
| FR7 | task0001 | TS-9, TS-12 |
| FR8 | task0001, task0002, task0003 | TS-13; docstrings by the manual check below |
| FR9 | task0001 | TS-14 |
| NFR1 | task0001 | TS-15 |
| NFR2 | task0001, task0002 | TS-16 |
| NFR3 | task0001 | TS-3, TS-5 |
| NFR4 | task0001, task0002, task0003 | TS-7; diff by the manual check below |

## Manual Testing (E2E Not Possible)

- [ ] The canonical plan lines in implementation-planner.md render the same bytes as the validator's canonical function, compared on the integrated branch.
- [ ] Each of the seven stable_ids appears in a recurrence test.
- [ ] The docstrings of `report-name-entry.py` and of the changed validator functions state FR4 to FR7.
- [ ] The integrated diff adds no `gate_id`, no user question and no `workflow.yaml` field.

## Performance / Security Verification

- TM-1: entries limited to files holding an old reference at the base commit — TS-1 and TS-3.
- TM-2: `requirements_patch` limited to `tasks_append` of entry ids — TS-1 and TS-2.
- TM-3: `new_path` form check in condition 4 — TS-5.
- TM-4: every plan compared, and merged plans byte-equal to the base commit — TS-6.
- TM-5: documents created on the correction entry rejected after path normalization — TS-14.
- TM-6: positional comparison with literal replacements — TS-11, the `enabled` to `disabled` case.
- TM-7: scenario-ID scan skipped on the correction entry only — TS-10.
- TM-8: alignment search bounded by visited states — a crafted text with prefix-related permitted texts completes (TS-11).
- TM-9: entry files read only through `base_tree_entry` and `_read_base_document` — TS-3, and a code read of the new base reads.
- TM-10: read limit and UTF-8 check on entry files — TS-16.
- TM-11: entry plan byte-equal to the canonical text — TS-3, with the TASK.md case.
- TM-12: form check before rendering — TS-3, the file with a newline or backtick.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 16 | 16 | 0 | 0 |
| Success criteria | 13 | 13 | 0 | 1 (AC-11 also has a manual check) |
| Security (TM-n) | 12 | 12 | 0 | 1 (TM-9 also has a code read) |
| Manual checks | 4 | 0 | 0 | 4 |
