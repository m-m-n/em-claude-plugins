# Threat Model: first-entry-timestamp-scan

## Verdict
no-trust-boundary

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR3, NFR1-NFR4) at tier `full`,
and the single planned task, task0001 (domain `input-handling`). The
feature's whole change set is additional `unittest` cases in
`tests/test_recover_orphaned_task.py`. Every input those tests read is a
fixture the test itself writes under a temporary directory; the child
process they start is the repository's own
`em-workflow/scripts/recover-orphaned-task.py` (and, through its default
wiring, the repository's own `journal-append-failed.py`), run by the same
user with the same privileges and fed only those fixtures. The transcripts
directory is always an injected temporary directory (NFR1), so no file from
outside the project is read or written. The production script whose
transcript reading does cross a boundary in operation is not changed by this
feature (FR3), so no crossing is added or altered.

Domain consistency: task0001 declares `input-handling` because its subject is
the transcript input shapes the script parses. Its only file is a test
module that reads nothing it did not write itself, so it sits on no trust
boundary and no `Boundary files` line applies to it.
