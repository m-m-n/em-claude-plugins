# Verification Document: routeback-deferred-findings

## Overview

**Feature**: routeback-deferred-findings / **SPEC.md**: `feature-docs/routeback-deferred-findings/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/routeback-deferred-findings/IMPLEMENTATION.md`

Integrated verification for the resolution of the six findings deferred at review
round 3 of `routeback-admissibility-exits`: `12839a507a7df994`, `2da3c75adac32650`,
`bc57aa350bb027c7`, `59e58726b1b22211`, `94de80a315821a55`, `9cc0ce6b64087d2f`.

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the change consists
  of Python scripts, Markdown documents, tests and JSON manifests with no build step)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors, no test skipped by this feature
- Coverage target: no coverage tool is configured (stdlib-only suite); the target is
  that every Acceptance Criterion of every task maps to at least one passing test,
  recorded in `test-docs/routeback-deferred-findings/{task}.tests.yaml`

### Test Scenarios from SPEC.md

TS-1 through TS-7 come from SPEC.md; TS-8 through TS-12 were added during planning so
that every FR/NFR has at least one verifying scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | I.2.b step 1 doc contract for the widened candidate set: a `launched` task with one or both artifacts missing and a non-outstanding `Task()` call joins Agent index lookup → Recovery → Orphan recovery → Same-session extension; artifact absence is evidence, not proof | New statements present; the pre-change "second, independent condition" wording absent, each absence proven against the verbatim pre-change sample; pinned retained literals still match | Integration (doc contract) |
| TS-2 | `recover-orphaned-task.py` evidence chain with worktree missing, branch missing, and both missing | Each reaches `recovered` under full proof with exactly one helper call (`stale-launched`, launch identity); unproven termination or stop result stays residual with a byte-identical journal; absent or unrecognized artifact token yields `task-artifacts-missing` before any read; existing step-order tests use an unrecognized token | Unit + subprocess |
| TS-3 | Doc-contract pin for `bc57aa350bb027c7`: the candidate-set predicate "whose `Task()` call is not among this reconcile step's own currently-outstanding calls" and the Same-session extension's `stale-launched` invocation | Predicate pinned in I.2.b; loop-2 restriction wording present in its verbatim sample and absent from the live document | Integration (doc contract) |
| TS-4 | `journal-append-failed.py --reason merge-unverified` with final event `merged`, `launched`, `failed`, none; concurrent calls; `orphaned` / `stale-launched` over `merged`; launch guard after a `merge-unverified` line | Append only over `merged` (fields event, task, at, reason); `noop_terminal` and byte-identical journal otherwise; at most one line under concurrency; existing no-op over `merged` kept; launch guard allows the relaunch | Unit + subprocess |
| TS-5 | I.2.c doc contract | Dead-end wording absent (negative proofs against the verbatim pre-change paragraph); the new exit statement present; no `append` / `rework` substring in I.2.c; batch-mode paragraph byte-identical | Integration (doc contract) |
| TS-6 | `workflow-schema.md` doc contract | Writer-set paragraph records `merge-unverified` as a third additive reason with exactly five writer names; Status semantics bullet carries no exception; `agents.jsonl` paragraph names all four readers and the I.2.b step 1 impact of an absent or stale index; three old phrases absent with negative proofs | Integration (doc contract) |
| TS-7 | Version lockstep | `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` both read 0.2.11 (the test asserts equal and strictly greater than 0.2.10) | Unit |
| TS-8 | I.2.a / I.2.b ancestor-check branch / orphan block / Supporting cast doc contract | I.2.b step 1 states the `merge-unverified` invocation with its preconditions, same-step re-replay and helper-failure residue; I.2.a states the retry path and the remaining helper-failure case; no sentence claims the orphan-recovery attempt is the only orchestrator-caused journal write; negative proofs for each removed phrase | Integration (doc contract) |
| TS-9 | Suite-level regression and scope | `python3 -m unittest discover -s tests` passes; `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` unchanged; no modified test module lost test methods; no pin removed without a replacement assertion | Integration + manual diff check |
| TS-10 | SC6 reason-code placement | Every backtick-quoted SC6 code occurs in `implement-phase.md` only within I.2.b; `workflow-schema.md` contains none | Unit (doc contract) |
| TS-11 | Launch guard and merge script untouched | `em-workflow/hooks/queue_launch_guard.py` and `em-workflow/scripts/merge-task.sh` have no diff against the implement base commit; the existing deny-after-`launched` and deny-after-`merged` pins pass | Integration + manual diff check |
| TS-12 | Stdlib-only tests | Every new or modified test module imports only the standard library (AST-based import checks) | Unit |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Standard-library-only imports are enforced by the suite itself (TS-12)

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage table below; every listed scenario passes |
| SC-2 | All test scenarios pass | `python3 -m unittest discover -s tests` exits 0 (TS-1 to TS-12) |
| SC-3 | AC-1 to AC-9 of REQUIREMENTS.md 11.1 are met | AC-1 → TS-1; AC-2 → TS-2; AC-3 → TS-3; AC-4 → TS-5, TS-8; AC-5 → TS-4; AC-6 → TS-6, TS-8; AC-7 → TS-6; AC-8 → TS-7; AC-9 → TS-9 |
| SC-4 | `python3 -m unittest discover -s tests` passes | Run the command; exit code 0 |
| SC-5 | `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` is unchanged | `git diff --quiet` of that path between the implement base commit and the integration branch tip |
| SC-6 | `plugin.json` and `marketplace.json` em-workflow entries read 0.2.11 | Read both files; TS-7 asserts equality and the move past 0.2.10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0003 | TS-1 |
| FR2 | task0002, task0003 | TS-1, TS-2 |
| FR3 | task0003 | TS-3 |
| FR4 | task0004 | TS-4, TS-8 |
| FR5 | task0001 | TS-4 |
| FR6 | task0004, task0005 | TS-5, TS-6, TS-8 |
| FR7 | task0005 | TS-6 |
| FR8 | task0005 | TS-6 |
| FR9 | task0006 | TS-7 |
| FR10 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-9 |
| NFR1 | task0001, task0005 | TS-6 |
| NFR2 | task0004 | TS-5 |
| NFR3 | task0004 | TS-5 |
| NFR4 | task0003, task0004, task0005 | TS-10 |
| NFR5 | task0001, task0002, task0003, task0004 | TS-1, TS-2, TS-4, TS-8 |
| NFR6 | task0001 | TS-4 |
| NFR7 | task0001, task0004 | TS-11 |
| NFR8 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-12 |

## E2E Testing

Not applicable: the project has no E2E framework and no E2E command
(`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)

- [ ] Read I.2.a, I.2.b step 1, I.2.c and the Supporting cast of
      `em-workflow/references/implement-phase.md` next to the writer-set, `agents.jsonl`
      and Status semantics parts of `em-workflow/references/workflow-schema.md`:
      no statement remains that a `failed` task has an exit outside retry / route back
      to planning / abort, that the orphan-recovery attempt is the only
      orchestrator-caused journal write, or that `agents.jsonl` is read only at stop.
- [ ] Confirm the citation label "I.2.b step 1 ancestor-check branch" used in
      `workflow-schema.md` points at the `merge-unverified` invocation text in
      `implement-phase.md` (IMPLEMENTATION.md SC-4).
- [ ] Confirm each of the six stable ids is addressed: `12839a507a7df994` (TS-1,
      TS-2), `2da3c75adac32650` (TS-4, TS-8), `bc57aa350bb027c7` (TS-3),
      `59e58726b1b22211` and `9cc0ce6b64087d2f` (TS-5, TS-6, TS-8),
      `94de80a315821a55` (TS-6).
- [ ] Confirm `em-workflow/README.md`'s journal description does not contradict the
      single helper exception (IMPLEMENTATION.md SC-3) and restates no SC6 code.
- [ ] Confirm that `em-workflow/hooks/queue_launch_guard.py`,
      `em-workflow/scripts/merge-task.sh` and
      `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` show no diff
      (TS-9, TS-11).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 12 (TS-1 to TS-12) | 12 | 0 | 2 (diff checks inside TS-9, TS-11) |
| Success criteria | 6 | 5 | 0 | 1 (SC-5 diff check) |
| Manual review | 5 | 0 | 0 | 5 |
