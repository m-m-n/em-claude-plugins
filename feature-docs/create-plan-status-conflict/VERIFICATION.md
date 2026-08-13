# Verification Document: create-plan-status-conflict

## Overview

**Feature**: create-plan-status-conflict
**SPEC.md**: `feature-docs/create-plan-status-conflict/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/create-plan-status-conflict/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature branch.
Per-task acceptance criteria live in `tasks/task0001.md` … `tasks/task0005.md`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty (the
  feature consists of markdown SSOT documents, JSON fixtures/manifest and
  Python tests; there is nothing to compile).
- Expected: n/a. The build gate is satisfied vacuously; do not invent a build
  step.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root of the integration worktree)
- Expected: exit code 0, zero failures, zero errors, and no test skipped that
  was not skipped before this feature.
- Coverage target: not measured — the project has no coverage tooling
  configured. The coverage contract is instead requirement-level: every FR/NFR
  below maps to at least one scenario, and each task's acceptance criteria map
  to assertions in the paired test file.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Step B in `skills/develop/SKILL.md` documents the create-plan exemption, its entry-status preservation and its rationale, while the design-system backfill description still precedes the generic `in_progress` update instruction | Doc assertions in `tests/test_develop_skill_rewiring.py` pass, including the pre-existing ordering assertion | Unit (doc assertion) |
| TS-2 | `references/phases/create-plan-phase.md` §3 documents both branches of the interrupted-`in_progress` rule (reset to `pending` when the patch is not applied; no reset when it is) | Doc assertions in `tests/test_phase_protocols.py` pass, and the section-coverage/order and must-not-restate assertions still pass | Unit (doc assertion) |
| TS-3 | The `replace_all` permission conditions in `references/workflow-patch.md` still permit exactly `pending` and `needs_update`, with the tasks-empty-or-all-pending condition intact | Assertions in `tests/test_workflow_patch_doc.py` pass; the document is unmodified by the feature | Unit (doc assertion) |
| TS-4 | Validating a `replace_all` patch with dry-run application against a workflow whose create-plan step is `in_progress` is rejected; the same patch shape passes for `pending` and for `needs_update` | Rejected case: exit 1 with the `replace-all-not-permitted` identifier attributed to the create-plan step status. Permitted cases: exit 0 | Integration (CLI + fixtures) |
| TS-5 | Full test-suite run after all tasks are merged | `python3 -m unittest discover -s tests` exits 0 | Integration |
| TS-6 | Step B in `skills/develop/SKILL.md` states stop condition 3's carve-out in generalized terms — a `needs_update` set by a transition whose owning phase protocol prescribes automatic re-entry does not stop the loop — enumerating both qualifying transitions (create-plan route back to planning; the create-spec rework spec-change transition) with their owning documents cited, stating the negative `create-spec.stalled` case and its `phase-state/rework.yaml` discriminator, and no longer containing the universal claim that the condition refers to steps other than create-plan. The create-plan `in_progress` exemption keeps its create-plan-only scope, and the spec-change transition is cited rather than restated | Doc assertions in `tests/test_develop_skill_rewiring.py` pass, including the absence assertion on the removed sentence and every pre-existing assertion in that file | Unit (doc assertion) |
| TS-7 | The five stale doc assertions found by the verify phase are retargeted at the current production text rather than deleted or weakened: the two agent-frontmatter assertions compare against the model value the agent files carry, the README assertion describes branch-based resume as the README now expresses it, the batch-mode coverage union names only concepts that document retains (each dropped concept noted with its new owner), and the Step A assertion guards explicit feature-name resolution instead of the removed 0/1/N-hit bootstrap states. No unconditional pass, no new skip/expectedFailure, no deleted test beyond the one prescribed substitution, and no production document, agent file, script or hook modified | Reading `tests/test_refitted_worker_agents.py`, `tests/test_planner_designer_worktree_docs.py`, `tests/test_batch_policies.py` and `tests/test_review_implement_develop_lock_contracts.py` against the integrated diff shows each assertion re-expressed against current text, and each fails when the guarded production text is perturbed | Unit (doc assertion) + diff inspection |

## Code Quality Verification

- Format: none configured (`format_command` is empty). Match the surrounding
  file's existing style instead.
- Static analysis: none configured. The repository's own invariant tests
  (`tests/test_check_plugin_invariants.py`, `tests/test_reference_sweep.py`)
  act as the plugin-level lint and are covered by TS-5.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The handling of a `replace_planning` patch against an `in_progress` create-plan step is uniquely determined (never `in_progress` at dispatch; reset on interrupted entry; rejected if submitted while `in_progress`) | Read Step B (TS-1), §3 (TS-2) and rule 5 (TS-3) together; TS-4 pins the rejection |
| AC2 | Step B and rule 5 do not contradict each other | TS-1 + TS-3, plus the manual cross-read item M-1 below |
| AC3 | The validator's behaviour matches the updated specification without a functional change | TS-4 passes with `references/workflow-patch.md` and `scripts/validate-worker-output.py` unmodified (M-2) |
| AC4 | §3 alone is sufficient to follow the recovery procedure | TS-2 for machine-checkable presence; M-3 for sufficiency |
| AC5 | `python3 -m unittest discover -s tests` passes in full | TS-5; TS-7 confirms the five stale assertions were retargeted rather than removed to reach exit 0 |
| AC6 | The plugin version is bumped | Inspect `em-workflow/.claude-plugin/plugin.json` (0.1.35) and confirm the root `.claude-plugin/marketplace.json` is unmodified |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0004 | TS-1; TS-6 (the `in_progress` exemption keeps its create-plan-only scope while the stop-condition carve-out generalizes) |
| FR2 | task0001 | TS-1 (entry-status preservation stated in Step B), TS-4 (both permitted entry statuses actually accepted) |
| FR3 | task0001, task0004 | TS-1; TS-6 (the rationale block's wording no longer over-claims) |
| FR4 | task0003 | TS-3 + M-2 (document unmodified) |
| FR5 | task0003 | TS-4 + M-2 (validator unmodified) |
| FR6 | task0002 | TS-2 |
| FR7 | task0002, task0004 | TS-5 + M-1 (plugin-wide cross-read); TS-6 + M-9 (SKILL.md no longer contradicts the rework SSOTs) |
| FR8 | task0001, task0002, task0003, task0004, task0005 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7 |
| FR9 | task0003 | TS-5 + AC6 inspection |
| NFR1 | task0003, task0004 | TS-5 + M-2 (no diff on the rework path: `append_rework` conditions, the validator's append branch, `references/rework-task-synthesis.md`); M-9 (`references/rework-task-synthesis.md` still absent from the integrated diff after the rework) |
| NFR2 | task0003 | TS-4 (validator decision logic still behaves identically), TS-5 + M-2 (diff limited to documents, tests, fixtures and the version) |
| NFR3 | task0001, task0002, task0004 | TS-1, TS-2 (rule-5 conditions referenced, never copied; existing must-not-restate assertions still pass); TS-6 (the spec-change transition is cited, never restated) |
| NFR4 | task0001, task0002 | TS-4 for the mechanical part; M-4 for an actual unattended run |

## E2E Testing

No E2E framework is configured for this repository (`e2e_test_command` is
empty), and the feature's end-to-end behaviour is an orchestrator run rather
than an application flow. The end-to-end check is therefore carried as M-4
under manual testing.

## Manual Testing (E2E Not Possible)

- [ ] M-1 (FR7, AC2): Cross-read the four documents — `skills/develop/SKILL.md`
      Step B, `references/phases/create-plan-phase.md` §3,
      `references/phase-state.md` (backfill section, legacy-compatibility
      table, Resume decision table) and `references/workflow-patch.md` rule 5 —
      and confirm no remaining statement asserts that every step is set
      `in_progress` before execution, and that none of the four contradicts
      another. Also re-run the plugin-wide sweep for the `in_progress` token
      to confirm no place outside those documents makes the claim.
- [ ] M-2 (FR4, FR5, NFR1, NFR2): Inspect the integrated diff and confirm it
      touches only documents, tests, fixtures and the plugin version — with
      `references/workflow-patch.md`, `scripts/validate-worker-output.py`,
      `references/rework-task-synthesis.md`, the hooks and the shell scripts
      completely absent from it.
- [ ] M-3 (AC4, US2): Read `references/phases/create-plan-phase.md` §3 in
      isolation and confirm a maintainer can execute the recovery of a feature
      interrupted at `in_progress` from it alone (which branch applies, what to
      reset, when to commit, when to dispatch) without consulting Step B first.
- [ ] M-4 (NFR4): Run `/em-workflow:develop --batch` (or resume this very
      feature) on a feature whose create-plan step is `pending` and confirm the
      phase reaches `completed` with no user interaction and no
      `replace-all-not-permitted` rejection.
- [ ] M-5 (EC2): Walk the already-applied-patch case: a feature interrupted at
      `in_progress` whose proposed patch was applied must reach `completed`
      with no reset, per §11 and the Resume decision table's applied row.
- [ ] M-6 (EC3): Walk the legacy case (create-plan `in_progress`, no
      phase-state) and confirm the legacy-compatibility table and the new §3
      rule land on the same conclusion (re-run from `pending`).
- [ ] M-7 (EC4): Confirm the develop loop's stuck detection (a step executed
      twice with no status progress) produces no false positive on a normal
      single-pass create-plan run, which now goes `pending` → `completed`
      without passing through `in_progress`.
- [ ] M-8 (EC5): Confirm no other mechanism depends on the create-plan step
      being `in_progress` — in particular the queue-related hooks, which are
      expected to read only the `implement` step and task statuses.
- [ ] M-9 (FR7, NFR1, review finding `cmp-stopcond3-universal-claim`):
      Cross-read `skills/develop/SKILL.md` Step B against
      `references/rework-task-synthesis.md` §10 and
      `references/contracts/rework-planner-contract.md`'s Specification-change
      transition, and confirm (a) the create-spec `needs_update` those
      documents prescribe is reachable — Step B executes create-spec instead of
      stopping — while (b) the `create-spec.stalled` abort still stops the
      loop, and (c) neither rework document was modified by this feature.
- [ ] M-10 (AC5, TS-7, verify failed items TS-5 / AC5): Confirm that the five
      stale assertions task0005 retargeted were invalidated by commits outside
      this feature (all five fail identically at
      `workflow[implement].base_commit` `ca1a189`), and that the integrated
      diff contains no change to `em-workflow/agents/designer.md`,
      `em-workflow/agents/implementation-planner.md`, `em-workflow/README.md`,
      `em-workflow/references/batch-mode.md` or
      `em-workflow/skills/develop/SKILL.md` made in order to satisfy one of
      them — the fix direction stayed test → current reality.

Mockup visual comparison is not applicable: the design step is `skipped`
(no visual element or UI in this feature).

## Performance / Security Verification (if applicable)

- Permission-condition floor: the first `replace_all` condition (tasks empty,
  or every task `pending`) is still required — verified by TS-3.
- Terminal-status protection: a `replace_all` against a `completed` / `failed`
  create-plan is still rejected — covered by the same validator check TS-4
  exercises; confirm no fixture or assertion weakens it.
- Write-ownership boundary: workers still never write `workflow.yaml`
  directly — verified as part of M-2 (no change to the ownership statements or
  to the validator).
- Performance: not applicable (documentation, tests and a version only).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 … TS-7) | 7 | 6 | 0 | 1 (TS-7's diff-inspection half, carried as M-10) |
| Success criteria (AC1 … AC6) | 6 | 4 | 0 | 2 (AC2, AC4 partially manual) |
| Manual checks (M-1 … M-10) | 10 | 0 | 0 | 10 |
| Security checks | 3 | 2 | 0 | 1 |
