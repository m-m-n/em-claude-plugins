# spec-writer Worker Contract

This document is the output contract for the `spec-writer` worker. It
extends the common dispatch input and worker result envelope defined in
`references/contracts/worker-envelope.md` — every field of that envelope
applies to this worker unchanged. This document states ONLY what is
specific to spec-writer: its additional input fields, its path-level
`write_policy` model, its payload shape, and its post-conditions.

Normative source: `feature-docs/agent-separation/design-input.md` 5.4.2.

## Responsibility

spec-writer produces REQUIREMENTS.md and SPEC.md from
requirements-analyst's resolved requirements. It never writes
workflow.yaml, and it never returns a `question_packet`
(`references/question-packet-schema.md`).

## Additional input fields

Beyond the common envelope input, spec-writer receives:

```yaml
requirements_analysis: {}      # requirements-analyst's resolved_requirements
templates:
  requirements: /absolute/.../templates/requirements-document.md
  spec: /absolute/.../templates/spec-document.md
```

- `requirements_analysis` — the `resolved_requirements` object produced by
  requirements-analyst's `completed` payload (analyst-contract.md). This is
  the sole source of requirement content; spec-writer renders it, it does
  not originate it.
- `templates` — the two document templates spec-writer fills in.

## `write_policy` — the path-level model (shared with designer)

`write_policy.targets` declares protection for **specific, already-known
paths**. Generated artifacts whose path is not fixed in advance (e.g.
mockup HTML) are never listed in `targets`; those are governed by
`allowed_write_roots` (directory-level permission to create) and
`written_artifacts` (post-hoc report of what was actually written).

### The protection split — `targets` vs. `allowed_write_roots`

| Situation at dispatch time | How permission is granted |
|---|---|
| The file **already exists** | Changing or deleting it requires explicit enumeration in `write_policy.targets`. **A file not enumerated in `targets` may not be modified even when it sits under an `allowed_write_roots` directory.** |
| The file **does not yet exist** | Creating it only requires that its path fall under one of `allowed_write_roots`. Its creation MUST be reported afterward in `written_artifacts`. |

Enumerating a path in `targets` is itself the permission to write that one
file — no separate grant is needed.

```yaml
write_policy:
  targets:
    - path: feature-docs/example/REQUIREMENTS.md
      action: create                # create | replace_own | replace_authorized | preserve | extend_only | regenerate
      expect_digest: null            # action-dependent, see table below
      authorization: null
    - path: feature-docs/example/SPEC.md
      action: replace_own
      expect_digest: sha256:abc...
      authorization: null
```

### The six `write_policy` actions

| action | `expect_digest` | worker behaviour |
|---|---|---|
| `create` | always `null` | The file must not already exist. If it does, return `blocked` instead of writing. |
| `replace_own` | required | Overwrites the same-phase output the worker itself produced earlier. If the current digest does not match, return `blocked`. |
| `replace_authorized` | required (the digest as of approval time) | A user-approved overwrite. If the current digest does not match the approved one, return `blocked` (see below — the digest is re-verified even though the overwrite was approved). |
| `preserve` | required | Read-only: the worker must not write this path, only use its content as input. If the digest does not match, return `blocked`. |
| `extend_only` | required | The worker may add new keys but must not modify or remove any existing key. If the digest does not match, return `blocked`. |
| `regenerate` | required | The worker may overwrite this path only if the dispatch also changed its declared `source` file in the same dispatch; if `source` was not changed, the worker must not write this path either. If the digest does not match, return `blocked`. |

**`regenerate` requires no separate user approval.** A regenerated artifact
is mechanically derived from its `source`; because the change to `source`
already went through whatever approval that change required, the derived
artifact's regeneration is covered by that same approval. The target
declares its origin with a `source` field:

```yaml
- path: design-system/tokens.html
  action: regenerate
  source: design-system/tokens.yaml
  expect_digest: sha256:...
```

**`replace_authorized` still verifies the digest even though the user
already approved the overwrite.** The approval covers "the content as of
the moment the approval question was created" — not "whatever the target
contains at dispatch time". If something else updated the target between
question creation and dispatch, that later content was never shown to the
user, so it is not covered by the approval. A digest mismatch under
`replace_authorized` therefore still returns `blocked`, and the
orchestrator treats the input as stale and re-requests approval.

### `extend_only` key-comparison rule

`extend_only` currently applies only to `design-system/tokens.yaml`. The
worker parses the target as a YAML map, computes the full set of existing
key paths (nested keys joined with `.`) together with their values, and
confirms every one of them is unchanged in the new content. The worker
returns `blocked` (comparison not possible) when the target is not a map,
or when it contains a YAML alias or merge key. Any removed key, or any
changed value for an existing key, is a blocked case as well.

## How the orchestrator chooses each target's action before dispatch

Before dispatching spec-writer, the orchestrator inspects each target
path's current digest and decides its `action`:

- The path does not exist → `create`.
- The path exists and its digest matches the immediately preceding
  same-phase worker output → `replace_own`.
- The path exists and its digest does **not** match → this is the
  digest-mismatch branch. In interactive mode the orchestrator raises a
  `gate_id: {phase}.artifact-overwrite` question offering overwrite /
  preserve-existing / abort; the answer sets the target's action to
  `replace_authorized`, `preserve`, or aborts the phase. In batch mode the
  orchestrator instead follows the `batch-policies.yaml` decision recorded
  for that gate.

## `completed` payload

- `spec_index`:
  - `requirements[]` — `id`, `title`, `status`, `tbd_reason`
  - `test_scenarios[]` — `id`, `requirement_ids`
- `assumptions_written[]`

## Post-conditions

- FR/NFR IDs are unique and match `^(FR|NFR)[1-9][0-9]*$`.
- `spec_index.requirements` IDs agree exactly with the IDs that appear in
  SPEC.md.
- Every requirement with `status: tbd` has a non-empty `tbd_reason`.
- **spec-writer must not invent requirements or assumptions that
  requirements-analyst did not produce.** Every requirement and assumption
  in the output must trace back to `requirements_analysis`.

## Gate option vocabulary

The option vocabulary a batch-policies.yaml `option_id` is checked against
(`references/gate-option-vocabulary.md` states the correspondence rule and
format this table follows). One shared block: the three
`{phase}.artifact-overwrite` gates ("How the orchestrator chooses each
target's action before dispatch", above) offer identical semantics, so each
gate gets its own row per option rather than one row shared across gates.

| gate_id | option_id | meaning |
|---|---|---|
| `create-spec.artifact-overwrite` | `preserve_and_reuse` | Batch mode's default: treat the existing artifact as authoritative — re-dispatch with that target's action set to `preserve`; the phase continues only if the existing artifact still passes the worker's postconditions. |
| `create-spec.artifact-overwrite` | `overwrite` | The user chooses to overwrite the existing artifact; the target's action becomes `replace_authorized`. |
| `create-spec.artifact-overwrite` | `abort` | The user chooses to abort the phase rather than touch the existing artifact. |
| `design.artifact-overwrite` | `preserve_and_reuse` | Batch mode's default: treat the existing artifact as authoritative — re-dispatch with that target's action set to `preserve`; the phase continues only if the existing artifact still passes the worker's postconditions. |
| `design.artifact-overwrite` | `overwrite` | The user chooses to overwrite the existing artifact; the target's action becomes `replace_authorized`. |
| `design.artifact-overwrite` | `abort` | The user chooses to abort the phase rather than touch the existing artifact. |
| `create-plan.artifact-overwrite` | `preserve_and_reuse` | Batch mode's default: treat the existing artifact as authoritative — re-dispatch with that target's action set to `preserve`; the phase continues only if the existing artifact still passes the worker's postconditions. |
| `create-plan.artifact-overwrite` | `overwrite` | The user chooses to overwrite the existing artifact; the target's action becomes `replace_authorized`. |
| `create-plan.artifact-overwrite` | `abort` | The user chooses to abort the phase rather than touch the existing artifact. |
