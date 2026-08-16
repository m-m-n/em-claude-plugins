# Verification Document: routeback-reset-scope-consistency

## Overview

**Feature**: routeback-reset-scope-consistency /
**SPEC.md**: `feature-docs/routeback-reset-scope-consistency/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/routeback-reset-scope-consistency/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature — the state of
the repository after every task has merged into the integration branch.
Task-level acceptance criteria live in the task plans.

## Build Verification

- Command: none. `workflow.yaml` `project.components.main.build_command` is
  empty — the deliverables are Markdown, JSON and Python test modules, none of
  which is compiled.
- Expected: n/a. The JSON manifests parsing successfully is asserted by the
  test suite instead (TS-9).

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the project root).
- Expected: exit code 0, zero failures, zero errors, zero skips.
- Coverage target: not measured — the project has no coverage tooling and the
  suite asserts document/registry contracts rather than executed lines. The
  substitute target is traceability: every requirement below maps to at least
  one test scenario, and every new-wording matcher carries a negative proof
  (TS-8, AC-4 of SPEC.md).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The I.2.c gate's `merged` conjunct is stated as a union of workflow.yaml status and Step I.2.b step 1's reconciled state, citing I.2.b as owner | The union statement is present in the normalized I.2.c section, the retained literal "no task has status `merged`" survives, and the pre-change sample lacks the union statement | Unit (document contract) |
| TS-2 | The write set's reset target is expressed in reconciled-state terms | The reconciled-state phrasing is present; the workflow.yaml-`status: failed`-only phrasing is absent; the four write instructions survive in order | Unit (document contract) |
| TS-3 | The cleanup sentence names its targets as the tasks just reset and states they are confirmed not merged | The scoped sentence is present and `git branch -D` occurs only inside it within the I.2.c section | Unit (document contract) |
| TS-4 | The rejected branch enumerates the reconciled-state-`merged` blocker and keeps its single terminal | The new blocker appears in the enumeration; `implement` set to `failed`, committed, stop condition 3 all survive; no route-back instruction appears after "When the gate does not hold" | Unit (document contract) |
| TS-5 | I.2.a's unreachability sentence and the Branch & Worktree Model's exit-4 union-rule sentence still describe the gate as it now reads | The exit-4 sentence identifies the `in_progress` union; I.2.a's sentence still slices from "Given I.2.c's route-back precondition" to "can never arise." | Unit (document contract) |
| TS-6 | The recursion-invariant statement is present and the I.2.a carve-out stays scoped to `failed` | Both statements present in the normalized I.2.a section | Unit (document contract) |
| TS-7 | Regression guards | I.2.c heading and batch-mode-paragraph TAIL byte-identical; the three protected raw line-wrap literals intact; the four normalized I.2.c orderings (60-character `tasks.{T}.status` / `pending` window, write tokens before cleanup, `commit-docs.sh` before cleanup before "End the phase with a", "terminal journal last event (`merged` or `failed`)" before "`create-plan` to `needs_update`") hold; retained gate literals present; "rework" / "append" absent from I.2.c; no bare git commit/add line in the file | Unit (regression) |
| TS-8 | Every new-wording matcher in TS-1 .. TS-6 has a negative proof against a verbatim pre-change sample, and each sample carries a retained anchor asserted positively | Each matcher's literal lives in one shared constant; each proof runs on the normalized captured sample; each sample's non-vacuity guard passes; exemptions recorded in the module docstring | Unit (meta / test quality) |
| TS-9 | Both version files report the same, bumped version string | Both parse as JSON; `0.1.x` with patch > 38; the two strings are equal | Unit (registry contract) |

### Rework scenarios (verify round 1 → task0003)

Added for the verify-sourced rework tasks; they extend the table above and are
run by the same command.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-10 | The route-back write set's reset target set covers both `failed` sources, and the document connects that set to the postcondition and to `replace_all`'s workflow.yaml-status permission conditions | The existing reconciled-state literal survives verbatim as the leading member, a workflow.yaml `status: failed` member is named alongside it, and one sentence states that the two sets can diverge (citing Step I.2.b step 3) and that covering both is what makes the postcondition true; the four write instructions, their order and the 60-character `tasks.{T}.status` / `pending` window still hold | Unit (document contract) |
| TS-11 | The cleanup sentence reads as a consequence of the gate and claims only what the two sources verify, with the merged-branch-without-journal-event residual recorded in the leftover-state style | The gate-consequence wording and the source-qualified not-merged claim are present, both retained cleanup literals survive, the residual sentence follows the leftover-state sentence, `git branch -D` still occurs exactly once inside the scoped sentence, and "rework" / "append" are still absent from the I.2.c section | Unit (document contract) |
| TS-12 | Step I.2.a's forward reference to the I.2.c gate points below, and the carve-out / gate / reconciled-state ownership chain has a stated termination point | No reference to the I.2.c gate as `above` remains in I.2.a; the recursion-invariant sentence still follows "can never arise."; the termination sentence states the carve-out applies only to a `failed` last event so Step I.2.b step 1's `merged` classification never consults it; the carve-out and in-flight sentences survive | Unit (document contract) |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty; there is no
  formatter configured for Markdown, JSON or the test suite.
- Static analysis: none configured. The equivalent guard for this feature is
  the document-contract suite itself, plus the JSON parse in TS-9.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | I.2.c's route-back admissibility, write set and cleanup all name Step I.2.b step 1's reconciled state | TS-1, TS-2, TS-3, TS-10 pass; plus the manual read-through below |
| AC-2 | A task whose journal last event is `merged` (ancestor-verified) is never a route-back cleanup target, whatever workflow.yaml says | TS-1, TS-3 and TS-11 pass; manual walk of EC-1 / EC-2 against the edited paragraph |
| AC-3 | The document states that `git branch -D` on this path targets only tasks confirmed not merged | TS-3 and TS-11 pass — TS-11 additionally requires the claim to be qualified by the two sources the path actually reads, with the unverifiable residual recorded rather than asserted away |
| AC-4 | Document-contract tests equivalent to TS-3 / TS-4 exist under `tests/`, each new matcher paired with a negative proof and a non-vacuity guard | TS-3, TS-4, TS-8 pass; the module docstring's matcher inventory lists every exemption |
| AC-5 | `python3 -m unittest discover -s tests` passes | Run the command from the project root; exit code 0, no skips |
| AC-6 | `tests/test_implement_routeback_gate.py` and `tests/test_recycled_task_id_consistency.py` pass unmodified | The suite run above, plus `git diff --name-only` against the implement base commit showing neither file in the diff |
| AC-7 | Both version files carry the same bumped version | TS-9 passes |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001, task0003 | TS-2, TS-10 |
| FR3 | task0001, task0003 | TS-3, TS-11 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001, task0003 | TS-5, TS-12 |
| FR6 | task0001, task0003 | TS-6, TS-12 |
| FR7 | task0001, task0003 | TS-8 (the module's own quality contract), exercised by TS-1 .. TS-7 and TS-10 .. TS-12 |
| FR8 | task0002 | TS-9 |
| NFR1 | task0001, task0003 | TS-7 (heading and batch-mode-paragraph byte identity) |
| NFR2 | task0001, task0003 | TS-7 (the three protected raw line-wrap literals) |
| NFR3 | task0001, task0003 | TS-7, TS-10 (the four normalized I.2.c orderings) |
| NFR4 | task0001, task0003 | TS-4, TS-7, TS-11 (rejected-path containment; "rework" / "append" absence) |
| NFR5 | task0001, task0003 | TS-7 (retained gate literals) |
| NFR6 | task0001, task0003 | TS-7 (no bare `git … commit` / `git … add -A` line) |
| NFR7 | task0001, task0002, task0003 | TS-8, TS-9 — every new module is standard-library-only, lives in the repository-root `tests/`, and is picked up by the discovery command |
| NFR8 | task0001, task0002, task0003 | TS-7, plus the manual diff-scope check below (no runtime script, hook or shell behaviour modified) |

Every requirement maps to at least one task and at least one test scenario;
there are no uncovered requirement IDs and no `tbd` requirements.

## E2E Testing

The project has no E2E framework and this feature adds no runtime behaviour to
exercise (`project.components.main.e2e_test_command` is empty). Nothing to run.

## Manual Testing (E2E Not Possible)

- [ ] Read the edited I.2.c "route back to planning" bullet end-to-end and
      confirm the gate, the write set and the cleanup read as one instruction
      naming one derivation source — not three locally-correct sentences
      (AC-1).
- [ ] Walk SPEC.md's EC-1 .. EC-6 against the edited paragraph and confirm
      each edge case is decidable from the text alone, in particular EC-1
      (journal `merged` + workflow.yaml `failed` → blocked, not cleaned up)
      and EC-3 (a `merged` claim failing `git merge-base --is-ancestor` does
      not block).
- [ ] Re-walk the three verify-round-1 failed items against the reworked text
      (task0003): MANUAL-1 — the write set now covers the same task set the
      postcondition and `replace_all` are judged over, including a task
      workflow.yaml reports `failed` with no journal event; MANUAL-2 — the
      not-merged claim states only what the two sources establish, and the
      branch-advanced-without-journal-event window is recorded as a residual;
      MANUAL-3 — following I.2.a's pointer to the I.2.c gate lands on I.2.c,
      and the carve-out / gate / reconciled-state chain has a stated
      termination point.
- [ ] Read the Branch & Worktree Model's exit-4 bullet and Step I.2.a's
      recycled-task-id paragraph and confirm both still describe the gate
      correctly now that it has two union rules (FR5, FR6).
- [ ] Inspect `git diff` for `em-workflow/references/implement-phase.md` and
      confirm there is no reflow-only hunk outside the edited sentences
      (NFR2 belt-and-braces beyond the three asserted literals).
- [ ] Run `git diff --name-only` against the implement base commit
      (`c8843c9c086323c5378c6b3abe89dc63e5c02a40`) and confirm the changed set
      is exactly: `em-workflow/references/implement-phase.md`, the two
      `.claude-plugin` manifests, the two new modules under `tests/`, this
      feature's `feature-docs/` and `test-docs/` records — and nothing under
      `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/skills/` or
      `em-workflow/agents/` (NFR8).

No mockup comparison item: the design step is `skipped` for this feature (no
UI, no rendered output, no design-system inputs).

## Performance / Security Verification

Not applicable. The change is documentation, registry metadata and test code
only; no runtime, script, hook or shell behaviour is modified (NFR8), and no
dependency is added (`project.license` is `none`, so no license constraint
applies).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 .. TS-12) | 12 | 12 | 0 | 0 |
| Success criteria (AC-1 .. AC-7) | 7 | 7 | 0 | 2 (AC-2 and AC-6 additionally get a manual read-through / diff check) |
| Functional requirements (FR1 .. FR8) | 8 | 8 | 0 | 0 |
| Non-functional requirements (NFR1 .. NFR8) | 8 | 8 | 0 | 1 (NFR8's diff-scope check) |
| Manual-only checks | 6 | 0 | 0 | 6 |
