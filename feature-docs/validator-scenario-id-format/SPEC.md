# Feature: validator-scenario-id-format

## Overview

`em-workflow/scripts/validate-worker-output.py` extracts VERIFICATION.md
scenario IDs in both the `TS-n` form and the `TSn` form. A rework that adds
a `TSn`-form scenario to VERIFICATION.md is recognized as adding a new
scenario. The scenario ID rule in `em-workflow/skills/plan-writing/SKILL.md`
agrees with the forms the validator extracts.

## Objectives

- When a rework-planner adds a scenario to VERIFICATION.md in either TS-n or
  TSn format, validate-worker-output.py recognizes it as new and no longer
  rejects correct output.
- The validator's scenario ID regex and the plan-writing scenario ID format
  rule agree.

## Acceptance Criteria

- [ ] **AC1** (FR1, FR2): Running the reproduction steps with TSn-form IDs
  (baseline TS1..TS12, rework adds TS13 to VERIFICATION.md and to
  `new_scenarios` and `tests_append`) produces no
  `is not a new VERIFICATION.md scenario` error.
- [ ] **AC2** (FR4): A test in `tests/test_validate_worker_output.py` fails
  if `_TS_ID_RE` is reverted to `r"TS-\d+"`.
- [ ] **AC3** (FR3, FR1): `plan-writing/SKILL.md` names TS-n as the form for
  new VERIFICATION.md files and states that TSn is also a valid,
  validator-recognized scenario ID. Those two forms are exactly the forms
  the validator extracts.
- [ ] **AC4** (FR5): The docstring of `extract_verification_scenario_ids`
  names both accepted forms and does not cite `SKILL.md 131-139`.
- [ ] **AC5** (NFR1, NFR2): `python3 -m unittest discover -s tests` passes.

## Technical Requirements

### Functional Requirements

- **FR1:** Recognize both scenario ID formats.
  `extract_verification_scenario_ids` in
  `em-workflow/scripts/validate-worker-output.py` extracts scenario IDs in
  both the TS-n form (`TS`, hyphen, one or more digits) and the TSn form
  (`TS`, one or more digits, no hyphen). A document may mix both forms.
  Recognition of TS-n stays unchanged.
- **FR2:** Hyphen-less new scenarios pass the rework_index check.
  When a `rework_index` `new_scenarios` entry uses the TSn form and is
  present in the feature's VERIFICATION.md but not in the baseline
  VERIFICATION.md, the validator reports no
  `is not a new VERIFICATION.md scenario` error for it. A TSn ID present in
  both documents is still rejected as not new.
- **FR3:** plan-writing scenario ID format rule.
  `em-workflow/skills/plan-writing/SKILL.md` says new VERIFICATION.md files
  use the TS-n form (`TS`, hyphen, digits) for scenario IDs. It also says
  the TSn form (no hyphen) is a valid scenario ID that the validator
  recognizes. Scenario IDs are compared as literal strings, so `TS13` and
  `TS-13` are distinct IDs. No other agent or contract text changes.
- **FR4:** Regression tests.
  `tests/test_validate_worker_output.py` has tests that fail if the
  validator stops recognizing TSn-form IDs. Coverage: extraction of TSn
  IDs, extraction from a document mixing both forms, and the
  `_validate_rework_index` path from the reproduction steps (baseline holds
  TS1..TS12, current VERIFICATION.md adds TS13, `new_scenarios ['TS13']`
  with `tests_append ['TS13']` produces no error).
- **FR5:** Stale docstring citation.
  The docstring of `extract_verification_scenario_ids` describes the
  accepted ID forms (TS-n and TSn) and no longer cites the stale
  `plan-writing/SKILL.md 131-139` line range.

### Non-Functional Requirements

- **NFR1 - No new test dependencies:** Tests use only the Python standard
  library `unittest`.
- **NFR2 - No regression:** `python3 -m unittest discover -s tests` passes.
  Existing TS-n tests and fixtures pass unmodified.

## Implementation Approach

### Architecture

Not applicable. The change touches a validator regex, its tests and a skill
document.

### Data Flow

Not applicable.

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/validate-worker-output.py`: `_TS_ID_RE`,
  `extract_verification_scenario_ids`, `_validate_rework_index`
- `em-workflow/skills/plan-writing/SKILL.md`: scenario ID format rule

**External Dependencies:**
- None

### File Structure

```
em-workflow/
├── scripts/
│   └── validate-worker-output.py      # FR1, FR2, FR5
└── skills/
    └── plan-writing/
        └── SKILL.md                   # FR3
tests/
└── test_validate_worker_output.py     # FR4
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (FR1): `extract_verification_scenario_ids` on a Test
  Scenarios section containing TS1, TS2 and TS13 - Returns
  `{'TS1','TS2','TS13'}`
- [ ] **TS-2** (FR1): `extract_verification_scenario_ids` on a section
  mixing TS-1 and TS2 - Returns `{'TS-1','TS2'}`
- [ ] **TS-3** (FR1): `extract_verification_scenario_ids` on a section
  containing TS13 - Returns TS13 and not TS1 (all digits consumed)
- [ ] **TS-4** (FR2): `_validate_rework_index` with baseline VERIFICATION.md
  TS1..TS12, current TS1..TS13, `new_scenarios ['TS13']`,
  `tests_append ['TS13']`, and task0007 in `tasks_patch` - No errors
- [ ] **TS-5** (FR2): `_validate_rework_index` with TS12 in both baseline
  and current VERIFICATION.md and `new_scenarios ['TS12']` - Error
  `new_scenarios 'TS12' is not a new VERIFICATION.md scenario`
- [ ] **TS-6** (FR2, FR3): `_validate_rework_index` with baseline containing
  TS-13 and current containing TS13, `new_scenarios ['TS13']` - TS13 is
  treated as a new, distinct literal ID (no `not a new` error)
- [ ] **TS-7** (NFR2): Existing TS-n tests
  (`TestReworkIndexNewScenariosRequireTestsAppend`,
  `TestReworkIndexRequiresBaselineForNewScenarios`) and the
  `references/fixtures` corpus - Pass unmodified

### Integration Tests

- None

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Manual Checks

- [ ] **TS-8** (FR3): plan-writing/SKILL.md scenario ID rule review -
  States TS-n as the form for new documents and TSn as also valid and
  validator-recognized, with literal-string comparison

### Edge Cases

- Covered by TS-3 (multi-digit TSn IDs) and TS-6 (TS-13 vs TS13 are
  distinct literal IDs).

### Performance Tests

- None

## Assumptions

- **a1:** Scenario IDs keep being compared as literal strings. TS13 and
  TS-13 are distinct IDs, and the validator does not normalize one form
  into the other.
- **a2:** Recognition of hyphenated TS-n IDs stays as it is, and the
  existing TS-n tests and fixtures keep passing unmodified.
- **a3:** IDs inside fenced code blocks or HTML comments, or outside the
  `### Test Scenarios from SPEC.md` section, are still ignored.

## Security Considerations

Not applicable.

## Error Handling

The validator error `new_scenarios '<id>' is not a new VERIFICATION.md
scenario` is still reported for an ID present in both the baseline and the
current VERIFICATION.md (FR2, TS-5).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1 through AC5 are satisfied

## Open Questions

None.

## References

- `em-workflow/scripts/validate-worker-output.py`
- `em-workflow/skills/plan-writing/SKILL.md`
- `tests/test_validate_worker_output.py`
