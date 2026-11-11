# Rework Task Synthesis Contract (em-workflow)

Referenced by all four rework routes: `references/review-phase.md`'s
interactive and batch rework branches, and `skills/develop/SKILL.md`'s
interactive and batch verify rework branches. Those four call sites point
here instead of restating anything below (NFR6).

## 1. Purpose

When review findings or verify failed items require code changes beyond
what a completed `implement` phase already covers, additional tasks are
synthesized and routed back through `implement`. This document's subject is
the CONTRACT the synthesis result must satisfy — not who writes the prose
that produces it. The executing worker today is `agents/rework-planner.md`,
but the contract survives a change of executing worker (Section 13).

## 2. Applicable modes

Four routes share this contract:

- Interactive review rework
- Batch review rework
- Interactive verify rework
- Batch verify rework

Task synthesis rules (Sections 4-9, 11) are IDENTICAL across all four routes.
What differs between interactive and batch is only how a rework round gets
selected (a user's choice vs. an auto-rework cap) and the retry/round limit —
never the shape of what gets synthesized (Section 11, Invariant 7).

## 3. Inputs

The synthesizing worker receives:

```yaml
rework_source:
  type: review                   # review | verify
  review_round: 2
  findings:                      # populated when type == review
    - stable_id: abc123
      severity: high
      category: security
      file: src/auth.go
      title: "…"
      description: "…"
      suggestion: "…"
  failed_items: []                # populated when type == verify
existing_tasks: {}                # workflow.yaml tasks snapshot
next_task_id: task0007
verification_index:               # VERIFICATION.md scenario IDs -> requirement IDs
  TS-1: [FR1]
  TS-2: [NFR1]
implementation_path: /absolute/.../IMPLEMENTATION.md
spec_path: /absolute/.../SPEC.md
verification_path: /absolute/.../VERIFICATION.md
```

The full input/output envelope (including the common worker envelope fields)
is owned by `references/contracts/rework-planner-contract.md` (see
Section 13); this section states only the rework-specific payload shape. The
worker also receives the orchestrator-resolved `plugin_versioning` value,
resolved at each dispatch (Section 10); its place in the input is stated in
that contract, which cites the field's definition.

## 4. Grouping rules

Findings and failed items are NOT mapped one-file-to-one-task. Findings (or
failed items) that share a root cause, a contract, or an Acceptance
Criterion are grouped into ONE task. Beyond grouping, ordinary task
decomposition applies unchanged — `skills/plan-writing/SKILL.md`'s Task
decomposition rules (worktree independence, size, `files` as a contract,
interface contracts over sequencing, objective Acceptance Criteria) govern
rework tasks exactly as they govern first-pass planning; this document does
not restate them.

## 5. Task ID allocation

New task IDs are allocated sequentially starting from the `next_task_id`
supplied in the input. No gaps, no reuse of any ID already present in
`existing_tasks`.

## 6. Task plan requirements

Every rework task gets a `tasks/taskNNNN.md` built from
`references/templates/task-plan.md`, exactly like a first-pass task plan.
Its Acceptance Criteria must be objective and test-translatable — the
implementer's TDD contract is unchanged by the task's rework origin. The
task plan records its origin as `provenance` (Section 11, Invariant 6).

Every synthesized task also follows the "Plugin Version Handling" section of
`em-workflow/skills/plan-writing/SKILL.md`, including its `files` rule; a
task's rework origin makes no difference to how that section applies, and
this document restates none of its rule text.

## 7. Metadata derivation

`files` / `skills` / `domains` / `requirements` are derived from the
MEANING of the finding or failed item — what it is actually about — never
from inheriting the file set of whichever existing task happens to overlap
on file path alone (Section 11, Invariant 4). `domains` values are drawn
ONLY from the vocabulary in `references/review-rules.yaml` (the SSOT
`references/workflow-schema.md` and `agents/implementation-planner.md`
already point to); this document does not restate that vocabulary. The
`files` rule of the section cited in Section 6 applies on top of the
meaning-derived `files`.

**Feature-docs files rule**: a rework-synthesized task's `files` contain no
path whose first path segment is exactly `feature-docs`. The segments are
taken with `\` treated as `/` and with empty and `.` segments dropped (the
normalization the validator already applies to allowed-root containment).
The rule applies to the entries of an `append_rework` patch only. Planning
documents under that directory change through the Docs-only correction
route (Section 9), never through an implementer task.

## 8. Verification coverage rules

Every rework task MUST declare its verification coverage in
`payload.rework_index`:

```yaml
rework_index:
  task0007:
    covered_by_existing: [TS-3]   # existing VERIFICATION.md scenario IDs, when they suffice
    new_scenarios: []             # newly added scenario IDs, when they don't
    rationale: "TS-3 already exercises the authorization boundary; no new case is needed"
```

A rework task whose `covered_by_existing` AND `new_scenarios` are BOTH empty
is FORBIDDEN — every rework task must be covered by an existing scenario, a
new one, or both.

### 8a. The most-reducing tier: no verification document exists

At the most-reducing tier (`minimal`), `VERIFICATION.md` is one of the
artifacts that tier's reduction table subtracts (`skills/develop/SKILL.md`'s
reduction table, cited not restated) — it is never produced, so
`verification_index` (Section 3) is empty and no scenario ID has ever been
indexed.

Two routes into rework exist in general: an UPGRADE, which recreates the
missing documents before any rework planning happens, and a DIRECT rework
without an upgrade. At this tier, the upgrade route is the one that can
succeed: FR12/FR19's upgrade procedure (`skills/develop/SKILL.md`, cited not
restated) is what recreates the missing planning documents, and only after
that has happened does a baseline `VERIFICATION.md` exist for this
synthesis to extend and for the validator to diff against. The direct route
— synthesizing a rework task at this tier without first upgrading — cannot
produce a valid task: with `verification_index` empty, `covered_by_existing`
can never cite a real scenario, so every rework task would have to declare
`new_scenarios` to satisfy the both-empty prohibition above, and a
`new_scenarios` claim with no `VERIFICATION.md` to diff against is exactly
the case Section 12's validation rule rejects — fail-closed, the same way an
unverifiable claim is already rejected when a baseline is missing for any
other reason. This document does not restate the upgrade procedure's
mechanics; it states only the consequence for this synthesis: **coverage
declaration at this tier requires the upgrade to have already happened.**
This holds regardless of which condition sent the round into rework —
including residual high-severity (not only critical) findings, and a
failed verify — since none of those conditions changes what
`verification_index` contains. Any rework entry point that dispatches
this synthesis at a reduced tier MUST have completed the upgrade route
first; the trigger that caused rework does not substitute for it.

## 9. Related document updates

| Document | Update condition |
|---|---|
| `tasks/taskNNNN.md` | Always created, one per synthesized task |
| Existing `tasks/*.md` | Changed only through the docs-only correction route below |
| `VERIFICATION.md` | Per Section 8's coverage rules, or the docs-only correction route below |
| `IMPLEMENTATION.md` | Only when the rework task introduces a NEW shared contract (interface, data format) with an existing task, or through the docs-only correction route below; the synthesizing worker always emits `payload.shared_contract_rationale` (summary of what was added, or why nothing needed adding) regardless of which branch it took, so the decision has a human-readable trail |
| `SPEC.md` / `REQUIREMENTS.md` | Never updated by this synthesis; a rework that needs a SPEC change takes the transition in Section 10 instead |

### Wording-correction route

Before a needed change to `IMPLEMENTATION.md` or `VERIFICATION.md` is routed
to rework-task synthesis above or to the SPEC-change transition (Section
10), route selection checks first whether it qualifies for this
independent route.

**Applies to**: a change confined to the wording of the two create-plan-owned
documents — `IMPLEMENTATION.md` and `VERIFICATION.md`.

**Eligibility (all three, conjunctive — every condition below must hold)**:

1. No planner re-entry is needed.
2. No plan or task metadata changes: the task set, `files`, `skills`,
   `domains`, `complexity`, or plan paths.
3. No requirement metadata changes: requirement statements, IDs, `status`,
   or the task/test mapping.

**Outcome when eligible**: the correction is applied through this section's
document-update channel with no task synthesized, `create-plan` is NOT set
to `needs_update`, and no workflow patch touching planning is produced.

**Guard**: failing any ONE of the three conditions above makes this route
inapplicable, and the change instead goes to the Docs-only correction route
below; a change that route does not accept goes through rework-task synthesis
or the SPEC-change transition (Section 10). Each condition names the concrete
artefact whose change disqualifies the route, so a change that turns out to
have touched, for example, requirement metadata is recognizable after the
fact rather than only by the intent behind it.

**Ordering**: this route is checked first; only a change that fails it can
reach the Docs-only correction route below, and only a change that fails that
route as well can reach rework-task synthesis or the SPEC-change transition
and, through the transition, the classification gate
(`references/question-resolution.md`).

### Docs-only correction route

A needed change that fails the Wording-correction route above is checked next
against this route, before it is routed to rework-task synthesis or to the
SPEC-change transition (Section 10).

**Scope**: a needed change that fails the Wording-correction route's
eligibility and is resolved by changing only `VERIFICATION.md`,
`IMPLEMENTATION.md` and existing `tasks/*.md` under `feature-docs/{feature}/`,
and the requirement test references (the `tests` of a requirement) in
`workflow.yaml`. A change that needs `SPEC.md` or `REQUIREMENTS.md` stays with
the SPEC-change transition (Section 10); this route never changes either.

**Decision order**: Wording-correction route -> Docs-only correction route ->
rework-task synthesis / SPEC-change transition. A change takes the first route
in this order whose conditions it meets.

**Result of a docs-only round**: no task is synthesized. The rework-planner
corrects the documents itself, as
`references/contracts/rework-planner-contract.md` states (cited, not
restated). Requirement test references change through the tests replacement
of `references/workflow-patch.md` (cited, not restated). The patch returns
only the origin step to `pending`: `verify` for verify-sourced rework,
`review` for review-sourced rework. This route does not return `implement` to
`pending`. Invariant 1 (Section 11) governs a transition that returns
`implement` to `pending` and is therefore not engaged by this route.

**Mixed round**: a round that holds both code corrections and docs-only
corrections. Docs-only items are corrected directly by the rework-planner;
code items become tasks under the grouping rules of Section 4. A round with at
least one task returns `implement` and the origin step to `pending`, as before.
The origin-step-only result above is limited to docs-only rounds, which
register no task.

**Declaration**: every correction made through this route, in a docs-only
round or in a mixed round, is declared in `payload.doc_corrections`, which
`references/contracts/rework-planner-contract.md` defines (cited, not
restated).

**Consistency with the specification**: every change this route makes keeps
the changed document consistent with `SPEC.md` and `REQUIREMENTS.md`, which
this route never changes. A correction that would make a scenario or
acceptance criterion check less than `SPEC.md` or `REQUIREMENTS.md` require
is not a docs-only correction; it continues to rework-task synthesis or the
SPEC-change transition (Section 10).

## 10. Workflow state transition

**Review-sourced rework** proceeds in this fixed order:

1. The orchestrator writes `review.needs_rework = true` and
   `review.status = pending` directly to workflow.yaml (orchestrator
   responsibility — this write is NEVER carried inside a worker patch).
2. The orchestrator dispatches rework-planner.
3. The orchestrator validates and applies rework-planner's patch
   (`tasks_patch` + `step_patches` + `preserve`; `references/workflow-patch.md`).
   The validation passes `--target-repo` (the integration worktree) and
   `--base-commit` (the full commit ID of the tip of the integration branch,
   resolved just before validating): the same two values as the canonical
   invocation of `references/phases/create-plan-phase.md` section 9.
4. `implement` returning to `pending` happens INSIDE that patch's
   `step_patches` in step 3 — it is never a separate write, and it never
   precedes step 3 registering at least one pending rework task
   (Section 11, Invariant 1).

**Verify-sourced rework** skips step 1 entirely and starts at step 2:
`review.needs_rework` is a review-specific field, so verify-sourced rework
never sets it (Section 11, Invariant 11).

**Dispatch input (step 2, all four routes)**: at every rework-planner
dispatch the orchestrator resolves `plugin_versioning` per the
`### plugin_versioning (dispatch-resolved value)` subsection of
`em-workflow/references/contracts/planner-contract.md`, from the integration
worktree's current state, passes it in rework-planner's input, includes it
in the `value_inputs` of `input_digest`, and, when it recomputes
`input_digest` on the worker's return, re-resolves it the same way. The
field's place in the input and its mandatory and untrusted status are stated
in `references/contracts/rework-planner-contract.md`; this document restates
neither the field's definition nor its resolution rules. Each of these
dispatches also carries the digest steps of `references/artifact-digest.md`:
`Pre-dispatch verification` of the `write_policy.targets` immediately before
the dispatch, and `Layer 5 recording` of `written_artifacts` into
`phase-state/rework.yaml` once layer 4 passes. Rework's action choice is
unchanged.

**Return-time digest (steps 2 and 3, all four routes)**: the rework-planner
run's entry in `phase-state/rework.yaml` carries `dispatch_digest_inputs`, the
per-path `digest_inputs` map of the dispatch's digest_source
(`references/phase-state.md` defines the field and when it is written). After
the scope verification (layer 4) of rework-planner's result passes, the
orchestrator recomputes the current digest_source and runs
`scripts/self-write-digest.py` (operation `identify_and_substitute`), as
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states. Step 3 validates the patch against the
digest_source the script returned, by application rules 1-14 of
`references/workflow-patch.md`: rule 1 compares that substituted digest_source
with the dispatch-time `input_digest`, and a mismatch, or a script exit other
than `0`, makes the result stale. The orchestrator then runs the return-time
recheck before step 3's application and before the recording phase-state write,
as `references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states; a recheck mismatch, or a recheck that cannot run,
makes the result stale. The patch is applied only after a passing recheck:
step 3's application, which is rule 15's single Write to workflow.yaml and
rule 16's R2 commit sequence, follows it, so a stale result (from rule 1's
comparison, the script exit or the recheck) reaches no workflow.yaml write and
no commit made by the patch. The orchestrator records `self_write_set` in the
same phase-state write as the `Layer 5 recording` of `written_artifacts` into
`phase-state/rework.yaml`.

**When rework needs a SPEC.md change**: the synthesizing worker creates no
task. Instead it returns `status: needs_user_input` with
`gate_id: rework.spec-change`. Once the user (interactive) selects the SPEC
change, the orchestrator's transition is fixed:

1. `create-spec` step → `needs_update`
2. `create-plan` / `implement` / `review` / `verify` steps → `pending`
   (only these steps' `status` is written; `verify`'s `result` and
   `failed_items` stay until the next verify run overwrites them)
3. `workflow[implement].base_commit` is preserved unchanged
4. phase-state `rework.yaml` records `reason`, `origin_kind`, `origin_id`,
   `recorded_at_commit`, and `replan_authorized: true` (field definitions
   owned by `references/phase-state.md`; this document does not restate
   them)
5. The develop state machine re-enters at `create-spec`

Step 2's `create-plan` re-entry is not rejected merely because merged tasks
already exist in `workflow.yaml` at that point. The permission conditions
that decide when a re-entry is admitted are owned by
`references/workflow-patch.md`; this document does not restate them.

In batch mode, `rework.spec-change` is resolved through the classification
gate defined in `references/question-resolution.md`, which this document
does not restate. Interactive mode is unchanged: the user is asked
directly.

**Other question conditions** — the synthesizing worker returns a question
packet instead of tasks only when: the same finding still has mutually
exclusive fix approaches; a requirement exclusion or license change is
required; or the finding alone cannot make its Acceptance Criteria
objective.

## 11. Invariants

1. For a rework-derived transition (Section 10), before `implement`
   returns to `pending`, at least one new rework task is registered in
   workflow.yaml. The develop skill's own batch infra auto-resume
   (`skills/develop/SKILL.md`, the auto-resume block) also returns
   `implement` to `pending`, but is not a rework-derived transition and
   registers no task; this invariant does not govern it — its precondition
   is `references/implement-phase.md`'s Step I.0 (cited, not restated
   here).
2. Every newly synthesized task's `status` is `pending`.
3. Every rework task plan states objective, test-translatable Acceptance
   Criteria.
4. `files` / `skills` / `domains` / `requirements` are derived from the
   finding's or failed item's meaning; file-overlap inheritance from an
   existing task alone is not sufficient.
5. `workflow[implement].base_commit` is never changed by a rework patch; it
   is always listed in the patch's `preserve` set.
6. Review-sourced tasks carry the finding's `stable_id`, verify-sourced
   tasks carry the failed item's ID, as `provenance`. Named as a pair, this
   is `origin_kind` (`review` | `verify`) and `origin_id`: for
   `origin_kind: review`, `origin_id` is the finding's `stable_id`; for
   `origin_kind: verify`, `origin_id` is the failed item's ID. This
   document is the pair's one definition; every consumer of a
   rework-derived question's origin — `references/question-resolution.md`
   for what origin verification matches against and what set the
   security / license / irreversible check runs over,
   `references/phase-state.md` for what the `spec_change` record stores —
   cites this pair rather than defining its own.
7. Interactive and batch never differ in task synthesis rules; they differ
   only in how a rework round is selected and in the retry/round cap.
8. Patch application and every workflow.yaml write are always performed by
   the orchestrator, never by the synthesizing worker itself.
9. When rework requires a SPEC.md change, no task is created — the
   SPEC-change transition (Section 10) applies instead.
10. Every rework task declares its verification coverage via `rework_index`
    (Section 8).
11. Verify-sourced rework never sets `review.needs_rework` — that field is
    review-specific, and the verify-sourced transition begins directly at
    dispatch (Section 10).

## 12. Validation

Machine-checkable rules a validator applies against the synthesis output:

- Every synthesized task appears as a key in `rework_index`.
- Every ID listed in a task's `covered_by_existing` exists in the input's
  `verification_index`.
- Rename-aware coverage: the previous bullet is refined as follows for
  `covered_by_existing` IDs, and every rejection below carries the code
  `rework-index`. A declared pair is a `scenario_renames` mapping under
  `payload.doc_corrections` whose `from` and `to` are both non-empty strings.
  The document diff is available when `--feature-dir` and `--baseline-dir`
  are both given and the feature directory holds `VERIFICATION.md`. The
  post-change set is the scenario IDs that the feature directory's
  `VERIFICATION.md` defines; the baseline set is the scenario IDs that the
  baseline directory's `VERIFICATION.md` defines, empty when that file is
  absent. When a set is needed and the `VERIFICATION.md` it comes from
  exists but cannot be read as text, the check reports one `rework-index`
  error that names the file, and no ID is accepted on the strength of that
  set. Each `covered_by_existing` ID is judged by the first of these rules
  that matches:
  - The ID is the `from` of any declared pair: rejected, with or without the
    diff, even when the ID is a key of `verification_index`. A declared
    pair's `from` is never accepted as `covered_by_existing`.
  - The ID is a key of `verification_index`: with the diff available it is
    accepted only when it is in the post-change set, whether or not the ID
    has anything to do with a rename; without the diff it is accepted as
    before, so a key unrelated to any rename is not affected.
  - The ID is the `to` of one or more declared pairs: with the diff
    available it is accepted only when EVERY declared pair with that `to`
    meets all four conditions: the pair's `from` is a key of
    `verification_index`, its `to` is in the post-change set, its `from` is
    in the baseline set, and its `from` is not in the post-change set.
    Without the diff a rename is never accepted (fail-closed); the
    rejection message names what is missing (`--feature-dir`,
    `--baseline-dir`, or the feature directory's `VERIFICATION.md`) and is
    worded differently from the message for an ID that no declared pair
    renames.
  - Any other ID: rejected, with the message for an ID that no declared pair
    renames.
  - With the diff available, every accepted `covered_by_existing` ID is
    therefore in the post-change set.
- Every ID listed in a task's `new_scenarios` exists in the VERIFICATION.md
  diff the synthesis produced.
- When `new_scenarios` is non-empty, the same IDs also appear in the
  `requirements_patch`'s `tests_append`.
- No task has BOTH `covered_by_existing` and `new_scenarios` empty
  (Section 8).
- A `new_scenarios` claim made while no `VERIFICATION.md` exists in the
  current feature directory is rejected outright, fail-closed, distinctly
  from a claim rejected merely because no baseline directory was supplied
  (Section 8a).
- No synthesized task's `files` (an `append_rework` entry) contains a path
  whose first path segment is exactly `feature-docs`, with `\` treated as `/`
  and with empty and `.` segments dropped (Section 7).
- No synthesized task's `files` (an `append_rework` entry) holds a new
  report-artifact name: a name that `skills/plan-writing/SKILL.md`'s
  `## Report Artifact Names` matches and that is not a regular file at the base
  commit. Each is reported with the error code `report-name-new-file`, and the
  check needs the two values that Section 10 step 3 passes.
- An `append_rework` patch whose `tasks_patch.entries` is absent or empty
  never returns `implement` to `pending`: its `step_patches` hold exactly
  one entry, for the origin step only, with `set.status` equal to
  `pending`, and none targets `implement` (Section 9, Docs-only correction
  route).
  - Origin step: the `type` of `rework_source` in the input envelope
    (`review` or `verify`) when the validator holds that envelope and
    `rework_source` is a mapping with a `type`. With no envelope (for
    example `--kind workflow-patch` alone), with no `rework_source`, or
    with a `rework_source` mapping that has no `type` key, the origin step
    is either `verify` or `review`. A `rework_source` that is not a
    mapping, or a `type` that is present but is not exactly the string
    `review` or `verify` (null, a non-string, or any other string), leaves
    no origin step that can match: the patch is rejected (fail-closed).
  - An entry whose `step_id` is `implement` is rejected whatever its
    `set.status` is.
  - The check is structural: it applies with and without `--dry-run-apply`,
    and on both routes that validate the patch, the result's
    `workflow_patch` under `--kind worker-result` and the patch under
    `--kind workflow-patch`.
  - Codes: every entry whose `step_id` is `implement` reports
    `docs-only-implement-reset`. Any other violation, that is
    `step_patches` not being a list of exactly one mapping, an entry for a
    step other than the origin step, or a `set.status` that is not the
    string `pending`, reports `docs-only-step-patches` once per patch, with
    a message that names the violated condition. An `implement` entry
    therefore reports both codes.

## 13. Execution adapter

The worker that performs this synthesis today is `agents/rework-planner.md`;
its input/output envelope (including the common worker envelope fields) is
`references/contracts/rework-planner-contract.md`. This document states the
contract the RESULT must satisfy; the adapter document states how the
current worker is invoked to produce it. A future change of executing
worker updates only the adapter, never this contract.
