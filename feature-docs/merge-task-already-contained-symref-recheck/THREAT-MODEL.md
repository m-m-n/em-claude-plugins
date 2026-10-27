# Threat Model: merge-task-already-contained-symref-recheck

## Verdict
threats-identified

## Rationale
Inputs inspected: SPEC.md, REQUIREMENTS.md and the already-contained path of `em-workflow/scripts/merge-task.sh`. There is no DESIGN.md because the design step was skipped. The tier is full. task0001 declares input-handling, external-io and data-persistence, so TB-1 is analyzed at deep depth.

There is one trust boundary: the integration ref in the git ref store that all worktrees of the repository share. Another process with write access to that ref store can change the ref. The merge lock serializes only cooperating callers. It does not stop such a writer.

Two Tampering threats realistically apply at this boundary, and both mitigations come from SPEC.md FR1. No other STRIDE category gets a row, for these reasons:
- The ERROR line discloses only the branch name and an exit status.
- A writer that could block merges already holds direct ref-write rights, so the change adds no new denial path.

Accepted residuals (SPEC.md Assumptions; no mitigation is added here):
- A symbolic ref holding the same value may be placed between the re-check and the CAS. The CAS then replaces it with a direct ref that holds a commit containing the task, so no un-integrated task is recorded as `merged`.
- Ref rewrites after the CAS are treated like any rewrite after a merge. The actor already holds direct ref-write rights.
- On the fast-forward and merge-commit paths, a no-deref update can replace a symbolic ref whose old value matches. This stays the previous feature's accepted residual.

## Trust Boundaries

### TB-1: Integration ref in the shared ref store → merge-task.sh already-contained path
Crossing: the kind (symbolic or direct) and the value of `refs/heads/<integration branch>`, written by another process with write access to the same repository's refs, and read by merge-task.sh after it takes the merge lock. The outcome passes onward as a `merged` event in journal.jsonl and as the exit code that the implementer agent and the orchestrator act on.
Boundary files: em-workflow/scripts/merge-task.sh
Depth: deep (input-handling, external-io, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Between the post-lock symbolic-ref check and the parent-value read, the integration ref is replaced by a symbolic ref to the task ref. The exact lookup follows it, the already-contained path is taken, and an un-integrated task gets a `merged` event and exit 0 while the integration ref stays symbolic (FR1, FR2, FR6). | TM-1 | Right before recording `merged`, re-run the quiet symbolic-ref query on the exact integration ref. Status 0 (dangling included), or any status other than 0 and 1, ends the run with exit 2 and one ERROR line. The run makes no journal append, prints no `MERGED:` line and writes no ref (FR1 (1), FR2, FR3). | task0001 AC-1, task0001 AC-3 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Tampering | After the same swap, the integration ref is restored to its original direct value (one that does not contain the task), or deleted, before the re-check. A check of the kind alone then passes, although the parent value read earlier no longer matches the ref (FR1). | TM-2 | Once the re-check passes, run a same-value no-deref compare-and-swap of the integration ref against the parent value read under the lock, as the last git call before the journal append. Any failure ends the run with exit 2 and one ERROR line naming update-ref, with no journal append and no `MERGED:` line (FR1 (2), FR2, FR3). | task0001 AC-2 | VERIFICATION.md Performance / Security Verification: TM-2 |
