# Threat Model: codex-guard-nested-bash-c

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, and the traversal and entry point of
the guard script (`find_deny`, `_scan`, `main`) in both copies, together
with the test harness that runs each copy as a separate process. Tier:
full. The guard's only input is the command string of one Codex Bash tool
call, read from standard input. That string is model-generated and can be
steered by repository content the model reads, so it is untrusted. task0001
declares `input-handling`, so TB-1 is analysed at deep depth. task0002
changes only the module docstring and the documentation tests; it crosses
no boundary.

Categories considered at TB-1 and not applicable: Spoofing and Repudiation
(the guard identifies no party and keeps no record), Tampering (the guard
holds no state and writes nothing, NFR1), Information disclosure (the deny
reason names only the matched interpreter name, which this feature does
not change), Elevation of privilege (the guard runs nothing; a pass leaves
the command exactly as it would run without the guard).

Residual risk, accepted by FR3 and NFR2: a launch placed in a
second-level-or-deeper string read after the re-read limit is reached
passes.

## Trust Boundaries

### TB-1: Codex Bash command string into the interactive guard hook
Crossing: the command string of one Codex Bash tool call, from the Codex agent process (model-generated, influenceable through repository content) into the guard process, whose verdict decides whether Codex runs the command.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | An interactive or program-less launch placed in a second-level-or-deeper shell `-c` string is not judged, passes the guard, and the REPL stalls the unattended Codex review (FR1, FR2) | TM-1 | Literal shell `-c` strings are judged at every level with the first-level rules, and the first launch to deny in judgment order is denied (IMPLEMENTATION.md T1-T4) | task0001 AC-1, AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Denial of service | A command with many or deeply nested `-c` strings makes the every-level traversal re-read text without bound or grow the call stack per level, so the hook overruns its time or ends in an error that `main` turns into a silent pass (FR2, FR3, NFR3) | TM-2 | Nested strings are walked with an explicit work list and no recursion, and the characters re-read from second-level-and-deeper strings are capped at 1,000,000 per command; strings past the cap pass unread and the cap is never a deny reason (IMPLEMENTATION.md T5-T7) | task0001 AC-4, AC-5, AC-6 | VERIFICATION.md Performance / Security Verification: TM-2 |
