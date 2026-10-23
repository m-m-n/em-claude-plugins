# Verification Document: artifact-digest-empty-targets

## Overview
**Feature**: artifact-digest-empty-targets / **SPEC.md**: `feature-docs/artifact-digest-empty-targets/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/artifact-digest-empty-targets/IMPLEMENTATION.md`

Scenarios TS-1 to TS-5 correspond in order to SPEC.md's Unit Tests scenarios 1 to 5. TS-6 covers SPEC.md's Edge Cases item. TS-7 and TS-8 make the unchanged-file conditions of FR3 and NFR2 checkable on the integrated result.

## Build Verification
- Command: none. `project.components.main.build_command` is empty in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not measured. The change is a procedure document plus documentation tests, so the pass or fail result of the suite is the criterion.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Cut out the Pre-dispatch verification section of `em-workflow/references/artifact-digest.md` by its heading, normalize whitespace, and check the zero-target statement | The section states that when zero targets require an `expect_digest`, Calculation is not run and the verification succeeds (not a mismatch). The statement precedes the section's Calculation step | Unit |
| TS-2 | Cut out the Layer 5 recording section by its heading, normalize whitespace, and check the zero-artifact statement | The section states that when `written_artifacts` has zero entries, Calculation is not run and nothing is recorded, and that the acceptability of an empty `completed` result is left to the rules of the layer that handles it | Unit |
| TS-3 | Run the existing test methods of `tests/test_artifact_digest_docs.py`, unchanged | All pass: the six level-2 headings, the exit-code-2 wording of the Calculation section ("no argument was given", "standard output carries no array"), Layer 5's "one Calculation call" and "every written_artifacts path", and the error-element mismatch and failure wording | Unit |
| TS-4 | Run the existing restatement-detection test (TestEverySiteCitesTheOwner) and `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` | The test passes and the dispatch_digest_wiring check reports a pass | Unit / Integration |
| TS-5 | For every new matcher used to assert absence, run its paired crafted-text case | Each such matcher fires on crafted text containing the phrase. Vacuous when no new matcher asserts absence | Unit |
| TS-6 | Check that the zero-target statement is keyed on the `expect_digest` requirement | The statement names the `expect_digest` requirement, so an empty targets list and an all-`create` targets list both fall under it | Unit |
| TS-7 | Check that the integrated diff against the base revision does not include `em-workflow/scripts/artifact-digest.py`, then run `python3 -B em-workflow/scripts/artifact-digest.py` with no argument | No diff for the script. The no-argument run exits with code 2 and prints no array on standard output | Integration |
| TS-8 | List the files changed by the integrated diff against the base revision | Only `em-workflow/references/artifact-digest.md`, `tests/test_artifact_digest_docs.py`, and paths under `feature-docs/artifact-digest-empty-targets/` or `test-docs/artifact-digest-empty-targets/` appear. No citing dispatch-site document and not `em-workflow/references/contracts/spec-writer-contract.md` | Integration |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty in workflow.yaml)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1-FR4 and NFR1-NFR3 are satisfied | Functional Requirements Coverage table below |
| SC-2 | AC-1: the Pre-dispatch verification section states the zero-target rule | TS-1, TS-6 |
| SC-3 | AC-2: the Layer 5 recording section states the zero-artifact rule and the delegation of empty-result acceptability | TS-2 |
| SC-4 | AC-3: `em-workflow/scripts/artifact-digest.py` is unchanged; the Calculation section's exit code 2 item still contains "no argument was given" | TS-3, TS-7 |
| SC-5 | AC-4: `tests/test_artifact_digest_docs.py` tests both zero cases, and the full suite passes | TS-1, TS-2, Test Verification command |
| SC-6 | AC-5: following the reproduction steps through the document reaches no no-argument Calculation call, the verification succeeds, and the dispatch proceeds | TS-1, Manual Testing item 1 |
| SC-7 | AC-6: dispatch_digest_wiring passes | TS-4 |
| SC-8 | `python3 -m unittest discover -s tests` passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6; Manual Testing item 1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3, TS-7 |
| FR4 | task0001 | TS-1, TS-2; Test Verification command |
| NFR1 | task0001 | TS-3 |
| NFR2 | task0001 | TS-4, TS-8 |
| NFR3 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] 1. Reproduction walk-through (AC-5): take the first create-spec dispatch of a new feature, where the REQUIREMENTS.md and SPEC.md targets are both `create`. Follow the edited Pre-dispatch verification section of `em-workflow/references/artifact-digest.md` in order. No step runs Calculation without an argument, the verification succeeds, and the procedure proceeds to dispatch.

## Performance / Security Verification (if applicable)
- TM-1: the zero-target condition counts the targets that require an `expect_digest` (not the presence of non-null values), and the procedure and mismatch conditions for one or more such targets are unchanged. Checked by TS-1 and TS-6 (the new tests on the Pre-dispatch verification section) and TS-3 (the existing mismatch-wording tests).
- TM-2: the Layer 5 zero-artifact rule only skips Calculation and records nothing, and it leaves the acceptability of an empty `completed` result to the rules of the layer that handles it. Checked by TS-2 (the delegation statement is present) and TS-3 (the existing failure-wording tests). A reviewer also reads the edited Layer 5 recording section to confirm that the edit added no wording that accepts an empty `completed` result.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Full test suite | 1 | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 1 |
| Total | 12 | 11 | 0 | 2 |

TM-2 has both an automated check and a manual review, so the Automated and Manual columns of the Security row overlap by one item.
