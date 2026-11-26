# Feature: dbracket-paren-group-spec-align

## Overview

For `[[ ( a == b ) && true ]]` followed by a canonical notion call with
`--session "$SID"`, the SPEC, the tests and the implementation of
dbracket-opener-arith-scan state the same judgment: the form is uncertain and
the following call is KIND_INSPECTED. The command-level reading in
`em-workflow/hooks/destructive-guard.py` is not changed; the prior feature's
SPEC, VERIFICATION note and test descriptions are aligned to it, and a test
and a case-table row pin the judgment.

## Objectives

- For `[[ ( a == b ) && true ]]` followed by a canonical notion call with
  `--session "$SID"`, the SPEC, the tests and the implementation of
  dbracket-opener-arith-scan state the same judgment: the form is uncertain
  and the following call is KIND_INSPECTED.
- A test and a case-table row detect any recurrence of the disagreement.

## Acceptance Criteria

- [ ] AC-1 (FR1, NFR2): `em-workflow/hooks/destructive-guard.py` has no diff
  between the implement base commit and the integration HEAD.
- [ ] AC-2 (FR2, FR3): `feature-docs/dbracket-opener-arith-scan/SPEC.md` no
  longer states that `[[ ( a == b ) && true ]]` is certain or that the
  following call stays KIND_NOTHING. FR3, AC-5 and TS-3 each state that the
  form is uncertain and that the following notion call with
  `--session "$SID"` is KIND_INSPECTED. AC-5 also states deny with
  git-branch-force-delete.
- [ ] AC-3 (FR4, FR7): The PAREN_FORM comment, the docstring of its test and
  the TS-3 note in VERIFICATION.md state the same judgment as the amended
  SPEC. None of them cites the task plan's 'SPEC discrepancy' as the basis.
- [ ] AC-4 (FR5): For ARRAY + `[[ ( a == b ) && true ]]; ` + the notion call
  with `--session "$SID"` (command `git branch -D example`),
  `Spy(...).kinds()` is `[KIND_INSPECTED]` and the hook judgment is deny with
  reason ID git-branch-force-delete.
- [ ] AC-5 (FR6, NFR4): `destructive-guard-cases.json` holds that command as
  a deny row whose label starts with `dbracket-paren-group-spec-align` and
  whose fourth element is `{"rule": "git-branch-force-delete"}`.
  `run-destructive-guard.py` matches both the decision and the reason ID.
- [ ] AC-6 (NFR1, NFR3):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
  exits 0. No existing case or test is removed. Neither
  `em-workflow/.claude-plugin/plugin.json` nor
  `.claude-plugin/marketplace.json` is changed.

## Technical Requirements

### Functional Requirements

- **FR1:** Command-level reading is unchanged.
  `em-workflow/hooks/destructive-guard.py` is not changed.
  `[[ ( a == b ) && true ]]` stays uncertain because the `(` boundary makes
  `a == b` a simple command whose name `a` is not an allow-list name. As a
  result, the following canonical notion call with `--session "$SID"` is
  KIND_INSPECTED.
- **FR2:** Amend FR3 of the dbracket-opener-arith-scan SPEC. In
  `feature-docs/dbracket-opener-arith-scan/SPEC.md`, FR3 no longer names
  `[[ ( a == b ) && true ]]` among the forms read as certain. FR3 states that
  this form stays uncertain: the `(` boundary makes `a == b` a simple command
  whose name `a` is not an allow-list name, and the command-level reading
  reads that command as uncertain, as before that feature. The following
  notion call with `--session "$SID"` is KIND_INSPECTED.
  `[[ ( true == x ) && true ]]` stays as a certain / KIND_NOTHING example.
- **FR3:** Amend AC-5 and TS-3 of the dbracket-opener-arith-scan SPEC. In the
  same SPEC, AC-5 no longer lists `[[ ( a == b ) && true ]]` among the forms
  that stay KIND_NOTHING. AC-5 states that, with the array assignment, the
  notion call after this form is KIND_INSPECTED and the hook decision is deny
  with reason ID git-branch-force-delete. TS-3 states the same expectation
  for this form (`[KIND_INSPECTED]`), separately from the forms that stay
  `[KIND_NOTHING]`.
- **FR4:** Align the test descriptions. In
  `tests/test_destructive_guard_args_json.py`, the comment on `PAREN_FORM`
  (lines 4271-4272) and the docstring of
  `test_a_parenthesised_comparison_without_an_operator_word_reports_no_uncertain_statement`
  (lines 4381-4384) state the amended SPEC judgment: the form is uncertain
  from the command-level reading and the following notion call is
  KIND_INSPECTED. They no longer cite the task plan's 'SPEC discrepancy'. The
  test's assertions are unchanged.
- **FR5:** Regression test for the judgment. A test in
  `tests/test_destructive_guard_args_json.py` pins two results for the
  command ARRAY (`A=(json --mcp desktop-commander --tool start_process); `) +
  `[[ ( a == b ) && true ]]` + `; ` + the canonical notion call with
  `--session "$SID"` whose `--args-json` command is `git branch -D example`.
  First, `Spy(...).kinds()` is `[KIND_INSPECTED]`. Second, the hook judgment
  is `("deny", "git-branch-force-delete")`.
- **FR6:** Case-table deny row.
  `em-workflow/hooks/tests/destructive-guard-cases.json` gains one deny row
  for the FR5 command. Its label starts with
  `dbracket-paren-group-spec-align`, and its fourth element is
  `{"rule": "git-branch-force-delete"}`. A test checks that this row is in
  the table with that decision, label prefix and rule.
- **FR7:** Align the VERIFICATION note of the prior feature. In
  `feature-docs/dbracket-opener-arith-scan/VERIFICATION.md`, the TS-3 note
  (lines 29-35) no longer says that SPEC FR3 / AC-5 call
  `[[ ( a == b ) && true ]]` certain. It states the amended SPEC judgment
  (uncertain, following call KIND_INSPECTED).

### Non-Functional Requirements

- **NFR1 - Existing cases and tests:** No existing case-table row or test is
  removed. `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` both pass.
- **NFR2 - Static analysis only:** The judgment is made only by static
  analysis of the command string, and nothing is executed.
  `destructive-guard.py` is not changed.
- **NFR3 - Version:** The plugin version is not changed. This is a bug fix,
  and GitHub Actions bumps the patch version.
- **NFR4 - Case label prefix:** The new case label does not start with
  `args-json-deferred-eval-bypass TS-16:` / `TS-17:`, because
  `test_every_case_of_this_task_is_in_the_table_with_its_decision` requires
  exactly 30 such labels. It also does not start with
  `dbracket-opener-arith-scan`.

## Implementation Approach

### Files

| Path | Change | Requirements |
|------|--------|--------------|
| `feature-docs/dbracket-opener-arith-scan/SPEC.md` | Amend FR3, AC-5 and TS-3 | FR2, FR3 |
| `feature-docs/dbracket-opener-arith-scan/VERIFICATION.md` | Amend the TS-3 note (lines 29-35) | FR7 |
| `tests/test_destructive_guard_args_json.py` | Align the `PAREN_FORM` comment and the docstring of its test; add the FR5 test and the FR6 table-membership test | FR4, FR5, FR6 |
| `em-workflow/hooks/tests/destructive-guard-cases.json` | Add one deny row | FR6, NFR4 |
| `em-workflow/hooks/destructive-guard.py` | No change | FR1, NFR2 |
| `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | No change | NFR3 |

### Command Shape

The FR5 test and the FR6 row use one command:

```
ARRAY + [[ ( a == b ) && true ]] + "; " + canonical notion call
```

- ARRAY is `A=(json --mcp desktop-commander --tool start_process); `.
- The canonical notion call carries `--session "$SID"`, and its
  `--args-json` command is `git branch -D example`.
- Expected results: `Spy(...).kinds()` is `[KIND_INSPECTED]`; the hook
  judgment is `("deny", "git-branch-force-delete")`.

## Assumptions

- **A0:** Direction (answer `create-spec.paren-group-direction` =
  `keep_reading_state_uncertain`, source batch-codex-consultation): the
  command-level reading is not changed. The prior feature's SPEC FR3 / AC-5 /
  TS-3 are amended to say that the form stays uncertain and that the
  following notion call is KIND_INSPECTED. The test descriptions are aligned.
  A test that pins KIND_INSPECTED and deny(git-branch-force-delete), and a
  deny case-table row, are added.
- **A1:** The new test and case row use the same shape as the existing
  dbracket-opener-arith-scan deny rows: ARRAY + form + `; ` + the notion call
  with `--session "$SID"` and `--args-json` command `git branch -D example`.
  Based on the code reading and the task's reproduction, the expected result
  is `[KIND_INSPECTED]` and deny / git-branch-force-delete.
- **A2:** No existing test or case row is removed. The `PAREN_FORM` test
  keeps its name and its assertions, and only its comment and docstring
  change.
- **A3:** Among the prior feature's documents, SPEC.md (FR3, AC-5, TS-3) and
  the TS-3 note in VERIFICATION.md are amended.
  `tasks/task0001.md` is left unchanged as the historical plan record.
- **A4:** New case labels start with `dbracket-paren-group-spec-align`. The
  plugin version is not changed.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/dbracket-paren-group-spec-align/**`
- `test-docs/dbracket-paren-group-spec-align/**`

`feature-docs/dbracket-paren-group-spec-align/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/dbracket-paren-group-spec-align/**` covers
`test-docs/dbracket-paren-group-spec-align/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/dbracket-paren-group-spec-align/` directory at all; the declared
`test-docs/dbracket-paren-group-spec-align/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Integration Tests
- [ ] TS-1: Run ARRAY + `[[ ( a == b ) && true ]]` + `; ` + the notion call
  with `--session "$SID"` through `Spy(...).kinds()`. The result is
  `[KIND_INSPECTED]`. Run `judge()` on the same command. The result is
  `("deny", "git-branch-force-delete")`. (AC-4)

### Regression Tests
- [ ] TS-2: Case table: the new deny row stands in
  `destructive-guard-cases.json` with the `dbracket-paren-group-spec-align`
  label prefix and `{"rule": "git-branch-force-delete"}`, and
  `run-destructive-guard.py` passes it. (AC-5)

### Edge Cases
- [ ] TS-3: The existing `PAREN_FORM` test still passes unchanged:
  `_args_json_conditional_step()` reports no uncertain statement and the scan
  returns true. The `[[ ( true == x ) && true ]]` allow test and its allow row
  still give KIND_NOTHING / allow. (AC-3, AC-4)

### Regression Tests (Suite)
- [ ] TS-4: All of `run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` pass. The diff shows no change to
  `destructive-guard.py` or to the version fields. (AC-1, AC-6)

### Review
- [ ] TS-5: Read the amended FR3 / AC-5 / TS-3 of the prior SPEC, the
  VERIFICATION TS-3 note and the two test descriptions. All of them state
  that the form is uncertain and that the following call is KIND_INSPECTED.
  (AC-2, AC-3)

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC-1 through AC-6 are satisfied
- [ ] TS-1 through TS-5 pass

## Open Questions

None. Every requirement is resolved.

## References

- dbracket-opener-arith-scan SPEC: `feature-docs/dbracket-opener-arith-scan/SPEC.md`
- dbracket-opener-arith-scan VERIFICATION: `feature-docs/dbracket-opener-arith-scan/VERIFICATION.md`
- Hook test rules: `.claude/rules/hook-tests.md`
- Plugin version rules: `.claude/rules/core-plugin-version-bump.md`
