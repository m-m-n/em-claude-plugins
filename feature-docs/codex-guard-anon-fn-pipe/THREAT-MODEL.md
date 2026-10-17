# Threat Model: codex-guard-anon-fn-pipe

## Verdict
threats-identified

## Rationale
Inspected: REQUIREMENTS.md, SPEC.md (tier full; the design step was skipped),
both copies of `scripts/codex-hook-interactive-guard.py` and
`tests/test_codex_hook_interactive_guard.py`. The planned change adds three
entries to the CASES test table; FR5 permits a change to both hook copies only
if one of those entries fails on the current code.

The guard reads the command string an agent proposes, from the PreToolUse
payload on standard input: one trust boundary (TB-1). task0001 declares
`input-handling`, so TB-1 is analysed at deep depth. Only Denial of service
applies there: the guard exists to stop a launch that opens a REPL and keeps
waiting after the terminal is gone, and this feature can weaken that only
through a parser change made under FR5. Spoofing and Repudiation do not apply
(the guard authenticates no caller and owes no record), Tampering does not
(the guard writes nothing and the feature adds no input path), Information
disclosure does not (the deny reason is unchanged by this feature), and
Elevation of privilege does not (the guard only denies or stays silent). The
false deny the new silent entries pin against is no threat: it fails closed,
with a reason the agent can act on (FR1, FR3). The test file is a harness the
developer runs, not a boundary.

## Trust Boundaries

### TB-1: Agent command text into the interactive-launch guard
Crossing: the Bash command string an agent proposes (model output, open to influence from untrusted content), carried by the Codex PreToolUse payload on standard input into the guard process, which answers with a deny object or nothing
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A parser change made under FR5 carries the head's pipe or stdin connection beyond the anonymous body (to the `(` group of the `()`, to a command after the separator that ends the arguments, from a redirect other than stdin, or to a brace group that is no anonymous body), or stops denying an explicit `-i` in a connected body, so a launch that opens a REPL passes the guard and stalls the run (FR2, FR5, NFR2) | TM-1 | The connection reaches the anonymous body alone and an explicit `-i` stays denied: every pre-existing CASES entry stays unchanged and passes on both copies, the deny entries that bound the connection included, and the new piped `-i` entry is denied | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, TM-1 |
