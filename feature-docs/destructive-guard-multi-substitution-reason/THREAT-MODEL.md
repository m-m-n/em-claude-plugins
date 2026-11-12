# Threat Model: destructive-guard-multi-substitution-reason

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md as revised for FR12 (tier `reduced`; no REQUIREMENTS.md, no
DESIGN.md), the hook the feature exercises (`em-workflow/hooks/destructive-guard.py`,
changed only under FR6), the regression test module task0001 added, and the change
task0002 makes to the case selection of
`tests/test_destructive_guard_mixed_rm_precedence.py`. The hook reads a Bash command
string from a PreToolUse payload. An agent writes that string, and it can carry text
that came from untrusted sources. The hook returns a decision and a reason text that an
agent or a human operator reads. That crossing is the one trust boundary, TB-1. Its
depth is deep because task0001 declares `input-handling`.

Three threats realistically apply at TB-1, in two STRIDE categories. Spoofing: substitution
body text reflected into the guard's reason text (FR1, FR11, SPEC.md Security
Considerations). Elevation of privilege, twice: a hook change made under FR6 that alters
the decision for multi-substitution targets, and the FR12 change to the
mixed-rm-precedence test's case selection, which could take recorded precedence cases
out of the run against the hook so that a precedence regression at TB-1 passes the
suite unnoticed. Information disclosure was considered and is not recorded: a
substitution body is literal text of a command its reader already sees, and the hook
never expands it. Tampering, Repudiation and Denial of service have no realistic path
here: the feature adds no input, no output channel and no processing beyond the existing
reason rendering.

The two test modules — the new module of task0001 and the mixed-rm-precedence module
task0002 changes — run only fixed inputs (the commands they hold and the repository's
case table) in the developer's test environment, so neither is a boundary. task0002
declares no domain.

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
| Elevation of privilege | A hook change made under FR6 to fix the reason rendering (for example in the name-based de-duplication of rm records) alters the decision, so a recursive delete with unresolvable substitution targets runs without confirmation (FR1, FR3, FR6, FR7 to FR11) | TM-2 | Regression tests pin the decision ask (deny under CLAUDE_BATCH) and the reason ID rm-unresolvable for every multi-substitution case; the hook changes only when a new test fails on the unmodified hook; both existing suites pass, with every existing test unchanged except FR12's change to the mixed-rm-precedence module | task0001 AC-2, AC-4, AC-5, AC-6, AC-7; task0002 AC-5 | VERIFICATION.md, Performance / Security Verification, item TM-2 (TS-1, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10) |
| Elevation of privilege | The FR12 change to how the mixed-rm-precedence module selects its own cases drops or moves recorded precedence cases (for example a label match that selects fewer cases than the table holds), so a regression in the decision precedence those cases pin — a recursive-delete deny no longer outranking another check's ask — passes the suite unnoticed (FR12, FR4) | TM-3 | The module selects its cases by the feature name followed by one space; TestCaseTable checks that the selected cases are a non-empty contiguous run starting at position PRE_EXISTING_CASE_COUNT; PRE_EXISTING_CASE_COUNT, PRE_EXISTING_CASES_DIGEST, each scenario's expected count and the case table stay unchanged | task0002 AC-2, AC-4 | VERIFICATION.md, Performance / Security Verification, item TM-3 (TS-12) |
