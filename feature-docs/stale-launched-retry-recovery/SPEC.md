# Feature: stale-launched-retry-recovery

## Overview

An implementer killed by the harness stream watchdog — a stop that delivers
neither `SubagentStop` nor `TaskStop` — leaves `journal.jsonl`'s last event for
its task as `launched`. `queue_launch_guard.py` then denies every retry of that
task id permanently, and the implement phase cannot be resumed. This feature
closes exactly that hole by extending the existing I.2.b orphan-recovery
machinery (`recover-orphaned-task.py` + `journal-append-failed.py`) so that the
residual it reports today as `same-session` can, when and only when explicit
evidence is available, reach a terminal `failed` event with the new reason
value `stale-launched`.

Requirements document: `feature-docs/stale-launched-retry-recovery/REQUIREMENTS.md`
(Japanese) is the companion document; every FR/NFR id below is the same id used
there.

## Objectives

- Close exactly the residual that `recover-orphaned-task.py` reports today as
  `same-session` (its step 6: the agent index's recorded `session_id` equals the
  current session's identity, so the cross-session transcript-inactivity proof in
  steps 7-9 is structurally unavailable).
- Close it by EXTENDING the existing I.2.b orphan-recovery machinery, never by
  adding a second recovery path, so the journal's writer set stays the one
  `workflow-schema.md` already declares.
- Preserve double-launch prevention undiminished: a genuinely in-flight task must
  still be denied a relaunch, and the recovery must never convert doubt into a
  journal write.

## User Stories

### US1: Recovering a watchdog-killed task
As an em-workflow orchestrator running the I.2.b reconcile step, I want a task
whose implementer was killed by the harness stream watchdog to reach a terminal
`failed` event, so that the implement phase can be resumed instead of being
permanently wedged on a stale `launched`.

**Acceptance Criteria:**
- [ ] AC1 — A task whose journal last event is `launched`, whose worktree and
      branch both exist, whose newest `agents.jsonl` entry binds to that launch
      per D7 and records the CURRENT session's identity, for which the harness
      reports this launch's execution terminated and the `TaskStop` call reports
      that same bound target explicitly not-running/absent, reaches outcome
      `recovered`: exactly one `failed` line is appended, carrying reason
      `stale-launched`, with fields `event`, `task`, `at`, `reason` in that order.
- [ ] AC2 — After AC1, `queue_launch_guard.py` ALLOWS a relaunch of that task id
      and appends exactly one `launched` line — the retry path is reachable again.
- [ ] AC9 — An existing hook (`queue_failure_net.py` or `queue_taskstop_net.py`)
      has already written a terminal `failed`, or `merge-task.sh` has written
      `merged`: the re-replay yields outcome `noop_terminal` with an empty
      reason, and nothing is appended.

### US2: Keeping a live implementer safe
As an em-workflow user whose implementer is legitimately quiet for a long
stretch (for example a 20-minute test run), I want recovery to refuse to act on
anything short of explicit termination evidence, so that a live implementer's
task is never marked `failed` and relaunched underneath it.

**Acceptance Criteria:**
- [ ] AC3 — The harness reports this launch still running: outcome is `residual`
      / `agent-still-live`; no `TaskStop` call decides anything by itself, no
      helper invocation occurs, the journal is byte-identical.
- [ ] AC4 — The harness supplies only a launch-acceptance response, or only a
      generic `is_error`, or only an output-idle interval: outcome is `residual` /
      `agent-termination-unproven` in each case. An elapsed-time threshold and a
      transcript/output-file idle interval are each independently insufficient and
      are pinned as such.
- [ ] AC5 — The harness proves termination but the `TaskStop` result is a generic
      error, or reports a DIFFERENT candidate absent: outcome is `residual` /
      `stop-result-unproven`. The journal is byte-identical.
- [ ] AC6 — The agent identity cannot be uniquely bound from the Agent index
      entry + worktree + this launch's response (no entry candidate, or two or
      more distinct candidates): outcome is `residual` /
      `agent-identity-unproven`. The recorded `session_id` is never used as the
      stop target in any code path.
- [ ] AC7 — The task worktree or the task branch is absent: outcome is `residual`
      / `task-artifacts-missing`, before any `agents.jsonl` read, any path
      assembly, or any file open.
- [ ] AC8 — Between the decision and the in-lock check a newer `launched` event
      for the same task is appended: `journal-append-failed.py`'s in-lock
      comparison fails, nothing is appended, and `recover-orphaned-task.py`
      reports `residual` / `launch-changed`. An event-name-only comparison fails
      this criterion.
- [ ] AC10 — Every residual and every `noop_terminal` outcome in AC3-AC9 leaves
      `journal.jsonl` byte-identical to its pre-call content (byte-for-byte
      comparison, not line-count comparison), and never creates the file or its
      parent directory.

### US3: Keeping every existing invocation and document SSOT intact
As a maintainer of em-workflow, I want the extension to be additive across both
CLIs, the journal writer set, and the documentation SSOTs, so that no existing
behaviour, reason code, or writer changes as a side effect.

**Acceptance Criteria:**
- [ ] AC11 — An invocation supplying none of the new evidence inputs, against a
      task whose recorded identity equals the current one, still reports
      `residual` / `same-session` — the pre-existing behaviour, unchanged.
- [ ] AC12 — `journal-append-failed.py --reason <unknown>` is still rejected
      non-zero with no write; the closed set now accepts exactly `orphaned` and
      `stale-launched`, and nothing else.
- [ ] AC13 — `queue_launch_guard.py`'s source is unchanged by this feature, and
      its existing behaviour (deny on `launched`, deny on `merged`,
      allow-and-append otherwise) is re-proven green.
- [ ] AC14 — `implement-phase.md`'s I.2.b Orphan recovery block, its
      Stale-`launched` caveat, and `workflow-schema.md`'s journal writer-set
      paragraph all name the new reason value and the new codes, with the journal
      writer set itself unchanged (`merge-task.sh`, `queue_launch_guard.py`,
      `queue_failure_net.py`, `queue_taskstop_net.py`, plus the one
      `journal-append-failed.py` exception).
- [ ] AC15 — `em-workflow/.claude-plugin/plugin.json` `version` and
      `.claude-plugin/marketplace.json`'s em-workflow `version` are equal and
      strictly greater than 0.1.77.
- [ ] AC16 — `python3 -m unittest discover -s tests` passes from the repository
      root.

## Technical Requirements

### Functional Requirements

- **FR1 — Scope is the same-session residual only** (status: ok): The feature
  addresses exactly the residual that `recover-orphaned-task.py` reports today as
  `same-session` (`recover-orphaned-task.py` step 6: the agent index's recorded
  `session_id` equals the current session's identity, so the cross-session
  transcript-inactivity proof in steps 7-9 is structurally unavailable). The
  existing I.2.b orphan-recovery machinery is EXTENDED in place — no second
  recovery path, no duplicated helper, no new journal writer beyond the one
  `workflow-schema.md` already excepts. Every other residual reason code
  (`no-agent-entry`, `stale-agent-entry`, `no-session-id`, `invalid-session-id`,
  `current-session-unknown`, `transcripts-dir-missing`, `transcript-unreadable`,
  `transcript-active`, `journal-not-launched`) keeps its current behaviour byte
  for byte.

- **FR2 — Same-session death is proven only by harness-termination evidence plus
  an explicit stop-tool not-running result** (status: ok): Same-session death for
  a task is provable ONLY by the conjunction of (a) explicit harness evidence that
  THIS launch's execution has terminated, and (b) an explicit not-running/absent
  result from the existing I.2.b Recovery `TaskStop` call against the SAME bound
  agent identity. No elapsed-time threshold, and no transcript or output-file idle
  interval, may substitute for either conjunct. A launch-acceptance response, a
  generic `is_error`, an output-idle interval, and a different candidate's absence
  are each explicitly insufficient.

- **FR3 — Fixed evidence order with one residual reason code per unmet
  condition** (status: ok): `recover-orphaned-task.py`'s same-session branch
  evaluates the following conditions in this strict order, stopping at the first
  unmet one with the named outcome and invoking nothing further:
  1. the task's journal last event is `launched` (terminal → outcome
     `noop_terminal`; any other → `journal-not-launched`) AND the task worktree
     and task branch both exist (else `task-artifacts-missing`);
  2. the task's newest `agents.jsonl` entry exists (else `no-agent-entry`) and
     satisfies the existing D7 launch-binding rule (else `stale-agent-entry`);
  3. the recorded `session_id` is present (else `no-session-id`), passes SC5
     format validation (else `invalid-session-id`), and the current session's
     identity and start time resolve per D2 (else `current-session-unknown`);
  4. the stop target's agent identity is uniquely bound from the Agent index
     entry + worktree path + this launch's response, with `session_id` NEVER
     reused as the stop target (else `agent-identity-unproven`);
  5. the harness reports THIS launch's execution as terminated (else
     `agent-termination-unproven`; harness reports it still running →
     `agent-still-live`);
  6. the I.2.b Recovery `TaskStop` call reports that same bound target explicitly
     not-running/absent (else `stop-result-unproven`; if an existing hook has
     meanwhile written a terminal event, re-replay and report `noop_terminal`);
  7. inside `journal-append-failed.py`'s existing exclusive flock, THIS SAME
     launch is still the task's last event — not merely that the last event is
     still named `launched` (else `launch-changed`; already terminal →
     `noop_terminal`);
  8. only when every condition holds, exactly one `failed` line is appended.

- **FR4 — The residual reason-code set is widened additively** (status: ok):
  `recover-orphaned-task.py`'s SC6 closed reason-code set (today the ten module
  constants `REASON_NO_AGENT_ENTRY` .. `REASON_JOURNAL_NOT_LAUNCHED`, lines 67-76)
  gains exactly six new members: `task-artifacts-missing`,
  `agent-identity-unproven`, `agent-termination-unproven`, `agent-still-live`,
  `stop-result-unproven`, and `launch-changed` for the in-lock step-7 failure. No
  existing member is renamed or removed, and no existing member's emission
  condition changes except as FR5 specifies for `same-session`.

- **FR5 — `same-session` stays emitted for callers that supply no same-session
  evidence** (status: ok): Entry into the new chain is opt-in on the caller
  supplying the FR2 evidence inputs. An invocation of `recover-orphaned-task.py`
  that supplies none of them behaves exactly as today: reaching step 6 with a
  recorded identity equal to the current one yields `residual` / `same-session`,
  leaving the journal byte-identical. This keeps the pre-existing invocation form
  and its pinned behaviour (`tests/test_recover_orphaned_task.py:783`
  `test_ac2b_identity_equal_to_current_reports_same_session`, and the payload
  assertion at line 1206) intact while the extended chain runs only when the
  orchestrator has the evidence to offer.

- **FR6 — `journal-append-failed.py`'s in-lock check compares the launch, not
  merely the event name** (status: ok): `journal-append-failed.py`'s
  `decide_and_append` (`scripts/journal-append-failed.py:155-178`) today appends
  when `last_event_for_task(content, task_id) == "launched"` — an event-NAME
  comparison that cannot distinguish the launch under recovery from a newer
  `launched` line appended between the decision and the append. The helper gains a
  launch-identity input (the `at` of the `launched` event the decision was made
  against) and, inside the SAME existing exclusive flock and before the append,
  requires that the task's last event is a `launched` event carrying that
  identity. A mismatch is a no-op that leaves the journal byte-identical and is
  reported upward so `recover-orphaned-task.py` yields `launch-changed`. The
  existing single-flock critical section, the `O_NOFOLLOW` / must-already-exist
  preconditions (lines 75-97), and the SC4 line shape (`event`, `task`, `at`,
  `reason`, in that order, lines 135-146) are unchanged. The helper stays the sole
  new journal writer; it is extended, not replaced.

- **FR7 — `VALID_REASONS` is widened by exactly one additive value** (status:
  ok): `journal-append-failed.py`'s D5 closed set `VALID_REASONS = {"orphaned"}`
  (`scripts/journal-append-failed.py:54`) gains exactly one member for this path —
  `stale-launched` — as a deliberate, reviewable widening of that constant,
  matching the D5 discipline the module docstring states. `orphaned` keeps its
  meaning and its emission path. The appended line's field names and order are
  unchanged (SC4), so the new value is an additive value of the existing `reason`
  field, exactly as `orphaned` was. `tests/test_journal_append_failed.py:406`
  `test_valid_reason_accepts_only_the_closed_set` must be updated in the same
  change, since it asserts the closed set's exact membership.

- **FR8 — `queue_launch_guard.py` is not modified** (status: ok):
  `queue_launch_guard.py` keeps reading ONLY the journal's last event for the task
  (`hooks/queue_launch_guard.py:222-236`: `launched` → deny in-flight, `merged` →
  deny merged, anything else including `failed` → allow and append `launched`).
  Recovery stays orchestrator-driven and lands the `failed` event in the journal
  BEFORE any relaunch, so the guard needs no new input, no new file to read, and
  no new carve-out. I.2.a's failed-only carve-out rationale is untouched. Any
  change to this file is out of scope for this feature.

- **FR9 — The journal stays byte-identical in every residual case** (status: ok):
  Every residual outcome, and every `noop_terminal` outcome, leaves
  `journal.jsonl` byte-identical to its pre-call content — no line appended, no
  line rewritten, no file created, no parent directory created. A non-zero exit
  from either script is likewise never accompanied by a journal write and is
  treated by the caller as Residual. The append-only property and the rule that
  the orchestrator never writes the journal directly (with this one
  narrowly-scoped exception) are preserved.

- **FR10 — Documentation SSOTs are updated in the same change** (status: ok):
  Three documentation sites must carry the extension: (a)
  `em-workflow/references/implement-phase.md`'s I.2.b "Orphan recovery" block
  (lines 542-585), the owning section that states the fixed evidence order and
  every reason code — it must state the new same-session branch, its six new
  codes, and its two-conjunct proof; (b) the same file's "Stale-`launched`
  caveat" (lines 1047-1061), which today enumerates four gap-closing mechanisms
  and explicitly does not cover a stop that delivers neither `SubagentStop` nor
  `TaskStop`; (c) `em-workflow/references/workflow-schema.md`'s journal writer-set
  paragraph (lines 383-402), the SSOT for the writer set and for `orphaned` being
  an additive value of the `failed` reason field, which must name the new reason
  value additively without adding a writer.

- **FR11 — Plugin version bump in the same change** (status: ok): Because files
  under `em-workflow/` change, the same change bumps
  `em-workflow/.claude-plugin/plugin.json` `version` (currently 0.1.77) and
  `.claude-plugin/marketplace.json`'s em-workflow entry `version` (currently
  0.1.77, line 27) to the same new value. Per
  `.claude/rules/core-plugin-version-bump.md` the increment is semver; this is a
  behaviour extension of existing scripts, so patch or minor.
  `tests/test_plugin_version_parity.py` pins the two values' equality.

- **FR12 — The new reason value is attributed `failed_kind: infra` exactly like
  `orphaned`** (status: assumed — derived, see Assumption A6):
  `implement-phase.md`'s abort-phase bullet (lines 885-888) sets
  `failed_kind: infra` when the failing task's failure originates from a journal
  `failed` event whose reason is `orphaned`; `workflow-schema.md`'s `infra`
  definition (lines 297-300) is "the implementer was orphaned, or a harness
  failure occurred". A watchdog kill is a harness failure, and FR1 makes this an
  extension of the same machinery, so the new reason value is attributed `infra`
  on the same bullet. The batch-mode override at lines 910-928 (which sets
  `failed_kind` `decision` unconditionally on the second failure, including for
  `orphaned`) is unchanged and applies to the new value identically.

- **FR13 — Contract tests are added under `tests/`** (status: ok): The change adds
  documentation-contract tests and script/hook tests to the repository-root
  `tests/` directory, named `test_*.py` per `test/README.md`, discovered by
  `python3 -m unittest discover -s tests` with no registration step and no
  third-party import. The existing suites for the touched components —
  `tests/test_recover_orphaned_task.py`, `tests/test_journal_append_failed.py`,
  `tests/test_queue_launch_guard.py`, `tests/test_plugin_version_parity.py` — are
  extended or kept green rather than replaced.

### Non-Functional Requirements

- **NFR1 — Fail-safe direction preserved:** Doubt never produces a journal write.
  Every unparsable, absent, ambiguous, incomparable or merely-unproven piece of
  evidence is a residual, never a pass — matching the discipline already stated in
  `recover-orphaned-task.py`'s `agent_entry_is_bound` (lines 368-387) and
  `journal-append-failed.py`'s `decide_and_append` docstring. The cost of a missed
  recovery is the pre-existing Residual; the cost of a false recovery is a live
  implementer's task marked `failed` and relaunched, which is strictly worse.

- **NFR2 — One critical section, unchanged:** The decision-and-append remains one
  exclusive advisory flock (`fcntl.LOCK_EX`) held on `journal.jsonl` across BOTH
  the replay and the append. FR6's launch-identity comparison happens inside that
  same existing lock; no second lock, no lock widening, no lock held across a
  subprocess invocation.

- **NFR3 — Layer separation preserved:** `recover-orphaned-task.py` stays the
  Decision layer and writes nothing itself; `journal-append-failed.py` stays the
  sole Journal-write layer, invoked exactly once, as a child process, at a path
  defaulting to the sibling script and overridable via `--journal-helper` for
  testing (D6). The orchestrator itself still never appends to `journal.jsonl`
  outside this one invocation.

- **NFR4 — Hook fail-open convention untouched:** All four queue hooks remain
  fail-open nets: any unexpected state exits 0 silently. No hook gains a blocking
  condition, and the hook classification table in `implement-phase.md` (lines
  959-964) — pinned by `tests/test_hook_classification_pin.py` and
  `tests/test_queue_hook_status_read_pin.py` — is unchanged:
  `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py`
  still do not read `tasks.{T}.status`, and `queue_stop_guard.py` still does.

- **NFR5 — Backwards compatibility of both CLIs:** Every existing invocation form
  of both scripts keeps its current outcome. New parameters are additive and
  optional-at-the-CLI-surface in the sense that omitting them reproduces today's
  behaviour exactly (FR5); no existing flag is renamed, removed, or given a new
  default.

- **NFR6 — No new runtime dependency:** Both scripts stay on the Python standard
  library, matching the rest of `em-workflow/scripts/` and `hooks/`; the tests
  import no third-party package.

## Implementation Approach

### Architecture

**Layer structure (unchanged from the prior feature, extended in place):**

```
┌──────────────────────────────────────────────────────────┐
│ Orchestrator — implement-phase.md I.2.b reconcile        │
│  supplies evidence inputs; writes no journal itself      │
├──────────────────────────────────────────────────────────┤
│ Decision layer — scripts/recover-orphaned-task.py        │
│  SC3 entry point; SC6 reason codes; writes nothing       │
├──────────────────────────────────────────────────────────┤
│ Journal-write layer — scripts/journal-append-failed.py   │
│  SC2 sole new writer; one flock; D5 closed reason set    │
├──────────────────────────────────────────────────────────┤
│ journal.jsonl — append-only raw event log                │
└──────────────────────────────────────────────────────────┘
```

**Component Diagram:**

```
recover-orphaned-task.py (Decision)
  ├─ reads  journal.jsonl        (replay: task's last event)
  ├─ reads  agents.jsonl         (newest entry; D7 binding; session_id)
  ├─ takes  harness termination evidence   (FR2 conjunct a)
  ├─ takes  TaskStop not-running result    (FR2 conjunct b)
  └─ invokes journal-append-failed.py  exactly once, as a child process (D6/NFR3)
        └─ one fcntl.LOCK_EX on journal.jsonl: replay → launch-identity
           comparison (FR6) → append one `failed` line (SC4 field order)

queue_launch_guard.py (unchanged, FR8)
  └─ reads journal.jsonl last event only: `launched` → deny, `merged` → deny,
     otherwise (including `failed`) → allow and append `launched`
```

### Data Flow

```
Orchestrator → recover-orphaned-task.py → (all FR3 conditions hold)
             → journal-append-failed.py → journal.jsonl (+1 `failed` line)
             ← outcome JSON             ← outcome JSON

Orchestrator → recover-orphaned-task.py → (first unmet FR3 condition)
             ← {"outcome":"residual","task":...,"reason":"<SC6 code>"}
               journal.jsonl byte-identical; helper never invoked
```

### CLI Surface

Both scripts keep their existing CLI; new parameters are additive and omitting
them reproduces today's behaviour exactly (NFR5, FR5).

`recover-orphaned-task.py`

```
Existing:  --task, --journal, --agents, --transcripts-dir,
           --current-session-id / D2 marker inputs, --journal-helper
Added:     the FR2 evidence inputs — harness termination evidence for THIS
           launch, and the TaskStop not-running/absent result for the SAME
           bound agent identity. Supplying none of them keeps the
           `same-session` outcome (FR5 / AC11).
Outcome:   one line of JSON on stdout with keys `outcome`
           (`recovered` | `noop_terminal` | `residual`), `task`, `reason`
           (an SC6 code for `residual`; empty otherwise). Exit 0 for every
           decided outcome.
```

`journal-append-failed.py`

```
Existing:  --journal PATH, --task TASKID, --reason NAME
Added:     a launch-identity input — the `at` of the `launched` event the
           decision was made against (FR6), compared inside the existing flock.
Reason:    closed set widened to exactly {`orphaned`, `stale-launched`} (FR7).
Outcome:   one line of JSON on stdout with keys `outcome`, `task`, `reason`;
           the launch-identity mismatch is a no-op reported upward so the
           decision layer can yield `launch-changed`.
```

### Journal Line Shape

The appended line's field names and order are unchanged (SC4); only the `reason`
value is new.

| Field | Order | Value |
|-------|-------|-------|
| `event` | 1 | `failed` |
| `task` | 2 | the task id |
| `at` | 3 | RFC3339, local time, seconds precision, explicit UTC offset |
| `reason` | 4 | `stale-launched` (new additive value of the existing field) |

### Residual Reason Codes

Existing ten (unchanged, FR1/FR4) plus six new members:

| Code | Emitted when (FR3 step) | Status |
|------|-------------------------|--------|
| `journal-not-launched` | 1 — last event is neither `launched` nor terminal | existing |
| `task-artifacts-missing` | 1 — task worktree or task branch absent | **new** |
| `no-agent-entry` | 2 — no `agents.jsonl` entry for the task | existing |
| `stale-agent-entry` | 2 — entry fails the D7 launch-binding rule | existing |
| `no-session-id` | 3 — entry carries no `session_id` | existing |
| `invalid-session-id` | 3 — value fails SC5 format validation | existing |
| `current-session-unknown` | 3 — D2 cannot resolve the current session | existing |
| `same-session` | 6 (existing chain) — recorded identity equals current, no FR2 evidence supplied | existing (FR5) |
| `transcripts-dir-missing` | existing chain step 7 | existing |
| `transcript-unreadable` | existing chain step 8 | existing |
| `transcript-active` | existing chain step 9 | existing |
| `agent-identity-unproven` | 4 — stop target not uniquely bound | **new** |
| `agent-termination-unproven` | 5 — termination of THIS launch not proven | **new** |
| `agent-still-live` | 5 — harness reports this launch still running | **new** |
| `stop-result-unproven` | 6 — stop result not an explicit not-running/absent for the same bound target | **new** |
| `launch-changed` | 7 — in-lock launch identity no longer the task's last event | **new** |

### Dependencies

**Internal Dependencies:**
- `feature-docs/orphaned-implementer-recovery/` — this feature extends its
  shipped machinery. Its SC2 (`journal-append-failed.py`), SC3
  (`recover-orphaned-task.py`), SC4 (the `failed` line shape), SC5 (session_id
  format rule), SC6 (the residual reason-code set), and D1/D2/D3/D5/D6/D7 are
  cited here, never redefined.
- `em-workflow/references/implement-phase.md` — I.2.b Orphan recovery block
  (lines 542-585) is the owning section for the evidence order and reason codes;
  Stale-`launched` caveat (lines 1047-1061); abort-phase bullet (lines 885-888)
  and its batch-mode override (lines 910-928); hook classification table (lines
  959-964).
- `em-workflow/references/workflow-schema.md` — journal writer-set paragraph
  (lines 383-402) is the SSOT for the writer set; `infra` definition (lines
  297-300).
- `em-workflow/hooks/queue_launch_guard.py` — read-only dependency; not modified
  (FR8).
- `.claude/rules/core-plugin-version-bump.md` — the version-bump rule behind FR11.

**External Dependencies:**
- None. Both scripts stay on the Python standard library, and the tests import no
  third-party package (NFR6).

### Affected Code Sites

```
em-workflow/
├── scripts/
│   ├── recover-orphaned-task.py      # SC6 constants (lines 67-76) +6 members;
│   │                                 # same-session branch extended (FR3/FR5);
│   │                                 # agent_entry_is_bound (lines 368-387)
│   │                                 # fail-safe discipline unchanged (NFR1)
│   └── journal-append-failed.py      # VALID_REASONS (line 54) +1 member (FR7);
│                                     # decide_and_append (lines 155-178) gains
│                                     # the in-lock launch-identity comparison
│                                     # (FR6); open_journal_for_append
│                                     # (lines 75-97) and build_failed_line
│                                     # (lines 135-146) unchanged
├── hooks/
│   └── queue_launch_guard.py         # NOT modified (FR8); lines 222-236 pinned
├── references/
│   ├── implement-phase.md            # I.2.b block 542-585; caveat 1047-1061
│   └── workflow-schema.md            # writer-set paragraph 383-402
└── .claude-plugin/plugin.json        # version bump (FR11)
.claude-plugin/marketplace.json       # em-workflow version bump, line 27 (FR11)
tests/                                # FR13: new + extended test modules
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
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

### Unit Tests

- [ ] **TS5 — In-lock launch-identity race** (FR6, FR9, NFR2):
      `journal-append-failed.py` unit test — build a journal whose last event is
      `launched` with `at` A; invoke the helper with launch identity A after
      rewriting the file so the last event is a `launched` with `at` B. Assert no
      append and the no-op outcome. Companion concurrency test in the style of
      `tests/test_journal_append_failed.py:277`: N concurrent invocations against
      the same launch identity append at most one `failed` line.
- [ ] **TS6 — Closed-set widening** (FR7, FR9): update
      `tests/test_journal_append_failed.py:406` to assert the widened
      `VALID_REASONS` accepts exactly `orphaned` and `stale-launched` and rejects
      `manual`, empty string, and `None`; add a CLI test that the new value
      appends with the SC4 field order and that an unknown value exits non-zero
      with no write.
- [ ] **TS4 — `session_id` is never a stop target** (FR2, FR3): source-level and
      behaviour-level pin — a fixture whose recorded `session_id` coincides with a
      harness agent-identifier candidate must not resolve the stop target from the
      `session_id`; outcome `agent-identity-unproven`, no `TaskStop` target derived
      from that field.

### Integration Tests

- [ ] **TS1 — Recovered path, end to end against a stub helper** (FR2, FR3, FR7,
      NFR3): fixture journal + `agents.jsonl` in a
      `tempfile.TemporaryDirectory`; `agents.jsonl` entry bound per D7,
      `session_id` equal to the supplied `--current-session-id`;
      harness-termination evidence and stop-result evidence both supplied as
      proven. Assert stdout is one JSON line
      `{"outcome":"recovered","task":...,"reason":""}`, exit 0, and exactly one
      `failed` line appended. Mirrors the existing AC-7 stub-injection pattern in
      `tests/test_recover_orphaned_task.py`.
- [ ] **TS7 — Retry reachability after recovery** (FR8): drive
      `queue_launch_guard.py` as a subprocess with JSON on stdin
      (`test/README.md`'s hook-contract pattern) against a journal whose last
      event is the `stale-launched` `failed`: assert no deny output, exit 0, and
      exactly one `launched` line appended. Also assert the guard still denies
      when the last event is `launched` and when it is `merged` — double-launch
      prevention undiminished.
- [ ] **TS8 — Documentation contract test** (FR10): assert verbatim that
      `implement-phase.md`'s I.2.b Orphan recovery block enumerates the new codes
      in the FR3 order, that its Stale-`launched` caveat covers the
      no-`SubagentStop`/no-`TaskStop` stop, that `workflow-schema.md`'s writer-set
      paragraph names the new reason value without adding a writer, and that the
      writer set string itself is unchanged.
- [ ] **TS9 — Hook classification and status-read pins stay green** (FR8, NFR4):
      `tests/test_hook_classification_pin.py` and
      `tests/test_queue_hook_status_read_pin.py` must pass unchanged, proving no
      queue hook gained a `tasks.{T}.status` read and the four-row classification
      table is intact.
- [ ] **TS10 — Version parity** (FR11): `tests/test_plugin_version_parity.py`
      green with both versions bumped to the same new value.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] `python3 -m unittest discover -s tests` passes from the repository root
      (AC16).

### Edge Cases

- [ ] **TS2 — Reason-code table, one case per unmet condition** (FR3, FR4, FR9):
      parameterised over the full ordered condition list of FR3 — journal terminal
      → `noop_terminal`; journal not launched → `journal-not-launched`; worktree
      missing → `task-artifacts-missing`; branch missing → `task-artifacts-missing`;
      no agents entry → `no-agent-entry`; entry older than the last `launched` by
      more than D7's tolerance → `stale-agent-entry`; `session_id` absent/empty →
      `no-session-id`; `session_id` failing `SESSION_ID_RE` → `invalid-session-id`;
      D2 unresolvable → `current-session-unknown`; ambiguous identity →
      `agent-identity-unproven`; termination unproven →
      `agent-termination-unproven`; still running → `agent-still-live`; stop result
      unproven → `stop-result-unproven`; launch changed in-lock → `launch-changed`.
      Each case asserts the exact reason string AND a byte-identical journal.
- [ ] **TS3 — Insufficient-evidence pins (negative, explicit)** (FR2, FR3, NFR1):
      three separate cases proving that a launch-acceptance response, a generic
      `is_error`, and an output-idle interval each independently yield
      `agent-termination-unproven`; plus a case proving no elapsed-time threshold
      exists anywhere in the chain (a fixture whose only distinguishing feature is
      a very old `at` must still yield `agent-termination-unproven`, never
      `recovered`).

### Performance Tests

Not applicable — no performance goals are specified for this feature.

## Security Considerations

- **Input Validation:** the recorded `session_id` is validated against SC5's
  format rule before use, and is NEVER reused as the stop target in any code path
  (FR3 step 4; pinned by TS4).
- **Data Protection:** `journal-append-failed.py`'s existing preconditions are
  unchanged (FR6): the journal file must already exist, its parent directory is
  never created, the path must not be a symbolic link, and it is opened with
  `O_NOFOLLOW` so a symlink planted between check and open is refused rather than
  followed.
- **Authentication / Authorization / XSS / SQL injection / CSRF:** not applicable
  — this feature has no network surface, no user interface, and no database.

## Error Handling

### Outcome and Reason Codes

| Outcome | Reason | Journal effect |
|---------|--------|----------------|
| `recovered` | empty | exactly one `failed` line appended, reason `stale-launched` |
| `noop_terminal` | empty | byte-identical (an existing writer already wrote a terminal event) |
| `residual` | one SC6 code (see the Residual Reason Codes table) | byte-identical |
| non-zero exit | diagnostics on stderr, never stdout | byte-identical; caller treats it as Residual |

### Error Flow

```
Evidence gathered → first unmet FR3 condition → stop immediately
                  → emit `residual` + its reason code → invoke nothing further
                  → journal byte-identical (FR9)
```

## Performance Optimization

Not applicable — no performance goals, throughput targets, or caching are
specified for this feature.

## Success Criteria

- [ ] All functional requirements FR1-FR13 are implemented and tested
- [ ] All non-functional requirements NFR1-NFR6 hold
- [ ] All test scenarios TS1-TS10 pass
- [ ] AC1-AC16 are each satisfied
- [ ] Security requirements are satisfied
- [ ] Documentation SSOTs (FR10) are updated in the same change
- [ ] Both plugin version fields are bumped to the same new value (FR11)
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

No requirement carries `status: tbd`. FR12 carries `status: assumed`: its
`failed_kind: infra` attribution was derived from FR1's extend-not-duplicate
scope and `workflow-schema.md`'s own `infra` definition (assumption A6), not
answered by the user.

## Assumptions

Every assumption below comes from requirements-analyst's resolved requirements;
none is originated here.

- **A1** (irreversible): The new journal `failed` reason value is named
  `stale-launched`. The exact literal is a naming choice not fixed by the answers;
  it lands in an append-only log that is never rewritten.
- **A2** (reversible): Entry into the new same-session chain is opt-in on the
  caller supplying the FR2 evidence inputs, so an invocation that supplies none of
  them still reports `same-session`. This reading is what makes "every other
  residual reason code keeps its current behaviour" hold for `same-session`
  itself; it is pinned today by `tests/test_recover_orphaned_task.py:783` and
  `:1206`.
- **A3** (reversible): The worktree/branch existence check producing
  `task-artifacts-missing` may be performed inside `recover-orphaned-task.py` or
  supplied by the orchestrator caller; today the script explicitly never re-checks
  those two conditions (module docstring,
  `scripts/recover-orphaned-task.py:7-11`). Either placement satisfies FR3
  provided the chain's first unmet condition yields that code and nothing further
  runs.
- **A4** (reversible): `queue_agent_index.py` needs no change: the existing entry
  shape (`agent_ids` candidate list, `task`, worktree path, and the independent
  top-level `session_id`) already carries everything FR3 step 4 needs to bind an
  identity uniquely, and the orchestrator-side read rule in `implement-phase.md`
  lines 1009-1017 already defines unresolvable and ambiguous lookups.
- **A5** (reversible): `queue_stop_guard.py` needs no change: once recovery
  appends a terminal `failed`, its existing replay reclassifies the task as failed
  and its refill-block condition resolves correctly. Its consecutive-block cap of
  3 already bounds the wedged-slot case.
- **A6** (reversible): FR12's `failed_kind: infra` attribution for the new reason
  value follows from FR1's extend-not-duplicate scope and `workflow-schema.md`'s
  own definition of `infra` ("a harness failure occurred"). It was derived, not
  answered.
- **A7** (reversible): The `task_description`'s premise that "no recovery path
  exists" is obsolete: the orphaned-implementer-recovery feature already shipped
  `recover-orphaned-task.py` and `journal-append-failed.py`, and its
  `same-session` residual is precisely the uncovered case. Its two stated
  constraints (`workflow-schema.md` is the writer-set SSOT; bump both version
  fields) are carried as FR10 and FR11.

## Design Step

Skipped. 変更対象は Python の CLI ヘルパ 2 本、参照ドキュメント 2 本、tests/ のみで、
ユーザーに見える UI 面・画面遷移・視覚表現を一切持たない。プロジェクトにデザイン
システムの候補ファイルも存在しない。

## References

- Requirements document: `feature-docs/stale-launched-retry-recovery/REQUIREMENTS.md`
- Prior feature this one extends: `feature-docs/orphaned-implementer-recovery/SPEC.md`
  and `feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md` (SC2, SC3,
  SC4, SC5, SC6, D1, D2, D3, D5, D6, D7 — cited, not redefined)
- Decision layer: `em-workflow/scripts/recover-orphaned-task.py`
- Journal-write layer: `em-workflow/scripts/journal-append-failed.py`
- Launch guard (unchanged): `em-workflow/hooks/queue_launch_guard.py`
- Owning phase document: `em-workflow/references/implement-phase.md`
- Journal writer-set SSOT: `em-workflow/references/workflow-schema.md`
- Version-bump rule: `.claude/rules/core-plugin-version-bump.md`
