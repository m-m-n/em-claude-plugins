# Threat Model: codex-guard-anon-heredoc-paren-delim

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR7, NFR1-NFR4), tier `full`,
and task0001's domains (`input-handling`), which set TB-1 to deep depth.

The guard reads the `tool_input.command` text an agent session submits and
decides between deny and no output. That text crosses from the agent process
into the guard's static shell parser; this is the feature's only trust
boundary (the guard reads no files, network or child processes — NFR3). The
change alters how one parser state derives a heredoc delimiter, and the
delimiter decides which following lines the guard inspects as commands and
which it skips as heredoc body. Two threats realistically apply, both
Denial of service against the unattended run the guard protects: a missed
interactive launch, and parse cost growth.

Categories without a row: Spoofing (the guard authenticates nothing and the
change adds no identity decision), Tampering (the guard changes no input or
state), Repudiation (the guard has no audit role), Information disclosure
(the deny message and the inputs read are unchanged), Elevation of privilege
(the guard grants nothing; a miss is captured under Denial of service).

Accepted residual, not a mitigation: an input made unknowable by FR3 produces
no output, so nothing in it is denied. This is the guard's existing policy
for inputs it cannot read (NFR4) and is not introduced by this design as a
protective measure. A false deny (the reported bug) is fail-closed and is the
functional defect FR1 corrects, not a recorded threat.

## Trust Boundaries

### TB-1: Agent-submitted command text into the guard parser
Crossing: the `tool_input.command` string an agent session submits,
delivered as hook JSON on standard input, into the guard's static parser.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A delimiter derived from an anonymous-function argument range that differs from zsh's reading makes the guard end the heredoc body later than zsh does, or never; lines zsh runs as commands after the true terminator are skipped as body, so an interactive launch reaches the unattended run and hangs it (FR1, FR2, FR3; AC-2, AC-4, AC-5, AC-6, AC-8) | TM-1 | Quote-remove only the range text, by the normal path's rules; leave the already-processed part outside the range untouched; make the input unknowable only for an unquoted `$'` / `$"`, so a quoted or escaped `$` still yields the zsh delimiter; keep inspecting the anonymous-function body after the heredoc closes | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | Command text with long or numerous delimiter ranges makes the new removal and `$'` / `$"` check cost grow faster than the input, so the hook overruns its time budget and stalls or fails the run (NFR1; FR4's scan bound) | TM-2 | One left-to-right pass per range, proportional to the range length; no rescan per body line; the `PAREN_SCAN_FACTOR` bound unchanged | task0001 AC-7 | VERIFICATION.md Performance / Security Verification: TM-2 |
