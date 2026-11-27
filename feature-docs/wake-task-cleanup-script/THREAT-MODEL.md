# Threat Model: wake-task-cleanup-script

## Verdict
threats-identified

## Rationale
Inspected at the full tier: SPEC.md, REQUIREMENTS.md, the current Step I.2.b
step 4 and Step I.0 of `em-workflow/references/implement-phase.md`, the git
helpers in `em-workflow/scripts/merge-git.py`, and the guards
`destructive-guard.py`, `interpreter-mismatch-guard.py` and
`failed-run-cleanup-guard.py`. The feature adds a script that performs
destructive git operations from values the orchestrator passes in (task0001,
domains input-handling, external-io and api-contract), and changes the
orchestrator command that runs it (task0002, domains api-contract and
config-infra). The feature ID and task IDs come from a repository directory
name and a repository-controlled `workflow.yaml` (Step I.0 step 2), so they
are attacker-influenceable. The two boundaries below are where that data and
that command cross into git and into the PreToolUse guards. TB-1 is analysed
deep because its task declares input-handling and external-io. Information
disclosure and Repudiation were considered at both boundaries and do not
realistically apply: the script prints only validated names and git's own
refusal text to its caller, and it records nothing that another party relies
on.

## Trust Boundaries

### TB-1: Caller-supplied identifiers into destructive git operations
Crossing: the orchestrator passes the integration worktree path, the feature
name and the task ID to the cleanup script, which turns them into a worktree
removal and a branch deletion on the shared repository. Because git runs
inside the script, the PreToolUse guards never see those individual git
commands.
Boundary files: em-workflow/scripts/cleanup-task.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A crafted feature, task ID or integration worktree path (a path separator, a `..` segment, the value `integration`, an empty value, a leading hyphen) steers the removal or deletion to a worktree or branch other than the merged task's (the integration worktree and branch included, which `failed-run-cleanup-guard.py` otherwise protects), or is read by git as an option (FR5, TS-6) | TM-1 | Whole-string validation of the feature name and task ID with Step I.0 step 2's patterns and a shape check of the integration worktree path, all before any git command; any mismatch exits non-zero having run no git command; values reach git as separate arguments, never through a shell | task0001 AC-1 | VERIFICATION.md TM-1 (TS-6) |
| Elevation of privilege | With the git commands hidden from the guards, a forcing flag or a prune issued by the script would destroy unmerged commits or uncommitted work in the task worktree with no guard able to veto it (FR2, FR6, FR7) | TM-2 | A closed set of git operations: worktree listing, non-forced worktree removal, exact ref resolution and non-forced `branch -d` run from the integration worktree; no `-D`, `--force`, `-f` or prune anywhere; branch deletion is skipped when the worktree removal was refused | task0001 AC-4, AC-7 | VERIFICATION.md TM-2 (TS-7, TS-3) |

### TB-2: The orchestrator's step 4 command into script resolution and the PreToolUse guards
Crossing: the orchestrator (an LLM following `implement-phase.md`) builds a
Bash command for step 4; the command resolves a script path and passes the
PreToolUse guards, and the orchestrator then acts on the script's output,
which carries git's own refusal text.
Boundary files: em-workflow/references/implement-phase.md
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A same-named file in the project tree or the current directory runs in place of the plugin's script; the target repository is untrusted, and this repository itself carries a working copy of `em-workflow/scripts/` (FR4) | TM-3 | Step 4 resolves the script per Step I.0 step 4 (`${CLAUDE_PLUGIN_ROOT}/scripts/`, the trusted-root fallback, never the current directory); when it cannot be resolved nothing is invoked and no other location is tried | task0002 AC-1 | VERIFICATION.md TM-3 (TS-8) |
| Denial of service | The step 4 call line is judged `ask` or `deny` by `destructive-guard.py` or `interpreter-mismatch-guard.py`; in a batch run `ask` becomes `deny` and the unattended run stops (NFR2) | TM-4 | The call line is `python3`, the resolved script path and three options with literal values: no git command, no forcing flag, no shell variable as a target | task0002 AC-5 | VERIFICATION.md TM-4 (TS-9) |
| Tampering | After a kept or skipped result, a non-zero exit or an unresolvable script, the orchestrator composes its own git command (from the main tree, or the forced form that git's refusal message suggests) and deletes unmerged work, the failure this feature replaces (FR3, FR4, FR8) | TM-5 | Step 4 states that no git command, forced or not, is run in place of the script on any outcome, and that the reason texts are data whose suggested commands are never run; what was kept is written into the wake phase's own report | task0002 AC-2 | VERIFICATION.md TM-5 (TS-8) |
