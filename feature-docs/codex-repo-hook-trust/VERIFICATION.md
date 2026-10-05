# Verification Document: codex-repo-hook-trust

## Overview
**Feature**: codex-repo-hook-trust / **SPEC.md**: `feature-docs/codex-repo-hook-trust/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-repo-hook-trust/IMPLEMENTATION.md`

Branch note: scenarios marked Branch E or Branch N depend on the FR1 outcome
(terms defined in IMPLEMENTATION.md). The branch actually taken is read from
the per-route verdict in
`feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md`; scenarios of the
other branch are reported as not applicable, never as passed.

## Build Verification
- Command: none — both components (repo-tests, plugin-invariants) declare an empty build_command
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (component repo-tests)
- Command: `python3 em-workflow/scripts/check-plugin-invariants.py .` (component plugin-invariants)
- Coverage target: no coverage tool is configured; coverage is judged by the scenario table below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC TS1, Branch E: stub codex first on PATH, HOME and CODEX_HOME temporary, every changed route × readonly/readwrite | The argv or environment carries the protective specification and the wrapper's guard registration; a fabricated argv/environment without the specification is rejected; the stub saw temporary HOME and CODEX_HOME; the sentinel credential value is absent from the wrapper's output | Unit |
| TS-2 | SPEC TS2, Branch E: real Codex 0.160.0, temporary repository with a marker-writing working-directory hook, every changed route × mode | A control launch without the specification creates the marker; the launch through the wrapper creates none; the case skips with its reason when codex is absent, does not report 0.160.0, or the control creates no marker | Integration |
| TS-3 | SPEC TS3: regression of tests/test_codex_hook_wrapper_args.py, tests/test_consultation_harness_chain.py, tests/test_codex_wrapper_single_invocation.py, tests/test_codex_reviewer_temp_file_isolation.py | All pass inside a passing full `python3 -m unittest discover -s tests` run; their expected fixed values differ from base_commit only where Branch E changed the launch | Integration |
| TS-4 | Findings record completeness (SPEC AC1) | The record gives executed / not executed / unobservable (with reason) for P1–P4 × mode × location × event, the Codex version reported (0.160.0), the source of the location and event list, the hook definitions, the probe commands, the positive control behind every "not executed", the same-key PreToolUse override observation, and the per-route verdict and branch | Inspection |
| TS-5 | Branch application consistency (FR3) | Every route the record marks executing carries the protective specification in each wrapper that has the route, and the record's post-change probe shows no repository hook ran; every route marked not executing has the same launch composition as at base_commit | Inspection |
| TS-6 | codex-interactive-guard-hook TB-3 (SPEC AC3, A1) | TB-3 cites the record and the per-route verdicts; the configuration-layers item is not stated as unresolved; Branch N: states that no route executes repository hooks; Branch E: names the changed routes, the means and any route on which the guard no longer fires; feature-docs/codex-interactive-guard-hook/SPEC.md is unchanged in the integrated diff | Inspection |
| TS-7 | Wrapper comments (SPEC AC5) | Each wrapper's Interactive-guard hook section comment states the FR1 result for that wrapper's routes and matches the argv the wrapper actually builds | Inspection |
| TS-8 | Real Codex home isolation (NFR1) | The record shows temporary HOME and CODEX_HOME for every probe; TS-1 and TS-2 launch with temporary HOME and CODEX_HOME; no test or record uses the user's real Codex home as a read or write location | Unit + Inspection |
| TS-9 | Standard library only (NFR2) | New and changed test modules import only Python standard library modules and modules inside tests/ | Inspection |
| TS-10 | Wrapper contract (NFR3) | Usage text and accepted options unchanged from base_commit; one codex exec per run; prompt last; no 2>&1 added to the em-workflow wrapper; exactly one 2>&1 in the em-review wrapper; the em-review wrapper rejects --litellm; the guard registration, --ignore-rules, the default route's --ignore-user-config and the --litellm route's -p litellm -m MODEL are present | Unit + Inspection |
| TS-11 | Both wrappers in the same change (NFR4) | The integrated diff (base_commit..integration branch) changes both wrapper files; a Branch E change on the default route uses the same means in both | Inspection |
| TS-12 | No credentials in records or output (NFR5) | The findings record and the TB-3 update contain no credential value; TS-1's sentinel check passes; when LITELLM_API_KEY is set in the verification environment, a count-only search finds its value nowhere in the test run output | Unit + Inspection |
| TS-13 | No plugin version change written (NFR6) | IMPLEMENTATION.md, the task plans and their Acceptance Criteria state no plugin version change; the integrated diff modifies neither plugin's .claude-plugin/plugin.json nor .claude-plugin/marketplace.json | Inspection |
| TS-14 | Plugin invariants | `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0 | Integration |
| TS-15 | Isolation of every Codex invocation the findings record relies on (NFR1; rework of TS-8) | Every Codex invocation the findings record cites as evidence — `codex --version`, `codex --help` and any subcommand help, `codex features list`, any other Codex subcommand, the probes, the positive controls and the post-change probes — is shown with HOME and CODEX_HOME set to temporary directories; no fact in the record (reported version, location and event list and its source, feature state, results) is derived from an invocation without them; any mention of the earlier non-isolated invocations is labelled superseded and none of their output is cited; the record states whether each re-derived fact is unchanged, and its result matrix, per-route verdicts and branch are unchanged | Inspection |

## Code Quality Verification
- Format: none configured (format_command is empty for both components)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The FR2 record states, for the em-workflow default route, the em-workflow --litellm route (trusted and not trusted) and the em-review route, whether working-directory hooks executed on Codex 0.160.0 | TS-4 |
| AC2 | Branch E: repository hooks do not execute on the changed routes, the FR5 tests pass, and the wrapper's own guard registration remains | TS-1, TS-2, TS-5, TS-10 |
| AC3 | Branch N: TB-3 records the result and no longer leaves it unresolved | TS-6 |
| AC4 | `python3 -m unittest discover -s tests` passes | TS-3 |
| AC5 | Both wrapper comments match the FR1 result and the actual launch | TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-4 |
| FR2 | task0001, task0002 | TS-4 |
| FR3 | task0001 | TS-1, TS-2, TS-5 |
| FR4 | task0001 | TS-6 |
| FR5 | task0001 | TS-1, TS-2 |
| FR6 | task0001 | TS-7 |
| NFR1 | task0001, task0002 | TS-8, TS-15 |
| NFR2 | task0001 | TS-9 |
| NFR3 | task0001 | TS-3, TS-10 |
| NFR4 | task0001 | TS-11 |
| NFR5 | task0001, task0002 | TS-12 |
| NFR6 | task0001 | TS-13 |

## Manual Testing (E2E Not Possible)
- [ ] TS-4: read the findings record against the probe matrix and confirm every probe command matches the argv the corresponding wrapper builds, with any difference listed
- [ ] TS-5: compare the record's per-route verdicts with the wrappers' launch composition in the integrated diff
- [ ] TS-6: read TB-3 and the Rationale of feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md against the record
- [ ] TS-7: read both wrapper comments against the record and the argv each wrapper builds
- [ ] TS-9, TS-11, TS-13: inspect imports and the integrated diff
- [ ] TS-15: read every Codex command line in the findings record (section 2 included) and confirm each shows temporary HOME and CODEX_HOME, that no cited output comes from a non-isolated invocation, and that the result matrix, per-route verdicts and branch are unchanged in the task0002 diff

## Performance / Security Verification
- TM-1: protective specification on every executing route, or positively controlled evidence that no route executes repository hooks — checked by TS-1, TS-2, TS-4, TS-5 and TS-6
- TM-2: the wrapper's own guard registration stays on every route, the same-key override is recorded, and any guard-off route is recorded in TB-3 — checked by TS-1, TS-4, TS-6 and TS-10
- TM-3: no credential value in the findings record, the TB-3 update or wrapper/test output — checked by TS-1 (sentinel) and TS-12
- TM-4: every probe and test launch uses temporary HOME and CODEX_HOME — checked by TS-1, TS-2, TS-8 and TS-15

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 15 | 4 fully (TS-1, TS-2, TS-3, TS-14) + 3 partly (TS-8, TS-10, TS-12) | 0 | 8 fully (TS-4, TS-5, TS-6, TS-7, TS-9, TS-11, TS-13, TS-15) + 3 partly (TS-8, TS-10, TS-12) |
| Success criteria | 5 | 2 (AC2, AC4) | 0 | 3 (AC1, AC3, AC5) + AC2 partly |
| Security (TM-n) | 4 | 4 partly (TM-1, TM-2, TM-3, TM-4) | 0 | 4 partly (TM-1, TM-2, TM-3, TM-4) |
