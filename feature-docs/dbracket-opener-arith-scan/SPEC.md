# Feature: dbracket-opener-arith-scan

## Overview

`destructive-guard` counts the arithmetic comparison operators (`-eq` / `-ne` /
`-lt` / `-le` / `-gt` / `-ge`) and `-v` inside a `[[ ]]` conditional even in
the statement that opens the conditional. When it counts one, it drops the
exclusion of the following notion call and inspects its `--args-json`.

## Objectives

- `destructive-guard` counts the arithmetic comparison operators (`-eq` / `-ne`
  / `-lt` / `-le` / `-gt` / `-ge`) and `-v` inside `[[ ]]`, including in the
  statement that opens the conditional. When it counts one, it drops the
  exclusion of the following notion call and inspects `--args-json`.

## Technical Requirements

### Functional Requirements

- **FR1: Scan the operator words inside the conditional in the statement that contains the opener.**
  `_args_json_conditional_step()` also scans the statement that opens `[[`
  (the statement where `was_open` is false and an opener is found). It scans
  the words from immediately after the opener up to immediately before the
  closer in the same statement (a word written literally as `]]`). When the
  statement has no closer, it scans to the end of the statement. If any word,
  as a restored string, is in `_ARGS_JSON_DOUBLE_BRACKET_WORDS` (`-eq`, `-ne`,
  `-lt`, `-le`, `-gt`, `-ge`, `-v`), the statement is uncertain. The word's
  position in the statement does not matter: the statement is uncertain even
  when the word is in a simple command delimited by `(`, `)`, `{`, `}`, and
  even when that command's name is an allow-list name (`true`, `false`,
  `echo`, `:`, `mcp-bridge`, `fi`, `done`).
- **FR2: Inspect the notion call that follows an uncertain chunk.**
  A canonical notion call with `--session "$SID"`
  (`mcp-bridge run --mcp notion ... --args-json`) that follows a chunk read as
  uncertain by FR1 does not receive the notion-pair exclusion and becomes
  `KIND_INSPECTED`. The `command` in `--args-json` is decoded and judged (for
  example, `git branch -D` is `deny` with the reason ID
  `git-branch-force-delete`).
- **FR3: Leave conditionals without operator words unchanged.**
  The FR1 scan adds nothing for a conditional in an opening statement that
  contains no word in `_ARGS_JSON_DOUBLE_BRACKET_WORDS`, and such a statement
  is read as before. `[[ ( true == x ) && true ]]` is read as certain, as
  before, and the following notion call with `--session "$SID"` stays
  `KIND_NOTHING`. `[[ ( a == b ) && true ]]` stays uncertain: the `(` boundary
  makes `a == b` a simple command whose name `a` is not an allow-list name,
  and the command-level reading reads that command as uncertain, as before
  this feature. The following notion call with `--session "$SID"` is
  `KIND_INSPECTED`. Words after the closer and words before the opener are
  not part of the FR1 scan.

### Non-Functional Requirements

- **NFR1 - Existing cases:** The existing allow / deny cases
  (`destructive-guard-cases.json`, `tests/test_destructive_guard_args_json.py`)
  are not removed, and all of them pass.
- **NFR2 - Call site and responsibility:** `_args_json_conditional_step()` is
  called only from `_args_json_nameref_scan()`, as before. It holds no decision
  (`permissionDecision`) and no reason ID (`destructive-guard/...`).
- **NFR3 - Docstring:** The docstring of `_args_json_nameref_scan()` contains
  none of the command names `declare`, `local`, `typeset`, `eval`, `source`,
  `trap`, `alias`, `mapfile`, `readarray`, `echo`, `mcp-bridge`, `printf`, as
  before.
- **NFR4 - Static analysis only:** The judgment is made only by static analysis
  of the command string, as before, and executes nothing.
- **NFR5 - Version:** The plugin version is not changed (this is a bug fix; the
  patch bump is done by GitHub Actions).

## Acceptance Criteria

- [ ] AC-1 (FR1): `_args_json_nameref_scan()` returns true for the chunk
  `[[ ( true -eq 0 ) && true ]]`. It also returns true with `-ne` / `-lt` /
  `-le` / `-gt` / `-ge`, with `||` instead of `&&`, and with the name inside
  the parentheses being `false` / `echo` / `:` / `mcp-bridge`.
- [ ] AC-2 (FR1, FR2): A command made of
  `A=(json --mcp desktop-commander --tool start_process); [[ ( true -eq 0 ) && true ]]; `
  followed by a canonical notion call with `--session "$SID"` (whose
  `--args-json` `command` is `git branch -D example`) becomes `KIND_INSPECTED`.
  The hook's overall decision is `deny` with the reason ID
  `git-branch-force-delete`.
- [ ] AC-3 (FR1, FR2): An opener after a leading word (such as `if`), as in
  `if [[ ( true -eq 0 ) && true ]]; then :; fi`, gives the same results as
  AC-1 / AC-2.
- [ ] AC-4 (FR1, FR2): A form containing `-v` (for example
  `[[ ( -v x ) && true ]]`) is also read as uncertain, and the following notion
  call becomes `KIND_INSPECTED`.
- [ ] AC-5 (FR3): `[[ ( true == x ) && true ]]` and each existing
  `CONDITIONAL_ALLOW` / `certain_forms` form are read as certain, as before,
  and the following call with `--session "$SID"` stays `KIND_NOTHING`.
  `[[ ( a == b ) && true ]]` stays uncertain from the command-level reading,
  as before: with the array assignment
  `A=(json --mcp desktop-commander --tool start_process); `, the following
  canonical notion call with `--session "$SID"` (whose `--args-json`
  `command` is `git branch -D example`) is `KIND_INSPECTED`, and the hook's
  overall decision is `deny` with the reason ID `git-branch-force-delete`.
- [ ] AC-6 (FR1, FR2, FR3, NFR1): The forms of AC-2 to AC-5 are added to
  `destructive-guard-cases.json` as deny / allow cases. Each deny case carries
  `{"rule": "git-branch-force-delete"}`. Both
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest tests.test_destructive_guard_args_json` pass.

## Implementation Approach

- Cause: in a statement that contains the opener, the operator words are seen
  by `_args_json_declares_nameref()` only per simple command. When the command
  after a `(` or `)` delimiter has an allow-list name, `-eq` is not counted. The
  minimal reproduction is `[[ ( true -eq 0 ) && true ]]`.
- Whether a word is an operator word is judged on the string restored by
  `_args_json_declaration_word()`, in the same way as the `was_open` branch and
  the `[[` branch of `_args_json_name_uncertain()`.
- The scan range is from the opener to the closer (to the end of the statement
  when there is no closer). The existing behavior of the `was_open` branch,
  which scans the whole statement, is unchanged.
- New case labels start with `dbracket-opener-arith-scan` and do not start with
  `args-json-deferred-eval-bypass TS-16:` / `TS-17:`.
  `test_every_case_of_this_task_is_in_the_table_with_its_decision` fixes the
  number of cases with those two prefixes at exactly 30.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths are derived at create-plan from every task's
`files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated entries
in addition to the feature-specific paths:

- `feature-docs/dbracket-opener-arith-scan/**`
- `test-docs/dbracket-opener-arith-scan/**`

`feature-docs/dbracket-opener-arith-scan/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the phase
documents and by `references/phase-state.md`; this section cites them and
restates none of their rules.

`test-docs/dbracket-opener-arith-scan/**` covers
`test-docs/dbracket-opener-arith-scan/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC author
explicitly removes them; their absence is never assumed by silence — removal
is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed at
verification time must be CONTAINED IN the declared set, not equal to it. A
feature that produces no implement tasks generates no
`test-docs/dbracket-opener-arith-scan/` directory at all; the declared
`test-docs/dbracket-opener-arith-scan/**` entry is still correct in that case
— a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: Pass each form of AC-1 / AC-4 to `_args_json_nameref_scan()` (the
  six operators and `-v`, `&&` / `||`, and the forms whose name inside the
  parentheses is an allow-list name) - it returns true. Before the fix it
  returns false, so this is a regression-detection test.

### Integration Tests
- [ ] TS-2: Run ARRAY + form + `; ` + a notion call with `--session "$SID"`
  through `Spy(...).kinds()` - the result is `[KIND_INSPECTED]` (AC-2 / AC-3 /
  AC-4).

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-3: False-positive prevention: the forms of AC-5 that are read as
  certain stay false (certain) - the result is `[KIND_NOTHING]`.
  `[[ ( a == b ) && true ]]` stays uncertain from the command-level reading -
  with the array assignment, the result is `[KIND_INSPECTED]`.

### Regression Tests
- [ ] TS-4: Case table: the deny / allow cases added to
  `destructive-guard-cases.json` match in both decision and reason ID under
  `run-destructive-guard.py`.
- [ ] TS-5: The existing suites (all cases of `run-destructive-guard.py`, all
  tests of `tests.test_destructive_guard_args_json`) pass.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None
