# Verification Document: batch-once-refire-dedup

## Overview

**Feature**: batch-once-refire-dedup / **SPEC.md**: `feature-docs/batch-once-refire-dedup/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/batch-once-refire-dedup/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the change
  is Markdown documents, a Python test module and JSON version fields).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, every test passes (existing and new).
- Coverage target: not applicable (text-contract tests; completeness is judged
  by the scenario table below, not by line coverage).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Extract the "Step A feature resolution" row of `em-workflow/references/batch-mode.md`'s `## Non-packet gates` table and check it for the re-launch contract | The row contains "`feature` value as the path argument" and "does not pass the task description again" | Unit |
| TS2 | Check the same row for the existing Step A rules, and SKILL.md's existing Step A wording | The row contains "Explicit feature-name/path argument wins", "No path argument → always a new feature", "Existing branches are never enumerated, and a feature is never guessed from them", "resuming requires the explicit feature name"; the existing SKILL.md Step A checks in `tests/test_review_implement_develop_lock_contracts.py` pass; the new pin on SKILL.md's 「パス引数なし」 item passes; `em-workflow/skills/develop/SKILL.md` has no diff between `workflow.implement.base_commit` and the integration HEAD | Unit + Inspection |
| TS3 | Extract the `state` bullet under `## Field values` of `em-workflow/references/batch-terminal-line.md` | It contains "re-launches the same feature", "`feature` value as the path argument" and "does not pass the task description again" | Unit |
| TS4 | Feed each TS1–TS3 matcher (and the 「パス引数なし」 pin) forged text lacking one required phrase, lacking the scope, or carrying the phrases only outside the scope | Every such case fails the matcher (non-vacuity); the new module's standard-library self-check passes | Unit |
| TS5 | Run `python3 -m unittest discover -s tests` | All existing tests (including the SC5 / `state`-literal guards in `tests/test_develop_once_option.py` and all of `tests/test_batch_stop_contract.py`) and the new tests pass | Integration |
| TS6 | Compare the em-workflow version in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` at `workflow.implement.base_commit` and at the integration HEAD | Both read the same value at HEAD, one patch step above their value at the base commit (0.2.12 → 0.2.13); the em-review entry's version is unchanged | Inspection |
| TS7 | Check format ownership | The batch-mode.md Step A row names `references/batch-terminal-line.md` as the value's owner (new module); `TestBatchModePointerSc5Compliance` passes; batch-terminal-line.md's `## Result format`, `## Escaping` and `## Field values` bullet-order tests in `tests/test_batch_stop_contract.py` pass; the diff of batch-mode.md adds no key list, value domain or escaping rule | Unit + Inspection |

TS1–TS5 come from SPEC.md; TS6 and TS7 are added here to give FR5 and NFR4 a
verifying check.

### Edge Cases (existing rules, confirmed unchanged)

- A re-launch that passes both a path argument and a task description: the
  path argument wins — the "Explicit feature-name/path argument wins" clause
  is still in the row (TS2).
- A `stopped` result with an empty `feature`: outside the re-launch contract —
  the added wording in batch-terminal-line.md sits in the phase-boundary
  sentence of the `state` bullet only (TS3, manual reading below).
- Re-launch after the retrospect boundary, invalid feature names, and a
  removed integration worktree: governed by unchanged SKILL.md rules (TS2).

## Code Quality Verification

- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Standard-library-only imports: the new module's self-check (TS4).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | batch-mode.md Step A row states the re-launch contract | TS1 |
| AC2 | batch-mode.md Step A row's existing rules and SKILL.md's existing wording remain | TS2 |
| AC3 | batch-terminal-line.md `phase_done` description keeps "re-launches the same feature" and states the contract | TS3 |
| AC4 | FR4 tests exist, have negative proofs, and the full suite passes | TS4, TS5 |
| AC5 | em-workflow version bumped by one patch step in both manifests | TS6 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS4 |
| FR2 | task0001 | TS2, TS5 |
| FR3 | task0001 | TS3, TS4 |
| FR4 | task0001 | TS1, TS2, TS3, TS4, TS5 |
| FR5 | task0001 | TS6 |
| NFR1 | task0001 | TS5 |
| NFR2 | task0001 | TS4, TS5 |
| NFR3 | task0001 | TS5 |
| NFR4 | task0001 | TS7 |

## Manual Testing (E2E Not Possible)

- [ ] Read the edited batch-mode.md Step A row as a whole: the appended
  sentence reads as the develop-side usage of the `feature` value only and
  does not restate the result format.
- [ ] Read the edited batch-terminal-line.md `state` bullet as a whole: the
  re-launch contract is attached to the `--once` phase-boundary sentence and
  does not extend to `stopped` results.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 7 (TS1–TS7) | 7 (TS2, TS6 and TS7 include a git-diff / file inspection step) | 0 | 0 |
| Code quality | 1 | 1 | 0 | 0 |
| Manual reading | 2 | 0 | 0 | 2 |
