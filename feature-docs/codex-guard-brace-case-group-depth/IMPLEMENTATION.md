# Implementation Plan: codex-guard-brace-case-group-depth

## Overview
Make the substitution reader of `codex-hook-interactive-guard.py` count the
`{ }` groups of a zsh brace-form case item body the way zsh does. The feature
has one implementation task (task0001). This document holds only the rules
that bind every task of the feature, including any rework task that review or
verify adds later.

## Technology Stack
- **Language**: Python 3, standard library only (the guard script and its tests)
- **Test framework**: `unittest` from the standard library (NFR4)
- **New dependencies**: none. No license to record.

## Layer Structure
1. Hook entry: reads the PreToolUse JSON from standard input and hands the
   command text to the parser. Unchanged.
2. Top-level command reading (`_Parser` outside substitutions). Unchanged
   (NFR5). This includes the existing reading of a top-level `{ : }`.
3. Substitution reader: `_Parser._skip_substitution` and the helpers it calls
   (`_read_command_word`, `_keyword_end`, `_hash_starts_comment`,
   `_empty_parens_end`), plus the module-level tables and the head-state
   constants that only the reader uses. **The feature changes only this
   layer.**
4. Verdict output (deny JSON or no output). Unchanged.

Dependencies point downward only. A helper of layer 3 never calls back into
the skip or into the word / quoted-unit readers. The existing structural
tests (`TestNoRecursion`, `TestSubstitutionSkipCallStructure`,
`TestSharedQuotedUnitReader`) enforce this.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| The two guard copies | One guard, shipped in two plugins | Post: after every commit of any task, `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` are byte-identical (NFR2). | task0001 and any later task of this feature |
| `CASES` table in `tests/test_codex_hook_interactive_guard.py` | Verdict table run against both copies | Each row is (expected verdict, label, command), with `deny` or `silent` as the verdict. Commands are unique across the table. No existing row is removed. | task0001 and any later task of this feature |

## Conventions
- **Edit once, copy once**: make every change in the em-workflow copy. Copy
  it byte-for-byte to the em-review copy in the same commit.
- **Change scope (NFR5)**: guard edits stay inside layer 3: its code, its
  docstrings and comments, and the comment of the head-state constants. A
  needed edit outside layer 3 is a plan deviation to report.
- **Undecidable means no output**: when the reader cannot place a close with
  certainty, it raises the existing undecidable signal. It never guesses a
  close.
- **Test rows**: reproduction and boundary inputs go into `CASES`. Inputs
  thousands of characters long go into the time-bounded deep-input test
  class, run against both copies. Docstring wording checks go into
  `TestSubstitutionSkipDocumentation`.
- **Row labels**: the label of a row added by this feature names this
  feature's SPEC scenario ID (TS-n) behind a prefix that tells it apart from
  the older `波括弧形式の case TS-n` labels. Earlier features reuse the same
  TS numbers.

## Cross-task Design Decisions

### D1: One task for the whole fix
FR1 to FR5 all change the same word-start branch of `_skip_substitution` and
the same docstring. FR2 depends on the close that FR1 reads (TS-6 needs
both). Split tasks would edit the same lines of the same two files and the
same marker tables. Affected: task0001.

### D2: The added reading state lives with the list state
Every new piece of state is a constant size per command list and is held
together with the state the list already carries. Examples: "a `}` that
closed a group was just read", "the function-name state goes on after an
extra name". The nested-context push and pop, and the arithmetic re-read
record (rule 9), already save and restore that state, so they carry the new
state without a second mechanism. No new state looks at characters behind
the current one (NFR1). Affected: task0001 and any rework of the reader.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A new reading applies wider than zsh and hides a launch (new bypass) | Medium | High | Conditions limited to FR1-FR4 / A-2 to A-7; each boundary has a row whose verdict differs between the intended and the rejected reading (THREAT-MODEL.md TM-2) |
| An existing `CASES` row changes verdict | Medium | Medium | Run the full table against both copies; a changed verdict other than the planned relabel of the old TS-16 row is reported as a deviation, not rewritten |
| Docstring rewording breaks marker tests | High | Low | Update `BRACE_FORM_MARKERS` / `RULE_MARKERS` in the same commit as the docstring |
| The two copies drift | Low | Medium | Edit-once-copy-once convention; the byte-identity test |
| Work grows faster than the input | Low | High | D2; TS-16 / TS-17 under the deep-input timeout (THREAT-MODEL.md TM-3) |

## Open Questions
- [ ] NFR2, NFR3, NFR4 and NFR5 have no SPEC TS-n scenario. VERIFICATION.md
      checks them through Success Criteria AC-7 / AC-8 and the change-set
      checks instead.
