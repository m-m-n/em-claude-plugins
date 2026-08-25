# Terminal Line Contract (em-workflow batch mode)

Referenced by `references/batch-mode.md`. This document is the sole owner
of the batch terminal line's format: its prefix, its field grammar, the
`state` / `step` / `reason` value domains, the closed stop reason-code set,
and the mapping from every terminating stop point to a reason code.

## Purpose

A batch run's terminal state must be readable from the output alone,
without relying on the caller process's exit code. The line's absence is
itself the abnormal-outcome signal: a crash or a truncated turn produces no
line, so a consumer that sees no line at the end of a run reads that
absence as an abnormal outcome rather than as success.

## Line format

The terminal line is the LAST line of the final assistant message of a
batch-mode turn that reaches a terminal state. It begins with a fixed
prefix (shown in full in the fenced examples below) followed by one ASCII
space, then exactly four `key=value` fields, always in this order:
`state`, `step`, `reason`, `detail`. A single space separates each field
from the next; no space appears around the `=`. `detail` is the last field
and its value runs to the end of the line, so it may itself contain
spaces. The line is always exactly one physical line — it is never
wrapped.

The same prefix and the same four fields are used whether the run
completed normally or stopped (`state=completed` or `state=stopped`);
there is no second shape to account for. A `--once` phase-boundary line
(`state=phase_done`) uses that same prefix, the same four fields and the
same field order. Emitting the line requires no external tool: it is a
single line of text appended to the final assistant message. The line is
emitted only in a batch-mode run — an interactive run emits nothing.

`detail`'s value is normalized before it is written into the line: every
CR, LF and TAB character in it is replaced with a single space, runs of
spaces are then collapsed to one and the result is trimmed. If the
normalized value is empty, a fixed non-empty placeholder is substituted, so
`## Field values`'s non-empty guarantee for `detail` still holds. This
normalization is what keeps the line always exactly one physical line even
when `detail`'s source (implementer notes, a gate's `blocking_reason`, a
YAML parser message) itself contains newlines.

Example (a stop):

```
EM_WORKFLOW_TERMINAL: state=stopped step=implement reason=step_stuck detail=implementer task0004 stuck after 3 conflict cycles
```

Example (normal completion):

```
EM_WORKFLOW_TERMINAL: state=completed step=retrospect reason=none detail=feature merged
```

## Field values

- `state` — the run's terminal outcome: `completed`, `stopped`, or
  `phase_done`. `phase_done` marks a `--once`-flagged launch that ended
  its turn at a single phase boundary; the line carries `reason=none` and
  a non-empty, single-line `detail`, using the same prefix, the same four
  fields and the same field order as every other terminal line. A
  consumer that sees `state=phase_done` re-launches the same feature to
  continue it.
- `step` — a closed value domain: one of the seven `workflow.yaml`
  step ids (`create-spec`, `design`, `create-plan`, `implement`,
  `review`, `verify`, `retrospect`), or the single sentinel `no-step`.
  The general rule: `step` names the step EXECUTED in that turn,
  never the step the next launch resumes at; at the verify-fail
  rework boundary the value is `verify`, even though the next launch
  resumes at `implement`. Two rules take precedence over the general
  rule: the single sentinel `no-step`, and the `state=completed` rule.
  `no-step` applies whenever no `workflow.yaml` step is in effect at
  the stop point: `stop-condition-6` (Step 0's git-setup abort),
  `step-a-abort` (Step A's feature-resolution failure), and
  `step-c-abort` (Step C's abort — every workflow step has already
  completed by then, and the stop happens outside any of them). On
  `state=completed` the value is always `retrospect` — the final
  workflow step, which a completed run has always reached. Because
  Step C is not a `workflow.yaml` step, a turn that executes Step C
  takes its value from whichever precedence rule applies rather than
  from the general rule: normal completion is `retrospect` (the
  `state=completed` rule), while `step-c-abort` is `no-step` (the
  sentinel rule) — this asymmetry is intentional, not an omission.
- `reason` — one of the eleven stop reason codes listed below, or the
  reserved value `none`. `none` is reserved for the non-stop terminal
  states, currently `state=completed` and `state=phase_done`; it is never
  used with `state=stopped`.
- `detail` — a single line, human-facing, non-empty description. It
  carries no confidential information beyond paths.

## Stop reason codes

Closed set of eleven stop reason codes:

| Code | Meaning | Applies to `state` |
|---|---|---|
| `step_stuck` | A workflow step could not make progress and is stuck | `stopped` |
| `step_needs_intervention` | A workflow step reported `failed` or `needs_update` | `stopped` |
| `workflow_yaml_unparseable` | `workflow.yaml` could not be parsed | `stopped` |
| `git_setup_aborted` | Step 0's git setup aborted (e.g. gitleaks missing) | `stopped` |
| `gate_fail_closed` | A gate was classified fail-closed and the phase aborted | `stopped` |
| `gate_option_unavailable` | A policy gate's option was unavailable | `stopped` |
| `implement_task_failed` | A task failed a second time in the implement phase | `stopped` |
| `verify_rework_cap_reached` | The verify phase's rework cap was reached | `stopped` |
| `completion_aborted` | Step C's completion processing aborted | `stopped` |
| `feature_resolution_aborted` | Step A's feature-resolution failed and the batch run aborted | `stopped` |
| `docs_commit_conflict_aborted` | A phase aborted after a second consecutive `commit-docs.sh` exit 4 | `stopped` |

The value `none` is reserved for the non-stop terminal states, currently
`state=completed` and `state=phase_done`; it is not itself a stop reason
code and is never used together with `state=stopped`. Every stop line
also carries a `step` field alongside `reason`, and always carries a
`detail` field.

## Stop point coverage

Every terminating stop point is bound to exactly one reason code above.
The third column names the document where the stop point is specified;
this table only maps it to a reason code, it does not redefine it.

| Stop point | Reason code | Source |
|---|---|---|
| `stop-condition-2` | `step_stuck` | `skills/develop/SKILL.md` |
| `stop-condition-3` | `step_needs_intervention` | `skills/develop/SKILL.md` |
| `stop-condition-4` | `workflow_yaml_unparseable` | `skills/develop/SKILL.md` |
| `stop-condition-6` | `git_setup_aborted` | `skills/develop/SKILL.md` |
| `fail-closed-abort` | `gate_fail_closed` | `references/question-resolution.md` |
| `policy-option-unavailable` | `gate_option_unavailable` | `references/batch-policies.yaml` |
| `implement-second-failure` | `implement_task_failed` | `references/implement-phase.md` |
| `verify-rework-cap` | `verify_rework_cap_reached` | `skills/develop/SKILL.md` |
| `step-c-abort` | `completion_aborted` | `skills/develop/SKILL.md` |
| `step-a-abort` | `feature_resolution_aborted` | `skills/develop/SKILL.md` |
| `docs-commit-conflict` | `docs_commit_conflict_aborted` | `references/phase-state.md` |

Precedence rule: when a stop matches more than one row above, the
phase-specific stop point takes precedence over the generic
`stop-condition-N` rows, so exactly one code applies.
`implement-second-failure`, `verify-rework-cap` and `docs-commit-conflict`
are the stop points that can also match `stop-condition-3` — all three
leave a step's status `failed`, which is `stop-condition-3`'s own trigger —
and in each case the phase-specific row wins. Correspondingly, the
`stop-condition-3` row's meaning is restricted to `failed` / `needs_update`
states that no phase-specific row covers.

## No line on a wait turn

A turn that has not reached any of the contract's terminal states emits no
terminal line. Develop's stop condition 5 (waiting for an implementer
notification) is one instance:
that wait is in-flight, not a stop, and the run resumes when the
notification arrives — a terminal line at that point would be misread as a
stop by a consumer parsing the output. Implement's launch turn and wake
turn (`references/implement-phase.md`) are further instances: both end the
turn mid-run, without the batch run itself having reached a terminal
state.

## Responsibility boundary

em-workflow declares the stop in its own output only. It performs no
status operation against the external task-management service — it does
not edit that service's task page body or status property. The relay from
this terminal line to a human reviewer happens through that external
service, in one direction only (outbound). This is also why `detail`
carries no confidential information: once emitted, the line's content is
relayed outside of em-workflow's own process boundary.
