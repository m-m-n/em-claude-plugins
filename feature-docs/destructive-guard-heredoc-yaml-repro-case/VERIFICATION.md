# Verification Document: destructive-guard-heredoc-yaml-repro-case

## Overview
**Feature**: destructive-guard-heredoc-yaml-repro-case / **SPEC.md**: `feature-docs/destructive-guard-heredoc-yaml-repro-case/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; one task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/destructive-guard-heredoc-yaml-repro-case/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty; the changed files are a Python hook script and a JSON case file, which are not built.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0. The runner's last line is `N/N passed`, with both numbers equal to the number of cases in `em-workflow/hooks/tests/destructive-guard-cases.json` plus one (the unattended-demotion check).
- Coverage target: not applicable. The expectation suite is case-based; every case must pass.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run the expectation suite and read the line of the FR1 allow case (the reported reproduction command: a quoted-delimiter heredoc that cat writes to `/tmp/example.yaml`, whose body quotes `git reset --hard` in backticks) | The runner prints an `ok` line with decision `allow` for the case (AC1 / FR1, FR2) | Integration (expectation suite) |
| TS-2 | Run the expectation suite and read the line of the FR3 deny case (the reproduction command followed by the line `git reset --hard HEAD~1`); then feed that command to `em-workflow/hooks/destructive-guard.py` directly as a Bash tool payload on standard input | The runner prints an `ok` line with decision `deny` for the case, and the guard's permission decision reason begins with `[destructive-guard/git-reset-hard]` (AC2 / FR3) | Integration (expectation suite + direct guard invocation) |
| TS-3 | Run `python3 em-workflow/hooks/tests/run-destructive-guard.py` over the whole suite, and compare the case file at `workflow.implement.base_commit` with the current one | Exit code 0 and `N/N passed`; every case of the base-commit file, including `["deny", "本物: git reset --hard", "git reset --hard HEAD~1"]` and the interpreter-fed heredoc deny cases, is present with the same decision, label and command; the current file has exactly two more cases (AC3, AC4 / FR4, NFR1) | Integration (expectation suite + file comparison) |

### Additional Verification Scenarios (planner-added; not in SPEC.md)
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-4 | Inspect the two cases added by this feature | Each label is a Japanese label in the style of the existing labels, and the two labels differ from each other and from every existing label; neither command contains `/home/`, `~` or `$HOME`, and the only path in them is `/tmp/example.yaml` (NFR2) | Inspection |
| TS-5 | List the files the feature's integration branch changes relative to `workflow.implement.base_commit` | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the list (NFR3) | Inspection (changed-file list) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty).
- Static analysis: none configured. The case file must parse as JSON; the runner loads it before judging any case, so a malformed file fails TS-3.
- When `em-workflow/hooks/destructive-guard.py` was changed, its diff is limited to what FR2 requires: the body of a heredoc whose delimiter is quoted and whose destination is cat redirecting to a file is not read as commands (see TM-2 below).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR4 are met and confirmed by tests | TS-1, TS-2, TS-3 pass |
| SC-2 | TS-1 to TS-3 all pass | Test Verification command exits 0, and the TS-2 reason check holds |
| SC-3 | NFR1 to NFR3 are met | TS-3 (NFR1), TS-4 (NFR2), TS-5 (NFR3) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1: runner `ok` for the allow case |
| FR2 | task0001 | TS-1: the in-tree guard returns `allow` for the reproduction command; when the guard was not changed, its file is byte-identical to the base commit |
| FR3 | task0001 | TS-2: runner `ok` for the deny case, reason tag `git-reset-hard` |
| FR4 | task0001 | TS-3: base-commit comparison of the case file and a full passing run |
| NFR1 | task0001 | TS-3: exit code 0, `N/N passed`, no `[TIMEOUT` marker |
| NFR2 | task0001 | TS-4: inspection of the new labels and commands |
| NFR3 | task0001 | TS-5: changed-file list excludes both version files |

## Manual Testing (E2E Not Possible)
- [ ] TS-4: judge that the two new labels follow the style of the existing Japanese labels (the path part of TS-4 is a mechanical check).

## Performance / Security Verification (if applicable)
- NFR1: every case finishes within the runner's 10-second limit — no runner line carries a `[TIMEOUT 10s]` marker.
- TM-1: lines after the heredoc terminator stay judged as commands — checked by TS-2: the FR3 case reports `ok` as `deny`, and the guard's reason for it begins with `[destructive-guard/git-reset-hard]`.
- TM-2: the heredoc-body exclusion does not reach interpreter-fed bodies or unquoted delimiters — checked by TS-3: every existing deny / ask case is unchanged and passes; when the guard was changed, its diff is also read to confirm the exclusion requires both a quoted delimiter and cat redirecting to a file.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios from SPEC.md (TS-1 to TS-3) | 3 | 3 | 0 | 0 |
| Additional scenarios (TS-4, TS-5) | 2 | 1 | 0 | 1 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 8 | 7 | 0 | 1 |
