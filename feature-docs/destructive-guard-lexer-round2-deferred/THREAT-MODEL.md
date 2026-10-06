# Threat Model: destructive-guard-lexer-round2-deferred

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (tier `full`; DESIGN.md is absent
because the design step was skipped), the eight review round 2 findings
they resolve, and the lexer and word split of the destructive-guard
PreToolUse hook that the change set touches. The hook receives the Bash
command an agent is about to run and returns allow, ask or deny; an allow
lets the command run without any user confirmation, including in unattended
batch runs. The hook's lexical reading decides which text of that command
is inspected as commands and which is skipped as here-document body,
comment or expansion content, so every divergence from bash 5.3 that skips
text bash executes is a bypass, and every reading whose cost is superlinear
either pushes benign commands over the work bound or risks the hook
timeout.

All five tasks declare the `input-handling` domain, so the one boundary
found is analysed at deep depth. The test assets every task also modifies
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
| Elevation of privilege | After a `<<` whose delimiter word cannot be read, a parameter-form `${`, `$((`, `$[`, a `((` at a command position or a `case` pattern state still opens, in the lexer or in statement shaping, so the lines bash executes are hidden inside an expansion or a case pattern and a destructive command there is allowed; scattered per-site tail checks let such gaps reappear (FR2, FR8). | TM-1 | Once a tail source is met these openers are refused (literal, listed as unopened) and statement shaping opens no case construct from the tail start on; every tail decision of the pass comes from one gate function, while `$(`, backticks and the command form of `${` still open so their content is inspected. | task0001 AC-2, AC-3, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-2, TS-11, TS-18) |
| Elevation of privilege | A `<<` after an assignment-word subscript whose `]` comes on a later line is not read as the real operator bash sees, so a quote or `${` in its body takes the close line and the following lines into a region and a destructive line bash executes is allowed (FR1). | TM-2 | The subscript is read across the newline to its `]`, and the following `<<` is a real operator whose body starts on the line after the operator's line and closes at its delimiter line; nothing in the body opens a region over later lines. | task0002 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-1) |
| Elevation of privilege | A line continuation inside an assignment word's name (`a\<newline>[1<<2]=x`) defeats subscript detection, so the `<<` inside becomes an operator whose whole-word delimiter matches a later line and swallows the destructive lines in between (FR4). | TM-3 | `NAME[` is detected on the word's leading characters with backslash-newline pairs removed, at the positions where it is detected today, and the subscript opens at the original `[`; an unclosed one keeps the unmatched-subscript ask. | task0002 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-4) |
| Elevation of privilege | `\r`, `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`, U+2028 and U+2029 end a delimiter word or a line for the hook but not for bash, so a body is placed over lines bash executes as commands, or closes early and leaves a command substitution behind a `#` (FR3). | TM-4 | A delimiter word ends only at a metacharacter, and the line index and the operator's-line rule split lines only at `\n`; the other characters are word characters. | task0003 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-3, TS-15) |
| Elevation of privilege | For an unquoted delimiter, bash joins backslash-newline before comparing a close line and the hook does not, so a body closes early (a `#` then hides a command substitution bash expands in the body) or late (a joined close line is missed and the lines after it are hidden) (FR5). | TM-5 | Unquoted close lines are compared on continuation-joined lines whose start is the body's first line or a line not preceded by an odd number of backslashes, with `<<-` tab removal after joining; quoted delimiters keep physical-line matching. | task0003 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 (TS-5, TS-16) |
| Elevation of privilege | `\r` is read as a blank, so a `#` right after it opens a comment that hides the rest of the line, which bash executes because the `#` is inside a word; reading `\r` as a word character must also not turn an existing denied command with a trailing `\r` into an allowed one (FR6). | TM-6 | Blanks are space and tab only in the lexer and in the masked-view tokenizer (both of its modes); the decision layer disregards a trailing `\r` when matching words against destructive rules. | task0004 AC-2, AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-6 (TS-6, TS-15) |
| Elevation of privilege | bash 5.3 runs the content of `${ cmd; }` and `${\| cmd; }` as commands, but the hook reads it as a parameter expansion whose content is never inspected, so a destructive command inside is allowed (FR7). | TM-7 | `${` followed by a space, a tab, a newline or a vertical bar opens a command-form substitution region at every level; its content, closed or unclosed, is queued and inspected as commands, including in unquoted here-document bodies. | task0005 AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-7 (TS-7, TS-17) |
| Denial of service | A new reading (name continuation removal, continuation-joined close lines, nested unclosed command forms) rescans text per opener, per body or per nesting level, so crafted or benign input exceeds the work bound or the hook timeout; an exceeded bound must never become an allow (NFR1, NFR2, NFR3). | TM-8 | Each new reading keeps lexer work within `LEX_WORK_FACTOR` × length + 1024 and doubling-linear; nested unclosed command forms are cut off by the statement layer's relative scan budget, which answers ask (deny in batch), never allow. | task0002 AC-6, task0003 AC-6, task0004 AC-6, task0005 AC-6 | VERIFICATION.md Performance / Security Verification, TM-8 (TS-9, TS-13, TS-14) |
