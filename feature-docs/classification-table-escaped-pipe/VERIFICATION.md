# Verification Document: classification-table-escaped-pipe

## Overview

**Feature**: classification-table-escaped-pipe / **SPEC.md**: `feature-docs/classification-table-escaped-pipe/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/classification-table-escaped-pipe/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the change is a Python test module with no build step)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests` (from the repository root of the integration worktree)
- Expected: no new failures compared with the base revision (NFR3)
- Coverage target: not applicable (no coverage tool is configured; standard library only)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC TS1: a one-row table whose hook cell contains a backslash-pipe inside the path (em-workflow/hooks/queue, backslash-pipe, stop_guard.py) and whose classification cell is the canonical READS_STATUS value is passed to parse_classification_table() | ClassificationTableError is raised; the message contains the phrase "not supported" and the backslash-pipe literal within the unsupported notice (not only inside the embedded row repr), and still carries the two-column expectation and the row repr | Unit |
| TS-2 | SPEC TS2: a one-row table whose hook cell is em-workflow/hooks/queue_stop_guard.py and whose classification cell is the reproduction value (reads tasks.{T}.status, backslash-pipe, journal) is passed to parse_classification_table() | ClassificationTableError is raised instead of the row being silently dropped; the message contains "not supported" and the backslash-pipe literal within the notice, and still carries the two-column expectation and the row repr | Unit |
| TS-3 | SPEC TS3: the single-column row only-one-column (no backslash-pipe) is passed to parse_classification_table() | ClassificationTableError is raised; the message does not contain "not supported" | Unit |
| TS-4 | SPEC TS4: the full test suite is run | The real document's classification table still parses to 4 rows; no new failures compared with the base revision | Integration |
| TS-5 | SPEC AC5 (FR4): the docstring of parse_classification_table() is inspected | The malformed-row Raises description states that backslash-pipe escapes are not interpreted and that such rows raise ClassificationTableError with an unsupported notice | Inspection |
| TS-6 | SPEC AC5 (FR2, NFR3): the diff of tests/test_hook_classification_pin.py against the base revision is inspected | Row splitting, the column-count check and classification-vocabulary validation are unchanged; the notice is added only in the column-count-mismatch branch and is triggered by a plain substring check on the row line; the message for rows without a backslash-pipe is unchanged; existing tests, including test_malformed_row_wrong_column_count_raises, are present and unmodified | Inspection |
| TS-7 | SPEC AC5 (NFR1, NFR2): the feature's full change set against the base revision is inspected | Outside feature-docs/ and test-docs/, the only changed file is tests/test_hook_classification_pin.py; it imports standard-library modules only; nothing is written under em-workflow/hooks/; no plugin version is changed | Inspection |

SPEC.md scenarios TS1 to TS4 correspond to TS-1 to TS-4. TS-5 to TS-7 are drawn from SPEC.md Success Criteria AC5 and NFR1 / NFR2.

### Edge Cases (SPEC.md)

- A row containing `\|` whose split yields exactly two cells: no unsupported notice; it fails through the existing classification-vocabulary or path-resolution validation, and its message is out of scope. Confirmed by TS-6 (the notice branch is reached only on a column-count mismatch).
- Escaped backslashes such as `\\|`: not analysed; detection is a plain substring check on the row line. Confirmed by TS-6.
- A trailing `\|`: no requirement.

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A table whose classification cell holds the reproduction value raises ClassificationTableError instead of dropping the row | TS-2 |
| AC2 | The message for a backslash-pipe row that does not split into two columns contains the two-column expectation, the row repr, the backslash-pipe literal and "not supported" | TS-1, TS-2 |
| AC3 | The message for a row without backslash-pipe that does not split into two columns is unchanged and does not contain "not supported" | TS-3, TS-6 |
| AC4 | Tests for FR3 cases (1) and (2) exist in tests/test_hook_classification_pin.py and pass | TS-1, TS-2 |
| AC5 | The real document table still parses to 4 rows, the suite has no new failures, row splitting is unchanged and the docstring records the backslash-pipe limitation | TS-4, TS-5, TS-6, TS-7 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3 |
| FR2 | task0001 | TS-4, TS-6 |
| FR3 | task0001 | TS-1, TS-2 |
| FR4 | task0001 | TS-5 |
| NFR1 | task0001 | TS-7 |
| NFR2 | task0001 | TS-7 |
| NFR3 | task0001 | TS-4, TS-6 |

## E2E Testing

None. The project has no E2E framework (SPEC.md: existing E2E tests none, run command not detected).

## Manual Testing (E2E Not Possible)

None beyond the inspection scenarios TS-5 to TS-7. The design step was skipped, so there is no mockup comparison.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit tests | 3 (TS-1 to TS-3) | 3 | 0 | 0 |
| Integration (full suite) | 1 (TS-4) | 1 | 0 | 0 |
| Inspection | 3 (TS-5 to TS-7) | 0 | 0 | 3 |
