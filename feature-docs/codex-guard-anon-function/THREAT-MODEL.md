# Threat Model: codex-guard-anon-function

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (reduced tier: no REQUIREMENTS.md, design step skipped) and the single task's metadata (task0001, domains: input-handling, which sets TB-1 to deep depth). The feature changes how codex-hook-interactive-guard reads shell command text proposed by the Codex agent. That text can be shaped by untrusted content the agent has read, so it crosses a trust boundary into the guard's static parser (TB-1). The one realistic threat at that boundary is the evasion this feature closes: an interactive launch inside a bare zsh anonymous function escapes judgment (TM-1).

Not recorded as threats:
- A false deny from an over-broad rule (reading a quoted or escaped `function`, or `function function ()`, as an anonymous function) gives an attacker nothing; it is a correctness regression covered by FR3 / FR4 and their regression cases.
- NFR2's no-recursion, single-forward-pass property is an existing property of the parser that this change preserves; the change adds no new nesting path, so no separate denial-of-service row is recorded.
- The forms SPEC.md lists under Out of Scope (`function` without parentheses; an argument after the closing brace) remain residual misses accepted by SPEC.md (A4); no mitigation is planned for them here.

Domain consistency: task0001 declares input-handling; both guard copies it modifies are TB-1's boundary files. Its third file, tests/test_codex_hook_interactive_guard.py, is the test harness and carries no boundary.

## Trust Boundaries

### TB-1: Codex-proposed command text to the interactive guard's parser
Crossing: a shell command string proposed by the Codex agent (its content can be influenced by untrusted text the agent has read) reaches the guard as JSON on standard input; the guard's static parse decides whether the command is denied before it runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command wraps an interactive launch in a bare zsh anonymous function — after a leading reserved word such as `!` or `then`, or with no prefix — and the guard reads the lone `function` as a function name, skips the body, and lets the interactive program start and wait for input, leaving an orphaned process and stalling an unattended run (FR1, FR6; the rule's edges are FR3, FR4) | TM-1 | When exactly one word remains after the leading reserved-word run (and `-p` after `time`) is removed, and that word is a bare `function`, the guard does not treat it as a function name and judges the following groups as executed groups; a quoted or escaped `function` and `function function ()` keep the definition reading | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 (TS1, TS2, TS3, TS8) |
