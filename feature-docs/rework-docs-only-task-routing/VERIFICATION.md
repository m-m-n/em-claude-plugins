# Verification Document: rework-docs-only-task-routing

## Overview
**Feature**: rework-docs-only-task-routing / **SPEC.md**: `feature-docs/rework-docs-only-task-routing/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/rework-docs-only-task-routing/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, every test passes, no existing test modified except intended updates (AC9)
- Coverage target: not measured (no coverage tool configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Docs-only round fixture (scenario IDs renamed from the hyphen-less form to the hyphenated form, existing `tasks/task0001.md` and `tasks/task0003.md` rewritten) under `--dry-run-apply` | Exit 0; after in-memory application `implement` is completed, `verify` is pending, no task is added, old test references are removed and the new IDs are present | Unit |
| TS-2 | Rework-planner result whose task `files` are `feature-docs/**` only | Rejected (exit 1, code `rework-task-feature-docs`) | Unit |
| TS-3 | Rework-planner result whose task `files` mix code and `feature-docs/**` | Rejected (exit 1, code `rework-task-feature-docs`) | Unit |
| TS-4 | Rework-planner result whose task `files` are code only | Accepted (exit 0) | Unit |
| TS-5 | `append_rework` patch with empty entries that returns `implement` to `pending` | Rejected (exit 1, code `docs-only-implement-reset`) | Unit |
| TS-6 | Tests replacement whose `expected.tests_contains` is not satisfied by the current `tests` | Rejected with `expected-mismatch` only | Unit |
| TS-7 | Mixed round listing a renamed ID in `covered_by_existing` | Accepted with a declared `scenario_renames` pair; rejected (code `rework-index`) without it | Unit |
| TS-8 | Doc test for `rework-task-synthesis.md`: Docs-only correction route subsection, decision order, no `implement` reset, mixed-round split, SPEC consistency, Section 7 / Section 12 rules | Pins pass; 13 sections, no `## 14.`, 11 invariants and the Wording-correction route's fixed content unchanged | Integration |
| TS-9 | Doc test for `agents/rework-planner.md` and `contracts/rework-planner-contract.md`: document update scope, `write_policy` `replace_own` listing and alignment, files rule, docs-only patch shape, `payload.doc_corrections`, rename-aware check 2 | Pins pass; the four numbered checks and the Gate identifiers section unchanged | Integration |
| TS-10 | Doc test for `skills/develop/SKILL.md`: docs-only result in the interactive and batch verify failure branches, note under the `--once` table | Pins pass; the existing "新しい rework task が 1 件以上…まで戻さない" text and the four-row table remain | Integration |
| TS-11 | Doc test for `references/review-phase.md`: interactive and batch rework paths cite the docs-only correction route; a review-sourced docs-only round returns only `review` to `pending` | Pins pass; existing pinned sentences unchanged | Integration |
| TS-12 | Doc test: `agents/implementer.md` still contains "Never modify `feature-docs/**`" | Pin passes | Integration |
| TS-13 | Review: each new rule is written once in its owning document and cited by path elsewhere | No restated rule found | Manual |
| TS-14 | Inspection: every new test module imports only standard-library modules and uses `unittest` | No third-party import in new test modules | Manual |
| TS-15 | Plugin version fields unchanged on the feature branch: diff of `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` between `workflow.implement.base_commit` and HEAD | No version change | Manual |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction case passes as a task-less `append_rework` patch under `--dry-run-apply`; applied state has `implement` completed, `verify` pending, old test references removed, new IDs present | TS-1 |
| AC2 | Results whose tasks list `feature-docs/**` paths (alone or mixed) are rejected | TS-2, TS-3 |
| AC3 | Empty-entries patch returning `implement` to `pending` is rejected | TS-5 |
| AC4 | Tests replacement with unmet `expected` is rejected with `expected-mismatch` | TS-6 |
| AC5 | Renamed ID in `covered_by_existing` passes with a declared rename, rejected without | TS-7 |
| AC6 | `rework-task-synthesis.md` Section 9 holds the docs-only subsection, the decision order and the no-`implement`-reset statement | TS-8 |
| AC7 | Rework-planner agent and contract state direct correction of `tasks/*.md` and `VERIFICATION.md`, the `replace_own` listing and the files rule | TS-9 |
| AC8 | develop SKILL.md verify failure branches (interactive and batch) and the `--once` section state the docs-only transition and the resume position `verify` | TS-10 |
| AC9 | `python3 -m unittest discover -s tests` passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-8 |
| FR2 | task0002, task0003 | TS-1, TS-9 |
| FR3 | task0001, task0002, task0004 | TS-2, TS-3, TS-4, TS-9 |
| FR4 | task0003 | TS-1, TS-6 |
| FR5 | task0001, task0003, task0004 | TS-1, TS-5, TS-8 |
| FR6 | task0001, task0002, task0004 | TS-7, TS-8, TS-9 |
| FR7 | task0001, task0002, task0003, task0004 | TS-7, TS-8, TS-9 |
| FR8 | task0005 | TS-10 |
| FR9 | task0001, task0002, task0003, task0004, task0005 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10 |
| NFR1 | task0001, task0005 | TS-10, TS-11 |
| NFR2 | task0001 | TS-8 |
| NFR3 | task0002 | TS-12 |
| NFR4 | task0001, task0002, task0003, task0005 | TS-13 |
| NFR5 | task0001, task0002, task0003, task0004, task0005 | TS-14 |
| NFR6 | — | TS-15 |

## Manual Testing (E2E Not Possible)
- [ ] TS-13: read the changed documents and confirm each rule is owned once (route: `rework-task-synthesis.md`; `doc_corrections` and `write_policy` listing: `rework-planner-contract.md`; tests replacement: `workflow-patch.md`) and only cited elsewhere
- [ ] TS-14: inspect the imports of the five new test modules
- [ ] TS-15: compare the version fields of `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` between `workflow.implement.base_commit` and HEAD
- [ ] Reproduction walk-through: read the Docs-only correction route and confirm the reported case (verify failure from a scenario-ID format guard whose fix changes requirement test references) is routed to the docs-only route, not to task synthesis, and that TS-1 encodes that case
- [ ] TM-7 review: confirm the route text requires consistency with the unchanged SPEC.md / REQUIREMENTS.md and excludes corrections that check less than they require

## Performance / Security Verification (if applicable)
- TM-1: validator rejects `append_rework` task `files` whose first normalized segment is `feature-docs` — checked by TS-2 and TS-3 (and the segment edge cases in task0004's unit tests)
- TM-2: validator rejects an empty-entries `append_rework` patch that returns `implement` to `pending` — checked by TS-5
- TM-3: tests replacement requires each `from` in `expected.tests_contains` and rejects unmet expectations with `expected-mismatch` — checked by TS-6 and task0003's structural unit tests
- TM-4: contract obliges `payload.doc_corrections` with documents and origin pair for every docs-only correction — checked by TS-9; TS-1 carries a conforming declaration
- TM-5: renamed `covered_by_existing` IDs accepted only through a declared rename to a `verification_index` key — checked by TS-7
- TM-6: existing `tasks/*.md` rewritten only as `replace_own` targets listed for that round; SPEC.md / REQUIREMENTS.md never targets — checked by TS-9; TS-1's written artifacts are each covered by a `replace_own` target
- TM-7: docs-only corrections stay consistent with the unchanged SPEC.md / REQUIREMENTS.md — checked by TS-8 and the manual TM-7 review

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 15 | 12 | 0 | 3 |
| Success criteria | 9 | 9 | 0 | 0 |
| Threat mitigations (TM-n) | 7 | 6 | 0 | 1 |
| Manual checks | 5 | 0 | 0 | 5 |
