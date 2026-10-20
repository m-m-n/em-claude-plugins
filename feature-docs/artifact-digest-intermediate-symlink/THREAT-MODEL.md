# Threat Model: artifact-digest-intermediate-symlink

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the goal recorded in workflow.yaml,
covering `em-workflow/scripts/artifact-digest.py` and the "Calculation"
section of `em-workflow/references/artifact-digest.md`. Tier: `full`.

The script receives path arguments from the orchestrator (write_policy
targets and worker-reported `written_artifacts`) and resolves them against
the integration worktree. Repository content can put symlinks in that
worktree, and another local process can create FIFOs or devices there or swap
components while the walk runs. The script reads with the orchestrator's own
privileges, and its digests feed write_policy decisions and layer-5 artifact
validation. This crossing is one trust boundary (TB-1). It is analysed at
deep depth because task0001 declares `input-handling` and `external-io`.
task0002 changes documentation text only and adds no boundary.

These were looked at and are not threats for this feature:
- A `..` component that climbs above the starting directory is out of scope
  (REQUIREMENTS.md A4, decision `keep_dotdot`). `..` is still opened without
  following a symlink, as every other component is.
- An absolute argument whose system prefix contains a symlink (for example
  `/proc/self/...`, or a temp root under a symlinked `/var`) now yields
  `not_a_regular_file`. This is the intended fail-closed outcome (A1).
- Spoofing, Repudiation and Elevation of privilege do not realistically apply.
  The script authenticates nothing, records no actions, and runs with the
  caller's privileges without changing them.
- The no-follow mitigation recorded in
  `feature-docs/worker-digest-ownership/THREAT-MODEL.md` is not edited (A6).
  This document records how this feature completes it.

Domain consistency after decomposition: task0001 declares `input-handling`
and `external-io`, and its boundary file `em-workflow/scripts/artifact-digest.py`
is listed under TB-1. Its only other file is a test file. task0002 declares
none of `auth`, `input-handling`, `external-io` or `data-persistence`.

## Trust Boundaries

### TB-1: Worktree filesystem objects into artifact-digest.py
Crossing: path arguments supplied by the orchestrator, and the filesystem
objects they name inside the integration worktree, cross into a reader that
runs with the orchestrator's privileges. Repository content or another local
process can make those objects symlinks, FIFOs or devices, or swap them during
the walk. The reader's stdout digests drive write_policy and artifact-validation
decisions.
Boundary files: em-workflow/scripts/artifact-digest.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A symlink at an intermediate component sends the walk outside the worktree. The digest of the out-of-tree regular file is then printed as if it belonged to the in-tree path (FR1, FR2; reproduced with `/proc/self/root/etc/hosts`). | TM-1 | Walk every argument one component at a time. Open each component relative to the previous directory descriptor, without following a symlink. A symlink at any component (to a directory, to a file, dangling or looping) makes that argument `not_a_regular_file`, with no digest on stdout (FR1, FR2). | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Tampering | A component is swapped for a symlink after the walk accepts it and before it is read, so the read lands on content reached through the symlink (FR5). | TM-2 | No separate check before the open: each component's descriptor-relative, no-follow open is itself the acceptance. The regular-file judgement is made on the descriptor that is actually read. A swap at any component produces an error token and nothing else (FR5). | task0001 AC-4 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Information disclosure | The platform may lack descriptor-relative open, the no-follow open flag or the directory-only open flag. A fallback to resolving the whole path would then quietly reopen the intermediate-symlink path (FR6, A5). | TM-3 | Check the three FR6 capabilities before processing any argument. If one is missing, write a message naming it to stderr, print no array and exit 2. Never fall back to resolving the whole path (FR6). | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-3 |
| Denial of service | A FIFO or device at an intermediate or final component blocks the open or the read, which stalls the orchestrator's digest step (FR5). | TM-4 | Every open in the walk is non-blocking. Intermediate opens accept directories only, so a non-directory fails at once (`missing`, FR3). The final element is judged to be a regular file on its descriptor before anything is read (FR1, FR3, FR5). | task0001 AC-3 | VERIFICATION.md Performance / Security Verification: TM-4 |
