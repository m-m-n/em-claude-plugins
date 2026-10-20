# Implementation Plan: codex-guard-case-reading-fixes

## Overview
Remove three misreads of a `case` statement inside `$( )` in the
substitution reader of codex-hook-interactive-guard (both plugin copies) —
argument-position `case` / `esac`, a comment directly after a pattern `)`,
and line continuations — and pin each with `CASES` rows and linear-time
tests. One task, task0001, carries the whole change.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3; enforced by
  `TestStaticConstraints`).
- **Tests**: unittest — `python3 -m unittest tests.test_codex_hook_interactive_guard`
  for the guard, `python3 -m unittest discover -s tests` for the whole suite.
- **New dependencies**: none (nothing to record against `project.license`).

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Hook script (two copies) | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read a PreToolUse(Bash) event and answer deny or silent for an interactive launch. This feature changes only the substitution reader (`_skip_substitution` and the methods it reaches) and their docstrings. |
| Tests | `tests/test_codex_hook_interactive_guard.py` | `CASES` table run against both copies, plus structural tests (`TestCopies`, `TestNoRecursion`, `TestSubstitutionSkipCallStructure`, `TestStaticConstraints`, `TestSubstitutionSkipDocumentation`) and size/time tests (`TestCaseStatementsInASubstitution`). |

Dependency direction: the tests load both script copies by path; the two
copies never import each other.

## Shared Components

This feature has a single task, so no component is built by one task and
consumed by another. The table records the contracts that task0001 and any
later task touching these files (rework tasks included) must keep.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| The two guard script copies | Identical hook behavior in em-workflow and em-review | Post: after every commit that changes either copy, the two files are byte-identical (FR6; checked by `TestCopies`). | task0001 |
| `CASES` table | Decision regression table for the guard | Each row is (expected verdict, label, command) with verdict `deny` or `silent`; every row runs against both copies; a pre-existing row is never removed and never changes verdict (SPEC A6). | task0001 |
| Substitution reader (`_skip_substitution`) | Skip a `$( )` body and report where it ends, or that the read is undecidable | Pre: its call signature and callers are unchanged. Post: its result keeps its current form and meaning, including the undecidable result and how callers handle it; it finishes in time linear in the input length (NFR1); no method it reaches is `_skip_substitution`, `_read_quoted_unit`, `parse` or `_remove_range_quotes` (NFR2); the docstring phrases pinned by `TestSubstitutionSkipDocumentation` remain (FR7). | task0001 |

## Conventions
- Two-copy edits: change one copy, then make the other byte-identical in
  the same commit; never commit a state where the copies differ.
- `CASES` labels carry the SPEC scenario ID (`TS1` … `TS19`) so a failing
  row traces back to SPEC.md.
- Notation in plans and tests follows SPEC.md: `<NL>` is a newline, and
  `\<NL>` is a backslash directly followed by a newline (a continuation
  pair). The test source must produce exactly those bytes.
- The plugin `version` fields (`plugin.json`, `.claude-plugin/marketplace.json`)
  are not part of this feature's change set (NFR4).

## Cross-task Design Decisions

### D1: One task for the whole change
All three fixes live in the same reader in the same two files, and the two
files must stay byte-identical. Parallel tasks would edit the same function
in both copies and conflict on every merge, and the new `CASES` rows and
linear-time tests can only pass against the fixed reader. task0001
therefore owns the reader change, both copies, the docstrings and every new
test. Affected tasks: task0001.

### D2: Scope limits from SPEC.md assumptions
The reading of positions after a `time` option, an assignment or a
redirection (A3), the main parser's case marks and continuation handling
outside `_skip_substitution` (A4), `#` after any `)` other than a pattern
`)` and the body-internal `x\<NL>#c` reading (A5), and zsh extendedglob
`(x)#` (A8) stay as they are. Any later task touching the reader keeps
these limits unless SPEC.md changes. Affected tasks: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The new command-position state changes the verdict of a pre-existing `CASES` row (for example a reserved word after a redirection or an assignment) | Medium | High | task0001 AC-7 runs every pre-existing row against both copies; A3 keeps those positions at argument position. |
| The keyword match on the pair-stripped sequence is retried inside a word, making long continuation runs quadratic | Medium | Medium | TS20–TS22 at `DEPTH` scale under `TIMEOUT` (task0001 AC-5, TM-4). |
| The two copies drift apart | Low | High | `TestCopies` (task0001 AC-6). |
| The docstring rewrite drops a pinned phrase | Low | Low | `TestSubstitutionSkipDocumentation` (task0001 AC-6). |

## Open Questions
- None.
