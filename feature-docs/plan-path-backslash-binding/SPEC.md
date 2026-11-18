# Feature: plan-path-backslash-binding

## Overview

The implement phase builds `task_plan_path` (Step I.2.a of
implement-phase.md) by joining the stored `tasks.{T}.plan` string as-is,
while the validator (`scripts/validate-worker-output.py`) reads the plan
after normalizing that value with `path_segments`. This feature makes the
phase documents derive `task_plan_path`, and apply Plan-path check rules 2
and 3, from the same normalized segments, so the plan handed to the
implementer is the file the validator checked. Requirements:
`feature-docs/plan-path-backslash-binding/REQUIREMENTS.md`.

## Objectives

- The plan handed to the implementer is the same file as the plan the
  validator checked; changing the spelling of `tasks.{T}.plan` cannot hand
  an unvalidated plan to the implementer.
- Even without malicious intent, a backslash-spelled plan value does not
  hand a nonexistent path to the implementer.

## User Stories

Not applicable. The change is limited to phase documents and tests; no
user-facing flow changes.

## Technical Requirements

### Functional Requirements
- **FR1:** task_plan_path is built from the normalized segments.
  In the Step I.2.a payload of implement-phase.md, `task_plan_path` is the
  absolute path formed by joining, onto the integration worktree's
  `feature-docs/{feature}/`, the segments obtained by normalizing the stored
  value `tasks.{T}.plan` with `path_segments` of
  `scripts/validate-worker-output.py`. The stored string is not joined
  as-is. `path_segments` is cited by reference; the document does not
  restate its procedure.
- **FR2:** Plan-path check rules 2 and 3 apply to the same resolved path.
  Rule 2 (the symlink check) and rule 3 (the realpath containment check)
  judge the same path that FR1 passes as `task_plan_path`, i.e. the
  normalized segments joined onto `feature-docs/{feature}`. Rule 1
  (`is_safe_relative_path` and at least one segment) and rule 4 (control
  characters) are unchanged. There remain exactly four rules, each a single
  one-sentence bullet.
- **FR3:** create-plan-phase.md section 2a is aligned.
  The sentence in section 2a stating how the implement phase resolves the
  stored value to an absolute path is changed to the same content as FR1
  ("join the segments normalized by `path_segments`"). Plan-path check stays
  cited, not restated. The sentence stating the stored value and the
  sentence stating the resolved absolute path remain separate sentences.
- **FR4:** The validator's resolution is unchanged.
  The behavior of `_resolve_contained_relative_path`,
  `_plan_is_bound_to_task_md`, `path_segments` and `is_safe_relative_path`
  in `scripts/validate-worker-output.py` does not change. `./tasks/{T}.md`,
  `tasks//{T}.md`, `tasks/./{T}.md` and `tasks\{T}.md` remain bound to
  `tasks/{T}.md`.
- **FR5:** The document tests follow the new wording.
  In `tests/test_final_path_correction_docs.py`, the wording pinned for the
  `task_plan_path` line, Plan-path check rules 2 and 3, and the section 2a
  resolution sentence is updated to match FR1 through FR3. The pre-fix
  "join the stored value as-is" wording is detected as a negative sample.

### Non-Functional Requirements
- **NFR1:** The Plan-path check paragraph satisfies the phrasing
  constraints pinned by `tests/test_final_path_correction_docs.py`:
  - it contains none of the `PP_FORBIDDEN_PHRASES`;
  - each sentence contains at most two condition markers
    (`PP_CONDITION_MARKERS`: strictly below / existing directory / realpath /
    `..` / empty component / link component / symbolic link);
  - it does not use uppercase EVERY or ALL;
  - it sits immediately after the Control-character check paragraph and
    immediately before the approval-gate paragraph.
- **NFR2:** Tests use only the Python standard library `unittest`, and
  `python3 -m unittest discover -s tests` passes in full.
- **NFR3:** The em-workflow version is not changed.

## Implementation Approach

### Architecture

The fix is the root fix only: the absolute plan path is built from the
normalized segments, and validation and launch use the same resolution
result. No rule rejecting a stored value that differs from its canonical
form is added to Plan-path check.

**Component Diagram:**
```
workflow.yaml tasks.{T}.plan (stored value)
        │
        ▼
path_segments (scripts/validate-worker-output.py, cited)
        │  normalized segments
        ├──► validator: _resolve_contained_relative_path  (unchanged, FR4)
        │
        └──► implement-phase.md Step I.2.a
               task_plan_path = feature-docs/{feature}/ + segments  (FR1)
               Plan-path check rules 2, 3 judge this same path      (FR2)
```

### Data Flow

```
stored plan value → path_segments → segments ─┬→ validator reads tasks/{T}.md
                                              └→ task_plan_path (same file)
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `scripts/validate-worker-output.py`: `path_segments` is cited as the
  normalization; `_resolve_contained_relative_path` is the reference result
  the document's derivation must match.

**External Dependencies:**
- None (Python standard library `unittest` only).

### File Structure

Files the requirements name:

```
implement-phase.md                       # Step I.2.a task_plan_path line; Plan-path check rules 2, 3 (FR1, FR2)
create-plan-phase.md                     # section 2a resolution sentence (FR3)
scripts/validate-worker-output.py        # unchanged (FR4)
tests/test_final_path_correction_docs.py # pinned wording updated (FR5)
tests/test_final_path_correction.py      # existing tests must keep passing (AC-5)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

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
- [ ] TS-1: Document test for the `task_plan_path` line - The current line
  contains wording that shows joining the normalized segments and satisfies
  the line-position condition (after `worktree_path`, before
  `implementation_md_path`, before the `## Untrusted data` line). A sample
  of the pre-fix line (joining the stored string as-is) is detected as a
  problem.
- [ ] TS-2: Document test for Plan-path check - The rule 2 and rule 3
  bullets contain wording that makes the normalized joined path the target
  of the check. The paragraph has four bullets, one sentence each, and
  satisfies the phrasing constraints (forbidden phrases, at most two
  condition markers per sentence, no uppercase quantifiers). A sample with
  one rule removed and a sample with the wording removed are detected.
- [ ] TS-3: Document test for create-plan-phase.md section 2a - The
  resolution sentence contains the new wording and the Plan-path check
  citation, and is a separate sentence from the stored-value sentence. A
  sample of the pre-fix section 2a is detected.

### Integration Tests
- [ ] TS-4: Behavior test against the decoy - In a temporary directory,
  `feature-docs/{feature}/tasks/` holds the canonical `task0003.md` and a
  decoy literally named `\task0003.md`. For plan `tasks/\task0003.md` and
  for plan `tasks\task0003.md`, the derivation the documents define
  (joining the segments normalized by `path_segments`) equals the path
  returned by the validator's `_resolve_contained_relative_path`, and does
  not point at the decoy.
- [ ] TS-5: Regression - The existing `tests/test_final_path_correction.py`
  (including the spelling binding of AC-5) and the remaining tests in
  `tests/test_final_path_correction_docs.py` pass.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- Spellings `./tasks/{T}.md`, `tasks//{T}.md`, `tasks/./{T}.md` and
  `tasks\{T}.md` remain bound to `tasks/{T}.md` (FR4; covered by TS-5).
- A file literally named `\task0003.md` under `tasks/` is never the target
  of `task_plan_path` (covered by TS-4).

### Acceptance Criteria
- [ ] AC-1: The `task_plan_path` line in the Step I.2.a payload of
  implement-phase.md shows the absolute path formed by joining the segments
  normalized by `path_segments` onto `feature-docs/{feature}/`. It does not
  show joining the stored string as-is. The line position is unchanged:
  immediately after `worktree_path`, immediately before
  `implementation_md_path`, and before the `## Untrusted data` line.
- [ ] AC-2: Plan-path check rules 2 and 3 take the same normalized joined
  path as `task_plan_path` as their target. There are four rules, one
  sentence each, satisfying the NFR1 phrasing constraints.
- [ ] AC-3: The resolution sentence in create-plan-phase.md section 2a
  states that the normalized segments are joined and cites Plan-path check.
  The stored-value sentence and the resolved-absolute-path sentence are
  separate sentences.
- [ ] AC-4: The attack scenario does not hold. Put the
  `canonical_correction_plan` output at `tasks/task0003.md`, put different
  content at the literal name `\task0003.md` under `tasks/`, and set plan to
  `tasks/\task0003.md` (or `tasks\task0003.md`). The `task_plan_path`
  derived as the documents define points at the same file as
  `tasks/task0003.md`, which the validator's
  `_resolve_contained_relative_path` reads, and not at `\task0003.md`.
- [ ] AC-5: The validator's existing behavior is unchanged. Existing tests,
  including `TestPlanBindingAdmits.test_every_spelling_of_tasks_t_md_is_bound`
  in `tests/test_final_path_correction.py`, pass unchanged.
- [ ] AC-6: Given the pre-fix wording as a sample ("joined with the stored
  tasks.{T}.plan value" at implement-phase.md:546, and "joined with that
  value" in create-plan-phase.md section 2a), the updated document tests
  detect it as a problem.
- [ ] AC-7: `python3 -m unittest discover -s tests` passes in full.

## Security Considerations

- **Input Validation:** The plan handed to the implementer is the file the
  validator checked, for every spelling of `tasks.{T}.plan` the validator
  accepts (FR1, FR2, AC-4). Plan-path check gains no rejection rule for
  non-canonical spellings (assumption A1).

## Error Handling

Not applicable. No new error path is added.

## Performance Optimization

Not applicable.

## Assumptions

- **A1:** The fix is the root fix only (build the absolute path from the
  normalized segments; validation and launch use the same resolution
  result). No rule rejecting a stored value that differs from its canonical
  form (the interim mitigation) is added to Plan-path check.
- **A2:** The validator's behavior of treating alternate spellings of
  `tasks/{T}.md` (`./`, `//`, `/./`, backslash) as bound is kept.
- **A3:** implement-phase.md cites `path_segments` by reference and does not
  restate the normalization procedure.
- **A4:** The version's minor / major is not raised. The patch is raised by
  Actions on push to main.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 through AC-7 are satisfied

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/plan-path-backslash-binding/REQUIREMENTS.md`
- implement-phase.md: Step I.2.a, Plan-path check
- create-plan-phase.md: section 2a
- `scripts/validate-worker-output.py`
- `tests/test_final_path_correction.py`, `tests/test_final_path_correction_docs.py`
