# Implementation Plan: codex-guard-for-wordlist-glob-qualifier

## Overview
Make `_skip_substitution` in codex-hook-interactive-guard read a `#` inside
a nested entry of a zsh `for name (words)` word list as a word character,
in both plugin copies, and pin the fix with deny rows in the shared case
table. The feature is one task (task0001).

## Technology Stack
- **Language**: Python 3, standard library only (an existing constraint of
  the hook, checked by the test module's static-constraint tests).
- **Tests**: standard-library unittest, `tests/test_codex_hook_interactive_guard.py`.
- **New dependencies**: none.

## Layer Structure
One layer: the hook script, which reads a PreToolUse(Bash) JSON on stdin,
reads `tool_input.command` statically and prints a deny decision or
nothing. It is shipped as two copies, one per plugin:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`

The test module runs one case table against both copies.

## Shared Components
None. The feature has one task, so no component is built by one task and
used by another.

## Conventions
- **Byte identity**: the two copies are changed in the same change and stay
  byte-identical (repository rule `.claude/rules/hook-tests.md`; checked by
  `TestCopies.test_the_two_copies_are_byte_identical`).
- **Case table**: `CASES` rows are (expected verdict, label, command) with
  the verdict `deny` or `silent`; the same table runs against both copies.
  Existing rows are never removed or edited. A missed deny is recorded as a
  row before it is fixed.
- **Test command**: `python3 -m unittest tests.test_codex_hook_interactive_guard`,
  run from the repository root in the same change as any edit to either
  copy.

## Cross-task Design Decisions

### D1: One task for the whole change
- **Decision**: the fix to both copies, the docstring update and the new
  case rows form a single task.
- **Rationale**: the repository requires the two copies to be changed
  together and kept byte-identical, and the case table runs against both.
  Splitting by file would put parallel tasks on byte-coupled files;
  splitting the rows from the fix would leave a test-only task whose
  acceptance cannot pass without the other task.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reading `#` as a word character in a nested entry lets a quote character after it open a quote, moving where the substitution closes for some input | Low | Medium | The change is limited to nested entries (SPEC A1, A2); the existing word-list rows and the TS26 timing test stay unchanged and keep passing (task0001 AC-3, AC-4) |
| The two copies diverge, leaving one plugin's guard fail-open | Low | High | Byte-identity test (task0001 AC-5) |
| The added check costs more than constant time per character | Low | Medium | One look at the entry beneath the top of the stack; TS26 timing test (task0001 AC-4) |

## Open Questions
- None.
