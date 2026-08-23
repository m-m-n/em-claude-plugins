# Feature: goal-vs-spec-divergence

## Overview

This feature persists the launch-time task description (the "goal") verbatim
and immutably in `feature-docs/{feature}/workflow.yaml`, so that a divergence
between the goal and the specification documents can be judged with the goal
preserved. It gives post-implementation SPEC changes a protocol-valid route
(today they are always rejected as a protocol error), and separates
"correcting a guard declaration" from "changing a requirement" so that
evidence-backed corrections do not halt unattended runs. The fail-closed
strength of security / license / irreversible-operation handling is not
weakened.

Requirements source: `feature-docs/goal-vs-spec-divergence/REQUIREMENTS.md`
(Japanese). This document is the implementation-facing rendering of the same
requirements; the requirements document is authoritative for their Japanese
statements.

## Objectives

- Keep the goal in a machine-readable, immutable form so that a goal-versus-
  specification divergence can be decided with the goal protected.
- Give post-implementation SPEC changes a route that holds up under the
  protocol (today they are always rejected as a protocol error).
- Separate declaration (guard) correction from requirement change, so that
  evidence-backed corrections do not stop unattended runs, without weakening
  the fail-closed strength of security / license / irreversible operations.
- Detect the same class of divergence at create-spec time, reducing
  downstream stops in the first place.

## User Stories

### US1: Goal persisted verbatim and immutably
As the create-spec orchestrator, I want to store the launch-time task
description verbatim in `workflow.yaml`'s `goal` block, so that every later
phase can read the original goal unchanged.

**Acceptance Criteria:**
- [ ] AC-1 (FR1, FR2): `workflow-schema.md` defines the `goal` block, the
      create-spec phase document's workflow.yaml construction procedure
      includes writing it, and later phases are documented as not rewriting it.
- [ ] AC-2 (FR1, FR3): the documents state explicitly that the goal is stored
      verbatim with no summarization or truncation, and that it is handled as
      untrusted data.

### US2: A post-implementation SPEC change completes
As the orchestrator, I want the SPEC-change transition to survive create-plan
re-entry even when merged tasks exist, so that a specification change after
implementation is not rejected as a protocol error.

**Acceptance Criteria:**
- [ ] AC-3 (FR4, FR5, FR6): `workflow-patch.md`'s `replace_all` permission
      condition includes "permitted even with merged tasks when create-plan is
      `needs_update`", is consistent with `rework-task-synthesis.md` Section 10,
      and `base_commit` preservation is stated.

### US3: Batch-mode divergence is classified before it halts the run
As a batch-mode user, I want a classification gate to decide whether the
implementation fails the goal or merely diverges from the specification text,
so that evidence-backed specification gaps proceed while goal reconsideration
always stops.

**Acceptance Criteria:**
- [ ] AC-4 (FR7, FR8): the gate is documented as batch-only, interactive is
      documented as asking the user directly as before, and the question is
      written so it can be posed in both directions (goal not met / text
      divergence).
- [ ] AC-5 (FR9, FR10): the asymmetry ("goal reconsideration needed" stops
      unconditionally; "specification gap" is adopted only when evidence IDs
      are named) and the adoption criterion are stated.
- [ ] AC-6 (FR11, NFR2): `question-resolution.md`'s fail-closed classification
      is revised while the immediate aborts for security / license /
      `reversible: false` remain verifiably intact, and `batch-policies.yaml`'s
      wording is consistent with the revised rule.
- [ ] AC-7 (FR12, FR13, FR14): Codex output stays untrusted, the Codex-absent
      Claude self-classification route exists, and the audit record includes
      the classifier and the named evidence IDs.

### US4: Wording-only corrections do not re-enter the planner
As the orchestrator, I want an independent route for wording-only corrections
to create-plan-owned documents, so that such a correction does not require
planner re-entry.

**Acceptance Criteria:**
- [ ] AC-8 (FR15, FR16): the wording-correction route is defined with its
      eligibility conditions (no planner re-entry; plan/task/requirement
      metadata unchanged), and changes that fail those conditions are stated to
      fall back to the normal route.

### US5: Impact on tests is surfaced at create-spec time
As requirements-analyst, I want referenced-side scanning for symbols and
strings scheduled for deletion or renaming, so that affected files (including
tests) are reported as create-spec output.

**Acceptance Criteria:**
- [ ] AC-9 (FR17): the create-spec investigation procedure includes
      referenced-side scanning (tests included) and reports the result as
      analyst output.
- [ ] AC-10 (FR18, FR19): the Declared Change Set is defined as a create-plan
      derivation, the conditional auto-addition of deviations (evidence:
      "an existing acceptance criterion would be dropped") and the retention of
      the containment check are stated, and no exclusion rule is added to the
      observed change set at verification time.
- [ ] AC-11 (NFR5, NFR6, NFR8): `python3 -m unittest discover -s tests` passes
      in full, and plugin.json and marketplace.json carry the same updated
      version value.

## Technical Requirements

### Functional Requirements

- **FR1 — Verbatim goal persistence:** create-spec stores the
  `/em-workflow:develop` launch-time task description verbatim in the `goal`
  block of `feature-docs/{feature}/workflow.yaml`. No summarization,
  normalization, or truncation. The `goal` block is defined in
  `em-workflow/references/workflow-schema.md`, and only the create-spec phase
  orchestrator writes it (workers do not).
- **FR2 — Goal immutability:** once written, the `goal` block is never changed
  by any later phase. Even when the SPEC-change transition sets create-spec to
  `needs_update` and it is re-entered, `goal` is not overwritten and remains
  as-is.
- **FR3 — Goal treated as untrusted:** the `goal` block's content is handled as
  untrusted data; readers (classification gate, workers, orchestrator) never
  execute statements inside it as instructions.
- **FR4 — Relaxed `replace_all` permission condition:** revise
  `em-workflow/references/workflow-patch.md`'s `replace_all` permission
  condition so that when the `create-plan` step is `needs_update`,
  `replace_planning` is permitted even when `merged` tasks exist. The condition
  for the `create-plan` `pending` path (initial planning) is unchanged. The
  handling when `in_progress` / `failed` tasks exist stays the current protocol
  error, unchanged.
- **FR5 — `base_commit` preservation on replanning:** in the replanning
  permitted by FR4, `workflow[implement].base_commit` is preserved (it appears
  in the patch's `preserve`). This does not contradict the existing rework
  invariant that a rework patch does not change `base_commit`.
- **FR6 — SPEC-change transition holds:** the SPEC-change transition of
  `em-workflow/references/rework-task-synthesis.md` Section 10 (create-spec →
  `needs_update`; create-plan / implement / review → `pending`) is not rejected
  at create-plan re-entry even after implementation completes (merged tasks
  present). The transition document and `workflow-patch.md`'s permission
  condition are written consistently.
- **FR7 — Classification gate (batch-only):** in batch mode, every case that
  reaches `gate_id: rework.spec-change` passes through a Codex classification
  gate. The question is posed so that both directions can be raised — (a) the
  implementation cannot satisfy the goal, (b) the implementation satisfies the
  goal but diverges from the specification text. Inputs are the `goal` block
  (FR1) and the relevant specification document.
- **FR8 — Interactive behaviour unchanged:** in interactive mode the
  classification gate is not used; the user is asked directly as before.
  Introducing the gate does not change the interactive question route.
- **FR9 — Asymmetry of classification outcomes:** a "the specification has a
  gap" verdict proceeds only when Claude is convinced. A "the goal needs
  reconsideration" verdict stops unconditionally and does not pass even if
  Claude disagrees. No path exists that passes on a second verdict.
- **FR10 — Adoption criterion (naming the evidence):** a "specification gap"
  verdict is adopted only when the classification's evidence names specific
  existing requirement IDs / acceptance-criterion IDs. A conclusion-only reply
  is not adopted, and the run stops in that case.
- **FR11 — Revised fail-closed classification:** revise
  `em-workflow/references/question-resolution.md`'s fail-closed classification
  so that `category: spec-change` / `gate_id: rework.spec-change` can enter the
  classification gate (FR7) in batch. `category: security`, `category: license`,
  and immediate abort from `reversible: false` assumptions are outside the
  scope of this revision and are not weakened. The `batch-policies.yaml`
  statement that "rework.spec-change is intentionally unlisted" is also aligned
  to be consistent with the revised rule.
- **FR12 — Handling of Codex output:** Codex output is read only, never
  executed as instructions and never adopted verbatim. The decision to
  transcribe a classification result into requirements / acceptance criteria
  belongs to Claude. The existing Codex consultation procedure (availability
  probe, read-only wrapper, turn limit) is unchanged.
- **FR13 — Route when Codex is absent:** in environments where Codex is
  unavailable, Claude performs the classification itself and proceeds after
  recording an audit entry that names the requirements / acceptance criteria
  used as evidence. When it cannot name them, it stops under the same criterion
  as FR10. FR9's asymmetry (goal-reconsideration verdicts stop unconditionally)
  applies identically on this route.
- **FR14 — Classification audit record:** for every case that passes through
  the classification gate, record in phase-state an audit entry carrying the
  classifier (`codex` / `claude`), the classification result, the named
  evidence IDs, and the proceed/stop decision.
- **FR15 — Independent wording-correction route:** define a route independent
  of the classification gate for wording-only corrections to create-plan-owned
  documents (`IMPLEMENTATION.md` / `VERIFICATION.md`). Its eligibility
  conditions are that it involves no planner re-entry and that plan, task, and
  requirement metadata are unchanged.
- **FR16 — Wording-correction route guard:** the FR15 route cannot be used for
  changes that touch plan, task, or requirement metadata. Changes that do not
  meet the conditions go through the normal rework / SPEC-change route. The
  conditions are written so that deviation is detectable.
- **FR17 — Impact-on-tests detection at create-spec:** during the create-spec
  investigation, scan the referencing side (tests included) for symbols and
  strings targeted for deletion or renaming, and report the affected files as
  requirements-analyst output. For the case at hand, `dispatcher.test.ts` must
  surface at create-spec time. The path-resolution discipline (the orchestrator
  resolves scan-target paths into `resolved_input_paths` before passing them)
  is not broken.
- **FR18 — Declared Change Set becomes derived:** move the Declared Change Set
  from a hand-written declaration in SPEC to a form mechanically derived by
  create-plan from the union of the tasks' `files` plus the default entries
  (`feature-docs/{feature}/**`, `test-docs/{feature}/**`). The documents state
  explicitly that this is a guard, not a statement of the goal.
- **FR19 — Conditional auto-addition of deviations, containment check
  retained:** an implement deviation is auto-added to the declaration only when
  it is presented with the evidence "an existing acceptance criterion would be
  dropped", and an audit record remains. The containment check (actual change
  set ⊆ declared set) remains, and unjustified scope expansion is stopped as
  before. No exclusion rule that subtracts anything from the change set
  observed at verification time is introduced.
- **FR20 — Handling of pre-existing features without a `goal` block:**
  `workflow.yaml` files of features that passed create-spec before this feature
  have no `goal` block. Define how such features are handled when they reach
  the classification gate (FR7 / FR13) — whether to backfill, or to leave the
  classification gate inapplicable and stop as before.
  **Status: TBD.** *tbd_reason:* the nine answers gathered here decide only
  goal persistence on the new create-spec route; retroactive treatment of
  existing features (backfill versus classification-gate-inapplicable, falling
  back to the previous stop) is not touched by any of the answers. It is to be
  settled during create-plan's TBD resolution.

### Non-Functional Requirements

- **NFR1 - SSOT discipline:** do not restate rules across the documents being
  changed; cite the existing SSOTs (`workflow-schema.md` / `workflow-patch.md` /
  `question-resolution.md` / `question-packet-schema.md` /
  `rework-task-synthesis.md` / the per-worker contracts) instead. Do not create
  a second statement of the same rule.
- **NFR2 - Fail-closed strength not regressed:** the immediate aborts for
  security / license / irreversible operations (`reversible: false`) remain at
  the same strength after the classification gate is introduced. The gate never
  becomes a bypass around them.
- **NFR3 - Unattended-run continuity:** the new gates and routes never raise,
  in batch, a confirmation that nobody can answer. When they stop, the reason
  and the evidence remain as a record.
- **NFR4 - Codex independence:** every capability of this feature holds in
  environments where Codex is not installed (FR13).
- **NFR5 - Test conventions:** tests live under the repository-root `tests/`
  directory as `test_*.py` and use only the Python standard library's
  `unittest` (no third-party dependencies). They are discoverable and runnable
  via `python3 -m unittest discover -s tests`.
- **NFR6 - Plugin version bump:** because files under `em-workflow/` change,
  raise the version in `em-workflow/.claude-plugin/plugin.json` and in the
  repository-root `.claude-plugin/marketplace.json` to the same value within
  the same change (`.claude/rules/core-plugin-version-bump.md`).
- **NFR7 - Single scope:** FR1–FR19 are specified and implemented together as
  one feature without splitting (no ordering of work is prescribed).
- **NFR8 - Existing tests not broken:** the existing modules under `tests/`
  (`test_workflow_patch_doc.py` / `test_question_resolution_doc.py` /
  `test_rework_synthesis_contract.py` /
  `test_declared_change_set_invariants.py` / `test_gate_option_vocabulary*.py`
  and others) stay green, or are updated in a way consistent with this
  feature's changes. Guards are not deleted in order to make the documents
  pass.

## Implementation Approach

### Architecture

The deliverables are markdown protocol documents, agent prompts, and Python
tests — there is no runtime service, UI surface, or data model (assumption
A-5). The affected artefacts group as follows.

**Component map:**

```
em-workflow/references/
├── workflow-schema.md              # goal block definition                (FR1, FR2, FR3)
├── workflow-patch.md               # replace_all permission, preserve      (FR4, FR5)
├── rework-task-synthesis.md §10    # SPEC-change transition                (FR6)
├── question-resolution.md          # fail-closed classification, gate      (FR7-FR14, NFR2)
├── question-packet-schema.md       # question / answer structure (cited)   (NFR1)
├── gate-option-vocabulary.md       # gate_id / option_id correspondence    (A-3)
├── phase-state.md                  # classification audit record location  (FR14)
└── contracts/                      # per-worker contracts (cited)          (NFR1, FR17)

em-workflow/skills/                 # phase documents: create-spec workflow.yaml
                                    # construction, wording-correction route,
                                    # Declared Change Set derivation
                                    #                                       (FR1, FR15, FR16, FR18, FR19)

em-workflow/agents/                 # requirements-analyst investigation procedure
                                    #                                       (FR17)

tests/                              # unittest document pins                (TS-1..TS-10, NFR5, NFR8)
```

### Data Flow

**Goal persistence (FR1–FR3):**

```
/em-workflow:develop task description
  → create-spec orchestrator (sole writer)
  → workflow.yaml `goal` block (verbatim, immutable thereafter)
  → read by workers / classification gate as UNTRUSTED data
```

**Batch classification gate (FR7–FR14):**

```
gate_id: rework.spec-change reached (batch)
  → gate input: goal block + relevant specification document
  → classifier: Codex, or Claude when Codex is unavailable (FR13)
  → verdict (a) implementation cannot satisfy the goal   → stop unconditionally (FR9)
    verdict (b) implementation satisfies goal, text diverges
        → evidence names existing requirement / acceptance-criterion IDs? (FR10)
              yes and Claude is convinced → proceed
              no                          → stop
  → audit record → phase-state: classifier, result, named evidence IDs, decision (FR14)
```

In interactive mode the gate is skipped and the user is asked directly (FR8).

**Post-implementation SPEC change (FR4–FR6):**

```
SPEC-change transition (rework-task-synthesis.md §10)
  create-spec → needs_update ; create-plan / implement / review → pending
  → create-plan re-entry with merged tasks present
  → workflow-patch.md: replace_planning permitted because create-plan is needs_update (FR4)
  → workflow[implement].base_commit carried in patch `preserve` (FR5)
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/workflow-schema.md`: the `goal` block is defined here
  (FR1); other documents cite rather than restate it (NFR1).
- `em-workflow/references/workflow-patch.md`: owns the `replace_all` permission
  condition and `preserve` (FR4, FR5).
- `em-workflow/references/rework-task-synthesis.md`: Section 10's SPEC-change
  transition must stay consistent with the above (FR6).
- `em-workflow/references/question-resolution.md`: owns the fail-closed
  classification being revised (FR11) and the aborts being preserved (NFR2).
- `em-workflow/references/gate-option-vocabulary.md`: if the classification gate
  adds a `gate_id`, its correspondence rule (option_id declaration under the
  `## Gate option vocabulary` section) and the matching check under `tests/`
  apply (assumption A-3).
- `em-workflow/references/phase-state.md`: destination of the classification
  audit record (FR14).
- Worker envelope / contracts: FR17's scanning keeps the orchestrator-resolved
  `resolved_input_paths` discipline (assumption A-4).

**External Dependencies:**
- Codex: optional. Used as the classifier through the existing consultation
  procedure, unchanged (FR12). All capabilities hold without it (NFR4, FR13).
- Python standard library `unittest` only; no third-party test dependencies
  (NFR5).

### File Structure

```
em-workflow/
├── references/           # protocol documents (SSOTs listed above)
├── skills/               # phase documents
├── agents/               # worker prompts
└── .claude-plugin/plugin.json     # version bump (NFR6)
.claude-plugin/marketplace.json    # version bump, same value (NFR6)
tests/
└── test_*.py             # unittest document pins (NFR5, NFR8)
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/**`
- `em-workflow/skills/**`
- `em-workflow/agents/**`
- `tests/**`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/goal-vs-spec-divergence/**`
- `test-docs/goal-vs-spec-divergence/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules. The design step is skipped for this
feature (assumption A-5), so no design artifacts are produced.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

FR18 of this feature moves this declaration from a hand-written SPEC section to
a create-plan derivation; this section is the declaration for the current
feature under the protocol as it stands at create-spec time.

## Test Scenarios

### Unit Tests

- [ ] TS-1 (FR1, FR2, FR3): pin the `goal` block's definition, immutability,
      and untrusted-handling statements in `workflow-schema.md` and the
      create-spec phase document by string scanning.
- [ ] TS-2 (FR4, FR5, FR6): confirm by scanning that `workflow-patch.md`'s
      `replace_all` permission condition and `rework-task-synthesis.md`
      Section 10's transition hold together, including that the old condition's
      wording no longer remains.
- [ ] TS-3 (FR7, FR8, FR9, FR10): confirm that the classification gate's
      batch-only restriction, two-directional question, asymmetry, and
      evidence-naming criterion are present in the relevant documents.
- [ ] TS-4 (FR11, NFR2): confirm as a retention pin that
      `question-resolution.md`'s fail-closed section still carries the immediate
      aborts for security / license / `reversible: false`, and confirm that the
      spec-change-side revision is in place.
- [ ] TS-5 (FR13, FR14): confirm that the Codex-absent self-classification
      route and the audit-record fields (classifier, evidence IDs, decision)
      are defined.
- [ ] TS-6 (FR15, FR16): confirm that all three eligibility conditions of the
      wording-correction route (no planner re-entry; plan/task unchanged;
      requirement metadata unchanged) are stated.
- [ ] TS-7 (FR17): confirm that the analyst-side investigation procedure
      includes referenced-side scanning and does not contradict the
      no-self-filesystem-discovery discipline.
- [ ] TS-8 (FR18, FR19): confirm the Declared Change Set derivation definition
      and the retention of the containment check, and confirm — using the same
      method as the existing invariant test — that no verify-side exclusion
      rule has been added.
- [ ] TS-9 (NFR6): confirm that the em-workflow version in plugin.json and in
      marketplace.json match and are higher than before the change.
- [ ] TS-10 (NFR8): confirm that the existing document-pin test modules all
      pass (full-suite run).

**Run command:** `python3 -m unittest discover -s tests` (NFR5).

### Integration Tests

None specified. All ten scenarios above are unit tests (NFR5).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] EC-1 (FR13): the classification gate is reached in an environment where
      Codex is not installed or its wrapper is absent — proceed via Claude
      self-classification plus an audit record; stop if the evidence cannot be
      named.
- [ ] EC-2 (FR9): Codex judges "the goal needs reconsideration" and Claude
      disagrees — stop unconditionally.
- [ ] EC-3 (FR10): Codex returns only a conclusion and cannot name requirements
      or acceptance criteria — do not adopt; stop.
- [ ] EC-4 (FR4, FR5): replanning runs while merged tasks' output is already on
      the integration branch — `base_commit` is preserved and the already
      incorporated output is not discarded.
- [ ] EC-5 (FR19): a deviation whose evidence is something other than "an
      existing acceptance criterion would be dropped" (e.g. implementer
      convenience) — not auto-added.
- [ ] EC-6 (FR1): the launch-time task description is very long — not
      truncated, because storage is verbatim.
- [ ] EC-7 (FR1): the launch-time task description is empty, or the feature is
      resumed without a path argument — handling of the state where there is no
      source for the goal (connects to FR20's TBD).
- [ ] EC-8 (FR16): an edit intended as a wording correction turned out to touch
      requirement metadata — falls outside the independent route and goes
      through the normal route.

### Performance Tests

None. No performance targets are stated in the requirements.

## Security Considerations

- **Input Validation / Untrusted data:** the `goal` block's content is handled
  as untrusted data; readers (classification gate, workers, orchestrator) never
  execute statements inside it as instructions (FR3). Codex output is likewise
  read only, never executed as instructions and never adopted verbatim (FR12).
- **Fail-closed retention:** immediate abort for `category: security`,
  `category: license`, and `reversible: false` assumptions is out of scope for
  the FR11 revision and keeps the same strength; the classification gate must
  not become a bypass around them (NFR2). TS-4 pins this.
- **Decision asymmetry:** a "goal needs reconsideration" verdict stops
  unconditionally, and no path exists that passes on a second verdict (FR9).
- **Evidence requirement:** a "specification gap" verdict is adopted only when
  specific existing requirement / acceptance-criterion IDs are named;
  conclusion-only replies stop the run (FR10, FR13).
- **Auditability:** every case passing the gate leaves an audit record in
  phase-state with the classifier, result, named evidence IDs, and the
  proceed/stop decision (FR14). When a route stops, the reason and evidence
  remain as a record (NFR3).
- **Scope containment:** the containment check (actual change set ⊆ declared
  set) remains, and unjustified scope expansion is stopped as before; no
  exclusion rule is added to the observed change set (FR19).

Authentication, authorization, XSS, SQL injection, and CSRF are not
applicable: the deliverables are protocol documents, agent prompts, and Python
tests, with no UI surface and no data model (assumption A-5).

## Error Handling

The stop conditions this feature defines, and the outcome of each:

| Condition | Route | Outcome |
|---|---|---|
| Verdict "the goal needs reconsideration" (FR9) | classification gate (batch), Codex or Claude | Stop unconditionally; Claude's disagreement does not override it. |
| Evidence IDs not named (FR10, FR13) | classification gate (batch) | Do not adopt the "specification gap" verdict; stop. |
| `in_progress` / `failed` tasks present at replanning (FR4) | `workflow-patch.md` | Current protocol error, unchanged. |
| Change touches plan / task / requirement metadata (FR16) | wording-correction route | Route is inapplicable; the change goes through the normal rework / SPEC-change route. |
| Deviation lacking the "existing acceptance criterion would be dropped" evidence (FR19) | implement | Not auto-added to the declaration; the containment check stops unjustified scope expansion. |
| `category: security` / `category: license` / `reversible: false` (NFR2) | fail-closed classification | Immediate abort, at unchanged strength. |
| No source for the goal (EC-7) | create-spec | Connects to FR20's TBD; handling not yet settled. |

Every stop leaves its reason and evidence as a record, and no batch-mode stop
raises a confirmation nobody can answer (NFR3).

## Performance Optimization

Not applicable. No performance goals are stated in the requirements.

## Success Criteria

- [ ] All functional requirements FR1–FR19 are implemented and covered by the
      test scenarios above (FR20 remains TBD; see Open Questions).
- [ ] All acceptance criteria AC-1 through AC-11 are satisfied.
- [ ] `python3 -m unittest discover -s tests` passes in full (AC-11, NFR5).
- [ ] Security requirements are satisfied: fail-closed strength for security /
      license / `reversible: false` is unchanged (NFR2), verified by TS-4.
- [ ] Existing `tests/` modules stay green or are updated consistently with
      this feature's changes, with no guard deleted (NFR8, TS-10).
- [ ] `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` carry the same raised version (NFR6,
      TS-9).
- [ ] Documents cite the existing SSOTs rather than restating their rules
      (NFR1).
- [ ] FR1–FR19 are delivered as a single feature without splitting (NFR7).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- [ ] FR20: Handling of pre-existing features without a `goal` block —
      the nine answers gathered here decide only goal persistence on the new
      create-spec route; retroactive treatment of existing features (backfill
      versus leaving the classification gate inapplicable and falling back to
      the previous stop) is not touched by any of the answers. To be settled
      during create-plan's TBD resolution.

## Assumptions

These are requirements-analyst's recorded assumptions, carried over unchanged.

- **A-1:** As a consequence of "verbatim storage", no size limit or
  summarization rule is introduced for the goal. Truncation breaks verbatimness
  and is therefore not an option (derived from answer 1; not a new decision).
- **A-2:** This feature's deliverables are markdown protocol documents, agent
  prompts, and Python tests under `tests/`; changes to runtime scripts
  (`scripts/*.py`) or hooks are not currently seen as required.
  `.claude/rules/hook-tests.md`'s `run-destructive-guard.py` becomes necessary
  only when `em-workflow/hooks/destructive-guard.py` is changed.
- **A-3:** If the new classification gate adds a `gate_id`, follow
  `references/gate-option-vocabulary.md`'s correspondence rule (option_id
  declaration under the `## Gate option vocabulary` section) and the
  corresponding check under `tests/`.
- **A-4:** FR17's referenced-side scanning takes the form of the orchestrator
  resolving paths into `resolved_input_paths` before passing them to the
  analyst, so that the discipline of workers performing no filesystem discovery
  of their own is preserved.
- **A-5:** The design step is skipped. The deliverables have no UI surface, no
  data model, and no design-system inputs.

## Design Step

Skipped. Resolved at gate `create-spec.design-step` with option `ask_user`; the
user confirmed skipping. The deliverables are only em-workflow's markdown
protocol documents, agent prompts, and the Python tests under `tests/`; they
carry no UI surface, data model, or design-system input, and no design system
exists in the repository (`design_system_candidates` is empty).

## References

- Requirements document (Japanese, authoritative for requirement statements):
  `feature-docs/goal-vs-spec-divergence/REQUIREMENTS.md`
- `goal` block definition (FR1): `em-workflow/references/workflow-schema.md`
- `replace_all` permission condition and `preserve` (FR4, FR5):
  `em-workflow/references/workflow-patch.md`
- SPEC-change transition, Section 10 (FR6):
  `em-workflow/references/rework-task-synthesis.md`
- Fail-closed classification (FR11, NFR2):
  `em-workflow/references/question-resolution.md`
- Question / answer structure (NFR1):
  `em-workflow/references/question-packet-schema.md`
- gate_id / option_id correspondence rule (A-3):
  `em-workflow/references/gate-option-vocabulary.md`
- Audit-record persistence (FR14): `em-workflow/references/phase-state.md`
- Plugin version bump rule (NFR6): `.claude/rules/core-plugin-version-bump.md`
