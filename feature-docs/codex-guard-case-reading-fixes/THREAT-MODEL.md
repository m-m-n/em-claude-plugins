# Threat Model: codex-guard-case-reading-fixes

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md as revised after review round 1
(tier: full; design step skipped). The feature changes only how the
substitution reader of codex-hook-interactive-guard (`_skip_substitution`,
in both plugin copies) reads a `case` statement inside `$( )`. The hook
receives a shell command string written by the agent — text the agent may
have shaped from untrusted content it read — and answers deny or silent for
an interactive launch. A misread of that string is the only way this change
can break what SPEC.md's security section protects (no fail-closed, no
fail-open), so the analysis has one trust boundary, TB-1.

TM-1 to TM-4 cover the first pass (task0001, merged). The revision adds
FR9–FR11 and revises FR1 / FR2 / A2 after review round 1 found two high
regressions in task0001's reading (findings 8aed11cf08b2dc4c and
2fe94b219da49a89): the word after a compound closing or a function head was
read as an argument. TM-5 to TM-8 record the threats the new reading adds at
the same boundary (task0002).

Both tasks declare `input-handling`, which sets TB-1's depth to deep. Their
other file, `tests/test_codex_hook_interactive_guard.py`, is not a boundary
file: it runs only under the test runner and receives no input from outside
the repository. No new dependency, network path, file write or privilege
change is introduced.

Every recorded threat is a Denial of service: both a missed deny (an
interactive process starts and stalls the unattended session) and a false
deny (a legitimate command is refused and the unattended run stops) end the
run without a human to recover it. Spoofing, Repudiation, Information
disclosure and Elevation of privilege do not realistically apply: the hook
holds no identity or secret, its only output is the verdict, and this
feature changes no record it writes. Tampering of the hook script itself is
outside what this feature changes.

## Trust Boundaries

### TB-1: Agent-authored command string into the guard's substitution reader
Crossing: the `tool_input.command` string of a PreToolUse(Bash) event,
authored by the agent (influenceable by untrusted text the agent has read),
crosses into the hook process, whose reader decides where a `$( )` and the
surrounding quote end and therefore whether a following interactive launch
is denied.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | An argument-position `case` / `esac`, including one after an argument-position reserved word or `!`, opens or closes a case statement (FR1, FR2). The reader then takes a later pattern `)` as the end of the substitution: a quoted `python3 -i` is denied (fail-closed), or the quote view shifts so a real launch after the substitution reads as quoted text and stays silent (fail-open). | TM-1 | Command position is forward state held per command list; `case` opens and an item-body `esac` closes only as a standalone word at command position; a reserved word or `!` at argument position never yields command position. | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | A `#` directly after a pattern-closing `)` is read as body text (FR3). An `esac`, `)` or quote inside that comment then closes the statement or the substitution, or opens a quote, giving a false deny or a missed deny for the launch that follows. | TM-2 | A `#` directly after the `)` that closes an item's pattern starts a comment that runs to the newline; nothing inside it closes a statement, closes a substitution or opens a quote. | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | A backslash-newline pair in a waiting phase, inside a keyword or directly after it (FR4, FR5), makes the read undecidable (the hook stays silent and the launch after the substitution starts) or makes a `case` / `esac` be taken or missed as a keyword, shifting the end of the substitution in either direction. | TM-3 | Every waiting phase skips continuation pairs and keeps its phase; `case` / `in` / `esac` are decided on the character sequence with the pairs removed, a pair inside a word never splits it, and a sequence that does not spell the keyword once the pairs are removed is never a keyword. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | Crafted long input — long runs of continuation pairs, many split words whose keyword match fails, many argument-position reserved words — pushes the new matching into super-linear time, so the hook does not answer within its time limit (NFR1). | TM-4 | A keyword match starts only at a word start and examines only the keyword's characters plus the pair runs between and directly after them; a failed match is not retried inside the same word; the number of matches that re-read one pair run is bounded by a constant; command-position state is constant size per context; no recursion (NFR2). | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Denial of service | After a compound-command closing (FR9) — the `)` of a command-position `(` or `((`, a `]]` closing a command-position `[[`, a case-closing `esac`, a command-position `fi` / `done` / `}` — the next `then` / `do` / `{` is read as an argument, so the `case` after it does not open and its pattern `)` is taken as the end of the substitution: the quote view shifts and a real launch after the substitution stays silent (fail-open; finding 8aed11cf08b2dc4c), or a quoted launch is denied (fail-closed). Treating a word-internal close, an unmatched `]]` or an argument-position `fi` / `done` / `}` as a closing misreads the other way, letting an argument `case` open a statement (FR1, FR2). | TM-5 | Command position is set forward, when the closing is read, after exactly the FR9 closings, using per-context state recorded at the opening (a `(` opened at command position, a `[[` read at command position); a closing substitution, quote, `${ }` or `)` of a non-command-position `(`, an unmatched `]]` and argument-position closing words keep the word going on; closing and reserved words are decided on the pair-stripped sequence. | task0002 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification, TM-5 |
| Denial of service | After a function head (FR10) — `name()`, `function name`, `function name()` — the body's `{` is read as an argument, so a `case` in the body does not open: a quoted `python3 -i` in an item body is denied (fail-closed) or a launch after the substitution stays silent (fail-open; finding 2fe94b219da49a89). Reading the name after `function` as a keyword, or starting a head from an argument-position or quoted `function`, misreads the other way (FR2). | TM-6 | An empty `()` after the first word of a simple command read at command position, and a standalone, unquoted, command-position `function` with its name (and an optional empty `()`), give the next word command position; the name is never a keyword; an argument-position, quoted or escaped `function` starts no head. | task0002 AC-2 | VERIFICATION.md Performance / Security Verification, TM-6 |
| Denial of service | After a loop or coproc head (FR11) — the `for` / `select` name, the arithmetic for's `))`, zsh `for name (words)`, `coproc` and its NAME, zsh `repeat` and its count — the next `do` / `{` is read as an argument, with the same fail-open / fail-closed outcomes for a `case` in the body. Reading the `for` name or the words of the zsh word list as keywords, or starting a head from an argument-position or quoted `for` / `select` / `coproc` / `repeat`, lets an argument `case` open a statement (FR2). | TM-7 | A per-context head state starts only from a standalone, unquoted, unescaped head word read at command position and decided on the pair-stripped sequence; it gives the FR11 positions command position, reads the for name, the repeat count and the zsh word list as ordinary words, and ends at a separator. | task0002 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-7 |
| Denial of service | Crafted long input against the new state — deeply nested compound closings, function heads or loop heads, long argument runs of closing words and reserved words, repeated empty-`()` checks — pushes the reading into super-linear time, so the hook does not answer within its time limit (NFR1). | TM-8 | `[[` tracking and the closing, function-head and loop/coproc-head decisions use constant-size state per context; the empty `()` check re-reads the blanks between the parentheses a bounded, constant number of times; no recursion (NFR2). | task0002 AC-5 | VERIFICATION.md Performance / Security Verification, TM-8 |
