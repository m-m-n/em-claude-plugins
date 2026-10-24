# Threat Model: codex-guard-funcname-anon-always

## Verdict
threats-identified

## Rationale
Inspected: the input of `codex-hook-interactive-guard.py` (both copies), the
`tool_input.command` string of a PreToolUse(Bash) JSON on standard input, and
the substitution reading (`_Parser._skip_substitution`) this feature changes.
Tier: full. Depth driver: task0001 declares `input-handling`, so TB-1 is
analysed deep.

The guard denies a launch of an interpreter or shell in interactive mode and
prints nothing when it cannot settle a command (fail-open by design). The
command text is produced by the Codex agent and can be steered by repository
content and prompts, so it crosses a trust boundary. A reading that stops
undecidable, or that places the close of a `$( )` in the wrong spot, lets an
interactive launch through, and the unattended run then stalls waiting for
input. The four threats below are the concrete ways this feature's reading
can fail that way. Each mitigation is made in both copies, which stay
byte-identical (FR6).

task0002 declares none of `auth`, `input-handling`, `external-io` or
`data-persistence`: it rewrites the `_skip_substitution` docstring and its
documentation tests and changes no reading, so it adds no boundary.

## Trust Boundaries

### TB-1: Codex-generated command string into the guard's substitution reader
Crossing: the `tool_input.command` text of a PreToolUse(Bash) JSON, written
by the Codex agent (model output that untrusted repository content can
steer), read by the guard process as shell text; this feature changes how
the `$( )` chunks of that text are read.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A `$( )` holding a multi-name `function` head with a keyword (`case`, a reserved word, a head word, `[[`, `esac`, `always`) after the second name makes the reader stop undecidable, so the hook prints nothing and the interactive launch after the substitution runs (FR1, AC1) | TM-1 | After the second name, every word other than a standalone `{` or `}`, an empty `()` and a separator is read as one more name; the reading right after the first name stays as it is (FR2) | task0001 AC-1 | VERIFICATION.md Performance / Security Verification TM-1 |
| Denial of service | `always`, `{` or `case` after the body of an anonymous function (`function { }`, `function () { }`, `() { }`) is read as a reserved word or at a command position, so the reader stops undecidable or puts the close of the substitution inside quoted text, and the launch is not denied (FR3, FR4, AC2 to AC5) | TM-2 | The `}` that closes an anonymous body sets no group-closed state and gives no command position; the words up to the next separator or the close of the list are arguments; a standalone `}` among them closes the innermost open `{` group of its list, and only an ordinary group's close lets a following `always` be a reserved word (FR5) | task0001 AC-2, task0001 AC-3 | VERIFICATION.md Performance / Security Verification TM-2 |
| Denial of service | The re-read of a `((` (rule 9) carries the further-name state, the anonymous-function states or the open `{` group records of the failed reading into the second reading, so the close is placed wrongly and the launch is not denied (NFR2) | TM-3 | The re-read returns the head state of the list that holds the `((` and the open `{` group records to their values at the `((` | task0001 AC-5 | VERIFICATION.md Performance / Security Verification TM-3 |
| Denial of service | A command with very many names or very many anonymous functions makes the new state tracking super-linear or recursive, so the hook exceeds its time or crashes and prints nothing (NFR1) | TM-4 | The reading stays one forward pass on the explicit stack; adding or removing an open `{` group record is constant work; nothing recurses | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-4 |
