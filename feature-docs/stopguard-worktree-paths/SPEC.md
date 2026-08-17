# Feature: stopguard-worktree-paths

## Overview

`em-workflow/hooks/queue_stop_guard.py` is the refill net that blocks a Stop
event while an in-progress feature still has launchable implement tasks. Under
the Branch & Worktree Model that `em-workflow/references/implement-phase.md`
fixes as SSOT, `feature-docs/{feature}/` exists only inside the integration
worktree, so the hook's root-relative path construction can never resolve
`workflow.yaml` and `journal.jsonl` at the same time and the net has never once
fired. This feature replaces path construction with pair-based resolution,
enumerates the integration-worktree layout from a cwd ancestor walk, and adds a
freshness filter that excludes abandoned integration worktrees — without adding
any path on which a session is wrongly blocked.

Requirements source: `feature-docs/stopguard-worktree-paths/REQUIREMENTS.md`.

## Objectives

- **OBJ1** — Make `em-workflow/hooks/queue_stop_guard.py` actually fire in real
  operation. Under the Branch & Worktree Model SSOT, `feature-docs/{feature}/`
  exists only inside the integration worktree, so the hook's current
  root-relative path construction can never resolve `workflow.yaml` and
  `journal.jsonl` at the same time; the refill net has never once fired.
- **OBJ2** — Keep the hook a fail-open net rather than an authority: the change
  adds no path on which a session is wrongly blocked, and every unexpected state
  still exits 0 silently.
- **OBJ3** — Derive feature identity exactly once. The reverted attempt
  (827d223 → db91387) enumerated feature names from a `feature-docs/*` wildcard
  and then rebuilt the path on the resolution side, so the file enumerated and
  the file read could differ. Enumeration and resolution must share one
  derivation.

## User Stories

### US1: The refill net fires from the main tree
As a Claude Code session running the implement phase, I want a Stop event whose
cwd is anywhere in the main tree to resolve the in-progress feature's
`workflow.yaml` and `journal.jsonl`, so that remaining launchable tasks actually
block the Stop instead of the net silently never firing.

**Acceptance Criteria:**
- [ ] **AC1** — With a fixture reproducing the real layout (`workflow.yaml`
      inside the integration worktree, `journal.jsonl` in the feature directory
      one level above it), a Stop event whose cwd is the main tree resolves both
      files and emits the expected BLOCK line naming feature, `free_slots` and
      the ascending task list, exit code 2.
- [ ] **AC2** — The same fixture with cwd set inside the integration worktree
      produces the identical decision, because the ancestor walk resolves to the
      same worktrees root.

### US2: Abandoned integration worktrees never block
As a Claude Code session, I want a feature whose integration worktree has been
abandoned to be excluded from the active set, so that a stale `in_progress`
implement step cannot block a Stop indefinitely.

**Acceptance Criteria:**
- [ ] **AC3** — A feature whose freshness mtime is older than 24 hours produces
      no block (exit 0) even though its implement step reads `in_progress` and
      refillable work exists; the same feature with a fresh mtime blocks.
- [ ] **AC4** — `journal.jsonl` absent and `workflow.yaml` fresh — the fallback
      mtime keeps the feature active; `journal.jsonl` absent and `workflow.yaml`
      stale — the feature is excluded.

### US3: One enumeration path, one feature-identity derivation
As a maintainer of the queue hooks, I want a single enumeration layout and a
single derivation of feature identity, so that the structural defect that caused
the earlier revert cannot recur.

**Acceptance Criteria:**
- [ ] **AC5** — A `workflow.yaml` placed only at
      `{root}/feature-docs/{feature}/workflow.yaml` with implement `in_progress`
      is never enumerated and never blocks.
- [ ] **AC6** — Every previously existing behavior of the hook — failed-task
      pass-through, recycled-task-id carve-out, free-slot arithmetic, sidecar
      fingerprint and the three-block cap, fail-open on missing/garbled inputs —
      is unchanged under the migrated fixture.
- [ ] **AC7** — No git subprocess is spawned on the Stop path, and
      `queue_stop_guard.py` imports only standard-library modules.
- [ ] **AC8** — `python3 -m unittest discover -s tests` passes, with the
      real-layout tests added to `tests/test_queue_stop_guard.py`.
- [ ] **AC9** — `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` carry the same bumped version in this
      change.

## Technical Requirements

### Functional Requirements

- **FR1 — Pair-based resolution of workflow.yaml and journal:**
  `evaluate_feature` no longer constructs
  `{root}/feature-docs/{feature}/workflow.yaml` (`queue_stop_guard.py:258`).
  Enumeration hands it an already-resolved pair — the feature identity together
  with the exact `workflow.yaml` path that was found — and it reads that path
  verbatim. The journal directory is derived from the same enumerated path's
  worktree-side segment, `{worktrees_root}/{feature}`, which is also where
  `journal.jsonl` and `stop-guard-state.json` already live
  (`queue_stop_guard.py:266` keeps that location; only the way it is reached
  changes). The file enumerated and the file read are therefore identical by
  construction, and the `feature-docs/*` wildcard inside the enumerated path is
  never used as a source of feature identity.
  Status: `resolved`.

- **FR2 — In-progress features are enumerable from the main tree:** A Stop event
  whose cwd is anywhere in the main tree enumerates every feature whose
  implement step is `in_progress`, by globbing the integration-worktree layout
  `{worktrees_root}/*/integration/feature-docs/*/workflow.yaml`.
  `active_features` returns (feature identity, `workflow.yaml` path) pairs rather
  than bare feature names, and the hook reaches a real block/no-block decision
  for those features. Feature ordering stays stable and by feature name, so the
  existing "first in-progress feature with refillable work wins" behavior is
  unchanged.
  Status: `resolved`.

- **FR3 — Freshness condition excludes abandoned integration worktrees:** A
  feature that is enumerated and whose implement step still reads `in_progress`
  is admitted to the active set only if it is fresh. Freshness is the mtime of
  `{worktrees_root}/{feature}/journal.jsonl`, falling back to the mtime of the
  enumerated `workflow.yaml` when `journal.jsonl` does not exist. A feature whose
  chosen mtime is more than 24 hours older than the current time is excluded from
  the active set and never blocks. The threshold is a single named constant. The
  check costs exactly one stat per candidate feature and adds no directory
  traversal. If neither stat can be performed, the feature is excluded — the
  undecidable case falls to the non-blocking side, matching the hook's
  net-not-authority contract.
  Status: `resolved`.

- **FR4 — Integration-worktree layout is the only enumerated layout:** The
  flat-layout enumeration `{root}/feature-docs/*/workflow.yaml`
  (`queue_stop_guard.py:311`) is removed outright; no second enumeration path
  remains. A `workflow.yaml` sitting directly under a main-tree `feature-docs/`
  is never enumerated, consistent with the SSOT that no `in_progress`
  `workflow.yaml` can exist there. Consequence for the test suite:
  `StopGuardFixture` in `tests/test_queue_stop_guard.py` currently writes
  `workflow.yaml` to `{root}/feature-docs/{feature}/workflow.yaml` and must be
  migrated to write it to
  `{root}/.claude/worktrees/em-workflow/{feature}/integration/feature-docs/{feature}/workflow.yaml`,
  keeping `journal.jsonl` and `stop-guard-state.json` at
  `{root}/.claude/worktrees/em-workflow/{feature}/`. Every existing test class in
  that file (blocking, failed-task, non-blocking states, consecutive-block cap,
  fail-open, retry-after-failure, recycled task id, round-1 regressions) inherits
  the migrated fixture; after migration no test may depend on the flat layout
  being enumerated.
  Status: `resolved`.

- **FR5 — Enumeration root comes from a cwd ancestor walk:** The enumeration root
  is obtained by walking up from the hook's cwd (self included) to the nearest
  ancestor containing `.claude/worktrees/em-workflow` and using that directory as
  the worktrees root — the identical mechanism as
  `queue_taskstop_net.find_worktrees_root` (`queue_taskstop_net.py:149`). No walk
  hit means no active feature and a silent exit 0. `find_project_root`'s
  `git rev-parse --show-toplevel` subprocess is removed from the Stop path, so
  the hook spawns no process at all. Because the queue hooks are standalone
  scripts invoked by path with no shared importable module, the walk is
  duplicated in `queue_stop_guard.py` with the same semantics as the existing
  implementation rather than factored out.
  Status: `resolved`.

### Non-Functional Requirements

- **NFR1 - Dependencies:** Python standard library only. No third-party import is
  added to `queue_stop_guard.py`; the existing stdlib-only test keeps passing.
- **NFR2 - Reliability (fail-open):** The fail-open contract is preserved without
  exception: malformed stdin, non-dict payload, unreadable or malformed
  `workflow.yaml` / `journal.jsonl`, an absent journal directory, a failed stat,
  an unreachable worktrees root, and any unhandled exception all exit 0 silently.
  No new code path can exit 2 for a condition that previously exited 0.
- **NFR3 - Performance:** Per-Stop cost stays bounded and does not grow: one glob
  over `{worktrees_root}/*/integration/feature-docs/*/workflow.yaml` plus one stat
  per enumerated feature, and one fewer subprocess than today (the git toplevel
  probe is gone). No recursive scan is introduced.
- **NFR4 - Structural invariant:** Feature identity is derived from exactly one
  place — the enumerated path — and never re-derived on the resolution side. This
  is the structural defect that caused the earlier revert, and is a
  review-blocking invariant for this feature.
- **NFR5 - Scope containment:** `queue_launch_guard.py`, `queue_failure_net.py`
  and `queue_taskstop_net.py` are not modified. The journal / sidecar location,
  the `MAX_PARALLEL_IMPLEMENTERS` slot arithmetic, the three-consecutive-block
  loop cap, and the recycled-task-id carve-out keep their current semantics.
- **NFR6 - Release:** The same change bumps `em-workflow/.claude-plugin/plugin.json`
  and the corresponding entry in `.claude-plugin/marketplace.json` to the
  identical new version; without the bump the installed plugin cache keeps serving
  the old hook and the fix does not take effect.

## Implementation Approach

### Architecture

The hook is a single standalone Python script invoked by path on the Stop event.
It has three stages; this feature changes the first two and leaves the third
untouched.

```
┌──────────────────────────────────────────────────────────┐
│ Stop event (stdin payload, cwd)                          │
├──────────────────────────────────────────────────────────┤
│ 1. Enumeration root  — cwd ancestor walk          [FR5]  │
│      nearest ancestor with .claude/worktrees/em-workflow │
├──────────────────────────────────────────────────────────┤
│ 2. Active set        — glob + in_progress + freshness    │
│      (feature, workflow.yaml path) pairs      [FR2, FR3] │
│      integration-worktree layout only              [FR4] │
├──────────────────────────────────────────────────────────┤
│ 3. Decision          — evaluate_feature(pair)     [FR1]  │
│      slot arithmetic / failed-task / recycled id / cap   │
│      UNCHANGED semantics                          [NFR5] │
└──────────────────────────────────────────────────────────┘
                     ↓                    ↓
                  exit 0            exit 2 + BLOCK line
```

**Component Diagram:**

```
find_worktrees_root(cwd)      -> worktrees_root | None            [FR5]
active_features(root)         -> [(feature, workflow_path), ...]  [FR2]
  ├── glob {root}/*/integration/feature-docs/*/workflow.yaml      [FR4]
  ├── implement step == in_progress
  └── is_fresh(feature, workflow_path)                            [FR3]
evaluate_feature(feature, workflow_path)                          [FR1]
  ├── read workflow_path verbatim (no reconstruction)      [FR1, NFR4]
  └── journal dir = {worktrees_root}/{feature}                    [FR1]
```

### Data Flow

```
Stop payload + cwd
  → ancestor walk                    → worktrees_root (or None → exit 0)
  → glob integration-worktree layout → (feature, workflow_path) pairs
  → in_progress filter               → candidate pairs
  → freshness stat (1 per candidate) → active pairs
  → stable sort by feature name      → first refillable feature
  → read workflow_path + {worktrees_root}/{feature}/journal.jsonl
  → BLOCK line on stderr, exit 2   |  no refill → exit 0
```

### Path Contract

| Artifact | Location |
|---|---|
| Enumerated `workflow.yaml` | `{worktrees_root}/{feature}/integration/feature-docs/{feature}/workflow.yaml` |
| `journal.jsonl` | `{worktrees_root}/{feature}/journal.jsonl` |
| `stop-guard-state.json` | `{worktrees_root}/{feature}/stop-guard-state.json` |
| Enumeration root | nearest cwd ancestor containing `.claude/worktrees/em-workflow` |

The journal / sidecar locations are unchanged by this feature; only the way they
are reached changes (FR1, assumption a1).

### API Design

Not applicable. The hook exposes no network or RPC surface; its only interface is
the Stop hook contract (stdin payload, stderr, exit code).

### Database Schema

Not applicable. The feature holds no persistent data model; it reads
`workflow.yaml`, `journal.jsonl` and `stop-guard-state.json` from the filesystem.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: SSOT for the Branch & Worktree
  Model that fixes where `feature-docs/{feature}/` can exist.
- `em-workflow/hooks/queue_taskstop_net.py`: the reference implementation of the
  ancestor walk (`find_worktrees_root`, `:149`). Not modified (NFR5); its
  semantics are duplicated because the queue hooks are standalone scripts with no
  shared importable module (FR5).

**External Dependencies:**
- None. Python standard library only (NFR1).

### File Structure

```
em-workflow/
├── hooks/
│   └── queue_stop_guard.py          # enumeration + resolution + freshness
└── .claude-plugin/
    └── plugin.json                  # version bump
tests/
└── test_queue_stop_guard.py         # fixture migration + real-layout tests
.claude-plugin/
└── marketplace.json                 # matching version bump
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/hooks/queue_stop_guard.py`
- `tests/test_queue_stop_guard.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Default workflow-generated entries, declared in addition to the paths above:

- `feature-docs/stopguard-worktree-paths/**`
- `test-docs/stopguard-worktree-paths/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These are
generated and owned by the phase documents and by `references/phase-state.md`;
this section cites them and restates none of their rules.

`test-docs/{feature}/**` covers
`test-docs/stopguard-worktree-paths/{T}.tests.yaml`, the per-task test record. It
is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration; they are not removed.

This declaration is a SUPERSET assertion: the actual change set observed at
verification time must be CONTAINED IN the declared set, not equal to it. A
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS1** (FR1, FR2, FR5) — Real-layout fixture, cwd = main tree root:
      `workflow.yaml` at
      `{root}/.claude/worktrees/em-workflow/{feature}/integration/feature-docs/{feature}/workflow.yaml`
      with implement `in_progress` and `task0001..task0002` declared,
      `journal.jsonl` at
      `{root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl` with no
      launched events. Expect exit 2 and a stderr BLOCK line naming the feature
      and both task ids.
- [ ] **TS2** (FR5, FR1) — Same fixture, cwd = the integration worktree
      directory. Expect the identical exit code and stderr, proving the ancestor
      walk resolves the same worktrees root from inside a worktree.
- [ ] **TS8** (FR2) — Two features enumerated at once, both `in_progress` and
      both refillable: the hook reports the first by stable feature-name
      ordering, exactly as before.

### Integration Tests

- [ ] **TS7** (FR4, NFR5) — Fixture migration regression sweep:
      `StopGuardFixture` writes to the integration-worktree path, and the existing
      test classes (`TestQueueStopGuardBlocking`, `TestQueueStopGuardFailedTask`,
      `TestQueueStopGuardNonBlockingStates`,
      `TestQueueStopGuardConsecutiveBlockCap`, `TestQueueStopGuardFailOpen`,
      `TestQueueStopGuardRetryAfterFailure`, `TestQueueStopGuardRecycledTaskId`,
      `TestQueueStopGuardReviewRound1Regressions`) pass unmodified in intent.
      Fixtures that write a journal must ensure the freshness check sees a current
      mtime, since tempfile-created files are fresh by construction.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

The project's test command is `python3 -m unittest discover -s tests` (AC8).

### Edge Cases

- [ ] **TS3** (FR1, FR3, NFR2) — Same fixture with `journal.jsonl` deleted but its
      directory present: every task counts as unlaunched and the hook still
      blocks. With the whole feature directory under `.claude/worktrees/em-workflow`
      absent: exit 0, no crash.
- [ ] **TS4** (FR3) — Freshness. (a) `journal.jsonl` mtime set to now minus 25
      hours via `os.utime` — exit 0, no block, despite an `in_progress` implement
      step and unlaunched tasks. (b) the same fixture with `journal.jsonl` mtime
      set to now — exit 2. (c) no `journal.jsonl`, `workflow.yaml` mtime set to now
      minus 25 hours — exit 0. (d) no `journal.jsonl`, `workflow.yaml` mtime set to
      now — exit 2. Boundary values are chosen well clear of the 24-hour threshold
      so the test is not clock-flaky.
- [ ] **TS5** (FR5, NFR2) — cwd is a temporary directory with no
      `.claude/worktrees/em-workflow` anywhere above it: exit 0, empty stderr, no
      exception.
- [ ] **TS6** (FR4) — Flat-layout removal:
      `{root}/feature-docs/{feature}/workflow.yaml` written with implement
      `in_progress` and no integration worktree present. Expect exit 0 — the flat
      layout is not an enumeration source.

### Performance Tests

Not applicable as a separate suite. The cost bound is asserted structurally by
NFR3 and TS9: one glob, one stat per enumerated feature, no subprocess, no
recursive scan.

### Static Assertions

- [ ] **TS9** (NFR1, NFR3, FR5) — `TestQueueStopGuardStdlibOnly` continues to
      pass, and `queue_stop_guard.py` no longer references `git` or spawns a
      subprocess on the Stop path.

## Security Considerations

- **Authentication / Authorization:** Not applicable. The hook is a local
  standalone script with no principal and no access-control surface.
- **Input Validation:** Malformed stdin, a non-dict payload, and unreadable or
  malformed `workflow.yaml` / `journal.jsonl` are all handled by exiting 0
  silently (NFR2). No input is executed or interpolated into a command — the Stop
  path spawns no subprocess at all (FR5, AC7).
- **Data Protection / XSS / SQL Injection / CSRF:** Not applicable. No user data,
  no rendered output, no database, no web surface.

## Error Handling

The hook has no error-code vocabulary; every abnormal condition resolves to a
silent exit 0 (NFR2).

| Condition | Behaviour |
|---|---|
| Malformed stdin / non-dict payload | exit 0, silent |
| Unreachable worktrees root (no ancestor walk hit) | exit 0, silent |
| Unreadable or malformed `workflow.yaml` / `journal.jsonl` | exit 0, silent |
| Absent journal directory | exit 0, silent |
| Failed freshness stat (neither stat performable) | feature excluded from the active set; exit 0 |
| Any unhandled exception | exit 0, silent |

**Error Flow:**

```
Abnormal condition → no stderr output → exit 0 (never exit 2)
```

No new code path may exit 2 for a condition that previously exited 0 (NFR2).

## Performance Optimization

### Performance Goals

- One glob per Stop over
  `{worktrees_root}/*/integration/feature-docs/*/workflow.yaml`.
- Exactly one stat per candidate feature for the freshness check; no directory
  traversal added.
- One fewer subprocess than today — the `git rev-parse --show-toplevel` probe is
  removed, leaving zero subprocesses on the Stop path.
- No recursive scan.

### Optimization Strategies

- Replace the `git rev-parse --show-toplevel` subprocess with an in-process cwd
  ancestor walk (FR5).
- Reuse the already-resolved enumerated path instead of re-deriving and
  re-stat'ing a reconstructed path (FR1).

### Caching Strategy

None. No cache is introduced.

## Success Criteria

- [ ] All functional requirements (FR1–FR5) are implemented and tested
- [ ] All test scenarios (TS1–TS9) pass
- [ ] `python3 -m unittest discover -s tests` passes (AC8)
- [ ] Fail-open contract holds without exception (NFR2)
- [ ] Feature identity is derived in exactly one place — review-blocking
      invariant (NFR4)
- [ ] `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`
      are unmodified (NFR5)
- [ ] `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
      carry the same bumped version (NFR6, AC9)
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1–FR5, NFR1–NFR6) is `resolved`; no requirement
carries `status: tbd`.

## Design Step

**Status:** skipped.

The feature's entire surface is path resolution and active-set filtering inside a
single Python Stop hook plus its unittest fixture. It has no UI, no rendered
output, no user-visible visual surface and no design-system inputs. The gate
`create-spec.design-step` resolved to `decide_autonomously` in batch mode,
adopting this recommendation without a user prompt.

## Assumptions

| ID | Assumption |
|---|---|
| a1 | The journal / sidecar location contract is unchanged: `journal.jsonl` and `stop-guard-state.json` live at `{worktrees_root}/{feature}/`, the parent of each implementer worktree, exactly as `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` derive it. This feature changes only how `workflow.yaml` is located and how features are enumerated. |
| a2 | The other three queue hooks are unaffected by this defect and are out of scope; no change is made to them. |
| a3 | The decision logic downstream of path resolution — slot arithmetic against `MAX_PARALLEL_IMPLEMENTERS`, the failed-task pass-through, the recycled-task-id carve-out, the sidecar fingerprint and the three-consecutive-block cap — keeps its current semantics; this feature touches path resolution, enumeration and the active-set filter only. |
| a4 | Because files under `em-workflow/` change, the plugin version must be bumped in the same change in both `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, and the user must restart Claude Code for the new hook to be served from the plugin cache. |
| a5 | Resolution of `requirement.abandoned-integration-worktree` (batch, codex consultation, option `journal_freshness`): the active set gains a freshness condition — `journal.jsonl` mtime, falling back to `workflow.yaml` mtime, older than 24 hours excludes the feature; undecidable stats fall to the excluded (non-blocking) side. Folded into FR3, AC3, AC4, TS4. |
| a6 | Resolution of `requirement.main-tree-flat-layout` (batch, codex consultation, option `worktree_only`): only the integration-worktree layout is enumerated; the flat-layout glob is removed and the existing test fixture migrates to the real layout. Folded into FR4, AC5, AC6, TS6, TS7. |
| a7 | Resolution of `requirement.enumeration-root-discovery` (batch, codex consultation, option `cwd_ancestor_walk`): the enumeration root is the nearest cwd ancestor containing `.claude/worktrees/em-workflow`, the same mechanism as `queue_taskstop_net.find_worktrees_root`; no git subprocess. Folded into FR5, AC2, AC7, TS2, TS5, TS9. |
| a8 | Resolution of `design-step.recommendation` (batch, decision table, option `decide_autonomously`): the analyst's skip recommendation is adopted as-is. |

## References

- Requirements document: `feature-docs/stopguard-worktree-paths/REQUIREMENTS.md`
- Hook under change: `em-workflow/hooks/queue_stop_guard.py`
- Ancestor-walk reference implementation: `em-workflow/hooks/queue_taskstop_net.py` (`:149`)
- Branch & Worktree Model SSOT: `em-workflow/references/implement-phase.md`
- Test suite: `tests/test_queue_stop_guard.py`
- Reverted prior attempt: commits 827d223 → db91387
