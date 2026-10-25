# Threat Model: merge-task-post-lock-rebind

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (FR1–FR7, NFR1–NFR4, A1–A5) at the reduced tier (no
REQUIREMENTS.md, no DESIGN.md) and the single planned task, task0001, whose
domains are concurrency, input-handling and config-infra; input-handling sets
TB-1 to deep depth. The feature has one trust boundary: the task worktree's
checkout state, which another local process using the same worktree can change
while merge-task.sh waits for the merge lock. What crosses it decides which
commit reaches the integration branch and which task the journal credits, and
two STRIDE categories realistically apply there.

Repudiation, information disclosure, denial of service and elevation of
privilege have no realistic path at TB-1: a rejection is the intended
fail-closed outcome, and the script gains no input, output channel or
privilege (NFR2). The new regression tests build only throwaway repositories
and inspect only the test's own child process, so they cross no trust
boundary.

## Trust Boundaries

### TB-1: Task worktree checkout state during the merge-lock wait
Crossing: the worktree's HEAD (the checked-out branch, or a detached HEAD) and the verified task ref, changeable by any other process using the same task worktree, read by merge-task.sh after the pre-lock identity binding and used to pick the commit merged into the integration branch and the task credited in the journal
Boundary files: em-workflow/scripts/merge-task.sh
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | After the pre-lock binding passes (FR1), another process switches the worktree to a different branch or detaches HEAD during the lock wait; that branch's tip is merged as the verified task and credited with its `merged` event (FR2, FR7) | TM-1 | Post-lock re-check of HEAD's symbolic ref against the verified task ref, placed as FR2 and FR3 order it; a different ref, a detached HEAD or an unresolvable HEAD ends in exit 2 (NFR1) | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | The checkout changes again after the post-lock re-check, so a merge source read through HEAD would put a commit from an unverified branch into the integration branch (FR4, A3) | TM-2 | Merge source resolved from the verified task ref instead of HEAD and used on every merge path; an unresolvable ref ends in exit 2 before any ref update or journal append (FR4, NFR1) | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 |
