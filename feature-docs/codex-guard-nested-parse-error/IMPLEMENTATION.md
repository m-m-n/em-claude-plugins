# Implementation Plan: codex-guard-nested-parse-error

## Overview
Make codex-hook-interactive-guard read a digit-only fd word of any length
before a redirect operator without raising, and skip a nested string whose
parse raises an unexpected error instead of letting the error silence the
whole guard. One task (task0001) carries the whole change.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1)
- **New dependencies**: none (no license to record)

## Layer Structure
One module, shipped as two byte-identical copies:
`em-workflow/scripts/codex-hook-interactive-guard.py` and
`em-review/scripts/codex-hook-interactive-guard.py`. The test module
`tests/test_codex_hook_interactive_guard.py` runs the same case table against
both copies. No layer or dependency direction changes.

## Shared Components
None. The feature has one task, so no component crosses a task boundary.

## Conventions
- **Parse-error policy of the guard** (applies to any later rework task on
  this feature):
  - Depth-0 parse error: no output (unchanged, docstring step 9).
  - Nested-string parse error, whether the undecidable signal or any other
    unexpected error: skip that string and continue from the command after
    the one holding it. A parse error is never a reason to deny (NFR5).
- **Two copies**: both copies change in the same change and stay
  byte-identical (FR4).
- **Regression cases**: new cases go into the test module's case table as
  (expected verdict, label, command), verdict `deny` or `silent`; commands in
  the table are unique (NFR3).
- **Version fields**: the change set includes no plugin manifest and no
  marketplace manifest (NFR4).

## Cross-task Design Decisions

### Single task
Decision: one task owns both guard copies and the test module.
Rationale: the copies must be byte-identical within one change (FR4), and the
case table must run against both. Splitting the copies across parallel
worktrees would make byte-identity depend on a merge.
Affected tasks: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The two copies drift | Low | High: em-review behaves differently from em-workflow | Both edited in task0001; copy-identity test (TS-8) |
| The broad catch around the nested parse hides a real defect in nested reading | Medium | Medium: a nested string that should deny is skipped silently | Broad catch limited to the nested parse; depth-0 handling and `_judge` unchanged; every existing case keeps its verdict (TS-8) |
| In-range fd words change verdict | Low | Medium | Boundary cases 2147483647 / 2147483648 and the all-zero case (TS-4, TS-5); existing cases unchanged (TS-8) |

## Open Questions
- [ ] Planning did not read the guard source. SPEC.md names only the
  conversion of the digit word before a redirect operator. If another
  digit-to-number conversion on the parse path can raise on a huge digit run
  at depth 0, the implementer reports it as a plan deviation rather than
  fixing it in this feature.
