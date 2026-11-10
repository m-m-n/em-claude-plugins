# Threat Model: destructive-guard-heredoc-yaml-repro-case

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR4, NFR1-NFR3, assumptions A1-A3) at the reduced
tier (no REQUIREMENTS.md; the design step was skipped). The feature's only
input is the Bash command string that `em-workflow/hooks/destructive-guard.py`
judges before the shell runs it. The feature adds an allow case and a contrast
deny case to the guard's expectation suite and, only when the allow case fails
against the current guard, narrows how the guard reads the body of a
quoted-delimiter heredoc that cat writes to a file (FR2). task0001 declares
`input-handling`, so the boundary is analysed at deep depth; its other domain,
`config-infra`, does not change the analysis.

The expectation suite file is project test data and not a boundary of its own;
it is listed under TB-1 because it pins the guard's verdicts at that boundary.
An installed copy of the hook in the plugin cache (the suspected origin of the
reported deny, SPEC assumption A1) is outside this feature's change set and is
not modelled. The verdict holds because widening the heredoc-body exclusion
can let a command that the shell actually executes pass the guard (TB-1).

## Trust Boundaries

### TB-1: Bash command string to the destructive-guard verdict
Crossing: a Bash command string composed by the agent, whose text can be
steered by untrusted content the agent has read, crosses into
destructive-guard.py, which returns allow, ask or deny before the shell runs
the command.
Boundary files: em-workflow/hooks/destructive-guard.py, em-workflow/hooks/tests/destructive-guard-cases.json
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A guard change made for FR2 treats lines after the heredoc terminator line as body text, so a real `git reset --hard` placed after the reproduction's terminator line passes the guard (FR2, FR3). | TM-1 | Only the lines strictly between the heredoc operator line and its terminator line are excluded from command reading; lines after the terminator stay judged as commands. The FR3 contrast case pins this as a deny carrying the `git-reset-hard` rule tag. | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification: TM-1 (via TS-2) |
| Elevation of privilege | A guard change made for FR2 extends the body exclusion to heredocs whose body the shell does execute: a body fed to an interpreter (a pipe into bash, python3, sh) or a body under an unquoted delimiter whose command substitutions bash runs. A destructive command in such a body would then pass the guard (FR2, FR4, A2, A3). | TM-2 | The body exclusion applies only when the delimiter is quoted and the destination is cat redirecting to a file. Every existing deny / ask case, including the interpreter-fed heredoc cases and the unquoted-delimiter substitution cases, is kept unchanged and passes. | task0001 AC-4, AC-5 | VERIFICATION.md, Performance / Security Verification: TM-2 (via TS-3) |
