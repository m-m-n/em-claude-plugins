# Implementation Plan: codex-guard-case-in-substitution

## Overview
The substitution skip of codex-hook-interactive-guard (both byte-identical
copies) reads a `case` statement inside a `$( ... )` that sits inside double
quotes, so a pattern's closing `)` no longer ends the chunk and a launch after
the chunk in the same `-c` string is judged. One task (task0001) carries the
reader change, its `CASES` rows and its performance, call-structure and
documentation tests; the decisions below bind it and any later rework task.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3) - unchanged.
- **Tests**: the standard library unit-test runner; every behaviour test runs
  each hook copy as a child process (existing harness in
  `tests/test_codex_hook_interactive_guard.py`).
- **New dependencies**: none, so no license to record (`project.license: none`).

## Layer Structure
| Layer | Responsibility | Changed by this feature |
|-------|----------------|-------------------------|
| Hook entry and judgment (`main`, `find_deny`, `_scan`, `_judge`) | stdin JSON to verdict; nested `-c` walk; checkpoint rule | No |
| Reader (`_Parser`: word reading, anonymous-function argument ranges, `_remove_range_quotes`) | split the command string into simple commands and words | No |
| Shared quoted-unit reader (`_read_quoted_unit`) | read a backslash pair, a single-quoted unit, a double-quoted unit; the only caller of the substitution skip | No (call structure kept, FR6) |
| Substitution skip (`_skip_substitution`) and its keyword predicate (`_is_case_keyword`) | locate the close of a substitution that opens inside double quotes | Yes |

Allowed call direction: word reading and `_remove_range_quotes` call the
shared quoted-unit reader; it calls the substitution skip; the substitution
skip may call only bounded lookup helpers (keyword and standalone-word
checks). Nothing at or below the substitution skip calls the shared
quoted-unit reader, `parse`, `_remove_range_quotes`, or the substitution skip
again (NFR2).

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Substitution skip (`_skip_substitution`) | Return the index just after a substitution that begins inside double quotes | Pre: the start index is at `$(`, `$((` or a backquote that opens inside double quotes; the signature is unchanged. Post: returns the index just after the close zsh uses, `case` statements inside the chunk read per task0001's reading model; raises `_Undecidable` (never any other exception) when the chunk is not closed or its close cannot be located with certainty, which covers the FR4 forms and the forms in D2 and D3 below; constant work per character; the contents of the chunk are never judged. Its two existing reach paths (word reading, delimiter-range quote removal) are unchanged. | task0001 |
| `CASES` table (`tests/test_codex_hook_interactive_guard.py`) | One table of behaviour rows run against both copies | Each row is (expected verdict, label, command); expected is `deny` or `silent`; labels and commands are unique across the table; existing rows are never removed and their expected values never change | task0001 |

## Conventions
- **Byte-identical copies**: every edit to the hook is made identically in
  `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py` in the same commit
  (FR8, checked by `TestCopies`).
- **Fail-open policy**: a form whose close cannot be located raises
  `_Undecidable`; the output for it is silent. A close is never guessed. A
  form that bash or zsh accepts is read, never made undecidable for
  convenience (D3).
- **Nesting**: every nesting level (a `case` statement in a body, a
  substitution in the subject, a pattern or a body, a parenthesised group in
  the subject or a pattern, a subshell in a body) is an entry on the one
  explicit stack of the substitution skip; no recursion, no call cycle (NFR2).
- **Linear time**: each character is consumed once by the skip's main loop;
  forward checks look at most four characters ahead; a backward look covers
  only the preceding run of blanks and the run of letters before it (NFR1).
- **Test rows**: labels follow the table's existing convention (Japanese
  descriptive labels); new rows are appended after the last existing row.
- **Version files**: `plugin.json` and `.claude-plugin/marketplace.json` are in
  no task's file set (NFR4).

## Cross-task Design Decisions

### D1: The position right after an item terminator is a pattern position
FR1 defines the pattern position as right after `in` and right after an item
terminator; FR3 also lists "right after an item terminator" among the
positions where `case` is recognized in a body. One position cannot be both.
The plan follows FR1 and the case grammar of bash and zsh: after a terminator,
a standalone `esac` closes the statement and every other word, `case`
included, begins a pattern. Inside a body, `case` is recognized at the
positions `_is_case_keyword` recognizes today plus the first word of the body
(right after the pattern's closing `)`), which covers nested `case`
statements (TS7). The orchestrator's Codex review of this plan adopted D1 as
written. **FR3's words "right after an item terminator" are superseded by
D1** for this feature's implementation, review and verification; SPEC.md
itself is not edited. Affects: task0001 and any rework of the reading model.

### D2: An unmatched `)` in an item body is undecidable
A `)` read while the body itself is the innermost context (no subshell or
substitution opened in the body is still open) means the substitution would
end before `esac`. SPEC.md does not name this form; bash and zsh reject it,
and it falls under FR4 (2) (the statement is not closed by `esac`) and the
module docstring's "close cannot be located with certainty". It raises
`_Undecidable`. Affects: task0001.

### D3: Header and pattern forms are read unless neither bash nor zsh accepts them
The subject word and the patterns are read as shell words, so every form a
shell accepts is read, not made undecidable. The forms below were run on real
shells by the orchestrator's Codex review and must be read: an empty leading
alternative in zsh (`|x)` at a pattern position, `(|x)` after the optional
leading parenthesis); parentheses in the subject (`case x(a|b) in`); a
numeric range as the subject (`case <1-2> in`); a process substitution as the
subject (`case <(:) in`, accepted by bash and zsh). The reading model also
reads, by construction, comments between the header words and an `in` that is
directly followed by an operator character.

Reading rules that follow from this:
- Inside a parenthesised group of the subject or of a pattern, every
  character up to the matching `)` belongs to the word (blanks, `|`, `#`,
  `;`, `&`, `<`, `>` and newlines included); quoted units and substitutions
  are still read by the current rules, and a nested `(` nests.
- In the subject, `<(` and `>(` open a command-list context, like `$(`;
  `<` and `>` not followed by `(` are subject characters. In a pattern, `<`
  and `>` are pattern characters.
- A `;`, `&`, `|` or `)` outside the subject's groups ends the subject; what
  follows is then not `in`, so FR4 (1) applies. No separate rule is added.

Undecidable beyond FR4 and D2, only where neither bash nor zsh accepts the
input:
- an unquoted `;` or `&` at a pattern position or right after the optional
  leading `(`: a separator where both grammars require a pattern word;
- an unquoted newline, `;` or `&` in a pattern outside its parenthesised
  groups: both grammars end the pattern word there and then require `|` or
  `)`.

These two follow the case grammars of bash and zsh; the planner did not run
them on real shells (Open Questions). TS21 pins the accepted forms listed
above. Affects: task0001.

### D4: The module docstring stays as it is
FR9's updates go to the docstring of `_skip_substitution` (and of
`_is_case_keyword` when its behaviour or signature changes). The module
docstring's step 3, including "A chunk that is not closed, or whose close
cannot be located with certainty -> no output", is left unchanged, and every
existing `TestGuardDocumentation` marker stays. Affects: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A pattern `)`, a quoted `)` or an argument `esac` misplaces the close, so substitution contents are judged (false deny) | Low | Medium | Reading model of task0001; TS8-TS11 rows (TM-2) |
| A form bash or zsh accepts is made undecidable, widening fail-open | Low | Medium | D3 reads every form except the two neither shell accepts; TS21 rows pin the zsh forms |
| Case reading becomes super-linear or deep input exhausts the stack | Low | High | Constant work per character, explicit stack; TS16, TS19, `TestNoRecursion` (TM-3) |
| An existing `CASES` row changes verdict | Low | High | Case states are entered only at a recognized `case` keyword; backquote, double-quote, arithmetic and `${` contexts untouched; full suite (TS17) |
| The two copies diverge | Low | Medium | `TestCopies` byte comparison (FR8) |
| A documentation marker is lost while editing docstrings | Low | Low | `TestGuardDocumentation` unchanged; new documentation test (TS18) |

## Open Questions
- [x] D1: resolved. The orchestrator's Codex review adopted D1, and FR3's
      "right after an item terminator" is superseded by D1 (recorded above;
      SPEC.md unchanged).
- [ ] D3: the two forms kept undecidable (an unquoted `;` or `&` where a
      pattern word must begin; an unquoted newline, `;` or `&` in a pattern
      outside its groups) follow the bash and zsh case grammars but were not
      run on real shells by the planner. If either shell accepts one, move it
      to the read side in a rework task.
