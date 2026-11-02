# Threat Model: scenario-id-ts-hyphen

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR5, NFR1-NFR3, assumptions
A1-A7), at the `full` tier, against the four planned tasks. task0002, task0003
and task0004 edit agent prompts, a template, contracts, a skill and a phase
document. These are plugin files read as trusted instructions, and the edits
add no path along which data crosses between parties at run time, so they
introduce no trust boundary. task0001 (domain `input-handling`, analysed at
deep depth) makes `em-workflow/scripts/validate-worker-output.py` open and
scan files that the implementation-planner worker wrote and named in its
workflow patch. That worker's output is shaped by untrusted input (the
Untrusted-Input Handling section of
`em-workflow/references/contracts/worker-envelope.md`), and the orchestrator
relies on the validator's verdict. This is the one boundary, TB-1. The
existing task-plan checks already guard their own reads of `plan` paths. The
new check adds reads of its own: the plans again and, for implementation-planner
results, VERIFICATION.md. The threats below concern only these new reads.
Spoofing, Repudiation and Elevation of privilege do not realistically apply:
the validator holds no identity, keeps no audit record, and runs with the
orchestrator's own privileges. Tampering does not apply either: the check only
reads files and never writes.

## Trust Boundaries

### TB-1: implementation-planner output -> validator scenario-ID form check
Crossing: the `tasks_patch.entries[].plan` path strings from the
implementation-planner's workflow patch, and the contents and file state of
the VERIFICATION.md and task plans that the worker wrote into the feature
directory, cross from the worker (LLM output, untrusted) into the validator,
a deterministic gate the orchestrator relies on.
Boundary files: em-workflow/scripts/validate-worker-output.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A worker-supplied `plan` value (absolute, containing `..`, or passing through a symlink) or a symlinked VERIFICATION.md makes the new check (FR3) open a file outside the feature directory and echo IDs taken from it into the validator's output | TM-1 | The check reads a plan only after it passes the existing plan-path safety, symlink, containment, regular-file and size checks, and leaves a failing plan to those checks' errors. It reads VERIFICATION.md only when it is a regular, non-symlink file; otherwise it reports a `scenario-id-form` error without scanning the content | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Denial of service | An oversized, non-regular or non-UTF-8 VERIFICATION.md makes the new check (FR3) exhaust memory or raise, so the validator returns no verdict, or the file is skipped and its hyphen-less IDs pass unchecked | TM-2 | The VERIFICATION.md read is bounded by the existing plan-read byte limit. A file that is too large, not a regular file, or not UTF-8 yields a `scenario-id-form` error instead of an exception or a silent skip | task0001 AC-6 | VERIFICATION.md, Performance / Security Verification, TM-2 |
