# Implementation Plan: subagent-report-write-block

## Overview

Stop a plan with a new FR2-matching name at validation, make the implementer
fail immediately on the Write rejection, stop the parent from retrying the same
cause, and add a correction procedure for the final path of an existing plan,
entered from `implement: failed` at the start of a re-run.

## Technology Stack

- **Language / Framework / Key libraries**: Python 3 standard library, PyYAML
  (already a runtime dependency of the validator), git, unittest.
- **New dependencies**: none, so no license entry is needed.

## Layer Structure

| Layer | Holds | Depends on |
|---|---|---|
| Rule text | `em-workflow/skills/plan-writing/SKILL.md`, section `## Report Artifact Names` (FR1, FR2) | Nothing |
| Mechanical checks | `em-workflow/scripts/validate-worker-output.py` (regex constant, FR3, FR4, FR5), `em-workflow/scripts/report-name-entry.py` (FR6 judgment) | git, the journal, workflow.yaml |
| Protocol documents | workflow-patch, workflow-schema, create-plan-phase, rework-task-synthesis, implement-phase, batch-mode, batch-terminal-line, develop, implementer, worktree-task-workflow, planner and rework-planner documents | Cite the rule text and the mechanical checks; never restate the regex |

`report-name-entry.py` loads `validate-worker-output.py` as a sibling file, so
the regex and every judgment have one implementation (NFR3).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `REPORT_ARTIFACT_NAME_RE` | The FR2 constant in the validator | Pattern source is exactly `^(REPORT\|SUMMARY\|FINDINGS\|ANALYSIS).*\.md$` (without the table escapes), compiled case-insensitively | task0001, task0002 |
| `is_report_artifact_name(path) -> bool` | FR2 judgment | Any input. True only for a string whose last normalized path segment (`path_segments`) matches the constant. Directory names are never judged | task0001, task0002 |
| `require_report_name_base(target_repo, base_commit)` | FR4 input check | Raises `ExecutionError` when a value is missing, the commit is not 40 or 64 lowercase hex digits, the repository is unusable, or the commit does not resolve to a commit object. Returns nothing on success. Called only after a matching name was found | task0001, task0002 |
| `base_tree_entry(target_repo, base_commit, path) -> "regular" \| "other" \| "absent"` | Reads the tree entry at the base commit | Pre: the base passed `require_report_name_base`, the path passed `is_safe_relative_path`. `regular` is a non-symlink file entry; `other` is a directory, symlink or submodule. The path is normalized with `path_segments` and reaches git without a shell, as literal text: it is never read as an option, pathspec magic or a revision expression | task0001, task0002 |
| `find_report_name_violations(files_by_task, target_repo, base_commit) -> [(task_id, path)]` | FR3 judgment over a task-to-files mapping | Skips non-string and unsafe entries (already reported elsewhere). Reads the base inputs only when a matching name is present. A matching name is a violation unless `base_tree_entry` is `regular` | task0001, task0002 |
| `journal_last_events(journal_path) -> {task_id: (event, line)}` | Last-event-per-task replay | A missing file reads as no events; an unreadable file raises `ExecutionError`. Blank, malformed and unknown-event lines are skipped but counted for `line`, which follows the line-counting rule of the `routeback_failed_journal_line` section of `references/workflow-schema.md` | task0002 |
| `path_correction_precondition_errors(workflow, corrections, last_events, target_repo, base_commit) -> [error]` | FR5 conditions 1 to 3 | Used by the dry-run check and by the entry script. A correction is a mapping with `task_id` and `old_path`; the entry script supplies them from its violations | task0002 |
| Validator CLI | Base and journal inputs | `--target-repo` (integration worktree), `--base-commit` (full commit ID of the integration tip), `--journal` (the feature's `journal.jsonl`). All optional to the parser; each is read only when needed | task0001, task0002, task0004 |
| Validator error codes | Machine-readable rejections | `report-name-new-file` (FR3; each error carries `task_id` and `path`). `path-correction-shape`, `path-correction-not-permitted`, `path-correction-step-patches`, and one per FR5 condition in order: `path-correction-in-flight`, `path-correction-merged`, `path-correction-old-path`, `path-correction-new-path`, `path-correction-content` | task0001, task0002, task0004 |
| `tasks_patch.path_corrections` | The FR5 patch field | A non-empty list of mappings with exactly `task_id`, `old_path`, `new_path`, on `replace_planning` only. Every `task_id` is in `carried_task_ids`. Owned by `references/workflow-patch.md`, section `## Final-path correction` | task0002, task0003, task0004 |
| `report-name-entry.py` | FR6 judgment | Arguments `--workflow`, `--journal`, `--target-repo`, `--base-commit`. Prints one JSON object with `entry` (`none`, `dispatch` or `blocked`), `violations` (each with `task_id`, `path`, `failed_journal_line`) and `errors`. Exit 0 for all three outcomes, exit 2 on an execution error. `none`: implement is not failed, or no failed task has a violation. `dispatch`: violations exist and conditions 1 to 3 hold. `blocked`: violations exist and one of conditions 1 to 3 fails | task0002, task0007 |
| Implementer report field `write_rejection` | FR7 report | `null`, or a mapping with `path` (repository-relative) and `rejection_text`. Top-level key of the Step 7 report | task0005, task0006 |
| `tasks.{T}.notes` marker | FR8 record | `notes` begins with the literal `report-name-write-rejected:`, followed by the target path and the rejection text. Written only in the wake commit. Applying a correction to the task clears `notes` to null | task0004, task0006, task0007 |
| `planning_inputs.path_correction` | The FR6 dispatch input | A value resolved by the orchestrator: `targets`, a list of `task_id` and `old_path`. Null on every other dispatch. A `value_inputs` member when present | task0003, task0004, task0007 |
| Cited headings | Stable citation anchors | `## Report Artifact Names` (plan-writing), `## Final-path correction` (workflow-patch), `## 13. Final-path correction dispatch` (create-plan-phase), `## Step A.6: failed からの入口` (develop) | task0001, task0003, task0004, task0005, task0006, task0007 |

task0001 owns the first five components. A worktree branched before they reach
the parent implements them to this contract, in the same place of the file; a
merge conflict is resolved by parent-side adoption.

## Conventions

- **Names**: no deliverable of this feature has an FR2 file name. Tests build
  any such file at run time in a disposable repository.
- **Exit codes**: 1 is a validation failure with JSON detail on stdout; 2 is an
  execution error raised as `ExecutionError`. Missing or unresolvable inputs are
  exit 2, never a pass.
- **Citation**: documents other than plan-writing cite `## Report Artifact Names`
  and do not contain the regex. implementer.md quotes the rejection text, not the
  regex.
- **Pinned text**: existing documents are pinned by tests. Add new sentences next
  to pinned ones instead of rewording them. These stay as they are: `All eighteen
  rules apply`, the `Neither this protocol-error rule` sentence, `Step I.0
  recognises three entry routes`, the two sentences on the writer and lifecycle in
  `## routeback_failed_journal_line`, the Resume guard bullets, and the ten rows of
  the batch Non-packet gates table.
- **Tests**: unittest only. Git-using tests create their repository in a temporary
  directory and set identity per command.

## Cross-task Design Decisions

### D1: The correction is a field of `replace_planning`

FR5 is an exception to the verbatim copy of carried records, so it lives on the
operation that carries records. No third operation and no new `--kind` is added:
the `--kind` count and the operation set are pinned. Affects task0002, task0003,
task0004.

### D2: Permission states for `path_corrections`

| State | Result |
|---|---|
| `create-plan: completed` and `implement: failed` (the correction entry, FR6) | Admitted. Carry-over and `preserve` obligations of the Re-planning path apply. A `failed` task is permitted; an `in_progress` task stays `replace-all-not-permitted`. `step_patches` must be empty |
| The Re-planning path, including route back | Admitted under that path's existing rules |
| The Initial-planning path | Rejected, `path-correction-not-permitted` |

A `replace_all` without `path_corrections` behaves as before in every state.
Affects task0002, task0004.

### D3: Condition 5 is checked mechanically

For IMPLEMENTATION.md, VERIFICATION.md and each target task's plan, take the
version at the base commit and the current version, and apply one normalization
to both: a single left-to-right pass that replaces each old path by its new path
and each old file name by its new file name, longer match first. The two results
must be equal, and the current version must not contain an old path. A document
absent at the base commit is outside the set. New task plans under `entries` are
outside the set. Affects task0002, task0003, task0004.

### D4: Patch and restoration are one Write

On the correction entry the orchestrator applies the patch and the FR6 restoration
in memory and writes workflow.yaml once, in one commit, after the artifact commit.
An interruption therefore cannot leave corrected `files` with `implement: failed`,
which the FR6 judgment would no longer recognize. A re-run after an interruption
re-judges from workflow.yaml with a new `request_id` and `patch_id`. Affects
task0004, task0007.

### D5: The target restarts through the route-back record

The FR6 restoration sets `tasks.{T}.status` to `pending` and
`tasks.{T}.routeback_failed_journal_line` to the task's last `failed` line, so
I.2.a, I.2.b and `queue_stop_guard.py` classify it as unlaunched with no hook
change. The kept worktree and branch are reused as they are. Affects task0004,
task0006, task0007.

### D6: FR6 runs once per invocation in Step A.6

Step A.6 sits between Step A.5 and Step B and runs only on Step A's existing-feature
branch. Step B never re-enters it, which is what keeps it out of the failed run.
Outcomes `none` and `blocked` fall through to Step B, where stop condition 3 fires
as before. Affects task0007.

### D7: Batch stop binding

The FR8 batch abort binds to the `implement-second-failure` row
(`implement_task_failed`) through a named paragraph in `## Stop point coverage`,
without a new row or reason code. Affects task0006.

### D8: Scenario-ID scan on a correction

A patch with non-empty `path_corrections` skips the VERIFICATION.md target of the
scenario-ID form check, because the correction may change only path strings. New
task plans under `entries` stay checked. Affects task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| task0001 and task0002 edit the same validator regions | High | Medium | Components pinned above; parent-side adoption |
| A restarted implementer finds uncommitted changes in the kept worktree | Medium | Low | The worktree is reused as it is, like the existing retry; it is never discarded automatically |
| An interruption between the implementer's return and the wake commit loses the FR7 report | Low | Low | The marker is absent, so one ordinary retry may run; the next rejection records it |
| A future Claude Code changes the rejection condition (A4) | Low | Medium | Definition lives in one section and one constant, pinned by a test |

## Open Questions

- [ ] FR10 has no implementing task: the procedure is already in SPEC.md and the
      plugin must not hold it. TS-16 verifies it manually.
