# Verification Document: sca-cargo-implicit-workspace-members

## Overview
**Feature**: sca-cargo-implicit-workspace-members / **SPEC.md**: `feature-docs/sca-cargo-implicit-workspace-members/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, single task — no cross-task decisions) / **THREAT-MODEL.md**: `feature-docs/sca-cargo-implicit-workspace-members/THREAT-MODEL.md`

Scenario IDs use the hyphenated form. TS-1 to TS-7 correspond one-to-one, in
order, to SPEC.md's seven Test Scenarios; TS-8 (THREAT-MODEL.md mitigations)
and TS-9 (change-set constraints) are added by the plan.

## Build Verification
- Command: none (both components are Python with an empty `build_command` in workflow.yaml)
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both
- Coverage target: no coverage tool is configured; every task0001 Acceptance Criterion maps to at least one test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Root `[workspace]` without `members` and `member = { path = "member" }`; `member/Cargo.toml` declares a crate; the cargo-audit stand-in reports a high-severity advisory for it (SPEC AC1) | No finding; `skipped` false; `skip_reason` None; summary ends with the cargo undetermined note with count 1; the member manifest's declaration has no effect | Integration (scan harness) |
| TS-2 | `members = []` with a path dependency (SPEC AC2) | Same as TS-1 | Integration (scan harness) |
| TS-3 | Path entry in `dev-dependencies`, `build-dependencies`, `target.'cfg(unix)'.dependencies`, and the `[dependencies.member]` sub-table (SPEC AC3) | Each case: no finding; note with count 1 | Integration (scan harness) |
| TS-4 | `[workspace.dependencies]` path entry inherited through `workspace = true`, plain and with a `package` rename (SPEC AC4) | Undeclared advisory counted once; the renamed name's advisory is a finding | Integration (scan harness) |
| TS-5 | Path-dependency workspace with a root-declared `serde` advisory, and with an undeclared advisory of determined below-threshold severity (SPEC AC5) | `serde` advisory is a finding with no note; below-threshold advisory is neither a finding nor counted | Integration (scan harness) |
| TS-6 | `members` omitted or empty with no path-bearing root entry; an unreferenced `[workspace.dependencies]` path entry only; a `[package]` manifest without `[workspace]` with a path dependency (SPEC AC6) | Undeclared advisory stays transitive; no note; the two existing workspace-complete tests pass unchanged | Integration (scan harness) |
| TS-7 | Full test suite (SPEC AC7) | `python3 -m unittest discover -s tests` exits 0; no pre-existing test method changed | Integration (suite) |
| TS-8 | Hostile path entries: a path value pointing outside the project at a Cargo.toml declaring the crate; a non-string `path` on a root entry; a non-string `path` on an inherited `[workspace.dependencies]` entry (THREAT-MODEL.md TM-2, TM-3, TM-4) | Scan returns normally; the direct-name resolution returns an incomplete set without raising; the advisory is counted once and is not a finding; summary and skip_reason contain no path value, dependency key or manifest path | Integration (scan harness) + Unit |
| TS-9 | Change-set check against the base branch | No edit to `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, or `feature-docs/sca-directness-resolution/**`; source changes limited to `em-workflow/scripts/scan-dependencies.py` and `tests/` | Static (git diff) |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR5 are implemented and tested | TS-1 to TS-6 pass |
| SC-2 | SPEC.md's seven Test Scenarios pass | TS-1 to TS-7 pass |
| SC-3 | Existing tests pass unchanged (NFR5) | TS-7 passes; the diff of `tests/test_scan_dependencies_cargo_directness.py` adds lines only |
| SC-4 | Plugin version is not edited (NFR6) | TS-9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3 |
| FR2 | task0001 | TS-4 |
| FR3 | task0001 | TS-6 |
| FR4 | task0001 | TS-1, TS-2, TS-5 |
| FR5 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-6 (the regression tests themselves) |
| NFR1 | task0001 | TS-7 (existing standard-library-only import test) |
| NFR2 | task0001 | TS-1, TS-8 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-8 |
| NFR5 | task0001 | TS-6, TS-7 |
| NFR6 | task0001 | TS-9 |

## Manual Testing (E2E Not Possible)
- None. SPEC.md declares no E2E tests, and the goal's reproduction steps are automated as TS-1.

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md).
- TM-1: a `[workspace]` manifest with a path-bearing root entry marks the cargo direct set incomplete — checked by TS-1, TS-2, TS-3 and TS-4 (the undeclared advisory is counted in the cargo undetermined note, never silently dropped) and TS-6 (workspaces without a path-bearing root entry, and manifests without `[workspace]`, stay complete).
- TM-2: path values are never resolved or opened — checked by TS-1 (the member manifest's declaration has no effect) and TS-8 (a Cargo.toml outside the project has no effect), plus a diff review confirming no new file-open path in `em-workflow/scripts/scan-dependencies.py`.
- TM-3: summary and skip_reason carry only the fixed token and count — checked by TS-8 (a distinctive path value, dependency key and the manifest path are absent from both).
- TM-4: unexpected shapes never raise out of the scan — checked by TS-8 (non-string `path` values on a root entry and on an inherited entry; the scan and the direct-name resolution return normally).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Plugin invariants | 1 | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 4 | 4 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
