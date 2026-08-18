# Verification Document: declared-change-set-implementation

## Overview

**Feature**: declared-change-set-implementation
**SPEC.md**: `feature-docs/declared-change-set-implementation/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/declared-change-set-implementation/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature. Per-task
acceptance criteria live in `tasks/task0001.md` and `tasks/task0002.md`.

## Build Verification

Not applicable. `project.components.main.build_command` is empty — the project
has no build step. The changed artifacts are Markdown, Python test modules, and
JSON manifests, none of which is compiled.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Working directory: repository root
- Expected: exit code 0, no failures, no errors
- Coverage target: not measured. The project has no coverage tooling and adding
  one is outside this feature's declared change set (NFR4).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The SPEC-template test asserts that every member of its literal set — including the newly added one — appears in the template's `## Declared Change Set` section | All assertions in that module pass | Unit |
| TS2 | The REQUIREMENTS-template test performs the same assertion against `### 9.4 宣言された変更集合` of its template | All assertions in that module pass | Unit |
| TS3 | The negative proof against the captured pre-change samples keeps detecting absence for input that does not contain the added member | Every negative-proof assertion in both modules passes, and the samples are byte-identical to their pre-change state | Unit (edge case) |
| TS4 | The whole suite passes without regression after both tasks are merged | Exit code 0, no failures, no errors, no skipped-then-silently-passing module | Integration |

## Code Quality Verification

- Format: not applicable. `project.components.main.format_command` is empty; the
  project defines no formatter.
- Static analysis: not configured for this project.
- Standing constraint re-checked at verification time: no test module under
  `tests/` imports a package outside the Python standard library (NFR2).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1–FR4 are implemented | The coverage table below has a task for every FR, and each FR's verification column reports pass |
| SC-2 | All test scenarios TS1–TS4 pass | Run the test command from the repository root; exit code 0 |
| SC-3 | `python3 -m unittest discover -s tests` passes at the repository root | Same run as SC-2 |
| SC-4 | The change scope stays within the two templates, two test modules, and two version declarations | MV-4 below: the observed change set of the merged feature is contained in SPEC.md's Declared Change Set |
| SC-5 | Code review is completed | The review phase records a round with no residual critical/high findings |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS4 |
| FR2 | task0001 | TS2, TS4 |
| FR3 | task0001 | TS1, TS2, TS4 |
| FR4 | task0002 | No automated test (see Gaps below) — MV-2 |
| NFR1 | task0001 | TS1, TS2 verify the member's spelling against the SSOT naming; MV-1 verifies notation and placement |
| NFR2 | task0001 | TS4 |
| NFR3 | task0001 | TS3, TS4 |
| NFR4 | task0001, task0002 | No automated test (see Gaps below) — MV-3, MV-4 |

### Coverage gaps

- **FR4** has no verifying test. The project has no test that reads the plugin
  manifests, and adding one would create a new test module, which NFR4 places
  outside the declared change set. Verified by MV-2 instead.
- **NFR4** is a scope constraint on the change itself; it is verified by the
  declared change-set containment check (MV-4) rather than by the suite.
- **NFR1**'s placement half (the added member's position relative to its
  neighbours) is not asserted by any test — only its presence and spelling are.
  Verified by MV-1.

## E2E Testing

Not applicable. The project has no E2E framework and
`project.components.main.e2e_test_command` is empty. Nothing in this feature is
executable end-to-end.

## Manual Testing (E2E Not Possible)

- [ ] **MV-1 (NFR1)**: in both templates, the added member sits immediately
      after the `SPEC.md` entry, uses the same inline-code notation as its
      neighbours in that same sentence, and uses that sentence's own separator
      (comma-and-prose in the English template, ideographic comma in the
      Japanese one). The spelling matches
      `em-workflow/references/phases/create-plan-phase.md` and
      `em-workflow/references/phase-state.md`.
- [ ] **MV-2 (FR4)**: `em-workflow/.claude-plugin/plugin.json` and the
      corresponding entry in `.claude-plugin/marketplace.json` declare the same
      version string, that string is one patch increment above the value both
      declared before this feature, and both files' diffs are a single changed
      line each.
- [ ] **MV-3 (NFR3, NFR4)**: the captured pre-change samples inside both test
      modules are unchanged, and no pre-existing member was renamed, reordered,
      or removed in any of the four content destinations.
- [ ] **MV-4 (NFR4, SC-4)**: the merged feature's observed change set, excluding
      the workflow-generated `feature-docs/` and `test-docs/` entries, is
      contained in the six paths SPEC.md declares. Any additional path is a
      scope violation.

## Performance / Security Verification

Not applicable. The feature adds no runtime code, no input handling, no network
or filesystem behaviour, and no dependency. `project.license` is `none` and the
feature introduces no new dependency, so no license verification applies.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 4 (TS1–TS4) | 4 | 0 | 0 |
| Success criteria | 5 (SC-1–SC-5) | 3 | 0 | 2 |
| Manual checks | 4 (MV-1–MV-4) | 0 | 0 | 4 |
| Build / format | 0 | 0 | 0 | 0 |
