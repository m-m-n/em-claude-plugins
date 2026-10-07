# Threat Model: task-status-key-exact-match

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier reduced: no REQUIREMENTS.md, design step skipped) and
the per-task status read in `em-workflow/hooks/queue_stop_guard.py` that the
feature changes. The feature changes one rule: which direct-child line of a
task block counts as the status key line (FR1). The Stop hook reads
workflow.yaml, whose task `notes` values carry free text that reached the file
from outside the orchestrator; that text crosses into the hook's Stop
decision, so one trust boundary exists (TB-1). task0001 declares
`input-handling`, which sets TB-1's depth to deep. The fix makes the reader
keep reading after a direct-child line it no longer treats as a key, and that
continuation is where a status-shaped line outside the direct keys could be
picked up; one Tampering threat applies there.

The hook's other inputs, the Stop-hook JSON on stdin and the queue journal,
are read exactly as before; the feature changes nothing on those paths, so
they add no boundary to this analysis. No Denial of service row is recorded:
the changed recognition adds no unbounded matching, and the reader's
no-raise, fail-open behavior (NFR2) is unchanged.

## Trust Boundaries

### TB-1: workflow.yaml task blocks into the Stop hook's status read
Crossing: workflow.yaml text, including each task's `notes` value (free text
from outside the orchestrator, written as a block scalar), read line by line
by the Stop hook process; the per-task status it yields decides whether the
hook blocks the Stop event.
Boundary files: em-workflow/hooks/queue_stop_guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Once the reader continues past a direct-child line that is no longer a status key line (FR1), a status-shaped line inside a task's notes block-scalar body or a nested mapping is taken as the task's status, contrary to the read scope FR2 keeps: a body `status: pending` makes the hook block Stop for a task that is not pending, and a body non-pending value masks a direct `status: pending` that follows it. | TM-1 | The exact key-name check applies only to lines that already passed the direct-child indentation filter, and skipping a non-key line leaves the direct-indent state and the multi-line value tracking untouched, so block-scalar body, nested-mapping and comment lines remain non-candidates whatever precedes them. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-8, TS-9) |
