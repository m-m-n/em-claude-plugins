# Feature: orphaned-implementer-recovery

## Overview

When a session disappears, an implementer's journal can be left with
`launched` as its final event — an "orphaned `launched`". The task stays
in-flight, the route-back gate blocks, and an unattended run ends at a
gate-rejected terminal. This feature makes the I.2.b reconcile pass detect
that state from recorded session identity plus transcript evidence, append a
`failed` event with reason `orphaned` through a new helper, and thereby merge
the orphan into the existing I.2.c failed path.

The requirement source for this document is
`feature-docs/orphaned-implementer-recovery/REQUIREMENTS.md` (Japanese); this
SPEC renders the same requirements in implementation terms and adds no
requirement of its own.

## Objectives

- Return an implementer left as an orphaned `launched` by a vanished session
  to a runnable state without human intervention.
- Merge orphaned `launched` into the existing I.2.c failed path so batch's
  `implement.failed-task` policy (kept worktree + resume guard, one retry)
  fires, closing the route the unattended run takes from route-back gate
  block to gate-rejected terminal.
- Keep the double-launch-prevention discipline (never rewrite `launched`)
  intact, admitting orchestrator-side terminal-event writes only as an
  exception limited to cases where session disappearance can be proven.

## User Stories

### US1: Automatic recovery of an orphaned `launched`

As the orchestrator running I.2.b reconcile, I want to prove that the session
that launched an implementer is gone, so that I can record `failed` (reason
`orphaned`) and let the normal failed path retry the task.

**Acceptance Criteria:**

- [ ] AC-1: At launch time, the orchestrator's `session_id` is recorded in
      `agents.jsonl` as an independent field (never inside `agent_ids`).
- [ ] AC-2: In I.2.b reconcile, for a candidate task (`launched` + worktree
      and branch present + no live agent in the Agent index) whose recorded
      `session_id` differs from the current session and whose transcript
      (`~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`) shows no
      activity newer than the current session's start, a `failed` event with
      reason `orphaned` is recorded in the journal.
- [ ] AC-3: An `orphaned` `failed` is treated as an ordinary I.2.c failed:
      batch fires `implement.failed-task`'s single retry (kept worktree,
      resume guard); interactive offers retry / route-back / abort.

### US2: Falling back to Residual when disappearance cannot be proven

As the orchestrator running I.2.b reconcile, I want to leave the journal
untouched whenever session disappearance cannot be proven, so that the
double-launch-prevention discipline is never weakened.

**Acceptance Criteria:**

- [ ] AC-4: When `session_id` is absent, identical to the current session, or
      the session's end cannot be confirmed, the previous Residual behaviour
      (journal unchanged, gate-rejected terminal) is preserved.
- [ ] AC-5: `em-workflow/references/implement-phase.md`'s I.2.b Recovery /
      Residual text and its "Supporting cast" journal-write rule, and
      `em-workflow/references/workflow-schema.md`'s journal event definition,
      are updated.
- [ ] AC-6: A unittest fixture (journal.jsonl / agents.jsonl / task worktree
      and branch / transcript) reproduces the agent-vanished-while-`launched`
      state and confirms that `failed` (reason `orphaned`) is written exactly
      once, that non-qualifying cases degrade to Residual, and that a launch
      after `failed` is permitted by the launch guard. A real develop run is
      not required.

## Technical Requirements

### Functional Requirements

- **FR1 — Recording `session_id` at launch:** When `queue_agent_index.py`
  appends one entry to `agents.jsonl`, that entry records the orchestrator's
  `session_id` as an independent field. `session_id` is not added to the
  `agent_ids` candidate list. The current entry is only
  {agent_id, agent_ids, task, worktree_path, at} and does not read the
  `session_id` the hook input carries.
- **FR2 — Detection condition for an orphaned `launched`:** In I.2.b
  reconcile, for a candidate task (journal's final event is `launched`, both
  the task worktree and the task branch exist, and live-agent resolution via
  the Agent index returns no live agent), the task is judged an orphaned
  `launched` when the `session_id` recorded in `agents.jsonl` differs from
  the current session's `session_id` and that session's transcript can be
  confirmed to contain no activity newer than the current session's start.
- **FR3 — Journal `failed(reason: orphaned)` writer helper:** For a task
  judged an orphaned `launched`, a `failed` event with reason `orphaned` is
  appended to the journal through a helper newly added under
  `em-workflow/scripts/`. The helper takes the same exclusive flock on
  journal.jsonl as `merge-task.sh`, performs replay-then-append inside one
  critical section, and is a no-op when the final event is already terminal
  (`merged` / `failed`). It is written in a unit-testable form.
- **FR4 — Downstream convergence of an orphaned failed:** A `failed` with
  reason `orphaned` is interpreted as an ordinary I.2.c failed. In batch, the
  `implement.failed-task` policy fires exactly one retry with a kept worktree
  and the I.2.a resume guard; in interactive, retry / route back to planning /
  abort are offered. `queue_launch_guard.py` already permits relaunching a
  task whose final event is `failed`, so the retry launch passes the launch
  guard.
- **FR5 — Degradation to Residual when the condition is not met:** When
  `session_id` was not recorded, the recorded `session_id` equals the current
  session, or the session's end cannot be confirmed from the transcript, the
  journal is not written and the previous Residual behaviour (journal
  unchanged, task still in-flight, route-back gate block, gate-rejected
  terminal, the task named in the report) is preserved.
- **FR6 — `session_id` format validation and transcript path containment:**
  A `session_id` read from `agents.jsonl` is used only as a comparison value
  and as the file-name element of the transcript path. It passes format
  validation before being interpolated into a path, and the assembled
  transcript path (`~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`) is
  confirmed to stay under `~/.claude/projects/` before being read.
- **FR7 — SSOT document updates:** Update
  `em-workflow/references/implement-phase.md`'s I.2.b Recovery / Residual
  rules and the journal-write rule in "Supporting cast: journal, hooks,
  resume" (currently "The orchestrator NEVER writes it"), and
  `em-workflow/references/workflow-schema.md`'s journal event definition and
  writer set (currently "No other hook, and never the orchestrator, appends
  to journal.jsonl"), so that they carry the new exception.
- **FR8 — Stating `agents.jsonl`'s scope of authority:** Keep the existing
  invariant that `agents.jsonl` is never a source of task status, and state
  in the SSOT (the Agent index writer bullet in implement-phase.md and the
  `agents.jsonl` paragraph in workflow-schema.md) that the sole exception is
  the session identity the I.2.b orphan recovery reads.
- **FR9 — Backward compatibility:** Preserve backward compatibility of
  journal events. An existing `agents.jsonl` entry without a `session_id`
  field follows the previous Residual path, and
  `queue_taskstop_net.py`'s existing matching (`agent_ids` candidate list /
  `AGENT_ID_KEYS` fallback / `MAX_AGENT_IDS_LEN` cap / containment check)
  does not change behaviour because of the added field.

### Non-Functional Requirements

- **NFR1 — Preserving the double-launch-prevention discipline:** The
  discipline of never rewriting `launched` is preserved. The terminal-event
  append exception applies only when session disappearance has been proven;
  any case that cannot be proven always falls to the Residual side
  (fail-safe direction).
- **NFR2 — Journal append exclusion discipline:** Journal appends follow the
  same discipline as the existing writers (merge-task.sh /
  queue_launch_guard.py / queue_failure_net.py / queue_taskstop_net.py): an
  exclusive flock on the journal file itself, compare-and-append with replay
  and append in one critical section, O_NOFOLLOW-equivalent symlink refusal,
  and never creating the directory.
- **NFR3 — Preserving the hook's fail-open discipline:** Adding `session_id`
  to `queue_agent_index.py` does not break the fail-open discipline. When
  `session_id` cannot be obtained or is invalid, the existing append still
  succeeds and the hook always exits 0.
- **NFR4 — Test dependency constraint:** Test code uses only the Python
  standard library (unittest, Python 3.14) and imports no third-party
  package (test/README.md). A real develop run is not required as a
  verification method.
- **NFR5 — Test placement and naming:** New tests go under the repository
  root `tests/` as `test_*.py` and are collected by
  `python3 -m unittest discover -s tests`. Hooks are verified by subprocess
  launch with stdin JSON; shell scripts are verified against a throwaway git
  repository in a tempfile (test/README.md). Real `~/.claude` state is never
  touched.
- **NFR6 — Plugin version bump:** Because files under `em-workflow/` change,
  the same change raises `version` in
  `em-workflow/.claude-plugin/plugin.json` and in the corresponding entry of
  `.claude-plugin/marketplace.json` to the same value
  (.claude/rules/core-plugin-version-bump.md).
- **NFR7 — SSOT non-duplication discipline:** Updates to implement-phase.md /
  workflow-schema.md follow the existing cite-not-restate discipline. One
  owning section is chosen; every other location cites it only.

## Implementation Approach

### Architecture

**Components:**

```
launch time
  Claude Code hook input (session_id, transcript_path)
        │
        ▼
  queue_agent_index.py ──append──▶ agents.jsonl
                                    {agent_id, agent_ids, task,
                                     worktree_path, at, session_id}

I.2.b reconcile (orchestrator)
  candidate detection ── journal final event == launched
                      ├─ task worktree and task branch exist
                      └─ Agent index live-agent resolution: none
        │
        ▼
  session identity + transcript evidence (FR2 / FR6)
        │
        ├── proven ──▶ em-workflow/scripts/<new helper> (FR3)
        │                  flock(journal.jsonl) → replay → append
        │                  failed(reason: orphaned)   [no-op if terminal]
        │                        │
        │                        ▼
        │                  I.2.c ordinary failed handling (FR4)
        │                        ├─ batch: implement.failed-task, 1 retry
        │                        │         kept worktree + resume guard
        │                        └─ interactive: retry / route-back / abort
        │
        └── not proven ──▶ Residual (FR5): journal unchanged
```

### Data Flow

```
reconcile
  → read agents.jsonl entry for the candidate task
  → validate session_id format                      (FR6; invalid → Residual)
  → compare recorded session_id vs current session  (equal → Residual)
  → assemble ~/.claude/projects/{encoded-cwd}/{session_id}.jsonl
  → confirm the path stays under ~/.claude/projects/ (FR6; else → Residual)
  → read transcript; check for activity newer than the current session start
        no newer activity → orphaned                (FR2)
        unreadable / newer activity → Residual      (FR5)
  → helper: flock(journal.jsonl) → replay → append failed(reason: orphaned)
        final event already terminal → no-op        (FR3)
```

### Data Structures

**`agents.jsonl` entry (FR1 extends the existing shape):**

| Field | Status | Description |
|---|---|---|
| `agent_id` | existing | unchanged |
| `agent_ids` | existing | candidate list; `session_id` is NOT added to it |
| `task` | existing | unchanged |
| `worktree_path` | existing | unchanged |
| `at` | existing | unchanged |
| `session_id` | added by FR1 | the orchestrator's session id, an independent field |

**Journal event (FR3 extends the existing `failed` reason set):**

| Event | Reason | Writer |
|---|---|---|
| `failed` | `orphaned` | the new `em-workflow/scripts/` helper (added) |

Existing event names are neither removed nor renamed; the change is additive
only.

### Affected Documents and Code Sites

The change touches the following sites (supplied as reference-impact context;
these sites originate no requirement of their own):

| Site | Kind | Change | Requirement |
|---|---|---|---|
| implement-phase.md "Supporting cast" **Journal** bullet ("The orchestrator NEVER writes it; only `merge-task.sh` and the journal-writing hooks below append to it"), the corresponding workflow-schema.md writer-set paragraph, and em-workflow/README.md's journal description | documentation string | rewrite | FR3, FR7 |
| implement-phase.md I.2.b step 1 Recovery / Residual block | documentation block | rewrite | FR2, FR5, FR7 |
| implement-phase.md **Stale-`launched` caveat** paragraph | documentation block | rewrite | FR2, FR7 |
| implement-phase.md **Agent index writer** (`queue_agent_index.py`) bullet and workflow-schema.md's `agents.jsonl` paragraph | documentation block | rewrite | FR1, FR8 |
| `queue_agent_index.py`'s `append_index_entry` entry dict {agent_id, agent_ids, task, worktree_path, at} | code structure | extend | FR1 |
| journal event definitions `launched` / `merged` / `failed` and the `failed` reason string set | schema definition | extend | FR3, FR7 |
| the accepted-field set on the `agents.jsonl` reader side (`entry_matches_identifier` / `candidate_list_within_cap` / `entry_contained_in_feature`) | code behaviour | compatibility check | FR9 |

Tests that hold verbatim constants for the rewritten documentation blocks —
`tests/test_implement_routeback_gate.py` (I.2.b Recovery / Residual citation
phrases, the Stale-`launched` caveat block, the Agent index writer bullet
block) — and `tests/test_queue_agent_index.py` /
`tests/test_queue_taskstop_net.py` (per-field entry assertions, the
`index_entry()` fixture helper, `TestRealAgentIndexWriterInterop`) move with
those sites. `queue_stop_guard.py`'s `KNOWN_EVENTS = ("launched", "merged",
"failed")` inspects event names only and is unaffected by the added reason.

### Dependencies

**Internal Dependencies:**

- `em-workflow/hooks/queue_agent_index.py`: writes the `session_id` FR2 reads.
- `em-workflow/scripts/merge-task.sh`: the precedent for FR3's flock /
  replay-then-append discipline.
- `em-workflow/hooks/queue_launch_guard.py`: already permits relaunching a
  task whose final event is `failed` (FR4).
- `em-workflow/hooks/queue_taskstop_net.py`: the resolution behaviour FR9
  must leave unchanged.
- `em-workflow/references/command-execution-protocol.md`: consulted at
  create-plan if the orchestrator invokes the new helper via Bash.

**External Dependencies:**

- Python standard library only (unittest, Python 3.14) for tests — no
  third-party package (NFR4).
- Claude Code's hook input JSON, which carries `session_id` and
  `transcript_path`.
- The Claude Code transcript file at
  `~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`, read-only.

### File Structure

```
em-workflow/
├── hooks/
│   └── queue_agent_index.py          # FR1: record session_id
├── scripts/
│   └── <new journal helper>          # FR3: failed(reason: orphaned)
├── references/
│   ├── implement-phase.md            # FR7, FR8
│   └── workflow-schema.md            # FR7, FR8
├── README.md                         # journal description, FR7
└── .claude-plugin/plugin.json        # NFR6
.claude-plugin/marketplace.json       # NFR6
tests/
├── test_queue_agent_index.py         # FR1, FR9
├── test_queue_taskstop_net.py        # FR9
├── test_implement_routeback_gate.py  # FR7, FR8
└── test_*<new orphan recovery tests> # FR2..FR6, AC-6
```

The helper's implementation language is deliberately left open here; see
Open Questions.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/orphaned-implementer-recovery/**`
- `test-docs/orphaned-implementer-recovery/**`

`feature-docs/orphaned-implementer-recovery/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/orphaned-implementer-recovery/**` covers
`test-docs/orphaned-implementer-recovery/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/orphaned-implementer-recovery/` directory at all; the declared
`test-docs/orphaned-implementer-recovery/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (FR1, FR2, FR3): With a fixture where the journal's final
      event is `launched`, the task worktree and branch exist, the
      `agents.jsonl` `session_id` differs from the current session, and that
      transcript has no activity at or after the current session's start,
      exactly one `failed` line with reason `orphaned` is appended to the
      journal.
- [ ] **TS-2** (FR3): Idempotency — calling the helper twice in the same
      state leaves `failed` as a single line (a no-op when the final event is
      terminal).
- [ ] **TS-3** (FR2, FR5): Degradation to Residual — the journal is unchanged
      in all three cases: (a) the `agents.jsonl` entry has no `session_id`,
      (b) the recorded `session_id` equals the current session, (c) the
      transcript is unreadable or has activity newer than the current
      session's start.

### Integration Tests

- [ ] **TS-4** (FR4): After a `failed` (reason `orphaned`) is recorded, a
      launch of the same task is permitted by `queue_launch_guard.py` and
      `launched` is appended (it is not denied).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

A real develop run is not required as a verification method (NFR4).

### Edge Cases

- [ ] **TS-5** (FR5, FR6): Path containment — with an `agents.jsonl` entry
      carrying a malformed `session_id` (path separator, `..`, empty string,
      etc.), nothing outside `~/.claude/projects/` is read, the journal is
      not written, and the flow falls to Residual.
- [ ] **TS-6** (FR1, FR9): Backward compatibility — for an existing
      `agents.jsonl` entry with no `session_id`, `queue_taskstop_net.py`'s
      resolution behaviour (match / ambiguity refusal / staleness /
      containment) is unchanged.

### Performance Tests

Not specified — the requirements carry no performance target.

## Security Considerations

- **Input Validation (FR6):** A `session_id` read from `agents.jsonl` is
  used only as a comparison value and as the file-name element of the
  transcript path, and passes format validation before being interpolated
  into a path.
- **Path containment (FR6):** The assembled transcript path
  (`~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`) is confirmed to
  stay under `~/.claude/projects/` before it is read.
- **Symlink refusal and directory creation (NFR2):** Journal appends apply
  O_NOFOLLOW-equivalent symlink refusal and never create the directory.
- **Fail-safe default (NFR1):** Any case where session disappearance cannot
  be proven falls to Residual; the terminal-event append exception applies
  only to proven cases.
- **Test isolation (NFR5):** Tests never touch real `~/.claude` state.

## Error Handling

| Condition | Handling | Requirement |
|---|---|---|
| `session_id` not recorded in the entry | Do not write the journal; Residual | FR5 |
| Recorded `session_id` equals the current session | Do not write the journal; Residual | FR5 |
| Session end not confirmable from the transcript (unreadable, or activity newer than the current session's start) | Do not write the journal; Residual | FR5 |
| Malformed `session_id` (fails format validation or escapes `~/.claude/projects/`) | Do not read outside the root; do not write the journal; Residual | FR5, FR6 |
| Journal's final event already terminal (`merged` / `failed`) | Helper is a no-op | FR3 |
| `session_id` unobtainable or invalid at hook time | The existing append still succeeds; the hook exits 0 | NFR3 |

## Success Criteria

- [ ] All functional requirements (FR1–FR9) are implemented and tested.
- [ ] All non-functional requirements (NFR1–NFR7) are satisfied.
- [ ] All test scenarios (TS-1–TS-6) pass under
      `python3 -m unittest discover -s tests`.
- [ ] AC-1 through AC-6 in
      `feature-docs/orphaned-implementer-recovery/REQUIREMENTS.md` are met.
- [ ] The SSOT documents (implement-phase.md, workflow-schema.md) are
      updated under the cite-not-restate discipline (FR7, FR8, NFR7).
- [ ] The plugin version is bumped in both locations (NFR6).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

No requirement carries `status: tbd`; FR1–FR9 and NFR1–NFR7 are all resolved.
The following implementation details were deliberately deferred to create-plan
and are recorded here as carried-forward assumptions, not as unresolved
requirements:

- [ ] The encoding rule for `encoded-cwd` in
      `~/.claude/projects/{encoded-cwd}/{session_id}.jsonl` is settled at
      create-plan / implementation.
- [ ] The source of the current session's start time used to judge "no
      activity newer than the current session's start" (the first entry of
      the current session's transcript, the hook input, or the reconcile
      execution time) is settled at create-plan. Only the proof condition
      itself — that there is no activity newer than the current session's
      start — is fixed as a requirement.
- [ ] The new helper's implementation language is undecided. The repository
      has precedents in both bash (`em-workflow/scripts/merge-task.sh`) and
      python3 (`em-workflow/scripts/validate-worker-output.py`, which depends
      on PyYAML). The only constraints are that it be unit-testable and
      follow the same flock / replay-then-append discipline as
      `merge-task.sh`; the language choice is create-plan's discretion.
- [ ] Whether the approval gate in `command-execution-protocol.md`
      (`bash_guard.py`) needs handling when the orchestrator invokes the new
      helper via Bash is confirmed at create-plan. That this is the workflow's
      own script invocation rather than a command string originating from
      `workflow.yaml` is the deciding consideration.

## References

- Requirements document: `feature-docs/orphaned-implementer-recovery/REQUIREMENTS.md`
- `em-workflow/references/implement-phase.md`: I.2.b Recovery / Residual, the
  Supporting cast journal-write rule, the Agent index writer bullet, the
  Stale-`launched` caveat (FR7, FR8)
- `em-workflow/references/workflow-schema.md`: journal event definitions and
  writer set, the `agents.jsonl` paragraph (FR7, FR8)
- `em-workflow/README.md`: the journal description (FR7)
- `em-workflow/hooks/queue_agent_index.py` (FR1),
  `queue_launch_guard.py` (FR4), `queue_taskstop_net.py` (FR9),
  `queue_stop_guard.py` (unaffected)
- `em-workflow/scripts/merge-task.sh`: flock / replay-then-append precedent (FR3)
- `em-workflow/references/command-execution-protocol.md`: Bash approval gate
- `test/README.md`: test conventions (NFR4, NFR5)
- `.claude/rules/core-plugin-version-bump.md`: version bump rule (NFR6)

## Out of Scope

Filed as separate tasks:

- WIP-commit practice for the implementer at the point its fmt/tests pass.
- Avoiding develop stop-condition 3 by classifying failure reasons.
- Graceful shutdown on the dispatcher side.

The design step is skipped: there is no UI surface — the changes are limited
to Markdown SSOT documents (implement-phase.md / workflow-schema.md), a Python
hook (`em-workflow/hooks/queue_agent_index.py`), a new helper under
`em-workflow/scripts/`, and unittests under `tests/`, with no visual artifact
and no design-system candidate.
