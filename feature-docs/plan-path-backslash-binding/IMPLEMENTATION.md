# Implementation Plan: plan-path-backslash-binding

## Overview

The implement phase builds `task_plan_path`, and Plan-path check rules 2 and 3
judge, the path made from the segments that `path_segments` returns for the
stored `tasks.{T}.plan` value, which is the resolution the validator already
reads (FR1, FR2). Section 2a of `phases/create-plan-phase.md` states the same
resolution (FR3). The validator is unchanged (FR4). A behavior test shows that
the derived path and the validator's path are one file, never a decoy whose
literal name holds a backslash (SPEC.md AC-4).

## Technology Stack

- **Documents**: Markdown reference documents under `em-workflow/references/`.
- **Tests**: the Python 3 standard library `unittest` only, run by
  `python3 -m unittest discover -s tests`.
- **Validator (read only)**: `em-workflow/scripts/validate-worker-output.py`.
- **New dependencies**: none. `project.license` is `none`, so no license
  record is needed.

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Phase documents | `em-workflow/references/implement-phase.md`, `em-workflow/references/phases/create-plan-phase.md` | State how the orchestrator resolves and checks the plan path it hands to the implementer (FR1, FR2, FR3) |
| Validator (unchanged) | `em-workflow/scripts/validate-worker-output.py` | Owns `path_segments` and the reference resolution `_resolve_contained_relative_path` (FR4) |
| Tests | `tests/test_final_path_correction_docs.py` (wording pins), `tests/test_plan_path_backslash_binding.py` (new, behavior) | Pin the document wording (FR5) and the behavior against the validator (SPEC.md AC-4) |

Dependency direction: the documents cite validator function names; the tests
read the documents or load the validator by file path; the validator reads
neither.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Plan path resolution (FR1) | The one derivation of the absolute plan path from the stored value | Pre: S is the stored `tasks.{T}.plan` value and passes Plan-path check rule 1 (a safe relative path in the sense of `is_safe_relative_path`, naming at least one segment after `path_segments`). Derivation: the integration worktree's `feature-docs/{feature}/` directory, joined in order with each segment that `path_segments` of `scripts/validate-worker-output.py` returns for S. The stored string S is never joined as-is. Post: for every such S, the result is the same path that `_resolve_contained_relative_path` returns for S under the same feature directory when it admits S, and a file whose literal name holds a backslash is never the result. Plan-path check rules 2 and 3 judge this result. | task0001 (states it in both phase documents), task0002 (encodes it in a test and compares it with the validator) |
| `path_segments`, `is_safe_relative_path`, `_resolve_contained_relative_path`, `_plan_is_bound_to_task_md` | Validator functions referenced by name | Unchanged in name, parameters and behavior (FR4). The documents cite `path_segments` by name and do not restate its procedure | task0001 (cites), task0002 (calls, read only) |

## Conventions

- **Citation discipline.** A document cites `path_segments` by name together
  with `scripts/validate-worker-output.py` and does not describe what the
  normalization does (SPEC.md A3). Section 2a keeps citing the Plan-path check
  without restating it.
- **Root fix only.** No rule rejecting a stored value that differs from its
  canonical form is added anywhere (SPEC.md A1). Every spelling the validator
  binds keeps working.
- **Tests.** Standard library only. Docs tests slice the section they concern
  and normalize whitespace before matching. Every new matcher has a negative
  proof against a verbatim pre-fix sample captured from the base revision. No
  test writes under `em-workflow/`: fixtures live in temporary directories, and
  the validator is loaded by file path without leaving compiled files under
  `em-workflow/`.
- **File ownership.** No file is in the `files` of both tasks. Neither task
  modifies `em-workflow/scripts/validate-worker-output.py` or
  `tests/test_final_path_correction.py`.
- **Plugin version.** This repository is exempt: version handling follows
  `em-workflow/skills/plan-writing/SKILL.md`, `## Plugin Version Handling`,
  `### Exempt repositories`.
- **Paths in text.** Repository-relative paths only.

## Cross-task Design Decisions

### D1: One derivation, stated by the documents and proven by a behavior test

task0001 writes the Plan path resolution into the `task_plan_path` line,
Plan-path check rules 2 and 3 and section 2a. task0002 encodes the same
derivation from the Shared Components contract and compares its result with
the validator's `_resolve_contained_relative_path`. Both follow the contract
rather than each other's text, so they run in parallel. Affected tasks:
task0001, task0002.

### D2: The backslash spellings stay admitted

The fix aligns the implement phase with the validator instead of narrowing
what the validator binds (SPEC.md A1, A2). task0001 adds no rejection rule to
the Plan-path check; task0002 asserts that the validator still binds both
backslash spellings and the other normalized spellings to `tasks/{T}.md`.
Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| New wording in Step I.2.a or section 2a trips a locator or threshold of a neighbouring pinned test | Medium | Medium | task0001 lists the phrases its new text avoids and the neighbouring modules to run; the full suite is run |
| A literal backslash file name cannot be created on the platform that runs the tests | Low | Low | task0002 skips those cases with a stated reason where backslash is a path separator |
| The derivation the test encodes drifts from the one the documents state | Low | Medium | Both follow the Shared Components contract; the docs tests pin the documents to `path_segments` |

## Open Questions

- [ ] None blocking.
