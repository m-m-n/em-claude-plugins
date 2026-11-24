# Threat Model: env-route-unreadable-heredoc-ask

## Verdict
threats-identified

## Rationale

Inspected at the reduced tier (no REQUIREMENTS.md, no DESIGN.md): SPEC.md,
the env route of `em-workflow/hooks/destructive-guard.py` (the payload chunk,
the body reading under each extglob setting, the combination of the readings
and the deferred asks), the decision-case file and the existing env-route unit
tests.

The feature's one input is the command string of a Bash tool call that the
PreToolUse hook receives. An agent writes that string, and the agent's context
can hold attacker-influenced text. The hook's verdict decides whether the
command runs without a human confirmation; under claude-batch an ask becomes a
deny. This is one trust boundary (TB-1). task0001 declares `input-handling`,
so TB-1 is analysed at deep depth.

Elevation of privilege and Tampering apply: a crafted command can make the
guard allow a destructive `--args-json` command that it should confirm. Denial
of service applies: a rule broader than FR1 turns benign env-route bodies into
asks, and an ask stops an unattended run. Spoofing, Repudiation and
Information disclosure do not apply: the hook authenticates no party, this
feature changes no record of decisions, and the hook discloses nothing beyond
its verdict and reason.

Outside this feature's scope and not mitigated here: an env-route payload that
the lexer cannot settle within its bounds gives an empty reading
(IMPLEMENTATION.md, Open Questions).

## Trust Boundaries

### TB-1: Agent-issued Bash command to the destructive-guard verdict (env route)
Crossing: the command string of a Bash tool call, from the agent (whose input may carry attacker-influenced text) to the PreToolUse hook, whose allow / ask / deny decides whether the command runs unconfirmed; specifically the `bash -c` payload that the env route reads when `env` is written as a path or with a lone `-`.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A notion-pair `mcp-bridge run --args-json` call placed after a here-document whose delimiter word cannot be read is not inspected by the env route, and the flags that the payload's lexing raised are restored, so the command is allowed without confirmation (SPEC.md Overview, FR1, FR3) | TM-1 | When the payload's map is unreadable and its raw tail holds the `mcp-bridge` word, the reading is unrestorable and the command gets the `args-json-unrestorable` ask (deny in batch), whatever the pair kind or the lifting (A1, A2) | task0001 AC-1, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Tampering | The command word in the tail is split with quotes or with a line continuation, so that a literal match of `mcp-bridge` fails (FR1 (a)) | TM-2 | Before matching, the tail's line continuations are removed, then its `'`, `"` and `\` characters, in that fixed order | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Tampering | The command word is written in ANSI-C quoting (for example `$'\x6dcp-bridge'`), so that no literal form of the word appears (FR1 (b)) | TM-3 | Any `$'` in the tail makes the reading unrestorable | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-3 |
| Elevation of privilege | The payload is read under both extglob settings, and only one reading meets the unreadable tail with the word; the other reading's clean result could stand for the payload (FR2) | TM-4 | The Unrestorable flags of the readings are combined with OR, so one reading is enough | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification, TM-4 |
| Denial of service | A rule broader than FR1, or a leak into run() of the flags the payload's lexing raises, turns benign env-route bodies (an unreadable here-document alone, or `mcp-bridge` only before the `<<`) into asks that stop unattended runs (FR1, FR3, NFR1) | TM-5 | The new ask needs both an unreadable map and condition (a) or (b) on the tail; the flag save and restore is unchanged; no path outside the env route changes | task0001 AC-3, AC-6 | VERIFICATION.md, Performance / Security Verification, TM-5 |
