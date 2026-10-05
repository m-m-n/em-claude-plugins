# Threat Model: destructive-guard-unified-lexer

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md and the change target em-workflow/hooks/destructive-guard.py at the full tier. The hook is a PreToolUse security control. It statically reads Bash command text written by the agent, and that text can carry content from untrusted sources (repository files, tool output, injected instructions). From that reading it returns allow, ask or deny before execution, including in unattended batch runs, where ask is demoted to deny. This feature rewrites how that text is lexed, so the boundary between untrusted command text and the guard's decision is directly in scope. task0001 declares `input-handling`, which sets this boundary to deep analysis.

No new boundary is introduced. The feature adds no file access, network access, evaluation (NFR1) or dependency (NFR2). The cases file and the agreement test are test fixtures, not runtime inputs. Spoofing, Repudiation and Information disclosure do not realistically apply at TB-1: the hook authenticates no party, this feature touches no audit record, and the decision message goes back to the same session that sent the command.

## Trust Boundaries

### TB-1: Agent-generated Bash command text into the destructive-guard decision
Crossing: a Bash command string produced by the agent, possibly shaped by untrusted content, passes into destructive-guard.py's static analysis, which returns the decision that gates its execution.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Quoting or expansion syntax (`$'...'`, `${...}`, `$((...))`, `((...))`, `$[...]`, or an opener that never closes) is read differently from bash. A following destructive statement then hides inside a misread quote, comment, swallowed separator or heredoc body, and the hook allows it without confirmation (FR1, FR2, FR3, FR5, FR6) | TM-1 | One single-pass lexer is the only source of quote, comment and expansion ranges and reads these contexts as bash does; an opener that never closes is read as not opened (SPEC A3) | task0001 AC-1, AC-3 | VERIFICATION.md TM-1 |
| Elevation of privilege | Once `${...}` and arithmetic become inert for separators and operators, a `$(...)` or backtick written inside them is no longer extracted, so the destructive command it runs is never checked (FR4, FR9) | TM-2 | Substitution regions nested in parameter-expansion and arithmetic regions are still reported as spans and queued for scanning; the three substitution-search policies stay distinct | task0001 AC-1, AC-5 | VERIFICATION.md TM-2 |
| Elevation of privilege | Characters inside a real heredoc body drive quote or comment state, or a body is attributed to the wrong host statement, so a sink-bound body is treated as data (FR8) | TM-3 | Real heredoc body lines change no lexer state; positions are mapped between the original, body-stripped and marker-inserted text so each body belongs to the statement holding its operator | task0001 AC-5 | VERIFICATION.md TM-3 |
| Elevation of privilege | Characters rewritten only to feed shlex leak into the values the checks read, or Tok provenance flags stop matching the original input, so a destructive target is inspected as different text (FR7) | TM-4 | The masked view only guides token positions; values are restored from the original characters by position, and is_operator / quoted / unresolved follow the original input | task0001 AC-4 | VERIFICATION.md TM-4 |
| Denial of service | The lexer change misreads benign commands as deny or ask; under unattended runs ask becomes deny and the run stops (FR12, SPEC A2) | TM-5 | Every existing case keeps its position and expected verdict, allow cases included, and benign controls run through the agreement test | task0001 AC-2 | VERIFICATION.md TM-5 |
| Denial of service | A long crafted input, such as many openers that never close, makes lexing super-linear, so the hook gives no decision within the 10-second hooks.json timeout (NFR3) | TM-6 | Lexing, including settling unclosed openers, stays linear in input length; past its bound the hook issues the existing scan-budget ask decision, never allow | task0001 AC-6 | VERIFICATION.md TM-6 |
