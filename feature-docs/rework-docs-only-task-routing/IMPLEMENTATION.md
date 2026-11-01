# Implementation Plan: rework-docs-only-task-routing

## Overview

Route rework corrections that only need `feature-docs/{feature}/` planning documents and requirement test references to the rework-planner itself (docs-only correction route), never to an implementer task, and keep `implement` completed on a docs-only round so an unattended run does not stop at implement `failed` (`failed_kind: decision`).

## Technology Stack

- **Language**: Python 3 (validator script, tests); Markdown (contracts, agent and skill documents)
- **Key libraries**: Python standard library `unittest` for every new test (NFR5); the validator's existing YAML parser dependency is unchanged
- **New dependencies**: none (`project.license: none`; nothing to record)

## Layer Structure

| Layer | Members | Responsibility |
|---|---|---|
| Contract (SSOT prose) | `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/contracts/rework-planner-contract.md`, `em-workflow/references/workflow-patch.md` | Own each rule exactly once (NFR4) |
| Process | `em-workflow/agents/rework-planner.md`, `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/review-phase.md` | Describe who does what, citing the contract layer by path; never restate it |
| Machine | `em-workflow/scripts/validate-worker-output.py`, fixtures under `em-workflow/references/fixtures/`, tests under `tests/` | Render contract rules mechanically and pin them |

Allowed dependency direction: Process -> Contract, Machine -> Contract. A rule's prose and its validator rendering describe the same rule; the prose owner is the task named in Shared Components below.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Docs-only correction route (named subsection) | The rule set for corrections resolvable by planning documents alone | Lives in `rework-task-synthesis.md` Section 9 as a subsection whose heading is literally `### Docs-only correction route`, placed after `### Wording-correction route` and before `## 10.`. Other documents cite it by this name plus the file path, in English; Japanese documents may add the Japanese term 文書のみ修正経路 next to the cited name | task0001 (owner), task0002, task0005 |
| Route decision order | Which route a needed change takes | Fixed order: Wording-correction route -> Docs-only correction route -> rework-task synthesis / SPEC-change transition. A change needing SPEC.md or REQUIREMENTS.md never takes the docs-only route | task0001 (owner), task0002, task0005 |
| Docs-only round | The rework round whose result corrects documents only | Precondition: the round's every failed item or finding is resolved by the docs-only route. Postcondition (patch shape): operation `append_rework`, `tasks_patch.mode: append`, `expected_next_task_id` equal to the input's `next_task_id`, `tasks_patch.entries` absent or an empty mapping; `step_patches` holds one entry, for the origin step only (`verify` for verify-sourced, `review` for review-sourced), setting `status: pending` with `expected.status` equal to that step's current status; no `step_patches` entry targets `implement`; `preserve` includes `workflow.implement.base_commit`. Payload: `rework_index` present as an empty mapping, `shared_contract_rationale` present, `doc_corrections` non-empty | task0001 (owner), task0002, task0003, task0004, task0005 |
| Mixed round | A round with both code corrections and docs-only corrections | Docs-only items are corrected directly by the rework-planner; code items become tasks under the existing grouping rule (Section 4). Patch: at least one entry; `step_patches` return `implement` and the origin step to `pending` as before. Payload `doc_corrections` non-empty | task0001 (owner), task0002, task0004 |
| `requirements_patch` tests replacement | Replacing scenario IDs in a requirement's `tests` | Set key `tests_replace`: a non-empty list of pairs, each a mapping with `from` (old ID) and `to` (new ID), both non-empty strings, `from` different from `to`, no `from` repeated within one requirement entry. Expected key `tests_contains`: a list of IDs; every `from` of that entry's `tests_replace` must appear in it (checked structurally). Under dry-run, every `tests_contains` ID must be in the requirement's current `tests`, else rejection with code `expected-mismatch`. Application: each `from` is replaced by its `to` at the same position; when `to` is already present, `from` is removed without adding a duplicate; `tests_replace` is applied before `tests_append` in the same entry. The `_append` forms and direct assignments of `status` / `tbd_reason` / `excluded_reason` are unchanged | task0003 (owner), task0001, task0002 |
| `payload.doc_corrections` | Declaration of every correction made through the docs-only route (FR7) | Optional key of the rework-planner `completed` payload (not added to the validator's required payload keys). Value: a list; each entry is a mapping with `origin_kind` (`review` or `verify`) and `origin_id` (the Invariant 6 pair of `rework-task-synthesis.md`), `documents` (non-empty list of feature-directory-relative paths, each one of `VERIFICATION.md`, `IMPLEMENTATION.md` or an existing `tasks/taskNNNN.md`) and `scenario_renames` (optional list of pairs, each a mapping with `from` and `to`, used when a scenario ID is renamed, e.g. TS-less-hyphen form to TS-hyphen form). Contract obligation: non-empty on every `completed` result that corrected documents through the docs-only route (docs-only and mixed rounds), absent or empty otherwise. The validator consumes only `scenario_renames`; malformed entries contribute nothing and never raise | task0002 (owner), task0001, task0003, task0004 |
| Rename-aware coverage rule | Judging `covered_by_existing` after a scenario rename | A `covered_by_existing` ID passes when it is a key of the input's `verification_index`, or when some declared `scenario_renames` pair has it as `to` and that pair's `from` is a key of `verification_index`; otherwise rejection with the existing code `rework-index` | task0001 (prose in Section 12), task0002 (contract check 2), task0004 (validator) |
| Feature-docs files rule | Keeping planning documents out of implementer tasks (FR3) | A rework-synthesized task's `files` contain no path whose first path segment is exactly `feature-docs`, segments taken with `\` treated as `/` and empty and `.` segments dropped (the same normalization the validator already uses for allowed-root containment). Applies to `append_rework` entries only | task0001 (prose owner, Section 7), task0002 (rework-planner.md sentence), task0004 (validator) |

## Conventions

- **Terminology**: English documents use "docs-only correction route", "docs-only round", "mixed round", "origin step". `skills/develop/SKILL.md` uses 文書のみ修正経路 / 文書のみの回 / 混在する回 / 発生元の step, citing the route by its English heading.
- **SSOT discipline (NFR4)**: each rule is written once, in the owner named above; every other document cites it by path (and section or heading) without restating it, matching the existing "cited, not restated" phrasing in these documents.
- **Pinned existing text**: when modifying a document, insert new sentences or paragraphs; do not reflow, reword or re-indent existing sentences. Several existing tests pin literal text, including line breaks and indentation.
- **Tests**: each task creates exactly one new test module under `tests/`, imports only standard-library modules, and edits no existing test module. A doc-test pin is accompanied by a non-vacuity negative sample, following the existing doc-test modules. A test module reads only files its own task owns, plus read-only references explicitly named in its task plan.
- **Fixtures**: new fixture cases sit under `em-workflow/references/fixtures/<kind>/<group>/<case>/`, are discovered by the existing data-driven runner in `tests/test_validate_worker_output.py` without editing it, and carry the `valid-` or `invalid-` prefix matching the expected exit code.
- **Validator errors**: every new rejection is reported through the script's existing error-record form with a kebab-case code; malformed input becomes a validation error or is ignored as stated in its rule, never an uncaught exception.
- **Version**: no plan text in this feature instructs a plugin version change.

## Cross-task Design Decisions

### D1: A docs-only round is recognized by empty task entries

Decision: no new patch field or flag marks a docs-only round; an `append_rework` patch whose `tasks_patch.entries` is absent or empty is the docs-only round.
Rationale: the patch already carries the fact; the validator can check it structurally (FR5) without a new vocabulary item.
Affected: task0001, task0002, task0003, task0004, task0005.

### D2: `payload.doc_corrections` is optional to the validator

Decision: the key is not added to the rework-planner's required payload keys; its presence is a contract obligation stated in `rework-planner-contract.md`, and the validator reads only `scenario_renames` from it.
Rationale: existing rework-planner results without document corrections stay valid; the SPEC lists only the rename-aware coverage rejection for FR7.
Affected: task0002, task0003, task0004.

### D3: Tests replacement binds `from` to `expected`

Decision: every `from` of `tests_replace` must also be listed in the same entry's `expected.tests_contains`, checked structurally, so a replacement can never skip the dry-run expectation check.
Rationale: FR4 requires the old ID's presence to be confirmed by `expected`; binding them makes that confirmation unavoidable.
Affected: task0003 (owner), task0001 and task0002 (cite).

### D4: Fixture independence across parallel tasks

Decision: the docs-only round fixture (TS-1) belongs to task0003, because it needs the tests replacement; it conforms to the docs-only round, `doc_corrections` and feature-docs files contracts above, so it still passes after task0004's rules merge. task0004's fixtures use no `tests_replace`, so they pass in a worktree without task0003's change.
Rationale: tasks run fully in parallel; each task's own suite must pass in its own worktree and after integration.
Affected: task0003, task0004.

### D5: Prose owners for validator rules

Decision: task0004 changes no contract prose. The prose for its rules is owned by task0001 (Section 7 and Section 12 of `rework-task-synthesis.md`) and task0002 (check 2 of `rework-planner-contract.md`); task0003 owns both the prose (`workflow-patch.md`) and the validator rendering of the tests replacement.
Rationale: the validator's own header requires rule and prose to change together; the split keeps each prose owner single.
Affected: task0001, task0002, task0003, task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing doc tests pin literal text that the new sentences disturb (Wording-correction route blocks, develop verify item 6 line break, the four-row `--once` table, review-phase R5 sentences, the contract's four numbered checks) | Medium | Medium | Conventions "Pinned existing text"; each task plan names the pins in its files; full suite run per task |
| task0003 and task0004 both edit `validate-worker-output.py` | High | Low | Different regions (requirements-patch handling vs task-entry, step-patch and rework-index checks); merge conflicts resolved by the parent-side adoption protocol |
| The orchestrator does not list a rewritten `tasks/*.md` as a `replace_own` target, so layer-4 scope verification rejects a docs-only round at run time | Medium | High | Contract text in task0002 states the listing rule; the pre-dispatch decision itself is an open question below |
| Fixture `base_input_digest` drifts from its digest-source | Low | Low | Compute it with the validator's own normalization when authoring the fixture |

## Open Questions

- [ ] Pre-dispatch listing of existing `tasks/*.md`: FR2 lists a rewritten task plan as a `replace_own` target only on rounds that rewrite it, mirroring the VERIFICATION.md / IMPLEMENTATION.md precedent. Neither the precedent nor this feature states how the orchestrator knows, before dispatch, which task plans a round will rewrite.
