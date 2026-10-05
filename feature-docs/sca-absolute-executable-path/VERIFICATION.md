# Verification Document: sca-absolute-executable-path

## Overview
**Feature**: sca-absolute-executable-path / **SPEC.md**: `feature-docs/sca-absolute-executable-path/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-absolute-executable-path/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-absolute-executable-path/THREAT-MODEL.md`

## Build Verification
- Command: none. The `build_command` of both components (`repo-tests`, `plugin-invariants`) is empty, because Python scripts are not built.
- Expected: not applicable

## Test Verification
- Command (component `repo-tests`): `python3 -m unittest discover -s tests`
- Command (component `plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both
- Focused modules: `python3 -m unittest tests.test_sca_absolute_executable_resolution`, `python3 -m unittest tests.test_sca_child_env_path_filtering`, `python3 -m unittest tests.test_sca_scan_unchanged_surfaces`
- Coverage target: no coverage tool is configured. Every SPEC success criterion and every task Acceptance Criterion maps to at least one scenario below.

### Test Scenarios from SPEC.md
TS-1 to TS-9 are SPEC.md's TS1 to TS9 under the same numbers. TS-10 to TS-14 cover the SPEC requirements that have no SPEC scenario (FR5, NFR1, NFR2, NFR3 / AC7, NFR4).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1, AC1) Temporary directory holding a relative-entry directory and an absolute stub directory, process cwd where the relative entry resolves, PATH `tools` + separator + the absolute stub directory; resolve `npm` | Returns the stub's absolute path | Unit |
| TS-2 | (SPEC TS2, AC2) PATH made only of relative / empty entries (`tools`, `./node_modules/.bin`, `.`, empty, `~/bin`), with an executable under each | Resolution returns none; `build_scan_jobs` returns `["npm_tool_not_found"]` and 0 plans | Unit |
| TS-3 | (SPEC TS3, AC3, AC4) Recording-stub harness with `services/api/package.json`, `services/api/package-lock.json`, a marker-writing `services/api/tools/npm` and `<cwd>/tools/npm`, PATH `tools` + separator + the stub directory; run `run_scan` | Recorded argv[0] is the stub's absolute path; neither `tools/npm` marker exists | Integration |
| TS-4 | (SPEC TS4, AC4) `run_scan` for a nested go project (cwd `<root>/services/api`), a root go project, pip (cwd root), npm and cargo (cwd the isolation directory) | Every recorded argv[0] is absolute and equals the value of `resolve_executable` | Integration |
| TS-5 | (SPEC TS5, AC5) `build_child_env` with a mixed PATH | Only the absolute entries remain, in their original order and unmodified | Unit |
| TS-6 | (SPEC TS6, AC5) `build_child_env` with a PATH of only relative / empty entries, with an empty-string PATH, and with an environ that has no PATH | The result has no PATH key | Unit |
| TS-7 | (SPEC TS7, AC5) `run_scan` with a runner PATH that holds relative / empty entries around the absolute stub directory | Every recorded child environment's PATH holds no relative or empty entry | Integration |
| TS-8 | (SPEC TS8, AC6) `build_child_env` with every pass-through key and the pinned variables set (absolute PATH); existing `test_ac2` with its fixture PATH made absolute | Result equals pass-through keys + pins | Unit |
| TS-9 | (SPEC TS9, AC1) PATH unset; the default search path substituted with a mix of relative / empty entries and an absolute stub directory | Resolution returns the stub's absolute path | Unit |
| TS-10 | (FR5) Inspect the `resolve_executable` docstring, the Scan job construction section comment, the `build_scan_jobs` docstring, the comment above `CHILD_ENV_BASE_KEYS` and the `build_child_env` docstring | Each describes the FR1 / FR4 behavior; nothing says PATH is carried through unchanged or that resolution is a plain PATH lookup | Inspection |
| TS-11 | (NFR1, AC7) Static import check of `em-workflow/scripts/scan-dependencies.py`; `build_child_env` called while file opening, filesystem inspection and process launching are made to fail | Only standard-library imports; `build_child_env` returns the same result | Unit |
| TS-12 | (NFR2, NFR3) Read the diff from the implement step's `base_commit` to HEAD | No change to `em-workflow/references/vuln-scanners.yaml` or `em-workflow/references/review-phase.md`; the `scan-dependencies.py` hunks touch none of `ALLOWED_EXECUTABLES`, `ECOSYSTEM_ENV_PINS`, `ECOSYSTEM_LOCKFILES`, the `CHILD_ENV_BASE_KEYS` key list or the skip-reason tokens; the only change to an existing test file is the `test_ac2` fixture PATH value | Inspection |
| TS-13 | (NFR3, AC7) Run `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` | Both exit 0 | Command |
| TS-14 | (NFR4) Diff `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` from the implement step's `base_commit` to HEAD | Empty diff | Command |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | With relative and absolute entries mixed in PATH and an executable of the same name under both, `resolve_executable` returns the absolute-entry side's absolute path | TS-1, TS-9 |
| AC2 | With the executable only under relative / empty entries, `resolve_executable` returns none, and `build_scan_jobs` gives `<ecosystem>_tool_not_found` once and no plan | TS-2 |
| AC3 | In the attack scenario, neither `services/api/tools/npm` nor `<cwd>/tools/npm` is launched | TS-3 |
| AC4 | For nested-cwd jobs (nested go, npm / cargo isolation) and root-cwd jobs (pip, root go), argv[0] is absolute and equals `resolve_executable`'s value | TS-3, TS-4 |
| AC5 | The child PATH keeps only absolute entries; no PATH key when only relative / empty entries exist or PATH is absent | TS-5, TS-6, TS-7 |
| AC6 | Pass-through keys other than PATH and the per-ecosystem pins reach the child unchanged | TS-8 |
| AC7 | `python3 -m unittest discover -s tests` passes | TS-11, TS-13 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-9 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3, TS-4 |
| FR4 | task0002 | TS-5, TS-6, TS-7, TS-8 |
| FR5 | task0001, task0002 | TS-10 |
| NFR1 | task0001, task0002 | TS-11 |
| NFR2 | task0001, task0002 | TS-8, TS-12 |
| NFR3 | task0001, task0002 | TS-12, TS-13 |
| NFR4 | task0001, task0002 | TS-14 |

## Manual Testing (E2E Not Possible)
- [ ] TS-10: read the five comment / docstring locations and confirm that they describe absolute-only resolution and the absolute-only child PATH
- [ ] TS-12: read the diff from the implement step's `base_commit` and confirm the unchanged surfaces (NFR2) and the single existing-test change (NFR3)

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md Performance Tests: 該当なし)
- TM-1: resolution searches only absolute entries and returns an absolute path or none, and every job's argv[0] is that path — checked by TS-3 (in the attack scenario, neither planted `tools/npm` is launched and argv[0] is the stub's absolute path), with TS-1, TS-2, TS-4 and TS-9 covering the resolution and argv[0] cases
- TM-2: the child PATH keeps only absolute entries, and there is no PATH key when none remain — checked by TS-7 (no recorded child PATH holds a relative or empty entry), with TS-5 and TS-6 covering the `build_child_env` cases

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-14) | 14 | 12 | 0 | 2 |
| SPEC success criteria (AC1 to AC7) | 7 | 7 | 0 | 0 |
| Security mitigations (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Mockup comparison (design step skipped) | 0 | 0 | 0 | 0 |
