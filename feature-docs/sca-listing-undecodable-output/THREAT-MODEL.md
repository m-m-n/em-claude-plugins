# Threat Model: sca-listing-undecodable-output

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR8, NFR1-NFR6, Security Considerations) at the
reduced tier (no REQUIREMENTS.md, no DESIGN.md). The feature changes how
`file-tasks` receives and classifies the output of the `task list` process it
launches through the `--entry-point` program. That output is produced by
another process and originates in an external task system, so it crosses a
trust boundary (TB-1). task0001 declares `input-handling` and `external-io`,
which set the depth of TB-1 to deep; its third domain, `api-contract`, does
not change the depth.

Two STRIDE categories realistically apply at TB-1: Denial of service
(malformed bytes abort the run before any summary is printed, which is the
reported defect itself) and Information disclosure (listing content or
decode-error text being carried into the summary and report that the
orchestrator reads). Spoofing of the entry point and tampering with a listing
that does decode are handled by the existing checks whose names and
conditions this feature keeps unchanged (`entry_point_invalid`,
`listing_output_not_json`, `listing_output_not_array`; NFR2); the feature does
not alter them, so they get no row. The `task create` / `task update`
invocation is outside the change range (NFR1) and is not analyzed here.

## Trust Boundaries

### TB-1: task-listing process output into file-tasks
Crossing: the stdout and stderr bytes and the exit code of the
`task list --type セキュリティ --format json` process (another process,
launched through the user-supplied `--entry-point`, whose content comes from
an external task system) flow into `list_security_tasks`; its result selects
the `file_tasks` branch and the content of the JSON summary and report.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | Bytes on stdout of a successful (exit 0) listing that are not valid UTF-8 raise a decode error that escapes `list_security_tasks` and aborts file-tasks with no JSON summary and no report (FR3, FR5, FR8) | TM-1 | Listing output is captured as bytes; after the exit-code check, stdout alone is decoded as strict UTF-8 and a decode failure becomes the unavailable outcome `listing_output_undecodable`, which takes the existing degraded report branch and ends with exit code 0 | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification item TM-1 (TS-1, TS-2, TS-5) |
| Denial of service | Bytes on stderr that are not valid UTF-8 abort file-tasks, or disable filing, even though the listing itself succeeded with a valid stdout (FR4) | TM-2 | stderr is never decoded; availability is decided from the exit code and stdout only | task0001 AC-4 | VERIFICATION.md Performance / Security Verification item TM-2 (TS-4) |
| Information disclosure | Fragments of the listing output, or the decode error's message (which quotes the offending bytes and their position), are copied into the summary's `degraded_reason` or into the report file read by the orchestrator (NFR3) | TM-3 | `degraded_reason` carries only the fixed token; neither the summary nor the report contains listing output or decode-error text | task0001 AC-1 | VERIFICATION.md Performance / Security Verification item TM-3 (TS-9) |
