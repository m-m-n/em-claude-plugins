# Feature: batch-codex-autonomous-decisions

## Overview

In `--batch`, em-workflow's fail-closed immediate abort for `category: security`,
`category: license`, and questions named by an `assumptions[]` entry with
`reversible: false` is removed: those questions instead enter
`references/question-resolution.md`'s Codex consultation route and are resolved
autonomously. Interactive runs keep today's immediate abort verbatim, so the
attended path is never weakened. Every autonomous resolution, the alternatives
rejected and the reasoning behind it are appended to
`feature-docs/{feature}/phase-state/batch-audit.yaml` and carried out in the run
report.

Requirements source: `feature-docs/batch-codex-autonomous-decisions/REQUIREMENTS.md`.
This document is the implementation-facing rendering of the same requirements;
every FR/NFR id below is the id used there.

## Objectives

- An unattended `--batch` run never stops because a worker declared a question
  irreversible or classified it as security/license: the orchestrator consults
  Codex (or an Opus subagent) and continues on its own judgement.
- Interactive runs keep today's fail-closed immediate abort exactly as it stands,
  so relaxing batch never weakens the attended path.
- Every autonomously taken decision, the alternatives rejected, and the reasoning
  behind it survive as an auditable record that the run report carries out to the
  external task-management service.

## Assumptions

These are requirements-analyst's resolved assumptions, carried into this
specification unchanged. Each is reversible.

- **A1** — The explicit fail-closed gate-list slot in the Fail-closed
  classification keeps its unconditional abort in both modes. *Reason*: the task
  enumerates exactly three arms to remove, and the list currently holds zero
  entries, so relaxing it would change nothing today while removing a reserved
  defence. *Impact*: low.
- **A2** — `category: spec-change` outside `rework.spec-change`, and both
  directions of the malformed `gate_id`/`category` pairing, keep aborting in both
  modes. *Reason*: these are integrity checks over pairing consistency, not
  judgement calls, and the task does not name them. *Impact*: medium.
- **A3** — `em-workflow/scripts/run_codex_exec.sh` is the wrapper the fallback
  chain is added to, and it already accepts the `readonly -C <root> <prompt>` form
  question-resolution.md invokes. *Reason*: question-resolution.md's Codex
  consultation procedure names exactly that path and invocation; the script itself
  was not in this dispatch's scan targets. *Impact*: medium.
- **A4** — The Opus escalation is a Task dispatch at Opus/xhigh; whether it needs a
  dedicated agent definition under `em-workflow/agents/` is left to planning.
  *Reason*: the task constraint names the model and reasoning level but not a
  delivery vehicle, and no existing agent file was in scope this round.
  *Impact*: low.
- **A5** — No new `gate_id` is minted and no `batch-policies.yaml` entry is added;
  relaxed questions keep whatever `gate_id` they already carry. *Reason*: the
  relaxation changes the classification step, not the gate vocabulary; adding a
  gate would ripple into the frozen registry derivation and
  gate-option-vocabulary.md. *Impact*: medium.
- **A6** — Notion integration is out of implementation scope; em-workflow's
  obligation ends at the run report. *Reason*: resolved by answer
  `requirement.notion-reporting-scope` = `report_only`. *Impact*: low.
- **A7** — The version bump is patch-level. *Reason*:
  core-plugin-version-bump.md states behaviour corrections are patch-level and
  that most changes are; this change adds no new plugin surface. *Impact*: low.
- **A8** — The five-turn ceiling counts wrapper launches, and the Opus escalation
  dispatch is counted separately, outside that ceiling. *Reason*:
  question-resolution.md's ceiling is stated in terms of wrapper launches; answer
  `requirement.escalation-subagent` places the escalation after the consultation
  ends. *Impact*: low.

## User Stories

### US1: Batch resolves a relaxed question through consultation
As an operator running em-workflow with `--batch`, I want a question that a worker
declared irreversible or classified as security/license to enter the Codex
consultation route, so that the unattended run keeps going instead of stopping for
a human.

**Acceptance Criteria:**
- [ ] AC-1: In `--batch`, a question carrying `category: security`, a question
      carrying `category: license`, and a question named by an `assumptions[]`
      entry with `reversible: false` each enter question-resolution.md's Codex
      consultation route instead of aborting immediately.
- [ ] AC-8: The Classification gate's direction-2 category/irreversibility check is
      relaxed in batch on the same terms, while its direction-1 origin-membership
      check and both malformed-pairing aborts stay fail-closed in both modes.
- [ ] AC-9: `references/question-resolution.md`, `references/batch-mode.md` and
      `references/batch-policies.yaml` are updated, and every passage that states an
      abort is non-overridable — including the Precedence reservation and the
      `block`-branch paragraph — is rewritten to state the two-mode split.

### US2: The undecided remainder is escalated once, with reasoning
As an operator running em-workflow with `--batch`, I want questions the
consultation could not map to be escalated together in a single Opus subagent
dispatch that returns both the decision and why, so that the run reaches a decision
at a bounded cost and I can audit it afterwards.

**Acceptance Criteria:**
- [ ] AC-3: The consultation keeps the per-packet five-turn ceiling; any question
      still unmapped when it ends is escalated, together with every other unmapped
      question of that packet, in one Opus subagent dispatch that returns both the
      decision and its reasoning.
- [ ] AC-4: When Codex CLI is absent, the same Opus/xhigh subagent route runs in the
      consultation's place.
- [ ] AC-2: When the consultation reaches no decision, the run does not abort — it
      takes the minimum-side-effect option on the success path, by the same rule the
      existing unlisted-gate fallback states.

### US3: Consultation survives a provider outage without a protocol change
As a maintainer of em-workflow, I want the provider fallback chain to live inside
the wrapper script, so that a usage limit or a Vertex error does not stop the run
and adding or reordering providers needs no protocol-document edit.

**Acceptance Criteria:**
- [ ] AC-5: The GPT -> GLM5.2 (Vertex AI) -> Muse Spark chain is implemented in
      `em-workflow/scripts/run_codex_exec.sh`; no protocol document names a
      provider.

### US4: Interactive keeps its fail-closed abort
As an operator running em-workflow without `--batch`, I want all three arms to keep
aborting immediately, so that relaxing batch does not weaken the attended path.

**Acceptance Criteria:**
- [ ] AC-7: Interactive mode (`--batch` absent) is unchanged: all three arms still
      abort immediately, and no new interactive question is introduced.
- [ ] AC-10: `question-packet-schema.md`'s `on_unanswered: block` constraint and
      `validate-worker-output.py`'s `BLOCKING_REQUIRED_CATEGORIES` check are
      byte-identical in behaviour; only their rationale prose changes.
- [ ] AC-11: `gate_fail_closed` remains in batch-terminal-line.md's closed
      eleven-code set with its `fail-closed-abort` stop-point row intact; its
      coverage wording names only the surviving aborts.

### US5: Every autonomous decision is auditable
As an operator reviewing an unattended run afterwards, I want the decision taken,
the alternatives rejected and the discussion's key points recorded and reported, so
that I can check the run's judgement without re-running it.

**Acceptance Criteria:**
- [ ] AC-6: The decision taken, the alternatives rejected and the discussion's key
      points are recorded in `feature-docs/{feature}/phase-state/batch-audit.yaml` in
      phase-state.md's batch audit record shape, and appear in batch-mode.md's
      `## Reporting` required contents and its audit-item source map.
- [ ] AC-12: A question-packet fixture carrying `reversible: false` exists under
      `em-workflow/references/fixtures/` and `validate-worker-output.py` accepts it;
      document-pin tests assert the batch route is stated and the interactive abort
      retained.
- [ ] AC-13: `python3 -m unittest discover -s tests` passes, with every pin listed in
      `reference_impact` updated rather than removed.
- [ ] AC-14: `em-workflow/.claude-plugin/plugin.json` and the root
      `.claude-plugin/marketplace.json` carry the same bumped version.

## Technical Requirements

### Functional Requirements

- **FR1 — Batch relaxation of the three fail-closed arms:** In `--batch`,
  `references/question-resolution.md`'s Fail-closed classification no longer aborts
  on `category: security`, on `category: license`, or on an `assumptions[]` entry
  naming the question with `reversible: false`. Each such question instead enters
  the Codex consultation route (the Unlisted-gate fallback's consultation
  procedure) and is resolved there.
- **FR2 — Interactive abort retained verbatim:** Outside `--batch`, all three arms
  keep aborting the phase immediately, before any policy lookup, before
  consultation, before `on_unanswered` is read, and before any option is selected.
  The relaxation is conditioned on the `--batch` flag alone, never on the `batch`
  block in workflow.yaml.
- **FR3 — Aborts that survive in batch:** The following keep aborting fail-closed
  in BOTH modes: the explicit fail-closed gate-list slot; `category: spec-change`
  whose `gate_id` is not exactly `rework.spec-change`; both directions of the
  malformed `gate_id`/`category` pairing; and the Classification gate's step-3
  origin-verification aborts (absent, unresolvable, or non-member `origin_id`).
- **FR4 — Precedence reservation reworded:** The **Precedence reservation**
  paragraph is rewritten so that its "abort arm evaluated first, abort final and
  non-overridable" rule is scoped to interactive for the three relaxed arms, while
  the routed arm still never converts a surviving abort (FR3) into a classification
  in either mode.
- **FR5 — Classification gate direction 2 relaxed on the same terms:** Per answer
  `requirement.classification-gate-scope` = `both_arms_except_membership`: in batch,
  the Classification gate's direction-2 category/irreversibility check (bound-set
  member category `security`/`license`/sentinel/missing/out-of-vocabulary, and the
  `reversible: false` arm) is relaxed on exactly the same terms as FR1, routing to
  consultation instead of aborting.
- **FR6 — Direction 1 stays fail-closed:** The Classification gate's direction-1
  origin-membership check and the malformed-pairing abort remain fail-closed in both
  modes; they are integrity checks over orchestrator-held data, not judgement calls,
  and the document states that split explicitly.
- **FR7 — Consultation batching and ceiling unchanged:** Per answer
  `requirement.escalation-subagent` = `keep_per_packet_ceiling`: a relaxed question
  joins the packet's single batched consultation; the turn-3 trajectory judgement
  and the five-turn per-packet ceiling are unchanged, so a 32-question packet still
  costs at most five wrapper launches.
- **FR8 — Single Opus escalation for the unmapped remainder:** When the
  consultation ends with any question of the packet still unmapped onto an
  `option_id`, ALL such questions are escalated together in ONE Opus subagent
  dispatch. The dispatch returns, per question, either a chosen `option_id` or an
  explicit no-decision, together with the reasoning for it; that reasoning is
  recorded.
- **FR9 — Codex-absent route:** When the availability probe reports `unavailable`,
  the orchestrator takes the same Opus/xhigh subagent route (FR8) instead of
  skipping straight to `on_unanswered`.
- **FR10 — No abort when nothing maps:** If neither the consultation nor the Opus
  escalation produces a mapping, the run does not abort: it falls through to
  `on_unanswered`, where `block` takes the option with the smallest side effect on
  the success path — the existing unlisted-gate fallback rule, now explicitly
  reaching the relaxed categories in batch.
- **FR11 — Block-branch prose rewritten:** The Unlisted-gate fallback's `block`
  branch no longer states that security/licensing/irreversible-operation questions
  never reach it. It states the two-mode split: in interactive they were aborted
  upstream; in batch they arrive here through the relaxed route. The
  specification-change carve-out (removed by the routed arm at step 2) is kept as a
  separate, distinct mechanism.
- **FR12 — Batch resolution sequence step 2 updated:** Step 2 of the Batch
  resolution sequence is updated so "a question it aborts never reaches step 3" is
  stated as mode-conditional, without restating the Classification gate's Outcome
  step (the NFR1 non-duplication guard stays satisfied).
- **FR13 — Provider fallback chain inside the wrapper:** Per answer
  `requirement.backend-fallback-chain` = `wrapper_owns_chain`:
  `em-workflow/scripts/run_codex_exec.sh` implements GPT -> GLM5.2 (Vertex AI) ->
  Muse Spark, detecting the usage-limit response and the Vertex error and switching
  provider transparently. `question-resolution.md` states only that the wrapper may
  answer from a fallback provider and names no provider and no mechanics.
- **FR14 — Audit record for every autonomous resolution:** Every resolution taken
  through the relaxed route appends one element to
  `feature-docs/{feature}/phase-state/batch-audit.yaml` `records[]`, in the
  batch-audit-record shape `references/phase-state.md` defines. `resolution_note`
  names the gate, the option chosen, the options not chosen, the discussion's key
  points, whether Codex was consulted, whether a fallback provider answered, and
  whether the Opus escalation ran with its reasoning. `source` is drawn from the
  closed vocabulary (`batch-codex-consultation` when a suggestion mapped,
  `batch-safe-default` when the minimum-side-effect branch was taken).
- **FR15 — phase-state.md gains this writer:** `references/phase-state.md`'s Batch
  audit record file section adds this route as a writer, with its `question_id` rule
  (the question's own `question_id` when a worker packet exists, the gate's
  `gate_id` when the gate was orchestrator-opened) and its commit reach-point.
- **FR16 — Reporting contents extended, Notion out of scope:** Per answer
  `requirement.notion-reporting-scope` = `report_only`:
  `references/batch-mode.md`'s `## Reporting` required contents gain the autonomous
  fail-closed-route resolutions, and the `## Batch quiet output` audit-item source
  map gains the corresponding row. em-workflow performs no operation against Notion
  or any external service; relaying stays that service's job.
- **FR17 — batch-policies.yaml header rewritten:** The header comment stops
  asserting that the `category: security`, `category: license` and
  `reversible: false` arms keep aborting "at unchanged strength". It states the
  batch relaxation and the interactive retention, still citing
  `references/question-resolution.md` by path without restating gate internals, and
  keeps `rework.spec-change` documented as intentionally unlisted.
- **FR18 — on_unanswered constraint kept, rationale reworded:** Per answer
  `requirement.on-unanswered-block-coupling` = `keep_constraint_reword`:
  `references/question-packet-schema.md` keeps "a question whose `category` is
  `spec-change`, `security`, or `license` must carry `on_unanswered: block`"
  verbatim; only the rationale sentence is reworded to say that in batch `block`
  routes into the minimum-side-effect branch rather than an abort.
- **FR19 — Validator check kept, message rationale reworded:**
  `scripts/validate-worker-output.py` keeps
  `BLOCKING_REQUIRED_CATEGORIES = {"spec-change", "security", "license"}` and the
  `on_unanswered != "block"` rejection unchanged. Only the error message's
  parenthetical rationale is reworded. No accept/reject behaviour changes and the
  frozen gate-registry derivation is untouched.
- **FR20 — Fixture plus validator assertion:** Per answer
  `requirement.verification-fixture-shape` = `fixture_plus_validator`: a
  question-packet fixture carrying an `assumptions[]` entry with `reversible: false`
  is added under `em-workflow/references/fixtures/`, in the existing
  kind/group/`valid-`-prefixed directory convention, and `validate-worker-output.py`
  accepts it (exit 0) both directly and through the existing fixture-corpus sweep.
- **FR21 — Document-pin assertions:** Document-pin tests assert that the rewritten
  documents state the batch route AND retain the interactive abort. Every existing
  pin that asserts a sentence this change removes is replaced at equal specificity
  with a positive pin on the new wording plus a negative proof that the superseded
  wording is gone, per the repo's established C5 convention.
- **FR22 — Terminal-line reason code retained, coverage narrowed:** Per answer
  `requirement.gate-fail-closed-terminal-reason` = `retain_narrowed`:
  `references/batch-terminal-line.md` keeps `gate_fail_closed` inside the closed
  eleven-code set and keeps the `fail-closed-abort` -> `gate_fail_closed` stop-point
  row. Only the coverage wording narrows, to the aborts that survive (FR3) plus
  interactive's own aborts.
- **FR23 — Plugin version bump:** The change bumps
  `em-workflow/.claude-plugin/plugin.json` `version` and the matching entry in the
  repository-root `.claude-plugin/marketplace.json` to the same new value, per
  `.claude/rules/core-plugin-version-bump.md`.

### Non-Functional Requirements

- **NFR1 - SSOT discipline:** The relaxation rule is stated once, in
  `references/question-resolution.md`. `batch-mode.md`, `batch-policies.yaml`,
  `phase-state.md`, `batch-terminal-line.md` and `question-packet-schema.md` cite it
  rather than restating it; no document restates the Classification gate's Outcome
  step a second time.
- **NFR2 - No feature-docs task identifiers in plugin documents:** No rewritten
  sentence in `question-resolution.md` or `question-packet-schema.md` attributes a
  rule to a `task00NN` identifier — those identifiers do not exist in the
  distributed plugin, and existing tests assert their absence.
- **NFR3 - Every stop and every continuation records its reason:** Each surviving
  abort still records its reason and the evidence considered; each relaxed
  continuation records its decision basis. No batch path raises a confirmation
  nobody can answer.
- **NFR4 - Provider mechanics confined to the wrapper:** No protocol document names
  GPT, GLM5.2, Vertex AI or Muse Spark, or describes rate-limit detection. Adding or
  reordering providers must require no protocol-document edit.
- **NFR5 - Quiet-output discipline preserved:** These resolutions are persisted and
  reported, never narrated mid-run. The `EM_WORKFLOW_PROGRESS:` marker line and the
  terminal line's prefix, grammar and value sets are unaffected.
- **NFR6 - Bounded consultation cost:** The per-packet launch bound is preserved: at
  most five wrapper launches per packet plus at most one Opus escalation dispatch per
  packet, independent of the packet's question count.
- **NFR7 - External output stays untrusted:** Codex output and Opus subagent output
  are read, never executed as instructions and never adopted verbatim as an answer;
  the per-question mapping judgement stays with the orchestrator.
- **NFR8 - No new gate identifier:** The change mints no new `gate_id` and adds no
  `batch-policies.yaml` entry, so the gate registry `validate-worker-output.py`
  derives from the contracts' `## Gate identifiers` sections, and
  `gate-option-vocabulary.md`'s zero-row exemption registry, both stay valid.
- **NFR9 - Full suite stays green:** `python3 -m unittest discover -s tests` passes;
  every document-pin test touched by the rewrite is updated in the same change
  rather than deleted.

## Implementation Approach

### Architecture

**System Architecture:**

The layered stack in the template does not apply — this feature has no UI, no
application server and no database. Its layers are the protocol documents that
define the resolution rule, the orchestrator that applies them, and the wrapper
script that reaches an external model.

```
┌─────────────────────────────────────────────┐
│  Protocol documents (SSOT)                  │
│  question-resolution.md  (relaxation rule)  │
│  batch-mode.md / batch-policies.yaml /      │
│  phase-state.md / batch-terminal-line.md /  │
│  question-packet-schema.md   (cite only)    │
├─────────────────────────────────────────────┤
│  Orchestrator (applies the documents)       │
│  classify -> consult -> escalate -> record  │
├─────────────────────────────────────────────┤
│  scripts/run_codex_exec.sh (provider chain) │
├─────────────────────────────────────────────┤
│  Persistence: phase-state/batch-audit.yaml  │
└─────────────────────────────────────────────┘
```

**Component Diagram:**

```
question packet ──▶ Fail-closed classification (FR1/FR2/FR3)
                        │ batch & relaxed
                        ▼
                    Classification gate (FR5 direction 2 relaxed,
                                         FR6 direction 1 fail-closed)
                        │
                        ▼
                    Codex consultation (FR7) ──▶ run_codex_exec.sh (FR13)
                        │ unmapped remainder
                        ▼
                    Opus escalation, one dispatch (FR8/FR9)
                        │ still unmapped
                        ▼
                    on_unanswered: minimum side effect (FR10/FR11)
                        │
                        ▼
                    batch-audit.yaml records[] (FR14/FR15)
                        │
                        ▼
                    run report contents (FR16)
```

### Data Flow

```
--batch flag + question packet
  → classification (relaxed arms routed, surviving aborts still abort)
  → batched consultation (≤5 wrapper launches per packet)
  → wrapper: GPT → GLM5.2 (Vertex AI) → Muse Spark, reports which answered
  → orchestrator maps suggestion → option_id   (never adopts output verbatim)
  → unmapped remainder → one Opus/xhigh dispatch → option_id or no-decision + reason
  → still unmapped → on_unanswered: minimum-side-effect option
  → append one record to phase-state/batch-audit.yaml
  → run report
```

### API Design

N/A — the feature exposes and consumes no HTTP API. Its only external interfaces
are a local wrapper-script invocation (`readonly -C <root> <prompt>`, FR13/A3) and a
Task dispatch to an Opus/xhigh subagent (FR8/FR9/A4).

### Database Schema

N/A — no database. The only persisted structure is the batch audit record appended
to `feature-docs/{feature}/phase-state/batch-audit.yaml` `records[]`, whose shape is
defined by `references/phase-state.md` and is not restated here (NFR1). The fields
this feature constrains are:

| Field | Constraint | Source |
|---|---|---|
| `question_id` | The question's own `question_id` when a worker packet exists; the gate's `gate_id` when the gate was orchestrator-opened | FR15 |
| `source` | Closed vocabulary: `batch-codex-consultation` when a suggestion mapped, `batch-safe-default` when the minimum-side-effect branch was taken | FR14 |
| `resolution_note` | Names the gate, the option chosen, the options not chosen, the discussion's key points, whether Codex was consulted, whether a fallback provider answered, and whether the Opus escalation ran with its reasoning | FR14 |

#### Entity Relationship Diagram

N/A — no entities and no relations to diagram.

### Dependencies

**Internal Dependencies:**

- `references/question-resolution.md`: the SSOT the relaxation rule is stated in
  (FR1, FR4, FR11, FR12, NFR1).
- `references/batch-mode.md`: reporting contents and the audit-item source map
  (FR16).
- `references/batch-policies.yaml`: header comment; no new entry is added (FR17,
  NFR8, A5).
- `references/phase-state.md`: batch audit record shape and writer list (FR14,
  FR15).
- `references/batch-terminal-line.md`: closed reason-code set and stop-point table
  (FR22).
- `references/question-packet-schema.md`: the `on_unanswered: block` constraint
  (FR18).
- `references/gate-option-vocabulary.md`: zero-row exemption registry, must stay
  valid (NFR8).
- `scripts/validate-worker-output.py`: message rationale only; behaviour unchanged
  (FR19, FR20).
- `.claude/rules/core-plugin-version-bump.md`: version bump rule (FR23, A7).

**External Dependencies:**

- Codex CLI, invoked through `em-workflow/scripts/run_codex_exec.sh` (FR13, A3).
  Absence is a supported state and takes the Opus route (FR9).
- The provider chain reached by the wrapper. Named here only because FR13 requires
  it; no protocol document names any of them (NFR4).
- An Opus/xhigh subagent Task dispatch (FR8, A4).

### File Structure

The template's Go service layout does not apply. The files this change touches:

```
em-workflow/
├── references/
│   ├── question-resolution.md          # FR1 FR3 FR4 FR11 FR12 FR13 NFR1 NFR2
│   ├── batch-mode.md                   # FR16
│   ├── batch-policies.yaml             # FR17
│   ├── phase-state.md                  # FR15
│   ├── batch-terminal-line.md          # FR22
│   ├── question-packet-schema.md       # FR18 NFR2
│   └── fixtures/                       # FR20 (new question-packet fixture)
├── scripts/
│   ├── run_codex_exec.sh               # FR13
│   └── validate-worker-output.py       # FR19 (message rationale only)
├── tests/                              # FR21 NFR9 (document pins, validator, wrapper)
└── .claude-plugin/plugin.json          # FR23
.claude-plugin/marketplace.json         # FR23
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

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

- [ ] TS-1 (FR1, FR2, FR21): question-resolution.md states, for each of the three
      arms, that batch routes to consultation and interactive aborts immediately; a
      negative proof asserts the superseded unconditional-abort sentence is gone.
- [ ] TS-2 (FR4, FR3, FR21): the rewritten Precedence reservation still forbids the
      routed arm converting a SURVIVING abort into a classification, and no longer
      claims the three relaxed arms are non-overridable in batch.
- [ ] TS-3 (FR11, FR10, FR21): the `block` branch of the Unlisted-gate fallback
      states the two-mode split and keeps the spec-change carve-out as a distinct
      mechanism; the pre-change sentence is absent.
- [ ] TS-4 (FR5, FR6, FR21): the Classification gate's direction 1 keeps the
      identical final-and-non-overridable wording; direction 2 states the batch
      relaxation. The phrase-count assertion in `tests/test_classification_gate.py` is
      updated to the new count rather than deleted.
- [ ] TS-5 (FR17, NFR1): batch-policies.yaml's header no longer contains "unchanged
      strength" for the three arms, still names question-resolution.md by path, and
      still restates no gate internals.
- [ ] TS-6 (FR22, FR3): batch-terminal-line.md's eleven reason codes and eleven
      stop-point rows are unchanged as sets; the `gate_fail_closed` coverage prose
      names only the surviving aborts.
- [ ] TS-7 (FR16, FR14): batch-mode.md's `## Reporting` list and the audit-item
      source map both carry the new item, and their item counts in
      `tests/test_batch_quiet_output_discipline.py` and
      `tests/test_batch_quiet_output_audit_persistence.py` are updated to match.
- [ ] TS-8 (FR15, FR14): phase-state.md's batch audit record writers list includes
      the new writer with its `question_id` rule; the record shape is unchanged.
- [ ] TS-9 (FR19, FR18): validate-worker-output.py still rejects a `security`
      question with `on_unanswered: record_tbd` (exit 1) and still rejects `license`
      and `spec-change` the same way.
- [ ] TS-12 (NFR2, NFR4): no plugin document under `em-workflow/references/` matches
      `task\d{4}` where the existing pins forbid it, and no document names a provider.

### Integration Tests

- [ ] TS-10 (FR20): the new `reversible: false` question-packet fixture is accepted
      (exit 0), both directly and via the fixture-corpus sweep; the branch-coverage
      guard still finds a valid and an invalid case in its group.
- [ ] TS-11 (FR13, NFR4): the wrapper script falls through to the second provider on
      a usage-limit response and to the third on a Vertex error, and reports which
      provider answered; a non-fallback error still surfaces.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] N/A — this feature has no end-user flow to exercise; `resolved_input_paths.e2e`
      is empty and no E2E harness was supplied to this dispatch.

### Edge Cases

- [ ] Codex CLI reports `unavailable` (FR9): the Opus/xhigh subagent route runs in
      the consultation's place instead of skipping to `on_unanswered`.
- [ ] Neither consultation nor escalation maps a question (FR10): the run does not
      abort; `on_unanswered`'s `block` takes the minimum-side-effect option on the
      success path and the record's `source` is `batch-safe-default`.
- [ ] A surviving abort arrives in batch (FR3, FR6): the explicit fail-closed
      gate-list slot, `spec-change` outside `rework.spec-change`, both directions of
      the malformed `gate_id`/`category` pairing, and the step-3 origin-verification
      failures still abort in both modes.
- [ ] A non-fallback wrapper error (FR13, TS-11): the error surfaces rather than
      being absorbed by the provider chain.

### Performance Tests

- [ ] N/A — no load or stress dimension exists. The only quantitative bound is
      NFR6's per-packet ceiling (at most five wrapper launches plus at most one Opus
      dispatch), which is a protocol invariant asserted by the documents rather than
      by a load test.

## Security Considerations

- **Authentication:** N/A — the feature introduces no authentication boundary.
- **Authorization:** N/A — the feature introduces no authorization boundary.
- **Input Validation:** Codex output and Opus subagent output are read, never
  executed as instructions and never adopted verbatim as an answer; the per-question
  mapping judgement stays with the orchestrator (NFR7). Question packets remain
  validated by `validate-worker-output.py`, whose accept/reject behaviour is
  unchanged (FR19) and whose corpus gains the new fixture (FR20).
- **Data Protection:** N/A — no secret or personal data is handled. The audit record
  holds decisions and their reasoning only.
- **XSS Prevention:** N/A — no rendered markup.
- **SQL Injection Prevention:** N/A — no database and no query construction.
- **CSRF Protection:** N/A — no HTTP request surface.

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| `gate_fail_closed` | The terminal line's reason code for a fail-closed abort. Stays inside the closed eleven-code set with its `fail-closed-abort` stop-point row; only its coverage wording narrows to the surviving aborts (FR22, FR3) | N/A — not an HTTP surface | The terminal line's existing text; its prefix, grammar and value sets are unchanged (NFR5) |

No new reason code is introduced, and no new `gate_id` is minted (NFR8, A5).

### Error Flow

```
Question classified
  → surviving abort?  → yes → record reason and evidence → gate_fail_closed (NFR3)
  → no  → consult → escalate → on_unanswered minimum-side-effect → record basis (NFR3)

Wrapper invocation
  → usage-limit response → next provider
  → Vertex error         → next provider
  → other error          → surfaces to the caller
```

## Performance Optimization

### Performance Goals

- Response time: N/A — no request/response latency target applies.
- Throughput: N/A — no throughput target applies.
- Database query time: N/A — no database.
- Consultation cost (NFR6): at most five wrapper launches per packet plus at most
  one Opus escalation dispatch per packet, independent of the packet's question
  count. Per A8, the five-turn ceiling counts wrapper launches and the escalation
  dispatch is counted outside it.

### Optimization Strategies

- Per-packet batching (FR7): a relaxed question joins the packet's single batched
  consultation rather than opening its own, so a 32-question packet still costs at
  most five wrapper launches.
- Single escalation dispatch (FR8): every still-unmapped question of a packet is
  escalated together in one dispatch rather than one dispatch per question.

### Caching Strategy

N/A — nothing is cached; each consultation is per packet and its outcome is
persisted, not reused as a cache.

## Success Criteria

- [ ] All functional requirements (FR1–FR23) are implemented and tested.
- [ ] All test scenarios (TS-1–TS-12) pass.
- [ ] Performance meets specified goals — NFR6's per-packet launch bound holds.
- [ ] Security requirements are satisfied — NFR7's untrusted-output discipline holds.
- [ ] Documentation is complete — every document listed in File Structure is updated
      and NFR1's cite-don't-restate discipline holds.
- [ ] Code review is completed.
- [ ] AC-1 through AC-14 in REQUIREMENTS.md section 11.1 are all met.
- [ ] `python3 -m unittest discover -s tests` passes with every touched pin updated
      rather than deleted (NFR9, AC-13).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement (FR1–FR23, NFR1–NFR9) is `status: resolved` and carries no
`tbd_reason`.

## Implementation Phases (if applicable)

N/A — no phased rollout is required. The design step was skipped (the feature
introduces no user interface, no rendered artifact, no new file format and no
design-system surface; the question packet, the answer object, the batch audit
record and the terminal line are all already specified by existing SSOT documents),
so the create-plan phase derives the task split directly from FR1–FR23 and
NFR1–NFR9.

## References

- Requirements document: `feature-docs/batch-codex-autonomous-decisions/REQUIREMENTS.md`
- Relaxation rule SSOT: `em-workflow/references/question-resolution.md`
- Batch reporting and quiet output: `em-workflow/references/batch-mode.md`
- Batch decision table: `em-workflow/references/batch-policies.yaml`
- Batch audit record shape and writers: `em-workflow/references/phase-state.md`
- Terminal-line reason codes and stop points: `em-workflow/references/batch-terminal-line.md`
- Question packet and `on_unanswered`: `em-workflow/references/question-packet-schema.md`
- Gate option vocabulary: `em-workflow/references/gate-option-vocabulary.md`
- Codex wrapper: `em-workflow/scripts/run_codex_exec.sh`
- Worker output validation: `em-workflow/scripts/validate-worker-output.py`
- Fixture corpus: `em-workflow/references/fixtures/`
- Plugin version bump rule: `.claude/rules/core-plugin-version-bump.md`
