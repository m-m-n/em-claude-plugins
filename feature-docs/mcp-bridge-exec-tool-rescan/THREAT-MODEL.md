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

TM-2 also depends on mcp-bridge `run` parsing its options as decision D1 of
IMPLEMENTATION.md records (single-dash and double-dash forms, the `=` form,
the last occurrence winning, and option parsing stopping at `--` or at the
first positional word). The set of undeterminable forms TM-2 re-scans is
wider than the list in SPEC.md A2: it is every form outside the complete
flag sequence of D1. This is the plan's reading of FR1's undeterminable
clause and of NFR2; SPEC.md is not rewritten in this run.

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
| Spoofing | A command makes the guard read the target as `notion` / `notion-create-comment` while mcp-bridge receives another server or tool, through a form a word-by-word reading misjudges: a repeated flag, a quoted flag word or value, an `=` form, a single-dash flag whose last occurrence wins, or a notion pair placed after `--` or after a positional word, where mcp-bridge has stopped reading options (FR1, NFR2, A2) | TM-2 | The pair is determined only when the words after `run` read as a complete sequence of the known `run` flags in the exact double-dash form, each value-taking flag followed by its value word and `--dry-run` alone, with `--mcp`, `--tool` and `--args-json` each exactly once and no `--`, positional word, single-dash form or `=` form (IMPLEMENTATION.md D1); every other form is undeterminable and re-scanned | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, item TM-2 |
