# Threat Model: mcp-bridge-args-json-exec-guard

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md as revised by the spec-change re-entry
of review round 1 (FR1-FR13, NFR1-NFR5, assumptions A1-A11) and by the spec
change of verify round 1 (AC-11, NFR3), at the full tier; the design step was
skipped, so there is no DESIGN.md. destructive-guard is the
PreToolUse hook whose static analysis of a Bash command decides allow, deny or
ask before the shell runs it. The command is written by the agent and can
carry content from untrusted inputs. For `mcp-bridge run`, an allow lets an MCP
server process receive the `--args-json` value, and a shell-executing tool runs
its `command` in a shell; for a `-c` / `eval` / here-string payload, an allow
lets a nested shell run it. That decision point is TB-1. task0001, task0003 and
task0005 declare `auth` and `input-handling`; task0002 and task0004 declare
`input-handling`; all five are merged. All five change only
`em-workflow/hooks/destructive-guard.py` among the boundary files, so TB-1 is
analysed at deep depth. The case file and the unit test module are test data
and test code, not boundary files.

This re-plan closes the remainder the first plan accepted: the flag forms
mcp-bridge reads (a quoted flag name, the `=` form, a single dash, a value
before `--` or a positional word, a repeated `--args-json`), a destination
that is not static, and static words whose quoting the guard cannot restore
(TM-6, TM-7); and the payload counter that silently dropped decoded commands
and payloads (TM-2, TM-8). The flag reading follows the option parsing
recorded in mcp-bridge-exec-tool-rescan IMPLEMENTATION.md decision D1 (A11).

The spec change of verify round 1 corrects only the recorded pre-change
verdict of TS-19 (deny, SPEC.md AC-11) and removes TS-19 from the pre-change
reproduction set (SPEC.md NFR3). It adds no input, boundary or threat and
changes no mitigation, so the verdict and TM-1 to TM-8 stand unchanged.

Accepted remainder (SPEC.md FR6 and FR8; IMPLEMENTATION.md O1 and O2): a
command written as plain text in a key other than the top-level `command`, or
in a `command` below the top level (O1); and the FR6 forms (O2) -- an
`--args-json` value word or a flag-position word that is not static, an
unknown flag, a value-taking flag with no value word, no `--args-json`, a
value that does not decode as JSON, a decoded top level that is not an
object. They keep today's raw-string verdict, which is allow when the raw text
shows no substitution. No mitigation is planned for them.

Unchanged dependencies: the notion pair stays excluded on assumption A1, as in
mcp-bridge-exec-tool-rescan, through the canonical flag reading only (A9).
Decoded strings can hold control characters, as a raw command can; the re-scan
treats them as it treats the raw command's. The new asks become deny under
batch (A10); that is a cost to legitimate commands, not a gain for an
attacker, so it has no row.

Categories with no row: Repudiation and Information disclosure (the change
adds no record and exposes no data).

## Trust Boundaries

### TB-1: Agent-issued Bash command to destructive-guard verdict
Crossing: a Bash command string written by the agent crosses into
destructive-guard's static analysis. Its verdict decides whether the shell
runs it: for `mcp-bridge run`, the `--args-json` value goes, after Bash quote
removal and JSON decoding, to an MCP server process, and an
argument-executing tool runs the decoded `command` in a shell; for a `-c` /
`eval` / here-string payload, a nested shell runs the payload.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive command for a shell-executing tool is written where the raw-string scan cannot see it: a substitution in JSON escapes, a double-quoted `\$(`, an ANSI-C `\x24(`, or plain text in the top-level `command`; the guard allows it and the tool runs it (FR3, FR4, FR5; SPEC.md TS-1 to TS-8) | TM-1 | The value word is rebuilt under Bash quoting rules and decoded as JSON; the candidate bodies of every string value and every top-level `command` string are queued for the ordinary re-scan, at every statement position; the step only adds chunks, so the raw-string scan and every existing verdict stay (NFR2) | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Tampering | A key is repeated so that the guard reads one value while mcp-bridge or the tool uses another, or the top-level `command` pairs outnumber the payload counter so that the later ones are dropped unscanned (FR4, FR5, A2, A4; finding 32aa9e6e947c325d) | TM-2 | Every key/value pair of every object is kept and inspected, duplicates included; the top-level `command` strings take no count from `MAX_SHELL_PAYLOAD_EXPANSIONS` and are bounded only by the scan budget, whose overrun gives the `scan-budget-exceeded` ask | task0001 AC-5, task0003 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-2 |
| Tampering | A value that the guard's decoder cannot finish, though mcp-bridge or the tool decodes it (nesting deeper than the decoder handles, a number it refuses), falls to the FR6 path and keeps today's verdict, allow (FR6, FR7, A2) | TM-3 | Nesting deeper than `MAX_ARGS_JSON_DEPTH`, measured before decoding, and any decoder failure other than a JSON syntax error give the `scan-budget-exceeded` ask (deny under batch), settled after the queue is drained; only a syntax error is an FR6 form | task0001 AC-5, task0003 AC-7 | VERIFICATION.md Performance / Security Verification, item TM-3 |
| Denial of service | A large or deeply nested value, or decoded strings holding deep substitution chains, push the hook past its 10-second timeout, where its verdict is lost; or the step's own bound ends the scan before the inspections already queued run, so a deny they would earn is weakened to an ask (FR7, NFR1; findings 2a7b7391eec63ca0, 3be0fecc1174dfe2) | TM-4 | The rebuild, the decode and the walk are charged to the relative scan budget of `statements()`, queued chunks are charged when popped, and the walk is iterative; a step overrun, or a charge that would pass the budget, is not added, queues nothing and holds the `scan-budget-exceeded` ask until the queue is drained, so a deny found there wins | task0001 AC-6, task0003 AC-7 | VERIFICATION.md Performance / Security Verification, item TM-4 |
| Spoofing | A command makes the guard read the notion pair while mcp-bridge receives another server or tool (a repeated `--mcp` / `--tool` whose last value wins, a quoted `notion`, a quoted flag name), so that FR2 skips the decode (FR2, A9; SPEC.md TS-29) | TM-5 | FR2 excludes a statement only when the canonical flag reading determines the pair: `--mcp`, `--tool` and `--args-json` each once, every flag word and the values `notion` and `notion-create-comment` each written as one unquoted run (mcp-bridge-exec-tool-rescan FR1); every other readable sequence is decoded | task0001 AC-3, task0003 AC-3 | VERIFICATION.md Performance / Security Verification, item TM-5 |
| Elevation of privilege | The value is written in a flag form mcp-bridge reads but the guard's reading does not -- a quoted or backslashed flag name, the `=` form, a single-dash flag, a value before `--` or a positional word, a repeated `--args-json` -- or behind a destination that is not static, so the decode is skipped and the destructive value is allowed (FR3, FR6, A8, A11; findings 65c5a71c6af6cb06, e0e4df99e5cded9d; SPEC.md TS-17, TS-20, TS-23 to TS-26) | TM-6 | The words after `run` are read as mcp-bridge reads them: flag words after quote removal, both dash forms, the `=` form, `--` and a positional word ending the flags; every `--args-json` value is inspected on its own, whatever the destination; only the FR6 forms keep the raw-string verdict | task0003 AC-2 | VERIFICATION.md Performance / Security Verification, item TM-6 |
| Elevation of privilege | A static word whose quoting the guard cannot restore, though Bash passes it on (an ANSI-C NUL that ends the word, a character outside ASCII, an escape `_decode_ansi_c()` does not handle, a locale quote), keeps the decode from running, and the destructive value is allowed (FR11; finding e0e4df99e5cded9d; SPEC.md TS-21) | TM-7 | Such a word in value or flag position, with no FR6 (1) element in it, holds the `args-json-unrestorable` ask, settled after the queue is drained; a deny found wins; batch demotes the ask to deny; the notion pair is not affected | task0003 AC-5 | VERIFICATION.md Performance / Security Verification, item TM-7 |
| Elevation of privilege | Harmless `-c` / `eval` / here-string payloads, or decoded top-level `command` strings, use up the `MAX_SHELL_PAYLOAD_EXPANSIONS` counter ahead of a destructive payload, which is then silently not scanned and allowed (FR5, FR12; finding 934ab7486f2cfbfb; SPEC.md TS-19, TS-22) | TM-8 | Decoded `command` strings take no count; a payload that is not queued because the counter is used up holds the `scan-budget-exceeded` ask, settled after the queue is drained; a deny found wins | task0003 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-8 |
