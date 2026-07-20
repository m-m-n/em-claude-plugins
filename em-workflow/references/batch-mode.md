# Batch Mode Protocol (em-workflow)

Referenced by `/em-workflow:develop` when the `--batch` flag is present.
This document is the SSOT for every gate's batch behavior — phase protocols
contain only short pointers back here.

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
  or fail). Every interactive gate resolves per the decision table below.
- Failure stops are UNCHANGED: batch mode removes confirmations on the
  success path, it never hides failures. Stuck steps, YAML errors, and
  post-cap failures still stop the run with a report — the external service
  reads that report and cuts a follow-up task.

## Decision table

| Gate (interactive behavior) | Batch behavior |
|---|---|
| Step 0 git-setup (gitleaks missing → abort) | UNCHANGED — abort with report. Unattended environments must be provisioned up front |
| Step A feature selection (multiple candidates → AskUserQuestion) | Explicit path argument wins. No path + exactly 1 candidate → use it. No path + multiple → abort with report (never guess). No candidates → batch create-spec from the task-description argument; no task description either → abort with report |
| Command approval gate (AskUserQuestion → `--record`) | Auto-approve: pipe every unapproved workflow.yaml command into `bash_guard.py --record` without asking. Refusal patterns are UNCHANGED — hard fail, never recorded, never run. List every auto-approved string in the run report (audit trail) |
| create-spec interactive clarification (Phase 2, AskUserQuestion) | Codex consultation loop — see the batch section of `agents/requirements-spec-creator.md`. Decisions and unresolved defaults are recorded as Assumptions in SPEC.md |
| create-spec design-step decision (ambiguous → ask) | Decide autonomously (include it in the Codex consultation when one runs); record `skipped_reason` or leave `pending` as decided |
| planner TBD resolution (3-way ask) | Auto-select 仮定を置いて進める (`status: assumed`), record the assumption in the task plan and completion report |
| planner license conflict (3-way ask) | Auto-select 互換ライセンスの別ライブラリへ差し替える. If no compatible alternative exists, abort the phase with a report |
| planner existing-files re-run (3-way ask) | Auto-select 更新（マージ） |
| implement I.2.c failed task (retry / re-plan / abort ask) | Auto-retry ONCE per task on the kept worktree (I.2.a resume guard). A second failure of the same task → abort the phase: implement stays `failed`, drain in-flight tasks, report, stop. Never auto-route-back-to-planning |
| review R4 conflict group (one ask per group) | Skip the site (abort all members) — conflicting prescriptions are mechanically unresolvable without a human |
| review R4 needs-judgment (one ask per finding) | Auto-select `Apply as-is (editor interprets)` |
| review completion gate (residual critical/high > 0 → ask) | Auto-rework, cap 1: `batch.review_rework_count == 0` → synthesize rework tasks (below), increment the counter, set `review.needs_rework: true`, review step `pending`, implement step `pending`; the state machine re-enters implement. Counter already ≥ 1 → mark each residual finding `resolution: deferred` with `resolution_reason: "batch mode: rework cap reached"` and complete the step (the record keeps them visible for human evaluation) |
| verify fail (rework-destination ask) | Auto-rework, cap 1: `batch.verify_rework_count == 0` → synthesize ONE rework task from `failed_items`, increment the counter, set verify `pending`, implement `pending`. Counter already ≥ 1 → verify stays `failed`, report, stop |
| Step C merge proposal (AskUserQuestion) | Default: auto-merge into `base_branch` (cleanliness check UNCHANGED; dirty tree → abort with report, branch left in place). PR variant: when the task description or SPEC.md explicitly requests a pull request, do NOT merge locally — push the integration branch and open a PR against `base_branch` via `gh pr create` (title: feature name; body: run summary), leaving branch and worktree cleanup to the post-merge flow after the PR lands |

## Rework task synthesis

The ONLY case where the orchestrator adds tasks without the planner. For
review residuals: one task per affected file (group findings sharing a
file); for verify: one task covering `failed_items`.

1. Number the task as the next `taskNNNN` in sequence.
2. Write `feature-docs/{feature}/tasks/taskNNNN.md`: the finding(s) /
   failed item(s) verbatim (file, title, description, suggestion),
   and Acceptance Criteria = the finding no longer reproduces / the failed
   scenario passes.
3. Add the workflow.yaml `tasks` entry: `files` = the findings' files;
   `skills` / `domains` inherited from the existing task whose `files`
   overlap (empty when none); `complexity: low` (single-file fix) or
   `medium`; `requirements` = the FR/NFR IDs of the overlapping task.
4. Do NOT change `workflow[implement].base_commit` — the integration branch
   continues from where it is; the next review diffs the full range as
   usual.

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
create-spec/planning, auto-rework rounds consumed (review / verify), and any
deferred findings with their stable_ids. The external service relays this to
the human evaluator — it is the only confirmation surface batch mode has.
