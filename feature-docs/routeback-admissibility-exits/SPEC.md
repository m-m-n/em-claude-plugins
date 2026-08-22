# Feature: routeback-admissibility-exits

## Overview

The implement phase's I.2.c route-back protocol can currently reach states the
workflow cannot leave: a task id recycled through route-back can inherit a
journal last event of `merged` and become permanently unlaunchable, and a plan
carrying a stale `launched` has abort as its only option. This feature makes
every failure path in that protocol end in a leavable state, and corrects the
I.2.a unreachability argument that the trust-but-verify path falsifies. The
change is expected to be protocol documentation plus tests; see
`REQUIREMENTS.md` for the full Japanese requirements this document renders.

## Objectives

- Every failure path in the implement phase's I.2.c route-back protocol ends in
  a state the workflow can leave: no task may become permanently unlaunchable,
  and no plan may be left with abort as its only option.
- The protocol document's own unreachability claims must be true of the
  protocol as written, so future changes reason from a correct base rather than
  from a claim the trust-but-verify path falsifies.

## User Stories

### US1: Leaving a recycled task id that inherited `merged`

As the em-workflow orchestrator, I want a recycled task id whose journal last
event is `merged` to still be launchable (or to be unreachable by construction),
so that route-back never strands a task permanently.

**Acceptance Criteria:**
- [ ] AC-1: `em-workflow/references/implement-phase.md` defines an
      automatically-recoverable exit for a re-numbered task whose inherited
      journal last event is `merged`, or its body makes that combination
      unreachable including the case where a journal `merged` fails
      `git merge-base --is-ancestor`.
- [ ] AC-3: I.2.a's unreachability paragraph no longer asserts a justification
      that the trust-but-verify path falsifies; its `failed`-only carve-out
      scoping is re-justified or widened consistently with AC-1's mechanism.

### US2: Leaving a plan that carries a stale `launched`

As the em-workflow orchestrator, I want a plan whose task journal claims
`launched` while nothing is actually in flight to have a recovery path other
than abort, so that the phase is not forced to terminate.

**Acceptance Criteria:**
- [ ] AC-2: `em-workflow/references/implement-phase.md` defines a recovery path
      other than abort for a plan carrying a stale `launched`, and states what
      I.2.b step 1's worktree/branch existence check yields for such a task.

### US3: Keeping the protocol change verifiable

As a future author of `implement-phase.md`, I want the change to arrive with
matching requirements, acceptance criteria, test scenarios and matcher updates,
so that the documented invariants stay machine-checked.

**Acceptance Criteria:**
- [ ] AC-4: REQUIREMENTS.md / SPEC.md carry requirements, acceptance criteria
      and test scenarios corresponding to AC-1..AC-3, and the two named test
      modules assert them with the paired regression proofs NFR2 requires.
- [ ] AC-5: `python3 -m unittest discover -s tests` passes.
- [ ] AC-6: `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` agree on the same version, strictly
      greater than 0.1.47.
- [ ] AC-7: Every `implement-phase.md` literal still pinned by a surviving test
      remains byte-identical, and every literal deliberately rewritten has its
      matcher updated in the same change with a negative proof against the
      pre-change bytes.

## Technical Requirements

### Functional Requirements

- **FR1 — Exit for a recycled task id that inherited a `merged` journal event:**
  `em-workflow/references/implement-phase.md` MUST guarantee that a task id
  reset to `pending` by I.2.c's route-back write set and re-issued by the
  planner's `replace_all` renumbering can never be left permanently unlaunchable
  by a journal last event of `merged` — either by defining an
  automatically-recoverable exit for that state, or by making the combination
  unreachable in a way the body states, explicitly covering the trust-but-verify
  case in which merge-task.sh wrote `merged` to the journal but
  `git merge-base --is-ancestor` fails (so neither gate source reports `merged`
  and route-back proceeds).

- **FR2 — Correct I.2.a's unreachability argument:** The I.2.a paragraph's
  claim that "Because route-back proceeds only when no task is `merged` under
  either source (the widened I.2.c gate above), no retired task id can leave a
  `merged` last event behind for a renumbered task to inherit, so the
  recycled-task-id carve-out above stays correctly scoped to `failed` only"
  MUST be restated so it holds under the trust-but-verify case, consistent with
  whatever mechanism FR1 adopts (either a narrowed precondition or a widened
  carve-out).

- **FR3 — Exit for a plan carrying a stale `launched`:** A plan in which some
  task's journal last event is `launched` while no implementer is actually in
  flight (no task worktree, no task branch, no live agent) MUST have a
  protocol-defined recovery path other than abort — for example by evaluating
  the route-back precondition against I.2.b step 1's reconciled state so a stale
  `launched` counts as terminal, or by stating an explicit recovery procedure on
  the gate-rejected branch.

- **FR4 — Give I.2.b step 1's in-flight verification a defined outcome:**
  I.2.b step 1's trust-but-verify "Worktree/branch existence for tasks the
  journal claims are in-flight" check MUST have a stated effect on the
  reconciled state. Today the Stale-`launched` caveat asserts the wake-phase
  reconcile "catches" a stale `launched`, while I.2.b step 1 and I.2.a both
  state that a `launched` last event is ALWAYS in-flight regardless of any other
  source — so no rule says what the check's failure produces.

- **FR5 — Keep the hook contract consistent:** Any changed classification rule
  MUST stay consistent with the hook classification table and with what the four
  queue hooks actually do: `queue_launch_guard.py`, `queue_failure_net.py` and
  `queue_taskstop_net.py` judge from the journal's last event alone;
  `queue_stop_guard.py` additionally reads `tasks.{T}.status`. If a chosen
  mechanism requires a hook behavior change, all four hooks MUST be considered
  in the same change.

- **FR6 — SPEC-side coverage:** The protocol change MUST be accompanied by
  matching requirements, acceptance criteria and test scenarios in this
  feature's REQUIREMENTS.md / SPEC.md, and by matcher updates in
  `tests/test_recycled_task_id_consistency.py` and
  `tests/test_implement_routeback_gate.py` wherever a pinned literal is
  rewritten.

- **FR7 — Plugin version bump in lockstep:** Because files under `em-workflow/`
  change, `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` MUST be bumped to the same new version in
  the same change (current shared value: 0.1.47).

### Non-Functional Requirements

- **NFR1 - Maintainability (hook code untouched by default):** No hook under
  `em-workflow/hooks/` changes unless the adopted mechanism demonstrably
  requires it; if one does, the change covers `queue_launch_guard.py`,
  `queue_stop_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py`
  together.

- **NFR2 - Maintainability (test-module discipline):** Both named test modules
  follow a fixed convention: every new absence assertion is paired with a
  negative proof against a verbatim pre-change sample, every pre-change sample
  carries a non-vacuity "retained anchor" guard, no test is removed or skipped,
  and the module's test-method count does not decrease.

- **NFR3 - Maintainability (single-source discipline in implement-phase.md):**
  A rule stays owned by exactly one site and is cited elsewhere, never
  restated — the convention the current I.2.c gate text ("cited here as the
  owning rule, not restated") and the hook classification table already follow.

- **NFR4 - Reliability (suite green):** `python3 -m unittest discover -s tests`
  passes from the repository root.

- **NFR5 - Maintainability (no bare git commit/add lines):**
  `implement-phase.md` introduces no shell line matching a bare `git commit` or
  `git add -A` invocation outside `commit-docs.sh` (pinned by
  `TestContainmentAndInvariants.test_no_bare_git_commit_or_add_lines`).

## Implementation Approach

### Architecture

This feature's deliverable is a protocol document plus its guarding tests. There
is no runtime component, no service layer and no data store. The relevant
structure is the set of sites that own the route-back rules and the checkers
that pin them:

```
em-workflow/references/implement-phase.md
├── Step I.0            — pending-status statement (pinned literal)
├── I.2.a               — scope statement, recycled-task-id carve-out,
│                         unreachability paragraph (FR2 target)
├── I.2.b step 1        — trust-but-verify reconcile (FR4 target)
├── I.2.b step 3        — commit-docs.sh invocation (pinned literal)
└── I.2.c               — route-back admissibility gate, write set,
                          gate-rejected branch, batch-mode tail (FR1/FR3 target)

em-workflow/hooks/           (unchanged unless NFR1's condition is met)
├── queue_launch_guard.py    — journal last event only; deny_already_merged
├── queue_failure_net.py     — journal last event only; fires on SubagentStop
├── queue_taskstop_net.py    — journal last event only; fires after TaskStop
└── queue_stop_guard.py      — journal last event + tasks.{T}.status

tests/
├── test_recycled_task_id_consistency.py
└── test_implement_routeback_gate.py
```

**Statement of approach freedom:** the repair options recorded upstream
(defect 1: narrow the precondition vs. widen the carve-out; defect 2: a
reconciled-state precondition vs. an explicit recovery procedure) are candidate
approaches, not decisions. FR1–FR4 are therefore stated as outcomes, and the
plan phase may pick either option for each defect.

### Data Flow

The two defective paths, as they behave today:

```
Defect 1 (FR1/FR2):
  merge-task.sh appends `merged` to journal
    → `git merge-base --is-ancestor` fails
    → neither gate source reports `merged`, neither reports in-flight
    → I.2.c admits route-back; write set resets task ids to `pending`
    → planner `replace_all` renumbers; a task id is re-issued
    → journal last event for that id is still `merged`
    → queue_launch_guard.py denies the launch (deny_already_merged), forever

Defect 2 (FR3/FR4):
  a launch is allowed but never actually starts
    → journal last event stays `launched`
    → queue_failure_net.py fires only on an actual SubagentStop; and
      queue_taskstop_net.py only after a TaskStop tool call completes
    → no writer can terminalize `launched`
    → I.2.b step 1 / I.2.a treat `launched` as ALWAYS in-flight
    → route-back precondition never holds → abort is the only exit
```

### Wording and pinning constraints on the target document

These constrain where prose may be placed, and are the reason the acceptance
criteria above are stated as outcomes rather than as literals:

- **I.2.c token ban.** Two tokens are banned anywhere inside the I.2.c section
  by existing invariant tests; one of them is the verb for writing to the
  journal. Recovery prose placed in I.2.c therefore cannot describe journal
  mechanics directly, which pushes journal-mechanics wording toward I.2.b or the
  Supporting cast section, with I.2.c citing the owning site per NFR3. This
  document refers to that ban descriptively and does not restate the banned
  tokens.
- **I.2.a phrase ban.** The phrase "governs only" is forbidden in I.2.a by
  `TestI2aScopeStatementIsSelfConsistent`.
- **Gate-rejected branch slice.** The slice running from "When the gate does not
  hold" to the abort-phase bullet must not contain ROUTEBACK_TIP, the
  ordered-write-set phrase, or the forced worktree-removal command. It currently
  pins a sentence declaring that no retry loop, no alternative recovery route
  and no degraded route back is offered. Adding a recovery route on that branch
  collides with that pin; reclassifying a stale `launched` upstream does not.
- **Rewriting a pinned literal is permitted.** Where a currently-pinned literal
  legitimately needs rewriting — notably the terminal journal-last-event literal
  pinned in `tests/test_recycled_task_id_consistency.py`, and the
  gate-rejected-branch sentence above — the literal is NOT required to survive.
  The requirement is AC-7's: the matcher is updated in the same change, with a
  paired negative proof against the pre-change bytes and a non-vacuity retained
  anchor guard. No acceptance criterion in this document requires any particular
  new string to appear in `implement-phase.md`.
- **`replace_all` precondition.** `replace_all` is a protocol error while any
  task is `in_progress` / `merged` / `failed` (`workflow-patch.md`), so the
  route-back write set must still leave every task `pending` after the change.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the document under change.
- `em-workflow/references/workflow-patch.md`: owns `replace_all`'s precondition.
- `em-workflow/hooks/queue_launch_guard.py`, `queue_stop_guard.py`,
  `queue_failure_net.py`, `queue_taskstop_net.py`: the four queue hooks whose
  classification behavior FR5 must stay consistent with.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`:
  version lockstep (FR7).

**External Dependencies:**
- Python standard library `unittest` (test runner for NFR4).
- `git` (`git merge-base --is-ancestor`, the trust-but-verify probe).

### File Structure

```
em-workflow/
├── references/implement-phase.md
├── .claude-plugin/plugin.json
└── hooks/                        # unchanged unless NFR1's condition is met
    ├── queue_launch_guard.py
    ├── queue_stop_guard.py
    ├── queue_failure_net.py
    └── queue_taskstop_net.py
tests/
├── test_recycled_task_id_consistency.py
└── test_implement_routeback_gate.py
.claude-plugin/marketplace.json
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/implement-phase.md`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_implement_routeback_gate.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `em-workflow/hooks/queue_launch_guard.py` (only if NFR1's condition is met)
- `em-workflow/hooks/queue_stop_guard.py` (only if NFR1's condition is met)
- `em-workflow/hooks/queue_failure_net.py` (only if NFR1's condition is met)
- `em-workflow/hooks/queue_taskstop_net.py` (only if NFR1's condition is met)

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/routeback-admissibility-exits/**`
- `test-docs/routeback-admissibility-exits/**`

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

- [ ] **TS-1** (AC-1 → FR1, FR2): Document-contract assertion — the I.2.c
      admissibility text states the exit (or unreachability) required by AC-1,
      asserted against a whitespace-normalized slice of the I.2.c section.
- [ ] **TS-2** (AC-2 → FR3, FR4): Document-contract assertion — the
      stale-`launched` recovery path of AC-2 is present, and I.2.b step 1's
      existence check has a stated outcome.
- [ ] **TS-3** (AC-3 → FR2): Absence assertion plus paired negative proof — the
      falsified I.2.a justification sentence is gone, proven against a verbatim
      pre-change sample captured from base 9f5d7ae.
- [ ] **TS-4** (AC-7, AC-4 → FR6, NFR2, NFR3, NFR5): Matcher-update regression
      proofs for each rewritten pinned literal (notably the terminal
      journal-last-event literal in
      `tests/test_recycled_task_id_consistency.py`, if rewritten), each with a
      non-vacuity retained-anchor guard.
- [ ] **TS-5** (AC-7 → NFR2, NFR3, NFR5): Retention assertions — the I.2.c
      heading's byte-identity, the batch-mode paragraph as the byte-identical
      tail of I.2.c, I.2.b step 3's `commit-docs.sh` line-wrap literal, I.2.a's
      Select literal and Step I.0's pending-status literal all survive.
- [ ] **TS-6** (AC-7, NFR5 → NFR2, NFR3, NFR5): Invariant assertions — the two
      forbidden tokens stay absent from the whole I.2.c section; no "governs
      only" in I.2.a; no "never reads workflow.yaml" claim anywhere; no bare git
      commit/add line.
- [ ] **TS-7** (AC-6 → FR7): Version lockstep — the plugin manifest and
      marketplace entry agree, with patch strictly greater than 47.

### Integration Tests

- [ ] `python3 -m unittest discover -s tests` passes from the repository root
      (AC-5 → NFR4). This is the aggregate run of TS-1..TS-7 together with the
      pre-existing suite.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] Journal last event `merged` but `git merge-base --is-ancestor` fails:
      neither gate source reports `merged`, neither reports in-flight, so
      route-back is admitted today and the recycled id inherits `merged` — the
      FR1 trigger. Expected handling: FR1's exit, or a stated unreachability
      that covers exactly this case.
- [ ] `queue_launch_guard.py` denies any launch whose journal last event is
      `merged` (`deny_already_merged`), reading the journal only; the journal is
      append-only and the orchestrator never writes it, so no writer can retire
      that state — the launch denial is permanent. Expected handling: the
      adopted mechanism must not depend on retiring a journal state.
- [ ] Stale `launched`: `queue_failure_net.py` fires only on an actual
      SubagentStop and `queue_taskstop_net.py` only after a TaskStop tool call
      completes, so an allowed-but-never-started launch leaves `launched` with
      no writer able to terminalize it. Expected handling: FR3/FR4's recovery
      path or reconciled-state classification.
- [ ] A task with no journal event at all never blocks route-back
      (`replace_all` recycles every id, so it has nothing to inherit) — must
      remain true after the change.
- [ ] Wording constraint inside I.2.c: recovery prose placed there cannot use
      the journal-write verb, which pushes journal-mechanics wording toward
      I.2.b or the Supporting cast section (see "Wording and pinning constraints"
      above).
- [ ] Wording constraint inside I.2.a: the phrase "governs only" is forbidden.
- [ ] Gate-rejected branch slice: an added recovery route on that branch
      collides with its currently-pinned "no alternative recovery route"
      sentence, whereas reclassifying a stale `launched` upstream does not.
      Expected handling: either avoid that branch, or rewrite the pin with the
      AC-7 paired matcher update and negative proof.
- [ ] `replace_all` is a protocol error while any task is `in_progress` /
      `merged` / `failed` (`workflow-patch.md`), so the route-back write set
      must still leave every task `pending` after the change.

### Performance Tests

Not applicable — the change has no runtime performance surface.

## User Experience

The only user-visible surface is I.2.c's AskUserQuestion menu (retry / route
back to planning / abort phase) and the phase's terminal report. Any new exit
must be expressible within that menu or happen automatically before it; batch
mode never offers route-back automatically (`implement.failed-task` auto-selects
retry once, then abort).

## Security Considerations

- **New attack surface:** None. The change is expected to be documentation plus
  tests.
- **If a hook is touched:** its existing defenses must be preserved —
  `O_NOFOLLOW` journal open, flock-serialized compare-and-append, task-id and
  absolute-worktree-path validation, and `agents.jsonl` / `journal.jsonl`
  same-directory containment — along with the fail-open convention.
- **Authentication / Authorization / XSS / SQL injection / CSRF:** not
  applicable to this change.

## Error Handling

The protocol's failure surface, not an error-code table:

| Condition | Today | Required outcome |
|---|---|---|
| Recycled task id whose journal last event is `merged` | Launch permanently denied by `deny_already_merged` | FR1: an automatically-recoverable exit, or a stated unreachability covering the trust-but-verify case |
| Plan carrying a stale `launched` | Abort is the only exit | FR3: a protocol-defined recovery path other than abort |
| I.2.b step 1 existence check fails for a task the journal calls in-flight | No rule states the effect | FR4: a stated effect on the reconciled state |

## Traceability

| Requirement | Acceptance criteria | Test scenarios |
|---|---|---|
| FR1 | AC-1 | TS-1 |
| FR2 | AC-1, AC-3 | TS-1, TS-3 |
| FR3 | AC-2 | TS-2 |
| FR4 | AC-2 | TS-2 |
| FR5 | — (solution-shape constraint; see NFR1) | — |
| FR6 | AC-4 | TS-4 |
| FR7 | AC-6 | TS-7 |
| NFR1 | — (solution-shape constraint; see FR5) | — |
| NFR2 | AC-4, AC-7 | TS-4, TS-5, TS-6 |
| NFR3 | AC-7 | TS-4, TS-5, TS-6 |
| NFR4 | AC-5 | Integration run |
| NFR5 | AC-7 | TS-4, TS-5, TS-6 |

FR5 and NFR1 constrain the shape of any adopted solution rather than asserting a
separately testable document property; they are checked when a mechanism is
chosen in the plan phase.

## Success Criteria

- [ ] All functional requirements (FR1–FR7) are implemented and tested
- [ ] All test scenarios (TS-1..TS-7) pass
- [ ] Security requirements are satisfied (no new attack surface; hook defenses
      preserved if a hook is touched)
- [ ] REQUIREMENTS.md and SPEC.md are complete and mutually consistent
- [ ] Code review is completed
- [ ] AC-1 through AC-7 are all satisfied

## Assumptions

- Scope is `em-workflow/references/implement-phase.md` plus the two named test
  modules plus the two version manifests; hook source stays unchanged unless the
  adopted mechanism provably requires all four hooks to change (the task
  description's own constraint).
- The task description's repair options (defect 1: narrow the precondition vs.
  widen the carve-out; defect 2: reconciled-state precondition vs. an explicit
  recovery procedure) are candidate approaches, not decisions; the requirements
  above are stated as outcomes so the plan phase may pick either.
- No LICENSE file exists at the integration worktree root, so the project SPDX
  identifier is unresolved and is recorded as none rather than guessed.
- `feature-docs/recycled-task-id-consistency/reviews/round2.yaml` (finding ids
  `29b99dea6a37377d` / `c431ec8ba89742db`) was not supplied in the envelope and
  was not read; those ids are carried as provenance only.
- PR #5's conflict integration with main is out of scope per the task
  description; this specification is grounded entirely in base 9f5d7ae.
- The design step is skipped: this is a protocol-document and test-only change
  with no user-facing UI, no rendered output and no design-system inputs.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement above is `resolved`.

## References

- Requirements document (Japanese): `feature-docs/routeback-admissibility-exits/REQUIREMENTS.md`
- Protocol under change: `em-workflow/references/implement-phase.md`
- `replace_all` precondition: `em-workflow/references/workflow-patch.md`
- Guarding tests: `tests/test_recycled_task_id_consistency.py`,
  `tests/test_implement_routeback_gate.py`
- Queue hooks: `em-workflow/hooks/queue_launch_guard.py`,
  `queue_stop_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`
- Version manifests: `em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
- Provenance only (not read): `feature-docs/recycled-task-id-consistency/reviews/round2.yaml`
  findings `29b99dea6a37377d` / `c431ec8ba89742db`
