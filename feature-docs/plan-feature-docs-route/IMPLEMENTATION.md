# Implementation Plan: plan-feature-docs-route

## Overview

Keep `feature-docs/**` out of implementer task `files` (a plan-writing rule
plus a validator check on `replace_planning` entries), give the
implementation-planner a two-stage, explicitly granted route to amend other
features' documents inside create-plan, and extend develop's Step A.6 failed
entry with a feature-docs correction that removes such paths from a failed
feature's plan so a re-run proceeds.

## Technology Stack

- **Python 3** - the validator, the new entry script and the self-write digest
  script. They keep using what they use today (the standard library and the
  PyYAML the validator already loads); nothing new is introduced.
- **unittest** (standard library) - every test (NFR3). Suite command:
  `python3 -m unittest discover -s tests`.
- **Markdown** - contracts, phase documents, skill and agent prompts.
- No new dependency (`project.license: none`; nothing to record).

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Rule owners (SSOT, NFR4) | `em-workflow/skills/plan-writing/SKILL.md` (`## Feature-docs Files`), `em-workflow/references/contracts/planner-contract.md` (`## Other-feature documents`, `### feature_docs_correction (dispatch-resolved value)`), `em-workflow/references/contracts/spec-writer-contract.md` (the write_policy action table), `em-workflow/references/workflow-patch.md` (`## Feature-docs correction`) | Hold the rule text once |
| Orchestrator procedure | `em-workflow/skills/develop/SKILL.md` (Step A.6), `em-workflow/references/phases/create-plan-phase.md` (sections 4, 7, 8, 9, 12, 13), `em-workflow/references/phase-state.md` | When and how the orchestrator grants, records, dispatches and restores |
| Worker prompt | `em-workflow/agents/implementation-planner.md` | What the planner does; cites the owners |
| Mechanical checks | `em-workflow/scripts/validate-worker-output.py`, `em-workflow/scripts/feature-docs-entry.py` (new), `em-workflow/scripts/self-write-digest.py` | Enforce the owners' rules |

Dependency direction: procedure and prompt cite owners by path plus heading;
scripts implement owners; an owner never restates another owner. The
implementer's rule (`em-workflow/agents/implementer.md`,
`em-workflow/skills/worktree-task-workflow/SKILL.md`, "Never modify
`feature-docs/**`") is not changed by any task (FR10).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Feature-docs path predicate | Decide whether a path is a feature-docs path (FR1, FR2, FR8) | Input: any value. True only for a string whose first segment, after the validator's existing `path_segments` normalization (`\` read as `/`, empty and `.` segments dropped), is exactly `feature-docs`. A non-string is false. Never raises. Expressed with the existing `path_segments` (unchanged, not renamed) the same way the append check already does; no task introduces a new shared helper for it | task0001 (rule text), task0004, task0006, task0007 (rule text) |
| Other-feature document scope rule | Decide whether a path may be granted and amended (FR5) | See D4 below. Text owned by planner-contract.md `## Other-feature documents`; implemented once in the validator; applied by the orchestrator at grant time | task0002 (owner), task0005 (validator), task0009 (grant), task0001 (planner behaviour) |
| write_policy action `amend_other_feature` | Per-path permission to modify one existing other-feature document (FR4) | See D2 below. Row owned by spec-writer-contract.md | task0003 (owner, self-write), task0005 (validator admission), task0002, task0009 |
| Planner request result | Stage-1 declaration of documents to amend (FR4) | See D3 below | task0001, task0002, task0005, task0009 |
| Fix declaration | Stage-2 declaration of each amendment made (FR3, FR7) | See D3 below | task0001, task0002, task0005, task0009 |
| Phase-state record `other_feature_doc_fixes` | Durable record of declared fixes (FR7) | See D5 below. Defined in phase-state.md | task0009 (owner), task0005 (shape check) |
| `scripts/feature-docs-entry.py` | Step A.6 judgment for the feature-docs correction (FR8) | See D6 below | task0006 (implements), task0008 (cites) |
| Patch field `tasks_patch.feature_docs_removals` | Remove feature-docs paths from carried task records on the correction entry (FR8, FR9) | See D7 below. Owned by workflow-patch.md `## Feature-docs correction` | task0007 (owner), task0006 (validator), task0001 (planner produces), task0008 (orchestrator applies) |
| Planning input `planning_inputs.feature_docs_correction` | Tell the planner which (task, path) pairs to correct | See D8 below. Owned by planner-contract.md | task0002 (owner), task0001, task0008 |
| Step A.6 order and restoration split | Combine the feature-docs and final-path judgments in one evaluation (FR8, FR9, A4) | See D9 below. Owned by develop SKILL.md | task0008 (owner), task0010 (revises the split); task0006 provides `final_path_remaining` and shares the failed-task selection |

## Conventions

- **Names are fixed here.** Every task uses exactly the identifiers in this
  document: error codes, the action, payload keys, the phase-state key, the
  patch field, the planning input, the script name and the headings.
- **Rule text lives in one owner (NFR4).** Other documents cite the owner by
  path plus heading and add only their own procedure.
- **Errors, never exceptions (NFR2).** Each new validator check reports a
  malformed value as an error of its own code (or of the existing structural
  code for that field) and skips the rest of its check for that value; it
  never raises. The entry script follows `scripts/report-name-entry.py`:
  exit 0 for every judgment outcome, exit 2 with a one-line stderr message
  (no traceback) for an execution error.
- **New tests go into new test modules** under `tests/`. Do not edit
  `tests/test_validate_worker_output.py` (its bytes are pinned by
  `tests/test_gate_option_vocabulary.py`).
- **Byte pins.** `tests/test_gate_option_vocabulary.py` pins the SHA-256 of
  `em-workflow/references/workflow-patch.md` and
  `em-workflow/scripts/validate-worker-output.py`. A task that changes one of
  them refreshes that pin and adds a "Refreshed again by
  plan-feature-docs-route/taskNNNN" comment that names what changed (refresh,
  don't remove). Several tasks refresh the same pin; on the merge conflict
  this produces, the parent-side adoption protocol recomputes the digest for
  the merged file and re-runs the suite.
- **Pinned wording is kept.** Existing document tests pin phrases, heading
  lists and byte digests of sections (see each task's Design). A task never
  deletes or weakens an existing assertion; where a pin must move because the
  task intentionally changes the pinned text, the pin is refreshed in the same
  task and the refresh is named in a comment.
- **Heading constraints.**
  - `em-workflow/agents/implementation-planner.md`: its `### ` headings stay
    exactly the nine step headings, and its `## Gate option vocabulary`
    section stays byte-identical and last. New planner text uses paragraphs
    and one new H2 section with no subheading.
  - `em-workflow/references/workflow-patch.md`: `## Final-path correction`
    stays directly before `## Ownership boundary`; the new
    `## Feature-docs correction` goes between
    `## Interrupted authorization-spend recovery` and
    `## Final-path correction`. The numbered application rules stay eighteen.
  - `em-workflow/references/phases/create-plan-phase.md`: section 13 stays
    the last H2. The feature-docs correction dispatch is the H3
    `### Feature-docs correction dispatch` inside section 13, placed after
    section 13's existing paragraphs, and it uses no bold paragraph label
    that section 13 already uses.
- **Forbidden words in create-plan-phase.md.** From the section 12 heading to
  the end of the document, text never contains `exclud`, `subtract`,
  `ignor`, `除外`, `SUPERSET`, `CONTAINED IN`, `Initial-planning path` or
  `protocol error on BOTH paths` (pinned by existing tests). Write "out of
  scope", "removes" or "not granted" instead.
- **Backtick token rule.** In planner-contract.md, create-plan-phase.md and
  spec-writer-contract.md, never write a backtick span shaped like a gate id
  (a dotted word pair, such as a bare YAML file name of a phase); write
  `phase-state/create-plan.yaml` with its directory.
- **Digest sentences.** Every new sentence about a digest names the
  orchestrator as the actor or is a negation (checked by
  `em-workflow/scripts/check-plugin-invariants.py`).
  `em-workflow/references/contracts/worker-envelope.md` never contains the
  string `expect_digest`.
- **Untrusted input and redaction (NFR5).** Documents cite the worker
  envelope's Untrusted-Input Handling and Doc Redaction sections; they do not
  restate them. No written document contains a home-directory absolute path
  or a Notion URL; paths are repository-relative.
- **No gate, no question (NFR1).** Nothing in this feature adds a `gate_id`,
  a question-packet category or a user question; every new decision is
  mechanical.

## Cross-task Design Decisions

### D1. FR2 error code `plan-task-feature-docs`

The validator rejects each feature-docs path in the `files` of a
`tasks_patch.entries` item of a `replace_planning` patch with code
`plan-task-feature-docs`: one error per offending path, the message holding
the task id and the path as given. `carried_task_ids` are not checked (their
records are copied verbatim). The append check and its code
`rework-task-feature-docs` are unchanged, and an append entry never gets the
new code. The minimal-tier `plan` value (`TASK.md`) is outside the rule
because only `files` is checked. Affects task0001, task0004, task0009.

### D2. New write_policy action `amend_other_feature`

A seventh action, owned by spec-writer-contract.md's action table. The
table's heading becomes count-free, "The `write_policy` actions". Every
citation of the old heading and every "six actions" mention in the plugin is
updated to count-free wording.

| Property | Value |
|---|---|
| `expect_digest` | Required: the digest the orchestrator recorded for the path at dispatch |
| Worker behaviour | May modify the content of the existing file; must not create, delete or change the file kind |
| Valid on | implementation-planner dispatches of create-plan only (the feature-docs correction dispatch included) |
| Scope | planner-contract.md `## Other-feature documents` (cited) |
| Self-write membership | `created`: not a member; `modified`: member; `deleted`: not a member |
| Not reused | `replace_own`, `replace_authorized`, and the artifact-overwrite batch policy are never used for these documents |

Affects task0002, task0003, task0005, task0009.

### D3. Two-stage dispatch

| Stage | Who | What |
|---|---|---|
| 1 | Planner | When the plan needs another feature's document changed and the dispatch carries no `amend_other_feature` target, the planner writes nothing and returns the request result |
| Grant | Orchestrator | Validates the request result; for each requested path, confirms the scope rule and that the file exists as a regular file; adds one `amend_other_feature` target per path with the current digest; re-dispatches under a new `request_id` with the same planning inputs |
| 2 | Planner | Plans as usual, amends the granted documents, and returns a normal `completed` result that also declares each amendment |

The request result is `status: completed` with `written_artifacts` empty,
`workflow_patch` null, and a payload holding only
`other_feature_doc_requests`. That is a non-empty list of mappings with
exactly `path` and `reason` (non-empty strings, paths unique). It is
admitted only on a dispatch with no `amend_other_feature` target. A question
packet takes precedence over stage 1 as usual.

The fix declaration is `payload.other_feature_doc_fixes`, a list of mappings
with exactly `path`, `change` and `reason` (non-empty strings). It is
admitted only when the dispatch carries `amend_other_feature` targets. The
set of its paths equals the set of `amend_other_feature` target paths listed
in `written_artifacts`, and every amended path is in `written_artifacts`.
A granted target the planner leaves unchanged is neither declared nor
reported.

Validator codes:

| Code | Rejects |
|---|---|
| `other-feature-doc-scope` | A path out of scope in a request, a fix or an `amend_other_feature` target; such a target on any other worker or phase; such a target without `expect_digest` |
| `other-feature-doc-request` | A malformed request result, or one on a dispatch that already has grants |
| `other-feature-doc-fix` | A malformed or non-matching fix declaration, or a malformed fix record |

Grants are not persisted outside the dispatch they belong to; an
interrupted stage 2 resumes by re-running stage 1. A stage-2 planner that
finds it needs a document it was not granted returns `blocked` naming the
path. A planner that needs a path out of scope writes nothing to it and
returns `blocked` naming the path (A2). Affects task0001, task0002,
task0005, task0009.

### D4. Scope rule (FR5)

A path is in scope for feature F when all of these hold:

1. It is a string that passes the validator's safe-relative check
   (non-empty, not absolute, no NUL, no `..` segment with `\` read as `/`).
2. Its normalized segments number at least three, the first is exactly
   `feature-docs` and the second is not F.
3. Its last segment ends with `.md` (case-sensitive).
4. It is not inside `feature-docs/{x}/phase-state/`,
   `feature-docs/{x}/tasks/` or `feature-docs/{x}/design/mockups/`, compared
   by segments.

So `feature-docs/LESSONS.md` (two segments) and
`feature-docs/{x}/workflow.yaml` (not Markdown) are out of scope. Existence
as a regular file is checked by the orchestrator at grant time; the
validator does not read the file system for this rule.

### D5. Fix record (FR7)

`phase-state/create-plan.yaml` gains a top-level, append-only list
`other_feature_doc_fixes`. Each entry has `path`, `change`, `reason` and
`produced_by` (the run's `request_id`). The orchestrator appends one entry
per declared fix in the run's recording phase-state write (the write that
records layer 5 and `self_write_set`). The list is never rewritten or
cleared, a phase restart (`generation` increment) included. Section 12 of
create-plan-phase.md adds every entry's `path` as a fourth input of the
declared change set. The validator checks the list's shape when present
(`other-feature-doc-fix`); its absence is valid. Affects task0005, task0009.

### D6. Entry script `em-workflow/scripts/feature-docs-entry.py`

The arguments are the four of `scripts/report-name-entry.py`: `--workflow`,
`--journal`, `--target-repo` and `--base-commit`. The script loads the
validator and `scripts/report-name-entry.py` as siblings, so the failed-task
and unmerged-task selection, the journal replay and the report-name
violation finder each keep one implementation. It prints one JSON object
with exactly these keys:

| Key | Value |
|---|---|
| `entry` | `none`, `dispatch` or `blocked` |
| `targets` | List of mappings with `task_id`, `path` and `failed_journal_line` (the task's last `failed` journal line, or null) |
| `errors` | List; the failed conditions on `blocked` |
| `final_path_remaining` | Boolean |

The judgment:

1. `implement` not `failed`: `none`.
2. No failed task (the report-name-entry definition: status `failed`, or
   last journal event `failed` on a task not `merged`) holds a feature-docs
   path in its `files`: `none`.
3. Otherwise `targets` is every distinct (task, path) pair, over every task
   whose status is not `merged`, in workflow task order and then file order,
   whose path is a feature-docs path. No base-commit check applies to a
   target.
4. `blocked`, with one error per failure naming the task:
   - a task is in flight (status `in_progress` or last journal event
     `launched`);
   - a target task's last journal event is `merged`;
   - a target task's `files` would be empty once its feature-docs paths are
     removed (A3).
5. Otherwise `dispatch`. `final_path_remaining` is true only on `dispatch`
   when some failed task, with its feature-docs paths removed, still holds a
   report-name violation (the validator's finder, which uses `--target-repo`
   and `--base-commit`); false in every other case.

Malformed input follows the Conventions. Affects task0006, task0008.

### D7. Removal patch field `tasks_patch.feature_docs_removals`

A non-empty list of mappings with exactly `task_id` and `path`, on
`replace_planning` only. Every `task_id` is in `carried_task_ids`, each pair
appears once, and the field never appears together with `path_corrections`.

Admission and limits:

- Admitted only on the correction entry (`create-plan` `completed` and
  `implement` `failed`). A `failed` task is permitted there; an
  `in_progress` task is not.
- Any other state is rejected as `feature-docs-removal-not-permitted`,
  the Re-planning and Initial-planning paths included.
- On the correction entry, `step_patches` and `tasks_patch.entries` are
  empty, and `requirements_patch` is null or has no entries.
- The Re-planning path's carry-over and `preserve` obligations apply.

Conditions and codes:

| Code | Rejects |
|---|---|
| `feature-docs-removal-shape` | A malformed field, an unknown or non-carried `task_id`, a duplicate pair, use with `path_corrections`, use on `append_rework` |
| `feature-docs-removal-not-permitted` | Any state other than the correction entry |
| `feature-docs-removal-in-flight` | A task with status `in_progress` or last journal event `launched` |
| `feature-docs-removal-merged` | A target with status or last journal event `merged` |
| `feature-docs-removal-path` | A `path` that is not a feature-docs path or is not in the target's `files` |
| `feature-docs-removal-empty-files` | A target whose `files` would become empty |
| `feature-docs-removal-incomplete` | A task not `merged` that still holds a feature-docs path after the patch |
| `feature-docs-removal-limits` | A breach of the limits above |

Application, in memory: every occurrence of `path` is removed from the
target's `files` and `notes` is set to null. Every other field, and every
other record, is copied verbatim. Each target's plan Files sections must
equal its corrected `files` (`task-plan-files-mismatch`, as for an entry).
Under `--dry-run-apply` a patch with this field needs `--workflow`,
`--journal` and `--feature-dir`; a missing one is an execution error
(exit 2). A `replace_all` without this field behaves as before in every
state. Affects task0001, task0006, task0007, task0008.

### D8. Correction dispatch input `planning_inputs.feature_docs_correction`

Its value is a mapping with `targets`, a list of `task_id` and `path`
mappings that the orchestrator copies from the entry script's `targets`.
It is null on every other dispatch and never non-null together with
`path_correction`. When present it is a `value_inputs` member.

On this dispatch:

- `write_policy.targets` are `replace_own` for IMPLEMENTATION.md,
  VERIFICATION.md and each target task's plan, plus `amend_other_feature`
  targets after a stage-1 request. `allowed_write_roots` is empty.
- The planner skips the `### 2a.` pass and does not write THREAT-MODEL.md.
- It returns `replace_planning` with:
  - every registered id in `carried_task_ids`;
  - every target in `feature_docs_removals`;
  - `entries` and `step_patches` empty;
  - `requirements_patch` null.
- `payload.task_index` is empty. `payload.other_feature_doc_fixes` is
  present when it amended documents.

Each target path is handled by kind:

| Target path | Handling |
|---|---|
| In scope | Amended through the D3 stages |
| The own feature's IMPLEMENTATION.md or VERIFICATION.md | Edited directly under `replace_own` |
| A document the target plan asked no change of | Removed only |
| Any other path needing a change | `blocked` naming the path |

Affects task0001, task0002, task0008.

### D9. Step A.6 order and restoration split (A4)

1. One Step A.6 evaluation runs the feature-docs judgment first, then the
   final-path judgment. Neither result skips the evaluation of the other.
2. A feature-docs `dispatch` runs section 13's
   `### Feature-docs correction dispatch`. Each validated correction is
   written with the artifact commit first, then one Write and one commit
   carrying its patch (`notes` cleared by the patch's application).
3. The Write of a correction that is not the last of the evaluation carries
   its patch only. It writes no restoration item: each target's
   `tasks.{T}.status` stays `failed` and no `routeback_failed_journal_line`
   is written, so every target stays a failed task (status `failed`) for
   the failed-task selection that `scripts/report-name-entry.py` owns and
   `scripts/feature-docs-entry.py` shares, whether or not the task has a
   `failed` journal event.
4. Every restoration item goes into the Write of the last correction of the
   evaluation, together, and only when no judgment of the evaluation is
   unresolved: the task-level items (status `pending`,
   `routeback_failed_journal_line` when `failed_journal_line` is non-null)
   for the targets of every correction of the evaluation (`violations` of
   the final-path correction, `targets` of the feature-docs correction),
   and the step-level items (`implement` `pending`, `failed_kind` null).
   This is FR9's one Write. A judgment is unresolved when it is `blocked`,
   exits non-zero, or ends without a validated patch; then no restoration
   item is written at all.
5. The feature-docs correction is last when `final_path_remaining` is
   false. Otherwise the final-path judgment then runs on the new state, with
   a freshly captured integration tip; while `implement` is still `failed`
   it can dispatch section 13 as today, and that correction is last.
6. If that final-path judgment returns `none`, the restoration items of
   point 4 (the feature-docs targets' task-level items and the step-level
   items) are written alone, in one Write and one commit.
7. Any unresolved judgment leaves `implement` `failed`, so Step B's stop
   condition 3 fires. The stop report names each unresolved judgment's
   failed conditions, read from `errors`.

Section 13's existing Apply paragraph stays true: the final-path correction
is always the last correction of its evaluation, so its Write carries its
patch and the restoration together. An interruption between two
corrections, or an unresolved final-path judgment after a written
feature-docs correction, leaves every target with status `failed` and
`implement` `failed`. The next Step A.6 evaluation finds no feature-docs
path left, so the feature-docs judgment returns `none`, and the final-path
judgment still selects those tasks as failed tasks. The restoration of that
evaluation is written for the targets of its own corrections. Affects
task0006, task0008, task0010.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Three tasks change `validate-worker-output.py` and refresh the same byte pin, causing merge conflicts | High | Medium | Pin refresh rule in Conventions; separate new test modules per task; parent-side adoption recomputes the digest after merge |
| Existing document tests pin phrases, heading lists and section digests in the files this feature edits | High | Medium | Heading constraints and forbidden words in Conventions; each task's Design lists the pins it must keep; the full suite is an acceptance criterion of every task |
| The seventh action breaks tests that enumerate six actions | Medium | Medium | task0003 owns the action-model pins and refreshes them; other tasks do not touch the action table |
| Planner and validator drift on the scope rule | Low | High | Single text owner (planner-contract.md) and a single validator implementation; the orchestrator's grant cites the same owner |
| A failed feature has both a feature-docs and a report-name problem and restoration runs too early | Medium | Medium | D9 restoration split and `final_path_remaining` |

## Open Questions

- [ ] None blocking. The four SPEC open questions are decided here: the
      declaration channel (D3), the action name `amend_other_feature` (D2),
      the code `plan-task-feature-docs` (D1), and the order (D9).
