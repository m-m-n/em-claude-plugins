# Verification Document: sca-file-tasks-unexpected-exceptions

## Overview
**Feature**: sca-file-tasks-unexpected-exceptions / **SPEC.md**: `feature-docs/sca-file-tasks-unexpected-exceptions/SPEC.md` / **IMPLEMENTATION.md**: not created (`reduced` tier; a single task, so no cross-task decision exists)

Scenario numbering: TS-1 to TS-8 below correspond one-to-one to the eight
scenarios of SPEC.md's Test Scenarios section, in the same order; TS-9 to
TS-12 are added here to give FR6 / NFR1 / NFR2 / NFR4 / NFR5 a dedicated
check. Mitigation IDs (TM-n) refer to THREAT-MODEL.md.

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) declare an empty build command; the changed script is interpreted Python.
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests` from the repository root
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .` from the repository root
- Expected: exit code 0 for both, no failures or errors.
- Coverage target: not measured (no coverage tool is configured and the project is standard-library only). Every scenario below whose test type is Unit or Integration has at least one test in `tests/test_sca_file_tasks_unexpected_exceptions.py`.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Real CLI as a subprocess, create path, empty listing, findings for pkg-a, a package name containing NUL (JSON-escaped in the findings file) and pkg-c, against the recording stand-in entry point | Exit code 0; no `Traceback` on stderr; stderr contains `task_create_failed`; stdout is exactly one JSON object equal to the twelve-key summary with `filed_packages` [pkg-a], `failed_package` the NUL name, `failure_reason` `task_create_failed`, `unattempted_packages` [NUL name, pkg-c], all other keys at their no-op values; the stand-in logged one create call (pkg-a) and never saw pkg-c | Integration |
| TS-2 | `file_tasks` in-process, append path, listing of three incomplete tasks where pkg-b's task id contains NUL | `appended_packages` [pkg-a], `failed_package` pkg-b, `failure_reason` `task_update_failed`, `unattempted_packages` [pkg-b, pkg-c]; the stand-in received an update for pkg-a's task only | Unit |
| TS-3 | `file_tasks` in-process with the temporary references-file writer replaced by a double raising UnicodeEncodeError on its second call, create path and append path | Same summary as the existing OSError write-failure case: `failed_package` pkg-b, `unattempted_packages` [pkg-b, pkg-c], `failure_reason` `task_create_failed` / `task_update_failed` per path, pkg-a completed | Unit |
| TS-4 | Both filing helpers called directly, with the writer and then the process launch made to raise ValueError, UnicodeEncodeError and TypeError in turn | ValueError and UnicodeEncodeError leave each helper as EntryPointError whose cause is that exact exception object (and the temporary file is gone after a failed launch); TypeError propagates as TypeError; non-zero exit and invalid entry point behave as before | Unit |
| TS-5 | The writer called directly with the reference line made of U+D800 followed by " (high)", recording the created temporary file's name | UnicodeEncodeError is raised (not EntryPointError) and the file does not exist afterwards; the existing OSError write-failure case still raises the raw OSError and leaves no file | Unit |
| TS-6 | Real CLI as a subprocess, three packages, the second finding's advisory id is the JSON-escaped U+D800 | Exit code 0; no `Traceback`; stdout is exactly one JSON object with no surrogate in it; `filed_packages` are the other two packages; `failed_package` / `failure_reason` null; `unattempted_packages` empty; `malformed_findings` equals [{position: 1, reason: the new fixed reason}] and that reason differs from the existing title-contract reason | Integration |
| TS-7 | `group_findings_by_package` called directly with a lone surrogate in the package, in the advisory id, and in a string severity (one case each); `file_tasks` with entry point None (temporary git repository as project root) and on the degraded report branch, each with a surrogate-bearing finding | Each offending finding is recorded as malformed with the new reason and grouped nowhere, others are grouped normally, nothing is raised; on both report branches the report file is written, the summary is returned and the finding appears in `malformed_findings` | Unit |
| TS-8 | Run both suite commands from the repository root | Both pass; `tests/test_sca_file_tasks_oserror.py` is unmodified in the diff from the base revision | Integration |
| TS-9 | Docstring checks in the new module: helpers and shared runner name ValueError alongside OSError; writer states removal on OSError or ValueError and the raw re-raise; grouping states the UTF-8 encodability skip; `file_tasks` names ValueError among mid-batch failures; NFR4 sentence constraints on the three helper / runner docstrings and the `file_tasks` "Five keys are ADDED" list | All assertions hold | Unit |
| TS-10 | Summary content discipline over the TS-1, TS-2, TS-3 and TS-6 runs | Exactly twelve keys; `failure_reason` null or one of the two tokens; neither `failure_reason` nor any `malformed_findings[].reason` contains the exception text, the package text or the advisory-id text; for TS-1 to TS-3 the exception text appears on stderr | Unit |
| TS-11 | Import discipline: an import scan of the new test module, plus a diff check of the script's imports against the base revision | Every module the new test module imports is a standard-library module; the diff adds no import to `em-workflow/scripts/scan-dependencies.py` | Unit + Manual |
| TS-12 | Version files untouched: list the files changed from the base revision | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the list | Manual |

## Code Quality Verification
- Format: none configured (empty format command for both components).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | FR1-FR6 rows below each have a passing scenario (TS-1 to TS-9) |
| SC-2 | All test scenarios pass | TS-1 to TS-12 all pass |
| SC-3 | NFR1-NFR5 are met | TS-10 (NFR1), TS-11 (NFR2), TS-8 (NFR3), TS-8 and TS-9 (NFR4), TS-12 (NFR5) |
| SC-4 | `tests/test_sca_file_tasks_oserror.py` passes unmodified | TS-8 (suite passes; the file is absent from the diff) |
| SC-5 | Code review is complete | The review phase finishes with no residual critical / high finding |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-5 |
| FR4 | task0001 | TS-6, TS-7 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-8, TS-9 |
| NFR1 | task0001 | TS-1, TS-6, TS-10 |
| NFR2 | task0001 | TS-11 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-8, TS-9 |
| NFR5 | task0001 | TS-12 |

## E2E Testing
Not applicable: the project has no E2E framework (both components declare an empty E2E command).

## Manual Testing (E2E Not Possible)
- [ ] FR6 wording review: the six docstrings describe the widened behaviour in prose a maintainer can follow, and the comment above the existing malformed reason constant no longer presents it as the only malformed reason.
- [ ] TS-11 diff half: the diff of `em-workflow/scripts/scan-dependencies.py` adds no import statement.
- [ ] TS-12: the changed-file list from the base revision contains neither plugin version file.

## Performance / Security Verification (if applicable)
- Performance: not applicable (SPEC.md states no performance goal).
- TM-1: grouping skips a finding whose package, advisory id or string severity is not UTF-8 encodable, records it with the new fixed reason, and processes the rest on every branch — checked by TS-6 (CLI, ntd branch, no surrogate on stdout) and TS-7 (direct grouping, report and degraded report branches).
- TM-2: both helpers convert OSError and ValueError (UnicodeEncodeError included) from the writer or the launch into EntryPointError with the cause kept, and the loop ends through break-and-return with one JSON summary and exit code 0 — checked by TS-1 (NUL package name through the real CLI), TS-3 (writer UnicodeEncodeError on both paths) and TS-4 (helper-level conversion and TypeError non-conversion).
- TM-3: a NUL in a listed task id ends the append path through break-and-return with `task_update_failed` — checked by TS-2 and TS-4 (append helper).
- TM-4: `failure_reason` stays one of the two tokens, the new malformed reason is a fixed constant, and exception / package / advisory text never reaches those fields — checked by TS-10, with TS-6 additionally checking the new reason differs from the title-contract reason.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 11 | 0 | 1 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 5 | 4 | 0 | 1 |
| Requirements coverage (FR / NFR) | 11 | 10 | 0 | 1 |
| Manual testing | 3 | 0 | 0 | 3 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
