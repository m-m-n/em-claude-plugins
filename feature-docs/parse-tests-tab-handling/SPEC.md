# Feature: parse-tests-tab-handling

## Overview

`parse_tests`, used by the record check in `tests/test_tests_yaml_id_resolution.py`,
stops handling a `tests` list correctly when a line in it contains a tab.
With this change, a `tests` list that contains tab lines still yields one
failure message that carries both the extraction errors and the resolution
errors of every readable ID.

## Objectives

- In `parse_tests` of the record check in `tests/test_tests_yaml_id_resolution.py`,
  report extraction errors and resolution errors of readable IDs together in a
  single failure message even when lines containing tabs are present
  (fulfilling the purpose of the record check's FR2).

## Acceptance Criteria

`<TAB>` below denotes a literal tab character.

### AC-1 (covers FR1)
- [ ] `extract_text` receives `acceptance_tests:` / `  AC-1:` / `    tests:` /
  `      <TAB>- tests.nope.bad` / `      - tests.nope.good`.
- [ ] `acs['AC-1'] == ['tests.nope.good']`.
- [ ] The errors for AC-1 include `tab in indentation` and do not include
  `inconsistent indentation of fields`.
- [ ] `check_record` reports exactly one resolution error, for `tests.nope.good` of AC-1.

### AC-2 (covers FR2)
- [ ] After `tests:`, the only line is the tab line `      <TAB>- tests.nope.bad`.
- [ ] Both when it is followed by `    red_confirmed: true` and when it is
  followed by end of file, AC-1 has exactly one error, `tab in indentation`.
- [ ] `neither a value nor items` is not reported, and `acs['AC-1'] == []`.

### AC-3 (covers FR3)
- [ ] `extract_text` receives `acceptance_tests:` / `  AC-1:` / `    tests:` /
  `      - tests.nope.fragment` / `        <TAB>continued` / `      - tests.nope.control`.
- [ ] `acs['AC-1'] == ['tests.nope.control']`, and AC-1 reports `tab in indentation`.
- [ ] `tests.nope.fragment` does not appear in any error line of `check_record`.

### AC-4 (covers FR4)
- [ ] With `      - tests.nope.kept` / `      <TAB>x` / `      - tests.nope.after`,
  `acs['AC-1'] == ['tests.nope.kept', 'tests.nope.after']`.
- [ ] AC-1 has exactly one error, `tab in indentation`.

### AC-5 (covers FR5, NFR1, NFR2, NFR3)
- [ ] `python3 -m unittest tests.test_tests_yaml_id_resolution` succeeds.
- [ ] `python3 -m unittest discover -s tests` succeeds.
- [ ] No existing test case is removed and no existing expected value changes.

## Technical Requirements

### Functional Requirements
- **FR1:** Continue reading after a tab line in the first item. When the item
  line immediately following the `tests` key contains a tab, report
  `tab in indentation` for each tab line and continue parsing the list. The
  indentation of list items is determined by the first line that contains no
  tab. Subsequent single-line IDs are extracted and checked for resolution.
  Subsequent items are not reported as `inconsistent indentation of fields`.
- **FR2:** A `tests` block that ends with tab lines only. When what follows
  the `tests` key consists only of lines containing tabs (followed by another
  field or by end of file), report only `tab in indentation` for each tab
  line. Do not report `tests key has neither a value nor items`.
- **FR3:** Drop the fragment on a deeper continuation line containing a tab.
  Inside a list item, a line whose leading spaces outnumber the item's
  indentation and are then followed by a tab is reported only as
  `tab in indentation`. If the preceding element is held as an ID read on a
  single line, that ID is removed from the resolution targets. Deeper lines
  that follow are left to the existing handling.
- **FR4:** A tab line at the same depth is not a continuation line. Inside a
  list item, a line whose leading spaces equal the item's indentation and are
  then followed by a tab is not treated as a continuation line. Report only
  `tab in indentation`, and keep the preceding ID among the resolution targets.
- **FR5:** Tests that detect regression. Add tests covering the behaviour of
  FR1 through FR4 to `tests/test_tests_yaml_id_resolution.py`, including
  reproduction steps 1 and 2 from the ticket.

### Non-Functional Requirements
- **NFR1 - Dependencies:** The test code imports only the standard library.
- **NFR2 - Compatibility:** Existing test cases (including the existing
  `tab in indentation` cases that contain tabs) are not removed, and their
  expected values do not change.
- **NFR3 - Change scope:** Changes are limited to `tests/test_tests_yaml_id_resolution.py`.

## Implementation Approach

### Architecture

The change is confined to the processing order of the parser (`parse_tests`)
inside the test module `tests/test_tests_yaml_id_resolution.py`. There is no UI,
API, or data store involved; the design step was skipped.

### Dependencies

**Internal Dependencies:**
- `tests/test_tests_yaml_id_resolution.py`: `parse_tests`, `extract_text`, `check_record`

**External Dependencies:**
- None (standard library only, per NFR1)

### File Structure

```
tests/
└── test_tests_yaml_id_resolution.py   # parse_tests fix and new tests (FR1-FR5)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/parse-tests-tab-handling/**`
- `test-docs/parse-tests-tab-handling/**`

`feature-docs/parse-tests-tab-handling/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/parse-tests-tab-handling/**` covers
`test-docs/parse-tests-tab-handling/{T}.tests.yaml`, the per-task test record.
It is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/parse-tests-tab-handling/` directory at all; the declared
`test-docs/parse-tests-tab-handling/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (AC-1): In a `tests` block whose first item is a tab line, the
  subsequent single-line ID is extracted and resolved, and no field
  indentation mismatch error is reported.
- [ ] TS-2 (AC-2): In a `tests` block consisting only of tab lines (followed
  by another field, and followed by end of file), only the tab error is reported.
- [ ] TS-3 (AC-3): With a tab continuation line deeper than the item, the
  preceding fragment disappears from both `acs` and the `check_record` error
  lines, and the subsequent ID remains.
- [ ] TS-4 (AC-4): With a tab line at the same depth as the item, the IDs
  before and after it both remain, and only the tab error is reported.

### Integration Tests
- [ ] TS-5 (AC-5): Both the module-level run and the full run via `discover` succeed.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- Covered by TS-2 (tab-only `tests` block, both terminations), TS-3, and TS-4.

## Assumptions

- **A1:** Lines with a tab in their indentation continue to be reported as
  unsupported notation (`tab in indentation`) after the fix. The notation
  scope of SC-2 does not change.
- **A2:** A tab continuation line deeper than the item is reported only as
  `tab in indentation`, and the preceding fragment is dropped. Deeper lines
  that follow are left to the existing handling.
- **A3:** A line in which a tab follows the same number of spaces as the
  item's indentation is not treated as a continuation line.
- **A4:** When what follows `tests:` ends with tab lines only, only the tab
  errors are reported, and `tests key has neither a value nor items` is not reported.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None

## References

- Target module: `tests/test_tests_yaml_id_resolution.py`
