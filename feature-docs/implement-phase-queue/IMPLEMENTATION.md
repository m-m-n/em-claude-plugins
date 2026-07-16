# Implementation Plan: Implement Phase Queue

## Overview

Replace the implement phase's chunked-barrier parallelism with a work-queue
loop, backed by a machine-written append-only journal and three deterministic
hooks (Stop / PreToolUse / SubagentStop) that catch orchestrator discipline
failures.

## Technology Stack

- **Python 3 (stdlib only)** — the three new hook scripts (same runtime
  assumption as the existing `bash_guard.py`; no PyYAML, no third-party
  packages).
- **POSIX shell + git + flock** — `merge-task.sh` extension (unchanged
  language).
- **stdlib unittest** — test suite under repository-root `tests/`
  (`python3 -m unittest discover -s tests`, per `test/README.md`).

## Layer Structure

- **Protocol documents** (`em-workflow/references/`) — instruct the LLM
  orchestrator. May reference hooks; never depend on hook internals.
- **Hooks** (`em-workflow/hooks/`) — deterministic gatekeepers, invoked by
  Claude Code with JSON on stdin. Read protocol state (workflow.yaml,
  journal, git); never launch agents; never write workflow.yaml.
- **Scripts** (`em-workflow/scripts/`) — called by implementer agents inside
  worktrees. `merge-task.sh` is the only journal writer among them.

Dependency direction: documents → (name) hooks/scripts. Hooks and scripts
never read protocol documents.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Journal (`journal.jsonl`) | Machine-written raw event log per feature | See "Journal contract" below | task0001, task0002, task0003, task0004, task0005 |
| Task-identity discovery | Identify implementer launches/stops and their task | See "Task-identity discovery" below | task0003, task0004 |
| Stop-guard sidecar (`stop-guard-state.json`) | Persist the consecutive-block counter | Written ONLY by the Stop hook; lives next to the journal; machine-written JSON; absent = counter 0 | task0002 |
| `MAX_PARALLEL_IMPLEMENTERS = 6` | Slot cap | Constant, duplicated verbatim in implement-phase.md and the Stop hook; no override mechanism (out of scope) | task0002, task0005 |

### Journal contract (SSOT for all journal readers/writers)

- Path: `{project_root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl`
  (sibling of the per-task worktree directories; `{project_root}` = the MAIN
  working tree's top level).
- Format: one JSON object per line, append-only, never rewritten, never
  deleted. Unknown fields are ignored by readers; a malformed line is
  skipped by readers (fail-safe read), never a crash.
- Event vocabulary (field `event`; all events carry `task` = `taskNNNN` and
  `at` = RFC 3339 timestamp with offset):
  - `launched` — appended by the PreToolUse launch guard when it lets an
    implementer `Task()` call through.
  - `merged` — appended by `merge-task.sh` on merge success only (exit 0
    paths); carries `commit` = the resulting parent-branch commit SHA.
  - `failed` — appended by the SubagentStop failure net; carries `reason`
    (one line, free text).
- **State derivation rule**: a task's state is decided by its LAST event in
  file order — no event: unlaunched; `launched`: in-flight; `merged`:
  merged (terminal); `failed`: failed (user decision pending; a subsequent
  `launched` puts it back in flight — that is the retry path).
- **Append discipline**: every writer appends exactly one line while holding
  an exclusive `flock` on the journal file itself, creating parent
  directories/file if absent (opened with no-follow semantics — a symlink
  planted at the journal path never redirects the write). No
  read-modify-write, ever. The launch guard additionally runs its
  replay → decide → append sequence as ONE critical section under that same
  flock (atomic compare-and-append), so concurrent launches for the same
  task serialize and exactly one appends `launched`.
- Identifier validation before any path/derivation use: `feature` matches
  `^[a-z0-9][a-z0-9-]*$`, task ids match `^task[0-9]+$` (the implement
  phase's existing fail-closed gate, applied by every journal consumer).

### Task-identity discovery (launch guard + failure net)

Implementer prompts already begin with a `# Task assignment` block
containing `task_id: {taskNNNN}` and `worktree_path: {absolute path}` lines
(implement-phase.md Step I.2 payload — unchanged by this feature).

- An agent invocation counts as an em-workflow implementer if and only if
  its subagent type is `em-workflow:implementer` (when the hook input
  provides the type) or, failing that, its prompt/first user message
  contains a `# Task assignment` block with a valid `task_id:` line.
- The journal path is derived from the `worktree_path` line: the journal is
  `dirname(normpath(worktree_path))/journal.jsonl` — byte-identical
  derivation in both hooks. Validation is likewise identical in both hooks:
  absolute path, `..` segments rejected, internal spaces allowed (the
  parser captures the whole line remainder). If either line is missing or
  fails validation, the hook treats the agent as not-an-implementer and
  exits 0.

## Conventions

- **Fail-open hooks**: the three queue hooks are invariant NETS, not
  authorities. On any unexpected state — missing files, unparsable input,
  validation failure, no active feature — they exit 0 silently. Wrongly
  blocking a session is worse than missing one violation; the orchestrator
  protocol plus the resume guard remain authoritative. (Contrast:
  `bash_guard.py` guards a security boundary and stays fail-closed. The
  launch guard's deny is a positive detection, not a fail-closed default.)
- **Self-contained hook scripts**: each hook is one standalone Python file
  (like `bash_guard.py`); no shared module between hooks. The small
  duplication of journal-reading logic is accepted so each script stays
  independently testable and loadable.
- **workflow.yaml reading in hooks is line-based** (the established
  `bash_guard.py` pattern): the Stop hook locates active features by
  globbing `feature-docs/*/workflow.yaml` from the project root and detects
  `implement` step `in_progress` / task ids by line patterns. No YAML
  library.
- **No script writes workflow.yaml** (existing rule, unchanged): the
  journal is the machine side; workflow.yaml stays LLM-written summary SSOT.
- Timestamps follow the RFC 3339-with-offset convention everywhere.
- Test files: `tests/test_*.py`, subprocess-driven hook-contract tests per
  `test/README.md`.

## Cross-task Design Decisions

### D1: Event-sourced in-flight tracking (journal, not memory)

The in-flight set is derived by replaying the journal (last event per
task), cross-checked by the orchestrator against git actual state
(worktrees, `merge-base --is-ancestor`). The LLM never carries in-flight
state across turns from memory. Affects: task0002, task0003, task0004,
task0005.

### D2: `launched` is written by the launch guard, not the orchestrator

Keeping the journal 100% machine-written requires the launch event to come
from a deterministic component; the PreToolUse hook is the only such point
on the launch path. Consequence: if a launch is allowed by the hook but the
`Task()` call ultimately does not run, a stale `launched` line can remain —
the Stop hook's consecutive-block cap and the orchestrator's git-state
reconcile bound the damage. Affects: task0002, task0003, task0005.

### D3: Hook registration is owned by task0005

Tasks 0002–0004 deliver hook scripts; they become active only via
`hooks.json`. task0005 owns wiring all three entries (plus the existing
bash_guard entry staying intact) — the integration-wiring owner rule.
Affects: task0002, task0003, task0004, task0005.

### D4: merge-task.sh stays authoritative for "merged"

Only merge success (both the real-merge paths and the already-merged
idempotent path) appends `merged`. Identity binding is fail-closed and runs
BEFORE any merge/ref update: inside the em-workflow worktree layout,
`TASK_ID` must equal the worktree's task directory and the parent-branch
argument must be `em-workflow/{feature}/integration` — a mismatch aborts
(exit 2), preserving the invariant that every exit-0 merge in the layout
also gets its `merged` event (an exit-0 merge without the event would make
the failure net record a merged task as failed). The idempotent path ("already contained
in parent") also appends, so a retry that discovers the merge already
happened still closes the loop in the journal; readers tolerate duplicate
`merged` lines for a task (last-event rule is unaffected). Affects:
task0001, task0002, task0003, task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Stale `launched` (allowed launch that never ran) wedges a slot | Low | Medium | Stop-hook block cap (3) + orchestrator reconcile against git state; documented in implement-phase.md |
| SubagentStop input shape varies across Claude Code versions | Medium | Medium | Identity discovery falls back from agent-type field to prompt scanning; unknown shape → fail-open exit 0 |
| Concurrent journal appends corrupt lines | Low | High | flock on the journal file for every append; integration test with parallel writers (TS-6) |
| Hook crash blocks the user's session | Low | High | Fail-open convention: any unhandled state exits 0; unit tests cover missing-file/malformed-input paths |
| Protocol doc and hook constants drift (cap = 6) | Medium | Low | Constant pinned in this document; both sites reference it verbatim; review checks conformance |

## Open Questions

- [ ] None.
