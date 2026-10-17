# Threat Model: codex-guard-brace-anon-arg-rescue

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md at the full tier (no DESIGN.md — the
design step was skipped). The feature changes how the guard's body reader
treats a lone `}` in the `zsh -c` command string it receives from a Codex
tool call. That string is model-generated and can be steered by untrusted
content the agent has read, so it is untrusted input crossing into the
guard (TB-1). The only task, task0001, declares `input-handling`, so TB-1 is
analysed at deep depth.

The guard is a preventive control for the unattended run. Its failure modes
at this boundary are a missed interactive launch (the run stalls), a
spurious deny (a legitimate command is blocked), and a guard that cannot
reach a verdict in time. All three are Denial of service against the
unattended run, so TB-1 carries three Denial-of-service rows. The change adds
no file, network or subprocess access and no dependency (NFR3), and the
guard's output is limited to a deny verdict or no output, so Spoofing,
Repudiation, Information disclosure and Elevation of privilege have no
realistic path at this boundary and get no row.

The residual misses and the spurious deny that SPEC.md accepts in its
Assumptions (the subshell form, FR7; a `}` with pending words in a
non-anonymous `{` group; a trailing extra `)`) are scope decisions recorded
there, not threats mitigated here.

Post-decomposition consistency: task0001 declares `input-handling`, and both
guard copies it modifies are listed under TB-1's Boundary files. Its third
file, the test module, implements no boundary.

## Trust Boundaries

### TB-1: Codex tool-call command string to the guard's command parser
Crossing: the Bash command text a Codex agent proposes (model-generated,
influenceable by untrusted content the agent read) arrives as hook input and
is read by the guard's body reader, whose verdict decides whether zsh runs it.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command wraps the rescuable argument-paren form (a provisional group whose first direct separator is `;` or a lone `&`) inside a `{ ...; }` group or an anonymous-function body. The guard reads the closing `}` as an ordinary word, the enclosing group stays open in its reading, and it gives no output, while zsh closes the group and runs the interactive launch after the separator, stalling the unattended run (SPEC FR1, FR2, FR4; REQUIREMENTS F01, F02, F04). | TM-1 | At a lone bare `}` whose innermost open groups form a qualifying provisional chain directly inside a `{` group, rescue the chain and close that group, then continue reading exactly as after a `; }` close. The same change is made in both copies (NFR2). | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | The new close path closes where zsh does not: a `}` that is quoted, part of an expansion, joined to other characters or a redirect target; a chain that fails the separator condition or has no separator; a chain not directly inside a `{` group; or a failed check that alters the open-group state. The guard's reading of later commands then diverges from what zsh executes, so a legitimate command gets a spurious deny or a later launch is read in the wrong group and missed (SPEC FR1, FR3, FR7; REQUIREMENTS F01, F03, F07). | TM-2 | Only a lone bare unquoted `}` word reaches the check. A non-qualifying chain leaves the `}` an ordinary word and changes no open group, separator record or recorded command. Every pre-existing CASES verdict is kept. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Denial of service | Input with a deep provisional chain (an unrescuable one included) followed by many `}` makes a per-`}` outward walk over the chain quadratic, or recursion over nesting depth exhausts the stack, so the guard overruns its time limit or crashes instead of reaching a verdict (SPEC NFR1). | TM-3 | Decide each `}` in amortized constant time from values fixed when each group opens; remove each provisional group at most once; use no recursion. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-3 |
