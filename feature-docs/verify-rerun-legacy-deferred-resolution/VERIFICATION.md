# Verification Document: verify-rerun-legacy-deferred-resolution

## Overview
**Feature**: verify-rerun-legacy-deferred-resolution / **SPEC.md**: `feature-docs/verify-rerun-legacy-deferred-resolution/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/verify-rerun-legacy-deferred-resolution/IMPLEMENTATION.md`

## Build Verification
- Command: none (project.components.main.build_command is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0
- Coverage target: not measured (no coverage command is configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The develop SKILL.md subsection 「#### verify pass による deferred 指摘の解決」 is read for the legacy re-run statement | The subsection states that a verify re-run on a workflow.yaml whose verify step lacks round / passed_ids follows the same procedure, that round becomes 1, that passed_ids is written in the same write as result, and that on pass the mapping and the run of resolve-verified-findings.py are performed; tests/test_verify_pass_resolution_procedure.py pins each statement | Unit |
| TS-2 | The same subsection is read for the mapping rule | It states that a finding is mapped even with an add-on (cause analysis, fix suggestion, scope judgment), and that ambiguous findings, findings also claiming another not-passed criterion's miss or another defect, and findings where the ID merely appears are not mapped; the phrase 「未達そのもの以外の内容を含む指摘は対応づけない」 is absent; the updated TestAC2MappingRule test pins this | Unit |
| TS-3 | A legacy workflow.yaml (verify step without round / passed_ids, every step completed or skipped) and a round 2 record with one deferred high finding with category spec are committed in a temporary git repository, and merge-preflight.py is run | merge-preflight.py returns unresolved_findings | Integration |
| TS-4 | On the same fixture, round 1, passed_ids containing the criterion ID and result pass are recorded, resolve-verified-findings.py is run with a mapping file of the stable_id and its criterion ID, and the result is committed | The finding has resolution fixed and a verify_resolution field, and merge-preflight.py returns proceed | Integration |
| TS-5 | `python3 -m unittest discover -s tests` is run | Exit code 0, existing tests included | Regression |

## Code Quality Verification
- Format: none configured (project.components.main.format_command is empty)
- Static analysis: none configured
- Imports: the two test files import only the standard library (NFR1), checked by reading their import statements

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The subsection states the legacy re-run procedure, and a test pins it | TS-1 |
| AC2 | The subsection states the revised mapping rule, a test pins it, and the test that pinned the old phrase is updated | TS-2 |
| AC3 | On the legacy fixture, the re-run, script run and commit set the finding fixed and merge-preflight.py returns proceed; before the re-run it returns unresolved_findings | TS-3, TS-4 |
| AC4 | resolve-verified-findings.py, merge-preflight.py, the existing tests in tests/test_resolve_verified_findings.py and the REQUIREMENTS.md / SPEC.md of verify-pass-resolves-deferred-findings are unchanged, and the suite passes | TS-5, plus a diff of the feature's integration range (implement base_commit to the integration branch tip) showing no change to those files |
| Suite | `python3 -m unittest discover -s tests` passes | TS-5 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1; TS-4 exercises the recorded re-run end to end |
| FR2 | task0001, task0002 | TS-5 and the AC4 diff check |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-1, TS-2 |
| FR5 | task0002 | TS-3, TS-4 |
| FR6 | task0001, task0002 | TS-5 and the AC4 diff check |
| NFR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4 run as standard-library tests; import check under Code Quality Verification |
| NFR2 | task0001 | TS-5 runs the fixed-phrase assertions of tests/test_verify_pass_resolution_procedure.py |
| NFR3 | task0001 | TS-5 runs the assertions that the subsection adds no gate or question |
| NFR4 | task0001, task0002 | TS-5 and the AC4 diff check, which also shows no change to the version fields of em-workflow/.claude-plugin/plugin.json and .claude-plugin/marketplace.json |

## Manual Testing (E2E Not Possible)
- [ ] Read the rewritten subsection as a whole: the kept phrase 未達そのものであるときだけ and the add-on tolerance read as one consistent rule (the claim is the miss itself; add-ons are not a second claim), and the legacy re-run statement does not contradict the subsection's other steps.

## Performance / Security Verification (if applicable)
- TM-1: the mapping rule maps a finding only when its claim is the passed criterion's miss, and excludes findings that also claim another not-passed criterion's miss or another defect, ambiguous findings and ID-only findings — checked by the TS-2 assertions in tests/test_verify_pass_resolution_procedure.py, with the manual read above as a supplement.
- TM-2: the subsection keeps the Untrusted-Input Handling reference and 本文に ID が現れているだけでは足りない, and adds no gate or question — checked by the assertions in tests/test_verify_pass_resolution_procedure.py, run under TS-5.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Success criteria (AC1 to AC4, Suite) | 5 | 5 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Manual reading | 1 | 0 | 0 | 1 |
