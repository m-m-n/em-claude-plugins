# Implementation Plan: review-gate-abort-recovery

## Overview

Make `em-workflow/references/review-phase.md` Phase R5 the single definition
site for (a) the review status the orchestrator writes when a
`rework.spec-change` question stops a review-sourced rework run, (b) the
resume path from that stop, and (c) the recovery of a review step already
left `failed`; `em-workflow/skills/develop/SKILL.md` cites those definitions
at the two places that need them. Two new document-structure test modules
pin the wording, each matcher paired with a negative twin.

## Technology Stack

- **Documents**: Markdown SSOT files of the em-workflow plugin — protocol
  definitions the orchestrator reads and follows
- **Tests**: Python 3 standard-library `unittest` — document-structure tests
  collected by `python3 -m unittest discover -s tests`
- **New dependencies**: none (no license to record)

## Layer Structure

| Layer | Location | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Definition | `em-workflow/references/review-phase.md`, Phase R5 | Owns the gate-abort status rule, the resume path, the legacy recovery procedure, and the stated scope of the `status: failed` reservation | Cites `question-resolution.md`, `rework-task-synthesis.md`, `phase-state.md`, `batch-terminal-line.md` and SKILL.md's existing exit-4 recovery, restating none of them |
| Citation | `em-workflow/skills/develop/SKILL.md` | Names the Definition layer's blocks at the Step B gate-call paragraph and at the 停止時の報告 section | Definition layer, by label (SC1, SC2) |
| Test | `tests/` | One new module per edited document; each module reads only the document it pins (task0001's module additionally reads `workflow-schema.md`, read-only, for the schema non-change guard) | The document it pins |

Dependency direction: Citation → Definition; Test → its own document. No
new Definition-layer text depends on the Citation layer's new insertions.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| SC1 — gate-abort block label | Names the Phase R5 block that defines the review status at a spec-change gate abort and the resume path from it | Label text: `Spec-change gate abort (review-sourced rework)`. Definition form: the label in bold opens exactly one paragraph inside `## Phase R5: Persist the round record`, after the batch-mode paragraphs (the one opening "Batch mode (develop-駆動 only): no offer" and the one opening "This batch auto-rework / defer-at-cap behaviour above") and before `## Phase R6: Report (Japanese)`. Post: the bold form occurs exactly once in review-phase.md; any document may cite the label in SC3 form. | task0001 (defines), task0002 (cites) |
| SC2 — legacy-recovery block label | Names the Phase R5 block that defines the recovery of a review step already left `failed` | Label text: `Legacy review-failure recovery`. Definition form: the label in bold opens exactly one paragraph inside Phase R5, after the SC1 block and before `## Phase R6: Report (Japanese)`. Post: the bold form occurs exactly once in review-phase.md; any document may cite the label in SC3 form. | task0001 (defines), task0002 (cites) |
| SC3 — citation form | How a document refers to SC1 / SC2 | Pre: the citing sentence sits inside the paragraph or section that needs it. Post: the sentence names `references/review-phase.md` (a `${CLAUDE_PLUGIN_ROOT}/` prefix is allowed), the token `Phase R5`, and the label text verbatim without bold markers; it restates none of the cited block's field values, conditions or commit step. | task0002 (two citations), task0001 (one citation of SC1 inside the `status: failed` reservation paragraph) |

## Conventions

- **Host language**: new text in review-phase.md is English; new text in
  SKILL.md is Japanese, matching the surrounding prose.
- **Cited, not restated (NFR3)**: a rule lives only in its Definition-layer
  block; every other mention cites it in SC3 form.
- **Insert, never re-wrap**: existing lines are neither edited nor
  re-wrapped; new text is added as new lines. Existing tests match phrases
  that a re-wrap would split. SC1 / SC2 label text and every SC3 citation
  stay on a single line.
- **Literal absence (both documents; already enforced by existing sweeps)**:
  no batch stop reason code (including `unmapped_stop`), no `no-step`, no
  `phase_done`, no `EM_WORKFLOW_` prefix literal, no additional occurrence of
  the user-question tool name `AskUserQuestion`, and no new gate identifier.
- **Test modules**: standard library only; files are reached by literal path
  joins from the repository root, never by glob or directory walk; one
  matcher per pinned element, each paired with a negative twin (synthetic
  text kept inline in the module, or the pre-change text verbatim when the
  matcher defends an addition to existing prose) and a non-vacuity check on
  every sliced region; no existing test module is edited; the literal
  `SPEC.md` is not used in the new modules (a repository sweep flags it when
  it appears near `feature-docs` and a wildcard character).
- **Plugin version**: no task's file set includes
  `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`
  (NFR6).

## Cross-task Design Decisions

### D1: One definition site (FR2, NFR3)

The gate-abort status rule, the resume path and the legacy recovery
procedure are defined once, in Phase R5 (SC1, SC2). SKILL.md cites them and
restates nothing. Rationale: two copies of a status rule drift; Phase R5
already owns the review step's rework paths. Affected: task0001, task0002.

### D2: No stop reason code in either document

Which reason code a gate-abort stop binds to belongs to
`batch-terminal-line.md` (Stop point coverage table and Fallback rule);
neither edited document names a code. Rationale: existing sweeps forbid
code literals in both documents, and that table binds the fail-closed aborts
and the Classification gate's stop through different rows, so a restated
code would drift. Affected: task0001, task0002.

### D3: Recovery guidance is carried in full at run time, cited in prose

`batch-terminal-line.md` requires `resume_conditions` to carry stop-recovery
guidance in full; a pointer alone does not satisfy it. The documents
therefore instruct the stop report to convey the guidance's content
together with the location of its definition, while the citing prose names
the definition (SC3) rather than copying it. Affected: task0001 (the guidance
a gate-abort stop reports), task0002 (the stop-condition-3 report on
`review: failed`).

### D4: No new control-flow element (FR3, NFR1, NFR2)

Resumption goes through Step B's existing selection of the first step that
is neither `completed` nor `skipped`. No Step B branch, no
stop-condition-3 exception and no interactive question is added; the legacy
recovery procedure is a documented state repair, not a Step B evaluation.
Affected: task0001, task0002.

### D5: Integration consistency through shared literals

Tasks run in parallel, so neither test module asserts on the other task's
document. Each pins the SC1 / SC2 literals on its own document; that the
labels SKILL.md cites resolve in review-phase.md is checked on the
integrated tree at verify (VERIFICATION.md TS-9). Affected: task0001,
task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An insertion breaks a phrase, order or count an existing test pins (NFR4) | Medium | High | Each task plan lists the known pins for its document; insert-never-re-wrap convention; the full suite is in each task's Acceptance Criteria |
| Label drift between the defining and the citing document | Low | Medium | SC1 / SC2 literals pinned on both sides; TS-9 at verify |
| A `gate_id` or reason-code literal enters review-phase.md | Medium | Medium | Literal-absence convention; existing whole-file sweeps |
| The legacy recovery procedure is read as an automatic Step B branch, weakening stop condition 3 | Low | High | D4; task0001 pins the block's statement that it adds no Step B branch and no stop-condition-3 exception |

## Open Questions

- [ ] For the fail-closed aborts (origin-membership failure, malformed
  pairing), `question-resolution.md` closes a packet as `obsolete` only on
  the Classification gate's stop / inapplicable outcomes; what the previous
  packet's state is on resume after a fail-closed abort is not stated in
  SPEC.md, and this plan adds no rule for it.
- [ ] SPEC.md's edge case binds a gate-abort batch stop to `unmapped_stop`,
  while `batch-terminal-line.md`'s coverage table routes the fail-closed
  aborts through its `fail-closed-abort` row. Per D2 neither document names
  a code, so no contradiction is written, but the SPEC statement is
  imprecise for those two stops.
- [ ] A batch `rework.spec-change` question that trips the Classification
  gate's direction 2 takes the relaxed consultation route and can stop
  through the Unlisted-gate fallback; that stop is not among SPEC.md's
  enumerated gate aborts and is not covered by this plan.
- [ ] SPEC.md names the orchestrator as the actor of the legacy recovery
  procedure but not what prompts its application; this plan only requires
  that the procedure adds no Step B branch and no stop-condition-3
  exception.
