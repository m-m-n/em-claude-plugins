# Verification Document: sca-per-project-scan-binding

## Overview
**Feature**: sca-per-project-scan-binding / **SPEC.md**: `feature-docs/sca-per-project-scan-binding/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-per-project-scan-binding/IMPLEMENTATION.md`

This document covers the integrated verification run by the verify phase.
Task-level acceptance criteria live in `tasks/task0001.md` to `tasks/task0003.md`.

## Build Verification
- Command: none — both components (`repo-tests`, `plugin-invariants`) declare an empty `build_command` (Python, no build step).
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both, no failures or errors.
- Coverage target: no coverage tool is configured; every task Acceptance Criterion maps to at least one test (see each task plan's Test Notes).

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC-1, AC-15 / FR1, FR2, FR3, FR4) services/api holds package.json and package-lock.json; changed_files is [services/api/package.json]; a cwd-recording npm stub is on PATH | npm launched once; recorded cwd is the real path of project_root/services/api; the finding's file is services/api/package.json; skipped is false | Integration |
| TS-2 | (AC-2, AC-15 / FR1, FR3) services/api and services/web are both bindable and both package.json files change | npm launched twice, services/api first; each cwd is its own directory; each project's findings carry its own package.json path | Integration |
| TS-3 | (AC-3, AC-5, AC-6 / FR4, FR6, NFR3) a project missing its anchor for each of npm (also yarn.lock only), cargo and go (go.sum-only change without go.mod), at the root and nested; plus a go.sum-only change with go.mod present | no launch and skip_reason exactly `<ecosystem>_project_unbindable` for each anchorless case, with no directory name in skip_reason or summary; the go.mod case launches go in that directory | Integration |
| TS-4 | (AC-4, AC-9 / FR7, FR8, NFR2, NFR3, NFR5) bindable and unbindable npm projects mixed; two unbindable npm projects; changed_files reversed | skipped true, skip_reason exactly npm_project_unbindable (once), bindable findings kept, summary's scanned list names npm once, no directory name in skip_reason or summary, result conforms to review-output-schema.json, skip_reason identical under reversal | Integration |
| TS-5 | (AC-7 / FR5, FR6) anchor or manifest symlinked into another directory (inside and outside the root), npm-shrinkwrap.json symlinked elsewhere beside a valid package-lock.json, absolute path, `..`-escaping path, NUL-containing path, deleted selected target, absent project directory | no launch for that project, `<ecosystem>_project_unbindable`, no launch at the root or an ancestor; a separate valid npm project in the same run is still launched in its own directory | Integration |
| TS-6 | (AC-8 / FR1) a/package.json, a/./package-lock.json and a repeated a/package.json | one group, one launch, finding labelled a/package.json | Integration |
| TS-7 | (AC-10, AC-13 / FR11, FR12) build_scan_job argv / env and the purity of build_scan_job and build_scan_jobs | npm argv ends with audit, --json, --workspaces=false; go env holds GOWORK=off and GOFLAGS=-mod=readonly over caller values; with file opening and process launching patched to fail, both functions complete without calling them | Unit |
| TS-8 | (AC-11 / FR10) pip changes in two directories (requirements.txt project; poetry.lock + pyproject.toml project) | pip audited once per group with lockfile-first selection; every pip launch's cwd is project_root; existing pip lockfile tests pass | Integration |
| TS-9 | (AC-12 / FR7, FR9) npm executable absent; two npm groups, one anchorless | skip_reason exactly npm_tool_not_found; nothing launched; no project-level reason added | Integration |
| TS-10 | (AC-5 / NFR1) git repository holding a cargo project without Cargo.lock; a cargo-audit stub that would write Cargo.lock if launched | git status --porcelain identical before and after the scan; no Cargo.lock created | Integration |
| TS-11 | (AC-14 / FR13) review-phase.md Phase R2 | the appended multi-project partial-coverage passage is present after the existing paragraph; the existing paragraph and all pinned phrases are present verbatim | Unit (document) |
| TS-12 | (AC-16 / FR14, NFR4) full suite including the updated fixtures (manifest + anchor) | `python3 -m unittest discover -s tests` exits 0; the new test modules import only standard-library modules | Integration (suite) |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured.
- Append-only documentation (FR13): `git diff` of `em-workflow/references/review-phase.md` between the feature's base commit (`workflow.implement.base_commit`) and the integration HEAD contains no removed line.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; both test commands exit 0 |
| SC-2 | All test scenarios pass | TS-1 to TS-12 pass in the suite run |
| SC-3 | Security requirements are satisfied | TM-1 to TM-5 items below |
| SC-4 | Documentation is complete (FR13) | TS-11 and the append-only diff check |
| SC-5 | Code review is completed | review phase completed with no unresolved critical / high finding |
| SC-6 | The reproduction steps no longer reproduce the defect (AC-15) | TS-1 and TS-2 pass |
| SC-7 | A test detects a recurrence (AC-15) | TS-1 and TS-2 exist in the suite and fail against the pre-feature run_scan |
| SC-8 | The em-workflow version is not changed by hand (A-13) | the feature diff against the base commit touches neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-2, TS-6 |
| FR2 | task0001, task0002 | TS-1 |
| FR3 | task0001, task0002 | TS-1, TS-2 |
| FR4 | task0002 | TS-1, TS-3 |
| FR5 | task0002 | TS-5 |
| FR6 | task0002 | TS-3, TS-5 |
| FR7 | task0002 | TS-4, TS-9 |
| FR8 | task0002 | TS-4 |
| FR9 | task0002 | TS-9 |
| FR10 | task0002 | TS-8 |
| FR11 | task0001 | TS-7 |
| FR12 | task0001, task0002 | TS-7 |
| FR13 | task0003 | TS-11 |
| FR14 | task0001, task0002 | TS-12 |
| NFR1 | task0001, task0002 | TS-10 |
| NFR2 | task0001, task0002 | TS-4 |
| NFR3 | task0002 | TS-3, TS-4 |
| NFR4 | task0001, task0002, task0003 | TS-12 |
| NFR5 | task0002 | TS-4 |

## E2E Testing
None — the project has no E2E framework (SPEC.md: Existing E2E tests: None).

## Manual Testing (E2E Not Possible)
None — every scenario is automated with scanner stubs on a temporary PATH (NFR4).

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md: Performance Tests 該当なし).
- TM-1: real-path containment of changed files, project directory, anchor and manifest; no fallback; build_scan_job rejects absolute / escaping npm / cargo / go targets — checked by TS-5 (no launch recorded for the project or at the root, exact `<ecosystem>_project_unbindable`) and task0002 AC-1's rejection test.
- TM-2: one scan unit per verified project with cwd and label from the same group; incomplete groups make the result skipped while completed findings stay — checked by TS-1 and TS-2 (recorded cwd and label per project) and TS-4 (skipped true with the bindable project's findings kept).
- TM-3: npm `--workspaces=false` and go `GOWORK=off` — checked by TS-7 (argv element present; env value holds over a caller-supplied GOWORK).
- TM-4: launch only with an existing anchor lockfile, go `GOFLAGS=-mod=readonly` — checked by TS-7 (env value) and TS-10 (tree unchanged, no Cargo.lock created).
- TM-5: skip_reason and the summary's reason list built only from fixed tokens — checked by TS-3 and TS-4 (no fixture directory name appears in skip_reason or summary; skip_reason is an exact token string).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 12 | 0 | 0 |
| Code quality (append-only diff) | 1 | 1 | 0 | 0 |
| Success criteria (SC-1 to SC-8) | 8 | 7 | 0 | 1 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
