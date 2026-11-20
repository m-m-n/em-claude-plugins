# Verification Document: review-perspective-model-effort

## Overview
**Feature**: review-perspective-model-effort / **SPEC.md**: `feature-docs/review-perspective-model-effort/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/review-perspective-model-effort/IMPLEMENTATION.md`

## Build Verification
- Command: none. The `main` component has an empty build command.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit 0.
- Also: `python3 -m unittest tests.test_codex_wrapper_model_flag tests.test_reviewers_primary_chains tests.test_contributor_tier_criteria` exits 0 (SPEC.md AC9).
- Coverage target: not measured. Each scenario below maps to named test modules.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Both wrappers, `readonly --effort high` | The argv has the adjacent pair `-c` / `model_reasoning_effort="high"` exactly once and no xhigh pair (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-2 | Both wrappers, readonly and readwrite without `--effort` | Readonly has exactly one xhigh pair; readwrite has no `model_reasoning_effort` element (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-3 | Both wrappers, `readwrite --effort low` | Exactly one low pair (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-4 | em-workflow wrapper, `readonly --litellm M --effort low` | Exactly one low pair, no xhigh pair (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-5 | Both wrappers, `--effort` with no value, and with a quoted, uppercase, space-containing or empty value | Exit 1, no launch recorded (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-6 | `--effort` combined with `-m`, `-C`, `--output-schema`; `--effort` given twice | Each flag pair stays adjacent, the prompt is last; the later value wins (`tests/test_codex_wrapper_model_flag.py`) | Unit |
| TS-7 | Both registries' codex entries | Model and effort match the FR2 table literally; the two files agree per perspective; the entry pattern reads `effort` (`tests/test_codex_wrapper_model_flag.py`) | Integration |
| TS-8 | `EXPECTED_CHAINS` | Codex entries hold model and effort; the entry-shape check requires both (`tests/test_reviewers_primary_chains.py`) | Integration |
| TS-9 | `EM_REVIEW_EXPECTED_CHAINS` | em-review codex entries hold the FR2 values (`tests/test_contributor_tier_criteria.py`) | Integration |
| TS-10 | Pinned usage literals | They hold the new usage with `--effort`; the existing xhigh-default checks pass (`tests/test_codex_hook_wrapper_args.py`, `tests/test_codex_wrapper_single_invocation.py`) | Integration |
| TS-11 | Hash and literal pins of codex-reviewer.md, review-protocol.md and review-phase.md | Refreshed in place with comments; the suite passes (`tests/test_reviewer_roles_protocol.py`, `tests/test_reproduction_reviewer_instructions.py`, `tests/test_tier_record_schema_v2.py`) | Integration |
| TS-12 | `PINNED_CHAINS` | performance / spec / architecture are codex → litellm `muse-spark`, matching the README table (`tests/test_llm_led_review_user_docs.py`) | Integration |

### Test Scenarios added by the plan

These IDs are not in SPEC.md. They make FR6–FR10 and NFR5 test-translatable.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-13 | codex-reviewer Step 5 and review-protocol Inputs, both plugins | Step 5 adds `--effort "<effort>"` before `"$PROMPT"` only when supplied, verbatim; Inputs documents `effort` for the codex reviewer only (`tests/test_codex_reviewer_effort_docs.py`) | Integration |
| TS-14 | review-phase R2 codex bullet, both plugins | An entry's `effort: E` is added to the input block verbatim, with no allow-list check; the litellm bullet adds none (`tests/test_review_phase_effort_docs.py`) | Integration |
| TS-15 | Round-record documents, both plugins | Codex runs given `effort` carry it in R3a and R5 (em-workflow) and in the em-review record; litellm rows never do (`tests/test_review_phase_effort_docs.py`) | Integration |
| TS-16 | Both READMEs | em-review's chain table is codex-first for every non-empty chain; both READMEs state that `effort` takes the model's path to `--effort` (`tests/test_effort_user_docs.py`) | Integration |
| TS-17 | security-review-model SKILL.md | No wrapper-fixed xhigh statement, no "other perspectives write no `model`" statement, no literal xhigh override; effort comes from the security codex entry (`tests/test_effort_user_docs.py`) | Integration |
| TS-18 | Version manifests | em-workflow and em-review each have a minor bump over the base version, and each marketplace entry equals its manifest (`tests/test_review_perspective_model_effort_version_bump.py`) | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Each perspective's codex reviewer calls `codex exec` with the FR2 model and effort; the path is documented | TS-7, TS-8, TS-9 (values); TS-1, TS-3 (wrapper argv); TS-13, TS-14 (documented path); manual path read-through below |
| AC2 | No `--effort`: readonly gets one xhigh pair, readwrite none | TS-2 |
| AC3 | `--effort LEVEL` gives one LEVEL pair and no xhigh, in readonly, readwrite and the em-workflow `--litellm` route | TS-1, TS-3, TS-4 |
| AC4 | Missing or non-matching value: exit 1, no launch, both wrappers | TS-5 |
| AC5 | Codex runs given `effort` carry it in both review-phase records | TS-15 |
| AC6 | README chain tables codex-first, the effort sentence present, `PINNED_CHAINS` matching | TS-12, TS-16 |
| AC7 | No xhigh-fixed or "other perspectives write no `model`" text in the skill | TS-17 |
| AC8 | Minor bumped, plugin.json and marketplace.json equal | TS-18 |
| AC9 | The three named test modules pass | Test Verification "Also" command |
| AC10 | The whole suite passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-7, TS-8 |
| FR2 | task0002 | TS-7, TS-8, TS-9 |
| FR3 | task0001 | TS-1, TS-3, TS-5, TS-6, TS-10 |
| FR4 | task0001 | TS-1, TS-2, TS-3 |
| FR5 | task0001 | TS-4 |
| FR6 | task0003 | TS-11, TS-13 |
| FR7 | task0003, task0004 | TS-11, TS-13, TS-14 |
| FR8 | task0004 | TS-11, TS-15 |
| FR9 | task0005 | TS-12, TS-16 |
| FR10 | task0005 | TS-17 |
| NFR1 | task0001 | TS-2 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-1, TS-3, TS-5 |
| NFR4 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 (stub on `PATH`); every new module imports only the standard library |
| NFR5 | task0006 | TS-18 |
| NFR6 | task0001, task0002, task0003, task0004, task0005 | TS-8, TS-9, TS-10, TS-11, TS-12 |

## Manual Testing (E2E Not Possible)
- [ ] Read the path from end to end, in the merged tree:
      `reviewers.yaml` codex entry → `review-phase.md` R2 codex bullet →
      `review-protocol.md` Inputs `effort` item → `codex-reviewer.md` Step 5 →
      `run_codex_exec.sh` `--effort`. Confirm the documents describe one
      consistent route, in both plugins (SPEC.md AC1).

## Performance / Security Verification
- NFR2: an effort value outside `^[a-z]+$` never reaches a `codex exec`
  launch — TS-5.
- TM-1: the wrapper embeds LEVEL only when it matches `^[a-z]+$`, and
  otherwise exits 1 without launching — checked by TS-5 in both wrappers.
  The rejected values are a double quote, an uppercase letter, a space, a
  backslash and the empty string; each run must exit 1 with an empty
  launch log.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit | TS-1 to TS-6, TS-18 | 7 | 0 | 0 |
| Integration | TS-7 to TS-17 | 11 | 0 | 0 |
| Success criteria | AC1 to AC10 | 10 | 0 | 1 (AC1 path read-through) |
| Security | NFR2, TM-1 | 2 | 0 | 0 |
| Full suite | `python3 -m unittest discover -s tests` | 1 | 0 | 0 |
