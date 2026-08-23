# Verification Document: goal-vs-spec-divergence

## Overview

**Feature**: goal-vs-spec-divergence
**SPEC.md**: `feature-docs/goal-vs-spec-divergence/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/goal-vs-spec-divergence/IMPLEMENTATION.md`

This document defines the INTEGRATED verification run after every task has
merged. Per-task acceptance criteria live in `tasks/taskNNNN.md` and are not
repeated here.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. The
  deliverables are Markdown, YAML and JSON documents plus Python test
  modules; there is no build step.
- Expected: not applicable. The manifests' JSON validity is covered by TS-9.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: line coverage is not measured (no coverage tooling, and
  the units under test are documents). The equivalent target is
  **scenario coverage**: every scenario below is pinned by at least one
  module under `tests/`, and every requirement maps to at least one scenario.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Scan `workflow-schema.md` and `create-spec-phase.md` for the `goal` block's definition, verbatim-storage, single-writer, immutability and untrusted-handling statements | All statements present; the schema states the block is optional and never backfilled | Unit |
| TS-2 | Scan `workflow-patch.md`'s `replace_all` permission conditions and `rework-task-synthesis.md`'s SPEC-change transition together | The `needs_update` path permits merged tasks, `in_progress`/`failed` are still protocol errors, `base_commit` preservation is stated, and the superseded wording is absent from both documents | Unit |
| TS-3 | Scan for the classification gate's batch-only restriction, two-directional question, asymmetry and evidence criterion | All four present in `question-resolution.md`; interactive stated as unchanged | Unit |
| TS-4 | Retention pin: `question-resolution.md` still aborts immediately for `category: security`, `category: license` and `reversible: false`, and the spec-change arm is routed instead | Three abort arms intact with their non-overridable clauses; spec-change arm routed; `batch-policies.yaml`'s header consistent | Unit |
| TS-5 | Scan for the Codex-absent self-classification route and the audit record's fields | Route defined with the same asymmetry and evidence criterion; `classifier` / `verdict` / `evidence_ids` / `decision` / `reason` defined in `phase-state.md` | Unit |
| TS-6 | Scan for all three eligibility conditions of the wording-correction route | No planner re-entry, plan/task metadata unchanged, requirement metadata unchanged — stated conjunctively, with the fallback to the normal route | Unit |
| TS-7 | Scan the analyst-side investigation procedure for referenced-side scanning | The request flag, the result field (test files included) and the orchestrator-resolves-paths discipline are all stated; no self-discovery is implied | Unit |
| TS-8 | Scan the declared-change-set derivation, the retained containment check, and — by the same method as the existing invariant module — the absence of any verify-side exclusion rule | Derivation defined as tasks' `files` ∪ default entries, guard status stated, containment retained, zero exclusion-rule offenders | Unit |
| TS-9 | Compare the em-workflow version in `plugin.json` and `marketplace.json` | Both parse, are equal, and are strictly greater than the pre-change baseline | Unit |
| TS-10 | Run the entire suite, including every pre-existing document-pin module | Full suite green; no guard deleted | Unit (full suite) |
| TS-11 | Retention pin for Codex-output handling: read-only, never executed, never adopted verbatim; the consultation procedure's probe / wrapper / turn ceiling / decision-stays-with-Claude mechanics unchanged | All present; the gate introduces no second, laxer statement | Unit |
| TS-12 | SSOT discipline: the `goal` block is defined in exactly one document; the default-entry enumeration's carrier set is unchanged (or updated in the same edit); no rule gains a second home | No duplicate definition; carrier scan reports no unexpected carrier | Unit |
| TS-13 | Every new stop path states that its reason and evidence are recorded, and no new batch statement raises a confirmation nobody can answer | Present for the gate's stops, the inapplicable case, and the rejected deviation | Unit |
| TS-14 | Codex independence: every capability of the gate is stated to hold without Codex | The Codex-absent route carries the same verdicts, asymmetry and evidence criterion; no capability is conditioned on Codex being installed | Unit |
| TS-15 | Traceability: every FR1–FR19 has at least one task and at least one test in `workflow.yaml`'s requirements mapping, and every listed ID exists | No requirement with an empty `tasks` or `tests` array except FR20's own entry, which carries both | Manual / integrated |
| TS-16 | Every test module added by this feature is discovered by the run command and imports only the standard library | Discovery finds each new module; no third-party import | Unit |
| TS-17 | Scan for the goal-absent inapplicability rule (FR20 / assumption A-6) | `question-resolution.md` states the gate is inapplicable without a `goal` block, the run stops as before, no backfill occurs, and the stop reason records the inapplicability; `workflow-schema.md` states the block is optional | Unit |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty. Markdown
  and YAML are hand-formatted; the wrap width and heading style of each
  edited document follow that document's existing conventions.
- Static analysis: none configured. The document-pin modules under `tests/`
  serve this role for the protocol documents.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1–FR19 implemented and covered by the scenarios above (FR20 resolved as an assumption) | TS-1 … TS-8, TS-11 … TS-14, TS-17; requirements mapping check TS-15 |
| SC-2 | AC-1 … AC-11 of the user stories satisfied | Read each user story's acceptance criterion against the merged documents; each maps to the scenarios above |
| SC-3 | `python3 -m unittest discover -s tests` passes in full | TS-10 |
| SC-4 | Fail-closed strength for security / license / `reversible: false` unchanged | TS-4 (retention pin), reviewed as a security item |
| SC-5 | Existing `tests/` modules green or updated consistently, no guard deleted | TS-10 plus a diff review of every pre-existing module touched: each change must be traceable to an intended document change |
| SC-6 | Both manifests carry the same raised version | TS-9 |
| SC-7 | Documents cite existing SSOTs rather than restating rules | TS-12, reviewed as an architecture item |
| SC-8 | FR1–FR19 delivered as one feature without splitting | TS-15 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0007 | TS-1 |
| FR2 | task0001, task0007 | TS-1 |
| FR3 | task0001, task0004 | TS-1 |
| FR4 | task0002 | TS-2 |
| FR5 | task0002 | TS-2 |
| FR6 | task0003 | TS-2 |
| FR7 | task0004 | TS-3 |
| FR8 | task0004 | TS-3 |
| FR9 | task0004 | TS-3 |
| FR10 | task0004 | TS-3 |
| FR11 | task0004, task0006 | TS-4 |
| FR12 | task0004 | TS-11 |
| FR13 | task0004 | TS-5 |
| FR14 | task0004, task0005 | TS-5 |
| FR15 | task0003 | TS-6 |
| FR16 | task0003 | TS-6 |
| FR17 | task0007, task0008 | TS-7 |
| FR18 | task0009 | TS-8 |
| FR19 | task0010 | TS-8 |
| FR20 | task0001, task0004, task0007 | TS-17 |
| NFR1 | task0001 … task0010 | TS-12 |
| NFR2 | task0004, task0006 | TS-4 |
| NFR3 | task0004, task0005, task0010 | TS-13 |
| NFR4 | task0004 | TS-14 |
| NFR5 | task0001 … task0011 | TS-16 |
| NFR6 | task0011 | TS-9 |
| NFR7 | task0001 … task0011 | TS-15 |
| NFR8 | task0001 … task0011 | TS-10 |

## E2E Testing

No E2E framework exists in this repository
(`project.components.main.e2e_test_command` is empty), and this feature
introduces no runtime surface to drive. Omitted deliberately.

## Manual Testing (E2E Not Possible)

- [ ] MV-1 (TS-15): read `workflow.yaml`'s requirements mapping after the
      integrated merge and confirm every FR1–FR19 entry has a non-empty
      `tasks` and `tests` array, and that every referenced task ID and
      scenario ID exists.
- [ ] MV-2 (SC-5): review the diff of every pre-existing module under
      `tests/` that a task modified, confirming each change tracks an
      intended document change rather than relaxing a guard.
- [ ] MV-3 (SC-7): read the merged documents for duplicated rules — the
      `goal` block, the classification gate's verdicts, the declared-change-set
      default entries and the containment semantics must each have exactly one
      home, with every other mention a citation.
- [ ] MV-4: confirm no file outside SPEC.md's Declared Change Set was
      modified — in particular nothing under `em-workflow/scripts/**`,
      `em-workflow/hooks/**`, or another feature's `feature-docs/**`.
- [ ] MV-5 (SC-4): read the merged `question-resolution.md` end to end and
      confirm the classification gate cannot be reached from the security,
      license or irreversible-operation arms by any path.

Mockup visual comparison is not applicable: the design step is `skipped` for
this feature and no design artifact exists.

## Performance / Security Verification

- **Performance**: no performance requirement is stated; no threshold to
  check.
- **Security — fail-closed retention (NFR2)**: TS-4 plus MV-5. The three
  immediate-abort arms must be individually present with their
  non-overridable clauses intact.
- **Security — untrusted data (FR3, FR12)**: TS-1 and TS-11. The goal text
  and Codex output must be stated as data to read, never as instructions to
  follow, at every site that consumes them.
- **Security — scope containment (FR19)**: TS-8. The containment check must
  still stop unjustified scope expansion, and no exclusion rule may subtract
  workflow-generated artefacts from the observed change set.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 17 | 16 | 0 | 1 (TS-15) |
| Success criteria | 8 | 5 | 0 | 3 (SC-2, SC-5, SC-7) |
| Manual verification | 5 | 0 | 0 | 5 |
| Security items | 3 | 3 | 0 | 1 overlap (MV-5) |
