# Verification Document: verify-pass-resolves-deferred-findings

## Overview
**Feature**: verify-pass-resolves-deferred-findings / **SPEC.md**: `feature-docs/verify-pass-resolves-deferred-findings/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/verify-pass-resolves-deferred-findings/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the Python
  sources are not built)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors, existing tests included
- Coverage target: no coverage tool is configured; every task Acceptance
  Criterion maps to at least one test

### Test Scenarios from SPEC.md

TS-1 to TS-8 come from SPEC.md. TS-9 to TS-12 are added by this plan to give
FR9, FR10, FR11, NFR1, NFR3, NFR4, NFR5 and NFR6 a verifying scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | In a temporary git repository, a latest round record with a deferred spec/high finding, a `workflow.yaml` with verify pass, and a mapping to a passed ID; run the script and commit `workflow.yaml` and the record in one commit (`tests/test_resolve_verified_findings.py`) | Before the script, `merge-preflight.py` returns `unresolved_findings`; after it, the finding is `fixed` with the fixed-format reason and the five `verify_resolution` keys, and `merge-preflight.py` returns `proceed` (SPEC AC1, AC2, AC9) | Integration |
| TS-2 | Findings absent from the mapping, a deferred `category: security` finding, findings mapped to excluded, unevaluated and unknown IDs; run the script (`tests/test_resolve_verified_findings.py`) | All stay deferred with unchanged values; `merge-preflight.py` returns `unresolved_findings` (SPEC AC3) | Integration |
| TS-3 | Run the script against a `workflow.yaml` whose verify result is `fail` (`tests/test_resolve_verified_findings.py`) | The round record is byte-identical (SPEC AC4) | Unit |
| TS-4 | Findings with resolution unresolved / fixed / declined, and a round1 finding while round2 is the latest; run the script (`tests/test_resolve_verified_findings.py`) | None of them changes (SPEC AC5) | Unit |
| TS-5 | Run the script twice with the same inputs (`tests/test_resolve_verified_findings.py`) | The record is byte-identical after both runs (SPEC AC6) | Unit |
| TS-6 | Run the script with a broken mapping, a broken round record and a broken `workflow.yaml`, each separately (`tests/test_resolve_verified_findings.py`) | Non-zero exit and no file changed (SPEC AC7) | Unit |
| TS-7 | Check the text of develop SKILL.md's verify section, workflow-schema.md and review-phase.md (`tests/test_verify_pass_resolution_procedure.py`, `tests/test_verify_resolution_record_docs.py`) | The procedure (round, passed_ids, mapping in pass rounds, script run, same `commit-docs.sh` commit) and the new fields are present (SPEC AC8) | Unit |
| TS-8 | Run `python3 -m unittest discover -s tests` | Passes, existing tests included (SPEC AC10) | Integration |
| TS-9 | Check the text of batch-mode.md's Reporting and audit-item source map (`tests/test_verify_resolution_record_docs.py`) | The fixed-by-verify-pass group (stable_id, verify round, criteria IDs) is shown apart from the still-deferred group and sourced from the latest round record; free text is not transcribed (FR10) | Unit |
| TS-10 | Run the script with a YAML tag that constructs a language-native object, with an instruction-like sentinel in finding text and the mapping, and on a successful rewrite (`tests/test_resolve_verified_findings.py`) | The tagged input exits non-zero with nothing written; the sentinel never appears in stdout or stderr; only the latest round record changes (NFR1, NFR6) | Integration |
| TS-11 | Check the new subsection of develop SKILL.md's verify section (`tests/test_verify_pass_resolution_procedure.py`) | It states identical application in interactive and batch mode and contains no `gate_id`, `AskUserQuestion` or `batch-policies.yaml` (FR9, NFR4) | Unit |
| TS-12 | Diff the integration branch against `workflow.implement.base_commit`: `git diff {base_commit}..HEAD -- em-workflow/scripts/merge-preflight.py tests/test_merge_preflight.py` and `git diff {base_commit}..HEAD -- em-workflow/.claude-plugin/plugin.json .claude-plugin/marketplace.json` | The first diff is empty; the second shows no change to a `version` line (FR11, NFR3, NFR5) | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | An eligible deferred spec/high finding becomes `fixed` with the reason and the structured provenance | TS-1 |
| AC2 | `merge-preflight.py` returns `proceed` on the committed AC1 state | TS-1 |
| AC3 | Unmapped, non-spec and non-passed-ID findings stay deferred; the preflight returns `unresolved_findings` | TS-2 |
| AC4 | A verify result of `fail` changes no finding | TS-3 |
| AC5 | Unresolved / fixed / declined findings and older rounds do not change | TS-4 |
| AC6 | Two runs give the same result as one | TS-5 |
| AC7 | Structurally broken input: nothing written, non-zero exit | TS-6 |
| AC8 | develop SKILL.md, workflow-schema.md and review-phase.md carry the procedure and the new fields | TS-7 |
| AC9 | Without the fix, the AC1 / AC2 tests fail | TS-1 (its "before" assertion) |
| AC10 | `python3 -m unittest discover -s tests` passes | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-7 |
| FR2 | task0002 | TS-7 |
| FR3 | task0002 | TS-7; manual walk-through below |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-6, TS-7 |
| FR5 | task0001, task0003 | TS-1, TS-7 |
| FR6 | task0002 | TS-1, TS-7 |
| FR7 | task0001, task0002 | TS-5 |
| FR8 | task0001 | TS-2, TS-3, TS-4 |
| FR9 | task0002 | TS-11 |
| FR10 | task0003 | TS-9 |
| FR11 | task0001 | TS-1, TS-2, TS-12 |
| NFR1 | task0001, task0002, task0003 | TS-10 |
| NFR2 | task0002, task0003 | TS-8 |
| NFR3 | task0001, task0002, task0003 | TS-8, TS-12 |
| NFR4 | task0002 | TS-11 |
| NFR5 | task0001, task0002, task0003 | TS-12 |
| NFR6 | task0001 | TS-10 |

## Manual Testing (E2E Not Possible)
- [ ] FR3 judgment walk-through: read the new subsection of develop SKILL.md's
  verify section and confirm by hand that, for a deferred spec/high finding
  whose text says only that one specific acceptance criterion is unmet, the
  rule maps it to that criterion; and that a finding which also points out a
  code defect, or which only mentions a criterion ID, is left out.

## Performance / Security Verification (if applicable)
- Performance: not applicable.
- TM-1: the mapping is judged only in pass rounds, only for deferred
  critical/high spec findings, only when the content is the non-attainment
  itself, with untrusted text read as data — checked by TS-7 (task0002 AC-2)
  and the manual walk-through above.
- TM-2: `passed_ids` holds only IDs evaluated with a pass outcome, leaving
  out excluded and unevaluated IDs, replaced each round — checked by TS-7
  (task0002 AC-1).
- TM-3: every mapping entry is re-checked against structured values and an
  ineligible entry changes nothing — checked by TS-2 (task0001 AC-2).
- TM-4: YAML is read with safe load only, and a tag constructing a
  language-native object is a structural error — checked by TS-10 (task0001
  AC-7).
- TM-5: all inputs are validated before any write, a structural error writes
  nothing, and only the latest round record is written — checked by TS-6 and
  TS-10 (task0001 AC-6, AC-7).
- TM-6: script output carries only validated structured values — checked by
  TS-10 (task0001 AC-7).
- TM-7: the rewritten finding carries the fixed-format reason and the
  `verify_resolution` record, committed with the verify result — checked by
  TS-1 (task0001 AC-1) and TS-7 (task0002 AC-3).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 12 | 0 | 0 |
| Success criteria (AC1 to AC10) | 10 | 10 | 0 | 0 |
| Requirements coverage | 17 | 17 | 0 | 0 |
| Security mitigations (TM-1 to TM-7) | 7 | 7 | 0 | 1 |
| Manual walk-through | 1 | 0 | 0 | 1 |
