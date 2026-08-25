# Verification Document: develop-once-option

## Overview

**Feature**: develop-once-option
**SPEC.md**: `feature-docs/develop-once-option/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/develop-once-option/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged. Per-task acceptance criteria live in `tasks/taskNNNN.md`.

## Build Verification

- Command: none. `workflow.yaml` `project.components.main.build_command` is
  empty — this repository is a Claude Code plugin marketplace with no build
  step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository
  root.
- Expected: exit code 0, no failures and no errors.
- Coverage target: not measured. The project runs no coverage tool; coverage
  is expressed as the requirement → scenario mapping below, and every
  requirement must reach at least one scenario.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Whole suite: `python3 -m unittest discover -s tests` from the repository root | exit 0, no failures, no errors | Unit |
| TS2 | Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py` against the repository root | exit 0 | Integration |
| TS3 | Contract-document structure: exactly seven level-2 headings in order; `## Field values` carries the third `state` value; it is paired with `reason=none` and a non-empty single-line `detail`; the `step` field's executed-step rule (with `verify` at the verify-fail rework boundary); every count-bearing statement about terminal states is true; `state=completed` / `state=stopped` keep their meanings | all assertions pass | Unit |
| TS4 | Pointer-document literal absence: the extended contract-literal guard over SKILL.md and `batch-mode.md` reports zero violations, the prefix is absent from both whole files, and the retained subsection guarantees hold (terminal line is the last line of the final assistant message, the Read-before-emitting instruction, the generalized no-line rule) | zero violations; all retained assertions pass | Unit |
| TS5 | Guard negative proof: a forged SKILL.md subsection and a forged `batch-mode.md` section that restate the new `state` value are both rejected, each with a non-vacuity guard proving the forged text is otherwise well-formed and correctly sliced | forged samples rejected; non-vacuity guards pass | Unit |
| TS6 | Guard false-positive proof: the real SKILL.md and the real `batch-mode.md` — which use `completed` / `skipped` / `stopped` as ordinary step-status vocabulary — yield zero violations under the extended guard in both modules | zero violations | Unit |
| TS7 | Stop-condition list: item 7 is present, items 1-6 are unchanged, and the bullet-3 slicing (`3. ` … `4. `) used by the pre-existing module still works | all assertions pass | Unit |
| TS8 | Placement regression: no level-2 heading sits between 「## 停止時の報告」 and 「## バッチ終端行」 | assertion passes | Integration |
| TS9 | Prefix-uniqueness sweep over every file under `em-workflow/`: the prefix occurs only in `references/batch-terminal-line.md`, and there only inside fenced blocks | no offenders | Integration |
| TS10 | Non-regression: `batch-mode.md`'s Non-packet gates table still has ten data rows with its catch-all / diff-size / per-command wording; the contract's reason-code table still extracts to eleven codes; its coverage table still extracts to the eleven pinned key→code pairs | all assertions pass | Integration |
| TS11 | `--once` argument documentation: 「引数処理」 states the flag is per-invocation, combinable with `--batch`, and persisted neither to `workflow.yaml` nor to `phase-state/`; the frontmatter `argument-hint` lists it | all assertions pass | Unit |
| TS12 | Phase-boundary definition: SKILL.md covers all four boundary kinds — ordinary step `completed`/`skipped` plus commit, `retrospect` `completed` with Step C deferred to the next launch, the verify-fail rework patch commit, and the two automatic-re-entry routing commits | all four kinds present | Unit |
| TS13 | Interactive closing line: the `--once` closing report line matches the specified text exactly, including the `{step}` and `{feature}` placeholders | exact match (whitespace-stripped comparison) | Unit |
| TS14 | Non-boundaries: SKILL.md states that `--once` never ends the turn inside the implement phase, and that stop condition 5's wait turns and implement's launch and wake turns stay non-terminal and emit no terminal line | all assertions pass | Unit |
| TS15 | Version parity: the em-workflow `version` in `em-workflow/.claude-plugin/plugin.json` and in the `.claude-plugin/marketplace.json` entry selected by name are identical and greater than the pre-change value | assertion passes | Unit |
| TS16 | `reason` value-domain coherence: the contract's `## Field values` `reason` bullet and the closing prose of `## Stop reason codes` both reserve `none` for the non-stop states, naming `state=completed` and `state=phase_done`; neither retains a formulation limiting `none` to `state=completed` alone; `none` is still stated not to be a stop reason code and never to accompany `state=stopped`; the eleven reason codes still all carry `Applies to state` = `stopped` | all assertions pass; a forged section carrying the old single-state restriction is rejected, with a non-vacuity guard | Unit |
| TS17 | `step` rule precedence: the `step` bullet states the executed-step rule together with the two rules that take precedence over it — the `no-step` sentinel when no `workflow.yaml` step is in effect, and `retrospect` on `state=completed` — and states that a Step C turn's value differs by outcome (`retrospect` on normal completion, `no-step` on `step-c-abort`); the `verify`-at-the-verify-fail-rework-boundary example is retained | all assertions pass; removing an exception clause fails the assertion | Unit |
| TS18 | Terminal-line emission condition in SKILL.md: 「## バッチ終端行」 defines emission by the turn having reached a terminal state the SSOT defines, not by the turn ending the run, so the `--once` phase boundary falls inside the definition; the last-line rule, the Read-before-emitting instruction, the stop-point enumeration and the generalized no-line rule (停止条件 5, implement's launch and wake turns) are all retained; no `state` value literal and no terminal-state count appears anywhere in the file | all assertions pass; a forged subsection carrying the old run-ending-only definition is rejected, with a non-vacuity guard | Unit |
| TS19 | Guard false-positive proof shape: `tests/test_batch_stop_contract_skill_wiring.py` asserts nothing about whether a guard-whitelisted step-status word occurs in the real SKILL.md or `batch-mode.md`; whitelist tolerance is proven against synthetic samples; the two whole-file zero-violation checks over the real files and the `completed` / `skipped` non-vacuity check remain | all assertions pass | Unit |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; this
  repository runs no formatter.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py`
  (TS2) is the repository's structural checker and stands in for one — it
  covers agent-dispatch parity, stale references, gate-id coverage and
  domains-vocabulary parity across the plugin's documents.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | The Functional Requirements Coverage table below has no empty cell |
| SC2 | All test scenarios pass | TS1 through TS19 all green |
| SC3 | Security requirements are satisfied | SPEC.md declares no applicable security requirement beyond `detail` carrying no confidential information beyond paths — checked as part of TS3's `detail` assertions |
| SC4 | Documentation is complete | The three documents state argument handling, all four phase boundaries, the emission occasions and the value domain, each in its owning layer |
| SC5 | Code review is completed | review phase records no residual critical/high finding |
| SC6 | AC1-AC11 of REQUIREMENTS.md 11.1 are satisfied | AC1→TS11, AC2→TS7, AC3→TS12, AC4→TS3/TS16/TS17, AC5→TS3/TS10/TS16, AC6→TS4, AC7→TS5/TS6/TS19, AC8→TS4/TS8/TS18, AC9→TS13, AC10→TS15/TS2, AC11→TS1 |
| SC7 | A launch without `--once` behaves byte-identically to today | TS7 (items 1-6 unchanged), TS8, TS10 and the whole pre-existing suite in TS1 stay green; no task changes a runtime script |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS11, TS1 |
| FR2 | task0001 | TS12 |
| FR3 | task0001 | TS12 |
| FR4 | task0001 | TS12 |
| FR5 | task0001 | TS7, TS12 |
| FR6 | task0001 | TS7 |
| FR7 | task0003, task0005 | TS3, TS10, TS16 |
| FR8 | task0003, task0005 | TS3, TS17 |
| FR9 | task0002, task0006 | TS4, TS8, TS18 |
| FR10 | task0002, task0003, task0006 | TS4, TS5, TS6, TS19 |
| FR11 | task0002, task0003, task0005, task0006 | TS3, TS4, TS16, TS18 |
| FR12 | task0001 | TS13 |
| FR13 | task0004 | TS2, TS15 |
| FR14 | task0001, task0006 | TS14, TS18 |
| NFR1 | task0002, task0003, task0006 | TS4, TS9 |
| NFR2 | task0001, task0002, task0003, task0004, task0005, task0006 | TS1 |
| NFR3 | task0001, task0002, task0003, task0004, task0005, task0006 | TS1, TS5, TS19 |
| NFR4 | task0001, task0002, task0003, task0005, task0006 | TS3, TS7, TS8, TS10, TS16, TS17 |
| NFR5 | task0002, task0003, task0006 | TS3, TS4, TS18 |

## E2E Testing

Not applicable. `project.components.main.e2e_test_command` is empty and the
repository has no E2E framework. The feature's own end-to-end behaviour — an
outer driver re-launching after each phase — is a property of the develop
orchestrator's prompt, which has no automated harness in this repository; it
is covered by the manual item below.

## Manual Testing (E2E Not Possible)

- [ ] Read the merged 「## バッチ終端行」 section and `batch-mode.md`'s
      `## Terminal line` end to end and confirm an orchestrator following
      them would emit exactly one terminal line at a `--once` phase
      boundary, and none on a wait / launch / wake turn.
- [ ] Read the merged phase-boundary definition and confirm each of the four
      boundary kinds is unambiguous about the point at which the turn ends
      (after the commit, never before).
- [ ] Confirm the interactive closing line reads naturally with `{step}` and
      `{feature}` substituted by a real value.
- [ ] Confirm no mockup / design-artifact comparison is required: the design
      step is `skipped` for this feature and there is no visual surface.

## Performance / Security Verification (if applicable)

- Performance: not applicable — SPEC.md declares no performance requirement.
- Security: the terminal line's `detail` carries no confidential information
  beyond paths and is normalized to one physical line (NFR5) — verified
  textually as part of TS3.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 19 | 19 | 0 | 0 |
| Success criteria | 7 | 6 | 0 | 1 (SC5, review phase) |
| Manual checks | 4 | 0 | 0 | 4 |
