# Threat Model: routeback-record-direct-key

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier `reduced`: no REQUIREMENTS.md, no DESIGN.md) and the
input of `em-workflow/hooks/queue_stop_guard.py` whose reading this feature
changes: the task blocks of `workflow.yaml`. Within a task block,
`tasks.{T}.notes` is written by the orchestrator at Step I.2.c from the
implementer's report and so carries untrusted text, while
`routeback_failed_journal_line` is an orchestrator-only record
(`em-workflow/references/workflow-schema.md`). The hook's exit code (0 or 2)
depends on that record, so text reaching the record read from `notes` crosses
a trust boundary. task0001 declares `input-handling`, so the boundary is
analyzed at deep depth.

The journal file and the Stop-hook stdin JSON are also read by the hook, but
this feature does not change how they are read and adds no crossing for them.
The per-task status read is outside the change set (SPEC A2) and was not
re-analyzed here. The test file of task0001 only builds fixtures and runs the
hook, so it is not a boundary file.

The mitigation relies on `notes` being serialized as valid YAML, where block
scalar bodies and scalar continuation lines are indented deeper than the key
that owns them (SPEC A1).

## Trust Boundaries

### TB-1: Untrusted notes text vs. the orchestrator-only route-back record
Crossing: text derived from implementer reports, stored by the orchestrator
in `tasks.{T}.notes` of `workflow.yaml` (as a block scalar or a multi-line
quoted scalar), reaches the Stop hook's line-based record read. That read
decides whether a `pending` task whose last journal event is `failed` is
classified as unlaunched (exit 2, relaunch demanded) or as failed (exit 0).
Boundary files: `em-workflow/hooks/queue_stop_guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A record-shaped line inside the notes body, or nested under another key, is taken as the route-back record (FR1, FR4): (a) a value equal to the `failed` event's line forges a record, so a task with no record or a non-matching record is classified unlaunched and the hook demands a relaunch that bypasses the Step I.2.c decision; (b) because `notes` precedes the record in the schema key order, a non-matching value shadows a matching real record, so the hook exits 0 where it must block. | TM-1 | The record is read only from lines at the direct-child indentation of the task's own mapping; deeper-indented lines (block scalar bodies of every indicator form, scalar continuation lines, nested mapping or sequence keys) are never read as a record, so notes content can neither create nor shadow it (FR1, FR2). | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification item TM-1 (TS-1 to TS-6) |
