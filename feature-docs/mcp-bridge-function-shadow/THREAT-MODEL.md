# Threat Model: mcp-bridge-function-shadow

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`, so SPEC.md is the requirements source; no
REQUIREMENTS.md, no DESIGN.md) and the notion-pair exclusion of the
`mcp-bridge run --args-json` step in `em-workflow/hooks/destructive-guard.py`
that the SPEC changes, together with the readers it builds on: the
command-name override reading, the current-shell substitution reading, the
chunk derivation links and the chain walk of the nameref answer, and the
notion-path readings task0002 adds (the statically restored command word, the
env reading of a child shell payload, the static-run match). Both tasks
(task0001, and task0002 from the review round 1 rework) declare
`input-handling`, so the one boundary below is analysed at deep depth.

This re-planning pass follows the SPEC.md revision of the NFR1 / AC9 / TS-16
baseline. That revision changes how the existing unittest suite is compared,
not what crosses the boundary, so the boundary and its threats are unchanged.

The feature closes a bypass of a security gate: each threat below is the
goal's attack scenario in one of its forms (FR1 to FR4, with the decision of
FR5), or the regression the change could cause (legitimate notion calls turned
into denies or asks, or a hook evaluation that fails on deep nesting; FR6, FR7,
NFR1, NFR2). Mitigations exist only for those recorded threats.

TM-2 also counts `trap`, `mapfile` and `readarray`, which FR2 does not list.
Each runs a string as code in the current shell, so
`trap 'mcp-bridge() { :; }' DEBUG` defines the function inside the command
itself, which is the goal's attack scenario. The nameref reading of the same
notion-pair decision already counts these command words as leaving the shell
state unknown. This is the plan's only addition to the construct set of FR1 to
FR3.

Accepted residual risks, recorded and not mitigated here (outside FR1 to FR3):

- PATH set through a form the override reading does not read: `env PATH=...`
  in front of the command, a `PATH=` word of `declare`, `typeset`, `local` or
  `readonly`, and `read` or `printf -v` into PATH. FR1 pins the reading to
  `_overrides_command_name()`. Each form needs an executable named
  `mcp-bridge` placed in the new PATH.
- A startup file of the shell that runs the notion call as a `-c` payload
  (`BASH_ENV=` or `ENV=` on that statement). It needs a file placed
  beforehand.
- A function-import variable name split by an expansion (`${P}FUNC_...`,
  `BASH_FU${x}NC_`). FR3 is a substring match; the scan reads each word's raw
  text, its whole restored value and its static runs, so a name written in
  decodable ANSI-C quoting is read (TM-3), but no static run holds a name
  split by an expansion.
- A notion call whose command word cannot be restored statically, such as a
  locale quote (`$"mcp-bridge"`). The `--args-json` step does not take such a
  statement as an `mcp-bridge run` statement for any pair, so no lift applies
  to it; the notion path restores the command word only when it can be
  restored statically (TM-1).
- The substring match of FR3 and `BASH_CMDS` also reads the notion statement's
  own value words, so a comment body that names `BASH_FUNC_`, `BASH_ALIASES` or
  `BASH_CMDS` and also writes a destructive command inside `$( )` or backticks
  is denied. SPEC.md Assumptions accept the false positives of the substring
  match.
- Shell state set by an earlier Bash tool call (SPEC.md Assumptions).

Domain consistency: task0001 and task0002 each declare `input-handling` and
list `em-workflow/hooks/destructive-guard.py`, the boundary file of TB-1.
Their other files (the runner case table and the unit-test module) hold tests
only and implement no boundary.

## Trust Boundaries

### TB-1: Bash command text into the destructive-guard notion-pair exclusion
Crossing: a Bash command string written by the agent, whose output can be
steered by untrusted text it has read, crosses into the hook's static
analysis. The hook decides whether the command runs unattended. For a
notion-pair `mcp-bridge run` statement it decides whether the `--args-json`
value is inspected at all, while the shell decides at run time what the name
`mcp-bridge` runs.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A function definition of any name or form, `alias` / `hash` / `enable`, a PATH assignment or a `BASH_CMDS` word in the command makes the name `mcp-bridge` run other code, while the hook excludes the notion-pair statement's `--args-json` value, so a destructive top-level `command` runs unchecked (the goal's attack scenario; FR1, FR4, FR5) | TM-1 | The notion-pair exclusion is lifted when any FR1 construct stands in the statement's chunk or in any chunk of its enclosing chain, before or after the call; the statement is then read, decoded and inspected like every other pair. On the notion path a command word that restores statically to `mcp-bridge` (ANSI-C quoting) is read as `mcp-bridge`, and `BASH_CMDS` is matched in the static runs of a word | task0001 AC-1, AC-3; task0002 AC-1, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | A statement that runs a string as code in the current shell (`eval`, `source`, `.`, `trap`, a `mapfile` / `readarray` callback), a current-shell substitution (`${ cmd; }` and its pipe-sign form) or a command name that cannot be read statically defines `mcp-bridge` out of the hook's sight (FR2, FR4) | TM-2 | Such a statement in the statement's chunk or its enclosing chain lifts the exclusion; `trap`, `mapfile` and `readarray` count together with the three FR2 command words | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Elevation of privilege | A function or alias imported through the environment (`BASH_FUNC_name%%`, `BASH_ALIASES`) into the shell that runs the notion call, for example a `bash -c` payload (FR3, FR4) | TM-3 | A word in the statement's chunk or its enclosing chain that holds `BASH_FUNC_` or `BASH_ALIASES`, in its raw text, its restored value or one of its static runs, lifts the exclusion; a `bash -c` payload reached through `env` by a path, after a lone `-` or after an ANSI-C `=` is read as a derived chunk of the statement's chunk; the two words stay out of the shared override and masking-stop vocabularies | task0001 AC-1, AC-6; task0002 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-3 |
| Denial of service | Lifting the exclusion too widely turns legitimate notion-comment calls into denies or asks, which stops unattended runs (FR6, FR7, NFR1) | TM-4 | Quoted strings, comments and data heredoc bodies do not match FR1 / FR2; the raw-candidate skip, the override and heredoc data decisions and the masking stop are unchanged; a lifted call with a harmless decoded value stays allow; the existing notion-pair allow cases stay allow; the readings task0002 adds apply only on the notion-pair path and set no Unrestorable flag | task0001 AC-3, AC-4, AC-6; task0002 AC-2, AC-5 | VERIFICATION.md, Performance / Security Verification, TM-4 |
| Denial of service | A deep nest of substitutions makes the chain decision recurse past the interpreter limit or repeat its scan for every statement, so one hook evaluation fails or runs past its timeout (NFR2) | TM-5 | The answer is computed once per chunk and kept, and the chain is walked in a loop without recursion | task0001 AC-5 | VERIFICATION.md, Performance / Security Verification, TM-5 |
