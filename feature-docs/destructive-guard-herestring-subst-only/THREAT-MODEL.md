# Threat Model: destructive-guard-herestring-subst-only

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR3, NFR1-NFR2) at the reduced tier; there is no
REQUIREMENTS.md or DESIGN.md. The one implementing task declares
`input-handling`, so the boundary it touches is analysed at deep depth.

destructive-guard is the PreToolUse gate between a Bash command string and
its execution. This feature changes only the guard's here-string branch.
The defect it fixes is a guard bypass: a crafted command line crashes the
hook, and the crash is non-blocking. That makes one boundary with one
applicable category. The crash of the guard is how the bypass happens, not
a separate denial-of-service threat, so it gets no row of its own.

`em-workflow/hooks/tests/destructive-guard-cases.json` is test data that only
the suite runner reads. It is not a boundary. Crash paths outside the
here-string branch are outside this feature's scope (NFR1). No mitigation is
recorded for them.

## Trust Boundaries

### TB-1: Bash command string into the destructive-guard PreToolUse hook
Crossing: the Bash tool's command text goes from the agent to the guard
hook, which decides allow / ask / deny before the shell runs it. The agent
writes the command text, and untrusted content in its context (files, task
text, tool output) can steer what it writes.
Boundary files: `em-workflow/hooks/destructive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A command line can aim a here-string at a shell word whose only remaining token is a substitution (`$()` or backtick spelling). This makes the here-string branch read past the end of the statement's word list. The uncaught error ends the hook with a non-blocking error exit. Every destructive statement later in the same command line then runs without the deny it would otherwise get (fail-open; FR1, FR2). | TM-1 | The here-string branch reads the candidate body word only when its index lies inside the word list. Otherwise it takes the existing fallback, which returns the here-string target token. The hook therefore completes and judges every later statement normally. Regression cases for both substitution spellings are in the expectation suite (FR3). | task0001 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification: TM-1 (via TS-1, TS-2) |
