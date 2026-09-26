# Verification Document: routeback-ssot-drift

## Overview

**Feature**: routeback-ssot-drift / **SPEC.md**:
`feature-docs/routeback-ssot-drift/SPEC.md` / **IMPLEMENTATION.md**:
`feature-docs/routeback-ssot-drift/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the integration
  worktree root
- Expected: exit code 0, no failures or errors, and no test skipped by this
  feature
- Coverage target: not applicable (document-contract tests; no coverage
  tool is configured)

### Test Scenarios from SPEC.md

TS-1 to TS-5 correspond one-to-one to SPEC.md TS1 to TS5. TS-6 is added for
NFR3 and for the "unchanged" clauses of FR4, FR5 and FR8.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Static text tests on `em-workflow/references/workflow-schema.md` with whitespace normalized: the sole-reader sentence form, "exists solely to make a stop resolvable back to a task" and "its absence only degrades the stop-tool recorder to a no-op" are absent; the agents.jsonl paragraph names `queue_taskstop_net.py`, `queue_failure_net.py` and the Orchestrator-side read (with the orphan-recovery evidence chain), states the purpose and the absence behavior (Residual, `no-agent-entry`) by citing `implement-phase.md`, and tells the two "ambiguous" conditions apart | All assertions and their negative proofs pass | Unit |
| TS-2 | Static test on the module docstring of `em-workflow/hooks/queue_agent_index.py`: the "Its only job is to record" stop-only claim is absent; readers and purpose agree with TS-1 | Assertions and negative proofs pass | Unit |
| TS-3 | Retention tests on the I.2.b section of `em-workflow/references/implement-phase.md`: the partial-artifact recovery sentence and the third-case (stop tool stops nothing / recorder appends no terminal event) Residual sentence are present | Assertions and non-vacuity proofs pass | Unit |
| TS-4 | `TestPluginVersionBumpedInLockstep` in `tests/test_implement_routeback_gate.py` runs with baseline (0, 2, 10) against 0.2.11 in both manifests | Both tests in the class pass | Unit |
| TS-5 | Full suite: `python3 -m unittest discover -s tests` | Exit code 0; every pre-existing pin listed in NFR2 still passes | Integration |
| TS-6 | Change-set scope check on the integrated diff against the implement base commit: changed paths are limited to `em-workflow/references/workflow-schema.md`, `em-workflow/hooks/queue_agent_index.py`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `tests/test_implement_routeback_gate.py`, `tests/test_routeback_ssot_drift_agent_index.py`, `tests/test_routeback_ssot_drift_i2b_retention.py`, plus `feature-docs/routeback-ssot-drift/**` and `test-docs/routeback-ssot-drift/**`; `em-workflow/references/implement-phase.md` and `tests/test_routeback_residual_connections_version_bump.py` are not in the diff; the diff of `queue_agent_index.py` lies entirely inside the module docstring; the em-review entry of `.claude-plugin/marketplace.json` is unchanged | All conditions hold | Integration (diff check) |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS-1 to TS-4 and TS-6 pass |
| SC-2 | All test scenarios pass | TS-5 exits 0 and TS-6 holds |
| SC-3 | Documentation is complete | TS-1 and TS-2 pass; manual reading below |
| SC-4 | Code review is completed | The review step reads `completed` in workflow.yaml |

### SPEC.md Acceptance Criteria

| SPEC AC | How to Verify |
|---------|---------------|
| AC1 | TS-1 |
| AC2 | TS-1 |
| AC3 | TS-1 (names and distinction), TS-6 (`implement-phase.md` unchanged) |
| AC4 | TS-2 (docstring), TS-6 (nothing outside the docstring changes) |
| AC5 | TS-3 |
| AC6 | TS-4 (baseline (0, 2, 10)), TS-6 (the (0, 2, 0) module untouched) |
| AC7 | TS-4 |
| AC8 | TS-5 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-1, TS-6 |
| FR5 | task0001 | TS-2, TS-6 |
| FR6 | task0002 | TS-3 |
| FR7 | task0002 | TS-3 |
| FR8 | task0001 | TS-4, TS-6 |
| FR9 | task0001 | TS-4 |
| NFR1 | task0001, task0002 | TS-5 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-6 |

## E2E Testing

Not applicable. SPEC.md records no existing E2E tests and no E2E run
command.

## Manual Testing (E2E Not Possible)

- [ ] Read the rewritten agents.jsonl paragraph of `workflow-schema.md`
  next to `implement-phase.md`'s Supporting cast (Agent index writer bullet
  with its Orchestrator-side read, SubagentStop failure net, stop-tool
  recorder) and I.2.b step 1: the paragraph agrees on readers, purpose and
  absence behavior, and restates no rule beyond the two one-line
  "ambiguous" definitions FR4 requires.
- [ ] Read the new `queue_agent_index.py` module docstring next to the
  schema paragraph: both describe the same readers and purpose.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests | 4 (TS-1 to TS-4) | 4 | 0 | 0 |
| Integration | 2 (TS-5, TS-6) | 2 | 0 | 0 |
| Documentation reading | 2 | 0 | 0 | 2 |
