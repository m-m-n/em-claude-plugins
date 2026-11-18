# Threat Model: mcp-bridge-exec-tool-rescan

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR6, NFR1-NFR4, assumptions
A1-A4) at the full tier; the design step was skipped, so there is no
DESIGN.md. The feature changes one condition (S1) of destructive-guard, the
PreToolUse hook whose static analysis of a Bash command decides allow, deny
or ask before the shell runs it. The command text is written by the agent
and can carry content from untrusted inputs; an allow verdict lets it reach
a shell and, for `mcp-bridge run`, lets an MCP server process receive the
`--args-json` value. That decision point is TB-1. task0001 declares `auth`
and `input-handling`, so TB-1 is analysed at deep depth.

Condition recorded for FR6: after this change the re-scan skip of S1 applies
only to the pair `--mcp notion` / `--tool notion-create-comment`. The skip
depends on assumption A1: the `notion-create-comment` tool of the `notion` MCP
server uses `--args-json` only as data and never runs it as a shell command.
Every other `--mcp` / `--tool` pair, and every form whose pair cannot be
determined, is re-scanned (TM-1, TM-2). If A1 stops holding for the server
registered as `notion`, a substitution inside the data word of that one pair
goes unscanned; this dependency is the accepted remainder of the allowed pair.

Categories with no row: Repudiation and Information disclosure (the change
adds no record and exposes no data); Denial of service (the pair check is one
pass over the words of one statement, and `scan_budget` and
`MAX_SHELL_PAYLOAD_EXPANSIONS` stay unchanged per NFR1). The case file
`em-workflow/hooks/tests/destructive-guard-cases.json` in task0001's files is
test data and is not a boundary file.

## Trust Boundaries

### TB-1: Agent-issued Bash command to destructive-guard verdict
Crossing: a Bash command string written by the agent crosses into
destructive-guard's static analysis; the verdict decides whether the shell
runs it and, for `mcp-bridge run`, whether an MCP server process receives the
`--args-json` value, which an argument-executing tool runs in a shell.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive command wrapped in a command substitution inside the single-quoted `--args-json` value of an `mcp-bridge run` that targets an argument-executing tool is skipped as data, so the guard allows a command it must deny (FR1, NFR2; SPEC.md TS-1) | TM-1 | S1 returns its data word only when both sides of the `notion` / `notion-create-comment` pair hold; another server, another tool, or a missing `--mcp` / `--tool` makes S1 return the empty set, so every candidate is re-scanned | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Spoofing | A command makes the guard read the target as `notion` / `notion-create-comment` while mcp-bridge receives a different server or tool, through a form the exact-word reading misjudges: a repeated flag, a quoted flag word or value, or a `--flag=value` word (FR1, NFR2, A2) | TM-2 | A side of the pair holds only when exactly one word after `run` equals the flag after quote removal or begins with the flag followed by `=`, that word is the flag written without quote or escape, and the next word is the expected value written as one unquoted run; every other form is undeterminable and re-scanned | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, item TM-2 |
