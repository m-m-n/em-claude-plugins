# Implementation Plan: em-workflow Agent Responsibility Separation

## Overview

Restructure the `em-workflow` plugin so the orchestrator owns state transitions, dialogue, workflow.yaml writes, commits and approval gates, while investigation, authoring and planning run as Task-dispatched workers that return structured envelopes. The deliverables are protocol documents, agent definitions, two Python tooling scripts and their tests.

## Technology Stack

- **Markdown**: protocol documents, contracts, agent definitions, phase protocols. These are the primary product — they are prompts and specifications read by Claude Code, not code.
- **YAML**: `references/batch-policies.yaml` (gate policy SSOT); fixture and schema examples embedded in documents.
- **Python 3 + PyYAML**: `em-workflow/scripts/validate-worker-output.py` (worker output validation) and `em-workflow/scripts/check-plugin-invariants.py` (repository invariant checks). PyYAML is a new runtime dependency for the plugin; it is NOT a test dependency.
- **Python standard-library `unittest`**: all tests, run by `python3 -m unittest discover -s tests`.

## Normative source

`feature-docs/agent-separation/design-input.md` (design revision rev13) is the normative detailed specification for every deliverable in this feature. Each task plan cites the sections it implements. **Because that document is committed on the integration branch, every task worktree contains it.** This is what makes the tasks worktree-independent: a task never needs a sibling task's output to know a shared structure, because the shared structure is defined in `design-input.md`, not in the sibling's deliverable.

When `design-input.md` and this plan appear to differ on mechanism, `design-input.md` wins. When they differ on which task owns a file, this plan wins.

## Layer Structure

| Layer | Contents | Depends on |
|-------|----------|------------|
| Schema layer | `worker-envelope.md`, `question-packet-schema.md`, `workflow-patch.md`, `phase-state.md` | design-input.md only |
| Contract layer | `contracts/*-contract.md` (5 worker contracts) | schema layer (by reference) |
| Policy layer | `question-resolution.md`, `batch-policies.yaml`, `rework-task-synthesis.md` | schema layer (by reference) |
| Worker layer | `agents/*.md` | contract layer (by reference) |
| Orchestration layer | `references/phases/*.md`, `skills/develop/SKILL.md` | all of the above (by reference) |
| Tooling layer | `scripts/validate-worker-output.py`, `scripts/check-plugin-invariants.py` and their tests | schema + contract layers (by reference) |

Dependency direction is strictly downward, and every dependency is expressed as a **path reference**, never as a copied value (NFR6). A document in a higher layer states "see `references/…`" and does not restate the structure.

## Shared Components

Every cross-task shared structure is defined in `design-input.md`. The table below pins which section is authoritative and which task owns the document that renders it, so that a task consuming a structure never has to read the producing task's plan.

| Component | Responsibility | Contract (normative source) | Used by tasks |
|-----------|----------------|-----------------------------|---------------|
| Worker input/output envelope | Common dispatch input and result shape for the five in-scope workers; six `status` values with exclusivity constraints | design-input.md 5.3 | task0001 (owns doc), task0006, task0007, task0008, task0009, task0010, task0011 |
| Question packet / answer | Question request objects returned by workers; answer objects produced by the orchestrator; answer-mode consistency rules 1–5 | design-input.md 5.1, 5.2 | task0001 (owns doc), task0005, task0006, task0007, task0008, task0009, task0010, task0011 |
| Workflow patch | `replace_planning` / `append_rework` operations, `tasks_patch` / `requirements_patch` / `step_patches` / `preserve`, sixteen application rules | design-input.md 5.5 | task0002 (owns doc), task0007, task0008, task0009, task0010, task0011 |
| phase-state | Persistence schema, ID uniqueness and idempotency, `worker_runs[].status` transitions, `active_request_id` lifecycle, `resolved_input_cache`, exit-4 recovery, resume decision table, legacy compatibility | design-input.md 5.6, 5.12 | task0003 (owns doc), task0008, task0011, task0012 |
| `input_digest` (rule R1) | Normalized-JSON sha256 over `digest_source`; per-worker `digest_inputs` sets; orchestrator-side glob resolution; `resolved_input_cache`; discovery caps | design-input.md 5.0 R1 | task0003, task0006, task0007, task0008, task0011, task0012, task0014 |
| `completed_at_commit` (rule R2) | The HEAD immediately before the commit that sets a step's status to `completed`; applies to all seven steps | design-input.md 5.0 R2 | task0011, task0012, task0013 |
| `write_policy` | Path-level protection: six actions, `expect_digest` requirements, the split between `targets` (existing-file protection) and `allowed_write_roots` (new-file directories) | design-input.md 5.4.2 | task0006, task0007, task0008, task0009, task0010, task0011 |
| `project.design_system` | `kind` (`project_native` / `em_workflow` / `none`) + `paths`; resolution rules; the kind × token-existence cross-product table; the `design-system.reclassify` gate; backfill | design-input.md 5.0 R1, 5.4.5, 5.7 step 11a, 5.12 | task0007, task0010, task0011, task0012, task0013 |
| Gate IDs | The identifier joining a question to a batch policy; the complete set used across phases | design-input.md 5.7, 5.8, 5.9 | task0005 (owns policy file), task0011, task0012, task0014 |
| Scope verification | Clean-worktree precondition, snapshot contents, index+working-tree-only change set, permission judgement, violation removal, stale handling, exclusivity assumption | design-input.md 5.11.3 | task0011 (owns procedure), task0012, task0006, task0007 (contracts state the assumption) |
| Rework synthesis contract | Grouping, task ID allocation, metadata derivation, `rework_index` coverage rules, state transition ordering, eleven invariants | design-input.md 5.10, 5.4.4 | task0004 (owns doc), task0007, task0009, task0012 |
| Validation CLI | `--kind` values, auxiliary arguments, exit codes 0/1/2, the limited Markdown marker parsing | design-input.md 5.11.1 | task0008 (owns script), task0011, task0012 |

## Conventions

- **Naming**: new reference documents use the existing kebab-case `references/*.md` convention. Contracts live under `references/contracts/`, phase protocols under `references/phases/`, fixtures under `references/fixtures/`. Agent definitions keep the existing `agents/<name>.md` form with the standard frontmatter (`name`, `description`, `model`, `effort`, `tools`, optional `skills`).
- **Plugin-root references**: documents refer to sibling plugin files as `${CLAUDE_PLUGIN_ROOT}/...`, matching the existing corpus.
- **Language**: protocol documents, contracts and agent prompts follow the existing corpus — English for structure and rules, Japanese where the existing document is Japanese or where the text is user-facing output. Do not translate a document that is currently in one language into the other.
- **Frontmatter constraint (NFR7)**: no new worker prompt may contain a `# Task assignment` heading, because `queue_agent_index.py` and `queue_launch_guard.py` fall back to that block when `subagent_type` is absent.
- **No value duplication (NFR6)**: a rule has exactly one SSOT; other documents carry a one-line summary plus a path reference. Reviewers treat a restated table as a defect.
- **Error handling policy**: worker-facing failures are classified per design-input.md 5.11.4; documents state the classification and the number of permitted re-dispatches rather than inventing new recovery paths.
- **Script exit codes**: both Python scripts use 0 = pass, 1 = check failure with machine-readable detail on stdout, 2 = execution error (missing dependency, unreadable input).
- **Tests**: every test file is `tests/test_*.py`, standard-library `unittest`, isolated via temporary directories, never touching real `~/.claude` state (per `test/README.md`).

## Cross-task Design Decisions

### D1: `design-input.md` is the shared contract carrier

Rather than pinning each shared structure inside this document, the design document itself is committed to the integration branch and cited by section. This keeps IMPLEMENTATION.md thin as the plan-writing rules require, guarantees every task worktree has the authoritative structure, and removes the need for any task to read a sibling's deliverable.

Affected tasks: all.

### D2: One file has exactly one owning task

The file sets of the fourteen tasks are pairwise disjoint. Tasks run fully in parallel and merge conflicts are resolved by parent-side adoption, which costs a re-implementation; disjoint ownership avoids that cost entirely. A task that discovers it needs to change a file owned by another task reports a plan deviation rather than editing it.

Affected tasks: all.

### D3: The validation script, its fixtures and its tests are one task

The script's structural rules and the fixture corpus are two renderings of the same rule set (design-input.md 10.5 names this as the drift risk to be controlled by fixtures). Splitting them across tasks would create a contract that is, in effect, the entire validator behaviour. They are therefore implemented together in task0008, with the fixture coverage table (design-input.md 5.11.5) as the acceptance boundary.

Affected tasks: task0008.

### D4: Repository invariant checks are a script tested against synthetic trees

The checks in design-input.md 9.1 (agent/dispatch parity, stale references, gate-ID coverage, `domains` parity) assert properties of the fully integrated repository, which no single task worktree exhibits. They are therefore implemented as `em-workflow/scripts/check-plugin-invariants.py`, whose unit tests exercise the check logic against synthetic directory trees built in temporary directories, so the task is testable in isolation. The authoritative run against the real repository is a verify-phase step recorded in VERIFICATION.md.

Affected tasks: task0014, and the verify phase.

### D5: The batch fail-closed change is intentional and localized

design-input.md 5.9 changes the current "unknown gate continues on the success path" behaviour to abort for specification, security, licensing and irreversible decisions. This is a deliberate behaviour change, not a regression, and it is expressed in exactly two places: the unlisted-gate fallback in `references/question-resolution.md` and the retained decisions in `references/batch-mode.md`. No other document restates it.

Affected tasks: task0005.

### D6: The old create-spec agent is deleted only in the sweep task

`agents/requirements-spec-creator.md` is removed by task0013 together with the stale-reference sweep, after task0009 and task0011 have created its replacements. Because tasks are parallel, the integration branch is transiently inconsistent; this is accepted per design-input.md 10.1, which states the plugin does not operate until the whole change lands.

Affected tasks: task0013, task0009, task0011.

### D7: PyYAML dependency documentation is split by document role

`README.md` gains the prerequisite and the `Bash(python3:*)` permission note; `test/README.md` is amended so its no-external-dependency rule is scoped to test code and does not contradict the plugin's runtime dependency. Both edits belong to the sweep task so the two statements are written together and stay consistent.

Affected tasks: task0013.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A contract document and the validator drift | Medium | High | D3 keeps them in one task; fixtures are the acceptance boundary; task0014's gate-ID and vocabulary checks catch cross-document drift |
| A task restates a structure instead of referencing it | Medium | Medium | NFR6 stated as a convention; reviewers treat restatement as a defect; task0013 sweeps for duplicated tables |
| Transient inconsistency on the integration branch during parallel implementation | High | Medium | Accepted per design-input.md 10.1; the invariant script and the verify phase run only after all tasks merge |
| Gate IDs in phase protocols diverge from `batch-policies.yaml` | Medium | High | task0014's gate-ID set comparison; both sides cite design-input.md 5.9 as the source |
| The validator's Markdown marker parsing breaks on existing templates | Medium | Medium | Markers are the existing template structures (design-input.md 5.11.1); task0008 tests parsing against the real `references/templates/task-plan.md` structure |
| A worker prompt accidentally uses a `# Task assignment` heading | Low | High | NFR7 stated as a convention; task0014 checks for it |
| Documents grow large enough to exceed a single implementer session | Medium | Medium | Fourteen tasks sized to one coherent document group each; acceptance criteria kept at or below seven per task |

## Open Questions

- [ ] None outstanding. All create-spec clarification points were resolved; see REQUIREMENTS.md 14.1.
