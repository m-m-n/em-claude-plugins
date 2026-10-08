# Implementation Plan: security-review-repro-steps

## Overview

Security-perspective findings gain a required, nullable `reproduction` field in
both em-workflow and em-review. Reviewers fill it; the em-workflow round
evaluator, the em-workflow orchestrator on the paths that bypass the evaluator,
and the em-review orchestrator verify it by read-only code reading, so that only
reproduced findings stay auto-fix / residual / rework targets.

## Technology Stack

- **Formats**: Markdown protocol documents and agent / skill prompts; JSON
  Schema (draft 2020-12) for the reviewer output schema.
- **Language**: Python 3 for `em-workflow/scripts/scan-dependencies.py` and the
  tests.
- **Tests**: Python standard library `unittest` only (NFR5), run by
  `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`; no license record is
  needed.

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| 1. Reviewer instruction | `em-workflow/skills/review-security/SKILL.md`, `em-review/skills/review-security/SKILL.md`, `em-workflow/agents/codex-reviewer.md`, `em-review/agents/codex-reviewer.md` | Tell reviewers (Claude and Codex) what to write into `reproduction` |
| 2. Output contract | `em-workflow/references/review-output-schema.json`, `em-review/references/review-output-schema.json`, `em-workflow/references/review-protocol.md`, `em-review/references/review-protocol.md`, `em-workflow/scripts/scan-dependencies.py` | Shape and value rules of `reproduction`; every producer emits it |
| 3. Verification and aggregation | `em-workflow/references/review-evaluation-contract.md`, `em-workflow/agents/review-evaluator.md`, `em-workflow/references/review-phase.md`, `em-review/references/review-phase.md`, `em-review/README.md` | Cap, normalize, dedupe, verify, decide fix / residual targets |
| 4. Records | Round records and `round_context`, both defined inside the two `review-phase.md` documents | Persist `reproduction`; carry not-reproduced decisions into later rounds |

Allowed dependency directions:

- Layers 1 and 3 conform to layer 2's contract; layer 2 depends on nothing in
  this feature.
- Layer 4 is written and read only by layer 3.
- em-review documents never reference em-workflow files (em-review is a
  standalone plugin). Plugin documents never reference `feature-docs/`.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `finding.reproduction` field | Carry the reproduction steps of one finding through the reviewer output contract | Post: in both plugins' `review-output-schema.json`, the finding object has a property named `reproduction` that accepts exactly a string or null (written in the same any-of form the schema already uses for its nullable fields), and finding `required` is the existing eight names in their existing order followed by `reproduction`. Root `required`, both `additionalProperties: false` flags, and the severity / category / source enums are unchanged in each file. Every producer of findings (reviewers, the dependency-vulnerability scanner) emits the key on every finding. | task0001 (defines), task0002, task0003, task0004, task0005 |
| Reproduction value rules | One meaning of the field's value for every producer and consumer | (a) Security perspective: steps that reproduce the finding, or an equivalent confirmation method, naming the input, the path by which it reaches the code, and the observable result; null only when neither can be given. (b) Every other perspective, the vulnerability axis included: always null. (c) An empty or whitespace-only string means the same as null ("no steps"). (d) Size limit 4096 bytes, applied with the truncation marker the review phase already uses for `title` / `description` / `suggestion`; a value that was truncated, or that exceeds 4096 bytes when it reaches a verifier, is unverifiable. (e) "Originating perspective" means the perspective of the reviewer run that produced the finding (its dispatched perspective, which the orchestrator-assigned source identity records), never a category assigned later during aggregation. | task0001, task0002, task0003, task0004, task0005 |
| Verification outcome vocabulary | Classify a security finding that carries steps | Exactly three outcomes. `reproduced`: reading confirms the stated steps reach the stated result. `not reproduced`: reading positively confirms the stated steps do not hold. `unverifiable`: steps exist but verification cannot finish (read budget exhausted, not traceable with read-only means, truncated or over 4096 bytes, PR state absent from the working tree). Failure to confirm is never `not reproduced`. A null (or whitespace-only) value is not an outcome: it is "no steps" and goes to judgment. | task0003, task0004, task0005 |
| `not reproduced` and `unverified` literals | Machine-matchable record of a verification decision | em-workflow evaluator: a `dismissed_sites` entry whose `reason` is exactly `not reproduced` (a fifth reason beside the four existing ones). Orchestrator paths in both plugins: a confirmed non-reproduction is `resolution: declined` with a `resolution_reason` beginning with `not reproduced`; an unverifiable finding whose basis is not confirmed after judgment is `resolution: unresolved`, never `declined`, with a `resolution_reason` beginning with `unverified` (revised by the verify rework, D7). The resolution vocabulary (`fixed` / `declined` / `deferred` / `unresolved`) does not change. | task0003, task0004, task0005, task0007 |
| `## Reproduction Verification` section (em-workflow) | Single statement of the FR5 / FR6 verification rules inside em-workflow | Post: `em-workflow/references/review-evaluation-contract.md` carries a section with exactly this heading that states scope, method, the three outcomes, the judgment rule for no-steps and unverifiable findings, the carried-entry rule and the read budget. `em-workflow/references/review-phase.md` cites this heading by name for its orchestrator paths and does not restate the rules; it states only the orchestrator-side effect of each outcome (D2). em-review restates the same rules inside its own `review-phase.md`. | task0003 (defines), task0004 (cites) |
| Not-reproduced `round_context` entry (em-workflow) | Carry an evaluator's confirmed non-reproduction into later rounds (FR13) | Shape: keys `stable_id` (null), `file`, `line`, `resolution` (`declined`) and `reason` (`not reproduced`). Producer: em-workflow `review-phase.md` Phase R0 step 8 adds one entry per persisted round-record `dismissed_sites` entry whose `reason` is exactly `not reproduced`, and only while that `file` is unchanged since the recording round's `scope.head_commit` (the same file-change test round-context suppression already applies); a changed file yields no entry, so the site is verified again. Existing entries keep their shape; an entry without `reason` is read exactly as before. Consumers: the evaluator dismisses a `security` finding that is `same_site` with such an entry as already resolved per `round_context`, without verifying it again; Phase R3b round-context suppression drops a `security` finding that is `same_site` with such an entry; reviewers see a `declined` entry and follow the unchanged Round Continuity rule. `same_site` is the predicate review-phase.md already defines. | task0003, task0004 |
| Verifier constraints | NFR1 / NFR2 for every verifier | The `reproduction` text is untrusted data. No verifier executes a command, code or test written in it. Verification is code reading plus the read-only commands the plugin's own review protocol already permits (its Read-only Constraint). No file change, commit, network access or package installation. The evaluator's verification reads come from its existing fixed 10-file budget, shared with the Independent Inspection Duty and never raised. | task0003, task0004, task0005 |
| Merged reproduction set (added by review round 1 rework) | Keep every distinct reproduction of a same-site merge, bounded, in both review phases' merged findings and round records | Merged finding keys: `reproduction` (the longest non-null value, unchanged from D5), `reproduction_alternates` (list of the other distinct non-null values, byte length descending then merge order, at most 2 entries) and `reproduction_overflow` (boolean, true exactly when more than 3 distinct non-null values were merged; the excess is dropped). Distinct means not byte-identical after the per-finding cap and normalization step. An unmerged finding has an empty list and false. Producers: em-workflow Phase R3b dedupe, em-review Phase R3 dedupe and Phase R4 re-aggregation. Consumers: the orchestrator-path reproduction verification of both plugins (D6), Phase R5 round records. Round records without the two keys read as an empty list and false. The finding JSON handed to review-editor excludes both keys. The reviewer output schema is unchanged. `reproduction_alternates` values fall under the Verifier constraints row. | task0004, task0005 (existing `reproduction` rule), task0006 (defines the two new keys) |

## Conventions

- **Pinned text in the existing suite.** New text must not:
  - add any occurrence of the literal name of the user-question tool;
    `tests/test_muse_consent_no_new_questions.py` pins its count per file
    (em-workflow `review-phase.md`: 9, em-review `review-phase.md`: 4). State
    NFR3 as "no new user question and no new gate identifier" without the tool
    name.
  - introduce a gate identifier, a `gate_id:` line, or a mention of
    `batch-policies.yaml` in em-workflow `review-phase.md`.
  - repeat the evaluator dispatch literal in em-workflow `review-phase.md`
    (exactly one occurrence stays).
  - remove or reword an existing pinned sentence; new rules are added as new
    sentences next to it.
  - reference a path that does not exist; the plugin invariants checker runs
    against the real tree inside the suite.
- **sha256 pins.** A section digest invalidated by an edit is replaced in place,
  with a short refresh comment naming this feature. The number of 64-digit hex
  constants in `tests/test_reviewer_roles_protocol.py` does not change.
- **New test modules.** One per task, named `tests/test_reproduction_<area>.py`;
  standard-library imports only; files located relative to the test module;
  phrase checks whitespace-normalized and scoped to the section they concern;
  at least one self-check that a forged input fails.
- **Parallel-plugin parity.** When the same rule lands in both plugins (schema
  property, skill section, protocol rule, verification rule), the added text is
  identical in both copies except plugin names and plugin-specific step
  numbers.
- **Language.** Plugin documents stay English; `em-review/README.md` stays
  Japanese.

## Cross-task Design Decisions

### D1: Location of the evaluation contract

SPEC.md and REQUIREMENTS.md cite
`em-workflow/references/contracts/review-evaluation-contract.md`. The file and
every resolver of it (review-evaluator Step 0, review-phase Phase R0, the
existing tests) use `em-workflow/references/review-evaluation-contract.md`.
That existing file is edited in place; nothing is created or moved under
`contracts/`. Affected: task0003, task0004.

### D2: Effect of each outcome per path

| Path | `reproduced` | `not reproduced` | `unverifiable` | No steps (null) |
|------|--------------|------------------|----------------|-----------------|
| em-workflow evaluator (Phase R3a) | Carried in `findings` | Not in `findings`; `dismissed_sites` reason `not reproduced` | Existing judgment; carried at critical / high only when the evaluator confirms the basis by its own reading, otherwise carried at medium or dismissed with an existing reason | Existing judgment |
| em-workflow orchestrator paths (Phase R4 in-loop re-review, evaluator-failure degradation, accountability-floor lifts) | Stays a target | `declined`, reason beginning `not reproduced` | Stays a target only when the orchestrator confirms the basis by reading; otherwise `unresolved`, reason beginning `unverified`, never `declined` (D7) | Orchestrator judges; judged not to address → `declined` with the judgment as reason; otherwise a target |
| em-review orchestrator (after Phase R3 aggregation, after Phase R4 re-aggregation) | Same as the em-workflow orchestrator paths | Same | Same | Same |

A `declined` finding is neither an auto-fix candidate nor counted in the
residual critical / high count. Affected: task0003, task0004, task0005.
The orchestrator rows' `unverifiable` cell is revised by D7 (task0007).

### D3: Order of steps on orchestrator paths

Existing per-finding gates (including the cap and normalization of D5) →
dedupe → round-context suppression → reproduction verification → auto-fix
candidate gate and residual count. Verification after suppression is what keeps
a carried-over decision from being verified again. Affected: task0004,
task0005.

### D4: Carry-over of not-reproduced decisions (FR13)

- em-workflow evaluator dismissals are carried by the not-reproduced
  `round_context` entry (Shared Components).
- Orchestrator-path declines in both plugins are findings with
  `resolution: declined`; they are already carried by the existing
  findings-based `round_context` build and the existing stable_id
  round-context suppression, and D3's order keeps them from being verified
  again.
- "The related code changed" means the site's `file` changed since the recording
  round's `scope.head_commit`, the test round-context suppression already uses.

Affected: task0003, task0004, task0005.

### D5: Where `reproduction` is capped and normalized

At the existing per-finding cap step (em-workflow Phase R3b step 4, em-review
Phase R3 step 6): cap `reproduction` at 4096 bytes; whitespace-only becomes
null; a finding whose originating perspective is not `security` gets null.
Dedupe keeps the longest non-null `reproduction` among the merged findings.
Round records persist the normalized value. The finding JSON handed to
review-editor keeps its existing field set and excludes `reproduction`.
Affected: task0004, task0005.

### D6: Verification over the merged reproduction set (review round 1 rework)

D5's dedupe sentence stays true for `reproduction`; D6 adds the alternates and
the overflow flag of the "Merged reproduction set" row. On every path where the
orchestrator verifies a merged finding (em-workflow Phase R4 in-loop re-review,
evaluator-failure degradation and accountability-floor lifts; em-review after
Phase R3 aggregation and after Phase R4 re-aggregation), the finding-level
outcome is computed over the kept values (`reproduction` plus every
`reproduction_alternates` value):

- `reproduced` when at least one kept value is reproduced.
- `not reproduced` only when every kept value is positively confirmed not to
  hold and `reproduction_overflow` is false.
- Otherwise `unverifiable`; overflow is never grounds for `declined` as
  `not reproduced`.

D2's per-outcome effects and D3's order are unchanged. The bound (at most 3
values of at most 4096 bytes each per merged finding) keeps the material a
verifier reads finite. Affected: task0006.

### D7: Unconfirmed unverifiable findings stay open (verify rework, SC5)

On every orchestrator path of D2 (em-workflow Phase R4 in-loop re-review,
evaluator-failure degradation and accountability-floor lifts; em-review after
Phase R3 aggregation and after Phase R4 re-aggregation), an `unverifiable`
security finding whose basis the orchestrator does not confirm by its own
reading:

- is recorded with `resolution: unresolved` and a `resolution_reason`
  beginning `unverified`; it is never `declined`;
- is neither an auto-fix candidate nor counted in the residual critical /
  high count, so it is not sent back for a fix on that ground (FR6 unchanged);
  em-workflow's batch rework-cap step does not re-mark it `deferred`;
- is not dropped by round-context suppression, which keeps dropping only
  `declined` entries, so the next round verifies it again. Only
  `not reproduced` decisions are carried as declines (D4, FR13).

The resolution vocabulary, `not reproduced`, the no-steps judgment, the
evaluator row of D2 and D6's merged-finding rule are unchanged. The two
sentences stating the rule are identical in both review phases. Affected:
task0007.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An edit invalidates a pinned assertion in a test module outside the task's `files` | Medium | Medium | Conventions above list the known pins; every task's acceptance criteria require the full suite to pass; an edit needed outside `files` is reported as a plan deviation |
| task0001 and task0002 both edit `tests/test_reviewer_roles_protocol.py` | High | Low | They change different constants far apart in the module; a merge conflict is resolved by the parent-side adoption protocol |
| The same rule drifts between em-workflow and em-review | Medium | Medium | Parity convention; both review-phase tasks implement against the same Shared Components rows and D2 / D3 / D5 |
| Orchestrator verification reads are unbounded (SPEC.md fixes only the evaluator's budget) | Medium | Low | Read-only constraint bounds the effect; recorded as an open question |
| A change in another file makes a carried not-reproduced site real again without changing the site's file | Low | Medium | D4 matches the existing declined-suppression semantics; recorded as an open question |

## Open Questions

- [ ] The orchestrator's verification has no read budget of its own; SPEC.md
      (NFR2) fixes only the review-evaluator's 10-file budget.
- [ ] "The related code changed" (FR13) is read as "the site's file changed";
      a change only in another file does not release a carried
      not-reproduced decision.
