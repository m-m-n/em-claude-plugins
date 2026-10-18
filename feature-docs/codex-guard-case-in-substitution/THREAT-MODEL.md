# Threat Model: codex-guard-case-in-substitution

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR9, NFR1-NFR4, assumptions A1-A6), REQUIREMENTS.md,
IMPLEMENTATION.md decisions D1-D4, and the reader the change touches (the
substitution skip of the two byte-identical guard copies and its callers).
Tier: full. DESIGN.md is absent (design step skipped). The single task
(task0001) declares the `input-handling` domain, so TB-1 is analysed at deep
depth; no task declares `auth`, `external-io` or `data-persistence`.

The feature changes how the guard reads one class of untrusted input, the
command string of a Codex Bash call, and nothing else: it adds no file,
network or process access (NFR3), no new input source, and no change to the
deny output (which never echoes command text). The one trust boundary is
therefore the command string entering the reader. Three threats apply there,
all Denial of service: a launch the guard fails to deny because it gives up
on a `case` statement (the defect this feature fixes, which also covers
shell-valid forms the reader would make undecidable without reason), a false
deny caused by misplacing the close of a substitution, and resource
exhaustion of the hook process on crafted `case` statements. Spoofing,
Tampering, Repudiation, Information disclosure and Elevation of privilege
have no realistic path through this change: the guard holds no identity,
writes nothing, keeps no record, discloses nothing and runs with its caller's
own rights.

Residual risk accepted by SPEC.md and left unmitigated here: the forms FR4
lists stay undecidable and give no output (fail-open, as before); `$(case ...)`
outside quotes stays out of scope (SPEC.md A1); a `case` word that is the
target of a `>&` / `<&` / `>|` redirect is still taken for the keyword (A3)
and ends undecidable. The forms IMPLEMENTATION.md D2 and D3 keep undecidable
are ones neither bash nor zsh accepts.

## Trust Boundaries

### TB-1: Bash command string entering the guard's reader
Crossing: the `tool_input.command` text of a Codex PreToolUse(Bash) event,
composed by the Codex agent and influenceable by untrusted repository content
or prompt injection, read by the hook process from standard input and walked
by the reader (word reading and the anonymous-function heredoc delimiter
range both reach the substitution skip through the shared quoted-unit reader).
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A `case` statement placed in a `$( ... )` inside double quotes, in a word or in an anonymous-function heredoc delimiter range, makes the reader give up, so a later interactive launch in the same `-c` string is not denied and the orphan REPL spins; the same happens when a header or pattern form a shell accepts is made undecidable (FR1, FR5) | TM-1 | Read the `case` statement, every form bash or zsh accepts included, so the close of the substitution is found where zsh finds it, and judge the launch after it | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 (TS1-TS10, TS15, TS21) |
| Denial of service | A pattern's `)`, a `)` or `\|` inside a quoted pattern or a nested substitution, or an `esac` that is an argument or sits in a comment, is taken as the end of the substitution or of the statement, so text inside the substitution is judged as a command and a legitimate call is denied, stalling the review (FR1, FR2, FR3, FR6) | TM-2 | Close the substitution only after every `case` statement in it is closed by `esac` at a pattern or command position; never judge the contents of the substitution; raise undecidable instead of guessing for any form whose close cannot be located (FR4) | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS8-TS14) |
| Denial of service | A command string with very many `case` items or deeply nested `case` statements makes reading super-linear or exhausts the call stack, so the hook does not answer in time (NFR1, NFR2) | TM-3 | Read `case` statements on the existing explicit stack with constant work per character and a backward look bounded to the preceding blank run and letter run; add no recursion and no call cycle | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 (TS16, TS17, TS19) |
