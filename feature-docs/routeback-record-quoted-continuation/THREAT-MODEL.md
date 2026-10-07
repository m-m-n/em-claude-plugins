# Threat Model: routeback-record-quoted-continuation

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR7, NFR1-NFR6, Assumptions A1-A8) and the
workflow.yaml readers of `em-workflow/hooks/queue_stop_guard.py` that the
feature changes (task-id enumeration, task-block scan, status read, record
read). Tier: reduced (no REQUIREMENTS.md, no DESIGN.md). The single task
declares `input-handling`, so TB-1 is analysed at deep depth.

One trust boundary exists (TB-1): free text that reaches multi-line quoted
scalars and flow collections of workflow.yaml - chiefly `tasks.{T}.notes`,
which the orchestrator fills with failure reasons taken from implementer
reports - is read by the Stop hook's line-based classifier, whose exit code
decides whether the session may end (exit 0) or must relaunch tasks
(exit 2). Tampering and Denial of service apply. Spoofing, Repudiation,
Information disclosure and Elevation of privilege get no row: the hook
authenticates no party, this change touches no audit record, the hook emits
only task ids and slot counts, and it runs with the session's own
privileges; the effect of a forged record (bypassing the pending user
decision) is recorded under Tampering. The journal reader and the Stop-hook
stdin reader are unchanged by this feature and are not re-analysed.

Accepted residual risks (not mitigated further):
- A quoted or flow value that never closes before end of file hides every
  later line, later tasks included, from the hook; the hook then falls to
  the non-blocking side (NFR2, SPEC A4).
- A value prefixed by an anchor or a tag, or following a quoted key, is not
  recognised as an opening (SPEC A6), so its multi-line body stays readable.

## Trust Boundaries

### TB-1: multi-line quoted / flow values in workflow.yaml -> Stop hook task-block reader
Crossing: free text written into multi-line double-quoted scalars,
single-quoted scalars, flow sequences and flow mappings of workflow.yaml
(notably `tasks.{T}.notes`, written by the orchestrator from implementer
failure reports) crosses into the Stop hook's line-based reader, whose
classification of each task (unlaunched / in flight / failed) decides
exit 0 or exit 2.
Boundary files: em-workflow/hooks/queue_stop_guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Forgery: a record-, status- or task-key-shaped line inside the body of such a value is read as a task's `routeback_failed_journal_line` record, its status, or a task boundary / task id (another task's included), so a genuinely failed task is classified unlaunched or a non-existent task is listed, and the hook exits 2 demanding a relaunch past the pending user decision (FR1, FR2, FR3; SPEC AC2, AC5) | TM-1 | The task-id enumeration and the task-block scan track the opening and closing of quoted scalars and flow collections from the first line of the file, with the FR3 escape and nesting rules, and never use a body line as a section start, section end, task key, block end or yielded block line, whatever its indentation; the status and record reads consume only the scan's output | task0001 AC-2 (also AC-4, AC-5) | VERIFICATION.md Performance / Security Verification item TM-1 (TS-2, TS-4, TS-6) |
| Denial of service | Hiding: a non-matching record-shaped body line ahead of the genuine direct-key record shadows it (first occurrence wins), a body line at column 0 ends the `tasks:` section early, or a quote / bracket that is not at a value-start position (block scalar body, comment line, plain scalar, escaped quote, comment after a same-line close) is taken as an opening and swallows the genuine lines after it; the refill the hook should demand is suppressed (exit 0) (FR1, FR3, FR4, FR5; SPEC AC3, AC6, AC7) | TM-2 | Body lines are dropped from the scan without ending any block or section; only a quote or bracket at a value-start position opens (FR4); escapes and same-line closes are honoured (FR3); a value that closes on its own line leaves every following line read as before (FR5) | task0001 AC-3 (also AC-4, AC-5) | VERIFICATION.md Performance / Security Verification item TM-2 (TS-3, TS-5, TS-6) |
| Denial of service | Crash: an unterminated quote or bracket (up to end of file) or undecodable bytes make the new open/close tracking raise; the hook's catch-all then ends with exit 0 without evaluating the remaining active features, disabling the net for them (NFR2) | TM-3 | The tracking never raises on any line content: an opening that never closes marks every remaining line as body (no record, no block), and undecodable bytes are read as replacement characters (NFR2) | task0001 AC-6 | VERIFICATION.md Performance / Security Verification item TM-3 (TS-8, TS-7) |
