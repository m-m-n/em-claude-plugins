# Feature: codex-guard-anon-arg-escaped-backquote

## Overview

`codex-hook-interactive-guard.py` (both the em-workflow and em-review copies)
must deny an explicit `python3 -i` even when the command contains, outside
quotes, a backquote command substitution that nests a backslash-escaped
backquote. This restores the behaviour lost as a regression surfaced by
`codex-guard-anon-arg-backquote` (review round 1, stable_id
`dfdc820511d4c859`).

REQUIREMENTS.md is not produced for this feature (reduced tier); this SPEC
carries the requirement IDs itself.

## Objectives

- Return codex-hook-interactive-guard (both copies) to a state where an
  explicit `python3 -i` is denied even when an unquoted backquote contains a
  backslash-escaped backquote (a nested command substitution).

## Technical Requirements

### Functional Requirements

- **FR1: Skip backslash pairs when searching for the end of an unquoted backquote.**
  In `parse`, the unquoted-backquote handling (currently lines 1464-1469,
  `` s.find("`", i + 1) ``) skips each backslash together with the single
  character after it while searching for the closing backquote, the same way
  the `b` context of `_skip_substitution` does. The first backquote that is
  not part of such a pair is the closing backquote, and the span from the
  opening to the closing backquote is added to the word as one dynamic chunk.
  When no closing backquote is found, the result stays `_Undecidable("quote")`
  as before.
- **FR2: Identical change in both copies.**
  The change is applied to both `em-workflow/scripts/codex-hook-interactive-guard.py`
  and `em-review/scripts/codex-hook-interactive-guard.py` within the same
  change, and the two copies remain byte-identical.
- **FR3: CASES row that detects recurrence.**
  `tests/test_codex_hook_interactive_guard.py`'s `CASES` gains a row whose
  expected decision is `deny` for the command below.

  Raw characters:

  ```
  zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo \`echo x\``)'
  ```

  As a Python literal:

  ```
  "zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo \\`echo x\\``)'"
  ```

### Non-Functional Requirements

- **NFR1 - Performance:** The closing-backquote search runs in time linear in
  the input length and uses no recursion (TestNoRecursion and
  TestMalformedAndDeepInput pass).
- **NFR2 - Dependencies:** Only the standard library is used, and the
  TestStaticConstraints constraints are satisfied.
- **NFR3 - Compatibility:** The decisions of the existing `CASES` and of all
  other tests do not change.

## Acceptance Criteria

- [ ] AC-1 (FR1, FR2): Feeding a JSON whose `tool_input.command` is the FR3
  command to the standard input of each copy outputs a JSON with
  `permissionDecision: deny`.
- [ ] AC-2 (FR3): `CASES` has exactly one row with the FR3 command as `deny`,
  and `python3 -m unittest tests.test_codex_hook_interactive_guard` passes
  against both copies.
- [ ] AC-3 (FR2): The two copies are byte-identical
  (`TestCopies.test_the_two_copies_are_byte_identical` passes).
- [ ] AC-4 (NFR1, NFR2, NFR3):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
  passes.

## Implementation Approach

### Files

```
em-workflow/scripts/codex-hook-interactive-guard.py   # parse: unquoted-backquote closing search
em-review/scripts/codex-hook-interactive-guard.py     # byte-identical copy
tests/test_codex_hook_interactive_guard.py            # CASES row (FR3)
```

### Dependencies

**Internal Dependencies:**
- `_skip_substitution` (`b` context): the backslash-pair skipping rule FR1
  follows.

**External Dependencies:**
- None (standard library only, NFR2).

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
- [ ] TS-1 (FR1, FR2, FR3): The FR3 command, run through both copies as a
  `CASES` row, is denied.
- [ ] TS-2 (NFR1, NFR2, NFR3): The existing `CASES` (including the
  backquote-related deny / silent rows at lines 558-567) and TestFailOpen's
  `` python3 -i `echo` `` keep their current decisions.
- [ ] TS-3 (FR2): The byte-identity test for the two copies passes.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A-1:** The reproduction command, in raw characters, is the FR3 command:

  ```
  zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo \`echo x\``)'
  ```

  The backslashes garbled in the Notion body were read according to the
  orchestrator's pre-investigation conclusion.
- **A-2:** FR1's scope is every backquote `parse` reads outside quotes, not
  only those inside an anonymous function's arguments.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Both copies remain byte-identical

## Open Questions

None.
