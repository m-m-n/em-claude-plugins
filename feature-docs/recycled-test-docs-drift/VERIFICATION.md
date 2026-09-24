# Verification Document: recycled-test-docs-drift

## Overview
**Feature**: recycled-test-docs-drift / **SPEC.md**: `feature-docs/recycled-test-docs-drift/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, single task, no file shared between tasks)

Scope of the change: the two record files `test-docs/recycled-task-id-contract/task0001.tests.yaml` and `test-docs/recycled-task-id-contract/task0002.tests.yaml`. No code and no test changes (NFR1, NFR2), so every check below is an inspection (YAML read, string search, git diff) or the existing suite.

"Base" below means the feature's base commit (workflow.implement.base_commit). The workflow-generated paths `feature-docs/recycled-test-docs-drift/**` and `test-docs/recycled-test-docs-drift/**` are part of the declared change set and are excluded from every "only these files changed" check.

## Build Verification
- Command: none (project.components.main.build_command is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run at the repository root of the integration worktree)
- Expected: finishes with 0 failures and 0 errors
- Coverage target: not applicable (no code is changed)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Load task0002.tests.yaml and task0001.tests.yaml as YAML; read acceptance_tests AC-4 of task0002 and the key set of every acceptance_tests entry in both files | task0002 AC-4 red_confirmed is false; its tests list is empty and its red_reason is unchanged from base; every entry in both files has tests, red_confirmed and red_reason | Inspection |
| TS-2 | Search task0001.tests.yaml for the string "All four hooks"; extract the quoted span from AC-3 red_reason, normalize whitespace, and search for it in whitespace-normalized em-workflow/references/implement-phase.md | 0 matches for "All four hooks"; the quoted span is found in implement-phase.md | Inspection |
| TS-3 | Read task0001.tests.yaml AC-6 tests; search tests/test_hook_classification_pin.py for each of test_bash_guard_reads_workflow_yaml_but_not_task_status, test_bare_workflow_yaml_mention_without_status_accessor_is_false, test_removing_the_status_carveout_flips_observation_to_false | AC-6 tests holds exactly 7 identifiers (the 4 present at base plus the 3 above as test_hook_classification_pin.TestObserveHookSource.method); each method name is found exactly once | Inspection |
| TS-4 | Read task0001.tests.yaml AC-6 red_reason; run git diff between base and the integrated tree for tests/test_hook_classification_pin.py | red_reason states it is a re-observation made in this feature, names 48386b9^ and what was reverted, and gives each of the 3 tests' observed outcome by name — or states explicitly that their red is unobserved; git diff for the test file is empty | Inspection |
| TS-5 | Read task0001.tests.yaml AC-7 | red_confirmed is false; red_reason contains 1493 (1452 + 41, at task0001 implementation time) and 1506 (integration after the review round 1 auto-fix), each with when it was taken, and the reason for false; check items (2) to (4) present at base are still there | Inspection |
| TS-6 | Read the notes of task0001.tests.yaml against AC-6 red_reason and AC-7 | No universal statement (e.g. "the red of every AC was re-confirmed") contradicts the AC-6 re-observation record or AC-7 red_confirmed false | Inspection |
| TS-7 | git diff --stat between base and the integrated tree, excluding the two workflow-generated paths above; git diff of the two record files; YAML load of both files; the suite command above | Changed files are exactly the 2 record files; no hunk touches task0001 AC-1/AC-2/AC-4/AC-5, task0002 AC-1/AC-2/AC-3/AC-5, or task0003.tests.yaml; nothing under em-workflow/ or tests/ changed and no test file was added; both files load as YAML; the suite ends with 0 failures | Inspection + existing suite |

## Code Quality Verification
- Format: none (project.components.main.format_command is empty)
- Static analysis: none; YAML validity is checked in TS-1 and TS-7

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR6 are all reflected | TS-1 to TS-6 |
| SC-2 | SPEC AC-1 to AC-7 are satisfied | TS-1 to TS-7 |
| SC-3 | TS-1 to TS-7 all pass | This document's scenario table |
| SC-4 | `python3 -m unittest discover -s tests` ends with 0 failures | TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-6 |
| NFR1 | task0001 | TS-7 (git diff scope, no change under em-workflow/ or tests/) |
| NFR2 | task0001 | TS-7 (no test file added) |
| NFR3 | task0001 | TS-7 (no hunk in untouched entries or task0003.tests.yaml) |
| NFR4 | task0001 | TS-7 (YAML load of both files, suite ends with 0 failures) |

## Manual Testing (E2E Not Possible)
- None. TS-6 is a reading-based inspection performed by the verifier; no human-only judgment is required.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Inspection scenarios (TS-1 to TS-7) | 7 | 7 (TS-6 by verifier reading) | 0 | 0 |
| Existing suite | 1 | 1 | 0 | 0 |
| Total | 8 | 8 | 0 | 0 |
