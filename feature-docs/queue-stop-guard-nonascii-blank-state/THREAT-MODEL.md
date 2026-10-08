# Threat Model: queue-stop-guard-nonascii-blank-state

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR6, NFR1-NFR4, Security Considerations) at the
reduced tier (no REQUIREMENTS.md; design step skipped). The feature changes
how the multi-line value tracker in `em-workflow/hooks/queue_stop_guard.py`
reads the lines of `workflow.yaml`. Task `notes` values are free text that
can carry text originating outside the orchestrator (failure reasons taken
from worker output), and the hook's reading of the file decides whether the
Stop hook blocks the session (exit 2) or lets it stop. That crossing is the
single trust boundary TB-1, analysed at deep depth because task0001 declares
`input-handling`.

Tampering and Denial of service apply at TB-1. Spoofing, Repudiation,
Information disclosure and Elevation of privilege do not: the hook only
reads the file and emits a block decision with task IDs; it authenticates
no party, keeps no audit record, exposes no file content beyond task IDs,
and changes no privilege.

Not mitigated by this feature, by SPEC.md's own scope (FR3, A3): at the
value-start position, a column-0 line of only non-ASCII whitespace followed
by `- '…` still opens a quoted value (residual A1 of
routeback-record-quoted-open-residual, pinned by
`TestColumnZeroNonAsciiBlankLine`). The ASCII-visible form of the same
concealment (a non-blank line at the parent indentation followed by a
deeper `- '…`) is outside this feature and unchanged.

Domain consistency: task0001 declares `input-handling`; its file
`em-workflow/hooks/queue_stop_guard.py` is TB-1's boundary file. Its other
file, `tests/test_queue_stop_guard_routeback_record.py`, is test code and
crosses no trust boundary.

## Trust Boundaries

### TB-1: workflow.yaml task text read by the Stop hook
Crossing: text of `workflow.yaml` task entries, in particular free-text
`notes` values that can carry worker- or review-originated text, read by the
Stop hook process, whose reading decides whether the session is blocked from
stopping.
Boundary files: `em-workflow/hooks/queue_stop_guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A `notes` value whose block scalar (FR1) or plain-scalar continuation (FR2) contains a line made only of non-ASCII whitespace at or below the parent indentation ends the tracker's state, so a following `- '…` line opens a quoted value that swallows the genuine `routeback_failed_journal_line` record and every later task; the Stop hook exits 0 where it should exit 2 (SPEC.md Security Considerations) | TM-1 | In the block-scalar and plain-continuation states, a line that is blank under Unicode whitespace but not made only of spaces and tabs neither continues nor ends the state at any indentation; the tracker state is left unchanged and the next line is judged against it, so the `- '…` line stays inside the value | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-3, TS-5) |
| Denial of service | A line in the new forms, or a value left unclosed until end of file, makes the tracker or a reader function raise, so the hook ends without reaching its block decision (NFR2) | TM-2 | The tracker and the three reader functions return without raising for any line content, including the new forms and values unclosed at end of file | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-4) |
