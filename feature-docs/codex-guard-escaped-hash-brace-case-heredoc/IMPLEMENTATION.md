# Implementation Plan: codex-guard-escaped-hash-brace-case-heredoc

## Overview

Two independent corrections to the substitution reader `_Parser._skip_substitution` of `codex-hook-interactive-guard.py` (the em-workflow and em-review copies, kept byte-identical): the `#` comment-start decision (FR1) and the reading of zsh's brace-form `case x { ... }` (FR2 to FR5), each with its docstring, comments and tests. Heredocs keep rule 8 (FR6).

## Technology Stack

- **Language**: Python 3, standard library only (unchanged)
- **Tests**: `unittest`, the existing `tests/test_codex_hook_interactive_guard.py` (CASES table run against both copies, docstring marker tests, scale tests)
- **New dependencies**: none (no license to record; `project.license` is `none`)

## Layer Structure

| Layer | Responsibility | Depends on |
|-------|----------------|------------|
| Hook script (two byte-identical copies) | Reads the PreToolUse(Bash) command; `_skip_substitution` locates the close of a substitution without judging its contents | nothing new |
| Test module | Drives each copy as a subprocess with the CASES rows; reads the docstrings for marker tests; runs scale tests | the two hook scripts |

No new layer, module or file.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_Parser._skip_substitution` (both copies) | Return the index right after the close of the substitution that begins at `start`, or raise `_Undecidable` | Pre: `start` is at `$(`, `$((` or a backtick. Post: the contents are never judged (NFR3); the close is returned only when it is certain, otherwise `_Undecidable`; one forward pass with total work within a constant times the string length (NFR1); nothing it reaches calls the skip again, the shared quoted-unit reader, `parse` or `_remove_range_quotes` (existing structural tests); the rule-9 re-read restores every value the reader keeps to its value at the `((` | task0001, task0002 |
| `#` comment-start decision (inside the skip) | Decide whether a `#` at a site where a comment can start begins a comment | Defined by task0001 (FR1). It is computed from the characters directly in front of the `#` (a bounded look) and, since task0003, from the one comment-end position of D4: the newline that ended the last comment is an unescaped newline in the look. task0002 adds no site where a `#` can start a comment: every `#` inside a brace-form statement goes through the existing sites (waiting phases, pattern, group, item body), so it gets the decision through them | task0001 (defines), task0002 (relies on it), task0003 (adds the comment-end position, D4) |
| Per-entry state of the skip (phase characters, per-entry saved state, the `((` record) | Hold what each stack entry and each command-position `((` needs | Neither task changes the meaning of the phase characters or the shape of the per-entry saved state. task0002 keeps its per-case-statement values (form and `{ }` depth) beside them and extends the `((` record and its restore. task0001 adds no state. task0003 adds the comment-end position (D4) to the `((` record and its restore, not to the per-entry saved state | task0001, task0002, task0003 |
| CASES table (`tests/test_codex_hook_interactive_guard.py`) | One row per input: (expected verdict, label, command) | Verdict is `deny` or `silent`; labels and commands are unique across the whole table (`test_cases_are_unique`); every row runs against both copies; pre-existing rows keep their verdicts except the one brace-form row FR8 names | task0001, task0002 |
| `TestSubstitutionSkipDocumentation` markers | Pin sentences of the `_skip_substitution` docstring | Every marker is a literal substring of the docstring of both copies; a stale sentence listed in a test stays absent | task0001, task0002 |
| `TestCaseStatementsInASubstitution` scale helper | Assert that a long input is denied in time on both copies | Uses the class's DEPTH and TIMEOUT (those of the deep-input class); the answer must be one deny object | task0001, task0002 |

## Conventions

- **Byte identity (FR9)**: every commit that edits one copy edits the other identically; the two files compare equal byte for byte at the end of every commit.
- **Test command**: `python3 -m unittest tests.test_codex_hook_interactive_guard` (`.claude/rules/hook-tests.md`); the full suite in VERIFICATION.md is the integrated run.
- **CASES labels**: Japanese, in the table's existing style. Rows of the `#` decision start with `置換の # の判定`, rows of the brace form start with `波括弧形式の case`, each followed by the VERIFICATION.md scenario ID when the row is one (`TS-n`). Commands are written as Python string literals, as in the existing rows (`\n` is a newline, `\\` is one backslash).
- **Undecidable reasons**: existing reason strings stay; a new undecidable form may use a new short reason string (no test asserts the reason text).
- **Docstring and comments**: English, in the docstring's existing vocabulary (command list, pattern position, item body, continuation pair, standalone word, undecidable). A task edits only the sentences and paragraphs it owns (D3); untouched lines are not re-wrapped.
- **Plugin versions**: this repository is exempt (the version is bumped by the repository's Actions workflow on push). No task lists `plugin.json` or `.claude-plugin/marketplace.json` among its files (NFR4).

## Cross-task Design Decisions

### D1: Split by reading, both inside `_skip_substitution`

The `#` decision (task0001) and the brace-form case reading (task0002) are separate readings with separate tests: no SPEC scenario needs both. Both tasks modify the same three files, so the edit regions are fixed in D2 and the docstring ownership in D3. As planned for task0001, the `#` decision carried no state, which kept the re-read and the saved state to task0002 alone. task0003 adds one value to the `((` record (D4).

Affected tasks: task0001, task0002.

### D2: Disjoint edit regions

Hook script, `_skip_substitution` and its neighbours (both copies identically; line numbers are those of SPEC.md A8 and shift as code is added):

| Region | task0001 | task0002 |
|--------|----------|----------|
| State initialisation before the main loop | does not touch | New values directly after the line that initialises the heredoc marks, the open-case count, the open `((` list and the re-read set |
| Word-list state update at the top of the loop, and its comment | owns | does not touch |
| Word-start condition of the lists p and 8: the `#` clause (near 2701) | owns | does not touch |
| Handling of the word kinds returned by the command-word decision (case, esac, reserved, ...) | does not touch | owns |
| Waiting phases 1, 3, 4, 5, 7: the `#` clause (near 2771) | owns | does not touch |
| Waiting phases: the phase-3 and phase-4 branches, and the comment that opens the waiting-phase block | does not touch | owns |
| Pattern and group: the `#` clause (near 2903) | owns | does not touch |
| Recording of a command-position `((` and the re-read restore (rule 9) | does not touch | owns |
| Word-list branch (near 2998) and its comment | owns | does not touch |
| General `#` comment branch (near 3004) and its comment | owns | does not touch |
| Item-terminator branch | does not touch | owns |
| `_read_command_word` | does not touch | may change |
| New helper methods, if any | directly after `_keyword_end` | directly after `_empty_parens_end` |

Test file:

| Region | task0001 | task0002 |
|--------|----------|----------|
| CASES | New block of rows directly before the comment that opens the `codex-guard-delim-brace-quote-per-shell` rows | The pre-existing row "zsh の case x { ... } の形は判定不能で、後ろの起動を拒否しない" changed in place; new block of rows directly after it |
| `TestCaseStatementsInASubstitution` | New scale tests at the end of the class, after the commented-lines-in-a-for-word-list test | New scale tests directly after the nested-case-statements test |
| `TestSubstitutionSkipDocumentation` | Edits `WORD_LIST_PROCESS_SUBSTITUTION_MARKERS`; a new marker tuple and test directly after the process-substitution-in-a-word-list test | Edits `UNDECIDABLE_MARKERS`; a new marker tuple and test directly after the test that names each form that stays undecidable |

A conflict that arises anyway is resolved identically in both copies, and byte identity is checked again.

Affected tasks: task0001, task0002.

### D3: Docstring ownership in `_skip_substitution`

- task0001: a new paragraph on the comment-start decision, placed between the rule 3 paragraph and the rule 4 paragraph; in the "Contexts on the stack" paragraph, the word-list sentences on where a `#` starts a comment and on the start of a word (the sentence "The start of a word is a state kept while reading and never looked up backward" included).
- task0002: the rule 2 paragraph, the rule 5, rule 8 and rule 9 paragraphs, the "Raises _Undecidable" paragraph, and the phase list in the "Contexts on the stack" paragraph.
- Markers pinned by tests in sentences a task does not own stay unchanged. The rule 1 sentence "The characters of the previous word are never looked at backward" and the heredoc sentence "a heredoc anywhere in the chunk (item bodies included) once a case statement is open" stay.

Affected tasks: task0001, task0002.

### D4: The comment-end position (review round 1 rework)

A backslash inside a comment is comment text, so the newline that ends a comment is never the second character of a continuation pair. The look of the comment-start decision cannot tell this from the characters alone, so the reader keeps one value:

- **Value**: the absolute index of the newline that ended the last comment the reader read; "none" before the first comment.
- **Written by**: every branch that reads a comment, in the same step, with the index of the newline that ends it. A comment that runs to the end of the input leaves the value unchanged.
- **Read by**: the comment-start decision only. In its look, a newline at that index is an unescaped newline whatever backslashes are in front of it.
- **Re-read**: the rule-9 re-read restores the value to its value at the `((`, beside task0002's values in the `((` record. The per-entry saved state does not hold it.
- **Work**: one assignment per comment and one comparison per newline the look crosses (NFR1).
- **Documentation**: the docstring sentences saying the decision keeps no state are replaced (D3's task0001 paragraph and the helper's own description).

task0003 edits the regions of D2 owned by task0001 (every `#` clause and comment branch, the word-list branch, the comment-start helper), plus the state initialisation before the main loop and the recording and restore of a command-position `((`, and the matching test-file regions. No other task is open, so these regions conflict with none.

Affected tasks: task0001 (its decision is extended), task0002 (its `((` record and restore gain one value), task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merge conflicts in `_skip_substitution` or the CASES table between the two tasks | Medium | Low | D2 and D3 keep the regions disjoint; conflicts are resolved identically in both copies and checked byte for byte |
| The two copies drift | Low | High | Byte comparison in each task's Acceptance Criteria and in VERIFICATION.md (TS-27) |
| The `#` correction overshoots: a real comment after a blank followed by a continuation pair, or after an escaped backslash, is read as a word character | Medium | Medium | TS-6 and the backslash-parity rows of task0001 |
| The newline that ends a backslash-ended comment is read as a continuation pair, so a `#` on the next line is a word character | High (found in review round 1) | High | D4 and task0003; TS-30 to TS-36 |
| A3 (closing a brace-form statement at a depth-0 body `}`) does not match zsh | Medium | Low | Per A3, a wrong deny is limited to strings zsh does not accept; the manual check in VERIFICATION.md records zsh's answer |
| A pre-existing CASES row changes verdict (NFR2) | Low | High | Each task runs the whole module on both copies; only the one brace-form row changes |

## Open Questions

- [ ] SPEC.md A3 is still not measured (VERIFICATION.md, manual check).
