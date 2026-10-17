# Threat Model: codex-guard-anon-fn-brace-close

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1-FR8, NFR1-NFR4) at the reduced tier; REQUIREMENTS.md and
DESIGN.md are absent. The feature changes how codex-hook-interactive-guard
parses the command string it receives on standard input from the Codex
PreToolUse hook. That string is produced by an agent and can be shaped by
untrusted content the agent read, and the guard's verdict decides whether the
command runs, so the parser sits on a trust boundary. task0001 declares
`input-handling`, so the boundary is analysed at deep depth.

Two threats apply: the guard being evaded by an input it cannot decide (the
regression this feature fixes), and the parser being driven into super-linear
work by deep nesting (the risk the fix itself can introduce). Spoofing,
Repudiation and Information disclosure do not apply: the guard holds no
identity, keeps no record and emits only a fixed verdict. A new false deny on
legitimate input (NFR3) is a correctness regression covered by the
verification scenarios rather than an attacker-driven threat, so it has no row.

## Trust Boundaries

### TB-1: Agent-proposed command string into the guard parser
Crossing: the shell command text the Codex agent proposes to run, delivered as
hook JSON on standard input, crosses from the agent process (model output that
untrusted content can influence) into the guard process, whose deny / silent
verdict decides whether the command runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An anonymous-function body whose closing `}` has no preceding `;` leaves its group open; the whole `-c` string becomes undecidable and is passed, so an interactive launch anywhere in the same string escapes the deny policy and can leave an orphan process waiting for input (FR1, FR2, FR3, FR8) | TM-1 | A standalone bare `}` closes the innermost open group when that group is an anonymous-function body or a `{` group inside one, even with words pending, after finalizing the pending simple command into that group exactly as a `;` terminator would; a quoted, escaped or expanded `}`, a `}` inside a word, and a `}` used as a redirect target never close a group (FR4) | task0001 AC-1, AC-2, AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification: TM-1 |
| Denial of service | A command string whose anonymous-function body holds deeply nested `{` groups makes a per-`}` "inside an anonymous-function body" check walk the enclosing groups, so parse time grows quadratically with input length and the hook stalls the agent's tool call (NFR1) | TM-2 | Whether a group lies inside an anonymous-function body is fixed once when the group opens, inherited from the enclosing group, and read in constant time at each `}`; no walk over enclosing groups, and the scan stays iterative | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification: TM-2 |
