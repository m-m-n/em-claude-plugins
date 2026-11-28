# Feature: dbracket-was-open-close-scan

## Overview

destructive-guard reads a `[[ ]]` conditional that `&&` / `||` split across
statements only up to its valid closer `]]`. Redirection targets after the
closer in the statement that holds it (such as `=~` or `-eq`) never drop the
exclusion of the following notion call. Other words after the closer, such as a
new `[[` after `then` / `do` and its operator words, are still read.

## Objectives

- In the `was_open` branch of `_args_json_conditional_step()`, read the words of
  the closing statement in order, close the conditional at the valid closer
  `]]`, and skip only the redirection targets after it.
- Keep the exclusion of the notion call that follows such a statement
  (`[[ true && true ]] >=~` / `>-eq`).
- Keep the detection of uncertain words that stand before the closer, and of a
  new `[[` (after `then` / `do`) and its operator words after the closer.

## Acceptance Criteria

- [ ] AC-1 (FR1, FR2): `_args_json_nameref_scan()` reads false for the chunk
  `[[ true && true ]] >=~` and for `[[ true && true ]] >-eq`.
- [ ] AC-2 (FR2): the command `[[ true && true ]] >=~; ` + the notion call with
  `--session "$SID"` (args-json command `git branch -D example`) gives
  `[KIND_NOTHING]` and the hook decision `allow`; the same with the array
  assignment `A=(json --mcp desktop-commander --tool start_process); ` in front.
- [ ] AC-3 (FR3): `[[ true && true =~ true ]]` and `[[ true && true -eq 0 ]]`
  followed by the same notion call (with the array assignment) give
  `[KIND_INSPECTED]` and `deny` with reason ID `git-branch-force-delete`; every
  existing CONDITIONAL_DENY / CONDITIONAL_ALLOW / CLOSER_OPERANDS form keeps its
  judgment.
- [ ] AC-4 (FR4): the docstring of `_args_json_conditional_step()` states that in
  a later statement only the redirection targets after the closer are not read,
  and that other words after the closer are still read.
- [ ] AC-5 (FR5, NFR1, NFR4): the rows of AC-2 / AC-3 / AC-6 stand in
  `destructive-guard-cases.json` under labels starting with
  `dbracket-was-open-close-scan` (deny rows with
  `{"rule": "git-branch-force-delete"}`, allow rows with no fourth element), and
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` pass.
- [ ] AC-6 (FR1, FR3): `if [[ true && true ]] then [[ 0 -eq SID=1 ]]; fi; ` and
  `while [[ true && true ]] do [[ -v x ]]; done; ` each followed by the same
  notion call give `[KIND_INSPECTED]` and `deny` with reason ID
  `git-branch-force-delete`.

## Technical Requirements

### Functional Requirements

- **FR1:** Read the closing statement in word order, close the conditional at the
  valid closer, and skip only the redirection targets after it.
  In the `was_open` branch of `_args_json_conditional_step()` (a statement
  entered while a conditional opened in an earlier statement is still open), the
  non-operator words are read in their order of appearance. Each word before the
  closer is checked as today: `_unsettled()` (a `=~` as written, also across a
  line continuation, or a word ending in one of `?*+@!` directly followed by
  `(`) and membership of its restored text in `_ARGS_JSON_DOUBLE_BRACKET_WORDS`
  make the statement uncertain (UNCERTAIN true, OPEN true). The first word
  written exactly `]]` with no stripped trailing carriage return is the closer:
  the conditional is closed there. After the closer, only redirection targets
  (the words that redirection operators such as `>` take) are not read. Other
  words after the closer, such as `then` / `do` followed by a new `[[` and its
  operator words, are still read as the existing reading reads them. A word
  whose restored text is `]]` but which is written with a backslash or a quote,
  or a `]]` with a stripped trailing carriage return, is not a closer and the
  reading continues past it, as today.
- **FR2:** The reported notion call keeps its exclusion. For
  `[[ true && true ]] >=~` followed by `; ` and a canonical notion call with
  `--session "$SID"`
  (`mcp-bridge run --mcp notion --tool notion-create-comment --session "$SID" --args-json '{"command":"git branch -D example"}'`),
  `_args_json_nameref_scan()` of the chunk reads false, the notion call is
  `KIND_NOTHING`, and the hook's decision is `allow`. The same holds with the
  array assignment `A=(json --mcp desktop-commander --tool start_process); ` in
  front, and with an operator word after the closer (`[[ true && true ]] >-eq`).
- **FR3:** Detection before the closer, and of a new `[[` after `then` / `do`,
  is kept. A `=~`, an extended pattern, or a word of
  `_ARGS_JSON_DOUBLE_BRACKET_WORDS` that stands before the closer in a
  continuation statement still makes the chunk uncertain, and the following
  notion call with `--session "$SID"` stays `KIND_INSPECTED` / `deny` with reason
  ID `git-branch-force-delete` (for example `[[ true && true =~ true ]]`,
  `[[ true && true -eq 0 ]]`). A new `[[` after `then` / `do` that follows the
  closer and holds such a word also keeps the following notion call
  `KIND_INSPECTED` / `deny` with the same reason ID (for example
  `if [[ true && true ]] then [[ 0 -eq SID=1 ]]; fi` and
  `while [[ true && true ]] do [[ -v x ]]; done`). A continuation statement with
  no closer keeps the existing behavior (open at a `;` / lone `&` or at the end
  of the chunk is uncertain). The opener-statement branch (`was_open` false) is
  not changed.
- **FR4:** Docstring. The docstring of `_args_json_conditional_step()` states that
  in a later statement that holds the closer, the words are read up to the
  closer, the redirection targets after the closer are not read, and other words
  after the closer (such as a new `[[` after `then` / `do`) are still read.
- **FR5:** Regression tests. A new test class in
  `tests/test_destructive_guard_args_json.py` pins FR1 to FR3, and
  `em-workflow/hooks/tests/destructive-guard-cases.json` gains the allow rows
  of FR2 and the deny rows of FR3 (including the `then` / `do` forms of AC-6)
  under labels starting with `dbracket-was-open-close-scan`; each deny row
  carries `{"rule": "git-branch-force-delete"}`. The rows are added before the
  fix.

### Non-Functional Requirements

- **NFR1 - Existing cases:** No existing allow / deny case of
  `destructive-guard-cases.json` or test of
  `tests/test_destructive_guard_args_json.py` is removed, and all pass.
- **NFR2 - Call site and responsibility:** `_args_json_conditional_step()` is
  called only from `_args_json_nameref_scan()`, holds no `permissionDecision` and
  no `destructive-guard/` reason ID, launches nothing and reads no file.
- **NFR3 - Static analysis only:** The judgment stays static analysis of the
  command string.
- **NFR4 - Label constraints:** New case labels do not start with
  `args-json-deferred-eval-bypass TS-16:` / `TS-17:`,
  `dbracket-opener-arith-scan`, or `dbracket-paren-group-spec-align`.
- **NFR5 - Version:** The plugin version is not changed (patch bump by GitHub
  Actions).

## Assumptions

- After `]]` in the same statement, Bash accepts redirections, a closing `)` of
  an enclosing group, and reserved words such as `then` / `do` that start
  further commands (which may hold a new `[[`). Skipping only the redirection
  targets loses no evaluating word; the command-level reading
  (`_args_json_declares_nameref()`) still reads the statement's simple commands
  as today. (reversible)
- The sentence in `feature-docs/dbracket-opener-arith-scan/SPEC.md` about the
  `was_open` branch scanning the whole statement records that feature's scope
  and is left as is; prior SPECs are not amended. (reversible)
- The opener-statement branch already stops at the closer (pinned by the existing
  test `test_an_operator_word_after_the_closer_is_not_scanned`) and is not
  changed. (reversible)

## Implementation Approach

### Architecture

**Component Diagram:**
```
_args_json_nameref_scan()
  └── _args_json_conditional_step()   (only caller: _args_json_nameref_scan)
        ├── opener-statement branch (was_open false)  -- unchanged
        └── was_open branch                           -- changed (FR1)
              ├── _unsettled()
              └── _ARGS_JSON_DOUBLE_BRACKET_WORDS
```

### Data Flow

```
continuation statement words (in order)
  → word before the closer: _unsettled() / _ARGS_JSON_DOUBLE_BRACKET_WORDS check
      → uncertain: (UNCERTAIN true, OPEN true)
  → first word written exactly `]]` (no stripped trailing carriage return): closer
      → conditional closed
  → after the closer: redirection targets are skipped; other words (e.g. `then` /
    `do` and a new `[[` with its operator words) are read as before
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `_unsettled()`: check of each word before the closer.
- `_ARGS_JSON_DOUBLE_BRACKET_WORDS`: membership check of each word's restored
  text before the closer.

**External Dependencies:**
- None.

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # _args_json_conditional_step() (FR1, FR4)
└── tests/
    └── destructive-guard-cases.json     # new allow / deny rows (FR5)
tests/
└── test_destructive_guard_args_json.py  # new test class (FR5)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/dbracket-was-open-close-scan/**`
- `test-docs/dbracket-was-open-close-scan/**`

`feature-docs/dbracket-was-open-close-scan/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/dbracket-was-open-close-scan/**` covers
`test-docs/dbracket-was-open-close-scan/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/dbracket-was-open-close-scan/` directory at all; the declared
`test-docs/dbracket-was-open-close-scan/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1, FR2): `_args_json_nameref_scan()` on `[[ true && true ]] >=~`
  and `[[ true && true ]] >-eq` - returns false; before the fix it returns true
  (regression detection). The closing statement reports (False, False) from
  `_args_json_conditional_step()`.

### Integration Tests
- [ ] TS-2 (FR2): `Spy(...).kinds()` on the AC-2 commands - gives
  `[KIND_NOTHING]`; `judge()` gives `allow`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-3 (FR3): Detection kept - `Spy(...).kinds()` on the AC-3 commands and on
  the `then` / `do` commands of AC-6 gives `[KIND_INSPECTED]`; `judge()` gives
  `("deny", "git-branch-force-delete")`.
- [ ] TS-4 (FR1, FR3): A non-closer `]]` (escaped, quoted, or with a stripped
  trailing carriage return) in the continuation statement before the real
  closer is read past. For `[[ a && \]\] == x ]] >=~` the continuation
  statement reports (false, false), and the scan still reads true because the
  command-level reading treats the statement's command name `]]` (written
  escaped) as uncertain. For `[[ a && true == X ]] >=~` and
  `[[ a && true == X ]] >-eq`, with X a non-closer `]]` form, the scan reads
  false. A continuation statement with `-eq` before a non-closer and no real
  closer stays uncertain.

### Regression Tests
- [ ] TS-5 (FR5, NFR1, NFR2, NFR3, NFR4): Case-table rows match decision and
  reason ID under `run-destructive-guard.py`; full suites pass.
- [ ] TS-6 (FR4): The docstring of `_args_json_conditional_step()` holds the
  revised statement of FR4 (words read up to the closer, redirection targets
  after the closer not read, other words after the closer such as a new `[[`
  after `then` / `do` still read).
- [ ] TS-7 (NFR5): The plugin version is unchanged.

### Performance Tests

Not applicable.

## Security Considerations

- **Input Validation:** The judgment stays static analysis of the command
  string (NFR3).
- Authentication, authorization, data protection, XSS, SQL injection and CSRF:
  not applicable.

## Error Handling

Not applicable.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 to AC-6 are satisfied
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `tests/test_destructive_guard_args_json.py`
- `feature-docs/dbracket-opener-arith-scan/SPEC.md`
