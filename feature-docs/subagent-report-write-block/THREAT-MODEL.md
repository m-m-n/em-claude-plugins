# Threat Model: subagent-report-write-block

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, the validator, the patch contract and the
implement protocol, at tier `full`. No auth surface exists. The domains
`input-handling`, `external-io` and `data-persistence` set a deep depth on the
validator boundary and the correction boundary. The journal is a machine-written
sibling of the worktree that crosses no boundary of its own and has no row.

## Trust Boundaries

### TB-1: Patch values to git
Crossing: `files`, `old_path`, `new_path` and the base commit, from worker output
and the command line, into a git process run by the validator and the entry script.
Boundary files: `em-workflow/scripts/validate-worker-output.py`, `em-workflow/scripts/report-name-entry.py`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A path shaped as an option, pathspec magic or a revision expression changes what git looks up, so a new matching name reads as an existing file and passes (FR3, NFR5) | TM-1 | A path reaches git without a shell, only after `is_safe_relative_path`, as literal text | task0001 AC-6, task0002 AC-7 | VERIFICATION.md TM-1 |
| Tampering | A base commit given as a revision expression or option moves the comparison to another tree (FR4, NFR5) | TM-2 | Only a full hexadecimal ID that resolves to a commit is accepted; anything else exits 2 | task0001 AC-5 | VERIFICATION.md TM-2 |
| Elevation of privilege | A patch with a matching name passes because the base input is missing or unresolvable (FR4) | TM-3 | A matching name with missing or unresolvable base input exits 2 and never passes | task0001 AC-5 | VERIFICATION.md TM-3 |

### TB-2: Correction proposal to orchestrator-owned state
Crossing: a worker's `path_corrections` and plan documents, into workflow.yaml and
the committed plan, as an exception to the verbatim copy of carried records.
Boundary files: `em-workflow/scripts/validate-worker-output.py`, `em-workflow/references/workflow-patch.md`, `em-workflow/references/workflow-schema.md`, `em-workflow/skills/develop/SKILL.md`
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A correction rewrites the record of a merged or in-flight task, or moves a path that is not a violation (FR5) | TM-4 | FR5 conditions 1 to 4 reject it, reading workflow.yaml, the journal and the base commit | task0002 AC-3, task0004 AC-2 | VERIFICATION.md TM-4 |
| Tampering | A plan document changes beyond path strings under the correction, altering an acceptance criterion with no review (FR5) | TM-5 | Condition 5 compares each document at the base commit with its current version after the same path normalization | task0002 AC-4, task0004 AC-2 | VERIFICATION.md TM-5 |
| Elevation of privilege | `path_corrections` is used to pass `replace_all`'s permission conditions or to move a step (FR5, FR6) | TM-6 | Admitted only in the states of IMPLEMENTATION.md D2; `step_patches` empty on the correction entry; an `in_progress` task stays rejected | task0002 AC-1, task0004 AC-1 | VERIFICATION.md TM-6 |

### TB-3: Implementer report to orchestrator
Crossing: the `write_rejection` field, from an implementer that reads untrusted
repository content, into the retry decision, committed `tasks.{T}.notes` and the
stop report.
Boundary files: `em-workflow/agents/implementer.md`, `em-workflow/references/implement-phase.md`
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A failure from another cause presents itself as a Write rejection, suppressing the retry it should get (FR8, NFR2) | TM-7 | The field is honored only on `status: failed` with a safe repository-relative path whose file name matches FR2; otherwise the failure is ordinary. The text is carried as data | task0006 AC-2 | VERIFICATION.md TM-7 |
| Information disclosure | The target path is reported as an absolute path under the home directory and lands in a commit and a stop report (NFR6) | TM-8 | The report states a repository-relative path; an absolute path is not honored and is not written to `notes` | task0005 AC-2, task0006 AC-2 | VERIFICATION.md TM-8 |

### TB-4: Subagent to Claude Code's Write validation
Crossing: a subagent's write, against the harness's rejection of matching names.
Boundary files: `em-workflow/agents/implementer.md`, `em-workflow/skills/worktree-task-workflow/SKILL.md`, `em-workflow/skills/plan-writing/SKILL.md`
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | The rejection is bypassed by a rename, another name, Edit creating the file, Bash, or the parent writing it (NFR1, FR7) | TM-9 | The implementer rule and the plan rule forbid each route; document contract tests pin them | task0001 AC-2, task0005 AC-3 | VERIFICATION.md TM-9 |
