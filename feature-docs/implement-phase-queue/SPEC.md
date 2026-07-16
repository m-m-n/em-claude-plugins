# Feature: Implement Phase Queue

## Overview

Change the em-workflow implement phase's parallel execution model from the
current chunked-barrier scheme to a work-queue scheme: keep up to 6 tasks
in flight at all times, refilling a freed slot with the next pending task as
soon as any task completes. Reliability — the reason the current design
chose barriers — is restored mechanically via a machine-written append-only
journal plus deterministic hooks.

## Objectives

- Eliminate parallelism loss: in the chunked-barrier scheme the slowest task
  in a chunk blocks the start of the entire next chunk.
- Turn orchestrator discipline failures (forgotten refill, double launch,
  swallowed failure) from silent failures into deterministically caught ones.
- Keep the no-dependency task model unchanged (worktree independence,
  contracts fixed in IMPLEMENTATION.md, conflicts resolved by parent-side
  adoption).

## User Stories

### US1: Queue-driven implement phase
As an em-workflow user, I want freed implementer slots refilled immediately,
so that uneven task sizes do not serialize the phase.

**Acceptance Criteria:**
- [ ] Up to 6 implementers are in flight whenever pending tasks remain.
- [ ] Completion of one task triggers reconcile + refill without waiting for
      the rest of any "chunk".

### US2: Deterministic discipline enforcement
As an em-workflow user, I want protocol invariants enforced by hooks rather
than by LLM memory, so that refill omissions, double launches, and swallowed
failures are caught mechanically.

**Acceptance Criteria:**
- [ ] Ending a turn with free slots + pending tasks is blocked (exit 2) by a
      Stop hook that names the tasks to launch.
- [ ] Launching an implementer for an already in-flight task is denied.
- [ ] An implementer that stops without a journal `merged` event is recorded
      as failed.

## Technical Requirements

### Functional Requirements

- **FR1 — Queue execution loop:** Rewrite
  `em-workflow/references/implement-phase.md` Step I.2 from static chunks
  into a background-launch + notification-driven refill loop:
  1. The main session launches up to 6 implementers for pending tasks **in
     the background** (synchronous `Task()` fan-out is forbidden — it
     reintroduces the barrier) and ends its turn.
  2. When an implementer finishes, `merge-task.sh` has recorded a `merged`
     event in the journal.
  3. Woken by the completion notification, the orchestrator re-derives the
     in-flight set from the journal + actual git state (reconcile), launches
     replacements into free slots, and ends the turn again.
  4. On any failed task: stop new launches, drain in-flight tasks only, then
     ask the user via AskUserQuestion — retry / route back to planning /
     abort (identical to current I.2.c; no skip option).
  5. The phase completes when every task is `merged`.
  The trust-but-verify merge check (`git merge-base --is-ancestor`), the
  fail-closed identifier validation gate, Step I.1 (integration branch), the
  I.2.a resume guard, and per-task worktree cleanup all remain in force.

- **FR2 — Journal:** A machine-written, append-only JSONL event log at
  `{project_root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl`.
  - Writers append exactly one line per event under flock (the existing
    `$GIT_COMMON_DIR/em-workflow-merge.lock`, or the journal file itself);
    no read-modify-write, so concurrent writers are safe.
  - Event vocabulary includes at minimum `merged` (written by
    merge-task.sh, e.g.
    `{"event":"merged","task":"task0007","commit":"...","at":"..."}`) and
    `failed` (written by the SubagentStop hook). The final event vocabulary
    (e.g. a launch-tracking event for the double-launch guard) is fixed by
    the planning phase; whatever is chosen, the journal stays append-only
    and machine-written.
  - Location rationale: rides the existing gitignore-guard coverage of
    `.claude/worktrees/`; writable by absolute path from every implementer
    worktree; scoped per feature; invisible to each task worktree's git.
  - The journal is **never deleted** — it persists after the phase as a
    post-mortem primary source.
  - workflow.yaml remains the LLM-managed summary SSOT; no script ever
    writes it (Python stdlib has no YAML parser; concurrent
    read-modify-write of one YAML file is itself a race; consistent with
    bash_guard.py keeping its approval store outside the yaml).

- **FR3 — merge-task.sh journal append:** Extend
  `em-workflow/scripts/merge-task.sh` (shell, unchanged language) to append
  the `merged` event on merge success, under the flock discipline above.

- **FR4 — Stop hook (loop guard):** New Python hook. When the orchestrator
  attempts to end its turn while the implement step is `in_progress`,
  pending (unlaunched) tasks remain, and free slots exist, exit 2 and tell
  the orchestrator which tasks to launch. Do NOT block when a failed task
  exists (user decision pending). Loop cap: after 3 consecutive blocks in
  the same derived state, stop blocking — emit a warning and let the turn
  end (the user takes over). The consecutive-block counter is persisted in
  a machine-written sidecar next to the journal.

- **FR5 — PreToolUse hook (double-launch guard):** New Python hook on
  `Task` tool calls. When an `em-workflow:implementer` launch's prompt
  carries a task_id that is already in flight, deny the call. A retry after
  a recorded failure is legitimate and must not be denied.

- **FR6 — SubagentStop hook (failure net):** New Python hook. When an
  implementer subagent stops and the journal has no `merged` event for its
  task, append a `failed` event. The hook fires for ALL subagent stops, so
  it must filter to em-workflow implementers and cleanly exit 0 for
  everything else.

- **FR7 — Hook registration:** Register the three hooks in
  `em-workflow/hooks/hooks.json` alongside the existing bash_guard entry,
  using the same `${CLAUDE_PLUGIN_ROOT}` invocation pattern.

- **FR8 — Documentation:** Update the plugin README, workflow-schema.md
  (sibling-artifacts section), and implement-phase.md so the role split is
  explicit: journal.jsonl = machine-written raw event log; workflow.yaml =
  LLM-managed summary (SSOT).

### Non-Functional Requirements

- **NFR1 — No new runtime dependencies:** Hooks are Python 3 stdlib only
  (same runtime assumption as bash_guard.py); merge-task.sh stays shell
  (git plumbing + flock); no PyYAML, no yq. Any workflow.yaml reading in
  hooks uses line-based parsing (the established bash_guard.py pattern).
- **NFR2 — Concurrency safety:** All journal writes are single-line appends
  under flock; readers tolerate concurrent appenders.
- **NFR3 — Resumability:** After a dead session, state is re-derivable from
  workflow.yaml + journal + git actual state; the existing I.2.a resume
  guard keeps working. Hooks cannot save a dead session and are not asked
  to (a timeout watchdog for hung implementers is explicitly out of scope).
- **NFR4 — Testability:** A repository-root `tests/` suite runs with
  `python3 -m unittest discover -s tests` (stdlib unittest, per
  test/README.md) covering the three hooks and the merge-task.sh journal
  append.

## Implementation Approach

### Architecture

```
Orchestrator (LLM, main session)          Hooks (deterministic gatekeepers)
  launches implementers (background)  ←──  Stop hook: blocks turn-end on
  reconciles from journal + git             forgotten refill (exit 2, cap 3)
  updates workflow.yaml (summary SSOT) ←──  PreToolUse hook: denies double
                                            launch of in-flight task_id
Implementers (subagents, worktrees)   ←──  SubagentStop hook: records
  merge-task.sh → journal `merged`          `failed` when no `merged` exists
                                            
journal.jsonl (append-only, machine-written, flock-serialized)
  = raw event log; never deleted; SSOT for mechanical in-flight derivation
```

The division of labor extends the existing pattern — "protocol invariants
are enforced by hooks; the LLM complies" (bash_guard.py / command approval).
Hooks cannot start `Task()` calls; the LLM remains the launcher, and hooks
guarantee that stopping the loop is detected, not that the loop runs.

### Data Flow

```
implementer completes → merge-task.sh (flock) → journal.jsonl append
completion notification → orchestrator wakes → read journal + git state
  → reconcile in-flight → refill free slots → end turn
turn-end attempt → Stop hook reads workflow.yaml (line-based) + journal
  → block (exit 2, tasks to launch) | pass (failed exists / cap hit / done)
```

### File Structure

```
em-workflow/
├── hooks/
│   ├── bash_guard.py          # existing
│   ├── hooks.json             # + Stop / PreToolUse(Task) / SubagentStop entries
│   └── {new hook scripts}.py  # names fixed by the planning phase
├── references/
│   ├── implement-phase.md     # Step I.2 rewritten (queue loop)
│   └── workflow-schema.md     # sibling artifacts: journal role noted
├── scripts/
│   └── merge-task.sh          # + journal append on merge success
tests/                         # NEW (repo root)
└── test_*.py                  # stdlib unittest
test/README.md                 # created by this create-spec phase
```

## Test Scenarios

### Unit Tests
- [ ] merge-task.sh appends a well-formed `merged` JSONL line on merge
      success, and appends nothing on merge failure.
- [ ] Stop hook: blocks (exit 2) with task names when implement is
      in_progress + free slots + pending tasks; passes when a failed task
      exists; passes when no pending tasks remain.
- [ ] Stop hook loop cap: 3 consecutive blocks in the same state → 4th
      attempt passes with a warning.
- [ ] PreToolUse hook: denies a duplicate in-flight launch; allows a first
      launch; allows a retry after a recorded failure; ignores non-implementer
      Task calls.
- [ ] SubagentStop hook: appends `failed` when an implementer stops without
      `merged`; exits 0 silently for non-implementer subagents and for
      implementers whose `merged` event exists.

### Integration Tests
- [ ] Concurrent journal appends from parallel writers produce no torn or
      interleaved lines (flock).
- [ ] Reconcile derivation: given a journal + a throwaway git repo with task
      branches/worktrees in mixed states, the derived in-flight set matches
      expectation.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] (none — protocol-document behavior is exercised via the unit/integration
      layers above)

### Edge Cases
- [ ] Exactly 6 tasks in flight (no free slot) → Stop hook passes.
- [ ] Zero pending tasks with in-flight remaining → Stop hook passes.
- [ ] Malformed journal line → readers skip it without crashing (fail-safe
      read).
- [ ] `.claude/worktrees/em-workflow/{feature}/` absent (phase not started)
      → all hooks exit 0 silently.

## Security Considerations

- **Input Validation:** The existing fail-closed identifier gate stays:
  `feature` matches `^[a-z0-9][a-z0-9-]*$`, task ids match `^task[0-9]+$`,
  validated before interpolation into any shell command or path. Hooks
  apply the same validation to task ids parsed from prompts/journal before
  using them in paths.
- **No privilege / no network:** Hooks are local stdlib Python; they read
  workflow.yaml, the journal, and git state only.
- **Repository-controlled input discipline:** journal.jsonl lives outside
  tracked content and is machine-written; hooks treat its content as data,
  never as shell input.

## Error Handling

| Case | Handling |
|------|----------|
| Implementer stops without `merged` | SubagentStop hook appends `failed`; orchestrator stops new launches, drains in-flight, asks retry / route back to planning / abort |
| Orchestrator ends turn with refillable slots | Stop hook exit 2 with tasks to launch; after 3 consecutive identical blocks, warn and pass |
| Duplicate launch of in-flight task | PreToolUse hook denies |
| Hung implementer (no completion notification) | Out of scope (no watchdog); covered operationally by the resume guard on the next /em-workflow:develop run |
| Dead session | Resume guard (I.2.a) + reconcile from workflow.yaml + journal + git |

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] `python3 -m unittest discover -s tests` passes
- [ ] Chunk barriers no longer exist in implement-phase.md Step I.2
- [ ] No new runtime dependencies introduced
- [ ] Documentation reflects the journal / workflow.yaml role split
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Design memo: `tmp/implement-phase-queue-design-20260715.md`
- Current protocol: `em-workflow/references/implement-phase.md`
- Established hook pattern: `em-workflow/hooks/bash_guard.py`,
  `em-workflow/references/command-execution-protocol.md`
- State schema: `em-workflow/references/workflow-schema.md`
