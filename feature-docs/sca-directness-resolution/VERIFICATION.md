# Verification Document: sca-directness-resolution

## Overview
**Feature**: sca-directness-resolution / **SPEC.md**: `feature-docs/sca-directness-resolution/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-directness-resolution/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-directness-resolution/THREAT-MODEL.md`

## Build Verification
- Command: none configured (`build_command` is empty for both `repo-tests` and `plugin-invariants` in workflow.yaml).
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit 0.
- Coverage target: not measured (no coverage tooling in the project, and NFR1 forbids adding one); every task Acceptance Criterion maps to at least one test.

### Test Scenarios from SPEC.md
TS-1 to TS-16 are SPEC.md TS1 to TS16 in order; TS-17 onward are derived from the FR / NFR text.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Cargo canonical matching: Cargo.toml declares Foo_Bar; payload without is_direct reports foo-bar at severity high | Exactly one finding | Unit (task0001) |
| TS-2 | Cargo sub-table: dependencies.serde sub-table with version '1' | serde advisory is a finding | Unit (task0001) |
| TS-3 | Cargo rename: alias = { package = 'real-name', version = '1' } | real-name advisory is a finding; alias is not matched | Unit (task0001) |
| TS-4 | Cargo target table: foo = '1' under target.'cfg(unix)'.dependencies | foo advisory is a finding | Unit (task0001) |
| TS-5 | Cargo workspace with members, advisory for an undeclared crate | No finding; cargo_directness_undetermined note with count 1 | Unit (task0001) |
| TS-6 | Cargo.toml that is invalid TOML | Advisory counted as cargo_directness_undetermined | Unit (task0001) |
| TS-7 | pyproject single quotes and extras: requests[socks]>=2 and django==3.2.0 | requests and django are both direct | Unit (task0002) |
| TS-8 | pyproject dynamic dependencies | Set incomplete (task0002); an incomplete pyproject set is counted as pip_directness_undetermined (task0003, stand-in resolver) | Unit (task0002, task0003) |
| TS-9 | requirements -r include, simple and nested; forms -rX, --requirement X, --requirement=X | Included names are direct | Unit (task0003) |
| TS-10 | Include pointing outside the root, or a symlink to outside | File not read; advisory counted as undetermined | Unit (task0003) |
| TS-11 | requirements include cycle | Walk terminates; names of both files are direct | Unit (task0003) |
| TS-12 | requirements -c constraints.txt | Not followed; not counted as undetermined | Unit (task0003) |
| TS-13 | Line holding only a URL or a local path | Set incomplete; advisory for an unlisted package counted | Unit (task0003) |
| TS-14 | Complete set with an undeclared package | Stays transitive; no undetermined note | Unit (task0001, task0003) |
| TS-15 | tomllib binding replaced by None | pyproject and Cargo units report their toml_parser_unavailable token and the scanner is not started; the requirements.txt unit completes | Unit (task0001, task0002) |
| TS-16 | Note order and wording | Undetermined notes follow the pip severity, unpinnable and go notes, pip before cargo; no package names or paths | Unit (task0001, task0003) |
| TS-17 | Cargo payload entry carrying is_direct (FR1) | Directness follows is_direct, also under an incomplete set; never undetermined | Unit (task0001) |
| TS-18 | Cargo workspace = true entry renamed in workspace.dependencies (FR2) | The renamed package is direct | Unit (task0001) |
| TS-19 | Poetry tables and non-declaration tables (FR3) | Poetry keys except python are direct; optional-dependencies, dependency-groups and Poetry group tables are not | Unit (task0002) |
| TS-20 | pyproject with neither a static project dependencies list nor Poetry tables (FR5) | Set incomplete (task0002); counted as pip_directness_undetermined (task0003, stand-in resolver) | Unit (task0002, task0003) |
| TS-21 | Backslash line continuation in requirements files (FR4) | A continued include or requirement is read as one line | Unit (task0003) |
| TS-22 | Missing include target; URL include (FR4, FR5, NFR2) | Not read and not fetched; set incomplete; advisory counted | Unit (task0003) |
| TS-23 | Counting edges under an incomplete set (FR5) | Known below-threshold severity dropped uncounted; unknown severity counted once and not in the unknown-severity note | Unit (task0001, task0003) |
| TS-24 | tomllib absent and the pip lockfile tokens (FR6) | pip_direct_manifest_not_found and pip_lockfile_unconvertible behave as before; requirements-derived units never report pip_toml_parser_unavailable | Unit (task0002) |
| TS-25 | Unexpected TOML shapes and unreadable manifests (NFR3) | Scan returns normally; set incomplete | Unit (task0001, task0002, task0003) |
| TS-26 | Full suite (AC8, NFR5) | python3 -m unittest discover -s tests exits 0; pre-existing npm and go tests unmodified | Integration (suite) |
| TS-27 | Plugin version fields untouched (NFR6) | No difference in em-workflow/.claude-plugin/plugin.json or .claude-plugin/marketplace.json between workflow.implement.base_commit and the integration head | Command (git diff) |
| TS-28 | Standard library only (NFR1) | scan-dependencies.py and the new test modules import only standard-library modules; tomllib only through the existing guarded import | Inspection |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Cargo name differing from the cargo-audit report only by case and separators yields a high / critical finding | TS-1 |
| AC2 | dependencies.serde sub-table yields a serde finding; package = rename yields a real-name finding | TS-2, TS-3 |
| AC3 | Single-quoted dependencies with extras: requests and django both direct | TS-7 |
| AC4 | requirements.txt with only -r requirements/base.txt: base.txt names direct | TS-9 |
| AC5 | Each FR5 incomplete case yields the matching undetermined note with the right count, skipped stays false | TS-5, TS-6, TS-8, TS-10, TS-13, TS-20, TS-22 |
| AC6 | Without tomllib, pyproject and Cargo units report their toml_parser_unavailable token and do not start the scanner | TS-15 |
| AC7 | Out-of-root includes (.., absolute, symlink) not read; include cycles terminate | TS-10, TS-11 |
| AC8 | python3 -m unittest discover -s tests passes | TS-26 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-17 |
| FR2 | task0001 | TS-2, TS-3, TS-4, TS-18 |
| FR3 | task0002 | TS-7, TS-19 |
| FR4 | task0003 | TS-9, TS-10, TS-11, TS-12, TS-21, TS-22 |
| FR5 | task0001, task0002, task0003 | TS-5, TS-6, TS-8, TS-10, TS-13, TS-14, TS-16, TS-20, TS-22, TS-23 |
| FR6 | task0001, task0002 | TS-15, TS-24 |
| FR7 | task0001, task0002, task0003 | TS-1, TS-2, TS-3, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-11, TS-13, TS-15, TS-26 |
| NFR1 | task0001, task0002, task0003 | TS-28 |
| NFR2 | task0003 | TS-10, TS-22 |
| NFR3 | task0001, task0002, task0003 | TS-6, TS-8, TS-25 |
| NFR4 | task0001, task0002, task0003 | TS-15, TS-16 |
| NFR5 | task0001, task0003 | TS-26 |
| NFR6 | task0001, task0002, task0003 | TS-27 |

## Manual Testing (E2E Not Possible)
- [ ] TS-28: read the import list of `em-workflow/scripts/scan-dependencies.py` and of the three new test modules and confirm every module is part of the Python standard library.

## Performance / Security Verification (if applicable)
- TM-1: includes are confined to the project root — TS-10 asserts that `..`, absolute-path and symlink includes leading outside the root are never opened and that their names never appear.
- TM-2: URL includes are never fetched — TS-22 asserts that a URL include causes no network attempt and marks the set incomplete.
- TM-3: include cycles terminate — TS-11 asserts that mutually including files finish with both files' names direct.
- TM-4: no exception escapes the scan — TS-6, TS-25 and TS-22 assert that invalid TOML, unexpected shapes, missing and unreadable files return normally with an incomplete set.
- TM-5: unresolvable declarations are surfaced, not dropped as transitive — TS-5, TS-8, TS-10, TS-13, TS-20 and TS-22 assert the undetermined count and note under an incomplete set, and TS-14 that a complete set keeps transitive behavior.
- TM-6: notes and skip reasons carry only fixed tokens and counts — TS-15 and TS-16 assert the exact token / note text and the absence of package names and paths.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-28) | 28 | 27 | 0 | 1 |
| Plugin invariants | 1 | 1 | 0 | 0 |
| Success criteria (AC1 to AC8) | 8 | 8 | 0 | 0 |
| Security mitigations (TM-1 to TM-6) | 6 | 6 | 0 | 0 |
