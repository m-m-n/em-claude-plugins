# Threat Model: destructive-guard-heredoc-literal

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR9, NFR1-NFR5, assumptions A-1 to A-5) at the reduced
tier (no REQUIREMENTS.md; the design step was skipped), after the SPEC change
that added FR9 and NFR5 and the revision that widened FR9 (3) to every
command word that cannot be fixed statically as a single word. The feature's
only input is the Bash command string that
`em-workflow/hooks/destructive-guard.py` judges before the shell runs it. The
feature stops the guard from reading the contents of closed ordinary string
literals in the body of a heredoc whose body is the program a Python
interpreter runs, and stops that masking again for the whole command when the
command holds a statement that can change what the Python name runs, the
shell's state, or how the Python output is evaluated. task0001 and task0002
both declare `input-handling` and `auth` (the guard is a permission gate), so
the one boundary is analysed at deep depth.

The expectation suite file is project test data and not a boundary of its
own; it is listed under TB-1 because it pins the guard's verdicts at that
boundary. The verdict holds because every narrowing of what the guard reads
can let a command that a shell actually runs pass the guard (TB-1).

Accepted residual risks, not mitigated here:

- Python code that hands the content of a masked literal to a shell later
  (`os.system`, a `subprocess` call with `shell=True`, a file written by
  Python and run by a shell afterwards) can pass the guard after this change.
  SPEC A-3 accepts this as a known limitation; the guard already does not
  follow a file written by a data heredoc into a later shell run.
- The FR7 override reading, which turns data-heredoc judgments undetermined,
  keeps its one-level `builtin` reading, so an override written behind nested
  `builtin` words does not change how a data heredoc is judged. This predates
  the feature; SPEC A-5 keeps it unchanged and TS-31 pins it.

Whole-command checks that read the raw command string (the
download-piped-to-shell check, the kill-word deferral) are unchanged by this
feature and not modelled.

## Trust Boundaries

### TB-1: Bash command string to the destructive-guard verdict
Crossing: a Bash command string composed by the agent, whose text can be
steered by untrusted content the agent has read, crosses into
destructive-guard.py, which returns allow, ask or deny before the shell runs
the command.
Boundary files: em-workflow/hooks/destructive-guard.py, em-workflow/hooks/tests/destructive-guard-cases.json
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Literal masking is applied to a heredoc whose body, or whose Python output, reaches a shell or a consumer the guard cannot resolve: a pipeline stage after the Python statement, a process substitution on it, or an enclosing statement such as `bash -c "$( )"` or `eval`. A backtick or `$( )` inside a literal that the shell then runs passes the guard (FR2, FR7). | TM-1 | Masking applies only when the host statement's downstream pipeline (including the downstream of any group open at it) has no sink stage and no undetermined stage, the host holds no process substitution, and every enclosing statement is lexed, holds no sink and is either assignment-only or a data command. Any other shape keeps today's decision exactly. | task0001 AC-4 | VERIFICATION.md, Performance / Security Verification: TM-1 (via TS-9, TS-10, TS-11, TS-12, TS-19) |
| Spoofing | The command word the guard reads as Python is not what consumes the body: a wrapper whose skipped words carry a shell (`env -S 'bash -s' python3`), or a command-name override (a function named `python3`, an alias, a PATH assignment) written before or after the heredoc. The body then runs as shell while its literals are masked (FR2). | TM-2 | A heredoc whose host statement's skipped words make a destination undetermined under the guard's existing skipped-word rule is not eligible. When any command-name override construct is seen anywhere in the command, every eligible body is also inspected unmasked, through the same deferral the guard already applies to data heredoc bodies. | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification: TM-2 (via TS-20) |
| Elevation of privilege | The heredoc body is not the program Python runs but data for one: a script operand, `-c`, `-m`, a heredoc on a file descriptor other than standard input, or a statement whose other redirects make another input the program (a second heredoc with a descriptor move such as `python3 <<'DATA' 3<&0 <<'PY'`, a duplication onto standard input, a `<` redirect). Python literal rules then hide shell syntax in text that the program can hand to a shell wholesale, which today's guard reads as shell (FR1, FR2, FR6). | TM-3 | Masking applies only when Python takes its program from this heredoc and nothing else: the heredoc is on standard input and is the statement's only heredoc, there is no here-string, every other redirect is an output redirect to a file (no input redirect, no file-descriptor duplication, move or close, no redirect on descriptor 0, no named descriptor), and the words after the Python command word are only `-` and letter-only short-option clusters containing neither `c` nor `m`. Any other shape keeps today's decision. | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification: TM-3 (via TS-21, TS-26) |
| Elevation of privilege | Masking hides text the interpreter executes as code rather than holds as data: a line outside every literal, an f-string or t-string replacement field (which from Python 3.12 may nest quotes of the f-string's own kind, so a scan that ends the f-string at the next same quote would mask code inside the field), or text after a quote that a comment or an unclosed literal leaves unmatched. A destructive line the guard catches today then passes (FR3, FR4, FR6). | TM-4 | Only closed ordinary literals are masked. The first literal whose prefix is anything other than empty or r, b and u (every f- and t-prefix included) makes the whole body undecidable, so no text of that body is masked and its extent is never guessed; a quote inside a comment opens nothing; any literal that does not close makes the whole body unmasked; text outside literals is read exactly as today. | task0001 AC-6 | VERIFICATION.md, Performance / Security Verification: TM-4 (via TS-13, TS-14, TS-15, TS-25) |
| Elevation of privilege | With an unquoted delimiter the outer shell expands `$( )` and backticks in the body, literals included, before Python receives it. Masking the literal contents would hide substitutions the shell runs (FR5). | TM-5 | For an unquoted delimiter the substitutions of the original, unmasked body are extracted and inspected exactly as for a data heredoc body (escaped openers stay literal, an unclosed opener makes the whole original body inspected), in addition to the masked body read as statements. | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification: TM-5 (via TS-7, TS-8) |
| Denial of service | A body crafted so that the literal scan costs more than linear time in its length (rescanning from each quote, backtracking) runs the hook past its time limit, and the command gets no verdict (NFR2). | TM-6 | The literal scan is one left-to-right pass over the body; the masked text has the body's length, so the existing relative scan budget bounds the whole run, and exceeding it asks rather than allows. | task0001 AC-8 | VERIFICATION.md, Performance / Security Verification: TM-6 (via TS-16, TS-24) |
| Elevation of privilege | Determining literal extents by evaluating, compiling or importing the body would run attacker-chosen Python inside the hook process (NFR1). | TM-7 | The literal scan reads the body's characters only; no part of the body is evaluated, compiled, executed or imported, and only the standard library is used. | task0001 AC-8 | VERIFICATION.md, Performance / Security Verification: TM-7 (via TS-24) |
| Spoofing | A command-name override that the one-level reading does not see — written behind nested `builtin` / `command` words, their options or `--` (`builtin builtin alias python3=bash`, `builtin builtin hash -p /bin/bash python3`) — makes the Python name run a shell while its literals stay masked. A list of stop words kept apart from the override vocabulary can also drift from it, so an override word added later stops nothing (FR9, NFR5). | TM-8 | The masking-stop check reads the command word through one function that removes any number of `builtin` / `command` words with their options and `--`; its command-word vocabulary is the override builtin set joined with the state builtins, and its variable-name vocabulary the override variable-name definition joined with `BASH_ALIASES`, each referring to the override definition by name. Every override word, nested or not, and every statement the override reading flags, stops masking for the whole command, before or after the heredoc. | task0002 AC-1, AC-6 | VERIFICATION.md, Performance / Security Verification: TM-8 (via TS-30, TS-32) |
| Elevation of privilege | A statement that changes shell state or a variable's attributes (`declare -i` making a later assignment evaluate an array subscript that holds `$( )` printed by Python; `source`, `eval`, `set`, `shopt`) is hidden from a reading of token values: behind nested `builtin` / `command` words, their options or `--`; behind a command word that a parameter expansion, a command substitution, a tilde, a pathname or extended-glob pattern, a brace expansion or a locale quote makes at run time; or spelled with quotes, escapes or an ANSI-C quote. Text inside a masked literal is then run by the shell (FR9). | TM-9 | Such a statement anywhere in the command stops masking for the whole command, before or after the heredoc. The command word, and every word passed while removing `builtin` / `command` and their options, is read as written with the lexer's region kinds: a word that only quotes and escapes make is restored and matched against the stop vocabulary; any word that depends on an expansion, a locale quote, an escape the decoder does not support, or a reading that failed is undeterminable and stops masking. | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification: TM-9 (via TS-28, TS-29, TS-33 to TS-39, TS-41) |
| Elevation of privilege | The exemption that keeps FR9 (3) off the code of a Python-program body re-read as shell reaches text the shell itself evaluates: a substitution in the body of an unquoted-delimiter heredoc, whose undeterminable command word would then not stop the masking of another Python body in the same command (FR9, FR5). | TM-10 | Only chunks that re-read a Python-program body, and chunks derived from them, are exempt, and only from FR9 (3). The substitutions the FR5 extraction queues from an unquoted delimiter's original body, the substitutions and unclosed command forms found in the body chunk of an unquoted-delimiter Python heredoc, and everything derived from them are not exempt; FR9 (1) and (2) apply to every chunk. | task0002 AC-4 | VERIFICATION.md, Performance / Security Verification: TM-10 (via TS-42) |
| Denial of service | A command crafted so that the masking-stop check costs more than linear time — re-peeling nested `builtin` words, or searching each word again from every `[`, `{` or quote for its closing character — runs the hook past its time limit, and the command gets no verdict (NFR2). | TM-11 | The peel visits each word of a statement at most once, the word reading reads each character of a word a bounded number of times, and the existing relative scan budget is unchanged, so exceeding it asks rather than allows. | task0002 AC-6 | VERIFICATION.md, Performance / Security Verification: TM-11 (via TS-16, TS-45) |
