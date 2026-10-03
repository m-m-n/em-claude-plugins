# Threat Model: destructive-guard-heredoc-sink-gaps

## Verdict
threats-identified

## Rationale

**Inspected.** SPEC.md and REQUIREMENTS.md (FR1-FR10, NFR1-NFR4, A6, A7) at
tier full. The design step was skipped.

**The boundary.** The feature changes `em-workflow/hooks/destructive-guard.py`.
This PreToolUse hook statically judges the Bash command string an agent is
about to run, and returns allow, ask or deny. The agent writes the command
string, and untrusted content the agent has read can shape it. That makes
the hook's input a trust boundary. The analysis depth is deep because every
task declares `input-handling`.

**Outside the boundary.**

- The test runner (`em-workflow/hooks/tests/run-destructive-guard.py`) and
  the case file (`em-workflow/hooks/tests/destructive-guard-cases.json`) are
  repository-internal test assets that run only on repository-controlled
  data. They cross no trust boundary.
- task0001 also declares `config-infra` for the runner. That is not one of
  the four depth-setting domains.

**Domain consistency check.** Every task declares `input-handling` and lists
`em-workflow/hooks/destructive-guard.py`, the TB-1 boundary file.

**STRIDE categories with no row.**

- Spoofing: the hook authenticates no party.
- Repudiation: the hook keeps no audit record.
- Information disclosure: the hook reads no file and no secret (NFR1).

**Accepted residual risk.** SPEC.md Security Considerations records A6
(override target path with no sink name). It carries no mitigation here.

## Trust Boundaries

### TB-1: Agent-issued Bash command string to the destructive-guard judgment
Crossing: the command string of a Bash tool call goes from the agent to the hook. Untrusted content the agent has read can shape that string. The hook decides whether the command runs without confirmation.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive heredoc body sent to a shell is judged data, so it runs without ask or deny. Cause: host-statement boundaries differ from lex_segments() at redirections and escapes, or the selected host statement lacks the heredoc's own operator (FR1, FR2; cdb8382d4bbb0b1d) | TM-1 | The host statement is the lex_segments() statement that contains the operator. A host statement without the heredoc's own operator yields undetermined, never data | task0002 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | An escaped quote read as a quote start hides statement separators, so a shell-bound heredoc is misjudged (FR3, FR2; 73a1d7b31734dd22) | TM-2 | scan_structure(), including its case/esac word reading, treats escaped quotes as literal characters | task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Elevation of privilege | A fake heredoc operator inside quotes or a comment takes the following real command lines as its body, hiding destructive commands (FR5; 18b99bd71e74c8dc) | TM-3 | Operators are recognized only in operator context, with substitutions excepted. Following lines stay in place. Quote and comment state is tracked across lines, and real bodies are left out of the tracking | task0003 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Elevation of privilege | A sink named in a skipped word or through env split-string runs the heredoc in a shell, while the trailing command name leads to a data judgment (FR6; 511cd470522973d8) | TM-4 | A sink in any skipped word, as written or with quotes removed, and every env split-string spelling yield undetermined | task0004 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Elevation of privilege | A function definition, alias, hash, enable or PATH assignment in the same command replaces a data command with a shell, so its heredoc body is executed (FR7; b8fd289ca7750a04) | TM-5 | Any override construct in the command makes every data judgment in that command undetermined | task0004 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |
| Denial of service | Many single-quoted `$(` make the matching quadratic. The judgment exceeds the 10-second hook timeout and is lost, so the destructive command in the same input is not stopped (FR4, FR10, NFR3; 26ab9a3d83649eff) | TM-6 | Single-quoted `$(` matching is linear and its results are unchanged. The runner bounds every evaluation at 10 seconds and counts an overrun as FAIL | task0001 AC-1, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-6 |
| Denial of service | A fix that widens undetermined or command re-reading turns legitimate commands into ask. Unattended runs demote ask to deny, which stops the run (FR9; REQUIREMENTS.md 11.1 AC-2, AC-6) | TM-7 | Changes only move data to undetermined. The fallback rescans only when its chunk holds a sink word. Allow cases are added for the reverse direction. Every pre-existing case is kept and passes | task0001 AC-7; task0002 AC-2, AC-6; task0003 AC-2, AC-3, AC-6; task0004 AC-3, AC-7 | VERIFICATION.md Performance / Security Verification, TM-7 |
