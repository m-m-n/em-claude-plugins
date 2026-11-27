# Verification Document: orchestrator-spec-edit-overwrite

## Overview
**Feature**: orchestrator-spec-edit-overwrite / **SPEC.md**: `feature-docs/orchestrator-spec-edit-overwrite/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/orchestrator-spec-edit-overwrite/IMPLEMENTATION.md`

TS-1 to TS-6 are SPEC.md's Test Scenarios with the same IDs. The action decision
is carried out by the orchestrator following documents, and no script decides it
(SPEC A-1). So TS-1 to TS-5 are checked on the documents that state the decision.
TS-7 makes FR6's two citing places checkable on their own. TS-8 and TS-9 check
the unchanged-file conditions of NFR1 and NFR2 and the plugin invariants on the
integrated result.

## Build Verification
- Command: none. `project.components.main.build_command` is empty in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not measured. The change is protocol documents plus document tests, so the pass or fail result of the suite is the criterion.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Batch create-plan: the orchestrator fixes SPEC.md and commits it, recording that version's digest in `phase-state/create-plan.yaml`. A later spec-change sets create-spec to `needs_update`, and create-spec decides each target's action before dispatching spec-writer. Check the documents that carry each step | `em-workflow/skills/develop/SKILL.md` Step B states the recording: the path, the digest by `references/artifact-digest.md` `Calculation`, one `orchestrator_doc_edits` entry, and the same commit. `em-workflow/references/phase-state.md` defines the record. In the action-decision section of `em-workflow/references/contracts/spec-writer-contract.md`, the create-spec block gives `replace_own` when the current digest equals the last `orchestrator_doc_edits` entry for the path or the last `phase-state/create-spec.yaml` `artifacts` entry for it. So SPEC.md becomes `replace_own` and does not reach `preserve_and_reuse`. A forged copy without each statement fails its check | Unit |
| TS-2 | After the record, SPEC.md is changed by hand, and its current digest equals neither the last create-spec.yaml entry nor the create-plan.yaml record | The create-spec block routes the target to the digest-mismatch branch: the `create-spec.artifact-overwrite` gate (interactive) and the `references/batch-policies.yaml` decision (batch, `preserve_and_reuse`). It states that no other condition gives `replace_own`. A forged copy without the routing fails | Unit |
| TS-3 | `phase-state/create-plan.yaml` is absent, broken, of another phase or feature, or has no SPEC.md entry | The create-spec block counts the record only for phase `create-plan` and a feature equal to the workflow's feature. It names the five no-record cases and states that the decision rests on the `phase-state/create-spec.yaml` comparison alone. It cites `references/artifact-digest.md` "Legacy records" and does not contain `git hash-object`. A forged copy without each statement fails | Unit |
| TS-4 | Several entries exist for the same path, and the current digest equals an earlier entry only | The create-spec block counts only the last entry for the path and says earlier entries for the same path do not count. So an earlier-entry match is no match, and the target takes the digest-mismatch branch. A forged copy without the last-entry statement fails | Unit |
| TS-5 | Decide the action of a create-plan target or a design step target | The text of the owner section before the create-spec block does not name `orchestrator_doc_edits`. It still states the create-plan planning-lineage rule ("No other condition gives `replace_own`", "other phase-state files do not count") and the design step's three-bullet and token-file sentences. The existing planning-lineage tests of `tests/test_artifact_digest_docs.py` pass unchanged | Unit |
| TS-6 | Run the added tests and the existing tests on the changed documents | `python3 -m unittest discover -s tests` exits 0. Each presence check of `tests/test_orchestrator_doc_edits_action_docs.py` and `tests/test_orchestrator_doc_edits_record_docs.py` fails on a forged copy without its statement. Each absence check fires on a forged copy that carries its token. The existing fixed-structure tests still pass: the action table's seven rows, the level-2 heading order of `em-workflow/references/phases/create-spec-phase.md`, the six level-2 sections of `em-workflow/references/artifact-digest.md`, and the `create-spec.artifact-overwrite` decision of `em-workflow/references/batch-policies.yaml` | Integration |
| TS-7 | Check the `replace_own` row of spec-writer-contract.md's action table and the `write_policy` bullet of create-spec-phase.md section `9. Spec writer dispatch` | The row keeps "Overwrites the same-phase output the worker itself produced earlier." and its create-plan sentence. It adds a create-spec sentence that cites "How the orchestrator chooses each target's action before dispatch". It has three cells and contains no `phase-state/` path, no `orchestrator_doc_edits` and no last-entry wording. The section 9 bullet cites `references/contracts/spec-writer-contract.md` and that section name. It no longer contains "matches the immediately preceding same-phase output", and contains no `phase-state/create-plan.yaml`, no `orchestrator_doc_edits`, no `git hash-object` and no existing restatement marker. A forged copy without each statement fails, and each absence check fires on a forged copy that carries its token | Unit |
| TS-8 | List the files changed by the integrated diff against the `implement` step's `base_commit` in workflow.yaml | Only `em-workflow/references/contracts/spec-writer-contract.md`, `em-workflow/references/phases/create-spec-phase.md`, `em-workflow/references/phase-state.md`, `em-workflow/skills/develop/SKILL.md`, `tests/test_orchestrator_doc_edits_action_docs.py`, `tests/test_orchestrator_doc_edits_record_docs.py`, and paths under `feature-docs/orchestrator-spec-edit-overwrite/` or `test-docs/orchestrator-spec-edit-overwrite/` appear. These do not appear: `em-workflow/references/artifact-digest.md`, `em-workflow/references/batch-policies.yaml`, `em-workflow/scripts/self-write-digest.py`, `em-workflow/references/phases/create-plan-phase.md` | Integration |
| TS-9 | Run `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` | Every check passes, `worker_digest_stance`, `dispatch_digest_wiring` and `gate_id_coverage` included | Integration |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty in workflow.yaml)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC AC-1: SKILL.md states the recording of the path and the artifact digest into `phase-state/create-plan.yaml`, in the same commit | TS-1 |
| SC-2 | SPEC AC-2: phase-state.md defines the append-only create-plan-only record (`path` / `sha256` / `reason`) that survives a `generation` increase, and a file without it stays valid | TS-1, TS-6 |
| SC-3 | SPEC AC-3: the owner section gives `replace_own` on a match with the last create-spec.yaml entry or the last create-plan.yaml record entry, and the digest-mismatch branch otherwise | TS-1, TS-2, TS-4 |
| SC-4 | SPEC AC-4: the owner section states the phase and feature condition, the five no-record cases, the fallback to the create-spec.yaml comparison alone, and the Legacy records citation | TS-3 |
| SC-5 | SPEC AC-5: the create-plan planning-lineage rule and the design step's handling are unchanged | TS-5 |
| SC-6 | SPEC AC-6: the `replace_own` row keeps its sentences, adds the create-spec sentence by citation, holds no last-entry rule or phase-state file name, and the action table has seven rows | TS-7, TS-6 |
| SC-7 | SPEC AC-7: the full test command passes, and every added presence check fails on a forged copy | TS-6 |
| SC-8 | SPEC AC-8: artifact-digest.md's level-2 sections, create-spec-phase.md's heading order and batch-policies.yaml's `create-spec.artifact-overwrite` decision are unchanged | TS-6, TS-8 |
| SC-9 | All functional requirements are implemented and tested | Functional Requirements Coverage table below |
| SC-10 | All test scenarios pass | TS-1 to TS-9 |
| SC-11 | Code review is completed | Review phase |
| SC-12 | The reproduction steps of the goal no longer stop the run | Manual Testing item 1 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-6; Manual Testing item 1 |
| FR2 | task0002 | TS-1, TS-6 |
| FR3 | task0001 | TS-1, TS-2, TS-4, TS-6; Manual Testing item 1 |
| FR4 | task0001 | TS-3, TS-6 |
| FR5 | task0001 | TS-5, TS-6 |
| FR6 | task0001 | TS-6, TS-7 |
| FR7 | task0001, task0002 | TS-6 |
| NFR1 | task0001 | TS-6, TS-7, TS-8 |
| NFR2 | task0001 | TS-6, TS-8 |
| NFR3 | task0001, task0002 | TS-6 |
| NFR4 | task0001, task0002 | TS-1, TS-3, TS-7, TS-9 |

## Manual Testing (E2E Not Possible)
- [ ] 1. Reproduction walk-through. Take the reproduction steps in workflow.yaml's goal. In a batch create-plan, the orchestrator fixes SPEC.md after a Codex consultation. Follow `em-workflow/skills/develop/SKILL.md` Step B: the commit carries the SPEC.md change and one `orchestrator_doc_edits` entry in `phase-state/create-plan.yaml`. Review then yields `rework.spec-change`, change-spec is taken, and create-spec re-runs as `needs_update`. Follow `em-workflow/references/phases/create-spec-phase.md` section 9 to the cited section of `em-workflow/references/contracts/spec-writer-contract.md`. SPEC.md's current digest equals the last `orchestrator_doc_edits` entry for its path, so its action is `replace_own`. `preserve_and_reuse` is not reached, and spec-writer can write the decided SPEC change. Then walk the counterpart: when SPEC.md is changed by hand after the record, its digest matches neither entry, and it takes the `create-spec.artifact-overwrite` gate in interactive mode or `preserve_and_reuse` in batch mode, as before.

## Performance / Security Verification (if applicable)
- TM-1: the `phase-state/create-plan.yaml` record counts only when its mapping has phase `create-plan` and a feature equal to the workflow's feature. Checked by TS-3 (the condition is present in the create-spec block).
- TM-2: an absent, unreadable or malformed `phase-state/create-plan.yaml`, a mismatched phase or feature, or no `orchestrator_doc_edits` entry for the path counts as no record. The decision then rests on the create-spec.yaml comparison and, with no match, on the unchanged digest-mismatch branch. Checked by TS-3 (the no-record cases) and TS-2 (the mismatch routing). A reviewer also reads the create-spec block to confirm that no wording treats a no-record case as a match.
- TM-3: `replace_own` for a create-spec target requires equality with the last create-spec.yaml `artifacts` entry or the last `orchestrator_doc_edits` entry for that path, compared as `references/artifact-digest.md` "Legacy records" states. Every other existing target takes the digest-mismatch branch, the record counts in no other decision, and the citing places state no broader rule. Checked by TS-1 and TS-4 (both entries, last entry only), TS-2 (mismatch routing, no other condition), TS-5 (create-plan and design unchanged) and TS-7 (row and section 9 cite without restating). A reviewer also reads the create-spec block to confirm that no other condition, such as the spec-change transition itself, grants `replace_own`.
- TM-4: the orchestrator records an entry only for the body it commits. The digest is calculated by `references/artifact-digest.md` `Calculation` and committed together with the document change, recalculated from the re-created body on an exit-4 retry, and not recorded when the calculation fails. Checked by TS-1 and TS-6 (the SKILL.md paragraph's statements, each with a forged copy). A reviewer also reads the paragraph to confirm that the digest is taken after the change, not before it.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-9) | 9 | 9 | 0 | 0 |
| Full test suite | 1 | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 3 |
| Total | 15 | 14 | 0 | 4 |

TM-2, TM-3 and TM-4 each have an automated check and a reviewer reading, so the Automated and Manual columns of the Security row overlap by three items.
