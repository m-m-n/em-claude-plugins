# Implementation Plan: routeback-admissibility-exits

## Overview

Every failure path of the implement phase's I.2.c route-back protocol is made
to end in a state the workflow can leave, and I.2.a's unreachability argument
is re-grounded on a premise the trust-but-verify path cannot falsify. The
deliverable is prose in `em-workflow/references/implement-phase.md`, matcher
updates in the two named test modules, and a lockstep plugin version bump —
no runtime code and no hook source changes.

## Technology Stack

- **Target document**: Markdown protocol specification
  (`em-workflow/references/implement-phase.md`) — the single normative source
  for the implement phase.
- **Test framework**: Python 3 standard-library `unittest`, run as
  `python3 -m unittest discover -s tests` from the repository root. No build
  step, no formatter, no static analysis configured for this project.
- **New dependencies**: none. Nothing is added to any manifest, so the
  `project.license: none` setting imposes no constraint on this change and no
  license conflict arises.

## Layer Structure

Rules in the target document are owned by exactly one site and cited (never
restated) elsewhere — NFR3's single-source discipline, the convention the
existing I.2.c gate text and the hook classification table already follow.
The owning sites this change touches, and the direction citations may run:

| Site | Owns | Cited by |
|---|---|---|
| Step I.2.a (launch phase) | Launch-selection rule; the recycled-task-id carve-out; the unreachability argument for `pending` + `launched` and for an inherited `merged` | I.2.b step 1, I.2.c, Supporting cast Stop-hook bullet |
| Step I.2.b step 1 (wake reconcile) | Last-event-per-task replay, the trust-but-verify cross-checks, and (new) the effect of a failed in-flight existence check plus the stale-`launched` recovery | I.2.c, Supporting cast Stale-`launched` caveat |
| Step I.2.c (failed handling) | Route-back admissibility gate, the ordered write set, the gate-rejected terminal, the abort terminal | Branch & Worktree Model's exit-4 bullet |
| Supporting cast | Journal contract, per-hook behaviour, hook classification table | I.2.a, I.2.b, I.2.c |

Journal-write mechanics may not be described inside I.2.c (see Conventions —
banned tokens): such wording belongs to I.2.b or Supporting cast, with I.2.c
citing the owning site.

## Shared Components

Contracts every task of this feature — and any review/verify-sourced follow-up
task appended later — implements against.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Route-back admissibility gate (I.2.c) | Decide whether the failed-handling path may reset the plan and re-enter planning | Precondition: no task has status `merged`; no task has status `in_progress`; no task's journal last event is `merged`; no task is in-flight under the last-event rule. Postcondition when it holds: every task is left `pending`, so `replace_all` is admissible on re-entry; every recycled task id carries either no journal event or a `failed` last event — the only two states the launch guard admits a launch after | task0001 |
| Wake-phase in-flight verification (I.2.b step 1) | Give the worktree/branch existence check a defined effect | Precondition: a task whose journal last event is `launched`. Postcondition: when neither the task worktree nor the task branch exists, the check fails; a failed check never reclassifies the task by itself (the last-event rule stays authoritative) — it triggers the stale-`launched` recovery below and is named in the phase report | task0001 |
| Stale-`launched` recovery (I.2.b step 1, writer owned by Supporting cast) | Turn a stale in-flight claim into a terminal journal state without any orchestrator journal write | Precondition: a task whose in-flight verification failed. Postcondition (success): the task's journal last event is terminal `failed`, so the next replay reconciles it as failed and it reaches the normal failed handling — retry or route-back — instead of abort-only. Postcondition (residual): when the stopped agent cannot be resolved to that task, the journal is unchanged, the task stays in-flight, the gate blocks, and the phase takes the existing gate-rejected terminal with the task named in the report | task0001 |
| Pinned-literal registry (below) | Fix which document literals may be rewritten and which may not | Precondition for any edit: a literal owned by a module outside this feature's declared change set is immutable. Postcondition: every rewritten literal has its matcher updated in the same change, with a paired negative proof and a retained-anchor guard | task0001 |
| Plugin version lockstep | Keep both manifests on one version | Precondition: both manifests read `0.1.47`. Postcondition: both read the same new value with patch strictly greater than 47, and the lockstep assertion's baseline is raised to 47 | task0001 |

## Conventions

**Wording bans inside the target document** (all enforced by tests):

- Two tokens are banned anywhere in the whole I.2.c section — `rework` and
  `append` — as substrings, checked on the whitespace-normalized section. The
  second is the verb for writing to the journal, which is why journal
  mechanics are worded in I.2.b / Supporting cast and only cited from I.2.c.
- The phrase `governs only` is banned in I.2.a.
- The claims `never read workflow.yaml` / `never reads workflow.yaml` are
  banned anywhere in the document.
- No shell line matching a bare `git commit` or `git add -A` invocation may be
  introduced anywhere in the document.

**Test-module discipline** (NFR2) — the convention both named modules already
follow, and which every new or updated matcher continues:

1. One module-level constant per asserted literal, read by both the positive
   assertion and its negative proof — the literal is never spelled twice.
2. Every absence assertion is paired with a negative proof run against a
   verbatim pre-change sample, copied byte-for-byte out of the target document
   as it reads at this task's branch point (base 9f5d7ae), never paraphrased
   or reconstructed.
3. Every pre-change sample carries a retained-anchor guard: a phrase asserted
   present in BOTH the sample and the live post-change document, so a negative
   proof cannot degrade into a tautology against an emptied sample.
4. No test is removed or skipped, and neither module's test-method count
   decreases. Class names may be reused; a second class of an existing name is
   never introduced (it would shadow the first and silently drop its tests).
5. Content assertions run against a whitespace-normalized copy of the relevant
   section; byte-identity and line-wrap assertions run against the raw text.

**Naming**: matcher constants describing pre-change wording carry a
`PRE_CHANGE_` / `OLD_` prefix; constants describing post-change wording are
named after the property they assert, not after the task that added them.

## Cross-task Design Decisions

### D1 — A third route-back gate conjunct, read from the journal's last event alone (FR1, FR2)

The gate gains one further conjunct beside its two existing halves: route-back
is inadmissible while any task's journal last event is `merged`, determined by
the last-event-per-task replay alone and explicitly independent of the
`git merge-base --is-ancestor` verification the `merged` half's second source
requires.

Rationale: today a task whose journal reports `merged` while the ancestor
check fails is invisible to both halves — the workflow.yaml half never saw a
`merged` status and the reconciled-state half rejects the unverified claim —
so route-back is admitted, the write set resets the ids, `replace_all`
renumbers, and the re-issued id inherits a `merged` last event that
`queue_launch_guard.py` denies forever with no writer able to retire it. The
third conjunct closes exactly that path and makes the combination unreachable
by construction, which is one of the two mechanisms FR1 permits.

Why this shape and not the alternative (widening I.2.a's carve-out so an
inherited `merged` counts as unlaunched): the launch guard reads the journal's
last event only and denies a `merged` launch regardless of workflow.yaml, so
the carve-out route would require a hook behaviour change and, under NFR1,
would drag all four queue hooks into this change. D1 needs no hook change.

Both existing halves keep their present two-source shape and wording — see the
pinned-literal registry; the conjunct is additive, never a restatement of
either half.

Affected: task0001 (I.2.c gate text).

### D2 — I.2.a's unreachability premise is replaced, its conclusion retained (FR2)

I.2.a's paragraph currently justifies the inheritance invariant with a premise
that the trust-but-verify path falsifies. That premise is replaced by one
resting on D1's conjunct: route-back proceeds only when no task's journal last
event is `merged`, read from the journal directly, so the justification holds
even when the ancestor check fails. The paragraph's conclusion — that no
retired task id can leave a `merged` last event behind for a renumbered task
to inherit, and that the recycled-task-id carve-out therefore stays correctly
scoped to `failed` only — is retained verbatim; it is pinned by a module
outside this feature's declared change set and is, under D1, true.

Affected: task0001 (I.2.a unreachability paragraph).

### D3 — The in-flight existence check gets an effect, not a reclassification (FR4)

I.2.b step 1's "worktree/branch existence for tasks the journal claims are
in-flight" check is given a stated outcome: when neither the task worktree nor
the task branch exists, the check FAILS, and the defined effect of that
failure is to trigger D4's recovery and to name the task in the phase report.
The failure does not, by itself, reclassify the task: the last-event rule
stays authoritative, so a `launched` last event still means in-flight until an
actual writer retires it. That is deliberate — reclassifying a stale
`launched` as unlaunched or terminal without retiring the journal state would
either produce a launch the guard denies, or admit route-back and hand a
renumbered id an inherited `launched` that is denied as a double launch. It is
also what keeps I.2.a's pinned "always in-flight" sentence true.

Affected: task0001 (I.2.b step 1, Supporting cast Stale-`launched` caveat).

### D4 — The stale-`launched` recovery is a real terminal event, not a reinterpretation (FR3)

The wake phase's recovery for a task whose in-flight verification failed is to
stop that task's recorded agent through the harness stop tool. The stop-tool
recorder — already the owning site for that mechanic, and already idempotent
with the SubagentStop failure net — records the task's terminal `failed`
event. On the next replay the task reconciles as `failed` and reaches the
normal failed handling, where retry and route-back are both available: a plan
carrying a stale `launched` therefore has an exit other than abort, which is
FR3's requirement, and it is reached automatically before the user-facing
menu, as the UX section of SPEC.md requires.

The residual case is stated rather than hidden: when the stopped agent cannot
be resolved to that task (no index entry, or an ambiguous identifier), the
journal is unchanged, the task stays in-flight, the gate blocks, and the phase
takes the existing gate-rejected terminal with the task named in the report.

Placement: the recovery is described upstream, in I.2.b, and only cited from
I.2.c. This is deliberate — the gate-rejected branch pins a sentence declaring
that no alternative recovery route is offered on that branch, and an upstream
recovery does not collide with it, while a recovery placed on that branch
would.

Affected: task0001 (I.2.b step 1, Supporting cast, the I.2.c citation).

### D5 — No hook source changes (FR5, NFR1)

D1–D4 are expressed entirely in terms of the four queue hooks' existing
behaviour: the launch guard's deny sets are unchanged and are what D1's
conjunct and D4's recovery are designed around; the stop-tool recorder's
existing idempotent terminalization is the only journal writer either decision
relies on; `queue_stop_guard.py`'s carve-out and the hook classification table
are untouched. No file under `em-workflow/hooks/` is modified by this feature,
so NFR1's all-four-together condition is never triggered.

### D6 — Version lockstep is owned by the same task (FR7)

Because files under `em-workflow/` change, both manifests move from `0.1.47`
to `0.1.48` in the same change, and the existing lockstep assertion's patch
baseline is raised from 42 to 47. That assertion lives inside one of the two
named test modules, which is why the bump is not a separate task: a task that
bumped the version without owning the assertion, or vice versa, would leave
one of the two worktrees red.

### D7 — Placement and ordering constraints inside I.2.c

New I.2.c prose must satisfy all of the following, each of which is enforced
by an existing test:

- It contains neither banned token (Conventions above).
- It does not mention the per-task status field before the ordered write set:
  two tests take the FIRST occurrence of that field token in the normalized
  section and require `pending` within the next 60 characters.
- It does not separate the two status conjuncts of the gate's opening
  sentence: a test requires no sentence break between them.
- Any citation of D4's recovery appears BEFORE the gate-rejected marker
  sentence, never inside the gate-rejected slice.
- The literal naming a terminal journal last event of `merged` or `failed`
  keeps its position before the `create-plan` write-set instruction.

## Rework Round 1 — revised shared contracts (task0002)

Additive. Review round 1 found that three of the Shared Components
postconditions above are satisfiable by text that leaves the corresponding
state without a reachable exit, so a follow-up task implementing against the
table as written would reproduce the defect. The rows below are what task0002
implements against; they supersede the named postconditions in the respects
stated and nothing else. Every other decision (D2, D5, D6, D7), the
Conventions, and the pinned-literal registry stand unchanged.

| Component | Revised contract | Supersedes |
|---|---|---|
| Wake-phase in-flight verification (I.2.b step 1) | Precondition unchanged. Postcondition: the check FAILS in the state the recovery exists for — the launch was allowed but never started, so the task worktree and the task branch both exist while the journal's last event is `launched`. A condition satisfiable only when both artifacts are absent does not meet this contract. The failure still never reclassifies the task by itself | D3's postcondition wording, and the Shared Components row's "when neither the task worktree nor the task branch exists" |
| Stale-`launched` recovery (I.2.b step 1) | Postcondition (primary): the allowed-but-never-started state reaches the terminal-journal-event outcome, not the residual. Postcondition (residual): the residual applies only to an enumerated set of conditions that does not include a launch that never started. Input contract: every input the recovery consumes is owned by exactly one site — if that input is a state source, the wake/resume state-source enumeration names it, so the recovery never depends on a source the protocol excludes; a recovery that consumes no such input satisfies this contract vacuously | D4's residual scope, and its unstated task → agent-identifier lookup |
| Route-back admissibility gate (I.2.c) | Postcondition: a conjunct may block route-back for a state only while that state has a stated outcome other than the gate-rejected/abort terminal, reached without the user selecting abort. Narrowing a conjunct is admissible only together with a stated exit for the state it protected — a recycled id must never inherit a journal `merged` with no way out. The gate-rejected branch enumerates every condition that reaches it | D1's consequence for the trust-but-verify state (journal `merged`, ancestor check failing), which D1 left on the gate-rejected terminal |
| Plugin version lockstep | Precondition: both manifests read `0.1.48`. Postcondition: both read the same new value with patch strictly greater than 48, and the lockstep assertion's baseline is raised from 47 to 48 | D6's `0.1.47` → `0.1.48` values only |

D5 (no hook source changes) is unaffected: the input contract above is a
statement about what the orchestrator protocol may read, not about what any
hook does, so nothing under `em-workflow/hooks/` changes and NFR1's
all-four-together condition stays untriggered.

## Pinned-literal registry

The declared change set permits edits to `tests/test_recycled_task_id_consistency.py`
and `tests/test_implement_routeback_gate.py` ONLY. Every other test module is
an immutable pin: a literal it asserts must survive this change byte-for-byte
(under whitespace normalization where that module normalizes). The registry
below is the design-level consequence; the full suite is the mechanical check.

Immutable (owned by `tests/test_routeback_reset_scope_consistency.py`, outside
the declared change set) — these literals MUST survive:

```
I.2.c:
  no task has status `merged`
  no task has status `in_progress`
  re-read from workflow.yaml task statuses
  not inferred from the drain above
  The `merged` half is likewise a union of two independent sources
  workflow.yaml reporting a task `merged`
  Step I.2.b step 1's reconciled state reporting a task `merged`
  verified by `git merge-base --is-ancestor` as that step already requires
  The `in_progress` half is a union of two independent sources
  cited here as the owning rule, not restated
  terminal journal last event (`merged` or `failed`)      <- before `create-plan` to `needs_update`
  every task whose Step I.2.b step 1 reconciled state is `failed`
  clean up worktrees and branches for exactly the tasks the write set just reset
  a task whose reconciled state is `merged` is never a cleanup target, whatever workflow.yaml says
  When the gate does not hold
  Step I.2.b step 1's reconciled state reports a task `merged` though workflow.yaml does not
I.2.a:
  Given I.2.c's route-back precondition                    <- slice opening anchor
  can never arise.                                         <- slice closing anchor
  no retired task id can leave a `merged` last event behind for a renumbered task to inherit
  This carve-out is deliberately scoped to `failed` only
  A task whose journal last event is `launched` is always in-flight, regardless of workflow.yaml `status`
Branch & Worktree Model:
  The widened I.2.c gate's `in_progress` union rule
```

Also immutable through other modules outside the declared change set: I.2.b
step 2/3's ordering anchors and the wake-phase commit literal, Step I.1's
baseline commit literal, the hook classification table's rows, and the exit-4
recovery-loop sentences.

Rewritable, provided AC-7's paired matcher update lands in the same change
(each is asserted only by the two named modules): the I.2.a sentence carrying
the falsified premise, and any literal those two modules pin that a decision
above genuinely requires to change. No decision above requires rewriting the
literal naming a terminal journal last event of `merged` or `failed`, and it
must not be rewritten — an immutable module pins it.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| An edit breaks a literal pinned by a module outside the declared change set, which cannot be fixed by editing that module | Medium | High | The registry above lists the design-level pins; run the full suite after each edit site, never only the two named modules |
| New I.2.c prose introduces a banned token (notably the journal-write verb) | Medium | Medium | Journal mechanics live in I.2.b / Supporting cast; I.2.c cites only (D7) |
| The stale-`launched` recovery is written as a reclassification, contradicting I.2.a's pinned "always in-flight" sentence | Medium | High | D3 states the effect as an action plus a report, never a reclassification |
| A recovery route added on the gate-rejected branch collides with its pinned "no alternative recovery route" sentence | Low | Medium | D4 places the recovery upstream in I.2.b |
| The residual unresolvable-agent case is left unstated, so the protocol is again non-total | Medium | Medium | D4 requires the residual to be stated explicitly, with the task named in the report |
| A matcher is updated without its paired negative proof or retained anchor, weakening the guard silently | Medium | Medium | Conventions 1–4; AC-5 makes the pairing itself a criterion |

## Open Questions

- [ ] None blocking. SPEC.md's Open Questions section is empty and every
      requirement in workflow.yaml is `ok`.
