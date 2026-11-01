# Verification Document: rework-docs-only-medium-fixes

## Overview
**Feature**: rework-docs-only-medium-fixes / **SPEC.md**: `feature-docs/rework-docs-only-medium-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/rework-docs-only-medium-fixes/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tool; NFR2)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A declared rename's `to` is not in the post-change VERIFICATION.md (fictitious `to`, for example TS3→TS-9999) (FR1) | rejected, `rework-index`, exit 1 | Unit |
| TS-2 | A declared rename's `from` remains in the post-change VERIFICATION.md (FR1) | rejected, `rework-index`, exit 1 | Unit |
| TS-3 | A declared rename's `from` is not in the baseline VERIFICATION.md (FR1) | rejected, `rework-index`, exit 1 | Unit |
| TS-4 | `--feature-dir` or `--baseline-dir` is missing (FR1) | no rename-based acceptance; rejected, `rework-index`, exit 1, with a diff-unavailable message distinct from the no-declaration message | Unit |
| TS-5 | feature-dir has no VERIFICATION.md (FR1) | no rename-based acceptance; rejected, `rework-index`, exit 1 | Unit |
| TS-6 | A declared rename meets all conditions (baseline has TS3; post-change has TS-3 and not TS3) (FR1, FR7) | accepted, exit 0 | Unit |
| TS-7 | A declared rename's `from` (TS3) is listed in covered_by_existing although it is a verification_index key (FR2) | rejected, `rework-index`, exit 1 | Unit |
| TS-8 | With the diff available, a covered_by_existing ID is absent from the post-change VERIFICATION.md (FR2) | rejected, `rework-index`, exit 1 | Unit |
| TS-9 | Without the directories, a verification_index key unrelated to any rename is covered_by_existing (FR2) | accepted as before, exit 0 | Unit |
| TS-10 | Docs-only round: an entry sets implement to completed (FR3) | rejected, `docs-only-implement-reset`, exit 1 | Unit |
| TS-11 | Docs-only round: step_patches is empty (FR3) | rejected, `docs-only-step-patches`, exit 1 | Unit |
| TS-12 | Docs-only round: step_patches has two or more entries (a non-origin step mixed in) (FR3) | rejected, `docs-only-step-patches`, exit 1 | Unit |
| TS-13 | Docs-only round: the origin step's set.status is not pending (for example completed) (FR3) | rejected, `docs-only-step-patches`, exit 1 | Unit |
| TS-14 | The envelope's rework_source.type is verify but step_id is review, or the reverse (FR3) | rejected, `docs-only-step-patches`, exit 1 | Unit |
| TS-15 | No envelope rework_source.type: a single verify or review entry with pending; another step_id (FR3) | the former is accepted (exit 0); the latter is rejected (exit 1) | Unit |
| TS-16 | The FR3 rejections with and without `--dry-run-apply`, under `--kind worker-result` and `--kind workflow-patch` (FR3) | rejected on every combination | Unit |
| TS-17 | tests_replace chain (TS-1→TS-2, TS-2→TS-3) (FR4) | rejected, `requirements_patch`, exit 1 | Unit |
| TS-18 | tests_replace swap (TS-1→TS-2, TS-2→TS-1) (FR4) | rejected, `requirements_patch`, exit 1 | Unit |
| TS-19 | Non-overlapping pairs (valid-docs-only-round's TS1→TS-1, TS2→TS-2) (FR4, FR7) | accepted, exit 0 | Unit |
| TS-20 | Every existing valid- fixture (FR7) | accepted, exit 0 | Unit |
| TS-21 | Malformed rework_source / step_patches / tests_replace / VERIFICATION.md (NFR1) | no exception; exit 1 with JSON error details; never exit 2 | Unit |
| TS-22 | The three SSOT documents state the FR1–FR4 rules (FR5) | each named section states its rule (task0004 AC-1 to AC-4) | Manual |
| TS-23 | The tests added or changed by this feature import only the standard library and repository-local modules (NFR2) | no third-party import | Manual |
| TS-24 | The full test suite passes from the repository root (NFR3) | `python3 -m unittest discover -s tests` exits 0 | Unit |

TS-23 and TS-24 are verification scenarios for NFR2 and NFR3 (SPEC.md AC-4). They are not listed in SPEC.md's Test Scenarios.

## Code Quality Verification
- Format: none (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | For each of FR1–FR4 there is an invalid- fixture and a test, and the validator rejects it with exit code 1 | TS-1, TS-4, TS-7, TS-10 to TS-14, TS-17, TS-18 pass |
| AC-2 | Every existing valid- fixture is accepted with exit code 0 (valid-mixed-round-renamed-scenario-declared with feature-dir / baseline-dir) | TS-6, TS-19, TS-20 pass |
| AC-3 | rework-task-synthesis.md Section 12, rework-planner-contract.md check 2 and workflow-patch.md Tests replacement state the FR1–FR4 rules | TS-22 |
| AC-4 | `python3 -m unittest discover -s tests` passes | TS-21, TS-23, TS-24 |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR has a task and a passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-24 |
| SC-3 | Documentation is complete (FR5) | TS-22 |
| SC-4 | Code review is completed | The review phase records zero residual critical / high findings |
| SC-5 | `python3 -m unittest discover -s tests` passes from the repository root (NFR3) | TS-24 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR2 | task0001 | TS-7, TS-8, TS-9 |
| FR3 | task0002 | TS-10, TS-11, TS-12, TS-13, TS-14, TS-15, TS-16 |
| FR4 | task0003 | TS-17, TS-18, TS-19 |
| FR5 | task0004 | TS-22 |
| FR6 | task0001, task0002, task0003 | TS-1, TS-4, TS-7, TS-10, TS-11, TS-12, TS-13, TS-14, TS-17, TS-18 |
| FR7 | task0001, task0002, task0003 | TS-6, TS-19, TS-20 |
| NFR1 | task0001, task0002, task0003 | TS-21 |
| NFR2 | task0001, task0002, task0003 | TS-23 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-24 |

## Manual Testing (E2E Not Possible)
- [ ] TS-22: Read rework-task-synthesis.md Section 12 (the Rename-aware coverage item and the docs-only `append_rework` item), rework-planner-contract.md check 2 and the workflow-patch.md Tests replacement section. Confirm that each states the rules of IMPLEMENTATION.md D2–D4 and that none still states the looser rule.
- [ ] TS-23: Read the import statements of the test files changed by this feature. Confirm that every imported module is a standard-library or repository-local module.

## Performance / Security Verification (if applicable)
- TM-1: rename-based acceptance only when the document diff confirms every FR1 condition, failing closed when the diff is unavailable. Checked by TS-1 to TS-6 (automated).
- TM-2: a declared rename's `from` is never accepted, and with the diff available every covered ID must be in the post-change VERIFICATION.md. Checked by TS-7, TS-8 and TS-9 (automated).
- TM-3: a docs-only round has exactly one origin-step entry with pending, the origin matched against the envelope (fail-closed when malformed), and implement entries rejected. Checked by TS-10 to TS-16 (automated).
- TM-4: overlapping tests_replace from/to sets are rejected structurally. Checked by TS-17, TS-18 and TS-19 (automated).
- TM-5: malformed input is reported as exit 1 with JSON details and never raises. Checked by TS-21 (automated).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 24 | 22 | 0 | 2 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 9 | 6 | 0 | 3 |
| Security (TM-n) | 5 | 5 | 0 | 0 |
