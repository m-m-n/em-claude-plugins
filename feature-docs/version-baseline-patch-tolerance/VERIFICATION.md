# Verification Document: version-baseline-patch-tolerance

## Overview
**Feature**: version-baseline-patch-tolerance / **SPEC.md**: `feature-docs/version-baseline-patch-tolerance/SPEC.md` / **IMPLEMENTATION.md**: not produced (tier `reduced`, one task)

Notation: a baseline is (M, m, p), its major, minor and patch as integers; candidates are written relative to it.

## Build Verification
- Command: none (`build_command` of component `main` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Module-only command: `python3 -m unittest discover -s tests -p test_review_perspective_model_effort_version_bump.py`
- Expected: the module-only command exits 0; the full command reports no failure and no error for `test_review_perspective_model_effort_version_bump`.
- Coverage target: none set (no coverage tool is configured)

### Test Scenarios from SPEC.md
TS-1 to TS-7 are SPEC.md's Test Scenarios. TS-8 to TS-10 are derived from SPEC.md's Success Criteria AC6, AC7 and AC8.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Fake baseline; candidate (M, m + 1, 0) | Accepted (`test_accepts_the_correct_bump`) | Unit |
| TS-2 | Fake baseline; candidate (M, m + 1, a nonzero patch) | Accepted (the test that replaces `test_rejects_minor_bump_with_nonzero_patch`) | Unit |
| TS-3 | Fake baseline; candidate (M, m + 2, 0) | Accepted (the test that replaces `test_rejects_minor_raised_by_two`) | Unit |
| TS-4 | Fake baseline; a patch-only bump, an unchanged version, a lowered minor | Each rejected with AssertionError (`test_rejects_patch_only_bump`, `test_rejects_unchanged_version`, `test_rejects_lowered_minor`) | Unit |
| TS-5 | Fake baseline; a different major with minor m + 1 | Rejected (`test_rejects_major_change`) | Unit |
| TS-6 | String-ordering traps | A numerical bump that sorts lower as a string is accepted; a numerically lower value that sorts higher as a string is rejected (`test_string_ordering_trap_rejects_a_numerically_lower_version` and its accepting counterpart, both unchanged) | Unit |
| TS-7 | The four current-version tests against the actual manifests and marketplace entries | `test_version_is_a_minor_bump_over_baseline` (in `TestEmWorkflowManifest` and in `TestEmReviewManifest`), `test_em_workflow_entry_version_is_a_minor_bump_over_baseline` and `test_em_review_entry_version_is_a_minor_bump_over_baseline` pass | Integration |
| TS-8 | Module docstring and `_assert_minor_bump_over_baseline` docstring | Both state the lower-bound rule; the matcher -> negative-proof list names only tests that exist in the module, the two replacement tests included, and neither removed test name | Inspection |
| TS-9 | Diff between the `implement` step's `base_commit` and the integration HEAD | No change to `tests/test_destructive_guard_args_json.py`; no change to the version field of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | Inspection (git diff) |
| TS-10 | Imports and referenced test names | `test_only_standard_library_imports` passes; every test name of this module referenced by `test-docs/review-perspective-model-effort/task0006.tests.yaml` exists in the module | Unit + Inspection |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The four current-version tests pass against the current repository files | TS-7: module-only command; the four tests are reported ok |
| AC2 | `test_rejects_patch_only_bump`, `test_rejects_unchanged_version`, `test_rejects_major_change`, `test_rejects_lowered_minor`, `test_string_ordering_trap_rejects_a_numerically_lower_version` and `test_entry_without_a_version_fails_the_bump_check` keep passing and still raise AssertionError on their fake input | TS-4, TS-5, TS-6: module-only command; each test is reported ok |
| AC3 | A test accepting a minor bump with a nonzero patch exists; `test_rejects_minor_bump_with_nonzero_patch` does not | TS-2; the removed name is absent from the module |
| AC4 | A test accepting a minor raised by two exists; `test_rejects_minor_raised_by_two` does not | TS-3; the removed name is absent from the module |
| AC5 | A different major numerically above the bound is rejected | TS-5 |
| AC6 | The docstrings state the lower-bound rule; the negative-proof list names only existing tests | TS-8 |
| AC7 | The diff has no change to `tests/test_destructive_guard_args_json.py` and no version-field change | TS-9 |
| AC8 | The full test command passes for this module; every referenced test name exists | Test Verification full command; TS-10 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-7 |
| FR2 | task0001 | TS-4, TS-5 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-8 |
| FR6 | task0001 | TS-9 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-9 |
| NFR4 | task0001 | TS-7, TS-10 |

## Manual Testing (E2E Not Possible)
- [ ] TS-8: read the module docstring and the helper docstring; confirm the rule and that each test in the negative-proof list exists in the module.
- [ ] TS-10: compare the test names of this module referenced by `test-docs/review-perspective-model-effort/task0006.tests.yaml` with the test methods of the module; none is missing.

## Performance / Security Verification (if applicable)
- Not applicable: THREAT-MODEL.md's verdict is `no-trust-boundary`, and SPEC.md has no performance requirement.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Integration scenarios (TS-7) | 1 | 1 | 0 | 0 |
| Inspection scenarios (TS-8 to TS-10) | 3 | 1 | 0 | 2 |
| Success criteria (AC1 to AC8) | 8 | 6 | 0 | 2 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
