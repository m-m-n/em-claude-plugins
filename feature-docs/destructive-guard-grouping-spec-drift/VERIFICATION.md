# Verification Document: destructive-guard-grouping-spec-drift

## Overview

**Feature**: destructive-guard-grouping-spec-drift / **SPEC.md**: `feature-docs/destructive-guard-grouping-spec-drift/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-grouping-spec-drift/IMPLEMENTATION.md`

This document covers the integrated verification run by the verify phase. Task-level acceptance criteria live in `tasks/task0001.md` to `tasks/task0003.md`.

## Build Verification

- Command: none. Both components in workflow.yaml `project.components` (`main`, `destructive-guard`) have an empty `build_command`.
- Expected: not applicable.

## Test Verification

- Command (component `destructive-guard`): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (component `main`): `python3 -m unittest discover -s tests`
- Expected: both exit 0.
- Coverage target: not measured (the project has no coverage tooling). Completeness is expressed as case coverage instead: every case listed in SPEC FR1, FR7 and FR8 is present in `em-workflow/hooks/tests/destructive-guard-cases.json` and passes.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Case-table run: `python3 em-workflow/hooks/tests/run-destructive-guard.py` on the integrated tree | Every case passes, including the trailing unattended-demotion case; exit 0. Covers the FR1, FR7 and FR8 rows, the FR9 relabelled row and every pre-existing row | Unit |
| TS-2 | Repository unit tests: `python3 -m unittest discover -s tests` | Pass, including the case-table invariants (no duplicate commands, pinned verdicts of the pre-task commands), the standard-library-only check, the forbidden-call list and the failed-run-cleanup-guard tests | Integration |
| TS-3 | Optional: `python3 em-workflow/hooks/tests/run-destructive-guard.py` given the installed cache copy of destructive-guard.py for the em-workflow version the feature ends at as its argument | Every case passes against the installed copy. Skipped (not a failure) when that cache directory does not exist yet | Unit (optional) |
| TS-4 | Prior-feature document consistency (SPEC Success Criteria AC-10) | In the prior feature's SPEC.md and REQUIREMENTS.md, FR2 (c) / (d), the Edge Cases mv line and FR6 match the implementation for mv, the six destination families and the head() / statements() input shaping | Manual |
| TS-5 | Version fields (SPEC Success Criteria AC-11) | The em-workflow `version` in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` carry the same value, with the patch position raised from the base commit's value and major / minor unchanged; the em-review version is unchanged from the base commit | Unit (file inspection) |

TS-1 to TS-3 are the SPEC's own scenarios. TS-4 and TS-5 are derived from SPEC Success Criteria AC-10 and AC-11, which no SPEC scenario covers. SPEC's TS-E2E is not applicable (see E2E Testing).

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured. The invariants that matter here (standard library only, no filesystem call or subprocess, no duplicate case command) run inside TS-2.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The case-table runner passes every case, including the trailing unattended-demotion case, and exits 0 | TS-1 |
| AC-2 | `python3 -m unittest discover -s tests` passes | TS-2 |
| AC-3 | With only the FR1 cases and the FR7 tar create / list allow cases added, the runner is red | Test records of task0001 and task0002 under `test-docs/destructive-guard-grouping-spec-drift/` show a red runner run before the code change (not re-executable on the integrated tree) |
| AC-4 | The five ticket reproductions are ask in the runner (deny with `CLAUDE_BATCH=1`) | TS-1 for the runner verdict; manual batch check below for deny |
| AC-5 | Through every construct, the rm recursive-delete, git, self-modification and transcript-write verdicts match the bare command | TS-1 (FR1 groups 2 to 6) |
| AC-6 | The fused-closer forms of cp are ask; `(rm -rf /tmp/x)>/dev/null` is allow | TS-1 |
| AC-7 | Every existing case keeps its command and expected verdict; only the FR9 mv label changes | TS-1, TS-2, and the manual case-table diff review below |
| AC-8 | tar `-C` is a write target only in extract mode; each of the six families has at least one ask and one allow case | TS-1, plus reading the FR7 block of the case table |
| AC-9 | `sudo -u` / `bash -c` / `eval`-routed rm cases exist and pass | TS-1 |
| AC-10 | The prior feature's SPEC.md and REQUIREMENTS.md match the implementation | TS-4 |
| AC-11 | Both em-workflow version fields carry the same value with the patch position raised from the base commit | TS-5 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 (FR1 rows present and passing); red run recorded in task0001's test record |
| FR2 | task0001 | TS-1 (FR1 groups 1 to 6) |
| FR3 | task0001 | TS-1 (fused-closer rows, pinned quoted-paren git row) |
| FR4 | task0001 | TS-1 (FR1 group 7 and all pre-existing rows) |
| FR5 | task0001 | TS-1 (payload and substitution rows, deferral rows), TS-2 (failed-run-cleanup-guard tests) |
| FR6 | task0002 | TS-1 (tar extract, create and list rows) |
| FR7 | task0002 | TS-1 (six-family rows); red run recorded in task0002's test record |
| FR8 | task0002 | TS-1 (seven rm pinning rows) |
| FR9 | task0002 | TS-1, TS-2 (relabelled row keeps command and verdict), manual case-table diff review |
| FR10 | task0003 | TS-4 |
| FR11 | task0003 | TS-4 |
| FR12 | task0001, task0002 | TS-5 (TS-3 optional) |
| NFR1 | task0001, task0002 | TS-2 (forbidden-call list) |
| NFR2 | task0001, task0002 | TS-2 (standard-library-only check) |
| NFR3 | task0001, task0002 | TS-1, TS-2, manual case-table diff review |
| NFR4 | task0001, task0002 | TS-2 (duplicate and pinned-verdict invariants) |
| NFR5 | task0001, task0002 | TS-1 (allow rows from FR1 group 7, FR4 pins and FR7) |
| NFR6 | task0001, task0002 | TS-1 (runner clears `CLAUDE_BATCH`; expected verdicts are runner verdicts) |

## E2E Testing

Not applicable: the project has no E2E infrastructure (SPEC TS-E2E).

## Manual Testing (E2E Not Possible)

- [ ] AC-4 batch variant: feed each of the five ticket reproduction commands to `em-workflow/hooks/destructive-guard.py` as a PreToolUse(Bash) hook input with `CLAUDE_BATCH=1` set in the environment; each verdict is deny.
- [ ] Case-table diff review (AC-7, NFR3): the integrated diff of `em-workflow/hooks/tests/destructive-guard-cases.json` against the base commit contains only added rows plus the single label change on the row `mv ~/.claude/hooks/x.py extra.txt /tmp/y`, whose command and expected verdict (ask) are unchanged.
- [ ] TS-4 (AC-10): read the prior feature's SPEC.md FR2, Edge Cases, FR6, architecture diagram, component diagram, Dependencies and Data Flow, and the eight listed places in its REQUIREMENTS.md; confirm each matches IMPLEMENTATION.md "Write-target sources" and "tar extract-mode rule" and the head() / statements() input-shaping facts, and that no statement fixes the sources at three or limits mv to its last argument.
- [ ] TS-3 (optional): after the plugin is reinstalled at the version the feature ends at, run the runner against the installed cache copy.
- [ ] `em-workflow/hooks/failed-run-cleanup-guard.py` has no diff against the base commit (FR5).

## Performance / Security Verification

- Bypass closed (security): FR1 groups 1 to 6 pass in TS-1, so wrapping a command in `( )`, `{ }`, if/elif/else, for, while/until, `!`, case or a function definition no longer skips the rm, git, self-modification or transcript-write checks.
- No new false positives (NFR5): every allow row (FR1 group 7, the FR4 pinned rows, the FR7 allow rows, all pre-existing allow rows) passes in TS-1.
- Performance: not applicable.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 5 (TS-1 to TS-5) | 3 (TS-1, TS-2, TS-5) | 0 | 2 (TS-3 optional, TS-4) |
| Success criteria | 11 (AC-1 to AC-11) | 9 | 0 | 2 (AC-3 via test records, AC-10) |
| Additional manual checks | 3 (batch variant, case-table diff, failed-run-cleanup-guard diff) | 0 | 0 | 3 |
