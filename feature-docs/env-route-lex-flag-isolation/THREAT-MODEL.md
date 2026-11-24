# Threat Model: env-route-lex-flag-isolation

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier reduced; REQUIREMENTS.md and the design step are absent by tier). The feature changes how destructive-guard, a PreToolUse guard, reads the body of a `bash -c` command reached through env. The command string reaches the guard from the agent's Bash tool call, which untrusted content in the agent's context can influence, and an allow decision lets the command run without user approval. The one task, task0001, declares `input-handling`, which sets TB-1's depth to deep; its production file is TB-1's boundary file, and its other two files (the decision-case table and a unit test module) are test inputs that carry nothing across a boundary. The threats below are the ways the change itself could widen what the guard allows. The false-positive deny the feature removes is the feature's objective (SPEC.md Objectives), not a threat.

## Trust Boundaries

### TB-1: Bash tool command string into the destructive-guard decision
Crossing: a command string composed by the agent, which untrusted content can influence, crosses into the guard; the guard lexes it and returns allow / ask / deny, and allow lets the command run without approval.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Restoring the flags to a fixed false value after the env-route reading clears an unreadable-delimiter flag raised earlier outside the env route, so a command that pairs an env-route statement with a heredoc whose delimiter cannot be read runs without the ask it gets today (FR1, NFR1). | TM-1 | Each flag is restored to the value it held at entry to the env-route reading, never to a fixed value. | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-4) |
| Elevation of privilege | Today the extglob-met flag leaked by the env-route reading makes `run()` re-read the whole command with extglob on, which incidentally catches a notion pair visible only under that reading. Confining the flags removes that re-read, so a destructive notion-pair call placed after an extended-pattern line in an env-route body is allowed (FR3; SPEC.md AC-3). | TM-2 | When the first reading meets an extended-pattern parenthesis, the env route reads the body under both extglob settings and checks the notion pairs found by either reading. | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-6) |
| Elevation of privilege | The extglob setting switched for the second reading stays switched after the env route (on a normal exit or when an exception propagates), so the rest of the command is lexed under the other setting, where a statement the original setting shows can be discarded as a syntax error (FR2, FR3). | TM-3 | The extglob setting is put back to its entry value on every exit from the env-route reading, exceptions included. | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-8) |
| Elevation of privilege | With two readings, an overrun or unrestorable signal raised by only one of them is dropped, so a body that was not fully read is treated as fully inspected (FR4). | TM-4 | Overrun and unrestorable are reported when either reading raises them. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-9) |
