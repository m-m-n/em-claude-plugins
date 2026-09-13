# Implementation Plan: stale-launched-retry-recovery

## Overview

The existing I.2.b orphan-recovery machinery is extended in place so that the
residual `recover-orphaned-task.py` reports today as `same-session` can, when
and only when explicit termination evidence is supplied, reach a terminal
`failed` event carrying the new reason value `stale-launched`. Four tasks:
the journal-write helper, the decision layer, the documentation SSOTs, and
the version bump plus the retry-reachability proof.

## Technology Stack

- **Language**: Python 3 (standard library only) — both scripts already are,
  and NFR6 forbids widening that.
- **Test framework**: `unittest` from the standard library, discovered by
  `python3 -m unittest discover -s tests` (`test/README.md`).
- **New dependencies**: none. No third-party package is added by any task, in
  runtime code or test code. `project.license` is `none`, so no license
  compatibility constraint applies; the zero-new-dependency fact is recorded
  here because the license review perspective cross-checks against this
  section.

## Layer Structure

Unchanged from the prior feature; extended in place. Dependency direction is
downward only — no layer below ever calls up.

| Layer | Component | Responsibility | May write `journal.jsonl` |
|---|---|---|---|
| Orchestrator | I.2.b reconcile (documented, not coded here) | Gathers evidence and passes it as CLI inputs | No |
| Decision | `em-workflow/scripts/recover-orphaned-task.py` | Evaluates the fixed evidence order, emits an outcome, invokes the journal helper at most once as a child process | No — never writes anything |
| Journal write | `em-workflow/scripts/journal-append-failed.py` | The single narrowly-scoped writer exception: one exclusive advisory lock across replay and append | Yes, exactly one line |
| Data | `journal.jsonl` | Append-only raw event log | — |

The journal writer set itself does not change: `merge-task.sh`,
`queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`,
plus the one `journal-append-failed.py` exception. No task adds a writer.
`queue_launch_guard.py` is not modified by any task (FR8).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| SC2′ — journal helper CLI | Decide and append under one lock | Pre: journal file already exists, is not a symbolic link, parent directory exists (all unchanged). Accepts `--journal PATH --task TASKID --reason NAME` plus the new optional `--launch-at VALUE`. `--reason` is checked against the closed set {`orphaned`, `stale-launched`} before the journal is opened; any other value exits non-zero with no write. Post: exactly one of the three outcomes below, on one line of JSON on stdout with keys `outcome`, `task`, `reason`; exit 0 for all three; the journal is byte-identical for the two non-appending outcomes | task0001 (builds), task0002 (invokes) |
| SC2′ outcome vocabulary | Report the helper's decision upward | `appended` — the task's last event is `launched` and, when `--launch-at` was supplied, that event's `at` equals the supplied value; exactly one `failed` line was appended. `noop_terminal` — the task's last event is `merged`, `failed`, absent, or any other name; nothing appended. `launch_changed` — `--launch-at` was supplied, the last event is `launched`, but its `at` differs (including absent or non-string); nothing appended | task0001 (emits), task0002 (maps to outcomes) |
| SC4 — appended line shape | Pin the `failed` line | Unchanged: field names and order are `event`, `task`, `at`, `reason`. `event` is `failed`; `at` is RFC3339 local time, seconds precision, explicit UTC offset; `reason` is the `--reason` value. `stale-launched` is a new additive value of the existing `reason` field, nothing else changes | task0001, task0003, task0004 (as the string a fixture journal carries) |
| SC3′ — decision layer CLI | Entry point for the I.2.b reconcile step | Existing inputs unchanged. New optional inputs (see Evidence inputs below). Post: one line of JSON on stdout with keys `outcome` (`recovered` \| `noop_terminal` \| `residual`), `task`, `reason` (an SC6 code for `residual`, empty string otherwise); exit 0 for every decided outcome; diagnostics on stderr only | task0002 (builds), task0003 (documents) |
| SC6 — residual reason-code set | Closed vocabulary of residual reasons | The existing ten values are unchanged in spelling and in emission condition. Exactly six values are added: `task-artifacts-missing`, `agent-identity-unproven`, `agent-termination-unproven`, `agent-still-live`, `stop-result-unproven`, `launch-changed` | task0002 (emits), task0003 (documents verbatim) |
| Agent index entry | Diagnostic launch record, read-only here | Existing shape, not modified by this feature: `task`, `at`, `agent_id`, `agent_ids` (the candidate list), `worktree_path`, and an independent optional `session_id`. `session_id` is never a member of `agent_ids` and is never a stop-target candidate | task0002 |

### Evidence inputs (SC3′, new and optional)

Seven inputs, each additive. Supplying none of them reproduces today's
behaviour exactly (FR5 / NFR5). Every token vocabulary below is closed: an
absent, empty or unrecognized value is never a proof, always the residual its
step names.

| Input | Step | Accepted values | Meaning |
|---|---|---|---|
| `--worktree-present` | 1 | `yes` \| `no` | Whether the caller observed the task worktree |
| `--branch-present` | 1 | `yes` \| `no` | Whether the caller observed the task branch |
| `--task-worktree` | 4 | absolute path | The task worktree path the bound agent index entry must name |
| `--stop-target` | 4 | identifier string | The agent identity the I.2.b Recovery stop call was made against |
| `--launch-termination` | 5 | `terminated` \| `running` \| `launch-accepted` \| `error` \| `output-idle` | What the harness reports about THIS launch's execution |
| `--stop-result` | 6 | `not-running` \| `error` | What the stop call reported |
| `--stop-result-target` | 6 | identifier string | Which target the stop result is about |

Only `terminated` proves step 5; `running` yields `agent-still-live`; every
other value — including `launch-accepted`, `error`, `output-idle`, an
unrecognized token and an absent input — yields
`agent-termination-unproven`. Only `not-running`, together with a
`--stop-result-target` equal to the bound identity, proves step 6; everything
else yields `stop-result-unproven`.

### Agent-identity binding rule (step 4)

The stop target's identity is uniquely bound when ALL of the following hold
against the selected (newest, D7-bound) agent index entry: the entry names
exactly one distinct candidate in its candidate list; the entry's recorded
worktree path equals the supplied `--task-worktree`; and `--stop-target`
equals that one candidate. Anything else — no candidate, two or more distinct
candidates, a worktree mismatch, a stop-target mismatch, an absent
`--stop-target` — is `agent-identity-unproven`. The recorded `session_id` is
never read as a candidate and never becomes the stop target on any path.

This bar is deliberately STRICTER than the orchestrator's existing
stop-target read rule (which passes the first-recorded candidate when several
exist): stopping the wrong thing is recoverable, recording a live
implementer's task as `failed` is not.

## Conventions

- **Reason-code spelling**: residual reason codes and journal `reason` values
  are lowercase kebab-case (`stale-launched`, `agent-still-live`). Helper
  outcome tokens stay snake_case, matching the existing `noop_terminal`.
- **Error-handling policy (NFR1, binding on every task)**: doubt never
  produces a journal write. Unparsable, absent, ambiguous, incomparable or
  merely-unproven evidence is a residual, never a pass. A non-zero exit from
  either script is never accompanied by a write and is treated by the caller
  as Residual.
- **Byte-identity (FR9)**: every residual and every `noop_terminal` leaves
  `journal.jsonl` byte-identical to its pre-call content, and creates neither
  the file nor its parent directory. Tests assert byte-for-byte equality of
  the file content, never a line count.
- **Output discipline**: one line of JSON on stdout for a decided outcome;
  diagnostics on stderr only, never stdout.
- **Backwards compatibility (NFR5)**: no existing flag is renamed, removed or
  given a new default; every new input is optional and omitting all of them
  reproduces today's behaviour.
- **Test placement**: repository-root `tests/`, named `test_*.py`, discovered
  with no registration step, importing no third-party package
  (`test/README.md`). Fixtures live in per-test temporary directories; no
  test touches real `~/.claude` state.
- **Documentation wording**: documentation states the EVIDENCE that must be
  proven and the reason codes verbatim; it does not spell CLI flag names, so
  a documentation-contract test never pins a flag spelling.

## Cross-task Design Decisions

### D-A — The new chain is entered on supplied evidence alone

Entry into the extended chain is opt-in on the caller supplying at least one
of the seven evidence inputs (FR5's own rule). When none is supplied, the
script runs today's pipeline unchanged and still reports `same-session` where
it does today. Recorded-identity equality is NOT re-tested as an entry
condition — FR3's ordered chain contains no such condition, and every pinned
legacy test uses the no-evidence invocation form.

Equality is nonetheless a *precondition* of the chain, established
structurally rather than by a second test: FR3 scopes the new chain to
`recover-orphaned-task.py`'s **same-session branch**, and that branch is
reached only under `recorded_session_id == current_id`
(`em-workflow/scripts/recover-orphaned-task.py:564-565`). The chain therefore
cannot run for a task launched by a different session; re-testing there would
be dead code. task0002 must place the chain inside that branch and not lift it
to an earlier point in the pipeline — doing so would break this guarantee.
Affected tasks: task0002 (implements), task0003 (documents).

### D-B — Worktree and branch presence are supplied by the caller

The decision layer does not re-derive artifact existence (it explicitly never
has); it accepts the caller's two separate observations and treats a `no`, an
absent input or an unrecognized value as `task-artifacts-missing`. This is
the placement REQUIREMENTS A3 permits, keeps the decision layer free of any
version-control invocation, and makes the missing-worktree and
missing-branch cases two distinct test inputs. The check is a pure argument
check evaluated FIRST in the new chain, so it decides before any agent index
read, any path assembly and any file open (AC7).
Affected tasks: task0002, task0003.

### D-C — Launch identity is the raw `at` string of the `launched` event

The decision layer reads the task's last `launched` event's `at` field and
passes that raw value to the helper; the helper compares it, inside the
existing lock, against the `at` of the task's last event, as exact strings.
The value travels unparsed end to end, so no timestamp-format normalisation
can make two different launches compare equal. Two launches whose `at`
strings are identical (same whole second) are indistinguishable by this
comparison — accepted: it is strictly stronger than today's event-name-only
comparison, and a relaunch inside the same second is not a reachable state
for this workflow.
Affected tasks: task0001, task0002.

### D-D — Helper outcome `launch_changed` maps to residual `launch-changed`

The helper reports the in-lock mismatch upward as its own outcome value; the
decision layer maps `appended` → `recovered`, `noop_terminal` →
`noop_terminal`, `launch_changed` → `residual` with reason `launch-changed`.
Any other helper outcome value, a non-zero helper exit, or unparsable helper
stdout stays what it is today: a non-zero exit from the decision layer, never
reported as `recovered`.
Affected tasks: task0001, task0002.

### D-E — Reason is chosen by the caller of the helper, per chain

The legacy chain keeps invoking the helper with reason `orphaned` and no
launch-identity input. The new chain invokes it with reason `stale-launched`
and the launch-identity input. The helper itself never infers a reason.
Affected tasks: task0001, task0002.

### D-F — Contract-halves testing; the integrated pair is verified by the verify phase

Tasks run in parallel in separate worktrees, so no task's worktree contains
another task's code. task0002 therefore proves its half against an injected
stub helper (the existing `--journal-helper` override), asserting the exact
argument shape it sends; task0001 proves the other half by driving the real
helper directly with that same argument shape. The end-to-end pair — the
decision layer invoking the REAL sibling helper through its default path — is
an integrated verification item in VERIFICATION.md, run after merge, not a
per-task test. No placeholder is introduced by either task, so there is
nothing left to wire.

### D-G — Documentation is additive; existing pinned phrases stay green

`tests/test_implement_routeback_gate.py` pins exact phrases from the I.2.b
Orphan recovery block, the Stale-`launched` caveat and the
`workflow-schema.md` writer-set paragraph, including the sentence describing
the `orphaned` invocation and the writer-set sentence itself. The
documentation edit ADDS the new branch, the six new codes and the new reason
value without rewriting those sentences, so those pins keep passing
unchanged.
Affected tasks: task0003.

### D-H — Version target and the one exact-value pin that must be re-anchored

Both version fields move from `0.1.77` to `0.1.78` (patch: a behaviour
extension of existing scripts). `tests/test_codex_wrapper_fallback_removal_version_bump.py`
asserts the em-workflow version equals `0.1.77` exactly (its
`TestSpecificVersionValues` class and the value table it reads); it must be
re-anchored to the new value in the same change, the way earlier features
re-anchored their predecessors. Every other version module compares against a
baseline floor and needs no edit.
Affected tasks: task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A live implementer's task is recovered and relaunched underneath it | Low | High | Two-conjunct proof, no time-based proxy anywhere, every unproven input a residual (NFR1); explicit negative pins for launch-acceptance, generic error and output-idle evidence |
| A relaunch lands between the decision and the append, and the wrong launch is failed | Low | High | In-lock launch-identity comparison against the raw `at` (D-C), reported upward as `launch-changed` |
| The stop target is resolved from `session_id` and the wrong agent is stopped | Low | High | Binding rule reads only the candidate list; `session_id` is never a candidate; pinned at source level and behaviour level |
| The documentation edit breaks an existing verbatim pin | Medium | Medium | Additive editing (D-G); the pinning module is listed in task0003's file set so a needed re-anchor is in scope rather than a deviation |
| The version bump breaks the one exact-value pin | High | Low | D-H names the module and includes it in task0004's file set |
| The two CLI halves drift apart before the integrated run | Low | Medium | Both halves pinned to the same contract in this document; argument shape asserted on the sending side and accepted on the receiving side (D-F) |

## Open Questions

- [ ] FR12 carries `status: assumed`: the `failed_kind: infra` attribution
      for `stale-launched` is derived from the `infra` definition, not
      answered by the user. task0003 documents it; a later answer would be a
      documentation-only change.
