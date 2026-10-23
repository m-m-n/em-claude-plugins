# Feature: codex-guard-for-wordlist-glob-qualifier

## Overview

`codex-hook-interactive-guard.py` (both the em-workflow and em-review copies)
reads a `#` right after a nested `(` (a glob qualifier) inside a zsh
`for name (words)` word list as the start of a comment. With no newline
after it, the reading becomes undecidable (`_Undecidable`) and the
`python3 -i` after the substitution is not denied (fail-open). This feature
makes that `#` a word character in nested entries of the word list.

Requirements document: `feature-docs/codex-guard-for-wordlist-glob-qualifier/REQUIREMENTS.md`

## Objectives

- Eliminate the state where codex-hook-interactive-guard misreads the `#` of
  the glob qualifier `*(#qN)` in a zsh `for name (words)` word list as a
  comment and fails to deny the `python3 -i` after the substitution
  (fail-open).

## User Stories

### US1: Deny `python3 -i` after a word list containing a glob qualifier
As an em-workflow / em-review user running codex-hook-interactive-guard as a
PreToolUse(Bash) hook, I want a command whose `$( )` contains a zsh for word
list with `*(#qN)` followed by `python3 -i` to be denied.

**Acceptance Criteria:**
- [ ] AC1: Passing `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` as tool_input.command makes both copies return deny
- [ ] AC2: Passing `echo "$(for x (*(#qN)) { :; })"; python3 -i` makes both copies return deny
- [ ] AC3: The AC1 and AC2 inputs each appear once as a deny row in CASES, and test_cases_run_against_both_copies and test_cases_are_unique pass
- [ ] AC4: The existing substitution-reading rows TS1, TS5, TS6, TS7, TS8, TS28 and test_ts26_commented_lines_in_a_for_word_list_are_read_in_time keep passing unchanged
- [ ] AC5: TestCopies.test_the_two_copies_are_byte_identical passes
- [ ] AC6: `python3 -m unittest tests.test_codex_hook_interactive_guard` passes in full

## Technical Requirements

### Functional Requirements
- **FR1:** Read `#` right after a nested `(` in a word list as a word character. In `_skip_substitution`'s context w, in the entry of a nested `(` opened inside the word list (an entry whose `stack[-2]` is `w`), a `#` whose preceding character is `(` does not start a comment and is read as a word character. `echo "$(for x (*(#qN)) { :; })"; python3 -i` and `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` are denied.
- **FR2:** Comments start only in the outermost word-list entry. A `#` in context w starts a comment only while reading the outermost word-list entry (an entry whose `stack[-2]` is not `w`). The reading in the outermost entry is unchanged: a `#` preceded by space, tab, newline, `;`, `&`, `|`, or `(` starts a comment that runs to the next newline (including TS8's `for x (# c<newline>a)`).
- **FR3:** Fix both copies identically. `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` are fixed in the same change and kept byte-identical.
- **FR4:** Regression test. Add the two reproduction inputs (the zsh -c form and the top-level form) as deny rows to `CASES` in `tests/test_codex_hook_interactive_guard.py`, run against both copies.

### Non-Functional Requirements
- **NFR1 - Performance:** Keep reading linear. The added check is constant time per character (a `stack[-2]` lookup), and the existing TS26 (DEPTH lines of commented word-list lines) keeps being decided within its time limit.

## Implementation Approach

### Architecture

Change is confined to the context-w handling of `#` in `_skip_substitution`
in `codex-hook-interactive-guard.py`.

**Component Diagram:**
```
_skip_substitution
  context w entry
    stack[-2] != "w"  (outermost entry)  -> existing comment reading (FR2)
    stack[-2] == "w"  (nested entry)     -> `#` is a word character (FR1)
```

### Data Flow

```
PreToolUse(Bash) JSON (stdin) -> codex-hook-interactive-guard.py -> deny / no output
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`: byte-identical copies (FR3)
- `tests/test_codex_hook_interactive_guard.py`: `CASES` table run against both copies (FR4)

**External Dependencies:**
- None

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py
em-review/scripts/codex-hook-interactive-guard.py
tests/test_codex_hook_interactive_guard.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-for-wordlist-glob-qualifier/**`
- `test-docs/codex-guard-for-wordlist-glob-qualifier/**`

`feature-docs/codex-guard-for-wordlist-glob-qualifier/**` covers
`REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These
are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/codex-guard-for-wordlist-glob-qualifier/**` covers
`test-docs/codex-guard-for-wordlist-glob-qualifier/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-for-wordlist-glob-qualifier/` directory at all; the
declared `test-docs/codex-guard-for-wordlist-glob-qualifier/**` entry is
still correct in that case — a declared path that never materializes is
not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (FR1, FR4): `zsh -c 'setopt extendedglob; echo "$(for x (*(#qN)) { :; })"; python3 -i'` - deny
- [ ] TS2 (FR1, FR4): `echo "$(for x (*(#qN)) { :; })"; python3 -i` - deny
- [ ] TS3 (FR2): existing substitution-reading TS8 `echo "$(for x (# c\na) { case x in x) printf '%s' '"';; esac; })"; python3 -i` - deny (unchanged, keeps passing)
- [ ] TS4 (FR2): existing substitution-reading TS1, TS5, TS6, TS7, TS28 - deny (unchanged, keep passing)
- [ ] TS5 (NFR1): existing test_ts26_commented_lines_in_a_for_word_list_are_read_in_time - passes (unchanged)
- [ ] TS6 (FR3): TestCopies.test_the_two_copies_are_byte_identical - passes

Run command: `python3 -m unittest tests.test_codex_hook_interactive_guard`

### Integration Tests
- None

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] In a nested entry (`stack[-2] == "w"`), a `#` preceded by space or similar also does not start a comment (assumption A2)
- [ ] Out of scope: the misreading of `$(ls *(#qN))` in context p is not changed (assumption A3)

### Performance Tests
- [ ] TS5 (NFR1) above

## Security Considerations

- **Input Validation:** The fix removes a fail-open path in the hook's static reading of `tool_input.command` (FR1).
- Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF: Not applicable.

## Error Handling

Not applicable.

## Performance Optimization

### Performance Goals
- NFR1: constant-time added check per character (`stack[-2]` lookup); TS26 decided within its time limit.

## Assumptions

- **A1:** Whether an entry is nested can be decided by `stack[-2] == "w"`. A `(` read inside context w always pushes a w entry, and beneath the outermost w is something other than w (p, 8, etc.).
- **A2:** Under FR2, in a nested entry a `#` preceded by space or similar does not start a comment either.
- **A3:** The misreading of `$(ls *(#qN))` in context p is out of scope and is not changed.
- **A4:** The plugin version is not touched.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals (NFR1)
- [ ] The two copies remain byte-identical

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None

## References

- `em-review/scripts/codex-hook-interactive-guard.py:2539`
- `em-workflow/scripts/codex-hook-interactive-guard.py` (identical content)
