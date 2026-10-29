# Verification Document: verify-cap-worktree-cleanup

## Overview
**Feature**: verify-cap-worktree-cleanup / **SPEC.md**: `feature-docs/verify-cap-worktree-cleanup/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/verify-cap-worktree-cleanup/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty: a Python
  hook with no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted run: `python3 -m unittest tests.test_failed_run_cleanup_guard tests.test_guard_deferral_parity tests.test_verify_cap_run_continuation tests.test_step_c_verify_failed_default tests.test_hooks_registration tests.test_guardrail_hooks_migration`
- Expected: exit code 0, with no failures and no errors.
- Coverage target: the project has no coverage tooling. Instead, every
  automated scenario below has at least one test case in
  `tests/test_failed_run_cleanup_guard.py`.

### Test Scenarios from SPEC.md

TS-1 to TS-8 come from SPEC.md. TS-9 to TS-13 are derived by the planner from
FR3, FR5, NFR3, NFR6 and NFR7 and have no SPEC.md counterpart.

The base fixture has these step statuses:

- create-spec: completed
- design: skipped
- create-plan, implement, review: completed
- verify: failed
- retrospect: completed

Its `batch.verify_rework` is `rounds` 1 with `failed_id_counts` {V1: 2}.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | S1 in the excluded state: pass `git worktree remove` with the integration worktree's absolute path, against the base fixture. Run once with CLAUDE_BATCH set and once without | Empty stdout and exit code 0 in both runs | Unit |
| TS-2 | S1 with only the hard cap reached: use the TS-1 step statuses with `rounds` 3 and `failed_id_counts` {V1: 1} | Empty stdout | Unit |
| TS-3 | S3 in the excluded state: pass `gh pr create` with the TS-1 fixture's integration worktree as cwd | Empty stdout | Unit |
| TS-4 | S2 in the excluded state: pass `git branch -d em-workflow/{feature}/integration` with the TS-1 fixture's root as cwd | Deny. The reason contains the feature and verify | Unit |
| TS-5 | A missing exclusion condition: start from TS-1 and break one condition at a time, then pass S1. The cases are: retrospect pending; implement also failed; batch block absent; `rounds` 2 with every `failed_id_counts` value 1; `rounds` as a string; `failed_id_counts` as a list; a `failed_id_counts` value of true | Deny in every case, never empty output | Unit |
| TS-6 | An unresolvable target: use a root holding only an excluded-state worktree as cwd, and pass `git worktree remove "$WT"` and `git branch -d "$BR"` separately | S1 gives empty stdout. S2 gives ask, or deny with CLAUDE_BATCH set | Unit |
| TS-7 | Regression of existing behavior: run the targeted modules listed above, then the full discover run | Every test passes | Integration |
| TS-8 | Documentation: read the hook's module docstring and the failed-run-cleanup-guard.py entry of `em-workflow/README.md` | Both state the excluded-state conditions, and both state that S2 is not excluded | Inspection |
| TS-9 | A chained unresolvable payload (planner-derived, FR5): use the TS-6 root as cwd, and send one payload that chains `git worktree remove "$WT"` and `git branch -d "$BR"`. Send it in both orders | Ask, or deny with CLAUDE_BATCH set, in both orders. The S1 result never leaks into S2. Each worktree's workflow.yaml is read at most once per payload | Unit |
| TS-10 | Cap-record reading (planner-derived, FR3): use the TS-1 step statuses with these cap records: (i) `failed_id_counts` {V1: 2} and no `rounds`; (ii) `rounds` 3 and no `failed_id_counts`; (iii) a `batch` that is not a mapping, or a `verify_rework` that is not a mapping; (iv) only an obsolete `verify_rework_count` of 3, placed under `batch` or inside `verify_rework`; (v) a batch block with `rounds` 0 and an empty `failed_id_counts` | Cases (i) and (ii) give empty stdout. Cases (iii), (iv) and (v) give deny | Unit |
| TS-11 | Free text is ignored (planner-derived, NFR3): put text shaped like step statuses and cap values into `goal` and other free-text fields of two fixtures, the TS-1 fixture and a retrospect-pending fixture | The TS-1 fixture still gives empty stdout. The retrospect-pending fixture still gives deny | Unit |
| TS-12 | The version is unchanged (planner-derived, NFR7): run `git diff --name-only` from the implement step's `base_commit` to HEAD | The list contains neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | Command check |
| TS-13 | Test conventions (planner-derived, NFR6): inspect the test cases added to `tests/test_failed_run_cleanup_guard.py` | They use only standard-library unittest with tempfile fixtures, and they reference no real worktree and no `~/.claude` path | Inspection |

## Code Quality Verification
- Format: none configured. `project.components.main.format_command` is empty.
- Static analysis: none configured.
- Hook invariants, checked by inspection of the diff of
  `em-workflow/hooks/failed-run-cleanup-guard.py`:
  - no allow decision is emitted on any added path
  - no subprocess use is introduced
  - no file write is introduced

  These checks cover NFR1 and NFR2, together with TS-7.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | S1 against an excluded-state integration worktree gets no decision, with or without CLAUDE_BATCH | TS-1 |
| AC2 | S3 with an excluded-state integration worktree as cwd gets no decision | TS-3 |
| AC3 | S2 for an excluded-state feature is denied with the feature and verify in the reason | TS-4 |
| AC4 | S1 is denied when any one exclusion condition is missing | TS-5, TS-10 |
| AC5 | Exclusion holds with the lineage cap only, and with the hard cap only | TS-1, TS-2 |
| AC6 | Unresolvable S1 gets no decision. Unresolvable S2 gets ask (deny under CLAUDE_BATCH) | TS-6, TS-9 |
| AC7 | The docstring and the README entry describe the excluded state and S2's handling | TS-8 |
| AC8 | The listed existing tests and the full discover run pass | TS-7 |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | TS-1 to TS-13 |
| SC-3 | Documentation is complete | TS-8 |
| SC-4 | Code review is completed | Review phase result |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| FR3 | task0001 | TS-1, TS-2, TS-5, TS-10 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-6, TS-9 |
| FR6 | task0001 | TS-5, TS-7 |
| FR7 | task0001, task0002 | TS-8 |
| FR8 | task0001 | TS-7, TS-1, TS-3, TS-4, TS-5 |
| NFR1 | task0001 | TS-7 |
| NFR2 | task0001 | TS-7, TS-9 |
| NFR3 | task0001 | TS-5, TS-11 |
| NFR4 | task0001 | TS-7 |
| NFR5 | task0001 | TS-1, TS-2, TS-5 |
| NFR6 | task0001 | TS-13 |
| NFR7 | task0001, task0002 | TS-12 |

## Manual Testing (E2E Not Possible)
- [ ] TS-8: check the docstring and the README entry, as described in the
  scenario table.
- [ ] TS-13: check the test conventions, as described in the scenario table.
- [ ] NFR5 cross-check: compare the hook's thresholds with the lineage-cap
  definition in `em-workflow/skills/develop/SKILL.md`, section "batch 自動
  rework の系譜 cap". Expected: lineage cap at a `failed_id_counts` value of 2
  or more, hard cap at `rounds` of 3 or more.
- [ ] Reproduction steps from the goal: a live batch develop run that reaches
  Step C with verify failed at the cap is not executed in verify. TS-1 stands
  in for it, using the same S1 payload shape and the same workflow.yaml state
  as the Step C invocation.

## Performance / Security Verification (if applicable)
- NFR2: workflow.yaml is read at most once per target, including in a chained
  S1 + S2 payload. Checked by TS-9 (read count).
- TM-1: strict cap-record typing (bool is not an integer; a non-mapping
  container gives no exclusion; one invalid member invalidates the whole
  record). Checked by TS-5 and TS-10: every type-confused case yields a deny.
- TM-2: the decision reads only the steps' id and status and
  `batch.verify_rework`'s numeric members. Checked by TS-11: status-shaped and
  cap-shaped free text changes no outcome.
- TM-3: the excluded-state classification never raises. Checked by TS-5: the
  list-typed and bool-typed cap-record cases yield a deny, not empty output.
- TM-4: the unresolvable-target aggregate is memoized separately for each
  shape. Checked by TS-9: a chained S1 + S2 payload still yields ask (deny
  under CLAUDE_BATCH) in both orders.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit scenarios (TS-1 to TS-6, TS-9 to TS-11) | 9 | 9 | 0 | 0 |
| Regression (TS-7) | 1 | 1 | 0 | 0 |
| Command check (TS-12) | 1 | 1 | 0 | 0 |
| Inspection (TS-8, TS-13, NFR5 cross-check, reproduction stand-in) | 4 | 0 | 0 | 4 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| NFR2 read count | 1 | 1 | 0 | 0 |
| **Total** | 20 | 16 | 0 | 4 |
