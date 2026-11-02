# Threat Model: approval-unicode-whitespace

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR9, NFR1-NFR4, Security Considerations),
REQUIREMENTS.md, and the approval paths of
`em-workflow/scripts/merge-preflight.py` and `em-workflow/hooks/bash_guard.py`
that those requirements name. Tier: full. Task domains: task0001 `auth`,
`input-handling`, `api-contract`; task0002 `auth`, `input-handling`,
`data-persistence`; task0003 `api-contract`. Every boundary below is touched
by `auth` and `input-handling`, so all are analysed at deep depth.

The feature exists to close an approval-gate bypass, so the threats recorded
here are the ones the requirements already target; each cites its
requirement IDs. Three boundaries carry text that an attacker who can change
the repository, or an agent steered by such text, can influence into an
approval decision. Repudiation, information disclosure and denial of service
were considered and do not realistically apply: no identity or audit record
changes, no secret crosses these boundaries, and the only availability effect
— a padded command now needs approval or stops a batch run — is the intended
fail-closed outcome.

Post-decomposition consistency: task0001 and task0002 declare `auth`,
`input-handling` or `data-persistence`; their source files appear in the
Boundary files lines below. Their test files are not boundary files. task0003
declares none of the four depth domains.

## Trust Boundaries

### TB-1: repository-controlled command values into merge-preflight check 7
Crossing: the `*_command` values of `workflow.yaml` at the integration branch
tip (writable by anyone who can push to the repository) are compared with the
user-owned approved set read through `bash_guard.py --list`; a `proceed`
outcome lets the unattended merge flow run them.
Boundary files: `em-workflow/scripts/merge-preflight.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A value padded with a whitespace character other than space or tab before or after an approved absolute-path command is counted as that approved command, while Bash runs it as a different, work-tree-relative program (FR1, FR2; SPEC.md AC1, AC4) | TM-1 | Only spaces and tabs are trimmed; every value that is still non-matchable stops check 7 as `commands_unapproved`; the raw-value LF / CR exclusion stays | task0001 AC-1 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | A value made only of non-space/tab whitespace is skipped as empty, so a declared command never reaches check 7 and the run proceeds (FR3; SPEC.md AC9) | TM-2 | Only values empty after the space/tab trim are skipped; any other whitespace-only value is collected and stops as unapproved | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |

### TB-2: Bash tool command into the PreToolUse hook decision
Crossing: the command string of every Bash tool call — issued by an agent that
may be steered by repository text, or copied from a repository-controlled
`workflow.yaml` — is judged by the hook against the user-owned approval store
and against the commands declared in working-tree `feature-docs/*/workflow.yaml`
files.
Boundary files: `em-workflow/hooks/bash_guard.py`
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Non-space/tab whitespace, a trailing LF, or a backslash and LF around an approved string is trimmed away at the hook entry, so the hook allows a command that Bash runs as something else (FR1, FR4; SPEC.md AC2, AC4, AC6) | TM-3 | The hook entry trims spaces and tabs only; a non-matchable command never gets an allow from the exact-match or the cd prefix branch | task0001 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-3 |
| Elevation of privilege | The same padding inside the remainder of the cd prefix form is trimmed away, so the cd prefix allow is given for a remainder Bash runs as something else (FR5; SPEC.md AC3, AC6) | TM-4 | The remainder is trimmed by spaces and tabs only; a non-matchable remainder is never a cd prefix candidate and is excluded | task0001 AC-4 | VERIFICATION.md, Performance / Security Verification, TM-4 |
| Elevation of privilege | Declared-command extraction absorbs the padding, so a padded declared value is not recognised as declared, the hook gives no decision and the call falls through to the normal permission flow instead of the unapproved deny (FR8; SPEC.md AC2) | TM-5 | Key and value are separated by spaces and tabs only and the value is trimmed by spaces and tabs only; a padded value stays declared and the hook denies it as unapproved | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-5 |

Note on TM-5: `declared_commands` also puts into the declared set, in addition to the value trimmed of spaces and tabs, the value with every leading and trailing U+0020, U+0009, U+0085, U+2028 and U+2029 removed, when that result is not empty. Mismatches produced by YAML escape notation, by block scalars, and by characters inside the value are out of scope; such invocations reach the normal permission prompt.

### TB-3: approval-gate input and the stored approval set
Crossing: command lines that the orchestrator passes on stdin to
`bash_guard.py --record` / `--remove` (text derived from a
repository-controlled `workflow.yaml`), and the entries already present in the
user-owned approval store, become the approved set that the hook and
`--list` (and through it merge-preflight check 7) rely on.
Boundary files: `em-workflow/hooks/bash_guard.py`
Depth: deep (auth, input-handling, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | `--record` strips non-space/tab whitespace (including the CR of a CRLF line) before storing, so the stored approval differs from the string presented for approval and recorded in the batch audit trail (FR7; SPEC.md AC7) | TM-6 | `--record` and `--remove` refuse the whole input when any line is non-matchable after removing one trailing LF and trimming spaces and tabs: stderr report, exit code 1, store unchanged | task0002 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-6 |
| Elevation of privilege | A stored entry with non-space/tab whitespace at either end is trimmed into a different string and counted as approved by the hook, and listed by `--list` for merge-preflight (FR6; SPEC.md AC8) | TM-7 | `approved_for` trims spaces and tabs only and drops non-matchable entries; `--list` prints only the remaining entries | task0002 AC-1 | VERIFICATION.md, Performance / Security Verification, TM-7 |
