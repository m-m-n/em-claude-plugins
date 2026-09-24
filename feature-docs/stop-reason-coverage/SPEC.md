# Feature: stop-reason-coverage

## Overview

`em-workflow/references/batch-terminal-line.md` gains a catch-all reason code
(`unmapped_stop`) and fallback rule, so that every batch-terminating stop is bound to
exactly one reason code by construction. The same change maps the refusal-pattern
hard fail to `gate_fail_closed`, makes the `no-step` rule condition-based, and
corrects the precedence rule. The contract test pins and the plugin version follow.
Requirements: `feature-docs/stop-reason-coverage/REQUIREMENTS.md`.

## Objectives

- Make the claim in batch-terminal-line.md that every terminating stop is bound to
  exactly one reason code true by construction. Use a catch-all fallback rather than
  a hand-maintained list of rows.
- Close the `step` value gap (the no-step enumeration) and the contradictions in the
  precedence rule (the docs-commit-conflict status claim; a state-based rather than
  route-based restriction for stop-condition-3).
- Keep the contract test suite and the plugin invariants green, with test pins synced
  to the new contract.

## User Stories

Not applicable.

## Technical Requirements

### Functional Requirements

- **FR1: Catch-all reason code and coverage row.** The closed stop reason-code set in
  batch-terminal-line.md gains one code, `unmapped_stop`, whose Applies-to `state` is
  `stopped`. The coverage table gains one row, `unmapped-terminating-stop` →
  `unmapped_stop`, whose Source cell is a backticked path that resolves under
  em-workflow/ (`references/batch-terminal-line.md`, where the fallback rule is
  defined). The code's meaning is "a terminating stop that no other coverage row
  names". It is never described as an unknown or undetermined cause. Neither
  identifier contains a dot. The literal `unmapped_stop` does not currently occur in
  skills/develop/SKILL.md, references/batch-mode.md or references/implement-phase.md
  (verified), and it must not be added to them.
- **FR2: Fallback rule with lowest precedence.** `## Stop point coverage` states a
  fallback rule. A terminating stop that no other row names binds to `unmapped_stop`.
  Every other row always takes precedence over the catch-all, including the generic
  `stop-condition-N` rows and the refusal-pattern row of FR5, and the catch-all
  applies last. The sentence "Every terminating stop point is bound to exactly one
  reason code above" is rewritten so it holds by construction: exactly one code,
  either a named row's code or the catch-all's. The existing precedence among named
  rows (phase-specific over generic, FR8) is unchanged in effect. The stops the task
  names fall to the catch-all through this rule: designer-contract.md's kind:none ×
  token-present abort with truncated candidate discovery, the em_workflow ×
  tokens.html-only pre-dispatch abort, and phase-state.md's unknown schema_version
  abort. So do the other untabled aborts found in question-resolution.md and
  batch-policies.yaml.
- **FR3: Catch-all scope limited to batch-terminating stops.** The fallback applies
  only to stops that terminate a batch run with `state` `stopped`. It never applies to
  wait turns (stop condition 5, implement's launch/wake turns), normal completion, a
  `--once` phase boundary (`phase_done`), the infra auto-resume (which is not a stop),
  or the 64 KiB size-collision outcome. The 64 KiB case keeps its existing statement
  that it emits no result and adds no reason code and no coverage row.
  `context_budget_reached` remains the only documented reason code without a coverage
  row.
- **FR4: detail and resume_conditions for a catch-all stop.** When `reason` is
  `unmapped_stop`, `detail` names the stop site (the owning document and step or
  section where the stop occurred) and the concrete cause. `resume_conditions` stays
  mandatory and non-whitespace, as for every `stopped` result.
- **FR5: Refusal-pattern hard fail mapped to gate_fail_closed (9e5ce22b85677b38).** A
  coverage row binds the create-spec.command-approval refusal-pattern hard fail to
  `gate_fail_closed`, with Source `references/batch-policies.yaml`. Its key is
  hyphenated with no dot, for example `command-refusal`. The `gate_fail_closed`
  Meaning cell is extended to name this abort. It keeps the
  `references/question-resolution.md` citation and the "both modes" / "interactive"
  wording, and does not re-enumerate `category: security`, `category: license` or
  `reversible: false`. No new code is minted for this stop.
- **FR6: Condition-based no-step rule (6d3ffa3e04510229 / 454755f74a3e8a04).** In the
  `step` bullet, `no-step` applies whenever no workflow.yaml step was executed in that
  turn or the stop occurs outside Step B. This condition governs, and the named stop
  points become non-exhaustive examples. The bullet explicitly covers two cases. A
  stop-condition-4 stop takes `no-step` when no step was executed in that turn;
  otherwise the general executed-step rule applies. A stop raised in Step A.5,
  including the refusal-pattern hard fail, takes `no-step`. The anchor phrase
  "`no-step` applies whenever" stays on one physical line. The step-domain declaration
  ("a closed value domain: one of the seven `workflow.yaml` step ids (...), or the
  single sentinel `no-step`.") is unchanged. Every backticked hyphenated key the
  bullet names must be a coverage-table key.
- **FR7: Precedence text matches Source documents (e0aba3d91cffcb97).** The precedence
  rule no longer says all three phase-specific stop points leave a step `failed`.
  implement-second-failure and verify-rework-cap write `failed`. docs-commit-conflict
  aborts without writing any status, because the failed write is itself the stop
  cause. The paragraph still names `implement-second-failure`, `verify-rework-cap` and
  `docs-commit-conflict`, and it does not name `no-work-required`.
- **FR8: Route-based stop-condition-3 restriction (c1e94c9399f18b7d).** The
  stop-condition-3 restriction becomes route-based. A phase-specific row wins when the
  current run reaches the stop through that phase's own abort route. This includes
  implement-second-failure, which the same run realizes through its next Step B
  evaluation. stop-condition-3 (`step_needs_intervention`) binds a stop at Step B's
  entry evaluation that reads a `failed` / `needs_update` status no route of the
  current run produced, such as a `failed` left by an earlier run's
  implement-second-failure. The implement `failed_kind` restriction (decision, or
  auto-resume cap reached) is kept. implement-phase.md's pinned sentence ("since
  `references/batch-terminal-line.md` already gives `implement-second-failure`
  precedence over `stop-condition-3`") stays true and unedited. The "Precedence rule:"
  label is kept.
- **FR9: Test pin sync and new catch-all tests.** Sync the pins to the new contract
  (13 codes, 14 reason-domain values, 14 coverage rows).
  tests/test_batch_stop_contract.py: REASON_CODES, STOP_POINT_KEYS,
  _KEY_CODE_PAIRS_IN_ORDER, NO_STEP_STOP_POINTS, the count-word tests ("twelve" →
  "thirteen", "thirteenth" → "fourteenth"), and _assert_precedence_rule_stated
  (replace the state-based "no phase-specific row covers" check with the route-based
  wording). tests/test_batch_stop_contract_skill_wiring.py: the REASON_CODES tuple and
  the member-count test (13 → 14). tests/test_failed_kind_batch_docs.py:
  EXPECTED_REASON_CODE_STATE_PAIRS and the pins on the state-based precedence phrase.
  tests/test_no_work_required_stop.py: EXPECTED_REASON_CODE_STATE_PAIRS, the exact
  coverage-row list and the set-size prose pins. tests/test_develop_once_option.py:
  SC5_REASON_CODES (absence list; add no_work_required and unmapped_stop). Add tests
  that verify three things: (a) every named row, including stop-condition-N and the
  refusal row, takes precedence over the catch-all; (b) a stop no row names resolves
  to `unmapped_stop`, with the task's untabled stops (designer aborts, phase-state
  schema_version mismatch) as fixtures; (c) the catch-all's scope excludes wait turns,
  normal completion, `phase_done` and the 64 KiB no-result case. Each new matcher
  carries a negative proof and a non-vacuity guard.
- **FR10: Version bump.** Bump em-workflow from 0.2.0 to 0.2.1 in both
  em-workflow/.claude-plugin/plugin.json and .claude-plugin/marketplace.json.
- **FR11: Literal ownership preserved.** Reason-code literals, the prefix and the
  field names remain owned by batch-terminal-line.md alone. skills/develop/SKILL.md,
  references/batch-mode.md and references/implement-phase.md receive no reason-code
  literal. SKILL.md's 「バッチ構造化結果」 enumeration already defers to the SSOT's
  stop points and is not edited.

### Non-Functional Requirements

- **NFR1 - Test suite:** `python3 -m unittest discover -s tests` passes; test modules
  import the Python standard library only.
- **NFR2 - Plugin invariants:** `em-workflow/scripts/check-plugin-invariants.py` stays
  green; new identifiers contain no dot, so they never match its gate_id shape.
- **NFR3 - Section stability:** batch-terminal-line.md's `## Result format`,
  `## Escaping` and `## Responsibility boundary` sections stay byte-identical. The
  nine level-2 headings and their order are unchanged, with `Stop reason codes`
  immediately followed by `Stop point coverage`.
- **NFR4 - Test authoring:** Test authoring follows the repository convention: each
  new matcher has a negative proof and a non-vacuity guard, and there is no
  cross-module test import.

## Implementation Approach

### Architecture

Not applicable (contract Markdown, tests and version fields only).

### Contract changes in `em-workflow/references/batch-terminal-line.md`

| Location | Change | Requirement |
|---|---|---|
| `## Stop reason codes` table | Add `unmapped_stop` (Applies-to `state`: `stopped`); meaning "a terminating stop that no other coverage row names" | FR1 |
| `## Stop reason codes` table, `gate_fail_closed` Meaning cell | Extend to name the refusal-pattern hard fail; keep the `references/question-resolution.md` citation and the "both modes" / "interactive" wording | FR5 |
| `## Stop point coverage` table | Add `unmapped-terminating-stop` → `unmapped_stop` (Source `references/batch-terminal-line.md`) | FR1 |
| `## Stop point coverage` table | Add the refusal-pattern row (hyphenated key, no dot) → `gate_fail_closed` (Source `references/batch-policies.yaml`) | FR5 |
| `## Stop point coverage` prose | Fallback rule with lowest precedence; rewrite of "Every terminating stop point is bound to exactly one reason code above" | FR2 |
| `## Stop point coverage` prose | Catch-all scope exclusions; 64 KiB statement kept | FR3 |
| `detail` / `resume_conditions` rule | Catch-all `detail` names the stop site and the concrete cause | FR4 |
| `step` bullet | Condition-based `no-step` rule; stop-condition-4 and Step A.5 cases | FR6 |
| Precedence rule | docs-commit-conflict writes no status; route-based stop-condition-3 restriction | FR7, FR8 |

Resulting counts: 13 codes, 14 reason-domain values, 14 coverage rows (FR9).

### Dependencies

**Internal Dependencies:**

- `em-workflow/references/implement-phase.md`: its pinned precedence sentence stays
  true and unedited (FR8).
- `em-workflow/scripts/check-plugin-invariants.py`: stays green (NFR2).

**External Dependencies:**

- None. Test modules import the Python standard library only (NFR1).

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json                 # version 0.2.1 (FR10)
└── references/batch-terminal-line.md          # FR1-FR8
.claude-plugin/marketplace.json                # em-workflow version 0.2.1 (FR10)
tests/
├── test_batch_stop_contract.py                # FR9
├── test_batch_stop_contract_skill_wiring.py   # FR9
├── test_failed_kind_batch_docs.py             # FR9
├── test_no_work_required_stop.py              # FR9
└── test_develop_once_option.py                # FR9
```

Not edited: `em-workflow/skills/develop/SKILL.md`,
`em-workflow/references/batch-mode.md`, `em-workflow/references/implement-phase.md`
(FR11).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/stop-reason-coverage/**`
- `test-docs/stop-reason-coverage/**`

`feature-docs/stop-reason-coverage/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/stop-reason-coverage/**` covers
`test-docs/stop-reason-coverage/{T}.tests.yaml`, the per-task test record. It
is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/stop-reason-coverage/` directory at all; the declared
`test-docs/stop-reason-coverage/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 (FR1, FR9, NFR4): Extract the reason-code table and assert it equals the
  13-code set including `unmapped_stop`. Negative proof: a table without it is
  rejected. Non-vacuity: the forged table is otherwise well formed.
- [ ] TS2 (FR1, FR5, FR9): Run bidirectional coverage over 14 keys, including
  `unmapped-terminating-stop` and the refusal key. Existing negative proofs (missing
  key, code outside the set, duplicate key) are re-exercised against the widened
  constants.
- [ ] TS3 (FR2, FR5, FR9, NFR4): Precedence matcher: the coverage section states that
  named rows, including stop-condition-N and the refusal row, win over the catch-all,
  which applies last. Negative proof: a forged section that states the fallback
  without the lowest-precedence wording is rejected.
- [ ] TS4 (FR2, FR5, FR9, NFR4): A resolution helper in the test module maps a stop
  key to its row's code, and a key with no row to `unmapped_stop`. Fixtures:
  `stop-condition-3` → `step_needs_intervention` (an existing row wins); the refusal
  key → `gate_fail_closed`; designer-abort and schema_version-mismatch sites (no row)
  → `unmapped_stop`. Negative proof: a helper that ignores precedence is caught.
- [ ] TS5 (FR3, FR9, NFR4): Scope matcher: the catch-all text excludes wait turns,
  normal completion, `phase_done` and the 64 KiB no-result case, and the 64 KiB
  paragraph still says no reason code / no coverage row. Negative proof: forged text
  without the exclusions is rejected.
- [ ] TS6 (FR1, FR4, FR9, NFR4): Meaning-cell matcher: the `unmapped_stop` meaning
  says "no other row names" and does not describe an unknown cause. The detail rule
  requires the stop site and the concrete cause. Negative proof: forged "unknown
  cause" wording is rejected.
- [ ] TS7 (FR6, FR9): The `no-step` bullet's extracted keys equal the synced
  NO_STEP_STOP_POINTS and are a subset of the coverage keys. The condition-based
  wording mentions stop-condition-4 and Step A.5.
- [ ] TS8 (FR7, FR8, FR9): The route-based precedence wording replaces the
  state-based phrase, the three colliding keys are still named, and
  `no-work-required` is not named. implement-phase.md's pinned sentence is unchanged.
- [ ] TS9 (FR7, FR9): The docs-commit-conflict no-status statement is present, and
  the old "all three leave a step's status `failed`" wording is absent.
- [ ] TS10 (FR11): Whole-file literal guards: `unmapped_stop` is absent from
  SKILL.md, batch-mode.md and implement-phase.md.
- [ ] TS11 (FR3): Exactly one documented code, context_budget_reached, has no
  coverage row (existing test, re-run).

### Integration Tests

- [ ] `python3 -m unittest discover -s tests` passes (NFR1).
- [ ] `em-workflow/scripts/check-plugin-invariants.py` stays green (NFR2).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] A re-entry stop on a `failed` left by a prior run binds to
  `step_needs_intervention` (FR8, AC8).
- [ ] A stop-condition-4 stop with no step executed in that turn takes `no-step`;
  otherwise the general executed-step rule applies (FR6, AC6).
- [ ] The 64 KiB size-collision outcome emits no result and adds no reason code and
  no coverage row (FR3, AC3).

### Performance Tests

Not applicable.

## Security Considerations

Not applicable.

## Error Handling

Not applicable.

## Performance Optimization

Not applicable.

## Success Criteria

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

## Assumptions

- A1: The precedence rule becomes route-based as specified in FR8.
- A2: docs-commit-conflict writes no status (FR7).
- A3: The `no-step` rule is condition-based, and the named stop points become
  examples (FR6).
- A4: The refusal-pattern hard fail maps to the existing `gate_fail_closed` code
  through a new row (FR5).
- A5: The version bump is the patch 0.2.0 → 0.2.1.
- A6: Literal ownership stays with batch-terminal-line.md, and the pointer documents
  are not edited (FR11).
- A7: The catch-all identifiers are code `unmapped_stop` and stop-point key
  `unmapped-terminating-stop`, with Source `references/batch-terminal-line.md`.
- A8: Updating loop-develop to accept `unmapped_stop` is out of scope and left as a
  follow-up.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. No requirement has `status: tbd`.

## References

- Requirements: `feature-docs/stop-reason-coverage/REQUIREMENTS.md`
- Contract SSOT: `em-workflow/references/batch-terminal-line.md`
- Stop sources: `em-workflow/references/contracts/designer-contract.md`,
  `em-workflow/references/phase-state.md`, `em-workflow/references/batch-policies.yaml`,
  `em-workflow/references/question-resolution.md`
- Pinned sentence: `em-workflow/references/implement-phase.md`
- Invariants: `em-workflow/scripts/check-plugin-invariants.py`
