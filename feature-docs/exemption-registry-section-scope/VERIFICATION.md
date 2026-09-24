# Verification Document: exemption-registry-section-scope

## Overview

**Feature**: exemption-registry-section-scope / **SPEC.md**: `feature-docs/exemption-registry-section-scope/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/exemption-registry-section-scope/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the
  change is Python test code with no build step).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors.
- Coverage target: not measured. The project uses the standard library only
  and has no coverage tool. Instead, every scenario below maps to at least
  one automated test or one diff/static check.

### Test Scenarios from SPEC.md

Scenarios 1 to 7 come from SPEC.md Test Scenarios. Scenarios 8 and 9 come
from SPEC.md FR1 / FR2 and its Edge Cases. Scenarios 10 to 13 come from
SPEC.md Non-Functional Requirements. In this table, "registry section"
means the level-2 section headed Exemption registry.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | FR1, FR5, FR6: an unrelated table in a level-2 Gate option vocabulary section names `create-spec.feature-identity` and is placed before a zero-row registry section (the ticket's reproduction) | The loader returns an empty set; the fixture's non-vacuity precondition holds | Unit (hermetic) |
| TS-2 | FR1, FR5: a table in a later level-2 section (e.g. Scope), after the registry section, names a select gate | That gate is not exempted; with one valid registry row for another gate, the result is exactly that other gate | Unit (hermetic) |
| TS-3 | FR1, FR5: a level-3 subheading inside the registry section, followed by the table | The section does not end at the subheading; the table's valid row is returned | Unit (hermetic) |
| TS-4 | FR2, FR3: registry rows missing a reason, missing a guarantee, naming a non-select gate, or having the wrong cell count | Each case makes the loader raise `ValueError`; the validation cases' messages contain the matching violation substring | Unit (hermetic) |
| TS-5 | FR2, FR3: a valid registry row naming a select gate | The loader returns exactly that gate id | Unit (hermetic) |
| TS-6 | FR4: both test modules get the extractor, parser, validator and loader from the shared helper | `tests/_gate_vocabulary.py` is the only module under `tests/` defining them; both test modules import them from it; no local duplicate remains | Integration (full discover run + static inspection) |
| TS-7 | FR5, FR7, FR8: absent registry file; rewritten `TestExemptionRegistryDegrade` fixtures; real repository registry | Absent file gives an empty set; the level-2 heading fixtures behave as specified; the real registry exists and gives an empty set; the existing doc-side AC-3 / AC-4 tests and the correspondence sweep stay green | Integration (full discover run) |
| TS-8 | FR1: line-anchored section start: a document whose only registry-like heading is a level-3 Exemption registry heading, or that mentions the level-2 heading text only mid-line in prose | No section is found and the loader returns an empty set | Unit (hermetic) |
| TS-9 | FR2: a present registry section holding prose but no table | The loader raises `ValueError` | Unit (hermetic) |
| TS-10 | NFR1, NFR5: import surface of the helper and the two edited test modules | The helper imports only standard-library modules. The two test modules import only standard-library modules plus the helper. No test module imports another test module | Static inspection |
| TS-11 | NFR2: feature diff between the implement base commit and the integration branch | No path under `em-workflow/` changes; `.claude-plugin/marketplace.json` does not change; both em-workflow version fields stay 0.2.1 | Integration (diff check) |
| TS-12 | NFR3: location of `ISSUING_SITE_MAP` | Still defined in `tests/test_gate_option_vocabulary.py` and not in the helper; doc-side `test_issuing_site_map_is_cited_not_restated` passes | Static inspection + Unit |
| TS-13 | NFR4: frozen digest pins | `TestFrozenMachineReadSurface` passes; none of `em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py`, `tests/test_validate_worker_output.py` or the design-step fixture appears in the feature diff | Integration (full discover run + diff check) |

## Code Quality Verification

- Format: not configured (`project.components.main.format_command` is
  empty).
- Static analysis: not configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `load_exempt_gate_ids()` collects table rows only from `## Exemption registry` up to the next `## ` heading, through the same shared extractor as the doc-side registry section | TS-1, TS-2, TS-3, TS-8 pass; TS-6 static inspection |
| AC-2 | Parsed exemption rows are validated the same way as `validate_exemption_rows`, and an invalid row raises | TS-4, TS-5, TS-9 pass |
| AC-3 | One non-test helper under `tests/` holds the shared parser/validator, and both test modules use it | TS-6, TS-10 |
| AC-4 | A hermetic test shows that an unrelated table plus a zero-row `## Exemption registry` gives an empty set | TS-1 passes |
| AC-5 | `python3 -m unittest discover -s tests` passes | Test Verification command exits 0 |
| SC-1 | All functional requirements implemented and tested | Every row of the coverage table below has a task and a passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-13 all pass |
| SC-3 | Code review completed | The review phase finishes with `residual_critical_high: 0` |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-8 |
| FR2 | task0001 | TS-4, TS-5, TS-9 |
| FR3 | task0001 | TS-4, TS-5 |
| FR4 | task0001 | TS-6 |
| FR5 | task0001 | TS-1, TS-2, TS-3, TS-7 |
| FR6 | task0001 | TS-1, TS-2, TS-4, TS-5, TS-7 |
| FR7 | task0001 | TS-7 |
| FR8 | task0001 | TS-7 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-11 |
| NFR3 | task0001 | TS-12 |
| NFR4 | task0001 | TS-13 |
| NFR5 | task0001 | TS-10 |

## E2E Testing

Not applicable. The project has no E2E framework (`e2e_test_command` is
empty) and the change has no user-facing surface.

## Manual Testing (E2E Not Possible)

- [ ] Read the helper's module docstring and confirm that it states the
  degrade / raise policy: the three fail-safe empty-set conditions, with
  every other malformed registry raising.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 13 | 13 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| SPEC success criteria | 8 | 8 | 0 | 0 |
| Manual review | 1 | 0 | 0 | 1 |
