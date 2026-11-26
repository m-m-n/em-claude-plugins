# Threat Model: dbracket-paren-group-spec-align

## Verdict
threats-identified

## Rationale
Inspected: this feature's SPEC.md (reduced tier, so no REQUIREMENTS.md and no
DESIGN.md), its change set (the dbracket-opener-arith-scan SPEC.md and
VERIFICATION.md, `tests/test_destructive_guard_args_json.py`,
`em-workflow/hooks/tests/destructive-guard-cases.json`) and the hook whose
judgment those documents and tests describe
(`em-workflow/hooks/destructive-guard.py`, unchanged under FR1 / NFR2).

The feature changes no runtime code, but it settles which judgment the hook's
input boundary is held to. Before the amendment, FR3 / AC-5 of the
dbracket-opener-arith-scan SPEC asked for KIND_NOTHING after
`[[ ( a == b ) && true ]]`; a change made to meet that text would exempt the
following notion call from inspection. TB-1 records that threat. task0001
declares `input-handling`, so TB-1 is analysed at deep depth, and its files
are among TB-1's boundary files.

The amended documents and the test files cross no further boundary: they are
repository files read by developers and by the test runners, and nothing in
them is executed as a command (NFR2).

## Trust Boundaries

### TB-1: Agent-issued Bash command string to the destructive-guard static judgment
Crossing: a Bash command string written by an agent (untrusted; it may carry a destructive command inside the `--args-json` of a notion call) enters the PreToolUse hook, which judges it by static analysis only.
Boundary files: `em-workflow/hooks/destructive-guard.py` (unchanged), `tests/test_destructive_guard_args_json.py`, `em-workflow/hooks/tests/destructive-guard-cases.json`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destructive command in the `--args-json` of a canonical notion call with `--session "$SID"` placed after `[[ ( a == b ) && true ]]` escapes inspection if the command-level reading is relaxed to read that form as certain, as the pre-amendment dbracket-opener-arith-scan SPEC asked (FR1, FR2, FR3, FR5, FR6) | TM-1 | The command-level reading stays as it is, so the form stays uncertain and the following notion call is inspected. A test and a deny case-table row pin `[KIND_INSPECTED]` and deny with reason ID `git-branch-force-delete` for that command. The dbracket-opener-arith-scan SPEC no longer asks for KIND_NOTHING after the form (planner amendment at create-plan). | task0001 AC-1, AC-2, AC-3 (AC-6 keeps the hook unchanged) | VERIFICATION.md, Performance / Security Verification, TM-1 (TS-1, TS-2, TS-4, TS-5) |
