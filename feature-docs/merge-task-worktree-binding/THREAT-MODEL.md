# Threat Model: merge-task-worktree-binding

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md FR1-FR8 and NFR1-NFR4, REQUIREMENTS.md, and the current
identity binding of `em-workflow/scripts/merge-task.sh` (the layout check that
today applies only inside the em-workflow layout and lets every other
invocation merge unbound). Tier: full. The single boundary below is analysed
at deep depth, driven by task0001's `input-handling` domain; task0001's
`api-contract` domain does not change the depth.

The feature's only trust boundary is the invocation of merge-task.sh by an
implementer agent. The caller is not adversarial, but its working directory,
its arguments and its checked-out HEAD are not guaranteed to be what the task
plan intends: the incident recorded in workflow.yaml's goal came from a working
directory that had drifted back to the main working tree. This model therefore
treats those three inputs as untrusted and analyses the integrity of the shared
integration branch and of the feature journal.

Categories with no row: Information disclosure (the script reads no secret and
prints only branch names, commit ids and paths the caller already holds);
Denial of service (a rejection refuses only invocations that are not the named
task's own, and the retry path of implement-phase.md I.2.b runs in the task's
own worktree, SPEC.md A5); Elevation of privilege (the script runs with the
caller's own privileges, and the caller can already update any ref directly;
the guard addresses accidental misuse, not a privilege boundary).

task0002 declares no domain and edits only a citation in
`em-workflow/references/implement-phase.md` and a phrase constant in a test
module; it crosses no boundary.

## Trust Boundaries

### TB-1: Implementer invocation -> merge-task.sh (shared integration branch and feature journal)
Crossing: the working directory, the two positional arguments (parent branch,
task id) and the checked-out HEAD state of the calling implementer agent's
shell (another process, LLM-driven, whose working directory can drift between
tool calls) cross into merge-task.sh, which holds the authority to advance the
feature's integration branch ref shared by every task and to append the
`merged` event that the orchestrator's failure net reads from the feature
journal.
Boundary files: em-workflow/scripts/merge-task.sh
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A worktree that is not the named task's own (the main working tree, the feature's integration worktree, or a worktree outside the em-workflow layout) is accepted as that task, and its HEAD is merged under the task's name (SPEC.md FR1, FR4; the incident in workflow.yaml goal). | TM-1 | Reject with exit 2 unless the worktree's top-level directory has the em-workflow task layout and its last segment equals the task-id argument; the check runs before the merge lock, the clean-tree precondition and any merge or ref update. | task0001 AC-1, AC-3 | VERIFICATION.md TM-1 (TS1, TS2, TS3, TS8) |
| Tampering | Inside the task's own worktree, a HEAD that is not the task branch (detached HEAD, another branch checked out) is merged into the integration branch, bringing in unrelated history (FR3, FR4). | TM-2 | Require HEAD's symbolic ref to equal the task branch's full ref derived from the worktree path and the task id; otherwise reject with exit 2 before the lock. | task0001 AC-2, AC-3 | VERIFICATION.md TM-2 (TS4, TS5, TS8) |
| Tampering | A failure to resolve the top-level directory or HEAD's symbolic ref is read as "no binding applies", so the merge proceeds unbound; this is the fail-open path the current script takes (NFR1). | TM-3 | Treat every resolution failure as a rejection (exit 2), never as permission to merge. | task0001 AC-2, AC-4 | VERIFICATION.md TM-3 (TS4, TS9) |
| Tampering | The parent-branch argument names a branch other than this feature's integration branch (for example the base branch), and that branch is advanced; today this is possible for every invocation outside the layout, where no parent check runs (FR2). | TM-4 | Every accepted invocation is inside the layout, so the existing check that the parent argument equals the integration branch derived from the worktree path applies to every merge. | task0001 AC-1, AC-5 | VERIFICATION.md TM-4 (TS1, TS6) |
| Repudiation | A run exits 0 without appending its `merged` journal event, so the merge leaves no attributable record and the failure net records a merged task as failed (SPEC.md Objectives, FR1, FR5). | TM-5 | Exit 0 is reachable only after the layout binding passes, so the journal home is always derivable; the best-effort append and its warning on failure stay as they are. | task0001 AC-1, AC-4, AC-5 | VERIFICATION.md TM-5 (TS3, TS6, TS10) |
