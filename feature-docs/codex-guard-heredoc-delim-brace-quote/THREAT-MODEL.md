# Threat Model: codex-guard-heredoc-delim-brace-quote

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the full tier (no DESIGN.md: the design step was skipped). The feature changes how codex-hook-interactive-guard reads the `<<` / `<<-` delimiter word of a shell command proposed by a Codex agent. That command text is untrusted input reaching a safety control whose verdict (deny, or no output) decides whether an interactive launch goes through in an unattended run, so one trust boundary exists (TB-1). task0001 declares `input-handling`, so TB-1 is analysed at deep depth; its files are the two guard copies listed under Boundary files, and the test module carries no boundary. Realistic categories at TB-1: elevation of privilege (a launch passes the guard because the delimiter is registered differently from zsh) and denial of service (a false deny from a guessed delimiter halts an unattended run; a superlinear scan stalls the hook). Spoofing, repudiation and information disclosure were considered and do not apply: the guard evaluates the command text statically, never executes it, authenticates no party and keeps no record.

## Trust Boundaries

### TB-1: Codex agent command text into the interactive guard parser
Crossing: the shell command a Codex agent proposes (the hook input's tool command, including commands nested in a `zsh -c` argument) enters the guard's static parser, which returns deny or no output; the guard never executes the command.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A `<<` / `<<-` delimiter containing `${ ... }` with quotes, an escaped or quoted `}`, a nested `${ ... }` or a `$( ... )` is registered as a string different from zsh's, so the guard ends the heredoc on a different line and an interactive launch after zsh's terminator is read as body and passes with no output (FR1, FR2; reproduction TS1). | TM-1 | At the delimiter position, find the close of `${` with the zsh-equivalent search (quote spans, escapes, nesting depth, `$( ... )` skipped as a unit) and register the range with the `_remove_range_quotes` quote-removal rule applied; text outside the range keeps its reading. | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 (TS1 to TS15, TS34) |
| Denial of service | A delimiter form whose zsh reading the guard does not reproduce (an unquoted `$'` / `$"` inside or outside `${ ... }`, or a `${` whose close cannot be determined) is registered under a guessed string, so heredoc body lines are judged as commands and a false deny halts an unattended run (TS21 to TS23 are deny before the change) (FR2, FR3, FR4). | TM-2 | Never register a guessed delimiter: these forms raise the existing undecidable outcome, which judges commands up to the last checkpoint and emits nothing otherwise (FR6). Residual: a launch after the checkpoint in these forms is not judged, accepted by SPEC.md A-3. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 (TS16 to TS28) |
| Denial of service | A crafted delimiter with deep `${` nesting, many `$( ... )` or long unclosed constructs makes the new close search superlinear and stalls the hook (NFR2). | TM-3 | A single forward scan linear in the range length; a nested `$( ... )` is skipped once as a unit and never re-read; the existing length-cap and timing tests stay green. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-3 (TS38) |
