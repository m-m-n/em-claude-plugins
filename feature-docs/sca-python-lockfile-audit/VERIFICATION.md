# Verification Document: sca-python-lockfile-audit

## Overview
**Feature**: sca-python-lockfile-audit / **SPEC.md**: `feature-docs/sca-python-lockfile-audit/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-python-lockfile-audit/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-python-lockfile-audit/THREAT-MODEL.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) declare an empty build command, and the change is Python scripts and tests.
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests` — expected exit code 0, no failures or errors.
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .` — expected exit code 0.
- Coverage target: no coverage tool is configured for this project. Minimum and target are both that every Acceptance Criterion of task0001 (AC-1 to AC-10) is exercised by at least one test.

### Test Scenarios from SPEC.md
TS1-TS10 come from SPEC.md. TS11-TS15 are added by this plan, marked "(plan)", for requirements SPEC.md gives no scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | A project in a temporary directory: poetry.lock pins a vulnerable version, and pyproject.toml declares a range that admits the fixed version. Only poetry.lock is changed. The stub pip-audit on PATH inspects the received `-r` file and returns a vulnerability for that pin. | At least one finding for the package. `skipped` false, `skip_reason` null. Finding `file` is poetry.lock's project-relative path, and its description carries the pinned version. | Integration |
| TS2 | Same as TS1 with Pipfile.lock (pins in `default` and `develop`) and a Pipfile declaring the package under `[packages]`. | Finding present, `skipped` false, finding `file` is Pipfile.lock. The prepared file holds the pins of both groups. | Integration |
| TS3 | Argument vector of the lockfile-derived job. The test at `tests/test_sca_scan_invocation.py` lines 243-248 is replaced, and the forbidden-token check at lines 258-264 is narrowed to non-lockfile jobs. | The lockfile job is exactly [pip-audit, `-r`, prepared file, `--no-deps`, `--disable-pip`, `--format`, `json`]. `--no-deps` / `--disable-pip` appear only on lockfile jobs, never on requirements.txt / pyproject.toml jobs. With [pyproject.toml, poetry.lock] changed, exactly one lockfile job runs. | Unit |
| TS4 | Selected lockfile is an invalid-TOML poetry.lock, an invalid-JSON Pipfile.lock, a poetry.lock without a package array, or a lockfile whose entries are all git. | Each yields `skipped` true with `pip_lockfile_unconvertible`. The stub records no invocation. | Integration |
| TS5 | Selected lockfile has no sibling declaration file, or a broken one. | `skipped` true with `pip_direct_manifest_not_found`. The stub records no invocation. | Integration |
| TS6 | Lockfile with git / path entries and an entry named like `-r evil`. | The summary carries the `pip_lockfile_entries_unpinnable` count note and `skipped` is false. The prepared file recorded by the stub holds only lines that pass FR11. | Integration |
| TS7 | Lockfile pinning one name at two versions. | The stub is launched twice, and each prepared file contains the name once. Findings for both versions are in one result. Two scans of the same input are byte-identical. | Integration |
| TS8 | Declaration says `Django`; the lockfile and pip-audit output say `django`. | Treated as a direct dependency; a finding is reported. | Integration |
| TS9 | A git-initialized project, scanned with a lockfile change. | `git status --porcelain` is identical before and after, and no prepared file remains in the temporary location. | Integration |
| TS10 | Existing pins in `tests/test_sca_scan_normalization.py` lines 187-192 and 295-312 (pip manifests and args). | Pass with that file unmodified. | Unit |
| TS11 | (plan) In one scan, the pip lockfile is unconvertible, cargo's tool is absent, and npm completes. | `skip_reason` is `cargo_tool_not_found+pip_lockfile_unconvertible`, and npm's findings are kept. | Integration |
| TS12 | (plan) A lockfile job is built from a prepared path that does not exist. A lockfile manifest is given without a prepared path. | The first job is built with no file read or written and no process launched. The second call is rejected and the directory form is never produced. | Unit |
| TS13 | (plan) Invariants: the registry pip entry, `ALLOWED_EXECUTABLES`, `ECOSYSTEM_LOCKFILES`, the pip child-environment pins, and the script's imports. | All equal their pre-change values. The script imports nothing outside the standard library beyond its existing optional YAML import. | Unit |
| TS14 | (plan) Test-module imports and both suites. | New and changed test modules import only the standard library. Both Test Verification commands exit 0. | Suite |
| TS15 | (plan) Plugin version files. | `git diff --name-only` between `workflow.implement.base_commit` and HEAD lists no path under a `.claude-plugin/` directory. | Command check |

## Code Quality Verification
- Format: none configured (empty `format_command` in both components).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | FR1-FR12 and NFR1-NFR7 are satisfied | Functional Requirements Coverage below |
| SC2 | AC1-AC11 are satisfied | AC1 to TS1, AC2 to TS2, AC3 to TS3, AC4 to TS3 and TS10, AC5 to TS4, AC6 to TS5, AC7 to TS6, AC8 to TS7, AC9 to TS8, AC10 to TS9, AC11 to TS14 |
| SC3 | TS1-TS10 pass | Test Verification commands |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS3 |
| FR2 | task0001 | TS1, TS2 |
| FR3 | task0001 | TS1, TS3, TS10 |
| FR4 | task0001 | TS7 |
| FR5 | task0001 | TS4 |
| FR6 | task0001 | TS6 |
| FR7 | task0001 | TS2 |
| FR8 | task0001 | TS5 |
| FR9 | task0001 | TS8 |
| FR10 | task0001 | TS1 |
| FR11 | task0001 | TS6 |
| FR12 | task0001 | TS11 |
| NFR1 | task0001 | TS9 |
| NFR2 | task0001 | TS12 |
| NFR3 | task0001 | TS7 |
| NFR4 | task0001 | TS13 |
| NFR5 | task0001 | TS14 |
| NFR6 | task0001 | TS13 |
| NFR7 | task0001 | TS15 |

## Manual Testing (E2E Not Possible)
- [ ] When a real pip-audit and network access are available, run `scan` against a sample project. Its poetry.lock pins a version with a published advisory, and its pyproject.toml declares that package. Confirm that pip-audit accepts the lockfile argument vector (pip is not reported as `pip_undocumented_exit_status`, `pip_unparseable_output` or `pip_empty_output`) and that the finding is reported. The automated tests use only a stub (NFR5), so this is the only check against the real tool.

## Performance / Security Verification
- TM-1: only FR11-valid `name==version` lines reach the prepared file, and every other entry is excluded and counted. Checked by TS6: the stub records the prepared file's content. No line begins with `-`, contains whitespace, `;` or `#`, or carries an excluded name.
- TM-2: no fallback for an unconvertible or partially convertible lockfile. Checked by TS4 (fixed reason, no stub invocation) and TS6 (count note with `skipped` false).
- TM-3: the lockfile and the declaration file are read only when they resolve inside the project root. Checked by the task0001 tests for AC-5 and AC-7: a lockfile symlinked outside the root gives `pip_lockfile_unconvertible`, and a declaration file symlinked outside the root gives `pip_direct_manifest_not_found`. The stub records no invocation in either case.
- TM-4: no exception leaves the scan on malformed content. Checked by the task0001 tests for AC-5 and AC-7 (wrong value types, non-UTF-8 bytes, nesting beyond the parser's limit, broken declaration file), plus TS4, TS5 and TS11 (completed ecosystems' findings kept).
- TM-5: every lockfile job carries `--no-deps` and `--disable-pip`. Checked by TS3 and by the argument vectors the stub records in TS1 and TS7.
- TM-6: prepared files are owner-only, outside the project root, and removed on every exit path. Checked by TS9 and by the task0001 tests for AC-9 (recorded permission bits, exception-path cleanup).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS15) | 15 | 15 | 0 | 0 |
| Security mitigations (TM-1 to TM-6) | 6 | 6 | 0 | 0 |
| Suite commands | 2 | 2 | 0 | 0 |
| Real-tool check | 1 | 0 | 0 | 1 |
