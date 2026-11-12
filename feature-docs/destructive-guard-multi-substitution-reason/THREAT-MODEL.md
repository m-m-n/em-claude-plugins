# Threat Model: destructive-guard-multi-substitution-reason

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`; no REQUIREMENTS.md, no DESIGN.md), the hook the
feature exercises (`em-workflow/hooks/destructive-guard.py`, changed only under FR6)
and the new regression test module. The hook reads a Bash command string from a
PreToolUse payload. An agent writes that string, and it can carry text that came from
untrusted sources. The hook returns a decision and a reason text that an agent or a
human operator reads. That crossing is the one trust boundary, TB-1. Its depth is deep
because task0001 declares `input-handling`.

Two STRIDE categories realistically apply at TB-1: Spoofing, through substitution body
text reflected into the guard's reason text (FR1, FR11, SPEC.md Security
Considerations), and Elevation of privilege, through a hook change made under FR6 that
alters the decision for multi-substitution targets. Information disclosure was
considered and is not recorded: a substitution body is literal text of a command its
reader already sees, and the hook never expands it. Tampering, Repudiation and Denial
of service have no realistic path here: the feature adds no input, no output channel
and no processing beyond the existing reason rendering.

The new test module `tests/test_destructive_guard_multi_substitution_reason.py` runs
only fixed inputs in the developer's test environment, so it is not a boundary.

## Trust Boundaries

### TB-1: Bash command string to destructive-guard decision and reason text
Crossing: a Bash command string in a PreToolUse payload enters the hook from the agent
that wrote it, including the bodies of command, backtick and process substitutions,
which can carry text from untrusted sources; the hook's decision and reason text go
back to that agent and to the human operator.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Text inside a substitution body (instruction-shaped text, or a forged positional designation) is echoed into the reason text and reaches the reader as guard-authored text, misleading the reader about which target was flagged (FR1, FR11, US1) | TM-1 | A substitution-only target is rendered only as its positional designation with the fixed stand-in `$(...)`; no substitution body text appears in the reason text, and regression tests with distinct bodies pin this | task0001 AC-2, AC-6 | VERIFICATION.md, Performance / Security Verification, item TM-1 (TS-1, TS-9) |
| Elevation of privilege | A hook change made under FR6 to fix the reason rendering (for example in the name-based de-duplication of rm records) alters the decision, so a recursive delete with unresolvable substitution targets runs without confirmation (FR1, FR3, FR6, FR7 to FR11) | TM-2 | Regression tests pin the decision ask (deny under CLAUDE_BATCH) and the reason ID rm-unresolvable for every multi-substitution case; the hook changes only when a new test fails on the unmodified hook, and both existing suites still pass unchanged | task0001 AC-2, AC-4, AC-5, AC-6, AC-7 | VERIFICATION.md, Performance / Security Verification, item TM-2 (TS-1, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10) |
