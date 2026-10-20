# Threat Model: codex-guard-case-reading-fixes

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (tier: full; design step skipped).
The feature changes only how the substitution reader of
codex-hook-interactive-guard (`_skip_substitution`, in both plugin copies)
reads a `case` statement inside `$( )`. The hook receives a shell command
string written by the agent — text the agent may have shaped from untrusted
content it read — and answers deny or silent for an interactive launch. A
misread of that string is the only way this change can break what SPEC.md's
security section protects (no fail-closed, no fail-open), so the analysis
has one trust boundary, TB-1.

The single task (task0001) declares `input-handling`, which sets TB-1's
depth to deep. Its other file, `tests/test_codex_hook_interactive_guard.py`,
is not a boundary file: it runs only under the test runner and receives no
input from outside the repository. No new dependency, network path, file
write or privilege change is introduced.

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
