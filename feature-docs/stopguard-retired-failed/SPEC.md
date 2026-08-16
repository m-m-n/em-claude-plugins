# Feature: stopguard-retired-failed

## Overview

`queue_stop_guard.py` is the implement-phase Stop hook that catches a forgotten work-queue refill. It derives every task's state from the journal's last event alone, so a single `failed` event belonging to a task id that a route-back re-plan has since retired suppresses the whole feature permanently. This feature makes the hook reinterpret the exact pair (workflow.yaml `tasks.{T}.status: pending`, journal last event `failed`) as *unlaunched*, mirroring the recycled-task-id carve-out the orchestrator already applies in `implement-phase.md` I.2.a, while leaving every genuine-failure path suppressing exactly as before.

Requirements source: `feature-docs/stopguard-retired-failed/REQUIREMENTS.md`.

## Objectives

- Restore the implement-phase refill-forgetting net for features that have gone through a route-back re-plan.
- Keep the hook a net rather than an authority: introduce no new path on which the hook wrongly blocks a session.
- Keep `implement-phase.md`'s hook-scope statement consistent with the implementation.

## User Stories

### US1: The refill net fires again after a re-plan
As the em-workflow orchestrator, I want the Stop hook to still name unlaunched tasks after a route-back re-plan has recycled task ids, so that a forgotten refill is caught instead of being silenced forever by a retired id's residual `failed` event.

**Acceptance Criteria:**
- [ ] AC1: With workflow.yaml `implement: in_progress`, tasks task0001..task0003 all `status: pending`, and a journal whose only content is `failed` for task0001 (a retired id's residue), the hook exits 2 and its stderr names task0001, task0002 and task0003 as launch targets.
- [ ] AC5 (in part): an unparsable or absent per-task status exits 0 without a traceback.

### US2: A genuine failure still holds the session
As the em-workflow orchestrator, I want a genuinely failed task to keep suppressing the block, so that a pending user decision is not overridden by the hook.

**Acceptance Criteria:**
- [ ] AC2: With the same shape but task0001's workflow.yaml `status: failed`, the hook exits 0.
- [ ] AC3: With task0001 `status: in_progress` and journal last event `failed` (failure recorded, wake phase not yet reconciled), the hook exits 0.
- [ ] AC4: With a mix — task0001 `pending` + journal `failed` (retired), task0002 `failed` + journal `failed` (genuine) — the hook exits 0.

### US3: The documentation matches the code
As a developer reading `implement-phase.md`, I want its hook-scope sentence to reflect that `queue_stop_guard.py` now consults `tasks.{T}.status`, so that the SSOT does not contradict the shipped hook.

**Acceptance Criteria:**
- [ ] AC6: `implement-phase.md` no longer claims `queue_stop_guard.py` never consults `tasks.{T}.status`, and still claims it for the other three hooks.
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both read version 0.1.42.
- [ ] AC8: `python3 -m unittest discover -s tests` passes with no regression in the existing queue_stop_guard tests.

## Technical Requirements

### Functional Requirements

- **FR1 — Retired-id `failed` no longer silences the feature:** In `queue_stop_guard.py`'s `evaluate_feature`, a task whose journal last event is `failed` but whose workflow.yaml `tasks.{T}.status` is `pending` is classified as unlaunched, not failed. Such a task therefore neither contributes to the whole-feature suppression nor is excluded from the launch list. This mirrors the orchestrator's already-established recycled-task-id carve-out in `implement-phase.md` I.2.a, so the hook only ever names tasks the orchestrator itself would legitimately launch.
- **FR2 — Genuine failures still suppress blocking:** The existing whole-feature suppression (`evaluate_feature` returns `None`, hook exits 0) is retained for every task whose journal last event is `failed` and whose workflow.yaml `tasks.{T}.status` is anything other than `pending` — specifically `failed`, `in_progress`, `merged`, any unrecognized value, an absent status key, or an unparsable task block. `in_progress` + journal `failed` is the wake-phase-not-yet-reconciled case and MUST keep suppressing.
- **FR3 — Per-task status parsing stays line-based:** The per-task `status:` value is read with the same line-based technique already used for the `implement` step status and the `tasks:` key list — no YAML library, stdlib only. The read is scoped to the individual `taskNNNN:` block (its own indented keys) so a workflow-step `status:` line can never be mistaken for a task status and vice versa. A task block whose status cannot be determined yields the conservative classification of FR2.
- **FR4 — Reclassified tasks flow through the existing selection and cap machinery unchanged:** A task reclassified by FR1 participates normally in free-slot computation (`MAX_PARALLEL_IMPLEMENTERS - in_flight`), the ascending-task-id bounded launch list, the BLOCK stderr message, and the fingerprint feeding the 3-consecutive-block cap and its `stop-guard-state.json` sidecar. No new sidecar field, no new file, and no change to the cap semantics.
- **FR5 — Task ids absent from the current plan remain ignored:** A retired id that no longer appears as a key under workflow.yaml's `tasks:` mapping continues to be ignored entirely (`evaluate_feature` already iterates only over `task_ids_from_workflow`). No change is required for this case; it must not regress.
- **FR6 — `implement-phase.md`'s hook-scope sentence is amended:** The statement that `queue_launch_guard.py`, `queue_stop_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` derive a task's state from the journal's last event alone and never consult `tasks.{T}.status` is amended so that `queue_stop_guard.py` is an explicit exception applying the recycled-task-id carve-out, while the other three hooks remain journal-last-event-only. The Stop-hook bullet under "Supporting cast: journal, hooks, resume" is updated consistently.
- **FR7 — The other three hooks are untouched:** `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` are not modified. In particular `queue_launch_guard.py`'s criterion stays journal-last-event-only and a post-`failed` launch stays the legitimate retry path.
- **FR8 — Unit tests added:** `tests/test_queue_stop_guard.py` gains tests covering the retired-id case and the genuine-failure case, using the existing `StopGuardFixture` / `build_workflow_yaml` subprocess-contract style. `build_workflow_yaml` currently hard-codes `status: pending` for every task, so it gains a way to set a per-task status without breaking the existing call sites.
- **FR9 — Plugin version bump in the same change:** `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`'s em-workflow entry are both bumped from 0.1.41 to 0.1.42 (patch — behavior fix) as part of this change, with identical values in both places.

### Non-Functional Requirements

- **NFR1 — Reliability (fail-open contract preserved):** Every unexpected condition (unreadable or malformed workflow.yaml, malformed journal lines, non-JSON stdin, missing `feature-docs`, missing journal directory) continues to exit 0 silently, and no exception escapes `main()`. The new status read adds no path on which the hook can crash or block on ambiguous state.
- **NFR2 — Portability (stdlib-only imports):** `queue_stop_guard.py` continues to import only Python standard-library modules (asserted by the existing `TestQueueStopGuardStdlibOnly` test).
- **NFR3 — Data integrity (read-only with respect to the journal):** The hook keeps reading `journal.jsonl` and `workflow.yaml` only, and writes nothing except its existing `stop-guard-state.json` sidecar (atomic `mkstemp` + `os.replace`). `workflow-schema.md`'s writer-set statement for `journal.jsonl` stays true unchanged.
- **NFR4 — Performance (bounded hook latency):** Parsing stays a single line-based pass per file; no additional subprocess, network call, or filesystem scan is introduced.

## Implementation Approach

### Architecture

**System Architecture:**
```
┌─────────────────────────────────────┐
│  Claude Code Stop event (stdin JSON)│
├─────────────────────────────────────┤
│  hook_main() — per-feature loop     │
├─────────────────────────────────────┤
│  evaluate_feature()                 │
│    · implement_in_progress()        │
│    · task_ids_from_workflow()       │
│    · task_statuses_from_workflow()  │ ← new line-based read (FR3)
│    · read_journal()                 │
│    · classification (FR1 / FR2)     │
├─────────────────────────────────────┤
│  cap + sidecar (unchanged, FR4)     │
├─────────────────────────────────────┤
│  exit 0 (pass/warn) | exit 2 (BLOCK)│
└─────────────────────────────────────┘
```

**Component Diagram:**
```
workflow.yaml ──▶ implement_in_progress()   ──▶ gate: implement step in_progress
workflow.yaml ──▶ task_ids_from_workflow()  ──▶ the id set to evaluate (FR5)
workflow.yaml ──▶ per-task status read      ──▶ discriminator for FR1 / FR2
journal.jsonl ──▶ read_journal()            ──▶ last event per task
                     │
                     ▼
              classification → unlaunched | in_flight | failed
                     │
                     ▼
          free slots → bounded launch list → fingerprint → sidecar cap
```

The only behavioral change is inside `evaluate_feature`'s classification branch for the `failed` last event; every stage upstream and downstream of it is unchanged (FR4).

### Data Flow

```
Stop event → hook_main → active_features → evaluate_feature
                                              ├── workflow.yaml (steps, task ids, per-task status)
                                              └── journal.jsonl (last event per task)
                                                    ↓
                          classify → {unlaunched, in_flight, failed}
                                                    ↓
              failed non-empty? ── yes ─▶ return None ─▶ exit 0        (FR2)
                     │ no
                     ▼
        free_slots = MAX_PARALLEL_IMPLEMENTERS - len(in_flight)
        to_launch  = sorted(unlaunched)[:free_slots]                   (FR4)
                     ↓
        sidecar fingerprint/counter → BLOCK (exit 2) or WARNING (exit 0)
```

### Classification Rule

| journal last event | workflow.yaml `tasks.{T}.status` | classification | requirement |
|---|---|---|---|
| (no event) | any | unlaunched | existing behavior |
| `launched` | any | in_flight | existing behavior |
| `merged` | any | terminal, not tracked | existing behavior |
| `failed` | `pending` | **unlaunched** | FR1 |
| `failed` | `failed` | failed (suppress) | FR2 |
| `failed` | `in_progress` | failed (suppress) | FR2 |
| `failed` | `merged` | failed (suppress) | FR2 |
| `failed` | unrecognized value / key absent / block unparsable | failed (suppress) | FR2, FR3 |
| any | task id not under `tasks:` | not evaluated at all | FR5 |

### API Design

Not applicable — this feature exposes no HTTP or RPC interface. The hook's external contract is unchanged and consists of:

**Input:** the Stop hook's JSON object on stdin (`stop_hook_active` and any other keys), read fail-open.

**Output:** the process exit code plus stderr text, both byte-identical in format to today's:

```
queue_stop_guard: BLOCK feature={feature} free_slots={slots} launch={tasks}
queue_stop_guard: WARNING feature={feature} blocked {cap} consecutive times in the same state; letting the turn end — check on the implement phase.
```

| Exit code | Meaning |
|---|---|
| 0 | No block: nothing actionable, a suppressing failure, an unevaluable feature, an over-cap state, or any fail-open condition |
| 2 | BLOCK: refillable slots and unlaunched tasks exist |

### Database Schema

Not applicable — no database. The two files the hook reads and the one sidecar it writes keep their existing shapes; no workflow.yaml schema field is added or changed (A5), and no new sidecar field is introduced (FR4).

| File | Role | Change |
|---|---|---|
| `feature-docs/{feature}/workflow.yaml` | step statuses, `tasks:` id set, per-task `status` | read-only; per-task `status` newly read |
| `.claude/worktrees/em-workflow/{feature}/journal.jsonl` | append-only event log | read-only, unchanged (NFR3) |
| `.claude/worktrees/em-workflow/{feature}/stop-guard-state.json` | `fingerprint`, `counter` | unchanged fields, unchanged atomic write |

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: owns the recycled-task-id carve-out (I.2.a) that FR1 mirrors, and carries the hook-scope sentence FR6 amends.
- `tests/test_queue_stop_guard.py`: owns `StopGuardFixture` / `build_workflow_yaml`, which FR8 extends with a per-task status option.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: the two version locations FR9 bumps together.

**External Dependencies:**
- Python standard library only (NFR2). No third-party package is added.

### File Structure

```
em-workflow/
├── hooks/
│   └── queue_stop_guard.py          # FR1-FR5, NFR1-NFR4
├── references/
│   └── implement-phase.md           # FR6
└── .claude-plugin/
    └── plugin.json                  # FR9 (0.1.41 → 0.1.42)
.claude-plugin/
└── marketplace.json                 # FR9 (em-workflow entry, 0.1.41 → 0.1.42)
tests/
└── test_queue_stop_guard.py         # FR8
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/hooks/queue_stop_guard.py`
- `em-workflow/references/implement-phase.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/test_queue_stop_guard.py`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/stopguard-retired-failed/**`
- `test-docs/stopguard-retired-failed/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`,
`VERIFICATION.md`, `retrospect.yaml`, and the design artifacts the design
step produces. These are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/{feature}/**` covers `test-docs/stopguard-retired-failed/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

Run command: `python3 -m unittest discover -s tests`

### Unit Tests

- [ ] TS1 (FR1, FR4): Retired id — tasks pending, journal last `failed` for task0001 → exit 2, all three ids named.
- [ ] TS2 (FR2): Genuine failure — task0001 `status: failed` + journal `failed` → exit 0.
- [ ] TS3 (FR2): Unreconciled failure — task0001 `status: in_progress` + journal `failed` → exit 0.
- [ ] TS4 (FR1, FR2): Mixed retired + genuine → exit 0.
- [ ] TS5 (FR4): Retired id combined with in-flight tasks — `free_slots` arithmetic and the bounded ascending launch list still correct.
- [ ] TS6 (FR1, FR4): Retired id then relaunched (journal `failed` then `launched`, status `pending`) — counts as in-flight, not unlaunched.

### Integration Tests

- [ ] TS9 (FR4): Consecutive-block cap — a retired-id-derived block state still caps at 3 and re-arms on state change.
- [ ] TS10 (FR7, FR8, NFR1, NFR2): Regression sweep — full `python3 -m unittest discover -s tests`.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Not applicable — the repository has no E2E infrastructure.

### Edge Cases

- [ ] TS7 (FR2, FR3, NFR1): Task status key absent / task block malformed + journal `failed` → exit 0, no traceback.
- [ ] TS8 (FR5): Retired id no longer present under `tasks:` → ignored entirely, other tasks still evaluated.
- [ ] AC5 fail-open sweep: missing journal directory, malformed journal lines, malformed stdin, and missing `feature-docs` each exit 0 without a traceback.

### Performance Tests

- [ ] Not applicable as a separate test — NFR4 is satisfied structurally: parsing stays a single line-based pass per file, with no added subprocess, network call, or filesystem scan.

## Security Considerations

- **Authentication:** Not applicable — a local Stop hook invoked by Claude Code.
- **Authorization:** Not applicable.
- **Input Validation:** Non-JSON stdin, malformed journal lines, and a malformed or unreadable workflow.yaml are all handled fail-open (NFR1): the hook exits 0 silently, and no exception escapes `main()`.
- **Data Protection:** The hook reads `journal.jsonl` and `workflow.yaml` only and writes nothing but its existing `stop-guard-state.json` sidecar (NFR3). The sidecar write keeps its atomic `mkstemp` + `os.replace` form, which never follows a pre-planted symlink and never truncates an existing target.
- **XSS Prevention:** Not applicable — no web surface.
- **SQL Injection Prevention:** Not applicable — no database.
- **CSRF Protection:** Not applicable — no web surface.

## Error Handling

### Error Codes

The hook has no error-code vocabulary; every abnormal condition resolves to a silent exit 0 (NFR1).

| Condition | Handling | Exit code |
|---|---|---|
| Non-JSON or non-object stdin | Ignore, no output | 0 |
| workflow.yaml unreadable or malformed | Feature not evaluable, skip | 0 |
| Journal directory missing | Feature not evaluable, skip | 0 |
| Journal file missing but its directory exists | Every declared task counts as unlaunched | 0 or 2 |
| Malformed journal line | Skip that line | 0 or 2 |
| Per-task status absent or unparsable | Conservative failed classification (FR2, A4) | 0 |
| Any unexpected exception | Caught in `main()`, fail-open | 0 |

### Error Flow

```
Unexpected condition → local except / conservative classification → return None or skip → exit 0 (never a traceback, never a block)
```

## Performance Optimization

### Performance Goals

- No numeric latency target is specified. The binding constraint is NFR4: a single line-based pass per file and no added subprocess, network call, or filesystem scan.

### Optimization Strategies

- Per-task status is collected in the same line-based traversal family already used for the `implement` step status and the `tasks:` key list (FR3), so no extra file open pattern is introduced beyond what already exists.
- Classification remains a single loop over the task ids declared in workflow.yaml (FR5).

### Caching Strategy

- No cache is introduced. The existing `stop-guard-state.json` sidecar keeps its current role and fields (FR4).

## Success Criteria

- [ ] All functional requirements (FR1–FR9) are implemented and tested
- [ ] All test scenarios (TS1–TS10) pass
- [ ] AC1: retired-id case exits 2 and names task0001, task0002, task0003
- [ ] AC2: genuine failure (`status: failed`) exits 0
- [ ] AC3: `status: in_progress` + journal `failed` exits 0
- [ ] AC4: mixed retired + genuine exits 0
- [ ] AC5: fail-open intact across missing journal directory, malformed journal lines, malformed stdin, missing `feature-docs`, and unparsable/absent per-task status — all exit 0 without a traceback
- [ ] AC6: `implement-phase.md` no longer claims `queue_stop_guard.py` never consults `tasks.{T}.status`, and still claims it for the other three hooks
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both read version 0.1.42
- [ ] AC8: `python3 -m unittest discover -s tests` passes with no regression in the existing queue_stop_guard tests
- [ ] `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` are unmodified (FR7)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement (FR1–FR9, NFR1–NFR4) is `resolved`.

## Assumptions

These assumptions come from the requirements analysis; each one is recorded with its reason, impact and reversibility.

| ID | Assumption | Reason | Impact | Reversible |
|---|---|---|---|---|
| A1 | The discriminator is workflow.yaml's `tasks.{T}.status`: only the exact pair (`status: pending`, journal last event `failed`) is reinterpreted as unlaunched. | The journal is append-only, carries no re-plan/retirement marker, and the planner's `replace_all` recycles ids from `task0001` — so a journal-only discriminator does not exist even in principle. `implement-phase.md` I.2.a already defines exactly this carve-out for the orchestrator. | medium | yes |
| A2 | Amending `implement-phase.md`'s hook-scope sentence (FR6) is in scope for this feature. | The code change would otherwise contradict a live SSOT statement in the same plugin. The declared out-of-scope covers only `queue_launch_guard.py`'s criterion. | low | yes |
| A3 | The version bump is a patch: 0.1.41 → 0.1.42. | Behavior fix, no new capability, per the repository's CLAUDE.md. | low | yes |
| A4 | Unknown/unparsable per-task status is treated as failed (suppress, exit 0) rather than as pending. | The hook's fail-open contract prefers missing a violation over blocking a session on state it cannot read. | low | yes |
| A5 | No user-facing surface, CLI output format, or workflow.yaml schema field changes; the BLOCK/WARNING stderr formats stay byte-identical. | Nothing in the task description asks for them, and existing tests assert on those strings. | low | yes |

## Implementation Phases (if applicable)

### Phase 1: Hook behavior and tests
**Goals:** Implement the classification change and lock it in with tests.
**Deliverables:**
- Per-task status read scoped to the `taskNNNN:` block in `queue_stop_guard.py` (FR3)
- The FR1 / FR2 classification branch in `evaluate_feature` (FR1, FR2, FR4, FR5)
- New tests plus the `build_workflow_yaml` per-task status option in `tests/test_queue_stop_guard.py` (FR8)

### Phase 2: Documentation and version
**Goals:** Keep the SSOT and plugin metadata consistent with the shipped hook.
**Deliverables:**
- Amended hook-scope sentence and Stop-hook bullet in `em-workflow/references/implement-phase.md` (FR6)
- Version 0.1.42 in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (FR9)

## References

- Requirements document: `feature-docs/stopguard-retired-failed/REQUIREMENTS.md`
- Stop hook under change: `em-workflow/hooks/queue_stop_guard.py`
- Recycled-task-id carve-out and hook-scope statement: `em-workflow/references/implement-phase.md`
- Existing unit tests: `tests/test_queue_stop_guard.py`
- Version locations: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Repository conventions (marketplace layout, patch-level version bumps): `CLAUDE.md`
- Project license: none (no LICENSE file)
