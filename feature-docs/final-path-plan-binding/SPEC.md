# Feature: final-path-plan-binding

Requirements document: `feature-docs/final-path-plan-binding/REQUIREMENTS.md`

## Overview

On the final-path correction entry, the plan document the validator compares
with the canonical text must be the same document the implementer is given as
its instructions. This feature rejects correction entries whose plan is not
bound to an existing `tasks/{T}.md` (interim mitigation), and makes the
implementer's plan path resolve from `tasks.{T}.plan` behind a fail-closed
path check (root fix).

## Objectives

- On the final-path correction entry, the plan document that the validator
  compares with the canonical text is the same document the implementer is
  given as its instructions, so the attack scenario (canonical text in a decoy
  plan, other instructions in an unregistered `tasks/{T}.md`) does not succeed.
- The canonical-text requirement of TM-11 (feature
  final-path-correction-medium-fixes) reaches the implementer's actual
  instruction input.

## User Stories

### US1: Correction entries cannot split the validated plan from the implementer's plan
As an em-workflow user, I want a correction entry whose plan differs from an
existing `tasks/{T}.md` to be rejected, so that the attack scenario does not
succeed.

**Acceptance Criteria:**
- [ ] AC-1: With plan `tasks/task0003-safe.md` (canonical text) and an
  unregistered `tasks/task0003.md` present, the correction-entry patch yields
  `path-correction-entries` naming `task0003` and `tasks/task0003.md`, both
  through `validate_workflow_patch(dry_run=True)` and
  `validate_worker_result`. (FR1)
- [ ] AC-2: An entry with plan `tasks/{T}.md` and canonical text, with no other
  file, yields no error; an entry with a free plan path and no `tasks/{T}.md`
  present yields no new error. (FR1)
- [ ] AC-3: An entry whose plan is a `TASK.md` path while `tasks/{T}.md` exists
  is rejected with `path-correction-entries`; a directory and a dangling
  symlink at `tasks/{T}.md` are rejected the same way. (FR1, NFR2)
- [ ] AC-6: `workflow-patch.md`'s path-correction-entries bullet states the FR1
  rejection, and the existing docs tests pass. (FR4, NFR5)

### US2: The implementer reads the registered plan
As an em-workflow user, I want the implementer's `task_plan_path` to be
resolved from `tasks.{T}.plan` and checked fail-closed, so that the
canonical-text requirement reaches the implementer's actual instruction input.

**Acceptance Criteria:**
- [ ] AC-4: `implement-phase.md`'s prompt payload gives `task_plan_path` from
  `tasks.{T}.plan`; the fixed `tasks/{T}.md` payload text is gone. (FR2)
- [ ] AC-5: `implement-phase.md` states the FR3 path check (safe relative path,
  no symlink component, realpath containment, Cc/U+2028/U+2029 on stored and
  resolved values, all selected tasks) and its abort handling, before any
  implementer launch prompt is built. (FR3)
- [ ] AC-8: `batch-terminal-line.md` binds the FR3 stop to the
  stop-condition-3 row and `step_needs_intervention`. (FR6)

### US3: Regression coverage
As an em-workflow user, I want the behavior pinned by tests, so that the fix
stays in place.

**Acceptance Criteria:**
- [ ] AC-7: `python3 -m unittest discover -s tests` passes. (FR5, NFR1, NFR3,
  NFR5)

## Technical Requirements

### Functional Requirements

- **FR1:** Correction-entry rejection of an unbound `tasks/{T}.md`. In
  `em-workflow/scripts/validate-worker-output.py`, `_correction_entries_errors`
  rejects an item of `tasks_patch.entries` with `path-correction-entries`
  (error carries `task_id` and path `tasks/{T}.md`) when a directory entry
  `tasks/{T}.md` exists now under the feature directory and the item's `plan`,
  compared after `path_segments` normalization, is not `tasks/{T}.md`. Any kind
  of entry counts as existing (regular file, directory, symlink including a
  dangling one). The check applies on the correction entry only, like the
  other path-correction-entries limits; the Re-planning path and other states
  are unchanged. This constraint applies only to correction entries where
  `tasks/{T}.md` co-exists with a different plan; it does not require the fixed
  `tasks/{T}.md` name for every plan elsewhere.
- **FR2:** Implementer plan path resolved from `tasks.{T}.plan`.
  `em-workflow/references/implement-phase.md` (prompt payload, currently line
  518) resolves `task_plan_path` as the absolute path of the integration
  worktree's `feature-docs/{feature}/{tasks.{T}.plan}`, not the fixed
  `feature-docs/{feature}/tasks/{T}.md`. This matches
  `em-workflow/references/phases/create-plan-phase.md` section 2a (lines
  103-107), including the minimal-tier `TASK.md` plan. The stored
  `tasks.{T}.plan` value is relative to `feature-docs/{feature}` (e.g.
  `TASK.md` at the minimal tier, `tasks/task0001.md` otherwise);
  `create-plan-phase.md` section 2a's wording is clarified to state the stored
  value and the resolved absolute path separately.
- **FR3:** Fail-closed check of the resolved plan path. Before any implementer
  launch prompt is built, `implement-phase.md` checks the `tasks.{T}.plan`
  value of every selected task (not only the first): it is a safe relative
  path (not absolute, no `..` segment, the same separator / empty-segment /
  `.` rules as the validator's safe-relative-path check), no path component
  (intermediate ones included) is a symlink, its realpath stays inside
  `feature-docs/{feature}`, and neither the stored value nor the resolved
  absolute path contains a character of Unicode category Cc, U+2028 or
  U+2029. When any selected task fails, the phase aborts with the same
  terminal handling as the existing `worktree_path` control-character check:
  report the offending task IDs, build no implementer launch prompt for any
  selected task, launch no implementer, write implement `failed` with
  `failed_kind: decision` in one commit, never sanitize and never fall back to
  `tasks/{T}.md`; tasks launched by an earlier refill are neither waited for,
  cancelled nor rolled back.
- **FR4:** Contract text for the new rejection.
  `em-workflow/references/workflow-patch.md`, "Limits on entries",
  path-correction-entries bullet, states the FR1 rejection. Every existing
  `LIMITS_NEEDLES` string of `tests/test_final_path_correction_docs.py` stays,
  and the limits paragraph adds no numbered item.
- **FR5:** Regression tests. `tests/test_final_path_correction.py` gets a
  reproduction of the attack scenario: a new entry with plan
  `tasks/{T}-safe.md` holding `canonical_correction_plan` output, plus a
  present `tasks/{T}.md` with other text, raises `path-correction-entries`
  under `validate_workflow_patch(dry_run=True)` and `validate_worker_result`;
  plan equal to `tasks/{T}.md` with canonical text and no other file still
  passes; a `TASK.md` plan with `tasks/{T}.md` present is rejected. A docs test
  pins that `implement-phase.md` resolves `task_plan_path` from
  `tasks.{T}.plan` and no longer contains the fixed `tasks/{T}.md` payload
  line.
- **FR6:** Batch stop binding for the plan-path check.
  `em-workflow/references/batch-terminal-line.md`'s named exception that binds
  the Step I.2.a control-character check stop to the stop-condition-3 row and
  `step_needs_intervention` also covers the FR3 plan-path check stop, so a
  batch run reports it as `step_needs_intervention` and not `unmapped_stop`.

### Non-Functional Requirements

- **NFR1 - Git access:** `_correction_entries_errors` reads git only through
  `_read_base_document`; the new check uses a working-tree lstat/lexists of
  `feature_dir` and contains none of `_run_git`, `subprocess`, `ls-tree`,
  `cat-file` (pinned by
  `TestEntryLimits.test_entry_files_reach_git_only_through_the_base_readers`).
- **NFR2 - Fail-closed:** An unreadable or indeterminate state of
  `tasks/{T}.md` is treated as existing; an entry is never passed on a
  doubtful read.
- **NFR3 - Test dependencies:** Tests use only the Python standard library
  (`unittest`), per `test/README.md`.
- **NFR4 - Version:** No change to plugin version fields
  (`.claude/rules/core-plugin-version-bump.md`); this is a patch-level fix.
- **NFR5 - Existing tests:** Existing tests in
  `tests/test_final_path_correction.py` and
  `tests/test_final_path_correction_docs.py` keep passing unchanged.

## Implementation Approach

### Architecture

Not applicable (no UI, no service layers). Changes are confined to a validator
script, reference documents and unit tests.

**Component Diagram:**
```
validate-worker-output.py
  _correction_entries_errors   -- FR1 check (working-tree lstat/lexists of feature_dir)
references/
  workflow-patch.md            -- FR4 contract text
  implement-phase.md           -- FR2 task_plan_path resolution, FR3 path check and abort
  phases/create-plan-phase.md  -- FR2 wording of section 2a (stored value vs. resolved path)
  batch-terminal-line.md       -- FR6 batch stop binding
tests/
  test_final_path_correction.py       -- FR5 attack reproduction
  test_final_path_correction_docs.py  -- FR5 docs test
```

### Data Flow

```
correction entry (tasks_patch.entries[].plan)
  -> _correction_entries_errors: tasks/{T}.md exists (any kind, or indeterminate)
       and normalized plan != tasks/{T}.md  -> path-correction-entries
implement phase
  -> FR3 check of tasks.{T}.plan for every selected task
       fail -> abort (implement failed, failed_kind: decision, one commit)
       pass -> task_plan_path = absolute integration-worktree path of
               feature-docs/{feature}/{tasks.{T}.plan} -> implementer prompt
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `_read_base_document` / `_read_current_document` in
  `validate-worker-output.py`: the only git access path of
  `_correction_entries_errors` (NFR1) and the feature-dir-relative plan read.
- `path_segments` normalization in `validate-worker-output.py`: used for the
  FR1 plan comparison.
- The validator's safe-relative-path check: the FR3 relative-path rules mirror
  it.
- The existing `worktree_path` control-character check (Step I.2.a) of
  `implement-phase.md`: FR3 reuses its terminal handling.

**External Dependencies:**
- None. Tests use only the Python standard library (`unittest`).

### File Structure

```
em-workflow/
├── scripts/
│   └── validate-worker-output.py        # FR1
└── references/
    ├── workflow-patch.md                # FR4
    ├── implement-phase.md               # FR2, FR3
    ├── batch-terminal-line.md           # FR6
    └── phases/
        └── create-plan-phase.md         # FR2 (section 2a wording)
tests/
├── test_final_path_correction.py        # FR5
└── test_final_path_correction_docs.py   # FR5
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
- [ ] TS-1: Attack reproduction: canonical decoy plan + unregistered
  `tasks/{T}.md` - `path-correction-entries` (validator and worker-result
  paths).
- [ ] TS-2: Bound plan: plan `tasks/{T}.md` with canonical text - no error.
- [ ] TS-3: Free plan path, `tasks/{T}.md` absent - no new error (existing
  TestCreatedDocuments / TestEntryLimits behavior kept).
- [ ] TS-4: `tasks/{T}.md` as directory, dangling symlink, and with a `TASK.md`
  plan - rejected.
- [ ] TS-5: Plan path spellings normalizing to `tasks/{T}.md` (e.g.
  `./tasks/{T}.md`) - treated as bound.
- [ ] TS-6: Re-planning path and other states - the new check does not run.

### Integration Tests
- [ ] TS-7: Docs test: `implement-phase.md` resolves `task_plan_path` from
  `tasks.{T}.plan` and states the FR3 abort.
- [ ] TS-8: Code-read test: `_correction_entries_errors` still reaches git only
  through the base readers.
- [ ] TS-9: Docs test: `batch-terminal-line.md` binds the FR3 stop to
  `step_needs_intervention`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- Covered by TS-4, TS-5 and TS-6.

### Performance Tests
- Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** FR1 rejects a correction entry whose plan is not bound
  to an existing `tasks/{T}.md`; FR3 checks every selected task's
  `tasks.{T}.plan` (safe relative path, no symlink component, realpath
  containment, no Cc / U+2028 / U+2029 in the stored and resolved values)
  before any implementer launch prompt is built.
- **Data Protection:** Not applicable.
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.
- **Fail-closed:** An unreadable or indeterminate state of `tasks/{T}.md` is
  treated as existing (NFR2); a failed FR3 check is never sanitized and never
  falls back to `tasks/{T}.md`.

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| `path-correction-entries` | Correction entry whose `plan` (after `path_segments` normalization) is not `tasks/{T}.md` while `tasks/{T}.md` exists or its state is indeterminate (FR1, NFR2) | - | Error carries `task_id` and `tasks/{T}.md` |
| FR3 plan-path check abort | A selected task's `tasks.{T}.plan` fails the FR3 check | - | Offending task IDs are reported |

### Error Flow

```
FR1: violation -> path-correction-entries (task_id, tasks/{T}.md)
FR3: any selected task fails -> report offending task IDs
     -> build no implementer launch prompt, launch no implementer
     -> write implement failed (failed_kind: decision) in one commit
     -> tasks launched by an earlier refill: not waited for, not cancelled, not rolled back
     -> batch: step_needs_intervention (stop-condition-3 row), not unmapped_stop (FR6)
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC-1 through AC-8 are met

## Assumptions

- A1: Both the interim mitigation (FR1) and the root fix (FR2, FR3) are in
  scope for this feature.
- A2: `tasks.{T}.plan` values are relative to `feature-docs/{feature}` (e.g.
  `tasks/task0001.md`), as the validator reads them with
  `_read_current_document(feature_dir, plan)` and the test fixtures register
  them.
- A3: The FR1 existence check uses the current working tree of the feature
  directory, not the base commit.
- A4: Existing tests that pin the path-correction-entries behavior and the
  TM-9 code-read constraint are preserved invariants.
- A5: The FR3 abort reuses the terminal handling of the existing
  `worktree_path` control-character check (implement step failed,
  `failed_kind: decision`, one commit via `commit-docs.sh`).
- A6: Codex consultation (batch): scope includes both interim mitigation and
  root fix; `tasks.{T}.plan` is feature-dir-relative; FR3 reuses the
  control-character check's terminal handling. Each choice matched analyst
  assumptions A1, A2, A5.
- A7: FR3's path check mirrors the validator's existing plan-document checks
  (symlink in any component rejected, realpath containment), and its
  character check covers the full Cc set plus U+2028/U+2029 on both stored and
  resolved values.
- A8: The batch stop-reason binding for the FR3 stop must be stated explicitly
  (FR6), since `batch-terminal-line.md` limits its named exception to the
  control-character check alone.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- Requirements: `feature-docs/final-path-plan-binding/REQUIREMENTS.md`
- `em-workflow/references/workflow-patch.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/phases/create-plan-phase.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/scripts/validate-worker-output.py`
