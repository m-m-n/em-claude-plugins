# Threat Model: codex-guard-heredoc-delim-brace-case

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (reduced tier; REQUIREMENTS.md and DESIGN.md are absent
by tier reduction), the reading path this feature changes in
codex-hook-interactive-guard (the delimiter-position `${` handed by `_dollar`
to the braced reading of `_remove_range_quotes`, then `_read_quoted_unit`,
then `_skip_substitution`), and its test table. The feature changes how the
guard parses command text it receives from another process, so one trust
boundary exists. The single task declares `input-handling`, so the analysis
depth is deep.

Every threat recorded is Denial of service. The guard exists to stop an
interactive launch that would stall an unattended Codex review, and the ways
it fails are a missed deny or no answer at all. The other STRIDE categories
do not realistically apply. The guard only reads the command text and emits
either a deny or nothing. It executes nothing, stores nothing, holds no
secret and grants no privilege, and a command it does not deny runs with the
same rights it would have without the guard.

## Trust Boundaries

### TB-1: Codex tool-call command text → interactive-launch guard
Crossing: the `tool_input.command` string of the PreToolUse JSON that the
Codex hook passes on standard input. The Codex agent writes this string, and
repository content can steer that agent's output. The string goes into the
guard's static parser, which decides between a deny and no output.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A heredoc delimiter whose `${ ... }` holds an unquoted `$( ... )` with a case statement makes the guard register a different delimiter from zsh's. The real terminator line is then read as body, and the interactive launch after it gets no deny, so the interpreter waits on input and stalls the unattended review (FR1, FR2; regression stable_id 5b8947f11cc2c3b8). | TM-1 | In a delimiter's `${ ... }` range, an unquoted `$(` / `$((` is skipped by the case-aware substitution skip through the shared quoted-unit reader and kept as written, so the registered delimiter equals zsh's. Every other reading stays as it is (FR3). | task0001 AC-1, AC-3 | VERIFICATION.md TM-1 |
| Denial of service | The case-aware skip may fail to locate the close inside that range (no closing `esac`, or the skip ends past the range). If the guard then registers a guessed delimiter, or ends in an error other than the undecidable signal, the checkpoint reading is lost and a launch on an earlier line passes too (FR2, NFR3). | TM-2 | On an overrun or an unreadable skip, the new path ends only in the undecidable signal. The checkpoint rule then judges the lines up to the last checkpoint (an earlier launch is denied), and the rest gives no output. | task0001 AC-2 | VERIFICATION.md TM-2 |
| Denial of service | Command text with many or long delimiter `${ ... }` ranges that hold `$( ... )` could make the reading super-linear (a substitution read again) or recursive, so the hook runs past its time or fails and gives no answer (NFR1, NFR2). | TM-3 | Each `$( ... )` is skipped once and reading goes on after it, and an overrun ends the reading. The new path is the one-way chain range reading → shared reader → skip, with no recursion and no call cycle, and the skip is still called only from the shared reader. | task0001 AC-4, AC-5 | VERIFICATION.md TM-3 |
