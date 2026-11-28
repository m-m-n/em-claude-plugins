# Threat Model: destructive-guard-resolver-only-evidence

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier reduced; no REQUIREMENTS.md, design step skipped).
The feature changes one reading rule of `em-workflow/hooks/destructive-guard.py`:
how the body of a command-name substitution head is read as rm / git
evidence. The text it reads is the Bash command the agent submits in the
PreToolUse payload, which untrusted content the agent has read can steer, so
the reading sits on a trust boundary (TB-1). task0001 declares
`input-handling`, so TB-1 is analyzed at deep depth. The case table and the
unit test files carry verification only; they are not boundary files.

The narrowing itself is what TB-1 addresses: bodies the guard used to read as
rm / git (any body whose last word was rm / git) become unreadable unless
they match FR1. TB-1 records the two ways the FR1 forms themselves could be
lost while the reader is rewritten.

Accepted by SPEC.md and not mitigated here (FR1, FR2, NFR1, NFR2, and the
SPEC.md Assumptions): a body outside FR1 is unreadable and allowed even when
the shell would print rm / git from it. This covers heads other than the FR1
words (for example `echo`, `type`, `builtin`, a path-form `command` or
`printf`), a resolver word written with quoting or a backslash escape, quoted
command names, and bodies with separators or pipes. This model records no
mitigation for them.

Spoofing, Repudiation, Information disclosure and Denial of service do not
realistically apply at TB-1: the reader is pure string processing over one
body and changes no decision text, logging or resource use.

## Trust Boundaries

### TB-1: agent-submitted Bash command to the destructive-guard decision
Crossing: the Bash command string in the PreToolUse payload, produced by the agent (and steerable by untrusted content it read), crossing into the hook that decides allow, ask or deny.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive command headed by a resolver substitution in an FR1 form (for example `$(which -a rm)`, `$(/usr/bin/which rm)`, `$(command -v -- rm)`, `$(printf rm)`) is read as unreadable by the narrowed reader, for example because of a run of separators or a leading or trailing newline in the body, and is allowed instead of taking the rm / git route (FR1, FR4) | TM-1 | The reader accepts every FR1 shape, treats a run of spaces and tabs as one separator, and drops leading and trailing whitespace, newlines included, before matching; the case table pins deny with reason IDs for the FR1 forms | task0001 AC-1, AC-5 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Tampering | A NAME split by a backslash-newline continuation, which the shell joins back into rm, is read as something other than rm by the rewritten reader and allowed (FR3) | TM-2 | Continuation lines are removed exactly as today before the newline check and the split; the lexer agreement test pins the reading rm and the deny of its command | task0001 AC-4 | VERIFICATION.md, Performance / Security Verification, TM-2 |
