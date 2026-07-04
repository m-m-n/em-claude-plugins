# workflow.yaml Schema (em-workflow SSOT)

`feature-docs/{feature}/workflow.yaml` is the single state file for one feature's
workflow run. It unifies what em-sdd split across `sdd.yaml` + `tasks.yaml`:
step state, task metadata, the review plan/summary, and the requirements
mapping. The path and name deliberately differ from em-sdd's
`doc/tasks/*/sdd.yaml` so that em-sdd's Stop hook never misfires while both
plugins coexist.

## Write ownership

**Only the orchestrator (the `/em-workflow:develop` main session) writes
workflow.yaml.** Implementer agents work inside worktrees and MUST NOT touch
it — a workflow.yaml edited inside a task branch becomes a guaranteed merge
conflict. This rule is restated in the `worktree-task-workflow` skill.

Exception: the upstream agents (requirements-spec-creator, implementation-
planner) create/extend the file when dispatched by the orchestrator — they run
in the main checkout, not in a worktree.

## Full structure

```yaml
schema_version: 1
feature: {feature-name}            # lowercase-with-hyphens
created: {YYYY-MM-DD}
base_branch: {branch}              # user's branch at /develop start; NEVER committed to
parent_branch: em-workflow/{feature}/integration
                                   # workflow-owned integration branch; task branches
                                   # fork from & merge into it (see implement-phase.md
                                   # Branch & Worktree Model)

project:
  components:
    main:                          # one entry per buildable component
      language: {language}
      build_command: "{cmd}"       # free-form shell — subject to the
      test_command: "{cmd}"        # command-execution approval gate
      format_command: "{cmd}"
      e2e_test_command: "{cmd or empty}"

workflow:                          # fixed step sequence; orchestrator advances it
  - id: create-spec
    artifacts: [REQUIREMENTS.md, SPEC.md]
    status: completed              # pending | in_progress | completed | failed | needs_update
    completed_at_commit: {sha}     # set on completion
  - id: create-plan
    artifacts: [IMPLEMENTATION.md, VERIFICATION.md, tasks/]
    status: pending
  - id: implement                  # wave-parallel implementation, merge included
    status: pending
    base_commit: {sha}             # HEAD when the integration branch was created;
                                   # the review phase diffs base_commit..parent_branch
  - id: review                     # dynamic review + bounded auto-fix
    status: pending
  - id: verify                     # integrated verification per VERIFICATION.md
    status: pending
    result: null                   # pass | fail — set by the verify phase
    failed_items: []               # failing scenario/criteria IDs + 1-line note
                                   #   (read back by retrospect as verification_failures)
  - id: retrospect                 # automatic collection (lightweight, no approval)
    status: pending

tasks:                             # written by implementation-planner; status by orchestrator
  task0001:
    title: {short title}
    plan: tasks/task0001.md        # relative to feature-docs/{feature}/
    files:                         # files the task is EXPECTED to touch
      - src/foo/bar.go             # (planner prediction; drives wave assignment)
    wave: 1                        # tasks whose files overlap MUST NOT share a wave
    skills: [backend-impl]         # from references/impl-skills.yaml; may be []
    domains: [data-persistence]    # ⊆ the 8-value vocabulary in review-rules.yaml
    complexity: medium             # low | medium | high (criteria: planner skill)
    requirements: [FR1]            # SPEC.md requirement IDs this task implements
    status: pending                # pending | in_progress | merged | failed
    notes: null                    # set on failure (reason; feeds re-planning)
    branch: em-workflow/{feature}/task0001   # set by orchestrator at dispatch

review:                            # phase-state SUMMARY only (details: reviews/roundN.yaml)
  status: pending                  # pending | in_progress | completed | failed
  rounds_completed: 0
  plan:                            # written when the review phase starts
    floor: [comprehensive, spec, security]     # Layer-1 mechanical result
    discretionary:                 # Layer-2 additions (add-only; reason mandatory)
      - perspective: performance
        reason: "統合 diff にホットループへの変更が含まれるため"
    codex_cross_validation: true   # per review-rules.yaml codex_cross_validation
  perspectives:                    # per-perspective completion in the latest round
    security: completed            # pending | completed | skipped | failed
  residual_critical_high: 0        # gate: workflow may not complete while > 0
  needs_rework: false              # true → send back to implement phase

requirements:                      # traceability SSOT (em-sdd pattern)
  FR1:
    title: {title from SPEC.md}
    status: ok                     # ok | tbd | assumed | excluded
    tbd_reason: null               # set when status: tbd
    excluded_reason: null          # set when status: excluded (planner's TBD
                                   #   resolution 「除外して進める」; e.g.
                                   #   "外部APIが廃止済みのため今回スコープ外")
    tasks: [task0001]              # filled by implementation-planner
    tests: [TS-1]                  # VERIFICATION.md scenario IDs
```

## Sibling artifacts

```
feature-docs/{feature}/
├── REQUIREMENTS.md      # 要件定義書 (Japanese)
├── SPEC.md              # spec SSOT (English)
├── IMPLEMENTATION.md    # CROSS-TASK design decisions ONLY (layering, shared
│                        #   components, naming conventions). Per-task detail
│                        #   lives in tasks/taskNNNN.md.
├── VERIFICATION.md      # feature-wide integrated verification items
├── workflow.yaml        # this file
├── tasks/
│   └── task0001.md      # per-task plan + Acceptance Criteria (mandatory)
├── reviews/
│   └── round1.yaml      # per-round review record (see review-phase.md)
└── retrospect.yaml      # raw lesson candidates (see retrospect flow)
```

## Status semantics

- The orchestrator decides the next step by scanning `workflow[]` for the
  first entry with `status != completed` — identical to em-sdd's loop.
- `tasks.*.status` transitions: `pending → in_progress` (orchestrator, at
  dispatch) `→ merged` (orchestrator, after the implementer reports its
  merge-task.sh success) or `→ failed`. A `failed` task resolves ONLY by
  retry or by routing back to planning (`create-plan: needs_update` →
  re-scope; implement-phase.md I.2.c). There is no skip state — the implement
  step completes only when every task is `merged`. Dropping a requirement is
  a planning/spec-layer change (SPEC.md update path), never an implement-phase
  shortcut.
- A task is DONE only when its branch is merged into `parent_branch`
  ("実装完了 = 親ブランチへのマージ完了").
- `review.residual_critical_high > 0` blocks the workflow from completing:
  the orchestrator must either loop the review phase, route back to
  implement (`needs_rework: true`), or get an explicit user decision.
