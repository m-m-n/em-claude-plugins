# Verification Document: exit4-ac2-test-id-drift

## Overview

- **Feature**: exit4-ac2-test-id-drift
- **SPEC.md**: `feature-docs/exit4-ac2-test-id-drift/SPEC.md`
- **IMPLEMENTATION.md**: not written. The tier is reduced and the feature has a
  single task, so no file is shared between tasks.
- **Task plan**: `feature-docs/exit4-ac2-test-id-drift/tasks/task0001.md`
- **THREAT-MODEL.md**: `feature-docs/exit4-ac2-test-id-drift/THREAT-MODEL.md`
  (verdict `no-trust-boundary`)

Terms used below:

- **target record**: `test-docs/exit4-tip-argument/task0002.tests.yaml`
- **version_bump module**: `tests/test_exit4_tip_argument_version_bump.py`
- **new module**: `tests/test_exit4_ac2_test_id_drift.py`
- **stale ID**: `tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_has_no_version_key`
- **replacement ID**: `tests.test_exit4_tip_argument_version_bump.TestMarketplaceEntryVersion.test_em_review_entry_version_not_bumped_with_em_workflow`

## Build Verification

- **Command**: none. Both components (`repo-tests`, `plugin-invariants`) have
  an empty build_command.
- **Expected**: not applicable.

## Test Verification

- **Command** (component `repo-tests`), from the repository root:
  `python3 -m unittest discover -s tests`
- **Command** (component `plugin-invariants`), from the repository root:
  `python3 em-workflow/scripts/check-plugin-invariants.py .`
- **Expected**: both exit 0.
- **Coverage target**: no coverage tool is configured for this repository.
  Coverage is judged by the scenario-to-requirement mapping below.

### Test Scenarios from SPEC.md

TS-1 to TS-5 correspond one-to-one to SPEC.md TS1 to TS5. TS-6 to TS-12 are
added here so that every FR and NFR has a verifying item.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC TS1 (FR1): run the replacement ID by name with the unittest runner from the repository root | Exit 0, 1 test run, 0 failures | Command |
| TS-2 | SPEC TS2 (FR5, FR6): the new module extracts every acceptance test ID from the target record and resolves each one, whether it is a module, class or method ID | 11 IDs extracted (AC-1: 2, AC-2: 4, AC-3: 1, AC-4: 4, AC-5: 0); all resolve; test passes | Unit |
| TS-3 | SPEC TS3 (FR7): the resolution judge is given the stale ID | Judged unresolved, including when the standard loader signals the missing attribute through a placeholder or loader error; the stale ID's module part and module-plus-class part resolve | Unit |
| TS-4 | SPEC TS4 (FR7): non-vacuity guard on the extracted ID list | The list is not empty and contains the replacement ID; AC-5 (`tests: []`) contributes no ID | Unit |
| TS-5 | SPEC TS5 (FR3, FR4): read the version_bump module's docstring from source | Neither ``no `version` key`` nor `no-version-key` is present; the text read is not empty and mentions AC-2 and AC-4 | Unit |
| TS-6 | FR2: inspect the AC-2 block of the target record | Contains "44 not greater than 44"; does not contain "that entry is untouched"; `red_confirmed: true` | Unit |
| TS-7 | FR5: aggregate check over two distinct unresolvable IDs and one resolvable ID | Fails; the message contains both unresolvable IDs and not the resolvable one | Unit |
| TS-8 | FR6: the new module's target list | Explicit enumeration whose only entry is the target record; no glob or directory scan of `test-docs/` | Inspection |
| TS-9 | NFR1: the new module's imports | Only standard-library modules; no YAML library | Inspection |
| TS-10 | NFR2: diff of the version_bump module against the base commit | Every changed line is inside the module docstring | Inspection |
| TS-11 | NFR3: diff stat of the feature against the base commit | No change under `em-review/`, `em-workflow/` or `plugin-dev/`; `.claude-plugin/marketplace.json` unchanged | Command |
| TS-12 | NFR4: `python3 -m unittest discover -s tests` from the repository root | Exit 0 | Command |

## Code Quality Verification

- **Format**: none configured. Both format_command values are empty.
- **Static analysis**: none configured.
- **Change-set containment** (SPEC AC-6): every path changed relative to the
  base commit is one of the following.
  - The target record. Only AC-2's fourth test ID and AC-2's red_reason
    differ.
  - The version_bump module, inside its module docstring only.
  - The new module.
  - Files under `feature-docs/exit4-ac2-test-id-drift/` or
    `test-docs/exit4-ac2-test-id-drift/`.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | AC-2 lists the replacement ID instead of the stale ID, and the replacement ID passes when run by name | TS-1, TS-2 |
| AC-2 | AC-2's red_reason states the observed em-workflow red and the em-review retention guards, without "that entry is untouched" | TS-6 plus the manual item below |
| AC-3 | The version_bump module docstring no longer contains the old strings and matches the real assertions | TS-5 plus the manual item below |
| AC-4 | The recurrence test resolves all 11 IDs of the target record, which is enumerated explicitly | TS-2, TS-8 |
| AC-5 | Negative proof for the stale ID and non-vacuity guard on the extracted list | TS-3, TS-4 |
| AC-6 | Full suite passes; the change set is limited; plugin.json and marketplace.json are unchanged | TS-9, TS-10, TS-11, TS-12, Change-set containment |
| SC | All functional requirements are implemented and tested; all test scenarios pass; `python3 -m unittest discover -s tests` succeeds from the repository root | TS-1 to TS-12 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-6, manual red_reason review |
| FR3 | task0001 | TS-5, manual docstring review |
| FR4 | task0001 | TS-5, manual docstring review |
| FR5 | task0001 | TS-2, TS-7 |
| FR6 | task0001 | TS-2, TS-8 |
| FR7 | task0001 | TS-3, TS-4 |
| NFR1 | task0001 | TS-9 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-11 |
| NFR4 | task0001 | TS-12 |

## Manual Testing (E2E Not Possible)

The project has no E2E framework, so there is no E2E section.

- [ ] **red_reason semantics (FR2)**: AC-2's red_reason in the target record
  meets all of the following.
  - It keeps the existing em-workflow clause verbatim.
  - It describes the two em-review tests (`source` unchanged; em-review
    `version` not following the em-workflow manifest `version`) as retention
    guards that were already green before the change.
  - It claims no red that was not observed.
  - It stays a single-line double-quoted scalar.
- [ ] **Docstring semantics (FR3, FR4)**: the version_bump module docstring
  meets all of the following.
  - Its AC-2 bullet describes the em-review version assertion as "not equal to
    the plugin manifest's version".
  - Its AC-4 inventory names the em-review source check and the em-review
    version non-linkage check.
  - It still classifies both as regression guards that need no negative
    proof.
- [ ] **Record well-formedness**: the target record still parses as YAML with
  the same top-level keys: `task_id`, `baseline_failures`, `final_failures`,
  `acceptance_tests`.

## Performance / Security Verification (if applicable)

Not applicable. The THREAT-MODEL.md verdict is `no-trust-boundary`, so there
is no TM-n to verify, and SPEC.md states no performance requirement.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS-2 to TS-7) | 6 | 6 | 0 | 0 |
| Command checks (TS-1, TS-11, TS-12, plugin-invariants) | 4 | 4 | 0 | 0 |
| Inspection (TS-8, TS-9, TS-10, change-set containment) | 4 | 0 | 0 | 4 |
| Manual semantic review | 3 | 0 | 0 | 3 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| **Total** | 17 | 10 | 0 | 7 |
