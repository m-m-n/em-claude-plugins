# Implementation Plan: destructive-guard-heredoc-bypass-fixes

## Overview
Close three lexer bypass paths in `em-workflow/hooks/destructive-guard.py`
(findings b0734a006de6f4d7, a7c0d90ac3e44e5b, f34ee27bc8c323b1) without
removing or weakening any existing deny / ask case. Three tasks change three
separate judgments of the lexer, and each task appends its own reproduction
inputs to the case table.

## Technology Stack
- **Language**: Python 3, standard library only (NFR4).
- **Test runners**: `em-workflow/hooks/tests/run-destructive-guard.py` (case
  table) and unittest discovery under `tests/` (lexer stage-agreement tests
  and linearity tests).
- **New dependencies**: none. `project.license` is `none`, so no license
  constraint applies and no dependency license is recorded.

## Layer Structure
| Layer | Responsibility | Members this feature touches |
|---|---|---|
| Lexer | Reads the command string word by word: assignment words, builtin names, array and subscript extents, pending here-document bodies, extglob parse units | `word_transition()`, `close_subscript()`, `_count_extglob_units()` and the eval / -c expansion points that feed it |
| Decision | Turns the lexer's reading into allow / ask / deny, including the downgrade of ask to deny under unattended execution | `decide()` — not modified |
| Tests | Case table (expected verdict per input) and unit tests comparing lexer stages and checking linearity | case table — append-only; unit-test files — not modified |

Dependency direction: Decision reads Lexer results; tests drive both through
the hook's existing entry point. No task adds a dependency from the Lexer to
the Decision layer.

Notation used in all plan documents of this feature: `{BS-NL}` is a backslash
immediately followed by a newline; `{NL}` is a newline.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Command-name classification (inside `word_transition()`) | Decides which group the command word of a simple command belongs to: the declaration group (declare, typeset, local, export, readonly), the re-parsing group (eval, let, alias), or neither | Pre: applied to the logical word (next row). Post: group membership is exactly as listed here — no task adds or removes a member; the two groups are distinguishable to every consumer; a command word split by in-word `{BS-NL}` is classified the same as the unsplit word; every consumer reads this one classification and none re-reads the raw command word to decide the group | task0001 (supplies the logical word as its input), task0002 (makes the two groups distinguishable and branches on them) |
| Logical word and assignment-word judgment (inside `word_transition()`) | For the word being scanned: its leading plain text with every `{BS-NL}` that bash removes as a line continuation skipped, and the judgment whether the word is an assignment word of the form `NAME=`, `NAME+=` or `NAME[` | Pre: accumulated during the existing single scan of the word. Post: the judgment reads the logical word; ARR_END (array start) and SUB_AT (subscript start) are offsets in the original input, never in the logical word; for a word without an in-word `{BS-NL}`, the judgment, ARR_END and SUB_AT are identical to the current behavior | task0001 (produces it), task0002 (consumes the `NAME[` judgment and SUB_AT in builtin arguments) |
| Case table (`em-workflow/hooks/tests/destructive-guard-cases.json`) | Verdict expectations, one `[expected verdict, label, command]` triple per entry | Append-only: no existing entry is removed, reordered, or has its verdict, label or command changed; each task appends its entries as one contiguous block; every label is unique in the table | task0001, task0002, task0003 |
| Lexer work bound (`LEX_WORK_FACTOR`) | Keeps the lexer's total work linear in input length | Work a task adds is done inside the existing scan and counted against the existing bound; no task adds a second pass over the input or an uncounted loop | task0001, task0002, task0003 |

## Conventions
- **Case labels**: a new entry's label begins with the finding ID it
  reproduces or whose fix it exercises (b0734a006de6f4d7, a7c0d90ac3e44e5b or
  f34ee27bc8c323b1), followed by a short description of the form.
- **bash measurement**: an entry whose expected verdict rests on "bash
  executes this line" is added only after confirming it on bash 5.3.9. The
  confirmation runs the same input with the destructive line replaced by a
  harmless marker command, in a scratch directory, and observes whether the
  marker runs. The destructive line itself is never executed.
- **Offsets**: every position the lexer records (ARR_END, SUB_AT, an extglob
  unit's position) is in original-input coordinates.
- **Error handling**: no new error path. The hook's existing behavior when the
  work bound is reached is unchanged.
- **Files no task modifies**: `tests/test_destructive_guard_lexer_agreement.py`
  (its `SUBSCRIPT_ARRAY_FORMS` test must pass unchanged),
  `em-workflow/hooks/tests/run-destructive-guard.py`, the `decide()` function,
  `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  (NFR5).

## Cross-task Design Decisions

### D1: Split by finding, not by file
All three tasks modify `destructive-guard.py`; task0001 and task0002 both
modify `word_transition()`. The split follows the findings because each has
its own reproduction inputs and acceptance tests. The two `word_transition()`
contracts in Shared Components are the seam between task0001 (what the word
is) and task0002 (what an argument `NAME[` does to pending here-document
bodies). Merge conflicts in `word_transition()` and at the end of the case
table are expected and resolved by the parent-side adoption protocol.
Affected: task0001, task0002, task0003.

### D2: Each task adds the reproduction inputs it fixes (FR5)
FR5 is implemented by all three tasks: each appends its own entries first
(they fail before the fix) and then changes the hook until they pass.
Affected: task0001, task0002, task0003.

### D3: The duplicated scanners stay duplicated
Unifying the subscript / extglob scanners with the main loop
(765c3a53859569c2) is out of scope. A task whose change alters how the main
loop reads quotes, expansions or process substitutions inside a subscript or
extglob region makes the duplicated scanner read them the same way;
`TestStageAgreement` and `TestStageAgreementUnderExtglobOn`, which pick up
every new case-table entry automatically, are the check.
Affected: task0001, task0002, task0003.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| task0001's and task0002's edits to `word_transition()` merge into a reading neither task tested (a command name split by `{BS-NL}` in front of a builtin argument `NAME[`) | Medium | High | Shared Components contracts; task0001 adds split-name variants of T2 E-1 and T2 E-9 whose deny holds under both tasks; VERIFICATION.md TS12 checks the composed behavior on the integrated branch |
| A change in the main loop diverges from the duplicated subscript / extglob scanner (the cause of regression d96cc6e9cb96644b) | Medium | High | D3; stage-agreement tests over every new entry |
| A fix turns an existing allow case into ask or deny, halting unattended runs | Medium | Medium | Every existing entry, allow included, is part of each task's acceptance (NFR1) |
| bash 5.3.9 is not available where a task is implemented, so "bash executes this line" cannot be measured as specified | Medium | Medium | The implementer states the bash version actually used in its completion report; a form whose execution was not confirmed is not added as deny |
| Measuring with the real destructive line damages the working tree | Low | High | bash measurement convention: harmless marker only, in a scratch directory |

## Open Questions
- None.
