# Threat Model: file-tasks-temp-unlink-oserror

## Verdict
no-applicable-threat

## Rationale
Inspected: SPEC.md (FR1-FR7, NFR1-NFR4, A-1 to A-7) at the reduced tier
(no REQUIREMENTS.md, design step skipped). The change is confined to how
`_run_entry_point_with_references` in `em-workflow/scripts/scan-dependencies.py`
treats an OS error raised while deleting the temporary references file the
process created itself, plus the docstrings and tests that describe it.
Analysis depth: standard, deepened for `external-io` (task0001 declares it
for the file-system side effect of the deletion).

Two existing trust boundaries sit next to the change: the launch of the
external filing entry point (another process), and the shared temporary
directory that holds the references file. The change alters neither: the
entry point's invocation, inputs and exit-status handling stay as they are
(FR3, FR4), and the references file's creation and its write-failure
cleanup stay as they are (A-3).

No STRIDE category realistically applies to what does change:

- A references file left behind after a failed deletion (A-2) is already
  left behind by the current code. Its readability is fixed when it is
  created, which this feature does not touch, and a party able to read it
  could already read it while the entry point runs. Continuing to later
  packages can leave more than one such file per run, each with the same
  exposure as today.
- The deletion error goes only to the invoking process's stderr (FR2), the
  same party that started the run. Its text comes from the operating system
  and the process's own temporary path, not from external input. Stdout and
  the summary keys stay unchanged (NFR2).
- No new input is parsed, no privilege changes, and no new network or
  process call is introduced.

Domain consistency: task0001 declares `external-io`. Its files
(`em-workflow/scripts/scan-dependencies.py`,
`tests/test_sca_file_tasks_oserror.py`) appear in no `Boundary files` line
because this short form has no Trust Boundaries section; the reasons above
are why no boundary is recorded for them.
