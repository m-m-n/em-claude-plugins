# Batch Mode Protocol (em-workflow)

Referenced by `/em-workflow:develop` when the `--batch` flag is present.
This document covers the batch gates that never pass through a worker's
question packet. Gates keyed to a packet's `gate_id` resolve per
`references/question-resolution.md`'s batch resolution sequence against the
policy table in `references/batch-policies.yaml`; rework task synthesis is
defined in `references/rework-task-synthesis.md`. Phase protocols point to
these three documents rather than restating gate behavior.

## Purpose & activation

Batch mode exists for externally-triggered, unattended runs: an external
task-management service creates a task, marks it ready, and launches Claude
Code headlessly (e.g. `claude -p "/em-workflow:develop --batch <task>"`).
The human's job is reduced to: create the task, mark it ready, evaluate the
finished product. A rejected result becomes a NEW task — develop never waits
for a human mid-run.

- Active ONLY when the current invocation's arguments contain `--batch`.
  The `batch` block in workflow.yaml persists rework counters ONLY — it
  never activates the mode. A re-entry without `--batch` runs fully
  interactive again.
- In batch mode the orchestrator and every inline phase MUST NOT call
  `AskUserQuestion` (a headless run has no responder; the call would hang
  or fail). A gate carried in a worker's question packet resolves per
  `references/question-resolution.md` and `references/batch-policies.yaml`
  (including that document's unlisted-gate fallback for a `gate_id` with no
  policy entry). A gate that never passes through a question packet
  resolves per the table below.
- Failure stops are UNCHANGED: batch mode removes confirmations on the
  success path, it never hides failures. Stuck steps, YAML errors, and
  post-cap failures still stop the run with a report — the external service
  reads that report and cuts a follow-up task.

## Non-packet gates

None of the gates below is expressed as a question packet, so none carries
a `gate_id` and none appears in `references/batch-policies.yaml`.

| Gate (interactive behavior) | Batch behavior |
|---|---|
| Step 0 git-setup (gitleaks missing → abort) | UNCHANGED — abort with report. Unattended environments must be provisioned up front |
| Step A feature selection (multiple branches → AskUserQuestion) | Explicit feature-name/path argument wins — resolved to its `em-workflow/{feature}/integration` branch (re-materializing the worktree via `git worktree add` if it was removed). No argument + exactly 1 matching branch → use it. No argument + multiple branches → abort with report (never guess). Zero branches → batch create-spec from the task-description argument; no task description either → abort with report |
| Review phase diff-size gate (`references/review-phase.md`) | Codex consultation (same procedure as the create-spec batch loop, `agents/requirements-spec-creator.md`); no decision reached → take the option with the smallest / most reversible side effect and continue. Record the resolution in the run report |
| Per-command approval fallback used when the PreToolUse hook is inactive (`references/command-execution-protocol.md`, python3 missing) | Same as the diff-size gate above: Codex consultation, falling back to the minimum-side-effect option, recorded in the run report |

Any other non-packet `AskUserQuestion` site not listed above follows the
same rule as the two rows above: Codex consultation first, the
minimum-side-effect option when no decision is reached, never a silent stop
on the success path. Failure stops are unchanged per Purpose & activation.

## workflow.yaml `batch` block

```yaml
batch:                       # created by the orchestrator on the first
  review_rework_count: 0     #   --batch run that touches this feature
  verify_rework_count: 0
```

Counters only. Never used to decide whether batch mode is active (that is
the `--batch` flag's job, per-invocation).

## Reporting

The final report of a batch run MUST include, beyond the normal completion
report: every auto-approved command string, every assumption recorded during
create-spec/planning, auto-rework rounds consumed (review / verify), any
deferred findings with their stable_ids, every unlisted-gate fallback
resolution (gate / options / choice / Codex consulted or not), and the kept
integration branch name
with the take-over guidance (batch never merges — the human switches to the
branch in the main working tree and merges locally or pushes + opens a PR).
The external service relays this to the human evaluator — it is the only
confirmation surface batch mode has.
