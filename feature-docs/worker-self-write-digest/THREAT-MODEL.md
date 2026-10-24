# Threat Model: worker-self-write-digest

## Verdict
threats-identified

## Rationale

Inspected: REQUIREMENTS.md, SPEC.md (FR1–FR11, NFR1–NFR6), workflow.yaml, and
the documents and scripts the feature changes or relies on: worker-envelope.md
Rule R1, the designer / planner / rework-planner contracts, workflow-patch.md
application rule 1, phase-state.md, create-spec-phase.md "Scope verification",
artifact-digest.md, create-plan-phase.md, rework-task-synthesis.md section 10,
the develop skill's 「design ステップ分岐」, validate-worker-output.py's
`--dry-run-apply`. Tier `full`; the design step is `skipped`, so no DESIGN.md
was an input.

The feature relaxes the return-time staleness check: paths a worker changed
are given their dispatch-time digest when the change counts as a self-write.
Whatever decides that membership is therefore a gate between an LLM worker
(whose inputs include untrusted content) and the orchestrator's acceptance of
its result, and the persisted record of that decision feeds the resume
decision later. Both are trust boundaries with realistic threats, so the
verdict is `threats-identified`.

Depth is `deep` for both boundaries: task0001 declares `input-handling`;
task0002 declares `data-persistence`; task0003 declares `data-persistence` and
`input-handling`.

Post-decomposition consistency: every task declaring one of the four depth
domains has at least one file on a `Boundary files` line. Files of those tasks
that are on no such line, and why:

- `em-workflow/references/contracts/designer-contract.md`,
  `planner-contract.md`, `rework-planner-contract.md` (task0002) only cite
  Rule R1 and name overlapping paths; the decision itself is stated and made
  elsewhere.
- The three new test modules run against temporary directories or read
  documents; they take no worker output and authorize nothing.

SPEC.md's Security Considerations records no protected asset (Not
applicable); this document states how the staleness check can be broken and
how the design prevents it, citing requirement IDs only.

## Trust Boundaries

### TB-1: Worker changes and worker-reported paths to the return-time staleness decision
Crossing: files the worker created or modified in the integration worktree,
including file names it chose under an allowed write root, and the path list
in its `written_artifacts` cross from the worker (an LLM subagent fed untrusted
content) into the orchestrator, which decides from them which digest inputs
take their dispatch-time value and whether the result is accepted as not
stale.
Boundary files: em-workflow/scripts/self-write-digest.py,
em-workflow/references/contracts/worker-envelope.md,
em-workflow/references/workflow-patch.md,
em-workflow/references/phases/create-plan-phase.md,
em-workflow/references/rework-task-synthesis.md,
em-workflow/skills/develop/SKILL.md
Depth: deep (input-handling, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | The worker lists in `written_artifacts` a digest input it did not change (for example `SPEC.md`), claiming a change from elsewhere as its own so that it receives the dispatch-time digest and staleness goes undetected (FR2, FR4) | TM-1 | Membership requires presence in the change set the orchestrator observed in the scope verification; `written_artifacts` is not an input of the identification | task0001 AC-1, task0002 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | The worker changes a digest input beyond what its `write_policy` action permits — modifies an existing file covered only by an allowed write root, writes a `preserve` target, regenerates a target whose `source` did not change, or deletes a target — and the substitution hides the change from the staleness check (FR3, FR4) | TM-2 | The per-action membership matrix admits only permitted change kinds (allowed write roots: creation only; `preserve`: never; `regenerate`: only with its `source`; deletion: never); a non-admitted change keeps its current digest and makes the result stale | task0001 AC-1, task0002 AC-1 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Elevation of privilege | A file name the worker chose under an allowed write root (for example a new `tasks/` file) carries shell metacharacters and, carried by the observed change set, is interpolated into the command the orchestrator runs for the self-write script, executing commands with the orchestrator's permissions (FR10) | TM-3 | The script takes its whole input as one JSON document named by a single argument; the orchestrator writes that document with its file-writing tool outside the integration worktree, never through shell interpolation, and no path from it ever appears on the command line | task0001 AC-7, task0002 AC-1 | VERIFICATION.md Performance / Security Verification, TM-3 |

### TB-2: Persisted phase-state records and on-disk artifacts to the resume decision
Crossing: the dispatch-time map and the self-write set persisted in
`phase-state/*.yaml`, and the artifact files in the integration worktree —
both editable by the user or another process between an interruption and the
resumed run — cross into the orchestrator's resume decision (whether the
recorded input is still current and whether a pending patch may be applied).
Boundary files: em-workflow/references/phase-state.md,
em-workflow/references/contracts/worker-envelope.md,
em-workflow/references/phases/create-plan-phase.md,
em-workflow/references/rework-task-synthesis.md,
em-workflow/skills/develop/SKILL.md,
em-workflow/scripts/self-write-digest.py
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A self-written artifact is edited after its digest was recorded and before a resumed run; the resume comparison substitutes its dispatch-time digest, so the edit goes unnoticed and a stale plan or patch is accepted (FR6, FR7) | TM-4 | The resume keeps comparing artifact bodies with their recorded digests; `self_write_set` is written in the same phase-state write as the run's layer-5 `artifacts` entries, so every substituted path has a recorded digest that comparison checks | task0002 AC-4, task0003 AC-1, task0003 AC-3, task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 |
