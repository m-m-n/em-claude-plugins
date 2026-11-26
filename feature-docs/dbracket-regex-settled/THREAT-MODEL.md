# Threat Model: dbracket-regex-settled

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1 to FR7, NFR1 to NFR4, assumptions A1 to A8), the two
tasks of this plan (task0001, merged, and task0002), and the three readings
they change in `em-workflow/hooks/destructive-guard.py`:
`_args_json_conditional_step()`, the simple-command split of
`_args_json_nameref_scan()`, and the simple-command split of item 3 of
`_args_json_shadow_scan()`. Tier: reduced (no REQUIREMENTS.md, design step
skipped). Depth is deep: both tasks declare `input-handling`.

The guard is a PreToolUse hook. Before a Bash command runs, it reads the
command string statically and decides whether it runs. That string is written
by the agent and can carry text shaped by untrusted content the agent has
read, so the guard's reading is a trust boundary (TB-1). This feature relaxes
that reading in three places: a `=~` word or an extended-pattern prefix no
longer makes a statement uncertain by itself, the parentheses counted as a
pattern's no longer split simple commands in the nameref reading, and the
same parentheses no longer split simple commands in item 3 of the shadow
scan, the reading that lifts the notion pair's exclusion. Each relaxation is
an evasion surface when the guard's idea of where a pattern or the
conditional ends differs from Bash's; all three are recorded below.

The change adds no input, file, network or process boundary (NFR3). The depth
count is one pass over words the guard already lexes, and the shadow scan runs
it once more over its own tokens of the same chunk, so it opens no
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
| Elevation of privilege | Closer misplaced inside a pattern. A `]]` written inside the parentheses of a regex or an extended pattern (for example `[[ x =~ (]]) \|\| true -eq 0 ]]`), or touching a pattern's parenthesis with no blank between (`[[ x =~ (x)]] \|\| true -eq 0 ]]`, which Bash reads as one pattern word), is pattern text for Bash, which keeps reading the conditional and evaluates the operand of the arithmetic comparison after `\|\|` in the current shell. A reading that closed the conditional at that `]]` would read the rest as an ordinary command under an allow-listed name, keep the chunk certain, and let the following canonical notion call keep its exclusion, so the command in its `--args-json` runs unjudged (FR1, FR2, FR3). | TM-1 | Once a `=~` word written exactly so, or an extended-pattern prefix directly followed by `(`, has been read inside the conditional, the unquoted parenthesis operator tokens are counted and only the first `]]` at depth 0 closes the conditional. A statement that ends with depth 1 or more, whose depth falls below 0, that holds a parenthesis fused with another operator character while counting, whose `]]` touches a `)` before it or a `(` after it with no blank between, or that writes the `=~` or the step from prefix to `(` across a line continuation stays uncertain. The statements after `&&` / `\|\|` follow the same rule (FR3), and the operator words of `_ARGS_JSON_DOUBLE_BRACKET_WORDS` stay uncertain inside a pattern (FR5, A5). | task0001 AC-2, AC-3, AC-4; task0002 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | Boundary dropped outside a pattern in the nameref reading. FR4 stops treating counted parentheses as simple-command boundaries. If a parenthesis that Bash reads as a command boundary were dropped, the word after it would no longer be checked as a command name against the allow-list, and a command that may declare a nameref or leave the shell state unknown could pass as a word of another command (FR4). | TM-2 | Only the parentheses counted by the TM-1 reading, in a statement the conditional reading did not report uncertain, lose their boundary role. Parentheses before the pattern start, before the opener, after the closer and in a statement without a conditional stay boundaries, and the `[[` command that takes in the pattern's words stays uncertain when one of them is an operator word of `_ARGS_JSON_DOUBLE_BRACKET_WORDS`. | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Elevation of privilege | Boundary dropped in the lift reading. FR7 makes item 3 of `_args_json_shadow_scan()`, which lifts the notion pair's exclusion when some simple command's name runs a string as code or cannot be restored, keep counted parentheses inside their simple command too. That reading matters on its own when the notion call's `--session` value is a literal, which the nameref reading does not concern. If item 3 dropped a parenthesis that Bash reads as a command boundary, used parentheses counted from another lexing of the chunk, or used parentheses of a conditional whose end the reading never placed (a statement read uncertain before its closer, or a conditional still open at the end of the chunk), a command name that runs a string as code would stand inside another command's words, the exclusion would not be lifted, and the command in the `--args-json` payload would run unjudged (FR7, A7, A8). | TM-3 | Item 3 takes counted parentheses only from `_args_json_conditional_step()` run on item 3's own lexed tokens of each statement, with the open state carried from the first statement of the chunk, and uses those of a conditional only once the reading has reached that conditional's closer with no statement on the way read uncertain. A statement read uncertain, every statement after it, the statements of a conditional still open at the end of the chunk, and a statement with no counted parenthesis are split at every parenthesis as before. Parentheses before a pattern start, before the opener, after the closer and in a statement without a conditional stay boundaries. Items 1, 2, 4 and 5 of the shadow scan and the judgment of `_args_json_runs_string_as_code()` are unchanged. | task0002 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-3 |
