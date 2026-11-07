# Threat Model: final-path-correction-medium-fixes

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md, the correction path of
`em-workflow/scripts/validate-worker-output.py` and
`em-workflow/scripts/report-name-entry.py`. The tier is full. The domains
`input-handling` and `external-io` on task0001 set the depth to deep on every
boundary below.

The feature hardens a validator that stands between a worker and the
orchestrator, so the worker's patch is the untrusted input. A planner that read
injected repository text can return any patch, and the correction dispatch runs
with no gate and no user question.

task0002 declares `api-contract` only, so its files sit on no `Boundary files`
line. `report-name-entry.py` reads `workflow.yaml` and the journal, which are
orchestrator-owned, and this feature adds no parsing to it. task0003 changes
documents only.

## Trust Boundaries

### TB-1: Correction patch to workflow state
Crossing: a `workflow_patch` and the plan documents returned by
implementation-planner, a worker that reads untrusted repository text, cross
into the orchestrator's application to `workflow.yaml` and its artifact commit.
Boundary files: `em-workflow/scripts/validate-worker-output.py`
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A correction dispatch, limited to path strings, registers a new task on arbitrary files through `tasks_patch.entries` (FR1, finding 73c084892e91326c) | TM-1 | An entry passes only when every file is regular at the base commit and holds an old reference there; otherwise `path-correction-entries` | task0001 AC-1 | VERIFICATION.md TM-1 |
| Tampering | The same patch excludes a requirement or edits its test mapping through `requirements_patch` (FR1) | TM-2 | Only `tasks_append` of ids under `tasks_patch.entries` passes; otherwise `path-correction-requirements` | task0001 AC-1 | VERIFICATION.md TM-2 |
| Tampering | A sentence placed in `new_path` is accepted as a path replacement and adds an instruction to a task (FR2, finding 7dad93fa93454f47) | TM-3 | Condition 4 rejects a `new_path` outside the FR2 form | task0001 AC-3 | VERIFICATION.md TM-3 |
| Tampering | A non-target plan is edited because condition 5 compares target plans only (FR3, finding 041b04abfc9d5b87) | TM-4 | Condition 5 covers every plan in `workflow.yaml`; a merged task's plan must be byte-equal to the base commit | task0001 AC-4 | VERIFICATION.md TM-4 |
| Tampering | A plan document created on the correction entry has no base version, so nothing compares it; `./VERIFICATION.md` hides the name (FR9) | TM-5 | A document absent at the base commit and present now is rejected; paths are compared after normalization | task0001 AC-4 | VERIFICATION.md TM-5 |
| Tampering | Text outside a path reference is rewritten by using two corrections' new names as interchangeable values (FR6, finding a848a53b57fb0188) | TM-6 | Comparison is positional: only a base occurrence may differ, and a replacement is literal and never rescanned | task0001 AC-6 | VERIFICATION.md TM-6 |
| Tampering | A re-planning body update adds a hyphen-less scenario ID to VERIFICATION.md under the scan skip (FR5) | TM-7 | The skip applies only on the correction entry | task0001 AC-5 | VERIFICATION.md TM-7 |
| Denial of service | Occurrences whose permitted texts are prefixes of each other make the alignment search grow exponentially (FR6) | TM-8 | The alignment search remembers visited states, over documents already bounded by the read limit | task0001 AC-6 | VERIFICATION.md TM-8 |

### TB-2: Patch path strings to git and the file system
Crossing: `files`, `old_path`, `new_path` and `plan` strings from a worker patch
reach git object reads of the base commit and reads of the integration worktree.
Boundary files: `em-workflow/scripts/validate-worker-output.py`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An entry file string acts as a git option, pathspec or revision in the new base read (NFR3) | TM-9 | Entry files are read only through `base_tree_entry` and `_read_base_document`, so the string never reaches git | task0001 AC-1 | VERIFICATION.md TM-9 |
| Denial of service | An entry names a huge or binary blob, which is loaded to search for a reference (FR1, NFR2) | TM-10 | The existing read limit applies before the blob is read; a file over it or not UTF-8 is rejected | task0001 AC-1 | VERIFICATION.md TM-10 |

### TB-3: Rendered plan text to the implementer prompt
Crossing: strings from a worker patch are written into a new task's plan, which
an implementer agent reads as its instructions.
Boundary files: `em-workflow/scripts/validate-worker-output.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A new task's plan carries instructions beyond the correction (FR1) | TM-11 | The plan must be byte-equal to the canonical text the validator renders, a TASK.md plan included | task0001 AC-2 | VERIFICATION.md TM-11 |
| Tampering | A newline or backtick in a rendered string breaks out of its line and adds text to the canonical plan (FR1) | TM-12 | Each file, `old_path` and `new_path` passes the FR2 form check before it is rendered; otherwise `path-correction-entries` | task0001 AC-2 | VERIFICATION.md TM-12 |
