# Threat Model: sca-file-tasks-unexpected-exceptions

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR6, NFR1-NFR5) at the `reduced` tier, together with
the current `file-tasks` code path in `em-workflow/scripts/scan-dependencies.py`
(grouping, the two filing helpers, the shared entry-point runner, the
temporary references-file writer, the filing loop and the CLI's stdout
summary). The single task declares `input-handling`, `external-io` and
`api-contract`; the first two set a deep analysis depth for the boundaries
where finding text and task-system output enter the script.

Three boundaries carry data this feature changes the handling of: finding
text from the scanner output, task ids from the external task system's
listing, and the summary the orchestrator reads back. The threats are
availability of the whole batch run (a single crafted character ends the
process without a summary) and untrusted text reaching summary fields that
the orchestrator treats as fixed machine tokens. No authentication,
authorization or persistence surface is touched; argument passing to the
entry point stays a list-form launch with no shell, unchanged by this
feature, so no injection row is recorded for it.

Domain consistency check: task0001 declares `input-handling` and
`external-io`; its implementation file `em-workflow/scripts/scan-dependencies.py`
is the boundary file of every boundary below. Its other file, the new test
module, implements no boundary.

## Trust Boundaries

### TB-1: Finding text into grouping, the temporary references file and the entry-point launch
Crossing: package, advisory id and severity recovered from the findings file
(scanner output carrying advisory-database text, outside the project's
control) flow into `file-tasks` grouping, the temporary references file, the
entry-point process arguments, the report file and the stdout summary.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A finding whose package, advisory id or string severity cannot be encoded as UTF-8 (a lone surrogate) raises an encoding error during truncation, the temporary-file write, the report write or the stdout serialization; the process ends with a traceback, prints no summary, and the record of packages already filed in the batch is lost (FR4, NFR1). | TM-1 | Grouping checks UTF-8 encodability of the three fields before truncation, skips a failing finding and records it in `malformed_findings` with a new fixed reason; every other finding is processed on all three branches, and no unencodable text reaches the report, the summary or stdout. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | A package name containing NUL makes the entry-point launch raise ValueError, which escapes the filing loop; the process ends with a traceback and no summary (FR1, FR2, FR5). The same holds for any OSError or ValueError raised while writing the temporary references file. | TM-2 | Both filing helpers convert OSError and ValueError (including UnicodeEncodeError) raised while writing the temporary file or launching the entry point into EntryPointError with the original exception kept as the cause; the filing loop ends through the existing break-and-return route and the CLI prints exactly one JSON summary with exit code 0. | task0001 AC-1, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification: TM-2 |

### TB-2: Task-system listing output into the update launch
Crossing: task ids returned on stdout by the external task-system entry
point (another process) are passed back as an argument of the update
launch.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (external-io, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A listed task id containing NUL (or an unencodable character) makes the update launch raise ValueError, which escapes the filing loop on the append path; the process ends with a traceback and no summary (FR1, FR2). | TM-3 | The append helper converts the ValueError into EntryPointError with the original kept as the cause; the loop ends through break-and-return with `failure_reason` `task_update_failed`, the failed package and every later package listed in `unattempted_packages`. | task0001 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification: TM-3 |

### TB-3: The file-tasks summary into the orchestrator's context
Crossing: the stdout JSON summary (and stderr text) of `file-tasks` is read
by the orchestrator agent, so summary field values are interpolated into an
LLM's context.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Exception text from the newly converted ValueError / UnicodeEncodeError, or package- / advisory-sourced text, ends up in `failure_reason` or `malformed_findings[].reason`, fields the orchestrator treats as fixed machine tokens, letting crafted finding content steer the orchestrator (NFR1, FR4). | TM-4 | `failure_reason` stays one of `task_create_failed` / `task_update_failed`; the new malformed reason is a fixed module constant never built from finding content; exception text goes to stderr only; the summary keeps exactly twelve keys. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification: TM-4 |
