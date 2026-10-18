# Threat Model: codex-guard-anon-arg-backquote-comment

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md and workflow.yaml at tier `full`; the
design step was skipped. The feature changes how the guard's static parser
reads a command string, so its single input — `tool_input.command`, text
written by an agent and possibly steered by content the agent read — is the
one trust boundary. task0001 declares `input-handling`, which sets this
boundary's depth to deep.

The guard holds no identity, no secret and no stored state, writes nothing
and touches no file, network or child process (NFR2); its only output is the
deny decision or no output. Spoofing, Tampering, Repudiation, Information
disclosure and Elevation of privilege therefore get no row. The harm at this
boundary is a command that should be denied getting no decision, so an
interactive `python3 -i` starts and stalls the unattended run: every row is
Denial of service.

Post-decomposition check: task0001 (`input-handling`) has two of its files
in the Boundary files line below. Its third file,
`tests/test_codex_hook_interactive_guard.py`, is the test table run against
the guard, not a place where the boundary is implemented.

## Trust Boundaries

### TB-1: Agent-written command string into the guard's static decision
Crossing: the `tool_input.command` string passed on the hook's standard input, from the agent that wrote the command (untrusted, possibly prompt-steered) to the guard's parser, whose deny-or-no-output decision decides whether the command may run.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | Evasion by comment: an anonymous function argument range that returns to group reading through a backquote and holds an unquoted `#` at word start after whitespace makes the guard read the `#` as a comment, skip the closing parenthesis and end undecidable with no output, so the body's explicit `python3 -i` runs (FR1, FR2, FR3; review finding ab990994bd365064). The em-review copy left unfixed keeps the same evasion (FR6). | TM-1 | A provisional group opened under the FR2 condition, and every group opened inside it (FR3), reads a word-start unquoted `#` as a word character while it is the innermost open group, so the group closes and the body is judged; the change is applied to both copies byte-identically (FR6). | task0001 AC-1, AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Denial of service | Evasion through an over-broad exception: if `#` after the parser's own separator were still read as a word character, following text such as a lone single quote would become an unclosed quote, the guard would end undecidable and a command denied today would get no output (FR4, FR5, NFR2). | TM-2 | The exception starts only under the FR2 condition, is inherited only at group open, is cleared on the innermost group by the five direct separators of FR4 and by nothing else, and every other reading listed in FR5 is unchanged; every existing deny row stays deny. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, item TM-2 |
| Denial of service | Evasion by cost: crafted deep nesting makes the new per-group state cost super-linear time or exhaust the call stack, so the hook runs out of time or fails instead of reaching a deny (NFR1). | TM-3 | The state is decided once per group open from the parent; reading `#` and reading a separator consult only the innermost group in constant time; no recursion is added; the existing performance and recursion-check tests pass on both copies. | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, item TM-3 |
