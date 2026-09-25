# Verification Document: tests-yaml-record-contract

## Overview

**Feature**: tests-yaml-record-contract / **SPEC.md**: `feature-docs/tests-yaml-record-contract/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/tests-yaml-record-contract/IMPLEMENTATION.md`

## Build Verification

- Command: none (workflow.yaml `project.components.main.build_command` is empty; the
  change is Markdown, JSON and a Python test module).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run at the repository root)
- Expected: exit code 0, no failures or errors, and the new document-contract test module
  is among the collected tests.
- Coverage target: not applicable (document-contract tests; the project has no coverage
  tooling).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Extract the Step 4c section of implementer.md; check the rule for criteria with no executable check (`tests: []` / `red_confirmed: false` / `red_reason` / `unconfirmed_reds`) and the mention of documentation-only tasks | All present in Step 4c | Unit |
| TS-2 | Check Step 4c for the meaning of `red_confirmed: true` (observed failure of an executed check), that reading a document is not an observation, and the prohibition on locally redefining field meanings | All present in Step 4c | Unit |
| TS-3 | Check that Step 4c names `unconfirmed_reds` as the report destination for `red_confirmed: false`, and that no wording to put those criteria in notes remains | Destination present; old routing phrase absent | Unit |
| TS-4 | Check Step 4c for: re-run output recorded in the `final_failures` comment, the skip condition (no change to files the suite reads), the "baseline inherited" wording and the report statement when skipping, re-running when the condition cannot be confirmed, and the prohibition on presenting the same run result twice | All present in Step 4c | Unit |
| TS-5 | Check that Step 6 states the re-run after parent-side adoption is not subject to the skip condition | Present in Step 6 | Unit |
| TS-6 | Run the document-contract test against the pre-change implementer.md and observe it fail; run it after the change and observe it pass | Fails before, passes after | Integration |
| TS-7 | Compare the em-workflow version in plugin.json and marketplace.json with each other and with the value at the implement base commit | Equal to each other; exactly one patch above the base value | Integration |
| TS-8 | Run `python3 -m unittest discover -s tests` at the repository root | Exit code 0; no test that passed at the base now fails | Integration |
| TS-9 | Planner-added (SPEC has no scenario for NFR1): compare the tests.yaml keys described in implementer.md at the implement base commit and at the integration head | Same key set; only comment text for `final_failures` may differ | Integration |
| TS-10 | Planner-added (SPEC has no scenario for NFR2 / NFR3): list the files changed between the implement base commit and the integration head | No validator, hook or script for tests.yaml is added or changed; among documents, only implementer.md carries the tests.yaml recording rules (no other document restates them) | Integration |

## Code Quality Verification

- Format: none configured (workflow.yaml `format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Step 4c states the no-executable-red recording form and names documentation-only tasks as covered | TS-1 (automated by the contract test) |
| AC-2 | Step 4c fixes the meaning of `red_confirmed: true`, excludes reading a document as an observation, and forbids local redefinition | TS-2 (automated by the contract test) |
| AC-3 | Step 4c routes `red_confirmed: false` to `unconfirmed_reds` and no longer routes it to notes | TS-3 (automated by the contract test) |
| AC-4 | Step 4c states the `final_failures` re-run recording, skip condition, skip wording and report statement, and re-run on unconfirmable condition | TS-4 (automated by the contract test) |
| AC-5 | Step 4c forbids presenting the same run result as two independent observations | TS-4 (automated by the contract test) |
| AC-6 | Step 6 states the skip condition does not apply after parent-side adoption | TS-5 (automated by the contract test) |
| AC-7 | The contract test checks AC-1 to AC-6, fails before the change and passes after | TS-6 (red evidence in the task's tests.yaml plus the current green run) |
| AC-8 | plugin.json and marketplace.json em-workflow versions are equal and one patch above the previous value | TS-7 |
| AC-9 | `python3 -m unittest discover -s tests` passes with no regression | TS-8 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6 |
| FR2 | task0001 | TS-2, TS-6 |
| FR3 | task0001 | TS-3, TS-6 |
| FR4 | task0001 | TS-4, TS-6 |
| FR5 | task0001 | TS-5, TS-6 |
| FR6 | task0001 | TS-6 |
| FR7 | task0001 | TS-7 |
| NFR1 | task0001 | TS-4, TS-9 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-10 |
| NFR4 | task0001 | TS-6, TS-8 |
| NFR5 | task0001 | TS-8 |

## Manual Testing (E2E Not Possible)

- [ ] Read Step 4c, Step 6 and Step 7 of implementer.md together: the new rules are
      coherent, use the Step 7 report fields `unconfirmed_reds` and `notes` as they are
      defined there, and do not contradict the `tests_yaml_path` description in
      `em-workflow/references/implement-phase.md` or `em-workflow/skills/tdd-testing/SKILL.md`
      (SPEC ASM-4, ASM-5).
- [ ] Each SPEC edge case resolves unambiguously from the new wording: mixed criteria in one
      task; a build or lint criterion; a documentation-only task for which a
      document-contract test can be written; a task that changed a document the tests
      read; an unconfirmable skip condition; repeated adoptions in the Step 6 conflict loop.
- [ ] The task's own `test-docs/tests-yaml-record-contract/task0001.tests.yaml` follows the
      new rules: `red_confirmed: true` only where a failing run was observed, criteria
      without an observable red recorded with `red_confirmed: false` and a `red_reason`,
      and a `final_failures` comment that reflects an actual re-run rather than a copy of
      the baseline run.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 10 (TS-1 to TS-10) | 10 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 9 (AC-1 to AC-9) | 9 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
