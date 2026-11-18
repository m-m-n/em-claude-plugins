# Threat Model: mixed-rm-self-config-deny

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, the exclusion step of `main()` in `em-workflow/hooks/destructive-guard.py` on both rm routes (plain and substitution-headed), `rm_operands_name_self_config()`, the operand numbering `check_rm()` uses, the case table and `.claude/rules/hook-tests.md`. Tier: full. Domains: task0001 declares `input-handling` (the hook parses command text it receives), which sets TB-1 to deep; task0002 declares `config-infra` only and changes a rule document that no decision path reads, so it touches no trust boundary.

The feature changes how the hook decides on the command string of a Bash PreToolUse payload. That string is written by the agent session and can be shaped by untrusted content the session has read; the hook's verdict decides whether the command runs and what the user is asked to approve. That crossing is the one trust boundary (TB-1).

Residual, out of scope (SPEC.md A2, REQUIREMENTS.md 1.3): an operand whose raw form matches the protected pattern but resolves outside it (`~/.claude/skills/../../valuable`) is still left out of the pool. This feature records no mitigation for it.

Not recorded as a threat: the protected set per target is computed by the same single pass over the operands as today's per-invocation test (NFR4), so no new denial-of-service surface appears. The amended SPEC.md of destructive-guard-mixed-rm-precedence and the rule document are inputs of no decision.

## Trust Boundaries

### TB-1: Bash command text into the destructive-guard verdict
Crossing: the command string of a Bash PreToolUse payload, written by the agent session (possibly shaped by untrusted content), crosses into the hook; the hook's verdict (allow / ask / deny, then the CLAUDE_BATCH demotion) decides whether the command runs and what the user is asked to approve.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | One rm lists a protected self-config operand beside a recursive-delete target the hook denies (or a root / home target). Because the exclusion drops every record of that rm, only the self-modification ask is shown, and approving it also runs the unprotected delete; under CLAUDE_BATCH the reason names self-modification instead of the delete (REQUIREMENTS.md 1.1; SPEC.md FR1, FR3) | TM-1 | The exclusion works per target: only the records of the operands in the protected set are left out, the records of the other targets of the same rm join the pool, and a deny among them wins in the resolution step before any demotion, with a reason built from the winning targets alone | task0001 AC-1, AC-2 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | The protected set and the records are numbered on different operand bases or by different rules (the `--` rule, operator tokens, dash-leading operands, the remainder of a substitution-headed statement), so the exclusion removes the record of a target the hook denies instead of the protected operand's record (SPEC.md FR1, FR2) | TM-2 | The protected set is computed on the same operand basis `check_rm()` received for that invocation and numbered by the same operand numbering, on both routes; the protected-path test stays "raw form or normalized form matches" | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-2 |
