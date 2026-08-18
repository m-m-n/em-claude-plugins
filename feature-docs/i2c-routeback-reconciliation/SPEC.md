# Feature: i2c-routeback-reconciliation

Requirements document: `feature-docs/i2c-routeback-reconciliation/REQUIREMENTS.md`.

## Overview

The `### I.2.c: Failed handling` text in `em-workflow/references/implement-phase.md` is already
on main and already carries the merged intent of two source features,
recycled-task-id-consistency and routeback-gate-postcondition. This feature produces a single
verification record that establishes, with re-checkable evidence, that the merged text expresses
both features' intent without contradiction, that names each deliberate departure from a source
SPEC's literal wording together with the authoritative document for it, and that records PR #5's
settled disposition. It changes no protocol document, no test matcher and no version field.

## Objectives

- OBJ1: Establish, with reproducible evidence, that the already-merged `### I.2.c: Failed handling`
  text expresses the intent of BOTH source features in one non-contradictory body of prose.
- OBJ2: Record where the merged text deliberately departs from a source SPEC's literal wording, and
  which document is authoritative for each departure, so a later reader does not reopen a settled
  conflict from the superseded text.
- OBJ3: Settle and record the disposition of PR #5, closing the task that was opened on the
  assumption that it was still unmergeable.
- OBJ4: Produce this as a verification record only — change no protocol document, no test matcher
  and no version field.

## User Stories

The resolved requirements define no user stories; this feature has no UI surface and no interactive
actor. Its acceptance is expressed directly by the acceptance criteria below.

## Technical Requirements

### Functional Requirements

- **FR1 — Verify the reconciled gate condition satisfies both features' acceptance criteria:**
  The verification record must show that the merged I.2.c route-back gate simultaneously satisfies
  routeback-gate-postcondition AC1 (the gate is stated as "no task has status `merged`" AND "no task
  has status `in_progress`", with the write set still resetting `failed` tasks to `pending`) and
  recycled-task-id-consistency AC-3/FR3 (route-back is admissible only when every task whose journal
  carries an event has a terminal journal last event).
  Evidence: `implement-phase.md` lines 405-428 — the conjunction at lines 407-409, the `merged` half
  stated as a union of `workflow.yaml` and Step I.2.b step 1's reconciled state (lines 413-418), the
  `in_progress` half stated as a union of `workflow.yaml` and Step I.2.b's last-event-per-task rule
  (lines 418-423), and the sentence at lines 423-428 that derives the terminal-last-event property
  from the second union member.
  The record must state that FR3's precondition is satisfied AS a union member rather than as a
  separate check, and that "no task has status `merged`" survives verbatim as both SPECs require.

- **FR2 — Verify the write-then-commit-then-cleanup ordering and record which source ordering was
  superseded:**
  The verification record must show the merged admitted path orders: gate decision → integration-worktree
  refresh → `ROUTEBACK_TIP` capture → one ordered `workflow.yaml` write set → route-back commit →
  worktree/branch cleanup → end-of-phase report.
  Evidence: `implement-phase.md` line 444 ("Commit that write set next, BEFORE any cleanup") and
  lines 450-451 ("Only once that commit succeeds, clean up worktrees and branches"), plus the
  documented residual leftover state at lines 456-459.
  The record must state that recycled-task-id-consistency's `SPEC.md` as-written ordering
  (write set → cleanup → commit; SPEC.md line 160, NFR1 line 87 and TS-10 line 244) is SUPERSEDED,
  that its own Merge Note row 3 (SPEC.md line 23) records the supersession and its rationale, and
  that routeback-gate-postcondition FR3/AC3's requirement that the gate decision precede every
  `commit-docs.sh` invocation and all cleanup still holds under this ordering.

- **FR3 — Verify the gate-rejection side effect and reconcile the two features' opposing statements
  about it:**
  The verification record must show that the merged rejected path performs exactly one write — the
  `implement` step's `status` set to `failed` — and exactly one commit of that write
  ("docs({feature}): implement route-back gate rejected"), preceded by a refresh and a
  `TERMINAL_TIP` capture, with no route-back write set, no worktree/branch cleanup and no route-back
  commit.
  Evidence: `implement-phase.md` lines 467-486, notably the enumeration of all four rejection causes
  (lines 467-472), the single-write sentence (lines 473-479) and the scoped no-side-effect sentence
  (lines 480-482).
  The record must reconcile the two source statements explicitly: routeback-gate-postcondition FR2
  (lines 86-90) requires the `implement: failed` write, while its FR3/AC3 (lines 47-49, 91-94) say
  the rejected path "commits nothing and mutates nothing"; recycled-task-id-consistency FR4/AC-4
  (lines 51, 78) require that `implement` STAY `failed` with no write. The record must state the
  reconciled reading — the "nothing" in routeback-gate-postcondition AC3 scopes to the ROUTE-BACK
  write set, commit and cleanup, not to the terminal status commit — and cite
  recycled-task-id-consistency `SPEC.md`'s Merge Note row 2 (line 22), which already adopts that
  reading as "the same guarantee, stated as an explicit write rather than as an absence".

- **FR4 — Verify both document-contract modules are green against the merged text:**
  The verification record must show that `tests/test_implement_routeback_gate.py` and
  `tests/test_recycled_task_id_consistency.py` both encode the MERGED wording and ordering, not
  either pre-merge variant, and that both pass.
  Evidence anchors to cite: `test_implement_routeback_gate.py` lines 486-502
  (`test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`, asserting
  gate < refresh < tip < write set < commit < cleanup), lines 504-512
  (`test_rejected_path_order_gate_terminal_write_terminal_commit`), line 569
  (`test_implement_is_written_to_failed_and_committed`) and lines 407-418 (the `in_progress`-half-as-union
  assertions); `test_recycled_task_id_consistency.py` lines 892-897
  (`test_commit_precedes_cleanup_precedes_end_of_phase_report`, asserting
  `commit_idx < cleanup_idx < report_idx`) whose class docstring at lines 864-871 records the
  commit-before-cleanup rationale, and lines 521-533 (the terminal-last-event precondition and its
  position before the ordered write set).

- **FR5 — Version bump, not applicable to this feature:**
  NOT APPLICABLE. The task description's fifth acceptance criterion required a lockstep bump of
  `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. It is conditioned
  on modifying a file under `em-workflow/`; the resolved scope (`verify_and_close`) forbids any such
  modification, so the condition never arises and no bump is owed. The verification record must
  state this as resolved-not-applicable, not as an outstanding item, and record the observed state
  as evidence that the two registries are already in lockstep:
  `em-workflow/.claude-plugin/plugin.json` reads `"version": "0.1.45"` and the em-workflow entry of
  `.claude-plugin/marketplace.json` reads `"version": "0.1.45"`. It must also note that
  recycled-task-id-consistency FR9/AC-9's target of 0.1.38 was satisfied at merge time and has since
  been superseded by later bumps, so 0.1.45 is not a violation of that AC.

- **FR6 — Record PR #5's settled disposition:**
  The verification record must record PR #5 as MERGED, with the evidence the orchestrator gathered:
  `gh pr view 5` reporting state MERGED (base main, head
  `em-workflow/recycled-task-id-consistency/integration`), and
  `git merge-base --is-ancestor origin/em-workflow/recycled-task-id-consistency/integration origin/main`
  returning true. It must state that the task description's fourth acceptance criterion is satisfied
  by the first disjunct's stronger form — the branch is not merely mergeable, it is merged — and that
  no further action on PR #5 is owed.

- **FR7 — The deliverable is a verification record under this feature's directory only:**
  The sole artifact this feature produces is a verification record under
  `feature-docs/i2c-routeback-reconciliation/`. The change set must contain no path under
  `em-workflow/`, no path under `tests/`, and neither `em-workflow/.claude-plugin/plugin.json` nor
  `.claude-plugin/marketplace.json`. In particular `em-workflow/references/implement-phase.md`,
  `tests/test_implement_routeback_gate.py` and `tests/test_recycled_task_id_consistency.py` are
  read-only inputs to this feature.

### Non-Functional Requirements

- **NFR1 — Evidence-backed, re-checkable claims:** Every claim in the verification record cites a
  locatable anchor — a quoted phrase plus its section, or a test module and test-method name — so a
  reader can re-run the check without re-deriving the history. No claim rests on the task
  description's narrative alone.

- **NFR2 — Zero-diff outside this feature's directory:** `git diff --name-only` for this change is a
  subset of `feature-docs/i2c-routeback-reconciliation/**` (plus, where the implement phase mandates
  them, `test-docs/i2c-routeback-reconciliation/**`). No file under `em-workflow/`, `tests/`, or
  either manifest appears.

- **NFR3 — Supersession is recorded, never silently dropped:** Wherever the merged text departs from
  a source SPEC's literal wording, the record names the source statement, the merged statement, and
  the document that is authoritative — following the precedent of recycled-task-id-consistency
  `SPEC.md`'s Merge Note table. It does not present a superseded statement as satisfied.

- **NFR4 — No behaviour change and no new mechanical checker:** The feature introduces no hook,
  script, agent, skill or test-matcher change, and adds no new mechanical checker. Its acceptance bar
  is a green `python3 -m unittest discover -s tests` over the unmodified suite.

- **NFR5 — Local documentation conventions:** The verification record follows the repository's
  feature-docs conventions: markdown, backtick conventions for identifiers and file paths, and no
  rationale beyond what the requirements state.

## Acceptance Criteria

- [ ] **AC1 (FR1):** Reading the merged `### I.2.c: Failed handling` shows the route-back gate stated
      as a conjunction of "no task has status `merged`" and "no task has status `in_progress`"
      (`implement-phase.md` lines 407-409), each half stated as a union of a `workflow.yaml` source
      and a Step I.2.b journal source (lines 413-423), and the record cites both
      routeback-gate-postcondition AC1 and recycled-task-id-consistency AC-3 as satisfied by that
      single sentence group.
- [ ] **AC2 (FR1):** The record shows that the gate's second union member is what makes route-back
      admissible only when every task whose journal carries an event has a terminal last event,
      quoting `implement-phase.md` lines 423-428, and notes that a task with no journal event at all
      never blocks route-back.
- [ ] **AC3 (FR2):** The record shows the admitted-path order commit-before-cleanup by quoting
      "Commit that write set next, BEFORE any cleanup" (line 444) and "Only once that commit
      succeeds" (line 450), and names recycled-task-id-consistency `SPEC.md` line 23 as the document
      that records the supersession of its own written cleanup-before-commit ordering.
- [ ] **AC4 (FR2):** The record confirms routeback-gate-postcondition AC3's "gate decision before any
      `commit-docs.sh` invocation and before route-back cleanup" still holds in the merged text,
      citing that the gate sentence group (lines 405-428) precedes the first `commit-docs.sh`
      (line 445).
- [ ] **AC5 (FR3):** The record shows the rejected path's only side effect is the `implement: failed`
      write plus its own commit, quoting `implement-phase.md` lines 480-482, and states the
      reconciled reading of routeback-gate-postcondition AC3's "nothing is committed" as scoped to
      the route-back write set, commit and cleanup — citing recycled-task-id-consistency `SPEC.md`
      line 22 as prior adoption of that reading.
- [ ] **AC6 (FR3):** The record enumerates all four gate-rejection causes as the merged text states
      them (lines 467-472) and confirms no retry loop, no alternative recovery route and no degraded
      route back is offered (lines 485-486).
- [ ] **AC7 (FR4):** The record names, for each of the three reconciled hunks, at least one test
      method in `tests/test_implement_routeback_gate.py` or
      `tests/test_recycled_task_id_consistency.py` that pins the merged form — at minimum
      `test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`,
      `test_rejected_path_order_gate_terminal_write_terminal_commit`,
      `test_implement_is_written_to_failed_and_committed`, and
      `test_commit_precedes_cleanup_precedes_end_of_phase_report`.
- [ ] **AC8 (FR4, NFR4):** `python3 -m unittest discover -s tests` run from the repository root exits
      0 with no test skipped, added, deleted or modified; the record states the observed test count
      alongside the orchestrator's own observation of 1522 tests OK.
- [ ] **AC9 (FR5):** The record states the version-bump requirement as not applicable, and records
      the observed lockstep pair `em-workflow/.claude-plugin/plugin.json` = 0.1.45 and
      `.claude-plugin/marketplace.json` em-workflow entry = 0.1.45. Neither file is modified.
- [ ] **AC10 (FR6):** The record states PR #5 as MERGED with both pieces of orchestrator evidence,
      and maps that to the task description's fourth acceptance criterion.
- [ ] **AC11 (FR7, NFR2):** `git diff --name-only` for this change lists no path under
      `em-workflow/`, no path under `tests/`, and neither manifest.
- [ ] **AC12 (NFR1, NFR3):** Every departure between the merged text and a source SPEC is listed in
      one table with three columns — source statement, merged statement, authoritative document —
      covering at minimum the routeback-gate-postcondition AC3 rejected-path-commit departure and the
      recycled-task-id-consistency NFR1/TS-10 ordering departure.

## Implementation Approach

### Architecture

The deliverable is a single markdown verification record under
`feature-docs/i2c-routeback-reconciliation/`. It has no runtime component, no UI surface, no data
model and no API surface. Its structure is driven by the requirements above:

```
verification record
├── merged gate condition          (FR1 — AC1, AC2)
├── admitted-path ordering         (FR2 — AC3, AC4)
├── rejected-path side effect      (FR3 — AC5, AC6)
├── test-suite evidence            (FR4 — AC7, AC8)
├── version-bump non-applicability (FR5 — AC9)
├── PR #5 disposition              (FR6 — AC10)
└── departure table                (NFR3 — AC12)
```

### Data Flow

```
read-only inputs                          verification record
─────────────────────────────────────     ───────────────────
em-workflow/references/implement-phase.md  → quoted anchors (FR1, FR2, FR3)
tests/test_implement_routeback_gate.py     → named test methods (FR4)
tests/test_recycled_task_id_consistency.py → named test methods (FR4)
recycled-task-id-consistency SPEC.md       → Merge Note rows 2, 3 (FR2, FR3, NFR3)
routeback-gate-postcondition SPEC.md       → AC1-AC3 classification (FR1, FR3, NFR3)
em-workflow/.claude-plugin/plugin.json     → observed 0.1.45 (FR5)
.claude-plugin/marketplace.json            → observed 0.1.45 (FR5)
orchestrator gh/git observations           → PR #5 MERGED (FR6)
```

Every input above is read-only for this feature (FR7).

### Departure Table (required content, NFR3 / AC12)

The record's departure table carries three columns and covers at minimum these two rows.

| Source statement | Merged statement | Authoritative document |
|---|---|---|
| routeback-gate-postcondition FR3/AC3: the rejected path "commits nothing and mutates nothing" (lines 47-49, 91-94) | The rejected path writes `implement: failed` and commits exactly that write; "nothing" scopes to the route-back write set, commit and cleanup (`implement-phase.md` lines 473-482) | `em-workflow/references/implement-phase.md`; the reading is already adopted by recycled-task-id-consistency `SPEC.md` Merge Note row 2 (line 22) |
| recycled-task-id-consistency `SPEC.md`: write set → cleanup → commit (line 160, NFR1 line 87, TS-10 line 244) | write set → commit → cleanup (`implement-phase.md` line 444, lines 450-451) | `em-workflow/references/implement-phase.md`; the supersession is recorded by recycled-task-id-consistency `SPEC.md` Merge Note row 3 (line 23), and `tests/test_recycled_task_id_consistency.py` is authoritative for the test-level expression |

routeback-gate-postcondition `SPEC.md` carries no merge note of its own — it is the feature that
landed first — so this verification record is the only place its AC3 departure is documented.

### Dependencies

**Internal dependencies (all read-only):**

- `em-workflow/references/implement-phase.md`: the merged `### I.2.c: Failed handling` text under
  verification.
- `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`: the
  document-contract modules that pin the merged form.
- `feature-docs/recycled-task-id-consistency/SPEC.md`, `feature-docs/routeback-gate-postcondition/SPEC.md`:
  the two source SPECs.
- `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version observation
  only.

**External dependencies:** none. The repository has no LICENSE file, no package manifest and no E2E
infrastructure.

### File Structure

```
feature-docs/i2c-routeback-reconciliation/
├── REQUIREMENTS.md
├── SPEC.md
└── (the verification record and the workflow-generated artifacts)
```

## Declared Change Set

Feature-specific paths: none beyond the two default entries below — FR7 confines the deliverable to
this feature's own directory.

- `feature-docs/i2c-routeback-reconciliation/**`
- `test-docs/i2c-routeback-reconciliation/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`,
`workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These are generated and owned
by the phase documents and by `references/phase-state.md`; this section cites them and restates none
of their rules.

`test-docs/{feature}/**` covers `test-docs/i2c-routeback-reconciliation/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC author explicitly removes
them; their absence is never assumed by silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed at verification time must be
CONTAINED IN the declared set, not equal to it. A feature that produces no implement tasks generates
no `test-docs/{feature}/` directory at all; the declared `test-docs/{feature}/**` entry is still
correct in that case — a declared path that never materializes is not a violation.

Explicitly excluded by FR7 and NFR2: any path under `em-workflow/`, any path under `tests/`,
`em-workflow/.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json`.

## Test Scenarios

### Document Assertions

- [ ] **TS1** (AC1/AC2 — FR1): Slice `implement-phase.md` from `### I.2.c: Failed handling` to
      `### Supporting cast`, normalize whitespace, and confirm both gate conjuncts and both union
      members are present in one sentence group, with "no task has status `merged`" surviving
      verbatim.
- [ ] **TS2** (AC3/AC4 — FR2): In the same slice, confirm the index order
      gate < "Refresh the integration worktree first" < "ROUTEBACK_TIP" <
      "make one ordered workflow.yaml write set" < "Commit that write set next, BEFORE any cleanup" <
      "Only once that commit" < "End the phase with a".

### Abnormal Path

- [ ] **TS3** (AC5/AC6 — FR3): Slice from "When the gate does not hold" to `- **abort phase**` and
      confirm it contains the `implement: failed` write, the `TERMINAL_TIP` capture, the
      "implement route-back gate rejected" commit message, the scoped ONLY-side-effect sentence, and
      no occurrence of `git worktree remove --force`.

### Cross-Document

- [ ] **TS4** (AC1/AC5/AC12 — FR1, FR3, NFR1, NFR3): Walk routeback-gate-postcondition `SPEC.md`
      AC1-AC3 and recycled-task-id-consistency `SPEC.md` AC-3/AC-4 against the merged slice, and
      classify each as satisfied-verbatim, satisfied-under-the-reconciled-reading, or superseded —
      with the authoritative document named for the last two classes.

### Regression

- [ ] **TS5** (AC7/AC8 — FR4, NFR4): Run `python3 -m unittest discover -s tests` from the repository
      root; confirm exit 0, and confirm `tests/test_implement_routeback_gate.py` and
      `tests/test_recycled_task_id_consistency.py` both pass as modules in their own right.

### Boundary

- [ ] **TS6** (AC7 — FR4, NFR3): Confirm `test_recycled_task_id_consistency.py`'s TS-10 class asserts
      `commit_idx < cleanup_idx` (lines 892-897), i.e. the module was updated away from its SPEC's
      as-written cleanup-first ordering, so the suite pins the merged order rather than tolerating
      either.

### Diff Scope

- [ ] **TS7** (AC9/AC11 — FR5, FR7, NFR2): Run `git diff --name-only` for the change and confirm it
      is a subset of `feature-docs/i2c-routeback-reconciliation/**` and
      `test-docs/i2c-routeback-reconciliation/**`, and that `em-workflow/references/implement-phase.md`,
      both test modules and both manifests are absent from it.

### Staleness

- [ ] **TS8** (AC10 — FR6): Confirm the verification record states the task description's premise
      (PR #5 CONFLICTING, reconciliation outstanding) as stale, and names the evidence that
      superseded it.

### Edge Cases

- [ ] **TS9** (FR5): Confirm the record notes that recycled-task-id-consistency FR9/AC-9's version
      target 0.1.38 is historical and that the current 0.1.45 lockstep pair does not violate it.
- [ ] **TS10** (FR2, NFR3): Confirm the record notes that recycled-task-id-consistency `SPEC.md`'s
      Merge Note (lines 9-27) already exists in-repo and is itself corroborating evidence that the
      reconciliation landed, independent of the git/gh evidence.

### E2E Tests

**Existing E2E tests**: None. **Run command**: Not detected. The repository has no E2E
infrastructure.

## Assumptions

- **ASM1** (gate `create-spec.requirement-clarification`, question
  `scope.reconciliation-already-merged`, option `verify_and_close`, source `batch_policy`): The task
  description's premise is stale. The I.2.c reconciliation is already on main; this feature is scoped
  to verification and record-keeping only, with no edit to `em-workflow/references/implement-phase.md`,
  no test-matcher change and no version bump.
- **ASM2** (confirmed facts carried forward from the orchestrator's verification): `gh pr view 5`
  reports state MERGED (base main, head `em-workflow/recycled-task-id-consistency/integration`);
  `git merge-base --is-ancestor origin/em-workflow/recycled-task-id-consistency/integration origin/main`
  returns true; `python3 -m unittest discover -s tests` reports 1522 tests, OK.
- **ASM3** (supersession, recorded per NFR3): Where the merged `implement-phase.md` text differs from
  recycled-task-id-consistency `SPEC.md` as written, the merged text is authoritative — that SPEC's
  own Merge Note (lines 9-27) says so. This covers its Architecture/Data-Flow ordering
  (write set → cleanup → commit), its NFR1 ordering clause and its TS-10 wording;
  `tests/test_recycled_task_id_consistency.py` is authoritative for the test-level expression of that
  ordering.
- **ASM4** (reconciled reading, recorded per NFR3): routeback-gate-postcondition FR3/AC3's "the
  rejected path commits nothing and mutates nothing" is read as scoped to the route-back write set,
  route-back commit and route-back cleanup. Its own FR2 requires the `implement: failed` write, so an
  unscoped reading would make that feature self-contradictory. The merged text states the scoped form
  explicitly, and recycled-task-id-consistency's Merge Note row 2 already adopts this reading.
- **ASM5**: routeback-gate-postcondition `SPEC.md` carries no merge note of its own — it is the
  feature that landed first — so this verification record is the only place its AC3 departure is
  documented.
- **ASM6** (gate `create-spec.design-step`, question `design.step-decision`, option
  `decide_autonomously`, source `batch_policy`): The design step is skipped.
- **ASM7** (derived from ASM1): No version bump is owed.
- **ASM8**: The repository has no LICENSE file, no package manifest and no E2E infrastructure.

## Design Step

Skipped. Resolved at gate `create-spec.design-step` with option `decide_autonomously`, which accepted
requirements-analyst's `skip` recommendation. The feature's sole deliverable is a markdown
verification record under `feature-docs/i2c-routeback-reconciliation/`; it has no UI surface, no data
model, no API surface and no design-system input, and the repository has no design system.

## Security Considerations

Not applicable. The feature adds no code path, no input handling and no data storage; its inputs are
read-only repository documents.

## Success Criteria

- [ ] All functional requirements FR1-FR7 are satisfied by the verification record.
- [ ] All non-functional requirements NFR1-NFR5 are satisfied.
- [ ] All acceptance criteria AC1-AC12 hold.
- [ ] All test scenarios TS1-TS10 pass.
- [ ] `python3 -m unittest discover -s tests` is green over the unmodified suite (NFR4).
- [ ] `git diff --name-only` stays within the declared change set (NFR2, AC11).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every functional and non-functional requirement is `resolved`; no requirement carries
`status: tbd`.

## References

- Requirements document: `feature-docs/i2c-routeback-reconciliation/REQUIREMENTS.md`
- Merged text under verification: `em-workflow/references/implement-phase.md`,
  `### I.2.c: Failed handling`
- Document-contract tests: `tests/test_implement_routeback_gate.py`,
  `tests/test_recycled_task_id_consistency.py`
- Source SPECs: `feature-docs/recycled-task-id-consistency/SPEC.md` (Merge Note, lines 9-27),
  `feature-docs/routeback-gate-postcondition/SPEC.md`
- Version observation: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
