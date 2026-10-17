# Threat Model: codex-guard-anon-arg-backquote

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md and SPEC.md (FR1-FR9, NFR1-NFR3), tier `full`,
design step skipped. The feature changes how the guard reads a `(`...`)`
range among the arguments of a zsh anonymous function inside the command
string it receives on stdin. That command string is the feature's one trust
boundary: the Codex agent composes it, its output can be steered by untrusted
repository or prompt content, and the guard's verdict on it decides whether an
interactive interpreter launch reaches the shell of an unattended run.

The only task (task0001) declares `input-handling`, so the boundary is
analysed at deep depth; no task declares `auth`, `external-io` or
`data-persistence`. Two threats realistically apply, both Denial of service:
the evasion this feature fixes (a regression of the earlier argument-range
change, review finding `1241d15972c80d75`) and the parse cost of the new
fallback path. The hook's input/output shape, its deny reason and its
independence from files, network, processes and environment (NFR2) are not
changed by this feature, so no other STRIDE category gets a row. The known
false deny (SPEC.md "Known False Deny", FR4) is a fail-closed trade-off the
requirements accept, not a threat.

## Trust Boundaries

### TB-1: Agent-composed command string -> guard verdict
Crossing: the `tool_input.command` string the Codex agent sends through the
PreToolUse hook's stdin, crossing from model output (influenceable by
untrusted content) into the guard's parser, whose verdict (one deny object or
no output) decides whether the command runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A backquote inside an argument range (unquoted, or inside double quotes) lets the range end at a `)` inside the backquoted text; the leftover backquote is then read as unclosed, the whole `-c` string becomes undecidable, and an explicit `python3 -i` in the anonymous body is not denied, so the interactive interpreter waits on stdin and stalls the unattended run (FR1, FR2, FR4, FR6) | TM-1 | A range that holds a backquote that is neither inside single quotes nor right after a backslash (one inside double quotes included, balanced or not) is never read as an argument word: its `(` opens a provisional group exactly as for an unquoted `;`, `&` or newline, so the body's explicit `-i` is read and denied; how the range's `)` is located is unchanged | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | A crafted command that nests many anonymous functions whose argument ranges each hold a backquote sends every range to the group reading; restarting the range scan from each nested `(` would make the guard's parse quadratic and overrun the hook's time budget (NFR1) | TM-2 | Noticing the backquote adds constant work per scanned character and no recursion, and every range scan stays charged to the existing work cap, so the whole parse stays linear in the string length | task0001 AC-7 | VERIFICATION.md Performance / Security Verification: TM-2 |
