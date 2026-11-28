# Threat Model: dbracket-was-open-close-scan

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md as changed after review round 1 (reduced tier:
REQUIREMENTS.md absent, design step skipped), the `was_open` branch of
`_args_json_conditional_step()` in `em-workflow/hooks/destructive-guard.py` as
merged by task0001, and its only caller `_args_json_nameref_scan()`.

The feature changes how the PreToolUse guard reads a Bash command string it
receives from the agent. That string can carry text shaped by untrusted
content the agent read, and the guard's reading decides whether the
`--args-json` command of a notion call is inspected before the shell runs it.
This is a trust boundary. task0001 and task0002 both declare the
`input-handling` domain, so the boundary is analyzed at deep depth.

The change narrows the conditional reading of a continuation statement: after
its closer, the redirection targets are no longer read. The realistic threats
are bypasses in which the narrowed reading misses a word Bash evaluates: a
closer the scan accepts and Bash does not (TM-1), or a word after the closer
that the reading skips while Bash evaluates it (TM-2). Review round 1 found the
second kind when the reading skipped every word after the closer (a new `[[`
after `then` / `do`). The changed code stores nothing, touches no file or
network and involves no identity, so Spoofing, Repudiation, Tampering and
Information disclosure do not apply. A false positive (a certain command read
as uncertain) is the defect this feature fixes, not an attacker-driven threat.

The two test files both tasks declare
(`em-workflow/hooks/tests/destructive-guard-cases.json`,
`tests/test_destructive_guard_args_json.py`) are not on the boundary: they
hold fixed test data and the hook does not read them at run time.

Outside this feature's requirements: neither branch of the conditional
reading follows a new `[[` opened after the closer that `&&` or `||` splits
again into a later statement; once the closer is met, the conditional counts
as closed. This feature does not change that reading; the create-plan report
lists it as an open question.

## Trust Boundaries

### TB-1: Agent-issued Bash command string into the destructive-guard static judgment
Crossing: a Bash command string, written by the agent and possibly shaped by
untrusted content it read, crosses from the Bash tool call into the PreToolUse
hook, whose static reading decides allow / ask / deny before the shell runs it.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A command crafted so that the reading of a continuation statement (FR1) takes a word for the closer while Bash does not. Bash is still inside the conditional, but the reading treats the conditional as closed, so a word after it that evaluates code inside the conditional (a `=~` regex, an extended pattern, an arithmetic operator word) can escape the reading, the chunk reads certain, and the `--args-json` command of the following notion call runs uninspected (FR1, FR3, NFR1). | TM-1 | Only the first word written exactly `]]` with no stripped trailing carriage return is the closer. A `]]` written with a backslash, a quote or a line continuation, or with a stripped trailing carriage return, is read past as an operand. Every word before the closer keeps the `_unsettled()` and `_ARGS_JSON_DOUBLE_BRACKET_WORDS` checks. A continuation statement with no closer stays open and is uncertain at a `;`, a lone `&` or the end of the chunk. The opener-statement branch and the other readings of `_args_json_nameref_scan()` (redirection-variable subscript, deferred evaluation, and the command-level reading of each simple command, which still reads the words after the closer) are unchanged. | task0001 AC-4, AC-7; task0002 AC-7 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | A command crafted so that, after the closer of a continuation statement, a word Bash evaluates is not read: an operator word (`-eq` and the other integer comparisons, `-v`) or a `=~` of a new `[[` after `then` / `do`, which Bash accepts directly after `]]` with no separator, skipped because the reading stops at the closer or takes the word for a redirection target. The chunk reads certain, and the `--args-json` command of the following notion call runs uninspected (FR1, FR3, NFR1). | TM-2 | After the closer, a word is skipped only when it directly follows a token the lexer marked as an operator whose whole text has the redirection-operator shape (recognized after the fused-closer split, so `)>` counts as `)` and `>`). Every other word after the closer (reserved words such as `then` / `do`, a new `[[`, its operands and operator words, a word after a quoted or escaped `>` or `<`, a word after a `)` or `(`) keeps the `_unsettled()` and `_ARGS_JSON_DOUBLE_BRACKET_WORDS` checks, either of which makes the statement uncertain. | task0002 AC-1, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-2 |
