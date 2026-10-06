# Threat Model: destructive-guard-lexer-round2-residuals

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`; REQUIREMENTS.md and DESIGN.md are
intentionally absent), the four review findings it resolves, and the lexer
of the destructive-guard PreToolUse hook that the change set touches. The
hook receives the Bash command an agent is about to run and returns allow,
ask or deny; an allow lets the command run without any user confirmation,
including in unattended batch runs. The hook's lexical reading decides
which lines of that command are inspected as commands and which are skipped
as here-document body, so every divergence from bash's reading that skips a
line bash executes is a bypass, and every reading whose cost is superlinear
can push benign commands over the work bound.

All four tasks declare the `input-handling` domain, so the one boundary
found is analysed at deep depth. The test assets the tasks also modify
(`em-workflow/hooks/tests/destructive-guard-cases.json`,
`tests/test_destructive_guard_lexer_agreement.py`) are verification inputs
that never run in the hook's decision path and cross no boundary.

## Trust Boundaries

### TB-1: Agent-proposed Bash command text into the destructive-guard decision
Crossing: the command string Claude Code hands to the PreToolUse hook on
stdin. It is produced by an agent whose output can be steered by untrusted
text the agent has read (repository files, tool output, web content), and
it crosses into the hook, whose decision gates execution of that command
without user confirmation.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A `{` directly after the arithmetic-for header, or the word after `time --` / `time -p --`, is not read at a command position, so a following `((1<<2))` is read as two parentheses holding a here-document operator; the next line, which bash executes, is skipped as body and a destructive command on it is allowed (FR1, FR2). | TM-1 | `{` is recognized as a reserved word wherever a reserved word is recognized directly after a closer, and `--` after `time` / `time -p` keeps the command position; the `((...))` there is an arithmetic command that registers no here-document operator, so the following line is inspected. | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2) |
| Elevation of privilege | A `<<` inside the array subscript of an assignment word (`name[...]=`) is registered as a here-document operator, so lines bash executes are skipped as body (FR3). | TM-2 | At positions where bash accepts an assignment, `name[` is read through its matching `]` and nothing inside opens a here-document operator; an unclosed subscript is settled as not opened, after which no `<<` operator is read, so following lines stay inspected (NFR6). | task0002 AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3, TS-9) |
| Elevation of privilege | A here-document delimiter containing a non-word character (`END-X`, `E.X`) or a quote character (`E\X`) is cut short or mis-valued, so the body is closed at the wrong line and a line bash executes is skipped as body (FR4). | TM-3 | The delimiter is the whole word up to the next unquoted metacharacter, with quote removal applied; close-line matching accepts such values; a delimiter word that cannot be read takes no body, so following lines stay inspected (NFR6). | task0003 AC-2, AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-4, TS-9) |
| Denial of service | Each `((` / `$((` that closes without an adjacent `))` triggers a re-read of the whole text, so work grows quadratically and short benign commands exceed the work bound: the hook answers ask, which batch mode turns into deny, halting unattended runs; crafted input must also not convert an exceeded bound into an allow (FR5, NFR1, NFR2, NFR3). | TM-4 | The two-parentheses reading is reached without a whole-text re-read per opener, keeping work within the linear bound; exceeding the bound still yields ask (deny in batch), never allow. | task0004 AC-2, AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-5, TS-6, TS-12, TS-13) |
