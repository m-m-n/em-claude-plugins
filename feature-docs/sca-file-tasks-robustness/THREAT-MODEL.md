# Threat Model: sca-file-tasks-robustness

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1–FR6, NFR1–NFR6, Security Considerations), REQUIREMENTS.md, and the four tasks' file sets; tier `full`. Depth is deep on every boundary: task0001 and task0004 declare `input-handling`, task0002 and task0004 declare `external-io`, task0003 declares `data-persistence`. Each of these tasks has at least one file on a `Boundary files` line below: `em-workflow/scripts/scan-dependencies.py` (TB-1, TB-2, TB-3), and `em-workflow/references/review-phase.md` and `em-workflow/references/batch-mode.md` (TB-2, where the summary is persisted into the committed round record and the batch final report is assembled from that record). Test modules carry no boundary of their own.

Three boundaries carry untrusted data into this feature's code, and at least one STRIDE category realistically applies to each. Categories without a row were considered and have no realistic path in this change: at TB-1, recovery reads the package and advisory id before the short title and the collapse touches only the short title, so no new way to forge a package / advisory pair arises (Spoofing); at TB-2, which program is launched is unchanged — only how its launch failure is handled changes (Elevation of privilege); at TB-3, path verification and binding keep their existing confinement rules, so only the reordering risk below is new.

## Trust Boundaries

### TB-1: Advisory text from scanner output into finding titles and triage filing
Crossing: advisory short titles in the scanner tools' output (text authored by third-party advisory databases) into the finding title, which the file-tasks subcommand parses back into (package, advisory id) to decide whether the finding becomes a task or a report entry.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A short title containing a line break makes the finding title unrecoverable, so the finding is classified malformed and never becomes a task or a report entry: a real vulnerability silently leaves triage (FR1, FR2) | TM-1 | Collapse every whitespace run of the short title to one space and strip its ends at the single title-assembly point, before truncation, for all four normalizers; a round-trip test over all four normalizers pins recovery, grouping and filing | task0001 AC-1, AC-2, AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 |

### TB-2: Entry-point process and OS into the file-tasks summary, the committed round record and the batch final report
Crossing: file-tasks launches the caller-supplied task-system entry point (another process) and writes a temporary references file; launch and write failures arrive as OS errors carrying OS-supplied text (local paths). The resulting summary is persisted by the orchestrator into the committed round record `reviews/roundN.yaml`, which humans and agents read later, and from which a batch run's final report — relayed by an external service to the human evaluator — is assembled through batch-mode.md's audit-item source map.
Boundary files: em-workflow/scripts/scan-dependencies.py, em-workflow/references/review-phase.md, em-workflow/references/batch-mode.md
Depth: deep (external-io, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | An OS error from launching the entry point or writing the temporary file escapes file-tasks and the CLI; the process dies with a traceback and no JSON, and every package already filed in that batch goes unrecorded (FR3) | TM-2 | Both filing helpers turn every OS error into the existing entry-point failure, which the existing break-and-return path handles; the CLI prints exactly one JSON object and exits 0 | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Repudiation | A partial filing failure is recorded in the committed round record exactly like full success, and packages never attempted leave no trace (FR4, FR5) | TM-3 | The summary carries `unattempted_packages` on every branch; the receipt records `failed_package`, `failure_reason`, `malformed_findings`, `listing_dropped_count` and `unattempted_packages` in all three of its definitions; a non-empty list is reported as "triage filing incomplete" in R6 and in the batch final result, the latter through one batch-mode.md Reporting item and source-map row pointing at the receipt | task0002 AC-4, AC-5; task0003 AC-1, AC-2, AC-3, AC-6, AC-8 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Information disclosure | OS-error text (local filesystem paths) or advisory-sourced text reaches `failure_reason`, a malformed reason, `unattempted_packages` or the receipt, and from there the committed (and pushed) round record, the agents that read it and the batch final report (NFR2) | TM-4 | `failure_reason` and the malformed reason stay fixed tokens; `unattempted_packages` holds only the canonical package names `filed_packages` already uses; OS-error text goes to stderr only; the receipt copies summary values and nothing else; the batch final report's source for this item is the receipt alone | task0002 AC-6; task0003 AC-4, AC-8 | VERIFICATION.md Performance / Security Verification, TM-4 |

### TB-3: Changed-file paths and the reviewed tree's layout into scan planning and launch
Crossing: changed-file paths from the reviewed diff and the reviewed tree's on-disk layout (symlinks, aliases, `..` spellings) — attacker-influenceable when an untrusted branch is reviewed — into build_scan_jobs' real-path grouping and target selection, then into the run side's binding check, isolation directory and scanner launch.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Planning every ecosystem before the first launch widens the window between real-path grouping and launch; if the run side trusted the plan instead of re-running its binding check, prepared the isolation directory before that check, or re-selected a different target than the one checked, a symlink swapped in after planning would send a scanner outside its verified project directory or onto the reviewed tree's own scanner configuration (FR6, NFR1) | TM-5 | The run side keeps the per-group binding check immediately before isolation and launch, in the current order, against the plan's own target; the isolation directory is prepared only after that check passes; the plan never substitutes for the check; an ecosystem failing validation or resolution gets no path verification at all | task0004 AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |
