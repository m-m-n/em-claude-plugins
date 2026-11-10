# Verification Document: muse-guard-deny-recovery

## Overview
**Feature**: muse-guard-deny-recovery / **SPEC.md**: `feature-docs/muse-guard-deny-recovery/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/muse-guard-deny-recovery/IMPLEMENTATION.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused run: `python3 -m unittest tests.test_muse_guard tests.test_codex_reviewer_skip_handling tests.test_reviewer_roles_protocol tests.test_review_phase_llm_led tests.test_review_phase_shard_dispatch tests.test_em_review_r2b_contributor_consent`
- Coverage target: not measured (document pins and a hook string constant)

### Test Scenarios from SPEC.md
TS-1 to TS-8 come from SPEC.md; TS-9 to TS-13 are added by this plan for the success criteria and non-functional requirements SPEC.md lists without a scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run each muse_guard.py copy as a subprocess with a `codex exec -m muse-spark-contributor` payload in a repository without recorded consent | Deny, four-field payload, one-line `additionalContext` holding `contributor_consent_missing`, both branches, `muse-spark`, the copy's own consent skill name and the `--record` prohibition, without the old switching instruction (AC-6, FR6) | Unit (`tests/test_muse_guard.py`) |
| TS-2 | Existing `TestBothCopiesShape` one-line diff check | Passes: same line count, only the `PLUGIN_SLUG` line differs (AC-7, FR7) | Unit (`tests/test_muse_guard.py`) |
| TS-3 | Skip Semantics retryable-group check in `tests/test_codex_reviewer_skip_handling.py` with the updated value sets and count words | Passes on both protocols; forged texts with the old count word or without the new value are rejected (AC-1, AC-2, FR1, FR2) | Unit |
| TS-4 | Updated skip_reason, retryable count and non-retryable sentence pins in `tests/test_reviewer_roles_protocol.py` | Passes (AC-1, FR1) | Unit |
| TS-5 | `routing_table_ok` and the `\| the next entry` counts | Accepts exactly the five-row table; rejects the four-row table and a changed old row; count is 5 in both `tests/test_review_phase_llm_led.py` and `tests/test_review_phase_shard_dispatch.py` (AC-3, FR3) | Unit |
| TS-6 | Precedence statement pin and unchanged harness-level sentence pin | Passes; a forged text without the precedence statement is rejected (AC-4, FR4) | Unit (`tests/test_review_phase_shard_dispatch.py`) |
| TS-7 | README hop paragraph pins in `tests/test_review_phase_shard_dispatch.py` | Passes (AC-8, FR8) | Unit |
| TS-8 | em-review R2b table pin | Four rows including the new row; forged texts rejected (AC-5, FR5) | Unit (`tests/test_em_review_r2b_contributor_consent.py`) |
| TS-9 | Full suite run (plan-added) | `python3 -m unittest discover -s tests` exits 0 (AC-10, FR9, NFR5) | Unit |
| TS-10 | Version fields untouched (plan-added) | `git diff` from workflow.yaml `implement.base_commit` to the integration head shows no change to the `version` field of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` (AC-9, NFR2) | Manual command check |
| TS-11 | Forbidden words absent (plan-added) | The em-review scan for `shard` / `dispatch cap` in `tests/test_codex_reviewer_skip_handling.py` and the framing-phrase checks in `tests/test_reviewer_roles_protocol.py` pass (NFR3) | Unit |
| TS-12 | Existing R2b pins verbatim (plan-added) | `tests/test_review_phase_llm_led.py`, `tests/test_review_phase_shard_dispatch.py`, `tests/test_sca_axis_review_phase_r0_r3.py`, `tests/test_threat_model_review_phase.py` and `tests/test_contributor_tier_criteria.py` pass (NFR4) | Unit |
| TS-13 | Hook decision behavior unchanged (plan-added) | Every pre-existing classification, no-decision, store, CLI and source-hygiene test of `tests/test_muse_guard.py` passes unmodified, and the diff of both copies touches only DENY_CONTEXT and its comment (NFR1) | Unit + diff review |

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | em-workflow Skip Semantics lists the value and the five-value statements | TS-3, TS-4 |
| AC-2 | em-review Skip Semantics lists the value and the four-value statements | TS-3 |
| AC-3 | em-workflow R2b table has five rows and the note's three points | TS-5 |
| AC-4 | em-workflow precedence over the harness-level path | TS-6 |
| AC-5 | em-review R2b table has four rows | TS-8 |
| AC-6 | DENY_CONTEXT content of both copies | TS-1 |
| AC-7 | Copies differ only in `PLUGIN_SLUG` | TS-2 |
| AC-8 | README hop paragraph | TS-7 |
| AC-9 | No `version` change | TS-10 |
| AC-10 | Full suite passes | TS-9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-3, TS-4 |
| FR2 | task0002 | TS-3 |
| FR3 | task0003 | TS-5 |
| FR4 | task0003 | TS-6 |
| FR5 | task0004 | TS-8 |
| FR6 | task0001 | TS-1 |
| FR7 | task0001 | TS-2 |
| FR8 | task0003 | TS-7 |
| FR9 | task0001, task0002, task0003, task0004 | TS-9 |
| NFR1 | task0001 | TS-1, TS-13 |
| NFR2 | task0001, task0002, task0003, task0004 | TS-10 |
| NFR3 | task0001, task0002, task0004 | TS-11 |
| NFR4 | task0003, task0004 | TS-12 |
| NFR5 | task0001, task0002, task0003, task0004 | TS-9 |

## Manual Testing (E2E Not Possible)
- [ ] Read the rewritten DENY_CONTEXT of both copies as a denied agent would: one line, natural Japanese, the reviewer branch and the non-reviewer branch cannot be confused, and it agrees with the Skip Semantics bullet and the R2b note.

## Performance / Security Verification (if applicable)
- TM-1: DENY_CONTEXT keeps the user-only consent clause and the `--record` prohibition, has the two branches and no entry-switching instruction; the Skip Semantics bullet forbids recording or re-judging consent — checked by TS-1 and by reading both Skip Semantics bullets.
- TM-2: DENY_CONTEXT embeds only `PLUGIN_SLUG` — checked by the existing no-interpolation test in `tests/test_muse_guard.py` (command-text marker, repository path and store path absent from every output field) and by reading the constant.
- TM-3: hook decision behavior unchanged — checked by TS-13 and the existing no-`ask` / no-`allow` source-hygiene tests.
- TM-4: the new value advances only to the next chain entry within the 2-hop budget, never re-dispatches the denied entry as plain `muse-spark`, falls back as before when the chain is exhausted, and a result without a valid skip object keeps the harness-level path — checked by TS-5, TS-6 and TS-8 and by reading both Phase R2b sections.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 13 | 11 | 0 | 2 (TS-10 command check; TS-13 diff review part) |
| Success criteria | 10 | 9 | 0 | 1 (AC-9) |
| Requirements coverage | 14 | 14 | 0 | 0 |
| Security (TM) | 4 | 4 | 0 | 4 (reading part of each item) |
| Manual reading | 1 | 0 | 0 | 1 |
