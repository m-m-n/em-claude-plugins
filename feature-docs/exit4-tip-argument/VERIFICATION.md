# Verification Document: exit4-tip-argument

## Overview

**Feature**: exit4-tip-argument
**SPEC.md**: `feature-docs/exit4-tip-argument/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/exit4-tip-argument/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the whole feature, run
after every task has merged. Per-task completion is governed by each task
plan's own Acceptance Criteria.

Test scenario IDs below (`TS1` … `TS9`) are hyphen-less, matching SPEC.md's
numbering and the `tests` arrays already recorded in workflow.yaml
`requirements`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the
  changed artifacts are Markdown prose, JSON registries and Python test
  modules, none of which has a build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root)
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: not measured. The project has no coverage tooling and the
  test suite is contract-style (assertions over documents and registries),
  so the meaningful target is "every FR with an automated scenario has a
  passing scenario", tracked in the coverage table below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Existing, unmodified: `tests/test_rework_synthesis_contract.py::test_completed_at_commit_wording_is_unchanged` | Passes — Step I.3's pinned completion sentence still matches byte-for-byte after the insertion | Unit (pre-existing) |
| TS2 | Existing, unmodified: `tests/test_rework_synthesis_contract.py::test_regression_precondition_stated_before_launch_selection` | Passes — the pending-task precondition still precedes Step I.2.a's launch-selection wording | Unit (pre-existing) |
| TS3 | New: Step I.2.a's text contains the refresh, the tip capture into a named variable, the `tasks.{T}.status` / `tasks.{T}.branch` write and a `commit-docs.sh` invocation whose third argument is that variable, in that order | Passes; the matcher's negative proof fails against the captured pre-change sample | Unit (new) |
| TS4 | New: Step I.3's text contains the same four elements in the same order, and the pinned completion sentence is present byte-for-byte in the raw document text | Passes; negative proof and non-vacuity guard both hold | Unit (new) |
| TS5 | New: the fresh-capture-on-every-entry statement (including the refill re-entry) is present, and `RECONCILE_TIP` occurs inside Step I.2.a only in the not-reused context — never as a `commit-docs.sh` third argument | Passes; negative proof holds | Unit (new) |
| TS6 | Manual/review: read the exit-4 recovery bullet's six-site enumeration against the per-step text | One-to-one correspondence for all six sites; Step I.2.c's route-back is the only carve-out | Manual |
| TS7 | New: both version registries parse as JSON, report the same version string, and that version is on the `0.1.x` line with patch strictly greater than 44; the `em-review` entry is untouched | Passes; the baseline and equality matchers each fail against their forged samples | Unit (new) |
| TS8 | Manual/verify: inspect the feature diff for out-of-scope files | `em-workflow/scripts/commit-docs.sh` is absent; every pre-existing `tests/*.py` is absent; the only `tests/` entries are the two new modules | Manual |
| TS9 | Manual/review: read the six call sites' wording side by side | All six use the same shape, the same variable-capture idiom and the same exit-4 cross-reference phrasing — one mechanism, not per-step variants | Manual |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; there is
  no formatter configured for Markdown, JSON or the test modules.
- Static analysis: none configured.
- Convention check (part of review): the new test modules use only the
  Python standard library, live in the repository-root `tests/` directory,
  and follow the `test_<target>.py` / `Test<Behavior>` /
  `test_<condition>_<expected_result>` naming in `test/README.md`.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Step I.2.a states the refresh, capture, write, commit-with-tip sequence in order | TS3 |
| AC2 | Step I.3 states the same four elements in the same order | TS4 |
| AC3 | The pinned Step I.3 sentence is byte-identical and `tests/test_rework_synthesis_contract.py` is unchanged in the diff | TS1 + TS4 (byte identity) + TS8 (diff inspection) |
| AC4 | The document states a fresh tip is captured on every entry including the refill re-entry, and `$RECONCILE_TIP` is not reused | TS5 |
| AC5 | `$RECONCILE_TIP` never appears in Step I.2.a as the value passed to `commit-docs.sh` | TS5 |
| AC6 | Every enumerated call site has a three-argument `commit-docs.sh` invocation in its own step's text | TS3 + TS4 (the two added sites) and TS6 (the full one-to-one read) |
| AC7 | `python3 -m unittest discover -s tests` exits 0 | Run the test command from the repository root after all tasks merge |
| AC8 | `em-workflow/scripts/commit-docs.sh` is absent from the diff | TS8 |
| AC9 | Both registries carry the same new patch-bumped version | TS7 |
| AC10 | `test_regression_precondition_stated_before_launch_selection` still passes | TS2 |
| — | Code review is completed | Review phase result recorded in workflow.yaml |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS3, TS4, TS6 |
| FR2 | task0001 | TS2, TS3 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS1, TS4, TS8 |
| FR5 | task0001 | TS5 |
| FR6 | task0002 | TS7 |
| NFR1 | task0001 | TS9 |
| NFR2 | task0001 | TS8 |
| NFR3 | task0001, task0002 | TS1, TS2, TS8, plus the full-suite run (AC7) |
| NFR4 | task0001 | TS6 |

## E2E Testing

Not applicable. `project.components.main.e2e_test_command` is empty and the
project has no E2E surface — the change is protocol prose plus a version
bump.

## Manual Testing (E2E Not Possible)

- [ ] TS6: read the Branch & Worktree Model's exit-4 recovery bullet and
      check each of the six names it enumerates against that step's own
      text; confirm each has a three-argument `commit-docs.sh` invocation and
      that Step I.2.c's route-back remains the only documented carve-out.
- [ ] TS8: inspect the integrated diff and confirm the changed-file set is
      contained in the declared change set — in particular that
      `em-workflow/scripts/commit-docs.sh` and every pre-existing
      `tests/*.py` (notably `tests/test_rework_synthesis_contract.py`) are
      absent from it.
- [ ] TS9: read Step I.1, Step I.2.a, Step I.2.b, both Step I.2.c terminal
      commits and Step I.3 in sequence and confirm the six call sites read as
      one mechanism: same four-part shape, same `{NAME}_TIP` capture idiom,
      same exit-4 cross-reference phrasing.
- [ ] Read Step I.2.b step 5's refill path into Step I.2.a as a reader would
      and confirm it is impossible to conclude that the already-captured
      `$RECONCILE_TIP` may be reused.

## Performance / Security Verification

Not applicable. The feature introduces no runtime surface, no dependency, no
input handling, no persisted data and no authentication or authorization
path. SPEC.md records every security category as not applicable.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 9 (TS1-TS9) | 6 (TS1-TS5, TS7) | 0 | 3 (TS6, TS8, TS9) |
| Success criteria | 10 (AC1-AC10) + review | 7 (AC1, AC2, AC4, AC5, AC7, AC9, AC10) | 0 | 3 (AC3 partly, AC6 partly, AC8) |
| Requirements | 10 (FR1-FR6, NFR1-NFR4) | 8 | 0 | 2 (NFR1, NFR4 — review reads) |
