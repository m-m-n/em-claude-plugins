# Verification Document: rework-replan-artifact-digest

## Overview
**Feature**: rework-replan-artifact-digest / **SPEC.md**: `feature-docs/rework-replan-artifact-digest/SPEC.md` / **IMPLEMENTATION.md**: not produced (tier `reduced`, one task, no file declared by more than one task)

TS-1 to TS-6 are SPEC.md's Test Scenarios with the same IDs. TS-7 and TS-8 make the unchanged-file conditions of NFR1 and NFR2 and the dispatch-site wiring checkable on the integrated result. TS-9 and TS-10 were added by review round 1 rework (task0002): they check that every create-plan dispatch passes the actions chosen by the action-decision rule, with no plan-document action fixed elsewhere.

## Build Verification
- Command: none. `project.components.main.build_command` is empty in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not measured. The change is procedure documents plus document tests, so the pass or fail result of the suite is the criterion.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Cut out the section "How the orchestrator chooses each target's action before dispatch" of `em-workflow/references/contracts/spec-writer-contract.md` by its heading, normalize whitespace, and check the create-plan statement | The section names `phase-state/create-plan.yaml` and `phase-state/rework.yaml`, the last-entry-per-path rule, and `replace_own` for create-plan. Its scope covers the section 4 planner dispatch, re-planning after a spec-change transition or a tier upgrade included, and the section 13 final-path correction and feature-docs correction dispatches. A forged section without `phase-state/rework.yaml` fails the matcher | Unit |
| TS-2 | In the same section, check the routing of a create-plan target that matches neither entry | The target is routed to the `create-plan.artifact-overwrite` gate (interactive) and the `references/batch-policies.yaml` decision (batch). A forged section without that routing fails | Unit |
| TS-3 | In the same section, check the rework.yaml read conditions and the Legacy records citation | The section states phase `rework` and a feature equal to the workflow's feature. It states that an absent, unreadable or malformed file, a mismatched phase or feature, or no `artifacts` entry for the path counts as no record. It cites `references/artifact-digest.md` "Legacy records" for rework.yaml values and does not contain `git hash-object`. A forged section without each statement fails | Unit |
| TS-4 | In `em-workflow/references/phases/create-plan-phase.md`, check "4. Planner dispatch", the part of "13. Final-path correction dispatch" before its subsection, and "Feature-docs correction dispatch" | Each cites `references/contracts/spec-writer-contract.md` and "How the orchestrator chooses each target's action before dispatch". None contains `git hash-object`, an existing restatement marker or `phase-state/rework.yaml`. A forged slice without the citation fails, and each absence matcher fires on a forged slice that holds its token | Unit |
| TS-5 | Run the existing tests `TestOwnerDocumentStructure`, `TestDispatchSitesRegistry`, `TestLegacyRecords` and `test_rework_dispatch_input_paragraph_records_into_rework_yaml` in `tests/test_artifact_digest_docs.py`, and `tests/test_spec_change_replan_authorization.py`, unchanged | All pass | Integration |
| TS-6 | Run the full test command of Test Verification | Exit code 0 | Integration |
| TS-7 | List the files changed by the integrated diff against the `implement` step's `base_commit` in workflow.yaml | Only `em-workflow/references/contracts/spec-writer-contract.md`, `em-workflow/references/phases/create-plan-phase.md`, `em-workflow/references/contracts/planner-contract.md`, `em-workflow/agents/implementation-planner.md`, `tests/test_artifact_digest_docs.py`, and paths under `feature-docs/rework-replan-artifact-digest/` or `test-docs/rework-replan-artifact-digest/` appear. `em-workflow/references/artifact-digest.md`, `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/phase-state.md` and `em-workflow/references/batch-policies.yaml` do not appear | Integration |
| TS-8 | Run `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` | Every check passes, `dispatch_digest_wiring` included | Integration |
| TS-9 | In `em-workflow/references/contracts/planner-contract.md`, check the `write_policy` paragraph of "Additional input: `planning_inputs`" and the **write_policy** bullets of "path_correction (dispatch-resolved value)" and "feature_docs_correction (dispatch-resolved value)"; in `em-workflow/agents/implementation-planner.md`, check the own-documents bullet of "Feature-docs correction" | Each planner-contract.md slice cites `references/contracts/spec-writer-contract.md` and "How the orchestrator chooses each target's action before dispatch" for the plan-document actions and contains no "has action `replace_own`". The `planning_inputs` paragraph lists each existing task plan under `tasks/` in `write_policy.targets` and keeps new task plans under `allowed_write_roots` (`tasks/`). The feature-docs bullet still says "`allowed_write_roots` is empty" and keeps the `amend_other_feature` targets. The agent bullet edits IMPLEMENTATION.md or VERIFICATION.md only under a target whose action permits writing and returns `status: blocked` naming the path under `preserve`. A forged slice without each statement fails, and the absence matcher fires on a forged bullet that says "has action `replace_own`" | Unit |
| TS-10 | In `em-workflow/references/phases/create-plan-phase.md`, check the `write_policy` bullet of "4. Planner dispatch", the **Dispatch.** paragraph of "13. Final-path correction dispatch" and the dispatch paragraph of "Feature-docs correction dispatch"; in `em-workflow/references/contracts/spec-writer-contract.md`, check the `replace_own` row of the action table | The section 4 bullet names each existing task plan under `tasks/` as a target. The **Dispatch.** paragraph states that each target carries the action chosen in **Pre-dispatch.**. The feature-docs dispatch paragraph carries the empty `allowed_write_roots` of planner-contract.md's `### feature_docs_correction (dispatch-resolved value)`. None of these slices contains `git hash-object`, a restatement marker or `phase-state/rework.yaml`. The `replace_own` row keeps "Overwrites the same-phase output the worker itself produced earlier." and cites "How the orchestrator chooses each target's action before dispatch", and the action table has seven rows. A forged slice without each statement fails, and each absence matcher fires on a forged slice that holds its token | Unit |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty in workflow.yaml)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC AC-1: the action-decision section gives `replace_own` for a match with the last entry for the path in `phase-state/create-plan.yaml` or `phase-state/rework.yaml` | TS-1 |
| SC-2 | SPEC AC-2: a create-plan target matching neither entry takes the `create-plan.artifact-overwrite` gate / `references/batch-policies.yaml` decision | TS-2 |
| SC-3 | SPEC AC-3: the rework.yaml read conditions and Legacy records for rework.yaml values are stated | TS-3 |
| SC-4 | SPEC AC-4: create-plan-phase.md sections 4 and 13, and the feature-docs correction subsection, cite the owner without `git hash-object` and without restatement markers | TS-4 |
| SC-5 | SPEC AC-5: artifact-digest.md keeps its six level-2 sections and six registry rows, and every NFR2 pinned statement is present | TS-5, TS-7 |
| SC-6 | SPEC AC-6: new tests cover SPEC AC-1 to AC-4 with forged-text cases, and the full test command passes | TS-1 to TS-4, TS-6 |
| SC-7 | All functional requirements are implemented and tested | Functional Requirements Coverage table below |
| SC-8 | All test scenarios pass | TS-1 to TS-10 |
| SC-9 | Code review is completed | Review phase |
| SC-10 | The reproduction steps of the goal no longer stop the run | Manual Testing item 1 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-10; Manual Testing item 1 |
| FR2 | task0001 | TS-2; Manual Testing item 1 |
| FR3 | task0001, task0002 | TS-1, TS-4, TS-9, TS-10 |
| FR4 | task0001, task0002 | TS-4, TS-9, TS-10 |
| FR5 | task0001 | TS-3 |
| FR6 | task0001 | TS-3 |
| FR7 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-9, TS-10 |
| NFR1 | task0001, task0002 | TS-5, TS-7, TS-8 |
| NFR2 | task0001, task0002 | TS-5, TS-7 |
| NFR3 | task0001, task0002 | TS-4, TS-10 |
| NFR4 | task0001, task0002 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] 1. Reproduction walk-through. Take the reproduction steps in workflow.yaml's goal: rework-planner rewrote VERIFICATION.md during a verify rework (recorded in `phase-state/rework.yaml`), the classification gate chose `spec_gap`, the spec-change transition ran, and create-spec was re-run. Follow `em-workflow/references/phases/create-plan-phase.md` section 4 to the cited section of `em-workflow/references/contracts/spec-writer-contract.md`. VERIFICATION.md's current digest equals the last rework.yaml entry for its path, so its action is `replace_own`. The `create-plan.artifact-overwrite` gate and the batch policy are not reached, and the planner can update VERIFICATION.md to the revised SPEC. Then walk the counterpart: when VERIFICATION.md was edited after the rework write, its digest matches neither last entry, and it takes the gate in interactive mode or the batch policy (`preserve_and_reuse`) in batch mode, as before.

## Performance / Security Verification (if applicable)
- TM-1: a rework.yaml record counts only when its mapping has phase `rework` and a feature equal to the workflow's feature. Checked by TS-3 (the phase and feature condition is present in the owner section).
- TM-2: an absent, unreadable or malformed rework.yaml, a mismatched phase or feature, or no `artifacts` entry for the path counts as no record, and the decision falls back to the create-plan.yaml comparison and then to the unchanged mismatch branch. Checked by TS-3 (the no-record cases are present) and TS-2 (the mismatch routing is present). A reviewer also reads the edited section to confirm that no wording treats a no-record case as a match.
- TM-3: `replace_own` for a create-plan target requires equality with the last `artifacts` entry for that path in one of the two files, compared as `references/artifact-digest.md` "Legacy records" states; every other existing target takes the unchanged mismatch branch. Checked by TS-1 (both files and the last-entry rule), TS-2 (the mismatch routing), TS-3 (the Legacy records citation and no `git hash-object`) and TS-5 (Legacy records is unchanged). A reviewer also reads the edited section to confirm that no other condition, such as the spec-change transition itself, grants `replace_own`.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-10) | 10 | 10 | 0 | 0 |
| Full test suite | 1 | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 2 |
| Total | 15 | 14 | 0 | 3 |

TM-2 and TM-3 each have an automated check and a reviewer reading, so the Automated and Manual columns of the Security row overlap by two items.
