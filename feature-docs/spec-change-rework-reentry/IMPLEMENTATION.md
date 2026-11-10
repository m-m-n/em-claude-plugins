# Implementation Plan: spec-change-rework-reentry

## Overview

A feature that went through rework's SPEC-change transition reaches
review → verify → retrospect without anyone hand-editing `workflow.yaml`:
the transition also returns `verify` to `pending`, implement Step I.0 gains a
SPEC-change re-entry route that completes the phase through Step I.3 when no
task is pending, and Invariant 1 states that it does not govern the
SPEC-change transition. Requirements: `SPEC.md`, `REQUIREMENTS.md`.

## Technology Stack

- **Language / Framework**: Markdown protocol documents of the em-workflow
  plugin (English; `em-workflow/skills/develop/SKILL.md` is Japanese) and
  Python 3 standard-library `unittest` modules under `tests/`.
- **Key libraries**: none.
- **New dependencies**: none (so no dependency license is recorded;
  `project.license` is `none`).

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Owner documents | `em-workflow/references/rework-task-synthesis.md` Section 10 (SPEC-change transition) and Section 11 (invariants); `em-workflow/references/implement-phase.md` Step I.0 (entry preconditions) | State each rule once |
| Citing documents | `em-workflow/references/contracts/rework-planner-contract.md` and `em-workflow/agents/rework-planner.md` (their existing five-step summary of the transition); `em-workflow/skills/develop/SKILL.md` 「verify フェーズ」 item 6 | Point at the owner; the contract and the agent prompt keep their existing five-step summary form |
| Document tests | `tests/*.py` | Read the documents from the repository root and pin their wording |

Allowed dependency direction: citing documents → owner documents; tests →
documents. An owner document never restates a citing document's content.

## Shared Components

These are document anchors. Each task edits only the sections it owns and
relies on the others' anchors as stated here.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| SPEC-change transition block | The transition rework applies when a SPEC.md change is selected | Location: `em-workflow/references/rework-task-synthesis.md`, heading `## 10. Workflow state transition`, block labelled `**When rework needs a SPEC.md change**`. Pre and post: exactly five numbered steps 1–5, immediately followed by the paragraph that opens with "Step 2's `create-plan` re-entry". Post (after task0001): step 2 names `create-plan`, `implement`, `review` and `verify` as set to `pending`. Heading, label and numbering never change. | task0001 (owner); task0002 and task0003 cite it as "Section 10" |
| Section 11 invariant list | The rework-synthesis invariants | Heading `## 11. Invariants`; exactly 11 numbered invariants before and after; Invariant 1 and Invariant 9 keep their numbers, Invariant 9 its text. Post (after task0002): Invariant 1 states that it does not govern the SPEC-change transition and cites Step I.0. | task0002 (owner); task0003 cites "Invariant 1" (existing citation) and may cite "Invariant 9" |
| Step I.0 re-entry precondition | Entry routes into `implement` and the protocol-error ABORT | `em-workflow/references/implement-phase.md`, heading `## Step I.0: Preconditions`, item labelled `5. **Re-entry precondition**`. Heading and label unchanged. Post (after task0003): the item owns the SPEC-change re-entry's identification, its zero-task path and the ABORT for every other state. | task0003 (owner); task0002 cites it as "`references/implement-phase.md`'s Step I.0" |
| `spec_change` record | The record of `phase-state/rework.yaml` that the SPEC-change transition writes | Defined by `em-workflow/references/phase-state.md`, which this feature does not change; field meanings are cited, never restated | task0002 (named only as a field set it must not restate), task0003 (reads it) |

## Conventions

- **Terminology (English documents)**: "SPEC-change transition" is the
  transition of Section 10's `**When rework needs a SPEC.md change**` block.
  "SPEC-change re-entry" is the entry into `implement` after that transition
  and the create-spec → create-plan re-run that follows it.
- **Citation, not restatement (NFR1)**: Invariant 1 cites Step I.0 and copies
  none of its identification conditions; Step I.0 cites Section 10 and
  `references/phase-state.md` and restates neither the five transition steps
  nor the field definitions; SKILL.md cites Section 10 and lists none of its
  steps.
- **Pinned wording**: an edit leaves every line that an existing test pins as
  raw text byte-identical; new statements are added as new sentences and
  lines, not by reflowing pinned lines. Where an edit necessarily changes a
  pinned string, digest or count, the same task updates that pin to the new
  wording and keeps the assertion's meaning: eleven invariants, five-step
  numbering 1–5, the precondition stated before the launch selection, and
  every existing non-vacuity test.
- **Document tests**: standard library only; the repository root is computed
  from the module's own path; exact markers are module constants; matching is
  whitespace-normalised except where a raw pin is intended (Japanese text
  wraps without a space, so normalisation removes all whitespace); every
  matcher is backed by a negative proof against synthetic text that lacks the
  statement, and a verbatim pre-change excerpt is among the negative samples
  so each new module demonstrably fails against the pre-change wording (SPEC
  AC7). A new module asserts nothing about a section another task owns.
- **Language and redaction (NFR4)**: English documents stay English and
  SKILL.md additions are Japanese; no changed document holds a Notion URL or
  an absolute path under the home directory.
- **Plugin files**: no task edits `em-workflow/.claude-plugin/plugin.json` or
  `.claude-plugin/marketplace.json` (NFR2).

## Cross-task Design Decisions

### D1: Tasks follow document ownership; pins travel with the edit

Decision: task0001 owns Section 10 and its three citing documents, task0002
owns Section 11, task0003 owns Step I.0. Each task updates, in the same task,
every existing test that pins the section it edits.
Rationale: tasks run in parallel in separate worktrees; a pin (for example
the Section 11 SHA-256 in `tests/test_rework_docs_only_route_doc.py`) can only
be recomputed by the task that changes the pinned text, and each worktree must
pass the full suite on its own.
Affected tasks: task0001, task0002, task0003.

### D2: One new recurrence-test module per task

Decision: FR7's four checks are split by owner — (a) in
`tests/test_spec_change_verify_pending.py` (task0001), (d) in
`tests/test_spec_change_invariant_scope.py` (task0002), (b) and (c) in
`tests/test_spec_change_implement_reentry.py` (task0003). Together they cover
FR7 (a)–(d).
Rationale: a single module covering all four would fail in every worktree
except the one holding all edits.
Affected tasks: task0001, task0002, task0003.

### D3: Shared files are edited in disjoint parts

Decision: `em-workflow/references/rework-task-synthesis.md` is edited by
task0001 only in Section 10 and by task0002 only in Section 11.
`tests/test_rework_synthesis_contract.py` is touched by task0002 only inside
the Section 11 invariants class and by task0003 only inside the
implement-phase precondition class. `tests/test_failed_kind_resume_reentry.py`
is edited by task0003 only; its Invariant 1 pins keep passing because task0002
does not reflow pinned lines.
Rationale: keeps parallel merges free of overlapping hunks; any remaining
conflict is resolved by the implementer's parent-side adoption protocol.
Affected tasks: task0001, task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A test outside a task's `files` pins wording the task changes | Medium | Medium | Each task runs the full suite; a needed file outside `files` is reported as a plan deviation. Known pins are listed in each task plan. |
| A reflow of a pinned line breaks raw-text pins in other modules | Medium | Low | Conventions, Pinned wording: add lines, do not reflow. |
| The SPEC-change re-entry is identified where it should not be, skipping the protocol-error ABORT | Low | High | THREAT-MODEL.md TM-1 to TM-3, carried by task0003's Acceptance Criteria. |
| Merge conflict in a shared test module or in rework-task-synthesis.md | Low | Low | D3: disjoint parts per task. |

## Open Questions

- None.
