# Feature: TaskStop journal `failed` event

## Overview

When an em-workflow implementer subagent is stopped via the `TaskStop` tool, the
per-feature journal (`journal.jsonl`) currently keeps `launched` as that task's last
event, because the `SubagentStop` failure net (`em-workflow/hooks/queue_failure_net.py`)
does not record a `failed` event on that path. The launch guard
(`em-workflow/hooks/queue_launch_guard.py`) then denies relaunching the task on the
next `/em-workflow:develop`, and since the journal may only be written by
`merge-task.sh` and the queue hooks, the orchestrator cannot recover without violating
that contract.

This feature makes a `TaskStop`-initiated stop produce a journal `failed` event, so the
next develop run re-enters the task through the normal retry path. The launch guard's
double-launch protection is unchanged.

## Objectives

- Record a `failed` journal event when an implementer is stopped via `TaskStop`.
- Keep the orchestrator out of the journal-writing role entirely.
- Leave the existing `SubagentStop` failure-net behavior byte-for-byte identical.
- Preserve the fail-open, never-authoritative character of all queue hooks.

## User Stories

### US1: Resume after a deliberate mid-run stop

As an em-workflow user, I want to stop a running implementer with `TaskStop` and later
resume with `/em-workflow:develop`, so that an interrupted feature continues without
manual journal surgery.

**Acceptance Criteria:**

- [ ] After `TaskStop` on an implementer, the journal contains a `failed` event for that task.
- [ ] Re-running `/em-workflow:develop` relaunches the task through the retry path
      (launch guard allows it).
- [ ] The orchestrator writes nothing to the journal at any point.

### US2: Selective stop during parallel implementation

As an em-workflow user, I want to stop exactly one of several in-flight implementers,
so that the other tasks keep running and stay `launched` in the journal.

**Acceptance Criteria:**

- [ ] Only the stopped task gets a `failed` event.
- [ ] Other in-flight tasks' journal state is unchanged.

### US3: No regression on the existing failure path

As a maintainer, I want the `SubagentStop` failure net to behave exactly as before,
so that this change cannot destabilize the normal implement loop.

**Acceptance Criteria:**

- [ ] The existing `tests/test_queue_failure_net.py` suite passes unmodified.
- [ ] `queue_failure_net.py`'s externally observable behavior (exit code, journal
      side-effects, identity discovery rules) is unchanged.

## Technical Requirements

### Functional Requirements

- **FR1:** Determine empirically whether a `TaskStop` invocation fires the
  `SubagentStop` hook event, and whether `PreToolUse` / `PostToolUse` hooks fire for
  the `TaskStop` tool. Record the observed hook input/output payload shapes
  (which fields are present, and what identifies the stopped agent). The
  implementation mechanism of FR2/FR3 is chosen from this result; do not implement
  against a guessed payload shape.
- **FR2:** On a `TaskStop`-initiated stop of an em-workflow implementer whose task's
  last journal event is neither `merged` nor `failed`, append exactly one `failed`
  event to that feature's `journal.jsonl`, under an exclusive `flock`, with a `reason`
  string that identifies the stop as `TaskStop`-initiated and is distinguishable from
  the `SubagentStop` net's existing reason string.
- **FR3:** Resolve the stopped agent to an em-workflow `taskNNNN` and its journal path.
  The `TaskStop` tool input identifies the agent by a harness agent identifier, not by
  em-workflow task identity, so a mapping from harness agent identifier to
  (`task_id`, `worktree_path`) must be established at launch time and consulted at
  stop time. The mapping store lives beside the journal in the feature's worktree
  root directory and is a separate file from `journal.jsonl` — the journal's
  append-only writer-restricted contract is not extended to it.
- **FR4:** The recorder is idempotent with respect to the existing failure net: replay
  the journal for the task before appending, and append nothing when the last event is
  already `merged` or `failed`. If both the `SubagentStop` net and the `TaskStop`
  recorder fire for the same stop, exactly one `failed` line results.
- **FR5:** Every failure to identify the stopped agent, resolve the mapping, locate
  the journal directory, or read/write the journal results in a silent exit 0 with no
  journal write — the same behavior the system has today (no regression, no fabricated
  state).
- **FR6:** Register any new hook in `em-workflow/hooks/hooks.json` using the same
  `${CLAUDE_PLUGIN_ROOT}`-relative `python3` command form and a 15-second timeout as
  the existing entries.
- **FR7:** Update `em-workflow/references/implement-phase.md` (Supporting cast: the
  hook inventory, and the Stale-`launched` caveat) and
  `em-workflow/references/workflow-schema.md` (the journal writer list) so the
  documented set of journal writers matches the implementation.

### Non-Functional Requirements

- **NFR1 - Reliability:** All queue hooks remain fail-open nets, never authorities. A
  new hook must never block a stop, never raise out of `main()`, and must exit 0 on
  every unexpected state (this is enforced by a top-level catch-all, not only by
  careful coding).
- **NFR2 - Security:** Input validation matches the existing hooks: `task_id` must
  match `^task[0-9]+$`; a worktree path must be absolute and must not contain a `..`
  path segment. Journal and mapping-store files are opened with `O_NOFOLLOW` so a
  planted symlink cannot redirect a write.
- **NFR3 - Compatibility:** Python 3.14 standard library only; no new external
  dependencies. On a Claude Code version where the required hook event or payload
  field is absent, the system degrades to today's behavior rather than misbehaving.
- **NFR4 - Concurrency:** Journal appends happen inside an exclusive `flock` critical
  section covering replay-decide-append, so concurrent stops of different tasks cannot
  interleave into a corrupt or duplicated record. A stop of one task never mutates
  another task's journal state.
- **NFR5 - Testability:** New hooks are tested as subprocesses fed JSON on stdin,
  asserting on exit code and journal side-effects, per `test/README.md`. Tests live in
  the repository-root `tests/` directory as `test_*.py` and use `unittest`.

## Implementation Approach

### Architecture

The implement phase's journal is written by four kinds of writer after this change:

```
merge-task.sh                    -> merged
queue_launch_guard.py  (PreToolUse Task|Agent)   -> launched
queue_failure_net.py   (SubagentStop)            -> failed  (natural/crashed stop)
<new recorder>         (TaskStop-triggered)      -> failed  (deliberate stop)   [new]
```

The orchestrator remains a non-writer.

### Data Flow

```
Agent launch  -> launch guard appends `launched`
              -> mapping store records agent-identifier -> (task_id, worktree_path)

TaskStop      -> recorder resolves agent identifier via mapping store
              -> replays journal for task_id
              -> appends `failed` unless last event is merged/failed
```

### Mapping store

A per-feature sidecar file in the feature's worktree root directory
(`{project_root}/.claude/worktrees/em-workflow/{feature}/`), sibling to
`journal.jsonl`. It is append-only JSONL, machine-written, and carries at minimum the
harness agent identifier, `task_id`, and `worktree_path`. Lookup by agent identifier
scans the mapping stores of the features present under
`{project_root}/.claude/worktrees/em-workflow/*/` — the stop-side hook input is not
required to name the feature.

The file is diagnostic plumbing, not part of the journal contract: it may be
regenerated or absent, and its absence degrades the recorder to a no-op (FR5).

### File Structure

```
em-workflow/
├── hooks/
│   ├── hooks.json                  # register the new hook (FR6)
│   ├── queue_launch_guard.py       # may also write the mapping store (FR3)
│   ├── queue_failure_net.py        # UNCHANGED behavior (US3)
│   └── <new recorder>.py           # TaskStop -> journal failed (FR2)
├── references/
│   ├── implement-phase.md          # Supporting cast update (FR7)
│   └── workflow-schema.md          # journal writer list update (FR7)
tests/
└── test_<new recorder>.py          # subprocess-driven hook tests (NFR5)
```

Exact file names and the choice of hook event(s) are determined by FR1's findings and
fixed during the create-plan step.

## Test Scenarios

### Unit Tests

- [ ] Stop event for an em-workflow implementer with last event `launched` — one
      `failed` line appended, exit 0.
- [ ] Stop event with last event `merged` — nothing appended, exit 0.
- [ ] Stop event with last event `failed` — nothing appended, exit 0 (idempotency).
- [ ] Stop event for a non-implementer agent — nothing appended, exit 0.
- [ ] Mapping store missing / carries no entry for the agent identifier — nothing
      appended, exit 0.
- [ ] Journal directory absent — nothing appended, exit 0, directory not created.
- [ ] Malformed JSON on stdin — exit 0, no output, no journal write.
- [ ] Invalid `task_id` (not `^task[0-9]+$`) in the mapping entry — nothing appended.
- [ ] Relative or `..`-containing worktree path in the mapping entry — nothing appended.
- [ ] The appended line's shape matches the journal event schema
      (`event` / `task` / `at` RFC 3339 with offset / `reason`).

### Integration Tests

- [ ] Three tasks `launched`; a stop for one of them appends `failed` for that task
      only; the other two tasks' last events remain `launched`.
- [ ] `SubagentStop` net and the `TaskStop` recorder both run for the same task — the
      journal ends with exactly one `failed` line for it.
- [ ] Journal state after a recorded `failed` is accepted by `queue_launch_guard.py`
      as a retry-path allow (guard appends `launched` and emits no deny decision).
- [ ] `hooks.json` parses and registers the new hook with the expected matcher and
      timeout (extend `tests/test_hooks_registration.py` coverage).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Manual scenario (recorded in VERIFICATION.md): launch an implementer, stop it via
      `TaskStop`, confirm the journal `failed` line, then confirm a develop re-entry is
      not denied by the launch guard.

### Edge Cases

- [ ] Concurrent stops of two different tasks — both `failed` lines land, neither is
      truncated or interleaved (flock discipline).
- [ ] Mapping store containing a stale entry for an already-merged task — replay
      suppresses the append.
- [ ] Symlink planted at the journal or mapping-store path — the write is refused
      (`O_NOFOLLOW`), hook still exits 0.
- [ ] A `TaskStop` targeting an agent that is not an em-workflow implementer but whose
      identifier collides with nothing in the mapping store — no-op.

### Performance Tests

Not applicable. The hook runs once per stop and reads at most one journal plus the
mapping stores under a single project root; the existing 15-second hook timeout is
ample.

## Security Considerations

- **Input Validation:** `task_id` matched against `^task[0-9]+$`; worktree paths must
  be absolute with no `..` segment. Malformed input is discarded, never sanitized into
  something usable.
- **Data Protection:** File opens use `O_NOFOLLOW`; journal appends hold an exclusive
  `flock`. No file outside the feature's worktree root directory is written.
- **Untrusted input:** Hook stdin is treated as untrusted structured data — no value
  from it is interpolated into a shell command; the hook executes no subprocesses.

## Error Handling

There is no user-facing error surface. Every abnormal condition maps to "exit 0, write
nothing":

| Condition | Handling |
|---|---|
| Malformed stdin JSON | exit 0, no output |
| Agent identifier absent or unresolvable | exit 0, no output |
| Mapping store missing / unreadable | exit 0, no output |
| Journal directory missing | exit 0, no output, no directory created |
| Journal unreadable or unwritable | exit 0, no output |
| Any unhandled exception | caught at top level, exit 0 |

## Success Criteria

- [ ] All functional requirements are implemented and tested.
- [ ] All test scenarios pass (`python3 -m unittest discover -s tests`).
- [ ] The four acceptance criteria from the originating task are satisfied.
- [ ] `queue_failure_net.py`'s behavior is unchanged and its existing tests pass.
- [ ] Documentation (`implement-phase.md`, `workflow-schema.md`) matches the
      implemented writer set.

## Assumptions

Recorded per batch-mode discipline: this feature was specified without user dialogue,
and the Codex consultation loop was skipped because `codex` is not installed on this
machine. The following decisions were made by the specifying agent, not confirmed by
the user.

- **A1 — Mechanism:** The stop is captured by hooking the `TaskStop` tool call rather
  than by loosening `queue_launch_guard.py`. Rationale: the originating task explicitly
  scopes guard-logic relaxation out, and the journal-writer contract permits hooks as
  writers. FR1's investigation may show the `SubagentStop` net already fires and merely
  fails identity discovery; in that case fixing the identity discovery inside
  `queue_failure_net.py` is the preferred implementation, subject to US3 (no behavior
  change on the existing path) being re-interpreted as "no change for inputs that
  already resolved correctly".
- **A2 — Mapping store:** An agent-identifier→task mapping sidecar is assumed to be
  necessary because `TaskStop`'s input names the agent by harness identifier. If FR1
  finds that the stop-side hook input already carries the implementer's prompt or
  transcript path (as `SubagentStop` does), the mapping store is unnecessary and must
  be dropped rather than built.
- **A3 — Mapping store location:** Beside `journal.jsonl` in the feature's worktree
  root directory, as a separate file, so the journal's writer-restriction and
  append-only-forever guarantees are not diluted.
- **A4 — Scope of documentation updates:** Limited to `implement-phase.md` and
  `workflow-schema.md`. Plugin `version` bump handling follows the repository's
  patch-bump convention in `em-workflow/.claude-plugin/plugin.json`.
- **A5 — No design step:** This feature has no user-visible UI surface, so the
  `design` step is skipped.
- **A6 — Project components:** No build or format command exists in this repository;
  the test command is `python3 -m unittest discover -s tests` per `test/README.md`.
- **A7 — License:** No `LICENSE` file exists at the repository root, so
  `project.license` is recorded as `none`.

## References

- Originating task: [https://www.notion.so/3ab3509ec8ee81759577e03ff305b12c](https://www.notion.so/3ab3509ec8ee81759577e03ff305b12c)
- `feature-docs/taskstop-journal-failed-event/REQUIREMENTS.md`
- `em-workflow/references/implement-phase.md` — Supporting cast, Stale-`launched` caveat
- `em-workflow/references/workflow-schema.md` — journal writer contract
- `feature-docs/implement-phase-queue/IMPLEMENTATION.md` — Journal contract,
  Task-identity discovery contract
