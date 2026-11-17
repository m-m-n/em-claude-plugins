# Implementation Plan: final-path-plan-binding

## Overview

On the final-path correction entry, the validator rejects an entry whose plan
is not bound to an existing `tasks/{T}.md` (interim mitigation, FR1, FR4). The
implement phase gives the implementer the plan named by `tasks.{T}.plan`,
behind a fail-closed Plan-path check (root fix, FR2, FR3, FR6). Together the
two close the attack scenario of SPEC.md US1: the document the validator
compared with the canonical text is the document the implementer reads.

## Technology Stack

- **Language**: Python 3 (the validator `em-workflow/scripts/validate-worker-output.py`).
- **Tests**: the standard library `unittest` only, run by
  `python3 -m unittest discover -s tests`.
- **Documents**: Markdown reference documents under `em-workflow/references/`.
- **New dependencies**: none. `project.license` is `none`, and no license
  record is needed.

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Validator | `em-workflow/scripts/validate-worker-output.py` | Decides mechanically whether a worker patch is admitted (FR1) |
| Contract and phase documents | `em-workflow/references/workflow-patch.md`, `implement-phase.md`, `phases/create-plan-phase.md`, `batch-terminal-line.md`, `workflow-schema.md` | State the rules the orchestrator follows and the validator implements (FR2, FR3, FR4, FR6) |
| Tests | `tests/test_final_path_correction.py`, `tests/test_final_path_correction_docs.py` and the pinned neighbours | Pin the behaviour and the wording (FR5) |

Dependency direction: tests read the validator and the documents; the
validator does not read the documents; a document cites the validator's
function names only where the existing text already does so.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Binding rule of the correction entry (FR1) | One rule, implemented in the validator and stated in the contract | Pre: the patch is on the correction entry (the state in which the other `path-correction-entries` limits run). Rule: for each mapping item of `tasks_patch.entries` with key T, when an entry of any kind exists now at `tasks/{T}.md` under the feature directory and the item's `plan`, compared after `path_segments` normalization, is not `tasks/{T}.md`, the item is rejected. Post: the rejection has code `path-correction-entries`, carries `task_id` T and path `tasks/{T}.md`, and comes in addition to any other error of the same item. An indeterminate state of `tasks/{T}.md` counts as existing. The rule does not run on the Re-planning path or in any other state, and it does not require `tasks/{T}.md` for a plan when no such entry exists. | task0001 (implements), task0002 (states it in `workflow-patch.md`) |
| `path-correction-entries` error code | Existing code of the entries limit | Unchanged name and shape; the binding rule adds one more reason under it and no new code | task0001, task0002 |
| `tests/test_final_path_correction_docs.py` | Docs pins of the final-path correction | task0002 inserts its new class directly after `TestMediumFixesLimitsOutsideTheConditions`; task0003 appends its new classes at the end of the file, before the module's main guard. Neither task edits an existing class, helper or constant, and neither edits the module docstring: each new class names the scenario it covers in its own docstring. New module-level constants sit directly above the class that uses them. | task0002, task0003 |
| `tests/test_gate_option_vocabulary.py` | Byte pins of contract and validator files | task0001 refreshes only the validator pin, `VALIDATE_WORKER_OUTPUT_SHA256`; task0002 refreshes only the `workflow-patch.md` pin, `WORKFLOW_PATCH_SHA256`. Each refresh is done in place with a new comment paragraph directly above the assignment, opened by "Refreshed again by final-path-plan-binding/taskNNNN", saying what changed and ending with "Same rationale: refresh, don't remove." | task0001, task0002 |

## Conventions

- **Error shape.** The validator reports the binding rejection through the
  existing per-entry rejection of `_correction_entries_errors`: code
  `path-correction-entries`, a message that names the binding, `task_id` and
  `path`.
- **Fail closed.** A doubtful read never admits an entry (validator), and a
  doubtful plan path never reaches an implementer (implement phase). Nothing
  is repaired, stripped or replaced, and nothing falls back to
  `tasks/{T}.md`.
- **Git access.** `_correction_entries_errors` and anything it calls for the
  binding reach git only through `_read_base_document`; the binding reads the
  working tree of the feature directory and starts no process (NFR1).
- **Tests.** Standard library only (NFR3). New tests are new classes; the
  existing tests of `tests/test_final_path_correction.py` and
  `tests/test_final_path_correction_docs.py` are not edited (NFR5). Docs
  tests slice the owned section, normalize whitespace before matching, and
  give every new matcher a negative proof against a forged or pre-change
  sample. No test writes under `em-workflow/`; fixtures live in temporary
  directories.
- **Citation discipline.** A document cites a rule that another document or
  section owns, by path plus heading or by the named paragraph, instead of
  restating it.
- **Plugin version.** This repository is exempt: version handling follows
  `em-workflow/skills/plan-writing/SKILL.md`, `## Plugin Version Handling`,
  `### Exempt repositories`.
- **Paths in text.** Repository-relative paths only; no absolute
  home-directory path and no external URL in any changed file.

## Cross-task Design Decisions

### D1: The validator and the contract state one binding rule

task0001 implements the binding rule of Shared Components and task0002 states
it in the `path-correction-entries` bullet of `workflow-patch.md`. Both use the
same condition, code, fields, fail-closed reading and scope, so the contract
and the validator cannot disagree after the parallel merge. Affected tasks:
task0001, task0002.

### D2: The interim mitigation and the root fix ship together

FR1 alone leaves the implementer's plan path fixed; FR2 alone leaves a free
plan path that may hold a decoy. Both are in this feature (SPEC.md assumption
A1). The validator rule and the implement-phase change do not depend on each
other's text, so the tasks run in parallel. Affected tasks: task0001, task0003.

### D3: Shared test files are touched at disjoint places

`tests/test_final_path_correction_docs.py` and
`tests/test_gate_option_vocabulary.py` are each touched by two tasks. The
insertion points and the pin ownership in Shared Components keep the edits
apart, so a merge conflict, if any, is a textual adjacency only. Affected
tasks: task0001, task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The binding rule adds an error to an existing test of `tests/test_final_path_correction.py` | Low | Medium | Existing fixtures use plan `tasks/task0003.md` for key `task0003`, which is bound. The implementer runs the full suite; a failing existing test is reported as a plan deviation, never edited |
| New wording in `implement-phase.md` or `batch-terminal-line.md` trips a locator of a neighbouring pinned test | Medium | Medium | task0003 lists the phrases its new text must avoid and the neighbouring modules to run |
| Two tasks refresh pins in the same test module | Medium | Low | Each task owns one pin; the comment paragraphs sit above different assignments |
| The Plan-path check stop is reported as `unmapped_stop` in batch | Low | Medium | FR6 binds it to the `stop-condition-3` row in task0003 |

## Open Questions

- [ ] None blocking.
