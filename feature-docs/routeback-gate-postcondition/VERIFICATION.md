# Verification Document: routeback-gate-postcondition

## Overview

**Feature**: routeback-gate-postcondition /
**SPEC.md**: `feature-docs/routeback-gate-postcondition/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/routeback-gate-postcondition/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, run after
every task has merged into the integration branch. Task-level acceptance
criteria live in `tasks/task0001.md` through `tasks/task0005.md`.

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
| TS9 | Inspect the integrated diff's file list (paths under `feature-docs/` excluded — they are this feature's own planning documents, not its change surface) | The only implementation paths are `em-workflow/references/implement-phase.md`, `tests/test_implement_routeback_gate.py` and `em-workflow/.claude-plugin/plugin.json`; alongside them the diff carries exactly one `test-docs/routeback-gate-postcondition/{taskNNNN}.tests.yaml` evidence record per task registered in `workflow.yaml` and no other `test-docs/` path; no frozen file and no `marketplace.json` entry appears | Manual (diff-scope inspection) |
| TS10 | Run `python3 -m unittest discover -s tests` from the repository root | Exit 0, with no test skipped or removed | Integration (command) |
| TS11 | Compare the test module against its pre-change state | Every assertion that pinned the old I.2.c or exit-4 wording was updated in the same change; the module's test method count did not decrease and no `skip` was introduced | Manual (diff review) + Integration (TS10 as the green proof) |

### Rework Round 1 Scenarios (review-sourced)

Added by the round-1 rework for tasks task0003 / task0004. Every scenario
above (TS1–TS11) stands unchanged; these state the additional postconditions
the rework introduces. Where a rework postcondition narrows the scope of an
earlier scenario's expected result, the scenario below is the precise
statement to verify against — see the note after the table.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS12 | Read Step I.2.c's rejected path in `em-workflow/references/implement-phase.md` | The path sets the `implement` step to `failed` in workflow.yaml and commits that single write via `commit-docs.sh`; no "stays `failed`" formulation remains; develop Step B stop condition 3 is still the named halt; the scope sentence states that no route-back write set, no worktree/branch cleanup and no route-back commit occur and that the terminal write plus its own commit is the only side effect | Unit (document assertion) + Manual trace |
| TS13 | Compare the exit-4 recovery statements in `em-workflow/references/implement-phase.md`, `em-workflow/scripts/commit-docs.sh` (RECOVERY CONTRACT header) and `em-workflow/skills/develop/SKILL.md` (exit-4 paragraph) | All three state the same carve-out and all three name Step I.2.c's route-back commit as its only site; the phase's enumeration also binds Step I.2.c's rejected-path terminal status commit; the proof enumerates the paths that can advance the integration branch ref and names the residual assumption plus its terminal; the route back's order is write set → commit → cleanup so the stop-with-report terminal is reached with nothing deleted | Unit (document assertion) + Manual (semantic review) |
| TS14 | Reason over a workflow.yaml whose task row reads `pending` while the journal's last event for that task is `launched` (a live implementer the status does not reflect) | The documented gate blocks route back: its `in_progress` half is the union of the workflow.yaml status and Step I.2.b's last-event-per-task in-flight rule, cited to Step I.2.b as owner, and either source alone blocks | Manual (reasoning over TS13's and TS1's asserted text) |
| TS15 | Load `test-docs/routeback-gate-postcondition/task0001.tests.yaml` and `task0002.tests.yaml` | Every `acceptance_tests` entry in both files carries `tests`, `red_confirmed` and `red_reason`; `task0001` AC-6 and AC-7 read `red_confirmed: false`; no `red_reason` text and no `tests` list changed | Manual (record inspection) |
| TS16 | Inspect the integrated diff's file list after every rework round (paths under `feature-docs/` excluded, as in TS9) | It adds exactly two implementation paths to TS9's three — `em-workflow/scripts/commit-docs.sh` and `em-workflow/skills/develop/SKILL.md` — and no other implementation path; the `test-docs/routeback-gate-postcondition/` half of the diff is exactly one `{taskNNNN}.tests.yaml` record per task registered in `workflow.yaml`, with no record for an unregistered task and none missing; `em-workflow/scripts/validate-worker-output.py`, `em-workflow/references/workflow-patch.md` and `em-workflow/references/contracts/*` are byte-identical; the root `.claude-plugin/marketplace.json` is unmodified; `em-workflow/.claude-plugin/plugin.json` still reads `0.1.37`; no new checker, validator rule, script or test module was added, and `commit-docs.sh`'s diff contains comment lines only | Manual (diff-scope inspection) |

**Scope notes for TS6 and TS9 after the rework** (neither scenario is
rewritten; these state how each is read against the reworked documents):

- TS6's "no `commit-docs.sh` call and no cleanup step is reachable after the
  gate rejects" is verified against the rejected path's *route-back* side
  effects, which is what FR3/AC3 constrain: no route-back write set, no
  cleanup and no route-back commit. The single `implement: failed` status
  write and its own commit — the terminal FR2/AC2 require, which cannot exist
  unpersisted — is the one side effect that path has, and TS12 is the precise
  statement of it. TS6's cleanup half is unchanged and still holds absolutely.
- TS9's three-path list is the pre-rework *implementation* scope. TS16 states
  the post-rework implementation list; TS9's substance (no frozen file, no
  `marketplace.json` entry, no new checker/script) is carried into TS16
  unchanged.
- **Per-task evidence records are structural, not scope creep** (restated in
  rework round 2; see that section below). `agents/implementer.md` obliges
  EVERY task to write `test-docs/{feature}/{taskNNNN}.tests.yaml`, so one such
  record per registered task is guaranteed to appear in the integrated diff and
  can never be absent. Both TS9 and TS16 therefore state that half of the file
  list as a per-task rule rather than as a fixed enumeration: what they
  constrain is that no OTHER path appears, and that the record set matches the
  task set exactly. A file-count expectation that omits these records is a
  defect in the scenario, not evidence of an out-of-scope change.

### Rework Requirements Coverage

| Requirement | Rework task | Verification |
|-------------|-------------|--------------|
| FR1 | task0003 | TS14 |
| FR2 | task0003 | TS12 |
| FR3 | task0003 | TS12 |
| FR4 | task0003 | TS13 |
| FR5 | task0003 | TS16 |
| NFR1 | task0003 | TS16 |
| NFR2 | task0003 | TS14 |
| NFR3 | task0003, task0004 | TS15, TS16, plus TS10's command run |

### Rework Manual Testing

- [ ] TS12: read Step I.2.c's rejected path top-down and confirm the only
      side-effecting instruction it reaches is the `implement: failed` write
      and its commit — no refresh for a route back, no tip capture for one, no
      write set, no cleanup.
- [ ] TS13: read the three exit-4 statements side by side and confirm no
      reader could derive a different obligation depending on which document
      they opened first.
- [ ] TS14: walk the gate text against a workflow.yaml / journal pair that
      disagree, in both directions, and confirm the union blocks in both.
- [ ] TS15: load both `tests.yaml` records and diff their key sets per entry.

- [ ] TS16: run a changed-file listing for the integration branch against
      `base_branch`, drop the `feature-docs/` paths, and confirm the five
      expected implementation paths plus exactly one
      `test-docs/routeback-gate-postcondition/{taskNNNN}.tests.yaml` per task in
      `workflow.yaml` — and nothing else.

### Rework Round 2 Scenarios

Added by the round-2 rework for task0005. Every scenario above (TS1–TS16)
stands and none is rewritten.

**Scope note for TS15** (the scenario is not rewritten; this states how it is
read after round 2): TS15's "no `red_reason` text and no `tests` list changed"
clause is scoped to the round-1 change it was written for — task0004's addition
of `red_confirmed` keys to `task0001.tests.yaml`. Round 2's task0005 re-points
stale method names inside that record's `tests` lists, which TS18 is the precise
statement of; TS15's key-set half (every entry in `task0001.tests.yaml` and
`task0002.tests.yaml` carries all three keys, `task0001` `AC-6`/`AC-7` reading
`red_confirmed: false`) is unchanged and still holds absolutely, and TS17
restates it over every record.

**Two scenarios above were restated in this round, with their substance
untouched.** The verify round failed TS9 and TS16 on their expected file lists
only: both enumerated a fixed set that omitted the per-task
`test-docs/{feature}/{taskNNNN}.tests.yaml` evidence records the implementer
contract mandates for EVERY task. Those records are structurally guaranteed to
be in the diff, so the enumeration — not the shipped change — was the defect.
Each scenario's expected file list is now stated as a per-task rule (see the
scope notes above); every substantive clause of both scenarios is carried over
verbatim and stays checkable: frozen-file byte-identity, `marketplace.json`
unmodified, `plugin.json` reading `0.1.37`, `commit-docs.sh`'s diff
comment-only, and no new checker, validator rule, script or test module.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS17 | Load every `test-docs/routeback-gate-postcondition/{taskNNNN}.tests.yaml` record present in the integration branch | Every entry under `acceptance_tests` in every record carries all three keys `tests`, `red_confirmed` and `red_reason`, with `red_confirmed` a YAML boolean — no entry omits one; in particular `task0003.tests.yaml`'s `AC-7` and `AC-8` read `red_confirmed: false`; every `red_reason` string and every `red_confirmed` value in every record is otherwise unchanged by this round, and the only `tests` list that changed is the method-name re-pointing TS18 states | Manual (record inspection) |
| TS18 | Resolve every test method name referenced from `test-docs/routeback-gate-postcondition/task0001.tests.yaml` against the current `tests/test_implement_routeback_gate.py` | Every referenced method name is defined in that module; every Acceptance Criterion that carried a non-empty `tests` list before this round still carries a non-empty one afterwards (no entry was emptied to reach resolvability); the `red_confirmed` values and `red_reason` texts of that record are unchanged | Manual (record inspection + name resolution) |

#### Rework Round 2 Requirements Coverage

| Requirement | Rework task | Verification |
|-------------|-------------|--------------|
| NFR3 | task0005 | TS17, TS18, plus TS10's command run |

#### Rework Round 2 Manual Testing

- [ ] TS17: load every `tests.yaml` record under
      `test-docs/routeback-gate-postcondition/` and compare the key set of each
      `acceptance_tests` entry against the three mandated keys; confirm the two
      repaired `task0003` entries read `red_confirmed: false` and that the diff
      for the record adds `red_confirmed` lines only.
- [ ] TS18: list the method names defined in
      `tests/test_implement_routeback_gate.py`, list the names referenced by
      `task0001.tests.yaml`, and confirm the second set is a subset of the
      first; then confirm no criterion's `tests` list went from non-empty to
      empty.

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
      `base_branch`, drop the `feature-docs/` paths, and confirm the three
      expected implementation paths plus one
      `test-docs/routeback-gate-postcondition/{taskNNNN}.tests.yaml` per task in
      `workflow.yaml` — and nothing else; confirm no added file is a checker,
      validator or script.
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
| Rework scenarios (TS12–TS18) | 7 | 2 (TS12, TS13) | 0 | 5 (TS14, TS15, TS16, TS17, TS18) |
| Success criteria (AC1–AC7) | 7 | 4 (AC1, AC2, AC3, AC7) | 0 | 3 (AC4 partial, AC5, AC6) |
| Requirements (FR1–FR6, NFR1–NFR3) | 9 | 9 covered | 0 | — |
