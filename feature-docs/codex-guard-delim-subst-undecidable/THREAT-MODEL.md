# Threat Model: codex-guard-delim-subst-undecidable

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the `full` tier. The feature changes
how the guard's shared substitution skip reads shell text inside `$( ... )`
(FR1, FR2, FR3) in both copies of the Codex hook guard. That text is the
command string a Codex agent submits, which is attacker-influenceable (the
agent's output can be steered by untrusted repository or prompt content), so
the guard's parser sits on a trust boundary. The single task (task0001)
declares `input-handling`, which sets the analysis depth to deep; its two
script files are the Boundary files of TB-1, and its third file (the test
module) is test harness only and carries no boundary. SPEC.md's Security
Considerations (NFR3) states what is protected; this document states how the
changed reading can be broken and how the design prevents it.

The guard turns an undecidable reading into no output (silent), which lets
the command run. Both threats below are therefore availability threats: an
interactive command such as `python3 -i` that the guard fails to deny stalls
an unattended run.

## Trust Boundaries

### TB-1: Agent-submitted command text into the guard's static parser
Crossing: the shell command string in the hook's stdin JSON (`tool_input.command`), authored by the Codex agent, crosses into the guard process, whose parser decides deny or silent without executing it.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command whose heredoc delimiter `${ ... }` contains a `$( ... )` holding a same-line `<<`, a command-position arithmetic `((`, or a parenthesis inside an argument word makes the shared skip report undecidable, so the guard emits nothing and an interactive `python3 -i` after the terminator line runs and stalls the unattended session (regression against FR1, FR2, FR3, NFR3) | TM-1 | The shared skip reads all three forms to the delimiter end zsh uses: a same-line `<<` outside a case statement is read through without reading a body; a command-position `((` closed by `))` is read as arithmetic; a `(` not at command position opens a word-parenthesis context. A `<<` inside a case statement and a `<<` followed by an unquoted newline before the substitution closes stay undecidable. Both copies stay byte-identical and are exercised by the same CASES rows (FR4, FR5) | task0001 AC-1, AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Denial of service | A crafted command with many command-position `((` that do not close as `))` drives the new arithmetic-then-subshell fallback into re-reading the same text repeatedly, pushing the guard into super-linear time or deep recursion so the hook times out or crashes without a decision (FR2, NFR1) | TM-2 | At most one fallback re-read per `((`; a fixed cap on the total characters re-read within one call, with undecidable once the cap is exceeded; the reader keeps its explicit stack and never recurses | task0001 AC-2, AC-7 | VERIFICATION.md Performance / Security Verification, item TM-2 |
