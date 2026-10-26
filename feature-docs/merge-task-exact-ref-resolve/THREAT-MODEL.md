# Threat Model: merge-task-exact-ref-resolve

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md at the reduced tier (REQUIREMENTS.md is absent by tier
reduction, DESIGN.md is absent because the design step was skipped) and the
post-lock section of `em-workflow/scripts/merge-task.sh` that SPEC.md names.
The only input this change touches is repository ref state that the script
reads inside the merge lock's critical section. That state lives in the
shared git common directory, so any other process with write access to the
repository can create, delete or repoint refs while a run waits for the
lock. This is the single trust boundary, TB-1. task0001 declares
`input-handling` and `external-io`, so TB-1 is analysed at deep depth.

The party at TB-1 already has write access to the repository and can move
the task branch itself (the feature goal's damage-and-condition note), so
Elevation of privilege and Information disclosure do not apply: the change
exposes no new capability and no new data. Denial of service does not apply
either: when this party makes a run fail closed with exit 2, that is the
intended outcome, not a threat. The recorded threats are the ways this
party can turn the script's fail-closed guarantee into a silent wrong merge
or a false `merged` record.

task0001's other files, `tests/test_merge_task_journal.py` and
`tests/test_merge_unverified_exit_doc_contract.py`, only exercise or pin
the boundary implementation and carry no boundary of their own.

## Trust Boundaries

### TB-1: Repository ref state written by other processes → merge-task.sh post-lock resolution
Crossing: refs in the repository's shared git common directory (the task
branch ref, the integration branch ref, tags, and any other ref under
`refs/`) cross from another process with write access to the repository
into the script's choice of merge source and parent value. That process can
create, delete or repoint them while the run waits for the merge lock. The
script then updates the integration branch ref and appends to the feature's
`journal.jsonl` based on that choice.
Boundary files: em-workflow/scripts/merge-task.sh
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | With the task branch deleted during the lock wait, a ref whose name is the task ref's full name under another prefix that ambiguous-name resolution tries (e.g. the tag `refs/tags/refs/heads/em-workflow/{feature}/{taskNNNN}`) stands in for the task ref. Its commit is merged as `merge: {TASK_ID}`, the run exits 0 and a `merged` event is written (FR1, FR2, FR6) | TM-1 | The merge source is resolved only from the task ref's exact full name. When that exact ref is absent, the run exits 2 with an ERROR line naming it, before any ref update, merge commit or journal append | task0001 AC-1 | VERIFICATION.md TM-1 (TS-1) |
| Spoofing | With the integration branch deleted during the lock wait, a same-named ref (e.g. the tag `refs/tags/refs/heads/{parent-branch}`) stands in for the parent. If it points at the task tip, the run exits 0 through the already-contained path and writes a `merged` event although nothing was merged (FR7, FR8) | TM-2 | The parent value is resolved only from the exact ref `refs/heads/{parent-branch}`. When that ref is absent, the run exits 2 with an ERROR line naming the parent branch, before the already-contained, fast-forward and merge-commit paths | task0001 AC-2 | VERIFICATION.md TM-2 (TS-3) |
| Tampering | The exact-ref lookup returns whatever object ID the ref holds and does not peel it to a commit. A task ref or integration ref rewritten directly to a non-commit object would pass a non-commit ID to the ancestry checks, merge-tree, commit-tree and update-ref (FR3, SPEC.md A3) | TM-3 | Both resolved values are confirmed to be commit objects before any of the three paths runs. Otherwise the run exits 2 with no ref change, no merge commit and no journal line | task0001 AC-3, AC-4 | VERIFICATION.md TM-3 (TS-4 and the parent non-commit check) |
| Tampering | Other processes can still move the task ref after it is resolved, because no lock covers the ref against them. If the paths re-read it separately, the integration branch could advance to a commit the ancestry checks never examined, or the `merged` event could name a commit other than the one merged (FR4) | TM-4 | One merge-source value is resolved and type-checked once, after the post-lock re-check. It is the only value the already-contained, fast-forward and merge-commit paths use, including their update-ref, journal append and output message | task0001 AC-5 | VERIFICATION.md TM-4 (TS-5) |
