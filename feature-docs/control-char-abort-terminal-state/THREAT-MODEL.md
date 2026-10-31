# Threat Model: control-char-abort-terminal-state

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR5, NFR1-NFR4, assumptions A1-A5) at the `reduced`
tier (no REQUIREMENTS.md, design step skipped), and the places the change
lands: Step I.2.a's Control-character check and Step I.2.c's abort phase in
`em-workflow/references/implement-phase.md`, the `failed_kind` section of
`em-workflow/references/workflow-schema.md`, and the workflow state
`em-workflow/hooks/queue_stop_guard.py` reads. task0001 declares
`input-handling` and `concurrency`; `input-handling` sets TB-1 to deep.

One trust boundary applies. The canonical `worktree_path` is derived from
the filesystem, where an entry placed under the worktree area can be a link
whose target name carries control characters. This feature changes neither
the check nor its rejected set; it changes the state the phase leaves after
rejecting, which decides whether the rejection holds across turns. The
terminal write carries only constant values (the `implement` status,
`failed_kind`, the abort phase's commit subject) and the stop's report names
task IDs, so no path content reaches the write, the commit or the hook.

`em-workflow/references/workflow-schema.md` (a count in a schema document)
and the two test modules (which read repository documents) cross no trust
boundary and are not boundary files. The `concurrency` aspect — sibling
implementers launched by an earlier refill may still merge while the
terminal write is committed — involves only this feature's own processes
(same trust); it is covered by the `commit-docs.sh` tip check and exit-4
recovery the abort phase already uses, and no threat is recorded for it.

## Trust Boundaries

### TB-1: Filesystem-derived canonical worktree_path into implement-phase launch control
Crossing: the strict-realpath value of a task's worktree path, whose
characters come from filesystem entries under the project's worktree area
(any party able to create an entry there controls the link target name),
crosses into the orchestrator's launch decision, the implementer launch
prompt and the cd command.
Boundary files: `em-workflow/references/implement-phase.md`, `em-workflow/hooks/queue_stop_guard.py` (unchanged by this feature, NFR2; it reads the state the stop leaves)
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | After the check rejects a path, the `implement` step stays `in_progress`, so the queue Stop hook blocks the turn end and names the rejected task as a launch target; following that request launches an implementer whose prompt and cd command carry the control-character path, defeating the rejection (FR1, NFR2) | TM-1 | The stop takes Step I.2.c's abort-phase terminal handling at the check: one write setting the `implement` status to `failed` with `failed_kind` `decision`, committed through `commit-docs.sh`, so the hook (which only considers features whose `implement` step is `in_progress`) has no candidate and develop stops at stop condition 3 | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-5) |
| Denial of service | A terminal write carrying the external-cause value would let batch's `failed_kind` auto-resume re-enter the implement phase, meet the same rejection and abort again on each resume round (FR2; SPEC A2) | TM-2 | `failed_kind` is `decision` unconditionally on this path, so the batch auto-resume does not apply and stop condition 3 fires in both interactive and batch runs | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-1, TS-3) |
