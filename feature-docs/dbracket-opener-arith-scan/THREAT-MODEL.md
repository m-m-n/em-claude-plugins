# Threat Model: dbracket-opener-arith-scan

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1 to FR3, NFR1 to NFR5), the single task of this plan
(task0001), and the reading it changes, `_args_json_conditional_step()` as
called from `_args_json_nameref_scan()` in
`em-workflow/hooks/destructive-guard.py`. Tier: reduced (no REQUIREMENTS.md,
design step skipped). Depth is deep: task0001 declares `input-handling`.

The guard is a PreToolUse hook. Before a Bash command runs, it reads the
command string statically and decides whether it runs. That command string is
written by the agent and can carry text shaped by untrusted content the agent
has read, so the guard's reading is a trust boundary (TB-1). This feature
changes only how that reading treats the statement that opens a `[[ ]]`
conditional. It adds no input, file, network or process boundary: the new
scan reads the same lexed words of the same statement and executes nothing
(NFR4). Its cost is one pass over the words of a statement the guard already
lexes, so it opens no new resource-exhaustion path. The one threat that
applies is evasion of the guard, recorded below.

## Trust Boundaries

### TB-1: Agent-written Bash command into the destructive-guard static judgment
Crossing: the Bash command string the agent proposes, whose text may be shaped
by untrusted content, crosses into the PreToolUse hook. The hook's allow /
ask / deny decision governs whether the command runs, including an
`mcp-bridge` call whose `--args-json` payload carries a command for another
tool.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A `[[ ]]` conditional whose opening statement holds an arithmetic comparison operator or `-v` inside parentheses, after an allow-listed name (for example `[[ ( true -eq 0 ) && true ]]`, also after a leading `if`), evaluates its operand in the current shell, yet the guard reads the chunk as certain. The following canonical notion call keeps the notion-pair exclusion, and the command in its `--args-json` runs without being judged (FR1, FR2). | TM-1 | In the statement that opens the conditional, the words from just after the opener up to just before the closer (to the end of the statement when it has none) are scanned for the operator words. A hit makes the chunk uncertain, so the exclusion is dropped and the payload is decoded and judged. Words outside that range are not scanned (FR3). | task0001 AC-1, AC-2 | VERIFICATION.md, Performance / Security Verification, TM-1 |
