# Threat Model: codex-guard-case-paren-rescue

## Verdict
threats-identified

## Rationale
Inspected REQUIREMENTS.md and SPEC.md as revised after review round 1 (tier:
full; the design step was skipped, so there is no DESIGN.md). The feature
changes only the parser of codex-hook-interactive-guard (the em-workflow and
em-review copies) and the guard's test table. The guard reads shell command
text proposed by the Codex agent — model-generated text that untrusted
repository or prompt content can steer — and answers deny or silent; that
crossing is the single trust boundary (TB-1). task0001 and task0002 both
declare `input-handling`, so TB-1 is analysed at deep depth.

Four Denial-of-service threats realistically apply at TB-1. Two concern the
case mark's lifetime in both directions: a pattern `)` read as the subshell
close because no mark refused the rescue (TM-1), and a mark that refuses the
rescue where it should not, or is dropped where it should stay (TM-3,
TM-4). The fourth is parser-cost blow-up from the per-word, per-group and
per-`)` work (TM-2). Spoofing, Repudiation, Information disclosure and
Elevation of privilege do not realistically apply: the guard holds no
identity, no secret and no audit duty, and grants nothing beyond its own deny
/ silent answer.

Post-decomposition check: both tasks declare `input-handling`; their guard
files are TB-1's boundary files. `tests/test_codex_hook_interactive_guard.py`,
also in both tasks' files, runs only in development and reads no external
input, so it is not a boundary file.

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
| Denial of service | A command whose case-pattern `)` follows a provisional group chain (review finding 5e71ff00fdbe5aff; FR1, FR2, FR3) makes the paren rescue read the pattern terminator as the close of the subshell just outside the chain, so a later stdin redirect is credited to an earlier interactive launch and the guard answers silent; the launch then runs with its input unconnected, which is exactly what the guard exists to stop, and the unattended run stalls | TM-1 | The innermost provisional group counts each bare command-position `case` (FR1), a provisional child fixes its inherited value from the parent alone (FR2), and the paren rescue is refused while either value is 1 or more (FR3): the pattern `)` closes the provisional group itself, so the redirect never reaches the earlier launch | task0001 AC-1, AC-2, AC-3; task0002 AC-5 | VERIFICATION.md, Performance / Security Verification: TM-1 |
| Denial of service | Long or deeply nested crafted command text makes the marking, the esac decrement, the inheritance or the paren check scan the open-group stack or recurse, so the guard's parse turns super-linear or exceeds the recursion limit and the hook stalls or crashes (NFR1) | TM-2 | Mark, run and after-`in` state change in constant time per appended word, the inherited value is fixed from the parent alone in constant time per opened group, and the paren check reads only the innermost group's two values; no recursion and no ancestor walk | task0001 AC-7; task0002 AC-7 | VERIFICATION.md, Performance / Security Verification: TM-2 |
| Denial of service | A mark that outlives its `case` (round 1 findings 285d9bc33784bb3d, df4afa83e782d56a), or a mark set on a `case` that follows a reserved word containing quoting or escaping (finding b374e6b3c3d4b471), refuses the paren rescue where the `)` genuinely closes the chain, so an unconnected interactive launch is answered silent (FR1, FR2, FR3) | TM-3 | The case mark is the number of unfinished `case`s and a bare `esac` at an FR1 position decrements the own mark first and the inherited value only when the own mark is 0 (FR1, FR2); only bare reserved words extend the leading run, so a quoted or escaped one leaves the following `case` unmarked (FR1) | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification: TM-3 |
| Denial of service | An `esac` that does not close the pending `case` — one in argument position, one containing quoting, escaping or expansion, or the inner `esac` of a nested `case` — drops the mark to 0 early, re-enabling the paren rescue so a later pattern `)` is read as the subshell close and the redirect is credited to the earlier launch (FR1, FR4) | TM-4 | The decrement fires only for a bare `esac` at an FR1 position, by one per `esac` and never below 0, and the mark holds a count rather than a yes/no value, so an inner `esac` leaves the outer `case` counted (FR1) | task0002 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification: TM-4 |
