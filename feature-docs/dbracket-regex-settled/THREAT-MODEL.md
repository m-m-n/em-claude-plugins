# Threat Model: dbracket-regex-settled

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1 to FR6, NFR1 to NFR4, assumptions A1 to A6), the
single task of this plan (task0001), and the two readings it changes in
`em-workflow/hooks/destructive-guard.py`: `_args_json_conditional_step()` and
the simple-command split of `_args_json_nameref_scan()`. Tier: reduced (no
REQUIREMENTS.md, design step skipped). Depth is deep: task0001 declares
`input-handling`.

The guard is a PreToolUse hook. Before a Bash command runs, it reads the
command string statically and decides whether it runs. That string is written
by the agent and can carry text shaped by untrusted content the agent has
read, so the guard's reading is a trust boundary (TB-1). This feature relaxes
that reading in two places: a `=~` word or an extended-pattern prefix no
longer makes a statement uncertain by itself, and the parentheses counted as a
pattern's no longer split simple commands. Each relaxation is an evasion
surface when the guard's idea of where a pattern or the conditional ends
differs from Bash's; both are recorded below.

The change adds no input, file, network or process boundary (NFR3). The depth
count is one pass over words the guard already lexes, so it opens no
resource-exhaustion path. Repudiation and information disclosure do not
apply: the hook keeps no record and returns nothing beyond its decision.

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
| Elevation of privilege | Closer misplaced inside a pattern. A `]]` written inside the parentheses of a regex or an extended pattern (for example `[[ x =~ (]]) \|\| true -eq 0 ]]`) is pattern text for Bash, which keeps reading the conditional and evaluates the operand of the arithmetic comparison after `\|\|` in the current shell. A reading that closed the conditional at that `]]` would read the rest as an ordinary command under an allow-listed name, keep the chunk certain, and let the following canonical notion call keep its exclusion, so the command in its `--args-json` runs unjudged (FR1, FR2, FR3). | TM-1 | Once a `=~` word written exactly so, or an extended-pattern prefix directly followed by `(`, has been read inside the conditional, the unquoted parenthesis operator tokens are counted and only the first `]]` at depth 0 closes the conditional. A statement that ends with depth 1 or more, whose depth falls below 0, that holds a parenthesis fused with another operator character while counting, or that writes the `=~` or the step from prefix to `(` across a line continuation stays uncertain. The statements after `&&` / `\|\|` follow the same rule (FR3), and the operator words of `_ARGS_JSON_DOUBLE_BRACKET_WORDS` stay uncertain inside a pattern (FR5, A5). | task0001 AC-2, AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | Boundary dropped outside a pattern. FR4 stops treating counted parentheses as simple-command boundaries. If a parenthesis that Bash reads as a command boundary were dropped, the word after it would no longer be checked as a command name against the allow-list, and a command that may declare a nameref or leave the shell state unknown could pass as a word of another command (FR4). | TM-2 | Only the parentheses counted by the TM-1 reading, in a statement the conditional reading did not report uncertain, lose their boundary role. Parentheses before the pattern start, before the opener, after the closer and in a statement without a conditional stay boundaries, and the `[[` command that takes in the pattern's words stays uncertain when one of them is an operator word of `_ARGS_JSON_DOUBLE_BRACKET_WORDS`. | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification, TM-2 |
