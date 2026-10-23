# Implementation Plan: codex-guard-delim-brace-quote-per-shell

## Overview
codex-hook-interactive-guard decides how to read the `${ ... }` ranges of a heredoc delimiter in a nested `-c` string from the shell that directly holds the string. One task, task0001, makes the change. It touches the parser, the module-level parse driver and the hand-off between `_judge` and `_scan`, in both byte-identical copies of the guard. It also adds the regression rows and tests.

This document holds the feature-wide reading model: the vocabulary, the classification by holder, the two forms of a delimiter word, the rule that combines the dual reading, and how reads are counted. Every task of this feature, rework tasks included, implements against it. Per-component detail lives in tasks/task0001.md.

## Technology Stack
- **Language**: Python 3, standard library only (NFR6).
- **Tests**: the standard-library unittest runner. The CASES table in `tests/test_codex_hook_interactive_guard.py` runs against both copies.
- **New dependencies**: none. `project.license` is `none` and nothing is added, so there is no license constraint to check.

## Layer Structure
Both copies are one module with four layers. Calls only go downward.

| Layer | Members | Responsibility | May call |
|-------|---------|----------------|----------|
| Hook entry | `main`, `find_deny` | Read the stdin JSON, parse the hook command (quote-removal reading), start the walk | Parse driver, Walk |
| Walk | `_scan`, `_judge`, the shell classifiers | Judge simple commands. Hand each nested literal `-c` string to the parse driver, together with the holder's kind and delimiter reading. Count NESTED_READ_LIMIT. | Parse driver |
| Parse driver | module-level `parse` and its non-recursive helper | Build parsers for the kind and the delimiter reading, apply the unknown-kind re-read, combine the readings | `_Parser` |
| Parser | `_Parser` | Read one string, with switches fixed for the parser's life | Its own methods |

No function calls itself and no set of functions forms a call cycle (TestNoRecursion). Nested strings are walked with the explicit work list.

## Shared Components
None. The feature has one task, and its component contracts are in tasks/task0001.md.

## Conventions
- **Two copies**: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` change in the same change and stay byte-identical (NFR1).
- **Fail-open**: anything the guard cannot read with certainty passes. There are two exceptions. The checkpoint rule judges the commands up to the last checkpoint. The dual reading denies when either reading denies (D3).
- **Error containment**: `_scan` keeps exactly one try around its nested parse call. That try catches `_Undecidable` and the general exception class, and the general handler neither returns nor raises (NFR3).
- **Docstrings are contract text**: the module docstring's decision flow and each changed method's docstring change together with the behaviour. Every phrase an existing documentation test asserts is kept verbatim (NFR4).
- **CASES rows**: each row is `(expected, label, command)`. `expected` is `deny` or `silent`, and commands are unique. No existing row is removed or changes its expected verdict (NFR5).
- **Plugin version**: this feature does not touch `plugin.json` or `marketplace.json`. The repository's Actions workflow raises the version on push (NFR7).

## Cross-task Design Decisions

### D1: The delimiter reading is a second axis beside the kind
The kind (bash / zsh / unknown) keeps deciding the coproc NAME rule, the zsh repeat rule and the unknown-kind re-read (FR1). A separate value, the delimiter reading, decides how a delimiter `${ ... }` range is registered:

| Holder of the string | Kind (unchanged) | Delimiter reading |
|---|---|---|
| bash: the bare name, a digits-and-dots suffix, a path, an option-less wrapper, `--posix` | bash | bash form only |
| zsh (suffixed included) | zsh | quote removal only |
| dash (suffixed included) | unknown | quote removal only |
| sh, ksh (suffixed and path included) | unknown | both: bash form first, then quote removal |
| the hook command itself | unknown | quote removal only |

The holder is matched the way the kind is matched today: the basename of the command word left after assignments and option-less wrappers, compared as the name itself or the name followed only by digits and dots. Only the direct holder decides. The driver's default delimiter reading is quote removal, so `parse(command)` and `parse(command, kind)` behave exactly as they do today (A-6; TestRereadFallback still sees two parsers).

Rationale: FR1 groups shells differently for the two purposes (dash is unknown kind but has quote removal only, while sh is unknown kind with both readings). Keeping the axes apart leaves every existing kind behaviour untouched.

### D2: The two forms of a delimiter word
- **Quote-removal form**: the text registered today, unchanged.
- **Bash form** (FR2): when the delimiter word holds at least one `${` range and no quote unit outside its ranges, each range contributes its original characters, minus the backslash-newline pairs outside single quotes. All other text of the word is the same as in the quote-removal form. Otherwise the bash form is the quote-removal form.
- **Quote unit outside the ranges**: a `'`, `"` or `\` unit that the word reader reads for the delimiter word. This includes a quote unit inside a parenthesised argument range of the word. A backslash-newline pair is not a unit. A `$( ... )` or backquote span written directly in the word is not a unit, and neither are the quotes inside it.
- **Inside a range**: a single-quoted unit keeps its original characters. A backslash pair keeps its two characters, except a backslash-newline, which adds nothing. A double-quoted unit keeps its original characters minus the backslash-newline pairs the shared reader drops. A substitution keeps the text the shared reader returns, in both forms (open question O1). Every other character stays as written.
- Both forms come from the one forward scan that finds the range's close. These stay unchanged: the close search, the undecidable cases (an unquoted `$'` / `$"`, an unclosed quote or substitution, text that ends before the close) and the reading of a parenthesised range (FR2, FR4).
- A parser built for the bash form registers the bash form. A parser built for quote removal registers the quote-removal form. Either parser records that the word "differs" when its two forms are unequal.

### D3: Combining the dual reading (sh / ksh)
1. Reading A is the bash form and reading B is quote removal. Each reading runs today's single-reading procedure for the string's kind. For the unknown kind that means a first read with both switches on, a re-read with both switches off when the first read stops undecidable, and a fall-back to the first read's checkpoint commands when the re-read fails.
2. Reading B is skipped only when every parser built for reading A ended by returning or by raising `_Undecidable`, and none of them recorded a differing delimiter word.
3. What each reading adds: a reading read to its end adds its commands. A reading that stopped undecidable adds its checkpoint commands. A reading that raised any other exception adds nothing, and it does not discard what the other reading added.
4. The result is the concatenation, reading A first. When either reading stopped undecidable, the result is raised as an `_Undecidable` that carries it. Otherwise it is returned. When neither reading added anything (both raised another exception), reading A's exception leaves the driver, exactly as an unexpected error leaves it today.
5. There are no per-delimiter combinations. Each reading applies one rule to the whole string (FR3).

Rationale: FR3 says "independently" and "deny if either". TM-2 adds that no outcome of one reading can suppress the other reading's commands.

### D4: Counting and cost
- `_scan` counts a string once, at its length, before the driver runs. That position is unchanged, so the driver's extra reads cost no budget (FR5).
- A nested string counts each time the walk reaches it in the combined commands. A string that appears in both readings therefore counts twice (FR5).
- A string gets at most two readings, each with at most two reads, and each read is linear (NFR2, TM-3).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rewriting the docstrings breaks an existing marker test | Medium | Medium | Keep every asserted phrase verbatim, and run the documentation tests (TS33). |
| The hook command or the zsh / dash readings shift by accident | Low | High | The default delimiter reading is quote removal. Existing CASES rows plus TS24, TS25, TS28, TS29 and TS31 pin these readings. |
| A wrong "differs" record skips reading B and misses a launch | Low | High | The D3 skip condition, verified by the parser-count tests (TS42). |
| ksh / mksh follow neither rule | Medium | Medium | Accepted (SPEC A-1). |
| An unquoted `$'` in a range under bash is missed | Low | Low | Accepted (SPEC A-4). |
| Walking both readings doubles the walks of nested strings, so NESTED_READ_LIMIT is reached sooner | Medium | Low | Intended by FR5. Reaching the limit is never a reason to deny, and level-0 and first-level strings are still judged. |
| A backslash-newline inside a substitution in a range is kept (O1) | Low | Low | No line can then match the delimiter, so the body stays open and the checkpoint rule applies. The reading before this feature behaves the same. |

## Open Questions
- [ ] O1: Under the bash form, a substitution inside a delimiter range keeps the text the shared reader returns, so a backslash-newline inside it is not removed. SPEC FR2 does not fix this case. Confirm against bash in review.
