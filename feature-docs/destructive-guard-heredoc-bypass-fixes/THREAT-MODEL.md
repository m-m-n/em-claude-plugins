# Threat Model: destructive-guard-heredoc-bypass-fixes

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the workflow goal (findings
b0734a006de6f4d7, a7c0d90ac3e44e5b, f34ee27bc8c323b1). Tier: full. Every
task declares the `input-handling` domain, so the single boundary below is
analysed at deep depth.

The feature changes only how `em-workflow/hooks/destructive-guard.py` lexes
the Bash command string it judges. That string is the one input that crosses
a trust boundary: an agent produces it, the agent's output can be steered by
untrusted content or simply be wrong, and the hook's verdict is the control
that decides whether bash runs it without confirmation, unattended batch runs
included. Each of the three findings is a way to make the hook's reading of
that string differ from bash's reading, so each is recorded as Elevation of
privilege: a command the policy denies (or asks about) runs as if allowed.
The lexing work this feature adds is a second, Denial-of-service exposure on
the same input.

No other boundary exists: the feature adds no network access, persistence,
authentication or privilege change.
`em-workflow/hooks/tests/destructive-guard-cases.json`, which every task also
modifies, is project-owned test data read only by the test runner, never by
the hook at run time, so it is not a boundary file.

Spoofing, Tampering, Repudiation and Information disclosure get no row: the
hook authenticates no party, keeps no state the input could alter, records
nothing new, and returns only a verdict. The harm a bypass enables (destroyed
repository state) is captured under Elevation of privilege, the category of
the control being evaded.

## Trust Boundaries

### TB-1: Agent-proposed Bash command string into the destructive-guard verdict
Crossing: the command string of a Bash tool call crosses from the agent (whose
output can be influenced by untrusted content) into the hook's lexer; the
hook's allow / ask / deny verdict decides whether bash executes the string,
and under unattended execution ask is downgraded to deny.
Boundary files: em-workflow/hooks/destructive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A backslash-newline inside a word hides an array assignment or a builtin name from the hook, so the hook does not read the destructive line after the here-document operator the way bash does and allows it (FR1; finding b0734a006de6f4d7) | TM-1 | Judge assignment words and builtin names on the logical word (every in-word line continuation removed), keeping array and subscript start positions in original-input offsets | task0001 AC-1, AC-2, AC-4 | VERIFICATION.md Performance / Security Verification item TM-1 (TS1, TS2, TS12) |
| Elevation of privilege | `NAME[` in the arguments of a declaration builtin makes the hook defer the start of a pending here-document body, so a line bash executes falls outside what the hook inspects as a command (FR2; finding a7c0d90ac3e44e5b; regression from a baseline deny) | TM-2 | In declaration-builtin arguments, `NAME[` does not defer any pending here-document body; T2 E-9 keeps deny | task0002 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification item TM-2 (TS3, TS6) |
| Elevation of privilege | The same shape with eval / let / alias lets bash execute the hidden line while the hook allows it; folding these builtins into the declaration-builtin handling instead loses the deny of T2 E-1 (FR3) | TM-3 | Handle eval / let / alias as a separate group: forms measured on bash 5.3.9 to execute the hidden line return deny, while T2 E-1's deny and the `SUBSCRIPT_ARRAY_FORMS` reading are kept | task0002 AC-2, AC-3, AC-5 | VERIFICATION.md Performance / Security Verification item TM-3 (TS4, TS6, TS8) |
| Elevation of privilege | An outer and an inner eval that share the text before the parenthesis (`x=(@`) collapse into one extglob parse unit, so an extglob switch between them goes undetected and the command is allowed (FR4; finding f34ee27bc8c323b1) | TM-4 | Identify parse units by origin (top level or a specific eval / -c expansion) and position instead of by prefix text; the switch yields ask, downgraded to deny under unattended execution by the existing downgrade | task0003 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification item TM-4 (TS5, TS7, TS8) |
| Denial of service | The added logical-word tracking or parse-unit identity bookkeeping grows faster than linearly on a crafted command (many in-word line continuations, deep eval nesting), stalling the hook on a Bash call (NFR2) | TM-5 | Do both inside the existing single scan, charged to the existing `LEX_WORK_FACTOR` bound, without re-reading the input | task0001 AC-6, task0003 AC-4 | VERIFICATION.md Performance / Security Verification item TM-5 (TS8) |
