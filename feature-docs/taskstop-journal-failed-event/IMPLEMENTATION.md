# Implementation Plan: TaskStop journal `failed` event

## Overview

Add a second journal-`failed` writer that fires when an em-workflow implementer is
stopped through the `TaskStop` tool, plus the agent-identity index that makes such a
stop resolvable to a task. `queue_failure_net.py` and `queue_launch_guard.py` are not
behaviorally modified.

## Investigation result (FR1 — resolved during planning)

The `SubagentStop` path was probed empirically in this repository before planning, by
launching two `em-workflow:implementer` subagents whose task-assignment blocks pointed
at a throwaway journal directory:

| Probe | Stop mechanism | Journal outcome |
|---|---|---|
| `task0001` | `TaskStop` tool | `launched` only — no `failed` appended |
| `task0002` | natural completion | `launched`, then `failed` appended by `queue_failure_net.py` |

Both probes were launched identically, so identity discovery
(`agent_type` / `# Task assignment` parsing) is demonstrably working. The difference
is the stop mechanism alone.

**Conclusion**: `TaskStop` does not deliver a usable `SubagentStop` event to the
failure net. Fixing identity discovery inside `queue_failure_net.py` cannot address
this case — the fix must hang off a different trigger. This retires SPEC.md assumption
A1's alternative branch and confirms A2 (the stop-side input does not carry the
implementer's prompt or transcript, so an identity mapping is required).

## Technology Stack

- **Language**: Python 3.14, standard library only (`json`, `os`, `re`, `fcntl`,
  `datetime`, `glob`) — matching the three existing queue hooks. No new dependency,
  therefore no license check applies (`project.license: none`).
- **Test framework**: `unittest`, run as `python3 -m unittest discover -s tests`.

## Layer Structure

Three layers, unchanged in shape by this feature:

1. **Authoritative state** — `workflow.yaml` (LLM-written) and git actual state.
   Neither is touched by hooks.
2. **Machine-written raw log** — `journal.jsonl`. Writers: `merge-task.sh`,
   `queue_launch_guard.py`, `queue_failure_net.py`, and (new) the TaskStop recorder.
   Append-only; never rewritten or deleted.
3. **Diagnostic plumbing** — the (new) agent index. Not part of the journal contract:
   it may be absent, stale, or regenerated, and its absence degrades the recorder to a
   no-op.

Dependency direction is strictly downward: layer 3 is read only by layer 2's new
writer; nothing in layer 2 or 3 reads layer 1.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Agent index file | Map a harness agent identifier to an em-workflow task identity | See "Agent index contract" below | task0001 (writer), task0002 (reader) |
| Journal append discipline | Add one `failed` line without duplicating an existing terminal event | Pre: journal directory exists; the task's last event is neither `merged` nor `failed`. Post: exactly one `failed` line for that task is appended, written under an exclusive whole-file lock, with fields `event` / `task` / `at` / `reason`. On any precondition failure: no write, no error surfaced | task0002 |
| Task-identity discovery | Decide whether a subagent launch belongs to em-workflow and extract its identity | Pre: an agent-launch tool input. Post: returns a task identifier matching `^task[0-9]+$` and an absolute worktree path containing no `..` segment, or nothing. Identical acceptance rules to `queue_launch_guard.py`'s existing implementation | task0001 |
| Journal-directory derivation | Locate a feature's journal from a task worktree path | Pre: validated absolute worktree path. Post: the parent directory of the normalized worktree path; the journal is the `journal.jsonl` entry inside it. Identical to the derivation already used by both existing hooks | task0001, task0002 |

### Agent index contract

- **Location**: a file named `agents.jsonl` in the feature's worktree root directory —
  the same directory that holds `journal.jsonl`, i.e. the parent of the per-task
  worktree directories. One index per feature.
- **Format**: append-only JSONL. One object per launch, carrying at minimum: the
  harness agent identifier, the em-workflow task identifier, the task worktree path,
  and an RFC 3339 timestamp with offset.
- **Write discipline**: appended under an exclusive whole-file lock, opened with the
  symlink-refusing open flag, permissions `0o644`, created if absent. The containing
  directory is never created by the index writer — an absent directory means the
  launch is not an em-workflow implementer launch in a live feature, and the writer
  no-ops.
- **Read discipline**: the reader scans index files for entries whose agent identifier
  matches, and uses the LAST such entry (a harness identifier could in principle be
  reused; last-wins matches the journal's own last-event-wins replay convention).
  Malformed lines are skipped, never raised.
- **Discovery from the reader side**: the stop-side hook input does not name the
  feature. The reader determines the search root by walking up from the hook input's
  working directory to the nearest ancestor containing an
  `.claude/worktrees/em-workflow` directory, then examines the `agents.jsonl` of each
  feature directory one level below it. Walking stops at the filesystem root; finding
  no such ancestor is a no-op.
- **Lifecycle**: never pruned by this feature. It is diagnostic plumbing whose growth
  is bounded by the number of implementer launches in a feature.

### Journal event shape

The appended event reuses the existing journal event shape exactly: `event` set to the
failure value, `task` set to the task identifier, `at` set to an RFC 3339 timestamp
with local offset, and `reason` set to a human-readable string. The recorder's reason
string must be distinguishable from `queue_failure_net.py`'s existing reason so that a
post-mortem can tell a deliberate stop from a swallowed failure.

## Conventions

- **Hook file naming**: `em-workflow/hooks/queue_<role>.py`, mirroring the existing
  three. Test files: `tests/test_<hook module name>.py`.
- **Registration**: every hook is registered in `em-workflow/hooks/hooks.json` under
  its event, with the command form `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/<file>` and
  `timeout: 15`, matching the existing entries verbatim in shape.
- **Error policy (fail-open, mandatory)**: every hook added here is a net, not an
  authority. `main()` wraps everything in a top-level catch-all and returns 0. No
  hook prints anything on the failure path; no hook creates directories; no hook
  fabricates state. This is the same convention documented in
  `references/implement-phase.md` (Supporting cast) and enforced by the existing
  hooks' tests.
- **Validation policy**: task identifiers must match `^task[0-9]+$`; worktree paths
  must be absolute and free of `..` path segments. Values failing validation are
  discarded, never repaired.
- **No subprocess execution**: hooks in this feature execute no external commands and
  interpolate no input into a shell.
- **Docstring discipline**: each hook file opens with a module docstring stating what
  fires it, what it writes, and its fail-open guarantee — matching the existing three.

## Cross-task Design Decisions

### D1: The trigger is the `TaskStop` tool call, not a stop lifecycle event

The investigation above shows no usable stop lifecycle event reaches the hooks on this
path. The remaining observable is the `TaskStop` tool invocation itself, which the
orchestrator makes and which therefore passes through the tool-call hook events.

The recorder runs on the **post**-invocation event, not the pre-invocation one: a
pre-invocation recorder would mark a task failed before the stop is known to have
succeeded, and a failed stop would then leave a live implementer that the launch guard
would happily double-launch. Recording after the fact can only ever be late, never
wrong in that direction.

Affected tasks: task0002.

### D2: Agent identity is indexed at launch, not reconstructed at stop

The stop-side input identifies the agent by the harness's own identifier. Nothing in
that identifier encodes the em-workflow task. The launch side, by contrast, carries
the full task assignment. The index is therefore written at launch and read at stop.

The index writer is a **separate hook file** from `queue_launch_guard.py` rather than
an extension of it. Rationale: the launch guard is the sole writer of `launched` events
and runs inside a lock-protected compare-and-append critical section; adding an
unrelated second write path into that file risks the very behavior US3 protects. A
separate file on a separate event keeps the guard byte-identical.

Affected tasks: task0001, task0002.

### D3: Payload-shape tolerance instead of payload-shape assumption

The exact field layout that the harness delivers for these tool-call events could not
be observed in this environment (hook registration is read at session start, so a
newly added hook cannot be exercised in the session that adds it). Both new hooks
therefore accept more than one plausible layout:

- The **index writer** extracts the agent identifier from the tool result, accepting
  either a structured field or an identifier embedded in result text, and extracts the
  task assignment from the tool input's prompt.
- The **recorder** extracts the agent identifier from the tool input's task-identifier
  field, falling back to the corresponding field of the tool result.

When no layout matches, both hooks no-op silently (FR5). The cost of a wrong guess is
therefore exactly today's behavior, never a regression. Confirming the live payload is
a manual verification item (VERIFICATION.md), not an automated one.

Affected tasks: task0001, task0002.

### D4: Idempotency is enforced by journal replay, not by writer coordination

Both `failed` writers replay the journal for the task and decline to append when the
last event is already terminal. No cross-writer coordination beyond the shared file
lock is introduced. If a future harness version starts delivering both events for the
same stop, the result is still exactly one `failed` line.

Affected tasks: task0002.

### D5: `hooks.json` is edited by both hook tasks

Both task0001 and task0002 add their own registration entry to the same file. Tasks run
fully in parallel and file overlap is permitted; a conflict here resolves through the
implementer's parent-side-adoption protocol (adopt the parent's version of the file and
re-apply this task's entry). Each task owns exactly its own entry and must not remove
or reorder the existing three. task0003 owns verifying that all registrations are
present and consistent.

Affected tasks: task0001, task0002, task0003.

### D6: Documentation is a task, not a side effect

The set of journal writers is documented in two reference files that are themselves the
SSOT for other agents' behavior. Leaving them stale would make a future orchestrator
believe the journal has three writers. task0003 owns both edits plus the plugin patch
version bump.

Affected tasks: task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The harness does not deliver a tool-call hook event for the stop tool, or omits the agent identifier | Medium | High — the feature silently does nothing | D3 payload tolerance; fail-open so behavior is never worse than today; explicit manual verification item; the failure mode is visible (journal still shows `launched` after a stop) |
| The launch-side tool result does not expose the agent identifier | Medium | High — index stays empty, recorder no-ops | Same as above; the index writer's tests cover both a structured field and an embedded identifier |
| A stale index entry maps an identifier to an already-merged task | Low | Low | Journal replay suppresses the append (D4) |
| Index file grows unbounded | Low | Low | One line per implementer launch per feature; the directory is removed with the feature's worktrees |
| Editing `hooks.json` from two parallel tasks conflicts | Medium | Low | D5 parent-side adoption; task0003 verifies the merged result |
| A new hook raises and blocks a tool call | Low | High | Mandatory top-level catch-all returning 0, covered by a malformed-input test in each task |

## Open Questions

- [ ] The live payload shape of the launch-side and stop-side tool-call hook events is
      unverified in this environment; it must be confirmed in a fresh session after
      these hooks are registered (VERIFICATION.md manual item MV-1). This is the one
      item that automated tests cannot close.
