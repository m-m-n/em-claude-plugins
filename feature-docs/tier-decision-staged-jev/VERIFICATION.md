# Verification Document: tier-decision-staged-jev

## Overview

**Feature**: tier-decision-staged-jev / **SPEC.md**: `feature-docs/tier-decision-staged-jev/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/tier-decision-staged-jev/IMPLEMENTATION.md`

## Build Verification

- Command: none configured (`project.components.main.build_command` is empty).
  Syntax check of the evaluator: `python3 -m py_compile em-workflow/scripts/decide-tier.py`
- Expected: exit code 0, no errors

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0; no failures and no errors. The only accepted skips
  are the copy checks against the jev / typesafe-ai skill documents when
  those documents are absent, and each such skip states its reason.
- Coverage target: not measured (standard-library-only test constraint,
  NFR3); coverage is tracked through the scenario-to-requirement mapping
  below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Triage case: final probabilities 0.09 / 0.90 / 0.01 / 0.00 for buckets 0-3, both tools usable | tier reduced, decided_by threshold_rows:reduced | Unit |
| TS-2 | Final probabilities 0.37 / 0.59 / 0.03 / 0.01 (formerly forced to full) | tier reduced | Unit |
| TS-3 | Final probabilities 0.85 / 0.10 / 0.05 / 0.00, once with expectation_clear 0.1 and once without expectation_clear | tier minimal in both cases | Unit |
| TS-4 | Final probabilities 0.50 / 0.30 / 0.15 / 0.05; boundary 0.80 / 0.10 / 0.05 / 0.05; boundary 0.50 / 0.35 / 0.10 / 0.05 | full; minimal; reduced | Unit |
| TS-5 | Final score missing bucket "3"; bucket 2 is NaN; bucket 1 is 1.2; bucket sum 1.10 | tier full in each case; the reason names the bucket or states the sum; stdout parses as strict JSON; exit code 0 | Unit |
| TS-6 | Legacy two-reading readings payload given to the evaluator; whole-tree scan of em-workflow/ for the string readings_disagree | legacy payload gives tier full as invalid input; the scan finds zero matches (per-task scans cover owned files, the whole-tree scan runs here at verify) | Unit + Integration |
| TS-7 | codex_available false with a final score that would otherwise be minimal | tier full, decided_by fallback_matrix:jev_only_usable (not a threshold row); the rule table's jev_only_usable row action is full | Unit |
| TS-8 | jev_available false, with codex_available true and with codex_available false; jev_exit_codes entries 1, 2 and 75 | tier full, decided_by fallback_matrix:jev_unusable in both cases; each of the three exit codes is classified unusable | Unit |
| TS-9 | SKILL.md Step A tier-decision section, raw-text conformance: call order; final-call input contents including the first result with confidence; bucket descriptions passed to both Jev calls; Jev-unusable handling; step 6 Codex-unavailable handling; no-work-required stop; single-final-score evaluator payload; tier.yaml schema_version 2 recording and resume reuse; no decimal threshold literal, no P(0), no expectation_clear; no gate_id and no AskUserQuestion | every matcher passes on the real section and fails on its forged violating sample; the section locator finds a non-empty section | Integration |
| TS-10 | tier-rules.yaml conformance: four bucket descriptions; rule addition plus test addition in bucket 1; question_set comment; seven Codex fact fields with vocabularies; pre-existing Codex fields kept; probability_sum_tolerance declared; no long line copied from the jev or typesafe-ai skill documents | all present; no copied line (the copy check is skipped with a stated reason when a document is absent) | Integration |
| TS-11 | Record and projections: phase-state.md schema_version 2 definition and version 1 resume reuse; create-spec-phase.md mapping table; workflow-schema.md tier section; SKILL.md retrospect signals.tier_decision block | every schema_version 2 member defined; the table covers every member; tier_decision keeps exactly four sub-fields; rationale never mentions agreement between readings; no threshold restated in the workflow-schema.md tier section | Integration |
| TS-12 | Plugin version check | the em-workflow versions in plugin.json and marketplace.json are equal and numerically greater than 0.2.9 | Unit |
| TS-13 | Rule-table dependence: threshold rows and tolerance read from tier-rules.yaml; a rules table lacking the tolerance or a lower bound; no row on confidence or expectation_clear | rows are minimal, reduced, full in that order with bounds from the table; a missing member gives full with a reason naming it; no confidence-only threshold | Unit |
| TS-14 | Review documents untouched | no change to em-workflow/references/review-phase.md or em-workflow/references/review-rules.yaml between the implement base commit and HEAD; tests/test_tier_spec_perspective.py passes unmodified | Integration |
| TS-15 | Full suite | the test command above exits 0 using only standard-library unittest | Integration |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured; the syntax check under Build Verification applies
- Whole-tree string scan (TS-6): `grep -rn readings_disagree em-workflow/` prints nothing
- Review-document diff (TS-14): `git diff --stat {implement.base_commit}..HEAD -- em-workflow/references/review-phase.md em-workflow/references/review-rules.yaml` prints nothing

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | SKILL.md describes Jev (description only), then the Codex survey, then Jev (description plus both JSON results), and the final call receives the first result including confidence (FR1, FR2) | TS-9 |
| AC2 | The evaluator decides from a valid four-bucket final score alone: 0.09 / 0.90 / 0.01 / 0.00 is reduced; bucket 0 at 0.85 is minimal regardless of expectation_clear; 0.50 / 0.30 is full (FR3, FR4) | TS-1, TS-3, TS-4 |
| AC3 | A missing bucket, a non-finite or out-of-range bucket, or an out-of-tolerance sum gives full with the bucket or sum in the reason (FR3) | TS-5 |
| AC4 | The string readings_disagree appears nowhere under em-workflow/, and no rule forces full on disagreement between readings (FR5) | TS-6 |
| AC5 | codex_output_schema keeps its fields and adds seven fact fields, each with a value vocabulary (FR7) | TS-10 |
| AC6 | phase-state.md defines tier.yaml schema_version 2; bases holds the first and final Jev score objects; pre_survey_estimate holds the Codex JSON (FR10) | TS-11 |
| AC7 | With codex_available false the evaluator returns full even for a would-be minimal score; SKILL.md step 6 and fallback_matrix describe the same treatment (FR8) | TS-7, TS-9 |
| AC8 | question_set defines bucket 0-3 descriptions with rule addition plus test addition in bucket 1 (FR6) | TS-10 |
| AC9 | The full suite passes; plugin.json and marketplace.json carry the same raised em-workflow version (NFR1, NFR2, NFR3, NFR5) | TS-15, TS-12, TS-13 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0003 | TS-9 |
| FR2 | task0003 | TS-9 |
| FR3 | task0001 | TS-5 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR5 | task0001, task0003, task0004 | TS-6, TS-9, TS-11 |
| FR6 | task0002, task0003 | TS-10, TS-9 |
| FR7 | task0002 | TS-10 |
| FR8 | task0001, task0003 | TS-7, TS-9 |
| FR9 | task0001, task0003 | TS-8, TS-9 |
| FR10 | task0003, task0004 | TS-11, TS-9 |
| FR11 | task0004 | TS-11 |
| FR12 | task0003 | TS-9 |
| NFR1 | task0001 | TS-5, TS-13 |
| NFR2 | task0001, task0003, task0004 | TS-9, TS-11, TS-13 |
| NFR3 | task0001, task0002, task0003, task0004, task0005 | TS-15 |
| NFR4 | task0003 | TS-9 |
| NFR5 | task0005 | TS-12 |
| NFR6 | task0004 | TS-14 |

## Manual Testing (E2E Not Possible)

The staged calls need the real Jev skill and Codex, so no automated
end-to-end run exists.

- [ ] M-1: In a scratch repository, start `/em-workflow:develop` with a task
      description for a rule addition plus a test addition. Confirm the call
      order Jev (description only), Codex read-only pre-survey, Jev (final);
      confirm the final call's input contains the first Jev JSON result
      (including confidence) and the Codex JSON; confirm
      `phase-state/tier.yaml` is schema_version 2 with both `bases` entries
      and `pre_survey_estimate`. Confirm the Jev result carries its bucket
      map under `probabilities` (IMPLEMENTATION.md SC-2).
- [ ] M-2: Where the Codex pre-survey can be made unusable (for example a run
      in which it cannot start), confirm the final Jev call is not made, the
      tier is full, and tier.yaml has no `pre_survey_estimate` and carries a
      `fallback_reason`.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build (syntax check) | 1 | 1 | 0 | 0 |
| Unit scenarios (TS-1 to TS-8, TS-12, TS-13) | 10 | 10 | 0 | 0 |
| Integration scenarios (TS-6 whole-tree scan, TS-9, TS-10, TS-11, TS-14, TS-15) | 6 | 6 | 0 | 0 |
| Staged run against real tools | 2 | 0 | 0 | 2 |
