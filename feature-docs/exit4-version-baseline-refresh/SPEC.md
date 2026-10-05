# Feature: exit4-version-baseline-refresh

## Overview

`tests/test_exit4_tip_argument_version_bump.py` compares the em-workflow
version in both registries against a fixed pre-bump baseline. This feature
refreshes that baseline to the real pre-bump value at exit4-tip-argument's
diff base (`0.1.68`, patch 68), aligns the module's text and the per-task
test record with it, and adds a test that ties the baseline constant to the
forged pre-bump sample.

## Objectives

- Make `tests/test_exit4_tip_argument_version_bump.py` actually guard the
  exit4-tip-argument version bump: the module goes red on a tree whose
  em-workflow registries read the real pre-bump value at that feature's
  diff base (`0.1.68`).
- Add a test that detects when the module's baseline constant and its
  forged pre-bump sample drift apart again.

## Acceptance Criteria

- [ ] **AC-1** (FR1): `BASELINE_PATCH` in
  `tests/test_exit4_tip_argument_version_bump.py` equals `68`.
- [ ] **AC-2** (FR2): `FORGED_PRE_BUMP_VERSION` equals `"0.1.68"`.
  `test_baseline_matcher_rejects_forged_pre_bump_version` and
  `test_forged_pre_bump_version_is_well_formed` pass.
- [ ] **AC-3** (FR4): The new tie test exists in
  `TestValidationDetectsRegressions` and passes. It fails when
  `BASELINE_PATCH` and `FORGED_PRE_BUMP_VERSION`'s patch differ, which is
  shown by observing it red before both constants agree.
- [ ] **AC-4** (FR3): No docstring or comment in the module presents `44` or
  `0.1.44` as the baseline.
- [ ] **AC-5** (FR5): The AC-1, AC-2 and AC-3 `red_reason` values in
  `test-docs/exit4-tip-argument/task0002.tests.yaml` name the new baseline
  and quote the re-observed failure. No other field of that file changes.
- [ ] **AC-6** (NFR1, NFR2, NFR3, NFR4, NFR5):
  `python3 -m unittest discover -s tests` exits 0. The diff contains only
  `tests/test_exit4_tip_argument_version_bump.py`,
  `test-docs/exit4-tip-argument/task0002.tests.yaml` and this feature's own
  `feature-docs` / `test-docs` entries. The module's imports are standard
  library only.

## Technical Requirements

### Functional Requirements

- **FR1 - Baseline constant refresh:** In
  `tests/test_exit4_tip_argument_version_bump.py`, `BASELINE_PATCH` is `68`.
  This is the em-workflow patch level both registries carried at
  exit4-tip-argument's diff base `02aff93`.
- **FR2 - Forged pre-bump sample refresh:**
  `TestValidationDetectsRegressions.FORGED_PRE_BUMP_VERSION` is `"0.1.68"`.
  The existing negative proof
  (`test_baseline_matcher_rejects_forged_pre_bump_version`) and its
  non-vacuity guard (`test_forged_pre_bump_version_is_well_formed`) run
  against that value unchanged in structure.
- **FR3 - Module text alignment:** Every docstring and comment in the module
  that states the old baseline is rewritten to the new one:
  - line 2: `strictly greater than 44`
  - line 9: `patch strictly greater than 44`
  - line 18: `patch > 44`
  - lines 27-29: `raising the baseline patch to 44 ... un-bumped `0.1.44` tree`
  - line 56 comment: `both registries read 0.1.44`

  No text in the module still presents `44` or `0.1.44` as the baseline.
- **FR4 - Baseline/sample tie test:** A new test in
  `TestValidationDetectsRegressions` asserts that `FORGED_PRE_BUMP_VERSION`
  parses as `X.Y.Z` with major/minor `(0, 1)` and patch equal to
  `BASELINE_PATCH`, so a change to either constant without the other fails.
  The test uses the module's existing `_parse_version`, the standard library
  only, and no git invocation.
- **FR5 - Per-task test record alignment:** In
  `test-docs/exit4-tip-argument/task0002.tests.yaml`, the `red_reason` of
  AC-1, AC-2 and AC-3 is rewritten to the new baseline. Each records the
  result actually observed when the module is re-run against a tree whose
  em-workflow registries read the pre-bump value, including the real
  `AssertionError` text. The em-review clause of AC-2's `red_reason` and
  every other field of the file are unchanged.

### Non-Functional Requirements

- **NFR1 - No registry edits:** Neither
  `em-workflow/.claude-plugin/plugin.json` nor
  `.claude-plugin/marketplace.json` appears in the diff. Any red-run check
  against the pre-bump value is done in a throwaway copy and is never
  committed.
- **NFR2 - Suite stays green:** `python3 -m unittest discover -s tests`
  exits 0. `tests/test_exit4_tip_argument_version_bump.py` is the only file
  under `tests/` that is modified.
- **NFR3 - Standard library only:** The module keeps importing only the
  Python standard library (`json`, `re`, `unittest`, `pathlib`) and no other
  test module.
- **NFR4 - Historical records untouched:**
  `feature-docs/exit4-tip-argument/SPEC.md`,
  `feature-docs/exit4-tip-argument/tasks/task0002.md` and
  `feature-docs/exit4-tip-argument/reviews/round2.yaml` are not modified.
- **NFR5 - Sibling finding excluded:** Round-2 finding `4773e33be20e67f4` is
  out of scope: the stale AC-2 test ID
  `test_em_review_entry_has_no_version_key` in `task0002.tests.yaml` and the
  docstring's AC-2 "no version key" text. Neither is edited by this feature.

## Implementation Approach

### Architecture

Not applicable. The change is confined to one Python test module and one
per-task YAML test record.

### Dependencies

**Internal Dependencies:**
- `tests/test_exit4_tip_argument_version_bump.py`: existing
  `_parse_version` helper, reused by the FR4 tie test.
- `test-docs/exit4-tip-argument/task0002.tests.yaml`: the per-task test
  record whose AC-1/AC-2/AC-3 `red_reason` values FR5 updates.

**External Dependencies:**
- None. No dependency is introduced.

### File Structure

```
tests/
└── test_exit4_tip_argument_version_bump.py   # FR1-FR4
test-docs/
└── exit4-tip-argument/
    └── task0002.tests.yaml                   # FR5
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/exit4-version-baseline-refresh/**`
- `test-docs/exit4-version-baseline-refresh/**`

`feature-docs/exit4-version-baseline-refresh/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/exit4-version-baseline-refresh/**` covers
`test-docs/exit4-version-baseline-refresh/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/exit4-version-baseline-refresh/` directory at all; the declared
`test-docs/exit4-version-baseline-refresh/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS1** (FR1, NFR2): Run the module on the current tree:
  `TestPluginManifestVersion` and `TestMarketplaceEntryVersion` pass.
- [ ] **TS2** (FR2): The negative proof rejects the forged `"0.1.68"` sample
  through the baseline matcher, and the non-vacuity guard confirms that
  sample parses.
- [ ] **TS3** (FR4): The tie test asserts that `FORGED_PRE_BUMP_VERSION`
  parses to `(0, 1, BASELINE_PATCH)`. TDD order: write it while the
  constants still read `44` / `"0.1.44"` (green), change only
  `BASELINE_PATCH` and observe red, then update `FORGED_PRE_BUMP_VERSION`
  and observe green.
- [ ] **TS5** (NFR2): Run the full suite with
  `python3 -m unittest discover -s tests`: exit 0.

### Manual Tests

- [ ] **TS4** (FR1, FR5): In a throwaway copy of the repository (never
  committed), set both registries' em-workflow version to the pre-bump
  value and run the module. The baseline tests for AC-1/AC-2 must go red.
  Record the observed `AssertionError` text into the `red_reason` values.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] The `red_reason` text records the message `unittest` actually prints.
  `assertGreater` compares tuples, so the message has the form
  `(0, 1, N) not greater than (0, 1, N)`, not `44 not greater than 44`
  (FR5).

## Assumptions

- **A1:** Refresh the baseline rather than drop the matcher or retire the
  module (answer to `approach.module-treatment`,
  batch-codex-consultation). Codex verified via git that both registries
  read `0.1.68` at `02aff93` and `0.1.69` at `b7541db`.
- **A2:** Only the AC-1/AC-2/AC-3 `red_reason` values in
  `task0002.tests.yaml` are updated. SPEC.md FR6 and `tasks/task0002.md`
  remain historical records (answer to `scope.historical-records`).
- **A3:** Recurrence detection is the real pre-bump negative proof plus a
  stdlib-only tie test, with no git dependency (answer to
  `testing.recurrence-detection`).
- **A4:** Finding `4773e33be20e67f4` is excluded (answer to
  `scope.sibling-finding-ac2`).
- **A5:** `FORGED_VERSION_A` / `FORGED_VERSION_B` (`"0.1.45"` /
  `"0.1.46"`) stay unchanged; they are an arbitrary differing pair for the
  equality matcher.
- **A6:** The baseline matcher keeps its per-component tuple comparison
  against `(0, 1, BASELINE_PATCH)`, so later minor or major bumps (current
  `0.3.16`) stay green. The docstring's "major/minor 0.1" wording is
  rewritten under FR3 to describe this comparison rather than a `0.1` pin.
- **A7:** The tie test's method name is not load-bearing; any name following
  `test/README.md`'s `test_<condition>_<expected_result>` convention
  satisfies FR4.
- **A8:** This change touches no file under a plugin directory, so the
  plugin-version-bump workflow bumps nothing. This SPEC writes no plugin
  version change.
- **A9:** No LICENSE file exists at the project root; this feature
  introduces no dependency.

## Analyst Warnings

- The old `red_reason` wording `44 not greater than 44` does not match what
  `unittest` actually prints: `assertGreater` compares tuples, so the real
  message has the form `(0, 1, N) not greater than (0, 1, N)`. FR5 requires
  recording the re-observed text.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

None. Every requirement is resolved.

## References

- Module under change: `tests/test_exit4_tip_argument_version_bump.py`
- Per-task test record: `test-docs/exit4-tip-argument/task0002.tests.yaml`
