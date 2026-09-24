# Verification Document: repo-suite-pinned-test-drift

## Overview

**Feature**: repo-suite-pinned-test-drift / **SPEC.md**: `feature-docs/repo-suite-pinned-test-drift/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/repo-suite-pinned-test-drift/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests` (from the repository root of the integration worktree)
- Expected: exit code 0, zero failures, zero errors
- Coverage target: not applicable (no coverage tooling is configured)

### Test Scenarios from SPEC.md

TS-1 to TS-5 are SPEC TS1 to TS5. TS-6 to TS-9 are derived from NFR1 to NFR4, which have no SPEC scenario of their own.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC1, AC2) Run the full repository suite in the integration worktree after the em-workflow version bump. | Exit code 0 with no failures. The 16 tests that failed at the base all pass: test_abort_terminal_commit_precedence (2, under the names given in FR6), test_batch_structured_result_output_version_bump (1), test_codex_wrapper_fallback_removal_version_bump (2), test_develop_once_option (1), test_muse_consent_no_new_questions (1), test_muse_consent_version_bump (1), test_reviewers_primary_chains (4), test_step_c_verify_failed_default (2), test_stop_reason_coverage_version_bump (2, under the names given in FR7). | Integration |
| TS-2 | (AC3) The FR6–FR9 version matchers are exercised with forged data by hermetic tests in the suite. Each matcher gets the cases of its applicable columns in the IMPLEMENTATION.md D2 table. | Every applicable case exists and passes: a forged higher version (99.0.0, identical in both registries where agreement applies) is accepted; a version below the floor is rejected; a malformed version is rejected; disagreeing registries are rejected. | Unit |
| TS-3 | (AC4) test_muse_consent_no_new_questions's test_no_develop_or_review_document_exceeds_its_pinned_budget. | The test passes. `em-workflow/skills/develop/SKILL.md` has at most 7 occurrences of AskUserQuestion. `BASELINE_COUNTS` is unchanged from the base. | Unit |
| TS-4 | (AC5) The existing version-parity tests, including `tests/test_plugin_version_parity.py`, and the manifest values. | The parity tests pass. em-workflow reads 0.2.4 in `em-workflow/.claude-plugin/plugin.json` and in its `.claude-plugin/marketplace.json` entry. em-review reads 0.5.13 in both of its places. | Integration |
| TS-5 | (AC6) Diff of the integration branch against the base commit. | Under `em-workflow/`, only two things change: the one phrase on the `--pr` item of 引数処理 in SKILL.md (near line 106), and the `version` value in `plugin.json`. The SKILL.md argument-hint line, the Step C wording, the `review-rules.yaml` selection rules and the `plugin.json` description are unchanged. | Manual (diff) |
| TS-6 | (NFR1) Import statements of every test module modified by this feature. | Every imported top-level module is part of the Python standard library. | Static check |
| TS-7 | (NFR2) The version checks changed under FR6–FR9. | No check compares with a current version literal of any plugin (0.2.3, 0.2.4, 0.5.13). Floors are used only through the lower-bound comparison. | Static check |
| TS-8 | (NFR3) The non-version matchers changed under FR1–FR3, FR5 and FR10 are exercised with forged data. | Each changed matcher has at least one hermetic negative-proof test that rejects forged data. The wrapped-phrase matchers (FR3, FR10) also accept a wrapped occurrence and reject an altered phrase. | Unit |
| TS-9 | (NFR4) Diff of `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` against the base commit. | The only changes are the em-workflow version values. No other field, key order or whitespace changes. | Manual (diff) |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured. TS-6 and TS-7 are the static checks for this feature.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The full suite exits 0 in the integration worktree after the version bump | TS-1 |
| AC2 | The 16 observed failures all pass (FR6 / FR7 tests under their new names) | TS-1 |
| AC3 | The FR6–FR9 matchers accept a forged higher version and reject below-floor, malformed and disagreeing versions | TS-2 |
| AC4 | SKILL.md has at most 7 AskUserQuestion occurrences and `BASELINE_COUNTS` is unchanged | TS-3 |
| AC5 | em-workflow is 0.2.4 in both places, and em-review is 0.5.13 in both | TS-4 |
| AC6 | argument-hint, Step C wording, review-rules.yaml selection rules and plugin.json description are unchanged (FR4's one phrase excepted) | TS-5 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-5, TS-8 |
| FR2 | task0002 | TS-1, TS-5, TS-8 |
| FR3 | task0002 | TS-1, TS-5, TS-8 |
| FR4 | task0001 | TS-3, TS-5 |
| FR5 | task0004 | TS-1, TS-8 |
| FR6 | task0003 | TS-1, TS-2 |
| FR7 | task0003 | TS-1, TS-2 |
| FR8 | task0004 | TS-1, TS-2 |
| FR9 | task0004 | TS-1, TS-2 |
| FR10 | task0005 | TS-1, TS-5, TS-8 |
| FR11 | task0001 | TS-4, TS-9 |
| NFR1 | task0002, task0003, task0004, task0005 | TS-6 |
| NFR2 | task0003, task0004 | TS-2, TS-7 |
| NFR3 | task0002, task0003, task0004, task0005 | TS-2, TS-8 |
| NFR4 | task0001 | TS-5, TS-9 |

## Manual Testing (E2E Not Possible)

- [ ] TS-5: review the diff of `em-workflow/` against the base commit.
- [ ] TS-9: review the diff of both manifest files against the base commit.
- [ ] TS-6: inspect the imports of the modified test modules.
- [ ] TS-7: inspect the changed version checks for current-version literals.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 9 | 4 (TS-1, TS-2, TS-3, TS-8) | 0 | 5 (TS-4 value check, TS-5, TS-6, TS-7, TS-9) |
| Success criteria | 6 | 4 (AC1–AC4) | 0 | 2 (AC5 value check, AC6) |
