# Threat Model: codex-guard-brace-case-group-depth

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md, SPEC.md (FR1-FR6, NFR1-NFR5, A-1 to A-8) and the
substitution reader of `codex-hook-interactive-guard.py` that the feature
changes. Tier: full. Domain that sets the depth: `input-handling` (deep).

The guard is a PreToolUse(Bash) hook. It reads the command text an agent is
about to run and denies an interactive interpreter launch, because such a
launch waits for input and stalls an unattended run. The command text comes
from another process (the agent), and that agent may have been steered by
repository content it read. A misreading in the substitution reader is
therefore a guard bypass: an undecidable chunk gives no output, and no output
lets the command run. This feature changes exactly how that reader finds the
close of a brace-form case statement, so the boundary below applies.

Categories that do not apply at this boundary: Spoofing (the hook
authenticates no party), Repudiation (the feature adds or removes no record of
decisions), Information disclosure (the deny reason does not echo command text,
and this feature does not change the deny output), Elevation of privilege (the
guard grants nothing; it only denies). A false deny (the FR2 / FR3 regression)
is a correctness defect that blocks a legitimate command. Under batch mode the
agent gets the deny reason and can rewrite the command, so it is not a stall.
It is covered by the scenario tests, not by a mitigation.

Domain consistency: task0001 declares `input-handling`. Its guard files are
the Boundary files of TB-1. Its test file is not a boundary: it only runs the
hook.

## Trust Boundaries

### TB-1: Agent-authored command text into the guard's substitution reader
Crossing: the `tool_input.command` string of a PreToolUse(Bash) JSON payload,
written by the agent process and read on standard input by the hook process.
The substitution reader decides where each `$( )` ends, and that decides
which commands the guard judges.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`,
`em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A brace-form item body holds a `{ }` group closed by a `}` at an argument position (FR1). The reader leaves the group open, stops undecidable at the next item terminator and gives no output. An interactive launch after the substitution is never judged, and the unattended run waits for input. | TM-1 | In the item body list itself of a brace-form statement, a standalone, unquoted, unescaped `}` at an argument position is read like the command-position `}`: it lowers the depth when one or more groups are open, and closes the statement at depth 0. The close is located and the launch after it is judged (FR1). | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | The readings added for FR2 (`always` as a reserved word), FR3 (extra function names) and FR1 could be applied wider than zsh applies them. Examples: `always` after a separator or after the `}` that closes the statement; a reserved word or a head word taken as a function name; a quoted or escaped `}` counted. The reader would then put the close of the substitution somewhere zsh does not. Text outside the substitution would be skipped as if inside it, which hides a real launch (a new bypass). | TM-2 | Each new reading applies only under the conditions FR1 to FR4 and A-2 to A-7 state. Every other position keeps the previous reading. A group still open at an item terminator stays undecidable. | task0001 AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | A long or deeply nested command makes the reader's work grow faster than the input length, so the hook overruns its time (NFR1). Examples: thousands of nested `{ }` groups closed by argument-position `}`, a long run of function names, or many `}`. | TM-3 | The reading stays one forward pass. The added state is a constant size per command list, is kept together with the list's existing state, and is restored by the arithmetic re-read (rule 9). No backward look is added (NFR1). | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
