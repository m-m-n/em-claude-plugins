# Feature: final-path-correction-medium-fixes

## Overview

This feature fixes the seven medium findings that round 1 of the `subagent-report-write-block` review left on the final-path correction of em-workflow. Three findings let a correction patch pass changes other than paths, and four keep the correction procedure from completing or let a reference slip through. Requirements are in `feature-docs/final-path-correction-medium-fixes/REQUIREMENTS.md`.

## Objectives

- A final-path correction changes nothing but paths: its validation passes no other change.
- The correction of a plan holding report-artifact names completes across several tasks and on re-planning.

## User Stories

None defined. Acceptance criteria are listed under Success Criteria.

## Technical Requirements

### Functional Requirements

- **FR1:** Limit entries and requirements_patch on the correction entry. Under --dry-run-apply, on a patch with non-empty tasks_patch.path_corrections while create-plan is completed and implement is failed:
    - (a) requirements_patch is rejected with `path-correction-requirements` unless it is null or has no entries, or every item names a requirement already in workflow.yaml and its `set` holds only `tasks_append` whose values are all ids under tasks_patch.entries.
    - (b) An item of tasks_patch.entries is rejected with `path-correction-entries` unless its `files` is non-empty and every file is a regular file at the base commit whose text holds an old path or a bare old file name of the patch's corrections (occurrence as defined in FR7). A file that cannot be read as text within the existing read limit is rejected.
    - (c) Each file of an entry and each old_path and new_path rendered into its plan must pass the FR2 form check, else `path-correction-entries`.
    - (d) The plan of an entry must be byte-equal to the canonical text the validator renders from that task's id and files and the corrections whose old path or bare old file name occurs in those files at the base commit: a title, the Files section, and one acceptance criterion per such correction stating that the old reference is replaced by the new one, nothing else. This holds for a TASK.md plan too, else `path-correction-entries`. The canonical form is one function in the validator.
    - The Re-planning path is not limited. Finding 73c084892e91326c.
- **FR2:** Restrict the form of new_path. Condition 4 also rejects with `path-correction-new-path` a new_path that fails any of: full match of `[\w./-]+` (Unicode word characters, `.`, `/`, `-`); equal to its normalized form (`/`.join(path_segments(new_path))), so `.`, `./`, `a//b.md`, `a/./b.md` and a trailing `/` are rejected; first segment does not start with `-`. The handling of `files` under tasks_patch.entries does not change. Finding 7dad93fa93454f47.
- **FR3:** Compare the plans of non-target tasks on the correction entry. On the correction entry, condition 5 also covers the plan of every task in workflow.yaml that is not a target of the patch, whatever its status. The plan of a task whose status or last journal event is `merged` must be byte-equal to the base commit, else `path-correction-content` naming the document; this holds for a shared plan as well and takes precedence over any replacement a target task would need. The plan of any other non-target task is compared positionally (FR6): each occurrence holds the old text or a permitted replacement, so an old reference may remain and nothing else may change. A plan shared with a target task is compared as a target plan, and an old reference may not remain there. A plan that cannot be compared is rejected. Finding 041b04abfc9d5b87.
- **FR4:** Align the entry's targets with the validator. scripts/report-name-entry.py keeps deciding `none` from the failed tasks: no violation in a failed task's files is `none`, whatever other tasks hold. When a failed task has a violation, `violations` lists the violations of every task whose status is not `merged`, in task then file order, and conditions 1 to 3 are judged on that whole list. The output keys do not change; an element for a task with no failed journal event carries `failed_journal_line: null`. Finding 4409a460572aac40.
- **FR5:** Limit condition 5's comparison to outside the Re-planning path. On the Re-planning path (create-plan needs_update, or pending on a SPEC-change re-entry) the base-versus-current comparison of condition 5 does not run. Condition 5 there requires only that the current IMPLEMENTATION.md, VERIFICATION.md and target task plans hold no old path and no bare old file name, else `path-correction-content`; a document that does not exist now is not an error. Conditions 1 to 4 and the plan Files-section agreement stay. The VERIFICATION.md skip of the scenario-ID scan applies only on the correction entry: a correction patch on the Re-planning path, or one validated without workflow.yaml, scans VERIFICATION.md. Finding dc9fcac543811a2d.
- **FR6:** Compare positionally, so one old file name may map to different new names. Condition 5 no longer normalizes both sides to one text. It fixes non-overlapping occurrences of old paths and bare old file names in the base version, longer match first, and only at an occurrence may the current version differ. All other text must be identical, and replacement values are literal and never rescanned, so candidate names are never equal to each other outside an occurrence: with a/REPORT.md to a/enabled and b/REPORT.md to b/disabled, changing `Authentication is enabled` to `Authentication is disabled` is rejected. An old path occurrence permits only its own new path. A bare old file name permits: in the plan of a target task, the new file names of the corrections of the tasks using that plan when they hold that old file name, otherwise those of all corrections of the patch. For a plan used by several target tasks, the candidates are the union of those tasks' corrections, and the plan's Files sections are checked against the union of those tasks' files. Example: base `Write a/REPORT.md. REPORT.md must exist.` and current `Write a/one.md. one.md must exist.` pass with a/REPORT.md to a/one.md and b/REPORT.md to b/two.md together. In the plan of the task corrected to a/one.md, `two.md` in place of that bare name is rejected. Finding a848a53b57fb0188.
- **FR7:** Reject a bare old file name left behind. Condition 5 rejects a current IMPLEMENTATION.md, VERIFICATION.md or target task plan holding a bare occurrence of an old file name, ambiguous names included, with `path-correction-content`. A bare occurrence is the literal, case-sensitive old file name not preceded by an ASCII letter, digit, `_`, `-`, `.`, `/` or `\`, and not followed by an ASCII letter, digit, `_`, `-`, `/` or `\`, or by `.` plus one of letter, digit, `_`, `-`. The comparison treats a bare old file name as an occurrence only at a bare occurrence, so `existing/REPORT.md`, `PREREPORT.md` and `REPORT.md.bak` are neither replaced nor flagged, and rewriting them fails the comparison. A one-segment old path is matched as a bare name. An old path of several segments is an occurrence under the same boundary rule, except that a preceding `./` still counts, so `existing/a/REPORT.md` and `a/release-REPORT.md` are not occurrences and may not change. The left-behind check uses these occurrences, not a substring search. Finding 25461d162dc42425.
- **FR8:** State the rules in the owning documents. references/workflow-patch.md `## Final-path correction` states FR1 to FR3, FR5 to FR7 and FR9, with the FR1 limits and their two error codes outside the five numbered conditions. agents/implementation-planner.md `## Final-path correction` states: the new_path form; in a non-target unmerged plan only references may be replaced, and a merged task's plan is not edited; the canonical plan of a new task; which new name replaces a shared bare name; what `entries` and `requirements_patch` may hold on the correction dispatch; on a re-planning pass the body may change and no old path or bare old file name may remain. references/phases/create-plan-phase.md lists the two new codes where it lists the correction codes. The docstrings of scripts/report-name-entry.py and the affected validator functions follow FR4 to FR7.
- **FR9:** Reject plan documents created on the correction entry. On the correction entry, IMPLEMENTATION.md, VERIFICATION.md or a plan of a task in workflow.yaml with no entry at the base commit and present now is rejected with `path-correction-content`. The one exception is the plan of a new task under entries, when that path is none of those documents and collides with none of them after path normalization (`./` and repeated separators removed). Where a path is both, the constraint on the existing document wins.

### Non-Functional Requirements

- **NFR1 - Unchanged behavior outside corrections:** A patch without tasks_patch.path_corrections validates as before in every state, including entries and requirements_patch on plain re-planning.
- **NFR2 - Fail closed:** A document or file that cannot be read or compared is a rejection, never a pass. Missing inputs stay an execution error (exit 2). The entry script's exit codes do not change.
- **NFR3 - Literal paths:** Paths stay literal text. Base-commit reads use base_tree_entry and _read_base_document; no shell and no git pathspec.
- **NFR4 - No new gate:** No new gate_id, user question, or workflow.yaml field is added. The output keys of report-name-entry.py do not change.

## Implementation Approach

### Architecture

The change stays inside the existing validator and entry script. How the rules apply depends on the path the patch takes.

| Rule | Correction entry | Re-planning path |
|---|---|---|
| Definition | Non-empty tasks_patch.path_corrections while create-plan is completed and implement is failed | create-plan needs_update, or pending on a SPEC-change re-entry |
| entries and requirements_patch | Limited (FR1) | Not limited (FR1) |
| Condition 5 base-versus-current comparison | Runs positionally (FR6) and covers non-target plans (FR3) | Does not run (FR5) |
| Condition 5 left-behind check | Rejects a bare occurrence in the current documents and target plans (FR7) | The only part of condition 5 that remains (FR5) |
| VERIFICATION.md scenario-ID scan | Skipped (FR5) | Runs (FR5) |
| Conditions 1 to 4 and the plan Files-section agreement | Apply | Apply (FR5) |

### Data Flow

Not applicable.

### API Design

Not applicable. The output keys of `report-name-entry.py` do not change (NFR4); an element for a task with no failed journal event carries `failed_journal_line: null` (FR4).

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `base_tree_entry` and `_read_base_document`: base-commit reads (NFR3)
- `path_segments`: normalized form of new_path (FR2)

**External Dependencies:**
- None.

### File Structure

```
em-workflow/
├── agents/implementation-planner.md          # FR8
├── references/
│   ├── phases/create-plan-phase.md           # FR8
│   └── workflow-patch.md                     # FR8
└── scripts/
    ├── report-name-entry.py                  # FR4, FR8
    └── validate-worker-output.py             # FR1 to FR3, FR5 to FR9
tests/
└── test_final_path_correction.py             # AC-11
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/final-path-correction-medium-fixes/**`
- `test-docs/final-path-correction-medium-fixes/**`

`feature-docs/final-path-correction-medium-fixes/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/final-path-correction-medium-fixes/**` covers `test-docs/final-path-correction-medium-fixes/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/final-path-correction-medium-fixes/` directory at all; the declared
`test-docs/final-path-correction-medium-fixes/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

**Run command**: `python3 -m unittest discover -s tests`

### Unit Tests
- [ ] TS-1: Correction entry, entries with an unrelated file and requirements_patch set.status: excluded, through validate_worker_result dry_run - Rejected with both new codes (FR1)
- [ ] TS-2: requirements_patch variants: tests_append, status, tests_replace, an unregistered requirement id, tasks_append of a carried id - Each rejected with path-correction-requirements (FR1)
- [ ] TS-3: Entry files: new file, directory, regular file without a reference, non-UTF-8 file, empty list, regular file referencing the old path, regular file referencing the bare name; plan differing from the canonical text; a file with a newline or backtick in its name - Only the two reference cases with the canonical plan pass (FR1)
- [ ] TS-4: The same entries and requirements_patch on the Re-planning path - Not rejected by the new codes (FR1, FR5)
- [ ] TS-5: new_path with spaces, a newline, a backtick, `:(top)README.md`, `-x.md`, `.`, `./`, `a//b.md`, `a/`, and a non-ASCII directory - All rejected except the non-ASCII directory (FR2)
- [ ] TS-6: Non-target plan edited and reference-replaced, for pending, failed, merged by status and merged by journal; shared TASK.md plan with path replacement only; shared plan including a merged task - Edits rejected; replacement passes only unmerged; shared plan passes unless a merged task shares it (FR3)
- [ ] TS-7: Entry with failed and unstarted tasks holding violations; merged task holding a name; unstarted task whose last journal event is merged; unstarted task whose name is a directory at the base - Both listed with a null line for the unstarted task; merged task not listed; the last two blocked (FR4)
- [ ] TS-8: Entry output of two targets fed through a corrected patch and validated - No report-name-new-file error (FR4)
- [ ] TS-9: Re-planning with path_corrections, body updates, needs_update and route-back states - Pass with the residual check only; old path or bare name left is rejected (FR5, FR7)
- [ ] TS-10: Scenario-ID scan on a correction patch: correction entry, Re-planning path, workflow absent - Skipped on the correction entry only (FR5)
- [ ] TS-11: Two corrections sharing an old file name: shared documents, each target plan, a plan of a task with neither; candidate names swapped outside an occurrence; old file name inside `a/release-REPORT.md`; plan shared by two targets - Per FR6 (FR6)
- [ ] TS-12: Boundary cases of the bare name: backtick, parenthesis, sentence-final period, Japanese text directly adjacent, `#anchor`, directory prefix, name prefix, `.bak` suffix, different case, one-segment old path; multi-segment old path under a longer path and after `./` - Per FR7 (FR7)
- [ ] TS-13: Document tests read workflow-patch.md, implementation-planner.md and create-plan-phase.md - The rules and the two new codes are stated (FR8)
- [ ] TS-14: Correction entry with a plan document absent at the base: VERIFICATION.md, IMPLEMENTATION.md, an existing task's plan, an entry plan naming VERIFICATION.md or `./VERIFICATION.md`, a new task's own plan - Only the last passes (FR9)

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Input Validation:** tasks_patch.entries and requirements_patch are limited on the correction entry (FR1), new_path form is restricted (FR2), condition 5 covers non-target plans (FR3), plan documents created on the correction entry are rejected (FR9). A document or file that cannot be read or compared is a rejection (NFR2). Paths stay literal text (NFR3).

Authentication, authorization, data protection, XSS, SQL injection and CSRF do not apply.

## Error Handling

### Error Codes

| Code | Description |
|---|---|
| `path-correction-requirements` | New. requirements_patch outside the FR1 limit |
| `path-correction-entries` | New. tasks_patch.entries item outside the FR1 limit |
| `path-correction-new-path` | new_path failing the FR2 form check |
| `path-correction-content` | Condition 5 rejection stated in FR3, FR5, FR7 and FR9 |

### Error Flow

A document or file that cannot be read or compared is a rejection, never a pass. Missing inputs stay an execution error (exit 2). The entry script's exit codes do not change (NFR2).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC-1: The round1 reproduction of 73c084892e91326c (a task0003 entry on .github/workflows/deploy.yml plus FR1 set.status: excluded) is rejected with path-correction-entries and path-correction-requirements (FR1).
- [ ] AC-2: A new entry whose files are regular at the base and hold the old path or bare old name, with its canonical plan and a requirements_patch of tasks_append for that id, passes on the correction entry; the same entry with any added line in the plan, TASK.md included, is rejected (FR1).
- [ ] AC-3: The round1 new_path sentence and the newline form on a TASK.md plan are rejected with path-correction-new-path (FR2).
- [ ] AC-4: Editing an acceptance criterion in a non-target plan on the correction entry is rejected with path-correction-content for pending, failed and merged tasks; replacing an old reference passes in an unmerged plan and is rejected in the plan of a task whose status or last journal event is merged; a plan left unchanged passes (FR3).
- [ ] AC-5: With a failed task and an unstarted task each holding a new report-artifact name, the entry returns dispatch listing both, and correcting both passes the validator (FR4).
- [ ] AC-6: A failed task with no violation beside a pending task with one still returns none (FR4).
- [ ] AC-7: A re-planning patch with path_corrections and body updates to the three documents passes; the same patch leaving an old path or bare old file name is rejected; a hyphen-less ID in VERIFICATION.md is reported as scenario-id-form (FR5, FR7).
- [ ] AC-8: On the correction entry the comparison still rejects a body change, and VERIFICATION.md is still not scanned (FR5).
- [ ] AC-9: The a/REPORT.md and b/REPORT.md example of a848a53b57fb0188 passes on documents and plans, the wrong new name in a task's own plan is rejected, and changing `enabled` to `disabled` outside an occurrence is rejected when both are candidate names (FR6).
- [ ] AC-10: A bare old file name left in a document is rejected; existing/REPORT.md, PREREPORT.md and REPORT.md.bak left unchanged pass (FR7).
- [ ] AC-12: On the correction entry a newly created VERIFICATION.md is rejected, also when an entry names it as its plan; a new task's own plan at a free path passes (FR9).
- [ ] AC-13: A plan shared by two target tasks passes with both tasks' replacements and its Files sections checked against the union of their files (FR6).
- [ ] AC-11: `python3 -m unittest discover -s tests` passes, with a recurrence test for each of the seven findings and the pinning tests in reference_impact updated (FR1 to FR8).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. No requirement has `status: tbd`.

## Assumptions

- A1: Re-planning: condition 5 keeps only the residual check. Splitting correction and body update into two passes is not adopted.
- A2: An unmerged non-target plan may keep an old reference; replacement there is allowed, not required.
- A3: new_path keeps non-ASCII word characters allowed; a sentence without spaces or punctuation in that form still passes.
- A4: An entry's file is not required to be a test file by name or to belong to a merged task; holding a reference at the base is the check.
- A5: The body of a new task plan under entries is a canonical generated text on the correction entry; on the Re-planning path it stays free.
- A6: An unstarted task added to violations is already `pending`, so the Step A.6 restoration needs no text change; a null failed_journal_line leaves its routeback record as it is.
- A7: `./REPORT.md` counts as path-qualified, not as a bare occurrence, for a one-segment old path; a preceding `./` still counts for an old path of several segments.

## References

- Requirements: `feature-docs/final-path-correction-medium-fixes/REQUIREMENTS.md`
- Round 1 review: `feature-docs/subagent-report-write-block/reviews/round1.yaml` on `em-workflow/subagent-report-write-block/integration`
- `em-workflow/references/workflow-patch.md`

## Reference Impact

- `test_only_the_target_tasks_plan_is_compared`: Pinned behavior reverses (FR3); rename and invert (`tests/test_final_path_correction.py`)
- `test_new_task_plans_under_entries_are_outside_the_set`: Its src/d.py entry is now rejected on the correction entry (FR1); rewrite with a referencing file (`tests/test_final_path_correction.py`)
- `test_a_bare_old_file_name_left_in_place_is_equal_after_normalization`: Pinned behavior reverses (FR7); rename and invert (`tests/test_final_path_correction.py`)
- `test_the_normalization_is_deterministic_on_a_shared_bare_name`: Pinned left-alone result and left_behind list change (FR6, FR7); rewrite (`tests/test_final_path_correction.py`)
- `test_paths_are_literal_text (new_path `:(top)README.md`)`: That new_path is now rejected by FR2; the base_tree_entry assertions stay, the validate assertion inverts (`tests/test_final_path_correction.py`)
- `test_a_correction_patch_skips_the_verification_target_only and _validate_scenario_id_form(workflow_patch, feature_dir)`: The function needs the workflow to decide the skip (FR5); the test passes a correction-entry workflow; call site in validate_worker_result changes (`em-workflow/scripts/validate-worker-output.py`, `tests/test_final_path_correction.py`)
- `_correction_normalizer / _normalize_path_strings`: Normalization becomes per-document and reports bare names (FR6, FR7); signatures may change; tests call both directly (`em-workflow/scripts/validate-worker-output.py`, `tests/test_final_path_correction.py`)
- `_path_correction_content_errors`: Takes the patch state (FR3, FR5). `correction_entry` is computed inside the replace_all branch, so the state must be available to the `if corrections:` block (`em-workflow/scripts/validate-worker-output.py`)
- `Comparison and condition wording in workflow-patch.md and implementation-planner.md`: Text is extended, not removed. Pinned phrases stay, as do the `**Comparison` and `**Conditions.**` to `**Ownership.**` section markers; new pins are added (`em-workflow/references/workflow-patch.md`, `em-workflow/agents/implementation-planner.md`, `em-workflow/references/phases/create-plan-phase.md`, `tests/test_final_path_correction_docs.py`, `tests/test_report_name_planner_docs.py`)
- `judge() in report-name-entry.py`: Violations widen when a failed task has one (FR4); existing tests keep passing, new tests added (`em-workflow/scripts/report-name-entry.py`, `tests/test_report_name_entry.py`)
- `_validate_corrected_task_plans`: Files check of a shared plan uses the union of the sharing tasks' files (FR6) (`em-workflow/scripts/validate-worker-output.py`, `tests/test_final_path_correction.py`)
- `tests pinning `A document absent at the base commit is outside the set``: Reverses on the correction entry (FR9); text in workflow-patch.md changes (`em-workflow/references/workflow-patch.md`, `tests/test_final_path_correction.py`, `tests/test_final_path_correction_docs.py`)
