# Feature: recycled-task-id-contract

## Overview

The recycled-task-id wording in section I.2.a of `em-workflow/references/implement-phase.md` (the em-workflow SSOT) is self-contradictory, so a reader cannot reach a single interpretation. The Stop-hook bullets in the same document's Supporting cast section do not agree with I.2.a either, and `tests/test_recycled_task_id_consistency.py` currently passes even when the implementation breaks. This feature rewrites the affected documentation, splits the ineffective assertions, and pins the documented hook classification against the hook sources with a machine-checked test.

Requirements source: `feature-docs/recycled-task-id-contract/REQUIREMENTS.md`.

## Objectives

- Remove the self-contradiction from I.2.a's recycled-task-id wording so that readers reach a single interpretation.
- Update `tests/test_recycled_task_id_consistency.py` to a contract that matches the implementation, ending its no-op state.
- Pin the documented classification rule to the hook implementation mechanically, so a change on only one side is detected.

## User Stories

### US1: A reader of implement-phase.md resolves recycled-task-id handling unambiguously
As an em-workflow reader (orchestrator or worker), I want to read I.2.a and reach one interpretation of recycled-task-id handling, so that I do not have to guess which of two contradictory statements applies.

**Acceptance Criteria:**
- [ ] AC1: I.2.a's recycled-task-id wording is a single, non-contradictory statement (FR1).
- [ ] AC2: The Supporting cast Stop-hook bullets agree with I.2.a (FR2).
- [ ] AC4: I.2.a states, with its reason, that the hooks treat a task as unlaunched based solely on the absence of the journal (FR4).

### US2: A developer detects doc/implementation divergence by running the tests
As a developer or CI, I want the consistency tests to fail when either the documentation or the hook implementation changes alone, so that the classification rule and the hooks cannot silently drift apart.

**Acceptance Criteria:**
- [ ] AC3: `TestRecycledTaskIdRuleScopedToOrchestrator` asserts the "3 hooks that do not read status" group and the "explicit exception `queue_stop_guard.py`" separately (FR3).
- [ ] AC5: One pin test parses the machine-readable hook classification table in the documentation and verifies, for each listed hook, whether its source reads `tasks.{T}.status` (FR5).
- [ ] AC6: `python3 -m unittest discover -s tests` passes from the repository root.
- [ ] AC7: The versions in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are bumped to the same value (FR6).

## Technical Requirements

### Functional Requirements

- **FR1 — Make I.2.a's recycled-task-id wording non-contradictory:** Rewrite the recycled-task-id description in `em-workflow/references/implement-phase.md` I.2.a into a single, self-consistent statement. It must be unambiguous on a single reading that the recycled-task-id rule is scoped to the orchestrator, and how far the hook side is responsible. (status: resolved)
- **FR2 — Align the Supporting cast Stop-hook bullets with I.2.a:** Update the Stop-hook bullets in the same document's Supporting cast section so they do not contradict the I.2.a wording settled by FR1. Both must refer to the same classification (hooks that read `tasks.{T}.status` vs. hooks that do not). (status: resolved)
- **FR3 — Split the assertions in `TestRecycledTaskIdRuleScopedToOrchestrator`:** In `tests/test_recycled_task_id_consistency.py`, express `TestRecycledTaskIdRuleScopedToOrchestrator` as an assertion over the "3 hooks that do not read `tasks.{T}.status`" and a separate assertion over the "explicit exception `queue_stop_guard.py`". The two groups must not be collapsed into one assertion, and if either side breaks, the test for that group must fail. (status: resolved)
- **FR4 — Record the unlaunched-detection divergence in I.2.a as SSOT:** Without changing hook behaviour, state in `implement-phase.md` I.2.a — together with its reason — that the hooks treat a task as unlaunched based solely on the absence of the journal. I.2.a must not be worded as a promise of protection that the hooks do not provide. (status: resolved)
- **FR5 — Make the hook classification table machine-readable and pin it with one test:** Add to `implement-phase.md` a machine-readable table mapping hook name to classification (reads `tasks.{T}.status` / does not read it), and have a pin test parse that table and verify, for each hook listed, whether its source reads `tasks.{T}.status`. The test must fail when only the documentation side or only the implementation side changes. The test must be kept to a single test. (status: resolved)
- **FR6 — Bump the plugin version:** Because files under `em-workflow/` change, raise the version in `em-workflow/.claude-plugin/plugin.json` and in the corresponding entry of the repository-root `.claude-plugin/marketplace.json` to the same value, by a patch increment, within the same change. (status: resolved)

### Non-Functional Requirements

- **NFR1 - Test dependencies:** Test code uses only the Python standard library `unittest` and imports no third-party package (`test/README.md`).
- **NFR2 - Test placement and naming:** Tests live under the repository-root `tests/` directory as `test_*.py`; classes are named `Test<Behavior>` and methods `test_<condition>_<expected_result>`. Targets are handled by path reference (e.g. `em-workflow/hooks/queue_stop_guard.py`).
- **NFR3 - Out-of-scope immutability:** The classification logic in `queue_stop_guard.py` itself is not changed. No hook's runtime behaviour changes at all in this feature.
- **NFR4 - Single source of truth:** The expected hook classification originates solely from the documentation-side table; no duplicated hard-coded classification is introduced inside the tests.

## Implementation Approach

### Architecture

**System Architecture:**

```
┌──────────────────────────────────────────────────────────┐
│ em-workflow/references/implement-phase.md   (SSOT)       │
│   - I.2.a recycled-task-id wording          (FR1, FR4)   │
│   - Supporting cast Stop-hook bullets       (FR2)        │
│   - machine-readable hook classification table (FR5)     │
└───────────────┬──────────────────────────────────────────┘
                │ parsed by
                ▼
┌──────────────────────────────────────────────────────────┐
│ tests/  (unittest, stdlib only)                          │
│   - TestRecycledTaskIdRuleScopedToOrchestrator (FR3)     │
│   - pin test over the classification table     (FR5)     │
└───────────────┬──────────────────────────────────────────┘
                │ inspects source of
                ▼
┌──────────────────────────────────────────────────────────┐
│ em-workflow/hooks/*.py   (unchanged — NFR3)              │
└──────────────────────────────────────────────────────────┘
```

**Component Diagram:**

```
implement-phase.md ── classification table ──> pin test ──> hook sources
        │                                                       ▲
        └── I.2.a / Supporting cast wording (human-readable) ────┘
                     (must describe the same classification)
```

### Data Flow

```
implement-phase.md table → parse rows (hook name, classification)
                         → read each hook source by path
                         → check whether it references tasks.{T}.status
                         → assert parsed classification == observed behaviour
```

The documentation table is the only source of the expected classification
(NFR4); the tests derive their expectations from it rather than restating
them.

### API Design

Not applicable. This feature exposes no API surface.

### Database Schema

Not applicable. This feature introduces no persistent data.

The only structured data it introduces is the documentation table:

| Column | Type | Null | Default | Description |
|--------|------|------|---------|-------------|
| hook name | string | NO | - | Path reference to the hook (e.g. `em-workflow/hooks/queue_stop_guard.py`) |
| classification | enum | NO | - | Reads `tasks.{T}.status` / does not read it |

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the SSOT whose I.2.a (:222-232) and Supporting cast Stop-hook bullets (:496-506) are edited, and which hosts the new classification table.
- `em-workflow/hooks/*.py`: the hook sources the pin test inspects; unchanged by this feature (NFR3).
- `tests/test_recycled_task_id_consistency.py`: hosts `TestRecycledTaskIdRuleScopedToOrchestrator`.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: version bump targets (FR6).

**External Dependencies:**
- Python standard library `unittest` only. No third-party package (NFR1).

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md          # I.2.a, Supporting cast, classification table
├── hooks/                          # inspected, not modified
└── .claude-plugin/
    └── plugin.json                 # version bump
tests/
└── test_recycled_task_id_consistency.py   # split assertions + pin test
.claude-plugin/
└── marketplace.json                # version bump (same value as plugin.json)
```

The exact hook file names covered by the classification table are taken
from `implement-phase.md`'s own wording and the new table; the on-disk hook
file listing is confirmed during the implementation phase.

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/implement-phase.md`
- `tests/**`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/recycled-task-id-contract/**`
- `test-docs/recycled-task-id-contract/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`,
`VERIFICATION.md`, `retrospect.yaml`, and the design artifacts the design
step produces. These are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 (FR3, FR5): For each of the "3 hooks that do not read status" listed in the classification table, assert individually that its source does not read `tasks.{T}.status`.
- [ ] TS2 (FR3, FR5): For `queue_stop_guard.py`, verify in a separate assertion that, as the explicit exception, it does read `tasks.{T}.status`.

### Integration Tests

- [ ] TS3 (FR5) — pin test: Parse the classification table in `implement-phase.md` and verify that, for every hook listed, the implementation and the classification agree. It fails on a hook name absent from the implementation, or on a classification that disagrees with the implementation.
- [ ] TS5 (FR3, FR5): The full run of `python3 -m unittest discover -s tests` succeeds.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS4 (FR5) — negative check: Inverting only the classification in the table makes the pin test fail (confirming the test is not a no-op).

### Performance Tests

Not applicable. This feature has no runtime performance surface.

## Security Considerations

Not applicable. This feature changes documentation, tests, and version
fields only; it introduces no authentication, authorization, input
handling, or data-protection surface.

## Error Handling

The only failure surface is test failure. The pin test (FR5) fails when a
hook name in the table is absent from the implementation, or when a
classification in the table disagrees with the corresponding hook source.
The split assertions (FR3) fail per group, so a break in the
"does not read status" group and a break in the `queue_stop_guard.py`
exception are distinguishable.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements (FR1-FR6) are implemented.
- [ ] All test scenarios (TS1-TS5) pass.
- [ ] AC1: I.2.a's recycled-task-id wording is a single, non-contradictory statement (FR1).
- [ ] AC2: The Supporting cast Stop-hook bullets agree with I.2.a (FR2).
- [ ] AC3: `TestRecycledTaskIdRuleScopedToOrchestrator` asserts the "3 hooks that do not read status" and the explicit exception `queue_stop_guard.py` separately (FR3).
- [ ] AC4: I.2.a states, with its reason, that the hooks decide unlaunched solely from the absence of the journal (FR4).
- [ ] AC5: A single pin test parses the machine-readable hook classification table and verifies each hook's source against it (FR5).
- [ ] AC6: `python3 -m unittest discover -s tests` passes from the repository root.
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same bumped version (FR6).
- [ ] The classification logic of `queue_stop_guard.py` and every hook's runtime behaviour are unchanged (NFR3).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1-FR6, NFR1-NFR4) is `resolved`.

## Assumptions

Carried over from the resolved requirements analysis:

- The repository root contains no LICENSE file, so the SPDX identifier
  cannot be determined (treated as not detected).
- The concrete names of the "3 hooks that do not read status" originate
  from `implement-phase.md`'s wording and from the new classification
  table. The on-disk hook file listing is confirmed during the
  implementation phase.
- Hook behaviour is not changed; the fact that the hooks treat a task as
  unlaunched solely from the absence of the journal is recorded, with its
  reason, in `implement-phase.md` I.2.a as SSOT (batch-codex-consultation,
  gate `create-spec.requirement-clarification`, option
  `doc_records_divergence`). Rationale: changing `queue_stop_guard.py`'s
  classification logic is out of scope per the task description, and
  writing down the journal-absence rule avoids the SSOT promising
  protection the hooks do not provide.
- A machine-readable hook-to-classification table is added to
  `implement-phase.md`, and the pin test parses it to verify whether each
  hook's source reads `tasks.{T}.status` (batch-codex-consultation, gate
  `create-spec.requirement-clarification`, option `parse_doc_table`).
  Rationale: parsing the table makes the documentation the origin of the
  expected classification, so a one-sided change makes the test fail.

## Implementation Phases (if applicable)

Not applicable. The change is small enough to be delivered as a single
phase.

## References

- Requirements document: `feature-docs/recycled-task-id-contract/REQUIREMENTS.md`
- SSOT under change: `em-workflow/references/implement-phase.md` (I.2.a at :222-232, Supporting cast Stop-hook bullets at :496-506)
- Test under change: `tests/test_recycled_task_id_consistency.py` (`TestRecycledTaskIdRuleScopedToOrchestrator`)
- Test conventions: `test/README.md`
- Notion task: [https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804](https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804)
- Origin review findings: `eda12b14c5d3235f` (comprehensive / medium / confidence 80), `0e36903a813a34fa` (architecture / medium / confidence 75)
