# Implementation Plan: orphaned-implementer-recovery

## Overview

Session identity is recorded at launch, a new journal writer appends a
terminal `failed` event under the existing exclusion discipline, and a new
decision entry point proves — or fails to prove — that the session which
launched an implementer is gone. Proven cases converge into the existing
I.2.c failed path; everything else stays Residual.

## Technology Stack

- **Language**: Python 3, **standard library only** — the two new
  `em-workflow/scripts/` helpers and the changed hook. Chosen over bash
  because both helpers parse JSON event lines, compare timestamps, and must
  be unit-testable at function level as well as through their command-line
  entry point. `em-workflow/scripts/validate-worker-output.py` is the in-repo
  precedent for a Python script; unlike it, these two must import no
  third-party package (NFR4).
- **Tests**: `unittest` from the standard library, collected by
  `python3 -m unittest discover -s tests` (NFR5).
- **New dependencies**: none. No package manifest is touched, so no license
  compatibility question arises. `project.license` is `none`, which imposes
  no constraint; this line is the record required of a technology choice.

## Layer Structure

Three runtime layers; dependencies point downward only, never sideways.

| Layer | Component | Responsibility | May depend on |
|---|---|---|---|
| Recording | `queue_agent_index.py` (hook) | Writes the launching session's identity into the agent index at launch | nothing below |
| Decision | `recover-orphaned-task.py` | Gathers evidence for one candidate task and decides recovered / residual. Writes nothing itself | Journal-write layer, via SC2's contract only |
| Journal-write | `journal-append-failed.py` | The only new writer of a journal event | nothing below |

The documentation layer (`implement-phase.md`, `workflow-schema.md`,
`em-workflow/README.md`) describes all three. It carries one owning section
and cites it everywhere else (NFR7); it never re-states a rule.

The Decision layer never appends to the journal directly, and the
Journal-write layer never gathers evidence. This split is what keeps the
NFR1 exception narrow: the only journal write authority added to the
orchestrator is a helper whose reason value is drawn from a closed set.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| **SC1** — agent index entry `session_id` field | Carries the identity of the session that launched an implementer | Written as an **independent top-level field** of the entry, alongside the existing `agent_id` / `agent_ids` / `task` / `worktree_path` / `at`. **Never** appended to the `agent_ids` candidate list and never a match candidate. Pre: the hook input supplies a value passing SC5. Post: when it does not, the field is omitted and the entry is still appended (fail-open, NFR3). Readers MUST treat absence as "unknown" — legacy entries have no such field — and degrade to Residual | task0001 (writer), task0003 (reader), task0004 (documentation) |
| **SC2** — `em-workflow/scripts/journal-append-failed.py` | Appends one terminal `failed` event to the journal | Parameters: `--journal PATH`, `--task TASKID`, `--reason NAME` (all required; `--reason` validated against the closed set whose only member is `orphaned`). Pre: the journal file already exists — the helper never creates it and never creates its directory; the file is opened for append **without following a symbolic link**. Critical section: an exclusive advisory lock is taken on the journal file itself, and the replay that determines the task's final event plus the append both happen inside that single lock hold. Post: exactly one `failed` line is appended when the task's final event is `launched`; **nothing** is written when it is already `merged` or `failed`; the appended line's field shape follows SC4. Outcome: one line of JSON on stdout with keys `outcome` (`appended` \| `noop_terminal`), `task`, `reason`; exit 0 for both decided outcomes, non-zero (and no write) for usage or internal errors | task0002 (owner), task0003 (caller), task0004 (documentation) |
| **SC3** — `em-workflow/scripts/recover-orphaned-task.py` | Decides, for one candidate task, whether the launching session is provably gone; on proof invokes SC2 with reason `orphaned` | Parameters: `--journal PATH`, `--agents-index PATH`, `--task TASKID` (required); `--transcripts-dir PATH`, `--current-session-id ID`, `--current-session-start TIMESTAMP`, `--marker TOKEN`, `--journal-helper PATH` (optional; `--journal-helper` defaults to the sibling `journal-append-failed.py` in the same directory). Pre: the caller has already established the candidate conditions it owns (journal final event `launched`, task worktree and task branch present, no live agent). The agent index entry it reads is evidence only once it is BOUND to the launch under recovery per D7; an entry that cannot be bound ends the run as `residual` with SC6's `stale-agent-entry`, before the entry's session identity is read. Post: on proof, SC2 is invoked exactly once with the task identifier and reason `orphaned`, and SC2's outcome is propagated; on every other path the journal is **byte-identical** to its pre-call content, SC2 is not invoked, and no file outside the resolved transcripts directory is opened. Outcome: one line of JSON on stdout with keys `outcome` (`recovered` \| `noop_terminal` \| `residual`), `task`, `reason` (a reason code from SC6; empty for `recovered`); exit 0 for all decided outcomes. A non-zero exit means usage or internal error, is never accompanied by a journal write, and the caller treats it as Residual | task0003 (owner), task0004 (documentation) |
| **SC4** — journal `failed` event line shape | Keeps the new writer's output indistinguishable in shape from the existing ones | The appended line's field names and ordering are **taken from the existing `failed` writers** (`queue_failure_net.py`, `queue_taskstop_net.py`) rather than invented. The change is additive: a new value (`orphaned`) of the existing reason field. No existing event name or reason is renamed or removed (FR9) | task0002 (writer), task0004 (schema documentation) |
| **SC5** — `session_id` validation rule | Keeps a recorded identity safe to compare and to use as a path element | A value is valid when it is a non-empty string of at most 64 characters whose first character is an ASCII letter or digit and whose remaining characters are ASCII letters, digits, hyphens or underscores. Dots, path separators, whitespace and NUL are rejected, which makes a `..` segment unrepresentable. Applied **before** the value is used as a path element; path containment (D1) is checked in addition, never instead | task0001 (applies it on write), task0003 (applies it on read), task0004 (documentation) |
| **SC6** — residual reason codes | Makes each unproven path distinguishable in reports and tests | Closed set: `no-agent-entry`, `stale-agent-entry`, `no-session-id`, `invalid-session-id`, `same-session`, `current-session-unknown`, `transcripts-dir-missing`, `transcript-unreadable`, `transcript-active`, `journal-not-launched`. Every code means "the journal was not written". `stale-agent-entry` means the agent index entry could not be bound to the launch under recovery (D7) | task0003 (producer), task0004 (documentation), task0006 (adds `stale-agent-entry`) |

## Conventions

- **Naming**: new helpers are hyphenated file names under
  `em-workflow/scripts/` (repo precedent: `merge-task.sh`,
  `commit-docs.sh`, `validate-worker-output.py`).
- **Outcome reporting**: every new helper reports one line of JSON on
  stdout and exits 0 for any *decided* outcome, reserving non-zero exits
  for usage and internal errors. Diagnostics go to stderr, never stdout.
- **Error-handling policy (fail-safe direction, NFR1)**: any condition that
  cannot be proven — missing data, unreadable file, unparsable timestamp,
  unresolvable current session — resolves to Residual and no journal write.
  There is no path on which doubt produces a write.
- **Journal-write discipline (NFR2)**: exclusive advisory lock on the
  journal file itself; replay and append inside one lock hold; refusal to
  follow a symbolic link when opening for append; never create the file or
  its directory.
- **Test placement (NFR4, NFR5)**: repository-root `tests/`, named
  `test_*.py`, standard library only. Every path root that would otherwise
  resolve under the real `~/.claude` is injectable so that no test reads or
  writes real state. Hooks are exercised by subprocess with stdin JSON;
  scripts are exercised through their command-line entry point plus
  function-level calls.
- **Version bump ownership**: exactly one task per round touches
  `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` (NFR6) — task0004 for the implement
  round, task0006 for the review-rework round, which is the only task of that
  round changing a file under `em-workflow/`. No other task edits either
  file.
- **Documentation ownership (NFR7)**: `implement-phase.md`'s I.2.b
  Recovery / Residual block is the single owning section for the orphan
  recovery rule. Every other location cites it by repository-relative path.

## Cross-task Design Decisions

### D1 — Transcripts directory derivation and containment

The transcripts directory defaults to `~/.claude/projects/{encoded}`, where
`{encoded}` is the invoking process's absolute working directory with every
character outside the set {ASCII letters, digits, hyphen} replaced by
exactly one hyphen — no collapsing of consecutive replacements, and the
leading path separator becoming a leading hyphen.

`--transcripts-dir` replaces the derivation entirely; tests always use it so
real `~/.claude` state is never touched (NFR5). The assembled transcript
file path must resolve **inside** the resolved directory, and when the
default derivation is in effect it must additionally resolve under
`~/.claude/projects/`. A missing directory is `transcripts-dir-missing`
(Residual), never an attempt to search elsewhere.

*Rationale and risk*: the encoding is observed from the harness's on-disk
layout, not documented by it. A wrong rule can only fail to find a file,
which degrades to Residual — never to a false recovery. The derivation is a
pure function with unit tests over known samples, and VERIFICATION.md
carries a manual check against the real layout.
Affects task0003, task0004.

### D2 — Current-session identity and start time

SC3 never guesses which session is current. It accepts either:

1. an explicit `--current-session-id` together with an explicit
   `--current-session-start`, or
2. a `--marker TOKEN` the caller has already emitted into its own
   transcript.

Form 1 takes precedence. With form 2, resolution scans the resolved
transcripts directory ordered by modification time, newest first, for the
first transcript containing the token; that file's name stem is the current
session identity and its **first entry's timestamp** is the current session's
start. This settles the SPEC's carried-forward question in favour of the
"first entry of the current session's transcript" source. The scan may be
bounded by the implementation (the current session's transcript is by
construction among the newest); a miss is `current-session-unknown`
(Residual).

The orchestrator emits the token in a command it runs before the recovery
invocation, then passes the same token — documented by task0004 in the
owning section.

*Rationale*: this is the only source of the orchestrator's own session
identity this repository can rely on without a harness API it cannot
verify, and the fail-safe direction means a miss costs only the
pre-existing Residual behaviour. If a direct source of the current session
identity turns out to be available, it feeds form 1 without any contract
change.
Affects task0003, task0004.

### D3 — Proof condition and timestamp comparison

The recorded session is proven gone when the newest usable timestamp in its
transcript is **strictly older** than the current session's start. A line
whose timestamp cannot be parsed is skipped; a transcript from which no
usable timestamp can be read at all is `transcript-unreadable` (Residual),
not "no activity". Activity at or after the current session's start is
`transcript-active` (Residual).
Affects task0003, task0004.

### D4 — Bash approval gate: no change required

The approval store described in `references/command-execution-protocol.md`
gates the four `*_command` strings declared in `workflow.yaml`. The two new
helpers are plugin-owned scripts invoked the way `merge-task.sh` and
`commit-docs.sh` already are — they are not `workflow.yaml`-derived command
strings, so they are neither approved nor declared, and the gate does not
apply. No task modifies `command-execution-protocol.md`, and no approval
entry is planned. This settles the SPEC's carried-forward question.
Affects task0003, task0004.

### D5 — The write authority stays narrow

SC2's `--reason` is validated against a closed set containing only
`orphaned`. The orchestrator therefore gains authority to record exactly
the one terminal event the SSOT exception permits, and widening it later is
a deliberate, reviewable change to that closed set rather than a
consequence of the helper being generic (NFR1).
Affects task0002, task0004.

### D6 — Split helper, injectable path

The decision layer invokes the journal-write layer as a child process at a
path defaulting to its sibling script, overridable through
`--journal-helper`. Task0003 owns the wiring: its default path resolution is
an acceptance criterion, so nobody has to "wire it later". Its own tests
inject a stub implementing SC2's outcome contract, which keeps task0003
verifiable inside its own worktree; the real end-to-end pairing is
TS-1, verified in the verify phase after both tasks merge.
Affects task0002, task0003.

### D7 — Binding the agent index entry to the launch under recovery

Index recording is fail-open (SC1): a launch whose index write was missed —
absent journal directory, an unobtainable or invalid session identity, any
hook-level failure — leaves the PREVIOUS launch's entry as the newest entry
for that task. The newest entry is therefore not evidence about the launch
under recovery until it has been bound to it, and the `launched` journal
event carries no session identity of its own to correlate against.

**Rule.** Let `L` be the `at` of the LAST `launched` journal event recorded
for the task. When the journal records at least one `launched` event for the
task, the agent index entry is admitted as evidence only when its own `at`
parses and is not earlier than `L` by more than the tolerance below;
otherwise the outcome is `residual` with SC6's `stale-agent-entry`, and
nothing further runs — no session identity is read, no path is assembled, no
file is opened, the journal stays byte-identical. Data that cannot be
compared at all (an `at` absent, non-string, unparsable, or incomparable
across aware/naive instants, on either side) is a binding failure, never a
pass: the Conventions' error-handling policy applies unchanged, doubt never
produces a write.

The rule does not apply when the journal records no `launched` event for the
task. No recovery can result from such a journal — the journal pre-check
already ends that run as `journal-not-launched` or `noop_terminal` — so
applying it there would only relabel an existing outcome.

**Tolerance: 2 seconds.** The two writes come from two separate PreToolUse
hook invocations — `queue_launch_guard.py` appends the journal `launched`
line, `queue_agent_index.py` appends the index entry — each stamping whole
seconds from the local clock in an order the harness does not fix, so the
genuine pair can straddle a second boundary in either direction. A genuinely
stale entry is separated from the newest launch by a whole implementer run,
not by seconds, so the tolerance admits the real pair without admitting a
previous launch's entry.

**Placement.** The check is a step of SC3's fixed evidence order, run
immediately after "an agent index entry exists for the task" and before the
entry's session identity is read; every other step keeps its position and its
reason code. `implement-phase.md`'s I.2.b Orphan recovery block states the
order (Conventions, NFR7) and is updated in the same change.
Affects task0003, task0004, task0006.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The D1 encoding rule does not match the harness's real layout | Medium | Recovery never fires; behaviour stays as today | Pure-function unit tests over known samples; manual layout check in VERIFICATION.md; fail-safe degrades to Residual |
| The D2 marker has not reached the current transcript when resolution runs | Medium | Recovery skipped for that pass | The orchestrator emits the marker in an earlier command; a miss is Residual, and the next pass retries |
| A live sibling session blocked on a long tool call shows no recent transcript activity | Low | A live task could be recorded `failed` | Requires the recorded identity to differ from the current session as well; one develop run per feature is a pre-existing assumption; SC2's in-lock replay keeps the journal consistent if the sibling later writes a terminal event |
| SC4's line shape drifts from the existing `failed` writers | Medium | Downstream readers mis-parse the new line | Shape is derived from the existing writers, not invented; TS-4 proves the launch guard accepts the result |
| Verbatim documentation constants in the test suite break when the prose is rewritten | High | Test failures | task0004 owns both the prose and the constants in one change |
| D7's tolerance is too small for the two hooks' clock granularity | Low | The genuine entry is rejected, so recovery does not fire and behaviour stays as today (fail-safe) | Both tolerance boundaries are pinned by tests; a miss costs only the pre-existing Residual, never a false recovery |
| Two new scripts plus a hook change land in parallel | Medium | Integration mismatch at the SC2/SC3 boundary | SC2's parameter and outcome contract is pinned above; task0003 tests against a stub of that contract; TS-1 verifies the real pairing |

## Open Questions

- [ ] Whether the harness exposes the orchestrator's own session identity
      directly. If it does, it feeds D2 form 1 and the marker scan becomes
      an unused fallback — no contract change either way.
- [ ] Whether a test already asserts plugin/marketplace version
      consistency. TS-11 is planned as a verify-phase check rather than a
      new test file so that it cannot collide with one.
