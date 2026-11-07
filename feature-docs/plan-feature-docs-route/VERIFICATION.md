# Verification Document: plan-feature-docs-route

## Overview
**Feature**: plan-feature-docs-route / **SPEC.md**: `feature-docs/plan-feature-docs-route/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/plan-feature-docs-route/IMPLEMENTATION.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty; Python sources and Markdown need no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors
- Coverage target: not measured (the project has no coverage tool; NFR3 limits tests to the standard-library unittest)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A replace_planning patch whose task `files` holds `feature-docs/call-end-history/THREAT-MODEL.md` | Rejected with exactly one `plan-task-feature-docs` error whose message holds the task id and the path | Unit |
| TS-2 | Path forms `./feature-docs/x`, `feature-docs\x\y.md`, `feature-docs//x`, `feature-docs-archive/x`, `src/feature-docs/x` in a replace_planning entry | The first three are rejected; `feature-docs-archive/x` and `src/feature-docs/x` pass | Unit |
| TS-3 | An append_rework patch with a feature-docs path | `rework-task-feature-docs` judgment unchanged; `plan-task-feature-docs` never appears | Unit |
| TS-4 | A re-planning patch whose `carried_task_ids` task has a feature-docs path in `files` | No `plan-task-feature-docs` error | Unit |
| TS-5 | Document content tests for plan-writing SKILL.md, implementation-planner.md, planner-contract.md, create-plan-phase.md and the implementer's two documents | Each states the decided rules (Feature-docs Files rule and its citation, two-stage route, scope rule, digest_inputs and self-write overlap, grant, fix recording, declared change set input); the implementer's "Never modify `feature-docs/**`" text is still present | Unit (document) |
| TS-6 | Entry judgment on a workflow.yaml whose failed task's `files` holds another feature's THREAT-MODEL.md | `dispatch`; targets collected over every unmerged task; a path present at the base commit is still a target | Unit (script) |
| TS-7 | Entry judgment when `implement` is not failed, when a task is in flight, and when only merged tasks hold feature-docs paths | Never `dispatch` (`none` for the first and third, `blocked` naming the condition for in-flight) | Unit (script) |
| TS-8 | Applying a validated correction patch | The target's `files` loses the feature-docs paths and `notes` is cleared; merged task records unchanged; Step A.6 documents `implement` and the target task back to `pending` | Unit (validator) + Unit (document) |
| TS-9 | Malformed inputs to the validator and the entry script | Reported as errors (validator) or exit 2 with a stderr message and no traceback (script); never an exception | Unit |
| TS-10 | (planner-added) Validator checks of the other-feature document route: scope rule, `amend_other_feature` admission, request result, fix declaration, phase-state fix record | Each out-of-rule case yields its code (`other-feature-doc-scope`, `other-feature-doc-request`, `other-feature-doc-fix`); each in-rule case passes | Unit (validator) |
| TS-11 | (planner-added) `amend_other_feature` in the action model: spec-writer-contract row, worker-envelope self-write row, `self-write-digest.py` identification | `modified` under the action is a self-write; `created` and `deleted` are not; an unknown action is still rejected; no action-model document says "six actions" | Unit (document + script) |
| TS-12 | (planner-added) Document tests for develop Step A.6, create-plan-phase.md section 13's feature-docs correction subsection and workflow-patch.md `## Feature-docs correction` | Step A.6 runs the feature-docs judgment before the final-path judgment, states the restoration split and adds no gate or question; the subsection and the patch section state their contracts; existing pins hold | Unit (document) |

## Code Quality Verification
- Format: none (workflow.yaml `format_command` is empty)
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` run from the repository root reports no finding (its existing test module also runs in the suite)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | plan-writing states the Feature-docs Files rule and implementation-planner cites it | TS-5 |
| AC2 | replace_planning `files` with feature-docs paths are rejected with the new code, path forms handled, append rule unchanged, the old test's expectation inverted | TS-1, TS-2, TS-3 |
| AC3 | Carried tasks with feature-docs paths are not rejected by the new code | TS-4 |
| AC4 | planner-contract states declaration, two stages, the new grant, the scope rule (with the out-of-scope list), digest_inputs and the self-write overlap | TS-5, TS-10, TS-11 |
| AC5 | create-plan-phase.md section 12 includes the fix declarations as an input | TS-5 |
| AC6 | Entry judgment returns `dispatch` with the right targets, ignores base-commit presence, and never dispatches when not failed or in flight | TS-6, TS-7 |
| AC7 | Restoration sets `implement` and targets to `pending`, `failed_kind` null, `notes` cleared, `routeback_failed_journal_line` recorded; merged tasks unchanged | TS-8, TS-12 |
| AC8 | The implementer's "Never modify `feature-docs/**`" text remains | TS-5 |
| AC9 | The full suite passes | `python3 -m unittest discover -s tests` exits 0 |

### Functional Requirements Coverage
Requirement IDs are hyphen-less (`FR1`, `NFR2`) and must string-match the
workflow.yaml `requirements` keys and the SPEC.md numbering exactly —
traceability checks compare these as literal strings.
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-5 |
| FR2 | task0004 | TS-1, TS-2, TS-3, TS-4 |
| FR3 | task0001, task0002, task0005, task0009 | TS-5, TS-10 |
| FR4 | task0001, task0002, task0003, task0005, task0009 | TS-5, TS-10, TS-11 |
| FR5 | task0002, task0005, task0009 | TS-5, TS-10 |
| FR6 | task0002, task0003, task0005, task0009 | TS-5, TS-11 |
| FR7 | task0005, task0009 | TS-5, TS-10 |
| FR8 | task0001, task0002, task0006, task0007, task0008, task0010 | TS-6, TS-7, TS-12 |
| FR9 | task0006, task0007, task0008, task0010 | TS-6, TS-7, TS-8, TS-12 |
| FR10 | task0001 | TS-5 |
| NFR1 | task0008, task0009 | TS-12 (no new `gate_id` or question stated and asserted) |
| NFR2 | task0004, task0005, task0006 | TS-9 |
| NFR3 | task0001 to task0010 | TS-9; every new test module imports only the standard library and unittest (checked in review) |
| NFR4 | task0001, task0002, task0003, task0007, task0009 | TS-5 (citations present, rule wording absent from citing documents) |
| NFR5 | task0001, task0002 | TS-5 (untrusted-input statement); doc redaction enforced by the existing hook on every feature-docs write |
| NFR6 | none (no task changes a version) | Manual item 1 below |

## E2E Testing
Not applicable: the project has no E2E framework (`e2e_test_command` is
empty), and the feature has no user interface.

## Manual Testing (E2E Not Possible)
- [ ] 1. NFR6: the integrated diff against `implement.base_commit` changes neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json`.
- [ ] 2. Cross-document consistency: read develop Step A.6, create-plan-phase.md section 13's feature-docs correction subsection, workflow-patch.md `## Feature-docs correction` and planner-contract.md `### feature_docs_correction (dispatch-resolved value)` together, and confirm they use the same names (`feature-docs-entry.py`, `targets`, `final_path_remaining`, `feature_docs_removals`, `planning_inputs.feature_docs_correction`) and the same order and restoration split as IMPLEMENTATION.md D6 to D9.
- [ ] 3. Cross-document consistency of the other-feature route: planner-contract.md `## Other-feature documents`, spec-writer-contract.md's `amend_other_feature` row, create-plan-phase.md sections 4, 8 and 12 and phase-state.md use the same payload keys, codes and record name as IMPLEMENTATION.md D2 to D5.

## Performance / Security Verification (if applicable)
- TM-1: scope-enforced grants — automated: `tests/test_other_feature_docs_validator.py` rejects every out-of-scope path in requests, fixes and `amend_other_feature` targets, and the target on any dispatch other than an implementation-planner create-plan dispatch, with `other-feature-doc-scope`; document tests assert the scope rule in planner-contract.md, the action row in spec-writer-contract.md and the grant rule in create-plan-phase.md section 4.
- TM-2: declared fixes equal written grants and are recorded — automated: `tests/test_other_feature_docs_validator.py` rejects a written grant without a fix, a fix without a write, and a malformed phase-state record with `other-feature-doc-fix`; document tests assert section 8's coverage and recording sentences and section 12's fourth input.
- TM-3: other-feature document content treated as untrusted — automated: document tests assert the untrusted-input statement and its citation in implementation-planner.md and planner-contract.md.
- TM-4: removal patch conditions — automated: `tests/test_feature_docs_removal_validator.py` produces each `feature-docs-removal-*` code from its failing case, accepts a `failed` target, rejects an `in_progress` task, and shows that the application changes only the named path and `notes`; document tests assert the conditions in workflow-patch.md `## Feature-docs correction`.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 12 | 0 | 0 |
| Code quality (plugin invariants) | 1 | 1 | 0 | 0 |
| Success criteria (AC1 to AC9) | 9 | 9 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Manual | 3 | 0 | 0 | 3 |
| Total | 29 | 26 | 0 | 3 |
