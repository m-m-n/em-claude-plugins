# Worker Envelope Contract (SSOT)

Normative source: `feature-docs/agent-separation/design-input.md` 5.3
(envelope structure), 2.3 (applicability), 5.0 R1 (`input_digest` /
staleness detection) and 5.11.2 (validation layers). This document is the
SSOT for the common worker input/output envelope structure, and states
rule R1's normalization procedure and the seven validation layers in full
(below) — the design document is provenance for these rules, not a
required destination for resolving them. Its machine verification lives in
`scripts/validate-worker-output.py` (`--kind worker-result`), backed by
fixtures under `references/fixtures/` (design-input.md 10.5). Each
worker's `payload` shape is defined in that worker's own contract,
`references/contracts/*-contract.md`.

This document does not restate `write_policy`'s internal structure (its
six actions, its per-target digest-expectation requirement, or the split
between existing-file protection and new-file `allowed_write_roots`) —
that is owned by design-input.md 5.4.2 and the per-worker contracts. It
also does not restate the workflow patch's operations or fields
(`references/workflow-patch.md`, design-input.md 5.5) or the phase-state
persistence schema (`references/phase-state.md`, design-input.md 5.6); the
envelope's `workflow_patch` output field and `prior_packets` input field
are pointers into those SSOTs, not copies of them.

## Applicability (design-input.md 2.3)

The envelope below applies to exactly five workers. Every other worker
keeps its current input/output form.

| Applies | Does not apply |
|---|---|
| `requirements-analyst` (new) | `implementer` |
| `spec-writer` (new) | `reviewer` / `codex-reviewer` |
| `rework-planner` (new) | `review-editor` |
| `implementation-planner` (revised) | `gitignore-guard` / `git-setup-guard` |
| `designer` (revised) | |

`review-editor` keeps its own JSON form: it never asks its own questions —
the orchestrator resolves any decision before dispatch — so it falls
outside this envelope's scope.

## Input fields

| Field | Meaning | Mandatory |
|---|---|---|
| `schema_version` | Envelope schema version | Yes |
| `request_id` | Unique identifier for this dispatch | Yes |
| `phase` | Owning phase: `create-spec` \| `create-plan` \| `review` \| `verify` \| `rework` | Yes |
| `mode` | `interactive` or `batch` | Yes |
| `project_root` | Absolute path to the main repository | Yes |
| `integration_worktree` | Absolute path to the feature's integration worktree | Yes |
| `feature` | Feature slug | Yes |
| `feature_dir` | Absolute path to `feature-docs/{feature}` inside the integration worktree | Yes |
| `plugin_root` | Absolute path to the plugin root | Yes |
| `workflow_path` | Absolute path to `workflow.yaml` | Yes |
| `input_revision` | Revision-identity object (Rule R1, below) | Yes |
| `input_revision`.`workflow_blob` | Blob id of `workflow.yaml` at dispatch time; null before it exists | Yes (value nullable) |
| `input_revision`.`input_digest` | `sha256:`-prefixed digest computed per Rule R1 (below) | Yes |
| `input_revision`.`base_revision` | Reference-only revision information | Yes |
| `task_description` | Free-form task text, or null | No (nullable) |
| `prior_packets` | Paths to prior phase-state packets (`references/phase-state.md`) | Yes (may be empty) |
| `answers` | Array of answer objects (`references/question-packet-schema.md` 5.2) | Yes (may be empty) |
| `write_policy` | Path-level write-protection object; internal structure owned by design-input.md 5.4.2 and the per-worker contracts | Yes |
| `resolved_input_paths` | Orchestrator-resolved dynamic input paths (Rule R1, below); only the categories the worker's own contract requires are non-empty | Yes |
| `resolved_input_paths`.`e2e` | Resolved E2E input paths | Yes (may be empty) |
| `resolved_input_paths`.`design_system_candidates` | Design-system candidate paths | Yes (may be empty) |
| `resolved_input_paths`.`project_design_system` | Confirmed `project.design_system` paths | Yes (may be empty) |
| `resolved_input_paths`.`package_files` | Resolved package-manifest paths | Yes (may be empty) |
| `resolved_input_paths`.`other_features_design` | Resolved sibling-feature design paths | Yes (may be empty) |
| `resolved_input_paths`.`visual_inputs` | Resolved visual input paths | Yes (may be empty) |
| `allowed_write_roots` | New-file directories the worker may write under | Yes (may be empty) |
| `output_contract_path` | Path to the worker's own `references/contracts/*-contract.md` | Yes |

### Read restriction

A worker reads **only** the fixed-path inputs the envelope explicitly
names (`workflow_path`, and any of `templates` / `design_inputs` /
`planning_inputs` / `output_contract_path` etc. its own contract lists)
and the paths listed under `resolved_input_paths`. A worker never performs
its own filesystem discovery — no globbing, no directory listing beyond a
supplied path — to find additional inputs. Each per-worker contract
restates this constraint in its own terms.

## Rule R1: `input_digest` and staleness detection

Input staleness is judged by **`input_digest` equality**, never by
comparing commit SHAs — a commit cannot embed its own SHA into a tracked
file, so SHA comparison is not an available mechanism.

`input_digest` is the sha256 of the normalized-JSON serialization of a
`digest_source` object:

```yaml
digest_source:
  worker: implementation-planner
  mode: interactive
  workflow_blob: 8f17c04...          # git rev-parse HEAD:{workflow.yaml's relative path}
  digest_inputs:                     # file inputs; a path-ascending-sorted map
    feature-docs/example/SPEC.md: sha256:...
    feature-docs/example/REQUIREMENTS.md: sha256:...
  value_inputs:                      # non-file inputs; a key-ascending-sorted map
    task_description: sha256:...     # null allowed
  answers_digest: sha256:...         # sha256 of the question_id-sorted, normalized answers JSON
  write_policy_digest: sha256:...
```

**Normalization procedure**: sort every object's keys in ascending order,
serialize to JSON using separators `(",", ":")`, leave non-ASCII characters
unescaped, then take the sha256 of the resulting bytes.

Besides `digest_inputs` and `value_inputs`, `digest_source` carries two
more sha256 fields computed the same way: `answers_digest` (the sha256 of
the question_id-sorted, normalized JSON of the dispatch's `answers`) and
`write_policy_digest` (the sha256 of the normalized `write_policy` object).

A file that does not exist is omitted from `digest_inputs` entirely — its
key is absent, not present with a null or empty value. A directory target
expands to one key per file underneath it.

**`digest_inputs`'s target set is per-worker and contract-owned**: each
worker's own `references/contracts/*-contract.md` carries a `digest_inputs`
section that exhaustively lists everything that can influence that
worker's output, including the contract document itself (a contract change
alters the worker's output shape). The orchestrator builds `input_digest`
from exactly that worker's list — nothing more, nothing less. The
orchestrator alone resolves any glob-derived category before dispatch and
lists the resolved paths in `resolved_input_paths`; no worker performs its
own filesystem discovery to expand this set.

**Recomputation and comparison timing** — what makes staleness detection
work: the orchestrator computes `input_digest` once, before dispatch, and
places it in the input envelope's `input_revision.input_digest`. The
worker copies that value verbatim into its output's
`input_revision.input_digest` (an echo, never a recomputation). On the
worker's return, the orchestrator recomputes `input_digest` from the
current state of the same inputs and compares it against the dispatch-time
value; a mismatch means a tracked input changed during the dispatch window
and the result is treated as stale. This only works if dispatch-time and
return-time computation both follow the identical normalization procedure
above — an implementation that diverges on either side silently defeats
staleness detection.

(Provenance: design-input.md 5.0 R1. The rule is stated in full above; the
design document is not required reading to apply it.)

## Validation layers

Every worker result and every workflow patch passes through seven
validation layers, split between the validation script
(`scripts/validate-worker-output.py`) and the orchestrator itself:

| # | Layer | Owner |
|---|---|---|
| 1 | Syntax validation (parses as JSON/YAML) | Script |
| 2 | Structural validation | Script |
| 3 | Revision validation (`input_digest` and the workflow patch's base-revision fields; see `references/workflow-patch.md`) | Script (`--dry-run-apply`) |
| 4 | Scope validation (dispatch-window write containment, `references/contracts/worker-envelope.md`'s exclusivity assumption below) | Orchestrator (Bash) |
| 5 | Artifact validation (declared-file existence and digest match) | Orchestrator (Bash) |
| 6 | Cross-artifact validation (SPEC ID / task metadata / VERIFICATION ID reference consistency) | Script |
| 7 | State-machine postcondition | Orchestrator |

(Provenance: design-input.md 5.11.2.)

## Output fields

| Field | Meaning | Mandatory |
|---|---|---|
| `schema_version` | Envelope schema version | Yes |
| `request_id` | Echo of the input `request_id` | Yes |
| `worker` | Worker name | Yes |
| `status` | One of the six values below | Yes |
| `input_revision` | Echo of the input `input_revision` | Yes |
| `input_revision`.`workflow_blob` | Echoed verbatim from the input | Yes |
| `input_revision`.`input_digest` | Echoed verbatim from the input | Yes |
| `question_packet` | The question packet (`references/question-packet-schema.md` 5.1); present only when `status: needs_user_input` | Conditional (see status table) |
| `blocking_reason` | Human-readable reason; present only when required by `status` | Conditional (see status table) |
| `written_artifacts` | Every path the worker wrote, each paired with its sha256 digest | Yes (may be empty) |
| `workflow_patch` | Proposed workflow patch (`references/workflow-patch.md`); worker-specific, may be absent | No |
| `mode_echo` | Verbatim echo of a mode-selecting input field; see the `mode_echo` rule below | Yes (null unless the worker has a mode input) |
| `payload` | Worker-specific result payload, defined in the worker's own `references/contracts/*-contract.md`; present only when `status: completed` | Conditional (see status table) |
| `warnings` | Non-blocking warnings | Yes (may be empty) |
| `report` | Short human-readable summary | Yes |

## `status` values and field constraints

| `status` | Meaning | Mandatory | Forbidden |
|---|---|---|---|
| `needs_user_input` | Worker needs a user decision | `question_packet` | `written_artifacts`, `workflow_patch`, `blocking_reason`, `payload` |
| `completed` | Worker finished | `payload` | `question_packet` |
| `blocked` | An external condition must be resolved first | `blocking_reason` | `question_packet`, `payload` |
| `invalid_input` | The input envelope itself was invalid | `blocking_reason` | `question_packet`, `payload` |
| `stale_input` | The worker detected that its own input was stale | — | `question_packet`, `payload` |
| `failed` | Execution failed | `blocking_reason` | `question_packet`, `payload` |

Source: design-input.md 5.3 states the `needs_user_input`/`completed`
mandatory-and-forbidden pair explicitly; the `blocked` /`invalid_input` /
`stale_input` / `failed` forbidden columns follow from the same table's
general rule that `question_packet` and `payload` are each populated for
exactly one status (`needs_user_input` and `completed` respectively) and
therefore absent from every other status.

Re-dispatch behavior per status:

- `invalid_input`: MUST NOT be re-dispatched without first fixing the
  input that was rejected.
- `stale_input`: may be re-dispatched.
- `failed`: may be re-dispatched exactly once with the same input.

## `mode_echo` rule

A worker whose input carries a mode-selecting field copies that field's
value into its output `mode_echo` verbatim. Today only
`requirements-analyst`'s `analysis_mode` input qualifies; every other
worker in the 2.3 applicability table always emits `mode_echo: null`.
`scripts/validate-worker-output.py` (`--kind worker-result`) rejects a
result whose `mode_echo` is absent, or does not match the corresponding
input field, as a validation error.

## `written_artifacts` reporting

Whenever a worker writes any file, it lists every written path in
`written_artifacts`, each entry paired with the sha256 digest of the
content it wrote.

## Exclusivity assumption during dispatch (design-input.md 5.11.3)

> During a worker's dispatch, only the orchestrator and the dispatched
> worker may create, modify, or delete files in the integration worktree.
> Other processes may advance the integration branch's ref, but must never
> touch the worktree's files directly.

This assumption applies only to the five workers in the 2.3 applicability
table, and only for the interval from the start of the dispatch's scope
snapshot capture through the end of that dispatch's scope verification —
it is not a standing constraint on the plugin as a whole. The review
phase's wave-parallel auto-fix loop (`references/review-phase.md`) is an
explicit exception governed by its own per-wave verification rules, not by
this assumption.

## Cross-references

- Question packet and answer structure:
  `references/question-packet-schema.md` (design-input.md 5.1, 5.2).
- Per-worker `payload` contracts: `references/contracts/analyst-contract.md`,
  `spec-writer-contract.md`, `planner-contract.md`,
  `rework-planner-contract.md`, `designer-contract.md`.
- Workflow patch structure: `references/workflow-patch.md`
  (design-input.md 5.5).
- Phase-state persistence: `references/phase-state.md` (design-input.md
  5.6).
- Machine validation and fixtures: `scripts/validate-worker-output.py`,
  `references/fixtures/` (design-input.md 5.11.1, 10.5).
