# Verification Document: task-tier-reduction

## Overview

**Feature**: task-tier-reduction /
**SPEC.md**: `feature-docs/task-tier-reduction/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/task-tier-reduction/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged into the integration branch. Task-level criteria live in the thirteen
task plans under `feature-docs/task-tier-reduction/tasks/` — the original
eight, plus task0009 … task0013 synthesized from review round 1.

## Build Verification

- Command: none — `workflow.yaml`'s `project.components.main.build_command`
  is empty (AS-8: this repository has no build step).
- Expected: not applicable. Recorded as "no build step" rather than skipped
  silently.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, zero failures and zero errors.
- Baseline: the pre-change failure set recorded at the integration branch's
  base commit. A post-change failure counts only if it is not in that set.
- Coverage target: not measured — this repository configures no coverage
  tooling, and none is added by this feature.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The reason-code table assertion in `tests/test_failed_kind_batch_docs.py` is updated to include the new code | The module passes, and its negative proof still detects both an added and a removed code | Integration |
| TS-2 | The stop-point coverage row count and key-count assertions in `tests/test_batch_quiet_output_discipline.py` are updated from their current value | The module passes, and its forbidden-literal checks still cover every reason code including the new one | Integration |
| TS-3 | `tests/test_structured_result_conformance.py` and `tests/test_structured_result_consumer_constraints.py` extract the reason codes from the owning table rather than from a literal list | Both modules pass unmodified after the new code lands (regression confirmation only) | Integration |
| TS-4 | A structured result carrying the stopped state, the new reason code, the no-step sentinel and non-empty resume guidance is checked against the consumer-constraint rules | The result is accepted; a variant with empty resume guidance is rejected | Unit |
| TS-5 | A `workflow.yaml` whose non-design step carries the skipped status with a skip reason is read by the develop loop's step-selection rule | Not treated as a YAML error; the skipped step is passed over and the next non-terminal step is selected | Integration |
| TS-6 | A single-task planning patch with an empty requirement map and an empty per-task requirement list is validated by `em-workflow/scripts/validate-worker-output.py` | Validation passes; the task entry still carries every mandatory field including complexity | Integration |
| TS-7 | A develop-driven review round is selected with no spec document present | The floor drops the spec perspective and records a skip notice; the security and comprehensive perspectives remain in the floor | Integration |
| TS-8 | A run interrupted before `workflow.yaml` was created is resumed, and the persisted tier decision is transcribed again | The tier is restored from phase-state, and a re-transcription never lowers a tier already recorded in `workflow.yaml` | Integration |
| TS-9 | Each combination of Jev unavailable (any non-zero exit status) and Codex unavailable is evaluated | Every combination the fallback matrix marks unusable resolves to the tier that removes nothing | Unit |
| TS-10 | The threshold evaluation is called with observed values covering all three rows | First bucket 0.81 with the clarity member 0.6 gives `minimal`; first bucket 0.50 with second bucket 0.40 gives `reduced`; first bucket 0.37 with second bucket 0.59 gives `full`, caught by the first-bucket floor of 0.40 despite summing to 0.96 | Unit |
| TS-11 | `references/tier-rules.yaml` exists, and every document naming it names a path that resolves; the plugin invariant checker is run unchanged | The path resolves for every reference; the checker exits 0 | Integration |
| TS-12 | The workflow schema document defines the tier field and the decision block with its four sub-fields | Both are defined, and the schema's worked example carries them | Integration |
| TS-13 | The Step A decision procedure is read for its external-invocation contract | It names the readonly Codex wrapper and never the raw Codex subcommand; it names the Jev skill with its JSON input and output switches; it merges the estimate into the Jev state and records both decision bases; it reproduces no text from either external skill | Integration |
| TS-14 | The terminal-line contract's responsibility-boundary section is compared against its pre-change text | Byte-identical: no external task-management service operation is introduced | Integration |
| TS-15 | The reduction table is read for each tier's subtractions and for what every tier keeps | `reduced` and `minimal` subtract exactly the documented artifacts; the full test suite, the Step 0 git-setup gate and the integration worktree appear as kept in every tier, and no text anywhere subtracts the integration worktree | Integration |
| TS-16 | The upgrade procedure is read | Upgrading is expressed only as skipped becoming pending; no new status value is introduced; the completed create-spec re-execution step is present; the automatic-re-entry carve-out enumerates three transitions and its exhaustiveness sentence matches that count | Integration |
| TS-17 | The retrospect record's shape is read | It carries the decided tier, the decision rationale, the Jev probability values and the Codex estimate | Integration |
| TS-18 | The plugin is scanned for gate identifiers introduced by this feature | None is introduced, and the invariant checker's bidirectional gate-identifier check passes in both directions | Integration |
| TS-19 | The rework path is read for the minimal case | The behaviour when the verification document is absent is stated, and the rework validator's scenario-novelty check has a defined outcome for that case | Integration |
| TS-20 | The decision procedure is read for the standalone route | The same rules apply when the run starts from a `workflow.yaml` with no external task service involved; no branch conditions on the presence of that service | Integration |
| TS-21 | Both distribution manifests are parsed, and every module under `tests/` is scanned for a literal major/minor assertion | The manifests carry the same version string, strictly greater than the pre-change value under per-component numeric comparison with the minor component raised and the major unchanged; no module pins the major/minor pair against a literal; the other plugin's entry is unchanged | Unit |
| TS-22 | The decision path and the stop path are scanned for user-facing gates | No gate identifier and no user-question call is introduced on either path; a batch run needs no new policy entry to pass through them | Integration |
| TS-23 | Every test module added by this feature is inspected | Each is discovered by the suite command, lives under `tests/` with the `test_` prefix, and imports only standard-library modules | Unit |
| TS-24 | The Step A bootstrap order is read across the develop skill and the create-spec phase protocol | The integration branch/worktree is secured after the no-work stop check and before the tier record is written and committed; the phase protocol reuses that worktree and names the single case in which it creates one itself; the two documents yield exactly one ordering | Integration |
| TS-25 | A single-task patch whose entry's `plan` names a real two-section task document is validated the way the create-plan phase invokes the validator, against a feature directory holding that document | No error is reported; the files reconciliation and the Acceptance Criteria presence check are not applied; path containment, symlink rejection, existence and the size limit still are; an entry naming an ordinary task plan still fails on a file-set mismatch and on a missing Acceptance Criteria section | Integration |
| TS-26 | The tier upgrade procedure is read for its re-entry preconditions | Both branches write and commit the re-entry/re-planning authorization record — with its origin pair taken from the trigger — before any step status is set; the `reduced`→`full` branch re-runs create-spec, then design, then create-plan; the requirements document is attributed to create-spec's subtraction and the implementation plan to create-plan's; the carve-out's tier-upgrade entry covers both re-entries and its stated count equals the number of transitions listed | Integration |
| TS-27 | The evaluator is called with a rules table carrying an unrecognized row that declares thresholds, with a declared threshold member whose observation is absent or renamed, with non-finite and out-of-unit-interval observations, and with two readings resolving to different tiers | No case is adopted without its declared comparisons being evaluated; every malformed or out-of-range case and every disagreement yields the tier that removes nothing with a reason naming the offending member; the emitted result carries no non-finite token; the process exits 0 | Unit |
| TS-28 | The tier-decision record and its two projections are read | One document owns the mapping from the persisted record's fields to the decision block's four sub-fields and to the retrospect signal, and the other two cite it; the subtraction list is a projection of the tier through the reduction table; every basis identifier resolves to a rules-file decision-basis value; the persisted record's path reads `feature-docs/{feature}/phase-state/tier.yaml` everywhere | Integration |

**Note on TS-10.** SPEC's earlier threshold rows made TS-10's second case
(first bucket 0.37, second bucket 0.59, expected `full`) yield `reduced`,
because the pair sums to 0.96. FR4 has since been amended with a first-bucket
floor of 0.40 for `reduced`, so all three of TS-10's cases now hold exactly as
SPEC states them and no substitute values are needed. See IMPLEMENTATION.md,
Resolved Questions.

## Code Quality Verification

- Format: none — `format_command` is empty in `workflow.yaml` (AS-8).
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  run from the repository root. Expected: every check reports PASS and the
  process exits 0.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The rules file exists and holds the Jev questions, the thresholds and the Codex output schema | TS-11, plus reading the file for its three top-level groups |
| AC-2 | The workflow schema defines the tier field and the decision block's four sub-fields | TS-12 |
| AC-3 | The status semantics admit a non-design skipped step, and the develop skill's turn-ending condition, Step B discipline, Step C entry condition and completion table agree | TS-5, TS-15 |
| AC-4 | Thresholds are taken from the probability members, and no confidence-only threshold is written anywhere | TS-10, plus a repository-wide absence check for a confidence-only threshold |
| AC-5 | The reason-code table gains one row, the coverage table gains the matching row, and the prose stating the set size is updated | TS-1, TS-2, TS-3 |
| AC-6 | The new stop satisfies the stopped state, the no-step sentinel and non-empty resume guidance | TS-4 |
| AC-7 | The two reduced tiers' subtractions are documented and the create-plan preconditions are tier-aware | TS-15, TS-6 |
| AC-8 | The minimal tier's empty requirement map and its single task-document task are documented as legitimate | TS-6 |
| AC-9 | The develop-driven route drops the spec perspective with a skip notice when the spec document is absent | TS-7 |
| AC-10 | Upgrading is expressed only as skipped becoming pending; the completed create-spec re-execution and the carve-out update are present | TS-16 |
| AC-11 | Nothing anywhere subtracts the integration worktree | TS-15 |
| AC-12 | The whole suite passes | Test Verification above |
| AC-13 | The plugin invariant checker passes every check | Code Quality Verification above |
| AC-14 | Both manifests carry the same raised version | TS-21 |
| AC-15 | The minimal tier's rework behaviour is documented | TS-19 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-11 |
| FR2 | task0002, task0013 | TS-12 |
| FR3 | task0002, task0005 | TS-5 |
| FR4 | task0001, task0012 | TS-10 |
| FR5 | task0001, task0003 | TS-13 |
| FR6 | task0003 | TS-13 |
| FR7 | task0003, task0004 | TS-1, TS-2, TS-4 |
| FR8 | task0004 | TS-14 |
| FR9 | task0005, task0011 | TS-15 |
| FR10 | task0005, task0006, task0010 | TS-15 |
| FR11 | task0005 | TS-15 |
| FR12 | task0002, task0005, task0011 | TS-8 |
| FR13 | task0001, task0003, task0012 | TS-9, TS-27 |
| FR14 | task0003 | TS-20 |
| FR15 | task0003, task0006, task0009, task0013 | TS-8, TS-24, TS-28 |
| FR16 | task0006, task0010 | TS-6 |
| FR17 | task0007 | TS-7 |
| FR18 | task0006, task0010 | TS-6, TS-25 |
| FR19 | task0005, task0011 | TS-16, TS-26 |
| FR20 | task0003, task0013 | TS-17 |
| FR21 | task0005 | TS-15 |
| FR22 | task0004 | TS-1, TS-2, TS-3 |
| FR23 | task0003 | TS-18 |
| FR24 | task0008 | TS-19 |
| NFR1 | task0001, task0003, task0012 | TS-13 |
| NFR2 | task0005, task0007 | TS-7 |
| NFR3 | task0003, task0004, task0005, task0009, task0013 | TS-3 |
| NFR4 | task0008 | TS-21 |
| NFR5 | task0001, task0003 | TS-13 |
| NFR6 | task0003, task0004, task0005, task0009, task0011 | TS-22 |
| NFR7 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009, task0010, task0011, task0012, task0013 | TS-23 |

## E2E Testing

No end-to-end framework exists in this repository and
`workflow.yaml`'s `e2e_test_command` is empty (AS-8). No E2E scenario is
automated for this feature.

## Manual Testing (E2E Not Possible)

The behaviours below exercise external tools and a live orchestrator run, so
they cannot be asserted from the suite. They are human-run checks after the
integrated verification passes.

- [ ] A run whose Codex estimate reports no work remaining ends before any
      workflow step, with the stopped state, the no-step sentinel, non-empty
      resume guidance saying no resumption is needed, and the Codex rationale
      present in the stop recovery text (FR7).
- [ ] A live decision with both tools available records two decision bases —
      description-only and description-plus-estimate — in the persisted
      decision block (FR6).
- [ ] With the Jev skill returning a non-zero exit status, the run proceeds at
      the tier that removes nothing, and no confirmation prompt appears in an
      unattended run (FR13, NFR6).
- [ ] A `minimal` run produces a task document with exactly its two sections,
      one task entry, and still runs the whole existing test suite and the
      Step 0 git-setup gate (FR10, FR11).
- [ ] An upgrade triggered by a critical review finding raises the tier,
      returns the skipped steps to pending, and re-runs the completed
      create-spec step so the spec document exists (FR12, FR19).

Mockup visual comparison is not applicable: the design step is `skipped` and
this feature has no visual surface.

## Performance / Security Verification

- Performance: no target is fixed by SPEC; nothing to measure.
- Security — review perspective: the baseline perspective set is unchanged, so
  the security perspective is selected on every run at every granularity
  (NFR2). Verified by TS-7 and by a direct read of the review rules' baseline.
- Security — secret scanning: the Step 0 git-setup gate, which installs the
  secret-scanning pre-commit hook, runs in every tier (FR11). Verified by
  TS-15.
- Security — external execution: the Codex pre-survey runs through the
  readonly wrapper and never through the raw subcommand (FR5). Verified by
  TS-13.
- Security — external services: no task-management service status or body is
  touched, and the responsibility-boundary section is unchanged (FR8).
  Verified by TS-14.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 … TS-28) | 28 | 28 | 0 | 0 |
| Success criteria (AC-1 … AC-15) | 15 | 15 | 0 | 0 |
| Static analysis | 1 | 1 | 0 | 0 |
| Manual checks | 5 | 0 | 0 | 5 |
| **Total** | **49** | **44** | **0** | **5** |
