# Verification Document: exit4-version-baseline-refresh

## Overview
**Feature**: exit4-version-baseline-refresh / **SPEC.md**: `feature-docs/exit4-version-baseline-refresh/SPEC.md` / **IMPLEMENTATION.md**: not written (tier `reduced`, single task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/exit4-version-baseline-refresh/THREAT-MODEL.md` (verdict `no-trust-boundary`)

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command (full suite): `python3 -m unittest discover -s tests`
- Command (module under change): `python3 -m unittest tests.test_exit4_tip_argument_version_bump`
- Coverage: not measured (standard-library `unittest` only, no coverage tooling); the scenario coverage below is the criterion

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1; FR1, NFR2) Run the module on the current tree | `TestPluginManifestVersion` and `TestMarketplaceEntryVersion` pass with `BASELINE_PATCH` at 68 | Unit |
| TS-2 | (SPEC TS2; FR2) Run the negative proof and the non-vacuity guard against the forged `"0.1.68"` sample | `test_baseline_matcher_rejects_forged_pre_bump_version` passes (the baseline matcher rejects the sample) and `test_forged_pre_bump_version_is_well_formed` passes (the sample parses) | Unit |
| TS-3 | (SPEC TS3; FR4) Run the new tie test in `TestValidationDetectsRegressions`; confirm task0001's per-task test record shows it was observed red while only `BASELINE_PATCH` had changed | The tie test passes: `FORGED_PRE_BUMP_VERSION` parses to (0, 1, `BASELINE_PATCH`); the record shows the red-then-green observation; the test uses only the standard library and invokes no git | Unit |
| TS-4 | (SPEC TS4; FR1, FR5, NFR1) In a throwaway copy outside the repository (never committed), set both registries' em-workflow version to the pre-bump `0.1.68` and run the module | `test_version_is_past_baseline` and `test_em_workflow_entry_version_is_past_baseline` fail with a tuple-form message "(0, 1, 68) not greater than (0, 1, 68)"; the text matches what the AC-1 / AC-2 / AC-3 `red_reason` values quote | Manual |
| TS-5 | (SPEC TS5; NFR2) Run the full suite | `python3 -m unittest discover -s tests` exits 0 | Integration |
| TS-6 | (SPEC AC-4; FR3, NFR5) Search the module text for `44` | No docstring or comment presents `44` or `0.1.44` as the baseline; the AC-1 docstring describes the per-component comparison against (0, 1, `BASELINE_PATCH`), not a `0.1` pin; the AC-2 "no version key" wording is unchanged | Static check |
| TS-7 | (SPEC AC-5; FR5, NFR5) Compare `test-docs/exit4-tip-argument/task0002.tests.yaml` against the integration base | Only the AC-1, AC-2 and AC-3 `red_reason` values differ; each names the new baseline and quotes the tuple-form `AssertionError`; AC-2's em-review clause is retained; the AC-2 test ID `test_em_review_entry_has_no_version_key` is still listed | Static check |
| TS-8 | (SPEC AC-6; NFR1, NFR3, NFR4, NFR5) List the feature's changed paths against the integration base and inspect the module's imports | Changed paths are only `tests/test_exit4_tip_argument_version_bump.py`, `test-docs/exit4-tip-argument/task0002.tests.yaml` and this feature's own `feature-docs` / `test-docs` entries; neither registry file nor any of the three exit4-tip-argument historical records appears; the module imports only `json`, `re`, `unittest`, `pathlib` and no other test module | Static check |

## Code Quality Verification
- Format: not configured (`project.components.main.format_command` is empty)
- Static analysis: not configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `BASELINE_PATCH` equals 68 | Inspection of the module; TS-1, TS-4 |
| AC-2 | `FORGED_PRE_BUMP_VERSION` equals `"0.1.68"`; negative proof and non-vacuity guard pass | Inspection of the module; TS-2 |
| AC-3 | The tie test exists, passes, and was observed red before both constants agreed | TS-3 |
| AC-4 | No docstring or comment presents `44` / `0.1.44` as the baseline | TS-6 |
| AC-5 | The AC-1 / AC-2 / AC-3 `red_reason` values name the new baseline and quote the re-observed failure; no other field changes | TS-4, TS-7 |
| AC-6 | Full suite exits 0; diff confined; stdlib-only imports | TS-5, TS-8 |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | TS-1 through TS-8 |
| SC-3 | Code review is completed | review step of workflow.yaml reaches `completed` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-6 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-4, TS-7 |
| NFR1 | task0001 | TS-4, TS-8 |
| NFR2 | task0001 | TS-1, TS-5 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-8 |
| NFR5 | task0001 | TS-7, TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] TS-4: throwaway red run against the pre-bump registry value. The copy lives outside the repository working tree, is discarded afterwards, and the repository's registry files are never edited (NFR1).

## Performance / Security Verification (if applicable)
- Not applicable: THREAT-MODEL.md's verdict is `no-trust-boundary` (no TM-n), and SPEC.md states no performance requirement.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit tests | 3 (TS-1, TS-2, TS-3) | 3 | 0 | 0 |
| Integration tests | 1 (TS-5) | 1 | 0 | 0 |
| Static checks | 3 (TS-6, TS-7, TS-8) | 3 | 0 | 0 |
| Manual tests | 1 (TS-4) | 0 | 0 | 1 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| Total | 8 | 7 | 0 | 1 |
