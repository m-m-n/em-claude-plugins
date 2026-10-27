# Implementation Plan: merge-task-already-contained-symref-recheck

## Overview

On the already-contained path of `em-workflow/scripts/merge-task.sh`, re-check the integration ref right before `merged` is recorded (symbolic-ref re-determination, then a same-value compare-and-swap), and add tests that hit the gap between the existing post-lock check and the parent-value read. Requirements: SPEC.md FR1–FR6, NFR1–NFR5.

## Technology Stack

- **Script**: Bash — `em-workflow/scripts/merge-task.sh` (existing). Runtime requirements stay git 2.40 or later and util-linux `flock` (NFR5).
- **Tests**: Python 3 standard-library `unittest` (test/README.md), run as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. No license entry is recorded (`project.license: none`, and nothing new is introduced).

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Script | `em-workflow/scripts/merge-task.sh` | Behavior under change (already-contained branch and its comments only) |
| Behavioral tests | `tests/test_merge_task_journal.py` | Run the script as a subprocess against throwaway git repositories; inject ref races through a git shim placed first on PATH |
| Content-pin tests | `tests/test_merge_unverified_exit_doc_contract.py` | Pin the script's sha256 and the single-line "Parent already contains us" case name |

Dependency direction: tests reference the script by path; the script knows nothing about the tests.

## Shared Components

None. The feature is a single task (task0001), so no component is built by one task and consumed by another.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

## Conventions

These rules bind task0001 and any later rework task that touches the same files.

- **Rejection path**: every new rejection in merge-task.sh goes through the script's existing fatal-error path: exactly one stderr line beginning with `ERROR`, exit 2. The line names the integration branch. It never carries dirty-worktree wording (uncommitted / untracked / commit everything).
- **Case-name line pin**: the text "Parent already contains us" stays on exactly one line of merge-task.sh, and the line right after it stays the `merge-base --is-ancestor` check.
- **Forbidden comment phrases**: no comment in merge-task.sh contains "manual invocation", "merge-only" or "exercising only merge". The doc-contract module pins these phrases as absent.
- **Content pin**: every commit that changes merge-task.sh sets `EXPECTED_MERGE_TASK_SH_SHA256` to that commit's script content, in the same commit.
- **Test form**: standard library only, throwaway repositories under a temporary directory, merge-task.sh run as a subprocess. No kill / pkill / killall. Ref races are injected synchronously through the git shim. The lock-wait helper is used only when a change during the lock wait is needed.

## Cross-task Design Decisions

### D1: One task for the whole feature

- **Decision**: the script change, the content pin and the gap tests form one task.
- **Rationale**: FR5 requires the pin to change in the same commit as the script. FR6 requires the gap test to fail against the pre-change script and pass after it. A parallel split would leave each half unable to verify itself.
- **Affected tasks**: task0001.

### D2: Change boundary inside merge-task.sh

- **Decision**: only the already-contained branch gains code. These stay byte-for-byte unchanged: the existing post-lock symbolic-ref check before the parent-value read, the fast-forward path and the merge-commit path (NFR1, SPEC.md Assumptions). Comment updates are limited to the four locations FR4 names. They also cover any wording elsewhere in those comments that counts the integration ref's no-deref update-ref calls, so the count stays accurate.
- **Affected tasks**: task0001 and any rework task on merge-task.sh.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Comment edits break the existing line pin or forbidden-phrase pins | Medium | Low | Conventions above; run both test modules on every change |
| Content pin falls out of sync when several commits touch the script | Medium | Low | Each script-changing commit updates the pin itself |
| A shim-based race test passes vacuously because the shim never fired | Low | Medium | Each new test asserts how many times the shim acted, and the tests are run red against the pre-change script first |
| git's own diagnostic output adds extra error lines and makes the one-ERROR-line assertion ambiguous | Low | Low | The re-check's git calls do not pass their own diagnostics through to stderr |
| Residual: a same-value symbolic ref placed between the re-check and the CAS is replaced by a direct ref | Low | Low | Accepted per SPEC.md Assumptions; see THREAT-MODEL.md Rationale |

## Open Questions

- None.
