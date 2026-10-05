# Threat Model: prelaunch-inprogress-routeback

## Verdict
threats-identified

## Rationale

**What was inspected.** SPEC.md and REQUIREMENTS.md (FR1–FR13, NFR1–NFR5),
at tier `full`. task0001 and task0002 (FR1–FR6) are merged and unchanged.
This pass covers what FR7–FR13 add: a new workflow.yaml record that grants
an automatic relaunch of a `failed` task, the readers that trust it, and
the worker-patch path that could forge it.

**Domains that set the depth.**

- `data-persistence` (task0003, task0004, task0006);
- `input-handling` (task0004, task0005, task0006);
- `external-io` (task0005).

**Why the record matters.** The record decides whether a `pending` +
`failed` task is relaunched without I.2.c's user decision. In batch mode,
that decision is the `implement.failed-task` policy. A forged or
misread record therefore bypasses an approval step. That is why both
boundaries below are analysed in depth.

**FR1–FR6 surface.** This surface stays as the previous model recorded it.
The launch-state commit reads `journal.jsonl` under the same last-event
interpretation it already used. It adds no new input, writer, command or
privilege.

**Domain re-check.** Every task that declares one of the four depth
domains has at least one file on a `Boundary files` line:

- task0003 and task0004 edit `em-workflow/references/implement-phase.md`
  (TB-2);
- task0005 edits `em-workflow/hooks/queue_stop_guard.py` (TB-2);
- task0006 edits `em-workflow/scripts/validate-worker-output.py`,
  `em-workflow/references/workflow-patch.md` and
  `em-workflow/references/workflow-schema.md` (TB-1).

task0003 declares `data-persistence` because it changes which task states
the launch-state commit persists. Its boundary relevance is that it closes
the window in which a launched-then-failed task would otherwise persist as
`pending`. That closure is part of TM-2's design context.

## Trust Boundaries

### TB-1: Worker workflow patch to workflow.yaml task records

**Crossing.** Two LLM workers produce `tasks_patch.entries`:
implementation-planner (`replace_all`) and rework-planner (`append`). Both
workers' inputs include untrusted text. The orchestrator validates those
entries with `validate-worker-output.py` and applies them to workflow.yaml,
the orchestrator-owned state file.

**Boundary files:**

- `em-workflow/scripts/validate-worker-output.py`
- `em-workflow/references/workflow-patch.md`
- `em-workflow/references/workflow-schema.md`

**Depth:** deep (input-handling, data-persistence).

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A worker patch sets `tasks.{T}.routeback_failed_journal_line` on a task entry. The record's only legitimate writer is the orchestrator's route-back write set (FR11). A worker-set record would forge the orchestrator-only reset authorization that lets a `failed` task relaunch without I.2.c's decision (FR8, FR13). | TM-1 | Task-entry validation rejects any `tasks_patch.entries` entry carrying the key, under both `replace_all` and `append`, null included (FR13). The schema names the orchestrator as the sole writer. Carried ids are copied only from the orchestrator's own workflow.yaml (FR12). The `preserve` vocabulary is not widened. | task0006 AC-2, AC-5 | VERIFICATION.md TS14, TS12, Security item TM-1 |

### TB-2: Journal and the workflow.yaml record to the automatic-relaunch decision

**Crossing.**

- `journal.jsonl` is written by other processes: the queue hooks,
  `merge-task.sh` run inside implementer worktrees, and
  `journal-append-failed.py`.
- workflow.yaml's `routeback_failed_journal_line` is read by the Stop hook
  process (`queue_stop_guard.py`) and by the orchestrator (I.2.a selection,
  I.2.b step 1).
- Together they decide whether a `pending` + `failed` task is relaunched
  automatically or routed to I.2.c's user decision.

**Boundary files:**

- `em-workflow/hooks/queue_stop_guard.py`
- `em-workflow/references/implement-phase.md`

**Depth:** deep (input-handling, data-persistence, external-io).

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A `pending` + `failed` task is reclassified as unlaunched, and relaunched without I.2.c's decision, on a record that does not identify that failure as the one route-back reset (FR5, FR8, FR9, FR10). The record may be absent or null. It may be malformed: zero, negative, non-integer, quoted, empty or leading-zero. It may sit in another task's block or on a step-level line. It may name an older line, after a relaunch that failed again or after a failure that never reached the launch-state commit. | TM-2 | The carve-out applies only when all three conditions hold: status `pending`, journal last event `failed`, and that event's physical line equal to the task's own record. Anything else is `failed`. The orchestrator routes it to I.2.c's failure handling, and the Stop hook does not block (exit 0). The hook reads the record only from the task's own block and accepts only the canonical form (FR9, A3). Nothing clears the record, so a re-failure on a new line stops matching (FR8). | task0004 AC-1, AC-2; task0005 AC-1, AC-2 | VERIFICATION.md TS9, TS10, Security item TM-2 |
| Tampering | The hook and the orchestrator count journal lines differently, so a record matches for one classifier but not the other. Possible causes: lines that are blank, malformed, carry an unknown event or an invalid task id; a stray CR; a final line without LF. The result is an unintended relaunch, or a hook BLOCK that the orchestrator would not honour (FR9, FR11, A1). | TM-3 | A single counting rule is defined once in `workflow-schema.md` and applied by both classifiers (FR11). Lines are delimited by LF only, and every physical line counts, including blank, malformed, unknown-event and invalid-task lines. The journal is append-only, so a recorded line never changes (A5). | task0005 AC-3; task0006 AC-1 | VERIFICATION.md TS10 (f), TS12, Security item TM-3 |
