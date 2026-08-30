# Feature: develop-once-option

## Overview

`--once` is a new per-invocation argument for the `develop` skill. When it is
given, the run executes exactly one phase and ends the turn instead of
self-driving to the next step. It is never persisted, it combines with
`--batch`, and a run without it behaves exactly as today.

Requirements document: `feature-docs/develop-once-option/REQUIREMENTS.md`.

## Objectives

- Cut the develop orchestrator's context consumption at phase boundaries by
  ending the turn after one phase when `--once` is given.
- Let an outer driver advance a feature one phase per Claude Code launch,
  re-launching the same feature after each phase.

## User Stories

### US1: Advance one phase per launch from an outer driver
As an outer driver, I want each `--batch --once` launch to execute exactly one
phase and end, so that I can advance a feature one phase per Claude Code launch
and re-launch the same feature afterwards.

**Acceptance Criteria:**
- [ ] AC1: SKILL.md's 引数処理 documents `--once` as per-invocation, combinable
      with `--batch`, and persisted nowhere; the frontmatter `argument-hint`
      includes it.
- [ ] AC2: SKILL.md's 「ターンを終わらせていい唯一の条件」 has a seventh item
      covering the `--once` phase boundary, with items 1-6 unchanged.
- [ ] AC3: SKILL.md states the phase-boundary definition covering all four
      boundary kinds: a step reaching `completed`/`skipped`; retrospect
      `completed` with Step C deferred to the next launch; the verify-fail
      rework patch commit; and the two automatic-re-entry routing commits
      (implement I.2.c route-back, rework spec-change).
- [ ] AC4: batch-terminal-line.md defines the third `state` value with
      `reason=none` and a non-empty `detail`, states the `step` field carries
      the executed step (verify at the verify-fail rework boundary), and leaves
      `completed`/`stopped` semantics, the eleven reason codes and the coverage
      table unchanged.
- [ ] AC5: batch-terminal-line.md still has exactly its seven level-2 headings
      in order, and every cardinality statement about terminal states is true
      after the addition.

### US2: Keep the SSOT partition mechanically enforced
As a maintainer of the batch terminal-line contract, I want pointer documents to
carry no value literal and the existing literal guard to cover `state` values,
so that the contract document stays the sole owner of every value domain.

**Acceptance Criteria:**
- [ ] AC6: Neither SKILL.md nor batch-mode.md contains any `state` value
      literal, the prefix literal, all four field-name tokens together, any
      reason code, or the sentinel.
- [ ] AC7: The extended literal guard fails against a forged SKILL.md /
      batch-mode.md excerpt that restates the new `state` value, and passes
      against the real files — including against their existing `completed` /
      `skipped` / `stopped` step-status prose (no false positive).
- [ ] AC8: SKILL.md's 「バッチ終端行」 subsection still directly follows
      「停止時の報告」 with no other level-2 heading between them, still
      instructs Reading the contract document immediately before emitting, and
      still states the generalized no-line rule naming 停止条件 5 and
      implement's launch/wake turns.

### US3: Be told how to continue in interactive mode
As a user running develop interactively with `--once`, I want the closing report
to tell me how to continue, so that I know the exact next launch to run.

**Acceptance Criteria:**
- [ ] AC9: The interactive `--once` closing line matches the specified text
      exactly, with `{step}` and `{feature}` substituted.
- [ ] AC10: `version` is identical in `em-workflow/.claude-plugin/plugin.json`
      and `.claude-plugin/marketplace.json`, and higher than before.
- [ ] AC11: `python3 -m unittest discover -s tests` passes, including the three
      pre-existing modules in reference_scan_targets.

## Technical Requirements

### Functional Requirements

- **FR1 — `--once` argument handling:** `em-workflow/skills/develop/SKILL.md`'s
  「引数処理」 gains `--once`: when present, the run executes one phase and ends
  the turn instead of advancing to the next step. It is a per-invocation setting
  only — it is never written to `workflow.yaml` and never to `phase-state/`. It
  combines with `--batch`. Without the flag, the run behaves exactly as today
  (self-driving until every `workflow[]` step is `completed`, `design` may be
  `skipped`). The skill's frontmatter `argument-hint` lists the flag.
- **FR2 — Definition of one phase (the `completed` boundary):** One phase is:
  one `workflow[]` step executed, its `status` settled to `completed`
  (`skipped` for `design` only), and that state committed. The turn ends at that
  point.
- **FR3 — Step C is its own phase:** Step C (完了処理) counts as one independent
  phase. Under `--once` the turn ends when `retrospect` reaches `completed`;
  Step C runs on the next launch.
- **FR4 — verify-fail rework boundary:** When verify records `fail`, one phase
  completes at the point where the rework patch has been applied, `implement`
  and `verify` are back to `pending`, and the change is committed. The next
  launch resumes at `implement`.
- **FR5 — Non-`completed` phase boundaries:** The two automatic-re-entry
  transitions enumerated in SKILL.md Step B's 「停止条件 3 との優先関係」 are
  also `--once` phase boundaries: implement I.2.c's route back to planning
  (`create-plan` → `needs_update`) and rework's spec-change transition
  (`create-spec` → `needs_update`). In both, the turn ends once the routing
  patch is applied and committed. `--once` promises one phase, not one
  `completed` status transition.
- **FR6 — Stop condition 7:** SKILL.md's 「ターンを終わらせていい唯一の条件」
  list gains item 7: under `--once`, when one phase has completed. The existing
  six conditions and their wording are unchanged.
- **FR7 — Batch terminal line, third `state` value:**
  `em-workflow/references/batch-terminal-line.md` — the sole owner of the line's
  value domains — adds a third `state` value for the `--once` phase boundary,
  emitted with `reason=none` and a non-empty single-line `detail`, using the
  same prefix and the same four fields in the same order. `state=completed` and
  `state=stopped` keep their current meanings, and the eleven stop reason codes
  plus the stop-point coverage table are unchanged. The document states that an
  outer driver re-launches the same feature on seeing the new state.
- **FR8 — Terminal line `step` at a `--once` boundary:** The terminal line's
  `step` names the step executed in that turn, not the step the next launch will
  resume at. At the verify-fail rework boundary the value is `verify`. The line
  describes the phase that ended the invocation; it is not a resume cursor.
- **FR9 — SSOT partition, no state-value literal in SKILL.md:** SKILL.md's
  「バッチ終端行」 subsection states only WHEN the line is emitted for a `--once`
  phase boundary; it carries no `state` value literal, keeping the existing
  instruction to Read `${CLAUDE_PLUGIN_ROOT}/references/batch-terminal-line.md`
  immediately before emitting and to use the prefix, field grammar and value
  sets defined there. `references/batch-mode.md` likewise restates no value
  literal.
- **FR10 — Literal guard extended to `state` values:** The existing
  contract-literal guard in `tests/test_batch_stop_contract_skill_wiring.py`
  (`_find_contract_literal_violations`, applied to both SKILL.md and
  batch-mode.md) and the equivalent absence check in
  `tests/test_batch_stop_contract.py`
  (`TestBatchModePointer.test_restates_no_contract_literal`) are extended to
  cover the `state` value set, so FR9 is enforced mechanically rather than by
  convention. The extension must not false-positive on `completed` / `stopped` /
  `skipped`, which both documents already use as ordinary `workflow.yaml`
  step-status vocabulary — the guard is scoped the way the four field names
  already are (checked as a contract-specific shape, not as bare words).
- **FR11 — Terminal-state cardinality wording:** Wording that pins the number of
  terminal states must stay true after FR7: batch-terminal-line.md's `state`
  bullet ("closed set of two values") and its 「No line on a wait turn」 sentence
  ("either of the contract's two terminal states"), and SKILL.md's
  「同 SSOT が定める 2 つの終端状態のいずれか」. SKILL.md expresses the rule
  without pinning the cardinality and without naming any state value (FR9).
- **FR12 — Interactive closing line:** In interactive mode the `--once` closing
  report adds exactly one line:
  `{step} が完了したよ。続きは /clear してから /em-workflow:develop {feature} を実行してね`.
- **FR13 — Plugin version bump:** Per
  `.claude/rules/core-plugin-version-bump.md`, the same change bumps `version`
  in both `em-workflow/.claude-plugin/plugin.json` and the repository-root
  `.claude-plugin/marketplace.json` to the same value. The target is
  0.1.50 → 0.1.51.
- **FR14 — No mid-implement termination:** `--once` never ends the turn inside
  the implement phase. In-flight background implementers are lost on process
  exit, so the turn ends only at a phase boundary. Stop condition 5's wait
  turns, and implement's launch and wake turns, remain non-terminal and emit no
  terminal line.

### Non-Functional Requirements

- **NFR1 - SSOT partition preserved:** `references/batch-terminal-line.md`
  remains the sole owner of the prefix, the field grammar and every value
  domain. Pointer documents name the document and restate no literal. The prefix
  continues to occur, among all files under `em-workflow/`, only in that
  document and only inside fenced example blocks.
- **NFR2 - Documentation-only change surface:** The change touches Markdown
  prompts/reference documents plus two JSON version fields. No runtime script
  behaviour changes, so verification is by structural/textual assertion over the
  files, matching the convention the three scanned test modules already follow.
- **NFR3 - Test conventions:** New tests live in the repository-root `tests/`
  directory as `test_*.py`, discovered by
  `python3 -m unittest discover -s tests`, and import the Python standard
  library only (`test/README.md`; enforced in-module by
  `TestOwnModuleStdlibOnly`). Every new matcher carries a negative proof plus a
  non-vacuity guard; pure regression guards over retained wording are exempt,
  per the convention documented in the existing modules.
- **NFR4 - Backward compatibility:** A launch without `--once` produces
  byte-identical behaviour to today. Existing pinned structures stay intact:
  batch-terminal-line.md's seven level-2 headings in order, its eleven reason
  codes and eleven-row coverage table, and batch-mode.md's ten-row Non-packet
  gates table with its catch-all / diff-size / per-command wording.
- **NFR5 - Reporting completeness in batch:** A `--once` batch turn still emits
  the terminal line as the last line of the final assistant message, with
  `detail` normalized to one physical line and carrying no confidential
  information beyond paths.

## Implementation Approach

### Architecture

The change is documentation-only (NFR2). Three layers are involved, and the
partition between them is itself a requirement (NFR1, FR9):

```
┌──────────────────────────────────────────────────────────┐
│  Prompt layer   skills/develop/SKILL.md                  │
│                 - argument handling (FR1)                │
│                 - phase-boundary definition (FR2-FR5)    │
│                 - stop condition 7 (FR6)                 │
│                 - WHEN to emit the line only (FR9, FR11) │
├──────────────────────────────────────────────────────────┤
│  Pointer layer  references/batch-mode.md                 │
│                 - names the contract, no literal (FR9)   │
├──────────────────────────────────────────────────────────┤
│  Contract SSOT  references/batch-terminal-line.md        │
│                 - prefix, field grammar, value domains   │
│                 - third `state` value (FR7, FR8)         │
├──────────────────────────────────────────────────────────┤
│  Enforcement    tests/test_batch_stop_contract*.py       │
│                 - literal guard over `state` (FR10)      │
└──────────────────────────────────────────────────────────┘
```

**Component Diagram:**

```
outer driver ──launch(--batch --once)──▶ develop (SKILL.md)
             ◀──terminal line (state/step/reason/detail)──
             └──re-launch same feature──▶
```

### Data Flow

```
launch --once → execute one workflow[] step
              → settle status + commit          (FR2/FR3/FR4/FR5)
              → batch: emit terminal line       (FR7/FR8/NFR5)
                interactive: emit closing line  (FR12)
              → end turn                        (FR6)
```

No persisted data is added: `--once` is per-invocation and is written neither to
`workflow.yaml` nor to `phase-state/` (FR1).

### Phase boundaries

The four boundary kinds an implementation must treat identically (AC3):

| Boundary | Ends the turn when | Terminal-line `step` | Next launch resumes at |
|---|---|---|---|
| Ordinary step (FR2) | step `status` is `completed` (`skipped` for `design`) and committed | the executed step | the following step |
| `retrospect` (FR3) | `retrospect` reaches `completed` | `retrospect` | Step C (完了処理) |
| verify-fail rework (FR4, FR8) | rework patch applied, `implement`/`verify` back to `pending`, committed | `verify` | `implement` |
| automatic re-entry (FR5) | routing patch applied and committed (`create-plan` → `needs_update`, or `create-spec` → `needs_update`) | the executed step | the re-entered step |

Non-boundaries (FR14): stop condition 5's wait turns and implement's launch and
wake turns — non-terminal, no terminal line.

### API Design

Not applicable — this feature exposes no API.

### Database Schema

Not applicable — this feature adds no persisted data (FR1).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-terminal-line.md`: sole owner of the terminal
  line's prefix, field grammar and value domains (FR7, NFR1).
- `em-workflow/references/batch-mode.md`: pointer document that must restate no
  literal (FR9, NFR4).
- `tests/test_batch_stop_contract_skill_wiring.py`,
  `tests/test_batch_stop_contract.py`: the literal guard extended by FR10.
- `.claude/rules/core-plugin-version-bump.md`: the version-bump rule FR13
  follows.

**External Dependencies:**
- Python standard library only; tests import nothing else (NFR3).

### File Structure

```
em-workflow/
├── skills/develop/SKILL.md              # FR1, FR2-FR6, FR9, FR11, FR12, FR14
├── references/
│   ├── batch-terminal-line.md           # FR7, FR8, FR11 (contract SSOT)
│   └── batch-mode.md                    # FR9 (pointer, no literal)
└── .claude-plugin/plugin.json           # FR13
.claude-plugin/marketplace.json          # FR13
tests/
├── test_batch_stop_contract_skill_wiring.py   # FR10
└── test_batch_stop_contract.py                # FR10
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/develop-once-option/**`
- `test-docs/develop-once-option/**`

`feature-docs/develop-once-option/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/develop-once-option/**` covers
`test-docs/develop-once-option/{T}.tests.yaml`, the per-task test record. It is
generated and owned by `implement-phase.md`; this section cites it and restates
none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/develop-once-option/` directory at all; the declared
`test-docs/develop-once-option/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1: Whole suite — `python3 -m unittest discover -s tests` from the
      repository root. (NFR2, NFR3)
- [ ] TS2: Plugin invariants — `python3 em-workflow/scripts/check-plugin-invariants.py`
      against the repository root exits 0 (evidence: AC-5 of
      `tests/test_batch_stop_contract_skill_wiring.py`). (FR13)
- [ ] TS3: Contract document structure — heading count/order, the new `state`
      value's presence in the `## Field values` domain, `reason=none` pairing,
      and the executed-step rule for `step`. (FR7, FR8, FR11, NFR4)
- [ ] TS4: Pointer-document literal absence — extended
      `_find_contract_literal_violations` over SKILL.md's 「バッチ終端行」
      subsection and batch-mode.md's `## Terminal line`, plus a whole-file
      prefix-absence check. (FR9, FR10, NFR1)
- [ ] TS5: Guard negative proof — a forged subsection restating the new `state`
      value is rejected; a non-vacuity guard proves the forged text is otherwise
      well-formed and sliced correctly. (FR10, NFR3)
- [ ] TS6: Guard false-positive proof — the real SKILL.md (which uses
      `completed` / `skipped` extensively for step statuses) yields zero
      violations. (FR10)
- [ ] TS7: Stop-condition list — item 7 present, items 1-6 unchanged, bullet-3
      slicing (`3. ` … `4. `) still works. (FR5, FR6, NFR4)

### Integration Tests

- [ ] TS8: Placement regression — no level-2 heading between
      「## 停止時の報告」 and 「## バッチ終端行」. (FR9, NFR4)
- [ ] TS9: Prefix uniqueness sweep over every file under `em-workflow/` still
      finds the prefix only in batch-terminal-line.md, only inside fenced
      blocks. (NFR1)
- [ ] TS10: Non-regression — batch-mode.md's Non-packet gates table still has
      ten data rows; batch-terminal-line.md's reason-code table still extracts
      to eleven codes and its coverage table to the eleven pinned key→code
      pairs. (FR7, NFR4)

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] Verify-fail rework boundary: the terminal line's `step` is `verify`, not
      the resumption point `implement`. (FR4, FR8)
- [ ] `retrospect` completion: the turn ends there and Step C runs on the next
      launch rather than in the same turn. (FR3)
- [ ] Automatic re-entry transitions: the turn ends after the routing commit
      even though no step reached `completed`. (FR5)
- [ ] Inside implement: wait turns and launch/wake turns never end the turn and
      emit no terminal line. (FR14)
- [ ] Guard scoping: `completed` / `skipped` / `stopped` used as ordinary
      step-status vocabulary in the pointer documents must not be flagged.
      (FR10)

### Performance Tests

Not applicable — no performance requirement is in scope.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** Not applicable.
- **Data Protection:** The terminal line's `detail` carries no confidential
  information beyond paths, and is normalized to one physical line (NFR5).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

No error codes are introduced. The failure modes in scope are guard outcomes
over the documents:

| Condition | Detected by | Outcome |
|---|---|---|
| A pointer document restates a `state` value literal | extended literal guard (FR10) | Test failure |
| The guard flags step-status prose (`completed` / `skipped` / `stopped`) | false-positive proof over the real files (FR10, AC7) | Test failure |
| A cardinality statement about terminal states became false | contract-structure assertions (FR11, AC5) | Test failure |

## Performance Optimization

Not applicable — no performance goal is in scope. The feature's purpose is
context-consumption reduction at phase boundaries, achieved by ending the turn
(FR1, FR2).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC1–AC11 in REQUIREMENTS.md 11.1 are all satisfied
- [ ] A launch without `--once` behaves byte-identically to today (NFR4)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement is `resolved`.

## Assumptions

- **A1:** The implement I.2.c route-back and the rework spec-change transitions
  are `--once` phase boundaries; the turn ends once the routing patch is applied
  and committed.
- **A2:** The terminal line's `step` carries the step executed in that turn
  (`verify` at the verify-fail rework boundary), not the resume point.
- **A3:** SKILL.md carries no `state` value literal; the existing literal guard
  is extended to `state` values to enforce it mechanically.
- **A4:** The design step is skipped on the analyst's recommendation, without a
  separate user confirmation.
- **A5:** The current plugin version is 0.1.50 and the target is 0.1.51. The
  current value was confirmed in both
  `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

## Design Step

`skipped`. The change is confined to Markdown prompt/reference documents, their
test modules and two JSON version fields. There is no user interface, no visual
surface and no design system in this project (design-system candidates resolved
to zero paths), so the design step has no artifact to produce.

## References

- Requirements document: `feature-docs/develop-once-option/REQUIREMENTS.md`
- develop skill: `em-workflow/skills/develop/SKILL.md`
- Terminal-line contract SSOT: `em-workflow/references/batch-terminal-line.md`
- Batch mode: `em-workflow/references/batch-mode.md`
- Existing guards: `tests/test_batch_stop_contract_skill_wiring.py`,
  `tests/test_batch_stop_contract.py`
- Test conventions: `test/README.md`
- Version-bump rule: `.claude/rules/core-plugin-version-bump.md`
- Change-set derivation: `references/phases/create-plan-phase.md`
