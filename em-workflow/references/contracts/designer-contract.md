# designer Contract (em-workflow SSOT)

Input/output contract for the `designer` worker. Renders design-input.md
5.4.5 and 4.2. This document adds only designer-specific content; the
common dispatch envelope is defined once in
`references/contracts/worker-envelope.md` and is not restated here. The
path-level write-policy model (the six actions, the `targets` /
`allowed_write_roots` split, `expect_digest` requirements) is owned by
`references/contracts/spec-writer-contract.md` and is cited by path below,
not restated.

## Responsibility

Execute the existing designer process (D0-D4) as a Task. The designer is
**fully autonomous**: it returns neither a `question_packet` nor a
`workflow_patch`.

- No `question_packet`: of the common envelope's six `status` values, the
  designer's dispatch never resolves to the one that requires a
  `question_packet`; every dispatch instead resolves to one of the
  remaining five: `completed` / `blocked` / `invalid_input` / `stale_input`
  / `failed`.
- No `workflow_patch`: design-input.md 4.2 states the reason — returning
  the written artifacts is enough for the orchestrator to advance the
  design step to `completed`, and since decision authority stays with the
  orchestrator regardless, routing that decision through a patch adds no
  information the artifacts didn't already carry.

## Additional input: `design_inputs`

```yaml
design_inputs:
  requirements_path: /absolute/.../REQUIREMENTS.md
  spec_path: /absolute/.../SPEC.md
  workflow_path: /absolute/.../workflow.yaml
  design_token_template: /absolute/.../references/templates/design-tokens.yaml
```

Project-native design system files, other features' `DESIGN.md` files, and
`visual_inputs` are supplied via `resolved_input_paths` (the common
envelope's `project_design_system` / `other_features_design` /
`visual_inputs` categories), not via `design_inputs`.

## write_policy targets

The designer may produce `DESIGN.md`, `design-system/tokens.yaml`,
`design-system/tokens.html`, and any number of mockup HTML files. The first
three have paths fixed in advance and so are listed in
`write_policy.targets`; a new mockup's filename is the designer's own
choice, so new mockups are governed by `allowed_write_roots` instead, with
`written_artifacts` reporting each path created after the fact. **An
existing mockup being updated (not created) is the existing-file case and
so it too must be listed in `targets`** (the general targets/allowed-roots
split owned by `references/contracts/spec-writer-contract.md`).

```yaml
allowed_write_roots:
  - feature-docs/example/design/mockups/
write_policy:
  targets:
    - path: feature-docs/example/DESIGN.md
      action: create
      expect_digest: null
    - path: design-system/tokens.yaml
      action: extend_only
      expect_digest: sha256:...
    - path: design-system/tokens.html
      action: regenerate
      source: design-system/tokens.yaml
      expect_digest: sha256:...
    - path: feature-docs/example/design/mockups/screen-main.html   # existing mockup update only
      action: replace_own
      expect_digest: sha256:...
```

**Why `design-system/` is not an `allowed_write_root`**: the designer only
ever legitimately writes two files under it, `tokens.yaml` and
`tokens.html`, both with paths fixed in advance and both already covered by
`targets` (`create` / `extend_only` / `regenerate`). Granting the whole
directory as an allowed write root would additionally let through an
out-of-scope new file (e.g. a stray `design-system/theme.css`) that
`targets` would otherwise block. `allowed_write_roots` is reserved for the
one case where the designer's write target genuinely cannot be pinned in
advance: new mockup filenames.

## Token yaml/html linkage

The existing designer behavior — every change to `tokens.yaml` is followed
by regenerating `tokens.html` — is expressed as `tokens.html`'s
`action: regenerate` with `source: design-system/tokens.yaml`. Verification
is bidirectional:

- If `written_artifacts` includes `tokens.yaml`, it must also include
  `tokens.html`.
- If `tokens.html` alone is present in `written_artifacts` (its `source` was
  not also written), that is a violation.

Because the designer is fully autonomous and never obtains user approval
mid-run, an existing `tokens.yaml` is always `extend_only` and
`tokens.html` is always `regenerate` — `replace_authorized` (which requires
a prior approval question) never applies to either file for this worker.

## `project.design_system.kind` × token-existence table

design-input.md 5.0 R1 / 5.4.5. `kind` and the actual existence of
`design-system/tokens.yaml` / `tokens.html` jointly determine the targets
the orchestrator sets before dispatch:

| `kind` | `tokens.yaml` | `tokens.html` | targets (yaml / html) | Note |
|---|---|---|---|---|
| `project_native` | any | any | **not listed** | `paths` (the project-native files) are a read-only input. Any existing `design-system/tokens.yaml` / `tokens.html` is left out of `targets` entirely, so it is protected by the general targets rule (an existing file not enumerated in `targets` may not be touched) and cannot be newly created either (`allowed_write_roots` is only `design/mockups/`). Leftover em-workflow tokens are never updated. |
| `em_workflow` | yes | yes | `extend_only` / `regenerate` | Normal path. |
| `em_workflow` | yes | no | `extend_only` / `create` | `tokens.html` is a generated artifact: it gets created only if `tokens.yaml` was actually changed this dispatch (`create` means "reject if it exists", not "must be written"). |
| `em_workflow` | no | yes | — | **ABORT before dispatch.** A generated artifact existing without its source is an inconsistent state; the designer is never asked to judge it. The orchestrator reports the offending path; recovery is for the user to delete `tokens.html` or restore `tokens.yaml`, then resume. |
| `em_workflow` | no | no | `create` / `create` | Same as drafting from scratch. |
| `none` | no | no | `create` / `create` | Fresh draft. |
| `none` | yaml or html exists | — | — | **ABORT before dispatch, then run the reclassification gate** (below). `kind: none` claims no design system exists, but a token file is present — that claim cannot be true, so dispatch does not proceed on the stale `kind`. |

Two rows are abort cases: `em_workflow` with `tokens.yaml` absent and
`tokens.html` present, and `none` with either token file present.

**This cross-product check is not design-step-specific.** Every phase that
consumes `project.design_system` in `digest_inputs` /
`resolved_input_paths` — design and create-plan — runs the same check
before dispatching its worker, so the inconsistency is caught even on the
path where the design step was `skipped` and `create-plan` runs next. It is
implemented in `references/phases/create-plan-phase.md`'s preconditions for
create-plan, and (because design has no dedicated phase protocol document)
in `skills/develop/SKILL.md`'s design-step branch, immediately before the
designer is dispatched, for design.

## Reclassification gate (`design-system.reclassify`)

Triggered when `kind: none` but a token file exists. This does **not**
return to create-spec — create-spec is already `completed`, and re-entering
it would re-run other already-confirmed values along with this one. Instead
it is a standalone gate, executed in place, run at whichever entry point
(design or create-plan) hit the abort:

1. Dispatch requirements-analyst with `analysis_mode:
   design_system_detection` to get design-system candidates.
   - If candidate discovery hit the safe upper bound (`truncated: true`),
     apply the 5.0 R1 truncation rule instead of proceeding: interactive
     asks (same `design-system.reclassify` gate) for a manual `kind` /
     `paths`; batch **aborts** rather than falling back to the default
     reclassification below.
2. Ask (interactive, `gate_id: design-system.reclassify` — a phase-independent
   name, shared by both the design and create-plan entry points) to
   reconfirm `kind` and `paths`, showing the token file(s) that were found.
   In batch, follow `batch-policies.yaml`'s policy for this gate (default:
   reclassify to `em_workflow`, since a token file existing means `none`
   was the wrong classification).
3. Update `workflow.yaml`'s `project.design_system` and commit via
   `commit-docs.sh` with message `docs({feature}): reclassify
   design_system`.
4. Re-read `workflow.yaml` and **resume from the same step's preconditions**
   (the step's `status` is not changed by this gate).
5. If the newly-confirmed `kind` still lands on one of the two abort rows
   above (e.g. reclassified to `em_workflow` but `tokens.yaml` is still
   absent while `tokens.html` exists), follow that row's own recovery
   procedure — there is no separate gate for this secondary case.

## `digest_inputs`

`REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`, `design-system/tokens.yaml`,
`design-system/tokens.html`, `references/templates/design-tokens.yaml`,
other features' `DESIGN.md` files, each project-native design system file,
each `optional_visual_inputs` file, this contract document itself.

**`project_native` exclusion**: when `project.design_system.kind:
project_native`, `design-system/tokens.yaml` and `design-system/tokens.html`
are excluded from `digest_inputs` (they are not judgment inputs when the
project has its own design system, even if leftover files exist). Under
`project_native`, the project's own design-system files that DO enter
`digest_inputs` (`each project-native design system file`, above) arrive
only through `resolved_input_paths.project_design_system` — the designer
never discovers them itself (see "Additional input" above).

## `completed` payload

```yaml
payload:
  design_summary:
    decisions_count: 4
    open_items: []
    tokens: [color.primary, spacing.md]
    mockups: [feature-docs/example/design/mockups/screen-main.html]
```

The orchestrator sets the design step's `status` and `completed_at_commit`
(rule R2) itself after verifying the written artifacts — the designer does
not set either.

## Scope & concurrency assumption

During dispatch, only the orchestrator and the dispatched worker may create,
modify or delete files in the integration worktree (design-input.md
5.11.3); this assumption applies for the interval from scope-snapshot
capture through scope verification, and is not a permanent constraint on
the plugin as a whole.

## Gate option vocabulary

The option vocabulary a batch-policies.yaml `option_id` is checked against
(`references/gate-option-vocabulary.md` states the correspondence rule and
format this table follows).

| gate_id | option_id | meaning |
|---|---|---|
| `design-system.reclassify` | `em_workflow` | Batch mode's default: reclassify to em-workflow's own design system, since an existing token file means `none` was the wrong classification. |
| `design-system.reclassify` | `project_native` | The user reclassifies to the project's own native design system. |
| `design-system.reclassify` | `none` | The user reclassifies back to no design system. |
