# Verification Document: routeback-residual-connections

## Overview

**Feature**: routeback-residual-connections / **SPEC.md**: `feature-docs/routeback-residual-connections/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/routeback-residual-connections/IMPLEMENTATION.md`

This is the integrated verification run by the verify phase on the integration branch.
Task-level acceptance criteria live in `tasks/task0001.md`. "Base" below means
workflow.yaml `workflow[implement].base_commit`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty: Python, with no
  build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository root.
- Expected: exit code 0.
- Coverage target: not applicable. These are document-contract tests over Markdown and
  JSON, so line coverage does not measure them. Completeness is tracked by the
  matcher-to-proof inventory in the test module docstring instead.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | FR1, AC-1: Normalized I.2.a carries the journal-`merged` premise naming Step I.2.c's gate as `below`. No I.2.c gate or conjunct reference in I.2.a reads `above`. The referenced third-conjunct phrase exists in normalized I.2.c. Negative proof against the already-captured "(the widened I.2.c gate above)" sample. | All assertions pass. The negative proof shows the direction and `above` matchers flag the old wording. | Unit (document contract) |
| TS-2 | FR2, AC-2: The chain-termination sentence is in I.2.a, after the single-causal-construction span (which keeps exactly one "Because " and one " so ") and before the two-parties sentence. The recursion-invariant sentence still follows "can never arise.". The carve-out and in-flight sentences survive. Negative proof against the verbatim I.2.a excerpt at `9f9502487a8da29220aece87f253058becda432e`. | All pass. The excerpt lacks every new termination constant, and its non-vacuity guard passes. | Unit (document contract) |
| TS-3 | FR3, AC-3: The reset target set names "every task whose Step I.2.b step 1 reconciled state is `failed`" (leading, verbatim) and the workflow.yaml `status: failed` member. The connecting sentence cites Step I.2.b step 3 and `replace_all`, and ties the union to the postcondition. The 60-character `tasks.{T}.status` → `pending` window and the four write-token order still hold. Negative proof against the 9f95024 write-set excerpt. | All pass. The excerpt lacks the second member and the connecting sentence, and its guard passes. | Unit (document contract) |
| TS-4 | FR4, FR5, AC-4, AC-5: The cleanup sentence attributes the reconciled-`merged` exclusion to the gate above. The not-merged claim is qualified by workflow.yaml `status` and Step I.2.b step 1's reconciled state, and the bare "confirmed not merged" is absent. The residual sentence follows the leftover-state sentence, precedes "End the phase with a", and names merge-task.sh as the owner of the ref-update / journal-write behaviour. `git branch -D` occurs exactly once inside the scoped sentence. "append" / "rework" are absent from I.2.c. Negative proof against the 9f95024 cleanup excerpt. | All pass. The excerpt contains "confirmed not merged" and lacks every new constant, and its guard passes. | Unit (document contract) |
| TS-5 | FR7, AC-7: Both manifests parse. The em-workflow version is strictly greater than 0.2.0 by per-component numeric comparison, and the two registries are equal. Negative proofs with a forged 0.2.0 and a forged differing pair. | All pass. Both manifests read 0.2.1. | Unit (JSON) |
| TS-6 | AC-8, NFR2, NFR3, NFR5, NFR6, NFR7, NFR9: `python3 -m unittest discover -s tests` exits 0. This runs every pre-existing anchor, ordering, byte-identity and bare-git-line guard in `tests/test_recycled_task_id_consistency.py`, `tests/test_implement_routeback_gate.py`, `tests/test_routeback_reset_scope_consistency.py` and `tests/test_routeback_reset_scope_version_bump.py`. `git diff` from the base to the integration branch is empty for the two edit-forbidden modules. The new modules import only the standard library. | Exit 0. Empty diff for both edit-forbidden modules. | Integration (suite) |
| TS-7 | NFR1, planner-added (SPEC gives NFR1 no scenario): `git diff --name-only` from the base to the integration branch lists only `em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `tests/test_routeback_reset_scope_consistency.py`, `tests/test_routeback_residual_connections_version_bump.py`, and paths under `feature-docs/routeback-residual-connections/` and `test-docs/routeback-residual-connections/`. | No other path appears. In particular, nothing under `em-workflow/scripts/`, `em-workflow/hooks/`, `em-workflow/agents/` or `em-workflow/skills/` changes. | Integration (diff) |

### Edge Cases (from SPEC.md)

Each edge case is covered by a manual reading item below. They are not separate
automated tests.

- EC-1: a task that is workflow.yaml `failed` with no journal event enters the reset
  set only through the FR3 union. Covered by MANUAL-1.
- EC-2: a merged branch whose journal event is missing is the recorded residual.
  Covered by MANUAL-2.
- EC-3: cleanup on an absent worktree or branch is unspecified and out of scope.
  Recorded under MANUAL-2 as a known gap, and not a failure.
- EC-4: the ancestor-check-failed case stays blocked by the third conjunct, because the
  gate is evaluated before the write set. Covered by MANUAL-1.

## Code Quality Verification

- Format: none (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The I.2.a reference to the I.2.c gate reads `below` and resolves to the journal-`merged` conjunct, and no `above` reference remains | TS-1, MANUAL-3 |
| AC-2 | The I.2.a chain-termination sentence is present | TS-2, MANUAL-3 |
| AC-3 | The reset target set names both `failed` sources, and the connecting sentence cites Step I.2.b step 3 and `replace_all` | TS-3, MANUAL-1 |
| AC-4 | The cleanup names the gate as the reason for the exclusion, and both cleanup literals survive | TS-4, MANUAL-2 |
| AC-5 | The unqualified "confirmed not merged" is gone, the claim is source-qualified, and the residual sentence follows the leftover-state sentence | TS-4, MANUAL-2 |
| AC-6 | TS-10 / TS-11 / TS-12-equivalent tests exist, each with a negative proof and a non-vacuity guard | TS-1–TS-4 plus inspection of the module docstring's inventory |
| AC-7 | Both manifests read 0.2.1 | TS-5 |
| AC-8 | The suite passes and the edit-forbidden modules are unmodified | TS-6 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1; MANUAL-3 |
| FR2 | task0001 | TS-2; MANUAL-3 |
| FR3 | task0001 | TS-3; MANUAL-1 |
| FR4 | task0001 | TS-4; MANUAL-2 |
| FR5 | task0001 | TS-4; MANUAL-2 |
| FR6 | task0001 | TS-1, TS-2, TS-3, TS-4 (the tests themselves); TS-6 (they run green) |
| FR7 | task0001 | TS-5 |
| NFR1 | task0001 | TS-7 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-4 |
| NFR5 | task0001 | TS-3, TS-4, TS-6 |
| NFR6 | task0001 | TS-1, TS-2, TS-6 |
| NFR7 | task0001 | TS-6 |
| NFR8 | task0001 | TS-3, TS-4 (citations present); MANUAL-4 (no restatement) |
| NFR9 | task0001 | TS-6 |

## E2E Testing

Not applicable: the project has no E2E framework (`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)

Each item reads the final integrated `em-workflow/references/implement-phase.md` and
re-performs the PR #7 verify reading for the connection it closes. Item numbers match
that PR's MANUAL-n.

- [ ] MANUAL-1 (closes PR #7 MANUAL-1; FR3, EC-1, EC-4)
  - Walk a task that is workflow.yaml `status: failed` with no journal event through
    I.2.c. It must enter the reset set through the second union member and end up
    `pending`, which leaves no workflow.yaml `failed`.
  - Confirm that the text's claim "the postcondition holds" follows from the gate
    (workflow.yaml has no `merged` / `in_progress`) plus the union (workflow.yaml has no
    `failed`), and that it matches `references/workflow-patch.md`'s `replace_all`
    permission conditions and protocol-error rule, which read workflow.yaml statuses.
  - Walk a task whose journal last event is `merged` but whose reconciled state is
    `failed` (ancestor check failed). Confirm the third conjunct still blocks route-back
    before the write set, so the union never makes it admissible.
- [ ] MANUAL-2 (closes PR #7 MANUAL-2; FR4, FR5, EC-2, EC-3)
  - Confirm the cleanup sentence's not-merged claim asserts no more than workflow.yaml
    `status` and Step I.2.b step 1's reconciled state establish.
  - Confirm the reconciled-`merged` exclusion is presented as a consequence of the gate,
    not as a second, independent filter.
  - Compare the residual sentence against `em-workflow/scripts/merge-task.sh`. The
    integration ref advances by `git update-ref` before the journal write. A failed
    journal write prints a warning and the script still exits 0. The "already contained"
    early exit depends on the same journal write. Confirm the sentence describes that
    window accurately and calls it a residual the gate does not close.
  - EC-3 (cleanup on an absent worktree or branch) stays unspecified. That is expected,
    not a failure.
- [ ] MANUAL-3 (closes PR #7 MANUAL-3; FR1, FR2)
  - Confirm I.2.a's forward reference reads `below` and lands on I.2.c's third
    conjunct, which blocks on a journal `merged` independent of the ancestor check.
  - Confirm the new termination sentence genuinely ends the chain I.2.a carve-out ← I.2.c
    gate ← I.2.b step 1 reconciled state ← I.2.a carve-out. The carve-out acts only on a
    `failed` last event paired with workflow.yaml `pending`, so it cannot change the
    `merged` / in-flight classifications the gate reads.
  - Confirm the sentence does not contradict I.2.c's `in_progress`-half wording "(a
    `launched` last event, with the recycled-task-id carve-out that step already
    defines)".
- [ ] MANUAL-4 (NFR8): each new sentence cites its owning rule and does not restate it.
  The owning rules are Step I.2.b step 3, `references/workflow-patch.md`'s `replace_all`
  permission conditions, and merge-task.sh's journal-write behaviour. No new sentence
  paraphrases those rules beyond what FR3 / FR5 require.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Document-contract tests | 4 (TS-1–TS-4) | 4 | 0 | 0 |
| Manifest version test | 1 (TS-5) | 1 | 0 | 0 |
| Suite / diff checks | 2 (TS-6, TS-7) | 2 | 0 | 0 |
| Manual reading | 4 (MANUAL-1–MANUAL-4) | 0 | 0 | 4 |
| **Total** | 11 | 7 | 0 | 4 |
