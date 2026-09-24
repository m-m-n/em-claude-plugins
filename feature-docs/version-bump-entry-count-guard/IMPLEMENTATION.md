# Implementation Plan: version-bump-entry-count-guard

## Overview

Remove the marketplace entry-count guard and the whole-array name/source
snapshot from `tests/test_recycled_task_id_contract_version_bump.py`,
consolidate task0002's AC-3 verification into the em-workflow entry
name/source check, and align `test-docs/recycled-task-id-contract/task0002.tests.yaml`.
The feature is delivered as a single task (task0001).

## Technology Stack

- **Language**: Python 3 (existing repository test suite)
- **Test framework**: unittest (standard library), run from the repository
  root with `python3 -m unittest discover -s tests`
- **Libraries**: standard library only — unittest / json / re / pathlib (NFR2)
- **New dependencies**: none. `project.license` is `none`; there is no new
  dependency whose license needs recording.

## Layer Structure

Not applicable. The change is confined to one test module and one test
record document; no plugin or production code is touched.

## Shared Components

None. This is a single-task feature. The em-workflow entry check that
task0001 introduces is local to the test module and has no consumer in any
other task; its contract lives in `tasks/task0001.md`.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| — | — | — | — |

## Conventions

- **Change set (NFR1)**: the only feature-specific files changed are
  `tests/test_recycled_task_id_contract_version_bump.py` and
  `test-docs/recycled-task-id-contract/task0002.tests.yaml`. A need to touch
  any other file is reported as a plan deviation, never absorbed silently.
- **Protected paths (NFR3)**: nothing under `em-workflow/` and not
  `.claude-plugin/marketplace.json` is modified; no plugin version is
  bumped. Both changed files sit outside every plugin directory, so the
  repository's plugin version-bump rule does not apply.
- **Imports and JSON (NFR2)**: test code imports only unittest / json / re /
  pathlib. marketplace.json is always read by JSON parsing, never by
  pattern matching over its text.
- **In-test data (FR5)**: the pass/fail demonstrations use marketplace data
  built inside the test. No repository file (marketplace.json included) and
  no temporary copy of one is written to exercise a failure.
- **Removed identifiers stay removed**: `MARKETPLACE_NAME_SOURCE_BASELINE`,
  `TestMarketplaceOtherFieldsUnchanged`, `test_entry_count_unchanged` and
  `test_every_entry_name_and_source_matches_baseline` do not reappear
  anywhere in either changed file — including comments and docstrings that
  would refer back to them. Verification finds them by text search.

## Cross-task Design Decisions

### D1: Single task

The two files are coupled by test identifiers: the AC-3 record in
task0002.tests.yaml must name tests that exist in the module. Both changes
go into task0001 so the record and the module change together.

### D2: One check, used by the retained test and the in-test cases

The retained test `test_em_workflow_entry_name_and_source_unchanged` and the
FR5 in-test cases exercise the same module-local check. In-test cases that
call a separate copy of the logic would not demonstrate anything about the
retained test (FR2, FR5). Affected task: task0001.

### D3: Scope boundary (SPEC A-1)

The entry-count guards in the other version-bump modules
(`tests/test_batch_policy_option_id_version_bump.py`,
`tests/test_goal_vs_spec_divergence_version_bump.py`,
`tests/test_rework_contract_drift_version_bump.py`) are not changed. Adding
a third plugin still fails those modules after this feature.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Another test module references or imports the removed constant or class, so removing them breaks the suite | Low | Medium | Full-suite run (TS-5) plus a text search of `tests/`; a hit outside the two files is reported as a plan deviation (NFR1) |
| Moving the retained test's assertions into the shared check silently loosens them (FR2) | Low | High | task0001 requires every em-workflow assertion of the retained test to survive; TS-2 / TS-3 prove the check still fails on source and name drift |
| The rewritten AC-3 red_reason states run observations that the original record does not contain | Low | Low | task0001 limits the rewrite to removing the entry-count and whole-array mentions |
| A third plugin addition still fails the three out-of-scope modules | High | Medium | Out of scope (SPEC Out of Scope); a separate task |

## Open Questions

- None.
