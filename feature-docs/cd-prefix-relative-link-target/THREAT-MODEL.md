# Threat Model: cd-prefix-relative-link-target

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR5, NFR1-NFR3) at the `reduced` tier
(REQUIREMENTS.md and design subtracted). The feature narrows one refusal in
the cd-prefix path check of the PreToolUse hook `bash_guard.py`: a link
target that is relative is no longer refused on its text alone. That check
is part of a permission gate — its allow decision skips the user's
permission prompt — so relaxing it is a change at a trust boundary.
task0001 declares `auth` and `input-handling`, so the boundary is analysed
at deep depth.

The verdict holds because the relaxation opens one realistic path to an
unintended allow (TM-1) and the change itself risks loosening the check it
keeps (TM-2). Link loops and the followed-link bound are unchanged by this
feature (FR4) and add no new threat, so no Denial of service row is
recorded. The other two files of task0001 — the protocol document and the
test module — carry no trust boundary: neither is read by the hook at
decision time.

## Trust Boundaries

### TB-1: Agent-written cd path and in-area links into the hook's allow decision
Crossing: the `<path>` of a `cd "<path>" && <approved command>` Bash call,
written by an agent whose instructions may be attacker-influenced, together
with symbolic links inside the area that the same agent can create, cross
into the PreToolUse hook. The hook resolves the path in its own process and,
when the path check passes, allows a command that then runs in the Bash
process without a permission prompt.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | With relative link targets no longer refused on their text (FR1), a link inside the area whose relative target climbs to the root with `..`, or otherwise reaches, a location under /proc or /dev/fd makes the hook resolve that location against its own process, judge the path below the area, and auto-allow an approved command that Bash runs in a different directory (FR3, NFR2). | TM-1 | A relative target is joined to the directory that holds the link, and every stage reached from it — including the location left after each `..` — passes the existing per-stage /proc–/dev/fd check; the walk refuses at the first such stage, before probing anything inside /proc. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-3) |
| Elevation of privilege | Restricting the lexical target check to relative targets in the wrong direction, or removing it, lets a link whose absolute target is `/proc/self/cwd`, `/proc/self` or `/dev/fd/<N>` pass the path check (FR2, FR4). | TM-2 | The lexical check of the target text stays in place for every absolute target, and the existing absolute-target tests stay unmodified and pass. | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-4) |
