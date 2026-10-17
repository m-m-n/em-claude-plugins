# Threat Model: codex-guard-anon-arg-paren-comment

## Verdict
threats-identified

## Rationale
Inspected REQUIREMENTS.md and SPEC.md (tier: full; design step skipped). The
feature changes the parsing logic of codex-hook-interactive-guard, a
PreToolUse hook that receives a shell command string proposed by the Codex
agent and denies interactive launches. That command string is untrusted
input: repository content or prompts the agent reads can steer it. This gives
one trust boundary (TB-1). The single task (task0001) declares
`input-handling`, so TB-1 is analysed at deep depth. No `auth`,
`external-io` or `data-persistence` surface is touched: the guard reads only
its hook payload and emits only its verdict (NFR2).
`tests/test_codex_hook_interactive_guard.py` is test code that feeds fixed
strings to the guard and crosses no boundary. Spoofing, Repudiation and
Information disclosure do not realistically apply: the guard authenticates
nobody, keeps no record whose integrity matters, and holds no secret.

## Trust Boundaries

### TB-1: Codex hook payload to guard verdict
Crossing: a shell command string authored by the Codex agent (another process whose output untrusted repository text can steer) passes through the PreToolUse hook payload into the guard; the guard's verdict decides whether the command runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command hides an interactive launch after a `;` or lone `&` inside an anonymous-function argument `(` whose closing `)` sits in a comment or is missing; the guard reports undecidable (no output), the launch runs, and the unattended session stalls waiting for input (FR1, FR2, FR6). | TM-1 | Rescue: an unclosed provisional group whose first direct separator is `;` or lone `&` is dissolved, and the commands after that separator are judged in the enclosing context without the anonymous-function head's pipe or input redirection. | task0001 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | Deeply nested unclosed provisional groups make the rescue re-read the input once per level or recurse, so the guard exceeds its time budget or overflows the stack and returns no verdict, letting the command through (NFR1). | TM-2 | The rescue does linear total work over the input (no per-level re-reading; each dissolution is constant amortized work) and uses no recursion. | task0001 AC-7 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Elevation of privilege | To learn how zsh splits the command, the fix consults a real shell or evaluates the command text, executing attacker-steerable commands with the hook's privileges (NFR2). | TM-3 | The verdict is derived from the command string alone using the standard library; the guard opens no file, network connection or child process. | task0001 AC-8 | VERIFICATION.md Performance / Security Verification: TM-3 |
