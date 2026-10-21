# Implementation Plan: codex-guard-case-reading-fixes

## Overview
Remove misreads of a `case` statement inside `$( )` in the substitution
reader of codex-hook-interactive-guard (both plugin copies), and pin each
with `CASES` rows and linear-time tests. task0001 (merged) fixed
argument-position `case` / `esac`, a comment directly after a pattern `)`,
and line continuations. task0002 makes the word after a compound-command
closing, a function head, or a loop or coproc head a command position
(FR9–FR11), removing the regressions review round 1 found in task0001's
reading (findings 8aed11cf08b2dc4c, 2fe94b219da49a89).

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

task0001 is merged, and task0002 is implemented on the integration branch
that carries it; no two tasks of this feature work on these files in
parallel. The table records the contracts that task0002 consumes from
task0001 and that every later task touching these files (rework tasks
included) must keep.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| The two guard script copies | Identical hook behavior in em-workflow and em-review | Post: after every commit that changes either copy, the two files are byte-identical (FR6; checked by `TestCopies`). | task0001, task0002 |
| `CASES` table | Decision regression table for the guard | Each row is (expected verdict, label, command) with verdict `deny` or `silent`; every row runs against both copies; a pre-existing row is never removed and never changes verdict (SPEC A6); a row's label carries its scenario ID from VERIFICATION.md. | task0001, task0002 |
| Substitution reader (`_skip_substitution`) | Skip a `$( )` body and report where it ends, or that the read is undecidable | Pre: its call signature and callers are unchanged. Post: its result keeps its current form and meaning, including the undecidable result and how callers handle it; it finishes in time linear in the input length (NFR1); no method it reaches is `_skip_substitution`, `_read_quoted_unit`, `parse` or `_remove_range_quotes` (NFR2); the docstring phrases pinned by `TestSubstitutionSkipDocumentation` that predate this feature remain (FR7). | task0001, task0002 |
| Command-position state (inside the reader) | For each command-list context (a `$(` body, a nested `(` body, a case item body), whether the next word is at command position | Established by task0001: true at list start, after `;` / `&` / `\|` (including `&&` / `\|\|`), after a newline, after a subshell `(`, and after a `then` / `do` / `else` / `elif` / `if` / `while` / `until` / `time` / `!` / `{` that is itself at command position; false after any other word; a closing substitution, quote, `${ }` or `)` of a non-command-position `(` continues the word. `case` opens, and an item-body `esac` closes, only as a standalone word at command position (FR2); `case` / `in` / `esac` are decided on the pair-stripped sequence (FR5). task0002 adds the FR9 closings, FR10 function heads and FR11 loop/coproc heads to the true-set, and decides every reserved word on the pair-stripped sequence (FR1). Post: the state, including everything task0002 adds, is constant size per context (NFR1). | task0001, task0002 |

## Conventions
- Two-copy edits: change one copy, then make the other byte-identical in
  the same commit; never commit a state where the copies differ.
- `CASES` labels carry the scenario ID: TS1–TS19, TS23–TS40 and TS44–TS59
  from SPEC.md, TS61 for the plan-defined rows (VERIFICATION.md), so a
  failing row traces back to its scenario.
- Notation in plans and tests follows SPEC.md: `<NL>` is a newline, and
  `\<NL>` is a backslash directly followed by a newline (a continuation
  pair). The test source must produce exactly those bytes.
- The plugin `version` fields (`plugin.json`, `.claude-plugin/marketplace.json`)
  are not part of this feature's change set (NFR4).

## Cross-task Design Decisions

### D1: One task per planning pass for the reader
Every fix lives in the same reader in the same two files, and the two files
must stay byte-identical. Parallel tasks would edit the same state machine
in both copies and conflict on every merge, and the new `CASES` rows and
linear-time tests can only pass against the changed reader. The first pass
placed the whole change in task0001 (merged). The re-plan after the SPEC
change (FR1 / A2 revised, FR9–FR11 added) places the whole delta in
task0002 for the same reason; it is not split along FR9 / FR10 / FR11,
because all three extend the same command-position state. Affected tasks:
task0001, task0002.

### D2: Scope limits from SPEC.md assumptions
These stay as they are, and any task touching the reader keeps them unless
SPEC.md changes:
- positions after a `time` option, an assignment or a redirection,
  including after a compound closing (A3);
- the main parser's case marks and continuation handling outside
  `_skip_substitution` (A4);
- `#` after any `)` other than a pattern `)`, and the body-internal
  `x\<NL>#c` reading (A5); zsh extendedglob `(x)#` (A8);
- how words inside `[[ … ]]` are read — `[[` is tracked only to recognise
  its `]]` (A9);
- zsh argument-position `}` closing a brace group (A10);
- multi-name zsh function definitions and function-name validity (A11).

Affected tasks: task0001, task0002.

### D3: Command position is decided forward, where the word is read
The backward look at the previous word's characters is not a basis for any
decision (FR1). A closing or head gives command position at the moment it
is read, from constant-size state recorded when its opening was read
(whether a `(` was opened at command position, whether a `[[` was read at
command position, which head word started a head). This keeps the NFR1
linear bound and the NFR2 no-recursion rule. Affected tasks: task0001,
task0002.

### D4: Scenario ID ranges
SPEC.md owns TS1–TS60. Plan-defined verification items in VERIFICATION.md
start at TS61. The first pass's plan-defined integration items, numbered
TS23–TS29 then, are renumbered to TS62–TS68 because SPEC.md now assigns
TS23–TS60 to its own scenarios. Affected tasks: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The new command position after a closing or head changes the verdict of a pre-existing `CASES` row (a word after `)`, `esac`, `fi`, `done` or `}` that was an argument now opens a `case`) | Medium | High | task0002 AC-7 runs every pre-existing row against both copies (TS62); A3 keeps the redirection and assignment limits. |
| The empty `()` check or head recognition re-reads input, making nested heads or long argument runs quadratic | Medium | Medium | TS41–TS43 and TS60 at `DEPTH` scale under `TIMEOUT` (task0002 AC-5, TM-8). |
| The zsh for word list is read as a subshell, so words inside it take effect as keywords | Medium | Medium | Word-list rule in task0002 Design section 4; TS49 and TS54. |
| The two copies drift apart | Low | High | `TestCopies` (TS63). |
| The docstring rewrite drops a pinned phrase | Low | Low | `TestSubstitutionSkipDocumentation` (TS66). |

## Open Questions
- None.
