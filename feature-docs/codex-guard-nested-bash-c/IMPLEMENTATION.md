# Implementation Plan: codex-guard-nested-bash-c

## Overview
codex-hook-interactive-guard judges the literal `-c` operand of a shell at
every nesting level with the first-level rules, walks nested strings with
an explicit work list, and caps the characters re-read from
second-level-and-deeper strings. task0001 changes the traversal and pins the
behaviour in tests; task0002 rewrites step 7 of the module docstring to
describe it.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1) - unchanged.
- **Tests**: the standard library unittest module, through the existing
  harness in `tests/test_codex_hook_interactive_guard.py`, which runs each
  copy of the hook as a separate process.
- **New dependencies**: none. `project.license` is `none`, and no
  dependency is added, so no license is recorded.

## Layer Structure

| Layer | Elements in the script | Changed by |
|---|---|---|
| Entry / output | `main`, `deny_reason` | - |
| Traversal | `find_deny`, `_scan` | task0001 |
| Judgment | `_judge`, `_command_index`, `_read_options`, `_read_shell_options`, `_family_of` | - |
| Parser | `parse`, `_Parser` | - |
| Module docstring | "Decision flow", step 7 | task0002 |

Allowed dependency direction: entry -> traversal -> judgment -> parser. The
traversal is the only layer that reads a nested string: it hands each
string to the parser and each simple command to the judgment layer. The
judgment and parser layers are reused unchanged at every level; no new
reading rule is added (NFR2).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Nested-string traversal (`find_deny` -> `_scan`) | Decide the first launch to deny across level 0 and every nested shell `-c` string | `find_deny(command)` keeps its signature. Pre: `command` is a string. Post: returns (kind, name) of the first launch to deny in judgment order, or nothing when there is none. Behaviour: rules T1-T7 below. `_scan` keeps its name and remains the function that walks nested strings; its parameters are free | task0001 (implements), task0002 (documents) |
| Re-read limit constant `NESTED_READ_LIMIT` | The one place the limit value lives | Module-level constant in the constants block after the module docstring. Value: 1,000,000. Unit: characters of a string's value as handed to the parser (after the holding level's quote removal). Read only by the traversal | task0001 (defines, tests), task0002 (documents the value) |
| Two-copy identity | Keep `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` one file | Every edit to either copy is applied to the other in the same commit; the two files are byte-identical at every commit (`TestCopies`) | task0001, task0002 |
| Region ownership in the shared files | Keep the two parallel tasks' edits in disjoint regions | Table "Region ownership" below | task0001, task0002 |

### Terms

| Term | Meaning |
|---|---|
| Level 0 | the command the hook receives |
| First-level string | the literal first operand of a shell `-c` in a level-0 command |
| Second-level-and-deeper string | the literal first operand of a shell `-c` in a command inside a first-level-or-deeper string |

### Nested-string traversal rules (T1-T7)

- **T1 Reading at every level**: a command string at any level is split by
  the existing parser, and each of its simple commands is judged by the
  existing per-command judgment exactly as at level 0. Wrappers and options
  are read the same way; the shells (bash sh zsh dash ksh) with `-c`
  anywhere in a bundle (`-lc`, `-cx`) yield their literal first operand as a
  string of the next level; shell `-n` is treated exactly as at level 0.
- **T2 Connection**: the commands of a string inherit the standard input
  connection of the command that holds the string, through every level. At
  every level a command is connected when it inherits a connection, has a
  stdin redirect, sits on the right side of a pipe, or is inside a
  connected group. Commands inside a function body are not judged.
- **T3 Undecidable and dynamic**: a string the parser cannot read
  (unbalanced quote, unterminated heredoc, unclosed group) is skipped and
  passes; the traversal goes on with the command after its holder. A
  dynamic operand yields no string.
- **T4 Order**: within one string, commands are judged in source order.
  When a command holds a readable string, every command of that string, and
  of the strings nested in it by the same rule, is judged before the next
  command after the holder. The first command in this order that is a
  launch to deny ends the traversal and decides (kind, name); no string
  after it is read.
- **T5 Walk**: nesting is followed with an explicit work list of pending
  strings. No function in the script calls itself, directly or through
  another function, so nesting depth costs no call-stack depth.
- **T6 Limit**: one running total per hook command, starting at zero.
  First-level strings are never counted and are always read (subject to
  T3). When a second-level-or-deeper string is about to be read: if the
  limit has already been reached, or the running total plus the string's
  length exceeds `NESTED_READ_LIMIT`, the limit is reached, and that string
  and every later second-level-or-deeper string (in T4 order, across all
  first-level strings) are not read and pass. Otherwise its length is added
  to the running total and it is read; a string that then proves
  undecidable still counts. A string that brings the total exactly to the
  limit is read.
- **T7 The limit is not a verdict**: reaching the limit produces no output
  on its own. Level-0 commands and the commands of first-level strings are
  still judged after it.

### Region ownership

| File | task0001 edits | task0002 edits |
|---|---|---|
| both script copies | the constants block (adds `NESTED_READ_LIMIT`), `_scan`, `find_deny` | the module docstring, step 7 only |
| `tests/test_codex_hook_interactive_guard.py` | `CASES` rows and the comments inside the table; new test methods or classes for judgment order, recursion absence, the limit, and deep or many nesting | `TestGuardDocumentation` (its marker tuples and new methods inside it) |

Neither task edits the other's region. Adding `CASES` rows shifts which
rows `SAMPLE_CASES` picks; that needs no change elsewhere.

## Conventions
- `CASES` rows are (expected, label, command): expected is `deny` or
  `silent`, the label is Japanese and states the behaviour, and every
  command is unique across the table (`test_cases_are_unique`).
- Inputs near or above the limit, and deep nesting, go in dedicated test
  methods, never in `CASES`: `CASES` and its every-twelfth-row sample are
  rerun per copy, per working directory and per environment.
- Every behaviour test runs both copies as separate processes
  (`HookCopiesMixin`); the hook module is never imported.
- Fail-open (NFR2): any path that cannot decide passes. No new path may
  raise out to `main` or write to standard error.
- Docstrings and code comments are English; `CASES` labels are Japanese.
- No task's change set includes either plugin's `.claude-plugin/plugin.json`
  or the root `.claude-plugin/marketplace.json` (NFR5).

## Cross-task Design Decisions

### D1: The behaviour and its description are separate tasks bound by T1-T7
- **Decision**: task0001 implements T1-T7 and the constant; task0002
  rewrites docstring step 7 from T1-T7 and the constant's value alone,
  without reading task0001's code.
- **Rationale**: each side is testable on its own (`CASES` and the
  traversal tests do not depend on the docstring; the docstring markers do
  not depend on the traversal), and T1-T7 is the single description both
  follow.
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The two tasks' edits to the same three files conflict at merge | Low | Medium | Region ownership table; the regions are far apart in each file |
| The two copies diverge | Low | High (`TestCopies` fails) | Two-copy identity contract; both tasks run `TestCopies` |
| Docstring and behaviour disagree | Medium | Low | Both follow T1-T7 and the constant value; manual check in VERIFICATION.md |
| Over-limit inputs slow the suite | Medium | Low | Large inputs stay out of `CASES`; few over-limit runs (task0001 Test Notes) |
| A launch placed past the limit passes | Low | Medium | Accepted by FR3 and NFR2; recorded as residual risk in THREAT-MODEL.md |

## Open Questions
- None.
