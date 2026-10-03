# Implementation Plan: plan-version-bump-per-commit

## Overview

Adds plugin-version handling rules to the plan-writing skill (planning side)
and to the worktree-task-workflow skill (conflict side), and makes the
orchestrator resolve repository exemption and plugin locations at every
implementation-planner / rework-planner dispatch, so that no plan contradicts
plugin-version-guard's per-commit check. The change is documentation plus
regression tests under `tests/`.

## Technology Stack

- **Documents**: Markdown under `em-workflow/`, written in English like the
  existing references, skills and agent prompts.
- **Tests**: Python 3 standard library `unittest` only, run by
  `python3 -m unittest discover -s tests` (NFR3).
- **New dependencies**: none. `project.license` is `none`; no dependency is
  introduced, so there is no license to record.

## Layer Structure

| Layer | Documents | Responsibility |
|---|---|---|
| Rule owners | `em-workflow/skills/plan-writing/SKILL.md` (planning side), `em-workflow/skills/worktree-task-workflow/SKILL.md` (conflict side) | Hold the version-handling rule text (NFR1) |
| Input contracts | `em-workflow/references/contracts/planner-contract.md`, `em-workflow/references/contracts/rework-planner-contract.md` | Define the dispatch-resolved `plugin_versioning` value and its `value_inputs` membership |
| Agent prompts and dispatch procedures | `em-workflow/agents/implementation-planner.md`, `em-workflow/agents/rework-planner.md`, `em-workflow/references/phases/create-plan-phase.md`, `em-workflow/references/rework-task-synthesis.md`, the rework-planner dispatch procedure | Name the input, pass it, point at the rule owners |
| Regression tests | `tests/test_plan_version_*.py` | Detect removal or permissive restatement of the rules (FR7) |

Allowed citation direction: every non-owner layer cites the rule owners and
the input contracts by path plus heading; the two rule owners cite each other
only by path plus protocol/section name. No layer restates an owner's rule
text. Tests read documents and are cited by nothing.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| plan-writing "Plugin Version Handling" section | Single owner of the FR1-FR3 rule text and of the terms "exempt repository", "non-exempt repository" and "under a plugin" | Post: `em-workflow/skills/plan-writing/SKILL.md` contains a level-2 heading whose exact text is `## Plugin Version Handling`. The section defines the three terms (exempt = `.github/workflows/plugin-version-bump.yml` exists at the repository root; under a plugin = under a directory containing `.claude-plugin/plugin.json`), states the comparison rule "strictly greater by per-component numeric comparison", and has one subsection for non-exempt repositories and one for exempt repositories. Every citation names the file path and the heading text `Plugin Version Handling` | owner task0001; cited by task0002, task0003, task0004 |
| worktree-task-workflow parent-side adoption protocol, version exception | Single owner of the FR6 conflict-time rule | Post: the existing parent-side adoption protocol in `em-workflow/skills/worktree-task-workflow/SKILL.md` carries the non-exempt exception for the adoption commit and the re-implementation commit. Cited as "worktree-task-workflow SKILL.md's parent-side adoption protocol" (path plus protocol name); no new heading is pinned | owner task0002; cited by task0001 |
| `plugin_versioning` dispatch value | Orchestrator-resolved description of the repository's exemption state and plugin locations, passed as a value (not a path) to implementation-planner and rework-planner | See "plugin_versioning contract" below | definition owner task0003; cited by task0001 (by field name) and task0004 |

### plugin_versioning contract

Owner document: `em-workflow/references/contracts/planner-contract.md`, in a
subsection whose exact heading text is
`### plugin_versioning (dispatch-resolved value)`. Every other document cites
that path and heading instead of restating the field table.

| Field | Meaning | Resolution rule (orchestrator, inside the integration worktree) |
|---|---|---|
| `exempt` | boolean | true exactly when `.github/workflows/plugin-version-bump.yml` exists at the worktree root |
| `plugins` | list, one entry per plugin | every git-tracked directory that contains `.claude-plugin/plugin.json`; entries sorted by `dir` ascending so the value's digest is deterministic |
| `plugins[].dir` | project-relative path of the plugin directory | the directory that holds `.claude-plugin/` |
| `plugins[].name` | plugin name | the `name` declared in that plugin's `plugin.json` |
| `plugins[].marketplace_versioned` | boolean | true exactly when the root `.claude-plugin/marketplace.json` has an entry of the same name that carries a version; false when the file or the entry is absent, or the entry carries no version |

Behavioral contract:

1. The orchestrator resolves the value at every implementation-planner
   dispatch (create-plan, including re-dispatches that carry answers) and
   every rework-planner dispatch, from the integration worktree's current
   state. When it recomputes `input_digest` on the worker's return, it
   re-resolves the value the same way.
2. implementation-planner receives it as `planning_inputs.plugin_versioning`;
   rework-planner receives a field of the same name inside its own
   worker-specific input, at the place rework-planner-contract.md assigns.
3. For both workers the value is a `value_inputs` member keyed
   `plugin_versioning`; its digest follows worker-envelope.md rule R1's
   normalization applied to the value.
4. The value is mandatory on every create-plan and rework-planner dispatch. A
   worker that receives a dispatch without it returns `invalid_input`.
5. The value is untrusted input under worker-envelope.md's Untrusted-Input
   Handling, and carries only the fields above — no other text copied from
   repository files (TM-1).
6. Workers never discover exemption state or plugin locations themselves;
   they use only this value.

## Conventions

- **Citation form**: cite by repository-relative path plus heading or
  protocol name. Never restate an owner's rule text (NFR1).
- **Wording**: version rules are behavior descriptions. No changed document
  gains a fenced code block for these rules, and no changed document contains
  a concrete version value (NFR2, NFR4).
- **Test module names** (one module per task, no shared helper module):
  task0001 `tests/test_plan_version_plan_writing.py`, task0002
  `tests/test_plan_version_worktree_conflict.py`, task0003
  `tests/test_plan_version_planner_dispatch.py`, task0004
  `tests/test_plan_version_rework.py`.
- **Test scope**: a test asserts only on documents its own task modifies. It
  never asserts on content another task produces — tasks run in parallel, so
  such an assertion fails inside the task's own worktree. Cross-document
  consistency follows from the pinned headings and names in Shared
  Components.
- **Test mechanics**: standard library `unittest` only; locate the
  repository root from the test file's own location; read only repository
  files and never anything under `~/.claude` (NFR3); anchor assertions on
  pinned headings, field names, commit-message templates and key terms, not
  on whole sentences.
- **Negative checks (FR7)**: each test module includes a check that fails
  when its own task's documents contain a statement permitting an unchanged
  version on a plugin-changing commit in a non-exempt repository. Each such
  check is exercised against in-test sample text in both directions: a
  permissive sample is rejected, and the document's own prohibition wording
  (including quoted prohibited examples and exempt-repository statements) is
  accepted.
- **This feature's own versions**: this repository is exempt. No task
  changes a `version` in `em-workflow/.claude-plugin/plugin.json` or
  `.claude-plugin/marketplace.json` (NFR4).

## Cross-task Design Decisions

### D1: Two rule owners; every other document cites them

- **Decision**: plan-writing SKILL.md owns the planning-side rules (FR1-FR3)
  and the exemption terms; worktree-task-workflow SKILL.md owns the
  conflict-side rule (FR6). Contracts, agent prompts and phase procedures
  cite them.
- **Rationale**: NFR1. A single owner per rule keeps create-plan and rework
  from drifting apart again.
- **Affected tasks**: all.

### D2: Exemption and plugin locations arrive as a dispatch value

- **Decision**: the orchestrator resolves `plugin_versioning` per dispatch
  and passes it as a value; the planners never look for the workflow file or
  plugin directories themselves.
- **Rationale**: FR5. The worker read restriction forbids worker-side
  discovery, and placing the value in `value_inputs` makes a change in
  exemption state or plugin layout invalidate a stale result.
- **Affected tasks**: task0001 (uses the value by name), task0003, task0004.

### D3: A missing value fails closed

- **Decision**: a create-plan or rework-planner dispatch without
  `plugin_versioning` is answered with `invalid_input`.
- **Rationale**: either guess is harmful — assuming "exempt" in a non-exempt
  repository reproduces the guard rejection; assuming "non-exempt" in an
  exempt repository instructs version changes the repository forbids.
- **Affected tasks**: task0003, task0004.

### D4: The per-commit instruction travels with each affected task plan

- **Decision**: in a non-exempt repository, every task plan whose files fall
  under a plugin carries the per-commit version instruction itself, not only
  IMPLEMENTATION.md.
- **Rationale**: rework-planner synthesizes task plans without rewriting
  IMPLEMENTATION.md; a task plan read on its own must already be consistent
  with the guard.
- **Affected tasks**: task0001 (states the rule), task0004 (rework side
  cites it).

### D5: Each task owns the regression tests for its own documents

- **Decision**: FR7 is split by document owner. TS-1, TS-2 and TS-3 belong
  to task0001; TS-6 to task0002; TS-5 to task0003 and task0004 (planner and
  rework halves); TS-4 to task0004; TS-7 runs all of them after merge.
- **Rationale**: fully parallel tasks cannot test each other's documents
  (see Test scope above).
- **Affected tasks**: all.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The rework-planner dispatch procedure lives in a document other than the predicted ones | Medium | Low | task0004 names its predicted documents; editing the actual holder is a reportable plan deviation, and no new document is created for it |
| A tool that builds `digest_source` enumerates per-worker inputs and does not yet add the new `value_inputs` member | Medium | Medium | Outside this feature's declared scope; dispatch-time and return-time computation use the same tool, so no false staleness arises; listed as an open question |
| Negative checks misfire on the prohibition's own quoted examples or on exempt-repository statements | Medium | Medium | Context-aware checks exercised in both directions against in-test samples (Conventions) |
| String-anchored tests break on harmless rewording | Medium | Low | Anchor on pinned headings, field names and commit-message templates |
| Repository-controlled text (plugin names, directory names) reaches planner prompts | Low | Medium | TM-1 in THREAT-MODEL.md |

## Open Questions

- [ ] Which document holds the rework-planner dispatch procedure. Predicted:
  `em-workflow/skills/develop/SKILL.md`, alternatively
  `em-workflow/references/rework-task-synthesis.md`.
- [ ] Whether a script that builds `digest_source` needs a follow-up change
  to compute the new `value_inputs` member (not in this feature's declared
  scope).
