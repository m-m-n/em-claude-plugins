# Verification Document: abort-phase-terminal

## Overview

**Feature**: abort-phase-terminal /
**SPEC.md**: `feature-docs/abort-phase-terminal/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/abort-phase-terminal/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, after all
tasks are merged into the integration branch. Per-task acceptance criteria
live in `tasks/task0001.md`, `tasks/task0002.md` and `tasks/task0003.md`.

## Build Verification

Not applicable. `workflow.yaml` `project.components.main.build_command` is
empty — this repository is a Claude Code plugin marketplace with no build
step. Nothing is compiled or packaged by this feature.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root)
- Expected: exit code 0, no failures and no errors
- Coverage target: not applicable — no coverage tooling is configured and no
  coverage threshold exists in the project. The equivalent completion signal
  is scenario coverage: every requirement below maps to at least one test
  scenario, and every scenario is exercised by the single command above
  (except the parts explicitly marked manual).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Slice implement-phase.md from `### I.2.c: Failed handling` to `### Supporting cast`, normalize whitespace, then take the slice from `- **abort phase**` to the batch-mode paragraph's start | The slice contains the refresh literal `reset --hard em-workflow/{feature}/integration`, a `rev-parse HEAD` tip capture, a write of the `implement` step's `status` to `failed`, and a `commit-docs.sh` call with a third argument; the phrase `` leave `implement` as `failed` for manual handling `` is absent from the section; the section heading and the `- **abort phase**` opener are byte-identical | Unit |
| TS-2 | On the same section, take the slice starting at `` Batch mode (`references/batch-mode.md` `` | It contains the same refresh / write / `commit-docs.sh` / report elements, no longer contains `` implement stays `failed`, report and stop ``, and — on the raw, un-normalized text — still ends the section with nothing between it and `### Supporting cast` | Unit |
| TS-3 | Read both abort slices (the option bullet and the batch-mode paragraph) and the rejected-path branch | Both abort slices state the bounded side-effect set (no `create-plan` `needs_update`, no task status/notes write set, no worktree or branch cleanup) and name `stop condition 3` together with the `next Step B iteration` formulation; the rejected path's own side-effect sentences are still present unchanged | Unit |
| TS-4 | Regression: assert the literal `the same terminal as the "abort phase" option below` in the rejected-path slice | Present; the existing tests asserting it (`test_rejected_path_cites_stop_condition_3_and_abort_phase`, `test_control_returns_via_stop_condition_3`) pass unmodified | Unit (regression) |
| TS-5 | Over the normalized Branch & Worktree Model section, check the bounded-recovery enumeration | The abort terminal status commit is named among the bound call sites; `Step I.1's baseline commit`, `Step I.2.b's wake-phase commit` and `Step I.2.c's rejected-path terminal status commit` are still named; the route-back commit is still the single carve-out; the literal `` the three `commit-docs.sh` call sites in this phase where exit 4 can occur `` is absent | Unit |
| TS-6 | Read batch-mode.md and locate the row containing `` `implement.failed-task` `` | The row states the write-and-commit terminal, still contains `Auto-select **retry** once per task`, `Route-back-to-planning is never taken automatically` and `` Full detail: `references/implement-phase.md` Step I.2.c ``, and no longer contains `` `implement` stays `failed` ``; `tests/test_batch_policies.py` stays green unmodified | Unit |
| TS-7 | Run the three pin-bearing modules — `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py` | Each module's batch-mode paragraph equality assertion passes against the post-change text. Negative proof (manual, not committed): reverting any single one of the three literals to its pre-change value makes exactly that module fail | Unit (regression) + Manual |
| TS-8 | Edge case: on the normalized I.2.c section, assert absence of the substrings `rework` and `append`; scan the whole implement-phase.md for bare `git commit` / `git add` lines | Both substrings absent; the bare-line scan returns an empty list | Unit |
| TS-9 | `tests/test_implement_routeback_gate.py::TestPluginVersionBumpedInLockstep` | Passes: the plugin manifest and the marketplace `em-workflow` entry agree, `(major, minor) == (0, 1)`, patch > 42. Inspection additionally confirms both read `0.1.44` | Unit + Manual (value inspection) |
| TS-10 | Integration: inspect the working-tree diff of the merged feature and run the full suite | The change set touches only implement-phase.md, batch-mode.md, the three pin modules and the two version manifests — `tests/test_abort_phase_terminal_batch_mode.py` is absent from it, the `implement.failed-task` row assertions living in `tests/test_implement_routeback_gate.py`; `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py`, `em-workflow/scripts/commit-docs.sh`, the hooks and `feature-docs/routeback-gate-postcondition/SPEC.md` are absent from the diff; `python3 -m unittest discover -s tests` exits 0 | Integration (manual diff inspection + automated suite) |

## Code Quality Verification

- Format: not applicable — `project.components.main.format_command` is empty
  and the repository defines no formatter for Markdown, Python or JSON.
- Static analysis: not applicable — no linter is configured. The equivalent
  mechanical guard for this feature is the document-contract test set above,
  which pins the structural anchors and forbidden substrings.
- Manual quality check: the two protocol documents must remain internally
  consistent (NFR6) — see the Manual Testing section.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-A | All functional requirements FR1–FR10 are implemented and verified | The coverage table below; every row has at least one passing scenario |
| SC-B | All non-functional requirements NFR1–NFR6 hold | The coverage table below |
| SC-C | All test scenarios TS-1 through TS-10 pass | Run the suite; perform the two manual items |
| SC-D | `python3 -m unittest discover -s tests` exits 0 from the repository root | Run the command; check the exit code |
| SC-E | Both version manifests read `0.1.44` | TS-9 |
| SC-F | The actual change set is contained in SPEC.md's Declared Change Set | TS-10 |
| SC-G | Code review is completed | The review phase's own record |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-4 |
| FR6 | task0001 | TS-5 |
| FR7 | task0002 | TS-6 |
| FR8 | task0001 | TS-7 |
| FR9 | task0002 | TS-9 |
| FR10 | task0001, task0002 | TS-10 |
| NFR1 | task0001 | TS-8 |
| NFR2 | task0001 | TS-1 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001, task0002 | TS-10 |
| NFR5 | task0001, task0002 | TS-7, TS-10 |
| NFR6 | task0001, task0002 | TS-3, TS-6 |

## E2E Testing

Not applicable. The project defines no E2E command
(`project.components.main.e2e_test_command` is empty) and no E2E
infrastructure exists (SPEC.md assumption A6). This feature ships no runtime
surface an E2E harness could drive.

## Manual Testing (E2E Not Possible)

- [ ] **Change-set containment (TS-10)**: inspect the merged diff and confirm
      it touches only the seven expected paths; confirm every frozen path
      listed in TS-10 is absent from it, and that
      `tests/test_abort_phase_terminal_batch_mode.py` is absent from it too.
- [ ] **Byte-pin negative proof (TS-7)**: revert one of the three paragraph
      literals to its pre-change value, run the suite, confirm exactly that
      one module fails, then restore it. Nothing from this experiment is
      committed.
- [ ] **Version value inspection (TS-9)**: read both manifests and confirm
      the literal `0.1.44` in each (the automated assertion is deliberately
      value-independent).
- [ ] **Cross-document consistency (NFR6)**: read Step I.2.c's abort option,
      its batch-mode paragraph, the rejected-path branch, and batch-mode.md's
      `implement.failed-task` row side by side; confirm all four describe one
      and the same terminal and that none claims `implement` reaches `failed`
      without naming the write that produces it.
- [ ] **Readability of the stopping point (BO2)**: confirm that, reading only
      Step I.2.c, an agent can tell that after abort the run stops via
      develop's stop condition 3 on the next Step B iteration.

No mockup comparison item applies: the design step is `skipped` and this
feature produces no visual surface.

## Performance / Security Verification

Not applicable. This is a documentation-only change (NFR4) with no
authentication, authorization, input-handling, data-storage, network or
performance surface. No performance requirement exists in the resolved
requirements.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 … TS-10) | 10 | 9 | 0 | 3 (TS-7 negative proof, TS-9 value inspection, TS-10 diff inspection) |
| Success criteria (SC-A … SC-G) | 7 | 4 | 0 | 3 |
| Requirements (FR1–FR10, NFR1–NFR6) | 16 | 16 | 0 | 0 |
| Build / format / static analysis | 0 | 0 | 0 | 0 (not applicable) |
