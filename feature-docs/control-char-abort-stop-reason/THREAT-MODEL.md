# Threat Model: control-char-abort-stop-reason

## Verdict
no-applicable-threat

## Rationale
Inspected at the reduced tier (no REQUIREMENTS.md, no DESIGN.md): SPEC.md
(FR1-FR3, NFR1-NFR5, A1-A4), the "Precedence rule:" paragraph of
`em-workflow/references/batch-terminal-line.md` that task0001 edits, the
Control-character check of Step I.2.a in
`em-workflow/references/implement-phase.md` (left unchanged, A1), and the new
document test module. The only task declares `api-contract`; none of `auth`,
`input-handling`, `external-io` or `data-persistence` is declared, so the
analysis ran at standard depth.

Two existing trust boundaries sit next to the change: the batch structured
result handed to the external batch consumer, and the attacker-influenceable
worktree path (a link target whose name carries control characters) that
triggers the stop. The feature changes what crosses neither of them. It only
changes which member of the closed reason-code set the contract names for one
stop (`step_needs_intervention` instead of `unmapped_stop`, FR1). The `reason`
value is a constant the contract selects, not data derived from the path. The
check that rejects the path before any use, the `detail` and
`resume_conditions` rules, and the run's fail-closed end are all unchanged.
The new test reads a repository file only. No STRIDE category realistically
applies to the changed behavior.
