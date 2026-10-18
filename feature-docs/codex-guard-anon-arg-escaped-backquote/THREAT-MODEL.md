# Threat Model: codex-guard-anon-arg-escaped-backquote

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR3, NFR1-NFR3, A-1, A-2) and the workflow goal, at
the reduced tier (no REQUIREMENTS.md; the design step was skipped). The
feature changes where the guard's parser ends an unquoted backquote span in
the command text it receives, in both copies of the guard, and adds one
regression row to the guard's case table.

The guard's only input is the shell command an agent's tool call proposes,
which the hook runtime hands to the guard process as JSON on standard input.
That text is model output that untrusted repository or task content can
steer, so it crosses a trust boundary (TB-1). The only task, task0001,
declares `input-handling`, which sets TB-1's depth to deep; no task declares
`auth`, `external-io` or `data-persistence`.

The guard returns a deny decision or stays silent. Its purpose is to keep an
explicit interactive interpreter (`python3 -i`) from starting a session that
waits for input and stalls an unattended run, so the realistic category at
TB-1 is Denial of service. Spoofing, Repudiation, Information disclosure and
Elevation of privilege get no row: the guard authenticates no party, keeps
no audit record the feature changes, reads no secret, and grants no
privilege.

task0001 also modifies `tests/test_codex_hook_interactive_guard.py`. That
file is not a boundary file: it runs only in the development test suite and
never receives tool-call input at run time.

## Trust Boundaries

### TB-1: Agent-proposed shell command to the guard's parser
Crossing: the shell command text in the hook input's `tool_input.command`,
produced by the agent and passed by the hook runtime to the guard process on
standard input; the guard's decision (deny, or silent) flows back to the
runtime.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | Evasion of the explicit-`-i` deny: an unquoted backquote that nests a backslash-escaped backquote makes the closing search stop at the escaped backquote, the last backquote is then read as unclosed, the parse becomes undecidable, the guard stays silent, and the explicit `python3 -i` in the same command starts an interactive session that stalls the run (FR1, FR3, A-1, A-2). The evasion stays open in whichever copy is left unfixed (FR2). | TM-1 | The closing search consumes each backslash together with the character after it, the rule the `b` context of `_skip_substitution` already applies, so escaped backquotes stay inside one dynamic chunk and the explicit `-i` is reached and denied. The change lands in both copies, which stay byte-identical, and a deny row with the reproduction command guards against recurrence. | task0001 AC-1, AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | Crafted command text (long runs of backslashes, many backquotes, a span that never closes) makes the modified closing search super-linear or recursive, so the guard exhausts its time or stack budget instead of returning a decision (NFR1). | TM-2 | The closing search is one forward pass that examines each character at most once and uses no recursion; a span with no closing backquote once pairs are consumed returns the existing `quote` undecidable result. | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
