# Verification Document: tip-capture-idiom-unification

## Overview

**Feature**: tip-capture-idiom-unification /
**SPEC.md**: `feature-docs/tip-capture-idiom-unification/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/tip-capture-idiom-unification/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged result. Per-task
acceptance criteria live in `tasks/task0001.md` and `tasks/task0002.md`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. The change set is
  Markdown, shell comments, Python test modules and JSON manifests; nothing is compiled.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the integration worktree root.
- Expected: exit code 0, no failures and no errors, and the new module
  `tests/test_tip_capture_idiom_uniformity.py` present among the discovered modules.
- Coverage target: no coverage tooling is configured in this repository, so no
  percentage target applies. The equivalent criterion is that every requirement below
  maps to at least one passing scenario.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The new uniformity module locates the seven tip-carrying call sites (`BASE_COMMIT`, `LAUNCH_TIP`, `RECONCILE_TIP`, `ROUTEBACK_TIP`, `TERMINAL_TIP`, `ABORT_TIP`, `COMPLETION_TIP`) in `implement-phase.md` and checks each one | Per site: the capture resolves the integration branch ref, no capture uses the worktree-HEAD form, every refresh target in the site is the branch name, and the capture index is less than the refresh index | Unit |
| TS-2 | The Branch & Worktree Model's exit-4 recovery bullet is checked for the same capture-before-refresh relation the per-site checks assert | The bullet states re-capture from the branch ref before the refresh; first attempt and exit-4 retry cannot diverge | Unit |
| TS-3 | The new module reads `commit-docs.sh` and checks both prose blocks | The `expected_base_tip` description and the RECOVERY CONTRACT block describe capture from the branch ref before/independent of the refresh; the old refresh-time-capture phrasing is gone; the carve-out sentence naming Step I.2.c's route-back commit is present verbatim | Unit |
| TS-4 | The new module compares `commit-docs.sh`'s comment-stripped source against a pinned pre-change expectation | Every non-comment line is byte-identical; the change is comment-only | Unit |
| TS-5 | `python3 -m unittest discover -s tests` runs over the merged result | The whole suite passes, including the amended `tests/test_implement_routeback_gate.py` and the untouched `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_recycled_task_id_consistency.py` and `tests/test_routeback_reset_scope_consistency.py` | Integration |
| TS-6 | `git diff` over `tests/` is inspected against the implement baseline | The only pre-existing module touched is `tests/test_implement_routeback_gate.py`, and within it only the route-back order pin, the abort tip-capture literal and the abort order pin changed; the sole added file is the new uniformity module | Manual (diff) |
| TS-7 | One converted site is temporarily reverted to the post-refresh HEAD capture form, the suite is run, and the revert is undone | The uniformity module fails on the reverted document and passes again afterwards — it detects drift rather than passing trivially | Manual (negative) |
| TS-8 | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are read directly | Both carry the identical version string `0.1.46`, one patch step above `0.1.45` | Manual (diff) |

TS-7's committed counterpart is the module's own negative proofs (each new matcher
fails against a captured pre-change sample, each sample carrying a non-vacuity guard);
the temporary-revert run above is the manual confirmation that those proofs describe
the live document.

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty.
- Static analysis: none configured. The equivalent gate is that the new test module
  imports only the Python standard library and no other test module.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1-FR10 are implemented | The coverage table below; every row has a task and a passing scenario |
| SC-2 | All non-functional requirements NFR1-NFR6 are satisfied | The coverage table below, plus TS-6's diff inspection for NFR2 / NFR6 |
| SC-3 | Acceptance criteria AC1-AC6 hold | AC1 → TS-1; AC2 → TS-2; AC3 → TS-3, TS-4; AC4 → TS-5, TS-6; AC5 → TS-7; AC6 → TS-8 |
| SC-4 | Test scenarios TS-1 through TS-8 pass | This document's scenario table |
| SC-5 | The full suite passes | TS-5 |
| SC-6 | The observed change set is contained in SPEC.md's Declared Change Set | TS-6 plus a `git diff --name-only` over the whole merged result |
| SC-7 | `implement-phase.md` and `commit-docs.sh` prose are internally consistent | TS-1, TS-2, TS-3, with the one documented exception recorded in IMPLEMENTATION.md D5 |
| SC-8 | Code review is completed | The review phase's own record |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-1 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-5 |
| FR7 | task0001 | TS-5, TS-6 |
| FR8 | task0001 | TS-3, TS-4 |
| FR9 | task0001 | TS-7 |
| FR10 | task0002 | TS-8 |
| NFR1 | task0001 | TS-1, TS-2 |
| NFR2 | task0001 | TS-5, TS-6 |
| NFR3 | task0001 | TS-5, TS-6 |
| NFR4 | task0001 | TS-3, TS-4 |
| NFR5 | task0001 | TS-1, TS-7 |
| NFR6 | task0001, task0002 | TS-6 |

## E2E Testing

No E2E framework is configured for this repository and
`project.components.main.e2e_test_command` is empty; the feature has no runtime
surface to drive. This section has no items.

## Manual Testing (E2E Not Possible)

- [ ] TS-6: inspect `git diff` over `tests/` against the implement baseline commit and
      confirm the scope containment described above.
- [ ] TS-7: temporarily revert one converted site to the post-refresh HEAD capture
      form, confirm the uniformity module fails, then restore the file and confirm it
      passes again.
- [ ] TS-8: read both version manifests and confirm the identical `0.1.46` string.
- [ ] Confirm the residual item recorded in IMPLEMENTATION.md D5 — the Step I.2.c
      batch-mode restatement left byte-identical — is still the accepted disposition
      rather than an oversight.

The design step is `skipped` for this feature, so there is no mockup
visual-comparison item.

## Performance / Security Verification (if applicable)

- Performance: not applicable — no runtime execution path changes.
- Security (NFR5, the one safety-relevant invariant): no site targets `reset --hard`
  at a captured SHA; every refresh target is the branch name. Checked mechanically by
  TS-1 across all seven sites, and by TS-7's drift proof.
- `commit-docs.sh` argument handling, exit codes, locking and staleness comparison are
  unchanged — checked by TS-4.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (document/script consistency) | 4 | 4 | 0 | 0 |
| Integration (full suite) | 1 | 1 | 0 | 0 |
| Scope containment / drift / manifests | 3 | 0 | 0 | 3 |
| Total | 8 | 5 | 0 | 3 |
