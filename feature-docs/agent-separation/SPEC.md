# Feature: em-workflow Agent Responsibility Separation

## Overview

Restructure the `em-workflow` plugin so that the orchestrator (`/em-workflow:develop`) owns only state transitions, user dialogue, workflow.yaml updates, commits and approval gates, while all investigation, analysis, document authoring and planning run as Task-dispatched subagents (workers). Workers never ask the user; they return structured question packets. Workers that need workflow.yaml changes propose patches instead of writing the file.

The normative, self-contained detailed specification for this feature is `feature-docs/agent-separation/design-input.md` (design revision rev13, 2085 lines). Every requirement below cites the section of that document that defines its details. Where this SPEC and `design-input.md` appear to differ, `design-input.md` is authoritative for mechanism, and this SPEC is authoritative for scope and requirement identity.

## Objectives

- Make every definition under `em-workflow/agents/` actually Task-dispatched, eliminating the "read the definition file and follow it inline" execution form.
- Make the orchestrator the single writer of workflow.yaml.
- Fix the real rework bug: returning `implement` to `pending` with no pending task makes the implement phase spin with nothing to launch.
- Persist dialogue and worker-run state (phase-state) so create-spec and create-plan survive interruption and resume without re-asking answered questions.
- Replace eyeball schema checks with a bundled validation script driven by fixtures.

## User Stories

### US1: Run create-spec interactively with resumable dialogue
As an em-workflow user, I want create-spec to ask me questions through the orchestrator and persist every answer, so that an interrupted session resumes without re-asking what I already answered.

**Acceptance Criteria:**
- [ ] The orchestrator is the only caller of AskUserQuestion; requirements-analyst returns question packets instead.
- [ ] Every answer is persisted to `phase-state/create-spec.yaml` and committed before the worker is re-dispatched.
- [ ] On resume, answered questions are not re-presented.

### US2: Rework from review or verify actually re-runs implementation
As an em-workflow user, I want a rework decision to add real pending tasks before `implement` returns to `pending`, so that the implement phase has something to launch.

**Acceptance Criteria:**
- [ ] All four routes (interactive review, batch review, interactive verify, batch verify) add at least one pending rework task before `implement` is set to `pending`.
- [ ] `workflow[implement].base_commit` is unchanged across rework re-entry.
- [ ] `references/implement-phase.md` states the pending-task precondition for rework re-entry.

### US3: Unattended batch runs decide gates mechanically
As an operator launching `--batch` headlessly, I want every question-packet gate resolved from a gate-ID policy table, so that the run completes without any AskUserQuestion call and reports how each gate was decided.

**Acceptance Criteria:**
- [ ] Every gate expressed as a question packet has an entry in `references/batch-policies.yaml`.
- [ ] Gates not expressed as question packets remain in `references/batch-mode.md`.
- [ ] Unlisted gates that cannot be mapped to an option ID abort when the decision concerns specification change, security, licensing, or an irreversible operation.

### US4: Worker output is machine-validated
As a plugin maintainer, I want worker output, packets, answers, patches and phase-state validated by a bundled script, so that contract drift is caught by exit codes rather than by reading YAML.

**Acceptance Criteria:**
- [ ] `scripts/validate-worker-output.py` returns 0 for valid fixtures and 1 for invalid fixtures.
- [ ] The script returns exit code 2 when PyYAML is unavailable.
- [ ] `tests/test_validate_worker_output.py` runs the fixtures under `python3 -m unittest discover -s tests`.

## Technical Requirements

### Functional Requirements

- **FR1:** Create `references/rework-task-synthesis.md` as the single source of truth for rework task synthesis, covering purpose, applicable modes (interactive/batch × review/verify), inputs, grouping rules, task ID allocation, task plan requirements, metadata derivation, verification coverage rules, related document updates, workflow state transition, invariants, validation, and the execution adapter reference. All four referrers (`references/review-phase.md` interactive and batch rework branches, `skills/develop/SKILL.md` interactive and batch verify rework branches) must reference this document. Details: design-input.md 5.10.

- **FR2:** Add a rework re-entry precondition to `references/implement-phase.md`: at least one pending task must exist in workflow.yaml before `implement` is returned to `pending`. The `completed_at_commit` semantics stay unchanged. Details: design-input.md 3.3, 6.2, 8.1.

- **FR3:** Create `references/contracts/worker-envelope.md` defining the common worker input and output envelope: input fields (`schema_version`, `request_id`, `phase`, `mode`, `project_root`, `integration_worktree`, `feature`, `feature_dir`, `plugin_root`, `workflow_path`, `input_revision`, `task_description`, `prior_packets`, `answers`, `write_policy`, `resolved_input_paths`, `allowed_write_roots`, `output_contract_path`) and output fields (`schema_version`, `request_id`, `worker`, `status`, `input_revision`, `question_packet`, `blocking_reason`, `written_artifacts`, `workflow_patch`, `mode_echo`, `payload`, `warnings`, `report`), the six `status` values with their exclusivity constraints, and the rule that workers must not read outside the explicitly supplied fixed-path inputs and `resolved_input_paths`. The envelope applies only to the five new/refitted workers. Details: design-input.md 2.3, 5.3.

- **FR4:** Create `references/contracts/analyst-contract.md` for requirements-analyst, covering the `analysis_mode` values (`full`, `design_system_detection`), `analysis_scope`, the `analysis_snapshot` payload for `needs_user_input`, the `completed` payload for each mode, the mutual-exclusion rules between modes, the `digest_inputs` set, and the `mode_echo` requirement. Details: design-input.md 5.0 R1, 5.4.1.

- **FR5:** Create `references/contracts/spec-writer-contract.md` for spec-writer, covering `requirements_analysis` and `templates` inputs, the path-level `write_policy` model (`create` / `replace_own` / `replace_authorized` / `preserve` / `extend_only` / `regenerate`, their `expect_digest` requirements and worker behaviour), the protection split between `write_policy.targets` and `allowed_write_roots`, the `spec_index` payload, and the post-conditions on FR/NFR ID format, uniqueness, `tbd_reason`, and the prohibition on the writer inventing requirements the analyst did not produce. Details: design-input.md 5.4.2.

- **FR6:** Create `references/contracts/planner-contract.md` for implementation-planner, covering `planning_inputs`, `write_policy`, the question-packet conditions (TBD, license conflict, existing files), the `completed` output (`written_artifacts`, `workflow_patch`, `payload.task_index`), the `digest_inputs` set, and the prohibition on setting `branch` / `notes` / running status / `completed_at_commit`. Details: design-input.md 5.4.3.

- **FR7:** Create `references/contracts/rework-planner-contract.md` for rework-planner, covering the `rework_source` input, grouping rules, the document update scope table, the verification coverage rules and mandatory `payload.rework_index`, `payload.shared_contract_rationale`, the `rework.spec-change` transition, and the restricted set of conditions under which a packet may be returned. Details: design-input.md 5.4.4.

- **FR8:** Create `references/contracts/designer-contract.md` for designer, covering `design_inputs`, the path-level `write_policy` targets for DESIGN.md / `design-system/tokens.yaml` / `tokens.html` / existing mockups, `allowed_write_roots` for new mockups, the tokens.yaml↔tokens.html linkage via `regenerate`, the `project.design_system.kind` branch table, the exclusion of the two token files from `digest_inputs` under `project_native`, the `payload.design_summary`, and the rules that designer returns neither a question packet nor a workflow patch. Details: design-input.md 4.2, 5.4.5.

- **FR9:** Implement `scripts/validate-worker-output.py` in Python 3 with PyYAML, supporting `--kind` values `worker-result` / `question-packet` / `answers` / `workflow-patch` / `phase-state` and the auxiliary inputs `--packet`, `--answers`, `--workflow`, `--registries`, `--phase-state`, `--input-envelope`, `--digest-source`, `--feature-dir`, `--baseline-dir`, `--dry-run-apply`. It performs structural validation, cross-reference validation, the limited Markdown marker parsing described in the design, and the `--dry-run-apply` patch checks. `--input-envelope` is mandatory for `--kind worker-result` for every worker. Exit codes: 0 pass, 1 validation failure with JSON detail on stdout, 2 execution error including missing PyYAML. No JSON Schema evaluator is implemented. Details: design-input.md 5.11.1, 5.11.2.

- **FR10:** Create `references/fixtures/` containing valid and invalid samples covering, at minimum, one case per branch in the fixture coverage table: `worker-result` per worker and per allowed status (including requirements-analyst `full` and `design_system_detection` separately, plus `mode_echo` missing and mismatched invalids), `question-packet` across the four answer modes and option-count boundaries with `depends_on` / `supersedes`, `answers` valid and invalid per mode, `workflow-patch` for `replace_planning` and `append_rework` with permission-condition, missing-preserve and expected-mismatch invalids, and `phase-state` for each resume status. Details: design-input.md 5.11.5.

- **FR11:** Add `tests/test_validate_worker_output.py` following the repository test convention (Python standard-library `unittest`, invoked via `python3 -m unittest discover -s tests`), which runs `scripts/validate-worker-output.py` against every fixture under `references/fixtures/` and asserts exit code 0 for valid fixtures and 1 for invalid fixtures.

- **FR12:** Create `references/workflow-patch.md` defining the restricted patch format: common fields, the `replace_planning` / `append_rework` operations and their constraints, `tasks_patch` (atomic upsert, `replace_all` permission conditions, `append` provenance), `requirements_patch`, `step_patches` keyed by `step_id`, `preserve` with its permitted vocabulary and per-operation mandatory sets, the sixteen application rules, and the rule that `project` and review summary blocks are not patchable by workers. Generic RFC 6902 JSON Patch is explicitly not adopted. Details: design-input.md 5.5.

- **FR13:** Create `references/phase-state.md` defining the phase-state file layout under `feature-docs/{feature}/phase-state/`, its schema, ID uniqueness and idempotency rules, the permitted `worker_runs[].status` transitions including the terminal `discarded_stale`, `active_request_id` lifecycle and its `discarded_stale` exception, `resolved_input_cache` semantics, the commit procedure with the mandatory `expected_base_tip` argument, the exit-4 recovery procedures for phase-state updates and for worker artifact commits, the `stale_redispatch_count` limit of one consecutive retry, size management, and the legacy-compatibility rules. Details: design-input.md 5.6, 5.12.

- **FR14:** Create `references/question-packet-schema.md` defining the question packet and answer output contracts: packet fields and ID patterns, the `category` vocabulary, question fields including `gate_id`, `answer_mode`, `options`, `depends_on`, `supersedes`, `on_unanswered`, the answer object fields and `source` vocabulary, and answer-mode consistency rules 1–5. `on_unanswered` must have no value that automatically converts an unanswered question into an assumption. Details: design-input.md 5.1, 5.2.

- **FR15:** Create `references/question-resolution.md` defining the shared interactive/batch packet resolution procedure: deduplication order, stable priority sort, `depends_on` gating, the AskUserQuestion presentation limits (max 3 questions per call, max 4 options per question), the batch resolution steps, and the unlisted-gate fallback including the Codex consultation step and the fail-closed rule for specification change, security, licensing and irreversible operations. Details: design-input.md 5.9.

- **FR16:** Create `references/batch-policies.yaml` as the gate-ID-based batch decision SSOT covering exactly the gates expressed as question packets, including all gate IDs referenced by the phase protocols. `rework.spec-change` is intentionally absent so it falls through to the unlisted-gate abort path. Details: design-input.md 5.9.

- **FR17:** Refit `agents/designer.md` to the structured input/output contract: treat workflow.yaml as read-only, return no workflow patch, never commit, honour the path-level `write_policy`, and produce the common envelope output. Change the design step in `skills/develop/SKILL.md` to `Task(subagent_type="em-workflow:designer")`, and add the `project.design_system` cross-product check plus the `design-system.reclassify` gate immediately before dispatch. Details: design-input.md 4.2, 5.4.5, 6.2.

- **FR18:** Refit `agents/implementation-planner.md` to remove AskUserQuestion, return question packets and a workflow patch proposal instead of writing workflow.yaml, and state that the `domains` vocabulary SSOT is `references/review-rules.yaml`. Details: design-input.md 5.4.3, 5.5.6, 6.2.

- **FR19:** Create `references/phases/create-plan-phase.md` covering purpose and ownership, preconditions (including clean integration worktree and the `project.design_system` cross-product check), reconcile on entry, planner dispatch, question loop, packet normalization, planner completion output, the seven validation layers, the machine-checked planning invariants, atomic patch application, and completion/partial-completion handling. Details: design-input.md 5.8.

- **FR20:** Create `agents/requirements-analyst.md` implementing the investigation and question-generation worker per FR4: project context inspection, requirement clarification candidates, command/license detection, design step recommendation, and design system candidate detection, with no file writes, no commits, no AskUserQuestion and no branch/worktree operations. Details: design-input.md 5.4.1.

- **FR21:** Create `agents/spec-writer.md` implementing the document authoring worker per FR5: generate REQUIREMENTS.md (Japanese) and SPEC.md (English) from the analyst's `resolved_requirements`, never write workflow.yaml, never return a question packet. Details: design-input.md 5.4.2.

- **FR22:** Create `references/phases/create-spec-phase.md` covering purpose and ownership, inputs and preconditions, the bootstrap and durable-state boundary (feature identity gate, worktree creation immediately after the feature name is fixed, persistence of every answer), reconcile on entry, the analyst dispatch loop, question normalization, interactive and batch answer handling, spec-writer dispatch, artifact validation, workflow.yaml construction, the mandatory design-system determination step, the command approval gate, completion, the termination conditions with no fixed round limit, and the `progress_fingerprint`-based loop-stop conditions with the three-way stalled gate. Details: design-input.md 5.7.

- **FR23:** Create `agents/rework-planner.md` implementing the rework planning worker per FR7, and connect it as the execution adapter referenced by `references/rework-task-synthesis.md`. Details: design-input.md 5.4.4, 5.10.

- **FR24:** Update `references/batch-mode.md`: move question-packet gates to `references/batch-policies.yaml`, move the rework task synthesis body to `references/rework-task-synthesis.md` and the Codex fallback detail to `references/question-resolution.md`, and retain only the batch decisions that are not expressed as question packets. Details: design-input.md 6.2, 6.3, 6.4.

- **FR25:** Update `references/workflow-schema.md`: make the orchestrator the sole writer of workflow.yaml by removing the upstream-agent exception, document the phase-state sibling directory, state that the `domains` vocabulary SSOT is `review-rules.yaml`, add the normative definition of `completed_at_commit` (the HEAD immediately before the commit that sets the step's status to `completed`) with its applicability to all seven steps, and add the `project.design_system` field with `kind` and `paths`. Details: design-input.md 5.0 R2, 5.5.6, 6.2, 8.3.

- **FR26:** Update the remaining references and templates for the new worker names and contracts: `references/review-phase.md` (reference the rework SSOT and rework-planner from both branches, and document the `needs_rework` update ordering), `references/command-execution-protocol.md` (question packet connection and the `create-spec.command-approval` gate ID), `references/license-compat.md`, `references/impl-skills.yaml`, `references/templates/requirements-document.md`, `references/templates/spec-document.md`, `references/templates/test-readme.md`, `references/templates/task-plan.md` (header reference only; structural markers are unchanged), `skills/plan-writing/SKILL.md` (domains SSOT statement), and `skills/design/SKILL.md` (follow the designer contract change). Details: design-input.md 6.2.

- **FR27:** Update `skills/develop/SKILL.md` to route create-spec, design and create-plan through the phase protocols and Task dispatch, reference the rework SSOT from the verify rework branches, express `completed_at_commit` per the normative definition without changing its semantics, and insert the `project.design_system` backfill branch between step selection and the `in_progress` update, re-reading workflow.yaml and restarting step selection after backfill. Details: design-input.md 5.12, 6.2.

- **FR28:** Delete `agents/requirements-spec-creator.md` after the analyst, spec-writer and create-spec phase protocol are in place, remove the "read the definition file and follow it inline" wording from the develop step table, remove the upstream-agent write exception from `workflow-schema.md`, remove the rework synthesis body from `batch-mode.md`, and remove the per-gate three-way handling inside `implementation-planner.md`'s batch section. No definition that is not Task-dispatched may remain under `agents/`. Details: design-input.md 6.3, 6.4, 8.2.

- **FR29:** Update `README.md` to reflect the worker composition, phase-state, the batch policy SSOT, the PyYAML prerequisite and the `Bash(python3:*)` permission note, and bump `version` and update `description` in `em-workflow/.claude-plugin/plugin.json`. Details: design-input.md 6.2, 10.4.

- **FR30:** Provide the automated verification checks listed in the design: fixture valid/invalid execution, fixture branch coverage against the coverage table, parity between the `agents/*.md` filename set and the repository's `subagent_type` reference set, absence of stale references (`requirements-spec-creator`, "Read してインラインで従う"), gate-ID set comparison between `batch-policies.yaml` and the `gate_id` occurrences in the phase protocols, `domains` vocabulary parity between `review-rules.yaml` and `skills/plan-writing/SKILL.md`, workflow-patch `--dry-run-apply` rejection cases, phase-state reconcile state-table cases, and `input_digest` reproducibility. Details: design-input.md 9.1.

- **FR31:** Implement the scope verification procedure in the phase protocols: require a clean integration worktree before dispatch and abort with the offending paths when it is not clean (no automatic cleaning), take the pre-dispatch snapshot of HEAD SHA, index blob IDs and modes, the untracked list and the `extend_only` key set, compute the worker change set from the index and working-tree layers only, hashing content solely for the paths reported as changed (the clean-worktree precondition makes the index blob IDs carry the tracked working tree's identity, so no whole-tree hashing pass is needed; deletions, mode changes and file/symlink/absent transitions must still be detected), judge permitted scope by splitting changed paths on pre-dispatch existence, remove violations by restoring tracked files from the snapshot blob and trashing untracked violators with `gio` (aborting when `gio` is unavailable), then evaluate HEAD movement and perform the stale path with `reset --hard` and re-dispatch. Record the exclusivity assumption and its scope in the phase protocols and contracts. Details: design-input.md 5.11.3, 8.9.

- **FR32:** Implement legacy feature compatibility: workflow.yaml files without phase-state are handled per the upstream-step status table, and workflow.yaml files without `project.design_system` are backfilled once via a `design_system_detection` analyst dispatch and the `create-spec.design-system` gate before the design or create-plan step is entered. An unknown phase-state `schema_version` (> 1) aborts as a plugin version mismatch. Details: design-input.md 5.12.

### Non-Functional Requirements

- **NFR1 - Ownership:** Only the orchestrator writes workflow.yaml. No worker definition contains an instruction to write it, and every commit that changes workflow.yaml originates from the orchestrator. Details: design-input.md 4.1, 8.3.

- **NFR2 - Dialogue fidelity:** create-spec has no fixed round limit; loop termination is defined by `progress_fingerprint` differencing; unresolved items are never converted to assumptions automatically; the stalled gate offers continue / record TBD / abort. Details: design-input.md 5.7, 8.4.

- **NFR3 - Resumability:** create-spec and create-plan resume from phase-state after interruption without re-presenting answered questions; phase-state is committed to the integration branch; workflow.yaml contains no dialogue history; exit-4 recovery upserts the retained answer idempotently onto the refreshed phase-state. Details: design-input.md 5.6, 8.6.

- **NFR4 - Batch fail-closed:** In batch mode AskUserQuestion is never called. Unlisted gates that cannot be mapped to an option ID abort when the decision concerns specification change, security, licensing or an irreversible operation. This is an intentional behaviour change from the current `batch-mode.md` "continue on the success path" rule. Batch reports include each automatic answer's `source` and `resolution_note`. Details: design-input.md 5.9, 8.5.

- **NFR5 - Runtime dependencies:** Python 3 with PyYAML is required for `scripts/validate-worker-output.py`; its absence yields exit code 2 with a message naming PyYAML. `gio` is optional; without it, untracked scope violators are neither deleted nor moved and the phase aborts with the offending paths listed. Both, plus the `Bash(python3:*)` permission note, are documented in `README.md`; `test/README.md` is updated so its no-external-dependency rule is scoped to test code rather than contradicting the runtime dependency. Details: design-input.md 2.4, 10.4.

- **NFR6 - Single source of truth:** Each rule has exactly one SSOT (worker I/O structure in `references/contracts/*.md`, its machine validation in the script plus fixtures, patch operations in `workflow-patch.md`, phase-state in `phase-state.md`, batch gate resolution in `batch-policies.yaml` plus `question-resolution.md`, rework synthesis in `rework-task-synthesis.md`, `domains` in `review-rules.yaml`, impl skills in `impl-skills.yaml`, `completed_at_commit` in `workflow-schema.md`). Phase protocols and agent prompts carry path references only, never copied values. Details: design-input.md 10.5.

- **NFR7 - Hook compatibility:** New worker prompts must not use a `# Task assignment` heading, because `queue_agent_index.py` and `queue_launch_guard.py` use that block as a fallback when `subagent_type` is absent. The six existing hooks require no logic changes. Details: design-input.md 6.5.

- **NFR8 - Path safety:** All compared paths are normalized relative to the project root; absolute paths are accepted only when realpath resolution is contained under the project root; paths yielding `..` segments after relativization are rejected; containment is judged on path segments rather than string prefixes; a path whose root or any segment is a symlink is a violation; comparison is case-sensitive and post-normalization collisions on case-insensitive filesystems are violations. Details: design-input.md 5.11.3, 8.9.

- **NFR9 - Discovery cost:** `**/` globs are resolved once per phase run and cached in `resolved_input_cache`, invalidated by `generation_digest` rather than HEAD; re-resolution is triggered only by a new phase run, a worker writing under a candidate path, or a worktree refresh after exit 4; directory candidates enumerate only the listed extensions; discovery stops at 500 files or 5 MB total with `truncated: true`, after which interactive asks for manual specification and batch aborts regardless of the route's default policy. Details: design-input.md 5.0 R1.

## Implementation Approach

### Architecture

**Responsibility split (target state):**

```
┌──────────────────────────────────────────────────────────┐
│ Orchestrator  (/em-workflow:develop, phase protocols)    │
│  state transitions · AskUserQuestion · workflow.yaml     │
│  commits · approval gates · worker output validation     │
│  branch/worktree operations · glob resolution            │
└───────────────┬──────────────────────────────────────────┘
                │ Task dispatch (common envelope)
┌───────────────▼──────────────────────────────────────────┐
│ Workers                                                   │
│  requirements-analyst · spec-writer · designer            │
│  implementation-planner · rework-planner                  │
│  read-only on workflow.yaml · no commits · no Ask         │
└──────────────────────────────────────────────────────────┘
```

**Execution form (target state):**

| Definition | Form | Questions | workflow.yaml |
|---|---|---|---|
| requirements-analyst | Task | returns packet | read only |
| spec-writer | Task | none | read only |
| designer | Task | none | read only (no patch) |
| implementation-planner | Task | returns packet | proposes patch |
| rework-planner | Task | conditional packet | proposes patch |
| implementer / reviewer / codex-reviewer / review-editor / gitignore-guard / git-setup-guard | Task (unchanged) | none | untouched |

### Data Flow

```
Orchestrator → resolve globs → compute input_digest → snapshot → Task dispatch
             ← worker result (envelope) ←
             → validate (script) → scope check → commit artifacts
             → apply workflow patch → update step status → commit
```

### Dependencies

**Internal Dependencies:**
- `scripts/commit-docs.sh`: unchanged; callers must pass `expected_base_tip` as the third argument.
- `scripts/merge-task.sh`: unchanged; implement phase only.
- Existing hooks (`queue_*`, `bash_guard`): unchanged, subject to NFR7.

**External Dependencies:**
- Python 3 with PyYAML: required by `scripts/validate-worker-output.py`.
- `gio`: optional, used to trash untracked scope violators.
- Codex CLI via `scripts/run_codex_exec.sh`: optional, used for the batch unlisted-gate fallback.

### File Structure

```
em-workflow/
├── agents/
│   ├── requirements-analyst.md        # new
│   ├── spec-writer.md                 # new
│   ├── rework-planner.md              # new
│   ├── designer.md                    # refit
│   ├── implementation-planner.md      # refit
│   └── requirements-spec-creator.md   # deleted
├── references/
│   ├── rework-task-synthesis.md       # new
│   ├── question-packet-schema.md      # new
│   ├── question-resolution.md         # new
│   ├── phase-state.md                 # new
│   ├── workflow-patch.md              # new
│   ├── batch-policies.yaml            # new
│   ├── contracts/                     # new (6 files)
│   ├── fixtures/                      # new
│   └── phases/                        # new (create-spec-phase.md, create-plan-phase.md)
├── scripts/
│   └── validate-worker-output.py      # new
└── skills/develop/SKILL.md            # rewired
tests/
└── test_validate_worker_output.py     # new
```

## Test Scenarios

### Unit Tests
- [ ] TS-1: `validate-worker-output.py` returns 0 for every valid fixture and 1 for every invalid fixture (FR9, FR10, FR11).
- [ ] TS-2: Answer-mode consistency rules 1–5 reject the invalid answer fixtures (FR9, FR14).
- [ ] TS-3: `--dry-run-apply` rejects stale `base_input_digest` / `base_workflow_blob`, duplicate patch IDs, `expected` mismatch, `replace_all` applied after implementation started, and `append_rework` missing `workflow.implement.base_commit` from `preserve` (FR9, FR12).
- [ ] TS-4: requirements-analyst `design_system_detection` output containing `resolved_requirements` is rejected; missing or mismatched `mode_echo` is rejected; omitting `--input-envelope` for `--kind worker-result` returns exit code 2 (FR4, FR9).
- [ ] TS-5: Phase-state fixtures for each resume status validate successfully, and `resolved_at_generation` greater than `generation` is rejected (FR13).
- [ ] TS-6: `import yaml` failure yields exit code 2 with a message naming PyYAML (FR9, NFR5).

### Integration Tests
- [ ] TS-7: The `agents/*.md` filename set equals the repository's `subagent_type` reference set (FR28, FR30).
- [ ] TS-8: No occurrence of `requirements-spec-creator` or "Read してインラインで従う" remains in the repository (FR28, FR30).
- [ ] TS-9: The gate-ID set in `batch-policies.yaml` covers every `gate_id` used by the phase protocols, and `rework.spec-change` is absent (FR16, FR30).
- [ ] TS-10: The `domains` vocabulary in `review-rules.yaml` matches the listing in `skills/plan-writing/SKILL.md` (FR26, FR30).
- [ ] TS-11: `input_digest` computed twice from identical inputs is identical (FR9, FR30).

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] TS-12: A small feature (1–2 tasks) completes interactively through every phase (FR17–FR23, FR27).
- [ ] TS-13: The same feature completes under `--batch` with zero AskUserQuestion calls (FR16, NFR4).
- [ ] TS-14: Interactive review rework adds pending tasks and the implement phase launches them (FR1, FR2, FR23).
- [ ] TS-15: Batch review rework does the same via the policy table (FR1, FR16).
- [ ] TS-16: Interactive verify rework does the same (FR1, FR27).
- [ ] TS-17: Batch verify rework does the same (FR1, FR16, FR27).
- [ ] TS-18: create-spec interrupted mid-dialogue resumes without re-presenting answered questions (FR22, NFR3).
- [ ] TS-19: create-plan interrupted during worker dispatch resumes from phase-state (FR19, NFR3).
- [ ] TS-20: Choosing specification change during rework returns create-spec to `needs_update` without creating tasks (FR7, FR23).

### Edge Cases
- [ ] TS-21: spec-writer receiving an existing SPEC.md whose digest does not match returns `blocked` (FR5).
- [ ] TS-22: Batch encountering a digest-mismatched existing artifact follows `preserve_and_reuse`, continuing when post-conditions hold and aborting when they do not (FR16, NFR4).
- [ ] TS-23: A concurrent process advances the integration branch during worker dispatch; the scope comparison runs first, violations are removed, then the worktree is refreshed and re-dispatched, and the concurrent merge is not reported as a scope violation (FR31, NFR8).
- [ ] TS-24: A dirty integration worktree aborts the phase before dispatch with the offending paths listed and nothing cleaned automatically (FR31).
- [ ] TS-25: `kind: none` with existing token files triggers the `design-system.reclassify` gate and resumes from the same step; `kind: em_workflow` with tokens.yaml absent and tokens.html present aborts before dispatch (FR8, FR17).
- [ ] TS-26: Design system candidate discovery exceeding 500 files or 5 MB asks for manual specification interactively and aborts in batch (FR32, NFR9).
- [ ] TS-27: A workflow.yaml without `project.design_system` is backfilled before the step is set to `in_progress`, and step selection restarts afterwards (FR32).
- [ ] TS-28: Two consecutive exit-4 responses to an artifact commit set the phase to `failed`; the first records `discarded_stale` and increments `stale_redispatch_count` in the same commit, before re-dispatch (FR13).
- [ ] TS-29: A symlinked path segment leading outside the project root is detected as a violation (FR31, NFR8).
- [ ] TS-30: `gio` unavailable leaves untracked violators in place and aborts the phase with their paths listed (FR31, NFR5).

### Performance Tests
Not applicable; the only cost constraint is the discovery cap in NFR9, verified by TS-26.

## Security Considerations

- **Input Validation:** Worker output is validated structurally and by cross-reference before any state change; the orchestrator never silently corrects worker output beyond mechanical ordering and digest recomputation.
- **Path Traversal Prevention:** Path normalization, containment on segments, rejection of `..`, symlink rejection, and case-sensitive comparison per NFR8.
- **Untrusted Advisor Output:** Codex consultation output is treated as untrusted; commands are never executed and file contents are never adopted verbatim from it.
- **Fail-Closed Automation:** Batch decisions concerning specification change, security, licensing or irreversible operations abort rather than guessing (NFR4).
- **Secret Scanning:** Unchanged; the gitleaks pre-commit hook installed by the existing git-setup gate continues to apply.

## Error Handling

Failure classification and handling follow design-input.md 5.11.4: transient (one re-dispatch with identical input), stale (scope procedure then re-dispatch with a new request ID), correctable-schema (one re-dispatch with the validator error attached), scope violation (remove then abort), semantic invariant (one re-dispatch with the concrete diff), repeated failure (set the step to `failed` or `needs_update` and abort), user-decision required (convert to a question packet), irrecoverable (abort).

## Success Criteria

- [ ] All functional requirements are implemented and their cited design-input.md sections are reflected in the produced files.
- [ ] All test scenarios pass.
- [ ] Security requirements are satisfied.
- [ ] Documentation is complete (`README.md`, `test/README.md`, plugin description).
- [ ] Code review is completed.
- [ ] The acceptance conditions in design-input.md 8.1 through 8.9 are met.

## Open Questions

None. All clarification points were resolved during create-spec.

## Assumptions

- The design document `design-input.md` is copied into `feature-docs/agent-separation/` because the repository's `tmp/` directory is gitignored and would therefore be invisible inside the integration and task worktrees. It is the normative detailed specification for this feature.

## References

- Detailed specification (normative): `feature-docs/agent-separation/design-input.md`
- Requirements document: `feature-docs/agent-separation/REQUIREMENTS.md`
- Test conventions: `test/README.md`
