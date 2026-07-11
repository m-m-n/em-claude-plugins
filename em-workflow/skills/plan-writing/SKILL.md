---
name: plan-writing
description: 実装計画・タスク分割の執筆規則（em-workflow implementation-planner 静的プリロード用）。コード禁止規則、薄い IMPLEMENTATION.md と VERIFICATION.md のテンプレート、タスク分割規則（worktree 独立性 / files 予測 / インターフェース契約）、complexity・domains の判定基準、保存前セルフチェックリストを定義します。
user-invocable: false
---

# Plan Writing Guide (em-workflow planner preload)

## Absolute Rule: No Concrete Code

**Plans describe WHAT to build and contracts, NEVER HOW to code it.**

Allowed: function signatures with pre/postconditions, diagram-convertible
numbered flows, behavioral condition descriptions ("if X then Y behavior"),
component responsibility tables.

Not allowed: language-specific code blocks, specific library/API calls
(`filepath.Base`, `tea.Cmd`, `Channel<Vec<u8>>`, ...), copy-paste-ready
snippets, struct/enum definitions, exhaustive step-by-step implementation
order.

Conversion example: `filepath.Base(p.path)` → "extract last segment of path".

## IMPLEMENTATION.md (thin, cross-task ONLY)

Contains ONLY decisions that two or more tasks share. Per-task content
belongs in tasks/taskNNNN.md — if a section applies to a single task, move it
there.

```markdown
# Implementation Plan: {Feature Name}

## Overview
{1-2 sentences}

## Technology Stack
- **Language / Framework / Key libraries**: {name - purpose}

## Layer Structure
{layers, their responsibilities, allowed dependency directions}

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|

## Conventions
{naming, error-handling policy, logging policy — cross-task rules only}

## Cross-task Design Decisions
{decision, rationale, affected tasks — one subsection per decision}

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|

## Open Questions
- [ ] {item}
```

## Task decomposition rules

1. **Worktree independence**: each task must be implementable from its own
   task plan + IMPLEMENTATION.md alone, inside an isolated worktree. A task
   plan never references a sibling task plan.
2. **Size**: a task is one implementer session's worth of coherent work
   (roughly: one component, one endpoint group, one UI area). Split anything
   whose Acceptance Criteria exceed ~7 items.
3. **`files` prediction is a contract**: list every file the task should
   create or modify. Review scoping and deviation tracking depend on it —
   when unsure whether a task touches a file, INCLUDE it.
4. **Interface contracts instead of sequencing**: ALL tasks are implemented
   fully in parallel — there is no ordering mechanism between tasks. When one
   task's code uses a component another task builds, pin that component's
   contract (signature, pre/postconditions) in IMPLEMENTATION.md Shared
   Components so both sides implement against the contract independently.
   File overlap between tasks is allowed — merge conflicts are resolved by
   the implementer's parent-side-adoption protocol. Integration mismatches
   surface in the review/verify phases and are resolved as new tasks.
5. **Acceptance Criteria**: mandatory, objectively verifiable, test-
   translatable. They are the implementer's TDD contract ("テスト通過 =
   タスク完了").
6. Use `${CLAUDE_PLUGIN_ROOT}/references/templates/task-plan.md` verbatim as
   the structure.
7. **Integration wiring must have an owner**: when a consumer task is
   permitted to compile against a clearly-marked placeholder for a component
   another task builds, exactly one task's plan (or a dedicated integration
   task) must own replacing that placeholder with the real wiring, stated in
   its Acceptance Criteria. "Integration wires it later" without an owning
   task means nobody wires it until review.
   (Evidence: braille-ar-overlay 2026-07-11 — MainActivity placeholder
   reached review unwired; high findings b1f3fbd049a5cb53 / b1d63678861295ba)

## complexity criteria (low / medium / high)

- **low**: localized change in one or few files following an existing
  pattern; no new component; no contract changes; obvious test approach.
- **medium**: new component, or changes spanning multiple components; changes
  an internal contract with all callers updated inside the task; requires
  design choices within an established architecture.
- **high**: ANY of — touches concurrency, transactions, or a security
  boundary; changes a public/external contract or data schema (migration
  needed); introduces a new architectural element or crosses layers in a new
  way; failure modes are subtle (partial failure, retries, ordering).

When in doubt between two levels, pick the higher one (complexity drives the
review floor and codex cross-validation — under-rating weakens review).

## domains criteria (assign every value that materially applies)

- `auth` — authentication/authorization logic, sessions, tokens, permissions.
- `input-handling` — parsing/validating external input (user, API, file).
- `data-persistence` — DB schema/queries, storage formats, migrations.
- `external-io` — network calls, third-party APIs, file-system side effects.
- `concurrency` — goroutines/threads/async orchestration, locks, shared state.
- `api-contract` — public API shapes, status codes, exported interfaces.
- `ui` — rendered UI, styling, user-facing interaction flows.
- `config-infra` — build/CI/deploy config, environment wiring, tooling.

## VERIFICATION.md Template (feature-wide)

```markdown
# Verification Document: {Feature Name}

## Overview
**Feature**: {name} / **SPEC.md**: `{path}` / **IMPLEMENTATION.md**: `{path}`

## Build Verification
- Command: {from workflow.yaml project.components}
- Expected: exit code 0, no errors

## Test Verification
- Command: {from workflow.yaml}
- Coverage target: minimum {X}%, target {Y}%

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-N | {scenario} | {outcome} | Unit/Integration |

## Code Quality Verification
- Format: {command} / Static analysis: {command}

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|

### Functional Requirements Coverage
Requirement IDs are hyphen-less (`FR1`, `NFR2`) and must string-match the
workflow.yaml `requirements` keys and the SPEC.md numbering exactly —
traceability checks compare these as literal strings.
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task000N, ... | {method} |

## E2E Testing
{project E2E framework if any; otherwise omit}
- [ ] {automatable scenario}

## Manual Testing (E2E Not Possible)
- [ ] {human-judgment scenario}

## Performance / Security Verification (if applicable)
- {requirement}: {threshold / check}

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
```

## Pre-Save Self-Verification Checklist (MANDATORY)

- [ ] No language-specific code blocks, library API calls, or snippets
      anywhere (IMPLEMENTATION.md AND every task plan).
- [ ] IMPLEMENTATION.md contains only cross-task content.
- [ ] Every task: files / skills / domains / complexity /
      requirements all present in workflow.yaml.
- [ ] Every cross-task component use has its contract pinned in
      IMPLEMENTATION.md Shared Components.
- [ ] Every task plan has non-empty, verifiable Acceptance Criteria.
- [ ] Every FR/NFR maps to ≥ 1 task and ≥ 1 test (or is flagged as a gap).
- [ ] skills values exist in impl-skills.yaml; domains values in the 8-value
      vocabulary; complexity in {low, medium, high}.
