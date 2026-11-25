# Threat Model: env-route-unreadable-heredoc-ask

## Verdict
threats-identified

## Rationale

Inspected at the reduced tier (no REQUIREMENTS.md, no DESIGN.md): SPEC.md,
the env route of `em-workflow/hooks/destructive-guard.py` (the payload's map,
the payload chunk, the body reading under each extglob setting, the tail rule,
the combination of the readings and the deferred asks), the decision-case file,
the env-route unit tests, and the findings of review round 1.

The feature's one input is the command string of a Bash tool call that the
PreToolUse hook receives. An agent writes that string, and the agent's context
can hold attacker-influenced text. The hook's verdict decides whether the
command runs without a human confirmation; under claude-batch an ask becomes a
deny. This is one trust boundary (TB-1). task0001 and task0002 declare
`input-handling`, so TB-1 is analysed at deep depth.

Elevation of privilege and Tampering apply: a crafted command can make the
guard allow a destructive `--args-json` command that it should confirm. Denial
of service applies: a rule broader than FR1 turns benign env-route bodies into
asks, and an ask stops an unattended run. Spoofing, Repudiation and
Information disclosure do not apply: the hook authenticates no party, this
feature changes no record of decisions, and the hook discloses nothing beyond
its verdict and reason.

Outside this feature's scope and not mitigated here: an env-route payload whose
map the lexer cannot give at all has an empty reading (IMPLEMENTATION.md D5; a
separate follow-up task), and a name that becomes `mcp-bridge` only after
expansion is not matched (SPEC.md A3).

## Trust Boundaries

### TB-1: Agent-issued Bash command to the destructive-guard verdict (env route)
Crossing: the command string of a Bash tool call, from the agent (whose input may carry attacker-influenced text) to the PreToolUse hook, whose allow / ask / deny decides whether the command runs unconfirmed; specifically the `bash -c` payload that the env route reads when `env` is written as a path or with a lone `-`.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A notion-pair `mcp-bridge run --args-json` call placed after a here-document whose delimiter word cannot be read is not inspected by the env route, and the flags that the payload's lexing raised are restored, so the command is allowed without confirmation (SPEC.md Overview, FR1, FR3) | TM-1 | When the payload's map is unreadable and its raw tail holds the `mcp-bridge` word, the reading is unrestorable and the command gets the `args-json-unrestorable` ask (deny in batch), whatever the pair kind or the lifting (A1, A2) | task0001 AC-1, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Tampering | The command word in the tail is split with quotes or with a line continuation, so that a literal match of `mcp-bridge` fails (FR1 (a)) | TM-2 | Before the word is matched, the tail's line continuations are removed, then its `'`, `"` and `\` characters, in that fixed order | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Tampering | The command word is written in ANSI-C quoting (for example `$'\x6dcp-bridge'`), so that no literal form of the word appears (FR1 (b)) | TM-3 | Any `$'` in the tail makes the reading unrestorable | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-3 |
| Elevation of privilege | The payload is read under both extglob settings, and only one reading meets the unreadable tail with the word; the other reading's clean result could stand for the payload (FR2) | TM-4 | The Unrestorable flags of the readings are combined with OR, so one reading is enough | task0001 AC-5; task0002 AC-4 | VERIFICATION.md, Performance / Security Verification, TM-4 |
| Denial of service | A rule broader than FR1, or a leak into run() of the flags the payload's lexing raises, turns benign env-route bodies (an unreadable here-document alone, `mcp-bridge` only before the `<<`, a `$` that no quote character directly follows, or a body the lexer cannot settle that meets neither condition) into asks that stop unattended runs (FR1, FR3, NFR1) | TM-5 | The new ask needs both an unreadable map and condition (a) or (b) on the tail; the flag save and restore is unchanged; no path outside the env route changes; no exception caught before is propagated | task0001 AC-3, AC-6; task0002 AC-2, AC-4, AC-5, AC-7 | VERIFICATION.md, Performance / Security Verification, TM-5 |
| Tampering | The command word is split with a locale quote (for example `mcp-$"bridge"`), so that removing the quote characters leaves the `$` inside the word and the literal match fails (FR1 (b)) | TM-6 | Any `$"` in the tail makes the reading unrestorable | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-6 |
| Tampering | A line continuation is put between the `$` and the quote character of an ANSI-C or locale quote, so that neither `$'` nor `$"` appears in the raw tail (FR1 (b)) | TM-7 | The tail's line continuations are removed before `$'` and `$"` are looked for | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-7 |
| Elevation of privilege | The payload's map shows an unreadable tail that meets (a) or (b), but the payload also makes a later step of the chunk build fail; the empty reading then drops the rule's answer and the command is allowed (FR1) | TM-8 | The rule is evaluated on the map, and its answer is kept in the reading when the chunk is not built | task0002 AC-4, AC-6 | VERIFICATION.md, Performance / Security Verification, TM-8 |
