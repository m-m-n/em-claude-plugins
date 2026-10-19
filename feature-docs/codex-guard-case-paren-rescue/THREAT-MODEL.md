# Threat Model: codex-guard-case-paren-rescue

## Verdict
threats-identified

## Rationale
Inspected REQUIREMENTS.md and SPEC.md (tier: full; the design step was
skipped, so there is no DESIGN.md). The feature changes only the parser of
codex-hook-interactive-guard (the em-workflow and em-review copies) and the
guard's test table. The guard reads shell command text proposed by the Codex
agent — model-generated text that untrusted repository or prompt content can
steer — and answers deny or silent; that crossing is the single trust
boundary (TB-1). task0001 declares `input-handling`, so TB-1 is analysed at
deep depth.

Two Denial-of-service threats realistically apply at TB-1: evasion through
the case-pattern `)` (the regression this feature removes) and parser-cost
blow-up from the new per-word, per-group and per-`)` work. Spoofing,
Repudiation, Information disclosure and Elevation of privilege do not
realistically apply: the guard holds no identity, no secret and no audit
duty, and grants nothing beyond its own deny / silent answer.
`tests/test_codex_hook_interactive_guard.py` runs only in development and
reads no external input, so it is not a boundary file.

## Trust Boundaries

### TB-1: Proposed command text into the interactive-launch guard
Crossing: the shell command string a Codex agent proposes (another process,
carrying model-generated text that untrusted content can influence) enters
the guard's parser through the hook's standard-input JSON; the guard's deny
/ silent answer decides whether the command runs.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A command whose case-pattern `)` follows a provisional group chain (review finding 5e71ff00fdbe5aff; FR1, FR2, FR3) makes the paren rescue read the pattern terminator as the close of the subshell just outside the chain, so a later stdin redirect is credited to an earlier interactive launch and the guard answers silent; the launch then runs with its input unconnected, which is exactly what the guard exists to stop, and the unattended run stalls | TM-1 | A case mark on the innermost provisional group at a bare command-position `case` (FR1), fixed in constant time onto provisional children along the chain (FR2), and no paren rescue for a group carrying either value (FR3): the pattern `)` closes the provisional group itself, so the redirect never reaches the earlier launch | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification: TM-1 |
| Denial of service | Long or deeply nested crafted command text makes the new marking, inheritance or paren check scan the open-group stack or recurse, so the guard's parse turns super-linear or exceeds the recursion limit and the hook stalls or crashes (NFR1) | TM-2 | The mark is set in constant time per appended word, the inherited value is fixed from the parent alone in constant time per opened group, and the paren check reads only the group's own two values; no recursion and no ancestor walk | task0001 AC-7 | VERIFICATION.md, Performance / Security Verification: TM-2 |
