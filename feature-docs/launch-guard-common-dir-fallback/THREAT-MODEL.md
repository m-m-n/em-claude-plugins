# Threat Model: launch-guard-common-dir-fallback

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md (FR1 to FR8, NFR1 to NFR5), the launch
guard hook and its two test modules. Tier: full. The single task declares the
domains `auth`, `input-handling` and `external-io`, which set a deep depth for
the one boundary below.

The launch guard is a PreToolUse permission hook. Its decision consumes the
launch payload (the cwd, and the worktree path from the task-assignment block,
which is orchestrator-authored text the project already treats as untrusted)
and the output of two existing git calls, which reflect on-disk repository
metadata the hook does not control. The feature changes only how that decision
is made on the segment-free path; it adds no input, no process and no write
(FR4, NFR3). Two STRIDE categories apply: denial of service through false
denials (the defect this feature fixes) and elevation of privilege through
over-allowing (a regression of what NFR4 keeps denied). Repudiation and
information disclosure do not apply: the journal and the denial message are
untouched. The two test files are not boundary files: they exercise the
boundary and carry no runtime input.

Residual risks accepted by the requirements as written, with no mitigation
invented for them:

- FR2 skips the cwd check whenever the derived root does not contain the
  worktree path. This also covers a worktree store placed outside the project,
  where a launch from any cwd is no longer denied (FR2, NFR2).
- A worktree path that is itself wrong (for example, one below the integration
  worktree) can satisfy FR3 from that worktree's cwd. The hook stays a net, not
  an authority: the orchestrator's own fail-closed gate on the assignment
  governs real launches (the hook's fail-open convention).

## Trust Boundaries

### TB-1: Launch payload and git-reported repository layout into the launch-guard permission decision
Crossing: from the Claude Code process into the hook, the PreToolUse payload's
cwd and the assignment block's worktree path (orchestrator-authored, untrusted);
from git into the hook, the common dir resolved at the worktree path and the
toplevel resolved at the cwd, both derived from repository metadata on disk
(a worktree's git pointer, submodule and separate-git-dir layouts). Both feed
the project-root derivation and the allow/deny decision.
Boundary files: em-workflow/hooks/queue_launch_guard.py
Depth: deep (auth, input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A layout the fallback was not written for — a common dir whose last element is not `.git` (submodule, separate git dir), a derived root that does not contain the worktree path, or a project root that is a linked worktree — makes the hook deny a correct launch on every attempt, stalling the implement phase, unattended batch runs included (REQUIREMENTS.md FR1, FR2, FR3, NFR2) | TM-1 | On the segment-free path only: a normalized common dir whose last element is not exactly `.git`, and a derived root that does not contain the worktree path, leave the root undetermined (no denial); the cwd check does not deny when the root contains the cwd's toplevel and that toplevel strictly contains the worktree path; no new exception escapes the hook, so every new outcome is exit 0 | task0001 AC-1, AC-2, AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Elevation of privilege | The widened no-denial conditions let a launch from a cwd other than the project root pass in the standard linked layout — the integration worktree or the task worktree itself as cwd — bypassing the denial NFR4 requires (REQUIREMENTS.md NFR4, FR5; SPEC.md A3) | TM-2 | FR3 requires both containments and strict containment of the worktree path, so a toplevel equal to the worktree path, or a toplevel the root does not contain, stays denied; FR2 skips only when the root does not contain the worktree path, which the standard linked layout never produces; FR1 to FR3 never run on the segment path; the existing denial tests are kept with their assertions unchanged | task0001 AC-3, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
