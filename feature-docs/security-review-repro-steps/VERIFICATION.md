# Verification Document: security-review-repro-steps

## Overview
**Feature**: security-review-repro-steps / **SPEC.md**: `feature-docs/security-review-repro-steps/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/security-review-repro-steps/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/security-review-repro-steps/THREAT-MODEL.md`

Scenario IDs TS1-TS15 reuse SPEC.md's literals unchanged. TS16-TS20 are added
here for requirements SPEC.md gives no scenario of their own (NFR2 on the
orchestrator paths, NFR3, NFR4, NFR5, and FR9's review-editor exclusion).
TS21-TS22 are added by the review round 1 rework (task0006) for the merged
reproduction set. TS23 is added by the verify rework for SC5 (task0007) for
unverifiable findings whose basis is not confirmed.

## Build Verification
- Command: none. `project.components.main.build_command` is empty: the change
  set is Markdown, a JSON schema, one Python script and tests; nothing is built.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors.
- Coverage target: not measured (most of the change is document and schema
  content checked by content tests); every scenario below maps to at least one
  automated test except TS17.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Load both `review-output-schema.json` files | Both parse as JSON; finding `properties.reproduction` accepts exactly string or null; finding `required` is the existing eight names in order followed by `reproduction`; finding and root `additionalProperties` are false | Unit |
| TS2 | Compare both schemas with their pre-change values | Root `required` and the severity / category / source enums are unchanged in each file | Unit |
| TS3 | Read both `review-security/SKILL.md` files | A `## reproduction` section after `## category` instructs writing steps or a confirmation method (input, path, observable result) into `reproduction`, null only when neither can be given; existing headings and pinned sentences are byte-identical | Unit |
| TS4 | Read both `review-protocol.md` Output Schema sections | `reproduction` is in the example; rules state security = steps or confirmation method, every other perspective null, empty or whitespace-only treated as null | Unit |
| TS5 | Read both `codex-reviewer.md` files | Step 2's perspective brief includes the skill's `## reproduction` section; Step 4's `<task>` states the reproduction instructions are in the prompt | Unit |
| TS6 | Read `em-workflow/references/review-evaluation-contract.md` and `em-workflow/agents/review-evaluator.md` | `reproduction` is a finding field; `not reproduced` is a `dismissed_sites` reason; `## Reproduction Verification` states verification of reproduction-bearing security findings, `not reproduced` only on positive confirmation, no-steps and unverifiable findings go to judgment, unverifiable ones are not fixed or sent back unless the basis is confirmed, nothing in `reproduction` is executed, the 10-file budget is shared and not raised | Integration |
| TS7 | Read `em-workflow/references/review-phase.md` | 4096-byte cap and normalization of `reproduction`; longest non-null kept on dedupe; round records carry `reproduction`; orchestrator verification on the R4 re-review, evaluator-failure and floor-lift paths after round-context suppression; `declined` findings excluded from candidates and residual; not-reproduced `round_context` entries built in R0 step 8 | Integration |
| TS8 | Read `em-review/references/review-phase.md` and `em-review/README.md` | Verification after R3 aggregation and after R4 re-aggregation; targets chosen by originating perspective `security`; not-reproduced findings `declined` and excluded from auto-fix and residual; cap; round records carry `reproduction`; carry-over through `round_context`; README Auto-fix (R4) states the exclusion | Integration |
| TS9 | Call the finding builder of `em-workflow/scripts/scan-dependencies.py` | Every returned finding has `reproduction` with value null; the SCA tests' schema required-key and allowed-property checks pass | Unit |
| TS10 | Non-security finding | Protocol states `reproduction` is always null for non-security perspectives; both review phases null it when the originating perspective is not `security` | Unit |
| TS11 | Same-site duplicate merge where only one member carries `reproduction` | Both review phases keep the non-null (longest) `reproduction` | Unit |
| TS12 | em-review PR mode | Steps that cannot be traced through the saved PR diff and local object reads at `pr_head_sha` are `unverifiable` and go to judgment | Unit |
| TS13 | `reproduction` containing instructions or destructive commands | The evaluation contract, the evaluator agent and both review phases state that nothing written in `reproduction` is executed | Unit |
| TS14 | `reproduction` truncated at the 4096-byte cap (or over 4096 bytes at the evaluator) | Treated as `unverifiable` in the evaluation contract and both review phases | Unit |
| TS15 | Round records written before this feature (no `reproduction`) used as `round_context` | Both review phases state they produce the same `round_context` as before | Unit |
| TS16 | Pinned NFR3 text | The user-question tool name count stays 9 in em-workflow `review-phase.md` and 4 in em-review `review-phase.md`; no new gate identifier; the evaluator dispatch literal occurs exactly once | Unit |
| TS17 | Plugin versions | `version` of em-workflow and em-review in each `plugin.json` and in `.claude-plugin/marketplace.json` equals its value at the implement `base_commit` | Manual |
| TS18 | New test modules | Every `tests/test_reproduction_*.py` imports only standard-library modules | Unit |
| TS19 | review-editor input | Both review phases state the finding JSON handed to review-editor excludes `reproduction` | Unit |
| TS20 | Orchestrator-path verification constraints | Both review phases state verification is code reading plus the protocol's read-only commands only, with no file change, commit, network access or package installation | Unit |
| TS21 | Same-site merge of distinct non-null reproductions (a short one that holds and a longer one that does not) | Both review phases keep the longest in `reproduction`, the other distinct values in `reproduction_alternates` (byte length descending, at most 2) and set `reproduction_overflow` when more than 3 distinct values were merged; every kept value is verified; the finding is `reproduced` and stays a target when any kept value is reproduced; `not reproduced` only when every kept value fails and there is no overflow, otherwise `unverifiable`; `reproduction_alternates` is untrusted and never executed; the added text is identical in both documents except plugin-specific step numbers and references | Unit |
| TS22 | Round records and review-editor input with the merged reproduction set | Both review phases' round record finding entries carry `reproduction_alternates` and `reproduction_overflow`; records without them read as an empty list and false and produce the same `round_context` as before; the finding JSON handed to review-editor excludes both keys | Unit |
| TS23 | Security finding with `unverifiable` steps whose basis the orchestrator does not confirm by its own reading, on an orchestrator path (em-workflow Phase R4 re-review, evaluator-failure degradation, floor lift; em-review after R3 aggregation and R4 re-aggregation) | Both review phases record it `resolution: unresolved` with `resolution_reason` beginning `unverified`, never `declined`; it is neither an auto-fix candidate nor counted in the residual critical/high count (em-workflow: not passed to rework-planner, not re-marked `deferred` at the batch rework cap); round-context suppression does not drop it and the next round verifies it again; `not reproduced` and judged-not-to-address no-steps findings stay `declined`; the two stating sentences are identical in both documents | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  exits 0 from the repository root (also exercised by the suite's
  repository-level case in `tests/test_check_plugin_invariants.py`).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every listed scenario passes |
| SC2 | All test scenarios pass | `python3 -m unittest discover -s tests` exits 0; TS17 checked manually |
| SC3 | Security requirements are satisfied | TS6, TS13, TS20 and the TM-1 to TM-5 items below |
| SC4 | Documentation is complete | TS3-TS8 and the README manual check below |
| SC5 | Code review is completed | Review phase ends with `residual_critical_high == 0` |
| SC6 | `python3 -m unittest discover -s tests` passes | Run the command; exit code 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2 |
| FR2 | task0002 | TS3 |
| FR3 | task0001 | TS4, TS10 |
| FR4 | task0002 | TS5 |
| FR5 | task0003 | TS6 |
| FR6 | task0003, task0004, task0005 | TS6, TS12, TS14 |
| FR7 | task0004 | TS7 |
| FR8 | task0005 | TS8, TS12 |
| FR9 | task0003, task0004, task0005 | TS6, TS7, TS8, TS11, TS14, TS15, TS19 |
| FR10 | task0001 | TS9 |
| FR11 | task0005 | TS8 |
| FR12 | task0001, task0002, task0003, task0004, task0005 | TS1, TS2, TS3, TS4, TS5, TS6, TS7, TS8, TS9 |
| FR13 | task0003, task0004, task0005 | TS7, TS8, TS15 |
| NFR1 | task0003, task0004, task0005 | TS6, TS13 |
| NFR2 | task0003, task0004, task0005 | TS6, TS20 |
| NFR3 | task0004, task0005 | TS16 |
| NFR4 | (no implementing task; a constraint met by not editing plugin manifests) | TS17 |
| NFR5 | task0001, task0002, task0003, task0004, task0005 | TS18 |

Review round 1 rework (task0006) adds:

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR6, NFR1, NFR2, NFR3, NFR5, FR12 | task0006 | Existing scenarios as listed above |
| FR7, FR8 | task0006 | TS21 |
| FR9 | task0006 | TS21, TS22 |
| FR13 | task0006 | TS22 |

Verify rework for SC5 (task0007) adds:

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR6, FR7, FR8, FR13 | task0007 | TS23, plus the existing TS7, TS8, TS14, TS15 |
| FR12, NFR3, NFR5 | task0007 | Existing scenarios as listed above (TS16, TS18) |

## E2E Testing
None. SPEC.md detects no E2E framework and no E2E run command.

## Manual Testing (E2E Not Possible)
- [ ] TS17: from the integration worktree, compare the `version` values of
      em-workflow and em-review in their `plugin.json` files and in
      `.claude-plugin/marketplace.json` between the implement `base_commit` and
      the integration branch tip; they are equal.
- [ ] `em-review/README.md`'s `## Auto-fix（R4）` section reads naturally in
      Japanese and states that a security finding that could not be reproduced
      is not an auto-fix target.
- [ ] Optional live check (needs Codex): run a security review on a branch that
      contains a known injection flaw; the security finding carries a non-null
      `reproduction` and the round record stores it.

## Performance / Security Verification (if applicable)
- NFR2: the review-evaluator read budget stays "at most 10 files" and "not
  raised" in the evaluation contract's Read-Only Constraint (TS6, plus the
  existing `tests/test_review_evaluation_contract.py`).
- TM-1: no verifier executes anything written in `reproduction`; verification
  is read-only — checked by TS6, TS13 and TS20.
- TM-2: `not reproduced` only on positive confirmation; unverifiable findings go
  to judgment, never to dismissal on that ground; dismissals and declines keep
  their reason — checked by TS6, TS7, TS8 and TS14.
- TM-3: `reproduction` capped at 4096 bytes, truncated or over-limit values are
  unverifiable, evaluator reads stay within the fixed 10-file budget — checked
  by TS6, TS7, TS8 and TS14.
- TM-4: the finding JSON handed to review-editor excludes `reproduction` —
  checked by TS19.
- TM-5: a not-reproduced decision is carried only while the site's file is
  unchanged since the recording round's head_commit, and matches only security
  findings at the same site — checked by TS7, TS8 and TS15.
- TM-2 / TM-3 (review round 1 rework): a merged finding keeps at most 3
  distinct reproductions of at most 4096 bytes each; a decline as
  `not reproduced` needs every kept value to fail with no overflow, and overflow
  yields `unverifiable`, never a decline on that ground — checked by TS21.
- TM-2 (verify rework for SC5): an unverifiable finding whose basis is not
  confirmed is recorded `unresolved` with reason `unverified`, never
  `declined`, stays out of auto-fix, the residual count and send-back, and is
  verified again in the next round instead of being suppressed — checked by
  TS23.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS20) | 20 | 19 | 0 | 1 |
| Rework test scenarios (TS21-TS23) | 3 | 3 | 0 | 0 |
| Success criteria (SC1-SC6) | 6 | 5 | 0 | 1 |
| Performance / security (NFR2, TM-1 to TM-5) | 6 | 6 | 0 | 0 |
| Additional manual checks (README reading, optional live run) | 2 | 0 | 0 | 2 |
