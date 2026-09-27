# Threat Model: loop-command-guard

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md at the `full` tier (the design step
was skipped, so there is no DESIGN.md). The feature adds one PreToolUse(Bash)
hook that reads command text and returns a permission decision, plus its
registration, tests, documentation and version metadata.

That hook is the only point where data crosses between parties of different
trust. The command text is authored by the LLM agent, which can itself be
steered by untrusted content it has read. The hook's output then feeds Claude
Code's permission decision alongside the other PreToolUse(Bash) guards.
Analysis depth for that boundary is deep because task0001 declares `auth`
(the hook takes part in the permission decision) and `input-handling` (it
parses untrusted command text).

The documentation files (em-workflow/README.md, .claude/rules/hook-tests.md),
the test modules and the version manifests move no data across a trust
boundary. That is why task0001's other files appear in no Boundary files
line.

SPEC.md deliberately accepts some gaps, and this design does not claim to
prevent them:
- loops inside script files run by path (A3)
- shells reached as another command's argument, over ssh, or through a pipe
  (A6)
- shells other than bash / sh / zsh (A6)
- a top-level command whose structure cannot be settled (FR8, A5). Such a
  command passes silently even when it also contains a loop.

## Trust Boundaries

### TB-1: Agent-authored Bash command -> loop-command-guard.py -> Claude Code permission decision
Crossing: Claude Code writes the PreToolUse payload to the hook's standard
input. The payload's `tool_input.command` is text authored by the LLM agent,
another party whose output untrusted content can influence. The hook's
standard output returns into Claude Code's permission decision for that Bash
call, which the other registered PreToolUse(Bash) guards also feed.
Boundary files: em-workflow/hooks/loop-command-guard.py, em-workflow/hooks/hooks.json
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A while / until loop sits in a nested execution context the reader does not re-read: a shell `-c` string, an eval argument, a command substitution or backtick (including inside double quotes), a heredoc or herestring fed to a shell, or a shell behind a prefix command. The loop reaches execution, never ends, and hangs the session (REQUIREMENTS.md 1.1; FR2, FR3, FR5) | TM-1 | Every nested form that FR3, FR5 and A6 name is re-read with the same command-position rule, recursively. A nested text that cannot be settled yields no finding for itself, but it never cancels a finding in the enclosing text | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | The guard denies legitimate commands that only mention while / until as data: argument words, quoted text, heredoc bodies fed to non-shell commands, comments, or quoted / escaped reserved words. Ordinary work such as commit messages, or file writes through a heredoc, is blocked (FR4, A7; REQUIREMENTS.md UC02) | TM-2 | A loop is detected only at a command position, after the reader has settled quotes, escapes, heredocs and comments. Heredoc bodies and herestrings are re-read only when fed to bash / sh / zsh | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Elevation of privilege | While reading the command, the guard runs or expands part of it, for example by executing a command substitution to learn its content, or by handing the text to a shell for a syntax check. Unapproved code then runs inside the hook before any permission decision exists (NFR1, NFR2) | TM-3 | The hook reads the command purely as text. It creates no process, evaluates no part of the command text, opens no file and opens no network connection | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Elevation of privilege | The guard emits a decision other than deny (allow or ask), or it is registered after destructive-guard.py. Its output then ends the permission decision for calls it should leave to the later guards, or destructive-guard.py's blanket allow preempts its deny (NFR3, FR7, FR9, A12) | TM-4 | The hook's output is the deny object or nothing. Its registration sits immediately before destructive-guard.py. The registration tests pin the nine-entry order and keep destructive-guard.py as the last Bash guard able to return a decision | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Denial of service | A pathological command, such as a very large heredoc body or very deep nesting, exhausts recursion or runs past the 15-second registration timeout. The hook then ends with a traceback on stderr and a non-zero exit, or times out, instead of reaching a clean outcome. That call is also delayed (NFR2, FR8) | TM-5 | Nesting is read only to a fixed maximum depth. Every failure, including recursion exhaustion, ends silently with exit status 0 and empty stderr. Work grows with command length, and megabyte-scale input finishes far inside the registration timeout | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |
