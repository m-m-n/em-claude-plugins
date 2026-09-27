# Verification Document: threat-model-stride

## Overview
**Feature**: threat-model-stride / **SPEC.md**: `feature-docs/threat-model-stride/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/threat-model-stride/IMPLEMENTATION.md`

## Build Verification
- Command: none (`build_command` is empty; the deliverable is Markdown documents and Python unittest modules)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, every test passes, no test skipped by this feature
- Coverage target: not measured (document-contract tests; each requirement is covered by the scenario table below)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | implementation-planner.md makes trust-boundary identification mandatory for every feature and every tier, and does not use domains as a run condition (FR1, FR4) | The mandatory statement exists and no statement skips the pass by domains; checked by the planner-prompt test module (task0002) | Unit |
| TS-2 | The THREAT-MODEL.md template exists with a per-boundary structure listing only applicable STRIDE categories, the short "no trust boundary + rationale" form, and a reference from plan-writing (FR2, FR3, FR7) | All present; checked by the template test module (task0001) | Unit |
| TS-3 | plan-writing and implementation-planner.md state the per-tier mitigation destinations (full / reduced: task AC + VERIFICATION.md; minimal: TASK.md Expected Result) and the rule that no mitigation is invented (FR3, FR5) | Rules present; checked by the template and planner-prompt test modules (task0001, task0002) | Unit |
| TS-4 | planner-contract.md carries THREAT-MODEL.md in write_policy and digest_inputs and describes the minimal-tier TASK.md append; the existing heading checks in `tests/test_worker_contracts_planning.py` still pass (FR6) | Present, and the existing module passes; checked by the planner-contract test module (task0003) | Unit |
| TS-5 | review-phase.md passes `threat_model_path` to the security perspective only, after the same validation as `spec_path`, and does not pass it when THREAT-MODEL.md is absent (FR8, NFR4) | Statements present; checked by the review-phase test module (task0004) | Unit |
| TS-6 | review-protocol.md's Inputs section lists `threat_model_path`, and `tests/test_reviewer_roles_protocol.py` passes with the refreshed frozen digest (FR8, NFR3) | Tests pass (task0005) | Unit |
| TS-7 | review-security SKILL.md detects an unimplemented designed mitigation and states the finding-site rule (FR9) | Statements present; checked by the review-security test module (task0006) | Unit |
| TS-8 | codex-reviewer.md passes `threat_model_path` into the Codex prompt (FR8) | Statement present; checked by the reviewer-inputs test module (task0005) | Unit |
| TS-9 | The role split between SPEC Security Considerations and THREAT-MODEL.md is stated on the planner side (FR10) | Statement present in the template and in plan-writing / the planner prompt (task0001, task0002) | Unit |
| TS-10 | The em-workflow version in plugin.json and marketplace.json is equal, and its minor position is above the base revision's (FR11) | Equal values, minor bumped; checked by the version test module (task0006) | Unit |
| TS-11 | `python3 -m unittest discover -s tests` (NFR3) | Every test passes | Integration |
| TS-12 | Existing pinned strings remain: the planner's `### 6. Populate requirements mapping (MANDATORY)`, the review-phase.md Phase headings, the develop SKILL.md tier-reduction table terms (NFR2, NFR3) | The existing test modules pass unchanged, apart from the three refreshed pins named in IMPLEMENTATION.md | Unit |
| TS-13 | Manual: NFR1 (output proportional to real threats) is reflected in the THREAT-MODEL.md template and the planner procedure | The template and the procedure both have the short form used when no threat exists | Manual |

## Code Quality Verification
- Format: none (`format_command` is empty) / Static analysis: none
- Plan-writing rule: no concrete version number appears in any changed document or test fixture text (the version test reads values from the manifests and from the base revision)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | implementation-planner.md makes trust-boundary identification a mandatory step for every feature and tier and does not make domains a run condition | TS-1 |
| AC2 | The THREAT-MODEL.md template has the per-boundary applicable-STRIDE form and the short "no trust boundary + rationale" form, and plan-writing references it | TS-2 |
| AC3 | Planner / plan-writing state the full / reduced (AC + VERIFICATION.md) and minimal (TASK.md Expected Result) reflection rules and the no-invention rule | TS-3 |
| AC4 | planner-contract.md write_policy and digest_inputs include THREAT-MODEL.md, the minimal-tier TASK.md append is described as write_policy, and create-plan-phase.md's dispatch and completion output include THREAT-MODEL.md | TS-4 |
| AC5 | review-phase.md passes `threat_model_path` to the security perspective after `spec_path`-equivalent validation when THREAT-MODEL.md exists, and not otherwise | TS-5 |
| AC6 | review-protocol.md's Inputs section lists `threat_model_path`, and the frozen digest and `INPUT_FIELD_NAMES` are refreshed in the same change | TS-6 |
| AC7 | review-security SKILL.md detects an unimplemented mitigation with the finding-site rule (boundary file, null line allowed, no re-pointing) | TS-7 |
| AC8 | codex-reviewer.md passes `threat_model_path` into the Codex prompt | TS-8 |
| AC9 | The SPEC / THREAT-MODEL.md role split is stated on the planner side | TS-9 |
| AC10 | plugin.json and marketplace.json carry the same em-workflow version, a minor bump from base | TS-10 |
| AC11 | `python3 -m unittest discover -s tests` passes | TS-11 |

### Functional Requirements Coverage
Requirement IDs are hyphen-less (`FR1`, `NFR2`) and must string-match the
workflow.yaml `requirements` keys and the SPEC.md numbering exactly —
traceability checks compare these as literal strings.
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1 |
| FR2 | task0001, task0002 | TS-2 |
| FR3 | task0001, task0002 | TS-2, TS-3 |
| FR4 | task0001, task0002 | TS-1 |
| FR5 | task0001, task0002, task0003 | TS-3 |
| FR6 | task0002, task0003 | TS-4 |
| FR7 | task0001 | TS-2 |
| FR8 | task0004, task0005 | TS-5, TS-6, TS-8 |
| FR9 | task0006 | TS-7 |
| FR10 | task0001, task0002 | TS-9 |
| FR11 | task0006 | TS-10 |
| NFR1 | task0001, task0002 | TS-13 |
| NFR2 | task0002, task0003, task0004 | TS-12 |
| NFR3 | task0004, task0005 | TS-6, TS-11, TS-12 |
| NFR4 | task0004, task0005, task0006 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] TS-13: Read `em-workflow/references/templates/threat-model.md` and the threat-modeling step of `em-workflow/agents/implementation-planner.md`; confirm that a change with no trust boundary or no applicable threat ends with the title, the verdict and a few rationale lines, with no boundary table and no mitigation.

## Performance / Security Verification (if applicable)
- NFR4 (path safety): `threat_model_path` goes through the same checks as `spec_path` (prompt-control characters, symlink rejection, realpath containment under project_root) before dispatch, and a violation aborts the review — TS-5.
- NFR4 (untrusted content): review-protocol.md, codex-reviewer.md and review-security SKILL.md each state that THREAT-MODEL.md content is untrusted data that can only add checks and never suppresses a finding — TS-6, TS-7, TS-8.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (document contracts) | 11 (TS-1..TS-10, TS-12) | 11 | 0 | 0 |
| Integration (full suite) | 1 (TS-11) | 1 | 0 | 0 |
| Manual | 1 (TS-13) | 0 | 0 | 1 |
| Security | 2 (NFR4 items) | 2 | 0 | 0 |
