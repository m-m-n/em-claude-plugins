# Implementation Plan: final-path-correction-medium-fixes

## Overview

Fix the seven medium findings on the final-path correction. The validator and
the entry script change, the owning documents follow, and a correction changes
nothing but paths.

## Technology Stack

- **Language / Framework**: Python 3, standard library `unittest`.
- **Key libraries**: none new. No new dependency is introduced, so no license
  record applies.

## Layer Structure

| Layer | Responsibility | Depends on |
|---|---|---|
| `em-workflow/scripts/validate-worker-output.py` | Correction rules, in its `--dry-run-apply` stage and its worker-result stage | none of the layers below |
| `em-workflow/scripts/report-name-entry.py` | The entry decision of a develop re-run | the validator, as its sibling module |
| `em-workflow/references/`, `em-workflow/agents/` | The written contract of the same rules | states the rules; nothing imports it |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Validator helpers used by the entry script | Decide violations and conditions 1 to 3 | `find_report_name_violations(files_by_task, target_repo, base_commit)`, `path_correction_precondition_errors(workflow, corrections, last_events, target_repo, base_commit)`, `read_journal_events(journal_path)` and `workflow_find_step` keep their signatures and results. Post: violations come in the iteration order of the mapping, then file order | task0001 (keeps them unchanged), task0002 (calls them) |
| Error codes | Name the two new rejections | `path-correction-requirements` for `requirements_patch` and `path-correction-entries` for `tasks_patch.entries`. Both are reported outside the five numbered conditions | task0001 (emits), task0003 (documents) |
| Reference occurrence | Say where an old reference stands in a text | Decision D3 | task0001 (implements), task0002 (test fixtures rely on it), task0003 (documents) |
| Permitted replacement | Say what an occurrence may become | Decision D4 | task0001 (implements), task0003 (documents) |
| Document classes | Say which rule covers which document | Decision D5 | task0001 (implements), task0003 (documents) |
| Canonical plan text | Fix the body of a new task's plan on the correction entry | Decision D6 | task0001 (renders), task0003 (documents) |
| Byte pins in `tests/test_gate_option_vocabulary.py` | Pin the digests of the validator and of workflow-patch.md | Decision D7 | task0001, task0003 |

## Conventions

- Rejections use the existing error shape. A condition 5 error keeps its
  `document` field, with the document spelled as `workflow.yaml` spells it.
- A document or file that cannot be read or compared is a rejection. A missing
  input stays an execution error (exit 2).
- Base-commit reads go through `base_tree_entry` and `_read_base_document` only.
- A file with a report-artifact name exists only at run time, inside a test's
  temporary repository.
- A recurrence test names its finding's stable_id in a comment.

## Cross-task Design Decisions

### D1: One task owns every validator change

task0001 holds every validator change. Tasks run fully in parallel, and FR1 calls
the occurrence rule of FR7 and the form check of FR2. A placeholder in the same
module would be overridden silently by the real definition, and two tasks
refreshing `VALIDATE_WORKER_OUTPUT_SHA256` would conflict on one line by
construction. task0001 therefore has eight criteria, one per requirement group,
which is past the size guideline by one.

Affected tasks: task0001, task0002, task0003.

### D2: Correction path state

A patch with non-empty `tasks_patch.path_corrections` is in exactly one state,
computed from `workflow.yaml` and the phase state before the `replace_all` branch:

- **Correction entry**: `create-plan` is `completed` and `implement` is `failed`.
- **Re-planning path**: `create-plan` is `needs_update`, or `pending` on a
  SPEC-change re-entry.
- **Any other state**: already rejected as `path-correction-not-permitted`.
  Condition 5 runs as on the correction entry, the strictest form, and the FR1
  limits do not run.

Affected tasks: task0001, task0003.

### D3: Reference occurrence

SPEC.md FR7 is the rule. These readings complete it.

- The scan runs left to right. At one position the longer token wins.
  Occurrences never overlap.
- A token is an old path of several segments, or a bare old file name.
- A one-segment old path, judged after `path_segments`, is matched only as a bare
  name.
- "A preceding `./`" means the two characters before the token are `./`. It lifts
  the boundary rule for an old path of several segments only.
- Every test of a character class is on ASCII letters and digits, as FR7 states.

Affected tasks: task0001, task0002, task0003.

### D4: Permitted text at an occurrence

The old text itself is always permitted by the comparison. The left-behind check
rejects it where it may not remain. Otherwise:

| Occurrence | Document | Permitted replacements |
|---|---|---|
| Old path of several segments | Any | That correction's `new_path` |
| Bare old file name | Target plan | The new file names of the corrections of the target tasks using that plan that hold this old file name; when there are none, the new file names of all corrections of the patch that hold it |
| Bare old file name | Any other document | The new file names of all corrections of the patch that hold it |
| One-segment old path | As for a bare old file name | The bare replacements above, plus the `new_path` of each selected correction whose old path is that one segment |

The last row is needed because a plan's Files section must hold the full
`new_path` of a one-segment old path that moves to another directory.

Affected tasks: task0001, task0003.

### D5: Document classes

On the correction entry a document takes the first class that fits. Paths are
compared after `path_segments` normalization.

| Class | Document | Comparison with the base commit | Left-behind check |
|---|---|---|---|
| Merged plan | Plan used by a task whose status or last journal event is `merged` | Byte-equal | No |
| Target plan | Plan used by a target task | Positional | Yes |
| Shared document | IMPLEMENTATION.md, VERIFICATION.md | Positional | Yes |
| Non-target plan | Plan of any other task in `workflow.yaml` | Positional | No |

For every class:

- No entry at the base commit and present now: rejected (FR9).
- No entry at the base commit and absent now: nothing to compare, not an error.
- An entry at the base commit and absent now: rejected.
- Not regular at the base commit, or unreadable now: rejected.

A new task's plan under `tasks_patch.entries` is in none of these classes unless
its normalized path equals one of those documents, in which case that document's
class applies. That is the FR9 exception and its precedence.

On the Re-planning path only IMPLEMENTATION.md, VERIFICATION.md and the target
plans are read, only the left-behind check runs, and a document absent now is not
an error.

Affected tasks: task0001, task0003.

### D6: Canonical plan text

The text is UTF-8 with LF line ends and a final LF. Its lines, in order, are:

1. `# Task Plan: {task_id} - correct path references`
2. An empty line.
3. `## Scope`
4. An empty line.
5. `### Files to Modify`
6. For each file of the entry, in `files` order:
   ``- `{file}` - correct the old references``
7. An empty line.
8. `## Acceptance Criteria (MANDATORY)`
9. An empty line.
10. For each correction with an occurrence in those files at the base commit, in
    `path_corrections` order, with n counting from 1:
    ``- [ ] AC-{n}: `{old_path}` is replaced by `{new_path}`, and the bare `{old_name}` by `{new_name}`.``

`{old_name}` and `{new_name}` are the last path segments. A correction has an
occurrence when the scan finds its old path, or its old file name as a bare
occurrence.

Affected tasks: task0001, task0003.

### D7: Byte pins

Changing a pinned file requires refreshing its digest in
`tests/test_gate_option_vocabulary.py`, in place, with a `Refreshed again by`
comment. The digest is taken last, after every other edit of the pinned file, and
again after any conflict adoption that touches it.

- task0001 alone owns `VALIDATE_WORKER_OUTPUT_SHA256`.
- task0003 alone owns `WORKFLOW_PATCH_SHA256`.

Affected tasks: task0001, task0003.

### D8: Non-target plan write permission

`planner-contract.md` and section 13 of create-plan-phase.md do not change, and no
file is added to any task. The FR8 text in `## Final-path correction` of
`agents/implementation-planner.md` stays, with one condition: an unmerged
non-target plan's references are replaced only when that plan is listed in
`write_policy.targets`. Otherwise the planner leaves it unedited, because FR3 and
A2 allow the old reference to remain there. Widening the write permission is a
separate follow-up task, outside this feature.

Affected tasks: task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The canonical text in implementation-planner.md and the renderer drift apart | Low | High: every new task under `entries` is rejected | D6 fixes the text for both tasks; VERIFICATION.md compares them after integration |
| task0001 is large for one session | Medium | Medium | Its design is split into components that can be tested one at a time |
| A pinned phrase stays in workflow-patch.md but stops being true | Medium | Medium | task0003 keeps the phrases and states the positional comparison in them |

## Open Questions

None.
