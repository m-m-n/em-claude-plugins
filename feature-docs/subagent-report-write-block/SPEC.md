# Feature: subagent-report-write-block

## Overview

When an em-workflow plan makes a file whose name starts with REPORT an
implementer's artifact, Claude Code's Write tool rejects every write by the
subagent and implement stops. This feature stops such plans at validation,
makes the implementer fail immediately on the rejection, stops the parent from
retrying the same cause, and defines how to correct the final path of an
existing plan. Requirements are stated in
`feature-docs/subagent-report-write-block/REQUIREMENTS.md`.

## Objectives

- A report artifact that follows the plan reaches the parent branch without
  stopping on the implementer's Write rejection.
- A plan holding a new file with a matching name is stopped by validation
  before implement.
- A rejection does not use up retries on the same cause; fixing the cause is
  the resume condition.
- The procedure to resume tcp-send-path-fr8-race-audit is decided.

## User Stories

### US1: Report artifacts reach the parent branch
As an em-workflow user, I want a planned report artifact to be written and
merged, so that implement does not stop on the Write rejection.

**Acceptance Criteria:**
- [ ] AC-2: A plan whose report artifact has a non-matching name passes
      validation, is not rejected by the implementer's Write, and is merged
      into the parent branch.
- [ ] AC-3: A plan that updates a matching-name file existing at the base
      commit passes validation.

### US2: Matching names are stopped at validation
As an em-workflow user, I want a plan with a new matching name to be rejected
by validation, so that it does not reach implement.

**Acceptance Criteria:**
- [ ] AC-1: A plan holding a new `test-docs/<feature>/REPORT.md` in tasks'
      files is rejected by validation and does not proceed to implement.
- [ ] AC-7: Tests that detect a recurrence exist and
      `python3 -m unittest discover -s tests` passes.

### US3: Fixing the cause is the way to resume
As an em-workflow user, I want a rejection to stop without same-cause retries
and to resume after the final path is corrected, so that a run does not spend
retries on a cause a retry cannot fix.

**Acceptance Criteria:**
- [ ] AC-4: A correction meeting the FR5 conditions is applied with files, the
      task body, the verification conditions and the references in tests
      aligned; a correction that fails even one condition is not applied.
- [ ] AC-5: On a re-run that names the feature, when implement is failed and an
      FR3 violation remains, the run enters FR5, and the target task can
      restart after it is applied. The entry is not taken inside the failed
      run.
- [ ] AC-6: On a rejection the implementer returns `status: failed` with the
      target path and the rejection text, and the parent does not retry the
      same cause, including on a resume after an interruption.

### US4: tcp-send-path-fr8-race-audit can resume
As an em-workflow user, I want a decided resume procedure for
tcp-send-path-fr8-race-audit, so that the feature can resume from its actual
state.

**Acceptance Criteria:**
- [ ] AC-8: This SPEC holds the resume procedure for
      tcp-send-path-fr8-race-audit, including the check of the actual state and
      the entry from failed.

## Technical Requirements

### Functional Requirements

- **FR1:** Plan naming rule. implementation-planner and rework-planner do not
  make a file with an FR2 matching name that does not exist at the base commit
  an artifact of tasks' files, a task body, an acceptance criterion or
  VERIFICATION.md. A report artifact takes a name that does not match FR2. A
  plan holds no step that writes under another name and then renames. A task
  that updates a matching-name file existing at the base commit states in its
  body that the update is made with Edit. The rule text lives in one section of
  `em-workflow/skills/plan-writing/SKILL.md`; other documents cite it.
- **FR2:** Definition of a matching name. Only the file name, the final path
  segment, is judged. A file name matching the regular expression
  `/^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$/i` is a matching name. Case is
  ignored. Directory names are not judged.
- **FR3:** Rejecting new matching names at validation.
  `em-workflow/scripts/validate-worker-output.py`, when validating a workflow
  patch, rejects a matching name in the files of `tasks_patch.entries` that
  does not exist at the base commit (exit 1, a dedicated error code, showing
  the task id and the path). This applies to both replace_planning and
  append_rework, on every tier. A matching name existing as a regular file at
  the base commit passes as an update. Under `--dry-run-apply` the same check
  also runs on the files of tasks in carried_task_ids whose status is not
  merged.
- **FR4:** Base input contract. The target repository is the integration
  worktree. The base commit is the full commit ID of the tip of
  `em-workflow/{feature}/integration`, resolved by the orchestrator before
  validation runs. validate-worker-output.py receives these two values as
  arguments, and every validation call from create-plan, rework and the FR5
  correction passes them. A patch without a matching name does not read the
  two values and may omit them. A patch with a matching name where either value
  is missing or cannot be resolved exits 2 and does not pass.
- **FR5:** Procedure to correct the final path of an existing plan. The plugin
  defines, as a rule, the procedure that changes a matching name in an existing
  plan to a non-matching name. One correction moves the old path to the new
  path across `tasks.{T}.files`, the Files section, body and acceptance
  criteria of `tasks/{T}.md`, IMPLEMENTATION.md, the verification conditions of
  VERIFICATION.md, and the references in tests.
  - Ownership: implementation-planner corrects the plan documents and proposes
    the files change; the orchestrator applies it to workflow.yaml. The
    implementer and rework-planner do not correct the plan.
  - References in tests: an unmerged reference is corrected by that task's
    implementer following the corrected plan; a merged reference is corrected
    by a new task added in the same correction.
  - Conditions, all required:
    1. No task is in-flight.
    2. Neither the target task's status nor its final journal event is merged.
    3. The old path is a matching name and does not exist at the base commit.
    4. The new path is not a matching name, passes `is_safe_relative_path`, and
       does not exist at the base commit.
    5. The change is limited to replacing path strings and does not change the
       meaning of requirements or acceptance criteria.
  - A correction that fails any condition is not applied.
  - The procedure is defined in `references/workflow-patch.md` as an exception
    to the rule that copies a carried task's record verbatim, and it is also
    usable in re-planning entered through route back.
- **FR6:** Entry from failed (status: assumed, see A1). At the start of a
  develop re-run that names the feature, the orchestrator judges whether
  implement is failed and an FR3 violation remains in the files of a failed
  task. If so, it enters the FR5 procedure before stop condition 3, even when
  failed_kind is decision. This entry is not taken inside the failed run. After
  FR5 is applied, one write set sets implement to pending and failed_kind to
  null, makes the target task startable, and removes the retry-consumption
  record. The target task's worktree and branch and merged tasks are not
  touched. A worktree with uncommitted changes is not discarded automatically.
  When the FR5 conditions are not met, workflow.yaml is not changed and the run
  stops at stop condition 3.
- **FR7:** Implementer's immediate failure. When Write is rejected for an FR2
  name, the implementer stops work and immediately returns `status: failed`. A
  dedicated report field carries the repository-relative target path and the
  rejection text, and merge_script is not run. The implementer does not work
  around the rejection by renaming, writing under another name, creating the
  file with Edit, writing through Bash, or asking the parent to write it. This
  rule also applies to a Write rejection on a file existing at the base commit.
  A matching-name file existing at the base commit is updated with Edit from
  the start, not by switching to Edit after a rejection.
- **FR8:** Parent retry suppression and resume condition. On an FR7 report, the
  parent does not retry the same cause, in interactive or batch. In-flight
  tasks are collected as before. Batch proceeds to abort phase without
  consuming an automatic retry, with failed_kind set to decision. Interactive
  removes retry from the options. The resume condition is fixing the cause,
  that is, completing FR5. The parent records the cause in `tasks.{T}.notes`
  with a wake commit and does not auto-retry on a resume after an interruption
  either. The stop report carries the target path, the rejection text and the
  resume condition. Handling of failures from other causes does not change.
- **FR9:** Recurrence-detecting tests. `tests/` gains tests for the FR2
  judgment, the FR3 rejection and pass, the FR4 missing input, and the FR5
  conditions. Document contract tests check that the plan-writing, implementer,
  implement-phase and batch-mode documents hold the FR1, FR7 and FR8 rules. A
  test checks that a patch equivalent to the plan in the reproduction steps is
  rejected. `references/fixtures/` covers the validation script's rule.
- **FR10:** Resume procedure for tcp-send-path-fr8-race-audit. This SPEC holds
  the resume procedure for the web-sip-phone feature
  tcp-send-path-fr8-race-audit; the plugin does not. See
  "Resume Procedure: tcp-send-path-fr8-race-audit".

### Non-Functional Requirements

- **NFR1 - No bypass of the rejection:** No setting, hook, rename procedure or
  parent-writes-instead procedure that bypasses Claude Code's Write rejection
  is introduced.
- **NFR2 - Existing behavior:** Validation results for plans without a matching
  name, and the handling of implement failures from other causes, do not
  change. All existing tests pass.
- **NFR3 - Single definition:** The regular expression is implemented in one
  place, validate-worker-output.py. The rule text is in one section of
  plan-writing and other documents cite it. A test pins the document's regular
  expression to the implementation's constant.
- **NFR4 - Test execution:** Tests use the standard library unittest and run
  with `python3 -m unittest discover -s tests`. Verification that uses git runs
  on a disposable repository in a temporary directory and does not touch the
  real Claude Code configuration.
- **NFR5 - Input handling:** files values are untrusted input and are passed to
  git without going through a shell. The base commit accepts only a full
  hexadecimal commit ID.
- **NFR6 - Scope and content:** The implementation of this feature does not
  write to web-sip-phone. Deliverables contain no Notion URL and no absolute
  path under the home directory.

## Implementation Approach

### Architecture

**Component Diagram:**

```
plan-writing SKILL.md (rule text, FR1 + FR2)
   ^ cited by planner documents, implementer.md, implement-phase, batch-mode

validate-worker-output.py (regex constant, FR2 + FR3 + FR4)
   ^ called by the orchestrator at create-plan, rework and FR5 correction
   ^ constant pinned to the plan-writing regex by a test (NFR3)

references/workflow-patch.md (FR5 exception to verbatim carried records)
   ^ used by the FR6 entry and by re-planning through route back
```

### Data Flow

Plan validation:

```
planner -> workflow patch -> validate-worker-output.py -> workflow.yaml -> implement
                              ^ integration worktree + base commit (FR4)
                              | new matching name: exit 1
                              | missing or unresolvable base input: exit 2
```

Write rejection:

```
implementer Write rejected -> status: failed + target path + rejection text
  -> parent: no same-cause retry -> tasks.{T}.notes via wake commit
  -> stop report (target path, rejection text, resume condition)
```

Resume from failed:

```
develop re-run naming the feature -> FR6 judgment -> FR5 conditions
  met:     planner corrects documents and proposes files -> orchestrator applies
           -> one write set restores implement and the target task
  not met: workflow.yaml unchanged -> stop condition 3
```

### API Design

#### validate-worker-output.py

- New inputs: the target repository and the base commit, as arguments (FR4).
- A patch without a matching name does not read them and may omit them.
- Exit 1: a new matching name, with a dedicated error code, the task id and the
  path (FR3).
- Exit 2: a patch with a matching name whose two values are missing or
  unresolvable (FR4).

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/validate-worker-output.py`: FR2 constant, FR3, FR4.
- `em-workflow/skills/plan-writing/SKILL.md`: FR1 and FR2 rule text.
- `em-workflow/agents/implementer.md`: FR7.
- `em-workflow/references/workflow-patch.md`: FR5.
- implement-phase, batch-mode, worktree-task-workflow and the develop entry
  documents: FR6, FR7, FR8.

**External Dependencies:**
- git: resolves whether a path exists at the base commit (FR3, FR4).
- Python standard library unittest: tests (NFR4).

### File Structure

```
em-workflow/
├── agents/
│   └── implementer.md               # FR7
├── references/
│   ├── fixtures/                    # FR9
│   └── workflow-patch.md            # FR5
├── scripts/
│   └── validate-worker-output.py    # FR2 constant, FR3, FR4
└── skills/
    └── plan-writing/
        └── SKILL.md                 # FR1, FR2 rule text
tests/                               # FR9
```

## Resume Procedure: tcp-send-path-fr8-race-audit

This procedure belongs to this SPEC only (FR10). The actual state of
web-sip-phone is unconfirmed (A5), so the procedure starts from checking it.
The implementation of this feature does not write to web-sip-phone (NFR6); the
steps below run in web-sip-phone after this feature is available.

1. Check the actual state of tcp-send-path-fr8-race-audit:
   - implement's status and failed_kind
   - tasks' status
   - each task's final journal event
   - whether the task worktree and branch exist
   - that the integration tip does not contain
     `test-docs/tcp-send-path-fr8-race-audit/REPORT.md`
2. Restart Claude Code so that the em-workflow containing this feature takes
   effect.
3. If implement is failed, re-run `/em-workflow:develop` naming the feature.
   The FR6 entry judges the state at the start of the re-run, and enters the
   FR5 procedure when an FR3 violation remains in the files of a failed task,
   even when failed_kind is decision. A batch re-run uses the same entry.
4. In FR5, implementation-planner corrects the plan documents and proposes a
   new path that meets condition 4, and the orchestrator applies it to
   workflow.yaml. The FR6 write set then makes the target task startable.
5. The target task runs and its report is merged into the parent branch under
   the new name.

If the check shows anything other than failed: the FR6 entry does not apply, so
do not use it. Stop this procedure, leave workflow.yaml unchanged and report
the confirmed state.

If the FR5 conditions are not met, including when the integration tip already
contains `test-docs/tcp-send-path-fr8-race-audit/REPORT.md` (condition 3):
workflow.yaml is not changed and the run stops at stop condition 3 (FR6). No
correction is applied.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/subagent-report-write-block/**`
- `test-docs/subagent-report-write-block/**`

`feature-docs/subagent-report-write-block/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/subagent-report-write-block/**` covers
`test-docs/subagent-report-write-block/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/subagent-report-write-block/` directory at all; the declared
`test-docs/subagent-report-write-block/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: Validate a replace_planning patch whose files hold a new
      `test-docs/x/REPORT.md` - exit 1, a dedicated error code, the task id and
      the path are shown (FR2, FR3, FR9)
- [ ] TS-2: Validate a patch whose new files hold `report.md`,
      `Analysis-notes.md`, `SUMMARY_x.MD` and `findings.md` - all are rejected
      (FR2, FR3)
- [ ] TS-3: Validate a patch whose files hold `report.txt`, `reports/foo.md`,
      `audit-report.md` and `README.md` - all pass (FR2, FR3, NFR2)
- [ ] TS-4: Validate a patch whose files hold a matching name existing as a
      regular file at the base commit - passes (FR3, FR4)
- [ ] TS-5: Validate a patch whose files hold a matching name existing as a
      directory at the base commit - rejected as new (FR3)
- [ ] TS-6: Validate a patch with a matching name, once without the base input
      and once with an unresolvable base - both exit 2 and do not pass (FR4)
- [ ] TS-7: Validate a patch without a matching name and without the base
      input - passes as before (FR4, NFR2)
- [ ] TS-8: Validate an append_rework patch, and a plan with a new matching
      name in a TASK.md task - both are rejected (FR3)
- [ ] TS-9: Validate with `--dry-run-apply` a re-planning patch with matching
      names in the files of a carried non-merged task and of a merged task -
      only the non-merged task's violation is rejected (FR3, FR5)
- [ ] TS-10: Apply a correction meeting the FR5 conditions, and corrections
      that each break one condition - only the correction meeting them is
      applied (FR5)
- [ ] TS-11: Validate with a corrected task's Files section disagreeing with
      files - rejected with `task-plan-files-mismatch` (FR5)

### Document Contract Tests
- [ ] TS-12: Read the implementer.md and worktree-task-workflow rules - the
      immediate failure, the report of target path and rejection text, and the
      ban on workarounds are written (FR7, FR9, NFR1)
- [ ] TS-13: Read the implement-phase.md and batch-mode.md rules - retry
      suppression, recording in `tasks.{T}.notes`, and the resume condition are
      written (FR8, FR9)
- [ ] TS-14: Read the develop entry rule - the judgment at the start of a
      re-run, not entering inside the failed run, and stopping when the
      conditions are not met are written (FR6, FR9)
- [ ] TS-15: Compare the plan-writing regular expression with the validation
      script's constant - they match (FR2, NFR3)

### Manual Checks
- [ ] TS-16: Read the resume procedure in this SPEC - the check of the actual
      state, the entry from failed, the restart, and the handling when the
      conditions are not met are present (FR10)

### Integration Tests
None.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Performance Tests
None.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** files values are untrusted and reach git without a
  shell. The base commit accepts only a full hexadecimal commit ID (NFR5). A
  new path in an FR5 correction passes `is_safe_relative_path` (FR5).
- **Data Protection:** Deliverables contain no Notion URL and no absolute path
  under the home directory (NFR6).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

| Code | Description | Outcome |
|------|-------------|---------|
| Dedicated FR3 code | New matching name in files | Exit 1, showing the task id and the path |
| Missing or unresolvable base | Patch with a matching name lacks the two values or they cannot be resolved | Exit 2, does not pass |
| `task-plan-files-mismatch` | A corrected task's Files section disagrees with files | Rejected |

### Error Flow

```
Write rejected -> implementer status: failed -> parent stops without same-cause retry
  -> resume only after FR5 is complete
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

- **A1** (impact: medium): The FR6 entry is judged at the start of a develop
  re-run that names the feature. A batch re-run uses the same entry, and no new
  gate is added.
- **A2** (impact: medium): For FR5, implementation-planner corrects the plan
  documents and proposes files, and the orchestrator applies the change to
  workflow.yaml.
- **A3** (impact: medium): Edit is not subject to Claude Code's rejection, and a
  matching-name file existing at the base commit can be updated with Edit.
- **A4** (impact: low): The FR2 regular expression is the same as the rejection
  condition of Claude Code 2.1.318.
- **A5** (impact: medium): The actual state of web-sip-phone is unconfirmed, and
  the FR10 procedure is written on the premise of checking it.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/subagent-report-write-block/REQUIREMENTS.md`
- Workflow patch: `em-workflow/references/workflow-patch.md`
