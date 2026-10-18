# Threat Model: codex-guard-subshell-anon-arg-semicolon

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR10, NFR1-NFR4), the two copies of
codex-hook-interactive-guard and its test module. Tier: full. The one task
(task0001) declares `input-handling`, so the boundary it touches is analysed at
deep depth.

The guard has exactly one input: the command string of a Codex Bash tool call.
That string is written by an LLM agent whose context can carry untrusted
repository text, so it is attacker-influenceable, and the guard's verdict (deny,
or no output) decides whether the command runs. That crossing is the single
trust boundary, TB-1. The feature adds one new reading at TB-1: an unquoted `)`
may now rescue a chain of provisional groups and close the `(` group outside it.

No other boundary exists for this change: the guard reads no file, network
connection, environment variable or working directory and starts no process
(NFR3, unchanged and already pinned by the static-constraint test), and its deny
reason echoes no text from the command (existing behaviour this feature does not
touch). The test module lies outside the boundary; it holds the verification,
not the crossing.

At TB-1, Spoofing, Tampering, Repudiation, Information disclosure and Elevation
of privilege have no realistic threat for this change: the guard holds no
identity, writes nothing, keeps no record, discloses nothing new and grants no
privilege. What the guard protects is availability — a missed interactive launch
leaves an orphan REPL spinning after the terminal is gone, a false deny blocks a
legitimate call, and a slow parse stalls the call — so the threats recorded are
all Denial of service.

## Trust Boundaries

### TB-1: Codex Bash command string into the guard's parser
Crossing: the `tool_input.command` string of a Codex PreToolUse(Bash) call,
produced by an LLM agent and attacker-influenceable, crosses into the guard
process, whose verdict decides whether that command runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A crafted string with a deep chain of provisional groups, or many `)` after such a chain, makes the new check at `)` walk the chain or remove the same group more than once, so parsing turns super-linear and the hook overruns its time limit (NFR1, NFR2). | TM-1 | The check at `)` reads only the innermost group, its chain base and the values fixed when that group opened, in constant time; each provisional group leaves the stack of open groups at most once; no function calls itself. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-15, TS-16, TS-20) |
| Denial of service | A crafted string whose `)` the guard reads differently from zsh lets an interactive launch run unjudged — a launch inside the rescued chain, or after the subshell the `)` closes, attributed to a connected or skipped group, or left in a reading the guard reports as undecidable — and the orphaned REPL keeps spinning (FR1, FR2, FR6). | TM-2 | Commands read in the rescued chain stay commands of the closed `(` group, so only that group's own pipe, stdin redirect or function-body status reaches them; text after the close is read outside that group; a later `)` with no open `(` group is a separator, so a redirect after it connects nothing. | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-1 to TS-5, TS-13) |
| Denial of service | The new reading denies a command zsh would run without opening a REPL, blocking a legitimate Codex call (FR3, FR4, FR7, NFR4). | TM-3 | The `)` rescue fires only when the innermost open group is provisional, its chain meets the shared separator condition, and the chain base is a `(` group; every other `)` keeps its present reading. False denies are accepted only for the two inputs zsh 5.9 rejects as parse errors, each labelled as a known false deny. | task0001 AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-6 to TS-12, TS-14, TS-17) |
