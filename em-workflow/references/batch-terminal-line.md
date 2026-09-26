# Structured Result Contract (em-workflow batch mode)

Referenced by `references/batch-mode.md`. This document is the sole owner
of the batch structured result's format: its key set and key order, its
quoting and escaping rules, the `state` / `step` / `reason` / `detail` /
`feature` / `branch` / `pr_url` / `resume_conditions` value domains and
derivations, the closed stop reason-code set, the mapping from every
terminating stop point to a reason code, and the consumer constraints a
result must satisfy.

## Purpose

A batch run's terminal state must be machine-readable from the output
alone, without relying on the caller process's exit code. The absence of
a result is itself the abnormal-outcome signal: a crash or a truncated
turn produces no result, so a consumer that sees no result at the end of
a run reads that absence as an abnormal outcome rather than as success.

## Result format

The final assistant message of a terminal batch turn is exactly one bare
YAML mapping and nothing else: no code fence, no surrounding prose, no
document separator (`---`), no comments, and no key beyond the eight
below. The mapping carries exactly these eight keys, each written once,
in this fixed order:

```yaml
state: "stopped"
step: "implement"
reason: "step_stuck"
detail: "implementer task0004 stuck after 3 conflict cycles"
feature: "batch-structured-result-output"
branch: "em-workflow/batch-structured-result-output/integration"
pr_url: ""
resume_conditions: "Resolve the conflict manually and re-run implement for task0004."
```

Every value is a double-quoted scalar; an empty value is written as an
empty pair of double quotes (`""`), never omitted and never left
unquoted. Each key sits at the start of its own physical line, so the
result is always exactly eight physical lines: no value may contain a
literal, unescaped newline (see `## Escaping`). Emitting the result needs
no external tool: it is eight lines of text written as the final
assistant message. The result is emitted only in a batch-mode run — an
interactive run emits nothing here.

## Escaping

The rule below is applied to every one of the eight values, character by
character, left to right, and never re-processes a character the rule has
just generated.

| Source character | Emitted |
|---|---|
| `\` | `\\` |
| `"` | `\"` |
| CR (U+000D) | `\r` |
| LF (U+000A) | `\n` |
| TAB (U+0009) | `\t` |

Any character not covered above that falls in U+0000-U+001F,
U+007F-U+009F, U+2028, U+2029, U+FFFE or U+FFFF becomes a backslash, `u`,
and exactly four lower-case hex digits. Every other valid Unicode
character, including non-BMP characters, is emitted unchanged.

## Field values

- `state` — the run's terminal outcome: `completed`, `stopped`, or
  `phase_done`. `phase_done` marks a `--once`-flagged launch that ended
  its turn at a single phase boundary, with `reason` `none` and a
  non-empty `detail`, using the same eight-key structured result as every
  other terminal outcome. A consumer that sees `state` as `phase_done`
  re-launches the same feature to continue it: it passes the result's
  `feature` value as the path argument and does not pass the task
  description again.
- `step` — a closed value domain: one of the seven `workflow.yaml` step
  ids (`create-spec`, `design`, `create-plan`, `implement`, `review`,
  `verify`, `retrospect`), or the single sentinel `no-step`. The general
  rule: `step` names the step EXECUTED in that turn, never the step the
  next launch resumes at; at the verify-fail rework boundary the value is
  `verify`, even though the next launch resumes at `implement`. Two rules
  take precedence over the general rule: the single sentinel `no-step`,
  and the rule for `state` `completed`. `no-step` applies whenever no
  `workflow.yaml` step was executed in that turn, or the stop occurs
  outside Step B; this condition governs, and the stop points named below
  are examples, not an exhaustive list: `stop-condition-6` (Step 0's
  git-setup abort), `step-a-abort` (Step A's feature-resolution failure),
  and `step-c-abort` (Step C's abort; every workflow step has already
  completed). A `stop-condition-4` stop takes `no-step` when no step was
  executed in that turn; otherwise the general rule applies. A stop
  raised in Step A.5, including the command-approval refusal-pattern hard
  fail, also takes `no-step`.
  When `state` is `completed` the value is always `retrospect` — the
  final workflow step, which a completed run has always reached. Because
  Step C is not a `workflow.yaml` step, a turn that executes Step C takes
  its value from whichever precedence rule applies rather than from the
  general rule: normal completion is `retrospect` (the `state` `completed`
  rule), while `step-c-abort` is `no-step` (the sentinel rule) — this
  asymmetry is intentional, not an omission.
- `reason` — one of fourteen documented values, or the reserved value
  `none`. The fourteen are the thirteen stop reason codes listed below,
  plus `context_budget_reached` — a value the consumer defines and
  reserves, that em-workflow never emits. `none` is reserved for the
  non-stop terminal states — `state` `completed` and `state` `phase_done`
  — and is never used when `state` is `stopped`.
- `detail` — a human-facing, non-empty description. Before escaping, its
  value is normalized: every CR, LF and TAB in it is replaced with a
  single space, runs of spaces are then collapsed to one, and the result
  is trimmed; if the normalized value would be empty, a fixed non-empty
  placeholder is substituted instead, so the non-empty guarantee always
  holds. `## Escaping`'s rule is then applied to whatever remains. Items
  carried in `detail` are separated by a fixed textual delimiter — a
  space, a vertical bar (`|`), and a space — that survives normalization,
  so their boundaries remain readable in the single collapsed line.
  `detail` is not a byte-verbatim record: whitespace inside a carried
  command string is normalized by the rule above. The verbatim record
  stays in the persisted audit source that `batch-mode.md`'s
  `## Batch quiet output` audit-item source map already names for that
  item; stating this is a disclosure, not a licence to replace an item
  with that pointer.
- `feature` — the feature slug: the confirmed slug once the feature is
  resolved; empty before resolution, except at Step 0's git-setup abort
  when a supplied name matches the slug pattern `^[a-z0-9][a-z0-9-]*$`,
  in which case `feature` carries that supplied name. A supplied name
  that fails the slug pattern is never used, and no value is ever guessed
  from a task description or from an existing branch — those cases, and
  Step A's feature-resolution abort, leave `feature` empty.
- `branch` — the integration branch name: empty until this run has
  created or confirmed an integration branch; from that point on, the
  branch name, including at every later abort or stop in the same run.
- `pr_url` — the created pull request's bare URL once this run has
  created one; empty otherwise, for the remainder of the run once set.
- `resume_conditions` — the stop-recovery guidance: non-whitespace
  whenever `state` is `stopped` — never empty and never whitespace-only —
  empty for every other `state`. Its value is NOT put through `detail`'s
  normalization: any Markdown newlines, indentation and trailing spaces it
  carries survive as `## Escaping`'s escapes rather than being collapsed.
- Every audit item `batch-mode.md`'s `## Reporting` enumerates is carried
  in full inside `detail`; the stop-recovery guidance above is carried in
  full inside `resume_conditions`. A count alone, or a pointer alone,
  satisfies neither. The item list stays `batch-mode.md`'s `## Reporting`
  to own and is not reproduced here — this document names the section,
  not its contents.
- One named exception, and only one: where an item's text carries a
  secret, exactly that portion is replaced by a fixed placeholder. This is
  the confidentiality rule of `## Responsibility boundary` taking
  precedence over the in-full rule above; it is a redaction, never a count
  or a pointer substitution, and it never applies to a path.

## Stop reason codes

Closed set of thirteen stop reason codes:

| Code | Meaning | Applies to `state` |
|---|---|---|
| `step_stuck` | A workflow step could not make progress and is stuck | `stopped` |
| `step_needs_intervention` | A workflow step reported `needs_update`, or reported `failed` — for the `implement` step, `failed` counts when `failed_kind` reads `decision` (including the missing-value case per `references/workflow-schema.md`), or when the automatic-resume attempt count has reached its cap per `skills/develop/SKILL.md`; other steps' `failed` is unchanged | `stopped` |
| `workflow_yaml_unparseable` | `workflow.yaml` could not be parsed | `stopped` |
| `git_setup_aborted` | Step 0's git setup aborted (e.g. gitleaks missing) | `stopped` |
| `gate_fail_closed` | A gate was classified fail-closed: the aborts `references/question-resolution.md` keeps fail-closed in both modes, plus, in interactive, that mode's own additional aborts, plus the command-approval refusal-pattern hard fail `references/batch-policies.yaml` keeps (`create-spec.command-approval`) | `stopped` |
| `gate_option_unavailable` | A policy gate's option was unavailable | `stopped` |
| `implement_task_failed` | A task failed a second time in the implement phase | `stopped` |
| `verify_rework_cap_reached` | The verify phase's rework cap was reached | `stopped` |
| `completion_aborted` | Step C's completion processing aborted | `stopped` |
| `feature_resolution_aborted` | Step A's feature-resolution failed and the batch run aborted | `stopped` |
| `docs_commit_conflict_aborted` | A phase aborted after a second consecutive `commit-docs.sh` exit 4 | `stopped` |
| `no_work_required` | The pre-run estimate reported that no work remains before any workflow step began | `stopped` |
| `unmapped_stop` | A terminating stop that no other coverage row names, bound to this code by the Fallback rule below | `stopped` |

`context_budget_reached` is a fourteenth, reserved value in the `reason`
domain (`## Field values`): the consumer defines it and em-workflow never
emits it, so no row above binds it to a stop point (see `## Stop point
coverage`).

The value `none` is reserved for the non-stop terminal states — `state`
`completed` and `state` `phase_done` — it is not itself a stop reason
code and is never used when `state` is `stopped`. Every stop result also
carries a `step` field alongside `reason`, and always carries a `detail`
field.

## Stop point coverage

Every batch-terminating stop binds to exactly one code by construction:
the code of the row below that names it, with the Precedence rule
settling a stop that two named rows match, or otherwise `unmapped_stop`,
through the Fallback rule below, when no other row names it. The third
column names the document where the stop point is specified; this table
only maps it to a reason code, it does not redefine it.

| Stop point | Reason code | Source |
|---|---|---|
| `stop-condition-2` | `step_stuck` | `skills/develop/SKILL.md` |
| `stop-condition-3` | `step_needs_intervention` | `skills/develop/SKILL.md` |
| `stop-condition-4` | `workflow_yaml_unparseable` | `skills/develop/SKILL.md` |
| `stop-condition-6` | `git_setup_aborted` | `skills/develop/SKILL.md` |
| `fail-closed-abort` | `gate_fail_closed` | `references/question-resolution.md` |
| `policy-option-unavailable` | `gate_option_unavailable` | `references/batch-policies.yaml` |
| `command-refusal` | `gate_fail_closed` | `references/batch-policies.yaml` |
| `implement-second-failure` | `implement_task_failed` | `references/implement-phase.md` |
| `verify-rework-cap` | `verify_rework_cap_reached` | `skills/develop/SKILL.md` |
| `step-c-abort` | `completion_aborted` | `skills/develop/SKILL.md` |
| `step-a-abort` | `feature_resolution_aborted` | `skills/develop/SKILL.md` |
| `docs-commit-conflict` | `docs_commit_conflict_aborted` | `references/phase-state.md` |
| `no-work-required` | `no_work_required` | `skills/develop/SKILL.md` |
| `unmapped-terminating-stop` | `unmapped_stop` | `references/batch-terminal-line.md` |

Precedence rule: when a stop matches more than one row above, the
phase-specific stop point takes precedence over the generic
`stop-condition-N` rows, so exactly one code applies.
`implement-second-failure` and `verify-rework-cap` write a step's status
`failed`, which is `stop-condition-3`'s own trigger; `docs-commit-conflict`
aborts without writing any status, because the failed status write is
itself its stop cause. A phase-specific row wins when the current run
reaches the stop through that phase's own abort route. This includes
`implement-second-failure`, which the same run realizes through its next
Step B evaluation when that evaluation reads the `failed` the run wrote.
Correspondingly, the `stop-condition-3` row's meaning binds a stop at Step
B's entry evaluation that reads a `failed` / `needs_update` status no
route of the current run produced — for example, a `failed` left by an
earlier run's `implement-second-failure` — and, for the `implement`
step's `failed`, further restricted to the cases where `failed_kind`
reads `decision`, or where the automatic-resume attempt count has reached
its cap per `skills/develop/SKILL.md` (see the `step_needs_intervention`
row above). The one such collision: the batch second-failure abort's
terminal status commit (Step I.2.c abort-phase terminal status commit)
returns exit 4 on its first attempt and exit 4 again on its single
exit-4 retry. That stop matches both `implement-second-failure` and
`docs-commit-conflict`. The row whose commit failure directly caused the
stop wins, and this stop binds to `docs_commit_conflict_aborted`, not to
`implement_task_failed`. This stop ends the run: the run never reaches a
Step B entry evaluation that reads the uncommitted `implement: failed`,
so neither `implement-second-failure` nor `stop-condition-3` applies to
that run. A first exit 4 followed by a successful retry instead commits
the terminal status write, and that stop keeps `implement_task_failed`.
In this collision's case, the terminal status write — the pair
`implement: failed` / `failed_kind: decision` — exists in the
integration worktree but stays uncommitted and never reaches the
branch; this is distinct from "no status written". How that leftover is
disposed of and handled by the next run is defined by the abort
terminal-commit exception in implement-phase.md's Branch & Worktree
Model. This resolution is confined to that one collision: the Step I.1
baseline, Step I.2.a launch, Step I.2.b wake and Step I.3 completion
exit-4 stops keep their binding to `docs_commit_conflict_aborted` alone.

Exactly one documented `reason` code, `context_budget_reached`, has no
stop point in the table above: it is reserved by the consumer and never
emitted by em-workflow, so this asymmetry is intentional, not an
omission.

Fallback rule: a batch-terminating stop that no other row above names
binds to `unmapped_stop`. Every other row takes precedence over this
catch-all, including the generic `stop-condition-N` rows and the
`command-refusal` row; the catch-all applies last, after the Precedence
rule above has settled any match among named rows. Non-exhaustive
examples this catch-all reaches: `references/contracts/designer-contract.md`'s
`kind: none` × token-present abort, including its batch abort when
candidate discovery is truncated; that same contract's `em_workflow` ×
`tokens.html`-only abort before dispatch; `references/phase-state.md`'s
unknown `schema_version` abort; and the remaining untabled aborts of
`references/question-resolution.md` and `references/batch-policies.yaml`.

Scope: the fallback applies only to a stop that ends a batch run with
`state` `stopped`. It never applies to: a wait turn — develop's stop
condition 5, or implement's launch and wake turns (see `## No result on
a wait turn`); normal completion; a `--once` phase boundary
(`phase_done`); the infra auto-resume, which is not a stop; or the 64
KiB size-collision outcome, which emits no result and, per `## Consumer
constraints`, adds no reason code and no coverage row.

Catch-all result: when `reason` is `unmapped_stop`, `detail` names the
stop site — the owning document, and the step or section where the stop
occurred — and the concrete cause. `resume_conditions` stays mandatory
and non-whitespace, as for every `stopped` result.

## Consumer constraints

The consumer rejects a result that violates any of the following:

1. `state` `stopped` together with `reason` `none`.
2. `state` `phase_done` without `reason` `none` and an empty
   `resume_conditions`.
3. A `branch` value containing a line terminator or a terminal-control
   code point.
4. A `pr_url` value containing a line terminator or a terminal-control
   code point.
5. A result exceeding 64 KiB, encoded UTF-8, in total.

`## Escaping` does not help with constraints 3 and 4: the consumer
rejects the value after parsing it, so an escaped control character
inside `branch` or `pr_url` is rejected exactly like a bare one.

Nothing may be dropped, summarized, replaced by a count, or replaced by a
pointer in order to satisfy the 64 KiB bound. The bound is hard: an
oversize result is never emitted, never truncated to fit. Therefore a run
that cannot satisfy both this bound and `batch-mode.md`'s `## Reporting`
"in full" requirement emits no result for that run, and `## Purpose`'s
absence signal applies to it: a consumer that sees no result reads an
abnormal outcome. This is a chosen fail-closed behaviour, not an emitter
improvising, and it adds no reason code and no `## Stop point coverage`
row. The assembled content is not lost: it remains in the persisted audit
sources.

**em-workflow's OWN emitter obligations and rejection rules.** The rules
below are em-workflow's own hardening obligations, stated here as defense
in depth alongside the five carried-over constraints above — they are NOT
carried-over consumer behaviour, and this repository can verify nothing
about how (or whether) the external consumer enforces them.

- `detail` rejects a line terminator or a terminal-control code point
  after decoding, in the same form as constraints 3 and 4 above:
  `## Field values` already replaces every CR, LF and TAB in `detail`
  with a single space before escaping, so a surviving one means the
  normalization was skipped. `## Escaping` does not help here either: an
  escaped control character inside `detail` is rejected exactly like a
  bare one.
- `resume_conditions` rejects only a terminal-control code point other
  than CR (U+000D), LF (U+000A) or TAB (U+0009) after decoding — a
  decoded CR, LF or TAB inside `resume_conditions` is NOT a violation,
  because `## Field values` defines those as surviving as `## Escaping`'s
  escapes rather than being collapsed. `## Escaping` does not help here
  either: an escaped control character inside `resume_conditions`, other
  than those three, is rejected exactly like a bare one.
- The top-level mapping's key sequence is exactly the eight keys of
  `## Result format`, in that order: a result with a missing, extra or
  reordered key is rejected.
- A key appearing more than once is rejected before any parser's
  last-wins resolution; equivalently, a result that is not exactly eight
  physical lines is rejected on shape alone.
- A `state`, `step` or `reason` value outside its documented domain is
  rejected.

## No result on a wait turn

A turn that has not reached any of the contract's terminal states emits
no result. Develop's stop condition 5 (waiting for an implementer
notification) is one instance: that wait is in-flight, not a stop, and
the run resumes when the notification arrives — a result at that point
would be misread as a stop by a consumer parsing the output. Implement's
launch turn and wake turn (`references/implement-phase.md`) are further
instances: both end the turn mid-run, without the batch run itself having
reached a terminal state. What such a turn emits instead is owned by
`references/batch-mode.md`, not by this document.

## Responsibility boundary

em-workflow declares the stop in its own output only. It performs no
status operation against the external task-management service — it does
not edit that service's task page body or status property. The relay
from this structured result to a human reviewer happens through that
external service, in one direction only (outbound). This is also why
`detail`, `resume_conditions`, `branch` and `pr_url` carry no confidential
information beyond paths: once emitted, the result's content is relayed
outside of em-workflow's own process boundary.
