---
title: "stop-reason-coverage"
created_date: 2026-09-24
status: draft
---

# stop-reason-coverage - Requirements

## 1. Overview

### 1.1 Background

The terminal-line contract in `em-workflow/references/batch-terminal-line.md`
declares that every terminating stop point is bound to exactly one reason code.
The round 2 review of PR #8 (`feature-docs/batch-stop-contract/reviews/round2.yaml`)
recorded six findings against that contract (high 1 / medium 5), deferred when the
batch-mode rework cap was reached:

- `b654786a7fb8e13c` (high): terminating stops absent from the coverage table.
- `6d3ffa3e04510229` / `454755f74a3e8a04` (medium): stops that can carry a `step`
  value although the `no-step` list names them.
- `e0aba3d91cffcb97` (medium): the precedence rule's claim that all three
  phase-specific stop points leave a step `failed`.
- `c1e94c9399f18b7d` (medium): the state-based `stop-condition-3` restriction.
- `9e5ce22b85677b38` (medium): the refusal-pattern hard fail without a coverage row.

### 1.2 Purpose

- Make the claim in batch-terminal-line.md that every terminating stop is bound to
  exactly one reason code true by construction. Use a catch-all fallback rather than
  a hand-maintained list of rows.
- Close the `step` value gap (the no-step enumeration) and the contradictions in the
  precedence rule (the docs-commit-conflict status claim; a state-based rather than
  route-based restriction for stop-condition-3).
- Keep the contract test suite and the plugin invariants green, with test pins synced
  to the new contract.

### 1.3 Scope

In scope:

- `em-workflow/references/batch-terminal-line.md` (reason-code table, coverage table,
  fallback rule, `step` bullet, precedence rule).
- Test pins and new tests in `tests/test_batch_stop_contract.py`,
  `tests/test_batch_stop_contract_skill_wiring.py`, `tests/test_failed_kind_batch_docs.py`,
  `tests/test_no_work_required_stop.py`, `tests/test_develop_once_option.py`.
- Version fields in `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json`.

Out of scope:

- Accepting `unmapped_stop` on the loop-develop side, and loop-develop's receipt of
  the terminal line and Notion status transitions (A8).
- Edits to the pointer documents `skills/develop/SKILL.md`, `references/batch-mode.md`
  and `references/implement-phase.md` (FR11).

## 2. Business Requirements

### 2.1 Business Objectives

- Make the claim in batch-terminal-line.md that every terminating stop is bound to
  exactly one reason code true by construction. Use a catch-all fallback rather than
  a hand-maintained list of rows.
- Close the `step` value gap (the no-step enumeration) and the contradictions in the
  precedence rule (the docs-commit-conflict status claim; a state-based rather than
  route-based restriction for stop-condition-3).
- Keep the contract test suite and the plugin invariants green, with test pins synced
  to the new contract.

### 2.2 Target Users

Not applicable.

### 2.3 Expected Effects

Not applicable.

## 3. Use Cases

Not applicable.

## 4. Functional Requirements

### 4.1 Requirement List

| ID | Title | Status |
|----|-------|--------|
| FR1 | Catch-all reason code and coverage row | resolved |
| FR2 | Fallback rule with lowest precedence | resolved |
| FR3 | Catch-all scope limited to batch-terminating stops | resolved |
| FR4 | detail and resume_conditions for a catch-all stop | resolved |
| FR5 | Refusal-pattern hard fail mapped to gate_fail_closed (9e5ce22b85677b38) | resolved |
| FR6 | Condition-based no-step rule (6d3ffa3e04510229 / 454755f74a3e8a04) | resolved |
| FR7 | Precedence text matches Source documents (e0aba3d91cffcb97) | resolved |
| FR8 | Route-based stop-condition-3 restriction (c1e94c9399f18b7d) | resolved |
| FR9 | Test pin sync and new catch-all tests | resolved |
| FR10 | Version bump | resolved |
| FR11 | Literal ownership preserved | resolved |

### 4.2 Requirement Details

#### FR1: Catch-all reason code and coverage row

The closed stop reason-code set in batch-terminal-line.md gains one code,
`unmapped_stop`, whose Applies-to `state` is `stopped`. The coverage table gains one
row, `unmapped-terminating-stop` → `unmapped_stop`, whose Source cell is a backticked
path that resolves under em-workflow/ (`references/batch-terminal-line.md`, where the
fallback rule is defined). The code's meaning is "a terminating stop that no other
coverage row names". It is never described as an unknown or undetermined cause.
Neither identifier contains a dot. The literal `unmapped_stop` does not currently
occur in skills/develop/SKILL.md, references/batch-mode.md or
references/implement-phase.md (verified), and it must not be added to them.

#### FR2: Fallback rule with lowest precedence

`## Stop point coverage` states a fallback rule. A terminating stop that no other row
names binds to `unmapped_stop`. Every other row always takes precedence over the
catch-all, including the generic `stop-condition-N` rows and the refusal-pattern row
of FR5, and the catch-all applies last. The sentence "Every terminating stop point is
bound to exactly one reason code above" is rewritten so it holds by construction:
exactly one code, either a named row's code or the catch-all's. The existing
precedence among named rows (phase-specific over generic, FR8) is unchanged in
effect.

The stops the task names fall to the catch-all through this rule:

- designer-contract.md's kind:none × token-present abort with truncated candidate
  discovery;
- the em_workflow × tokens.html-only pre-dispatch abort;
- phase-state.md's unknown schema_version abort.

So do the other untabled aborts found in question-resolution.md and
batch-policies.yaml.

#### FR3: Catch-all scope limited to batch-terminating stops

The fallback applies only to stops that terminate a batch run with `state`
`stopped`. It never applies to:

- wait turns (stop condition 5, implement's launch/wake turns);
- normal completion;
- a `--once` phase boundary (`phase_done`);
- the infra auto-resume (which is not a stop);
- the 64 KiB size-collision outcome.

The 64 KiB case keeps its existing statement that it emits no result and adds no
reason code and no coverage row. `context_budget_reached` remains the only documented
reason code without a coverage row.

#### FR4: detail and resume_conditions for a catch-all stop

When `reason` is `unmapped_stop`, `detail` names the stop site (the owning document
and step or section where the stop occurred) and the concrete cause.
`resume_conditions` stays mandatory and non-whitespace, as for every `stopped`
result.

#### FR5: Refusal-pattern hard fail mapped to gate_fail_closed (9e5ce22b85677b38)

A coverage row binds the create-spec.command-approval refusal-pattern hard fail to
`gate_fail_closed`, with Source `references/batch-policies.yaml`. Its key is
hyphenated with no dot, for example `command-refusal`. The `gate_fail_closed` Meaning
cell is extended to name this abort. It keeps the `references/question-resolution.md`
citation and the "both modes" / "interactive" wording, and does not re-enumerate
`category: security`, `category: license` or `reversible: false`. No new code is
minted for this stop.

#### FR6: Condition-based no-step rule (6d3ffa3e04510229 / 454755f74a3e8a04)

In the `step` bullet, `no-step` applies whenever no workflow.yaml step was executed
in that turn or the stop occurs outside Step B. This condition governs, and the named
stop points become non-exhaustive examples. The bullet explicitly covers two cases:

- A stop-condition-4 stop takes `no-step` when no step was executed in that turn;
  otherwise the general executed-step rule applies.
- A stop raised in Step A.5, including the refusal-pattern hard fail, takes
  `no-step`.

The anchor phrase "`no-step` applies whenever" stays on one physical line. The
step-domain declaration ("a closed value domain: one of the seven `workflow.yaml`
step ids (...), or the single sentinel `no-step`.") is unchanged. Every backticked
hyphenated key the bullet names must be a coverage-table key.

#### FR7: Precedence text matches Source documents (e0aba3d91cffcb97)

The precedence rule no longer says all three phase-specific stop points leave a step
`failed`. implement-second-failure and verify-rework-cap write `failed`.
docs-commit-conflict aborts without writing any status, because the failed write is
itself the stop cause. The paragraph still names `implement-second-failure`,
`verify-rework-cap` and `docs-commit-conflict`, and it does not name
`no-work-required`.

#### FR8: Route-based stop-condition-3 restriction (c1e94c9399f18b7d)

The stop-condition-3 restriction becomes route-based. A phase-specific row wins when
the current run reaches the stop through that phase's own abort route. This includes
implement-second-failure, which the same run realizes through its next Step B
evaluation. stop-condition-3 (`step_needs_intervention`) binds a stop at Step B's
entry evaluation that reads a `failed` / `needs_update` status no route of the
current run produced, such as a `failed` left by an earlier run's
implement-second-failure. The implement `failed_kind` restriction (decision, or
auto-resume cap reached) is kept. implement-phase.md's pinned sentence ("since
`references/batch-terminal-line.md` already gives `implement-second-failure`
precedence over `stop-condition-3`") stays true and unedited. The "Precedence rule:"
label is kept.

#### FR9: Test pin sync and new catch-all tests

Sync the pins to the new contract (13 codes, 14 reason-domain values, 14 coverage
rows).

- tests/test_batch_stop_contract.py: REASON_CODES, STOP_POINT_KEYS,
  _KEY_CODE_PAIRS_IN_ORDER, NO_STEP_STOP_POINTS, the count-word tests ("twelve" →
  "thirteen", "thirteenth" → "fourteenth"), and _assert_precedence_rule_stated
  (replace the state-based "no phase-specific row covers" check with the route-based
  wording).
- tests/test_batch_stop_contract_skill_wiring.py: the REASON_CODES tuple and the
  member-count test (13 → 14).
- tests/test_failed_kind_batch_docs.py: EXPECTED_REASON_CODE_STATE_PAIRS and the pins
  on the state-based precedence phrase.
- tests/test_no_work_required_stop.py: EXPECTED_REASON_CODE_STATE_PAIRS, the exact
  coverage-row list and the set-size prose pins.
- tests/test_develop_once_option.py: SC5_REASON_CODES (absence list; add
  no_work_required and unmapped_stop).

Add tests that verify three things:

- (a) every named row, including stop-condition-N and the refusal row, takes
  precedence over the catch-all;
- (b) a stop no row names resolves to `unmapped_stop`, with the task's untabled stops
  (designer aborts, phase-state schema_version mismatch) as fixtures;
- (c) the catch-all's scope excludes wait turns, normal completion, `phase_done` and
  the 64 KiB no-result case.

Each new matcher carries a negative proof and a non-vacuity guard.

#### FR10: Version bump

Bump em-workflow from 0.2.0 to 0.2.1 in both em-workflow/.claude-plugin/plugin.json
and .claude-plugin/marketplace.json.

#### FR11: Literal ownership preserved

Reason-code literals, the prefix and the field names remain owned by
batch-terminal-line.md alone. skills/develop/SKILL.md, references/batch-mode.md and
references/implement-phase.md receive no reason-code literal. SKILL.md's
「バッチ構造化結果」 enumeration already defers to the SSOT's stop points and is not
edited.

## 5. Non-Functional Requirements

- NFR1: `python3 -m unittest discover -s tests` passes; test modules import the
  Python standard library only.
- NFR2: `em-workflow/scripts/check-plugin-invariants.py` stays green; new identifiers
  contain no dot, so they never match its gate_id shape.
- NFR3: batch-terminal-line.md's `## Result format`, `## Escaping` and
  `## Responsibility boundary` sections stay byte-identical. The nine level-2 headings
  and their order are unchanged, with `Stop reason codes` immediately followed by
  `Stop point coverage`.
- NFR4: Test authoring follows the repository convention: each new matcher has a
  negative proof and a non-vacuity guard, and there is no cross-module test import.

## 6. UI/UX Requirements

Not applicable. The design step was skipped: the change touches only contract
Markdown, tests and version fields; there is no UI surface.

## 7. Data Requirements

Not applicable.

## 8. External Integrations

Not applicable.

## 9. Constraints

### 9.1 Technical Constraints

- Reason-code literals, the prefix and the field names are owned by
  batch-terminal-line.md alone (FR11, A6).
- New identifiers contain no dot (FR1, FR5, NFR2).
- batch-terminal-line.md's `## Result format`, `## Escaping` and
  `## Responsibility boundary` sections stay byte-identical (NFR3).

### 9.2 Business Constraints

- Accepting `unmapped_stop` on the loop-develop side is out of scope (A8).

### 9.3 Schedule Constraints

None.

### 9.4 Declared Change Set

The feature-specific paths are not enumerated by hand; create-plan derives them from
each task's `files` in `workflow.yaml` (`references/phases/create-plan-phase.md`).

**Default members** (always part of the declaration unless the SPEC author explicitly
removes them):

- `feature-docs/stop-reason-coverage/**`
- `test-docs/stop-reason-coverage/**`

`feature-docs/stop-reason-coverage/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`,
`VERIFICATION.md`, `retrospect.yaml`, and the design artifacts the design step
produces. Their generators are the phase documents and `references/phase-state.md`
(cited only; rules not restated).

`test-docs/stop-reason-coverage/**` covers `{T}.tests.yaml` (path form:
`test-docs/stop-reason-coverage/{T}.tests.yaml`). Its generator is
`implement-phase.md` (cited only; rules not restated).

**Semantics**:

- The default members are part of the declaration unless the SPEC author explicitly
  removes them. Removal is a deliberate narrowing, never an omission by silence.
- This declaration is a superset assertion: the actual change set must be CONTAINED
  IN the declaration. A declared path that is never generated is not a violation. A
  feature that produces no implement tasks generates no
  `test-docs/stop-reason-coverage/` directory, and the declared
  `test-docs/stop-reason-coverage/**` is still correct.

## 10. Anticipated Issues and Risks

### 10.1 Technical Issues

None recorded.

### 10.2 Business Risks

None recorded.

## 11. Success Criteria

### 11.1 Acceptance Criteria

- [ ] AC1 (b654786a7fb8e13c): the reason-code table contains `unmapped_stop`
  (stopped). The coverage table contains `unmapped-terminating-stop` →
  `unmapped_stop`. The fallback rule binds every terminating stop no other row names,
  including the four stops the task names, to exactly one code.
- [ ] AC2: the coverage section states that every other row, including
  stop-condition-N and the refusal row, takes precedence over the catch-all, and that
  the catch-all applies last.
- [ ] AC3: the catch-all's meaning is "a terminating stop no other row names", never
  "unknown cause". Its scope excludes wait turns, normal completion, `phase_done` and
  the 64 KiB no-result case, and the 64 KiB statement still adds no code or row.
- [ ] AC4: a catch-all stop's `detail` names the stop site and the concrete cause,
  and `resume_conditions` stays mandatory.
- [ ] AC5 (9e5ce22b85677b38): a coverage row maps the refusal-pattern hard fail to
  `gate_fail_closed`, with Source `references/batch-policies.yaml`.
- [ ] AC6 (6d3ffa3e04510229 / 454755f74a3e8a04): the `no-step` rule is
  condition-based and yields a `step` value for stop-condition-4 and Step A.5 stops.
- [ ] AC7 (e0aba3d91cffcb97): the precedence text says docs-commit-conflict writes no
  status.
- [ ] AC8 (c1e94c9399f18b7d): the stop-condition-3 restriction is route-based. A
  re-entry stop on a `failed` left by a prior run binds to `step_needs_intervention`,
  and implement-phase.md's pinned precedence sentence remains true.
- [ ] AC9: the pins REASON_CODES / STOP_POINT_KEYS / _KEY_CODE_PAIRS_IN_ORDER /
  NO_STEP_STOP_POINTS and the dependent pins in the other listed modules are synced.
  New tests prove both that existing rows win and that the catch-all applies to
  untabled stops, with a negative proof and a non-vacuity guard.
- [ ] AC10: `python3 -m unittest discover -s tests` passes and
  check-plugin-invariants.py stays green.
- [ ] AC11: plugin.json and marketplace.json both carry version 0.2.1 for
  em-workflow.

### 11.2 KPI

Not applicable.

## 12. Test Scenarios

### 12.1 Scenarios

- [ ] TS1: Extract the reason-code table and assert it equals the 13-code set
  including `unmapped_stop`. Negative proof: a table without it is rejected.
  Non-vacuity: the forged table is otherwise well formed.
- [ ] TS2: Run bidirectional coverage over 14 keys, including
  `unmapped-terminating-stop` and the refusal key. Existing negative proofs (missing
  key, code outside the set, duplicate key) are re-exercised against the widened
  constants.
- [ ] TS3: Precedence matcher: the coverage section states that named rows, including
  stop-condition-N and the refusal row, win over the catch-all, which applies last.
  Negative proof: a forged section that states the fallback without the
  lowest-precedence wording is rejected.
- [ ] TS4: A resolution helper in the test module maps a stop key to its row's code,
  and a key with no row to `unmapped_stop`. Fixtures: `stop-condition-3` →
  `step_needs_intervention` (an existing row wins); the refusal key →
  `gate_fail_closed`; designer-abort and schema_version-mismatch sites (no row) →
  `unmapped_stop`. Negative proof: a helper that ignores precedence is caught.
- [ ] TS5: Scope matcher: the catch-all text excludes wait turns, normal completion,
  `phase_done` and the 64 KiB no-result case, and the 64 KiB paragraph still says no
  reason code / no coverage row. Negative proof: forged text without the exclusions
  is rejected.
- [ ] TS6: Meaning-cell matcher: the `unmapped_stop` meaning says "no other row names"
  and does not describe an unknown cause. The detail rule requires the stop site and
  the concrete cause. Negative proof: forged "unknown cause" wording is rejected.
- [ ] TS7: The `no-step` bullet's extracted keys equal the synced NO_STEP_STOP_POINTS
  and are a subset of the coverage keys. The condition-based wording mentions
  stop-condition-4 and Step A.5.
- [ ] TS8: The route-based precedence wording replaces the state-based phrase, the
  three colliding keys are still named, and `no-work-required` is not named.
  implement-phase.md's pinned sentence is unchanged.
- [ ] TS9: The docs-commit-conflict no-status statement is present, and the old "all
  three leave a step's status `failed`" wording is absent.
- [ ] TS10: Whole-file literal guards: `unmapped_stop` is absent from SKILL.md,
  batch-mode.md and implement-phase.md.
- [ ] TS11: Exactly one documented code, context_budget_reached, has no coverage row
  (existing test, re-run).

## 13. Glossary

| Term | Definition |
|------|------------|
| catch-all | The `unmapped-terminating-stop` → `unmapped_stop` coverage row and its fallback rule (FR1, FR2) |

## 14. Confirmations

### 14.1 Confirmed Items

Assumptions recorded by requirements analysis (batch mode):

- [x] A1: The precedence rule becomes route-based as specified in FR8.
- [x] A2: docs-commit-conflict writes no status (FR7).
- [x] A3: The `no-step` rule is condition-based, and the named stop points become
  examples (FR6).
- [x] A4: The refusal-pattern hard fail maps to the existing `gate_fail_closed` code
  through a new row (FR5).
- [x] A5: The version bump is the patch 0.2.0 → 0.2.1.
- [x] A6: Literal ownership stays with batch-terminal-line.md, and the pointer
  documents are not edited (FR11).
- [x] A7: The catch-all identifiers are code `unmapped_stop` and stop-point key
  `unmapped-terminating-stop`, with Source `references/batch-terminal-line.md`.
- [x] A8: Updating loop-develop to accept `unmapped_stop` is out of scope and left as
  a follow-up.

### 14.2 Open Items

None.

## 15. References

- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/references/contracts/designer-contract.md`
- `em-workflow/references/phase-state.md`
- `em-workflow/references/batch-policies.yaml`
- `em-workflow/references/question-resolution.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/scripts/check-plugin-invariants.py`
- `feature-docs/batch-stop-contract/reviews/round2.yaml` (PR #8)
