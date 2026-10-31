# Threat Model: canonical-worktree-path-guards

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the two consumers this feature changes
— the launch guard hook (stdin JSON from the harness: the task-assignment
prompt's `worktree_path` line and `cwd`) and the stale-launched identity
binding in the recovery script (the Agent index entry's recorded
`worktree_path` read from `agents.jsonl`, and the `--task-worktree` argument
supplied by the orchestrator). Tier: full. Domains declared by the tasks:
`input-handling` and `external-io` (launch guard), `input-handling` and
`auth` (identity binding), `api-contract` (invocation-contract wording);
the first three set a deep analysis on the two boundaries below.

Two changes introduce new behaviour at a boundary: the launch guard gains a
git subprocess run in a directory named by prompt-carried text, and the
binding replaces a plain equality with link resolution of two
externally-supplied path values. Both are analyzed below. The
invocation-contract wording change in `em-workflow/references/implement-phase.md`
is trusted plugin text consumed by the orchestrator and crosses no new
boundary. Test modules are not boundary files.

Not analyzed as separate threats: a local actor able to plant links inside
the project already has write access to the journal and the Agent index, so
link planting adds no capability; layouts whose link resolves outside the
main worktree and link targets that recreate the
`/.claude/worktrees/em-workflow/` segment are out of scope per SPEC.md
(Edge Cases) and REQUIREMENTS.md 1.3. Spoofing and Tampering of the launch
guard's own decision are not recorded: the guard is a fail-open net, a wrong
derived root can only produce a deny (fail-closed for that launch), and the
orchestrator protocol stays authoritative.

## Trust Boundaries

### TB-1: Launch guard — prompt-carried worktree_path to a git subprocess
Crossing: the `worktree_path` line of the task-assignment block (text written
by the orchestrator session into the subagent-launch call, delivered on the
hook's stdin) becomes the working directory of a new
`git rev-parse --path-format=absolute --git-common-dir` process whose output
determines the project root (FR2).
Boundary files: em-workflow/hooks/queue_launch_guard.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | The fallback git call runs inside a synchronous PreToolUse hook on every implementer launch; a call that hangs, fails to start, exits non-zero or prints nothing would stall or crash the launch, and in batch mode nobody can answer a stuck session (FR2, NFR2, NFR4) | TM-1 | The fallback runs only when the segment is absent, is `git rev-parse` only, is bounded by the existing `GIT_TIMEOUT_SECONDS`; a start failure, timeout, non-zero exit or empty output leaves the project root undetermined, the cwd check is skipped and the hook exits 0 with no output | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-1 |

### TB-2: Stale-launched binding — recorded and supplied worktree values to link resolution
Crossing: the Agent index entry's `worktree_path` (a JSON value in
`agents.jsonl`, written by another hook from launch-prompt text) and the
`--task-worktree` argument (or the equivalent function-level parameter)
are resolved through the filesystem's links and compared; the result gates
whether the recovery chain may reach `recovered` and invoke the journal
helper (FR4, NFR3).
Boundary files: em-workflow/scripts/recover-orphaned-task.py
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Once the comparison resolves links (FR4), an empty or relative value on either side would be resolved against the script's working directory, so an entry that names no real worktree could bind to the supplied `--task-worktree` (or the reverse) and let the chain reach `recovered` (FR4, NFR3) | TM-2 | Both values must be non-empty strings that are absolute paths before any resolution happens; otherwise the binding fails as `agent-identity-unproven` and the journal stays byte-identical | task0002 AC-3 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Denial of service | A malformed recorded value (non-string, embedded NUL) or an error raised while resolving either side escapes the script as an exception instead of a residual, ending the reconcile step's call with a traceback (FR4, NFR3) | TM-3 | The type check precedes resolution; every OS-level or invalid-value error raised while resolving either side is a binding failure (`agent-identity-unproven`); no exception leaves the script and the journal stays byte-identical | task0002 AC-4 | VERIFICATION.md Performance / Security Verification: TM-3 |
| Spoofing | Rewriting `resolve_bound_stop_target` could let the recorded session identity, or one of several candidates, become the stop target (FR4) | TM-4 | Candidates come only from `agent_ids`, exactly one distinct candidate is required, `--stop-target` must equal it, and the function's source text (docstring included) contains no `session_id` token | task0002 AC-6 | VERIFICATION.md Performance / Security Verification: TM-4 |
