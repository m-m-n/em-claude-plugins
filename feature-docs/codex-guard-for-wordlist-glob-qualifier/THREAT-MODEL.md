# Threat Model: codex-guard-for-wordlist-glob-qualifier

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md, SPEC.md (FR1 to FR4, NFR1, assumptions A1 to A4),
the context-w handling of `#` in `_skip_substitution` of both copies of
`codex-hook-interactive-guard.py`, and the case table in
`tests/test_codex_hook_interactive_guard.py`. Tier: full. Design step:
skipped (no UI). The only task, task0001, declares `input-handling`, which
sets this analysis to deep for the one boundary below.

The hook reads the Bash command text an agent is about to run and decides
deny or no output by static reading alone; it never executes the command.
The command text is produced by the model and can carry text influenced by
untrusted content, so the hook's reading is a trust boundary. What crosses
it is a string; the hook writes nothing, opens no network and spawns no
process (pinned by the test module's static-constraint tests), so
Spoofing, Repudiation, Information disclosure and Elevation of privilege
have no realistic path at this boundary. The realistic category is Denial
of service: a misread that leaves an interactive launch undenied stalls an
unattended run at an input prompt, and a reading that is no longer linear
lets a long command outrun the hook's time.

Post-decomposition check: task0001's files include both hook copies, which
are this boundary's files. The test module is not a boundary file: it
passes inputs to the hook as JSON on stdin and executes none of them.

## Trust Boundaries

### TB-1: Agent-generated Bash command text into the hook's static reader
Crossing: the `tool_input.command` string of a PreToolUse(Bash) JSON on
stdin, from the agent (model output, possibly shaped by untrusted content)
into codex-hook-interactive-guard, which decides deny or no output
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A `#` inside a nested entry of a zsh `for name (words)` word list in `$( )` (a glob qualifier such as `*(#qN)`) is read as a comment start; with no newline after it the substitution is undecidable and the `python3 -i` after it is not denied, so an unattended run can stall at an interactive prompt (FR1, FR3, FR4) | TM-1 | In a nested word-list entry every `#` is a word character and starts no comment; the same change lands in both copies, which stay byte-identical | task0001 AC-1, AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-6, TS-7) |
| Denial of service | Widening the change past nested entries alters the outermost word-list entry, so a comment there that hides a `)` or a quote (the TS8 `for x (# c<newline>a)` form) is read as words, the substitution closes at the wrong place and a later launch is no longer denied (FR2) | TM-2 | The comment start in context w is decided by the entry kind: in the outermost entry its start condition and its run to the next newline are unchanged | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3, TS-4) |
| Denial of service | The added entry-kind check makes the reading super-linear, so a long command (many commented word-list lines) is not decided in time (NFR1) | TM-3 | The check is one constant-time look at the entry directly beneath the top of the context stack, with no backward scan of the text or the stack | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-5) |
