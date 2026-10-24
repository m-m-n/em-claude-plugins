# Implementation Plan: codex-guard-funcname-anon-always

## Overview
Fix two fail-open regressions of the substitution reading
(`_Parser._skip_substitution`) of `codex-hook-interactive-guard.py`: the words
after the second `function` name, and the words after the body of a zsh
anonymous function. task0001 changes the reading and its behavior tests;
task0002 rewrites the `_skip_substitution` docstring and its documentation
tests to state the same reading.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3)
- **Tests**: standard-library `unittest`, `tests/test_codex_hook_interactive_guard.py`, which runs each copy of the hook as a separate process

## Layer Structure
One module, shipped as two byte-identical copies (FR6):
- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`

Only the reading inside `_Parser._skip_substitution` changes behavior. The
top-level reading (outside `_skip_substitution`) and the body `}` of named
function definitions (`name()`, `function name`) keep their reading (A5).

## Shared Components

The shared component is the substitution reading model below. task0001
implements it; task0002 states it in prose in the `_skip_substitution`
docstring. Neither task reads the other's diff; both work against this
model.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Further-name state | Reads the words after the second `function` name | Rule M1 | task0001 (implements), task0002 (documents) |
| Anonymous-head state | Marks that the next `{` is an anonymous function's body | Rule M2 | task0001, task0002 |
| Open `{` group records | Tells, for each command list, which `{` groups are open and whether each is an anonymous body | Rule M3 | task0001, task0002 |
| Anonymous-body close | What the `}` that closes an anonymous body does | Rule M4 | task0001, task0002 |
| Anonymous-arguments state | Reads the words after an anonymous body | Rule M5 | task0001, task0002 |
| Group-closing `}` and `always` | Which `}` lets a following `always` be a reserved word | Rule M6 | task0001, task0002 |
| Head-state set | The values of a list's head state (rule 7) | Rule M7 | task0001 (constants and module comment), task0002 (docstring) |
| Arithmetic re-read restore | What the rule 9 re-read returns to its value at the `((` | Rule M8 | task0001, task0002 |
| Linear reading | Time and recursion bounds | Rule M9 | task0001, task0002 |

### Substitution reading model (contract)

"Standalone" below means: decided on the characters with the continuation
pairs left out, unquoted, unescaped, and a word of its own (the existing
keyword decision). Every rule holds in every command list of the chunk
(the body of a `$(`, a subshell, a case item body).

**M1 Further-name state (FR1, FR2).**
- In the function-name state (right after the first name), a word for which
  the command-word decision at a command position gives no kind is the
  second name, as today. After it, the list is in the further-name state,
  not in the function-name state.
- In the further-name state, at the start of a word: a standalone `{` or a
  standalone `}` is read as it is at a command position anywhere else. Every
  other word is one more name: reserved words, `!`, the head words
  (`function` `for` `select` `coproc` `repeat`), `case`, `esac`, `[[`,
  `always`, quoted words and words holding a substitution. The further-name
  state and the command position are kept.
- An empty `()` ends the head and the next word is at a command position, as
  after the first name. A separator (`;` `&` `|` newline) or the close of the
  list ends the state. A non-empty `(`, `<`, `>` and a comment `#` keep their
  current reading.
- The reading right after the first name does not change (FR2): there only a
  word with no kind is a name, and a word with a kind is read as it is today.

**M2 Anonymous-function heads (FR3, A3).** Three forms:
- (a) A standalone `{` in the name position right after `function` (current
  reading): it opens an anonymous body at once.
- (b) An empty `()` right after `function`, with no name: the head ends there
  (current reading) and the list enters the anonymous-head state.
- (c) An empty `()` read at a command position while the list has no head
  state (no word of a simple command read yet): the list enters the
  anonymous-head state.

"Empty `()`" is the existing empty-parentheses decision (only blanks and
continuation pairs between the parentheses). In the anonymous-head state,
blanks, continuation pairs and newlines keep the state; the next standalone
`{` is read at a command position and opens an anonymous body. Anything else
ends the state, and what follows is read as it is today after a function
head.

**M3 Open `{` group records.**
- Every `{` that opens a group in a command list adds one record for that
  list, innermost last: a standalone `{` read at a command position (the body
  `{` of a named function, the `{` after `always`, after `coproc`, after a
  reserved word included) and the name-position `{` of form (a). The record is
  marked "anonymous body" for an M2 body and "ordinary" otherwise.
- A `}` that closes a group (M4, M5, M6) removes the innermost record of its
  own list. A `}` never closes a group of another list. When a list closes,
  its remaining records are dropped with it.
- In a brace-form case item body, the records of the body list and the
  rule 2 depth rise and fall at the same `{` and `}`.
- The records are kept outside the constant-size state of each list, on one
  explicit list that runs beside the reader's stack. Adding or removing a
  record is constant work.

**M4 Closing an anonymous body (FR3).** A `}` that removes an
anonymous-body record does not set the group-closed state, and the next word
is not at a command position: the list enters the anonymous-arguments state.
This holds for a standalone `}` at a command position of any list, for a `}`
at an argument position of a brace-form item body list itself (rule 2; it
still lowers the depth there), and for a `}` in anonymous arguments (M5).

**M5 Anonymous-arguments state (FR3, FR4, A2, A4).**
- Every word is an argument and none is at a command position: `always`,
  `{`, `case`, `esac`, reserved words, `!`, head words and `[[` open nothing
  and close nothing.
- One exception (FR4): a standalone `}` removes the innermost record of its
  list.
  - Ordinary group: the `}` is a group-closing `}` (M6); the
    anonymous-arguments state ends and the list is in the group-closed state.
  - Anonymous body: the list stays in the anonymous-arguments state (the
    arguments of the enclosing anonymous function).
  - No record in the list (A2): current reading. In a list that is not a
    brace-form item body the `}` is an ordinary argument; in a brace-form
    item body list at depth 0 it closes the statement as today.
- A quoted `"}"`, an escaped `\}`, and a `}` that is part of a word (`a}`,
  `}a`) stay arguments.
- A `(` is a word parenthesis (rule 10), and redirections and heredoc
  operators (rule 8) keep their reading (A4). The state is kept across them,
  across quoted words, words holding a substitution or `${ }`, and every
  closing inside a word.
- The state ends at `;`, `&`, `|` (and every operator or item terminator that
  starts with one of them), a newline, the close of the list, or the
  ordinary-group case above.

**M6 Group-closing `}` and `always` (FR5).** A group-closing `}` is a `}`
that removes an ordinary record (at a command position, at an argument
position of a brace-form item body list itself, or in anonymous arguments),
or a standalone `}` at a command position of a list that is not a brace-form
item body and has no record (current reading). The `}` that closes a
brace-form statement and the `}` that closes an anonymous body are not
group-closing. After a group-closing `}`, a standalone `always` that follows
after only spaces, tabs and continuation pairs is a reserved word and the
next word is at a command position (unchanged).

**M7 Head-state set (rule 7).** The per-list head state keeps its existing
values and gains three: further-name (M1), anonymous-head (M2) and
anonymous-arguments (M5). Their lifetimes are the ones stated in M1, M2 and
M5; the lifetimes of the existing values do not change.

**M8 Arithmetic re-read (rule 9, NFR2).** When a `((` is read again as two
subshells, the head state of the list that holds the `((` (the three new
values included) returns to its value at the `((`, and so do the open `{`
group records: the records of lists opened after the `((` go with their stack
entries, and the records of lists open at the `((` lie under the arithmetic
command, where nothing changes them.

**M9 Linear reading (NFR1).** The reading stays one forward pass on the
explicit stack, with constant work per character apart from the existing
bounded looks. Nothing recurses.

## Conventions
- Both copies change together and stay byte-identical (FR6).
- `CASES` rows are `(expected verdict, label, command)` with the verdict
  `deny` or `silent`; labels are Japanese, as in the existing rows, and every
  command is unique in the table.
- No file under `.claude-plugin/` is part of any task's change set (NFR4).
- Tests use the standard library only (NFR3).

## Cross-task Design Decisions

### D1: Split by edit region
task0001 owns the code of both copies and every comment or docstring outside
the `_skip_substitution` docstring: the module comments before the constants
(the head-state comment included), inline comments, and the docstring of any
other method that the new reading makes inaccurate (for example the sentence
of `_read_command_word` that names the one argument-position word that closes
anything). In the test file it owns the `CASES` table and the test methods
outside `TestSubstitutionSkipDocumentation`.

task0002 owns only the `_skip_substitution` docstring in both copies and the
`TestSubstitutionSkipDocumentation` class.

task0001 places the declarations of any new reading state after the existing
state declarations of `_skip_substitution` (after the comment-end position),
not right under the docstring, so the two tasks' changes to the same files
stay in separate regions. Affected: task0001, task0002.

### D2: Scenario IDs
VERIFICATION.md uses the `TSn` form (no hyphen), because SPEC.md and the
`tests` lists of workflow.yaml already use `TS1` to `TS12`. Affected: all.

### D3: "Verdict unchanged" rows
A row that pins an unchanged verdict (TS3, TS12) records the verdict the
guard gives at the base revision for that command. Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Form (c) of M2 (an empty `()` at a command position with no head) changes the verdict of an existing row | Medium | Medium | task0001 AC-4 keeps every existing row and class; a conflict is reported as a plan deviation |
| The docstring (task0002) and the code (task0001) describe different readings | Medium | Medium | Both follow M1 to M9; VERIFICATION.md has a manual cross-check; a mismatch becomes a rework task |
| The two tasks conflict when merged | Low | Low | D1 region ownership |
| The new state tracking breaks linear time or adds recursion | Low | High | M9; TS11 and TestNoRecursion |
| One copy keeps the old reading | Low | High | TestCopies |

## Open Questions
- [ ] A3 names blanks, continuation pairs and newlines between an anonymous
  head's empty `()` and its `{`. M2 ends the anonymous-head state at anything
  else, a comment included.
