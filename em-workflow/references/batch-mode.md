# Batch Mode Protocol (em-workflow)

Referenced by `/em-workflow:develop` when the `--batch` flag is present.
This document covers the batch gates that carry NO `gate_id` at all. Any
gate that carries a `gate_id` — whether a worker returned it inside a
question packet or the orchestrator raised it directly outside of any
packet — resolves per `references/question-resolution.md`'s batch
resolution sequence against the policy table in
`references/batch-policies.yaml`; rework task synthesis is defined in
`references/rework-task-synthesis.md`. Phase protocols point to these three
documents rather than restating gate behavior.

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
  or fail). **The jurisdiction split is by gate-identifier presence, never
  by who presents the gate.** A gate that carries a `gate_id` — whether a
  worker returned it inside a question packet, or the orchestrator raised
  it directly outside of any packet (e.g. the `{phase}.artifact-overwrite`
  family, `references/contracts/spec-writer-contract.md`) — resolves per
  `references/question-resolution.md`'s batch resolution sequence and
  `references/batch-policies.yaml` (including that document's unlisted-gate
  fallback for a `gate_id` with no policy entry). A gate that carries NO
  `gate_id` at all resolves per the table below.
- Failure stops are UNCHANGED: batch mode removes confirmations on the
  success path, it never hides failures. Stuck steps, YAML errors, and
  post-cap failures still stop the run with a report — the external service
  reads that report and cuts a follow-up task.

## Non-packet gates

None of the gates below carries a `gate_id` at its originating site, so
none appears in `references/batch-policies.yaml` — the split is by
identifier presence, not by whether a worker or the orchestrator raises the
gate. A gate that DOES carry a `gate_id`, even one the orchestrator raises
directly outside of any worker's packet (e.g. the `{phase}.artifact-
overwrite` family), resolves per `references/batch-policies.yaml` instead —
see that file's `create-spec.artifact-overwrite`, `design.artifact-overwrite`
and `create-plan.artifact-overwrite` entries, one source of truth for all
three phases.

| Gate (interactive behavior) | Batch behavior |
|---|---|
| Step 0 git-setup (gitleaks missing → abort) | UNCHANGED — abort with report. Unattended environments must be provisioned up front |
| Step A feature resolution (interactive path takes the task description from the conversation) | Explicit feature-name/path argument wins — resolved to its `em-workflow/{feature}/integration` branch (re-materializing the worktree via `git worktree add` if it was removed). No path argument → always a new feature: batch create-spec from the task-description argument; no task description either → abort with report. Existing branches are never enumerated, and a feature is never guessed from them — resuming requires the explicit feature name |
| Review phase diff-size gate (`references/review-phase.md`) | Codex consultation per `references/question-resolution.md`'s unlisted-gate fallback procedure; no decision reached → take the option with the smallest / most reversible side effect and continue. Record the resolution in the run report |
| Per-command approval fallback used when the PreToolUse hook is inactive (`references/command-execution-protocol.md`, python3 missing) | Same as the diff-size gate above: Codex consultation, falling back to the minimum-side-effect option, recorded in the run report. Caches the resolution per literal command string within the run — matching the interactive fallback's per-literal-string cache in `references/command-execution-protocol.md` — so an identical command string is decided once, not re-consulted on every occurrence |
| `implement.failed-task` — Step I.2.c task failure after the parent-side-adoption protocol is exhausted (`references/implement-phase.md` Step I.2.c: retry / route-back-to-planning / abort via AskUserQuestion) | Auto-select **retry** once per task (kept worktree, I.2.a resume guard). A second failure on the SAME task → **abort phase** (`implement` stays `failed`). Route-back-to-planning is never taken automatically. Full detail: `references/implement-phase.md` Step I.2.c |
| `review.auto-fix-conflict` — Phase R4 conflict group (`references/review-phase.md`: one option per sibling + `Apply all` + `Skip this site`, via AskUserQuestion) | Skip the site — abort all group members; conflicting prescriptions are not mechanically resolvable. Full detail: `references/review-phase.md` Phase R4 |
| `review.auto-fix-judgment` — Phase R4 needs-judgment finding (`references/review-phase.md`: parsed alternatives or `Apply as-is` / `Skip`, via AskUserQuestion) | Auto-select **Apply as-is (editor interprets)**. Full detail: `references/review-phase.md` Phase R4 |
| `review.residual-critical-high` — Phase R5 completion gate when `residual_critical_high > 0` (`references/review-phase.md`: another round / rework / explicit acceptance, via AskUserQuestion) | Auto-rework once (`batch.review_rework_count` cap 1); at cap, mark residuals `deferred` with reason `"batch mode: rework cap reached"` and complete the step. Full detail: `references/review-phase.md` Phase R5 |
| `verify.failed` — verify-phase failure (`skills/develop/SKILL.md` 「verify フェーズ」: rework to implement / rework to review / abort, via AskUserQuestion) | Auto-rework once (`batch.verify_rework_count` cap 1); at cap, stay `failed` and stop with a report. Full detail: `skills/develop/SKILL.md` 「verify フェーズ」 |
| `develop.completion` — Step C completion choice (`skills/develop/SKILL.md` Step C: merge / keep branch / open PR, via AskUserQuestion) | Auto-select **keep branch** — no merge, no push, no PR created. Full detail: `skills/develop/SKILL.md` Step C |

The `{phase}.artifact-overwrite` family (`create-spec.artifact-overwrite`,
`design.artifact-overwrite`, `create-plan.artifact-overwrite`) is NOT a row
in this table — each carries a `gate_id`, so all three phases resolve
through `references/batch-policies.yaml` as one source of truth, even
though the orchestrator (not a worker packet) raises the question in every
case. See that file's entries, not this one.

Any other non-packet `AskUserQuestion` site not listed above, and for which
no phase protocol or `references/batch-policies.yaml` entry already states a
default, follows Codex consultation first, the minimum-side-effect option
when no decision is reached, never a silent stop on the success path. This
fallback NEVER overrides a default that a phase protocol or the policy file
already states for its own gate — the ten rows above (and every
`references/batch-policies.yaml` entry) always win over it. Failure stops
are unchanged per Purpose & activation.

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
