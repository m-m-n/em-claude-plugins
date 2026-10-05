# Implementation Plan: prelaunch-inprogress-routeback

## Overview

task0001 and task0002 (merged) moved Step I.2.a's launch-state capture /
refresh / write / commit sequence behind the approval gate and the launch
loop. This plan adds FR7–FR13 / NFR5. The launch-state commit records a task
that launched and then failed before that commit as `failed`. The
recycled-task-id carve-out applies only when the task's last `failed` journal
event is the one route-back reset, as identified by a new orchestrator-only
record, `tasks.{T}.routeback_failed_journal_line`. The Stop hook, the
workflow schema, the re-planning carry-over and the worker-patch validator
are aligned with that record.

## Technology Stack

- **Protocol documents**: Markdown — `em-workflow/references/implement-phase.md`
  (orchestrator protocol), `em-workflow/references/workflow-schema.md`
  (workflow.yaml schema SSOT), `em-workflow/references/workflow-patch.md`
  (worker patch contract).
- **Hook**: `em-workflow/hooks/queue_stop_guard.py` — Python 3, standard
  library only, line-based reading, fail-open.
- **Validator**: `em-workflow/scripts/validate-worker-output.py` — Python 3,
  standard library only.
- **Tests**: Python 3, standard library `unittest` only (`test/README.md`).
- **New dependencies**: none (no license entry required).
- **Commands**: `python3 -m unittest discover -s tests` (repo-tests),
  `python3 em-workflow/scripts/check-plugin-invariants.py .` (plugin-invariants).

## Layer Structure

| Layer | Content | Allowed dependency direction |
|-------|---------|------------------------------|
| Schema / contract documents | `workflow-schema.md` (defines the record), `workflow-patch.md` (carry-over list) | none — they are the SSOT the others cite |
| Protocol document | `implement-phase.md` | cites the schema for the record's definition; never restates it |
| Executables | `queue_stop_guard.py` (reader), `validate-worker-output.py` (rejects worker writes; carries the record through `apply_patch`) | implement the contracts below; neither imports the other |
| Tests | `tests/test_*.py` | read documents as text or run the executables (hook as a subprocess, validator in-process via its loaded module); a test module never imports another task's new test module |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Record `tasks.{T}.routeback_failed_journal_line` | Identifies the exact journal `failed` event that a route-back reset returned to `pending` | **Name**: literal `routeback_failed_journal_line`, a key of the task's own `tasks.{T}` mapping in workflow.yaml. **Value**: the 1-based physical line number, in `{project_root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl`, of the task's last `failed` event at reset time. **Line counting**: lines are delimited by LF only (a CR is never a delimiter); line N is the N-th LF-terminated segment counted from 1; a final segment with no terminating LF counts as one more line when it is non-empty; blank lines, malformed lines, lines with an unknown event and lines with an invalid task id are all counted. **Canonical form**: an unquoted decimal integer of ASCII digits whose first digit is 1–9. Every reader treats a value that is absent, `null`, or not in canonical form as "no record". **Writer**: only the orchestrator, inside Step I.2.c's route-back write set. A reset task with no journal event gets no record. **Never rewritten** by the I.2.a launch-state commit, I.2.b step 3, a retry or a terminal-status write. It is overwritten only when a later route-back resets the same task again. Nothing clears it. **Readers**: I.2.a selection, I.2.b step 1 reconcile, `queue_stop_guard.py`. **Re-planning**: copied verbatim for carried ids. **Workers**: may never set it in `tasks_patch.entries`. | task0003, task0004, task0005, task0006 |
| Schema anchor | Where the record is defined | `workflow-schema.md` carries a section whose heading line is exactly ``## `routeback_failed_journal_line` `` (task0006). `implement-phase.md` cites `references/workflow-schema.md` for the definition and does not restate the counting or canonical-form rules (task0004). | task0004, task0006 |
| Three-condition match rule | Classifies a `pending` + `failed` task | A task is **unlaunched** under the recycled-task-id carve-out only when all three hold: (1) its workflow.yaml `status` is `pending`; (2) its journal last event is `failed`; (3) that event's physical line equals the task's record. Otherwise a `pending` + `failed` task is **failed**: the orchestrator routes it to I.2.c's failure handling (batch: `implement.failed-task`), and the Stop hook does not block for that feature (exit 0). The no-event, `launched` and `merged` classifications do not change. The protocol text (task0004) and the hook (task0005) implement this rule identically. | task0004, task0005 |
| Term "launch-state commit" | Names the Region L commit whose third argument is `"$LAUNCH_TIP"` | Region L keeps the literal term (task0003). The FR5 / FR10 sentences in Region P refer to that commit with the same literal term (task0004). Neither side restates the other's rule. | task0003, task0004 |
| Edit regions in `implement-phase.md` | Disjoint ownership of the one shared file | **Region L** runs from the paragraph that opens "For each selected task T" up to the `### I.2.b: Wake phase` heading. task0003 edits it; no other task does. **Region P** runs from the `### I.2.a: Launch phase` heading up to "For each selected task T". task0004 edits it, plus three other spots: I.2.b step 1's `failed` exception clause, a single added item in I.2.c's route-back write set, and the Supporting cast Stop-hook bullet. No task edits the Step I.2 intro, the Branch & Worktree Model, the hook classification table, or any other part of I.2.b / I.2.c. | task0003, task0004 |
| Protected text (NFR1) | I.2.c and the exit-4 recovery bullet | The `### I.2.c: Failed handling` section is unchanged except for the one write-set item task0004 adds. The Branch & Worktree Model's exit-4 recovery bullet is byte-identical to the implement base. | task0003, task0004 |
| Test-module ownership | Which task edits which test module | **task0003** creates `tests/test_prelaunch_failed_launch_state.py`. **task0004** creates `tests/test_routeback_record_carve_out.py`. It is the only task that edits `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py` and `tests/test_implement_routeback_gate.py`, and only to follow changed wording. **task0005** creates `tests/test_queue_stop_guard_routeback_record.py`. It is the only task that edits `tests/test_queue_stop_guard.py` and `tests/test_queue_hook_status_read_pin.py`. **task0006** creates `tests/test_routeback_record_schema_patch.py`. It is the only task that edits `tests/test_replanning_carry_over.py`. **No task** edits `tests/test_prelaunch_inprogress_launch_order.py` or `tests/test_prelaunch_inprogress_pending_launched.py`. | all |

## Conventions

- **Test module shape** (every new module):
  - Standard library `unittest` only, discovered by
    `python3 -m unittest discover -s tests` with no registration.
  - Never imports another task's new test module.
  - Document sections are sliced by heading text, using the same boundaries
    existing modules use.
  - Content assertions run on whitespace-normalized text; byte-identity
    assertions run on raw text. The two are never mixed in one assertion.
  - Every literal asserted as new wording is a module-level constant, read
    by both its positive test and its negative-proof test.
  - Every new-wording matcher has a negative proof against a verbatim
    pre-change sample of the same region. The sample is captured from the
    document as it reads at the task's base revision, never reconstructed.
    Each negative proof also has a non-vacuity guard: an anchor present in
    both the sample and the live document.
  - Hooks are run as subprocesses, with JSON on stdin.
  - Fixtures are built in temporary directories. No test writes under
    `em-workflow/`.
- **Document wording**:
  - New prose cites owning rules by reference and does not restate them:
    the record's definition in `workflow-schema.md`, the Branch & Worktree
    Model exit-4 recovery bullet, the I.2.a in-flight rule, and
    `references/batch-policies.yaml`'s `implement.failed-task`.
  - No new git command is introduced, and no line that starts with `git`
    and commits or adds is introduced.
- **Existing tests**: an existing module is edited only in three cases:
  - to follow wording this feature changes;
  - to add a matching record to a recycled-task-id fixture (FR9);
  - to follow the carry-over field list (FR12).
  No existing judgment case is deleted (NFR3).
- **Error handling**:
  - The Stop hook fails open (exit 0) on any unexpected state.
  - The validator reports a rejected worker patch with its existing
    machine-readable error shape.

## Cross-task Design Decisions

### D1: One record, one definition, many readers

The record's value, counting rule and canonical form are defined once, in
`workflow-schema.md` (task0006). Every reader treats a non-canonical value
as "no record". This includes the orchestrator's reading in I.2.a and
I.2.b step 1 (task0004), not only the hook (task0005). It prevents the two
classifiers from disagreeing on a value such as one with a leading zero.
Affected tasks: task0004, task0005, task0006.

### D2: Disjoint edit regions inside `implement-phase.md`

FR7 lives in Region L (task0003). FR5 / FR8 / FR10 live in Region P,
I.2.b step 1, the I.2.c write set and the Stop-hook bullet (task0004).
Neither task's region overlaps the other's. Each task's own worktree keeps
the full suite green on its own, because each task leaves the other
region's pinned text untouched.
Affected tasks: task0003, task0004.

### D3: The record is written only at route-back, so every other `pending` + `failed` is `failed`

The record is never written at launch or by a status update. It is never
cleared. So a later failure of the same task moves the last `failed` event
to a new line, and the record no longer matches. A failure that never
reached the launch-state commit (interruption, second exit 4) also fails
the match. Both cases therefore go to I.2.c's user decision. FR7 covers the
remaining window inside one I.2.a entry by writing such a task `failed`
outright.
Affected tasks: task0003, task0004, task0005.

### D4: Workers cannot author the record; re-planning carries it

The record's only writer is the orchestrator. `validate-worker-output.py`
rejects any `tasks_patch.entries` entry that carries the key, in both
`replace_all` and `append`, even when its value is null.
`workflow-patch.md` adds the field to the verbatim carry-over list.
`apply_patch` already deep-copies carried records, so the record survives a
re-plan without entering the `preserve` vocabulary.
Affected tasks: task0006 (the tasks that read the record rely on this).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The hook and the orchestrator count journal lines differently, so one relaunches a task the other routes to I.2.c | Medium | High | Single counting rule in Shared Components, defined once in `workflow-schema.md` (D1); hook tests with blank, malformed and CR-containing lines before the target line |
| task0004's I.2.c insertion splits a phrase that an existing module pins | Medium | Medium | task0004 lists the pinned spans and the insertion constraints; three I.2.c-pinning modules are in its file set for follow-only edits |
| Region L rewording for FR7 drops a phrase that `tests/test_prelaunch_inprogress_launch_order.py` pins | Medium | Medium | task0003 lists the pinned phrases; that module must pass unmodified |
| The new schema section lands inside a span that an existing schema doc-contract test compares byte for byte | Low | Medium | task0006 names the forbidden spans and a safe position |
| Existing `queue_stop_guard` tests that expect exit 2 on `pending` + `failed` silently flip to exit 0 | High (expected) | Low | task0005 adds a matching record to exactly those fixtures and keeps their expectations |

## Open Questions

- None.
