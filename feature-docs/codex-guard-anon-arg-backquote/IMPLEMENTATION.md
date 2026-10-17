# Implementation Plan: codex-guard-anon-arg-backquote

## Overview

Fix a fail-open regression in `codex-hook-interactive-guard.py`. A `(`...`)`
range among the arguments of a zsh anonymous function that holds a triggering
backquote falls back to the provisional-group reading, so the anonymous body's
explicit `python3 -i` is denied again. The feature is one task (task0001).

## Technology Stack

- **Language**: Python 3, standard library only (NFR2)
- **Tests**: `unittest`, in `tests/test_codex_hook_interactive_guard.py`
- **New dependencies**: none, so there is no license to record (`project.license` is `none`)

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Guard (two copies) | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read the PreToolUse JSON from stdin, parse the command string, print one deny object or nothing |
| Test suite | `tests/test_codex_hook_interactive_guard.py` | The `CASES` table and the structural tests (documentation, performance, recursion, static constraints, byte identity), run against both copies |

Dependency direction: the test suite runs and reads both guard copies. The
guard depends on nothing outside the Python standard library.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| The two guard copies | One parser and one verdict, shipped in two plugins | After every commit the two files are byte-identical. The hook's input/output is unchanged: stdin JSON in, exactly one deny object or no output out | task0001 |
| `CASES` table | Regression table for the guard's verdicts | Rows are (verdict `deny` or `silent`, Japanese label, command). Labels and commands are unique. Every row runs against both copies. Existing rows are never removed or altered | task0001 |

## Conventions

- Change both guard copies in the same commit and keep them byte-identical
  (FR8).
- Add regression rows to `CASES` in the existing three-element form. Never
  remove an existing deny row.
- Docstrings are in English. A docstring and the `TestGuardDocumentation`
  marker that checks it change in the same commit.
- Parsing stays linear in the string length and uses no recursion (NFR1).
  Range scans stay charged to the existing work cap.
- Standard library only. No file, network or child-process access. The verdict
  depends on the command string alone (NFR2).
- Error-handling policy (existing, unchanged): input the parser cannot decide
  gives no output. This feature only routes the backquote case back to a
  decidable reading. Its one undecidable outcome is an unclosed backquote
  (FR6).
- Commands in tests are hook input only, never executed.
- Test commands, run from the repository root:
  `python3 -m unittest tests.test_codex_hook_interactive_guard` (focused) and
  `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
  (component).

## Cross-task Design Decisions

### D1: One task

- **Decision**: the feature is one task.
- **Rationale**: the two copies must change in the same commit (FR8). The
  docstring markers in the test file must change in the same commit as the
  docstrings (FR7). The new `CASES` rows are the TDD contract for the parser
  change. A split would give parallel tasks that edit the same functions in the
  same three files, with tests that fail until a sibling task merges.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A pre-existing `CASES` row changes verdict | Low | High | No existing row has a backquote inside an argument range. task0001 AC-5 requires every existing row to pass unchanged |
| The new trigger leaks into the reading of `$(` and process substitution | Low | Medium | The trigger is a separate scan result, and the substitution skipper does not read it. The existing `$(` rows still pass |
| The new fallback path makes the parse quadratic | Low | Medium | The work-cap charge is unchanged. A performance shape is added (TM-2) |
| The two copies diverge | Low | Medium | The existing byte-identity test |
| The accepted false deny for a balanced backquote followed by a stdin redirect surprises users | Medium | Low | Accepted by the requirements (SPEC.md "Known False Deny") and pinned by a labelled `CASES` row |
| The docstring wording breaks an existing documentation marker | Medium | Low | Keep the existing markers verbatim, or update them in the same commit |

## Open Questions

- None.
