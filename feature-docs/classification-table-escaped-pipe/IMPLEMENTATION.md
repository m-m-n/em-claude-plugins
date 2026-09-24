# Implementation Plan: classification-table-escaped-pipe

## Overview

`parse_classification_table()` in `tests/test_hook_classification_pin.py` keeps its existing row splitting and adds, to the column-count-mismatch `ClassificationTableError` raised for rows containing `\|`, a notice that `\|` escapes are not supported; tests pin that behavior. The feature is one task (task0001); this document records only the feature-wide decisions.

## Technology Stack

- **Language**: Python 3 (existing repository test code)
- **Test framework**: Python standard library `unittest`, run as `python3 -m unittest discover -s tests`
- **New dependencies**: none. No license entries to record (`project.license: none`).

## Layer Structure

Not applicable. The change is confined to one test module at the repository root (`tests/`). No file under `em-workflow/` is touched.

## Shared Components

None. The feature has a single task, so no component is built by one task and consumed by another.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | - | - | - |

## Conventions

- Parser error messages stay in English, like the module's existing messages.
- Standard library only; nothing is written under `em-workflow/hooks/` (the module's existing AC-7 is retained).
- Existing tests in the module are neither modified nor deleted; new behavior is pinned by added tests.

## Cross-task Design Decisions

### D1: Explicit failure instead of escape interpretation

- **Decision**: The row splitting, column-count check and classification-vocabulary validation stay as they are. A non-separator row that does not split into two cells keeps raising `ClassificationTableError`; when that row line contains the substring `\|`, the message additionally states that `\|` escapes are not supported by this parser (literal `\|` and the phrase "not supported"). Rows without `\|` keep the existing message.
- **Source**: SPEC.md FR1, FR2; REQUIREMENTS.md 14.1 (create-spec.expected-behavior-option: explicit_failure).
- **Affected tasks**: task0001

### D2: One task for the whole change set

- **Decision**: The parser message branch, its docstring and the added tests live in the same file, function and test class, so the feature is planned as a single task.
- **Affected tasks**: task0001

### D3: No plugin version bump

- **Decision**: The change lies outside `em-workflow/`, so `.claude/rules/core-plugin-version-bump.md` does not apply and no plugin version is changed (SPEC.md File Structure).
- **Affected tasks**: task0001

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An assertion that the message contains the backslash-pipe literal passes without the new notice, because the embedded repr of the offending row already contains that two-character sequence (repr doubles the backslash, and the doubled form still contains backslash + pipe) | High | Medium | task0001 requires the literal to be verified within the notice, independent of the embedded row repr (task0001 AC-1, AC-2, Test Notes) |
| Test input meant to hold one backslash followed by a pipe is written with an unrecognized string escape, emitting a warning or holding different characters than intended | Medium | Low | task0001 Test Notes |
| An existing test in the module is edited while adding the new ones | Low | Medium | NFR3; diff inspection in VERIFICATION.md TS-6 |

## Open Questions

- None
