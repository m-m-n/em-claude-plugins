# Verification Document: stop-reason-coverage

## Overview

- **Feature**: stop-reason-coverage
- **SPEC.md**: `feature-docs/stop-reason-coverage/SPEC.md`
- **IMPLEMENTATION.md**: `feature-docs/stop-reason-coverage/IMPLEMENTATION.md`

## Build Verification

- Command: not applicable. `project.components.main.build_command` is empty,
  because the change is contract Markdown, tests and version fields.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository
  root.
- Expected: exit code 0, with no failures and no errors.
- Coverage target: not applicable. These are documentation-contract tests, and
  no coverage tooling is configured.

### Test Scenarios from SPEC.md

Scenario IDs TS-1 to TS-11 correspond one-to-one to SPEC.md TS1 to TS11.
TS-12 to TS-16 add the SPEC requirements that SPEC's list does not carry as a
scenario of its own.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Extract the `## Stop reason codes` table's codes and compare them with the 13-code set that includes `unmapped_stop` (Applies-to `stopped`). A forged 12-row table without it goes through the same matcher | The live set equals the 13-code set. The forged table is rejected, and its non-vacuity guard shows it is otherwise well formed | Unit |
| TS-2 | Bidirectional coverage over the 14 keys, including `unmapped-terminating-stop` and `command-refusal`. The missing-key, code-outside-set, duplicate-key and reserved-code-row negative proofs are re-run against the widened constants. Source paths are resolved | Every key appears exactly once. Every code in the 13-code set is bound, and no bound code falls outside it. Every forged table is rejected. Every Source path resolves under `em-workflow/` | Unit |
| TS-3 | Fallback precedence matcher over the "Fallback rule:" paragraph | The paragraph states that named rows, including `stop-condition-N` and `command-refusal`, take precedence over the catch-all, which applies last. The old sentence "Every terminating stop point is bound to exactly one reason code above" is absent. A forged paragraph without the lowest-precedence wording is rejected | Unit |
| TS-4 | A resolver over the live coverage pairs, with these fixtures: `stop-condition-3`, `command-refusal`, the two designer-contract.md abort sites and the phase-state.md unknown `schema_version` site | The results are `step_needs_intervention`, `gate_fail_closed`, `unmapped_stop`, `unmapped_stop` and `unmapped_stop`. The untabled sites are absent from the live keys. A resolver that ignores precedence is caught on `stop-condition-3` | Unit |
| TS-5 | Scope matcher over the appended coverage text and `## Consumer constraints` | The catch-all excludes wait turns (stop condition 5, launch and wake turns), normal completion, `phase_done`, the infra auto-resume and the 64 KiB outcome. The 64 KiB paragraph still says no reason code and no coverage row. Forged text without the exclusions is rejected | Unit |
| TS-6 | Meaning-cell matcher and detail-rule matcher | The `unmapped_stop` Meaning says no other row names the stop, and contains neither "unknown" nor "undetermined". The catch-all `detail` names the stop site and the concrete cause, and `resume_conditions` stays mandatory. Forged "unknown cause" wording is rejected | Unit |
| TS-7 | Extract the `no-step` bullet's keys and run the condition-wording matcher | The extracted keys equal {`stop-condition-6`, `step-a-abort`, `step-c-abort`, `stop-condition-4`} and are a subset of the coverage keys. The executed-step / outside-Step-B condition governs, and the stop-condition-4 and Step A.5 cases are stated. The real pre-change bullet is rejected | Unit |
| TS-8 | Route-based precedence matcher over the Precedence rule paragraph | The route-based wording replaces "no phase-specific row covers". `implement-second-failure`, `verify-rework-cap` and `docs-commit-conflict` are named, and `no-work-required` is not. A re-entry stop on a `failed` left by an earlier run binds to `step_needs_intervention`. implement-phase.md's pinned sentence is present and unchanged. The real pre-change paragraph is rejected | Unit |
| TS-9 | Docs-commit-conflict status matcher | The no-status statement for `docs-commit-conflict` is present. "all three leave a step's status `failed`" is absent. The real pre-change paragraph is rejected | Unit |
| TS-10 | Whole-file literal guards with the widened absence tuples in `test_batch_stop_contract_skill_wiring.py` (14 members) and `test_develop_once_option.py` | `unmapped_stop` is absent from `skills/develop/SKILL.md`, `references/batch-mode.md` and `references/implement-phase.md`. A synthetic excerpt naming it is flagged. `git diff {implement base_commit}..HEAD` shows no change to those three files | Unit |
| TS-11 | Existing context-budget exception test | Exactly one documented code, `context_budget_reached`, has no coverage row | Unit |
| TS-12 | Check the `gate_fail_closed` Meaning cell and the `command-refusal` row | The Meaning names the refusal-pattern hard fail. It keeps the `references/question-resolution.md` citation and the "both modes" and "interactive" wording, without `category: security`, `category: license` or `reversible: false`. The row binds `command-refusal` to `gate_fail_closed` with Source `references/batch-policies.yaml`. The real pre-change cell is rejected | Unit |
| TS-13 | Section stability of `batch-terminal-line.md` | The existing byte-identical tests for `## Result format` and `## Escaping` pass. The nine level-2 headings keep their order, with `Stop reason codes` immediately followed by `Stop point coverage`. `git diff {implement base_commit}..HEAD -- em-workflow/references/batch-terminal-line.md` has no hunk inside `## Result format`, `## Escaping` or `## Responsibility boundary` | Unit + diff check |
| TS-14 | Full suite | `python3 -m unittest discover -s tests` exits 0. Every new test module imports the standard library only and imports no other test module | Integration |
| TS-15 | Plugin invariants | `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0. `unmapped_stop`, `unmapped-terminating-stop` and `command-refusal` contain no dot | Integration |
| TS-16 | Version bump test module plus a registry read | `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry of `.claude-plugin/marketplace.json` both read `0.2.1`. The baseline matcher (strictly greater than 0.2.0) and the equality matcher pass, and their forged samples are rejected | Unit |

SPEC.md edge cases:

- The re-entry stop on a prior run's `failed` is covered by TS-8.
- The stop-condition-4 stop with no step executed is covered by TS-7.
- The 64 KiB no-result outcome is covered by TS-5.

## Code Quality Verification

- Format: not applicable, because `project.components.main.format_command` is
  empty.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  (TS-15).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The reason-code table contains `unmapped_stop` (`stopped`), and the coverage table contains `unmapped-terminating-stop` → `unmapped_stop`. The fallback binds every unnamed terminating stop, including the four stops the source task names, to exactly one code | TS-1, TS-2, TS-3, TS-4, plus manual trace M-2 |
| AC2 | Every other row, including `stop-condition-N` and the refusal row, takes precedence over the catch-all, which applies last | TS-3, TS-4 |
| AC3 | The catch-all's meaning is "no other row names" and never "unknown cause". The scope exclusions are stated, and the 64 KiB statement is unchanged | TS-5, TS-6 |
| AC4 | A catch-all `detail` names the stop site and the concrete cause, and `resume_conditions` stays mandatory | TS-6 |
| AC5 | A coverage row maps the refusal-pattern hard fail to `gate_fail_closed`, with Source `references/batch-policies.yaml` | TS-2, TS-12 |
| AC6 | The `no-step` rule is condition-based and yields a `step` value for stop-condition-4 and Step A.5 stops | TS-7 |
| AC7 | The precedence text says docs-commit-conflict writes no status | TS-9 |
| AC8 | The stop-condition-3 restriction is route-based. A re-entry stop on a prior run's `failed` binds to `step_needs_intervention`, and implement-phase.md's pinned sentence stays true | TS-8 |
| AC9 | The pins are synced, and the new tests prove both that existing rows win and that the catch-all applies to untabled stops, each with a negative proof and a non-vacuity guard | TS-1 to TS-10 |
| AC10 | The suite passes and the invariants stay green | TS-14, TS-15 |
| AC11 | plugin.json and marketplace.json both carry 0.2.1 for em-workflow | TS-16 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-6 |
| FR2 | task0001 | TS-3, TS-4 |
| FR3 | task0001 | TS-5, TS-11 |
| FR4 | task0001 | TS-6 |
| FR5 | task0001 | TS-2, TS-3, TS-4, TS-12 |
| FR6 | task0002 | TS-7 |
| FR7 | task0002 | TS-8, TS-9 |
| FR8 | task0002 | TS-8 |
| FR9 | task0001, task0002, task0003 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10 |
| FR10 | task0004 | TS-16 |
| FR11 | task0003 | TS-10 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-14 |
| NFR2 | task0001, task0002 | TS-15 |
| NFR3 | task0001, task0002 | TS-13 |
| NFR4 | task0001, task0002, task0004 | TS-1, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-12, TS-16 |

## Manual Testing (E2E Not Possible)

- [ ] M-1: Read the merged `## Field values` `step` bullet and the whole
  `## Stop point coverage` section end to end. Confirm that:
  - the Precedence rule and Fallback rule paragraphs read as one coherent rule
    set;
  - the fallback refers to the Precedence rule by its label;
  - no sentence contradicts another.
- [ ] M-2: Trace each stop the source task names to exactly one code and one
  `step` value, using the source documents together with the coverage table
  and the fallback rule:
  - designer-contract.md's `kind: none` × token-present abort, including the
    batch abort on truncated candidate discovery;
  - its `em_workflow` × `tokens.html`-only abort;
  - phase-state.md's unknown `schema_version` abort;
  - the `create-spec.command-approval` refusal-pattern hard fail.
- [ ] M-3: Search every file under `em-workflow/` for the literal
  `unmapped_stop`. It occurs only in `references/batch-terminal-line.md`.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Contract unit tests | 13 (TS-1 to TS-13) | 13 | 0 | 0 |
| Integration (suite, invariants) | 2 (TS-14, TS-15) | 2 | 0 | 0 |
| Version | 1 (TS-16) | 1 | 0 | 0 |
| Manual reading and tracing | 3 (M-1 to M-3) | 0 | 0 | 3 |
