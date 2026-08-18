# Verification Document: recycled-task-id-contract

## Overview

**Feature**: recycled-task-id-contract /
**SPEC.md**: `feature-docs/recycled-task-id-contract/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/recycled-task-id-contract/IMPLEMENTATION.md`

Every command below runs from the repository root of the integration
worktree.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. This
  feature ships Markdown and Python test modules; there is nothing to build.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: not measured — the project has no coverage tooling and no
  coverage threshold. Coverage is expressed instead as requirement-to-test
  mapping in "Functional Requirements Coverage" below.

### Test Scenarios from SPEC.md

TS1-TS5 come from SPEC.md's Test Scenarios / Edge Cases. TS6-TS13 are added
by this verification plan so that every FR/NFR has at least one verifying
scenario; they are derived from SPEC.md's Success Criteria (AC1, AC2, AC4,
AC7) and Non-Functional Requirements.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | For each hook the classification table places in the "does not read the per-task workflow status" group, assert individually that I.2.a's wording places it there | Each hook of the group is asserted separately; the group is non-empty | Unit |
| TS2 | For the explicit exception (`queue_stop_guard.py`), verify in a separate assertion that it is classified as reading the per-task workflow status | The exception is asserted independently of the group above; breaking one does not mask the other | Unit |
| TS3 | Pin test: parse the classification table in `implement-phase.md` and verify, for every listed hook, that the classification and the source agree | Empty disagreement list; a hook path that does not resolve, an unknown classification value or a missing table is a failure | Integration |
| TS4 | Negative check: an inverted classification (sample table whose values are flipped) is fed through the same parse/compare path | Non-empty disagreement list — the pin is proven not to be a no-op | Unit |
| TS5 | Full run of `python3 -m unittest discover -s tests` from the repository root | Exit code 0; every pre-existing module still green | Integration |
| TS6 | I.2.a's recycled-task-id scope statement is a single, self-consistent statement — no "only X … with a contradicting exception" construction | The post-change phrase is present, the contradicting construction absent, with a paired negative proof | Unit |
| TS7 | The Stop-hook bullets in "Supporting cast: journal, hooks, resume" state the same classification as I.2.a and cite the classification table | Bullet wording agrees with I.2.a; no bullet contradicts the table | Unit |
| TS8 | I.2.a states, with its reason, that the hooks treat a task as unlaunched solely from the absence of a journal event for that id | The statement and its reason are present; no promise of the `status != merged` protection the hooks do not apply | Unit |
| TS9 | Both version registries parse as JSON and carry the same version, one patch increment above the pre-change value | Versions equal; family unchanged; patch above the recorded baseline; forged pre-bump value fails | Unit |
| TS10 | The new and changed test modules import only the standard library (a sibling module inside `tests/` is not a third-party dependency) | No third-party import anywhere in the feature's test code | Unit + inspection |
| TS11 | The new modules live at `tests/test_*.py`, are discovered by the runner, and follow the `Test<Behavior>` / `test_<condition>_<expected_result>` naming | Both modules appear in the discovery run; naming conventions hold | Inspection |
| TS12 | The integrated diff touches no file under `em-workflow/hooks/` | Zero hook files in the diff; `queue_stop_guard.py`'s classification logic byte-identical | Inspection |
| TS13 | No hook classification is restated as a literal in test code; both consumers derive their expectation from the parsed table | Exactly one parse step exists and is shared; no hard-coded hook-to-classification mapping in `tests/` | Inspection |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty. Follow
  the surrounding style of each edited file.
- Static analysis: none configured in this project.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | I.2.a's recycled-task-id wording is a single, non-contradictory statement | TS6, plus the manual single-reading check below |
| AC2 | The Supporting cast Stop-hook bullets agree with I.2.a | TS7, plus the manual cross-read below |
| AC3 | `TestRecycledTaskIdRuleScopedToOrchestrator` asserts the two groups separately | TS1, TS2 |
| AC4 | I.2.a states, with its reason, that the hooks decide unlaunched solely from the absence of the journal | TS8 |
| AC5 | One pin test parses the machine-readable table and verifies each hook's source against it | TS3, TS4 |
| AC6 | `python3 -m unittest discover -s tests` passes from the repository root | TS5 |
| AC7 | Both registries carry the same bumped version | TS9 |
| — | `queue_stop_guard.py`'s classification logic and every hook's runtime behaviour are unchanged (NFR3) | TS12 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS6, TS5 |
| FR2 | task0001 | TS7, TS5 |
| FR3 | task0001 | TS1, TS2, TS5 |
| FR4 | task0001 | TS8, TS5 |
| FR5 | task0001 | TS1, TS2, TS3, TS4, TS5 |
| FR6 | task0002 | TS9, TS5 |
| NFR1 | task0001, task0002 | TS10, TS5 |
| NFR2 | task0001, task0002 | TS11, TS5 |
| NFR3 | task0001, task0002 | TS12 |
| NFR4 | task0001 | TS13, TS3 |

## E2E Testing

Not applicable — `project.components.main.e2e_test_command` is empty and the
project has no E2E framework. The feature has no runtime surface an E2E test
could exercise.

## Manual Testing (E2E Not Possible)

- [ ] Read I.2.a once, top to bottom, and confirm a single interpretation of
      the recycled-task-id rule is reachable without cross-referencing
      another section (AC1 — machine assertions can pin phrases but not
      "non-contradictory on a single reading").
- [ ] Read the Supporting cast Stop-hook bullets against I.2.a and the
      classification table and confirm all three describe the same
      classification (AC2).
- [ ] Confirm I.2.a's unlaunched-detection paragraph reads as a record of
      what the hooks actually do, not as a promise of protection (AC4).
- [ ] Confirm the classification table's rows match the hooks the surrounding
      prose names — no orphan row, no unlisted hook that the prose classifies.

## Performance / Security Verification (if applicable)

Not applicable. The feature changes documentation, test code and two version
fields; it introduces no runtime path, no input surface and no data handling.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS13) | 13 | 9 | 0 | 4 (TS10-TS13 are inspection-assisted) |
| Success criteria (AC1-AC7 + NFR3) | 8 | 6 | 0 | 3 |
| Manual checks | 4 | 0 | 0 | 4 |
