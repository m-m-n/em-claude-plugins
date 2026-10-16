# Threat Model: codex-guard-anon-stdin-args

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at tier `full`. The one task, task0001,
declares the `input-handling` domain, which sets TB-1 to deep depth. The
feature changes how codex-hook-interactive-guard parses the shell command
string it receives as hook input. That string is written by Codex, an LLM
agent whose output can be steered by repository content, so it is untrusted
input entering the guard. The guard only analyzes the string statically and
executes nothing (NFR3), so Spoofing, Tampering, Repudiation, Information
disclosure and Elevation of privilege have no realistic path through this
change. Denial of service applies in two ways: the cost of parsing a crafted
string, and a crafted string that passes an interactive launch as silent so
that it stalls an unattended run. task0001's files that implement the
boundary are listed under TB-1; its test file holds no parsing logic.

## Trust Boundaries

### TB-1: Codex-proposed shell command into the guard parser
Crossing: the shell command string Codex proposes to run (hook input from another process, produced by an LLM agent and influenceable through repository content) enters the guard's zsh command parser
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command whose anonymous-function arguments nest `(` ranges that contain `;` makes the new argument range scan rescan the rest of the input from each nested `(`, so parse time grows quadratically and the hook stalls (NFR2, NFR3) | TM-1 | The argument range check keeps total parsing work linear in input length, including when a range containing `;` falls back to opening a group and a nested anonymous function's arguments meet another `(` inside it; no recursion is introduced | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | A command shaped so that an interactive interpreter launch is read as connected, or as part of an argument word, passes the guard as silent; the interactive process then waits on stdin and stalls the unattended run (FR2, FR3, NFR1) | TM-2 | The one-word reading of `(`…`)` applies only when the range holds no unquoted `;`, `&` or newline; the head stdin connection reaches only the anonymous body; non-stdin redirects do not connect; an explicit `-i` stays denied; every existing case keeps its verdict and out-of-scope forms keep the base revision's verdict | task0001 AC-2, AC-4, AC-7 | VERIFICATION.md Performance / Security Verification, TM-2 |
