# Verification Document: routeback-gate-postcondition

## Overview

**Feature**: routeback-gate-postcondition /
**SPEC.md**: `feature-docs/routeback-gate-postcondition/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/routeback-gate-postcondition/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, run after
every task has merged into the integration branch. Task-level acceptance
criteria live in `tasks/task0001.md` and `tasks/task0002.md`.

## Build Verification

- Command: not applicable — `project.components.main.build_command` is empty
  (the repository ships Markdown protocol documents, Python scripts and JSON
  manifests; nothing is compiled).
- Substitute check: `em-workflow/.claude-plugin/plugin.json` and the
  repository-root `.claude-plugin/marketplace.json` both parse as JSON.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root — here, from the integration worktree root).
- Expected: exit code 0, no failure, no error, no skipped test.
- Coverage target: not applicable — the repository has no coverage tooling and
  none is added (FR5). The coverage substitute is requirement traceability:
  every FR/NFR maps to at least one scenario below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Read `em-workflow/references/implement-phase.md` Step I.2.c | Both status names (`merged`, `in_progress`) appear as conjunctive blockers of route back, and `failed` → `pending` is still in the write set | Unit (document assertion) |
| TS2 | Reason over a workflow.yaml where some tasks are `failed` and none is `merged` or `in_progress` | The documented gate admits route back; the write set turns the `failed` tasks into `pending`, satisfying `replace_all` admissibility | Manual (reasoning over TS1's asserted text) |
| TS3 | Reason over a workflow.yaml with a stale `in_progress` task left by a crashed implementer | The documented gate rejects route back rather than admitting it on the strength of the drain step alone | Manual (reasoning over TS1's asserted text) |
| TS4 | Reason over a workflow.yaml where every task is already `pending`, or there are no tasks | The gate admits route back and the write set is a no-op | Manual (reasoning over TS1's asserted text) |
| TS5 | Inspect the rejected path in Step I.2.c | Exactly one terminal is named — `implement: failed` plus develop Step B stop condition 3 — with no retry, alternative recovery or degraded route back offered for that path | Unit (document assertion) |
| TS6 | Trace the rejected path in the edited prose | No `commit-docs.sh` call and no cleanup step is reachable after the gate rejects; the rejected run leaves worktree and git history untouched | Unit (document-order assertion) + Manual trace |
| TS7 | Search the Branch & Worktree Model section's exit-4 recovery bullet | The I.2.c route-back commit case is absent; the unreachability justification (no `in_progress` task → no running implementer → no concurrent `merge-task.sh` caller) is present alongside the surviving I.1 and I.2.b entries | Unit (document assertion) |
| TS8 | Read the justification text | It ties unreachability to the widened gate rather than to the drain step in isolation, so the gate surface and the model surface do not disagree | Manual (semantic review) |
| TS9 | Inspect the integrated diff's file list | Only `em-workflow/references/implement-phase.md`, `tests/test_implement_routeback_gate.py` and `em-workflow/.claude-plugin/plugin.json` appear; no frozen file and no `marketplace.json` entry | Manual (diff-scope inspection) |
| TS10 | Run `python3 -m unittest discover -s tests` from the repository root | Exit 0, with no test skipped or removed | Integration (command) |
| TS11 | Compare the test module against its pre-change state | Every assertion that pinned the old I.2.c or exit-4 wording was updated in the same change; the module's test method count did not decrease and no `skip` was introduced | Manual (diff review) + Integration (TS10 as the green proof) |

## Code Quality Verification

- Format: not applicable — `project.components.main.format_command` is empty.
- Static analysis: not applicable — no linter is configured, and adding one is
  out of scope (FR5).
- Standing substitute: the repository's existing document-contract suites
  (`tests/test_review_implement_develop_lock_contracts.py`,
  `tests/test_phase_state_doc.py`, `tests/test_reference_sweep.py`,
  `tests/test_check_plugin_invariants.py`) must pass unmodified — they are the
  regression net for prose this feature is not allowed to disturb.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Step I.2.c states the admissibility condition as "no task has status `merged` AND no task has status `in_progress`", and its write set still resets `failed` tasks to `pending` | TS1, plus TS2–TS4 reasoning |
| AC2 | Step I.2.c states that when the condition is not met, `implement` is set to `failed` and the run stops on develop Step B stop condition 3 | TS5 |
| AC3 | Step I.2.c places the gate decision before any `commit-docs.sh` invocation and before route-back cleanup, and says nothing is committed on the rejected path | TS6 |
| AC4 | The Branch & Worktree Model section no longer lists the I.2.c route-back commit among its exit-4 recovery cases and states the unreachability justification in its place | TS7, TS8 |
| AC5 | No new checker, validator rule or script is introduced, and `em-workflow/scripts/validate-worker-output.py`, `em-workflow/references/workflow-patch.md` and `em-workflow/references/contracts/*` are byte-identical to their pre-change content | TS9, TS10 |
| AC6 | `em-workflow/.claude-plugin/plugin.json` reads version `0.1.37` and the root `.claude-plugin/marketplace.json` is unmodified | TS9, plus a direct read of the version field |
| AC7 | `python3 -m unittest discover -s tests` exits 0, including the tests that pin the edited prose | TS10, TS11 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS4 |
| FR2 | task0001 | TS5 |
| FR3 | task0001 | TS6 |
| FR4 | task0001 | TS7, TS8 |
| FR5 | task0001 | TS9, TS10, TS11 |
| FR6 | task0002 | TS9 |
| NFR1 | task0001, task0002 | TS9, TS10 |
| NFR2 | task0001 | TS3 |
| NFR3 | task0001, task0002 | TS10, TS11 |

## E2E Testing

Not applicable — `project.components.main.e2e_test_command` is empty and the
feature changes protocol documents, which have no runtime surface to drive
end to end.

## Manual Testing (E2E Not Possible)

- [ ] TS2 / TS3 / TS4: walk the edited Step I.2.c text against the three
      workflow.yaml states (failed-only, stale `in_progress`, all-`pending` or
      empty) and confirm the documented decision matches the expected one in
      the table above.
- [ ] TS6: read the rejected path top-down and confirm no side-effecting
      instruction (refresh, tip capture, write set, cleanup, `commit-docs.sh`)
      is reachable from it.
- [ ] TS8: confirm the unreachability justification names the widened gate as
      the guaranteeing condition, and that the gate surface and the exit-4
      surface of the document state the same thing.
- [ ] TS9: run a changed-file listing for the integration branch against
      `base_branch` and confirm the three expected paths and nothing else;
      confirm no added file is a checker, validator or script.
- [ ] TS11: diff `tests/test_implement_routeback_gate.py` against its
      pre-change state and confirm no assertion was removed or skipped to
      reach green.
- [ ] AC6: read the `version` field of `em-workflow/.claude-plugin/plugin.json`
      and confirm it is `0.1.37`.

Mockup visual comparison is not applicable — the design step is `skipped`
(ASM6); this feature has no visual surface.

## Performance / Security Verification (if applicable)

Not applicable — SPEC.md declares no performance and no security requirement,
and the change adds no executable behavior.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1–TS11) | 11 | 5 (TS1, TS5, TS6, TS7, TS10) | 0 | 6 (TS2, TS3, TS4, TS8, TS9, TS11) |
| Success criteria (AC1–AC7) | 7 | 4 (AC1, AC2, AC3, AC7) | 0 | 3 (AC4 partial, AC5, AC6) |
| Requirements (FR1–FR6, NFR1–NFR3) | 9 | 9 covered | 0 | — |
