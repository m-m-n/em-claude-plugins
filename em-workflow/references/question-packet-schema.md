# Question Packet & Answer Contract (SSOT)

Normative source: `feature-docs/agent-separation/design-input.md` 5.1
(question packet) and 5.2 (answer). This document is the output contract
for both structures — worker-facing and human-facing. Machine verification
lives in `scripts/validate-worker-output.py`, backed by fixtures under
`references/fixtures/` (design-input.md 10.5).

This document does not restate the batch gate-resolution table (owned by
`references/batch-policies.yaml` and `references/question-resolution.md`),
the workflow patch structure (`references/workflow-patch.md`, design-input.md
5.5), or the phase-state persistence schema (`references/phase-state.md`,
design-input.md 5.6). The `gate_id` field below is a join key into the
batch-policy SSOT, not a copy of it.

## The packet is question-request-only

A question packet is a worker-to-orchestrator artifact whose only purpose
is requesting user decisions. It never expresses "no questions are
needed": the worker's overall outcome is carried entirely by the worker
result's `status` field (`references/contracts/worker-envelope.md`), not
by the packet's absence or by an empty `questions` array.

## Identifier patterns and size limits

| Field | Pattern / limit |
|---|---|
| `packet_id` | `^[a-z][a-z0-9-]*-q[0-9]{4}$` |
| `question_id` | `^[a-z][a-z0-9._-]*$` |
| `summary` | optional; at most 2000 characters |
| `header` | at most 12 characters |
| `questions` | 1 to 32 entries |
| `options` when `answer_mode` is a select variant | 2 to 4 entries |
| `options` when `answer_mode` is `freeform` | 0 entries |

## Packet fields

| Field | Meaning |
|---|---|
| `schema_version` | Packet schema version |
| `packet_id` | Unique packet identifier (see pattern above) |
| `phase` | Owning phase: `create-spec` \| `create-plan` \| `review` \| `verify` \| `rework` |
| `worker` | One of the five workers in the 2.3 applicability table |
| `iteration` | Attempt count, `>= 1` |
| `input_revision` | Echo of the dispatch's `input_revision` (`workflow_blob`, `input_digest`) |
| `summary` | Optional free-text summary of the worker's progress |
| `confirmed_facts` | Optional list of facts the worker has confirmed |
| `confirmed_facts[]`.`fact_id` | Fact identifier |
| `confirmed_facts[]`.`statement` | The confirmed statement |
| `confirmed_facts[]`.`source` | Where the fact came from |
| `assumptions` | Optional list of assumptions the worker is proposing |
| `assumptions[]`.`assumption_id` | Assumption identifier |
| `assumptions[]`.`statement` | The assumption text |
| `assumptions[]`.`reason` | Why the assumption was made |
| `assumptions[]`.`impact` | `low` \| `medium` \| `high` |
| `assumptions[]`.`reversible` | Boolean |
| `assumptions[]`.`related_question_ids` | Related `question_id` values |
| `questions` | 1 to 32 question objects |
| `questions[]`.`question_id` | Question identifier (see pattern above) |
| `questions[]`.`gate_id` | Join key to a batch policy. Batch handling of a `gate_id` is owned by `references/batch-policies.yaml`. The gate identifiers themselves are defined at their point of origin — each worker's own contract or agent prompt (its decision-point-to-`gate_id` table, e.g. `references/contracts/analyst-contract.md`, `agents/implementation-planner.md`) or the phase protocol that opens an orchestrator-side gate — not restated here |
| `questions[]`.`category` | One of the `category` vocabulary values below |
| `questions[]`.`priority` | `critical` \| `high` \| `normal` \| `low` |
| `questions[]`.`blocking` | Boolean |
| `questions[]`.`prompt` | The question text shown to the user |
| `questions[]`.`header` | Short header (see the size limit above) |
| `questions[]`.`answer_mode` | `single_select` \| `multi_select` \| `freeform` \| `select_or_freeform` |
| `questions[]`.`options` | Select-mode options (see the size limit above) |
| `questions[].options[]`.`option_id` | Option identifier |
| `questions[].options[]`.`label` | Option label |
| `questions[].options[]`.`description` | Option description |
| `questions[].options[]`.`recommended` | Boolean |
| `questions[]`.`why_needed` | Why the question is needed |
| `questions[]`.`evidence` | Supporting evidence entries |
| `questions[].evidence[]`.`path` | Evidence file path |
| `questions[].evidence[]`.`line` | Evidence line number |
| `questions[].evidence[]`.`detail` | Evidence detail text |
| `questions[].evidence[]`.`origin_id` | The `origin_id` half of the `origin_kind` / `origin_id` pair `references/rework-task-synthesis.md`'s Invariant 6 defines (cited, not restated); `references/question-resolution.md`'s Classification gate step 3 requires at least one `evidence[]` entry carrying it for a `rework.spec-change` question |
| `questions[]`.`depends_on` | `question_id` values this question depends on |
| `questions[]`.`supersedes` | `question_id` values this question supersedes |
| `questions[]`.`on_unanswered` | `block` \| `record_tbd` \| `use_batch_policy` |

## `category` vocabulary

`feature-identity`, `business-objective`, `functional-requirement`,
`acceptance-criteria`, `user-experience`, `technical-requirement`,
`edge-case`, `security`, `dependency`, `license`, `testing`,
`design-step`, `tbd-resolution`, `existing-files`, `artifact-overwrite`,
`rework`, `spec-change`, `completion`, `other`.

## `on_unanswered`

No `on_unanswered` value converts an unanswered question into an assumption
automatically. In interactive mode, an unanswered blocking
question is never silently downgraded into an assumption; `record_tbd` and
`use_batch_policy` are the only non-`block` values, and neither one is an
assumption.

A question whose `category` is `spec-change`, `security`, or `license` must
carry `on_unanswered: block` — a question in one of those categories can
never be left to resolve as `record_tbd` or `use_batch_policy`.
`scripts/validate-worker-output.py` enforces this constraint mechanically
and rejects a packet where it does not hold;
`references/question-resolution.md`'s fail-closed classification states the
resolution-time rule this constraint backs.

## Mapping onto AskUserQuestion

`options[].label`, `options[].description`, and `options[].recommended`
map directly onto AskUserQuestion's per-option fields of the same names.
`header` maps onto AskUserQuestion's `header`.

## Answer object

```yaml
question_id: requirement.fr4.tbd-resolution
packet_id: create-plan-q0001
answered_at: "2026-08-02T16:00:00+09:00"
source: user
answer_mode: select_or_freeform
selected_option_ids: [assume]
freeform: "..."
normalized_answer: "..."
resolution_note: null
```

| Field | Meaning |
|---|---|
| `question_id` | Echo of the answered question's `question_id` |
| `packet_id` | Echo of the packet's `packet_id` |
| `answered_at` | RFC 3339 timestamp with an explicit offset |
| `source` | See the `source` vocabulary below |
| `answer_mode` | Echo of the corresponding question's `answer_mode` |
| `selected_option_ids` | Selected `option_id` values |
| `freeform` | Free-text answer content |
| `normalized_answer` | The orchestrator's normalized rendering of the answer |
| `resolution_note` | Optional note on how the answer was resolved |

### `source` vocabulary

`user`, `batch-decision-table`, `batch-codex-consultation`,
`batch-safe-default`, `batch-classification-gate`.

### Consistency rules

Rules 1-5 are machine-verified by `scripts/validate-worker-output.py`;
rules 6 and 7 are not.

1. `single_select` — `selected_option_ids` has exactly one entry;
   `freeform` is null.
2. `multi_select` — `selected_option_ids` has one or more entries. To allow
   selecting none, the question must expose an explicit "none of these"
   option.
3. `freeform` — `selected_option_ids` is empty; `freeform` is non-empty.
4. `select_or_freeform` — a selection uses an `option_id`; choosing
   "Other" uses `freeform`. If both are present, `freeform` is treated as
   supplementary detail on the selection.
5. Every value in `selected_option_ids` must exist among the corresponding
   question's `options[].option_id` values.
6. The worker receives this answer object, never AskUserQuestion's raw
   return value.
7. When a freeform answer's meaning is not unambiguous, the orchestrator
   does not guess and normalize it: it asks a follow-up question under a
   new `question_id` instead.

## Cross-references

- Worker envelope and `status`: `references/contracts/worker-envelope.md`
  (design-input.md 5.3).
- Batch gate resolution: `references/batch-policies.yaml`,
  `references/question-resolution.md` (design-input.md 5.9).
- Workflow patch: `references/workflow-patch.md` (design-input.md 5.5).
- Phase-state persistence: `references/phase-state.md` (design-input.md
  5.6).
- Machine validation and fixtures: `scripts/validate-worker-output.py`,
  `references/fixtures/` (design-input.md 5.11.1, 10.5).
