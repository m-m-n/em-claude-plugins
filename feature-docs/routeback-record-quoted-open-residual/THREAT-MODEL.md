# Threat Model: routeback-record-quoted-open-residual

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1–FR4, NFR1–NFR4, Security Considerations > Input
Validation) at tier `reduced` (REQUIREMENTS.md and DESIGN.md are absent by
tier). The single task, task0001, declares the domain `input-handling`,
which sets TB-1 to deep depth.

The feature changes how the Stop hook's line reader interprets `workflow.yaml`
text the hook does not control. A misread hides a genuine
`routeback_failed_journal_line` record and every later task block, so the
hook exits 0 where it must exit 2. Two such misreads (FR1, FR2) are
realistic tampering paths at an existing boundary, so the verdict is
`threats-identified`. The feature adds no new input source, network access
or dependency (NFR1), so no new boundary is introduced. The test file
`tests/test_queue_stop_guard_routeback_record.py` carries no boundary.

The `TM-n` identifiers below are local to this document. The "TM-2" named in
SPEC.md's Overview refers to an earlier feature's threat model, not to TM-2
here.

Residual (scoped out by SPEC.md, no mitigation recorded here): SPEC.md's
Edge Cases keep a column-0 line made only of U+3000 or U+00A0, followed by a
`- '…` line, opening as before (assumption A1).

## Trust Boundaries

### TB-1: workflow.yaml text into the Stop hook's line reader
Crossing: the text of the feature's `workflow.yaml` — in particular
free-form task `notes` values, whose content the hook does not control —
read by the Stop hook process through `_MultilineValueTracker` and the
readers that use it (`task_ids_from_workflow`, `iter_task_block_lines`,
`task_routeback_records_from_workflow`) to decide whether to block the stop.
Boundary files: `em-workflow/hooks/queue_stop_guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A `notes` value inside a flow collection with a `?` in the middle of a plain scalar, followed by a space and a quote (FR1; SPEC.md Security Considerations, Input Validation), makes the tracker open an inner string; every later line, including the genuine route-back record and later task blocks, is read as value body and the hook exits 0 instead of 2. | TM-1 | A `?` is the flow mapping-key indicator only at a flow-entry start and only when followed by a space, a tab or the end of the line; any other `?` is an ordinary character that clears the entry-start and after-close state, so a quote after it opens no inner string on the same or a later line (FR1). | task0001 AC-1 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Tampering | A line inside a `notes` value made only of non-ASCII whitespace (e.g. U+3000, U+00A0) is read as blank, leaving the tracker waiting for a value so the next line's quote or bracket opens a value; later records and task blocks are hidden and the hook exits 0 (FR2; SPEC.md Security Considerations, Input Validation). | TM-2 | The tracker's blank-line rule, in both the line reader and the block-scalar branch, accepts only lines of spaces and tabs; any other whitespace-only line is read by the normal rules (FR2). | task0001 AC-2 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Denial of service | Line content reaching the changed tracker paths, including a value left unclosed to end of file, raises an exception in the tracker or a reader, breaking the fail-open contract so the guard cannot complete its decision (NFR2). | TM-3 | The tracker and every reader return normally for any line content, including the new fixtures and values left unclosed to end of file (NFR2). | task0001 AC-6 | VERIFICATION.md Performance / Security Verification: TM-3 |
