# Implementation Plan: codex-guard-brace-anon-arg-rescue

## Overview
In both copies of codex-hook-interactive-guard, a lone bare `}` that follows
a rescuable chain of provisional argument groups closes the enclosing `{`
group (plain brace group, anonymous-function body or function-definition
body), so an interactive launch after the rescued separator is judged. The
whole change is carried by one task, task0001.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3)
- **Test framework**: unittest, `tests/test_codex_hook_interactive_guard.py`
- **New dependencies**: none. No license to record; `project.license` is `none`.

## Layer Structure
| Layer | Responsibility | May depend on |
|---|---|---|
| Hook entry | Reads the hook input, extracts the command string, emits a deny verdict or no output | Command parser |
| Command parser (`_Parser` body reader, `_Group` frames, `_rescue_argument_groups`) | Reads the string, tracks open groups and their first direct separators, reaches deny or undecidable | Standard library only |
| Tests | Drive both copies with one CASES table and the structural test classes | Both copies, read-only |

This feature changes only the command parser layer and the tests. The hook
entry, the verdict output format and the existing test classes' contracts
stay as they are.

## Shared Components
None. The feature has a single task, so no component is built by one task
and consumed by another. The two guard copies are one artifact kept
byte-identical (see Conventions), not two components.

## Conventions
- **Two copies**: `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py` change in the same
  change and stay byte-identical (NFR2, TestCopies).
- **CASES format**: each entry is (expected verdict, label, command) with the
  expected verdict `deny` or `silent`; every entry runs against both copies.
- **Undecidable stays silent**: when the reader cannot decide, it gives no
  output. The new rule turns a reading into a decision only when all of its
  conditions hold; a check that fails changes no parser state.
- **Complexity**: linear time in the input length, no recursion (NFR1,
  TestNoRecursion).
- **Docstrings and comments**: English. Existing marker sentences that the
  tests check are kept verbatim.
- **Version fields**: no task edits a plugin `version` field (NFR4); the
  repository's Actions workflow handles version bumps.

## Cross-task Design Decisions

### Single-task decomposition
- **Decision**: one task covers the parser rule, the docstrings, both copies
  and the tests.
- **Rationale**: NFR2 requires both copies to change together and stay
  byte-identical. The parser rule, the docstrings that describe it, and the
  marker test that checks those docstrings in both copies touch the same
  regions of the same three files. Splitting them into parallel tasks would
  put concurrent edits into those regions of two byte-identical files, and the
  tests written first under TDD depend on the rule they exercise.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The rescue decision at `}` and the end-of-input rescue in `_rescue_argument_groups` disagree on which chains qualify | Medium | High (new misses or spurious denies) | task0001 defines the chain's separator condition once and applies it at both points; the TS16 and TS17 cases pin the non-qualifying separators |
| The new close path fires on a `}` that zsh does not treat as closing, or a failed check alters parser state | Medium | High | Only a lone bare `}` word reaches the check; a failed check changes nothing; TS18 to TS21 and every existing CASES entry are kept as regression guards (TM-2) |
| A per-`}` walk over open groups makes deep inputs quadratic | Medium | Medium (hook time-out) | Values fixed when each group opens; TS22 performance test (TM-3) |
| The two copies drift apart | Low | High (the bypass stays open in one plugin) | TestCopies |
| A docstring sentence to be rewritten is also an existing test marker | Low | Low | Marker text is kept verbatim; a conflict that cannot be resolved that way is reported as a plan deviation instead of deleting the marker |

## Open Questions
- None.
