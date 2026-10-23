# Threat Model: codex-guard-delim-brace-quote-per-shell

## Verdict
threats-identified

## Rationale
Inspected: the guard's single input, `tool_input.command` of the PreToolUse(Bash)
JSON read from standard input. The Codex agent composes that string, and it can
carry text influenced by untrusted content the agent has read. The literal shell
`-c` strings nested in it are read by the same parser. Tier: full. task0001
declares `input-handling`, so this boundary is analysed at deep depth. The guard
touches no file, network connection or child process, keeps no state between
calls and has no authentication, so this is the only trust boundary. The test
file is not a boundary.

Not recorded as threats:
- False denies caused by the dual reading of FR3, where one reading places a
  launch inside a heredoc body. They are a cost SPEC FR3 accepts, not a way to
  break the guard.
- The miss on an unquoted `$'` inside a range under bash. SPEC A-4 accepts it.
- The ksh / mksh behaviour that follows neither rule. SPEC A-1 accepts it.

## Trust Boundaries

### TB-1: Agent-composed Bash command string -> guard parser
Crossing: the command string (and every literal shell `-c` string nested in it) passes from the Codex agent, whose output untrusted content can influence, into the guard's parser and judgment. The guard's deny is the policy enforcement point for interactive launches.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A string held by `bash -c` (or `sh -c` / `ksh -c`) has a heredoc delimiter with a quoted `${ ... }` range. The guard reads it with zsh's quote removal, so it closes the body on a different line than the shell does. The interactive launch after the shell's real terminator line is then read as body text and passes the guard (FR1, FR2, FR3; this is the fail-open the feature fixes). | TM-1 | Read the delimiter range by the rule of the shell that directly holds the string. Bash gets the bash form. sh and ksh get both forms, and the guard denies when either reading denies. zsh, dash and the hook command keep quote removal. | task0001 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Elevation of privilege | A string that is read twice (held by sh or ksh) is crafted so that one reading hides the other reading's deny. The ways: the reading stops undecidable, it raises an unexpected error, or it is wrongly judged identical to the other so the second reading is skipped (FR3). | TM-2 | The two readings are combined independently. An undecidable reading adds its checkpoint commands. A reading that raises any other exception adds nothing and drops nothing from the other reading. The second reading is skipped only when every parser of the first reading finished, by returning or by raising `_Undecidable`, and none of them registered a delimiter whose two forms differ. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, item TM-2 |
| Denial of service | Each sh / ksh string is read twice, with a re-read for each reading, and its nested strings are walked once per reading. This multiplies parse work. A crafted string that nests deeply and uses differing delimiters could push the hook past its time bound and stall the Bash call (FR3, FR5, NFR2). | TM-3 | A string gets at most two readings and each reading at most two reads, each in linear time. A string counts once, at its length, toward NESTED_READ_LIMIT before it is read. Each walk of a nested string at level two or deeper counts again. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-3 |
