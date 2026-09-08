# Feature: assumptions-reversible-criteria

## Overview

The meaning that `assumptions[].reversible`'s gate assumes and the meaning a
worker writes have diverged, so the fail-closed irreversibility arm can fire on
an assumption that is not genuinely irreversible. This feature states the
judgement criterion for `assumptions[].reversible` in the SSOT that owns the
field and makes it binding on every worker that can emit a question packet. The
strength of the fail-closed classification's four abort arms is unchanged; only
what legitimately populates the irreversibility arm's input is narrowed.

Requirements document: `feature-docs/assumptions-reversible-criteria/REQUIREMENTS.md`.

## Objectives

- A worker must never attach `reversible: false` to a preserved constraint, an
  invariant, or a fact pinned by an existing test, so that the fail-closed
  irreversibility arm fires only on genuinely irreversible operations.
- The criterion for `assumptions[].reversible` is stated in the SSOT that owns
  the field and is binding on every worker that can emit a question packet, so
  the meaning the field's gate assumes and the meaning a worker writes stop
  diverging.
- The strength of the fail-closed classification's four abort arms (security /
  license / spec-change / irreversibility) is preserved unchanged; this feature
  narrows what legitimately populates the irreversibility arm's input, never the
  arm itself.

## User Stories

The resolved requirements carry no user stories: this feature introduces no user
interface and no end-user-facing behaviour. Its acceptance criteria are
enumerated under Success Criteria below, each tagged with the requirement it
belongs to.

## Technical Requirements

### Functional Requirements

- **FR1 — SSOT definition of `assumptions[].reversible`:**
  `em-workflow/references/question-packet-schema.md`'s
  `assumptions[].reversible` row (currently the bare word "Boolean", line 56)
  states the judgement criterion: `false` is attached only to an assumption
  about an operation that cannot be undone once applied; a preserved
  constraint, an invariant, or a fact pinned by an existing test is `true`.
  This document is the single place the criterion is defined.

- **FR2 — The criterion binds the packet-capable worker agent prompts:**
  `em-workflow/agents/requirements-analyst.md`,
  `em-workflow/agents/implementation-planner.md`, and
  `em-workflow/agents/rework-planner.md` each carry the criterion as a binding
  rule on the worker, pointing at the FR1 SSOT rather than restating its full
  text.

- **FR3 — The criterion binds the packet-capable worker contracts:**
  `em-workflow/references/contracts/analyst-contract.md`,
  `planner-contract.md`, and `rework-planner-contract.md` each carry the same
  binding pointer as FR2, so a worker that reads only its contract is bound
  identically to one that reads only its prompt.

- **FR4 — The fail-closed arms keep their current strength:**
  `em-workflow/references/question-resolution.md`'s Fail-closed classification
  is not weakened: the irreversibility arm, the `category: security` /
  `category: license` arms, the `category: spec-change` arm with its single
  `rework.spec-change` routed exception, the Precedence reservation, the
  surviving-abort enumeration, the batch relaxation, and the Classification
  gate's direction-2 irreversibility check all keep their current behaviour and
  their worker-declared-basis paragraph. Any edit here is a citation of FR1's
  criterion, never a change of what aborts.

- **FR5 — Recurrence-detecting tests:** A new stdlib-only `unittest` module
  under `tests/` pins FR1 (the criterion's presence and its two halves in
  question-packet-schema.md), FR2 and FR3 (the criterion present in all three
  prompts and all three contracts, asserted per file so a single omission
  fails), and FR4 (the existing arm wording retained), each with a
  negative/non-vacuity proof against forged text in the manner of
  `tests/test_batch_codex_autonomous_decisions_version_bump.py`.

- **FR6 — A worked counter-example fixture for the reported shape:** A
  question-packet fixture under
  `em-workflow/references/fixtures/question-packet/` carries an assumption of
  the reported A3 shape — a constraint that survives because an existing test
  pins it — declared `reversible: true`, as the positive companion to the
  existing `category-fail-closed/valid-irreversible-assumption-blocking/`
  fixture, and is accepted by `scripts/validate-worker-output.py` both directly
  and in a full fixture sweep.

- **FR7 — Plugin version bump in both registries:**
  `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry of
  `.claude-plugin/marketplace.json` move from the 0.1.64 baseline to the same
  strictly greater patch version; the `em-review` entry (0.5.7) is untouched.

### Non-Functional Requirements

- **NFR1 — SSOT discipline:** The criterion is defined once (FR1). Every other
  site cites it; no site restates it in a way that can drift, matching the
  repository's existing one-statement-per-fact convention.

- **NFR2 — No new gate identifier and no policy change:** No `gate_id` is
  added, removed, or renamed, and `em-workflow/references/batch-policies.yaml`
  is unchanged, so `scripts/check-plugin-invariants.py`'s gate-id coverage
  check stays satisfied.

- **NFR3 — No feature-docs task identifiers in plugin documents:** No
  `task00NN` identifier or `feature-docs/` path is cited inside any
  `em-workflow/` document as attribution, following the existing convention
  pinned by the current test suite.

- **NFR4 — Test conventions:** New tests live in the repository-root `tests/`
  directory as `test_*.py`, import only the standard library, and
  `python3 -m unittest discover -s tests` passes with no pre-existing test
  removed or weakened.

- **NFR5 — Genuinely irreversible declarations keep working:** The validator's
  `assumptions[].reversible` boolean type check is unchanged, and the existing
  `valid-irreversible-assumption-blocking` fixture keeps declaring
  `reversible: false` and keeps being accepted, so this feature removes no
  ability to declare a real irreversible operation.

- **NFR6 — Documentation minimality:** The added text states the criterion and
  nothing else: no justification narrative, no reference to the originating
  incident, and no restatement of the resolution procedure that
  `references/question-resolution.md` owns.

## Implementation Approach

### Architecture

The change surface is documentation, one fixture, tests, and two manifests. The
criterion is defined once and cited from six worker-facing documents:

```
em-workflow/references/question-packet-schema.md   <- FR1: the criterion (SSOT)
        ^                    ^
        | cites              | cites
        |                    |
  agents/                references/contracts/
    requirements-analyst.md    analyst-contract.md
    implementation-planner.md  planner-contract.md
    rework-planner.md          rework-planner-contract.md
              (FR2)                    (FR3)

em-workflow/references/question-resolution.md      <- FR4: unchanged in strength,
                                                      may cite FR1's criterion
```

**Component Diagram:**

- FR1 site: the `assumptions[].reversible` row of the question-packet schema —
  the only place the criterion's full wording exists (NFR1).
- FR2 sites: the three agent prompts of the workers whose capability entry
  permits `status: needs_user_input`.
- FR3 sites: the three worker contracts of those same three workers, so prompt
  readers and contract readers are bound identically.
- FR4 site: the fail-closed classification, whose arms and worker-declared-basis
  paragraph are retained; edits there are citations only.
- FR6 site: the question-packet fixture tree, gaining the `reversible: true`
  positive companion to the existing irreversible fixture.
- FR5/NFR4 site: the repository-root `tests/` directory.
- FR7 sites: the two manifests.

### Data Flow

```
worker forms an assumption
  -> applies FR1's criterion (via its prompt (FR2) or its contract (FR3))
  -> writes assumptions[].reversible
  -> validate-worker-output.py checks the boolean type only (NFR5, unchanged)
  -> question-resolution.md's fail-closed irreversibility arm reads the value
     (FR4, behaviour unchanged)
```

### API Design

No API surface is added or changed.

### Database Schema

No data model is added or changed.

### Dependencies

**Internal Dependencies:**

- `em-workflow/references/question-packet-schema.md`: owns
  `assumptions[].reversible`; FR1's definition site.
- `em-workflow/references/question-resolution.md`: owns the fail-closed
  classification whose irreversibility arm consumes the field (FR4).
- `em-workflow/scripts/validate-worker-output.py`: its `WORKER_CAPABILITIES`
  table determines the three packet-capable workers (FR2, FR3), and its boolean
  type check on `assumptions[].reversible` is unchanged (NFR5).
- `em-workflow/references/batch-policies.yaml` and
  `scripts/check-plugin-invariants.py`: unchanged; the gate-id coverage check
  must stay satisfied (NFR2).
- `.claude/rules/core-plugin-version-bump.md`: the two-registry bump rule (FR7).

**External Dependencies:**

None. New tests import only the standard library (NFR4).

### File Structure

```
em-workflow/
├── references/
│   ├── question-packet-schema.md            # FR1: criterion defined here
│   ├── question-resolution.md               # FR4: strength retained
│   ├── contracts/
│   │   ├── analyst-contract.md              # FR3
│   │   ├── planner-contract.md              # FR3
│   │   └── rework-planner-contract.md       # FR3
│   └── fixtures/question-packet/            # FR6: new reversible:true fixture
├── agents/
│   ├── requirements-analyst.md              # FR2
│   ├── implementation-planner.md            # FR2
│   └── rework-planner.md                    # FR2
└── .claude-plugin/plugin.json               # FR7
.claude-plugin/marketplace.json              # FR7
tests/                                       # FR5, NFR4
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/assumptions-reversible-criteria/**`
- `test-docs/assumptions-reversible-criteria/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

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

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (FR1): question-packet-schema.md's `assumptions[].reversible`
      row contains the irreversible-operation half and the preserved-constraint
      half of the criterion.
- [ ] **TS-2** (FR2): Each of `agents/requirements-analyst.md`,
      `agents/implementation-planner.md`, `agents/rework-planner.md` carries
      the criterion (one assertion per file, so one missing file fails alone).
- [ ] **TS-3** (FR3): Each of `contracts/analyst-contract.md`,
      `planner-contract.md`, `rework-planner-contract.md` carries the criterion
      (one assertion per file).
- [ ] **TS-4** (FR4, NFR5): question-resolution.md still carries all four abort
      arms, the Precedence reservation, the surviving-abort enumeration and the
      worker-declared-basis paragraph.
- [ ] **TS-7** (FR7): Version-bump module: both registries past the 0.1.64
      baseline and mutually equal, em-review pinned at 0.5.7, with per-matcher
      negative proofs.
- [ ] **TS-8** (NFR2, NFR3, NFR4): No new `gate_id` appears in any changed
      plugin document and `batch-policies.yaml` is unchanged; new test modules
      import only the standard library.

### Integration Tests

- [ ] **TS-6** (FR6, NFR5): The new fixture parses, declares `reversible: true`
      on a test-pinned constraint assumption, and `validate-worker-output.py`
      accepts it directly and under the fixture sweep; the pre-existing
      irreversible fixture still declares `reversible: false` and is still
      accepted.

### E2E Tests

**Existing E2E tests**: None (no E2E input paths were resolved for this
feature).
**Run command**: Not detected

### Edge Cases

- [ ] **TS-5** (FR5, NFR4): Negative proof: the criterion matcher rejects
      forged document text with the criterion removed, and the non-vacuity
      companion shows it accepts forged text containing it.

### Performance Tests

Not applicable: no runtime behaviour changes.

## Security Considerations

No security surface is added or changed. The `category: security` abort arm of
the fail-closed classification keeps its current behaviour and its
non-overridable wording (FR4).

## Error Handling

No new error codes or error paths are introduced.
`scripts/validate-worker-output.py` keeps only its existing boolean type check
on `assumptions[].reversible`; the criterion is a semantic judgement that is not
machine-checkable (NFR5).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] **AC-1 (FR1):** `em-workflow/references/question-packet-schema.md`'s
      `assumptions[].reversible` row states both halves of the criterion —
      `false` only for an operation that cannot be undone once applied, and
      `true` for a preserved constraint / invariant / test-pinned fact.
- [ ] **AC-2 (FR2):** Each of the three packet-capable agent prompts carries
      the criterion, asserted per file.
- [ ] **AC-3 (FR3):** Each of the three packet-capable worker contracts carries
      the criterion, asserted per file.
- [ ] **AC-4 (FR4):** The fail-closed classification's four abort arms and
      their non-overridable wording are byte-for-byte retained; the existing
      pins in `tests/test_question_resolution_doc.py`,
      `tests/test_classification_gate.py`,
      `tests/test_spec_change_origin_binding.py`,
      `tests/test_batch_stop_contract.py` and `tests/test_batch_policies.py`
      still pass unmodified.
- [ ] **AC-5 (FR5):** The new test module fails when the criterion text is
      removed from any one of the seven documents (proved against forged
      content), and passes against the real tree.
- [ ] **AC-6 (FR6):** The new fixture declares an assumption whose statement is
      a test-pinned preserved constraint and whose `reversible` is `true`, and
      `scripts/validate-worker-output.py` exits 0 on it directly and in the
      fixture sweep.
- [ ] **AC-7 (FR7):** Both registries report the same version, strictly greater
      than 0.1.64 at the patch component, with major.minor unchanged and the
      em-review entry left at 0.5.7.
- [ ] **AC-8 (DoD):** `python3 -m unittest discover -s tests` passes.
- [ ] **AC-9 (reproduction):** An assumption of the reported A3 shape — a
      constraint preserved because a test pins it — is classified
      `reversible: true` under the documented criterion, so it no longer names
      a question into the irreversibility arm.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every FR and NFR is `status: ok`.

## Assumptions

These assumptions were resolved by requirements-analyst and are carried here
unchanged.

| ID | Assumption | Impact | Reversible |
|----|------------|--------|------------|
| a1 | Remedy (a) from the task description is adopted and remedy (b) is out of scope: the fail-closed irreversibility arm's worker-declared basis is left as it is, and only the criterion for populating it is documented. | high | true |
| a2 | The criterion is written once, in question-packet-schema.md, and the six worker-facing documents cite it rather than duplicating its full wording. | medium | true |
| a3 | The prompt/contract coverage is the three workers whose capability entry permits `status: needs_user_input` — requirements-analyst, implementation-planner, rework-planner — not all five envelope workers. | medium | true |
| a4 | No runtime behaviour changes: validate-worker-output.py keeps only its boolean type check on `assumptions[].reversible`, because the criterion is a semantic judgement that is not machine-checkable. | medium | true |
| a5 | The version bump is patch-level from the 0.1.64 baseline recorded in both registries. | low | true |
| a6 | The change surface is limited to Markdown/JSON documents under `em-workflow/`, one new question-packet fixture, new and existing test modules under `tests/`, and the two manifests; no hook or script behaviour changes. | medium | true |

Their recorded reasons:

- **a1**: The task description states (a) has the smaller change surface and
  does not weaken the fail-closed arms, and the (b) direction was already
  addressed for batch runs by the merged `batch-codex-autonomous-decisions`
  feature.
- **a2**: The repository's SSOT discipline treats a duplicated normative
  sentence as drift risk; the task's expectation (a) is satisfied by a binding
  pointer.
- **a3**: `em-workflow/scripts/validate-worker-output.py`'s
  `WORKER_CAPABILITIES` table allows `needs_user_input` only for those three;
  spec-writer and designer cannot return a `question_packet` and therefore can
  never emit `assumptions[]`, so guidance in their documents would be
  unreachable text.
- **a4**: The distinction between an irreversible operation and a preserved
  constraint cannot be derived from the packet's structure; the existing check
  is type-level only.
- **a5**: `.claude/rules/core-plugin-version-bump.md` prescribes patch
  granularity for behaviour corrections, and both registries currently read
  0.1.64.
- **a6**: Every acceptance criterion above resolves to document text, a
  fixture, tests, or a version value.

## Design Step

Skipped. The feature changes SSOT Markdown documents, agent prompts, one JSON
fixture, tests and two manifests. It introduces no user interface, no rendered
artifact, no new file format, and no design-system surface;
`design_system_candidates` is empty and zero candidates were detected.

## References

- Requirements document: `feature-docs/assumptions-reversible-criteria/REQUIREMENTS.md`
- `em-workflow/references/question-packet-schema.md`: SSOT for
  `assumptions[].reversible`
- `em-workflow/references/question-resolution.md`: fail-closed classification
- `em-workflow/scripts/validate-worker-output.py`: `WORKER_CAPABILITIES` and the
  `assumptions[].reversible` type check
- `em-workflow/references/batch-policies.yaml`,
  `scripts/check-plugin-invariants.py`: gate-id coverage
- `.claude/rules/core-plugin-version-bump.md`: two-registry version bump rule
