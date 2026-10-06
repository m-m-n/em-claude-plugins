# Verification Document: validator-scenario-id-format

## Overview
**Feature**: validator-scenario-id-format / **SPEC.md**: `feature-docs/validator-scenario-id-format/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/validator-scenario-id-format/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main` has no build command)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Coverage target: not defined

### Test Scenarios from SPEC.md
Fixture IDs used by these scenarios are listed under Scenario Fixtures below.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (FR1, FR4) Scenario ID extraction on a Test Scenarios section holding fixture F1 (three hyphen-less IDs) | Returns exactly the three hyphen-less IDs of F1 | Unit |
| TS-2 | (FR1, FR4) Extraction on fixture F2 (one hyphenated and one hyphen-less ID) | Returns exactly both IDs of F2, each in its own literal form | Unit |
| TS-3 | (FR1) Extraction on fixture F3 (one multi-digit hyphen-less ID) | Returns the full multi-digit ID only; no shorter ID made from its leading digit | Unit |
| TS-4 | (FR2, FR4) Rework-index validation with fixture F4 (baseline of twelve hyphen-less IDs, current adds a thirteenth, declared in new_scenarios and tests_append, task0007 in tasks_patch) | No errors | Unit |
| TS-5 | (FR2) Rework-index validation with fixture F5 (a hyphen-less ID present in both baseline and current, declared in new_scenarios) | The existing error "new_scenarios '<id>' is not a new VERIFICATION.md scenario" for that ID | Unit |
| TS-6 | (FR2, FR3) Rework-index validation with fixture F6 (baseline holds a hyphenated ID, current holds the hyphen-less ID with the same number, declared in new_scenarios) | The hyphen-less ID is new and distinct; no "is not a new VERIFICATION.md scenario" error | Unit |
| TS-7 | (NFR2) Existing hyphenated-ID tests (TestReworkIndexNewScenariosRequireTestsAppend, TestReworkIndexRequiresBaselineForNewScenarios) and the em-workflow/references/fixtures corpus | Pass without modification | Unit |
| TS-8 | (FR3) Review of the scenario ID rule in em-workflow/skills/plan-writing/SKILL.md | States the hyphenated form for new VERIFICATION.md files, the hyphen-less form as also valid and validator-recognized, and literal-string comparison; the two forms equal the forms the validator extracts; the rule sits outside the fenced template | Manual |
| TS-9 | (NFR1, NFR2; SPEC AC5) Full test suite run with the command above | Exit code 0; new tests use only the standard-library unittest framework | Integration |
| TS-10 | (FR4; SPEC AC2) Mutation check: scenario ID pattern temporarily set back to the hyphenated-only form, then the suite is run | The tests for the first, second and fourth scenarios of this table fail; the temporary change is discarded | Manual |
| TS-11 | (FR5; SPEC AC4) Review of the docstring of extract_verification_scenario_ids | Names both accepted forms; does not cite the stale plan-writing SKILL.md line range | Manual |

### Scenario Fixtures
This subsection is outside the parsed Test Scenarios section, so its literal
IDs are fixture data, not scenario IDs of this document.

- F1: rows carrying TS1, TS2 and TS13.
- F2: rows carrying TS-1 and TS2.
- F3: a single row carrying TS13.
- F4: baseline VERIFICATION.md rows TS1 through TS12; current rows TS1 through
  TS13; rework_index `new_scenarios` ['TS13']; requirements_patch
  `tests_append` ['TS13']; task0007 in `tasks_patch`.
- F5: baseline and current both carry TS12; `new_scenarios` ['TS12'].
- F6: baseline carries TS-13; current carries TS13; `new_scenarios` ['TS13'];
  `tests_append` ['TS13'].

## Code Quality Verification
- Format: none configured / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction steps with hyphen-less IDs produce no `is not a new VERIFICATION.md scenario` error | TS-4 |
| AC2 | A test fails if the scenario ID pattern is reverted to the hyphenated-only form | TS-10 |
| AC3 | `plan-writing/SKILL.md` names TS-n for new files and TSn as also valid and validator-recognized; these equal the validator's forms | TS-8, TS-1, TS-2 |
| AC4 | The extraction function's docstring names both forms and does not cite `SKILL.md 131-139` | TS-11 |
| AC5 | `python3 -m unittest discover -s tests` passes | TS-9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3 |
| FR2 | task0001 | TS-4, TS-5, TS-6 |
| FR3 | task0002 | TS-6, TS-8 |
| FR4 | task0001 | TS-1, TS-2, TS-4, TS-10 |
| FR5 | task0001 | TS-11 |
| NFR1 | task0001 | TS-9 |
| NFR2 | task0001, task0002 | TS-7, TS-9 |

## Manual Testing (E2E Not Possible)
- [ ] TS-8: review the scenario ID rule in `em-workflow/skills/plan-writing/SKILL.md`
- [ ] TS-10: mutation check of the scenario ID pattern
- [ ] TS-11: review the docstring of `extract_verification_scenario_ids`

## Performance / Security Verification (if applicable)
- TM-1: novelty is the literal set difference between the current and the
  baseline VERIFICATION.md through one extraction rule, with no normalization
  between forms — checked by TS-5 (a hyphen-less ID present in both documents
  is rejected), TS-7 (existing hyphenated-ID rejection tests pass unmodified)
  and TS-6 (the two forms are not collapsed into one ID).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS-1 to TS-7) | 7 | 7 | 0 | 0 |
| Integration (TS-9) | 1 | 1 | 0 | 0 |
| Manual review (TS-8, TS-10, TS-11) | 3 | 0 | 0 | 3 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 12 | 9 | 0 | 3 |
