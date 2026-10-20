# Threat Model: codex-guard-redirect-only-list-pending

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, and the list-continuation handling of the
guard parser in both copies (the separator path, the end of a simple command,
the two paths that close a `(` group at a `)`, and the checkpoint test at a
top-level newline), together with the case table that pins the guard's
verdicts. Tier: full. The single task (task0001) declares `input-handling`, so
TB-1 is analysed at deep depth.

The feature changes how a PreToolUse guard parses untrusted command text and
decides between a deny and no output. That parse is a trust boundary, and the
defect being fixed is a fail-open on it, so Denial of service applies in both
directions: a missed deny lets an interactive interpreter stall an unattended
run, and an over-broad fix denies commands the shell would never run. A slow
parse is a third availability path, because the guard runs on every Bash call.
Spoofing, Repudiation and Elevation of privilege do not apply: the guard
authenticates nothing, records nothing and grants nothing — it only denies or
stays silent. Tampering does not apply: the hook reads its input and writes no
file. Information disclosure does not apply to this change: the deny reason
text is not touched by this feature.

The false denies accepted by SPEC.md AS1 (`&& ;`, `&& &`, a `>` with no target,
each followed by an undecidable line) are not recorded as a threat: the shell
runs nothing for those forms, and the SPEC accepts the deny as a known cost.

Domain consistency: task0001 declares `input-handling`; its two guard files are
TB-1's boundary files. Its third file, the test module, carries test data only
and is no boundary.

## Trust Boundaries

### TB-1: Agent-issued Bash command text into the codex-hook-interactive-guard parser
Crossing: the command string of a Bash tool call issued by the Codex agent
(model output, which untrusted repository and prompt content can influence)
passes from the agent CLI process into the PreToolUse hook process on standard
input, where it is parsed statically to decide a deny or no output.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command whose `&&` / `||` right side holds only redirections, or whose last simple command before a `)` that closes a `(` group holds only redirections, leaves the list continuation open; a later undecidable fragment then yields no output, so an explicit interactive interpreter launch on an earlier line passes the guard and waits for input, stalling an unattended run (FR1, FR2, FR6; fail-open) | TM-1 | The list continuation ends at any separator other than `&&` / `||` that is not a newline or that ends a simple command holding a redirection, and at a `)` that closes a `(` group (the ordinary path and the rescue path) when the simple command it ends holds a redirection; the next top-level newline is then a checkpoint and the earlier launch is denied. Both copies carry the identical change (FR4) | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 item (TS1 to TS6, TS9 to TS13) |
| Denial of service | A fix that ends the continuation too eagerly — at a blank line, a comment-only line, a heredoc body, or a `)` with no redirection before it — turns a still-open list into a checkpoint and denies commands the shell never runs, blocking legitimate work (FR1, FR6, NFR4; SPEC.md AS3) | TM-2 | A newline that ends an empty command without a redirection, a heredoc body, and a `)` whose ended simple command holds no redirection leave the continuation as it was; every pre-existing case-table row keeps its verdict | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 item (TS7, TS8, TS14, TS15, TS21) |
| Denial of service | The guard runs on every Bash call with command text of any length; deciding the new clearing by walking groups, scanning back over the line or copying the command list at each newline or `)` would let a long command stall the hook (NFR1) | TM-3 | The new clearing reads only the separator and the redirection fact that the end of the simple command already reports; no parser state, no walk and no list copy is added | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, TM-3 item (TS19) |
