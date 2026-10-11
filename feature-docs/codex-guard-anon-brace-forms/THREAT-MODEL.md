# Threat Model: codex-guard-anon-brace-forms

## Verdict
threats-identified

## Rationale
Inspected REQUIREMENTS.md, SPEC.md, both copies of
`codex-hook-interactive-guard.py` and its contract test module, at the full
tier. The only input is the command string of a Codex Bash call, which the
model writes and the guard receives on stdin; task0001 declares
`input-handling`, so that boundary is analysed at deep depth.

The property at stake is availability: an interactive launch that passes the
guard is left on a closed pseudo terminal as an orphan process that keeps
waiting for input. Only Denial of service applies. The guard authenticates
nobody, changes no data, keeps no record, grants no privilege, and its deny
reason does not echo the command text, so Spoofing, Tampering, Repudiation,
Information disclosure and Elevation of privilege have no row.

## Trust Boundaries

### TB-1: Codex command string into the guard's parser
Crossing: the Bash command string of a Codex tool call (model-written text)
enters the guard as JSON on stdin; the guard's reading of it decides whether
the launch reaches the pseudo terminal.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | An interactive launch in the body of a zsh anonymous function (the parenless form, or a body followed by arguments) is never judged, so it runs and is left as an orphan waiting for input (FR1, FR2) | TM-1 | The parser recognizes the three anonymous-function heads and judges the body's commands; the words after the body's closing brace are read as arguments instead of making the string undecidable | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | The new readings pass too much: the argument span after the body, or the pipe connection handed to the body, reaches past the anonymous function and hides a later program-less or interactive launch, or the connection suppresses an explicit `-i` (FR2, FR3) | TM-2 | The argument span ends at the next separator or at the close of an enclosing subshell, and applies to anonymous bodies only; the pipe connection is set on the body group only; an explicit interactive option is denied whatever the connection | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | A crafted long command makes the parenless-form decision re-read the word list at each `{`, or makes nested anonymous bodies recurse, so the guard does not answer in time or exhausts the call stack (NFR2, NFR3) | TM-3 | The parenless-form decision takes constant time per `{`, from per-command state updated as words are appended; groups stay on the explicit stack; no function calls itself or forms a cycle | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
