# implementation-planner Contract (em-workflow SSOT)

Input/output contract for the `implementation-planner` worker. Renders
design-input.md 5.4.3 and the `implementation-planner` row of 5.0 R1. This
document adds only planner-specific content; the dispatch envelope shape
(input fields, output fields, the six `status` values and their
exclusivity constraints, `mode_echo`, `written_artifacts` reporting, the
read-restriction rule) is defined once in
`references/contracts/worker-envelope.md` and is not restated here. The
question packet / answer shape is defined once in
`references/question-packet-schema.md` and is not restated here.

## Responsibility

Analysis, `IMPLEMENTATION.md`, task plans (`tasks/taskNNNN.md`) and
`VERIFICATION.md`. The planner never calls AskUserQuestion itself — that
tool has exactly one caller, the orchestrator (design-input.md 4.1) — and
never writes `workflow.yaml` directly (workers treat it read-only; the
planner's only channel for a `workflow.yaml` change is the `workflow_patch`
it returns, per `references/workflow-patch.md`). The planner MAY still
return `status: needs_user_input` with a `question_packet` (see "Question
packet bundling rule" below) — "no user questions" means the planner does
not perform the asking, not that it never has anything to ask.

## Additional input: `planning_inputs`

```yaml
planning_inputs:
  requirements_path: /absolute/.../REQUIREMENTS.md
  spec_path: /absolute/.../SPEC.md
  design_path: /absolute/.../DESIGN.md        # null if design step was skipped
  lessons_path: /absolute/.../LESSONS.md      # null if the project has none
  impl_skills_registry: /absolute/.../references/impl-skills.yaml
  review_rules: /absolute/.../references/review-rules.yaml
  license_compat: /absolute/.../references/license-compat.md
  threat_model_template: /absolute/.../references/templates/threat-model.md
  plugin_versioning: {...}                    # a value resolved by the orchestrator at dispatch, not a path
  feature_docs_correction: {...}              # a value resolved by the orchestrator on the feature-docs correction dispatch; null on every other dispatch
```

`write_policy` is also part of the input, in the common path-level form
defined by `references/contracts/spec-writer-contract.md` (the write-policy
model's owning document — the actions, the `targets` /
`allowed_write_roots` split, `expect_digest` requirements). This contract
does not restate that model. The planner's `write_policy.targets` cover
`IMPLEMENTATION.md` and `VERIFICATION.md` (action `create` on a first pass,
`replace_own` on a same-phase rewrite); `THREAT-MODEL.md` is a target on the
same terms (action `create` on a first pass, `replace_own` on a same-phase
rewrite — the existing re-plan authorization path applies unchanged). At the
`minimal` tier, `TASK.md` is additionally a write_policy target with action
`extend_only` and `expect_digest` set to its digest at dispatch time (see
the minimal-tier `TASK.md` append rule below). Task plan files are new per
task and so are governed by `allowed_write_roots` (`tasks/`) with
`written_artifacts` reporting each path created. `amend_other_feature` targets
appear in `write_policy.targets` only after a request, as
`## Other-feature documents` below states.

### Minimal-tier `TASK.md` append (SC-3)

Applies only when the tier is `minimal` and the threat-model verdict is
`threats-identified`. This is the Markdown counterpart of the `extend_only`
key-comparison rule `references/contracts/spec-writer-contract.md` owns for
YAML — the same action, applied to a Markdown file's exact-prefix content
instead of a YAML key set.

- **write_policy target**: `feature-docs/{feature}/TASK.md`, action
  `extend_only`, `expect_digest` = its digest at dispatch time. The
  orchestrator includes this target on every minimal-tier dispatch — the
  verdict is not known before dispatch — but the planner writes to it only
  for `threats-identified`.
- **Exact-prefix rule**: the pre-existing content of `TASK.md` must be an
  exact prefix of the new content.
- **No-heading rule**: the appended text contains no heading line.
- **Final-section precondition**: `## Expected Result` must be the final
  section of the pre-existing file. When it is missing or not final, the
  planner returns `blocked` (an existing `status` value) and writes nothing
  to `TASK.md`.
- **written_artifacts**: `TASK.md` appears in `written_artifacts` only when
  it was actually appended.

### plugin_versioning (dispatch-resolved value)

`planning_inputs.plugin_versioning` describes the repository's exemption
state and plugin locations. Unlike the path entries above it is a value: the
orchestrator computes it and places it in the dispatch, and the planner never
discovers either piece of state itself. The same value, resolved the same
way, is also passed to rework-planner;
`references/contracts/rework-planner-contract.md` assigns its place in that
worker's input.

| Field | Meaning | Resolution rule (orchestrator, inside the integration worktree) |
|---|---|---|
| `exempt` | boolean | true exactly when `.github/workflows/plugin-version-bump.yml` exists at the worktree root |
| `plugins` | list, one entry per plugin | every git-tracked directory that contains `.claude-plugin/plugin.json`; entries sorted by `dir` ascending so the value's digest is deterministic |
| `plugins[].dir` | project-relative path of the plugin directory | the directory that holds `.claude-plugin/` |
| `plugins[].name` | plugin name | the `name` declared in that plugin's `plugin.json` |
| `plugins[].marketplace_versioned` | boolean | true exactly when the root `.claude-plugin/marketplace.json` has an entry of the same name that carries a version; false when the file or the entry is absent, or the entry carries no version |

- **Resolution timing**: the orchestrator resolves the value at every
  implementation-planner dispatch (create-plan, including re-dispatches that
  carry answers), from the integration worktree's current state. When it
  recomputes `input_digest` on the planner's return, it re-resolves the value
  the same way.
- **Mandatory**: the value is mandatory on every create-plan dispatch. A
  dispatch without it is answered with `invalid_input` (a `status` value
  defined by `references/contracts/worker-envelope.md`).
- **Untrusted**: the value is untrusted input under
  `references/contracts/worker-envelope.md`'s Untrusted-Input Handling
  section (TM-1), which this contract cites and does not restate. It carries
  only the exemption boolean, project-relative plugin directory paths, plugin
  names and the per-plugin marketplace flag — no other text copied from
  repository files.
- **Use**: the planner uses only this value. How it is applied is owned by
  `skills/plan-writing/SKILL.md`'s "Plugin Version Handling" section and is
  not restated here.

### path_correction (dispatch-resolved value)

`planning_inputs.path_correction` is present on the final-path correction
dispatch and null on every other dispatch. Like `plugin_versioning` it is a
value, not a path: the orchestrator resolves it and places it in the
dispatch, and the planner never discovers its content itself. When the
orchestrator dispatches, and how it resolves the value, are owned by
`references/phases/create-plan-phase.md`, section
`## 13. Final-path correction dispatch`, and are not restated here.

```yaml
path_correction:                   # null on every other dispatch
  targets:                         # one entry per task whose path is corrected
    - task_id: task0004
      old_path: <repository-relative path>
```

- **Shape**: `targets` is a list of mappings with exactly `task_id` and
  `old_path`.
- **Untrusted**: the value is untrusted input under
  `references/contracts/worker-envelope.md`'s Untrusted-Input Handling
  section, which this contract cites and does not restate. It carries only
  task ids and project-relative paths.
- **Digest**: when present it is a `value_inputs` member of this worker's
  `input_digest`, as stated under `## digest_inputs` below.
- **write_policy**: on this dispatch `write_policy.targets` has action
  `replace_own` for IMPLEMENTATION.md, VERIFICATION.md and each target's task
  plan.
- **Output**: the `workflow_patch` is `replace_planning` carrying
  `tasks_patch.path_corrections`, whose shape and permission conditions are
  owned by `references/workflow-patch.md`, section
  `## Final-path correction`. `payload.task_index` lists only `entries`, and
  may be empty.
- **Process**: what the planner does with the value is owned by
  `agents/implementation-planner.md`, section `## Final-path correction`.

### feature_docs_correction (dispatch-resolved value)

`planning_inputs.feature_docs_correction` is present on the feature-docs
correction dispatch and null on every other dispatch. Like `path_correction`
it is a value, not a path: the orchestrator resolves it and places it in the
dispatch, and the planner never discovers its content itself. When the
orchestrator dispatches, and how it resolves the value, are owned by
`references/phases/create-plan-phase.md`, section
`### Feature-docs correction dispatch` (inside
`## 13. Final-path correction dispatch`), and are not restated here.

```yaml
feature_docs_correction:           # null on every other dispatch
  targets:                         # one entry per (task, path) pair to correct
    - task_id: task0004
      path: <repository-relative path>
```

- **Shape**: `targets` is a list of mappings with exactly `task_id` and
  `path`.
- **Exclusive**: the value is never non-null together with `path_correction`.
- **Untrusted**: the value is untrusted input under
  `references/contracts/worker-envelope.md`'s Untrusted-Input Handling
  section, which this contract cites and does not restate. It carries only
  task ids and project-relative paths.
- **Digest**: the orchestrator includes it, when present, as a
  `value_inputs` member of this worker's `input_digest`, as stated under
  `## digest_inputs` below.
- **write_policy**: on this dispatch `write_policy.targets` has action
  `replace_own` for IMPLEMENTATION.md, VERIFICATION.md and each target's task
  plan, plus the `amend_other_feature` targets after a request
  (`## Other-feature documents` below). `allowed_write_roots` is empty.
- **Output**: the `workflow_patch` is `replace_planning` carrying
  `tasks_patch.feature_docs_removals`, whose shape and permission conditions
  are owned by `references/workflow-patch.md`, section
  `## Feature-docs correction`. `payload.task_index` is empty.
- **Process**: what the planner does with the value is owned by
  `agents/implementation-planner.md`, section `## Feature-docs correction`.

## Question packet bundling rule

Questions covering TBD resolution, license conflict, and existing-file
disposition MUST be bundled into a single `question_packet` (one
`needs_user_input` iteration), not split across several. The one exception:
if license-candidate discovery depends on the answer to a TBD question,
those two MAY be split across separate iterations, because the second
question cannot be formed until the first is answered.

An `assumptions[].reversible` entry is `false` only for an assumption
about an operation that cannot be undone once applied; it is `true` for a
preserved constraint, an invariant, or a fact pinned by an existing test
(`references/question-packet-schema.md`).

## digest_inputs

Per 5.0 R1, the orchestrator builds `input_digest` from exactly the set this
contract declares — the planner does not expand it:

- `REQUIREMENTS.md`, `SPEC.md`, `DESIGN.md`, `LESSONS.md`, `workflow.yaml`
- `references/impl-skills.yaml`, `references/review-rules.yaml`,
  `references/license-compat.md`, `references/workflow-schema.md`
- `references/templates/task-plan.md`, `skills/plan-writing/SKILL.md`,
  `references/templates/threat-model.md`
- `design-system/tokens.yaml` (design system tokens — see exception below),
  or the project-native design system's own files
- the existing `IMPLEMENTATION.md` / `VERIFICATION.md` / `THREAT-MODEL.md` /
  everything under `tasks/` (so a re-plan detects drift against what is
  already written)
- each `amend_other_feature` target of the dispatch (the document the grant
  lets the planner amend; see `## Other-feature documents` below)
- this contract document itself (a contract change alters the planner's
  output shape)

The planner's `value_inputs` has one member, `plugin_versioning` (defined
under "### plugin_versioning (dispatch-resolved value)" above), digested per
`references/contracts/worker-envelope.md` rule R1's normalization of the
value. `value_inputs` gains `planning_inputs.path_correction` as a member when
it is present (defined under "### path_correction (dispatch-resolved value)"
above), digested the same way. `value_inputs` gains
`planning_inputs.feature_docs_correction` as a member when it is present
(defined under "### feature_docs_correction (dispatch-resolved value)" above),
digested the same way. `task_description` is not part of the
planner's input; that belongs to requirements-analyst.

**`project.design_system.kind` exception** (design-input.md 5.4.5): when
`kind: project_native`, `design-system/tokens.yaml` and
`design-system/tokens.html` are excluded from `digest_inputs` — the planner
must not use leftover em-workflow tokens as a judgment input when the
project has its own design system. The full `kind` × token-existence
cross-product this exception is drawn from is owned by
`references/contracts/designer-contract.md`; this contract only states the
consequence for the planner's own `digest_inputs`.

The orchestrator applies the self-write rule of
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing", when it recomputes `input_digest` on this worker's
return. The overlap between this worker's `digest_inputs` and the paths its
`write_policy` lets it write is `IMPLEMENTATION.md`, `VERIFICATION.md`,
`THREAT-MODEL.md` and `tasks/`, together with the document of each
`amend_other_feature` target of the dispatch.

## `completed` payload

```yaml
written_artifacts: [...]        # IMPLEMENTATION.md, VERIFICATION.md, THREAT-MODEL.md, tasks/taskNNNN.md — paths only, sha256 computed by the orchestrator; TASK.md too at the minimal tier, only when appended
workflow_patch: {...}           # operation: replace_planning — see references/workflow-patch.md
payload:
  task_index:
    task0001: { title: ..., complexity: medium, domains: [...], requirements: [FR1] }
  # other_feature_doc_fixes:         # stage 2 of the other-feature route only, when granted documents were amended
  #   - { path: ..., change: ..., reason: ... }
```

The `completed` output is this triple: `written_artifacts`, `workflow_patch`
and `payload.task_index`. On the final-path correction dispatch,
`payload.task_index` follows the rule of "### path_correction
(dispatch-resolved value)" above. On the feature-docs correction dispatch,
`payload.task_index` follows the rule of "### feature_docs_correction
(dispatch-resolved value)" above. The request result of the other-feature
route is the stage-1 `completed` shape that `## Other-feature documents` below
defines (empty `written_artifacts`, null `workflow_patch`, no
`payload.task_index`); a stage-2 result adds `payload.other_feature_doc_fixes`
to the triple and reports each amended document in `written_artifacts`. The
`workflow_patch` the planner returns uses
`operation: replace_planning` (bound to `tasks_patch.mode: replace_all`,
targeting the `create-plan` step); the operation's permission conditions,
the `tasks_patch` entry shape, and the application rules are owned by
`references/workflow-patch.md` and are not restated here.

On a re-planning pass (the Re-planning path —
`references/workflow-patch.md`'s `replace_all` permission conditions own
which states satisfy it, and is not restated here as a single `create-plan`
status literal), `tasks_patch` also carries `carried_task_ids` alongside
`entries`. What the two fields mean — eligibility, disjointness, and how a
carried id's record is copied — is owned by `references/workflow-patch.md`'s
Re-planning task-id allocation section and is not restated here.

## Prohibited fields

The planner MUST NOT set: `branch`, `notes`, any running/in-progress
`status` value, or `completed_at_commit` on any task or step. These are
orchestrator-owned — `completed_at_commit` specifically is reserved to the
orchestrator by rule R2 (design-input.md 5.0), and `references/workflow-patch.md`'s
`step_patches` contract permits only `status` as a settable field with
`base_commit` / `completed_at_commit` excluded even there.

## Task decomposition, complexity and domains vocabulary

The criteria the planner applies when splitting work into tasks (worktree
independence, size, `files` prediction as a contract, interface contracts
instead of sequencing, Acceptance Criteria, integration wiring ownership)
and the `complexity` levels (`low` / `medium` / `high`) are owned by
`skills/plan-writing/SKILL.md` ("Task decomposition rules" and "complexity
criteria" sections) and are not restated here — the planner is dispatched
with that skill loaded and follows it directly.

The `domains` vocabulary used in `tasks_patch` entries is described (not
owned) by `skills/plan-writing/SKILL.md`; its single source of truth is
`references/review-rules.yaml`, per `references/workflow-patch.md`'s
"Domains vocabulary SSOT" section and design-input.md 5.5.6.

## Scope & concurrency assumption

During dispatch, only the orchestrator and the dispatched worker may create,
modify or delete files in the integration worktree (design-input.md
5.11.3); this assumption applies for the interval from scope-snapshot
capture through scope verification, and is not a permanent constraint on
the plugin as a whole.

## Other-feature documents

The planner changes an existing document of another feature only through the
two stages below, with a grant from the orchestrator between them. The route
applies when the plan needs such a document changed. The write_policy action
`amend_other_feature` is owned by
`references/contracts/spec-writer-contract.md` (its action table) and is not
restated here.

- **Stage 1: the request result.** When the plan needs another feature's
  document changed and the dispatch carries no `amend_other_feature` target,
  the planner writes nothing and returns `status: completed` with empty
  `written_artifacts`, a null `workflow_patch` and a payload holding only
  `other_feature_doc_requests`: a non-empty list of mappings with exactly
  `path` and `reason` (non-empty strings, paths unique). The request result is
  admitted only on a dispatch without `amend_other_feature` targets. A
  question packet takes precedence over it.
- **Grant and re-dispatch.** The orchestrator adds one `amend_other_feature`
  target per requested in-scope path that exists as a regular file, sets
  `expect_digest` to the digest of that path at dispatch, and re-dispatches
  under a new `request_id` with the same planning inputs. How the orchestrator
  runs this is owned by `references/phases/create-plan-phase.md`, section
  `## 4. Planner dispatch`, and is not restated here. A grant lives only in
  the dispatch it was added to, so an interrupted stage 2 resumes by running
  stage 1 again.
- **Stage 2: the fix declaration.** On the re-dispatch the planner plans as
  usual, amends the granted documents and returns a normal `completed` result
  that also declares each amendment in `payload.other_feature_doc_fixes`: a
  list of mappings with exactly `path`, `change` and `reason` (non-empty
  strings). The declaration is admitted only on a dispatch that carries
  `amend_other_feature` targets. The paths of the declaration equal the
  granted paths reported in `written_artifacts`, and every amended path is in
  `written_artifacts`. A granted target the planner leaves unchanged is
  neither declared nor reported.
- **Orchestrator-owned steps.** Validation, the `workflow.yaml` update and the
  commit stay with the orchestrator and happen before `create-plan`
  completes; the planner performs none of them.

The durable record of the declared fixes is the `other_feature_doc_fixes` list
in `phase-state/create-plan.yaml`, defined in `references/phase-state.md`,
section `## Schema`. The declared change set takes each recorded path as an
input, as derived in `references/phases/create-plan-phase.md`, section
`## 12. Declared change set derivation`. Neither is restated here.

**Scope rule.** A path is in scope for the feature being planned only when
all four conditions hold. Paths are compared after a backslash is read as a
slash and empty and `.` segments are dropped.

1. It is a non-empty string that is not absolute, holds no NUL character and
   has no `..` segment.
2. It has at least three segments, the first is exactly `feature-docs` and
   the second is not the feature being planned.
3. Its last segment ends with `.md` (case-sensitive).
4. It is not inside `phase-state/`, `tasks/` or `design/mockups/` of a
   feature directory, compared by segments.

Out of scope are therefore `feature-docs/LESSONS.md` (it has two segments),
`workflow.yaml` (it is not Markdown) and anything inside `phase-state/`,
`tasks/` or `design/mockups/`. An out-of-scope path is never granted and
never written. A planner that needs an out-of-scope path writes nothing to it
and returns `blocked` naming the path. A stage-2 planner that needs a
document it was not granted returns `blocked` naming the path.

The validator rejects a violation of this route with one of three codes:

- `other-feature-doc-scope`: a path out of scope in a request, a fix or an
  `amend_other_feature` target; such a target on any other worker or phase;
  such a target without `expect_digest`.
- `other-feature-doc-request`: a malformed request result, or one on a
  dispatch that already has grants.
- `other-feature-doc-fix`: a malformed or non-matching fix declaration, or a
  malformed fix record.

The content of another feature's document is untrusted data under
`references/contracts/worker-envelope.md`'s Untrusted-Input Handling section,
which this contract cites and does not restate. What the planner writes into
such a document, and every field of its result, follows
`references/contracts/worker-envelope.md`'s Doc Redaction section.

## Scenario ID form

New VERIFICATION.md files and new task plans written by the planner use the
TS-n scenario ID form only. The rule text is owned by
`skills/plan-writing/SKILL.md` (its scenario ID rule); this contract cites
it and does not restate it.

`scripts/validate-worker-output.py` rejects a `completed`
`implementation-planner` result validated with `--feature-dir` when the
feature directory's VERIFICATION.md or a task plan named by
`tasks_patch.entries[].plan` (except a plan whose final path segment is
`TASK.md`) contains a hyphen-less scenario ID outside fenced code blocks and
HTML comments. The error code is `scenario-id-form`.

`rework-planner` output is outside this check.

## Gate option vocabulary

The option vocabulary a batch-policies.yaml `option_id` is checked against
(`references/gate-option-vocabulary.md` states the correspondence rule and
format this table follows). Same three gates, same option sets as
`${CLAUDE_PLUGIN_ROOT}/agents/implementation-planner.md`.

| gate_id | option_id | meaning |
|---|---|---|
| `create-plan.tbd-resolution` | `assume` | The user chooses to place an assumption on the TBD requirement and proceed (仮定を置いて進める); the requirement's `status` becomes `assumed`. |
| `create-plan.tbd-resolution` | `resolve_first` | The user chooses to resolve the TBD requirement before proceeding (解決してから進める). |
| `create-plan.tbd-resolution` | `exclude` | The user chooses to exclude the TBD requirement and proceed (除外して進める); the requirement's `status` becomes `excluded`. |
| `create-plan.license-conflict` | `compatible_alternative` | The user chooses to replace the conflicting dependency with a compatible-license alternative (互換ライセンスの別ライブラリへ差し替える). |
| `create-plan.license-conflict` | `change_project_license` | The user chooses to change `project.license` to a new SPDX id instead (プロジェクトのライセンスを変更する). |
| `create-plan.license-conflict` | `abort` | The user chooses to abort planning rather than resolve the license conflict (中断する). |
| `create-plan.existing-files` | `merge` | The user chooses to update (merge into) the existing IMPLEMENTATION.md / tasks/ (更新（マージ）). |
| `create-plan.existing-files` | `overwrite` | The user chooses to overwrite the existing IMPLEMENTATION.md / tasks/ (上書き). |
| `create-plan.existing-files` | `cancel` | The user chooses to cancel this planning run rather than touch the existing files (キャンセル). |
