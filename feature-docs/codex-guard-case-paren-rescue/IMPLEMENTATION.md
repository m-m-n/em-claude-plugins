# Implementation Plan: codex-guard-case-paren-rescue

## Overview

A narrow fix to codex-hook-interactive-guard (the em-workflow and em-review
copies): a case mark on provisional groups, inherited along the provisional
chain, turns off the paren rescue for that chain, removing the deny-to-silent
regression from review finding 5e71ff00fdbe5aff. The feature is one task
(task0001).

## Technology Stack

- **Language**: Python 3, standard library only — the existing guard scripts
  and their unittest suite.
- **New dependencies**: none (`project.license` is `none`; no license record
  is needed).

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Guard (two copies) | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read the proposed command text and decide deny or silent |
| Tests | `tests/test_codex_hook_interactive_guard.py` | Run the CASES table, the byte-identity check, the docstring-marker checks and the depth / linearity checks against both copies |

Allowed dependency direction: tests load both guard copies; the two copies
never depend on each other.

## Shared Components

No component is shared between tasks: the feature has a single task
(task0001), which owns every file above.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

## Conventions

- **Byte identity**: the em-review copy is byte-identical to the em-workflow
  copy after every commit that touches either (NFR2;
  `.claude/rules/hook-tests.md`).
- **CASES rows**: `(expected, label, command)` with expected `deny` or
  `silent`; the same table runs against both copies; existing rows are never
  edited or removed (SPEC.md constraint A5).
- **Parser cost**: linear in input length, no recursion (NFR1).
- **Docstring markers**: every marker the existing tests check is kept
  verbatim (FR5).

## Cross-task Design Decisions

### D1: One task for both copies and the test table

- **Decision**: the guard change, its replication into the second copy and
  the new CASES rows form a single task.
- **Rationale**: the two copies must change byte-identically in the same
  commit (FR6, NFR2), and the CASES table is the TDD contract for both;
  splitting them would put parallel edits on the same files with no ordering
  between tasks.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The mark fires on a `case` that is not a command-position keyword (argument position, quoted), turning connected forms into deny | Medium | Medium | TS-7 / TS-8 rows expecting silent; FR1's four-part condition |
| Inheritance implemented as an ancestor walk at `)` time, making the parse super-linear | Medium | High | Value fixed from the parent alone when the child opens (FR2); depth / linearity tests (TS-10); THREAT-MODEL.md TM-2 |
| The inherited value folded into `outer_blocked`, changing the brace rescue | Low | High | Separate value (FR2, constraint A2); existing brace-rescue rows unchanged (TS-10) |
| The two copies drift | Low | Medium | Byte-identity test (TS-10) |
| A docstring rewrite drops a marker the tests check | Low | Low | Docstring-marker tests (TS-10) |

## Open Questions

- None.
