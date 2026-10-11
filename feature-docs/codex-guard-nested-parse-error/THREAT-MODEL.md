# Threat Model: codex-guard-nested-parse-error

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the `full` tier. The feature changes
codex-hook-interactive-guard, which reads the command text of a hook payload
and decides whether to deny an interactive launch. That command text is
written by an agent session whose content can be shaped by untrusted text the
agent has read, so it crosses a trust boundary into the guard's parser. The
guard reads no file, network or subprocess (NFR1) and the feature adds no new
input, so this is the only boundary. Depth is deep because the only task
(task0001) declares `input-handling`; its two guard files are the boundary
files below, and its third file (the test module) only drives the guard.

Both recorded threats are denial of service: the guard exits with no output,
a later interactive launch in the same command is not denied, and an
unattended run stalls on an interactive process. Categories not recorded:
Spoofing, Repudiation and Information disclosure (the guard holds no
identity, log or secret); Elevation of privilege (the guard is not an
authorization control; a missed deny gives the agent nothing beyond its own
session's rights). A false deny is not recorded: the new handling never
produces a deny (NFR5). An unexpected error in the depth-0 parse still yields
no output by decision (SPEC.md assumption A3, docstring step 9); with TM-1 no
known input reaches that path, and it is an accepted residual, not a mitigated
threat.

## Trust Boundaries

### TB-1: Hook payload command text into the guard parser
Crossing: the command string of the hook payload, authored by an agent
session that may carry untrusted text, enters the guard's parser and its scan
of nested `bash -c` strings.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A digit-only word thousands of digits long before a redirect operator, at depth 0, 1, or 2 and deeper, makes redirect reading raise an unhandled conversion error; the guard prints nothing and the later interactive launch passes (FR1, FR5; regression cases FR3, FR7) | TM-1 | The digit word is classified from its zero-stripped length and a string comparison against the 2147483647 limit, with no numeric conversion, so no length raises; an over-range word stays an ordinary word and the redirect binds to the operator's default fd | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | Any other unexpected error raised while parsing a nested string escapes the nested scan, which catches only the undecidable signal; the guard prints nothing and the remaining commands are never judged (FR2) | TM-2 | The handler around the nested parse also catches unexpected errors, skips that string and resumes from the command after the one holding it, never turning the error into a deny (FR2, NFR5) | task0001 AC-4 | VERIFICATION.md Performance / Security Verification: TM-2 |
