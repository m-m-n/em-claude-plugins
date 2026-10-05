# Threat Model: codex-guard-parser-fixes

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md of this feature (tier `full`), and the
task decomposition. The feature changes how the interactive-launch guard
parses one input — the command string Codex is about to run — and edits one
earlier SPEC document.

- task0001 declares `input-handling` and owns both copies of the guard, so
  TB-1 is analysed at `deep` depth.
- task0002 declares no domain and edits only
  `feature-docs/codex-interactive-guard-hook/SPEC.md`, a document read by
  people. It crosses no trust boundary and has no row here.
- The guard reads nothing besides that command string: no file, environment
  variable, network or child process (NFR2). TB-1 is therefore the only
  boundary.
- Only Denial of service applies at TB-1. The guard authenticates no one,
  records nothing, discloses nothing beyond its fixed deny message, changes
  no state and runs with the reviewer's own privileges. Its one
  security-relevant output is the verdict, and a wrong verdict costs
  availability: the review stalls on an interactive interpreter and leaves an
  orphaned process.
- False denials of legitimate commands are the feature's functional subject
  (FR3, FR4, FR5). They are not recorded as threats.

Accepted residual (by requirement, not mitigated here): input the parser
cannot follow is let through as indeterminate (NFR1), and the contents of a
command substitution are not judged (A1). An interactive launch placed
inside such a construct on purpose is therefore not denied.

## Trust Boundaries

### TB-1: Codex reviewer command string into the interactive-launch guard
Crossing: Codex is an LLM reviewer, and the untrusted repository content it
reviews can steer its output. The shell command text it is about to run
arrives as the guard's stdin JSON (`tool_input.command`) and crosses into the
guard's parser. The parser's verdict (deny / silent) decides whether Codex
runs the command.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | An interactive interpreter launch passes the guard because it is hidden in one of these shell forms: a `-c` option bundle, after `--` or a lone `-`, `-c` followed by a separate `-i` word, or a shell `-h` / `-V` read as an information display. The launch then waits for input, stalls the review and leaves an orphaned process (FR1, FR2). | TM-1 | Shells read `-c` as a flag that takes no value. Reading continues through the rest of the bundle and the later option words, and stops at `--` or a lone `-`. An `i` anywhere in them is denied, and the first operand is judged as the command string. Shells have no information short options, so shell `-h` / `-V` lead to the existing no-operand launch denial. | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, item TM-1 |
| Denial of service | A new relaxation reaches beyond its stated trigger, so an interactive launch that was denied before now passes. Examples: skipping a double-quoted substitution also swallows text after the closing quote; a group counts as connected because of a non-stdin redirect or because it is on the left of a pipe; a `-i` launch inside a connected group passes; a pending pipe survives a newline after `&&` / `||` (FR3, FR4, FR5, NFR1). | TM-2 | Each relaxation is limited to its stated trigger. Substitution skipping ends at the matching close, and ordinary parsing resumes after the closing quote. A group is connected only by a pipe on its left or by a stdin redirect after its close. `-i` launches are denied whether or not the group is connected. A pending pipe survives only empty commands after `\|` / `\|&`. The deny-side boundary cases are pinned in the shared case table. | task0001 AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, item TM-2 |
| Denial of service | Malformed or deeply nested input on the new reading paths makes the parser raise, run out of recursion depth or never finish. Such input includes unclosed or deeply nested substitutions inside double quotes, unbalanced or deeply nested groups, and long runs of empty lines after a pipe. The guard then ends with a traceback or a non-zero exit instead of a verdict, or stalls the command (NFR1). | TM-3 | Every new reading path terminates. Input it cannot follow (unclosed, unbalanced, or nested deeper than it follows) becomes the indeterminate outcome (no output, exit 0), never an exception or a non-zero exit. | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, item TM-3 |
