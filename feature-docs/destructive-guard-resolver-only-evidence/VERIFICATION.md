# Verification Document: destructive-guard-resolver-only-evidence

## Overview
**Feature**: destructive-guard-resolver-only-evidence / **SPEC.md**: `feature-docs/destructive-guard-resolver-only-evidence/SPEC.md` / **IMPLEMENTATION.md**: not produced (tier reduced; a single task, so no file is shared between tasks) / **THREAT-MODEL.md**: `feature-docs/destructive-guard-resolver-only-evidence/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components` (`hooks`, `tests`) defines no build command.
- Expected: not applicable.

## Test Verification
- Command (hooks): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: every case passes, exit code 0.
- Command (tests): `python3 -m unittest discover -s tests`
- Expected: the set of failing and erroring test IDs equals the set at the base revision.
- Base comparison: run the unittest command on a checkout of the base revision (`workflow.implement.base_commit` in workflow.yaml) and on the integrated tree, collect the IDs reported as FAIL or ERROR in each run, and compare the two sets. The tests this feature adds pass, so they enter neither set.
- Coverage target: none set; no coverage command is configured.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `$(dirname /opt/rm) -rf /home/user/valuable` | allow | Integration (case table) |
| TS-2 | `$(ls -d /usr/bin/rm) -rf /home/user/valuable` | allow | Integration (case table) |
| TS-3 | `$(readlink -f ./rm) -rf /home/user/valuable` | allow | Integration (case table) |
| TS-4 | `$(basename /a/b git) clean -fd` | allow | Integration (case table) |
| TS-5 | `$(command -v rm) -rf /home/user/valuable` | deny, reason ID `rm-recursive` | Integration (case table) |
| TS-6 | `$(command -v git) reset --hard HEAD` | deny, reason ID `git-reset-hard` | Integration (case table) |
| TS-7 | `$(which ls rm) -rf /home/user/valuable` | allow | Integration (case table) |
| TS-8 | `$(rm) -rf /home/user/valuable` | allow | Integration (case table) |
| TS-9 | The existing `$(which ...)` cases and the existing `$(printf rm)` case of the case table | Same verdict and reason ID as at the base revision | Integration (case table, existing) |
| TS-10 | `$(true) rm -rf /home/user/valuable` (existing case) | deny through the plain route | Integration (case table, existing) |
| TS-11 | Both suites | `run-destructive-guard.py` passes every case; the failing-ID set of `unittest discover` equals the base revision's | Suite |
| TS-12 | `$(which -a rm) -rf /home/user/valuable` | deny, reason ID `rm-recursive` | Integration (case table) |
| TS-13 | `$(/usr/bin/which rm) -rf /home/user/valuable` | deny, reason ID `rm-recursive` | Integration (case table) |
| TS-14 | `$(command -v -- rm) -rf /home/user/valuable` | deny, reason ID `rm-recursive` | Integration (case table) |

## Code Quality Verification
- Format: none configured / Static analysis: none configured.
- Change-set check (NFR3, NFR4): the list of paths changed between the base revision and the integrated tree holds no `plugin.json`, no `.claude-plugin/marketplace.json` and no file named `failed-run-cleanup-guard.py`, and every listed path lies in the declared change set: the files of task0001, `feature-docs/destructive-guard-resolver-only-evidence/**` and `test-docs/destructive-guard-resolver-only-evidence/**`.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The four non-resolver forms (`dirname`, `ls -d`, `readlink -f`, `basename`) are allow | TS-1, TS-2, TS-3, TS-4 |
| AC-2 | The resolver forms are deny and the existing cases keep their verdict and reason ID | TS-5, TS-6, TS-12, TS-13, TS-14; TS-9 for the existing `$(which rm)`, backtick `which rm`, `$(which git) reset --hard HEAD` and `$(printf rm)` cases |
| AC-3 | The case table holds the FR5 cases | Read the added cases of `em-workflow/hooks/tests/destructive-guard-cases.json`; TS-1 to TS-8 and TS-12 to TS-14 run them |
| AC-4 | `run-destructive-guard.py` passes every case | TS-11 |
| AC-5 | The failing-ID set of `unittest discover -s tests` equals the base revision's | TS-11 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-5, TS-6, TS-9, TS-12, TS-13, TS-14; accepted-shape table in `tests/test_destructive_guard_resolver_evidence.py` |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-7, TS-8; unreadable-shape table in `tests/test_destructive_guard_resolver_evidence.py` |
| FR3 | task0001 | TS-9; TS-11 (lexer agreement continuation-line test and the FR3 rows of the new unit table) |
| FR4 | task0001 | TS-1 to TS-10, TS-12 to TS-14 |
| FR5 | task0001 | TS-1 to TS-8, TS-11 to TS-14 |
| FR6 | task0001 | TS-11 (docstring assertion of the new unit module, existing docstring pins); manual docstring review |
| FR7 | task0001 | TS-11 (lexer agreement test) |
| NFR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-7, TS-8: they expect allow, so an ask fails them |
| NFR2 | task0001 | Manual review of the added cases |
| NFR3 | task0001 | Change-set check |
| NFR4 | task0001 | Change-set check |

## Manual Testing (E2E Not Possible)
- [ ] Read the rewritten docstring of `read_command_name_evidence()` and confirm its steps match SPEC.md FR1 to FR3 (FR6).
- [ ] Read the added cases and confirm none asserts deny or ask for a body with separators, pipes or a quoted command name (NFR2).

## Performance / Security Verification
- NFR1: no fail-closed ask. The allow cases TS-1, TS-2, TS-3, TS-4, TS-7 and TS-8 expect allow, so an ask on an unreadable body fails them.
- TM-1: the reader accepts every FR1 shape, treats a run of spaces and tabs as one separator and drops leading and trailing whitespace, newlines included — checked by the deny cases TS-5, TS-6, TS-12, TS-13 and TS-14 with their reason IDs, the existing cases of TS-9, and the accepted-shape table of `tests/test_destructive_guard_resolver_evidence.py`.
- TM-2: continuation lines are removed as today before the newline check and the split — checked by `tests/test_destructive_guard_lexer_agreement.py` (`which r` + backslash-newline + `m` reads as `rm` and its command is denied), run under TS-11.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-14) | 14 | 14 | 0 | 0 |
| Success criteria (AC-1 to AC-5) | 5 | 5 | 0 | 0 |
| Requirements coverage (FR1 to FR7, NFR1 to NFR4) | 11 | 10 | 0 | 1 |
| Code quality (change-set check) | 1 | 1 | 0 | 0 |
| Security (NFR1, TM-1, TM-2) | 3 | 3 | 0 | 0 |
| Manual review (FR6 docstring, NFR2 cases) | 2 | 0 | 0 | 2 |
