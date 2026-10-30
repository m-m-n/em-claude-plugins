# Threat Model: is-below-stalled-walk-proc-read

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, and the current stage walk and `is_below`
in `em-workflow/hooks/bash_guard.py`, together with
`tests/test_bash_guard_cd_prefix.py`. Tier: full. The single task (task0001)
declares `input-handling`, which sets TB-1 to deep depth; its other domain,
`api-contract`, does not deepen the analysis.

The feature changes how the hook process resolves a path written by an agent
and the link targets that agent can create. That input reaches the hook's
allow decision, so a trust boundary exists. Elevation of privilege and Denial
of service realistically apply to it.

Not covered here: the walk and the later realpath calls are separate reads of
the file system, so a concurrent change to the tree between them is not
addressed. This exists before the feature, and the feature does not change it.

The protocol text change (FR5) and the test additions (FR7, FR8) cross no
trust boundary. Domain consistency: task0001 declares `input-handling`, and
its boundary file `em-workflow/hooks/bash_guard.py` appears in TB-1's Boundary
files. Its other files (the protocol document and the test module) implement
no boundary.

## Trust Boundaries

### TB-1: Agent-written cd prefix path and link targets into the hook's path check
Crossing: the `<path>` of a `cd "<path>" && <approved command>` Bash call,
written by an agent that may be prompt-injected, and the targets of symbolic
links that agent can create. Both are resolved by the bash_guard.py hook
process with its own probes and link reads, and the result decides whether
the command is allowed.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A path whose stage walk stalls at an absent or regular-file stage, and whose lenient continuation climbs to /proc or /dev/fd, lets the later realpath calls resolve /proc/self/... against the hook process. The decision then rests on the hook process's own cwd or fds, not on what Bash resolves (FR1, FR2, NFR1, NFR2; SPEC A1, A5) | TM-1 | The stage walk continues past the stall under the lenient realpath rule. On both the logical-path walk and the physical-path walk, it refuses before probing at any stage under /proc or /dev/fd (the location left after `..` included) and at any followed link whose absolute target text is under one. A refusal makes `is_below` return False before any realpath call | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 (TS1, TS3) |
| Denial of service | After a stall, the walk follows links the agent planted. A link loop or a long chain reached only through the continuation could keep the walk running without bound, which stalls the hook and every Bash call it guards (FR4; SPEC A3) | TM-2 | Links followed after the stall count toward the same FOLLOWED_LINK_LIMIT as those followed before it, and exceeding the limit refuses | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-2 (TS6) |
| Elevation of privilege | An implementation of the continuation that also relaxes the walk before the stall, or that changes `is_below`'s order of checks or post-walk rule, could turn an existing refusal or a False into an allow for a path that is not an existing directory below the area (FR3, FR4, FR6, NFR1, NFR3) | TM-3 | Lenient handling of probe and link-read failures starts only at the first stall. Before it, errors other than an absent or non-directory stage still refuse. `is_below`'s order of checks and post-walk rule stay unchanged, with no pre-check added, so the change only adds refusals | task0001 AC-4, AC-5, AC-7 | VERIFICATION.md Performance / Security Verification: TM-3 (TS5, TS6, TS8) |
