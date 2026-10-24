# Threat Model: self-write-exclusivity-window

## Verdict
threats-identified

## Rationale
Inspected SPEC.md, REQUIREMENTS.md and the documents the feature changes:
Rule R1 and the exclusivity section of `worker-envelope.md`, the
exclusivity section of `create-spec-phase.md`, "Layer 5 recording" of
`artifact-digest.md`, and the three dispatch sites. Tier: full. The tasks
declare `concurrency` and `data-persistence`; `data-persistence` sets deep
depth for the one boundary found.

The feature changes protocol text and document tests only; it adds no
runtime input path, network call or privilege change. It does, however,
define how the orchestrator decides what it records as a worker's output
while other local processes can still reach the integration worktree's
files. That crossing is a trust boundary, and Tampering applies to it. No
other STRIDE category realistically applies: no identity is asserted
(Spoofing), no audit claim is made beyond the recorded digests themselves
(covered by the Tampering rows), nothing confidential is handled, and a
spurious stale result only triggers the existing re-dispatch path.

The two new document test files read repository documents only and cross
no boundary. Every task that declares `data-persistence` has at least one
of its files in the `Boundary files` line below.

## Trust Boundaries

### TB-1: Integration worktree files between scope verification and the recording write
Crossing: file content of a self-write-set path written by a process other
than the orchestrator and the dispatched worker, entering the phase-state
`artifacts` record as that worker's output (another process → the
orchestrator's return-time procedure).
Boundary files: em-workflow/references/contracts/worker-envelope.md, em-workflow/references/phases/create-spec-phase.md, em-workflow/references/artifact-digest.md, em-workflow/skills/develop/SKILL.md, em-workflow/references/phases/create-plan-phase.md, em-workflow/references/rework-task-synthesis.md
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | An external rewrite of a self-write-set path after the scope verification is hidden by the self-write substitution and recorded at Layer 5 as the worker's output (FR1, FR2; SPEC AC-1, AC-6) | TM-1 | The orchestrator's return-time recheck in R1 "Order": after the comparison and before the recording write, each self-write-set path's current git blob id, mode and kind are compared with the values the same run's scope verification observed; a mismatch or a recheck that cannot run makes the result stale, and nothing is recorded. The citing documents place the recheck before the recording write (FR6, FR7). | task0001 AC-1, AC-2, AC-3; task0003 AC-2; task0004 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | A write in the window from the recheck to the recording write, or a same-path write by another actor before the scope verification, cannot be told apart from the worker's write; the documents end the exclusivity assumption at the scope verification, so this window is covered by nothing (FR3, FR4, FR5; SPEC Security Considerations) | TM-2 | Both statements of the exclusivity assumption extend its interval through the completion of the recording write (through the stale judgment for a stale result), and R1 "Known limit" states that the remaining window rests on that assumption. The assumption stays unenforced by lock or hook, as the SPEC states. | task0002 AC-1, AC-2, AC-4; task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 |
