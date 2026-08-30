# Reconciliation Record: I.2.c Failed handling

This record establishes, with re-checkable anchors, that the already-merged
`### I.2.c: Failed handling` text in `em-workflow/references/implement-phase.md` expresses the
intent of both source features (recycled-task-id-consistency and routeback-gate-postcondition)
without contradiction, names every deliberate departure from a source SPEC's literal wording
together with its authoritative document, and records PR #5's settled disposition.

Anchor format: every claim below carries either (a) a quoted phrase, its containing section, and
the line range observed in this worktree at writing time, or (b) a test module path plus a
test-method name. Where the observed range differs from the range cited by
`feature-docs/i2c-routeback-reconciliation/SPEC.md`, the difference is noted; where no difference
is noted, the observed range matched the cited range exactly. Source-feature requirement IDs are
always qualified by their feature name.

## 1. Merged gate condition (FR1)

**Section**: `### I.2.c: Failed handling`, the "route back to planning" bullet,
`em-workflow/references/implement-phase.md`.

The merged route-back gate is stated as a conjunction:

> "no task has status `merged`, and no task has status `in_progress`"

Observed lines 407-408 (`SPEC.md` cites 407-409; the quoted conjunct itself ends at 408, the
extra line SPEC.md's range covers is the following "both re-read from workflow.yaml..." clause).

Each half is stated as a union of a `workflow.yaml` source and a Step I.2.b journal source:

> "The `merged` half is likewise a union of two independent sources, either of which blocks:
> workflow.yaml reporting a task `merged`, OR Step I.2.b step 1's reconciled state reporting a
> task `merged` (journal last event `merged`, verified by `git merge-base --is-ancestor` as that
> step already requires) — cited here as the owning rule, not restated."

Observed lines 413-418 (matches SPEC.md's cited range exactly).

> "The `in_progress` half is a union of two independent sources, either of which blocks:
> workflow.yaml reporting a task `in_progress`, OR Step I.2.b's last-event-per-task rule reporting
> a task in-flight (a `launched` last event, with the recycled-task-id carve-out that step already
> defines) — cited here as the owning rule, not restated."

Observed lines 418-423 (matches SPEC.md's cited range exactly).

The sentence deriving the terminal-last-event property from the second union member:

> "The second source is what makes the gate admit route-back only when every task in the current
> plan whose journal carries any event has a terminal journal last event (`merged` or `failed`) —
> the planner's `replace_all` recycles every id, not only the failed ones, so a task with no
> journal event at all has nothing to inherit and never blocks route-back."

Observed lines 423-428 (matches SPEC.md's cited range exactly). This sentence is also the anchor
for **"a task with no journal event at all never blocks route-back"**: it is stated explicitly in
the clause above, non-blocking is not inferred.

**recycled-task-id-consistency's terminal-last-event precondition (its own FR3/AC-3) is satisfied
AS a union member, not as a separate check.** Anchor: `feature-docs/recycled-task-id-consistency/SPEC.md`
Merge Note row 1, line 21: "The second source is what rejects a non-terminal (`launched`) last
event, so FR3's precondition holds as that union member rather than as a separate check."
Classification: **satisfied-under-the-reconciled-reading**, authoritative document
`em-workflow/references/implement-phase.md` (the reading is adopted by
recycled-task-id-consistency `SPEC.md` Merge Note row 1, line 21).

**"no task has status `merged`" survives verbatim.** Anchor: the conjunction quote above, lines
407-408. Classification: **satisfied-verbatim**, against both routeback-gate-postcondition AC1
and recycled-task-id-consistency AC-3.

**Both routeback-gate-postcondition AC1 and recycled-task-id-consistency AC-3 are satisfied by
this single sentence group** (lines 407-428, plus the write-set-resets-`failed`-to-`pending` text
at lines 434-437: "set the `implement` step back to `pending`, record each such task's failure
reason ... and set `tasks.{T}.status` back to `pending` for every task in that set").

- routeback-gate-postcondition AC1 (`feature-docs/routeback-gate-postcondition/SPEC.md` lines
  35-37: the gate stated as "no task has status `merged` AND no task has status `in_progress`",
  write set still resets `failed` tasks to `pending`): **satisfied-verbatim**.
- recycled-task-id-consistency AC-3 (`feature-docs/recycled-task-id-consistency/SPEC.md` line 50:
  a separately-stated precondition sentence, positioned before the ordered write set):
  **satisfied-under-the-reconciled-reading** — the merged text expresses the same precondition as
  a union member rather than as its own sentence. Authoritative document:
  `em-workflow/references/implement-phase.md`; recycled-task-id-consistency `SPEC.md` Merge Note
  row 1 (line 21) is the adopting record.

## 2. Admitted-path ordering (FR2)

**Section**: `### I.2.c: Failed handling`, the "route back to planning" bullet, admitted branch.

Observed order (each anchor quoted, `em-workflow/references/implement-phase.md`):

1. Gate decision — the conjunction group, lines 407-428 (Section 1 above).
2. "Refresh the integration worktree first" — lines 428-429.
3. `ROUTEBACK_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)` — line 431.
4. "make one ordered workflow.yaml write set over the reset target set" — lines 432-433 (the write
   set itself runs through line 443: `create-plan` → `needs_update`, `implement` → `pending`,
   failure reason into `tasks.{T}.notes`, `tasks.{T}.status` → `pending`).
5. Route-back commit — "Commit that write set next, BEFORE any cleanup" — line 444, followed by the
   `commit-docs.sh` call at lines 445-446.
6. Worktree/branch cleanup — "Only once that commit succeeds, clean up worktrees and branches for
   exactly the tasks the write set just reset" — lines 450-452.
7. End-of-phase report — "End the phase with a" (clear report) — line 459.

This order is confirmed by test:
`tests/test_implement_routeback_gate.py`::`test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`
(`class TestGateDecisionPrecedesAllSideEffects`), which asserts
`gate_idx < refresh_idx < tip_idx < write_set_idx < commit_idx < cleanup_idx`.

**Commit-before-cleanup quotes**:

> "Commit that write set next, BEFORE any cleanup:" (line 444)

> "Only once that commit succeeds, clean up worktrees and branches for exactly the tasks the write
> set just reset" (lines 450-452; the quoted "Only once that commit" clause SPEC.md cites at
> 450-451 is the opening of this same sentence)

**recycled-task-id-consistency `SPEC.md` records the supersession of its own as-written
cleanup-before-commit ordering** in its Merge Note row 3, line 23: "Architecture / Data Flow: write
set → cleanup → commit | write set → **commit → cleanup**. An unexpected non-zero exit at the
route-back commit then stops the phase at a point where no worktree or branch has been deleted."
Classification of the as-written ordering (`feature-docs/recycled-task-id-consistency/SPEC.md`
line 160 diagram "ordered workflow.yaml write set → cleanup → commit"; NFR1 line 87 "`git worktree
remove --force` must precede the FIRST `commit-docs.sh`"; TS-10 line 244 "cleanup precedes the
first `commit-docs.sh`"): **superseded**. Authoritative document:
`em-workflow/references/implement-phase.md`; the supersession itself is recorded by
recycled-task-id-consistency `SPEC.md` Merge Note row 3 (line 23), and
`tests/test_recycled_task_id_consistency.py` is authoritative for the test-level expression —
confirmed by `test_commit_precedes_cleanup_precedes_end_of_phase_report`
(`class TestI2cOrderings`, lines 892-897), which asserts `commit_idx < cleanup_idx < report_idx`,
and whose class docstring (lines 864-871) records the commit-before-cleanup rationale ("An
unexpected non-zero exit at the route-back commit must not leave the write set uncommitted with
worktrees already deleted").

**routeback-gate-postcondition AC3's "gate decision before any `commit-docs.sh` invocation and
before route-back cleanup" still holds.** The gate sentence group (lines 407-428) precedes the
first `commit-docs.sh` invocation inside the I.2.c section, which occurs at line 445. Classification
(`feature-docs/routeback-gate-postcondition/SPEC.md` AC3, lines 47-49; FR3, lines 91-94):
**satisfied-verbatim**.

**Documented residual leftover state**:

> "this order's one residual leftover state is the commit succeeding and the cleanup not yet
> running, i.e. stale worktrees for tasks now `pending`, which Step I.2.a's resume guard and its
> recycled-task-id rule already cover"

Observed lines 456-459 (matches SPEC.md's cited range exactly).

## 3. Rejected-path side effect (FR3)

**Section**: `### I.2.c: Failed handling`, "When the gate does not hold" branch.

The rejected path performs exactly one write and one commit, preceded by a refresh and a terminal
tip capture:

1. Refresh — "The phase instead refreshes the integration worktree first (the same `reset --hard`
   as above)" — lines 473-474.
2. Terminal tip capture — `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)` — line
   475.
3. The single write — `implement` step's `status` set to `failed`:

> "sets the `implement` step's `status` to `failed` in workflow.yaml — the single write this path
> makes — and commits exactly that write:"

Observed lines 476-478 (matches SPEC.md's cited range for the single-write sentence, 473-479,
within one line of the write clause itself).

4. The one commit — `commit-docs.sh "$WT_ROOT/integration" "docs({feature}): implement route-back
   gate rejected" "$TERMINAL_TIP"` — lines 478-479.

**Scoped no-side-effect sentence**:

> "There is no route-back write set, no worktree/branch cleanup and no route-back commit on this
> path — the terminal status write and its own commit are the ONLY side effect."

Observed lines 479-482 (SPEC.md cites 480-482; the sentence's opening clause starts at the end of
line 479).

**All four gate-rejection causes**, as the merged text states them:

> "When the gate does not hold — because a task has status `merged`, because Step I.2.b step 1's
> reconciled state reports a task `merged` though workflow.yaml does not, because a task has
> status `in_progress`, or because Step I.2.b's last-event-per-task rule reports a task in-flight —
> this automatic re-entry does not apply"

Observed lines 467-472 (matches SPEC.md's cited range exactly). The four causes: (1) a task has
status `merged`; (2) Step I.2.b step 1's reconciled state reports a task `merged` though
workflow.yaml does not; (3) a task has status `in_progress`; (4) Step I.2.b's last-event-per-task
rule reports a task in-flight.

**No retry loop, no alternative recovery route, no degraded route back**:

> "No retry loop, no alternative recovery route, and no degraded route back is offered for this
> path."

Observed lines 485-486 (matches SPEC.md's cited range exactly).

**Reconciled reading of routeback-gate-postcondition AC3's "nothing".**
routeback-gate-postcondition FR3 (`feature-docs/routeback-gate-postcondition/SPEC.md` lines 91-94)
states "the rejected path commits nothing and mutates nothing"; its AC3 (lines 47-49) states
"nothing is committed on the rejected path." routeback-gate-postcondition's own FR2 (lines 86-90)
requires the `implement: failed` write, so an unscoped reading of "nothing" would make that
feature self-contradictory. The merged text (Section 3 above) states the scoped form explicitly:
"nothing" scopes to the route-back write set, route-back commit and worktree/branch cleanup — not
to the terminal status write and its own commit. Classification: **satisfied-under-the-reconciled-reading**.
Authoritative document: `em-workflow/references/implement-phase.md`; recycled-task-id-consistency
`SPEC.md` Merge Note row 2, line 22, already adopts this reading: "Gate rejection takes the
rejected path, which *writes* the `implement` step's `status` to `failed` and commits exactly that
write — the terminal status write plus its own commit are the only side effect. Same guarantee,
stated as an explicit write rather than as an absence."

**Distinction between the route-back commit and the terminal status commit**: the rejected path
never invokes the route-back commit (the `commit-docs.sh` call at lines 445-446, message
`docs({feature}): implement route back to planning`); it invokes only the terminal status commit
(lines 478-479, message `docs({feature}): implement route-back gate rejected`). No route-back
write set, no worktree/branch cleanup and no route-back commit occur on the rejected path (quoted
above, lines 479-482).

## 4. Test-suite evidence (FR4)

Both document-contract modules encode the MERGED wording and ordering, not either pre-merge
variant. For each of the three reconciled hunks, at least one test method pins the merged form:

| Reconciled hunk | Test method | Module |
|---|---|---|
| Admitted-path order (gate → refresh → tip → write set → commit → cleanup) | `test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup` | `tests/test_implement_routeback_gate.py` (`class TestGateDecisionPrecedesAllSideEffects`) |
| Rejected-path order (gate → terminal write → terminal commit) | `test_rejected_path_order_gate_terminal_write_terminal_commit` | `tests/test_implement_routeback_gate.py` (`class TestGateDecisionPrecedesAllSideEffects`) |
| Rejected path writes `implement: failed` and commits it (not merely "stays failed") | `test_implement_is_written_to_failed_and_committed` | `tests/test_implement_routeback_gate.py` (`class TestRejectedPathHasSingleGeneralizedTerminal`) |
| Admitted-path commit precedes cleanup precedes end-of-phase report | `test_commit_precedes_cleanup_precedes_end_of_phase_report` | `tests/test_recycled_task_id_consistency.py` (`class TestI2cOrderings`) |

Additional corroborating methods for the `in_progress`-half-as-union assertions (both encode the
merged form, not a pre-merge variant):

- `test_in_progress_half_is_stated_as_a_union`, `test_union_second_source_is_step_i2b_last_event_rule`,
  `test_union_cites_step_i2b_as_owner_without_restating` — `tests/test_implement_routeback_gate.py`
  (`class TestRouteBackGateIsConjunctionOfBothBlockers`).
- `test_precondition_names_terminal_event_with_merged_and_failed`,
  `test_precondition_precedes_ordered_write_set`, `test_existing_merged_gate_survives` —
  `tests/test_recycled_task_id_consistency.py` (`class TestRouteBackPreconditionRequiresTerminalEvent`).

`tests/test_recycled_task_id_consistency.py`'s `class TestI2cOrderings` docstring (lines 864-871)
records the commit-before-cleanup rationale directly: "The commit-before-cleanup order is owned by
I.2.c itself: an unexpected non-zero exit at the route-back commit must not leave the write set
uncommitted with worktrees already deleted." This is the module encoding the merged ordering
rather than recycled-task-id-consistency `SPEC.md`'s as-written (superseded) ordering — see Section
2 above.

**Observed suite outcome**: `python3 -m unittest discover -s tests`, run from the repository root
in this worktree, exited 0 with:

```
Ran 1522 tests in 12.759s

OK
```

This matches the 1522-test, OK baseline recorded in this feature's own `SPEC.md` ASM2. No test was
added, deleted, modified or skipped by this task — the task's change set (Section 7) contains no
path under `tests/`. As additional evidence that both cited modules are green in their own right:
`python3 -m unittest tests.test_implement_routeback_gate` reports "Ran 105 tests ... OK", and
`python3 -m unittest tests.test_recycled_task_id_consistency` reports "Ran 70 tests ... OK".

## 5. Settled dispositions (FR5, FR6)

### Version-bump requirement — resolved-not-applicable

This feature's own `SPEC.md` FR5 (lines 98-108) states the task description's fifth acceptance
criterion (a lockstep version bump) as NOT APPLICABLE: it is conditioned on modifying a file under
`em-workflow/`, and the resolved scope forbids any such modification, so the condition never
arises. This is recorded here as **resolved-not-applicable**, not as an outstanding item.

Observed lockstep pair: `em-workflow/.claude-plugin/plugin.json` reads `"version": "0.1.45"`
(observed at its line 7); the `em-workflow` entry of `.claude-plugin/marketplace.json` reads
`"version": "0.1.45"` (observed at its line 26). Neither file is modified by this task.

recycled-task-id-consistency FR9/AC-9 (`feature-docs/recycled-task-id-consistency/SPEC.md` FR9
line 83, AC-9 line 66) targeted `0.1.38`. That target is historical: it was satisfied at merge
time and has since been superseded by later bumps to `0.1.45`. The observed `0.1.45` lockstep pair
is not a violation of recycled-task-id-consistency AC-9.

### PR #5 — MERGED

This record states PR #5 as MERGED, with both pieces of orchestrator evidence carried forward from
this feature's own `SPEC.md` ASM2: "`gh pr view 5` reports state MERGED (base main, head
`em-workflow/recycled-task-id-consistency/integration`); `git merge-base --is-ancestor
origin/em-workflow/recycled-task-id-consistency/integration origin/main` returns true;
`python3 -m unittest discover -s tests` reports 1522 tests, OK."

This maps to the task description's fourth acceptance criterion (as characterized by this
feature's own `SPEC.md` FR6, lines 110-117) as **satisfied by the stronger first disjunct**: the
branch is not merely mergeable, it is merged. No further action on PR #5 is owed.

The task description's premise — PR #5 CONFLICTING, reconciliation outstanding — is **stale**. The
evidence that superseded it is the `gh pr view 5` MERGED state and the `git merge-base
--is-ancestor` ancestry check above, both carried in this feature's `SPEC.md` ASM1 (lines 372-376)
and ASM2.

recycled-task-id-consistency `SPEC.md`'s in-repo Merge Note (lines 9-27) is itself corroborating
evidence that the reconciliation landed, independent of the git and gh observations: it is a
document that already exists on `main`, recording that "the integration adopted [routeback-gate-postcondition]'s
I.2.c design and re-expressed this feature's intent (FR3-FR5) in its vocabulary" (lines 15-16).

## 6. Departure table (NFR3)

Every departure between the merged text and a source SPEC's literal wording is listed here — the
only table of this kind in the record.

| Source statement | Merged statement | Authoritative document |
|---|---|---|
| routeback-gate-postcondition FR3/AC3: the rejected path "commits nothing and mutates nothing" (`feature-docs/routeback-gate-postcondition/SPEC.md` lines 91-94, 47-49) | The rejected path writes `implement: failed` and commits exactly that write; "nothing" scopes to the route-back write set, commit and cleanup (`em-workflow/references/implement-phase.md` lines 476-482) | `em-workflow/references/implement-phase.md`; the reading is already adopted by recycled-task-id-consistency `SPEC.md` Merge Note row 2 (line 22) |
| recycled-task-id-consistency `SPEC.md`: write set → cleanup → commit (line 160 diagram, NFR1 line 87, TS-10 line 244) | write set → commit → cleanup (`em-workflow/references/implement-phase.md` line 444, lines 450-452) | `em-workflow/references/implement-phase.md`; the supersession is recorded by recycled-task-id-consistency `SPEC.md` Merge Note row 3 (line 23), and `tests/test_recycled_task_id_consistency.py` is authoritative for the test-level expression |

routeback-gate-postcondition `SPEC.md` carries no merge note of its own (confirmed: no "Merge
Note" heading exists in `feature-docs/routeback-gate-postcondition/SPEC.md`) — it is the feature
that landed first — so this record is the only place its AC3 departure is documented.

No superseded statement appears anywhere in this record as "satisfied": both rows above are
classified `superseded` (the ordering row) or `satisfied-under-the-reconciled-reading` (the
side-effect row, Section 3) — never `satisfied-verbatim`.

## 7. Change-set scope statement (FR7, NFR2)

This task's change set consists of exactly the two files listed under this feature's task0001 plan
Scope:

- `feature-docs/i2c-routeback-reconciliation/RECONCILIATION-RECORD.md` (this file)
- `test-docs/i2c-routeback-reconciliation/task0001.tests.yaml`

`git diff --name-only` against this task branch's base (merge-base with
`em-workflow/i2c-routeback-reconciliation/integration`) lists no path under `em-workflow/`, no path
under `tests/`, and neither `em-workflow/.claude-plugin/plugin.json` nor
`.claude-plugin/marketplace.json`:

```
feature-docs/i2c-routeback-reconciliation/RECONCILIATION-RECORD.md
test-docs/i2c-routeback-reconciliation/task0001.tests.yaml
```
