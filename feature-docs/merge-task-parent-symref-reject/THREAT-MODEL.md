# Threat Model: merge-task-parent-symref-reject

## Verdict
threats-identified

## Rationale
Inspected REQUIREMENTS.md and SPEC.md at the full tier (the design step was
skipped, so there is no DESIGN.md). The feature changes one boundary-facing
script, `em-workflow/scripts/merge-task.sh`. The input it newly guards is the
state of the integration ref `refs/heads/<parent-branch>` (a direct value or a
symbolic ref) as left by any other process that can write the same
repository. task0001 declares `concurrency`, `external-io` and
`input-handling`; `input-handling` and `external-io` set TB-1 to deep depth.
The verdict holds because that ref state is controllable by a concurrent
writer and, before this feature, decided which branch the script's update-ref
moved and whether a `merged` event was recorded.

Not analysed as new boundaries:
- The caller-supplied arguments (parent branch, task id), HEAD and the task
  ref are validated by the pre-existing identity binding and the post-lock
  HEAD re-check, which this feature leaves unchanged (task-ref side:
  REQUIREMENTS.md 14.1; pinned by TS-7).
- task0001 also lists `tests/test_merge_task_journal.py` and
  `tests/test_merge_unverified_exit_doc_contract.py`; they implement no
  boundary and so are absent from the Boundary files line. The test-only git
  shim they introduce lives under `tests/` at the repository root, which is
  not part of the distributed plugin.

Accepted residuals (recorded threats with no mitigation in this feature):
- A re-point of the integration ref after the TM-1 check and before the
  already-contained ancestor check can still lead to a `merged` record,
  because that path performs no update-ref (REQUIREMENTS.md 1.3 and 14.1 put
  it out of scope).
- Under TM-2, a re-point after the TM-1 check whose referent equals the old
  value may let update-ref replace the symbolic ref itself with a direct ref;
  the referent is not moved (SPEC.md Assumptions).

The acting party already holds direct write access to refs, so no row is
recorded for Elevation of privilege; forcing an exit 2 is not a new Denial of
service capability for a party that can already delete the ref.

## Trust Boundaries

### TB-1: Integration ref state shared with other repository writers
Crossing: the content of `refs/heads/<parent-branch>`, written by another
process with write access to the same repository (before the run, during the
merge-lock wait, or between the script's checks and its ref update), is read
by merge-task.sh and decides which ref its update-ref moves and whether it
records `merged`.
Boundary files: em-workflow/scripts/merge-task.sh
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A symbolic ref placed at the integration ref before the run or during the lock wait makes the parent value resolve through it: the fast-forward / merge-commit update-ref then moves the referent branch (e.g. main) instead of the integration branch, or, when it targets the task ref, the already-contained path records `merged` for a task that was never merged (FR1, FR4; SPEC.md AC-1 to AC-6) | TM-1 | Under the merge lock and immediately before the parent value is read, merge-task.sh asks git whether the integration ref is itself a symbolic ref; a symbolic ref (dangling included) or an undeterminable answer ends the run with exit 2 and one ERROR line naming the integration branch, before any merge path, update-ref, merge-tree, commit-tree or journal append, leaving every ref unchanged (FR1, FR2, FR3, FR4) | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification item TM-1 (TS-1 to TS-5, TS-9) |
| Tampering | After the TM-1 check passes, the integration ref is re-pointed to a symbolic ref targeting another branch right before update-ref; a dereferencing update-ref whose old value matches the referent then moves that branch (FR7; SPEC.md AC-8) | TM-2 | Both update-ref calls on the integration ref (fast-forward and merge-commit) use the no-deref option and keep the old-value comparison against PARENT, so a symbolic ref placed after the check is never followed to its referent (FR7) | task0001 AC-4 | VERIFICATION.md Performance / Security Verification item TM-2 (TS-8) |
