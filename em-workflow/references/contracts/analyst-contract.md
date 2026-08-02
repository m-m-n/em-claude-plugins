# requirements-analyst Worker Contract

This document is the output contract for the `requirements-analyst` worker.
It extends the common dispatch input and worker result envelope defined in
`references/contracts/worker-envelope.md` — every field of that envelope
applies to this worker unchanged. This document states ONLY what is specific
to requirements-analyst: its additional input fields, its payload shapes,
and the rules unique to its two modes.

Normative source: `feature-docs/agent-separation/design-input.md` 5.0 R1 and
5.4.1.

## Responsibility

requirements-analyst performs the investigation and question-generation half
of create-spec:

- Project context inspection (`CLAUDE.md`, test conventions, E2E
  infrastructure, project commands, license detection).
- Generating requirement-clarification candidates (objectives, functional
  and non-functional requirements, acceptance criteria, edge cases).
- Command and license detection.
- Design-step recommendation.
- Design-system candidate detection and classification.

requirements-analyst performs NONE of the following: it writes no files, it
makes no commits, it performs no branch or worktree operations, and it never
calls AskUserQuestion or otherwise asks the user directly. Any user-facing
question it needs answered is expressed as a `question_packet`
(`references/question-packet-schema.md`) in its result, for the orchestrator
to resolve.

## Additional input fields

Beyond the common envelope input, requirements-analyst receives:

```yaml
analysis_mode: full           # full | design_system_detection
analysis_scope:                # each item's real paths arrive via resolved_input_paths (envelope)
  inspect_claude_md: true
  inspect_test_conventions: true
  inspect_e2e: true
  inspect_project_commands: true
  inspect_license: true
  decide_design_step: true
task_description: |
  The feature description supplied by the user.
known_feature_name: example-feature
```

- `analysis_mode` — selects which of the two contract modes below applies.
  Copied back verbatim as `mode_echo` (see below).
- `analysis_scope` — which categories of project-context inspection the
  orchestrator wants this dispatch to perform. Only meaningful in
  `analysis_mode: full`; `design_system_detection` ignores it entirely.
- `task_description` — the free-form feature description the user supplied.
  May be null on a repeat dispatch where it was already established.
- `known_feature_name` — the feature name already resolved by the
  orchestrator, when known.

## `analysis_snapshot` (returned with `status: needs_user_input`)

When requirements-analyst cannot proceed without user clarification, its
`payload.analysis_snapshot` carries the following fields:

- `feature_name_candidate`
- `objectives`
- `functional_requirements`
- `non_functional_requirements`
- `acceptance_criteria`
- `user_experience`
- `edge_cases`
- `security_constraints`
- `project_context` — `languages`, `frameworks`,
  `existing_test_infrastructure`, `existing_e2e_infrastructure`
- `detected_commands` — list of `component`, `field`, `value`, `evidence`
- `detected_license` — `spdx`, `confidence`
- `design_step_recommendation` — `value`, `reason`
- `design_system_candidates` — candidate paths and their classification;
  detection and classification only, no `kind` decision (see below)

This payload is exclusive to `analysis_mode: full` (see the mode table
below).

## `completed` payload (`analysis_mode: full`)

When `analysis_mode: full` reaches `status: completed`, `payload` MUST
contain:

- `resolved_requirements`:
  - `feature_name`
  - `business_objectives`
  - `functional_requirements[]` — `id`, `title`, `statement`, `status`,
    `tbd_reason`
  - `non_functional_requirements[]`
  - `acceptance_criteria`
  - `test_scenarios`
  - `assumptions`
  - `design_step` — `status`, `skipped_reason`
- `project_detection` — `license`, `components`
- `design_system_candidates`

## `analysis_mode: design_system_detection` (lightweight, backfill-only)

A restricted mode used only for the `design-system` backfill path
(design-input.md 5.12). It detects design-system candidates and nothing
else.

- `analysis_scope` is ignored entirely.
- The `completed` payload contains **only** `design_system_candidates`.
  `resolved_requirements` and `project_detection` are **prohibited** in this
  mode — including either is a validation error.
- This mode can return only three of the six envelope `status` values:
  `completed`, `blocked`, `failed`. It never returns `needs_user_input` — it
  never returns a `question_packet`.
- `digest_inputs` (below) is restricted to the design-system candidate
  search inputs; the full-mode input set does not apply.

`scripts/validate-worker-output.py` enforces this exclusivity by branching
on `analysis_mode` (design-input.md 5.4.1).

## `digest_inputs`

Per design-input.md 5.0 R1, this is the exhaustive set of inputs that can
influence this worker's output. The orchestrator builds `input_digest` from
exactly this set — nothing more, nothing less.

| mode | `digest_inputs` (files) | `value_inputs` |
|---|---|---|
| `full` | `CLAUDE.md` (project root and the relevant directory), `LICENSE`, whichever package manifest files exist, `test/README.md`, resolved E2E-discovery paths, resolved design-system candidate paths, existing REQUIREMENTS.md / SPEC.md, this contract document itself | `task_description` |
| `design_system_detection` | resolved design-system candidate paths, this contract document itself | — |

The orchestrator resolves every glob-derived category (E2E discovery,
design-system candidates) **before** dispatch and lists the resolved paths
in the envelope's `resolved_input_paths`. requirements-analyst reads nothing
outside the fixed-path inputs the envelope supplies plus the entries of
`resolved_input_paths` — it never performs its own filesystem discovery.

## `mode_echo`

requirements-analyst is the one worker whose input carries a mode selector.
It MUST copy `analysis_mode` verbatim into the result's `mode_echo` field.
Validation confirms the input `analysis_mode` and the returned `mode_echo`
match before applying either mode's payload-exclusivity rules; a missing or
mismatched `mode_echo` is a validation error.

## Design-system candidate categories

requirements-analyst reports design-system candidates by classifying each
resolved path (supplied via `resolved_input_paths.design_system_candidates`)
into one of the following categories:

- Token definition files
- Utility CSS configuration
- Design-system directories
- CSS variable definitions
- Native theme files

**requirements-analyst detects and classifies design-system candidates; it
does not decide the project's `kind`** (`project_native` / `em_workflow` /
`none`). That decision belongs to the orchestrator-driven create-spec
procedure (design-input.md 5.0 R1, 5.7 step 11a).

## Gate identifiers

requirements-analyst never asks the user directly; every user-facing
decision it raises is expressed as a `question_packet` question whose
`gate_id` joins it to a batch policy in `references/batch-policies.yaml`.
`analysis_mode: full` raises exactly these decision points:

| decision point | `gate_id` |
|---|---|
| Requirement clarification (any unresolved objective, functional or non-functional requirement, acceptance criterion, user-experience point, edge case, security constraint, or similar) | `create-spec.requirement-clarification` |
| Design-step recommendation | `create-spec.design-step` |

`analysis_mode: design_system_detection` never returns a `question_packet`
(see above) and so raises neither gate. Gate resolution itself —
interactive prompting, or the decision table in batch mode — is entirely
orchestrator-owned per `references/question-resolution.md` and
`references/batch-policies.yaml`; this worker's only responsibility toward
that mechanism is assigning each question its `gate_id`.

## Exclusivity assumption

During its dispatch window, requirements-analyst assumes exclusive access to
the integration worktree: no other worker dispatch or orchestrator commit
runs against that worktree while this worker is executing
(design-input.md 5.11.3).
