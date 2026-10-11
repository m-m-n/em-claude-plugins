# Threat Model: codex-guard-extglob-funcname

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (reduced tier: REQUIREMENTS.md and DESIGN.md do not exist)
and the planned change: the function-name judgment of
codex-hook-interactive-guard.py in both plugin copies, plus its test file.
The guard's input is a shell command string that the Codex reviewer proposes
to run during an unattended review; the guard's deny / silent result decides
whether that command runs. The string is untrusted — it is produced by
another agent process whose context can include repository content under
review — so the guard sits on a trust boundary (TB-1). task0001 declares
`input-handling`, which sets TB-1's depth to deep. The test file is not on
the boundary: it only feeds fixed strings to the guard.

Post-decomposition check: task0001 is the only task and the only one
declaring a depth domain (`input-handling`); both guard copies in its files
appear in TB-1's Boundary files.

## Trust Boundaries

### TB-1: Codex reviewer command string into the interactive-launch guard
Crossing: a shell command string proposed by the Codex reviewer agent
(another process, whose context can include untrusted repository content)
enters the guard, whose deny / silent decision governs whether the command
runs inside an unattended run.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A word ending in an extglob operator character followed by `()` is read as a function name, so the group after it (for example an interactive interpreter launch after a newline) is left out of the judgment; Bash still runs that group, and the interactive process waits for input and stalls the unattended run. The misread occurs without a reserved word, after reserved words, with `function`, and inside a `bash -c` string (FR1, FR2, FR3). | TM-1 | The function-name judgment rejects a candidate name whose content ends in `?`, `*`, `+`, `@` or `!`, regardless of quoting, escaping or whitespace before `(` (SPEC.md assumptions A1, A3), so the group after `()` is evaluated in every form and at every nesting level | task0001 AC-1, AC-2, AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification item TM-1 (TS-1 to TS-5, TS-7, TS-8) |
