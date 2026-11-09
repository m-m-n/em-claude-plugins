# Threat Model: verification-md-regular-file-read

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR4, NFR1-NFR3, assumptions A1-A4) at the reduced
tier: there is no REQUIREMENTS.md and the design step was skipped. The
feature changes how `em-workflow/scripts/validate-worker-output.py` reads
`VERIFICATION.md` from the `--feature-dir` and `--baseline-dir` directories
while it validates rework-planner output. The validator does not control the
kind or the content of those files: the feature-dir copy is worker-written,
and the baseline-dir copy is whatever the baseline holds. That read is the
one trust boundary (TB-1). The single task, task0001, declares
`input-handling` and `external-io`, so TB-1 is analysed at deep depth.

task0001 also modifies `tests/test_rework_docs_only_validator_rules.py`.
That file implements no boundary and is therefore not listed under Boundary
files.

Spoofing, Repudiation, Information disclosure and Elevation of privilege do
not realistically apply at TB-1. The validator only derives a scenario-ID
set from the file and reports errors naming the file's path back to the same
caller. No identity, audit record, secret content or privilege crosses the
boundary.

## Trust Boundaries

### TB-1: VERIFICATION.md read by the rework-planner output validator
Crossing: the file kind and the bytes of `{feature-dir}/VERIFICATION.md` and
`{baseline-dir}/VERIFICATION.md`, both outside the validator's control, enter
the validator process whose result gates the unattended run
Boundary files: `em-workflow/scripts/validate-worker-output.py`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A VERIFICATION.md that is a FIFO, a device file, or a symlink to one (for example to /dev/zero) makes opening or reading it block, or never reach end of file. Validation then never returns and the unattended run stops (FR1, FR3, A1). | TM-1 | The path is classified without following a symlink, opened without following a symlink and without blocking, and the opened descriptor is confirmed to be a regular file before any byte is read. A symlink, a directory, a FIFO, a device file and any stat or open failure give the unreadable state with a reason, and the loader never raises. The existing rework-index error reports the needed unreadable file, and the CLI ends with exit 1. | task0001 AC-1, AC-4, AC-5, AC-6 | VERIFICATION.md, Performance / Security Verification, item TM-1 |
| Denial of service | A very large regular VERIFICATION.md is read into memory in full and exhausts it (FR2). | TM-2 | At most the byte limit plus one byte is read. A file over the limit gives the unreadable state and is never loaded in full, and only a file within the limit is decoded as UTF-8. | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, item TM-2 |
