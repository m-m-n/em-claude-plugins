# Threat Model: codex-hook-tty-reaper-anchor-identity

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the workflow goal of this feature
(tier: full; the design step was skipped, so there is no DESIGN.md). The
change sits in the Codex Stop hook script (two byte-identical copies) and
its test module.

The hook reads the state of processes it does not control from the process
table at two points in time: the ancestor-chain read, then the snapshot.
That state belongs to other processes and the OS and can change between the
two reads (a process exits, its PID is reassigned). The process table is
therefore a trust boundary on the input side (TB-1). The hook then sends
SIGTERM / SIGKILL to processes it selected from that state, which is a
trust boundary on the output side (TB-2).

Depth: the single task (task0001) declares `external-io`, so both
boundaries are analysed at deep depth; it also declares `concurrency`,
which does not change the depth. Both boundaries list task0001's two script
files. The task's third file, the test module, is not a boundary file: it
drives the script in-process through the existing test seam and crosses no
boundary itself.

STRIDE: Spoofing applies at both boundaries (a different process occupying
a PID the hook trusts). Its consequence, an unrelated process being
stopped, is the denial-of-service outcome SPEC.md Security Considerations
protects against; it is recorded through the Spoofing rows, not as a
separate row. Tampering, Repudiation, Information disclosure and Elevation
of privilege have no realistic path here: the hook runs with the invoking
user's own privilege, writes nothing to stdout / stderr (NFR2), and keeps no
record that would need non-repudiation.

## Trust Boundaries

### TB-1: Process table read (other processes -> hook target selection)
Crossing: process-table state of processes the hook does not control (PID,
parent PID, start time, stdin terminal), read by the hook twice — during
the ancestor-chain read and again in the snapshot. Between the two reads
the anchor can exit and its PID can be reassigned to an unrelated process.
Boundary files: `em-workflow/scripts/codex-hook-tty-reaper.py`, `em-review/scripts/codex-hook-tty-reaper.py`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | An unrelated process X receives the anchor's PID after the ancestor-chain read. In the snapshot X stands in for the anchor, and X's later-started descendants whose stdin is on `/dev/pts/*` pass the parent-child start-time rule and the pidfd identity check, so they are selected and signalled (FR1, FR4; SPEC.md US1, AC1). | TM-1 | Carry the anchor start time read during the ancestor-chain read to the point after the snapshot. Before any target selection, pidfd opening or signal, require the snapshot entry for the anchor PID to exist and to carry exactly that start time (no tolerance; one tick is a mismatch). Otherwise stop nothing and end with exit code 0 and no output (FR1, NFR2). | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification TM-1 (TS-1, TS-2, TS-6) |

### TB-2: Signal delivery (hook -> other processes)
Crossing: SIGTERM / SIGKILL sent by the hook to the processes it selected
from the snapshot.
Boundary files: `em-workflow/scripts/codex-hook-tty-reaper.py`, `em-review/scripts/codex-hook-tty-reaper.py`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A signal addressed by PID after the anchor identity check reaches whichever process holds that PID at delivery time; a process that took the PID after the check would receive it (NFR4). | TM-2 | Add no PID-addressed signal delivery: every signal the hook sends keeps going through the existing pidfd path (NFR4). | task0001 AC-7 | VERIFICATION.md Performance / Security Verification TM-2 |
