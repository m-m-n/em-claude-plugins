# Verification Document: rework-recheck-before-patch-write

## Overview
**Feature**: rework-recheck-before-patch-write / **SPEC.md**: `feature-docs/rework-recheck-before-patch-write/SPEC.md` / **IMPLEMENTATION.md**: none (a single task with no shared file; not written at the reduced tier)

The task plan is `feature-docs/rework-recheck-before-patch-write/tasks/task0001.md`.
The scenarios below are the ones SPEC.md "Test Scenarios" gives; this document
cites them by ID and does not copy them.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change
  is Markdown and a Python test with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Focused command: `python3 -m unittest tests.test_recheck_dispatch_sites_docs`
- Expected: exit code 0, no failures or errors
- Coverage target: no coverage tool is configured. The target is scenario
  coverage: TS-1 to TS-4 below are present and pass.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The order probe on the real rework section 10 "Return-time digest" paragraph | The probe finds validation, then the recheck, then the application; no defect | Unit (document probe) |
| TS-2 | The forged control: the base-revision paragraph, with the recheck after "validates and applies" | The order probe fires with an application-order defect | Unit (forged-text control) |
| TS-3 | The full suite, including the unchanged design-step-5 and create-plan-section-8 site checks and `tests/test_return_time_recheck_docs.py` | All tests pass | Unit / Integration (whole suite) |
| TS-4 | Section 10's numbered steps 1-4 of review-sourced rework | Items 1-4 exist in order with unchanged meaning; a forged inserted step fires | Unit (document probe) |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Change set: the integration diff against `workflow.implement.base_commit`
  touches only `em-workflow/references/rework-task-synthesis.md`,
  `tests/test_recheck_dispatch_sites_docs.py`, the task's
  `test-docs/rework-recheck-before-patch-write/task0001.tests.yaml`, and the
  workflow-generated files under `feature-docs/rework-recheck-before-patch-write/`
- Version files: the integration diff touches neither
  `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`,
  `plugin-dev/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json`
  (NFR4)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | In the Return-time digest paragraph, the first "return-time recheck" follows the step 3 validation wording and the rule-1 compare/stale sentence, and precedes the first mention of the patch application | TS-1 (task0001 AC-1) |
| AC-2 | The paragraph states that the patch is applied only after a passing recheck, so a stale recheck reaches no workflow.yaml write or commit from the patch | TS-1 (task0001 AC-2, the application-sentence probe and its forged control) |
| AC-3 | The existing `REWORK_SITE` checks pass on the reworded paragraph | TS-3 (task0001 AC-4) |
| AC-4 | Section 10's numbered steps 1-4 keep their numbers; the review-phase.md and develop SKILL.md citations resolve to the same steps | TS-4 (task0001 AC-5) |
| AC-5 | The new order probe passes on the real document and fires on the base-revision control; the full suite passes | TS-1, TS-2, TS-3 |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-3 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-1, TS-2 |
| NFR1 | task0001 | TS-1, TS-2 (naming and standard-library use of the new tests) |
| NFR2 | task0001 | TS-1, TS-2 (paragraph slices and whitespace-insensitive token positions) |
| NFR3 | task0001 | TS-3 |
| NFR4 | task0001 | Code Quality Verification, version files check (no TS ID in SPEC.md) |

## Manual Testing (E2E Not Possible)
- [ ] The reworded Return-time digest paragraph reads as one coherent ordering
      statement: validation (rules 1-14) -> return-time recheck -> application
      (rule 15 write, rule 16 commits), with the recording sentence after the
      recheck. It does not order the recording write and the patch write
      against each other.
- [ ] `em-workflow/references/workflow-patch.md`,
      `em-workflow/references/contracts/worker-envelope.md`,
      `em-workflow/references/phases/create-plan-phase.md`,
      `em-workflow/references/review-phase.md` and
      `em-workflow/skills/develop/SKILL.md` are unchanged in the integration
      diff (SPEC.md, Unchanged Documents).

## Performance / Security Verification (if applicable)
- TM-1: the return-time recheck precedes step 3's application (rule 15 Write to
  workflow.yaml, rule 16 R2 commits), and the paragraph states that the patch
  is applied only after a passing recheck. Checked by:
  - TS-1: the order probe and the application-sentence probe pass on the real
    paragraph;
  - TS-2: the base-revision control fires;
  - the task0001 forged copy with the application sentence moved before the
    recheck fires.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-4) | 4 | 4 | 0 | 0 |
| Success criteria (AC-1 to AC-5, SC-1, SC-2) | 7 | 7 | 0 | 0 |
| Code quality / change set (change set, version files) | 2 | 2 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
| Performance / Security (TM-1) | 1 | 1 | 0 | 0 |
| **Total** | 16 | 14 | 0 | 2 |
