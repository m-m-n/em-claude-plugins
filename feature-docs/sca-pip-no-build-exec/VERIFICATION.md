# Verification Document: sca-pip-no-build-exec

## Overview
**Feature**: sca-pip-no-build-exec / **SPEC.md**: `feature-docs/sca-pip-no-build-exec/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-pip-no-build-exec/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the plugin ships Python scripts that are not built)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (the tests use the standard library only and the project has no coverage tool)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `build_scan_job` for pip, given a prepared file, for `requirements.txt` and for `pyproject.toml` at the root and nested | argv is exactly the executable path, `-r`, the prepared file outside the project root, `--no-deps`, `--disable-pip`, `--format`, `json`. The cwd is the project root and no argv element names the reviewed project. Without a prepared file, job construction is refused | Unit |
| TS-2 | Extraction on requirements and pyproject fixtures, including an include, a `-c` file, editable / local / URL / VCS / marker / wildcard / `===` / range / extras lines and poetry values, plus grouping of one name at two versions | Only the allowed lines are returned, in canonical form with extras dropped. The excluded count matches. Out-of-root includes and `-c` files are never opened. Two versions of one name give two groups | Unit |
| TS-3 | `run_scan` with a recording pip-audit stub on fully pinned and mixed manifests | The recorded prepared-file content is exactly the validated pin lines and both flags are present. A mixed unit keeps its findings, carries `pip_manifest_entries_unpinnable` in `skip_reason`, and has `skipped` true | Integration |
| TS-4 | `run_scan` on a manifest with no auditable item | The stub is never started, and the pip reason is exactly `pip_manifest_unpinnable` | Integration |
| TS-5 | The existing lockfile suites: `tests/test_sca_pip_lockfile_audit.py` and the lockfile cases in the other modules | Pass with unchanged expectations, except where the source of the flags moved | Integration |
| TS-6 | Registry pins and validation cases through the restricted subset parser of `tests/test_sca_scan_invocation.py` | The pip entry declares `target_forms` with the `prepared_requirements` form and its literal flag and arguments. Invalid form tokens are rejected with `pip_target_forms_invalid`. The npm, cargo and go entries are byte-identical | Unit |
| TS-7 | Prepared-file cleanup after a normal completion and after an injected launch failure, with a project-tree snapshot | No prepared file remains in the test-owned temporary directory, and the project tree is byte-identical before and after | Integration |
| TS-8 | Untrusted-text fixtures with distinctive package names and paths | Neither `skip_reason` nor `summary` contains those names, those paths or the project root | Integration |
| TS-9 | Full suite run | `python3 -m unittest discover -s tests` exits 0 | Integration |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` (run from the repository root) exits 0
- Syntax: `python3 -m py_compile em-workflow/scripts/scan-dependencies.py` exits 0

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | pip job argv is the prepared-file form for `requirements.txt` and `pyproject.toml` (root and nested), with no reviewed-project path and no directory form | TS-1, TS-3 |
| AC-2 | The prepared file holds exactly the allowed `name==version` lines. Out-of-root includes are not opened and `-c` files are never opened | TS-2, TS-3 |
| AC-3 | A mixed input launches on the pins, keeps findings, and gives the excluded-items token and `skipped` true. No auditable item means no launch and only the no-item token | TS-3, TS-4 |
| AC-4 | Two versions of one name across a requirements file and its include give two prepared files and two launches | TS-2 (grouping), TS-3 (launches) |
| AC-5 | The lockfile route's argv, skip reasons and `pip_lockfile_entries_unpinnable` note are unchanged | TS-5 |
| AC-6 | The pip entry declares the per-form table, `build_scan_job` holds neither flag literally, invalid tokens are rejected with a fixed reason, and the other entries are byte-identical | TS-6, TS-1 |
| AC-7 | No prepared file remains and nothing under the project root is created or changed, on normal and exceptional exit | TS-7 |
| AC-8 | `skip_reason` and `summary` carry no fixture package name, path or project root | TS-8 |
| AC-9 | The full suite exits 0 | TS-9 |
| AC-10 | SPEC.md records the review-sca-axis FR1 replacement and the NFR2 application. It also records the npm / cargo / go results with follow-up task references. Nothing under `feature-docs/review-sca-axis/` changed | Manual (see Manual Testing) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-2, TS-3 |
| FR3 | task0001 | TS-3, TS-4 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-1, TS-6 |
| FR6 | task0001 | TS-3, TS-4 |
| FR7 | task0001 | TS-9 |
| FR8 | none (satisfied by SPEC.md) | Manual: AC-10 document check |
| FR9 | none (SPEC.md record and follow-up filing) | Manual: AC-10 document check |
| NFR1 | task0001 | TS-1, TS-2, TS-3 |
| NFR2 | task0001 | TS-7 |
| NFR3 | task0001 | TS-5, TS-9 |
| NFR4 | task0001 | TS-8 |
| NFR5 | task0001 | TS-3 (determinism case) |
| NFR6 | task0001 | TS-9 |

## E2E Testing
No E2E framework exists for this project (SPEC.md: none detected).

## Manual Testing (E2E Not Possible)
- [ ] AC-10 (FR8): SPEC.md's section on consistency with review-sca-axis states the replacement of the pip command form of review-sca-axis FR1, and how review-sca-axis NFR2 applies.
- [ ] AC-10 (FR9): SPEC.md's section on the other-ecosystem check records, for each of npm, cargo and go, whether the scan executes reviewed-project code. For go this includes package loading and toolchain switching. Each risk found has a follow-up task reference. No row reads "未記録".
- [ ] AC-10: the integration branch's diff against the base branch touches no file under `feature-docs/review-sca-axis/`.
- [ ] The registry header comment describes `target_forms` and no longer describes a pip top-level `args` / `target_flag`. The docstrings and comments of the pip job construction no longer describe the removed forms.
- [ ] Each existing test expectation changed by task0001 matches the SPEC rule it now encodes. None of them weakens an assertion of the lockfile route, the environment pins or `forbidden_tokens`.

## Performance / Security Verification (if applicable)
- TM-1: prepared-file-only launch with the form's flags; no reviewed file or directory is ever a pip-audit target — TS-1 argv and refusal cases, TS-3 recorded argv and file content
- TM-2: only canonical `name==version` lines that match the pin rule and pass `_pip_pin_is_valid` reach the prepared file — TS-2 extraction fixtures, TS-3 recorded file content
- TM-3: extraction opens only files confined to the project root and never opens `-c` files or URLs — TS-2 open-recorder assertions
- TM-4: extraction never raises for malformed, non-UTF-8, cyclic or unexpected input, and ends with a fixed outcome — TS-2 malformed-input cases
- TM-5: child environment pins, executable allowlist, absolute-path resolution and argv launch are unchanged — TS-5 and the unchanged environment-pin tests within TS-9
- TM-6: `skip_reason` and `summary` hold only fixed tokens and counts — TS-8
- TM-7: prepared files are owner-only, unpredictably named, removed on normal and exceptional exit, and the project tree is unchanged — TS-7

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Code quality | 2 | 2 | 0 | 0 |
| Success criteria (AC-1 to AC-10) | 10 | 9 | 0 | 1 |
| Functional requirements coverage | 15 | 13 | 0 | 2 |
| Manual checks | 5 | 0 | 0 | 5 |
| Security (TM-1 to TM-7) | 7 | 7 | 0 | 0 |
