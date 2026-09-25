# Verification Document: task-id-allocation-ssot

## Overview

**Feature**: task-id-allocation-ssot / **SPEC.md**: `feature-docs/task-id-allocation-ssot/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/task-id-allocation-ssot/IMPLEMENTATION.md`

## Build Verification

- Command: none. `project.components.main.build_command` is empty, and the change has no build artifact.
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Coverage target: not applicable. The change consists of document text, docstrings, comments and version fields. Completeness is measured instead as "every SPEC success criterion maps to at least one passing test or check" (see SPEC.md Compliance below).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Slice implement-phase.md I.2.c, whitespace-normalize it, and check each removed recycling / renumbering phrase | None of the phrases are present. The same matcher detects each phrase in the embedded pre-change I.2.c sample (negative proof). | Unit |
| TS-2 | Check I.2.c for the citation of workflow-patch.md 'Re-planning task-id allocation' and for the own-terminal-event statement | Both are present. Neither matcher fires on the pre-change sample. | Unit |
| TS-3 | Check the third-conjunct anchors, the rewritten rationale and the re-judgment record for all three countermeasures | The four THIRD_CONJUNCT anchors still match. The updated THIRD_CONJUNCT_NARROWING_PHRASE, NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE and the anchor test near line 2276 of tests/test_implement_routeback_gate.py pin the own-id rationale. The re-judgment passage names all three countermeasures. Each new matcher has a negative proof. | Unit |
| TS-4 | Check the old re-scope sentence and its carried-verbatim replacement in I.2.c | The old sentence is absent. The replacement states that the failed id is carried verbatim, that new tasks go above the high-water mark, cites the owning section, and keeps the SPEC.md update path. Negative proof against the pre-change sample. | Unit |
| TS-5 | Check label retention and the stop-guard docstring | 'recycled-task-id carve-out' remains where it appeared before. The retention tests in tests/test_recycled_task_id_consistency.py, tests/test_routeback_reset_scope_consistency.py and tests/test_failed_kind_resume_reentry.py still pass. The queue_stop_guard.py docstring lacks 'a recycled task id left behind by a route-back re-plan'. tests/test_queue_stop_guard.py passes without modification. | Unit |
| TS-6 | Run the existing allocation-rule and citation tests | tests/test_workflow_patch_doc.py and tests/test_replanning_producer_alignment.py pass without modification | Unit |
| TS-7 | Check the validator comment near the replace-all-task-id-reused block | The comment does not claim that `entries` re-declares registered ids, and it describes `carried_task_ids`. tests/test_validate_worker_output.py and its fixtures pass without modification. | Unit |
| TS-8 | Run the version-bump test module | The em-workflow versions in plugin.json and marketplace.json are equal and strictly greater than the largest baseline pinned by the existing tests/*_version_bump.py modules | Unit |
| TS-9 | Run the full suite with `python3 -m unittest discover -s tests` | Every test passes | Integration |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- **Behaviour-invariance check (NFR2; SPEC AC-6, AC-8)**:
  - Files: queue_launch_guard.py, queue_stop_guard.py, queue_failure_net.py and queue_taskstop_net.py under em-workflow/hooks/, plus em-workflow/scripts/validate-worker-output.py.
  - Procedure: take each file's content at `workflow.implement.base_commit` and at the integrated tip. Parse both with the same Python interpreter, remove module, class and function docstrings, and compare the resulting syntax trees. Comments are not part of the tree, so comment-only edits drop out naturally.
  - Expected: identical trees for all five files.
- **Owning-section invariance (SPEC AC-7)**:
  - Diff these four files between `workflow.implement.base_commit` and the integrated tip:
    - em-workflow/references/workflow-patch.md
    - em-workflow/agents/implementation-planner.md
    - em-workflow/references/contracts/planner-contract.md
    - em-workflow/references/phases/create-plan-phase.md
  - Expected: an empty diff for each.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Whitespace-normalized I.2.c contains none of 'recycles every id', 'renumbered task id', 'leaves a recycled id launchable', 'no recycled id can ever inherit' | TS-1 |
| AC-2 | I.2.c cites 'Re-planning task-id allocation' and states that a task's journal terminal events are its own (ids are never re-issued) | TS-2 |
| AC-3 | The third conjunct remains un-narrowed. Its four anchors remain, and its rationale refers to the task's own `merged` event and the launch guard's denial. | TS-3 |
| AC-4 | The re-judgment of `deny_already_merged`, the third conjunct and the failed+pending carve-out is recorded, with own-id reasons | TS-3, plus Manual Testing item 2 |
| AC-5 | The old re-scope sentence is absent. The replacement cites the owning section and keeps the SPEC.md update path. | TS-4, plus Manual Testing item 3 |
| AC-6 | The carve-out label remains, including in skills/develop/SKILL.md. The stop-guard docstring lacks the recycled-id phrase. Hook code is unchanged apart from the docstring. | TS-5, plus the behaviour-invariance check |
| AC-7 | The owning section is unchanged. The planner, planner contract and create-plan phase still cite it without restating the rule. | TS-6, plus the owning-section invariance check |
| AC-8 | The validator comment describes `carried_task_ids`. Executable code is unchanged. | TS-7, plus the behaviour-invariance check |
| AC-9 | plugin.json and marketplace.json carry the same em-workflow version, exactly one patch step above the pre-change version | TS-8, plus a diff of both manifests against `workflow.implement.base_commit` (only the patch component increases by 1) |
| AC-10 | The full suite passes. The I.2.c literals in tests/test_implement_routeback_gate.py are updated, and each new matcher has a negative proof. | TS-9, TS-3 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-2, TS-6, owning-section invariance check |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-1, TS-2 |
| FR4 | task0001 | TS-3, Manual Testing item 2 |
| FR5 | task0001 | TS-4, Manual Testing item 3 |
| FR6 | task0001, task0002 | TS-5 |
| FR7 | task0002 | TS-7 |
| FR8 | task0002 | TS-8 |
| NFR1 | task0001, task0002 | TS-9 |
| NFR2 | task0002 | TS-5, TS-7, behaviour-invariance check |
| NFR3 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-7 (every new matcher carries a negative proof) |
| NFR4 | task0001 | TS-2, TS-6, owning-section invariance check |

## E2E Testing

Not applicable. The project has no E2E framework (`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)

- [ ] 1. Read I.2.a, I.2.c and workflow-patch.md 'Re-planning task-id allocation' side by side. Confirm that no sentence in I.2.c contradicts the owning section or I.2.a, and that the text alone answers whether recycled-task-id inheritance can occur (it cannot).
- [ ] 2. In the I.2.c re-judgment passage, confirm that each of the three countermeasures has a necessity reason that holds without any id reuse.
- [ ] 3. Confirm that the rewritten re-scope passage grants the planner no action beyond the owning section: it does not edit a carried task's body, and new work enters only as new ids. Confirm also that dropping a requirement still routes through the SPEC.md update path.
- [ ] 4. Confirm that the stop-guard docstring and the validator comment read consistently with the owning section, and use the same own-id wording as I.2.c.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Integration test scenario (TS-9) | 1 | 1 | 0 | 0 |
| Code quality checks (behaviour invariance, owning-section invariance) | 2 | 2 | 0 | 0 |
| SPEC success criteria (AC-1 to AC-10) | 10 | 10 | 0 | 0 |
| Manual reading checks | 4 | 0 | 0 | 4 |
