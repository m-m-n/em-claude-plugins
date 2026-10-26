# Threat Model: codex-hook-tty-reaper-pid-reuse

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR9, NFR1-NFR4, A1-A5, Security Considerations) and
REQUIREMENTS.md at tier `full`. The single task (task0001) declares
`input-handling`, `external-io` and `concurrency`; the first two set the depth
of the one boundary found to `deep`.

The hook runs with the user's privileges and sends SIGTERM / SIGKILL to
processes it identifies from the kernel process table. Which process holds a
given PID, and when, is decided by the lifetimes of processes the hook does not
control, so process identity crosses a trust boundary into the hook's
signalling decision (TB-1). Every recorded threat is the same kind of identity
confusion — a recycled PID standing in for the process the hook meant — at a
different point of the run; its effect is that an unrelated process of the
user is terminated.

Considered and not recorded:

- The single `ANCHOR` argument comes from the plugins' own `run_codex_exec.sh`,
  which this feature does not change (A2); it adds no new crossing.
- A process controls its own stat line (for example its command name). Stat
  parsing is not changed by this feature, and turning a crafted line against
  the start-time rule would additionally need the PID-reuse race of TM-1 to
  occur during the snapshot, which that process cannot arrange.
- Signals to processes of other users are refused by the kernel; the hook gains
  no privilege. The refusal is handled by the existing error rule (FR5).
- The hook prints nothing (NFR2), so nothing read from the process table is
  disclosed.

Residual: equal start times are adopted on purpose (FR1, FR6). A parent PID
recycled within the same start-time tick as its child cannot be told apart by
start time and remains accepted.

## Trust Boundaries

### TB-1: Process table and process lifetimes -> reaper target identity and signal delivery
Crossing: process identity data (PID, PPID, start time, state) read from the
kernel process table, whose values follow the lifetimes of processes the hook
does not control, crosses into the reaper's choice of which process receives
SIGTERM / SIGKILL; the signal then crosses back out to that process.
Boundary files: em-workflow/scripts/codex-hook-tty-reaper.py, em-review/scripts/codex-hook-tty-reaper.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A parent's PID is recycled while the snapshot is being taken, so a process unrelated to the anchor (and its whole subtree) is linked under a new process that is a descendant, and is signalled (FR1; SPEC.md AC-1) | TM-1 | Adopt a descendant link only when the parent's recorded start time is not later than the child's (equal is adopted); take the anchor's start time from the snapshot and stop nothing when the anchor is absent | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Spoofing | A PID on the hook's own ancestor chain is recycled, so an unrelated process stands in for an ancestor and corrupts the anchor validation and the exclusion of the hook's real ancestors (FR6; SPEC.md AC-4) | TM-2 | Check every ancestor-chain link with the same start-time rule; any link whose parent started later than its child stops the whole run from signalling | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Spoofing | The verified target exits and its PID is reassigned between the identity check and SIGTERM, so SIGTERM reaches the new process (FR2; SPEC.md AC-2) | TM-3 | Obtain a pidfd before the identity check, run the check while holding it, and send SIGTERM only through that pidfd; a target that fails the check is never signalled | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Spoofing | The target exits during the grace period and its PID is reassigned before SIGKILL, so SIGKILL reaches the new process (FR3; SPEC.md AC-7) | TM-4 | Hold the SIGTERM pidfd through the grace period, repeat the identity check, and send SIGKILL through the same pidfd; never open a second pidfd for a target | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Spoofing | Where pidfd is unavailable, falling back to PID-addressed signalling would re-open the windows TM-3 and TM-4 close (FR4; SPEC.md AC-5) | TM-5 | No fallback: when either pidfd function is missing or the kernel reports ENOSYS, send no signal and never use PID-addressed signalling | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |
