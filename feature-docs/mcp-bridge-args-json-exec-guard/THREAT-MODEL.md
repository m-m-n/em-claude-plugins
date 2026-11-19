# Threat Model: mcp-bridge-args-json-exec-guard

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR10, NFR1-NFR4, assumptions
A1-A7) at the full tier; the design step was skipped, so there is no
DESIGN.md. destructive-guard is the PreToolUse hook whose static analysis of a
Bash command decides allow, deny or ask before the shell runs it. The command
is written by the agent and can carry content from untrusted inputs. For
`mcp-bridge run`, an allow lets an MCP server process receive the
`--args-json` value, and a shell-executing tool runs its `command` in a shell.
That decision point is TB-1. task0001 declares `auth` and `input-handling`,
and task0002 declares `input-handling`; both change only
`em-workflow/hooks/destructive-guard.py` among the boundary files, so TB-1 is
analysed at deep depth. The case file and the unit test module are test data
and test code, not boundary files.

Accepted remainder (SPEC.md FR6 and FR8; IMPLEMENTATION.md O1 and O2): the
forms the static reading does not settle keep today's verdict, which is allow
when the raw text shows no substitution. Some of them are forms mcp-bridge
still reads, given the option parsing recorded in mcp-bridge-exec-tool-rescan
IMPLEMENTATION.md decision D1: a single-dash or `=` form of a flag, a `--` or
a positional word after the value, a repeated `--args-json`. A value word whose
ANSI-C escapes `_decode_ansi_c()` does not decode is another. A plain-text
command in a key other than the top-level `command` (O1) is not detected
either. No mitigation is planned for these; they are an open question of
IMPLEMENTATION.md.

Unchanged dependencies: the notion pair stays excluded on assumption A1, as in
mcp-bridge-exec-tool-rescan. Once the `MAX_SHELL_PAYLOAD_EXPANSIONS` counter is
used up, a top-level `command` string is not queued, the same as a `-c` or
`eval` payload (A4); the counter and its handling are not changed. Decoded
strings can hold control characters, as a raw command can; the re-scan treats
them as it treats the raw command's.

Categories with no row: Repudiation and Information disclosure (the change
adds no record and exposes no data).

## Trust Boundaries

### TB-1: Agent-issued Bash command to destructive-guard verdict, for a shell-executing MCP tool
Crossing: a Bash command string written by the agent crosses into
destructive-guard's static analysis. Its verdict decides whether the shell
runs `mcp-bridge run`, which hands the `--args-json` value, after Bash quote
removal and JSON decoding, to an MCP server process; an argument-executing
tool runs the decoded `command` in a shell.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive command for a shell-executing tool is written where the raw-string scan cannot see it: a substitution in JSON escapes, a double-quoted `\$(`, an ANSI-C `\x24(`, or plain text in the top-level `command`; the guard allows it and the tool runs it (FR3, FR4, FR5; SPEC.md TS-1 to TS-8) | TM-1 | The value word is rebuilt under Bash quoting rules and decoded as JSON; the candidate bodies of every string value and every top-level `command` string are queued for the ordinary re-scan, at every statement position; the step only adds chunks, so the raw-string scan and every existing verdict stay (NFR2) | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Tampering | A key is repeated so that the guard reads one value while mcp-bridge or the tool uses another, and the destructive value goes unread (FR4, FR5, A2) | TM-2 | Every key/value pair of every object is kept and inspected, duplicates included, for the candidate search and for the top-level `command` | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, item TM-2 |
| Tampering | A value that the guard's decoder cannot finish, though mcp-bridge or the tool decodes it (nesting deeper than the decoder handles, a number it refuses), falls to the FR6 path and keeps today's verdict, allow (FR6, FR7, A2) | TM-3 | Nesting deeper than `MAX_ARGS_JSON_DEPTH`, measured before decoding, and any decoder failure other than a JSON syntax error end the scan with the `scan-budget-exceeded` ask (deny under batch); only a syntax error is an FR6 form | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, item TM-3 |
| Denial of service | A large or deeply nested value, or decoded strings holding deep substitution chains, push the hook past its 10-second timeout, where its verdict is lost (FR7, NFR1) | TM-4 | The rebuild, the decode and the walk are charged to the relative scan budget of `statements()`, queued chunks are charged when popped, and the walk is iterative; an overrun gives the `scan-budget-exceeded` ask | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-4 |
| Spoofing | A command makes the guard read the notion pair while mcp-bridge receives another server or tool (a repeated `--mcp` / `--tool` whose last value wins, a quoted `notion`), so that FR2 skips the decode (FR2) | TM-5 | FR2 excludes a statement only when the canonical flag reading determines the pair: `--mcp`, `--tool` and `--args-json` each once, the values `notion` and `notion-create-comment` each written as one unquoted run (mcp-bridge-exec-tool-rescan FR1); every other readable sequence is decoded | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, item TM-5 |
