# Threat Model: routeback-record-key-exact-match

## Verdict
no-applicable-threat

## Rationale
Inspected: SPEC.md (FR1 to FR3, NFR1, NFR2, assumptions A-1 to A-4), the route-back
record read in `em-workflow/hooks/queue_stop_guard.py`, and its test module
`tests/test_queue_stop_guard_routeback_record.py`. The tier is `reduced`. The
single task, task0001, declares `input-handling`, so the analysis was done at
standard depth.

One trust boundary exists. The Stop hook reads workflow.yaml line by line,
and part of that file's text (for example a task's `notes`) can come from
outside the orchestrator. No STRIDE category realistically applies to what
this feature changes:

- The change only narrows which direct-child lines count as the record key
  (FR1, FR2). Fewer lines are recognised, and no line is newly recognised.
- Text that can carry outside content (body lines of multi-line values,
  block scalar bodies, nested lines) is excluded before key recognition, by
  rules this feature leaves unchanged (A-1).
- After the change, a line can become the record only if it is an exact-key
  line at a task's direct-child indentation. Only the writer of workflow.yaml's
  direct keys can place such a line, and that writer can already write the
  record itself. No new Tampering or Spoofing path appears.
- The only behavioural change is that a genuine record behind a non-key line
  is now read. The hook then blocks in the intended route-back case, under the
  existing three-condition match. No new blocking condition appears, so no
  Denial of service applies.

Domain consistency: task0001 declares `input-handling`, yet its file
`em-workflow/hooks/queue_stop_guard.py` appears in no `Boundary files` line.
That is because the short form has no Trust Boundaries section. The boundary
described above was inspected and has no applicable STRIDE category.
