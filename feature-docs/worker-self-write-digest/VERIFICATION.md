# Verification Document: worker-self-write-digest

## Overview
**Feature**: worker-self-write-digest / **SPEC.md**: `feature-docs/worker-self-write-digest/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/worker-self-write-digest/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the integration worktree root)
- Expected: exit code 0, no failures or errors.
- Coverage target: every test scenario below has at least one passing test or a recorded check; no line-coverage tool is configured for this repository.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Designer `extend_only`: `tokens.yaml` modified (key added) under `extend_only` and `tokens.html` modified under `regenerate`, run through the self-write script | Substituted digest equals the dispatch-time digest; the unsubstituted current digest differs | Unit |
| TS-2 | Planner re-plan: `IMPLEMENTATION.md` / `VERIFICATION.md` modified under `replace_own` plus a new `tasks/task000N.md` under the `tasks/` allowed write root | Substituted digest equals the dispatch-time digest; `validate-worker-output.py --dry-run-apply` with the substituted digest_source reports no `stale-input-digest`, and with the unsubstituted one reports it | Unit / Integration |
| TS-3 | Rework-planner: `VERIFICATION.md` (and `IMPLEMENTATION.md`) modified under `replace_own` plus a new file under `tasks/` | Not stale: substituted digest equals the dispatch-time digest; `--dry-run-apply` passes for an `append_rework` patch | Unit / Integration |
| TS-4 | `SPEC.md` changes during the window alongside legitimate self-writes; separately, each of `value_inputs`, `answers_digest`, `write_policy_digest`, `workflow_blob` changes | Every case is stale (digests differ) | Unit |
| TS-5 | `written_artifacts` lists `SPEC.md` but the observed change set excludes it | `SPEC.md` is not in the self-write set and is not substituted | Unit |
| TS-6 | An existing `tasks/` file modified under the allowed write root alone; a modified `preserve` target; `tokens.html` changed without `tokens.yaml` | None is a self-write; with the path as a digest input the result is stale | Unit |
| TS-7 | A `create` target absent at dispatch and present after | It is a self-write; its key is absent from the substituted digest_source; the digest matches the dispatch-time digest | Unit |
| TS-8 | Resume after self-writes, using a phase-state document whose last `worker_runs` entry carries `dispatch_digest_inputs` and `self_write_set` | `substitute_only` reproduces the entry's `input_digest` (no false mismatch); after editing a self-written artifact, its `artifact-digest.py` digest differs from the recorded `artifacts[].sha256` (detected) | Integration |
| TS-9 | Document assertions on `worker-envelope.md` R1 and on the three contracts' citations and overlap lists, and on `workflow-patch.md` application rule 1 | R1 states the conditional rule once; each contract cites R1 and names exactly its overlapping paths; rule 1 cites R1's substitution | Unit (document) |
| TS-10 | Full suite including `check-plugin-invariants` `worker_digest_stance` and `dispatch_digest_wiring` on the real repository | `python3 -m unittest discover -s tests` exits 0 | Integration |
| TS-11 | Document assertions on the three dispatch-site procedures (「design ステップ分岐」, create-plan sections 3/4/8/9, rework section 10) | Each records `dispatch_digest_inputs`, names `scripts/self-write-digest.py` after the scope verification and before the R1 comparison / validator / layer-5 recording, cites R1, and records `self_write_set` with the layer-5 write; create-plan section 3 uses `substitute_only` on resume | Unit (document) |
| TS-12 | Document assertions on `phase-state.md`'s `worker_runs` fields | Both fields appear in the schema block and the field table with their write timing; the idempotency exception allows `status` plus the one-time `self_write_set` addition; the Resume decision table applies R1's substitution and keeps the artifact-digest comparison | Unit (document) |
| TS-13 | `digest_source` structure: the script's output keeps the current digest_source's top-level members; R1's normalization paragraph and the seven structural keys stay unchanged | Output key set equals input key set; existing `test_worker_contract_docs` and `digest_reproducibility` checks pass | Unit |
| TS-14 | Plugin version fields after the change | The `version` in `em-workflow/.claude-plugin/plugin.json` and in the `em-workflow` entry of `.claude-plugin/marketplace.json` equal their values at the commit recorded as `workflow.implement.base_commit` | Integration (verify-phase check) |
| TS-15 | No restatement of R1 outside R1 | The three contracts and the three dispatch-site sections cite R1 and contain no action-by-kind matrix wording or substitution wording | Unit (document) |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0 (also exercised inside the test suite).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR maps to at least one task and one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-15 pass |
| SC-3 | `python3 -m unittest discover -s tests` passes in full (NFR4) | TS-10 |
| SC-4 | The plugin version is not changed (NFR5) | TS-14 |
| SC-5 | The new tests fail against the pre-fix behaviour (AC10) | TS-1 to TS-3 and TS-2's validator case assert that the unsubstituted current digest_source (the pre-fix behaviour) is judged stale; the script and its tests do not exist before the change |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-7 |
| FR2 | task0001, task0002 | TS-1, TS-5 |
| FR3 | task0001, task0002 | TS-1, TS-2, TS-6, TS-7 |
| FR4 | task0001, task0002 | TS-4 |
| FR5 | task0001, task0002, task0003 | TS-2, TS-3 |
| FR6 | task0001, task0002, task0003 | TS-8, TS-11 |
| FR7 | task0001, task0002, task0003 | TS-8, TS-12 |
| FR8 | task0002, task0003 | TS-11 |
| FR9 | task0002 | TS-9 |
| FR10 | task0001, task0003 | TS-11 |
| FR11 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-10 |
| NFR1 | task0001, task0002 | TS-13 |
| NFR2 | task0002 | TS-10 |
| NFR3 | task0003 | TS-10 |
| NFR4 | task0001, task0002, task0003 | TS-10 |
| NFR5 | task0001, task0002, task0003 | TS-14 |
| NFR6 | task0002, task0003 | TS-15 |

## Manual Testing (E2E Not Possible)
- [ ] "再現手順で現象が起きない": in a scratch feature with an existing `design-system/tokens.yaml`, dispatch the designer with `extend_only`; after it adds a key and regenerates `tokens.html`, the design-step recheck does not report stale.
- [ ] A live create-plan re-plan that rewrites `IMPLEMENTATION.md` / `VERIFICATION.md` with `replace_own` and adds a task plan passes the validator's `--dry-run-apply` without a stale report.

## Performance / Security Verification (if applicable)
- TM-1: membership requires the orchestrator-observed change set; `written_artifacts` never admits a path — checked by TS-5 (task0001 AC-1) and the R1 document assertion in TS-9 (task0002 AC-1).
- TM-2: the per-action membership matrix admits only permitted change kinds — checked by the table-driven matrix test and TS-6 (task0001 AC-1, AC-4) and the R1 document assertion in TS-9 (task0002 AC-1).
- TM-3: the script takes one JSON input document named by a single argument, and R1 requires the orchestrator to write it with its file-writing tool outside the integration worktree without shell interpolation — checked by the CLI tests (task0001 AC-7) and the R1 document assertion in TS-9 (task0002 AC-1).
- TM-4: on resume the artifact-body comparison with recorded digests stays, and `self_write_set` is written in the same phase-state write as the run's layer-5 `artifacts` entries — checked by TS-8 (task0001 AC-6), TS-12 (task0002 AC-4) and TS-11 (task0003 AC-1, AC-3).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-15) | 15 | 15 | 0 | 0 |
| Success criteria | 5 | 5 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Manual reproduction | 2 | 0 | 0 | 2 |
| **Total** | 26 | 24 | 0 | 2 |
