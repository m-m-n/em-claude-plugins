# Verification Document: destructive-guard write-target scoping

## Overview

**Feature**: destructive-guard-write-target-scoping /
**SPEC.md**: `feature-docs/destructive-guard-write-target-scoping/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-write-target-scoping/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature. Per-task
acceptance criteria live in the task plans and are not repeated here.

## Build Verification

- Command: none. Both components declared in workflow.yaml (`repo` and
  `hooks`) carry an empty `build_command` — this is an interpreted-language
  repository with no build step.
- Expected: not applicable; nothing is built.

## Test Verification

- Command (hooks component): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (repo component): `python3 -m unittest discover -s tests`
- Expected: exit code 0 from both, no failing case and no error output.
- Coverage target: no coverage tooling is configured for this repository, so
  no percentage target applies. The equivalent bar is case-level: every case
  in the expectation table, plus the trailing unattended-demotion case in the
  runner, must pass.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run the destructive-guard expectation suite over the full case table and the trailing unattended-demotion case | Exit code 0; every case matches its expected judgment, including the five newly added allow cases and every pre-existing ask / deny case | Unit |
| TS-2 | Run the repository-wide unit test suite | Exit code 0; no regression introduced by the hook rewrite or the manifest edits | Integration |
| TS-3 | Run the expectation suite against the installed plugin cache copy of the hook, after the version bump has been picked up (optional, environment-dependent) | Exit code 0, demonstrating the fix reached the installed copy | Integration |

## Code Quality Verification

- Format: none. Both components declare an empty `format_command`; no
  formatter is configured for this repository.
- Static analysis: none configured. In its place, the review phase inspects
  the hook diff for the completeness of the write-target extraction (see
  Security Verification below).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The expectation suite passes every case and exits 0 | TS-1 |
| AC-2 | The five false-positive cases exist with an allow expectation and are judged allow | TS-1, plus reading the five entries in the case table |
| AC-3 | With only the cases added and the fix not applied, the suite is red | Manual: the implement-phase test record for task0001 shows the red run and the five failing cases |
| AC-4 | The 34 pre-existing cases are neither deleted nor altered and all pass | Manual: the case-table diff is additions only; combined with TS-1 |
| AC-5 | Both transcript-read commands are allow, not deny | TS-1 (the two cases are in the table) |
| AC-6 | A transcript write stays deny; a settings write stays ask; a recursive skills removal stays ask | TS-1 (all three are pre-existing cases) |
| AC-7 | The trailing unattended-demotion case passes | TS-1 (the runner executes it after the table) |
| AC-8 | Both manifests carry the identical version 0.1.56 | Manual: parse both files and compare the two values |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1; the five entries are present in the case table with an allow expectation |
| FR2 | task0001 | TS-1, TS-2; the hook diff shows the judgment matching set members instead of the whole segment |
| FR3 | task0001 | TS-1; the cases whose only redirect target is the null device are allowed |
| FR4 | task0001 | TS-1; the read-source-only cases (settings read redirected to a temporary path, and a copy whose destination is outside the protected tree) are allowed |
| FR5 | task0001 | TS-1; every pre-existing ask / deny case plus the unattended-demotion case still passes |
| FR6 | task0001 | TS-1; the hook diff shows no change to the deletion judgment or its allowance rule |
| FR7 | task0002 | TS-2, TS-3; both manifest version values read 0.1.56 and are identical |
| NFR1 | task0001 | TS-1; judgments come from string analysis only, and re-running the suite yields identical results |
| NFR2 | task0001 | TS-1, TS-2; both suites run under a plain interpreter with no package installation, so a third-party import would fail the run; the hook's import list is inspected in review |
| NFR3 | task0001 | TS-1; combined with the additions-only case-table diff and the recorded red run |
| NFR4 | task0001 | TS-1; both directions are covered in one run — the five false positives now pass, and no previously-detected command was released |

## E2E Testing

No E2E framework exists in this repository and none is introduced by this
feature. No E2E scenario applies.

## Manual Testing (E2E Not Possible)

- [ ] The implement-phase test record for task0001 shows the suite red after
      the five cases were added and before the judgment was rewritten, with
      those five as the only failures (AC-3).
- [ ] The case-table diff contains additions only — no pre-existing entry was
      deleted, reordered in a way that alters an entry, or edited (AC-4).
- [ ] The hook diff leaves the deletion judgment and its allowance rule
      untouched (FR6).
- [ ] Both manifests are parsed and their version values compared: identical,
      and equal to 0.1.56; no other plugin's version moved (AC-8).
- [ ] Optional, environment-dependent: after the installed plugin cache has
      picked up the new version, the expectation suite is run against that
      copy of the hook (TS-3).

## Performance / Security Verification

- Detection floor (IMPLEMENTATION.md D3): no command that is ask or deny
  before the change becomes allow after it, other than the five newly added
  cases. Verified by the pre-existing cases all passing in TS-1.
- Extraction completeness: the write-target set is assembled from all three
  declared sources — output redirect targets, the target arguments of the
  in-place writer family and of the in-place stream editor, and the target
  arguments of the file-manipulating commands. Because an unmatched command is
  allowed outright and skips the auto-mode classifier, an omitted source is a
  detection gap; the review phase checks the three sources against the diff by
  hand.
- Static-analysis-only guarantee: the judgment path executes nothing and
  touches no filesystem object belonging to the inspected command (NFR1).
- Asymmetric cost (NFR4): a residual false positive ends an unattended run on
  the spot, and the transcript rule cannot be waved through by a human. Any
  newly discovered false positive is handled by adding its case first, per the
  project's hook-test rule.
- Performance: not applicable; no performance requirement exists for this
  feature.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 3 | 2 (TS-1, TS-2) | 0 | 1 (TS-3, optional) |
| Success criteria | 8 | 5 | 0 | 3 |
| Requirements | 11 | 11 | 0 | 3 also carry a manual check |
| Manual checks | 5 | — | — | 5 |
