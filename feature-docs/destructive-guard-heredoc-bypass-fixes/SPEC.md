# Feature: destructive-guard-heredoc-bypass-fixes

## Overview

Close three remaining bypass paths (b0734a006de6f4d7 / a7c0d90ac3e44e5b /
f34ee27bc8c323b1) in the lexer of `em-workflow/hooks/destructive-guard.py`,
through which the hook returns allow for a destructive line that bash
executes. Requirements document: `REQUIREMENTS.md` in this directory.

## Objectives

- Close the three bypass paths (b0734a006de6f4d7 / a7c0d90ac3e44e5b /
  f34ee27bc8c323b1) so that the hook no longer allows a destructive line
  that bash executes.
- Remove none of the existing deny / ask cases (in particular T2 E-1 and
  T2 E-9).

## User Stories

Not applicable.

## Technical Requirements

### Functional Requirements

- **FR1:** Judge assignment words and builtin names on the logical word with
  in-word line continuations removed (b0734a006de6f4d7).
  `word_transition()` judges assignment words (`NAME=` / `NAME+=` / `NAME[`)
  and builtin names (declaration builtins, eval / let / alias) on the logical
  word obtained by removing every backslash-newline inside the word. The
  array start position (`ARR_END`) and the subscript start position
  (`SUB_AT`) stay as positions in the original input. A command that places a
  destructive line after `x\<newline>=( <<EOF` or
  `decl\<newline>are x=( <<EOF` is denied.
- **FR2:** Do not delay the body of a pending here-document at `NAME[` in a
  declaration builtin's arguments (a7c0d90ac3e44e5b).
  When reading `NAME[` in the arguments of declare / typeset / local /
  export / readonly, the hook must not delay the start of the here-document
  body and thereby hide, as non-command, a line that bash reads as body.
  Reproduction inputs that were deny in the baseline return to deny.
  T2 E-9 (`git reset --hard` after `declare -a x[0]=( <<EOF`) stays deny.
- **FR3:** Treat eval / let / alias separately from the declaration
  builtins.
  `NAME[` in the arguments of eval / let / alias is handled separately from
  the declaration builtins. Among the shapes identical to FR2, the eval /
  let / alias shapes confirmed by measurement on bash 5.3.9 to execute the
  hidden line are added as deny cases and fixed to deny. The deny of T2 E-1
  (`git reset --hard` after `eval x[a b]=( <<EOF`) and the reading of
  `SUBSCRIPT_ARRAY_FORMS` in `tests/test_destructive_guard_lexer_agreement.py`
  (registers no here-document operator) are preserved.
- **FR4:** Count extglob parse units distinguished by original position and
  origin (f34ee27bc8c323b1).
  `_count_extglob_units()` does not deduplicate parse units by the text
  before the parenthesis alone; it distinguishes them by their position in
  the original input and by which of the eval / -c expansions they came
  from. Distinct units with the same text before the parenthesis (e.g. an
  outer and an inner eval sharing the prefix `x=(@`) are not merged into
  one. This reproduction input yields the extglob-switch ask.
- **FR5:** Add the reproduction inputs to the case table.
  Add to `em-workflow/hooks/tests/destructive-guard-cases.json`, as
  `[expected verdict, label, command]` triples, the reproduction inputs of
  b0734a006de6f4d7 and a7c0d90ac3e44e5b (including the FR3 eval / let /
  alias shapes) as deny, and the reproduction input of f34ee27bc8c323b1 as
  ask. Existing cases are not removed and their expected verdicts are not
  changed.

### Non-Functional Requirements

- **NFR1 - Detection power:** The number of deny and ask cases in the case
  table does not decrease. Every existing case (including allow) passes with
  its expected verdict.
- **NFR2 - Work bound:** The logical-word judgment and the parse-unit
  distinction are done within the existing lexer work bound
  (`LEX_WORK_FACTOR`) without re-reading the input. The existing linearity
  tests pass.
- **NFR3 - Test execution:** In the same change,
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` all pass.
- **NFR4 - Standard library only:** The hook and the tests use only the
  Python standard library.
- **NFR5 - Version:** The em-workflow version is not changed by hand.

## Implementation Approach

### Architecture

**Components touched:**
```
em-workflow/hooks/destructive-guard.py
  word_transition()        FR1 (assignment word / builtin name judgment),
                           FR2, FR3 (NAME[ in declaration builtins vs eval / let / alias)
  _count_extglob_units()   FR4
em-workflow/hooks/tests/destructive-guard-cases.json
                           FR5
```

### Data Flow

Not applicable.

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/tests/run-destructive-guard.py`: case-table runner (NFR3)
- `tests/test_destructive_guard_lexer_agreement.py`: `TestStageAgreement`,
  `TestStageAgreementUnderExtglobOn`, `SUBSCRIPT_ARRAY_FORMS` (FR3, edge cases)

**External Dependencies:**
- Python standard library only (NFR4)

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py
└── tests/
    ├── destructive-guard-cases.json
    └── run-destructive-guard.py
tests/
└── test_destructive_guard_lexer_agreement.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-heredoc-bypass-fixes/**`
- `test-docs/destructive-guard-heredoc-bypass-fixes/**`

`feature-docs/destructive-guard-heredoc-bypass-fixes/**` covers
`REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These
are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/destructive-guard-heredoc-bypass-fixes/**` covers
`test-docs/destructive-guard-heredoc-bypass-fixes/{T}.tests.yaml`, the
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

Case-table entries (`em-workflow/hooks/tests/destructive-guard-cases.json`):

- [ ] TS1 (FR1, AC1): expected `deny`. Input:
  ```
  x\
  =( <<EOF
  git reset --hard HEAD
  EOF
  ```
- [ ] TS2 (FR1, AC2): expected `deny`. Input:
  ```
  decl\
  are x=( <<EOF
  git reset --hard HEAD
  EOF
  ```
- [ ] TS3 (FR2, AC3): expected `deny`. Shape: a here-document operator
  placed first, `NAME[` in the arguments of declare / typeset / local /
  export / readonly on the same line, and a destructive line that bash
  executes on a following line. The concrete input is fixed after
  confirming on bash 5.3.9 that the destructive line is executed.
- [ ] TS4 (FR3, AC4): expected `deny`. Shape: the TS3 shape with the
  command name changed to eval / let / alias, limited to the forms measured
  on bash 5.3.9 to execute the destructive line.
- [ ] TS5 (FR4, AC5): expected `ask`. Shape: an outer and an inner eval
  both carrying the prefix `x=(@`, with extglob switched between them (the
  f34ee27bc8c323b1 reproduction input).
- [ ] TS6 (FR2, FR3, NFR1, AC6): expected `deny`. Existing cases T2 E-1 /
  T2 E-9.
- [ ] TS7 (FR4, NFR1, AC8): expected `allow`. Existing case T2 AC-4.7
  (`x=( @(foo|bar) ); cat <<"EOF"\nhello\nEOF`).

### Integration Tests

- [ ] TS8 (FR3, NFR2, NFR3, AC7, AC10): expected `pass`.
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` all pass, including the existing
  `SUBSCRIPT_ARRAY_FORMS` test unchanged.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] Consecutive backslash-newlines inside a word (`x\<newline>\<newline>=(`)
- [ ] Line continuation in the middle of `NAME[` or `+=`
  (`x\<newline>[0]=(`, `x+\<newline>=(`)
- [ ] Line continuation in the middle of the command name of eval / let /
  alias and of the other declaration builtins
- [ ] eval / let / alias with quoted arguments do not open an array (keep
  the allow of T2 E-15)
- [ ] declare prefixed by builtin / command is out of scope and stays allow
  (T2 E-16 / E-17)
- [ ] New cases are automatically included in `TestStageAgreement` of
  `tests/test_destructive_guard_lexer_agreement.py` (and, for those
  containing an extended-pattern parenthesis, in
  `TestStageAgreementUnderExtglobOn`) and must pass there as well

### Performance Tests
- [ ] Existing linearity tests pass (NFR2)

## Security Considerations

- **Input Validation:** FR1 to FR4.
- Other items: Not applicable.

## Error Handling

Not applicable.

## Performance Optimization

### Performance Goals
- Stay within `LEX_WORK_FACTOR` without re-reading the input (NFR2).

## Success Criteria

- [ ] AC1 (FR1): TS1 input is denied
- [ ] AC2 (FR1): TS2 input is denied
- [ ] AC3 (FR2): a reproduction input that delays the body of a pending
  here-document at `NAME[` in the arguments of a declaration builtin
  (declare / typeset / local / export / readonly) is denied
- [ ] AC4 (FR3): reproduction inputs of the same shape for eval / let /
  alias, measured on bash 5.3.9 to execute the hidden line, are denied
- [ ] AC5 (FR4): a reproduction input where an outer and an inner eval share
  the prefix `x=(@` and switch extglob midway yields ask
- [ ] AC6 (FR2, FR3, NFR1): T2 E-1 and T2 E-9 stay deny
- [ ] AC7 (FR3): the existing test confirming that no here-document operator
  is registered for each form of `SUBSCRIPT_ARRAY_FORMS` passes unchanged
- [ ] AC8 (FR4, NFR1): T2 AC-4.7 (`x=( @(foo|bar) ); cat <<"EOF"\nhello\nEOF`)
  stays allow
- [ ] AC9 (FR5, NFR1): every reproduction input is added to the case table,
  and the deny and ask counts are not lower than before the change
- [ ] AC10 (NFR2, NFR3): `run-destructive-guard.py` and
  `unittest discover -s tests` all pass

## Assumptions

All reversible.

- 765c3a53859569c2 (unifying the subscript / extglob scanners) is out of
  scope for this feature and handled in a separate task.
- The f34ee27bc8c323b1 reproduction input is added as ask; deny under
  unattended execution is ensured by the existing downgrade in `decide()`
  (the downgrade cases at the end of `run-destructive-guard.py`).
- Whether bash executes a line is judged by measurement on bash 5.3.9.
- round 2 medium findings such as 8633a419fec4b21c (excess ask from counting
  re-parses of the same parenthesis as multiple units) are out of scope.
- Existing deny / ask cases are not removed and their expected verdicts are
  not changed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/destructive-guard-heredoc-bypass-fixes/REQUIREMENTS.md`
- Findings: `feature-docs/destructive-guard-heredoc-syntax-error/reviews/round2.yaml`
