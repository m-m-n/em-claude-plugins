# Verification Document: plan-version-bump-per-commit

## Overview
**Feature**: plan-version-bump-per-commit / **SPEC.md**: `feature-docs/plan-version-bump-per-commit/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/plan-version-bump-per-commit/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change is Markdown documents plus Python tests)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: not measured (the tests check document content; there is no production code under test)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | plan-writing SKILL.md's Plugin Version Handling section states the non-exempt per-commit bump rule: same-commit patch bump, marketplace alignment, advance on each commit in one task, strictly greater than the preceding HEAD; plus the newly-added-plugin and unversioned-entry exclusion | Stated; the tests in `tests/test_plan_version_plan_writing.py` pass | Unit |
| TS-2 | plan-writing SKILL.md prohibits keep-unchanged instructions and requires plugin-changing tasks to list `plugin.json` (and `marketplace.json` when versioned) in `files`; the checklist carries matching items; the negative check rejects a permissive sample | Stated; the tests in `tests/test_plan_version_plan_writing.py` pass | Unit |
| TS-3 | plan-writing SKILL.md defines exempt / non-exempt by `.github/workflows/plugin-version-bump.yml` and states that exempt plans instruct no version change (minor / major: position only, no value) | Stated; the tests in `tests/test_plan_version_plan_writing.py` pass | Unit |
| TS-4 | rework-planner.md, rework-planner-contract.md and rework-task-synthesis.md cite the plan-writing Plugin Version Handling section without restating it, and contain no permission for rework tasks to keep the version | Cited; the tests in `tests/test_plan_version_rework.py` pass | Unit |
| TS-5 | planner-contract.md and rework-planner-contract.md define the `plugin_versioning` input (mandatory, untrusted) and its `value_inputs` membership; create-plan-phase.md and the rework-planner dispatch procedure state that it is resolved, passed and re-resolved on return; implementation-planner.md and rework-planner.md name it | Stated; the tests in `tests/test_plan_version_planner_dispatch.py` and `tests/test_plan_version_rework.py` pass | Unit |
| TS-6 | worktree-task-workflow SKILL.md's parent-side adoption protocol states the non-exempt rule: adoption commit above both the parent-side and task-side HEAD values, re-implementation commit above the post-adoption HEAD value, marketplace alignment, no extra step when exempt | Stated; the tests in `tests/test_plan_version_worktree_conflict.py` pass | Unit |
| TS-7 | Run `python3 -m unittest discover -s tests` on the integrated branch | Exit code 0 | Integration |
| TS-8 | (Verification-derived from NFR4) Between `workflow.implement.base_commit` and the integration branch tip, no `version` value changes in `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`, and the feature's plan documents (IMPLEMENTATION.md, VERIFICATION.md, tasks/) contain no concrete version value | No change; no concrete value found | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Document rules: the new rule text contains no fenced code block (checked by TS-1 / TS-6) and no concrete version value (TS-1, TS-6, TS-8)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every row's tests pass under TS-7 |
| SC-2 | All test scenarios pass | TS-1 to TS-8 |
| SC-3 | AC1 (FR1, FR2) satisfied | TS-1, TS-2 |
| SC-4 | AC2 (FR3) satisfied | TS-3 |
| SC-5 | AC3 (FR4) satisfied | TS-4 |
| SC-6 | AC4 (FR5) satisfied | TS-5 |
| SC-7 | AC5 (FR6) satisfied | TS-6 |
| SC-8 | AC6 (FR7, NFR3) satisfied | TS-7 |
| SC-9 | Goal completion: the reproduction steps no longer produce the failure, and a regression test exists | Manual reproduction walk-through below; TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0004 | TS-4 |
| FR5 | task0003, task0004 | TS-5 |
| FR6 | task0002 | TS-6 |
| FR7 | task0001, task0002, task0003, task0004 | TS-7 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-4, TS-5, TS-6 (citation instead of restatement) |
| NFR2 | task0001, task0002 | TS-1, TS-6 (no code, no concrete values in the new rules) |
| NFR3 | task0001, task0002, task0003, task0004 | TS-7 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction walk-through (goal's reproduction steps): for a hypothetical non-exempt repository with two tasks touching the same plugin, applying the new plan-writing section yields no "only the first task bumps" instruction, a version bump on every plugin-changing commit, and `plugin.json` (plus `marketplace.json` when versioned) in both tasks' `files`; for a version-line merge conflict, the worktree-task-workflow exception yields an adoption-commit value above both sides.
- [ ] Exempt walk-through: applying the new section to this repository (which has `.github/workflows/plugin-version-bump.yml`) yields no version-change instruction, consistent with the repository's own version rule.
- [ ] Citation integrity after merge: the headings `## Plugin Version Handling` (plan-writing SKILL.md) and `### plugin_versioning (dispatch-resolved value)` (planner-contract.md) exist, and every document that cites them uses the same path and heading text.
- [ ] Readability (NFR2): the new rules read as unambiguous behavior descriptions.

## Performance / Security Verification (if applicable)
- Performance: not applicable (no runtime component)
- TM-1: `plugin_versioning` is classified as untrusted input under worker-envelope.md's Untrusted-Input Handling and limited to the exemption boolean, plugin directory paths, plugin names and the per-plugin marketplace flag — checked by the untrusted-classification assertions in `tests/test_plan_version_planner_dispatch.py` (task0003 AC-4) and `tests/test_plan_version_rework.py` (task0004 AC-4), run under TS-7

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Integration (TS-7, TS-8) | 2 | 2 | 0 | 0 |
| Manual | 4 | 0 | 0 | 4 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 13 | 9 | 0 | 4 |
