# Verification Document: recycled-task-id-carveout

## Overview

**Feature**: recycled-task-id-carveout / **SPEC.md**: `feature-docs/recycled-task-id-carveout/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/recycled-task-id-carveout/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature. Per-task acceptance criteria live in `feature-docs/recycled-task-id-carveout/tasks/taskNNNN.md`.

## Build Verification

- Command: none — `workflow.yaml` `project.components.main.build_command` is empty (this repository has no build step).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Expected: exit code 0, no failures and no errors.
- Coverage target: no numeric coverage goal is defined for this repository. The equivalent gate is scenario coverage: every TS below has at least one asserting test, and every new matcher has a paired negative proof.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Normalized I.2.a does not contain the contradictory scope literal, and the whole document contains neither `never read workflow.yaml` nor `never reads workflow.yaml`; negative proof flags the captured pre-change wording | Both absence assertions hold; the negative proof shows the matcher fires on the pre-change sample | Unit |
| TS-2 | Normalized I.2.a names the three journal-only hooks in one claim that they never consult `tasks.{T}.status`; negative proof fails on a sample that folds `queue_stop_guard.py` into that same claim | Positive matcher holds on the revised document; negative proof holds on the sample | Unit |
| TS-3 | Normalized I.2.a names `queue_stop_guard.py` as the explicit exception applying the carve-out; negative proof fails on the pre-change wording where it appeared only in the four-hook "never consults" list | Positive matcher holds; negative proof holds | Unit |
| TS-4 | Normalized Supporting-cast Stop-hook bullet states the carve-out-scoped equivalence and cites I.2.a; the I.2.b step 1 citation literal survives unchanged | Both assertions hold | Unit |
| TS-5 | Static scan over `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py` finds no per-task status read; the same scan flags a sample that DOES read a status, and does not flag a sample containing only the bare substring `workflow.yaml` | Empty violation list for the three real sources; violation reported for the violating sample; none for the bare-substring sample | Integration |
| TS-6 | `queue_stop_guard.py` run as a subprocess on a fixture where a task's journal last event is `failed` and its workflow.yaml status is `pending` | Exit code 2; the BLOCK line on standard error names that task id | Integration |
| TS-7 | Same fixture with that task's workflow.yaml status set to a non-`pending` value | Exit code 0; no BLOCK line | Integration |
| TS-8 | Normalized I.2.a contains the divergence statement naming the missing-journal-event case and marking it deliberate; negative proof shows it absent from the pre-change paragraph sample | Positive matcher holds; negative proof holds | Unit |
| TS-9 | Both version-carrying files parse as JSON, their em-workflow version values are equal, and the value is past the pre-change baseline `0.1.44` | Equality and past-baseline assertions hold; both negative proofs hold | Unit |
| TS-10 | Every pre-change sample introduced by this feature carries a positively-asserted retained anchor in a `TestPreChangeSampleGuards` class (per module) | All guard assertions hold | Unit |
| TS-11 | The full suite — every pre-existing module in `tests/`, including this feature's untouched neighbours and the pre-existing TS-7/TS-8/TS-9/TS-10 guards inside `tests/test_recycled_task_id_consistency.py` — runs green | `python3 -m unittest discover -s tests` exits 0 | Integration |

## Code Quality Verification

- Format: none — `format_command` is empty for this repository. Verify by inspection that new test code follows the surrounding modules' style (module docstring stating what the module covers, module-level constants for matcher literals, `Test<Behavior>` classes, `test_<condition>_<expected_result>` methods).
- Static analysis: none configured. The equivalent gate is the dependency floor: confirm by inspection that no test module imports a third-party package and that no test module imports another test module.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1-FR8 are implemented and tested | Requirements coverage table below; every row has both a task and a verification |
| SC-2 | All test scenarios TS-1..TS-11 pass | Run the test command; map each scenario to its asserting test |
| SC-3 | All non-functional requirements NFR1-NFR6 are satisfied | NFR rows of the coverage table below |
| SC-4 | `python3 -m unittest discover -s tests` exits 0 from the repository root | Run the command on the integrated worktree |
| SC-5 | `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry in `.claude-plugin/marketplace.json` both read `0.1.45` | Direct read of both files (the literal is deliberately not pinned by a test — IMPLEMENTATION.md D5) |
| SC-6 | `queue_stop_guard.py`'s classification logic is byte-unchanged | Diff the feature's merged change set against its base: no file under `em-workflow/hooks/` appears |
| SC-7 | The observed change set is contained in SPEC.md's Declared Change Set | Diff the merged change set against the declared superset |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3 |
| FR2 | task0001 | TS-4 |
| FR3 | task0001 | TS-2, TS-3, TS-10 |
| FR4 | task0002 | TS-5, TS-6, TS-7 |
| FR5 | task0001, task0002 | TS-5, TS-10 |
| FR6 | task0001 | TS-8 |
| FR7 | task0003 | TS-9 (durable pin) + SC-5 (literal, by direct read) |
| FR8 | task0001, task0002, task0003 | TS-11 |
| NFR1 | task0001, task0002, task0003 | TS-11 + import inspection (Code Quality above) |
| NFR2 | task0001, task0002, task0003 | TS-11 (discovery with no registration step) + naming inspection |
| NFR3 | task0001 | TS-11 + inspection that prose matchers compare normalized text while the byte-identity/raw line-wrap guards compare raw text |
| NFR4 | task0002 | TS-6, TS-7 + SC-6 |
| NFR5 | task0002 | TS-6, TS-7 + inspection that the fixture is confined to a temporary directory |
| NFR6 | task0001 | TS-4 |

## E2E Testing

Not applicable — `e2e_test_command` is empty and this feature has no end-to-end surface. The closest equivalent, running the real hook binary under the real hook contract, is covered by TS-6 / TS-7.

## Manual Testing (E2E Not Possible)

- [ ] Read the revised I.2.a recycled-task-id paragraph end to end and confirm it yields ONE interpretation of scope: no sentence restricts the rule to the orchestrator and then exempts a hook. (Human judgment — the automated matchers can only check literals.)
- [ ] Confirm the divergence statement reads as a deliberate, documented divergence describing intended fail-open behavior, not as a defect report or a promise to fix.
- [ ] Confirm the Supporting-cast Stop-hook bullet cites I.2.a rather than restating the rule in a form that could drift, and that I.2.a is still the only normative statement.
- [ ] Confirm by direct read that both version-carrying files show `0.1.45` (SC-5).
- [ ] Confirm the merged change set touches no file under `em-workflow/hooks/` (SC-6).
- No mockup comparison applies: the design step is `skipped` (no user-visible surface).

## Performance / Security Verification

Not applicable. No performance goal is stated. No authenticated, authorized or externally reachable surface is added; the only process boundary exercised is the existing hook contract, observed under a fixture confined to a temporary directory (NFR5).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1..TS-11) | 11 | 11 | 0 | 0 |
| Success criteria (SC-1..SC-7) | 7 | 4 | 0 | 3 |
| Requirements (FR1-FR8, NFR1-NFR6) | 14 | 14 | 0 | 4 (supplementary judgment items) |
