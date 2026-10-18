# Implementation Plan: codex-guard-anon-heredoc-delim-dq-subst

## Overview
Make codex-hook-interactive-guard register the same heredoc delimiter as zsh
when the delimiter range of an anonymous-function heredoc contains a
double-quoted command or arithmetic substitution. The fix moves all quote
removal (backslash pair, single quote, double quote) into one shared reader,
called by both word reading and delimiter-range quote removal. One task
(task0001) delivers the feature, so this document only frames it. The
reader's contract and the detailed design are in `tasks/task0001.md`.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3).
- **Tests**: the repository's unittest suite, specifically `tests/test_codex_hook_interactive_guard.py`.
- **New dependencies**: none. No license to record; `project.license` is `none`.

## Layer Structure
The guard is one module with no architectural layers. Inside it, the
feature fixes one call direction (NFR2):

1. Readers: the parse body's word reading, and the delimiter-range quote removal (`_remove_range_quotes`).
2. The shared quoted-unit reader (new). It takes over the double-quote reading now done by `_double_quoted`.
3. `_skip_substitution` (existing, iterative).

Calls go only downward (1 → 2 → 3). Level 3 never calls level 2 or 1, and
no level calls itself.

## Shared Components
None across tasks, because the feature has one task. Two callers inside
that task share the quoted-unit reader, and its contract is pinned in
`tasks/task0001.md`.

## Conventions
- Both guard copies are edited in the same change and stay byte-identical (FR6): `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`.
- Regression cases go into the `CASES` table of `tests/test_codex_hook_interactive_guard.py` as (expected verdict, label, command), with verdict `deny` or `silent`. The same table runs against both copies.
- Error policy: an input the guard cannot read the way zsh does is undecidable (the module's existing `_Undecidable` signal), and the guard reports it as silent (SPEC.md Error Handling). No new error kind is added.
- The plugins' `plugin.json` and `.claude-plugin/marketplace.json` are not part of this feature's change set (NFR4).

## Cross-task Design Decisions
None, because the feature has one task. The reader contract, the limit
semantics and the overrun handling are in `tasks/task0001.md`.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Moving the word reader onto the shared reader changes ordinary word reading: empty quotes, backslash-newline, trailing backslash, dynamic flag | Medium | High: a new miss or false deny on common commands | New FR5 cases (TS-6), plus all existing `CASES` passing unchanged (TS-7). THREAT-MODEL.md TM-3 |
| The range-side double-quote branch differs from the word reader's rule in more than substitutions, so adopting the shared rule changes range behavior beyond FR3 | Low | Medium | Existing delimiter-range cases must keep their verdicts (TS-7). A conflict is reported as a plan deviation, not settled by a silent rule change |
| A call cycle between `_skip_substitution` and the shared reader | Low | High | TestNoRecursion (TS-8). THREAT-MODEL.md TM-4 |
| The two copies drift apart | Low | Medium | TestCopies (TS-8) |

## Open Questions
- None.
