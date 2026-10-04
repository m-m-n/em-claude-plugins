# Verification Document: sca-scanner-project-config-isolation

## Overview
**Feature**: sca-scanner-project-config-isolation / **SPEC.md**: `feature-docs/sca-scanner-project-config-isolation/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-scanner-project-config-isolation/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-scanner-project-config-isolation/THREAT-MODEL.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) declare an empty `build_command`.
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both. No real npm or cargo-audit is required (NFR4).
- Coverage target: no coverage tool is configured. Coverage is judged by the scenario-to-requirement mapping below.

### Test Scenarios from SPEC.md
SPEC.md scenario TS1–TS9 corresponds to TS-1 to TS-9 here. TS-10 to TS-13 are derived from FR5, FR3, FR11 / FR13 and NFR4.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | npm, with an adversarial `.npmrc` (`https-proxy`, `strict-ssl=false`, `registry`, `cafile`) at the project root, scanned through run_scan with an offline recording stub (SPEC TS1) | The stub's cwd real path is outside the real project root. There is no `.npmrc` in the cwd or any ancestor. argv is `[<npm>, audit, --json, --workspaces=false]`. The copies of `package.json` and the anchor match the originals. The unit is completed with the label `package.json`. | Unit (stub) |
| TS-2 | npm, with both `npm-shrinkwrap.json` and `package-lock.json` present (SPEC TS2) | `npm-shrinkwrap.json` is copied as the anchor | Unit (stub) |
| TS-3 | cargo, with an adversarial `.cargo/audit.toml` (`[advisories] ignore`, `[database] url/path`) (SPEC TS3) | The cwd is outside the real project root and there is no `.cargo/audit.toml` in the cwd or any ancestor. argv is `[<cargo-audit>, audit, --file, <copy inside cwd>, --json]`, with no `--url` / `--db`. The copy matches `Cargo.lock`. Direct dependencies are judged from the original `Cargo.toml`. | Unit (stub) |
| TS-4 | npm and cargo, with several groups whose inputs differ (SPEC TS4) | Each invocation's inputs match its own group's originals, and each group gets a distinct isolation directory. Processing order and findings file labels are unchanged. | Unit (stub) |
| TS-5 | The temp parent is redirected into the reviewed tree through `TMPDIR`, `TEMP`, `TMP`, `tempfile.tempdir` or a symlink (SPEC TS5) | `<ecosystem>_isolation_failed`. The scanner is not launched, and nothing is created or changed under the real project root. | Unit (stub) |
| TS-6 | A copy fails for one group in a multi-group run (SPEC TS6) | The failing group is not launched and gets `<ecosystem>_isolation_failed`. The other groups are scanned and their findings remain. `skip_reason` and summary contain no path string. | Unit (stub) |
| TS-7 | Runs ending in success, tool failure, timeout, and a copy failure part-way through (SPEC TS7) | No isolation directory remains after any of them. The stub-recorded cwd permission bits grant nothing to group or other. | Unit (stub) |
| TS-8 | build_scan_job called with a prepared path while file opening and process creation are forbidden by mocks (SPEC TS8) | The call succeeds for npm and for cargo | Unit |
| TS-9 | pip and go jobs, ECOSYSTEM_ENV_PINS, and HOME in child environments (SPEC TS9) | The pip / go argv, cwd and env equal the pre-change values. ECOSYSTEM_ENV_PINS equals the pre-change snapshot. Every child receives the runner's HOME unchanged. No new pin appears in the npm / cargo child environments. | Unit (stub) |
| TS-10 | A copy source that is an allowed same-directory symlink (FR5) | The isolation directory holds a regular file whose content equals the link target | Unit (stub) |
| TS-11 | The cargo entry in `vuln-scanners.yaml` (FR3) | The entry declares the `--file` target flag, and job assembly places `--file <copy>` immediately after `audit` | Unit |
| TS-12 | Documentation for the new execution location (FR11, FR13) | The axis-2 text in `review-phase.md` and the docstrings / comments in `scan-dependencies.py` and `vuln-scanners.yaml` describe isolation-directory execution, `--file`, both isolation tokens and the trusted configuration scope. None of them still says that npm / cargo run with the project root as cwd. | Unit (token presence) + Inspection |
| TS-13 | The full suite runs offline without npm or cargo-audit installed (NFR4) | `python3 -m unittest discover -s tests` exits 0, and the result is the same on every run | Suite |

## Code Quality Verification
- Format: none configured (empty `format_command`)
- Static analysis: none configured. Plugin structural invariants are checked by `python3 em-workflow/scripts/check-plugin-invariants.py .`.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every row has at least one task and at least one scenario, and every scenario passes |
| SC-2 | All test scenarios pass | TS-1 to TS-13 pass under the Test Verification commands |
| SC-3 | Security requirements are satisfied | Every item in Performance / Security Verification passes |
| SC-4 | Documentation is complete (FR13) | TS-12 |
| SC-5 | Code review is completed | The review phase finishes with no residual critical / high findings |
| SC-6 | `python3 -m unittest discover -s tests` passes (SPEC AC11) | TS-13 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-3 |
| FR3 | task0001 | TS-3, TS-11 |
| FR4 | task0001 | TS-8 |
| FR5 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-10 |
| FR6 | task0001 | TS-5 |
| FR7 | task0001 | TS-5, TS-6 |
| FR8 | task0001 | TS-7 |
| FR9 | task0001 | TS-1, TS-3, TS-4 |
| FR10 | task0001, task0002 | TS-9 |
| FR11 | task0001, task0002 | TS-9, TS-12 |
| FR12 | task0001 | TS-1, TS-3 |
| FR13 | task0001, task0002 | TS-12 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001, task0002 | TS-13 |

## Manual Testing (E2E Not Possible)
- [ ] TS-12 (inspection part): read the axis-2 section of `em-workflow/references/review-phase.md`, the comments and docstrings named in FR13 in `em-workflow/scripts/scan-dependencies.py`, and the cargo entry comment in `em-workflow/references/vuln-scanners.yaml`. Confirm that they agree with the IMPLEMENTATION.md Shared Components contracts and that no statement still says npm / cargo run with the project root as cwd.

The SPEC.md reproduction steps are covered by the stub scenarios above (SPEC.md Assumption A2). No manual run with a real npm or cargo-audit is part of this verification.

## Performance / Security Verification
- NFR2: nothing is created or changed under the real project root — before/after tree snapshot in TS-5, plus the stub-recorded cwd outside the root in TS-1 and TS-3
- NFR3: `skip_reason` and summary contain no path string — TS-6
- TM-1: npm runs from an isolation directory with no project `.npmrc` on its cwd or ancestor path — checked by TS-1 (stub-recorded cwd real path and ancestor scan)
- TM-2: cargo-audit runs from an isolation directory with `--file` pointing at the copy, with no `--url` / `--db` and no project `.cargo/audit.toml` on its cwd or ancestor path — checked by TS-3
- TM-3: copy sources are re-validated with the binding check's rule and copied as regular-file content — checked by TS-10, with the content comparison in TS-1 and TS-3
- TM-4: real-path containment checks on the temp parent before creation and on the isolation directory after creation — checked by TS-5 (all five redirection forms)
- TM-5: an isolation failure gives `not_completed` with the isolation token and no in-tree fallback launch — checked by TS-5 and TS-6 (the stub is never invoked for the failing unit)
- TM-6: one group's isolation failure does not stop the other groups, and their findings remain — checked by TS-6
- TM-7: one uniquely named, owner-only directory per group — checked by TS-4 (distinct directories) and TS-7 (permission bits)
- TM-8: owner-only access and removal on every outcome — checked by TS-7
- TM-9: fixed tokens only in `skip_reason` / summary — checked by TS-6

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 13 | 13 | 0 | 1 (TS-12 inspection part) |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria | 6 | 4 | 0 | 2 (SC-4 inspection part, SC-5 review phase) |
| Security (NFR2, NFR3, TM-1 to TM-9) | 11 | 11 | 0 | 0 |
