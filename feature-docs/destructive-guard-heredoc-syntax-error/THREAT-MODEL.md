# Threat Model: destructive-guard-heredoc-syntax-error

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and workflow.yaml (tier `reduced`; REQUIREMENTS.md and
DESIGN.md are intentionally absent). The feature changes how the
destructive-guard PreToolUse hook lexes Bash command text before deciding
allow / ask / deny. That command text is produced by the agent and can be
steered by untrusted content the agent has read, and the hook's verdict is
the only gate between it and execution without confirmation (in batch runs
an ask is demoted to deny, so a wrong allow is never caught by a human).
The single task declares the `input-handling` domain, so the boundary is
analysed at deep depth. Threats below cover the bypass this feature closes,
a bypass the change itself could open, and the availability risks the
change introduces (over-suppression halting unattended runs, lexer work
growth). The task's files are `em-workflow/hooks/destructive-guard.py`
(listed as the boundary file) and
`em-workflow/hooks/tests/destructive-guard-cases.json` (the verification
table for that boundary, not a boundary itself).

## Trust Boundaries

### TB-1: Agent-issued Bash command text into the destructive-guard verdict
Crossing: a Bash command string from the agent's tool call (LLM output,
influenceable by untrusted content) crosses into the PreToolUse hook; the
hook's verdict decides whether the shell runs it without human
confirmation.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A command writes `<<` directly inside an array compound assignment; the guard reads the following lines as heredoc body and returns allow, while bash discards that line and runs the following destructive lines without confirmation (FR1, FR3) | TM-1 | lex_shell() / _lex_pass() do not register a heredoc operator for `<<` / `<<-` at direct position inside an array compound-assignment parenthesis, so the following lines are classified as commands | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Elevation of privilege | The same bypass through a heredoc operator registered on the discarded line before the array (e.g. `cat <<'A'; x=( <<B`), whose body would hide the following lines (FR2) | TM-2 | No heredoc operator registered on the discarded line takes a body | task0001 AC-3 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Elevation of privilege | The lexer change turns a form that the existing case table holds at deny or ask into allow, opening a new bypass (FR6, NFR3) | TM-3 | The case table only gains entries, the deny + ask count does not decrease, and the full case table and unittest suite pass in the same change | task0001 AC-6 | VERIFICATION.md Performance / Security Verification: TM-3 |
| Denial of service | Over-broad suppression (an ancestor array alone suppressing registration, or array state never cleared) makes legitimate heredoc bodies classified as commands, so ask / deny halts unattended runs (FR3, FR4) | TM-4 | Suppression applies only at direct position; all lexical context is cleared at the end of the discarded line; the FR4 allow forms and the post-reset heredoc form are pinned as allow cases | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification: TM-4 |
| Denial of service | Crafted input (many pending heredoc operators, repeated discarded lines) drives the added tracking or cancellation past the lexer work bound or the hook time limit (NFR2) | TM-5 | Tracking and cancellation stay inside the single left-to-right pass without re-reading earlier input; the existing work bound and its scan-budget ask are kept | task0001 AC-7 | VERIFICATION.md Performance / Security Verification: TM-5 |
