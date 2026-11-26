# Threat Model: dbracket-was-open-close-scan

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (reduced tier: REQUIREMENTS.md absent, design step
skipped) and the code the single task changes, the `was_open` branch of
`_args_json_conditional_step()` in `em-workflow/hooks/destructive-guard.py`,
with its only caller `_args_json_nameref_scan()`.

The feature changes how the PreToolUse guard reads a Bash command string it
receives from the agent. That string can carry text shaped by untrusted
content the agent read, and the guard's reading decides whether the
`--args-json` command of a notion call is inspected before the shell runs it.
This is a trust boundary. task0001 declares the `input-handling` domain, so the
boundary is analyzed at deep depth.

The change narrows the conditional reading: words after the closer of a
continuation statement are no longer read. The realistic threat is therefore a
bypass in which the narrowed reading misses an evaluating word. The changed
code stores nothing, touches no file or network and involves no identity, so
Spoofing, Repudiation, Tampering and Information disclosure do not apply. A
false positive (a certain command read as uncertain) is the defect this
feature fixes, not an attacker-driven threat.

The two test files of task0001 (`em-workflow/hooks/tests/destructive-guard-cases.json`,
`tests/test_destructive_guard_args_json.py`) are not on the boundary: they hold
fixed test data and the hook does not read them at run time.

## Trust Boundaries

### TB-1: Agent-issued Bash command string into the destructive-guard static judgment
Crossing: a Bash command string, written by the agent and possibly shaped by
untrusted content it read, crosses from the Bash tool call into the PreToolUse
hook, whose static reading decides allow / ask / deny before the shell runs it.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A command crafted so that the narrowed reading of a continuation statement (FR1) stops at a word the scan takes for the closer while Bash does not. A word after it that evaluates code (a `=~` regex, an extended pattern, an arithmetic operator word) then escapes the conditional reading, the chunk reads certain, and the `--args-json` command of the following notion call runs uninspected (FR1, FR3, NFR1). | TM-1 | Only the first word written exactly `]]` with no stripped trailing carriage return ends the reading. A `]]` written with a backslash, a quote or a line continuation, or with a stripped trailing carriage return, is read past as an operand. Every word before the closer keeps the `_unsettled()` and `_ARGS_JSON_DOUBLE_BRACKET_WORDS` checks. A continuation statement with no closer stays open and is uncertain at a `;`, a lone `&` or the end of the chunk. The opener-statement branch and the other readings of `_args_json_nameref_scan()` (redirection-variable subscript, deferred evaluation, and the command-level reading of each simple command, which still reads the words after the closer) are unchanged. | task0001 AC-4, AC-7 | VERIFICATION.md, Performance / Security Verification, TM-1 |
