# Feature: spec-file-set-completeness

## Overview

A SPEC that declares a closed change set is currently not satisfiable by the workflow's own execution: the artifacts em-workflow is obliged to generate fall outside the declaration. This feature adds a "Declared Change Set" section to em-workflow's own SPEC and REQUIREMENTS templates, whose fixed default membership is `feature-docs/{feature}/**` and `test-docs/{feature}/**`. The change is documentation plus tests only; containment verification semantics at verify time are unchanged.

Requirements source: `feature-docs/spec-file-set-completeness/REQUIREMENTS.md`.

## Objectives

- A SPEC that declares a closed change set can be satisfied by the workflow's own execution: the artifacts em-workflow is obliged to generate (per-task test records, and every feature-docs artifact produced after SPEC authoring) are inside the declaration from the moment the SPEC is written, so implement/review/verify never reach a dead end whose only exit is a SPEC edit that `em-workflow/references/rework-task-synthesis.md` forbids (it routes such an edit to `gate_id: rework.spec-change`).
- The fix is inherited, not repeated: it lives in the two document templates spec-writer renders, so every future feature gets the correct default membership without per-feature remediation and without a verify-side exclusion rule.
- Containment stays strong: nothing is subtracted from the observed change set at verification time; the declaration is widened to match reality instead.

## User Stories

### US1: A SPEC author declares a change set that includes the workflow's own outputs
As a SPEC author (the spec-writer worker), I want the rendered SPEC and REQUIREMENTS documents to already carry `feature-docs/{feature}/**` and `test-docs/{feature}/**` as default members of the declared change set, so that the artifacts em-workflow is obliged to generate are inside the declaration from the moment the SPEC is written.

**Acceptance Criteria:**
- [ ] AC-1: `em-workflow/references/templates/spec-document.md` contains a top-level heading `## Declared Change Set` inside its fenced template body, whose position is after the `### File Structure` subsection and before `## Test Scenarios`.
- [ ] AC-2: `em-workflow/references/templates/requirements-document.md` contains `### 9.4 宣言された変更集合` under `## 9. 制約条件`, and every pre-existing top-level section heading (`## 1. 概要` .. `## 15. 参考資料`) is present with its number and title unchanged.
- [ ] AC-3: Both new sections contain the literals `feature-docs/{feature}/**` and `test-docs/{feature}/**`.
- [ ] AC-4: Both new sections name `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md` and `retrospect.yaml` as feature-docs members and `{T}.tests.yaml` as the test-docs member, and each cites `implement-phase.md` (for the test record) and the phase documents / `references/phase-state.md` (for the feature-docs artifacts) rather than restating their rules.
- [ ] AC-11: Both additions sit inside their document's fenced template body; the spec-document addition is English and uses `{placeholder}` form; the requirements-document addition is Japanese and uses the `### N.M` numbering form.

### US2: A workflow run reaches verify without a forbidden SPEC edit
As a workflow operator, I want the declaration to be a superset assertion whose default entries survive unless explicitly removed, so that implement/review/verify never dead-ends into a SPEC edit that `rework-task-synthesis.md` routes to `gate_id: rework.spec-change`, and so that a declared path which never materializes is not a violation.

**Acceptance Criteria:**
- [ ] AC-5: Both new sections state that the default entries remain unless explicitly removed, that the actual change set must be CONTAINED IN the declaration, and that a declared path which never materializes is not a violation — naming the zero-implement-task feature (no `test-docs/{feature}/` generated at all) as the concrete case.
- [ ] AC-6: `git diff --name-only` for the change lists no path under `em-workflow/references/` other than the two template files, and no path under `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/` or `em-workflow/references/contracts/`. No document introduces a rule excluding workflow-generated artifacts from the observed change set at verification time.
- [ ] AC-14: No test, document or script added by this feature makes the new section mandatory for an existing SPEC, or fails a SPEC that declares no closed file set; the existing feature-docs of completed features remain byte-unchanged.

### US3: Completed features are not rewritten
As a workflow operator, I want the already-consistent state of completed features pinned by a test rather than remediated by an edit, so that no completed feature's documents are rewritten and the consistent state cannot silently regress.

**Acceptance Criteria:**
- [ ] AC-7: `git diff --name-only` for the change lists no path under `feature-docs/recycled-task-id-consistency/`, and a test asserts that `feature-docs/recycled-task-id-consistency/SPEC.md` and `REQUIREMENTS.md` still enumerate `test-docs/recycled-task-id-consistency/**` in their change-containment statements.
- [ ] AC-8: `git diff --name-only` for the change is a subset of {`em-workflow/references/templates/spec-document.md`, `em-workflow/references/templates/requirements-document.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `feature-docs/spec-file-set-completeness/**`, `test-docs/spec-file-set-completeness/**`, the new/extended module(s) under `tests/`}.
- [ ] AC-9: `em-workflow/.claude-plugin/plugin.json` reads `"version": "0.1.41"`, and the `em-workflow` entry of `.claude-plugin/marketplace.json` reads `"version": "0.1.41"`; the `em-review` entry is unchanged.
- [ ] AC-10: A repository-wide search finds the default-membership enumeration only in the two templates; no third document under `em-workflow/references/`, `em-workflow/agents/` or `em-workflow/skills/` restates it.
- [ ] AC-12: `python3 -m unittest discover -s tests` passes from the repository root with every pre-existing test module byte-unchanged.
- [ ] AC-13: The new test module exists, is discovered by `unittest discover`, implements TS-1..TS-13, imports nothing outside the Python standard library, and gives every new matcher a negative-proof test that flags the captured pre-change template text.

## Technical Requirements

### Functional Requirements

- **FR1 - SPEC template gains a Declared Change Set section:** `em-workflow/references/templates/spec-document.md` gains, inside its outer fenced ```markdown template body, a new top-level section `## Declared Change Set`, positioned after the `### File Structure` subsection of `## Implementation Approach` and before `## Test Scenarios`. The section carries (a) a `{placeholder}` list for the feature-specific paths the SPEC author enumerates and (b) a fixed default-membership block (FR3, FR4) that is present in every rendered SPEC.
- **FR2 - REQUIREMENTS template gains the equivalent section:** `em-workflow/references/templates/requirements-document.md` gains, inside its fenced template body, a new subsection `### 9.4 宣言された変更集合` under the existing `## 9. 制約条件`, carrying the same default membership as FR1's section. It is added as a subsection specifically so that every existing top-level section number (1..15) and title stays unchanged.
- **FR3 - Default membership is both workflow-output roots:** Both new sections state that a feature's declared change set includes, by default, `feature-docs/{feature}/**` AND `test-docs/{feature}/**`. Restricting the default to `test-docs/` alone is explicitly rejected: the feature-docs root is what carries the artifacts generated after the SPEC is written, so omitting it reproduces the same dead end one phase later.
- **FR4 - The default membership enumerates what the two roots cover, by citation:** Both new sections enumerate the workflow-generated artifacts the two roots cover, so a SPEC author does not have to rediscover them: under `feature-docs/{feature}/` — `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and any design artifacts the design step produces; under `test-docs/{feature}/` — the per-task `{T}.tests.yaml` records that `em-workflow/references/implement-phase.md` mandates (`tests_yaml_path` = `test-docs/{feature}/{T}.tests.yaml`, written in the task worktree and merged into the parent branch with the implementation). Each entry CITES the phase document that owns the artifact's generation rather than restating that document's rules.
- **FR5 - Default-inclusive, superset semantics stated explicitly:** Both new sections state two properties of the declaration: (a) the default entries are part of it unless the SPEC author explicitly removes them — removal is a deliberate narrowing, never an omission by silence; and (b) the declaration is a SUPERSET assertion — the actual change set must be CONTAINED IN it, so a declared path that never materializes is not a violation. The zero-implement-task case is named as the concrete instance: a feature that produces no implement tasks generates no `test-docs/{feature}/` directory at all, and the declared `test-docs/{feature}/**` entry is still correct.
- **FR6 - Containment verification semantics are unchanged:** No document gains a rule that excludes workflow-generated artifacts from the observed change set at verification time. Every committed artifact remains part of the actual change set exactly as today. Not modified by this feature: `em-workflow/references/implement-phase.md`, `review-phase.md`, `review-protocol.md`, `phases/create-spec-phase.md`, `phases/create-plan-phase.md`, `rework-task-synthesis.md`, everything under `em-workflow/references/contracts/`, `em-workflow/scripts/validate-worker-output.py`, and everything under `em-workflow/hooks/`, `em-workflow/agents/`, `em-workflow/skills/`.
- **FR7 - Completed features are not rewritten; the already-consistent state is pinned by a test:** `feature-docs/recycled-task-id-consistency/SPEC.md` and `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md` are NOT modified: at the base revision they already enumerate `test-docs/recycled-task-id-consistency/**` in their change-containment requirement (SPEC.md FR8 / AC-8; REQUIREMENTS.md's corresponding constraint), so there is nothing to remediate. Instead, a document-contract test pins that already-consistent state so it cannot silently regress.
- **FR8 - Change containment for this feature:** The change touches only: `em-workflow/references/templates/spec-document.md`; `em-workflow/references/templates/requirements-document.md`; `em-workflow/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; artifacts under `feature-docs/spec-file-set-completeness/**`; artifacts under `test-docs/spec-file-set-completeness/**`; and the new or extended test module(s) under `tests/`. This enumeration is itself an instance of what FR1-FR5 add to the templates.
- **FR9 - Plugin version bump to 0.1.41 in both registries:** As part of the same change, `em-workflow/.claude-plugin/plugin.json`'s `version` goes from `0.1.40` to `0.1.41` (patch), and the `plugins[]` entry of the root `.claude-plugin/marketplace.json` whose `name` is `em-workflow` goes from `0.1.40` to `0.1.41`. The `em-review` entry is not touched and no other field of either file changes.

### Non-Functional Requirements

- **NFR1 - Documentation-and-tests-only change:** No executed behaviour changes. No file under `em-workflow/hooks/` or `em-workflow/scripts/` is edited, and no agent prompt or skill under `em-workflow/agents/` or `em-workflow/skills/` is edited. Deliverables are the two template documents, this feature's feature-docs artifacts, the version bump, and new tests.
- **NFR2 - SSOT non-duplication:** The default-membership enumeration exists only in the two templates — one statement per template, no third document restating it. Each enumerated entry cites the document that owns the artifact's generation (`implement-phase.md` for `{T}.tests.yaml`, the create-spec / create-plan / review / verify phase documents and `references/phase-state.md` for the feature-docs artifacts) instead of copying its rules.
- **NFR3 - Local style consistency of both templates:** `spec-document.md`'s addition stays in English, uses the existing `{placeholder}` convention and `## ` / `### ` heading structure, and sits inside the outer fenced ```markdown block (not outside it). `requirements-document.md`'s addition stays in Japanese, follows its `### N.M` numbering scheme, and likewise sits inside its fenced template body. Neither addition carries rationale beyond what the requirements state.
- **NFR4 - The existing suite stays green with every pre-existing module unmodified:** `python3 -m unittest discover -s tests` passes from the repository root with every pre-existing module under `tests/` unmodified — including `tests/test_reference_sweep.py`, `tests/test_check_plugin_invariants.py`, `tests/test_worker_contracts_create_spec.py`, `tests/test_worker_contract_docs.py` and `tests/test_recycled_task_id_consistency.py`. No existing module currently asserts anything about either template, so the additions must not break the repository-wide reference and invariant sweeps either.
- **NFR5 - New verification is Python unittest document-contract tests with negative proofs:** New verification is added as Python `unittest` document-contract tests under `tests/` (stdlib only, no third-party imports, `tests/test_*.py`), runnable by `python3 -m unittest discover -s tests` from the repository root; the project defines no build command, no format command and no E2E infrastructure. They follow the repository pattern established by `tests/test_recycled_task_id_consistency.py`: module-level path constants, heading-based section slicing, a `_normalize_ws` helper for prose assertions with raw text used only for byte-identity assertions, and at least one negative-proof test per NEW matcher demonstrating that the matcher flags the captured pre-change template text (a test that can never fail is not a test). Retention matchers need no negative proof.
- **NFR6 - No retroactive obligation on SPECs without a closed declaration:** A SPEC that does not declare a closed file set at all stays valid and is unaffected: nothing added by this feature rejects such a SPEC, requires it to be rewritten, or makes the new section mandatory for documents already written. The template change affects documents generated from the templates going forward; existing feature-docs are untouched.

## Implementation Approach

### Architecture

**System Architecture:**

N/A — this change introduces no runtime layers. It edits two markdown template documents that the spec-writer worker renders, plus one Python unittest module. The relevant structure is document-level, not layered:

```
em-workflow/references/templates/
├── spec-document.md            # + "## Declared Change Set" (FR1)
└── requirements-document.md    # + "### 9.4 宣言された変更集合" (FR2)
                                #   both carry the same default membership (FR3, FR4, FR5)
```

**Component Diagram:**

```
spec-document.md ─────┐
                      ├─► rendered by spec-writer ─► feature-docs/{feature}/SPEC.md
requirements-document.md ─┘                       ─► feature-docs/{feature}/REQUIREMENTS.md

tests/test_*.py ─► document-contract assertions over both templates (TS-1..TS-13)
```

### Data Flow

```
template edit → spec-writer renders → SPEC declares feature-docs/{feature}/** and test-docs/{feature}/**
              → implement/review/verify produce artifacts under those roots
              → verify observes the full committed change set (unchanged semantics, FR6)
              → actual change set is CONTAINED IN the declaration (FR5)
```

### API Design

N/A — this change adds no API, endpoint or request/response surface.

### Database Schema

N/A — this change adds no table, schema or entity relationship.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: owns the generation of the per-task `{T}.tests.yaml` record (`tests_yaml_path` = `test-docs/{feature}/{T}.tests.yaml`); FR4 cites it rather than restating it.
- `em-workflow/references/phase-state.md` and the create-spec / create-plan / review / verify phase documents: own the generation of the feature-docs artifacts; FR4/NFR2 cite them rather than restating them.
- `em-workflow/references/rework-task-synthesis.md`: routes a SPEC edit to `gate_id: rework.spec-change`; it is the constraint the objectives avoid hitting, and it is not modified (FR6).
- `tests/test_recycled_task_id_consistency.py`: the repository test pattern the new module follows (NFR5), unmodified (NFR4).

**External Dependencies:**
- None. New tests import nothing outside the Python standard library (NFR5).

### File Structure

```
em-workflow/
├── references/templates/
│   ├── spec-document.md              # FR1
│   └── requirements-document.md      # FR2
└── .claude-plugin/plugin.json        # FR9: 0.1.40 → 0.1.41
.claude-plugin/marketplace.json       # FR9: em-workflow entry 0.1.40 → 0.1.41
feature-docs/spec-file-set-completeness/**
test-docs/spec-file-set-completeness/**
tests/                                # new or extended document-contract module(s) (NFR5)
```

## Declared Change Set

The change set this SPEC declares (FR8, AC-8) is exactly:

- `em-workflow/references/templates/spec-document.md`
- `em-workflow/references/templates/requirements-document.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `feature-docs/spec-file-set-completeness/**`
- `test-docs/spec-file-set-completeness/**`
- the new or extended test module(s) under `tests/`

The declaration is a SUPERSET assertion: the actual change set must be CONTAINED IN it, and a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1): Assert `## Declared Change Set` is present in spec-document.md and that its normalized index is greater than that of `### File Structure` and less than that of `## Test Scenarios`.
- [ ] TS-2 (FR1, NFR3): Assert the new SPEC-template section lies inside the outer fenced ```markdown block (its offset falls between the opening and closing fence).
- [ ] TS-3 (FR2): Assert `### 9.4 宣言された変更集合` is present in requirements-document.md and positioned after `### 9.3 スケジュール制約` and before `## 10. 想定される課題とリスク`.
- [ ] TS-5 (FR3): Assert both new sections contain `feature-docs/{feature}/**` and `test-docs/{feature}/**`.
- [ ] TS-6 (FR4): Assert both new sections enumerate all eight feature-docs members and the `{T}.tests.yaml` test-docs member, and cite `implement-phase.md`.
- [ ] TS-10 (FR9): Assert both registries read `0.1.41` and that the `em-review` marketplace entry is unchanged.

### Integration Tests
- [ ] TS-9 (FR7): Assert `feature-docs/recycled-task-id-consistency/SPEC.md` still lists `test-docs/recycled-task-id-consistency/**` in FR8 and AC-8, and that `REQUIREMENTS.md` still lists it in its corresponding constraint (pin test; retention matcher, no negative proof needed).
- [ ] TS-11 (NFR2): Assert the default-membership enumeration appears in exactly the two template files across `em-workflow/**` (duplication guard).

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] N/A — the project defines no E2E infrastructure (NFR5); the only project command is `python3 -m unittest discover -s tests`.

### Edge Cases
- [ ] TS-4 (FR2): Assert every pre-existing top-level heading `## 1. 概要` .. `## 15. 参考資料` is present with unchanged number and title (renumbering guard).
- [ ] TS-7 (FR5): Assert both new sections state the default-unless-removed rule and the containment (subset, not equality) rule, including the zero-implement-task non-violation case.
- [ ] TS-8 (FR6): Assert none of `implement-phase.md`, `review-phase.md`, `review-protocol.md`, `phases/create-spec-phase.md`, `phases/create-plan-phase.md`, `rework-task-synthesis.md` or `references/contracts/*` contains a verify-side exclusion rule for workflow-generated artifacts (negative assertion over a matcher for such a rule).
- [ ] TS-12 (NFR6): Assert no matcher added by this feature is applied to any file under `feature-docs/*/SPEC.md` as a mandatory-section requirement — a SPEC without a Declared Change Set section is not flagged by anything this feature adds.
- [ ] TS-13 (NFR5): Negative proofs: for each new matcher of TS-1, TS-3, TS-5, TS-6, TS-7 and TS-8, run it against a module-level captured pre-change sample of the corresponding template text and assert it reports absence; guard each sample for non-vacuity.

### Performance Tests
- [ ] N/A — no performance goals are defined for this change.

## Security Considerations

- **Authentication:** N/A — this change adds no authenticated surface.
- **Authorization:** N/A — this change adds no authorization decision.
- **Input Validation:** N/A — this change adds no runtime input path; the new tests read repository documents only.
- **Data Protection:** N/A — this change handles no sensitive data.
- **XSS Prevention:** N/A — no user interface.
- **SQL Injection Prevention:** N/A — no database.
- **CSRF Protection:** N/A — no web request surface.

## Error Handling

### Error Codes

N/A — this change defines no error codes; it changes no executed behaviour (NFR1).

### Error Flow

```
N/A — no runtime error path. Contract violations surface as unittest failures
(TS-1..TS-13) under `python3 -m unittest discover -s tests`.
```

## Performance Optimization

### Performance Goals

N/A — no performance goals are defined for this change.

### Optimization Strategies

N/A — no optimization is in scope.

### Caching Strategy

N/A — nothing is cached.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals — N/A, no performance goals are defined
- [ ] Security requirements are satisfied — N/A, no security requirements are defined
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC-1 .. AC-14 all hold (see US1/US2/US3 above and REQUIREMENTS.md section 11.1)
- [ ] `python3 -m unittest discover -s tests` passes from the repository root with every pre-existing test module byte-unchanged (AC-12)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None. No requirement has `status: tbd`; FR1..FR7 are recorded as `assumed` (see Assumptions below) and FR8, FR9, NFR1..NFR6 as `ok`.

**Assumptions carried into this specification:**

- A1 (high impact, reversible): The structural fix is placed in the SPEC / REQUIREMENTS templates as a new 'declared change set' section whose default membership includes the workflow-generated artifacts; containment verification semantics stay as they are today, treating every committed artifact as part of the actual change set (no verify-side exclusion). Reason: resolved for question `fix-locus` (packet create-spec-q0001) via batch codex consultation under `gate_id: create-spec.requirement-clarification`, whose policy sets `record_as_assumption: true`.
- A2 (high impact, reversible): The default declared set is both `test-docs/{feature}/**` and `feature-docs/{feature}/**`; the latter covers the artifacts generated after SPEC authoring (reviews/roundN.yaml, retrospect.yaml, VERIFICATION.md, tasks/, workflow.yaml, phase-state/). Reason: resolved for question `workflow-artifact-set` (packet create-spec-q0001) via batch codex consultation under the same gate.
- A3 (low impact, reversible): `feature-docs/recycled-task-id-consistency/SPEC.md` and `REQUIREMENTS.md` are not edited; their already-consistent state is pinned by a document-contract test only. Reason: resolved for question `recycled-feature-remediation` (packet create-spec-q0001) via batch codex consultation under the same gate.
- A4 (low impact, reversible): The plugin version is bumped 0.1.40 → 0.1.41 in both `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry of `.claude-plugin/marketplace.json`. Reason: repository convention (root CLAUDE.md); 0.1.40 verified as the current value in both files at the base revision.
- A5 (medium impact, reversible): The change is documentation plus tests only: no hook, script, agent prompt or skill behaviour changes. Reason: the fix locus (A1) is two markdown templates.
- A6 (medium impact, reversible): New verification is Python `unittest` document-contract tests under `tests/`, stdlib-only, with negative-proof coverage for each new matcher. Reason: the project's only test infrastructure is `python3 -m unittest discover -s tests`.
- A7 (low impact, reversible): The design step is skipped for this feature. Reason: `references/batch-policies.yaml` resolves `create-spec.design-step` in batch mode with `decide_autonomously`; this change has no user-visible surface, no UI, no new architecture and no data model.

## Implementation Phases (if applicable)

N/A — this change is delivered as a single phase: the two template edits (FR1..FR5), the version bump (FR9), and the new document-contract test module (NFR5), all inside the change set declared above (FR8).

## References

- REQUIREMENTS document: `feature-docs/spec-file-set-completeness/REQUIREMENTS.md`
- SPEC template (target of FR1): `em-workflow/references/templates/spec-document.md`
- REQUIREMENTS template (target of FR2): `em-workflow/references/templates/requirements-document.md`
- Owner of `{T}.tests.yaml` generation: `em-workflow/references/implement-phase.md`
- Owner of phase-state artifacts: `em-workflow/references/phase-state.md`
- SPEC-edit gate (`gate_id: rework.spec-change`): `em-workflow/references/rework-task-synthesis.md`
- Already-consistent precedent pinned by FR7: `feature-docs/recycled-task-id-consistency/SPEC.md`
- Test pattern followed by NFR5: `tests/test_recycled_task_id_consistency.py`
