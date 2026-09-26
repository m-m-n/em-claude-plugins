# Feature: routeback-ssot-drift

## Overview

Aligns the agent index (`agents.jsonl`) description in `workflow-schema.md`
and the module docstring of `em-workflow/hooks/queue_agent_index.py` with
`implement-phase.md` on readers, purpose and behavior when the index is
absent. Keeps the existing I.2.b step 1 outcomes for the partial-artifact
state and the stop-tool recorder no-op, and raises the version lockstep
guard's baseline to the real base.

## Objectives

- Make the agent index description in workflow-schema.md match implement-phase.md on readers, purpose and behavior when absent.
- Keep the defined outcomes for the worktree/branch partial-artifact states and the stop-tool recorder no-op in the implement protocol.
- Bring the version lockstep guard's baseline up to the real base so that a missed version bump is caught.

## User Stories

No user stories were produced for this feature. Acceptance criteria are
listed below with the requirements they cover.

**Acceptance Criteria:**
- [ ] AC1 (FR1): The workflow-schema.md agents.jsonl paragraph names `queue_taskstop_net.py`, `queue_failure_net.py` and the orchestrator's Orchestrator-side read (cited to implement-phase.md) as readers. It does not present `queue_taskstop_net.py` as the sole reader.
- [ ] AC2 (FR2, FR3): workflow-schema.md contains neither 'exists solely to make a stop resolvable back to a task' nor 'its absence only degrades the stop-tool recorder to a no-op'. It states that absence leads to the Residual / gate-rejected terminal by citing implement-phase.md.
- [ ] AC3 (FR4): workflow-schema.md names the stop-side and orchestrator-side read rules with their owners and says their 'ambiguous' conditions differ. The orchestrator-side wording in implement-phase.md is unchanged.
- [ ] AC4 (FR5): The `queue_agent_index.py` module docstring no longer says its only job is resolving a later TaskStop. Nothing outside the docstring changes in that file.
- [ ] AC5 (FR6, FR7): implement-phase.md still contains the partial-artifact recovery sentence and the third-case (stop tool stops nothing / recorder appends no terminal event) Residual sentence.
- [ ] AC6 (FR8): `TestPluginVersionBumpedInLockstep` asserts > (0, 2, 10). `tests/test_routeback_residual_connections_version_bump.py` still uses (0, 2, 0).
- [ ] AC7 (FR9): plugin.json and the marketplace.json em-workflow entry both read 0.2.11.
- [ ] AC8 (NFR1, NFR2): `python3 -m unittest discover -s tests` exits 0.

## Technical Requirements

### Functional Requirements
- **FR1:** Schema names every agents.jsonl reader. The workflow-schema.md agents.jsonl paragraph no longer presents `queue_taskstop_net.py` at stop as the only reader. It names every reader implement-phase.md defines: the stop-tool recorder (`queue_taskstop_net.py`), the SubagentStop failure net's agent-index fallback (`queue_failure_net.py`), and the orchestrator's I.2.b step 1 recovery check through the Orchestrator-side read, including the orphan-recovery evidence chain. It cites implement-phase.md rather than restating those rules.
- **FR2:** Schema states the index's purpose. The phrase 'exists solely to make a stop resolvable back to a task' is removed from workflow-schema.md. The paragraph says the index resolves a stop or a recovery check back to a task and its worktree.
- **FR3:** Schema states behavior when the index is absent. The phrase 'its absence only degrades the stop-tool recorder to a no-op' is removed from workflow-schema.md. The paragraph says an absent or stale index also makes the Orchestrator-side lookup unresolvable, which leads to Residual (journal unchanged, task stays in-flight, route-back gate blocks, gate-rejected terminal). It also says orphan recovery stops at `no-agent-entry`. Both are stated by citing implement-phase.md's I.2.b Recovery / Residual block.
- **FR4:** The two 'ambiguous' conditions are told apart. implement-phase.md's orchestrator-side 'ambiguous' wording stays unchanged. workflow-schema.md names both read rules with their owners: the stop-side resolution in `queue_taskstop_net.py` / IMPLEMENTATION.md's Agent index contract, and implement-phase.md's Orchestrator-side read. It states that stop-side 'ambiguous' (the identifier matches entries of two or more distinct (agents.jsonl, task) pairs) and orchestrator-side 'ambiguous' (the selected entry names no usable candidate) are different conditions.
- **FR5:** `queue_agent_index.py` docstring matches the schema. The module docstring of `em-workflow/hooks/queue_agent_index.py` no longer says its only purpose is resolving a later `TaskStop`. It describes the readers and purpose consistently with FR1 and FR2. Only the docstring changes, not the code.
- **FR6:** Partial-artifact outcome stays defined. implement-phase.md I.2.b step 1 keeps its definition that a task whose journal last event is `launched`, with only one of task worktree and task branch present, triggers the same recovery and falls to Residual.
- **FR7:** Recorder no-op outcome stays defined. implement-phase.md I.2.b step 1 keeps its third case: when the harness stop tool stops nothing, or the stop-tool recorder does not append a terminal event, the case gets the Residual treatment.
- **FR8:** Version baseline follows the real base. In `tests/test_implement_routeback_gate.py`, `TestPluginVersionBumpedInLockstep` asserts both manifest versions are strictly greater than (0, 2, 10), replacing (0, 1, 48). The class docstring and comment history are updated. The baseline in `tests/test_routeback_residual_connections_version_bump.py` stays (0, 2, 0).
- **FR9:** Plugin version bump. `em-workflow/.claude-plugin/plugin.json` `version` and the em-workflow entry's `version` in `.claude-plugin/marketplace.json` both go from 0.2.10 to 0.2.11 in the same change.

### Non-Functional Requirements
- **NFR1 - Test suite:** `python3 -m unittest discover -s tests` passes.
- **NFR2 - Pinned phrases:** Every phrase the existing tests pin in workflow-schema.md and implement-phase.md stays present, including: 'it carries no status semantics of its own, may be absent or stale', the session_id exception sentence, the I.2.b Recovery / Residual citation, 'when the Agent index lookup is unresolvable or ambiguous, the ', and 'an unresolvable lookup (no entry for the task) or an ambiguous one (the selected entry names no usable candidate) stops nothing'.
- **NFR3 - Runtime behavior:** Hook runtime behavior does not change. Only documentation, docstrings, tests and version manifests are edited.

## Implementation Approach

### Architecture

Not applicable. The change is limited to documentation, a module
docstring, tests and version manifests (NFR3).

### Data Flow

Not applicable.

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- implement-phase.md: workflow-schema.md cites its I.2.b Recovery / Residual block and its Orchestrator-side read (FR1, FR3, FR4).
- `queue_taskstop_net.py` / IMPLEMENTATION.md's Agent index contract: owner of the stop-side read rule named in workflow-schema.md (FR4).

**External Dependencies:**
- None.

### File Structure

Files edited by this feature:

```
workflow-schema.md                                         # FR1, FR2, FR3, FR4
em-workflow/hooks/queue_agent_index.py                     # FR5 (module docstring only)
implement-phase.md                                         # FR6, FR7 (text kept; orchestrator-side 'ambiguous' wording unchanged)
tests/test_implement_routeback_gate.py                     # FR8
em-workflow/.claude-plugin/plugin.json                     # FR9
.claude-plugin/marketplace.json                            # FR9
```

`tests/test_routeback_residual_connections_version_bump.py` keeps its
(0, 2, 0) baseline (FR8).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/routeback-ssot-drift/**`
- `test-docs/routeback-ssot-drift/**`

`feature-docs/routeback-ssot-drift/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/routeback-ssot-drift/**` covers
`test-docs/routeback-ssot-drift/{T}.tests.yaml`, the per-task test record.
It is generated and owned by `implement-phase.md`; this section cites it
and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/routeback-ssot-drift/` directory at all; the declared
`test-docs/routeback-ssot-drift/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1, AC2, AC3 / FR1, FR2, FR3, FR4): A static text test on workflow-schema.md, with whitespace normalized, asserts that the three removed phrases are absent and that the reader names and the two-'ambiguous' distinction are present.
- [ ] TS2 (AC4 / FR5): A static test on `queue_agent_index.py`'s module docstring asserts that the 'Its only job is to record' stop-only claim is absent.
- [ ] TS3 (AC5 / FR6, FR7): Assert that the partial-artifact and third-case Residual sentences are present in implement-phase.md, unless an existing test already pins them.
- [ ] TS4 (AC6, AC7 / FR8, FR9): The existing `TestPluginVersionBumpedInLockstep` runs with baseline (0, 2, 10) and passes against version 0.2.11 in both manifests.

### Integration Tests
- [ ] TS5 (AC8 / NFR1, NFR2): Run `python3 -m unittest discover -s tests`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- None.

### Performance Tests
- Not applicable.

## Security Considerations

Not applicable. No runtime behavior changes (NFR3).

## Error Handling

Not applicable. No runtime behavior changes (NFR3).

## Performance Optimization

Not applicable.

## Assumptions

- A1: Items 2 and 3 of the ticket are already defined at the base revision (implement-phase.md lines 555-561 and 571-584). The feature keeps that text and does not rewrite it.
- A2: Both manifests read 0.2.10 at base, so the new baseline is (0, 2, 10) and the bump target is 0.2.11.
- A3: The test-pinned phrases listed in NFR2 are preserved.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- implement-phase.md: I.2.b step 1, Recovery / Residual block, Orchestrator-side read
- workflow-schema.md: agents.jsonl paragraph
- `em-workflow/hooks/queue_agent_index.py`
- `tests/test_implement_routeback_gate.py`
- `tests/test_routeback_residual_connections_version_bump.py`
