# Threat Model: plan-version-bump-per-commit

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md at the full tier (design step skipped).
The feature changes planning-rule text (plan-writing SKILL.md), a
conflict-protocol rule (worktree-task-workflow SKILL.md), two worker input
contracts, two agent prompts, the create-plan and rework-planner dispatch
procedures, and adds regression tests under `tests/`.

Its only new crossing between parties is FR5's dispatch-resolved value: the
orchestrator reads repository-controlled files (presence of the exemption
workflow file, every `.claude-plugin/plugin.json`, the root
`.claude-plugin/marketplace.json`) and places what it derives into the
implementation-planner and rework-planner inputs — repository text
interpolated into an LLM prompt (TB-1). task0003 and task0004 declare
`input-handling` (with `api-contract`) for exactly these documents, which
sets TB-1 to deep.

Not trust boundaries:
- The new rule text in plan-writing SKILL.md and worktree-task-workflow
  SKILL.md (task0001, task0002) is plugin-authored guidance; no data from
  another party crosses into it. Both tasks declare only `config-infra`.
- Implementer commits remain checked by plugin-version-guard, which this
  feature does not change (A5); the feature changes only what plans instruct.
- Plugin directory paths that now enter task `files` pass through the
  existing workflow-patch application rule that rejects absolute paths, `..`
  and NUL; this feature does not alter that rule.
- The regression tests read only repository files and nothing under
  `~/.claude` (NFR3).

Domain consistency: every task declaring one of `auth`, `input-handling`,
`external-io` or `data-persistence` (task0003, task0004) has its documents
listed under TB-1's Boundary files.

## Trust Boundaries

### TB-1: Repository files to planner input (plugin_versioning)
Crossing: repository-controlled content — the presence of `.github/workflows/plugin-version-bump.yml`, plugin names and directory names from `.claude-plugin/plugin.json` files, and entries of the root `.claude-plugin/marketplace.json` — read by the orchestrator and passed as the `plugin_versioning` value into the implementation-planner and rework-planner prompts.
Boundary files: em-workflow/references/contracts/planner-contract.md, em-workflow/references/phases/create-plan-phase.md, em-workflow/agents/implementation-planner.md, em-workflow/references/contracts/rework-planner-contract.md, em-workflow/agents/rework-planner.md, em-workflow/references/rework-task-synthesis.md, em-workflow/skills/develop/SKILL.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A plugin name, directory name or marketplace entry carrying instruction-shaped text reaches the planners through the new dispatch value (FR5) and steers the plan — for example toward dropping the version rules required by FR1, FR2 and FR4 | TM-1 | Both input contracts classify `plugin_versioning` as untrusted input under worker-envelope.md's Untrusted-Input Handling, and restrict it to the exemption boolean, project-relative plugin directory paths, plugin names and the per-plugin marketplace flag, with no other text copied from repository files | task0003 AC-4; task0004 AC-4 | VERIFICATION.md Performance / Security Verification: TM-1 |
