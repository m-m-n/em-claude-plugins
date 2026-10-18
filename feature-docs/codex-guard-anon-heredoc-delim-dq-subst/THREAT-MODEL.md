# Threat Model: codex-guard-anon-heredoc-delim-dq-subst

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and workflow.yaml (tier `full`, design
step skipped). The feature changes only the static shell parser of
codex-hook-interactive-guard (both copies) and its test table. The single
task declares the `input-handling` domain, so the one boundary found is
analysed at deep depth.

The guard reads one input: the command text of the hook's stdin JSON. That
text is produced by another process (the agent session issuing the shell
command) and can be steered by whatever content that session has read, so
it is untrusted. The guard's verdict (deny or silent) is the only thing it
emits. It performs no writes and starts no process (NFR3), so no other
trust boundary exists. The test file is test-only and is not a boundary.

Every threat recorded below is a parser differential: the guard reading a
command differently from zsh, so that its verdict does not describe what
the shell will run. All are classed as Denial of service. A missed
interactive interpreter launch would wait for input inside an unattended
run. A false deny stops a legitimate command, and with it the unattended
run. No Spoofing, Repudiation, Information disclosure or Elevation of
privilege row is written: the guard authenticates no caller, keeps no
record, emits nothing beyond the verdict, and executes nothing taken from
the input.

Residual, accepted by SPEC.md (Error Handling): an undecidable input is
reported as silent, which is the guard's existing policy. TM-2 does not
change that policy. It sends the overrun shapes into it instead of letting
them produce a guessed delimiter.

Post-decomposition consistency: task0001 declares `input-handling`, and both
guard copies in its `files` are TB-1 boundary files. Its third file,
`tests/test_codex_hook_interactive_guard.py`, is test-only.

## Trust Boundaries

### TB-1: Hook command text into the guard's static shell parser
Crossing: the command string in the hook's stdin JSON, written by another process (the agent session issuing the command), into the guard's static parser. The parser's deny/silent verdict decides whether an interactive interpreter launch goes ahead.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A double-quoted substitution with inner quotes inside the delimiter range of an anonymous-function heredoc makes the guard register a delimiter different from zsh's (FR3; FR1, FR2). The guard then ends the heredoc body on a different line than the shell does. An interactive launch after the real terminator is read as body and passes (fail-open), or a body line is read as a command and denied (false deny). | TM-1 | One shared quoted-unit reader keeps every double-quoted backtick, `$( )` and `$(( ))` substitution verbatim, inner quotes included, and serves both word reading and delimiter-range quote removal. The registered delimiter then matches zsh's. | task0001 AC-1, AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-4, TS-5) |
| Denial of service | A double-quoted substitution in a delimiter range that only closes after the end of the range found by `_scan_parens` (FR4) lets the reader build the delimiter from text outside the range, so the guard diverges from the shell again. A quoted unit left open before its limit (FR1), or a substitution that `_skip_substitution` cannot read, does the same. | TM-2 | Each of these makes the verdict undecidable instead of producing a delimiter: a substitution skip ending beyond the reader's limit, a quoted unit that does not close before the limit, or `_skip_substitution`'s own undecidable result (passed through unchanged). | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3) |
| Denial of service | Moving the word reader's backslash, single-quote and double-quote branches onto the shared reader changes how an ordinary word is read (FR5, FR2). For example, an empty quote no longer starts a word, a backslash-newline starts one, a trailing backslash is no longer undecidable, or a double-quoted substitution no longer marks the word dynamic. The operand/option split of an interpreter command then shifts: `python3 '' -i` read as `python3 -i`, or the line-continuation case read as an operand. The result is a new false deny or a new miss. | TM-3 | The shared reader's result keeps every distinction the word reader makes today: dynamic-ness; an empty quoted unit starts a word; a backslash-newline adds no character and starts no word; a backslash at the end of the input is undecidable. All pre-existing cases keep their verdicts. | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-6, TS-7) |
| Denial of service | Deeply nested or very long quoting and substitution in the command could make the consolidated reader recurse or re-scan (NFR1, NFR2). Recursion exhausts the stack and the hook errors out. Re-scanning grows faster than linearly and the hook exceeds its time budget. Either way, no verdict comes back. | TM-4 | Calls go only from a reader, to the shared reader, to the iterative `_skip_substitution`. `_skip_substitution` never calls back into the shared reader or either reader, and nothing recurses. An overrun ends the judgment, so at most one scan runs past a range. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-8: TestNoRecursion and the scale test; manual call-structure inspection) |
