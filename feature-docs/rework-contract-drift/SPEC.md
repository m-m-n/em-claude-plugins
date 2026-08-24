# Feature: rework-contract-drift

## Overview

The goal-vs-spec-divergence verify-origin rework (task0027–task0029) introduced or left open
four producer/consumer contract breaks, so the SPEC-change re-entry path that feature opened is
rejected at apply time instead of functioning end to end. This feature closes those four breaks,
replaces every rule restated away from its owning SSOT document with a citation of the owner, and
adds test coverage that fails against the pre-change tree.

The change surface is documentation, one agent prompt, one validation script, and stdlib
`unittest` tests. There is no UI, no API, no database, and no E2E infrastructure.

Requirements source: `feature-docs/rework-contract-drift/REQUIREMENTS.md` (Japanese). This
document renders the same requirements in implementation terms and adds nothing to them.

**Design step: SKIPPED.** There is no UI surface — no screen, component, style, or design token
is created or altered — so no design artifact is produced for this feature.

**FR-number disambiguation (assumption A4):** this SPEC's FR7 (phase-state `schema_version`) is a
DIFFERENT requirement from the goal-vs-spec-divergence SPEC's FR7 (the gate-passage invariant
cited inside this SPEC's FR3). Every mention of the latter in this document is written as
"goal-vs-spec-divergence SPEC FR7" and never as a bare "FR7".

## Objectives

- **BO1:** Close the four producer/consumer contract breaks that the goal-vs-spec-divergence
  verify-origin rework (task0027–task0029) introduced or left open, so that the SPEC-change
  re-entry path the previous feature opened actually functions end to end instead of being
  rejected at apply time.
- **BO2:** Eliminate the drift class itself: every rule restated away from its owning SSOT
  document is replaced by a citation of the owner, so a later edit to the owner cannot silently
  leave a stale copy behind.
- **BO3:** Make each closed drift detectable by the test suite. The full suite (2234 tests, green)
  detects none of the four defects today; a regression of any of them must fail a test after this
  feature.
- **BO4:** Preserve fail-closed strength. No change may open an unattended batch run to
  auto-classifying a security- or license-related rework into a SPEC.md change.

## User Stories

Not applicable. The resolved requirements produced no user stories; this feature has no end-user
interaction surface. The acceptance criteria that would otherwise sit under user stories are
listed under **Acceptance Criteria** below.

## Acceptance Criteria

- [ ] **AC1:** `agents/implementation-planner.md` and `contracts/planner-contract.md` no longer
      contain the `needs_update`-keyed re-planning condition; both cite
      `references/workflow-patch.md`'s Re-planning path.
- [ ] **AC2:** `test_replanning_producer_alignment.py`'s two-branch test asserts both owner-defined
      paths and no longer pins the `needs_update` literal; it fails against the pre-change prompt.
- [ ] **AC3:** `finding_stable_id` appears nowhere in the repository outside history — not in
      `workflow-patch.md`, not in `skills/develop/SKILL.md`, not in `question-packet-schema.md`,
      not in `question-resolution.md`, not in `rework-planner-contract.md`, not in
      `validate-worker-output.py`, not in `references/fixtures/`, and not in `tests/`.
- [ ] **AC4:** `references/workflow-schema.md` defines `failed_items[].category` as required, with
      the closed vocabulary
      `comprehensive | spec | security | performance | architecture | license | unknown`.
- [ ] **AC5:** `question-resolution.md` direction 2 cites that definition, and states the gate-side
      abort on `security`, `license`, `unknown`, missing, unreadable, or out-of-vocabulary in the
      same non-overridable wording direction 1 uses.
- [ ] **AC6:** A verify-origin case whose category is `unknown` still REACHES the classification
      gate (the verify phase does not abort it), and the gate then aborts it.
- [ ] **AC7:** SPEC.md, the VERIFICATION.md format, `verification_index`, the retrospect phase and
      the rework-planner are unchanged by FR3.
- [ ] **AC8:** `validate-worker-output.py` rejects an out-of-vocabulary `origin_kind` and an
      out-of-vocabulary or missing `failed_items[].category`.
- [ ] **AC9:** The SPEC contains an explicit, named resolution for FR7 — a migration rule, a
      compatibility rule, or a justified version transition — and states what happens to an
      existing on-disk `rework.yaml` written under `schema_version: 1`.
- [ ] **AC10:** `python3 -m unittest discover -s tests` is green in full, and
      `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same
      raised version.

## Technical Requirements

### Functional Requirements

- **FR1 — Re-planning branch key cites workflow-patch.md instead of restating it:** The
  implementation-planner prompt (`em-workflow/agents/implementation-planner.md:126-133`) MUST stop
  restating the re-planning condition. Its two task-id allocation branches are keyed by citing
  `references/workflow-patch.md`'s Re-planning path, which already covers both cases — including
  the `pending` state the SPEC-change transition actually produces — rather than by the erroneous
  "`create-plan` is `needs_update`" literal. The decision rule stays owned by `workflow-patch.md`
  and is cited, never copied. In the SAME change,
  `em-workflow/references/contracts/planner-contract.md:102` is aligned to the same citation form,
  and `tests/test_replanning_producer_alignment.py::TestImplementationPlannerTwoBranchAllocation::test_two_branches_present_keyed_on_create_plan_status`
  is updated to assert both owner-defined paths instead of pinning the `needs_update` literal that
  currently freezes the bug in place. The orchestrator-passes-the-path alternative is NOT adopted;
  no new dispatch input field is defined for the planner.

- **FR2 — Re-planning authorization condition uses the origin_kind/origin_id pair:**
  `em-workflow/references/workflow-patch.md:97-98`, which OWNS the unspent-re-planning-authorization
  condition, MUST name the fields task0029 renamed to: the record carries `reason`, `origin_kind`,
  `origin_id` and `recorded_at_commit` (all non-empty). The stale `finding_stable_id` is removed —
  it is the repository's last non-fixture normative use of the old name. In the same change,
  `em-workflow/skills/develop/SKILL.md`'s remaining instruction to record "the interruption reason
  and the finding's `stable_id` into the same file" is aligned to the same `origin_kind` /
  `origin_id` pair.

- **FR3 — verify-origin failed_items carry a required category; fail-closed lives at the gate:**
  `workflow.yaml`'s verify-step `failed_items` MUST be structured so that each entry carries a
  REQUIRED `category` drawn from the closed vocabulary
  `comprehensive | spec | security | performance | architecture | license | unknown` (the
  review-perspective set plus an `unknown` fail-closed sentinel). The verify-phase orchestrator
  assigns `category` at the moment it records `failed_items`, from the failing VERIFICATION.md
  scenario and the requirement IDs that scenario maps to via `verification_index`; it assigns
  `unknown` whenever that evidence is insufficient, unmapped, contradictory, or cannot exclude
  security/license. The fail-closed abort does NOT live in the verify phase: verify records
  `unknown` and lets the case reach the classification gate, because aborting during verify would
  recreate the violation of **goal-vs-spec-divergence SPEC FR7** ("every case that reaches
  `gate_id: rework.spec-change` passes through the gate"). The CLASSIFICATION GATE aborts on
  `security`, `license`, `unknown`, missing, unreadable, or out-of-vocabulary `category`, in the
  same non-overridable wording direction 1 already uses. `question-resolution.md`'s direction 2
  CITES the `failed_items` `category` definition rather than reading a field that cannot exist.
  Documents in scope: `references/workflow-schema.md`, `skills/develop/SKILL.md` verify step 4,
  `references/question-resolution.md`, and `scripts/validate-worker-output.py`. Explicitly OUT of
  scope and unchanged: SPEC.md, the VERIFICATION.md format, `verification_index`, the retrospect
  phase, and the rework-planner.

- **FR4 — Rename finding_stable_id to origin_id across schema and every consumer:**
  `questions[].evidence[].finding_stable_id` MUST be renamed to `origin_id` in
  `em-workflow/references/question-packet-schema.md`, and every consumer MUST be aligned in the
  SAME change: `references/question-resolution.md`,
  `references/contracts/rework-planner-contract.md`, `scripts/validate-worker-output.py`, the
  fixtures under `references/fixtures/`, and every existing test reference. The pair definition
  (`origin_kind` -> `origin_id`) remains owned by `references/rework-task-synthesis.md` Invariant 6
  and is CITED, not restated, by the packet schema. This requirement is all-or-nothing within one
  change: no intermediate state may exist in which the packet producer and the origin-verification
  consumer disagree on the field name. Broadening the existing field's description in place is NOT
  adopted. This is the widest blast radius in the feature.

- **FR5 — Rule 18 authorization consumption is recoverable and idempotent:**
  `references/workflow-patch.md:278` places application rule 18's authorization consumption after
  rules 15/16, so an interruption between them breaks the "consumed exactly once" invariant with
  no recovery rule defined. The document MUST define the recovery and idempotency rule for
  resuming after such an interruption.

- **FR6 — origin_kind's closed vocabulary is enforced by the validator:**
  `scripts/validate-worker-output.py:738` does not validate `origin_kind` against its closed
  vocabulary, while `classification` gained exactly such enforcement in the same change. The
  validator MUST enforce `origin_kind`'s closed vocabulary, removing the asymmetry.

- **FR7 — phase-state schema_version is resolved explicitly for the destructive shape change:**
  `references/phase-state.md:121` left `schema_version` at 1 across a destructive shape change (the
  mandatory `origin_kind`/`origin_id` pair; `classification` becoming a list), which silently makes
  an in-flight feature's on-disk `rework.yaml` non-reenterable. The SPEC MUST resolve this
  EXPLICITLY by exactly one of: a stated migration rule for existing on-disk records, a stated
  compatibility rule under which version 1 records remain readable, or a justified version
  transition. Silently leaving in-flight `rework.yaml` non-reenterable is NOT an acceptable
  outcome. This is the highest-acceptance-risk item among FR5–FR11 and was explicitly conditioned
  as such when the medium scope was accepted. NOTE: this feature's FR7 is unrelated to the
  goal-vs-spec-divergence SPEC's FR7 cited inside FR3.

- **FR8 — classification's replay rule under the idempotency section:**
  `references/phase-state.md:138` removed `classification` from the idempotency section, leaving it
  the only append-type record with no defined replay rule. Its replay rule MUST be defined.

- **FR9 — Direction 2's independence claim is reconciled with the reversible arm:**
  `references/question-resolution.md:191` declares dependence on no worker-supplied field, which
  contradicts the `assumptions[].reversible` arm in the same paragraph. The contradiction MUST be
  resolved so the declaration and the arm agree.

- **FR10 — High-water mark restatement is replaced by a citation of its SSOT:**
  `agents/implementation-planner.md:132` restates the high-water mark as
  `max(carried_task_ids union entries)`, which disagrees with the SSOT definition (the maximum
  INCLUDING retired ids). This is the same restatement-drift class as FR1 and lives in the same
  file; it MUST be fixed by citing the owning definition rather than by correcting the copy in
  place.

- **FR11 — Rule 18's phase-state crossing is covered by the Ownership boundary section:**
  `references/workflow-patch.md:275`'s rule 18 crosses into phase-state, which the document's
  Ownership boundary section does not mention. That section MUST cover the crossing.

### Non-Functional Requirements

- **NFR1 — No fail-closed regression:** No change may weaken fail-closed strength anywhere. In
  particular, the FR3 path must not leave an unattended batch run able to auto-classify a security-
  or license-related rework into a SPEC.md change. Every newly introduced arm resolves to abort
  when its evidence is absent, unreadable, or outside its vocabulary.
- **NFR2 — Single ownership, citation over restatement:** Every rule this feature touches has
  exactly one owning document. Fixes replace a drifted restatement with a citation of the owner
  (FR1, FR4, FR10); no fix introduces a new restatement of a rule owned elsewhere.
- **NFR3 — Coordinated rename atomicity:** FR4's rename is all-or-nothing within a single change:
  schema, consumers, fixtures and tests move together, with no committed state in which producer
  and consumer disagree on the field name.
- **NFR4 — Detection, not just correction:** Each of FR1–FR4 gains test coverage that fails against
  the pre-change tree. The current suite detects none of the four; `workflow-patch.md` is read by
  tests only at a frozen SHA, which is itself why FR2's drift went unnoticed, so the added coverage
  must read the live document.
- **NFR5 — Suite stays green under the project's own runner:** `python3 -m unittest discover -s tests`
  passes in full after the change. Test code adds no third-party dependency (Python 3.14 stdlib
  `unittest` only).
- **NFR6 — Plugin version bump:** Because files under `em-workflow/` change, the version MUST be
  raised in the same change in BOTH `em-workflow/.claude-plugin/plugin.json` and the matching entry
  in the repository-root `.claude-plugin/marketplace.json`, to the SAME value. These are behavior
  fixes to existing documents and scripts, so a patch-level bump is the expected increment. No
  other plugin's version moves.
- **NFR7 — Rejected findings stay out:** The two rejected items — the alleged fixture migration gap
  and the five performance findings — are excluded from every requirement, acceptance criterion and
  test scenario, and must not be reintroduced by any later phase.

## Implementation Approach

### Architecture

There is no runtime system architecture to describe: no UI layer, no application server, no
business-logic layer, and no data-access layer. The change surface consists of four artifact
classes:

```
SSOT documents (Markdown)
  workflow-patch.md ......... re-planning path, authorization condition,
                              application rules 15/16/18, Ownership boundary   (FR1, FR2, FR5, FR11)
  workflow-schema.md ........ failed_items[].category definition               (FR3)
  question-resolution.md .... direction 1 / direction 2                        (FR3, FR4, FR9)
  question-packet-schema.md . questions[].evidence[] field names               (FR4)
  phase-state.md ............ schema_version, idempotency section              (FR7, FR8)
  planner-contract.md ....... re-planning citation form                        (FR1)
  rework-planner-contract.md  origin_id consumer                               (FR4)
  skills/develop/SKILL.md ... verify step 4, authorization record instruction  (FR2, FR3)

Agent prompt
  agents/implementation-planner.md ... branch key, high-water mark             (FR1, FR10)

Validation script
  scripts/validate-worker-output.py ... category / origin_kind vocabularies    (FR3, FR4, FR6)

Tests (stdlib unittest, repository-root tests/)
  coverage that fails against the pre-change tree                              (NFR4)
```

**Ownership map (NFR2).** Each rule touched here has exactly one owner, and every other mention
becomes a citation of it:

| Rule | Owner | Citing sites |
|---|---|---|
| Re-planning path / branch key | `references/workflow-patch.md` | `agents/implementation-planner.md`, `contracts/planner-contract.md` |
| Unspent re-planning authorization condition | `references/workflow-patch.md` | `skills/develop/SKILL.md` |
| `origin_kind` -> `origin_id` pair definition | `references/rework-task-synthesis.md` Invariant 6 | `references/question-packet-schema.md` |
| `failed_items[].category` definition and vocabulary | `references/workflow-schema.md` | `references/question-resolution.md` direction 2, `skills/develop/SKILL.md` verify step 4 |
| High-water mark definition (maximum INCLUDING retired ids) | its existing SSOT definition | `agents/implementation-planner.md` |

### Data Flow

The one producer/consumer flow this feature changes is the verify-origin path (FR3):

```
VERIFICATION.md failing scenario
  → verification_index → requirement IDs
  → verify-phase orchestrator assigns failed_items[].category
     (unknown when evidence is insufficient, unmapped, contradictory,
      or cannot exclude security/license)
  → the case ALWAYS reaches the classification gate
     (verify never aborts here — aborting would recreate the
      goal-vs-spec-divergence SPEC FR7 violation)
  → classification gate:
       security | license | unknown | missing | unreadable | out-of-vocabulary → abort
       comprehensive | spec | performance | architecture                       → classify
```

The second flow is the question-packet path (FR4): the packet producer writes
`questions[].evidence[].origin_id`, and the origin-verification consumer reads that same name;
both move in one change so no intermediate disagreement exists (NFR3).

### API Design

Not applicable. This feature defines and changes no HTTP endpoint, request/response body, or
error-response envelope.

### Database Schema

Not applicable. There is no database, no table, and no entity-relationship diagram. The only
persisted-record shape concerns are the on-disk phase-state records (`rework.yaml`), handled as
FR7 (`schema_version`) and FR8 (`classification` replay rule).

### Dependencies

**Internal Dependencies:**

- `references/workflow-patch.md` — owns the re-planning path, the authorization condition,
  application rules 15/16/18, and the Ownership boundary section (FR1, FR2, FR5, FR11).
- `references/rework-task-synthesis.md` Invariant 6 — owns the `origin_kind` -> `origin_id` pair
  definition that FR4's schema change cites.
- `references/workflow-schema.md` — the definition site `question-resolution.md` direction 2 cites
  under FR3.
- `references/phases/create-plan-phase.md` — derives the feature-specific Declared Change Set
  entries at create-plan.

**External Dependencies:**

- None added. Test code adds no third-party dependency; Python 3.14 stdlib `unittest` only (NFR5,
  assumption A7). `validate-worker-output.py` may continue to use PyYAML, which is a runtime
  dependency of the plugin, not a test dependency.

### File Structure

This SPEC hand-authors no file list. The feature-specific paths are derived at create-plan from
every task's `files` entries in `workflow.yaml` (`references/phases/create-plan-phase.md`); the
documents, prompt, script and tests named normatively inside FR1–FR11 above are the anchors those
tasks are written against.

Two placement constraints apply to whatever create-plan derives:

- No new slash command: anything command-shaped is added as `em-workflow/skills/<name>/SKILL.md`,
  never under `commands/` (assumption A5).
- Every file under `em-workflow/` ships to users' plugin caches, so a test or development file
  placed inside the plugin directory is distributed; the repository-root `tests/` directory is
  outside the plugin and is not distributed (assumption A6).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths:

- `feature-docs/rework-contract-drift/**`
- `test-docs/rework-contract-drift/**`

`feature-docs/rework-contract-drift/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rework-contract-drift/**` covers `test-docs/rework-contract-drift/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rework-contract-drift/` directory at all; the declared
`test-docs/rework-contract-drift/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

All scenarios run under the project's own runner, `python3 -m unittest discover -s tests`
(NFR5). Coverage for FR1–FR4 must fail against the pre-change tree and must read the live
documents rather than a frozen SHA (NFR4).

### Unit Tests

- [ ] **TS1** (FR1): Pre-change red / post-change green: assert the planner prompt's two branches
      are keyed on the workflow-patch.md Re-planning path. Fails against the current prompt.
- [ ] **TS3** (FR2, FR4, NFR4): Repository-wide absence scan for `finding_stable_id` across
      normative documents, fixtures and tests, reading live files rather than a frozen SHA.
- [ ] **TS4** (FR2, NFR4): `workflow-patch.md`'s authorization condition is read from the LIVE
      document and asserted to name `origin_kind` and `origin_id` — the frozen-SHA read is what let
      FR2 escape the 2234-test suite.
- [ ] **TS5** (FR3): Validator rejects `failed_items` entries with a missing, empty, or
      out-of-vocabulary `category`, and accepts each of the seven vocabulary values.
- [ ] **TS8** (FR6): Validator rejects an out-of-vocabulary `origin_kind`, mirroring the existing
      `classification` vocabulary test.

### Integration Tests

- [ ] **TS2** (FR1): Apply a SPEC-change-transition create-plan patch (with `create-plan` at
      `pending` and at least one merged task) through `validate-worker-output.py --dry-run-apply`;
      it is accepted, and neither `replace-all-entry-for-registered-id` nor
      `replace-all-drops-task` fires.
- [ ] **TS6** (FR3, NFR1): Gate behavior table: `security` -> abort, `license` -> abort, `unknown`
      -> abort, missing -> abort, unreadable -> abort, out-of-vocabulary -> abort;
      `comprehensive` / `spec` / `performance` / `architecture` -> proceed to classification.
- [ ] **TS7** (FR4): A verify-origin question packet built per the renamed schema passes origin
      verification step 3 (it carries `evidence[].origin_id`), where the pre-change producer
      omitted the field and aborted.
- [ ] **TS9** (FR7): A `rework.yaml` written under the pre-change shape is handled exactly as
      FR7's chosen resolution specifies — migrated, accepted for compatibility, or rejected with
      the stated version-transition diagnostic — never silently non-reenterable.

### E2E Tests

Not applicable. This feature has no E2E infrastructure and no user flow to drive; no existing E2E
suite was resolved for it.

### Edge Cases

The edge cases this feature is required to handle are carried by the scenarios above rather than
listed separately:

- [ ] Missing, empty, or out-of-vocabulary `failed_items[].category` — TS5, TS6.
- [ ] Unreadable `category` evidence at the gate — TS6.
- [ ] An `unknown` category reaching (not aborting before) the classification gate — TS6, AC6.
- [ ] A pre-change-shape `rework.yaml` on disk — TS9.

### Performance Tests

Not applicable. No performance requirement exists for this feature, and the five performance
findings are excluded by NFR7.

## Security Considerations

- **Fail-closed strength (NFR1, BO4):** every newly introduced arm resolves to abort when its
  evidence is absent, unreadable, or outside its vocabulary. No change may leave an unattended
  batch run able to auto-classify a security- or license-related rework into a SPEC.md change.
- **Gate-side abort (FR3):** the classification gate aborts on `security`, `license`, `unknown`,
  missing, unreadable, or out-of-vocabulary `category`, in the same non-overridable wording
  direction 1 already uses. The verify phase does not abort; it records `unknown` so the case still
  passes through the gate, which is what keeps goal-vs-spec-divergence SPEC FR7 satisfied.
- **Input validation (FR3, FR6):** `validate-worker-output.py` enforces the closed vocabularies for
  `failed_items[].category` and for `origin_kind`.
- **Authentication / Authorization / Data protection / XSS / SQL injection / CSRF:** not
  applicable — there is no user-facing surface, no request handling, and no data store.

## Error Handling

There are no error codes and no HTTP statuses in this feature. The error behavior it defines is
abort behavior:

| Condition | Where handled | Outcome |
|---|---|---|
| `failed_items[].category` is `security` | classification gate | abort (non-overridable) |
| `failed_items[].category` is `license` | classification gate | abort (non-overridable) |
| `failed_items[].category` is `unknown` | classification gate | abort (non-overridable) |
| `failed_items[].category` missing | classification gate | abort (non-overridable) |
| `failed_items[].category` unreadable | classification gate | abort (non-overridable) |
| `failed_items[].category` out of vocabulary | classification gate | abort (non-overridable) |
| Evidence insufficient / unmapped / contradictory / cannot exclude security or license | verify-phase orchestrator | record `category: unknown`, do NOT abort; let the case reach the gate |
| Out-of-vocabulary `origin_kind` | `validate-worker-output.py` | reject |
| Out-of-vocabulary or missing `failed_items[].category` | `validate-worker-output.py` | reject |
| Interruption between application rules 15/16 and rule 18's authorization consumption | `references/workflow-patch.md` | resolved by the recovery and idempotency rule FR5 requires |
| On-disk `rework.yaml` written under the pre-change shape | `references/phase-state.md` | resolved by FR7's chosen resolution: migration, compatibility, or a justified version transition with a stated diagnostic — never silently non-reenterable |

## Performance Optimization

Not applicable. No performance goal, optimization strategy, or caching behavior is specified for
this feature; the five performance findings are excluded by NFR7.

## Success Criteria

- [ ] All functional requirements FR1–FR11 are implemented.
- [ ] All acceptance criteria AC1–AC10 hold.
- [ ] All test scenarios TS1–TS9 pass, and the FR1–FR4 coverage fails against the pre-change tree
      (NFR4).
- [ ] `python3 -m unittest discover -s tests` is green in full, with no third-party test dependency
      added (NFR5).
- [ ] Fail-closed strength is not weakened anywhere (NFR1).
- [ ] Every touched rule has exactly one owner and no new restatement was introduced (NFR2).
- [ ] FR4's rename landed atomically, with no committed state in which producer and consumer
      disagree on the field name (NFR3).
- [ ] `em-workflow/.claude-plugin/plugin.json` and the root `.claude-plugin/marketplace.json` carry
      the same raised version, and the report to the user notes that a Claude Code restart is
      needed for it to take effect (NFR6, assumption A2).
- [ ] The two rejected items (the alleged fixture migration gap, the five performance findings) are
      absent from the delivered change (NFR7).
- [ ] FR3's out-of-scope set is untouched: SPEC.md, the VERIFICATION.md format,
      `verification_index`, the retrospect phase, the rework-planner (AC7).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement FR1–FR11 and NFR1–NFR7 is resolved (`status: ok`); no requirement carries a
`tbd_reason`.

The FR-number ambiguity recorded as assumption A4 is not an open question: it is resolved by the
qualification convention stated in the Overview — the goal-vs-spec-divergence SPEC's FR7 is always
named in full and never written as a bare "FR7" in this document.

## Implementation Phases (if applicable)

Not applicable at spec time. Task decomposition is owned by create-plan, which derives tasks and
their `files` from this SPEC; the design step is skipped, so no design phase precedes it.

Two ordering constraints bind whatever decomposition create-plan produces:

- FR4's rename must land as a single atomic change across schema, consumers, fixtures and tests
  (NFR3).
- FR1's prompt fix, its `planner-contract.md` alignment, and its test update land in the same
  change (FR1).

## Assumptions

Recorded by requirements-analyst and rendered here unchanged; all are reversible.

- **A1:** Recorded per the batch policy's `record_as_assumption`: FR1's direction (a), FR4's
  `rename_to_origin_id`, and the `all_seven` medium scope were resolved by Codex consultation
  mapped onto existing option ids, with the orchestrator judging each mapping. FR3 was decided by
  the user directly.
- **A2:** Files under `em-workflow/` will change, so the version-bump obligation (NFR6) applies:
  both `em-workflow/.claude-plugin/plugin.json` and the root `.claude-plugin/marketplace.json`
  entry, same value, in the same change. Reporting the change to the user includes that a Claude
  Code restart is needed for it to take effect.
- **A3:** `em-workflow/hooks/destructive-guard.py` is NOT expected to be touched by this feature.
  If it is, its own runner (`python3 em-workflow/hooks/tests/run-destructive-guard.py`) must run in
  the same change, and any newly discovered misfire or miss gets a case in
  `em-workflow/hooks/tests/destructive-guard-cases.json` BEFORE the fix.
- **A4:** "FR7" is ambiguous across documents in this feature: the goal-vs-spec-divergence SPEC's
  FR7 (the gate-passage invariant cited by FR3's rationale) is a DIFFERENT requirement from this
  feature's FR7 (phase-state `schema_version`). Downstream documents must qualify which SPEC each
  FR number belongs to.
- **A5:** No new slash command is created; anything command-shaped would be added as
  `em-workflow/skills/<name>/SKILL.md`, never under `commands/`.
- **A6:** The plugin ships every file under `em-workflow/` to users' caches, so any test or
  development file added inside the plugin directory is distributed. Repository-root `tests/` is
  outside the plugin and is not distributed.
- **A7:** Test code adds no third-party dependency. `validate-worker-output.py` may continue to use
  PyYAML, which is a runtime dependency of the plugin, not a test dependency.
- **A8:** The commit range `711a9519..53395562` on branch
  `em-workflow/goal-vs-spec-divergence/integration` and the review record at
  `tmp/em-review-goal-vs-spec-rework/round1.yaml` are the evidence base for FR1–FR11. This
  feature's integration branch was created from that unmerged branch, because the lines FR1–FR4
  anchor against do not exist on `main`.

## References

- Requirements document (Japanese): `feature-docs/rework-contract-drift/REQUIREMENTS.md`
- `em-workflow/references/workflow-patch.md` — owner of the Re-planning path, the unspent
  authorization condition, application rules 15/16/18, and the Ownership boundary section
  (FR1, FR2, FR5, FR11)
- `em-workflow/references/workflow-schema.md` — definition site for `failed_items[].category` (FR3)
- `em-workflow/references/question-resolution.md` — direction 1 / direction 2 (FR3, FR4, FR9)
- `em-workflow/references/question-packet-schema.md` — `questions[].evidence[]` schema (FR4)
- `em-workflow/references/phase-state.md` — `schema_version` and the idempotency section (FR7, FR8)
- `em-workflow/references/rework-task-synthesis.md` Invariant 6 — owner of the
  `origin_kind` -> `origin_id` pair definition (FR4)
- `em-workflow/references/contracts/planner-contract.md` (FR1)
- `em-workflow/references/contracts/rework-planner-contract.md` (FR4)
- `em-workflow/agents/implementation-planner.md` (FR1, FR10)
- `em-workflow/skills/develop/SKILL.md` — verify step 4 and the authorization-record instruction
  (FR2, FR3)
- `em-workflow/scripts/validate-worker-output.py` (FR3, FR4, FR6)
- `em-workflow/references/fixtures/` (FR4)
- `tests/test_replanning_producer_alignment.py` (FR1)
- `em-workflow/references/phases/create-plan-phase.md` — derives the Declared Change Set's
  feature-specific paths
- Branch `em-workflow/goal-vs-spec-divergence/integration`, commit range `711a9519..53395562` —
  evidence base (A8)
- `tmp/em-review-goal-vs-spec-rework/round1.yaml` — review record, evidence base (A8)
