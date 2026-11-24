# Threat Model: env-route-partial-overrun-check

## Verdict
threats-identified

## Rationale
Inspected: the Bash command string that reaches destructive-guard's PreToolUse
decision and travels its env route (a notion / mcp-bridge call lifted from an
environment assignment, read once per extglob reading). The feature is a
security fix to that decision path (REQUIREMENTS.md 1.1, SPEC.md Security
Considerations). Tier: full. Task task0001 declares `input-handling`, so the
one boundary found is analysed at deep depth. No task declares `auth`,
`external-io` or `data-persistence`.

The verdict holds because the command string is attacker-influenceable (the
agent that issues it can be steered by untrusted content), and the change both
closes a deny bypass and adds new rescan work and a new branch next to the
lexer-state restore. Each realistic way the changed decision can be broken is
recorded below.

The test files of task0001 (`em-workflow/hooks/tests/destructive-guard-cases.json`,
`tests/test_destructive_guard_env_route.py`) are not boundary files: they only
exercise the boundary and take no input from outside the project. Task0001's
boundary file, `em-workflow/hooks/destructive-guard.py`, appears in TB-1.

## Trust Boundaries

### TB-1: Agent-issued Bash command into destructive-guard's env-route decision
Crossing: a Bash command string proposed by the agent (attacker-influenceable
through untrusted content the agent has read) crosses into the hook, whose
deny / ask / allow decision gates whether the command runs with the user's
privileges. On this route the string carries an environment-assignment body
whose two extglob readings each decode notion pairs (body and command).
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A body crafted so that only one extglob reading overruns makes the env-route statement queue nothing; the destructive command decoded by the in-limit reading is never rescanned, and the decision stays at the scan-budget ask, which an interactive user can approve (FR1, FR3; SPEC.md AC-1) | TM-1 | When exactly one of two readings overruns, the in-limit reading's bodies and commands are queued for rescan, the scan-budget ask is still held, and a deny produced by the rescan wins over every held ask through the existing settle mechanism | task0001 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-3) |
| Elevation of privilege | When the readings are de-duplicated together, the overrun reading's items can shadow equal strings of the in-limit reading; arranging for the overrun reading to be read first gets the in-limit item dropped as a duplicate and never queued (FR4, FR5) | TM-2 | De-duplication and charge are computed over the in-limit reading only; the overrun reading's items are never queued and never take part in the comparison, whatever the read order | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3) |
| Denial of service | Queuing the in-limit reading's items under an already-raised overrun adds rescan work, so a body whose in-limit reading decodes a large amount of text can push the hook past its scan budget (FR6) | TM-3 | The in-limit items' charge is added to the scan budget before anything is queued; when it would exceed the budget, nothing is queued and the scan-budget ask is held | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-5) |
| Elevation of privilege | Restructuring the per-reading combine leaks the lexer states out of the env route, so later statements of the same command are parsed under the wrong extglob setting and a destructive command in them can be misread (NFR5) | TM-4 | The env route restores the three lexer states to their entry values on every exit path, the new one-sided-overrun branch included, and records no extglob unit | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-3, TS-6) |
