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
there is no second shape to account for. Emitting the line requires no
external tool: it is a single line of text appended to the final assistant
message. The line is emitted only in a batch-mode run — an interactive run
emits nothing.

Example (a stop):

```
EM_WORKFLOW_TERMINAL: state=stopped step=implement reason=step_stuck detail=implementer task0004 stuck after 3 conflict cycles
```

Example (normal completion):

```
EM_WORKFLOW_TERMINAL: state=completed step=retrospect reason=none detail=feature merged
```

## Field values

- `state` — closed set of two values: `completed`, `stopped`.
- `step` — a `workflow.yaml` step id (`create-spec`, `design`,
  `create-plan`, `implement`, `review`, `verify`, `retrospect`), or the
  single sentinel `no-step`. `no-step` applies whenever no `workflow.yaml`
  step is in effect at the stop point: Step 0's git-setup abort, Step A's
  feature-resolution failure, and Step C's abort (every workflow step has
  already completed by then, and the stop happens outside any of them). On
  `state=completed` the value is always `retrospect` — the final workflow
  step, which a completed run has always reached.
- `reason` — one of the nine stop reason codes listed below, or the
  reserved value `none` (used only when `state=completed`).
- `detail` — a single line, human-facing, non-empty description. It
  carries no confidential information beyond paths.

## Stop reason codes

Closed set of nine stop reason codes:

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

The value `none` is reserved for `state=completed`; it is not itself a
stop reason code and is never used together with `state=stopped`. Every
stop line also carries a `step` field alongside `reason`, and always
carries a `detail` field.

## Stop point coverage

Every terminating stop point is bound to exactly one reason code above.
The third column names the document that owns (defines) the stop point;
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

## No line on a wait turn

A turn that ends at develop's stop condition 5 (waiting for an implementer
notification) emits no terminal line. That wait is in-flight, not a stop:
the run resumes when the notification arrives, and a terminal line at that
point would be misread as a stop by a consumer parsing the output.

## Responsibility boundary

em-workflow declares the stop in its own output only. It performs no
status operation against the external task-management service — it does
not edit that service's task page body or status property. The relay from
this terminal line to a human reviewer happens through that external
service, in one direction only (outbound). This is also why `detail`
carries no confidential information: once emitted, the line's content is
relayed outside of em-workflow's own process boundary.
