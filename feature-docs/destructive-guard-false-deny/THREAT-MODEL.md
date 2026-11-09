# Threat Model: destructive-guard-false-deny

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR7, NFR1-NFR4) at the full
tier, the PreToolUse hook `em-workflow/hooks/destructive-guard.py` (the
chunk loop of `statements()` that queues substitution bodies for
re-scanning) and its case suite. The hook is the permission decision point
between a Bash command the agent proposes and the shell that runs it. The
agent's context can carry untrusted text, so the command string is
untrusted input. The feature narrows what the hook re-scans (FR2). It
leaves `check_git()`, `implement-phase.md` and the scan budgets unchanged
(FR1, NFR2).

task0001 declares `auth`, because the hook's output is a permission
decision, and `input-handling`, because the hook parses the command string.
TB-1 is therefore analysed at deep depth. FR1 changes no code and pins
existing behaviour with two cases, so it adds no threat. There is no Denial
of service row: the change only removes queued work, and the scan budgets
stay unchanged (NFR2). There is no Spoofing, Repudiation or Information
disclosure row: the hook reads only the command string and emits a
decision.

## Trust Boundaries

### TB-1: Agent-proposed Bash command to shell execution
Crossing: a Bash command string proposed by the agent, whose context can carry untrusted text (task descriptions, fetched documents, tool output), crosses into the destructive-guard PreToolUse hook, which decides whether the shell may run it.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | After the FR2 narrowing, the hook no longer re-scans a destructive command written inside a single-quoted substitution candidate of the top-level command. Another part of the same command can still make a shell or another program execute that text later: one of the FR4 paths, a wrapper, a path-qualified shell name, or an execution word outside the minimum vocabulary. The command then runs with no deny (FR2, FR4). | TM-1 | The hook leaves a candidate's body unqueued only in the top-level chunk, and only when every FR2 condition (a)-(d) is decided true. Any condition it cannot decide makes it re-scan as before. The execution-word test reads the command word after the existing assignment and wrapper skip and compares the word's last path segment. Its vocabulary covers at least FR2 (c). Deny cases pin each FR4 path, each execution word beyond bash, sh and eval, and each fail-closed condition. | task0001 AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | The narrowing removes single-quote candidates from the marked span list instead of only from the queue. Tokens then lose their unresolved / substitution-only flags, and the hook judges an `rm` whose target came from substitution text as a resolved target (FR3). | TM-2 | The change leaves unchanged the top-level span computation, both marking passes, the run-global substitution list and its marker indices, and the per-token flags. Only queueing differs. The FR3 example cases stay in the suite with unchanged expected decisions. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
