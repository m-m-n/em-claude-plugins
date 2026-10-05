# Verification Document: sca-file-tasks-robustness

## Overview
**Feature**: sca-file-tasks-robustness / **SPEC.md**: `feature-docs/sca-file-tasks-robustness/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-file-tasks-robustness/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-file-tasks-robustness/THREAT-MODEL.md`

## Build Verification
- Command: none (`build_command` is empty for both components `repo-tests` and `plugin-invariants`).
- Expected: not applicable.

## Test Verification
- Command (component `repo-tests`): `python3 -m unittest discover -s tests`
- Expected: exit code 0, every test passes (SPEC AC10).
- Coverage target: not measured (standard-library unittest only; no coverage tool is part of the project).

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1) For each of the pip, npm, cargo and go normalizers: advisory text with LF, CRLF, TAB and Unicode whitespace; a short title made only of whitespace; a title longer than 4096 bytes. Then run the findings through file_tasks. | Titles contain no line break; recover_package_advisory returns the original (package, advisory_id); no finding is malformed; file_tasks yields a task or report entry for every package; the over-long title is truncated after the collapse | Unit/Integration |
| TS-2 | (SPEC TS2) Real CLI, 3 packages, stand-in entry point whose create launch fails with an OS error on the 2nd package (bad interpreter placed after the listing) | Exit 0; exactly one JSON object on stdout; no traceback; filed_packages = [1st]; failed_package = 2nd; failure_reason = task_create_failed; unattempted_packages = [2nd, 3rd]; 3rd never attempted | Integration |
| TS-3 | (SPEC TS3) Same as TS-2 on the append path (existing incomplete tasks) | As TS-2 with appended_packages = [1st] and failure_reason = task_update_failed | Integration |
| TS-4 | (SPEC TS4) Writing the temporary references file raises an OS error on the 2nd package | Handled like TS-2 / TS-3; no exception escapes file_tasks | Unit |
| TS-5 | (SPEC TS5) The 1st package fails | filed and appended empty; unattempted_packages holds every non-malformed package in processing order; malformed findings absent | Unit |
| TS-6 | (SPEC TS6) Full success, report branch, degraded report branch | unattempted_packages == [] on all three | Unit |
| TS-7 | (SPEC TS7) Existing listing-launch-failure degraded case (bad interpreter from the start) | branch report, degraded true, degraded_reason listing_launch_failed, unchanged | Integration |
| TS-8 | (SPEC TS8) Document-text tests on review-phase.md | R4 receipt item, R5 YAML block and R5 prose each carry the five fields with the another-round values; the unattempted-package rule (no automatic retry, remainder-only re-run with its listing condition); "triage filing incomplete" with packages in R6 and the batch final result; completion condition unchanged; no gate identifier; existing pins kept | Unit (document text) |
| TS-9 | (SPEC TS9) build_scan_jobs grouping / order / reason tests as plan checks, including real-path grouping for symlinked aliases and `..` paths; argv / env / cwd checks on build_scan_job and run_scan; run_scan shown to go through build_scan_jobs with a test double; a symlink swapped after planning is rejected by the run-side binding check | Plans carry the six fields in registry and group order; run_scan launches exactly the returned plans without re-selecting targets; the swapped plan launches nothing, gets no isolation directory and reports the unbindable token | Unit/Integration |
| TS-10 | (SPEC TS10) Existing run_scan end-to-end suites: execution, normalization, binding, isolation, pip lockfile, go real output, unchanged surfaces | Pass with their observed-behaviour assertions unchanged | Integration |
| TS-11 | (NFR2) An OS error whose message carries a unique marker and an advisory short title carrying another unique marker | Neither marker in failure_reason, any malformed reason, unattempted_packages or the printed JSON summary; the OS-error marker appears on stderr | Unit |
| TS-12 | (NFR5) Summary key set on every return branch (ntd success, ntd partial failure, report, degraded report); existing file-tasks test module | Exactly the eleven pre-existing keys plus unattempted_packages; tests/test_sca_task_filing.py passes unchanged | Unit |
| TS-13 | (NFR3) Imports of the script and of every new or modified test module | Standard library only (each module's import assertion passes) | Unit |
| TS-14 | (NFR4) Integrated diff from the implement base commit to HEAD | No change to any `.claude-plugin/plugin.json` or to `.claude-plugin/marketplace.json` | Manual (git diff) |
| TS-15 | (FR5, NFR6; SPEC TS8's batch final result part) Document-text tests on batch-mode.md's `## Reporting` and audit-item source map | Exactly one added Reporting item carrying "triage filing incomplete" and the unattempted packages, before the kept integration branch name; exactly one added source-map row pointing at `reviews/roundN.yaml` `triage_filing.unattempted_packages` / `triage_filing.failed_package` and citing review-phase.md; no receipt definition restated; gate_id count and level-2 headings unchanged; the existing batch-mode pins moved from seven to eight with no assertion deleted | Unit (document text) |

## Code Quality Verification
- Format: none (`format_command` is empty).
- Static analysis (component `plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .` — expected exit code 0.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A multi-line pip advisory (with CVSS vector) yields a title without line breaks that recovers and is filed or reported | TS-1 |
| AC2 | Round-trip test covers all four normalizers, multi-line text and titles truncated past 4096 bytes, and fails without the fix | TS-1; red-phase evidence in task0001's implementer report |
| AC3 | 3-package batch, 2nd create / update launch fails: exit 0, one JSON object, filed / appended = [1st], failed_package = 2nd, unattempted_packages = [2nd, 3rd], no traceback | TS-2, TS-3 |
| AC4 | Temporary-file write failure handled like AC3 | TS-4 |
| AC5 | Existing listing-launch-failure degraded behaviour unchanged | TS-7 |
| AC6 | Five fields in all three receipt places; existing pins kept | TS-8 |
| AC7 | No automatic retry; "triage filing incomplete" in R6 and the batch final result; completion condition unchanged; remainder-only re-run with its listing condition | TS-8, TS-15 |
| AC8 | unattempted_packages empty on full success and both report branches; all non-malformed packages on a first-package failure; never malformed findings | TS-5, TS-6 |
| AC9 | run_scan calls build_scan_jobs and consumes its plans; both test sides exercise that path; argv / env / cwd assertions live in build_scan_job and run_scan tests | TS-9 |
| AC10 | `python3 -m unittest discover -s tests` passes in full | Test Verification command above |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-1 |
| FR3 | task0002 | TS-2, TS-3, TS-4, TS-7 |
| FR4 | task0003 | TS-8 |
| FR5 | task0002, task0003 | TS-2, TS-3, TS-5, TS-6, TS-8, TS-15 |
| FR6 | task0004 | TS-9 |
| NFR1 | task0004 | TS-10 |
| NFR2 | task0002, task0003 | TS-11, TS-8, TS-15 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-13 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-14 |
| NFR5 | task0002 | TS-12 |
| NFR6 | task0003 | TS-8, TS-15 |

## Manual Testing (E2E Not Possible)
- [ ] TS-14: run a name-only diff from the implement base commit to HEAD in the integration worktree and confirm no `.claude-plugin/plugin.json` and no `.claude-plugin/marketplace.json` appears.
- [ ] Read review-phase.md's Phase R4 "Triage filing" subsection, the Phase R5 receipt (YAML and prose) and Phase R6 end to end, then `references/batch-mode.md`'s `## Reporting` and audit-item source map: the five fields, the unattempted-package rule and the "triage filing incomplete" report read consistently, and batch-mode.md points at the receipt without restating its definitions.

## Performance / Security Verification (if applicable)
- TM-1: whitespace collapse at the title-assembly point before truncation — checked by TS-1 (all four normalizers round-trip; no malformed finding).
- TM-2: OS errors in both filing helpers become the existing entry-point failure; one JSON object, exit 0 — checked by TS-2, TS-3, TS-4.
- TM-3: `unattempted_packages` on every branch plus the five receipt fields and the "triage filing incomplete" report in R6 and in the batch final report — checked by TS-5, TS-6, TS-8, TS-15.
- TM-4: fixed-token reasons, package names only in `unattempted_packages`, OS-error text on stderr only, receipt copies summary values only, batch final report sourced from the receipt only — checked by TS-11, TS-8 and TS-15.
- TM-5: run-side binding check kept before isolation and launch, against the plan's own target; no path verification for invalid or unresolved ecosystems — checked by TS-9 (symlink swapped after planning, test-double target) and TS-10.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-15) | 15 | 14 | 0 | 1 |
| Code quality (plugin invariants) | 1 | 1 | 0 | 0 |
| SPEC success criteria (AC1 to AC10) | 10 | 10 | 0 | 0 |
| Manual document read-through | 1 | 0 | 0 | 1 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
