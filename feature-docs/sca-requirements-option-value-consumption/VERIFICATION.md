# Verification Document: sca-requirements-option-value-consumption

## Overview
**Feature**: sca-requirements-option-value-consumption / **SPEC.md**: `feature-docs/sca-requirements-option-value-consumption/SPEC.md` / **IMPLEMENTATION.md**: not written (single task, no cross-task decisions) / **THREAT-MODEL.md**: `feature-docs/sca-requirements-option-value-consumption/THREAT-MODEL.md`

## Build Verification
- Command: none — both components (`repo-tests`, `plugin-invariants`) declare an empty build_command; the Python scripts need no build step
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: each command exits 0
- Coverage target: no coverage tool is configured; coverage is judged by scenario coverage (every TS-n below has at least one test or inspection)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | requirements.txt `--trusted-host -c -r deps.txt`; deps.txt `vuln-pkg==1.0`; advisory for vuln-pkg | Names {vuln-pkg}, complete=True, deps.txt opened, exactly one finding, no undetermined note, no network attempt | Unit |
| TS-2 | requirements.txt `-f -c -r deps.txt`, repeated (subTest) with `-i`, `--extra-index-url`, `--index-url`, `--pypi-url`, `--find-links`, `--no-binary`, `--only-binary`, `--use-feature`, `--hash`, `--global-option`, `-C`, `--config-settings` | Names {vuln-pkg}, complete=True, deps.txt opened | Unit |
| TS-3 | requirements.txt `-f "-enamed-pkg" -r actual.txt`; actual.txt `actual-pkg` | Names exclude named-pkg and include actual-pkg, complete=True, actual.txt opened | Unit |
| TS-4 | requirements.txt `--find-links "-rdeps.txt" -r actual.txt`; deps.txt and actual.txt inside the root | deps.txt not opened, actual.txt opened, no deps.txt names, complete=True | Unit |
| TS-5 | requirements.txt `-f -- -r deps.txt` | deps.txt opened, complete=True | Unit |
| TS-6 | `--trusted-host=x -r deps.txt`, `--index-url= -r deps.txt`, `-ihttps://example.invalid/simple -r deps.txt`, `-f./wheels -r deps.txt` | deps.txt opened, complete=True | Unit |
| TS-7 | `--trusted -c -r deps.txt`, `--index -c -r deps.txt`, `--find -c -r deps.txt`; scan with own-pkg declared and an advisory for undeclared-pkg | complete=False, deps.txt not opened, the undetermined note counts 1 advisory | Unit |
| TS-8 | `--trusted -r deps.txt` and `--trusted=-rdeps.txt` | The first opens deps.txt with complete=False; the second does not open deps.txt, complete=False | Unit |
| TS-9 | `--constraint-extra x --con y`, `--con y`, `--no x`, `--constraint-extra x` | The first three complete=False, `--constraint-extra x` complete=True; names {own-pkg} | Unit |
| TS-10 | `-i`, `-f`, `--trusted-host`, `--`, `-f ./wheels --`, `--index-url URL -- --no-index` | complete=True, names {own-pkg} | Unit |
| TS-11 | requirements.txt `-r inc.txt` with inc.txt `--trusted-host -c -r deeper.txt`; separately requirements.txt `--trusted-host \` continued by `-c -r deeper.txt` | deeper.txt opened, its names included, complete=True | Unit |
| TS-12 | Full repository test suite | `python3 -m unittest discover -s tests` exits 0; among pre-existing tests only `test_ac6_a_constraint_abbreviation_is_not_flagged` changes its expectation; new tests are in `tests/test_scan_dependencies_pip_directness.py` and use standard-library modules only | Integration |
| TS-13 | Plugin invariants | `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0 | Integration |
| TS-14 | Scan of an abbreviation whose `=` value carries a secret-looking host (e.g. `--trusted=secret-host.invalid`, advisory for an undeclared package) and of a consumed index URL carrying an embedded user and token before `-c -r deps.txt` | Summary and findings contain no text, path, host or credential from the line; the only note token is the existing pip directness note, at most once | Unit |
| TS-15 | Inspection of the docstrings of `_requirements_option_items` and `_pip_requirements_direct_names` and the comment of the abbreviation option table | They describe value-only option consumption, the self-contained forms, non-interpretation of consumed values and abbreviation handling over every value-taking long name | Manual (inspection) |

TS-1 to TS-11 are SPEC.md's unit scenarios; TS-12 and TS-13 number SPEC.md's two integration tests (AC-12, AC-13); TS-14 verifies NFR3 (TM-4); TS-15 verifies FR8.

## Code Quality Verification
- Format: not configured (format_command is empty for both components) / Static analysis: not configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1–FR8 and NFR1–NFR5 are satisfied | Functional Requirements Coverage table below |
| SC-2 | AC-1 to AC-13 are satisfied | AC-1..AC-11 by TS-1..TS-11, AC-12 by TS-12, AC-13 by TS-13 |
| SC-3 | TS-1 to TS-11 pass | Run `python3 -m unittest discover -s tests` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-11 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-11 |
| FR3 | task0001 | TS-6 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-11 |
| FR5 | task0001 | TS-7, TS-8, TS-9 |
| FR6 | task0001 | TS-10, TS-12 |
| FR7 | task0001 | TS-9, TS-12 |
| FR8 | task0001 | TS-15 (inspection) |
| NFR1 | task0001 | TS-12 (includes the existing standard-library-only test) |
| NFR2 | task0001 | TS-1, TS-4, TS-8 |
| NFR3 | task0001 | TS-14 |
| NFR4 | task0001 | TS-12 |
| NFR5 | task0001 | TS-13 |

## Manual Testing (E2E Not Possible)
- [ ] TS-15: read the two docstrings and the abbreviation-table comment in `em-workflow/scripts/scan-dependencies.py` and confirm they match FR1–FR5

## Performance / Security Verification (if applicable)
- TM-1: separated forms of every value-only option consume the next token as a discarded value — checked by TS-1, TS-2 and TS-11 (the include after `-c` is opened and the set stays complete with the included names)
- TM-2: an abbreviation of any value-taking long name makes the set incomplete without consuming the next token — checked by TS-7, TS-8 and TS-9 (complete=False, and the undeclared advisory is counted in the existing note)
- TM-3: consumed and abbreviation values are never opened, fetched or added as names — checked by TS-3, TS-4, TS-5 and TS-8 (named-pkg absent, deps.txt not opened from a value, no network attempt)
- TM-4: consumed and undetermined values never reach the summary or findings — checked by TS-14 (forbidden fragments absent; only the existing pip directness note token)

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1..TS-15) | 15 | 14 | 0 | 1 |
| Code quality | 0 | 0 | 0 | 0 |
| Security (TM-1..TM-4) | 4 | 4 | 0 | 0 |
| Total | 19 | 18 | 0 | 1 |
