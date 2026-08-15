# Verification Document: recycled-task-id-consistency

## Overview

**Feature**: recycled-task-id-consistency
**SPEC.md**: `feature-docs/recycled-task-id-consistency/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/recycled-task-id-consistency/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged result. Per-task
acceptance criteria live in `tasks/task0001.md`, `tasks/task0002.md` and
`tasks/task0003.md`.

## Build Verification

- Command: none. `workflow.yaml` `project.components.main.build_command` is
  empty — the deliverables are Markdown, JSON and Python test modules, and the
  repository has no build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository root
  (the integration worktree root during verification).
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: not applicable — the project has no coverage tooling and no
  runtime code is added. The equivalent measure here is requirement coverage:
  every FR/NFR maps to at least one scenario below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Normalized `### I.2.b` section: step 3's `failed` write-back names step 1's reconciled state | Reconciled-state phrasing present; "for every task whose last journal event is `failed`" absent; `merged` half and report clause retained | Unit |
| TS-2 | I.2.a's normative statement and I.2.b step 1's citation | "Recycled task id: workflow.yaml's status wins over a stale journal event here" present; "the recycled-task-id rule in I.2.a above" present | Unit |
| TS-3 | Normalized I.2.c: the route-back precondition | Precondition names a terminal journal last event with both `merged` and `failed`; its index precedes that of "`create-plan` to `needs_update`"; "no task has status `merged`" still present | Unit |
| TS-4 | Normalized I.2.c: the inapplicable branch | States `implement` stays `failed`, cites stop condition 3 / "abort phase"; the whole section contains neither `rework` nor `append` | Unit |
| TS-5 | Normalized I.2.a slice: the unreachability sentences | Mention the planner renumbering (`replace_all`) together with `launched` and `pending`; the retained in-flight sentence still present | Unit |
| TS-6 | The orchestrator-only scope sentence | Names all four hook filenames and the "never consults `tasks.{T}.status`" claim; the document nowhere contains "never read workflow.yaml" | Unit |
| TS-7 | RAW regression: the two line-wrap-sensitive literals (`Select` / `unlaunched tasks (...` and `require at least one task in `tasks` whose` / `` `status == pending` ``) | Both present verbatim, the Step I.0 one earlier in the file than the Step I.2.a one; failure message names the wrap | Unit (regression) |
| TS-8 | RAW regression: the I.2.b commit literal | `"docs({feature}): implement wake` + newline + three-space indent + `phase reconcile" "$RECONCILE_TIP"` present verbatim | Unit (regression) |
| TS-9 | Byte identity of the I.2.c heading and the batch-mode paragraph | Heading byte-identical; the batch-mode paragraph is still the byte-identical tail of the I.2.c section | Unit (regression) |
| TS-10 | Normalized I.2.c intra-section orderings | First `tasks.{T}.status` has `pending` within 60 characters; the four write tokens precede `git worktree remove --force`; cleanup precedes the first `commit-docs.sh`, which precedes `End the phase with a` | Unit (regression) |
| TS-11 | Both registries report `0.1.38` for em-workflow, and `implement-phase.md` has no bare `git commit` / `git add -A` line | `plugin.json` `version` is `0.1.38`; the `em-workflow` marketplace entry is `0.1.38`; the `em-review` entry carries no `version`; zero bare git commit/add lines | Unit |
| TS-12 | Change containment: `git diff --name-only` against the implement baseline commit | Every path is inside {`em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `feature-docs/recycled-task-id-consistency/**`, `test-docs/recycled-task-id-consistency/**`, new modules under `tests/`}; no path under `feature-docs/implement-routeback-gate/`, `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`; no pre-existing `tests/` module modified | Manual (inspection) |
| TS-13 | SSOT non-duplication and local style of the edited prose | The added text cites `references/workflow-patch.md`, `skills/develop/SKILL.md` Step B's stop-condition-3 precedence clause and the "Supporting cast" inventory rather than restating them; exactly one normative statement of the recycled-task-id rule remains; English prose, backtick conventions and bullet structure match the surroundings | Manual (inspection) |
| TS-14 | Negative-proof coverage of the new matchers | Each new matcher in both new modules has at least one test demonstrating that it flags the corresponding pre-change wording | Manual (inspection over the merged test modules) |
| TS-15 | Negative proofs for the eight new-wording matchers of `tests/test_recycled_task_id_consistency.py` (AC-1's reconciled-state phrasing, AC-4's three INAPPLICABLE-branch matchers, AC-5's unreachability sentence, AC-6's three scope-sentence matchers) | For each of the eight, a named negative-proof test applies the module's whitespace-normalizing helper to a captured pre-change sample and shows the matcher does not match it; each sample is guarded by a retained-anchor assertion so the proof cannot be vacuous; the positive test and its proof share one module-level constant per matcher | Unit |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty — the
  repository defines no formatter.
- Static analysis: none configured. The document-contract suite is the standing
  static check over the protocol documents and registries.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1–FR9 are implemented and covered by SPEC.md AC-1 .. AC-12 | Requirements coverage table below; TS-1 .. TS-6, TS-11, TS-12 |
| SC-2 | All test scenarios TS-1 .. TS-11 pass | `python3 -m unittest discover -s tests` exits 0 |
| SC-3 | The suite passes with the six enumerated pre-existing modules unmodified | TS-12 confirms they are unmodified; the suite run confirms they pass |
| SC-4 | The change stays inside FR8's declared file set and lists no path under `feature-docs/implement-routeback-gate/` | TS-12 |
| SC-5 | Both registries read version `0.1.38` for em-workflow | TS-11 |
| SC-6 | Every new matcher has a negative-proof test | TS-15 (automated, for the eight new-wording matchers task0003 covers), then TS-14 (inspection confirming the module's inventory names a proof or a documented exemption for every remaining matcher) |
| SC-7 | Exactly one normative statement of the recycled-task-id rule remains, and rules owned elsewhere are cited rather than restated | TS-2, TS-13 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-6 |
| FR7 | task0001, task0002 | TS-12 (no path under `feature-docs/implement-routeback-gate/`; this feature's REQUIREMENTS.md and SPEC.md carry the requirements, ACs and scenarios) |
| FR8 | task0001, task0002, task0003 | TS-12 |
| FR9 | task0002 | TS-11 |
| NFR1 | task0001, task0002, task0003 | TS-7, TS-8, TS-9, TS-10, TS-11, plus the full-suite run with the six protected modules unmodified (TS-12) |
| NFR2 | task0001 | TS-13 |
| NFR3 | task0001, task0002, task0003 | TS-12 (no path under `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`) |
| NFR4 | task0001 | TS-13 |
| NFR5 | task0001, task0002, task0003 | TS-1 .. TS-11 exist as `unittest` modules discovered by the single project command; TS-15; TS-14 |

## E2E Testing

Not applicable. The repository has no E2E infrastructure and
`project.components.main.e2e_test_command` is empty. Every automatable scenario
is a document-contract assertion inside the `unittest` suite.

## Manual Testing (E2E Not Possible)

- [ ] TS-12: run `git diff --name-only` for the integrated change against the
      implement baseline commit and confirm the path set matches FR8's declared
      set exactly, with no pre-existing `tests/` module and no
      `feature-docs/implement-routeback-gate/` path listed.
- [ ] TS-13: read the edited I.2.a / I.2.b / I.2.c passages and confirm the rule
      is stated normatively once, that the other sites cite it, that
      `workflow-patch.md` / `develop/SKILL.md` / the "Supporting cast" inventory
      are cited rather than restated, and that the prose matches the surrounding
      style.
- [ ] TS-14: read both new test modules and confirm every new matcher has a
      negative-proof test against pre-change wording. After task0003, this is a
      lookup against the matcher → negative-proof inventory in
      `tests/test_recycled_task_id_consistency.py`'s docstring: confirm the
      inventory lists every matcher in the module, and that each entry names
      either a negative-proof test or a documented exemption (retention matcher
      or regression guard). TS-15 covers the eight entries automatically.
- [ ] Read the merged I.2.c section end-to-end and confirm the route-back
      precondition, the inapplicable branch and the existing merged-task branch
      describe three mutually exclusive outcomes with no partial-write path
      between them.

## Performance / Security Verification

Not applicable. Documentation-only change (NFR3): no executed behaviour changes,
no runtime surface, no data stored or transmitted.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 15 | 12 (TS-1 .. TS-11, TS-15) | 0 | 3 (TS-12 .. TS-14) |
| Success criteria | 7 | 5 | 0 | 2 |
| Requirements (FR + NFR) | 14 | 14 (each maps to ≥ 1 scenario) | 0 | — |
