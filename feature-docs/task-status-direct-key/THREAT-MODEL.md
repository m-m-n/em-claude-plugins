# Threat Model: task-status-direct-key

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR5, assumptions A1-A5) and the workflow.yaml `goal` block; tier `reduced`; the single task declares the `input-handling` domain, which sets TB-1 to deep depth.

The feature changes how `em-workflow/hooks/queue_stop_guard.py` reads each task's status from workflow.yaml. One trust boundary is crossed: `tasks.{T}.notes` holds text written from implementer reports and is attacker-influenceable (SPEC.md Overview), while the status read from the same task block decides whether the Stop hook blocks and which tasks it names for launch. The hook's other inputs are not new crossings: the journal is machine-written by the plugin's own hooks and scripts and is only read here, the route-back record and the direct keys are orchestrator-written, and this feature changes neither of their readers (NFR5).

Residual risk not mitigated by this feature: continuation lines of multi-line quoted scalars that sit at the direct-child indentation can still be read as a status (SPEC.md A2, Out of Scope). The mitigation below also relies on the writer keeping block-scalar body lines indented deeper than the direct keys; that serialization is outside this feature.

## Trust Boundaries

### TB-1: Untrusted task notes text into the Stop hook status reader
Crossing: free text in `tasks.{T}.notes` (written into workflow.yaml from implementer reports; attacker-influenceable) is read, inside the same task block as the orchestrator-written direct keys, by the Stop hook's status reader, whose result drives the hook's block / launch decision.
Boundary files: em-workflow/hooks/queue_stop_guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A `status:` line inside the block-scalar body of a direct key (the notes field, any literal or folded header form) is taken as the task's status when the direct status key is absent or comes later (FR1, FR2). Crafted notes can make a task look `pending`, so the hook blocks the stop and names the task for launch, or can hide a direct `pending` behind another value, so the hook lets the session stop with work outstanding (FR4). | TM-1 | Only lines at exactly the task block's direct-child indentation (A1) are status candidates; block-scalar body lines and nested-mapping lines are never candidates, and the first direct-child status key decides (A5). | task0001 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification: TM-1 (TS1, TS3, TS5) |
| Denial of service | Crafted notes content or task-block layout makes the changed status reader raise, so the Stop hook ends with a traceback and a non-zero exit instead of failing open (NFR2). | TM-2 | The status reader handles any task-block content without an uncaught exception; content it cannot interpret yields no status for that task, and the hook keeps exit code 0. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-2 |
