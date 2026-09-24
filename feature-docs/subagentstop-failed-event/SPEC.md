# Feature: subagentstop-failed-event

## Overview

When an em-workflow implementer stops without reaching merge, the SubagentStop
failure net (`em-workflow/hooks/queue_failure_net.py`) appends exactly one
`failed` event to `journal.jsonl`, so `queue_launch_guard.py` accepts the
`implement.failed-task` retry. The failure net gains broader implementer
recognition and task identification, launch-guard-identical task-id parsing,
an atomic replay-and-append, and a per-invocation diagnostics log. Requirements
document: `feature-docs/subagentstop-failed-event/REQUIREMENTS.md`.

## Objectives

- When an em-workflow implementer stops without reaching merge, the SubagentStop failure net (`queue_failure_net.py`) appends exactly one `failed` event, so the launch guard accepts the `implement.failed-task` retry (fresh implementer dispatch into the kept worktree).
- Remove the in-repo causes that let the failure net silently skip a real implementer stop: unprefixed agent_type, missing prompt or transcript path, task assignment not in the first user message, task-id parsing that differs from the launch guard, and a non-atomic read then append.
- After the fact, it must be possible to tell "SubagentStop never fired" apart from "the hook fired but could not identify the task".

## User Stories

### US1: Retry a task whose implementer stopped without merging
As the em-workflow orchestrator, I want the failure net to record `failed` when an implementer stops without reaching merge, so that the `implement.failed-task` retry (fresh implementer dispatch into the kept worktree) passes the launch guard.

**Acceptance Criteria:**
- [ ] AC-1: For an implementer stop whose task's last event is `launched`, exactly one `failed` line is appended in each of these cases: agent_type `em-workflow:implementer`; agent_type `implementer`; agent_type absent; assignment block only in the 2nd user message; transcript path missing but agent_id resolvable through agents.jsonl.
- [ ] AC-2: A relaunch of the same task id is allowed by `queue_launch_guard.py` after the net appends `failed`.
- [ ] AC-3: `queue_failure_net.py` and `queue_taskstop_net.py` invoked concurrently and repeatedly for the SAME task leave exactly one `failed` line, and every journal line parses.
- [ ] AC-4: With a task_id line before the `# Task assignment` header, the failure net and the launch guard resolve the same task_id, which is the one after the header.
- [ ] AC-6: Existing behavior is kept: a `merged` or `failed` last event leads to no append; an explicit non-implementer agent_type (for example Explore) leads to no append; an absent journal directory leads to no append and nothing is created.

### US2: Diagnose an implementer stop after the fact
As an em-workflow user, I want one diagnostics line per failure-net invocation, so that I can tell "SubagentStop never fired" apart from "the hook fired but could not identify the task".

**Acceptance Criteria:**
- [ ] AC-5: Each identification outcome writes one diagnostics line with the matching outcome code. No diagnostics line is written when no worktrees root is found. Diagnostics write failures do not change the exit code or the journal.

## Technical Requirements

### Functional Requirements

- **FR1: Implementer recognition by agent_type** — `queue_failure_net.py` treats agent_type `em-workflow:implementer` and unprefixed `implementer` as implementer stops. Any other non-empty agent_type still means "not an implementer" and the hook does nothing (the existing `test_queue_failure_net.py:355` Explore case keeps passing). An absent or empty agent_type falls through to assignment-block and index identification, as today.
- **FR2: Assignment block found beyond the first user message** — When no inline prompt field (`prompt` / `initial_prompt` / `agent_prompt`) carries a `# Task assignment` block, the hook reads the transcript at `agent_transcript_path` and uses the FIRST user-role message whose text contains a `# Task assignment` header line. It no longer uses only the first user-role message of the transcript.
- **FR3: Agent-index fallback when prompt text is unavailable** — When no assignment block can be found (no inline prompt, missing or unreadable transcript path, or no block in any user message) and agent_type is implementer or absent, the hook resolves the task from agents.jsonl using the SubagentStop payload's `agent_id`. Resolution uses the same rules as `queue_taskstop_net.py`'s `find_task_identity`: walk up from the payload `cwd` to the nearest `.claude/worktrees/em-workflow`, the candidate-list cap, containment in the feature directory, refusal when the identifier is ambiguous across tasks, and refusal when a later launch of the same task exists. An unresolved lookup does nothing.
- **FR4: Task-id parsing identical to the launch guard** — `queue_failure_net.py` extracts `task_id` and `worktree_path` only from the text AFTER the first `# Task assignment` header line, using the same logic and regexes as `queue_launch_guard.py`'s `extract_task_assignment`. Any `task_id:` or `worktree_path:` line before the header (for example a task id quoted in a preamble) is ignored. Both files keep their own copies (the hooks are standalone and stdlib-only), and a parity test pins that the two produce identical results on the same inputs.
- **FR5: Atomic replay and append** — `queue_failure_net.py` replays the journal and appends `failed` inside ONE exclusive flock critical section on the journal file descriptor (opened `O_RDWR|O_CREAT|O_APPEND|O_NOFOLLOW`, then fsync after writing), the same way `queue_taskstop_net.py` and `queue_launch_guard.py` do. It appends only when the task's last event is not `merged` or `failed`. Running concurrently with `queue_taskstop_net.py` for the same task leaves at most one `failed` line.
- **FR6: Invocation diagnostics** — Each `queue_failure_net.py` invocation appends one JSON line to a diagnostics log that is separate from `journal.jsonl`. The log lives at the nearest `.claude/worktrees/em-workflow` directory found by walking up from the payload `cwd`, or from the resolved `worktree_path` when `cwd` yields none. The line records: RFC 3339 timestamp with offset, `hook_event_name`, `agent_id`, `agent_type`, the identification source (`inline` / `transcript` / `agent-index` / `none`), `task_id` when resolved, and one outcome code from a fixed set: `not-implementer-type`, `no-prompt-text`, `no-assignment-block`, `invalid-identity`, `index-unresolved`, `journal-dir-missing`, `already-terminal`, `appended`, `error`. `error` also records the exception class name. Prompt text is never logged. When no worktrees root can be found, or the log cannot be written (including a symlink at the log path), the hook skips the log silently. The log never changes the exit code or the journal. A missing diagnostics line alone does not distinguish a hook that did not run from a hook that ran but could not write the log.
- **FR7: Retry reachability after the net records failure** — After `queue_failure_net.py` appends `failed` for a task whose last event was `launched`, a relaunch of the same task id through `queue_launch_guard.py` is allowed and appends a new `launched` line (existing launch-guard behavior, now pinned by a test that runs the failure net first).
- **FR8: Documentation update** — `implement-phase.md`'s "SubagentStop failure net" bullet states the identification order (agent_type set, then assignment block from inline prompt or the first user message that contains one, then agent-index fallback), the atomic compare-and-append, the diagnostics log location and outcome codes, and that a missing diagnostics line alone does not distinguish a hook that did not run from a hook that ran but could not write the log. The Stale-`launched` caveat states that a stop delivering no SubagentStop event is covered by the existing extended same-session branch of I.2.b step 1's orphan-recovery attempt, without adding a writer. `queue_failure_net.py`'s module docstring is updated to match. Phrases pinned by `tests/test_stale_launched_doc_contract.py` stay intact, and the journal writer set stays unchanged.
- **FR9: Plugin version bump** — em-workflow version goes from 0.2.3 to 0.2.4 in both `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json`, in the same change.

### Non-Functional Requirements

- **NFR1 - Fail-open exit:** `queue_failure_net.py` always exits 0 and never blocks the subagent stop. It stays fail-open, with a top-level catch-all.
- **NFR2 - Standard library only:** Only Python standard library imports, in both the hook and the tests (TestStdlibOnly keeps passing). No shared module is imported from `hooks/`.
- **NFR3 - No new journal writer:** No new journal writer is added. The diagnostics log is never `journal.jsonl` and has no task-status meaning.
- **NFR4 - Unchanged `failed` line and FAILED_REASON:** The format of the `failed` journal line is unchanged (`event`, `task`, `at`, `reason`). The `FAILED_REASON` value is unchanged and stays a single-line double-quoted module constant, because `tests/test_queue_taskstop_net.py:52-59` parses it by regex.
- **NFR5 - Unchanged SubagentStop registration:** The `hooks.json` SubagentStop registration (no matcher, command `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/queue_failure_net.py`, timeout 15) is unchanged.
- **NFR6 - Symlink refusal:** Symlinks are refused at both the journal path and the diagnostics log path (`O_NOFOLLOW`).
- **NFR7 - Test suite passes:** `python3 -m unittest discover -s tests` passes.

## Implementation Approach

### Architecture

**System Architecture:**
```
Claude Code harness
  └─ SubagentStop (hooks.json, no matcher, timeout 15)
       └─ em-workflow/hooks/queue_failure_net.py
            ├─ reads:  SubagentStop payload, transcript, agents.jsonl, journal.jsonl
            ├─ writes: journal.jsonl (failed line, under exclusive flock)
            └─ writes: .claude/worktrees/em-workflow/subagent-stop-diagnostics.jsonl
```

**Component Diagram:**
```
queue_failure_net.py
  1. agent_type check                     (FR1)
  2. assignment block: inline prompt       (FR2)
       -> transcript, first user message containing the header
  3. extract_task_assignment copy          (FR4, parity with queue_launch_guard.py)
  4. agent-index fallback                  (FR3, same rules as queue_taskstop_net.py find_task_identity)
  5. flock { replay journal; append failed if last event not merged/failed }  (FR5)
  6. diagnostics line                      (FR6)

queue_launch_guard.py   -- journal writer for `launched`; relaunch allowed after `failed` (FR7)
queue_taskstop_net.py   -- concurrent `failed` writer; at most one `failed` combined (FR5)
```

### Data Flow

```
implementer stops
  → harness SubagentStop payload → queue_failure_net.py
  → identify task (agent_type → assignment block → agent index)
  → flock(journal) → replay → append `failed` (only if last event is not merged/failed) → fsync
  → append one diagnostics line (skipped silently when no worktrees root or not writable)
  → exit 0
orchestrator relaunches same task id → queue_launch_guard.py allows → new `launched`
```

### API Design

No network API. The hook's input and output files:

**Input (SubagentStop payload fields used):** `agent_type`, `agent_id`, `cwd`, `hook_event_name`, `prompt` / `initial_prompt` / `agent_prompt`, `agent_transcript_path`.

**Output 1 — journal `failed` line (format unchanged, NFR4):** fields `event`, `task`, `at`, `reason`.

**Output 2 — diagnostics line (FR6):** RFC 3339 timestamp with offset, `hook_event_name`, `agent_id`, `agent_type`, identification source (`inline` / `transcript` / `agent-index` / `none`), `task_id` when resolved, outcome code, and the exception class name when the outcome is `error`.

### Database Schema

Not applicable. Data is stored in JSON Lines files:

| File | Location | Notes |
|------|----------|-------|
| `journal.jsonl` | unchanged | `failed` line format unchanged (NFR4) |
| `subagent-stop-diagnostics.jsonl` | directly under `.claude/worktrees/em-workflow/` | not committed, no rotation (A-5); no task-status meaning (NFR3) |

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/queue_launch_guard.py`: source of `extract_task_assignment` logic and regexes copied into the failure net; parity test target (FR4). Relaunch behavior pinned after the failure net (FR7).
- `em-workflow/hooks/queue_taskstop_net.py`: `find_task_identity` resolution rules reused by the agent-index fallback (FR3); concurrent `failed` writer (FR5).
- `queue_agent_index.py` / agents.jsonl: identifier candidates matched against the payload `agent_id` (FR3, A-2).
- `em-workflow/references/implement-phase.md`: documentation target (FR8).
- `tests/test_stale_launched_doc_contract.py`: pinned phrases and journal writer set (FR8, A-7).
- `tests/test_queue_taskstop_net.py:52-59`: `FAILED_REASON` regex (NFR4, A-8).

**External Dependencies:**
- Python standard library only (NFR2).

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json        # version 0.2.4 (FR9)
├── hooks/
│   ├── queue_failure_net.py          # FR1-FR6, docstring (FR8)
│   ├── queue_launch_guard.py         # parity source (FR4), relaunch (FR7)
│   └── queue_taskstop_net.py         # identity rules (FR3), concurrency (FR5)
└── references/implement-phase.md     # FR8
.claude-plugin/marketplace.json       # em-workflow version 0.2.4 (FR9)
tests/test_queue_failure_net.py       # TS1-TS8
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/subagentstop-failed-event/**`
- `test-docs/subagentstop-failed-event/**`

`feature-docs/subagentstop-failed-event/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/subagentstop-failed-event/**` covers `test-docs/subagentstop-failed-event/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/subagentstop-failed-event/` directory at all; the declared
`test-docs/subagentstop-failed-event/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (FR1): `tests/test_queue_failure_net.py`: unprefixed agent_type `implementer` + `launched` - exactly 1 `failed`
- [ ] TS2 (FR2): assignment block in the 2nd user message of the transcript (1st user message has no block) - exactly 1 `failed`
- [ ] TS3 (FR3): transcript path missing/absent + agents.jsonl entry matching payload `agent_id` under a `cwd` inside `.claude/worktrees/em-workflow` - exactly 1 `failed`; ambiguous or stale index entry - no append
- [ ] TS4 (FR4): example `task_id: task0099` line before the header, real task after the header - `failed` recorded for the post-header task, not task0099; the same prompt fed to `queue_launch_guard.py` resolves the same task (parity)
- [ ] TS7 (FR6, NFR1, NFR6): diagnostics - one line per invocation with the outcome codes `appended` / `already-terminal` / `not-implementer-type` / `no-assignment-block` / `index-unresolved` / `journal-dir-missing`; no line when `cwd` has no worktrees root; symlinked or unwritable log path - exit 0, journal unaffected; prompt text absent from the log

### Integration Tests
- [ ] TS5 (FR5): concurrency - N subprocesses of `queue_failure_net.py` and `queue_taskstop_net.py` for the same task started together (threads) - exactly 1 `failed` line, all lines parse
- [ ] TS6 (FR7): failure net appends `failed`, then `queue_launch_guard.py` relaunch of the same task - allowed, new `launched` appended
- [ ] TS8 (FR1, FR5, NFR1): regression - existing merged / failed / Explore / missing-journal-dir / malformed-input cases stay green

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] Ambiguous or stale agent-index entry - no append (TS3)
- [ ] `task_id:` line before the `# Task assignment` header - ignored (TS4)
- [ ] Symlinked or unwritable diagnostics log path - exit 0, journal unaffected (TS7)
- [ ] No worktrees root above `cwd` - no diagnostics line (TS7)

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** Agent-index resolution checks containment in the feature directory and refuses ambiguous identifiers and identifiers with a later launch of the same task (FR3). Task-id parsing reads only text after the first `# Task assignment` header (FR4).
- **Data Protection:** Prompt text is never written to the diagnostics log (FR6). Symlinks are refused at the journal path and the diagnostics log path via `O_NOFOLLOW` (NFR6).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Diagnostics outcome codes (FR6). None of them changes the exit code, which is always 0 (NFR1).

| Code | Description | Journal effect |
|------|-------------|----------------|
| `not-implementer-type` | Non-empty agent_type other than `em-workflow:implementer` / `implementer` | none |
| `no-prompt-text` | No prompt text available | none |
| `no-assignment-block` | No `# Task assignment` block found | none |
| `invalid-identity` | Parsed task identity is invalid | none |
| `index-unresolved` | Agent-index fallback resolved no task | none |
| `journal-dir-missing` | Journal directory absent | none (nothing created) |
| `already-terminal` | Task's last event is `merged` or `failed` | none |
| `appended` | `failed` appended | one `failed` line |
| `error` | Exception caught by the top-level catch-all; exception class name recorded | none |

### Error Flow

```
Exception → top-level catch-all → diagnostics line with `error` + exception class name (skipped silently if unwritable) → exit 0
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC-1: For an implementer stop whose task's last event is `launched`, exactly one `failed` line is appended in each of these cases: agent_type `em-workflow:implementer`; agent_type `implementer`; agent_type absent; assignment block only in the 2nd user message; transcript path missing but agent_id resolvable through agents.jsonl.
- [ ] AC-2: A relaunch of the same task id is allowed by `queue_launch_guard.py` after the net appends `failed`.
- [ ] AC-3: `queue_failure_net.py` and `queue_taskstop_net.py` invoked concurrently and repeatedly for the SAME task leave exactly one `failed` line, and every journal line parses.
- [ ] AC-4: With a task_id line before the `# Task assignment` header, the failure net and the launch guard resolve the same task_id, which is the one after the header.
- [ ] AC-5: Each identification outcome writes one diagnostics line with the matching outcome code. No diagnostics line is written when no worktrees root is found. Diagnostics write failures do not change the exit code or the journal.
- [ ] AC-6: Existing behavior is kept: a `merged` or `failed` last event leads to no append; an explicit non-implementer agent_type (for example Explore) leads to no append; an absent journal directory leads to no append and nothing is created.
- [ ] AC-7: `implement-phase.md` is updated per FR8, and the version is 0.2.4 in both files.
- [ ] AC-8: `python3 -m unittest discover -s tests` passes.

## Assumptions

- **A-1:** Unprefixed agent_type `implementer` is treated as an em-workflow implementer. A same-named agent from another plugin still needs a valid assignment block and an existing journal directory before anything is written.
- **A-2:** The SubagentStop payload's `agent_id` matches one of the identifier candidates `queue_agent_index.py` records in agents.jsonl. This cannot be proven in the repo. The diagnostics log records `agent_id` so the assumption can be checked later; when it does not hold, the fallback resolves nothing (no-op).
- **A-3:** Parity with the launch guard is achieved by keeping a copy of `extract_task_assignment` in each hook plus a parity test, not a shared module, because hooks are standalone stdlib-only scripts and TestStdlibOnly rejects non-stdlib imports.
- **A-4:** Whether the harness delivers SubagentStop for background or resumable implementers is out of scope and not fixable in the repo. A non-delivered stop stays covered by the existing stale-launched recovery (`recover-orphaned-task.py` extended same-session branch). This feature only makes non-delivery observable.
- **A-5:** The diagnostics log file name is `subagent-stop-diagnostics.jsonl`, directly under `.claude/worktrees/em-workflow/`. It is not committed and has no rotation.
- **A-6:** The version bump is a patch (0.2.3 -> 0.2.4), per `core-plugin-version-bump.md`'s "behavior fix is patch" rule.
- **A-7:** The journal writer set pinned by `tests/test_stale_launched_doc_contract.py:255-263` (`merge-task.sh`, `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`, `journal-append-failed.py`) stays unchanged.
- **A-8:** The `FAILED_REASON` value and its single-line constant form stay unchanged (pinned by `tests/test_queue_taskstop_net.py:52-59`).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement is resolved.

## References

- Requirements: `feature-docs/subagentstop-failed-event/REQUIREMENTS.md`
- `em-workflow/references/implement-phase.md` ("SubagentStop failure net", "Stale-`launched` caveat")
- `em-workflow/references/batch-mode.md` (`implement.failed-task`)
- `em-workflow/hooks/queue_failure_net.py`
- `em-workflow/hooks/queue_taskstop_net.py`
- `em-workflow/hooks/queue_launch_guard.py`
